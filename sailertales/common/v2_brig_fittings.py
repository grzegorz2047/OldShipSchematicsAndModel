"""Separate the working rig's real lead blocks, eyes and their supported falls.

The reference-data adaptation originally stacked several independent lead blocks
at one point. Keep separate lead sheaves, move their complete rope turns with
them, and retain a short physical strop between each block and its fixing eye.
"""
import copy
import json
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def point(q):return Vector((q[0],-q[2],q[1]))
def gltf(q):return [q.x,q.z,-q.y]


def remove(obj):
    if obj is not None:
        me=obj.data if obj.type=='MESH' else None
        bpy.data.objects.remove(obj,do_unlink=True)
        if me is not None and me.users==0:bpy.data.meshes.remove(me)


def cap_separated_strops(obj):
    """Close only small source-fitting cuts exposed by material separation."""
    bm=bmesh.new();bm.from_mesh(obj.data)
    unseen={e for e in bm.edges if e.is_boundary};loops=[];skipped=[];caps=0
    while unseen:
        edge=unseen.pop();edges={edge};todo=[edge];vertices=set(edge.verts)
        while todo:
            q=todo.pop()
            for v in q.verts:
                for e in v.link_edges:
                    if e in unseen:
                        unseen.remove(e);edges.add(e);todo.append(e);vertices.update(e.verts)
        span=Vector(tuple(max(v.co[k] for v in vertices)-min(v.co[k] for v in vertices)
                          for k in range(3))).length
        closed=all(sum(e in edges for e in v.link_edges)==2 for v in vertices)
        if closed and len(edges)<=16 and span<=.22:
            adjacent=[f.material_index for e in edges for f in e.link_faces]
            material=max(set(adjacent),key=adjacent.count) if adjacent else 0
            result=bmesh.ops.holes_fill(bm,edges=list(edges),sides=16)
            for face in result.get('faces',[]):face.material_index=material
            caps+=len(result.get('faces',[]));loops.append({'edges':len(edges),'diameter_m':span})
        else:skipped.append({'edges':len(edges),'diameter_m':span,'simple_loop':closed})
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(obj.data);bm.free();obj.data.update()
    return {'object':obj.name,'small_strop_contact_caps':caps,'capped_loops':loops,
        'unmodified_large_or_branched_openings':skipped,
        'reason':'The source unioned wood fitting and tarred strop; separating their materials exposes small hidden contact cuts.'}


def rail_eye(ctx,side,s):
    kd,K=ctx['kd'],ctx['K']
    z=float(kd.Zd(s)+kd.rail_r(s))
    x=side*(float(kd.H(s,z)[0])-K['NADBURCIE_GR']/2)
    return Vector((x,-s,z+K['RELING_GR']+.025))


def world_tree(obj):
    dg=bpy.context.evaluated_depsgraph_get()
    me=bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    vertices=[obj.matrix_world@v.co for v in me.vertices]
    tree=BVHTree.FromPolygons(vertices,[list(p.vertices) for p in me.polygons])
    bpy.data.meshes.remove(me)
    return tree


