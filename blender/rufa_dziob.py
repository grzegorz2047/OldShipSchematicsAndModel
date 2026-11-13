"""Rufa i dziób: okna kabiny w pawęży, listwy kontry i pawęży skrzydłowej, pilastry, tafla z kartuszem
i woluty, narożniki rufy, latarnia; kolano galionu, zwój (scroll), policzki, relingi galionu ze słupkami, kratownice,
knechty bukszprytu, kotbelki ze wspornikami, kluzy.

Pewność: kształty ozdób to moja interpretacja opisu z rozdziału 04 przewodnika (zwój jak na planie Swift 1721, płaska pawęż,
2–4 okna na slupie, płaskorzeźba zamiast galerii) – szczegóły snycerki przyjęte (źródła opisują tylko jej miejsca).
"""
import math

import numpy as np
from mathutils import Matrix, Vector

import narzedzia as N
from narzedzia import P
from materialy import region as R

GALION = dict(
    # kolano galionu: (z, wysunięcie przed lico dziobnicy)                                   rozdział 04: 1,5–2,0 m
    KOLANO=[(-1.3, 0.0), (-0.6, 0.12), (0.0, 0.30), (0.6, 0.58), (1.2, 0.93), (1.8, 1.30), (2.3, 1.58),
            (2.48, 1.50), (2.62, 1.0), (2.72, 0.35), (2.76, 0.0)],
    KOLANO_GR=0.24,
    OKNA_X=(-1.26, -0.42, 0.42, 1.26), OKNO=(0.54, 0.70), OKNO_Z=2.18,   # 4 okna kabiny (rozdział 04: 2–4)
    KOTBELKA_S=12.35, KOTBELKA_WYST=1.15, KOTBELKA_PRZEKR=0.25,           # rozdział 04
    # kluzy (rozdział 04: wysoko przy dziobnicy, pod kotbelką): nad górnym policzkiem galionu, który przechodzi pod
    # pierścieniem kluzy (przyjęte, żeby policzek nie przecinał otworu)
    KLUZA_S=13.05, KLUZA_Z=1.95, KLUZA_R=0.14,
)


# ---------------------------------------------------------------- pomocnicze: lico pawęży i dziobnicy
class Rufa:
    def __init__(self, ctx):
        kd, K = ctx["kd"], ctx["K"]
        rr = [r for r in ctx["rufa_rzedy"] if r[0] >= K["Z_PAWEZ_DOLNA"] - 1e-6]
        a = np.array(rr)
        self.z, self.s, self.x, self.b = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
        self.ztop = float(self.z[-1])

    def pt(self, x, z, out=0.0):
        """Punkt na licu pawęży (x, z) odsunięty o 'out' na zewnątrz (w tył)."""
        s_e = float(np.interp(z, self.z, self.s))
        x_e = float(np.interp(z, self.z, self.x))
        b = float(np.interp(z, self.z, self.b))
        t = max(-1.0, min(1.0, x / x_e))
        s = s_e - b * (1 - t * t)
        # normalna w rzucie: d s/d x = 2 b x / x_e²  → (x, s): n ∝ (−ds/dx·…)
        dsdx = 2 * b * x / (x_e * x_e)
        n = Vector((-dsdx, -1.0))
        n.normalize()
        return P(x + n.x * out, s + n.y * out, z)

    def half(self, z):
        return float(np.interp(z, self.z, self.x))


def stem_face(ctx):
    """Lico dziobnicy: funkcja z → s (przednia krawędź) i grubości."""
    K = ctx["K"]
    pts = np.array(N.catmull(K["DZIOB"], 12))
    out = []
    for i in range(len(pts)):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == len(pts) - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        t = t / np.linalg.norm(t)
        nrm = np.array([t[1], -t[0]])
        out.append(pts[i] + nrm * K["DZIOBNICA_GR"])
    out = np.array(out)
    o = np.argsort(out[:, 1])
    zz, ss = out[o, 1], out[o, 0]
    return lambda z: float(np.interp(z, zz, ss))


def _ring_sweep(sk, path, prof, mat, scale=None, caps=True):
    return N.sweep(sk, path, prof, mat, cap0=caps, cap1=caps, scale=scale)


