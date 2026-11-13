"""Sterowanie: dwa warianty napędu steru w jednym modelu (rozdział 09 przewodnika).

naped_kolo   – koło sterowe na dwóch stojakach z bębnem; sterlina z bębna przez dwa przepusty z krążkami w pokładzie
               rufowym, krążki przy burtach pod pokładem i do końca rumpla, który pracuje w kabinie pod pokładem rufowym.
naped_rumpel – rumpel na głowicy steru nad pokładem rufowym, talie odciążające do pierścieni w nadburciu.

Oba rumple są dziećmi steru (jeden napęd: obrót steru o kąt α obraca rumpel). Każdy obiekt wariantu ma właściwość
'wariant'; części stałe i koło są dziećmi pustego obiektu grupy (naped_kolo / naped_rumpel, extras.wariant,
extras.widoczny_domyslnie). Stanowiska i przeszkody do testu chodzenia też niosą 'wariant'.

Przełożenie koła (zapisane w extras koła i w bryg_poklad.json):
    wychylenie rumpla o α przesuwa jego koniec w poprzek o L_r·sin α, o tyle samo sterlina nawija się na bęben
    (krążki przy burtach, lina prawie poprzecznie do rumpla), więc liczba obrotów koła
        n = L_r · sin α / (π · D_b)
    dla L_r = 3,0 m, D_b = 0,30 m, α = 35°: n = 3,0 · 0,574 / 0,942 ≈ 1,83 obrotu.
"""
import math

import bpy
import numpy as np
from mathutils import Matrix, Vector

import narzedzia as N
from narzedzia import P
from wyposazenie import N_ring, blok, deck, przeszkoda, stanowisko

WARIANTY = ("naped_kolo", "naped_rumpel")


def _os(ctx):
    (sa0, za0), (sa1, za1) = ctx["ster_os"]
    ax = (P(0, sa1, za1) - P(0, sa0, za0)).normalized()
    return ax


def _grupa(ctx, nazwa, domyslny):
    e = N.empty(nazwa, Vector((0, 0, 0)), ctx["kol"]["wyposazenie"], size=0.5)
    e["wariant"] = nazwa
    e["widoczny_domyslnie"] = bool(nazwa == domyslny)
    ctx.setdefault("warianty_napedu", {})[nazwa] = dict(grupa=e, obiekty=[])
    return e


def _do_grupy(ctx, ob, nazwa, rodzic=None):
    ob["wariant"] = nazwa
    ctx["warianty_napedu"][nazwa]["obiekty"].append(ob.name)
    par = rodzic if rodzic is not None else ctx["warianty_napedu"][nazwa]["grupa"]
    mw = ob.matrix_world.copy()
    ob.parent = par
    ob.matrix_parent_inverse = par.matrix_world.inverted()
    ob.matrix_world = mw
    return ob


