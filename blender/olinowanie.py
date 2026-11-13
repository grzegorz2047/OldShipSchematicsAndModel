"""Olinowanie stałe (rozdział 06 przewodnika): ławy wantowe z jufersami i puttingami, wanty z jufersami i talrepami, wyblinki,
drążki i podwantki, ściągacze, wanty stengowe (jufersy na marsie) i bramstengowe, paduny, sztagi z myszami,
watersztagi, wanty i wiązanie bukszprytu; perty ze strzemionami, stropy i tie na rejach.

Liny zbierane są w rejestrze (ctx['liny']: grupa, łamana, średnica, materiał, rodzic, skręt) i zamieniane na rurki
w realizuj(ctx, d_min): do .blend z prawdziwymi średnicami, do GLB z dolną granicą D_MIN_GLB (eksport.py).
Rurki: liczba boków zależna od średnicy (rozdział 08), UV: v – obwód, u – długość / (2 skoki splotu, skok 3,3 d).
"""
import math

import bpy

import numpy as np
from mathutils import Matrix, Vector

import narzedzia as N
from narzedzia import P


# ---------------------------------------------------------------- rejestr lin
def lina(ctx, grupa, pts, d, mat="lina_smolowana", parent=None, sag=0.0, n=None, lewy=None, od=None, do=None, wariant=None):
    """Lina w rejestrze. od / do – nazwy obiektów ruchomych, na których leży początek / koniec (lina dynamiczna:
    osobny węzeł lina_dyn_*, końce zapisane w liny.json także w układzie lokalnym tych obiektów)."""
    pts = [Vector(p) for p in pts]
    if sag > 0 and len(pts) == 2:
        L = (pts[1] - pts[0]).length
        nn = n or max(6, min(24, int(L / 0.35) + 2))
        pts = N.catenary(pts[0], pts[1], sag * L if sag < 1 else sag, nn)
    if lewy is None:
        lewy = mat == "lina_smolowana"
    ctx.setdefault("liny", []).append(dict(g=grupa, p=pts, d=d, m=mat, parent=parent, lewy=lewy, od=od, do=do, wariant=wariant))


def _sides(d):
    return 8 if d >= 0.06 else 6 if d >= 0.035 else 5 if d >= 0.02 else 4      # cienkie linki 4 boki


RUCHOME_KONCE = ("reja_", "gafel", "bom", "dzialo_", "furta_pokrywa_", "kolo_sterowe", "rumpel", "ster",
                 "kabestan_beben", "pompa_L_dzwignia", "pompa_P_dzwignia", "dzwon")


def oznacz_dynamiczne(ctx, tol=0.035):
    """Liny bez rodzica, których koniec leży na części ruchomej (reja, gafel, laweta, pokrywa, rumpel, koło…):
    od / do = nazwa tej części (najbliższa powierzchnia w odległości ≤ promień + tol)."""
    from mathutils.bvhtree import BVHTree
    trees = []
    for ob in bpy.data.objects:
        if ob.type != "MESH" or not ob.name.startswith(RUCHOME_KONCE) or ob.name.startswith(("lina_", "dzialo_lufa",
                                                                                              "dzialo_laweta")):
            continue
        if ob.name.endswith("_lufa"):
            continue
        dg = bpy.context.evaluated_depsgraph_get()
        trees.append((ob.name, BVHTree.FromObject(ob, dg, deform=False), ob.matrix_world.inverted()))
    def wewnatrz(tr, q):
        """Punkt q (lokalnie) wewnątrz bryły: nieparzysta liczba przecięć półprostej (dwa kierunki zgodne)."""
        wyn = []
        for dv in (Vector((0.013, 0.007, 1.0)).normalized(), Vector((0.011, 1.0, 0.017)).normalized()):
            k, o_ = 0, Vector(q)
            for _ in range(32):
                hit = tr.ray_cast(o_, dv)
                if hit[0] is None:
                    break
                k += 1
                o_ = hit[0] + dv * 1e-5
            wyn.append(k % 2 == 1)
        return all(wyn)
    # drzewca ruchome (reje, gafel, bom) analitycznie: odcinek osi i promień – rozstrzyga tak samo po obu burtach
    # (odległość do siatki walca zależy od podziału ścian)
    osie = []
    for nm_r, Y in ctx.get("rig", {}).get("reje", {}).items():
        o_ = Y.get("obj")
        if o_ is None:
            continue
        c_ = Vector(Y["c"])
        if "end" in Y:
            a_, b_ = c_, Vector(Y["end"])
        else:
            a_, b_ = c_ - Vector((Y["L"] / 2, 0, 0)), c_ + Vector((Y["L"] / 2, 0, 0))
        osie.append((o_.name, a_, b_, Y["sr"] / 2))

    def na_drzewcu(p, r_l):
        for (nm_r, a_, b_, r_) in osie:
            ab = b_ - a_
            t_ = max(0.0, min(1.0, (Vector(p) - a_).dot(ab) / ab.length_squared))
            if (Vector(p) - (a_ + ab * t_)).length <= r_ + r_l + tol:
                return nm_r
        return None
    n = 0
    for L in ctx.get("liny", []):
        if L["parent"] is not None:
            continue
        for key, p in (("od", L["p"][0]), ("do", L["p"][-1])):
            if L.get(key):
                continue
            nm_r = na_drzewcu(p, L["d"] / 2)
            if nm_r:
                L[key] = nm_r
                n += 1
                continue
            for (nm, tr, Minv) in trees:
                q = Minv @ Vector(p)
                loc, nrm, idx, d = tr.find_nearest(q, L["d"] / 2 + tol)
                # koniec liny przy powierzchni albo w bryle części ruchomej (np. nok rei, gdzie odległość do
                # najbliższej ściany zależy od podziału walca) – rozstrzyga to samo po obu burtach
                if loc is not None or wewnatrz(tr, q):
                    L[key] = nm
                    n += 1
                    break
    ctx["_dyn_oznaczone"] = True
    return n


