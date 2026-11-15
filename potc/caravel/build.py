#!/usr/bin/env python3
"""Build the family with two measured, physically fitted gunport seats."""
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
from v5_shipkit import build
import v5_decks as _decks


def _fit_forward_port_sills(ctx):
    """House the retained forward lower-port sills in the real waterways."""
    import json
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from v2_boats import physical_uv
    from v2_mesh_finish import finish_scene

    objects = {o.name: o for o in ctx.vis}
    for side in ("port", "starboard"):
        waterway = objects["gun_deck_0_waterway_" + side]
        sill = objects["gunport_0_" + side + "_9_sill"]
        tree_a = BVHTree.FromPolygons(
            [waterway.matrix_world @ v.co for v in waterway.data.vertices],
            [tuple(f.vertices) for f in waterway.data.polygons])
        tree_b = BVHTree.FromPolygons(
            [sill.matrix_world @ v.co for v in sill.data.vertices],
            [tuple(f.vertices) for f in sill.data.polygons])
        if not tree_a.overlap(tree_b):
            continue
        path = json.loads(waterway["grain_path_json"])["points"]
        modifier = waterway.modifiers.new("fitted_forward_gunport_sill_seat", "BOOLEAN")
        modifier.operation = "DIFFERENCE"
        modifier.solver = "EXACT"
        modifier.object = sill
        bpy.context.view_layer.objects.active = waterway
        with bpy.context.temp_override(object=waterway, active_object=waterway):
            bpy.ops.object.modifier_apply(modifier=modifier.name)
        if not waterway.data.vertices:
            raise ValueError("Gunport seat removed the complete lower waterway")
        finish_scene([waterway])
        for layer in list(waterway.data.uv_layers):
            waterway.data.uv_layers.remove(layer)
        physical_uv(waterway, Vector(waterway.get("grain_axis", [0, -1, 0])),
                    [Vector(q) for q in path])
        # A carved seat is no longer a regularly indexed tube. Retain its
        # measured grain path, but remove the obsolete tube-ring UV hint.
        if "rope_path_json" in waterway:
            del waterway["rope_path_json"]
        waterway["construction_kind"] = "fitted_forward_gunport_waterway"
        waterway["fitted_seat_cutter"] = sill.name
        waterway["preserve_solid_lod"] = True


def _build_with_fitted_waterways():
    original_waterways = _decks._waterways

    def fitted_waterways(ctx, deck_id, *args, **kwargs):
        result = original_waterways(ctx, deck_id, *args, **kwargs)
        # Only this measured 32-gun family has the two 16mm forward contacts.
        # Both sill solids, floor surfaces and hull silhouette stay intact.
        if ctx.spec.get("id") == "caravel" and deck_id == "gun_deck_0":
            _fit_forward_port_sills(ctx)
        return result

    _decks._waterways = fitted_waterways
    try:
        return build(HERE / "spec.json", HERE)
    finally:
        _decks._waterways = original_waterways


if __name__ == "__main__":
    _build_with_fitted_waterways()
