# 13. 3D quality checklist

## What this stage is for

A ship model can look right in one picture and still be broken: a gun that goes through its port lid when it moves,
a texture stretched along one plank, a yard that turns black in the game because its faces point inwards. This
chapter is a checklist for a 3D model of a ship that is meant to be used, not only looked at: in a game, a simulation
or a viewer.

For every item you get:

- **what** to check;
- **why** it matters;
- **how to test** it, by hand or with a script;
- the **reference model** result or target, where we have one.

The last part lists mistakes we really made while building the reference model, with the symptom, the cause and the
test that now catches each of them.

Numbers marked "at the time of writing" (triangle counts, file sizes, numbers of ropes) change a little whenever the
model is rebuilt. Take the current values from the data files and from your own run of the tests. Confidence labels
are explained in [chapter 01](01-ship-type-and-era.md); in this chapter most values are **reference model** choices
or measurements.

## Concepts

- **Mesh**: the surface of a 3D object, made of **vertices** (points), **edges** and **faces** (usually triangles).
- **Closed solid** (manifold, "watertight"): a mesh in which every edge belongs to exactly two faces.
- **Normal**: the direction a face points to. On a closed solid all normals should point outwards.
- **Pivot** (origin): the point an object turns about. **Local axes**: the object's own X, Y, Z.
- **UV map**: a flat layout of the surface onto the texture picture. **u** and **v** are the two picture directions.
- **Texel density**: how many texture pixels fall on one metre of surface (px/m).
- **Anisotropy** (of a UV map): how much more the texture is stretched in one direction than in the other.
- **PBR** (physically based rendering): materials described by base colour (**albedo**), **roughness** and
  **metalness**, so they look right under any light.
- **sRGB and linear**: two ways to store a colour value. Pictures are stored in sRGB (more steps for dark tones);
  lighting is computed in linear values. glTF colour factors are linear [1].
- **glTF / GLB**: an open file format for 3D scenes; GLB is its single-file binary form [1].
- **Extras**: a free field in glTF for application-specific data [2]. The reference model writes axes and ranges of
  moving parts there.
- **LOD** (level of detail): simpler versions of a model shown from far away.
- **Collision proxy**: a few simple solids that stand in for the ship when the game tests what touches what.
- **BVH** (bounding volume hierarchy): a tree of boxes around triangles that makes "does this touch that?" fast.

## A. Units, scale and axes

| # | Check | Why | How to test | Reference model |
|---|---|---|---|---|
| A1 | Units are metres, scale 1 | glTF lengths are in metres [1]; a wrong unit makes the ship 1000 times too big or too small | load the file and measure the bounding box | breadth 7.60 m, main truck 28.84 m above the water (`data/spars.csv`) |
| A2 | Axes: +Y up, bow towards +Z, +X to port | glTF uses +Y up and +Z forward, with −X to the right [1], so +X is port | in a viewer, look along +Z: you see the bow; the port side is on your left | (X, Y, Z) = (x, z, s) (`data/SCHEMA.md`) |
| A3 | Root at a meaningful point | games place and float the ship by its root | the root (0, 0, 0) must be on the design waterline at mid deck length | z = 0 waterline, s = 0 mid deck (reference model) |
| A4 | Transforms applied on static parts | a hidden scale or rotation breaks physics, instancing and exports | every static object: scale 1, rotation 0 | 0 objects with scale ≠ 1 (at the time of writing) |

## B. Names

| # | Check | Why | How to test | Reference model |
|---|---|---|---|---|
| B1 | Lower case, digits and underscores only; no copy suffixes such as `.001` | code finds parts by name; copy suffixes change between exports | a regular expression over all node names, for example `^[a-z0-9_]+$` | 0 failures (at the time of writing) |
| B2 | One language, one name per part | two names for one part cause silent bugs | compare with `data/names-map.csv` (category `glb_node`, column `english`) | English names, for example `main_topsail_yard`, `gun_port_3`, `gunport_lid_starboard_2` |
| B3 | Side and number in the name | the game must tell the two sides apart | `_port_` / `_starboard_` plus a number; check positions in the data files | `swivel_gun_port_1` … `_4`; `gun_starboard_1` … `_5` |
| B4 | Material names consistent | duplicates hide in similar names | list materials; no near-duplicates | 33 materials in the main file (at the time of writing) |

