# Data files of the reference model

All files in `data/` are written by the generator scripts from the same parameters as the 3D model. Do not edit them by
hand: change the parameters and run the export again (see the main README).

## Coordinate system (all files)

Every point is written as **[x, s, z] in metres**:

| Axis | Direction | Zero |
|---|---|---|
| x | athwartships, **positive to port** (larboard) | centreline |
| s | fore and aft, **positive forward** | middle of the 28.0 m deck length between rabbets (stem rabbet at the deck s = +14.0, sternpost s = −14.0) |
| z | up | design waterline |

The triple (s, x, z) is right-handed. Conversions:

- glTF / game file (+Y up): (X, Y, Z) = (x, z, s); the bow points to +Z.
- Blender (Z up): (X, Y, Z) = (x, −s, z); the bow points to −Y.
- Research notes measure stations from the dead flat: s = z_df + 1.96.

Plan polygons are [x, s]. JSON files carry the same description in `coordinate_system`; CSV files start with comment
lines beginning with `#` (read them with `comment="#"` in pandas, or skip lines starting with `#`).

## Sources and confidence

Every value in `parameters.json` has `confidence` (one of `period`, `secondary`, `our inference`, `reference model`)
and `source` (the chapter of the guide that explains it, e.g. `docs/en/02-hull-lines-and-offsets.md`).

## Files

### parameters.json
All generator parameters in groups: `hull`, `decks`, `stern_and_head`, `spars`, `standing_rigging`,
`running_rigging`, `sails`, `fittings`, `steering`, `materials`, `variants`. Each group: `description`, `sources`,
`values`; each value: `value`, `unit` (when the key does not end in a unit), `confidence`, `source`, `note`.
Key suffixes give the unit: `_m` metres, `_deg` degrees, `_m2` square metres; `_s_z_m` is a list of [s, z] points.

### offsets.csv, offsets.json
Hull lines. `offsets.csv` is a long table with columns `table, station_s_m, station_z_df_m, line, line_value_m,
half_breadth_m, z_m`. Tables:

| table | content |
|---|---|
| research_moulded | research offsets, moulded (no planking): keel underside, rabbet, bearding (z), waterlines −2.5 … +0.5 (line_value_m = z of the waterline, half_breadth_m), deck at side, greatest breadth, waist rail |
| generator_outside_planking | the table the generator uses: half-breadths outside the planking on lines parallel to the keel rabbet, line_value_m = height above the rabbet; z_m = rabbet z + height |
| buttock_generator | height of the bottom where the generator surface reaches the half-breadth line_value_m (1, 2, 3 m) |
| stem_rabbet, sternpost_rabbet, transom_centreline | profile points (s, z) |
| transom_half_breadth | half-breadth of the after end at height z |
| deck_at_side, rail_top | deck line at the side and the top of the rail cap along s |

`offsets.json` holds the same numbers in structured form (`research_table`, `generator_table`, `buttocks`, `stem`,
`sternpost`, `transom`, `deck_and_rail`).

### spars.csv
One row per spar: `spar, kind, length_m, d_max_m, d_mid_m, d_end_m` (largest, middle, end diameter), `start_*` and
`end_*` (heel and head of a mast, port and starboard yardarm of a yard, jaws and peak of the gaff), `angle_deg` with
`angle_ref` (rake of a mast from vertical, steeve of the bowsprit, angle of the gaff), heights of deck, top platform,
start of the masthead, crosstrees, cap and truck, and for yards the lowered and hoisted heights.

### rigging-lines.json
`belaying_points` (pins, fife rails, pin rails and kevels: `id`, `kind`, `position`, `ropes`), `ropes` (one entry per
named rope with total length, number of segments, belaying point) and `lines` – 1317 segments of 836 ropes.
Fields of a segment:

