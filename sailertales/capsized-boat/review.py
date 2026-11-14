"""Actual GLB/source review with high inverted-bottom and rescue-seat views.

The orange seat locator is presentation-only, created equally in source/export
renders. It is never included in either delivered model or triangle counts.
Frozen common review code is imported unchanged.
"""
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'sailertales/common'))
import v2_review as R

original_views=R.views
original_setup=R.setup
original_render=R.render
seat_active=False
locators=[]


def views(nav):
    result=original_views(nav)
    target=Vector(result['hero']['target'])
    span=(Vector(result['hero']['position'])-target).length
    result['hero']['position']=list(target+Vector((1.05,1.2,1.6)).normalized()*span)
    # A top view of the actual inverted hull, including no invented walk deck.
    result['deck']['hide_rig']=False
    # Changing direction invalidates the original projected fit. Fit all real
    # hull/debris bounds again and centre their projection with15% margin.
    for name in ('hero','deck'):
        definition=result[name]
        target=Vector(definition['target']);position=Vector(definition['position'])
        rotation=(target-position).to_track_quat('-Z','Y').to_matrix()
        points=[rotation.transposed()@(o.matrix_world@Vector(corner)-target)
                for o in R.candidates() for corner in o.bound_box]
        lo=Vector((min(v.x for v in points),min(v.y for v in points),0))
        hi=Vector((max(v.x for v in points),max(v.y for v in points),0))
        shift=rotation@((lo+hi)/2)
        definition['target']=list(target+shift);definition['position']=list(position+shift)
        definition['scale']=max(hi.x-lo.x,(hi.y-lo.y)*1.25)*1.15
    asset=Path(sys.argv[sys.argv.index('--')+1]).resolve()
    seat=json.loads((asset/'states.json').read_text())['anchors']['seat_anchor']
    target=R.point(seat)+Vector((0,0,.02))
    result['seat']={'target':list(target),'position':list(target+Vector((1.3,1.9,1.8))),
                    'ortho':True,'scale':2.6,'hide_rig':False,'seat_locator':True}
    return {name:result[name] for name in ('hero','deck','seat')}


def setup(resolution):
    scene=original_setup(resolution)
    if seat_active:
        asset=Path(sys.argv[sys.argv.index('--')+1]).resolve()
        anchor=R.point(json.loads((asset/'states.json').read_text())['anchors']['seat_anchor'])
        material=bpy.data.materials.new('presentation_seat_locator');material.use_nodes=True
        bs=material.node_tree.nodes.get('Principled BSDF')
        bs.inputs['Base Color'].default_value=(1.,.18,.025,1)
        bs.inputs['Roughness'].default_value=.55
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=.035,
                                          location=anchor+Vector((0,0,.055)))
        marker=bpy.context.object;marker.name='presentation_only_seat_locator'
        marker['asset_role']='review_locator';marker.data.materials.append(material)
        locators.append(marker)
    return scene


def render(definition,path,resolution):
    global seat_active
    seat_active=definition.get('seat_locator',False)
    try:return original_render(definition,path,resolution)
    finally:
        for marker in locators:bpy.data.objects.remove(marker,do_unlink=True)
        locators.clear();seat_active=False


R.views=views;R.setup=setup;R.render=render
R.main()
asset=Path(sys.argv[sys.argv.index('--')+1]).resolve()
path=asset/'export-review.json';review=json.loads(path.read_text())
review['presentation_overlay']='Orange dot in seat view identifies the actual seat anchor; temporary display locator only, absent from GLBs and packed authoring scene.'
path.write_text(json.dumps(review,indent=2)+'\n')
