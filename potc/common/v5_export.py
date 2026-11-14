"""Detailed fleet delivery with full-resolution embedded PBR and paint-only palettes."""
import copy
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import bpy

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(ROOT/'sailertales/common')]
from v2_audit import weld_topology
from v2_export import triangles
from v5_materials import upgrade_scene
from v5_glb_pack import compact

# These comments/authoring switches are retained in source.blend and the build
# ledger. Actual geometry, material roles, timber paths and scene semantics stay
# in GLB; repeating these strings on thousands of nodes adds no runtime detail.
BUILD_ONLY_EXTRAS=('uv_method','occlusion_uv','material_roles_json','preserve_solid_lod')


def write(path,value):
    Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def paint(material,color):
    """Only a constant multiplier changes; texture/UV/PBR remain invariant."""
    material.diffuse_color=tuple(color)
    if material.use_nodes:
        node=material.node_tree.nodes.get('palette_multiplier')
        if node:node.inputs[7].default_value=tuple(color)


def export_glb(path,objects):
    bpy.ops.object.select_all(action='DESELECT')
    previous=[];source_metadata=[]
    try:
        for obj in objects:
            previous.append((obj,obj.hide_get(),obj.hide_viewport))
            obj.hide_viewport=False;obj.hide_set(False);obj.select_set(True)
            removed={key:obj[key] for key in BUILD_ONLY_EXTRAS if key in obj}
            source_metadata.append((obj,removed))
            for key in removed:del obj[key]
        bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,
            export_extras=True,export_yup=True,export_apply=True,export_animations=False,
            export_materials='EXPORT',export_image_format='AUTO',export_cameras=False,
            # glTF viewers derive the same tangent basis from normals and UV0.
            # Omitting this redundant 16-byte/vertex attribute preserves every
            # surface and map while keeping the detailed fleet packages smaller.
            export_lights=False,export_texcoords=True,export_normals=True,export_tangents=False)
        compact(path)
    finally:
        for obj,properties in source_metadata:
            for key,value in properties.items():obj[key]=value
        for obj,hidden,viewport in previous:
            obj.hide_set(hidden);obj.hide_viewport=viewport


def used_images(objects):
    result={}
    for obj in objects:
        if obj.type!='MESH':continue
        for material in obj.data.materials:
            if material and material.use_nodes:
                for node in material.node_tree.nodes:
                    if node.type=='TEX_IMAGE' and node.image:result[node.image.as_pointer()]=node.image
    return list(result.values())


def _copy_immutable(source,destination):
    if source.resolve()==destination.resolve():return
    if destination.exists():destination.unlink()
    try:os.link(source,destination)
    except OSError:shutil.copyfile(source,destination)


def _save_sources(objects,directory,level):
    """Persist exactly the map inputs used by this export, including LOD bakes."""
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    entries=[]
    for image in used_images(objects):
        source=Path(bpy.path.abspath(image.filepath)) if image.filepath else None
        name=image.name.removeprefix('lod1_').removeprefix('lod2_')
        name=Path(name).stem+'.png'
        destination=directory/name
        if source and source.exists() and source.suffix.lower()=='.png' and (level==0 or not image.get('v5_resampled',True)):
            _copy_immutable(source,destination)
        else:
            temporary=destination.with_name(destination.stem+'.tmp.png')
            image.filepath_raw=str(temporary);image.file_format='PNG';image.save()
            temporary.replace(destination)
        image.filepath_raw=str(destination)
        if not image.packed_file:image.pack()
        entries.append({'image':image.name,'file':str(destination.relative_to(directory.parents[1])),
            'pixels':list(image.size),'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),
            'bytes':destination.stat().st_size,'color_space':image.colorspace_settings.name})
    return entries


