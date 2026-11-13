# 14. Using the model in a game

## What this stage is for

The reference model is built to be **used**: walked on, steered, fought and animated. This chapter explains what is
in the model file and the data files, and how to connect them to a game engine. The steps do not depend on one
engine. Short notes show how the same thing is done with the glTF format and the three.js library for the web.

At the end of this chapter you will know:

- the coordinate system, the units and the node names;
- where the work stations are, which way the people face and what they work;
- which parts move, about which axis and how far;
- how to walk on the decks, switch between wheel and tiller, brace the yards and keep ropes attached to them;
- how to switch levels of detail, use the collision solids and keep the sea out of the towed boat;
- how to hook up the capstan, the pumps, the guns, the wheel and the bell;
- what is planned but not in the model yet, and how the model is prepared for it.

Confidence labels are explained in [chapter 01](01-ship-type-and-era.md). In this chapter nearly every number is a
**reference model** value from the files named; game rates and crew numbers are **our inference** unless stated.

## Concepts

- **Engine**: the program that draws the game and runs its rules (for example three.js, Godot, Unity, Unreal).
- **Node**: one element of a 3D scene with its own position, rotation and scale; nodes form a tree (the scene
  graph). A child moves with its parent.
- **Extras**: free data stored on a glTF node [1]. three.js copies them into `object.userData` [2].
- **Work station**: a marked place where a person stands to do one job, with a facing direction and a hand height.
- **Variant**: two versions of the same part in one file, of which one is shown (here: wheel or tiller).
- **Dynamic rope**: a rope segment with one end on a moving part; the game must redraw it when the part moves.
- **LOD** (level of detail): simpler copies of the ship for long distances.
- **Collision solid**: a simple, invisible shape used to test contact.
- **Stencil buffer**: a per-pixel mark the graphics card can write and test; used here to stop the sea being drawn
  inside the boat.

## Files

| File | What it is |
|---|---|
| `model/snow.glb` | full detail: static hull and rigging meshes, every moving part as its own node, 142 empty station nodes, both steering variants, the boat's water mask |
| `model/snow_lod1.glb`, `model/snow_lod2.glb` | one mesh each, moving parts in their rest position; about 50 % and 5 % of the triangles (at the time of writing) |
| `model/snow_collision.glb` | 36 simple solids (nodes `collision_*`), no materials |
| `data/stations.csv` | the 142 work stations |
| `data/moving-parts.csv` | the 59 moving parts (14 of them port lids) with pivot, axis and range |
| `data/deck-layout.json` | decks, obstacles, stairs, hatches, climbs, rail heights, walker size |
| `data/rigging-lines.json` | all rope segments; dynamic ones with local end points |
| `data/names-map.csv` | the English name of every node, key and value |

The model files of the release are in `model/`. Their node names and extras keys are the English names of
`data/names-map.csv`.

## Coordinates and units

| Item | Value (reference model, `data/SCHEMA.md`) |
|---|---|
| Units | metres; angles in the data files in degrees |
| Game / glTF axes | +Y up, bow towards +Z, +X towards port; this matches glTF, where +Z is forward and −X is right [1] |
| Origin | (0, 0, 0) on the design waterline, at the middle of the 28.0 m deck length |
| Data files | points written as [x, s, z]; in the game (X, Y, Z) = (x, z, s) |
| Facing angles | `facing_deg` in `data/stations.csv`: 0° = towards the bow, +90° = towards port, i.e. a turn about +Y |

**Local coordinates in the data files.** `from_local` and `to_local` in `data/rigging-lines.json` and the words
"local X, Y, Z" in the `axis` texts are given in the axes of the modelling program (Z up). The glTF export turns every
node's local axes the same way as the world axes. So for a point or axis given locally (Xb, Yb, Zb):

(X, Y, Z) in the glTF node = (Xb, Zb, −Yb)

| Text in the data | Axis in a glTF / three.js node |
|---|---|
| local Z | local +Y |
| local −X | local −X |
| local Y | local −Z |

