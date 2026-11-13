# 12. Designing other ships from this one

## What this stage is for

The reference model is one ship: a snow of about 1710, 28.0 m on deck and 7.60 m wide. The rules that made it are
general. Change a few numbers and the same rules give you a sloop, a ketch, a schooner, a later brig or a small
three-masted ship. Change the date and some parts must change with it.

This chapter tells you:

- which parameters to change, and what follows from each of them;
- how the main rig variants differ from the reference model;
- what changes if you move the date by a few decades either way;
- what you must check after every change: guns, headroom, draught, sail balance, bracing, rope clashes;
- two complete worked examples: a sloop of about 21 m and a three-masted ship of about 32 m.

Both examples are **our inference**: we applied the rules of chapters 01, 02 and 05 to new main dimensions. They are
starting points for your own design, not reconstructions of real ships. Confidence labels (period, secondary, our
inference, reference model) are explained in [chapter 01](01-ship-type-and-era.md).

## Concepts

- **Parameter**: one number the design is built from (deck length, breadth, mast position, date).
- **Proportion rule**: a period or modern rule that gives one size from another, for example the main mast from deck
  length and breadth.
- **Variant**: the same hull with a different rig, steering, paint or boat position. In `data/parameters.json` the
  group `variants` holds the switches of the reference model.
- **Centre of effort (CE)**: the point where the total wind force on the sails acts. We take it as the centre of area
  of all sails, drawn flat in the side view.
- **Centre of lateral resistance (CLR)**: the point where the water resists the ship being pushed sideways. We take it
  as the centre of area of the underwater side profile.
- **Lead**: how far the CE lies forward of the CLR, usually given as a percentage of the waterline length.
- **Bracing range**: how far a yard can turn about its mast before it touches a shroud, stay or another yard.
- **Displacement**: the mass of water the hull pushes aside, equal to the mass of the ship.

## The chain of numbers

Every size in the reference model comes from a few numbers, in this order (reference model; rules in chapters 01, 02
and 05):

1. **Type and date** decide the rig, stern, head and steering (chapter 01).
2. **Deck length L** and **breadth B** decide depth in hold, keel length and tonnage (chapter 01).
3. **Shape numbers** (deadrise, sheer, tumblehome, position of the dead flat) decide the stations and the offsets
   (chapter 02).
4. **Port spacing** and the length of the waist decide the number of guns (chapters 01 and 04).
5. **L and B** decide the main mast, M = (L + B) / 2; all other masts and yards follow from M (chapter 05).
6. **Mast diameters** decide the rope sizes: the main stay is about 1/6 of the main mast diameter, the shrouds and
   lanyards follow from the stay (chapter 06, secondary sources, our inference).
7. **Yards and heights** decide the sails (chapter 08), and the sails decide the balance (this chapter).

So a change at the top runs all the way down. A change at the bottom (a longer jib-boom, a moved mast) can break a
check higher up, for example the sail balance.

## Which parameters to change

| Parameter (`data/parameters.json`) | Reference value | What follows from it | Chapter |
|---|---|---|---|
| deck length L (28.0 m, `data/SCHEMA.md`) | 28.0 m | keel, tonnage, number of ports, mast lengths | 01, 02, 05 |
| breadth B (chapter 01) | 7.60 m over planking | depth in hold, tonnage, mast lengths, deck width for guns | 01, 05 |
| `keel_drag_per_m`, `keel_rabbet_z_at_s0_m` | 0.40 m drag over the keel | draught fore and aft | 02 |
| `deck_at_side_s_z_m`, `deck_camber_m` | sheer 0.95 m forward, 0.45 m aft; camber 0.12 m | port sills, freeboard, walking surface | 02, 04 |
| `quarterdeck_break_s_m`, `quarterdeck_height_above_main_deck_m` | −5.04 m; 1.70 m | headroom aft, room for the main mast and ladder | 04 |
| `gunport_centres_s_m` | 6 open pairs at 2.45 m | guns, channels, chain plates, capstan room | 04, 09 |
| `fore_mast_s_at_deck_m`, `main_mast_s_at_deck_m` | +10.08, −1.40 | sail balance, hatches, capstan, stays | 05 |
| `snow_rig`, `has_boom` (group `variants`) | snow, no boom | gaff sail on a trysail mast or on the mainmast | 05, 08 |
| `steering_drive` | wheel (tiller as a variant) | steering gear, stations aft | 09 |
| `bowsprit_steeve_deg` | 30° | jib-boom height, head sails, fore stay leads | 05, 06 |

