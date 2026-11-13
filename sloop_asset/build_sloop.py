"""Build an independent inferred 1715 merchant sloop. Blender 4.3.2.
blender -b --factory-startup --python-exit-code 1 --python sloop_asset/build_sloop.py -- --out build/sloop_1715
"""

from pathlib import Path
import argparse, json, math, shutil, sys
import bpy, bmesh
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(Path(__file__).resolve().parent), str(ROOT / "blender")]
import geometry as G
from audit import audit_scene
from check_asset import source_hashes
import parametry as PR, rzedne, kadlub

P = lambda x, s, z: Vector((x, -s, z))
SCALE_X = 6.45 / 7.6
SCALE_S = 21 / 28
SCALE_Z = 2.47 / abs(PR.KADLUB["ZK0"])
STATIONS = []
OBSTACLES = []
CONTROLS = []


def write(name, value):
    (OUT / name).write_text(
        json.dumps(value, indent=2, ensure_ascii=False, default=lambda x: list(x)),
        encoding="utf-8",
    )


def plain(name, color, metal=0, rough=0.7):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = (*color, 1)
    bs.inputs["Roughness"].default_value = rough
    bs.inputs["Metallic"].default_value = metal
    return m


def empty(name, pos=(0, 0, 0), parent=None, kind=None):
    o = bpy.data.objects.new(name, None)
    G.ASSET.objects.link(o)
    o.location = pos
    if parent:
        G.parent_world(o, parent)
    if kind:
        o["control_type"] = kind
        CONTROLS.append(o)
    return o


def mesh(name, verts, faces, mat, uv=None, parent=None):
    o = G.new_mesh(name, verts, faces, mat, uv)
    if parent:
        G.parent_world(o, parent)
    return o


def box(name, c, size, mat, parent=None):
    x, y, z = c
    a, b, d = [v / 2 for v in size]
    vs = [
        (x + i * a, y + j * b, z + k * d)
        for k in (-1, 1)
        for j in (-1, 1)
        for i in (-1, 1)
    ]
    o = mesh(
        name,
        vs,
        [
            (0, 2, 3, 1),
            (4, 5, 7, 6),
            (0, 1, 5, 4),
            (2, 6, 7, 3),
            (0, 4, 6, 2),
            (1, 3, 7, 5),
        ],
        mat,
        parent=parent,
    )
    uv = o.data.uv_layers.new(name="UVMap")
    for face in o.data.polygons:
        face.use_smooth = False
        axis = max(range(3), key=lambda i: abs(face.normal[i]))
        axes = [i for i in range(3) if i != axis]
        for li in face.loop_indices:
            p = o.data.vertices[o.data.loops[li].vertex_index].co
            uv.data[li].uv = (p[axes[0]] * 0.8, p[axes[1]] * 0.8)
    return o


def tube(name, points, d, mat, parent=None, sides=8):
    o = G.tube(name, points, d, mat, sides)
    if parent:
        G.parent_world(o, parent)
    return o


def tapered(name, points, diameters, mat, parent=None, sides=12):
    o = tube(name, points, 1, mat, parent, sides)
    for i, d in enumerate(diameters):
        p = Vector(points[i])
        for v in o.data.vertices[i * sides : (i + 1) * sides]:
            v.co = p + (v.co - p) * d
    return o


def ring(name, c, axis, r, thickness, mat, parent=None):
    axis = Vector(axis).normalized()
    u = axis.cross(Vector((0, 0, 1)))
    if u.length < 0.1:
        u = axis.cross(Vector((1, 0, 0)))
    u.normalize()
    v = axis.cross(u)
    pts = [
        Vector(c) + r * (u * math.cos(t) + v * math.sin(t))
        for t in np.linspace(0, 2 * math.pi, 25)
    ]
    return tube(name, pts, thickness, mat, parent, 6)


def rope(name, pts, d=0.022, tar=False, parent=None):
    return tube(name, pts, d, M["rope_tarred" if tar else "rope_untarred"], parent, 5)


def workstation(name, x, s, role):
    x = max(-float(DECK.width(s)) + 0.45, min(float(DECK.width(s)) - 0.45, x))
    z = DECK.heights(x, s)
    o = empty("station_" + name, P(x, s, z))
    o["role"] = role
    STATIONS.append(
        {"id": name, "position_gltf_m": [x, z, s], "role": role, "crew_height_m": 1.75}
    )


def obstacle(name, x, s, w, l, h):
    OBSTACLES.append({"id": name, "x": x, "s": s, "width": w, "length": l, "height": h})


class Deck:
    def __init__(self, ps, kd):
        global SCALE_X, SCALE_S
        SCALE_X = 6.45 / (2 * float(np.max(ps.X0[ps.r_deck])))
        SCALE_S = 21 / float(ps.S0[ps.r_deck, -1] - ps.S0[ps.r_deck, 0])
        self.ss = ps.S0[ps.r_deck] * SCALE_S
        self.ww = ps.X0[ps.r_deck] * SCALE_X
        self.kd = kd

    def width(self, s):
        return np.interp(s, self.ss, self.ww)

    def heights(self, x, s):
        w = self.width(s)
        return self.kd.Zd(np.asarray(s) / SCALE_S) * 0.95 + 0.10 * (
            (w / (6.45 / 2)) ** 2 - (np.asarray(x) / (6.45 / 2)) ** 2
        )


