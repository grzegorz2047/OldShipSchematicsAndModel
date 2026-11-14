"""Build the four real SailerTales construction-boat states, with repair components.

Blender 5.2: --background --factory-startup --python-exit-code 1 --python
sailertales/boat-frame/build.py -- --out build/final/boat-frame
No generated AI geometry and no game runtime adapter are used.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'sailertales/common'))
from v2_boats import physical_uv
from v2_export import export_glb,lod,triangles
from v2_materials import upgrade_scene

L,B,D,N,KEEL_Y=6.5,.86,.92,8,.42
RIB_U=[-.8,-.6,-.4,-.2,0,.2,.4,.6,.8]
PEG_U=[-.4,-.2,0,.2,.4]
THICKNESS=.022
VIS=[];COL=[];MARKERS=[];MATS={}


def p(x,z,y):return Vector((x,-z,y))
def gltf(q):return [float(q.x),float(q.z),float(-q.y)]
def write(path,data):Path(path).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def hull_b(u):return B*max(0,1-abs(u)**3)**.52
def sheer(u):return D*(1+.1*u*u+.42*u**4)
def rocker(u):return .12*abs(u)**3

def hp(u,t,sx,off=0):
    a=min(1.06,t)*math.pi/2
    x=hull_b(u)*math.sin(min(a,math.pi/2))**.85
    y=rocker(u)+(sheer(u)-rocker(u))*(1-max(0,math.cos(a))**1.3)+max(0,t-1)*.5
    return p(sx*max(0,x-off*math.sin(a)),u*L/2,KEEL_Y+y+off*math.cos(a))

def stem(k,sx):
    y0=rocker(.985)-.07;y1=sheer(1)+.16
    return p(0,sx*L/2*(.975+.03*math.sin(min(1,max(0,k))*math.pi/2)),KEEL_Y+y0+(y1-y0)*max(0,k)**1.35)

def stem_z(y):
    y0=rocker(.985)-.07;y1=sheer(1)+.16
    k=min(1,max(0,(y-KEEL_Y-y0)/(y1-y0)))**(1/1.35)
    return L/2*(.975+.03*math.sin(k*math.pi/2))


def collider(o):
    c=o.copy();c.data=o.data.copy();c.name='col_'+o.name
    bpy.context.scene.collection.objects.link(c)
    c['asset_role']='collision';c['source_name']=o.name;c.hide_render=True
    c.data.materials.clear();c.data.materials.append(MATS['collision'])
    COL.append(c);return c


def mesh(name,verts,faces,mat='wood',stage=0,group=None,grain=Vector((0,-1,0)),path=None,collision=True):
    me=bpy.data.meshes.new(name+'_mesh');me.from_pydata(verts,[],faces);me.update()
    o=bpy.data.objects.new(name,me);bpy.context.scene.collection.objects.link(o)
    me.materials.append(MATS[mat]);o['kind']='hull' if group in ('spine','planking') else 'fitting';o['asset_role']='visual'
    o['construction_stage']=stage;o['assembly']=group or name;o['physics']='solid' if collision else 'component'
    physical_uv(o,grain,path)
    VIS.append(o)
    if collision:collider(o)
    return o


def box(name,center,size,mat='wood',stage=0,group=None,grain=Vector((1,0,0))):
    center=Vector(center);h=Vector(size)/2
    verts=[center+Vector((a*h.x,b*h.y,c*h.z)) for c in(-1,1) for b in(-1,1) for a in(-1,1)]
    faces=[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]
    return mesh(name,verts,faces,mat,stage,group,grain)


def sweep(name,points,width,depth,mat='wood',stage=0,group=None,width_axis=Vector((0,-1,0))):
    points=list(map(Vector,points));verts=[];faces=[];axis=Vector(width_axis).normalized()
    for i,point in enumerate(points):
        tangent=(points[min(i+1,len(points)-1)]-points[max(0,i-1)]).normalized()
        w=axis-tangent*axis.dot(tangent)
        if w.length<.01:raise RuntimeError('Degenerate sweep section '+name)
        w.normalize();n=tangent.cross(w).normalized()
        verts.extend([point-w*width/2-n*depth/2,point+w*width/2-n*depth/2,
                      point+w*width/2+n*depth/2,point-w*width/2+n*depth/2])
    for i in range(len(points)-1):
        for j in range(4):faces.append((4*i+j,4*i+(j+1)%4,4*(i+1)+(j+1)%4,4*(i+1)+j))
    faces+=[(3,2,1,0),tuple(4*(len(points)-1)+j for j in range(4))]
    return mesh(name,verts,faces,mat,stage,group,points[-1]-points[0],points)


def cylinder(name,center,axis,radius,length,stage=3):
    axis=Vector(axis).normalized();x=axis.cross(Vector((0,0,1)))
    if x.length<.01:x=axis.cross(Vector((1,0,0)))
    x.normalize();y=axis.cross(x).normalized();verts=[]
    for sign,r in [(-1,radius*.846),(1,radius)]:
        for j in range(8):verts.append(center+sign*axis*length/2+r*(math.cos(j*math.pi/4)*x+math.sin(j*math.pi/4)*y))
    faces=[tuple(reversed(range(8))),tuple(range(8,16))]+[(j,(j+1)%8,(j+1)%8+8,j+8) for j in range(8)]
    return mesh(name,verts,faces,'dark',stage,'pegs',axis,collision=False)


def strake_vertices(j,sx,u0,u1):
    # Retain the game profile in the body. Last body station is 0.965 rather
    # than 0.985, so the real 22 mm solid tapers monotonically into the stem
    # rabbet instead of folding its final station back through itself.
    cap0=u0<=-.98;cap1=u1>=.98
    lo=max(u0,-.965);hi=min(u1,.965)
    count=max(6,round((hi-lo)/1.93*64))
    stations=([('cap',-1)] if cap0 else [])+[('body',lo+(hi-lo)*i/count) for i in range(count+1)]+([('cap',1)] if cap1 else [])
    verts=[]
    for kind,u in stations:
        body_u=u if kind=='body' else u*.965
        for t,off in [(j/N,-.014),((j+1)/N+.012,0),((j+1)/N+.012,THICKNESS),(j/N,THICKNESS-.014)]:
            q=hp(body_u,t,sx,off)
            if kind=='cap':
                q.x=sx*(.042-off*math.sin(t*math.pi/2));q.y=-u*(stem_z(q.z)-.03)
            verts.append(q)
    faces=[]
    for i in range(len(stations)-1):
        for k in range(4):faces.append((i*4+k,i*4+(k+1)%4,(i+1)*4+(k+1)%4,(i+1)*4+k))
    faces+=[(3,2,1,0),tuple((len(stations)-1)*4+k for k in range(4))]
    path=[sum(verts[i*4:i*4+4],Vector())/4 for i in range(len(stations))]
    return verts,faces,path


def strake(name,j,sx,u0,u1,stage,component=False):
    verts,faces,path=strake_vertices(j,sx,u0,u1)
    o=mesh(name,verts,faces,'wood',stage,'repair_plank' if component else 'planking',path=path,collision=not component)
    o['strake_index']=j;o['hull_side']=sx;o['u_min']=u0;o['u_max']=u1
    o['scantling_m']=THICKNESS;o['source_formula']='src/models/hull.js strakeGeo + closed 22 mm thickness'
    if component:
        original=[q.copy() for q in verts]
        # Keep the source bow centre, cant and rise. Rotate the stock section
        # into an orthogonal frame so a solid board is not sheared by reusing
        # the game's unrotated edge vector. Grain paths follow the morph.
        bow=sum(verts[-4:],Vector())/4
        aft=p(math.sin(.5)*sx,-math.cos(.5),.08)
        forward=-aft.normalized();bow_tangent=(path[-1]-path[-2]).normalized()
        rotation=bow_tangent.rotation_difference(forward)
        cross=[rotation@(q-bow) for q in verts[-4:]]
        cross=[q-forward*q.dot(forward) for q in cross]
        distance=0;centers={} 
        previous=bow
        for i in range(len(path)-1,-1,-1):
            distance+=(path[i]-previous).length;previous=path[i]
            centers[i]=bow+p(math.sin(.5)*sx*distance,-math.cos(.5)*distance,.08*distance)
        straight=[centers[i//4]+cross[i%4] for i in range(len(verts))]
        mapping={tuple(round(c,7) for c in q):i for i,q in enumerate(original)}
        basis=o.shape_key_add(name='Basis');key=o.shape_key_add(name='straight')
        for v in o.data.vertices:
            index=mapping.get(tuple(round(c,7) for c in v.co))
            if index is None:raise RuntimeError('Repair morph lost its source vertex correspondence')
            key.data[v.index].co=straight[index]
        key.value=0;key.slider_min=0;key.slider_max=1
        o['morph_contract']='Basis=fitted; straight weight=1-smoothstep(b); smoothstep(b)=b*b*(3-2*b); setGapPlank(null) hides this component'
        o['grain_morph_paths_json']=json.dumps({'schema':1,'axes':'object_local','morph':'straight','base':[list(q) for q in path],'target':[list(centers[i]) for i in range(len(path))],'interpolation':'linear in the actual straight shape-key weight'})
        o['straight_stock_section']='Constant orthogonal cross-section; source 0.5 rad cant and 0.08 m/m rise retained; bow centre fixed.'
    return o


def marker(name,q,**extras):
    o=bpy.data.objects.new(name,None);o.location=q;bpy.context.scene.collection.objects.link(o)
    o['asset_role']='marker';o['kind']='hook';o.empty_display_size=.05
    for k,v in extras.items():o[k]=v
    MARKERS.append(o);return o


def geometry(side):
    for i,u in enumerate([-.52,.52]):
        s=u*L/2;top=KEEL_Y+rocker(u)-.145
        box('trestle_%d_foot'%i,p(0,s,.08),(2.6,.24,.16),'tar',group='trestle_%d'%i)
        box('trestle_%d_keel_block'%i,p(0,s,(top+.16)/2),(.46,.20,top-.16),'dark',group='trestle_%d'%i)
        for sx in(-1,1):
            end=hp(u,.52,sx,-.03)
            sweep('trestle_%d_brace_%s'%(i,'starboard' if sx>0 else 'port'),[p(sx*1.12,s,.16),end],.08,.08,'dark',group='trestle_%d'%i)
            box('trestle_%d_shoe_%s'%(i,'starboard' if sx>0 else 'port'),p(sx*1.12,s,.18),(.20,.20,.04),'tar',group='trestle_%d'%i)
    keel=[p(0,(-.975+1.95*i/32)*L/2,KEEL_Y+rocker(-.975+1.95*i/32)-.07) for i in range(33)]
    sweep('spine_keel',keel,.09,.15,'dark',width_axis=Vector((1,0,0)),group='spine')
    for sx,label in[(-1,'stern'),(1,'bow')]:
        sweep('spine_'+label+'_stem',[stem(i/24,sx) for i in range(25)],.09,.13,'dark',width_axis=Vector((1,0,0)),group='spine')
    for i,u in enumerate(RIB_U):
        points=[]
        for sx,ts in[(-1,[1-i/28 for i in range(29)]),(1,[i/28 for i in range(1,29)])]:
            for t in ts:
                q=hp(u,t,sx,.045)
                q.z-=.007*max(0,1-t/.18)**2
                points.append(q)
        sweep('frame_%02d'%i,points,.055,.07,'wood',stage=0 if i%2==0 else 1,group='frames')
    for j in range(N):
        stage=1 if j<3 else 2 if j<6 else 3
        for sx in(-1,1):
            label='starboard' if sx>0 else 'port'
            spans=[(-.985,-.42),(.42,.985)] if j==4 and sx==side else[(-.985,.985)]
            for k,(a,b) in enumerate(spans):strake('hull_strake_%02d_%s_%d'%(j,label,k),j,sx,a,b,stage)
    for sx,label in[(-1,'port'),(1,'starboard')]:
        points=[hp(-.965+1.93*i/64,1.02,sx,-.02) for i in range(65)]
        for index,sign in [(0,-1),(-1,1)]:
            q=points[index].copy();q.x=sx*.062;q.y=-sign*(stem_z(q.z)-.03)
            if sign<0:points.insert(0,q)
            else:points.append(q)
        sweep('trim_gunwale_'+label,points,.06,.07,'dark',stage=3,group='trim',width_axis=Vector((1,0,0)))
    for i,u in enumerate([-.5,.02,.5]):
        z=KEEL_Y+sheer(u)-.20;width=2*hull_b(u)*.95
        box('trim_seat_%d'%i,p(0,u*L/2,z),(width,.24,.035),'wood',3,'trim')
        for sx in(-1,1):
            box('trim_seat_%d_cleat_%s'%(i,'starboard' if sx>0 else 'port'),p(sx*(width/2-.035),u*L/2,z-.035),(.12,.27,.035),'dark',3,'trim',Vector((0,-1,0)))
    plank=strake('repair_plank',4,side,-.42,.42,2,component=True)
    for i,u in enumerate(PEG_U):
        q=hp(u,.565,side,-.012);normal=(q-hp(u,.565,side,.038)).normalized()
        cylinder('repair_peg_%d'%i,q,normal,.026,.034)
    return plank


def joints(objects):
    # Declare only actual structural contacts, after detecting overlapping
    # surface boxes. Each rule names two concrete members and its joinery.
    pairs=[];bounds={}
    for o in objects:
        if o.type!='MESH':continue
        points=[o.matrix_world@v.co for v in o.data.vertices]
        bounds[o.name]=([min(q[k] for q in points) for k in range(3)],[max(q[k] for q in points) for k in range(3)])
    def overlap(a,b):return all(bounds[a][0][k]<=bounds[b][1][k]+.001 and bounds[b][0][k]<=bounds[a][1][k]+.001 for k in range(3))
    def put(a,b,reason):
        if overlap(a.name,b.name):pairs.append({'a':a.name,'b':b.name,'reason':reason})
    solids=[o for o in objects if o.type=='MESH']
    for i,a in enumerate(solids):
        for b in solids[i+1:]:
            aa,bb=a['assembly'],b['assembly']
            if aa=='spine' and bb in ('spine','frames','planking') or bb=='spine' and aa in ('frames','planking'):
                put(a,b,'Keel/stem scarf, frame heel seating or plank-end rabbet in the actual boat backbone.')
            elif {aa,bb}=={'frames','planking'}:
                put(a,b,'The steam-bent frame bears against the inner face of this solid clinker plank; the small frame heel is seated on the keel.')
            elif aa==bb=='planking' and a.get('hull_side')==b.get('hull_side') and abs(a.get('strake_index',-9)-b.get('strake_index',-9))==1:
                put(a,b,'Adjacent clinker strakes have the source 0.012 transverse lap and 14 mm lower-edge flare; this local structural lap is intentional.')
            elif aa.startswith('trestle_') and bb==aa:
                put(a,b,'The trestle brace and keel block are housed into the cross-foot and retained by its bearing shoe.')
            elif (aa.startswith('trestle_') and bb in ('spine','planking')) or(bb.startswith('trestle_') and aa in ('spine','planking')):
                put(a,b,'This specific trestle member is the physical bearing under the keel or lower bilge, rather than an unrelated object crossing the hull.')
            elif aa=='trim' and bb in ('trim','planking','frames','spine') or bb=='trim' and aa in ('planking','frames','spine'):
                put(a,b,'Gunwale caps the upper strake; seat ends and their cleats are housed into the upper inside planking.')
    return pairs


def contracts(side):
    anchors={};details={}
    def anchor(name,q,source,**extra):
        anchors[name]=gltf(q);details[name]={'position_gltf_m':gltf(q),'source':source,**extra};marker(name,q,source=source,**extra)
    anchor('repair_gap',hp(0,.565,side,-.02),'point(gap,0.5)',hull_u=0.,hull_t=.565,hull_side=side)
    anchor('repair_gap_center',hp(0,.565,side,-.02),'point(gap,0.5) alias',hull_u=0.,hull_t=.565,hull_side=side)
    for i,u in enumerate(PEG_U):anchor('peg_%d'%i,hp(u,.565,side,-.02),'point(peg,%d)'%i,hull_u=u,hull_t=.565,hull_side=side)
    for i,(sx,t,u) in enumerate([(1,.5,.3),(-1,.375,-.72),(-1,.25,.12)]):
        sx*=side;q=hp(u,t,sx,-.02)
        anchor('leak_%d'%i,q,'point(leak,%d)'%i,hull_u=u,hull_t=t,hull_side=sx)
        drip=hp(u,t-.01,sx,-.03);drip.z=0
        anchor('drip_%d'%i,drip,'point(drip,%d)'%i)
    for i,k in enumerate([.8,.655]):
        q=stem(k,1);tangent=(stem(k+.01,1)-stem(k-.01,1)).normalized()
        normal=Vector((0,-tangent.z,tangent.y))
        if normal.y>0:normal=-normal
        normal.normalize();q+=normal*.066
        anchor('stem_mark_%d'%i,q,'point(stem,%d)'%i,normal_gltf=list(gltf(normal)),tangent_gltf=list(gltf(tangent)))
    marker('asset_origin',Vector((0,0,0)),units='metres',meaning='ground under keel centre; source KEEL_Y=0.42 m already included')
    hooks={'setStage':[0,1,2,3],'setGapPlank':[0,1],'setPegs':[0,5],'setTrim':[False,True],
           'setWater':[False,True],'setLeak':{'index':[0,1,2],'state':[0,1,2,3,4]},
           'setMarks':{'father':[0,1],'son':[0,1]},'carve':{'mark':[0,1],'seconds_default':3},
           'point':['gap','peg','leak','drip','stem']}
    probe_u=.10;probe=hp(probe_u,.565,side,0);normal=(hp(probe_u,.565,side,-.01)-hp(probe_u,.565,side,.01)).normalized()
    return anchors,details,hooks,{'probe_gltf_m':[gltf(probe+normal*.18),gltf(probe-normal*.18)],'shell_patterns':['hull_strake_*'],'strake':4,'hull_side':side,'u0':-.42,'u1':.42,'length_parameter_m':.84*L/2}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);ap.add_argument('--work-side',type=int,choices=(-1,1),default=1)
    ap.add_argument('--texture-cache',type=Path,default=ROOT/'build/pbr-v2')
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);out=args.out.resolve();(out/'model').mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.unit_settings.scale_length=1
    for name,canonical in [('wood','wood'),('dark','wood_dark'),('tar','wood_black')]:
        m=bpy.data.materials.new(canonical);m.diffuse_color=(.6,.4,.2,1);m['uv_tile_m']=[2.,2.];MATS[name]=m
    MATS['collision']=bpy.data.materials.new('collision_debug');MATS['collision'].diffuse_color=(.1,.5,.2,1)
    plank=geometry(args.work_side);anchors,anchor_details,hooks,gap=contracts(args.work_side)
    materials=upgrade_scene(VIS,args.texture_cache)
    # Small alternating variations read as separate oak boards, without fake
    # additional geometry, UV changes or a photographic texture claim.
    base=next(o for o in VIS if o.name.startswith('hull_strake_')).data.materials[0];variations=[]
    for i,factor in enumerate([.96,1.,1.04]):
        m=base.copy();m.name='frame_oak_planking_%d'%i
        for node in m.node_tree.nodes:
            if node.type=='MIX' and node.data_type=='RGBA':
                c=list(node.inputs[7].default_value);node.inputs[7].default_value=(*[min(1,x*factor) for x in c[:3]],c[3])
        variations.append(m)
    for o in VIS:
        if o.name.startswith('hull_strake_') or o.name=='repair_plank':o.data.materials[0]=variations[int(o.get('strake_index',0))%3]
    main_objects=[o for o in VIS if o['assembly'] not in ('repair_plank','pegs')]
    main_colliders=[o for o in COL if o['source_name'] in {v.name for v in main_objects}]
    intended=joints(main_objects)
    states=[]
    for stage in range(4):
        visual=[o for o in main_objects if o['construction_stage']<=stage]
        collision=[o for o in main_colliders if o['construction_stage']<=stage]
        model='ship.glb' if stage==3 else 'stage_%d.glb'%stage
        col='collision.glb' if stage==3 else 'collision_%d.glb'%stage
        export_glb(out/'model'/model,visual+MARKERS);export_glb(out/'model'/col,collision)
        states.append({'id':'stage%d'%stage,'stage':stage,'model':'model/'+model,'collision':'model/'+col,
                       'mesh_nodes':len(visual),'triangles':triangles(visual),'adds': ['spine and alternating frames','remaining frames and strakes 0–2','strakes 3–5 with repair gap','strakes 6–7, trim and three seats'][stage]})
    trim=[o for o in main_objects if o['assembly']=='trim'];pegs=[o for o in VIS if o['assembly']=='pegs']
    export_glb(out/'model/repair_plank.glb',[plank]);export_glb(out/'model/pegs_5.glb',pegs);export_glb(out/'model/trim.glb',trim)
    trim_colliders=[o for o in main_colliders if o['source_name'] in {v.name for v in trim}]
    export_glb(out/'model/trim_collision.glb',trim_colliders)
    components=[{'id':'repair_plank','model':'model/repair_plank.glb','morph':'straight','basis':'fitted','default_visible':False},
                {'id':'pegs','model':'model/pegs_5.glb','count':5,'default_visible':False},
                {'id':'trim','model':'model/trim.glb','collision':'model/trim_collision.glb','included_in_canonical_stage3':True,'toggle_nodes':[o.name for o in trim]}]
    counts={'lod0':triangles(main_objects),'collision':triangles(main_colliders),
            'lod1':lod(main_objects,out/'model/ship_lod1.glb',1),'lod2':lod(main_objects,out/'model/ship_lod2.glb',2)}
    for o in VIS:
        o.hide_render=o['assembly'] in ('repair_plank','pegs');o.hide_set(o.hide_render)
    for o in COL:o.hide_render=True;o.hide_set(True)
    for image in bpy.data.images:
        if image.source=='FILE' and not image.packed_file:image.pack()
    bpy.context.scene.frame_set(0);bpy.ops.wm.save_as_mainfile(filepath=str(out/'model/ship.blend'),compress=True)
    spec=json.loads((HERE/'spec.json').read_text());spec['work_side']=args.work_side
    state_doc={'schema':1,'kind':'boat-frame','states':states,'components':components,'anchors':anchors,'hooks':hooks,'gap':gap,
       'visibility':{'stage_members':'construction_stage <= requestedStage; stages are cumulative','repair_plank':'separate component; hidden initially','pegs':'show first k of repair_peg_0..4','trim':'already present at stage3; setTrim(false) hides trim_* in ship.glb, do not add trim.glb a second time'},
       'work_side':args.work_side,'coordinate_contract':'glTF metres: +X is the selected source work side for work=1, +Y up, +Z bow; KEEL_Y=0.42 already included'}
    navigation={'schema':2,'units':'metres','axes':'glTF X across, Y up, Z forward','routes':[],
       'scope':'Construction prop: no walkable boat interior or self-contained terrain; external ground access belongs to the level.',
       'external_workspace':{'suggested_clearance_box_gltf_m':{'min':[-2.05,0,-3.9],'max':[2.05,2.2,3.9]},'tested_as_walk_route':False,'reason':'The delivered support/collision meshes define the actual obstacle. Ground, navmesh and player-controller testing require the game level.'}}
    source_spec=spec.get('source_files',{})
    design={'schema':3,'construction':'Source-parametric clinker-built construction/repair boat on two real timber trestles.',
      'basis':{'game_commit':spec['source_commit'],'game_files':source_spec,'guide':['docs/en/03-hull-construction.md','docs/en/09-deck-machinery.md','docs/en/13-3d-quality-checklist.md'],
       'source_dimensions':{'length_m':L,'half_beam_m':B,'depth_m':D,'strakes_per_side':N,'keel_ground_lift_m':KEEL_Y}},
      'frame_stations_u':RIB_U,'scantlings_m':{'plank_thickness':THICKNESS,'frame_section':[.055,.07],'keel_section':[.09,.15],'stem_section':[.09,.13],'gunwale_section':[.06,.07]},
      'construction_stages':states,'intended_joints':intended,'materials':materials,'triangles':counts,
      'deviations':['The game uses zero-thickness plank sheets. This asset closes every plank into a 22 mm wooden solid, including end grain.',
         'The last body station moves from |u|=0.985 to 0.965 before the same stem rabbet cap, preventing a folded solid at the end.',
         'The straight repair stock rotates its constant cross-section into the real straight centreline plane instead of shearing the original game sheet; the bow centre, 0.5 rad cant and 0.08 m/m rise are retained.',
         'Frame heels are seated 7 mm lower at the keel. Seat cleats and wider 2.60 m trestle cross-feet replace unsupported source contacts with physical bearing.',
         'This is an independent authored asset and hook contract. Three.js loading, live visibility, morph control, leak effects, water and carving progression still require a game adapter.'],
      'export':{'units':'metres','axes':'glTF +X source local right / repair side when work=1, +Y up, +Z bow','collision_mode':'one concave static collider per actual timber; state exports exclude later members','no_full_hull_proxy':True,
        'packed_scene':'stage3 visible, repair plank/pegs and all collision objects hidden; markers retained','morph':'repair_plank: Basis fitted, straight target weight=1-b*b*(3-2*b)'},
      'runtime_contract':{'source_hooks':hooks,'hook_implementation_delivered':False,'adapter_required':True,'no_mast_or_rudder':True}}
    hooks_doc={'schema':1,'source_commit':spec['source_commit'],'implementation':'declarative source-compatible hooks; no runtime adapter is included','anchors':anchor_details,
       'point_gap':{'default_i':0,'default_position_gltf_m':gltf(hp(-.42,.565,args.work_side,-.02)),'centre_anchor':'repair_gap (explicit i=0.5; not the source default)','formula':'hullPt(-0.42+0.84*i,0.565,workSide,off=-0.02) + KEEL_Y','parameter_i':[0,1]},
       'setGapPlank':{'grain_metadata':'grain_morph_paths_json stores exact fitted/straight section centroids; interpolate with the actual morph weight','stock_geometry':'orthogonal solid stock cross-section, fixed bow centre, source cant/rise retained','hide_values':[None,False],'bend_input':[0,1],'straight_morph_weight':'1-b*b*(3-2*b)','collision':'Moving repair plank has no static collision in canonical ship; its separate mesh may become an engine moving collider.'},
       'setPegs':{'prefix':'repair_peg_','count':5,'show':'index < clamp(k,0,5)'},'setTrim':{'prefix':'trim_','collider_prefix':'col_trim_','effective':'stage>=3 && trimOn','collision':'Toggle both matching visual and collision nodes; trim_collision.glb is the separate static collision subset.'},
       'setWater':{'height_above_keel_m':.27,'world_height_m':KEEL_Y+.27,'geometry':'No water FX mesh supplied; adapter clips its own water surface to the hull.'},
       'setLeak':{'sites':3,'states':{'0':'off','1':'wet seam and drops','2':'chalk mark','3':'oakum','4':'tarred seam'},'geometry':'Declared seam and ground-drip anchors; dynamic decals, drops and puddle growth belong to the adapter.'},
       'setMarks':{'father_anchor':'stem_mark_0','son_anchor':'stem_mark_1','progress':[0,1],'strokes_m':[
          [[-.034,.026,-.017,-.03],[-.017,-.03,0,.014],[0,.014,.017,-.03],[.017,-.03,.034,.026],[-.036,.042,.036,.042]],
          [[-.03,.028,.031,.021],[.001,.025,.008,-.034],[.008,-.034,.02,-.025]]]},
       'carve':{'default_duration_s':3,'min_duration_s':.1,'progress':'from+(1-from)*clamp(elapsed/sec,0,1)'},
       'source_work_side':{'1':'canonical selected repair side +X','-1':'rebuild with --work-side -1; all peg/leak/gap coordinates follow source mirroring','0':'stage0 uses same spine; a completed non-work boat is canonical stage3 plus the fitted repair_plank, without repair FX'}}
    for name,data in [('spec.json',spec),('states.json',state_doc),('hooks.json',hooks_doc),('navigation.json',navigation),('design.json',design)]:write(out/name,data)
    print('BOAT_FRAME_EXPORTED',counts,len(main_objects),'members',len(intended),'structural joint rules',flush=True)

if __name__=='__main__':main()
