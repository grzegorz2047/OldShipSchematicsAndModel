"""Arkusze konstrukcji kadłuba: wręg wykreślony łukami, profil konstrukcyjny, przekrój na śródokręciu.
Kadłub, berghołty, pokład, nadburcie, furty – z parametrów; elementy nieobecne w modelu 3D (nadstępka, wręgi,
belki, kolana, wzdłużnik) – z proporcji rozdziału 03 (our inference), słownik KONSTR."""
import math

import numpy as np

import geometria as G
from rysunki_svg import Arkusz, Widok


def _ark(nazwa, jez, nr, z, fmt="A3"):
    return Arkusz(nazwa, jez, fmt, nr, z)


def _x_luki(w, y):
    """Półszerokość wręgu wykreślonego łukami na wysokości y (None poniżej R0)."""
    (r0x, r0y), F, T, B = w["R0"], w["F"], w["T"], w["B"]
    if y < r0y:
        return None
    if y <= F[1]:
        return r0x + (y - r0y) / math.tan(math.radians(w["alpha"]))
    if y <= T[1]:
        C, R = w["Cf"], w["Rf"]
    elif y <= B[1]:
        C, R = w["Cb"], w["Rb"]
    else:
        C, R = w["Cu"], w["Ru"]
    d = R * R - (y - C[1]) ** 2
    return C[0] + math.sqrt(max(d, 0.0))


def wreg_srodkowy(S):
    """Wręg śródokręcia (s = +1,96) z tabeli badań; kąt wzniosu dna dobrany do rzędnych tej stacji."""
    row = [r for r in S.PR.LINIE_WREGI if abs(r[0]) < 1e-6][0]
    zd, keel, rab, beard, ys, deck, dhb, b, hb, rail, top = row
    wl = [-2.5, -2.0, -1.5, -1.0, -0.5, 0.0, 0.5]
    best = None
    for al in np.arange(6.0, 22.01, 0.25):
        w = G.wreg_lukami(b, hb, rail, top, al, r0=(S.K["STEPKA_SZER"] / 2, beard))
        e = sum((_x_luki(w, z) - y) ** 2 for z, y in zip(wl, ys) if _x_luki(w, z) is not None)
        if best is None or e < best[0]:
            best = (e, al, w)
    return best[2], row, math.sqrt(best[0] / len(wl))


