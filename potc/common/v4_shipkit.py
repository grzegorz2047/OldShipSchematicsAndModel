"""Additive, spec-driven wooden-ship reconstructions for ordinary POTC 2003 types.
Dimensions and physical silhouettes are authored estimates, not recovered game meshes.
Blender: --python v4_shipkit.py -- SPEC.json --out DIRECTORY
"""
import argparse,hashlib,json,math,sys,re
from pathlib import Path
import bpy,bmesh
from mathutils import Vector
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(ROOT/'sailertales/common')]
from v2_boats import physical_uv
from v2_materials import upgrade_scene


def safe_name(name):return re.sub('[^a-z0-9_]','_',str(name).lower().replace('-','minus_'))

def p(x,s,z):return Vector((x,-s,z))
def _lin(v):return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4

def rgba(value):
    if isinstance(value,str):
        value=value.lstrip('#');return [_lin(int(value[i:i+2],16)/255) for i in(0,2,4)]+[1.]
    return list(value[:3])+[value[3] if len(value)>3 else 1.]


def _curve(rows,x,index):
    """Monotone cubic interpolation of authored offsets, without negative overshoot."""
    xs=[r[0] for r in rows];ys=[r[index] for r in rows]
    if x<=xs[0]:return ys[0]
    if x>=xs[-1]:return ys[-1]
    ds=[(ys[i+1]-ys[i])/(xs[i+1]-xs[i]) for i in range(len(xs)-1)]
    slopes=[ds[0]]+[0 if ds[i-1]*ds[i]<=0 else 2/(1/ds[i-1]+1/ds[i]) for i in range(1,len(xs)-1)]+[ds[-1]]
    i=next(i for i in range(len(xs)-1) if xs[i]<=x<=xs[i+1]);h=xs[i+1]-xs[i];t=(x-xs[i])/h
    return (2*t**3-3*t*t+1)*ys[i]+(t**3-2*t*t+t)*h*slopes[i]+(-2*t**3+3*t*t)*ys[i+1]+(t**3-t*t)*h*slopes[i+1]


