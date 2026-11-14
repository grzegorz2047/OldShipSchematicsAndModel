#!/usr/bin/env python3
"""Build this authored POTC family reconstruction in Blender 5.2."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "potc/common"))
from v4_shipkit import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=HERE,
                        help="Output asset folder, relative to the repository root or absolute")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    spec = json.loads((HERE / "spec.json").read_text())
    out = args.out if args.out.is_absolute() else ROOT / args.out
    design = build(spec, out)
    design.update(spec["game_source"])
    (out / "design.json").write_text(json.dumps(design, indent=2) + "\n")


if __name__ == "__main__":
    main()
