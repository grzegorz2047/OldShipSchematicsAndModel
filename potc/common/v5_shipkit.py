"""Detailed ordinary POTC reconstructions with researched connected interiors.

The frozen v4 silhouette/gun/rig builders remain reusable primitives; v5 owns
all new deck architecture, physical interior detail and package metadata.
"""
import argparse,json,sys
from pathlib import Path
import bpy
from mathutils import Vector
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path[:0]=[str(HERE),str(ROOT/'sailertales/common')]
import v4_shipkit as K
from v4_shipkit import safe_name,p,rgba,_curve


class Context(K.Context):
    def __init__(self,spec):
        layout=spec.get('detailed_layout',{});hold=layout.get('hold') or {}
        if layout.get('kind')!='open_boat' and hold:
            for mast in spec.get('rig',{}).get('masts',[]):
                at=float(mast['at'])
                if float(hold.get('from',-.38))<=at<=float(hold.get('to',.34)):
                    mast['heel_z_m']=float(hold['floor_z_m'])+.10+K._curve(spec['hull']['profile'],at,3)*.35
                    mast['heel_basis']='Authored interior mast step above keelson through real deck partner apertures.'
                elif layout.get('cabin') and float(layout['cabin']['from'])<=at<=float(layout['cabin']['to']):
                    mast['heel_z_m']=float(layout['cabin']['floor_z_m'])+.10+K._curve(spec['hull']['profile'],at,3)
                    mast['heel_basis']='Authored aft mast step reached through the true cabin and raised-deck mortises.'
        super().__init__(spec)
        from v5_materials import register_materials
        register_materials(self)
        self.portals=[];self.detail_features={};self.rig_ledger={};self._joint_pairs=set()
    def collider(self,obj):
        if obj.get('kind') in('partition','stair','structure'):
            obj['construction_kind']=obj['kind'];obj['kind']='surface'
        return super().collider(obj)
    def profile_curve(self,s,index):return _curve(self.profile,s/self.L,index)
    def joint(self,a,b,reason):
        a=a.name if hasattr(a,'name') else str(a);b=b.name if hasattr(b,'name') else str(b)
        if a==b:return
        key=tuple(sorted((a,b)))
        if key in self._joint_pairs:return
        self._joint_pairs.add(key);self.joints.append({'a':a,'b':b,'reason':reason})


def sync_colliders(ctx):
    """Refresh exact visual copies after legitimate architectural hole cutting."""
    sources={o.name:o for o in ctx.vis if o.type=='MESH'}
    for collider in ctx.col:
        source=sources.get(collider.get('visual_source'))
        if source is None:continue
        old=collider.data;collider.data=source.data.copy();collider.data.materials.clear();collider.data.materials.append(ctx.materials['collision'])
        collider.matrix_world=source.matrix_world.copy()
        if old.users==0:bpy.data.meshes.remove(old)


def primary_fittings_with_final_guns(ctx):
    """Use final solid gun bounds without treating curved rope boxes as walls.

    The ropes remain in the scene and are restored to the complete visual
    inventory immediately; the independent all-role E1 audit still tests them.
    """
    original=ctx.vis;solids=[o for o in original if not(o.name.startswith('gun_') and o.get('kind')=='rope')]
    ctx.vis=list(solids);before=len(ctx.vis)
    try:K.fittings(ctx)
    finally:
        added=ctx.vis[before:];ctx.vis=original+added
    ctx.primary_fitting_plan={'method':'Final solid gun/cascabel bounds; curved rope bounding boxes omitted only from primary placement, all ropes retained for actual scene collision tests.','curved_rope_boxes_omitted':len(original)-len(solids)}