Change one group at a time and run the checks of this chapter after each change.

## Proportion rules in one place

| Quantity | Rule | Confidence and source |
|---|---|---|
| Deck length / breadth | 3.1–3.3 for sloops of 1710–1720; 3.5–3.7 for the snow-sloops of the 1740s | our inference from secondary data, chapter 01 |
| Depth in hold | 0.40–0.45 of B (sloops); 0.32 for the 20-gun ship of 1719 | our inference, chapter 01; secondary [1] |
| Keel | 0.77–0.84 of the deck length | our inference, chapter 01 |
| Tons burthen | K × B × (B/2) / 94 (feet) | secondary, chapter 02 |
| Displacement | Δ = 1.025 · Cb · L_wl · B_wl · T; Cb about 0.50 for this hull | standard, chapter 02; reference model |
| Port spacing | about 2.3–2.6 m between centres | our inference from secondary data, chapter 01 |
| Main mast | M = (L + B) / 2, from the heel to the cap | period (Steel 1794) [2], chapter 05 |
| Fore mast | 8/9 M | period [2] |
| Mizen mast (three-masters) | 6/7 M | period [2] |
| Topmasts | main 3/5 M; fore 8/9 of the main topmast; mizen 3/4 of the main topmast | period [2] |
| Topgallant masts | 1/2 of the topmast | period [2], chapter 05 |
| Main yard | 8/9 M; fore yard 7/8 of the main yard | period [2] |
| Topsail yards | main 5/7 of the main yard; fore 7/8 of the main topsail yard | period [2] |
| Cross-jack yard (three-masters) | = fore topsail yard | period [2] |
| Mizen yard (lateen) | 6/7 of the main yard | period [2] |
| Bowsprit, jib-boom | 3/5 M; jib-boom about 5/7 of the bowsprit | period [2], chapter 05 |
| Boom and gaff of a sloop | boom 2/3 of its mast; gaff 3/5 of the boom | period [2], chapter 05 |
| Diameters | 1 in per yard of length (1/36) for masts; 0.7 in per yard for lower yards | period [2], chapter 05 |
| Mast positions, ship | fore 1/9, main 5/9, mizen 17/20 of the deck length abaft the stem | period [2], chapter 05 |
| Main stay | about 1/6 of the main mast diameter | secondary, chapter 06 |

Steel printed these rules in **1794**, about 80 years after our date. Chapter 05 explains why we still use them and
where the earlier rules differ.

## Rig variants

| Variant | What changes from the reference snow | Earliest safe date | Confidence and source |
|---|---|---|---|
| **Brig with a boom** (later brig) | no trysail mast; the gaff and a boom sit on the mainmast itself; `snow_rig = false`, `has_boom = true` | about 1770 for the name and rig in the strict sense | period records via study, chapter 01 [3] |
| **Brigantine** | foremast square-rigged; mainmast with a gaff sail and small square topsails only | about 1695 | period, chapter 01 [3] |
| **Sloop** (one mast) | one mast with a gaff mainsail, staysail and jib; larger ones with a square topsail | before 1700 | period, chapter 01 [3] |
| **Ketch** | tall mainmast and a short mizzen, no foremast; the mizzen stands forward of the rudder head | 17th century; navies used ketches for bomb vessels and small sloops | period, chapter 01 [3]; secondary [4] |
| **Schooner** | two masts with gaff sails, small square topsails possible | Dutch pictures from the early 17th century; developed in British North America from about 1713 | secondary [5] |
| **Small three-masted ship** (sixth rate) | three masts, square sails on fore and main, a lateen mizzen; one gun deck | 20-gun ships of the 1719 Establishment | secondary [1]; mizzen: secondary [6] |

