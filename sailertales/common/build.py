"""Reproducible walkable SailerTales reconstructions; Blender 5.2, no add-ons.

Usage: blender -b --factory-startup --python-exit-code 1 --python
sailertales/common/build.py -- sailertales/brig/spec.json [--render]
Authoring coordinates: x across, y aft (-forward), z up. glTF: X,Y,Z=x,z,-y.
"""
import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

RNG = random.Random(1718)
VIS, COL, ROUTES, MARKERS = [], [], [], []


def p(x, s, h):
    return Vector((x, -s, h))


def material(name, color, metallic=0, wood=False):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Roughness'].default_value = 0.82 if not metallic else 0.38
    bs.inputs['Metallic'].default_value = metallic
    if wood:
        im = bpy.data.images.get('WoodGrain')
        if im is None:
            im = bpy.data.images.new('WoodGrain', width=128, height=128)
            pixels = []
            for y in range(128):
                for x in range(128):
                    v = 0.68 + 0.12 * math.sin(y * 2.1 + 3 * math.sin(x * 0.045))
                    v += RNG.uniform(-0.045, 0.045)
                    if y % 16 == 0:
                        v *= 0.5
                    pixels.extend((v, v * 0.82, v * 0.57, 1))
            im.pixels = pixels
            im.pack()
        tex = m.node_tree.nodes.new('ShaderNodeTexImage')
        tex.image = im
        mix = m.node_tree.nodes.new('ShaderNodeMixRGB')
        mix.blend_type = 'MULTIPLY'
        mix.inputs[0].default_value = 1
        mix.inputs[2].default_value = (*color, 1)
        m.node_tree.links.new(tex.outputs['Color'], mix.inputs[1])
        m.node_tree.links.new(mix.outputs[0], bs.inputs['Base Color'])
    return m


def mesh(name, vertices, faces, mat, collision=False, surface=False):
    me = bpy.data.meshes.new(name)
    me.from_pydata(vertices, [], faces)
    me.update()
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    me.materials.append(mat)
    uv = me.uv_layers.new(name='UVMap')
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (co.y / 2, co.x / 2 + co.z / 3)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(me)
    bm.free()
    VIS.append(o)
    if collision:
        o['physics'] = 'walk_surface' if surface else 'solid'
        c = o.copy()
        c.data = o.data.copy()
        c.name = 'COL_' + name
        bpy.context.collection.objects.link(c)
        COL.append(c)
        c.hide_render = True
    return o


def cube(name, pos, size, mat, collision=True, surface=False):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    o = bpy.context.object
    o.name = name
    o.dimensions = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat)
    VIS.append(o)
    if collision:
        o['physics'] = 'walk_surface' if surface else 'solid'
        c = o.copy()
        c.data = o.data.copy()
        c.name = 'COL_' + name
        bpy.context.collection.objects.link(c)
        c.hide_render = True
        COL.append(c)
    return o


def rod(name, a, b, radius, mat, collision=False, vertices=10):
    a, b = Vector(a), Vector(b)
    bpy.ops.mesh.primitive_cone_add(vertices=vertices, radius1=radius,
                                   radius2=radius * 0.82, depth=(b-a).length,
                                   location=(a+b)/2)
    o = bpy.context.object
    o.name = name
    o.rotation_euler = (b-a).to_track_quat('Z', 'Y').to_euler()
    o.data.materials.append(mat)
    VIS.append(o)
    if collision:
        o['physics'] = 'solid'
        c = o.copy()
        c.data = o.data.copy()
        c.name = 'COL_' + name
        bpy.context.collection.objects.link(c)
        c.hide_render = True
        COL.append(c)
    return o


def line(name, points, radius, mat):
    for i in range(len(points)-1):
        rod(name + '_' + str(i), points[i], points[i+1], radius, mat, vertices=6)


def marker(name, point):
    o = bpy.data.objects.new(name, None)
    o.location = point
    o.empty_display_size = 0.2
    bpy.context.collection.objects.link(o)
    MARKERS.append(o)
    return o


def route(name, pts):
    ROUTES.append({'name': name, 'points': [[q.x, q.z, -q.y] for q in pts]})
    for i, q in enumerate(pts):
        marker('route_' + name + '_' + str(i), q)


