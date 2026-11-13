"""Pokład i nadburcia: pokrywa relingu z profilem, ściek, wierzchołki wręgów od środka, listwy, szpigaty,
pokrywy furt (osobne obiekty, oś w zawiasie), schody na pokład rufowy, balustrada progu, drzwi kabiny.
"""
import math

import numpy as np
from mathutils import Matrix, Vector

import narzedzia as N
from narzedzia import P
from materialy import region as R


def _plan_normal(xs, ss):
    dx = np.gradient(xs)
    ds = np.gradient(ss)
    l = np.sqrt(dx * dx + ds * ds) + 1e-12
    nx, ns = ds / l, -dx / l
    flip = nx < 0
    nx[flip] *= -1
    ns[flip] *= -1
    return nx, ns, dx / l, ds / l


def inner_at(ps, r, s):
    """Punkt nadburcia od środka (lewa burta) w rzędzie r na długości s → (x, s, z) i wektory: do środka (mx, ms),
    wzdłuż (tx, ts)."""
    c1 = ps.c_in1
    xs, ss, zs = ps.xin[r, :c1 + 1], ps.sin[r, :c1 + 1], ps.zin[r, :c1 + 1]
    x = float(np.interp(s, ss, xs))
    z = float(np.interp(s, ss, zs))
    nx, ns, tx, ts = _plan_normal(xs, ss)
    return (x, s, z), (-float(np.interp(s, ss, nx)), -float(np.interp(s, ss, ns))), \
        (float(np.interp(s, ss, tx)), float(np.interp(s, ss, ts)))


def profile_sweep(sk, pts, inward, prof, mat, closed=True, side=1, caps=True, up=(0, 0, 1)):
    """Profil (w, h) przeciągnięty wzdłuż punktów pts (x, s, z) lewej burty: w – w głąb (wektor inward[i] w rzucie
    (mx, ms)), h – w górę. side=-1 – lustro na prawą burtę."""
    n = len(pts)
    rings = []
    L = [0.0]
    for i in range(1, n):
        L.append(L[-1] + math.dist(pts[i], pts[i - 1]))
    for i in range(n):
        x, s, z = pts[i]
        mx, ms = inward[i]
        ring = []
        for (w, h) in prof:
            ring.append(P(side * (x + mx * w), s + ms * w, z + h))
        rings.append(sk.verts(ring))
    m = len(prof)
    per = [0.0]
    for j in range(1, m + 1):
        a, b = prof[(j - 1) % m], prof[j % m]
        per.append(per[-1] + math.hypot(a[0] - b[0], a[1] - b[1]))
    for i in range(n - 1):
        for j in range(m if closed else m - 1):
            j2 = (j + 1) % m
            q = [rings[i][j], rings[i + 1][j], rings[i + 1][j2], rings[i][j2]]
            uv = [(L[i], per[j]), (L[i + 1], per[j]), (L[i + 1], per[j + 1]), (L[i], per[j + 1])]
            if side < 0:
                q, uv = q[::-1], uv[::-1]
            sk.face(q, uv, mat)
    if closed and caps:
        c0 = list(reversed(rings[0])) if side > 0 else list(rings[0])
        c1 = list(rings[-1]) if side > 0 else list(reversed(rings[-1]))
        sk.face_proj(c0, mat, flat=True)
        sk.face_proj(c1, mat, flat=True)
    return rings


