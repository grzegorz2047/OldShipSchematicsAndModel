"""Drzewca: kolumny masztów (zbieżność Steela, wuldingi, kwadratowe topy z policzkami), marsy (zaokrąglony przód,
otwór, obrzeże), belki marsa, ezelhofty, stengi z salingami, bramstengi z gałką, maszt snow, bukszpryt z bomstengą
i blindareją, reje (osobne obiekty z osią na osi masztu, lokalna Z = oś masztu), gafel i bom ze szczękami.

Liczby: parametry.DRZEWCA (rozdział 05 przewodnika). Wszystkie punkty zaczepienia lin trafiają do ctx['rig'].
"""
import math

import numpy as np
from mathutils import Matrix, Vector

import narzedzia as N
from narzedzia import P


def interp_taper(fracs, vals, f):
    return float(np.interp(f, fracs, vals))


class Maszt:
    """Oś masztu: s(z) = s_d − (z − z_d)·tan(pochylenie); punkty i promienie wzdłuż wysokości z."""

    def __init__(self, nazwa, s_d, z_d, rake_deg, z_heel, L, sr, top_len, D):
        self.nazwa = nazwa
        self.s_d, self.z_d = s_d, z_d
        self.t = math.tan(math.radians(rake_deg))
        self.cr = math.cos(math.radians(rake_deg))
        self.z_heel = z_heel
        self.z_cap = z_heel + L * self.cr
        self.z_top = self.z_cap - top_len * self.cr      # belki marsa (podstawa topu)
        self.sr = sr
        self.D = D

    def s(self, z):
        return self.s_d - (z - self.z_d) * self.t

    def p(self, z, dx=0.0, ds=0.0):
        return P(dx, self.s(z) + ds, z)

    def dir(self):
        return (P(0, self.s(1.0), 1.0) - P(0, self.s(0.0), 0.0)).normalized()

    def r(self, z):
        T = self.D["TAPER_MASZT"]
        if z <= self.z_top:
            f = (z - self.z_d) / (self.z_top - self.z_d)
            return self.sr / 2 * interp_taper([0, .25, .5, .75, 1.0], T[:4] + [T[4]], max(f, 0))
        return self.sr / 2 * T[5]


def _band(sk, c, axis, r, mat, n=3, w=0.022):
    """Opaska z liny (wulding): n zwojów (każdy zamknięty; sąsiednie zachodzą na siebie o 10 % – bez wspólnych
    krawędzi, które po scaleniu wierzchołków miały po 4 ściany)."""
    for k in range(n):
        cc = c + axis * (k - (n - 1) / 2) * w * 0.9
        N.lathe(sk, [(r, -w / 2), (r + w * 0.45, -w / 4), (r + w * 0.5, 0), (r + w * 0.45, w / 4), (r, w / 2)],
                mat, cc, axis=axis, sides=12, close_ends=False)


def kolumna(ctx, m, sk):
    D = ctx["PR"].DRZEWCA
    ax = m.dir()
    zs = list(np.linspace(m.z_d - 0.15, m.z_top, 12))
    path = [m.p(z) for z in zs]
    sc = [m.r(z) / m.r(m.z_d) for z in zs]
    N.sweep(sk, path, N.circle_prof(m.r(m.z_d), 16), "drewno", scale=sc)        # dno w kadłubie, bryła zamknięta
    # top: kwadratowy, od belek do ezelhoftu
    hs = m.sr * D["TAPER_MASZT"][5] / 2
    N.oriented_box(sk, m.p(m.z_top - 0.05), m.p(m.z_cap), hs * 2, hs * 2, "drewno_czarne", up=Vector((0, -1, 0)))
    # policzki (hounds) pod belkami marsa
    for sgn in (1, -1):
        a = m.p(m.z_top - 1.7, dx=sgn * (m.r(m.z_top - 1.0) + 0.04))
        b = m.p(m.z_top - 0.02, dx=sgn * (m.r(m.z_top) + 0.05))
        N.oriented_box(sk, a, b, 0.11, m.sr * 0.55, "drewno_czarne", up=Vector((0, -1, 0)))
    # wuldingi co ok. 0,95 m
    z = m.z_d + 1.5
    while z < m.z_top - 2.0:
        _band(sk, m.p(z), ax, m.r(z), "lina_smolowana")
        z += 0.95
    # opętnik (partners): pierścień klinów przy pokładzie
    N.lathe(sk, [(m.r(m.z_d) + 0.12, 0.0), (m.r(m.z_d) + 0.09, 0.08), (m.r(m.z_d), 0.12)], "drewno_ciemne",
            m.p(m.z_d - 0.01), axis=ax, sides=16, close_ends=False)