Notes for modellers (our inference):

- A **brig with a boom** needs room for the boom over the quarterdeck. In the reference model the boom jaws would be
  3.95 m above the main deck (`boom_jaws_above_main_deck_m`); check that the boom clears heads on the quarterdeck,
  which is 1.70 m higher.
- A **ketch** has no foremast, so the main mast moves forward to about where the snow's fore and main masts would
  balance. Re-run the sail balance; the mizzen moves the CE aft.
- A **schooner** of 1710 is rare in an English navy. Use it for colonial merchants and coasters.
- For a **three-master**, Steel's mizen yard is a long yard set at an angle (lateen) in our period. When the gaff
  mizzen (driver, spanker) replaced it is not settled in our sources: one source puts the change in the early 19th
  century [6] (secondary). Keep the lateen yard for 1710.

## Moving the date

| Feature | Earlier, about 1680–1700 | Reference, about 1710 | Later, about 1740–1770 | Confidence and source |
|---|---|---|---|---|
| Steering | whipstaff or tiller | tiller; wheel possible from about 1703–1712 | wheel usual; whipstaffs "largely replaced" by 1750 | secondary and period, chapter 09 |
| Head | lion figurehead | scroll on small ships about 1720; lion still standard on small RN ships | lion or scroll; billethead only late in the century | period (plans, model), secondary, chapters 01, 04 |
| Bowsprit | sprit topmast at the bowsprit end | small ships change to a jib-boom from 1705 | jib-boom on all ships within about 20 years | period, chapter 05 |
| Spritsail yard | yes | yes | yes, until about 1800 | period, chapter 05 |
| Gaff sail | small, on brigantines and sloops | without a boom, brailed to the mast | boom more and more common | secondary, chapter 08; our inference for the boom |
| Name "brig" | not used | short for "brigantine" | strict brig from about 1770 | period and secondary, chapter 01 |
| Bottom | wood, white stuff | wood, white stuff | copper from 1761 (HMS *Alarm*) | secondary, chapter 01 |
| Guns | mixed old patterns | Borgard's calibres from 1716 | carronades only from the 1770s | secondary, chapters 01, 09 |
| Pumps, galley | elm pumps, brick hearth | the same | iron stoves from the 1750s; improved chain pumps in the 1770s | secondary, chapter 09 |
| Boats | on the booms or towed | the same | davits only between 1790 and 1804 | secondary, chapter 01 |

Change the parts as a set. A 1740 hull with a whipstaff, or a 1700 hull with a wheel and a billethead, mixes dates.

## What to check after a change

### 1. Gun ports and room to work the guns

- Ports 2.3–2.6 m apart (chapter 01). A port must not cut a chain plate, a channel or a mast partner.
- Across the deck, two guns of a pair run in, plus their recoil, must leave a walkway. In the reference model the
  carriage is 1.5 m long and the recoil up to 1.5 m (`guns`, group `fittings`); several guns recoil less because a
  fitting stops them (`limited_by` in `data/moving-parts.csv`: main fife rail, capstan pawl rim, main and fore hatch).
- Each person at a gun needs a free circle of about 0.45 m radius (0.30 m against the side); the walking test of the
  reference model uses these values (reference model, chapter 13).
- Port sills at least about 1.2 m above the water (chapter 02).

### 2. Height below deck

- Depth in hold sets the space under the main deck. Under a quarterdeck 1.70 m high, with beams of about 0.22 m,
  headroom is about 1.5–1.6 m (chapter 04, our inference).
