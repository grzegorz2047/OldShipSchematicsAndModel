#!/usr/bin/env python3
"""Render the declared intact Lugger hold pose with the frozen review engine.

Run after v5_review.py has produced the complete current-model manifest:
blender -b -t 1 --python potc/lugger/render-detail-overrides.py
No model, material, geometry, lighting preset, lens or sample count is edited.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import bpy
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'common'))
import v5_review as R


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    camera_path=HERE/'detail-camera-overrides.json'
    config=json.loads(camera_path.read_text())
    manifest_path=HERE/'detail-render.json'
    manifest=json.loads(manifest_path.read_text())
    model=HERE/config['model_path']
    before=digest(model)
    if before!=config['model_sha256'] or before!=manifest['model_sha256']:
        raise ValueError('Camera override requires its declared current GLB; regenerate/review the pose after a model change')
    if R.RENDERER_SHA256!=config['renderer_sha256'] or R.RENDERER_SHA256!=manifest['renderer_sha256']:
        raise ValueError('Frozen renderer identity differs from the declared camera evidence')
    if config['resolution']!=[640,512] or config['samples']!=12:
        raise ValueError('The reviewed detail resolution and sample count must remain unchanged')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(model))
    bpy.context.view_layer.update()
    records=[]
    for name,override in config['overrides'].items():
        entry=next(view for view in manifest['views'] if view['name']==name)
        if entry['category']!='interior' or override['hidden_nodes'] or override['hide_rig']:
            raise ValueError('This correction is an intact interior camera pose only')
        definition=copy.deepcopy(entry)
        for key in ('position','target','lens_mm','hide_rig','hidden_nodes','room_id'):
            definition[key]=override[key]
        definition['scope']='Intact actual-GLB hold view with an explicit asset-local camera pose; the default pose was obstructed by companion treads. Frozen lens, lighting, samples, materials and geometry are retained.'
        output=HERE/entry['path']
        hidden=R.render(definition,output,640,12)
        if hidden:
            raise ValueError('Intact camera correction unexpectedly hid actual visual geometry')
        for key in ('position','target','lens_mm','hide_rig','hidden_nodes','room_id','scope'):
            entry[key]=definition[key]
        entry['actual_hidden_nodes']=hidden
        entry['sha256']=digest(output)
        entry['camera_override']={'path':camera_path.name,'sha256':digest(camera_path),
            'wrapper_path':Path(__file__).name,'wrapper_sha256':digest(__file__),
            'reason':override['reason'],'default_position':override['default_position'],
            'default_target':override['default_target'],'eye_height_m':override['eye_height_m']}
        records.append(entry['camera_override'])
    if digest(model)!=before:
        raise ValueError('Read-only camera correction changed the delivered model')
    manifest['camera_overrides']=records
    manifest['review_status']='PENDING_MANUAL_INSPECTION'
    manifest['presentation']+=' The Lugger hold pose is explicitly corrected by the SHA-bound asset-local camera JSON and reproducible wrapper; no frozen common file is changed.'
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    print('LUGGER_INTACT_CAMERA_CORRECTED',before,'PENDING_MANUAL_INSPECTION',flush=True)


if __name__=='__main__':
    main()
