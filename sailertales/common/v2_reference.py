"""Original reference construction, parameter adaptation and conservative seam repair.

Returns the original live construction context for interior and sailing variants.
No reference module is edited; profile-specific range fixes are runtime adapters.
"""
import ast
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys
import pickle
import types

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils import Matrix,Quaternion,Euler

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SOURCE=ROOT/'blender'
if not SOURCE.exists(): SOURCE=ROOT/'upstream'/'blender'


def read_adapter():
    sp=importlib.util.spec_from_file_location('_reference_profile',HERE/'rebuild_reference.py')
    mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
    return mod


def topology(o):
    bm=bmesh.new();bm.from_mesh(o.data)
    result={'boundary_edges':sum(e.is_boundary for e in bm.edges),
            'non_manifold_edges':sum(not e.is_manifold for e in bm.edges),
            'zero_area_faces':sum(f.calc_area()<1e-11 for f in bm.faces)}
    bm.free();return result


def stitch_collinear_seams(o,tolerance=2e-5):
    """Split coincident straight boundary edges at shared T junctions, then weld.

    Does not fill a missing face or close an intentionally open aperture. The
    reference plank cutter can leave two different subdivisions of one edge.
    """
    before=topology(o)
    bm=bmesh.new();bm.from_mesh(o.data)
    split_count=0
    for attempt in range(3):
        edges=[e for e in bm.edges if e.is_boundary]
        verts=list({v for e in edges for v in e.verts})
        splits=[]
        for e in edges:
            a,b=e.verts;delta=b.co-a.co;den=delta.length_squared
            if den<tolerance*tolerance:continue
            interior=[]
            for v in verts:
                if v in e.verts:continue
                t=(v.co-a.co).dot(delta)/den
                if t<=1e-5 or t>=1-1e-5:continue
                if (v.co-(a.co+t*delta)).length<=tolerance:
                    interior.append((t,v.co.copy()))
            if interior:splits.append((e,a,b,sorted(interior,key=lambda x:x[0])))
        if not splits:break
        for e,a,b,parts in splits:
            if not e.is_valid:continue
            current=e;start=a
            for _,point in parts:
                if not current.is_valid:break
                delta=b.co-start.co
                if delta.length_squared<1e-14:break
                fraction=(point-start.co).dot(delta)/delta.length_squared
                if not 1e-5<fraction<1-1e-5:continue
                _,new=bmesh.utils.edge_split(current,start,fraction)
                new.co=point;split_count+=1
                remaining=[ee for ee in new.link_edges if b in ee.verts]
                if not remaining:break
                current=remaining[0];start=new
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=tolerance)
    # Preserve winding: after a Boolean difference a disconnected inner cavity
    # intentionally carries negative signed volume. Recalculating every island
    # here would reverse its floor and ceiling before the hatch connects it.
    bm.to_mesh(o.data);bm.free();o.data.update()
    after=topology(o)
    return {'object':o.name,'before':before,'after':after,'edge_splits':split_count,
            'method':'split coincident collinear boundary subdivisions, weld within 20 micrometres'}


def parameter_ranges(pr,length):
    """The published scripts contain sampling brackets sized for the 28 m ship."""
    import rzedne
    original=rzedne.Kadlub.deck_c
    def deck_c(self,s):
        if self._dc is None:
            ss=np.arange(-length*.65,length*.65+.05,.05)
            zb=self.Zd(ss);y=self.H(ss,zb)
            self._dc=(ss,zb+self.K['WYPUKLOSC']*(y/self.K['POL_B'])**2)
        return np.interp(s,self._dc[0],self._dc[1])
    rzedne.Kadlub.deck_c=deck_c
    import kadlub
    init=kadlub.Poszycie.__init__
    # Source constructor only clamps its deck interpolation helper beyond +/-15.5.
    # Give the helper a profile-sized range before its later calls via Zd/Rr.
    def Zd(self,s):return self.kd.Zd(s)
    def Rr(self,s):return self.kd.rail_r(s)
    kadlub.Poszycie.Zd=Zd;kadlub.Poszycie.Rr=Rr
    def end(self,fn,fore):
        kd=self.kd;lo,hi=(0,length) if fore else (-length,0)
        for _ in range(52):
            m=(lo+hi)/2;h=float(fn(m))-float(kd.zk(m))
            difference=m-(kd.f_of_h(h) if fore else kd.a_of_h(h))
            if difference<0:lo=m
            else:hi=m
        return (lo+hi)/2
    kadlub.Poszycie._end_aft=lambda self,fn:end(self,fn,False)
    kadlub.Poszycie._end_fore=lambda self,fn:end(self,fn,True)