def hull():
    global DECK
    kd = rzedne.Kadlub(PR.KADLUB, PR.RZEDNE_H, PR.RZEDNE_S, PR.RZEDNE)
    ps = kadlub.Poszycie(kd, PR.KADLUB)
    DECK = Deck(ps, kd)
    G.DECKS = DECK
    nr = ps.r_deck + 1
    nc = ps.X.shape[1]
    verts = []
    faces = []
    mi = []
    mats = [
        M["bottom_white_stuff"],
        M["side_oiled_oak"],
        M["wood_black"],
        M["deck_planking"],
    ]
    ids = {}
    for side in (-1, 1):
        for r in range(nr):
            for c in range(nc):
                z = ps.Z[r, c]
                ids[side, r, c] = len(verts)
                verts.append(
                    P(
                        side * ps.X[r, c] * SCALE_X,
                        ps.Ss[r, c] * SCALE_S,
                        z * (SCALE_Z if z < 0 else 0.95),
                    )
                )
        for r in range(nr - 1):
            for c in range(nc - 1):
                faces.append(
                    tuple(
                        ids[side, a, b]
                        for a, b in ((r, c), (r, c + 1), (r + 1, c + 1), (r + 1, c))
                    )
                )
                mi.append(
                    0
                    if ps.tags[r] in ("dno", "farba_dna")
                    else 2 if ps.tags[r] == "bergholt" else 1
                )
    for c in range(nc - 1):
        faces.append((ids[-1, 0, c], ids[1, 0, c], ids[1, 0, c + 1], ids[-1, 0, c + 1]))
        mi.append(0)
    for c in (0, nc - 1):
        for r in range(nr - 1):
            faces.append(
                (ids[-1, r, c], ids[-1, r + 1, c], ids[1, r + 1, c], ids[1, r, c])
            )
            mi.append(0 if r < 24 else 1)
    cap = {}
    r = nr - 1
    ntrans = 12
    for c in range(nc):
        s = ps.S0[r, c] * SCALE_S
        w = ps.X0[r, c] * SCALE_X
        for j in range(ntrans + 1):
            if j == 0:
                cap[c, j] = ids[-1, r, c]
            elif j == ntrans:
                cap[c, j] = ids[1, r, c]
            else:
                x = w * (j / ntrans * 2 - 1)
                cap[c, j] = len(verts)
                verts.append(P(x, s, float(DECK.heights(x, s))))
    for c in range(nc - 1):
        for j in range(ntrans):
            faces.append((cap[c, j], cap[c + 1, j], cap[c + 1, j + 1], cap[c, j + 1]))
            mi.append(3)
    # The end-cap boundary is subdivided to match the deck cap exactly.
    for c in (0, nc - 1):
        old = 2 * (nr - 1) * (nc - 1) + (nc - 1) + (0 if c == 0 else nr - 1) + (nr - 2)
        # Same wall face, now with all deck-edge points as part of its polygon.
        faces[old] = tuple(
            [ids[-1, nr - 2, c], ids[1, nr - 2, c]]
            + [cap[c, j] for j in range(ntrans, -1, -1)]
        )
    o = mesh("sloop_hull_closed", verts, faces, mats[0])
    [o.data.materials.append(m) for m in mats[1:]]
    for p, m in zip(o.data.polygons, mi):
        p.material_index = m
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if bm.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    bad = sum(not e.is_manifold for e in bm.edges)
    volume = bm.calc_volume()
    bm.to_mesh(o.data)
    bm.free()
    assert bad == 0, ("hull nonmanifold", bad)
    layer = o.data.uv_layers.new(name="UVMap")
    for poly in o.data.polygons:
        for li in poly.loop_indices:
            p = o.data.vertices[o.data.loops[li].vertex_index].co
            layer.data[li].uv = (
                (p.x * 0.7, -p.y * 0.6)
                if poly.material_index == 3
                else (-p.y * 0.32, p.z * 0.5)
            )
    o["provenance"] = (
        "New watertight sloop mesh from reference offset-line family, rescaled independently of the snow game asset."
    )
    # Bulwarks, gunports and continuous capping rails follow the new working deck.
    a = float(DECK.ss[0])
    f = float(DECK.ss[-1])
    ports = (-0.9, 6.5)
    edges = sorted(
        set(
            [
                a,
                f,
                *np.linspace(a, f, 70),
                *[v for s in ports for v in (s - 0.48, s + 0.48)],
            ]
        )
    )
    vs = []
    fs = []

    def wall(side, s0, s1, h0, h1):
        base = len(vs)
        for s in (s0, s1):
            w = float(DECK.width(s))
            z = float(DECK.heights(w, s))
            for x in (side * (w - 0.12), side * (w + 0.015)):
                for h in (h0, h1):
                    vs.append(P(x, s, z + h))
        fs.extend(
            tuple(base + i for i in q)
            for q in (
                (0, 4, 6, 2),
                (1, 3, 7, 5),
                (0, 1, 5, 4),
                (2, 6, 7, 3),
                (0, 2, 3, 1),
                (4, 5, 7, 6),
            )
        )

    for side in (-1, 1):
        for s0, s1 in zip(edges, edges[1:]):
            if any(abs((s0 + s1) / 2 - s) < 0.48 for s in ports):
                wall(side, s0, s1, 0, 0.23)
                wall(side, s0, s1, 0.78, 0.84)
            else:
                wall(side, s0, s1, 0, 0.84)
        pts = [
            P(
                side * float(DECK.width(s)),
                s,
                float(DECK.heights(DECK.width(s), s)) + 0.86,
            )
            for s in np.linspace(a, f, 100)
        ]
        tube("caprail_" + str(side), pts, 0.16, M["wood_dark"], sides=8)
    walls = mesh("merchant_teal_bulwarks", vs, fs, M["paint_merchant_teal"])
    for p in walls.data.polygons:
        p.use_smooth = False
    for s in (a, f):
        w = float(DECK.width(s))
        z = float(DECK.heights(w, s))
        box(
            "end_bulwark",
            P(0, s, z + 0.42),
            (max(0.2, 2 * w), 0.14, 0.84),
            M["paint_merchant_teal"],
        )
    # Solid keel and stem from the same scaled rabbet profile.
    kp = [
        P(0, s * SCALE_S, float(kd.zk(s)) * SCALE_Z - 0.12)
        for s in np.linspace(-10.6, 10.7, 24)
    ]
    tube("keel", kp, 0.24, M["wood_dark"], sides=4)
    sp = [
        P(0, s * SCALE_S, z * (SCALE_Z if z < 0 else 0.95))
        for s, z in PR.KADLUB["DZIOB"]
    ]
    tube("raked_stem", sp, 0.27, M["wood_dark"], sides=6)
    return {
        "closed_shell_volume_m3": round(volume, 3),
        "nonmanifold_edges": bad,
        "deck_length_m": round(f - a, 4),
        "beam_m": round(float(max(DECK.ww) * 2), 4),
        "scaled_rabbet_depth_midship_m": 2.47,
    }