# ------------------------------------------------------------------ wariant: rumpel na pokładzie
def rumpel_pokladowy(ctx):
    U = ctx["PR"].UKLAD["RUMPEL"]
    ps = ctx["poszycie"]
    kol = ctx["kol"]["wyposazenie"]
    ster = ctx["obj"]["ster"]
    s_h, z_h = ctx["ster_glowica"]
    zq = deck(ctx, s_h + 0.3, 0.0, qd=True)
    a_k = math.radians(U["kat"])
    # długość: koniec z gałką (0,13 m) i połową przekroju przy ±35° co najmniej 0,10 m od wewnętrznej krawędzi
    # pokrywy relingu (pokrywa wystaje 0,16 m do środka poza nadburcie)
    L = U["dl"]
    while L > 2.0:
        Le = L + 0.13
        se, xe = s_h + Le * math.cos(a_k), Le * math.sin(a_k) + U["przekr"] / 2
        x_out, _ = ps.outer(se, zq + U["h_konca"])
        if xe <= x_out - (ctx["K"]["RELING_SZER"] - 0.01) - 0.10:
            break
        L -= 0.05
    sk = N.Siatka("rumpel")
    a = P(0, s_h, zq + U["h_glowicy"])
    b = P(0, s_h + L, zq + U["h_konca"])
    N.oriented_box(sk, a, a.lerp(b, 0.7), U["przekr"], U["przekr"], "drewno_ciemne")
    N.sweep(sk, [a.lerp(b, 0.69), b], N.circle_prof(U["przekr"] * 0.36, 10), "drewno_ciemne", scale=[1.0, 0.75])
    N.lathe(sk, [(0.0, 0.0), (0.06, 0.0), (0.075, 0.05), (0.05, 0.11), (0.0, 0.13)], "drewno_ciemne", b,
            axis=(b - a).normalized(), sides=10)
    # okucie (obręcz) rumpla na głowicy steru
    N.cylinder(sk, a + Vector((0, 0.0, -0.11)), a + Vector((0, 0.0, 0.11)), 0.2, 0.2, "zelazo", sides=12)
    ob = N.to_object(sk, kol, recalc=True)
    N.ustaw_os(ob, P(0, s_h, z_h), _os(ctx), Vector((0, -1, 0)))
    ob["os_ruchu"] = "dziecko steru: obrót razem ze sterem wokół jego osi, ±%d°" % U["kat"]
    ob["dlugosc_m"] = round(L, 2)
    _do_grupy(ctx, ob, "naped_rumpel", rodzic=ster)
    # talie odciążające: ucho na rumplu 0,75 L od osi → pierścienie w nadburciu na tej samej długości
    from olinowanie import lina
    sp = s_h + 0.75 * L
    zt = zq + U["h_glowicy"] + (U["h_konca"] - U["h_glowicy"]) * 0.75
    for sg in (1, -1):
        xr = sg * (U["przekr"] / 2 + 0.03)
        a_r = P(xr, sp, zt)
        c = N_ring(ctx, sp, zq + 0.55, sg, odst=0.075)
        blok(ctx, a_r.lerp(c, 0.2), (c - a_r).normalized(), 0.12)
        blok(ctx, a_r.lerp(c, 0.7), (c - a_r).normalized(), 0.12)
        for off in (-0.016, 0.016):
            lina(ctx, "talie_rumpla", [a_r + Vector((0, 0, off)), c + Vector((0, 0, off))], 0.018, "lina_jasna",
                 od=ob.name, wariant="naped_rumpel")
    przeszkoda(ctx, "rumpel", "rumpel", "prostokat", s_h + L / 2, 0.0, (L, 0.3), U["h_konca"], poziom="rufowy",
               wariant="naped_rumpel")
    ctx["rumpel"] = dict(s_h=s_h, L=L, kat=U["kat"])
    st = s_h + L - 0.3
    for sg in (1, -1):
        stanowisko(ctx, "ster", st, sg * 0.62, deck(ctx, st, sg * 0.62, qd=True), 0.35, -sg, obiekt="rumpel",
                   os="dziecko steru (oś steru)", zakres=[-U["kat"], U["kat"]], h_rak=U["h_konca"] - 0.05,
                   wariant="naped_rumpel")
    return ob


