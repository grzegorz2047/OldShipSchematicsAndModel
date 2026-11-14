"""Additive acceptance audit for boat-frame and capsized-boat game props.

Uses frozen v2 geometry/material/UV checks. No fabricated walking routes and no
aliasing of new IDs to existing ships. Run in Blender; see --help.
"""
from pathlib import Path
import argparse
import ast
import collections
import copy
import fnmatch
import hashlib
import json
import math
import re
import sys
import tempfile

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import v2_audit as A
import v2_integrity as I
import v2_review as R

KINDS = {"boat-frame", "capsized-boat"}
FLOAT = {"lift": 0, "span": 2.4, "beam": .7, "bob": .03, "sway": .09, "tilt": .7}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def child(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Asset path escapes package: " + str(relative))
    return path


def finite(values):
    return all(math.isfinite(float(v)) for v in values)


def contract_errors(spec, states, nav):
    errors = []
    kind = spec.get("id")
    if kind not in KINDS or states.get("kind") != kind or states.get("schema") != 1:
        errors.append("Unknown prop kind or inconsistent state contract")
    if nav.get("routes") != []:
        errors.append("These props have no authored onboard walking routes; routes must be []")
    rows = states.get("states", [])
    if not rows or any(not r.get("model") or not r.get("collision") for r in rows):
        errors.append("Each state needs actual visual and collision GLBs")
    if kind == "boat-frame":
        if sorted(r.get("stage", -1) for r in rows) != [0, 1, 2, 3]:
            errors.append("All four distinct construction stages 0..3 are required")
        components = {r.get("id"): r for r in states.get("components", [])}
        for name in ("repair_plank", "pegs", "trim"):
            if not components.get(name, {}).get("model"):
                errors.append("Missing component " + name)
        if components.get("repair_plank", {}).get("morph") != "straight":
            errors.append("repair_plank must declare its straight morph")
        anchors = states.get("anchors", {})
        for name in ("repair_gap", *["peg_" + str(i) for i in range(5)]):
            if name not in anchors:
                errors.append("Missing construction marker " + name)
        expected = {"setStage": [0, 1, 2, 3], "setGapPlank": [0, 1],
                    "setPegs": [0, 5], "setTrim": [False, True]}
        for key, value in expected.items():
            if states.get("hooks", {}).get(key) != value:
                errors.append("Missing or inconsistent source hook " + key)
        gap = states.get("gap", {})
        probe = gap.get("probe_gltf_m", [])
        if len(probe) != 2 or any(len(p) != 3 or not finite(p) for p in probe):
            errors.append("A finite two-point geometric repair-gap probe is required")
        elif (Vector(probe[1]) - Vector(probe[0])).length < .05:
            errors.append("Repair-gap probe is token-sized")
        if not gap.get("shell_patterns"):
            errors.append("Repair-gap shell object patterns are required")
    elif kind == "capsized-boat":
        if len(rows) != 1:
            errors.append("Capsized prop has one static authored state")
        node = states.get("seat", {}).get("node")
        if not node or node not in states.get("anchors", {}):
            errors.append("A named actor seat anchor is required")
        for key, expected in FLOAT.items():
            value = states.get("float", {}).get(key)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value - expected) > 1e-8:
                errors.append("Wrong source float parameter " + key)
    for name, xyz in states.get("anchors", {}).items():
        if not isinstance(xyz, list) or len(xyz) != 3 or not finite(xyz):
            errors.append("Invalid marker coordinates " + name)
    return errors


def capture_current():
    """Same frozen v2 measurements, applied to the current evaluated morph pose."""
    records = []
    for obj in list(bpy.context.scene.objects):
        if obj.type != "MESH":
            continue
        obj.data.calc_loop_triangles()
        points = [obj.matrix_world @ v.co for v in obj.data.vertices]
        ids = [tuple(t.vertices) for t in obj.data.loop_triangles]
        if not ids:
            continue
        topology, boundaries, unique, islands = A.weld_topology(obj)
        records.append({"name": obj.name, "kind": A.inferred_kind(obj), "extras": dict(obj.items()),
                        "vertices": unique, "triangles": [tuple(points[i] for i in tri) for tri in ids],
                        "min": Vector(tuple(min(p[k] for p in points) for k in range(3))),
                        "max": Vector(tuple(max(p[k] for p in points) for k in range(3))),
                        "tree": BVHTree.FromPolygons(points, ids, all_triangles=True, epsilon=1e-7),
                        "topology": topology, "boundaries": boundaries, "islands": islands,
                        "materials": [], "uv": A.uv_metrics(obj),
                        "transform": {"scale": list(obj.scale), "rotation": list(obj.rotation_euler)}})
    return records


