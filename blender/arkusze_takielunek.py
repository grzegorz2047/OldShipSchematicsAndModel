"""Arkusze ożaglowania i takielunku (analitycznie z parametrów i rejestru lin): typy ożaglowania, plan drzewc,
olinowanie stałe, jufers i talrep, olinowanie ruchome, plan kołkowania, bloki i jufersy, plan żagli."""
import math
import re

import numpy as np

import nazwy_publiczne as NP
from rysunki_svg import Arkusz, Widok

KOLORY = {"fore_yard": "#1f77b4", "fore_topsail_yard": "#2ca02c", "fore_topgallant_yard": "#17becf",
          "main_yard": "#d62728", "main_topsail_yard": "#ff7f0e", "main_topgallant_yard": "#9467bd",
          "spritsail_yard": "#8c564b", "gaff": "#e377c2", "inne": "#555555"}


def _nazwa_en(t):
    return t.replace("_", " ")


# ------------------------------------------------------------------ wspólne: kadłub z boku, drzewca, liny
def kadlub_bok(V, S, pioro="gruba", fill=None):
    syl = S.sylwetka()
    V.linia(syl, pioro, zamknij=True, fill=fill, fop=0.25 if fill else None)
    p = S.profil()
    V.linia(p["galion"], "srednia")
    V.linia(p["poklad"], "cienka")
    V.linia(p["rufowy"], "cienka")
    V.odcinek((-16.5, 0), (23.5, 0), "osiowa")


def drzewce(V, a, b, d0, d1, pioro="srednia", kolor="#000"):
    (s0, z0), (s1, z1) = a, b
    L = math.hypot(s1 - s0, z1 - z0) or 1
    nx, nz = -(z1 - z0) / L, (s1 - s0) / L
    V.linia([(s0 + nx * d0 / 2, z0 + nz * d0 / 2), (s1 + nx * d1 / 2, z1 + nz * d1 / 2),
             (s1 - nx * d1 / 2, z1 - nz * d1 / 2), (s0 - nx * d0 / 2, z0 - nz * d0 / 2)], pioro, kolor, zamknij=True)


def drzewca_bok(V, S, sp, reje="opuszczone", etykiety=None, a=None):
    """Maszty, stengi, bramstengi, maszt snow, bukszpryt, bomstenga, gafel (z boku); reje widziane z noku (koła);
    marsy, ezelhofty, salingi."""
    rows = {r["spar"]: r for r in sp}
    for nm, r in rows.items():
        if r["kind"] == "yard":
            continue
        a_, b_ = (r["start"][1], r["start"][2]), (r["end"][1], r["end"][2])
        drzewce(V, a_, b_, r["d_max_m"], r["d_end_m"])
    for mk in ("fok", "grot"):
        M = S.M["maszty"][mk]
        o = M["osie"]
        top = M["top"]
        zt = top["z"]
        sc = top["c_s"]
        V.linia([(sc - top["Lb"], zt), (sc + top["Lf"], zt), (sc + top["Lf"], zt - 0.3), (sc - top["Lb"], zt - 0.3)],
                "srednia", zamknij=True)
        zc = o["z_cap"]
        s_c = S.ms(mk, zc)
        L_c = 4 * o["st"]["sr"] + 0.08
        V.linia([(s_c - 0.15, zc), (s_c - 0.15 + L_c, zc), (s_c - 0.15 + L_c, zc + M["cap_T"]), (s_c - 0.15, zc + M["cap_T"])],
                "srednia", zamknij=True)
        zx = o["st"]["z_head"]
        s_x = S.ms(mk, zx, "st")
        V.odcinek((s_x - 0.55, zx + 0.05), (s_x + 0.65, zx + 0.05), "srednia")
    for nm in ("fok", "fokmars", "fokbram", "grot", "grotmars", "grotbram", "blinda"):
        for rob, pio in ((False, "srednia"), (True, "ukryta")):
            if reje == "opuszczone" and rob:
                continue
            if reje == "robocze" and not rob:
                continue
            c = S.reja_c(nm, rob)
            V.okrag((c[1], c[2]), max(S.M["reje"][nm]["sr"] / 2, 0.06), pio)


def liny_bok(V, S, nazwy, warunek, kolor=lambda e: "#000", pioro="cienka", tylko_prawa=True):
    out = {}
    for L, (pl, e, typ) in zip(S.M["liny"], nazwy):
        if not warunek(L, e):
            continue
        p = L["p"]
        if tylko_prawa and min(q[0] for q in p) > 0.02 and not L.get("jednostronna"):
            continue
        V.linia([(q[1], q[2]) for q in p], pioro, kolor(e), w=max(0.13, min(0.6, L["d"] * 1000 / V.skala * 0.6)))
        out.setdefault(e, []).append(L)
    return out


def _sp(K_):
    return K_["dane"]["spars"]


def _nazwy(K_):
    return K_["dane"]["nazwy"]


