"""Arkusze mechanizmów pokładu: sterowanie, kabestan, kotwica i kotbelka, pompa, działo z lawetą.
Bryły – rzut siatek z usuwaniem linii zasłoniętych (model_rysunkowy.py); liny – z rejestru lin; wymiary – z parametrów
(UKLAD w parametry.py i stałe modułów); przekrój pompy – rysunek analityczny z parametrów (model nie ma wnętrza)."""
import math

import numpy as np

from rysunki_svg import Arkusz, Widok, zakres_odcinkow


def _seg(R, nazwa, f=None):
    s = R.get(nazwa, {}).get("odcinki", [])
    if f:
        s = [[*f(a, b), *f(c, d), w] for a, b, c, d, w in s]
    return s


def _liny(S, warunek):
    return [L for L in S.M["liny"] if warunek(L)]


def _rysuj_liny(V, liny, proj, pioro="srednia", kolor="#7a4a1a"):
    for L in liny:
        V.linia([proj(p) for p in L["p"]], pioro, kolor)


# ======================================================================== sterowanie
def steering_gear(K_, jez, nr, z_ilu):
    S, R = K_["S"], K_["rzuty"]
    U = S.U
    KO, RU = U["KOLO"], U["RUMPEL"]
    a = Arkusz("steering-gear", jez, "A3", nr, z_ilu)
    sk = 40.0
    qd = S.M["inne"]["qd_z"]
    os_s = S.M["inne"]["ster_glowica"][0]
    # widok z boku (z prawej burty): u = s, v = z
    B = Widok(a, 40.0, 120.0, sk, u0=-15.4, v0=2.0)
    B.obszar = (22, 26, 210, 150)
    B.tytul_widoku((26, 20), "Wheel variant, side view from starboard")
    for nm in ("kolo_bok", "rumpel_bok", "bloki_bok"):
        B.odcinki_siatki(_seg(R, nm))
    zq = lambda s: S.deck_c(s) + S.K["POLPOKLAD_H"]
    B.linia([(s, zq(s)) for s in np.linspace(-15.0, -9.0, 20)], "srednia")
    B.linia([(s, zq(s) - S.K["POKLAD_GR"]) for s in np.linspace(-15.0, -9.0, 20)], "cienka")
    _rysuj_liny(B, _liny(S, lambda L: L["g"] == "sterlina"), lambda p: (p[1], p[2]))
    B.os((os_s, 1.6), (os_s, 4.2))
    kd = S.ob.get("kolo_sterowe")
    if kd:
        c = kd["polozenie"]
        B.wymiar((c[1], zq(c[1])), (c[1], c[2]), -18, kier="v", txt="%s %s" % (a.t("axle"), a.n(KO["os_h"])))
        B.wymiar((c[1] - 0.2, c[2] - KO["D"] / 2), (c[1] - 0.2, c[2] + KO["D"] / 2), -30, kier="v",
                 txt="Ø %s" % a.n(KO["D"]))
        B.etykieta((c[1], c[2] + KO["D"] / 2 - 0.05), a.t("Wheel, 10 spokes"), (1, -1), h=2.1)
        B.etykieta((c[1] + 0.35, c[2]), "%s Ø %s, %d %s" % (a.t("Drum"), a.n(KO["D_beben"]), KO["zwoje"],
                                                          a.t("turns of tiller rope")), (1, -0.5), h=2.1)
        B.etykieta((c[1] + 0.1, zq(c[1]) + 0.3), a.t("Standards"), (1, 0.5), h=2.1)
    B.etykieta((-13.0, zq(-13.0) - KO["rumpel_pod"]), "%s %s, %s %s" % (a.t("Tiller below the quarterdeck"),
                                                                       a.n(KO["rumpel_dl"]), a.t("depth"),
                                                                       a.n(KO["rumpel_pod"])), (1, 1), h=2.1)
    B.etykieta((os_s, 3.9), a.t("Rudder head (axis)"), (-1, -1), h=2.1)
    # rzut z góry: u = s, v = x
    T = Widok(a, 40.0, 214.0, 50.0, u0=-15.4, v0=0.0)
    T.obszar = (22, 160, 210, 270)
    T.tytul_widoku((26, 157), "Wheel variant, plan")
    for nm in ("kolo_gora", "rumpel_gora", "bloki_gora"):
        T.odcinki_siatki(_seg(R, nm))
    _rysuj_liny(T, _liny(S, lambda L: L["g"] == "sterlina"), lambda p: (p[1], p[0]))
    T.os((-15.3, 0), (-9.5, 0))
    L_t = KO["rumpel_dl"]
    kat = KO["kat"]
    T.luk((os_s, 0), L_t, -kat, kat, "punkt")
    for sg in (1, -1):
        T.odcinek((os_s, 0), (os_s + L_t * math.cos(math.radians(sg * kat)), L_t * math.sin(math.radians(sg * kat))),
                  "osiowa")
    T.wymiar_kat((os_s, 0), L_t * 0.75, 0, kat, "%s°" % a.n(kat, 0))
    T.wymiar((os_s, -0.45), (os_s + L_t, -0.45), -3, kier="h", txt="%s %s" % (a.t("tiller"), a.n(L_t)))
    T.etykieta((os_s + L_t * 0.6, L_t * math.sin(math.radians(kat)) * 0.6), a.t("Tiller arc ±35°"), (1, 1), h=2.1)
    T.etykieta((-12.0, 2.0), a.t("Sheaves in the deck and blocks at the sides"), (1, 1), h=2.1)
    # wariant z rumplem na pokładzie
    T2 = Widok(a, 245.0, 88.0, 50.0, u0=-15.4, v0=0.0)
    T2.obszar = (225, 26, 408, 150)
    T2.tytul_widoku((228, 20), "Deck tiller variant, plan")
    T2.odcinki_siatki(_seg(R, "rumpel_gora"))
    T2.odcinki_siatki(_seg(R, "bloki_gora"))
    _rysuj_liny(T2, _liny(S, lambda L: L["g"] == "talie_rumpla"), lambda p: (p[1], p[0]))
    T2.os((-15.3, 0), (-10.5, 0))
    rp = S.M["inne"]["rumpel"]
    T2.luk((rp["s_h"], 0), rp["L"], -RU["kat"], RU["kat"], "punkt")
    T2.wymiar((rp["s_h"], -0.5), (rp["s_h"] + rp["L"], -0.5), -3, kier="h", txt="%s %s" % (a.t("tiller"), a.n(rp["L"])))
    T2.etykieta((rp["s_h"] + 0.75 * rp["L"], 0.15), a.t("Relieving tackles to the bulwark rings"), (1, 1), h=2.1)
    # wzór przełożenia
    n = KO["rumpel_dl"] * math.sin(math.radians(KO["kat"])) / (math.pi * KO["D_beben"])
    x0, y0 = 232.0, 180.0
    a.text((x0, y0), a.t("Gear ratio of the wheel"), 3.0, "start", bold=True)
    a.text((x0, y0 + 7), "n = L · sin 35° / (π · D)", 2.8, "start")
    a.text((x0, y0 + 13), "= %s · %s / (π · %s) = %s %s" % (a.n(KO["rumpel_dl"]), a.n(math.sin(math.radians(35)), 3),
                                                            a.n(KO["D_beben"]), a.n(n, 2), a.t("turns")), 2.8, "start")
    a.text((x0, y0 + 20), a.t("L - tiller length, D - drum diameter; turns of the wheel for 35° of rudder."), 2.2,
           "start", italic=True)
    a.text((x0, y0 + 26), "%s Ø %s %s" % (a.t("Tiller rope"), a.n(KO["d_sterliny"] * 1000, 0), "mm"), 2.4, "start")
    a.podzialka((240, 228), sk, 2)
    a.podzialka((240, 245), 50.0, 2)
    a.ramka("Steering gear", "1:40, plans 1:50", "Wheel, drum, tiller rope, tiller; deck tiller variant",
            uwagi=("Fittings projected from the 3D model; tiller ropes from the rigging data.",))
    return a


