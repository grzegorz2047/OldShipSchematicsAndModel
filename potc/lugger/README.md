# POTC2003 lugger: two authored palettes

Low narrow hull, two dominant square-rigged masts and a small aft fore-and-aft sail.

This is a new procedural reconstruction of the ordinary class-6 lugger, with 12 guns. Its nominal 23.0 × 5.8 m hull is an authored design, not a measurement or extraction of the 2003 proprietary game model. Game-specific wiki describes a square-rigged sloop-built lugger. Stock walk script identifies two large climbing mast groups. Set-sail shapes and aft gaff are authored inference; this is not the later custom three-masted LuggerVML/Heavy Lugger model.

Ochre and navy change hull paint and trim. Deck, spars, rope, cloth and metal keep their deliberate natural materials. These are static duel visuals with shared static hull/deck collision and two LODs per palette. No walking, animation or runtime adapter is claimed.

Sources and precise claims are in [design.json](design.json). Hull offsets, mast positions, sail dimensions and paint values are in [spec.json](spec.json). The method follows [the repository guide](../../docs/en/12-designing-other-ships.md), with actual exported-GLB inspection and validation.

Built and validated with **Blender 5.2.3**. Use Blender **5.2 or newer** for rebuilding and opening the packed source scenes.

The builder writes the delivered asset folder. Run acceptance again after every source or model change. The detail renderer reimports the delivered GLB and records review lighting and every temporary cutaway visibility change; it never changes model geometry. Inspect its deck, hull/rig and interior images, then record concrete findings in `detail-review.json` before the v5 acceptance run.

```sh
blender -b -t 1 --factory-startup --python-exit-code 1 --python potc/lugger/build.py
```

## Delivered files

| Palette | Main model | Distance levels | Packed source | Actual GLB views |
|---|---|---|---|---|
| Ochre | [ship.glb](model/ochre/ship.glb) | [LOD1](model/ochre/lod1.glb), [LOD2](model/ochre/lod2.glb) | [source.blend](model/ochre/source.blend) | [hero](previews/ochre/hero.png), [detail](previews/ochre/detail.png) |
| Navy | [ship.glb](model/navy/ship.glb) | [LOD1](model/navy/lod1.glb), [LOD2](model/navy/lod2.glb) | [source.blend](model/navy/source.blend) | [hero](previews/navy/hero.png), [detail](previews/navy/detail.png) |

The palettes share [static collision](model/collision.glb). [Validation](validation.json) measures the actual delivered GLBs; [source/export comparisons](export-review.json) compare renders from each packed source with its GLB reimport. Scope exclusions are recorded explicitly in the validation matrix.

```sh
blender -b -t 1 --factory-startup --python-exit-code 1 --python potc/common/v5_review.py -- --asset-dir potc/lugger --resolution 640
blender -b -t 1 --factory-startup --python-exit-code 1 --python potc/lugger/render-detail-overrides.py
blender -b -t 1 --factory-startup --python-exit-code 1 --python potc/common/v5_audit.py -- --asset-dir potc/lugger --source-root . --resolution 480
python potc/common/v5_integrity.py --asset-dir potc/lugger --source-root .
```

## Researched deck and interior reconstruction

The v5 layout is documented in [layout-research.json](layout-research.json). Dimensions, frame spacing, compartments and fitting positions are authored estimates fitted to the preserved POTC-family hull. These sources do not document the proprietary retail model and do not establish exact stock interiors. No museum image is copied into the model or its textures.

- Large uncluttered working hold -0.30L to +0.37L, floor -0.80 m, cargo laid beside a central aisle.
- Small after cuddy -0.47L to -0.33L, sunk sole -0.30 m, bench and locker, with no freestanding adult berth; no saloon table suite.
- 2.0 × 1.35 m main hatch at +0.12L, low quarterdeck companion and visible ladder/stair.
- Twelve open-battery guns, low bulwarks, compact capstan with messenger rope, and actual fitted planked cargo boxes.

Later Cornish fishing records constrain accommodation scale, not the chronology or exact rig of the game asset. Cargo assortment and compartment dimensions are authored.

References read: [Royal Museums Greenwich SLR0606: French 8-gun lugger, circa 1800](https://www.rmg.co.uk/collections/objects/rmgc-object-66567), [National Maritime Museum Cornwall / Tony Pawlyn: PZ.28 Ada](https://www.maritimeviews.co.uk/west-cornwall-luggers-and-mfv/pz-28-ada/).

The short after cabin uses one offset descending companion through its forward doorway. Its roof remains intact above the room; there is no second shaft consuming the limited furnishing area.

The compact after cuddy contains a real bench and locker. A freestanding adult berth is omitted: a 0.60 × 1.80 m mattress cannot retain the supported floor, 0.65 m aisle and descending door access inside this preserved hull. The Cornish analogue establishes a modest crew cuddy, not a fixed bed plan for this game family.

The modest aft casements use proportionate segmented timber jambs that follow the actual tapered reveal, leaving every retained glass pane clear through the hull opening. The exact glazing arrangement is an authored fitting choice informed by small timber-vessel construction, not an inspected plan of this proprietary game interior.

The intact hold review uses the explicit pose in [detail-camera-overrides.json](detail-camera-overrides.json), rendered by [render-detail-overrides.py](render-detail-overrides.py) through the frozen review engine. This moves the camera clear of companion treads while retaining every actual mesh, the 20 mm lens, 1.23 m eye height, lighting preset and 640 × 512 / 12-sample settings. The manifest records both the default and corrected poses and their input hashes.
