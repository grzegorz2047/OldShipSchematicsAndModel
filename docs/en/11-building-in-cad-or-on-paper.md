# 11. Building the ship in CAD or on paper

## What this stage is for

You do not need Blender to build this ship. Every number the 3D model was made from is in `data/`, and every sheet
in `plans/` was drawn from those numbers. This chapter shows three other ways to rebuild the ship from them:

- **on paper**, with a pencil, a steel rule, dividers and a batten, the way the drawing office of a shipyard worked;
- **in any CAD program** (computer-aided design), free or commercial, with steps that do not depend on one program;
- **as a card or wooden model** built on a skeleton of frames.

At the end of this chapter you will have:

- a lines plan of your own, faired in three views, or a faired hull surface in CAD;
- deck, ports, keel, stem, sternpost, spars and (if you want) rigging placed from the data files;
- a short list of control dimensions to check your work against `data/parameters.json` and `data/spars.csv`.

Read [chapter 02](02-hull-lines-and-offsets.md) first: it explains the lines plan, the table of offsets and the arcs
of a frame. Confidence labels (period, secondary, our inference, reference model) are explained in
[chapter 01](01-ship-type-and-era.md). Most numbers in this chapter are **reference model** values taken from the
data files; the file is named each time. The model is still being refined, so take the current value from the file.

## Concepts

- **Scale**: the ratio between the drawing and the real ship. At 1:48, 1 mm on paper is 48 mm on the ship.
- **Station** (theoretical frame): a cross-section of the hull at a fixed place along the ship.
- **Waterline**: a horizontal cut through the hull. **Buttock**: a vertical cut parallel to the centreline.
- **Body plan, half-breadth plan, sheer plan**: the three views of a lines plan (front, top, side).
- **Batten**: a thin, even strip of wood or plastic bent through points to draw a smooth curve. **Ducks** are the
  weights that hold it.
- **Fair**: smooth, with no bumps, flats or sudden changes of curvature.
- **Spline**: the computer version of a batten, a smooth curve through or near a set of points.
- **Loft**: in CAD, a surface stretched through a row of section curves. (In a shipyard, "lofting" is drawing the
  lines full size on the floor of the mould loft [1] (secondary).)
- **Moulded**: measured to the outside of the frames, without planking. **Outside planking**: measured to the outer
  face of the planks.
- **Shell**: a surface given a thickness, such as planking.
- **Camber**: the upward curve of the deck towards the centreline. **Sheer**: the rise of the deck towards the ends.
- **Bulkhead** (in a model): a flat board cut to the shape of one station; a row of them on a keel board forms the
  skeleton of a model.

## What you need from this repository

| File | What it gives you | Used in |
|---|---|---|
| `data/offsets.csv` (or `data/offsets.json`) | the hull: stations, waterlines, heights; stem, sternpost and transom points; deck and rail lines | parts A, B, C |
| `data/parameters.json` | main dimensions, keel and stem sizes, planking thickness, camber, port positions and sizes, fittings | all parts, final check |
| `data/spars.csv` | every mast, yard, gaff and bowsprit spar: ends, three diameters, heights of tops, caps and trucks | A.8, B.10, C.5 |
| `data/rigging-lines.json` | every rope segment as a polyline with its diameter | A.8, B.11 |
| `data/deck-layout.json` | deck outlines, deck height formula, obstacles, stairs | B.7 |
| `plans/lines-plan.svg` | the faired lines plan at 1:48 on an A1 sheet | compare your drawing |
| `plans/frame-construction-arcs.svg` | the midship frame drawn with three arcs at 1:25 | A.6 |
| `plans/midship-section.svg`, `plans/hull-profile-structure.svg` | frame, keel, keelson and deck structure | B.9, C.2 |
| `plans/deck-plan.svg`, `plans/spar-plan.svg` | deck layout at 1:80, spars at 1:150 | A.8 |
| `data/SCHEMA.md` | the meaning of every column | always |

