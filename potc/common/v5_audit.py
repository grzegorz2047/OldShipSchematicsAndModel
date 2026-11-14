"""Run frozen v4 acceptance, then independently measure additive v5 detail.

Blender invocation: --background --python potc/common/v5_audit.py --
  --asset-dir potc/brig --source-root . [--reuse-review] [--detail-only]

The portable checker uses Python/numpy/Pillow outside Blender.  --detail-only
refreshes the added evidence and complete file inventory after recording a
visual review, and then reruns every frozen portable v4 gate/signature check.
It never changes frozen v4 geometric results or acceptance thresholds.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import v4_audit as A
import v4_integrity as V
from v5_joint_index import indexed_quality
import v5_contract as C
from v5_uv_metrics import vectorized_uv

SOURCES = C.AUDIT_SOURCES


def command(root, asset, flag):
    python = shutil.which("python3")
    if not python:
        raise RuntimeError("Portable v5 checks require Python 3 with numpy and Pillow")
    process = subprocess.run([python, str(root/"potc/common/v5_integrity.py"),
                              "--asset-dir", str(asset), "--source-root", str(root), flag],
                             check=False, capture_output=True, text=True)
    if process.returncode:
        raise RuntimeError(process.stderr.strip() or process.stdout.strip())
    return json.loads(process.stdout)


def audit(asset, root, resolution=480, render=True, detail_only=False):
    asset, root = Path(asset).resolve(), Path(root).resolve()
    if detail_only:
        report = C.read(asset/"validation.json")
        # Changing a review record must not invalidate inventory completeness.
        # Frozen geometry rows and old acceptance matrices stay untouched.
        report["sha256"] = {p.relative_to(asset).as_posix(): V.digest(p) for p in sorted(asset.rglob("*"))
                            if p.is_file() and p.name != "validation.json" and "__pycache__" not in p.parts
                            and not p.name.endswith(".blend1")}
        report['passed']=all(row['status']=='PASS' for row in report['matrix'] if row['required'])
        (asset/"validation.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
        C.check_base(asset, root)
    else:
        with vectorized_uv(A.A), indexed_quality(A), C.release_quality_profile(A):
            report = A.audit(asset, root, resolution, render)
    report.update(detail_schema=5,validation_profile=C.PROFILE)
    if 'V5 resource applicability' not in report['scope']:
        report['scope'] += ' V5 resource applicability: original H1/H2 rows remain visible as SUPERSEDED; fixed reviewed v5 package_budget limits replace only those two resource gates.'
    (asset/'validation.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    upgrade = command(root, asset, "--measure-only")
    upgrade["audit_source_sha256"] = {path: V.digest(root/path) for path in SOURCES}
    report["detail_upgrade"] = upgrade
    report['passed']=report['passed'] and upgrade['passed']
    (asset/"validation.json").write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    print("V5_DETAIL", report["vessel"], upgrade["passed"],
          {row["id"]: row["status"] for row in upgrade["matrix"]}, flush=True)
    if not upgrade["passed"]:
        failures = {key: value.get("errors", []) for key, value in upgrade["checks"].items() if not value["passed"]}
        raise RuntimeError("Required additive v5 detail gate failed: " + json.dumps(failures))
    result = command(root, asset, "--verify")
    print("V5_PORTABLE", json.dumps(result), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=ROOT)
    parser.add_argument("--resolution", type=int, default=480)
    parser.add_argument("--reuse-review", action="store_true")
    parser.add_argument("--detail-only", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    if args.resolution < 320:
        parser.error("Source/export review resolution must be at least 320")
    audit(args.asset_dir, args.source_root, args.resolution, not args.reuse_review, args.detail_only)


if __name__ == "__main__":
    main()