def frame_arcs(K_, jez, nr, z_ilu):
    S = K_["S"]
    a = _ark("frame-construction-arcs", jez, nr, z_ilu)
    w, row, rms = wreg_srodkowy(S)
    zd, keel, rab, beard, ys, deck, dhb, b, hb, rail, top = row
    V = Widok(a, 205.0, 118.0, 25.0)
    V.tytul_widoku((30, 20), "Midship frame (s = +1.96) drawn with arcs, moulded")
    for z in np.arange(-3.0, 2.01, 0.5):
        V.odcinek((-2.4, z), (4.2, z), "konstr")
        V.tekst((4.25, z), "WL " + a.n(z, 1), 1.9, "start", dy=0.7)
    for x in np.arange(0.5, 4.01, 0.5):
        V.odcinek((x, -3.0), (x, 2.1), "konstr")
        V.tekst((x, -3.0), a.n(x, 1), 1.9, "middle", dy=3.2)
    V.os((0, -3.3), (0, 2.3))
    for C, R in ((w["Cf"], w["Rf"]), (w["Cb"], w["Rb"])):
        V.luk(C, R, -120, 60, "konstr")
    V.odcinek(w["R0"], (w["R0"][0] + 4.0 * math.cos(math.radians(w["alpha"])),
                        w["R0"][1] + 4.0 * math.sin(math.radians(w["alpha"]))), "punkt")
    V.odcinek(w["R0"], w["F"], "gruba")
    V.linia(G.luk_punkty(w["Cf"], w["Rf"], w["F"], w["T"]), "gruba")
    V.linia(G.luk_punkty(w["Cb"], w["Rb"], w["T"], w["B"]), "gruba")
    V.linia(G.luk_punkty(w["Cu"], w["Ru"], w["B"], w["N"]), "gruba")
    V.odcinek((0, keel), (w["R0"][0], keel), "srednia")
    V.odcinek((w["R0"][0], keel), w["R0"], "srednia")
    for nm, C in (("C_f", w["Cf"]), ("C_b", w["Cb"]), ("C_u", w["Cu"])):
        V.odcinek((C[0] - 0.08, C[1]), (C[0] + 0.08, C[1]), "cienka")
        V.odcinek((C[0], C[1] - 0.08), (C[0], C[1] + 0.08), "cienka")
        V.tekst(C, nm, 2.4, "end", dx=-1.5, dy=-1.5, bold=True)
    V.wymiar_r(w["Cf"], w["Rf"], -62, "R_f = %s" % a.n(w["Rf"]))
    V.wymiar_r(w["Cb"], w["Rb"], -20, "R_b = %s" % a.n(w["Rb"]))
    V.wymiar_r(w["Cu"], w["Ru"], 3, "R_u = %s" % a.n(w["Ru"]))
    for nm, p, pref in (("R0", w["R0"], (-1, 1)), ("F", w["F"], (1, 1)), ("T", w["T"], (1, 0.6)),
                        ("B", w["B"], (1, 0)), ("N", w["N"], (1, -1))):
        V.okrag(p, 0.035, "cienka", fill="#000")
        V.etykieta(p, "%s (%s; %s)" % (nm, a.n(p[0]), a.n(p[1])), pref, h=2.2)
    V.odcinek(w["R0"], (w["R0"][0] + 1.6, w["R0"][1]), "cienka")
    V.wymiar_kat(w["R0"], 1.4, 0.0, w["alpha"], "α = %s°" % a.n(w["alpha"], 2))
    for z, y in zip([-2.5, -2.0, -1.5, -1.0, -0.5, 0.0, 0.5], ys):
        V.odcinek((y - 0.05, z - 0.05), (y + 0.05, z + 0.05), "cienka")
        V.odcinek((y - 0.05, z + 0.05), (y + 0.05, z - 0.05), "cienka")
    sec = S.przekroj(1.96, z_top=rail)
    V.linia(sec, "ukryta")
    V.etykieta(sec[len(sec) // 3], a.t("generator frame, outside of planking"), (1, 1), h=2.2)
    V.wymiar((0, hb), (b, hb), -8.0, kier="h", txt="b = %s" % a.n(b))
    V.wymiar((b, 0.0), (b, hb), 22.0, kier="v", txt="h_b = %s" % a.n(hb))
    V.wymiar((top, rail), (b, rail), 6.0, kier="h", txt="Δ = %s" % a.n(b - top))
    x0, y0 = 26.0, 168.0
    rows = [("α", "%s°" % a.n(w["alpha"], 2)), ("R0", "(%s; %s)" % (a.n(w["R0"][0]), a.n(w["R0"][1]))),
            ("F", "(%s; %s)" % (a.n(w["F"][0]), a.n(w["F"][1]))), ("R_f = 0.38 b", a.n(w["Rf"])),
            ("C_f", "(%s; %s)" % (a.n(w["Cf"][0]), a.n(w["Cf"][1]))), ("R_b = 1.05 b", a.n(w["Rb"])),
            ("C_b", "(%s; %s)" % (a.n(w["Cb"][0]), a.n(w["Cb"][1]))),
            ("T", "(%s; %s)" % (a.n(w["T"][0]), a.n(w["T"][1]))),
            ("R_u", a.n(w["Ru"])), ("C_u", "(%s; %s)" % (a.n(w["Cu"][0]), a.n(w["Cu"][1]))),
            (a.t("rms vs. table"), a.n(rms, 3))]
    a.text((x0, y0 - 6), a.t("Arc data (m)"), 2.8, "start", bold=True)
    for i, (k, v) in enumerate(rows):
        a.text((x0, y0 + i * 4.6), k, 2.2, "start")
        a.text((x0 + 62, y0 + i * 4.6), v, 2.2, "end")
        a.path([(x0, y0 + i * 4.6 + 1.3), (x0 + 62, y0 + i * 4.6 + 1.3)], "konstr")
    a.podzialka((110, 262), 25.0, 2)
    a.ramka("Frame construction by arcs", "1:25",
            "Deadrise line, floor sweep, breadth sweep, top-timber sweep (chapter 02)",
            uwagi=("Crosses: research offsets of this station. Dashed: generator frame outside the planking.",
                   "α fitted to the research offsets of the station (least squares)."))
    return a


KONSTR = dict(stepka_pod_wrebem=0.25, stepka_nad_wrebem=0.05, zamek_dl=1.0, fartuch=0.40,
              dennik_nad_wrebem=0.22, nadstepka=0.28, nadstepka_szer=0.25, wreg_szer=0.20, wreg_gr_stepka=0.26,
              wreg_gr_reling=0.12, belka_wys=0.20, belki_co=1.2, wzdluznik=(0.30, 0.12), kolano_gr=0.15,
              kolano_ramie=0.9, wewn_poszycie=0.05)


def _offset(pts, d):
    out = []
    for i in range(len(pts)):
        p0, p1 = np.array(pts[max(i - 1, 0)]), np.array(pts[min(i + 1, len(pts) - 1)])
        t = p1 - p0
        n = np.array([-t[1], t[0]]) / (np.hypot(*t) or 1)
        dd = d(i) if callable(d) else d
        out.append(tuple(map(float, np.array(pts[i]) + n * dd)))
    return out


def hull_profile(K_, jez, nr, z_ilu):
    S = K_["S"]
    K, KS = S.K, KONSTR
    a = _ark("hull-profile-structure", jez, nr, z_ilu)
    sk = 100.0
    V = Widok(a, 32.0, 72.0, sk, u0=-15.8, v0=0.0)
    V.tytul_widoku((30, 20), "Structural profile (planking removed, one frame in four)")
    def rysuj(V, glowny):
        E = V.etykieta if glowny else (lambda *x, **k: None)
        Wm = V.wymiar if glowny else (lambda *x, **k: None)
        prof = S.profil()
        zk = S.zk
        s_heel = prof["tyl_wreb"][0][0]
        s_ff = S.K["DZIOB"][0][0]
        L_k = s_ff - s_heel
        zamki = [s_heel + L_k / 3, s_heel + 2 * L_k / 3]
        top = [(s, zk(s) + KS["stepka_nad_wrebem"]) for s in np.linspace(s_heel, s_ff, 30)]
        bot = [(s, zk(s) - KS["stepka_pod_wrebem"]) for s in np.linspace(s_heel, s_ff, 30)]
        V.linia(top + bot[::-1], "gruba", zamknij=True)
        V.linia(prof["stepka"], "srednia")
        for zs in zamki:
            z0 = zk(zs)
            V.linia([(zs - KS["zamek_dl"] / 2, z0 + 0.05), (zs - KS["zamek_dl"] / 2, z0 - 0.05),
                     (zs + KS["zamek_dl"] / 2, z0 - 0.05), (zs + KS["zamek_dl"] / 2, z0 - 0.25)], "cienka")
            E((zs, z0 - 0.1), "%s %s" % (a.t("scarph"), a.n(KS["zamek_dl"], 1)), (0.3, 1), h=2.1)
        V.linia(prof["lico"], "gruba")
        st = prof["wreb"][40:]
        V.linia(st, "srednia")
        fart = _offset(st, KS["fartuch"])
        V.linia(fart, "cienka")
        V.linia(prof["tyl_lico"], "gruba")
        V.linia(prof["tyl_wreb"], "srednia")
        br = [(r[0] + S.PR.LINIE_PRZESUNIECIE, r[3]) for r in S.PR.LINIE_WREGI if r[3] is not None]
        dw = [(s, z) for s, z in br if s < 2.0 and z > zk(s) + 0.12]
        if dw:
            dw = [(prof["tyl_wreb"][0][0] + 0.05, dw[0][1])] + dw + [(dw[-1][0] + 2.0, zk(dw[-1][0] + 2.0) + 0.05)]
            V.linia(dw, "srednia")
        nd = [(s, zk(s) + KS["dennik_nad_wrebem"]) for s in np.linspace(-9.0, 9.6, 20)]
        nu = [(s, zk(s) + KS["dennik_nad_wrebem"] + KS["nadstepka"]) for s in np.linspace(-9.0, 9.6, 20)]
        V.linia(nd + nu[::-1], "srednia", zamknij=True)
        rozst = K["PILERS_ROZSTAW"]
        ramy = list(np.arange(-12.48, 12.0, 4 * rozst))
        dws, dwz = [p[0] for p in dw], [p[1] for p in dw]
        for s in ramy:
            z0 = zk(s) + KS["dennik_nad_wrebem"]
            if dw and dws[0] <= s <= dws[-1]:
                z0 = max(z0, float(np.interp(s, dws, dwz)))
            z1 = S.rail(s)
            for d in (-KS["wreg_szer"] / 2, KS["wreg_szer"] / 2):
                V.odcinek((s + d, z0), (s + d, z1), "cienka")
        Wm((ramy[7], S.rail(ramy[7]) + 0.2), (ramy[8], S.rail(ramy[8]) + 0.2), 4,
                 txt="4 × %s = %s" % (a.n(rozst), a.n(4 * rozst)), kier="h")
        ss = np.linspace(-14.0, 13.6, 80)
        for (o, d_, w_) in K["BERGHOLTY"]:
            for dd in (o, d_):
                V.linia([(s, S.deck_side(s) - dd) for s in ss], "cienka" if w_ < 0.05 else "srednia")
        zcl = lambda s: S.deck_side(s) - K["POKLAD_GR"] - KS["belka_wys"]
        ss2 = np.linspace(-5.0, 13.0, 60)
        V.linia([(s, zcl(s)) for s in ss2], "ukryta")
        V.linia([(s, zcl(s) - KS["wzdluznik"][0]) for s in ss2], "ukryta")
        belki = list(np.arange(-4.6, 12.5, KS["belki_co"]))
        for s in belki:
            zc = S.deck_c(s) - K["POKLAD_GR"]
            V.linia([(s - 0.11, zc), (s + 0.11, zc), (s + 0.11, zc - 0.2), (s - 0.11, zc - 0.2)], "srednia", zamknij=True)
            sg = 1 if s > 1.96 else -1
            zb = zcl(s)
            V.linia([(s + sg * 0.11, zb), (s + sg * 0.11, zb - KS["kolano_ramie"])], "cienka")
        for s in np.arange(-14.0, -5.3, KS["belki_co"]):
            zc = S.deck_c(s) + K["POLPOKLAD_H"] - K["POKLAD_GR"]
            V.linia([(s - 0.11, zc), (s + 0.11, zc), (s + 0.11, zc - 0.2), (s - 0.11, zc - 0.2)], "srednia", zamknij=True)
        V.linia(prof["poklad"], "cienka")
        V.linia(prof["rufowy"], "cienka")
        V.linia(prof["reling"], "srednia")
        V.linia([prof["tyl_lico"][1]] + prof["rufa"], "srednia")
        V.linia(prof["galion"], "cienka")
        for sp in K["FURTY_S"] + K["FURTY_ZAMKNIETE_S"]:
            zd = S.deck_side(sp)
            V.linia([(sp - 0.3, zd + K["FURTA_PROG"]), (sp + 0.3, zd + K["FURTA_PROG"]),
                     (sp + 0.3, zd + K["FURTA_NADPROZE"]), (sp - 0.3, zd + K["FURTA_NADPROZE"])], "ukryta", zamknij=True)
        for mk in ("fok", "grot"):
            o = S.M["maszty"][mk]["osie"]
            V.os((S.ms(mk, o["z_heel"]), o["z_heel"]), (S.ms(mk, 4.2), 4.2))
        lab = [((zamki[1] + 2, zk(zamki[1] + 2) - 0.18), "Keel (moulded 0.30, sided 0.26)", (0.2, 1)),
               ((4.0, zk(4.0) - 0.28), "False keel 0.06", (0.3, 1)),
               (prof["lico"][len(prof["lico"]) // 2], "Stem (moulded 0.35)", (1, 0)),
               (fart[len(fart) // 2], "Apron 0.40", (-1, -1)),
               (prof["lico"][3], "Gripe (forefoot)", (1, 1)),
               (prof["tyl_lico"][0], "Sternpost (0.40 heel, 0.28 head)", (-1, 1)),
               (dw[2] if dw else (-10, -2), "Deadwood aft (to the bearding line)", (1, -1)),
               (nu[12], "Keelson 0.25 × 0.28 on the floors", (0.2, -1)),
               ((ramy[3], 0.0), "Frames 0.20 sided, room and space 0.52", (0.3, -1)),
               ((8.0, S.deck_side(8.0) - 0.13), "Main wales 2 × 0.26 + 0.22", (0.3, 1)),
               ((6.2, zcl(6.2) - 0.15), "Clamp 0.30 × 0.12 (hidden)", (0.3, 1)),
               ((belki[4], S.deck_c(belki[4]) - 0.2), "Deck beams 0.22 × 0.20, every 1.2", (0.2, -1)),
               ((belki[9] + 0.11, S.deck_side(belki[9]) - 0.7), "Hanging knee, arm 0.9", (0.2, 1)),
               ((K["FURTY_S"][2], S.deck_side(K["FURTY_S"][2]) + 0.6), "Gun port 0.60 × 0.50 (hidden)", (0.2, -1)),
               (prof["galion"][5] if prof["galion"] else (15, 1), "Knee of the head", (1, -1)),
               ((-10.0, S.deck_c(-10) + K["POLPOKLAD_H"] - 0.17), "Quarterdeck beams", (0.2, -1))]
        for p, t, pref in lab:
            E(p, a.t(t), pref, h=2.2)
        Wm((s_heel, zk(s_heel) - 0.31), (s_ff, zk(s_ff) - 0.31), -12, kier="h",
                 txt="%s %s" % (a.t("keel"), a.n(L_k)))
    rysuj(V, True)
    for (x0, y0, x1, y1, s0, z0, tyt) in ((150.0, 158.0, 262.0, 252.0, 9.0, -3.6, "Bow detail"),
                                           (272.0, 150.0, 345.0, 252.0, -15.8, -3.6, "Stern detail")):
        Vd = Widok(a, x0, y1 - 4, 75.0, u0=s0, v0=z0)
        Vd.obszar = (x0, y0, x1, y1)
        Vd.tytul_widoku((x0, y0 - 4), tyt)
        rysuj(Vd, False)
        prof_ = S.profil()
        if s0 > 0:
            Vd.wymiar(prof_["glowica"], (prof_["glowica"][0] - S.K["DZIOBNICA_GR"], prof_["glowica"][1]), 5, kier="h")
            Vd.wymiar((S.K["DZIOB"][0][0], S.zk(S.K["DZIOB"][0][0]) - 0.31), (14.0, 1.85), 0, kier="h", txt="%s" % a.n(14.0 - S.K["DZIOB"][0][0]))
        else:
            tw = prof_["tyl_wreb"]
            Vd.wymiar_kat(tw[0], 2.5, 90.0, 90.0 + S.K["TUCK_RAKE"], "%s°" % a.n(S.K["TUCK_RAKE"], 1))
            Vd.odcinek(tw[0], (tw[0][0], tw[0][1] + 3.0), "konstr")
    D = Widok(a, 70.0, 214.0, 10.0)
    D.tytul_widoku((30, 146), "Keel section")
    hs = K["STEPKA_SZER"] / 2
    D.linia([(-hs, 0.05), (hs, 0.05), (hs, -0.25), (-hs, -0.25)], "gruba", zamknij=True)
    D.linia([(-hs, -0.25), (hs, -0.25), (hs, -0.31), (-hs, -0.31)], "srednia", zamknij=True)
    pl = K["POSZYCIE_GR"]
    for sg in (1, -1):
        D.linia([(sg * hs, -0.02), (sg * (hs + 0.25), 0.04), (sg * (hs + 0.25), 0.04 + pl),
                 (sg * (hs - 0.02), 0.03 + pl)], "srednia")
    D.os((0, -0.35), (0, 0.15))
    D.wymiar((-hs, -0.31), (hs, -0.31), -6, kier="h")
    D.wymiar((hs, 0.05), (hs, -0.25), 10, kier="v")
    D.wymiar((hs, -0.25), (hs, -0.31), 24, kier="v")
    D.etykieta((hs + 0.2, 0.04 + pl), a.t("Garboard strake 0.065"), (1, -1), h=2.1)
    D.etykieta((0, -0.28), a.t("False keel"), (-1, 1), h=2.1)
    D.etykieta((-hs, 0.0), a.t("Rabbet"), (-1, -0.5), h=2.1)
    a.podzialka((230, 132), sk, 5)
    a.podzialka((150, 270), 75.0, 3)
    a.ramka("Hull structure - profile", "1:100, 1:75, 1:10", "Backbone, frames, wales, clamp, beams and knees",
            uwagi=("Members not built in the 3D model (keelson, frames, beams, knees, apron) use the proportions of "
                   "chapter 03 (our inference).",))
    return a


def midship_section(K_, jez, nr, z_ilu):
    S = K_["S"]
    K, KS = S.K, KONSTR
    a = _ark("midship-section", jez, nr, z_ilu)
    s = 1.96
    V = Widok(a, 70.0, 124.0, 25.0)
    V.tytul_widoku((30, 20), "Midship section s = +1.96, port half (looking forward)")
    zk = S.zk(s)
    hs = K["STEPKA_SZER"] / 2
    pl = K["POSZYCIE_GR"]
    zd = S.deck_side(s)
    zr = S.rail(s)
    sec = [(y, z) for y, z in S.przekroj(s, z_top=zr) if z >= zk - 0.001]
    mould = _offset(sec, pl)
    n_m = len(mould)
    fr_in = _offset(mould, lambda i: (KS["wreg_gr_stepka"] + (KS["wreg_gr_reling"] - KS["wreg_gr_stepka"]) * i / n_m))
    V.linia(sec, "gruba")
    V.linia(mould, "srednia")
    V.linia(fr_in, "srednia")
    for zj in (-1.9, -0.3, zd + 0.25):
        i = int(np.argmin([abs(p[1] - zj) for p in mould]))
        V.odcinek(mould[i], fr_in[i], "srednia")
    for zj, nm, pref in ((-2.35, "Floor", (1, 1)), (-1.1, "First futtock", (1, 0.4)), (0.4, "Second futtock", (1, 0)),
                         (zd + 0.6, "Top timber", (1, -0.4))):
        i = int(np.argmin([abs(p[1] - zj) for p in mould]))
        V.etykieta(((mould[i][0] + fr_in[i][0]) / 2, mould[i][1]), a.t(nm), pref, h=2.2)
    V.linia([(0, zk + 0.05), (hs, zk + 0.05), (hs, zk - 0.25), (0, zk - 0.25)], "gruba")
    V.linia([(hs, zk - 0.25), (hs, zk - 0.31), (0, zk - 0.31)], "srednia")
    V.os((0, zk - 0.6), (0, zr + 0.5))
    zn = zk + KS["dennik_nad_wrebem"]
    V.linia([(0, zn), (KS["nadstepka_szer"] / 2, zn), (KS["nadstepka_szer"] / 2, zn + KS["nadstepka"]),
             (0, zn + KS["nadstepka"])], "gruba")
    V.okrag((hs + 0.08, zk + 0.12), 0.04, "cienka")
    cz = [p for p in _offset(fr_in, KS["wewn_poszycie"]) if zn + 0.1 < p[1] < zd - 0.6]
    V.linia(cz, "cienka")
    yd = float(S.H(s, zd)[0]) - pl - KS["wreg_gr_reling"] - 0.02
    beam_top = [(float(x), S.deck_c(s) - K["WYPUKLOSC"] * (x / K["POL_B"]) ** 2 - K["POKLAD_GR"])
                for x in np.linspace(0, yd, 20)]
    V.linia(beam_top + [(p[0], p[1] - KS["belka_wys"]) for p in beam_top[::-1]], "gruba", zamknij=True)
    deck_top = [(x, z + K["POKLAD_GR"]) for x, z in beam_top]
    V.linia(deck_top, "srednia")
    for x in np.arange(0.24, yd, 0.24):
        zz = S.deck_c(s) - K["WYPUKLOSC"] * (x / K["POL_B"]) ** 2
        V.odcinek((x, zz), (x, zz - K["POKLAD_GR"]), "konstr")
    zb = beam_top[-1][1] - KS["belka_wys"]
    wc, tc = KS["wzdluznik"]
    V.linia([(yd, zb), (yd - tc, zb), (yd - tc, zb - wc), (yd, zb - wc)], "srednia")
    kr, kg = KS["kolano_ramie"], KS["kolano_gr"]
    V.linia([(yd - tc, zb - wc), (yd - tc, zb - kr), (yd - tc - kg, zb - kr + 0.1), (yd - tc - kg, zb - kg),
             (yd - kr, zb), (yd - kr + 0.1, zb)], "srednia")
    ww, wh = K["WODOSCIEK"]
    zdt = deck_top[-1][1]
    V.linia([(yd, zdt), (yd - ww, zdt), (yd - ww * 0.4, zdt + wh), (yd, zdt + wh)], "srednia")
    xo = float(S.H(s, zr)[0])
    V.linia([(xo - K["NADBURCIE_GR"], zdt + wh), (xo - K["NADBURCIE_GR"], zr)], "srednia")
    V.linia([(xo - K["NADBURCIE_GR"] - 0.06, zdt + wh), (xo - K["NADBURCIE_GR"] - 0.06, zd + K["FURTA_PROG"])], "cienka")
    rw, rg = K["RELING_SZER"], K["RELING_GR"]
    xr = xo - K["NADBURCIE_GR"] / 2
    V.linia([(xr - rw / 2, zr), (xr + rw / 2, zr), (xr + rw / 2, zr + rg), (xr - rw / 2, zr + rg)], "gruba", zamknij=True)
    for (o, d_, pr) in K["BERGHOLTY"]:
        z0, z1 = zd - d_, zd - o
        x0_, x1_ = float(S.H(s, z0)[0]), float(S.H(s, z1)[0])
        V.linia([(x0_, z0), (x0_ + pr, z0 + 0.02), (x1_ + pr, z1 - 0.02), (x1_, z1)], "gruba")
    zp0, zp1 = zd + K["FURTA_PROG"], zd + K["FURTA_NADPROZE"]
    V.odcinek((xo - 0.2, zp0), (xo, zp0), "ukryta")
    V.odcinek((xo - 0.2, zp1), (xo, zp1), "ukryta")
    zl = zr - 0.035
    LS, LG = S.O["LAWA_SZER"], S.O["LAWA_GR"]
    V.linia([(xo, zl), (xo + LS, zl), (xo + LS, zl - LG), (xo, zl - LG)], "ukryta")
    V.linia([(xo, zl - 0.12), (xo + 0.08, zl - 0.12), (xo + 0.08, zl - 0.30), (xo, zl - 0.30)], "ukryta")
    labs = [((hs, zk - 0.1), "Keel", (-1, 1)), ((hs * 0.5, zk - 0.28), "False keel", (1, 1)),
            ((KS["nadstepka_szer"] / 2, zn + 0.2), "Keelson", (1, -1)), ((hs + 0.08, zk + 0.12), "Limber hole", (1, 1)),
            (cz[len(cz) // 2] if cz else (2, -1), "Ceiling 0.05", (-1, 0)),
            ((yd - tc / 2, zb - wc / 2), "Clamp 0.30 × 0.12", (-1, -0.3)),
            ((yd * 0.5, beam_top[10][1] - 0.1), "Deck beam 0.22 × 0.20, camber 0.12", (0, 1)),
            ((yd - tc - kg / 2, zb - kr * 0.6), "Hanging knee", (-1, 0.2)),
            ((yd - ww / 2, zdt + wh / 2), "Waterway 0.25 × 0.10", (-1, -1)),
            ((yd * 0.3, deck_top[6][1]), "Deck planks 0.07", (0, -1)),
            ((xo - 0.17, zd + 0.22), "Spirketting 0.06", (-1, 0)),
            ((xo - 0.07, zd + 0.95), "Bulwark 0.14", (-1, 0.3)),
            ((xr, zr + rg), "Rail cap 0.30 × 0.07", (-0.3, -1)),
            ((xo + 0.03, zd - 0.13), "Main wale", (1, 0)), ((xo + 0.01, zd - 0.37), "Middle strake", (1, 0.2)),
            ((xo + 0.03, zd - 0.61), "Main wale", (1, 0.4)),
            ((xo + LS / 2, zl - 0.05), "Channel (at the masts only)", (1, -1)),
            ((xo + 0.04, zl - 0.21), "Channel wale", (1, 0)),
            ((xo, zp0), "Port sill", (1, 0.4)), ((xo, zp1), "Port lintel", (1, -0.2)),
            (sec[len(sec) // 4], "Planking 0.065", (1, 0.5))]
    for p, t, pref in labs:
        V.etykieta(p, a.t(t), pref, h=2.2)
    xd = xo + 0.9
    V.wymiar((xd, 0), (xd, zd), 10, kier="v", txt="%s %s" % (a.t("deck at side"), a.n(zd)))
    V.wymiar((xd, zd), (xd, zr), 10, kier="v", txt=a.n(zr - zd))
    V.wymiar((xd, zk - 0.31), (xd, 0), 10, kier="v")
    V.wymiar((0, zr + rg), (xo, zr + rg), 12, kier="h", txt="%s %s" % (a.t("half-breadth at rail"), a.n(xo)))
    yb = float(S.H(s, 0.4)[0])
    V.wymiar((0, zk - 0.31), (yb, zk - 0.31), -6, kier="h", txt="%s %s" % (a.t("half-breadth"), a.n(yb)))
    V.wymiar((xo - 0.6, zd), (xo - 0.6, zp0), -8, kier="v", txt=a.n(K["FURTA_PROG"]))
    V.wymiar((xo - 0.6, zp0), (xo - 0.6, zp1), -8, kier="v", txt=a.n(K["FURTA_NADPROZE"] - K["FURTA_PROG"]))
    V.odcinek((-0.3, 0), (xo + 1.6, 0), "osiowa")
    V.tekst((xo + 1.65, 0), "DWL", 2.2, "start", dy=0.8)
    a.podzialka((30, 270), 25.0, 2)
    a.ramka("Midship section", "1:25", "Structure at the dead flat; planking outside the generator surface",
            uwagi=("Keelson, frames, ceiling, clamp, beams and knees: proportions of chapter 03 (our inference);",
                   "hull surface, wales, deck, bulwark, rail and ports from the model parameters."))
    return a
