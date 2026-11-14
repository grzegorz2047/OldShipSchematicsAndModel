"""Independent audits of original, static POTC-family duel display assets.

Run with Blender: --background --python potc/common/v4_audit.py --
  --asset-dir potc/lugger --source-root . [--resolution 640]

Both colours are reimported. Frozen geometric thresholds are evaluated once per
LOD only after decoded geometry/UV/node and non-paint material equality is proven.
No runtime movement, historical exactness or walking simulation is claimed.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "sailertales/common"))
import v2_audit as A
import v2_integrity as I
import v2_review as R
import v4_integrity as V

LEVELS = ("ship", "lod1", "lod2")
PALETTES = ("ochre", "navy")
QUALITY_IDS = {"A4", "B1", "B4", "D1", "D2", "D3", "E1", "E2", "F6", "F7", "F8",
               "G2", "G3", "G4", "G5", "H1", "H2", "H4", "H6"}
REQUIRED_IDS = ("contract", "geometry", "quality", "rig", "collision", "color_variants",
                "source_parity", "render_parity", "provenance", "negative_controls", "type_identity")
NA_REASONS = {
    "walking": "Static duel display asset; no walkable-player release is supplied or tested.",
    "navigation": "No runtime navigation graph or player destinations are authored for this release.",
    "controllers": "No game controller or sailing physics implementation is part of this model package.",
    "movement_ranges": "Only the authored static rig and gun pose are audited; full movement ranges are not tested.",
    "historical_exactness": "Original authored interpretation of the stock game family; no claim of exact historical or proprietary mesh reproduction.",
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def safe(root, relative):
    relative = V.relative_path(relative)
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()):
        raise ValueError("Asset/source path leaves its root: " + relative)
    return result


def sha_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def triangle_geometry(records):
    """World-coordinate triangle multiset, invariant to export seam/index order."""
    result = {}
    for record in records:
        triangles = []
        for triangle in record["triangles"]:
            triangles.append(tuple(sorted(tuple(round(float(v), 5) for v in point) for point in triangle)))
        result[record["name"]] = {"triangles": len(triangles), "sha256": sha_json(sorted(triangles))}
    return result


def bounds(records):
    if not records:
        return None
    return {"min": [min(float(r["min"][k]) for r in records) for k in range(3)],
            "max": [max(float(r["max"][k]) for r in records) for k in range(3)],
            "axes": "Blender world X=port,Y=aft,Z=up"}


def joinery(design, records, canonical, level):
    names = {r["name"] for r in records}
    canonical_names = {r["name"] for r in canonical}
    prefix = "lod%d_" % level if level else ""
    aliases = {name: name[len(prefix):] for name in names
               if prefix and name.startswith(prefix) and name[len(prefix):] in canonical_names}
    rules = []
    for rule in design.get("intended_joints", []):
        if not isinstance(rule, dict) or not isinstance(rule.get("reason"), str) or not rule["reason"].strip():
            raise ValueError("Every intended joint needs a concrete pair and a reason")
        if any(not isinstance(rule.get(key), str) or any(c in rule[key] for c in "*?[") for key in ("a", "b")):
            raise ValueError("POTC joints must name concrete members, not wildcard exemptions")
        if rule["a"] not in canonical_names or rule["b"] not in canonical_names or rule["a"] == rule["b"]:
            raise ValueError("Intended joint refers to missing/same canonical members")
        first, second = (prefix + rule["a"], prefix + rule["b"])
        if first in names and second in names:
            rules.append({"a": first, "b": second, "reason": rule["reason"],
                          "source_a": rule["a"], "source_b": rule["b"]})
    result = dict(design)
    result["intended_joints"] = rules
    return result, {"prefix": prefix, "aliases": aliases, "concrete_rules": rules}


def quality(records, doc, structural, design, full_detail):
    """Select geometry/material rows from frozen v2, without changing thresholds."""
    topology = A.topology_summary(records)
    penetration = A.audit_penetration(records, design)
    uv = A.summarized_uv(records)
    materials = A.material_json_checks(doc, structural)
    rig = A.audit_rig(records, design)
    attachment_support = rope_attachments(records)
    rig["clearance_passed"] = rig["passed"]
    rig["attachment_support"] = attachment_support
    rig["passed"] = rig["passed"] and attachment_support["passed"]
    checks = {"export": {"model/ship.glb": structural},
              "topology": {"model/ship.glb": topology, "model/collision.glb": topology},
              "penetration": penetration, "uv": uv, "materials": materials, "rig": rig,
              "navigation": {"placeholder": {"passed": False}, "model/collision.glb": {"passed": False}},
              "walking_width": {"placeholder": {"passed": False}}, "dimensions": {"passed": False},
              "bounds": {}, "source_parity": {"passed": False}, "render_parity": {"present": False},
              "provenance": {"passed": False}, "lods": {"passed": False}}
    # Frozen make_matrix reads player.height unconditionally. This temporary input
    # exists solely to obtain the selected non-player rows below; none of its
    # navigation/player rows enters a report or passes an acceptance gate.
    matrix = A.make_matrix(checks, records, doc, design,
                           {"units": "metres", "axes": "glTF Y up", "player": {"height": 1.85}})
    selected = QUALITY_IDS | ({"F1", "F2", "F3", "F4"} if full_detail else set())
    rows = [row for row in matrix if row["id"] in selected]
    missing = [r["name"] for r in records if r["uv"].get("missing_uv")]
    rows.append({"id": "no_missing_uv", "required": True, "status": "FAIL" if missing else "PASS",
                 "scope": "measured", "evidence": {"missing_uv_objects": missing}})
    full_grain = not full_detail or any(row["id"] == "F4" and row["required"] and row["status"] == "PASS" for row in rows)
    passed = bool(records) and topology["passed"] and not missing and full_grain and all(
        row["status"] == "PASS" for row in rows if row["required"])
    return {"passed": passed, "full_detail_uv_targets": full_detail, "matrix": rows,
            "missing_uv_objects": missing, "topology": topology, "penetration": penetration,
            "uv": uv, "materials": materials, "rig": rig,
            "scope": "Frozen v2 thresholds. Distance LODs omit full-detail density/stretch/grain targets."}


def rope_attachments(records):
    """Measure every declared rope end against actual support triangles."""
    by_name = {record["name"]: record for record in records}
    rows, errors = [], []
    for rope in records:
        if rope["kind"] != "rope":
            continue
        extra = rope["extras"]
        try:
            path = extra.get("rope_path_json")
            path = json.loads(path) if isinstance(path, str) else path
            if not isinstance(path, dict) or path.get("axes") != "blender_world":
                raise ValueError("Missing explicit Blender-world rope path")
            points = path.get("points")
            if not isinstance(points, list) or len(points) < 2 or any(
                not isinstance(point, list) or len(point) != 3 or any(type(v) not in (int, float) or not math.isfinite(v) for v in point)
                for point in points):
                raise ValueError("Invalid finite rope path")
        except (ValueError, TypeError) as error:
            errors.append({"rope": rope["name"], "problem": str(error)})
            continue
        prefix = next((prefix for prefix in ("lod1_", "lod2_") if rope["name"].startswith(prefix)), "")
        for key, point, adjacent in (("attachment_start", points[0], points[1]),
                                      ("attachment_end", points[-1], points[-2])):
            target_name = extra.get(key)
            if prefix and isinstance(target_name, str) and prefix + target_name in by_name:
                target_name = prefix + target_name
            target = by_name.get(target_name)
            if target is None or target is rope:
                errors.append({"rope": rope["name"], "endpoint": key, "target": target_name,
                               "problem": "Target must be an actual other visual mesh, not an Empty or self marker"})
                continue
            nearest = target["tree"].find_nearest(Vector(point))
            distance = float(nearest[3]) if nearest[0] is not None else math.inf
            rope_nearest = rope["tree"].find_nearest(Vector(point))
            rope_distance = float(rope_nearest[3]) if rope_nearest[0] is not None else math.inf
            tangent = Vector(point) - Vector(adjacent)
            cap_alignment = abs(float(rope_nearest[1].dot(tangent.normalized()))) if tangent.length > 1e-8 and rope_nearest[0] is not None else 0
            passed = distance <= .05 and rope_distance <= .005 and cap_alignment >= .95
            row = {"rope": rope["name"], "endpoint": key, "target": target_name,
                   "path_position_blender_m": point, "nearest_target_surface_distance_m": distance,
                   "nearest_actual_rope_surface_distance_m": rope_distance,
                   "rope_cap_normal_tangent_alignment": cap_alignment,
                   "rope_surface_tolerance_m": .005, "minimum_cap_normal_alignment": .95,
                   "tolerance_m": .05, "passed": passed}
            rows.append(row)
            if not passed:
                errors.append(row)
    return {"passed": not errors, "ropes": sum(record["kind"] == "rope" for record in records),
            "endpoints_measured": len(rows), "endpoints": rows, "errors": errors,
            "scope": "Source endpoint paths in GLB extras measured against actual rope end-cap triangles and the named support/cloth triangles; no tensile or dynamic simulation."}


def type_identity(spec, design, records, doc):
    contract = design.get("type_contract", {})
    names = {r["name"] for r in records}
    errors = []
    expected_counts = {"mast_nodes": len(spec.get("rig", {}).get("masts", [])),
                       "sail_nodes": sum(len(mast.get("sails", [])) for mast in spec.get("rig", {}).get("masts", []))
                       + len(spec.get("rig", {}).get("jibs", [])),
                       "gun_nodes": sum(2 * row["pairs"] for row in spec.get("guns", {}).get("rows", []))}
    actual = {}
    records_by_name = {r["name"]: r for r in records}
    for key in ("hull_nodes", "mast_nodes", "sail_nodes", "gun_nodes"):
        declared = contract.get(key)
        if not isinstance(declared, list) or any(not isinstance(n, str) for n in declared) or len(declared) != len(set(declared)):
            errors.append("Invalid concrete type ledger: " + key)
            continue
        absent = sorted(set(declared) - names)
        if absent:
            errors.append("Missing type ledger nodes: " + ",".join(absent))
        actual[key] = declared
        if key == "hull_nodes" and (not declared or any(records_by_name[n]["kind"] != "hull" for n in declared if n in names)):
            errors.append("Hull ledger must contain real hull-tagged meshes")
        if key == "hull_nodes" and set(declared) != {r["name"] for r in records if r["kind"] == "hull"}:
            errors.append("Hull ledger omits or adds actual hull-tagged meshes")
        if key == "mast_nodes" and any(records_by_name[n]["kind"] != "spar" for n in declared if n in names):
            errors.append("Mast ledger must contain real spars")
        if key == "mast_nodes" and set(declared) != {r["name"] for r in records if r["extras"].get("rig_member") == "mast"}:
            errors.append("Mast ledger differs from all actual mast members")
        if key == "sail_nodes" and set(declared) != {r["name"] for r in records if r["kind"] == "sail"}:
            errors.append("Sail ledger differs from the actual canvas meshes")
        if key in expected_counts and len(declared) != expected_counts[key]:
            errors.append("Spec plan and actual ledger count differ: " + key)
        if key == "gun_nodes" and any(records_by_name[n]["extras"].get("role") != "cannon_barrel"
                                      for n in declared if n in names):
            errors.append("Gun ledger must contain actual cannon-barrel members")
        if key == "gun_nodes" and set(declared) != {r["name"] for r in records if r["extras"].get("role") == "cannon_barrel"}:
            errors.append("Gun ledger omits or adds actual cannon barrels")
    expected_kinds = Counter(sail.get("kind") for mast in spec.get("rig", {}).get("masts", []) for sail in mast.get("sails", []))
    expected_kinds.update("jib" for _ in spec.get("rig", {}).get("jibs", []))
    actual_kinds = Counter(r["extras"].get("sail_kind") for r in records if r["kind"] == "sail")
    if expected_kinds != actual_kinds:
        errors.append("Actual cloth plan differs from authored square/lateen/fore-and-aft sail-kind counts")
    dimensions = A.measured_hull_dimensions(records, spec)
    if not dimensions["passed"]:
        errors.append("Measured hull length/beam differs from nominal dimensions")
    nodes = doc.get("nodes", [])
    origin_index = next((i for i, n in enumerate(nodes) if n.get("name") == "asset_origin"), None)
    origin = nodes[origin_index] if origin_index is not None else None
    scene = doc.get("scenes", [])[doc.get("scene", 0)] if doc.get("scenes") else {}
    children = {child for n in nodes for child in n.get("children", [])}
    origin_ok = bool(origin is not None and all(abs(v) < 1e-6 for v in origin.get("translation", [0, 0, 0]))
                     and not origin.get("matrix") and origin_index not in children
                     and origin_index in scene.get("nodes", [])
                     and all(abs(v - expected) < 1e-6 for v, expected in zip(origin.get("rotation", [0, 0, 0, 1]), [0, 0, 0, 1]))
                     and all(abs(v - 1) < 1e-6 for v in origin.get("scale", [1, 1, 1])))
    if not origin_ok:
        errors.append("Missing asset_origin at the authored waterline origin")
    return {"passed": not errors, "errors": errors, "family": spec["family"],
            "expected_plan_counts": expected_counts, "actual_node_ledger": actual,
            "expected_sail_kinds": dict(expected_kinds), "actual_sail_kinds": dict(actual_kinds),
            "dimensions": dimensions, "origin_at_zero": origin_ok,
            "scope": "Authored family plan, real mesh membership/counts and dimensional sanity; no exact proprietary mesh claim."}


def collision_sanity(collision, visual, design):
    declaration = design.get("collision", {})
    targets = declaration.get("visual_nodes", [])
    problems = []
    visual_geometry = triangle_geometry(visual)
    collision_geometry = triangle_geometry(collision)
    if not isinstance(declaration.get("scope"), str) or not declaration.get("scope", "").strip():
        problems.append("Missing explicit collision scope")
    if not isinstance(targets, list) or not targets or len(targets) != len(set(targets)):
        problems.append("Collision requires a nonempty unique list of actual hull/deck source nodes")
        targets = []
    kinds = {r["name"]: r["kind"] for r in visual}
    if any(name not in visual_geometry or kinds.get(name) not in ("hull", "surface") for name in targets):
        problems.append("Collision references missing or non-hull/deck visual nodes")
    matched = []
    seen = Counter()
    for record in collision:
        name = record["name"]
        source = record["extras"].get("visual_source")
        if not source and name.startswith("col_"):
            source = name[4:]
        seen[source] += 1
        exact = source in targets and collision_geometry[name] == visual_geometry.get(source)
        if not exact:
            problems.append("Collider is not an exact closed source-surface copy: " + name)
        matched.append({"collider": name, "visual_source": source, "exact_world_triangle_match": exact,
                        "collider_geometry": collision_geometry[name], "visual_geometry": visual_geometry.get(source)})
    if set(seen) != set(targets) or any(count != 1 for count in seen.values()):
        problems.append("Collider/source mapping is incomplete, duplicate or contains extra geometry")
    topology = A.topology_summary(collision)
    if not topology["passed"]:
        problems.append("Collision solids have invalid closed topology")
    return {"passed": not problems and bool(collision), "errors": problems, "scope": declaration.get("scope"),
            "topology": topology, "visual_nodes": targets, "matching": matched,
            "visual_bounds": bounds([r for r in visual if r["name"] in targets]),
            "collision_bounds": bounds(collision), "world_coordinate_rounding_m": 1e-5,
            "method": "Exact world-triangle multisets preserve actual concave hull/deck geometry and port openings; no walking simulation."}


def source_parity(path, records, exported):
    bpy.ops.wm.open_mainfile(filepath=str(path), load_ui=False)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    source = {}
    all_points = []
    for obj in R.candidates():
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        mesh.calc_loop_triangles()
        vertices = [evaluated.matrix_world @ v.co for v in mesh.vertices]
        triangles = [tuple(vertices[i] for i in tri.vertices) for tri in mesh.loop_triangles]
        source[obj.name] = {"name": obj.name, "triangles": triangles}
        all_points.extend(vertices)
        evaluated.to_mesh_clear()
    source_geometry = triangle_geometry(list(source.values()))
    export_geometry = triangle_geometry(records)
    unpacked = [im.name for im in bpy.data.images if im.source == "FILE" and im.users and not im.packed_file]
    # Quantised hashes are useful fingerprints, but two almost equal float32
    # points can lie on opposite quantisation boundaries. Compare actual points
    # and triangle centres bidirectionally rather than treating that as damage.
    from mathutils.kdtree import KDTree
    per_node_comparison = {}
    for name in sorted(set(source_geometry) | set(export_geometry)):
        first = source.get(name)
        second = next((r for r in records if r["name"] == name), None)
        if first is None or second is None:
            per_node_comparison[name] = {"passed": False, "reason": "Missing source/export visual node"}
            continue
        source_points = [p for triangle in first["triangles"] for p in triangle]
        export_points = [p for triangle in second["triangles"] for p in triangle]
        source_points.extend(sum(triangle, Vector()) / 3 for triangle in first["triangles"])
        export_points.extend(sum(triangle, Vector()) / 3 for triangle in second["triangles"])
        trees = []
        for points in (source_points, export_points):
            tree = KDTree(len(points))
            for index, point in enumerate(points):
                tree.insert(point, index)
            tree.balance()
            trees.append(tree)
        maximum = max([trees[1].find(point)[2] for point in source_points]
                      + [trees[0].find(point)[2] for point in export_points], default=math.inf)
        count_match = len(first["triangles"]) == len(second["triangles"])
        per_node_comparison[name] = {"passed": count_match and maximum <= .00002,
                                     "triangle_count_match": count_match,
                                     "max_bidirectional_vertex_centroid_distance_m": maximum,
                                     "tolerance_m": .00002}
    per_node_equal = bool(per_node_comparison) and all(row["passed"] for row in per_node_comparison.values())
    source_triangles = sum(len(r["triangles"]) for r in source.values())
    exported_triangles = sum(len(r["triangles"]) for r in records)
    # Independent exact triangle/position comparison is stronger than frozen
    # source parity's 1% count and 2mm overall-bounds tolerances.
    return {"passed": bool(source) and per_node_equal and not unpacked,
            "source_triangles": source_triangles, "export_triangles": exported_triangles,
            "export_indexed_triangles": exported["triangles"],
            "per_node_world_triangle_match": per_node_equal, "source_node_geometry": source_geometry,
            "export_node_geometry": export_geometry, "unpacked_used_images": unpacked,
            "per_node_comparison": per_node_comparison,
            "source_blend_sha256": I.digest(path), "world_coordinate_rounding_m": 1e-5,
            "scope": "Every evaluated source visual mesh-node instance versus actual reimported GLB triangles; collision/presentation excluded."}


def source_files(root, spec, asset):
    """AST closure from this family, never other families' specs/builders."""
    own = root / "potc" / spec["id"]
    pending = [root / "potc/common/v4_audit.py", root / "potc/common/v4_integrity.py"]
    pending.extend(own.glob("*.py"))
    if not (own / "build.py").is_file():
        raise ValueError("Missing own family build.py")
    if not (own / "spec.json").is_file():
        raise ValueError("Missing own family source spec.json")
    found = set()
    folders = (root / "potc/common", root / "sailertales/common", root / "blender", root)
    while pending:
        path = pending.pop().resolve()
        if path in found or not path.is_file():
            continue
        if not path.is_relative_to(root):
            raise ValueError("AST source dependency leaves source root")
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
                if module.startswith("v4_") and not resolved:
                    raise ValueError("Missing local v4 source dependency: " + module)
    for name in ("spec.json", "design.json"):
        if (own / name).is_file():
            found.add((own / name).resolve())
    # Explicit source-evidence files can be shared frozen records, not arbitrary
    # paths discovered by scanning sibling family folders.
    for relative in spec.get("source_paths", []):
        path = safe(root, relative)
        if not path.is_file():
            raise ValueError("Missing declared source evidence: " + relative)
        found.add(path)
    workflow = root / ".github/workflows/potc-integrity.yml"
    if workflow.is_file():
        found.add(workflow.resolve())
    return {path.relative_to(root).as_posix(): I.digest(path) for path in sorted(found)}


