"""Check exported sloop files against their Blender audit without Blender.

python sloop_asset/check_asset.py build/sloop_1715
This checks integrity and audit coverage; it does not repeat geometric tests.
"""

from pathlib import Path
import hashlib
import json
import sys

from glb_io import validate


FILES = {
    "lod0": "sloop_1715.glb",
    "lod1": "sloop_1715_lod1.glb",
    "lod2": "sloop_1715_lod2.glb",
    "collision": "sloop_1715_collision.glb",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes(root):
    paths = [root / "model/snow.glb"]
    paths += sorted((root / "blender").glob("*.py"))
    paths += sorted((root / "sloop_asset").glob("*.py"))
    return {p.relative_to(root).as_posix(): sha256(p) for p in paths}


def check(folder, source_root=None):
    folder = Path(folder)
    report = json.loads((folder / "native_import_validation.json").read_text())
    manifest = json.loads((folder / "asset_manifest.json").read_text())
    assert report["result"] == "passed"
    assert report["source_file_sha256"] == manifest["source_file_sha256"]
    if source_root:
        assert source_hashes(source_root) == manifest["source_file_sha256"], "stale source audit"
    for name, expected in report["data_file_sha256"].items():
        assert sha256(folder / name) == expected, "stale data audit: " + name
    for level, name in FILES.items():
        path = folder / name
        model = report["models"][level]
        assert model["result"] == "passed"
        assert sha256(path) == model["sha256"], "stale export audit: " + name
        _, _, triangles = validate(path)
        assert triangles == model["triangles"], (level, triangles)
        if level == "collision":
            continue
        frames = list(range(0, 97, 12)) if level == "lod0" else [0]
        assert model["audit_frames"] == frames
        rig = json.loads((folder / ("export_rigging_" + level + ".json")).read_text())
        clear = json.loads((folder / ("export_clearance_" + level + ".json")).read_text())
        assert rig["source_glb_sha256"] == clear["source_glb_sha256"] == model["sha256"]
        assert rig["passed"] and not rig["hits"] and rig["frames"] == frames
        assert clear["passed"] and clear["minimum_m"] >= 2.2
        assert [sample["frame"] for sample in clear["per_frame"]] == frames
    access = json.loads((folder / "deck_access.json").read_text())
    assert access["passed"] and len(access["stations"]) == 9 and all(access["stations"].values())
    return {"result": "passed", "models": 4, "stations": 9}


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    source = root if (root / "sloop_asset").is_dir() else None
    print(json.dumps(check(sys.argv[1] if len(sys.argv) > 1 else "build/sloop_1715", source)))
