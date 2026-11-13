"""Guide-built snow-family vessels with true hollow holds and captain's cabin.

Original reference shell, stations, spars and fittings are preserved. New spaces
are explicit game reconstructions, cut into that shell rather than fake floors.
"""
import argparse
import fnmatch
import hashlib
import importlib
import json
import math
import heapq
from pathlib import Path
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix,Vector

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from v2_reference import build_reference,load_context,save_context,topology,stitch_collinear_seams


def P(x,s,z):return Vector((x,-s,z))
def gltf(p):return [p.x,p.z,-p.y]


def tag(o,kind='fitting',physics='none'):
    o['asset_role']='visual';o['kind']=kind;o['physics']=physics
    o['authored_access']=True
    return o


def mesh(ctx,name,verts,faces,material='drewno',kind='fitting',physics='none'):
    N=__import__('narzedzia')
    sk=N.Siatka(name)
    sk.verts(verts)
    for f in faces:sk.face_proj(f,material)
    o=N.to_object(sk,ctx['_v2_interiors'],recalc=True,weld=.00001)
    return tag(o,kind,physics)


def box(ctx,name,point,size,material='drewno',physics='solid'):
    N=__import__('narzedzia');sk=N.Siatka(name);N.box(sk,point,size,material)
    o=N.to_object(sk,ctx['_v2_interiors'],recalc=True)
    return tag(o,'fitting',physics)


def rod(ctx,name,a,b,r,material='drewno',physics='none'):
    N=__import__('narzedzia');sk=N.Siatka(name)
    N.cylinder(sk,a,b,r,r*.94,material,sides=10)
    return tag(N.to_object(sk,ctx['_v2_interiors'],recalc=True),'fitting',physics)


def remove(o):
    if o is not None:
        for child in list(o.children):
            child.matrix_world=child.matrix_world.copy();child.parent=None
        bpy.data.objects.remove(o,do_unlink=True)


def cut(target,cutter,reason,operation='DIFFERENCE'):
    before=topology(target)
    if before['non_manifold_edges']:
        raise RuntimeError('Boolean input is not closed: '+str(before))
    cutter.data.materials.clear()
    for m in target.data.materials:cutter.data.materials.append(m)
    # Cut surfaces use oak, retaining the same slot order as the target.
    oak=next((i for i,m in enumerate(target.data.materials) if m and m.name.startswith('drewno')),0)
    for poly in cutter.data.polygons:poly.material_index=oak
    mod=target.modifiers.new(reason,'BOOLEAN');mod.operation=operation
    mod.solver='MANIFOLD';mod.object=cutter;mod.material_mode='INDEX'
    bpy.context.view_layer.objects.active=target
    with bpy.context.temp_override(object=target,active_object=target):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    remove(cutter)
    result=stitch_collinear_seams(target)
    if result['after']['non_manifold_edges']:
        raise RuntimeError(reason+' left non-manifold geometry: '+str(result))
    return {'operation':reason,'before':before,'after':result['after']}


def box_cutter(ctx,name,x,s,z,w,l,h):
    return box(ctx,name,P(x,s,z),(w,l,h),'drewno',physics='none')


def cavity(ctx,name,s_min,s_max,sole,roof_offset):
    """Closed, section-lofted void inside the documented outer planking.

    Every side offset comes from kd.H(s,z), not the previous generic hull curve.
    The ceiling follows the reference sheer and camber.
    """
    kd=ctx['kd'];verts=[];faces=[];sections=45
    for s in np.linspace(s_min,s_max,sections):
        ztop=float(kd.deck_c(s))+roof_offset-.18
        side=[]
        for z in np.linspace(sole,ztop,12):
            width=float(kd.H(s,z)[0])-.18
            if width<.25:raise RuntimeError(name+' reaches narrow deadwood')
            side.append((width,float(z)))
        # Bottom left -> bottom right -> starboard side up -> ceiling -> port down.
        ring=[P(-side[0][0],s,sole),P(side[0][0],s,sole)]
        ring.extend(P(w,s,z) for w,z in side[1:])
        wtop=side[-1][0]
        for x in np.linspace(wtop,-wtop,13)[1:]:
            ring.append(P(float(x),s,float(kd.deck_z(s,x))+roof_offset-.18))
        ring.extend(P(-w,s,z) for w,z in reversed(side[1:-1]))
        if len(verts)==0:ring_count=len(ring)
        if len(ring)!=ring_count:raise RuntimeError('Inconsistent cavity section')
        verts.extend(ring)
    for i in range(sections-1):
        for j in range(ring_count):
            a=i*ring_count+j;b=i*ring_count+(j+1)%ring_count
            faces.append((a,b,b+ring_count,a+ring_count))
    faces.append(tuple(reversed(range(ring_count))))
    faces.append(tuple((sections-1)*ring_count+j for j in range(ring_count)))
    o=mesh(ctx,name,verts,faces,kind='helper')
    o['asset_role']='presentation'
    return o


def plank_ramp(ctx,name,x,s_bottom,s_top,z_bottom,z_top,width):
    v=[P(x-width/2,s_bottom,z_bottom-.14),P(x+width/2,s_bottom,z_bottom-.14),
       P(x+width/2,s_top,z_top-.14),P(x-width/2,s_top,z_top-.14),
       P(x-width/2,s_bottom,z_bottom),P(x+width/2,s_bottom,z_bottom),
       P(x+width/2,s_top,z_top),P(x-width/2,s_top,z_top)]
    o=mesh(ctx,name,v,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)],
           'drewno','surface','walk_surface')
    # Thin transverse strips sit below the ramp plane: identical visual/physics envelope.
    count=math.ceil(abs(z_top-z_bottom)/.17)
    for k in range(count):
        t=(k+.5)/count;s=s_bottom+(s_top-s_bottom)*t;z=z_bottom+(z_top-z_bottom)*t
        strip=box(ctx,name+'_plank_%02d'%k,P(x,s,z-.018),(width,.032,.024),'drewno_ciemne','none')
        strip.rotation_euler.x=-math.atan2(z_top-z_bottom,s_top-s_bottom)
    for sign in [-1,1]:
        a=P(x+sign*(width/2+.06),s_bottom,z_bottom+.95)
        b=P(x+sign*(width/2+.06),s_top,z_top+.95)
        rod(ctx,name+'_rail_'+('port' if sign>0 else 'starboard'),a,b,.03)
        for t in [0,.5,1]:
            s=s_bottom+(s_top-s_bottom)*t;z=z_bottom+(z_top-z_bottom)*t
            rod(ctx,name+'_post_'+str(sign)+'_'+str(t),P(x+sign*(width/2+.06),s,z),
                P(x+sign*(width/2+.06),s,z+.95),.033)
    return o


