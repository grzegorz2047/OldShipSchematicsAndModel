"""Finalize explicit big-vessel mesh topology before canonical export.

Evaluates authored modifiers, removes collinear triangulation fragments and caps
small cut ends of rope/furled fabric tubes. Open glazing remains a surface.
Every correction is recorded; the exported asset still faces an independent audit.
"""
import math
import bpy
import bmesh
from mathutils import Vector
from mathutils.kdtree import KDTree


def mesh_stats(bm):
    return {'non_manifold_edges':sum(not e.is_manifold for e in bm.edges),
            'boundary_edges':sum(e.is_boundary for e in bm.edges),
            'zero_area_faces':sum(f.calc_area()<1e-12 for f in bm.faces),
            'faces':len(bm.faces),'vertices':len(bm.verts)}


def components(bm):
    unseen=set(bm.verts)
    while unseen:
        root=unseen.pop();verts={root};queue=[root]
        while queue:
            v=queue.pop()
            for e in v.link_edges:
                w=e.other_vert(v)
                if w in unseen:unseen.remove(w);verts.add(w);queue.append(w)
        faces={f for v in verts for f in v.link_faces}
        if faces:yield verts,faces


def separate_close_contacts(bm):
    # Source primitives sometimes meet at identical corners without sharing a
    # volume. Keep both closed timber/metal pieces instead of welding that
    # corner into a non-manifold pinch. Clearance is only forty micrometres.
    count=0
    for _ in range(3):
        bm.verts.ensure_lookup_table();bm.verts.index_update();bm.normal_update()
        tree=KDTree(len(bm.verts))
        for v in bm.verts:tree.insert(v.co,v.index)
        tree.balance();moved=set()
        for v in list(bm.verts):
            for _,index,distance in tree.find_range(v.co,1.01e-5):
                if index<=v.index or index in moved:continue
                w=bm.verts[index]
                if any(e.other_vert(v) is w for e in v.link_edges):continue
                direction=w.normal.normalized()
                if direction.length<.5:direction=Vector((.37,.53,.76)).normalized()
                w.co+=direction*4e-5;moved.add(index);count+=1
        if not moved:break
    return count


def remove_opposed_duplicate_triangles(bm):
    bm.verts.index_update();bm.normal_update();groups={}
    for f in bm.faces:groups.setdefault(tuple(sorted(v.index for v in f.verts)),[]).append(f)
    remove=[]
    for fs in groups.values():
        if len(fs)<2:continue
        if len(fs)==2 and fs[0].normal.dot(fs[1].normal)<-.99:remove.extend(fs)
        else:remove.extend(fs[1:])
    if remove:bmesh.ops.delete(bm,geom=remove,context='FACES')
    return len(remove)


def triangulate_safe(bm,ngon_method):
    # Two thin adjacent n-gons may offer the same internal diagonal. Reusing
    # it would join four triangles into one edge even though both original
    # surfaces were closed. Select the other diagonal on the second quad.
    bm.verts.index_update();bm.faces.index_update();diagonals={};special=set()
    quads=[f for f in bm.faces if len(f.verts)==4]
    for f in quads:
        vv=list(f.verts)
        for a,b in ((vv[0],vv[2]),(vv[1],vv[3])):
            key=tuple(sorted((a.index,b.index)));diagonals.setdefault(key,[]).append(f)
            if bm.edges.get((a,b)) is not None:special.add(f)
    for fs in diagonals.values():
        if len(fs)>1:special.update(fs)
    for f in sorted(special,key=lambda f:f.index):
        if not f.is_valid or len(f.verts)!=4:continue
        vv=list(f.verts);first=bm.edges.get((vv[0],vv[2]));second=bm.edges.get((vv[1],vv[3]))
        method='ALTERNATE' if first is not None and second is None else 'FIXED' if second is not None and first is None else 'BEAUTY'
        bmesh.ops.triangulate(bm,faces=[f],quad_method=method,ngon_method=ngon_method)
    bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>3],quad_method='BEAUTY',ngon_method=ngon_method)