def deck_fittings():
    # A modest aft cabin leaves both side passages open.
    s = -6.4
    z = float(DECK.heights(0, s))
    box("aft_cabin", P(0, s, z + 0.55), (2.0, 2.6, 1.1), M["side_oiled_oak"])
    obstacle("aft_cabin", 0, s, 2.0, 2.6, 1.1)
    box("cabin_roof", P(0, s, z + 1.14), (2.25, 2.85, 0.15), M["wood_dark"])
    box("cabin_door", P(0, s + 1.31, z + 0.47), (0.62, 0.04, 0.94), M["wood_dark"])
    for x in (-0.7, 0.7):
        box(
            "cabin_window_frame",
            P(x, s + 1.335, z + 0.72),
            (0.39, 0.045, 0.36),
            M["paint_ochre"],
        )
        box(
            "cabin_window",
            P(x, s + 1.365, z + 0.72),
            (0.30, 0.025, 0.27),
            M["glass_sloop"],
        )
        box(
            "window_mullion",
            P(x, s + 1.39, z + 0.72),
            (0.025, 0.025, 0.28),
            M["paint_ochre"],
        )
    for name, s, w, l in (
        ("main_cargo_hatch", 4.0, 1.7, 2.4),
        ("aft_hatch", -3.4, 1.5, 2.0),
    ):
        z = float(DECK.heights(0, s))
        box(
            name + "_coaming",
            P(0, s, z + 0.08),
            (w + 0.15, l + 0.15, 0.16),
            M["wood_dark"],
        )
        box(name + "_closed_lid", P(0, s, z + 0.155), (w, l, 0.06), M["deck_planking"])
        for dx in (-w * 0.28, w * 0.28):
            box(name + "_strap", P(dx, s, z + 0.192), (0.045, l, 0.018), M["iron"])
    for i, (x, s) in enumerate(((1.75, -3.5), (-1.75, -3.5))):
        z = float(DECK.heights(x, s))
        pts = [P(x, s, z + h) for h in (0, 0.12, 0.4, 0.7, 0.8)]
        tapered(
            "cargo_cask_" + str(i),
            pts,
            [0.5, 0.64, 0.68, 0.62, 0.5],
            M["wood_dark"],
            sides=14,
        )
        for h, r in ((0.10, 0.30), (0.27, 0.335), (0.57, 0.33), (0.72, 0.29)):
            ring("cask_hoop", P(x, s, z + h), (0, 0, 1), r, 0.035, M["iron"])
        obstacle("cask_" + str(i), x, s, 0.7, 0.7, 0.8)
    for i, (x, s) in enumerate(((1.6, 3.4), (-1.5, 4.5))):
        z = float(DECK.heights(x, s))
        box(
            "cargo_crate_" + str(i),
            P(x, s, z + 0.37),
            (0.7, 0.8, 0.74),
            M["side_oiled_oak"],
        )
        for dx in (-0.27, 0.27):
            box(
                "crate_strap",
                P(x + dx, s, z + 0.38),
                (0.045, 0.83, 0.78),
                M["wood_dark"],
            )
        obstacle("crate_" + str(i), x, s, 0.8, 0.9, 0.8)
    # Capstan, bitts and a period timber-stock anchor at each bow.
    s = 8.9
    z = float(DECK.heights(0, s))
    root = empty("capstan_rotation", P(0, s, z), kind="rotate_local_z")
    tapered(
        "capstan_drum",
        [P(0, s, z + h) for h in (0, 0.12, 0.65, 0.8)],
        [0.7, 0.48, 0.38, 0.7],
        M["wood_dark"],
        root,
    )
    for theta in (0, math.pi / 2):
        vec = Vector((math.cos(theta), math.sin(theta), 0))
        tube(
            "capstan_handspike",
            [P(0, s, z + 0.7) - vec, P(0, s, z + 0.7) + vec],
            0.07,
            M["wood"],
            root,
        )
    obstacle("capstan", 0, s, 1.8, 1.8, 0.85)
    for side in (-1, 1):
        x = side * 1.9
        s = 8.3
        z = float(DECK.heights(x, s))
        tube(
            "cathead",
            [P(x, s, z + 0.5), P(side * 3.0, s + 1.0, z + 1.0)],
            0.22,
            M["wood_dark"],
            sides=4,
        )
        c = P(side * 2.8, s + 1, z + 0.1)
        tube(
            "anchor_shank",
            [c + Vector((0, 0, -0.8)), c + Vector((0, 0, 0.65))],
            0.105,
            M["iron"],
        )
        tube(
            "anchor_arms",
            [
                c + Vector((-0.6, 0, -0.5)),
                c + Vector((0, 0, -0.8)),
                c + Vector((0.6, 0, -0.5)),
            ],
            0.09,
            M["iron"],
        )
        box(
            "anchor_timber_stock",
            c + Vector((0, 0, 0.45)),
            (0.16, 1.2, 0.18),
            M["wood_dark"],
        )
        ring("anchor_ring", c + Vector((0, 0, 0.75)), (0, 1, 0), 0.13, 0.035, M["iron"])
        rope(
            "anchor_cable_" + str(side),
            [
                c + Vector((0, 0, 0.8)),
                P(side * 2.6, 8.8, z + 0.9),
                P(side * 0.5, 7.6, z + 0.12),
            ],
            0.065,
            True,
        )
    # Pins, cleats, belayed coils, stern compass and bell.
    for side in (-1, 1):
        for s in (-8.5, -1.7, 3.8, 7.9):
            x = side * (float(DECK.width(s)) - 0.28)
            z = float(DECK.heights(x, s))
            box("pinrail", P(x, s, z + 0.88), (0.23, 0.7, 0.075), M["wood_dark"])
            for ds in (-0.22, 0, 0.22):
                tube(
                    "belaying_pin",
                    [P(x, s + ds, z + 0.68), P(x, s + ds, z + 1.03)],
                    0.035,
                    M["wood"],
                )
            pts = [
                P(
                    x - 0.12 * side + 0.14 * math.cos(t),
                    s + 0.2 * math.sin(t),
                    z + 0.05 + 0.005 * t,
                )
                for t in np.linspace(0, 6 * math.pi, 65)
            ]
            rope("belayed_coil", pts, 0.018)
    z = float(DECK.heights(-1.55, -8.3))
    box(
        "compass_binnacle", P(-1.55, -8.3, z + 0.47), (0.42, 0.38, 0.94), M["wood_dark"]
    )
    tapered(
        "compass_bowl",
        [P(-1.55, -8.3, z + h) for h in (0.96, 1.06)],
        [0.28, 0.32],
        M["bronze"],
    )
    x = 1.25
    s = 7.1
    z = float(DECK.heights(x, s))
    tube(
        "bell_frame",
        [
            P(x - 0.25, s, z),
            P(x - 0.25, s, z + 1.4),
            P(x + 0.25, s, z + 1.4),
            P(x + 0.25, s, z),
        ],
        0.065,
        M["wood_dark"],
    )
    tapered(
        "ship_bell",
        [P(x, s, z + h) for h in (1.27, 1.15, 0.99)],
        [0.08, 0.15, 0.26],
        M["bronze"],
    )
    workstation("helm", 1.25, -8.7, "tiller")
    workstation("main_halyards", 1.35, 0, "main_sail")
    workstation("cargo", 0.9, 5.6, "cargo")
    workstation("anchor", -1.3, 8.5, "anchor")