def mars(ctx, m, sk, W, Lt):
    """Belki (trestle trees, crosstrees) i pomost marsa: tył prosty, przód zaokrąglony, otwór w środku."""
    zt = m.z_top
    hs = m.sr * ctx["PR"].DRZEWCA["TAPER_MASZT"][5] / 2
    # trestle trees
    for sgn in (1, -1):
        a = m.p(zt + 0.07, dx=sgn * (hs + 0.07), ds=-Lt * 0.42)
        b = m.p(zt + 0.07, dx=sgn * (hs + 0.07), ds=Lt * 0.55)
        N.oriented_box(sk, a, b, 0.11, 0.17, "drewno_czarne")
    # crosstrees
    for f in (-0.32, 0.12, 0.45):
        a = m.p(zt + 0.2, dx=-W * 0.48, ds=Lt * f)
        b = m.p(zt + 0.2, dx=W * 0.48, ds=Lt * f)
        N.oriented_box(sk, a, b, 0.09, 0.09, "drewno_czarne")
    # pomost: pas między obrysem D a otworem (lubber's hole), grubość 0,06
    c_s = m.s(zt) + Lt * 0.06
    z0, z1 = zt + 0.245, zt + 0.305
    hx, hb, hf = W * 0.20, Lt * 0.30, Lt * 0.20      # otwór: półszerokość, w tył, w przód
    n = 48
    outer, inner = [], []
    Lb, Lf = Lt * 0.48, Lt * 0.52
    for k in range(n):
        th = 2 * math.pi * k / n
        dx, dy = math.cos(th), math.sin(th)          # dx – w poprzek, dy – wzdłuż (+ dziób)
        # obrys: z tyłu prostokąt, z przodu półelipsa
        if dy >= 0:
            # przecięcie promienia z elipsą (W/2, Lf) i bokami
            t1 = 1.0 / math.sqrt((dx / (W / 2)) ** 2 + (dy / Lf) ** 2)
            t = t1
        else:
            t = min(abs((W / 2) / dx) if abs(dx) > 1e-6 else 1e9, abs(Lb / dy) if abs(dy) > 1e-6 else 1e9)
        outer.append((dx * t, dy * t))
        ti = min(abs(hx / dx) if abs(dx) > 1e-6 else 1e9, abs((hf if dy > 0 else hb) / dy) if abs(dy) > 1e-6 else 1e9)
        inner.append((dx * ti, dy * ti))
    vo0 = [sk.vert(P(x, c_s + y, z0)) for (x, y) in outer]
    vo1 = [sk.vert(P(x, c_s + y, z1)) for (x, y) in outer]
    vi0 = [sk.vert(P(x, c_s + y, z0)) for (x, y) in inner]
    vi1 = [sk.vert(P(x, c_s + y, z1)) for (x, y) in inner]
    for k in range(n):
        k2 = (k + 1) % n
        sk.face_proj([vi1[k], vo1[k], vo1[k2], vi1[k2]], "drewno")
        sk.face_proj([vi0[k2], vo0[k2], vo0[k], vi0[k]], "drewno")
        sk.face_proj([vo0[k], vo0[k2], vo1[k2], vo1[k]], "drewno_czarne")
        sk.face_proj([vi0[k2], vi0[k], vi1[k], vi1[k2]], "drewno_czarne")
    # obrzeże (listwa) na krawędzi
    rim = [P(x * 0.985, c_s + y * 0.985, z1 + 0.03) for (x, y) in outer]
    # pierścień: początek i koniec z denkami (styk na łączeniu – dwie zamknięte końcówki zamiast otwartych pętli)
    N.sweep(sk, rim + [rim[0]], N.rect_prof(0.06, 0.06), "drewno_czarne", cap0=True, cap1=True,
            up=Vector((0, 0, 1)))
    return dict(c_s=c_s, z=z1, W=W, Lb=Lb, Lf=Lf, outer=outer, Lt=Lt)


