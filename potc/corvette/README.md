# POTC2003 Corvette — two painted static assets

Slender three-masted, 32-gun corvette with a flush deck and single open battery; square fore/main and square upper mizzen with a gaff spanker.

The pinned stock-derived script identifies `Corvette1` as class 2 with **32 guns**. The procedural reconstruction uses authored dimensions **42 × 10 m**, draught 3.8 m and main-deck freeboard 2.15 m. These are design estimates, not recovered game dimensions. Stock-derived scripts give the Corvette 32 guns and higher speed/turn rates than the Frigate. A single battery, low superstructure and finer lines distinguish the authored corvette from the frigate.

Ochre and navy variants share geometry, UVs, hierarchy and natural deck, canvas, rigging and metal materials. Only `paint_hull` and `paint_trim` change. Main, LOD1 and LOD2 GLBs plus packed Blender source are in `model/<palette>/`; collision is shared. Source and imported-GLB renders are retained for both views and palettes. `validation.json` and `export-review.json` record actual checks.

| Ochre | Navy |
| --- | --- |
| ![Ochre exported GLB](previews/ochre/hero.png) | ![Navy exported GLB](previews/navy/hero.png) |

Build with Blender 5.2.3:

```sh
blender -b --python potc/corvette/build.py
```

![Authored hull and sail-plan schematic](type-plan.svg)

`spec.json` and `type-profile.json` record the family plan, exact stock-stat evidence, guide references and uncertainty. The 2003 published screenshot is used only for general visual vocabulary; its ship family is not authenticated. No proprietary mesh, texture or paid generated asset is included. The stock-derived modern compatibility script is not claimed to be a byte-identical retail dump.

This is a **static duel asset**. Engine sailing, buoyancy, damage, gun logic and crew controllers are absent. Walking and interior navigation are not claimed and are outside this asset's acceptance scope.