Note the trap in the reference names: `gun_port_1` is the first **gun on the port side**, while
`gunport_lid_port_1` is the **lid of a gun port** on the port side.

## C. Pivots of moving parts

| # | Check | Why | How to test | Reference model |
|---|---|---|---|---|
| C1 | Each moving part is its own node | a part merged into the hull cannot move | list the nodes; compare with `data/moving-parts.csv` | 59 rows in `data/moving-parts.csv` (at the time of writing), among them the 14 port lids and the rudder head |
| C2 | Pivot on the real axis, local Z along it | then a turn is one angle about one axis | rotate the part through its range in a viewer; nothing may slide | yards: local Z along the mast; rudder: along the pintle line (`axis_dir_*` in `data/moving-parts.csv`) |
| C3 | Axis and range written in the file | the game needs limits without guessing | read the node's extras (`motion_axis`, `range_deg` or `range_m`) | all moving parts carry them (at the time of writing: 59 objects, 0 missing) |
| C4 | Children move with their parent | furled sails, parrels, footropes must follow the yard | turn the yard; the children follow | furled sails and parrels are children of their yards |

## D. Mesh hygiene

| # | Check | Why | How to test | Reference model |
|---|---|---|---|---|
| D1 | Solids are closed | volume tests, inside tests and many tools need closed shells | count edges that do not have exactly two faces | 0 open objects (at the time of writing); ropes have open ends hidden in fittings |
| D2 | No duplicate vertices (closer than 0.01 mm), no zero-area faces, no loose vertices or edges | they break normals, smoothing and booleans | merge by distance 1e-5 m; count before and after | 0 / 0 / 0 |
| D3 | Normals outwards | with back-face culling, inward faces disappear | signed volume of each closed part must be positive | 0 reversed |
| D4 | No coplanar faces closer than 1 mm | they flicker (z-fighting) | for faces of different objects, nearest face within 1 mm and normals parallel | 0 pairs |
| D5 | Few "needle" triangles on smoothly shaded surfaces | thin triangles shade badly where the surface is curved; on a flat facet they do no harm | ratio of longest edge to height > 40; count those with a neighbour across an edge at 2–30° | about 640 on smoothly shaded surfaces, below our limit of 1500; about 3400 more on flat facets, made when overlapping solids are merged (at the time of writing) |
| D6 | Mesh density fits the size | 24 sides on a ratline wastes triangles | count sides of swept parts | ropes 8, 6, 5 or 4 sides by diameter; masts 16; yards 12 (chapter 08) |
| D7 | The hull is fair | bumps show in reflections and on the lines plan, and they are copied by everyone who uses the table | cut the hull by waterlines, buttocks and stations; split each cut into lobes of one curvature sign; count lobes with a sagitta over 4 mm; a fair line has at most 3 | **not met below the waterline aft**: 34 surplus lobes, bumps of 1–5 cm in the run; topsides and fore body fair (measured, see [chapter 02](02-hull-lines-and-offsets.md)) |
| D8 | No twisted tubes | a tube whose first ring is the mirror image of the next collapses to a flat strip at mid-length (an "hourglass"), and it still passes the closed-solid test | in each quad, opposite edges must run side by side; count quads whose opposite edges cross | 0 in the ropes; 7 small faces in the stern carvings and the hull top still have crossed edges (at the time of writing). Until a late review the first segment of every swept tube was twisted: a third of all rope faces, and every straight shroud, lanyard and ratline over its whole length |

## E. Interpenetration (parts inside other parts)

**Why**: a barrel through a lid, a rope through a boat or a carriage inside the bulwark looks wrong at once, and
breaks physics and animation.

**How the reference model tests it** (our method, reference model):

1. Split every mesh (except ropes) into its **connected parts** ("islands"); a cannon is barrel, carriage, trucks.
2. For every pair of parts whose bounding boxes touch (also two parts of the same object), build a BVH of each and
   ask for overlapping triangles.
3. Where triangles overlap, measure the **depth**: for vertices of one part, test whether they lie inside the other
   (cast rays in three directions and count crossings: an odd count means inside), and take the largest distance from
   such a vertex to the other part's surface.