- If you lower the quarterdeck, check the wheel or tiller below it and the companion stairs (8 steps in
  `data/deck-layout.json`).

### 3. Draught and displacement

For a hull of the same shape, scale the displacement by length, breadth and draught (our inference):

Δ₂ ≈ Δ₁ · (L₂ / L₁) · (B₂ / B₁) · (T₂ / T₁)

with Δ₁ about 317 t, L₁ = 28.0 m, B₁ = 7.60 m, T₁ = 2.85 m to the rabbet (chapter 02). If you change the shape as
well, measure the new hull with the method of chapter 02. Check also that the tonnage (bm) lands within about 10 % of
a real ship of the same size (chapter 01). In the reference model bm / Δ is about 243 / 317 = 0.77 (our calculation);
a ship with a shallow hold has a larger ratio, because the bm formula ignores depth.

### 4. Sail balance

If the CE is too far aft, the ship turns into the wind by herself (weather helm); if it is too far forward, she
turns away from it (lee helm). The real centres move when the ship heels and gathers way, so designers draw the CE
some distance forward of the CLR [8] (secondary).

1. **CLR**: draw the underwater side profile (keel, stem, sternpost, up to the waterline; leave out the rudder) and
   find its centre of area. On paper: cut it out of card and balance it on a pin [7] (secondary).
2. **CE**: draw every sail flat in the side view; find the centre of area of each (a trapezoid for a square sail,
   a triangle for a head sail, a four-sided shape for a gaff sail); take the area-weighted mean.
3. **Lead** = s(CE) − s(CLR), divided by the waterline length.

For the reference model (our calculation from `data/offsets.csv`, `data/spars.csv` and the set-sail estimates in
`data/parameters.json`):

| Item | Value |
|---|---|
| Underwater profile | 80.4 m², CLR at s = −0.92, 1.53 m below the water |
| Courses, topsails, gaff sail, jib, fore topmast staysail | 638 m², CE at s = +3.33, 10.6 m above the water |
| Lead | 4.24 m = 15.5 % of L_wl 27.31 m |
| Topsails, gaff sail and jib only ("fighting sail") | 345 m², CE at s = +1.89, lead 2.81 m = 10.3 % |

For yachts, designers give a lead of 7–12 % for schooners, 11–14 % for ketches and 13–17 % for sloops [8]
(secondary, modern yachts). We found no period figure for square-riggers. Use the reference model as the yardstick:
keep your lead within a few per cent of its 15 % for the same sails, and within the yacht range for fore-and-aft rigs
(our inference).

### 5. Bracing range