def render_pair(asset, palette, resolution):
    source_path = asset / "model" / palette / "source.blend"
    model_path = asset / "model" / palette / "ship.glb"
    source_folder = asset / "review" / palette
    preview_folder = asset / "previews" / palette
    source_folder.mkdir(parents=True, exist_ok=True)
    preview_folder.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(source_path), load_ui=False)
    bpy.context.scene.frame_set(0)
    definitions = R.views({"routes": []})
    definitions = {"hero": definitions["hero"], "detail": definitions["deck"]}
    source_count = R.triangle_count(R.candidates())
    for name, definition in definitions.items():
        R.render(definition, source_folder / ("source_" + name + ".png"), resolution)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(model_path))
    bpy.context.view_layer.update()
    export_count = R.triangle_count(R.candidates())
    for name, definition in definitions.items():
        R.render(definition, preview_folder / (name + ".png"), resolution)
    views = {name: R.compare(source_folder / ("source_" + name + ".png"), preview_folder / (name + ".png"))
             for name in definitions}
    inputs = {"model/" + palette + "/" + name: I.digest(asset / "model" / palette / name)
              for name in ("ship.glb", "source.blend")}
    images = {p.relative_to(asset).as_posix(): I.digest(p)
              for p in (*source_folder.glob("source_*.png"), *preview_folder.glob("*.png"))}
    return {"passed": source_count == export_count and all(row["passed"] for row in views.values()),
            "source_triangles": source_count, "export_triangles": export_count,
            "triangle_match": source_count == export_count, "views": views, "cameras": definitions,
            "resolution": resolution, "sha256": inputs, "output_sha256": images,
            "scope": "Actual GLB versus its own packed colour scene under identical cameras/lights; detail is a hull/deck view with rig hidden, not a walking proof."}