4. Report every pair deeper than **5 mm**, unless the pair is on a list of **intended joints**. Each intended joint
   has a written reason, for example: a mast passes through the deck partners and stands on the keelson (hidden);
   frame heads pass through the deck into the rail cap; a pintle sits in its gudgeon; a tiller is fitted into the
   rudder head.
5. Ropes have no inside, so for a rope only touching is reported, not depth.

| # | Check | Reference model (at the time of writing) |
|---|---|---|
| E1 | No unintended pair deeper than 5 mm | 0 pairs above the threshold; 35 rope contacts without penetration listed for review |
| E2 | Every intended joint has a reason | a list of 192 rules, each with its reason, in the check report |
| E3 | Moving parts tested across their range | swivels every 45°, guns over their recoil, lids over their opening, yards every 5° up to 35°, lowered and hoisted |
| E4 | Standing objects touch the deck | carriages, pumps, capstan base, binnacle, fife rails: no gap and no sinking |
| E5 | Every rope end is attached | each end of each rope lies within 1 cm of another part, inside it, or on another rope; closed coils and the free end of the bell rope are listed exceptions: 0 loose ends of 2 136 |
| E6 | Every block is held by something | each block touches a solid, hangs on a tarred pendant, is threaded on a straight taut tackle, or has a strop to a spar, a fitting or a standing rope; a running rope that bends at a block does not hold it: 105 blocks, 59 of them with a strop, 0 unattached |

Checks E5 and E6 were added late, after a review by eye. All earlier checks passed, yet 69 rope ends hung in the air:
an earlier fix for ropes that passed through the rail had simply shortened them. Once every rope end touched something,
41 blocks turned out to hang in the air themselves, with the rope ends resting on them. A test proves only what it
measures: "nothing passes through anything" does not mean "everything is attached", so each needs its own test.

The range test gives the limits written to `data/moving-parts.csv` (column `limited_by`): for example `gun_port_3`
recoils 0.75 m before it reaches the main hatch, and the lowered `main_topsail_yard` turns only ±5° before it touches
the ratlines (reference model).

## F. UV maps and textures

| # | Check | Why | How to test | Target or reference value |
|---|---|---|---|---|
| F1 | Texel density per material | too low looks blurred next to sharp parts; too high wastes memory | for every face: px/m = √(UV area × image pixels / 3D area); per material take the area-weighted median and the 5th percentile | about 1024 px/m on large surfaces; at least about 450 px/m on fittings (reference model target) |
| F2 | Even density within a material | a part with half the density shows larger grain | ratio of 95th to 5th percentile ≤ 1.44 (±20 %); ropes and glass checked separately | all 19 materials inside (at the time of writing) |
| F3 | Anisotropy below 1.25 | stretched texture: planks that look wider one way | per triangle, the two singular values s₁ ≥ s₂ of the map from the triangle's plane to pixels; anisotropy = s₁ / s₂; report the share of area above 1.25 | deck 0.2 %, black paint 4 %, oiled oak side 7.6 % of area above 1.25 |
| F4 | Grain along the timber | wood grain across a spar looks false at once | for each elongated wooden part (main axis ≥ 2.5 × the next), share of side-face area where the u direction is within 25° of the part's axis | 94–100 % for the wood materials |
| F5 | Rope texture scaled by diameter | a fixed tile makes thin ropes look straight-stranded | u = length / (2 × 3.3 × d), v around the rope (chapter 08) | as stated |
| F6 | Texture sizes are powers of two | mipmaps and compression expect them | check width and height | all |
| F7 | Colour maps in sRGB, data maps linear, normal maps with +Y up | glTF reads base colour as sRGB, normal maps as linear; the ORM map has roughness in G and metalness in B, occlusion in R [2] | inspect the texture slots | colour sRGB; normals OpenGL style; ORM = occlusion, roughness, metal |
| F8 | Occlusion on its own UV | a baked AO map needs unique, non-overlapping UVs | second UV set; occlusion texture uses texCoord 1 | hull with fittings (2048 px) and spars (1024 px) |

