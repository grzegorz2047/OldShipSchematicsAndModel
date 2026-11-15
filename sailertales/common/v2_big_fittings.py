"""Explicit furniture placements for the guide-built walkable interiors."""
import bpy
import bmesh
from mathutils import Vector


def P(x,s,z):return Vector((x,-s,z))
def gltf(p):return [p.x,p.z,-p.y]


def relocate_water_supply(ctx):
    """Store the complete source water cask in the real hold to clear pumps."""
    source=bpy.data.objects.get('wyposazenie_drobne')
    if source is None:raise RuntimeError('Reference small fittings missing')
    u=ctx['PR'].UKLAD['BECZKA_WODY'];kd=ctx['kd']
    origin=P(u['x'],u['s'],float(kd.deck_z(u['s'],u['x'])))
    target=P(-1.85,0,ctx['_v2_interior_design']['hold_floor_m'])
    bm=bmesh.new();bm.from_mesh(source.data);bm.verts.index_update();seen=set();selected=set()
    for v in bm.verts:
        if v in seen:continue
        group={v};queue=[v];seen.add(v)
        while queue:
            w=queue.pop()
            for e in w.link_edges:
                q=e.other_vert(w)
                if q not in seen:seen.add(q);group.add(q);queue.append(q)
        points=[source.matrix_world@w.co for w in group]
        if points and all(abs(q.x-origin.x)<u['r']+.045 and abs(q.y-origin.y)<u['r']+.045 and
                          -.04<q.z-origin.z<u['h']+.05 for q in points):
            selected.update(w.index for w in group)
    bm.free()
    if not selected:raise RuntimeError('Could not isolate reference water cask')
    origin.z=min((source.matrix_world@source.data.vertices[i].co).z for i in selected)
    barrel=source.copy();barrel.data=source.data.copy();barrel.name='freshwater_barrel_hold'
    ctx['_v2_interiors'].objects.link(barrel)
    for ob,keep in [(source,False),(barrel,True)]:
        bm=bmesh.new();bm.from_mesh(ob.data);bm.verts.index_update()
        delete=[v for v in bm.verts if (v.index not in selected if keep else v.index in selected)]
        if delete:bmesh.ops.delete(bm,geom=delete,context='VERTS')
        if keep:
            delta=ob.matrix_world.inverted().to_3x3()@(target-origin)
            for v in bm.verts:v.co+=delta
        bm.to_mesh(ob.data);bm.free();ob.data.update()
    barrel['asset_role']='visual';barrel['kind']='fitting';barrel['physics']='solid';barrel['authored_access']=True
    for station in ctx.get('stanowiska',[]):
        if station.get('czynnosc')=='beczka' or station.get('nazwa','').startswith('beczka'):
            station.update(x=-1.,s=0.,z=target.z)
            marker=bpy.data.objects.get(station['nazwa'])
            if marker is not None:marker.location=P(-1,0,target.z)
    ctx['_v2_routes'].append({'name':'hold_water_supply','mode':'walk','points':
         [gltf(P(-1,1.2,target.z)),gltf(P(-1,0,target.z))]})
    ctx['_v2_interior_design']['water_supply']={'source':'blender/wyposazenie.py:drobne',
        'original_gltf':gltf(origin),'hold_gltf':gltf(target),
        'reason':'The complete source cask is stored on the hold sole to clear both pumps and the capstan bar rack.'}


def separate_canvas_gaskets(ctx):
    """Keep six-millimetre rope gasket loops separate from closed fabric rolls."""
    ledger=[]
    for source in list(bpy.context.scene.objects):
        if source.type!='MESH' or not source.name.startswith(('zagiel_','zagle_')):continue
        bm=bmesh.new();bm.from_mesh(source.data);bm.verts.index_update();selected=set();seen=set()
        for v in bm.verts:
            if v in seen:continue
            group={v};queue=[v];seen.add(v)
            while queue:
                w=queue.pop()
                for e in w.link_edges:
                    q=e.other_vert(w)
                    if q not in seen:seen.add(q);group.add(q);queue.append(q)
            faces={f for w in group for f in w.link_faces}
            if faces and all(f.material_index<len(source.data.materials) and
                source.data.materials[f.material_index].name.startswith(('lina_','rope_')) for f in faces):
                selected.update(w.index for w in group)
        bm.free()
        if not selected:continue
        rope=source.copy();rope.data=source.data.copy();rope.name='rope_gaskets_'+source.name
        ctx['_v2_interiors'].objects.link(rope)
        for ob,keep in [(source,False),(rope,True)]:
            bm=bmesh.new();bm.from_mesh(ob.data);bm.verts.index_update()
            delete=[v for v in bm.verts if (v.index not in selected if keep else v.index in selected)]
            if delete:bmesh.ops.delete(bm,geom=delete,context='VERTS')
            bm.to_mesh(ob.data);bm.free();ob.data.update()
        rope['kind']='rope';rope['asset_role']='visual';rope['physics']='none'
        if 'cloth_state' in rope:del rope['cloth_state']
        rope['source_fabric_assembly']=source.name
        ledger.append({'canvas':source.name,'rope_gaskets':rope.name,
            'source':'blender/zagle.py:na_rei; rectangular 6 x 35 mm gasket loops',
            'reason':'Material-separated gasket straps are rigging, not the furled canvas solid.'})
    ctx['_v2_interior_design']['furled_gasket_parts']=ledger


def add_night_head_joints(objects,design):
    """Record inspected collar/brace housings, after deterministic timber split."""
    names={o.name for o in objects}
    head='galion' if 'galion' in names else 'head'
    if head not in names:raise RuntimeError('Missing bow head structure')
    for name in ('catheads_timber_002','catheads_timber_003'):
        if name not in names:raise RuntimeError('Missing inspected hawse collar '+name)
        design['intended_joints'].append({'a':head,'b':name,
            'reason':'The wood-and-iron hawse collar is housed 39-41 mm into bow timber; its source axial profile extends 50 mm inward.',
            'source':'blender/rufa_dziob.py:kotbelki_i_kluzy, hawse-collar axial profile'})
    name='catheads_timber_005'
    if name not in names:raise RuntimeError('Missing inspected cathead brace')
    design['intended_joints'].append({'a':head,'b':name,
        'reason':'The curved cathead support seats up to 9 mm into the head cheek at its hull fastening, before the free head rail begins.',
        'source':'blender/rufa_dziob.py:kotbelki_i_kluzy, curved support foot'})
