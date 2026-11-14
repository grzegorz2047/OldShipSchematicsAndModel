"""Render inspectable detail evidence from the actual delivered GLB.

Blender --background --python v5_review.py -- --asset-dir potc/brig
Only review cameras, lights and temporary visibility are changed.  The GLB and
packed source are never saved or modified.  Cutaways explicitly list hidden
mesh nodes.  This command records evidence, not an automatic visual PASS.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

RENDERER_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def meshes():
    return [o for o in bpy.context.scene.objects if o.type == 'MESH'
            and o.get('asset_role') not in ('collision', 'presentation')
            and not o.name.lower().startswith('col_')]


def box(objects):
    points = [o.matrix_world @ Vector(p) for o in objects for p in o.bound_box]
    if not points:
        raise ValueError('No actual mesh bounds for review camera')
    return (Vector(tuple(min(q[k] for q in points) for k in range(3))),
            Vector(tuple(max(q[k] for q in points) for k in range(3))))


def rig_object(ob):
    role = str(ob.get('kind', ob.get('role', ''))).lower()
    member = str(ob.get('rig_member', '')).lower()
    # A channel or deadeye named after a shroud remains useful deck evidence;
    # only its actual standing/running line is hidden.  Preserve spare spars
    # stowed on deck and structural mast partners for the same reason.
    component = str(ob.get('rig_detail_component', ''))
    if ((component and component != 'rig_rope')
            or ob.get('detail_feature') == 'stowage'
            or ob.get('structural_role')):
        return False
    return (role in {'sail', 'canvas', 'rigging', 'mast', 'yard'}
            or member in {'mast', 'spar', 'yard', 'bowsprit', 'sail'}
            or bool(role == 'rope' and ob.get('attachment_start') and ob.get('attachment_end'))
            or any(
        word in ob.name.lower() for word in
        ('sail', 'shroud', 'ratline', 'stay', 'yard', 'mast', 'bowsprit')))


def definitions(spec, design, objects):
    length = float(spec['length'])
    beam = float(spec['beam'])
    freeboard = float(spec['freeboard'])
    detail = design.get('detail_contract', design.get('detail', {}))
    lookup = {o.name: o for o in objects}
    lo, hi = box(objects)
    center = (lo + hi) / 2
    span = max((hi - lo).length, 3)
    direction = Vector((1.15, 1.65, .72)).normalized()
    position = center + direction * span * 2
    rotation = (center - position).to_track_quat('-Z', 'Y').to_matrix().transposed()
    corners = [rotation @ (o.matrix_world @ Vector(p) - center)
               for o in objects for p in o.bound_box]
    scale = max(max(p.x for p in corners) - min(p.x for p in corners),
                (max(p.y for p in corners) - min(p.y for p in corners)) * 1.25) * 1.10
    result = {'hull_rig': {'category': 'hull_rig', 'position': list(position),
                         'target': list(center), 'ortho_scale_m': scale,
                         'hide_rig': False, 'hidden_nodes': [],
                         'scope': 'Whole actual GLB with all visible hull, rig and sails.'}}
    hatch = spec.get('detailed_layout', {}).get('hatch') or {}
    at = float(hatch.get('at', .02)) * length
    x = float(hatch.get('x_m', 0))
    if hatch:
        x += min(.7, float(hatch.get('width_m', 1.2)) * .38)
    target = Vector((x, -at, freeboard + .18))
    result['deck_closeup'] = {
        'category': 'deck', 'position': list(target + Vector((3.6, 4.0, 5.3))),
        'target': list(target), 'ortho_scale_m': 4.5, 'hide_rig': True,
        'hidden_nodes': [], 'physical_scale_reference': 'Bryg Mewa PR 3 helm: 4.5 m orthographic field',
        'scope': 'Actual deck and fitting close-up at a fixed 4.5 metre physical field; rig hidden for visibility.'}
    for room in detail.get('interiors', []):
        identifier = room['id']
        floors = [lookup[n] for n in room.get('floor_nodes', []) if n in lookup]
        if not floors:
            continue
        rlo, rhi = box(floors)
        samples = [Vector(q) for q in room.get('clearance_samples', [])]
        floor_z = sum(q.z for q in samples) / len(samples) - .08 if samples else (rlo.z + rhi.z) / 2
        if identifier == 'open_boat':
            target = Vector((0, (rlo.y + rhi.y) / 2, floor_z + .30))
            result['open_bilge'] = {
                'category': 'interior', 'position': list(target + Vector((2.9, 2.3, 4.2))),
                'target': list(target), 'ortho_scale_m': 4.5, 'hide_rig': True,
                'hidden_nodes': [], 'room_id': identifier,
                'scope': 'Open boat well, exposed frames, bilge boards and thwarts; there is no enclosed cabin.'}
            continue
        # Every declared belowdeck battery needs its own intact evidence, even
        # when its authored identifier does not begin with "gun".
        room_kind = room.get('kind', '')
        is_battery = room_kind == 'gun_deck' or identifier.startswith('gun')
        if identifier not in {'hold', 'cabin'} and not is_battery:
            continue
        dy = max(.8, rhi.y - rlo.y)
        door_x = float(spec.get('detailed_layout', {}).get('cabin', {}).get('door_x_m', 0)) if identifier == 'cabin' else 0
        # Look from the opposite side of an offset descending companion, so
        # its treads do not fill the foreground and conceal the room joinery.
        camera_x = (-math.copysign(beam * .09, door_x) if identifier == 'cabin' and door_x
                    else beam * .065)
        pos = Vector((camera_x, rlo.y + min(.55, dy * .17), floor_z + 1.23))
        target = Vector((-beam * .055, rhi.y - min(.40, dy * .13), floor_z + .95))
        placements = [q for q in design.get('outfit', {}).get('placements', [])
                      if q.get('room') == identifier and q.get('placed') is not False
                      and all(key in q for key in ('x_m', 's_m', 'floor_z_m', 'height_m'))]
        if identifier == 'hold' and placements:
            # Aim at actual side stowage from the clear working aisle.  The
            # extreme fore end is commonly occupied by a cable-store ladder
            # and is a poor, obstructed camera station for a long hold.
            middle_s = -(rlo.y+rhi.y)/2
            fitting = min(placements, key=lambda q: abs(float(q['s_m'])-middle_s))
            fy = -float(fitting['s_m'])
            fz = float(fitting['floor_z_m'])
            target = Vector((float(fitting['x_m']), fy,
                             fz+min(.55, float(fitting['height_m'])*.65)))
            camera_y = min(rhi.y-.45, fy+min(3., dy*.22))
            if camera_y-fy < 1.2:
                camera_y = max(rlo.y+.45, fy-min(3., dy*.22))
            aisle_x = -math.copysign(min(.60, beam*.06), float(fitting['x_m']) or 1.)
            pos = Vector((aisle_x, camera_y, fz+1.23))
        elif identifier == 'cabin' and placements:
            # The forward doorway is often directly beside the berth.  An
            # intact view from the after end shows both berth and writing
            # furniture at a useful distance rather than cropping their feet.
            target = Vector((sum(float(q['x_m']) for q in placements)/len(placements),
                             -sum(float(q['s_m']) for q in placements)/len(placements),
                             floor_z+.78))
            pos = Vector((max(-.5, min(.5, door_x*.35)),
                          rhi.y-min(.55, dy*.17), floor_z+1.23))
        elif is_battery:
            # Use the central working aisle rather than the fine bow end of a
            # long gun deck.  Both rows, their ports and the overhead framing
            # remain real surrounding geometry in this eye-height view.
            pos = Vector((min(.60, beam*.055), rhi.y-dy*.25, floor_z+1.23))
            target = Vector((-min(.45, beam*.04), rlo.y+dy*.20, floor_z+1.02))
        if (target - pos).length < .4:
            target.y += .7
        result[identifier + '_interior'] = {
            'category': 'interior', 'position': list(pos), 'target': list(target),
            'lens_mm': 20, 'hide_rig': False, 'hidden_nodes': [], 'room_id': identifier,
            'scope': 'Camera inside the actual enclosed GLB room; auxiliary camera fill reveals timber and furniture.'}
        if is_battery:
            result[identifier + '_interior'].update(
                room_kind='gun_deck', label='Belowdeck battery: ' + identifier,
                scope='Intact eye-height view along the actual belowdeck battery aisle; gun carriages, ports, hull and overhead timbers retained. Auxiliary camera fill only.')
        # A separate honest cutaway makes structure inspectable even if a mast
        # or furniture limits the natural eye-height interior camera.
        hidden = []
        for ob in objects:
            role = str(ob.get('structural_role', ''))
            kind = str(ob.get('kind', ''))
            if kind == 'hull' or ob.name in design.get('type_contract', {}).get('hull_nodes', []):
                hidden.append(ob.name)
            elif role in {'deck_plank', 'deck_beam', 'waterway'}:
                olo, ohi = box([ob])
                if ohi.z > floor_z + .35:
                    hidden.append(ob.name)
            elif role == 'bulkhead':
                hidden.append(ob.name)
        target = Vector((0, (rlo.y + rhi.y) / 2, floor_z + .4))
        result[identifier + '_cutaway'] = {
            'category': 'interior', 'position': list(target + Vector((beam * 1.1, dy * .25 + 2, max(4, beam)))),
            'target': list(target), 'ortho_scale_m': max(4.5, min(length * .85, max(dy, rhi.x-rlo.x) * 1.12)),
            'hide_rig': True, 'hidden_nodes': hidden, 'room_id': identifier,
            'scope': 'Read-only cutaway: named outer hull, upper deck timbers and bulkheads temporarily hidden; delivered GLB unchanged.'}
        if is_battery:
            result[identifier + '_cutaway'].update(
                room_kind='gun_deck', label='Belowdeck battery cutaway: ' + identifier)
    return result


def render(definition, path, resolution, samples):
    scene = bpy.context.scene
    for ob in list(scene.objects):
        if ob.type in {'CAMERA', 'LIGHT'}:
            bpy.data.objects.remove(ob, do_unlink=True)
    previous = {o.name: o.hide_render for o in meshes()}
    hidden = set(definition.get('hidden_nodes', []))
    for ob in meshes():
        ob.hide_render = ob.name in hidden or (definition.get('hide_rig') and rig_object(ob))
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = resolution
    scene.render.resolution_y = round(resolution * .8)
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = 'AgX'
    scene.view_settings.look = 'AgX - Medium High Contrast'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    world = bpy.data.worlds.new('detail_review_world')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (.28, .30, .34, 1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = .65
    scene.world = world
    pos, target = Vector(definition['position']), Vector(definition['target'])
    bpy.ops.object.camera_add(location=pos)
    camera = bpy.context.object
    camera.rotation_euler = (target - pos).to_track_quat('-Z', 'Y').to_euler()
    camera.data.clip_start = .025
    camera.data.clip_end = 1000
    if 'ortho_scale_m' in definition:
        camera.data.type = 'ORTHO'
        camera.data.ortho_scale = definition['ortho_scale_m']
    else:
        camera.data.lens = definition.get('lens_mm', 20)
    scene.camera = camera
    interior = 'ortho_scale_m' not in definition
    light_scale = 3.0 if interior else max(5., definition['ortho_scale_m'])
    lighting = [(pos, 115 if interior else 100 * light_scale ** 2, 1.5 if interior else light_scale * .65)]
    if not interior:
        lighting += [(target + Vector((-1, -1, 1.5)) * light_scale,
                      55 * light_scale ** 2, light_scale * .75)]
    else:
        lighting += [(target + Vector((0, 0, .45)), 35, 1.0)]
    for location, energy, size in lighting:
        bpy.ops.object.light_add(type='AREA', location=location)
        light = bpy.context.object
        light.data.energy = energy
        light.data.size = size
        light.rotation_euler = (target - light.location).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    actual_hidden = [ob.name for ob in meshes() if ob.hide_render]
    for ob in meshes():
        ob.hide_render = previous.get(ob.name, False)
    return actual_hidden


def review(asset, palette='ochre', resolution=640, samples=12, selected_views=None):
    asset = Path(asset).resolve()
    spec = json.loads((asset / 'spec.json').read_text())
    design = json.loads((asset / 'design.json').read_text())
    model = asset / 'model' / palette / 'ship.glb'
    before = digest(model)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(model))
    bpy.context.view_layer.update()
    objects = meshes()
    output = asset / 'previews' / palette / 'detail'
    output.mkdir(parents=True, exist_ok=True)
    views = definitions(spec, design, objects)
    if selected_views:
        unknown = set(selected_views) - set(views)
        if unknown:
            raise ValueError('Unknown review views: ' + ', '.join(sorted(unknown)))
        views = {name: value for name, value in views.items() if name in selected_views}
    records = []
    for name, definition in views.items():
        path = output / (name + '.png')
        print('V5_REVIEW_RENDER', spec['id'], name, flush=True)
        actual_hidden = render(definition, path, resolution, samples)
        records.append({'name': name, 'path': path.relative_to(asset).as_posix(),
                        'sha256': digest(path), **definition,
                        'actual_hidden_nodes': actual_hidden})
    if digest(model) != before:
        raise RuntimeError('Read-only review unexpectedly changed delivered GLB')
    result = {'schema': 5, 'ship_id': spec['id'], 'palette': palette,
              'model_path': model.relative_to(asset).as_posix(), 'model_sha256': before,
              'renderer_sha256': RENDERER_SHA256, 'resolution': [resolution, round(resolution * .8)],
              'render_samples': samples, 'views': records,
              'review_status': 'PENDING_MANUAL_INSPECTION',
              'presentation': 'Actual GLB reimport; auxiliary area lights and temporary visibility only. Cutaways list every hidden mesh. Original materials and geometry are unmodified.',
              'scope': 'One palette supplies natural-material/interior evidence. Both palette heroes and source/export parity remain separate v4 acceptance evidence.'}
    (asset / 'detail-render.json').write_text(json.dumps(result, indent=2) + '\n')
    print('V5_REVIEW_EVIDENCE', spec['id'], len(records), 'PENDING_MANUAL_INSPECTION', flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset-dir', type=Path, required=True)
    parser.add_argument('--palette', default='ochre')
    parser.add_argument('--resolution', type=int, default=640)
    parser.add_argument('--samples', type=int, default=12)
    parser.add_argument('--views', nargs='+', help='Optional exact view names for a focused rerender')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    if args.resolution < 480:
        parser.error('Detail review resolution must be at least 480')
    review(args.asset_dir, args.palette, args.resolution, args.samples, args.views)


if __name__ == '__main__':
    main()
