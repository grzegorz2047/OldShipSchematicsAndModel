#!/usr/bin/env python3
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
from v5_shipkit import build
if __name__ == "__main__":
    build(HERE / "spec.json", HERE)

# POTC_SURFACE_REPAIR_POST_BUILD
if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    from gun_surface_repair import repair_package
    repair_package(HERE)