def route(ctx,name,points,mode='walk'):
    ctx['_v2_routes'].append({'name':name,'mode':mode,'points':[gltf(p) for p in points]})


def augment_interiors(ctx,spec):
    N=__import__('narzedzia');kd=ctx['kd'];K=ctx['K'];U=ctx['PR'].UKLAD
    ctx['_v2_interiors']=N.kolekcja('v2_interiors',ctx['root'])
    ctx['_v2_routes']=[];ops=[]
    hull=ctx['obj']['kadlub'];tag(hull,'hull','walk_surface')
    # Ensure oak is an available Boolean material slot, after all reference paints.
    if N.MATERIALY_REJESTR['drewno'] not in list(hull.data.materials):
        hull.data.materials.append(N.MATERIALY_REJESTR['drewno'])
    main_sole=float(kd.deck_c(0))
    hold_sole=main_sole-2.5
    hold=cavity(ctx,'hold_void',-spec['length']*.14,spec['length']*.30,hold_sole,0)
    ops.append(cut(hull,hold,'hollow_hold'))
    sq=K['POLPOKLAD_S'];cabin_sole=float(kd.deck_c(sq))+K['POLPOKLAD_H']-2.45
    room=cavity(ctx,'captains_cabin_void',-spec['length']*.44,sq-.05,cabin_sole,K['POLPOKLAD_H'])
    ops.append(cut(hull,room,'hollow_captains_cabin'))
    # Open the original main hatch, retaining its documented 2.4 x 1.8 m family.
    L=U['LUK_GLOWNY'];s0,s1,hx=L['s0'],L['s1'],L['pol_x']
    hatch=bpy.data.objects.get('luk_glowny');remove(hatch)
    import wyposazenie
    hatch=wyposazenie.luk(ctx,'main_hatch_open_coaming',s0,s1,hx,L['h'],krata=False)
    tag(hatch,'fitting','solid')
    zmain=float(kd.deck_c((s0+s1)/2))
    cutter=box_cutter(ctx,'main_hatch_void',0,(s0+s1)/2,zmain-.25,2*hx,s1-s0,1.1)
    ops.append(cut(hull,cutter,'open_main_hatch'))
    # A steep ladder is a climb interaction, not a falsely passable 35-degree floor.
    ladder_s=s0+.23
    for sign in [-1,1]:
        o=rod(ctx,'hold_ladder_stringer_'+str(sign),P(sign*.44,ladder_s,hold_sole),
            P(sign*.44,ladder_s,zmain+1.7),.045,physics='solid')
        o['kind']='ladder';o['climbable']=True;o['physics']='solid'
    for i,z in enumerate(np.arange(hold_sole+.2,zmain+.75,.27)):
        o=rod(ctx,'hold_ladder_rung_%02d'%i,P(-.43,ladder_s,float(z)),P(.43,ladder_s,float(z)),.025)
        o['kind']='ladder';o['climbable']=True;o['physics']='solid'
    for name,a,b in [('mount_post',P(1.4,ladder_s,float(kd.deck_z(ladder_s,1.4))),P(1.4,ladder_s,zmain+1.7)),
                     ('mount_rail',P(.44,ladder_s,zmain+1.7),P(1.4,ladder_s,zmain+1.7))]:
        o=rod(ctx,'hold_ladder_'+name,a,b,.035);o['kind']='ladder';o['climbable']=True;o['physics']='solid'
    climb_s=ladder_s+.45
    route(ctx,'main_deck_hatch_approach',[P(1.4,climb_s,float(kd.deck_z(climb_s,1.4))),
        P(1.4,s0-.6,float(kd.deck_z(s0-.6,1.4)))])
    route(ctx,'hold_ladder',[P(1.4,climb_s,float(kd.deck_z(climb_s,1.4))),
        P(1.4,climb_s,zmain+.50),P(0,climb_s,zmain+.50),P(0,climb_s,hold_sole)],'climb')
    route(ctx,'hold_aisle',[P(0,climb_s,hold_sole),P(-1,climb_s,hold_sole),
        P(-1,1.2,hold_sole),P(-1,-spec['length']*.10,hold_sole)])
    # Replace decorative sealed reference doors with one real open companionway.
    remove(bpy.data.objects.get('grodz_drzwi'))
    # The reference quarterdeck companion has dummy steps projecting into the
    # unmodelled cabin. Its function is replaced by the real side entrance below.
    remove(bpy.data.objects.get('zejsciowka'))
    door_x=1.45
    ops.append(cut(hull,box_cutter(ctx,'cabin_portal_void',door_x,sq,cabin_sole+1.08,1.30,1.0,2.20),
                   'open_captains_portal'))
    entry_top=sq+2.0
    ops.append(cut(hull,box_cutter(ctx,'cabin_stairwell_void',door_x,(sq+.06+entry_top)/2,
                   cabin_sole+1.6,1.30,entry_top-(sq+.06),3.4),'open_sunken_cabin_companion'))
    top_z=float(kd.deck_z(entry_top,door_x))
    plank_ramp(ctx,'captain_companionway',door_x,entry_top,sq-.25,top_z,cabin_sole,1.15)
    # Jambs and a hinged open door are separate closed meshes at the true pivot.
    for dx in [-.70,.70]:
        box(ctx,'captain_door_jamb_'+str(dx),P(door_x+dx,sq-.03,cabin_sole+1.1),(.09,.14,2.2))
    box(ctx,'captain_door_lintel',P(door_x,sq-.03,cabin_sole+2.23),(1.49,.14,.10))
    hinge=bpy.data.objects.new('captain_door_hinge',None);ctx['_v2_interiors'].objects.link(hinge)
    hinge.location=P(door_x-.62,sq-.04,cabin_sole);hinge['asset_role']='marker';hinge['control']='door'
    hinge.rotation_euler.z=math.pi/2
    hinge['axis']='local_z';hinge['range_deg']=[0,90];hinge['authored_angle_deg']=90
    panel=box(ctx,'captain_door_open',P(door_x-.62,sq-.67,cabin_sole+1.05),(.06,1.24,2.1),'drewno_ciemne')
    mw=panel.matrix_world.copy();panel.parent=hinge;panel.matrix_world=mw
    panel['hinge']=hinge.name;panel['control']='captain_door'
    # Furniture stays outboard, and every leg rests on the new cabin sole.
    centre=(sq-spec['length']*.40)/2
    bx=-1.6;tx=1.9
    box(ctx,'captain_bunk_frame',P(bx,centre,cabin_sole+.30),(.82,2.0,.40),'drewno')
    box(ctx,'captain_bunk_mattress',P(bx,centre,cabin_sole+.57),(.76,1.9,.14),'plotno')
    for dx in [-.30,.30]:
        for ds in [-.8,.8]:
            box(ctx,'captain_bunk_leg_'+str(dx)+'_'+str(ds),P(bx+dx,centre+ds,cabin_sole+.05),(.10,.10,.10),'drewno')
    box(ctx,'captain_chart_table',P(tx,centre,cabin_sole+.78),(.85,1.3,.08),'drewno')
    for dx in [-.30,.30]:
        for ds in [-.5,.5]:
            rod(ctx,'chart_table_leg_'+str(dx)+'_'+str(ds),P(tx+dx,centre+ds,cabin_sole),
                P(tx+dx,centre+ds,cabin_sole+.74),.045,physics='solid')
    # Both complete pump/lever groups move outboard, clearing the real cabin
    # companion to starboard and quarterdeck companion to port.
    moved=[]
    for nm in ['pompa_L','pompa_L_dzwignia','pompa_P','pompa_P_dzwignia']:
        o=bpy.data.objects.get(nm)
        if o is not None:o.location.x+=1.25 if nm.startswith('pompa_L') else -1.25;moved.append(nm)
    route(ctx,'captains_cabin',[P(door_x,entry_top+.55,float(kd.deck_z(entry_top+.55,door_x))),
        P(door_x,entry_top,top_z),P(door_x,sq-.25,cabin_sole),
        P(door_x,sq-1.0,cabin_sole),P(0,sq-1.0,cabin_sole),P(0,centre,cabin_sole)])
    # Gentler full-width companionway to quarterdeck, with the same platform.
    remove(bpy.data.objects.get('schody_rufowe'))
    qx=-1.45
    qbottom=sq+2.55;qtop=sq-.14
    qz0=float(kd.deck_z(qbottom,qx));qz1=float(kd.deck_z(qtop,qx))+K['POLPOKLAD_H']+.012
    # Move the real guard opening with the stairs; the old centre opening is
    # closed by a rail and balusters so it does not become an unprotected drop.
    guard=bpy.data.objects.get('balustrada_progu')
    if guard is not None:
        zguard=float(kd.deck_z(sq-.08,qx))+K['POLPOKLAD_H']
        ops.append(cut(guard,box_cutter(ctx,'quarterdeck_guard_opening',qx,sq-.08,zguard+.60,
            1.34,.50,1.60),'relocate_quarterdeck_guard_opening'))
        tag(guard,'fitting','solid')
    qs=sq-.08
    for height in [.04,.89]:
        rod(ctx,'quarterdeck_closed_gap_rail_'+str(height),
            P(-.66,qs,float(kd.deck_z(qs,-.66))+K['POLPOKLAD_H']+height),
            P(.66,qs,float(kd.deck_z(qs,.66))+K['POLPOKLAD_H']+height),.035,physics='solid')
    for x in [-.44,0,.44]:
        z=float(kd.deck_z(qs,x))+K['POLPOKLAD_H']
        rod(ctx,'quarterdeck_closed_gap_post_'+str(x),P(x,qs,z),P(x,qs,z+.89),.035,physics='solid')
    plank_ramp(ctx,'quarterdeck_companionway',qx,qbottom,qtop,qz0,qz1,1.1)
    route(ctx,'quarterdeck_access',[P(qx,qbottom,qz0),P(qx,qtop,qz1),
        P(qx,sq-.9,float(kd.deck_z(sq-.9,qx))+K['POLPOKLAD_H'])])
    # Fore/aft port-side circulation connects the hatch and both companionways.
    xs=-2.15
    route(ctx,'main_deck_circulation',[P(xs,s,float(kd.deck_z(s,xs)))
        for s in np.linspace(sq+1.5,spec['length']*.27,11)])
    ctx['_v2_interior_design']={'operations':ops,'hold_floor_m':hold_sole,'cabin_floor_m':cabin_sole,
        'hatch':{'s0':s0,'s1':s1,'half_width':hx,'mode':'climb'},
        'captain_door_width_m':1.30,'captain_door_height_m':2.20,
        'cabin_floor_lowering_m':float(kd.deck_c(sq))-cabin_sole,
        'reference_pump_relocations':moved,'quarterdeck_gradient_deg':math.degrees(math.atan2(qz1-qz0,qbottom-qtop)),
        'quarterdeck_stair_x_m':qx,'quarterdeck_guard':'opening moved to port stair; old centre gap closed',
        'basis':'Ch.03 hollow framing, Ch.04 decks/cabin, Ch.09 hatch ladders; interior layout is game inference'}
    return ctx['_v2_interior_design']


