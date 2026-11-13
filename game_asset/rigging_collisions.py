"""Blender geometry audit for ropes/canvas and mutually intersecting sails.

blender -b ship.blend --python game_asset/rigging_collisions.py -- report.json
The authored cloth loop is sampled at frames 0,12,...,96. Connections on the
cloth perimeter (within 25 mm) are reported separately from interior crossings.
"""
import collections
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree


def geometry(obj,evaluated=False,rope_only=False,material_indices=None):
    evaluated_obj=obj.evaluated_get(bpy.context.evaluated_depsgraph_get()) if evaluated else None
    mesh=evaluated_obj.to_mesh() if evaluated else obj.data
    matrix=obj.matrix_world
    rope_materials={i for i,m in enumerate(mesh.materials) if m and m.name.startswith(("rope_tarred","rope_untarred"))}
    selected=rope_materials if rope_only else material_indices
    faces=[tuple(p.vertices) for p in mesh.polygons if selected is None or p.material_index in selected]
    if not faces:
        if evaluated_obj: evaluated_obj.to_mesh_clear()
        return None
    used=set(i for f in faces for i in f)
    remap={old:new for new,old in enumerate(sorted(used))}
    verts=[matrix@mesh.vertices[i].co for i in sorted(used)]
    faces=[tuple(remap[i] for i in f) for f in faces]
    edges=collections.Counter(tuple(sorted((a,b))) for f in faces for a,b in zip(f,f[1:]+f[:1]))
    lo=Vector(tuple(min(v[k] for v in verts) for k in range(3)))
    hi=Vector(tuple(max(v[k] for v in verts) for k in range(3)))
    record={"vertices":verts,"edges":list(edges),"lo":lo,"hi":hi}
    if not rope_only:
        record["bvh"]=BVHTree.FromPolygons(verts,faces,all_triangles=False,epsilon=1e-7)
        samples=[]
        for (a,b),count in edges.items():
            if count!=1: continue
            n=max(1,math.ceil((verts[a]-verts[b]).length/.015))
            samples.extend(verts[a].lerp(verts[b],i/n) for i in range(n+1))
        kd=KDTree(len(samples))
        for i,p in enumerate(samples):kd.insert(p,i)
        kd.balance(); record["boundary"]=kd
    if evaluated_obj: evaluated_obj.to_mesh_clear()
    return record


def intersections(source,target):
    if any(source["hi"][k]<target["lo"][k] or source["lo"][k]>target["hi"][k] for k in range(3)):
        return [],0
    hits=[]; boundary_contacts=0
    lo,hi=target["lo"],target["hi"]
    for i,j in source["edges"]:
        a,b=source["vertices"][i],source["vertices"][j]
        if any(max(a[k],b[k])<lo[k]-1e-5 or min(a[k],b[k])>hi[k]+1e-5 for k in range(3)):continue
        delta=b-a; length=delta.length
        if length<1e-7:continue
        point,_,_,_=target["bvh"].ray_cast(a,delta/length,length)
        if point is None:continue
        if target["boundary"].find(point)[2]<=.025:
            boundary_contacts+=1
        elif all((point-p).length>.08 for p in hits):hits.append(point)
    return hits,boundary_contacts


def audit_scene(frames=tuple(range(0,97,12)),check_sails=True):
    old_frame=bpy.context.scene.frame_current
    bpy.context.scene.frame_set(0)
    ropes={}
    for obj in bpy.data.objects:
        if obj.type=="MESH" and not obj.name.startswith("preview_"):
            record=geometry(obj,rope_only=True)
            if record:ropes[obj.name]=record
    sail_specs=[]
    for obj in bpy.data.objects:
        if obj.type!="MESH":continue
        for index,material in enumerate(obj.data.materials):
            if material and material.name.startswith("flax_"):
                sail_specs.append((material.name.removeprefix("flax_")+"_set",obj,{index}))
    if len(sail_specs)!=12:
        raise ValueError("Expected all 12 cloth materials, found %d"%len(sail_specs))
    result={"frames":list(frames),"rope_objects":len(ropes),"sails":len(sail_specs),
            "boundary_tolerance_m":.025,"scope":"Rope mesh edges versus cloth interior; own bolt ropes are expected edge attachments. Sail edges versus other cloth interiors are checked in both directions.","per_frame":[],"hits":[]}
    for frame in frames:
        bpy.context.scene.frame_set(frame)
        sails={name:geometry(o,evaluated=True,material_indices=indices) for name,o,indices in sail_specs}
        crossing_pairs=0; contacts=0
        for rope,record in ropes.items():
            for sail,target in sails.items():
                if rope.startswith(sail.removesuffix("_set")+"_bolt_rope_"):continue
                hits,touch=intersections(record,target);contacts+=touch
                if hits:
                    crossing_pairs+=1
                    result["hits"].append({"frame":frame,"kind":"rope_canvas","rope":rope,"sail":sail,"points_blender_m":[[round(v,5) for v in p] for p in hits]})
        sail_pairs=0
        if check_sails:
            names=list(sails)
            for i,a in enumerate(names):
                for b in names[i+1:]:
                    h1,t1=intersections(sails[a],sails[b]);h2,t2=intersections(sails[b],sails[a]);contacts+=t1+t2
                    if h1 or h2:
                        sail_pairs+=1
                        result["hits"].append({"frame":frame,"kind":"canvas_canvas","a":a,"b":b,"points_blender_m":[[round(v,5) for v in p] for p in (h1+h2)[:16]]})
        result["per_frame"].append({"frame":frame,"rope_canvas_pairs":crossing_pairs,"canvas_canvas_pairs":sail_pairs,"perimeter_contacts":contacts})
    bpy.context.scene.frame_set(old_frame)
    result["passed"]=not result["hits"]
    return result


if __name__=="__main__":
    path=Path(sys.argv[sys.argv.index("--")+1]) if "--" in sys.argv else Path("rigging_collisions.json")
    report=audit_scene()
    path.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("RIGGING_COLLISION_AUDIT",json.dumps({k:v for k,v in report.items() if k!="hits"}),flush=True)
    if not report["passed"]: raise RuntimeError("Ropes or sails intersect canvas; see "+str(path))