# zamocowanie końców lin (przed realizuj): grupa liny → części, na których jej koniec może leżeć (prefiksy nazw)
KONCE_NA = {
    "perty": ("reja_",), "strzemiona": ("reja_",), "stropy": ("drzewca", "reja_", "bukszpryt"),
    "paduny": ("drzewca",), "wanty": ("drzewca", "jufersy"), "sztagi": ("drzewca", "bukszpryt", "sztagi_okucia", "galion"),
    "dziala": ("dzialo_", "okucia_pokladu", "bloki"), "talie_rumpla": ("bloki", "rumpel", "okucia_pokladu"),
    "sterlina": ("bloki", "kolo_sterowe", "rumpel", "okucia_pokladu"),
    "kotwice": ("nagielbank", "kotbelki", "kotwica_", "kadlub"),
    "ruchome": ("reja_", "gafel", "bom", "bloki", "drzewca", "bukszpryt", "okucia_pokladu", "nagielbank", "kolkownice",
                "knagi", "kadlub_reling", "rufa_pawez"),
    "lodz": ("lodz", "okucia_pokladu"),
}
KONCE_MAKS = 0.07       # m: najdalej tyle koniec może być od zamierzonej części (niedokładność przyłożenia)


def zamocuj_konce(ctx, tol=0.008):
    """Końce lin leżące 1–7 cm od części, na której z założenia się kończą (KONCE_NA: reja dla pert, top masztu dla
    padunów, lufa dla lin dział…), przedłużone o krótki odcinek do jej powierzchni (3 mm w głąb) – lina się nie
    skraca i nie zmienia przebiegu. Liny z 'do_zagla' (gordingi przy zwiniętym żaglu) kończą się na wałku płótna
    tego żagla (najbliższy punkt powierzchni, do 0,6 m). Zwraca listę przedłużeń (do kontroli)."""
    from mathutils.bvhtree import BVHTree
    cache = {}

    def drzewo(ob):
        if ob.name not in cache:
            me = ob.data
            cache[ob.name] = (BVHTree.FromPolygons([v.co for v in me.vertices], [p.vertices for p in me.polygons]),
                              ob.matrix_world.copy(), ob.matrix_world.inverted())
        return cache[ob.name]
    kier = [Vector((1, 0.013, 0.007)).normalized(), Vector((0.011, 1, 0.017)).normalized()]

    def wewnatrz(tr, q):
        g = 0
        for dv in kier:
            n_, o_ = 0, Vector(q)
            for _ in range(48):
                hit = tr.ray_cast(o_, dv)
                if hit[0] is None:
                    break
                n_ += 1
                o_ = hit[0] + dv * 1e-5
            g += n_ & 1
        return g == len(kier)
    obs = [o for o in bpy.data.objects if o.type == "MESH" and not o.name.startswith(("lina_", "##")) and
           len(o.data.polygons) and o.users_collection and o.users_collection[0].name != "_eksport"]
    zm = []
    for L in ctx.get("liny", []):
        # lina opasująca wałek żagla ('owin': nazwa żagla) – punkty po pierwszym przyłożone do powierzchni płótna
        # (promień liny + 3 mm), zamiast łuku z zapasem odstającego od nieregularnego wałka
        ow = bpy.data.objects.get(L["owin"]) if L.get("owin") else None
        if ow is not None:
            tr, M, Mi = drzewo(ow)
            nowe = [L["p"][0]]
            for p in L["p"][1:]:
                loc, nrm, idx, d = tr.find_nearest(Mi @ p, 1.0)
                if loc is None:
                    nowe.append(p)
                    continue
                q = M @ loc
                kr_ = (p - q).normalized() if (p - q).length > 1e-6 else (M.to_3x3() @ nrm).normalized()
                nowe.append(q + kr_ * (L["d"] / 2 + 0.003))
            L["p"] = nowe
        pts = L["p"]
        if len(pts) < 2 or (len(pts) > 2 and (pts[0] - pts[-1]).length < 1e-3):
            continue
        r = L["d"] / 2
        cele = None
        for g, pref in KONCE_NA.items():
            if L["g"].startswith(g):
                cele = pref
        for k in (0, 1):
            e = Vector(pts[0] if k == 0 else pts[-1])
            if k == 1 and L.get("do_zagla"):
                kand, maks = [o for o in obs if o.name == L["do_zagla"]], 0.6
            elif cele:
                kand, maks = [o for o in obs if o.name.startswith(cele)], KONCE_MAKS
            else:
                continue
            best = None
            for o in kand:
                if L.get("wariant") and o.get("wariant") and o.get("wariant") != L.get("wariant"):
                    continue
                tr, M, Mi = drzewo(o)
                loc, nrm, idx, d = tr.find_nearest(Mi @ e, maks + r)
                if loc is None:
                    continue
                q = M @ loc
                d = (q - e).length
                if best is None or d < best[0]:
                    best = (d, q, (M.to_3x3() @ nrm).normalized(), o.name)
            if best is None or best[0] - r <= tol:
                continue
            d, q, n, nm = best
            # wewnątrz części (parzystość przecięć dwóch półprostych) – już zamocowany; normalna ku końcowi liny
            tr, M, Mi = drzewo(bpy.data.objects[nm])
            if wewnatrz(tr, Mi @ e):
                continue
            if (e - q).dot(n) < 0:
                n = -n
            nowy = q - n * 0.003
            if k == 0:
                L["p"] = [nowy] + list(pts)
            else:
                L["p"] = list(pts) + [nowy]
            pts = L["p"]
            L["przedluzona"] = True
            zm.append(dict(grupa=L["g"], koniec=k, do=nm, odleglosc_m=round(d - r, 3)))
    ctx["zamocowane_konce"] = zm
    return zm


