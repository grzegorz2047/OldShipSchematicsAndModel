"""Explicit semantic contracts for the static working rig's real attachments."""
import bpy


def prepare(ctx):
    from v2_rigging import YARD_NAMES
    for source,current in YARD_NAMES.items():
        obj=bpy.data.objects.get(current)
        if obj is not None:obj['source_name']=source
    for source in ('drzewca','bukszpryt'):
        obj=ctx['obj'].get(source)
        if obj is not None:obj['source_name']=source
    attachments=[]
    sails=[o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('kind')=='sail']
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH':continue
        if 'yard_parrel' in obj.name or obj.name.startswith('rak_'):
            obj['kind']='fitting'
            obj['construction']='closed wooden parrel trucks and mast/yard attachment hardware'
    for sail in sails:
        if not sail.name.endswith('_set'):continue
        stem=sail.name[:-4]
        for obj in bpy.context.scene.objects:
            if obj.type=='MESH' and (obj.name==stem+'_sheet' or obj.name.startswith(stem+'_sheet_')):
                obj['kind']='rope';obj['edge_attachment']=True;obj['attachment_sail']=sail.name
                attachments.append({'sail':sail.name,'rope':obj.name,'joint':'sheet fastened to the sail clew'})
    ctx['_v2_brig_attachment_contract']={'clew_attachments':attachments,
        'parrel_fittings':[o.name for o in bpy.context.scene.objects if o.name.startswith('rak_') or 'yard_parrel' in o.name],
        'yard_source_aliases':{current:source for source,current in YARD_NAMES.items() if bpy.data.objects.get(current)},
        'scope':'own clew/luff joints only; independent audit still requires all intersections within 25 mm of a cloth boundary'}
    ctx['_v2_brig_joint_rules']=[{'a':'gaff_sail_set','b':'spars',
        'reason':'The gaff sail luff is attached to the snow mast; only measured cloth-boundary contact is allowed.'}]
    return ctx['_v2_brig_attachment_contract']
