"""Model do rysunków i danych publicznych (Blender, bez okna): budowa generatora do etapu żagli w pamięci
(bez scalania brył, eksportu i renderów), zapis liczb z ctx (drzewca, ławy, kołki, rejestr lin z opisem miejsca
wywołania) i rzuty krawędzi siatek z usuwaniem linii zasłoniętych.

Wynik: katalog podręczny (domyślnie build/rysunki_robocze/cache): model.json, rzuty.json.
Wołany z rysunki.py; sam niczego nie rysuje.

Opis lin: generator nie nadaje linom nazw – olinowanie.lina() jest tu owinięte funkcją, która zapisuje przy każdej
linie nazwę funkcji wołającej, wiersz kodu i proste zmienne lokalne (burta, maszt, reja, nazwa kołka). Nazwy
publiczne powstają z tego opisu w dane_publiczne.py (reguły po polsku → angielsku, nazwy_publiczne.py).
"""
import json
import linecache
import math
import os
import sys
try:
    import konsola  # noqa: F401  (wyjście na konsolę w UTF-8 także na Windows)
except ImportError:
    pass
import time

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
ROOT = os.path.abspath(os.path.join(HERE, ".."))     # katalog główny repozytorium

MODULY = ("narzedzia", "narzedzia_math", "parametry", "rzedne", "kadlub", "materialy", "rufa_dziob", "drzewca",
          "olinowanie", "wyposazenie", "zagle", "poklad", "ruchome", "przenikanie", "sterowanie", "praktyki")


# ------------------------------------------------------------------ opis wywołań lina()
def _proste(d):
    out = {}
    for k, v in d.items():
        if k.startswith("_") or k in ("ctx", "self"):
            continue
        if isinstance(v, bool) or isinstance(v, (int, str)) or (isinstance(v, float) and math.isfinite(v)):
            if isinstance(v, str) and len(v) > 60:
                continue
            out[k] = v
    return out


def owin_lina(olinowanie):
    orig = olinowanie.lina

    def lina(ctx, grupa, pts, d, *a, **kw):
        n0 = len(ctx.get("liny", []))
        ramki = []
        f = sys._getframe(1)
        for _ in range(4):
            if f is None or os.path.basename(f.f_code.co_filename) in ("model_rysunkowy.py", "buduj.py"):
                break
            ramki.append(dict(fn=f.f_code.co_name, mod=os.path.basename(f.f_code.co_filename)[:-3],
                              kod=linecache.getline(f.f_code.co_filename, f.f_lineno).strip()[:160],
                              lok=_proste(f.f_locals)))
            f = f.f_back
        orig(ctx, grupa, pts, d, *a, **kw)
        for L in ctx["liny"][n0:]:
            L["_opis"] = ramki
    olinowanie.lina = lina
    return orig