# ---------------------------------------------------------------- rufa
def rufa(ctx):
    kd, K = ctx["kd"], ctx["K"]
    G = GALION
    rf = Rufa(ctx)
    sk = N.Siatka("rufa_pawez")
    skz = N.Siatka("rufa_rzezby")
    zwt, zc = K["Z_PAWEZ_DOLNA"], K["Z_NAWIS"]
    zqd = float(kd.deck_c(-14.0)) + K["POLPOKLAD_H"]
    ztop = rf.ztop

    def across(z, out, n=24, inset=0.0):
        xe = rf.half(z) - inset
        return [rf.pt(xe * (1 - 2 * k / n), z, out) for k in range(n + 1)]

    def moulding(z, h, d, mat, inset=0.04, przerwa=0.0):
        """Listwa w poprzek pawęży na wysokości z: wysokość h, wystawanie d; przerwa > 0 – listwa przerwana
        w osi na szerokość 2·przerwa (otwór steru)."""
        xe = rf.half(z) - inset
        if przerwa > 0:
            odc = [list(np.linspace(xe, przerwa, 13)), list(np.linspace(-przerwa, -xe, 13))]
        else:
            odc = [list(np.linspace(xe, -xe, 25))]
        # profil zamknięty w płaszczyźnie (na zewnątrz = −s, w górę = z); spód 4 mm w licu pawęży (bryła zamknięta,
        # bez ścian współpłaszczyznowych z licem)
        prof = [(-0.004, -h / 2), (d * 0.7, -h / 2), (d, -h / 4), (d, h / 4), (d * 0.7, h / 2), (-0.004, h / 2)]
        for xs in odc:
            vs = []
            for x in xs:
                ring = [rf.pt(x, z + b, a) for (a, b) in prof]
                vs.append(sk.verts(ring))
            m = len(prof)
            for k in range(len(vs) - 1):
                for j in range(m):
                    j2 = (j + 1) % m
                    q = [vs[k][j], vs[k][j2], vs[k + 1][j2], vs[k + 1][j]]
                    sk.face_proj(q, mat, axis=1)
            sk.face_proj(list(reversed(vs[0])), mat, flat=True)
            sk.face_proj(list(vs[-1]), mat, flat=True)
    # pawęż skrzydłowa (gruba belka pod kontrą, przerwana na otwór steru) i listwy kontry, okien, pokładu rufowego
    moulding(zwt + 0.04, 0.24, 0.12, R("listwa"), inset=0.0, przerwa=ctx["ster_otwor"]["r"] + 0.03)
    moulding(zc + 0.02, 0.10, 0.08, R("listwa"))
    moulding(G["OKNO_Z"] - 0.07, 0.07, 0.07, R("rzezby"))
    moulding(G["OKNO_Z"] + G["OKNO"][1] + 0.08, 0.08, 0.08, R("rzezby"))
    moulding(zqd - 0.02, 0.10, 0.09, R("listwa"))
    # okna: rama (4 listwy), szprosy w teksturze, szyba wysunięta przed lico
    wx, wz = G["OKNO"]
    for xc in G["OKNA_X"]:
        z0, z1 = G["OKNO_Z"], G["OKNO_Z"] + wz
        x0, x1 = xc - wx / 2, xc + wx / 2
        g = [rf.pt(x0, z0, 0.035), rf.pt(x1, z0, 0.035), rf.pt(x1, z1, 0.035), rf.pt(x0, z1, 0.035)]
        vi = sk.verts(g)
        # szyba: UV 0..1 na całe okno (kafel 1 m → skala okna)
        sk.face([vi[0], vi[1], vi[2], vi[3]], [(1, 0), (0, 0), (0, 1), (1, 1)], "szklo", flat=True)
        fw = 0.07
        # boki ramy wchodzą 2 cm w listwy górną i dolną (bez wspólnych krawędzi – po scaleniu miały po 4 ściany)
        e_ = 0.02
        for (a, b, c, d) in (((x0 - fw, z0 - fw), (x1 + fw, z0 - fw), (x1 + fw, z0), (x0 - fw, z0)),
                             ((x0 - fw, z1), (x1 + fw, z1), (x1 + fw, z1 + fw), (x0 - fw, z1 + fw)),
                             ((x0 - fw + 0.003, z0 - e_), (x0, z0 - e_), (x0, z1 + e_), (x0 - fw + 0.003, z1 + e_)),
                             ((x1, z0 - e_), (x1 + fw - 0.003, z0 - e_), (x1 + fw - 0.003, z1 + e_), (x1, z1 + e_))):
            cs = [a, b, c, d]
            boczna = a[1] < z0 - 0.01 and c[1] > z1 + 0.01       # bok ramy: lico 4 mm za licem listew (bez migotania)
            front = sk.verts([rf.pt(px, pz, 0.066 if boczna else 0.07) for (px, pz) in cs])
            back = sk.verts([rf.pt(px, pz, -0.006 if boczna else -0.01) for (px, pz) in cs])
            sk.face_proj([front[0], front[1], front[2], front[3]], R("listwa"), flat=True, axis=1)
            for i in range(4):
                j = (i + 1) % 4
                sk.face_proj([back[i], back[j], front[j], front[i]], R("listwa"), flat=True)
            sk.face_proj([back[3], back[2], back[1], back[0]], R("listwa"), flat=True)      # spód w licu (zamknięta)
    # pilastry między oknami (złocone): baza, trzon, kapitel
    px_list = [-1.86, -0.84, 0.0, 0.84, 1.86]
    for xc in px_list:
        z0, z1 = G["OKNO_Z"] - 0.03, G["OKNO_Z"] + wz + 0.03
        for (zz0, zz1, w, d) in ((z0, z0 + 0.06, 0.16, 0.10), (z0 + 0.06, z1 - 0.08, 0.10, 0.07),
                                 (z1 - 0.08, z1, 0.17, 0.11)):
            cs = [(xc - w / 2, zz0), (xc + w / 2, zz0), (xc + w / 2, zz1), (xc - w / 2, zz1)]
            front = skz.verts([rf.pt(px, pz, d) for (px, pz) in cs])
            back = skz.verts([rf.pt(px, pz, -0.01) for (px, pz) in cs])
            skz.face_proj([front[0], front[1], front[2], front[3]], R("rzezby"), axis=1, rot=math.pi / 2)
            for i in range(4):
                j = (i + 1) % 4
                skz.face_proj([back[i], back[j], front[j], front[i]], R("rzezby"))
            skz.face_proj(list(reversed(back)), R("rzezby"))
    # tafla nad pokładem rufowym: kartusz owalny, po bokach płaskie wstęgi S z wolutami (snycerka, nie liny)
    zcart = (zqd + ztop) / 2 + 0.02
    up_rufa = Vector((0, 1, 0))                       # lico pawęży patrzy ku rufie (+Y Blendera)

    def wstega(pts2, w0, w1, h=0.045, out=0.012):
        pts3 = [rf.pt(x, z, out) for (x, z) in pts2]
        n = len(pts3)
        sc = [1.0 + (w1 / w0 - 1.0) * k / max(n - 1, 1) for k in range(n)]
        prof = [(-w0 / 2, 0.0), (w0 / 2, 0.0), (w0 * 0.36, h), (-w0 * 0.36, h)]
        N.sweep(skz, pts3, prof, R("rzezby"), scale=sc, up=up_rufa)

    def spirala(cx, cz, r0, obroty, kier, a0):
        out = []
        n = int(28 * obroty)
        for k in range(n + 1):
            a = a0 + kier * 2 * math.pi * obroty * k / n
            r = r0 * math.exp(-1.1 * k / n * obroty)
            out.append((cx + r * math.cos(a), cz + r * math.sin(a)))
        return out
    # kartusz: owalna rama z płaską wstęgą, płyta w kolorze pawęży, rozeta
    ov = [(0.44 * math.cos(2 * math.pi * k / 40), zcart + 0.29 * math.sin(2 * math.pi * k / 40)) for k in range(41)]
    wstega(ov, 0.075, 0.075, 0.05)
    cen = skz.vert(rf.pt(0.0, zcart, 0.06))
    ring = [skz.vert(rf.pt(0.38 * math.cos(2 * math.pi * k / 24), zcart + 0.24 * math.sin(2 * math.pi * k / 24), 0.025))
            for k in range(24)]
    # płyta jako bryła zamknięta: wypukłe lico, obrzeże do 5 mm w głąb lica pawęży i płaski spód
    ring_t = [skz.vert(rf.pt(0.38 * math.cos(2 * math.pi * k / 24), zcart + 0.24 * math.sin(2 * math.pi * k / 24), -0.005))
              for k in range(24)]
    cen_t = skz.vert(rf.pt(0.0, zcart, -0.005))
    for k in range(24):
        a_, b_ = ring[k], ring[(k + 1) % 24]
        pa, pb = Vector(skz.v[a_]), Vector(skz.v[b_])
        skz.face([cen, b_, a_], [(0, zcart), (pb.x, pb.z), (pa.x, pa.z)], R("pawez"))
        c_, d_ = ring_t[k], ring_t[(k + 1) % 24]
        skz.face_proj([a_, b_, d_, c_], R("pawez"))
        skz.face_proj([cen_t, c_, d_], R("pawez"))
    N.lathe(skz, [(0.0, 0.0), (0.09, 0.0), (0.1, 0.02), (0.07, 0.045), (0.03, 0.06), (0.0, 0.065)], R("rzezby"),
            rf.pt(0.0, zcart, 0.06), axis=up_rufa, sides=12)
    for k in range(8):
        a_ = 2 * math.pi * k / 8
        wstega([(0.12 * math.cos(a_), zcart + 0.12 * math.sin(a_)), (0.2 * math.cos(a_), zcart + 0.17 * math.sin(a_))],
               0.05, 0.02, 0.03, 0.06)
    # korona nad kartuszem: trzy listki
    for (dx, hh) in ((-0.13, 0.12), (0.0, 0.19), (0.13, 0.12)):
        wstega([(dx * 0.6, zcart + 0.30), (dx, zcart + 0.30 + hh * 0.6), (dx * 1.1, zcart + 0.30 + hh)], 0.07, 0.02)
    for sgn in (1, -1):
        # górna wstęga S: od kartusza w bok i w dół, zwinięta w wolutę
        c1 = (sgn * 1.42, zcart - 0.02)
        body = [(sgn * 0.47, zcart + 0.06), (sgn * 0.72, zcart + 0.24), (sgn * 1.02, zcart + 0.25),
                (sgn * 1.30, zcart + 0.13)]
        body = [tuple(p) for p in N.catmull(body, 6)]
        vol = spirala(c1[0], c1[1], 0.15, 1.15, -sgn, math.pi / 2 + (0.0 if sgn > 0 else 0.0))
        vol = [(c1[0] + (x - c1[0]), z) for (x, z) in vol]
        wstega(body + vol[1:], 0.11, 0.035)
        # dolna wstęga (przeciwna): pod spodem, krótsza, zwinięta do góry
        c2 = (sgn * 1.02, zcart - 0.14)
        body2 = [tuple(p) for p in N.catmull([(sgn * 0.46, zcart - 0.07), (sgn * 0.7, zcart - 0.24),
                                              (sgn * 0.93, zcart - 0.26)], 6)]
        vol2 = spirala(c2[0], c2[1], 0.10, 1.0, sgn, -math.pi / 2)
        wstega(body2 + vol2[1:], 0.08, 0.03)
        # liście: krótkie, zwężające się wstęgi wychodzące z górnej woluty ku narożnikowi
        for (dz, ln) in ((0.10, 0.34), (-0.08, 0.28)):
            pts = [tuple(p) for p in N.catmull([(sgn * 1.5, zcart + dz), (sgn * (1.5 + ln * 0.5), zcart + dz + 0.06),
                                                (sgn * (1.5 + ln), zcart + dz - 0.02)], 5)]
            wstega(pts, 0.07, 0.015)
    # korona pawęży: łukowa deska nad pokrywą relingu w środku
    crown = []
    xe = rf.half(ztop) * 0.62
    for k in range(25):
        t = -1 + 2 * k / 24
        crown.append((xe * t, ztop + 0.07 + 0.30 * math.cos(t * math.pi / 2) ** 1.5))
    vb, vt = [], []
    for (x, zt_) in crown:
        vb.append((rf.pt(x, ztop + 0.03, 0.02), rf.pt(x, ztop + 0.03, -0.10)))
        vt.append((rf.pt(x, zt_, 0.02), rf.pt(x, zt_, -0.10)))
    for k in range(len(crown) - 1):
        for (i0, i1) in ((0, 0), (1, 1)):
            pass
        a0, a1 = sk.vert(vb[k][0]), sk.vert(vb[k + 1][0])
        b0, b1 = sk.vert(vt[k][0]), sk.vert(vt[k + 1][0])
        c0, c1 = sk.vert(vb[k][1]), sk.vert(vb[k + 1][1])
        d0, d1 = sk.vert(vt[k][1]), sk.vert(vt[k + 1][1])
        sk.face_proj([a0, a1, b1, b0], R("pawez"), axis=1)
        sk.face_proj([c1, c0, d0, d1], R("pawez"), axis=1)
        sk.face_proj([b0, b1, d1, d0], R("reling"))
        # spód (leży na pokrywie relingu) i końce – deska korony jest bryłą zamkniętą
        sk.face_proj([a1, a0, c0, c1], R("pawez"))
        if k == 0:
            sk.face_proj([a0, b0, d0, c0], R("pawez"))
        if k == len(crown) - 2:
            sk.face_proj([a1, c1, d1, b1], R("pawez"))
    edge = [(x, zt_ - 0.035) for (x, zt_) in crown]
    wstega(edge, 0.06, 0.06, 0.04, 0.03)
    ctx["latarnia_baza"] = rf.pt(0.0, crown[12][1] + 0.02, -0.04)
    # narożniki pawęży: pilaster z wolutą u góry (od pawęży skrzydłowej do relingu)
    for sgn in (1, -1):
        zz = np.linspace(zwt + 0.12, ztop - 0.05, 14)
        pts2 = [(sgn * (rf.half(z) - 0.09), z) for z in zz]
        wstega(pts2, 0.13, 0.13, 0.06, 0.0)
        ztp = zz[-1]
        cx = sgn * (rf.half(ztp) - 0.09)
        vol = spirala(cx - sgn * 0.08, ztp - 0.06, 0.09, 1.1, -sgn, 0.0)
        wstega([(cx, ztp - 0.25), (cx, ztp - 0.06)] + vol, 0.09, 0.03, 0.05, 0.05)
    ob = N.to_object(sk, ctx["kol"]["rufa_dziob"], recalc=True)
    ob.data.set_sharp_from_angle(angle=math.radians(35))
    oz = N.to_object(skz, ctx["kol"]["rufa_dziob"], recalc=False)
    oz.data.set_sharp_from_angle(angle=math.radians(50))
    latarnia(ctx)
    return ob, oz