def finish(ctx,out=None):
    import v2_rigging as rig
    paths=copy.deepcopy(rig.RIGGING_PATHS)
    moved=[];changed={};strops={};rules=[];used_eyes=set()
    eyes=[o for o in rig.ASSET.objects if o.type=='MESH' and o.name.startswith('sheet_eye_')]
    eyes.sort(key=lambda o:int(o.name.rsplit('_',1)[-1]))
    rail=bpy.data.objects.get('hull_rail') or bpy.data.objects.get('kadlub_reling')
    if rail:
        for eye in eyes:
            rules.append({'a':rail.name,'b':eye.name,
                'reason':'The forged rail eye has its lower fixing sunk into the timber rail cap, like the guide deck-eye fasteners.'})

    # Three distinct braces need three supported turning sheaves, not three
    # intersecting wooden housings over coincident copies of one eye.
    for side in (1,-1):
        rows=[(name,r) for name,r in paths.items() if r.get('mesh_object')=='rigging_running_sailing'
              and 'fore_' in r.get('source_rope','') and '_brace_' in r.get('source_rope','')
              and ('_port' in r['source_rope'])==(side==1)
              and bpy.data.objects.get('brace_turning_block_'+str(r.get('source_line_id'))) is not None]
        # Globals retain source_line_id; source_rope is added by _paths_report.
        if not rows:
            rows=[]
            for name,r in paths.items():
                line_id=r.get('source_line_id')
                if r.get('mesh_object')!='rigging_running_sailing' or line_id is None:continue
                logical=rig.RIG['lines'][line_id]['rope']
                if logical.startswith('fore_') and '_brace_' in logical and ('_port' in logical)==(side==1) and bpy.data.objects.get('brace_turning_block_'+str(line_id)) is not None:
                    r['source_rope']=logical;rows.append((name,r))
        rows.sort(key=lambda item:item[1]['source_line_id'])
        for index,(name,row) in enumerate(rows):
            points=[point(q) for q in row['points_gltf_m']]
            old=points[1].copy();old_eye=old-Vector((0,0,.156))
            candidates=[o for o in eyes if o.name not in used_eyes and (o.matrix_world.translation-old_eye).length<.01]
            if not candidates:raise RuntimeError('Missing source brace rail eye: '+name)
            eye=candidates[0];used_eyes.add(eye.name)
            target_eye=rail_eye(ctx,side,-old.y-index*.22)
            eye.location+=target_eye-eye.matrix_world.translation
            target=target_eye+Vector((0,0,.256))
            block=bpy.data.objects['brace_turning_block_'+str(row['source_line_id'])]
            block.location+=target-old
            points[1]=target;changed[name]=points
            strops['brace_turning_strop_'+str(row['source_line_id'])]=[target_eye+Vector((0,0,.036)),target]
            moved.append({'block':block.name,'rail_eye':eye.name,'from_gltf_m':gltf(old),'to_gltf_m':gltf(target),
                'reason':'separate brace sheave above its own rail eye; a short tarred strop spans the clear gap'})

    # Lift lead blocks stood inside the main fife rail. Place each complete lead
    # beside it, clear of the port companionway approach, with distinct sheaves.
    main_ids={1:[1172,1228,1289],-1:[1199,1256,1304]}
    for side,ids in main_ids.items():
        for index,line_id in enumerate(ids):
            name='rope_static_line_'+str(line_id)
            if name not in paths:continue
            row=paths[name];points=[point(q) for q in row['points_gltf_m']]
            old=points[1].copy();x=side*1.05;s=-(1.8-index*.22)
            z=float(ctx['kd'].deck_z(s,x));target=Vector((x,-s,z+.25))
            block=bpy.data.objects['deck_lead_block_'+str(line_id)]
            block.location+=target-old;points[1]=target;changed[name]=points
            foot=Vector((x,-s,z+.06))
            strops['deck_lead_strop_'+str(line_id)]=[foot,target]
            bpy.ops.mesh.primitive_torus_add(major_radius=.030,minor_radius=.007,
                major_segments=12,minor_segments=6,location=(x,-s,z+.035),rotation=(math.pi/2,0,0))
            eye=bpy.context.object;eye.name='lift_lead_eye_'+str(line_id)
            for col in list(eye.users_collection):col.objects.unlink(eye)
            rig.ASSET.objects.link(eye);eye.data.materials.append(bpy.data.materials.get('iron') or bpy.data.materials.get('v2_iron'))
            eye['kind']='fitting';eye['asset_role']='visual'
            moved.append({'block':block.name,'deck_eye':eye.name,'from_gltf_m':gltf(old),'to_gltf_m':gltf(target),
                'reason':'separate lift lead outside the main fife rail, supported by its own deck eye and strop'})

    # Three halliard falls occupy three independent sheaves; separate the lead
    # points fore/aft while keeping their safe original distance from the side.
    halliard_rows=[paths['rope_static_line_'+str(i)] for i in (1284,1285,1286)
                   if 'rope_static_line_'+str(i) in paths]
    halliard_x=sum(point(row['points_gltf_m'][1]).x for row in halliard_rows)/len(halliard_rows)-.18 if halliard_rows else 0
    for index,line_id in enumerate((1284,1285,1286)):
        name='rope_static_line_'+str(line_id)
        if name not in paths:continue
        row=paths[name];points=[point(q) for q in row['points_gltf_m']]
        old=points[1].copy();target=old.copy();target.x=halliard_x
        target.y=2.4+(index-1)*.22
        target.z=float(ctx['kd'].deck_z(-target.y,target.x))+.25
        block=bpy.data.objects['deck_lead_block_'+str(line_id)]
        block.location+=target-old;points[1]=target;changed[name]=points
        strops['deck_lead_strop_'+str(line_id)]=[Vector((target.x,target.y,target.z-.19)),target]
        bpy.ops.mesh.primitive_torus_add(major_radius=.030,minor_radius=.007,
            major_segments=12,minor_segments=6,location=(target.x,target.y,target.z-.215),rotation=(math.pi/2,0,0))
        eye=bpy.context.object;eye.name='halliard_lead_eye_'+str(line_id)
        for col in list(eye.users_collection):col.objects.unlink(eye)
        rig.ASSET.objects.link(eye);eye.data.materials.append(bpy.data.materials.get('iron') or bpy.data.materials.get('v2_iron'))
        eye['kind']='fitting';eye['asset_role']='visual'
        moved.append({'block':block.name,'from_gltf_m':gltf(old),'to_gltf_m':gltf(target),
            'reason':'independent halliard sheaves separated by 0.22 m instead of overlapping housings'})

    # Deduplicate physically identical eye bolts. All rope ends retain their
    # actual point and a single real fixing remains there.
    duplicates={};kept=[]
    for eye in eyes:
        if eye.name not in bpy.data.objects:continue
        same=next((o for o in kept if (o.matrix_world.translation-eye.matrix_world.translation).length<1e-5),None)
        if same is not None:duplicates[eye.name]=same.name;remove(eye)
        else:kept.append(eye)

    # An authored sheet eye beside a swivel must clear that weapon physically.
    swivels=[o for o in rig.ASSET.objects if o.type=='MESH' and o.name.startswith('swivel_gun_')]
    trees=[world_tree(o) for o in swivels]
    for eye in kept:
        if eye.name in used_eyes:continue
        old_eye=eye.matrix_world.translation.copy()
        def clear(p):return all(tree.find_nearest(p)[3]>.085 for tree in trees)
        if clear(old_eye):continue
        side=1 if old_eye.x>0 else -1
        for shift in (-.25,.25,-.50,.50):
            target_eye=rail_eye(ctx,side,-old_eye.y+shift)
            if clear(target_eye):break
        else:raise RuntimeError('No clear rail eye position beside swivel: '+eye.name)
        eye.location+=target_eye-old_eye
        for name,row in paths.items():
            pp=changed.get(name,[point(q) for q in row['points_gltf_m']])
            for endpoint in (0,-1):
                if (pp[endpoint]-(old_eye+Vector((0,0,.036)))).length<.02:
                    pp[endpoint]=target_eye+Vector((0,0,.036));changed[name]=pp
        moved.append({'eye':eye.name,'from_gltf_m':gltf(old_eye),'to_gltf_m':gltf(target_eye),
            'reason':'move the fixing and its sheet ends clear of the swivel gun socket'})

    # Rebuild the joined running mesh from its declared centreline records, so
    # block relocation changes the real rope geometry and not only metadata.
    running=[(name,row) for name,row in paths.items() if row.get('mesh_object')=='rigging_running_sailing']
    remove(bpy.data.objects.get('rigging_running_sailing'));pieces=[]
    for name,row in running:
        pp=changed.get(name,[point(q) for q in row['points_gltf_m']])
        obj=rig.tube(name,pp,row['diameter_m'],rig.ROPE)
        if obj:
            rig.RIGGING_PATHS[name].update({k:v for k,v in row.items() if k not in ('points_gltf_m','mesh_object')})
            pieces.append(obj)
    joined=rig.join_rope_meshes(pieces,'rigging_running_sailing');joined['kind']='rope';joined['asset_role']='visual'
    for name,pp in strops.items():
        old=bpy.data.objects.get(name);attrs=dict(old.items()) if old else {}
        remove(old);obj=rig.tube(name,pp,.018 if name.startswith('brace') else .014,rig.TAR)
        if obj:
            for key,value in attrs.items():obj[key]=value
            obj['kind']='rope';obj['asset_role']='visual'
    for name,pp in changed.items():
        if any(name==n for n,r in running):continue
        row=paths[name];old=bpy.data.objects.get(row['mesh_object'])
        if old is None or row['mesh_object']!=name:raise RuntimeError('Unsupported shared sheet endpoint update: '+name)
        attrs=dict(old.items());material=old.data.materials[0];remove(old)
        obj=rig.tube(name,pp,row['diameter_m'],material)
        for key,value in attrs.items():obj[key]=value
        obj['kind']='rope';obj['asset_role']='visual'
        rig.RIGGING_PATHS[name].update({k:v for k,v in row.items() if k not in ('points_gltf_m','mesh_object')})
    source_blocks=bpy.data.objects['rigging_static_blocks']
    source_blocks['source_name']='bloki'
    source_blocks['reference_source_name']='bloki'
    caps=cap_separated_strops(source_blocks)
    for rule in rules:
        rule['b']=duplicates.get(rule['b'],rule['b'])
    ctx['obj']['liny']=[o for o in rig.ASSET.objects if o.type=='MESH' and o.get('kind')=='rope']
    ledger={'moved_fittings':moved,'duplicate_eye_nodes_removed':duplicates,
        'rerouted_rope_names':sorted(changed),'material_separation_caps':caps,
        'intended_joints':list({(r['a'],r['b']):r for r in rules}.values()),
        'scope':'actual blocks, metal eyes and rope paths reconstructed before the independent exported-GLB audit'}
    ctx['_v2_brig_fittings']=ledger
    ctx.setdefault('_v2_brig_joint_rules',[]).extend(ledger['intended_joints'])
    if ctx.get('_v2_rigging_report') is not None:
        report=ctx['_v2_rigging_report']
        report['pre_fittings_audit_summary']={
            'rope_canvas_passed':report.get('rope_canvas',{}).get('passed'),
            'spar_canvas_passed':report.get('spar_canvas',{}).get('passed'),
            'attachment_failure_count':report.get('attachments',{}).get('failure_count'),
            'scope':'Original deployment before the lead fittings were separated.'}
        report['rigging_paths']=rig._paths_report()
        report['fittings_reconstruction']=ledger
        report['rope_canvas']=rig.audit_scene(frames=(0,))
        report['spar_canvas']=rig.audit_spars()
        report['attachments']=rig.audit_attachment_paths(report['rigging_paths'])
        report['passed']=report['rope_canvas']['passed'] and report['spar_canvas']['passed'] and report['attachments']['passed']
        report['post_fittings_validation']='Current reconstructed source rig checked again; independent GLB reimport remains a required separate gate.'
        if out is not None:(Path(out)/'rigging-working.json').write_text(json.dumps(report,indent=2)+'\n')
        if not report['passed']:raise RuntimeError('Reconstructed brig leads failed current source rig checks')
    return ledger