def ezelhoft(sk, m, z_cap, front_off, L, Wd, th, mat="drewno_czarne"):
    """Ezelhoft: blok nad topem, tylna część na czopie kolumny, przednia obejmuje stengę."""
    c = m.p(z_cap + th / 2, ds=front_off / 2)
    R = N.rot_to(m.dir(), up=Vector((0, -1, 0)))
    N.box(sk, c, (Wd, L, th), mat, rot=N.rot_to(Vector((0, 0, 1))) @ Matrix.Identity(3))


class Stenga:
    def __init__(self, base_m, s_off, z_heel, L, sr, head, D, taper):
        self.m = base_m
        self.s_off = s_off
        self.z_heel = z_heel
        self.z_top = z_heel + L * base_m.cr
        self.z_head = self.z_top - head * base_m.cr
        self.sr = sr
        self.taper = taper

    def s(self, z):
        return self.m.s(z) + self.s_off

    def p(self, z, dx=0.0, ds=0.0):
        return P(dx, self.s(z) + ds, z)

    def r(self, z, z_from):
        T = self.taper
        if z <= self.z_head:
            f = (z - z_from) / max(self.z_head - z_from, 1e-3)
            return self.sr / 2 * interp_taper([0, .25, .5, .75, 1.0], T[:4] + [T[4]], max(f, 0))
        return self.sr / 2 * T[5]


def stenga_geom(sk, st, z_cap, mat="drewno"):
    zs = list(np.linspace(st.z_heel, st.z_head, 10))
    path = [st.p(z) for z in zs]
    r0 = st.r(z_cap, z_cap)
    sc = [st.r(max(z, z_cap), z_cap) / r0 for z in zs]
    N.sweep(sk, path, N.circle_prof(r0, 12), mat, scale=sc)
    hs = st.sr * st.taper[5] / 2 * 1.15
    N.oriented_box(sk, st.p(st.z_head - 0.02), st.p(st.z_top), hs * 2, hs * 2, "drewno_czarne", up=Vector((0, -1, 0)))
    # kwadratowa pięta z sztabą (fid)
    N.oriented_box(sk, st.p(st.z_heel - 0.05), st.p(st.z_heel + 0.35), st.sr * 1.02, st.sr * 1.02, mat,
                   up=Vector((0, -1, 0)))


def reja(ctx, nazwa, m_center, m_axis, L, sr, kol, with_parrel_r=None, mat="drewno_ciemne", oct_mid=False):
    """Reja jako osobny obiekt: oś obrotu = oś masztu przez punkt m_center (Blender), lokalna Z = m_axis."""
    D = ctx["PR"].DRZEWCA
    T = D["TAPER_REJA"]
    sk = N.Siatka(nazwa)
    yard_c = m_center
    n = 17
    xs = np.linspace(-L / 2, L / 2, n)
    path = [yard_c + Vector((x, 0, 0)) for x in xs]
    sc = [interp_taper([0, .25, .5, .75, 1.0], T, abs(x) / (L / 2)) for x in xs]
    f0 = len(sk.f)
    N.sweep(sk, path, N.circle_prof(sr / 2, 12, math.pi / 12), mat, scale=sc)
    # kolor wierzchołków: noki ciemniejsze (smoła, brud z rąk przy refowaniu), środek jaśniejszy – wytarty przez raki
    for fi in range(f0, len(sk.f)):
        cs = []
        for vi in sk.f[fi]:
            xn = abs((Vector(sk.v[vi]) - yard_c).x) / (L / 2)
            t = 0.92 - 0.30 * float(np.clip((xn - 0.78) / 0.17, 0, 1)) + 0.08 * float(np.clip(1 - xn / 0.09, 0, 1))
            cs.append((t, t * 0.985, t * 0.955))
        sk.odcien[fi] = cs
    # okucia noków: dwie obręcze, klampy (cleats) przy stropie
    for sgn in (1, -1):
        for f in (0.93, 0.985):
            x = sgn * L / 2 * f
            rr = sr / 2 * interp_taper([0, .25, .5, .75, 1.0], T, f) + 0.008
            N.cylinder(sk, yard_c + Vector((x - 0.02, 0, 0)), yard_c + Vector((x + 0.02, 0, 0)), rr, rr, "zelazo",
                       sides=12)
        N.box(sk, yard_c + Vector((sgn * sr * 0.9, 0, sr / 2 + 0.02)), (0.06, sr * 0.5, 0.05), mat)
        N.box(sk, yard_c + Vector((sgn * L / 2 * 0.9, 0, sr * 0.45 * T[3])), (0.05, 0.05, 0.04), mat)
    ob = N.to_object(sk, kol, recalc=True)
    return ob