## Coordinates and units

All files use metres and the ship's own axes ([chapter 02](02-hull-lines-and-offsets.md), `data/SCHEMA.md`):

| Axis | Direction | Zero |
|---|---|---|
| s | along the ship, positive forward | middle of the 28.0 m deck length (stem rabbet at the deck s = +14.0) |
| x | across, positive to port | centreline |
| z | up | design waterline |

Most CAD programs use X, Y, Z with Z up. A simple choice is CAD X = s (forward), CAD Y = x (to port), CAD Z = z.
This keeps the triple right-handed, like the data (reference model, `data/SCHEMA.md`). Write the mapping on the first
sheet of your drawing so nobody mirrors the ship by mistake. The hull is symmetric: the files give the port half
(x ≥ 0); you mirror it.

## Part A. On paper

### A.1 Choose scale and sheet

The hull is about 29.2 m long from the stem head to the taffrail. With the bowsprit and jib-boom the whole ship is
about 37.5 m: from the jib-boom end at s = +22.36 (`data/spars.csv`) to the top of the transom at s = −15.15
(`transom_centreline` in `data/offsets.csv`) (our calculation).

| Scale | Hull length on paper | Whole ship with jib-boom | Sheet for the lines plan |
|---|---|---|---|
| 1:48 | 608 mm | 781 mm | A1 (841 × 594 mm), as `plans/lines-plan.svg` |
| 1:64 | 456 mm | 586 mm | A2 (594 × 420 mm) |
| 1:96 | 304 mm | 391 mm | A3 (420 × 297 mm) |

1:48 is a quarter of an inch to the foot. The period plans of *Ferret* (1711) and *Swift* (1721) named in chapter 01
are drawn at this scale [2] (period, plans). Choose it if you can. At 1:96 a 0.5 mm pencil line is already 48 mm
wide on the ship, too coarse for fairing (our inference).

### A.2 Draw the grid

1. Tape the sheet flat. Use a hard pencil (2H or harder) and a steel rule.
2. Draw the **baseline** (a horizontal line below the keel) and, above it, the **design waterline** z = 0.
3. Draw waterlines every 0.5 m: at 1:48 that is 10.42 mm apart. Label them −2.5 … +0.5 as in `data/offsets.csv`.
4. Draw the **station lines** at the s values of the file: −13.04, −11.04, −8.54, −5.54, −2.54, −0.04, +1.96, +4.46,
   +6.96, +9.46, +11.46, +12.96. They are closer together near the ends, where the shape changes fastest.
5. Draw the buttock lines at x = 1, 2 and 3 m in the half-breadth plan and in the body plan.
6. **Check the grid**: measure both diagonals of each large rectangle. If they differ by more than 0.5 mm, the grid is
   not square; redraw it. A skewed grid spoils every later step.

### A.3 Read the offsets

`data/offsets.csv` is one long table. Lines starting with `#` are comments. For a moulded drawing use the rows with
`table = research_moulded`; each row gives a station (`station_s_m`), what the row is (`line`), and a half-breadth
(`half_breadth_m`) or a height (`z_m`). For example, the midship station s = +1.96 contains:

| line | line_value_m | half_breadth_m | z_m | Meaning |
|---|---|---|---|---|
| keel_underside | | | −3.10 | bottom of the keel |
| rabbet | | | −2.85 | where the planking meets the keel |
| waterline | −2.0 | 2.93 | −2.0 | half-breadth on waterline −2.0 |
| waterline | 0.0 | 3.71 | 0.0 | half-breadth on the design waterline |
| greatest_breadth | | 3.73 | 0.35 | widest point of the frame |
| deck_at_side | | 3.70 | 0.90 | deck edge |
| rail_waist | | 3.51 | 1.95 | top of the bulwark in the waist |

