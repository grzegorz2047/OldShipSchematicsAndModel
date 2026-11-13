"""Canonical guide-based asset packaging: names, GLB, packed scene and static LODs."""
import json
from pathlib import Path
import re
import sys
import unicodedata

import bpy

ROOT=Path(__file__).resolve().parents[2]
for source in (ROOT/'blender',ROOT/'upstream'/'blender'):
    if source.exists() and str(source) not in sys.path:
        sys.path.insert(0,str(source))
try:
    import nazwy_publiczne as NP
except ImportError:
    NP=None


def snake(name):
    name=str(name)
    if NP:
        try:
            translated=NP.en(name)
            if translated:name=translated
        except (KeyError,ValueError,TypeError):pass
    name=str(name).replace('ł','l').replace('Ł','L')
    name=unicodedata.normalize('NFKD',name).encode('ascii','ignore').decode()
    name=re.sub(r'([a-z0-9])([A-Z])',r'\1_\2',name)
    name=re.sub(r'[^a-z0-9]+','_',name.lower()).strip('_') or 'asset_node'
    if NP:
        tokens=[]
        for token in name.split('_'):
            translated=NP.SLOWA.get(token,token)
            tokens.append(str(translated) if translated else token)
        name='_'.join(tokens)
    return re.sub(r'[^a-z0-9]+','_',name.lower()).strip('_') or 'asset_node'


def remap(value,names):
    if isinstance(value,str):return names.get(value,value)
    if isinstance(value,list):return [remap(v,names) for v in value]
    if isinstance(value,tuple):return tuple(remap(v,names) for v in value)
    if isinstance(value,dict):return {k:remap(v,names) if k!='source_name' else v for k,v in value.items()}
    return value


def normalize(objects):
    names={};used=set()
    for o in sorted(objects,key=lambda ob:ob.name):
        old=o.name;base=snake(old);new=base;n=1
        while new in used:
            new=base+'_%03d'%n;n+=1
        used.add(new);names[old]=new
    # Temporary names prevent Blender from adding incidental .001 suffixes.
    originals={o:o.name for o in objects}
    for i,o in enumerate(objects):o.name='_name_normalization_%06d'%i
    for o,old in originals.items():
        o.name=names[old]
        if old!=o.name:o['source_name']=old
        if o.type=='MESH' and o.data.users==1:o.data.name=o.name+'_mesh'
    for material in list(bpy.data.materials):
        material.name=snake(material.name)
    for image in list(bpy.data.images):
        image.name=snake(image.name)
    for o in objects:
        for key in list(o.keys()):
            if key=='source_name':continue
            value=o[key]
            if isinstance(value,str) and value in names:o[key]=names[value]
    return names


def triangles(objects):
    total=0
    for o in objects:
        if o.type=='MESH':
            o.data.calc_loop_triangles();total+=len(o.data.loop_triangles)
    return total


def export_glb(path,objects):
    bpy.ops.object.select_all(action='DESELECT')
    prior=[]
    for o in objects:
        prior.append((o,o.hide_get(),o.hide_viewport))
        o.hide_viewport=False;o.hide_set(False);o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,
        export_extras=True,export_yup=True,export_apply=True,export_animations=False,
        export_materials='EXPORT',export_image_format='AUTO',export_cameras=False,
        export_lights=False,export_texcoords=True,export_normals=True,export_tangents=False)
    for o,hidden,viewport in prior:o.hide_set(hidden);o.hide_viewport=viewport