class Context:
    p=staticmethod(p);P=staticmethod(p)
    def __init__(self,spec):
        self.spec=spec;self.L=float(spec['length']);self.B=float(spec['beam']);self.draft=float(spec['draft']);self.freeboard=float(spec['freeboard'])
        self.vis=[];self.col=[];self.markers=[];self.joints=[];self.deck_nodes=[];self.hull_nodes=[];self.gun_nodes=[];self.materials={}
        self.hull=spec.get('hull',{});self.profile=self.hull.get('profile',[[-.5,.3,.5,.5],[-.35,.88,.08,.15],[0,1,0,0],[.3,.78,.1,.15],[.5,.025,1.0,.8]])
        self.profile=sorted(self.profile);self.stern_extension=self.B*.12 if self.hull.get('stern_style')=='round' else 0
        self.castles=[dict(v) for v in self.hull.get('castles',[])]
        for key in('quarterdeck','forecastle'):
            if self.hull.get(key):self.castles.append(dict(self.hull[key]))
        self.ports=[]
        for row,definition in enumerate(spec.get('guns',{}).get('rows',[])):
            n=int(definition['pairs']);a=definition.get('from',-.34)*self.L;b=definition.get('to',.33)*self.L
            pitch=(b-a)/max(n-1,1);w=float(definition.get('port_width_m',min(1.0,max(.5,pitch*.48))))
            for k in range(n):
                s=(a+b)/2 if n==1 else a+(b-a)*k/(n-1)
                self.ports.append({'s':s,'z':float(definition['z_m'])+(_curve(self.profile,s/self.L,3) if definition.get('follow_sheer',True) else 0),'w':w,'h':float(definition.get('port_height_m',.85)), 'row':row,'index':k})
        for role,alias in [('wood','wood'),('deck','deck_planking'),('spar','wood_dark'),('paintHull','side_oiled_oak'),('paintTrim','wood'),('rope','rope_untarred'),('canvas','canvas'),('iron','iron'),('seam','wood_black')]:
            m=bpy.data.materials.new(alias);m.diffuse_color=(.5,.3,.15,1);m['uv_tile_m']=[2.4,2.4] if role=='canvas' else [1.,.5] if role=='rope' else [2.,2.]
            self.materials[role]=m
        self.materials['collision']=bpy.data.materials.new('collision_debug')
    def width(self,s,z=None):
        factor=max(.012,_curve(self.profile,s/self.L,1));half=self.B/2*factor
        if self.stern_extension and s<-self.L/2:half*=math.sqrt(max(0,1-((s+self.L/2)/self.stern_extension)**2))
        if z is None:return max(.04,half*float(self.hull.get('deck_beam_factor',1.)))
        bottom=-self.draft+_curve(self.profile,s/self.L,2);deck=self.main_height(s)
        t=max(0,min(1,(z-bottom)/max(deck-bottom,.1)))
        section=math.sin(t*math.pi/2)**float(self.hull.get('section_power',.7))
        tumble=1-(1-float(self.hull.get('deck_beam_factor',1.)))*max(0,(t-.65)/.35)
        return max(.035,half*section*tumble)
    def main_height(self,s):return self.freeboard+_curve(self.profile,s/self.L,3)
    def deck_height(self,s):
        return self.main_height(s)+max([0.]+[float(c['height_m']) for c in self.castles if c['from']*self.L-1e-6<=s<=c['to']*self.L+1e-6])
    deck_z=deck_height
    def mesh(self,name,verts,faces,material='wood',kind='fitting',grain_path=None,collision=False,extras=None):
        name=safe_name(name)
        me=bpy.data.meshes.new(name+'_mesh');me.from_pydata(verts,[],faces);me.update()
        obj=bpy.data.objects.new(name,me);bpy.context.scene.collection.objects.link(obj)
        roles=[material] if isinstance(material,str) else material
        for role in roles:me.materials.append(self.materials[role])
        obj['kind']=kind;obj['asset_role']='visual';obj['material_roles_json']=json.dumps(roles)
        physical_uv(obj,Vector((0,-1,0)),grain_path)
        if roles==['rope']:
            for q in me.uv_layers.active.data:q.uv.x*=2;q.uv.y*=4
        elif roles==['canvas']:
            for q in me.uv_layers.active.data:q.uv*=2/2.4
        if extras:
            for k,v in extras.items():obj[k]=v
        self.vis.append(obj)
        if collision:self.collider(obj)
        return obj
    def collider(self,obj):
        col=obj.copy();col.data=obj.data.copy();col.name='col_'+obj.name;bpy.context.scene.collection.objects.link(col)
        col['asset_role']='collision';col['visual_source']=obj.name;col.hide_render=True
        col.data.materials.clear();col.data.materials.append(self.materials['collision']);self.col.append(col);return col
    def joint(self,a,b,reason):
        a=a.name if hasattr(a,'name') else str(a);b=b.name if hasattr(b,'name') else str(b)
        if a==b:return
        row={'a':a,'b':b,'reason':reason}
        if not any({r['a'],r['b']}=={a,b} for r in self.joints):self.joints.append(row)
    def marker(self,name,point,extras=None,**kw):
        name=safe_name(name)
        obj=bpy.data.objects.new(name,None);obj.location=point;bpy.context.scene.collection.objects.link(obj);obj['asset_role']='marker'
        for k,v in dict(extras or {},**kw).items():obj[k]=v
        self.markers.append(obj);return obj
    def beam(self,name,a,b,width,depth,material='wood',kind='fitting',collision=False):
        a,b=Vector(a),Vector(b);direction=(b-a).normalized();u=direction.cross(Vector((0,0,1)))
        if u.length<.01:u=direction.cross(Vector((1,0,0)))
        u.normalize();v=direction.cross(u).normalized();verts=[]
        for q in(a,b):verts.extend([q-u*width/2-v*depth/2,q+u*width/2-v*depth/2,q+u*width/2+v*depth/2,q-u*width/2+v*depth/2])
        faces=[(3,2,1,0),(4,5,6,7)]+[(j,(j+1)%4,(j+1)%4+4,j+4) for j in range(4)]
        return self.mesh(name,verts,faces,material,kind,[a,b],collision,{'preserve_solid_lod':True} if width<.08 or depth<.08 else None)
    def box(self,name,center,size,material='wood',kind='fitting',collision=False,grain=None):
        c=Vector(center);x,y,z=[v/2 for v in size];verts=[c+Vector((i*x,j*y,k*z)) for k in(-1,1) for j in(-1,1) for i in(-1,1)]
        axis=max(range(3),key=lambda i:float(size[i]));direction=Vector(tuple(1 if i==axis else 0 for i in range(3))) if grain is None else Vector(grain)
        return self.mesh(name,verts,[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)],material,kind,grain_path=[c-direction,c+direction],collision=collision)
    def tube(self,name,points,radius,material='rope',kind='rope',sides=6,collision=False,extras=None):
        points=list(map(Vector,points));cyclic=len(points)>3 and (points[0]-points[-1]).length<1e-6
        radii=list(radius) if isinstance(radius,(list,tuple)) else [float(radius)]*len(points)
        if cyclic:points=points[:-1];radii=radii[:-1]
        verts=[];faces=[];previous=None
        for i,q in enumerate(points):
            t=(points[(i+1)%len(points)]-points[(i-1)%len(points)]).normalized() if cyclic else (points[min(i+1,len(points)-1)]-points[max(0,i-1)]).normalized()
            u=previous-t*previous.dot(t) if previous is not None else t.cross(Vector((0,0,1)))
            if u.length<.01:u=t.cross(Vector((1,0,0)))
            u.normalize();v=t.cross(u);previous=u
            verts.extend(q+radii[i]*(math.cos(j*2*math.pi/sides)*u+math.sin(j*2*math.pi/sides)*v) for j in range(sides))
        for i in range(len(points) if cyclic else len(points)-1):
            nxt=(i+1)%len(points)
            for j in range(sides):faces.append((i*sides+j,i*sides+(j+1)%sides,nxt*sides+(j+1)%sides,nxt*sides+j))
        if not cyclic:faces+=[tuple(reversed(range(sides))),tuple((len(points)-1)*sides+j for j in range(sides))]
        info={'preserve_solid_lod':True,'diameter_m':2*max(radii),'rope_path_json':json.dumps({'axes':'blender_world','points':[list(q) for q in points]})}
        info.update(extras or {})
        return self.mesh(name,verts,faces,material,kind,points,collision,info)