def _physical_joints(ctx):
    """Keep explicitly authored joints only where real surfaces can meet."""
    bounds={}
    for obj in ctx.vis:
        if obj.type!='MESH':continue
        points=[obj.matrix_world@v.co for v in obj.data.vertices]
        if not points:continue
        bounds[obj.name]=([min(q[k] for q in points) for k in range(3)],[max(q[k] for q in points) for k in range(3)])
    def nearby(row):
        if row['a'] not in bounds or row['b'] not in bounds:return False
        a,b=bounds[row['a']],bounds[row['b']]
        return all(a[0][k]<=b[1][k]+.035 and b[0][k]<=a[1][k]+.035 for k in range(3))
    ctx.joints=[row for row in ctx.joints if nearby(row)]


def build(spec,out):
    source_dir=Path(spec).resolve().parent if isinstance(spec,(str,Path)) else Path(out).resolve()
    if isinstance(spec,(str,Path)):spec=json.loads(Path(spec).read_text())
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ctx=Context(spec);ctx.source_dir=source_dir
    from v5_decks import build_decks
    from v4_rig import build_rig
    from v5_outfit import build_outfit
    from v5_export import finish
    print('V5_STAGE hull',spec['id'],flush=True);K.hull(ctx)
    print('V5_STAGE deck_architecture',flush=True);build_decks(ctx)
    print('V5_STAGE battery',flush=True);K.guns(ctx)
    from v5_gun_details import build_gun_details
    build_gun_details(spec,ctx)
    gun_rig_ledger=ctx.rig_ledger
    print('V5_STAGE primary_fittings',flush=True);primary_fittings_with_final_guns(ctx)
    print('V5_STAGE working_rig',flush=True);rig=build_rig(spec,ctx)
    rig.setdefault('ropes',[]).extend(name for name in gun_rig_ledger.get('ropes',[]) if name not in rig.get('ropes',[]))
    attached={row['rope'] for row in rig.get('attachments',[])}
    rig.setdefault('attachments',[]).extend(row for row in gun_rig_ledger.get('attachments',[]) if row['rope'] not in attached)
    rig['rope_count']=len(rig['ropes']);ctx.rig_ledger=rig
    from v5_decks import build_mast_partners
    build_mast_partners(ctx)
    print('V5_STAGE detailed_outfit',flush=True);outfit=build_outfit(spec,ctx)
    if isinstance(outfit,dict):
        ctx.outfit_ledger=outfit
        ctx.detail_contract.setdefault('feature_groups',[]).extend(outfit.get('feature_groups',[]))
    if ctx.layout.get('kind')=='open_boat':
        from v5_openboat_details import complete_openboat_details
        ctx.outfit_ledger['open_boat_completion']=complete_openboat_details(ctx)
    for group,names in ctx.detail_features.items():
        names=list(dict.fromkeys(names))
        existing=next((g for g in ctx.detail_contract.setdefault('feature_groups',[]) if g['id']==group),None)
        if existing:
            existing['nodes']=list(dict.fromkeys(existing.get('nodes',[])+names));existing['required']=True
            existing['minimum_instances']=max(existing.get('minimum_instances',1),min(3,len(names)))
            existing.pop('reason',None)
        else:ctx.detail_contract['feature_groups'].append({'id':group,'nodes':names,'minimum_instances':min(3,len(names)),'required':True})
    # Room furnishers report actual mesh names, never proxy navigation labels.
    for room in ctx.rooms:
        room['furnishing_nodes']=[o.name for o in ctx.vis if o.get('room_id')==room['id'] and o.get('detail_feature') in ('interior_furniture','stowage')]
    from v5_decks import bind_battery_rooms
    bind_battery_rooms(ctx)
    ctx.marker('asset_origin',Vector((0,0,0)),{'units':'metres','waterline':True,'detail_version':5})
    from v5_decks import finalize_contract
    finalize_contract(ctx)
    from v5_decks import structural_bearing_joints
    ctx.structural_bearings=structural_bearing_joints(ctx)
    sync_colliders(ctx);_physical_joints(ctx)
    return finish(ctx,spec,Path(out),rig)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('spec',type=Path);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:]);build(args.spec,args.out)