# ======================================================================== plan drzewc
def spar_plan(K_, jez, nr, z_ilu):
    S = K_["S"]
    sp = _sp(K_)
    a = Arkusz("spar-plan", jez, "A3", nr, z_ilu)
    sk = 150.0
    V = Widok(a, 145.0, 222.0, sk, u0=0.0, v0=0.0)
    V.obszar = (22, 26, 296, 250)
    V.tytul_widoku((26, 20), "Spar plan, side elevation from starboard")
    kadlub_bok(V, S, "srednia")
    drzewca_bok(V, S, sp, reje="oba")
    rows = {r["spar"]: r for r in sp}
    # wysokości (z nad wodnicą) – linijka po lewej
    xs = -15.5
    for mk, xl in (("main", -16.3), ("fore", -17.9)):
        lm, tm, tg = rows[mk + "_mast"], rows[mk + "_topmast"], rows[mk + "_topgallant_mast"]
        marks = [(lm["start_z"] if "start_z" in lm else lm["start"][2], "heel"), (lm["deck_z_m"], "deck"),
                 (lm["top_platform_z_m"], "top"), (lm["cap_z_m"], "cap"), (tm["crosstrees_z_m"], "crosstrees"),
                 (tm["cap_z_m"], "topmast cap"), (tg["truck_z_m"], "truck")]
        prev = 0.0
        for z, nm in marks:
            V.wymiar((xl, prev), (xl, z), 0, kier="v", txt=a.n(z), h=1.8)
            prev = z
        V.tekst((xl, marks[-1][0] + 0.8), a.t("Fore mast" if mk == "fore" else "Main mast"), 1.9)
    for mk in ("fore", "main"):
        lm = rows[mk + "_mast"]
        for z, nm in ((lm["top_platform_z_m"], "Top"), (lm["cap_z_m"], "Cap"),
                      (rows[mk + "_topmast"]["crosstrees_z_m"], "Crosstrees"), (rows[mk + "_topgallant_mast"]["truck_z_m"],
                                                                              "Truck")):
            s_ = S.ms("fok" if mk == "fore" else "grot", z)
            V.etykieta((s_, z), "%s %s" % (a.t(nm), a.n(z)), (1, 0) if mk == "fore" else (-1, 0), h=1.9, dmin=4)
    for mk in ("fok", "grot"):
        o = S.M["maszty"][mk]["osie"]
        V.os((o["s_d"], o["z_heel"]), (S.ms(mk, 27.0), 27.0))
        V.wymiar_kat((o["s_d"], o["z_d"]), 6.0, 90, 90 + max(math.degrees(math.atan(o["tan_rake"])), 0.2) * 4,
                     "%s°" % a.n(math.degrees(math.atan(o["tan_rake"])), 1))
    bs = rows["bowsprit"]
    V.wymiar_kat((bs["start"][1], bs["start"][2]), 4.0, 0, bs["angle_deg"], "%s°" % a.n(bs["angle_deg"], 0))
    for nm, txt, pref in (("bowsprit", "Bowsprit", (1, 1)), ("jib_boom", "Jib-boom", (1, 1)), ("gaff", "Gaff", (-1, 1)),
                          ("snow_mast", "Snow mast", (-1, 0.3))):
        r = rows.get(nm)
        if r:
            m = ((r["start"][1] + r["end"][1]) / 2, (r["start"][2] + r["end"][2]) / 2)
            V.etykieta(m, "%s %s, Ø %s" % (a.t(txt), a.n(r["length_m"]), a.n(r["d_max_m"], 3)), pref, h=1.9)
    V.etykieta((S.reja_c("grot")[1], S.reja_c("grot")[2]), a.t("Yards end on: lowered (solid), hoisted (dashed)"),
               (-1, -0.3), h=1.9)
    # reje rozłożone (prawa kolumna)
    Y = Widok(a, 350.0, 40.0, sk, u0=0.0, v0=0.0)
    a.text((298, 33), a.t("Yards, gaff (length, diameter at slings / yardarm)") + "  1:150", 2.4, "start", bold=True)
    yy = 0.0
    for nm in ("main_yard", "fore_yard", "main_topsail_yard", "fore_topsail_yard", "spritsail_yard",
               "main_topgallant_yard", "fore_topgallant_yard", "gaff"):
        r = rows[nm]
        L = r["length_m"]
        if nm == "gaff":
            drzewce(Y, (-L / 2, yy), (L / 2, yy), r["d_max_m"], r["d_end_m"])
        else:
            drzewce(Y, (-L / 2, yy), (0, yy), r["d_end_m"], r["d_max_m"])
            drzewce(Y, (0, yy), (L / 2, yy), r["d_max_m"], r["d_end_m"])
        Y.tekst((-L / 2, yy), a.t(_nazwa_en(nm).capitalize()), 1.9, "start", dy=-1.6)
        Y.tekst((L / 2, yy), "%s · Ø %s / %s" % (a.n(L), a.n(r["d_max_m"], 3), a.n(r["d_end_m"], 3)), 1.9, "end",
                dy=3.6)
        yy -= 1.35
    # mars i ezelhoft (rzut z góry) 1:50
    T = Widok(a, 352.0, 205.0, 50.0, u0=0.0, v0=0.0)
    a.text((298, 160), a.t("Main top and cap, plan") + "  1:50", 2.4, "start", bold=True)
    M = S.M["maszty"]["grot"]
    top = M["top"]
    outer = top["outer"]
    T.linia([(y, x) for x, y in outer], "gruba", zamknij=True)
    W, Lt = top["W"], top["Lt"]
    hx, hb, hf = W * 0.20, Lt * 0.30, Lt * 0.20
    T.linia([(-hb, -hx), (hf, -hx), (hf, hx), (-hb, hx)], "srednia", zamknij=True)
    o = M["osie"]
    T.okrag((0.0 - Lt * 0.06, 0), o["sr"] * 0.31, "srednia")
    T.okrag((o["st"]["s_off"] - Lt * 0.06, 0), o["st"]["sr"] / 2, "srednia")
    T.wymiar((-top["Lb"], -W / 2), (top["Lf"], -W / 2), -5, kier="h")
    T.wymiar((top["Lf"], -W / 2), (top["Lf"], W / 2), 5, kier="v")
    T.etykieta((hf, hx), a.t("Lubber's hole"), (1, 1), h=1.9)
    T.tekst((0, W / 2 + 0.25), a.t("forward") + " →", 1.9)
    a.podzialka((26, 262), sk, 10)
    a.ramka("Spar plan", "1:150, 1:50", "Masts with rake, heights, yards lowered and hoisted, bowsprit, jib-boom, gaff",
            uwagi=("All lengths, diameters and heights: data/spars.csv.",))
    return a