# ======================================================================== kabestan
def capstan(K_, jez, nr, z_ilu):
    S, R = K_["S"], K_["rzuty"]
    U = S.U["KABESTAN"]
    a = Arkusz("capstan", jez, "A3", nr, z_ilu)
    sk = 20.0
    s0 = U["s"]
    zd = S.deck_c(s0)
    P_ = Widok(a, 112.0, 140.0, sk, u0=s0, v0=0.0)
    P_.tytul_widoku((26, 20), "Plan")
    P_.odcinki_siatki(_seg(R, "kabestan_gora"))
    P_.okrag((s0, 0), U["r_draga"], "osiowa")
    _rysuj_liny(P_, _liny(S, lambda L: L["g"] == "kabestan"), lambda p: (p[1], p[0]), "cienka")
    P_.wymiar_r((s0, 0), U["r_draga"], 112, "R %s" % a.n(U["r_draga"]))
    P_.wymiar_r((s0, 0), U["r_glowica"], 20, "R %s" % a.n(U["r_glowica"]))
    P_.etykieta((s0 + U["r_draga"] * 0.75, U["r_draga"] * 0.1), "%s (%d)" % (a.t("Capstan bars"), U["dragi"]), (1, -1), h=2.2)
    P_.etykieta((s0 + 1.6, -0.5), a.t("Swifter"), (1, 1), h=2.2)
    P_.etykieta((s0 + U["r_draga"] * 0.75, -U["r_draga"] * 0.68), a.t("Circle swept by the bars"), (1, 1), h=2.2)
    E = Widok(a, 300.0, 120.0, sk, u0=s0, v0=zd)
    E.tytul_widoku((225, 20), "Elevation from starboard")
    E.odcinki_siatki(_seg(R, "kabestan_bok"))
    E.odcinek((s0 - 2.0, 0 + zd), (s0 + 2.0, zd), "srednia")
    E.os((s0, zd - 0.2), (s0, zd + U["h"] + 0.2))
    E.wymiar((s0 + U["r_draga"], zd), (s0 + U["r_draga"], zd + U["h"]), 8, kier="v", txt="%s %s" % (a.t("height"), a.n(U["h"])))
    E.wymiar((s0 - U["r_draga"], zd), (s0 - U["r_draga"], zd + U["h_draga"]), -8, kier="v",
             txt="%s %s" % (a.t("bars at"), a.n(U["h_draga"])))
    E.wymiar((s0 - U["r_glowica"], zd + U["h"] + 0.05), (s0 + U["r_glowica"], zd + U["h"] + 0.05), 6, kier="h",
             txt="Ø %s" % a.n(2 * U["r_glowica"]))
    E.wymiar((s0 - U["r_beben"], zd + 0.5), (s0 + U["r_beben"], zd + 0.5), 0, kier="h", txt="Ø %s" % a.n(2 * U["r_beben"]),
             tlo=True)
    E.etykieta((s0 + U["r_glowica"] * 0.8, zd + U["h"] - 0.1), a.t("Drumhead with bar holes"), (1, -1), h=2.2)
    E.etykieta((s0 + U["r_beben"], zd + 0.6), a.t("Barrel with whelps"), (1, 0), h=2.2)
    E.etykieta((s0 + 0.55, zd + 0.1), a.t("Pawl rim and pawls"), (1, 1), h=2.2)
    E.etykieta((s0 - 1.4, zd + U["h_draga"]), a.t("Bar"), (-1, -1), h=2.2)
    a.podzialka((225, 200), sk, 2)
    a.ramka("Capstan", "1:20", "Pawl rim, barrel with whelps, drumhead, bars, swifter",
            uwagi=("Projected from the 3D model; the barrel turns about its vertical axis without limit.",))
    return a