If you want the drawing **outside the planking** (the shape you see), use `generator_outside_planking` instead: the
same 12 stations, but with half-breadths on 28 lines parallel to the keel rabbet (`line_value_m` is the height above
the rabbet). Do not mix the two tables in one drawing: they differ by the planking, 0.065 m (reference model,
`planking_thickness_m` in `data/parameters.json`).

A few lines of Python print one station in millimetres at your scale:

```python
import csv
SCALE = 48
rows = [r for r in csv.DictReader(l for l in open("data/offsets.csv", encoding="utf-8") if not l.startswith("#"))
        if r["table"] == "research_moulded" and r["station_s_m"] == "1.96"]
for r in rows:
    hb = r["half_breadth_m"] and "%.1f mm" % (float(r["half_breadth_m"]) * 1000 / SCALE)
    z = r["z_m"] and "%.1f mm" % (float(r["z_m"]) * 1000 / SCALE)
    print(r["line"], r["line_value_m"], hb, z)
```

### A.4 Plot the three views

1. **Sheer plan (side view).** Plot the keel underside and the rabbet at each station. Plot the stem from the
   `stem_rabbet` rows and the sternpost from `sternpost_rabbet` (heel at s = −13.10, raked 11.4° from vertical). Plot
   the deck line from `deck_at_side` and the rail from `rail_top`.
2. **Body plan (front view).** For each station mark the half-breadth on each waterline, the greatest breadth, the
   deck and the rail. By custom the after stations go on the left half and the forward stations on the right.
3. **Half-breadth plan (top view).** For each waterline transfer the half-breadths of all stations with dividers.
   Add the deck line (half-breadths in `deck_at_side`) and the transom (`transom_half_breadth`).

### A.5 Fair with a batten

1. Pin or weight the batten on the points of one waterline in the half-breadth plan.
2. Let the batten find its own curve. Where it will not pass through a point without a kink, leave the point.
3. **Move the point, not the batten.** Correct the same point in the body plan, so both views agree.
4. Draw the buttocks in the sheer plan from the half-breadth and body plans, and fair them the same way.
5. Accept up to 1 mm on paper at 1:48 (about 50 mm on the ship) between views (our inference, as in chapter 02).

### A.6 Draw a frame with arcs