def reling(ctx, ps):
    """Pokrywa relingu wzdłuż górnej krawędzi poszycia (obie burty i pawęż)."""
    K = ctx["K"]
    sk = N.Siatka("kadlub_reling")
    rt = ps.r_top
    xs, ss, zs = ps.X[rt], ps.Ss[rt], ps.Z[rt]
    nx, ns, _, _ = _plan_normal(xs, ss)
    w = K["RELING_SZER"]
    prof = [(-0.045, -0.035), (-0.045, 0.028), (-0.022, K["RELING_GR"] - 0.005), (w - 0.03, K["RELING_GR"] - 0.005),
            (w - 0.01, 0.035), (w - 0.01, -0.035)]
    # przy dziobnicy pokrywy obu burt schodzą się – skracam do kolumny, gdzie półszerokość > 0,25 m
    cend = len(xs) - 1
    while xs[cend] < 0.25 + w * 0.5:
        cend -= 1
    pts = [(xs[c], ss[c], zs[c]) for c in range(cend + 1)]
    inward = [(-nx[c], -ns[c]) for c in range(cend + 1)]
    for side in (1, -1):
        profile_sweep(sk, pts, inward, prof, R("reling"), side=side)
    # pawęż (taffrail): wzdłuż górnego rzędu rufy, do środka = ku dziobowi
    rz = ctx["rufa_rzedy"][rt]
    z_end, s_end, x_end, bul = rz
    pts, inward = [], []
    for k in range(17):
        t = 1 - 2 * k / 16
        pts.append((x_end * t, s_end - bul * (1 - t * t), z_end))
        inward.append((0.0, 1.0))
    profile_sweep(sk, pts, inward, prof, R("reling"), side=1)
    ob = N.to_object(sk, ctx["kol"]["kadlub"], recalc=True)
    ob.data.set_sharp_from_angle(angle=math.radians(35))
    return ob


def sciek_i_wregi(ctx, ps):
    K = ctx["K"]
    sk = N.Siatka("kadlub_sciek_wregi")
    ww, wh = K["WODOSCIEK"]
    prof = [(-0.02, -0.012), (ww, -0.012), (ww, 0.01), (ww * 0.62, 0.03), (ww * 0.3, 0.06), (0.06, wh - 0.01),
            (-0.02, wh)]
    for (r, c0, c1) in ((ps.r_deck, ps.c_qd, ps.c_in1), (ps.r_qd, 0, ps.c_qd)):
        xs, ss, zs = ps.xin[r, c0:c1 + 1], ps.sin[r, c0:c1 + 1], ps.zin[r, c0:c1 + 1]
        nx, ns, _, _ = _plan_normal(xs, ss)
        pts = [(xs[i], ss[i], zs[i]) for i in range(len(xs))]
        inward = [(-nx[i], -ns[i]) for i in range(len(xs))]
        for side in (1, -1):
            profile_sweep(sk, pts, inward, prof, "poklad", side=side)
    # wierzchołki wręgów od środka nadburcia
    pw, pd = K["PILERS"]
    sp = K["PILERS_ROZSTAW"]
    hw = K["FURTA_SZER"] / 2
    ports = list(K["FURTY_S"])
    s_lo = ps.sin[ps.r_qd, 0] + 0.25
    s_hi = ps.sin[ps.r_deck, ps.c_in1] - 0.2
    pos = []
    s = s_lo
    while s < s_hi:
        if not any(abs(s - p0) < hw + 0.42 for p0 in ports):
            pos.append(s)
        s += sp
    for p0 in ports:
        pos += [p0 - hw - 0.32, p0 + hw + 0.32]          # laweta z kołami mieści się między nimi
    pos = sorted(p for p in pos if abs(p - K["POLPOKLAD_S"]) > 0.14)
    ctx["wregi_nadburcia_s"] = pos
    for s in pos:
        r_bot = ps.r_qd if s < K["POLPOKLAD_S"] else ps.r_deck
        (xb, _, zb), (mx, ms), (tx, ts) = inner_at(ps, r_bot, s)
        (xt, _, zt), (mx2, ms2), _ = inner_at(ps, ps.r_top, s)
        zt -= 0.025                       # 1 cm w pokrywie relingu (zakryte)
        zb -= 0.05                        # 5 cm w pokładzie / ścieku (zakryte), bez ściętego końca w powietrzu
        for side in (1, -1):
            corners = []
            for (xx, zz, mxx, mss) in ((xb, zb, mx, ms), (xt, zt, mx2, ms2)):
                for (a, b) in ((-pw / 2, -0.012), (pw / 2, -0.012), (pw / 2, pd), (-pw / 2, pd)):
                    corners.append(P(side * (xx + tx * a + mxx * b), s + ts * a + mss * b, zz))
            v = sk.verts(corners)
            for q in ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
                qq = [v[i] for i in q]
                sk.face_proj(qq if side > 0 else qq[::-1], "drewno", flat=True, rot=math.pi / 2)
    ob = N.to_object(sk, ctx["kol"]["kadlub"], recalc=True)
    ob.data.set_sharp_from_angle(angle=math.radians(35))
    return ob


