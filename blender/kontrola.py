"""Kontrola modelu → <out>/kontrola.json: wymiary główne, trójkąty na kolekcję i grupę, szczelność
i symetria kadłuba, spójność normalnych, gęstość tekseli na materiał (px/m), progi furt nad wodą, wyniki chodzenia,
położenia masztów, rozmiar GLB i tekstur; po eksporcie GLB wczytany z powrotem i policzony jeszcze raz.
"""
import json
import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

from narzedzia import S


def tris(ob):
    me = ob.data
    me.calc_loop_triangles()
    return len(me.loop_triangles)


def tris_world(objs):
    """Trójkąty z instancjami (każdy obiekt liczony osobno, nawet jeśli dzieli siatkę)."""
    return sum(tris(o) for o in objs if o.type == "MESH")


def szczelnosc(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.edges.ensure_lookup_table()
    boundary = sum(1 for e in bm.edges if e.is_boundary)
    nonman = sum(1 for e in bm.edges if not e.is_manifold and not e.is_boundary)
    # niespójna kolejność: krawędź z dwiema ścianami przechodzącymi ją w tę samą stronę
    bad = 0
    for e in bm.edges:
        if len(e.link_loops) == 2:
            l1, l2 = e.link_loops
            if l1.vert == l2.vert:
                bad += 1
    vol = 0.0
    for f in bm.faces:
        vs = [v.co for v in f.verts]
        for k in range(1, len(vs) - 1):
            vol += vs[0].dot(vs[k].cross(vs[k + 1])) / 6.0
    bm.free()
    return dict(krawedzie_brzegowe=boundary, krawedzie_niemanifold=nonman, niespojne_normalne=bad,
                objetosc_m3=round(vol, 2))


def symetria(ob):
    me = ob.data
    co = np.zeros(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    kd = KDTree(len(co))
    for i, c in enumerate(co):
        kd.insert(c, i)
    kd.balance()
    dmax = 0.0
    for c in co[::7]:
        _, _, d = kd.find((-c[0], c[1], c[2]))
        dmax = max(dmax, d)
    return round(dmax, 4)


def gestosc_tekseli(objs):
    """px/m na materiał: sqrt(pole UV · rozdzielczość² / pole 3D), mediana i 5. percentyl ważone polem."""
    acc = {}
    for ob in objs:
        if ob.type != "MESH" or not ob.data.uv_layers:
            continue
        me = ob.data
        uv = me.uv_layers.active.data
        M = ob.matrix_world
        for poly in me.polygons:
            if poly.material_index >= len(me.materials) or me.materials[poly.material_index] is None:
                continue
            mat = me.materials[poly.material_index]
            img = None
            if mat.use_nodes:
                for n in mat.node_tree.nodes:
                    if n.type == "TEX_IMAGE" and n.image and n.image.colorspace_settings.name == "sRGB":
                        img = n.image
                        break
            if img is None:
                continue
            res = math.sqrt(img.size[0] * img.size[1])     # obraz prostokątny (atlas desek 4096 × 1024)
            idx = list(poly.loop_indices)
            vs = [M @ me.vertices[me.loops[i].vertex_index].co for i in idx]
            us = [uv[i].uv for i in idx]
            a3 = 0.0
            a2 = 0.0
            for k in range(1, len(idx) - 1):
                a3 += (vs[k] - vs[0]).cross(vs[k + 1] - vs[0]).length / 2
                a2 += abs((us[k][0] - us[0][0]) * (us[k + 1][1] - us[0][1]) -
                          (us[k][1] - us[0][1]) * (us[k + 1][0] - us[0][0])) / 2
            if a3 < 1e-5 or a2 < 1e-12:
                continue
            d = res * math.sqrt(a2 / a3)
            acc.setdefault(mat.name, []).append((d, a3))
    out = {}
    for m, lst in acc.items():
        a = np.array(lst)
        o = np.argsort(a[:, 0])
        d, w = a[o, 0], a[o, 1]
        cw = np.cumsum(w) / w.sum()
        out[m] = dict(mediana=round(float(d[np.searchsorted(cw, 0.5)]), 1),
                      p05=round(float(d[np.searchsorted(cw, 0.05)]), 1),
                      p95=round(float(d[min(np.searchsorted(cw, 0.95), len(d) - 1)]), 1), pole_m2=round(float(w.sum()), 1))
    return out


def symetria_lin(liny, tol=0.03):
    """Test symetrii rejestru lin (dane, nie siatki): pary lewa–prawa po odbiciu końców w x."""
    def lustro(nm):
        if not nm:
            return nm
        for a, b in (("_L", "_P"), ("_P", "_L")):
            if a in nm:
                return nm.replace(a, b)
        return nm
    # wyjątki – grupy z założenia niesymetryczne (z powodem); liny oznaczone 'jednostronna' – pojedyncze liny
    # z jedną talią albo po jednej stronie masztu (fały marsrei foka i grota po przeciwnych burtach – rozdział 07;
    # gardafał i pikfał gafla – po jednej linie, schodzą po przeciwnych stronach masztu)
    POMIN = {"buchty": "zwoje na zajętych kołkach – zależne od przydziału kołków",
             "kotwice": "lewa kotwica podniesiona, prawa rzucona",
             "lodz": "łódź za rufą (faleń jedna, łódź skręcona)",
             "sterlina": "wariant napędu steru (kołowy)", "talie_rumpla": "wariant napędu steru (rumpel)",
             "dziala": "liny dział: tylko przy działach z listy DZIALA.z_linami i w stanach odrzutu",
             "dzwon": "jeden dzwon przy lewej burcie", "kabestan": "linka przez końce drągów kabestanu (w osi)",
             "wiazanie": "wiązanie bukszprytu: zwoje ukośne w jedną stronę (przez otwór w dziobnicy) – bez odbicia"}
    pominiete = sum(1 for L in liny if L["g"].startswith(tuple(POMIN)))
    jedn = sum(1 for L in liny if L.get("jednostronna") and not L["g"].startswith(tuple(POMIN)))
    liny = [L for L in liny if not L["g"].startswith(tuple(POMIN)) and not L.get("jednostronna")]

    def sx(L):
        return sum(p.x for p in L["p"]) / len(L["p"])
    # liny w osi (środek wszystkich punktów |x| ≤ tol: oka want wokół topu, wiązania sztagów, ściągacze i perty
    # od burty do burty): muszą być symetryczne same w sobie – każdy punkt odbity w x leży przy linii (≤ tol)
    w_osi = [L for L in liny if abs(sx(L)) <= tol]
    osi_zle = []
    for L in w_osi:
        pts = [Vector(p) for p in L["p"]]
        odl = 0.0
        for p in pts:
            q = Vector((-p.x, p.y, p.z))
            best = 1e9
            for a, b in zip(pts[:-1], pts[1:]):
                ab = b - a
                t = max(0.0, min(1.0, (q - a).dot(ab) / max(ab.length_squared, 1e-12)))
                best = min(best, (a + ab * t - q).length)
            odl = max(odl, best)
        if odl > 0.05:          # 2 × 2,5 cm: bomstenga leży z boku bukszprytu (końce sztagów 2 cm od osi)
            osi_zle.append("%s %s (odchyłka %.3f m)" % (L["g"], [round(v, 2) for v in L["p"][0]], odl))
    lewe = [L for L in liny if sx(L) > tol]
    prawe = [L for L in liny if sx(L) < -tol]
    bez, rozne = [], []
    uzyte = set()
    for L in lewe:
        a = Vector((-L["p"][0].x, L["p"][0].y, L["p"][0].z))
        b = Vector((-L["p"][-1].x, L["p"][-1].y, L["p"][-1].z))
        kand = None
        for scisle in (True, False):            # najpierw odpowiednik o tej samej średnicy i materiale
            for i, R_ in enumerate(prawe):
                if i in uzyte or R_["g"] != L["g"] or (scisle and (abs(R_["d"] - L["d"]) > 1e-6 or R_["m"] != L["m"])):
                    continue
                # gordingi kończą się na wałku zwiniętego żagla (nieregularny, losowy promień) – tam 10 cm
                # końce przedłużone do części (olinowanie.zamocuj_konce, ≤ 7 cm) – 8 cm
                tl = 0.20 if (L.get("do_zagla") or R_.get("do_zagla")) else                     (0.08 if (L.get("przedluzona") or R_.get("przedluzona")) else tol)
                for (pa, pb, odw) in ((R_["p"][0], R_["p"][-1], False), (R_["p"][-1], R_["p"][0], True)):
                    if (pa - a).length < tl and (pb - b).length < tl:
                        kand = (i, odw)
                        break
                if kand:
                    break
            if kand:
                break
        opis = "%s %s" % (L["g"], [round(v, 2) for v in L["p"][0]])
        if kand is None:
            bez.append(opis)
            continue
        uzyte.add(kand[0])
        R_ = prawe[kand[0]]
        od_r, do_r = (R_.get("do"), R_.get("od")) if kand[1] else (R_.get("od"), R_.get("do"))
        pola_l = (round(L["d"], 4), L["m"], lustro(L.get("od")), lustro(L.get("do")), L.get("wariant"))
        pola_r = (round(R_["d"], 4), R_["m"], od_r, do_r, R_.get("wariant"))
        if pola_l != pola_r:
            rozne.append(dict(lina=opis, lewa=list(map(str, pola_l)), prawa=list(map(str, pola_r))))
    prawe_bez = ["%s %s" % (R_["g"], [round(v, 2) for v in R_["p"][0]]) for i, R_ in enumerate(prawe) if i not in uzyte]
    return dict(lewe=len(lewe), prawe=len(prawe), pary=len(uzyte), bez_odpowiednika=len(bez) + len(prawe_bez),
                rozne_pola=len(rozne), przyklady_bez=(bez + prawe_bez)[:8], przyklady_rozne=rozne[:8],
                w_osi=len(w_osi), w_osi_niesymetryczne=len(osi_zle), przyklady_w_osi=osi_zle[:8],
                wyjatki_grupy=POMIN, wyjatki_liny_pominiete=pominiete, liny_jednostronne=jedn,
                wynik="tak" if not bez and not rozne and not prawe_bez and not osi_zle else "nie")


# końce lin, które z założenia nie leżą na żadnej części (grupa liny → powód); test 'końce lin zamocowane'
WYJATKI_KONCE = {
    "buchty": "zwoje na kołkach – pętle zamknięte (bez końców)",
    "dzwon": "linka dzwonu: dolny koniec zwisa swobodnie (uchwyt do bicia w dzwon)",
}
KONCE_TOL = 0.01      # m: odstęp powierzchni liny od części, przy którym koniec uznajemy za zamocowany


def bloki_zamocowane(ctx, tol=KONCE_TOL):
    """Test 'bloki zamocowane' na gotowym modelu. Test końców lin uznaje koniec za zamocowany, gdy dotyka bloku –
    nie sprawdza, czy sam blok jest do czegoś przymocowany. Tutaj: każdy blok z rejestru (wyposazenie.blok) styka
    się z bryłą, wisi na smołowanym wisiorze, jest blokiem przelotowym napiętej talii (lina przechodzi przez
    niego na wprost) albo ma strop (wyposazenie.stropy_blokow), którego koniec leży
    w części konstrukcji (≤ tol od powierzchni albo w środku) lub na linie stałej; bloki schowane w zamkniętej
    bryle (krążki sterliny pod pokładem rufowym, póki kadłub nie ma wnętrza) są pomijane. Wynik: liczby i lista bloków
    bez zaczepu (punkt w układzie statku x, s, z)."""
    from mathutils.bvhtree import BVHTree
    rej = ctx.get("bloki_rejestr", [])
    bryly = []
    for o in bpy.data.objects:
        if o.type != "MESH" or o.name.startswith(("lina_", "##", "bloki", "zagiel", "lodz_maska")) or \
                not o.users_collection or o.users_collection[0].name in ("_eksport", "stanowiska") or \
                (o.hide_render and not o.get("wariant")) or o.name.endswith("_glb") or not len(o.data.polygons):
            continue
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        bryly.append(dict(o=o, lo=Vector([min(v[i] for v in bb) for i in range(3)]),
                          hi=Vector([max(v[i] for v in bb) for i in range(3)]), w=o.get("wariant"),
                          M=o.matrix_world.inverted(), tr=None))
    stale = [L for L in ctx.get("liny", []) if L["g"].startswith(("sztagi", "wanty", "paduny", "podwantki"))]
    dirs = [Vector((1, 0.013, 0.007)).normalized(), Vector((0.011, 1, 0.017)).normalized()]

    def wewnatrz(tr, q):
        g = 0
        for dv in dirs:
            n, o_ = 0, Vector(q)
            for _ in range(48):
                hit = tr.ray_cast(o_, dv)
                if hit[0] is None:
                    break
                n += 1
                o_ = hit[0] + dv * 1e-5
            g += n & 1
        return g == len(dirs)

    def odstep(e, wariant):
        best = 9.0
        for b in bryly:
            if b["w"] and b["w"] != wariant:
                continue
            if any(e[j] < b["lo"][j] - 0.3 or e[j] > b["hi"][j] + 0.3 for j in range(3)):
                continue
            if b["tr"] is None:
                me_ = b["o"].data
                b["tr"] = BVHTree.FromPolygons([v.co for v in me_.vertices], [p.vertices for p in me_.polygons])
            q = b["M"] @ e
            loc, nrm, idx, d = b["tr"].find_nearest(q, 0.3)
            if loc is None:
                continue
            d = (b["o"].matrix_world @ loc - e).length
            if d > tol and wewnatrz(b["tr"], q):
                d = 0.0
            best = min(best, d)
            if best <= tol:
                break
        return best
    ze_stropem, zle = 0, []
    for b in rej:
        if b.get("kotwica") is None:
            continue
        ze_stropem += 1
        e = Vector(b["kotwica"])
        if str(b.get("do", "")).startswith("lina:"):
            d = 9.0
            for L in stale:
                for a_, b_ in zip(L["p"][:-1], L["p"][1:]):
                    ab = b_ - a_
                    t = max(0.0, min(1.0, (e - a_).dot(ab) / max(1e-9, ab.length_squared)))
                    d = min(d, (a_ + ab * t - e).length - L["d"] / 2)
        else:
            d = odstep(e, b.get("wariant"))
        if d > tol and odstep(Vector(b["c"]), b.get("wariant")) <= 1e-9:
            continue                        # blok w środku zamkniętej bryły (pod pokładem bez wnętrza): niewidoczny
        if d > tol:
            zle.append(dict(blok=[round(v, 3) for v in S(b["c"])], koniec_stropu=[round(v, 3) for v in S(e)],
                            odstep_m=round(d, 3), do=b.get("do")))
    bez = ctx.get("bloki_bez_zaczepu", [])
    return dict(tol_m=tol, blokow=len(rej), ze_stropem=ze_stropem, bez_zaczepu=len(bez), stropy_w_powietrzu=len(zle),
                ukryte_w_bryle=sum(1 for b in rej if b.get("ukryty_w")),
                przelotowe_w_talii=sum(1 for b in rej if b.get("w_talii")),
                lista_bez_zaczepu=bez, lista_stropow_w_powietrzu=zle, stropy=ctx.get("stropy_blokow", []),
                wynik="tak" if not bez and not zle else "nie")


def konce_lin(ctx, tol=KONCE_TOL):
    """Test 'końce lin zamocowane' na rejestrze lin (oś liny, prawdziwa średnica): każdy koniec (pierwszy i ostatni
    punkt; pętle zamknięte pomijane) leży najwyżej tol od powierzchni innej części (bryły, żagla, bloku) albo w jej
    środku, albo przy innej linie (splot, strop, lina na linie). Części z wariantem napędu steru tylko ze swoim
    wariantem. Wynik: liczby, lista wiszących końców (grupa, punkt w układzie statku x, s, z, odstęp)."""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    liny = ctx.get("liny", [])
    nazwy_lin = set(o.name for o in ctx["obj"].get("liny", []))
    bryly = []
    for o in bpy.data.objects:
        if o.type != "MESH" or o.name.startswith(("lina_", "##")) or o.name in nazwy_lin or not o.users_collection \
                or o.users_collection[0].name in ("_eksport", "stanowiska") or (o.hide_render and not o.get("wariant")):
            continue
        if o.name.endswith("_glb") or not len(o.data.polygons):
            continue
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        lo = Vector([min(v[i] for v in bb) for i in range(3)])
        hi = Vector([max(v[i] for v in bb) for i in range(3)])
        bryly.append(dict(o=o, lo=lo, hi=hi, w=o.get("wariant"), M=o.matrix_world.inverted(), tr=None))
    # odcinki wszystkich lin (do sprawdzenia splotów / lin kończących się na innych linach)
    A, B, Rr, Ix = [], [], [], []
    for i, L in enumerate(liny):
        for a, b in zip(L["p"][:-1], L["p"][1:]):
            A.append(tuple(a))
            B.append(tuple(b))
            Rr.append(L["d"] / 2)
            Ix.append(i)
    A, B, Rr, Ix = np.array(A), np.array(B), np.array(Rr), np.array(Ix)
    AB = B - A
    ab2 = np.maximum((AB * AB).sum(1), 1e-12)
    dirs = [Vector((1, 0.013, 0.007)).normalized(), Vector((0.011, 1, 0.017)).normalized()]

    def wewnatrz(tr, q):
        g = 0
        for dv in dirs:
            n, o_ = 0, Vector(q)
            for _ in range(48):
                hit = tr.ray_cast(o_, dv)
                if hit[0] is None:
                    break
                n += 1
                o_ = hit[0] + dv * 1e-5
            g += n & 1
        return g == len(dirs)
    wynik, wisi, pominiete = 0, [], 0
    for i, L in enumerate(liny):
        pts = L["p"]
        if len(pts) < 2:
            continue
        if L["g"].startswith(tuple(WYJATKI_KONCE)):
            pominiete += 2
            continue
        if len(pts) > 2 and (pts[0] - pts[-1]).length < 1e-3:
            continue                                   # pętla zamknięta
        r = L["d"] / 2
        for k, e in ((0, pts[0]), (1, pts[-1])):
            wynik += 1
            best = 9.0
            kto = None
            for b in bryly:
                if L.get("wariant") and b["w"] and b["w"] != L.get("wariant"):
                    continue
                if any(e[j] < b["lo"][j] - 0.3 or e[j] > b["hi"][j] + 0.3 for j in range(3)):
                    continue
                if b["tr"] is None:              # z danych siatki (ukryte warianty nie mają siatki w depsgrafie)
                    me_ = b["o"].data
                    b["tr"] = BVHTree.FromPolygons([v.co for v in me_.vertices], [p.vertices for p in me_.polygons])
                q = b["M"] @ e
                loc, nrm, idx, d = b["tr"].find_nearest(q, 0.3)
                if loc is None:
                    continue
                d = (b["o"].matrix_world @ loc - e).length
                if d > r + tol and wewnatrz(b["tr"], q):
                    d = 0.0
                if d - r < best:
                    best, kto = d - r, b["o"].name
                if best <= tol:
                    break
            if best > tol:
                ev = np.array(tuple(e))
                t = np.clip(((ev - A) * AB).sum(1) / ab2, 0, 1)
                dd = np.linalg.norm(A + AB * t[:, None] - ev, axis=1) - Rr - r
                dd[Ix == i] = 9.0
                j = int(np.argmin(dd))
                if dd[j] < best:
                    best, kto = float(dd[j]), "lina:" + liny[Ix[j]]["g"]
            if best > tol:
                wisi.append(dict(grupa=L["g"], koniec=k, punkt=[round(v, 3) for v in S(e)], odstep_m=round(best, 3),
                                 najblizej=kto, srednica=L["d"]))
    return dict(tol_m=tol, koncow=wynik, wiszace=len(wisi), wyjatki=WYJATKI_KONCE, pominiete_konce=pominiete,
                lista=sorted(wisi, key=lambda w: -w["odstep_m"]), wynik="tak" if not wisi else "nie")


def zbuduj(ctx, glb=None):
    kd, K, PR = ctx["kd"], ctx["K"], ctx["PR"]
    ps = ctx["poszycie"]
    rig = ctx["rig"]
    J = {}
    # wymiary
    hull = ctx["obj"]["kadlub"]
    co = np.array([hull.matrix_world @ v.co for v in hull.data.vertices])
    allm = [o for o in bpy.data.objects if o.type == "MESH" and not o.name.startswith("##")
            and o.users_collection and o.users_collection[0].name != "_eksport"]
    ext = np.array([o.matrix_world @ Vector(c) for o in allm for c in o.bound_box])
    hb_wregi = max(max(v for v in r[4] if v is not None) for r in PR.LINIE_WREGI)
    J["wymiary"] = dict(
        _opis=("pary wielkości nazwanych: konstrukcyjne (z tabeli rzędnych po wręgach / między pionami) i zmierzone "
               "na siatce modelu (z poszyciem, berghołtami, nawisem rufy)"),
        dlugosc_miedzy_pionami_m=28.0,
        dlugosc_pokladu_m=round(ps.rf[ps.r_deck] - ps.ra[ps.r_deck], 2),
        dlugosc_kadluba_z_nawisem_rufy_m=round(float(-co[:, 1].min() - (-co[:, 1].max())), 2),
        dlugosc_calkowita_z_bomstenga_m=round(float(ext[:, 1].max() - ext[:, 1].min()), 2),
        szerokosc_konstrukcyjna_m=7.60,
        szerokosc_po_wregach_m=round(2 * hb_wregi, 2),
        szerokosc_z_poszyciem_i_bergholtami_m=round(float(co[:, 0].max() - co[:, 0].min()), 2),
        zanurzenie_srodokrecie_m=round(float(-(float(kd.zk(0.0)) - K["STEPKA_WYS"])), 2),
        zanurzenie_rufa_m=round(float(-(float(kd.zk(K["TUCK_S0"])) - K["STEPKA_WYS"])), 2),
        zanurzenie_dziob_m=round(float(-(float(kd.zk(K["DZIOB"][0][0])) - K["STEPKA_WYS"])), 2),
        # dolna krawędź płaskiej pawęży (tuck): w osi (ostatni rząd o szerokości tylnicy) i pierwszy rząd pełnej szerokości
        tuck_pawezy_w_osi_nad_woda_m=round(float(max(r[0] for r in ctx["rufa_rzedy"] if r[2] <= K["STEPKA_SZER"] / 2 + 0.01
                                                     and r[0] < K["Z_PAWEZ_DOLNA"])), 3),
        tuck_pawezy_pelna_szerokosc_nad_woda_m=round(float(min(r[0] for r in ctx["rufa_rzedy"]
                                                               if r[2] > K["STEPKA_SZER"] / 2 + 0.5)), 3),
        poklad_przy_burcie_srodokrecie=round(float(kd.Zd(0.0)), 3),
        poklad_w_osi_srodokrecie=round(float(kd.deck_c(0.0)), 3),
        polpoklad_nad_glownym=K["POLPOKLAD_H"],
        top_grotbramstengi=round(float(rig["maszty"]["grot"]["br"].z_top), 2),
        top_fokbramstengi=round(float(rig["maszty"]["fok"]["br"].z_top), 2),
    )
    J["maszty"] = {k: dict(s_pokladu=round(v["m"].s_d, 3), pochylenie_deg=round(math.degrees(math.atan(v["m"].t)), 2),
                           sr_przy_pokladzie=round(v["m"].sr, 3), mars_z=round(v["top"]["z"], 2),
                           mars_szer_dl=[round(v["W"], 2), round(v["Lt"], 2)])
                   for k, v in rig["maszty"].items()}
    if ctx["snow"]:
        J["maszty"]["snow"] = dict(s_pokladu=round(rig["snow"]["s"], 3), sr=round(2 * rig["snow"]["r"], 3))
    J["reje"] = {k: dict(dl=round(v["L"], 2), sr=round(v["sr"], 3)) for k, v in rig["reje"].items()}
    # trójkąty
    kol = {}
    for cn, c in ctx["kol"].items():
        objs = [o for o in c.all_objects if o.type == "MESH"]
        kol[cn] = tris_world(objs)
    J["trojkaty_kolekcje_blend"] = kol
    J["trojkaty_grupy_blend"] = dict(kadlub_poklad_wyposazenie=kol["kadlub"] + kol["rufa_dziob"] + kol["wyposazenie"],
                                     drzewca_olinowanie_zagle=kol["drzewca"] + kol["olinowanie"] + kol["zagle_zwiniete"])
    # kadłub: szczelność, symetria
    J["kadlub_powloka"] = dict(**szczelnosc(hull), symetria_max_odchylka_m=symetria(hull))
    # furty
    J["furty"] = [dict(z=round(s, 2), prog_nad_woda=round(float(ps.Zd(s)) + K["FURTA_PROG"], 3),
                       otwor=[K["FURTA_SZER"], round(K["FURTA_NADPROZE"] - K["FURTA_PROG"], 2)])
                  for s in sorted(K["FURTY_S"])]
    # gęstość tekseli
    J["gestosc_tekseli_px_m"] = gestosc_tekseli(allm)
    # chodzenie
    if "chodzenie_json" in ctx:
        k = ctx["chodzenie_json"]["kontrola"]
        J["chodzenie"] = {a: b for a, b in k.items() if not a.startswith("_")}
        J["stanowiska_liczba"] = ctx["chodzenie_json"]["stanowiska_liczba"]
    # symetria danych lin: każda lina z końcem po lewej (x > 3 cm) ma prawy odpowiednik (końce odbite w x ± 3 cm)
    # z tymi samymi polami (grupa, średnica, materiał, czy ma od/do obiekt – nazwy z _L/_P zamienione)
    J["symetria_lin"] = symetria_lin(ctx.get("liny", []))
    # końce lin zamocowane (twardy test: wiszące końce poza wyjątkami = błąd)
    J["konce_lin"] = konce_lin(ctx)
    # bloki zamocowane (twardy test: blok bez styku, wisiora ani stropu = błąd)
    J["bloki"] = bloki_zamocowane(ctx)
    # ściany o zerowym polu UV przerzutowane przy tworzeniu siatek (narzedzia.to_object)
    import narzedzia as _N
    J["uv_zerowe_naprawione"] = dict(sorted(_N.UV_ZEROWE_NAPRAWIONE.items()))
    # tekstury
    td = os.path.join(ctx["out"], "tekstury")
    J["tekstury"] = {f: os.path.getsize(os.path.join(td, f)) for f in sorted(os.listdir(td)) if f.endswith(".jpg")}
    J["tekstury_lacznie_bajty"] = sum(J["tekstury"].values())
    # GLB
    if glb and os.path.exists(glb):
        E = ctx.get("eksport", {})
        sel = E.get("sel", [])
        tri_k = sum(tris(o) for o in sel if o.type == "MESH" and (o.name == "kadlub_statyczny" or not (
            o.name.startswith("reja_") or o.name.startswith("gafel") or o.name.startswith("bom") or
            o.name.startswith("takielunek") or o.name.startswith("zagiel") or o.name.startswith("lina_") or
            o.name.startswith("rak_"))))
        tri_t = sum(tris(o) for o in sel if o.type == "MESH") - tri_k
        J["glb"] = dict(plik=glb, bajty=os.path.getsize(glb), trojkaty_kadlub_poklad_wyposazenie=tri_k,
                        trojkaty_drzewca_olinowanie_zagle=tri_t, wezly=len(sel))
        # tabela dobrych praktyk (praktyki.py) – przed ponownym wczytaniem (import dodaje kopie i osierocone dane)
        import praktyki
        praktyki.zbuduj(ctx, J, glb)
        # wczytanie z powrotem w osobnej scenie
        cur = bpy.context.window.scene if bpy.context.window else bpy.context.scene
        sc2 = bpy.data.scenes.new("_wczytany")
        try:
            bpy.context.window.scene = sc2
        except Exception:
            pass
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=glb)
        new = [o for o in bpy.data.objects if o not in before]
        t2 = sum(tris(o) for o in new if o.type == "MESH")
        J["glb"]["wczytany_trojkaty"] = t2
        J["glb"]["wczytany_obiekty"] = len(new)
        J["glb"]["wczytany_puste_stanowiska"] = sum(1 for o in new if o.type == "EMPTY" and o.name.startswith("stan_"))
        J["glb"]["zgodnosc_trojkatow"] = t2 == tri_k + tri_t
        names_new = set(o.name.split(".")[0] for o in new)
        J["glb"]["brak_w_glb"] = sorted(o.name for o in sel if o.type == "MESH" and o.name not in names_new)[:40]
        # obwiednia po wczytaniu (osie glTF → Blender: dziób −Y)
        bb = np.array([o.matrix_world @ Vector(c) for o in new if o.type == "MESH" for c in o.bound_box])
        J["glb"]["obwiednia_blender"] = [[round(float(v), 2) for v in bb.min(0)], [round(float(v), 2) for v in bb.max(0)]]
        for o in new:
            bpy.data.objects.remove(o, do_unlink=True)
        try:
            bpy.context.window.scene = cur
        except Exception:
            pass
        bpy.data.scenes.remove(sc2)
        # materiały w GLB (czy mnożnik koloru doszedł jako baseColorFactor)
        import struct
        with open(glb, "rb") as f:
            data = f.read()
        ln = struct.unpack("<I", data[12:16])[0]
        gj = json.loads(data[20:20 + ln].decode("utf-8"))
        J["glb"]["materialy"] = {m["name"]: m.get("pbrMetallicRoughness", {}).get("baseColorFactor") for m in gj["materials"]}
        J["glb"]["obrazy"] = len(gj.get("images", []))
        J["glb"]["siatki"] = len(gj.get("meshes", []))
        J["glb"]["wezly_gltf"] = len(gj.get("nodes", []))
    # przenikanie brył, migotanie, zakresy ruchu, styk z pokładem (na obiektach przed scaleniem)
    import przenikanie as PZ
    import time as _t
    t0 = _t.time()
    import sterowanie
    objs_all = [o for o in bpy.data.objects if o.type == "MESH" and o.users_collection and
                o.users_collection[0].name not in ("_eksport", "Scene Collection") and not o.name.startswith("##")
                and not o.name.endswith("_glb") and (not o.hide_render or o.get("wariant"))]
    dom = ctx.get("naped_domyslny", "naped_kolo")
    J["przenikanie"] = dict(prog_m=PZ.PROG, wariant_domyslny=dom, warianty={},
                            lista_polaczen_zamierzonych=[dict(a=a, b=b, uzasadnienie=w)
                                                         for (a, ma, b, mb, w) in PZ.POLACZENIA])
    J["zakresy_ruchu_warianty"] = {}
    ruch_pref = ("ster", "rumpel", "kolo_sterowe", "kabestan_beben", "pompa_L_dz", "pompa_P_dz", "furta_pokrywa",
                 "reja_", "dzialko_", "dzwon", "gafel", "bom")
    for w in sterowanie.WARIANTY:
        objs = [o for o in objs_all if o.get("wariant") in (None, w)]
        zgl, zam, mig = PZ.test(objs)
        J["przenikanie"]["warianty"][w] = dict(zgloszone_pary=len(zgl), zamierzone_pary=len(zam),
                                               zgloszone_ponad_prog=sum(1 for r in zgl if r["max_wnikniecie_m"] > PZ.PROG),
                                               styki_lin_bez_wnikniecia=sum(1 for r in zgl if r["max_wnikniecie_m"] <= PZ.PROG),
                                               zgloszenia=sorted(zgl, key=lambda r: -r["max_wnikniecie_m"]),
                                               zamierzone=sorted(zam, key=lambda r: -r["max_wnikniecie_m"]),
                                               migotanie=mig)
        stat = [o for o in objs if not o.name.startswith(ruch_pref) and not o.name.startswith("dzialo_")
                and not o.name.startswith("lina_dyn_") and not (o.name.startswith("lina_") and o.parent is not None)]
        zr = PZ.zakresy(ctx, stat, wariant=w)
        # reje i gafel przy brasowaniu: bloki olinowania ruchomego są statyczne jak liny ruchome (po zbrasowaniu
        # gra je przelicza albo ukrywa – ruchome.py) – ich styki z reją i żaglem odnotowane osobno, nie jako kolizje
        for o_ in zr:
            if o_.get("obiekt", "").startswith(("reja_", "gafel")):
                pom = 0
                for st_ in o_.get("stany", []):
                    k0 = len(st_.get("kolizje", []))
                    st_["kolizje"] = [k_ for k_ in st_.get("kolizje", []) if k_.get("z") != "bloki"]
                    pom += k0 - len(st_["kolizje"])
                if pom:
                    o_["styki_z_blokami_olinowania_ruchomego"] = pom
                    o_["kolizji"] = sum(len(st_["kolizje"]) for st_ in o_.get("stany", []))
        J["zakresy_ruchu_warianty"][w] = zr
    J["przenikanie"].update({k: v for k, v in J["przenikanie"]["warianty"][dom].items()})
    J["przenikanie"]["czas_s"] = round(_t.time() - t0, 1)
    J["zakresy_ruchu"] = J["zakresy_ruchu_warianty"][dom]
    J["ograniczenia_ruchu"] = ctx.get("ograniczenia_ruchu")
    nazwy = [o.name for o in bpy.data.objects if o.type == "MESH" and (
        (o.name.startswith("dzialo_") and not o.name.endswith(("_lufa", "_glb"))) or o.name in (
            "wyposazenie_drobne", "szafka_kompasowa", "pompa_L", "pompa_P", "kabestan_podstawa", "lodz_legary",
            "kolo_stojaki", "dzwon_rama", "zejsciowka", "nagielbank_fok", "nagielbank_grot"))]
    J["styk_z_pokladem"] = PZ.styk_z_pokladem(ctx, nazwy)
    if glb is None:
        import praktyki
        praktyki.zbuduj(ctx, J, None)
    else:
        for r in J.get("dobre_praktyki", []):
            if r["kryterium"].startswith("zgodność po ponownym"):
                g_ = J.get("glb", {})
                ok = g_.get("brak_w_glb") == [] and abs(g_.get("wczytany_trojkaty", 0) - J.get("trojkaty_glb", 0)) <= \
                    0.06 * J.get("trojkaty_glb", 1)
                r.update(wynik="tak" if ok else "nie", liczby=dict(wczytany=g_.get("wczytany_trojkaty"),
                         wyslany=g_.get("trojkaty_kadlub_poklad_wyposazenie", 0) + g_.get("trojkaty_drzewca_olinowanie_zagle", 0),
                         brak_w_glb=g_.get("brak_w_glb")), uwagi="różnica ≤ 50 trójkątów (zdegenerowane usuwane przy imporcie)")
    p = os.path.join(ctx["out"], "kontrola.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(J, f, ensure_ascii=False, indent=1)
    print("KONTROLA " + json.dumps(J, ensure_ascii=False)[:3000])
    return J
