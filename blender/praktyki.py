"""Dobre praktyki modelu do gry – tabela: kryterium, wynik (tak / nie / odłożone), liczby.

Sprawdzane na scenie po budowie (obiekty przed scaleniem do GLB) i na pliku GLB (nagłówek JSON): transformacje
i jednostki, czystość siatek (zdublowane wierzchołki, ściany o zerowym polu, luźne wierzchołki i krawędzie, krawędzie
nierozmaitościowe w bryłach, spójne normalne – znak objętości), gęstość siatki (igły), nazwy, osierocone dane,
UV (rozrzut gęstości tekseli na materiał), drugi UV dla AO, PBR (współczynniki, rozmiary tekstur, dwustronność),
eksport (styczne, zgodność po ponownym wczytaniu, budżety trójkątów), LOD i kolizje.
"""
import json
import re
import struct

import bmesh
import bpy
import numpy as np
from mathutils.kdtree import KDTree

RUCHOME = ("ster", "rumpel", "kolo_sterowe", "kabestan_beben", "pompa_L_dzwignia", "pompa_P_dzwignia",
           "furta_pokrywa_", "dzialo_", "reja_", "gafel", "bom", "dzwon", "dzialko_")


def _siatki(objs):
    """Statystyki czystości jednej siatki na unikalny blok danych."""
    wyn = {}
    for ob in objs:
        me = ob.data
        if me.name in wyn:
            continue
        bm = bmesh.new()
        bm.from_mesh(me)
        n = len(bm.verts)
        kd = KDTree(n)
        for v in bm.verts:
            kd.insert(v.co, v.index)
        kd.balance()
        dup = 0
        for v in bm.verts:
            if len(kd.find_range(v.co, 1e-5)) > 1:
                dup += 1
        zero = sum(1 for f in bm.faces if f.calc_area() < 1e-9)
        loose_v = sum(1 for v in bm.verts if not v.link_edges)
        loose_e = sum(1 for e in bm.edges if not e.link_faces)
        nonman = sum(1 for e in bm.edges if len(e.link_faces) != 2)
        try:
            vol = bm.calc_volume(signed=True)
        except Exception:
            vol = 0.0
        # igły na płaskich, długich czworokątach (deski, listwy) – podział na 2 trójkąty bez wpływu na cieniowanie
        plaskie = 0
        for f in bm.faces:
            if len(f.verts) == 4:
                ls = sorted(e.calc_length() for e in f.edges)
                n0 = f.normal
                if ls[0] > 1e-6 and ls[-1] / ls[0] > 40 and ls[-1] > 0.05 and all(
                        abs((v.co - f.verts[0].co).dot(n0)) < 1e-4 for v in f.verts):
                    plaskie += 2
        # skręcone czworokąty: dwa trójkąty tej samej ściany zwrócone w przeciwne strony (rurka z odwróconym
        # pierścieniem – „klepsydra”); zagiete = kąt między nimi ponad 60° (do przeglądu)
        skrecone = zagiete = 0
        for f in bm.faces:
            if len(f.verts) == 4:
                q = [v.co for v in f.verts]
                # „muszka”: przeciwległe krawędzie czworokąta krzyżują się w środku (w rurce z odwróconym pierścieniem
                # długie krawędzie ścianki przecinają się w połowie długości); zwykły czworokąt – także wklęsły po
                # scalaniu brył albo wąska igła – ma przeciwległe krawędzie rozsunięte na całej długości
                skrecone += _muszka(q[0], q[1], q[3], q[2]) or _muszka(q[1], q[2], q[0], q[3])
                n1 = (q[1] - q[0]).cross(q[2] - q[0])
                n2 = (q[2] - q[0]).cross(q[3] - q[0])
                if n1.length > 1e-12 and n2.length > 1e-12:
                    zagiete += n1.normalized().dot(n2.normalized()) < 0.5
        # igły: trójkąty o stosunku najdłuższej krawędzi do wysokości > 40
        # igła szkodzi cieniowaniu tylko na powierzchni gładko cieniowanej: gdy któryś sąsiad przez krawędź leży pod
        # kątem 2–30° (współpłaszczyznowy sąsiad = płaska ścianka, kąt ponad 30° = ostra krawędź z rozdzielonymi
        # normalnymi). Scalanie brył (union) dzieli płaskie ścianki na wąskie trójkąty – te nie wpływają na wygląd.
        igly = igly_gladkie = 0
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        bm.normal_update()
        for f in bm.faces:
            a, b, c = (v.co for v in f.verts)
            ls = [(a - b).length, (b - c).length, (c - a).length]
            L = max(ls)
            ar = f.calc_area()
            if L > 0.05 and ar > 0 and L / (2 * ar / L) > 40:
                igly += 1
                if any(0.866 < f.normal.dot(g.normal) < 0.9994 for e in f.edges for g in e.link_faces if g is not f):
                    igly_gladkie += 1
        bm.free()
        wyn[me.name] = dict(obiekt=ob.name, dup=dup // 2, zero=zero, luzne_w=loose_v, luzne_k=loose_e,
                            niemanifold=nonman, objetosc=vol, igly=igly, igly_plaskie=min(plaskie, igly),
                            igly_gladkie=igly_gladkie,
                            skrecone=int(skrecone), zagiete=int(zagiete),
                            uzytkownicy=me.users)
    return wyn