# ------------------------------------------------------------------ budowa
def zbuduj_model(out_model):
    """Etapy buduj.py do żagli (te same parametry i ten sam kod), w pamięci. Zwraca ctx."""
    for m in list(sys.modules):
        if m in MODULY:
            del sys.modules[m]
    import narzedzia as N
    import parametry as PR
    import rzedne
    import materialy
    import olinowanie
    owin_lina(olinowanie)
    statek = PR.STATKI["BRYG"]
    schemat = statek["schemat"]
    texdir = os.path.join(out_model, "tekstury")
    if not os.path.exists(os.path.join(texdir, "poklad_kolor.jpg")):
        import subprocess
        subprocess.run(["python", os.path.join(HERE, "tekstury.py"), texdir], check=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    K = statek["kadlub"]
    kd = rzedne.Kadlub(K, PR.RZEDNE_H, PR.RZEDNE_S, PR.RZEDNE)
    materialy.zbuduj(texdir, schemat, None)
    root = N.kolekcja(statek["nazwa"])
    kol = {k: N.kolekcja(k, root) for k in ("kadlub", "rufa_dziob", "drzewca", "olinowanie", "wyposazenie",
                                            "zagle_zwiniete", "stanowiska")}
    ctx = dict(kd=kd, K=K, PR=PR, statek=statek, kol=kol, obj={}, schemat=schemat, out=out_model, root=root,
               snow=statek.get("snow", False))
    import kadlub
    kadlub.zbuduj(ctx)
    kadlub.os_kadluba(ctx)
    kadlub.ster(ctx)
    ctx["pokl_z"] = float(kd.deck_c(0.0))
    ctx["qd_z"] = float(kd.deck_c(-9.0)) + K["POLPOKLAD_H"]
    for et in ("poklad", "rufa_dziob", "drzewca", "olinowanie", "wyposazenie", "ruchome", "zagle"):
        __import__(et).zbuduj(ctx)
    olinowanie.oznacz_dynamiczne(ctx)
    import sterowanie
    sterowanie.pokaz(ctx, ctx.get("naped_domyslny", "naped_kolo"))
    bpy.context.view_layer.update()
    return ctx


# ------------------------------------------------------------------ zapis liczb z ctx
def _ser(v, depth=0):
    """Wartość z ctx → JSON. Wektory Blendera → układ statku [x, s, z]."""
    import numpy as np
    if depth > 6:
        return None
    if isinstance(v, Vector):
        return [round(v[0], 4), round(-v[1], 4), round(v[2], 4)] if len(v) == 3 else [round(c, 4) for c in v]
    if isinstance(v, bpy.types.ID):
        return v.name
    if isinstance(v, (bool, str)) or v is None:
        return v
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return round(float(v), 5) if math.isfinite(v) else None
    if isinstance(v, np.ndarray):
        return _ser(v.tolist(), depth + 1)
    if isinstance(v, dict):
        return {str(k): _ser(x, depth + 1) for k, x in v.items() if not callable(x)}
    if isinstance(v, (list, tuple)):
        return [_ser(x, depth + 1) for x in v]
    if hasattr(v, "__dict__"):
        return {k: _ser(x, depth + 1) for k, x in v.__dict__.items() if k not in ("D", "m", "kd", "K") and not callable(x)}
    return None


def _maszt_osie(R_):
    m, st, br = R_["m"], R_["st"], R_["br"]
    return dict(s_d=m.s_d, z_d=m.z_d, tan_rake=m.t, z_heel=m.z_heel, z_cap=m.z_cap, z_top=m.z_top, sr=m.sr,
                r_deck=m.r(m.z_d), r_top=m.r(m.z_top),
                st=dict(s_off=st.s_off, z_heel=st.z_heel, z_top=st.z_top, z_head=st.z_head, sr=st.sr),
                br=dict(s_off=br.s_off, z_heel=br.z_heel, z_top=br.z_top, z_head=br.z_head, sr=br.sr))


def obiekty_sceny():
    out = []
    for o in bpy.data.objects:
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box] if o.type == "MESH" else [o.matrix_world.translation]
        xs = [c[0] for c in bb]
        ys = [-c[1] for c in bb]
        zs = [c[2] for c in bb]
        props = {}
        for k in o.keys():
            if k.startswith("_") or k in ("cycles",):
                continue
            try:
                props[k] = _ser(o[k] if not hasattr(o[k], "to_list") else o[k].to_list())
            except Exception:
                pass
        out.append(dict(nazwa=o.name, typ=o.type, rodzic=o.parent.name if o.parent else None,
                        kolekcja=o.users_collection[0].name if o.users_collection else None,
                        polozenie=_ser(o.matrix_world.translation), obrot=[round(r, 5) for r in o.rotation_euler],
                        min=[round(min(xs), 4), round(min(ys), 4), round(min(zs), 4)],
                        max=[round(max(xs), 4), round(max(ys), 4), round(max(zs), 4)],
                        wierzcholki=len(o.data.vertices) if o.type == "MESH" else 0,
                        widoczny=not o.hide_render, wlasciwosci=props,
                        materialy=sorted({s.material.name for s in o.material_slots if s.material}) if o.type == "MESH" else []))
    return out


def _stale_modulow():
    """Stałe liczbowe zapisane w modułach generatora (poza parametry.py): kształt galionu, czopy steru, promienie
    zwiniętych żagli, postać testu chodzenia."""
    out = {}
    for mod, nazwy in (("rufa_dziob", ("GALION",)), ("kadlub", ("STER_KAT", "STER_CZOPY", "TRZON_R")),
                       ("zagle", ("RAD",)), ("chodzenie", ("R_POSTACI", "WZROST", "KROK_SIATKI"))):
        try:
            m = __import__(mod)
        except Exception:
            continue
        for n in nazwy:
            if hasattr(m, n):
                out.setdefault(mod, {})[n] = _ser(getattr(m, n))
    return out


