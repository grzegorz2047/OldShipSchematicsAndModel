"""Restore actual wheel-variant helm clearances in a guide-built brig scene.

Works on the original or exported/reimported meshes. No source files are edited.
Call repair_helm() on a packed scene before canonical re-export. The default also
adds the real stock-cover collider if the source physics omitted it.
"""
import math
import bpy
import bmesh
import numpy as np
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree


def _points(o):return [o.matrix_world@v.co for v in o.data.vertices]
def _bounds(o):
    vv=_points(o)
    return Vector(tuple(min(v[k] for v in vv) for k in range(3))),Vector(tuple(max(v[k] for v in vv) for k in range(3)))
def _overlap(a,b):return all(a[0][i]<=b[1][i] and b[0][i]<=a[1][i] for i in range(3))
def _collision(o):return o.get('asset_role')=='collision' or o.name.lower().startswith(('col_','collision_'))
def _names(o):return (o.name,str(o.get('source_name','')),str(o.get('source_assembly','')))
def _find(objects,*names):
    return next((o for o in objects if o.type=='MESH' and any(n in names for n in _names(o))),None)


def _stats(o):
    bm=bmesh.new();bm.from_mesh(o.data)
    r={'boundary_edges':sum(e.is_boundary for e in bm.edges),'non_manifold_edges':sum(not e.is_manifold for e in bm.edges),
       'zero_area_faces':sum(f.calc_area()<1e-12 for f in bm.faces),'faces':len(bm.faces)}
    bm.free();return r


def _weld(o):
    if o.data.users>1:o.data=o.data.copy()
    bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-5)
    bm.to_mesh(o.data);bm.free();o.data.update()
    s=_stats(o)
    if s['non_manifold_edges']:raise RuntimeError('Helm Boolean input not closed: '+o.name+str(s))


def _tree(o):
    vv=_points(o);return BVHTree.FromPolygons(vv,[list(p.vertices) for p in o.data.polygons])


def _material_index(o):
    for tokens in (('wood','drew'),('deck','poklad'),('paint','farba')):
        for i,m in enumerate(o.data.materials):
            if m and any(t in m.name.lower() for t in tokens):return i
    return 0


def _map_cut_uv(o,cutter_tree):
    layer=o.data.uv_layers.active or o.data.uv_layers.new(name='UVMap')
    changed=0
    for face in o.data.polygons:
        vv=[o.matrix_world@o.data.vertices[i].co for i in face.vertices]
        center=sum(vv,Vector())/len(vv);hit=cutter_tree.find_nearest(center)
        if hit[0] is None or hit[3]>.00015:continue
        normal=o.matrix_world.to_3x3()@face.normal
        if abs(normal.normalized().dot(hit[1]))<.95:continue
        # New Boolean walls get an undistorted metric chart. Original surface UVs stay intact.
        u=(vv[1]-vv[0]).normalized();n=normal.normalized();v=n.cross(u).normalized()
        mat=o.data.materials[face.material_index] if face.material_index<len(o.data.materials) else None
        images=[node.image for node in mat.node_tree.nodes if node.type=='TEX_IMAGE' and node.image] if mat and mat.use_nodes else []
        color=next((im for im in images if im.colorspace_settings.name=='sRGB'),images[0] if images else None)
        width,height=color.size if color else (1024,1024)
        for li,q in zip(face.loop_indices,vv):layer.data[li].uv=(q.dot(u)*1024/max(width,1),q.dot(v)*1024/max(height,1))
        changed+=1
    return changed


def _cut(o,cutter,label):
    _weld(o);before=_stats(o);tree=_tree(cutter)
    cutter.data.materials.clear()
    for m in o.data.materials:cutter.data.materials.append(m)
    index=_material_index(o)
    for p in cutter.data.polygons:p.material_index=index
    mod=o.modifiers.new(label,'BOOLEAN');mod.operation='DIFFERENCE';mod.solver='MANIFOLD';mod.object=cutter
    if hasattr(mod,'material_mode'):mod.material_mode='INDEX'
    with bpy.context.temp_override(object=o,active_object=o):bpy.ops.object.modifier_apply(modifier=mod.name)
    # Repair only coincident straight subdivisions, preserving UV loops and original surface shape.
    from v2_reference import stitch_collinear_seams
    stitch_collinear_seams(o)
    from v2_mesh_finish import finish_scene
    cleanup=finish_scene([o])
    after=_stats(o)
    if after['non_manifold_edges']:raise RuntimeError('Helm Boolean output not closed: '+o.name+str(after))
    mapped=_map_cut_uv(o,tree)
    return {'object':o.name,'operation':label,'before':before,'after':after,'new_wall_uv_faces':mapped,'mesh_finish':cleanup}


