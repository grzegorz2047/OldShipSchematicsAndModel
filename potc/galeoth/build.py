#!/usr/bin/env python3
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
from v5_shipkit import build
if __name__ == "__main__":
    build(HERE / "spec.json", HERE)