def zbuduj(ctx):
    kd, K, PR = ctx["kd"], ctx["K"], ctx["PR"]
    D = PR.DRZEWCA
    kol = ctx["kol"]["drzewca"]
    rig = {"maszty": {}, "reje": {}}
    ctx["rig"] = rig
    sk = N.Siatka("drzewca")
    snow = ctx["snow"]
    for key, nm_, Lk, srk, topk, stk, st_srk, st_top, brk, br_srk, rake in (
            ("fok", "FOK", "FOK", "FOK_SR", "FOK_TOP", "FOK_STENGA", "FOK_STENGA_SR", "FOK_STENGA_TOP", "FOK_BRAM",
             "FOK_BRAM_SR", "FOK_POCHYL"),
            ("grot", "GROT", "GROT", "GROT_SR", "GROT_TOP", "GROT_STENGA", "GROT_STENGA_SR", "GROT_STENGA_TOP",
             "GROT_BRAM", "GROT_BRAM_SR", "GROT_POCHYL")):
        s_d = D[nm_ + "_S"]
        z_d = float(kd.deck_c(s_d))
        z_heel = float(kd.zk(s_d)) + D["KILSON_NAD_WREBEM"]
        m = Maszt(key, s_d, z_d, D[rake], z_heel, D[Lk], D[srk], D[topk], D)
        kolumna(ctx, m, sk)
        Lst = D[stk]
        W = Lst * D["MARS_SZER_STENGI"]
        Lt = W * D["MARS_DL_SZER"]
        top = mars(ctx, m, sk, W, Lt)
        # stenga: przed topem kolumny, pięta nad belkami marsa
        hs = m.sr * D["TAPER_MASZT"][5] / 2
        st_off = hs + D[st_srk] / 2 + 0.03
        st = Stenga(m, st_off, m.z_top + 0.05, Lst, D[st_srk], D[st_top], D, D["TAPER_STENGA"])
        stenga_geom(sk, st, m.z_cap)
        # ezelhoft kolumny
        cap_L = 4 * D[st_srk] + 0.08
        cap_W = 2 * D[st_srk] + 0.05
        cap_T = cap_W * 4 / 9
        cc = P(0, m.s(m.z_cap) + st_off / 2, m.z_cap + cap_T / 2)
        N.box(sk, cc, (cap_W, cap_L, cap_T), "drewno_czarne")
        # saling stengi (trestle + crosstrees)
        zx = st.z_head
        Wx = W * 0.62
        for sgn in (1, -1):
            N.oriented_box(sk, st.p(zx + 0.05, dx=sgn * (st.sr * 0.35 + 0.05), ds=-0.55),
                           st.p(zx + 0.05, dx=sgn * (st.sr * 0.35 + 0.05), ds=0.65), 0.07, 0.1, "drewno_czarne")
        for f in (-0.35, 0.35):
            N.oriented_box(sk, st.p(zx + 0.15, dx=-Wx / 2, ds=f), st.p(zx + 0.15, dx=Wx / 2, ds=f), 0.07, 0.07,
                           "drewno_czarne")
        # bramstenga przed topem stengi
        hs2 = st.sr * D["TAPER_STENGA"][5] / 2 * 1.15
        br_off = st_off + hs2 + D[br_srk] / 2 + 0.02
        br = Stenga(m, br_off, zx + 0.05, D[brk] + 1.0, D[br_srk], 0.9, D, D["TAPER_STENGA"])
        zs = list(np.linspace(br.z_heel, br.z_top, 8))
        sc = [1.0 - 0.45 * (z - br.z_heel) / (br.z_top - br.z_heel) for z in zs]
        N.sweep(sk, [br.p(z) for z in zs], N.circle_prof(D[br_srk] / 2, 10), "drewno", scale=sc)
        N.lathe(sk, [(0.0, 0.0), (0.11, 0.0), (0.12, 0.04), (0.1, 0.08), (0.0, 0.09)], "drewno_czarne",
                br.p(br.z_top), axis=m.dir(), sides=12)
        # ezelhoft stengi
        ccap = P(0, st.s(st.z_top) + (br_off - st_off) / 2, st.z_top + 0.07)
        N.box(sk, ccap, (2 * D[br_srk] + 0.06, 4 * D[br_srk] + 0.12, 0.14), "drewno_czarne")
        rig["maszty"][key] = dict(m=m, st=st, br=br, top=top, W=W, Lt=Lt, Wx=Wx, st_off=st_off, br_off=br_off,
                                  z_br_head=br.z_top - 1.0 - 0.0, cap_T=cap_T)
    # maszt snow: tuż za grotmasztem, od pokładu do spodu belek grotmarsa
    mg = rig["maszty"]["grot"]["m"]
    if snow:
        s_sn = D["GROT_S"] - D["SNOW_ODSTEP"]
        z0 = float(kd.deck_c(s_sn))
        z1 = mg.z_top - 0.02
        r_sn = D["SNOW_MASZT_SR"] * D["GROT_SR"] / 2
        a = P(0, s_sn, z0 - 0.1)
        b = P(0, s_sn - (z1 - z0) * mg.t, z1)
        N.cylinder(sk, a, b, r_sn, r_sn * 0.85, "drewno", sides=12, segs=4)
        rig["snow"] = dict(s=s_sn, z0=z0, z1=z1, r=r_sn, t=mg.t)
    ob = N.to_object(sk, kol, recalc=True)
    ob.name = "drzewca"
    ob.data.set_sharp_from_angle(angle=math.radians(40))
    ctx["obj"]["drzewca"] = ob
    bukszpryt(ctx)
    reje_wszystkie(ctx)
    gafel_bom(ctx)


