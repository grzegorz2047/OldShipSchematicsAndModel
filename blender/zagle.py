"""Żagle zwinięte (statek na kotwicy, rozdział 08 przewodnika: 'furled'): wałek płótna na wierzchu i z przodu rei, grubszy w środku
(bunt), z krawatami (gaskets) co ok. 1,1 m; obiekty 'zagiel_<reja>' są dziećmi rej (obracają się z nimi).
Żagiel gaflowy podgarnięty gejtawami do gafla i masztu snow, kliwer zwinięty na bomstendze, sztaksle opuszczone
na bukszpryt i u stopy fokmasztu.
"""
import math
import random

import numpy as np
from mathutils import Vector

import narzedzia as N
from narzedzia import P


RAD = {"": (0.30, 0.15), "mars": (0.25, 0.12), "bram": (0.16, 0.085), "blinda": (0.21, 0.11)}


def walek(sk, pts, radii, rng, mat="plotno", sides=12):
    path = [Vector(p) for p in pts]
    sc = [r / radii[0] for r in radii]
    tw = [rng.uniform(-0.25, 0.25) for _ in path]
    prof = [(radii[0] * math.cos(2 * math.pi * k / sides) * rng.uniform(0.86, 1.08),
             radii[0] * math.sin(2 * math.pi * k / sides) * rng.uniform(0.80, 1.05)) for k in range(sides)]
    N.sweep(sk, path, prof, mat, scale=sc, twist=tw, up=Vector((0, 0, 1)))


def _odcinki_sztagow(ctx):
    """Odcinki sztagów (Blender) z promieniem – wałki żagli zwiniętych omijają je (sztag przechodzi przed reją)."""
    if "_sztagi_odc" not in ctx:
        seg = []
        for L in ctx.get("liny", []):
            if L["g"] == "sztagi" and len(L["p"]) >= 2 and (L["p"][-1] - L["p"][0]).length > 2.0:
                for a, b in zip(L["p"][:-1], L["p"][1:]):
                    seg.append((Vector(a), Vector(b), L["d"] / 2))
        ctx["_sztagi_odc"] = seg
    return ctx["_sztagi_odc"]


def _odl_sztag(ctx, p):
    best, kier = 1e9, None
    if "_drzewca_bvh" not in ctx:
        import bpy
        from mathutils.bvhtree import BVHTree
        d = bpy.data.objects.get("drzewca")
        ctx["_drzewca_bvh"] = (BVHTree.FromObject(d, bpy.context.evaluated_depsgraph_get()), d.matrix_world.copy()) \
            if d else None
    if ctx["_drzewca_bvh"]:
        tr, M = ctx["_drzewca_bvh"]
        loc, nrm, _, dd = tr.find_nearest(M.inverted() @ p, 1.0)
        if loc is not None:
            q = M @ loc
            best, kier = (p - q).length, ((p - q).normalized() if (p - q).length > 1e-6 else Vector((0, 1, 0)))
    for a, b, r in _odcinki_sztagow(ctx):
        ab = b - a
        t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-9)))
        q = a + ab * t
        d = (p - q).length - r
        if d < best:
            best, kier = d, (p - q).normalized() if (p - q).length > 1e-6 else Vector((0, 1, 0))
    return best, kier


def omin_sztagi(ctx, pts, radii, luz=0.02, r_min=0.04):
    """Zmniejsza promień wałka przy sztagu (i odsuwa oś, gdy promień nie wystarcza)."""
    out_p, out_r = [], []
    for p, r in zip(pts, radii):
        p = Vector(p)
        d, kier = _odl_sztag(ctx, p)
        if d - luz < r:
            r2 = max(d - luz, r_min)
            if d - luz < r_min:
                p = p + kier * (r_min - (d - luz))
            r = r2
        out_p.append(p)
        out_r.append(r)
    return out_p, out_r


