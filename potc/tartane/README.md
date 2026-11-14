# POTC2003 tartane: two authored palettes

One lateen mast, low pointed ends, modest sheer and no battery.

This is a new procedural reconstruction of the ordinary class-7 tartane, with 0 guns. Its nominal 9.0 × 3.0 m hull is an authored design, not a measurement or extraction of the 2003 proprietary game model. Stock small fishing-boat role and one-mast status. Sail dimensions, deck arrangement and line offsets are authored reconstruction.

Ochre and navy change hull paint and trim. Deck, spars, rope, cloth and metal keep their deliberate natural materials. These are static duel visuals with shared static hull/deck collision and two LODs per palette. No walking, animation or runtime adapter is claimed.

Sources and precise claims are in [design.json](design.json). Hull offsets, mast positions, sail dimensions and paint values are in [spec.json](spec.json). The method follows [the repository guide](../../docs/en/12-designing-other-ships.md), with actual exported-GLB inspection and validation.

Built and validated with **Blender 5.2.3**. Use Blender **5.2 or newer** for rebuilding and opening the packed source scenes.

The builder writes the delivered asset folder. Run acceptance again after every source or model change. The detail renderer reimports the delivered GLB and records review lighting and every temporary cutaway visibility change; it never changes model geometry. Inspect its deck, hull/rig and interior images, then record concrete findings in `detail-review.json` before the v5 acceptance run.

```sh
blender -b -t 1 --factory-startup --python-exit-code 1 --python potc/tartane/build.py
```

## Delivered files

| Palette | Main model | Distance levels | Packed source | Actual GLB views |
|---|---|---|---|---|
| Ochre | [ship.glb](model/ochre/ship.glb) | [LOD1](model/ochre/lod1.glb), [LOD2](model/ochre/lod2.glb) | [source.blend](model/ochre/source.blend) | [hero](previews/ochre/hero.png), [detail](previews/ochre/detail.png) |
| Navy | [ship.glb](model/navy/ship.glb) | [LOD1](model/navy/lod1.glb), [LOD2](model/navy/lod2.glb) | [source.blend](model/navy/source.blend) | [hero](previews/navy/hero.png), [detail](previews/navy/detail.png) |

The palettes share [static collision](model/collision.glb). [Validation](validation.json) measures the actual delivered GLBs; [source/export comparisons](export-review.json) compare renders from each packed source with its GLB reimport. Scope exclusions are recorded explicitly in the validation matrix.

```sh
blender -b -t 1 --factory-startup --python-exit-code 1 --python potc/common/v5_review.py -- --asset-dir potc/tartane --resolution 640
blender -b -t 1 --factory-startup --python-exit-code 1 --python potc/common/v5_audit.py -- --asset-dir potc/tartane --source-root . --resolution 480
python potc/common/v5_integrity.py --asset-dir potc/tartane --source-root .
```

## Researched deck and interior reconstruction

The v5 layout is documented in [layout-research.json](layout-research.json). Dimensions, frame spacing, compartments and fitting positions are authored estimates fitted to the preserved POTC-family hull. These sources do not document the proprietary retail model and do not establish exact stock interiors. No museum image is copied into the model or its textures.

- Open central well from -0.25L to +0.25L, narrow sole boards at -0.20 m leaving bilge visible.
- Paired frames at 0.42 m nominal spacing, mast heel/step and thwarts; small fore and aft working platforms.
- One tiller, light anchor, oars, net-rope coil, small planked fishing-tackle boxes and hand cleats.

Fishing gear is a functional reconstruction, not an archaeological inventory. No enclosed hold, cabin, stairs, cannon or capstan; decorative floor boards do not assert continuous historical ceiling.

References read: [Nautical Archaeology Digital Library: Sardinaux](https://www.shiplib.org/shipwrecks/sardinaux), [ANCRE: La Diligente, royal tartane, 1738](https://ancre.fr/en/monograph/19-monographie-de-la-diligente-tartane-du-roi-1738.html), [Voile Latine de Sète: Bèla Latina restoration](https://voilelatinesete.org/bela-latina/).

Two small timber hand cleats sit on the bow and stern end platforms. Their feet follow the real platform sheer; the open well retains a clear passage beside its mast partners. No enclosed cabin or deck hatch is added.