# ======================================================================== kotwica
def anchor(K_, jez, nr, z_ilu):
    S, R = K_["S"], K_["rzuty"]
    a = Arkusz("anchor-and-cathead", jez, "A3", nr, z_ilu)
    gal = S.M["stale"]["rufa_dziob"]["GALION"]
    sk = 25.0
    A = Widok(a, 85.0, 50.0, sk, u0=0.0, v0=0.0)
    A.tytul_widoku((26, 20), "Bower anchor, arms in the plane of the drawing")
    A.odcinki_siatki(_seg(R, "kotwica_rufa"))
    L = 3.3
    A.wymiar((0.6, 0.0), (0.6, -L), 30, kier="v", txt="%s %s" % (a.t("shank"), a.n(L)))
    A.wymiar((-1.05 * math.sin(math.radians(52)), -L + 0.6), (1.05 * math.sin(math.radians(52)), -L + 0.6), -60,
             kier="h", txt="%s %s" % (a.t("span of the arms"), a.n(2 * 1.05 * math.sin(math.radians(52)))))
    for p, t, pref in (((0, 0.05), "Ring", (1, -1)), ((0, -0.34), "Stock (end on)", (1, -0.3)),
                       ((0, -1.6), "Shank", (1, 0)), ((0, -L), "Crown", (1, 1)),
                       ((0.55, -L + 0.2), "Arm", (1, 0.3)), ((0.72, -L + 0.52), "Palm (fluke)", (1, -0.2)),
                       ((-0.86, -L + 0.72), "Bill", (-1, -0.4))):
        A.etykieta(p, a.t(t), pref, h=2.2)
    B = Widok(a, 210.0, 50.0, sk, u0=0.0, v0=0.0)
    B.tytul_widoku((150, 20), "Side view, stock across")
    B.odcinki_siatki(_seg(R, "kotwica_bok"))
    B.wymiar((-1.75, -0.34), (1.75, -0.34), 8, kier="h", txt="%s %s" % (a.t("stock"), a.n(3.5)))
    B.etykieta((1.2, -0.34), a.t("Wooden stock with iron hoops"), (1, 1), h=2.2)
    # dziób z boku 1:75 z liną kotwiczną i kotbelką
    D = Widok(a, 270.0, 205.0, 75.0, u0=9.0, v0=0.0)
    D.obszar = (240, 140, 408, 250)
    D.tytul_widoku((242, 136), "Bow from starboard: cathead, hawse, cable")
    D.odcinki_siatki(_seg(R, "dziob_bok"), ukryte=False)
    _rysuj_liny(D, _liny(S, lambda L: L["g"] == "kotwice"), lambda p: (p[1], p[2]), "srednia")
    D.odcinek((9.0, 0), (19.5, 0), "osiowa")
    D.etykieta((gal["KLUZA_S"], gal["KLUZA_Z"]), "%s Ø %s" % (a.t("Hawse hole"), a.n(2 * gal["KLUZA_R"])), (-1, -1), h=2.0)
    cb = S.M["inne"]["kotbelki"][0][1]
    D.etykieta((cb[1], cb[2]), "%s, %s %s" % (a.t("Cathead"), a.t("projects"), a.n(gal["KOTBELKA_WYST"])), (1, -1), h=2.0)
    D.etykieta((15.5, -0.3), a.t("Starboard anchor let go"), (1, 1), h=2.0)
    D.etykieta((12.8, 1.5), a.t("Port anchor catted (far side)"), (-1, 0.5), h=2.0)
    a.podzialka((26, 262), sk, 2)
    a.podzialka((150, 262), 75.0, 3)
    a.ramka("Anchor and cathead", "1:25, 1:75", "Bower anchor with its parts; catted and let-go positions",
            uwagi=("Anchor projected from the 3D model in its own coordinates; cable and cat fall from the rope data.",))
    return a


