"""Physical bored cannon barrels, reinforcing rings and fixed breeching tackle.

The original stock-backed gun ledger and locations are retained.  This module
replaces each simple capped barrel's mesh with a closed, thick-walled bored
casting, and adds actual static metal/rope hardware.  It does not implement
recoil, loading or a runtime weapon controller.
"""
import json
import math

import bpy
import bmesh
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from v2_boats import physical_uv

CARRIAGE_INSET_M = .200


def _casting(obj, ctx, a, b, radius):
    axis = (b-a).normalized()
    u = Vector((0, 1, 0))
    v = axis.cross(u).normalized()
    length = (b-a).length
    # The final two stations form a real recessed bore and its closed back.
    profile = [(0, 0), (0, .70), (.035, .90), (.10, 1.03),
               (.20, 1.00), (.58, .92), (.87, .84), (.95, .94),
               (1, .94), (1, .57), (.69, .57), (.67, 0)]
    sides = 20
    verts, rings, faces = [], [], []
    for fraction, scale in profile:
        center = a + axis*(fraction*length)
        ring = []
        if scale == 0:
            ring.append(len(verts)); verts.append(center)
        else:
            for j in range(sides):
                angle = j*2*math.pi/sides
                ring.append(len(verts))
                verts.append(center + radius*scale*(u*math.cos(angle)+v*math.sin(angle)))
        rings.append(ring)
    for first, second in zip(rings, rings[1:]):
        for j in range(sides):
            if len(first) == 1:
                faces.append((first[0], second[j], second[(j+1) % sides]))
            elif len(second) == 1:
                faces.append((first[j], second[0], first[(j+1) % sides]))
            else:
                faces.append((first[j], second[j], second[(j+1) % sides], first[(j+1) % sides]))
    mesh = bpy.data.meshes.new(obj.name+'_bored_casting')
    mesh.from_pydata(verts, [], faces); mesh.update()
    bm = bmesh.new(); bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(mesh); bm.free()
    old = obj.data; obj.data = mesh
    mesh.materials.append(ctx.materials['iron'])
    physical_uv(obj, Vector((0, -1, 0)), [a, b])
    if old.users == 0:
        bpy.data.meshes.remove(old)
    obj['real_bore_depth_m'] = .31*length
    obj['real_bore_diameter_m'] = 1.14*radius
    obj['preserve_solid_lod'] = True
    return axis, u, v, length


def _ring(ctx, name, center, u, v, radius, thickness, material='iron'):
    points = [center+radius*(u*math.cos(j*math.pi/10)+v*math.sin(j*math.pi/10))
              for j in range(21)]
    return ctx.tube(name, points, thickness, material=material, kind='fitting', sides=6)


def _line(ctx, name, points, first, last):
    obj = ctx.tube(name, points, .022, material='ropeTar', kind='rope', sides=8)
    obj['attachment_start'] = first.name; obj['attachment_end'] = last.name
    obj['rope_path_json'] = json.dumps({'axes':'blender_world', 'points':[list(p) for p in points]})
    reason = 'The fixed breeching fall is knotted onto the actual forged hull eyes.'
    ctx.joint(obj, first, reason); ctx.joint(obj, last, reason)
    rig = ctx.rig_ledger
    rig.setdefault('ropes', []).append(obj.name)
    rig.setdefault('attachments', []).append({'rope':obj.name, 'start':first.name,
        'end':last.name, 'points_blender_m':[list(p) for p in points], 'reason':reason})
    return obj