def lod(objects,path,level):
    ratio=.50 if level==1 else .08
    temps=[];materials={};images={}
    max_image=1024 if level==1 else 512
    for o in objects:
        if o.type!='MESH':continue
        kind=str(o.get('kind',o.get('role',''))).lower()
        fine=any(t in o.name for t in ('ratline','footrope','bolt_rope','running','lanyard','trunnel'))
        if level==2 and fine:continue
        clone=o.copy();clone.data=o.data.copy();clone.name='lod%d_'%level+o.name
        clone.parent=None;clone.matrix_world=o.matrix_world.copy()
        bpy.context.scene.collection.objects.link(clone);temps.append(clone)
        clone.hide_render=False;clone.hide_set(False)
        clone.data.calc_loop_triangles()
        count=len(clone.data.loop_triangles)
        if count>24:
            dec=clone.modifiers.new('distance_simplification','DECIMATE')
            dec.ratio=max(ratio,.22) if kind in ('rope','rigging') else ratio
            bpy.context.view_layer.objects.active=clone
            try:bpy.ops.object.modifier_apply(modifier=dec.name)
            except RuntimeError:clone.modifiers.remove(dec)
        for i,m in enumerate(list(clone.data.materials)):
            if not m:continue
            key=m.as_pointer()
            if key not in materials:
                nm=m.copy();nm.name='lod%d_'%level+m.name
                if nm.use_nodes:
                    for node in nm.node_tree.nodes:
                        if node.type=='TEX_IMAGE' and node.image:
                            old=node.image;k=old.as_pointer()
                            if k not in images:
                                im=old.copy();im.name='lod%d_'%level+old.name
                                scale=min(1,max_image/max(im.size))
                                if scale<1:im.scale(max(1,round(im.size[0]*scale)),max(1,round(im.size[1]*scale)))
                                images[k]=im
                            node.image=images[k]
                materials[key]=nm
            clone.data.materials[i]=materials[key]
    export_glb(path,temps)
    count=triangles(temps)
    for o in temps:
        mesh=o.data;bpy.data.objects.remove(o,do_unlink=True)
        if mesh.users==0:bpy.data.meshes.remove(mesh)
    for m in materials.values():
        if m.users==0:bpy.data.materials.remove(m)
    for im in images.values():
        if im.users==0:bpy.data.images.remove(im)
    return count


def finalize(spec,out,visual_objects=None,collision_objects=None,navigation=None,design=None,
             generate_lods=True):
    out=Path(out).resolve();model=out/'model';model.mkdir(parents=True,exist_ok=True)
    scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    all_objects=list(scene.objects)
    collisions=list(collision_objects) if collision_objects is not None else [o for o in all_objects
        if o.get('asset_role')=='collision' or o.name.lower().startswith('col_')]
    visual=list(visual_objects) if visual_objects is not None else [o for o in all_objects
        if o not in collisions and o.get('asset_role')!='presentation' and
        o.type in ('MESH','EMPTY') and (not o.hide_render or o.type=='EMPTY')]
    if not collisions or not any(o.type=='MESH' for o in visual):
        raise ValueError('Both visual and collision geometry are required')
    for o in visual:
        if not o.get('asset_role'):o['asset_role']='marker' if o.type=='EMPTY' else 'visual'
    for o in collisions:o['asset_role']='collision'
    selected=list(dict.fromkeys(visual+collisions))
    names=normalize(selected)
    navigation=remap(navigation or json.loads((out/'navigation.json').read_text(encoding='utf-8')),names)
    design=remap(design or json.loads((out/'design.json').read_text(encoding='utf-8')),names)
    debug=bpy.data.materials.get('collision_debug') or bpy.data.materials.new('collision_debug')
    debug.diffuse_color=(.1,.5,.2,1);debug.use_nodes=True
    for o in collisions:
        if o.type=='MESH':o.data.materials.clear();o.data.materials.append(debug)
    export_glb(model/'ship.glb',visual)
    export_glb(model/'collision.glb',collisions)
    counts={'lod0':triangles(visual),'collision':triangles(collisions)}
    if generate_lods:
        counts['lod1']=lod(visual,model/'ship_lod1.glb',1)
        counts['lod2']=lod(visual,model/'ship_lod2.glb',2)
    for o in collisions:o.hide_render=True;o.hide_set(True)
    bpy.data.orphans_purge(do_local_ids=True,do_linked_ids=True,do_recursive=True)
    for im in bpy.data.images:
        if im.source=='FILE' and not im.packed_file:
            try:im.pack()
            except RuntimeError:pass
    scene.frame_set(0)
    bpy.ops.wm.save_as_mainfile(filepath=str(model/'ship.blend'),compress=True)
    design['triangles']=counts
    design['export']={'units':'metres','axes':'glTF +X port, +Y up, +Z forward',
        'animations':'authored static pose; transforms/pivot markers retained',
        'lods':'static distance meshes with 1024/512 max texture dimension',
        'collision_mode':'separate static concave meshes; moving parts require engine setup'}
    for name,value in [('spec.json',spec),('navigation.json',navigation),('design.json',design),('name-map.json',names)]:
        (out/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('CANONICAL_EXPORT',spec['id'],counts,flush=True)
    return {'objects':visual,'collisions':collisions,'names':names,'triangles':counts,
            'navigation':navigation,'design':design}
