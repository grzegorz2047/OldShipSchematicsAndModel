"""Close only tiny source block/strop cut ends with stable centre fans.

API: repair(bpy.data.objects['rigging_static_blocks']). No original face or
vertex is deleted. The centre-fan avoids n-gon diagonal/collinearity ambiguity.
"""
import bmesh
from mathutils import Vector


def statistics(bm):
    return {'boundary_edges':sum(e.is_boundary for e in bm.edges),
            'non_manifold_edges':sum(not e.is_manifold for e in bm.edges),
            'zero_area_faces':sum(f.calc_area()<1e-12 for f in bm.faces)}


def repair(obj,max_diameter=.025):
    bm=bmesh.new();bm.from_mesh(obj.data)
    # This is the same ten-micrometre equivalence used by the export audit.
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-5)
    before=statistics(bm)
    unseen={e for e in bm.edges if e.is_boundary};groups=[]
    while unseen:
        edge=unseen.pop();edges={edge};stack=[edge];vertices=set(edge.verts)
        while stack:
            q=stack.pop()
            for v in q.verts:
                for e in v.link_edges:
                    if e in unseen:
                        unseen.remove(e);edges.add(e);stack.append(e);vertices.update(e.verts)
        points=[v.co.copy() for v in vertices]
        diameter=max((a-b).length for a in points for b in points)
        simple=all(sum(e in edges for e in v.link_edges)==2 for v in vertices)
        if not simple or len(edges)>16 or diameter>max_diameter:
            bm.free();raise RuntimeError('Opening is not a tiny simple strop cut: '+str((len(edges),diameter,simple)))
        groups.append((edges,vertices,diameter))
    caps=[];centres=[]
    uv_layers=list(bm.loops.layers.uv.values())
    for edges,vertices,diameter in groups:
        center=sum((v.co for v in vertices),Vector())/len(vertices)
        cv=bm.verts.new(center);centres.append(cv)
        # The boundary already has an outward winding. Reverse its directed
        # edge in the new face so the final solid keeps that winding.
        attached=[f for e in edges for f in e.link_faces]
        indices=[f.material_index for f in attached]
        material=max(set(indices),key=indices.count)
        tile=(2.,2.)
        if material<len(obj.data.materials):
            mat=obj.data.materials[material]
            if mat is not None:tile=tuple(mat.get('uv_tile_m',tile))
        edge=next(iter(edges));face=edge.link_faces[0]
        loop=next(l for l in face.loops if l.edge is edge)
        a,b=loop.vert,loop.link_loop_next.vert
        u=(b.co-a.co).normalized()
        # Newell normal from the edge-relative fan; its direction follows cap
        # winding rather than an arbitrary world axis.
        normal=Vector()
        for e in edges:
            f=e.link_faces[0];lo=next(l for l in f.loops if l.edge is e)
            normal+=(lo.link_loop_next.vert.co-center).cross(lo.vert.co-center)
        if normal.length<1e-10:
            bm.free();raise RuntimeError('Cut end has no stable cap plane')
        normal.normalize();u=(u-normal*u.dot(normal)).normalized();v=normal.cross(u).normalized()
        phases={}
        for layer in uv_layers:
            values=[l[layer].uv.copy() for f in attached for l in f.loops if l.vert in vertices]
            phases[layer]=sum(values,Vector((0.,0.)))/len(values) if values else Vector((0.,0.))
        new=[]
        for e in edges:
            f=e.link_faces[0];lo=next(l for l in f.loops if l.edge is e)
            va,vb=lo.vert,lo.link_loop_next.vert
            cap=bm.faces.new((vb,va,cv));cap.material_index=material;cap.smooth=False;new.append(cap)
            for layer in uv_layers:
                for l in cap.loops:
                    delta=l.vert.co-center
                    l[layer].uv=phases[layer]+Vector((delta.dot(u)/tile[0],delta.dot(v)/tile[1]))
        caps.append({'boundary_edges':len(edges),'diameter_m':diameter,'fan_triangles':len(new),
                     'minimum_triangle_area_m2':min(f.calc_area() for f in new),'source_material_slot':material})
    bm.normal_update()
    reversed_components=0;seen=set()
    for cv in centres:
        if cv in seen:continue
        vertices={cv};stack=[cv];seen.add(cv)
        while stack:
            q=stack.pop()
            for e in q.link_edges:
                w=e.other_vert(q)
                if w not in seen:seen.add(w);vertices.add(w);stack.append(w)
        faces={f for v in vertices for f in v.link_faces}
        if not all(e.is_manifold for f in faces for e in f.edges):continue
        origin=sum((v.co for v in vertices),Vector())/len(vertices)
        volume=0.
        for f in faces:
            pp=[v.co-origin for v in f.verts]
            for i in range(1,len(pp)-1):volume+=pp[0].dot(pp[i].cross(pp[i+1]))/6
        if volume<-1e-12:
            bmesh.ops.reverse_faces(bm,faces=list(faces));reversed_components+=1
        elif abs(volume)<=1e-12:
            bm.free();raise RuntimeError('Newly closed source component has negligible volume')
    after=statistics(bm)
    if any(after.values()):
        bm.free();raise RuntimeError('Tiny-end repair did not yield clean topology: '+str(after))
    bm.to_mesh(obj.data);bm.free();obj.data.update()
    return {'object':obj.name,'before':before,'after':after,'caps':caps,
            'outward_components_reversed':reversed_components,
            'original_faces_removed':0,'original_vertices_removed':0,
            'method':'tiny hidden strop end loops closed by explicitly oriented metric-UV centre fans'}