def guns():
    for side in (-1, 1):
        for number, s in enumerate((-0.9, 6.5)):
            x = side * (float(DECK.width(s)) - 0.88)
            z = float(DECK.heights(x, s))
            name = ("port" if side > 0 else "starboard") + "_" + str(number + 1)
            root = empty(
                "gun_" + name + "_recoil", P(x, s, z), kind="translate_local_x"
            )
            root["range_m"] = [-0.6, 0]
            root["calibre"] = "3-pounder illustrative"
            # Construct locally; the whole mount is then rotated to point outboard.
            parts = []
            base = P(x, s, z)
            parts.append(
                box(
                    name + "_carriage",
                    base + Vector((0, 0, 0.35)),
                    (0.95, 0.66, 0.26),
                    M["carriage_red_ochre"],
                )
            )
            for yy in (-0.3, 0.3):
                parts.append(
                    box(
                        name + "_cheek",
                        base + Vector((0, yy, 0.52)),
                        (0.74, 0.09, 0.36),
                        M["carriage_red_ochre"],
                    )
                )
                for xx in (-0.32, 0.32):
                    parts.append(
                        tube(
                            name + "_wheel",
                            [
                                base + Vector((xx, yy - 0.07, 0.19)),
                                base + Vector((xx, yy + 0.07, 0.19)),
                            ],
                            0.36,
                            M["wood_dark"],
                            sides=12,
                        )
                    )
            pivot = empty(
                "gun_" + name + "_elevation",
                base + Vector((-0.02, 0, 0.65)),
                root,
                "rotate_local_y",
            )
            pivot["range_deg"] = [-5, 12]
            profile = [
                (-0.28, 0.025),
                (-0.26, 0.06),
                (-0.18, 0.055),
                (-0.16, 0.115),
                (0.02, 0.12),
                (0.1, 0.1),
                (0.8, 0.07),
                (1.1, 0.066),
                (1.17, 0.09),
                (1.22, 0.09),
                (1.23, 0.038),
                (0.98, 0.038),
                (0.98, 0.004),
                (-0.28, 0.004),
            ]
            vs = []
            fs = []
            N = 16
            for xx, r in profile:
                for j in range(N):
                    vs.append(
                        base
                        + Vector((-0.02, 0, 0.65))
                        + Vector(
                            (
                                xx,
                                r * math.cos(j * 2 * math.pi / N),
                                r * math.sin(j * 2 * math.pi / N),
                            )
                        )
                    )
            for i in range(len(profile)):
                for j in range(N):
                    fs.append(
                        (
                            i * N + j,
                            i * N + (j + 1) % N,
                            ((i + 1) % len(profile)) * N + (j + 1) % N,
                            ((i + 1) % len(profile)) * N + j,
                        )
                    )
            mesh(name + "_hollow_barrel", vs, fs, M["iron_gun_barrel"], parent=pivot)
            for o in parts:
                G.parent_world(o, root)
            # Parent transform is applied only after world-preserving parenting.
            root.rotation_euler.z = 0 if side > 0 else math.pi
            obstacle("gun_" + name, x, s, 1.2, 1.0, 0.9)
            workstation("gun_" + name, side * (abs(x) - 1.0), s, "gun_3lb")


def rudder():
    s = -10.6
    z = float(DECK.heights(0, -10.2))
    r = empty("rudder_and_tiller", P(0, s, z + 0.45), kind="rotate_local_z")
    r["range_deg"] = [-30, 30]
    # Stock, blade and two pintles: no wheel or modern linkage.
    tube("rudder_stock", [P(0, s, -2.4), P(0, s, z + 0.55)], 0.19, M["wood_dark"], r)
    vs = [
        P(x, ss, h)
        for x in (-0.12, 0.12)
        for ss, h in ((s, -2.4), (s - 1.1, -2.2), (s - 0.7, -0.2), (s, -0.2))
    ]
    mesh(
        "rudder_blade",
        vs,
        [
            (0, 3, 2, 1),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
        ],
        M["wood_dark"],
        parent=r,
    )
    for h in (-1.8, -0.65):
        ring("rudder_pintle", P(0, s, h), (0, 0, 1), 0.14, 0.04, M["iron"], r)
    tube(
        "tiller",
        [P(0, s, z + 0.46), P(0.35, -9.2, z + 0.55), P(0.45, -8.2, z + 0.50)],
        0.12,
        M["wood"],
        r,
    )