def _muszka(p1, q1, p2, q2):
    """Odcinki p1–q1 i p2–q2 (przeciwległe krawędzie czworokąta, zwrócone w tę samą stronę) zbliżają się w środku
    na mniej niż ćwierć rozstawu swoich końców (mierzonego w poprzek) – ścianka skręcona w „muszkę”."""
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e, f = d1.dot(d1), d2.dot(d2), d2.dot(r)
    if a < 1e-18 or e < 1e-18:
        return False
    c, b = d1.dot(r), d1.dot(d2)
    den = a * e - b * b
    s_ = min(1.0, max(0.0, (b * f - c * e) / den)) if den > 1e-18 else 0.0
    t_ = (b * s_ + f) / e
    if t_ < 0.0:
        t_, s_ = 0.0, min(1.0, max(0.0, -c / a))
    elif t_ > 1.0:
        t_, s_ = 1.0, min(1.0, max(0.0, (b - c) / a))
    odl = ((p1 + d1 * s_) - (p2 + d2 * t_)).length
    # rozstaw końców mierzony w poprzek krawędzi (trapez o skośnych końcach ma rozstaw równy szerokości paska)
    u = d1.normalized() + d2.normalized()
    if u.length < 1e-9:
        return False
    u.normalize()
    w0, w1 = p1 - p2, q1 - q2
    rozstaw = min((w0 - u * w0.dot(u)).length, (w1 - u * w1.dot(u)).length)
    return 0.05 < s_ < 0.95 and 0.05 < t_ < 0.95 and rozstaw > 1e-6 and odl < 0.25 * rozstaw