# ======================================================================== pompa
def pump(K_, jez, nr, z_ilu):
    S, R = K_["S"], K_["rzuty"]
    U = S.U["POMPY"]
    a = Arkusz("pump", jez, "A3", nr, z_ilu)
    sk = 20.0
    s0, x0 = U["s"], U["x"]
    zd = S.deck_c(s0) - S.K["WYPUKLOSC"] * (x0 / S.K["POL_B"]) ** 2
    z_dno = S.zk(s0) + 0.55
    r = U["r"]
    rb = r * 0.5
    # przekrój (analityczny): v = z względem pokładu
    V = Widok(a, 110.0, 70.0, sk, u0=0.0, v0=zd + U["h"])
    V.obszar = (24, 26, 205, 250)
    V.tytul_widoku((26, 20), "Section through the pump")
    top = zd + U["h"]
    # widok przerwany: rura od góry do zd − 1,1 i dolne 0,8 m przy stopie (przesunięte w górę)
    zc1 = zd - 1.1
    gap = (zc1 - 0.35) - (z_dno + 0.8)
    zdol = z_dno + gap
    for sg in (1, -1):
        V.odcinek((sg * r, zc1), (sg * r, top), "gruba")
        V.odcinek((sg * rb, zc1), (sg * rb, top), "srednia")
        V.odcinek((sg * r, zdol), (sg * r, zdol + 0.8), "gruba")
        V.odcinek((sg * rb, zdol + 0.05), (sg * rb, zdol + 0.8), "srednia")
    for zz in (zc1, zdol + 0.8):
        V.linia([(-r - 0.05, zz), (-r * 0.3, zz + 0.04), (r * 0.3, zz - 0.04), (r + 0.05, zz)], "cienka")
    V.tekst((r + 0.08, zc1 - 0.18), "%s %s" % (a.t("tube length below deck"), a.n(zd - z_dno)), 2.0, "start")
    V.odcinek((-r, top), (r, top), "gruba")
    V.odcinek((-r, zdol), (r, zdol), "gruba")
    V.os((0, zdol - 0.2), (0, top + 0.6))
    for z_, nm in ((zd, "deck"),):
        V.odcinek((-0.8, z_), (0.8, z_), "srednia")
        V.tekst((-0.82, z_), a.t("Deck"), 2.0, "end", dy=0.7)
    z_dno = zdol
    zb = z_dno + 0.35            # zawór dolny (stały)
    V.linia([(-rb, zb), (rb, zb), (rb, zb + 0.12), (-rb, zb + 0.12)], "srednia", zamknij=True)
    V.linia([(-rb * 0.6, zb + 0.12), (0, zb + 0.2), (rb * 0.6, zb + 0.12)], "cienka")
    zt = zd - 0.6                # tłok z zaworem (bucket)
    V.linia([(-rb, zt), (rb, zt), (rb, zt + 0.14), (-rb, zt + 0.14)], "gruba", zamknij=True)
    V.linia([(-rb * 0.6, zt + 0.14), (0, zt + 0.22), (rb * 0.6, zt + 0.14)], "cienka")
    V.odcinek((0, zt + 0.14), (0, top + 0.45), "srednia")
    # dźwignia ±25° na osi nad pompą
    piv = (-0.25, top + 0.5)
    for ang, pio in ((0, "gruba"), (U["wahanie"], "ukryta"), (-U["wahanie"], "ukryta")):
        c, s_ = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        V.odcinek((piv[0] - 0.3 * c, piv[1] - 0.3 * s_), (piv[0] + (U["dzwignia"] - 0.3) * c,
                                                          piv[1] + (U["dzwignia"] - 0.3) * s_), pio)
    V.okrag(piv, 0.03, "cienka", fill="#000")
    V.wymiar_kat(piv, 0.9, -U["wahanie"], U["wahanie"], "±%s°" % a.n(U["wahanie"], 0))
    V.wymiar((piv[0], piv[1] + 0.25), (piv[0] + U["dzwignia"] - 0.3, piv[1] + 0.25), 4, kier="h",
             txt="%s %s" % (a.t("brake"), a.n(U["dzwignia"])))
    zs = top - 0.25
    V.linia([(r, zs), (r + 0.35, zs - 0.08), (r + 0.35, zs - 0.16), (r, zs - 0.1)], "srednia")
    V.wymiar((r + 0.6, zd), (r + 0.6, top), 4, kier="v", txt=a.n(U["h"]))
    V.wymiar((-r, z_dno - 0.1), (r, z_dno - 0.1), -4, kier="h", txt="Ø %s" % a.n(2 * r))
    for p, t, pref in (((r, zd - 1.2), "Elm tube (bored trunk)", (1, 0)), ((rb * 0.5, zb + 0.06), "Lower box, fixed valve", (1, 0.2)),
                       ((rb * 0.5, zt + 0.07), "Bucket with valve on the spear", (1, 0)), ((0, zd + 0.3), "Spear (pump rod)", (1, -0.3)),
                       (piv, "Brake pivot", (-1, -1)), ((r + 0.3, zs - 0.1), "Spout (dale to the scupper)", (1, 0.4)),
                       ((0, z_dno), "Foot in the well, above the keelson", (1, 1))):
        V.etykieta(p, a.t(t), pref, h=2.2)
    # widok modelu (rzut siatki), z boku: u = s, v = z
    E = Widok(a, 300.0, 110.0, sk, u0=s0, v0=zd)
    E.tytul_widoku((225, 20), "Model pump from starboard (port pump)")
    E.odcinki_siatki(_seg(R, "pompa_bok"))
    E.odcinek((s0 - 1.0, zd), (s0 + 1.4, zd), "srednia")
    G = Widok(a, 300.0, 200.0, sk, u0=s0, v0=x0)
    G.tytul_widoku((225, 150), "Plan")
    G.odcinki_siatki(_seg(R, "pompa_gora"))
    a.podzialka((225, 245), sk, 2)
    a.ramka("Pump", "1:20", "Elm-tree (common) pump: tube, bucket, valves, brake ±25°, spout",
            uwagi=("Section drawn from the parameters (tube Ø, height, brake, swing); valves and tube length: our "
                   "inference (chapter 09). The 3D model has only the outside.",))
    return a


