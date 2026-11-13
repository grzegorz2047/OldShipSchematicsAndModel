"""Remove redundant guide-mesh subdivisions within a measured 5 mm envelope.

Keep material and UV seams, moving origins and the original planking shape.
This is a geometry budget operation; independent export/route audits still run.
"""
import bmesh
import bpy
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from v2_mesh_finish import triangulate_safe


def samples(mesh):
    mesh.calc_loop_triangles()
    result=[v.co.copy() for v in mesh.vertices]
    result.extend((mesh.vertices[t.vertices[0]].co+mesh.vertices[t.vertices[1]].co+
                   mesh.vertices[t.vertices[2]].co)/3 for t in mesh.loop_triangles)
    return result


def topology(bm):
    return (sum(not e.is_manifold for e in bm.edges),
            sum(f.calc_area()<1e-11 for f in bm.faces))


def simplify(objects,tolerance=.005,triangle_budget=280000):
    deps=bpy.context.evaluated_depsgraph_get()
    changes=[];before_total=after_total=0;instances={}
    for obj in objects:
        if obj.type!='MESH':continue
        # Preserve source instancing (notably the gun carriages). The guide
        # budget counts indexed geometry once, and GLB keeps these shared meshes.
        settings=('width','segments','limit_method','angle_limit','harden_normals',
                  'weight','keep_sharp','mode','thresh','show_viewport','show_render')
        modifiers=tuple((m.type,tuple((k,getattr(m,k)) for k in settings if hasattr(m,k))) for m in obj.modifiers)
        key=(obj.data.as_pointer(),modifiers)
        if any(m.type not in ('BEVEL','WEIGHTED_NORMAL') for m in obj.modifiers):key+=(obj.as_pointer(),)
        if key in instances:
            shared=instances[key]
            if shared is not None:
                old_mesh=obj.data;obj.data=shared;obj.modifiers.clear()
                if old_mesh.users==0:bpy.data.meshes.remove(old_mesh)
            continue
        original=bpy.data.meshes.new_from_object(obj.evaluated_get(deps))
        original.calc_loop_triangles();before=len(original.loop_triangles)
        before_total+=before;after_total+=before
        kind=obj.get('kind','')
        if kind in ('sail','glass','ladder','surface') or 'szklo' in obj.name:
            instances[key]=None;bpy.data.meshes.remove(original);continue
        bm=bmesh.new();bm.from_mesh(original)
        original_topology=topology(bm);original_tree=BVHTree.FromBMesh(bm)
        bm.free()
        old_samples=samples(original)
        neighbors=[set() for v in original.vertices]
        kd=KDTree(len(original.vertices))
        for v in original.vertices:kd.insert(v.co,v.index)
        kd.balance()
        for e in original.edges:
            a,b=e.vertices;neighbors[a].add(b);neighbors[b].add(a)
        angles=[.003,.01]
        chosen=None;chosen_count=before;chosen_error=0;chosen_angle=0
        for angle in angles:
            protected=set();candidate=None
            for attempt in range(4):
                bm=bmesh.new();bm.from_mesh(original);bm.verts.ensure_lookup_table();bm.verts.index_update()
                vv=[v for v in bm.verts if v.index not in protected]
                ee=[e for e in bm.edges if all(v.index not in protected for v in e.verts)]
                bmesh.ops.dissolve_limit(bm,angle_limit=angle,use_dissolve_boundaries=False,
                    verts=vv,edges=ee,delimit={'MATERIAL','UV'})
                triangulate_safe(bm,'BEAUTY')
                if topology(bm)!=original_topology:
                    bm.free();break
                candidate=bpy.data.meshes.new('_budget_candidate')
                bm.to_mesh(candidate);bm.free();candidate.calc_loop_triangles()
                for material in original.materials:candidate.materials.append(material)
                count=len(candidate.loop_triangles)
                if count>=chosen_count:
                    bpy.data.meshes.remove(candidate);candidate=None;break
                tree=BVHTree.FromPolygons([v.co for v in candidate.vertices],
                    [tuple(t.vertices) for t in candidate.loop_triangles],all_triangles=True)
                deviations=[(tree.find_nearest(p)[3],p) for p in old_samples]
                deviations.extend((original_tree.find_nearest(p)[3],p) for p in samples(candidate))
                maximum=max((d for d,p in deviations),default=0)
                if maximum<=tolerance:break
                # Keep the original curved neighborhood wherever a coarse
                # dissolution would leave the measured surface envelope.
                for d,p in deviations:
                    if d>tolerance:
                        protected.update(index for _,index,_ in kd.find_n(p,4))
                for _ in range(2):
                    protected.update(j for i in list(protected) for j in neighbors[i])
                bpy.data.meshes.remove(candidate);candidate=None
            if candidate is None:continue
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
                'topology_preserved':True,'material_slots_preserved':True})
        instances[key]=chosen
        bpy.data.meshes.remove(original)
    result={'before_triangles':before_total,'after_triangles':after_total,
        'count_scope':'distinct source mesh/modifier signatures; delivered GLB indexed counts are independently audited',
        'surface_tolerance_m':tolerance,'sampling':'bidirectional vertices and triangle centroids',
        'preserved_boundaries':['material','UV'],'changes':changes}
    print('GUIDE_GEOMETRY_BUDGET',before_total,after_total,flush=True)
    if after_total>triangle_budget:
        raise RuntimeError('Vessel remains above guide triangle budget: '+str(after_total))
    return result