def safe_lod(ctx,level):
    """Bounded decimation retains closed fittings; main image data is never scaled."""
    objects=[];materials={};images={};target=.62 if level==1 else .30
    # Eight-k main maps have separate distance maps, never in-place resampling.
    max_image=2048 if level==1 else 1024
    for source in ctx.vis:
        if source.type!='MESH':continue
        obj=source.copy();obj.data=source.data.copy();obj.name='lod%d_'%level+source.name
        bpy.context.scene.collection.objects.link(obj);objects.append(obj)
        obj.data.calc_loop_triangles();count=len(obj.data.loop_triangles)
        if count>160 and source.get('kind')!='sail' and not source.get('preserve_solid_lod'):
            original=obj.data.copy();modifier=obj.modifiers.new('bounded_distance_mesh','DECIMATE')
            modifier.ratio=max(target,96/count);bpy.context.view_layer.objects.active=obj
            with bpy.context.temp_override(object=obj,active_object=obj):
                bpy.ops.object.modifier_apply(modifier=modifier.name)
            stats,*_=weld_topology(obj)
            bad=any(stats[key] for key in ('non_manifold_edges','zero_area_faces','duplicate_faces',
                'reversed_closed_components','nearly_zero_volume_closed_components'))
            if bad:
                discarded=obj.data;obj.data=original
                if discarded.users==0:bpy.data.meshes.remove(discarded)
            elif original.users==0:bpy.data.meshes.remove(original)
        for index,material in enumerate(list(obj.data.materials)):
            if not material:continue
            key=material.as_pointer()
            if key not in materials:
                new=material.copy();new.name='lod%d_'%level+material.name
                if new.use_nodes:
                    for node in new.node_tree.nodes:
                        if node.type!='TEX_IMAGE' or not node.image:continue
                        old=node.image;image_key=old.as_pointer()
                        if image_key not in images:
                            image=old.copy();image.name='lod%d_'%level+old.name
                            scale=min(1,max_image/max(image.size))
                            image['v5_resampled']=scale<1
                            if scale<1:image.scale(max(1,round(image.size[0]*scale)),max(1,round(image.size[1]*scale)))
                            if image.packed_file:image.unpack(method='REMOVE')
                            images[image_key]=image
                        node.image=images[image_key]
                materials[key]=new
            obj.data.materials[index]=materials[key]
        obj['asset_role']='presentation';obj.hide_render=True
    return objects



def cleanup_lod_sources(objects):
    """Remove derived distance scenes with four bounded dependency updates.

    Only collected LOD IDs whose users fall to zero are removed.  A source
    mesh/material/image shared with the editable main scene therefore survives.
    """
    objects=list(objects);meshes={};materials={}
    images=used_images(objects)
    for obj in objects:
        if obj.type!='MESH':continue
        meshes[obj.data.as_pointer()]=obj.data
        for material in obj.data.materials:
            if material:materials[material.as_pointer()]=material
    counts={'objects':len(objects),'meshes':0,'materials':0,'images':0}
    if objects:bpy.data.batch_remove(ids=set(objects))
    for key,datablocks in (('meshes',meshes.values()),('materials',materials.values()),('images',images)):
        unused={datablock for datablock in datablocks if datablock.users==0}
        counts[key]=len(unused)
        if unused:bpy.data.batch_remove(ids=unused)
    return counts