def latarnia(ctx):
    """Latarnia rufowa na żelaznym wsporniku nad koroną pawęży: sześciokąt, szyby, kopuła, gałka."""
    sk = N.Siatka("latarnia_rufowa")
    b = Vector(ctx["latarnia_baza"])
    N.cylinder(sk, b, b + Vector((0, 0, 0.32)), 0.035, 0.03, "zelazo", sides=8)
    N.cylinder(sk, b + Vector((0, 0.0, 0.25)), b + Vector((0, 0.18, 0.25)), 0.025, 0.025, "zelazo", sides=6)
    c = b + Vector((0, 0.0, 0.34))
    N.lathe(sk, [(0.0, 0.0), (0.18, 0.0), (0.2, 0.03), (0.2, 0.06), (0.16, 0.08)], "zelazo", c, sides=6)
    # szyby i słupki
    for k in range(6):
        a0 = 2 * math.pi * k / 6
        a1 = 2 * math.pi * (k + 1) / 6
        p0 = c + Vector((0.17 * math.cos(a0), 0.17 * math.sin(a0), 0.08))
        p1 = c + Vector((0.17 * math.cos(a1), 0.17 * math.sin(a1), 0.08))
        p2 = c + Vector((0.20 * math.cos(a1), 0.20 * math.sin(a1), 0.52))
        p3 = c + Vector((0.20 * math.cos(a0), 0.20 * math.sin(a0), 0.52))
        vv = sk.verts([p0, p1, p2, p3])
        sk.face(vv, [(0, 0), (0.25, 0), (0.25, 0.5), (0, 0.5)], "szklo", flat=True)
        N.cylinder(sk, p0, p3, 0.014, 0.014, "zelazo", sides=6)
    N.lathe(sk, [(0.22, 0.52), (0.24, 0.55), (0.2, 0.6), (0.15, 0.68), (0.08, 0.74), (0.03, 0.78), (0.03, 0.84),
                 (0.05, 0.87), (0.0, 0.92)], "zelazo", c, sides=12)
    ob = N.to_object(sk, ctx["kol"]["rufa_dziob"], recalc=True)
    ob.name = "latarnia_rufowa"
    ctx["obj"]["latarnia"] = ob
    return ob


