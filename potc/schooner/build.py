#!/usr/bin/env python3
"""Build the researched family with scoped end-bearing assembly clearance."""
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
from v5_shipkit import build
import v5_decks as _decks


def _fit_low_forecastle(ctx, nodes):
    """Fit the 280mm raised platform to its actual underlying deck timbers."""
    import json
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from v2_boats import physical_uv
    from v2_mesh_finish import finish_scene

    vertices, faces = [], []
    for ob in ctx.deck_groups['main']:
        offset = len(vertices)
        vertices.extend(ob.matrix_world @ v.co for v in ob.data.vertices)
        faces.extend(tuple(offset + i for i in f.vertices) for f in ob.data.polygons)
    floor = BVHTree.FromPolygons(vertices, faces)

    # Full-height knees cannot fit a 280mm step. Keep their upper beam seat,
    # but make the lower corner bear on the real main sole as a compact knee.
    for ob in nodes:
        if ob.get('structural_role') != 'deck_knee':
            continue
        if len(ob.data.vertices) != 6:
            raise ValueError('Unexpected low-forecastle knee construction')
        for index in (2, 5):
            old = ob.matrix_world @ ob.data.vertices[index].co
            station = -old.y
            side = 1 if old.x >= 0 else -1
            height = ctx.main_height(station)
            # The main waterway is centred 200mm inside the hull with a
            # 70mm section. Land the short knee on the sole inboard of it.
            x = side * max(.03, ctx.width(station, height) - .30)
            contact = None
            for inward in (0., .004, .008, .016, .024):
                xx = x - side * inward
                contact = floor.ray_cast(ctx.p(xx, station, height + .60), Vector((0, 0, -1)), 1.20)[0]
                if contact is not None:
                    break
            if contact is None:
                raise ValueError('No actual main-sole bearing below low forecastle knee')
            if contact.z >= min((ob.matrix_world @ ob.data.vertices[i].co).z for i in (0, 1)) - .025:
                raise ValueError('Insufficient real height for a compact forecastle knee')
            ob.data.vertices[index].co = ob.matrix_world.inverted() @ contact
        ob.data.update()
        path = [ob.matrix_world @ ob.data.vertices[i].co for i in (1, 2)]
        finish_scene([ob])
        physical_uv(ob, (path[1] - path[0]).normalized(), path)
        ob['construction_kind'] = 'compact_low_forecastle_knee'
        ob['preserve_solid_lod'] = True

    # Shallow fitted seats let the upper beams meet the existing main
    # waterways without putting two pieces of solid wood through one another.
    waterways = [o for o in ctx.vis if o.name.startswith('main_waterway_')]
    for ob in nodes:
        if ob.get('structural_role') != 'deck_beam':
            continue
        for waterway in waterways:
            a = BVHTree.FromPolygons([ob.matrix_world @ v.co for v in ob.data.vertices],
                                     [tuple(f.vertices) for f in ob.data.polygons])
            b = BVHTree.FromPolygons([waterway.matrix_world @ v.co for v in waterway.data.vertices],
                                     [tuple(f.vertices) for f in waterway.data.polygons])
            if not a.overlap(b):
                continue
            modifier = ob.modifiers.new('fitted_main_waterway_seat', 'BOOLEAN')
            modifier.operation = 'DIFFERENCE'
            modifier.solver = 'EXACT'
            modifier.object = waterway
            bpy.context.view_layer.objects.active = ob
            with bpy.context.temp_override(object=ob, active_object=ob):
                bpy.ops.object.modifier_apply(modifier=modifier.name)
            if not ob.data.vertices:
                raise ValueError('Waterway seat removed a complete raised-deck beam')
            finish_scene([ob])
            path = json.loads(ob['grain_path_json'])['points'] if ob.get('grain_path_json') else None
            physical_uv(ob, Vector(ob.get('grain_axis', [1, 0, 0])),
                        [Vector(q) for q in path] if path else None)
            ob['construction_kind'] = 'notched_low_forecastle_beam'
            ob['preserve_solid_lod'] = True


def _build_with_bearing_clearance():
    original_beams = _decks._beams

    def end_bearings(ctx, deck_id, a, b, baseline, *args, **kwargs):
        # The adjacent same-level cabin/hold soles share a floor seam. Keep
        # their separate 140mm beams and 130mm knees genuinely apart; the
        # forecastle end knees also stand clear of the 75mm breakwall. Only
        # bearing stations move 120mm inward: floors and door bounds stay put.
        if ctx.spec.get("id") == "schooner" and deck_id in {"hold", "cabin_sole", "castle_1"}:
            inset = .12
            if b - a <= 2 * inset:
                raise ValueError("Insufficient room span for the authored end-bearing clearance")
            a, b = a + inset, b - inset
        nodes = original_beams(ctx, deck_id, a, b, baseline, *args, **kwargs)
        if ctx.spec.get("id") == "schooner" and deck_id == "castle_1":
            _fit_low_forecastle(ctx, nodes)
        return nodes

    _decks._beams = end_bearings
    try:
        return build(HERE / "spec.json", HERE)
    finally:
        _decks._beams = original_beams


if __name__ == "__main__":
    _build_with_bearing_clearance()