def _thick_surface(ctx,name,vertices,faces,side,material='paintHull',kind='hull',thickness=.12):
    """Double a connected perforated skin and cap every real boundary loop."""
    edges={}
    for f in faces:
        for a,b in zip(f,f[1:]+f[:1]):edges.setdefault(tuple(sorted((a,b))),[]).append((a,b))
    inner=[]
    for q in vertices:
        q=Vector(q);bottom=-ctx.draft+_curve(ctx.profile,-q.y/ctx.L,2);t=max(0,min(1,(q.z-bottom)/max(ctx.main_height(-q.y)-bottom,.1)))
        inner.append(Vector((side*max(.01,side*q.x-thickness*math.sin(t*math.pi/2)),q.y,q.z+thickness*math.cos(t*math.pi/2))))
    n=len(vertices);allfaces=list(faces)+[tuple(n+i for i in reversed(f)) for f in faces]
    for linked in edges.values():
        if len(linked)==1:
            a,b=linked[0];allfaces.append((a,b,b+n,a+n))
    return ctx.mesh(name,vertices+inner,allfaces,material,kind)


def hull(ctx):
    h=ctx.hull;N=max(20,int(h.get('longitudinal_stations',48)));draft=ctx.draft
    ss={-ctx.L/2+ctx.L*i/N for i in range(N+1)}
    for port in ctx.ports:ss.update((port['s']-port['w']/2,port['s']+port['w']/2))
    ss=sorted(ss);topmax=max(ctx.deck_height(s) for s in ss)+float(h.get('bulwark_height',.8))
    zz={-draft+(topmax+draft)*i/max(18,int(h.get('plank_rows',24))) for i in range(max(18,int(h.get('plank_rows',24)))+1)}
    for port in ctx.ports:zz.update((port['z']-port['h']/2,port['z']+port['h']/2))
    zz=sorted(zz)
    for side,label in[(1,'port'),(-1,'starboard')]:
        verts=[];faces=[];lookup={}
        def vertex(i,z):
            s=ss[i];bottom=-draft+_curve(ctx.profile,s/ctx.L,2);top=ctx.deck_height(s)+float(h.get('bulwark_height',.8))
            z=max(bottom,min(top,z));key=(i,round(z,7))
            if key not in lookup:lookup[key]=len(verts);verts.append(p(side*ctx.width(s,z),s,z))
            return lookup[key]
        for i in range(len(ss)-1):
            s=(ss[i]+ss[i+1])/2;bottom=-draft+_curve(ctx.profile,s/ctx.L,2);top=ctx.deck_height(s)+float(h.get('bulwark_height',.8))
            for j in range(len(zz)-1):
                z=(zz[j]+zz[j+1])/2
                # Clip every intersecting grid cell, including the triangular
                # wedge when only one station lies below the sheer. A midpoint
                # test drops that wedge and makes a four-face diagonal pinch
                # where a rectangular gunport corner meets the rising rail.
                bottoms=[-draft+_curve(ctx.profile,ss[k]/ctx.L,2) for k in(i,i+1)]
                tops=[ctx.deck_height(ss[k])+float(h.get('bulwark_height',.8)) for k in(i,i+1)]
                if zz[j+1]<=min(bottoms)+1e-9 or zz[j]>=max(tops)-1e-9:continue
                if not ctx.spec.get('guns',{}).get('open_battery') and any(abs(s-r['s'])<r['w']/2-1e-7 and abs(z-r['z'])<r['h']/2-1e-7 for r in ctx.ports):continue
                ids=[vertex(i,zz[j]),vertex(i+1,zz[j]),vertex(i+1,zz[j+1]),vertex(i,zz[j+1])]
                ids=list(dict.fromkeys(ids))
                if len(ids)>=3:faces.append(tuple(ids if side>0 else reversed(ids)))
        obj=_thick_surface(ctx,'hull_shell_'+label,verts,faces,side);ctx.hull_nodes.append(obj)
        # True timber keel and cap rails meet the individual hollow shell.
        rail=ctx.tube('gunwale_'+label,[p(side*ctx.width(s,ctx.deck_height(s)),s,ctx.deck_height(s)+float(h.get('bulwark_height',.8))) for s in ss],[min(.065,ctx.width(s,ctx.deck_height(s))*.28) for s in ss],'paintTrim','fitting',sides=6)
        ctx.joint(obj,rail,'The gunwale caps the upper edge of this timber hull side.')
    keel=ctx.tube('keel',[p(0,s,-draft+_curve(ctx.profile,s/ctx.L,2)) for s in ss],.10,'spar','hull',sides=4)
    ctx.hull_nodes.append(keel)
    for ob in ctx.hull_nodes:
        if ob!=keel:ctx.joint(ob,keel,'The port and starboard plank shells are rabbeted onto the longitudinal keel.')
    for sign,label in[(-1,'stern'),(1,'bow')]:
        s=sign*ctx.L/2;bottom=-draft+_curve(ctx.profile,sign*.5,2);top=ctx.deck_height(s)+float(h.get('bulwark_height',.8))
        width=ctx.width(s,top)
        if sign<0 and ctx.stern_extension:
            verts=[];faces=[];segments=20;rows=24
            for inner in(0,1):
                for j in range(rows+1):
                    z=bottom+(top-bottom)*j/rows;w=max(.015,ctx.width(s,z)-inner*.08);depth=ctx.stern_extension-inner*.08
                    for k in range(segments+1):
                        angle=-math.pi/2+math.pi*k/segments;verts.append(p(w*math.sin(angle),s-depth*math.cos(angle),z))
            n=(rows+1)*(segments+1)
            for layer in(0,1):
                off=layer*n
                for j in range(rows):
                    for k in range(segments):
                        a=off+j*(segments+1)+k;f=(a,a+1,a+segments+2,a+segments+1);faces.append(f if layer==0 else tuple(reversed(f)))
            for j in range(rows):
                for k in(0,segments):
                    a=j*(segments+1)+k;b=(j+1)*(segments+1)+k;faces.append((a,b,b+n,a+n))
            for k in range(segments):
                for j in(0,rows):
                    a=j*(segments+1)+k;faces.append((a,a+n,a+n+1,a+1))
            stem=ctx.mesh(label+'_closure',verts,faces,'paintTrim','hull')
            rim=ctx.tube('round_stern_rail',[p(width*math.sin(-math.pi/2+math.pi*k/segments),s-ctx.stern_extension*math.cos(-math.pi/2+math.pi*k/segments),top) for k in range(segments+1)],.055,'paintTrim','fitting')
            ctx.joint(stem,rim,'The curved stern rail caps the real rounded merchant stern.')
            for ob in ctx.vis:
                if ob.name.startswith('gunwale_'):ctx.joint(rim,ob,'The curved stern rail joins the actual port or starboard cap rail.')
        else:
            verts=[];faces=[];rows=24
            for j in range(rows+1):
                z=bottom+(top-bottom)*j/rows;w=ctx.width(s,z)+.02
                verts.extend([p(-w,s-.09,z),p(w,s-.09,z),p(w,s+.09,z),p(-w,s+.09,z)])
            for j in range(rows):
                for k in range(4):faces.append((j*4+k,j*4+(k+1)%4,(j+1)*4+(k+1)%4,(j+1)*4+k))
            faces+=[(3,2,1,0),tuple(rows*4+k for k in range(4))]
            stem=ctx.mesh(label+'_closure',verts,faces,'paintTrim','hull')
        ctx.hull_nodes.append(stem)
        for ob in [o for o in ctx.hull_nodes[:-1] if o.name.startswith('hull_shell_') or o.name=='keel']:ctx.joint(ob,stem,'The hull side and backbone terminate in this real stem or stern closure.')
    for stem in [o for o in ctx.hull_nodes if o.name.endswith('_closure')]:
        for rail in [o for o in ctx.vis if o.name.startswith('gunwale_')]:ctx.joint(stem,rail,'This actual cap rail is housed into its terminal stem or stern timber.')
    from v2_audit import weld_topology
    from v2_mesh_finish import finish_scene
    ctx.hull_finish=[]
    for ob in ctx.hull_nodes:
        stats,*_=weld_topology(ob)
        if stats['zero_area_faces'] or stats['non_manifold_edges'] or stats['duplicate_faces']:
            ctx.hull_finish.append(finish_scene([ob]))
        ctx.collider(ob)