def _cylinder(axis_origin,axis,radius,z0,z1):
    p0=axis_origin+axis*((z0-axis_origin.z)/axis.z);p1=axis_origin+axis*((z1-axis_origin.z)/axis.z)
    bm=bmesh.new();bmesh.ops.create_cone(bm,cap_ends=True,cap_tris=False,segments=96,
        radius1=radius/math.cos(math.pi/96),radius2=radius/math.cos(math.pi/96),depth=(p1-p0).length)
    bm.transform(Matrix.Translation((p0+p1)/2)@Vector((0,0,1)).rotation_difference(axis).to_matrix().to_4x4())
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));me=bpy.data.meshes.new('helm_stock_opening_cutter_mesh');bm.to_mesh(me);bm.free()
    o=bpy.data.objects.new('helm_stock_opening_cutter',me);bpy.context.scene.collection.objects.link(o)
    o['asset_role']='presentation';return o


def _tiller_cutter(tiller,clearance=.012):
    dg=bpy.context.evaluated_depsgraph_get();me=bpy.data.meshes.new_from_object(tiller.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
    me.transform(tiller.matrix_world);bm=bmesh.new();bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-5);bm.normal_update()
    for v in bm.verts:v.co+=v.normal.normalized()*clearance
    bm.to_mesh(me);bm.free();me.update()
    o=bpy.data.objects.new('helm_tiller_envelope_cutter',me);bpy.context.scene.collection.objects.link(o);o['asset_role']='presentation'
    return o


def _deck_sampler(hull,cover,axis_origin,axis):
    vv=_points(cover);low=min(q.z for q in vv)+.08
    center=axis_origin+axis*((low-axis_origin.z)/axis.z);vertices=_points(hull);faces=[];samples=[]
    # The source cover's aft rays struck the top of the transom, making an unwanted
    # 0.6 m warped cover. Select the actual nearby quarterdeck level instead.
    for p in hull.data.polygons:
        pts=[vertices[i] for i in p.vertices];c=sum(pts,Vector())/len(pts)
        normal=(hull.matrix_world.to_3x3()@p.normal).normalized()
        if normal.z>.92 and abs(c.x-center.x)<1.2 and abs(c.y-center.y)<1.2 and low-.18<c.z<low+.23:
            faces.append(list(p.vertices));samples.extend(pts)
    if len(samples)<6:raise RuntimeError('No measured quarterdeck surface near stock cover')
    tree=BVHTree.FromPolygons(vertices,faces)
    a=np.array([[1,q.x-center.x,q.y-center.y,(q.x-center.x)**2,(q.x-center.x)*(q.y-center.y),(q.y-center.y)**2] for q in samples])
    b=np.array([q.z for q in samples]);coeff=np.linalg.lstsq(a,b,rcond=None)[0]
    def height(x,y):
        hit=tree.ray_cast(Vector((x,y,low+.4)),Vector((0,0,-1)),1.0)[0]
        if hit is not None:return hit.z
        dx,dy=x-center.x,y-center.y
        return float(np.array([1,dx,dy,dx*dx,dx*dy,dy*dy])@coeff)
    return height,{'quarterdeck_samples':len(samples),'level_selection_m':[low-.18,low+.23]}


def _rebuild_cover(cover,hull,axis_origin,axis):
    vv=_points(cover);radius=max(((q-axis_origin)-axis*(q-axis_origin).dot(axis)).length for q in vv)
    deck,proof=_deck_sampler(hull,cover,axis_origin,axis);base_z=min(q.z for q in vv)+.08
    center=axis_origin+axis*((base_z-axis_origin.z)/axis.z)
    ex=Vector((1,0,0));ex=(ex-axis*ex.dot(axis)).normalized();ey=axis.cross(ex).normalized()
    top=[];bottom=[]
    for k in range(24):
        theta=2*math.pi*k/24;q=center+radius*(ex*math.cos(theta)+ey*math.sin(theta))
        for _ in range(4):q+=axis*((deck(q.x,q.y)-.004-q.z)/axis.z)
        top.append(q.copy());bottom.append(q-axis*(.08/axis.z))
    # Keep the original object, materials, extras and world transform.
    inverse=cover.matrix_world.inverted();pts=[inverse@q for q in top+bottom]
    faces=[tuple(range(24)),tuple(reversed(range(24,48)))]+[(k,(k+1)%24,(k+1)%24+24,k+24) for k in range(24)]
    old=cover.data;me=bpy.data.meshes.new(old.name+'_measured_cover');me.from_pydata(pts,[],faces)
    for m in old.materials:me.materials.append(m)
    cover.data=me;bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();me.update()
    uv=me.uv_layers.new(name='UVMap')
    for f in me.polygons:
        p=[cover.matrix_world@me.vertices[i].co for i in f.vertices]
        tangent=Vector((0,1,0));n=(p[1]-p[0]).cross(p[2]-p[0]).normalized()
        tangent=(tangent-n*tangent.dot(n)).normalized()
        if tangent.length<.5:tangent=Vector((1,0,0))
        cross=n.cross(tangent).normalized();mat=me.materials[f.material_index] if me.materials else None
        ims=[node.image for node in mat.node_tree.nodes if node.type=='TEX_IMAGE' and node.image] if mat and mat.use_nodes else []
        im=next((im for im in ims if im.colorspace_settings.name=='sRGB'),ims[0] if ims else None);w,h=im.size if im else (1024,1024)
        for li,q in zip(f.loop_indices,p):uv.data[li].uv=(q.dot(tangent)*1024/max(w,1),q.dot(cross)*1024/max(h,1))
    cover['authored_access']=True;cover['physics']='walk_surface'
    proof.update(radius_m=radius,wall_clearance_m=.004,vertical_thickness_m=.08,
        top_gap_m=[min(deck(q.x,q.y)-q.z for q in top),max(deck(q.x,q.y)-q.z for q in top)],
        old_vertical_extent_m=[min(q.z for q in vv),max(q.z for q in vv)],new_vertical_extent_m=[min(q.z for q in top+bottom),max(q.z for q in top+bottom)])
    return radius,proof


