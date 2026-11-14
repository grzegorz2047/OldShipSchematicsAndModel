# POTC2003 galeoth: two authored palettes

Broad round afterbody, pronounced quarterdeck, widely separated fore/main masts with square canvas and an aft lateen.

This is a new procedural reconstruction of the ordinary class-5 galeoth, with 16 guns. Its nominal 26.0 × 7.2 m hull is an authored design, not a measurement or extraction of the 2003 proprietary game model. Stock-derived walk script has widely separated fore/main climbing groups and high aft deck. Contemporary player discussion describes an armed fast trader and distinguishes the later gaff-boom Galeoth. The mixed square/lateen set rig is our inference, not a claim to recover the proprietary stock mesh.

Ochre and navy change hull paint and trim. Deck, spars, rope, cloth and metal keep their deliberate natural materials. These are static duel visuals with shared static hull/deck collision and two LODs per palette. No walking, animation or runtime adapter is claimed.

Sources and precise claims are in [design.json](design.json). Hull offsets, mast positions, sail dimensions and paint values are in [spec.json](spec.json). The method follows [the repository guide](../../docs/en/12-designing-other-ships.md), with actual exported-GLB inspection and validation.

Built and validated with **Blender 5.2.3**. Use Blender **5.2 or newer** for rebuilding and opening the packed source scenes.

The builder writes the delivered asset folder. Run acceptance again after every source or model change. The detail renderer reimports the delivered GLB and records review lighting and every temporary cutaway visibility change; it never changes model geometry. Inspect its deck, hull/rig and interior images, then record concrete findings in `detail-review.json` before the v5 acceptance run.

```sh
blender -b -t 1 --factory-startup --python-exit-code 1 --python potc/galeoth/build.py
```

## Delivered files

| Palette | Main model | Distance levels | Packed source | Actual GLB views |
|---|---|---|---|---|
| Ochre | [ship.glb](model/ochre/ship.glb) | [LOD1](model/ochre/lod1.glb), [LOD2](model/ochre/lod2.glb) | [source.blend](model/ochre/source.blend) | [hero](previews/ochre/hero.png), [detail](previews/ochre/detail.png) |
| Navy | [ship.glb](model/navy/ship.glb) | [LOD1](model/navy/lod1.glb), [LOD2](model/navy/lod2.glb) | [source.blend](model/navy/source.blend) | [hero](previews/navy/hero.png), [detail](previews/navy/detail.png) |

The palettes share [static collision](model/collision.glb). [Validation](validation.json) measures the actual delivered GLBs; [source/export comparisons](export-review.json) compare renders from each packed source with its GLB reimport. Scope exclusions are recorded explicitly in the validation matrix.

```sh
blender -b -t 1 --factory-startup --python-exit-code 1 --python potc/common/v5_review.py -- --asset-dir potc/galeoth --resolution 640
blender -b -t 1 --factory-startup --python-exit-code 1 --python potc/common/v5_audit.py -- --asset-dir potc/galeoth --source-root . --resolution 480
python potc/common/v5_integrity.py --asset-dir potc/galeoth --source-root .
```

## Researched deck and interior reconstruction

The v5 layout is documented in [layout-research.json](layout-research.json). Dimensions, frame spacing, compartments and fitting positions are authored estimates fitted to the preserved POTC-family hull. These sources do not document the proprietary retail model and do not establish exact stock interiors. No museum image is copied into the model or its textures.

- Broad cargo hold -0.27L to +0.37L, floor -0.90 m; fitted side casks and planked storage outside the center aisle, with the foremost supported boxes and rope coils in a forward cable/stores zone from +0.15L.
- After cabin -0.47L to -0.285L, sole 0.95 m, compact table/bench/berth/locker beneath 1.25 m quarterdeck.
- Main 2.2 × 1.6 m cargo hatch +0.08L, small fore stores hatch +0.31L, and offset quarterdeck companion.
- Sixteen-gun single battery start moves to -0.24L for bulkhead clearance; no oar benches or rowing gallery are invented.

Galeoth/galliot names cover differing historical rigs and hulls; these are explicit construction analogues, not an identified exact prototype. The game-derived mixed rig, hull form and count remain decisive.

References read: [Rijksmuseum NG-MC-674: Model of a Polacre / Daedalus](https://www.rijksmuseum.nl/nl/collectie/object/Model-van-een-polakker--be50c8b05850324bf29aaac85ed74070), [Royal Museums Greenwich SLR0394: small armed vessel construction analogue](https://www.rmg.co.uk/collections/objects/rmgc-object-66355).

The short after cabin uses one offset descending companion through its forward doorway. Its roof remains intact above the room; there is no second shaft consuming the limited furnishing area.

The modest aft casements use proportionate segmented timber jambs that follow the actual tapered reveal, leaving every retained glass pane clear through the hull opening. Their lower edges sit above the existing aft main-deck sole strip; no glass is presented as a window through solid deck timber. The exact glazing arrangement is an authored fitting choice informed by small timber-vessel construction, not an inspected plan of this proprietary game interior.