# ---------------------------------------------------------------- dziób
def dziob(ctx):
    kd, K = ctx["kd"], ctx["K"]
    G = GALION
    ps = ctx["poszycie"]
    sf = stem_face(ctx)
    sk = N.Siatka("galion")
    skz = N.Siatka("galion_rzezby")
    kn = np.array(G["KOLANO"])
    zs = np.linspace(kn[0, 0], kn[-1, 0], 40)
    inner, outer, hw, mats = [], [], [], []
    for z in zs:
        ah = float(np.interp(z, kn[:, 0], kn[:, 1]))
        s_in = sf(z) - 0.06
        inner.append(P(0, s_in, z))
        outer.append(P(0, sf(z) + max(ah, 0.02), z))
        hw.append(G["KOLANO_GR"] / 2 * (1 - 0.25 * min(1, max(0, (z + 1.3) / 3.6))))
    for i in range(len(zs) - 1):
        mats.append(R("dno") if (zs[i] + zs[i + 1]) / 2 < K["LINIA_WODNA_FARBA"] else R("burta"))
    N.solid_strip(sk, inner, outer, hw, mats)
    z_fig = 2.30
    s_fig = sf(z_fig) + float(np.interp(z_fig, kn[:, 0], kn[:, 1]))
    # zwój (scroll): pełna woluta – grubość promieniowa równa odstępowi zwojów, więc zwoje przylegają; oko w środku
    c_s, c_z = s_fig - 0.16, z_fig + 0.10
    sp, rad = [], []
    nturn = 1.6
    kexp = 0.1
    for k in range(80):
        th = -math.pi * 0.5 + k / 79 * nturn * 2 * math.pi
        r = 0.30 * math.exp(-kexp * (th + math.pi * 0.5))
        dr = r * (1 - math.exp(-kexp * 2 * math.pi))
        sp.append((c_s + (r - dr / 2) * math.cos(th), c_z + (r - dr / 2) * math.sin(th)))
        rad.append(dr)
    path = [P(0, s, z) for (s, z) in sp]
    w = G["KOLANO_GR"] * 0.95
    sc = [rr / rad[0] for rr in rad]
    r0 = rad[0]
    prof = [(-r0 / 2, -w / 2 * 0.85), (-r0 / 4, -w / 2), (r0 / 4, -w / 2), (r0 / 2, -w / 2 * 0.85),
            (r0 / 2, w / 2 * 0.85), (r0 / 4, w / 2), (-r0 / 4, w / 2), (-r0 / 2, w / 2 * 0.85)]
    N.sweep(skz, path, prof, R("rzezby"), scale=sc, scale_b=[1.0] * len(sc), up=Vector((1, 0, 0)))
    for sgn in (1, -1):
        # listwa spiralna na bokach (krawędź zwoju) i oko woluty
        p2 = [P(sgn * (w / 2 + 0.008), s, z) for (s, z) in sp]
        N.sweep(skz, p2, N.circle_prof(0.018, 6), R("rzezby"), scale=[max(x, 0.4) for x in sc])
        N.lathe(skz, [(0.0, 0.0), (0.05, 0.0), (0.055, 0.015), (0.03, 0.03), (0.0, 0.035)], R("rzezby"),
                P(sgn * w / 2, sp[-1][0], sp[-1][1]), axis=Vector((sgn, 0, 0)), sides=10)
    # deska z ornamentem (trailboard) między policzkami: płaska listwa z rzędem „liści”
    for sgn in (1, -1):
        # deska z ornamentem: płaska listwa leżąca na boku kolana, z rzędem rozet
        pts = []
        for t in np.linspace(0, 1, 18):
            z = 1.05 + 0.65 * t
            s = sf(z) + float(np.interp(z, kn[:, 0], kn[:, 1])) * (0.30 + 0.40 * t)
            pts.append(P(sgn * (G["KOLANO_GR"] / 2 * 0.86), s, z))
        N.sweep(skz, pts, [(-0.06, 0.0), (0.06, 0.0), (0.045, 0.02), (-0.045, 0.02)], R("rzezby"),
                up=Vector((sgn, 0, 0)))
        for t in (0.2, 0.45, 0.7):
            q = pts[int(t * 17)]
            N.lathe(skz, [(0.0, 0.0), (0.035, 0.0), (0.04, 0.012), (0.02, 0.025), (0.0, 0.028)], R("rzezby"),
                    q + Vector((sgn * 0.018, 0, 0)), axis=Vector((sgn, 0, 0)), sides=8)
    def przy_burcie(cv, odst):
        """Punkty krzywej (x, s, z) nie głębiej w burcie niż odst od lica poszycia (wcześniej dolny policzek
        sterczał na berghołcie jako osobny ochrowy kawałek, a dalej chował się w burcie; koniec dolnego relingu
        galionu wychodził z burty jako jasny, poszarpany skrawek); pierwszy punkt 3 cm w burcie – koniec
        (czop) schowany w poszyciu."""
        out = []
        for i, (x, s, z) in enumerate(cv):
            if s < 13.9:
                try:
                    xo = ps.outer(s, z)[0]
                    x = xo - 0.03 if i == 0 else max(x, xo + odst)
                except Exception:
                    pass
            out.append((x, s, z))
        return out
    # policzki: dwie pełne, wygięte listwy (przekrój 0,16 × 0,11 z wyokrągleniem) z burty dziobu do boku kolana
    kg = lambda z: G["KOLANO_GR"] / 2 * (1 - 0.25 * min(1, max(0, (z + 1.3) / 3.6)))
    prof_p = [(-0.055, -0.08), (0.035, -0.08), (0.06, -0.045), (0.06, 0.045), (0.035, 0.08), (-0.055, 0.08)]
    for (zc_, f0) in ((1.05, 0.48), (1.62, 0.66)):
        for sgn in (1, -1):
            s_h = 12.45 if zc_ < 1.3 else 12.70
            xh, (nx, ns) = ps.outer(s_h, zc_ - 0.06)
            ah = float(np.interp(zc_ + 0.16, kn[:, 0], kn[:, 1]))
            pts = [(xh + 0.03, s_h, zc_ - 0.06), (xh * 0.78, s_h + 0.42, zc_ - 0.04), (xh * 0.42, s_h + 0.85, zc_ + 0.04),
                   (kg(zc_) + 0.08, sf(zc_ + 0.1) + ah * f0 * 0.6, zc_ + 0.12),
                   (kg(zc_ + 0.16) + 0.04, sf(zc_ + 0.16) + ah * f0, zc_ + 0.16)]
            cv = N.catmull(pts, 8)
            # policzek przylega do burty dziobu na całej długości: punkty krzywej nie wchodzą w poszycie głębiej niż
            # 1,5 cm (wcześniej początek dolnego policzka sterczał na berghołcie jako osobny ochrowy kawałek, a dalej
            # policzek chował się w burcie)
            path = [P(sgn * x, s, z) for (x, s, z) in przy_burcie(cv, 0.045)]
            N.sweep(sk, path, prof_p, R("burta_gorna"), up=Vector((0, 0, 1)))
    # relingi galionu: płynne łuki od relingu dziobu w dół i w przód, kończące się za zwojem
    rails = []
    s_kb = GALION["KOTBELKA_S"]
    # górny reling zaczyna się przed wspornikiem kotbelki (wspornik sięga s_kb + 0,63), dolny pod nim
    for (s_h, z_off, z_end, f_end, dip) in ((s_kb + 0.70, -0.06, 2.36, 0.82, 0.26), (s_kb + 0.80, -0.46, 1.98, 0.66, 0.2)):
        for sgn in (1, -1):
            zt = ps.rail_top(s_h) + z_off
            xh, (nx, ns) = ps.outer(s_h, zt - 0.06)
            ah = float(np.interp(z_end, kn[:, 0], kn[:, 1]))
            pe = (kg(z_end) + 0.03, sf(z_end) + ah * f_end, z_end)
            p1 = (xh * 0.80, s_h + 0.45, zt - dip * 0.75)
            p2 = (xh * 0.45, (s_h + pe[1]) / 2 + 0.25, min(zt, z_end) - dip)
            p3 = (kg(z_end) + 0.10, pe[1] - 0.35, z_end - dip * 0.35)
            cv = N.catmull([(xh + 0.03, s_h, zt - 0.03), p1, p2, p3, pe], 8)
            cv = przy_burcie(cv, 0.04)
            path = [P(sgn * x, s, z) for (x, s, z) in cv]
            N.sweep(sk, path, N.circle_prof(0.05, 10), R("burta_gorna"))
            rails.append((sgn, cv))
    # słupki galionu: od dolnego policzka do górnego relingu
    for sgn in (1, -1):
        up_cv = [c for (sg, c) in rails if sg == sgn][0]
        lo_cv = [c for (sg, c) in rails if sg == sgn][1]
        for f in (0.32, 0.58, 0.82):
            pu = up_cv[int(f * (len(up_cv) - 1))]
            pl = lo_cv[int(f * (len(lo_cv) - 1))]
            N.cylinder(sk, P(sgn * pl[0], pl[1], pl[2] - 0.30), P(sgn * pu[0], pu[1], pu[2]), 0.045, 0.04,
                       R("burta_gorna"), sides=8)
    # kratownice galionu: dwie połówki po bokach kolana (kolano przechodzi środkiem), z obramowaniem
    zg = 1.86
    s0 = sf(zg) + 0.03
    s1 = sf(zg) + float(np.interp(zg, kn[:, 0], kn[:, 1])) - 0.18
    xk = kg(zg) + 0.005
    half = lambda s: 0.52 * (1 - (s - s0) / (s1 - s0)) + 0.20 * (s - s0) / (s1 - s0)
    for sgn in (1, -1):
        for s in np.arange(s0 + 0.04, s1 - 0.02, 0.075):
            hw = half(s)
            N.oriented_box(sk, P(sgn * xk, s, zg), P(sgn * hw, s, zg), 0.025, 0.03, "drewno")
        for x in np.arange(xk + 0.04, 0.52, 0.075):
            s_end = s0 + (s1 - s0) * min(1.0, max(0.0, (0.52 - x) / (0.52 - 0.20)))
            if s_end - s0 < 0.08:
                continue
            N.oriented_box(sk, P(sgn * x, s0, zg + 0.028), P(sgn * x, s_end, zg + 0.028), 0.025, 0.03, "drewno")
        # obramowanie
        N.oriented_box(sk, P(sgn * xk, s1, zg + 0.012), P(sgn * half(s1), s1, zg + 0.012), 0.05, 0.06, "drewno_ciemne")
        N.oriented_box(sk, P(sgn * half(s0), s0, zg + 0.012), P(sgn * half(s1), s1, zg + 0.012), 0.05, 0.06,
                       "drewno_ciemne")
    # wytyki (bumpkins) na hals foka: krótkie drzewca z burty dziobu skośnie w przód i na boki
    for sgn in (1, -1):
        # pod opuszczoną kotwicą: drzewiec kotwicy wisi przy burcie 1,96–2,6 m nad wodą, wytyk przechodzi pod nim
        zb_ = ps.rail_top(12.0) - 0.95
        xb_, (nx, ns) = ps.outer(12.0, zb_)
        xa_, _ = ps.outer(11.85, zb_)
        a_ = P(sgn * (xa_ + 0.03), 11.85, zb_)          # przykręcony do burty od zewnątrz
        b_ = P(sgn * (xb_ + 0.75), 13.15, zb_ - 0.08)
        N.cylinder(sk, a_, b_, 0.065, 0.05, "drewno_czarne", sides=10)
        N.lathe(sk, [(0.066, -0.02), (0.075, 0.0), (0.066, 0.02)], "zelazo", b_ - (b_ - a_).normalized() * 0.08,
                axis=(b_ - a_).normalized(), sides=10, close_ends=False)
    # knechty bukszprytu (knightheads) po bokach głowicy dziobnicy
    zd = float(kd.deck_c(13.2))
    for sgn in (1, -1):
        b0 = P(sgn * 0.31, 13.35, zd - 0.05)
        b1 = P(sgn * 0.31, 13.45, ps.rail_top(13.4) + 0.32)
        N.oriented_box(sk, b0, b1, 0.22, 0.22, "drewno_ciemne", up=Vector((0, -1, 0)))
        N.lathe(sk, [(0.13, 0), (0.15, 0.04), (0.12, 0.1), (0.0, 0.16)], "drewno_ciemne", b1, sides=8)
    ctx["galion_figura"] = (s_fig, z_fig)
    ob = N.to_object(sk, ctx["kol"]["rufa_dziob"], recalc=True)
    ob.data.set_sharp_from_angle(angle=math.radians(40))
    oz = N.to_object(skz, ctx["kol"]["rufa_dziob"])
    oz.data.set_sharp_from_angle(angle=math.radians(50))
    kotbelki_i_kluzy(ctx)
    return ob