def halfwidth(s, L, B):
    u = s / (L/2)
    # Rounded full midbody; narrow bow and a transom stern.
    return B/2 * (max(0.012, 1-abs(max(u, -0.92))**3))**0.52


def hull(spec, mats, wreck=False):
    L, B, draft, deck = [spec[k] for k in ('length', 'beam', 'draft', 'deck')]
    segments, rings = 48, 12
    end = 0.22 if wreck else 0.99
    vs, fs = [], []
    for i in range(segments+1):
        s = (-0.98 + (end+0.98)*i/segments)*L/2
        u = s/(L/2)
        w = halfwidth(s, L, B)
        keel = -draft + 0.38*abs(u)**3
        rim = deck + (0.9 if not spec['small'] else 0.2) + abs(u)**4*0.5
        for j in range(rings+1):
            a = -math.pi/2 + math.pi*j/rings
            vs.append(p(w*math.sin(a), s, keel+(rim-keel)*(1-math.cos(a))))
    for i in range(segments):
        for j in range(rings):
            a = i*(rings+1)+j
            fs.append((a, a+1, a+rings+2, a+rings+1))
    fs += [tuple(range(rings, -1, -1)),
           tuple(segments*(rings+1)+j for j in range(rings+1))]
    o = mesh('Hull_shell', vs, fs, mats['hull'])
    mod = o.modifiers.new('Physical planking thickness', 'SOLIDIFY')
    mod.thickness = 0.07 if spec['small'] else 0.12
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier=mod.name)
    o['physics'] = 'solid'
    c = o.copy(); c.data = o.data.copy(); c.name = 'COL_Hull_shell'
    bpy.context.collection.objects.link(c); c.hide_render = True; COL.append(c)
    for poly in o.data.polygons:
        poly.use_smooth = True
    # Wales, gunwale, inner framing; all outside the designated walking strip.
    for sign in [-1, 1]:
        for level in ([deck+0.26] if spec['small'] else [deck-0.6, deck+0.35, deck+0.92]):
            pts = [p(sign*halfwidth(s, L, B), s, level+0.5*abs(s/(L/2))**4)
                   for s in [(-0.96+(end+0.96)*k/32)*L/2 for k in range(33)]]
            line('Gunwale' if level > deck else 'Wale', pts, 0.055 if spec['small'] else 0.09, mats['trim'])
        for k in range(1, 15):
            s = (-0.9+(end+0.9)*k/15)*L/2
            inset = 0.025 if spec['small'] else 0.14
            x = sign*(halfwidth(s,L,B)-inset)
            low, high, radius = (-0.18,0.16,0.018) if spec['small'] else (-0.65,0.8,0.055)
            if spec['small']:
                # Follow the bowl section instead of hanging vertical timbers
                # outside a narrow boat's narrowing underwater body.
                u = s/(L/2)
                keel = -draft+0.38*abs(u)**3
                rim = deck+0.2+abs(u)**4*0.5
                bottom_h = max(deck+low,keel+0.04)
                def rib_x(h):
                    c = 1-max(0,min(1,(h-keel)/(rim-keel)))
                    return sign*max(0.01,halfwidth(s,L,B)*math.sqrt(1-c*c)-0.025)
                rod('Frame_head',p(rib_x(bottom_h),s,bottom_h),
                    p(rib_x(deck+high),s,deck+high),radius,mats['wood'])
            else:
                rod('Frame_head',p(x,s,deck+low),p(x,s,deck+high),radius,mats['wood'])
    return o


def floor(spec, mats, name, h, s0, s1, width=None, hole=None):
    L, B = spec['length'], spec['beam']
    cuts = [s0, s1]
    if hole:
        cuts += [hole[2], hole[3]]
    # More cuts keep the deck inside the real rounded hull.
    cuts += [s0+(s1-s0)*k/36 for k in range(1,36)]
    cuts = sorted(set(c for c in cuts if s0 <= c <= s1))
    vs, fs = [], []
    for a,b in zip(cuts,cuts[1:]):
        w = min(halfwidth(a,L,B),halfwidth(b,L,B))-0.23
        if width is not None:
            w = min(w,width/2)
        spans = [(-w,w)]
        if hole and hole[2] < (a+b)/2 < hole[3]:
            spans = [(-w,hole[0]),(hole[1],w)]
        for x0,x1 in spans:
            if x1 <= x0:
                continue
            n=len(vs)
            vs += [p(x0,a,h-0.12),p(x1,a,h-0.12),p(x1,b,h-0.12),p(x0,b,h-0.12),
                   p(x0,a,h),p(x1,a,h),p(x1,b,h),p(x0,b,h)]
            fs += [tuple(n+j for j in f) for f in [(0,3,2,1),(4,5,6,7),(0,1,5,4),
                                                   (1,2,6,5),(2,3,7,6),(3,0,4,7)]]
    return mesh(name,vs,fs,mats['deck'],True,True)


