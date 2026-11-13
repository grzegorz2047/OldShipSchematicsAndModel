# Old ship schematics and model: a snow of about 1710

[Polska wersja](README.pl.md)

This repository is a guide to building one sailing warship of the early 18th century, and a set of open data and
drawings to build it from. The ship is a **snow**: a small two-masted square-rigger of about 1710, 28.0 m on deck
between the rabbets and 7.60 m wide over the planking, with ten guns on one deck, a steering wheel and her sails
furled at anchor. We call her the **reference model**. Every number in the guide is either taken from a source of
the period, from later studies, from our own reasoning, or from the reference model itself, and each is labelled so.

The guide is written for two kinds of reader:

- **a person** who wants to rebuild such a ship in Blender, in a CAD program or on paper, and then to design other
  ships of the period in the same way;
- **an AI agent** that does the same job: the data files are machine-readable, every column is described in
  [`data/SCHEMA.md`](data/SCHEMA.md), and every parameter carries its unit, its confidence and the chapter that
  explains it.

The guide, the description of the data, the drawings and the drawing booklet are in English and Polish. The Polish
text is a full version, not a word-for-word translation.

## What is where

| Folder or file | What it holds |
|---|---|
| `docs/en/`, `docs/pl/` | the guide: chapters, an appendix, a list of sources and a glossary (English and Polish; the files have the same names in both folders) |
| `data/` | the numbers of the reference model: parameters, table of offsets, spars, every rope segment, deck layout, work stations, moving parts, the map of names; described in `data/SCHEMA.md` and `data/SCHEMA.pl.md` |
| `plans/` | drawings made from the data by script: lines plan, sections, deck plan, spar, sail and rigging plans, belaying plan and details of the fittings; SVG sheets in millimetres at true paper size, PNG previews in `plans/png/` (not to scale), all sheets in `plans/plans-en.pdf`; Polish sheets in `plans/pl/` and `plans/plans-pl.pdf` |
| `drawing-tutorial/` | a printable step-by-step drawing booklet for young artists (about 12 to 16 years old), in English and Polish, with the scripts that made it |
| `model/` | the model files of the reference ship |
| `blender/` | the scripts that build the reference model in Blender |
| `LICENSE` | the MIT licence |

### `model/`

This folder holds the model files of the reference ship in glTF binary form (GLB), with English names:

| File | What it is |
|---|---|
| `model/snow.glb` | the full model, about 31 MB and 230 000 triangles: every moving part is its own node with its axis and range, and the 142 work stations are empty nodes |
| `model/snow_lod1.glb`, `model/snow_lod2.glb` | two simpler levels of detail, one mesh each (about 50 % and 5 % of the triangles) |
| `model/snow_collision.glb` | 36 simple collision solids, nodes `collision_*` |

Their node names and extra data are described in [chapter 14](docs/en/14-using-the-model-in-a-game.md), and the
checks they pass in [chapter 13](docs/en/13-3d-quality-checklist.md).

### `blender/`

This folder holds the generator: the Python scripts for Blender 5.2 that built the reference model, tested it and
wrote the files in `data/`, `plans/` and `model/`. One command builds the ship, from the repository root:

```
blender -b --factory-startup --python blender/buduj.py -- --glb --rendery none
```

The scripts are published as they were used, in Polish (module names, variables, comments).
[Chapter 10](docs/en/10-building-in-blender.md) explains how to run them, what each module does and where the
ship's numbers are, and gives a glossary of the Polish words in the code. The tool
`blender/nazwy_na_angielskie.py` turns the Polish names in a built file into the English names of `model/`, using
`data/names-map.csv`.

## Where to start

Read [chapter 01](docs/en/01-ship-type-and-era.md) first whatever your goal: it explains the ship type, the date and
the confidence labels used everywhere. Then choose a path.

**On paper or in CAD.** Read [chapter 02](docs/en/02-hull-lines-and-offsets.md) for the lines plan and the table of
offsets, then [chapter 11](docs/en/11-building-in-cad-or-on-paper.md), which takes you step by step from
`data/offsets.csv`, `data/spars.csv` and `data/rigging-lines.json` to a drawing, a CAD model or a card or wooden
model, with control dimensions to check your work. Compare with the sheets in `plans/`. For younger readers who
want to draw the ship rather than construct it, the booklet in `drawing-tutorial/` is the easier way in.

**In Blender.** Read chapters 01 to 09 in order: they go from the hull lines through the structure, decks, masts,
standing and running rigging, ropes and sails to the deck machinery, and each ends with a worked example from the
reference model. Check your model against [chapter 13](docs/en/13-3d-quality-checklist.md).
[Chapter 10](docs/en/10-building-in-blender.md) shows how to run the scripts in `blender/` that built the reference
model itself.