A yard pivots on its mast. When it turns by an angle θ, its after edge swings towards the shrouds and backstays and
its forward edge towards the stays. For a shroud at a distance w out from the mast and a aft of it, at the height of
the yard, the yard touches it at about θ ≈ atan(a / w) (our inference, flat geometry; subtract the yard's thickness).
In the reference model the lowered yards turn only ±5° to ±10° before they touch stays or ratlines, and all yards
turn ±35° when hoisted to the working position (reference model, `data/moving-parts.csv`). Wider channels and more
raked shrouds give more room. After any change to channels, shrouds or yard lengths, run the test again (chapter 13).

### 6. Rope clashes

Every new stay or shroud must miss yards, tops, the boat on its booms and deck fittings. Run the intersection test of
chapter 13 on the rigging after each change. A stay through the boat was a real mistake in the reference model.

## Worked example A: a sloop of about 21 m (our inference)

**Brief.** A single-masted merchant or privateer sloop of about 1715, gaff mainsail, staysail and jib, ten small
guns. All numbers below are our inference unless a source is named.

**Hull.**

| Quantity | Rule | Value |
|---|---|---|
| Deck length L | chosen | 21.0 m |
| Breadth B | L / 3.26 (sloops 3.1–3.3) | 6.45 m |
| Depth in hold | 0.43 B | 2.77 m |
| Keel | 0.78 L | 16.38 m |
| Tons burthen | 53.7 × 21.16 × 10.58 / 94 (feet) | 128 bm (*Ferret* 1711: 114; *Cruizer* 1709: 123, chapter 01) |
| Draught to the rabbet | 2.85 × 2.77 / 3.20 | 2.47 m |
| Displacement | 317 × (21.0/28.0) × (6.45/7.60) × (2.47/2.85) | about 175 t |

**Guns.** Five pairs of ports at 2.45 m: 9.8 m between the first and last port. Ten 3-pounders (barrel about 1.37 m,
chapter 09).

**First rig: the rules as they stand.** M = (21.0 + 6.45) / 2 = 13.72 m; boom 2/3 M = 9.15 m; gaff 3/5 of the boom =
5.49 m; bowsprit 3/5 M = 8.23 m; jib-boom 5.88 m. We put the mast 0.45 L abaft the stem head (s = +1.05), which the
balance check below needs; a first try at 0.38 L gave a lead of about 22 %. Sails: gaff mainsail 62 m², jib 40 m²,
fore staysail 28 m², total 130 m². Lead 3.56 m = 17 % of the waterline length (20.5 m).

**Sail area check.** Compare sail area with displacement as SA / Δ^(2/3) (area in m², Δ in t). The reference snow
gives 345 / 317^(2/3) = 7.4 for its fighting sail and 13.7 for its working sail. Our first sloop gives 130 / 175^(2/3)
= 4.1: far too little sail. The rule M = (L + B) / 2 was made for the main mast of a two-master; with one mast it is
too short (our inference). We found no period rule for the mast of a single-masted sloop in our sources.

**Second rig: all spars 1.3 times longer.**

| Spar | Value | Rule used |
|---|---|---|
| Mast | 17.84 m, Ø 0.496 m | 1.3 × (L + B)/2; diameter 1/36 of length |
| Masthead | 2.48 m | 5/36 of the mast |
| Topmast | 10.70 m, Ø 0.297 m | 3/5 of the mast |
| Boom | 11.89 m | 2/3 of the mast; the boom end reaches s = −10.7, just past the stern at −10.5 |
| Gaff | 7.14 m, at 38° | 3/5 of the boom |
| Bowsprit, jib-boom | 10.71 m, 7.65 m | 3/5 of the mast; 5/7 of the bowsprit |
| Square topsail yard (optional) | 11.33 m | 5/7 of 8/9 of the mast |

| Sail | Area | Centre of area (s, height above water) |
|---|---|---|
| Gaff mainsail | 117 m² | (−3.89, 8.21) |
| Jib | 71 m² | (+11.81, 8.01) |
| Fore staysail | 42 m² | (+4.62, 5.79) |
| **Total** | **230 m²** | **CE (+2.49, 7.71)** |

- CLR: the reference profile scaled to 21 m puts it at s = −0.69.
- Lead: 2.49 − (−0.69) = 3.18 m = 15.5 % of 20.5 m. Inside the sloop range of [8] and equal to the reference snow.
- Sail area: 230 / 175^(2/3) = 7.4, equal to the fighting sail of the reference snow.
- The CE now stands 7.7 m above the water, higher than before. Stability is not covered by this guide; a taller rig
  needs more ballast.
- The optional square topsail would add area high up and forward of the mast; check the lead again if you add it.

## Worked example B: a three-masted ship of about 32 m (our inference)

**Brief.** A small three-masted warship of about 1719 with twenty guns on one deck, sized like the 20-gun ship of the
1719 Establishment (gun deck 106 ft 0 in = 32.3 m, breadth 28 ft 4 in = 8.6 m, depth 9 ft 2 in = 2.8 m, keel
87 ft 9 in = 26.7 m, 374 49/94 bm [1] (secondary)).

**Hull.**

| Quantity | Rule | Value |
|---|---|---|
| Deck length L | chosen | 32.0 m |
| Breadth B | L / 3.72 | 8.60 m |
| Depth in hold | 0.32 B, as in 1719 | 2.75 m |
| Keel | 0.83 L | 26.56 m |
| Tons burthen | 87.1 × 28.2 × 14.1 / 94 (feet) | 369 bm (1719 Establishment: 374.5, within 2 %) |
| Draught to the rabbet | 2.85 × 2.75 / 3.20 | 2.45 m |
| Displacement | 317 × (32.0/28.0) × (8.60/7.60) × (2.45/2.85) | about 353 t (uncertain: the hold is much shallower than ours) |

**Masts and yards** (Steel's rules [2]):

| Spar | Rule | Length | Diameter |
|---|---|---|---|
| Main mast | (L + B) / 2 | 20.30 m | 0.564 m |
| Fore mast | 8/9 main | 18.04 m | 0.507 m (9/10 of the main) |
| Mizen mast | 6/7 main | 17.40 m | 0.483 m (1/36 of its length, our inference) |
| Main, fore, mizen topmast | 3/5 main; 8/9 of it; 3/4 of it | 12.18, 10.83, 9.13 m | |
| Main, fore topgallant mast | 1/2 topmast | 6.09, 5.41 m | |
| Main yard, fore yard | 8/9 main mast; 7/8 of it | 18.04, 15.79 m | main 0.351 m |
| Main, fore topsail yard | 5/7 main yard; 7/8 of it | 12.89, 11.28 m | |
| Cross-jack yard, spritsail yard | = fore topsail yard | 11.28 m | |
| Mizen (lateen) yard | 6/7 main yard | 15.47 m | |
| Bowsprit, jib-boom | 3/5 main mast; 5/7 of it | 12.18, 8.70 m | |

**Mast positions** (fore 1/9, main 5/9, mizen 17/20 of L abaft the stem [2]): fore 3.56 m (s = +12.44), main
17.78 m (s = −1.78), mizen 27.20 m (s = −11.20).

**Guns.** Ten pairs at 2.45 m need 22.05 m between the first and last port: for example s = +11.50 down to −10.55.
The main mast at s = −1.78 then falls between the ports at −0.75 and −3.20, so its channels and chain plates fit
between ports. Crews: 6–7 men per 6-pounder (chapter 09), so about 70 men to fight one broadside.

**Sail balance, rough.** Weight the fore and main masts by the squares of their lower and topsail yard lengths, the
mizzen by about a quarter of the square of its lateen yard, and the head sails by about 12 % of the fore and main
together: the CE comes out at s = +5.2, the CLR
(scaled) at s = −1.05, a lead of about 6.3 m = 20 % of the waterline length. This is more than the reference snow's
15 %. The method is crude; draw the sails and do the full check before you trust it. If the full check agrees, move
the masts a little aft or shorten the jib-boom.

**Date check.** For 1719: tiller or wheel (both possible), lion figurehead, jib-boom (small ships changed from 1705),
spritsail yard, lateen mizzen, no copper, no carronades, boats on the booms (chapters 01, 05, 09).

## Check yourself

- [ ] I changed one group of parameters at a time and wrote down why.
- [ ] L / B, depth / B and keel / L lie inside the ranges of chapter 01, or I have a source for leaving them.
- [ ] My tonnage is within about 10 % of a real ship of the same size.
- [ ] Every mast and yard follows from M by a rule I can name, or is marked as my own choice.
- [ ] Ports are 2.3–2.6 m apart, clear of channels and masts, sills about 1.2 m or more above the water.
- [ ] Guns run in with full recoil still leave a walkway; every station has its free circle.
- [ ] Sail balance: lead within a few per cent of the reference model for the same sails.
- [ ] Sail area per displacement close to the reference model.
- [ ] Yards brace as far as the rig needs; nothing clashes in the intersection test.
- [ ] All parts fit the chosen date (steering, head, bowsprit, gaff, bottom, guns, boats).

## Typical mistakes

1. Scaling the whole reference model up or down by one factor: masts, ports, people and ladders do not scale that way.
2. Using M = (L + B) / 2 for the only mast of a sloop, which gives too little sail.
3. Moving a mast for the deck layout and forgetting the sail balance.
4. A ketch with the mizzen abaft the rudder head (that is a yawl [4]).
5. A three-master of 1710 with a gaff spanker and a dolphin striker.
6. More guns than the waist can hold, or ports through the chain plates.
7. Changing the date of the hull but not of the head, the steering or the bowsprit.

## Sources

1. Wikipedia, "1719 Establishment" https://en.wikipedia.org/wiki/1719_Establishment (CC BY-SA). 20-gun ship: gun deck
   106 ft, keel 87 ft 9 in, breadth 28 ft 4 in, depth 9 ft 2 in, 374 49/94 bm.
2. D. Steel, *The Elements and Practice of Rigging and Seamanship* (1794), transcription
   https://whalesite.org/anthology/1794_Steel_Elements_and_Practice.htm. Main mast from lower deck and extreme breadth,
   mizen mast 6/7 of the main mast, mizen topmast 3/4 of the main topmast, cross-jack yard equal to the fore topsail
   yard, mizen yard 6/7 of the main yard; mast positions 1/9, 5/9, 17/20. Other rules as in chapter 05.
3. W. A. Baker, "Vessel Types of Colonial Massachusetts" and the other sources of
   [chapter 01](01-ship-type-and-era.md) (rig names and dates).
4. Wikipedia, "Ketch" https://en.wikipedia.org/wiki/Ketch (CC BY-SA). Mizzen forward of the rudder post; ketch versus
   yawl.
5. Wikipedia, "Schooner" https://en.wikipedia.org/wiki/Schooner (CC BY-SA). Dutch pictures of the early 17th century;
   development in British North America from about 1713.
6. Wikipedia, "Lateen" https://en.wikipedia.org/wiki/Lateen (CC BY-SA). Lateen mizzen on full-rigged ships; replaced
   by the driver or spanker in the early 19th century according to this page.
7. Duckworks Magazine, article on boat balance https://duckworksmagazine.com/08/howto/balance/index.htm (finding the
   centre of lateral resistance by balancing the profile on a pin).
8. D. Gerr, "Helm Control: The Delicate Balance", *Small Boat Journal* 60 (1988), reprinted at
   https://duckworksmagazine.com/05/vintage/sbj/3/index.htm (lead as a percentage of waterline length by rig; modern
   small craft).

