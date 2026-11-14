"""Two factor-only paint palettes and topology-preserving static POTC LODs."""
import json,math,sys,os
from pathlib import Path
import bpy
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(ROOT/'sailertales/common')]
from v2_export import export_glb,triangles
from v2_audit import weld_topology
from v2_materials import upgrade_scene


def write(path,value):Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def paint(material,color):
    material.diffuse_color=tuple(color)
    for node in material.node_tree.nodes:
        if node.type=='MIX' and node.data_type=='RGBA':node.inputs[7].default_value=tuple(color)


def safe_lod(ctx,level):
    objects=[];mats={};images={};target=.62 if level==1 else .30
    for source in ctx.vis:
        if source.type!='MESH':continue
        obj=source.copy();obj.data=source.data.copy();obj.name='lod%d_'%level+source.name
        bpy.context.scene.collection.objects.link(obj);objects.append(obj)
        obj.data.calc_loop_triangles();count=len(obj.data.loop_triangles)
        if count>160 and source.get('kind')!='sail' and not source.get('preserve_solid_lod'):
            original=obj.data.copy();modifier=obj.modifiers.new('bounded_distance_mesh','DECIMATE');modifier.ratio=max(target,96/count)
            bpy.context.view_layer.objects.active=obj
            with bpy.context.temp_override(object=obj,active_object=obj):bpy.ops.object.modifier_apply(modifier=modifier.name)
            stats,*_=weld_topology(obj)
            bad=stats['non_manifold_edges'] or stats['zero_area_faces'] or stats['duplicate_faces'] or stats['reversed_closed_components'] or stats['nearly_zero_volume_closed_components']
            if source.get('kind')!='sail' and bad:obj.data=original
        for index,material in enumerate(list(obj.data.materials)):
            key=material.as_pointer()
            if key not in mats:
                new=material.copy();new.name='lod%d_'%level+material.name
                if new.use_nodes:
                    for node in new.node_tree.nodes:
                        if node.type!='TEX_IMAGE' or not node.image:continue
                        old=node.image;ik=old.as_pointer()
                        if ik not in images:
                            image=old.copy();image.name='lod%d_'%level+old.name;scale=min(1,(1024 if level==1 else 512)/max(image.size))
                            if scale<1:image.scale(max(1,round(image.size[0]*scale)),max(1,round(image.size[1]*scale)))
                            if image.packed_file:image.unpack(method='REMOVE')
                            image.pack();images[ik]=image
                        node.image=images[ik]
                mats[key]=new
            obj.data.materials[index]=mats[key]
        obj['asset_role']='presentation';obj.hide_render=True
    return objects


def finish(ctx,spec,out,rig):
    from v4_shipkit import rgba
    out=out.resolve();out.mkdir(parents=True,exist_ok=True);(out/'model').mkdir(exist_ok=True)
    bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=1
    cache=Path(os.environ.get('POTC_TEXTURE_CACHE',str(ROOT/'build/pbr-v2')))
    old_names={role:material.name for role,material in ctx.materials.items() if role!='collision'}
    ledger=upgrade_scene(ctx.vis,cache)
    mapping={r['source']:bpy.data.materials[r['material']] for r in ledger['materials']}
    stable={'wood':'natural_wood','deck':'natural_deck_wood','spar':'natural_spar_wood','rope':'natural_rope','canvas':'natural_canvas','iron':'natural_iron','seam':'natural_seam_wood','paintHull':'paint_hull','paintTrim':'paint_trim'}
    for role,name in old_names.items():
        if name not in mapping:continue
        material=mapping[name];material.name=stable[role]
        if role in('paintHull','paintTrim'):material['palette_slot']=role
        ctx.materials[role]=material
    # Guide plank atlases are reduced to 4096x1024: still 930+ px/m on
    # the hull and 1163+ px/m on deck, with physical seams and tree-nails.
    for image in list(bpy.data.images):
        if max(image.size)>4096:
            if image.packed_file:image.unpack(method='REMOVE')
            image.scale(round(image.size[0]/2),round(image.size[1]/2));image.pack()
    # Collision geometry is an exact mesh copy of declared hull/deck objects.
    export_glb(out/'model/collision.glb',ctx.col)
    lods={1:safe_lod(ctx,1),2:safe_lod(ctx,2)}
    palettes=spec.get('palettes') or [{'id':'ochre','paintHull':'#b18b47','paintTrim':'#38342c'},{'id':'navy','paintHull':'#344969','paintTrim':'#bd9d58'}]
    for palette in palettes:
        for slot in('paintHull','paintTrim'):palette[slot]=rgba(palette[slot])
        folder=out/'model'/palette['id'];folder.mkdir(parents=True,exist_ok=True)
        for material in bpy.data.materials:
            slot=material.get('palette_slot')
            if slot in('paintHull','paintTrim'):paint(material,palette[slot])
        export_glb(folder/'ship.glb',ctx.vis+ctx.markers)
        for level,objects in lods.items():export_glb(folder/('lod%d.glb'%level),objects)
        for col in ctx.col:col.hide_render=True;col.hide_set(True)
        for image in bpy.data.images:
            if image.source=='FILE' and not image.packed_file:image.pack()
        bpy.ops.wm.save_as_mainfile(filepath=str(folder/'source.blend'),compress=True)
    spec['schema']=4;spec['asset_type']='static-duel-ship';spec['palettes']=palettes;spec['paint_materials']=['paint_hull','paint_trim']
    spec.setdefault('id',spec.get('family'));spec.setdefault('family',spec['id'])
    design={'schema':4,'id':spec['id'],'construction':'Authored procedural guide-based reconstruction. Source game stats determine class and gun counts; metre dimensions and hull offsets are estimates, not extracted stock meshes.',
      'source':spec.get('game_source',spec.get('source',{})),'authored_profile':spec.get('hull',{}),'rig':rig,
      'intended_joints':ctx.joints,'materials':ledger,'origin':{'units':'metres','waterline_y':0,'axes':'glTF +Y up,+Z bow,+X across'},
      'collision':{'scope':'Closed hollow hull shell and static deck slabs; excludes rig, fittings and gameplay walking physics. Real ports and open wells remain voids.','visual_nodes':[o['visual_source'] for o in ctx.col]},
      'type_contract':{'hull_nodes':[o.name for o in ctx.hull_nodes],'mast_nodes':[o.name for o in ctx.vis if o.get('role')=='mast' or o.get('rig_member')=='mast' or o.get('kind')=='mast' or o.name.startswith('mast_')],
        'sail_nodes':[o.name for o in ctx.vis if o.get('kind')=='sail'],'gun_nodes':[o.name for o in ctx.gun_nodes],'rig_plan':spec.get('rig',{}).get('masts',[])},
      'hull_numeric_finish':getattr(ctx,'hull_finish',[]),'counts':{'main_triangles':triangles(ctx.vis),'lod1_triangles':triangles(lods[1]),'lod2_triangles':triangles(lods[2]),'collision_triangles':triangles(ctx.col),'actualgun_count':len(ctx.gun_nodes)},
      'scope':'Static duel asset. No crew navigation, sailing physics, live cannon controls or complete interiors are claimed.'}
    write(out/'spec.json',spec);write(out/'design.json',design)
    print('V4_SHIP_EXPORTED',spec['id'],design['counts'],flush=True)
    return design
