"""Closed plank reconstruction of the active SailerTales capsized rescue prop.

Blender: --python sailertales/capsized-boat/build.py --
  sailertales/capsized-boat/spec.json --out build/final/capsized-boat
The frozen common modules are used unchanged. Authoring x,-s,height -> glTF x,height,s.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
COMMON=ROOT/'sailertales/common'
sys.path.insert(0,str(COMMON))
import v2_boats as B
from v2_materials import upgrade_scene
from v2_export import finalize

LENGTH=6.5;HALF_BEAM=.86;DEPTH=.92;BASE=.31


def write(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def p(x,s,height):return Vector((x,-s,height))
def q(v):return [float(v.x),float(v.z),float(-v.y)]
def rocker(u):return .12*abs(u)**3
def sheer(u):return DEPTH*(1+.1*u*u+.42*u**4)
def halfbeam(u):return HALF_BEAM*max(0,1-abs(u)**3)**.52


def stem_at(k,side):
    k=max(0,min(1,k));low=rocker(.985)-.07;high=sheer(1)+.16
    return (low+(high-low)*k**1.35,side*LENGTH/2*(.975+.03*math.sin(k*math.pi/2)))


def stem_s(height):
    low=rocker(.985)-.07;high=sheer(1)+.16
    k=max(0,min(1,(height-low)/(high-low)))**(1/1.35)
    return LENGTH/2*(.975+.03*math.sin(k*math.pi/2))


def hull_point(u,t,side,off=0,cap=False):
    a=min(1.06,t)*math.pi/2
    x=halfbeam(u)*math.sin(min(a,math.pi/2))**.85
    y=rocker(u)+(sheer(u)-rocker(u))*(1-max(0,math.cos(a))**1.3)+max(0,t-1)*.5
    x=max(0,x-off*math.sin(a));y+=off*math.cos(a)
    s=u*LENGTH/2
    if cap:
        x=.042;s=math.copysign(stem_s(y)-.03,u)
    # Source rotation.z=pi in Three.js: negate source x and y, keep +Z bow.
    return p(-side*x,s,BASE-y)


def closed_strake(j,side):
    nu,nt=64,4
    stations=[(-.985,True)]+[(-.985+1.97*i/nu,False) for i in range(nu+1)]+[(.985,True)]
    t0=j/8;t1=(j+1)/8+.012
    verts=[];params=[]
    for inner in (False,True):
        for u,cap in stations:
            for k in range(nt+1):
                f=k/nt;t=t0+(t1-t0)*f
                offset=(.028 if inner else 0)-.014*(1-f)
                verts.append(hull_point(u,t,side,offset,cap));params.append((u,t,inner))
    row=nt+1;n=len(stations);layer=row*n;faces=[]
    for inner in (0,1):
        base=inner*layer
        for i in range(n-1):
            for k in range(nt):
                a=base+i*row+k;faces.append((a,a+1,a+1+row,a+row))
    for i in range(n-1):
        for k in (0,nt):
            a=i*row+k;b=(i+1)*row+k;faces.append((a,b,b+layer,a+layer))
    for i in (0,n-1):
        for k in range(nt):
            a=i*row+k;faces.append((a,a+1,a+1+layer,a+layer))
    flank='port' if side<0 else 'starboard'
    grain_path=[hull_point(u,(t0+t1)/2,side,-.007,cap) for u,cap in stations]
    o=B.mesh('strake_%s_%02d'%(flank,j+1),verts,faces,'dark',True,'hull',grain_path=grain_path)
    # Biofilm is a true conformal material layer, not an intersecting mesh ribbon.
    o.data.materials.append(B.MATS['algae'])
    rng=random.Random(1700+j+(0 if side<0 else 100))
    for face in o.data.polygons:
        ids=list(face.vertices);outer=all(v<layer for v in ids);inside=all(v>=layer for v in ids)
        face.use_smooth=outer or inside
        if outer:
            u=sum(params[v][0] for v in ids)/len(ids);t=sum(params[v][1] for v in ids)/len(ids)
            if abs(u)<.96 and .74<t<.98 and rng.random()>.07:face.material_index=1
    o['construction']='individually closed lapstrake, cap lands on stem rabbet'
    return o


def keel():
    verts=[];faces=[];n=65
    for i in range(n):
        u=-.975+1.95*i/(n-1);s=u*LENGTH/2;top=.38-rocker(u)
        verts.extend([p(-.045,s,top-.15),p(.045,s,top-.15),p(.045,s,top),p(-.045,s,top)])
    for i in range(n-1):
        for k in range(4):
            a=i*4+k;b=i*4+(k+1)%4;faces.append((a,b,b+4,a+4))
    faces.extend([(3,2,1,0),tuple((n-1)*4+k for k in range(4))])
    return B.mesh('keel',verts,faces,'tar',True,'hull',grain_path=[p(0,(-.975+1.95*i/64)*LENGTH/2,.305-rocker(-.975+1.95*i/64)) for i in range(65)])


def oriented_box(name,center,axis,width,length,thickness,mat='wood'):
    axis=Vector(axis).normalized();across=axis.cross(Vector((0,0,1))).normalized();up=across.cross(axis).normalized()
    verts=[center+across*x*width/2+axis*y*length/2+up*z*thickness/2 for z in (-1,1) for y in (-1,1) for x in (-1,1)]
    faces=[(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]
    return B.mesh(name,verts,faces,mat,False,'fitting',grain=axis)


def float_details(hulls):
    # Keep adjuncts together under the prop root; leave a real gap at the shell.
    center=p(1.25,-.6,.02);axis=p(math.sin(.35),math.cos(.35),.012).normalized()
    # The source oar is six-sided. Its closed20-triangle solid is retained by
    # the frozen LOD builder, avoiding collapse of this thin shaft to one face.
    B.tube('floating_oar_shaft',[center-axis*1.3,center+axis*1.3],.025,'wood',False,'fitting',6)
    oriented_box('floating_oar_blade',center+axis*1.45,axis,.17,.50,.025)
    support,normal=surface_at(.1,-LENGTH/2+.1,hulls)
    attachment=support+normal*.005
    rope=[attachment,p(.3,-LENGTH/2-.8,.02),p(.8,-LENGTH/2-1.9,-.01),p(.5,-LENGTH/2-3,0)]
    B.tube('trailing_hemp_rope',rope,.011,'rope',False,'rope',8)
    for v in B.VIS[-1:]:v['free_end']='source trailing rescue debris; not a working sheet'
    B.empty('rope_attachment_anchor',attachment,kind='marker',interaction='rope tied to source after planking')
    verts=[];faces=[];nu,nv=20,16
    for layer in (0,1):
        for j in range(nv+1):
            y=-.55+1.1*j/nv
            for i in range(nu+1):
                x=-.75+1.5*i/nu
                h=.07*math.sin(x*5.1+y*2.3)+.05*math.cos(y*6.3)-.06*abs(x)-layer*.002
                xx=x*math.cos(.5)+y*math.sin(.5);ss=-x*math.sin(.5)+y*math.cos(.5)
                verts.append(p(-1.70+xx,1.2+ss,h))
    n=(nu+1)*(nv+1)
    for layer in (0,1):
        for j in range(nv):
            for i in range(nu):
                a=layer*n+j*(nu+1)+i;faces.append((a,a+1,a+nu+2,a+nu+1))
    for j in range(nv):
        for i in (0,nu):
            a=j*(nu+1)+i;b=a+nu+1;faces.append((a,b,b+n,a+n))
    for i in range(nu):
        for j in (0,nv):
            a=j*(nu+1)+i;faces.append((a,a+1,a+1+n,a+n))
    cloth=B.mesh('floating_sailcloth',verts,faces,'canvas',False,'fitting')
    cloth['cloth_state']='floating loose rag; closed 2mm surface, no deployed rig'
    for face in cloth.data.polygons:face.use_smooth=True
    return center


def surface_at(x,s,objects):
    verts=[];faces=[]
    for o in objects:
        o.data.calc_loop_triangles();base=len(verts)
        verts.extend(o.matrix_world@v.co for v in o.data.vertices)
        faces.extend(tuple(base+i for i in tri.vertices) for tri in o.data.loop_triangles)
    tree=BVHTree.FromPolygons(verts,faces,all_triangles=True)
    hit,normal,index,distance=tree.ray_cast(p(x,s,2),Vector((0,0,-1)),5)
    if hit is None:raise RuntimeError('No delivered hull support for the source rescue seat')
    return hit,normal


def precise_joints(objects):
    """Only declared timber interfaces whose real object bounds meet."""
    named={o.name:o for o in objects if o.type=='MESH'}
    bounds={}
    for name,o in named.items():
        points=[o.matrix_world@v.co for v in o.data.vertices]
        bounds[name]=([min(q[k] for q in points) for k in range(3)],
                      [max(q[k] for q in points) for k in range(3)])
    result=[]
    def joint(a,b,reason):
        if a not in bounds or b not in bounds:return
        aa,bb=bounds[a],bounds[b]
        if any(max(aa[0][k],bb[0][k])>min(aa[1][k],bb[1][k])+.002 for k in range(3)):return
        result.append({'a':a,'b':b,'reason':reason,'evidence':'specific source construction interface; actual world AABBs meet within2mm'})
    for flank in ('port','starboard'):
        for j in range(1,8):joint('strake_%s_%02d'%(flank,j),'strake_%s_%02d'%(flank,j+1),
            'These two adjacent closed lapstrakes share their specified caulked seam on the same flank.')
        joint('strake_%s_01'%flank,'keel','This flank garboard is housed in the keel rabbet.')
        joint('strake_%s_08'%flank,'gunwale_'+flank,'The gunwale cap lands on this flank top sheerstrake.')
        for title in ('bow','stern'):
            for j in range(1,9):joint('strake_%s_%02d'%(flank,j),'stem_'+title,
                'This strake end cap lands at this specific stem rabbet, closing the source pointed end.')
        # Source bench ends bear on the seventh strake at t≈0.8. A whole-hull
        # wildcard would hide a misplaced bench penetrating a lower garboard.
        for j in range(3):joint('submerged_bench_%02d'%j,'strake_%s_07'%flank,
            'This source submerged bench end bears against the inner seventh strake at its station.')
    joint('strake_port_01','strake_starboard_01','The two garboards meet at their housed centreline seam, under the keel.')
    for title in ('bow','stern'):joint('keel','stem_'+title,'This stem heel and the keel end form a structural scarf joint.')
    joint('floating_oar_shaft','floating_oar_blade','This single oar loom is housed in its blade.')
    source_rules=list(result)
    for level in (1,2):
        for row in source_rules:
            result.append({**row,'a':'lod%d_'%level+row['a'],'b':'lod%d_'%level+row['b'],
                'source_interface':[row['a'],row['b']],
                'evidence':'exact LOD node copies of this specific source construction interface; independently checked after import'})
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('spec');ap.add_argument('--out',required=True)
    a=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);spec_path=Path(a.spec).resolve();spec=json.loads(spec_path.read_text())
    fixed={'length':LENGTH,'beam':HALF_BEAM*2,'depth_amidships':DEPTH,
           'keel_top_above_calm_water':.38,'strakes_per_side':8,'plank_thickness':.028}
    for key,value in fixed.items():
        if not math.isclose(float(spec[key]),value,abs_tol=1e-10):
            raise ValueError('This fixed source-profile prop requires '+key+' = '+str(value))
    out=Path(a.out).resolve();(out/'model').mkdir(parents=True,exist_ok=True);(out/'previews').mkdir(exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    B.materials(out)
    algae=B.MATS['wood'].copy();algae.name='algae_coated_wood';algae['uv_tile_m']=(2.,2.)
    bs=next(n for n in algae.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    previous=bs.inputs['Base Color'].links[0].from_socket
    mix=algae.node_tree.nodes.new('ShaderNodeMix');mix.data_type='RGBA';mix.blend_type='MULTIPLY'
    mix.inputs['Factor'].default_value=1;mix.inputs[7].default_value=(.21,.57,.59,1)
    algae.node_tree.links.new(previous,mix.inputs[6]);algae.node_tree.links.new(mix.outputs[2],bs.inputs['Base Color'])
    for link in list(bs.inputs['Roughness'].links):algae.node_tree.links.remove(link)
    bs.inputs['Roughness'].default_value=.96
    for link in list(bs.inputs['Metallic'].links):algae.node_tree.links.remove(link)
    bs.inputs['Metallic'].default_value=0
    B.MATS['algae']=algae
    hulls=[closed_strake(j,side) for side in (-1,1) for j in range(8)]
    keel()
    for side,title in ((-1,'stern'),(1,'bow')):
        path=[]
        for i in range(33):
            yy,ss=stem_at(i/32,side);path.append(p(0,ss,BASE-yy))
        B.tube('stem_'+title,path,.045,'tar',True,'hull',12)
    for side in (-1,1):
        pts=[hull_point(-.975+1.95*i/48,1.02,side,-.02) for i in range(49)]
        B.tube('gunwale_'+('port' if side<0 else 'starboard'),pts,.032,'tar',True,'fitting',10)
    for i,u in enumerate((-.5,.02,.5)):
        B.box('submerged_bench_%02d'%i,p(0,u*LENGTH/2,BASE-sheer(u)+.2),(2*halfbeam(u)*.95,.24,.035),'wood',True,'fitting',Vector((1,0,0)))
    bpy.context.view_layer.update()
    oar=float_details(hulls)
    material_ledger=upgrade_scene(B.VIS)
    material_ledger['additional_materials']=[{'material':'algae_coated_wood','source':'original guide procedural wood PBR',
        'method':'conformal face coating, linear green-wash multiplier','linear_multiplier':[.21,.57,.59],'roughness':.96}]
    bpy.context.view_layer.update()
    support,normal=surface_at(.4,0,hulls)
    seat=p(.4,0,support.z-.02)
    B.empty('asset_origin',p(0,0,0),kind='marker',vessel_id=spec['id'],origin_description='source calm-water root; capsizing baked once')
    B.empty('seat_anchor',seat,kind='marker',interaction='father_rescue_sit',surface_inset_m=.02,source_seat_y=.185)
    B.empty('cling_anchor',p(1.15,0,-1.05),kind='marker',interaction='father_rescue_cling',follow_heave=False,follow_tilt=False)
    B.empty('keel_top_anchor',p(0,0,.38),kind='marker',interaction='calm_water_keel_top')
    B.empty('floating_oar_anchor',oar,kind='marker',interaction='floating_source_debris')
    nav={'schema':2,'units':'metres','axes':'glTF +X port, +Y up, +Z bow','routes':[],
         'source_commit':spec['source_commit'],'walkable':False,'interaction_mode':'actor rides explicit seat/cling anchors'}
    states={'schema':1,'kind':'capsized-boat','states':[{'id':'capsized','model':'model/ship.glb','collision':'model/collision.glb'}],
            'components':[],'anchors':{'seat_anchor':q(seat),'cling_anchor':[1.15,-1.05,0],'keel_top_anchor':[0,.38,0]},
            'seat':{'node':'seat_anchor'},'float':{'lift':0,'span':2.4,'beam':.7,'bob':.03,'sway':.09,'tilt':.7},
            'hooks':{'seat':'seat_anchor','float':'engine-owned'}}
    contract={'schema':1,'game_type':'capsized_boat','root_axes':'metres, +Y up, +Z bow; origin calm water',
      'capsizing':'already baked; do not apply an additional pi rotation',
      'actor_branches':{'sit':{'condition':"ctx.vars.ojciec === 'kil'",'node':'seat_anchor','pose':'sit','wave':True,'yaw':math.pi/2,'follow_prop_heave':True,'follow_prop_pitch_roll':True},
                        'cling':{'condition':"ctx.vars.ojciec !== 'kil'",'node':'cling_anchor','pose':'cling','yaw':-math.pi/2,'source_local_gltf':[1.15,-1.05,0],'follow_prop_heave':False,'follow_prop_pitch_roll':False}},
      'float':states['float'],'mission_instances':{'a1_3':{'id':'lodz_ojca','yaw_rad':.6,'drift':'windTo * 0.2 m/s'},'dev_plac_zabaw':{'yaw_rad':.6}},
      'adapter_required':['Expose seat_anchor coordinates relative to the prop root as prop.seat; apply the prop/world transform only through actors.ride.','Use source floatStep once at the prop root; adjunct oar, rope and cloth move with the same root.','For sit use actor ride with heave/pitch/roll; for cling follow source horizontal pose without heave/tilt.','Do not use obsolete seat fallback (0.45,0.85,0).','The source floating prop is non-solid; delivered collision meshes are optional query/picking geometry, not a standing deck.']}
    joints=precise_joints(B.VIS)
    design={'schema':2,'id':spec['id'],'construction':'eight individually closed lapstrakes per side, curved keel and stems, gunwales and the source three submerged benches; no fabricated ribs, mast or walking deck',
       'basis':{'guide_commit':'2e6f7e922e95396722376d42f3e2e0a12256029e','guide_chapters':['03','08','09','13','14'],'game_commit':spec['source_commit'],'source_files_sha256':spec['source_files_sha256'],'formulas':'ported HULL/hullB/hullSheer/hullRocker/hullPt/stemAt from SailerTales hull.js'},
       'source_reference_seat_gltf_m':[.4,.185,0],'delivered_seat_gltf_m':q(seat),'seat_support_gltf_m':q(support),'seat_support_normal_blender':list(normal),'seat_hip_inset_m':.02,
       'origin':{'position_gltf_m':[0,0,0],'meaning':'source calm-water prop root'},'capsize_baked':True,'float':states['float'],
       'intended_joints':joints,'materials':material_ledger,'spec_sha256':hashlib.sha256(spec_path.read_bytes()).hexdigest(),
       'game_deviations':['Source render surfaces are given real 28mm closed plank thickness, with extra stations for smooth curvature.','Keel top is geometrically 0.38m, following the source stated intent; the source primitive beam thickness would otherwise place its upper face above that value.','Seat height is fitted to delivered outer planking at source x=0.4m, with the same 20mm hip inset. Reference source seat is recorded separately.','Algae is a conformal material coating on the original t=0.74..0.98 band, avoiding a floating or penetrating overlay.','Oar is turned along the side and cloth moved 0.25m outward to avoid source decorative overlaps; source dimensions, floating character and shared root are retained.','No cabin, standing route, mast or rudder is invented for this flooded inverted prop.']}
    write(out/'states.json',states);write(out/'integration-contract.json',contract)
    result=finalize(spec,out,B.VIS+B.MARKERS,B.COL,nav,design,generate_lods=True)
    print('CAPSIZED_COMPLETE',result['triangles'],'seat',q(seat),'support',q(support),flush=True)


if __name__=='__main__':main()