# Cloth edges carry no morph displacement; rope attachments remain pinned.
def sail_quad(name, corners, boom):
    A, B, C, D = map(Vector, corners)
    N = 24
    vs = []
    uv = []
    weights = []

    def pt(u, v):
        low = A.lerp(D, v)
        low.z += 0.27 * math.sin(math.pi * v)
        high = B.lerp(C, v)
        p = low.lerp(high, u)
        w = math.sin(math.pi * u) * math.sin(math.pi * v)
        p.x += 0.43 * w
        return p, w

    for i in range(N + 1):
        for j in range(N + 1):
            p, w = pt(i / N, j / N)
            vs.append(p)
            weights.append(w)
            uv.append((j / N, i / N))
    fs = [
        (
            i * (N + 1) + j,
            i * (N + 1) + j + 1,
            (i + 1) * (N + 1) + j + 1,
            (i + 1) * (N + 1) + j,
        )
        for i in range(N)
        for j in range(N)
    ]
    mat = G.canvas_material(name, 11, 11, (2, 3))
    o = mesh(name + "_set", vs, fs, mat, uv, boom)
    G.animate_sail(o, weights)
    edgepaths = [
        [pt(0, v)[0] for v in np.linspace(0, 1, N + 1)],
        [pt(1, v)[0] for v in np.linspace(0, 1, N + 1)],
        [pt(u, 0)[0] for u in np.linspace(0, 1, N + 1)],
        [pt(u, 1)[0] for u in np.linspace(0, 1, N + 1)],
    ]
    for i, pts in enumerate(edgepaths):
        rope(name + "_bolt_rope_" + str(i), pts, 0.022, parent=boom)
    return o


def sail_tri(name, corners, parent):
    A, B, C = map(Vector, corners)
    N = 24
    vs = []
    uv = []
    weights = []
    ids = {}
    for i in range(N + 1):
        for j in range(N + 1 - i):
            u = i / N
            v = j / N
            w = 27 * u * v * (1 - u - v)
            p = A * (1 - u - v) + B * u + C * v
            p.x += 0.26 * w
            ids[i, j] = len(vs)
            vs.append(p)
            uv.append((u, v))
            weights.append(w)
    fs = []
    for i in range(N):
        for j in range(N - i):
            fs.append((ids[i, j], ids[i + 1, j], ids[i, j + 1]))
            if j < N - i - 1:
                fs.append((ids[i + 1, j], ids[i + 1, j + 1], ids[i, j + 1]))
    mat = G.canvas_material(name, 10, 11, ())
    o = mesh(name + "_set", vs, fs, mat, uv, parent)
    G.animate_sail(o, weights)
    for i, (a, b) in enumerate(((A, B), (B, C), (C, A))):
        rope(name + "_bolt_rope_" + str(i), [a, b], 0.018, parent=parent)
    return o