def zapisz_model(ctx, path):
    rig = ctx["rig"]
    import narzedzia as N
    liny = []
    for L in ctx.get("liny", []):
        pts = [N.S(p) for p in L["p"]]
        liny.append(dict(g=L["g"], d=L["d"], m=L["m"], rodzic=L["parent"].name if L["parent"] is not None else None,
                         od=L.get("od"), do=L.get("do"), wariant=L.get("wariant"), jednostronna=L.get("jednostronna"),
                         p=[[round(c, 4) for c in q] for q in pts], opis=L.get("_opis", [])))
    reje = {}
    for k, Y in rig["reje"].items():
        ob = Y.get("obj")
        reje[k] = dict(c=_ser(Vector(Y["c"])), axis_pt=_ser(Vector(Y["axis_pt"])) if "axis_pt" in Y else None,
                       L=Y["L"], sr=Y["sr"], mast=Y.get("mast"), z=Y.get("z"),
                       end=_ser(Vector(Y["end"])) if "end" in Y else None, obiekt=ob.name if ob else None,
                       dz_robocza=float(ob.get("wysokosc_robocza_dz_m", 0.0)) if ob else 0.0)
    maszty = {}
    for k, R_ in rig["maszty"].items():
        maszty[k] = dict(osie=_maszt_osie(R_), top=_ser(R_["top"]), W=R_["W"], Lt=R_["Lt"], Wx=R_["Wx"],
                         st_off=R_["st_off"], br_off=R_["br_off"], cap_T=R_["cap_T"],
                         shrouds={str(s): _ser(v) for s, v in R_.get("shrouds", {}).items()},
                         stave={str(s): _ser(v) for s, v in R_.get("stave", {}).items()})
    bs = rig["bukszpryt"]
    J = dict(
        czas=time.strftime("%Y-%m-%d %H:%M"),
        maszty=maszty, reje=reje, snow=_ser(rig.get("snow")),
        bukszpryt=dict(heel=list(bs["heel"]), end=list(bs["end"]), r0=bs["r0"], L=bs["L"], j0=_ser(bs["j0"]),
                       j1=_ser(bs["j1"]), sc=bs["sc"], path=_ser(bs["path"]), dir3=_ser(bs["dir3"])),
        lawy=_ser(rig.get("lawy")),
        belay=_ser(ctx.get("belay", [])), liny_stanowisk=_ser(ctx.get("liny_stanowisk", [])),
        kolki_nagielbankow=_ser(ctx.get("kolki_nagielbankow")), kolki_kolkownic=_ser(ctx.get("kolki_kolkownic")),
        liny=liny, obiekty=obiekty_sceny(),
        stale=_stale_modulow(),
        inne={k: _ser(ctx.get(k)) for k in ("kabestan_kolo", "kotbelki", "rumpel", "kolo", "schody", "pokrywy",
                                             "wregi_nadburcia_s", "szpigaty_s", "ster_os", "ster_glowica", "ster_otwor",
                                             "tylnica_gora", "galion_figura", "latarnia_baza", "lodz_stan",
                                             "drzwi_kabiny_x", "naped_domyslny", "rufa_rzedy", "dziala",
                                             "przejscia", "pokl_z", "qd_z")},
    )
    with open(path, "w", encoding="utf-8") as f:
        json.dump(J, f, ensure_ascii=False)
    return J


# ------------------------------------------------------------------ rzuty krawędzi siatek
# Widok: kierunek patrzenia d (od widza do obiektu, układ statku), osie rysunku u (w prawo), v (w górę).
WIDOKI_KIER = {
    "bok": ((1, 0, 0), (0, 1, 0), (0, 0, 1)),         # z prawej burty, dziób w prawo (jak na planach)
    "bok_l": ((-1, 0, 0), (0, -1, 0), (0, 0, 1)),     # z lewej burty, dziób w lewo
    "gora": ((0, 0, -1), (0, 1, 0), (1, 0, 0)),       # z góry: dziób w prawo, lewa burta u góry
    "rufa": ((0, 1, 0), (-1, 0, 0), (0, 0, 1)),       # od rufy: prawa burta po prawej stronie rysunku
    "dziob": ((0, -1, 0), (1, 0, 0), (0, 0, 1)),      # od dziobu: lewa burta po prawej
}


def _ship(v):
    return Vector((v[0], -v[1], v[2]))      # wektor statku → Blender (P bez skalarów)


def _bm(o, dg, lokalnie):
    import bmesh
    bm = bmesh.new()
    try:
        bm.from_object(o, dg)
    except ValueError:              # obiekt ukryty (drugi wariant sterowania) – siatka bez modyfikatorów
        bm.from_mesh(o.data)
    if not lokalnie:
        bm.transform(o.matrix_world)
    bm.normal_update()
    return bm