def bukszpryt(ctx):
    kd, K, PR = ctx["kd"], ctx["K"], ctx["PR"]
    D = PR.DRZEWCA
    rig = ctx["rig"]
    sk = N.Siatka("bukszpryt")
    ang = math.radians(D["BUKSZPRYT_WZNIOS"])
    dvec = (math.cos(ang), math.sin(ang))           # (s, z)
    # spód bukszprytu nad głowicą dziobnicy (s 14,1, z 3,4)
    st_head = K["DZIOB"][-1]
    r0 = D["BUKSZPRYT_SR"] / 2
    p_stem = (st_head[0] + 0.05, st_head[1] + D["BUKSZPRYT_NAD_DZIOBNICA"] + r0)
    L = D["BUKSZPRYT"]
    # pięta na pokładzie: cofamy się wzdłuż osi aż do pokładu + promień
    t_back = 0.0
    while True:
        s = p_stem[0] - dvec[0] * t_back
        z = p_stem[1] - dvec[1] * t_back
        if z - r0 <= float(kd.deck_c(s)) + 0.05 or t_back > 6:
            break
        t_back += 0.02
    heel = (p_stem[0] - dvec[0] * t_back, p_stem[1] - dvec[1] * t_back)
    end = (heel[0] + dvec[0] * L, heel[1] + dvec[1] * L)
    n = 12
    path = [P(0, heel[0] + dvec[0] * L * k / n, heel[1] + dvec[1] * L * k / n) for k in range(n + 1)]
    sc = [1.0 if k / n < 0.35 else 1.0 - 0.38 * (k / n - 0.35) / 0.65 for k in range(n + 1)]
    N.sweep(sk, path, N.circle_prof(r0, 16), "drewno", scale=sc)
    # ezelhoft bukszprytu na końcu (prostopadły do pionu), z otworem na bomstengę nad nim
    bsr = D["BOMSTENGA_SR"]
    pe = Vector(path[-1])
    dir3 = (Vector(path[-1]) - Vector(path[0])).normalized()
    up3 = Vector((0, 0, 1)) - dir3 * dir3.z
    up3.normalize()
    N.box(sk, pe + up3 * (r0 * 0.62 * 0.5 + bsr * 0.5) + dir3 * 0.08, (r0 * 1.5, 0.16, r0 * 1.2 + bsr + 0.1),
          "drewno_czarne", rot=N.rot_to(dir3, up=Vector((0, 0, 1))) @ Matrix.Rotation(math.pi / 2, 3, "X")
          if False else None)
    # nakładki (bees) i klampy wiązania
    for sgn in (1, -1):
        c = Vector(path[int(n * 0.8)]) + Vector((sgn * r0 * 0.75, 0, 0))
        N.box(sk, c, (0.08, 0.7, 0.14), "drewno_czarne")
    # bity bukszprytu: dwa słupki przy pięcie z poprzeczką
    zd = float(kd.deck_c(heel[0]))
    for sgn in (1, -1):
        N.box(sk, P(sgn * 0.42, heel[0] - 0.15, zd + 0.42), (0.22, 0.22, 0.95), "drewno_ciemne")
    N.box(sk, P(0, heel[0] - 0.15, zd + 0.62), (1.05, 0.2, 0.2), "drewno_ciemne")
    # bomstenga: na bukszprycie (lekko na prawo), od 0,62 długości bukszprytu przez ezelhoft
    jl = D["BOMSTENGA"]
    j0 = Vector(path[int(n * 0.62)]) + up3 * (r0 * 0.75 + bsr / 2) + Vector((-0.02, 0, 0))
    j1 = j0 + dir3 * jl
    N.cylinder(sk, j0, j1, bsr / 2, bsr / 2 * 0.6, "drewno", sides=10, segs=4)
    N.lathe(sk, [(0.0, 0.0), (bsr * 0.4, 0.0), (bsr * 0.45, 0.04), (0.0, 0.07)], "drewno_czarne", j1, axis=dir3,
            sides=10)
    ob = N.to_object(sk, ctx["kol"]["drzewca"], recalc=True)
    ob.data.set_sharp_from_angle(angle=math.radians(40))
    ctx["obj"]["bukszpryt"] = ob
    rig["bukszpryt"] = dict(heel=heel, end=end, dir=dvec, r0=r0, L=L, path=[Vector(p) for p in path], dir3=dir3,
                            up3=up3, j0=j0, j1=j1, sc=sc)
    # blindareja pod bukszpryt (ok. 0,8 długości bukszprytu)
    ps_ = Vector(path[int(n * 0.83)]) - up3 * (r0 * sc[int(n * 0.83)] + D["BLINDAREJA_SR"] / 2 + 0.25)
    ob = reja(ctx, "reja_blinda", ps_, Vector((0, 0, 1)), D["BLINDAREJA"], D["BLINDAREJA_SR"], ctx["kol"]["drzewca"])
    N.ustaw_os(ob, ps_, Vector((0, 0, 1)), Vector((1, 0, 0)))
    rig["reje"]["blinda"] = dict(obj=ob, c=ps_, L=D["BLINDAREJA"], sr=D["BLINDAREJA_SR"], mast=None)


