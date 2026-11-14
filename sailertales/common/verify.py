"""Reimport the delivered GLBs, sweep an upright player capsule along authored routes.

Run with Blender like build.py. Results bind to SHA256 of both GLBs and navigation.
This validates authored routes, not every point of a navigation mesh or game physics.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import closest_point_on_tri, intersect_ray_tri


def segment_distance2(p1,q1,p2,q2):
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


def tri_capsule_d2(a,b,tri):
    v0,v1,v2=tri
    hit=intersect_ray_tri(v0,v1,v2,b-a,a,True)
    if hit is not None and (hit-a).dot(b-a)>=0 and (hit-a).length_squared<=(b-a).length_squared+1e-10:
        return 0
    d=min((closest_point_on_tri(a,*tri)-a).length_squared,
          (closest_point_on_tri(b,*tri)-b).length_squared)
    for c,e in [(v0,v1),(v1,v2),(v2,v0)]:d=min(d,segment_distance2(a,b,c,e))
    return d


def load(path):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(path))
    bpy.context.view_layer.update()
    tris=[];vertices=[];faces=[]
    for o in list(bpy.context.scene.objects):
        if o.type!='MESH':continue
        o.data.calc_loop_triangles()
        for t in o.data.loop_triangles:
            tri=tuple(o.matrix_world@o.data.vertices[i].co for i in t.vertices)
            n=(tri[1]-tri[0]).cross(tri[2]-tri[0]).normalized()
            mn=Vector(tuple(min(v[k] for v in tri) for k in range(3)))
            mx=Vector(tuple(max(v[k] for v in tri) for k in range(3)))
            tris.append((o.name,tri,n,mn,mx,o.get('physics')))
            i=len(vertices);vertices.extend(tri);faces.append((i,i+1,i+2))
    return tris,BVHTree.FromPolygons(vertices,faces,all_triangles=True)


def to_blender(q):return Vector((q[0],-q[2],q[1]))


def rig_intersections(tris):
    groups={}
    rope_prefixes=('Shroud','Lift','Forestay')
    spar_prefixes=('Mast','Yard','Boom','Gaff','Bowsprit')
    for name,tri,*_ in tris:
        if name.startswith(('Sail_',)+rope_prefixes+spar_prefixes):
            groups.setdefault(name,[]).append(tri)
    trees={}
    for name,tt in groups.items():
        vertices=[v for t in tt for v in t]
        trees[name]=BVHTree.FromPolygons(vertices,[(i,i+1,i+2) for i in range(0,len(vertices),3)],all_triangles=True)
    errors=[]
    sails=[n for n in trees if n.startswith('Sail_')]
    for i,sail in enumerate(sails):
        for other in trees:
            if other==sail or (other in sails and sails.index(other)<i):continue
            pairs=trees[sail].overlap(trees[other])
            if pairs:errors.append({'sail':sail,'other':other,'triangle_pairs':len(pairs)})
    return {'passed':not errors,'sails':len(sails),
            'ropes':sum(n.startswith(rope_prefixes) for n in trees),
            'spars':sum(n.startswith(spar_prefixes) for n in trees),
            'scope':'authored static pose; bolt ropes are cloth-edge attachments',
            'intersections':errors}


def sweep(tris,bvh,nav):
    radius=nav['player']['radius'];height=nav['player']['height']
    # 15 mm geometric tolerance, 8 cm floor separation for the rounded foot on slopes.
    r=radius-0.015
    slope=math.cos(math.radians(nav['player']['max_slope_deg']))
    results=[]
    for route in nav['routes']:
        pts=[to_blender(q) for q in route['points']]
        samples=[]
        for a,b in zip(pts,pts[1:]):
            N=max(1,math.ceil((b-a).length/0.12))
            samples.extend(a.lerp(b,i/N) for i in range(N))
        samples.append(pts[-1])
        errors=[]
        for pi,foot in enumerate(samples):
            start=foot+Vector((0,0,.22))
            hit,normal,_,_=bvh.ray_cast(start,Vector((0,0,-1)),.52)
            if hit is None:
                errors.append({'sample':pi,'problem':'no floor within 30 cm','at':list(foot)})
                continue
            if abs(normal.z)<slope:
                errors.append({'sample':pi,'problem':'floor steeper than 35 degrees','normal':list(normal)})
                continue
            foot=Vector((foot.x,foot.y,hit.z))
            a=foot+Vector((0,0,r+.08));b=foot+Vector((0,0,height-r))
            lo=Vector((foot.x-r,foot.y-r,foot.z+.06))
            hi=Vector((foot.x+r,foot.y+r,foot.z+height))
            for name,tri,n,mn,mx,physics in tris:
                if any(mx[k]<lo[k] or mn[k]>hi[k] for k in range(3)):continue
                # A controller may step up 22 cm onto a visible stair tread.
                # This does not exempt low ceilings or other obstacles.
                if mx.z <= foot.z + .22:continue
                # Ignore the plane carrying this foot, not all surfaces of its object.
                if abs(n.z)>slope:
                    plane_z=tri[0].z-(n.x*(foot.x-tri[0].x)+n.y*(foot.y-tri[0].y))/n.z
                    if abs(plane_z-foot.z)<.14:continue
                if tri_capsule_d2(a,b,tri)<r*r-1e-8:
                    errors.append({'sample':pi,'problem':'capsule blocked','by':name,'at':list(foot)})
                    break
        results.append({'route':route['name'],'samples':len(samples),'passed':not errors,
                        'failures':errors[:8],'failure_count':len(errors)})
    return results


def self_test():
    # Negative controls ensure a wall and low ceiling actually fail the sweep.
    tri=(Vector((-2,0,0)),Vector((2,0,0)),Vector((0,0,3)))
    assert tri_capsule_d2(Vector((0,-1,1)),Vector((0,1,1)),tri)==0
    assert tri_capsule_d2(Vector((0,-2,1)),Vector((0,-1,1)),tri)>.9
    floor=[Vector((-5,-5,0)),Vector((5,-5,0)),Vector((5,5,0)),Vector((-5,5,0))]
    fs=[(0,1,2),(0,2,3)]
    nav={'player':{'radius':.38,'height':1.85,'max_slope_deg':35},
         'routes':[{'name':'control','points':[[0,0,-1],[0,0,1]]}]}
    def triangle(name,vs):
        n=(vs[1]-vs[0]).cross(vs[2]-vs[0]).normalized()
        return (name,vs,n,Vector(tuple(min(v[k] for v in vs) for k in range(3))),
                Vector(tuple(max(v[k] for v in vs) for k in range(3))),None)
    tris=[triangle('floor',tuple(floor[i] for i in f)) for f in fs]
    bvh=BVHTree.FromPolygons(floor,fs,all_triangles=True)
    assert sweep(tris,bvh,nav)[0]['passed']
    assert not sweep(tris+[triangle('wall',tri)],bvh,nav)[0]['passed']
    ceiling=tuple(Vector(v) for v in [(-3,-3,1.5),(3,-3,1.5),(0,3,1.5)])
    assert not sweep(tris+[triangle('ceiling',ceiling)],bvh,nav)[0]['passed']


def main():
    ap=argparse.ArgumentParser();ap.add_argument('spec');args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    self_test()
    path=Path(args.spec).resolve();dest=path.parent
    nav=json.loads((dest/'navigation.json').read_text())
    report={'schema':1,'blender':bpy.app.version_string,'capsule':nav['player'],
            'step_m':.12,'geometric_tolerance_m':.015,'rounded_foot_lift_m':.08,
            'negative_controls':['wall rejects','low ceiling rejects','open floor passes'],
            'checks':{},'sha256':{}}
    for filename in ['model/ship.glb','model/collision.glb']:
        f=dest/filename
        report['sha256'][filename]=hashlib.sha256(f.read_bytes()).hexdigest()
        tris,bvh=load(f)
        report['checks'][filename]={'triangles':len(tris),'routes':sweep(tris,bvh,nav)}
        if filename=='model/ship.glb':report['rig']=rig_intersections(tris)
    report['sha256']['navigation.json']=hashlib.sha256((dest/'navigation.json').read_bytes()).hexdigest()
    report['sha256']['spec.json']=hashlib.sha256(path.read_bytes()).hexdigest()
    for script in ['build.py','verify.py']:
        report['sha256']['../common/'+script]=hashlib.sha256((dest.parent/'common'/script).read_bytes()).hexdigest()
    report['passed']=all(r['passed'] for c in report['checks'].values() for r in c['routes']) and report['rig']['passed']
    (dest/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if not report['passed']:raise RuntimeError('Exported geometry blocks an authored route')


if __name__=='__main__':main()