def build_gun_details(spec, ctx):
    if hasattr(ctx,'_v5_gun_detail_ledger'):
        return ctx._v5_gun_detail_ledger
    names = ctx.detail_features.setdefault('gun_tackle', [])
    ledger = []
    # A hanging knee projects farther inboard than the thin hull shell. Find
    # room for the exposed eye, rather than burying its ring in that timber.
    support_roles={'hull_frame','top_timber','ceiling_strake','deck_plank',
                   'deck_beam','deck_knee','bulkhead','waterway','mast_partner',
                   'mast_step','hatch_coaming','window_frame','window_mullion','gunport_frame'}
    supports=[]
    for member in ctx.vis:
        if member.type!='MESH' or member.get('structural_role') not in support_roles:continue
        points=np.array([tuple(member.matrix_world@vertex.co) for vertex in member.data.vertices])
        if len(points):supports.append((member,points.min(axis=0),points.max(axis=0)))
    minimum=np.array([item[1] for item in supports]);maximum=np.array([item[2] for item in supports])
    support_trees={member.name:BVHTree.FromPolygons(
        [member.matrix_world@vertex.co for vertex in member.data.vertices],
        [list(face.vertices) for face in member.data.polygons]) for member,_,_ in supports}
    box_faces=[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]
    def eye_position(station,sign,lead,side,barrel_z):
        # Ordinary gun-side eyes sit below the barrel axis. Small longitudinal
        # alternatives place them between actual frames and castle knees.
        for dz in(-.15,-.25,-.05,.09):
            z=barrel_z+dz
            for extra in(0,.06,.12,.18,.24,.30):
                ss=station+sign*(lead+extra)
                if any(abs(ss-port['s'])<port['w']/2+.085 and
                       abs(z-port['z'])<port['h']/2+.08 for port in ctx.ports):continue
                outer=ctx.width(ss,z)
                for inset in(.37,.43,.49,.55):
                    center=ctx.p(side*(outer-inset),ss,z)
                    lo=np.array(center)-(.020,.075,.075);hi=np.array(center)+(.020,.075,.075)
                    possible=np.where(np.all(maximum>lo,axis=1)&np.all(minimum<hi,axis=1))[0] if len(supports) else []
                    if len(possible):
                        vertices=[Vector((x,y,z)) for z in(lo[2],hi[2]) for y in(lo[1],hi[1]) for x in(lo[0],hi[0])]
                        eye_box=BVHTree.FromPolygons(vertices,box_faces)
                        blocked=False
                        for index in possible:
                            tree=support_trees[supports[index][0].name]
                            nearest=tree.find_nearest(center)
                            if tree.overlap(eye_box) or (nearest[0] is not None and (center-nearest[0]).dot(nearest[1])<-.000001):
                                blocked=True;break
                        if blocked:continue
                    return center,outer,ss,z
        raise ValueError('No clear structural bay for a real breeching eye at '+str(station))
    for gun in list(ctx.gun_nodes):
        data = json.loads(gun['rope_path_json'])
        a, b = Vector(data['points'][0]), Vector(data['points'][-1])
        radius = float(gun.get('diameter_m', .2))/2
        side = 1 if b.x > a.x else -1
        # Inner frames occupy more breadth than the original thin hull shell.
        # Move the complete carriage/trunnion assembly inboard, keeping the
        # muzzle in its original real gunport and extending the casting inward.
        tag = gun.name.removeprefix('gun_barrel_')
        prefixes = tuple('gun_'+part+'_'+tag for part in
                         ('carriage', 'cheek', 'wheel', 'axle', 'trunnion'))
        inset = Vector((-side*CARRIAGE_INSET_M, 0, 0))
        for component in ctx.vis:
            if component.type != 'MESH' or not any(
                    component.name == prefix or component.name.startswith(prefix+'_')
                    for prefix in prefixes):
                continue
            for vertex in component.data.vertices:
                vertex.co += inset
            if 'rope_path_json' in component:
                path = json.loads(component['rope_path_json'])
                path['points'] = [list(Vector(q)+inset) for q in path['points']]
                component['rope_path_json'] = json.dumps(path)
        a += inset
        gun['rope_path_json'] = json.dumps({'axes':'blender_world',
            'points':[list(a), list(a.lerp(b, .18)), list(a.lerp(b, .6)), list(b)]})
        axis, u, v, length = _casting(gun, ctx, a, b, radius)
        parts = [gun]
        for j, (fraction, factor) in enumerate(((.10, 1.03), (.58, .93), (.96, .95))):
            ring = _ring(ctx, gun.name+'_reinforce_'+str(j), a+axis*length*fraction,
                         u, v, radius*factor, max(.009, radius*.09))
            ctx.joint(ring, gun, 'This cast reinforcing band is integral with this specific cannon body.')
            parts.append(ring)
        knob = ctx.tube(gun.name+'_cascabel', [a-axis*radius*.95, a],
                        radius*.34, material='iron', kind='fitting', sides=12)
        ctx.joint(knob, gun, 'The cascabel is cast into the closed breech of this cannon.')
        parts.append(knob)
        station = -a.y
        # Eyes stand on solid planking outside the real rectangular gunport.
        row = next((p for p in ctx.ports if abs(p['s']-station)<.001 and abs(p['z']-a.z)<.001), None)
        lead = (row['w']/2 if row else .5)+.14
        eyes, ends = [], []
        for sign in (-1, 1):
            center,outer,ss,z = eye_position(station,sign,lead,side,a.z)
            # The forged eye must clear the inward-projecting timber frame.
            # A real bolt shank spans back to the plate in the hull planking.
            eye = _ring(ctx, gun.name+'_breeching_eye_'+str(sign).replace('-', 'minus'),
                        center, Vector((0, 1, 0)), Vector((0, 0, 1)), .055, .012)
            plate_center = ctx.p(side*(outer-.115), ss, z)
            plate = ctx.box(eye.name+'_mounting_plate', plate_center,
                            (.045, .16, .17), material='iron')
            bolt = ctx.tube(eye.name+'_bolt_shank', [center, plate_center], .018,
                            material='iron', kind='fitting', sides=8)
            ctx.joint(eye, bolt, 'This forged gun eye is welded to its actual bolt shank.')
            ctx.joint(bolt, plate, 'The real eye-bolt shank passes through its own hull mounting plate.')
            for hull in ctx.hull_nodes:
                if hull.name.startswith('hull_shell_'):
                    ctx.joint(plate, hull, 'This actual gun eye plate is bolted into the adjacent solid port framing.')
                    ctx.joint(bolt, hull, 'The actual eye-bolt shank is through-bolted into the solid port timber.')
            for frame,low,high in supports:
                if frame.get('structural_role') not in ('hull_frame','top_timber','ceiling_strake','deck_beam','deck_knee','gunport_frame'):continue
                for hardware in(bolt,plate):
                    points=np.array([tuple(hardware.matrix_world@vertex.co) for vertex in hardware.data.vertices])
                    if np.all(points.min(axis=0)<=high) and np.all(points.max(axis=0)>=low):
                        ctx.joint(hardware,frame,'This named gun-eye fixing is through-bolted into its actual adjacent frame, beam or hanging-knee timber; the exposed ring remains clear of wood.')
            parts.extend((eye, plate, bolt)); eyes.append(eye)
            # Topmost torus vertex is an actual support surface for the knot.
            ends.append(center+Vector((0, 0, .067)))
        middle = a-axis*(radius*.75)+Vector((0, 0, radius*.34+.022))
        path = [ends[0], middle+Vector((0, -lead*.22, 0)),
                middle+Vector((0, lead*.22, 0)), ends[1]]
        fall = _line(ctx, gun.name+'_fixed_breeching', path, eyes[0], eyes[1])
        ctx.joint(fall, knob, 'The breeching fall passes around this cannon cascabel in its fixed rest pose.')
        parts.append(fall)
        for obj in parts:
            obj['detail_feature'] = 'gun_tackle'
            obj['detail_component'] = gun.name
            names.append(obj.name)
        ledger.append({'barrel':gun.name, 'bore_depth_m':.31*length,
                       'bore_diameter_m':1.14*radius, 'nodes':[p.name for p in parts]})
    if not ctx.gun_nodes:
        ctx.detail_features.pop('gun_tackle', None)
    ctx.rig_ledger['rope_count'] = len(ctx.rig_ledger.get('ropes', []))
    result={'scope':'Actual bored castings and fixed breeching tackle; no recoil simulation.',
            'gun_count':len(ledger), 'guns':ledger}
    ctx._v5_gun_detail_ledger=result
    return result