def reje_wszystkie(ctx):
    D = ctx["PR"].DRZEWCA
    rig = ctx["rig"]
    kol = ctx["kol"]["drzewca"]
    for key, NM in (("fok", "FOK"), ("grot", "GROT")):
        R_ = rig["maszty"][key]
        m, st, br = R_["m"], R_["st"], R_["br"]
        ax = m.dir()
        nm_pl = {"fok": "fok", "grot": "grot"}[key]
        specs = [
            (nm_pl, NM + "REJA", m.z_top - D["REJA_POD_MARSEM"], m, 0.0),
            (nm_pl + "mars", NM + "MARSREJA", m.z_cap + R_["cap_T"] + 0.35, st, R_["st_off"]),
            (nm_pl + "bram", NM + "BRAMREJA", st.z_top + 0.14 + 0.3, br, R_["br_off"]),
        ]
        # wysokość robocza (żagiel postawiony): dolne reje na stropach – bez zmian; marsreja podniesiona pod salingi
        # stengi, bramreja pod top bramstengi (rozdziały 05 i 08); w modelu reje stoją opuszczone (żagle zwinięte),
        # przesunięcie wzdłuż lokalnej Z w extras: wysokosc_robocza_dz_m
        z_rob = {nm_pl: specs[0][2], nm_pl + "mars": st.z_head - D["MARSREJA_POD_SALINGIEM"],
                 nm_pl + "bram": br.z_top - D["BRAMREJA_POD_TOPEM"]}
        for (nam, Lk, z, mast_obj, off) in specs:
            L, sr = D[Lk], D[Lk + "_SR"]
            if isinstance(mast_obj, Maszt):
                r_m = mast_obj.r(z)
            else:
                r_m = mast_obj.sr / 2 * 0.85
            s_ax = m.s(z) + off
            c_axis = P(0, s_ax, z)
            c_yard = P(0, s_ax + r_m + sr / 2 + 0.04, z)
            ob = reja(ctx, "reja_" + nam, c_yard, ax, L, sr, kol)
            # oś brasowania = oś masztu (stengi): rak obejmuje maszt, reja obiega go po okręgu, zostaje 4 cm luzu
            # od masztu przy każdym kącie (obrót wokół punktu styku przesuwał rak w maszt)
            N.ustaw_os(ob, c_axis, ax, Vector((1, 0, 0)))
            ob["wysokosc_robocza_dz_m"] = round(float(z_rob[nam] - z), 3)
            # rak (parrel): lina z kulkami wokół masztu
            skp = N.Siatka("rak_" + nam)
            rr = r_m + 0.035
            ring = [c_axis + Vector((rr * math.cos(t), rr * math.sin(t), 0)) for t in np.linspace(0, 2 * math.pi, 15)]
            # lina raka jako torus (bryła obrotowa z profilu-okręgu, zamknięta bez szwu)
            N.lathe(skp, [(rr + 0.012 * math.cos(a_), 0.012 * math.sin(a_)) for a_ in np.linspace(0, 2 * math.pi, 7)[:-1]],
                    "lina_smolowana", c_axis, axis=Vector((0, 0, 1)), sides=14, close_ends=False)
            for t in np.linspace(math.pi * 0.2, math.pi * 0.8, 5):
                q = c_axis + Vector((rr * math.cos(t + math.pi), rr * math.sin(t + math.pi), 0))
                N.lathe(skp, [(0.0, -0.03), (0.035, -0.012), (0.035, 0.012), (0.0, 0.03)], "drewno_ciemne",
                        q, sides=6)
            op = N.to_object(skp, kol)
            op.parent = ob
            op.matrix_parent_inverse = ob.matrix_world.inverted()
            rig["reje"][nam] = dict(obj=ob, c=c_yard, axis_pt=c_axis, L=L, sr=sr, mast=key, z=z)