# ------------------------------------------------------------------ wariant: koło sterowe
def kolo_sterowe(ctx):
    U = ctx["PR"].UKLAD["KOLO"]
    ps = ctx["poszycie"]
    kol = ctx["kol"]["wyposazenie"]
    ster = ctx["obj"]["ster"]
    s_w = U["s"]
    zq = deck(ctx, s_w, 0.0, qd=True)
    za = zq + U["os_h"]
    R = U["D"] / 2
    Rb = U["D_beben"] / 2
    d_l = U["d_sterliny"]
    fwd = Vector((0, -1, 0))                       # oś koła: ku dziobowi
    s_d0 = s_w + 0.17
    s_d1 = s_d0 + U["L_beben"]
    s_st = (s_w + 0.115, s_d1 + 0.065)             # stojaki: między kołem a bębnem i przed bębnem
    # ---- koło z bębnem (obiekt ruchomy, oś w osi bębna)
    sk = N.Siatka("kolo_sterowe")
    c = P(0, s_w, za)
    # obręcz (felgi) i piasta
    N.lathe(sk, [(R - 0.075, -0.032), (R, -0.032), (R + 0.004, 0.0), (R, 0.032), (R - 0.075, 0.032), (R - 0.079, 0.0),
                 (R - 0.075, -0.032)], "drewno_ciemne", c, axis=fwd, sides=40, close_ends=False, uv_obwod=True)
    N.lathe(sk, [(0.0, -0.10), (0.07, -0.10), (0.09, -0.085), (0.13, -0.07), (0.13, 0.07), (0.10, 0.09), (0.05, 0.10),
                 (0.0, 0.10)], "drewno_ciemne", c, axis=fwd, sides=20)
    N.lathe(sk, [(0.0, -0.118), (0.055, -0.118), (0.065, -0.10), (0.0, -0.10)], "braz", c, axis=fwd, sides=16)
    # szprychy toczone, zakończone rękojeściami za obręczą
    n_sz = U["szprychy"]
    for k in range(n_sz):
        t = 2 * math.pi * k / n_sz + math.pi / n_sz
        dr = Vector((math.cos(t), 0.0, math.sin(t)))
        prof = [(0.026, 0.11), (0.03, 0.16), (0.022, 0.30), (0.024, R - 0.08), (0.019, R + 0.02), (0.026, R + 0.07),
                (0.021, R + 0.12), (0.025, R + 0.15), (0.0, R + 0.172)]
        N.lathe(sk, prof, "drewno_ciemne", c, axis=dr, sides=8, ref=fwd)
    # oś żelazna przez stojaki, bęben z kołnierzami
    N.cylinder(sk, c - fwd * 0.10, P(0, s_st[1] + 0.10, za), 0.035, 0.035, "zelazo", sides=12)
    cb = P(0, s_d0, za)
    N.lathe(sk, [(0.03, -0.0), (Rb + 0.045, 0.0), (Rb + 0.045, 0.03), (Rb, 0.03), (Rb, U["L_beben"] - 0.03),
                 (Rb + 0.045, U["L_beben"] - 0.03), (Rb + 0.045, U["L_beben"]), (0.03, U["L_beben"])], "drewno",
            cb, axis=fwd, sides=20)
    # zwoje sterliny na bębnie: linia śrubowa, początek styczny po lewej (x = +r), koniec po prawej (x = −r)
    rz = Rb + d_l / 2
    sa, sb = s_d0 + 0.03 + d_l, s_d1 - 0.03 - d_l
    nz = U["zwoje"]
    phi1 = 2 * math.pi * nz + math.pi
    hel = []
    for i in range(int(nz * 28) + 15):
        f = i / (int(nz * 28) + 14)
        ph = phi1 * f
        hel.append(P(rz * math.cos(ph), sa + (sb - sa) * f, za + rz * math.sin(ph)))
    N.sweep(sk, hel, N.circle_prof(d_l / 2, 6), "lina_smolowana", rope=True, uv_u_scale=-2 * 3.3 * d_l)
    ob = N.to_object(sk, kol, recalc=True, weld=0.0004)
    ob.data.set_sharp_from_angle(angle=math.radians(35))
    N.ustaw_os(ob, P(0, s_d0 + U["L_beben"] / 2, za), fwd, Vector((1, 0, 0)))
    n_obr = U["rumpel_dl"] * math.sin(math.radians(U["kat"])) / (math.pi * U["D_beben"])
    ob["os_ruchu"] = "obrót wokół lokalnej Z (oś bębna, ku dziobowi), bez ograniczeń"
    ob["przelozenie_obroty_na_35deg"] = round(n_obr, 3)
    ob["przelozenie_wzor"] = "n = L_rumpla·sin(35°) / (π·D_bębna) = %.2f·%.3f / (π·%.2f)" % (
        U["rumpel_dl"], math.sin(math.radians(U["kat"])), U["D_beben"])
    _do_grupy(ctx, ob, "naped_kolo")
    ctx["kolo"] = dict(obj=ob, s=s_w, za=za, n_obr=n_obr)
    # ---- stojaki z łożyskami, podwaliny na pokładzie, przepusty z krążkami
    sk = N.Siatka("kolo_stojaki")
    for st in s_st:
        zd = deck(ctx, st, 0.0, qd=True)
        # stojak: deska 0,16 × 0,09 z zaokrągloną głową, łożysko (obejma żelazna) na osi
        prof = [(-0.08, 0.0), (0.08, 0.0), (0.08, za - zd + 0.02), (0.055, za - zd + 0.11), (-0.055, za - zd + 0.11),
                (-0.08, za - zd + 0.02)]
        v0 = sk.verts([P(x, st - 0.045, zd + 0.001 + z) for (x, z) in prof])
        v1 = sk.verts([P(x, st + 0.045, zd + 0.001 + z) for (x, z) in prof])
        sk.face_proj(v0, "drewno_ciemne", axis=1)
        sk.face_proj(v1[::-1], "drewno_ciemne", axis=1)
        for i in range(len(prof)):
            j = (i + 1) % len(prof)
            sk.face_proj([v0[j], v0[i], v1[i], v1[j]], "drewno_ciemne")
        N.lathe(sk, [(0.036, -0.06), (0.07, -0.06), (0.07, 0.06), (0.036, 0.06)], "zelazo", P(0, st, za),
                axis=Vector((0, 1, 0)), sides=14, close_ends=False)
    # podwalina (belka wzdłuż osi, na pokładzie, luz 1 mm) łączy stojaki
    a0, a1 = s_st[0] - 0.16, s_st[1] + 0.16
    p0 = P(0, a0, deck(ctx, a0, 0.0, qd=True) + 0.001 + 0.04)
    p1 = P(0, a1, deck(ctx, a1, 0.0, qd=True) + 0.001 + 0.04)
    N.oriented_box(sk, p0, p1, 0.12, 0.08, "drewno_ciemne")
    przep = []
    for (x0, s0) in ((rz, sa), (-rz, sb)):
        zd = deck(ctx, s0, x0, qd=True)
        # przepust: rama 0,14 × 0,26 × 0,07 wokół szczeliny 0,05 × 0,16, krążek w szczelinie (oś w poprzek)
        for (dx, ds, wx, ws) in ((0.0475, 0.0, 0.045, 0.26), (-0.0475, 0.0, 0.045, 0.26), (0.0, 0.105, 0.05, 0.05),
                                 (0.0, -0.105, 0.05, 0.05)):
            N.box(sk, P(x0 + dx, s0 + ds, zd + 0.036), (wx, ws, 0.07), "drewno_ciemne")
        rk = 0.065
        # krążek: oś wzdłuż x, górna krawędź tuż pod linią; lina schodzi pionowo po stronie dziobowej krążka
        ck = P(x0 - 0.0, s0 - rk - d_l / 2 - 0.004, zd + rk + 0.003)     # krążek w szczelinie nad pokładem
        N.lathe(sk, [(0.012, -0.012), (rk, -0.012), (rk - 0.01, 0.0), (rk, 0.012), (0.012, 0.012)], "drewno",
                ck, axis=Vector((1, 0, 0)), sides=16)
        przep.append((P(x0, s0, za), P(x0, s0, zd - 0.05)))
    so = N.to_object(sk, kol, recalc=True)
    so.data.set_sharp_from_angle(angle=math.radians(35))
    _do_grupy(ctx, so, "naped_kolo")
    # ---- rumpel pod pokładem rufowym (dziecko steru)
    s_h, _ = ctx["ster_glowica"]
    zqh = deck(ctx, s_h + 0.3, 0.0, qd=True)
    zt = zqh - U["rumpel_pod"]
    Lr = U["rumpel_dl"]
    sk = N.Siatka("rumpel_pod_pokladem")
    a = P(0, s_h, zt)
    b = P(0, s_h + Lr, zt + 0.05)
    N.oriented_box(sk, a, b, 0.16, 0.16, "drewno_ciemne")
    N.cylinder(sk, a + Vector((0, 0, -0.10)), a + Vector((0, 0, 0.10)), 0.2, 0.2, "zelazo", sides=12)
    N.cylinder(sk, b + Vector((-0.1, 0, 0)), b + Vector((0.1, 0, 0)), 0.03, 0.03, "zelazo", sides=8)
    ro = N.to_object(sk, kol, recalc=True)
    N.ustaw_os(ro, P(0, s_h, zt), _os(ctx), Vector((0, -1, 0)))
    ro["os_ruchu"] = "dziecko steru: obrót razem ze sterem, ±%d°" % U["kat"]
    _do_grupy(ctx, ro, "naped_kolo", rodzic=ster)
    # ---- sterlina: z bębna przez przepust w pokładzie, krążek przy burcie pod pokładem, do końca rumpla
    from olinowanie import lina
    zr = zt + 0.05
    for k, (sg, (top, low)) in enumerate(zip((1, -1), przep)):
        s_bl = s_h + Lr - 0.25
        xw = ps.inner(s_bl, zr + 0.5)[0] - 0.35
        cbl = P(sg * xw, s_bl, zr)
        blok(ctx, cbl, Vector((1, 0, 0)), 0.16)
        end = b + Vector((sg * 0.1, 0, 0))
        pts = [top, low, P(low.x, -low.y, zr), cbl + Vector((-sg * 0.09, 0, 0)), end]
        lina(ctx, "sterlina", pts, d_l, "lina_smolowana", od=ob.name, do=ro.name, wariant="naped_kolo")
    przeszkoda(ctx, "kolo_sterowe", "kolo_sterowe", "prostokat", s_w, 0.0, (0.2, U["D"] + 0.34), za + R + 0.17 - zq,
               poziom="rufowy", wariant="naped_kolo")
    przeszkoda(ctx, "kolo_stojaki", "kolo_stojaki", "prostokat", (s_st[0] + s_st[1]) / 2, 0.0,
               (s_st[1] - s_st[0] + 0.42, 0.46), za - zq + 0.11, poziom="rufowy", wariant="naped_kolo")
    opis = "ręce na szprychach na wysokości osi; %.2f obrotu koła = wychylenie steru o 35°" % n_obr
    for k, sg in enumerate((1, -1)):
        st_s, st_x = s_w - 0.55, sg * 0.50
        stanowisko(ctx, "kolo", st_s, st_x, deck(ctx, st_s, st_x, qd=True), 1, 0, obiekt="kolo_sterowe",
                   os="lokalna Z (oś bębna), bez ograniczeń", zakres=None, h_rak=U["os_h"], opis=opis,
                   wariant="naped_kolo")
    return ob


