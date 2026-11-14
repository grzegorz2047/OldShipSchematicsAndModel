"""Render the delivered construction-boat states and check source/export parity.

Blender 5.2.3:
  blender -b -t 1 --factory-startup --python-exit-code 1 --python
  sailertales/boat-frame/preview.py -- --asset-dir sailertales/boat-frame --resolution 800

Every public PNG comes from reimported delivered GLBs. Stage 3 already includes
trim; trim.glb is never added on top of ship.glb. Repair morphs are inspected
in separate fresh imports. The authoring scene is used only for control images.
"""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE=Path(__file__).resolve().parent
COMMON=HERE.parent/'common'
sys.path.insert(0,str(COMMON))
from v2_review import render,compare,triangle_count


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def visible_meshes():
    return [o for o in bpy.context.scene.objects if o.type=='MESH' and
            o.get('asset_role')=='visual' and not o.hide_render]


def evaluated_points(objects):
    dg=bpy.context.evaluated_depsgraph_get()
    return [o.matrix_world@Vector(p) for o in objects for p in o.evaluated_get(dg).bound_box]


def center(points):
    lo=Vector(tuple(min(p[k] for p in points) for k in range(3)))
    hi=Vector(tuple(max(p[k] for p in points) for k in range(3)))
    return (lo+hi)/2


def camera(points,direction=(1.4,1.65,.95),target=None,scale=None,margin=1.13):
    if not points:raise RuntimeError('No visible asset geometry to frame')
    target=Vector(target) if target is not None else center(points)
    direction=Vector(direction).normalized()
    span=max((p-target).length for p in points)*2
    position=target+direction*max(span*2,4)
    rotation=(target-position).to_track_quat('-Z','Y').to_matrix().transposed()
    local=[rotation@(p-target) for p in points]
    if scale is None:
        width=2*max(abs(p.x) for p in local)
        height=2*max(abs(p.y) for p in local)
        scale=max(width,height*1.25)*margin
    return {'position':list(position),'target':list(target),'ortho':True,
            'scale':float(scale),'hide_rig':False}


def load_glb(path,reset=True):
    if reset:bpy.ops.wm.read_factory_settings(use_empty=True)
    before=set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    bpy.context.view_layer.update()
    return [o for o in bpy.context.scene.objects if o not in before]


def find_record(value,name):
    if isinstance(value,dict):
        if name in value:return value[name]
        if value.get('name',value.get('id'))==name:return value
        for child in value.values():
            result=find_record(child,name)
            if result is not None:return result
    elif isinstance(value,list):
        for child in value:
            result=find_record(child,name)
            if result is not None:return result
    return None


def hook_point(asset,name):
    obj=bpy.data.objects.get(name)
    if obj is None:obj=next((o for o in bpy.context.scene.objects if o.name.endswith(name)),None)
    if obj is not None:return obj.matrix_world.translation.copy(),'delivered anchor node '+obj.name
    path=asset/'hooks.json'
    if path.exists():
        value=find_record(json.loads(path.read_text(encoding='utf-8')),name)
        if isinstance(value,dict):
            for key in ('position_blender_m','position_blender','blender_m','blender'):
                if key in value:return Vector(value[key]),'hooks.json:'+name+':'+key
            for key in ('position_gltf_m','position_gltf','gltf_m','gltf','position_m','position'):
                if key in value:
                    p=value[key];return Vector((p[0],-p[2],p[1])),'hooks.json:'+name+':'+key
        elif isinstance(value,list) and len(value)==3:
            return Vector((value[0],-value[2],value[1])),'hooks.json:'+name
    raise RuntimeError('Missing repair_gap_center in delivered anchors or hooks.json')


def signature(objects):
    result={}
    for obj in objects:
        points=evaluated_points([obj])
        result[obj.name]={'triangles':triangle_count([obj]),
            'min': [min(p[k] for p in points) for k in range(3)],
            'max': [max(p[k] for p in points) for k in range(3)]}
    return result


def signature_comparison(source,exported):
    missing=sorted(set(source)-set(exported));extra=sorted(set(exported)-set(source))
    counts=[];maximum=0.
    for name in sorted(set(source)&set(exported)):
        a,b=source[name],exported[name]
        if a['triangles']!=b['triangles']:counts.append(name)
        maximum=max(maximum,max(abs(a[key][i]-b[key][i]) for key in ('min','max') for i in range(3)))
    return {'passed':not missing and not extra and not counts and maximum<=1e-4,
            'missing_nodes':missing,'extra_nodes':extra,'triangle_mismatch_nodes':counts,
            'maximum_bounds_difference_m':maximum,'bounds_tolerance_m':1e-4}