def stow_capstan(ctx):
    """Removable handspikes are racked for the underway walking configuration."""
    N=__import__('narzedzia');U=ctx['PR'].UKLAD['KABESTAN'];kd=ctx['kd']
    body=bpy.data.objects.get('kabestan_beben')
    if body is None:return None
    centre=P(0,U['s'],float(kd.deck_c(U['s'])))
    sk=N.Siatka('capstan_keep_drum')
    N.cylinder(sk,centre+Vector((0,0,-.05)),centre+Vector((0,0,U['h']+.1)),
               U['r_glowica']+.045,U['r_glowica']+.045,'drewno',sides=64)
    cutter=N.to_object(sk,ctx['_v2_interiors'],recalc=True)
    result=cut(body,cutter,'stow_removable_capstan_bars','INTERSECT')
    removed=[]
    for o in list(bpy.context.scene.objects):
        if o.type=='MESH' and ('kabestan' in o.name or 'capstan' in o.name) and o is not body and \
           o.name not in ('kabestan_podstawa',) and (o.name.startswith('lina_') or o.get('kind')=='rope'):
            removed.append(o.name);remove(o)
    # Some source realizations merge the swifter into a broader rope object.
    # Delete only the connected mesh components at the documented swifter circle.
    for o in list(bpy.context.scene.objects):
        if o.type!='MESH' or not o.name.startswith('lina_'):continue
        bm=bmesh.new();bm.from_mesh(o.data);seen=set();delete=[]
        for v in bm.verts:
            if v in seen:continue
            group={v};stack=[v];seen.add(v)
            while stack:
                q=stack.pop()
                for e in q.link_edges:
                    w=e.other_vert(q)
                    if w not in seen:seen.add(w);group.add(w);stack.append(w)
            coords=[o.matrix_world@vv.co for vv in group]
            if len(coords)>3 and all(abs(p.z-centre.z-U['h_draga']-.05)<.035 and
                abs(math.hypot(p.x-centre.x,p.y-centre.y)-(U['r_draga']-.06))<.05 for p in coords):
                delete.extend(group)
        if delete:
            bmesh.ops.delete(bm,geom=delete,context='VERTS');bm.to_mesh(o.data);removed.append(o.name+':swifter')
        bm.free()
    s=ctx['K']['POLPOKLAD_S']+1.5
    zdeck=float(kd.deck_z(s,-3))
    side_x=-min(float(kd.H(ss,zdeck+.6)[0]) for ss in [s-.75,s+.75])+.70
    zdeck=float(kd.deck_z(s,side_x))
    length=U['r_draga']-U['r_glowica']
    bars=[]
    for i in range(8):
        row=i//2;column=i%2
        x=side_x+(column-.5)*.12;z=zdeck+.32+row*.13
        sk=N.Siatka('capstan_bar_stowed_%02d'%i)
        a=P(x,s-length/2,z);b=P(x,s+length/2,z)
        N.oriented_box(sk,a,b,.10,.10,'drewno')
        o=tag(N.to_object(sk,ctx['_v2_interiors'],recalc=True),'fitting','solid')
        bars.append(o.name)
    for ds in [-length*.35,length*.35]:
        post_floor=float(kd.deck_z(s+ds,side_x-.16));post_top=zdeck+1.06
        box(ctx,'capstan_bar_rack_post_'+str(ds),P(side_x-.16,s+ds,(post_floor+post_top)/2),(.10,.10,post_top-post_floor),'drewno_ciemne')
        for row in range(4):
            box(ctx,'capstan_bar_rack_shelf_'+str(ds)+'_'+str(row),P(side_x+.01,s+ds,zdeck+.24+row*.13),(.40,.12,.06),'drewno_ciemne')
    result.update({'state':'underway; bars and swifter removed from working circle',
        'stored_bar_objects':bars,'bar_length_m':length,'removed_swifter_geometry':removed,
        'guide_basis':'Ch.09 capstan removable handspikes; rack arrangement is game inference'})
    ctx['_v2_capstan_state']=result
    return result