def na_drzewcu(ctx, pts, rr, up, nazwa="bukszpryt"):
    import bpy
    from mathutils.bvhtree import BVHTree
    ob = bpy.data.objects.get(nazwa)
    if ob is None:
        return pts
    tr = BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())
    Mi = ob.matrix_world.inverted()
    out = []
    for p, r in zip(pts, rr):
        p = Vector(p)
        o = p + Vector(up) * 1.5
        hit = tr.ray_cast(Mi @ o, (Mi.to_3x3() @ -Vector(up)).normalized(), 3.0)
        if hit[0] is not None:
            s = ob.matrix_world @ hit[0]
            p = s + Vector(up) * (r + 0.01)
        # luz od całej bryły drzewca (nie tylko pod środkiem wałka): najbliższy punkt powierzchni (bomstenga,
        # ezelhoft, nakładki) co najmniej r + 1 cm od osi wałka
        for _ in range(6):
            nr = tr.find_nearest(Mi @ p)
            if nr[0] is None:
                break
            dist = (ob.matrix_world @ nr[0] - p).length
            if dist >= r + 0.009:
                break
            p = p + Vector(up) * (r + 0.01 - dist + 0.002)
        out.append(p)
    return out


def na_rei(ctx, nam, Y, rng):
    c = Vector(Y["c"])
    h = Y["L"] / 2
    sr = Y["sr"]
    typ = "blinda" if nam == "blinda" else ("mars" if nam.endswith("mars") else ("bram" if nam.endswith("bram") else ""))
    rb, ra = RAD[typ]
    sk = N.Siatka("zagiel_" + nam)
    xs = np.linspace(-h * 0.86, h * 0.86, 43)
    radii, pts = [], []
    g0 = -h * 0.8
    for x in xs:
        # między krawatami (co 1,1 m) płótno zwisa i pęcznieje, przy krawacie jest ściśnięte
        ph = ((x - g0) % 1.1) / 1.1
        fald = math.sin(math.pi * ph)
        r = (ra + (rb - ra) * math.exp(-(x / (h * 0.28)) ** 2)) * (0.86 + 0.2 * fald) + rng.uniform(-0.015, 0.015)
        radii.append(r)
        # przy środku rei wałek (bunt) cofnięty ku rei: przed reją przechodzi sztag
        fw = (sr * 0.35 + r * 0.55) * (1.0 - 0.6 * math.exp(-(x / (h * 0.18)) ** 2))
        pts.append(c + Vector((x, -fw, sr * 0.3 + r * 0.62 - 0.05 * fald)))
    pts, radii = omin_sztagi(ctx, pts, radii)
    walek(sk, pts, radii, rng)
    # krawaty: płaskie pętle ciasno opasujące reję i wałek – obwiednia wypukła przekroju rei (promień sr/2) i wałka
    # w miejscu krawata (oś i promień wałka z pts/radii po ominięciu sztagów, z zapasem na nieregularny profil +8 %
    # i skręt); wcześniej elipsa liczona z sr jako promienia była kilka razy większa od żagla
    xs_w = np.array([p.x - c.x for p in pts])
    for x in np.arange(-h * 0.8, h * 0.81, 1.1):
        i = int(np.argmin(np.abs(xs_w - x)))
        pw, rw = pts[i], radii[i] * 1.12 + 0.012
        ry = sr / 2 + 0.012
        if _odl_sztag(ctx, Vector((c.x + x, pw.y, pw.z)))[0] < rw + 0.05:
            continue
        kola = [(c.y, c.z, ry), (pw.y, pw.z, rw)]
        pk = [(cy + rr * math.cos(t), cz + rr * math.sin(t)) for (cy, cz, rr) in kola
              for t in np.linspace(0, 2 * math.pi, 14, endpoint=False)]
        pk.sort()

        def _kr(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
        dol, gora = [], []
        for q in pk:                                         # obwiednia wypukła (łańcuch monotoniczny)
            while len(dol) >= 2 and _kr(dol[-2], dol[-1], q) <= 0:
                dol.pop()
            dol.append(q)
        for q in reversed(pk):
            while len(gora) >= 2 and _kr(gora[-2], gora[-1], q) <= 0:
                gora.pop()
            gora.append(q)
        hull = dol[:-1] + gora[:-1]
        loop = [Vector((c.x + x, qy, qz)) for (qy, qz) in hull]
        loop.append(loop[0])
        N.sweep(sk, loop, N.rect_prof(0.006, 0.035), "lina_jasna", cap0=False, cap1=False)
    ob = N.to_object(sk, ctx["kol"]["zagle_zwiniete"], recalc=True)
    ob.data.polygons.foreach_set("use_smooth", [True] * len(ob.data.polygons))
    ob.data.set_sharp_from_angle(angle=math.radians(75))
    ob.parent = Y["obj"]
    ob.matrix_parent_inverse = Y["obj"].matrix_world.inverted()
    return ob


def zbuduj(ctx):
    rng = random.Random(7)
    rig = ctx["rig"]
    for nam, Y in rig["reje"].items():
        if nam in ("gafel", "bom"):
            continue
        na_rei(ctx, nam, Y, rng)
    # żagiel gaflowy: podgarnięty do gafla i masztu snow
    if "gafel" in rig["reje"]:
        gf = rig["reje"]["gafel"]
        sk = N.Siatka("zagiel_gaflowy")
        jaw, peak = Vector(gf["c"]), Vector(gf["end"])
        pts, rr = [], []
        for t in np.linspace(0.02, 0.92, 14):
            r = 0.2 * (1 - 0.55 * t) + rng.uniform(-0.01, 0.01)
            pts.append(jaw.lerp(peak, t) + Vector((0, 0, -0.08 - r)))
            rr.append(r)
        walek(sk, pts, rr, rng)
        if ctx["snow"]:
            sn = rig["snow"]
            zt = jaw.z - 0.4
            zb = rig["reje"]["bom"]["c"].z + 0.5 if "bom" in rig["reje"] else sn["z0"] + 2.0
            pts, rr = [], []
            for z in np.linspace(zt, zb, 10):
                r = 0.17 + 0.05 * math.sin((z - zb) / (zt - zb) * math.pi) + rng.uniform(-0.01, 0.01)
                s_ = sn["s"] - (z - sn["z0"]) * sn["t"] - sn["r"] - r * 0.8
                pts.append(P(0, s_, z))
                rr.append(r)
            walek(sk, pts, rr, rng)
        N.to_object(sk, ctx["kol"]["zagle_zwiniete"])
    # kliwer na bomstendze, sztaksel stengowy foka na bukszprycie, grotsztaksel u stopy fokmasztu
    bs = rig["bukszpryt"]
    sk = N.Siatka("zagle_sztakslowe")
    j0, j1 = bs["j0"], bs["j1"]
    d = (j1 - j0).normalized()
    pts, rr = [], []
    for t in np.linspace(0.45, 0.93, 10):
        r = 0.13 * (1 - 0.4 * abs(t - 0.6)) + rng.uniform(-0.008, 0.008)
        pts.append(j0.lerp(j1, t) + bs["up3"] * (r + 0.07))
        rr.append(r)
    pts = na_drzewcu(ctx, pts, rr, bs["up3"])
    walek(sk, pts, rr, rng)
    path = bs["path"]
    pts, rr = [], []
    for t in np.linspace(0.5, 0.66, 7):
        i = t * (len(path) - 1)
        p = path[int(i)].lerp(path[min(int(i) + 1, len(path) - 1)], i - int(i))
        r = 0.2 + rng.uniform(-0.01, 0.01)
        sc_ = bs["sc"][min(int(i), len(bs["sc"]) - 1)]
        pts.append(p + bs["up3"] * (bs["r0"] * sc_ + r + 0.01))
        rr.append(r)
    pts = na_drzewcu(ctx, pts, rr, bs["up3"])
    walek(sk, pts, rr, rng)
    F, G = rig["maszty"]["fok"], rig["maszty"]["grot"]
    a = G["m"].p(G["m"].z_top + 0.25)
    b = F["m"].p(F["m"].z_d + 0.55, ds=-(F["m"].r(F["m"].z_d) + 0.25))
    pts, rr = [], []
    for t in np.linspace(0.70, 0.82, 6):
        r = 0.18 + rng.uniform(-0.01, 0.01)
        pts.append(a.lerp(b, t) + Vector((0, 0, -r * 0.8)))
        rr.append(r)
    walek(sk, pts, rr, rng)
    N.to_object(sk, ctx["kol"]["zagle_zwiniete"])