def stairs(name, x, s0, s1, bottom, top, width, mats):
    # An inclined planked companionway has the same continuous top in both GLBs.
    # Embedded transverse strips suggest treads without projecting into a capsule.
    vs = [p(x-width/2,s0,bottom-0.12),p(x+width/2,s0,bottom-0.12),
          p(x+width/2,s1,top-0.12),p(x-width/2,s1,top-0.12),
          p(x-width/2,s0,bottom),p(x+width/2,s0,bottom),
          p(x+width/2,s1,top),p(x-width/2,s1,top)]
    o=mesh(name+'_ramp',vs,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),
                          (2,3,7,6),(3,0,4,7)],mats['wood'],True,True)
    o['construction'] = 'inclined planked companionway'
    N=max(1,math.ceil(abs(top-bottom)/0.18))
    for k in range(N):
        t=(k+0.5)/N
        tread = cube(name+'_tread_%02d'%k,
                     p(x,s0+(s1-s0)*t,bottom+(top-bottom)*t-0.018),
                     (width,0.035,0.025),mats['trim'],False)
        tread.rotation_euler.x = -math.atan2(top-bottom, s1-s0)
    for sign in [-1,1]:
        line(name+'_handrail',[p(x+sign*(width/2-0.015),s0,bottom+0.95),
                              p(x+sign*(width/2-0.015),s1,top+0.95)],0.032,mats['trim'])
        for t in [0,0.5,1]:
            s=s0+(s1-s0)*t; z=bottom+(top-bottom)*t
            rod(name+'_post',p(x+sign*width/2,s,z),p(x+sign*width/2,s,z+0.95),0.027,mats['trim'])


def barrel(name,x,s,h,mats,scale=1):
    rod(name,p(x,s,h),p(x,s,h+0.75*scale),0.32*scale,mats['wood'],True,12)
    for z in [0.12,0.63]:
        bpy.ops.mesh.primitive_torus_add(major_radius=0.31*scale,minor_radius=0.025*scale,
                                       major_segments=12,minor_segments=4,location=p(x,s,h+z*scale))
        o=bpy.context.object; o.name=name+'_hoop';o.data.materials.append(mats['iron']);VIS.append(o)


def canvas(name, corners, mats, belly=0.35):
    # Separate double-sided triangulated cloth, with a sewn panel texture.
    # Corners: foot-port, foot-starboard, head-starboard, head-port.
    vs,fs=[],[]
    N=10
    for j in range(N+1):
        v=j/N
        left=corners[0].lerp(corners[3],v)
        right=corners[1].lerp(corners[2],v)
        for i in range(N+1):
            u=i/N; q=left.lerp(right,u)
            q.y-=belly*math.sin(math.pi*u)*math.sin(math.pi*v)
            vs.append(q)
    for j in range(N):
        for i in range(N):
            a=j*(N+1)+i;fs += [(a,a+1,a+N+2),(a,a+N+2,a+N+1)]
    o=mesh(name,vs,fs,mats['canvas'])
    o['role']='sail'
    o['trim']='authored pose only; reroute running rigging for other trims'
    for poly in o.data.polygons: poly.use_smooth=True
    # Boundary ropes are edge attachments, never diagonals through cloth.
    for i in range(4):
        rod('Bolt_'+name,corners[i],corners[(i+1)%4],0.012,mats['rope'])
    return o


