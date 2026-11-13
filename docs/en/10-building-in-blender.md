# 10. Building the ship in Blender

## What this stage is for

The 3D model in `model/` was not modelled by hand. It is the output of a set of Python scripts for Blender, kept in
`blender/`. The scripts read the numbers of the reference model (the offsets, the spar rules, the rope list, the deck
layout), build every part from them, test the result and export it as glTF binary files (GLB). This chapter shows how
to run them yourself and how to find your way in the code.

At the end of this chapter you will have:

- a complete build of the ship in `build/`: a `.blend` file, the GLB file with its two levels of detail and the
  collision solids, the check report `kontrola.json` and control renders;
- the drawings and data files made again from your build, in a folder of your choice;
- the four files of `model/` made from your build, with English names;
- enough Polish words to read the code.

The scripts are written in Polish: module names, variable names and comments. They are published as they were used,
so that the code that made the model is the code you read. The glossary near the end of this chapter and
`data/names-map.csv` translate the words you meet most often. What a stage builds and why is explained in the chapters
of this guide that the comments point to ("rozdział 05" means chapter 05).

Read [chapter 12](12-designing-other-ships.md) if you want to change the ship, and
[chapter 13](13-3d-quality-checklist.md) for what the checks measure. Confidence labels are explained in
[chapter 01](01-ship-type-and-era.md); the numbers in this chapter are **reference model** values from our own runs.

## Concepts

- **Blender in background mode**: Blender started with `-b` runs a Python script without opening a window. Every step
  in this chapter works that way.
- **`bpy`**: the Python module of Blender. Scripts that import it run only inside Blender; the others run in any
  Python 3.
- **Factory settings** (`--factory-startup`): Blender starts without your preferences and add-ons, so a build does not
  depend on how your copy of Blender is set up.
- **Generator**: here, the set of scripts that builds the ship from numbers. Running it again with the same numbers
  gives the same file.
- **Stage** (Polish *etap*): one part of the build, such as the hull, the spars or the running rigging. Each stage is
  one module with a function `zbuduj(ctx)` ("build").
- **`ctx`**: a Python dictionary passed from stage to stage. It holds the parameters, the objects already built and
  the rope register.
- **Procedural texture**: a picture computed by a script (noise, plank layout), not photographed.
- **CC0**: the Creative Commons public domain dedication. A CC0 asset may be used for anything without asking or
  crediting [3].
- **GLB**: the single-file binary form of glTF 2.0 [1]. **Node**, **mesh**, **material** and **image** are the named
  parts of a glTF file; **extras** is a free field for application data [1].

## Requirements

| What | Version we used | What for |
|---|---|---|
| Blender | 5.2 | the build, the drawings model, the import test; other versions were not tested |
| Python 3 on the command line as `python` | 3.14, with numpy 2.5 and Pillow 13 | textures (`tekstury*.py`), deck plan picture, data files, the name tool |
| Chrome or Edge (optional) | any recent | PNG previews and PDF sets of the drawings; without it `rysunki.py` writes SVG only |
| Poly Haven textures (optional) | 2K JPG | the photographic texture set (see "Textures" below) |
| Free disk space | about 0.5 GB | `build/` after both builds, the renders and a trial run of the drawings (421 MB for us) |

The build scripts call `python` themselves for the texture steps, so `python` must start a Python 3 that has numpy
and Pillow (`python -m pip install numpy pillow`). Blender's own Python is used only for the steps that need `bpy`.

All commands below are run from the root folder of this repository. `blender` stands for the Blender program: on
Windows give the full path to `blender.exe` in the Blender installation folder, in quotes; on Linux and macOS the
`blender` command or the path to the program inside the application folder.

## Step by step: one build

### 1. Build with procedural textures

```
blender -b --factory-startup --python blender/buduj.py -- --glb --rendery none --out build/proceduralne
```

This builds the ship, saves `build/proceduralne/bryg.blend`, exports the GLB files and runs all checks; with
`--rendery none` it skips the renders. On our computer it took 4 minutes;
`build/proceduralne/bryg.glb` has the same 330 nodes and 230 419 triangles as the CC0 build, but is smaller
(29.2 MB instead of 31.0 MB), and the checks give the same 34 × `tak`, 2 × `info`, 0 × `nie`.

