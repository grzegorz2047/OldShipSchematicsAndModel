"""Fractured, explorable wreck from the guide's PCHIP offset family.

blender -b --factory-startup --python-exit-code 1 --python
sailertales/common/v2_wreck.py -- sailertales/wreck/spec.json --out build/final/wreck

The retained planking, transom, frames and keel are closed individual timber
solids. A broken ship has no watertight envelope, but its timber fragments do.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
import bmesh
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'blender'
if not SOURCE.exists():
    SOURCE = ROOT/'upstream'/'blender'
sys.path.insert(0,str(SOURCE))
import parametry as PR
from rzedne import Kadlub

VIS, COL, MARKERS = [], [], []
DECK_RECTS, HOLD_RECTS = [], []
MATERIALS = {}
KD = None
SPEC = None
HEEL = None
OUT = None
LADDER = None


def p(x,s,h):
    return Vector((x,-s,h))


def gltf(q):
    return [q.x,q.z,-q.y]


def write(name,data):
    (OUT/name).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def recalc(me):
    bm=bmesh.new();bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    if bm.calc_volume(signed=True)<0:
        bmesh.ops.reverse_faces(bm,faces=list(bm.faces))
    bm.to_mesh(me);bm.free();me.update()


def uv_project(o,tile=2.0):
    uv=o.data.uv_layers.new(name='uv0')
    xyz=np.array([tuple(v.co) for v in o.data.vertices],dtype=float)
    centered=xyz-xyz.mean(axis=0)
    _,_,axes=np.linalg.svd(centered,full_matrices=False)
    principal=Vector(axes[0]).normalized()
    for face in o.data.polygons:
        vs=[o.data.vertices[i].co for i in face.vertices]
        # U follows the timber's principal longitudinal axis on side faces.
        along=principal-face.normal*principal.dot(face.normal)
        if along.length<1e-8:
            along=vs[1]-vs[0]
        along.normalize()
        across=face.normal.cross(along).normalized()
        base=vs[0]
        for li in face.loop_indices:
            q=o.data.vertices[o.data.loops[li].vertex_index].co-base
            uv.data[li].uv=(q.dot(along)/tile,q.dot(across)/tile)


def mesh(name,vertices,faces,mat,kind='fitting',physics='none',uvs=None):
    me=bpy.data.meshes.new(name)
    me.from_pydata(vertices,[],faces);me.update()
    o=bpy.data.objects.new(name,me);bpy.context.collection.objects.link(o)
    me.materials.append(MATERIALS[mat] if isinstance(mat,str) else mat)
    recalc(me)
    o['asset_role']='visual';o['kind']=kind;o['role']=kind;o['physics']=physics
    if uvs:
        uv=me.uv_layers.new(name='uv0')
        for face in me.polygons:
            for li in face.loop_indices:
                uv.data[li].uv=uvs[me.loops[li].vertex_index]
            coords=[uv.data[li].uv for li in face.loop_indices]
            area=abs(sum(a.x*b.y-a.y*b.x for a,b in zip(coords,coords[1:]+coords[:1])))/2
            if area<1e-12 and face.area>1e-10:
                # Timber end caps require planar end-grain UVs, not the single
                # longitudinal U coordinate inherited from their sweep ring.
                center=sum((me.vertices[i].co for i in face.vertices),Vector())/len(face.vertices)
                u=(me.vertices[face.vertices[1]].co-me.vertices[face.vertices[0]].co).normalized()
                v=face.normal.cross(u).normalized()
                for li in face.loop_indices:
                    q=me.vertices[me.loops[li].vertex_index].co-center
                    uv.data[li].uv=(.5+q.dot(u)/2,.5+q.dot(v)/2)
    else:
        uv_project(o)
    VIS.append(o)
    return o


def collider(o):
    c=o.copy();c.data=o.data.copy();c.name='col_'+o.name
    c.data.name=c.name
    c.data.materials.clear();c.data.materials.append(MATERIALS['collision'])
    for poly in c.data.polygons:poly.material_index=0
    c['asset_role']='collision';c.hide_render=True
    bpy.context.collection.objects.link(c);COL.append(c)
    return c


def box(name,center,size,mat,kind='fitting',physics='solid'):
    x,y,z=center;hx,hy,hz=[v/2 for v in size]
    vs=[(x+i*hx,y+j*hy,z+k*hz) for k in [-1,1] for j in [-1,1] for i in [-1,1]]
    return mesh(name,vs,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)],mat,kind,physics)


def beam(name,points,width,depth,mat='oak',kind='fitting',physics='solid'):
    points=[Vector(q) for q in points]
    vs=[];fs=[];uv=[];distance=0
    for i,q in enumerate(points):
        tangent=points[min(i+1,len(points)-1)]-points[max(i-1,0)]
        tangent.normalize()
        a=Vector((0,1,0))
        if abs(tangent.dot(a))>.95:
            a=Vector((1,0,0))
        a=(a-tangent*a.dot(tangent)).normalized()
        b=tangent.cross(a).normalized()
        if i:
            distance+=(q-points[i-1]).length
        for u,v in [(-1,-1),(1,-1),(1,1),(-1,1)]:
            vs.append(q+a*(u*width/2)+b*(v*depth/2))
            uv.append((distance/2,((u+1)*width+(v+1)*depth)/4))
    for i in range(len(points)-1):
        for j in range(4):
            a=4*i+j;b=4*i+(j+1)%4
            fs.append((a,b,b+4,a+4))
    fs += [(3,2,1,0),tuple(4*(len(points)-1)+j for j in range(4))]
    o=mesh(name,vs,fs,mat,kind,physics,uv)
    o['grain_path_json']=json.dumps({'axes':'object_local','points':[list(q) for q in points]})
    return o


def tapered(name,a,b,r0,r1,mat='oak',kind='fitting',physics='solid',n=12,broken=False):
    a,b=Vector(a),Vector(b);axis=(b-a).normalized()
    u=axis.cross(Vector((0,0,1)))
    if u.length<.05:u=axis.cross(Vector((0,1,0)))
    u.normalize();v=axis.cross(u).normalized()
    vs=[];uv=[]
    for level,(q,r) in enumerate([(a,r0),(b,r1)]):
        for j in range(n):
            ang=2*math.pi*j/n
            q1=q+u*(r*math.cos(ang))+v*(r*math.sin(ang))
            if level and broken:q1+=axis*(.13*math.sin(j*2.1)+.045*math.cos(j*4.2))
            vs.append(q1);uv.append((level*(b-a).length/2,j*2*math.pi*r/2/n))
    fs=[(j,(j+1)%n,(j+1)%n+n,j+n) for j in range(n)]
    fs += [tuple(range(n-1,-1,-1)),tuple(n+j for j in range(n))]
    return mesh(name,vs,fs,mat,kind,physics,uv)


def marker(name,q,kind='station',**props):
    o=bpy.data.objects.new(name,None);o.location=q;o.empty_display_size=.18
    o['asset_role']='marker';o['kind']=kind
    for k,v in props.items():o[k]=v
    bpy.context.collection.objects.link(o);MARKERS.append(o)
    return o


def make_materials():
    tex=ROOT/'build'/'guide-brig'/'tekstury'
    if not (tex/'drewno_kolor.jpg').exists():
        from rebuild_reference import textures
        tex=ROOT/'build'/'reference_textures';textures(SOURCE,tex)
    cache={}
    def image(path,noncolor=False):
        if (str(path),noncolor) not in cache:
            im=bpy.data.images.load(str(path),check_existing=False)
            im.name=Path(path).stem.lower()
            im.colorspace_settings.name='Non-Color' if noncolor else 'sRGB'
            im.pack();cache[(str(path),noncolor)]=im
        return cache[(str(path),noncolor)]
    base=image(tex/'drewno_kolor.jpg')
    rgba=np.empty(len(base.pixels),dtype=np.float32);base.pixels.foreach_get(rgba)
    rgba=rgba.reshape((-1,4))
    for name,tint,bright in [('oak',(.78,.77,.72),.03),('deck',(.95,.92,.83),.055),
                             ('endgrain',(.82,.73,.58),.02),('dark_oak',(.50,.45,.35),.005)]:
        m=bpy.data.materials.new(name);m.use_nodes=True
        bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Metallic'].default_value=0
        bs.inputs['Roughness'].default_value=.83
        col=bpy.data.images.new(name+'_color',base.size[0],base.size[1],alpha=False)
        col.colorspace_settings.name='sRGB'
        # Weathering is a colour transform of the MIT procedural guide texture.
        a=rgba.copy();gray=a[:,:3].mean(axis=1)
        a[:,:3]=(a[:,:3]*.35+gray[:,None]*.65)*np.array(tint)+bright
        a[:,:3]=np.clip(a[:,:3],.025,.85)
        col.pixels.foreach_set(a.ravel())
        textures_dir=OUT/'textures';textures_dir.mkdir(exist_ok=True)
        col.filepath_raw=str(textures_dir/(name+'_color.png'));col.file_format='PNG'
        col.save();col.pack()
        ti=m.node_tree.nodes.new('ShaderNodeTexImage');ti.image=col
        m.node_tree.links.new(ti.outputs['Color'],bs.inputs['Base Color'])
        tn=m.node_tree.nodes.new('ShaderNodeTexImage');tn.image=image(tex/'drewno_normalne.jpg',True)
        normal=m.node_tree.nodes.new('ShaderNodeNormalMap')
        normal.inputs['Strength'].default_value=.55
        m.node_tree.links.new(tn.outputs['Color'],normal.inputs['Color'])
        m.node_tree.links.new(normal.outputs['Normal'],bs.inputs['Normal'])
        tr=m.node_tree.nodes.new('ShaderNodeTexImage');tr.image=image(tex/'drewno_szorstkosc.jpg',True)
        sp=m.node_tree.nodes.new('ShaderNodeSeparateColor')
        m.node_tree.links.new(tr.outputs['Color'],sp.inputs['Color'])
        m.node_tree.links.new(sp.outputs['Green'],bs.inputs['Roughness'])
        m.diffuse_color=(*tint,1);m.use_backface_culling=True
        MATERIALS[name]=m
    for name,color,metal,rough in [('iron',(.035,.032,.027),1,.75),('brass',(.34,.20,.065),1,.52),
                                  ('leather',(.16,.045,.027),0,.82),('paper',(.58,.51,.35),0,.95),
                                  ('glass',(.12,.18,.17),0,.20),
                                  ('collision',(.15,.4,.12),0,.9)]:
        m=bpy.data.materials.new(name);m.use_nodes=True
        bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*color,1)
        bs.inputs['Metallic'].default_value=metal;bs.inputs['Roughness'].default_value=rough
        m.diffuse_color=(*color,1);m.use_backface_culling=True;MATERIALS[name]=m


class Lines:
    """Original PCHIP reference shape mapped to the stranded wreck coordinates."""
    def __init__(self,spec):
        self.kd=Kadlub(PR.KADLUB,PR.RZEDNE_H,PR.RZEDNE_S,PR.RZEDNE)
        self.sl=spec['length']/28;self.sb=spec['beam']/7.6
        self.ref_deck=float(self.kd.deck_c(0))
        self.ref_keel=float(self.kd.zk(0))-PR.KADLUB['STEPKA_WYS']
        self.sz=(spec['deck']+spec['draft'])/(self.ref_deck-self.ref_keel)
        self.zoff=spec['deck']-self.ref_deck*self.sz
        self.plank=PR.KADLUB['POSZYCIE_GR']*self.sb

    def z(self,z):return z*self.sz+self.zoff
    def inverse_z(self,z):return (z-self.zoff)/self.sz
    def section(self,s,v):
        sr=s/self.sl;keel=float(self.kd.zk(sr));deck=float(self.kd.Zd(sr))
        zr=keel+(deck+1.05-keel)*v
        return float(self.kd.H(sr,zr)[0])*self.sb,self.z(zr)
    def width(self,s,z):
        return float(self.kd.H(s/self.sl,self.inverse_z(z))[0])*self.sb
    def deck(self,s,x=0):return self.z(float(self.kd.deck_z(s/self.sl,x/self.sb)))
    def aft(self,v):
        lo,hi=-16.0,-10.0
        for _ in range(48):
            sr=(lo+hi)/2;keel=float(self.kd.zk(sr));deck=float(self.kd.Zd(sr))
            h=(deck+1.05-keel)*v
            if sr-self.kd.a_of_h(h)<0:lo=sr
            else:hi=sr
        return (lo+hi)/2*self.sl


def shell():
    levels=18;segments=46
    for side in [-1,1]:
        for r in range(levels):
            va,vb=r/levels,(r+1)/levels
            end_a=2.35+.23*math.sin(r*2.3)+.08*side
            end_b=2.35+.23*math.sin((r+1)*2.3)+.08*side
            sa,sb=KD.aft(va),KD.aft(vb)
            vs=[]
            for inner in [False,True]:
                for v,start,end in [(va,sa,end_a),(vb,sb,end_b)]:
                    for i in range(segments+1):
                        s=start+(end-start)*i/segments
                        w,z=KD.section(s,v)
                        x=side*max(.015,w-(KD.plank if inner else 0))
                        vs.append(p(x,s,z))
            n=segments+1;fs=[]
            for i in range(segments):
                fs += [(i,i+1,n+i+1,n+i),
                       (2*n+i,3*n+i,3*n+i+1,2*n+i+1),
                       (i,2*n+i,2*n+i+1,i+1),
                       (n+i,n+i+1,3*n+i+1,3*n+i)]
            fs += [(0,n,3*n,2*n),(n-1,3*n-1,4*n-1,2*n-1)]
            o=mesh('hull_strake_%s_%02d'%('port' if side>0 else 'starboard',r),vs,fs,'oak','hull','solid')
            o['construction']='closed planking strake; capped staggered timber fracture'
            o['guide']='chapters 02,03; reference PCHIP offsets'
            collider(o)
    # Flat transom bands use the actual end-of-waterline profile of the source.
    for r in range(levels):
        a,b=r/levels,(r+1)/levels;sa,sb=KD.aft(a),KD.aft(b)
        wa,za=KD.section(sa,a);wb,zb=KD.section(sb,b)
        t=KD.plank
        vs=[p(-wa,sa,za),p(wa,sa,za),p(wb,sb,zb),p(-wb,sb,zb),
            p(-wa,sa+t,za),p(wa,sa+t,za),p(wb,sb+t,zb),p(-wb,sb+t,zb)]
        o=mesh('transom_strake_%02d'%r,vs,[(0,1,2,3),(4,7,6,5),(0,4,5,1),
                (1,5,6,2),(2,6,7,3),(3,7,4,0)],'dark_oak','hull','solid')
        collider(o)
    # Keel and keelson follow the guide rabbet with their own closed scantlings.
    ss=np.linspace(KD.aft(0)+.1,2.38,45)
    keel=[p(0,s,KD.z(float(KD.kd.zk(s/KD.sl)))-.11) for s in ss]
    o=beam('fractured_keel',keel,.26*KD.sb,.31*KD.sz,'dark_oak','hull');collider(o)
    keelson=[p(0,s,KD.z(float(KD.kd.zk(s/KD.sl)))+.34) for s in ss]
    o=beam('keelson',keelson,.28*KD.sb,.25*KD.sb,'oak','fitting');collider(o)
    # Wales remain full timbers, with damaged forward ends, not painted lines.
    for side in [-1,1]:
        for j,below in enumerate([.10,.40,.69]):
            pts=[]
            for s in np.linspace(-10.3,2.10+.10*side,45):
                z=KD.deck(s)-below;pts.append(p(side*(KD.width(s,z)+.018),s,z))
            o=beam('wale_%s_%d'%('p' if side>0 else 's',j),pts,.11,.15,'dark_oak','hull');collider(o)


def framing():
    spacing=.52*KD.sl
    for index,s in enumerate(np.arange(-10.0,2.18,spacing)):
        pts=[]
        # Main frame is an internal U timber, with no floating vertical feet.
        for side,values in [(-1,np.linspace(1,0,26)),(1,np.linspace(0,1,26)[1:])]:
            for v in values:
                w,z=KD.section(float(s),float(v))
                pts.append(p(side*max(.018,w-KD.plank-.065),float(s),z))
        o=beam('frame_%02d'%index,pts,.18*KD.sb,.12*KD.sb,'oak','fitting')
        o['guide']='chapter 03; source frame pitch 0.52m and scantlings .18 x .12m'
        collider(o)
        z=KD.z(float(KD.kd.zk(float(s)/KD.sl)))+.115
        fw=min(.65,max(.04,KD.width(float(s),z)-KD.plank-.07))
        o=beam('floor_timber_%02d'%index,[p(-fw,float(s),z),p(fw,float(s),z)],
               .18*KD.sb,.25,'oak','fitting');collider(o)
    # Last three exposed frames retain splintered foot sections beyond the shell.
    for i,s in enumerate([2.35,2.72,3.04]):
        for side in [-1,1]:
            pts=[]
            for v in np.linspace(0,.58-i*.10,18):
                w,z=KD.section(s,v);pts.append(p(side*max(.018,w-.12),s,z))
            o=beam('fractured_floor_%d_%s'%(i,'p' if side>0 else 's'),pts,.18*KD.sb,.12*KD.sb,'endgrain','fitting')
            collider(o)


def deck_planks():
    # Timber deck planks: guide ch.04 0.22m with real 8mm seams and staggered butts.
    plank=.22;seam=.008;deck_thick=.07
    hatch=(-1.10,1.10,-3.50,-.45)
    smin=-10.3;smax=1.95
    for k in range(-14,14):
        x0=k*plank+seam/2;x1=(k+1)*plank-seam/2
        xc=(x0+x1)/2
        starts=sorted(set([smin,smax,-3.5,-.45]+[smin+(k%4)*.51+j*3.20 for j in range(5)]))
        starts=[s for s in starts if smin<=s<=smax]
        for j,(s0,s1) in enumerate(zip(starts,starts[1:])):
            if s1-s0<.02:continue
            sc=(s0+s1)/2
            # Wide missing central boards are a genuine hatch, not a dark texture.
            if hatch[0]<xc<hatch[1] and hatch[2]<sc<hatch[3]:continue
            # Broken deck forward of hatch: retain side strips only.
            if sc>-.45 and abs(xc)<1.55:continue
            w=min(KD.width(s0,KD.deck(s0)),KD.width(s1,KD.deck(s1)))-.14
            if abs(xc)>w or x1>w or x0<-w:continue
            s0+=.004;s1-=.004
            # Each board follows the source sheer and camber, closed below.
            n=max(1,math.ceil((s1-s0)/.30));vs=[]
            for bottom in [False,True]:
                for x in [x0,x1]:
                    for m in range(n+1):
                        s=s0+(s1-s0)*m/n
                        z=KD.deck(s,x)-(deck_thick if bottom else 0)
                        vs.append(p(x,s,z))
            a=n+1;fs=[]
            for m in range(n):
                fs += [(m,m+1,a+m+1,a+m),(2*a+m,3*a+m,3*a+m+1,2*a+m+1),
                       (m,2*a+m,2*a+m+1,m+1),(a+m,a+m+1,3*a+m+1,3*a+m)]
            fs += [(0,a,3*a,2*a),(a-1,2*a-1,4*a-1,3*a-1)]
            o=mesh('deck_plank_%02d_%02d'%(k+14,j),vs,fs,'deck','surface','walk_surface')
            collider(o)
            DECK_RECTS.append((x0-.004,x1+.004,s0-.004,s1+.004))
            # The guide's 8mm seams contain caulking: they are not open holes.
            # Separate pitch strips sit 5mm below the wood without a fake deck
            # plane spanning the hatch or the broken bow.
            for axis in ['long','butt']:
                c=o.copy();c.data=o.data.copy();c.name='deck_caulk_%02d_%02d_%s'%(k+14,j,axis)
                c.data.name=c.name;c.data.materials.clear();c.data.materials.append(MATERIALS['dark_oak'])
                for v in c.data.vertices:
                    depth=KD.deck(-v.co.y,v.co.x)-v.co.z
                    if axis=='long':v.co.x=x1+(v.co.x-x0)/(x1-x0)*seam
                    else:v.co.y=-s1-seam+(v.co.y+s1)/(s1-s0)*seam
                    v.co.z=KD.deck(-v.co.y,v.co.x)-depth-.005
                for layer in list(c.data.uv_layers):c.data.uv_layers.remove(layer)
                recalc(c.data);uv_project(c)
                bpy.context.collection.objects.link(c);VIS.append(c);collider(c)
    # Coamings surround the retained hatch except its boarding side.
    for x in [-1.16,1.16]:
        spans=[(-3.5,-.45)] if x<0 else [(-3.5,-2.70),(-1.60,-.45)]
        for j,(a,b) in enumerate(spans):
            o=beam('hatch_coaming_%s_%d'%('p' if x>0 else 's',j),
                   [p(x,s,KD.deck(s,x)-.05) for s in np.linspace(a,b,12)],
                   .14,.20,'dark_oak','fitting');collider(o)
    # Real hold ceiling/floor boards leave central access and mast bypass clear.
    floor0=-7.8;floor1=2.10;sole=SPEC['sole']
    for k in range(-10,10):
        x0=k*plank+.004;x1=(k+1)*plank-.004
        # Fit the ceiling boards to the local inner hull. A single 3.5m-long
        # board was discarded at its narrow after end, leaving a missing floor
        # beside the ladder even where the hull was wide enough for it.
        mast_s=-SPEC['length']*.05
        floor_cuts=sorted(set([*np.linspace(floor0,floor1,23),mast_s-.24,mast_s+.24]))
        for j,(a,b) in enumerate(zip(floor_cuts,floor_cuts[1:])):
            if abs((x0+x1)/2)<.22 and mast_s-.24<(a+b)/2<mast_s+.24:
                continue  # Real opening around the mast, in both visuals and physics.
            w=min(KD.width(s,sole) for s in [a,(a+b)/2,b])-.20
            if x0<-w or x1>w:continue
            o=box('hold_plank_%02d_%d'%(k+10,j),p((x0+x1)/2,(a+b)/2,sole-.045),
                  (x1-x0,b-a-.008,.09),'deck','surface','walk_surface');collider(o)
            HOLD_RECTS.append((x0-.004,x1+.004,a,b))
            caulk=box('hold_caulk_%02d_%d_long'%(k+10,j),p(x1+.004,(a+b)/2,sole-.05),
                      (.008,b-a-.008,.09),'dark_oak','surface','walk_surface');collider(caulk)
            caulk=box('hold_caulk_%02d_%d_butt'%(k+10,j),p((x0+x1)/2,b,sole-.05),
                      (x1-x0,.008,.09),'dark_oak','surface','walk_surface');collider(caulk)
    # Deck beams under the intact afterdeck follow the camber; the forward beam
    # at the damaged end remains visibly broken rather than spanning the opening.
    for i,s in enumerate(np.arange(-9.5,-3.75,1.1733*KD.sl)):
        w=KD.width(float(s),KD.deck(float(s)))-.2
        pts=[p(x,float(s),KD.deck(float(s),x)-.18) for x in np.linspace(-w,w,15)]
        o=beam('deck_beam_%02d'%i,pts,.18,.22,'oak','fitting');collider(o)
    # Hatch sill at after edge is flush: no invented tall step blocks boarding.


def ladder():
    global LADDER
    s=-2.15;heel=math.radians(SPEC['heel_deg'])
    rotation=Matrix.Rotation(heel,4,'Y');inverse=rotation.inverted()
    # A salvage ladder is suspended plumb from a real hatch crossbeam. Baking
    # the same heel into ladder and ship would put upright hands >1m from it.
    anchors=[p(-.34,t,KD.deck(t,-.34)+.24) for t in np.linspace(-3.72,-.24,16)]
    support=beam('ladder_hanger_beam',anchors,.18,.18,'oak','fitting');collider(support)
    for j,t in enumerate([-3.72,-.24]):
        support=box('ladder_beam_seat_%d'%j,p(-.34,t,KD.deck(t,-.34)+.12),(.36,.26,.24),'dark_oak')
        collider(support)
    anchor=rotation@p(-.34,s,KD.deck(s,-.34)+.24)
    plane_x=anchor.x;shaft_x=plane_x+.52
    top_z=(rotation@p(1.30,s,KD.deck(s,1.30))).z
    bottom_z=(SPEC['sole']-math.sin(heel)*shaft_x)/math.cos(heel)
    rail_bottom=(SPEC['sole']-math.sin(heel)*plane_x)/math.cos(heel)
    world=lambda x,y,z:inverse@Vector((x,y,z))
    for side in [-1,1]:
        y=-s+side*.44
        rail=beam('ladder_stringer_%s'%('a' if side<0 else 'b'),
                  [world(plane_x,y,rail_bottom),world(plane_x,y,anchor.z)],
                  .065,.085,'oak','ladder');rail['climbable']=True;collider(rail)
        grip=beam('ladder_top_grip_%s'%('a' if side<0 else 'b'),
                  [world(plane_x,y,anchor.z),world(shaft_x+.90,y,anchor.z)],
                  .065,.065,'oak','ladder');grip['climbable']=True;collider(grip)
        post=beam('ladder_grip_post_%s'%('a' if side<0 else 'b'),
                  [world(shaft_x+.90,y,top_z),world(shaft_x+.90,y,anchor.z)],
                  .065,.065,'oak','ladder');post['climbable']=True;collider(post)
    n=math.ceil((anchor.z-rail_bottom)/.28)
    for j in range(n):
        z=rail_bottom+.12+j*(anchor.z-rail_bottom-.20)/max(1,n-1)
        rung=beam('ladder_rung_%02d'%j,[world(plane_x,-s-.44,z),world(plane_x,-s+.44,z)],
                  .065,.065,'oak','ladder');rung['climbable']=True;collider(rung)
    # Short boarding tread is physically supported by the opened coaming side.
    platform=box('ladder_boarding_tread',Vector((shaft_x+.685,-s,top_z-.06)),(.53,1.02,.12),'deck','surface','walk_surface')
    # box() above used world coordinates; convert it into the unheeled authoring
    # system so the common final transform will reproduce a level platform.
    platform.data.transform(inverse);recalc(platform.data);collider(platform)
    LADDER={'approach':world(shaft_x+.80,-s,top_z),'top':world(shaft_x+.46,-s,top_z),
            'shaft_top':world(shaft_x,-s,top_z),'bottom':world(shaft_x,-s,bottom_z),
            'body_offset_m':.52,'max_handhold_offset_m':math.hypot(.52,.44)}
    marker('ladder_top',LADDER['top'],kind='climb_endpoint')
    marker('ladder_bottom',LADDER['bottom'],kind='climb_endpoint')


def equipment():
    s=-SPEC['length']*.05
    lower_mast=(SPEC['length']+SPEC['beam'])/2
    radius=lower_mast/72
    mast=tapered('broken_main_mast',p(0,s,-.40),p(0,s,KD.deck(s)+1.12),radius,radius*.86,
                 'oak','spar','solid',16,True);collider(mast)
    mast['guide']='ch.05 Steel diameter = lower-mast length /36; retained stump only'
    # Collar is supported by the deck edge/mast partners and keelson, not floating.
    for side in [-1,1]:
        z=KD.deck(s,side*.26)
        o=box('mast_partner_%s'%('p' if side>0 else 's'),p(side*.29,s,z-.03),(.18,.8,.12),'dark_oak');collider(o)
    # Fallen spar lies on afterdeck cradles and the exposed frame at its forward end.
    spar_points=[p(-2.17,s,KD.deck(s,-2.17)+.20) for s in [-6.2,-4.5,-2.0,1.0]]
    spar=tapered('fallen_yard',spar_points[0],spar_points[-1],.13,.085,'dark_oak','spar','solid',12,True)
    collider(spar)
    for i,s in enumerate([-5.8,-4.0]):
        z=KD.deck(s,-2.17)
        o=box('spar_rest_%d'%i,p(-2.17,s,z+.035),(.38,.22,.07),'oak');collider(o)
    # Salvage cargo is behind/aside the certified route, never across it.
    for i,(x,s) in enumerate([(-.48,-4.0),(.48,-4.0)]):
        a=p(x,s,SPEC['sole']);b=p(x,s,SPEC['sole']+.72)
        o=tapered('salvage_cask_%d'%i,a,b,.27,.26,'oak','fitting','solid',16);collider(o)
        for j,z in enumerate([.12,.59]):
            o=tapered('cask_hoop_%d_%d'%(i,j),p(x,s,SPEC['sole']+z),p(x,s,SPEC['sole']+z+.035),
                      .279,.279,'iron','fitting','none',16)
    chest=box('salvage_chest',p(1.15,.95,SPEC['sole']+.27),(.65,.76,.54),'dark_oak');collider(chest)
    lid=box('salvage_chest_lid',p(1.15,.95,SPEC['sole']+.575),(.69,.80,.07),'oak');collider(lid)
    lid['interaction']='hinge';marker('chest_hinge',p(1.15,1.34,SPEC['sole']+.54),kind='hinge')
    # A closed book and compass are separate game objects with pickup anchors.
    bd=KD.deck(-6.6,.2)
    book=box('salvage_book',p(.20,-6.6,bd+.04),(.22,.31,.07),'leather',physics='none')
    box('book_pages',p(.20,-6.6,bd+.047),(.20,.285,.042),'paper',physics='none')
    marker('find_book',p(.20,-6.6,bd+.15),kind='pickup',object='salvage_book')
    z=SPEC['sole']+.611
    tapered('salvage_compass',p(1.15,.95,z),p(1.15,.95,z+.025),.095,.095,'brass',physics='none',n=24)
    tapered('compass_glass',p(1.15,.95,z+.026),p(1.15,.95,z+.030),.081,.081,'glass',physics='none',n=24)
    needle=box('compass_needle',p(1.15,.95,z+.031),(.012,.13,.008),'iron',physics='none')
    marker('find_compass',p(1.15,.95,z+.12),kind='pickup',object='salvage_compass')


def export(objects,path):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.hide_set(False);o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,
                              export_yup=True,export_extras=True,export_animations=False,
                              export_materials='EXPORT',export_image_format='AUTO',
                              export_texcoords=path.name!='collision.glb')


def merge_colliders():
    """Continuous closed hull walls/deck slabs replace per-board collider boxes.

    Joining touching closed boxes is not a manifold union. These meshes instead
    have shared boundary vertices and NO internal faces between neighbouring cells.
    """
    replaced=('col_hull_strake_','col_transom_strake_','col_deck_plank_',
              'col_deck_caulk_','col_hold_plank_','col_hold_caulk_')
    for o in list(COL):
        if o.name.startswith(replaced):
            COL.remove(o);bpy.data.objects.remove(o,do_unlink=True)
    def add(name,vs,fs,kind='hull',physics='solid'):
        o=mesh(name,vs,fs,'collision',kind,physics)
        VIS.remove(o);o['asset_role']='collision';o.hide_render=True
        o.matrix_world=HEEL;COL.append(o);return o
    levels=18;n=46;m=n+1
    for side in [-1,1]:
        vs=[]
        for inner in [False,True]:
            for r in range(levels+1):
                v=r/levels;start=KD.aft(v);end=2.35+.23*math.sin(r*2.3)+.08*side
                for j in range(m):
                    s=start+(end-start)*j/n;w,z=KD.section(s,v)
                    vs.append(p(side*max(.015,w-(KD.plank if inner else 0)),s,z))
        layer=(levels+1)*m;fs=[]
        for r in range(levels):
            for j in range(n):
                a=r*m+j;b=a+1;c=a+m+1;d=a+m
                fs += [(a,b,c,d),(layer+a,layer+d,layer+c,layer+b)]
            for j in [0,n]:
                a=r*m+j;b=(r+1)*m+j
                fs.append((a,b,layer+b,layer+a))
        for r in [0,levels]:
            for j in range(n):
                a=r*m+j;b=a+1;fs.append((a,layer+a,layer+b,b))
        add('col_hull_%s'%('port' if side>0 else 'starboard'),vs,fs)
    vs=[]
    for r in range(levels+1):
        v=r/levels;s=KD.aft(v);w,z=KD.section(s,v);t=KD.plank
        vs += [p(-w,s,z),p(w,s,z),p(-w,s+t,z),p(w,s+t,z)]
    fs=[]
    for r in range(levels):
        a=4*r;b=a+4
        fs += [(a,a+1,b+1,b),(a+2,b+2,b+3,a+3),(a,b,b+2,a+2),
               (a+1,a+3,b+3,b+1)]
    fs += [(0,2,3,1),tuple(4*levels+j for j in [0,1,3,2])]
    add('col_transom',vs,fs)
    for name,rects,top,thick in [('deck',DECK_RECTS,KD.deck,.07),
                                ('hold',HOLD_RECTS,lambda s,x:SPEC['sole'],.09)]:
        xs=sorted(set(round(v,9) for rect in rects for v in rect[:2]))
        ss=sorted(set(round(v,9) for rect in rects for v in rect[2:]))
        cells=set()
        for i,(xa,xb) in enumerate(zip(xs,xs[1:])):
            for j,(sa,sb) in enumerate(zip(ss,ss[1:])):
                x=(xa+xb)/2;s=(sa+sb)/2
                if any(a-1e-7<x<b+1e-7 and c-1e-7<s<d+1e-7 for a,b,c,d in rects):cells.add((i,j))
        vs=[];fs=[];cache={}
        def vi(i,j,bottom=False):
            key=(i,j,bottom)
            if key not in cache:
                cache[key]=len(vs);vs.append(p(xs[i],ss[j],top(ss[j],xs[i])-(thick if bottom else 0)))
            return cache[key]
        for i,j in sorted(cells):
            a,b,c,d=[vi(i+x,j+y) for x,y in [(0,0),(1,0),(1,1),(0,1)]]
            aa,bb,cc,dd=[vi(i+x,j+y,True) for x,y in [(0,0),(1,0),(1,1),(0,1)]]
            fs += [(a,b,c,d),(aa,dd,cc,bb)]
            if (i-1,j) not in cells:fs.append((a,d,dd,aa))
            if (i+1,j) not in cells:fs.append((b,bb,cc,c))
            if (i,j-1) not in cells:fs.append((a,aa,bb,b))
            if (i,j+1) not in cells:fs.append((d,c,cc,dd))
        add('col_%s_walk_slab'%name,vs,fs,'surface','walk_surface')


def lod(level):
    ratio=.50 if level==1 else .18
    copies=[];materials={};images={}
    for source in {m for o in VIS for m in o.data.materials if m}:
        m=source.copy();m.name='lod%d_%s'%(level,source.name)
        if m.use_nodes:
            for node in m.node_tree.nodes:
                if node.type!='TEX_IMAGE' or not node.image:continue
                image=node.image
                if image not in images:
                    im=image.copy();im.name='lod%d_%s'%(level,image.name)
                    target=1024 if level==1 else 512
                    scale=min(1,target/max(im.size))
                    im.scale(max(1,round(im.size[0]*scale)),max(1,round(im.size[1]*scale)))
                    im.pack();images[image]=im
                node.image=images[image]
        materials[source]=m
    for i,o in enumerate(VIS):
        if level==2 and (o.name.startswith(('cask_hoop','compass_','book_','spar_rest')) or
                        (o.name.startswith('frame_') and int(o.name.split('_')[1])%2)):
            continue
        c=o.copy();c.data=o.data.copy();c.name='lod%d_%s'%(level,o.name);c.data.name=c.name
        for j,m in enumerate(list(c.data.materials)):
            if m in materials:c.data.materials[j]=materials[m]
        bpy.context.collection.objects.link(c);copies.append(c)
        if len(c.data.polygons)>24:
            m=c.modifiers.new('reduce','DECIMATE');m.ratio=ratio
            bpy.context.view_layer.objects.active=c
            bpy.ops.object.modifier_apply(modifier=m.name)
    path=OUT/'model'/('ship_lod%d.glb'%level);export(copies,path)
    count=sum(len(o.data.loop_triangles) for o in copies)
    for o in copies:bpy.data.objects.remove(o,do_unlink=True)
    for m in materials.values():bpy.data.materials.remove(m)
    for im in images.values():bpy.data.images.remove(im)
    return count


def render():
    for o in COL:o.hide_render=True
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=32
    scene.render.resolution_x=1200;scene.render.resolution_y=900;scene.render.resolution_percentage=100
    scene.view_settings.view_transform='AgX'
    if scene.world is None:scene.world=bpy.data.worlds.new('wreck_world')
    scene.world.color=(.32,.32,.32)
    bounds=[o.matrix_world@Vector(q) for o in VIS for q in o.bound_box]
    lo=Vector(tuple(min(q[i] for q in bounds) for i in range(3)))
    hi=Vector(tuple(max(q[i] for q in bounds) for i in range(3)))
    center=(lo+hi)/2
    for i,(pos,power,size) in enumerate([((12,-12,18),5000,12),((-8,8,12),3500,10)]):
        bpy.ops.object.light_add(type='AREA',location=center+Vector(pos))
        o=bpy.context.object;o.name='presentation_light_%d'%i;o['asset_role']='presentation'
        o.data.energy=power;o.data.size=size
        o.rotation_euler=(center-o.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.object.camera_add();cam=bpy.context.object;cam.name='presentation_camera';cam['asset_role']='presentation'
    scene.camera=cam;cam.data.type='ORTHO'
    for name,delta,scale in [('hero',(15,-22,13),1.12),('deck',(7,-8,22),1.07),('stern',(15,24,10),1.12)]:
        cam.location=center+Vector(delta)
        cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler()
        bpy.context.view_layer.update();coords=[cam.matrix_world.inverted()@q for q in bounds]
        extent_x=max(q.x for q in coords)-min(q.x for q in coords)
        extent_y=max(q.y for q in coords)-min(q.y for q in coords)
        cam.data.ortho_scale=max(extent_x,extent_y*scene.render.resolution_x/scene.render.resolution_y)*scale
        scene.render.image_settings.file_format='JPEG';scene.render.image_settings.quality=90
        scene.render.filepath=str(OUT/'previews'/(name+'.jpg'));bpy.ops.render.render(write_still=True)
    cam.data.type='PERSP';cam.data.lens=22
    cam.location=HEEL@p(-.6,2.35,.85)+Vector((0,0,.70))
    target=HEEL@p(-.2,-3.7,1.3)
    cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
    scene.render.filepath=str(OUT/'previews'/'interior.jpg');bpy.ops.render.render(write_still=True)


def build(spec,out,no_render=False):
    global SPEC,OUT,KD,HEEL
    VIS.clear();COL.clear();MARKERS.clear();MATERIALS.clear();DECK_RECTS.clear();HOLD_RECTS.clear()
    SPEC=spec;OUT=Path(out).resolve();OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'model').mkdir(exist_ok=True);(OUT/'previews').mkdir(exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=1
    KD=Lines(spec);make_materials()
    shell();framing();deck_planks();ladder();equipment()
    marker('asset_origin',Vector((0,0,0)),kind='origin',vessel_id='wreck')
    marker('original_bow_reference',p(0,spec['length']/2,KD.z(0)),kind='bow_reference')
    marker('shore_connection',p(-.8,2.3,spec['sole']),kind='external_connection')
    HEEL=Matrix.Rotation(math.radians(spec.get('heel_deg',0)),4,'Y')
    for o in VIS+COL+MARKERS:o.matrix_world=HEEL@o.matrix_world
    merge_colliders()
    # Navigation feet in ship coordinates are baked with exactly the same heel.
    def route(name,coords,mode='walk'):
        return {'name':name,'mode':mode,'points':[gltf(HEEL@p(x,s,h)) for x,s,h in coords]}
    def route_points(name,points,mode='walk'):
        return {'name':name,'mode':mode,'points':[gltf(HEEL@Vector(q)) for q in points]}
    d=lambda s,x=0:KD.deck(s,x)
    routes=[
        route_points('aft_deck_to_hatch',[p(.11,-8,d(-8,.11)),p(.11,-4.55,d(-4.55,.11)),
                     p(1.98,-4.55,d(-4.55,1.98)),p(1.98,-2.15,d(-2.15,1.98)),LADDER['approach'],LADDER['top']]),
        route_points('hatch_to_hold',[LADDER['top'],LADDER['shaft_top'],LADDER['bottom']], 'climb'),
        route_points('hold_mast_bypass',[LADDER['bottom'],p(LADDER['bottom'].x,-3.15,spec['sole']),p(-.80,-3.15,spec['sole']),
                                  p(-.80,.05,spec['sole']),p(.10,.05,spec['sole']),p(.10,1.25,spec['sole'])]),
        route('book_station',[(.11,-7.5,d(-7.5,.11)),(.2,-6.6,d(-6.6,.2))]),
    ]
    nav={'schema':2,'units':'metres','axes':'glTF X port, Y up, Z bow',
         'player':{'radius':.38,'height':1.85,'max_slope_deg':35},'routes':routes,
         'source_commit':spec['source_commit'],
         'climb_controller_required':True,
         'climbs':[{'route':'hatch_to_hold','top':'ladder_top','bottom':'ladder_bottom',
                    'ladder':'ladder_stringer_a','body_offset_m':LADDER['body_offset_m'],
                    'max_handhold_offset_m':LADDER['max_handhold_offset_m']}],
         'limitations':['Requires world-upright climbing controller; ladder is not a 35 degree walking slope.',
                        'Shore/terrain connection is an engine placement contract, not included terrain.']}
    write('navigation.json',nav)
    write('spec.json',spec)
    report={'schema':2,'vessel':'wreck','reference_commit':'2e6f7e922e95396722376d42f3e2e0a12256029e',
       'source_files':{'blender/'+n:hashlib.sha256((SOURCE/n).read_bytes()).hexdigest() for n in ['parametry.py','rzedne.py','narzedzia_math.py']},
       'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
       'source_paths':spec['source_paths'],'game_source_commit':spec['source_commit'],
       'construction':{'offset_method':'Original rzedne.Kadlub PCHIP evaluation of PR.RZEDNE; no generic hull function',
          'length_scale':KD.sl,'breadth_scale':KD.sb,'vertical_scale':KD.sz,'stranded_z_offset_m':KD.zoff,
          'nominal_original_length_m':22,'nominal_beam_m':6,'retained_hull':'aft and midbody to staggered fracture at s~+2.35m',
          'planking_thickness_m':KD.plank,'frame_pitch_m':.52*KD.sl,'frame_section_m':[.18*KD.sb,.12*KD.sb],
          'deck_plank_width_m':.22,'deck_seam_m':.008,'deck_thickness_m':.07,
          'mast_lower_length_rule_m':(22+6)/2,'retained_mast_diameter_m':(22+6)/72,
          'heel_rad':math.radians(spec['heel_deg']),'heel_baked':True,'world_gravity':[0,-1,0]},
       'guide_matrix':{'01':'Merchant hull family of the c.1710 reference; wreck damage and salvage state are game inference.',
          '02':'Exact source offset-family evaluator; length/breadth transform and stranded datum recorded.',
          '03':'Closed strakes with capped splintered ends; separate keel, keelson, inner frames and wales.',
          '04':'Source sheer/camber, discrete deck planking and genuine absent boards around hatch.',
          '05':'Broken mainmast diameter from Steel M=(L+B)/2 and D=M/36; no surviving rig claimed.',
          '06':'N/A: no standing sail rig survives. Broken spar retained as separate timber.',
          '07':'N/A: no operable sailing rig or running rigging survives on this wreck.',
          '08':'No cloth to audit; separate closed timber fragments, source-derived PBR textures and grain-aligned UVs.',
          '09':'Separate plumb suspended ladder on real supports, casks, chest, book and compass anchors; accessible salvage hold.',
          '10':'Reproducible Blender script using original reference PCHIP module and numeric data.',
          '11':'CAD/paper artefact not requested; underlying reference stations and numeric transforms retained for reproduction.',
          '12':'Reference hull length/breadth/depth parameters are transformed before constructing new planks, frames and decks.',
          '13':'Closed-solid, normals, indices, UV, material, source/GLB and walking audits required on actual exports.',
          '14':'Separate physics geometry, glTF axes/metres, interaction anchors, climb endpoints, LODs.'},
       'deviations':["The source guide does not specify this wreck; damage, hold, salvage and ladder layout are explicit game inference.",
          "The source model's broad flat transom family is retained; no historical identity for the wreck is asserted.",
          "The game's deck/sole/draft values are mapped to a stranded vertical datum; they are not a new hydrostatic floating draft.",
          "No captain cabin survives; no fabricated room is added.",
          "Hull fairness is inherited from the documented source offset family, including its disclosed limitations below the aft waterline.",
          "Procedural MIT guide textures with colour-weathering transform; not photographic CC0 texture set."],
       'axes':{'bow_gltf':[0,0,1],'up_gltf':[0,1,0],'heel_baked':True},
       'intentional_joints':['Frames sit against inner planking; keelson meets floor frames.',
           'Wales overlap the plank shell as fastened external timber.',
           'Mast partners surround the retained central stump; stump is supported by keelson.',
           'Fallen spar rests on two afterdeck cradles and the forward retained framing.',
           'Ladder rungs join stringers; stringers are fastened to the hatch side.'],
       'intended_joints':[{'a':'frame_*','b':'hull_strake_*','reason':'Frames are fitted against inner planking.'},
           {'a':'frame_*','b':'fractured_keel','reason':'The U floor/futtock assembly seats into the keel rabbet, a housed structural timber joint.'},
           {'a':'floor_timber_*','b':'fractured_keel','reason':'Floor timbers are seated over the keel rabbet.'},
           {'a':'floor_timber_*','b':'keelson','reason':'The keelson is fastened directly above the transverse floor timbers.'},
           {'a':'floor_timber_*','b':'frame_*','reason':'Transverse floors join the lower futtocks of each frame.'},
           {'a':'floor_timber_*','b':'hull_strake_*','reason':'Floor-timber heads are housed against the inner bottom planking.'},
           {'a':'fractured_floor_*','b':'hull_strake_*','reason':'Retained floor remnants remain fastened to their damaged shell planking.'},
           {'a':'fractured_floor_*','b':'fractured_keel','reason':'Retained floor remnants are seated in the keel rabbet.'},
           {'a':'keelson','b':'hull_strake_*','reason':'Narrow after deadwood and inner bottom planking enclose the keelson seating.'},
           {'a':'fractured_keel','b':'hull_strake_*','reason':'The first planking strake lands in the keel rabbet.'},
           {'a':'frame_*','b':'keelson','reason':'Floor timbers are fastened to the keelson.'},
           {'a':'keelson','b':'broken_main_mast','reason':'The retained mast heel is housed in its structural step on the keelson.'},
           {'a':'frame_*','b':'hold_plank_*','reason':'Hold ceiling boards are fastened and locally housed over the internal frame faces.'},
           {'a':'frame_*','b':'hold_caulk_*','reason':'Ceiling-board caulking is housed along the same frame seating as its planks.'},
           {'a':'deck_beam_*','b':'deck_plank_*','reason':'Deck planks bed directly on the cambered deck beams.'},
           {'a':'deck_beam_*','b':'deck_caulk_*','reason':'Caulked deck seams extend down to their supporting deck beams.'},
           {'a':'hatch_coaming_*','b':'deck_plank_*','reason':'Hatch coamings are housed into and fastened to the surrounding deck timber.'},
           {'a':'hatch_coaming_*','b':'deck_caulk_*','reason':'Caulking seals the coaming-to-deck seating joint.'},
           {'a':'wale_*','b':'hull_strake_*','reason':'External wales overlap their supporting planking.'},
           {'a':'mast_partner_*','b':'broken_main_mast','reason':'Partners secure the mast stump at deck level.'},
           {'a':'ladder_*','b':'ladder_*','reason':'Ladder rungs, stringers, handrails and boarding tread are fastened joints.'},
           {'a':'ladder_stringer_*','b':'hold_plank_*','reason':'The plumb salvage ladder feet are seated into shallow mortises in the hold ceiling boards.'},
           {'a':'ladder_beam_seat_*','b':'deck_*','reason':'Hanger beam seats rest on and are fastened to intact deck timber.'},
           {'a':'ladder_boarding_tread','b':'deck_plank_*','reason':'The outer end of the salvage boarding tread is housed into the sloping deck edge.'},
           {'a':'ladder_boarding_tread','b':'deck_caulk_*','reason':'Caulking seals the housed boarding-tread seating at the sloping deck edge.'},
           {'a':'deck_caulk_*','b':'deck_plank_*','reason':'Pitch caulking fills the guide-specified 8mm plank seams.'},
           {'a':'hold_caulk_*','b':'hold_plank_*','reason':'Pitch caulking fills the guide-specified plank seams.'}],
       'outputs':{'visual_objects':len(VIS),'collision_objects':len(COL)}}
    write('design.json',report)
    for im in bpy.data.images:
        if im.source=='FILE' and not im.packed_file:im.pack()
    export(VIS+MARKERS,OUT/'model'/'ship.glb')
    export(COL,OUT/'model'/'collision.glb')
    lod(1);lod(2)
    for o in COL:o.hide_set(True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'model'/'ship.blend'),compress=True)
    if not no_render:render()
    print('WRECK_COMPLETE',OUT,flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('spec');ap.add_argument('--out',required=True)
    ap.add_argument('--no-render',action='store_true',help='Skip source beauty shots; exported GLB review is a separate step')
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    build(json.loads(Path(args.spec).read_text(encoding='utf-8')),args.out,args.no_render)