def rig(spec,mats):
    L,B,D=spec['length'],spec['beam'],spec['deck']
    kind=spec['rig']
    if kind=='none': return
    if spec['small']:
        mast_s=0.85; mast_x=0.22; H=4.75
        rod('Mast',p(mast_x,mast_s,D-0.4),p(mast_x,mast_s,H),0.085,mats['spar'],True)
        rod('Yard',p(-1.55,mast_s+0.16,4.25),p(1.55,mast_s+0.16,4.25),0.055,mats['spar'])
        # The original low sail obstructs a standing player. Foot raised deliberately.
        canvas('Sail_1',[p(-1.45,mast_s+0.25,D+2.15),p(1.45,mast_s+0.25,D+2.15),
                         p(1.35,mast_s+0.25,4.2),p(-1.35,mast_s+0.25,4.2)],mats,0.22)
        route('mast_bypass',[p(-0.38,-0.15,D),p(-0.38,0.85,D),p(-0.3,1.45,D)])
        return
    masts=[(L*0.20, D+L*0.68),(-L*0.14,D+L*0.77)] if kind in ['square','furled'] else [(L*0.10,D+L*0.80)]
    for mi,(s,H) in enumerate(masts):
        radius=B*0.029
        rod('Mast_%d'%mi,p(0,s,spec['sole']),p(0,s,H),radius,mats['spar'],True,12)
        # Shrouds are aft of their mast and aft of every deployed square sail.
        for sign in [-1,1]:
            for k in range(3):
                line('Shroud',[p(sign*(B/2-0.12),s-1.2-k*0.4,D+0.9),
                                p(sign*0.12,s-0.10,H*0.76)],0.026,mats['rope'])
        if kind in ['square','furled']:
            for yi,(f,wf,hf) in enumerate([(0.48,1.65,0.24),(0.76,1.2,0.18),(0.95,0.78,0.12)]):
                z=D+(H-D)*f; w=B*wf; sh=(H-D)*hf
                rod('Yard_%d_%d'%(mi,yi),p(-w/2,s+0.28,z),p(w/2,s+0.28,z),0.085,mats['spar'])
                if kind=='furled':
                    rod('Furled_%d_%d'%(mi,yi),p(-w*0.45,s+0.34,z-0.17),p(w*0.45,s+0.34,z-0.17),0.21,mats['canvas'])
                else:
                    canvas('Sail_%d_%d'%(mi,yi),[p(-w*0.46,s+0.40,z-sh),p(w*0.46,s+0.40,z-sh),
                                                                 p(w*0.47,s+0.40,z-0.12),p(-w*0.47,s+0.40,z-0.12)],mats,B*0.12)
                for sign in [-1,1]:
                    # Lift follows the edge above its sail; no downward diagonal across it.
                    line('Lift',[p(sign*w/2,s+0.28,z),p(0,s,H+0.2)],0.017,mats['rope'])
        else:
            boomH=D+2.35; aft=s-L*0.35
            rod('Boom',p(0.12,s,boomH),p(0.12,aft,boomH),0.08,mats['spar'])
            rod('Gaff',p(0.12,s,H*0.74),p(0.12,aft+1,H*0.86),0.065,mats['spar'])
            canvas('Sail_Main',[p(0.20,aft,boomH+0.1),p(0.20,s-0.2,boomH+0.1),
                                p(0.20,s-0.2,H*0.74),p(0.20,aft+1,H*0.86)],mats,0.25)
    # Bowsprit and forestay stay ahead of the foremost cloth (positive s).
    s,H=masts[0]; bs=p(0,L*0.69,D+2.2)
    rod('Bowsprit',p(0,L*0.36,D+0.7),bs,0.12,mats['spar'])
    line('Forestay',[p(0,s+0.08,H),bs],0.036,mats['rope'])
    # Masthead pennant, independent node.
    mesh('Pennant',[p(0,s,H),p(0,s,H+0.7),p(2,s,H+0.2)],[(0,1,2)],mats['flag'])