def rig():
    mast = empty("main_mast", P(0, 1.05, -1.84), kind="fixed_mast")
    mast["length_m"] = 17.84
    tapered(
        "main_mast_timber",
        [P(0, 1.05, z) for z in (-1.84, 1.0, 10.0, 13.5, 16.0)],
        [0.44, 0.496, 0.34, 0.28, 0.20],
        M["wood"],
        mast,
    )
    for z in (1.4, 3.0, 10.0, 13.5):
        ring(
            "mast_iron_band",
            P(0, 1.05, z),
            (0, 0, 1),
            0.247 if z < 4 else 0.17,
            0.035,
            M["iron"],
            mast,
        )
    boom = empty("main_boom", P(0.18, 0.83, 3.7), kind="rotate_local_z")
    boom["range_deg"] = [-35, 35]
    boom["default_pose_only_collision_checked"] = True
    tapered(
        "boom_timber",
        [P(0.18, 0.83, 3.7), P(1.65, -10.5, 3.8)],
        [0.25, 0.14],
        M["wood"],
        boom,
    )
    gaff = empty("main_gaff", P(0.10, 0.8, 11.12), mast, "hoist_and_rotate")
    gaff["angle_deg"] = 38
    tapered(
        "gaff_timber",
        [P(0.10, 0.8, 11.12), P(0.84, -4.63, 15.51)],
        [0.22, 0.13],
        M["wood"],
        gaff,
    )
    ring("gaff_jaws", P(0, 1.05, 11.12), (0, 0, 1), 0.3, 0.08, M["wood_dark"], gaff)
    sail_quad(
        "gaff_main",
        [
            P(0.22, 0.8, 3.95),
            P(0.22, 0.8, 11.0),
            P(0.96, -4.63, 15.4),
            P(1.63, -10.0, 4.0),
        ],
        boom,
    )
    for z in np.linspace(4, 10.9, 8):
        ring(
            "main_luff_hoop",
            P(0, 1.05, z),
            (0, 0, 1),
            0.335,
            0.025,
            M["wood_dark"],
            mast,
        )
    # Lacing sections sit along the head/foot edge, not through the canvas.
    for j, v in enumerate(np.linspace(0.06, 0.94, 12)):
        head = P(0.22, 0.8, 11.0).lerp(P(0.96, -4.63, 15.4), v)
        spar = P(0.10, 0.8, 11.12).lerp(P(0.84, -4.63, 15.51), v)
        rope("main_head_lacing_" + str(j), [head, spar], 0.012, parent=gaff)
        foot = P(0.22, 0.8, 3.95).lerp(P(1.63, -10, 4), v)
        foot.z += 0.27 * math.sin(math.pi * v)
        rope(
            "main_foot_lacing_" + str(j),
            [foot, P(0.18, 0.83, 3.7).lerp(P(1.65, -10.5, 3.8), v)],
            0.012,
            parent=boom,
        )
    bowsprit = empty("bowsprit", P(0, 5, 1.5), kind="fixed_spar")
    tapered(
        "bowsprit_timber",
        [P(0, 5, 1.5), P(0, 14.275, 6.85)],
        [0.35, 0.19],
        M["wood"],
        bowsprit,
    )
    tapered(
        "jibboom_timber",
        [P(0, 11.5, 5.25), P(0, 18.12, 9.08)],
        [0.19, 0.09],
        M["wood"],
        bowsprit,
    )
    # Stays occupy the windward face; sail clews and their sheets are to port.
    inner = [P(0.12, 1.15, 11.5), P(0.12, 13.5, 6.4), P(1.3, 5.1, 3.5)]
    outer = [P(0.14, 1.1, 15.6), P(0.14, 17.5, 8.8), P(2.8, 12.5, 4.8)]
    sail_tri("inner_staysail", inner, mast)
    sail_tri("outer_jib", outer, mast)
    for name, cs in (("inner_stay", inner), ("outer_stay", outer)):
        a, b, _ = cs
        a = a.copy()
        b = b.copy()
        a.x = 0
        b.x = 0
        rope(name, [a, b], 0.043, True, mast)
        for j, t in enumerate(np.linspace(0.06, 0.96, 13)):
            p = a.lerp(b, t)
            ring(name + "_hank_" + str(j), p, (0, 1, 0.5), 0.13, 0.013, M["iron"], mast)
    rope(
        "inner_sheet",
        [
            inner[2],
            P(
                float(DECK.width(3.8)) - 0.28,
                3.8,
                float(DECK.heights(float(DECK.width(3.8)) - 0.28, 3.8)) + 0.95,
            ),
        ],
        0.027,
        parent=mast,
    )
    rope(
        "jib_sheet",
        [
            outer[2],
            P(
                float(DECK.width(7.9)) - 0.28,
                7.9,
                float(DECK.heights(float(DECK.width(7.9)) - 0.28, 7.9)) + 0.95,
            ),
        ],
        0.027,
        parent=mast,
    )
    rope(
        "throat_halyard",
        [P(-0.15, 1.05, 15.8), P(-0.15, 0.8, 11.2), P(-0.45, 1.0, 2.1)],
        0.025,
        parent=mast,
    )
    rope(
        "peak_halyard",
        [P(-0.1, 1.05, 15.95), P(0.84, -4.63, 15.63), P(-0.5, 1.1, 2.1)],
        0.026,
        parent=mast,
    )
    rope(
        "boom_topping_lift",
        [P(-0.3, 1.05, 15.9), P(1.65, -10.5, 3.9)],
        0.028,
        parent=boom,
    )
    rope(
        "main_sheet",
        [P(1.65, -10.5, 3.8), P(2.15, -9.6, float(DECK.heights(2.15, -9.6)) + 0.88)],
        0.034,
        parent=boom,
    )
    for side in (-1, 1):
        svals = (0.3, -0.8, -1.9)
        feet = []
        for j, s in enumerate(svals):
            x = side * (float(DECK.width(s)) + 0.3)
            z = float(DECK.heights(x, s)) + 0.45
            foot = P(x, s, z)
            feet.append(foot)
            rope(
                "shroud_" + str(side) + "_" + str(j),
                [P(side * 0.12, 1.05, 14.85), foot],
                0.055,
                True,
                mast,
            )
            tube(
                "chainplate",
                [foot - Vector((0, 0, 0.35)), foot - Vector((0, 0, 1.15))],
                0.065,
                M["iron"],
            )
            for h in (0, -0.25):
                tube(
                    "deadeye",
                    [foot + Vector((0, -0.055, h)), foot + Vector((0, 0.055, h))],
                    0.19,
                    M["wood_dark"],
                    sides=12,
                )
            for ds in (-0.05, 0.05):
                rope(
                    "deadeye_lanyard",
                    [foot + Vector((ds, 0, 0)), foot + Vector((ds, 0, -0.26))],
                    0.015,
                    True,
                )
        for j, z in enumerate(np.arange(2.5, 13.6, 0.36)):
            t = (z - feet[0].z) / (14.85 - feet[0].z)
            pts = [p.lerp(P(side * 0.12, 1.05, 14.85), t) for p in feet]
            rope("ratline_" + str(side) + "_" + str(j), pts, 0.012, True, mast)
        x = side * (float(DECK.width(-4.0)) - 0.035)
        z = float(DECK.heights(x, -4)) + 0.78
        rope(
            "backstay_" + str(side),
            [P(side * 0.12, 1.05, 15.95), P(x, -4, z)],
            0.045,
            True,
            mast,
        )
        rope(
            "bowsprit_side_stay_" + str(side),
            [
                P(0, 14.275, 6.85),
                P(
                    side * (float(DECK.width(8.0)) - 0.05),
                    8.0,
                    float(DECK.heights(float(DECK.width(8.0)) - 0.05, 8.0)) + 0.78,
                ),
            ],
            0.04,
            True,
            bowsprit,
        )
        rope(
            "bobstay_" + str(side),
            [P(side * 0.08, 14.275, 6.8), P(side * 0.08, 10.9, 0.2)],
            0.05,
            True,
            bowsprit,
        )
        x = side * (float(DECK.width(-0.8)) + 0.17)
        z = float(DECK.heights(x, -0.8)) + 0.35
        box("shroud_channel", P(x, -0.8, z), (0.52, 3.4, 0.15), M["wood_dark"])
    workstation("jib_sheets", 2.25, 7.9, "jib_sheets")
    return mast, boom, gaff


def headroom():
    result = {
        "threshold_m": 2.2,
        "scope": "Canvas and boom above the authored working-deck footprint, nine sampled cloth-loop frames; excludes bowsprit outside the deck and designated nonwalkable cabin roof.",
        "frames": [],
    }
    for frame in range(0, 97, 12):
        bpy.context.scene.frame_set(frame)
        dg = bpy.context.evaluated_depsgraph_get()
        mins = {}
        for o in bpy.data.objects:
            if o.type != "MESH" or not (
                o.name.endswith("_set") or o.name == "boom_timber"
            ):
                continue
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            vals = []
            for v in me.vertices:
                p = o.matrix_world @ v.co
                x, s, z = p.x, -p.y, p.z
                if DECK.ss[0] < s < DECK.ss[-1] and abs(x) < DECK.width(s) - 0.1:
                    vals.append(z - float(DECK.heights(x, s)))
            ev.to_mesh_clear()
            if vals:
                mins[o.name] = round(min(vals), 4)
        result["frames"].append({"frame": frame, "min_clearance_by_object_m": mins})
    result["minimum_m"] = min(
        v for r in result["frames"] for v in r["min_clearance_by_object_m"].values()
    )
    result["passed"] = result["minimum_m"] >= 2.2
    bpy.context.scene.frame_set(0)
    return result