def _z_okuciami(ctx, wariant, fn):
    """Pierścienie i bloki wariantu w osobnych siatkach (żeby w drugim wariancie nie wisiały w powietrzu)."""
    old = {k: ctx.get(k) for k in ("_sk_drobne", "_sk_bloki")}
    tag = wariant.split("_")[1]
    ctx["_sk_drobne"] = N.Siatka("okucia_pokladu_" + tag)
    ctx["_sk_bloki"] = N.Siatka("bloki_" + tag)
    wynik = fn(ctx)
    for k in ("_sk_drobne", "_sk_bloki"):
        if ctx[k].f:
            if k == "_sk_bloki":            # okucia wariantu są już obiektem: blok bez styku dostaje strop
                from wyposazenie import stropy_blokow
                stropy_blokow(ctx, ctx[k], wariant=wariant)
            ob = N.to_object(ctx[k], ctx["kol"]["wyposazenie"], recalc=False)
            _do_grupy(ctx, ob, wariant)
        if old[k] is None:
            del ctx[k]
        else:
            ctx[k] = old[k]
    return wynik


def zbuduj(ctx):
    """Oba warianty napędu steru; widoczny domyślnie ten z parametru UKLAD['STEROWANIE']['naped']."""
    dom = "naped_" + ctx["PR"].UKLAD["STEROWANIE"]["naped"]
    for w in WARIANTY:
        _grupa(ctx, w, dom)
    _do_grupy(ctx, ctx["obj"]["ster_glowica"], "naped_rumpel", rodzic=ctx["obj"]["ster"])
    if ctx["obj"].get("pokrywa_trzonu") is not None:
        # pokrywa otworu trzonu w pokładzie rufowym – tylko przy kole (rumpel pracuje pod pokładem)
        _do_grupy(ctx, ctx["obj"]["pokrywa_trzonu"], "naped_kolo")
    _z_okuciami(ctx, "naped_kolo", kolo_sterowe)
    _z_okuciami(ctx, "naped_rumpel", rumpel_pokladowy)
    for w in WARIANTY:
        g = ctx["warianty_napedu"][w]
        g["grupa"]["wezly"] = ",".join(g["obiekty"])
    ctx["naped_domyslny"] = dom
    return dom


def pokaz(ctx, wariant):
    """Widoczność wariantu w .blend i na renderach (drugi ukryty); liny wariantu przez właściwość 'wariant'."""
    for ob in bpy.data.objects:
        w = ob.get("wariant")
        if w in WARIANTY:
            ob.hide_render = w != wariant
            ob.hide_viewport = w != wariant