def scene_records(objects):
    """Geometry snapshot for planning; acceptance independently reimports GLBs."""
    from mathutils.bvhtree import BVHTree
    records=[];dg=bpy.context.evaluated_depsgraph_get()
    for o in objects:
        if o.type!='MESH' or o.hide_render:continue
        me=bpy.data.meshes.new_from_object(o.evaluated_get(dg));me.calc_loop_triangles()
        triangles=[tuple(o.matrix_world@me.vertices[i].co for i in t.vertices) for t in me.loop_triangles]
        vertices=[p for tri in triangles for p in tri]
        if not vertices:bpy.data.meshes.remove(me);continue
        tree=BVHTree.FromPolygons(vertices,[(i,i+1,i+2) for i in range(0,len(vertices),3)],all_triangles=True)
        records.append({'name':o.name,'kind':o.get('kind','fitting'),'extras':dict(o.items()),'triangles':triangles,'tree':tree})
        bpy.data.meshes.remove(me)
    return records


def connect_deck_routes(ctx,spec):
    """Find connected main-deck corridors around the actual guide fittings."""
    from v2_audit import TriangleScene,capsule_triangle_d2
    records=scene_records([o for o in bpy.context.scene.objects if o.get('asset_role')!='collision'
                           and o.get('asset_role')!='presentation' and not o.hide_render])
    world=TriangleScene(records);kd=ctx['kd'];radius=.42;height=1.85;cos_slope=math.cos(math.radians(35))
    occupancy={};points={};step=.18
    def point(key):
        if key not in points:
            x,s=(key[0]*step,key[1]*step)
            proposed=P(x,s,float(kd.deck_z(s,x)))
            hit=world.support(proposed)
            points[key]=hit[0] if hit else None
        return points[key]
    def free(key):
        if key in occupancy:return occupancy[key]
        x,s=key[0]*step,key[1]*step
        if abs(x)>spec['beam']*.44 or not ctx['K']['POLPOKLAD_S']+.05<s<spec['length']*.34:
            occupancy[key]=False;return False
        foot=point(key)
        if foot is None:occupancy[key]=False;return False
        a=foot+Vector((0,0,radius+.08));b=foot+Vector((0,0,height-radius))
        lo=foot+Vector((-radius,-radius,.06));hi=foot+Vector((radius,radius,height))
        for index in world.candidates(lo,hi):
            mn,mx=world.mins[index],world.maxs[index]
            if any(mx[k]<lo[k] or mn[k]>hi[k] for k in range(3)):continue
            if mx.z<=foot.z+.22:continue
            tri=world.triangles[index];n=world.normals[index]
            if n.z>cos_slope:
                plane=tri[0].z-(n.x*(foot.x-tri[0].x)+n.y*(foot.y-tri[0].y))/n.z
                if abs(plane-foot.z)<.14:continue
            if capsule_triangle_d2(a,b,tri)<radius*radius-1e-8:
                occupancy[key]=False;return False
        occupancy[key]=True;return True
    def nearest(p):
        key=(round(p.x/step),round(-p.y/step))
        for d in range(6):
            candidates=[(key[0]+dx,key[1]+ds) for dx in range(-d,d+1) for ds in range(-d,d+1)
                        if max(abs(dx),abs(ds))==d]
            candidates.sort(key=lambda q:(point(q)-p).length_squared if point(q) is not None else math.inf)
            for q in candidates:
                if free(q):return q
        raise RuntimeError('No standing room near main-deck target '+str(list(p)))
    def path(a,b):
        start=nearest(a);goal=nearest(b)
        queue=[(0,start)];score={start:0};came={}
        while queue:
            _,u=heapq.heappop(queue)
            if u==goal:
                keys=[u]
                while u in came:u=came[u];keys.append(u)
                return [point(k) for k in reversed(keys)]
            for dx,ds in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                v=(u[0]+dx,u[1]+ds)
                if not free(v):continue
                if dx and ds and (not free((u[0]+dx,u[1])) or not free((u[0],u[1]+ds))):continue
                distance=(point(v)-point(u)).length
                cost=score[u]+distance
                if cost<score.get(v,math.inf):
                    came[v]=u;score[v]=cost
                    heuristic=math.hypot(v[0]-goal[0],v[1]-goal[1])*step
                    heapq.heappush(queue,(cost+heuristic,v))
        ctx['_v2_plan_failure']={'start':list(start),'goal':list(goal),
             'cells':[[k[0],k[1],int(v)] for k,v in occupancy.items()],
             'grid_m':step}
        raise RuntimeError('Guide fittings disconnect main-deck destinations '+str(list(a))+' -> '+str(list(b)))
    root=P(-1.5,-2.5,float(kd.deck_z(-2.5,-1.5)))
    root_point=point(nearest(root))
    old=ctx['_v2_routes'];replacement=[]
    desired={r['name']:r for r in old}
    targets=[('main_deck_to_hatch',Vector((desired['hold_ladder']['points'][0][0],
                 -desired['hold_ladder']['points'][0][2],desired['hold_ladder']['points'][0][1]))),
             ('main_deck_to_cabin',Vector((desired['captains_cabin']['points'][0][0],
                 -desired['captains_cabin']['points'][0][2],desired['captains_cabin']['points'][0][1]))),
             ('main_deck_to_quarterdeck',Vector((desired['quarterdeck_access']['points'][0][0],
                 -desired['quarterdeck_access']['points'][0][2],desired['quarterdeck_access']['points'][0][1]))),
             ('main_deck_forward',P(-1.35,spec['length']*.28,float(kd.deck_z(spec['length']*.28,-1.35))))]
    for name,target in targets:
        print('PLANNING',name,list(root_point),list(target),flush=True)
        pp=path(root_point,target)
        # Preserve the authored real landing as the endpoint where within one cell.
        if (pp[-1]-target).length<.30:pp.append(target)
        replacement.append({'name':name,'mode':'walk','points':[gltf(p) for p in pp]})
    ctx['_v2_routes']=replacement+[r for r in old if r['name'] not in ('main_deck_hatch_approach','main_deck_circulation')]
    return {'grid_m':step,'nodes_tested':len(occupancy),'start_gltf':gltf(root_point),
            'method':'A* over actual mesh capsule clearance; independently checked after GLB import'}