def listwy_i_szpigaty(ctx, ps):
    """Listwa pod relingiem, listwa na wysokości pokładu rufowego, ołowiane szpigaty."""
    kd, K = ctx["kd"], ctx["K"]
    sk = N.Siatka("kadlub_listwy")
    prof = [(0.005, -0.045), (-0.03, -0.035), (-0.042, 0.0), (-0.03, 0.035), (0.005, 0.045)]   # w < 0 = na zewnątrz

    def run(z_of_s, s0, s1, step=0.25):
        ss = list(np.arange(s0, s1, step)) + [s1]
        pts, inw = [], []
        for s in ss:
            z = z_of_s(s)
            x, (nx, ns) = ps.outer(s, z)
            pts.append((x, s, z))
            inw.append((-nx, -ns))
        for side in (1, -1):
            profile_sweep(sk, pts, inw, prof, R("listwa"), side=side)
    a_top = ps.ra[ps.r_top] + 0.12
    f_top = ps.rf[ps.r_top] - 0.6
    run(lambda s: ps.rail_top(s) - 0.13, a_top, f_top)
    run(lambda s: float(ps.Zd(s)) + K["POLPOKLAD_H"] - 0.06, ps.ra[ps.r_qd] + 0.12, K["POLPOKLAD_S"] - 0.05)
    # szpigaty: ołowiane rynienki tuż pod linią pokładu, między furtami
    ports = sorted(K["FURTY_S"])
    sc = [(a + b) / 2 for a, b in zip(ports[:-1], ports[1:])] + [ports[0] - 1.0, ports[-1] + 1.1]
    ctx["szpigaty_s"] = sc
    for s in sc:
        z = float(ps.Zd(s)) - 0.07
        x, (nx, ns) = ps.outer(s, z)
        x += 0.06 * nx
        for side in (1, -1):
            N.box(sk, P(side * (x + 0.03), s, z), (0.06, 0.16, 0.08), "zelazo")
    ob = N.to_object(sk, ctx["kol"]["kadlub"], recalc=True)
    ob.data.set_sharp_from_angle(angle=math.radians(35))
    return ob