def build_reference(spec,out):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    adapter=read_adapter()
    cache=ROOT/'build'/'guide-brig'/'tekstury'
    texture_dir=out/'tekstury'
    if cache.exists() and cache.resolve()!=texture_dir.resolve():
        shutil.copytree(cache,texture_dir,dirs_exist_ok=True)
    adapter.textures(SOURCE,texture_dir)
    sys.path.insert(0,str(SOURCE))
    source=(SOURCE/'buduj.py').read_text(encoding='utf-8')
    tree=ast.parse(source,filename=str(SOURCE/'buduj.py'))
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and node.name=='main':
            node.body.append(ast.Return(value=ast.Name(id='ctx',ctx=ast.Load())))
    tree.body=[n for n in tree.body if not (isinstance(n,ast.Expr) and
               isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='main')]
    ast.fix_missing_locations(tree)
    ns={'__file__':str(SOURCE/'buduj.py'),'__name__':'reference_construction'}
    exec(compile(tree,str(SOURCE/'buduj.py'),'exec'),ns)
    provenance=adapter.configure(ns['PR'],spec)
    if spec['id']=='night-hull':
        scupper_reference_ports=list(ns['PR'].KADLUB['FURTY_S'])
        ns['PR'].UKLAD['DZIALA']['bez_dziala']=list(ns['PR'].KADLUB['FURTY_S'])
        ns['PR'].UKLAD['DZIALKA_RELINGOWE']=[]
        ns['PR'].KADLUB['FURTY_S']=[];ns['PR'].KADLUB['FURTY_ZAMKNIETE_S']=[]
        ns['PR'].SCHEMATY['a'].update(burta='farba_czarna',burta_gorna='farba_czarna',
                                    pas_furt='farba_czarna',pawez='farba_czarna',rzezby='drewno_ciemne')
        provenance['armament']='unarmed prologue vessel'
    parameter_ranges(ns['PR'],spec['length'])
    if spec['id']=='night-hull':
        # Scuppers still drain an unarmed deck. The source computes their sites
        # from gun-port centres and otherwise indexes an empty port list.
        import poklad
        reference_scupper_builder=poklad.listwy_i_szpigaty
        def unarmed_scuppers(ctx,ps):
            saved=ctx['K']['FURTY_S']
            ctx['K']['FURTY_S']=scupper_reference_ports
            try:return reference_scupper_builder(ctx,ps)
            finally:ctx['K']['FURTY_S']=saved
        poklad.listwy_i_szpigaty=unarmed_scuppers
        provenance['scuppers']='Reference inter-port drain spacing retained as drain sites on the unarmed hull; no gun ports are created.'
    import kadlub
    port_boolean=kadlub.otwor_steru
    def deferred_port(ctx):ctx['_v2_deferred_port']=True
    kadlub.otwor_steru=deferred_port
    # Record rope callsites, preserving original rope construction semantics.
    import olinowanie,model_rysunkowy
    model_rysunkowy.owin_lina(olinowanie)
    repairs=[]
    N=ns['N'];original_to_object=N.to_object
    def to_object(sk,*args,**kwargs):
        o=original_to_object(sk,*args,**kwargs)
        if sk.nazwa=='kadlub':
            r=stitch_collinear_seams(o);repairs.append(r)
            if r['after']['non_manifold_edges']:
                bpy.ops.wm.save_as_mainfile(filepath=str(out/'topology-failure.blend'))
                bm=bmesh.new();bm.from_mesh(o.data)
                print('NONMANIFOLD',[(tuple(e.verts[0].co),tuple(e.verts[1].co),len(e.link_faces),[f.index for f in e.link_faces]) for e in bm.edges if not e.is_manifold],flush=True)
                bm.free()
                raise RuntimeError('Reference hull seam remains non-manifold: '+str(r))
        return o
    N.to_object=to_object
    sys.argv=['buduj.py','--','--out',str(out),'--rendery','none','--bez-blend','--bez-ao']
    ctx=ns['main']()
    if ctx is None:raise RuntimeError('Missing original construction context')
    final=stitch_collinear_seams(ctx['obj']['kadlub']);repairs.append(final)
    if final['after']['non_manifold_edges']:
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'topology-failure.blend'))
        raise RuntimeError('Final source hull is not closed: '+str(final))
    # The source's later primitive cleanup may delete small faces around the
    # shaft. Cut the original documented shaft AFTER that cleanup instead.
    port_boolean(ctx)
    port_result=topology(ctx['obj']['kadlub'])
    if port_result['non_manifold_edges']:
        bpy.ops.wm.save_as_mainfile(filepath=str(out/'topology-failure.blend'))
        raise RuntimeError('Stern shaft cut is not closed: '+str(port_result))
    repairs.append({'method':'original stern-shaft boolean deferred until after primitive cleanup',
                    'after':port_result})
    provenance['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(SOURCE.glob('*.py'))}
    provenance['adapter_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    provenance['repairs']=repairs
    provenance['sampling_ranges']='extended from reference 28 m brackets to selected profile length'
    ctx['_v2_provenance']=provenance;ctx['_v2_reference_source']=str(SOURCE)
    ctx['_v2_spec']=spec
    (out/'reference-provenance.json').write_text(json.dumps(provenance,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('V2_REFERENCE_READY',spec['id'],json.dumps(final),flush=True)
    return ctx


def restore_mathutils(kind,values,order=None):
    if kind=='Vector':return Vector(values)
    if kind=='Matrix':return Matrix(values)
    if kind=='Quaternion':return Quaternion(values)
    if kind=='Euler':return Euler(values,order)
    raise ValueError(kind)


class ContextPickler(pickle.Pickler):
    def persistent_id(self,o):
        if isinstance(o,types.ModuleType):return ('module',o.__name__)
        if isinstance(o,bpy.types.ID):
            for category in ('objects','collections','materials','meshes','images','curves'):
                if getattr(bpy.data,category).get(o.name) is o:
                    return ('bpy',category,o.name)
            raise TypeError('Unrecorded Blender ID '+str(type(o)))
        return None
    def reducer_override(self,o):
        if isinstance(o,Vector):return (restore_mathutils,('Vector',tuple(o)))
        if isinstance(o,Matrix):return (restore_mathutils,('Matrix',tuple(tuple(r) for r in o)))
        if isinstance(o,Quaternion):return (restore_mathutils,('Quaternion',tuple(o)))
        if isinstance(o,Euler):return (restore_mathutils,('Euler',tuple(o),o.order))
        return NotImplemented


class ContextUnpickler(pickle.Unpickler):
    def persistent_load(self,key):
        if key[0]=='module':return __import__(key[1])
        if key[0]=='bpy':
            value=getattr(bpy.data,key[1]).get(key[2])
            if value is None:raise KeyError('Missing cached object '+str(key))
            return value
        raise ValueError('Unknown context reference '+str(key))


class ShaftAxis:
    def __init__(self,axis):
        (self.s0,self.z0),(self.s1,self.z1)=axis
    def __call__(self,z):
        return self.s0+(z-self.z0)*(self.s1-self.s0)/(self.z1-self.z0)


def cache_data(value):
    if isinstance(value,dict):
        return {k:cache_data(v) for k,v in value.items() if not isinstance(v,types.FunctionType)}
    if isinstance(value,list):return [cache_data(v) for v in value]
    if isinstance(value,tuple):return tuple(cache_data(v) for v in value)
    return value


def save_context(ctx,path):
    """Local trusted construction cache, avoiding a full rebuild per rig test."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(path.with_suffix('.blend')),compress=True)
    pr={k:v for k,v in vars(ctx['PR']).items() if k.isupper() and
        isinstance(v,(dict,list,tuple,float,int,bool,str))}
    keys=('kd','K','statek','kol','obj','schemat','out','root','snow','rig','liny','belay',
          'liny_stanowisk','pokl_z','qd_z','kolki_nagielbankow','kolki_kolkownic',
          'ster_otwor','ster_os','ster_glowica','naped_domyslny','warianty_napedu',
          'stanowiska','przeszkody','przejscia','schody','_v2_spec','_v2_provenance','_v2_reference_source')
    value=cache_data({'pr':pr,'ctx':{k:ctx[k] for k in keys if k in ctx}})
    temporary=path.with_suffix('.pickle.part')
    with temporary.open('wb') as f:ContextPickler(f,protocol=4).dump(value)
    temporary.replace(path.with_suffix('.pickle'))


def load_context(path):
    """Load only a cache produced locally by save_context, never untrusted input."""
    path=Path(path);sys.path.insert(0,str(SOURCE))
    bpy.ops.wm.open_mainfile(filepath=str(path.with_suffix('.blend')))
    with path.with_suffix('.pickle').open('rb') as f:value=ContextUnpickler(f).load()
    import parametry,rzedne,kadlub
    for key,v in value['pr'].items():setattr(parametry,key,v)
    ctx=value['ctx'];ctx['PR']=parametry
    import narzedzia
    for name,material in parametry.MATERIALY.items():
        found=bpy.data.materials.get(name)
        if found is not None:
            narzedzia.MATERIALY_REJESTR[name]=found
            narzedzia.KAFLE[name]=material.get('kafel',(1,1))
    if bpy.data.materials.get('krata'):
        narzedzia.MATERIALY_REJESTR['krata']=bpy.data.materials['krata'];narzedzia.KAFLE['krata']=(.56,.56)
    if 'ster_otwor' in ctx:ctx['ster_otwor']['os']=ShaftAxis(ctx['ster_os'])
    parameter_ranges(parametry,ctx['_v2_spec']['length'])
    ctx['poszycie']=kadlub.Poszycie(ctx['kd'],ctx['K'])
    return ctx
