"""Complete promised small-boat cleats and measure an unobstructed open-well path.

This hook only applies to the researched open Tartane. It adds no cabin, hatch,
room, or optional equipment, and never hides an obstacle from its measurements.
"""
import math
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def _tree(objects):
    vertices, faces, owners = [], [], []
    for obj in objects:
        if obj.type != 'MESH':
            continue
        offset = len(vertices)
        vertices.extend(obj.matrix_world @ vertex.co for vertex in obj.data.vertices)
        for face in obj.data.polygons:
            faces.append(tuple(offset + index for index in face.vertices))
            owners.append(obj.name)
    return BVHTree.FromPolygons(vertices, faces, all_triangles=False, epsilon=.000001), owners


def _hit(tree, owners, origin, direction, distance):
    point, normal, index, travel = tree.ray_cast(Vector(origin), Vector(direction).normalized(), distance)
    return None if index is None else {'point': point, 'node': owners[index], 'distance_m': travel}


def complete_openboat_details(ctx):
    """Fit actual supported hand cleats and replace the obstructed well path."""
    if ctx.layout.get('kind') != 'open_boat':
        return None
    if getattr(ctx, 'openboat_details', None):
        return ctx.openboat_details
    ledger = {'scope': 'Promised hand cleats and supported open-well circulation only; all actual scene geometry retained.',
              'cleats': [], 'route': None}
    lookup = {obj.name: obj for obj in ctx.vis if obj.type == 'MESH'}
    added = []
    # Centreline longitudinal plank seams are real gaps. Choose the nearest
    # off-seam station whose actual platform supports the complete cleat base.
    for index, (fraction, deck_id) in enumerate(((-.43, 'stern_platform'), (.33, 'bow_platform'))):
        floors = ctx.deck_groups.get(deck_id, [])
        if not floors:
            raise ValueError('Open boat is missing its actual ' + deck_id)
        floor_tree, floor_owners = _tree(floors)
        station = ctx.L * fraction
        found = None
        for x in (.031, -.031, .057, -.057, .089, -.089):
            for delta in (0., .017, -.017, .037, -.037):
                s = station + delta
                samples = []
                for dx, ds in ((0., 0.), (-.080, -.120), (.080, -.120), (-.080, .120), (.080, .120)):
                    z = ctx.main_height(s + ds)
                    sample = _hit(floor_tree, floor_owners, ctx.p(x + dx, s + ds, z + .25), (0, 0, -1), .60)
                    if sample is None:
                        break
                    samples.append(sample)
                if len(samples) == 5 and max(q['point'].z for q in samples)-min(q['point'].z for q in samples) < .12:
                    found = (x, s, samples[0]['point'].z, samples)
                    break
            if found:
                break
        if found is None:
            raise ValueError('No supported actual end-platform footprint for promised hand cleat ' + str(index))
        x, s, z, support = found
        names = ['boat_hand_cleat_%d_%s' % (index, part) for part in ('base', 'horns', 'neck')]
        group = [lookup[name] for name in names if name in lookup]
        if group and len(group) != 3:
            raise ValueError('Incomplete original open-boat hand cleat assembly')
        if not group:
            # A small scribed foot follows the real sheer/camber instead of
            # balancing a horizontal box on its lowest corner.
            bottom = [Vector(q['point'])-Vector((0,0,.004)) for q in support[1:]]
            vertices = bottom+[q+Vector((0,0,.05)) for q in bottom]
            box_faces = [(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]
            foot = ctx.mesh(names[0], vertices, [tuple(reversed(face)) for face in box_faces],
                           'spar', 'fitting', [ctx.p(x,s-.12,z),ctx.p(x,s+.12,z)])
            group = [foot,
                     ctx.beam(names[1], ctx.p(x, s-.17, z+.12), ctx.p(x, s+.17, z+.12), .04, .045, 'wood', 'fitting'),
                     ctx.box(names[2], ctx.p(x, s, z+.075), (.065, .07, .10), 'spar', 'fitting')]
            added.extend(group)
        for obj in group:
            obj['detail_feature'] = 'mooring'
            obj['assembly_id'] = 'boat_hand_cleat_' + str(index)
            obj['preserve_solid_lod'] = True
            ctx.detail_features.setdefault('mooring', []).append(obj.name)
        ctx.joint(group[0], group[2], 'The cleat neck is housed in this actual timber foot.')
        ctx.joint(group[1], group[2], 'The two-ended cleat horn is housed across this actual neck.')
        base_tree, _ = _tree([group[0]])
        support_nodes = []
        for name in sorted(set(q['node'] for q in support)):
            obj = lookup[name]
            actual, _ = _tree([obj])
            if actual.overlap(base_tree):
                ctx.joint(group[0], obj, 'This small hand-cleat foot is housed into this measured end-platform plank.')
                support_nodes.append(name)
        if not support_nodes:
            raise ValueError('Hand cleat has no actual timber bearing contact')
        ledger['cleats'].append({'id': 'boat_hand_cleat_'+str(index), 'nodes': [q.name for q in group],
            'deck_id': deck_id, 'position_blender_m': list(ctx.p(x, s, z)), 'bearing_nodes': support_nodes,
            'floor_samples': [{'point': list(q['point']), 'node': q['node']} for q in support]})
    scene_tree, scene_owners = _tree(ctx.vis)
    room = ctx.room_planes['open_boat']
    floor_nodes = next(q['floor_nodes'] for q in ctx.rooms if q['id'] == 'open_boat')
    actual_floors = [lookup[name] for name in floor_nodes]
    floor_tree, floor_owners = _tree(actual_floors)
    radius, height = .24, 1.60
    a, b = room['from'], room['to']
    first, last = a+(b-a)*.32, a+(b-a)*.68
    diagnostics = []
    route = None
    maximum = room['width_m']/2-.105
    candidates = sorted(set(round(x, 4) for x in (.42, .45, .48, .51, .54, .57, .60, .63, .66) if x <= maximum))
    for x in [sign*x for x in candidates for sign in (1, -1)]:
        points, supports = [], []
        # Additional stations avoid silently bridging unsupported floor gaps.
        count = max(2, math.ceil((last-first)/.20))
        failures = []
        for i in range(count+1):
            s = first+(last-first)*i/count
            z = room['floor'](s)
            samples = [_hit(floor_tree, floor_owners, ctx.p(x+dx, s, z+.25), (0, 0, -1), .50)
                       for dx in (0., -.095, .095)]
            if any(q is None for q in samples):
                failures.append('unsupported feet')
                break
            foot = ctx.p(x, s, max(q['point'].z for q in samples)+.08)
            shoulder = foot+Vector((0, 0, min(.9, height*.55)))
            for axis in ((1,0,0), (-1,0,0), (0,1,0), (0,-1,0)):
                obstacle = _hit(scene_tree, scene_owners, shoulder, axis, radius)
                if obstacle:
                    failures.append(obstacle['node'])
            obstacle = _hit(scene_tree, scene_owners, foot+Vector((0,0,.15)), (0,0,1), height-.15)
            if obstacle:
                failures.append(obstacle['node'])
            if points:
                start = points[-1]+Vector((0,0,min(.9,height*.55)))
                step = shoulder-start
                obstacle = _hit(scene_tree, scene_owners, start, step, step.length)
                if obstacle:
                    failures.append(obstacle['node'])
            points.append(foot)
            supports.append([{'point':list(q['point']), 'node':q['node']} for q in samples])
        diagnostics.append({'x_m': x, 'blockers': sorted(set(failures))})
        if not failures:
            route = {'id':'open_boat_access', 'from':'main_deck', 'to':'open_boat',
                'points':[list(q) for q in points], 'clearance_radius_m':radius,
                'clearance_height_m':height, 'mode':'walk',
                'basis':'Off-centre route over the actual open-well sole, with measured foot support and all-scene shoulder/headroom rays.'}
            ledger['route'] = {'x_m':x, 'support_samples':supports, 'all_scene_clear':True,
                              'rejected_candidates':diagnostics[:-1]}
            break
    if route is None:
        raise ValueError('No supported all-scene-clear open-boat route: ' + str(diagnostics))
    existing = next((i for i, q in enumerate(ctx.routes) if q.get('id')=='open_boat_access'), None)
    if existing is None:
        raise ValueError('Missing original open-boat route to repair')
    ctx.routes[existing] = route
    ctx.detail_contract['routes'] = ctx.routes
    ctx.outfit_ledger.setdefault('nodes', []).extend(obj.name for obj in added)
    ctx.outfit_ledger['openboat_details'] = ledger
    ctx.openboat_details = ledger
    return ledger