def physical_colliders(ctx):
    """Concave hollow shell retains real portals; major fittings use simple solids."""
    N=__import__('narzedzia');kd=ctx['kd']
    col=bpy.data.collections.get('PHYSICS') or bpy.data.collections.new('PHYSICS')
    if col.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(col)
    objects=[]
    def duplicate(o,name,ratio=None):
        dg=bpy.context.evaluated_depsgraph_get()
        me=bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        c=bpy.data.objects.new(name,me);col.objects.link(c);c.matrix_world=o.matrix_world.copy()
        c['asset_role']='collision';c['kind']=o.get('kind','fitting');c['physics']=o.get('physics','solid')
        if o.get('kind')=='ladder':c['climbable']=True
        for key in ('hinge','control'):
            if key in o:c[key]=o[key]
        if ratio:
            dec=c.modifiers.new('collision_simplify','DECIMATE');dec.ratio=ratio
            with bpy.context.temp_override(object=c,active_object=c):bpy.ops.object.modifier_apply(modifier=dec.name)
        c.data.materials.clear();c.hide_render=True;objects.append(c)
        return c
    hull=ctx['obj']['kadlub'];hull.data.calc_loop_triangles()
    duplicate(hull,'col_hollow_hull',min(1,8000/max(1,len(hull.data.loop_triangles))))
    for o in list(bpy.context.scene.objects):
        if o is not hull and o.type=='MESH' and o.get('authored_access') and o.get('physics') in ('solid','walk_surface'):
            duplicate(o,'col_'+o.name.lower())
    # Default steering only; inactive deck-tiller variant is never exported.
    skip=('luk_glowny','main_hatch_open_coaming','schody_rufowe','grodz_drzwi','zejsciowka')
    for ob in ctx.get('przeszkody',[]):
        if ob['nazwa'].startswith(skip) or ob.get('wariant') not in (None,'naped_kolo'):continue
        if ob['h']<.3 or ob['nazwa'].startswith('maszt'):continue
        o=bpy.data.objects.get(ob['nazwa'])
        if o is None or o.hide_render:continue
        if o.name.startswith('nagielbank'):
            c=duplicate(o,'col_'+o.name.lower(),.65);c['physics']='solid'
            continue
        if o.name.startswith('pompa_L'):
            x=ob['x']+1.25
        elif o.name.startswith('pompa_P'):
            x=ob['x']-1.25
        else:x=ob['x']
        qd=ob.get('poziom')=='rufowy'
        z=float(kd.deck_z(ob['s'],x))+(ctx['K']['POLPOKLAD_H'] if qd else 0)
        sk=N.Siatka('col_'+o.name)
        if ob['typ']=='kolo':
            N.cylinder(sk,P(x,ob['s'],z),P(x,ob['s'],z+ob['h']),ob['wym'],ob['wym'],'drewno',sides=10)
        else:
            length,width=ob['wym'];N.box(sk,P(x,ob['s'],z+ob['h']/2),(width,length,ob['h']),'drewno')
        c=N.to_object(sk,col,recalc=True);c.name=c.name.lower();c.data.materials.clear()
        c['asset_role']='collision';c['kind']='fitting';c['physics']='solid';c.hide_render=True;objects.append(c)
    for key,info in ctx['rig']['maszty'].items():
        m=info['m'];sk=N.Siatka('col_mast_'+key)
        N.cylinder(sk,m.p(m.z_heel),m.p(m.z_top),m.sr/2,m.sr*.35,'drewno',sides=10)
        c=N.to_object(sk,col,recalc=True);c.data.materials.clear();c.hide_render=True
        c['asset_role']='collision';c['kind']='spar';c['physics']='solid';objects.append(c)
    for o in objects:
        result=topology(o)
        if result['non_manifold_edges']:raise RuntimeError('Collider not closed: '+o.name+str(result))
    return objects


