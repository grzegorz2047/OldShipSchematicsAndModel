"""Normalize only oversampled working-rig lead-block charts to their metre tile.

API: ledger = fix(objects, design). Positions, polygons, materials, UV direction
and anisotropy are unchanged; a continuous outlier chart is scaled once about its old centroid.
"""
import math
from collections import defaultdict
from mathutils import Vector


def material_sampling(material):
    tile=material.get('uv_tile_m')
    if tile is None or len(tile)!=2 or min(tile)<=0:
        raise RuntimeError('Lead-block material lacks a physical UV tile: '+material.name)
    images=[n.image for n in material.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
    colors=[im for im in images if any(s in im.name.lower() for s in ('color','colour','albedo','kolor','base'))]
    if not colors:colors=[im for im in images if im.colorspace_settings.name=='sRGB']
    if not colors:raise RuntimeError('Lead-block colour image missing: '+material.name)
    image=colors[0];pixels=image.size[0]*image.size[1]
    return float(pixels),math.sqrt(pixels/(float(tile[0])*float(tile[1])))


def fix(objects,design):
    report=[];seen=set();total=0
    for obj in sorted(objects,key=lambda o:o.name):
        if obj.type!='MESH' or not obj.name.startswith(('brace_turning_block_','deck_lead_block_')):continue
        mesh=obj.data
        if mesh.as_pointer() in seen:continue
        seen.add(mesh.as_pointer())
        if not mesh.uv_layers:raise RuntimeError('Lead block has no UV map: '+obj.name)
        uv=mesh.uv_layers.active.data;mesh.calc_loop_triangles()
        sampling={i:material_sampling(mat) for i,mat in enumerate(mesh.materials)
                  if mat and ('wood_ciemne' in mat.name or mat.get('source_material')=='wood_dark')}
        areas=defaultdict(lambda:[0.,0.])
        world=[obj.matrix_world@v.co for v in mesh.vertices]
        for tri in mesh.loop_triangles:
            if tri.material_index not in sampling:continue
            a,b,c=(world[i] for i in tri.vertices)
            physical=(b-a).cross(c-a).length/2
            ua,ub,uc=(uv[i].uv.copy() for i in tri.loops)
            du,dv=ub-ua,uc-ua
            chart=abs(du.x*dv.y-du.y*dv.x)/2
            areas[tri.polygon_index][0]+=physical;areas[tri.polygon_index][1]+=chart
        bad={}
        for index,(physical,chart) in sorted(areas.items()):
            poly=mesh.polygons[index];pixels,target=sampling[poly.material_index]
            if physical<1e-12 or chart<1e-14:continue
            density=math.sqrt(chart*pixels/physical)
            if not target/1.15<=density<=target*1.15:bad[index]=(density,target)
        # Existing continuous outlier patches receive ONE transform. Repaired
        # metric patches and UV seams remain separate, avoiding new chart seams.
        adjacency={i:set() for i in bad};edge_faces=defaultdict(list)
        for index in bad:
            poly=mesh.polygons[index];loops=list(poly.loop_indices)
            for k,li in enumerate(loops):
                lj=loops[(k+1)%len(loops)];a=mesh.loops[li].vertex_index;b=mesh.loops[lj].vertex_index
                edge_faces[tuple(sorted((a,b)))].append((index,{a:uv[li].uv.copy(),b:uv[lj].uv.copy()}))
        for entries in edge_faces.values():
            for i,(a,ua) in enumerate(entries):
                for b,ub in entries[i+1:]:
                    if mesh.polygons[a].material_index!=mesh.polygons[b].material_index:continue
                    if all((ua[k]-ub[k]).length<=1e-6 for k in ua):adjacency[a].add(b);adjacency[b].add(a)
        changed=[];remaining=set(bad)
        while remaining:
            first=min(remaining);remaining.remove(first);group={first};stack=[first]
            while stack:
                i=stack.pop()
                for j in sorted(adjacency[i]):
                    if j in remaining:remaining.remove(j);group.add(j);stack.append(j)
            group=sorted(group);material_index=mesh.polygons[group[0]].material_index
            pixels,target=sampling[material_index]
            physical=sum(areas[i][0] for i in group);chart=sum(areas[i][1] for i in group)
            density=math.sqrt(chart*pixels/physical);factor=target/density
            center=Vector((0.,0.))
            for i in group:
                loops=list(mesh.polygons[i].loop_indices)
                center+=sum((uv[li].uv for li in loops),Vector((0.,0.)))/len(loops)*areas[i][0]
            center/=physical
            for i in group:
                for li in mesh.polygons[i].loop_indices:uv[li].uv=center+(uv[li].uv-center)*factor
            changed.append({'polygons':group,'polygon_count':len(group),
                'density_before_px_m':density,'density_before_range_px_m':[min(bad[i][0] for i in group),max(bad[i][0] for i in group)],
                'density_target_px_m':target,'positive_uniform_uv_scale':factor,
                'existing_uv_continuity_preserved':True})
        if changed:
            mesh.update();total+=sum(row['polygon_count'] for row in changed)
            obj['uv_density_finish']='lead-block outlier charts normalized to the existing physical material tile; grain direction retained'
            report.append({'object':obj.name,'continuous_charts_scaled':len(changed),'polygons_scaled':sum(row['polygon_count'] for row in changed),'charts':changed})
    ledger={'method':'positive isotropic chart scaling about existing UV centroids to actual image/uv_tile_m density',
            'scope':'working-rig brace turning blocks and deck lead blocks only',
            'polygons_scaled':total,'continuous_charts_scaled':sum(len(row['charts']) for row in report),'objects':report,'positions_changed':False,'topology_changed':False,
            'materials_changed':False,'grain_direction_changed':False,'anisotropy_changed':False}
    design['uv_density_finish']=ledger
    return ledger
