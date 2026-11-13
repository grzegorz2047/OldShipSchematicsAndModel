"""Remove redundant guide-mesh subdivisions within a measured 5 mm envelope.

Keep material and UV seams, moving origins and the original planking shape.
This is a geometry budget operation; independent export/route audits still run.
"""
import bmesh
import bpy
from mathutils.bvhtree import BVHTree


def samples(mesh):
    mesh.calc_loop_triangles()
    result=[v.co.copy() for v in mesh.vertices]
    result.extend((mesh.vertices[t.vertices[0]].co+mesh.vertices[t.vertices[1]].co+
                   mesh.vertices[t.vertices[2]].co)/3 for t in mesh.loop_triangles)
    return result


def topology(bm):
    return (sum(not e.is_manifold for e in bm.edges),
            sum(f.calc_area()<1e-11 for f in bm.faces))


def simplify(objects,tolerance=.005):
    deps=bpy.context.evaluated_depsgraph_get()
    changes=[];before_total=after_total=0
    for obj in objects:
        if obj.type!='MESH':continue
        original=bpy.data.meshes.new_from_object(obj.evaluated_get(deps))
        original.calc_loop_triangles();before=len(original.loop_triangles)
        before_total+=before;after_total+=before
        kind=obj.get('kind','')
        if kind in ('sail','glass','ladder','surface') or 'szklo' in obj.name:
            bpy.data.meshes.remove(original);continue
        bm=bmesh.new();bm.from_mesh(original)
        original_topology=topology(bm);original_tree=BVHTree.FromBMesh(bm)
        bm.free()
        old_samples=samples(original)
        angles=[.003] if kind=='hull' else [.001,.003] if kind=='rope' else [.003,.006,.01]
        chosen=None;chosen_count=before;chosen_error=0;chosen_angle=0
        for angle in angles:
            bm=bmesh.new();bm.from_mesh(original)
            bmesh.ops.dissolve_limit(bm,angle_limit=angle,use_dissolve_boundaries=False,
                verts=list(bm.verts),edges=list(bm.edges),delimit={'MATERIAL','UV'})
            if topology(bm)!=original_topology:
                bm.free();continue
            candidate=bpy.data.meshes.new('_budget_candidate')
            bm.to_mesh(candidate);bm.free();candidate.calc_loop_triangles()
            count=len(candidate.loop_triangles)
            if count>=chosen_count:
                bpy.data.meshes.remove(candidate);continue
            tree=BVHTree.FromPolygons([v.co for v in candidate.vertices],
                [tuple(t.vertices) for t in candidate.loop_triangles],all_triangles=True)
            maximum=max((tree.find_nearest(p)[3] for p in old_samples),default=0)
            if maximum<=tolerance:
                maximum=max(maximum,max((original_tree.find_nearest(p)[3]
                    for p in samples(candidate)),default=0))
            if maximum>tolerance:
                bpy.data.meshes.remove(candidate);continue
            if chosen is not None:bpy.data.meshes.remove(chosen)
            chosen=candidate;chosen_count=count;chosen_error=maximum;chosen_angle=angle
        if chosen is not None:
            old_mesh=obj.data
            obj.data=chosen;obj.modifiers.clear()
            if old_mesh.users==0:bpy.data.meshes.remove(old_mesh)
            after_total+=chosen_count-before
            changes.append({'object':obj.name,'before_triangles':before,'after_triangles':chosen_count,
                'angle_limit_rad':chosen_angle,'maximum_sampled_surface_deviation_m':chosen_error,
                'topology_preserved':True})
        bpy.data.meshes.remove(original)
    result={'before_triangles':before_total,'after_triangles':after_total,
        'surface_tolerance_m':tolerance,'sampling':'bidirectional vertices and triangle centroids',
        'preserved_boundaries':['material','UV'],'changes':changes}
    print('BRIG_GEOMETRY_BUDGET',before_total,after_total,flush=True)
    if after_total>280000:
        raise RuntimeError('Brig remains above guide triangle budget: '+str(after_total))
    return result