def deck_piece(ctx,name,a,b,height=None,xmin=None,xmax=None):
    if abs(a+ctx.L/2)<.001:a-=ctx.stern_extension
    n=max(2,round((b-a)/ctx.L*48));verts=[];faces=[]
    for i in range(n+1):
        s=a+(b-a)*i/n
        z=ctx.main_height(s) if height is None else (height(s) if callable(height) else float(height))
        w=max(.015,ctx.width(s,z)-.13);lo=max(-w,xmin) if xmin is not None else -w;hi=min(w,xmax) if xmax is not None else w
        if hi<=lo:hi=lo+.005
        verts.extend([p(lo,s,z-.12),p(hi,s,z-.12),p(hi,s,z),p(lo,s,z)])
    for i in range(n):
        for j in range(4):faces.append((i*4+j,i*4+(j+1)%4,(i+1)*4+(j+1)%4,(i+1)*4+j))
    faces+=[(3,2,1,0),tuple(n*4+j for j in range(4))]
    obj=ctx.mesh(name,verts,faces,'deck','surface',grain_path=[sum(verts[:4],Vector())/4,sum(verts[-4:],Vector())/4],collision=True);ctx.deck_nodes.append(obj)
    for ob in ctx.hull_nodes:ctx.joint(obj,ob,'This deck slab is housed into the actual closed hull side; the collision is the same concave timber geometry.')
    # Real transverse beams support the slab instead of leaving its inset
    # edge floating beside the shell. Their upper face meets the slab underside.
    for k,t in enumerate((.2,.5,.8)):
        ss=a+(b-a)*t;zz=ctx.main_height(ss) if height is None else (height(ss) if callable(height) else float(height))
        width=ctx.width(ss,zz-.2)-.03
        lo=max(-width,xmin) if xmin is not None else -width;hi=min(width,xmax) if xmax is not None else width
        if hi-lo<.12:continue
        beam=ctx.beam(name+'_bearing_beam_%d'%k,p(lo,ss,zz-.20),p(hi,ss,zz-.20),.15,.16,'spar',kind='surface',collision=True)
        ctx.joint(beam,obj,'This actual transverse deck beam supports the slab underside.')
        for shell in ctx.hull_nodes:ctx.joint(beam,shell,'The deck beam ends are housed into the inner hull planking.')
    return obj


