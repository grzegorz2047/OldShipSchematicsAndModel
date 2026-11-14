# POTC2003 xebec: two authored palettes

Long fine pointed hull, strongly raked fore/mizzen, three lateens and long low bowsprit.

This is a new procedural reconstruction of the ordinary class-5 xebec, with 20 guns. Its nominal 28.0 × 6.6 m hull is an authored design, not a measurement or extraction of the 2003 proprietary game model. Contemporary stock-game discussion explicitly calls Xebec fully fore-and-aft rigged; game wiki notes overhanging bowsprit and aft mizzen. Our three-lateen reconstruction follows these cues and historical type, with authored hull proportions and sail sizes.

Ochre and navy change hull paint and trim. Deck, spars, rope, cloth and metal keep their deliberate natural materials. These are static duel visuals with shared static hull/deck collision and two LODs per palette. No walking, animation or runtime adapter is claimed.

Sources and precise claims are in [design.json](design.json). Hull offsets, mast positions, sail dimensions and paint values are in [spec.json](spec.json). The method follows [the repository guide](../../docs/en/12-designing-other-ships.md), with actual exported-GLB inspection and validation.

Built and validated with **Blender 5.2.3**. Use Blender **5.2 or newer** for rebuilding and opening the packed source scenes.

The builder writes the delivered asset folder. Run acceptance again after every source or model change. The detail renderer reimports the delivered GLB and records review lighting and every temporary cutaway visibility change; it never changes model geometry. Inspect its deck, hull/rig and interior images, then record concrete findings in `detail-review.json` before the v5 acceptance run.

```sh
blender -b -t 1 --factory-startup --python-exit-code 1 --python potc/xebec/build.py
```

## Delivered files

| Palette | Main model | Distance levels | Packed source | Actual GLB views |
|---|---|---|---|---|
| Ochre | [ship.glb](model/ochre/ship.glb) | [LOD1](model/ochre/lod1.glb), [LOD2](model/ochre/lod2.glb) | [source.blend](model/ochre/source.blend) | [hero](previews/ochre/hero.png), [detail](previews/ochre/detail.png) |
| Navy | [ship.glb](model/navy/ship.glb) | [LOD1](model/navy/lod1.glb), [LOD2](model/navy/lod2.glb) | [source.blend](model/navy/source.blend) | [hero](previews/navy/hero.png), [detail](previews/navy/detail.png) |

The palettes share [static collision](model/collision.glb). [Validation](validation.json) measures the actual delivered GLBs; [source/export comparisons](export-review.json) compare renders from each packed source with its GLB reimport. Scope exclusions are recorded explicitly in the validation matrix.

```sh
blender -b -t 1 --factory-startup --python-exit-code 1 --python potc/common/v5_review.py -- --asset-dir potc/xebec --resolution 640
blender -b -t 1 --factory-startup --python-exit-code 1 --python potc/common/v5_audit.py -- --asset-dir potc/xebec --source-root . --resolution 480
python potc/common/v5_integrity.py --asset-dir potc/xebec --source-root .
```

## Researched deck and interior reconstruction

The v5 layout is documented in [layout-research.json](layout-research.json). Dimensions, frame spacing, compartments and fitting positions are authored estimates fitted to the preserved POTC-family hull. These sources do not document the proprietary retail model and do not establish exact stock interiors. No museum image is copied into the model or its textures.

- Shallow framed hold -0.30L to +0.38L, sole -0.85 m; an actual fitted water cask and planked provisions box occupy supported side footprints. The narrow forward area stays clear; no invisible cable locker is claimed.
- Low after cabin -0.47L to -0.35L, floor -0.25 m and modest hinged seat locker combining seating and storage, with no unsupported freestanding adult berth; no stacked gun decks.
- 2.0 × 1.4 m centerline hatch at +0.13L, offset poop companion, visible pump and belaying fittings.
- Twenty open-deck guns retain clear working lanes; three lateen yards, detailed lead blocks and restrained stern rail/trim distinguish the fitting-out.

Le Requin is a family analogue, not a reproduction or a stock game interior plan. Oars are a historical xebec trait but the reconstruction does not invent a full rowing battery or change the POTC armament.

References read: [ANCRE: Le Requin xebec, 1750](https://ancre.fr/en/monograph/18-monographie-du-requin-chebec-1750-.html), [ANCRE: Le Requin English sample PDF, page 2](https://ancre.fr/en/index.php?controller=attachment&id_attachment=81), [Museums Victoria ST34691: Chebec class sailing model](https://collections.museumsvictoria.com.au/items/395808).

The short after cabin uses one offset descending companion through its forward doorway. Its roof remains intact above the room; there is no second shaft consuming the limited furnishing area.

The pointed after cuddy is deliberately modest: a combined seat locker preserves the clear aisle. A freestanding adult berth or royal-style cabin is not supported by the inspected source material or the available authored floor footprint.

A small high casement faces the weather deck through the forward cuddy wall. The 0.55 × 0.195 m opening is cut through the actual planks and has two retained closed glass panes. This glazing layout is an authored inference for the available space, not a recovered historical or stock-game interior; the pointed stern stays intact.

The cuddy seating and storage share one actual hollow planked locker, with a strong hinged timber seat lid and visible iron hinge leaves and pins. Its supported 0.44 × 0.52 m footprint preserves the narrow aisle; a separate long bench is not claimed.

The descending companion uses the supported side of its existing treads to pass beside the mizzen before returning to the cabin doorway. The mast, rails, hull and modest cuddy furniture remain in place. This is an authored clearance-fitted passage, not a recovered historical or stock-game route.