def pokrywy_furt(ctx, ps):
    """Pokrywy furt: osobne obiekty, oś obrotu w zawiasie nad furtą (lokalna Z wzdłuż burty, dodatni obrót
    otwiera na zewnątrz i w górę). Najbardziej rufowa furta (pod pokładem rufowym) zamknięta, bez otworu."""
    kd, K = ctx["kd"], ctx["K"]
    hw = K["FURTA_SZER"] / 2 + 0.035
    lids = []
    kat = math.radians(K["POKRYWA_KAT"])
    allp = [(s, True) for s in K["FURTY_S"]] + [(s, False) for s in K.get("FURTY_ZAMKNIETE_S", [])]
    allp.sort()
    for idx, (s0, otwarta) in enumerate(allp):
        z_sill = float(ps.Zd(s0)) + K["FURTA_PROG"] - 0.035
        z_lin = float(ps.Zd(s0)) + K["FURTA_NADPROZE"] + 0.035
        for side, tag in ((1, "L"), (-1, "P")):
            sk = N.Siatka("furta_pokrywa_%s%d" % (tag, idx + 1))
            # pokrywa gięta jak burta: siatka 5 (wzdłuż) × 4 (w pionie) na zewnętrznej powierzchni, grubość 0,07
            NS, NZ = 5, 4
            gi, go = [], []
            for iz in range(NZ):
                z = z_sill + (z_lin - z_sill) * iz / (NZ - 1)
                ri, ro = [], []
                for is_ in range(NS):
                    s_ = s0 - hw + 2 * hw * is_ / (NS - 1)
                    x, (nx, ns) = ps.outer(s_, z)
                    ri.append(sk.vert(P(side * (x + nx * 0.006), s_ + ns * 0.006, z)))
                    ro.append(sk.vert(P(side * (x + nx * 0.077), s_ + ns * 0.077, z)))
                gi.append(ri)
                go.append(ro)
            fl = side < 0
            for iz in range(NZ - 1):
                for is_ in range(NS - 1):
                    qo = [go[iz][is_], go[iz][is_ + 1], go[iz + 1][is_ + 1], go[iz + 1][is_]]
                    qi = [gi[iz + 1][is_], gi[iz + 1][is_ + 1], gi[iz][is_ + 1], gi[iz][is_]]
                    sk.face_proj(qo[::-1] if fl else qo, R("pokrywa_zew"), axis=0)
                    sk.face_proj(qi[::-1] if fl else qi, R("pokrywa_wew"), axis=0)
            ring_i = gi[0] + [gi[iz][-1] for iz in range(1, NZ)] + gi[-1][::-1][1:] + [gi[iz][0] for iz in range(NZ - 2, 0, -1)]
            ring_o = go[0] + [go[iz][-1] for iz in range(1, NZ)] + go[-1][::-1][1:] + [go[iz][0] for iz in range(NZ - 2, 0, -1)]
            for k in range(len(ring_i)):
                k2 = (k + 1) % len(ring_i)
                q = [ring_i[k], ring_i[k2], ring_o[k2], ring_o[k]]
                sk.face_proj(q[::-1] if fl else q, R("pokrywa_zew"), flat=True)
            # zawiasy (taśmy żelazne) na zewnątrz, ucho z linką
            for ds in (-hw * 0.55, hw * 0.55):
                xa, (nx, ns) = ps.outer(s0 + ds, z_lin - 0.2)
                N.box(sk, P(side * (xa + nx * 0.085), s0 + ds, z_lin - 0.2), (0.02, 0.05, 0.42), "zelazo")
            xa, (nx, ns) = ps.outer(s0, z_sill + 0.12)
            N.cylinder(sk, P(side * (xa + nx * 0.08), s0, z_sill + 0.12), P(side * (xa + nx * 0.12), s0, z_sill + 0.12),
                       0.02, 0.02, "zelazo", sides=8)
            ob = N.to_object(sk, ctx["kol"]["kadlub"], recalc=True)
            # oś: górna krawędź, zewnętrzna strona; lokalna Z ku dziobowi (lewa) / ku rufie (prawa)
            xh, (nx, ns) = ps.outer(s0, z_lin)
            pivot = P(side * (xh + nx * 0.075), s0 + ns * 0.075, z_lin)
            zdir = P(0, side * 1.0, 0) - P(0, 0, 0)
            N.ustaw_os(ob, pivot, zdir, Vector((0, 0, -1)))
            if otwarta:
                ob.matrix_world = ob.matrix_world @ Matrix.Rotation(kat, 4, "Z")
            ob["otwarta"] = otwarta
            ob["zakres_deg"] = [0, 100]
            lids.append(ob)
    ctx["pokrywy"] = lids
    return lids