**In a game.** Read [chapter 14](docs/en/14-using-the-model-in-a-game.md): it explains the files in `model/`, the
coordinates, the node names, the work stations, the moving parts, walking on the decks, the two steering variants,
the ropes that must follow moving yards, levels of detail and collisions. The data it uses are
`data/stations.csv`, `data/moving-parts.csv`, `data/deck-layout.json`, `data/rigging-lines.json` and
`data/names-map.csv`. The [appendix on handling the ship](docs/en/appendix-sail-handling.md) suggests game mechanics
that follow from how the crew really worked the sails.

**For another ship.** [Chapter 12](docs/en/12-designing-other-ships.md) shows which parameters to change, how the
rig variants differ, what changes with the date, what to check after each change, and two worked examples: a sloop
of about 21 m and a three-masted ship of about 32 m.

## Chapters

| Chapter | What it covers |
|---|---|
| [01. Ship type and era](docs/en/01-ship-type-and-era.md) | How to choose a type and a date, take the main dimensions from documented ships and avoid anachronisms; why the reference model is a snow of about 1710. |
| [02. Hull lines and offsets](docs/en/02-hull-lines-and-offsets.md) | The lines plan, the shape numbers, the midship frame drawn with arcs, the table of offsets of the reference model and the checks of displacement and fairness. |
| [03. Hull construction](docs/en/03-hull-construction.md) | Keel, stem, sternpost, frames, wales and planking: what each member does, how big it is, how it looks and how to model it. |
| [04. Decks, bulwarks, stern and head](docs/en/04-decks-bulwarks-stern-head.md) | Decks with camber and sheer, bulwarks, ports and lids, channels, catheads, the transom, the rudder, the head and a deck layout with room to work. |
| [05. Masts and spars](docs/en/05-masts-and-spars.md) | From deck length and breadth to a full spar table with the period rules of proportion, and how to draw and model the spars. |
| [06. Standing rigging](docs/en/06-standing-rigging.md) | Shrouds, ratlines, stays, backstays, the bowsprit rigging and the ropes on the yards, with the two ends and the diameter of every line. |
| [07. Running rigging and belaying](docs/en/07-running-rigging-and-belaying.md) | The lead of every running rope, a reconstructed belaying plan, the ropes with an end on a moving spar and the bracing limits of the yards. |
| [08. Ropes, blocks and sails](docs/en/08-ropes-blocks-and-sails.md) | How rope is made and how strong it is, blocks and deadeyes, how sails are built and look in each state, and how to draw ropes in 3D without flicker. |
| [09. Deck machinery and fittings](docs/en/09-deck-machinery.md) | Capstan, pumps, steering, guns, anchors, boats, bell and smaller fittings: parts, sizes, how they are worked and what moves. |
| [10. Building the ship in Blender](docs/en/10-building-in-blender.md) | Running the generator scripts: one build step by step, the modules, the parameters, the checks, the textures, the drawings and data, the renaming tool and a glossary of the Polish words in the code. |
| [11. Building the ship in CAD or on paper](docs/en/11-building-in-cad-or-on-paper.md) | Rebuilding the ship from the data files by hand, in any CAD program or as a card or wooden model, with control dimensions. |
| [12. Designing other ships from this one](docs/en/12-designing-other-ships.md) | Which parameters to change, rig variants, moving the date, the checks after each change and two worked examples. |
| [13. 3D quality checklist](docs/en/13-3d-quality-checklist.md) | Tests for units, names, pivots, meshes, interpenetration, UV maps, materials, file size, levels of detail, collisions and walking, and the mistakes we made. |
| [14. Using the model in a game](docs/en/14-using-the-model-in-a-game.md) | The model and data files from a game's point of view: coordinates, nodes, stations, moving parts, steering, dynamic ropes, collisions and the towed boat. |
| [Appendix. Handling the ship](docs/en/appendix-sail-handling.md) | How the crew sets, reefs and furls the sails, tacks, wears, heaves to and anchors; men and time; game mechanics that follow. |
| [Sources](docs/en/sources.md) | Every source cited in the chapters, once, with the chapters that cite it. |
| [Glossary](docs/en/glossary.md) | All terms of the chapters in alphabetical order, English, Polish and a short explanation. |

## Coordinates and units

All data files use metres and degrees, and write every point as **[x, s, z]** in the ship's own axes
(`data/SCHEMA.md`):

| Axis | Direction | Zero |
|---|---|---|
| x | athwartships, **positive to port** (larboard) | centreline |
| s | fore and aft, **positive forward** | middle of the 28.0 m deck length between rabbets (stem rabbet at the deck s = +14.0, sternpost s = −14.0) |
| z | up | design waterline |