def geometry_signature(records):
    digest = hashlib.sha256()
    triangles = []
    for record in records:
        for triangle in record["triangles"]:
            triangles.append(tuple(sorted(tuple(round(float(v), 6) for v in p) for p in triangle)))
    for triangle in sorted(triangles):
        digest.update(repr(triangle).encode("ascii"))
    return digest.hexdigest()


def pose_records(path, morph=None, weight=0):
    records = A.object_records(path)
    if morph is None:
        return records
    shaped = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.data.shape_keys
              and morph in o.data.shape_keys.key_blocks]
    if not shaped:
        raise ValueError("Missing delivered morph " + morph)
    for obj in shaped:
        for key in obj.data.shape_keys.key_blocks:
            if key.name != "Basis":
                key.value = weight if key.name == morph else 0
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    for obj in shaped:
        obj.data = bpy.data.meshes.new_from_object(obj.evaluated_get(graph))
        metadata = obj.get("grain_morph_paths_json")
        if metadata:
            contract = json.loads(metadata) if isinstance(metadata, str) else dict(metadata)
            base, target = contract.get("base", []), contract.get("target", [])
            if contract.get("axes") != "object_local" or contract.get("morph") != morph or len(base) != len(target) or len(base) < 2:
                raise ValueError("Invalid morph-specific grain centreline contract")
            if any(len(p) != 3 or not finite(p) for p in [*base, *target]):
                raise ValueError("Nonfinite morph grain centreline")
            posed_path = [list(Vector(a).lerp(Vector(b), weight)) for a, b in zip(base, target)]
            vertices = list({tuple(round(float(v), 6) for v in point.co) for point in obj.data.vertices})
            errors = []
            for point in posed_path:
                nearest = sorted(vertices, key=lambda v: (Vector(v) - Vector(point)).length_squared)[:4]
                centre = sum((Vector(p) for p in nearest), Vector()) / 4
                errors.append((centre - Vector(point)).length)
            if max(errors) > .001:
                raise ValueError("Morph grain path is not bound to actual four-vertex section centroids")
            obj["grain_path_json"] = json.dumps(posed_path)
            obj["audited_grain_pose_json"] = json.dumps({"weight": weight, "object_local": posed_path,
                "max_section_centroid_error_m": max(errors), "tolerance_m": .001})
    return capture_current()


def anchors_current():
    return {o.name: [float(o.matrix_world.translation.x), float(o.matrix_world.translation.z),
                     -float(o.matrix_world.translation.y)] for o in bpy.context.scene.objects if o.type == "EMPTY"}


def marker_check(expected, actual):
    missing = [name for name in expected if name not in actual]
    errors = {name: (Vector(actual[name]) - Vector(xyz)).length for name, xyz in expected.items() if name in actual}
    return {"passed": not missing and all(v <= .001 for v in errors.values()),
            "missing": missing, "position_errors_m": errors, "tolerance_m": .001,
            "actual_gltf_m": actual, "expected_gltf_m": expected}


def seat_check(states, records, actual):
    name = states["seat"]["node"]
    if name not in actual:
        return {"passed": False, "reason": "Seat node absent from delivered GLB"}
    xyz = actual[name]
    source_position = abs(xyz[0] - .4) <= .001 and abs(xyz[2]) <= .001
    seat = A.ship_to_blender(xyz)
    surfaces = [r for r in records if r["kind"] not in ("rope", "sail", "glass")
                and any(token in r["name"] for token in ("hull", "plank", "strake", "keel", "shell"))]
    hits = []
    for record in surfaces:
        hit, normal, _, distance = record["tree"].ray_cast(seat + Vector((0, 0, .15)), Vector((0, 0, -1)), .30)
        if hit is not None and normal.z > 0:
            hits.append({"object": record["name"], "surface_gltf_m": [hit.x, hit.z, -hit.y],
                         "vertical_gap_m": abs(hit.z - seat.z), "up_normal": normal.z})
    closest = min(hits, key=lambda row: row["vertical_gap_m"]) if hits else None
    return {"passed": source_position and closest is not None and closest["vertical_gap_m"] <= .08,
            "node": name, "position_gltf_m": xyz, "source_x_z_correct": source_position,
            "support": closest, "support_tolerance_m": .08,
            "scope": "Static seated actor attachment on real inverted hull; no standing/walking claim"}