def realizuj(ctx, d_min=0.0, kol=None, sufiks=""):
    """Rurki z rejestru: jeden obiekt na (grupę, rodzica), liny dynamiczne (koniec na części ruchomej) – każda
    osobno jako lina_dyn_<grupa>_<nr>. Zwraca listę obiektów."""
    kol = kol or ctx["kol"]["olinowanie"]
    if not ctx.get("_dyn_oznaczone"):
        oznacz_dynamiczne(ctx)
    groups = {}
    for k, L in enumerate(ctx.get("liny", [])):
        if L.get("od") or L.get("do"):
            key = ("dyn_%s_%d" % (L["g"], k), "")              # lina dynamiczna: własny węzeł lina_dyn_*
        else:
            key = (L["g"], L["parent"].name if L["parent"] is not None else "")
        groups.setdefault(key, []).append(L)
    out = []
    for (g, pn), lst in groups.items():
        sk = N.Siatka(("lina_%s_%s" % (g, pn) if pn else "lina_%s" % g) + sufiks)
        for L in lst:
            d = max(L["d"], d_min)
            r = d / 2
            lay = 3.3 * d
            pts = L["p"]
            if len(pts) < 2 or (pts[-1] - pts[0]).length < 1e-4:
                continue
            # skręt lewy (lina kablowa: wanty, sztagi) – odbicie u; prawy (liny ruchome) bez zmian
            N.sweep(sk, pts, N.circle_prof(r, _sides(L["d"])), L["m"], cap0=False, cap1=False, rope=True,
                    uv_u_scale=(-2 if L["lewy"] else 2) * lay)
        if not sk.f:
            continue
        ob = N.to_object(sk, kol)
        L0 = lst[0]
        if L0.get("od") or L0.get("do"):
            ob["od_obiekt"] = L0.get("od") or ""
            ob["do_obiekt"] = L0.get("do") or ""
            ob["lina_dynamiczna"] = True
            w = L0.get("wariant")
            for nm in (L0.get("od"), L0.get("do")):
                o_ = bpy.data.objects.get(nm) if nm else None
                if w is None and o_ is not None and o_.get("wariant"):
                    w = o_["wariant"]
            if w:
                ob["wariant"] = w
        par = lst[0]["parent"]
        if par is not None:
            ob.parent = par
            ob.matrix_parent_inverse = par.matrix_world.inverted()
        out.append(ob)
    return out


# ---------------------------------------------------------------- jufersy
def jufers(sk, c, n_face, up, D, mat="drewno_ciemne"):
    """Jufers: krążek o średnicy D, grubości D/2, rowek na obwodzie, 3 otwory. Zwraca położenia otworów
    (przód) i grubość."""
    n_face = Vector(n_face).normalized()
    up = (Vector(up) - n_face * Vector(up).dot(n_face)).normalized()
    R = D / 2
    T = D / 2
    prof = [(R * 0.82, -T / 2), (R * 0.97, -T * 0.32), (R * 0.86, 0.0), (R * 0.97, T * 0.32), (R * 0.82, T / 2)]
    N.lathe(sk, prof, mat, c, axis=n_face, sides=10, ref=up)
    side = up.cross(n_face).normalized()
    if n_face.x < 0:
        side = -side          # prawa burta: kipy w odbiciu lustrzanym lewej (talrep prowadzony jak po lewej)
    holes = []
    for a in (90, 210, 330):
        t = math.radians(a)
        holes.append(c + (up * math.sin(t) + side * math.cos(t)) * R * 0.45)
    # kipy (otwory) widać przez ciemne talrepy wchodzące w lico – bez osobnych dysków (bryła zamknięta, mniej trójkątów)
    return holes, T


def talrep(ctx, u_holes, l_holes, n_face, T, d, grupa="talrepy"):
    """Talrep (rozdział 06): przez 3 kipy, 6 odcinków między jufersami – 3 z przodu, 3 z tyłu (ostatni z dolnej kipy
    do górnej tylnej, gdzie talrep zaczyna się węzłem)."""
    f = n_face * (T / 2 + d / 2)
    pairs = [(u_holes[1] + f, l_holes[1] + f), (u_holes[0] + f, l_holes[0] + f), (u_holes[2] + f, l_holes[2] + f),
             (l_holes[1] - f, u_holes[0] - f), (l_holes[0] - f, u_holes[2] - f), (l_holes[2] - f, u_holes[1] - f)]
    for a, b in pairs:
        lina(ctx, grupa, [a, b], d, "lina_jasna")