## Terms used in this chapter

| English | Polish | Explanation |
|---|---|---|
| parameter | parametr | One number a design is built from. |
| proportion rule | reguła proporcji | Rule giving one size from another. |
| variant | wariant | Same hull, different rig or fittings. |
| centre of effort (CE) | środek ożaglowania | Centre of area of the sails, where the wind force acts. |
| centre of lateral resistance (CLR) | środek bocznego oporu | Centre of area of the underwater side profile. |
| lead | wyprzedzenie (środka ożaglowania) | Distance of the CE forward of the CLR. |
| weather helm, lee helm | nawietrzność, zawietrzność | Tendency to turn into or away from the wind. |
| bracing range | zakres brasowania | How far a yard can turn. |
| displacement | wyporność | Mass of the water pushed aside by the hull. |
| ketch, yawl | kecz, jol (ożaglowanie) | Two-masters with the mizzen forward of or abaft the rudder head. |
| schooner | szkuner | Two or more masts with gaff sails. |
| sixth rate, Establishment | okręt VI rangi, ustalenie wymiarów (Establishment) | Smallest rated ship; fixed dimensions for a class. |
| lateen mizzen | bezan łaciński | Long yard set at an angle on the mizzen mast. |
| cross-jack yard | reja bezanowa (krojcel) | Lowest yard on the mizzen of a ship. |
| driver, spanker | bezan gaflowy | Gaff sail on the mizzen of a later ship. |
