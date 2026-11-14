"""Additive detail/interior checks for v5 PoTC ships.

The frozen v4 release contract is always checked first.  These additional checks
decode delivered GLB geometry and images; they never certify a game controller.
Dependencies for the additional portable geometry checks: numpy and Pillow.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
from pathlib import Path
import sys

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import v4_integrity as V
import v5_contract as C
import v5_report_codec as REPORT

GATES = C.DETAIL_GATES
FEATURES = {"deck_planking", "internal_frames", "hatch_joinery", "access_stairs",
            "cabin_joinery", "helm", "anchors", "mooring", "pumps",
            "capstan_windlass", "gun_tackle", "rig_fittings", "stowage",
            "interior_furniture", "lighting"}
REQUIRED_ROLES = {"wood", "deck", "spar", "rope", "canvas", "iron"}
AUDIT_SOURCES = C.AUDIT_SOURCES


def read(path):
    return REPORT.read(path)


def safe(root, path):
    result = (Path(root) / V.relative_path(path)).resolve()
    V.require(result.is_relative_to(Path(root).resolve()), "Detail path leaves asset root")
    return result


def finite_point(value):
    return isinstance(value, list) and len(value) == 3 and all(V.finite_number(x) for x in value)


def evidence_precision(value):
    """Stable serialized evidence across NumPy/CPU reduction implementations.

    Gate decisions use the unrounded measurements. Only the saved diagnostic
    representation is rounded, far below every physical tolerance. Geometry,
    images, frozen v4 results and thresholds are never modified.
    """
    if isinstance(value, float):
        V.require(math.isfinite(value), 'Nonfinite detail measurement')
        return round(value, 8)
    if isinstance(value, dict):
        return {key:evidence_precision(item) for key,item in value.items()}
    if isinstance(value, (list,tuple)):
        return [evidence_precision(item) for item in value]
    return value


def matrix(node):
    if "matrix" in node:
        return np.array(node["matrix"], dtype=float).reshape((4, 4), order="F")
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    rot = np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                    [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                    [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
    result = np.eye(4)
    result[:3, :3] = rot @ np.diag(node.get("scale", [1, 1, 1]))
    result[:3, 3] = node.get("translation", [0, 0, 0])
    return result


def geometry(path):
    """Decode every actual visible mesh instance into Blender world metres."""
    doc, binary = V.frozen().read_glb(path)
    nodes, records, used = doc.get("nodes", []), {}, set()
    conversion = np.array([[1., 0, 0], [0, 0, -1.], [0, 1., 0]])
    cache = {}

    def acc(index):
        if index not in cache:
            cache[index] = np.array(V.decoded_accessor(doc, binary, index))
        return cache[index]

    def visit(index, parent, active):
        V.require(index not in active, "Cyclic v5 geometry hierarchy")
        node = nodes[index]
        world = parent @ matrix(node)
        if "mesh" in node:
            name = node.get("name")
            V.require(isinstance(name, str) and name not in records, "Duplicate/missing v5 mesh instance name")
            triangles = []
            material_names = set()
            for primitive in doc["meshes"][node["mesh"]].get("primitives", []):
                V.require(primitive.get("mode", 4) == 4, "v5 visual primitive must be triangles")
                vertices = acc(primitive["attributes"]["POSITION"])
                vertices = ((vertices @ world[:3, :3].T) + world[:3, 3]) @ conversion.T
                ids = (acc(primitive["indices"]).reshape(-1).astype(int) if "indices" in primitive
                       else np.arange(len(vertices)))
                triangles.append(vertices[ids.reshape((-1, 3))])
                if "material" in primitive:
                    used.add(primitive["material"])
                    material_names.add(doc["materials"][primitive["material"]]["name"])
            tri = np.concatenate(triangles) if triangles else np.empty((0, 3, 3))
            V.require(len(tri) > 0 and np.isfinite(tri).all(), "Missing/nonfinite actual v5 mesh geometry")
            areas = np.linalg.norm(np.cross(tri[:, 1]-tri[:, 0], tri[:, 2]-tri[:, 0]), axis=1)/2
            records[name] = {"name": name, "triangles": tri, "extras": node.get("extras", {}),
                             "min": tri.min(axis=(0, 1)).tolist(), "max": tri.max(axis=(0, 1)).tolist(),
                             "surface_area_m2": float(areas.sum()), "materials": sorted(material_names)}
        for child in node.get("children", []):
            visit(child, world, active | {index})

    scene = doc.get("scenes", [{}])[doc.get("scene", 0)]
    for index in scene.get("nodes", []):
        visit(index, np.eye(4), set())
    V.require(records, "No actual visible geometry in v5 ship")
    return records, doc, binary, used


class Rays:
    """Vectorized two-sided Moller-Trumbore tests against actual triangles."""
    def __init__(self, records, names=None, exclude=()):
        selected = set(records) if names is None else set(names)
        selected.difference_update(exclude)
        arrays, labels = [], []
        for name in sorted(selected):
            if name in records:
                arrays.append(records[name]["triangles"])
                labels.extend([name] * len(records[name]["triangles"]))
        self.triangles = np.concatenate(arrays) if arrays else np.empty((0, 3, 3))
        self.labels = labels
        self.a = self.triangles[:, 0]
        self.e1 = self.triangles[:, 1] - self.a
        self.e2 = self.triangles[:, 2] - self.a
        self.minimum = self.triangles.min(axis=1) if len(self.triangles) else np.empty((0, 3))
        self.maximum = self.triangles.max(axis=1) if len(self.triangles) else np.empty((0, 3))

    def hit(self, origin, direction, maximum):
        origin, direction = np.array(origin, float), np.array(direction, float)
        direction = direction / np.linalg.norm(direction)
        endpoint = origin + direction * maximum
        low, high = np.minimum(origin, endpoint)-1e-7, np.maximum(origin, endpoint)+1e-7
        candidates = np.where(np.all(self.maximum >= low, axis=1) & np.all(self.minimum <= high, axis=1))[0]
        if not len(candidates):
            return None
        p = np.cross(np.broadcast_to(direction, (len(candidates), 3)), self.e2[candidates])
        det = np.einsum("ij,ij->i", self.e1[candidates], p)
        valid = np.abs(det) > 1e-10
        inv = np.divide(1., det, out=np.zeros_like(det), where=valid)
        tvec = origin - self.a[candidates]
        u = np.einsum("ij,ij->i", tvec, p) * inv
        q = np.cross(tvec, self.e1[candidates])
        v = q @ direction * inv
        distance = np.einsum("ij,ij->i", self.e2[candidates], q) * inv
        valid &= (u >= -1e-7) & (v >= -1e-7) & (u+v <= 1+1e-7) & (distance >= 1e-6) & (distance <= maximum+1e-7)
        if not valid.any():
            return None
        found = np.where(valid, distance, np.inf).argmin()
        return {"distance_m": float(distance[found]), "node": self.labels[candidates[found]],
                "position": (origin + direction*distance[found]).tolist()}


def selected_nodes(value, records, label, minimum=1):
    V.require(isinstance(value, list) and len(value) >= minimum and len(value) == len(set(value))
              and all(isinstance(n, str) and n in records for n in value),
              "Missing/duplicate/nonmesh detail nodes: " + label)
    for name in value:
        V.require(len(records[name]["triangles"]) >= 4 and records[name]["surface_area_m2"] >= .00001,
                  "Empty/token geometry cannot count as a feature: " + name)
    return value


def research(asset, contract, spec):
    path = contract.get("research_path")
    result = {"passed": False, "path": path, "errors": []}
    try:
        doc = read(safe(asset, path))
        V.require(doc.get("ship_id", doc.get("id")) == spec["id"], "Historical layout research belongs to another vessel type")
        sources, decisions = doc.get("sources"), doc.get("decisions")
        V.require(isinstance(sources, list) and len(sources) >= 2, "At least two inspectable historical sources required per type")
        urls = set()
        for source in sources:
            V.require(isinstance(source, dict) and isinstance(source.get("url"), str)
                      and source["url"].startswith("https://") and source.get("title")
                      and source.get("applies_to", source.get("application")),
                      "Historical source requires URL, title and applied layout feature")
            urls.add(source["url"])
        V.require(len(urls) >= 2 and isinstance(decisions, list) and len(decisions) >= 3,
                  "Research requires distinct sources and at least three applied layout decisions")
        for decision in decisions:
            V.require(decision.get("feature") and decision.get("basis") and decision.get("source_urls")
                      and set(decision["source_urls"]).issubset(urls), "Unbound historical layout decision")
        V.require(isinstance(doc.get("limitations"), list) and bool(doc["limitations"]), "Reconstruction limits must be explicit")
        result.update(passed=True, sha256=V.digest(safe(asset, path)), sources=len(urls), decisions=len(decisions))
    except (ValueError, TypeError, OSError, KeyError) as error:
        result["errors"].append(str(error))
    return result


def features(contract, records, spec):
    rows, errors, seen, assigned = [], [], set(), {}
    groups = contract.get("feature_groups", [])
    for group in groups:
        try:
            identifier = group["id"]
            V.require(identifier in FEATURES and identifier not in seen, "Unknown/duplicate detail feature group")
            seen.add(identifier)
            if group.get("required") is False:
                V.require(isinstance(group.get("reason"), str) and len(group["reason"].strip()) >= 30,
                          "Feature omission requires a concrete researched type-specific reason")
                allowed = {"gun_tackle", "cabin_joinery", "lighting", "pumps"}
                if spec.get("detailed_layout", {}).get("kind") == "open_boat":
                    allowed |= {"hatch_joinery", "access_stairs", "capstan_windlass"}
                V.require(identifier in allowed,
                          "Fundamental structural/equipment feature cannot be omitted")
                V.require(identifier != "gun_tackle" or not spec.get("gun_count", V.STOCK_GUNS[spec["family"]]),
                          "Armed type cannot omit gun tackle")
                rows.append({"id": identifier, "required": False, "reason": group["reason"], "passed": True})
                continue
            V.require(group.get("required") is True, "Feature applicability must be explicit")
            count = group.get("minimum_instances")
            V.require(type(count) is int and count >= 1, "Invalid minimum feature instances")
            fixed_minimum = {"deck_planking": 20, "internal_frames": 6,
                             "hatch_joinery": 4, "access_stairs": 3, "cabin_joinery": 3}.get(identifier, 1)
            count = max(count, fixed_minimum)
            names = selected_nodes(group.get("nodes"), records, identifier, count)
            for name in names:
                V.require(name not in assigned, "One mesh cannot inflate two feature groups: " + name)
                assigned[name] = identifier
            area = sum(records[name]["surface_area_m2"] for name in names)
            if identifier in {"deck_planking", "internal_frames"}:
                span = max(records[n]["max"][1] for n in names)-min(records[n]["min"][1] for n in names)
                V.require(span >= spec["length"]*(.65 if identifier == "deck_planking" else .55),
                          "Structural feature covers a token patch instead of the vessel: " + identifier)
            rows.append({"id": identifier, "required": True, "passed": True, "nodes": names,
                         "actual_mesh_instances": len(names), "minimum_instances": count,
                         "surface_area_m2": area,
                         "bounds": {"min": np.min([records[n]["min"] for n in names], axis=0).tolist(),
                                    "max": np.max([records[n]["max"] for n in names], axis=0).tolist()}})
        except (ValueError, KeyError, TypeError) as error:
            errors.append(str(error))
    if seen != FEATURES:
        errors.append("Missing detail feature groups: " + ", ".join(sorted(FEATURES-seen)))
    planks = [r for r in records.values() if r["extras"].get("physical_plank")]
    if len(planks) < max(30, math.ceil(spec["length"])):
        errors.append("Deck requires actual separate physical planks, not added texture/count-only mesh")
    projected = sum(float(np.abs(np.cross(r["triangles"][:,1]-r["triangles"][:,0],
                                           r["triangles"][:,2]-r["triangles"][:,0])[:,2]).sum())/4
                    for r in planks)
    minimum_coverage = .20*spec["length"]*spec["beam"]
    if projected < minimum_coverage:
        errors.append("Physical plank area is below 20% of nominal deck footprint; tiny meshes cannot inflate the detail count")
    return {"passed": not errors, "groups": rows, "errors": errors, "physical_plank_instances": len(planks),
            "physical_plank_projected_area_m2": projected, "minimum_projected_plank_area_m2": minimum_coverage,
            "scope": "Concrete exported mesh membership and physical extent; node/triangle totals alone confer no detail score."}


def battery_inventory(room, contract, records):
    """Recheck a declared battery station against its actual truck/floor meshes."""
    rows,errors,seen=[],[],set()
    identifier=room['id']
    declared=room.get('battery_assemblies',[])
    global_rows=[row for row in contract.get('battery_floor_bindings',[]) if row.get('room_id')==identifier]
    if not declared:
        errors.append('Gun deck has no actual floor-bound battery assembly: '+identifier)
    if sorted(declared,key=lambda r:r.get('barrel_node',''))!=sorted(global_rows,key=lambda r:r.get('barrel_node','')):
        errors.append('Room/global battery floor inventories differ: '+identifier)
    floor_names=set(room.get('floor_nodes',[]));floor_rays=Rays(records,floor_names)
    for binding in declared:
        try:
            barrel=binding.get('barrel_node')
            V.require(binding.get('room_id')==identifier and binding.get('tolerance_m')==.20,
                      'Battery binding changed its room or existing 0.20m support tolerance')
            V.require(barrel in records and records[barrel]['extras'].get('role')=='cannon_barrel'
                      and barrel not in seen,'Battery inventory requires a distinct actual cannon barrel')
            seen.add(barrel)
            other_rooms={r.get('room_id') for r in contract.get('battery_floor_bindings',[]) if r.get('barrel_node')==barrel}
            V.require(other_rooms=={identifier},'One gun station was assigned to multiple deck floors')
            assembly=selected_nodes(binding.get('assembly_nodes'),records,identifier+' actual battery assembly',3)
            V.require(barrel in assembly and set(assembly).issubset(room.get('furnishing_nodes',[])),
                      'Battery assembly is not part of this room inventory')
            tag=barrel.removeprefix('gun_barrel_')
            V.require(any(name.startswith(('gun_cheek_'+tag+'_','gun_carriage_'+tag+'_','gun_axle_'+tag+'_')) for name in assembly),
                      'Battery inventory lacks its actual carriage')
            V.require(any(records[name]['extras'].get('kind')=='rope' and
                          records[name]['extras'].get('detail_feature')=='gun_tackle' for name in assembly),
                      'Battery inventory lacks actual breeching/tackle rope geometry')
            supports=binding.get('support_samples',[]);wheels=set();measured=[]
            V.require(isinstance(supports,list),'Battery truck support samples are missing')
            for sample in supports:
                wheel=sample.get('wheel_node');floor=sample.get('floor_node');point=sample.get('sample_blender_m')
                V.require(wheel in assembly and wheel.startswith('gun_wheel_'+tag+'_') and wheel not in wheels
                          and floor in floor_names and finite_point(point),'Invalid actual truck/floor support member')
                wheels.add(wheel);record=records[wheel]
                mid=(np.array(record['min'])+np.array(record['max']))/2;bottom=record['min'][2]
                V.require(abs(point[0]-mid[0])<=.02501 and abs(point[1]-mid[1])<=.00001
                          and abs(point[2]-(bottom+.20))<=.00001,
                          'Battery support ray is not attached to the actual truck bottom')
                hit=floor_rays.hit(point,[0,0,-1],.40)
                named_hit=Rays(records,[floor]).hit(point,[0,0,-1],.40)
                V.require(hit and named_hit and abs(hit['distance_m']-named_hit['distance_m'])<=.00001,
                          'Actual truck ray does not reach its declared supporting floor')
                error=abs(bottom-named_hit['position'][2])
                V.require(error<=.20 and V.finite_number(sample.get('floor_z_m'))
                          and abs(sample['floor_z_m']-named_hit['position'][2])<=.00001
                          and abs(sample.get('wheel_bottom_z_m',math.inf)-bottom)<=.00001
                          and abs(sample.get('contact_error_m',math.inf)-error)<=.00001,
                          'Recorded battery support is on the wrong physical deck or has stale measurements')
                measured.append({'wheel_node':wheel,'floor_node':floor,'point':point,
                                 'wheel_bottom_z_m':bottom,'measured_floor_z_m':named_hit['position'][2],
                                 'contact_error_m':error,'passed':True})
            V.require(len(wheels)>=2,'Battery assembly requires two distinct supported actual trucks')
            rows.append({'barrel_node':barrel,'assembly_nodes':assembly,'support_samples':measured,'passed':True})
        except (ValueError,KeyError,TypeError) as error:
            errors.append(str(error))
    return {'passed':not errors,'room_id':identifier,'assemblies':rows,'errors':errors,
            'scope':'Actual gun/carriage/tackle meshes and truck-bottom rays against this room\'s floor; existing 0.20m support tolerance and 0.40m ray length.'}


def interiors(contract, records, spec):
    rays = Rays(records)
    rows, errors, ids = [], [], set()
    for room in contract.get("interiors", []):
        identifier = room.get("id")
        try:
            V.require(isinstance(identifier, str) and identifier and identifier not in ids, "Missing/duplicate interior ID")
            ids.add(identifier)
            open_well = room.get("kind") == "open_well"
            V.require(room.get("kind") in {"hold", "cabin", "gun_deck", "crew_space", "open_well"}, "Unknown interior kind")
            V.require(not open_well or (spec.get("detailed_layout", {}).get("kind") == "open_boat"
                                       and room.get("open_top") is True),
                      "Open well exception requires the researched open-boat construction")
            floors = selected_nodes(room.get("floor_nodes"), records, identifier+" floor")
            if not open_well:
                selected_nodes(room.get("ceiling_nodes"), records, identifier+" ceiling")
            selected_nodes(room.get("wall_nodes"), records, identifier+" walls")
            selected_nodes(room.get("frame_nodes"), records, identifier+" frames", 2)
            selected_nodes(room.get("furnishing_nodes"), records, identifier+" furnishings", 2)
            minimum = 1.6 if open_well else room.get("minimum_headroom_m")
            V.require(V.finite_number(minimum) and minimum >= 1.6, "Interior usable clear height must be at least 1.6m")
            samples = room.get("clearance_samples")
            V.require(isinstance(samples, list) and len(samples) >= 3 and all(finite_point(p) for p in samples),
                      "At least three actual clear interior samples required")
            V.require(max(math.dist(a, b) for a in samples for b in samples) >= 1.2,
                      "Interior samples must span a meaningful space, not one repeated point")
            measured = []
            for point in samples:
                down = rays.hit(point, [0, 0, -1], .20)
                up = rays.hit(point, [0, 0, 1], minimum if open_well else 5)
                headroom = up["distance_m"] + (down["distance_m"] if down else 0) if up else None
                overhead_nodes = set(room.get("ceiling_nodes", [])) | set(room.get("frame_nodes", []))
                passed = bool(down and down["node"] in floors and
                              ((not up) if open_well else (up and up["node"] in overhead_nodes and headroom >= minimum)))
                measured.append({"point": point, "floor_hit": down, "overhead_hit": up,
                                 "headroom_m": headroom, "passed": passed})
            battery=battery_inventory(room,contract,records) if room['kind']=='gun_deck' else None
            passed=all(s['passed'] for s in measured) and (battery is None or battery['passed'])
            rows.append({"id": identifier, "kind": room["kind"], "passed": passed,
                         "minimum_headroom_m": minimum, "samples": measured,
                         "floor_nodes": floors, "ceiling_nodes": room.get("ceiling_nodes", []),
                         "wall_nodes": room["wall_nodes"], "frame_nodes": room["frame_nodes"],
                         "furnishing_nodes": room["furnishing_nodes"]})
            if battery is not None:rows[-1]['battery_inventory']=battery
            if not rows[-1]["passed"]:
                errors.append("Interior floor/headroom or actual battery inventory failed: " + identifier)
        except (ValueError, KeyError, TypeError) as error:
            errors.append(str(error))
    expected = "open_well" if spec.get("detailed_layout", {}).get("kind") == "open_boat" else "hold"
    if not rows or not any(row["kind"] == expected for row in rows):
        errors.append("Vessel requires an actual fitted " + expected)
    return {"passed": not errors, "rooms": rows, "errors": errors,
            "scope": "Actual floor/ceiling triangles and authored interior framing/furniture; geometric access only, no controller certification."}


def portals(contract, records, spec):
    rows, errors, ids = [], [], set()
    for portal in contract.get("portals", []):
        identifier = portal.get("id")
        try:
            V.require(isinstance(identifier, str) and identifier and identifier not in ids, "Missing/duplicate portal ID")
            ids.add(identifier)
            kind = portal.get("kind")
            V.require(kind in {"hatch", "door"} and finite_point(portal.get("center")), "Portal requires kind and finite actual center")
            width = portal.get("width_m")
            dimension = portal.get("depth_m") if kind == "hatch" else portal.get("height_m")
            V.require(V.finite_number(width) and width >= .65 and V.finite_number(dimension)
                      and dimension >= (.7 if kind == "hatch" else 1.6), "Undersized hatch/door aperture")
            axis = portal.get("axis")
            V.require(finite_point(axis), "Portal axis required")
            axis = np.array(axis, float)
            expected = np.array([0, 0, 1.] if kind == "hatch" else [0, 1., 0])
            V.require(abs(float(axis @ expected)) >= .999 and abs(float(np.linalg.norm(axis))-1) < .001,
                      "Portal must use vertical hatch or longitudinal door axis")
            frame = selected_nodes(portal.get("frame_nodes"), records, identifier+" frame", 3)
            access = selected_nodes(portal.get("access_nodes", []), records, identifier+" stair/ladder", 2 if kind == "hatch" else 0)
            V.require(not set(frame) & set(access), "Portal joinery cannot double-count as access stairs")
            frame_min = np.min([records[n]["min"] for n in frame], axis=0)
            frame_max = np.max([records[n]["max"] for n in frame], axis=0)
            frame_center = np.array(portal["center"], float)
            cross_index = 1 if kind == "hatch" else 2
            V.require(frame_min[0] <= frame_center[0]-width/2+.12
                      and frame_max[0] >= frame_center[0]+width/2-.12
                      and frame_min[cross_index] <= frame_center[cross_index]-dimension/2+.12
                      and frame_max[cross_index] >= frame_center[cross_index]+dimension/2-.12,
                      "Actual frame does not surround its claimed aperture: " + identifier)
            if kind == "hatch":
                access_min = np.min([records[n]["min"] for n in access], axis=0)
                access_max = np.max([records[n]["max"] for n in access], axis=0)
                V.require(access_max[2]-access_min[2] >= .45,
                          "Hatch access geometry has no meaningful stair/ladder descent")
            for name in access:
                V.require(records[name]["extras"].get("kind") in {"ladder", "stair", "surface", "fitting"},
                          "Portal access must be real stair/ladder geometry")
            # Stair treads are permitted in their own opening, deck/hull/lids are
            # never excluded.  This catches rooms sealed beneath intact decks.
            excluded = access if kind == "hatch" else []
            V.require(not any(records[n]["extras"].get("physical_plank")
                              or records[n]["extras"].get("kind") == "hull" for n in excluded),
                      "Deck/hull geometry cannot be excluded from opening tests")
            rays = Rays(records, exclude=excluded)
            center = np.array(portal["center"], float)
            cross = np.array([0, 1., 0] if kind == "hatch" else [0, 0, 1.])
            blockers, samples = [], []
            for a in np.linspace(-.38, .38, 5):
                for b in np.linspace(-.38, .38, 5):
                    point = center + [a*width, 0, 0] + b*dimension*cross
                    start = point - axis*.28
                    hit = rays.hit(start, axis, .56)
                    sample = {"point": point.tolist(), "blocker": hit}
                    samples.append(sample)
                    if hit:
                        blockers.append(hit)
            passed = not blockers
            rows.append({"id": identifier, "kind": kind, "from": portal.get("from"), "to": portal.get("to"),
                         "passed": passed, "width_m": width,
                         "depth_m" if kind == "hatch" else "height_m": dimension,
                         "center": portal["center"], "axis": portal["axis"], "frame_nodes": frame,
                         "access_nodes": access, "grid_samples": len(samples), "samples": samples,
                         "excluded_actual_stair_nodes": excluded, "blockers": blockers})
            if not passed:
                errors.append("Real hatch/door opening is blocked: " + identifier)
        except (ValueError, KeyError, TypeError) as error:
            errors.append(str(error))
    if spec.get("detailed_layout", {}).get("kind") != "open_boat" and (not rows or not any(row["kind"] == "hatch" for row in rows)):
        errors.append("At least one real open hatch required")
    return {"passed": not errors, "portals": rows, "errors": errors,
            "scope": "5x5 rays through inner 76% aperture and 0.56m local wall/deck slab; only explicitly named hatch stair geometry excluded."}


def access(contract, records, rooms, openings, spec):
    errors, rows, identifiers = [], [], set()
    # Keep diagnostics useful when an independent room gate (for example an
    # unfinished furnishing ledger) fails. Acceptance still requires both.
    room_ids = {r["id"] for r in contract.get("interiors", []) if isinstance(r.get("id"), str)}
    graph = {name: set() for name in room_ids | {"main_deck"}}
    portal_pairs = set()
    for portal in openings.get("portals", []):
        first, second = portal.get("from"), portal.get("to")
        if portal["passed"] and first in graph and second in graph and first != second:
            portal_pairs.add(frozenset([first, second]))
    if spec.get("detailed_layout", {}).get("kind") == "open_boat":
        portal_pairs.update(frozenset(["main_deck", r["id"]]) for r in contract.get("interiors", []) if r["kind"] == "open_well")
    rays = Rays(records)
    for route in contract.get("routes", []):
        try:
            name = route.get("id")
            V.require(isinstance(name, str) and name and name not in identifiers, "Missing/duplicate geometric access ID")
            identifiers.add(name)
            first, second = route.get("from"), route.get("to")
            V.require(frozenset([first, second]) in portal_pairs, "Geometric access lacks an actual clear named portal")
            mode = route.get("mode", "walk")
            V.require(mode in {"walk", "climb", "geometric_passage"}, "Unknown static access mode")
            excluded = []
            if mode == "climb":
                matching = [p for p in openings.get("portals", []) if p["kind"] == "hatch"
                            and p["passed"] and frozenset([p["from"], p["to"]]) == frozenset([first, second])]
                V.require(matching, "Climb access requires an actual open hatch and physical ladder")
                excluded = sorted(set(n for p in matching for n in p["access_nodes"]))
                V.require(len(excluded) >= 6, "Climb access requires actual ladder rungs and stringers")
                V.require(not any(records[n]["extras"].get("physical_plank")
                                  or records[n]["extras"].get("kind") == "hull" for n in excluded),
                          "Climb shaft cannot exclude deck or hull geometry")
            route_rays = Rays(records, exclude=excluded) if excluded else rays
            points = route.get("points")
            V.require(isinstance(points, list) and len(points) >= 2 and all(finite_point(p) for p in points), "Access polyline missing")
            radius = route.get("clearance_radius_m")
            V.require(V.finite_number(radius) and radius >= .24, "Access requires at least 0.48m clear body width")
            height = route.get("clearance_height_m", 1.6)
            V.require(V.finite_number(height) and height >= 1.6, "Access clear height too low")
            length, failures, samples = 0., [], 0
            for a, b in zip(points, points[1:]):
                a, b = np.array(a, float), np.array(b, float)
                distance = float(np.linalg.norm(b-a))
                V.require(distance > .001, "Repeated access path point")
                length += distance
                # Segment at shoulder height must be unobstructed.  The floor
                # route is authored on stair treads; no walking physics claimed.
                offset = np.array([0, 0, min(.9, height*.55)])
                hit = route_rays.hit(a+offset, b-a, distance)
                if hit:
                    failures.append({"test": "shoulder_segment", **hit})
                for t in np.linspace(0, 1, max(2, math.ceil(distance/.3)+1)):
                    foot = a+(b-a)*t
                    samples += 1
                    center = foot+offset
                    for axis in ([1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0]):
                        hit = route_rays.hit(center, axis, radius)
                        if hit:
                            failures.append({"test": "body_width", "sample": foot.tolist(), **hit})
                    hit = route_rays.hit(foot+[0, 0, .15], [0, 0, 1], height-.15)
                    if hit:
                        failures.append({"test": "headroom", "sample": foot.tolist(), **hit})
            V.require(length >= .8, "Token access line cannot connect an interior")
            passed = not failures
            if passed:
                graph[first].add(second)
                graph[second].add(first)
            rows.append({"id": name, "from": first, "to": second, "passed": passed,
                         "mode": mode, "excluded_actual_ladder_nodes": excluded,
                         "length_m": length, "samples": samples, "radius_m": radius,
                         "height_m": height, "failure_count": len(failures), "failures": failures[:30]})
            if not passed:
                errors.append("Interior access geometry blocked: " + name)
        except (ValueError, KeyError, TypeError) as error:
            errors.append(str(error))
    reached, pending = set(), ["main_deck"]
    while pending:
        current = pending.pop()
        if current not in reached:
            reached.add(current)
            pending.extend(graph[current]-reached)
    disconnected = sorted(room_ids-reached)
    if disconnected:
        errors.append("Interiors disconnected from main deck: " + ", ".join(disconnected))
    return {"passed": not errors, "routes": rows, "errors": errors,
            "reachable_spaces": sorted(reached), "disconnected_spaces": disconnected,
            "scope": "Actual portal graph, body-width rays, headroom rays and shoulder-height segments; no player movement/controller certification."}


def windows(contract, records, spec):
    """A pane on a solid transom is decoration, not a real cabin light."""
    errors, rows, ids = [], [], set()
    declared = contract.get("windows", [])
    if spec.get("detailed_layout", {}).get("cabin") and not declared:
        errors.append("A fitted stern cabin requires actual glazed window apertures")
    for window in declared:
        identifier = window.get("id")
        try:
            V.require(isinstance(identifier, str) and identifier and identifier not in ids, "Missing/duplicate window ID")
            ids.add(identifier)
            V.require(window.get("kind") == "window" and window.get("from") == "cabin"
                      and window.get("to") == "exterior", "Cabin light endpoints/kind invalid")
            hull = selected_nodes([window.get("hull_node")], records, identifier+" actual timber transom")
            selected_nodes(window.get("frame_nodes"), records, identifier+" actual window frame", 4)
            panes = selected_nodes(window.get("glass_nodes"), records, identifier+" actual closed glass panes")
            V.require(finite_point(window.get("axis")), "Window needs finite physical normal")
            axis = np.array(window["axis"], float)
            V.require(abs(np.linalg.norm(axis)-1) <= .01, "Window normal is not unit length")
            timber = Rays(records, exclude=panes)
            measured = []
            for name in panes:
                pane = records[name]
                V.require(any("glass" in material.lower() for material in pane["materials"]),
                          "Declared window glass has no actual glass material")
                center = (np.array(pane["min"])+np.array(pane["max"]))/2
                origin = center-axis*.42
                glass_hit = Rays(records, [name]).hit(origin, axis, .85)
                blocker = timber.hit(origin, axis, .85)
                measured.append({"pane": name, "center": center.tolist(), "glass_hit": glass_hit,
                                 "timber_blocker": blocker, "passed": bool(glass_hit and not blocker)})
            passed = all(row["passed"] for row in measured)
            rows.append({"id": identifier, "passed": passed, "hull_node": hull[0],
                         "axis": window["axis"], "pane_samples": measured,
                         "frame_nodes": window["frame_nodes"], "glass_nodes": panes})
            if not passed:
                errors.append("A claimed stern light is missing glass or blocked by real timber: " + identifier)
        except (ValueError, KeyError, TypeError) as error:
            errors.append(str(error))
    return {"passed": not errors, "windows": rows, "errors": errors,
            "scope": "Ray through the centre of every actual closed glazing pane, excluding only its window's glass and retaining every timber/frame/deck triangle."}


def image_stats(raw):
    with Image.open(io.BytesIO(raw)) as image:
        size = list(image.size)
        # Deterministic bounded sample avoids huge allocations for 8K maps.
        image.thumbnail((512, 512), Image.Resampling.BOX)
        pixels = np.asarray(image.convert("RGB"), dtype=np.float64)/255.
    return {"dimensions": size, "sha256": hashlib.sha256(raw).hexdigest(),
            "std_rgb": pixels.std(axis=(0, 1)).tolist(),
            "range_rgb": np.ptp(pixels, axis=(0, 1)).tolist(),
            "sample_dimensions": [pixels.shape[1], pixels.shape[0]]}


def materials(doc, binary, used, frozen_quality):
    rows, errors, roles, images = [], [], set(), {}
    uv = frozen_quality.get("uv", {}).get("materials", {})
    for index in sorted(used):
        material = doc["materials"][index]
        extras = material.get("extras", {})
        role = extras.get("material_role")
        name = material["name"]
        if role:
            roles.add(role)
        try:
            V.require(extras.get("guide_pbr_v5") is True and isinstance(role, str) and role,
                      "Used material lacks v5 PBR role: " + name)
            slots = {"basecolor": material.get("pbrMetallicRoughness", {}).get("baseColorTexture"),
                     "normal": material.get("normalTexture"),
                     "orm": material.get("pbrMetallicRoughness", {}).get("metallicRoughnessTexture")}
            detail = {}
            for slot, texture in slots.items():
                V.require(isinstance(texture, dict), "Missing exported " + slot + " map: " + name)
                source = doc["textures"][texture["index"]]["source"]
                if source not in images:
                    images[source] = image_stats(V.frozen().image_bytes(doc, binary, doc["images"][source]))
                stat = images[source]
                V.require(min(stat["dimensions"]) >= 256, "Tiny/placeholder v5 image: " + name)
                if role != "glass":
                    if slot == "basecolor":
                        V.require(max(stat["std_rgb"]) > .003, "Uniform exported basecolor: " + name)
                    elif slot == "normal":
                        V.require(max(stat["std_rgb"][:2]) > .001, "Flat exported normal map: " + name)
                    else:
                        V.require(stat["std_rgb"][1] > .003, "Uniform exported roughness map: " + name)
                detail[slot] = {"image_index": source, **stat}
            V.require(len({detail[s]["sha256"] for s in detail}) == 3, "One image reused across color/data roles: " + name)
            density = uv.get(name, {}).get("texel_density_px_m", {}).get("median")
            minimum = 2048 if role in {"iron", "brass"} else 1024 if role in {"wood", "deck", "spar", "paintHull", "paintTrim", "seam"} else 512
            if role != "glass":
                V.require(V.finite_number(density) and density >= minimum*.98,
                          "Material density below old Brig role benchmark: " + name)
            rows.append({"name": name, "role": role, "passed": True, "maps": detail,
                         "median_density_px_m": density, "benchmark_minimum_px_m": minimum})
        except (ValueError, KeyError, TypeError, OSError) as error:
            errors.append(str(error))
    if not REQUIRED_ROLES.issubset(roles):
        errors.append("Missing actual used material roles: " + ", ".join(sorted(REQUIRED_ROLES-roles)))
    return {"passed": not errors, "materials": rows, "errors": errors,
            "roles": sorted(roles), "scope": "Actual embedded map content/role separation and independently frozen measured full-detail UV density."}


def reviewed_gun_decks(contract, views, rendered):
    """Each authored battery room needs its own reviewed intact evidence."""
    return C.reviewed_gun_decks(contract,views,rendered)


def visual_review(asset, contract):
    path = contract.get("visual_review_path", "detail-review.json")
    try:
        review = read(safe(asset, path))
        renders = read(asset/"detail-render.json")
        V.require(renders.get("schema") == 5
                  and renders.get("model_sha256") == V.digest(safe(asset, renders.get("model_path"))),
                  "Actual GLB detail render provenance is absent or stale")
        V.require(renders.get("renderer_sha256") == V.digest(HERE/"v5_review.py"),
                  "Detail render used an unrecorded/stale renderer")
        rendered = {view["path"]: view for view in renders.get("views", [])}
        V.require(review.get("schema") == 5 and review.get("decision") == "PASS"
                  and isinstance(review.get("reviewer"), str) and review["reviewer"].strip(), "Missing actual v5 visual review")
        V.require(review.get("reference") == "Bryg Mewa PR 3", "Visual review must compare the original detailed Brig")
        views = review.get("views")
        V.require(isinstance(views, list) and len(views) >= 3, "Visual review needs deck, interior and hull/rig views")
        categories = set()
        for view in views:
            V.require(view.get("category") in {"deck", "interior", "hull_rig"}, "Unknown visual review category")
            categories.add(view["category"])
            V.require(view.get("sha256") == V.digest(safe(asset, view.get("path"))), "Visual review image stale")
            V.require(view.get("path") in rendered
                      and rendered[view["path"]].get("sha256") == view["sha256"],
                      "Visual review image is not bound to the current actual GLB render")
            V.require(view['category']==rendered[view['path']].get('category'),
                      'Review category differs from the actual rendered evidence')
            V.require(isinstance(view.get("findings"), list) and len(view["findings"]) >= 2
                      and all(isinstance(s, str) and len(s.strip()) >= 15 for s in view["findings"]),
                      "Each visual view requires concrete findings")
        V.require(categories == {"deck", "interior", "hull_rig"}, "Visual evidence categories incomplete")
        V.require(any(view["category"] == "interior" and not rendered[view["path"]].get("hidden_nodes")
                      for view in views), "At least one actual intact interior view required in addition to cutaways")
        gun_rooms=reviewed_gun_decks(contract,views,rendered)
        V.require(isinstance(review.get("limitations"), list), "Visual review must state limits")
        return {"passed": True, "path": path, "sha256": V.digest(safe(asset, path)), "views": views,
                "reviewer": review["reviewer"], "reference": review["reference"],
                'reviewed_intact_gun_decks':gun_rooms}
    except (ValueError, KeyError, TypeError, OSError) as error:
        return {"passed": False, "path": path, "errors": [str(error)]}


def controls():
    # Actual ray/triangle fixtures exercise the specific regression: furnished
    # rooms hidden beneath an intact deck and a doorway sealed by a wall.
    def panel(name, z):
        return {name: {"triangles": np.array([[[-2,-2,z],[2,-2,z],[2,2,z]],
                                               [[-2,-2,z],[2,2,z],[-2,2,z]]], dtype=float)}}
    deck = Rays(panel("unbroken_deck", 0))
    V.require(deck.hit([0,0,-.28], [0,0,1], .56)["node"] == "unbroken_deck", "Sealed hatch negative control failed")
    V.require(deck.hit([3,0,-.28], [0,0,1], .56) is None, "Clear hatch positive control failed")
    wall_data = panel("sealed_door", 0)
    wall_data["sealed_door"]["triangles"] = wall_data["sealed_door"]["triangles"][:, :, [0,2,1]]
    wall = Rays(wall_data)
    V.require(wall.hit([0,-.28,0], [0,1,0], .56) is not None, "Sealed door negative control failed")
    V.require(deck.hit([0,0,-1.5], [0,0,1], 1.6) is not None, "Low overhead negative control failed")
    return {"passed": True, "controls": ["real sealed hatch rejected", "real empty hatch accepted",
            "real sealed door rejected", "real overhead detected"],
            "scope": "Actual triangle ray tests; portable schema/feature/image mutation controls run in self_test."}


def geometry_controls():
    def box(name, lo, hi, material="wood"):
        lo, hi = np.array(lo, float), np.array(hi, float)
        vertices = np.array([[x,y,z] for x in (lo[0],hi[0]) for y in (lo[1],hi[1]) for z in (lo[2],hi[2])])
        faces = np.array([[0,1,3],[0,3,2],[4,6,7],[4,7,5],[0,4,5],[0,5,1],
                          [2,3,7],[2,7,6],[0,2,6],[0,6,4],[1,5,7],[1,7,3]])
        tri = vertices[faces]
        return {"name":name,"min":lo.tolist(),"max":hi.tolist(),"triangles":tri,
                "surface_area_m2":float(np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1).sum()/2),
                "materials":[material],"extras":{}}
    records = {
        "stern":box("stern",[-2,-.05,-1],[-.6,.05,1]),
        "left":box("left",[-.6,-.06,-.5],[-.5,.06,.5]),
        "right":box("right",[.5,-.06,-.5],[.6,.06,.5]),
        "head":box("head",[-.6,-.06,.5],[.6,.06,.6]),
        "sill":box("sill",[-.6,-.06,-.6],[.6,.06,-.5]),
        "glass":box("glass",[-.45,.01,-.45],[.45,.016,.45],"natural_glass")}
    contract = {"windows":[{"id":"actual_light","kind":"window","from":"cabin","to":"exterior",
                            "hull_node":"stern","frame_nodes":["left","right","head","sill"],
                            "glass_nodes":["glass"],"axis":[0,1,0]}]}
    spec = {"detailed_layout":{"cabin":{"present":True}}}
    V.require(windows(contract, records, spec)["passed"], "Real window opening positive control failed")
    sealed = copy.deepcopy(records)
    sealed["stern"]["triangles"] = np.concatenate([sealed["stern"]["triangles"], box("filler",[-.5,-.05,-.5],[.5,.05,.5])["triangles"]])
    V.require(not windows(contract, sealed, spec)["passed"], "Pane mounted on solid timber was accepted")
    missing = copy.deepcopy(contract)
    missing["windows"][0]["glass_nodes"] = ["missing_glass"]
    V.require(not windows(missing, records, spec)["passed"], "Nonmesh window marker was accepted")
    try:
        selected_nodes(["missing_mesh"], records, "synthetic feature")
    except ValueError:
        pass
    else:
        raise ValueError("Missing mesh accepted as physical detail")
    battery={
        'floor_lower':box('floor_lower',[-2,-2,-.08],[2,2,0]),
        'floor_upper':box('floor_upper',[-2,-2,1.92],[2,2,2]),
        'gun_barrel_0_port_00':box('gun_barrel_0_port_00',[-.2,-.3,.5],[.2,.3,.7]),
        'gun_cheek_0_port_00_test':box('gun_cheek_0_port_00_test',[-.2,-.3,.05],[.2,.3,.4]),
        'gun_wheel_0_port_00_0':box('gun_wheel_0_port_00_0',[-.45,-.1,0],[-.25,.1,.2]),
        'gun_wheel_0_port_00_1':box('gun_wheel_0_port_00_1',[.25,-.1,0],[.45,.1,.2]),
        'gun_barrel_0_port_00_breeching':box('gun_barrel_0_port_00_breeching',[-.1,-.4,.2],[.1,-.3,.3])}
    battery['gun_barrel_0_port_00']['extras']={'role':'cannon_barrel'}
    battery['gun_barrel_0_port_00_breeching']['extras']={'kind':'rope','detail_feature':'gun_tackle'}
    assembly=[name for name in battery if name.startswith('gun_')]
    support=[]
    for wheel in ['gun_wheel_0_port_00_0','gun_wheel_0_port_00_1']:
        mid=(np.array(battery[wheel]['min'])+np.array(battery[wheel]['max']))/2
        support.append({'wheel_node':wheel,'floor_node':'floor_lower','sample_blender_m':[float(mid[0]),float(mid[1]),.20],
                        'wheel_bottom_z_m':0.,'floor_z_m':0.,'contact_error_m':0.})
    binding={'room_id':'lower_battery','barrel_node':'gun_barrel_0_port_00','assembly_nodes':assembly,
             'support_samples':support,'tolerance_m':.20}
    room={'id':'lower_battery','kind':'gun_deck','floor_nodes':['floor_lower'],
          'furnishing_nodes':assembly,'battery_assemblies':[binding]}
    contract={'battery_floor_bindings':[binding]}
    V.require(battery_inventory(room,contract,battery)['passed'],'Actual battery/truck/floor fixture rejected')
    for label in ['wrong physical floor','missing tackle','empty battery']:
        altered=copy.deepcopy(room)
        if label=='wrong physical floor':
            altered['floor_nodes']=['floor_upper']
            for sample in altered['battery_assemblies'][0]['support_samples']:
                sample.update(floor_node='floor_upper',floor_z_m=2.)
        elif label=='missing tackle':
            altered['battery_assemblies'][0]['assembly_nodes']=[n for n in assembly if n!='gun_barrel_0_port_00_breeching']
        else:altered['battery_assemblies']=[]
        alternate={'battery_floor_bindings':altered['battery_assemblies']}
        V.require(not battery_inventory(altered,alternate,battery)['passed'],'Incorrect battery inventory accepted: '+label)
    return ["real glazed opening accepted", "pane over solid timber rejected",
            "missing glass mesh rejected", "nonmesh feature marker rejected",
            'actual battery/trucks/supporting floor accepted','battery assigned to wrong deck rejected',
            'battery without actual tackle rejected','empty battery inventory rejected']


def measure(asset, report):
    asset = Path(asset)
    design, spec = read(asset/"design.json"), read(asset/"spec.json")
    contract = design.get("detail_contract", {})
    V.require(contract.get("version") == 5 and contract.get("axes", "blender_world") == "blender_world",
              "Missing v5 Blender-world actual detail contract")
    records, doc, binary, used = geometry(asset/"model/ochre/ship.glb")
    rooms = interiors(contract, records, spec)
    openings = portals(contract, records, spec)
    checks = {"research": research(asset, contract, spec), "feature_inventory": features(contract, records, spec),
              "interior_geometry": rooms, "portal_voids": openings,
              "connected_access": access(contract, records, rooms, openings, spec),
              "window_voids": windows(contract, records, spec),
              "material_detail": materials(doc, binary, used, report["glb_files"]["model/ochre/ship.glb"]["quality"]),
              "visual_review": visual_review(asset, contract), "negative_controls": controls()}
    checks['package_budget'] = C.package_budget(asset,spec,report)
    return evidence_precision({"schema": 5, "passed": all(v["passed"] for v in checks.values()),
            "scope": "Substantial physical detail and visible accessible interiors; static authored geometry, no game controller, historical-exactness or sailing simulation certification.",
            "matrix": [{"id": key, "required": True, "status": "PASS" if checks[key]["passed"] else "FAIL",
                        "evidence": checks[key]} for key in sorted(GATES)], "checks": checks,
            "geometry_sha256": report["glb_files"]["model/ochre/ship.glb"]["geometry_sha256"],
            "detail_contract_sha256": V.sha(V.canonical(contract))})


def validate_upgrade(upgrade):
    return C.validate_upgrade(upgrade)


def check(asset, root=None):
    asset = Path(asset).resolve()
    root = Path(root).resolve() if root else HERE.parents[1]
    spec=read(asset/'spec.json')
    if spec.get('detail_schema')!=5:
        V.require('detail_schema' not in spec,'Unknown detail schema cannot fall back to v4')
        return V.check(asset,root)
    frozen = C.check(asset, root)
    report = read(asset/"validation.json")
    upgrade = report.get("detail_upgrade", {})
    validate_upgrade(upgrade)
    expected_sources = {path: V.digest(safe(root, path)) for path in sorted(AUDIT_SOURCES)}
    V.require(upgrade.get("audit_source_sha256") == expected_sources, "Stale/missing v5 audit/benchmark/CI provenance")
    actual = measure(asset, report)
    for key, value in actual.items():
        V.require(upgrade.get(key) == value, "Recomputed actual v5 geometry/material/review evidence differs: " + key)
    return {**frozen, "detail_schema": 5, "detail_gates": len(GATES), "actual_detail_recomputed": True}


def material_controls():
    """Exercise exported embedded-image failures, not a hand-authored PASS row."""
    binary, views, images, textures = bytearray(), [], [], []
    yy, xx = np.mgrid[:256, :256]
    for role in ("color", "normal", "orm", "uniform"):
        array = np.zeros((256,256,3), dtype=np.uint8)
        if role == "color":
            array[:,:,0] = 90 + xx//4
            array[:,:,1] = 60 + yy//5
            array[:,:,2] = 40 + (xx+yy)//8
        elif role == "normal":
            array[:,:,0] = 115 + xx//10
            array[:,:,1] = 115 + yy//10
            array[:,:,2] = 250
        elif role == "orm":
            array[:,:,0] = 240
            array[:,:,1] = 100 + (xx+yy)//5
            array[:,:,2] = 0
        else:
            array[:,:,:] = 128
        buffer = io.BytesIO()
        Image.fromarray(array).save(buffer, format="PNG")
        raw = buffer.getvalue()
        views.append({"buffer":0, "byteOffset":len(binary), "byteLength":len(raw)})
        binary.extend(raw)
        images.append({"bufferView":len(views)-1, "mimeType":"image/png", "name":role})
        textures.append({"source":len(images)-1})
    mats = []
    quality = {"uv":{"materials":{}}}
    for role in sorted(REQUIRED_ROLES):
        mats.append({"name":role,"extras":{"guide_pbr_v5":True,"material_role":role},
                     "pbrMetallicRoughness":{"baseColorTexture":{"index":0},
                                             "metallicRoughnessTexture":{"index":2}},
                     "normalTexture":{"index":1}})
        quality["uv"]["materials"][role] = {"texel_density_px_m":{"median":2048}}
    doc = {"materials":mats,"textures":textures,"images":images,"bufferViews":views}
    used = set(range(len(mats)))
    V.require(materials(doc, bytes(binary), used, quality)["passed"], "Real embedded image positive fixture failed")
    failures = []
    for label in ("uniform color", "flat normal", "uniform roughness", "merged color/data", "low density"):
        bad, bad_quality = copy.deepcopy(doc), copy.deepcopy(quality)
        if label == "uniform color":
            bad["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"]["index"] = 3
        elif label == "flat normal":
            bad["materials"][0]["normalTexture"]["index"] = 3
        elif label == "uniform roughness":
            bad["materials"][0]["pbrMetallicRoughness"]["metallicRoughnessTexture"]["index"] = 3
        elif label == "merged color/data":
            bad["materials"][0]["normalTexture"]["index"] = 0
        else:
            bad_quality["uv"]["materials"][mats[0]["name"]]["texel_density_px_m"]["median"] = 64
        V.require(not materials(bad, bytes(binary), used, bad_quality)["passed"], "Broken material accepted: "+label)
        failures.append(label+" rejected")
    return failures


def gun_review_controls():
    contract={'interiors':[{'id':'battery_lower','kind':'gun_deck'},{'id':'battery_middle','kind':'gun_deck'}]}
    rendered={name+'.png':{'room_id':name,'room_kind':'gun_deck','category':'interior',
                          'hidden_nodes':[],'actual_hidden_nodes':[]} for name in ('battery_lower','battery_middle')}
    views=[{'path':path,'category':'interior'} for path in rendered]
    V.require(reviewed_gun_decks(contract,views,rendered)==['battery_lower','battery_middle'],
              'Dynamic intact battery room labels were rejected')
    cases=[]
    for label in ('missing manual battery review','cutaway substituted','wrong room kind'):
        bad=copy.deepcopy(rendered);reviewed=copy.deepcopy(views)
        if label=='missing manual battery review':reviewed=reviewed[:1]
        elif label=='cutaway substituted':bad['battery_middle.png']['hidden_nodes']=['outer_hull']
        else:bad['battery_middle.png']['room_kind']='hold'
        try:reviewed_gun_decks(contract,reviewed,bad)
        except ValueError:cases.append(label+' rejected')
        else:raise ValueError('Missing intact battery evidence accepted: '+label)
    V.require(reviewed_gun_decks({'interiors':[{'id':'hold','kind':'hold'}]},[],{})==[],
              'Non-battery models acquired an extra battery-view requirement')
    return ['dynamic battery IDs accepted','non-battery requirements unchanged']+cases


def self_test():
    result = controls()
    fixture = {"schema": 5, "passed": True,
               "checks": {key: {"passed": True} for key in GATES}}
    fixture["matrix"] = [{"id": key, "required": True, "status": "PASS", "evidence": fixture["checks"][key]} for key in sorted(GATES)]
    validate_upgrade(fixture)
    rejected = []
    for key in sorted(GATES):
        bad = copy.deepcopy(fixture)
        del bad["checks"][key]
        try:
            validate_upgrade(bad)
        except ValueError:
            rejected.append("missing " + key)
        else:
            raise ValueError("Missing gate accepted: " + key)
    uniform = io.BytesIO()
    Image.new("RGB", (256,256), (128,128,255)).save(uniform, format="PNG")
    V.require(max(image_stats(uniform.getvalue())["std_rgb"]) < 1e-8, "Uniform image control failed")
    return {**result, "schema_negative_controls": rejected, "image_controls": material_controls(),
            "geometry_controls": geometry_controls(), "resource_profile_controls":C.self_test(),
            'gun_deck_review_controls':gun_review_controls()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--asset-dir", type=Path)
    target.add_argument("--all", action="store_true")
    target.add_argument("--self-test", action="store_true")
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--measure-only", action="store_true", help="Measure current actual geometry before assembling the v5 report")
    parser.add_argument("--verify", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        root = args.source_root.resolve() if args.source_root else HERE.parents[1]
        if args.self_test:
            result = self_test()
        elif args.all:
            paths = sorted((root/"potc").glob("*/spec.json"))
            V.require(paths, "No v5 PoTC assets found")
            result = {"passed": True, "assets": [check(p.parent, root) for p in paths]}
        elif args.measure_only:
            result = measure(args.asset_dir, read(args.asset_dir/"validation.json"))
        else:
            result = check(args.asset_dir, root)
        print(json.dumps(result, indent=2, allow_nan=False))
    except (ValueError, KeyError, TypeError, OSError, IndexError) as error:
        parser.exit(1, "PoTC detail integrity failed: " + str(error) + "\n")


if __name__ == "__main__":
    main()
