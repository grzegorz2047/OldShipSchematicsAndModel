"""Arkusze: plan pokładu (rzut z góry z wyposażeniem, przejściami, strefami odrzutu i stanowiskami) oraz rufa
i dziób (rzuty siatek z usuwaniem linii zasłoniętych + wymiary z parametrów)."""
import math

import numpy as np

import nazwy_publiczne as NP
from rysunki_svg import Arkusz, Widok, zakres_odcinkow


def _czytelna(pl):
    e = NP.en(pl) or pl
    return e.replace("_", " ")


def zarys_burty(S, z_fun=None, s0=-15.0, s1=14.5, n=160):
    """Zarys zewnętrzny kadłuba na wysokości relingu (rzut z góry): lista (s, x) lewej burty."""
    out = []
    for s in np.linspace(s0, s1, n):
        z = S.rail(s) if z_fun is None else z_fun(s)
        if s < S.aft_s(z) or s > S.stem_s(min(z, 3.3)) + 0.3:
            continue
        out.append((float(s), float(S.H(s, min(z, 4.6))[0])))
    return out


def deck_plan(K_, jez, nr, z_ilu):
    S = K_["S"]
    K = S.K
    a = Arkusz("deck-plan", jez, "A3", nr, z_ilu)
    sk = 80.0
    V = Widok(a, 26.0, 78.0, sk, u0=-15.4, v0=0.0)
    V.tytul_widoku((26, 20), "Deck plan: main deck and quarterdeck")
    P = S.plik("bryg_poklad.json")
    Kj = S.plik("kontrola.json") or {}
    # przejścia ≥ 0,8 m: siatka testu chodzenia (środek postaci r 0,3) zwężona o 0,1 i rozszerzona o 0,4
    for nm in ("glowny", "rufowy"):
        g = P["siatka_chodzenia"][nm]
        A = np.array([[c == "1" for c in row] for row in g["wiersze"]], bool)
        E = A.copy()
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                E &= np.roll(np.roll(A, di, 0), dj, 1)
        D = np.zeros_like(E)
        r = 4
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                if di * di + dj * dj <= r * r:
                    D |= np.roll(np.roll(E, di, 0), dj, 1)
        k = g["krok"]
        for i in range(D.shape[0]):
            j = 0
            while j < D.shape[1]:
                if D[i, j]:
                    j0 = j
                    while j < D.shape[1] and D[i, j]:
                        j += 1
                    s_ = g["z0"] + i * k
                    x0, x1 = g["x0"] + (j0 - 0.5) * k, g["x0"] + (j - 0.5) * k
                    V.wypelnij([(s_ - k / 2, x0), (s_ + k / 2, x0), (s_ + k / 2, x1), (s_ - k / 2, x1)], "#9fb7c9", 0.45)
                else:
                    j += 1
    # zarys burty (reling), wewnętrzna krawędź nadburcia = wielokąty pokładów
    zo = zarys_burty(S)
    V.linia(zo, "gruba")
    V.linia([(s, -x) for s, x in zo], "gruba")
    V.odcinek(zo[0], (zo[0][0], -zo[0][1]), "gruba")
    for p in P["powierzchnie"]:
        if p["nazwa"] in ("poklad_glowny", "poklad_rufowy"):
            V.linia([(q[1], q[0]) for q in p["wielokat"]], "srednia", zamknij=True)
    V.os((-15.2, 0), (14.8, 0))
    # przeszkody (wyposażenie) z deck layout
    odrzut = Kj.get("chodzenie", {}).get("odrzut_dzial_m", {})
    etyk = set()
    for o in P["przeszkody"]:
        (x, s) = o["srodek"]
        nm = o["nazwa"]
        if o["typ"] == "kolo":
            V.okrag((s, x), o["r"], "srednia")
        else:
            hl, hw = o["dl_z"] / 2, o["szer_x"] / 2
            rot = math.radians(o.get("obrot", 0.0) or 0.0)
            cs, sn = math.cos(rot), math.sin(rot)
            pts = [(s + dx * cs - dy * sn, x + dx * sn + dy * cs) for dx, dy in ((-hl, -hw), (hl, -hw), (hl, hw), (-hl, hw))]
            V.linia(pts, "ukryta" if o.get("chodzic") else "srednia", zamknij=True)
            if nm.startswith("dzialo_"):
                rec = odrzut.get(nm, 0.0)
                sg = 1 if x > 0 else -1
                xin = x - sg * hw
                V.linia([(s - hl, xin), (s + hl, xin), (s + hl, xin - sg * rec), (s - hl, xin - sg * rec)], "ukryta",
                        zamknij=True)
                V.wypelnij([(s - hl, xin), (s + hl, xin), (s + hl, xin - sg * rec), (s - hl, xin - sg * rec)], "#d9a066", 0.35)
                V.tekst((s, x), nm[-2:].replace("L", "P").replace("P", "S") if False else NP.STRONA[nm[7]][0].upper() + nm[8:],
                        1.8, dy=0.6)
        base = nm.rstrip("0123456789").rstrip("_")
        if base.startswith("dzialo"):
            base = "dzialo"
        if base not in etyk and not nm.startswith(("pompa_P", "maszt")):
            etyk.add(base)
            lab = {"dzialo": "Guns run out; orange: recoil zone", "kolkownica": "Pin rail",
                   "lina_kotwiczna": "Anchor cable (step over)"}.get(base) or _czytelna(nm).capitalize()
            V.etykieta((s, x), a.t(lab), (0.3, 1 if x >= 0 else -1), h=2.0, dmin=6)
    # maszty i koło drągów kabestanu
    for mk in ("fok", "grot"):
        o = S.M["maszty"][mk]["osie"]
        V.okrag((o["s_d"], 0), o["sr"] / 2, "gruba")
        V.etykieta((o["s_d"], 0), a.t("Fore mast" if mk == "fok" else "Main mast"), (0.3, 1), h=2.1)
    sn = S.M.get("snow")
    if sn:
        V.okrag((sn["s"], 0), sn["r"], "gruba")
        V.etykieta((sn["s"], 0), a.t("Snow mast"), (-0.3, -1), h=2.0)
    kk = S.M["inne"]["kabestan_kolo"]
    V.okrag((kk["s"], kk["x"]), kk["r"], "osiowa")
    V.wymiar_r((kk["s"], kk["x"]), kk["r"], 210, "R %s" % a.n(kk["r"]))
    V.etykieta((kk["s"] + kk["r"] * 0.7, kk["r"] * 0.7), a.t("Circle swept by the capstan bars"), (1, 1), h=2.0)
    # schody i próg pokładu rufowego
    sc = S.M["inne"]["schody"]
    V.linia([(sc["s_dol"], sc["x0"]), (sc["s_gora"], sc["x0"]), (sc["s_gora"], sc["x1"]), (sc["s_dol"], sc["x1"])],
            "srednia", zamknij=True)
    for k in range(1, sc["stopnie"]):
        sk_ = sc["s_dol"] + (sc["s_gora"] - sc["s_dol"]) * k / sc["stopnie"]
        V.odcinek((sk_, sc["x0"]), (sk_, sc["x1"]), "konstr")
    V.etykieta(((sc["s_dol"] + sc["s_gora"]) / 2, 0), a.t("Ladder to the quarterdeck"), (0.3, 1), h=2.0)
    V.odcinek((K["POLPOKLAD_S"], -3.5), (K["POLPOKLAD_S"], 3.5), "cienka")
    V.etykieta((K["POLPOKLAD_S"], -3.0), "%s s = %s" % (a.t("Quarterdeck break"), a.n(K["POLPOKLAD_S"])), (-0.2, -1), h=2.0)
    # stanowiska: numery
    act = {}
    for i, t in enumerate(P["stanowiska"]):
        x, z, s = t["stopy"]
        act.setdefault(t["czynnosc"], [])
        if t["poziom"] not in ("glowny", "rufowy") or abs(x) > 3.9:
            act[t["czynnosc"]].append(i + 1)
            continue
        V.okrag((s, x), 0.09, "bcienka", fill="#fff")
        X, Y = V.P(s, x)
        a.text((X, Y + 0.55), str(i + 1), 1.3, rejestr=False)
        act[t["czynnosc"]].append(i + 1)
    # linijka s pod rzutem
    y_r = -4.6
    V.odcinek((-15.0, y_r), (14.0, y_r), "cienka")
    for s in range(-15, 15):
        V.odcinek((s, y_r), (s, y_r + (0.25 if s % 5 else 0.45)), "cienka")
        if s % 5 == 0:
            V.tekst((s, y_r), "s = " + a.n(s, 0) if s == 0 else a.n(s, 0), 2.0, dy=3.4)
    V.wymiar((-14.0, -5.6), (14.0, -5.6), 0, kier="h", txt="%s 28.00" % a.t("deck length between rabbets")
             if jez == "en" else "%s 28,00" % a.t("deck length between rabbets"))
    lg = K["LUK_GLOWNY"] if "LUK_GLOWNY" in K else S.U["LUK_GLOWNY"]
    V.wymiar((lg["s0"], lg["pol_x"]), (lg["s1"], lg["pol_x"]), 4, kier="h")
    V.wymiar((lg["s1"], -lg["pol_x"]), (lg["s1"], lg["pol_x"]), 4, kier="v")
    yb = max(x for s, x in zo)
    V.wymiar((-8.0, -yb), (-8.0, yb), 0, kier="v", txt="%s %s" % (a.t("breadth at the rail"), a.n(2 * max(
        x for s, x in zo if abs(s + 8) < 0.2), 2)))
    # legenda stanowisk
    x0, y0 = 26.0, 160.0
    a.text((x0, y0 - 6), a.t("Work stations (numbers on the plan; data/stations.csv)"), 2.8, "start", bold=True)
    items = sorted(act.items(), key=lambda kv: kv[1][0])
    col_w = 66.0
    for i, (c, nums) in enumerate(items):
        cx, cy = x0 + (i // 10) * col_w, y0 + (i % 10) * 4.4
        rng = "%d–%d" % (nums[0], nums[-1]) if len(nums) > 1 and nums[-1] - nums[0] == len(nums) - 1 else \
            ", ".join(str(n) for n in nums[:6]) + ("…" if len(nums) > 6 else "")
        a.text((cx, cy), "%s: %s" % (a.t(_czytelna(c)), rng), 2.0, "start")
    a.fill([(x0, 214), (x0 + 6, 214), (x0 + 6, 217), (x0, 217)], "#9fb7c9", 0.45)
    a.text((x0 + 8, 216.8), a.t("walkways at least 0.8 m wide (from the walking test of the model)"), 2.1, "start")
    a.fill([(x0, 220), (x0 + 6, 220), (x0 + 6, 223), (x0, 223)], "#d9a066", 0.35)
    a.text((x0 + 8, 222.8), a.t("recoil zone of each gun (to the first obstacle)"), 2.1, "start")
    a.podzialka((26, 238), sk, 5)
    a.ramka("Deck plan", "1:80", "Main deck and quarterdeck with fittings, walkways, recoil zones and work stations",
            uwagi=("Stations aloft (tops, yardarms, shrouds, channels) are listed but not drawn.",
                   "Dashed outlines: obstacles one can step over (cable, thresholds).",
                   "Guns labelled P (port) / S (starboard) and number from forward."))
    return a


# ======================================================================== rufa i dziób
def stern_and_head(K_, jez, nr, z_ilu):
    S = K_["S"]
    K = S.K
    R = K_["rzuty"]
    a = Arkusz("stern-and-head", jez, "A3", nr, z_ilu)
    gal = S.M["stale"]["rufa_dziob"]["GALION"]
    # widok od rufy: u = −x (prawa burta w prawo), v = z
    sk = 50.0
    seg = R["rufa_widok"]["odcinki"]
    V = Widok(a, 110.0, 150.0, sk, u0=0.0, v0=0.0)
    V.obszar = (24, 26, 205, 248)
    V.tytul_widoku((26, 20), "Stern seen from aft")
    V.odcinki_siatki(seg, ukryte=False)
    V.os((0, -3.7), (0, 6.0))
    V.odcinek((-3.5, 0), (3.5, 0), "osiowa")
    V.tekst((3.55, 0), "DWL", 2.0, "start", dy=0.7)
    ob = S.ob

    def srodek(nm):
        o = ob.get(nm)
        return ((o["min"][0] + o["max"][0]) / 2, (o["min"][2] + o["max"][2]) / 2) if o else None
    hb = max(y for z, y in K["RUFA_SZER"])
    zhb = [z for z, y in K["RUFA_SZER"] if y == hb][0]
    V.wymiar((hb, zhb), (-hb, zhb), 68, kier="h", txt="%s %s" % (a.t("breadth of the stern"), a.n(2 * hb)))
    ox = gal["OKNA_X"]
    w_o, h_o = gal["OKNO"]
    zo_ = gal["OKNO_Z"]
    V.wymiar((ox[0] - w_o / 2, zo_ + h_o / 2), (ox[0] + w_o / 2, zo_ + h_o / 2), 6, kier="h")
    V.wymiar((ox[-1] + w_o / 2, zo_ - h_o / 2), (ox[-1] + w_o / 2, zo_ + h_o / 2), 5, kier="v")
    V.wymiar((ox[1], zo_ - h_o / 2 - 0.1), (ox[2], zo_ - h_o / 2 - 0.1), -4, kier="h")
    xr = -2.9
    for z0, z1 in ((0.0, K["Z_PAWEZ_DOLNA"]), (K["Z_PAWEZ_DOLNA"], K["Z_NAWIS"]), (K["Z_NAWIS"], K["RUFA"][-1][1])):
        V.wymiar((xr, z0), (xr, z1), -6, kier="v")
    for nm, txt, pref in (("latarnia_rufowa", "Stern lantern", (1, -0.5)), ("rufa_rzezby", "Carvings, pilasters, frieze", (1, -1)),
                          ("rufa_boki", "Quarter piece", (1, 0.2)), ("ster", "Rudder", (1, 0.6)),
                          ("rufa_pawez", "Upper transom", (-1, -1))):
        c = srodek(nm)
        if c:
            u = -c[0]
            if nm == "rufa_boki":
                u = -ob[nm]["min"][0] - 0.2
                c = (c[0], 2.0)
            if nm == "ster":
                c = (c[0], -1.5)
            if nm == "rufa_rzezby":
                c = (c[0], 3.9)
            if nm == "rufa_pawez":
                u, c = 1.6, (c[0], 3.3)
            V.etykieta((u, c[1]), a.t(txt), pref, h=2.1)
    V.etykieta((-ox[0], zo_), "%s %s × %s" % (a.t("Windows"), a.n(w_o), a.n(h_o)), (-1, -1), h=2.1)
    V.etykieta((0.5, (K["Z_PAWEZ_DOLNA"] + K["Z_NAWIS"]) / 2), a.t("Counter"), (1, 0.3), h=2.1)
    V.etykieta((1.0, 0.6), a.t("Lower (flat) transom"), (1, 0.5), h=2.1)
    V.etykieta((0.0, K["Z_PAWEZ_DOLNA"]), a.t("Wing transom"), (-1, 0.4), h=2.1)
    # dziób z boku: u = s, v = z
    seg = R["dziob_bok"]["odcinki"]
    D = Widok(a, 222.0, 150.0, sk, u0=9.6, v0=0.0)
    D.obszar = (212, 26, 408, 248)
    D.tytul_widoku((214, 20), "Head from starboard")
    D.odcinki_siatki(seg)
    D.odcinek((9.6, 0), (17.3, 0), "osiowa")
    st = K["DZIOB"]
    D.wymiar((st[-1][0], st[-1][1]), (st[-1][0], 0.0), -26, kier="v", txt="%s %s" % (a.t("stem head"), a.n(st[-1][1])))
    lz = np.array(S.profil()["lico"])
    kol = gal["KOLANO"]
    z_k = max(kol, key=lambda p: p[1])
    s_face = float(np.interp(z_k[0], lz[:, 1], lz[:, 0]))
    D.wymiar((s_face, z_k[0]), (s_face + z_k[1], z_k[0]), 18, kier="h", txt="%s %s" % (a.t("knee"), a.n(z_k[1])))
    D.etykieta((s_face + z_k[1] * 0.6, z_k[0] - 0.5), a.t("Knee of the head with scroll"), (1, 1), h=2.1)
    gf = S.M["inne"].get("galion_figura")
    if gf:
        D.etykieta((gf[0], gf[1]), a.t("Figure / scroll"), (1, -1), h=2.1)
    D.etykieta((14.6, 2.5), a.t("Cheeks and head rails"), (1, -1), h=2.1)
    D.etykieta((15.0, 3.2), a.t("Grating (head)"), (1, -1), h=2.1)
    ks, kz = gal["KLUZA_S"], gal["KLUZA_Z"]
    D.etykieta((ks, kz), "%s Ø %s" % (a.t("Hawse hole"), a.n(2 * gal["KLUZA_R"])), (-1, -1), h=2.1)
    cb = S.M["inne"]["kotbelki"][0][1]
    D.etykieta((cb[1], cb[2]), "%s s %s, %s %s" % (a.t("Cathead"), a.n(gal["KOTBELKA_S"]), a.t("projects"),
                                                  a.n(gal["KOTBELKA_WYST"])), (-1, -1), h=2.1)
    bs = S.M["bukszpryt"]
    D.wymiar_kat((bs["heel"][0] + 1.5, bs["heel"][1] + 1.5 * math.tan(math.radians(30)) + 0.0), 1.6, 0,
                 S.D["BUKSZPRYT_WZNIOS"], "%s %s°" % (a.t("steeve"), a.n(S.D["BUKSZPRYT_WZNIOS"], 0)))
    D.etykieta((14.3, 3.9), a.t("Bowsprit"), (1, -1), h=2.1)
    D.etykieta((st[3][0], st[3][1]), a.t("Stem"), (-1, 0.2), h=2.1)
    D.etykieta((13.0, -2.0), a.t("Gripe"), (-1, 1), h=2.1)
    a.podzialka((110, 262), sk, 5)
    a.ramka("Stern and head", "1:50", "Projected from the 3D model with hidden lines removed; dimensions from the "
                                       "parameters",
            uwagi=("Visible edges solid, hidden edges dashed (ray test against all meshes);",
                   "in the stern view hidden edges are left out for legibility."))
    return a