Density formula, step by step: a face of 1 m² that covers 1/4096 of a 4096 × 4096 picture has a UV area of
1/4096 and gets √(1/4096 × 4096 × 4096 / 1) = 64 px/m. (A density of 1024 px/m needs 1024² = 1 048 576 pixels on
every square metre.)

## G. Materials

| # | Check | Why | How to test | Target or reference value |
|---|---|---|---|---|
| G1 | Base colour inside a physical range | pure black or white does not occur in paint or wood and breaks lighting | non-metal base colours not below 30–50 sRGB and not above 240 sRGB (of 255) [3] | all inside (at the time of writing); the darkest is the smooth black paint of the rail, at about 50 sRGB after an earlier version at about 32 sRGB failed |
| G2 | Metalness 0 or 1 | real surfaces are metal or not; grey values only for dirt over metal [3] | the metallic factor is 0 or 1; the map is nearly black or white | iron and bronze 1, everything else 0 |
| G3 | Colour factor given as a linear value | glTF `baseColorFactor` is a **linear** multiplier [2] | convert sRGB c to linear: c / 12.92 if c ≤ 0.04045, else ((c + 0.055) / 1.055)^2.4 | `colour_multiplier_srgb` in `data/parameters.json` is stored in sRGB and converted on export |
| G4 | Double-sided only where needed | double-sided solids cost time and hide reversed normals | list materials with `doubleSided` (default false [2]) | canvas and glass only |
| G5 | No duplicate materials | each duplicate is one more draw call | list materials and their maps | copies only where a part needs its own AO map |

Example for G3: an sRGB multiplier of 0.33 is 0.089 in linear terms. Written as 0.33 straight into the linear
factor, the colour comes out as bright as an sRGB value of about 0.61: almost twice as light (our calculation).

## H. File budget and export

| # | Check | Why | How to test | Target or reference value |
|---|---|---|---|---|
| H1 | File size | download time and memory | size of `model/snow.glb` | ≤ 32 MB; 31.0 MB at the time of writing |
| H2 | Triangle budget | frame rate | count indexed triangles in the file | about 230 000 at the time of writing (our budget 280 000) |
| H3 | The file matches the source | an exporter can drop parts, merge images or change colours silently | load the exported file back; compare triangle counts (small losses from degenerate triangles are normal), the list of objects and the bounding box | no part missing |
| H4 | Images survive the export | three maps of one material must stay three pictures | for each material in the file: colour, ORM and normal images are different; mean colour of the exported colour map within 0.05 per channel of the source; size equal or halved 2, 4 or 8 times | all materials pass (at the time of writing) |
| H5 | Control renders from the exported file | the final proof is how it looks | render the same views (side from the water, deck at eye height, stern, wheel close up) from the exported file and from the source with the same light; compare mean brightness (≤ 10 % difference) and the share of each colour channel (≤ 0.04) | all four views pass (at the time of writing) |
| H6 | Tangents | normal maps need them | the reference file leaves them out on purpose: three.js derives them in the shader, and the file is smaller | none in the file |

## I. LOD and collisions

| # | Check | Why | How to test | Reference model (at the time of writing) |
|---|---|---|---|---|
| I1 | LOD levels exist and are much smaller | a far ship does not need 200 000 triangles | count triangles per file | LOD0 100 %; LOD1 about 50 % (one mesh, textures 1K); LOD2 about 5 % (no ratlines, lanyards, running rigging, small fittings; textures 512 px) |
| I2 | LOD switch does not jump | a sudden change of outline is visible | look at the switch distance; the silhouette (masts, yards, shrouds) must stay | chapter 08 gives distances for ropes |
| I3 | Collision solids are simple and cover the ship | physics and walking need cheap, closed shapes | count solids and triangles; overlay them on the model | 36 solids in `model/snow_collision.glb`, nodes `collision_*`: a simplified closed hull, deck slabs, bulwark boxes, 8-sided mast and bowsprit cylinders, boxes and cylinders for guns, capstan, pumps, wheel and other large fittings |
| I4 | Variant parts tagged | the wheel and the deck tiller must not both block the deck | each solid of a variant has the same `variant` value as the part | wheel and tiller solids tagged |

## J. Walking, stations and ropes