The safest way is not to use local names at all: `data/moving-parts.csv` also gives each part's axis as a direction
in ship coordinates (`axis_dir_x`, `axis_dir_s`, `axis_dir_z`) for the parts that turn about their local Z. Convert
it to (x, z, s) and turn the node about that world axis through its pivot.

## Node names

The released files use only the English names listed in `data/names-map.csv` (column `english`, category `glb_node`;
keys of extras in categories `glb_extras_key` and `json_key`). The other column of that file gives the generator's
internal names; you need it only for files made directly by the generator, not for the files in `model/`. three.js cleans node names of some characters when it loads them [2]; the
English names use only lower-case letters, digits and underscores, so they are not changed.

| Group | Examples (reference model) |
|---|---|
| Static meshes | `hull_static`, `spars_static`, `rigging_static` |
| Yards and gaff | `fore_yard`, `main_topsail_yard`, `spritsail_yard`, `gaff`; children: `main_yard_parrel`, furled sails `main_course`, `fore_topsail` … |
| Guns | `gun_port_1` … `gun_port_5`, `gun_starboard_1` … `_5`; barrels `gun_port_1_barrel` …; swivels `swivel_gun_port_1` … |
| Port lids | `gunport_lid_port_1` … `_7`, `gunport_lid_starboard_1` … `_7` |
| Deck machinery | `capstan_barrel`, `pump_port_brake`, `pump_starboard_brake`, `bell` |
| Steering | `rudder`, `rudder_head`, `deck_tiller`, `tiller_below_deck`, `steering_wheel`, `wheel_standards`, groups `steering_wheel_variant`, `deck_tiller_variant` |
| Stations | `station_capstan_1` … `_8`, `station_gun_captain_1` …, `station_wheel_1` … (142 in all) |
| Dynamic ropes | `rope_dynamic_<group>_<id>_glb`, where `<id>` is the `id` of the segment in `data/rigging-lines.json` |
| Boat | `boat_water_mask` |

Rope ids change when the rigging is rebuilt. Find dynamic ropes by their extras (`from_object`, `to_object`,
`dynamic`), not by a fixed number.

## Work stations

`data/stations.csv` has one row per station (142 at the time of writing). The same stations are empty nodes in the
model file; on such a node, **local +Z is the facing direction** of the person, and the extras repeat `activity`,
`object`, `hand_height_m` and `variant`.

| Column | Meaning |
|---|---|
| `x_m`, `s_m`, `z_m` | where the feet stand |
| `facing_x`, `facing_s`, `facing_z`, `facing_deg` | where the person looks |
| `object`, `axis`, `range_min`, `range_max` | the part worked and its motion |
| `hand_height_m` | hand height above the feet (for example 1.12 m at the capstan bars, 1.05 m at the wheel) |
| `ropes` | ropes handled there (braces, lifts, sheets …) |
| `variant` | only present in one steering variant |

| Activity | Stations | Activity | Stations |
|---|---|---|---|
| gun crews (captain, loader, sponger, two side tackle, train tackle, powder boy) | 70 for 10 guns | port lids | 10 |
| capstan | 8 (one per bar) | yardarms, tops | 8, 2 |
| pumps | 4 | shrouds (climb) | 4 |
| rope handling (braces, halliards, clewlines, sheets, lifts, vangs) | 20 | hatches | 3 |
| wheel, deck tiller | 2, 2 | catheads, anchor | 2, 1 |
| compass, bell, boat, water cask, hand lead, log line | 1 each | | |

Stations aloft (tops and yardarms) have an empty `level`; they stand on the footropes and the top platforms.

## Moving parts

`data/moving-parts.csv` lists every moving part (59 at the time of writing): `kind` (rotation or translation), the
pivot (`pivot_x_m`, `pivot_s_m`, `pivot_z_m`), the axis, `range_min` and `range_max` with `unit`, the rest value, the
`variant`, and `limited_by` (what stops the part). The model file carries the same data in the node extras
(`motion_axis`, `range_deg` or `range_m`, `continuous_rotation`).

