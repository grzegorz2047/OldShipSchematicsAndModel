"""Render actual delivered GLB and compare it with its packed authoring scene.

Blender CLI: --python v2_review.py -- ASSET_DIRECTORY [--resolution 640]
Writes export-review.json; source comparison images stay under review/.
The four canonical GLB views are kept in previews/; no presentation mesh enters GLB.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector


def point(q):return Vector((q[0],-q[2],q[1]))


def candidates():
    return [o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render
            and o.get('asset_role') not in ('collision','presentation')
            and not o.name.lower().startswith('col_')]


def setup(resolution):
    scene=bpy.context.scene
    for o in list(scene.objects):
        if o.type in ('CAMERA','LIGHT'):
            bpy.data.objects.remove(o,do_unlink=True)
        elif o.get('asset_role') in ('collision','presentation') or o.name.lower().startswith('col_'):
            o.hide_render=True
    scene.render.engine='CYCLES';scene.cycles.samples=12
    scene.cycles.use_denoising=True
    scene.render.resolution_x=resolution;scene.render.resolution_y=round(resolution*.8)
    scene.render.resolution_percentage=100
    scene.view_settings.view_transform='AgX'
    scene.view_settings.look='AgX - Medium High Contrast'
    world=bpy.data.worlds.new('review_world');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs['Color'].default_value=(.18,.18,.18,1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value=.65
    scene.world=world
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGB'
    return scene


def bounds(objects):
    points=[o.matrix_world@Vector(p) for o in objects for p in o.bound_box]
    lo=Vector(tuple(min(p[k] for p in points) for k in range(3)))
    hi=Vector(tuple(max(p[k] for p in points) for k in range(3)))
    return lo,hi


def triangle_count(objects):
    total=0;deps=bpy.context.evaluated_depsgraph_get()
    for o in objects:
        evaluated=o.evaluated_get(deps);mesh=evaluated.to_mesh()
        mesh.calc_loop_triangles();total+=len(mesh.loop_triangles)
        evaluated.to_mesh_clear()
    return total


def views(nav):
    objs=candidates();lo,hi=bounds(objs);center=(lo+hi)/2
    span=max((hi-lo).length,3)
    result={}
    for name,direction in [('hero',(1.15,1.65,.72)),('stern',(.15,1.8,.33))]:
        result[name]={'target':list(center),'position':list(center+Vector(direction).normalized()*span*2),
                      'ortho':True,'scale':None,'hide_rig':False}
    route=next((r for r in nav.get('routes',[]) if r.get('mode','walk')=='walk'),None)
    deck_height=float(np.median([q[1] for q in route['points']])) if route else lo.z+(hi.z-lo.z)*.12
    deck_center=Vector((0,(lo.y+hi.y)/2,deck_height))
    result['deck']={'target':list(deck_center),'position':list(deck_center+Vector((.8,1.2,2.2)).normalized()*span*2),
                    'ortho':True,'scale':None,'hide_rig':True}
    helm=next((o for o in objs if any(t in o.name.lower() for t in ('steering_wheel','helm_wheel','kolo_sterowe'))),None)
    if helm:
        hlo,hhi=bounds([helm]);target=(hlo+hhi)/2
        result['helm']={'target':list(target),'position':list(target+Vector((2.5,3.,1.4))),
                        'ortho':True,'scale':4.5,'hide_rig':False}
    else:
        foot=point(route['points'][0]) if route else deck_center
        result['helm']={'target':list(deck_center+Vector((0,0,.2))),
                       'position':list(foot+Vector((1.2,1.8,1.85))),
                       'ortho':False,'lens':24.,'hide_rig':False}
    for route in nav.get('routes',[]):
        key='cabin' if 'cabin' in route['name'] else 'hold' if 'hold_aisle' in route['name'] or 'hold_mast' in route['name'] else None
        if key and len(route['points'])>1:
            a=point(route['points'][-2]);b=point(route['points'][-1])
            if (a-b).length<.20:continue
            result[key]={'position':list(a+Vector((0,0,1.50))),
                         'target':list(b+Vector((0,0,1.20))),
                         'ortho':False,'lens':24.,'hide_rig':False}
    for definition in result.values():
        if definition['ortho'] and definition['scale'] is None:
            selected=objs
            if definition['hide_rig']:
                selected=[o for o in objs if not rig_object(o)]
            pos=Vector(definition['position']);target=Vector(definition['target'])
            rotation=(target-pos).to_track_quat('-Z','Y').to_matrix().transposed()
            points=[rotation@(o.matrix_world@Vector(p)-target) for o in selected for p in o.bound_box]
            width=max(p.x for p in points)-min(p.x for p in points)
            height=max(p.y for p in points)-min(p.y for p in points)
            definition['scale']=max(width,height*1.25)*1.15
    return result


def rig_object(o):
    kind=str(o.get('kind',o.get('role',''))).lower()
    return kind in ('sail','canvas','rope','rigging','spar','mast','yard') or any(t in o.name.lower()
        for t in ('sail','shroud','ratline','stay','rope','yard','mast','bukszpryt','reja','zagiel','lina_','maszt'))


def render(definition,path,resolution):
    scene=setup(resolution)
    hidden=[]
    if definition['hide_rig']:
        for o in candidates():
            if rig_object(o):hidden.append(o);o.hide_render=True
    pos=Vector(definition['position']);target=Vector(definition['target'])
    bpy.ops.object.camera_add(location=pos)
    camera=bpy.context.object;camera.rotation_euler=(target-pos).to_track_quat('-Z','Y').to_euler()
    camera.data.clip_start=.02;camera.data.clip_end=1000
    if definition['ortho']:
        camera.data.type='ORTHO';camera.data.ortho_scale=definition['scale']
    else:camera.data.lens=definition.get('lens',24.)
    scene.camera=camera
    lo,hi=bounds(candidates());span=max((hi-lo).length,3);center=(lo+hi)/2
    for direction,power in [((.8,1.,1.4),45),((-1.,-.7,.8),24)]:
        bpy.ops.object.light_add(type='AREA',location=center+Vector(direction)*span*.8)
        light=bpy.context.object;light.data.energy=power*span*span;light.data.size=span*.8
        light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
    if not definition['ortho']:
        bpy.ops.object.light_add(type='AREA',location=pos)
        light=bpy.context.object;light.data.energy=45;light.data.size=2
        light.rotation_euler=camera.rotation_euler
    scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
    for o in hidden:o.hide_render=False


def pixels(path):
    im=bpy.data.images.load(str(path),check_existing=False)
    im.colorspace_settings.name='Non-Color'
    values=np.empty(len(im.pixels),np.float32);im.pixels.foreach_get(values)
    values=values.reshape((-1,4))[:,:3].copy()
    bpy.data.images.remove(im)
    return values


def compare(a,b):
    aa=pixels(a);bb=pixels(b)
    background=np.median(np.concatenate((aa[:50],aa[-50:])),axis=0)
    mask=(np.linalg.norm(aa-background,axis=1)>.045)|(np.linalg.norm(bb-background,axis=1)>.045)
    if mask.sum()<100:mask=np.ones(len(aa),bool)
    ma=aa[mask].mean(axis=0);mb=bb[mask].mean(axis=0)
    luminance=np.array((.2126,.7152,.0722))
    brightness=abs(float((mb-ma)@luminance))/max(float(ma@luminance),.02)
    shares_a=ma/max(float(ma.sum()),1e-6);shares_b=mb/max(float(mb.sum()),1e-6)
    share=float(np.max(np.abs(shares_a-shares_b)))
    return {'foreground_pixels':int(mask.sum()),'source_mean_rgb':ma.tolist(),
            'export_mean_rgb':mb.tolist(),'brightness_fraction':brightness,
            'maximum_channel_share_difference':share,'passed':brightness<=.10 and share<=.04}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('asset');ap.add_argument('--resolution',type=int,default=640)
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=Path(args.asset).resolve();review=out/'review';review.mkdir(exist_ok=True)
    previews=out/'previews';previews.mkdir(exist_ok=True)
    nav=json.loads((out/'navigation.json').read_text(encoding='utf-8'))
    bpy.ops.wm.open_mainfile(filepath=str(out/'model/ship.blend'),load_ui=False)
    scene=bpy.context.scene;scene.frame_set(0)
    definitions=views(nav)
    source_counts=triangle_count(candidates())
    for name,definition in definitions.items():
        render(definition,review/('source_'+name+'.png'),args.resolution)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(out/'model/ship.glb'))
    bpy.context.view_layer.update()
    export_counts=triangle_count(candidates())
    for name,definition in definitions.items():
        render(definition,previews/(name+'.png'),args.resolution)
    comparisons={name:compare(review/('source_'+name+'.png'),previews/(name+'.png')) for name in definitions}
    result={'schema':1,'source_triangles':source_counts,'export_triangles':export_counts,
       'triangle_match':source_counts==export_counts,'views':comparisons,'cameras':definitions,
       'thresholds':{'brightness_fraction':.10,'channel_share_difference':.04},
       'scope':'Actual exported GLB vs packed source under identical camera/light. Deck view hides tagged rig in both.',
       'presentation':'review lighting only; interior views include a camera-area fill',
       'sha256':{name:hashlib.sha256((out/name).read_bytes()).hexdigest()
                 for name in ('model/ship.blend','model/ship.glb')}}
    result['passed']=result['triangle_match'] and all(r['passed'] for r in comparisons.values())
    (out/'export-review.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('EXPORT_REVIEW',out.name,result['passed'],comparisons,flush=True)
    if not result['passed']:raise RuntimeError('Export/source render difference exceeds guide threshold')


if __name__=='__main__':main()
