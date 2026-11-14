#!/usr/bin/env python3
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
from v5_shipkit import build

"""Measured Fleut end-seats and original isometric square-frame UVs only."""
from contextlib import contextmanager
import json,re
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from v2_boats import physical_uv
import v5_decks as D
import v5_materials as M

FRAME_NAMES={f'interior_frame_{i:03d}' for i in range(41)}

@contextmanager
def fleut_specialization():
    original_framing=D._framing;original_axial=M._axial_uv
    def frame_seats(ctx):
        original_framing(ctx)
        if ctx.spec.get('id')!='fleut':return
        nodes={o.name:o for o in ctx.frame_nodes};seats=[]
        for name in sorted(FRAME_NAMES):
            frame=nodes.get(name)
            if frame is None:raise ValueError('Missing measured Fleut frame '+name)
            path=list(map(Vector,json.loads(frame['rope_path_json'])['points']))
            for side in('port','starboard'):
                timber=nodes.get('top_timber_%s_%s_0'%(side,name.rsplit('_',1)[1]))
                if timber is None:continue
                grain=json.loads(timber['grain_path_json']);endpoints=list(map(Vector,grain['points']))
                foot=endpoints[0];end=min((path[0],path[-1]),key=lambda q:(q-foot).length)
                if (end-foot).length>.051 or abs(end.y-foot.y)>.00001 or abs(end.z-foot.z)>.00001:
                    raise ValueError('Fleut futtock is not at the measured same-bay frame endpoint: '+timber.name)
                def tree(ob):return BVHTree.FromPolygons([ob.matrix_world@v.co for v in ob.data.vertices],[tuple(p.vertices)for p in ob.data.polygons])
                if not tree(frame).overlap(tree(timber)):continue
                before=len(timber.data.polygons)
                for selected in list(bpy.context.selected_objects):selected.select_set(False)
                timber.select_set(True);bpy.context.view_layer.objects.active=timber
                modifier=timber.modifiers.new('fleut_actual_frame_end_seat','BOOLEAN');modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=frame
                bpy.ops.object.modifier_apply(modifier=modifier.name);timber.select_set(False)
                if not timber.data.polygons:raise ValueError('Frame end-seat consumed the upper timber '+timber.name)
                for layer in list(timber.data.uv_layers):timber.data.uv_layers.remove(layer)
                physical_uv(timber,Vector(timber.get('grain_axis',(0,0,1))),endpoints)
                timber['joinery_detail']='Closed upper futtock end-seat fitted to the actual same-bay lower frame; no clearance gap or penetration allowance.'
                timber['joinery_parent']=frame.name
                seats.append({'lower_frame':frame.name,'upper_timber':timber.name,'endpoint_distance_m':(end-foot).length,'faces_before':before,'faces_after':len(timber.data.polygons)})
        ctx.fleut_end_seats=seats
    def square_frame_uv(obj,roles):
        if obj.name in FRAME_NAMES and obj.get('structural_role')=='hull_frame' and roles==['wood']:
            path=json.loads(obj['rope_path_json'])['points']
            if len(obj.data.vertices)!=4*len(path):raise ValueError('Measured Fleut frame ring structure changed: '+obj.name)
            obj['uv_method']='Original isometric triangle charts on the curved four-sided timber; standard physical tile conversion retained.'
            obj['type_local_uv']='fleut_square_frame_isometry'
            return False
        return original_axial(obj,roles)
    D._framing=frame_seats;M._axial_uv=square_frame_uv
    try:yield
    finally:D._framing=original_framing;M._axial_uv=original_axial

if __name__ == "__main__":
    with fleut_specialization():
        build(HERE / "spec.json", HERE)