def big_ship(spec,mats):
    L,B,D,sole=[spec[k] for k in ['length','beam','deck','sole']]
    hull(spec,mats)
    # Hatch opening is actually absent from render AND collision geometry.
    hx=0.65 if B<6 else 1.25; hw=1.24 if B<6 else 1.32; s0=-2.7; s1=2.7
    floor(spec,mats,'Main_deck',D,-L*0.46,L*0.46,hole=(hx-hw/2,hx+hw/2,s0-0.6,s1+0.3))
    floor(spec,mats,'Hold_sole',sole,-L*0.40,L*0.39,width=B*0.53)
    stairs('Companionway',hx,s0,s1,sole,D,hw,mats)
    cube('Companionway_top_landing',p(hx,s1+0.32,D-0.06),(hw,0.68,0.12),mats['deck'],True,True)
    # Approach the landing along its centre, not diagonally through its handrail.
    route('deck_to_hold',[p(-0.75,3.8,D),p(hx,3.8,D),p(hx,s1,D),p(hx,s0,sole),
                          p(hx,s0-0.5,sole),p(-0.7,s0-0.5,sole)])
    route('main_deck',[p(-0.75,-L*0.25,D),p(-0.75,-3.5,D),p(-0.75,3.5,D),p(-0.75,L*0.30,D)])
    # Cabin is on main-deck level under a raised quarterdeck; door 1.3 x 2.15 m.
    front=-L*0.29; stern=-L*0.43; roof=D+2.4; cw=min(B*0.56,3.9)
    for sign in [-1,1]:
        cube('Cabin_side',p(sign*cw/2,(front+stern)/2,D+1.18),(0.12,front-stern,2.36),mats['wood'])
        cube('Cabin_front',p(sign*(cw/4+0.325),front,D+1.18),(cw/2-0.65,0.14,2.36),mats['wood'])
    cube('Door_lintel',p(0,front,D+2.27),(1.30,0.14,0.18),mats['trim'])
    cube('Cabin_stern',p(0,stern,D+1.18),(cw,0.12,2.36),mats['wood'])
    cube('Quarterdeck',p(0,(front+stern)/2,roof),(cw+0.2,front-stern+0.3,0.16),mats['deck'],True,True)
    # Open door hinged at port jamb; a game can rotate it, updating its collider.
    door=cube('Door_Captain_open',p(-0.65,front-0.65,D+1.05),(0.08,1.27,2.10),mats['trim'])
    marker('hinge_Captain',p(-0.65,front,D))['open_angle_deg']=90
    door['state']='open';door['hinge']='hinge_Captain'
    table_x=cw/2-0.30
    cube('Chart_table',p(table_x,stern+0.7,D+0.70),(0.48,0.8,0.08),mats['deck'])
    for x in [table_x-0.26,table_x+0.26]:
        rod('Table_leg',p(x,stern+0.6,D),p(x,stern+0.6,D+0.67),0.045,mats['wood'])
    cube('Bunk',p(-cw/2+0.48,stern+0.8,D+0.36),(0.75,1.4,0.45),mats['wood'])
    for sign in [-1,1]:
        cube('Stern_window',p(sign*cw*0.27,stern-0.066,D+1.45),(0.58,0.025,0.65),mats['glass'],False)
        for xx in [-0.15,0.15]:
            cube('Window_mullion',p(sign*cw*0.27+xx,stern-0.085,D+1.45),(0.025,0.035,0.65),mats['trim'],False)
    route('captains_cabin',[p(-0.75,front+1.8,D),p(-0.75,front+0.65,D),p(0,front+0.65,D),
                            p(0,front-0.5,D),p(0,(front+stern)/2,D)])
    marker('station_helm',p(-0.7,-L*0.22,D))
    marker('station_captain',p(0,(front+stern)/2,D))
    # Helm deliberately forward of cabin bulkhead.
    rod('Helm_pedestal',p(0.6,-L*0.22,D),p(0.6,-L*0.22,D+1.1),0.10,mats['wood'],True)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.40,minor_radius=0.035,
                                   major_segments=16,minor_segments=6,location=p(0.6,-L*0.22,D+1.15),
                                   rotation=(math.pi/2,0,0))
    o=bpy.context.object;o.name='Helm_wheel';o.data.materials.append(mats['trim']);VIS.append(o)
    o['physics']='solid'
    c=o.copy();c.data=o.data.copy();c.name='COL_Helm_wheel'
    bpy.context.collection.objects.link(c);c.hide_render=True;COL.append(c)
    for sign in [-1,1]:
        for k in range(spec.get('gun_pairs',0)):
            s=-L*0.12+k*2.7; x=sign*(halfwidth(s,L,B)-0.75)
            cube('Gun_carriage',p(x,s,D+0.23),(0.85,0.8,0.35),mats['trim'])
            rod('Gun_barrel',p(x-sign*0.35,s,D+0.62),p(x+sign*0.65,s,D+0.62),0.13,mats['iron'])
            marker('muzzle_%d_%d'%(sign,k),p(x+sign*0.7,s,D+0.62))
        # cargo remains clear of the stairs and hold centre aisle
        for s in [-L*0.26,L*0.26]:
            barrel('Hold_barrel',sign*B*0.18,s,sole,mats)
    # A separate external stair reaches quarterdeck without crossing cabin ceiling.
    qx=-cw/2-0.72
    if B>7:
        # Stop the ramp at the near edge of the landing to avoid a vertical step
        # where the level platform used to overlap the rising surface.
        stairs('Quarterdeck_stair',qx,front+4.5,front+0.1,D,roof+0.08,1.24,mats)
        cube('Quarterdeck_landing',p(qx,front-0.4,roof+0.02),(1.24,1.0,0.12),mats['deck'],True,True)
        cube('Quarterdeck_link',p((qx-cw/2)/2,front-0.55,roof+0.02),(abs(qx+cw/2)+0.9,0.8,0.12),mats['deck'],True,True)
        route('quarterdeck',[p(-0.75,front+5.2,D),p(qx,front+5.2,D),
                             p(qx,front+4.5,D),p(qx,front+0.1,roof+0.08),
                             p(qx,front-0.65,roof+0.08),p(-cw/2+0.5,front-0.65,roof+0.08)])
    rig(spec,mats)
    if spec['rig']=='furled':
        for k in range(7):
            s=-L*0.42+k*L*0.86/6
            o=cube('Lantern_%d'%k,p(B/2+0.1 if k<6 else 0,s,D+1.2),(0.28,0.25,0.4),mats['lamp'],False)
            o['lamp_index']=k


