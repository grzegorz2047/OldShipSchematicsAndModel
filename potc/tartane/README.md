# POTC2003 tartane: two authored palettes

One lateen mast, low pointed ends, modest sheer and no battery.

This is a new procedural reconstruction of the ordinary class-7 tartane, with 0 guns. Its nominal 9.0 × 3.0 m hull is an authored design, not a measurement or extraction of the 2003 proprietary game model. Stock small fishing-boat role and one-mast status. Sail dimensions, deck arrangement and line offsets are authored reconstruction.

Ochre and navy change hull paint and trim. Deck, spars, rope, cloth and metal keep their deliberate natural materials. These are static duel visuals with shared static hull/deck collision and two LODs per palette. No walking, animation or runtime adapter is claimed.

Sources and precise claims are in [design.json](design.json). Hull offsets, mast positions, sail dimensions and paint values are in [spec.json](spec.json). The method follows [the repository guide](../../docs/en/12-designing-other-ships.md), with actual exported-GLB inspection and validation.

Built and validated with **Blender 5.2.3**. Use Blender **5.2 or newer** for rebuilding and opening the packed source scenes.

The default build rebuilds the delivered asset folder. Use `-- --out build/final/tartane` for a staging build. Run acceptance again after every source or model change.

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
blender -b -t 1 --factory-startup --python-exit-code 1 --python potc/common/v4_audit.py -- --asset-dir potc/tartane --source-root . --resolution 480
python potc/common/v4_integrity.py --asset-dir potc/tartane --source-root .
```
