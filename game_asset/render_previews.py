"""Render the saved sailing asset without rebuilding its geometry or exports.

blender -b build/game_ship/snow_sailing.blend --python-exit-code 1 \
  --python game_asset/render_previews.py -- build/game_ship
"""
from pathlib import Path
import argparse
import json
import sys

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_ship as ship
from deck_clearance import DeckEnvelope


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--samples", type=int, default=64)
    parser.add_argument("--resolution-percentage", type=int, default=100)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    if args.samples < 1 or not 1 <= args.resolution_percentage <= 100:
        parser.error("samples must be positive; resolution must be 1–100 percent")
    ship.OUT = args.folder.resolve()
    (ship.OUT / "previews").mkdir(parents=True, exist_ok=True)
    ship.ASSET = bpy.data.collections["SHIP | snow 1710 | sailing"]
    ship.PRESENTATION = bpy.data.collections["PRESENTATION | excluded from GLB"]
    for obj in list(ship.PRESENTATION.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    ship.DECKS = DeckEnvelope(json.loads((ship.OUT / "data/deck-layout.json").read_text()))
    bpy.context.scene.frame_set(0)
    ship.render_setup(samples=args.samples, resolution_percentage=args.resolution_percentage)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(ship.OUT / "snow_sailing.blend"), compress=True)


if __name__ == "__main__":
    main()