def night_lanterns(ctx,spec):
    """Seven real housings with explicit engine interaction indices."""
    body=bpy.data.objects.get('latarnia_rufowa')
    glass=bpy.data.objects.get('latarnia_rufowa_szklo')
    if body is None or glass is None:raise RuntimeError('Reference stern lantern missing')
    for o in (body,glass):o['interaction_index']=0;o['light_index']=0
    body['kind']='fitting';body['physics']='none';body['asset_role']='visual'
    glass['kind']='glass';glass['physics']='none';glass['asset_role']='visual'
    glass['topology_reason']='single-pane lantern glazing; intentionally thin and double-sided'
    corners=[body.matrix_world@Vector(v) for v in body.bound_box]
    lo=Vector(tuple(min(v[k] for v in corners) for k in range(3)))
    hi=Vector(tuple(max(v[k] for v in corners) for k in range(3)))
    centre=(lo+hi)/2;half_height=(hi.z-lo.z)/2
    markers=[]
    for index in range(7):
        if index==0:
            target=centre
        else:
            side=1 if index<=3 else -1
            s=[-8.0,-1.5,7.0][(index-1)%3]*spec['length']/28
            z=float(ctx['kd'].Zd(s))+float(ctx['kd'].rail_r(s))+ctx['K']['RELING_GR']
            x=side*(float(ctx['kd'].H(s,z)[0])-.04)
            target=P(x,s,z+.12+half_height)
            delta=target-centre
            for template,suffix in [(body,'housing'),(glass,'glazing')]:
                copy=template.copy();copy.data=template.data.copy()
                copy.name='night_lantern_%d_%s'%(index,suffix)
                ctx['_v2_interiors'].objects.link(copy)
                copy.parent=None;copy.matrix_world=template.matrix_world.copy()
                copy.location+=delta;copy['interaction_index']=index;copy['light_index']=index
            rod(ctx,'night_lantern_%d_support'%index,P(x,s,z),P(x,s,z+.15),.045,'zelazo')
        marker=bpy.data.objects.new('night_lantern_%d'%index,None)
        ctx['_v2_interiors'].objects.link(marker);marker.location=target
        marker['asset_role']='marker';marker['interaction_index']=index
        marker['engine_hook']='setLit/lightUp';marker['default_lit']=False
        markers.append({'name':marker.name,'interaction_index':index,'position_gltf':gltf(target)})
    ctx['_v2_night_lanterns']=markers
    return markers


