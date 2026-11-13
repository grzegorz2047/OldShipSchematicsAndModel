"""Check that a passing Blender report still describes the delivered files.

Run with standard Python: python sailertales/common/check_asset.py [spec.json ...]
Without arguments, checks every sibling vessel. Does not replace Blender sweeps.
"""
import hashlib
import json
import sys
from pathlib import Path


def check(spec_path):
    folder = spec_path.resolve().parent
    report = json.loads((folder / 'validation.json').read_text(encoding='utf-8'))
    required = {
        'model/ship.glb', 'model/collision.glb', 'navigation.json', 'spec.json',
        '../common/build.py', '../common/verify.py',
    }
    if not required.issubset(report['sha256']):
        raise ValueError(f'{folder.name}: incomplete fingerprint manifest')
    for filename, expected in report['sha256'].items():
        actual = hashlib.sha256((folder / filename).read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f'{folder.name}: stale report for {filename}')
    routes = [r for c in report['checks'].values() for r in c['routes']]
    if not routes or not report['passed'] or not report['rig']['passed']:
        raise ValueError(f'{folder.name}: failed or empty report')
    if not all(r['passed'] and r['failure_count'] == 0 for r in routes):
        raise ValueError(f'{folder.name}: blocked route')
    nav = json.loads((folder / 'navigation.json').read_text(encoding='utf-8'))
    spec = json.loads(spec_path.read_text(encoding='utf-8'))
    if nav['player'] != report['capsule']:
        raise ValueError(f'{folder.name}: inconsistent player dimensions')
    if nav['source_commit'] != spec['source_commit']:
        raise ValueError(f'{folder.name}: inconsistent source reference')
    print(f'{folder.name}: PASS ({len(routes)} route checks, matching SHA-256)')


if __name__ == '__main__':
    specs = ([Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else
             sorted(Path(__file__).resolve().parent.parent.glob('*/spec.json')))
    if not specs:
        raise ValueError('No vessel specifications found')
    for spec_path in specs:
        check(spec_path)