def decks(ctx):
    cockpit=ctx.hull.get('cockpit')
    if cockpit:
        a=cockpit['from']*ctx.L;b=cockpit['to']*ctx.L;w=ctx.B/2*cockpit.get('width_factor',.65)
        deck_piece(ctx,'deck_bow',b,ctx.L/2);deck_piece(ctx,'deck_stern',-ctx.L/2,a)
        deck_piece(ctx,'deck_port_walkway',a,b,xmax=-w);deck_piece(ctx,'deck_starboard_walkway',a,b,xmin=w)
        floor=float(cockpit.get('floor_z_m',-.2));deck_piece(ctx,'cockpit_sole',a,b,height=floor,xmin=-w,xmax=w)
        if cockpit.get('benches',True):
            for i,s in enumerate([a+(b-a)*.2,a+(b-a)*.8]):
                o=ctx.box('thwart_%d'%i,p(0,s,ctx.main_height(s)-.15),(2*max(.10,ctx.width(s)-.10),.24,.07),'deck')
                for h in ctx.hull_nodes:ctx.joint(o,h,'The open-boat thwart is seated against the inner planking.')
    else:deck_piece(ctx,'main_deck',-ctx.L/2,ctx.L/2)
    for i,c in enumerate(ctx.castles):
        deck_piece(ctx,'castle_deck_%d'%i,c['from']*ctx.L,c['to']*ctx.L,height=lambda s,c=c:ctx.main_height(s)+c['height_m'])
        for sign,s in[(-1,c['from']*ctx.L),(1,c['to']*ctx.L)]:
            if abs(s)>=ctx.L*.499:continue
            z=ctx.main_height(s);o=ctx.box('castle_bulkhead_%d_%d'%(i,sign),p(0,s,z+c['height_m']/2),(max(.1,2*ctx.width(s)-.24),.13,c['height_m']),'paintHull')
            for d in ctx.deck_nodes:ctx.joint(o,d,'The castle end bulkhead meets its main and raised structural decks.')
    for row in ctx.spec.get('guns',{}).get('rows',[]):
        z=float(row['z_m'])-.67
        if z<ctx.freeboard-.3:deck_piece(ctx,'gun_deck_%d'%len(ctx.deck_nodes),float(row.get('from',-.35))*ctx.L-.7,float(row.get('to',.35))*ctx.L+.7,height=lambda s,z=z:z+_curve(ctx.profile,s/ctx.L,3))