### 2. Build with the photographic CC0 textures (as the files in `model/`)

```
blender -b --factory-startup --python blender/buduj.py -- --glb --rendery all --tekstury-cc0 path/to/polyhaven
```

`path/to/polyhaven` is the folder where you put the Poly Haven textures (see "Textures" below). This is the command
that made the files in `model/`. On our computer the build itself took 3 minutes and the whole run, with checks and
renders, about 8 minutes.

### 3. Options

Everything after `--` belongs to the script. Options with a value:

| Option | Values | Default | Meaning |
|---|---|---|---|
| `--out` | folder | `build` | where the results go |
| `--rendery` | `all`, `none`, `detale`, `porownanie` or a comma list of view names | `all` | which control renders to make (*rendery* = renders) |
| `--tekstury-cc0` | folder | none | use the Poly Haven texture set from this folder |
| `--schemat` | `a`, `b` | `a` | paint scheme: `a` period (white bottom, oiled sides, black and ochre), `b` black hull (*schemat* = scheme) |
| `--etapy` | comma list | all stages | build only some stages, for example `kadlub,poklad,rufa_dziob` (*etapy* = stages) |
| `--naped` | `kolo`, `rumpel` | `kolo` | steering drive shown by default: wheel or deck tiller (*napęd* = drive) |
| `--lodz` | `za_rufa`, `na_pokladzie`, `brak` | `za_rufa` | the boat towed astern, on deck, or none (*łódź* = boat) |
| `--snow` | `0`, `1` | `1` | snow rig (trysail mast abaft the main mast) or plain brig |
| `--dzialo-polyhaven` | file | none | use a CC0 cannon model from this glTF file instead of our own guns (*działo* = gun) |
| `--statek` | name | `BRYG` | which ship definition in `parametry.py` to build (*statek* = ship) |

Flags without a value:

| Flag | Meaning |
|---|---|
| `--glb` | export the GLB files, the levels of detail and the collision file, then run the checks |
| `--kontrola` | run the checks without exporting (*kontrola* = check) |
| `--bez-blend` | do not save the `.blend` file (*bez* = without) |
| `--bez-ao` | do not bake ambient occlusion (faster, darker corners are lost) |
| `--nowe-tekstury` | rebuild the CC0 plank textures even if they exist (*nowe* = new) |

A build without `--glb` stops after the `.blend` file and the renders.

## The build, stage by stage

`buduj.py` ("build") runs the stages below in this order. The Polish module name is given with its meaning.

