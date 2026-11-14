"""Portable SHA-bound report checks for the two nonwalkable construction/rescue props.

This reuses frozen v2 integrity checks and validates the additive report contract.
It does not rerun geometry, navigation, physics or image-comparison measurements.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import importlib.util
import json
import math
import re


KINDS = {"boat-frame", "capsized-boat"}
LODS = ("model/ship_lod1.glb", "model/ship_lod2.glb")
NA_IDS = ("J1", "J3", "J4", "player_destinations", "I3")
WEIGHTS = (0, .25, .5, .75, 1)
FLOAT = {"lift": 0, "span": 2.4, "beam": .7, "bob": .03, "sway": .09, "tilt": .7}
QUALITY_IDS = {"A4", "B1", "B4", "D1", "D2", "D3", "E1", "E2", "F6", "F7", "F8",
               "G2", "G3", "G4", "G5", "H1", "H2", "H4", "H6"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def relative_path(value):
    require(isinstance(value, str) and bool(value), "Missing relative asset path")
    path = PurePosixPath(value)
    require(not path.is_absolute() and ".." not in path.parts and chr(92) not in value
            and ":" not in value and path.as_posix() == value,
            "Noncanonical or escaping asset path: " + value)
    return value


def valid_digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def passing_matrix(matrix, label):
    require(isinstance(matrix, list) and bool(matrix), label + ": missing checklist")
    ids = set()
    required = 0
    for row in matrix:
        require(isinstance(row, dict), label + ": invalid checklist row")
        identifier = row.get("id")
        require(isinstance(identifier, str) and bool(identifier) and identifier not in ids,
                label + ": missing or duplicate checklist ID")
        ids.add(identifier)
        require(type(row.get("required")) is bool, label + ": required must be boolean")
        if row["required"]:
            required += 1
            require(row.get("status") == "PASS", label + ": required item is not PASS: " + identifier)
    require(required > 0, label + ": no required acceptance checks")
    return required


def quality_check(value, full_detail, label):
    require(isinstance(value, dict) and value.get("passed") is True,
            label + ": missing or failing quality audit")
    require(value.get("full_detail_uv_targets") is full_detail,
            label + ": wrong full-detail UV applicability")
    passing_matrix(value.get("matrix"), label + " quality")
    expected = QUALITY_IDS | ({"F1", "F2", "F3", "F4"} if full_detail else set())
    rows = {row["id"]: row for row in value["matrix"]}
    require(set(rows) == expected, label + ": incomplete or unexpected frozen quality gate set")
    for identifier, row in rows.items():
        if identifier in ("F4", "F8") and row.get("status") == "NA":
            require(row.get("required") is False and row.get("scope") in ("not_applicable", "not_tested")
                    and isinstance(row.get("reason"), str) and bool(row["reason"].strip()),
                    label + ": quality NA needs explicit applicability and reason: " + identifier)
        else:
            require(row.get("required") is True and row.get("status") == "PASS",
                    label + ": mandatory frozen quality gate is not PASS: " + identifier)


def coordinates(value, label):
    require(isinstance(value, list) and len(value) == 3
            and all(type(v) in (int, float) and math.isfinite(v) for v in value),
            "Invalid finite three-coordinate marker: " + label)
    return value


def prop_gates(report, states, matrix):
    names = {"contract", "anchors", "all_delivered_variants"}
    names.update(("seat", "float") if states["kind"] == "capsized-boat"
                 else ("stages", "repair_gap", "pegs"))
    checks = report.get("prop_checks")
    require(isinstance(checks, dict), "Missing measured prop checks")
    for name in names:
        gate = matrix.get("prop_" + name, {})
        require(gate.get("required") is True and gate.get("status") == "PASS",
                "Missing required passing prop gate: prop_" + name)
        require(isinstance(checks.get(name), dict) and checks[name].get("passed") is True,
                "Missing or failing measured prop check: " + name)
    anchors = states.get("anchors")
    require(isinstance(anchors, dict) and bool(anchors), "Missing current state anchors")
    measured = checks["anchors"].get("actual_gltf_m")
    errors = checks["anchors"].get("position_errors_m")
    require(isinstance(measured, dict) and isinstance(errors, dict) and set(errors) == set(anchors)
            and checks["anchors"].get("missing") == [], "Incomplete measured anchor binding")
    for name, expected in anchors.items():
        expected = coordinates(expected, name)
        actual = coordinates(measured.get(name), name + " delivered")
        error = math.dist(expected, actual)
        declared = errors[name]
        require(type(declared) in (int, float) and math.isfinite(declared)
                and 0 <= declared <= .001 and error <= .001 and abs(error - declared) <= 1e-6,
                "Current marker differs from measured GLB anchor: " + name)
    if "expected_gltf_m" in checks["anchors"]:
        require(checks["anchors"]["expected_gltf_m"] == anchors, "Current anchors differ from audit inputs")
    if states["kind"] == "capsized-boat":
        values = states.get("float")
        require(isinstance(values, dict) and set(values) == set(FLOAT)
                and all(type(values[key]) in (int, float) and math.isfinite(values[key])
                        and float(values[key]) == float(expected) for key, expected in FLOAT.items()),
                "Current float metadata differs from source constants")
        require(checks["float"].get("parameters") == values, "Float evidence differs from current state metadata")
        node = states.get("seat", {}).get("node")
        seat = checks["seat"]
        require(node in anchors and seat.get("node") == node and seat.get("source_x_z_correct") is True,
                "Current seat marker differs from measured seat contract")
        require(math.dist(coordinates(seat.get("position_gltf_m"), "measured seat"), anchors[node]) <= .001,
                "Seat evidence differs from current anchor")
        require(abs(anchors[node][0] - .4) <= .001 and abs(anchors[node][2]) <= .001,
                "Seat does not preserve source x/z coordinates")
    else:
        require({"repair_gap", *["peg_" + str(i) for i in range(5)]}.issubset(anchors),
                "Missing source construction/repair markers")


def stage_binding(report, states):
    ordered = sorted(states["states"], key=lambda row: row["stage"])
    paths = [row["model"] for row in ordered]
    counts = [report["state_files"][name].get("imported_triangles") for name in paths]
    signatures = [report["state_files"][name]["geometry_sha256"] for name in paths]
    measured = report["prop_checks"]["stages"]
    require(measured.get("stages") == [row["stage"] for row in ordered]
            and measured.get("model_paths") == paths
            and measured.get("triangles") == counts
            and measured.get("geometry_sha256") == signatures,
            "Current state ordering/paths differ from measured stage evidence")
    require(all(type(count) is int and count > 0 for count in counts)
            and all(a < b for a, b in zip(counts, counts[1:])) and len(set(signatures)) == 4,
            "Construction stages need increasing measured counts and four distinct geometries")
    for row, count in zip(ordered, counts):
        if "triangles" in row:
            require(type(row["triangles"]) is int and row["triangles"] == count,
                    "Declared construction-stage count differs from its actual file audit")


def registered_files(states):
    """Schema 1 has two implicit canonical LODs; an explicit list must agree."""
    registry = {}
    def add(value, role, entry):
        value = relative_path(value)
        require(value.startswith("model/") and PurePosixPath(value).suffix.lower() == ".glb",
                "Declared state is not a model GLB: " + value)
        require(value not in registry, "Duplicate or ambiguous GLB declaration: " + value)
        registry[value] = {"role": role, "entry": entry}

    rows = states.get("states")
    require(isinstance(rows, list) and bool(rows), "Missing authored prop states")
    identifiers = set()
    for row in rows:
        require(isinstance(row, dict), "Invalid state declaration")
        identifier = row.get("id")
        require(isinstance(identifier, str) and bool(identifier) and identifier not in identifiers,
                "Missing or duplicate authored state ID")
        identifiers.add(identifier)
        add(row.get("model"), "model", row)
        add(row.get("collision"), "collision", row)
    components = states.get("components", [])
    require(isinstance(components, list), "Components must be a list")
    component_ids = set()
    for row in components:
        require(isinstance(row, dict) and isinstance(row.get("id"), str) and bool(row["id"])
                and row["id"] not in component_ids, "Missing or duplicate component ID")
        component_ids.add(row["id"])
        add(row.get("model"), "component", row)
        if row.get("collision"):
            add(row["collision"], "collision", row)
    if states["kind"] == "boat-frame":
        stages = [row.get("stage") for row in rows]
        require(all(type(stage) is int for stage in stages) and sorted(stages) == [0, 1, 2, 3],
                "Construction prop must declare stages 0..3 exactly once")
        require({"repair_plank", "pegs", "trim"}.issubset(component_ids),
                "Missing required construction component")
        plank = next(row for row in components if row["id"] == "repair_plank")
        require(plank.get("morph") == "straight", "Repair plank must declare the straight morph")
    else:
        require(len(rows) == 1, "Capsized prop must have one authored static state")
    lod_entries = {}
    if "lods" in states:
        lods = states["lods"]
        require(isinstance(lods, list) and len(lods) == 2, "Explicit LOD list must contain the canonical pair")
        names = []
        for row in lods:
            require(isinstance(row, (str, dict)), "Invalid LOD declaration")
            name = relative_path(row if isinstance(row, str) else row.get("model"))
            names.append(name)
            lod_entries[name] = row if isinstance(row, dict) else {}
            if isinstance(row, dict) and "level" in row:
                require(type(row["level"]) is int and row["level"] in (1, 2)
                        and name == LODS[row["level"] - 1], "LOD level/path mismatch")
        require(sorted(names) == sorted(LODS), "Explicit LOD list differs from the canonical pair")
    for name in LODS:
        add(name, "lod", lod_entries.get(name, {}))
    require(registry.get("model/ship.glb", {}).get("role") == "model"
            and registry.get("model/collision.glb", {}).get("role") == "collision",
            "Canonical model/collision must be declared authored states")
    return registry


def validate_contract(report, states, nav, files):
    """Pure schema/binding checks; files maps actual relative filenames to SHA-256.

    Synthetic inputs are suitable for negative contract controls, not evidence
    that synthetic or unmeasured geometry satisfies the geometric auditor.
    """
    require(isinstance(report, dict) and type(report.get("schema")) is int and report["schema"] >= 3
            and type(report.get("prop_schema")) is int and report["prop_schema"] == 1,
            "Missing v3 prop-schema-1 acceptance report")
    require(report.get("passed") is True and report.get("vessel") in KINDS,
            "Unknown prop or nonpassing report")
    require(isinstance(states, dict) and type(states.get("schema")) is int and states["schema"] == 1
            and states.get("kind") == report["vessel"], "State contract kind/schema differs from the report")
    require(isinstance(nav, dict) and nav.get("routes") == [], "Props must explicitly declare navigation.routes=[]")
    required = passing_matrix(report.get("matrix"), "Prop report")
    matrix = {row["id"]: row for row in report["matrix"]}
    for identifier in NA_IDS:
        row = matrix.get(identifier, {})
        require(row.get("required") is False and row.get("status") == "NA"
                and row.get("scope") == "not_applicable"
                and isinstance(row.get("reason"), str) and bool(row["reason"].strip()),
                "Nonwalkable prop needs explicit justified NA: " + identifier)
    prop_gates(report, states, matrix)
    require(isinstance(files, dict), "Actual file inventory is missing")
    for name, digest in files.items():
        relative_path(name)
        require(valid_digest(digest), "Invalid actual file digest: " + name)
    hashes = report.get("sha256")
    require(isinstance(hashes, dict), "Missing report fingerprints")
    def bound(name):
        name = relative_path(name)
        require(name in files and valid_digest(hashes.get(name)) and hashes[name] == files[name],
                "Missing, stale or unbound file: " + name)
    for name in hashes:
        bound(name)
    for name in ("states.json", "navigation.json", "spec.json"):
        bound(name)
    def preview(name):
        name = relative_path(name)
        require(PurePosixPath(name).suffix.lower() == ".png", "Audit preview must be a PNG: " + name)
        bound(name)
    images = {name for name in files if PurePosixPath(name).suffix.lower() in (".png", ".jpg", ".jpeg")}
    for name in images:
        bound(name)
    registry = registered_files(states)
    shipped = {name for name in files if PurePosixPath(name).suffix.lower() == ".glb"}
    require(shipped == set(registry), "Registered/shipped GLB lists differ: " + str(sorted(shipped ^ set(registry))))
    audited = report.get("state_files")
    require(isinstance(audited, dict) and set(audited) == shipped,
            "Every shipped GLB must have exactly one state-file audit")
    morph_poses = 0
    for name, definition in registry.items():
        row = audited[name]
        role, entry = definition["role"], definition["entry"]
        require(isinstance(row, dict) and row.get("role") == role, "Wrong audit role: " + name)
        require(role == "component" or entry.get("morph") is None,
                "Only a separate component can declare a prop morph: " + name)
        bound(name)
        require(row.get("sha256") == hashes[name], "State-file audit fingerprint differs: " + name)
        for key in ("structure", "topology", "penetration"):
            require(isinstance(row.get(key), dict) and row[key].get("passed") is True,
                    "Missing or failing " + key + " audit: " + name)
        require(row.get("passed") is True and valid_digest(row.get("geometry_sha256")),
                "Missing or failing overall state-file audit: " + name)
        if role != "collision":
            require(isinstance(row.get("materials"), dict) and row["materials"].get("passed") is True,
                    "Missing or failing material semantics: " + name)
            quality_check(row.get("quality"), role != "lod", name)
        if role in ("model", "component"):
            preview(row.get("preview"))
        elif row.get("preview") is not None:
            preview(row["preview"])
        if entry.get("preview") is not None:
            preview(entry["preview"])
        expected_morph = entry.get("morph") if role == "component" else None
        morph = row.get("morph")
        if expected_morph is not None or morph is not None:
            require(expected_morph == "straight" and isinstance(morph, dict)
                    and morph.get("name") == expected_morph and morph.get("passed") is True,
                    "Missing, undeclared or failing straight morph: " + name)
            if morph.get("preview") is not None:
                preview(morph["preview"])
            poses = morph.get("poses")
            require(isinstance(poses, list) and len(poses) == len(WEIGHTS), "Incomplete morph pose sampling: " + name)
            weights = []
            for pose in poses:
                require(isinstance(pose, dict), "Invalid morph pose: " + name)
                weight = pose.get("weight")
                require(type(weight) in (int, float) and math.isfinite(weight), "Invalid morph weight: " + name)
                weights.append(weight)
                require(pose.get("passed") is True and isinstance(pose.get("topology"), dict)
                        and pose["topology"].get("passed") is True and valid_digest(pose.get("geometry_sha256")),
                        "Missing or failing morph pose audit: " + name)
                quality_check(pose.get("quality"), True, name + " morph")
                if weight in (0, 1) or pose.get("preview") is not None:
                    preview(pose.get("preview"))
            require(tuple(weights) == WEIGHTS, "Morph needs ordered weights 0,.25,.5,.75,1: " + name)
            require(poses[0]["geometry_sha256"] == row["geometry_sha256"]
                    and poses[0]["geometry_sha256"] != poses[-1]["geometry_sha256"],
                    "Morph endpoints are unchanged or differ from the audited basis: " + name)
            morph_poses += len(poses)
    if states["kind"] == "boat-frame":
        stage_binding(report, states)
    return {"passed": True, "vessel": report["vessel"], "required_checks": required,
            "state_files": len(audited), "morph_poses": morph_poses, "image_files": len(images)}


def check(asset_dir, source_root=None):
    asset = Path(asset_dir).resolve()
    frozen = Path(__file__).resolve().with_name("v2_integrity.py")
    require(frozen.is_file(), "Frozen sibling v2_integrity.py is required")
    module_spec = importlib.util.spec_from_file_location("_v3_frozen_v2_integrity", frozen)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    base = module.check_report(asset, source_root)
    def read(name):
        return json.loads((asset / name).read_text(encoding="utf-8"))
    report, states, nav = read("validation.json"), read("states.json"), read("navigation.json")
    require(read("spec.json").get("id") == report.get("vessel"), "Spec/report prop ID differs")
    files = {}
    for path in asset.rglob("*"):
        require(path.resolve().is_relative_to(asset), "Asset symlink escapes package: " + str(path))
        if path.is_file():
            files[path.relative_to(asset).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    result = validate_contract(report, states, nav, files)
    result["v2_integrity"] = base
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--asset-dir", type=Path)
    target.add_argument("--all", action="store_true", help="Check prop packages at sailertales/*/states.json")
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()
    try:
        if args.all:
            root = args.source_root.resolve() if args.source_root else Path(__file__).resolve().parents[2]
            paths = sorted((root / "sailertales").glob("*/states.json"))
            results = [check(path.parent, args.source_root) for path in paths]
            print(json.dumps({"passed": True, "prop_assets": len(results), "assets": results}, indent=2))
        else:
            print(json.dumps(check(args.asset_dir, args.source_root), indent=2))
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, "Prop integrity failed: " + str(error) + "\n")


if __name__ == "__main__":
    main()
