"""GLB structural inspection without Blender or extra Python packages."""

import json, struct, math
from pathlib import Path


def read_glb(path):
    raw = path.read_bytes()
    magic, version, length = struct.unpack_from("<III", raw)
    assert (magic, version, length) == (0x46546C67, 2, len(raw)), path
    chunks = {}
    offset = 12
    while offset < len(raw):
        n, kind = struct.unpack_from("<II", raw, offset)
        offset += 8
        assert n % 4 == 0 and offset + n <= len(raw), path
        chunks[kind] = raw[offset : offset + n]
        offset += n
    return json.loads(chunks[0x4E4F534A]), chunks[0x004E4942]


def accessor(g, b, index):
    a = g["accessors"][index]
    code = {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}[
        a["componentType"]
    ]
    size = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[a["type"]]
    fmt = "<" + code * size
    if "bufferView" in a:
        v = g["bufferViews"][a["bufferView"]]
        stride = v.get("byteStride", struct.calcsize(fmt))
        start = v.get("byteOffset", 0) + a.get("byteOffset", 0)
        out = [
            struct.unpack_from(fmt, b, start + i * stride) for i in range(a["count"])
        ]
    else:
        out = [(0,) * size for _ in range(a["count"])]
    # Blender uses sparse accessors for the cloth's pinned (zero-delta) vertices.
    if "sparse" in a:
        sparse = a["sparse"]
        indices = sparse["indices"]
        vals = sparse["values"]
        iv = g["bufferViews"][indices["bufferView"]]
        vv = g["bufferViews"][vals["bufferView"]]
        ifmt = "<" + {5121: "B", 5123: "H", 5125: "I"}[indices["componentType"]]
        io = iv.get("byteOffset", 0) + indices.get("byteOffset", 0)
        vo = vv.get("byteOffset", 0) + vals.get("byteOffset", 0)
        for i in range(sparse["count"]):
            target = struct.unpack_from(ifmt, b, io + i * struct.calcsize(ifmt))[0]
            assert 0 <= target < len(out)
            out[target] = struct.unpack_from(fmt, b, vo + i * struct.calcsize(fmt))
    return out


def validate(path):
    g, b = read_glb(path)
    assert all("uri" not in x for x in g.get("buffers", [])), "external buffer"
    assert all("uri" not in x for x in g.get("images", [])), "external image"
    assert g["buffers"][0]["byteLength"] <= len(b)
    for view in g.get("bufferViews", []):
        assert view.get("byteOffset", 0) + view["byteLength"] <= len(b)
    for node in g.get("nodes", []):
        assert all(0 <= c < len(g["nodes"]) for c in node.get("children", []))
        if "mesh" in node:
            assert 0 <= node["mesh"] < len(g["meshes"])
    tris = 0
    for mesh in g["meshes"]:
        for primitive in mesh["primitives"]:
            assert primitive.get("mode", 4) == 4
            count = g["accessors"][primitive["attributes"]["POSITION"]]["count"]
            positions = accessor(g, b, primitive["attributes"]["POSITION"])
            assert all(
                math.isfinite(v) for p in positions for v in p
            ), "non-finite position"
            indices = accessor(g, b, primitive["indices"])
            assert len(indices) % 3 == 0 and all(
                0 <= i[0] < count for i in indices
            ), "invalid index"
            tris += len(indices) // 3
            for target in primitive.get("targets", []):
                assert g["accessors"][target["POSITION"]]["count"] == count
    # Guns share mesh data. Count rendered instances, not just unique mesh buffers.
    mesh_tris = [
        sum(g["accessors"][p["indices"]]["count"] // 3 for p in m["primitives"])
        for m in g["meshes"]
    ]
    tris = sum(mesh_tris[n["mesh"]] for n in g["nodes"] if "mesh" in n)
    return g, b, tris
