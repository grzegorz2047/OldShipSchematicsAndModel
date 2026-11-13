"""Measure deployed canvas above both public deck polygons in an exported GLB.

This checks geometry (including wind morph extremes), not stability or sail loads.
Sampling is conservative: even projected areas occupied by deck equipment count.
"""
from pathlib import Path
import hashlib
import json
import sys

import numpy as np


class DeckEnvelope:
    def __init__(self, layout):
        self.surfaces=[]
        for surface in layout["surfaces"]:
            if surface["name"] not in ("main_deck", "quarterdeck"):
                continue
            polygon=np.asarray(surface["polygon_x_s"],dtype=float)
            # Both reference deck outlines are mirror symmetric around x=0.
            boundary={}
            for x,s in polygon:
                if x>=0:
                    boundary[s]=max(boundary.get(s,0),x)
            edge=np.array(sorted(boundary.items()))
            centre=np.array(surface["height"]["centreline_s_z"])
            self.surfaces.append((edge,centre,1.7 if surface["name"]=="quarterdeck" else 0))

    def heights(self, x, s):
        x,s=np.broadcast_arrays(np.asarray(x,dtype=float),np.asarray(s,dtype=float))
        result=np.full(x.shape,-np.inf)
        for edge,centre,offset in self.surfaces:
            width=np.interp(s,edge[:,0],edge[:,1])
            inside=(s>=edge[0,0])&(s<=edge[-1,0])&(np.abs(x)<=width)
            height=np.interp(s,centre[:,0],centre[:,1])+offset-.120*(x/3.80)**2
            result=np.where(inside,np.maximum(result,height),result)
        return result

    def required_height(self, x, s, clearance=2.25):
        height=float(self.heights(x,s))
        return height+clearance if np.isfinite(height) else -float("inf")


def node_worlds(g):
    parents={child:i for i,n in enumerate(g["nodes"]) for child in n.get("children",[])}
    cache={}
    def world(index):
        if index in cache:
            return cache[index]
        node=g["nodes"][index]
        if "matrix" in node:
            local=np.array(node["matrix"]).reshape((4,4),order="F")
        else:
            x,y,z,w=node.get("rotation",[0,0,0,1])
            r=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                        [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                        [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
            local=np.eye(4)
            local[:3,:3]=r@np.diag(node.get("scale",[1,1,1]))
            local[:3,3]=node.get("translation",[0,0,0])
        cache[index]=(world(parents[index]) if index in parents else np.eye(4))@local
        return cache[index]
    return [world(i) for i in range(len(g["nodes"]))]


def inspect_glb(path, layout, required=2.2):
    from validate_asset import read_glb, accessor
    g,b=read_glb(Path(path))
    deck=DeckEnvelope(layout)
    worlds=node_worlds(g)
    # Five subdivisions of every actual triangle, approximately 0.1–0.2 m
    # between samples at the authored sail mesh resolution.
    bary=np.array([(i/5,j/5,1-(i+j)/5) for i in range(6) for j in range(6-i)])
    result={"source_glb_sha256":hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            "required_clearance_m":required,"walker_height_m":layout["walker"]["height_m"],
            "scope":"canvas above main deck and quarterdeck; equipment footprints included; wind frames 0/24/72", "sails":{}}
    for index,node in enumerate(g["nodes"]):
        if not node.get("name","").endswith("_set"):
            continue
        minimum=float("inf"); below=0; area=0.; tested=0
        for primitive in g["meshes"][node["mesh"]]["primitives"]:
            positions=np.array(accessor(g,b,primitive["attributes"]["POSITION"]))
            indices=np.array(accessor(g,b,primitive["indices"]),dtype=int).ravel().reshape((-1,3))
            targets=[np.array(accessor(g,b,t["POSITION"])) for t in primitive.get("targets",[])]
            for state,weights in enumerate(((0,0),(.9,.05),(.05,.9))):
                verts=positions.copy()
                for weight,target in zip(weights,targets): verts+=weight*target
                verts=verts@worlds[index][:3,:3].T+worlds[index][:3,3]
                triangles=verts[indices]
                if state==0:
                    area+=float(np.linalg.norm(np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]),axis=1).sum()/2)
                samples=np.einsum("ij,tjk->tik",bary,triangles).reshape((-1,3))
                # glTF (x,y,z) == ship (x,height,s).
                floor=deck.heights(samples[:,0],samples[:,2])
                covered=np.isfinite(floor)
                if covered.any():
                    clearance=samples[covered,1]-floor[covered]
                    minimum=min(minimum,float(clearance.min()))
                    below+=int((clearance<required-.005).sum())
                    tested+=int(covered.sum())
        result["sails"][node["name"]]={"minimum_clearance_m":round(minimum,3) if np.isfinite(minimum) else None,
            "samples_below_clearance":below,"samples_over_decks":tested,"cloth_area_m2":round(area,2)}
    result["minimum_clearance_m"]=min(s["minimum_clearance_m"] for s in result["sails"].values() if s["minimum_clearance_m"] is not None)
    result["cloth_area_m2"]=round(sum(s["cloth_area_m2"] for s in result["sails"].values()),2)
    result["passed"]=not any(s["samples_below_clearance"] for s in result["sails"].values())
    return result


if __name__=="__main__":
    folder=Path(sys.argv[1] if len(sys.argv)>1 else "build/game_ship")
    report=inspect_glb(folder/"snow_sailing.glb",json.loads((folder/"data/deck-layout.json").read_text()))
    (folder/"deck_clearance.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if report["passed"] else 1)