def finish_mesh(o,ngon_method='BEAUTY'):
    dg=bpy.context.evaluated_depsgraph_get()
    old=o.data;me=bpy.data.meshes.new_from_object(o.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
    o.modifiers.clear();o.data=me
    if old.users==0:bpy.data.meshes.remove(old)
    bm=bmesh.new();bm.from_mesh(me);before=mesh_stats(bm)
    interfaces=[f for f in bm.faces if f.edges and all(len(e.link_faces)>2 for e in f.edges)]
    if interfaces:bmesh.ops.delete(bm,geom=interfaces,context='FACES')
    separated=separate_close_contacts(bm)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-5)
    for _ in range(2):
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-5)
        triangulate_safe(bm,ngon_method)
        remove_opposed_duplicate_triangles(bm)
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-5)
    loose=[v for v in bm.verts if not v.link_faces]
    if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
    name=o.name.lower();kind=o.get('kind','')
    tube=(kind=='rope' or name.startswith(('lina_','rope_','zagiel_','zagle_','furled_sail_')) or o.get('cloth_state')=='furled')
    caps=0
    if tube:
        edges=[e for e in bm.edges if e.is_boundary]
        if edges:
            result=bmesh.ops.holes_fill(bm,edges=edges,sides=16)
            caps=len(result.get('faces',[]))
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    flipped=0
    for verts,faces in components(bm):
        if not all(e.is_manifold for f in faces for e in f.edges):continue
        centre=sum((v.co for v in verts),Vector())/len(verts)
        volume=0.
        for f in faces:
            pp=[v.co-centre for v in f.verts]
            for i in range(1,len(pp)-1):volume+=pp[0].dot(pp[i].cross(pp[i+1]))/6
        if volume<0:
            bmesh.ops.reverse_faces(bm,faces=list(faces));flipped+=1
    triangulate_safe(bm,ngon_method)
    remove_opposed_duplicate_triangles(bm)
    after=mesh_stats(bm);bm.to_mesh(me);bm.free();me.update()
    return {'name':o.name,'before':before,'after':after,'capped_tube_ends':caps,'outward_islands_reoriented':flipped,'separated_contact_vertices':separated,'internal_interface_faces_removed':len(interfaces)}


def finish_scene(objects):
    reports=[];instances={}
    for o in objects:
        if o.type!='MESH' or o.get('kind')=='glass' or 'szklo' in o.name or 'glass' in o.name:continue
        modifiers=tuple((m.type,tuple((k,str(getattr(m,k))) for k in
            ('width','segments','limit_method','angle_limit','use_clamp_overlap','weight','keep_sharp') if hasattr(m,k))) for m in o.modifiers)
        signature=(o.data.as_pointer(),modifiers,str(o.get('kind','')),str(o.get('cloth_state','')))
        if signature in instances:
            data,row=instances[signature];o.modifiers.clear();o.data=data
            reports.append({**row,'name':o.name,'cached_geometry_from':row['name']});continue
        raw=o.data.copy();had_modifiers=bool(o.modifiers)
        dg=bpy.context.evaluated_depsgraph_get()
        evaluated=bpy.data.meshes.new_from_object(o.evaluated_get(dg),preserve_all_data_layers=True,depsgraph=dg)
        o.modifiers.clear();best=None;attempts=[]
        for source,mode in [(evaluated,'BEAUTY'),(evaluated,'EAR_CLIP')]+([(raw,'BEAUTY'),(raw,'EAR_CLIP')] if had_modifiers else []):
            o.data=source.copy()
            row=finish_mesh(o,mode);after=row['after']
            score=10000*after['non_manifold_edges']+after['zero_area_faces']
            row['triangulation']=mode;row['authored_modifiers_applied']=source is evaluated
            attempts.append({'score':score,'triangulation':mode,'authored_modifiers_applied':source is evaluated})
            result=o.data
            if best is None or score<best[0]:
                if best and best[2].users==0:bpy.data.meshes.remove(best[2])
                best=(score,row,result)
            elif result.users==0:bpy.data.meshes.remove(result)
            if score==0:break
        o.data=best[2];best[1]['attempts']=attempts;reports.append(best[1]);instances[signature]=(o.data,best[1])
        for me in (raw,evaluated):
            if me.users==0:bpy.data.meshes.remove(me)
    return {'method':'evaluate valid authored modifiers, weld10um, remove collinear/opposed fragments, explicit tube-end caps, outward closed islands',
            'objects':reports}