# ---------------------------------------------------------------- ławy wantowe
def pozycje_jufersow(K, O, s_d, key):
    """Położenia (s) jufersów na ławie wantowej masztu (od dziobu ku rufie, z pominięciem furt) i zakres deski ławy
    (s0, s1). Czysta funkcja parametrów – używana też przed budową drzewc (rufa_dziob: woluta uskoku przed ławą)."""
    hw = K["FURTA_SZER"] / 2 + 0.11
    ports = list(K["FURTY_S"]) + list(K.get("FURTY_ZAMKNIETE_S", []))
    n_all = O["WANTY"][key] + O["PADUNY_STENGOWE"] + O["PADUNY_BRAM"]
    s = s_d + 0.30
    pos = []
    while len(pos) < n_all:
        if any(abs(s - p0) < hw for p0 in ports):
            p0 = [p0 for p0 in ports if abs(s - p0) < hw][0]
            s = p0 - hw - 0.001
            continue
        pos.append(s)
        s -= O["JUFERSY_ROZSTAW"]
    return pos, pos[-1] - 0.32, pos[0] + 0.32


def lawy(ctx):
    kd, K, PR = ctx["kd"], ctx["K"], ctx["PR"]
    O = PR.OLINOWANIE
    ps = ctx["poszycie"]
    rig = ctx["rig"]
    sk = N.Siatka("lawy_wantowe")
    hw = K["FURTA_SZER"] / 2 + 0.11
    ports = list(K["FURTY_S"]) + list(K.get("FURTY_ZAMKNIETE_S", []))
    rig["lawy"] = {}
    for key in ("fok", "grot"):
        R_ = rig["maszty"][key]
        m = R_["m"]
        n_sh = O["WANTY"][key]
        pos, s0, s1 = pozycje_jufersow(K, O, m.s(m.z_d), key)      # jufersy z pominięciem furt
        z_of = lambda s_: ps.rail_top(s_) - 0.035      # górna płaszczyzna ławy pod zewnętrznym okapem pokrywy relingu
        # deska ławy: od burty na zewnątrz LAWA_SZER, grubość LAWA_GR, wzdłuż wzniosu
        # wcięcie od spodu nad furtami pod ławą (0,045 m na szerokości pokrywy + 4 cm przejścia): pokrywa furty
        # otwarta ponad lufę opiera się w nim (po zamknięciu ławy jako bryły pokrywa furty pod ławą foka otwierała
        # się tylko do 30° i lufa przechodziła przez pokrywę)
        hw_p = K["FURTA_SZER"] / 2 + 0.07
        pod_lawa = [p0 for p0 in ports if s0 < p0 < s1]
        ss = set(float(v) for v in np.linspace(s0, s1, 12))
        # na uskoku nadburcia (pokład rufowy) próbki co 0,1 m: deska idzie za krzywą uskoku, a nie cięciwą
        # (cięciwa schodziła w wolutę uskoku – 2,2 cm wejścia)
        sq_ = K["POLPOKLAD_S"]
        ss |= {float(v) for v in np.arange(sq_ - 0.1, sq_ + 1.05, 0.1) if s0 < v < s1}
        for p0 in pod_lawa:
            ss |= {p0 + sg * d_ for sg in (-1, 1) for d_ in (hw_p, hw_p + 0.04) if s0 < p0 + sg * d_ < s1}
        ss = sorted(ss)

        def wciecie(s_):
            g = 0.0
            for p0 in pod_lawa:
                d_ = abs(s_ - p0)
                g = max(g, 0.045 if d_ <= hw_p + 1e-6 else 0.045 * max(0.0, 1 - (d_ - hw_p) / 0.04))
            return g
        for side in (1, -1):
            inner_, outer_ = [], []
            for s_ in ss:
                z = z_of(s_)
                x, (nx, ns) = ps.outer(s_, z)
                inner_.append((x - 0.02, s_, z))
                outer_.append((x + O["LAWA_SZER"] * nx, s_ + O["LAWA_SZER"] * ns, z))
            vt, vb = [], []
            for (a, b) in zip(inner_, outer_):
                g = wciecie(a[1])
                vt.append((sk.vert(P(side * a[0], a[1], a[2])), sk.vert(P(side * b[0], b[1], b[2]))))
                vb.append((sk.vert(P(side * a[0], a[1], a[2] - O["LAWA_GR"] + g)),
                           sk.vert(P(side * b[0], b[1], b[2] - O["LAWA_GR"] + g))))
            for i in range(len(ss) - 1):
                q = [vt[i][0], vt[i + 1][0], vt[i + 1][1], vt[i][1]]
                sk.face_proj(q if side > 0 else q[::-1], "drewno_czarne")
                q = [vb[i][1], vb[i + 1][1], vb[i + 1][0], vb[i][0]]
                sk.face_proj(q if side > 0 else q[::-1], "drewno_czarne")
                q = [vt[i][1], vt[i + 1][1], vb[i + 1][1], vb[i][1]]
                sk.face_proj(q if side > 0 else q[::-1], "drewno_czarne")
                # ściana od burty (2 cm w poszyciu, niewidoczna) – deska jest bryłą zamkniętą
                q = [vt[i][0], vb[i][0], vb[i + 1][0], vt[i + 1][0]]
                sk.face_proj(q if side > 0 else q[::-1], "drewno_czarne")
            for (a_, b_) in ((vt[0], vb[0]), (vt[-1], vb[-1])):
                q = [a_[0], a_[1], b_[1], b_[0]]
                sk.face_proj(q, "drewno_czarne")
            # wsporniki pod ławą
            kand = [s0 + 0.15 + k * 0.1 for k in range(int((s1 - s0 - 0.3) / 0.1) + 1)]
            kand = [s_ for s_ in kand if all(abs(s_ - p0) > K["FURTA_SZER"] / 2 + 0.12 for p0 in ports)]
            wyb = []
            for cel in (s0 + 0.15, (s0 + s1) / 2, s1 - 0.15):
                if kand:
                    c_ = min(kand, key=lambda q: abs(q - cel))
                    if all(abs(c_ - w_) > 0.3 for w_ in wyb):
                        wyb.append(c_)
            for s_ in wyb:
                z = z_of(s_)
                x, (nx, ns) = ps.outer(s_, z - 0.35)
                a = P(side * (x + 0.03), s_, z - 0.6)
                b = P(side * (x + O["LAWA_SZER"] * 0.8), s_, z - O["LAWA_GR"] - 0.01)
                N.oriented_box(sk, a, b, 0.08, 0.08, "drewno_czarne")
        # jufersy dolne + puttingi
        D_low = O["JUFERS_Z_OBWODU"] * (O["D_WANTY_GROT" if key == "grot" else "D_WANTY_FOK"] * math.pi) / 0.0254 * 0.0254
        dead = []
        for i, s_ in enumerate(pos):
            z = z_of(s_)
            x, (nx, ns) = ps.outer(s_, z)
            xo = x + O["LAWA_SZER"] * nx - 0.06
            is_bs = i >= n_sh
            Dd = D_low if not is_bs else D_low * 0.85
            dead.append(dict(s=s_, x=xo, z=z + Dd / 2 + 0.01, D=Dd, backstay=is_bs, nx=nx, ns=ns))
            # putting: od dolnego jufersa w dół po burcie do berghołtu (na linii pokładu − 0,12)
            zb = float(ps.Zd(s_)) - 0.12
            xb, (nxb, nsb) = ps.outer(s_, zb)
            for side in (1, -1):
                a = P(side * (xo + 0.01), s_, z - 0.02)
                b = P(side * (xb + 0.07), s_, zb)
                N.oriented_box(sk, a, b, 0.05, 0.018, "zelazo", up=Vector((side, 0, 0)))
                N.cylinder(sk, b + Vector((side * -0.02, 0, 0)), b + Vector((side * 0.03, 0, 0)), 0.035, 0.035,
                           "zelazo", sides=8)
        rig["lawy"][key] = dict(dead=dead, s0=s0, s1=s1, n_sh=n_sh)
    ob = N.to_object(sk, ctx["kol"]["kadlub"], recalc=True)
    ob.data.set_sharp_from_angle(angle=math.radians(35))
    return ob