| # | Check | Why | How to test | Reference model |
|---|---|---|---|---|
| J1 | Every work station can be reached | a crew member who cannot reach the capstan is a bug | grid of 0.1 m on each deck; a figure of radius 0.3 m and height 1.75 m; flood fill from a start cell to each station | all stations reachable (`data/deck-layout.json`, `walker`) |
| J2 | Free space at each station | people need room to work | free circle of radius 0.45 m (0.30 m at the side) | stations moved by the test are listed in the report |
| J3 | Walkways | the crew must pass | narrowest gap between obstacles ≥ 0.8 m | none narrower (chapter 04) |
| J4 | Head clearance | beams and spars at head height | rays upwards from free cells between 1.45 and 2.0 m above the deck, ropes ignored | none at the time of writing |
| J5 | Guns run in | recoil can cut the deck in two | repeat J1 with every gun at full recoil | at the time of writing the bow stations (anchor, catheads, hand lead, fore shrouds) are cut off when all guns are run in |
| J6 | Rope symmetry | a missing starboard brace is easy to miss by eye | every rope with an end on the port side (x > 3 cm) must have a starboard twin with mirrored ends (within 3 cm), the same group, diameter and material; coils, anchors, boat, steering, gun and bell ropes and one-sided ropes excepted | 508 pairs, no rope without a twin and none with a different diameter (at the time of writing) |

## Worked example: the deck planking

1. The deck texture is an atlas of 4096 × 1024 pixels that covers 3.52 m × 0.88 m of deck (four rows of planks,
   reference model). Along the planks: 4096 / 3.52 = 1164 px/m. Across: 1024 / 0.88 = 1164 px/m. The density is the
   same both ways, so the anisotropy is 1.0 (our calculation).
2. The exported file gives a median of 1163 px/m and a 5th percentile of 1160 px/m: the whole deck is mapped evenly.
3. The anisotropy median is 1.001; 0.2 % of the deck area is above 1.25 (at the time of writing).
4. The deck passes F1, F2 and F3.

## Mistakes we actually made

| Mistake | Symptom | Cause | Test that now catches it |
|---|---|---|---|
| Gun barrels through the port lids | with the lid open and the gun run out, the muzzle passed through the lid | the lid's opening angle and the gun's barrel and elevation were set separately; nobody tested them together | range test (E3) of each lid and gun together; lids now open 95° to 100° over the barrel, and the range is cut to 85° or 75° where channels or mouldings stop the lid (`range_max` in `data/moving-parts.csv`) |
| Gun carriages inside the bulwark | the front of some carriages sank into the inner face of the bulwark, worst at the bow | the side leans inwards above the waterline and narrows towards the bow; the carriage was placed from the deck edge at one height | E1; the carriage front now keeps 3 cm from the bulwark over its full height and length |
| A stay through the boat | with the boat on its booms over the main hatch, a stay ran through it | the boat was placed from the deck layout without looking at the rigging | E1 with ropes: a rope that touches a closed solid is reported |
| 1K textures merged into one picture | in the exported file one material's colour, ORM and normal map pointed at the same picture; the material looked flat and wrongly coloured | half-size copies made for export got names that were not unique, so one picture replaced the others | H4: the three maps of each material must be different pictures |
| Colour multiplier in sRGB used as linear | parts looked much lighter in the game than in the source | the multiplier was written in sRGB, but the glTF factor is linear | G3, H4 (mean colour against the source), H5 (control renders) |
| Duplicate material slots after a Boolean | after the rudder hole was cut with a Boolean operation, the band of the gun ports took the deck material | several paint regions pointed to the same material in separate slots, and the Boolean renumbered the slots | one slot per material; H5 control renders and a look at the side after every Boolean |
| UV shear on the side | the planks of the hull texture slanted near the stern; anisotropy up to 2 | u was measured as the 3D arc length along each row of the hull mesh from midships; rows with more sheer were longer, so neighbouring rows drifted apart | F3; u is now measured in the horizontal plane (x, s) |
| Reversed normals of the yards | some yards (and parts of the boat) turned dark or vanished with back-face culling | an automatic "recalculate normals" flipped long, thin cylinders | D3: after the normals are made consistent, the signed volume of each closed part decides which way they point |
| AI texture generator on glued meshes | white and black stripes in the generated textures on small loose pieces and on inner faces | the parts were sent as many open, overlapping surfaces; the generator expects one closed shell | D1 before upload; open surfaces are first thickened, then all pieces are remeshed into one closed shell and reduced to a triangle budget |