def guns(ctx):
    for port in ctx.ports:
        for side,label in[(1,'port'),(-1,'starboard')]:
            s,z=port['s'],port['z'];x=side*ctx.width(s,z);tag='%d_%s_%02d'%(port['row'],label,port['index'])
            baseline=ctx.spec['guns']['rows'][port['row']]['z_m']-.67
            target=baseline+_curve(ctx.profile,s/ctx.L,3);candidates=[ctx.main_height(s)]+[ctx.main_height(s)+c['height_m'] for c in ctx.castles if c['from']*ctx.L<=s<=c['to']*ctx.L]
            nearest=min(candidates,key=lambda value:abs(value-target));floor=nearest if abs(nearest-target)<.30 else target
            available=min(ctx.width(s+ds,zz) for ds in(-.44,0,.44) for zz in(floor+.01,floor+.15,floor+.45,z))
            cx=side*min(ctx.width(s,z)-.65,available-.57)
            a=p(cx-side*.35,s,z);b=p(x+side*.8,s,z)
            barrel=ctx.tube('gun_barrel_'+tag,[a,a.lerp(b,.18),a.lerp(b,.6),b],max(.07,min(.18,ctx.B*.012)),'iron','fitting',sides=10)
            barrel['role']='cannon_barrel';ctx.gun_nodes.append(barrel)
            base=ctx.box('gun_carriage_'+tag,p(cx,s,floor+.30),(.85,.62,.30),'spar')
            for i in(-1,1):
                cheek=ctx.box('gun_cheek_'+tag+'_'+str(i),p(cx,s+i*.24,(floor+.45+z)/2),(.68,.12,max(.12,z-floor-.45)),'spar')
                ctx.joint(barrel,cheek,'The barrel trunnion is held by this real timber cheek.');ctx.joint(base,cheek,'The carriage cheek is mortised into its base.')
                wheel=ctx.tube('gun_wheel_'+tag+'_'+str(i),[p(cx+side*.02,s+i*.34,floor+.19),p(cx+side*.02,s+i*.39,floor+.19)],.19,'spar','fitting',sides=8)
                ctx.joint(wheel,base,'The carriage wheel is fixed to the axle and side cheek.')
                axle=ctx.tube('gun_axle_'+tag+'_'+str(i),[p(cx+side*.02,s+i*.20,floor+.19),p(cx+side*.02,s+i*.40,floor+.19)],.035,'iron','fitting',sides=6)
                ctx.joint(axle,wheel,'This axle passes through the actual wheel hub.');ctx.joint(axle,base,'The axle is held in the carriage side cheek.')
                trunnion=ctx.tube('gun_trunnion_'+tag+'_'+str(i),[p(cx,s+i*.18,z),p(cx,s+i*.32,z)],.065,'iron','fitting',sides=8)
                ctx.joint(trunnion,barrel,'The iron trunnion is forged into the barrel.');ctx.joint(trunnion,cheek,'The trunnion bears in the actual carriage cheek.')
                for d in ctx.deck_nodes:ctx.joint(wheel,d,'The wheel bears on this structural gun-deck surface.')
            for d in ctx.deck_nodes:ctx.joint(base,d,'The carriage feet bear on their structural gun deck or main deck.')