# ======================================================================== działo
def gun(K_, jez, nr, z_ilu):
    S, R = K_["S"], K_["rzuty"]
    U = S.U["DZIALA"]
    a = Arkusz("gun-and-carriage", jez, "A3", nr, z_ilu)
    K = S.K
    sk = 15.0
    ob = S.ob.get("dzialo_L2")
    s0 = ob["polozenie"][1] if ob else 1.11
    zd = S.deck_side(s0)
    Kj = S.plik("kontrola.json") or {}
    odr = Kj.get("chodzenie", {}).get("odrzut_dzial_m", {}).get("dzialo_L2", U["odrzut"])
    # widok z boku: rzut 'rufa' (u = −x), wylot w lewo; v = z
    xin = 3.7
    B = Widok(a, 70.0, 95.0, sk, u0=-xin, v0=zd)
    B.obszar = (24, 26, 408, 128)
    B.tytul_widoku((26, 20), "Side elevation (looking forward), port gun run out")
    B.odcinki_siatki(_seg(R, "dzialo_rufa"))
    xo = float(S.H(s0, zd + 0.5)[0])
    B.linia([(-xo - 0.3, zd), (-0.6, zd)], "srednia")
    for z_ in (zd + K["FURTA_PROG"], zd + K["FURTA_NADPROZE"]):
        B.odcinek((-xo - 0.1, z_), (-xo + 0.2, z_), "srednia")
    B.odcinek((-xo + 0.06, zd), (-xo + 0.06, zd + K["FURTA_PROG"]), "srednia")
    B.odcinek((-xo + 0.06, zd + K["FURTA_NADPROZE"]), (-xo + 0.06, zd + 1.05), "srednia")
    _rysuj_liny(B, _liny(S, lambda L: L.get("do") == "dzialo_L2"), lambda p: (-p[0], p[2]), "cienka")
    B.wymiar((-xo, zd + K["FURTA_PROG"]), (-xo, zd), 10, kier="v", txt="%s %s" % (a.t("sill"), a.n(K["FURTA_PROG"])))
    B.wymiar((-xo, zd + K["FURTA_NADPROZE"]), (-xo, zd + K["FURTA_PROG"]), 10, kier="v",
             txt=a.n(K["FURTA_NADPROZE"] - K["FURTA_PROG"]))
    bl = S.ob.get("dzialo_L2_lufa")
    if bl:
        B.wymiar((-bl["max"][0], bl["max"][2] + 0.05), (-bl["min"][0], bl["max"][2] + 0.05), 8, kier="h",
                 txt="%s %s" % (a.t("barrel"), a.n(U["lufa"])))
        B.wymiar((-bl["min"][0] + 0.25, zd), (-bl["min"][0] + 0.25, zd + U["os_lufy"]), 8, kier="v",
                 txt="%s %s" % (a.t("trunnions"), a.n(U["os_lufy"])))
        xr = -ob["min"][0]
        B.wymiar((xr - U["lawa_dl"], zd - 0.05), (xr, zd - 0.05), -8, kier="h", txt="%s %s" % (a.t("carriage"), a.n(U["lawa_dl"])))
        B.odcinek((xr, zd), (xr + odr, zd), "ukryta")
        B.wymiar((xr, zd - 0.05), (xr + odr, zd - 0.05), -8, kier="h", txt="%s %s" % (a.t("recoil"), a.n(odr)))
    ub = -(bl["min"][0] if bl else 1.9)
    for p, t, pref in (((ub - 0.7, zd + 0.8), "Barrel, 6-pounder", (0.3, -1)), ((ub - 0.9, zd + 0.15), "Truck carriage", (0.2, 1)),
                       ((ub - 0.2, zd + 0.45), "Quoin under the breech", (1, -0.3)), ((ub - 1.4, zd + 0.42), "Breeching", (-1, 1)),
                       ((-xo, zd + 0.55), "Gun port", (-1, -1))):
        B.etykieta(p, a.t(t), pref, h=2.2)
    # rzut z góry: u = −x, v = s
    T = Widok(a, 70.0, 200.0, sk, u0=-xin, v0=s0)
    T.obszar = (24, 140, 408, 250)
    T.tytul_widoku((26, 136), "Plan")
    T.odcinki_siatki(_seg(R, "dzialo_gora", lambda u, v: (-v, u)))
    _rysuj_liny(T, _liny(S, lambda L: L.get("do") == "dzialo_L2"), lambda p: (-p[0], p[1]), "cienka")
    T.odcinek((-xo, s0 - 0.6), (-xo, s0 + 0.6), "gruba")
    T.wymiar((-xo, s0 - K["FURTA_SZER"] / 2), (-xo, s0 + K["FURTA_SZER"] / 2), -10, kier="v",
             txt="%s %s" % (a.t("port"), a.n(K["FURTA_SZER"])))
    T.wymiar((-2.2, s0 - U["lawa_szer"] / 2), (-2.2, s0 + U["lawa_szer"] / 2), 30, kier="v",
             txt="%s %s" % (a.t("carriage"), a.n(U["lawa_szer"])))
    for p, t, pref in (((-2.2, s0 + 0.45), "Side tackles to ringbolts in the side", (1, 1)),
                       ((-3.3, s0 + 0.45), "Breeching through the cascabel", (1, 1))):
        T.etykieta(p, a.t(t), pref, h=2.2)
    a.podzialka((300, 236), sk, 1)
    a.ramka("Gun and carriage", "1:15", "6-pounder on a truck carriage with breeching and side tackles",
            uwagi=("Gun, carriage and port projected from the 3D model; ropes from the rope data; recoil distance "
                   "from the model's clearance test.",))
    return a