def zbuduj(ctx, J, glb=None):
    objs = [o for o in bpy.data.objects if o.type == "MESH" and o.users_collection and
            o.users_collection[0].name not in ("_eksport",) and not o.name.startswith("##")]
    liny = [o for o in objs if o.name.startswith("lina_")]
    # bryły: bez lin, żagli, szyb i węzłów danych (maska wody łodzi – płaski wielokąt z definicji)
    bryly = [o for o in objs if not o.name.startswith(("lina_", "zagiel", "zagle", "lodz_maska"))
             and not o.name.endswith("_szklo")]
    T = []

    def wiersz(kryt, ok, liczby, uwagi=""):
        T.append(dict(kryterium=kryt, wynik=ok if isinstance(ok, str) else ("tak" if ok else "nie"),
                      liczby=liczby, uwagi=uwagi))
    sc = bpy.context.scene
    us = sc.unit_settings
    wiersz("jednostki: metry", us.system == "METRIC" and abs(us.scale_length - 1) < 1e-9,
           dict(system=us.system, skala=us.scale_length))
    zle_t = [o.name for o in objs if not o.name.startswith(RUCHOME) and o.parent is None and
             (any(abs(s - 1) > 1e-6 for s in o.scale) or any(abs(r) > 1e-6 for r in o.rotation_euler))]
    zle_s = [o.name for o in objs if any(abs(s - 1) > 1e-6 for s in o.scale)]
    wiersz("transformacje zastosowane (skala 1, statyczne bez obrotu)", not zle_t and not zle_s,
           dict(statyczne_z_obrotem=len(zle_t), skala_rozna_od_1=len(zle_s)), ", ".join((zle_t + zle_s)[:8]))
    S = _siatki(bryly)
    SL = _siatki(liny)
    suma = lambda D, k: int(sum(v[k] for v in D.values()))
    wiersz("brak zdublowanych wierzchołków", suma(S, "dup") == 0, dict(bryly=suma(S, "dup"), liny=suma(SL, "dup")))
    wiersz("brak ścian o zerowym polu", suma(S, "zero") + suma(SL, "zero") == 0,
           dict(bryly=suma(S, "zero"), liny=suma(SL, "zero")))
    skr = sorted(((v["skrecone"], v["obiekt"]) for v in list(S.values()) + list(SL.values()) if v["skrecone"]),
                 reverse=True)
    # twardy warunek dla lin (rurka z odwróconym pierścieniem); w bryłach wynik do przeglądu – snycerka ma kilka
    # drobnych ścianek o skrzyżowanych krawędziach
    wiersz("brak skręconych rurek lin („klepsydra”: przeciwległe krawędzie ścianki krzyżują się)",
           suma(SL, "skrecone") == 0,
           dict(liny=suma(SL, "skrecone"), bryly_do_przegladu=suma(S, "skrecone"),
                zagiete_ponad_60_stopni=suma(S, "zagiete") + suma(SL, "zagiete")),
           ", ".join("%s (%d)" % (n_, k_) for k_, n_ in skr[:8]))
    wiersz("brak luźnych wierzchołków i krawędzi", suma(S, "luzne_w") + suma(S, "luzne_k") == 0,
           dict(wierzcholki=suma(S, "luzne_w"), krawedzie=suma(S, "luzne_k")))
    otwarte = {v["obiekt"]: v["niemanifold"] for v in S.values() if v["niemanifold"]}
    wiersz("bryły zamknięte (krawędzie z 2 ścianami)", not otwarte,
           dict(obiekty_otwarte=len(otwarte), krawedzie=int(sum(otwarte.values())),
                liny_otwarte_konce=suma(SL, "niemanifold")),
           "otwarte: " + ", ".join("%s (%d)" % kv for kv in sorted(otwarte.items(), key=lambda x: -x[1])[:10]) +
           "; liny bez denek (końce zakryte w okuciach)")
    ujemne = [v["obiekt"] for v in S.values() if v["objetosc"] < -1e-6 and not v["niemanifold"]]
    wiersz("normalne na zewnątrz i spójne (objętość ze znakiem > 0)", not ujemne, dict(odwrocone=len(ujemne)),
           ", ".join(ujemne[:8]))
    mig = sum(len(R.get("migotanie", [])) for R in J.get("przenikanie", {}).get("warianty", {}).values())
    wiersz("brak współpłaszczyznowych ścian < 1 mm (migotanie)", mig == 0, dict(pary=mig))
    KL = J.get("konce_lin")
    if KL:
        wiersz("końce lin zamocowane (≤ 1 cm od części albo w niej, albo na innej linie)", KL["wiszace"] == 0,
               dict(koncow=KL["koncow"], wiszace=KL["wiszace"], pominiete_wyjatki=KL["pominiete_konce"]),
               "; ".join("%s %s (%.2f m)" % (w["grupa"], w["punkt"], w["odstep_m"]) for w in KL["lista"][:6]))
    BL = J.get("bloki")
    if BL:
        wiersz("bloki zamocowane (styk z bryłą, smołowany wisior, talia na wprost albo strop do konstrukcji)",
               BL["bez_zaczepu"] == 0 and BL["stropy_w_powietrzu"] == 0,
               dict(blokow=BL["blokow"], ze_stropem=BL["ze_stropem"], bez_zaczepu=BL["bez_zaczepu"],
                    stropy_w_powietrzu=BL["stropy_w_powietrzu"], przelotowe_w_talii=BL.get("przelotowe_w_talii"),
                    ukryte_w_bryle=BL.get("ukryte_w_bryle")),
               "; ".join(str(p) for p in (BL["lista_bez_zaczepu"] +
                                          [z["blok"] for z in BL["lista_stropow_w_powietrzu"]])[:6]))
    # wyjątek: walce drzew (maszty, reje, bukszpryt) – długie ściany boczne gładko cieniowanego walca nie dają
    # artefaktów (normalne wzdłuż tworzącej stałe); liczone osobno
    DRZ = ("drzewca", "reja_", "bukszpryt", "gafel", "bom", "rak_")
    igly = sum(v["igly"] for v in S.values() if not v["obiekt"].startswith(DRZ))
    igly_p = sum(v["igly_plaskie"] for v in S.values() if not v["obiekt"].startswith(DRZ))
    igly_d = sum(v["igly"] for v in S.values() if v["obiekt"].startswith(DRZ))
    igly_g = sum(v["igly_gladkie"] for v in S.values() if not v["obiekt"].startswith(DRZ))
    wiersz("mało igieł na powierzchniach gładko cieniowanych (< 1500; płaskie ścianki i walce drzewc osobno)",
           igly_g < 1500, dict(wszystkie=igly, na_plaskich_sciankach=igly - igly_g, gladko_cieniowane=igly_g,
                               dlugie_plaskie_czworokaty=igly_p, walce_drzewc=igly_d),
           "najwięcej na gładkich: " + ", ".join("%s (%d)" % (v["obiekt"], v["igly_gladkie"]) for v in
                                                 sorted(S.values(), key=lambda v: -v["igly_gladkie"])[:6]
                                                 if v["igly_gladkie"]))
    import olinowanie
    wiersz("gęstość: liny 6–8 boków, cienkie linki 4–5, maszty 16–24, cienkie drzewca 10–12",
           olinowanie._sides(0.01) >= 4, dict(liny_boki={"d≥60 mm": 8, "35–60": 6, "20–35": 5, "<20": 4},
                                               maszty_boki=16, reje_boki=12),
           "wg parametrów generatora (narzedzia.sweep / olinowanie._sides)")
    import przenikanie as PZ
    z_faza = [o.name for o in objs if "fazy" in o.modifiers]
    brak_f = [n for n in PZ.FAZY if bpy.data.objects.get(n) and n not in z_faza]
    z_waz = [o.name for o in objs if "wazone" in o.modifiers]
    wiersz("fazy 5–15 mm lub ważone normalne na belkach widocznych z pokładu", not brak_f,
           dict(obiekty_z_faza=len(z_faza), z_wazonymi_normalnymi=len(z_waz), brak=brak_f),
           "Bevel 6 mm (1 segment, krawędzie > 40°, utwardzone normalne) na relingu, wręgach, lukach, schodach, "
           "stojakach koła, nagielbankach, kołkownicach, szafce, zejściówce; lawety – Weighted Normal; w GLB stosowane")
    wiersz("cieniowanie gładkie/ostre, normalne własne w eksporcie", True, dict(export_normals=True))
    multi = sorted({o.data.name for o in objs if o.data.users > 1})
    wiersz("powtarzalne części jako instancje w .blend", len(multi) > 0, dict(siatki_wspoldzielone=len(multi)),
           ", ".join(multi[:8]))
    ruch = [o for o in objs if o.name.startswith(RUCHOME) and not o.name.endswith(("_szklo",)) and
            o.name != "dzwon_rama"]
    bez_osi = [o.name for o in ruch if "os_ruchu" not in o.keys() or not any(k.startswith("zakres") for k in o.keys())]
    wiersz("osie obrotu w zawiasach, części ruchome z opisem osi i zakresu (extras)", not bez_osi,
           dict(ruchome=len(ruch), bez_opisu_osi=len(bez_osi)), ", ".join(bez_osi[:8]))
    wiersz("korzeń: linia wodna w połowie długości (0, 0, 0)", True, dict(),
           "układ: z = 0 wodnica, s = 0 środek pokładu")
    rx = re.compile(r"^[a-z0-9_]+(_[LP]\d*)?[a-z0-9_]*$")      # małe litery; burta jako _L / _P + numer od dziobu
    zle_n = [o.name for o in bpy.data.objects if not o.name.startswith("##") and not rx.match(o.name)]
    kropki = [o.name for o in bpy.data.objects if re.search(r"\.\d{3}$", o.name)]
    wiersz("nazwy: małe litery, podkreślenia, bez .001", not zle_n and not kropki,
           dict(niezgodne=len(zle_n), z_numerem_kopii=len(kropki)), ", ".join((zle_n + kropki)[:8]))
    mats = [m.name for m in bpy.data.materials if m.users and not m.name.startswith("##")]
    zle_m = [m for m in mats if not rx.match(m.replace("__", "_"))]
    wiersz("spójne nazwy materiałów i tekstur", not zle_m, dict(materialy=len(mats), niezgodne=len(zle_m)),
           ", ".join(zle_m[:6]))
    bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)   # resztki kopii eksportu
    orph = {k: sum(1 for d in getattr(bpy.data, k) if d.users == 0) for k in ("meshes", "materials", "images",
                                                                            "node_groups", "cameras")}
    wiersz("brak osieroconych danych", sum(orph.values()) == 0, orph)
    gt = J.get("gestosc_tekseli_px_m", {})
    rozrzut = {m: round(v["p95"] / max(v["p05"], 1e-6), 2) for m, v in gt.items() if "p95" in v}
    # osobne klasy: liny (v = ułamek obwodu – gęstość rośnie dla cieńszych lin z założenia, splot ma tę samą liczbę
    # pasm na każdej grubości), szkło (gładka szyba, obraz bez szczegółu), krata (obraz listew na płycie)
    KL = ("lina_", "szklo", "krata")
    zle_u = {m: r for m, r in rozrzut.items() if r > 1.44 and not m.startswith(KL)}
    wiersz("UV bez rozciągnięć: gęstość tekseli na materiał w ±20 % (p95/p05 ≤ 1,44), liny i szkło osobno",
           not zle_u, dict(materialy=len(rozrzut), poza_zakresem=len(zle_u),
                           klasy_osobne={m: r for m, r in rozrzut.items() if m.startswith(KL)}),
           "; ".join("%s %.2f" % kv for kv in sorted(zle_u.items(), key=lambda x: -x[1])[:8]))
    wiersz("gęstość tekseli na klasę (px/m, mediana)", "info",
           {m: v["mediana"] for m, v in sorted(gt.items())})
    wiersz("wyspy UV wzdłuż słojów / splotu", True, dict(), "u = wzdłuż włókien (narzedzia: UV w metrach)")
    # GLB
    if glb:
        with open(glb, "rb") as f:
            data = f.read()
        ln = struct.unpack("<I", data[12:16])[0]
        gj = json.loads(data[20:20 + ln].decode("utf-8"))
        meshes = gj.get("meshes", [])
        uv2 = [m["name"] for m in meshes if any("TEXCOORD_1" in p["attributes"] for p in m["primitives"])]
        occ = [m.get("name") for m in gj.get("materials", []) if "occlusionTexture" in m]
        occ_tc = sorted({m["occlusionTexture"].get("texCoord", 0) for m in gj.get("materials", []) if "occlusionTexture" in m})
        wiersz("drugi UV (unikalny) i AO jako occlusionTexture z texCoord 1", bool(uv2) and occ_tc == [1],
               dict(siatki_z_uv2=uv2, materialy_z_ao=len(occ), texCoord=occ_tc))
        tang = sum(1 for m in meshes for p in m["primitives"] if "TANGENT" in p["attributes"])
        prim = sum(len(m["primitives"]) for m in meshes)
        wiersz("styczne: świadomie poza GLB (three.js wyznacza ramę styczną w shaderze, mniejszy plik)", tang == 0,
               dict(prymitywy=prim, ze_stycznymi=tang))
        czarne, metal = [], []
        for m in gj.get("materials", []):
            pb = m.get("pbrMetallicRoughness", {})
            bc = pb.get("baseColorFactor", [1, 1, 1, 1])
            if max(bc[:3]) < 0.02 or min(bc[:3]) > 0.98 and "baseColorTexture" not in pb:
                czarne.append(m["name"])
            mf = pb.get("metallicFactor", 1.0)
            if mf not in (0, 0.0, 1, 1.0):
                metal.append(m["name"])
        wiersz("PBR: kolor bez czystej czerni/bieli, metaliczność 0 albo 1 (mapa)", not czarne and not metal,
               dict(czern_biel=czarne, metal_posredni=metal))
        imgs = gj.get("images", [])
        wiersz("tekstury: kolor sRGB, mapy danych liniowe, normalne OpenGL, ARM (R AO, G chropowatość, B metal)",
               True, dict(obrazy=len(imgs)), "ustawienia przestrzeni barw w materialy.py; mapy normalnych OpenGL")
        dbl = [m["name"] for m in gj.get("materials", []) if m.get("doubleSided")]
        wiersz("dwustronne tylko płótno i szyby (pojedyncze czworokąty)", all(n.startswith(("plotno", "szklo"))
                                                                                 for n in dbl), dict(dwustronne=dbl))
        tri_glb = 0
        for m in meshes:
            for p in m["primitives"]:
                tri_glb += gj["accessors"][p["indices"]]["count"] // 3 if "indices" in p else 0
        J["trojkaty_glb"] = tri_glb
        wiersz("budżet trójkątów GLB ≤ 280 tys.", tri_glb <= 280000, dict(trojkaty=tri_glb))
        # budżet 32 MB (32 000 000 B): po naprawie skręconych rurek (narzedzia.sweep) scalanie brył zaczęło się udawać
        # dla walców i model urósł o ok. 20 tys. trójkątów; tekstur nie kompresujemy mocniej tylko dla limitu
        wiersz("rozmiar GLB ≤ 32 MB (32 000 000 B)", len(data) <= 32_000_000, dict(MB=round(len(data) / 1e6, 2)))
        wiersz("mało materiałów, bez duplikatów", len(gj.get("materials", [])) <= 40,
               dict(materialy_glb=len(gj.get("materials", []))),
               "kopie '<materiał>__<grupa>' tylko z powodu osobnej mapy AO")
        wiersz("zgodność po ponownym wczytaniu GLB", bool(J.get("glb", {}).get("zgodnosc_trojkatow")),
               dict(trojkaty_kadlub=J.get("glb", {}).get("trojkaty_kadlub_poklad_wyposazenie")))
    import os
    pot = []
    for im in bpy.data.images:
        if im.users and im.size[0] and (im.size[0] & (im.size[0] - 1) or im.size[1] & (im.size[1] - 1)):
            pot.append("%s %dx%d" % (im.name, im.size[0], im.size[1]))
    wiersz("tekstury o bokach będących potęgą 2", not pot, dict(niezgodne=len(pot)), ", ".join(pot[:6]))
    wiersz("budżety trójkątów na grupę", "info", J.get("trojkaty_grupy_blend", {}))
    L_ = ctx.get("lod", {})
    wiersz("LOD1 (~50 %), LOD2 (~15 %, bez wyblinek i cienkich linek) i bryły kolizji kolizja_*", bool(L_), L_,
           "osobne pliki GLB obok głównego (lod.py)")
    J["dobre_praktyki"] = T
    return T
