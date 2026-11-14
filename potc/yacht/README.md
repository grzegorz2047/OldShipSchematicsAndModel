# POTC2003 yacht: two authored palettes

Fuller rounded bilge, broad transom, raised aft deck, square fore/main sails and a short mizzen.

This is a new procedural reconstruction of the ordinary class-6 yacht, with 16 guns. Its nominal 21.5 × 6.1 m hull is an authored design, not a measurement or extraction of the 2003 proprietary game model. The inspected original-POTC Yacht port screenshot shows three masts, three fore/main square-yard tiers and a short aft mast. Furled sails in that image do not establish every set-sail corner; our lateen mizzen and set-sail outlines are authored inference.

Ochre and navy change hull paint and trim. Deck, spars, rope, cloth and metal keep their deliberate natural materials. These are static duel visuals with shared static hull/deck collision and two LODs per palette. No walking, animation or runtime adapter is claimed.

Sources and precise claims are in [design.json](design.json). Hull offsets, mast positions, sail dimensions and paint values are in [spec.json](spec.json). The method follows [the repository guide](../../docs/en/12-designing-other-ships.md), with actual exported-GLB inspection and validation.

Built and validated with **Blender 5.2.3**. Use Blender **5.2 or newer** for rebuilding and opening the packed source scenes.

The builder writes the delivered asset folder. Run acceptance again after every source or model change. The detail renderer reimports the delivered GLB and records review lighting and every temporary cutaway visibility change; it never changes model geometry. Inspect its deck, hull/rig and interior images, then record concrete findings in `detail-review.json` before the v5 acceptance run.

```sh
blender -b -t 1 --factory-startup --python-exit-code 1 --python potc/yacht/build.py
```

The local builder finishes with the explicit [cannon surface repair](gun_surface_repair.py). Its [measured ledger](surface-repair.json) binds both packed scenes and all six visual exports: continuous barrel UV0/AO1 charts with one underside seam, a documented 5% density compensation, and matching native FREE corner normals plus the final post-export normal correction. This stage preserves positions, triangle indices, the remaining objects, material/image data and collision bytes; it does not claim a new architecture build. Photography, manual review and the full audit are renewed after the surface revision.

## Delivered files

| Palette | Main model | Distance levels | Packed source | Actual GLB views |
|---|---|---|---|---|
| Ochre | [ship.glb](model/ochre/ship.glb) | [LOD1](model/ochre/lod1.glb), [LOD2](model/ochre/lod2.glb) | [source.blend](model/ochre/source.blend) | [hero](previews/ochre/hero.png), [detail](previews/ochre/detail.png) |
| Navy | [ship.glb](model/navy/ship.glb) | [LOD1](model/navy/lod1.glb), [LOD2](model/navy/lod2.glb) | [source.blend](model/navy/source.blend) | [hero](previews/navy/hero.png), [detail](previews/navy/detail.png) |

The palettes share [static collision](model/collision.glb). [Validation](validation.json) measures the actual delivered GLBs; [source/export comparisons](export-review.json) compare renders from each packed source with its GLB reimport. Scope exclusions are recorded explicitly in the validation matrix.

```sh
blender -b -t 1 --factory-startup --python-exit-code 1 --python potc/common/v5_review.py -- --asset-dir potc/yacht --resolution 640
blender -b -t 1 --factory-startup --python-exit-code 1 --python potc/common/v5_audit.py -- --asset-dir potc/yacht --source-root . --resolution 480
python potc/common/v5_integrity.py --asset-dir potc/yacht --source-root .
```

## Researched deck and interior reconstruction

The v5 layout is documented in [layout-research.json](layout-research.json). Dimensions, frame spacing, compartments and fitting positions are authored estimates fitted to the preserved POTC-family hull. These sources do not document the proprietary retail model and do not establish exact stock interiors. No museum image is copied into the model or its textures.

- Framed cargo/stores hold from -0.27L to +0.35L, floor at -0.70 m.
- Compact panelled after cabin from -0.47L to -0.29L, floor 0.65 m beneath the 1.05 m raised quarterdeck; approximate clear height 2.05 m.
- 1.9 × 1.45 m open main hatch at +0.12L; offset descending quarterdeck companion; real door and trimmed stern lights.
- Sixteen guns retain one battery; start moves to -0.24L to clear the cabin bulkhead.

The 21.5 m reconstruction is smaller than the royal references. Royal furniture types and stern ornament are family analogues, not proof of the game Yacht interior.

References read: [Royal Museums Greenwich NPD0668: Royal Charlotte apartments, 1801](https://www.rmg.co.uk/collections/objects/rmgc-object-459294), [Royal Museums Greenwich NPD0989: Carolina plan, August 1720](https://www.rmg.co.uk/collections/objects/rmgc-object-532273), [Royal Museums Greenwich SLR0394: Peregrine Galley contemporary model](https://www.rmg.co.uk/collections/objects/rmgc-object-66355).

The short after cabin uses one offset descending companion through its forward doorway. Its roof remains intact above the room; there is no second shaft consuming the limited furnishing area.

The two decorated aft lights sit above the retained hanging-knee tops and aft main-sole strip, with a real 0.3675 m high glazing band below the original roof limit. Every retained closed pane looks through an actual timber opening; structural knees and deck timber remain intact. The exact light band is an authored fitting choice, not a traced royal-yacht or stock-game interior plan.