def set_repair_pose(objects,straight):
    keys=[]
    for obj in objects:
        if obj.type!='MESH' or obj.data.shape_keys is None:continue
        data=obj.data.shape_keys
        if data.animation_data:data.animation_data_clear()
        variants=list(data.key_blocks)[1:]
        if not variants:continue
        for key in variants:key.value=0
        selected=next((key for key in variants if 'straight' in key.name.lower()),None)
        if selected is None and len(variants)==1:selected=variants[0]
        if selected is None:raise RuntimeError('Ambiguous straight repair-plank morph: '+obj.name)
        selected.value=1. if straight else 0.
        keys.append({'node':obj.name,'morph':selected.name,'value':float(selected.value)})
    if not keys:raise RuntimeError('Delivered repair_plank.glb has no straight morph')
    bpy.context.view_layer.update()
    return keys


def render_previews(asset_dir,resolution=800,include_pegs=False):
    asset=Path(asset_dir).resolve();model=asset/'model'
    required=['ship.blend','ship.glb','stage_0.glb','stage_1.glb','stage_2.glb','repair_plank.glb','trim.glb']
    missing=[name for name in required if not (model/name).is_file()]
    if missing:raise FileNotFoundError('Construction-boat preview inputs missing: '+', '.join(missing))
    if include_pegs and not (model/'pegs_5.glb').is_file():raise FileNotFoundError(model/'pegs_5.glb')
    inputs={('model/'+name):(model/name) for name in required}
    for name in ('pegs_5.glb',):
        if (model/name).is_file():inputs['model/'+name]=model/name
    for name in ('hooks.json','states.json','workstates.json','design.json','spec.json'):
        if (asset/name).is_file():inputs[name]=asset/name
    hashes={name:digest(path) for name,path in inputs.items()}
    previews=asset/'previews';previews.mkdir(parents=True,exist_ok=True)
    review=asset/'review';review.mkdir(parents=True,exist_ok=True)

    # Source visibility is the builder's canonical stage-3/trim-on state. Hidden
    # stage and component objects stay hidden; they are never inferred from GLB.
    bpy.ops.wm.open_mainfile(filepath=str(model/'ship.blend'),load_ui=False)
    bpy.context.scene.frame_set(0)
    source=visible_meshes()
    if not source:raise RuntimeError('Packed source has no visible asset_role=visual meshes')
    source_signature=signature(source);source_count=triangle_count(source)
    hero=camera(evaluated_points(source))
    gap,gap_evidence=hook_point(asset,'repair_gap_center')
    try:
        first,_=hook_point(asset,'peg_0');last,_=hook_point(asset,'peg_4')
        along=(last-first).normalized()
        detail_points=[first-along*.45,last+along*.45,gap+Vector((0,0,.32)),gap-Vector((0,0,.32))]
        detail=camera(detail_points,direction=(3.8,.8,.75),target=gap,margin=1.15)
    except RuntimeError:
        detail=camera([gap],direction=(3.8,.8,.75),target=gap,scale=3.7)
    deck=camera(evaluated_points(source),direction=(1.0,1.3,2.5))
    definitions={'hero':hero,'deck':deck,'repair_gap_detail':detail}
    states={}
    for obj in source:
        value=str(obj.get('export_state','unspecified'));states[value]=states.get(value,0)+1
    for name,definition in definitions.items():render(definition,review/('source_'+name+'.png'),resolution)

    load_glb(model/'ship.glb');exported=visible_meshes()
    exported_signature=signature(exported);export_count=triangle_count(exported)
    parity=signature_comparison(source_signature,exported_signature)
    for name,definition in definitions.items():render(definition,previews/(name+'.png'),resolution)
    comparisons={name:compare(review/('source_'+name+'.png'),previews/(name+'.png')) for name in definitions}
    shutil.copyfile(previews/'hero.png',previews/'stage_3.png')
    stage_renders={'3':{'model':'model/ship.glb','image':'previews/stage_3.png',
        'same_actual_render_as':'previews/hero.png','trim_on':True,'pegs_on':False}}
    for stage in range(3):
        filename='stage_'+str(stage)+'.glb';load_glb(model/filename)
        render(hero,previews/('stage_'+str(stage)+'.png'),resolution)
        stage_renders[str(stage)]={'model':'model/'+filename,'image':'previews/stage_'+str(stage)+'.png'}

    # Component extraction is inspected independently. Hiding exactly the trim
    # nodes in a fresh main-GLB import demonstrates the runtime off state.
    load_glb(model/'trim.glb');trim_names={o.name for o in visible_meshes()}
    load_glb(model/'ship.glb');main={o.name:o for o in visible_meshes()}
    if not trim_names or not trim_names.issubset(main):
        raise RuntimeError('trim.glb node names do not identify a main-asset subset: '+str(sorted(trim_names-set(main))))
    for name in trim_names:main[name].hide_render=True
    render(hero,previews/'hero_trim_off.png',resolution)
    trim={'included_in_main_glb':True,'nodes_hidden_for_off_preview':sorted(trim_names),
          'off_image':'previews/hero_trim_off.png','duplicate_trim_imported_for_hero':False}

    # Recenter the CAMERA, not the component geometry, for two comparable views
    # of the actual fitted base and straight morph. Both use the same scale.
    load_glb(model/'repair_plank.glb');repair_objects=list(bpy.context.scene.objects)
    fitted_keys=set_repair_pose(repair_objects,False);fitted_points=evaluated_points(visible_meshes())
    straight_keys=set_repair_pose(repair_objects,True);straight_points=evaluated_points(visible_meshes())
    fitted_camera=camera(fitted_points,direction=(1.35,.85,.7))
    straight_camera=camera(straight_points,direction=(1.35,.85,.7))
    scale=max(fitted_camera['scale'],straight_camera['scale'])
    fitted_camera['scale']=straight_camera['scale']=scale
    set_repair_pose(repair_objects,False);render(fitted_camera,previews/'repair_fitted.png',resolution)
    set_repair_pose(repair_objects,True);render(straight_camera,previews/'repair_straight.png',resolution)
    load_glb(model/'ship.glb');added=load_glb(model/'repair_plank.glb',reset=False)
    installed_keys=set_repair_pose(added,False)
    if include_pegs:load_glb(model/'pegs_5.glb',reset=False)
    render(hero,previews/'repair_installed.png',resolution)
    render(detail,previews/'repair_installed_detail.png',resolution)
    repair={'model':'model/repair_plank.glb','fitted_morphs':fitted_keys,'straight_morphs':straight_keys,
        'installed_morphs':installed_keys,'pegs_in_installed_preview':include_pegs,
        'fitted_image':'previews/repair_fitted.png','straight_image':'previews/repair_straight.png',
        'installed_image':'previews/repair_installed.png',
        'installed_detail_image':'previews/repair_installed_detail.png',
        'camera_policy':'fitted and straight component views are separately centered with identical direction and orthographic scale',
        'cameras':{'fitted':fitted_camera,'straight':straight_camera}}
    if any(digest(inputs[name])!=expected for name,expected in hashes.items()):
        raise RuntimeError('Input assets changed while the previews were rendering')
    outputs={p.relative_to(asset).as_posix():digest(p) for folder in (previews,review) for p in sorted(folder.glob('*.png')) if not p.name.startswith('audit_')}
    result={'schema':1,'vessel':'boat-frame','passed':parity['passed'] and all(v['passed'] for v in comparisons.values()),
        'source_triangles':source_count,'export_triangles':export_count,'triangle_match':source_count==export_count,
        'geometry_parity':parity,'views':comparisons,'cameras':definitions,
        'view_labels':{'hero':'Canonical construction boat, stage3, trim on, repair gap open',
                       'deck':'Top three-quarter construction workspace overview; no walkable deck or player route is claimed',
                       'repair_gap_detail':'Positive-X repair side; missing plank and its five peg positions'},
        'thresholds':{'brightness_fraction':.10,'channel_share_difference':.04},
        'source_visible_export_states':states,'repair_anchor_evidence':gap_evidence,
        'stage_renders':stage_renders,'trim_toggle':trim,'repair_component':repair,
        'render':{'engine':'Cycles','samples':12,'resolution':[resolution,round(resolution*.8)]},
        'scope':'Source/export parity covers canonical stage3 with trim on and pegs off; every public preview is rendered from delivered GLBs.',
        'coordinate_system':'Blender X across, -Y forward, Z up; GLB X across, Y up, +Z forward; +X is the repair-gap side.',
        'sha256':hashes,'output_sha256':outputs,
        'preview_source_sha256':{str(Path(__file__).relative_to(HERE.parents[1])):digest(__file__),
                                'sailertales/common/v2_review.py':digest(COMMON/'v2_review.py')}}
    (asset/'export-review.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('BOAT_FRAME_PREVIEWS',json.dumps({'passed':result['passed'],'images':len(outputs),
        'source_triangles':source_count,'export_triangles':export_count,'views':comparisons}),flush=True)
    if not result['passed']:raise RuntimeError('Construction-boat source/export parity failed')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset-dir',default=str(HERE))
    parser.add_argument('--resolution',type=int,default=800)
    parser.add_argument('--include-pegs',action='store_true',help='Show pegs_5 only in the fitted installed-workpiece preview; never in the gap hero.')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    if not 320<=args.resolution<=1600:raise ValueError('Preview resolution must be320–1600pixels')
    render_previews(args.asset_dir,args.resolution,args.include_pegs)