# ======================================================================== olinowanie stałe
def _typ_stalej(e):
    t = re.sub(r"_(port|starboard)(_\d+)*$", "", e)
    t = re.sub(r"_\d+(_\d+)?$", "", t)
    return t


def standing_rigging(K_, jez, nr, z_ilu):
    S = K_["S"]
    sp, nazwy = _sp(K_), _nazwy(K_)
    O = S.O
    a = Arkusz("standing-rigging", jez, "A3", nr, z_ilu)
    sk = 150.0
    V = Widok(a, 130.0, 222.0, sk)
    V.obszar = (22, 26, 300, 250)
    V.tytul_widoku((26, 20), "Side elevation from starboard")
    kadlub_bok(V, S, "srednia")
    drzewca_bok(V, S, sp, reje="opuszczone")
    stale = ("wanty_grot", "wanty_fok", "sztagi", "podwantki", "wanty_stengowe", "paduny", "wanty_bramstengowe",
             "wiazanie", "sciagacze")
    grupy = liny_bok(V, S, nazwy, lambda L, e: L["g"] in stale, pioro="srednia")
    liny_bok(V, S, nazwy, lambda L, e: L["g"] in ("wyblinki", "talrepy"), pioro="konstr")
    typy = {}
    for e, Ls in grupy.items():
        typy.setdefault(_typ_stalej(e), []).append(Ls[0])
    for t, Ls in sorted(typy.items()):
        L = Ls[0]
        p = L["p"]
        m = p[len(p) // 2] if len(p) > 2 else [(p[0][i] + p[-1][i]) / 2 for i in range(3)]
        n = len(Ls)
        txt = "%s%s Ø %s" % (a.t(_nazwa_en(t).capitalize()), (" %d ×" % n) if n > 1 else "", a.n(L["d"] * 1000, 0))
        V.etykieta((m[1], m[2]), txt + " mm", (1 if m[1] > 2 else -1, -0.6 if m[2] > 10 else 0.6), h=1.8, dmin=4)
    # widok z przodu (od dziobu): u = x (lewa burta w prawo), v = z
    F = Widok(a, 355.0, 222.0, sk)
    F.obszar = (305, 26, 408, 250)
    F.tytul_widoku((307, 20), "View from ahead")
    sec = S.przekroj(1.96)
    F.linia([(y, z) for y, z in sec], "srednia")
    F.linia([(-y, z) for y, z in sec], "srednia")
    for mk in ("fok", "grot"):
        o = S.M["maszty"][mk]["osie"]
        F.odcinek((0, o["z_d"]), (0, o["br"]["z_top"]), "srednia")
        W = S.M["maszty"][mk]["W"]
        F.odcinek((-W / 2, S.M["maszty"][mk]["top"]["z"]), (W / 2, S.M["maszty"][mk]["top"]["z"]), "srednia")
    for L, (pl, e, typ) in zip(S.M["liny"], nazwy):
        if L["g"] in ("wanty_grot", "wanty_fok", "podwantki", "wanty_stengowe", "paduny", "wanty_bramstengowe",
                      "sciagacze"):
            F.linia([(q[0], q[2]) for q in L["p"]], "cienka")
    F.etykieta((-3.0, 4.5), a.t("Shrouds and backstays to the channels"), (1, 1), h=1.8)
    F.etykieta((1.4, 12.6), a.t("Futtock shrouds"), (1, 0.3), h=1.8)
    a.podzialka((26, 262), sk, 10)
    a.ramka("Standing rigging", "1:150", "Shrouds, topmast and topgallant shrouds, backstays, stays, bowsprit rigging",
            uwagi=("Each label: rope, number per side and diameter. Ratlines and lanyards thin.",
                   "Geometry and lengths: data/rigging-lines.json."))
    return a


# ======================================================================== jufers i talrep
def deadeye(K_, jez, nr, z_ilu):
    S = K_["S"]
    O = S.O
    a = Arkusz("deadeye-and-lanyard", jez, "A3", nr, z_ilu)
    d = O["D_WANTY_GROT"]
    D = O["JUFERS_Z_OBWODU"] * d * math.pi
    R = D / 2
    T_ = D / 2
    gap = O["JUFERS_ODSTEP"] * D
    dl = O["D_TALREP"]
    sk = 10.0
    V = Widok(a, 110.0, 150.0, sk)
    V.tytul_widoku((26, 20), "Pair of deadeyes, front view (main shroud)")
    zl, zu = 0.0, gap

    def jufers(c, up):
        V.okrag(c, R, "gruba")
        V.okrag(c, R * 0.86, "konstr")
        holes = []
        for ang in (90, 210, 330):
            t = math.radians(ang if up > 0 else ang + 180)
            h = (c[0] + R * 0.45 * math.cos(t), c[1] + R * 0.45 * math.sin(t))
            V.okrag(h, dl * 0.6, "srednia")
            holes.append(h)
        return holes
    hl = jufers((0, zl), 1)
    hu = jufers((0, zu), -1)
    pairs = [(hu[1], hl[1]), (hu[0], hl[0]), (hu[2], hl[2]), (hl[1], hu[0]), (hl[0], hu[2]), (hl[2], hu[1])]
    for k, (p, q) in enumerate(pairs):
        V.odcinek(p, q, "srednia" if k < 3 else "ukryta", kolor="#8a6d3b")
        m = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
        V.tekst(m, str(k + 1), 2.2, dx=2.2 if k < 3 else -2.2, kolor="#8a6d3b", bold=True)
    V.linia([(0, zu + R), (0.02, zu + R + 0.6)], "gruba")
    V.odcinek((-0.03, zu + R + 0.1), (0.05, zu + R + 0.6), "srednia")
    V.odcinek((0, zl - R), (0.0, zl - R - 0.55), "gruba")
    V.linia([(-0.025, zl - R - 0.55), (0.025, zl - R - 0.55), (0.025, zl - R - 0.6), (-0.025, zl - R - 0.6)], "srednia")
    V.wymiar((-R, zl), (R, zl), -R * 100 - 8, kier="h", txt="D = %s" % a.n(D, 3))
    V.wymiar((R + 0.05, zl), (R + 0.05, zu), 8, kier="v", txt="%s × D = %s" % (a.n(O["JUFERS_ODSTEP"], 1), a.n(gap, 3)))
    for p, t, pref in (((0.0, zu + R + 0.4), a.t("Shroud Ø %s mm, turned in round the upper deadeye") % a.n(d * 1000, 0), (1, 0)),
                       ((0.0, zl - R - 0.3), a.t("Chain plate (iron strop) to the wale"), (1, 0)),
                       (hu[0], a.t("Holes 3 × at 0.45 R"), (1, -0.4)),
                       ((0.06, (zl + zu) / 2), a.t("Lanyard Ø %s mm, 6 parts: 1-3 in front, 4-6 behind") % a.n(dl * 1000, 0),
                        (1, 0.4))):
        V.etykieta(p, t, pref, h=2.1)
    # widok z boku
    B = Widok(a, 300.0, 150.0, sk)
    B.tytul_widoku((235, 20), "Side view with channel")
    for zc in (zl, zu):
        B.linia([(-T_ / 2, zc - R), (T_ / 2, zc - R), (T_ / 2, zc + R), (-T_ / 2, zc + R)], "gruba", zamknij=True)
        B.odcinek((-T_ / 2 - 0.012, zc - R * 0.8), (-T_ / 2 - 0.012, zc + R * 0.8), "cienka")
    for x in (-T_ / 2 - dl / 2, T_ / 2 + dl / 2):
        B.odcinek((x, zl + R * 0.3), (x, zu - R * 0.3), "srednia", kolor="#8a6d3b")
    LS, LG = O["LAWA_SZER"], O["LAWA_GR"]
    zch = zl - R - 0.01
    B.linia([(-0.30, zch), (LS - 0.30, zch), (LS - 0.30, zch - LG), (-0.30, zch - LG)], "gruba", zamknij=True)
    B.odcinek((-0.30, zch + 0.4), (-0.30, zch - 0.9), "gruba")
    B.odcinek((0, zch - LG), (-0.27, zch - 0.85), "srednia")
    B.odcinek((0, zu + R), (0, zu + R + 0.6), "gruba")
    B.wymiar((-T_ / 2, zu + R), (T_ / 2, zu + R), 6, kier="h", txt="%s D/2 = %s" % (a.t("thickness"), a.n(T_, 3)))
    B.wymiar((-0.30, zch - LG), (LS - 0.30, zch - LG), -8, kier="h", txt="%s %s" % (a.t("channel"), a.n(LS)))
    B.wymiar((LS - 0.30, zch), (LS - 0.30, zch - LG), 8, kier="v", txt=a.n(LG))
    B.etykieta((-0.30, zch - 0.6), a.t("Ship's side"), (-1, 0), h=2.1)
    B.etykieta((0.15, zch - LG / 2), a.t("Channel"), (1, -1), h=2.1)
    tab = [("D = %s × %s × π · d" % (a.n(O["JUFERS_Z_OBWODU"], 1), "1"), ""),
           ("%s d = %s mm" % (a.t("main shroud"), a.n(d * 1000, 0)), "D = %s" % a.n(D, 3)),
           ("%s d = %s mm" % (a.t("fore shroud"), a.n(O["D_WANTY_FOK"] * 1000, 0)),
            "D = %s" % a.n(O["JUFERS_Z_OBWODU"] * O["D_WANTY_FOK"] * math.pi, 3)),
           (a.t("backstays"), "0.85 D"), (a.t("topmast shrouds (in the top)"), "D = 0.13"),
           (a.t("deadeye spacing on the channel"), a.n(O["JUFERSY_ROZSTAW"]))]
    x0, y0 = 235.0, 205.0
    a.text((x0, y0 - 6), a.t("Deadeye sizes (reference model)"), 2.6, "start", bold=True)
    for i, (k, v) in enumerate(tab):
        a.text((x0, y0 + i * 4.4), k, 2.1, "start")
        a.text((x0 + 80, y0 + i * 4.4), v, 2.1, "end")
    a.podzialka((26, 262), sk, 1)
    a.ramka("Deadeye and lanyard", "1:10", "Deadeye pair with lanyard, chain plate and channel",
            uwagi=("Lanyard rove as in the model: three parts in front, three behind; knot at the upper back hole.",))
    return a


# ======================================================================== olinowanie ruchome
def _kolor_ruchomej(e):
    for k in KOLORY:
        if e.startswith(k):
            return KOLORY[k]
    if e.startswith(("vang", "throat", "peak", "brail")):
        return KOLORY["gaff"]
    return KOLORY["inne"]


def running_rigging(K_, jez, nr, z_ilu):
    S = K_["S"]
    sp, nazwy = _sp(K_), _nazwy(K_)
    a = Arkusz("running-rigging", jez, "A3", nr, z_ilu)
    sk = 150.0
    V = Widok(a, 130.0, 222.0, sk)
    V.obszar = (22, 26, 300, 250)
    V.tytul_widoku((26, 20), "Side elevation from starboard, sails furled")
    kadlub_bok(V, S, "cienka")
    drzewca_bok(V, S, sp, reje="opuszczone")
    liny_bok(V, S, nazwy, lambda L, e: L["g"] in ("wanty_grot", "wanty_fok", "sztagi", "paduny", "wanty_stengowe",
                                                  "wanty_bramstengowe"), kolor=lambda e: "#bbbbbb", pioro="konstr")
    grupy = liny_bok(V, S, nazwy, lambda L, e: L["g"] in ("ruchome", "stropy"), kolor=_kolor_ruchomej, pioro="srednia")
    byly = set()
    for e, Ls in sorted(grupy.items()):
        L = Ls[0]
        p = L["p"]
        m = p[len(p) // 2] if len(p) > 2 else [(p[0][i] + p[-1][i]) / 2 for i in range(3)]
        e0 = re.sub(r"_(port|starboard)$", "", e)
        if e0 in byly:
            continue
        byly.add(e0)
        txt = "%s %s" % (a.t(_nazwa_en(e0)), a.n(L["d"] * 1000, 0))
        V.etykieta((m[1], m[2]), txt, (1 if m[1] > 2 else -1, -0.5), h=1.6, dmin=3, kolor=_kolor_ruchomej(e), max_d=45)
    x0, y0 = 307.0, 40.0
    a.text((x0, y0 - 6), a.t("Colour = yard or spar the rope works"), 2.4, "start", bold=True)
    for i, (k, c) in enumerate(KOLORY.items()):
        a.path([(x0, y0 + i * 5), (x0 + 8, y0 + i * 5)], "gruba", c, w=0.8)
        a.text((x0 + 11, y0 + i * 5 + 0.8), a.t({"inne": "other"}.get(k, _nazwa_en(k))), 2.2, "start")
    a.text((x0, y0 + 52), a.t("Numbers after the names: diameter in mm."), 2.0, "start", italic=True)
    a.text((x0, y0 + 57), a.t("Starboard ropes shown; port side mirrored."), 2.0, "start", italic=True)
    a.text((x0, y0 + 62), a.t("Standing rigging in light grey."), 2.0, "start", italic=True)
    a.podzialka((26, 262), sk, 10)
    a.ramka("Running rigging", "1:150", "Lifts, braces, clewlines, sheets, buntlines, halliards, ties, gaff ropes",
            uwagi=("Leads of the reference model (chapter 07); belaying points: belaying plan.",))
    return a


# ======================================================================== plan kołkowania
def belaying_plan(K_, jez, nr, z_ilu):
    S = K_["S"]
    RJ = K_["dane"]["rigging"]
    a = Arkusz("belaying-plan", jez, "A3", nr, z_ilu)
    sk = 80.0
    V = Widok(a, 26.0, 78.0, sk, u0=-15.4, v0=0.0)
    V.tytul_widoku((26, 20), "Belaying points, plan (reconstruction)")
    from arkusze_poklad import zarys_burty
    zo = zarys_burty(S)
    V.linia(zo, "gruba")
    V.linia([(s, -x) for s, x in zo], "gruba")
    V.odcinek(zo[0], (zo[0][0], -zo[0][1]), "gruba")
    P = S.plik("bryg_poklad.json")
    for p in P["powierzchnie"]:
        if p["nazwa"] in ("poklad_glowny", "poklad_rufowy"):
            V.linia([(q[1], q[0]) for q in p["wielokat"]], "cienka", zamknij=True)
    for mk in ("fok", "grot"):
        o = S.M["maszty"][mk]["osie"]
        V.okrag((o["s_d"], 0), o["sr"] / 2, "srednia")
    V.os((-15.2, 0), (14.8, 0))
    uzyte = [b for b in RJ["belaying_points"] if b["ropes"]]
    for b in RJ["belaying_points"]:
        x, s, z = b["position"]
        V.okrag((s, x), 0.04, "cienka", fill="#000" if b["ropes"] else "#fff")
    for b in uzyte:
        x, s, z = b["position"]
        V.etykieta((s, x), b["id"], (0.2, 1 if x >= 0 else -1), h=1.7, dmin=3, max_d=25, dot=False)
    x0, y0 = 26.0, 152.0
    a.text((x0, y0 - 6), a.t("Pin or kevel - rope belayed (reference model, reconstruction)"), 2.5, "start", bold=True)
    rows = []
    for b in uzyte:
        for r in b["ropes"]:
            rows.append((b["id"], r))
    n_kol = 3
    per = int(math.ceil(len(rows) / n_kol))
    for i, (pid, r) in enumerate(rows):
        cx, cy = x0 + (i // per) * 128.0, y0 + (i % per) * 3.55
        a.text((cx, cy), pid, 1.9, "start", bold=True)
        a.text((cx + 10, cy), a.t(_nazwa_en(r)), 1.9, "start")
    a.text((x0, 250), a.t("FF/MF fore/main fife rail, PF/SF/PM/SM pin rails port/starboard fore/main, K kevels; "
                          "open circles: free pins."), 2.0, "start", italic=True)
    a.ramka("Belaying plan", "1:80", "Which rope is belayed on which pin, cleat or kevel",
            uwagi=("Reconstruction for the reference model; pin rails along the bulwark are a likely anachronism "
                   "for 1710 (chapter 07).",))
    return a


# ======================================================================== bloki
def blocks(K_, jez, nr, z_ilu):
    S = K_["S"]
    a = Arkusz("blocks-and-deadeyes", jez, "A3", nr, z_ilu)
    d = 0.020
    sk = 2.0
    L = 8.5 * d
    st = 1.1 * d
    sd = 5.5 * d
    a.text((26, 22), a.t("Blocks, deadeye and heart - proportions in rope diameters d (drawn for d = 20 mm)") + "  1:2",
           3.2, "start", bold=True)

    def blok(xc, yc, n_kol=1, tytul="", L_=L, sheaves=None):
        V = Widok(a, xc, yc, sk)
        W = 0.7 * L_
        Tb = 0.5 * L_ + 0.4 * L_ * (n_kol - 1)
        # widok z przodu (lico): owal
        pts = [(W / 2 * math.cos(t), L_ / 2 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 49)]
        V.linia(pts, "gruba", zamknij=True)
        for (sy, sdia) in (sheaves or [(0.0, sd)]):
            V.linia([(-st / 2 * n_kol, sy - sdia / 2), (st / 2 * n_kol, sy - sdia / 2), (st / 2 * n_kol, sy + sdia / 2),
                     (-st / 2 * n_kol, sy + sdia / 2)], "ukryta", zamknij=True)
            V.okrag((0, sy), 0.006, "cienka")
        V.odcinek((0, L_ / 2), (0, L_ / 2 + 0.04), "srednia")
        V.wymiar((-W / 2, -L_ / 2), (W / 2, -L_ / 2), -6, kier="h", txt="%s d" % a.n(0.7 * L_ / d, 1))
        V.wymiar((W / 2, -L_ / 2), (W / 2, L_ / 2), 6, kier="v", txt="%s d" % a.n(L_ / d, 1))
        # z boku
        B = Widok(a, xc + 40 + Tb * 500, yc, sk)
        B.linia([(-Tb / 2, -L_ / 2 * 0.95), (Tb / 2, -L_ / 2 * 0.95), (Tb / 2, L_ / 2 * 0.95), (-Tb / 2, L_ / 2 * 0.95)],
                "gruba", zamknij=True)
        for k in range(n_kol):
            x = -Tb / 2 + Tb * (k + 0.5) / n_kol
            for (sy, sdia) in (sheaves or [(0.0, sd)]):
                B.linia([(x - st / 2, sy - sdia / 2), (x + st / 2, sy - sdia / 2), (x + st / 2, sy + sdia / 2),
                         (x - st / 2, sy + sdia / 2)], "ukryta", zamknij=True)
        B.wymiar((-Tb / 2, L_ / 2), (Tb / 2, L_ / 2), 6, kier="h", txt="%s d" % a.n(Tb / d, 1))
        a.text((xc - 30, yc - L_ * 250 - 8), a.t(tytul), 2.6, "start", bold=True)
    blok(60, 85, 1, "Single block")
    blok(190, 85, 2, "Double block")
    blok(320, 85, 1, "Fiddle block", L_=1.6 * L, sheaves=[(0.3 * L, sd), (-0.35 * L, sd * 0.7)])
    # jufers i serce
    V = Widok(a, 60, 205, sk)
    dsh = S.O["D_WANTY_GROT"]
    Dj = 1.5 * math.pi * dsh
    V.okrag((0, 0), Dj / 2 * 0.5, "gruba") if False else None
    k = 0.4
    Vj = Widok(a, 60, 205, 5.0)
    Vj.okrag((0, 0), Dj / 2, "gruba")
    for ang in (90, 210, 330):
        t = math.radians(ang)
        Vj.okrag((Dj / 2 * 0.45 * math.cos(t), Dj / 2 * 0.45 * math.sin(t)), 0.012, "srednia")
    Vj.wymiar((-Dj / 2, -Dj / 2), (Dj / 2, -Dj / 2), -6, kier="h", txt="D = 1.5 × π d_s = %s" % a.n(Dj, 3))
    a.text((30, 160), a.t("Deadeye (main shroud d_s = 49 mm), 1:5"), 2.6, "start", bold=True)
    Vh = Widok(a, 200, 205, 5.0)
    dst = S.O["D_GROTSZTAG"]
    Rh = 2.2 * dst
    Vh.linia([(Rh * math.cos(t), Rh * 1.15 * math.sin(t) - (0.25 * Rh if math.sin(t) < 0 else 0))
              for t in np.linspace(0, 2 * math.pi, 49)], "gruba", zamknij=True)
    Vh.okrag((0, 0.1 * Rh), Rh * 0.55, "srednia")
    Vh.wymiar((-Rh, -1.4 * Rh), (Rh, -1.4 * Rh), -4, kier="h", txt="%s d" % a.n(2 * Rh / dst, 1))
    a.text((165, 160), a.t("Heart (main stay collar, d = 80 mm), 1:5"), 2.6, "start", bold=True)
    tab = [("sheave thickness", "1.1 d"), ("sheave diameter", "5.5 d"), ("block length", "8-9 d"),
           ("block breadth", "0.7 × length"), ("block thickness", "0.5 × length + 0.4 × length per extra sheave"),
           ("deadeye diameter", "1.5 × circumference of the shroud"), ("deadeye thickness", "D/2"),
           ("heart (our inference)", "4.4 d outside, hole 2.4 d")]
    x0, y0 = 270.0, 168.0
    a.text((x0, y0 - 6), a.t("Rules (chapter 08)"), 2.6, "start", bold=True)
    for i, (k_, v) in enumerate(tab):
        a.text((x0, y0 + i * 4.3), a.t(k_), 2.1, "start")
        a.text((x0 + 38, y0 + i * 4.3), a.t(v), 2.1, "start")
    a.ramka("Blocks and deadeyes", "1:2, 1:5", "Proportions as multiples of the rope diameter",
            uwagi=("Reference model block lengths: 0.10-0.22 m (lifts 0.14, braces 0.16, topsail halliard 0.20).",))
    return a


# ======================================================================== plan żagli
def sail_plan(K_, jez, nr, z_ilu):
    S = K_["S"]
    sp = _sp(K_)
    a = Arkusz("sail-plan", jez, "A3", nr, z_ilu)
    sk = 150.0
    V = Widok(a, 130.0, 222.0, sk)
    V.obszar = (22, 26, 300, 250)
    V.tytul_widoku((26, 20), "Sail plan, all sails set (estimated from the spars)")
    kadlub_bok(V, S, "srednia")
    drzewca_bok(V, S, sp, reje="robocze")
    Z = S.zagle()
    suma = 0.0
    nazwy_en = {"fok": "Fore course", "fokmars": "Fore topsail", "fokbram": "Fore topgallant", "grot": "Main course",
                "grotmars": "Main topsail", "grotbram": "Main topgallant", "blinda": "Spritsail",
                "gaflowy": "Gaff sail (no boom)", "kliwer": "Jib", "sztaksel_fokstengi": "Fore topmast staysail",
                "sztaksel_grotstengi": "Main topmast staysail", "sztaksel_grota": "Main staysail"}
    for nm, z in Z.items():
        k = z["kontur"]
        V.linia(k, "srednia", zamknij=True, fill="#f3ead2", fop=0.55)
        suma += z["pole"]
        if z["typ"] == "square":
            (s0, zh), (s1, _), (s2, zf), (s3, _) = k
            n = z["szwy_glowica"]
            for i in range(1, n):
                f = i / n
                V.odcinek((s0 + (s1 - s0) * f, zh), (s3 + (s2 - s3) * f, zf), "konstr")
            for r in range(z.get("refy", 0)):
                zr = zh - 0.9 * (r + 1)
                fa = (zh - zr) / (zh - zf)
                V.odcinek((s0 + (s3 - s0) * fa, zr), (s1 + (s2 - s1) * fa, zr), "cienka")
        else:
            p0, p1 = k[0], k[-1]
            L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
            for i in range(1, int(L / 0.57)):
                f = i / (L / 0.57)
                q = (p0[0] + (p1[0] - p0[0]) * f, p0[1] + (p1[1] - p0[1]) * f)
                d = (k[1][0] - k[0][0], k[1][1] - k[0][1])
                V.odcinek(q, (q[0] + d[0] * (1 - f), q[1] + d[1] * (1 - f)), "konstr")
        cs = sum(p[0] for p in k) / len(k)
        cz = sum(p[1] for p in k) / len(k)
        V.tekst((cs, cz + 0.4), a.t(nazwy_en[nm]), 1.8, tlo=True)
        V.tekst((cs, cz - 0.6), "%s m²" % a.n(z["pole"], 0), 1.8, tlo=True)
    x0, y0 = 307.0, 40.0
    a.text((x0, y0 - 6), a.t("Sail areas (our inference)"), 2.6, "start", bold=True)
    for i, (nm, z) in enumerate(Z.items()):
        a.text((x0, y0 + i * 4.3), a.t(nazwy_en[nm]), 2.0, "start")
        a.text((x0 + 95, y0 + i * 4.3), "%s m²" % a.n(z["pole"], 1), 2.0, "end")
    a.text((x0, y0 + len(Z) * 4.3 + 2), a.t("Total"), 2.2, "start", bold=True)
    a.text((x0 + 95, y0 + len(Z) * 4.3 + 2), "%s m²" % a.n(suma, 0), 2.2, "end", bold=True)
    y1 = y0 + len(Z) * 4.3 + 12
    for i, t in enumerate(("Head 0.9 × yard; foot = head of the sail below", "(course: 0.95 × its yard);",
                           "yards hoisted to the working position;", "courses to 0.3 m above the rail;",
                           "cloths 0.61 m, seams every 0.57 m;", "topsails 2 reef bands (1710).",
                           "Square sails drawn in profile as if", "braced fore and aft (sail plan convention).")):
        a.text((x0, y1 + i * 3.8), a.t(t), 2.0, "start", italic=True)
    a.podzialka((26, 262), sk, 10)
    a.ramka("Sail plan", "1:150", "Outlines computed from the spars; seams, reef bands and area of each sail",
            uwagi=("The 3D model carries its sails furled; set sails here are an estimate (chapter 08).",))
    return a


# ======================================================================== typy ożaglowania
def ship_types(K_, jez, nr, z_ilu):
    S = K_["S"]
    a = Arkusz("ship-types", jez, "A3", nr, z_ilu)
    sk = 350.0
    Z = S.zagle()
    D = S.M["maszty"]

    def rig(xc, yc, tytul, typ):
        V = Widok(a, xc, yc, sk)
        a.text((xc - 50, yc - 90), a.t(tytul), 3.0, "start", bold=True)
        kadlub_bok(V, S, "srednia", fill="#cccccc")
        maszty = {"snow": [("fok", 0.0, 1.0), ("grot", 0.0, 1.0)], "brig": [("fok", 0.0, 1.0), ("grot", 0.0, 1.0)],
                  "brigantine": [("fok", 0.0, 1.0), ("grot", 0.0, 1.0)],
                  "ketch": [("grot", 3.4, 1.0), ("fok", -7.6 - (D["fok"]["osie"]["s_d"] - D["grot"]["osie"]["s_d"]), 0.8)]}[typ]
        etyk = []
        for i, (mk, ds, f) in enumerate(maszty):
            o = D[mk]["osie"]
            zd = o["z_d"]
            sc = lambda p: (p[0] + ds, zd + (p[1] - zd) * f)
            V.linia([sc((S.ms(mk, zd), zd)), sc((S.ms(mk, o["br"]["z_top"], "br"), o["br"]["z_top"]))], "gruba")
            nm_m = {"snow": ("Fore mast", "Main mast"), "brig": ("Fore mast", "Main mast"),
                    "brigantine": ("Fore mast", "Main mast"), "ketch": ("Main mast", "Mizzen mast")}[typ][i]
            etyk.append((sc((S.ms(mk, o["br"]["z_top"]), o["br"]["z_top"])), nm_m))
            square = [mk, mk + "mars", mk + "bram"]
            if typ == "brigantine" and mk == "grot":
                square = [mk + "mars", mk + "bram"]
            if typ == "ketch" and i == 1:
                square = [mk + "mars"]
            for nm in square:
                k = [sc(p) for p in Z[nm]["kontur"]]
                V.linia(k, "cienka", zamknij=True, fill="#f3ead2", fop=0.9)
            if (typ != "snow" and mk == "grot" and typ != "ketch") or (typ == "ketch" and i == 1):
                s_m = S.ms(mk, zd + 2.0) + ds
                peak = Z["gaflowy"]["kontur"][2]
                gaff_h = sc((S.ms(mk, D[mk]["top"]["z"] - 0.9), D[mk]["top"]["z"] - 0.9))
                kont = [(s_m - 0.2, zd + 3.0 * f), (gaff_h[0] - 0.2, gaff_h[1]),
                        (gaff_h[0] - 6.5 * f, gaff_h[1] + 4.5 * f), (gaff_h[0] - 10.5 * f, zd + 3.4 * f)]
                V.linia(kont, "cienka", zamknij=True, fill="#f3ead2", fop=0.9)
                if typ in ("brig", "brigantine", "ketch"):
                    V.odcinek(kont[0], kont[3], "srednia")
        if typ == "snow":
            sn = S.M["snow"]
            V.odcinek((sn["s"], sn["z0"]), (sn["s"] - (sn["z1"] - sn["z0"]) * sn["t"], sn["z1"]), "srednia")
            V.linia(Z["gaflowy"]["kontur"], "cienka", zamknij=True, fill="#f3ead2", fop=0.9)
            etyk.append(((sn["s"], sn["z0"] + 6), "Snow mast"))
        for nm in ("kliwer", "sztaksel_fokstengi"):
            k = Z[nm]["kontur"]
            if typ == "ketch":
                k = [(p[0] - 0.0, p[1]) for p in k]
            V.linia(k, "cienka", zamknij=True, fill="#f3ead2", fop=0.9)
        bs = S.M["bukszpryt"]
        V.odcinek(tuple(bs["heel"]), tuple(bs["end"]), "gruba")
        for p, t in etyk:
            V.etykieta(p, a.t(t), (1, -1), h=2.0, dmin=3)
    rig(95, 128, "Snow (reference model, about 1710)", "snow")
    rig(280, 128, "Later brig (gaff sail on the main mast, boom)", "brig")
    rig(95, 240, "Brigantine (no main course)", "brigantine")
    rig(280, 240, "Ketch (main and mizzen)", "ketch")
    a.ramka("Rigs on one hull", "1:350", "Snow, later brig, brigantine and ketch on the hull of the reference model",
            uwagi=("Schematic: same hull and spar proportions, sails set; no dimensions.",))
    return a