def small_boat(spec,mats):
    L,B,D=spec['length'],spec['beam'],spec['deck']
    hull(spec,mats)
    floor(spec,mats,'Cockpit_sole',D,-L*0.36,L*0.36,width=B-0.35)
    # Short seats at sides leave an actual central standing lane, not a solid thwart.
    if B>1.5:
        for sign in [-1,1]:
            # Keep the 0.76 m player lane beside Mewka's offset mast clear.
            seat_s = -L*0.30 if spec['rig'] != 'none' else -0.45
            seat_length = L*0.08 if spec['rig'] != 'none' else L*0.36
            cube('Side_seat',p(sign*(B/2-0.12),seat_s,D+0.25),(0.14,seat_length,0.12),mats['wood'])
    route('cockpit',[p(0,-L*0.2,D),p(0,0,D),p(0,L*0.15,D)] if spec['rig']=='none'
          else [p(-0.30,-L*0.2,D),p(-0.38,-0.15,D)])
    marker('station_helm',p(0,-L*0.2,D))
    # Oars are stored along the gunwale, not across the standing lane.
    for sign in [-1,1]:
        rod('Oar',p(sign*(B/2+0.10),-L*0.34,D+0.5),p(sign*(B/2+0.10),L*0.26,D+0.5),0.025,mats['wood'])
    rig(spec,mats)


def wreck_ship(spec,mats):
    hull(spec,mats,True)
    # Usable aft deck, real opening, exposed floor and a ramp to cargo.
    D=spec['deck']; sole=spec['sole']
    # The retained 0.5 rad heel adds transverse slope. Lengthen the gangway so
    # its WORLD slope remains below 35 degrees; widen for an upright capsule.
    floor(spec,mats,'Wreck_deck',D,-9.8,1.0,hole=(-1.35,1.35,-6.8,1.0))
    floor(spec,mats,'Wreck_hold',sole,-8.5,1.2,width=3.5)
    stairs('Wreck_companionway',0,-6.8,0.8,D,sole,2.4,mats)
    rod('Broken_mast',p(-2.1,-5.5,D),p(-2.1,-5.5,D+3),0.24,mats['spar'],True)
    barrel('Salvage_barrel',-1,-5,sole,mats)
    marker('find_book',p(-1,-6.8,D+0.15))
    marker('find_compass',p(1.2,-5.2,D+0.2))
    route('wreck_deck_to_hold',[p(0,-8.4,D),p(0,-6.8,D),p(0,0.8,sole),p(0,1,sole)])
    # Apply authored heel to all geometry and routes, keeping real gravity vertical.
    # The approach is a level world-space gangway: shore height belongs to the engine.
    from mathutils import Matrix
    heel=spec.get('heel_deg',0)*math.pi/180
    M=Matrix.Rotation(heel,4,'Y')
    for o in VIS+COL+MARKERS:
        o.matrix_world=M@o.matrix_world
    for r in ROUTES:
        for i,(x,h,s) in enumerate(r['points']):
            q=M@p(x,s,h);r['points'][i]=[q.x,q.z,-q.y]