def kotbelki_i_kluzy(ctx):
    kd, K = ctx["kd"], ctx["K"]
    G = GALION
    ps = ctx["poszycie"]
    sk = N.Siatka("kotbelki")
    s_c = G["KOTBELKA_S"]
    zt = ps.rail_top(s_c)
    a = G["KOTBELKA_PRZEKR"]
    ends = []
    for sgn in (1, -1):
        xh, (nx, ns) = ps.outer(s_c, zt)
        # od wnętrza (na pokładzie) na zewnątrz pod kątem ok. 45° do przodu, lekko w górę
        p_in = (xh - 0.85, s_c - 0.55, zt - 0.02)
        d = Vector((0.72, 0.69, 0.06)).normalized()
        L = (0.85 + G["KOTBELKA_WYST"]) / d.x
        p_out = (p_in[0] + d.x * L, p_in[1] + d.y * L, p_in[2] + d.z * L)
        b0, b1 = P(sgn * p_in[0], p_in[1], p_in[2]), P(sgn * p_out[0], p_out[1], p_out[2])
        N.oriented_box(sk, b0, b1, a, a, "drewno_czarne")
        # krążki (dwie szczeliny) i rozeta na czole
        dd = (b1 - b0).normalized()
        for k in (0.12, 0.30):
            N.box(sk, b1 - dd * k + Vector((0, 0, a / 2 + 0.002)), (0.06, 0.06, 0.006), "zelazo")
        # rozeta na czole: mniejsza i okrągła (20 boków; wcześniej 10-kąt na prawie całe czoło), UV z rzutu na
        # płaszczyznę czoła (UV toczenia dawało promieniste smugi tekstury jak słoje)
        f0 = len(sk.f)
        N.lathe(sk, [(0.0, 0.0), (0.075, 0.0), (0.085, 0.014), (0.065, 0.036), (0.03, 0.05), (0.0, 0.055)], R("rzezby"),
                b1, axis=dd, sides=20)
        e1 = dd.cross(Vector((0, 0, 1))).normalized()
        e2 = e1.cross(dd).normalized()
        for fi in range(f0, len(sk.f)):
            sk.uv[fi] = [(Vector(sk.v[i]).dot(e1), Vector(sk.v[i]).dot(e2)) for i in sk.f[fi]]
        # wspornik pod kotbelką: łuk od burty do spodu belki
        xs, (nx2, ns2) = ps.outer(s_c + 0.25, zt - 0.75)
        pts = [(xs, s_c + 0.25, zt - 0.75), (xs + 0.35, s_c + 0.55, zt - 0.32),
               (xh + 0.55, s_c + 0.38 + 0.25, zt - a / 2 - 0.03)]
        cv = N.catmull(pts, 6)
        N.sweep(sk, [P(sgn * x, s, z) for (x, s, z) in cv], N.rect_prof(0.16, 0.14), "drewno_czarne")
        ends.append((sgn, b1))
    ctx["kotbelki"] = ends
    # kluzy: okute pierścienie w burcie dziobu
    for sgn in (1, -1):
        s0, z0 = G["KLUZA_S"], G["KLUZA_Z"]
        x0, (nx, ns) = ps.outer(s0, z0)
        n3 = Vector((sgn * nx, -ns, 0)).normalized()
        c = P(sgn * x0, s0, z0)
        N.lathe(sk, [(G["KLUZA_R"] + 0.07, -0.01), (G["KLUZA_R"] + 0.08, 0.04), (G["KLUZA_R"] + 0.03, 0.09),
                     (G["KLUZA_R"], 0.08), (G["KLUZA_R"], -0.05)], "drewno_ciemne", c, axis=n3, sides=14,
                close_ends=False)
        N.lathe(sk, [(G["KLUZA_R"], -0.04), (G["KLUZA_R"], -0.046)], "zelazo", c, axis=n3, sides=14)
    ob = N.to_object(sk, ctx["kol"]["rufa_dziob"])
    ob.data.set_sharp_from_angle(angle=math.radians(40))
    return ob