| Part | Motion | Range (reference model) |
|---|---|---|
| `capstan_barrel` | turns about the vertical axis | unlimited |
| `pump_port_brake`, `pump_starboard_brake` | swing about an athwartships axis | ±25° |
| `rudder` | turns about the pintle line | ±35°; both tillers are its children |
| `steering_wheel` | turns about the fore-and-aft drum axis | unlimited; 1.826 turns for 35° of rudder |
| `gun_port_1` … | recoil along the barrel, inboard | 0.4–1.5 m; less where a fitting stops it |
| `gun_port_1_barrel` … | elevation | −5° to +10° |
| `swivel_gun_*` | turn about the pin; tilt in the yoke | 360°; ±30° |
| `bell` | swings fore and aft | ±30° |
| yards and `gaff` | turn about the mast (bracing) | see "Yards" below |
| `gunport_lid_port_1` … `_7`, `gunport_lid_starboard_1` … `_7` | turn about the top hinge | 0–100°; 95° or 85° where the channels stop them, 75° where the hull mouldings do |

Note: for the guns `kind = translation` along local −X, and for the barrels a rotation about local Y; for these the
`axis_dir_*` columns give the part's local Z (up), not the motion axis. Use the table of local axes above.

## Walking on the decks

`data/deck-layout.json` holds everything a walking system needs (reference model):

