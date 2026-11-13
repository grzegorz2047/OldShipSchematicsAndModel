"""Independent checks of the delivered, reimported guide-based vessel files.

Blender 5.2: --python v2_audit.py -- spec.json --asset-dir build/final/brig
The matrix states PASS/FAIL/NA with evidence. NA never means a test passed.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
import fnmatch
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import closest_point_on_tri, intersect_ray_tri

sys.path.insert(0,str(Path(__file__).resolve().parent))
from v2_integrity import digest,inspect_glb,resolve_source

STEP=0.10
GEOMETRY_TOLERANCE=0.015
FOOT_LIFT=0.08
STEP_ALLOWANCE=0.22
EDGE_CONTACT_TOLERANCE=0.025
MESH_WELD_TOLERANCE=1e-5


def ship_to_blender(q):
    return Vector((q[0],-q[2],q[1]))


def plain(value):
    if isinstance(value,dict):
        return {str(k):plain(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):
        return [plain(v) for v in value]
    if isinstance(value,np.ndarray):
        return value.tolist()
    if isinstance(value,np.generic):
        return value.item()
    if isinstance(value,Vector):
        return list(value)
    return value


def segment_d2(p1,q1,p2,q2):
    d1=q1-p1;d2=q2-p2;r=p1-p2
    a=d1.dot(d1);e=d2.dot(d2);f=d2.dot(r)
    if a<1e-12:
        s=0;t=max(0,min(1,f/e)) if e>1e-12 else 0
    else:
        c=d1.dot(r)
        if e<1e-12:s=max(0,min(1,-c/a));t=0
        else:
            b=d1.dot(d2);den=a*e-b*b
            s=max(0,min(1,(b*f-c*e)/den)) if abs(den)>1e-12 else 0
            t=(b*s+f)/e
            if t<0:t=0;s=max(0,min(1,-c/a))
            elif t>1:t=1;s=max(0,min(1,(b-c)/a))
    return ((p1+d1*s)-(p2+d2*t)).length_squared


def capsule_triangle_d2(a,b,tri):
    v0,v1,v2=tri
    hit=intersect_ray_tri(v0,v1,v2,b-a,a,True)
    if hit is not None and (hit-a).dot(b-a)>=0 and (hit-a).length_squared<=(b-a).length_squared+1e-10:
        return 0.0
    result=min((closest_point_on_tri(a,*tri)-a).length_squared,
               (closest_point_on_tri(b,*tri)-b).length_squared)
    for c,e in ((v0,v1),(v1,v2),(v2,v0)):
        result=min(result,segment_d2(a,b,c,e))
    return result


def triangle_intersection_points(a,b):
    points=[]
    for first,second in ((a,b),(b,a)):
        for i in range(3):
            p,q=first[i],first[(i+1)%3]
            d=q-p
            hit=intersect_ray_tri(*second,d,p,True)
            if hit is not None and -1e-8 <= (hit-p).dot(d) <= d.length_squared+1e-8:
                points.append(hit)
        for p in first:
            if (closest_point_on_tri(p,*second)-p).length_squared<1e-12:
                points.append(p)
    return points


def distance_to_edges(q,edges):
    if not edges:return math.inf
    result=math.inf
    for a,b in edges:
        ab=b-a
        t=max(0,min(1,(q-a).dot(ab)/max(ab.length_squared,1e-20)))
        result=min(result,(q-(a+ab*t)).length)
    return result


def inferred_kind(obj):
    kind=str(obj.get('kind',obj.get('role',''))).lower()
    known={'hull','sail','rope','spar','fitting','surface','ladder','collision','glass'}
    if kind in known:return kind
    name=obj.name.lower()
    if 'ladder' in name or 'drab' in name or obj.get('climbable'):
        return 'ladder'
    if any(n in name for n in ('sail','canvas','zagiel')) and not any(n in name for n in ('furled','zwin','bolt','rope')):
        return 'sail'
    if any(n in name for n in ('rope','rigging','shroud','stay','brace','lina_','want','szot','szta','bolt_')):
        return 'rope'
    if any(n in name for n in ('mast','yard','boom','gaff','spar','drzewca','reja','maszt','buksz')):
        return 'spar'
    if any(n in name for n in ('hull','kadlub','planking_shell','carved_log')):
        return 'hull'
    return 'fitting'


def weld_topology(obj):
    bm=bmesh.new();bm.from_mesh(obj.data)
    before=len(bm.verts)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=MESH_WELD_TOLERANCE)
    bm.verts.ensure_lookup_table();bm.edges.ensure_lookup_table();bm.faces.ensure_lookup_table()
    bm.verts.index_update();bm.edges.index_update();bm.faces.index_update()
    loose_v=sum(not v.link_faces for v in bm.verts)
    loose_e=sum(not e.link_faces for e in bm.edges)
    nonmanifold=[e for e in bm.edges if not e.is_manifold]
    zero=sum(f.calc_area()<1e-12 for f in bm.faces)
    seen=set();duplicates=0
    for f in bm.faces:
        key=tuple(sorted(v.index for v in f.verts))
        duplicates+=key in seen;seen.add(key)
    visited=set();volumes=[];components=0;islands=[]
    for v in bm.verts:
        if v.index in visited or not v.link_faces:continue
        queue=[v];component_v=[];component_f=set()
        while queue:
            x=queue.pop()
            if x.index in visited:continue
            visited.add(x.index);component_v.append(x);component_f.update(x.link_faces)
            queue.extend(e.other_vert(x) for e in x.link_edges if e.other_vert(x).index not in visited)
        components+=1
        closed=all(e.is_manifold for f in component_f for e in f.edges)
        if closed:
            points=[obj.matrix_world@v.co for v in component_v]
            mapping={v.index:i for i,v in enumerate(component_v)}
            tris=[]
            for f in component_f:
                ids=[mapping[v.index] for v in f.verts]
                tris.extend((ids[0],ids[i],ids[i+1]) for i in range(1,len(ids)-1))
            islands.append({'vertices':points,'triangle_indices':tris})
        if closed:
            center=np.mean(np.array([tuple(x.co) for x in component_v],dtype=np.float64),axis=0)
            volume=0.0
            for f in component_f:
                pts=[np.array(v.co,dtype=np.float64)-center for v in f.verts]
                for i in range(1,len(pts)-1):
                    volume+=float(np.dot(pts[0],np.cross(pts[i],pts[i+1])))/6
            volumes.append(volume)
    boundaries=[(obj.matrix_world@e.verts[0].co,obj.matrix_world@e.verts[1].co)
                for e in bm.edges if e.is_boundary]
    record={'vertices_after_weld':len(bm.verts),'export_seam_vertices_welded':before-len(bm.verts),
            'edges':len(bm.edges),'faces':len(bm.faces),'components':components,
            'non_manifold_edges':len(nonmanifold),'boundary_edges':sum(e.is_boundary for e in bm.edges),
            'zero_area_faces':zero,'duplicate_faces':duplicates,'loose_vertices':loose_v,'loose_edges':loose_e,
            'closed_component_signed_volumes_m3':volumes,
            'reversed_closed_components':sum(v<-1e-10 for v in volumes),
            'nearly_zero_volume_closed_components':sum(abs(v)<=1e-12 for v in volumes)}
    unique_world=[obj.matrix_world@v.co for v in bm.verts]
    bm.free()
    return record,boundaries,unique_world,islands


def object_records(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(path))
    bpy.context.view_layer.update()
    records=[]
    for obj in list(bpy.context.scene.objects):
        if obj.type!='MESH':continue
        obj.data.calc_loop_triangles()
        vertices=[obj.matrix_world@v.co for v in obj.data.vertices]
        triangles=[tuple(vertices[i] for i in t.vertices) for t in obj.data.loop_triangles]
        if not triangles:continue
        topology,boundaries,unique,islands=weld_topology(obj)
        mn=Vector(tuple(min(p[k] for p in vertices) for k in range(3)))
        mx=Vector(tuple(max(p[k] for p in vertices) for k in range(3)))
        ids=[tuple(t.vertices) for t in obj.data.loop_triangles]
        tree=BVHTree.FromPolygons(vertices,ids,all_triangles=True,epsilon=1e-7)
        rec={'name':obj.name,'kind':inferred_kind(obj),'extras':dict(obj.items()),
             'triangles':triangles,'vertices':unique,'min':mn,'max':mx,'tree':tree,
             'topology':topology,'boundaries':boundaries,'materials':[],
             'islands':islands,
             'transform':{'scale':list(obj.scale),'rotation':list(obj.rotation_euler)}}
        # UV metrics must be measured before the next import clears the scene.
        rec['uv']=uv_metrics(obj)
        records.append(rec)
    return records


def weighted_percentile(values,weights,percentile):
    if not values:return None
    v=np.asarray(values,float);w=np.asarray(weights,float)
    order=np.argsort(v);v=v[order];w=w[order]
    total=float(w.sum())
    if total<=0:return None
    index=min(len(v)-1,int(np.searchsorted(np.cumsum(w),percentile*total)))
    return float(v[index])


def uv_metrics(obj):
    me=obj.data
    if not me.uv_layers:return {'missing_uv':True,'materials':{}}
    layer=me.uv_layers.active.data
    stats=defaultdict(lambda:{'density':[],'anisotropy':[],'area':[],'degenerate_uv_area_m2':0.0,
                              'grain_area':0.0,'grain_aligned_area':0.0})
    world=np.array([tuple(obj.matrix_world@v.co) for v in me.vertices],dtype=np.float64)
    covariance=np.cov(world.T) if len(world)>2 else np.eye(3)
    eigenvalues,eigenvectors=np.linalg.eigh(covariance)
    wood_axis=eigenvectors[:,-1]
    is_elongated=eigenvalues[-1]>=2.5**2*max(eigenvalues[-2],1e-12)
    grain_path=[]
    authored_path=obj.get('grain_path_json')
    if authored_path:
        try:
            p=json.loads(authored_path) if isinstance(authored_path,str) else authored_path
            axes=p.get('axes','object_local') if isinstance(p,dict) else 'object_local'
            pts=p.get('points',[]) if isinstance(p,dict) else p
            if axes.lower() in ('gltf','gltf_world'):
                grain_path=[np.array(ship_to_blender(q),dtype=float) for q in pts]
            elif axes.lower() in ('blender','blender_world','world'):
                grain_path=[np.array(q,dtype=float) for q in pts]
            else:
                grain_path=[np.array(obj.matrix_world@Vector(q),dtype=float) for q in pts]
        except (TypeError,ValueError,KeyError):
            grain_path=[]
    def grain_tangent(center):
        nearest=None
        for a,b in zip(grain_path,grain_path[1:]):
            ab=b-a;length=float(np.linalg.norm(ab))
            if length<1e-10:continue
            t=max(0,min(1,float(np.dot(center-a,ab))/(length*length)))
            distance=float(np.linalg.norm(center-(a+ab*t)))
            if nearest is None or distance<nearest[0]:nearest=(distance,ab/length)
        return nearest[1] if nearest else wood_axis
    for tri in me.loop_triangles:
        mat=me.materials[tri.material_index] if tri.material_index<len(me.materials) else None
        if mat is None:continue
        images=[n.image for n in mat.node_tree.nodes if n.type=='TEX_IMAGE' and n.image] if mat.use_nodes else []
        color=[im for im in images if any(s in im.name.lower() for s in ('color','colour','kolor','albedo','base'))]
        if not color:color=[im for im in images if im.colorspace_settings.name=='sRGB']
        if not color:continue
        im=color[0];w,h=im.size
        pts=world[list(tri.vertices)]
        e1,e2=pts[1]-pts[0],pts[2]-pts[0]
        cross=np.cross(e1,e2);double_area=float(np.linalg.norm(cross));area=double_area/2
        if area<1e-12:continue
        uv=np.array([tuple(layer[i].uv) for i in tri.loops],dtype=np.float64)
        uv_edges=np.stack((uv[1]-uv[0],uv[2]-uv[0]),axis=1)
        uv_area=abs(float(np.linalg.det(uv_edges)))/2
        st=stats[mat.name]
        if uv_area<1e-14:
            st['degenerate_uv_area_m2']+=area
            st['density'].append(0.0);st['anisotropy'].append(1e12);st['area'].append(area)
            continue
        density=math.sqrt(uv_area*w*h/area)
        a1=e1/max(np.linalg.norm(e1),1e-20)
        normal=cross/double_area;a2=np.cross(normal,a1)
        domain=np.array([[np.dot(e1,a1),np.dot(e2,a1)],[np.dot(e1,a2),np.dot(e2,a2)]])
        try:
            physical_jacobian=uv_edges@np.linalg.inv(domain)
            pixel_jacobian=np.diag((w,h))@physical_jacobian
            singular=np.linalg.svd(pixel_jacobian,compute_uv=False)
            anisotropy=float(singular[0]/max(singular[1],1e-12))
            local_grain=grain_tangent(pts.mean(axis=0))
            if (is_elongated or len(grain_path)>1) and abs(np.dot(normal,local_grain))<0.5 and any(s in mat.name.lower() for s in ('wood','oak','pine','drew','deck','poklad','plank')):
                # Surface direction for increasing U while V is constant.
                u_domain=np.linalg.solve(physical_jacobian,np.array([1.0,0.0]))
                u_world=a1*u_domain[0]+a2*u_domain[1]
                cosine=abs(float(np.dot(u_world,local_grain)))/max(float(np.linalg.norm(u_world)),1e-12)
                st['grain_area']+=area
                if cosine>=math.cos(math.radians(25)):st['grain_aligned_area']+=area
        except np.linalg.LinAlgError:
            anisotropy=1e12
        st['density'].append(density);st['anisotropy'].append(anisotropy);st['area'].append(area)
    return {'missing_uv':False,'materials':dict(stats)}


class TriangleScene:
    def __init__(self,records):
        self.records=records
        self.triangles=[];self.names=[];self.normals=[];self.mins=[];self.maxs=[];self.extras=[]
        vertices=[];faces=[];self.cells=defaultdict(list);self.large=[]
        for r in records:
            for tri in r['triangles']:
                index=len(self.triangles)
                self.triangles.append(tri);self.names.append(r['name']);self.extras.append(r['extras'])
                self.normals.append((tri[1]-tri[0]).cross(tri[2]-tri[0]).normalized())
                mn=Vector(tuple(min(p[k] for p in tri) for k in range(3)))
                mx=Vector(tuple(max(p[k] for p in tri) for k in range(3)))
                self.mins.append(mn);self.maxs.append(mx)
                lo=[math.floor(v) for v in mn];hi=[math.floor(v) for v in mx]
                count=math.prod(b-a+1 for a,b in zip(lo,hi))
                if count>256:self.large.append(index)
                else:
                    for x in range(lo[0],hi[0]+1):
                        for y in range(lo[1],hi[1]+1):
                            for z in range(lo[2],hi[2]+1):self.cells[(x,y,z)].append(index)
                i=len(vertices);vertices.extend(tri);faces.append((i,i+1,i+2))
        self.tree=BVHTree.FromPolygons(vertices,faces,all_triangles=True) if faces else None

    def candidates(self,lo,hi):
        result=set(self.large)
        for x in range(math.floor(lo.x),math.floor(hi.x)+1):
            for y in range(math.floor(lo.y),math.floor(hi.y)+1):
                for z in range(math.floor(lo.z),math.floor(hi.z)+1):result.update(self.cells.get((x,y,z),()))
        return result

    def support(self,foot):
        if self.tree is None:return None
        # A capsule foot bridges the millimetre seams between real deck boards.
        # A centre-only ray can hit a tilted board side or miss an 8mm seam even
        # when the standing foot has sound support on both adjacent planks.
        candidates=[]
        for dx,dy in ((0,0),(-.07,0),(.07,0),(0,-.07),(0,.07),(-.14,0),(.14,0),(0,-.14),(0,.14)):
            hit,normal,index,distance=self.tree.ray_cast(foot+Vector((dx,dy,STEP_ALLOWANCE+0.01)),Vector((0,0,-1)),0.54)
            if hit is None or normal.z<math.cos(math.radians(35)):continue
            projected=hit.z-(normal.x*(foot.x-hit.x)+normal.y*(foot.y-hit.y))/normal.z
            if abs(projected-foot.z)>.30:continue
            candidates.append((abs(projected-foot.z),Vector((foot.x,foot.y,projected)),normal,index,distance))
        if not candidates:return None
        _,hit,normal,index,distance=min(candidates,key=lambda c:c[0])
        return hit,normal,index,distance


def sample_route(route):
    pts=[ship_to_blender(q) for q in route.get('points',[])]
    samples=[];length=0.0
    for a,b in zip(pts,pts[1:]):
        length+=(b-a).length
        n=max(1,math.ceil((b-a).length/STEP))
        samples.extend(a.lerp(b,i/n) for i in range(n))
    if pts:samples.append(pts[-1])
    return samples,length


def audit_routes(records,nav,geometry_tolerance=GEOMETRY_TOLERANCE,check_connectivity=True):
    world=TriangleScene(records)
    player=nav.get('player',{})
    radius=float(player.get('radius',0));height=float(player.get('height',0))
    max_slope=float(player.get('max_slope_deg',35))
    if radius<0.35 or height<1.75 or height<2*radius:
        return {'passed':False,'error':'Player dimensions missing or reduced below declared task dimensions','routes':[]}
    r=radius-geometry_tolerance;slope=math.cos(math.radians(max_slope));results=[];all_samples=[]
    ladders=[record for record in records if record.get('kind')=='ladder' or record.get('extras',{}).get('climbable')]
    for route in nav.get('routes',[]):
        samples,length=sample_route(route);errors=[]
        mode=route.get('mode','walk')
        if len(samples)<2 or length<0.30:
            errors.append({'problem':'empty or token-sized path','length_m':length})
        if mode not in ('walk','climb'):
            errors.append({'problem':'unknown route mode','mode':mode})
        for pi,original_foot in enumerate(samples):
            foot=original_foot.copy()
            support_normal=None
            requires_floor=mode=='walk' or pi in (0,len(samples)-1)
            if mode=='climb' and 0<pi<len(samples)-1:
                hand=foot+Vector((0,0,height*0.62))
                distances=[record['tree'].find_nearest(hand)[3] for record in ladders]
                distances=[d for d in distances if d is not None]
                if not distances or min(distances)>0.70:
                    errors.append({'sample':pi,'problem':'climb has no physical ladder within hand reach','at':list(foot)})
                    continue
            if requires_floor:
                support=world.support(foot)
                if support is None or support[0] is None:
                    errors.append({'sample':pi,'problem':'no floor within 0.30m below /0.23m above foot','at':list(foot)});continue
                hit,normal,_,_=support
                support_normal=normal
                if normal.z<slope:
                    errors.append({'sample':pi,'problem':'support faces downward or exceeds max slope','normal':list(normal),'at':list(foot)});continue
                if mode=='walk':foot.z=hit.z
                elif abs(hit.z-foot.z)>0.15:
                    errors.append({'sample':pi,'problem':'climb endpoint not on landing','gap_m':hit.z-foot.z});continue
            a=foot+Vector((0,0,r+FOOT_LIFT));b=foot+Vector((0,0,height-r))
            lo=Vector((foot.x-r,foot.y-r,foot.z+0.06))
            hi=Vector((foot.x+r,foot.y+r,foot.z+height))
            for index in world.candidates(lo,hi):
                mn,mx=world.mins[index],world.maxs[index]
                if any(mx[k]<lo[k] or mn[k]>hi[k] for k in range(3)):continue
                tri=world.triangles[index];normal=world.normals[index]
                # This controller can step 22cm; the allowance does not exempt
                # a ceiling, tall railing, or the rest of a floor object.
                if mode=='walk' and mx.z<=foot.z+STEP_ALLOWANCE:continue
                if mode=='walk' and support_normal is not None:
                    # Step height is relative to the local supporting deck,
                    # including its heel. A world-height bound falsely treats
                    # the high side of flush caulking as a tall wall.
                    def above_support(q):
                        plane=foot.z-(support_normal.x*(q.x-foot.x)+support_normal.y*(q.y-foot.y))/support_normal.z
                        return q.z-plane
                    if max(above_support(q) for q in tri)<=STEP_ALLOWANCE:continue
                if requires_floor and normal.z>slope:
                    plane_z=tri[0].z-(normal.x*(foot.x-tri[0].x)+normal.y*(foot.y-tri[0].y))/normal.z
                    if abs(plane_z-foot.z)<0.14:continue
                if capsule_triangle_d2(a,b,tri)<r*r-1e-8:
                    errors.append({'sample':pi,'problem':'capsule blocked','by':world.names[index],'at':list(foot)});break
        results.append({'name':route.get('name','unnamed'),'mode':mode,'length_m':length,
                        'samples':len(samples),'passed':not errors,'failure_count':len(errors),'failures':errors[:12]})
        all_samples.append(samples)
    # All authored destination routes must join the same physically checked graph.
    graph=[set() for _ in results]
    for i in range(len(results)):
        for j in range(i):
            connected=any((a-b).length<=0.30 for a in all_samples[i] for b in all_samples[j])
            if connected:graph[i].add(j);graph[j].add(i)
    reached=set()
    if results:
        queue=[0]
        while queue:
            i=queue.pop()
            if i in reached:continue
            reached.add(i);queue.extend(graph[i]-reached)
    disconnected=[results[i]['name'] for i in range(len(results)) if i not in reached]
    return {'passed':bool(results) and all(r['passed'] for r in results) and (not check_connectivity or not disconnected),
            'player':player,'sample_step_m':STEP,'geometry_tolerance_m':geometry_tolerance,
            'rounded_foot_lift_m':FOOT_LIFT,'controller_step_allowance_m':STEP_ALLOWANCE,
            'scope':'sampled authored corridors; climb mode requires a climb controller and real endpoint landings',
            'routes':results,'disconnected_routes':disconnected}


def intended_joint(a,b,design):
    for rule in design.get('intended_joints',[]):
        if not isinstance(rule,dict) or not rule.get('reason'):continue
        x,y=rule.get('a',''),rule.get('b','')
        if x in ('','*') and y in ('','*'):continue
        if (fnmatch.fnmatchcase(a,x) and fnmatch.fnmatchcase(b,y)) or (fnmatch.fnmatchcase(b,x) and fnmatch.fnmatchcase(a,y)):
            return rule['reason']
    return None


def audit_rig(records,design):
    sails=[r for r in records if r['kind']=='sail']
    obstacles=[r for r in records if r['kind'] in ('sail','rope','spar')]
    failures=[];edge_contacts=[];tested=0
    for sail in sails:
        for other in obstacles:
            if other is sail:continue
            if other['kind']=='sail' and other['name']<sail['name']:continue
            if any(sail['max'][k]<other['min'][k] or other['max'][k]<sail['min'][k] for k in range(3)):continue
            tested+=1
            overlaps=sail['tree'].overlap(other['tree'])
            if not overlaps:continue
            interior=0;contacts=0;unknown=0
            attached=other['extras'].get('attachment_sail')==sail['name'] and bool(other['extras'].get('edge_attachment'))
            reason=intended_joint(sail['name'],other['name'],design)
            for i,j in overlaps:
                points=triangle_intersection_points(sail['triangles'][i],other['triangles'][j])
                if not points:
                    unknown+=1;continue
                is_edge=all(distance_to_edges(p,sail['boundaries'])<=EDGE_CONTACT_TOLERANCE for p in points)
                if is_edge and (attached or reason):contacts+=1
                else:interior+=1
            if contacts:
                edge_contacts.append({'sail':sail['name'],'other':other['name'],'triangle_pairs':contacts,
                                      'reason':reason or 'own sewn bolt rope','max_boundary_distance_m':EDGE_CONTACT_TOLERANCE})
            if interior or unknown:
                failures.append({'sail':sail['name'],'other':other['name'],'interior_triangle_pairs':interior,
                                 'unclassified_overlap_pairs':unknown,'total_pairs':len(overlaps)})
    return {'passed':not failures,'sails':len(sails),'ropes':sum(r['kind']=='rope' for r in records),
            'spars':sum(r['kind']=='spar' for r in records),'pairs_tested':tested,
            'scope':'authored static pose; boundary allowance only for explicit, reasoned attachments',
            'edge_contact_tolerance_m':EDGE_CONTACT_TOLERANCE,'edge_contacts':edge_contacts,'intersections':failures}


def inside(tree,p):
    votes=[]
    for direction in (Vector((1,.137,.071)).normalized(),Vector((.103,1,.237)).normalized(),Vector((.173,.079,1)).normalized()):
        origin=p+direction*1e-6;hits=0
        for _ in range(128):
            hit,_,_,_=tree.ray_cast(origin,direction,1000)
            if hit is None:break
            hits+=1;origin=hit+direction*1e-5
        votes.append(bool(hits%2))
    return sum(votes)>=2


def audit_penetration(records,design):
    solids=[]
    for r in records:
        if r['kind'] in ('sail','rope') or r['topology']['non_manifold_edges']:continue
        if len(r.get('islands',[]))<=1:
            solids.append({**r,'base_name':r['name']});continue
        for index,island in enumerate(r['islands']):
            points=island['vertices'];ids=island['triangle_indices']
            solids.append({'name':r['name']+'#island_'+str(index),'base_name':r['name'],
                           'vertices':points,'triangles':[tuple(points[i] for i in tri) for tri in ids],
                           'min':Vector(tuple(min(p[k] for p in points) for k in range(3))),
                           'max':Vector(tuple(max(p[k] for p in points) for k in range(3))),
                           'tree':BVHTree.FromPolygons(points,ids,all_triangles=True,epsilon=1e-7)})
    solids.sort(key=lambda r:r['min'].x)
    failures=[];allowed=[];contacts=0;pairs=0
    for i,a in enumerate(solids):
        for b in solids[i+1:]:
            if b['min'].x>a['max'].x:break
            if any(a['max'][k]<b['min'][k] or b['max'][k]<a['min'][k] for k in (1,2)):continue
            overlaps=a['tree'].overlap(b['tree'])
            if not overlaps:continue
            pairs+=1
            reason=intended_joint(a['base_name'],b['base_name'],design)
            if reason:
                allowed.append({'a':a['name'],'b':b['name'],'reason':reason});continue
            maximum=0.0
            for first,second in ((a,b),(b,a)):
                for p in first['vertices']:
                    if any(p[k]<=second['min'][k]+.005 or p[k]>=second['max'][k]-.005 for k in range(3)):continue
                    nearest=second['tree'].find_nearest(p)
                    if nearest[0] is None or nearest[3]<=.005:continue
                    if inside(second['tree'],p):maximum=max(maximum,nearest[3])
            if maximum>.005+1e-5:
                failures.append({'a':a['name'],'b':b['name'],'max_measured_vertex_depth_m':maximum})
            else:contacts+=1
    return {'passed':not failures,'overlapping_solid_pairs':pairs,'surface_contact_pairs':contacts,
            'intended_joints':allowed,'unintended_penetrations':failures,
            'threshold_m':.005,'numeric_tolerance_m':1e-5,
            'connected_solid_parts':len(solids),
            'method':'connected closed islands (including within one mesh), vertices inside counterpart, three-ray majority and nearest-surface depth'}


def summarized_uv(records):
    values=defaultdict(lambda:{'density':[],'anisotropy':[],'area':[],'degenerate_uv_area_m2':0.0,'grain_area':0.0,'grain_aligned_area':0.0})
    missing=[]
    for r in records:
        if r['uv']['missing_uv']:missing.append(r['name'])
        for material,stats in r['uv']['materials'].items():
            v=values[material]
            for key in ('density','anisotropy','area'):v[key].extend(stats[key])
            for key in ('degenerate_uv_area_m2','grain_area','grain_aligned_area'):v[key]+=stats[key]
    output={}
    for name,s in values.items():
        area=sum(s['area']);p5=weighted_percentile(s['density'],s['area'],.05)
        p50=weighted_percentile(s['density'],s['area'],.5);p95=weighted_percentile(s['density'],s['area'],.95)
        high=sum(a for a,v in zip(s['area'],s['anisotropy']) if v>1.25)
        output[name]={'area_m2':area,'texel_density_px_m':{'p5':p5,'median':p50,'p95':p95},
                      'density_p95_p5_ratio':p95/max(p5,1e-12) if p5 is not None else None,
                      'anisotropy_p95':weighted_percentile(s['anisotropy'],s['area'],.95),
                      'anisotropy_over_1_25_area_share':high/max(area,1e-12),
                      'degenerate_uv_area_m2':s['degenerate_uv_area_m2'],
                      'wood_grain_measured_area_m2':s['grain_area'],
                      'wood_grain_aligned_share':s['grain_aligned_area']/s['grain_area'] if s['grain_area'] else None}
    grain_objects=[]
    for r in records:
        for material,s in r['uv']['materials'].items():
            if s['grain_area']>0:
                share=s['grain_aligned_area']/s['grain_area']
                if share<.94:
                    grain_objects.append({'object':r['name'],'kind':r['kind'],'material':material,
                                          'area_m2':s['grain_area'],'aligned_share':share})
    return {'missing_uv_objects':missing,'materials':output,'grain_objects_below_94_percent':grain_objects}


def source_parity(asset,records,export):
    path=asset/'model'/'ship.blend'
    if not path.exists():return {'passed':False,'reason':'Packed source scene missing'}
    bpy.ops.wm.open_mainfile(filepath=str(path))
    depsgraph=bpy.context.evaluated_depsgraph_get()
    source_names=[];points=[];triangles=0;unpacked=[]
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH' or obj.get('asset_role') in ('collision','presentation') or obj.name.lower().startswith('col_') or obj.hide_render:
            continue
        source_names.append(obj.name)
        evaluated=obj.evaluated_get(depsgraph);mesh=evaluated.to_mesh()
        mesh.calc_loop_triangles();triangles+=len(mesh.loop_triangles)
        points.extend(evaluated.matrix_world@v.co for v in mesh.vertices)
        evaluated.to_mesh_clear()
    for im in bpy.data.images:
        if im.source=='FILE' and im.users and not im.packed_file:
            unpacked.append(im.name)
    if not points:return {'passed':False,'reason':'No source visual geometry'}
    source_lo=Vector(tuple(min(p[k] for p in points) for k in range(3)))
    source_hi=Vector(tuple(max(p[k] for p in points) for k in range(3)))
    export_lo=Vector(tuple(min(r['min'][k] for r in records) for k in range(3)))
    export_hi=Vector(tuple(max(r['max'][k] for r in records) for k in range(3)))
    bound_error=max(abs(source_lo[k]-export_lo[k]) for k in range(3))
    bound_error=max(bound_error,max(abs(source_hi[k]-export_hi[k]) for k in range(3)))
    count_error=abs(triangles-export['triangles'])/max(triangles,1)
    exported_names={r['name'] for r in records}
    missing=sorted(set(source_names)-exported_names)
    extra=sorted(exported_names-set(source_names))
    return {'passed':bound_error<=.002 and count_error<=.01 and not missing and not extra and not unpacked,
            'source_triangles':triangles,'export_triangles':export['triangles'],
            'triangle_relative_difference':count_error,'max_bound_error_m':bound_error,
            'missing_source_mesh_nodes':missing,'unexpected_export_mesh_nodes':extra,
            'unpacked_used_images':unpacked,
            'method':'evaluated source visual meshes versus actual GLB mesh names, triangle count and world bounds'}


def topology_summary(records):
    errors=[]
    for r in records:
        t=r['topology'];kind=r['kind']
        reasons=[]
        documented_glass=kind=='glass' and bool(r['extras'].get('topology_reason')) and r['extras'].get('physics','none')=='none'
        if kind!='sail' and not documented_glass and t['non_manifold_edges']:reasons.append('solid is not closed')
        for field in ('zero_area_faces','duplicate_faces','loose_vertices','loose_edges','reversed_closed_components','nearly_zero_volume_closed_components'):
            if t[field]:reasons.append(field)
        if reasons:errors.append({'object':r['name'],'kind':kind,'reasons':reasons,**t})
    return {'passed':not errors,'weld_tolerance_m':MESH_WELD_TOLERANCE,
            'seam_vertices_note':'glTF UV/normal seams are welded only in an analysis copy before topology tests',
            'objects':[{k:r[k] for k in ('name','kind','topology')} for r in records],
            'failures':errors}


def material_json_checks(doc,integrity):
    failures=[];distinct_maps=[];doubles=[];fractional=[]
    for i,m in enumerate(doc.get('materials',[])):
        name=m.get('name',str(i));p=m.get('pbrMetallicRoughness',{})
        metal=p.get('metallicFactor',1)
        if not 0<=metal<=1:failures.append({'name':name,'problem':'metallic factor outside0..1'})
        if 'metallicRoughnessTexture' not in p and min(abs(metal),abs(metal-1))>1e-5:
            fractional.append({'name':name,'factor':metal})
        refs=[]
        for slot in (p.get('baseColorTexture'),p.get('metallicRoughnessTexture'),m.get('normalTexture')):
            if slot:
                texture=doc.get('textures',[])[slot['index']]
                refs.append(texture.get('source'))
        if len(refs)>=2 and len(set(refs))<len(refs):
            distinct_maps.append({'name':name,'image_indices':refs})
        if m.get('doubleSided'):
            doubles.append(name)
        for factor in p.get('baseColorFactor',[1,1,1,1]):
            if not 0<=factor<=1:failures.append({'name':name,'problem':'baseColorFactor outside0..1'})
    return {'passed':not failures and not distinct_maps,'errors':failures,
            'merged_image_role_failures':distinct_maps,'fractional_plain_metal':fractional,
            'double_sided_materials':doubles,'images_power_of_two':all(im['power_of_two'] for im in integrity['images']),
            'note':'glTF image slots enforce sRGB colour vs linear data semantics; OpenGL normal orientation is an authoring convention'}


def measured_hull_dimensions(records,spec):
    points=[p.copy() for r in records if r['kind']=='hull' for p in r['vertices']]
    if not points:return {'passed':False,'reason':'No tagged hull geometry to measure'}
    if spec.get('wreck') and spec.get('heel_deg'):
        angle=math.radians(float(spec['heel_deg']));c,s=math.cos(angle),math.sin(angle)
        points=[Vector((c*p.x-s*p.z,p.y,s*p.x+c*p.z)) for p in points]
    length=max(p.y for p in points)-min(p.y for p in points)
    breadth=max(p.x for p in points)-min(p.x for p in points)
    nominal_l=float(spec['length']);nominal_b=float(spec['beam'])
    min_length=.45 if spec.get('wreck') else .80
    good=min_length*nominal_l<=length<=1.20*nominal_l and .80*nominal_b<=breadth<=1.20*nominal_b
    return {'passed':good,'hull_length_m':length,'hull_breadth_m':breadth,
            'nominal_length_m':nominal_l,'nominal_breadth_m':nominal_b,
            'length_acceptance_ratio':[min_length,1.20],'breadth_acceptance_ratio':[.80,1.20],
            'note':'Scale sanity bounds include real stem/transom structure; wreck retains only part of nominal length, heel removed for measurement'}


CHECKLIST={
 'A1':'Metres and meaningful measured dimensions','A2':'Y up, bow +Z, port +X','A3':'Meaningful root and waterline','A4':'Applied static transforms',
 'B1':'Stable lowercase node names','B2':'Consistent English names','B3':'Side and index in paired part names','B4':'Consistent material names',
 'C1':'Moving parts separate nodes','C2':'Correct physical pivots/axes','C3':'Axis/range metadata','C4':'Children follow moving parent',
 'D1':'Closed solids','D2':'No degenerate/duplicate/loose geometry','D3':'Outward normals','D4':'No coplanar z-fighting','D5':'Needle triangle shading','D6':'Appropriate mesh density','D7':'Fair hull lines','D8':'Untwisted tube surfaces',
 'E1':'No unintended deep penetration','E2':'Reasoned intended joints','E3':'Full movement ranges tested','E4':'Fittings supported by deck','E5':'Rope endpoints attached','E6':'Blocks held by fittings/strops',
 'F1':'Texel density','F2':'Even texel density','F3':'Limited UV anisotropy','F4':'Wood grain follows timber','F5':'Rope UV scaled by diameter','F6':'Power-of-two textures','F7':'Correct colour/data map roles','F8':'AO on dedicated UV',
 'G1':'Physical base colours','G2':'Metal/nonmetal materials','G3':'Linear colour factors','G4':'Double-sided only where needed','G5':'No duplicate materials',
 'H1':'File size budget','H2':'Triangle budget','H3':'Exported file matches source','H4':'Independent texture roles survive export','H5':'Source/export control renders','H6':'Tangents strategy',
 'I1':'LOD levels','I2':'LOD silhouette continuity','I3':'Collision coverage and geometry','I4':'Variant colliders tagged',
 'J1':'Required destinations reachable','J2':'Room at work stations','J3':'Walking corridors','J4':'Head clearance','J5':'Access with guns recoiled','J6':'Paired rope symmetry'}


def make_matrix(checks,records,doc,design,nav):
    matrix={k:{'id':k,'chapter':k[0],'title':v,'status':'NA','required':False,
               'scope':'not_tested','reason':'This item needs additional authored evidence; it is not counted as a passing test.'}
            for k,v in CHECKLIST.items()}
    def put(key,passed,evidence,required=True,reason=None):
        matrix[key].update(status='PASS' if passed else 'FAIL',required=required,scope='measured',evidence=evidence)
        matrix[key].pop('reason',None)
        if reason:matrix[key]['reason']=reason
    def na(key,reason,scope='not_applicable'):
        matrix[key].update(status='NA',required=False,scope=scope,reason=reason)
    export=checks['export']['model/ship.glb']
    put('A1',checks['dimensions']['passed'] and nav.get('units','metres') in ('metres','meters','m'),{'world_bounds':checks['bounds'],'hull_measurement':checks['dimensions']})
    axes=nav.get('axes',nav.get('coordinate_system',''))
    put('A2',bool(axes) and ('up' in str(axes).lower() or 'gltf' in str(axes).lower()),{'navigation_axis_declaration':axes})
    origin=any(n.get('name','').lower() in ('asset_origin','ship_origin','vessel_origin') for n in doc.get('nodes',[]))
    put('A3',origin or bool(design.get('origin')),{'origin_node_present':origin,'design_origin':design.get('origin')})
    bad_transforms=[]
    for r in records:
        e=r['extras']
        moving=any(k in e for k in ('motion_axis','range_deg','range_m','os_ruchu','control_type'))
        if not moving and (any(abs(v-1)>1e-5 for v in r['transform']['scale']) or any(abs(v)>1e-5 for v in r['transform']['rotation'])):
            bad_transforms.append(r['name'])
    put('A4',not bad_transforms,{'unapplied_static_mesh_transforms':bad_transforms})
    names=[n.get('name','') for n in doc.get('nodes',[]) if n.get('name')]
    bad_names=[n for n in names if not re.fullmatch('[a-z0-9_]+',n)]
    put('B1',not bad_names,{'invalid_names':bad_names})
    material_names=[m.get('name','') for m in doc.get('materials',[])]
    duplicate_material_names=[n for n in material_names if re.search(r'\.\d{3}$',n)]
    put('B4',not duplicate_material_names,{'copy_suffix_material_names':duplicate_material_names})
    if design.get('moving_parts'):
        moving=design['moving_parts'];node_names=set(names)
        absent=[m.get('name') for m in moving if m.get('name') not in node_names]
        missing_meta=[m.get('name') for m in moving if not m.get('axis') or m.get('range') is None]
        put('C1',not absent,{'missing_moving_nodes':absent})
        put('C3',not missing_meta,{'incomplete_motion_records':missing_meta})
        na('E3','Authored static asset release; moving-part collision range simulation is not included.','not_tested')
    else:
        for k in ('C1','C2','C3','C4'):na(k,'No moving-part contract is declared for this static asset release.','not_tested')
    topology=checks['topology']['model/ship.glb']
    put('D1',not any(r['kind']!='sail' and not (r['kind']=='glass' and r['extras'].get('topology_reason') and r['extras'].get('physics','none')=='none') and r['topology']['non_manifold_edges'] for r in records),{'failures':topology['failures']})
    put('D2',not any(any(r['topology'][k] for k in ('zero_area_faces','duplicate_faces','loose_vertices','loose_edges')) for r in records),{'failures':topology['failures']})
    put('D3',not any(r['topology']['reversed_closed_components'] for r in records),{'reversed_objects':[r['name'] for r in records if r['topology']['reversed_closed_components']]})
    put('E1',checks['penetration']['passed'],checks['penetration'])
    joint_rules=design.get('intended_joints',[])
    put('E2',all(isinstance(j,dict) and bool(j.get('reason')) and bool(j.get('a')) and bool(j.get('b')) for j in joint_rules),{'declared_rules':len(joint_rules),'structured_rules_required':True})
    uv=checks['uv']['materials']
    density_fail=[];spread_fail=[];anisotropy_fail=[];grain_fail=[]
    for name,s in uv.items():
        lname=name.lower()
        large=any(x in lname for x in ('deck','poklad','hull','burta','planking','side_oiled'))
        exempt=any(x in lname for x in ('rope','lina','glass','szklo','canvas','flax','plotno'))
        p=s['texel_density_px_m']
        if not exempt and ((large and (p['median']<850 or p['p5']<800)) or (not large and p['p5']<450)):
            density_fail.append(name)
        if not exempt and s['density_p95_p5_ratio']>1.44:spread_fail.append(name)
        if not exempt and s['anisotropy_over_1_25_area_share']>.08:anisotropy_fail.append(name)
        if s['wood_grain_aligned_share'] is not None and s['wood_grain_aligned_share']<.94:grain_fail.append(name)
    put('F1',bool(uv) and not density_fail,{'materials':uv,'below_density_target':density_fail,
        'targets':'large median>=850,p5>=800px/m (about1k); fittings p5>=450px/m; canvas/rope/glass measured separately'})
    put('F2',not spread_fail,{'materials_above_p95_p5_1_44':spread_fail})
    put('F3',not anisotropy_fail,{'materials_above_8_percent_area_at_anisotropy1_25':anisotropy_fail})
    if any(s['wood_grain_aligned_share'] is not None for s in uv.values()):
        put('F4',not grain_fail,{'wood_grain_failures':grain_fail,'method':'elongated wooden meshes, side-face U tangent within25deg of major timber axis'})
    else:na('F4','No single-axis elongated wooden object could be measured; aggregate grain requires manual review.','not_tested')
    mats=checks['materials']
    put('F6',mats['images_power_of_two'],{'images':export['images']})
    put('F7',not mats['merged_image_role_failures'],{'material_slot_failures':mats['merged_image_role_failures']})
    ao=[m.get('name','') for m in doc.get('materials',[]) if m.get('occlusionTexture')]
    if not ao:na('F8','No baked AO texture is supplied; material AO is not claimed.')
    else:
        bad=[m.get('name','') for m in doc.get('materials',[]) if m.get('occlusionTexture') and m['occlusionTexture'].get('texCoord',0)!=1]
        put('F8',not bad,{'AO_materials_without_UV1':bad})
    put('G2',not mats['fractional_plain_metal'],{'fractional_plain_metallic_factors':mats['fractional_plain_metal']})
    put('G3',not mats['errors'],{'linear_glTF_factors_valid_0_1':not mats['errors'],'note':'sRGB-to-linear provenance remains in design/material recipe, glTF factor values are linear by specification'})
    unjustified=[n for n in mats['double_sided_materials'] if not any(x in n.lower() for x in ('canvas','flax','sail','plotno','glass','szklo','flag','pennant'))]
    put('G4',not unjustified,{'unjustified_double_sided_materials':unjustified})
    fingerprints=[]
    for m in doc.get('materials',[]):
        c=dict(m);c.pop('name',None);c.pop('extras',None);fingerprints.append(json.dumps(c,sort_keys=True))
    duplicates=len(fingerprints)-len(set(fingerprints))
    put('G5',duplicates==0,{'exact_duplicate_materials':duplicates})
    put('H1',export['bytes']<=32*1024*1024,{'bytes':export['bytes'],'budget_bytes':32*1024*1024})
    put('H2',export['triangles']<=280000,{'triangles':export['triangles'],'budget':280000})
    put('H4',not mats['merged_image_role_failures'],{'distinct_image_role_check':mats['merged_image_role_failures'],'embedded_images':len(export['images'])})
    tangent_count=sum('TANGENT' in p.get('attributes',{}) for me in doc.get('meshes',[]) for p in me.get('primitives',[]))
    put('H6',True,{'primitives_with_tangents':tangent_count,'strategy':'provided tangent attribute or engine-derived glTF tangent basis'})
    put('I1',checks['lods']['passed'],checks['lods'])
    put('I3',checks['navigation']['model/collision.glb']['passed'] and checks['topology']['model/collision.glb']['passed'],
        {'topology':checks['topology']['model/collision.glb']['passed'],'route_checks':checks['navigation']['model/collision.glb']})
    if not any(n.get('extras',{}).get('variant') for n in doc.get('nodes',[])):
        na('I4','No alternate physics variant is exported.')
    nav_pass=all(v['passed'] for v in checks['navigation'].values())
    na('J1','No complete floor-grid flood fill against every declared crew workstation has been run; authored player corridors are a separate required gate.','not_tested')
    width_pass=all(v['passed'] for v in checks['walking_width'].values())
    put('J3',width_pass,{'minimum_tested_capsule_diameter_m':.80,'scope':'declared walk corridors, strict zero geometric shrink','files':checks['walking_width']})
    put('J4',nav_pass,{'capsule_height_m':nav['player']['height'],'files':checks['navigation']})
    if not design.get('guns') and not any('gun' in r['name'] or 'dzial' in r['name'] for r in records):
        na('J5','No carriage guns in this asset.')
    if not checks['rig']['sails']:
        for k in ('E5','E6','F5','J6'):
            if not checks['rig']['ropes']:na(k,'No rigging in this vessel.')
    # These are explicit independent gates outside the letter-number guide table.
    put('H3',checks['source_parity']['passed'],checks['source_parity'])
    review=checks['render_parity']
    if review.get('present'):
        put('H5',review.get('passed',False),review)
    else:
        na('H5','Source/export control renders have not yet been provided.','not_tested')
        matrix['H5']['required']=True
    matrix['provenance']={'id':'provenance','chapter':'source','title':'Traceable construction design and rules','required':True,
                           'status':'PASS' if checks['provenance']['passed'] else 'FAIL','scope':'measured','evidence':checks['provenance']}
    matrix['rig_clearance']={'id':'rig_clearance','chapter':'E','title':'No undeclared canvas/rope/spar crossings','required':True,
                            'status':'PASS' if checks['rig']['passed'] else 'FAIL','scope':'measured','evidence':checks['rig']}
    matrix['player_destinations']={'id':'player_destinations','chapter':'J','title':'Declared player destinations and connected routes','required':True,
                                   'status':'PASS' if nav_pass else 'FAIL','scope':'measured','evidence':checks['navigation']}
    return list(matrix.values())


def self_test():
    floor=[Vector((-5,-5,0)),Vector((5,-5,0)),Vector((5,5,0)),Vector((-5,5,0))]
    def rec(name,tris,kind='fitting'):
        pts=[p for t in tris for p in t]
        return {'name':name,'triangles':tris,'kind':kind,'extras':{},
                'min':Vector(tuple(min(p[k] for p in pts) for k in range(3))),
                'max':Vector(tuple(max(p[k] for p in pts) for k in range(3)))}
    ground=rec('floor',[(floor[0],floor[1],floor[2]),(floor[0],floor[2],floor[3])])
    nav={'player':{'radius':.38,'height':1.85,'max_slope_deg':35},
         'routes':[{'name':'control','points':[[0,0,-1],[0,0,1]],'mode':'walk'}]}
    assert audit_routes([ground],nav)['passed'],'Open floor must pass'
    wall=rec('wall',[(Vector((-2,0,0)),Vector((2,0,0)),Vector((0,0,3)))])
    assert not audit_routes([ground,wall],nav)['passed'],'Wall must fail'
    ceiling=rec('ceiling',[(Vector((-3,-3,1.5)),Vector((3,-3,1.5)),Vector((0,3,1.5)))])
    assert not audit_routes([ground,ceiling],nav)['passed'],'Low ceiling must fail'
    assert not audit_routes([],nav)['passed'],'Missing floor must fail'
    tri=(Vector((-1,0,0)),Vector((1,0,0)),Vector((0,0,2)))
    assert capsule_triangle_d2(Vector((0,-1,1)),Vector((0,1,1)),tri)==0
    assert capsule_triangle_d2(Vector((0,-2,1)),Vector((0,-1,1)),tri)>.9
    def cube(name,center,size):
        x,y,z=center;a,b,c=[v/2 for v in size]
        vertices=[Vector((x+sx*a,y+sy*b,z+sz*c)) for sz in (-1,1) for sy in (-1,1) for sx in (-1,1)]
        faces=[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]
        triangles=[]
        for face in faces:
            triangles.extend((face[0],face[i],face[i+1]) for i in range(1,len(face)-1))
        r=rec(name,[tuple(vertices[i] for i in t) for t in triangles])
        r.update(vertices=vertices,tree=BVHTree.FromPolygons(vertices,triangles,all_triangles=True,epsilon=1e-7),
                 topology={'non_manifold_edges':0},boundaries=[],islands=[])
        return r
    a=cube('control_a',(0,0,0),(2,2,2));b=cube('control_b',(.5,.5,.5),(2,2,2))
    assert not audit_penetration([a,b],{})['passed'],'Deep solid penetration must fail'
    joint={'intended_joints':[{'a':'control_a','b':'control_b','reason':'Explicit synthetic mortise control'}]}
    assert audit_penetration([a,b],joint)['passed'],'Reasoned intended joint should be recorded'
    sail=rec('sail_control',[tri],'sail');sail.update(tree=BVHTree.FromPolygons(list(tri),[(0,1,2)],all_triangles=True,epsilon=1e-7),
         boundaries=[(tri[0],tri[1]),(tri[1],tri[2]),(tri[2],tri[0])])
    crossing=cube('rope_crossing',(0,0,1),(.02,2,.02));crossing['kind']='rope'
    assert not audit_rig([sail,crossing],{})['passed'],'Rope through cloth interior must fail'
    bolt=cube('sewn_bolt',(0,0,0),(1.6,.012,.012));bolt['kind']='rope'
    bolt['extras']={'attachment_sail':'sail_control','edge_attachment':True}
    assert audit_rig([sail,bolt],{})['passed'],'Explicit sewn boundary attachment should pass'
    return ['open floor accepted','wall rejected','low ceiling rejected','missing floor rejected',
            'capsule/triangle crossing detected','separated capsule/triangle accepted',
            'deep solid penetration rejected','reasoned joint recorded','rope through cloth rejected',
            'explicit sewn boundary attachment accepted']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('spec',nargs='?')
    parser.add_argument('--asset-dir');parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--skip-penetration',action='store_true',help='Diagnostic run only; acceptance report remains failed')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    controls=self_test()
    if args.self_test and not args.spec:
        print(json.dumps({'passed':True,'negative_controls':controls},indent=2));return
    if not args.spec:raise ValueError('A specification is required')
    spec_path=Path(args.spec).resolve();asset=Path(args.asset_dir).resolve() if args.asset_dir else spec_path.parent
    spec=json.loads(spec_path.read_text(encoding='utf-8'))
    nav=json.loads((asset/'navigation.json').read_text(encoding='utf-8'))
    design=json.loads((asset/'design.json').read_text(encoding='utf-8'))
    checks={'export':{},'topology':{},'navigation':{},'walking_width':{},'negative_controls':controls}
    visual_records=None;visual_doc=None
    for filename in ('model/ship.glb','model/collision.glb'):
        print('AUDIT_IMPORT',filename,flush=True)
        integrity,doc,_=inspect_glb(asset/filename)
        checks['export'][filename]=integrity
        records=object_records(asset/filename)
        checks['topology'][filename]=topology_summary(records)
        checks['navigation'][filename]=audit_routes(records,nav)
        width_nav=dict(nav);width_nav['player']=dict(nav['player']);width_nav['player']['radius']=.40
        width_nav['routes']=[r for r in nav['routes'] if r.get('mode','walk')=='walk']
        checks['walking_width'][filename]=audit_routes(records,width_nav,geometry_tolerance=0,check_connectivity=False)
        if filename=='model/ship.glb':
            visual_records=records;visual_doc=doc
            checks['rig']=audit_rig(records,design)
            checks['uv']=summarized_uv(records)
            checks['materials']=material_json_checks(doc,integrity)
            checks['penetration']=({'passed':False,'reason':'diagnostic skip; full penetration audit required'} if args.skip_penetration else audit_penetration(records,design))
    lods=[]
    for level in (1,2):
        path=asset/'model'/f'ship_lod{level}.glb'
        if path.exists():
            report,_,_=inspect_glb(path);lods.append({'level':level,**report})
        else:lods.append({'level':level,'passed':False,'error':'LOD file missing'})
    n0=checks['export']['model/ship.glb']['triangles']
    checks['lods']={'passed':all(l.get('passed') for l in lods) and len(lods)==2 and
                   lods[0].get('triangles',n0)<n0 and lods[1].get('triangles',n0)<lods[0].get('triangles',0),
                   'lod0_triangles':n0,'levels':lods}
    sources=next((design[k] for k in ('sources','source_files','source_sha256','basis','source_paths','provenance','source','reference_repository') if design.get(k)),None)
    rules=next((design[k] for k in ('rules','formulas','derived_parameters','construction') if design.get(k)),None)
    if rules is None and isinstance(design.get('source'),dict):
        rules=design['source'].get('rules',design['source'].get('derived_parameters'))
    checks['provenance']={'passed':bool(sources) and bool(rules),'source_evidence':sources,'rule_evidence':rules}
    checks['source_parity']=source_parity(asset,visual_records,checks['export']['model/ship.glb'])
    review_path=asset/'export-review.json'
    if review_path.exists():
        review=json.loads(review_path.read_text(encoding='utf-8'))
        hashes_match=all((asset/p).is_file() and digest(asset/p)==expected for p,expected in review.get('sha256',{}).items())
        checks['render_parity']={'present':True,'passed':bool(review.get('passed')) and hashes_match,
                                 'fingerprints_match':hashes_match,'review':review}
    else:
        checks['render_parity']={'present':False,'passed':False}
    all_points=[p for r in visual_records for p in (r['min'],r['max'])]
    checks['bounds']={'min_blender_m':[min(p[k] for p in all_points) for k in range(3)],
                      'max_blender_m':[max(p[k] for p in all_points) for k in range(3)]}
    checks['dimensions']=measured_hull_dimensions(visual_records,spec)
    matrix=make_matrix(checks,visual_records,visual_doc,design,nav)
    passed=all(c['status']=='PASS' for c in matrix if c['required']) and all(v['passed'] for v in checks['topology'].values())
    fingerprints={}
    for p in sorted(asset.rglob('*')):
        if p.is_file() and p.name not in ('validation.json',) and p.suffix.lower() in ('.glb','.blend','.json','.jpg','.png'):
            fingerprints[p.relative_to(asset).as_posix()]=digest(p)
    fingerprints['spec.json']=digest(spec_path)
    source_root=Path(__file__).resolve().parents[2]
    source_fingerprints={}
    for script in sorted(Path(__file__).resolve().parent.glob('v2_*.py')):
        source_fingerprints[script.relative_to(source_root).as_posix()]=digest(script)
    legacy_helper=Path(__file__).resolve().parent/'rebuild_reference.py'
    if legacy_helper.is_file():source_fingerprints[legacy_helper.relative_to(source_root).as_posix()]=digest(legacy_helper)
    referenced=design.get('source_files',{})
    if isinstance(referenced,list):
        referenced={v['path']:v.get('sha256') for v in referenced if isinstance(v,dict) and v.get('path')}
    if not referenced and isinstance(design.get('source_sha256'),dict):
        referenced={'blender/'+k:v for k,v in design['source_sha256'].items()}
    if isinstance(referenced,dict):
        for relative in referenced:
            canonical=relative.replace('\\','/')
            if canonical.startswith('upstream/'):
                canonical=canonical[len('upstream/'):]
            path=resolve_source(source_root,canonical)
            if path.is_file():source_fingerprints[canonical]=digest(path)
    basis=design.get('basis',{})
    if isinstance(basis,dict) and isinstance(basis.get('source'),str):
        canonical=basis['source'].split(':',1)[0].replace('\\','/')
        if canonical.startswith('upstream/'):canonical=canonical[len('upstream/'):]
        path=resolve_source(source_root,canonical)
        if path.is_file():source_fingerprints[canonical]=digest(path)
    coverage={s:sum(c['status']==s for c in matrix) for s in ('PASS','FAIL','NA')}
    coverage['not_tested']=sum(c.get('scope')=='not_tested' for c in matrix)
    result={'schema':2,'vessel':spec.get('id'),'blender':bpy.app.version_string,'passed':passed,
            'scope':'authored static assets and declared player routes; per-item matrix contains all untested or inapplicable guide checks',
            'checks':checks,'matrix':matrix,'coverage':coverage,'sha256':fingerprints,'source_sha256':source_fingerprints}
    (asset/'validation.json').write_text(json.dumps(plain(result),indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    summary={'vessel':spec.get('id'),'passed':passed,'coverage':coverage,
             'failed_required':[c['id'] for c in matrix if c['required'] and c['status']!='PASS'],
             'topology_failures':{k:len(v['failures']) for k,v in checks['topology'].items()},
             'navigation_failures':{k:[r['name'] for r in v.get('routes',[]) if not r['passed']] for k,v in checks['navigation'].items()}}
    print(json.dumps(plain(summary),indent=2),flush=True)
    if not passed:raise RuntimeError('Vessel acceptance failed; inspect validation.json')


if __name__=='__main__':main()