def segment_hits(records, probe, patterns=None):
    a, b = [A.ship_to_blender(p) for p in probe]
    direction = b - a
    hits = []
    selected = [r for r in records if patterns is None or any(fnmatch.fnmatchcase(r["name"], p) for p in patterns)]
    for record in selected:
        hit = record["tree"].ray_cast(a, direction.normalized(), direction.length)[0]
        if hit is not None:
            hits.append(record["name"])
    return {"selected_objects": len(selected), "hit_objects": hits}


def provenance(root, spec, design):
    pending = [HERE / "v3_prop_audit.py", HERE / "v3_prop_integrity.py", HERE / "v2_audit.py",
               HERE / "v2_review.py", HERE / "v2_integrity.py", HERE / "v2_export.py",
               root / "sailertales" / spec["id"] / "build.py"]
    pending.extend((root / "sailertales" / spec["id"]).glob("*.py"))
    found = set()
    while pending:
        path = pending.pop().resolve()
        if path in found or not path.is_file():
            continue
        if not path.is_relative_to(root):
            raise ValueError("Builder/helper source leaves repository root")
        found.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            modules = ([node.module] if isinstance(node, ast.ImportFrom) else
                       [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
            for module in modules:
                if not module:
                    continue
                for folder in (path.parent, HERE, root / "blender"):
                    candidate = folder / (module.replace(".", "/") + ".py")
                    if candidate.is_file():
                        pending.append(candidate)
    found.update((root / "blender").glob("*.py"))
    for pattern in ("fleet-inventory-*.json", "fleet-inventory-*.md"):
        found.update((root / "sailertales").glob(pattern))
    declared = design.get("source_files", {})
    if isinstance(declared, dict):
        for relative in declared:
            source = child(root, relative)
            if source.is_file():
                found.add(source)
    return {path.relative_to(root).as_posix(): I.digest(path) for path in sorted(found)}


def render_pose(asset, name, resolution):
    definition = R.views({"routes": []})["hero"]
    relative = "previews/audit_" + re.sub("[^a-z0-9_]+", "_", name.lower()) + ".png"
    R.render(definition, asset / relative, resolution)
    return relative


def frozen_quality(records, doc, structural, design, full_detail=True):
    """Evaluate the existing thresholds, without copying or loosening them."""
    topology = A.topology_summary(records)
    checks = {"export": {"model/ship.glb": structural},
              "topology": {"model/ship.glb": topology, "model/collision.glb": topology},
              "penetration": A.audit_penetration(records, design),
              "uv": A.summarized_uv(records), "materials": A.material_json_checks(doc, structural),
              "rig": A.audit_rig(records, design),
              "navigation": {"model/ship.glb": {"passed": False}, "model/collision.glb": {"passed": False}},
              "walking_width": {"applicable": {"passed": False}}, "dimensions": {"passed": False},
              "bounds": {}, "source_parity": {"passed": False}, "render_parity": {"present": False},
              "provenance": {"passed": False}, "lods": {"passed": False}}
    matrix = A.make_matrix(checks, records, doc, design, {"units": "metres", "axes": "glTF Y up", "player": {"height": 1.85}})
    selected = {"A4", "B1", "B4", "D1", "D2", "D3", "E1", "E2", "F6", "F7", "F8", "G2", "G3", "G4", "G5", "H1", "H2", "H4", "H6"}
    if full_detail:
        selected.update(("F1", "F2", "F3", "F4"))
    rows = [r for r in matrix if r["id"] in selected]
    return {"passed": all(r["status"] == "PASS" for r in rows if r["required"]),
            "matrix": rows, "full_detail_uv_targets": full_detail,
            "scope": "Frozen v2 thresholds; distance LODs omit full-detail density/stretch/grain targets"}


def lod_joinery(design, records, canonical_records, level):
    """Concrete aliases for the frozen exporter's exact lodN_ node copies."""
    prefix = "lod%d_" % level
    original = {r["name"] for r in canonical_records}
    mapped = {r["name"]: r["name"][len(prefix):] for r in records
              if r["name"].startswith(prefix) and r["name"][len(prefix):] in original}
    rows = []
    names = sorted(mapped)
    for index, first in enumerate(names):
        for second in names[index + 1:]:
            reason = A.intended_joint(mapped[first], mapped[second], design)
            if reason:
                rows.append({"a": first, "b": second, "reason": reason,
                             "source_a": mapped[first], "source_b": mapped[second]})
    result = dict(design)
    result["intended_joints"] = list(design.get("intended_joints", [])) + rows
    return result, rows


def inventory_evidence(root, spec):
    matching = []
    for path in sorted((root / "sailertales").glob("fleet-inventory-*.json")):
        inventory = read(path)
        variants = inventory.get("conclusion", {}).get("additional_active_asset_variants", [])
        if inventory.get("head") == spec.get("source_commit") and spec["id"] in variants:
            matching.append({"path": path.relative_to(root).as_posix(), "sha256": I.digest(path),
                             "game_commit": inventory["head"], "active_variant": spec["id"]})
    return {"passed": bool(matching), "matching_inventory": matching}


def self_test():
    controls = A.self_test()
    spec = {"id": "capsized-boat"}
    valid = {"schema": 1, "kind": "capsized-boat", "states": [{"id": "capsized", "model": "model/ship.glb", "collision": "model/collision.glb"}],
             "anchors": {"seat_anchor": [.4, .08, 0]}, "seat": {"node": "seat_anchor"}, "float": dict(FLOAT)}
    assert not contract_errors(spec, valid, {"routes": []})
    changed = copy.deepcopy(valid); changed["float"]["span"] = 99
    assert contract_errors(spec, changed, {"routes": []}), "Wrong float parameters must fail"
    changed = copy.deepcopy(valid); changed["anchors"] = {}
    assert contract_errors(spec, changed, {"routes": []}), "Missing seat must fail"
    assert contract_errors(spec, valid, {"routes": [{"name": "fabricated_walk"}]}), "Invented walks must fail"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add(size=2)
    hull = bpy.context.object; hull.name = "hull_control"; hull.scale = (.8, .8, .1)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    records = capture_current()
    assert seat_check(valid, records, {"seat_anchor": [.4, .08, 0]})["passed"]
    assert not seat_check(valid, records, {"seat_anchor": [.4, .8, 0]})["passed"], "Unsupported floating seat must fail"
    assert not seat_check(valid, records, {"seat_anchor": [.5, .08, 0]})["passed"], "Wrong source seat offset must fail"
    probe = [[0, .25, 0], [0, -.25, 0]]
    assert segment_hits(records, probe)["hit_objects"], "Filled repair gap must be detected"
    assert not segment_hits(records, [[2, .25, 0], [2, -.25, 0]])["hit_objects"], "Open probe must remain open"
    missing_marker = marker_check({"peg_0": [0, 0, 0]}, {})
    assert not missing_marker["passed"], "Missing physical GLB marker must fail"
    hull.shape_key_add(name="Basis")
    straight = hull.shape_key_add(name="straight")
    for vertex in straight.data:
        vertex.co.z += .4
    grain = {"axes": "object_local", "morph": "straight", "base": [[-.8, 0, 0], [.8, 0, 0]],
             "target": [[-.8, 0, .4], [.8, 0, .4]]}
    hull["grain_morph_paths_json"] = json.dumps(grain)
    with tempfile.TemporaryDirectory(prefix="prop-morph-control-") as temporary:
        valid_path, invalid_path = Path(temporary) / "valid.glb", Path(temporary) / "invalid.glb"
        bpy.ops.export_scene.gltf(filepath=str(valid_path), export_format="GLB", use_selection=True,
                                  export_extras=True, export_animations=False, export_morph=True)
        posed = pose_records(valid_path, "straight", .5)
        assert any(r["extras"].get("audited_grain_pose_json") for r in posed)
        A.object_records(valid_path)
        obj = next(o for o in bpy.context.scene.objects if o.type == "MESH")
        grain["target"] = [[-.8, 0, 7], [.8, 0, 7]]
        obj["grain_morph_paths_json"] = json.dumps(grain)
        bpy.ops.export_scene.gltf(filepath=str(invalid_path), export_format="GLB", export_extras=True,
                                  export_animations=False, export_morph=True)
        try:
            pose_records(invalid_path, "straight", .5)
        except ValueError as error:
            assert "section centroids" in str(error)
        else:
            raise AssertionError("Invented deformed grain path must fail")
    return controls + ["valid static seat accepted", "unsupported seat rejected", "wrong source seat offset rejected",
                       "incorrect float span rejected", "absent seat contract rejected", "fabricated walking rejected",
                       "filled repair gap ray detected", "empty repair gap ray accepted", "missing marker rejected",
                       "reimported morph grain centroid binding accepted", "invented morph grain path rejected"]


def audit_asset(spec_path, asset, resolution=480):
    controls = self_test()
    spec, states, nav, design = read(spec_path), read(asset / "states.json"), read(asset / "navigation.json"), read(asset / "design.json")
    errors = contract_errors(spec, states, nav)
    if errors:
        raise ValueError("; ".join(errors))
    registry = {}
    for row in states["states"]:
        for key in ("model", "collision"):
            registry[row[key]] = {"role": key, "state": row["id"]}
    for row in states.get("components", []):
        registry[row["model"]] = {"role": "component", "component": row["id"], **row}
        if row.get("collision"):
            registry[row["collision"]] = {"role": "collision", "component": row["id"]}
    for level in (1, 2):
        registry["model/ship_lod%d.glb" % level] = {"role": "lod", "level": level}
    shipped = {p.relative_to(asset).as_posix() for p in (asset / "model").rglob("*.glb")}
    if shipped != set(registry):
        raise ValueError("Unregistered/missing GLB state files: " + str(shipped.symmetric_difference(registry)))
    file_checks, captures, signatures = {}, {}, {}
    main_records = main_doc = main_export = main_markers = None
    for relative, entry in registry.items():
        path = child(asset, relative)
        structural, doc, _ = I.inspect_glb(path)
        records = A.object_records(path)
        markers = anchors_current()
        topology = A.topology_summary(records)
        file_design, joint_mapping = (lod_joinery(design, records, main_records, entry["level"])
                                      if entry["role"] == "lod" else (design, []))
        penetration = A.audit_penetration(records, file_design) if entry["role"] != "collision" else {"passed": True, "scope": "Collider unions may intentionally overlap; individual solids checked"}
        row = {"role": entry["role"], "sha256": I.digest(path), "structure": structural,
               "topology": topology, "penetration": penetration, "geometry_sha256": geometry_signature(records),
               "imported_triangles": sum(len(r["triangles"]) for r in records), "objects": len(records)}
        if entry["role"] == "lod":
            row["lod_joint_mapping"] = joint_mapping
        row["passed"] = structural["passed"] and topology["passed"] and penetration["passed"] and bool(records)
        if entry["role"] != "collision":
            row["uv"] = A.summarized_uv(records)
            row["materials"] = A.material_json_checks(doc, structural)
            row["quality"] = frozen_quality(records, doc, structural, file_design, entry["role"] != "lod")
            row["passed"] &= row["quality"]["passed"]
            if entry["role"] in ("component", "model"):
                image = render_pose(asset, entry.get("component", entry.get("state", "state")), resolution)
                row["preview"] = image
        if relative == "model/ship.glb":
            main_records, main_doc, main_export, main_markers = records, doc, structural, markers
        captures[relative] = records
        signatures[relative] = row["geometry_sha256"]
        if entry.get("morph"):
            morph_rows = []
            for weight in (0, .25, .5, .75, 1):
                posed = pose_records(path, entry["morph"], weight)
                topo = A.topology_summary(posed)
                finite_pose = all(finite(p) for record in posed for p in record["vertices"])
                result = {"weight": weight, "passed": topo["passed"] and finite_pose,
                          "topology": topo, "geometry_sha256": geometry_signature(posed)}
                result["grain_pose_evidence"] = {r["name"]: json.loads(r["extras"]["audited_grain_pose_json"])
                    for r in posed if r["extras"].get("audited_grain_pose_json")}
                result["quality"] = frozen_quality(posed, doc, structural, design)
                result["passed"] &= result["quality"]["passed"]
                if weight in (0, 1):
                    result["preview"] = render_pose(asset, entry["component"] + ("_fit" if weight == 0 else "_straight"), resolution)
                morph_rows.append(result)
            row["morph"] = {"name": entry["morph"], "poses": morph_rows,
                            "passed": all(p["passed"] for p in morph_rows) and morph_rows[0]["geometry_sha256"] != morph_rows[-1]["geometry_sha256"]}
            row["passed"] &= row["morph"]["passed"]
            print("PROP_MORPH_AUDIT", relative, [{"weight": p["weight"], "passed": p["passed"],
                   "failed_quality": [r["id"] for r in p["quality"]["matrix"] if r.get("required") and r["status"] != "PASS"],
                   "topology_failures": p["topology"]["failures"]} for p in morph_rows], flush=True)
        file_checks[relative] = row
        print("PROP_FILE_AUDIT", relative, row["passed"],
              [r["id"] for r in row.get("quality", {}).get("matrix", []) if r.get("required") and r["status"] != "PASS"], flush=True)
    if main_records is None:
        raise ValueError("Canonical ship.glb must be a declared state")
    marker_result = marker_check(states.get("anchors", {}), main_markers)
    prop_checks = {"contract": {"passed": True, "errors": []}, "anchors": marker_result}
    collider_checks = {}
    for state in states["states"]:
        visual, collision = captures[state["model"]], captures[state["collision"]]
        def bounds(rows):
            return {"min_blender_m": [min(r["min"][k] for r in rows) for k in range(3)],
                    "max_blender_m": [max(r["max"][k] for r in rows) for k in range(3)]}
        collider_checks[state["id"]] = {"visual_bounds": bounds(visual), "collision_bounds": bounds(collision),
            "scope": "Collider format and closed-solid topology only; bounds recorded for review, not a coverage/equivalence or active engine physics claim"}
    if spec["id"] == "capsized-boat":
        prop_checks["seat"] = seat_check(states, main_records, main_markers)
        prop_checks["float"] = {"passed": True, "parameters": states["float"], "scope": "Exact source metadata, not hydrodynamic simulation"}
    else:
        rows = sorted(states["states"], key=lambda row: row["stage"])
        counts = [file_checks[r["model"]]["imported_triangles"] for r in rows]
        prop_checks["stages"] = {"passed": all(a < b for a, b in zip(counts, counts[1:])) and len({signatures[r["model"]] for r in rows}) == 4,
                                 "stages": [r["stage"] for r in rows], "triangles": counts,
                                 "model_paths": [r["model"] for r in rows],
                                 "geometry_sha256": [signatures[r["model"]] for r in rows]}
        components = {row["id"]: row for row in states["components"]}
        plank = captures[components["repair_plank"]["model"]]
        open_probe = segment_hits(main_records, states["gap"]["probe_gltf_m"], states["gap"]["shell_patterns"])
        fitted_probe = segment_hits(plank, states["gap"]["probe_gltf_m"])
        prop_checks["repair_gap"] = {"passed": bool(open_probe["selected_objects"]) and not open_probe["hit_objects"] and bool(fitted_probe["hit_objects"]),
                                     "open_shell": open_probe, "fitted_plank": fitted_probe}
        peg_records = captures[components["pegs"]["model"]]
        peg_matches = []; unused = set(range(len(peg_records)))
        for index in range(5):
            if "peg_" + str(index) not in main_markers:
                continue
            point = A.ship_to_blender(main_markers["peg_" + str(index)])
            choices = [(peg_records[i]["tree"].find_nearest(point)[3], i) for i in unused]
            choices = [(distance, i) for distance, i in choices if distance is not None]
            if choices:
                distance, chosen = min(choices); unused.remove(chosen)
                peg_matches.append({"anchor": "peg_" + str(index), "mesh": peg_records[chosen]["name"], "surface_distance_m": distance})
        prop_checks["pegs"] = {"passed": len(peg_records) == 5 and len(peg_matches) == 5 and all(r["surface_distance_m"] <= .06 for r in peg_matches), "mesh_objects": len(peg_records),
                               "anchor_matches": peg_matches, "max_anchor_surface_distance_m": .06,
                               "scope": "Five separately addressable peg meshes plus five actual anchor nodes"}
    source_inventory = inventory_evidence(ROOT, spec)
    checks = {"negative_controls": controls, "source_inventory": source_inventory, "export": {"model/ship.glb": main_export},
              "topology": {"model/ship.glb": file_checks["model/ship.glb"]["topology"], "model/collision.glb": file_checks["model/collision.glb"]["topology"]},
              "penetration": file_checks["model/ship.glb"]["penetration"], "uv": A.summarized_uv(main_records),
              "materials": A.material_json_checks(main_doc, main_export), "rig": A.audit_rig(main_records, design),
              "navigation": {name: {"passed": False, "applicable": False, "routes": []} for name in ("model/ship.glb", "model/collision.glb")},
              "walking_width": {"applicable": {"passed": False}},
              "dimensions": A.measured_hull_dimensions(main_records, spec),
              "bounds": {"min_blender_m": [min(r["min"][k] for r in main_records) for k in range(3)], "max_blender_m": [max(r["max"][k] for r in main_records) for k in range(3)]},
              "source_parity": A.source_parity(asset, main_records, main_export),
              "provenance": {"passed": source_inventory["passed"] and bool(spec.get("source_paths")) and bool(design.get("rules", design.get("construction"))),
                             "source_inventory": source_inventory, "source_commit": spec.get("source_commit"), "source_paths": spec.get("source_paths")}}
    lod_counts = [file_checks["model/ship_lod%d.glb" % n]["structure"]["triangles"] for n in (1, 2)]
    checks["lods"] = {"passed": main_export["triangles"] > lod_counts[0] > lod_counts[1], "triangles": [main_export["triangles"], *lod_counts]}
    review = read(asset / "export-review.json")
    checks["render_parity"] = {"present": True, "passed": bool(review.get("passed")) and all(I.digest(child(asset, key)) == value for key, value in review.get("sha256", {}).items()), "review": review}
    matrix_nav = dict(nav)
    matrix_nav.setdefault("player", {"height": 1.85})
    matrix = A.make_matrix(checks, main_records, main_doc, design, matrix_nav)
    for row in matrix:
        if row["id"] in ("J1", "J3", "J4", "player_destinations", "I3"):
            row.update(status="NA", required=False, scope="not_applicable",
                       reason="Nonwalkable construction/rescue prop; actor seat/interaction anchors are tested separately. No onboard navigation or active engine collision claimed.")
            row.pop("evidence", None)
    for name, result in prop_checks.items():
        matrix.append({"id": "prop_" + name, "chapter": "prop", "title": name.replace("_", " "),
                       "required": True, "status": "PASS" if result["passed"] else "FAIL", "scope": "measured", "evidence": result})
    prop_checks["all_delivered_variants"] = {"passed": all(row["passed"] for row in file_checks.values()),
                                            "files": sorted(file_checks)}
    matrix.append({"id": "prop_all_delivered_variants", "chapter": "prop", "required": True,
                   "title": "Every shipped state, component, collision and morph is inspected", "scope": "measured",
                   "status": "PASS" if prop_checks["all_delivered_variants"]["passed"] else "FAIL",
                   "evidence": prop_checks["all_delivered_variants"]})
    hashes = {p.relative_to(asset).as_posix(): I.digest(p) for p in sorted(asset.rglob("*")) if p.is_file() and p.name not in ("validation.json", "README.md") and p.suffix.lower() in (".glb", ".blend", ".json", ".png", ".jpg", ".md")}
    hashes["spec.json"] = I.digest(spec_path)
    result = {"schema": 3, "prop_schema": 1, "vessel": spec["id"], "blender": bpy.app.version_string,
              "passed": all(r["status"] == "PASS" for r in matrix if r["required"]), "matrix": matrix,
              "scope": "Authored prop states and static interaction contracts; no onboard walking, animation controller or fluid simulation claim",
              "checks": checks, "prop_checks": prop_checks, "state_files": file_checks,
              "collider_scope": collider_checks,
              "sha256": hashes, "source_sha256": provenance(ROOT, spec, design)}
    (asset / "validation.json").write_text(json.dumps(A.plain(result), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": result["passed"], "required_checks": sum(bool(r["required"]) for r in matrix), "failed": [r["id"] for r in matrix if r["required"] and r["status"] != "PASS"]}), flush=True)
    if not result["passed"]:
        raise RuntimeError("Prop acceptance failed; inspect validation.json")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", nargs="?")
    parser.add_argument("--asset-dir", type=Path)
    parser.add_argument("--render-resolution", type=int, default=480)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    if args.self_test:
        print(json.dumps({"passed": True, "controls": self_test()}), flush=True)
        if not args.spec:
            return
    if not args.spec:
        parser.error("spec is required unless --self-test is selected")
    path = Path(args.spec).resolve()
    audit_asset(path, args.asset_dir.resolve() if args.asset_dir else path.parent, args.render_resolution)


if __name__ == "__main__":
    main()