Old frames were drawn as arcs of circles, not traced through points ([chapter 02](02-hull-lines-and-offsets.md)).
The sheet `plans/frame-construction-arcs.svg` draws the midship frame at 1:25 with three arcs and gives all the
numbers (reference model, our inference for the method's radii):

| Item | Value (m, moulded) |
|---|---|
| Start point on the keel R0 | (0.13, −2.85) |
| Deadrise | 12° up to the floor head F (2.20, −2.41) |
| Floor sweep | radius R_f = 1.42, tangent to the deadrise line at F |
| Breadth sweep | radius R_b = 3.92, vertical tangent at B (3.73, 0.35) |
| Touching point of the two sweeps | T (3.08, −1.80) |
| Top-timber sweep | radius R_u = 5.93, from B to the rail point N (3.51, 1.95) |

Draw it with a beam compass. Then check it: where your arcs cross the waterlines, they must match the half-breadths
of the midship station in `data/offsets.csv` within 0.05 m (reference model). Do the same for one forward and one
after station, using Table B of chapter 02 for their radii.

### A.7 Check that the three views agree

- Every point (a waterline crossing a station, a buttock crossing a waterline) appears at the same s, x and z in all
  three views.
- Waterlines in the top view: smooth, the bow fuller than the run.
- Buttocks in the side view: smooth, rising towards both ends.
- One diagonal through the bilge (chapter 02): no hollow or bump.
- After fairing, **write the corrected offsets**. The faired drawing is now the truth.

### A.8 Deck, ports, spars and rigging on paper

- **Ports**: centres at s = −3.79, −1.34, +1.11, +3.56, +6.01, +8.46, a closed port at −6.24; opening 0.60 wide, sill
  0.32 and lintel 0.82 above the deck (`gunport_*` in `data/parameters.json`, group `decks`).
- **Spars**: for each row of `data/spars.csv`, draw a line from (`start_s_m`, `start_z_m`) to (`end_s_m`,
  `end_z_m`) in the side view, and mark the widths `d_max_m`, `d_mid_m`, `d_end_m`. Yards seen from the side are
  short marks at their height; draw them full length in a front view (x and z).
- **Rigging**: for each segment in `data/rigging-lines.json` draw from `from` through `via` to `to`, side view (s, z)
  or front view (x, z). Draw stays and shrouds first; leave the 456 ratlines (`data/rigging-summary.csv`) for last.

## Part B. In any CAD program

The steps below work in any program that has 3D splines and a loft (also called "through sections" or "skin").
Names of commands differ; the idea does not.

### B.1 Set up

1. Set units to metres (or millimetres, and multiply every value by 1000).
2. Choose the axis mapping from "Coordinates and units" above and keep it.
3. Make one layer or group per item: grid, stations, profile, hull surface, deck, spars, rigging.

### B.2 Station curves from the offsets

1. For each station, make a list of points (x, z) from `research_moulded` (or `generator_outside_planking`), sorted
   from the keel upwards: rabbet, bearding, waterline points, greatest breadth, deck, rail.
2. Place each list in the plane of its station (CAD X = s).
3. Draw an **interpolating spline** (degree 3) through each list. Do not join the points with straight segments:
   12 stations joined by straight lines give visible facets (chapter 02, typical mistakes).

### B.3 Profile curves

1. Draw the stem rabbet through the `stem_rabbet` points in the centre plane.
2. Draw the sternpost rabbet as a straight line from the heel (s = −13.10, z = −3.119) to the point
   (s = −13.981, z = 1.25) (`sternpost_rabbet` in `data/offsets.csv`).
3. Draw the transom outline from `transom_half_breadth` (half-breadth at height z) in the plane of the transom, which
   is raked like the sternpost.
4. Draw the keel rabbet line z = −2.885 + 0.017857 · s (`keel_rabbet_z_at_s0_m`, `keel_drag_per_m`).

### B.4 Loft the hull

1. Loft a smooth (not ruled) surface through the station curves, from the transom to the stem.
2. Use the profile curves as guide rails if your program allows them; otherwise add one extra section at each end.
3. Mirror the surface across the centre plane.

### B.5 Check fairness

1. Cut the surface with planes at the waterlines and buttocks. Compare the cuts with the file values (and with Tables
   A and C of chapter 02).
2. Show a **curvature comb** (curvature plot) on each cut. The comb must change smoothly and keep its sign, except
   where you meant a hollow near the keel.
3. Show "zebra" stripes (reflection lines) if your program has them. The stripes must run in smooth bands.
4. If something is wrong, correct the **points** of a station and loft again. Do not push the surface by hand.

### B.6 Planking thickness

- The moulded surface is the outside of the frames. Planking adds 0.065 m on the bottom (reference model,
  `planking_thickness_m`); wales stand 0.02–0.06 m proud of it (`wales_from_to_projection_m`).
- Either offset the moulded surface outward by 0.065 m, or loft the `generator_outside_planking` table directly. The
  second way is what the reference model does; it tapers the planking to nothing at the deadwood (reference model).
- For a solid model, thicken the surface inward (shell). For drawings, keep it a surface.

### B.7 Deck with camber and sheer

The deck height at any point (reference model, `data/deck-layout.json`):

z = centreline_z(s) − 0.120 · (x / 3.80)²

`centreline_z(s)` is listed in the file every 0.5 m (for example 1.025 m at midships, our reading of the list); the
quarterdeck is 1.70 m higher, from s = −5.04 aft (`quarterdeck_break_s_m`, `quarterdeck_height_above_main_deck_m`).
Build the deck as a surface lofted through these arcs, then trim it with the inside of the bulwark (the `polygon_x_s`
of the deck in `data/deck-layout.json`).

### B.8 Ports

Cut each port as a box: 0.60 m along the ship, from sill 0.32 m to lintel 0.82 m above the deck at the side, through
the bulwark (`gunport_*`). The sides of the opening stay vertical; the sill follows the sheer.

### B.9 Keel, stem and sternpost

| Item | Size (reference model, `data/parameters.json`, group `hull`) |
|---|---|
| Keel | 0.26 sided (thick across), 0.31 below the rabbet (keel 0.25 + false keel 0.06) |
| Stem | 0.26 sided at the foot, 0.40 at the head; 0.35 moulded forward of the rabbet |
| Sternpost | 0.40 moulded at the heel, 0.28 at the head, aft of the rabbet |
| Frame spacing (room and space) | 0.52 |

Sweep a rectangle of these sizes along the rabbet lines. Chapter 03 explains the parts.

### B.10 Spars

For each row of `data/spars.csv`: draw the axis from start to end, place circles of diameter `d_max_m` at the
thickest point, `d_mid_m` at the middle and `d_end_m` at the end, and loft through them. Lower and topsail yards are
octagonal in the middle (period, [chapter 05](05-masts-and-spars.md)). Tops, caps and crosstrees go at the heights
`top_platform_z_m`, `cap_z_m`, `crosstrees_z_m`. Yards are listed lowered; `hoisted_z_m` gives the working height.

### B.11 Rigging

Each segment of `data/rigging-lines.json` is a polyline (`from`, `via`, `to`) with a `diameter_m`. Sweep a circle of
that diameter along it. There are 1317 segments of 836 ropes at the time of writing (`counts` in the file); begin with
the groups `stays`, `main_shrouds`, `fore_shrouds` and `backstays` (`data/rigging-summary.csv`). Leave `ratlines` and
`coils` for the end.

### Notes for some free tools

| Tool | Good for | Note |
|---|---|---|
| FreeCAD | full 3D: splines, loft, shell, booleans | free and open source, parametric [3] |
| FREE!ship | hull surfaces and hydrostatics | GPL v2, subdivision surfaces instead of NURBS, Windows [4] |
| LibreCAD | 2D lines plan and body plan | GPL v2, 2D only [5] |
| Inkscape | tracing and editing the SVG sheets in `plans/` | GPL, SVG is its own format [6] |

The scripts behind `plans/` write SVG in millimetres on the sheet, so a sheet opens at its true paper size in a vector
editor (reference model). Do not take dimensions from a PNG copy: the pixels are not to scale.

## Part C. A card or wooden model on a skeleton

Modellers build hollow hulls in two common ways: **plank-on-bulkhead** (shaped boards set across a keel board, then
planked) and **plank-on-frame** (keel, stem and post first, then real frames, then planks, like the real ship)
[7] (secondary). Card models use the same skeleton, covered with paper strips or panels.

### C.1 Templates from the stations

1. Choose the scale (1:48 gives a hull of 608 mm; 1:96 gives 304 mm, good for card).
2. Draw each station of the body plan full size at your scale (part A, or print it from your CAD drawing).
3. **Subtract the skin.** Bulkheads stand inside the planking. Draw each template inside the moulded line by the
   thickness of your planking at scale (for example 1.5 mm strip at 1:48), not by the real 0.065 m.
4. Add more stations if the spacing is too wide for your skin: card needs a support every 30–50 mm on the model,
   wood strip every 50–80 mm (our inference). Interpolate new stations on your faired drawing, not from the table.
5. Cut a slot at the bottom of each template for the keel board and mark the deck line from `deck_at_side`.

### C.2 Keel board and assembly

1. Cut the keel board to the sheer plan: rabbet line below, deck line above, with slots at each station.
2. Glue the bulkheads square to the keel board. Check from above that they are at right angles to it and from the
   front that each is upright.
3. Lay a thin batten along the bulkheads (as in A.5). Where it does not touch a bulkhead, the template is wrong;
   sand or pack it until the batten lies fair on all of them.

### C.3 Skin, deck, spars

- **Wood**: plank from the keel upwards and from the sheer downwards; planks taper towards the bow.
- **Card**: glue strips or pre-cut panels; overlap small tabs on the bulkheads.
- **Deck**: a card or veneer sheet bent over beams with the camber (0.12 m at 3.8 m half-breadth, reference model).
- **Spars** from `data/spars.csv` at scale: the main mast is 17.80 m long and 0.494 m thick at the partners, so at
  1:48 it is 371 mm long and 10.3 mm thick (our calculation).
- **Ropes**: at 1:48 a 49 mm main shroud is 1.0 mm and a 10 mm ratline 0.2 mm (our calculation). Thread thinner than
  about 0.1 mm is hard to handle; use the thinnest you can and keep the ratlines lighter than the shrouds.

## Checking your result against the data

Measure these on your drawing, CAD model or physical model and compare with the files.

| Check | Value (reference model) | File and key |
|---|---|---|
| Deck length between rabbets | 28.0 m (stem rabbet at the deck s = +14.0, sternpost s = −14.0) | `data/SCHEMA.md` |
| Breadth moulded / over planking | 7.46 / 7.60 m | chapter 01; `offsets.csv` (largest moulded half-breadth 3.73) |
| Keel rabbet at s = 0 | z = −2.885 | `parameters.json`, `keel_rabbet_z_at_s0_m` |
| Keel underside at midships | z = −3.10 | `offsets.csv`, `keel_underside` at s = +1.96 |
| Deck at side, midships | z = 0.90 | `offsets.csv`, `deck_at_side` |
| Deck camber | 0.12 m at 3.80 m half-breadth | `parameters.json`, `deck_camber_m`, `camber_reference_half_breadth_m` |
| Quarterdeck | 1.70 m above the main deck, from s = −5.04 aft | `parameters.json`, group `decks` |
| Port sills above the water | about 1.22–1.50 m | chapter 02 (measured in the model) |
| Fore mast / main mast at the deck | s = +10.08 / −1.40 | `spars.csv`, `deck_s_m` |
| Main top platform, main cap, main truck | z = 13.22 / 15.39 / 28.84 | `spars.csv`, `main_mast`, `main_topgallant_mast` |
| Main yard | 15.82 m long, 0.308 m at the slings | `spars.csv`, `main_yard` |
| Bowsprit steeve | 30° | `spars.csv`, `bowsprit`, `angle_deg` |

Accept 1 mm on paper at 1:48 (about 50 mm on the ship); in CAD, 10 mm (our inference). If a value is far off, look
first for a mirrored axis, a wrong unit (millimetres read as metres), or the moulded and outside-planking tables mixed.

## Worked example: the midship station at 1:48

1. Take the midship rows of `research_moulded` (A.3).
2. Divide every metre value by 48 and multiply by 1000 to get millimetres on paper (our calculation):

| Point | Ship (m) | Paper at 1:48 (mm) |
|---|---|---|
| Rabbet | x 0.13, z −2.85 | x 2.7, z −59.4 |
| WL −2.0 | x 2.93 | x 61.0 |
| WL 0 | x 3.71 | x 77.3 |
| Greatest breadth | x 3.73, z 0.35 | x 77.7, z 7.3 |
| Deck at side | x 3.70, z 0.90 | x 77.1, z 18.8 |
| Rail | x 3.51, z 1.95 | x 73.1, z 40.6 |

3. Plot the points on the station line of the body plan, measured from the centreline (x) and the design waterline (z).
4. Draw the frame with the three arcs of A.6, scaled the same way (R_f = 29.6 mm, R_b = 81.7 mm, R_u = 123.5 mm).
5. The arcs must pass within 1 mm of the points. If they do, the frame and the table agree.

## Check yourself

- [ ] I wrote down which CAD axis is s, x and z, and the ship is not mirrored (port is +x).
- [ ] I used either the moulded table or the outside-planking table, not both.
- [ ] The grid is square (diagonals within 0.5 mm).
- [ ] Every point appears at the same place in all three views (1 mm at 1:48).
- [ ] Waterline and buttock cuts of my surface are smooth and match the file within 50 mm.
- [ ] Deck camber 0.12 m, quarterdeck 1.70 m higher from s = −5.04.
- [ ] Masts stand at s = +10.08 and −1.40; the main truck is about 28.8 m above the water.
- [ ] My control dimensions agree with the table above.

## Typical mistakes

1. Joining offset points with straight lines instead of a batten or spline.
2. Mixing moulded and outside-planking offsets, so the hull is 0.065 m too wide or too narrow in places.
3. Mirroring the ship: port drawn as starboard because CAD Y was taken to starboard.
4. Taking sizes from a PNG instead of the SVG or the data.
5. Fairing the surface by hand in CAD so that it no longer matches the numbers.
6. Model bulkheads cut to the moulded line, so the planking makes the hull too big.
7. Ropes at full scale thickness copied blindly: at small scale the thin ones vanish, the thick ones look like cables.

## Sources

1. Wikipedia, "Lofting" https://en.wikipedia.org/wiki/Lofting (CC BY-SA). Full-size drawing, battens, mould loft.
2. Royal Museums Greenwich, plan ZAZ4877 *Ferret* (1711) and plan ZAZ4853 *Swift* (1721), both 1:48, as listed in
   the sources of [chapter 01](01-ship-type-and-era.md) (view only, RMG licensing terms). We did not check the scale
   of other collections.
3. FreeCAD https://www.freecad.org/ (free and open source parametric 3D modeller).
4. FREE!ship, SourceForge https://sourceforge.net/projects/freeship/ (GPL v2; subdivision surfaces, hydrostatics).
5. LibreCAD https://librecad.org/ (free, open source 2D CAD, GPL v2).
6. Wikipedia, "Inkscape" https://en.wikipedia.org/wiki/Inkscape (free vector editor, GPL, SVG native).
7. Wikipedia, "Ship model" https://en.wikipedia.org/wiki/Ship_model (CC BY-SA). Plank-on-bulkhead, plank-on-frame.

## Terms used in this chapter

| English | Polish | Explanation |
|---|---|---|
| scale | skala | Ratio between drawing and ship. |
| station, theoretical frame | wręg teoretyczny | Cross-section at a fixed place along the ship. |
| waterline, buttock | wodnica, przekrój wzdłużny | Horizontal and vertical lengthwise cuts. |
| body plan, half-breadth plan, sheer plan | plan wręgów, plan półszerokości, plan boczny | The three views of a lines plan. |
| batten, ducks | listwa krzywikowa, obciążniki | Strip for fair curves and the weights holding it. |
| fair, fairing | gładki, wygładzanie | Smooth; making a curve smooth. |
| spline | krzywa sklejana (spline) | Smooth computer curve through points. |
| loft | wyciągnięcie po przekrojach (loft) | Surface through a row of section curves. |
| curvature comb | grzebień krzywizny | Plot of curvature along a curve. |
| moulded, outside planking | po wręgach, po poszyciu | Measured to the frames; to the outer planks. |
| shell (thickness) | powłoka (z grubością) | Surface given a thickness. |
| camber, sheer | wypukłość pokładu, wznios pokładu | Curve across and along the deck. |
| bulkhead (model) | wręg modelu (gródź modelu) | Board cut to one station for a model skeleton. |
| plank-on-bulkhead, plank-on-frame | poszycie na grodziach, poszycie na wręgach | Two ways to build a model hull. |