| field | meaning |
|---|---|
| id | index (order of the generator) |
| rope, segment, segments | rope name and the segment's number within it |
| group | rope family (e.g. `main_shrouds`, `running`, `ratlines`) |
| kind | `standing`, `running` or `coil` |
| material | `tarred` or `untarred` |
| diameter_m, length_m | true diameter; length of the polyline |
| from, to, via | end points and intermediate points [x, s, z] (sag curve or lead points) |
| parent | spar the rope is fixed to (moves with it), or null |
| from_object, to_object, dynamic | moving part under an end; `dynamic` = an end lies on a moving part |
| from_local, to_local | that end in the local coordinates of the moving part (Blender axes of the part) |
| variant | steering variant the line belongs to, or null |
| belayed_to | id of the belaying point of the rope's last segment |
| one_sided | the rope exists on one side only (no mirror) |

### rigging-summary.csv
Totals per group: number of ropes and segments, total length, smallest and largest diameter.

### deck-layout.json
Walking data: `surfaces` (deck polygons [x, s], height formula `z = centreline_z(s) − camber·(x / half_breadth)²`
and a z grid; tops with their lubber's holes; channels), `obstacles` (rectangles or circles in plan with height,
`walkable` and `step_height_m`), `stairs`, `passages`, `climbs` (polylines up the shrouds), `side_edge`
(rail height along s), `walker` (figure radius and height used in the walking test).

### stations.csv
142 work stations: name, activity, level, feet position, facing vector and angle (0° = forward, +90° = to
port), the object worked, its axis and range, hand height, ropes handled.

### moving-parts.csv
Every moving part: kind (rotation or translation), axis description, pivot, local Z axis in ship coordinates, range
and unit, rest state, variant, what limits the range; for yards the range when lowered and when hoisted
(`range_hoisted_*`) and the hoist `working_height_dz_m`; the wheel's turns for 35° of rudder and the formula.

### names-map.csv
2140 rows: Polish names of objects, glTF nodes, keys and values used by the generator scripts → the English names
used here. Categories: object, glb_node, rope, rope_kind, rope_group, parameter, parameter_subkey, json_key,
glb_extras_key, material, paint_region, activity, station, obstacle, surface, level, spar, sail, belaying_point, text,
value.

## Reading the data in Python

```python
import csv, json

def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(line for line in f if not line.startswith("#")))

P = json.load(open("data/parameters.json", encoding="utf-8"))
print(P["groups"]["spars"]["values"]["main_mast_length_m"])     # value, unit, confidence, source

spars = {r["spar"]: r for r in read_csv("data/spars.csv")}
print(spars["main_mast"]["length_m"], spars["main_mast"]["cap_z_m"])

R = json.load(open("data/rigging-lines.json", encoding="utf-8"))
shrouds = [l for l in R["lines"] if l["group"] == "main_shrouds"]
print(len(shrouds), sum(l["length_m"] for l in shrouds))
```

## Drawing the ship without Blender

1. **Profile and body plan.** From `offsets.csv` take `generator_outside_planking` (or `research_moulded` for moulded
   lines). For each station plot (half_breadth_m, z_m): that is the frame. For each height plot (station_s_m,
   half_breadth_m) along the ship: that is a line parallel to the keel in the half-breadth plan. Close the ends with
   `stem_rabbet` and `transom_*`; draw `deck_at_side` and `rail_top` in the profile. Fair with a spline through the
   points, not with straight lines.
2. **Spars.** From `spars.csv` draw each spar as a tapered line from `start` to `end` (side view: s horizontal, z
   vertical), using `d_max_m`, `d_mid_m`, `d_end_m`. Mark the heights of tops, caps and crosstrees.
3. **Rigging.** From `rigging-lines.json` draw every segment from `from` through `via` to `to` (side view: s, z; front
   view: x, z). Line width ∝ `diameter_m`; tarred ropes dark, untarred light.
4. **Deck.** From `deck-layout.json` draw the deck polygons, obstacles and stairs in plan (x, s), and the stations from
   `stations.csv`.
5. Every drawing in `plans/` was made this way, by the scripts, from these numbers.
