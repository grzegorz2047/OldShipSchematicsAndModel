"""Rebuild this authored static POTC family; Blender 5.2.3 LTS, two palettes."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "potc/common"))
from v4_shipkit import build

if __name__ == "__main__":
    build(json.loads((HERE / "spec.json").read_text()), HERE)