def schody_i_prog(ctx, ps):
    """Schody na pokład rufowy (środek progu), balustrada progu z tralkami, drzwi kabiny w grodzi."""
    kd, K = ctx["kd"], ctx["K"]
    sq = K["POLPOKLAD_S"]
    H = K["POLPOKLAD_H"]
    n = int(round(H / 0.19))
    rise = H / n
    run = 0.22          # stopnie 0,19 × 0,22 m: strome schody okrętowe (ok. 41°)
    w = 0.90
    sk = N.Siatka("schody_rufowe")
    zdeck = float(kd.deck_z(sq + 1.0, 0.0))
    zqd = float(kd.deck_z(sq - 0.2, 0.0)) + H
    rise = (zqd - zdeck) / n
    s_bot = sq + (n - 1) * run
    for j in range(1, n):
        ztop = zdeck + j * rise
        s_front = sq + (n - j) * run
        N.box(sk, P(0, s_front - run / 2 + 0.02, ztop - 0.03), (w - 0.1, run + 0.04, 0.06), "drewno")
    # policzki (stringery)
    for sx in (-w / 2 + 0.03, w / 2 - 0.03):
        a = P(sx, s_bot + run + 0.05, zdeck)
        b = P(sx, sq - 0.02, zqd)
        N.oriented_box(sk, a + Vector((0, 0, 0.1)), b + Vector((0, 0, 0.1)), 0.06, 0.26, "drewno",
                       up=Vector((0, 0, 1)))
    # poręcze na słupkach
    for sx in (-w / 2 - 0.02, w / 2 + 0.02):
        p_bot = P(sx, s_bot + run, zdeck + 0.95)
        p_top = P(sx, sq + 0.1, zqd + 0.9)
        N.cylinder(sk, p_bot, p_top, 0.03, 0.03, "drewno", sides=8)
        N.cylinder(sk, P(sx, s_bot + run, zdeck), p_bot, 0.04, 0.035, "drewno", sides=8)
    ctx["schody"] = dict(s_gora=sq, s_dol=s_bot + run, x0=-w / 2, x1=w / 2, z0=zdeck, z1=zqd, stopnie=n,
                         wznios=rise, glebokosc=run)
    ob_s = N.to_object(sk, ctx["kol"]["kadlub"], recalc=True)
    # balustrada progu: poręcz 0,9 m nad pokładem rufowym, tralki co 0,22 m, przerwa na schody
    sk = N.Siatka("balustrada_progu")
    (xi, _, zi), _, _ = inner_at(ps, ps.r_qd, sq - 0.08)
    s_r = sq - 0.08
    xs = [x for x in np.arange(-xi + 0.12, xi - 0.1, 0.22) if abs(x) > w / 2 + 0.06]
    for x in xs:
        zb = float(kd.deck_z(s_r, x)) + H
        prof = [(0.035, 0), (0.035, 0.08), (0.05, 0.12), (0.03, 0.2), (0.045, 0.42), (0.06, 0.55), (0.03, 0.7),
                (0.035, 0.78), (0.035, 0.84)]
        N.lathe(sk, prof, "drewno", P(x, s_r, zb), sides=8)
    for sgn in (1, -1):
        x0, x1 = sgn * (w / 2 + 0.06), sgn * (xi - 0.02)
        zb0 = float(kd.deck_z(s_r, x0)) + H
        zb1 = float(kd.deck_z(s_r, x1)) + H
        N.oriented_box(sk, P(x0, s_r, zb0 + 0.87), P(x1, s_r, zb1 + 0.87), 0.12, 0.07, "drewno")
        N.oriented_box(sk, P(x0, s_r, zb0 + 0.02), P(x1, s_r, zb1 + 0.02), 0.1, 0.05, "drewno")
        N.box(sk, P(x0, s_r, zb0 + 0.48), (0.12, 0.12, 0.96), "drewno")
    ob_b = N.to_object(sk, ctx["kol"]["kadlub"], recalc=True)
    # drzwi kabiny w grodzi progu (po obu stronach schodów): rama i płyciny
    sk = N.Siatka("grodz_drzwi")
    for x0 in (-1.25, 1.25):
        zb = float(kd.deck_z(sq + 0.02, x0))
        s_f = sq + 0.015
        N.box(sk, P(x0, s_f, zb + 0.78), (0.72, 0.04, 1.56), "drewno_ciemne")
        for (dx, dz, hh) in ((-0.16, 0.42, 0.62), (0.16, 0.42, 0.62), (-0.16, 1.15, 0.6), (0.16, 1.15, 0.6)):
            N.box(sk, P(x0 + dx, s_f + 0.02, zb + dz), (0.24, 0.02, hh), "drewno_ciemne")
        for dx in (-0.39, 0.39):
            N.box(sk, P(x0 + dx, s_f + 0.03, zb + 0.82), (0.08, 0.06, 1.64), "drewno")
        N.box(sk, P(x0, s_f + 0.03, zb + 1.62), (0.86, 0.06, 0.08), "drewno")
        N.cylinder(sk, P(x0 + 0.24, s_f + 0.03, zb + 0.95), P(x0 + 0.24, s_f + 0.08, zb + 0.95), 0.025, 0.025,
                   "zelazo", sides=8)
    ob_d = N.to_object(sk, ctx["kol"]["kadlub"], recalc=True)
    ctx["drzwi_kabiny_x"] = (-1.25, 1.25)
    return ob_s, ob_b, ob_d


def zbuduj(ctx):
    ps = ctx["poszycie"]
    reling(ctx, ps)
    sciek_i_wregi(ctx, ps)
    listwy_i_szpigaty(ctx, ps)
    pokrywy_furt(ctx, ps)
    schody_i_prog(ctx, ps)
