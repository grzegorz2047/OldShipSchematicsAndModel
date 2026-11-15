#!/usr/bin/env python3
"""Build both painted variants using the repository-owned procedural ship kit."""
import json
import pathlib
import sys
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
from v4_shipkit import build
if __name__ == "__main__":
    build(json.loads((HERE / "spec.json").read_text()), HERE)
