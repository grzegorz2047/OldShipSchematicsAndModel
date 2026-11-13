"""Arkusze kadłuba: plan linii teoretycznych, wręg wykreślony łukami, profil konstrukcyjny, przekrój na śródokręciu,
plan pokładu, rufa i dziób. Linie liczone analitycznie z parametrów (geometria.py); rufa i galion – rzut siatek
(model_rysunkowy.py) z wymiarami z parametrów."""
import math

import numpy as np

import geometria as G
from rysunki_svg import Arkusz, Widok


def _ark(nazwa, jez, nr, z, fmt="A3"):
    return Arkusz(nazwa, jez, fmt, nr, z)


# ======================================================================== plan linii
def lines_plan(K_, jez, nr, z_ilu):
    S = K_["S"]
    K = S.K
    a = _ark("lines-plan", jez, nr, z_ilu, "A1")
    sk = 48.0
    stations = list(S.PR.RZEDNE_S)
    WL = [-2.5, -2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5]
    BT = [1.0, 2.0, 3.0]
    s0, s1 = -15.4, 14.6
    prof = S.profil()
    # ---------------- profil (sheer plan)
    V = Widok(a, 34.0, 132.0, sk, u0=s0, v0=0.0)
    V.tytul_widoku((34, 30), "Sheer plan (profile)")
    for z in WL:
        sa, sf = S.aft_s(z) if z <= K["Z_PAWEZ_DOLNA"] else S.kd.stern_center_s(z), S.stem_s(z)
        V.odcinek((s0 + 0.1, z), (s1 - 0.1, z), "konstr")
        V.tekst((s0 - 0.15, z), ("WL " + a.n(z, 1)), 2.0, "end", dy=0.7)
    for s in stations:
        V.odcinek((s, -3.6), (s, 4.3), "konstr")
        V.tekst((s, 4.45), a.n(s, 2), 2.0, "middle")
    for x in BT:
        pts = S.wzdluzny(x)
        if pts:
            V.linia(pts, "cienka")
            V.etykieta(pts[len(pts) // 5], "%s %s" % (a.t("Buttock"), a.n(x, 1)), (-0.3, 1), h=2.2)
    V.linia(prof["wreb"], "cienka")
    V.linia(prof["stepka"], "gruba")
    V.linia(prof["lico"], "gruba")
    V.linia(prof["tyl_wreb"], "cienka")
    V.linia(prof["tyl_lico"] + [prof["tyl_lico"][0]], "gruba")
    V.odcinek(prof["tyl_lico"][0], prof["stepka"][0], "gruba")
    V.linia([prof["tyl_lico"][1]] + prof["rufa"], "gruba")
    V.linia(prof["reling"], "gruba")
    V.linia([prof["glowica"], (14.6, S.rail(14.6))], "gruba")
    V.odcinek(prof["lico"][-1], prof["glowica"], "gruba")
    V.linia(prof["poklad"], "srednia")
    V.linia(prof["rufowy"], "srednia")
    # fałszywa stępka (kreska 0,06 nad spodem)
    V.linia([(s, z + 0.06) for s, z in prof["stepka"]], "konstr")
    # pionowe: rufowy i dziobowy (s = −14 i +14 na wrębach przy pokładzie)
    for s_p, lab in ((-14.0, "AP"), (14.0, "FP")):
        V.os((s_p, -3.9), (s_p, 4.7))
        V.tekst((s_p, -4.25), lab, 2.4, bold=True)
    # wymiary główne
    V.wymiar((-14.0, -3.9), (14.0, -3.9), 9.0, "%s %s" % (a.t("Length between rabbets at the deck"), a.n(28.0)),
             kier="h")
    zk0 = S.zk(0.0) - K["STEPKA_WYS"]
    V.wymiar((0.0, 0.0), (0.0, zk0), 0.0, kier="v", txt=None)
    V.tekst((0.15, zk0 / 2), a.t("draught at s = 0"), 2.0, "start")
    V.odcinek((1.96, -3.6), (1.96, 4.3), "osiowa")
    V.tekst((1.96, -3.75), a.t("dead flat") + " s = " + a.n(1.96), 2.1, "middle", dy=3.0)
    V.wymiar((-14.0, -4.6), (1.96, -4.6), 4.5, kier="h", txt="%s %s" % (a.n(15.96), a.t("from AP")))
    V.etykieta(prof["poklad"][60], a.t("Deck at side"), (0.2, -1), h=2.2)
    V.etykieta(prof["rufowy"][10], a.t("Quarterdeck at side"), (0.3, -1), h=2.2)
    V.etykieta(prof["reling"][80], a.t("Rail (top of cap)"), (0.2, -1), h=2.2)
    V.etykieta(prof["wreb"][20], a.t("Keel rabbet"), (0.2, 1), h=2.2)
    V.etykieta(prof["stepka"][28], a.t("Keel and false keel"), (0.1, 1), h=2.2)
    V.etykieta(prof["lico"][6], a.t("Stem"), (1, 1), h=2.2)
    V.etykieta(((prof["tyl_lico"][0][0] + prof["tyl_lico"][1][0]) / 2, 0.2),
               "%s %s°" % (a.t("Sternpost, rake"), a.n(K["TUCK_RAKE"], 1)), (-1, 1), h=2.2)
    V.etykieta(prof["rufa"][3], a.t("Counter and transom"), (-1, -1), h=2.2)
    # ---------------- rzut z góry (half-breadth plan): oś na dole, lewa burta w górę
    y_cl = 330.0
    H_ = Widok(a, 34.0, y_cl, sk, u0=s0, v0=0.0)
    H_.tytul_widoku((34, y_cl - 4.3 * 20.83 - 8), "Half-breadth plan")
    H_.os((s0, 0), (s1, 0))
    for s in stations:
        H_.odcinek((s, 0), (s, 3.95), "konstr")
    for x in BT:
        H_.odcinek((s0 + 0.2, x), (s1 - 0.2, x), "konstr")
        H_.tekst((s1 + 0.1, x), "%s %s" % (a.t("B"), a.n(x, 1)), 2.0, "start", dy=0.7)
    for z in WL:
        pts = S.wodnica(z)
        pts = [(s, y) for s, y in pts if y > 0.131]
        if len(pts) > 2:
            H_.linia(pts, "cienka")
            k = int(len(pts) * (0.30 + 0.06 * WL.index(z)))
            H_.etykieta(pts[k], "WL " + a.n(z, 1), (0.2, 1) if z < 0.4 else (-0.2, -1), h=2.0, dmin=4)
    ss = np.linspace(-15.0, 14.2, 160)
    dk = [(float(s), float(S.H(s, S.deck_side(s))[0])) for s in ss]
    rl = [(float(s), float(S.H(s, min(S.rail(s), 4.5))[0])) for s in np.linspace(-14.9, 14.3, 160)]
    H_.linia(dk, "srednia")
    H_.linia(rl, "gruba")
    H_.etykieta(dk[40], a.t("Deck at side"), (0.3, -1), h=2.2)
    H_.etykieta(rl[120], a.t("Rail"), (0.3, 1), h=2.2)
    yb, sb, zb = S.najwieksza_szerokosc()
    H_.wymiar((sb, 0.0), (sb, yb), 6.0, kier="v", txt="%s %s" % (a.n(yb, 3), a.t("half-breadth")))
    H_.tekst((sb + 0.3, yb + 0.2), "%s 2 × %s = %s (z = %s)" % (a.t("greatest breadth"), a.n(yb, 3),
                                                              a.n(2 * yb, 2), a.n(zb, 2)), 2.1, "start")
    # ---------------- rzut wręgów (body plan)
    xc = 748.0
    B_ = Widok(a, xc, 132.0, sk, u0=0.0, v0=0.0)
    B_.tytul_widoku((xc - 80, 30), "Body plan")
    a.text((xc - 40, 38), a.t("aft body"), 2.4, "middle", italic=True)
    a.text((xc + 40, 38), a.t("fore body"), 2.4, "middle", italic=True)
    B_.os((0, -3.6), (0, 4.5))
    for z in WL:
        B_.odcinek((-3.9, z), (3.9, z), "konstr")
    for x in BT:
        for sg in (1, -1):
            B_.odcinek((sg * x, -3.4), (sg * x, 4.3), "konstr")
    for s in stations:
        sec = S.przekroj(s)
        sg = 1 if s >= 1.96 else -1
        pts = [(sg * y, z) for y, z in sec]
        B_.linia(pts, "srednia")
        if abs(s - 1.96) < 1e-6:
            B_.linia([(-y, z) for y, z in sec], "srednia")
        top = pts[-1]
        B_.etykieta(top, a.n(s, 2), (sg * 0.3, -1), h=2.0, dmin=3, dot=False)
        zd = S.deck_side(s)
        yd = float(S.H(s, zd)[0])
        B_.okrag((sg * yd, zd), 0.03, "bcienka", fill="#000")
    B_.wymiar((-yb, 0.0), (yb, 0.0), -88.0, kier="h", txt="%s %s" % (a.t("breadth"), a.n(2 * yb, 2)))
    a.podzialka((34, 566), sk, 10)
    # ---------------- tabela rzędnych (z badań, po wręgach)
    _tabela_rzednych(a, S, 34.0, 400.0)
    a.ramka("Lines plan", "1:48 (A1)", "Stations, waterlines every 0.5 m, buttocks 1, 2, 3 m; lines to the outside "
                                       "of the planking (generator surface)",
            uwagi=("On A3 the drawing is at 1:96 - use the scale bar.",
                   "Sheer plan and body plan: z above the design waterline; half-breadth plan: x from the centreline.",
                   "Lines as generated from the table; the run below WL -1.0 is not faired (bumps of 1-5 cm), "
                   "see guide chapter 02."))
    return a


def _tabela_rzednych(a, S, x0, y0):
    PR = S.PR
    kol = ["s", "z_df", a.t("keel"), a.t("rabbet")] + ["WL " + a.n(w, 1) for w in (-2.5, -2.0, -1.5, -1.0, -0.5, 0.0,
                                                                                   0.5)] + \
        [a.t("deck z"), a.t("deck y"), "b", "h_b", a.t("rail z"), a.t("rail y")]
    cw = 22.0
    rh = 5.2
    a.text((x0, y0 - 9), a.t("Table of offsets (research table, moulded, m)"), 3.0, "start", bold=True)
    for j, c in enumerate(kol):
        a.text((x0 + j * cw + cw / 2, y0 - 1.5), c, 2.1, "middle", bold=True)
    a.path([(x0, y0), (x0 + cw * len(kol), y0)], "cienka")
    for i, row in enumerate(PR.LINIE_WREGI):
        zd, keel, rab, beard, ys, deck, dhb, b, hb, rail, top = row
        vals = [zd + PR.LINIE_PRZESUNIECIE, zd, keel, rab] + list(ys) + [deck, dhb, b, hb, rail, top]
        y = y0 + (i + 1) * rh
        for j, v in enumerate(vals):
            a.text((x0 + j * cw + cw / 2, y - 1.4), "–" if v is None else a.n(v, 2), 2.1, "middle")
        a.path([(x0, y), (x0 + cw * len(kol), y)], "konstr")
    for j in range(len(kol) + 1):
        a.path([(x0 + j * cw, y0 - 5), (x0 + j * cw, y0 + len(PR.LINIE_WREGI) * rh)], "konstr")
    a.text((x0, y0 + len(PR.LINIE_WREGI) * rh + 5), a.t("Generator table (outside planking, lines parallel to the keel): "
                                                     "data/offsets.csv"), 2.2, "start", italic=True)
