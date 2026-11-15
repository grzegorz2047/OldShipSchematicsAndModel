"""Guide-derived walkable merchant sloop. Blender 5.2; no add-ons.

blender -b --factory-startup --python-exit-code 1 --python sailertales/common/v2_sloop.py -- sailertales/merchant-sloop/spec.json --out build/final/merchant-sloop
Hull source: original chapter 02 offsets and interpolator. Rig source: chapter 12
and independently authored, intersection-audited sloop asset PR #2.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import bpy
import bmesh
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).resolve().parent))
SOURCE = ROOT/'blender'
if not SOURCE.exists(): SOURCE = ROOT/'upstream'/'blender'
sys.path.insert(0,str(SOURCE))
import parametry as PR
import rzedne
import kadlub

VIS=[]; COL=[]; MARKERS=[]; COUNTS={}; ROPE_PATHS=[];IN_RIG=False
P=lambda x,s,z: Vector((x,-s,z))


def unique(name):
    name=name.lower().replace('-','_').replace('.','_')
    n=COUNTS.get(name,0);COUNTS[name]=n+1
    return name if not n else name+'_'+str(n)


def tag(o,kind='fitting',physics='none'):
    o['asset_role']='visual';o['kind']=kind;o['physics']=physics
    VIS.append(o)
    return o


def uv_project(o,tile=2.0,grain=Vector((0,-1,0))):
    layer=o.data.uv_layers.get('UVMap') or o.data.uv_layers.new(name='UVMap')
    for poly in o.data.polygons:
        n=poly.normal.normalized();u=grain-n*grain.dot(n)
        if u.length<.05:u=Vector((1,0,0))-n*n.x
        if u.length<.05:u=Vector((0,0,1))-n*n.z
        u.normalize();v=n.cross(u).normalized()
        for li in poly.loop_indices:
            q=o.data.vertices[o.data.loops[li].vertex_index].co
            layer.data[li].uv=(q.dot(u)/tile,q.dot(v)/tile)


def mesh(name,verts,faces,mat,parent=None,kind='fitting',physics='none',uv=None):
    me=bpy.data.meshes.new(unique(name)+'_mesh');me.from_pydata(verts,[],faces);me.update()
    bm=bmesh.new();bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=0.000001)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if kind!='sail' and bm.calc_volume(signed=True)<0:bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(me);bm.free()
    o=bpy.data.objects.new(unique(name),me);ASSET.objects.link(o)
    if mat:me.materials.append(mat)
    tag(o,kind,physics)
    uv_project(o,2.4 if kind=='sail' else 2.0)
    if parent:parent_world(o,parent)
    return o


def parent_world(o,parent):
    bpy.context.view_layer.update();world=o.matrix_world.copy();o.parent=parent;o.matrix_world=world


def empty(name,pos=(0,0,0),parent=None,kind=None):
    o=bpy.data.objects.new(unique(name),None);o.location=pos;ASSET.objects.link(o)
    o['asset_role']='marker';o['kind']=kind or 'marker';MARKERS.append(o)
    if parent:parent_world(o,parent)
    return o


def col(o,kind=None):
    bpy.context.view_layer.update();c=o.copy();c.data=o.data.copy();c.parent=None
    c.matrix_world=o.matrix_world.copy();c.name=unique('col_'+o.name)
    PHYS.objects.link(c);c['asset_role']='collision';c['physics']='walk_surface' if (kind or o.get('kind'))=='surface' else 'solid'
    c['kind']=kind or o.get('kind','fitting');c.hide_render=True
    c.data.materials.clear();c.data.materials.append(M['collision']);COL.append(c)
    return c


def box(name,c,size,mat,parent=None,physics=False,kind='fitting'):
    if IN_RIG:size=tuple(v*RIG_SCALE for v in size)
    x,y,z=c;a,b,d=[q/2 for q in size]
    vs=[(x+i*a,y+j*b,z+k*d) for k in(-1,1) for j in(-1,1) for i in(-1,1)]
    fs=[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]
    o=mesh(name,vs,fs,mat,parent,kind,'solid' if physics else 'none')
    longest=max(range(3),key=lambda i:size[i]);grain=Vector((0,0,0));grain[longest]=1
    uv_project(o,2.0,grain)
    if physics:col(o)
    return o


def tube(name,points,d,mat,parent=None,sides=8,kind='fitting',physics=False,scale_rig_d=True):
    if IN_RIG and scale_rig_d:d*=RIG_SCALE
    pts=[Vector(q) for q in points];pts=[p for i,p in enumerate(pts) if not i or (p-pts[i-1]).length>1e-6]
    if len(pts)<2:return None
    vs=[];fs=[];lengths=[0.0]
    for a,b in zip(pts,pts[1:]):lengths.append(lengths[-1]+(b-a).length)
    normal=None
    for i,p in enumerate(pts):
        t=(pts[min(i+1,len(pts)-1)]-pts[max(0,i-1)]).normalized()
        if normal is None:
            normal=t.cross(Vector((0,0,1)))
            if normal.length<.1:normal=t.cross(Vector((1,0,0)))
        else:normal=normal-t*normal.dot(t)
        normal.normalize();other=t.cross(normal).normalized()
        for j in range(sides):
            ang=2*math.pi*j/sides;vs.append(p+d*.5*(normal*math.cos(ang)+other*math.sin(ang)))
    for i in range(len(pts)-1):
        for j in range(sides):
            a=i*sides+j;b=i*sides+(j+1)%sides;fs.append((a,b,b+sides,a+sides))
    fs += [tuple(range(sides-1,-1,-1)),tuple((len(pts)-1)*sides+j for j in range(sides))]
    o=mesh(name,vs,fs,mat,parent,kind,'solid' if physics else 'none')
    if kind=='rope':
        layer=o.data.uv_layers[0]
        # Rope lay is diameter-based, as required by guide chapter 08.
        repeat=6.6*d
        for poly in o.data.polygons:
            for li in poly.loop_indices:
                vi=o.data.loops[li].vertex_index;ringid=vi//sides;j=vi%sides
                layer.data[li].uv=(lengths[min(ringid,len(lengths)-1)]/repeat,j/sides)
    else:
        # Metric projection gives wood/iron the same 1024 px/m in both axes;
        # a normalized circumference previously stretched every narrow tube.
        uv_project(o,2.0,pts[-1]-pts[0])
        o['grain_path_json']=json.dumps({'axes':'object_local','points':[list(q) for q in pts]})
    if physics:col(o)
    return o


def tapered(name,points,diameters,mat,parent=None,sides=12):
    if IN_RIG:diameters=[d*RIG_SCALE for d in diameters]
    if name=='main_mast_timber':
        factor=(1.3*(SPEC['length']+SPEC['beam'])/2/36)/max(diameters)
        diameters=[d*factor for d in diameters]
    kind='spar' if 'timber' in name else 'fitting'
    o=tube(name,points,1,mat,parent,sides,kind,scale_rig_d=False)
    for i,d in enumerate(diameters):
        p=Vector(points[i])
        for v in o.data.vertices[i*sides:(i+1)*sides]:v.co=p+(v.co-p)*d
    uv_project(o,2.0,Vector(points[-1])-Vector(points[0]))
    if name=='main_mast_timber':o['physics']='solid';col(o)
    return o


def ring(name,c,axis,r,thickness,mat,parent=None):
    if IN_RIG:r*=RIG_SCALE;thickness*=RIG_SCALE
    axis=Vector(axis).normalized();u=axis.cross(Vector((0,0,1)))
    if u.length<.1:u=axis.cross(Vector((1,0,0)))
    u.normalize();v=axis.cross(u)
    # Analytic torus closes both parametric directions; a lofted loop's
    # transported start/end frames need not coincide and used to leave seams.
    vs=[];fs=[];n=24;m=6
    for i in range(n):
        t=2*math.pi*i/n;radial=u*math.cos(t)+v*math.sin(t)
        center=Vector(c)+r*radial
        for j in range(m):
            ph=2*math.pi*j/m;vs.append(center+thickness*.5*(radial*math.cos(ph)+axis*math.sin(ph)))
    for i in range(n):
        for j in range(m):fs.append((i*m+j,((i+1)%n)*m+j,((i+1)%n)*m+(j+1)%m,i*m+(j+1)%m))
    return mesh(name,vs,fs,mat,parent)


def rope(name,pts,d=.022,tar=False,parent=None):
    if IN_RIG:d*=RIG_SCALE
    o=tube(name,pts,d,M['rope_tarred' if tar else 'rope_untarred'],parent,6,'rope',scale_rig_d=False)
    if o:ROPE_PATHS.append({'object':o.name,'diameter_m':d,'points_gltf_m':[[q[0],q[2],-q[1]] for q in pts],
                          'edge_attachment':'bolt_rope' in name or 'lacing' in name})
    return o


def pbr(name,texture,color=(1,1,1),tile=2.0,metal=False,double=False):
    m=bpy.data.materials.new(name);m.use_nodes=True;nt=m.node_tree;bs=nt.nodes.get('Principled BSDF')
    for suffix,socket,noncolor in [('kolor','Base Color',False),('normalne','Normal',True),('szorstkosc','Roughness',True)]:
        path=TEXTURES/(texture+'_'+suffix+'.jpg')
        im=bpy.data.images.load(str(path),check_existing=True);im.colorspace_settings.name='Non-Color' if noncolor else 'sRGB'
        tx=nt.nodes.new('ShaderNodeTexImage');tx.image=im
        if suffix=='kolor':
            if color!=(1,1,1):
                # glTF exports the modern colour Mix as texture * baseColorFactor.
                # The legacy MixRGB renders correctly in Blender but loses tint.
                mx=nt.nodes.new('ShaderNodeMix');mx.data_type='RGBA';mx.blend_type='MULTIPLY'
                mx.inputs['Factor'].default_value=1;mx.inputs[7].default_value=(*color,1)
                nt.links.new(tx.outputs['Color'],mx.inputs[6]);nt.links.new(mx.outputs[2],bs.inputs[socket])
            else:nt.links.new(tx.outputs['Color'],bs.inputs[socket])
        elif suffix=='normalne':
            nm=nt.nodes.new('ShaderNodeNormalMap');nt.links.new(tx.outputs['Color'],nm.inputs['Color']);nt.links.new(nm.outputs[0],bs.inputs['Normal'])
        else:
            sp=nt.nodes.new('ShaderNodeSeparateColor');nt.links.new(tx.outputs['Color'],sp.inputs[0]);nt.links.new(sp.outputs['Green'],bs.inputs['Roughness'])
            bs.inputs['Metallic'].default_value=1 if metal else 0
    m.diffuse_color=(*tuple(.45*q for q in color),1);m.use_backface_culling=not double
    m['texture_tile_m']=tile;m['texture_source']='original blender/tekstury.py procedural PBR set'
    return m


def plain(name,color,metal=0,rough=.7):
    m=bpy.data.materials.new(name);m.use_nodes=True;bs=m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=(*color,1);bs.inputs['Roughness'].default_value=rough;bs.inputs['Metallic'].default_value=metal
    return m


class Deck:
    def __init__(self,ps,kd):
        global SX,SS,SZ
        SX=SPEC['beam']/(2*float(np.max(ps.X0[ps.r_deck])))
        SS=SPEC['length']/float(ps.S0[ps.r_deck,-1]-ps.S0[ps.r_deck,0])
        SZ=SPEC['draft']/abs(PR.KADLUB['ZK0'])
        self.ss=ps.S0[ps.r_deck]*SS;self.ww=ps.X0[ps.r_deck]*SX;self.kd=kd
    def width(self,s):return np.interp(s,self.ss,self.ww)
    def heights(self,x,s):
        w=self.width(s);b=SPEC['beam']/2
        return self.kd.Zd(np.asarray(s)/SS)*.95+.016*SPEC['beam']*((w/b)**2-(np.asarray(x)/b)**2)
    def inside(self,s,z):
        zs=z/(SZ if z<0 else .95)
        return max(.08,float(self.kd.H(float(s)/SS,zs)[0])*SX-.12)


def original_hull(coarse=False):
    global DECK
    kd=rzedne.Kadlub(PR.KADLUB,PR.RZEDNE_H,PR.RZEDNE_S,PR.RZEDNE);ps=kadlub.Poszycie(kd,PR.KADLUB)
    if not coarse:DECK=Deck(ps,kd)
    ri=list(range(ps.r_deck+1));ci=list(range(ps.X.shape[1]))
    if coarse:ri=sorted(set([0,*range(0,ps.r_deck,4),ps.r_deck]));ci=sorted(set([0,*range(0,ps.X.shape[1],5),ps.X.shape[1]-1]))
    nr,nc=len(ri),len(ci);vs=[];fs=[];ids={};mats=[]
    for sign in(-1,1):
        for r,rr in enumerate(ri):
            for c,cc in enumerate(ci):
                z=ps.Z[rr,cc];ids[sign,r,c]=len(vs)
                vs.append(P(sign*ps.X[rr,cc]*SX,ps.Ss[rr,cc]*SS,z*(SZ if z<0 else .95)))
        for r in range(nr-1):
            for c in range(nc-1):
                fs.append(tuple(ids[sign,a,b] for a,b in((r,c),(r,c+1),(r+1,c+1),(r+1,c))));mats.append(0 if ps.tags[ri[r]] in('dno','farba_dna') else 2 if ps.tags[ri[r]]=='bergholt' else 1)
    for c in range(nc-1):fs.append((ids[-1,0,c],ids[1,0,c],ids[1,0,c+1],ids[-1,0,c+1]));mats.append(0)
    for c in(0,nc-1):
        for r in range(nr-1):fs.append((ids[-1,r,c],ids[-1,r+1,c],ids[1,r+1,c],ids[1,r,c]));mats.append(1)
    cap={};ntrans=4 if coarse else 12
    for c,cc in enumerate(ci):
        s=ps.S0[ps.r_deck,cc]*SS;w=ps.X0[ps.r_deck,cc]*SX
        for j in range(ntrans+1):
            if j==0:cap[c,j]=ids[-1,nr-1,c]
            elif j==ntrans:cap[c,j]=ids[1,nr-1,c]
            else:
                x=w*(2*j/ntrans-1);cap[c,j]=len(vs);vs.append(P(x,s,float(DECK.heights(x,s))))
    for c in range(nc-1):
        for j in range(ntrans):fs.append((cap[c,j],cap[c+1,j],cap[c+1,j+1],cap[c,j+1]));mats.append(3)
    for c in(0,nc-1):
        old=2*(nr-1)*(nc-1)+(nc-1)+(0 if c==0 else nr-1)+(nr-2)
        fs[old]=tuple([ids[-1,nr-2,c],ids[1,nr-2,c]]+[cap[c,j] for j in range(ntrans,-1,-1)])
    o=mesh('hull_collision_source' if coarse else 'sloop_hull',vs,fs,M['bottom'],kind='hull',physics='solid')
    for mat in [M['wood'],M['dark'],M['deck']]:o.data.materials.append(mat)
    for poly,mi in zip(o.data.polygons,mats):poly.material_index=mi
    return o


def boolean(target,cutter):
    # Interior cut faces use the hull's oak slot, not the underwater white coat.
    cutter.data.materials.clear()
    for mat in target.data.materials:cutter.data.materials.append(mat)
    for poly in cutter.data.polygons:poly.material_index=1 if len(target.data.materials)>1 else 0
    bpy.context.view_layer.objects.active=target;target.select_set(True)
    mod=target.modifiers.new('real_interior_opening','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
    mod.material_mode='INDEX'
    bpy.ops.object.modifier_apply(modifier=mod.name)
    if cutter in VIS:VIS.remove(cutter)
    bpy.data.objects.remove(cutter,do_unlink=True);target.select_set(False)


def shaped_cavity(name,s0,s1,floor,ceiling):
    vs=[];fs=[];rings=[]
    for s in np.linspace(s0,s1,25):
        top=float(DECK.heights(0,s))-.13 if ceiling is None else ceiling
        zs=np.linspace(floor,top,9);r=[]
        for sign,zz in[(-1,zs),(1,zs[::-1])]:
            for z in zz:r.append(len(vs));vs.append(P(sign*min(1.40,DECK.inside(s,z)),s,z))
        rings.append(r)
    n=len(rings[0])
    for a,b in zip(rings,rings[1:]):
        for j in range(n):fs.append((a[j],a[(j+1)%n],b[(j+1)%n],b[j]))
    fs += [tuple(reversed(rings[0])),tuple(rings[-1])]
    return mesh(name,vs,fs,M['wood'])


HOLES=[(-.94,.94,-6.30,-4.15),(-.64,.64,-4.16,-2.45),(-.77,.77,2.65,4.85)]


def carve(target):
    boolean(target,shaped_cavity('hold_void',-2.3,5.5,-1.23,None))
    # Cabin and its exterior stair well are actual openings through the main deck.
    for x0,x1,s0,s1 in HOLES:
        bottom=.24 if s0<0 else -1.3
        cut=box('opening_cutter',P((x0+x1)/2,(s0+s1)/2,(bottom+4)/2),(x1-x0,s1-s0,4-bottom),M['wood'])
        boolean(target,cut)
    uv_project(target)


def hull_and_deck():
    global HULL
    HULL=original_hull();carve(HULL)
    coarse=original_hull(True);carve(coarse);VIS.remove(coarse);coarse.name=unique('col_hull');coarse['asset_role']='collision';coarse.hide_render=True;COL.append(coarse)
    coarse.data.materials.clear();coarse.data.materials.append(M['collision'])
    # Tangent-mapped individual physical boards use original unplanked wood,
    # retaining real .2 m widths and 1024 px/m instead of shrinking plank UVs.
    vs=[];fs=[];a,f=float(DECK.ss[0]),float(DECK.ss[-1]);beam=SPEC['beam']
    for row,x0 in enumerate(np.arange(-beam/2,beam/2,.20)):
        x1=min(beam/2,x0+.192)
        # Physical end joints occur at stock lengths, not at tessellation slices.
        cuts=sorted(set([a,f,*np.arange(a+(row%4)*.8,f,3.2),*[h[2] for h in HOLES],*[h[3] for h in HOLES]]))
        for s0,s1 in zip(cuts,cuts[1:]):
            if s0<a or s1>f or s1-s0<.005:continue
            spans=[(x0,x1)]
            for h0,h1,t0,t1 in HOLES:
                if t0<(s0+s1)/2<t1:
                    spans=[pair for aa,bb in spans for pair in [(aa,min(bb,h0)),(max(aa,h1),bb)] if pair[1]>pair[0]]
            for aa,bb in spans:
                if bb-aa<.01:continue
                samples=np.linspace(s0+.002,s1-.002,max(2,math.ceil((s1-s0)/.22)+1))
                rings=[]
                for s in samples:
                    w=float(DECK.width(s))-.02;xx0=max(aa,-w);xx1=min(bb,w)
                    if xx1-xx0<.008:
                        if len(rings)>1:
                            fs.append(tuple(reversed(rings[0])));fs.append(tuple(rings[-1]));rings=[]
                        elif rings:del vs[-4:];rings=[]
                        continue
                    n=len(vs);ring=[n,n+1,n+2,n+3]
                    vs.extend(P(x,s,float(DECK.heights(x,s))+dz) for x,dz in[(xx0,-.005),(xx1,-.005),(xx1,.025),(xx0,.025)])
                    if rings:
                        prev=rings[-1]
                        for j in range(4):fs.append((prev[j],prev[(j+1)%4],ring[(j+1)%4],ring[j]))
                    rings.append(ring)
                if len(rings)>1:
                    fs.append(tuple(reversed(rings[0])));fs.append(tuple(rings[-1]))
                elif rings:del vs[-4:]
    deck=mesh('individual_deck_boards',vs,fs,M['deck'],kind='surface')
    # Bulwarks, structural frame heads and caprails follow the original deck sheer.
    for side in(-1,1):
        ss=np.linspace(a+.10,f-.10,70);vv=[];ff=[]
        for s in ss:
            w=float(DECK.width(s));d=float(DECK.heights(w,s))
            vv.extend(P(side*x,s,d+h) for x,h in[(w-.11,0),(w+.015,0),(w+.015,.86),(w-.11,.86)])
        for i in range(len(ss)-1):
            for j in range(4):ff.append((i*4+j,i*4+(j+1)%4,(i+1)*4+(j+1)%4,(i+1)*4+j))
        ff.extend([tuple(range(3,-1,-1)),tuple((len(ss)-1)*4+j for j in range(4))])
        o=mesh('merchant_bulwark',vv,ff,M['teal'],physics='solid');col(o)
        pts=[P(side*float(DECK.width(s)),s,float(DECK.heights(DECK.width(s),s))+.90) for s in ss]
        tube('caprail',pts,.13,M['dark'])
        for s in np.arange(a+.5,f-.3,.5):
            x=side*(float(DECK.width(s))-.13);z=float(DECK.heights(x,s))
            box('frame_head',P(x,s,z+.39),(.12,.15,.78),M['wood'])
        for dz in(-.15,-.38):
            pts=[P(side*float(DECK.width(s))+.025*side,s,float(DECK.heights(DECK.width(s),s))+dz) for s in ss]
            tube('wale',pts,.12,M['dark'])
    # Keel and stem use original rabbet profile, not an invented ellipsoid.
    kd=DECK.kd
    tube('keel',[P(0,s*SS,float(kd.zk(s))*SZ-.09) for s in np.linspace(-10.6,9.3,40)],.21,M['dark'],sides=6)
    tube('stem',[P(0,s*SS,z*(SZ if z<0 else .95)) for s,z in PR.KADLUB['DZIOB'] if z<2.4],.23,M['dark'],sides=8)


def sloped(name,x,s0,s1,z0,z1,width):
    vs=[P(x+sx*width/2,s,z+dz) for dz in(-.12,0) for s,z in[(s0,z0),(s1,z1)] for sx in(-1,1)]
    o=mesh(name,vs,[(0,1,3,2),(4,6,7,5),(0,4,5,1),(2,3,7,6),(0,2,6,4),(1,5,7,3)],M['deck'],kind='surface',physics='walk_surface');col(o)
    for k in range(5):
        t=k/4;s=s0+(s1-s0)*t;z=z0+(z1-z0)*t
        # Grooves are embedded in the inclined plank surface.
        tube(name+'_seam',[P(x-width/2,s,z-.006),P(x+width/2,s,z-.006)],.008,M['dark'])
    return o


def cabin_and_hold():
    floor=.30;front=-4.15;back=-6.30;roof=2.56;cw=1.80
    o=box('cabin_sole',P(0,(front+back)/2,floor-.06),(cw+.18,front-back+.10,.12),M['deck'],physics=True,kind='surface')
    # Actual hollow deckhouse: four walls with an absent doorway, never a solid box.
    for side in(-1,1):
        box('cabin_side',P(side*(cw/2+.045),(front+back)/2,(floor+roof)/2),(.09,front-back,roof-floor),M['wood'],physics=True)
        box('cabin_front_jamb',P(side*(cw/4+.29),front,(floor+roof)/2),(cw/2-.58,.10,roof-floor),M['teal'],physics=True)
    box('cabin_rear',P(0,back,(floor+roof)/2),(cw,.10,roof-floor),M['wood'],physics=True)
    box('door_lintel',P(0,front,roof-.075),(1.16,.12,.15),M['dark'],physics=True)
    box('cabin_roof',P(0,(front+back)/2,roof+.06),(cw+.08,front-back+.10,.12),M['teal'],physics=True,kind='surface')
    door=box('captain_door_open',P(-.58,front-.55,floor+1.01),(.07,1.05,2.02),M['dark'],physics=True)
    hinge=empty('hinge_captain_door',P(-.58,front,floor),kind='hinge');hinge['axis']='up';hinge['open_angle_deg']=90
    door['hinge_marker']=hinge.name
    for x in(-.65,.65):
        box('rear_window_frame',P(x,back-.062,1.78),(.55,.04,.62),M['dark'])
        box('rear_window_glass',P(x,back-.086,1.78),(.45,.025,.52),M['glass'])
        box('window_mullion',P(x,back-.102,1.78),(.026,.03,.52),M['ochre'])
    # Period-sized berth lies athwartships at the back, leaving a standing entry.
    box('captain_berth',P(0,back+.48,floor+.26),(1.68,.68,.50),M['wood'],physics=True)
    box('berth_mattress',P(0,back+.48,floor+.55),(1.60,.64,.10),M['canvas'],physics=True)
    box('chart_table',P(.63,-4.95,floor+.72),(.43,.68,.08),M['deck'],physics=True)
    for s in(-4.71,-5.19):tube('table_leg',[P(.63,s,floor),P(.63,s,floor+.68)],.07,M['wood'])
    top_s=-2.45;bottom_s=front-.10
    top_z=float(DECK.heights(0,top_s))+.025
    sloped('cabin_companionway',0,top_s,bottom_s,top_z,floor,1.04)
    # Enclosed hold floor follows the hollow's available width.
    vs=[];fs=[];rings=[]
    for s in np.linspace(-2.20,5.35,30):
        w=min(1.36,DECK.inside(s,-1.18))-.02;n=len(vs)
        vs.extend(P(x,s,z) for x,z in[(-w,-1.29),(w,-1.29),(w,-1.18),(-w,-1.18)])
        ring0=[n,n+1,n+2,n+3]
        if rings:
            prev=rings[-1]
            for j in range(4):fs.append((prev[j],prev[(j+1)%4],ring0[(j+1)%4],ring0[j]))
        rings.append(ring0)
    fs.extend([tuple(reversed(rings[0])),tuple(rings[-1])])
    o=mesh('hold_sole',vs,fs,M['deck'],kind='surface',physics='walk_surface');col(o)
    # Genuine cargo opening: coaming is a frame; its lid is folded to the side.
    for side in(-1,1):
        z=float(DECK.heights(side*.83,3.75))+.10
        box('cargo_hatch_side',P(side*.83,3.75,z),(.12,2.4,.20),M['dark'],physics=True)
    for s in(2.59,4.91):
        box('cargo_hatch_end',P(0,s,float(DECK.heights(0,s))+.10),(1.77,.12,.20),M['dark'],physics=True)
    hatch=box('cargo_hatch_lid_open',P(1.04,3.75,float(DECK.heights(1.04,3.75))+.82),(.08,2.16,1.42),M['deck'],physics=True)
    empty('hinge_cargo_hatch',P(.77,3.75,float(DECK.heights(.77,3.75))),kind='hinge')['open_angle_deg']=90
    ztop=float(DECK.heights(0,2.85))+.025
    for x in(-.47,.47):tube('hold_ladder_stringer',[P(x,3.58,-1.18),P(x,2.85,ztop)],.07,M['wood'],kind='ladder',physics=True)
    for t in np.linspace(0,1,10):
        s=3.58-.73*t;z=-1.18+(ztop+1.18)*t
        tube('hold_ladder_rung',[P(-.46,s,z),P(.46,s,z)],.065,M['wood'],kind='ladder',physics=True)
    for x in(-.47,.47):
        tube('ladder_handhold',[P(x,2.85,ztop),P(x,2.85,ztop+1.10),P(x,2.45,ztop+1.10)],.04,M['iron'],kind='ladder',physics=True)
    for s in(-1.65,5.0):
        x=.45;z=-1.18
        o=tapered('hold_cask',[P(x,s,z+h) for h in(0,.10,.50,.65)],[.36,.46,.46,.36],M['wood']);o['physics']='solid';col(o)
        for h in(.10,.52):ring('cask_hoop',P(x,s,z+h),(0,0,1),.23,.025,M['iron'])
    x=.45;s=1.8;z=-1.18
    box('merchant_chest',P(x,s,z+.23),(.48,.60,.46),M['wood'],physics=True)
    for ds in(-.21,.21):box('chest_strap',P(x,s+ds,z+.24),(.50,.03,.49),M['iron'])


def fittings():
    # Tiller steering, capstan, bitts, pumps and timber-stock anchors: chapter 09.
    stern=float(DECK.ss[0]);s=stern-.14;z=float(DECK.heights(0,stern))+.02
    # Chapter09 tiller/stock outside the stern, supported by actual timber
    # deadwood and gudgeons rather than hiding the rudder inside the hull.
    vs=[]
    for zz in(-1.50,0.0,1.0):
        sf=float(DECK.kd.a_of_z(zz/(SZ if zz<0 else .95)))*SS+.03
        for xx,ss in[(-.12,sf),(.12,sf),(.12,stern+.02),(-.12,stern+.02)]:vs.append(P(xx,ss,zz))
    fs=[]
    for i in range(2):
        for j in range(4):fs.append((4*i+j,4*i+(j+1)%4,4*(i+1)+(j+1)%4,4*(i+1)+j))
    fs.extend([(3,2,1,0),(8,9,10,11)])
    mesh('sternpost_deadwood',vs,fs,M['dark'])
    tube('rudder_stock',[P(0,s,-1.50),P(0,s,z+1.05)],.19,M['wood'],kind='spar',physics=True)
    rudder=box('rudder_blade',P(0,s-.35,-.8),(.16,.78,1.45),M['dark'])
    empty('hinge_rudder',P(0,s,-.4),kind='hinge')['range_deg']=[-35,35]
    tube('tiller',[P(0,s,z+1.05),P(.20,stern+1.0,z+1.05),P(.35,stern+1.8,z+1.0)],.11,M['wood'],kind='spar')
    for zz in(-.95,-.1):
        tube('rudder_pintle',[P(-.16,stern+.04,zz),P(-.16,s,zz),P(.16,s,zz),P(.16,stern+.04,zz)],.06,M['iron'])
    cap_s=6.0;z=float(DECK.heights(0,cap_s))
    cap=tapered('capstan',[P(0,cap_s,z+h) for h in(0,.13,.6,.78)],[.60,.42,.33,.65],M['wood']);cap['physics']='solid';col(cap)
    # Removable bars are stowed in a proper rack; operating them is an engine state.
    # Keeping a deployed eight-bar circle here would block the ladder's landing.
    for k in range(8):
        x=float(DECK.width(6.85))-.40+(k%2)*.065
        h=float(DECK.heights(x,6.2))+.16+(k//2)*.06
        tube('capstan_bar_stowed',[P(x,5.65,h),P(x,6.85,h)],.05,M['wood'])
    for s in(5.82,6.68):
        x=float(DECK.width(6.85))-.36
        box('bar_rack',P(x,s,float(DECK.heights(x,s))+.10),(.24,.09,.18),M['dark'])
    for side in(-1,1):
        s=6.9;x=side*.65;z=float(DECK.heights(x,s))
        box('bow_bitt',P(x,s,z+.4),(.18,.18,.8),M['dark'],physics=True)
        tube('bitt_crosspiece',[P(x-.25,s,z+.64),P(x+.25,s,z+.64)],.11,M['wood'])
        # Anchor stocks remain outside the walking corridor; tied to real bitts.
        x=side*(float(DECK.width(6.4))+.62);z=float(DECK.heights(0,6.4))-.1
        tube('anchor_shank',[P(x,6.4,z),P(x,6.4,z-1.05)],.075,M['iron'])
        tube('anchor_stock',[P(x-.38,6.4,z-.16),P(x+.38,6.4,z-.16)],.13,M['wood'])
        tube('anchor_arms',[P(x-.38,6.4,z-.80),P(x,6.4,z-1.05),P(x+.38,6.4,z-.80)],.075,M['iron'])
        rope('anchor_cable',[P(x,6.4,z+.1),P(side*.65,6.9,float(DECK.heights(side*.65,6.9))+.55)],.055,True)
    x=.80;s=-1.4;z=float(DECK.heights(x,s))
    o=tapered('elm_pump',[P(x,s,z),P(x,s,z+.8)],[.25,.21],M['wood']);o['physics']='solid';col(o)
    tube('pump_handle',[P(x,s,z+.65),P(x-.4,s,z+.9)],.06,M['iron'])
    # Merchant cargo is stowed below. The narrow working deck stays clear.


def navigation():
    routes=[]
    def walk(name,points):routes.append({'name':name,'mode':'walk','points':[[x,float(DECK.heights(x,s))+.025,s] for x,s in points]})
    walk('main_deck_starboard',[(-1.45,-3.0),(-1.45,-.3),(-1.45,1.0),(-.7,1.85),(-1.45,2.3),(-1.45,5.25),(-.85,5.3)])
    walk('main_deck_port',[(1.45,-3.0),(1.45,-.2),(1.45,1.8),(1.45,1.9)])
    walk('working_deck_crossing',[(-1.45,-2.0),(0,-2.0),(1.45,-2.0)])
    walk('foredeck_crossing',[(-1.45,1.9),(0,2.0),(1.45,1.9)])
    walk('aft_helm_access',[(-1.45,-3.0),(-1.47,-4.3),(-1.47,-5.8),(-1.47,-6.2),(-1.35,-6.75),(-.55,-7.3)])
    # Direct approach to the lowered cabin entrance avoids the helm and stays.
    top=float(DECK.heights(0,-2.45))+.025
    routes.append({'name':'captains_cabin','mode':'walk','points':[[0,float(DECK.heights(0,-2.0))+.025,-2.0],[0,top,-2.25],[0,top,-2.45],[0,.30,-4.25],[0,.30,-4.65],[0,.30,-5.0]]})
    walk('hatch_approach',[(1.45,1.9),(0,2.0)])
    top=float(DECK.heights(0,2.85))+.025
    routes.append({'name':'hold_ladder','mode':'climb','points':[[0,float(DECK.heights(0,2.0))+.025,2.0],[0,top+.25,2.59],[0,top,3.15],[0,-1.18,3.88]],'requires':'ladder_controller','handhold_offset_m':.30})
    routes.append({'name':'hold_aisle','mode':'walk','points':[[0,-1.18,3.88],[-.94,-1.18,3.88],[-.94,-1.18,1.3],[-.94,-1.18,-.1],[-.94,-1.18,-1.7]]})
    empty('asset_origin',P(0,0,0),kind='origin')
    empty('bow_direction',P(0,1,0),kind='axis_marker')
    empty('station_helm',P(-.55,-7.3,float(DECK.heights(-.55,-7.3))+.025),kind='station')
    empty('station_captain',P(0,-5.0,.3),kind='station')
    empty('station_hold',P(-.94,-1.2,-1.18),kind='station')
    return {'schema':2,'units':'metres','axes':'glTF X port Y up Z bow',
            'player':{'radius':.38,'height':1.85,'max_slope_deg':35},'routes':routes,
            'source_commit':SPEC['source_commit'],'climb_controller_required':True}


def export(path,objects):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.hide_set(False);o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_extras=True,export_yup=True,
                              export_animations=False,export_materials='EXPORT',export_image_format='AUTO')


def lod(level):
    copies=[]
    for o in VIS:
        if o.type!='MESH':continue
        if level==2 and (o.get('kind')=='rope' or any(w in o.name for w in('hoop','mullion','band','lacing','ratline','seam','frame_head'))):continue
        c=o.copy();c.data=o.data.copy();c.name=unique('lod%d_'%level+o.name);c.data.name=c.name+'_mesh';c.parent=None;c.matrix_world=o.matrix_world.copy();ASSET.objects.link(c);copies.append(c)
        if len(c.data.polygons)>40 and c.get('kind')!='sail':
            mod=c.modifiers.new('distance_simplification','DECIMATE');mod.ratio=.48 if level==1 else .20
            bpy.context.view_layer.objects.active=c
            try:bpy.ops.object.modifier_apply(modifier=mod.name)
            except RuntimeError:pass
    export(OUT/'model'/('ship_lod%d.glb'%level),copies)
    for c in copies:bpy.data.objects.remove(c,do_unlink=True)


def previews():
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=24
    scene.render.resolution_x=1200;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    if scene.world is None:scene.world=bpy.data.worlds.new('sloop_world')
    scene.world.color=(.25,.25,.25);scene.view_settings.view_transform='AgX'
    for pos,energy,size in[((15,-10,24),13000,15),((-12,10,13),9000,12)]:
        bpy.ops.object.light_add(type='AREA',location=pos);light=bpy.context.object;light['asset_role']='presentation';light.data.energy=energy;light.data.size=size
        light.rotation_euler=(Vector((0,0,5))-light.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add();cam=bpy.context.object;cam['asset_role']='presentation';cam.data.type='ORTHO';scene.camera=cam
    scene.render.image_settings.file_format='JPEG';scene.render.image_settings.quality=90
    def shot(name,pos,target,scale):
        cam.location=pos;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
        scene.render.filepath=str(OUT/'previews'/name);bpy.ops.render.render(write_still=True)
    shot('hero.jpg',(22,26,16),(0,-1.0,6),30)
    hidden=[]
    for o in VIS:
        if o.get('kind') in('sail','rope','spar') or o.name.startswith(('cabin_roof','caprail','merchant_bulwark','main_luff_hoop','mast_iron_band','gaff_jaws','deadeye','chainplate')):
            o.hide_render=True;hidden.append(o)
    shot('deck.jpg',(13,18,23),(0,0,.5),23)
    shot('cabin.jpg',(6,9,8),(0,5.5,.9),7.5)
    for o in hidden:o.hide_render=False


def main():
    global SPEC,OUT,TEXTURES,ASSET,PHYS,M,G,RIG_SCALE,DECK,IN_RIG
    ap=argparse.ArgumentParser();ap.add_argument('spec');ap.add_argument('--out',required=True);ap.add_argument('--no-render',action='store_true')
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);SPEC=json.loads(Path(args.spec).read_text(encoding='utf-8'));OUT=Path(args.out).resolve()
    for p in(OUT/'model',OUT/'previews'):p.mkdir(parents=True,exist_ok=True)
    (OUT/'spec.json').write_bytes(Path(args.spec).read_bytes())
    TEXTURES=ROOT/'build'/'guide-brig'/'tekstury'
    if not (TEXTURES/'drewno_kolor.jpg').exists():raise RuntimeError('Run guide texture bootstrap first; expected '+str(TEXTURES))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ASSET=bpy.data.collections.new('sloop_visual');bpy.context.scene.collection.children.link(ASSET)
    PHYS=bpy.data.collections.new('physics');bpy.context.scene.collection.children.link(PHYS);PHYS.hide_render=True
    M={'wood':pbr('oiled_oak','drewno'),'dark':pbr('tarred_timber','drewno',(.12,.095,.07)),
       'deck':pbr('pine_deck_boards','drewno'),
       'teal':pbr('merchant_teal_paint','drewno',(.08,.35,.34)),
       'bottom':pbr('white_stuff','drewno'),
       'iron':pbr('forged_iron','zelazo',metal=True),'ochre':pbr('yellow_ochre','drewno',(.90,.65,.18)),
       'canvas':pbr('linen_canvas','plotno',tile=2.4,double=True),
       'glass':plain('cabin_glass',(.035,.12,.13),0,.18),'collision':plain('collision',(.1,.4,.1)),
       'rope_tarred':pbr('rope_tarred','lina',(.18,.15,.11)),'rope_untarred':pbr('rope_untarred','lina')}
    M.update(wood_dark=M['dark'],wood_black=M['dark'])
    # A white protective coat covers the wood albedo while retaining its grain
    # normal and roughness; all glTF colour factors remain within [0,1].
    bs=M['bottom'].node_tree.nodes.get('Principled BSDF')
    for link in list(bs.inputs['Base Color'].links):M['bottom'].node_tree.links.remove(link)
    bs.inputs['Base Color'].default_value=(.72,.69,.60,1)
    G=SimpleNamespace(canvas_material=lambda *args:M['canvas'],animate_sail=lambda *args:None)
    hull_and_deck();cabin_and_hold();fittings()
    actual=DECK;RIG_SCALE=(1.3*(SPEC['length']+SPEC['beam'])/2)/17.84
    class RigDeck:
        def width(self,s):return actual.width(.05*SPEC['length']+(s-1.05)*RIG_SCALE)/RIG_SCALE
        def heights(self,x,s):
            z=actual.heights(x*RIG_SCALE,.05*SPEC['length']+(s-1.05)*RIG_SCALE)
            return (z-ZSHIFT)/RIG_SCALE
    global ZSHIFT
    ZSHIFT=(-SPEC['draft']+.45)-(-1.84*RIG_SCALE)
    DECK=RigDeck();IN_RIG=True;rig();IN_RIG=False;DECK=actual
    sails={o.name.split('_set')[0]:o for o in VIS if o.get('kind')=='sail'}
    for o in VIS:
        if o.get('kind')!='rope':continue
        prefix=o.name.split('_bolt_rope')[0] if '_bolt_rope' in o.name else None
        if o.name.startswith(('main_head_lacing','main_foot_lacing')):prefix='gaff_main'
        if o.name.startswith('inner_sheet'):prefix='inner_staysail'
        if o.name.startswith('jib_sheet'):prefix='outer_jib'
        if prefix in sails:o['attachment_sail']=sails[prefix].name;o['edge_attachment']=True
    for o in MARKERS:
        if o.name.startswith('main_mast'):o['length_m']=1.3*(SPEC['length']+SPEC['beam'])/2
    bpy.context.view_layer.update()
    nav=navigation();(OUT/'navigation.json').write_text(json.dumps(nav,indent=2)+'\n')
    # Whole source frame retained in authoring blend; physics are hidden for rendering.
    for im in bpy.data.images:
        if im.source=='FILE' and not im.packed_file:im.pack()
    for o in COL:o.hide_set(True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'model'/'ship.blend'),compress=True)
    export(OUT/'model'/'ship.glb',VIS+MARKERS);export(OUT/'model'/'collision.glb',COL)
    for o in COL:o.hide_set(True)
    lod(1);lod(2)
    from v2_integrity import inspect_glb
    triangles={name:inspect_glb(OUT/'model'/filename)[0]['triangles'] for name,filename in [('lod0','ship.glb'),('lod1','ship_lod1.glb'),('lod2','ship_lod2.glb'),('collision','collision.glb')]}
    design={'schema':2,'id':SPEC['id'],'triangles':triangles,'type':'single_masted_merchant_sloop','period':'illustrative circa 1715',
            'reference_repository':'https://github.com/grzegorz2047/OldShipSchematicsAndModel',
            'chapters':['01-ship-type-and-era','02-hull-lines-and-offsets','03-hull-construction','04-decks-bulwarks-stern-head','05-masts-and-spars','06-standing-rigging','07-running-rigging-and-belaying','08-ropes-blocks-and-sails','09-deck-machinery','12-designing-other-ships','13-3d-quality-checklist','14-using-the-model-in-a-game'],
            'hull_method':'original rzedne.Kadlub PCHIP and kadlub.Poszycie offset family; independent L/B/draft profile; closed hollow shell with actual openings',
            'dimensions_m':{'deck_length':SPEC['length'],'beam':SPEC['beam'],'rabbet_draft':SPEC['draft']},
            'rules':{'main_mast':'1.3*(L+B)/2, chapter12 revised single-mast sloop','main_mast_length_m':1.3*(SPEC['length']+SPEC['beam'])/2,
                     'mast_diameter_rule':'lower mast length/36','guide_boom_length_m':2/3*(1.3*(SPEC['length']+SPEC['beam'])/2),
                     'guide_gaff_length_m':.6*(2/3*(1.3*(SPEC['length']+SPEC['beam'])/2)),
                     'deck_board_width_m':.20,'deck_stock_length_m':3.2,'wood_texture_repeat_m':2.0,'nominal_wood_texels_per_m':1024},
            'sails':3,'rig_source':'audited PR2 authored static rig, reconstructed around recalculated new mast and target hull; not a scaled finished model',
            'deviations':['The game used a .6-scaled brig; replaced with actual single-mast sloop profile.',
                          'Original reference does not supply interiors: lowered cabin sole .30m and hold sole -1.18m are gameplay inferences.',
                          'The legacy deck/sole scalar fields in spec.json preserve the game profile; the authored deck follows the guide offset sheer and the exact delivered floors are recorded in navigation.json.',
                          'Deckhouse clear width is 1.80m; berth and table are resized independently to retain a verified 0.80m exterior crew corridor.',
                          'Hold ladder requires climb controller, rather than pretending a steep historical ladder is a walkable35deg ramp.',
                          'Authored boom/gaff are shortened approximately4%/2% from the tabulated maximum to keep the working pose over the hull.',
                          'Static authored sailing pose only; arbitrary spar trimming requires rerouted runtime ropes.',
                          'Original source procedural PBR set is used, not the optional photographic CC0 set.'],
            'intended_joints':[
                {'a': 'shroud_channel*', 'b': 'deadeye*', 'reason': 'Deadeyes seat in the outboard shroud channel, secured by their chainplates.'},
                {'a': 'shroud_channel*', 'b': 'merchant_bulwark*', 'reason': 'The timber channel is fastened against the outer bulwark.'},
                {'a': 'shroud_channel*', 'b': 'frame_head*', 'reason': 'Channel ends house into the bulwark frame supports.'},
                {'a': 'merchant_bulwark*', 'b': 'sloop_hull*', 'reason': 'Bulwark heels are housed into the continuous hull/deck edge.'},
                {'a': 'cabin_*', 'b': 'sloop_hull*', 'reason': 'Deckhouse wall heels and companionway landing are housed into the edge of the real cabin opening.'},
                {'a': 'cargo_hatch_side*', 'b': 'sloop_hull*', 'reason': 'Hatch coaming heels are housed into the deck aperture sides.'},
                {'a': 'bow_bitt*', 'b': 'sloop_hull*', 'reason': 'Bitts are stepped through the deck into the hull framing.'},
                {'a': 'capstan*', 'b': 'sloop_hull*', 'reason': 'Capstan spindle is stepped through the supporting deck cap.'},
                {'a': 'merchant_bulwark*', 'b': 'individual_deck_boards*', 'reason': 'Deck-board ends are trapped beneath the bulwark heel.'},
                {'a': 'frame_head*', 'b': 'individual_deck_boards*', 'reason': 'Frame heads pass through the deck edge to support the caprail.'},
                {'a': 'cabin_*', 'b': 'individual_deck_boards*', 'reason': 'Deckhouse walls are housed through the planked opening perimeter.'},
                {'a': 'cargo_hatch_*', 'b': 'individual_deck_boards*', 'reason': 'Hatch coamings and open lid hinge bear on the planked aperture perimeter.'},
                {'a': 'bow_bitt*', 'b': 'individual_deck_boards*', 'reason': 'Bitts are through-deck timbers.'},
                {'a': 'capstan*', 'b': 'individual_deck_boards*', 'reason': 'Capstan heel passes through its deck bearing.'},
                {'a': 'main_mast_timber*', 'b': 'individual_deck_boards*', 'reason': 'Mast passes through its planked deck partners.'},
                {'a': 'stem*', 'b': 'individual_deck_boards*', 'reason': 'Stem head meets the end of the foredeck planking.'},
                {'a': 'elm_pump*', 'b': 'individual_deck_boards*', 'reason': 'Pump barrel passes through the deck to the bilge.'},
                {'a': 'bar_rack*', 'b': 'individual_deck_boards*', 'reason': 'Stowage racks are fixed into the planking beside the bulwark.'},
                {'a': 'hold_ladder_stringer*', 'b': 'hold_sole*', 'reason': 'Ladder stringer feet are housed into the hold floor.'},
                {'a': 'hold_ladder_rung*', 'b': 'hold_sole*', 'reason': 'Lowest ladder rung sits against the floor at the ladder foot.'},
                {'a': 'rear_window_frame*', 'b': 'rear_window_glass*', 'reason': 'Glazing is retained within the timber window rebate.'},
                {'a': 'cargo_hatch_end*', 'b': 'cargo_hatch_side*', 'reason': 'Hatch coaming corners use housed joints.'},
                {'a': 'hold_ladder_rung*', 'b': 'ladder_handhold*', 'reason': 'The upper rung meets the grab rail at the ladder head.'},
                {'a': 'bowsprit_timber*', 'b': 'jibboom_timber*', 'reason': 'Jibboom heel laps the bowsprit head in its fitted saddle.'},
                {'a': 'elm_pump*', 'b': 'pump_handle*', 'reason': 'Pump handle is pivoted in the barrel head.'},
                {'a': 'bar_rack*', 'b': 'frame_head*', 'reason': 'Rack ends are mounted to the adjacent bulwark frame.'},

                {'a':'keel*','b':'sloop_hull*','reason':'Chapter03 keel rabbet is a structural planking joint.'},
                {'a':'stem*','b':'sloop_hull*','reason':'Chapter03 stem rabbet receives the bow planking.'},
                {'a':'sternpost_deadwood*','b':'sloop_hull*','reason':'Aft deadwood and sternpost are structural timbers joined to the hull.'},
                {'a':'rudder_pintle*','b':'sternpost_deadwood*','reason':'Gudgeon fittings fasten the rudder hinge to the sternpost.'},
                {'a':'wale*','b':'sloop_hull*','reason':'Chapter03 external wales are fastened against the hull planking.'},
                {'a':'individual_deck_boards*','b':'sloop_hull*','reason':'Chapter04 deck planks sit on the supporting deck cap.'},
                {'a':'cabin_sole*','b':'sloop_hull*','reason':'Cabin floor slab is supported by the intentionally inset inner floor.'},
                {'a':'hold_sole*','b':'sloop_hull*','reason':'Hold floor planks overlap the supporting inner floor to eliminate cracks.'},
                {'a':'cabin_*','b':'cabin_*','reason':'Deckhouse wall posts, floor and roof meet in structural timber joints.'},
                {'a':'door_lintel*','b':'cabin_*','reason':'Door lintel is supported by the front jambs and deckhouse roof.'},
                {'a':'captain_door_open*','b':'cabin_front_jamb*','reason':'Open leaf is mounted at the marked jamb hinge.'},
                {'a':'rear_window*','b':'cabin_rear*','reason':'Glazing and window frames are mounted against the rear bulkhead.'},
                {'a':'window_mullion*','b':'rear_window*','reason':'Mullion joins the window frame around the glass.'},
                {'a':'captain_berth*','b':'berth_mattress*','reason':'Mattress is supported by the berth frame.'},
                {'a':'captain_berth*','b':'cabin_sole*','reason':'Built-in berth frame bears on the floor slab.'},
                {'a':'chart_table*','b':'table_leg*','reason':'Table legs terminate inside the table top.'},
                {'a':'frame_head*','b':'merchant_bulwark*','reason':'Frame heads are fixed to the inner face of the bulwark.'},
                {'a':'frame_head*','b':'sloop_hull*','reason':'Frame heels are housed into the side planking.'},
                {'a':'caprail*','b':'merchant_bulwark*','reason':'Caprail covers and joins the upper edge of the bulwark.'},
                {'a':'main_mast_timber*','b':'sloop_hull*','reason':'Mast passes through deck partners and is stepped near the keelson.'},
                {'a':'mast_iron_band*','b':'main_mast_timber*','reason':'Wrought-iron reinforcing bands are fitted tightly around the mast.'},
                {'a':'gaff_jaws*','b':'gaff_timber*','reason':'Gaff jaws are fastened to the heel of the gaff.'},
                {'a':'cask_hoop*','b':'hold_cask*','reason':'Iron hoops compress the cask staves.'},
                {'a':'merchant_chest*','b':'chest_strap*','reason':'Iron reinforcing straps are fitted over the timber chest.'},
                {'a':'capstan_bar_stowed*','b':'bar_rack*','reason':'Removable capstan bars rest in their stowage rack.'},
                {'a':'bitt_crosspiece*','b':'bow_bitt*','reason':'Bow bitts have mortised crosspieces.'},
                {'a':'anchor_shank*','b':'anchor_*','reason':'Anchor stock and forged arms are structurally fitted to the shank.'},
                {'a':'rudder_stock*','b':'rudder_blade*','reason':'Rudder blade is joined to its stock.'},
                {'a':'rudder_pintle*','b':'rudder_*','reason':'Pintles fasten the rudder assembly to its hinge axis.'},
                {'a':'tiller*','b':'rudder_stock*','reason':'Tiller heel is socketed over the rudder stock.'},
                {'a':'hold_ladder_rung*','b':'hold_ladder_stringer*','reason':'Ladder rungs are mortised between the stringers.'},
                {'a':'ladder_handhold*','b':'hold_ladder_stringer*','reason':'Grab rails are fastened to the top of the ladder stringers.'}
            ],
            'basis':'Chapter02 original offset interpolator; chapter12 revised single-mast sloop parameter chain; chapter09 merchant fittings; independently inferred player interiors.',
            'sources':[{'repository':'https://github.com/grzegorz2047/OldShipSchematicsAndModel','ref':'2e6f7e922e95396722376d42f3e2e0a12256029e','paths':['blender/parametry.py','blender/rzedne.py','blender/kadlub.py','docs/en/12-designing-other-ships.md']},
                       {'repository':'https://github.com/grzegorz2047/OldShipSchematicsAndModel','ref':'codex/sloop-1715-game-asset','path':'sloop_asset/build_sloop.py','usage':'audited authored cloth topology and working-rig ratios'}],
            'source_files':{'blender/'+p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.glob('*.py')},
            'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/'design.json').write_text(json.dumps(design,indent=2)+'\n')
    (OUT/'rigging_paths.json').write_text(json.dumps({'paths':ROPE_PATHS,'authored_pose_only':True},indent=2)+'\n')
    if not args.no_render:previews()
    print('V2_SLOOP_COMPLETE',OUT,flush=True)


def RP(x,s,z):
    return P(x*RIG_SCALE,.05*SPEC['length']+(s-1.05)*RIG_SCALE,z*RIG_SCALE+ZSHIFT)


# The three sail surfaces and working rig below retain the audited PR2 topology.
# Every authored point is evaluated again in the new chapter12 mast frame.
def sail_quad(name, corners, boom):
    A, B, C, D = map(Vector, corners)
    N = 24
    vs = []
    uv = []
    weights = []

    def pt(u, v):
        low = A.lerp(D, v)
        low.z += 0.27 * RIG_SCALE * math.sin(math.pi * v)
        high = B.lerp(C, v)
        p = low.lerp(high, u)
        w = math.sin(math.pi * u) * math.sin(math.pi * v)
        p.x += 0.43 * RIG_SCALE * w
        return p, w

    for i in range(N + 1):
        for j in range(N + 1):
            p, w = pt(i / N, j / N)
            vs.append(p)
            weights.append(w)
            uv.append((j / N, i / N))
    fs = [
        (
            i * (N + 1) + j,
            i * (N + 1) + j + 1,
            (i + 1) * (N + 1) + j + 1,
            (i + 1) * (N + 1) + j,
        )
        for i in range(N)
        for j in range(N)
    ]
    mat = G.canvas_material(name, 11, 11, (2, 3))
    o = mesh(name + "_set", vs, fs, mat, parent=boom, kind="sail")
    G.animate_sail(o, weights)
    edgepaths = [
        [pt(0, v)[0] for v in np.linspace(0, 1, N + 1)],
        [pt(1, v)[0] for v in np.linspace(0, 1, N + 1)],
        [pt(u, 0)[0] for u in np.linspace(0, 1, N + 1)],
        [pt(u, 1)[0] for u in np.linspace(0, 1, N + 1)],
    ]
    for i, pts in enumerate(edgepaths):
        rope(name + "_bolt_rope_" + str(i), pts, 0.022, parent=boom)
    return o


def sail_tri(name, corners, parent):
    A, B, C = map(Vector, corners)
    N = 24
    vs = []
    uv = []
    weights = []
    ids = {}
    for i in range(N + 1):
        for j in range(N + 1 - i):
            u = i / N
            v = j / N
            w = 27 * u * v * (1 - u - v)
            p = A * (1 - u - v) + B * u + C * v
            p.x += 0.26 * RIG_SCALE * w
            ids[i, j] = len(vs)
            vs.append(p)
            uv.append((u, v))
            weights.append(w)
    fs = []
    for i in range(N):
        for j in range(N - i):
            fs.append((ids[i, j], ids[i + 1, j], ids[i, j + 1]))
            if j < N - i - 1:
                fs.append((ids[i + 1, j], ids[i + 1, j + 1], ids[i, j + 1]))
    mat = G.canvas_material(name, 10, 11, ())
    o = mesh(name + "_set", vs, fs, mat, parent=parent, kind="sail")
    G.animate_sail(o, weights)
    for i, (a, b) in enumerate(((A, B), (B, C), (C, A))):
        rope(name + "_bolt_rope_" + str(i), [a, b], 0.018, parent=parent)
    return o



def rig():
    mast = empty("main_mast", RP(0, 1.05, -1.84), kind="fixed_mast")
    mast["length_m"] = 17.84
    tapered(
        "main_mast_timber",
        [RP(0, 1.05, z) for z in (-1.84, 1.0, 10.0, 13.5, 16.0)],
        [0.44, 0.496, 0.34, 0.28, 0.20],
        M["wood"],
        mast,
    )
    for z in (1.4, 3.0, 10.0, 13.5):
        ring(
            "mast_iron_band",
            RP(0, 1.05, z),
            (0, 0, 1),
            0.247 if z < 4 else 0.17,
            0.035,
            M["iron"],
            mast,
        )
    boom = empty("main_boom", RP(0.18, 0.83, 3.7), kind="rotate_local_z")
    boom["range_deg"] = [-35, 35]
    boom["default_pose_only_collision_checked"] = True
    tapered(
        "boom_timber",
        [RP(0.18, 0.83, 3.7), RP(1.65, -10.5, 3.8)],
        [0.25, 0.14],
        M["wood"],
        boom,
    )
    gaff = empty("main_gaff", RP(0.10, 0.8, 11.12), mast, "hoist_and_rotate")
    gaff["angle_deg"] = 38
    tapered(
        "gaff_timber",
        [RP(0.10, 0.8, 11.12), RP(0.84, -4.63, 15.51)],
        [0.22, 0.13],
        M["wood"],
        gaff,
    )
    ring("gaff_jaws", RP(0, 1.05, 11.12), (0, 0, 1), 0.3, 0.08, M["wood_dark"], gaff)
    sail_quad(
        "gaff_main",
        [
            RP(0.22, 0.8, 3.95),
            RP(0.22, 0.8, 11.0),
            RP(0.96, -4.63, 15.4),
            RP(1.63, -10.0, 4.0),
        ],
        boom,
    )
    for z in np.linspace(4, 10.9, 8):
        ring(
            "main_luff_hoop",
            RP(0, 1.05, z),
            (0, 0, 1),
            0.335,
            0.025,
            M["wood_dark"],
            mast,
        )
    # Lacing sections sit along the head/foot edge, not through the canvas.
    for j, v in enumerate(np.linspace(0.06, 0.94, 12)):
        head = RP(0.22, 0.8, 11.0).lerp(RP(0.96, -4.63, 15.4), v)
        spar = RP(0.10, 0.8, 11.12).lerp(RP(0.84, -4.63, 15.51), v)
        rope("main_head_lacing_" + str(j), [head, spar], 0.012, parent=gaff)
        foot = RP(0.22, 0.8, 3.95).lerp(RP(1.63, -10, 4), v)
        foot.z += 0.27 * RIG_SCALE * math.sin(math.pi * v)
        rope(
            "main_foot_lacing_" + str(j),
            [foot, RP(0.18, 0.83, 3.7).lerp(RP(1.65, -10.5, 3.8), v)],
            0.012,
            parent=boom,
        )
    bowsprit = empty("bowsprit", RP(0, 5, 1.5), kind="fixed_spar")
    tapered(
        "bowsprit_timber",
        [RP(0, 5, 1.5), RP(0, 14.275, 6.85)],
        [0.35, 0.19],
        M["wood"],
        bowsprit,
    )
    tapered(
        "jibboom_timber",
        [RP(0, 11.5, 5.25), RP(0, 18.12, 9.08)],
        [0.19, 0.09],
        M["wood"],
        bowsprit,
    )
    # Stays occupy the windward face; sail clews and their sheets are to port.
    inner = [RP(0.12, 1.15, 11.5), RP(0.12, 13.5, 6.4), RP(1.3, 5.1, 3.5)]
    outer = [RP(0.14, 1.1, 15.6), RP(0.14, 17.5, 8.8), RP(2.8, 12.5, 4.8)]
    sail_tri("inner_staysail", inner, mast)
    sail_tri("outer_jib", outer, mast)
    for name, cs in (("inner_stay", inner), ("outer_stay", outer)):
        a, b, _ = cs
        a = a.copy()
        b = b.copy()
        a.x = 0
        b.x = 0
        rope(name, [a, b], 0.043, True, mast)
        for j, t in enumerate(np.linspace(0.06, 0.96, 13)):
            p = a.lerp(b, t)
            ring(name + "_hank_" + str(j), p, (0, 1, 0.5), 0.13, 0.013, M["iron"], mast)
    rope(
        "inner_sheet",
        [
            inner[2],
            RP(
                float(DECK.width(3.8)) - 0.28,
                3.8,
                float(DECK.heights(float(DECK.width(3.8)) - 0.28, 3.8)) + 0.95,
            ),
        ],
        0.027,
        parent=mast,
    )
    rope(
        "jib_sheet",
        [
            outer[2],
            RP(
                float(DECK.width(7.9)) - 0.28,
                7.9,
                float(DECK.heights(float(DECK.width(7.9)) - 0.28, 7.9)) + 0.95,
            ),
        ],
        0.027,
        parent=mast,
    )
    rope(
        "throat_halyard",
        [RP(-0.15, 1.05, 15.8), RP(-0.15, 0.8, 11.2), RP(-0.45, 1.0, 2.1)],
        0.025,
        parent=mast,
    )
    rope(
        "peak_halyard",
        [RP(-0.1, 1.05, 15.95), RP(0.84, -4.63, 15.63), RP(-0.5, 1.1, 2.1)],
        0.026,
        parent=mast,
    )
    rope(
        "boom_topping_lift",
        [RP(-0.3, 1.05, 15.9), RP(1.65, -10.5, 3.9)],
        0.028,
        parent=boom,
    )
    rope(
        "main_sheet",
        [RP(1.65, -10.5, 3.8), RP(2.15, -9.6, float(DECK.heights(2.15, -9.6)) + 0.88)],
        0.034,
        parent=boom,
    )
    for side in (-1, 1):
        svals = (0.3, -0.8, -1.9)
        feet = []
        for j, s in enumerate(svals):
            x = side * (float(DECK.width(s)) + 0.3)
            z = float(DECK.heights(x, s)) + 0.45
            foot = RP(x, s, z)
            feet.append(foot)
            rope(
                "shroud_" + str(side) + "_" + str(j),
                [RP(side * 0.12, 1.05, 14.85), foot],
                0.055,
                True,
                mast,
            )
            tube(
                "chainplate",
                [foot - Vector((0, 0, 0.35)), foot - Vector((0, 0, 1.15))],
                0.065,
                M["iron"],
            )
            for h in (0, -0.25):
                tube(
                    "deadeye",
                    [foot + Vector((0, -0.055, h)), foot + Vector((0, 0.055, h))],
                    0.19,
                    M["wood_dark"],
                    sides=12,
                )
            for ds in (-0.05, 0.05):
                rope(
                    "deadeye_lanyard",
                    [foot + Vector((ds, 0, 0)), foot + Vector((ds, 0, -0.26))],
                    0.015,
                    True,
                )
        for j, z in enumerate(np.arange(RP(0,1.05,2.5).z, RP(0,1.05,13.6).z, 0.36)):
            t = (z - feet[0].z) / (RP(0,1.05,14.85).z - feet[0].z)
            pts = [p.lerp(RP(side * 0.12, 1.05, 14.85), t) for p in feet]
            rope("ratline_" + str(side) + "_" + str(j), pts, 0.012, True, mast)
        x = side * (float(DECK.width(-4.0)) - 0.035)
        z = float(DECK.heights(x, -4)) + 0.78
        rope(
            "backstay_" + str(side),
            [RP(side * 0.12, 1.05, 15.95), RP(x, -4, z)],
            0.045,
            True,
            mast,
        )
        rope(
            "bowsprit_side_stay_" + str(side),
            [
                RP(0, 14.275, 6.85),
                RP(
                    side * (float(DECK.width(8.0)) - 0.05),
                    8.0,
                    float(DECK.heights(float(DECK.width(8.0)) - 0.05, 8.0)) + 0.78,
                ),
            ],
            0.04,
            True,
            bowsprit,
        )
        rope(
            "bobstay_" + str(side),
            [RP(side * 0.08, 14.275, 6.8), RP(side * 0.08, 10.9, 0.2)],
            0.05,
            True,
            bowsprit,
        )
        x = side * (float(DECK.width(-0.8)) + 0.17)
        z = float(DECK.heights(x, -0.8)) + 0.35
        box("shroud_channel", RP(x, -0.8, z), (0.52, 3.4, 0.15), M["wood_dark"])
    return mast, boom, gaff




if __name__=="__main__":
    main()


