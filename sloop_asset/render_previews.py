"""Render the actual saved sloop model; images are not concept art.
blender -b build/sloop_1715/sloop_1715.blend --python-exit-code 1 --python sloop_asset/render_previews.py -- build/sloop_1715
"""

from pathlib import Path
import sys
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geometry as G
from build_sloop import Deck, PR, rzedne, kadlub

folder = Path(sys.argv[sys.argv.index("--") + 1]).resolve()
G.OUT = folder
G.ASSET = bpy.data.collections["SLOOP_GAME_ASSET"]
G.PRESENTATION = bpy.data.collections["PRESENTATION_ONLY"]
for obj in list(G.PRESENTATION.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
kd = rzedne.Kadlub(PR.KADLUB, PR.RZEDNE_H, PR.RZEDNE_S, PR.RZEDNE)
G.DECKS = Deck(kadlub.Poszycie(kd, PR.KADLUB), kd)
bpy.context.scene.frame_set(0)
G.render_setup()
bpy.ops.wm.save_as_mainfile(filepath=str(folder / "sloop_1715.blend"))