def gafel_bom(ctx):
    kd, D = ctx["kd"], ctx["PR"].DRZEWCA
    rig = ctx["rig"]
    kol = ctx["kol"]["drzewca"]
    mg = rig["maszty"]["grot"]["m"]
    if ctx["snow"]:
        sn = rig["snow"]
        s_of = lambda z: sn["s"] - (z - sn["z0"]) * sn["t"]
        r_m = sn["r"]
    else:
        s_of = mg.s
        r_m = mg.r(mg.z_top - 1.0)
    ax = mg.dir()
    out = {}
    for nam, L, sr, z, ang in (("gafel", D["GAFEL"], D["GAFEL_SR"], mg.z_top - 0.9, D["GAFEL_KAT"]),
                               ("bom", D["BOM"], D["BOM_SR"], float(kd.deck_c(D["GROT_S"])) + D["BOM_NAD_POKLADEM"], 2.5)):
        if nam == "bom" and not D["Z_BOMEM"]:
            continue
        sk = N.Siatka(nam)
        a = math.radians(ang)
        c_axis = P(0, s_of(z), z)
        start = P(0, s_of(z) - r_m - sr / 2 - 0.02, z)
        d = Vector((0, math.cos(a), math.sin(a)))       # w tył (Blender +Y) i w górę
        n = 10
        path = [start + d * (L * k / n) for k in range(n + 1)]
        sc = [1.0 - 0.35 * (k / n) ** 1.5 for k in range(n + 1)]
        N.sweep(sk, path, N.circle_prof(sr / 2, 12), "drewno_ciemne", scale=sc)
        # szczęki: dwa rogi obejmujące maszt
        for sgn in (1, -1):
            pts = []
            for t in np.linspace(0, math.pi * 0.62, 8):
                rr = r_m + 0.05
                pts.append(c_axis + Vector((sgn * rr * math.sin(t), rr * math.cos(t) * 1.0, 0)))
            pts = [start + Vector((sgn * 0.06, 0.12, 0))] + pts[::-1][:-1]
            N.sweep(sk, pts, N.rect_prof(0.07, sr * 0.9), "drewno_ciemne", up=Vector((0, 0, 1)))
        N.box(sk, start + d * 0.25, (sr * 1.15, 0.5, sr * 1.1), "drewno_ciemne")
        ob = N.to_object(sk, kol, recalc=True)
        N.ustaw_os(ob, c_axis, ax, Vector((0, 1, 0)))
        out[nam] = dict(obj=ob, start=start, end=path[-1], c=c_axis, L=L)
        rig["reje"][nam] = dict(obj=ob, c=start, axis_pt=c_axis, L=L, sr=sr, mast="grot", z=z, end=path[-1])
    return out