def deck_access():
    from collections import deque

    radius = 0.28
    step = 0.15
    obstacles = [
        *OBSTACLES,
        {"id": "mast", "x": 0, "s": 1.05, "width": 0.50, "length": 0.50, "height": 16},
    ]

    def free(x, s):
        if (
            not DECK.ss[0] + radius < s < DECK.ss[-1] - radius
            or abs(x) > float(DECK.width(s)) - 0.40
        ):
            return False
        return not any(
            abs(x - o["x"]) < o["width"] / 2 + radius
            and abs(s - o["s"]) < o["length"] / 2 + radius
            for o in obstacles
        )

    grid = {
        (i, j)
        for i in range(-22, 23)
        for j in range(-72, 73)
        if free(i * step, j * step)
    }

    def nearest(station):
        x, _, s = station["position_gltf_m"]
        assert free(x, s), ("Station obstructed or off deck", station["id"], x, s)
        return min(grid, key=lambda k: (k[0] * step - x) ** 2 + (k[1] * step - s) ** 2)

    start = nearest(STATIONS[0])
    visited = {start}
    queue = deque([start])
    while queue:
        i, j = queue.popleft()
        for p in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
            if p in grid and p not in visited:
                visited.add(p)
                queue.append(p)
    result = {
        "scope": "Plan-view connectivity on the closed working deck; closed hatches are walkable 0.185 m steps. No engine navmesh or dynamic obstacles.",
        "crew_radius_m": radius,
        "grid_spacing_m": step,
        "reachable_grid_cells": len(visited),
        "stations": {st["id"]: nearest(st) in visited for st in STATIONS},
    }
    result["passed"] = all(result["stations"].values())
    assert result["passed"], result
    return result


def sail_measurements():
    records = []
    for obj in G.ASSET.objects:
        if obj.type != "MESH" or not obj.name.endswith("_set"):
            continue
        obj.data.calc_loop_triangles()
        area = projected = 0.0
        centroid = Vector((0, 0, 0))
        for tri in obj.data.loop_triangles:
            a, b, c = [obj.matrix_world @ obj.data.vertices[i].co for i in tri.vertices]
            cross = (b - a).cross(c - a)
            area += cross.length / 2
            w = abs(cross.x) / 2
            projected += w
            centroid += (a + b + c) / 3 * w
        centroid /= projected
        records.append(
            {
                "name": obj.name,
                "surface_area_m2": round(area, 3),
                "side_projection_area_m2": round(projected, 3),
                "side_projection_centroid_gltf_m": [
                    round(centroid.x, 3),
                    round(centroid.z, 3),
                    round(-centroid.y, 3),
                ],
            }
        )
    return {
        "status": "Geometric measurements of authored pose, not aerodynamic forces or certified sail balance",
        "sails": records,
        "total_surface_area_m2": round(sum(x["surface_area_m2"] for x in records), 3),
    }


def make_lod(objects, level):
    copies = []
    for o in objects:
        if o.type != "MESH":
            continue
        if any(m and m.name.startswith("flax_") for m in o.data.materials):
            c = o.copy()
            c.data = o.data.copy()
            c.data.shape_keys.animation_data_clear() if c.data.shape_keys else None
        else:
            if level == 2 and any(
                t in o.name
                for t in ("ratline", "lacing", "coil", "lanyard", "hank", "pin", "hoop")
            ):
                continue
            c = o.copy()
            c.data = o.data.copy()
        G.ASSET.objects.link(c)
        c.parent = None
        c.matrix_world = o.matrix_world
        c.name = "LOD" + str(level) + "_" + o.name
        if c.data.shape_keys:
            for k in c.data.shape_keys.key_blocks:
                k.value = 0
            c.shape_key_clear()
        if (
            not any(
                m and m.name.startswith(("rope_", "flax_")) for m in c.data.materials
            )
            and len(c.data.polygons) > 80
        ):
            mod = c.modifiers.new("reduce", "DECIMATE")
            mod.ratio = 0.55 if level == 1 else 0.27
            with bpy.context.temp_override(object=c, active_object=c):
                bpy.ops.object.modifier_apply(modifier=mod.name)
        copies.append(c)
    # Merge static geometry to a single mesh; material slots retain audit provenance.
    bpy.ops.object.select_all(action="DESELECT")
    for c in copies:
        c.select_set(True)
    bpy.context.view_layer.objects.active = copies[0]
    bpy.ops.object.join()
    joined = bpy.context.object
    joined.name = "sloop_lod" + str(level)
    G.export_glb(OUT / ("sloop_1715_lod" + str(level) + ".glb"), [joined])
    n = G.triangles([joined])
    bpy.data.objects.remove(joined, do_unlink=True)
    return n


def collisions():
    col = bpy.data.collections.new("COLLISION_ONLY")
    bpy.context.scene.collection.children.link(col)
    objects = []
    for s in np.linspace(float(DECK.ss[0]) + 1, float(DECK.ss[-1]) - 1, 12):
        w = float(DECK.width(s))
        z = float(DECK.heights(0, s))
        objects.append(
            box(
                "UCX_deck",
                P(0, s, z - 0.12),
                (max(0.3, w * 2 - 0.18), 1.65, 0.23),
                M["collision"],
            )
        )
    for item in OBSTACLES:
        x, s = item["x"], item["s"]
        objects.append(
            box(
                "UCX_" + item["id"],
                P(x, s, float(DECK.heights(x, s)) + item["height"] / 2),
                (item["width"], item["length"], item["height"]),
                M["collision"],
            )
        )
    # Bulwarks retain their open gunports. Mast has a separate simple collider.
    wall = bpy.data.objects["merchant_teal_bulwarks"]
    wc = bpy.data.objects.new("COLLIDER_static_bulwarks", wall.data.copy())
    G.ASSET.objects.link(wc)
    objects.append(wc)
    wc.data.materials.clear()
    wc.data.materials.append(M["collision"])
    objects.append(box("UCX_mast", P(0, 1.05, 3.0), (0.50, 0.50, 5.0), M["collision"]))
    # Coarse hull is a decimated copy, intended as a static concave mesh collider.
    h = bpy.data.objects["sloop_hull_closed"]
    c = bpy.data.objects.new("COLLIDER_static_hull", h.data.copy())
    G.ASSET.objects.link(c)
    objects.append(c)
    c.data.materials.clear()
    c.data.materials.append(M["collision"])
    for poly in c.data.polygons:
        poly.material_index = 0
    mod = c.modifiers.new("coarse", "DECIMATE")
    mod.ratio = 0.07
    with bpy.context.temp_override(object=c, active_object=c):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    for o in objects:
        G.ASSET.objects.unlink(o)
        col.objects.link(o)
        o["collider_type"] = "static_concave_mesh" if o in (c, wc) else "box"
    G.export_glb(OUT / "sloop_1715_collision.glb", objects)
    n = len(objects)
    for o in objects:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(col)
    return n


