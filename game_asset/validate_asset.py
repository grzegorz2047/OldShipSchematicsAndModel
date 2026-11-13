"""Check the shipped GLBs without Blender or external packages.

python game_asset/validate_asset.py build/game_ship
Checks embedded resources, mesh/index references, triangles, all sail morphs,
animation duration, wheel-only variant and the presence of separate collisions.
"""
import json
from pathlib import Path
import math
import struct
import sys


def read_glb(path):
    raw=path.read_bytes()
    magic,version,length=struct.unpack_from("<III",raw)
    assert (magic,version,length)==(0x46546C67,2,len(raw)), path
    chunks={}; offset=12
    while offset<len(raw):
        n,kind=struct.unpack_from("<II",raw,offset); offset+=8
        assert n%4==0 and offset+n<=len(raw), path
        chunks[kind]=raw[offset:offset+n]; offset+=n
    return json.loads(chunks[0x4E4F534A]),chunks[0x004E4942]


def accessor(g,b,index):
    a=g["accessors"][index]
    code={5120:"b",5121:"B",5122:"h",5123:"H",5125:"I",5126:"f"}[a["componentType"]]
    size={"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4,"MAT4":16}[a["type"]]
    fmt="<"+code*size
    if "bufferView" in a:
        v=g["bufferViews"][a["bufferView"]]
        stride=v.get("byteStride",struct.calcsize(fmt))
        start=v.get("byteOffset",0)+a.get("byteOffset",0)
        out=[struct.unpack_from(fmt,b,start+i*stride) for i in range(a["count"])]
    else:
        out=[(0,)*size for _ in range(a["count"])]
    # Blender uses sparse accessors for the cloth's pinned (zero-delta) vertices.
    if "sparse" in a:
        sparse=a["sparse"]; indices=sparse["indices"]; vals=sparse["values"]
        iv=g["bufferViews"][indices["bufferView"]]; vv=g["bufferViews"][vals["bufferView"]]
        ifmt="<"+{5121:"B",5123:"H",5125:"I"}[indices["componentType"]]
        io=iv.get("byteOffset",0)+indices.get("byteOffset",0)
        vo=vv.get("byteOffset",0)+vals.get("byteOffset",0)
        for i in range(sparse["count"]):
            target=struct.unpack_from(ifmt,b,io+i*struct.calcsize(ifmt))[0]
            assert 0<=target<len(out)
            out[target]=struct.unpack_from(fmt,b,vo+i*struct.calcsize(fmt))
    return out


def validate(path):
    g,b=read_glb(path)
    assert all("uri" not in x for x in g.get("buffers",[])), "external buffer"
    assert all("uri" not in x for x in g.get("images",[])), "external image"
    assert g["buffers"][0]["byteLength"]<=len(b)
    for view in g.get("bufferViews",[]):
        assert view.get("byteOffset",0)+view["byteLength"]<=len(b)
    for node in g.get("nodes",[]):
        assert all(0<=c<len(g["nodes"]) for c in node.get("children",[]))
        if "mesh" in node: assert 0<=node["mesh"]<len(g["meshes"])
    tris=0
    for mesh in g["meshes"]:
        for primitive in mesh["primitives"]:
            assert primitive.get("mode",4)==4
            count=g["accessors"][primitive["attributes"]["POSITION"]]["count"]
            positions=accessor(g,b,primitive["attributes"]["POSITION"])
            assert all(math.isfinite(v) for p in positions for v in p), "non-finite position"
            indices=accessor(g,b,primitive["indices"])
            assert len(indices)%3==0 and all(0<=i[0]<count for i in indices), "invalid index"
            tris+=len(indices)//3
            for target in primitive.get("targets",[]):
                assert g["accessors"][target["POSITION"]]["count"]==count
    # Guns share mesh data. Count rendered instances, not just unique mesh buffers.
    mesh_tris=[sum(g["accessors"][p["indices"]]["count"]//3 for p in m["primitives"]) for m in g["meshes"]]
    tris=sum(mesh_tris[n["mesh"]] for n in g["nodes"] if "mesh" in n)
    return g,b,tris


def main(folder):
    folder=Path(folder)
    manifest=json.loads((folder/"asset_manifest.json").read_text())
    report={}
    for level,filename in (("lod0","snow_sailing.glb"),("lod1","snow_sailing_lod1.glb"),("lod2","snow_sailing_lod2.glb")):
        g,b,tris=validate(folder/filename)
        assert tris==manifest["triangles"][level], (level,tris)
        report[level]={"triangles":tris,"bytes":(folder/filename).stat().st_size,"nodes":len(g["nodes"])}
        assert not g.get("cameras") and not g.get("extensions",{}).get("KHR_lights_punctual")
        assert not any(n.get("name","").startswith("preview_") for n in g["nodes"])
        if level!="lod0":
            assert not g.get("animations"), "LOD must be a static pose"
            continue
        nodes={n["name"]:n for n in g["nodes"]}
        assert not any(n.get("extras",{}).get("variant")=="deck_tiller_variant" for n in g["nodes"])
        assert "steering_wheel" in nodes and "rudder" in nodes
        assert len([n for n in nodes if n.startswith("gun_port_") and n.removeprefix("gun_port_").isdigit()])==5
        assert len([n for n in nodes if n.startswith("gun_starboard_") and n.removeprefix("gun_starboard_").isdigit()])==5
        sails=[n for n in g["nodes"] if n.get("name","").endswith("_set")]
        assert len(sails)==12
        for n in sails:
            mesh=g["meshes"][n["mesh"]]
            assert mesh["extras"]["targetNames"]==["wind_port","wind_starboard"]
            for p in mesh["primitives"]:
                assert len(p["targets"])==2
                assert g["materials"][p["material"]].get("doubleSided"), n["name"]
                uv=accessor(g,b,p["attributes"]["TEXCOORD_0"])
                triangular=any(token in n["name"] for token in ("jib_","staysail_"))
                for target in p["targets"]:
                    deltas=accessor(g,b,target["POSITION"])
                    assert all(math.isfinite(v) and abs(v)<.11 for d in deltas for v in d)
                    for (u,v),delta in zip(uv,deltas):
                        # glTF flips V compared with Blender UVs; edge tests are invariant.
                        edge=min(abs(u),abs(1-u),abs(v),abs(1-v))<1e-6
                        if triangular:
                            edge=min(abs(u),abs(1-v),abs(u-v))<1e-6
                        if edge:
                            assert max(abs(x) for x in delta)<1e-5, "unpinned sail edge"
        animations=g.get("animations",[])
        assert len(animations)==1 and len(animations[0]["channels"])==12
        duration=max(max(t[0] for t in accessor(g,b,s["input"])) for s in animations[0]["samplers"])
        assert abs(duration-4)<.001, duration
        # Morph channels close exactly at the ends of the four-second loop.
        for sampler in animations[0]["samplers"]:
            out=accessor(g,b,sampler["output"])
            assert out[:2]==out[-2:]
        report["sails"]=12; report["animation_seconds"]=duration
        report["stations"]=sum(n.startswith("station_") for n in nodes)
    assert report["lod0"]["triangles"]>report["lod1"]["triangles"]>report["lod2"]["triangles"]
    cg,_,_=validate(folder/"snow_collision.glb")
    report["collision_meshes"]=sum("mesh" in n for n in cg["nodes"])
    assert report["collision_meshes"]==36
    clearance=json.loads((folder/"deck_clearance.json").read_text())
    assert clearance["passed"] and clearance["minimum_clearance_m"]>=2.2
    report["canvas_minimum_deck_clearance_m"]=clearance["minimum_clearance_m"]
    report["cloth_area_m2"]=clearance["cloth_area_m2"]
    report["result"]="passed"
    (folder/"validation.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    main(sys.argv[1] if len(sys.argv)>1 else "build/game_ship")