def finish(ctx,spec,out,rig):
    from v4_shipkit import rgba
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    model=out/'model';model.mkdir(exist_ok=True)
    scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
    cache=Path(os.environ.get('POTC_TEXTURE_CACHE_V5',str(ROOT/'build/pbr-v5')))
    ledger=upgrade_scene(ctx.vis,cache,materials=ctx.materials)
    # Explicit texture source files match the actual image nodes used in export.
    texture_sources={'main':_save_sources(ctx.vis,model/'textures/main',0)}
    export_glb(model/'collision.glb',ctx.col)
    lods={1:safe_lod(ctx,1),2:safe_lod(ctx,2)}
    for level,objects in lods.items():
        texture_sources['lod%d'%level]=_save_sources(objects,model/('textures/lod%d'%level),level)
    palettes=copy.deepcopy(spec.get('palettes') or [
        {'id':'ochre','paintHull':'#b18b47','paintTrim':'#38342c'},
        {'id':'navy','paintHull':'#344969','paintTrim':'#bd9d58'}])
    if len(palettes)!=2:raise ValueError('The detailed fleet contract requires exactly two paint palettes')
    for palette in palettes:
        for slot in ('paintHull','paintTrim'):palette[slot]=rgba(palette[slot])
        folder=model/palette['id'];folder.mkdir(exist_ok=True)
        for material in bpy.data.materials:
            slot=material.get('palette_slot')
            if slot in ('paintHull','paintTrim'):paint(material,palette[slot])
        export_glb(folder/'ship.glb',ctx.vis+ctx.markers)
        for level,objects in lods.items():export_glb(folder/('lod%d.glb'%level),objects)
    counts={'main_triangles':triangles(ctx.vis),'lod1_triangles':triangles(lods[1]),
        'lod2_triangles':triangles(lods[2]),'collision_triangles':triangles(ctx.col),
        'actualgun_count':len(ctx.gun_nodes)}
    # A main source scene contains its actual source geometry/images. Derived
    # distance exports have their own GLBs and source PNGs; packing duplicate
    # LOD image datablocks into both main Blends adds no editable source detail.
    cleanup_lod_sources(lods[1]+lods[2])
    for col in ctx.col:col.hide_render=True;col.hide_set(True)
    for image in used_images(ctx.vis):
        if not image.packed_file:image.pack()
    bpy.context.preferences.filepaths.save_version=0
    for palette in palettes:
        for material in bpy.data.materials:
            slot=material.get('palette_slot')
            if slot in ('paintHull','paintTrim'):paint(material,palette[slot])
        bpy.ops.wm.save_as_mainfile(filepath=str(model/palette['id']/'source.blend'),compress=True)
    research_path=Path(getattr(ctx,'detail_contract',{}).get('research_path','layout-research.json'))
    research_source=Path(getattr(ctx,'source_dir',out))/research_path
    research_output=out/research_path
    if research_source.is_file() and research_source.resolve()!=research_output.resolve():
        research_output.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(research_source,research_output)
    spec['schema']=4;spec['detail_schema']=5;spec['asset_type']='static-duel-ship';spec['palettes']=palettes
    spec['paint_materials']=['paint_hull','paint_trim']
    spec.setdefault('id',spec.get('family'));spec.setdefault('family',spec['id'])
    design={'schema':4,'detail_schema':5,'id':spec['id'],
        'construction':'Authored guide-based reconstruction with physical deck boards, timber structure, opened access and visible historical interiors. Source game statistics determine class and gun counts; dimensions/offsets are estimates, not extracted stock meshes.',
        'source':spec.get('game_source',spec.get('source',{})), 'authored_profile':spec.get('hull',{}),'rig':rig,
        'intended_joints':ctx.joints,'materials':ledger,'texture_sources':texture_sources,
        'origin':{'units':'metres','waterline_y':0,'axes':'glTF +Y up,+Z bow,+X across'},
        'collision':{'scope':'Exact closed hull/deck collider mesh copies; real ports, hatches and wells remain void. Excludes rig, fittings and gameplay walking physics.',
            'visual_nodes':[obj['visual_source'] for obj in ctx.col]},
        'type_contract':{'hull_nodes':[obj.name for obj in ctx.hull_nodes],
            'mast_nodes':[obj.name for obj in ctx.vis if obj.get('rig_member')=='mast'],
            'sail_nodes':[obj.name for obj in ctx.vis if obj.get('kind')=='sail'],
            'gun_nodes':[obj.name for obj in ctx.gun_nodes],'rig_plan':spec.get('rig',{}).get('masts',[])},
        'hull_numeric_finish':getattr(ctx,'hull_finish',[]),
        'detail_contract':getattr(ctx,'detail_contract',getattr(ctx,'detail_ledger',{})),
        'outfit':getattr(ctx,'outfit_ledger',{}),
        'counts':counts,
        'export':{'pbr':'Image basecolor + tangent normal + packed ORM embedded in every visual GLB; exact source maps in model/textures and packed in source.blend',
            'metadata':'Repeated authoring comments and LOD switches stay in source.blend; GLB retains actual geometry, material roles, timber paths, component identities and physical rig attachments.',
            'main_texture_resolution':'Deck/hull/paint 8192x2048; canvas2048x2048; no main-image downscale',
            'lod_texture_max_px':{'lod1':2048,'lod2':1024},
            'palettes':'Only paint_hull/paint_trim basecolor factors differ; natural-material maps and factors are deterministic'},
        'scope':'Static duel asset with visible historical interior structure/furnishings; no crew navigation, sailing simulation or live cannon controls.'}
    write(out/'spec.json',spec);write(out/'design.json',design)
    write(model/'texture-manifest.json',texture_sources)
    print('V5_SHIP_EXPORTED',spec['id'],design['counts'],flush=True)
    return design
