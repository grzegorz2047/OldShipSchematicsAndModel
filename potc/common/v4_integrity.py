"""Portable checks for additive, static PoTC-inspired two-palette ship packages.

The semantic signatures decode the delivered GLBs; they do not certify historical
accuracy, movement, walking, buoyancy or an in-game duel implementation.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import math
import re
import struct
from pathlib import Path, PurePosixPath


PALETTES = ("ochre", "navy")
LEVELS = ("ship", "lod1", "lod2")
VISUAL_FILES = {f"model/{palette}/{level}.glb" for palette in PALETTES for level in LEVELS}
GLB_FILES = VISUAL_FILES | {"model/collision.glb"}
FAMILIES = {"tartane", "yacht", "lugger", "galeoth", "xebec", "barque", "schooner", "caravel", "fleut",
            "pinnace", "brig", "galleon", "corvette", "frigate", "battleship"}
STOCK_GUNS = {"tartane": 0, "yacht": 16, "lugger": 12, "galeoth": 16, "xebec": 20,
              "barque": 16, "schooner": 20, "caravel": 32, "fleut": 20, "pinnace": 24,
              "brig": 24, "galleon": 38, "corvette": 32, "frigate": 44, "battleship": 70}
QUALITY_IDS = {"A4", "B1", "B4", "D1", "D2", "D3", "E1", "E2", "F6", "F7", "F8",
               "G2", "G3", "G4", "G5", "H1", "H2", "H4", "H6", "no_missing_uv"}
GATE_IDS = {"contract", "geometry", "quality", "rig", "collision", "color_variants", "source_parity",
            "render_parity", "provenance", "negative_controls", "type_identity"}
NA_IDS = {"walking", "navigation", "controllers", "movement_ranges", "historical_exactness"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha(value):
    return hashlib.sha256(value).hexdigest()


def digest(path):
    return sha(Path(path).read_bytes())


def relative_path(value):
    require(isinstance(value, str) and bool(value), "Missing relative asset path")
    path = PurePosixPath(value)
    require(not path.is_absolute() and ".." not in path.parts and chr(92) not in value
            and ":" not in value and path.as_posix() == value, "Noncanonical asset path: " + value)
    return value


def valid_digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_spec(spec):
    require(isinstance(spec, dict) and type(spec.get("schema")) is int and spec["schema"] == 4,
            "PoTC spec schema must be exactly 4")
    require(spec.get("family") in FAMILIES and spec.get("id") == spec["family"],
            "Only the fifteen authorized additive ordinary families are allowed; specials and sloop are excluded")
    require(spec.get("asset_type") == "static-duel-ship", "Asset must declare the static duel display scope")
    for name in ("length", "beam", "draft", "freeboard"):
        require(finite_number(spec.get(name)) and spec[name] > 0, "Invalid positive nominal dimension: " + name)
    require(spec["length"] > spec["beam"], "Nominal length must exceed beam")
    require(spec.get("paint_materials") == ["paint_hull", "paint_trim"], "Paint material allowlist must name the two fixed slots")
    palettes = spec.get("palettes")
    require(isinstance(palettes, list) and len(palettes) == 2
            and [entry.get("id") for entry in palettes if isinstance(entry, dict)] == list(PALETTES),
            "Exactly ordered ochre/navy palette definitions are required")
    for entry in palettes:
        for slot in ("paintHull", "paintTrim"):
            color = entry.get(slot)
            require(isinstance(color, list) and len(color) == 4
                    and all(finite_number(v) and 0 <= v <= 1 for v in color) and color[3] == 1,
                    "Paint must be an opaque finite linear RGBA factor: " + slot)
    for slot in ("paintHull", "paintTrim"):
        require(any(abs(a-b) > 1e-6 for a, b in zip(palettes[0][slot][:3], palettes[1][slot][:3])),
                "Palette definitions must differ in each declared paint slot: " + slot)
    hull = spec.get("hull")
    require(isinstance(hull, dict) and isinstance(hull.get("profile"), (str, list, dict)) and bool(hull["profile"]),
            "Missing authored hull profile plan")
    rig = spec.get("rig")
    require(isinstance(rig, dict) and isinstance(rig.get("masts"), list) and bool(rig["masts"])
            and all(isinstance(mast, dict) and isinstance(mast.get("sails"), list) for mast in rig["masts"]),
            "Missing authored mast/sail plan")
    guns = spec.get("guns")
    require(isinstance(guns, dict) and isinstance(guns.get("rows"), list)
            and all(isinstance(row, dict) and type(row.get("pairs")) is int and row["pairs"] >= 0 for row in guns["rows"]),
            "Gun rows must declare nonnegative integer pairs")
    expected_guns = STOCK_GUNS[spec["family"]]
    require(sum(2 * row["pairs"] for row in guns["rows"]) == expected_guns,
            "Authored barrel count differs from the ordinary stock family: " + spec["family"])
    for key in ("cannons", "gun_count"):
        if key in spec:
            require(type(spec[key]) is int and spec[key] == expected_guns, "Declared stock gun count differs: " + key)
    game_source = spec.get("game_source")
    if isinstance(game_source, dict) and "cannons" in game_source:
        require(type(game_source["cannons"]) is int and game_source["cannons"] == expected_guns,
                "Source stock gun count differs from the ordinary family")
    source_paths = spec.get("source_paths", [])
    require(isinstance(source_paths, list) and len(source_paths) == len(set(source_paths)), "Invalid source evidence list")
    for path in source_paths:
        relative_path(path)
    canonical(spec)  # Refuse NaN/Infinity anywhere in the authored contract.
    return {"passed": True, "family": spec["family"], "palettes": list(PALETTES)}


def passing_matrix(matrix, label):
    require(isinstance(matrix, list) and bool(matrix), label + ": missing checklist")
    rows = {}
    for row in matrix:
        require(isinstance(row, dict), label + ": invalid checklist row")
        identifier = row.get("id")
        require(isinstance(identifier, str) and identifier and identifier not in rows,
                label + ": missing or duplicate checklist ID")
        require(type(row.get("required")) is bool, label + ": required must be boolean")
        if row["required"]:
            require(row.get("status") == "PASS", label + ": required gate failed: " + identifier)
        rows[identifier] = row
    require(any(row["required"] for row in rows.values()), label + ": no required checks")
    return rows


def quality_check(value, full_detail, label):
    require(isinstance(value, dict) and value.get("passed") is True, label + ": missing/failing quality audit")
    require(value.get("full_detail_uv_targets") is full_detail, label + ": wrong full-detail UV applicability")
    require(value.get("missing_uv_objects") == [], label + ": UVs are missing or evidence is absent")
    rows = passing_matrix(value.get("matrix"), label + " quality")
    expected = QUALITY_IDS | ({"F1", "F2", "F3", "F4"} if full_detail else set())
    require(set(rows) == expected, label + ": incomplete/unexpected quality gate set")
    for identifier, row in rows.items():
        if identifier == "F8" and row.get("status") == "NA":
            require(row.get("required") is False and row.get("scope") == "not_applicable"
                    and isinstance(row.get("reason"), str) and row["reason"].strip(),
                    label + ": AO applicability needs an explicit reason")
        else:
            require(row.get("required") is True and row.get("status") == "PASS",
                    label + ": mandatory quality gate is not PASS: " + identifier)


def rig_check(value, label):
    require(isinstance(value, dict) and value.get("passed") is True
            and value.get("clearance_passed") is True and value.get("intersections") == [],
            label + ": measured cloth/rig clearance is absent or failed")
    support = value.get("attachment_support")
    ropes = value.get("ropes")
    require(type(ropes) is int and ropes >= 0 and isinstance(support, dict) and support.get("passed") is True
            and support.get("errors") == [] and support.get("ropes") == ropes
            and support.get("endpoints_measured") == 2 * ropes,
            label + ": incomplete/failing actual rope endpoint support")
    endpoints = support.get("endpoints")
    require(isinstance(endpoints, list) and len(endpoints) == 2 * ropes, label + ": endpoint ledger size differs")
    seen = {}
    for row in endpoints:
        require(isinstance(row, dict) and isinstance(row.get("rope"), str) and bool(row["rope"])
                and row.get("endpoint") in ("attachment_start", "attachment_end")
                and isinstance(row.get("target"), str) and bool(row["target"]) and row["target"] != row["rope"],
                label + ": invalid named actual rope/target endpoint")
        seen.setdefault(row["rope"], set())
        require(row["endpoint"] not in seen[row["rope"]], label + ": duplicate measured rope endpoint")
        seen[row["rope"]].add(row["endpoint"])
        point, distance = row.get("path_position_blender_m"), row.get("nearest_target_surface_distance_m")
        require(isinstance(point, list) and len(point) == 3 and all(finite_number(v) for v in point)
                and finite_number(distance) and 0 <= distance <= .05 and row.get("tolerance_m") == .05
                and row.get("passed") is True, label + ": rope endpoint is unsupported or exceeds 5cm")
        rope_distance = row.get("nearest_actual_rope_surface_distance_m")
        cap_alignment = row.get("rope_cap_normal_tangent_alignment")
        require(finite_number(rope_distance) and 0 <= rope_distance <= .005
                and row.get("rope_surface_tolerance_m") == .005
                and finite_number(cap_alignment) and .95 <= cap_alignment <= 1.000001
                and row.get("minimum_cap_normal_alignment") == .95,
                label + ": metadata endpoint is displaced from the actual rope cap or lies on a tube side")
    require(len(seen) == ropes and all(ends == {"attachment_start", "attachment_end"} for ends in seen.values()),
            label + ": both endpoints of every rope must be measured exactly once")
    return seen


_FROZEN = None


def frozen():
    global _FROZEN
    if _FROZEN is None:
        path = Path(__file__).resolve().parents[2] / "sailertales/common/v2_integrity.py"
        require(path.is_file(), "Frozen sailertales/common/v2_integrity.py is required")
        spec = importlib.util.spec_from_file_location("_potc_v4_frozen_v2_integrity", path)
        _FROZEN = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_FROZEN)
    return _FROZEN


def decoded_accessor(doc, binary, index):
    """Decode dense/strided data with frozen v2, then explicitly apply sparse data.

    Integer values remain integers; normalized/component metadata is also hashed.
    Matrix padding follows glTF's four-byte column alignment for byte/short types.
    """
    base = frozen()
    require(type(index) is int and 0 <= index < len(doc.get("accessors", [])), "Invalid accessor reference")
    a = doc["accessors"][index]
    require(type(a.get("count")) is int and a["count"] >= 0, "Invalid accessor count")
    require(a.get("componentType") in base.COMPONENTS and a.get("type") in base.WIDTH,
            "Unsupported accessor component/type")
    fmt, size = base.COMPONENTS[a["componentType"]]
    width = base.WIDTH[a["type"]]
    dimension = int(a["type"][-1]) if a["type"].startswith("MAT") else 1
    column_stride = ((dimension * size + 3) // 4) * 4
    padded = dimension > 1 and column_stride != dimension * size
    offsets = ([column * column_stride + row * size for column in range(dimension)
                for row in range(dimension)] if padded else [i * size for i in range(width)])
    element_size = dimension * column_stride if padded else width * size

    def decode(view_index, offset, count, component_fmt, component_size, component_offsets, element_bytes):
        require(type(view_index) is int and 0 <= view_index < len(doc.get("bufferViews", [])), "Invalid bufferView")
        view = doc["bufferViews"][view_index]
        require(view.get("buffer", 0) == 0, "External accessor buffer")
        start = view.get("byteOffset", 0) + offset
        stride = view.get("byteStride", element_bytes)
        end = start + (count - 1) * stride + element_bytes if count else start
        require(offset >= 0 and stride >= element_bytes and start >= view.get("byteOffset", 0)
                and end <= view.get("byteOffset", 0) + view["byteLength"] and end <= len(binary),
                "Accessor runs outside bufferView")
        unpack = struct.Struct("<" + component_fmt).unpack_from
        return [tuple(unpack(binary, start + row * stride + col)[0] for col in component_offsets)
                for row in range(count)]

    if a["count"] == 0:
        values = []
    elif "bufferView" not in a:
        values = [(0,) * width for _ in range(a["count"])]
    elif not a.get("sparse") and not padded:
        values = base.accessor_values(doc, binary, index)
    else:
        values = decode(a["bufferView"], a.get("byteOffset", 0), a["count"], fmt, size, offsets, element_size)
    sparse = a.get("sparse")
    if sparse:
        count = sparse["count"]
        require(type(count) is int and 0 < count <= a["count"], "Invalid sparse count")
        indices, replacements = sparse["indices"], sparse["values"]
        require(indices.get("componentType") in (5121, 5123, 5125), "Invalid sparse index type")
        index_fmt, index_size = base.COMPONENTS[indices["componentType"]]
        positions = [v[0] for v in decode(indices["bufferView"], indices.get("byteOffset", 0), count,
                                          index_fmt, index_size, [0], index_size)]
        require(positions == sorted(set(positions)) and all(0 <= x < a["count"] for x in positions),
                "Sparse indices are unordered, duplicated or out of range")
        replacement_values = decode(replacements["bufferView"], replacements.get("byteOffset", 0), count,
                                    fmt, size, offsets, element_size)
        for position, replacement in zip(positions, replacement_values):
            values[position] = replacement
    require(all(math.isfinite(x) for row in values for x in row), "Non-finite accessor value")
    return values


def visual_signature(path):
    """Hash decoded geometry/scene semantics and retain inspectable material data.

    Buffer packing and accessor numbering are excluded. Every accessor payload is
    nevertheless fingerprinted, including unused entries, UVs, normals, tangents,
    morph targets, joints, weights, inverse bind matrices and animation samples.
    """
    base = frozen()
    doc, binary = base.read_glb(path)
    require(len(doc.get("buffers", [])) <= 1, "Only one embedded GLB buffer is supported")
    for buffer in doc.get("buffers", []):
        require("uri" not in buffer and buffer.get("byteLength", 0) <= len(binary), "External/truncated buffer")
    for view in doc.get("bufferViews", []):
        require(view.get("buffer", 0) == 0 and view.get("byteOffset", 0) >= 0
                and view.get("byteOffset", 0) + view["byteLength"] <= len(binary), "Invalid bufferView range")
    accessors = []
    for index, accessor in enumerate(doc.get("accessors", [])):
        values = decoded_accessor(doc, binary, index)
        metadata = {key: value for key, value in accessor.items()
                    if key not in ("bufferView", "byteOffset", "sparse")}
        accessors.append({"metadata": metadata, "values_sha256": sha(canonical(values))})

    def acc(index):
        require(type(index) is int and 0 <= index < len(accessors), "Invalid accessor reference")
        return accessors[index]

    images = []
    for image in doc.get("images", []):
        raw = base.image_bytes(doc, binary, image)
        require(raw, "Empty embedded image")
        base.image_size(raw)
        images.append({"sha256": sha(raw), **{key: value for key, value in image.items()
                                               if key not in ("bufferView", "uri")}})

    def texture(index):
        require(type(index) is int and 0 <= index < len(doc.get("textures", [])), "Invalid texture reference")
        item = copy.deepcopy(doc["textures"][index])
        if "source" in item:
            source = item["source"]
            require(type(source) is int and 0 <= source < len(images), "Invalid image reference")
            item["source"] = images[source]
        if "sampler" in item:
            sampler = item["sampler"]
            require(type(sampler) is int and 0 <= sampler < len(doc.get("samplers", [])), "Invalid sampler")
            item["sampler"] = doc["samplers"][sampler]
        return item

    def material_value(value, key=""):
        if isinstance(value, dict):
            result = {k: material_value(v, k) for k, v in value.items()}
            if key.endswith("Texture") and "index" in result:
                result["index"] = texture(value["index"])
            return result
        if isinstance(value, list):
            return [material_value(v) for v in value]
        return value

    materials = {}
    material_names = []
    for material in doc.get("materials", []):
        name = material.get("name")
        require(isinstance(name, str) and name and name not in materials, "Material semantic names must be unique")
        materials[name] = material_value(material)
        material_names.append(name)
    meshes = []
    assigned = set()
    triangles = 0
    for mesh in doc.get("meshes", []):
        item = copy.deepcopy(mesh)
        for primitive in item.get("primitives", []):
            attributes = primitive.get("attributes", {})
            require("POSITION" in attributes, "Visual primitive has no POSITION")
            count = acc(attributes["POSITION"])["metadata"]["count"]
            require(all(acc(i)["metadata"]["count"] == count for i in attributes.values()), "Attribute count mismatch")
            primitive["attributes"] = {key: acc(index) for key, index in attributes.items()}
            for target in primitive.get("targets", []):
                require(all(acc(i)["metadata"]["count"] == count for i in target.values()), "Morph count mismatch")
            primitive["targets"] = [{key: acc(index) for key, index in target.items()}
                                    for target in primitive.get("targets", [])]
            if "indices" in primitive:
                index = primitive["indices"]
                index_values = decoded_accessor(doc, binary, index)
                require(doc["accessors"][index]["type"] == "SCALAR"
                        and all(type(v[0]) is int and 0 <= v[0] < count for v in index_values), "Invalid primitive indices")
                count = len(index_values)
                primitive["indices"] = acc(index)
            if primitive.get("mode", 4) == 4:
                require(count % 3 == 0, "Triangle index count is not divisible by three")
                triangles += count // 3
            if "material" in primitive:
                index = primitive["material"]
                require(type(index) is int and 0 <= index < len(material_names), "Invalid material assignment")
                primitive["material"] = material_names[index]
                assigned.add(material_names[index])
        meshes.append(item)
    skins = copy.deepcopy(doc.get("skins", []))
    for skin in skins:
        if "inverseBindMatrices" in skin:
            skin["inverseBindMatrices"] = acc(skin["inverseBindMatrices"])
    animations = copy.deepcopy(doc.get("animations", []))
    for animation in animations:
        for sampler in animation.get("samplers", []):
            sampler["input"], sampler["output"] = acc(sampler["input"]), acc(sampler["output"])
    nodes = doc.get("nodes", [])
    for node in nodes:
        if "mesh" in node:
            require(type(node["mesh"]) is int and 0 <= node["mesh"] < len(meshes), "Invalid node mesh")
        if "skin" in node:
            require(type(node["skin"]) is int and 0 <= node["skin"] < len(skins), "Invalid node skin")
        for child in node.get("children", []):
            require(type(child) is int and 0 <= child < len(nodes), "Invalid node child")
    visited, active = set(), set()

    def visit(index):
        require(index not in active, "Cyclic node hierarchy")
        if index not in visited:
            active.add(index)
            for child in nodes[index].get("children", []):
                visit(child)
            active.remove(index)
            visited.add(index)

    for index in range(len(nodes)):
        visit(index)
    for scene in doc.get("scenes", []):
        require(all(type(i) is int and 0 <= i < len(nodes) for i in scene.get("nodes", [])), "Invalid scene membership")
    if "scene" in doc:
        require(type(doc["scene"]) is int and 0 <= doc["scene"] < len(doc.get("scenes", [])), "Invalid default scene")
    for skin in skins:
        refs = skin.get("joints", []) + ([skin["skeleton"]] if "skeleton" in skin else [])
        require(bool(skin.get("joints")) and all(type(i) is int and 0 <= i < len(nodes) for i in refs), "Invalid skin joint/skeleton")
    for animation in animations:
        for channel in animation.get("channels", []):
            index = channel.get("sampler")
            target = channel.get("target", {})
            require(type(index) is int and 0 <= index < len(animation.get("samplers", [])), "Invalid animation sampler")
            require(type(target.get("node")) is int and 0 <= target["node"] < len(nodes)
                    and target.get("path") in ("translation", "rotation", "scale", "weights"), "Invalid animation target")
    geometry = {"asset": {k: v for k, v in doc.get("asset", {}).items() if k != "generator"},
                "nodes": doc.get("nodes", []), "meshes": meshes, "skins": skins,
                "animations": animations, "scenes": doc.get("scenes", []), "scene": doc.get("scene"),
                "extensions": doc.get("extensions", {}), "extras": doc.get("extras", {}),
                "extensionsUsed": sorted(doc.get("extensionsUsed", [])),
                "extensionsRequired": sorted(doc.get("extensionsRequired", [])),
                "all_accessor_payloads": sorted(sha(canonical(a)) for a in accessors)}
    # Node mesh/skin references, transforms, children, weights, names and all extras
    # stay in the geometry payload verbatim; palette exports retain stable order.
    return {"signature_schema": 1, "sha256": digest(path), "geometry_sha256": sha(canonical(geometry)),
            "materials": materials, "images": images, "textures": [texture(i) for i in range(len(doc.get("textures", [])))],
            "samplers": doc.get("samplers", []), "assigned_materials": sorted(assigned),
            "triangles": triangles, "accessors": len(accessors), "nodes": len(doc.get("nodes", [])),
            "meshes": len(meshes), "animations": len(animations)}


def compare_variants(first, second, paint_materials):
    """Compare actual semantic signatures, permitting RGB factors on named paints.

    This proves material payload differences; render parity is a separate audit.
    """
    a = visual_signature(first) if isinstance(first, (str, Path)) else first
    b = visual_signature(second) if isinstance(second, (str, Path)) else second
    errors = []
    paints = list(paint_materials)
    if not paints or len(set(paints)) != len(paints):
        errors.append("Paint allowlist must contain distinct semantic material names")
    if a.get("geometry_sha256") != b.get("geometry_sha256"):
        errors.append("Decoded geometry/scene/rig/assignment signatures differ")
    if a.get("sha256") == b.get("sha256"):
        errors.append("Palette GLBs are byte-identical")
    for key in ("images", "textures", "samplers", "assigned_materials"):
        if a.get(key) != b.get(key):
            errors.append("Palette invariant differs: " + key)
    ma, mb = a.get("materials", {}), b.get("materials", {})
    if set(ma) != set(mb):
        errors.append("Semantic material sets differ")
    changed = {}
    for name in sorted(set(ma) | set(mb)):
        if name not in ma or name not in mb:
            continue
        if name not in paints:
            if ma[name] != mb[name]:
                errors.append("Natural/unlisted material changed: " + name)
            continue
        left, right = copy.deepcopy(ma[name]), copy.deepcopy(mb[name])
        factors = []
        for material in (left, right):
            factor = material.setdefault("pbrMetallicRoughness", {}).get("baseColorFactor", [1, 1, 1, 1])
            if (not isinstance(factor, list) or len(factor) != 4 or
                    any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in factor)):
                errors.append("Invalid linear RGBA paint factor: " + name)
                factor = [1, 1, 1, 1]
            factors.append(factor)
            material["pbrMetallicRoughness"]["baseColorFactor"] = [0, 0, 0, factor[3]]
        if left != right:
            errors.append("Paint changed beyond RGB factor: " + name)
        if name not in a.get("assigned_materials", []) or name not in b.get("assigned_materials", []):
            errors.append("Paint is not assigned to actual geometry: " + name)
        if all(abs(x-y) <= 1e-6 for x, y in zip(factors[0][:3], factors[1][:3])):
            errors.append("Declared paint slot has no actual RGB difference: " + name)
        else:
            changed[name] = {"first": factors[0], "second": factors[1]}
    for name in paints:
        if name not in ma or name not in mb:
            errors.append("Declared paint material is missing: " + name)
    return {"passed": not errors, "geometry_sha256": a.get("geometry_sha256"),
            "first_sha256": a.get("sha256"), "second_sha256": b.get("sha256"),
            "paint_materials": paints, "changed_paints": changed, "errors": errors}


def paint_names(signature, level):
    names = set(signature.get("materials", {}))
    plain = ["paint_hull", "paint_trim"]
    prefixed = [f"lod{level}_" + name for name in plain] if level else plain
    selected = plain if set(plain).issubset(names) else prefixed
    require(set(selected).issubset(names), "Both exact semantic paint materials must exist")
    return selected


def validate_contract(report, spec, review, files):
    """Pure schema and measured-report/file binding checks (no Blender required)."""
    validate_spec(spec)
    canonical(report)
    canonical(review)
    require(isinstance(report, dict) and report.get("schema") == 4 and report.get("potc_schema") == 1
            and type(report.get("schema")) is int and type(report.get("potc_schema")) is int,
            "Missing exact v4/potc-schema-1 report")
    require(report.get("passed") is True and report.get("vessel") == spec["id"]
            and report.get("family") == spec["family"], "Report failed or differs from the current family contract")
    rows = passing_matrix(report.get("matrix"), "v4 acceptance")
    require(set(rows) == GATE_IDS | NA_IDS, "Incomplete/unexpected v4 acceptance gate set")
    checks = report.get("checks")
    require(isinstance(checks, dict) and set(checks) == GATE_IDS, "Incomplete measured acceptance evidence")
    for name in GATE_IDS:
        require(rows[name].get("required") is True and rows[name].get("status") == "PASS"
                and isinstance(checks[name], dict) and checks[name].get("passed") is True
                and rows[name].get("evidence") == checks[name], "Required evidence gate is missing/failing: " + name)
    for name in NA_IDS:
        row = rows[name]
        require(row.get("required") is False and row.get("status") == "NA"
                and row.get("scope") == "not_applicable" and isinstance(row.get("reason"), str)
                and bool(row["reason"].strip()), "Static exclusion must be explicit and justified: " + name)
    contract = checks["contract"]
    require(contract.get("ordinary_family") == spec["family"] and contract.get("schema") == 4
            and contract.get("static_scope") is True, "Measured ordinary-family contract differs from the spec")
    require(isinstance(files, dict) and all(relative_path(path) and valid_digest(value) for path, value in files.items()),
            "Invalid actual package inventory")
    inventory = report.get("sha256")
    require(isinstance(inventory, dict) and inventory == files, "SHA inventory must cover every shipped package file exactly")
    glbs = {path for path in files if path.lower().endswith(".glb")}
    require(glbs == GLB_FILES, "Missing or unregistered GLBs: " + str(glbs ^ GLB_FILES))
    required_files = GLB_FILES | {"spec.json", "design.json", "export-review.json"}
    for palette in PALETTES:
        required_files.add(f"model/{palette}/source.blend")
        for view in ("hero", "detail"):
            required_files.update((f"previews/{palette}/{view}.png", f"review/{palette}/source_{view}.png"))
    require(required_files.issubset(files), "Incomplete two-palette asset package: " + str(required_files - set(files)))
    audited = report.get("glb_files")
    require(isinstance(audited, dict) and set(audited) == GLB_FILES, "Every delivered GLB needs one audit row")
    for path in sorted(GLB_FILES):
        row = audited[path]
        require(isinstance(row, dict) and row.get("passed") is True and row.get("sha256") == files[path]
                and isinstance(row.get("structure"), dict) and row["structure"].get("passed") is True,
                "Missing/failing/stale GLB audit: " + path)
        require(type(row.get("imported_triangles")) is int and row["imported_triangles"] > 0
                and row["structure"].get("triangles") == row["imported_triangles"], "Triangle count binding differs: " + path)
        if path == "model/collision.glb":
            require(row.get("role") == "collision" and isinstance(row.get("sanity"), dict)
                    and row["sanity"].get("passed") is True
                    and row["sanity"].get("topology", {}).get("passed") is True
                    and row["sanity"] == checks["collision"], "Collision clone/topology acceptance is missing")
            collision = row["sanity"]
            targets, matching = collision.get("visual_nodes"), collision.get("matching")
            require(isinstance(targets, list) and targets and len(targets) == len(set(targets))
                    and isinstance(matching, list) and len(matching) == len(targets)
                    and {item.get("visual_source") for item in matching} == set(targets), "Incomplete collision/source node binding")
            for item in matching:
                require(item.get("exact_world_triangle_match") is True
                        and item.get("collider_geometry") == item.get("visual_geometry")
                        and valid_digest(item.get("visual_geometry", {}).get("sha256")), "Collision differs from its source surface")
            continue
        palette, filename = PurePosixPath(path).parts[1:]
        level = LEVELS.index(filename[:-4])
        signature = row.get("visual_signature")
        require(row.get("role") == "visual" and row.get("palette") == palette and row.get("level") == level
                and isinstance(signature, dict) and signature.get("signature_schema") == 1
                and signature.get("sha256") == files[path] and valid_digest(signature.get("geometry_sha256"))
                and signature.get("geometry_sha256") == row.get("geometry_sha256")
                and signature.get("triangles") == row["imported_triangles"], "Visual signature/role/count binding differs: " + path)
        if palette == PALETTES[0]:
            quality_check(row.get("quality"), level == 0, path)
            quality = row["quality"]
            for evidence in ("topology", "penetration", "materials", "rig"):
                require(isinstance(quality.get(evidence), dict) and quality[evidence].get("passed") is True,
                        "Missing/failing measured visual evidence: " + path + " " + evidence)
            rig_check(quality["rig"], path)
        else:
            quality = row.get("quality", {})
            require(quality.get("passed") is True and quality.get("geometry_and_material_invariants") is True
                    and quality.get("reused_from") == f"model/{PALETTES[0]}/{filename}", "Invalid paired quality reuse: " + path)
    pairs = report.get("palette_pairs")
    require(isinstance(pairs, dict) and set(pairs) == set(LEVELS)
            and checks["color_variants"].get("levels") == pairs, "Missing/stale palette pair gates")
    for level_index, level in enumerate(LEVELS):
        a, b = [audited[f"model/{palette}/{level}.glb"]["visual_signature"] for palette in PALETTES]
        actual = compare_variants(a, b, paint_names(a, level_index))
        require(actual["passed"] and pairs[level] == actual, "Material/geometry palette pair is invalid or stale: " + level)
        for palette, signature in zip(PALETTES, (a, b)):
            definition = next(entry for entry in spec["palettes"] if entry["id"] == palette)
            for name, slot in zip(paint_names(signature, level_index), ("paintHull", "paintTrim")):
                material = signature["materials"][name]
                require(material.get("extras", {}).get("palette_slot") == slot,
                        "Paint material lost its explicit palette-slot semantic: " + name)
                actual_factor = material.get("pbrMetallicRoughness", {}).get("baseColorFactor", [1, 1, 1, 1])
                require(len(actual_factor) == 4 and all(abs(a-b) <= 1e-6 for a, b in zip(actual_factor, definition[slot])),
                        "Current spec palette and actual embedded paint factor differ: " + palette + " " + name)
    counts = [audited[f"model/ochre/{level}.glb"]["imported_triangles"] for level in LEVELS]
    lods = checks["geometry"].get("lods", {})
    require(lods.get("passed") is True and lods.get("triangle_counts") == counts
            and counts[0] > counts[1] > counts[2] > 0, "Actual LOD triangle counts must decrease strictly")
    require(set(lods.get("bounds", {})) == {"lod1", "lod2"}
            and all(row.get("passed") is True for row in lods["bounds"].values()), "Missing/failing measured LOD bounds continuity")
    source = report.get("source_parity")
    require(isinstance(source, dict) and set(source) == set(PALETTES)
            and checks["source_parity"].get("palettes") == source, "Incomplete source parity evidence")
    for palette in PALETTES:
        row = source[palette]
        expected = audited[f"model/{palette}/ship.glb"]["imported_triangles"]
        require(row.get("passed") is True and row.get("per_node_world_triangle_match") is True
                and row.get("unpacked_used_images") == [] and row.get("source_triangles") == expected
                and row.get("export_triangles") == expected and row.get("export_indexed_triangles") == expected
                and row.get("source_blend_sha256") == files[f"model/{palette}/source.blend"], "Stale/failing source scene parity: " + palette)
        source_nodes, export_nodes = row.get("source_node_geometry"), row.get("export_node_geometry")
        require(isinstance(source_nodes, dict) and bool(source_nodes) and isinstance(export_nodes, dict)
                and set(source_nodes) == set(export_nodes), "Source/export node ledgers differ: " + palette)
        comparisons = row.get("per_node_comparison")
        require(isinstance(comparisons, dict) and set(comparisons) == set(source_nodes)
                and all(item.get("passed") is True for item in comparisons.values()), "Incomplete per-node source parity: " + palette)
        require(sum(item.get("triangles", 0) for item in source_nodes.values()) == expected
                and sum(item.get("triangles", 0) for item in export_nodes.values()) == expected,
                "Source/export node triangle totals differ: " + palette)
        for name, item in comparisons.items():
            distance = item.get("max_bidirectional_vertex_centroid_distance_m")
            require(item.get("triangle_count_match") is True and item.get("tolerance_m") == .00002
                    and finite_number(distance) and 0 <= distance <= .00002
                    and source_nodes[name].get("triangles") == export_nodes[name].get("triangles")
                    and valid_digest(source_nodes[name].get("sha256")) and valid_digest(export_nodes[name].get("sha256")),
                    "Per-node source geometry/tolerance evidence differs: " + palette + " " + name)
    render = report.get("render_parity")
    require(isinstance(review, dict) and review.get("schema") == 4 and review.get("passed") is True
            and review.get("palettes") == render and isinstance(render, dict) and set(render) == set(PALETTES),
            "Export review/report palette evidence differs")
    thresholds = review.get("thresholds", {})
    require(thresholds == {"brightness_fraction": .10, "maximum_channel_share_difference": .04}, "Render thresholds differ from the accepted contract")
    for palette in PALETTES:
        row = render[palette]
        count = audited[f"model/{palette}/ship.glb"]["imported_triangles"]
        require(row.get("passed") is True and row.get("triangle_match") is True
                and row.get("source_triangles") == count and row.get("export_triangles") == count
                and type(row.get("resolution")) is int and row["resolution"] >= 320, "Invalid actual source/export render review: " + palette)
        inputs = {f"model/{palette}/ship.glb", f"model/{palette}/source.blend"}
        outputs = {f"previews/{palette}/{view}.png" for view in ("hero", "detail")}
        outputs |= {f"review/{palette}/source_{view}.png" for view in ("hero", "detail")}
        require(row.get("sha256") == {p: files[p] for p in inputs}
                and row.get("output_sha256") == {p: files[p] for p in outputs}, "Render inputs/outputs are stale: " + palette)
        views = row.get("views")
        require(isinstance(views, dict) and set(views) == {"hero", "detail"}
                and all(item.get("passed") is True for item in views.values()), "Missing/failing source/export comparison views: " + palette)
        for item in views.values():
            for metric, limit in thresholds.items():
                require(finite_number(item.get(metric)) and 0 <= item[metric] <= limit,
                        "Render metric exceeds its unchanged threshold: " + palette + " " + metric)
    identity = checks["type_identity"]
    require(identity.get("family") == spec["family"] and identity.get("origin_at_zero") is True
            and identity.get("dimensions", {}).get("passed") is True, "Type identity/waterline origin evidence differs")
    plan = spec["rig"]
    expected_counts = {"mast_nodes": len(plan["masts"]),
                       "sail_nodes": sum(len(mast["sails"]) for mast in plan["masts"]) + len(plan.get("jibs", [])),
                       "gun_nodes": STOCK_GUNS[spec["family"]]}
    require(identity.get("expected_plan_counts") == expected_counts, "Measured type counts differ from the current authored/stock contract")
    ledger = identity.get("actual_node_ledger")
    require(isinstance(ledger, dict) and set(ledger) == {"hull_nodes", "mast_nodes", "sail_nodes", "gun_nodes"},
            "Incomplete actual type node ledger")
    for name, nodes in ledger.items():
        require(isinstance(nodes, list) and all(isinstance(node, str) and node for node in nodes)
                and len(nodes) == len(set(nodes)), "Invalid/duplicate actual type ledger: " + name)
        require(len(nodes) == expected_counts[name] if name in expected_counts else bool(nodes),
                "Actual type ledger count differs from the current plan: " + name)
    expected_kinds = {}
    for mast in plan["masts"]:
        for sail in mast["sails"]:
            kind = sail.get("kind")
            require(kind in ("square", "gaff", "lug", "lateen"), "Unsupported authored sail kind")
            expected_kinds[kind] = expected_kinds.get(kind, 0) + 1
    if plan.get("jibs"):
        expected_kinds["jib"] = len(plan["jibs"])
    require(identity.get("expected_sail_kinds") == expected_kinds and identity.get("actual_sail_kinds") == expected_kinds,
            "Actual square/lateen/fore-and-aft/jib plan differs from the current authored contract")
    require(checks["negative_controls"].get("controls"), "Missing meaningful auditor negative controls")
    return {"passed": True, "vessel": spec["id"], "required_checks": len(GATE_IDS),
            "glb_files": len(GLB_FILES), "palette_pairs": len(LEVELS), "package_files": len(files),
            "scope": "Decoded GLB pair invariants and SHA-bound measured reports; static display scope"}


def source_files(root, spec):
    """Recompute the auditor's own-builder/local-import dependency closure."""
    root = Path(root).resolve()
    own = root / "potc" / spec["id"]
    pending = [root / "potc/common/v4_audit.py", root / "potc/common/v4_integrity.py"]
    pending.extend(own.glob("*.py"))
    require((own / "build.py").is_file(), "Missing this family's source builder")
    require((own / "spec.json").is_file(), "Missing this family's authored source spec")
    found = set()
    folders = (root / "potc/common", root / "sailertales/common", root / "blender", root)
    while pending:
        path = pending.pop().resolve()
        if path in found or not path.is_file():
            continue
        require(path.is_relative_to(root), "AST source dependency leaves its root")
        found.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules = ([node.module] if isinstance(node, ast.ImportFrom)
                       else [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
            for module in modules:
                if not module:
                    continue
                resolved = False
                for folder in (path.parent, *folders):
                    candidate = folder / (module.replace(".", "/") + ".py")
                    if candidate.is_file():
                        pending.append(candidate)
                        resolved = True
                require(resolved or not module.startswith("v4_"), "Unresolved required local v4 import: " + module)
    for name in ("spec.json", "design.json"):
        if (own / name).is_file():
            found.add((own / name).resolve())
    for relative in spec.get("source_paths", []):
        path = (root / relative_path(relative)).resolve()
        require(path.is_relative_to(root) and path.is_file(), "Missing/escaping declared source evidence: " + relative)
        found.add(path)
    workflow = root / ".github/workflows/potc-integrity.yml"
    require(workflow.is_file(), "The additive portable CI workflow is required")
    found.add(workflow.resolve())
    return {path.relative_to(root).as_posix(): digest(path) for path in sorted(found)}


def check(asset_dir, source_root=None):
    asset = Path(asset_dir).resolve()
    root = Path(source_root).resolve() if source_root else Path(__file__).resolve().parents[2]

    def read(name):
        return json.loads((asset / name).read_text(encoding="utf-8"))

    spec, report, review = read("spec.json"), read("validation.json"), read("export-review.json")
    files = {}
    for path in sorted(asset.rglob("*")):
        require(path.resolve().is_relative_to(asset), "Asset symlink escapes its package: " + str(path))
        if path.is_file() and path.name != "validation.json" and "__pycache__" not in path.parts and not path.name.endswith(".blend1"):
            files[path.relative_to(asset).as_posix()] = digest(path)
    result = validate_contract(report, spec, review, files)
    actual_sources = source_files(root, spec)
    require(report.get("source_sha256") == actual_sources, "Audited source dependency closure is incomplete or stale")
    required_sources = {"potc/common/v4_audit.py", "potc/common/v4_integrity.py", f"potc/{spec['id']}/build.py", f"potc/{spec['id']}/spec.json",
                        "potc/common/v4_shipkit.py", "potc/common/v4_export.py", "potc/common/v4_rig.py",
                        "sailertales/common/v2_audit.py", "sailertales/common/v2_integrity.py", "sailertales/common/v2_review.py"}
    provenance = report["checks"]["provenance"]
    require(required_sources.issubset(actual_sources) and set(provenance.get("required_sources", [])) == required_sources
            and provenance.get("source_files") == len(actual_sources), "Missing required audit/source provenance")
    for path in sorted(VISUAL_FILES):
        actual = visual_signature(asset / path)
        require(actual == report["glb_files"][path]["visual_signature"], "Recomputed delivered GLB signature differs: " + path)
        if PurePosixPath(path).parts[1] == "ochre":
            doc, _ = frozen().read_glb(asset / path)
            actual_ropes = {node["name"] for node in doc.get("nodes", [])
                            if "mesh" in node and node.get("extras", {}).get("kind") == "rope"}
            supported = rig_check(report["glb_files"][path]["quality"]["rig"], path)
            require(actual_ropes == set(supported), "Endpoint audit does not cover all actual tagged rope meshes: " + path)
    base = frozen()
    for path in sorted(GLB_FILES):
        structural, _, _ = base.inspect_glb(asset / path)
        require(structural.get("passed") is True and structural == report["glb_files"][path]["structure"],
                "Recomputed GLB structure differs: " + path)
    if "navigation.json" in files:
        require(read("navigation.json").get("routes") == [], "Static release must not claim authored walking routes")
    result["source_files"] = len(actual_sources)
    result["actual_visual_signatures_recomputed"] = len(VISUAL_FILES)
    return result


def _contract_fixture(first, second):
    """Synthetic report fixture solely for schema/binding negative controls."""
    spec = {"schema": 4, "id": "lugger", "family": "lugger", "asset_type": "static-duel-ship",
            "length": 12, "beam": 4, "draft": 1, "freeboard": 1,
            "paint_materials": ["paint_hull", "paint_trim"],
            "palettes": [{"id": palette, "paintHull": signature["materials"]["paint_hull"]["pbrMetallicRoughness"]["baseColorFactor"],
                           "paintTrim": signature["materials"]["paint_trim"]["pbrMetallicRoughness"]["baseColorFactor"]}
                          for palette, signature in zip(PALETTES, (first, second))],
            "hull": {"profile": [[-.5, .1, 0, 0], [.5, .1, 0, 0]]}, "rig": {"masts": [{"sails": [{"kind": "square"}]}]},
            "guns": {"rows": [{"pairs": 6}]}}
    paths = GLB_FILES | {"spec.json", "design.json", "export-review.json", "build.py"}
    for palette in PALETTES:
        paths.add(f"model/{palette}/source.blend")
        for view in ("hero", "detail"):
            paths |= {f"previews/{palette}/{view}.png", f"review/{palette}/source_{view}.png"}
    files = {path: sha(path.encode()) for path in paths}
    audited, pairs = {}, {}
    counts = [12, 8, 4]
    for level_index, level in enumerate(LEVELS):
        for palette, original in zip(PALETTES, (first, second)):
            path = f"model/{palette}/{level}.glb"
            signature = copy.deepcopy(original)
            signature.update(sha256=files[path], geometry_sha256=sha(level.encode()), triangles=counts[level_index])
            for name, slot in zip(("paint_hull", "paint_trim"), ("paintHull", "paintTrim")):
                signature["materials"][name]["extras"] = {"palette_slot": slot}
            ids = QUALITY_IDS | ({"F1", "F2", "F3", "F4"} if level_index == 0 else set())
            quality = {"passed": True, "full_detail_uv_targets": level_index == 0, "missing_uv_objects": [],
                       "matrix": [{"id": name, "required": True, "status": "PASS"} for name in sorted(ids)],
                       **{key: {"passed": True} for key in ("topology", "penetration", "materials", "rig")}}
            quality["rig"].update(clearance_passed=True, intersections=[], ropes=1,
                                   attachment_support={"passed": True, "ropes": 1, "endpoints_measured": 2, "errors": [],
                                                       "endpoints": [{"rope": "control_rope", "endpoint": name, "target": "hull",
                                                                      "path_position_blender_m": [0, 0, 0],
                                                                      "nearest_target_surface_distance_m": 0, "tolerance_m": .05,
                                                                      "nearest_actual_rope_surface_distance_m": 0, "rope_surface_tolerance_m": .005,
                                                                      "rope_cap_normal_tangent_alignment": 1, "minimum_cap_normal_alignment": .95,
                                                                      "passed": True}
                                                                     for name in ("attachment_start", "attachment_end")]})
            if palette == "navy":
                quality = {"passed": True, "reused_from": f"model/ochre/{level}.glb", "geometry_and_material_invariants": True}
            audited[path] = {"passed": True, "role": "visual", "palette": palette, "level": level_index,
                             "sha256": files[path], "structure": {"passed": True, "triangles": counts[level_index]},
                             "imported_triangles": counts[level_index], "geometry_sha256": signature["geometry_sha256"],
                             "visual_signature": signature, "quality": quality}
        pairs[level] = compare_variants(audited[f"model/ochre/{level}.glb"]["visual_signature"],
                                       audited[f"model/navy/{level}.glb"]["visual_signature"], ["paint_hull", "paint_trim"])
    geometry = {"triangles": 3, "sha256": sha(b"collision source triangles")}
    collision = {"passed": True, "topology": {"passed": True}, "visual_nodes": ["hull"],
                 "matching": [{"collider": "col_hull", "visual_source": "hull", "exact_world_triangle_match": True,
                                "collider_geometry": geometry, "visual_geometry": geometry}]}
    audited["model/collision.glb"] = {"passed": True, "role": "collision", "sha256": files["model/collision.glb"],
                                     "structure": {"passed": True, "triangles": 3}, "imported_triangles": 3, "sanity": collision}
    source, render = {}, {}
    for palette in PALETTES:
        node_geometry = {"hull": {"triangles": 12, "sha256": sha(b"source fixture")}}
        source[palette] = {"passed": True, "per_node_world_triangle_match": True, "unpacked_used_images": [],
                           "source_triangles": 12, "export_triangles": 12, "export_indexed_triangles": 12,
                           "source_blend_sha256": files[f"model/{palette}/source.blend"],
                           "source_node_geometry": node_geometry, "export_node_geometry": node_geometry,
                           "per_node_comparison": {"hull": {"passed": True, "triangle_count_match": True,
                                                             "max_bidirectional_vertex_centroid_distance_m": 0, "tolerance_m": .00002}}}
        inputs = {f"model/{palette}/ship.glb", f"model/{palette}/source.blend"}
        outputs = {f"previews/{palette}/{view}.png" for view in ("hero", "detail")}
        outputs |= {f"review/{palette}/source_{view}.png" for view in ("hero", "detail")}
        render[palette] = {"passed": True, "triangle_match": True, "source_triangles": 12, "export_triangles": 12,
                           "resolution": 320, "sha256": {path: files[path] for path in inputs},
                           "output_sha256": {path: files[path] for path in outputs},
                           "views": {view: {"passed": True, "brightness_fraction": 0, "maximum_channel_share_difference": 0}
                                     for view in ("hero", "detail")}}
    checks = {name: {"passed": True} for name in GATE_IDS}
    checks["contract"].update(ordinary_family="lugger", schema=4, static_scope=True)
    checks["geometry"]["lods"] = {"passed": True, "triangle_counts": counts,
                                    "bounds": {level: {"passed": True} for level in ("lod1", "lod2")}}
    checks.update(collision=collision, color_variants={"passed": True, "levels": pairs},
                  source_parity={"passed": True, "palettes": source},
                  type_identity={"passed": True, "family": "lugger", "origin_at_zero": True, "dimensions": {"passed": True},
                                 "expected_plan_counts": {"mast_nodes": 1, "sail_nodes": 1, "gun_nodes": 12},
                                 "actual_node_ledger": {"hull_nodes": ["hull"], "mast_nodes": ["main"], "sail_nodes": ["main_square"],
                                                        "gun_nodes": ["barrel_%02d" % i for i in range(12)]},
                                 "expected_sail_kinds": {"square": 1}, "actual_sail_kinds": {"square": 1}},
                  negative_controls={"passed": True, "controls": ["Synthetic contract fixture"]})
    matrix = [{"id": name, "required": True, "status": "PASS", "evidence": checks[name]} for name in sorted(GATE_IDS)]
    matrix.extend({"id": name, "required": False, "status": "NA", "scope": "not_applicable", "reason": "Synthetic static scope"}
                  for name in sorted(NA_IDS))
    report = {"schema": 4, "potc_schema": 1, "vessel": "lugger", "family": "lugger", "passed": True,
              "matrix": matrix, "checks": checks, "glb_files": audited, "palette_pairs": pairs,
              "source_parity": source, "render_parity": render, "sha256": files}
    review = {"schema": 4, "passed": True, "palettes": render,
              "thresholds": {"brightness_fraction": .10, "maximum_channel_share_difference": .04}}
    return report, spec, review, files


def self_test():
    """Small synthetic positive/negative controls, not a real-ship certification."""
    import tempfile
    import zlib

    doc = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 0}], "bufferViews": [], "accessors": [],
           "materials": [{"name": "paint_hull", "pbrMetallicRoughness": {"baseColorFactor": [.5, .2, .05, 1]}},
                         {"name": "paint_trim", "pbrMetallicRoughness": {"baseColorFactor": [.7, .6, .2, 1]}},
                         {"name": "wood", "pbrMetallicRoughness": {"baseColorFactor": [.3, .2, .1, 1]}}],
           "nodes": [{"name": "ship", "mesh": 0, "children": [1], "skin": 0, "extras": {"pivot": [0, 0, 0]}},
                     {"name": "joint", "translation": [0, 0, 0]}],
           "scenes": [{"nodes": [0]}], "scene": 0}
    binary = bytearray()

    def view(data):
        binary.extend(b"\0" * (-len(binary) % 4))
        result = len(doc["bufferViews"])
        doc["bufferViews"].append({"buffer": 0, "byteOffset": len(binary), "byteLength": len(data)})
        binary.extend(data)
        return result

    def accessor(values, kind, component=5126):
        fmt, _ = frozen().COMPONENTS[component]
        width = frozen().WIDTH[kind]
        data = struct.pack("<" + fmt * len(values), *values)
        result = len(doc["accessors"])
        doc["accessors"].append({"bufferView": view(data), "componentType": component,
                                 "count": len(values) // width, "type": kind})
        return result

    def png(rgb):
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(b"\0" + bytes(rgb))) + chunk(b"IEND", b""))

    image_payload = png((120, 80, 40))
    image_view = view(image_payload)
    doc["images"] = [{"name": "natural_wood_albedo", "bufferView": image_view, "mimeType": "image/png"}]
    doc["samplers"] = [{"wrapS": 10497, "wrapT": 10497}]
    doc["textures"] = [{"source": 0, "sampler": 0}]
    for material in doc["materials"]:
        material["pbrMetallicRoughness"]["baseColorTexture"] = {"index": 0, "texCoord": 0}

    pos = accessor([0, 0, 0, 1, 0, 0, 0, 1, 0], "VEC3")
    normal = accessor([0, 0, 1] * 3, "VEC3")
    uv = accessor([0, 0, 1, 0, 0, 1], "VEC2")
    tangent = accessor([1, 0, 0, 1] * 3, "VEC4")
    joints = accessor([0, 0, 0, 0] * 3, "VEC4", 5121)
    weights = accessor([1, 0, 0, 0] * 3, "VEC4")
    indices = accessor([0, 1, 2], "SCALAR", 5123)
    inverse = accessor([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1], "MAT4")
    times = accessor([0, 1], "SCALAR")
    translations = accessor([0, 0, 0, 0, .1, 0], "VEC3")
    sparse_indices, sparse_values = view(bytes([1])), view(struct.pack("<fff", .1, 0, 0))
    morph = len(doc["accessors"])
    doc["accessors"].append({"componentType": 5126, "count": 3, "type": "VEC3",
                             "sparse": {"count": 1, "indices": {"bufferView": sparse_indices, "componentType": 5121},
                                        "values": {"bufferView": sparse_values}}})
    attributes = {"POSITION": pos, "NORMAL": normal, "TEXCOORD_0": uv,
                  "TANGENT": tangent, "JOINTS_0": joints, "WEIGHTS_0": weights}
    doc["meshes"] = [{"name": "hull", "weights": [0], "extras": {"targetNames": ["bend"]},
                       "primitives": [{"attributes": attributes, "indices": indices, "material": i,
                                       "targets": [{"POSITION": morph}]} for i in range(3)]}]
    doc["skins"] = [{"joints": [1], "skeleton": 1, "inverseBindMatrices": inverse}]
    doc["animations"] = [{"samplers": [{"input": times, "output": translations, "interpolation": "LINEAR"}],
                          "channels": [{"sampler": 0, "target": {"node": 1, "path": "translation"}}]}]

    def write(path, document, payload):
        document = copy.deepcopy(document)
        document["buffers"][0]["byteLength"] = len(payload)
        encoded = canonical(document)
        encoded += b" " * (-len(encoded) % 4)
        payload = bytes(payload) + b"\0" * (-len(payload) % 4)
        body = struct.pack("<I4s", len(encoded), b"JSON") + encoded + struct.pack("<I4s", len(payload), b"BIN\0") + payload
        path.write_bytes(struct.pack("<4sII", b"glTF", 2, len(body) + 12) + body)

    with tempfile.TemporaryDirectory(prefix="potc-v4-controls-") as temp:
        a, b = Path(temp) / "a.glb", Path(temp) / "b.glb"
        write(a, doc, binary)
        other = copy.deepcopy(doc)
        other["materials"][0]["pbrMetallicRoughness"]["baseColorFactor"] = [.02, .1, .3, 1]
        other["materials"][1]["pbrMetallicRoughness"]["baseColorFactor"] = [.2, .3, .4, 1]
        write(b, other, binary)
        first, second = visual_signature(a), visual_signature(b)
        paints = ["paint_hull", "paint_trim"]
        require(compare_variants(first, second, paints)["passed"], "Synthetic actual color pair was rejected")
        controls = 0

        def reject(document, payload=binary, allowlist=paints):
            nonlocal controls
            write(b, document, payload)
            try:
                passed = compare_variants(first, visual_signature(b), allowlist)["passed"]
            except (ValueError, KeyError, IndexError, struct.error):
                passed = False
            require(not passed, "Synthetic invalid pair was accepted")
            controls += 1

        reject(doc)  # Different filenames are not two color versions.
        metadata_only = copy.deepcopy(doc)
        metadata_only["asset"]["generator"] = "different generator"
        reject(metadata_only)
        for name in ("POSITION", "NORMAL", "TEXCOORD_0", "TANGENT", "JOINTS_0", "WEIGHTS_0"):
            payload = bytearray(binary)
            index = attributes[name]
            at = doc["bufferViews"][doc["accessors"][index]["bufferView"]]["byteOffset"]
            payload[at] ^= 1
            reject(other, payload)
        for index in (inverse, translations):
            payload = bytearray(binary)
            at = doc["bufferViews"][doc["accessors"][index]["bufferView"]]["byteOffset"]
            payload[at] ^= 1
            reject(other, payload)
        payload = bytearray(binary)
        payload[doc["bufferViews"][sparse_values]["byteOffset"]] ^= 1
        reject(other, payload)
        for mutate in (
                lambda d: d["nodes"][0]["extras"].update(pivot=[.1, 0, 0]),
                lambda d: d["nodes"][0].update(children=[]),
                lambda d: d["scenes"][0].update(nodes=[1]),
                lambda d: d["meshes"][0]["primitives"][0].update(material=2),
                lambda d: d["materials"][2]["pbrMetallicRoughness"].update(baseColorFactor=[.8, .8, .8, 1]),
                lambda d: d["materials"][0]["pbrMetallicRoughness"].update(roughnessFactor=.1),
                lambda d: d["materials"][0]["pbrMetallicRoughness"].update(baseColorFactor=[.02, .1, .3, .5]),
                lambda d: d["materials"][0].update(name="renamed_paint"),
                lambda d: d["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"].update(texCoord=1),
                lambda d: d["samplers"][0].update(wrapS=33071),
                lambda d: d["animations"][0]["channels"][0]["target"].update(node=0)):
            modified = copy.deepcopy(other)
            mutate(modified)
            reject(modified)
        changed_image = png((40, 80, 120))
        require(len(changed_image) == len(image_payload), "Synthetic PNG changed its encoded size")
        payload = bytearray(binary)
        start = doc["bufferViews"][image_view]["byteOffset"]
        payload[start:start + len(changed_image)] = changed_image
        reject(other, payload)
        reject(other, allowlist=[])
        reject(other, allowlist=["paint_hull", "paint_trim", "missing_paint"])
        fixture = _contract_fixture(first, second)
        validate_contract(*fixture)
        contract_controls = 0

        def reject_contract(mutate):
            nonlocal contract_controls
            values = list(copy.deepcopy(fixture))
            mutate(*values)
            try:
                validate_contract(*values)
            except (ValueError, KeyError, TypeError, IndexError):
                contract_controls += 1
            else:
                raise AssertionError("Synthetic invalid report/spec binding was accepted")

        for field in ("schema", "potc_schema"):
            reject_contract(lambda r, s, v, f, key=field: r.update({key: 0}))
        for family in ("manowar", "black-pearl", "fearless", "frigate-sat", "sloop"):
            reject_contract(lambda r, s, v, f, name=family: s.update(id=name, family=name))
        reject_contract(lambda r, s, v, f: s.update(asset_type="walkable-ship"))
        reject_contract(lambda r, s, v, f: s["guns"].update(rows=[]))
        reject_contract(lambda r, s, v, f: s["guns"]["rows"][0].update(pairs=5))
        reject_contract(lambda r, s, v, f: s["guns"]["rows"][0].update(pairs=True))
        reject_contract(lambda r, s, v, f: s.update(cannons=10))
        reject_contract(lambda r, s, v, f: s.update(game_source={"cannons": 0}))
        reject_contract(lambda r, s, v, f: s["palettes"][1].update(paintHull=s["palettes"][0]["paintHull"]))
        reject_contract(lambda r, s, v, f: s["palettes"][1].update(paintHull=[.9, .9, .9, 1]))
        reject_contract(lambda r, s, v, f: r["matrix"].__setitem__(slice(None), [x for x in r["matrix"] if x["id"] != "rig"]))
        reject_contract(lambda r, s, v, f: r["checks"].pop("collision"))
        reject_contract(lambda r, s, v, f: r["glb_files"].pop("model/navy/lod2.glb"))
        for gate in ("F1", "F4", "no_missing_uv"):
            reject_contract(lambda r, s, v, f, name=gate:
                            r["glb_files"]["model/ochre/ship.glb"]["quality"]["matrix"].__setitem__(
                                slice(None), [x for x in r["glb_files"]["model/ochre/ship.glb"]["quality"]["matrix"] if x["id"] != name]))
        reject_contract(lambda r, s, v, f: r["glb_files"]["model/ochre/lod1.glb"]["quality"].update(missing_uv_objects=["hull"]))
        reject_contract(lambda r, s, v, f: r["glb_files"]["model/ochre/ship.glb"]["quality"]["rig"].pop("attachment_support"))
        reject_contract(lambda r, s, v, f: r["glb_files"]["model/ochre/ship.glb"]["quality"]["rig"]["attachment_support"]["endpoints"][0].update(
            nearest_target_surface_distance_m=.051))
        reject_contract(lambda r, s, v, f: r["glb_files"]["model/ochre/ship.glb"]["quality"]["rig"]["attachment_support"]["endpoints"][0].update(
            nearest_actual_rope_surface_distance_m=.006))
        reject_contract(lambda r, s, v, f: r["glb_files"]["model/ochre/ship.glb"]["quality"]["rig"]["attachment_support"]["endpoints"][0].update(
            rope_cap_normal_tangent_alignment=.90))
        reject_contract(lambda r, s, v, f: r.update(invalid_nonfinite_evidence=float("nan")))
        reject_contract(lambda r, s, v, f: r["glb_files"]["model/navy/ship.glb"]["quality"].update(reused_from="model/ochre/lod2.glb"))
        reject_contract(lambda r, s, v, f: r["source_parity"]["navy"].update(source_blend_sha256="0" * 64))
        reject_contract(lambda r, s, v, f: r["source_parity"]["ochre"]["per_node_comparison"]["hull"].update(
            max_bidirectional_vertex_centroid_distance_m=.001))
        reject_contract(lambda r, s, v, f: r["render_parity"]["ochre"]["views"]["hero"].update(brightness_fraction=.11))
        reject_contract(lambda r, s, v, f: r["glb_files"]["model/collision.glb"]["sanity"]["matching"][0].update(exact_world_triangle_match=False))
        reject_contract(lambda r, s, v, f: r["checks"]["geometry"]["lods"].update(triangle_counts=[12, 12, 4]))
        reject_contract(lambda r, s, v, f: s["rig"].update(jibs=[{"kind": "jib"}]))
        reject_contract(lambda r, s, v, f: r["checks"]["type_identity"]["actual_node_ledger"]["gun_nodes"].pop())
        reject_contract(lambda r, s, v, f: r["checks"]["type_identity"]["actual_sail_kinds"].update(lateen=1))
        reject_contract(lambda r, s, v, f: r["matrix"].__setitem__(slice(None), [x for x in r["matrix"] if x["id"] != "walking"]))
        reject_contract(lambda r, s, v, f: f.update({"model/extra.glb": sha(b"unregistered extra model")}))
        reject_contract(lambda r, s, v, f: f.pop("previews/navy/hero.png"))
        reject_contract(lambda r, s, v, f: r["palette_pairs"]["lod1"].update(first_sha256="0" * 64))
        source_root = Path(temp) / "source-fixture"
        source_names = {"potc/common/v4_audit.py": "import v4_shipkit\n",
                        "potc/common/v4_integrity.py": "# synthetic source checker\n",
                        "potc/common/v4_shipkit.py": "import v4_export\nimport v4_rig\n",
                        "potc/common/v4_export.py": "# synthetic exporter\n",
                        "potc/common/v4_rig.py": "# synthetic rig\n",
                        "potc/lugger/build.py": "import v4_shipkit\n",
                        "potc/lugger/spec.json": "{}\n", ".github/workflows/potc-integrity.yml": "# synthetic CI\n"}
        for name, content in source_names.items():
            path = source_root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        closure = source_files(source_root, fixture[1])
        require(set(closure) == set(source_names), "Synthetic source closure omitted a helper/spec/workflow")
        source_controls = 0
        for name in ("potc/common/v4_export.py", "potc/common/v4_rig.py", "potc/lugger/spec.json"):
            path = source_root / name
            path.unlink()
            try:
                source_files(source_root, fixture[1])
            except ValueError:
                source_controls += 1
            else:
                raise AssertionError("Missing synthetic source dependency was accepted")
            path.write_text(source_names[name], encoding="utf-8")
        return {"passed": True, "synthetic_positive_pairs": 1, "synthetic_negative_pairs": controls,
                "synthetic_positive_contracts": 1, "synthetic_negative_contracts": contract_controls,
                "synthetic_positive_source_closures": 1, "synthetic_negative_source_closures": source_controls,
                "scope": "Portable contract/signature controls; no real-ship geometry certification"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--asset-dir", type=Path)
    target.add_argument("--all", action="store_true", help="Check delivered v4 packages under potc/*/spec.json")
    target.add_argument("--self-test", action="store_true", help="Run synthetic portable negative controls")
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()
    try:
        if args.self_test:
            result = self_test()
        elif args.all:
            root = args.source_root.resolve() if args.source_root else Path(__file__).resolve().parents[2]
            paths = sorted((root / "potc").glob("*/spec.json"))
            require(paths, "No additive PoTC ship packages were found")
            assets = [check(path.parent, root) for path in paths]
            result = {"passed": True, "assets": assets, "ship_families": len(assets)}
        else:
            result = check(args.asset_dir, args.source_root)
        print(json.dumps(result, indent=2, allow_nan=False))
    except (ValueError, KeyError, TypeError, OSError, IndexError, struct.error, SyntaxError) as error:
        parser.exit(1, "PoTC integrity failed: " + str(error) + "\n")


if __name__ == "__main__":
    main()
