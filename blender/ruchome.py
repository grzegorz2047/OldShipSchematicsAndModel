"""Olinowanie ruchome w rozsądnym wyborze (rozdział 07 przewodnika) przy żaglach zwiniętych (statek na kotwicy):
topenanty, brasy z wisiorami i blokami, gejtawy, szoty (luźne, ze zwisem), gordingi, fały marsli, gardafał
i pikfał gafla, gaje, dirki i szot bomu, fał kliwra, topenanty i brasy blindarei. Liny schodzą na kołki
nagielbanków i kołkownic albo na knagi pokładu rufowego; na zajętych kołkach wiszą buchty.

Uwaga: liny ruchome są statyczne (nie są dziećmi rej) – po zbrasowaniu rej w grze trzeba je przeliczyć albo
ukryć; tak samo w Blenderze.
"""
import math

import numpy as np
from mathutils import Vector

import narzedzia as N
from narzedzia import P
from olinowanie import lina
from wyposazenie import blok, buchta, stanowisko, deck, inner_x


class Kolki:
    def __init__(self, ctx):
        self.pools = {}
        for key, pins in ctx.get("kolki_nagielbankow", {}).items():
            self.pools["nagielbank_" + key] = [dict(p=p, used=None) for p in pins]
        rails = {}
        for p in ctx.get("kolki_kolkownic", []):
            x, s, z = p
            key = "kolkownica_%s_%s" % ("L" if x > 0 else "P", "fok" if s > 3 else "grot")
            rails.setdefault(key, []).append(dict(p=p, used=None))
        self.pools.update(rails)
        self.pools["knagi_rufowe"] = []
        self.log = []

    def add(self, pool, pts):
        self.pools.setdefault(pool, []).extend(dict(p=p, used=None) for p in pts)

    def take(self, pool, near, nazwa, grupa):
        lst = [k for k in self.pools.get(pool, []) if k["used"] is None]
        if not lst:
            lst = [k for k in self.pools.get(pool, [])]
        if not lst:
            return None
        # lustro: lina prawej burty (…_P) bierze kołek najbliższy odbiciu kołka swojej pary z lewej burty (…_L) –
        # inaczej kolejność przydziału dawała niesymetryczne kołki (topenanty foka: kontrola symetrii lin)
        if nazwa.endswith("_P"):
            para = [e for e in self.log if e["lina"] == nazwa[:-2] + "_L"]
            if para:
                near = (-para[-1]["p"][0], para[-1]["p"][1])
        k = min(lst, key=lambda k: (k["p"][0] - near[0]) ** 2 + (k["p"][1] - near[1]) ** 2)
        k["used"] = nazwa
        self.log.append(dict(pool=pool, p=k["p"], lina=nazwa, grupa=grupa))
        x, s, z = k["p"]
        return P(x, s, z + 0.1)


