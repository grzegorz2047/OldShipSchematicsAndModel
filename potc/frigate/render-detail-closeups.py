#!/usr/bin/env python3
"""Append SHA-bound, intact close-ups with the unchanged frozen review engine.

Run after all default v5_review.py views and before manual PASS/audit:
blender -b -t 1 --python potc/frigate/render-detail-closeups.py
Only declared camera poses/lenses differ. Geometry, material data, standard
interior lighting, sample count and every default view remain unchanged.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'common'))
import v5_review as R


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    config_path = HERE / 'detail-camera-closeups.json'
    config = json.loads(config_path.read_text())
    manifest_path = HERE / 'detail-render.json'
    manifest = json.loads(manifest_path.read_text())
    review_path = HERE / 'detail-review.json'
    if review_path.exists() and json.loads(review_path.read_text()).get('decision') == 'PASS':
        raise ValueError('Supplementary evidence must be finalized before manual PASS and the accepted audit')
    model = HERE / config['model_path']
    before = digest(model)
    if before != config['model_sha256'] or before != manifest['model_sha256']:
        raise ValueError('Supplementary camera requires the declared current delivered GLB')
    if R.RENDERER_SHA256 != config['renderer_sha256'] or R.RENDERER_SHA256 != manifest['renderer_sha256']:
        raise ValueError('The frozen common renderer changed')
    if config['resolution'] != [640, 512] or config['samples'] != 12:
        raise ValueError('Supplementary evidence must retain 640x512 and 12 samples')
    default_names = set(view['name'] for view in manifest['views']) - set(config['additional_views'])
    default_bytes = {view['path']: digest(HERE / view['path']) for view in manifest['views'] if view['name'] in default_names}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(model))
    bpy.context.view_layer.update()
    additions = []
    for name, declared in config['additional_views'].items():
        if declared['category'] != 'interior' or declared['hidden_nodes'] or declared['hide_rig']:
            raise ValueError('This supplementary camera is intact interior evidence only')
        definition = copy.deepcopy(declared)
        relative = 'previews/' + config['palette'] + '/detail/' + name + '.png'
        output = HERE / relative
        hidden = R.render(definition, output, 640, 12)
        if hidden:
            raise ValueError('Supplementary intact camera unexpectedly hid actual geometry')
        source = {'config_path': config_path.name, 'config_sha256': digest(config_path),
                  'wrapper_path': Path(__file__).name, 'wrapper_sha256': digest(__file__),
                  'reason': declared['reason'], 'frozen_renderer_sha256': R.RENDERER_SHA256}
        entry = {'name': name, 'path': relative, 'sha256': digest(output),
                 **definition, 'actual_hidden_nodes': hidden, 'supplementary_camera': source}
        manifest['views'] = [view for view in manifest['views'] if view['name'] != name]
        manifest['views'].append(entry)
        additions.append(source)
    if digest(model) != before:
        raise ValueError('Read-only supplementary renderer changed the delivered model')
    if any(digest(HERE / relative) != sha for relative, sha in default_bytes.items()):
        raise ValueError('A default rendered image was modified')
    if not default_names.issubset({view['name'] for view in manifest['views']}):
        raise ValueError('A default view was removed')
    manifest['supplementary_cameras'] = additions
    manifest['review_status'] = 'PENDING_MANUAL_INSPECTION'
    note = ' Supplementary intact near-gun evidence uses an explicit SHA-bound asset-local camera/config with the unchanged frozen renderer and lighting; every default view is retained.'
    if note not in manifest['presentation']:
        manifest['presentation'] += note
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print('FRIGATE_INTACT_GUN_CLOSEUP_ADDED', before, 'PENDING_MANUAL_INSPECTION', flush=True)


if __name__ == '__main__':
    main()