def main():
    global OUT, M
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build/sloop_1715")
    ap.add_argument("--no-render", action="store_true")
    args = ap.parse_args(
        sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    )
    OUT = Path(args.out).resolve()
    (OUT / "textures").mkdir(parents=True, exist_ok=True)
    (OUT / "previews").mkdir(exist_ok=True)
    G.OUT = OUT
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(ROOT / "model/snow.glb"))
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    G.ASSET = bpy.data.collections.new("SLOOP_GAME_ASSET")
    bpy.context.scene.collection.children.link(G.ASSET)
    G.PRESENTATION = bpy.data.collections.new("PRESENTATION_ONLY")
    bpy.context.scene.collection.children.link(G.PRESENTATION)
    M = {
        n: bpy.data.materials[n]
        for n in (
            "wood",
            "wood_dark",
            "wood_black",
            "side_oiled_oak",
            "deck_planking",
            "iron",
            "iron_gun_barrel",
            "bronze",
            "bottom_white_stuff",
            "carriage_red_ochre",
            "paint_ochre",
            "rope_tarred",
            "rope_untarred",
        )
    }
    M["paint_merchant_teal"] = plain("paint_merchant_teal", (0.025, 0.13, 0.15))
    M["glass_sloop"] = plain("glass_sloop", (0.035, 0.10, 0.13), 0.3, 0.22)
    M["collision"] = plain("collision", (0.1, 0.4, 0.1))
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    scene.render.fps = 24
    scene.frame_start = 0
    scene.frame_end = 96
    hull_report = hull()
    deck_fittings()
    guns()
    rudder()
    rig()
    bpy.context.view_layer.update()
    scene.frame_set(0)
    write("deck_access.json", deck_access())
    for o in G.ASSET.objects:
        if o.type == "MESH" and o.name not in (
            "sloop_hull_closed",
            "merchant_teal_bulwarks",
        ):
            # Recalculate consistently for robust lighting of generated primitives.
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
            bm.to_mesh(o.data)
            bm.free()
    report = audit_scene()
    write("rigging_collisions.json", report)
    print("RIGGING_RESULT", report["passed"], len(report["hits"]), flush=True)
    if not report["passed"]:
        raise RuntimeError("Canvas intersections; inspect rigging_collisions.json")
    clearance = headroom()
    write("deck_clearance.json", clearance)
    if not clearance["passed"]:
        raise RuntimeError("Insufficient canvas/boom headroom")
    write("sail_measurements.json", sail_measurements())
    write(
        "parameters.json",
        {
            "units": "metres, degrees",
            "coordinate_system": "glTF +X port, +Y up, +Z bow; design s is forward",
            "deck_length_m": 21.0,
            "beam_m": 6.45,
            "rabbet_depth_midship_m": 2.47,
            "mast_lower_length_m": 17.84,
            "mast_s_m": 1.05,
            "mast_head_above_water_m": 16.0,
            "mast_diameter_at_partners_m": 0.496,
            "gaff_angle_deg": 38.0,
            "sail_count": 3,
            "gun_count": 4,
            "historical_basis": "Illustrative chapter A sloop circa 1715. Four-gun merchant armament, reduced raised cloth outlines and flat working deck are game-design choices. No optional topmast fitted.",
        },
    )
    objects = list(G.ASSET.objects)
    n0 = G.triangles(objects)
    G.export_glb(OUT / "sloop_1715.glb", objects, True)
    n1 = make_lod(objects, 1)
    n2 = make_lod(objects, 2)
    nc = collisions()
    write(
        "workstations.json",
        {
            "coordinate_system": "glTF +X port, +Y up, +Z bow; metres",
            "stations": STATIONS,
        },
    )
    write(
        "rigging_paths.json",
        {
            "coordinate_system": "glTF metres",
            "default_pose_only": True,
            "paths": list(G.RIGGING_PATHS.values()),
        },
    )
    write(
        "deck_layout.json",
        {
            "obstacles": OBSTACLES,
            "closed_hatches_step_height_m": 0.185,
            "clear_side_passages": "authoring intent; no navmesh included",
        },
    )
    write(
        "asset_manifest.json",
        {
            "name": "Jaskolka - inferred merchant sloop circa 1715",
            "historical_status": "Illustrative reconstruction, not a documented vessel or certified sailing design",
            "basis": "docs/pl/12-designing-other-ships.md chapter A revised sloop; main reference hull offset family and CC0 materials",
            "deck": hull_report,
            "mast_count": 1,
            "sail_count": 3,
            "gun_count": 4,
            "armament": "Four illustrative 3-pounders, merchant variant",
            "triangles": {"lod0": n0, "lod1": n1, "lod2": n2},
            "collision_objects": nc,
            "source_file_sha256": source_hashes(ROOT),
            "controls": [{"name": o.name, **dict(o.items())} for o in CONTROLS],
            "animation": "Pinned-edge cloth wind loop, 4 seconds at 24 fps; LODs static",
            "limits": "Only authored sailing pose and wind morph loop audited; rotating spars requires runtime rig/rope solution. No flotation, navigation, damage or engine controller included.",
        },
    )
    # Keep only used PBR images; every retained image is packed in the blend.
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    for im in bpy.data.images:
        if im.source == "FILE" and not im.packed_file:
            try:
                im.pack()
            except RuntimeError:
                pass
    if not args.no_render:
        G.render_setup()
    scene.frame_set(0)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "sloop_1715.blend"))
    shutil.copy(
        ROOT / "blender/tekstury_cc0_spis.json", OUT / "texture_provenance.json"
    )
    shutil.copy(ROOT / "LICENSE", OUT / "LICENSE")
    for f in Path(__file__).resolve().parent.glob("*.py"):
        (OUT / "source").mkdir(exist_ok=True)
        shutil.copy(f, OUT / "source" / f.name)
    write(
        "build_summary.json",
        {
            "hull": hull_report,
            "triangles": [n0, n1, n2],
            "collision_objects": nc,
            "rope_canvas_passed": report["passed"],
            "minimum_canvas_boom_clearance_m": clearance["minimum_m"],
        },
    )
    print("SLOOP_COMPLETE", OUT, flush=True)


if __name__ == "__main__":
    main()