def zbuduj(ctx):
    rig = ctx["rig"]
    D = ctx["PR"].DRZEWCA
    K = ctx["K"]
    ps = ctx["poszycie"]
    kol = Kolki(ctx)
    # knagi (kevels) na nadburciu pokładu rufowego – na brasy grota, szoty, gaje
    sk = N.Siatka("knagi_rufowe")
    kn = []
    wr = sorted(ctx.get("wregi_nadburcia_s", []))
    cel = (-6.2, -7.6, -9.0, -10.4, -11.8, -13.0)
    srodki = [(a + b) / 2 for a, b in zip(wr[:-1], wr[1:]) if b - a > 0.45]
    for s in [min(srodki, key=lambda m: abs(m - c)) for c in cel] if srodki else cel:
        for side in (1, -1):
            from poklad import inner_at
            (xi, _, zi), _, _ = inner_at(ps, ps.r_qd, s)
            z = zi + 0.62
            xi = min(xi, ps.inner(s - 0.15, z + 0.08)[0], ps.inner(s + 0.15, z + 0.08)[0])   # zawalenie burt
            for ds in (-0.08, 0.08):
                N.box(sk, P(side * (xi - 0.045), s + ds, z), (0.09, 0.06, 0.06), "drewno_ciemne")
            N.box(sk, P(side * (xi - 0.06), s, z + 0.055), (0.06, 0.28, 0.05), "drewno_ciemne")
            kn.append((side * (xi - 0.09), s, z - 0.05))
    N.to_object(sk, ctx["kol"]["wyposazenie"], recalc=True)
    kol.add("knagi_rufowe", kn)
    lin = []      # (nazwa, grupa, maszt) do stanowisk

    from poklad import inner_at as _inner_at

    def nad_relingiem(x_side, s):
        """Punkt tuż nad wewnętrzną krawędzią pokrywy relingu: lina schodząca z zewnątrz przechodzi nad pokrywą
        i dopiero od środka schodzi na kołek (bez przechodzenia przez pokrywę i wierzchołki wręgów)."""
        (xi, _, zi), _, _ = _inner_at(ps, ps.r_top, s)
        return P(x_side * (xi - K["RELING_SZER"] + K["NADBURCIE_GR"] - 0.08), s, ps.rail_top(s) + K["RELING_GR"] + 0.04)

    def na_relingu(x_side, s, L=0.12):
        """Blok na śrubie oczkowej w pokrywie relingu: zwraca środek bloku (strop do ucha, bez wiszenia w powietrzu)."""
        xo, _ = ps.outer(s, ps.rail_top(s))
        xr = xo - K["NADBURCIE_GR"] / 2
        zt = ps.rail_top(s) + K["RELING_GR"] - 0.005
        skr = ctx.setdefault("_sk_drobne", N.Siatka("okucia_pokladu"))
        N.cylinder(skr, P(x_side * xr, s, zt - 0.05), P(x_side * xr, s, zt + 0.02), 0.012, 0.012, "zelazo", sides=8)
        c_r = P(x_side * xr, s, zt + 0.055)
        N.lathe(skr, [(0.027, -0.009), (0.036, 0.0), (0.027, 0.009), (0.018, 0.0)], "zelazo", c_r,
                axis=Vector((0, 1, 0)), sides=8, close_ends=False)
        cb = c_r + Vector((0, 0, 0.036 + L * 0.5))
        blok(ctx, cb, Vector((0, 0, 1)), L)
        return cb

    def belay(pool, near, nazwa, grupa, start, via=None, d=0.018, sag=0.0, jednostronna=False):
        pin = kol.take(pool, near, nazwa, grupa)
        n0 = len(ctx.get("liny", []))
        if pin is None:
            return
        via = list(via or [])
        if pool.startswith(("kolkownica", "knagi")):
            prev = via[-1] if via else start
            s_p = -pin.y
            v = nad_relingiem(1 if pin.x > 0 else -1, s_p)
            if abs(prev.x) > abs(v.x) - 0.02 and prev.z > v.z:
                via.append(v)
        pts = [start] + via + [pin]
        if sag > 0 and len(pts) == 2:
            lina(ctx, "ruchome", pts, d, "lina_jasna", sag=sag)
        else:
            for a, b in zip(pts[:-1], pts[1:]):
                lina(ctx, "ruchome", [a, b], d, "lina_jasna")
        if jednostronna:                    # pojedyncza lina bez pary na drugiej burcie (wyjątek testu symetrii)
            for L_ in ctx["liny"][n0:]:
                L_["jednostronna"] = True
        buchta(ctx, pin + Vector((0, 0, -0.02)), 0.45, d=min(d, 0.02))
        lin.append((nazwa, grupa, pool))

    for key in ("fok", "grot"):
        R_ = rig["maszty"][key]
        m, st, br = R_["m"], R_["st"], R_["br"]
        fife = "nagielbank_" + key
        rail = "kolkownica_%s_" + key
        for nm, lev in ((key, 0), (key + "mars", 1), (key + "bram", 2)):
            Y = rig["reje"][nm]
            c = Vector(Y["c"])
            h = Y["L"] / 2
            d_l = (0.020, 0.016, 0.010)[lev]
            for side, tg in ((1, "L"), (-1, "P")):
                # nok: punkt w bryle rei (na obu burtach tak samo rozpoznawany jako koniec na rei)
                arm = c + Vector((side * h * 0.96, 0, Y["sr"] * 0.12))
                # topenanta
                if lev == 0:
                    bl = P(side * 0.42, m.s(m.z_cap) + 0.05, m.z_cap - 0.05)
                elif lev == 1:
                    bl = P(side * 0.32, st.s(st.z_head) + 0.05, st.z_head - 0.05)
                else:
                    bl = P(side * 0.15, br.s(br.z_top - 1.0), br.z_top - 1.0)
                lina(ctx, "ruchome", [arm, bl], d_l, "lina_jasna")
                blok(ctx, bl, (arm - bl).normalized(), 0.14 if lev < 2 else 0.1)
                down = P(side * 0.3, m.s(m.z_top - 0.6) - 0.3, m.z_top - 0.6)
                belay(fife, (side * 0.7, m.s_d), "topenanta_%s_%s" % (nm, tg), "topenanty", bl, [down], d=d_l)
                # bras: wisior z blokiem, dalej ku rufie
                pend = arm + Vector((0, 0.85, -0.25))
                lina(ctx, "ruchome", [arm, pend], 0.024 if lev < 2 else 0.016, "lina_smolowana")
                blok(ctx, pend, Vector((0, 1, 0)), 0.16 if lev < 2 else 0.1)
                if key == "fok":
                    # przez blok na sztagu grota (dolny) / sztagu stengowym, potem do kołkownicy przy grocie
                    G = rig["maszty"]["grot"]
                    gm, gst = G["m"], G["st"]
                    if lev == 0:
                        a, b = gm.p(gm.z_top + 0.25), m.p(m.z_d + 0.55, ds=-(m.r(m.z_d) + 0.25))
                        f = 0.45
                    elif lev == 1:
                        a, b = gst.p(gst.z_head + 0.1, ds=0.1), m.p(m.z_top + 0.45, ds=m.sr * 0.4)
                        f = 0.5
                    else:
                        a, b = G["br"].p(G["br"].z_top - 0.9, ds=0.06), st.p(st.z_head + 0.2, ds=0.3)
                        f = 0.5
                    via = a.lerp(b, f) + Vector((side * 0.25, 0, 0))
                    blok(ctx, via, (b - a).normalized(), 0.12)
                    lina(ctx, "ruchome", [pend, via], 0.018 if lev < 2 else 0.012, "lina_jasna", sag=0.012)
                    # rozdział 07: brasy foka schodzą przy grotmaszcie – kołkownica grota (nie foka) obok ławy grota
                    belay("kolkownica_%s_grot" % tg, (side * 3.0, gm.s_d + 0.6), "bras_%s_%s" % (nm, tg), "brasy",
                          via, d=0.018 if lev < 2 else 0.012)
                else:
                    sb = (-12.95, -11.55, -13.4)[lev]        # poza zasięgiem obrotu działka relingowego (s −12,2)
                    from poklad import inner_at
                    rb = na_relingu(side, sb)
                    lina(ctx, "ruchome", [pend, rb], 0.018 if lev < 2 else 0.012, "lina_jasna", sag=0.012)
                    belay("knagi_rufowe", (side * 2.5, sb + 0.8), "bras_%s_%s" % (nm, tg), "brasy", rb,
                          d=0.018 if lev < 2 else 0.012)
                # gejtawy (żagiel zwinięty: róg podciągnięty pod reję) i szoty
                if lev < 2:
                    gx = side * (1.25 if lev == 0 else 0.9)
                    g0 = c + Vector((gx, 0.05, -Y["sr"] * 0.6))
                    blok(ctx, g0, Vector((0, 0, 1)), 0.12)
                    if lev == 0:
                        belay(rail % tg, (side * 3.0, m.s_d - 1.0), "gejtawa_%s_%s" % (nm, tg), "gejtawy", g0,
                              d=0.016)
                        # szot: róg szotowy podciągnięty gejtawą pod jej blok (żagiel zwinięty), lina luźno ku rufie
                        # do bloku na relingu za ławą wantową (wcześniej 3,6 m za masztem: w ławie, przez talrepy;
                        # foka 1,2 m za ławą – za pokrywą furty 6,01, grota 2,6 m – poza zasięgiem obrotu działek
                        # relingowych −6,6 i −9,4) i na kołek kołkownicy foka / knagę pokładu rufowego od środka
                        from olinowanie import pozycje_jufersow
                        _, s0_l, _ = pozycje_jufersow(K, ctx["PR"].OLINOWANIE, m.s_d, key)
                        s_sh = s0_l - (1.2 if key == "fok" else 2.6)
                        rs_ = na_relingu(side, s_sh)
                        rog_szot = g0 + Vector((0, 0, -0.07))
                        lina(ctx, "ruchome", [rog_szot, rs_], 0.028, "lina_jasna", sag=0.07)
                        belay(("kolkownica_%s_fok" % tg) if key == "fok" else "knagi_rufowe", (side * 2.8, s_sh + 0.3),
                              "szot_%s_%s" % (nm, tg), "szoty", rs_, d=0.028)
                    else:
                        hole = P(side * 0.35, m.s(m.z_top) - 0.15, m.z_top + 0.25)
                        belay(fife, (side * 0.7, m.s_d + 0.7), "gejtawa_%s_%s" % (nm, tg), "gejtawy", g0, [hole],
                              d=0.014)
                        # szot marsla: z rogu przez nok dolnej rei, wzdłuż rei do środka, w dół do nagielbanku
                        Yl = rig["reje"][key]
                        cl = Vector(Yl["c"])
                        p1 = cl + Vector((side * Yl["L"] / 2 * 0.93, 0.0, -Yl["sr"] * 0.62))
                        p2 = cl + Vector((side * 0.45, 0.0, -Yl["sr"] * 0.62))
                        lina(ctx, "ruchome", [c + Vector((side * h * 0.88, 0.0, -Y["sr"] * 0.55)), p1], 0.028, "lina_jasna")
                        lina(ctx, "ruchome", [p1, p2], 0.028, "lina_jasna")
                        blok(ctx, p2, Vector((1, 0, 0)), 0.16)
                        belay(fife, (side * 0.7, m.s_d - 0.7), "szot_%s_%s" % (nm, tg), "szoty", p2, d=0.028)
            # gordingi: 2 na żagiel, z bloków pod marsem / salingiem przed żaglem do rei
            if lev < 2:
                zb = (m.z_top - 0.05) if lev == 0 else (st.z_head - 0.05)
                sb = (m.s(zb) + 0.6) if lev == 0 else (st.s(zb) + 0.45)
                for gx in (-1.0, 1.0):
                    b0 = P(gx * 0.55, sb, zb)
                    blok(ctx, b0, Vector((0, 0, 1)), 0.1)
                    lina(ctx, "ruchome", [b0, c + Vector((gx * 1.0, -0.62, 0.05))], 0.012, "lina_jasna")
                    ctx["liny"][-1]["do_zagla"] = "zagiel_" + nm      # gording kończy się na wałku płótna (lik dolny)
            # fał marsrei: od topu stengi (tie) w dół do ławy wantowej (po przeciwnych burtach foka i grota)
            if lev == 1:
                side = -1 if key == "fok" else 1
                lw = rig["lawy"][key]["dead"]
                de = lw[min(len(lw) - 1, rig["lawy"][key]["n_sh"])]
                a = st.p(st.z_head - 0.35, ds=-st.sr / 2 - 0.05)
                b = P(side * (de["x"] - 0.25), de["s"] + 0.3, de["z"] + 0.15)
                blok(ctx, a, (b - a).normalized(), 0.2)
                # dolny blok talii fału: strop w dół, wzdłuż talii, do ucha przy ławie wantowej (punkt b)
                blok(ctx, b + (a - b).normalized() * 0.6, (b - a).normalized(), 0.2, strop=b,
                     strop_do=("lawy_wantowe",))
                for off in (-0.03, 0.0, 0.03):
                    lina(ctx, "ruchome", [a + Vector((off, 0, 0)), b + (a - b).normalized() * 0.6 + Vector((off, 0, 0))],
                         0.02, "lina_jasna")
                    ctx["liny"][-1]["jednostronna"] = True      # fał marsrei: jedna talia, burta z rozdziału 07
                lin.append(("fal_%s" % nm, "faly", "lawa_" + key))
    # gafel i bom
    G = rig["maszty"]["grot"]
    gm, gst = G["m"], G["st"]
    if "gafel" in rig["reje"]:
        gf = rig["reje"]["gafel"]
        # liny z końcem na bloku przy gaflu (gejtawy, gardafał, pikfał) są linami dynamicznymi gafla: blok wisi kilka
        # centymetrów od drzewca, więc rozpoznanie po odległości końca od powierzchni (oznacz_dynamiczne) łapało
        # tylko część z nich
        gf_nm = gf["obj"].name if gf.get("obj") is not None else "gafel"
        jaw, peak = Vector(gf["c"]), Vector(gf["end"])
        r_g = gf["sr"] / 2
        g_dir = (peak - jaw).normalized()

        def nad_gaflem(q, ku, L):
            """Środek bloku na stropie nad gaflem w punkcie q (oś gafla), odsunięty prostopadle do gafla w stronę
            punktu 'ku' o promień drzewca + pół bloku: lina kończy się na bloku, nie w drzewcu."""
            n = (ku - q) - g_dir * (ku - q).dot(g_dir)
            n.normalize()
            return q + n * (r_g + L * 0.5 + 0.01), n
        # gejtawy żagla gaflowego (rozdział 07: brails, 12 mm, 3–4 na żagiel, tylko bez bomu; żagiel
        # zrzucony do masztu) – przed gardafałem i pikfałem, póki kołki lustrzane na obu burtach są wolne (para
        # kołków symetryczna; pikfał zajmował kołek będący odbiciem kołka gejtawy): na każdej burcie 3 gejtawy – blok z boku gafla, odnoga obejmuje wałek płótna pod gaflem
        # (od boku do spodu, obie burty spotykają się pod wałkiem), część robocza wzdłuż gafla do bloku z przodu
        # masztu snow pod szczękami i w dół na kołek nagielbanku grota
        if "bom" not in rig["reje"] and ctx["snow"]:
            sn = rig["snow"]
            s_sn = lambda z: sn["s"] - (z - sn["z0"]) * sn["t"]
            for i, f in enumerate((0.3, 0.55, 0.8)):
                q = jaw.lerp(peak, f)
                r_w = 0.2 * (1 - 0.55 * f)                   # promień wałka płótna (zagle.py: żagiel gaflowy)
                C = q + Vector((0, 0, -0.08 - r_w))
                R = 1.25 * r_w + 0.03                        # poza wałkiem (profil +8 %, skręt, losowe r) z zapasem
                r_gf = r_g * (1.0 - 0.35 * f ** 1.5)
                zk = jaw.z - 0.32 - 0.2 * i
                for side, tg in ((1, "L"), (-1, "P")):
                    b = q + Vector((side * (r_gf + 0.05), 0, 0))
                    blok(ctx, b, Vector((0, 0, 1)), 0.1)
                    odnoga = [b + Vector((0, 0, -0.05))] + [C + Vector((side * R * math.cos(a), 0, R * math.sin(a)))
                                                             for a in (math.radians(v) for v in (35, 15, -5, -25, -45, -68))] + \
                        [C + Vector((0, 0, -R))]
                    # (nazwy zmiennych w wywołaniach lina() – dane_publiczne.nazwy_lin rozpoznaje po nich gejtawy)
                    gejtawa_gafla_odnoga = odnoga
                    lina(ctx, "ruchome", gejtawa_gafla_odnoga, 0.012, "lina_jasna", od=gf_nm)
                    ctx["liny"][-1]["owin"] = "zagiel_gaflowy"          # odnoga przyłożona do wałka (zamocuj_konce)
                    mb = P(side * (sn["r"] * 0.7 + 0.06), s_sn(zk) + sn["r"] * 0.7 + 0.05, zk)
                    blok(ctx, mb, (b - mb).normalized(), 0.1)
                    gejtawa_gafla_robocza = [b + Vector((0, 0, 0.05)), mb]
                    lina(ctx, "ruchome", gejtawa_gafla_robocza, 0.012, "lina_jasna", od=gf_nm)
                    belay("nagielbank_grot", (side * 0.6, gm.s_d - 0.9), "gejtawa_gafla_%d_%s" % (i + 1, tg),
                          "gejtawy", mb + Vector((0, 0, -0.06)), d=0.012)
        thr = gm.p(gm.z_top + 0.15, ds=-gm.sr * 0.6)
        cb, n_ = nad_gaflem(jaw.lerp(peak, 0.06), thr, 0.16)
        blok(ctx, cb, n_, 0.16)
        lina(ctx, "ruchome", [thr, cb + n_ * 0.08], 0.02, "lina_jasna", do=gf_nm)
        # część robocza gardafału: od bloku przy topie z boku szczęk gafla do nagielbanku (nie przez szczęki)
        belay("nagielbank_grot", (0.0, gm.s_d - 0.7), "gardafal", "faly", thr,
              [jaw + Vector((0.32, 0, 0.30))], d=0.02, jednostronna=True)
        pk = gst.p(gst.z_head - 0.1, ds=-gst.sr * 0.6)
        for f in (0.55, 0.92):
            cb, n_ = nad_gaflem(jaw.lerp(peak, f), pk, 0.14)
            lina(ctx, "ruchome", [pk, cb + n_ * 0.07], 0.02, "lina_jasna", do=gf_nm)
            blok(ctx, cb, n_, 0.14)
        belay("nagielbank_grot", (-0.6, gm.s_d - 0.7), "pikfal", "faly", pk, [gm.p(gm.z_top - 0.5, dx=-0.3, ds=-0.3)],
              d=0.02, jednostronna=True)
        for side, tg in ((1, "L"), (-1, "P")):
            from poklad import inner_at
            corner = na_relingu(side, -13.6, 0.10)
            lina(ctx, "ruchome", [peak, corner], 0.016, "lina_jasna", sag=0.02)
            belay("knagi_rufowe", (side * 2.4, -13.0), "gaj_%s" % tg, "gaje", corner, d=0.016)
    if "bom" in rig["reje"]:
        bm = rig["reje"]["bom"]
        bend = Vector(bm["end"])
        for side in (1, -1):
            lina(ctx, "ruchome", [gm.p(gm.z_top + 0.1, dx=side * 0.3, ds=-0.3), bend + Vector((side * 0.06, 0, 0.05))],
                 0.020, "lina_jasna", sag=0.004)
        # szot bomu: talia z noku bomu do pawęży
        from rufa_dziob import Rufa
        tr = Vector(P(0, -14.95, float(ctx["kd"].deck_c(-14.0)) + ctx["K"]["POLPOKLAD_H"] + 0.95))
        b1 = bend + Vector((0, -0.5, -0.12))
        blok(ctx, b1, (tr - b1).normalized(), 0.22)
        blok(ctx, tr + Vector((0, 0, 0.12)), (b1 - tr).normalized(), 0.22)
        for off in (-0.04, 0.0, 0.04):
            lina(ctx, "ruchome", [b1 + Vector((off, 0, 0)), tr + Vector((off, 0, 0.12))], 0.024, "lina_jasna")
        lin.append(("szot_bomu", "szoty", "pawez"))
    # blindareja: topenanty do ezelhoftu bukszprytu, brasy do relingu dziobu
    if "blinda" in rig["reje"]:
        Y = rig["reje"]["blinda"]
        c = Vector(Y["c"])
        h = Y["L"] / 2
        bs = rig["bukszpryt"]
        capp = bs["path"][-1]
        for side, tg in ((1, "L"), (-1, "P")):
            arm = c + Vector((side * h * 0.95, 0, 0.05))
            lina(ctx, "ruchome", [arm, capp + Vector((side * 0.15, 0, 0.05))], 0.016, "lina_jasna")
            rb = na_relingu(side, 11.9, 0.10)        # blok na śrubie oczkowej w pokrywie relingu dziobu
            lina(ctx, "ruchome", [arm, rb + Vector((0, 0, 0.05))], 0.016, "lina_jasna", sag=0.015)
            lin.append(("bras_blinda_%s" % tg, "brasy", "reling_dziobu"))
    ctx["belay"] = kol.log
    ctx["liny_stanowisk"] = lin
    # bloki i śruby oczkowe olinowania ruchomego dopisane do wspólnych siatek 'bloki' i 'okucia_pokladu' – te
    # obiekty powstały już w etapie wyposażenia (wcześniej wszystko, co dodał ten etap, nie trafiało do modelu:
    # liny kończyły się w powietrzu przy brakujących blokach); obiekty odtworzone z pełnych siatek
    import bpy
    for key in ("_sk_drobne", "_sk_bloki"):
        sk_ = ctx.get(key)
        if sk_ is None or not sk_.f:
            continue
        if key == "_sk_bloki":
            # bloki dodane w tym etapie, które niczego nie dotykają (przy ezelhofcie, pod marsem, obok sztagu),
            # dostają strop do najbliższej części konstrukcji albo liny stałej – blok nie wisi w powietrzu
            from wyposazenie import stropy_blokow
            stropy_blokow(ctx, sk_)
        stary = bpy.data.objects.get(sk_.nazwa)
        if stary is not None:
            me_ = stary.data
            bpy.data.objects.remove(stary, do_unlink=True)
            if me_.users == 0:
                bpy.data.meshes.remove(me_)
        N.to_object(sk_, ctx["kol"]["wyposazenie"], recalc=False)