def select_export(objects,path):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        o.hide_set(False);o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,
                              export_extras=True,export_yup=True,export_animations=False,
                              export_materials='EXPORT',export_image_format='AUTO')


def render(spec,dest):
    for o in COL:o.hide_render=True
    # Hero view and a genuine cutaway for checking the cabin and open hatch.
    scene=bpy.context.scene
    scene.render.engine='CYCLES';scene.cycles.samples=24
    scene.render.resolution_x=1000;scene.render.resolution_y=800;scene.render.resolution_percentage=100
    scene.world.color=(0.25,0.25,0.25)
    scene.view_settings.view_transform='AgX'
    L=spec['length']; H=spec['deck']+L*0.27
    bpy.ops.object.light_add(type='AREA',location=(L*0.6,-L*0.3,L*1.2))
    light=bpy.context.object;light.data.energy=2200*L;light.data.shape='DISK';light.data.size=L
    light.rotation_euler=(Vector((0,0,0))-light.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add(location=(L*0.85,L*1.1,L*0.78))
    cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=L*1.65
    cam.rotation_euler=(Vector((0,-L*0.05,H))-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.camera=cam
    scene.render.image_settings.file_format='JPEG';scene.render.image_settings.quality=88
    scene.render.filepath=str(dest/'hero.jpg');bpy.ops.render.render(write_still=True)
    for o in VIS:
        if any(t in o.name for t in ['Sail','Yard','Mast','Shroud','Lift','Bolt_','Forestay','Furled','Quarterdeck']):
            o.hide_render=True
    cam.location=(L*0.55,L*0.65,L*0.95);cam.data.ortho_scale=L*1.15
    cam.rotation_euler=(Vector((0,0,spec['deck']))-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(dest/'deck.jpg');bpy.ops.render.render(write_still=True)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('spec');ap.add_argument('--render',action='store_true')
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    path=Path(args.spec).resolve();spec=json.loads(path.read_text(encoding='utf-8'))
    dest=path.parent;out=dest/'model';out.mkdir(exist_ok=True)
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    mats={
      'wood':material('Oak',(.57,.34,.15),wood=True),
      'deck':material('Pine_deck',(.82,.68,.45),wood=True),
      'hull':material('Hull_planking',tuple(spec.get('color',[.30,.18,.09])),wood=True),
      'trim':material('Tarred_wales',(.055,.047,.038),wood=True),
      'spar':material('Oiled_spars',(.43,.26,.12),wood=True),
      'iron':material('Forged_iron',(.065,.072,.078),.70),
      'rope':material('Hemp',(.26,.23,.17)),
      'canvas':material('Linen_canvas',(.80,.73,.55)),
      'glass':material('Cabin_glass',(.20,.35,.37),.25),
      'flag':material('Pennant',(.55,.10,.075)),
      'lamp':material('Lantern_glass',(.9,.5,.12)),
    }
    mats['canvas'].use_backface_culling=False
    if spec.get('wreck'):wreck_ship(spec,mats)
    elif spec['small']:small_boat(spec,mats)
    else:big_ship(spec,mats)
    marker('asset_origin',p(0,0,0))['vessel_id']=spec['id']
    select_export(VIS+MARKERS,out/'ship.glb')
    select_export(COL,out/'collision.glb')
    nav={'schema':1,'units':'metres','axes':'glTF: X across, Y up, Z forward',
         'player':{'radius':0.38,'height':1.85,'max_slope_deg':35},'routes':ROUTES,
         'source_commit':spec['source_commit'],'limitations':spec['limitations']}
    (dest/'navigation.json').write_text(json.dumps(nav,indent=2)+'\n',encoding='utf-8')
    # Preserve a packed authoring scene; both physics and render geometry are named.
    for o in COL:o.hide_set(True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'ship.blend'))
    if args.render:
        previews=dest/'previews';previews.mkdir(exist_ok=True);render(spec,previews)
    print('BUILT',spec['id'],len(VIS),'visual objects',len(COL),'colliders')


if __name__=='__main__':main()
