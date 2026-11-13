# Reproducible SailerTales vessel reconstructions

Each sibling vessel directory is an independent game asset: `spec.json`, the
visual and collision GLBs in `model/`, a packed Blender scene, preview images,
authored routes in `navigation.json`, and a `validation.json` report.

The profiles refer to SailerTales commit
[`ea77e560ba4668c9dda55433813addbdb2f50176`](https://github.com/grzegorz2047/SailerTales/tree/ea77e560ba4668c9dda55433813addbdb2f50176).
Interior layouts, simplified hulls and new sailing rigs are game reconstructions,
not measured historical plans or replacements already connected to the game.
See each specification for its source paths and deliberate departures.

## Rebuild and validate

From the repository root, with Blender 5.2 and no add-ons (replace `brig` with the
selected vessel directory):

```sh
blender -b --factory-startup --python-exit-code 1 --python sailertales/common/build.py -- sailertales/brig/spec.json --render
blender -b --factory-startup --python-exit-code 1 --python sailertales/common/verify.py -- sailertales/brig/spec.json
python sailertales/common/check_asset.py
```

The last command requires only standard Python. It rejects missing or failed
reports and fingerprints that no longer match the GLBs, navigation, specification
or build/verification scripts. Changing a shared script requires rebuilding and
verifying every installed vessel.

## Walking and scope of checks

- Metres; glTF axes: X across, Y up, Z forward. Blender uses `(x, -s, height)`.
- Upright capsule: radius 0.38 m, total height 1.85 m, maximum floor slope 35 degrees.
- The actual exported visual AND collision GLBs are reimported for checking.
  Routes are sampled every 0.12 m or less, with 15 mm geometric tolerance, 80 mm
  rounded-foot lift and a 220 mm controller step allowance. These are sampled
  clearance checks, not a continuous physics simulation or complete navmesh.
- Negative controls reject a wall and a low ceiling and accept an open floor.
- Cloth is checked against other cloth, shrouds, lifts, forestays, masts, yards,
  booms, gaffs and bowsprit in the authored static pose. Bolt ropes intentionally
  attach to cloth edges. No claim is made for arbitrary trimming or moving cloth.
- Companionways are continuous inclined planked surfaces in both GLBs. Their
  transverse decorative strips are embedded below the walk surface. Rails stay
  outside the tested capsule, and landings meet the ramp ends at the same height.
- The wreck retains its 0.5 rad heel. Its longer, wider companionway is checked
  with world gravity vertical, including the combined longitudinal/transverse slope.

## Engine integration

Use `model/ship.glb` for rendering and `model/collision.glb` for physics; avoid
duplicating collision from the visual mesh. Configure static concave mesh
colliders for decks with real hatch openings and for the hollow hull. A convex
hull around the entire ship would close these openings. Apply exactly the same
asset transform to visuals, collision and the navigation points; the wreck's heel
is already baked in and must not be applied a second time.

Provide a character controller with the dimensions, slope and step rules above,
moving-platform support, water masking and spawn placement. These assets do not
include that adapter. A walking path is a verified corridor, not an invisible
barrier restricting movement to the line. Validate additional destinations when
adding gameplay or moving props.

The captain's door is a separate open node `Door_Captain_open`; `hinge_Captain`
records the hinge location. To animate it, parent the door and its matching
collider under a pivot at that marker; its current mesh origin is not the hinge.
Small open boats have no fabricated cabin or lower deck. Night-ship lantern nodes
are named for the engine's lighting sequence. No LODs, sail animations, full
structural simulation or arbitrary rig trimming are included in this asset set.