# ---------------------------------------------------------------- wanty, wyblinki, podwantki
def wanty(ctx):
    PR = ctx["PR"]
    O = PR.OLINOWANIE
    D = PR.DRZEWCA
    rig = ctx["rig"]
    sk = N.Siatka("jufersy")
    for key in ("fok", "grot"):
        R_ = rig["maszty"][key]
        m, st, br, top = R_["m"], R_["st"], R_["br"], R_["top"]
        lw = rig["lawy"][key]
        d_sh = O["D_WANTY_GROT" if key == "grot" else "D_WANTY_FOK"]
        hs = m.sr * D["TAPER_MASZT"][5] / 2
        zt = m.z_top
        z_stave = zt - 1.6
        for side in (1, -1):
            shrouds = []
            for i, de in enumerate(lw["dead"]):
                if de["backstay"]:
                    continue
                top_pt = P(side * (hs + 0.13), m.s(zt + 0.02) - 0.05 * (i - 2), zt + 0.02 + 0.03 * (i // 2))
                low_c = P(side * de["x"], de["s"], de["z"])
                dirv = (top_pt - low_c).normalized()
                up_c = low_c + dirv * (de["D"] * O["JUFERS_ODSTEP"])
                n_face = Vector((side * de["nx"], -de["ns"], 0)).normalized()
                hl, T = jufers(sk, low_c, n_face, dirv, de["D"])
                hu, _ = jufers(sk, up_c, n_face, -dirv, de["D"])
                talrep(ctx, hu, hl, n_face, T, O["D_TALREP"])
                a = up_c + dirv * (de["D"] / 2)
                lina(ctx, "wanty_" + key, [a, top_pt], d_sh)
                # opaska (strop) wokół górnego jufersa
                ring = [up_c + (dirv * math.cos(t) + dirv.cross(n_face).normalized() * math.sin(t)) * (de["D"] / 2 + 0.01)
                        for t in np.linspace(0, 2 * math.pi, 17)]
                lina(ctx, "wanty_" + key, ring, d_sh * 0.8)
                shrouds.append((a, top_pt))
            # wyblinki (rozdział 06): od ok. 0,8 m nad górnymi jufersami do drążka podwantek, co 0,36 m, zwis 1,5 %
            z0 = max(s_[0].z for s_ in shrouds) + 0.80
            rows = []
            z = z0
            while z < z_stave - 0.15:
                rows.append(z)
                z += O["WYBLINKI_ROZSTAW"]

            def at(sh, z):
                a, b = sh
                t = (z - a.z) / (b.z - a.z)
                return a.lerp(b, t)
            for j, z in enumerate(rows):
                k0, k1 = (1, len(shrouds) - 2) if j < 6 else (0, len(shrouds) - 1)
                for k in range(k0, k1):
                    p0, p1 = at(shrouds[k], z), at(shrouds[k + 1], z)
                    lina(ctx, "wyblinki", [p0, p1], O["D_WYBLINKA"], sag=O["WYBLINKI_ZWIS"], n=3)
            # drążek podwantek (futtock stave) i podwantki do krawędzi marsa
            ps0 = at(shrouds[0], z_stave)
            ps1 = at(shrouds[-1], z_stave)
            N.cylinder(sk, ps0 + (ps0 - ps1).normalized() * 0.08, ps1 + (ps1 - ps0).normalized() * 0.08, 0.03, 0.03,
                       "drewno_ciemne", sides=6)
            nfs = O["WANTY_STENGOWE"]
            for k in range(nfs):
                f = (k + 0.5) / nfs
                sp = ps0.lerp(ps1, 0.15 + 0.7 * f)
                rim = P(side * top["W"] / 2 * 0.95, top["c_s"] + (-0.35 + 0.7 * f) * top["Lt"] * 0.5 if False else
                        top["c_s"] + (-0.30 + 0.6 * f), top["z"] - 0.06)
                lina(ctx, "podwantki", [rim, sp], O["D_PODWANTKA"])
                N.box(sk, rim + Vector((side * 0.01, 0, 0.06)), (0.02, 0.06, 0.16), "zelazo")
            R_.setdefault("stave", {})[side] = (ps0, ps1)
            R_.setdefault("shrouds", {})[side] = shrouds
        # ściągacze: 4 liny między drążkami obu burt, za masztem (grot snowa: tam stoi maszt snow – pomijam)
        a0, a1 = R_["stave"][1]
        b0, b1 = R_["stave"][-1]
        for k in range(0 if (key == "grot" and ctx["snow"]) else 4):
            f = 0.3 + 0.15 * k
            pa, pb = a0.lerp(a1, f), b0.lerp(b1, f)
            mid = P(0, m.s(z_stave) - 0.0, z_stave + 0.05)
            mid = Vector((0, pa.y + 0.35, z_stave - 0.08))
            lina(ctx, "sciagacze", [pa, mid, pb], 0.024)
        # wanty stengowe: z topu stengi do jufersów na krawędzi marsa (3 na burtę), z wyblinkami
        d_ts = O["D_WANTY_STENG"]
        D_ts = 0.13
        zh = st.z_head
        for side in (1, -1):
            shr = []
            for k in range(O["WANTY_STENGOWE"]):
                f = (k + 0.5) / O["WANTY_STENGOWE"]
                lc = P(side * (top["W"] / 2 * 0.95 + 0.03), top["c_s"] + (-0.30 + 0.6 * f), top["z"] + D_ts / 2 + 0.02)
                tp = P(side * (st.sr * 0.4 + 0.08), st.s(zh) - 0.04 * k, zh + 0.04)
                dv = (tp - lc).normalized()
                uc = lc + dv * (D_ts * 2.7)
                nf = Vector((side, 0, 0))
                hl, T = jufers(sk, lc, nf, dv, D_ts)
                hu, _ = jufers(sk, uc, nf, -dv, D_ts)
                talrep(ctx, hu, hl, nf, T, O["D_TALREP_STENG"])
                lina(ctx, "wanty_stengowe", [uc + dv * D_ts / 2, tp], d_ts)
                shr.append((uc + dv * D_ts / 2, tp))
            z = shr[0][0].z + 0.45
            while z < zh - 0.9:
                for k in range(len(shr) - 1):
                    a, b = shr[k], shr[k + 1]
                    pa = a[0].lerp(a[1], (z - a[0].z) / (a[1].z - a[0].z))
                    pb = b[0].lerp(b[1], (z - b[0].z) / (b[1].z - b[0].z))
                    lina(ctx, "wyblinki", [pa, pb], O["D_WYBLINKA"], sag=O["WYBLINKI_ZWIS"], n=3)
                z += O["WYBLINKI_ROZSTAW"]
            # wanty bramstengowe: z topu bramstengi do końców salingu
            zg = br.z_top - 0.95
            for k in range(O["WANTY_BRAMSTENGOWE"]):
                a = P(side * R_["Wx"] / 2 * 0.95, st.s(zh) + (-0.3 + 0.6 * k), zh + 0.2)
                b = P(side * (br.sr * 0.4 + 0.04), br.s(zg), zg)
                lina(ctx, "wanty_bramstengowe", [a, b], O["D_WANTY_BRAM"])
            # paduny: stengowe (2) i bramstengowy (1) do jufersów ławy za wantami
            bs = [de for de in lw["dead"] if de["backstay"]]
            for i, de in enumerate(bs):
                low_c = P(side * de["x"], de["s"], de["z"])
                if i < O["PADUNY_STENGOWE"]:
                    tp = P(side * (st.sr * 0.4 + 0.06), st.s(zh) - 0.05, zh + 0.12 + 0.05 * i)
                    d_ = O["D_PADUN_STENG"]
                else:
                    tp = P(side * (br.sr * 0.4 + 0.03), br.s(zg) - 0.03, zg + 0.05)
                    d_ = O["D_PADUN_BRAM"]
                dv = (tp - low_c).normalized()
                up_c = low_c + dv * (de["D"] * 2.7)
                nf = Vector((side * de["nx"], -de["ns"], 0)).normalized()
                hl, T = jufers(sk, low_c, nf, dv, de["D"])
                hu, _ = jufers(sk, up_c, nf, -dv, de["D"])
                talrep(ctx, hu, hl, nf, T, O["D_TALREP"] * 0.8)
                lina(ctx, "paduny", [up_c + dv * de["D"] / 2, tp], d_)
        # pętle want na topie kolumny (stos pierścieni nad belkami)
        for k in range(4):
            z = zt + 0.04 + k * 0.055
            rr = hs * 1.42 + 0.03
            ring = [P(rr * math.cos(t), m.s(z) + rr * math.sin(t), z) for t in np.linspace(0, 2 * math.pi, 17)]
            lina(ctx, "wanty_" + key, ring, d_sh)
    ob = N.to_object(sk, ctx["kol"]["olinowanie"], recalc=True)
    ob.name = "jufersy"
    return ob


# ---------------------------------------------------------------- sztagi i bukszpryt
def mysz(sk, a, b, d):
    """Mysz na sztagu: wrzeciono 0,4 m w 1/3 długości od topu (rozdział 06)."""
    dv = (b - a).normalized()
    c = a.lerp(b, 1 / 3)
    N.lathe(sk, [(d / 2, -0.2), (d * 1.0, -0.12), (d * 1.6, 0.0), (d * 1.1, 0.12), (d / 2, 0.2)], "lina_smolowana",
            c, axis=dv, sides=8, close_ends=False)


def sztagi(ctx):
    kd, PR = ctx["kd"], ctx["PR"]
    O = PR.OLINOWANIE
    D = PR.DRZEWCA
    rig = ctx["rig"]
    sk = N.Siatka("sztagi_okucia")
    F, G = rig["maszty"]["fok"], rig["maszty"]["grot"]
    bs = rig["bukszpryt"]
    path = bs["path"]

    def bsp(f, above=True):
        i = f * (len(path) - 1)
        i0 = int(i)
        i1 = min(i0 + 1, len(path) - 1)
        c = path[i0].lerp(path[i1], i - i0)
        rr = bs["r0"] * (bs["sc"][i0] if i0 < len(bs["sc"]) else 0.6)
        return c + bs["up3"] * (rr + 0.02) * (1 if above else -1)
    # grotsztag: top grota → pokład u stopy foka (serce i obroża)
    mf = F["m"]
    a = G["m"].p(G["m"].z_top + 0.25, ds=G["m"].sr * 0.3)
    zf = mf.z_d
    b = mf.p(zf + 0.55, ds=-(mf.r(zf) + 0.25))
    lina(ctx, "sztagi", [a, b], O["D_GROTSZTAG"], sag=0.005)
    mysz(sk, a, b, O["D_GROTSZTAG"])
    N.lathe(sk, [(0.16, -0.06), (0.17, 0), (0.16, 0.06), (0.07, 0.06), (0.07, -0.06)], "drewno_ciemne", b,
            axis=(b - a).normalized(), sides=12)
    ring = [mf.p(zf + 0.55, dx=(mf.r(zf) + 0.03) * math.cos(t), ds=(mf.r(zf) + 0.03) * math.sin(t))
            for t in np.linspace(0, 2 * math.pi, 17)]
    lina(ctx, "sztagi", ring, 0.05)
    lina(ctx, "sztagi", [b + Vector((0, -0.08, 0)), mf.p(zf + 0.55, ds=-(mf.r(zf) + 0.03))], 0.03, "lina_jasna")
    # foksztag: top foka → obroża na bukszprycie (0,25 długości od pięty)
    a = mf.p(mf.z_top + 0.25, ds=mf.sr * 0.3)
    b = bsp(0.40)            # obroża ok. 1/4 wystającej części bukszprytu za dziobnicą (sztag przed reją foka)
    lina(ctx, "sztagi", [a, b], O["D_FOKSZTAG"], sag=0.004)
    mysz(sk, a, b, O["D_FOKSZTAG"])
    # sztagi stengowe
    st_g, st_f = G["st"], F["st"]
    lina(ctx, "sztagi", [st_g.p(st_g.z_head + 0.1, ds=0.1), mf.p(mf.z_top + 0.45, ds=mf.sr * 0.4)], O["D_SZTAG_STENG"])
    lina(ctx, "sztagi", [st_f.p(st_f.z_head + 0.1, ds=0.1), bsp(0.62)], O["D_SZTAG_STENG"])
    # sztagi bramstengowe i sztag kliwra
    br_g, br_f = G["br"], F["br"]
    lina(ctx, "sztagi", [br_g.p(br_g.z_top - 0.9, ds=0.06), st_f.p(st_f.z_head + 0.2, ds=0.3)], O["D_SZTAG_BRAM"])
    j0, j1 = bs["j0"], bs["j1"]
    jdir = (j1 - j0).normalized()
    lina(ctx, "sztagi", [br_f.p(br_f.z_top - 0.9, ds=0.06), j1 - jdir * 0.25], O["D_SZTAG_BRAM"])
    lina(ctx, "sztagi", [st_f.p(st_f.z_head + 0.05, ds=0.12), j1 - jdir * 0.6], O["D_SZTAG_KLIWRA"], sag=0.004)
    # watersztagi: z bukszprytu do kolana galionu nad wodą
    from rufa_dziob import stem_face, GALION
    sf = stem_face(ctx)
    kn = np.array(GALION["KOLANO"])
    for k, f in enumerate((0.56, 0.66)[:O["WATERSZTAGI"]]):
        zb = 0.25 + 0.25 * k
        pb = P(0, sf(zb) + float(np.interp(zb, kn[:, 0], kn[:, 1])) + 0.03, zb)
        pa = bsp(f, above=False)
        lina(ctx, "sztagi", [pa, pb], O["D_WATERSZTAG"])
        N.lathe(sk, [(0.1, -0.04), (0.11, 0), (0.1, 0.04), (0.04, 0.04), (0.04, -0.04)], "drewno_ciemne",
                pa.lerp(pb, 0.12), axis=(pb - pa).normalized(), sides=10)
    # wanty bukszprytu: z 0,5 długości na burty dziobu
    ps = ctx["poszycie"]
    for k, f in enumerate((0.48, 0.58)[:O["WANTY_BUKSZPRYTU"]]):
        for side in (1, -1):
            s_h = 12.9 - 0.45 * k
            x, (nx, ns) = ps.outer(s_h, 1.55)
            ph = P(side * (x + 0.04), s_h, 1.55)
            pa = bsp(f, above=False) + Vector((side * bs["r0"] * 0.6, 0, 0))
            lina(ctx, "sztagi", [pa, ph], O["D_WANTY_BUKSZ"])
            N.cylinder(sk, ph, ph + Vector((side * 0.05, 0, 0)), 0.04, 0.04, "zelazo", sides=8)
    # wiązanie bukszprytu: 9 zwojów nad głowicą dziobnicy do otworu w kolanie galionu
    st_head = ctx["K"]["DZIOB"][-1]
    z_hole = 2.55
    s_hole = sf(z_hole) + 0.3
    for k in range(O["WIAZANIE_ZWOJE"]):
        ds = (k - (O["WIAZANIE_ZWOJE"] - 1) / 2) * 0.045
        # punkt na bukszprycie nad głowicą
        f = 0.36 + ds / bs["L"]
        c = bsp(f, above=True)
        cb = bsp(f, above=False)
        mid = (c + cb) / 2
        rr = (c - cb).length / 2 + 0.01
        pts = []
        for t in np.linspace(-math.pi / 2, math.pi / 2, 9):
            pts.append(mid + bs["up3"] * (rr * math.sin(t)) + Vector((rr * math.cos(t), 0, 0)))
        hole = P(0, s_hole + ds * 0.4, z_hole)
        side_l = [P(0.14, hole.y * -1 if False else -(s_hole + ds * 0.4), z_hole)]
        pts_full = [P(0.13, s_hole + ds * 0.4, z_hole)] + pts[::-1] + [P(-0.13, s_hole + ds * 0.4, z_hole)]
        lina(ctx, "wiazanie", pts_full, O["D_WIAZANIE"])
    ob = N.to_object(sk, ctx["kol"]["olinowanie"], recalc=False)
    ob.name = "sztagi_okucia"
    return ob


# ---------------------------------------------------------------- liny na rejach
def reje_liny(ctx):
    PR = ctx["PR"]
    O = PR.OLINOWANIE
    rig = ctx["rig"]
    for nam, R in rig["reje"].items():
        if nam in ("gafel", "bom"):
            continue
        ob = R["obj"]
        c = Vector(R["c"])
        L = R["L"]
        sr = R["sr"]
        lower = nam in ("fok", "grot")
        tops = nam.endswith("mars")
        if not (lower or tops or nam == "blinda"):
            continue
        drop = O["PERTA_ZWIS"] if lower else 0.6
        nst = O["STRZEMIONA"] if lower else O["STRZEMIONA_MARS"]
        for side in (1, -1):
            a = c + Vector((side * L / 2 * 0.95, 0.0, 0.0))
            b = c + Vector((-side * 0.45, 0.0, 0.0))
            # rozdział 06: perty dolnych rej wiszą ok. 0,9 m pod reją (najniższy punkt łuku)
            pts = N.catenary(a, b, drop, 18)
            # perta wisi z tyłu rei (od strony rufy: +Y Blendera)
            pts = [p + Vector((0, sr * 0.6, -sr * 0.2)) for p in pts]
            # koniec perty przy noku (oko na rei): punkt 0,25 średnicy za osią, wewnątrz zbieżnej rei (z przesunięciem
            # łuku wisiał 5–7 cm za cienką reją); koniec przy maszcie bez zmian (tam wałek żagla)
            pts[0] = a + Vector((0, sr * 0.25, 0))
            lina(ctx, "perty", pts, O["D_PERTA"], parent=ob)
            for k in range(nst):
                f = (k + 1) / (nst + 1)
                x = side * (0.45 + (L / 2 * 0.95 - 0.45) * (1 - f))
                # punkt perty pod x
                best = min(pts, key=lambda p: abs(p.x - (c.x + x)))
                top = c + Vector((x, sr * 0.35, sr * 0.4))
                lina(ctx, "perty", [top, best], O["D_STRZEMIE"], parent=ob)
    # stropy dolnych rej i tie marsrei
    for key in ("fok", "grot"):
        R_ = rig["maszty"][key]
        m, st = R_["m"], R_["st"]
        y = rig["reje"][key]
        c = Vector(y["c"])
        lina(ctx, "stropy", [m.p(m.z_top + 0.05, ds=m.sr * 0.25), c + Vector((0, 0, y["sr"] / 2))], 0.032)
        ym = rig["reje"][key + "mars"]
        cm = Vector(ym["c"])
        lina(ctx, "stropy", [cm + Vector((0, 0, ym["sr"] / 2)), st.p(st.z_head - 0.25, ds=st.sr / 2 + 0.02)], 0.032,
             "lina_jasna")


def zbuduj(ctx):
    lawy(ctx)
    wanty(ctx)
    sztagi(ctx)
    reje_liny(ctx)
    # rurki powstają na końcu budowy (buduj.py → realizuj), po linach wyposażenia i olinowania ruchomego
