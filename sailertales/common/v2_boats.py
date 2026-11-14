"""Guide-based small boats: closed lapstrakes, working carvel boat and carved log.

blender -b --factory-startup --python-exit-code 1 --python
sailertales/common/v2_boats.py -- sailertales/mewka/spec.json --out build/final/mewka

The clinker cross-section and scantlings adapt wyposazenie.lodz_mesh from the
published construction guide. Small craft are not scaled versions of a warship.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import sys

import bpy
import bmesh
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(HERE))
UP = ROOT/'blender'
if not UP.exists():
    UP = ROOT/'upstream'/'blender'
sys.path.insert(0,str(UP))
import narzedzia as N
import parametry as PR
import materialy

VIS, COL, MARKERS = [], [], []
MATS = {}


def p(x,s,z):
    return Vector((x,-s,z))


def point_gltf(v):
    return [float(v.x),float(v.z),float(-v.y)]


def physical_uv(obj, grain=Vector((0,-1,0)),grain_path=None):
    """Per-triangle isometry: real metres, no projection stretch on the bilge.

    U follows the timber longitudinal axis projected onto the local face.
    Separate timber components have independently oriented real wood grain.
    """
    bm=bmesh.new();bm.from_mesh(obj.data)
    bmesh.ops.triangulate(bm,faces=list(bm.faces))
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    # Ch.13 D3: consistent normals alone do not choose outside for thin tubes.
    # Orient each CLOSED connected solid by its signed volume, never open cloth.
    unseen=set(bm.faces)
    while unseen:
        seed=unseen.pop();component=[seed];stack=[seed]
        while stack:
            face=stack.pop()
            for edge in face.edges:
                for other in edge.link_faces:
                    if other in unseen:
                        unseen.remove(other);component.append(other);stack.append(other)
        if all(edge.is_manifold for face in component for edge in face.edges):
            origin=component[0].verts[0].co.copy()
            volume=sum((face.verts[0].co-origin).dot((face.verts[1].co-origin).cross(face.verts[2].co-origin))/6
                       for face in component)
            if volume<0:bmesh.ops.reverse_faces(bm,faces=component)
    bm.normal_update()
    bm.to_mesh(obj.data);bm.free()
    uv=obj.data.uv_layers.new(name='uv_metre')
    for face in obj.data.polygons:
        normal=face.normal
        direction=grain
        if grain_path:
            center=sum((obj.data.vertices[i].co for i in face.vertices),Vector())/len(face.vertices)
            best=1e30
            for a,b in zip(grain_path,grain_path[1:]):
                delta=b-a
                t=max(0,min(1,(center-a).dot(delta)/max(delta.length_squared,1e-12)))
                dist=(center-a-delta*t).length_squared
                if dist<best:best=dist;direction=delta
        u=direction-normal*direction.dot(normal)
        if u.length<0.01:
            u=Vector((1,0,0))-normal*normal.x
        if u.length<0.01:
            u=Vector((0,1,0))-normal*normal.y
        u.normalize();v=normal.cross(u).normalized()
        for li in face.loop_indices:
            q=obj.data.vertices[obj.data.loops[li].vertex_index].co
            uv.data[li].uv=(q.dot(u)/2,q.dot(v)/2)
    obj['uv_method']='isometric triangles, physical 2 m grain tile'
    obj['grain_axis']=list(grain)
    if grain_path:
        obj['grain_path_json']=json.dumps({'axes':'object_local','points':[list(q) for q in grain_path]})


def mesh(name,verts,faces,mat='wood',collision=False,kind='fitting',grain=None,grain_path=None):
    name=re.sub('[^a-z0-9_]','_',name.lower())
    me=bpy.data.meshes.new(name)
    me.from_pydata(verts,[],faces);me.update()
    o=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(o)
    me.materials.append(MATS[mat])
    o['kind']=kind;o['asset_role']='visual';o['physics']='solid' if collision else 'none'
    physical_uv(o,grain if grain is not None else Vector((0,-1,0)),grain_path)
    VIS.append(o)
    if collision:
        collider(o)
    return o


def collider(obj,name=None):
    c=obj.copy();c.data=obj.data.copy();c.name=name or 'col_'+obj.name
    bpy.context.collection.objects.link(c)
    c['asset_role']='collision';c['source_name']=obj.name
    c.hide_render=True
    c.data.materials.clear();c.data.materials.append(MATS['collision'])
    COL.append(c)
    return c


def box(name,pos,size,mat='wood',collision=True,kind='fitting',grain=None):
    x,y,z=pos;a,b,c=[q/2 for q in size]
    vs=[(x+i*a,y+j*b,z+k*c) for k in (-1,1) for j in (-1,1) for i in (-1,1)]
    fs=[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]
    return mesh(name,vs,fs,mat,collision,kind,grain)


def tube(name,pts,radius,mat='wood',collision=False,kind='fitting',sides=8,end_radius=None):
    pts=[Vector(q) for q in pts]
    pts=[q for i,q in enumerate(pts) if not i or (q-pts[i-1]).length>1e-6]
    vs,fs=[],[]
    lengths=[0.0]
    for a,b in zip(pts,pts[1:]):lengths.append(lengths[-1]+(b-a).length)
    previous_u=None
    for i,q in enumerate(pts):
        tangent=pts[min(i+1,len(pts)-1)]-pts[max(0,i-1)]
        tangent.normalize()
        u=previous_u-tangent*previous_u.dot(tangent) if previous_u is not None else tangent.cross(Vector((0,0,1)))
        if u.length<0.01:u=tangent.cross(Vector((1,0,0)))
        if u.length<0.01:u=tangent.cross(Vector((0,1,0)))
        if previous_u is not None and u.dot(previous_u)<0:u=-u
        u.normalize();v=tangent.cross(u)
        previous_u=u.copy()
        r=radius+(end_radius-radius)*i/(len(pts)-1) if end_radius else radius
        vs.extend(q+r*(math.cos(j*2*math.pi/sides)*u+math.sin(j*2*math.pi/sides)*v) for j in range(sides))
    for i in range(len(pts)-1):
        for j in range(sides):
            a=i*sides+j;b=i*sides+(j+1)%sides
            fs.append((a,b,b+sides,a+sides))
    fs+=[tuple(reversed(range(sides))),tuple((len(pts)-1)*sides+j for j in range(sides))]
    o=mesh(name,vs,fs,mat,collision,kind,pts[-1]-pts[0])
    if mat in ('wood','dark','tar'):
        o['grain_path_json']=json.dumps({'axes':'object_local','points':[list(q) for q in pts]})
    # Re-map the curved side into axial length and circumference metres.
    uv=o.data.uv_layers.active
    for face in o.data.polygons:
        indices=[o.data.loops[li].vertex_index for li in face.loop_indices]
        if len({i//sides for i in indices})==1:continue
        js=[i%sides for i in indices]
        wraps=max(js)-min(js)>sides/2
        for li in face.loop_indices:
            vi=o.data.loops[li].vertex_index;ring,j=divmod(vi,sides)
            if wraps and j==0:j=sides
            uv.data[li].uv=((lengths[ring]/(2*3.3*radius*2),j/sides) if kind=='rope' else
                            (lengths[ring]/2,2*math.pi*radius*j/sides/2))
    if collision:
        # The copy was made before axial UV remapping; collider UVs have no use.
        pass
    if kind=='rope':
        o['uv_method']='guide rope repeat: U=length/(2*3.3*diameter), V=turn'
        o['path_gltf_m']=[point_gltf(q) for q in pts]
        o['diameter_m']=radius*2
    return o


def empty(name,pos,**extras):
    o=bpy.data.objects.new(name,None);o.location=pos
    bpy.context.collection.objects.link(o)
    o['asset_role']='marker'
    for key,value in extras.items():o[key]=value
    MARKERS.append(o)
    return o


def materials(dest):
    cache=ROOT/'build'/'guide-brig'/'tekstury'
    if not (cache/'drewno_kolor.jpg').exists():
        from rebuild_reference import textures
        cache=dest/'textures'
        textures(UP,cache)
    chosen={'wood':'drewno','dark':'drewno_ciemne','tar':'drewno_czarne',
            'rope':'lina_jasna','tar_rope':'lina_smolowana','canvas':'plotno','iron':'zelazo'}
    for name,key in chosen.items():
        spec=dict(PR.MATERIALY[key])
        # All fitting and timber textures have a 2 m physical repeat (1024 px/m).
        # Rope and sail use their original guide-scaled tiles below.
        m=materialy.material(key,spec,str(cache))
        if name=='iron':m['uv_tile_m']=(2.0,2.0)
        MATS[name]=m
    MATS['collision']=bpy.data.materials.new('physics_debug')
    MATS['collision'].diffuse_color=(.1,.4,.1,1)


class PlankBoat:
    """Ch. 09 jol section, with explicitly different plank-built profiles."""
    def __init__(self,spec):
        self.spec=spec;self.L=spec['length'];self.B=spec['beam'];self.floor=spec['deck']
        self.kind=spec['id'];self.base=-spec['draft']+.025
        self.freeboard={'dinghy':.22,'rowboat':.40,'mewka':.43}[self.kind]
        self.depth=self.floor-self.base+self.freeboard
        self.planks={'dinghy':6,'rowboat':7,'mewka':8}[self.kind]
        self.thickness={'dinghy':.018,'rowboat':.022,'mewka':.028}[self.kind]
        self.lap=.012 if self.kind!='mewka' else 0

    def section(self,u):
        if self.kind=='mewka':
            # Double-ended working boat, full amidships and finer at both ends.
            hb=self.B/2*max(.025,math.sin(math.pi*u)**.54)
            sheer=self.depth+.22*abs(2*u-1)**3
            rise=.13*abs(2*u-1)**4
        else:
            transom=.82 if self.kind=='dinghy' else .66
            full=.48 if self.kind=='dinghy' else .55
            hb=self.B/2*(transom+(1-transom)*math.sin(math.pi*min(u/full,1)*.5)) if u<full else \
                self.B/2*max(.02,math.cos((u-full)/(1-full)*math.pi/2)**.8)
            sheer=self.depth+(.08 if self.kind=='dinghy' else .13)*((u-.42)/.58)**2
            rise=(.08 if self.kind=='dinghy' else .12)*u**4
        return hb,sheer,rise

    def at(self,u,v,off=0,side=1):
        hb,sheer,rise=self.section(u);theta=v*math.pi/2
        # Scantlings taper into stem/keel joins rather than crossing the centreline.
        if off<0:off=max(off,-hb*.45)
        x=hb*math.sin(theta)**.75
        z=rise+(sheer-rise)*(1-math.cos(theta))**1.15
        nx,nz=math.sin(theta),-.6*math.cos(theta);n=math.hypot(nx,nz)
        return p(side*(x+off*nx/n),(u-.5)*self.L,self.base+z+off*nz/n)

    def inside_width(self,s,height):
        u=s/self.L+.5;lo,hi=.001,1
        for _ in range(32):
            v=(lo+hi)/2
            if self.at(u,v,-self.thickness-.045).z<height:lo=v
            else:hi=v
        return abs(self.at(u,(lo+hi)/2,-self.thickness-.045).x)

    def build(self):
        us=np.linspace(0,1,41)
        for side in (-1,1):
            for k in range(self.planks):
                v0=.008+.992*k/self.planks
                v1=.008+.992*(k+1)/self.planks
                if k and self.lap:v0-=.012
                loops=[[self.at(u,v0,self.lap,side) for u in us],
                       [self.at(u,v1,0,side) for u in us],
                       [self.at(u,v0,-self.thickness+.003,side) for u in us],
                       [self.at(u,v1,-self.thickness,side) for u in us]]
                vs=[q for row in loops for q in row];n=len(us);fs=[]
                for i in range(n-1):
                    fs += [(i,i+1,n+i+1,n+i),(2*n+i,3*n+i,3*n+i+1,2*n+i+1),
                           (i,2*n+i,2*n+i+1,i+1),(n+i,n+i+1,3*n+i+1,3*n+i)]
                fs += [(0,n,3*n,2*n),(n-1,3*n-1,4*n-1,2*n-1)]
                o=mesh('strake_%s_%02d'%('port' if side>0 else 'starboard',k+1),vs,fs,
                       'wood',False,'hull',grain_path=[self.at(u,(v0+v1)/2,0,side) for u in us])
                o['construction']='closed clinker strake with 12 mm lap' if self.lap else 'closed flush carvel strake'
                o['joint_reason']='intentional lap with adjoining strake and keel/stem'
            # Bent frames follow the actual inner section, not vertical rods.
            for i,u in enumerate(np.arange(.10,.91,.40/self.L)):
                tube('bent_frame_%s_%02d'%('p' if side>0 else 's',i),
                     [self.at(u,v,-self.thickness-.014,side) for v in np.linspace(.06,.96,12)],
                     .018,'dark',False,'fitting',6)
            tube('gunwale_%s'%side,[self.at(u,1,.006,side) for u in us],
                 .027 if self.kind!='mewka' else .035,'tar',True,'fitting',8)
            tube('inwale_%s'%side,[self.at(u,1,-self.thickness-.025,side) for u in us],
                 .022,'dark',False,'fitting',6)
            for j,u in enumerate((.32,.60)):
                c=self.at(u,1,-.008,side)
                for k,ds in enumerate((-.055,.055)):
                    tube('thole_%s_%s_%s'%(side,j,k),[c+p(0,ds,-.01),c+p(0,ds,.10)],.010,'dark',False,'fitting',6)
        # Keel, stem and sternpost follow the run/rising line from the guide.
        keel=[p(0,(u-.5)*self.L,self.base+self.section(u)[2]-.015) for u in us]
        tube('keel',keel,.045,'dark',True,'hull',8)
        for end,u in [('stem',1.0),('sternpost',0.0)]:
            c=self.at(u,0)
            top=p(0,(u-.5)*self.L,self.at(u,1).z+.035)
            tube(end,[c,p(0,(u-.5)*self.L,c.z+.15),top],.032,'dark',True,'hull',8)
        if self.kind!='mewka':
            u=0;profile=[self.at(u,v,.001,-1) for v in np.linspace(1,0,13)]+[self.at(u,v,.001,1) for v in np.linspace(0,1,13)[1:]]
            # Filled transom closes the hull stern, thickness toward the cockpit.
            vs=profile+[q+p(0,.032,0) for q in profile];n=len(profile)
            fs=[tuple(reversed(range(n))),tuple(range(n,2*n))]
            fs += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
            mesh('transom',vs,fs,'wood',True,'hull',Vector((1,0,0)))
        self.collision_shell()
        self.floorboards()
        self.seats_and_oars()

    def collision_shell(self):
        us=np.linspace(0,1,19);rows=[]
        for u in us:
            outer=[self.at(u,v,0,-1) for v in np.linspace(1,0,10)] + [self.at(u,v,0,1) for v in np.linspace(0,1,10)[1:]]
            inner=[self.at(u,v,-self.thickness,-1) for v in np.linspace(1,0,10)] + [self.at(u,v,-self.thickness,1) for v in np.linspace(0,1,10)[1:]]
            rows.append(outer+list(reversed(inner)))
        n=len(rows[0]);vs=[q for row in rows for q in row];fs=[]
        for i in range(len(rows)-1):
            for j in range(n):
                fs.append((i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j))
        fs += [tuple(reversed(range(n))),tuple((len(rows)-1)*n+j for j in range(n))]
        c=mesh('hull_collision_source',vs,fs,'collision',False,'hull')
        VIS.remove(c);COL.append(c);c.name='col_hollow_hull';c['asset_role']='collision';c['physics']='solid';c.hide_render=True
        c['construction']='closed thin shell; cockpit remains genuinely hollow'

    def floorboards(self):
        # Individual boards have their seams in geometry and the wood grain in UV.
        # Main floor never creates a deck closing the boat at gunwale height.
        s0,s1=-self.L*.28,self.L*.27
        board=.16 if self.kind!='dinghy' else .14
        widths=[self.inside_width(s,self.floor)-.035 for s in np.linspace(s0,s1,38)]
        maxw=max(widths)
        for i,x in enumerate(np.arange(-math.floor(maxw/board),math.floor(maxw/board)+1)*board):
            xx0,xx1=x-board/2+.003,x+board/2-.003
            vs=[];fs=[];rows=[]
            ss=np.linspace(s0,s1,38)
            for s in ss:
                w=self.inside_width(s,self.floor)-.03
                lo=max(xx0,-w);hi=min(xx1,w)
                if hi<=lo:continue
                rows.append([p(lo,s,self.floor-.035),p(hi,s,self.floor-.035),
                             p(hi,s,self.floor),p(lo,s,self.floor)])
            if len(rows)<2:continue
            vs=[q for row in rows for q in row]
            for j in range(len(rows)-1):
                for k in range(4):fs.append((j*4+k,j*4+(k+1)%4,(j+1)*4+(k+1)%4,(j+1)*4+k))
            fs += [(3,2,1,0),tuple((len(rows)-1)*4+k for k in range(4))]
            if fs:
                o=mesh('sole_board_%02d'%i,vs,fs,'wood',True,'surface')
                o['physics']='walk_surface'
                COL[-1]['physics']='walk_surface'

    def seats_and_oars(self):
        # Thwarts at the ends; two split side seats leave a continuous centre lane.
        seat_s=(-.34*self.L,.32*self.L)
        for j,s in enumerate(seat_s):
            z=self.floor+min(.24,self.freeboard-.06);w=self.inside_width(s,z)
            box('end_thwart_%02d'%j,p(0,s,z),(2*w,.19,.04),'wood',True,'fitting',Vector((1,0,0)))
            for side in (-1,1):
                box('thwart_riser_%s_%s'%(j,side),p(side*(w+.018),s,z-.0375),
                    (.065,.28,.085),'dark',False,'fitting')
        if self.kind=='rowboat':
            for side in (-1,1):
                x=side*(self.B/2-.15)
                box('side_seat_%s'%side,p(x,-.10*self.L,self.floor+.26),(.15,self.L*.22,.04),'wood',True)
                for j,s in enumerate((-.18*self.L,-.02*self.L)):
                    box('side_seat_knee_%s_%s'%(side,j),p(x+.015*side,s,self.floor+.185),
                        (.19,.14,.14),'dark',False,'fitting')
        for side in (-1,1):
            s0=-self.L*.28;s1=self.L*.24
            u0=s0/self.L+.5;u1=s1/self.L+.5
            a=self.at(u0,1,.006,side)+p(0,0,.07)
            b=self.at(u1,1,.006,side)+p(0,0,.07)
            tube('stowed_oar_shaft_%s'%side,[a,b],.021,'wood',False,'fitting',8)
            blade_c=b+(b-a).normalized()*.14
            box('stowed_oar_blade_%s'%side,blade_c,(.10,.38,.016),'wood',False,'fitting')
            # Lashings terminate on oar and real gunwale, rather than floating.
            for j,t in enumerate((.20,.65)):
                c=a.lerp(b,t);u=(1-t)*u0+t*u1
                root=self.at(u,1,-.01,side)
                tube('oar_lashing_%s_%s'%(side,j),[root,c+p(0,0,.022),root+p(0,.035,0)],.005,'rope',False,'rope',6)


def dugout(spec):
    L,B=spec['length'],spec['beam'];sole=spec['deck'];base=-spec['draft']
    rim=sole+.27
    # Outer ellipsoid log: a separate carved construction, no planks or ribs.
    us=np.linspace(-1,1,49);vs=[];fs=[];n=26
    for u in us:
        w=B/2*math.sqrt(max(.003,1-u**4))
        rise=.15*abs(u)**5
        for j in range(n):
            theta=2*math.pi*j/n
            x=w*math.cos(theta)
            z=(rim+base)/2+rise+(rim-base)/2*math.sin(theta)
            vs.append(p(x,u*L/2,z))
    for i in range(len(us)-1):
        for j in range(n):fs.append((i*n+j,i*n+(j+1)%n,(i+1)*n+(j+1)%n,(i+1)*n+j))
    fs += [tuple(reversed(range(n))),tuple((len(us)-1)*n+j for j in range(n))]
    hull=mesh('hollowed_log',vs,fs,'wood',False,'hull')
    # A closed carved cavity cuts into the monolithic solid and opens its top.
    us2=np.linspace(-.82,.82,35);rv=[];rf=[];m=20
    for u in us2:
        w=(B/2-.115)*math.sqrt(max(.04,1-(u/.90)**6))
        end_rise=.14*abs(u/.82)**6
        for j in range(m):
            theta=2*math.pi*j/m
            x=w*math.cos(theta)
            z=sole+end_rise+.65+.65*math.sin(theta)
            rv.append(p(x,u*L/2,z))
    for i in range(len(us2)-1):
        for j in range(m):rf.append((i*m+j,i*m+(j+1)%m,(i+1)*m+(j+1)%m,(i+1)*m+j))
    rf += [tuple(reversed(range(m))),tuple((len(us2)-1)*m+j for j in range(m))]
    cut=mesh('carving_cutter',rv,rf,'wood',False,'hull')
    bpy.context.view_layer.objects.active=hull
    mod=hull.modifiers.new('carved_cavity','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cut
    bpy.ops.object.modifier_apply(modifier=mod.name)
    VIS.remove(cut);bpy.data.objects.remove(cut,do_unlink=True)
    physical_uv(hull)
    hull['construction']='single carved timber; closed solid with open hollow cavity'
    hull['physics']='solid'
    # The inner flat footboards are not fabricated: this is the leveled carved sole.
    s0,s1=-L*.20,L*.20
    o=box('carved_sole',p(0,(s0+s1)/2,sole-.022),(.91,s1-s0,.044),'wood',False,'surface')
    o['construction']='leveled wood left inside log, not a plank insert'
    o['physics']='walk_surface'
    # The retained flat wood belongs to the same log, so remove internal faces.
    bpy.context.view_layer.objects.active=hull
    mod=hull.modifiers.new('retained_wood','BOOLEAN');mod.operation='UNION';mod.solver='EXACT';mod.object=o
    bpy.ops.object.modifier_apply(modifier=mod.name)
    VIS.remove(o);bpy.data.objects.remove(o,do_unlink=True)
    physical_uv(hull)
    for j,s in enumerate((-L*.30,L*.30)):
        seat=box('carved_end_seat_%s'%j,p(0,s,sole+.065),(.72,.22,.18),'wood',False,'fitting')
        bpy.context.view_layer.objects.active=hull
        mod=hull.modifiers.new('retained_end_seat','BOOLEAN');mod.operation='UNION';mod.solver='EXACT';mod.object=seat
        bpy.ops.object.modifier_apply(modifier=mod.name)
        VIS.remove(seat);bpy.data.objects.remove(seat,do_unlink=True)
    physical_uv(hull)
    collider(hull,'col_hollowed_log')
    # Paddle rests on two carved end seats; never across the standing lane.
    a=p(.50,-L*.32,sole+.23);b=p(.50,L*.26,sole+.23)
    tube('paddle_shaft',[a,b],.022,'wood',False,'fitting',8)
    box('paddle_blade',b+p(0,.12,0),(.15,.40,.025),'wood',False,'fitting')
    for j,t in enumerate((.2,.7)):
        q=a.lerp(b,t);u=(-q.y)/(L/2)
        w=B/2*math.sqrt(max(.003,1-u**4))
        z=(rim+base)/2+.15*abs(u)**5+(rim-base)/2*math.sqrt(max(0,1-(q.x/w)**2))
        root=p(q.x,-q.y,z)
        tube('paddle_lashing_%s'%j,[root,q+p(0,0,.025),root+p(0,.03,0)],.005,'rope',False,'rope',6)


def mewka_rig(spec,boat):
    D=spec['deck'];mast_s=.65;mast_x=.24;top=D+5.15
    tube('mast',[p(mast_x,mast_s,D-.16),p(mast_x,mast_s,top)],.075,'wood',True,'spar',12,.045)
    box('mast_step',p(mast_x,mast_s,D+.04),(.22,.24,.08),'dark',True)
    yard_z=top-.42;sail_s=mast_s+.22;width=3.20
    tube('yard',[p(mast_x-width/2,mast_s+.14,yard_z),p(mast_x+width/2,mast_s+.14,yard_z)],.043,'wood',False,'spar',12,.030)
    tube('yard_parrel',[p(mast_x-.025,mast_s+.14,yard_z),p(mast_x+.10,mast_s+.025,yard_z),
                        p(mast_x+.085,mast_s-.09,yard_z),p(mast_x-.085,mast_s-.09,yard_z),
                        p(mast_x-.10,mast_s+.025,yard_z),p(mast_x+.025,mast_s+.14,yard_z)],
         .008,'tar_rope',False,'rope',6)
    bottom=D+2.22;head=yard_z-.09
    nv,nu=12,14;verts=[];faces=[]
    for j in range(nv+1):
        v=j/nv
        half=(width/2-.10)+.05*v
        for i in range(nu+1):
            u=i/nu
            s=sail_s+.20*math.sin(math.pi*u)*math.sin(math.pi*v)
            verts.append(p(mast_x+(2*u-1)*half,s,bottom+(head-bottom)*v))
    for j in range(nv):
        for i in range(nu):
            a=j*(nu+1)+i;faces.append((a,a+1,a+nu+2,a+nu+1))
    sail=mesh('square_sail',verts,faces,'canvas',False,'sail')
    sail['surface_kind']='intentional open double-sided cloth'
    sail['minimum_foot_clearance_m']=bottom-D
    # Cloth maps to physical width/height, with seams vertical in the guide texture.
    uv=sail.data.uv_layers.active
    for f in sail.data.polygons:
        for li in f.loop_indices:
            q=sail.data.vertices[sail.data.loops[li].vertex_index].co
            uv.data[li].uv=(q.x/2.4,q.z/2.4)
    corners=[p(mast_x-width/2+.10,sail_s,bottom),p(mast_x+width/2-.10,sail_s,bottom),
             p(mast_x+width/2-.05,sail_s,head),p(mast_x-width/2+.05,sail_s,head)]
    for j in range(4):
        rope=tube('bolt_rope_%s'%j,[corners[j],corners[(j+1)%4]],.006,'rope',False,'rope',6)
        rope['attachment_sail']='square_sail';rope['edge_attachment']=True
    for j,x in enumerate(np.linspace(mast_x-width/2+.10,mast_x+width/2-.10,7)):
        rope=tube('head_roband_%s'%j,[p(x-.015,sail_s,head),p(x-.015,mast_s+.14,yard_z+.046),
                                    p(x+.015,mast_s+.14-.046,yard_z),p(x+.015,sail_s,head)],
                  .004,'rope',False,'rope',6)
        rope['attachment_sail']='square_sail';rope['edge_attachment']=True
    for side in (-1,1):
        # Aft chainplates are beyond the standing corridor at low elevations.
        s=-2.20;u=s/boat.L+.5
        foot=boat.at(u,1,-.005,side)+p(0,0,.025)
        box('chainplate_%s'%side,foot-p(0,0,.06),(.035,.09,.17),'iron',False)
        tube('shroud_%s'%side,[foot,p(mast_x,mast_s,top-.50)],.012,'tar_rope',False,'rope',6)
        # Brace ends actually attach to eyes on the after gunwale.
        tip=p(mast_x+side*width/2,mast_s+.14,yard_z)
        tube('brace_%s'%side,[tip,foot+p(0,.10,0)],.009,'rope',False,'rope',6)
        clew=p(mast_x+side*(width/2-.10),sail_s,bottom)
        stern_eye=boat.at(.12,1,-.012,side)
        rope=tube('sheet_%s'%side,[clew,stern_eye],.009,'rope',False,'rope',6)
        rope['attachment_sail']='square_sail';rope['edge_attachment']=True
    # Forestay remains ahead of cloth: its forward gunwale attachment is real.
    bow=boat.at(1,1,0,1);bow.x=0;bow.z+=.025
    box('mast_head_cap',p(mast_x,mast_s+.035,top-.06),(.14,.30,.12),'dark',False)
    tube('forestay',[p(mast_x,mast_s+.12,top-.02),bow],.012,'tar_rope',False,'rope',6)
    # Yard lifts attach above the cloth, not diagonally through it.
    for side in (-1,1):
        tube('lift_%s'%side,[p(mast_x+side*width/2,mast_s+.14,yard_z),p(mast_x,mast_s,top)],.008,'rope',False,'rope',6)
    # The hauling part is behind the mast and terminates at a named cleat.
    cleat=p(mast_x+.10,mast_s-.10,D+.55)
    box('halyard_cleat',cleat,(.15,.06,.045),'dark',False)
    block=p(mast_x+.13,mast_s+.11,top-.20)
    box('halyard_block',block,(.10,.075,.13),'dark',False)
    tube('halyard_block_strop',[p(mast_x,mast_s,top-.12),block+p(0,0,.06),
                               p(mast_x,mast_s,top-.18)],.006,'tar_rope',False,'rope',6)
    tube('halyard',[p(mast_x,mast_s+.10,yard_z),block,cleat],.007,'rope',False,'rope',6)
    # Tiller/rudder and a pair of stern fishing creels distinguish this working boat.
    stock_s=-boat.L/2-.075
    stock_top=max(D+.45,boat.at(0,1).z+.20)
    rudder=box('rudder',p(0,-boat.L/2-.20,-spec['draft']+.25),(.05,.28,.50),'dark',False,'fitting',Vector((0,0,1)))
    tube('rudder_stock',[p(0,stock_s,-.15),p(0,stock_s,stock_top)],.032,'dark',False,'fitting',8)
    tube('tiller',[p(0,stock_s,stock_top-.02),p(.10,-boat.L*.29,D+.45)],.025,'wood',False,'fitting',8)
    for j,z in enumerate((-.10,.12)):
        tube('rudder_pintle_%s'%j,[p(0,-boat.L/2,z),p(0,stock_s,z)],.014,'iron',False,'fitting',8)
    for j,s in enumerate((-1.8,-1.35)):
        x=.30
        box('fishing_creel_%s'%j,p(x,s,D+.16),(.27,.31,.32),'dark',True)
        for k in range(5):
            tube('creel_hoop_%s_%s'%(j,k),[p(x-.14,s-.15+k*.075,D+.03),p(x-.14,s-.15+k*.075,D+.32),
                                          p(x+.14,s-.15+k*.075,D+.32),p(x+.14,s-.15+k*.075,D+.03)],.006,'rope',False,'rope',6)
    empty('station_helm',p(-.20,-.75,D),activity='steering')
    empty('station_mast',p(-.25,.65,D),activity='sail_handling')


def write_json(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def select_export(objects,path):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.hide_set(False);o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,
                              export_extras=True,export_yup=True,export_animations=False,
                              export_materials='EXPORT',export_image_format='AUTO')


def make_lod(level,dest):
    copies=[]
    ratio=.55 if level==1 else .20
    for o in VIS:
        if level==2 and o.name.startswith(('bent_frame','thole','oar_lashing','creel_hoop','halyard_cleat')):continue
        c=o.copy();c.data=o.data.copy();c.name=o.name+'_lod%s'%level
        bpy.context.collection.objects.link(c)
        if len(c.data.polygons)>30 and c.get('kind') not in ('sail','rope'):
            bpy.context.view_layer.objects.active=c
            mod=c.modifiers.new('lod_reduction','DECIMATE');mod.ratio=ratio
            bpy.ops.object.modifier_apply(modifier=mod.name)
        copies.append(c)
    select_export(copies,dest/'model'/('ship_lod%s.glb'%level))
    for o in copies:bpy.data.objects.remove(o,do_unlink=True)


def render(spec,dest):
    for o in COL:o.hide_render=True
    scene=bpy.context.scene
    scene.render.engine='CYCLES';scene.cycles.samples=32
    scene.render.resolution_x=1200;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    scene.view_settings.view_transform='AgX'
    if scene.world is None:scene.world=bpy.data.worlds.new('boat_preview_world')
    scene.world.color=(.30,.30,.30)
    L=spec['length'];center=Vector((0,0,spec['deck']+(1.75 if spec['id']=='mewka' else .20)))
    for pos,energy,size in [(Vector((L*.8,L*.5,L*1.4)),900*L,L),
                            (Vector((-L*.7,-L*.5,L*.7)),450*L,L*.75)]:
        bpy.ops.object.light_add(type='AREA',location=pos)
        light=bpy.context.object;light['asset_role']='presentation';light.data.energy=energy;light.data.size=size
        light.rotation_euler=(center-light.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add(location=center+Vector((L*.95,L*.95,L*.62)))
    cam=bpy.context.object;cam['asset_role']='presentation';cam.data.type='ORTHO'
    cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.ortho_scale=L*1.22 if spec['id']!='mewka' else L*1.35
    scene.camera=cam;scene.render.image_settings.file_format='JPEG';scene.render.image_settings.quality=90
    scene.render.filepath=str(dest/'previews'/'hero.jpg');bpy.ops.render.render(write_still=True)
    cam.location=Vector((L*.40,L*.35,L*.9));center=Vector((0,0,spec['deck']))
    cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=L*1.10
    for o in VIS:
        if o.get('kind') in ('sail','spar','rope') and not o.name.startswith('oar_lashing'):o.hide_render=True
    scene.render.filepath=str(dest/'previews'/'deck.jpg');bpy.ops.render.render(write_still=True)
    for o in VIS:o.hide_render=False


def main():
    ap=argparse.ArgumentParser();ap.add_argument('spec');ap.add_argument('--out',required=True)
    ap.add_argument('--no-render',action='store_true')
    ap.add_argument('--render-only',action='store_true')
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    spec_path=Path(args.spec).resolve();spec=json.loads(spec_path.read_text(encoding='utf-8'))
    if spec['id'] not in ('mewka','dinghy','rowboat','dugout'):raise ValueError('This builder is for the four small craft')
    dest=Path(args.out).resolve();(dest/'model').mkdir(parents=True,exist_ok=True);(dest/'previews').mkdir(exist_ok=True)
    if args.render_only:
        bpy.ops.wm.open_mainfile(filepath=str(dest/'model'/'ship.blend'))
        VIS.extend(o for o in bpy.context.scene.objects if o.get('asset_role')=='visual' and o.type=='MESH')
        COL.extend(o for o in bpy.context.scene.objects if o.get('asset_role')=='collision')
        render(spec,dest)
        return
    bpy.ops.wm.read_factory_settings(use_empty=True)
    materials(dest)
    if spec['id']=='dugout':dugout(spec)
    else:
        boat=PlankBoat(spec);boat.build()
        if spec['id']=='mewka':mewka_rig(spec,boat)
    empty('asset_origin',p(0,0,0),vessel_id=spec['id'],origin_description='design waterline and hull mid-length')
    D=spec['deck'];L=spec['length']
    routes=[]
    if spec['id']=='mewka':
        routes=[{'name':'cockpit_and_mast_bypass','mode':'walk','points':[[ -.25,D,-.75],[-.25,D,.65],[-.25,D,1.20]]}]
    elif spec['id']=='dinghy':routes=[{'name':'standing_cockpit','mode':'walk','points':[[0,D,-.60],[0,D,.55]]}]
    elif spec['id']=='rowboat':routes=[{'name':'centre_cockpit','mode':'walk','points':[[0,D,-1.05],[0,D,1.05]]}]
    else:routes=[{'name':'carved_cockpit','mode':'walk','points':[[0,D,-.85],[0,D,.85]]}]
    nav={'schema':2,'units':'metres','axes':'glTF X port, Y up, Z bow',
         'player':{'radius':.38,'height':1.85,'max_slope_deg':35},'routes':routes,
         'source_commit':spec['source_commit'],'requires_engine_controller':True}
    write_json(dest/'navigation.json',nav)
    source_file=UP/'wyposazenie.py'
    construction={'dinghy':'short broad-transom clinker tender, 6 closed strakes per side',
                  'rowboat':'longer 7-strake clinker shore rowing boat with split side seats',
                  'mewka':'double-ended 8-strake carvel fishing boat, small square rig and rudder',
                  'dugout':'single carved hollow timber; no fabricated frames, strakes or keel'}[spec['id']]
    design={'schema':2,'id':spec['id'],'construction':construction,
            'basis':{'repo':'grzegorz2047/OldShipSchematicsAndModel','commit':'2e6f7e922e95396722376d42f3e2e0a12256029e',
                     'source':'blender/wyposazenie.py:lodz_mesh','sha256':hashlib.sha256(source_file.read_bytes()).hexdigest(),
                     'chapters':['03 hull construction','08 ropes and sails','09 deck machinery and fittings','13 quality checklist','14 game integration']},
            'dimensions_m':{'length':L,'beam':spec['beam'],'draft_game_bound':spec['draft'],'standing_sole':D},
            'rules':{'clinker_plank_m':.018 if spec['id']=='dinghy' else .022,'clinker_lap_m':.012,
                     'freeboard_above_sole_m':{'dinghy':.22,'rowboat':.40,'mewka':.43,'dugout':.27}[spec['id']],
                     'frame_spacing_m':.40,'wood_texture_tile_m':2,'wood_texture_pixels':2048,
                     'grain_uv':'physical isometric triangles; axial UV on rods',
                     'mewka_sail_foot_above_sole_m':2.22 if spec['id']=='mewka' else None},
            'confidence':'our inference; guide boat recipe adapted to game families, not a claimed period plan',
            'game_deviations':['End thwarts and side seats leave a real standing corridor; no solid thwart across that corridor.',
                               'The small craft have no fabricated cabin or lower deck.',
                               'Dimensions specified as game bounds; no hydrostatic seaworthiness certification.'],
            'materials':'original guide procedural PBR wood, iron, hemp and canvas; distinct colour/normal/roughness maps',
            'spec_sha256':hashlib.sha256(spec_path.read_bytes()).hexdigest()}
    if spec['id']=='mewka':design['game_deviations'] += ['Mast partner displaced 0.24m to starboard and sail foot raised to clear standing player.']
    if spec['id']=='dugout':
        design['basis']['source']='docs/en/03-hull-construction.md and 13/14 general timber, mesh and game principles'
        design['basis']['construction_note']='The guide does not supply a dugout plan. The single carved-log profile and retained seats are our inference; no clinker frame/plank recipe is claimed for this boat.'
    design['sources']=design['basis']
    design['origin']={'position_gltf_m':[0,0,0],'meaning':'design waterline at hull mid-length'}
    joints=[]
    def joint(a,b,reason):joints.append({'a':a,'b':b,'reason':reason})
    if spec['id']!='dugout':
        for side in ('port','starboard'):
            for k in range(1,boat.planks):
                joint('strake_%s_%02d'%(side,k),'strake_%s_%02d'%(side,k+1),
                      'Adjacent closed clinker strakes intentionally overlap by 12 mm.' if boat.lap else
                      'Adjacent carvel strakes meet at their sewn/caulked seam.')
        for a,b,why in [
            ('strake_*','bent_frame_*','Bent frames sit against the inside of planking, with housed timber joints.'),
            ('strake_*','gunwale_*','The sheerstrake is housed in the gunwale.'),
            ('strake_*','inwale_*','The inwale backs the upper planking.'),
            ('bent_frame_*','inwale_*','Frame heads are housed in the inwale.'),
            ('bent_frame_*','gunwale_*','Frame heads support the gunwale cap.'),
            ('strake_*','keel','Garboard strakes are rebated into the keel.'),
            ('strake_*','stem','Strake ends are housed in the stem rabbet.'),
            ('strake_*','sternpost','The after ends meet the sternpost.'),
            ('strake_*','transom','Strake ends are fixed to the transom edge.'),
            ('keel','stem','Keel and stem have a scarfed structural joint.'),
            ('keel','sternpost','Keel and sternpost are scarfed together.'),
            ('keel','transom','The transom lands on the after keel.'),
            ('sternpost','transom','The transom is secured to the sternpost.'),
            ('strake_*','thwart_riser_*','Thwart riser rails are housed against the inner planking.'),
            ('bent_frame_*','thwart_riser_*','Thwart risers land on supporting frames.'),
            ('end_thwart_*','thwart_riser_*','The ends of each thwart rest on timber riser rails.'),
            ('sole_board_*','bent_frame_*','The sole boards rest on the lower frames.'),
            ('thole_*','gunwale_*','Thole pins are fixed into the gunwale.'),
            ('thole_*','inwale_*','The thole socket is supported by the inwale.'),
            ('stowed_oar_shaft_*','stowed_oar_blade_*','The oar loom is housed in its blade; each whole oar is lashed above the gunwale.'),
            ('side_seat_*','side_seat_knee_*','Side seats are supported on timber knees.'),
            ('side_seat_knee_*','strake_*','Seat knees are housed against the inner planking.'),
            ('side_seat_*','strake_*','A side-seat edge is housed against planking.'),
            ('side_seat_knee_*','bent_frame_*','Seat knees land on supporting frames.'),
            ('inwale_*','gunwale_*','The gunwale cap is fastened over the backing inwale.')]:joint(a,b,why)
        for a,b,why in [
            ('gunwale_*','stem','Gunwale ends meet in the stem-head joint.'),
            ('gunwale_*','sternpost','Gunwale ends meet at the sternpost head.'),
            ('gunwale_*','transom','Gunwale caps are housed over the transom corners.'),
            ('inwale_*','stem','Inwale ends are housed into the stem head.'),
            ('inwale_*','sternpost','Inwale ends are housed at the sternpost head.'),
            ('inwale_*','transom','Inwale ends land against the transom.'),
            ('thole_*','strake_*','Thole pins pass through the gunwale into the backing sheerstrake.')]:joint(a,b,why)
        for family in ('gunwale_','inwale_'):
            members=[o.name for o in VIS if o.name.startswith(family)]
            if len(members)==2:joint(*members,'The port and starboard rail ends meet inside the stem-head joint.')
    else:joint('paddle_shaft','paddle_blade','The paddle loom is housed in its blade; the paddle is lashed above the carved rim.')
    if spec['id']=='mewka':
        for a,b,why in [('mast','mast_step','The mast heel passes through the partner and stands in its step.'),
                        ('mast','sole_board_*','The mast passes through a fitted partner in the sole.'),
                        ('mast_step','sole_board_*','The step is fastened to the sole structure.'),
                        ('mast_head_cap','mast','The cap is fitted around the mast head.'),
                        ('chainplate_*','strake_*','Chainplates are fastened to the planking.'),
                        ('chainplate_*','gunwale_*','Chainplate eyes emerge at the gunwale.'),
                        ('halyard_cleat','mast','The halyard cleat is bolted to the mast.'),
                        ('rudder','rudder_stock','The rudder blade is housed around the rudder stock.'),
                        ('rudder_stock','tiller','The tiller is mortised into the stock head.'),
                        ('rudder_pintle_*','sternpost','The iron pintles are fixed to the sternpost.'),
                        ('rudder_pintle_*','rudder_stock','The stock is supported by iron pintles.'),
                        ('rudder_pintle_*','rudder','The iron pintles support the rudder blade assembly.'),
                        ('square_sail','bolt_rope_*','Own bolt ropes are sewn to the canvas perimeter.'),
                        ('square_sail','head_roband_*','Robands tie the head of the cloth to the yard; only boundary contact is intentional.'),
                        ('square_sail','sheet_*','Sheets attach at the lower clews, not across cloth interiors.')]:joint(a,b,why)
    design['intended_joints']=joints
    write_json(dest/'design.json',design)
    # Keep source specification beside assets for exact reproduction.
    shutil.copyfile(spec_path,dest/'spec.json')
    from v2_materials import upgrade_scene
    design['materials']=upgrade_scene(VIS)
    from v2_export import finalize
    result=finalize(spec,dest,visual_objects=VIS+MARKERS,collision_objects=COL,
                    navigation=nav,design=design,generate_lods=True)
    if not args.no_render:render(spec,dest)
    print('COMPLETE_SMALL_BOAT',spec['id'],len(VIS),len(COL),flush=True)


if __name__=='__main__':main()