def fittings(ctx):
    from v4_fittings import build_fittings
    return build_fittings(ctx.spec,ctx)

def build(spec,out):
    if isinstance(spec,(str,Path)):spec=json.loads(Path(spec).read_text())
    from v4_export import finish
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ctx=Context(spec);print('V4_STAGE hull',spec['id'],flush=True);hull(ctx);print('V4_STAGE decks',flush=True);decks(ctx);print('V4_STAGE guns',flush=True);guns(ctx);print('V4_STAGE fittings',flush=True);fittings(ctx)
    try:
        from v4_rig import build_rig
        print('V4_STAGE rig',flush=True);rig=build_rig(spec,ctx)
    except ImportError:rig={'pending':'root rig helper not yet installed'}
    ctx.marker('asset_origin',Vector((0,0,0)),{'units':'metres','waterline':True})
    for ob in ctx.vis:
        if ob.get('kind')=='spar':
            for deck in ctx.deck_nodes:ctx.joint(ob,deck,'This mast heel or spar support is housed into a structural deck.')
    for bulkhead in [o for o in ctx.vis if o.name.startswith('castle_bulkhead_')]:
        for shell in ctx.hull_nodes:ctx.joint(bulkhead,shell,'The castle end bulkhead is seated in the actual upper hull planking.')
        for deck in ctx.deck_nodes:ctx.joint(bulkhead,deck,'This castle bulkhead terminates against its actual structural deck slab.')
    for thwart in [o for o in ctx.vis if o.name.startswith('thwart_')]:
        for deck in ctx.deck_nodes:ctx.joint(thwart,deck,'The transverse thwart ends bear on the adjoining side-deck ledges.')
    for mast in [o for o in ctx.vis if o.get('rig_member')=='mast']:
        for beam in [o for o in ctx.vis if '_bearing_beam_' in o.name]:ctx.joint(mast,beam,'The mast heel is seated in the actual supporting deck beam.')
    for bowsprit in [o for o in ctx.vis if o.name=='bowsprit']:
        for shell in ctx.hull_nodes:ctx.joint(bowsprit,shell,'The bowsprit heel is housed in the actual bow timber socket.')
    from mathutils.bvhtree import BVHTree
    bounds={};trees={}
    for obj in ctx.vis:
        if obj.type!='MESH':continue
        points=[obj.matrix_world@v.co for v in obj.data.vertices]
        bounds[obj.name]=([min(q[k] for q in points) for k in range(3)],[max(q[k] for q in points) for k in range(3)])
        if obj in ctx.deck_nodes or obj in ctx.hull_nodes:trees[obj.name]=BVHTree.FromPolygons(points,[list(f.vertices) for f in obj.data.polygons])
    for obj in ctx.vis:
        if obj.get('rig_member')!='deck_fastening':continue
        points=[obj.matrix_world@v.co for v in obj.data.vertices]
        tree=BVHTree.FromPolygons(points,[list(f.vertices) for f in obj.data.polygons])
        lo,hi=bounds[obj.name]
        for support in ctx.deck_nodes+ctx.hull_nodes:
            a,b=bounds[support.name]
            if all(lo[k]<=b[k] and a[k]<=hi[k] for k in range(3)) and tree.overlap(trees[support.name]):
                ctx.joint(obj,support,'This actual iron fastening is through-bolted into the intersected timber mounting surface.')
    def nearby(row):
        if row['a'] not in bounds or row['b'] not in bounds:return True
        a,b=bounds[row['a']],bounds[row['b']]
        return all(a[0][k]<=b[1][k]+.03 and b[0][k]<=a[1][k]+.03 for k in range(3))
    ctx.joints=[row for row in ctx.joints if nearby(row)]
    return finish(ctx,spec,Path(out),rig)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('spec',type=Path);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);build(json.loads(args.spec.read_text()),args.out)