The triple (s, x, z) is right-handed. Conversions:

- glTF and the game files (+Y up): (X, Y, Z) = (x, z, s); the bow points to +Z.
- Blender (Z up): (X, Y, Z) = (x, −s, z); the bow points to −Y.

Plan polygons are [x, s]. JSON files repeat this description in their field `coordinate_system`; CSV files start with
comment lines beginning with `#`. Key names end with their unit: `_m` metres, `_deg` degrees, `_m2` square metres.

## Confidence labels

Every value in the guide and in `data/parameters.json` carries one of four labels, explained in
[chapter 01](docs/en/01-ship-type-and-era.md):

- **period**: a source of the time, or several that agree;
- **secondary**: a modern study, a forum, a model kit, a replica, or a summary we could not check against the
  original;
- **our inference**: our own calculation or reconstruction, with no direct source;
- **reference model**: a value chosen or measured in the reference model.

Many period rules come from Steel (1794), some 80 years after our date, and from Lever (1808); the chapters say
where earlier sources differ.

## Limits of the reference model

The reference model is a careful reconstruction, not a surviving ship, and it is not finished. Know its limits
before you copy it:

- **The run below the waterline is not fair.** Between the sternpost and about s = −4 the hull carries bumps of
  1–5 cm, and the check for a fair hull fails there (34 surplus lobes). The topsides and the fore body are fair. The
  fault is in the table of offsets itself; when you loft your own hull, treat the offsets aft of s = −4 and below
  waterline −1.0 as still to be faired ([chapter 02](docs/en/02-hull-lines-and-offsets.md),
  [chapter 13](docs/en/13-3d-quality-checklist.md), check D7).
- **The sails are furled and the ship is at anchor.** Set sails exist only as estimated sizes in
  `data/parameters.json` ([chapter 08](docs/en/08-ropes-blocks-and-sails.md)).
- **The rigging does not move by itself.** Every rope is fixed geometry that sags under its own weight only: ropes
  do not run through their blocks and do not move in the wind. Segments with an end on a moving part are marked, and a
  game must redraw them itself ([chapter 07](docs/en/07-running-rigging-and-belaying.md),
  [chapter 14](docs/en/14-using-the-model-in-a-game.md)). Ropes that work only with set sails (tacks, bowlines,
  leechlines, reef tackles, the halliards, sheets and downhauls of the staysails and the jib, among others) are not
  modelled.
- **There is nothing below the deck.** The hold and the cabin are not built; the main hatch ladder and the companion
  stairs lead down to spaces that are not modelled. Inner timbers such as the keelson are described but not modelled
  ([chapter 03](docs/en/03-hull-construction.md)).
- **The belaying plan is a reconstruction.** We found no period belaying plan for a brig or snow, and the pin rails
  along the bulwark are probably an anachronism for 1710 ([chapter 07](docs/en/07-running-rigging-and-belaying.md)).
- **Many sizes are estimates.** Many machine dimensions for small ships of 1700–1720 are not recorded and are our
  estimates ([chapter 09](docs/en/09-deck-machinery.md)).
- **Some checks are still open**: the fair hull (above), free passage at the bow with all guns run in, and seven
  small faces with crossed edges in the stern carvings and the hull top
  ([chapter 13](docs/en/13-3d-quality-checklist.md), checks D7, J5 and D8).
- **Damage is not modelled**: no holes, fire, cut ropes or broken spars; chapter 14 says how the data prepare for
  them.

Numbers marked "at the time of writing" change a little whenever the model is rebuilt. The files in `data/` are
always the current values.

## Licence and material from others

The guide, the data, the drawings and the scripts in this repository are released under the MIT licence (see
[`LICENSE`](LICENSE)).

Material from others is **linked, not copied**, with one exception, the textures inside the model files:

- The textures of the reference model are made from eight photographic textures of Poly Haven, all CC0. The files
  in `model/` contain these pictures after our scripts turned the grain, changed the colours and laid them out as
  plank atlases. The original Poly Haven files are not in this repository: `blender/tekstury_cc0_spis.json` lists
  each asset with its page and authors, and [chapter 10](docs/en/10-building-in-blender.md) says how to download
  them for your own build.
- The period plans of F. H. af Chapman (*Architectura Navalis Mercatoria*, 1768) used for calibration are public
  domain; we link to them (Wikimedia Commons and Sjöhistoriska museet) and do not copy them.
- Plans and models of the Royal Museums Greenwich are linked for viewing only, under the museum's terms.
- Facts from books, articles, forums and Wikipedia are summarised in our own words; every source is listed in
  [Sources](docs/en/sources.md).