def repair_helm(objects=None,collision_objects=None,create_cover_collision=True):
    objects=list(objects) if objects is not None else list(bpy.context.scene.objects)
    if collision_objects is not None:objects=list(dict.fromkeys(objects+list(collision_objects)))
    visual=[o for o in objects if o.type=='MESH' and not _collision(o) and o.get('asset_role')!='presentation']
    hull=_find(visual,'hull','kadlub');rudder=_find(visual,'rudder','ster');cover=_find(visual,'rudder_stock_cover','pokrywa_trzonu');tiller=_find(visual,'tiller_below_deck','rumpel_pod_pokladem')
    if any(o is None for o in (hull,rudder,cover,tiller)):raise RuntimeError('Missing required actual helm meshes')
    axis=(rudder.matrix_world.to_3x3()@Vector((0,0,1))).normalized();origin=rudder.matrix_world.translation.copy()
    radius,proof=_rebuild_cover(cover,hull,origin,axis)
    vv=_points(cover);cutter=_cylinder(origin,axis,radius+.004,min(q.z for q in vv)-.22,max(q.z for q in vv)+.05)
    operations=[]
    hull_colliders=[o for o in objects if o.type=='MESH' and _collision(o) and (o.get('kind')=='hull' or o.name.lower() in ('col_hollow_hull','col_hull','collision_hull'))]
    for o in [hull]+hull_colliders:operations.append(_cut(o,cutter,'restore_actual_stock_cover_opening'))
    bpy.data.objects.remove(cutter,do_unlink=True)
    tiller_cut=_tiller_cutter(tiller);cut_bounds=_bounds(tiller_cut)
    for o in objects:
        if o.type!='MESH' or o is tiller or o.get('kind')=='glass' or any(t in o.name.lower() for t in ('glass','szklo')):continue
        if any(n.startswith(('stern_transom','stern_carvings','rufa_pawez','rufa_rzezby','col_stern_transom','col_stern_carvings')) for n in _names(o)) and _overlap(_bounds(o),cut_bounds):
            operations.append(_cut(o,tiller_cut,'restore_actual_tiller_sweep_recess'))
    bpy.data.objects.remove(tiller_cut,do_unlink=True)
    existing=[o for o in objects if o.type=='MESH' and _collision(o) and any('stock_cover' in n or 'pokrywa_trzonu' in n for n in _names(o))]
    created=[]
    if not existing and create_cover_collision:
        c=cover.copy();c.data=cover.data.copy();c.name='col_rudder_stock_cover';bpy.context.scene.collection.objects.link(c);existing=[c];created.append(c.name)
        if collision_objects is not None:collision_objects.append(c)
    for c in existing:
        c.data=cover.data.copy();c.parent=None;c.matrix_world=cover.matrix_world.copy();c.hide_render=True;c.hide_set(True)
        c['asset_role']='collision';c['kind']='fitting';c['physics']='walk_surface'
    return {'method':'Source kadlub.py stock-cover radius+4mm opening, measured quarterdeck top-4mm cover,80mm thickness; actual tiller-shaped12mm clearance in transom/carvings.',
        'cover':proof,'operations':operations,'cover_topology':_stats(cover),'created_colliders':created,'updated_cover_colliders':[o.name for o in existing]}