| # | Module | Meaning | What it does |
|---|---|---|---|
| 0 | `tekstury.py` | textures | procedural tiling textures (deck, side, paint, wood, iron, rope, canvas, window); runs in plain Python, only when `build/tekstury/` is empty |
| 0 | `tekstury_cc0.py`, `tekstury_deski.py` | CC0 textures, plank textures | with `--tekstury-cc0`: working copies of the Poly Haven pictures and our plank atlases (`td_*`) |
| 1 | `materialy.py` | materials | Blender materials laid out so that the glTF exporter writes them correctly |
| 2 | `rzedne.py`, `kadlub.py` | offsets, hull | the hull surface from the table of offsets, wales, bulwarks, decks, bulkheads, gun ports; keel, stem, sternpost; rudder |
| 3 | `poklad.py` | deck | rail cap, waterway, timber heads, mouldings, scuppers, port lids, ladder, breastwork |
| 4 | `rufa_dziob.py` | stern and bow | stern windows and carvings, lantern; knee of the head, scroll, head rails, catheads, hawse holes |
| 5 | `drzewca.py` | spars | masts, tops, caps, topmasts, snow mast, bowsprit, yards, gaff (Steel's rules, chapter 05) |
| 6 | `olinowanie.py` | rigging (standing) | channels, deadeyes, shrouds, lanyards, ratlines, futtock shrouds, stays, backstays, bowsprit rigging (chapter 06) |
| 7 | `wyposazenie.py`, `sterowanie.py` | fittings, steering | guns, capstan, pumps, hatches, fife rails and pin rails, wheel and tiller variants, boat, bell, anchors (chapter 09) |
| 8 | `ruchome.py` | running (rigging) | lifts, braces, clewlines, sheets, halliards, gaff ropes, coils on the pins (chapter 07) |
| 9 | `zagle.py` | sails | furled sails on the yards, gaff sail brailed in, head sails stowed (chapter 08) |
| 10 | `przenikanie.py` | interpenetration | motion limits from the geometry (port lids, gun recoil), later the merge of solids and the bracing range of the yards |
| 11 | `chodzenie.py` | walking | walkable surfaces, obstacles, stairs, work stations, walking test (`bryg_poklad.json`, nodes `stan_*`) |
| 12 | `kadlub.py` (`zabrudzenia`) | hull (dirt) | dirt in vertex colours: waterline band, streaks under ports and scuppers |
| 13 | `przenikanie.py` (`scal_bryly`, `porzadki`) | interpenetration | one clean solid per object; duplicate vertices, zero-area faces and loose parts removed |
| 14 | `olinowanie.py` (`zamocuj_konce`, `realizuj`) | rigging | rope ends pulled onto the parts they belong to; rope tubes made from the rope register |
| 15 | `eksport.py` | export | moving parts as separate nodes, the rest merged into static meshes; ambient occlusion baked; `bryg.glb` |
| 16 | `lod.py` | level of detail | `bryg_lod1.glb`, `bryg_lod2.glb` and the collision solids `bryg_kolizja.glb` |
| 17 | `kontrola.py`, `praktyki.py` | check, good practice | the report `kontrola.json` (see "Checks" below) |
| 18 | `rendery.py`, `plan_pokladu.py` | renders, deck plan | control renders in `build/rendery/`, a deck plan picture with the walking data |
| 19 | `kontrola_glb.py` | GLB check | the exported file against the source: images, colours, renders from the loaded GLB |

Helper modules: `parametry.py` (parameters, see below), `narzedzia.py` and `narzedzia_math.py` (tools: mesh builder,
tubes, curves), `deski.py` (planks: cuts the planking along the seams), `projekt_rzednych.py` (offsets design: turns
the table measured at the frames into the generator table), `plansza.py` (contact sheet of the renders).

## Where the parameters are and how to change them

All numbers of the ship are in one file, `blender/parametry.py`, in plain Python dictionaries:

| Dictionary | Content | Public data |
|---|---|---|
| `KADLUB` | hull: keel line, stem and stern profile, deck line, camber, rail heights, wales, gun ports | `data/parameters.json`, group `hull` |
| `LINIE_WREGI`, `RZEDNE_*` | table of offsets at the frames and the generator table | `data/offsets.csv` |
| `DRZEWCA` | spars from Steel's rules, positions, rake, steeve | `data/spars.csv` |
| `OLINOWANIE` | numbers and diameters of the standing ropes | `data/rigging-summary.csv` |
| `UKLAD` | deck layout: capstan, pumps, hatches, boat, steering, guns | `data/deck-layout.json` |
| `SCHEMATY`, `MATERIALY`, `MATERIALY_CC0`, `MATERIALY_TD` | paint schemes and materials | `data/parameters.json` |
| `STATKI` | named ship definitions (`BRYG`) | – |

`data/names-map.csv` (category `parameter`) gives the English name of every key, and `data/SCHEMA.md` the unit and
meaning. To build another ship, copy the `BRYG` definition, change the numbers and pass its name with `--statek`.
Which numbers to change, in which order, and what to check afterwards is the subject of
[chapter 12](12-designing-other-ships.md). After a change of the table at the frames (`LINIE_WREGI`), the
generator table in `parametry.py` is recomputed by `projekt_rzednych.py`:

```
python blender/projekt_rzednych.py
```

Without options it only prints the new table; with `--zapisz` (save) it rewrites it in `parametry.py` (the block
between `# >>> RZEDNE` and `# <<< RZEDNE`).

## What you get in `build/`

| File or folder | What it is |
|---|---|
| `bryg.blend` | the Blender scene before the export, with all objects separate (*bryg* = brig) |
| `bryg.glb` | the main GLB file (with Polish names) |
| `bryg_lod1.glb`, `bryg_lod2.glb` | levels of detail: about 50 % and about 5 % of the triangles |
| `bryg_kolizja.glb` | 36 collision solids, nodes `kolizja_*` (*kolizja* = collision) |
| `kontrola.json` | the check report |
| `parametry.json` | all parameters as JSON |
| `liny.json` | every rope: group, diameter, material, ends, length (*liny* = ropes) |
| `bryg_poklad.json` | walking data and work stations (*pokład* = deck) |
| `rendery/` | control renders and the deck plan picture |
| `tekstury/`, `tekstury_cc0/` | texture working copies |

The files in `build/` keep the Polish names of the generator. The names in `model/` are made from them by the
renaming tool (below). `build/` is listed in `.gitignore`.

## Checks

`kontrola.py` writes `build/kontrola.json`. Its main parts:

| Key | What it holds |
|---|---|
| `dobre_praktyki` | the good practice table: 36 criteria, each with `wynik` (result) `tak` (yes), `nie` (no) or `info`, and the numbers behind it |
| `wymiary`, `maszty`, `reje` | main dimensions, masts and yards measured on the model |
| `kadlub_powloka` | the hull shell: open edges, non-manifold edges, normals, volume, symmetry |
| `gestosc_tekseli_px_m` | texel density per material |
| `chodzenie`, `stanowiska_liczba` | walking test and number of work stations |
| `symetria_lin` | rope symmetry (port and starboard twins) |
| `konce_lin` | rope ends: every end must be attached (`wiszace` = hanging) |
| `bloki` | blocks: every block must be held (`bez_zaczepu` = without a hold) |
| `przenikanie` | interpenetration: pairs above the 5 mm threshold (`zgloszone_ponad_prog`) |
| `zakresy_ruchu`, `ograniczenia_ruchu` | moving parts tested across their range; the limits found |
| `glb`, `kontrola_glb` | the exported file loaded back and compared with the source |

Each check is explained in [chapter 13](13-3d-quality-checklist.md). Three of them were added late and are worth
knowing by name:

- **rope ends** (`konce_lin`, chapter 13, E5): each end of each rope must lie within 1 cm of another part, inside it,
  or on another rope;
- **blocks** (`bloki`, E6): each block must touch a solid, hang on a tarred pendant, sit on a straight taut tackle or
  have a strop;
- **twisted tubes** (criterion "brak skręconych rurek lin", D8): no quad of a rope tube may have opposite edges that
  cross.

A good build has 0 criteria with `nie`. Our build with the CC0 textures gave 34 × `tak`, 2 × `info`, 0 × `nie`;
0 hanging rope ends of 2 136; 0 of 105 blocks without a hold; 0 interpenetrating pairs above the threshold.

## Textures: procedural and CC0

Without `--tekstury-cc0` every material uses the procedural textures of `tekstury.py`. Nothing has to be downloaded.

With `--tekstury-cc0 FOLDER` the deck, the side planking, the paints, the spar and fitting wood, the iron and the
canvas use photographs from Poly Haven [2], all CC0 [3]; the ropes and the glass stay procedural. The pictures are not
in this repository. `blender/tekstury_cc0_spis.json` lists all 18 assets we had, with the page of each asset, the
authors, the licence, the real tile size and the file names. Eight of them are used by the generator (`"uzywany":
true`): `wood_planks_grey`, `brown_planks_09`, `brown_planks_03`, `black_painted_planks`, `white_planks_clean`,
`oak_veneer_01`, `rough_linen`, `rusty_metal_04`.

To prepare the folder:

1. Open the page of each used asset (for example https://polyhaven.com/a/wood_planks_grey).
2. Download at 2K resolution, JPG format, the maps **Diffuse**, **Normal (GL)** and **AO/Rough/Metal**. Poly Haven
   names them `<id>_diff_2k.jpg`, `<id>_nor_gl_2k.jpg` and `<id>_arm_2k.jpg`.
3. Put the three files of each asset in a subfolder named after the asset id:

```
polyhaven/
  wood_planks_grey/
    wood_planks_grey_diff_2k.jpg
    wood_planks_grey_nor_gl_2k.jpg
    wood_planks_grey_arm_2k.jpg
  brown_planks_09/
    ...
```

4. Run the build with `--tekstury-cc0 polyhaven` (or the path to the folder).

If the folder has its own `_spis.json` (same entries as the list), it is used; otherwise the list in `blender/` is.
The files you downloaded are never changed: the build writes its working copies (rotated grain, greyed paint and
canvas, our plank atlases `td_*`) to `build/tekstury_cc0/`. If you change a texture, delete that folder or pass
`--nowe-tekstury`.

## Drawings and data

`blender/rysunki.py` ("drawings") makes the data files of `data/` and the sheets of `plans/` from a finished build:

1. `model_rysunkowy.py` (drawing model) runs the generator again up to the sails, in memory, and records the numbers
   and the rope register; then it projects the meshes of `bryg.blend` with hidden lines removed;
2. `dane_publiczne.py` (public data) writes `data/` with English names (`nazwy_publiczne.py`, public names);
3. `arkusze_*.py` (sheets: `kadlub` hull, `konstrukcja` structure, `poklad` deck, `wyposazenie` fittings,
   `takielunek` rigging) draw the SVG sheets in English and Polish;
4. Chrome or Edge, without a window, makes the PNG previews and the PDF sets;
5. `kontrola_publiczna.py` (public check) compares the data with the model and looks for Polish words left in the
   data and on the English sheets.

By default `rysunki.py` writes into `data/` and `plans/` of the repository. To try it without touching them, give
another folder with `--publiczne`:

```
blender -b --factory-startup --python blender/rysunki.py -- --migawka --publiczne build/rysunki_test
```

`--migawka` (snapshot) first copies the build results and the generator modules to `build/rysunki_robocze/`, so the
drawings always come from one consistent state. On our computer the run took a little over a minute and ended with
`KONTROLA DANYCH: błędów 0` (data check: 0 errors). Other options: `--tylko lines-plan,deck-plan` (only these sheets),
`--bez-png`, `--bez-pdf`, `--bez-danych` (no PNG, no PDF, no data files).

## English names: the renaming tool and the files in `model/`

`blender/nazwy_na_angielskie.py` ("names to English") is plain Python 3, without Blender and without extra packages.
It reads a GLB file and `data/names-map.csv` and writes a copy in which the names of nodes, meshes, materials and
images, the keys of the extras and the known texts in the extras are English. It changes only the JSON part of the
file; the binary part (geometry and pictures) is copied byte for byte.

The translation comes first from `data/names-map.csv` (the category depends on where the name is: a node is looked up
as `glb_node`, `collision_node` or `object`; an extras key as `glb_extras_key` or `json_key`; a motion axis text as
`text`), then from the rules in `nazwy_publiczne.py` (for example `lina_dyn_dziala_904_glb` becomes
`rope_dynamic_gun_tackle_904_glb`: group and number from the pattern `lina_dyn_<group>_<number>`), and last from a
short list in the tool itself (`DODATKI`) for names that are not in the public data: three shared meshes, the merged
materials `<material>__<group>`, the picture names and three helper texts. The tool is strict: if any name, key or
text has no English equivalent, it writes nothing, lists what is missing and ends with exit code 1. At the end it
checks its own result: no Polish letters, no Polish words from the map, no two different nodes with the same English
name.

The four files in `model/` were made like this from our build:

```
python blender/nazwy_na_angielskie.py build/bryg.glb model/snow.glb
python blender/nazwy_na_angielskie.py build/bryg_lod1.glb model/snow_lod1.glb
python blender/nazwy_na_angielskie.py build/bryg_lod2.glb model/snow_lod2.glb
python blender/nazwy_na_angielskie.py build/bryg_kolizja.glb model/snow_collision.glb
```

To check a file only: `python blender/nazwy_na_angielskie.py --sprawdz model/snow.glb`.

| File | Nodes | Triangles | Contents |
|---|---|---|---|
| `model/snow.glb` | 330 | 230 419 | full model: moving parts as separate nodes with axes and ranges in the extras, two static meshes, 142 work station nodes |
| `model/snow_lod1.glb` | 1 | 119 626 | one mesh, about 50 % of the triangles, textures 1K |
| `model/snow_lod2.glb` | 1 | 11 019 | one mesh, about 5 %, no ratlines, lanyards or running rigging, textures 512 px |
| `model/snow_collision.glb` | 36 | 3 286 | collision solids, nodes `collision_*` |

(Triangles counted from the index buffers of the file; at the time of writing.)

If you change the generator and it makes parts with new names, run `rysunki.py` first, so that `data/names-map.csv`
gets the new names, and only then the renaming tool.

## Independent tests in `blender/niezalezne/`

`niezalezne` means "independent". These six scripts do not use the generator: they open a finished `.blend` or GLB
file and test it in their own way, as a second opinion on the checks in `kontrola.json`.

| Script | Meaning | What it tests | Result |
|---|---|---|---|
| `konce_lin.py` | rope ends | every end of every rope tube touches a part, lies inside a solid or crosses a part near its end | JSON file |
| `bloki_wiszace.py` | hanging blocks | groups of block parts that touch no solid, no standing rope and no tarred pendant ending on them | JSON file |
| `przenikanie.py` | interpenetration | pairs of connected parts whose triangles cross, with the depth | JSON file |
| `skrecone.py` | twisted | quads whose two triangles face opposite ways (an "hourglass" tube) | printed table |
| `igly.py` | needles | triangles longer than 40 × their height, on flat and on smooth surfaces | printed totals |
| `zblizenia2.py` | close-ups (2) | renders close-ups from a GLB file for a list of camera positions | PNG files |

Run them like this (each opens the file given before `--python`):

```
blender -b --factory-startup --disable-autoexec build/bryg.blend --python blender/niezalezne/konce_lin.py -- build/test_konce_lin.json
blender -b --factory-startup --disable-autoexec build/bryg.blend --python blender/niezalezne/bloki_wiszace.py -- build/test_bloki.json
blender -b --factory-startup --disable-autoexec build/bryg.blend --python blender/niezalezne/przenikanie.py -- build/test_przenikanie.json
blender -b --factory-startup --disable-autoexec build/bryg.blend --python blender/niezalezne/skrecone.py
blender -b --factory-startup --disable-autoexec build/bryg.blend --python blender/niezalezne/igly.py
blender -b --factory-startup --python blender/niezalezne/zblizenia2.py -- model/snow.glb build/zblizenia build/kadry.json
```

`--disable-autoexec` stops scripts stored inside a `.blend` file from running; use it for any file you did not make.
The optional last number of the first three is the tolerance in metres. `build/kadry.json` (*kadry* = frames) for
`zblizenia2.py` is a list of views: `{"name": [[target x, y, z], [camera x, y, z], lens_mm], ...}` in the
coordinates of the `.blend` file.
Our run on `build/bryg.blend` gave: `konce_lin.py` 0 of 1 523 tube ends in the air (tolerance 3 cm);
`bloki_wiszace.py` 96 block groups, all held (71 touch a solid, 23 hang on a standing rope or pendant, 2 are hidden
in a solid), none suspect; `przenikanie.py` 505 object pairs with crossing triangles. That last test has no list of
intended joints, so most pairs are intended (the deepest are furled sails lying in their yards); read it together with
`przenikanie` in `kontrola.json`. `skrecone.py` found 71 of 93 522 quads whose triangles face opposite ways, mostly
small faces at sharp bends: a stricter measure than the crossed-edge test of `kontrola.json`, which passes.
`igly.py` counted 4 772 needle triangles, 831 of them on smoothly shaded surfaces. `zblizenia2.py` wrote the two
views of `build/kadry.json` to `build/zblizenia/`.

## Limitations

- Tested with Blender 5.2 on Windows only. The scripts use `os.path` and should run on Linux and macOS, but we did not
  try. Other Blender versions may change the glTF exporter or the Python API.
- One ship definition (`BRYG`, the snow of about 1710). Other ships need new numbers (chapter 12) and, for a different
  stern, head or rig, new code.
- The full build takes about 8 minutes; `build/` grows to about 0.5 GB with both builds, renders and drawings.
- A build without the CC0 textures gives different pictures and a different file size than `model/`; the geometry is
  the same.
- The renaming tool knows the names this generator makes. New parts need new rows in `data/names-map.csv` (made by
  `rysunki.py`) or in the tool's `DODATKI` list.
- The code is in Polish. Identifiers are written without Polish letters (`kadlub` for *kadłub*), comments with them.

## Reading the code: Polish words

Identifiers drop the Polish letters: ą → a, ć → c, ę → e, ł → l, ń → n, ó → o, ś → s, ź and ż → z. `L` and `P` after
a name are the sides: *lewa* (port) and *prawa* (starboard). The ship's axes are `s` (along, + forward), `x` (across,
+ to port), `z` (up from the design waterline).

| In the code | Polish | English |
|---|---|---|
| `kadlub` | kadłub | hull |
| `poklad`, `poklad_rufowy`, `polpoklad` | pokład, pokład rufowy, półpokład | deck, quarterdeck |
| `wregi`, `wreg` | wręgi, wręg | frames, frame |
| `rzedne` | rzędne | offsets |
| `poszycie`, `deski` | poszycie, deski | planking, planks |
| `stepka`, `wrab` | stępka, wrąb | keel, rabbet |
| `dziobnica`, `tylnica` | dziobnica, tylnica | stem, sternpost |
| `dziob`, `rufa`, `pawez` | dziób, rufa, pawęż | bow, stern, transom |
| `burta`, `nadburcie`, `reling` | burta, nadburcie, reling | side, bulwark, rail |
| `bergholt` | berghołt | wale |
| `furta`, `pokrywa` | furta, pokrywa | gun port, lid |
| `ster`, `rumpel`, `kolo_sterowe` | ster, rumpel, koło sterowe | rudder, tiller, steering wheel |
| `galion`, `kotbelka`, `kluza` | galion, kotbelka, kluza | head, cathead, hawse hole |
| `drzewca`, `maszt` | drzewca, maszt | spars, mast |
| `fok`, `grot` | fok, grot | fore, main (mast or sail) |
| `stenga`, `bramstenga` | stenga, bramstenga | topmast, topgallant mast |
| `reja`, `mars`, `ezelhoft` | reja, mars, ezelhoft | yard, top, cap |
| `bukszpryt`, `bomstenga`, `blinda` | bukszpryt, bomstenga, blinda | bowsprit, jib-boom, spritsail |
| `gafel`, `bom` | gafel, bom | gaff, boom |
| `olinowanie`, `takielunek` | olinowanie, takielunek | rigging |
| `lina`, `liny` | lina, liny | rope, ropes |
| `wanta`, `wanty`, `podwantka` | wanta, wanty, podwantka | shroud, shrouds, futtock shroud |
| `sztag`, `padun` | sztag, padun | stay, backstay |
| `jufers`, `talrep`, `wyblinka` | jufers, talrep, wyblinka | deadeye, lanyard, ratline |
| `lawa_wantowa` | ława wantowa | channel |
| `blok`, `bloki`, `strop` | blok, bloki, strop | block, blocks, strop |
| `ruchome` | (liny) ruchome | running (rigging) |
| `topenanta`, `bras`, `szot`, `fal`, `gejtawa` | topenanta, bras, szot, fał, gejtawa | lift, brace, sheet, halliard, clewline |
| `perta` | perta | footrope |
| `zagiel`, `zagle` | żagiel, żagle | sail, sails |
| `wyposazenie` | wyposażenie | fittings, equipment |
| `dzialo`, `dzialko`, `laweta`, `lufa` | działo, działko, laweta, lufa | gun, swivel gun, carriage, barrel |
| `kabestan`, `pompa`, `luk` | kabestan, pompa, luk | capstan, pump, hatch |
| `kotwica`, `lodz`, `dzwon` | kotwica, łódź, dzwon | anchor, boat, bell |
| `nagielbank`, `kolkownica`, `kolek` | nagielbank, kołkownica, kołek | fife rail, pin rail, pin |
| `stanowisko`, `stan_*` | stanowisko | work station |
| `czynnosc`, `przeszkoda` | czynność, przeszkoda | activity, obstacle |
| `chodzenie`, `postac` | chodzenie, postać | walking, figure |
| `kolizja`, `przenikanie` | kolizja, przenikanie | collision, interpenetration |
| `os_ruchu`, `zakres` | oś ruchu, zakres | motion axis, range |
| `kontrola`, `wynik`, `tak`, `nie` | kontrola, wynik, tak, nie | check, result, yes, no |
| `tekstury`, `kolor`, `normalne`, `szorstkosc` | tekstury, kolor, normalne, szorstkość | textures, colour, normals, roughness |
| `farba`, `drewno`, `zelazo`, `plotno`, `szklo` | farba, drewno, żelazo, płótno, szkło | paint, wood, iron, canvas, glass |
| `srednica`, `dlugosc`, `szerokosc`, `wysokosc` | średnica, długość, szerokość, wysokość | diameter, length, breadth, height |
| `rysunki`, `arkusz`, `dane`, `nazwy` | rysunki, arkusz, dane, nazwy | drawings, sheet, data, names |
| `zbuduj`, `buduj`, `zapisz`, `scal` | zbuduj, buduj, zapisz, scal | build, build, save, merge |
| `statek`, `bryg` | statek, bryg | ship, brig |

For object and node names, rope groups, materials, parameters and keys, `data/names-map.csv` gives the exact English
name used in the data and in `model/` (columns `category`, `polish`, `english`).

## Check yourself

- [ ] The build ends with the line `KONIEC` (end) and no error.
- [ ] `build/kontrola.json`: 0 criteria with `nie`; `konce_lin.wiszace` = 0; `bloki.bez_zaczepu` = 0;
  `przenikanie.zgloszone_ponad_prog` = 0.
- [ ] With the CC0 textures, `build/bryg.glb` has 330 nodes and about 230 000 triangles.
- [ ] `rysunki.py` with `--publiczne build/...` ends with `KONTROLA DANYCH: błędów 0`, and `data/` and `plans/` of
  the repository are unchanged.
- [ ] The renaming tool ends with `błędów 0` (0 errors) for all four files, and `--sprawdz` finds nothing.
- [ ] The files in `model/` load in Blender (File > Import > glTF 2.0) with English names.

## Typical mistakes

1. Running the commands from inside `blender/` instead of the repository root: the output then goes to a different
   `build/` and `--tekstury-cc0` with a relative path is not found.
2. `python` on the command line is a Python without numpy or Pillow: the texture step stops with an import error.
3. Poly Haven files at another resolution or with other names (for example 4K, or PNG): the CC0 step does not find
   them. Use the names in `blender/tekstury_cc0_spis.json`.
4. Editing the texture working copies in `build/` and wondering why nothing changes: the build reuses them only while
   they exist; delete the folder after changing the sources.
5. Running `rysunki.py` without `--publiczne` while trying things: it overwrites `data/` and `plans/`.
6. Running the renaming tool on a file from a changed generator without updating the map first: the tool stops and
   lists the new names. That is intended.
7. Opening a `.blend` file from elsewhere without `--disable-autoexec`.

## Sources

1. Khronos Group, *glTF 2.0 Specification* https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html (binary GLB
   container, nodes, meshes, materials, images, extras).
2. Poly Haven https://polyhaven.com/ (textures; each asset page lists its authors and its CC0 licence); the asset
   list used here is `blender/tekstury_cc0_spis.json`.
3. Creative Commons, *CC0 1.0 Universal* https://creativecommons.org/publicdomain/zero/1.0/.
4. Blender Manual, *Command Line Arguments* https://docs.blender.org/manual/en/latest/advanced/command_line/arguments.html
   (`-b`, `--python`, `--factory-startup`, `--disable-autoexec`, arguments after `--`).
5. Blender Manual, glTF 2.0 add-on https://docs.blender.org/manual/en/latest/addons/scene_gltf2.html (custom
   properties exported as extras).

## Terms used in this chapter

| English | Polish | Explanation |
|---|---|---|
| background mode | tryb bez okna (tło) | Blender running a script without a window (`-b`). |
| factory settings | ustawienia fabryczne | Blender without user preferences and add-ons. |
| generator | generator | Scripts that build the model from numbers. |
| stage | etap | One part of the build, one module. |
| procedural texture | tekstura proceduralna | Picture computed by a script. |
| working copy | kopia robocza | File made by the build from a source file, which stays unchanged. |
| node, mesh, material, image | węzeł, siatka, materiał, obraz | Named parts of a glTF file. |
| extras | extras (dane dodatkowe glTF) | Free field for application data in glTF. |
| level of detail (LOD) | poziom szczegółów | Simpler model for distance. |
| collision solid | bryła kolizji | Simple solid for collision tests. |
| check report | raport kontroli | `kontrola.json`. |
| exit code | kod wyjścia | Number a program returns; 0 means success. |