def save_scene(ctx,spec,out):
    out=Path(out);(out/'model').mkdir(parents=True,exist_ok=True)
    origin=bpy.data.objects.get('asset_origin')
    if origin is None:
        origin=bpy.data.objects.new('asset_origin',None)
        ctx['root'].objects.link(origin)
    origin.location=(0,0,0)
    origin['asset_role']='marker'
    origin['waterline_m']=0.0
    origin['vessel_id']=spec['id']
    for o in bpy.context.scene.objects:
        if o.type=='MESH' and 'asset_role' not in o:
            o['asset_role']='visual'
            o['kind']='rope' if o.name.startswith('lina_') else ('sail' if o.name.startswith(('zagiel','zagle')) else
                       ('spar' if o.name.startswith(('drzewca','reja_','gafel','bukszpryt')) else 'fitting'))
            o['physics']='none'
        if spec['id']=='night-hull' and o.type=='MESH' and o.name.startswith(('zagiel','zagle')):
            # Furled cloth is a closed roll attached to spars, rather than an
            # open deployed membrane. Audit its solids/joints in E1; the sail
            # boundary test applies only to the deployed cloth of sailing rigs.
            o['kind']='fitting';o['cloth_state']='furled'
        if o.type=='MESH' and ('szklo' in o.name or o.get('kind')=='glass'):
            o['kind']='glass';o['physics']='none'
            o['topology_reason']='single-pane glazing; intentionally open double-sided surface'
        if o.get('wariant')=='naped_rumpel':o.hide_render=True;o['asset_role']='presentation'
    # Static mesh nodes carry applied rotation/scale; their geometry and child
    # world transforms stay unchanged. Moving nodes retain their actual axes.
    motion_keys=('motion_axis','range_deg','range_m','os_ruchu','control_type')
    for o in list(bpy.context.scene.objects):
        if o.type!='MESH' or o.get('asset_role') in ('collision','presentation') or any(k in o for k in motion_keys):
            continue
        basis=o.matrix_basis.copy()
        linear=basis.to_3x3().to_4x4()
        if all(abs(linear[i][j]-(1 if i==j else 0))<1e-7 for i in range(4) for j in range(4)):
            continue
        child_worlds={child:child.matrix_world.copy() for child in o.children}
        if o.data.users>1:o.data=o.data.copy()
        o.data.transform(linear)
        o.matrix_basis=Matrix.Translation(basis.translation)
        for child,world in child_worlds.items():child.matrix_world=world
    for im in bpy.data.images:
        if im.source=='FILE' and not im.packed_file:im.pack()
    bpy.ops.wm.save_as_mainfile(filepath=str(out/'model'/'ship.blend'),compress=True)
    nav={'schema':2,'units':'metres','axes':'glTF X across, Y up, Z forward',
         'player':{'radius':.38,'height':1.85,'max_slope_deg':35},'routes':ctx['_v2_routes'],
         'climb_controller_required':True,'source_commit':spec['source_commit']}
    (out/'navigation.json').write_text(json.dumps(nav,indent=2)+'\n',encoding='utf-8')
    ground_stations=[]
    for station in ctx.get('stanowiska',[]):
        if station.get('wariant') not in (None,'naped_kolo'):continue
        x,s,z=station['x'],station['s'],station['z']
        main=float(ctx['kd'].deck_z(s,x));quarter=main+ctx['K']['POLPOKLAD_H']
        if min(abs(z-main),abs(z-quarter))>.30:continue
        ground_stations.append({'name':station['nazwa'],'activity':station['czynnosc'],
             'feet_gltf':[x,z,s],'level':'main' if abs(z-main)<=abs(z-quarter) else 'quarterdeck',
             'variant':station.get('wariant'),'scope':'declared source work position; reachability separately measured'})
    design={'schema':2,'vessel':spec['id'],
            'construction':'Loft kadłuba z tabeli rzędnych, stępka i poszycie z poradnika, proporcje drzewc i pełny takielunek; rzeczywiste wnętrza i przejścia dodane jako rekonstrukcja do gry.',
            'source':ctx['_v2_provenance'],
            'source_files':[{'path':'blender/'+p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                 'reference_commit':'2e6f7e922e95396722376d42f3e2e0a12256029e'}
                 for p in sorted(Path(ctx['_v2_reference_source']).glob('*.py'))],
            'sources':{'guide_repository':'grzegorz2047/OldShipSchematicsAndModel',
                       'chapters':['01','02','03','04','05','06','07','08','09','12','13','14']},
            'interiors':ctx['_v2_interior_design'],
            'rigging':ctx.get('_v2_rigging_report',{'pose':'furled reference',
                 'cloth_audit':'Closed furled cloth rolls are fittings included in E1 solid penetration and reasoned construction joint tests; there are no deployed sail membranes.'}),
            'lanterns':ctx.get('_v2_night_lanterns',[]),
            'capstan':ctx.get('_v2_capstan_state'),
            'geometry_budget':ctx.get('_v2_geometry_budget'),
            'source_ground_stations':ground_stations,
            'aloft_station_scope':'Source mast-top/yardarm workstations require a climbing controller and are outside ground walking scope.',
            'rules':{'mast_main':'(length+breadth)/2','mast_fore':'8/9 main',
                     'hull':'reference table of offsets with monotone PCHIP, chapter 02',
                     'access':'real hollow voids, lowered cabin sole and climbable original-sized hatch'},
            'deviations':['Interior layout and lowered cabin sole are game reconstructions, not surviving period plans.',
                          'The dummy quarterdeck companion is replaced by the real cabin entrance to keep its stair fragments out of the cabin.',
                          'The unarmed prologue vessel uses the reference snow rig circa 1710.' if spec['id']=='night-hull' else 'BRIG is the game identifier; reference historical rig is snow circa 1710.',
                          'A climb controller is required at the hold ladder; no false floor-slope pass is claimed.']}
    design['intended_joints']=[
        {'a':'hold_ladder_*','b':'hold_ladder_*','reason':'rungs and mounting handrails fit into their stringers/posts'},
        {'a':'kadlub','b':'hold_ladder_stringer_*','reason':'ladder feet rest on hold sole and stringers extend through hatch coaming'},
        {'a':'captain_companionway*','b':'captain_companionway*','reason':'planked ramp and its structural handrail posts are joined'},
        {'a':'quarterdeck_companionway*','b':'quarterdeck_companionway*','reason':'companionway planks, stringer slab and rail posts form one structure'},
        {'a':'quarterdeck_closed_gap_*','b':'quarterdeck_closed_gap_*','reason':'new guard balusters are tenoned into the rails closing the obsolete stair opening'},
        {'a':'quarterdeck_closed_gap_*','b':'balustrada_progu','reason':'replacement guard rails join the retained centre posts of the original quarterdeck guard'},
        {'a':'captain_door_jamb_*','b':'captain_door_lintel','reason':'lintel is tenoned into jambs'},
        {'a':'captain_chart_table','b':'chart_table_leg_*','reason':'tabletop rests on legs'},
        {'a':'captain_bunk_frame','b':'captain_bunk_mattress','reason':'mattress rests on bunk frame'},
        {'a':'captain_bunk_frame','b':'captain_bunk_leg_*','reason':'short support legs meet the underside of the bunk frame'},
        {'a':'capstan_bar_rack_post_*','b':'capstan_bar_rack_shelf_*','reason':'tiered rack shelves are housed into their vertical posts'},
        {'a':'freshwater_barrel_hold','b':'freshwater_barrel_hold','reason':'Source iron hoops are fitted around the wooden cask body'},
        {'a':'pokrywa_trzonu','b':'ster','reason':'The stock head cover fits around the upper rudder stock; overlap is under 6 mm'}]
    for index in range(1,7):
        design['intended_joints'].append({'a':f'night_lantern_{index}_support','b':f'night_lantern_{index}_housing',
            'reason':'The lantern base seats 7.5 mm over its supporting iron socket.'})
    # Preserve the guide's documented construction joints as concrete object
    # pairs. Material-limited source exceptions require a separate measurement;
    # the obsolete "unmodelled cabin" exception does not apply to this interior.
    from przenikanie import POLACZENIA
    source_names=[o.name for o in bpy.context.scene.objects if o.type=='MESH' and
                  o.get('asset_role') not in ('collision','presentation')]
    declared=set()
    for a,ma,b,mb,reason in POLACZENIA:
        if ma!='*' or mb!='*' or 'nie jest modelowane' in reason:
            continue
        for name_a in source_names:
            if not fnmatch.fnmatchcase(name_a,a):continue
            for name_b in source_names:
                if not fnmatch.fnmatchcase(name_b,b):continue
                pair=tuple(sorted((name_a,name_b)))
                if pair in declared:continue
                declared.add(pair)
                design['intended_joints'].append({'a':name_a,'b':name_b,'reason':reason,
                    'source':'blender/przenikanie.py:POLACZENIA'})
    # Keep source joint matching above in the guide's original names, then give
    # furled cloth explicit names understood by the shared rig/deck preview.
    cloth_names={}
    for o in bpy.context.scene.objects:
        if o.type=='MESH' and o.get('cloth_state')=='furled' and not o.name.startswith('furled_sail_'):
            old=o.name;o.name='furled_sail_'+old;cloth_names[old]=o.name
    if cloth_names:
        from v2_export import remap
        design=remap(design,cloth_names)
    (out/'design.json').write_text(json.dumps(design,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return nav,design


def main():
    ap=argparse.ArgumentParser();ap.add_argument('spec');ap.add_argument('--out',required=True)
    ap.add_argument('--use-cache',action='store_true');ap.add_argument('--no-rig',action='store_true')
    ap.add_argument('--geometry-only',action='store_true')
    a=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);spec=json.loads(Path(a.spec).read_text(encoding='utf-8'))
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    cache=out/'reference'/'context'
    if a.use_cache and cache.with_suffix('.pickle').exists():ctx=load_context(cache)
    else:
        ctx=build_reference(spec,out/'reference')
        try:save_context(ctx,cache)
        except Exception as error:print('REFERENCE_CACHE_UNAVAILABLE',repr(error),flush=True)
    if spec['id']=='brig' and not a.no_rig:
        from v2_rigging import deploy
        deploy(ctx,spec,out)
    augment_interiors(ctx,spec)
    stow_capstan(ctx)
    if spec['id']=='night-hull':night_lanterns(ctx,spec)
    from v2_big_fittings import relocate_water_supply
    relocate_water_supply(ctx)
    from v2_mesh_finish import finish_scene
    mesh_finish=finish_scene([o for o in bpy.context.scene.objects if o.get('asset_role') not in ('collision','presentation')])
    if spec['id']=='brig':
        from v2_big_budget import simplify
        ctx['_v2_geometry_budget']=simplify([o for o in bpy.context.scene.objects
            if o.type=='MESH' and not o.hide_render and o.get('asset_role') not in ('collision','presentation')])
    colliders=physical_colliders(ctx)
    collider_finish=finish_scene(colliders)
    nav,design=save_scene(ctx,spec,out)
    design['mesh_finish']=mesh_finish
    design['collision_finish']=collider_finish
    design['route_planning']=connect_deck_routes(ctx,spec)
    nav['routes']=ctx['_v2_routes']
    visual=[o for o in bpy.context.scene.objects if o.type in ('MESH','EMPTY') and
            o.get('asset_role') not in ('collision','presentation') and (not o.hide_render or o.type=='EMPTY')]
    if not a.geometry_only:
        from v2_materials import upgrade_scene
        from v2_export import finalize
        design['materials']=upgrade_scene(visual)
        from v2_big_uv import finish_uv
        visual,design['uv_finish']=finish_uv(visual,design)
        finalize(spec,out,visual,colliders,nav,design)
    else:
        (out/'navigation.json').write_text(json.dumps(nav,indent=2)+'\n',encoding='utf-8')
        (out/'design.json').write_text(json.dumps(design,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        for path,objects in [(out/'model/ship.glb',visual),(out/'model/collision.glb',colliders)]:
            bpy.ops.object.select_all(action='DESELECT')
            for o in objects:o.hide_set(False);o.select_set(True)
            bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,
                export_extras=True,export_yup=True,export_apply=True,export_animations=False,export_materials='NONE')
    print('V2_BIG_SCENE_READY',spec['id'],len(colliders),'colliders',flush=True)


if __name__=='__main__':main()