1. **Surfaces**: `main_deck` and `quarterdeck` as polygons [x, s] (the inside of the bulwarks), with the height
   z = centreline_z(s) − 0.120 · (x / 3.80)² (the quarterdeck 1.70 m higher), and the same heights as a grid every
   0.5 m. The two tops are flat (z = 11.725 and 13.219) with a hole (the lubber's hole). The channels are listed too.
2. **Obstacles**: rectangles or circles in plan with a height, `walkable` and `step_height_m` (hatch coamings and the
   anchor cable can be stepped over; guns, capstan, masts cannot). Some carry a `variant`.
3. **Stairs and passages**: the quarterdeck ladder (9 steps of 0.191 m, 0.22 m going, 0.9 m wide); the main hatch
   ladder and the companion stairs lead below, where nothing is modelled yet.
4. **Climbs**: polylines up the shrouds to the tops, rungs every 0.36 m.
5. **Side edge**: the rail height along the ship; outside the deck polygon is overboard.
6. **Walker**: the test figure, radius 0.30 m, height 1.75 m. Use the same size for your crew, or run the reach
   test again (chapter 13).

To place a person: find the surface whose polygon contains (x, s), take its height, check obstacles at that point.

## Two steering variants

Both are in one file (reference model, `steering_drive` in `data/parameters.json`):

- `steering_wheel_variant` (visible by default): the wheel on its standards, a tiller below the quarterdeck, the
  tiller ropes and their blocks;
- `deck_tiller_variant`: the deck tiller on the rudder head with two tiller tackles.

Every node of a variant has `variant` in its extras; the two group nodes also have `visible_by_default`. Show the
nodes of one variant and hide the other. Do the same with stations, obstacles, collision solids and rope segments that
carry a `variant`. Both tillers are children of `rudder`, so turning the rudder turns whichever tiller is shown.

**Wheel ratio.** The tiller end moves across by L_r · sin α; the rope winds the same length on the drum, so the
wheel makes n = L_r · sin α / (π · D) turns (chapter 09). With L_r = 3.0 m and D = 0.30 m, 35° of rudder needs
1.826 turns (`wheel_turns_for_35deg`). A simple linear mapping (18.8° of wheel per degree of rudder) is close enough
for a game (our inference); the exact one is in the worked example below.

## Yards

| Yard | Lowered (sails furled) | Hoisted to the working position | Hoist (`working_height_dz_m`) |
|---|---|---|---|
| `fore_yard` | ±5° (stays) | ±35° | 0 |
| `fore_topsail_yard` | ±10° (ratlines) | ±35° | 4.784 m |
| `fore_topgallant_yard` | ±35° | ±35° | 2.902 m |
| `main_yard` | ±10° (stays) | ±35° | 0 |
| `main_topsail_yard` | ±5° (ratlines) | ±35° | 5.534 m |
| `main_topgallant_yard` | ±35° | ±35° | 3.362 m |
| `spritsail_yard` | ±35° | – | – |
| `gaff` | ±35° | – | – |

(Reference model, `data/moving-parts.csv`.) To set sail, first move the yard up its mast axis by
`working_height_dz_m`, then brace it within the hoisted range. Brace the yards of one mast together (chapter 07).

## Dynamic ropes

100 rope segments have one end on a moving part (`dynamic: true`, at the time of writing; `counts` in
`data/rigging-lines.json`): lifts, brace pendants, clewlines, sheets, slings and ties, the vangs, brails and halliards of the gaff, spritsail
braces, gun tackles, tiller ropes and tackles, the bell rope.
To keep them attached (chapter 07):

1. Take the moving end in local coordinates (`from_local` or `to_local`), convert it with
   (Xb, Yb, Zb) → (Xb, Zb, −Yb), and transform it with the moving part's current world matrix.
2. Keep the other end where it is.
3. Redraw the segment straight, or with its sag if it had `via` points (chapter 08).
4. The other segments of the same rope (from a block to a pin) do not move.

Segments that ride on a yard all the time (footropes, stirrups) are children of the yard and need no update.

## Levels of detail

Show the full model close by, LOD1 in the middle distance and LOD2 far away. Chapter 08 suggests switching at about
15–60 m for thin ropes and at about 250 m for everything but spars and sails (our inference). LOD1 and LOD2 are one
mesh each with every moving part at rest, so switch to them only where movement is no longer visible, or keep the
moving parts of the full model on top.

three.js has a ready LOD object: `addLevel(object, distance, hysteresis)`; the hysteresis (a fraction of the
distance) stops flicker at the boundary [3].

## Collision solids

The collision file holds 36 closed, simple solids (at the time of writing): a simplified hull of about 1500
triangles, 5 cm slabs for the main deck and quarterdeck, boxes along the bulwarks, 8-sided cylinders for the masts
and the bowsprit, and boxes or cylinders for guns, capstan, pumps, wheel, binnacle, hen coops and other large items.
Their node names start with `collision_`, followed by the name of the part they stand for. Load the file, keep it invisible, and give its solids to your physics
system. Solids of a steering variant carry the same `variant` value; switch them with the variant.

## The towed boat and its water mask

By default the ship lies at anchor with her boat towed astern on a painter (`boat_state = towed_astern` in
`data/parameters.json`). An open boat floating in a water plane shows the sea surface **inside** the boat. The node
`boat_water_mask` fixes this: a flat, one-sided polygon (normal up) along the outside of the boat's planking at the
boat's waterline. That waterline is 0.27 m above the bottom of the boat's keel (`boat_waterline_m` in the extras) and
lies at world height 0, the same as the sea.

How to use it (any engine): draw the mask after the opaque ship and before the water, writing only to the stencil
buffer (no colour, no depth); then draw the water only where the stencil is not set. In three.js the material flags
are `colorWrite`, `depthWrite`, `stencilWrite`, `stencilRef`, `stencilFunc`, `stencilZPass` [4], and the renderer
must be created with `stencil: true`, because the default is false [5].

## Hooking up interactions

| Machine | Nodes | Stations | Motion and numbers |
|---|---|---|---|
| Capstan | `capstan_barrel` | `station_capstan_1` … `_8` (hands 1.12 m) | turn the barrel about the vertical; 2.5 m of cable per turn (Ø 0.80 with whelps); 16 pawl clicks per turn; 4–6 turns a minute heaving, 1–2 breaking out (chapter 09, our inference for rates) |
| Pumps | `pump_port_brake`, `pump_starboard_brake` | `station_pump_1` … `_4` | brake swings ±25°; about 40 strokes a minute, about 100 l per minute per pump (chapter 09, secondary) |
| Guns | `gun_*`, `gun_*_barrel`, `gunport_lid_*` | 7 per gun: captain, loader, sponger, 2 side tackle, train tackle, powder boy | open the lid (to its `range_max`, 75–100°), drill as in chapter 09 (sponge, load, ram, run out, prime, point, fire); recoil along local −X up to the gun's range; elevation −5° to +10°; one shot per 2–3 minutes for 1710 (our inference) |
| Wheel | `steering_wheel`, `rudder` | `station_wheel_1`, `_2` (hands 1.05 m) | drive the rudder angle; derive the wheel angle; rudder ±35° |
| Deck tiller | `deck_tiller` (child of `rudder`) | `station_rudder_1`, `_2` | the helmsman walks with the tiller; ±35° |
| Bell | `bell` | `station_bell_1` | swing ±30°; strike every half hour, one more stroke each time, eight bells at the end of a four-hour watch (chapter 09, secondary) |

A minimal three.js sketch (our inference; check directions in your own viewer):

```js
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const renderer = new THREE.WebGLRenderer({ antialias: true, stencil: true });
const ship = (await new GLTFLoader().loadAsync('model/snow.glb')).scene;

// steering variant: show the nodes of one variant, hide the other
const active = 'steering_wheel_variant';
ship.traverse(o => { if (o.userData.variant) o.visible = o.userData.variant === active; });

// capstan: turns about its local +Y (the vertical); its rest rotation is the identity
const capstan = ship.getObjectByName('capstan_barrel');
function turnCapstan(deg) { capstan.rotateY(THREE.MathUtils.degToRad(deg)); }

// rudder and wheel: both turn about their local +Y (local Z in the data files)
const rudder = ship.getObjectByName('rudder');
const wheel = ship.getObjectByName('steering_wheel');
const r0 = rudder.quaternion.clone(), w0 = wheel.quaternion.clone(), up = new THREE.Vector3(0, 1, 0);
function setRudder(deg) {
  const a = THREE.MathUtils.degToRad(deg);
  rudder.quaternion.copy(r0).multiply(new THREE.Quaternion().setFromAxisAngle(up, a));
  const turns = 3.0 * Math.sin(a) / (Math.PI * 0.30);            // 1.826 at 35°
  wheel.quaternion.copy(w0).multiply(new THREE.Quaternion().setFromAxisAngle(up, turns * 2 * Math.PI));
}

// water mask of the towed boat: stencil only, then water where the stencil is not set
const mask = ship.getObjectByName('boat_water_mask');
mask.material = new THREE.MeshBasicMaterial({ colorWrite: false, depthWrite: false, stencilWrite: true,
  stencilRef: 1, stencilZPass: THREE.ReplaceStencilOp });
mask.renderOrder = 1;
// water.material.stencilWrite = true; water.material.stencilRef = 1;
// water.material.stencilFunc = THREE.NotEqualStencilFunc; water.renderOrder = 2;
```

## Worked example: one turn of the wheel

1. One full turn: n = 1. From n = L_r · sin α / (π · D): sin α = 1 × π × 0.30 / 3.0 = 0.314, so α = 18.3°.
2. The linear mapping gives 35° / 1.826 = 19.2° per turn: 0.9° more, which no player will notice.
3. Hard over (35°) needs 1.826 turns, so from hard over to hard over is 3.65 turns (our calculation, as chapter 09).
4. The helmsman stands at `station_wheel_1`: feet at x = 0.5, s = −12.10, z = 3.005, which is (0.5, 3.005, −12.10)
   in the game; `facing_deg` = 0, so he looks towards the bow (reference model, `data/stations.csv`).

## Planned, not in the model yet

These are planned; we give no dates. Below is only how the model is prepared for them.

| Topic | State now | How the model is prepared (reference model) |
|---|---|---|
| **Set sails** | all sails furled (`sails_set = false`); the ship is at anchor | every yard has a working height and a hoisted bracing range; set-sail sizes are estimated in `set_sail_estimates` (`data/parameters.json`) and chapter 08; furled sails are child nodes of their yards, so they can be swapped for set sails |
| **Interior below deck** | the hold and cabin are not modelled | the main hatch ladder and the companion stairs are in `data/deck-layout.json` with their lower ends; hull structure sizes are in chapter 03 |
| **Damage from shot**: holes and leaks | the hull and deck are merged static meshes | the hull surface and its thickness are known from `data/offsets.csv` and `planking_thickness_m`, so a hit point can be turned into a hole of known depth below or above the water |
| fire | none | materials are named per kind (wood, paint, rope, canvas), so a fire system can tell what burns |
| cut ropes | none | every rope segment is a separate, named entry in `data/rigging-lines.json` with its ends, diameter and belaying point, so one segment can be removed or made slack |
| broken spars | none | each mast piece (lower mast, topmast, topgallant mast) is its own row in `data/spars.csv` with its ends and heights of tops and caps; yards and the gaff are separate nodes; ropes record the spar they hang from (`parent`) |
| **Ropes in the wind** | ropes are static, sag from gravity only | dynamic segments already know their moving ends; sag is a formula of span and slack (chapter 08), so wind can be added as a sideways load |

## Check yourself

- [ ] I convert data points [x, s, z] to (x, z, s) and the bow points to +Z.
- [ ] I use English node names from `data/names-map.csv` and find dynamic ropes by their extras.
- [ ] I place people at the stations and turn them by `facing_deg` about +Y.
- [ ] Every moving part turns about its own axis within its range.
- [ ] Only one steering variant is visible, with its stations, obstacles and collision solids.
- [ ] Yards are hoisted before they are braced beyond the lowered range.
- [ ] Dynamic ropes follow their yards, guns and tillers.
- [ ] LOD switches only where movement is not visible.
- [ ] The sea does not show inside the towed boat.

## Typical mistakes

1. Reading [x, s, z] as (X, Y, Z): the ship stands on her side.
2. Using local axes from the data files as glTF local axes without the (X, Z, −Y) turn.
3. Showing both steering variants at once.
4. Bracing furled yards to 35° and pushing them through the stays.
5. Turning a yard and leaving its lifts and braces in the old place.
6. Rendering the collision file.
7. Forgetting `stencil: true` in three.js, so the water mask does nothing.

## Sources

1. Khronos Group, *glTF 2.0 Specification* https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html and schema
   https://raw.githubusercontent.com/KhronosGroup/glTF/main/specification/2.0/schema/extras.schema.json (axes,
   metres, extras as application-specific data).