def controls():
    frozen = A.self_test()
    relevant = [value for value in frozen if any(word in value for word in ("penetration", "joint", "cloth", "boundary"))]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.object
    assert A.weld_topology(cube)[0]["non_manifold_edges"] == 0
    cube.data.polygons[0].select = True
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(cube.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[0]], context="FACES")
    bm.to_mesh(cube.data)
    bm.free()
    assert A.weld_topology(cube)[0]["non_manifold_edges"] > 0
    relevant.extend(("closed solid accepted", "opened solid rejected"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    timber = bpy.context.object
    timber.name = "wood_control_beam"
    timber.dimensions = (2, .2, .2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    material = bpy.data.materials.new("wood_hull_control")
    material.use_nodes = True
    image = bpy.data.images.new("wood_albedo_control", width=2048, height=2048)
    image.colorspace_settings.name = "sRGB"
    image_node = material.node_tree.nodes.new("ShaderNodeTexImage")
    image_node.image = image
    material.node_tree.links.new(image_node.outputs["Color"], material.node_tree.nodes.get("Principled BSDF").inputs["Base Color"])
    timber.data.materials.append(material)
    layer = timber.data.uv_layers.active.data
    for polygon in timber.data.polygons:
        dominant = max(range(3), key=lambda axis: abs(polygon.normal[axis]))
        axes = (1, 2) if dominant == 0 else (0, 2) if dominant == 1 else (0, 1)
        for loop_index in polygon.loop_indices:
            point = timber.data.vertices[timber.data.loops[loop_index].vertex_index].co
            layer[loop_index].uv = (point[axes[0]] / 2, point[axes[1]] / 2)
    timber.data.calc_loop_triangles()
    original_uv = [tuple(loop.uv) for loop in layer]
    good = A.summarized_uv([{"name": timber.name, "kind": "spar", "uv": A.uv_metrics(timber)}])["materials"][material.name]
    assert abs(good["texel_density_px_m"]["median"] - 1024) < .01
    assert good["density_p95_p5_ratio"] <= 1.44 and good["anisotropy_over_1_25_area_share"] <= .08
    assert good["wood_grain_aligned_share"] >= .94
    for loop, uv in zip(layer, original_uv):
        loop.uv = (uv[0] * .1, uv[1] * .1)
    small = A.summarized_uv([{"name": timber.name, "kind": "spar", "uv": A.uv_metrics(timber)}])["materials"][material.name]
    assert small["texel_density_px_m"]["p5"] < 800
    for loop, uv in zip(layer, original_uv):
        loop.uv = (uv[0] * 4, uv[1])
    stretched = A.summarized_uv([{"name": timber.name, "kind": "spar", "uv": A.uv_metrics(timber)}])["materials"][material.name]
    assert stretched["anisotropy_over_1_25_area_share"] > .08
    for loop, uv in zip(layer, original_uv):
        loop.uv = (-uv[1], uv[0])
    rotated = A.summarized_uv([{"name": timber.name, "kind": "spar", "uv": A.uv_metrics(timber)}])["materials"][material.name]
    assert rotated["wood_grain_aligned_share"] < .94
    for loop in layer:
        loop.uv = (0, 0)
    degenerate = A.summarized_uv([{"name": timber.name, "kind": "spar", "uv": A.uv_metrics(timber)}])["materials"][material.name]
    assert degenerate["degenerate_uv_area_m2"] > 0
    relevant.extend(("isometric 1024px/m timber accepted", "low density rejected", "UV anisotropy rejected",
                     "cross-grain wood UV rejected", "collapsed UV triangles rejected"))
    bad_material = {"materials": [{"name": "map_role_control", "pbrMetallicRoughness": {
        "baseColorTexture": {"index": 0}, "metallicRoughnessTexture": {"index": 0}},
        "normalTexture": {"index": 0}}], "textures": [{"source": 0}]}
    assert not A.material_json_checks(bad_material, {"images": [{"power_of_two": True}]})["passed"]
    relevant.append("same image reused for colour/roughness/normal rejected")
    support = {"name": "support_control", "kind": "fitting", "extras": {},
               "tree": A.BVHTree.FromPolygons([Vector((-1, -1, 0)), Vector((1, -1, 0)), Vector((0, 2, 0))],
                                             [(0, 1, 2)], all_triangles=True)}
    rope_vertices = [Vector((x * .05, y, z * .05)) for z in (-1, 1) for y in (0, 1) for x in (-1, 1)]
    rope_faces = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    line = {"name": "rope_control", "kind": "rope", "extras": {
        "attachment_start": "support_control", "attachment_end": "support_control",
        "rope_path_json": json.dumps({"axes": "blender_world", "points": [[0, 0, 0], [0, 1, 0]]})},
        "tree": A.BVHTree.FromPolygons(rope_vertices, rope_faces)}
    assert rope_attachments([support, line])["passed"]
    line["extras"]["rope_path_json"] = json.dumps({"axes": "blender_world", "points": [[0, 0, 0], [0, 1, .2]]})
    assert not rope_attachments([support, line])["passed"]
    line["extras"]["attachment_end"] = "empty_origin_marker"
    assert not rope_attachments([support, line])["passed"]
    line["extras"]["attachment_end"] = "support_control"
    line["extras"]["rope_path_json"] = json.dumps({"axes": "blender_world", "points": [[0, .25, 0], [0, .75, 0]]})
    assert not rope_attachments([support, line])["passed"]
    relevant.extend(("rope endpoints on actual caps and target triangles accepted", "floating rope endpoint rejected",
                     "Empty or missing rope target rejected", "path metadata detached from actual rope caps rejected"))
    # Keep controls about audit behavior distinct from ship acceptance evidence.
    return {"passed": True, "controls": relevant,
            "scope": "Synthetic positive/negative controls of frozen intersection and topology logic, not model navigation claims."}


def audit(asset, root, resolution=480, render=True, geometry_only=False):
    spec = read(asset / "spec.json")
    V.validate_spec(spec)
    design = read(asset / "design.json")
    negative = controls()
    expected = {"model/%s/%s.glb" % (palette, level) for palette in PALETTES for level in LEVELS}
    expected.add("model/collision.glb")
    actual = {p.relative_to(asset).as_posix() for p in asset.rglob("*.glb")}
    if expected != actual:
        raise ValueError("Missing or unregistered delivered GLBs: " + str(expected ^ actual))
    pair_checks, files, canonical, canonical_doc = {}, {}, None, None
    first_level_records = {}
    for level_index, level in enumerate(LEVELS):
        paths = ["model/%s/%s.glb" % (palette, level) for palette in PALETTES]
        signatures = [V.visual_signature(asset / path) for path in paths]
        paint_names = [(("lod%d_" % level_index) if level_index else "") + name for name in spec["paint_materials"]]
        # Custom kit may retain semantic material names in LODs. Determine only
        # the exact prefix convention actually used by both GLBs, never wildcard.
        material_names = set(signatures[0].get("materials", {}))
        if set(spec["paint_materials"]).issubset(material_names):
            paint_names = spec["paint_materials"]
        pair = V.compare_variants(signatures[0], signatures[1], paint_names)
        pair_checks[level] = pair
        if not pair["passed"]:
            raise ValueError("Actual palette geometry/natural-material invariants failed: " + level + " " + str(pair))
        structural, doc, _ = I.inspect_glb(asset / paths[0])
        records = A.object_records(asset / paths[0])
        first_level_records[level] = records
        if level_index == 0:
            canonical, canonical_doc = records, doc
        level_design, mapped = joinery(design, records, canonical, level_index)
        measured = quality(records, doc, structural, level_design, level_index == 0)
        first_row = {"role": "visual", "palette": PALETTES[0], "level": level_index,
                     "sha256": I.digest(asset / paths[0]), "structure": structural,
                     "visual_signature": signatures[0], "geometry_sha256": signatures[0]["geometry_sha256"],
                     "imported_triangles": sum(len(r["triangles"]) for r in records),
                     "bounds": bounds(records), "quality": measured, "lod_joint_mapping": mapped}
        first_row["passed"] = structural["passed"] and measured["passed"] and measured["rig"]["passed"]
        files[paths[0]] = first_row
        second_structure, _, _ = I.inspect_glb(asset / paths[1])
        files[paths[1]] = {"role": "visual", "palette": PALETTES[1], "level": level_index,
                           "sha256": I.digest(asset / paths[1]), "structure": second_structure,
                           "visual_signature": signatures[1], "geometry_sha256": signatures[1]["geometry_sha256"],
                           "imported_triangles": first_row["imported_triangles"], "bounds": first_row["bounds"],
                           "quality": {"passed": measured["passed"], "reused_from": paths[0],
                                       "geometry_and_material_invariants": pair["passed"]},
                           "passed": first_row["passed"] and second_structure["passed"] and pair["passed"]}
    collision_path = "model/collision.glb"
    collision_structural, _, _ = I.inspect_glb(asset / collision_path)
    collision = A.object_records(asset / collision_path)
    collision_result = collision_sanity(collision, canonical, design)
    files[collision_path] = {"role": "collision", "sha256": I.digest(asset / collision_path),
                             "structure": collision_structural, "sanity": collision_result,
                             "imported_triangles": sum(len(r["triangles"]) for r in collision),
                             "passed": collision_structural["passed"] and collision_result["passed"]}
    identity = type_identity(spec, design, canonical, canonical_doc)
    if geometry_only:
        return {"diagnostic_only": True, "vessel": spec["id"], "family": spec["family"],
                "passed": all(row["passed"] for row in files.values()) and identity["passed"],
                "glb_files": files, "palette_pairs": pair_checks, "type_identity": identity,
                "scope": "Intermediate geometry diagnostics only; no source/export render acceptance or release report."}
    source = {palette: source_parity(asset / "model" / palette / "source.blend", canonical,
                                     files["model/%s/ship.glb" % palette]["structure"])
              for palette in PALETTES}
    if render:
        render_checks = {palette: render_pair(asset, palette, resolution) for palette in PALETTES}
        export_review = {"schema": 4, "passed": all(v["passed"] for v in render_checks.values()),
                         "palettes": render_checks,
                         "thresholds": {"brightness_fraction": .10, "maximum_channel_share_difference": .04}}
        (asset / "export-review.json").write_text(json.dumps(A.plain(export_review), indent=2) + "\n", encoding="utf-8")
    else:
        export_review = read(asset / "export-review.json")
        render_checks = export_review.get("palettes", {})
        for palette in PALETTES:
            row = render_checks.get(palette, {})
            for relative, digest in {**row.get("sha256", {}), **row.get("output_sha256", {})}.items():
                if I.digest(safe(asset, relative)) != digest:
                    raise ValueError("Existing render comparison is stale: " + relative)
    lod_counts = [files["model/ochre/%s.glb" % level]["imported_triangles"] for level in LEVELS]
    canonical_bounds = bounds(canonical)
    tolerance = max(.05, .015 * spec["length"])
    lod_bounds = {}
    for level in LEVELS[1:]:
        measured_bounds = files["model/ochre/%s.glb" % level]["bounds"]
        maximum = max(abs(measured_bounds[key][axis] - canonical_bounds[key][axis]) for key in ("min", "max") for axis in range(3))
        lod_bounds[level] = {"passed": maximum <= tolerance, "max_bound_error_m": maximum, "tolerance_m": tolerance}
    lods = {"passed": lod_counts[0] > lod_counts[1] > lod_counts[2] > 0 and all(r["passed"] for r in lod_bounds.values()),
            "triangle_counts": lod_counts, "bounds": lod_bounds,
            "scope": "Real decreasing draw triangle counts and world bounds continuity; no screen-space silhouette claim."}
    source_hashes = source_files(root, spec, asset)
    required_sources = {"potc/common/v4_audit.py", "potc/common/v4_integrity.py", "potc/common/v4_shipkit.py",
                        "potc/common/v4_export.py", "potc/common/v4_rig.py", "potc/%s/build.py" % spec["id"],
                        "potc/%s/spec.json" % spec["id"],
                        "sailertales/common/v2_audit.py", "sailertales/common/v2_integrity.py", "sailertales/common/v2_review.py"}
    provenance = {"passed": required_sources.issubset(source_hashes) and (root / "potc/common/v4_audit.py").read_bytes() == Path(__file__).read_bytes(),
                  "method": "Own builder/spec and transitive local AST imports; unrelated family builders/specs excluded.",
                  "required_sources": sorted(required_sources), "source_files": len(source_hashes)}
    checks = {"contract": {"passed": True, "ordinary_family": spec["family"], "schema": 4, "static_scope": True},
              "geometry": {"passed": all(row["passed"] for row in files.values()) and lods["passed"], "lods": lods},
              "quality": {"passed": all(files["model/ochre/%s.glb" % level]["quality"]["passed"] for level in LEVELS)},
              "rig": {"passed": all(files["model/ochre/%s.glb" % level]["quality"]["rig"]["passed"] for level in LEVELS)},
              "collision": collision_result,
              "color_variants": {"passed": all(row["passed"] for row in pair_checks.values()), "levels": pair_checks},
              "source_parity": {"passed": all(row["passed"] for row in source.values()), "palettes": source},
              "render_parity": {"passed": export_review.get("passed") is True and set(render_checks) == set(PALETTES)
                                 and all(row.get("passed") is True for row in render_checks.values())},
              "provenance": provenance, "negative_controls": negative, "type_identity": identity}
    matrix = [{"id": name, "required": True, "status": "PASS" if checks[name]["passed"] else "FAIL",
               "scope": "measured", "evidence": checks[name]} for name in REQUIRED_IDS]
    matrix.extend({"id": name, "required": False, "status": "NA", "scope": "not_applicable", "reason": reason}
                  for name, reason in NA_REASONS.items())
    assets = {p.relative_to(asset).as_posix(): I.digest(p) for p in sorted(asset.rglob("*"))
              if p.is_file() and p.name != "validation.json" and "__pycache__" not in p.parts and not p.name.endswith(".blend1")}
    report = {"schema": 4, "potc_schema": 1, "vessel": spec["id"], "family": spec["family"],
              "passed": all(row["status"] == "PASS" for row in matrix if row["required"]),
              "scope": "Static duel display model, two complete paint versions, authored LODs and exact concave static hull/deck collision.",
              "matrix": matrix, "checks": checks, "glb_files": files, "palette_pairs": pair_checks,
              "source_parity": source, "render_parity": render_checks,
              "sha256": assets, "source_sha256": source_hashes}
    (asset / "validation.json").write_text(json.dumps(A.plain(report), indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-dir", type=Path)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--resolution", type=int, default=480)
    parser.add_argument("--reuse-review", action="store_true")
    parser.add_argument("--geometry-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if args.self_test:
        print("V4_AUDIT_CONTROLS", json.dumps(controls()), flush=True)
        return
    if args.asset_dir is None:
        parser.error("--asset-dir is required")
    if args.resolution < 320:
        parser.error("Source/export review resolution must be at least 320")
    report = audit(args.asset_dir.resolve(), args.source_root.resolve(), args.resolution, not args.reuse_review, args.geometry_only)
    if args.geometry_only:
        output = args.asset_dir.resolve().parent / (args.asset_dir.name + "-geometry-diagnostic.json")
        output.write_text(json.dumps(A.plain(report), indent=2, allow_nan=False) + "\n", encoding="utf-8")
        print("V4_GEOMETRY_DIAGNOSTIC", report["vessel"], report["passed"], str(output), flush=True)
        if not report["passed"]:
            raise RuntimeError("Intermediate geometry diagnostics failed; see separate diagnostic file")
        return
    print("V4_AUDIT", report["vessel"], report["passed"], {row["id"]: row["status"] for row in report["matrix"]}, flush=True)
    if not report["passed"]:
        raise RuntimeError("Required static duel acceptance gate failed")
    result = V.check(args.asset_dir.resolve(), args.source_root.resolve())
    print("V4_PORTABLE", json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