## Check yourself

- [ ] The file loads in metres with the bow towards +Z and port towards +X.
- [ ] Every moving part has its pivot on its axis and its range in the extras.
- [ ] No unintended interpenetration above 5 mm, also across the range of every moving part.
- [ ] Texel density about 1024 px/m on large surfaces, at least about 450 px/m on fittings, spread ≤ ±20 %.
- [ ] Anisotropy above 1.25 on only a small share of each material; grain along the timber.
- [ ] Base colours within 30–240 sRGB; metalness 0 or 1; colour factors linear.
- [ ] The exported file matches the source in triangles, images, colours and control renders.
- [ ] LOD files and collision solids exist; variant parts are tagged.
- [ ] Every station is reachable, also with the guns run in.

## Typical mistakes

1. Trusting a pretty render instead of numbers.
2. Testing the model only in its rest pose.
3. Writing colours in sRGB into linear fields.
4. One texture size for everything, so small parts are sharp and the hull is blurred (or the opposite).
5. Letting the exporter merge parts that must move.
6. Exceptions to the tests without a written reason.
7. Checking the source file but not the exported file.

## Sources

1. Khronos Group, *glTF 2.0 Specification* https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html (coordinate
   system: +Y up, +Z forward, −X right; lengths in metres).
2. Khronos Group, glTF 2.0 JSON schema:
   https://raw.githubusercontent.com/KhronosGroup/glTF/main/specification/2.0/schema/material.pbrMetallicRoughness.schema.json
   (`baseColorFactor` and `metallicFactor` are linear multipliers; base colour texture in sRGB; metalness in B,
   roughness in G);
   https://raw.githubusercontent.com/KhronosGroup/glTF/main/specification/2.0/schema/material.schema.json (normal
   texture linear; occlusion in R; `doubleSided` false by default);
   https://raw.githubusercontent.com/KhronosGroup/glTF/main/specification/2.0/schema/extras.schema.json
   ("application-specific data").
3. Adobe, *The PBR Guide, part 2* https://www.adobe.com/learn/substance-3d-designer/web/the-pbr-guide-part-2 (dark
   values not below 30–50 sRGB, bright not above 240 sRGB; metallic map mostly black or white).
4. Blender Manual, glTF 2.0 add-on https://docs.blender.org/manual/en/latest/addons/scene_gltf2.html (custom
   properties exported as extras; +Y up option; occlusion through a "glTF Material Output" node group).

## Terms used in this chapter

| English | Polish | Explanation |
|---|---|---|
| mesh, vertex, edge, face | siatka, wierzchołek, krawędź, ściana | Parts of a 3D surface. |
| closed solid (manifold) | bryła zamknięta (rozmaitość) | Every edge has exactly two faces. |
| normal | normalna | Direction a face points to. |
| pivot, origin | punkt obrotu, początek obiektu | Point an object turns about. |
| UV map | mapa UV | Flat layout of the surface on the texture. |
| texel density | gęstość tekseli | Texture pixels per metre of surface. |
| anisotropy | anizotropia | Uneven stretching of a texture. |
| albedo, base colour | albedo, kolor bazowy | Colour of a surface without light and shade. |
| metalness, roughness | metaliczność, chropowatość | PBR material values. |
| sRGB, linear | sRGB, liniowy | Two ways to store colour values. |
| occlusion (AO) | okluzja otoczenia | Darkening in corners, baked into a map. |
| level of detail (LOD) | poziom szczegółów | Simpler model for distance. |
| collision proxy | bryła kolizji | Simple solid used for collision tests. |
| BVH | hierarchia brył otaczających (BVH) | Tree of boxes for fast intersection tests. |
| interpenetration | przenikanie brył | One part inside another. |
| z-fighting | migotanie (z-fighting) | Flicker of two faces in the same place. |
| back-face culling | pomijanie tylnych ścian | Not drawing faces that point away. |
| extras | extras (dane dodatkowe glTF) | Free field for application data in glTF. |