2. three.js, `GLTFLoader` source https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/jsm/loaders/GLTFLoader.js
   (extras copied into `userData`; base colour textures set to sRGB; node names cleaned with
   `PropertyBinding.sanitizeNodeName`).
3. three.js, `LOD` source https://raw.githubusercontent.com/mrdoob/three.js/dev/src/objects/LOD.js
   (`addLevel(object, distance, hysteresis)`).
4. three.js, `Material` source https://raw.githubusercontent.com/mrdoob/three.js/dev/src/materials/Material.js
   (stencil and write flags).
5. three.js, `WebGLRenderer` source https://raw.githubusercontent.com/mrdoob/three.js/dev/src/renderers/WebGLRenderer.js
   (`stencil` defaults to false).

## Terms used in this chapter

| English | Polish | Explanation |
|---|---|---|
| engine | silnik gry | Program that draws the game and runs its rules. |
| node, scene graph | węzeł, drzewo sceny | Element of a 3D scene; their tree. |
| extras, userData | extras, userData | Free data on a node; three.js name for it. |
| work station | stanowisko czynności | Place where a person stands to do one job. |
| facing direction | kierunek patrzenia | Where the person looks. |
| variant | wariant | One of two versions of a part in one file. |
| dynamic rope | lina dynamiczna | Rope segment with an end on a moving part. |
| level of detail (LOD) | poziom szczegółów | Simpler copy for distance. |
| hysteresis | histereza | Margin that stops switching back and forth. |
| collision solid | bryła kolizji | Invisible simple shape for contact tests. |
| stencil buffer | bufor szablonu | Per-pixel mark used to mask drawing. |
| water mask | maska wody | Polygon that keeps the sea out of the boat. |
| painter | faleń | Rope by which a boat is towed or made fast. |
| bracing, hoisting | brasowanie, podnoszenie (rei) | Turning a yard; raising it on its mast. |