def rzut(obiekty, widok, okludery=None, kat_ostry=35.0, krok=0.01, eps=0.004, klip=None, lokalnie=False):
    """Krawędzie ostre, brzegowe i konturowe siatek 'obiekty' w rzucie prostokątnym; widoczność próbkami
    co 'krok' (m) promieniem ku widzowi przez jedno drzewo BVH wszystkich okluderów (domyślnie te same obiekty).
    klip: (umin, umax, vmin, vmax, wmin, wmax) w układzie widoku (w – ku widzowi).
    lokalnie: współrzędne lokalne obiektu (np. kotwica bez obrotu na kotbelce).
    Zwraca listę odcinków [u0, v0, u1, v1, widoczny] w metrach."""
    d, u, v = (Vector(_ship(a)) for a in WIDOKI_KIER[widok])
    w = -d
    dg = bpy.context.evaluated_depsgraph_get()
    okl = okludery if okludery is not None else obiekty
    V, F = [], []
    for o in okl:
        if o.type != "MESH":
            continue
        bm = _bm(o, dg, lokalnie)
        base = len(V)
        V.extend(vv.co.copy() for vv in bm.verts)
        for f in bm.faces:
            F.append([base + vv.index for vv in f.verts])
        bm.free()
    tree = BVHTree.FromPolygons(V, F, all_triangles=False) if F else None
    out = []
    cos_t = math.cos(math.radians(kat_ostry))
    for o in obiekty:
        if o.type != "MESH":
            continue
        bm = _bm(o, dg, lokalnie)
        for e in bm.edges:
            lf = e.link_faces
            if len(lf) == 2:
                n0, n1 = lf[0].normal, lf[1].normal
                ostra = n0.dot(n1) < cos_t
                kontur = (n0.dot(d) > 0) != (n1.dot(d) > 0)
                if not (ostra or kontur):
                    continue
            elif len(lf) == 0:
                continue
            a, b = e.verts[0].co.copy(), e.verts[1].co.copy()
            if klip is not None:
                ua, va, wa = a.dot(u), a.dot(v), a.dot(w)
                ub, vb, wb = b.dot(u), b.dot(v), b.dot(w)
                c0, c1, c2, c3, c4, c5 = klip
                if max(ua, ub) < c0 or min(ua, ub) > c1 or max(va, vb) < c2 or min(va, vb) > c3 or \
                        max(wa, wb) < c4 or min(wa, wb) > c5:
                    continue
            L = (b - a).length
            if L < 1e-5:
                continue
            n = max(2, int(L / krok) + 1)
            vis = []
            for k in range(n + 1):
                q = a.lerp(b, k / n) + w * eps
                hit = tree.ray_cast(q, w, 1000.0) if tree else (None,)
                vis.append(hit[0] is None)
            k0 = 0
            for k in range(1, n + 1):
                if k == n or vis[k] != vis[k0]:
                    pa, pb = a.lerp(b, k0 / n), a.lerp(b, k / n)
                    out.append([round(pa.dot(u), 4), round(pa.dot(v), 4), round(pb.dot(u), 4), round(pb.dot(v), 4),
                                1 if vis[k0] else 0])
                    k0 = k
        bm.free()
    return _scal_wspolliniowe(out)


def _scal_wspolliniowe(seg):
    """Łączy następujące po sobie odcinki tej samej krawędzi o tej samej widoczności (mniej elementów SVG)."""
    out = []
    for s in seg:
        if out:
            p = out[-1]
            if p[4] == s[4] and abs(p[2] - s[0]) < 1e-6 and abs(p[3] - s[1]) < 1e-6:
                dx0, dy0 = p[2] - p[0], p[3] - p[1]
                dx1, dy1 = s[2] - s[0], s[3] - s[1]
                if abs(dx0 * dy1 - dy0 * dx1) < 1e-9:
                    p[2], p[3] = s[2], s[3]
                    continue
        out.append(list(s))
    return out


def _obiekty(prefiksy, wyklucz=("lina_", "stan_")):
    out = []
    for o in bpy.data.objects:
        if o.type != "MESH" or o.name.startswith(wyklucz):
            continue
        if any(o.name == p or o.name.startswith(p) for p in prefiksy):
            out.append(o)
    return out


def _wszystkie_siatki(wyklucz=("lina_", "stan_", "lodz_maska")):
    return [o for o in bpy.data.objects if o.type == "MESH" and not o.hide_render and not o.name.startswith(wyklucz)]


def _bbox_s(o):
    ss = [-(o.matrix_world @ Vector(c))[1] for c in o.bound_box]
    return min(ss), max(ss)