def boki_rufy(ctx):
    """Bok pokładu rufowego z podziałami jak pawęż: listwa w połowie wysokości, wstęga z wolutą na uskoku nadburcia
    (hance), małe okno kabiny w ramie z listwą i kartusz pod nim."""
    kd, K = ctx["kd"], ctx["K"]
    ps = ctx["poszycie"]
    sk = N.Siatka("rufa_boki")
    sq = K["POLPOKLAD_S"]

    def na_burcie(s, z, off):
        x, (nx, ns) = ps.outer(s, z)
        return (x + nx * off, s + ns * off, z), (nx, ns)

    def wstega(pts_sz, w0, w1, h=0.045, side=1, off=0.004):          # noqa: E301
        pts, ups = [], []
        for (s, z) in pts_sz:
            (x, s2, z2), (nx, ns) = na_burcie(s, z, off)
            pts.append(P(side * x, s2, z2))
            ups.append(Vector((side * nx, -ns, 0)))
        n = len(pts)
        sc = [1.0 + (w1 / w0 - 1.0) * k / max(n - 1, 1) for k in range(n)]
        prof = [(-w0 / 2, 0.0), (w0 / 2, 0.0), (w0 * 0.36, h), (-w0 * 0.36, h)]
        N.sweep(sk, pts, prof, R("rzezby"), scale=sc, up=ups)
    for side in (1, -1):
        # listwa w połowie boku pokładu rufowego (od pawęży do uskoku)
        ss = list(np.linspace(ps.ra[ps.r_top] + 0.15, sq - 0.15, 24))
        mid = [(s, float(ps.Zd(s)) + 1.18) for s in ss]
        wstega(mid, 0.07, 0.07, 0.04, side)
        # uskok nadburcia: wstęga wzdłuż krzywej uskoku zakończona wolutą (hance)
        pts = []
        f_next = min([f for f in K["FURTY_S"] if f > sq] or [sq + 2.0])
        s_end = min(sq + 0.95, f_next - K["FURTA_SZER"] / 2 - 0.035 - 0.30)   # woluta (r 0,12) przed pokrywą furty
        # wstęga 0,25 m pod pokrywą relingu (wcześniej 0,12): ława wantowa grota biegnie wzdłuż uskoku tuż pod
        # pokrywą (spód 0,125 m) – po zamknięciu ławy jako bryły test pokazał 2,75 cm wejścia ławy w wolutę
        for s in np.linspace(sq - 0.05, s_end, 12):
            pts.append((s, ps.rail_top(s) - 0.25))
        cs, cz = pts[-1][0] + 0.10, pts[-1][1] - 0.02
        # cała woluta (r 0,135) pod spodem ławy wantowej (pokrywa − 0,125) także tam, gdzie uskok już się wznosi
        cz = min(cz, min(ps.rail_top(s_) for s_ in np.linspace(cs - 0.15, cs + 0.15, 7)) - 0.125 - 0.15)
        wstega(pts, 0.10, 0.07, 0.05, side)
        # woluta: wypukła tarcza (zwój) na burcie i spirala wstęgi zwinięta na niej, z oczkiem w środku
        (xc_, sc_, zc_), (nx_, ns_) = na_burcie(cs, cz, 0.004)
        nrm = Vector((side * nx_, -ns_, 0)).normalized()
        cen = P(side * xc_, sc_, zc_)
        N.lathe(sk, [(0.0, 0.05), (0.06, 0.046), (0.11, 0.03), (0.135, 0.0)], R("rzezby"), cen, axis=nrm, sides=18)
        spir = []
        for k in range(0, 30):
            a = math.pi - 2 * math.pi * 1.6 * k / 29
            r = 0.125 * math.exp(-1.25 * k / 29)
            spir.append((cs + r * math.cos(a), cz + r * math.sin(a)))
        wstega(spir, 0.06, 0.025, 0.035, side, off=0.045)
        N.lathe(sk, [(0.0, 0.085), (0.025, 0.08), (0.03, 0.06)], R("rzezby"), cen, axis=nrm, sides=10)
        # okno kabiny (quarter light) z ramą i kartusz pod nim
        s0w, z0w = -11.6, float(ps.Zd(-11.6)) + 0.55
        wx, wz = 0.46, 0.36
        corners = [(s0w - wx / 2, z0w), (s0w + wx / 2, z0w), (s0w + wx / 2, z0w + wz), (s0w - wx / 2, z0w + wz)]
        g = [na_burcie(s, z, 0.02)[0] for (s, z) in corners]
        vg = sk.verts([P(side * x, s, z) for (x, s, z) in g])
        sk.face(vg if side < 0 else vg[::-1], [(0, 0), (1, 0), (1, 1), (0, 1)] if side < 0 else [(0, 1), (1, 1), (1, 0), (0, 0)],
                "szklo", flat=True)
        ramka = corners + [corners[0]]
        wstega([(s, z) for (s, z) in ramka], 0.07, 0.07, 0.05, side, off=0.0)
        kart = [(s0w + 0.32 * math.cos(2 * math.pi * k / 24), z0w - 0.32 + 0.14 * math.sin(2 * math.pi * k / 24))
                for k in range(25)]
        wstega(kart, 0.05, 0.05, 0.035, side)
    ob = N.to_object(sk, ctx["kol"]["rufa_dziob"])
    ob.data.set_sharp_from_angle(angle=math.radians(50))
    return ob


def zbuduj(ctx):
    rufa(ctx)
    boki_rufy(ctx)
    dziob(ctx)