def rzuty_arkuszy(ctx):
    """Rzuty do arkuszy: nazwa → dict(widok, odcinki, obiekty). Obiekty wybierane po nazwach z generatora."""
    R = {}
    t0 = time.time()

    def dodaj(nazwa, obiekty, widok, **kw):
        if not obiekty:
            R[nazwa] = dict(widok=widok, odcinki=[], obiekty=[])
            return
        t = time.time()
        seg = rzut(obiekty, widok, **kw)
        R[nazwa] = dict(widok=widok, odcinki=seg, obiekty=sorted(o.name for o in obiekty))
        print("RZUT %s: %d obiektów, %d odcinków, %.1f s" % (nazwa, len(obiekty), len(seg), time.time() - t))
    wszystkie = _wszystkie_siatki()
    with open(os.path.join(ctx["_cache"], "obiekty_siatek.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(o.name for o in wszystkie)))
    bez_zagli = [o for o in wszystkie if not o.name.startswith(("zagiel", "zagle"))]
    # rufa od tyłu: wszystko, co sięga za s = −10 (w = −s ≥ 10,5)
    bez_drzewc = [o for o in bez_zagli if not o.name.startswith(("drzewca", "reja_", "rak_", "gafel", "jufersy",
                                                                   "sztagi_okucia", "lodz"))]
    rufa = [o for o in bez_drzewc if _bbox_s(o)[0] < 4.0 and not o.name.startswith(("dzialo_", "furta_"))]
    dodaj("rufa_widok", rufa, "rufa", okludery=rufa, klip=(-7, 7, -4, 6.2, -4.0, 40), krok=0.012)
    # dziób z boku (prawa burta): s > 9
    dziob = [o for o in bez_zagli if _bbox_s(o)[1] > 9.0 and not o.name.startswith(("reja_", "rak_", "drzewca"))]
    dodaj("dziob_bok", dziob, "bok", okludery=dziob, klip=(9.4, 18.6, -4, 6.0, -12, 12), krok=0.012)
    # sprzęt pokładowy: w układzie świata (rzuty z boku, z góry, od rufy) – tylko te obiekty
    for nazwa, pref in (("kabestan", ("kabestan_beben", "kabestan_podstawa")), ("pompa", ("pompa_L",)),
                        ("kolo", ("kolo_sterowe", "kolo_stojaki")), ("dzialo", ("dzialo_L2",)),
                        ("szafka", ("szafka_kompasowa",)), ("rumpel", ("rumpel", "ster_glowica")), ("ster", ("ster",)), ("bloki", ("bloki_kolo", "bloki_rumpel", "okucia_pokladu_rumpel"))):
        ob = _obiekty(pref)
        for widok in ("bok", "gora", "rufa"):
            dodaj("%s_%s" % (nazwa, widok), ob, widok, krok=0.005, eps=0.002)
    print("RZUTY razem %.1f s" % (time.time() - t0))
    return R


def rzut_kotwicy(ctx):
    """Kotwica w układzie lokalnym (scena z budowy w pamięci: w bryg.blend obrót na kotbelce jest już wpisany
    w siatkę)."""
    R = {}
    ob = _obiekty(("kotwica_L",))
    for widok in ("bok", "gora", "rufa"):
        R["kotwica_%s" % widok] = dict(widok=widok, odcinki=rzut(ob, widok, krok=0.006, eps=0.002, lokalnie=True),
                                      obiekty=[o.name for o in ob])
    return R


def rzuty_z_pliku(blend, cache, dodatkowe=None):
    """Rzuty z kopii bryg.blend (stan modelu do rysunków); dodatkowe – rzuty już policzone (kotwica)."""
    bpy.ops.wm.open_mainfile(filepath=blend, load_ui=False)
    R = rzuty_arkuszy(dict(_cache=cache))
    R.update(dodatkowe or {})
    return R


def main():
    """Samodzielnie: blender -b --python model_rysunkowy.py -- --model DIR --cache DIR [--blend PLIK]"""
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opt = lambda k, d: os.path.abspath(a[a.index(k) + 1]) if k in a else d
    out_model = opt("--model", os.path.join(ROOT, "build", "rysunki_robocze", "model"))
    cache = opt("--cache", os.path.join(ROOT, "build", "rysunki_robocze", "cache"))
    blend = opt("--blend", os.path.join(out_model, "bryg.blend"))
    os.makedirs(cache, exist_ok=True)
    t0 = time.time()
    ctx = zbuduj_model(out_model)
    ctx["_cache"] = cache
    print("MODEL %.1f s, lin %d" % (time.time() - t0, len(ctx.get("liny", []))))
    zapisz_model(ctx, os.path.join(cache, "model.json"))
    if "--bez-rzutow" not in a:
        R = rzuty_z_pliku(blend, cache, rzut_kotwicy(ctx))
        with open(os.path.join(cache, "rzuty.json"), "w", encoding="utf-8") as f:
            json.dump(R, f)
    print("MODEL_RYSUNKOWY %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
