"""Generator brygu / snowa (Blender 5.2, bez okna) – punkt wejścia. Uruchamiany z katalogu głównego repozytorium:

    blender -b --factory-startup --python blender/buduj.py -- [--glb] [--statek BRYG] [--schemat a|b]
        [--out build] [--rendery all|lista,ujęć|none] [--bez-blend] [--tekstury-cc0 KATALOG]
        [--etapy kadlub,rufa_dziob,drzewca,olinowanie,wyposazenie,zagle]

Wyniki domyślnie w build/ w katalogu głównym repozytorium.

Kolejno: tekstury (jeśli ich brak – tekstury.py zwykłym Pythonem), materiały, kadłub, rufa i dziób, drzewca,
olinowanie, wyposażenie, żagle; zapis .blend, rendery. Eksport GLB i kontrola – eksport.py i kontrola.py
(wołane z tego pliku na końcu, gdy --glb).
"""
import os
import subprocess
import sys
try:
    import konsola  # noqa: F401  (wyjście na konsolę w UTF-8 także na Windows)
except ImportError:
    pass
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for m in list(sys.modules):
    if m in ("narzedzia", "narzedzia_math", "parametry", "rzedne", "kadlub", "materialy", "rendery", "rufa_dziob",
             "drzewca", "olinowanie", "wyposazenie", "zagle", "eksport", "kontrola", "poklad", "chodzenie",
             "ruchome", "przenikanie", "sterowanie", "praktyki", "lod", "kontrola_glb"):
        del sys.modules[m]

import narzedzia as N  # noqa: E402
import parametry as PR  # noqa: E402
import rzedne  # noqa: E402
import materialy  # noqa: E402
import rendery  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, ".."))     # katalog główny repozytorium (blender/ leży w nim)


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    o = {"--statek": "BRYG", "--schemat": None, "--out": os.path.join(ROOT, "build"),
         "--rendery": "all", "--dzialo-polyhaven": None, "--lodz": None, "--tekstury-cc0": None, "--naped": None, "--etapy": "kadlub,poklad,rufa_dziob,drzewca,olinowanie,wyposazenie,ruchome,zagle,przenikanie,chodzenie", "--snow": None}
    flags = set()
    for i, x in enumerate(a):
        if x in o and i + 1 < len(a):
            o[x] = a[i + 1]
        elif x.startswith("--"):
            flags.add(x)
    o["flags"] = flags
    return o


def main():
    t0 = time.time()
    A = args()
    statek = PR.STATKI[A["--statek"]]
    schemat = A["--schemat"] or statek["schemat"]
    out = os.path.abspath(A["--out"])
    texdir = os.path.join(out, "tekstury")
    if not os.path.exists(os.path.join(texdir, "poklad_kolor.jpg")):
        subprocess.run(["python", os.path.join(HERE, "tekstury.py"), texdir], check=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    K = statek["kadlub"]
    kd = rzedne.Kadlub(K, PR.RZEDNE_H, PR.RZEDNE_S, PR.RZEDNE)
    cc0 = None
    if A["--tekstury-cc0"] and os.path.isdir(A["--tekstury-cc0"]):
        # zestaw fotograficzny CC0: kopie robocze w <out>/tekstury_cc0 (pobranych plików nie zmienia)
        cc0 = os.path.join(out, "tekstury_cc0")
        if not os.path.exists(os.path.join(cc0, "_kafle.json")):
            subprocess.run(["python", os.path.join(HERE, "tekstury_cc0.py"), os.path.abspath(A["--tekstury-cc0"]), cc0],
                           check=True)
        # atlasy desek i materiały elementów z CC0 + układ desek (td_*, tekstury_deski.py)
        if not os.path.exists(os.path.join(cc0, "_td.json")) or "--nowe-tekstury" in A["flags"]:
            subprocess.run(["python", os.path.join(HERE, "tekstury_deski.py"), os.path.abspath(A["--tekstury-cc0"]), cc0],
                           check=True)
    materialy.zbuduj(texdir, schemat, cc0)
    root = N.kolekcja(statek["nazwa"])
    kol = {k: N.kolekcja(k, root) for k in ("kadlub", "rufa_dziob", "drzewca", "olinowanie", "wyposazenie",
                                            "zagle_zwiniete", "stanowiska")}
    ctx = dict(kd=kd, K=K, PR=PR, statek=statek, kol=kol, obj={}, schemat=schemat, out=out, root=root,
               snow=statek.get("snow", False) if A["--snow"] is None else A["--snow"] == "1")
    if A["--dzialo-polyhaven"] and os.path.exists(A["--dzialo-polyhaven"]):
        ctx["dzialo_polyhaven"] = os.path.abspath(A["--dzialo-polyhaven"])   # wariant CC0; bez ścieżki – własne
    if A["--lodz"]:
        ctx["lodz_stan"] = A["--lodz"]                                     # za_rufa | na_pokladzie | brak
    if A["--tekstury-cc0"] and os.path.isdir(A["--tekstury-cc0"]):
        ctx["tekstury_cc0"] = os.path.abspath(A["--tekstury-cc0"])         # zestaw fotograficzny CC0 (Poly Haven)
    if A["--naped"] in ("kolo", "rumpel"):
        PR.UKLAD["STEROWANIE"]["naped"] = A["--naped"]                    # wariant napędu steru widoczny domyślnie
    etapy = A["--etapy"].split(",")
    import kadlub
    # 1. Linie teoretyczne → poszycie: z tabeli rzędnych (rzedne.Kadlub) rzędy i kolumny siatki, berghołty,
    #    pawęż płaska i kontra, nadburcie od środka, pokład główny i rufowy, grodzie – zamknięta powłoka.
    kadlub.zbuduj(ctx)
    # 2. Oś kadłuba: stępka z dziobnicą (bryła wzdłuż wrębu) i tylnica z prostą krawędzią zawiasów steru.
    kadlub.os_kadluba(ctx)
    # 3. Ster na czopach: płetwa wzdłuż osi zawiasów, trzon do pokładu rufowego, okucia.
    kadlub.ster(ctx)
    ctx["pokl_z"] = float(kd.deck_c(0.0))
    ctx["qd_z"] = float(kd.deck_c(-9.0)) + K["POLPOKLAD_H"]
    ETAPY = [
        # 4. Pokład i nadburcia: pokrywa relingu, ściek, wierzchołki wręgów, listwy, szpigaty, pokrywy furt, schody.
        "poklad",
        # 5. Rufa i dziób: okna, listwy i snycerka pawęży, latarnia; kolano galionu ze zwojem, relingi, kotbelki, kluzy.
        "rufa_dziob",
        # 6. Drzewca z reguł Steela: kolumny, marsy, ezelhofty, stengi, bramstengi, maszt snow, bukszpryt, reje, gafel.
        "drzewca",
        # 7. Olinowanie stałe: ławy wantowe z jufersami, wanty z talrepami i wyblinkami, podwantki, sztagi, bukszpryt.
        "olinowanie",
        # 8. Wyposażenie pokładu (przed linami ruchomymi – liny schodzą na jego kołki): działa, kabestan, pompy, luki…
        "wyposazenie",
        # 9. Olinowanie ruchome przy żaglach zwiniętych: topenanty, brasy, gejtawy, szoty, fały, liny gafla.
        "ruchome",
        # 10. Żagle zwinięte na rejach (dzieci rej), żagiel gaflowy, kliwer i sztaksle.
        "zagle",
        # 11a. Ograniczenia ruchu z geometrii: kąt otwarcia pokryw furt, odrzut dział do pierwszej przeszkody.
        "przenikanie",
        # 11. Dane do chodzenia, stanowiska czynności i test ergonomii (bryg_poklad.json, puste obiekty stan_*).
        "chodzenie",
    ]
    for et in ETAPY:
        if et not in etapy:
            continue
        __import__(et).zbuduj(ctx)
    # 11b. Zabrudzenia kadłuba w kolorach wierzchołków: pas przy wodnicy, zacieki pod furtami, szpigatami, puttingami.
    kadlub.zabrudzenia(ctx)
    # 11c. Lufy dział i działek: żelazo gładsze (lekki połysk) niż okucia – osobny materiał 'zelazo_lufa'
    m_l = N.MATERIALY_REJESTR.get("zelazo_lufa")
    if m_l is not None:
        for o in bpy.data.objects:
            if o.type == "MESH" and o.name.endswith("_lufa"):
                for i, m in enumerate(o.data.materials):
                    if m is not None and m.name == "zelazo":
                        o.data.materials[i] = m_l
    # 12. Bryły złożone z prymitywów → jedna czysta bryła na obiekt (bez ścian wewnętrznych i wnikających końców).
    import przenikanie
    # 12a. Porządki siatek przed scaleniem: zdublowane wierzchołki, ściany o zerowym polu, luźne wierzchołki, normalne.
    ctx["porzadki"] = przenikanie.porzadki([o for o in bpy.data.objects if o.type == "MESH"])
    przenikanie.scal_bryly(ctx)
    przenikanie.porzadki([o for o in bpy.data.objects if o.type == "MESH" and not o.name.startswith("lina_")])
    # 13. Rurki lin z rejestru (prawdziwe średnice; do GLB eksport.py tworzy wersję z dolną granicą).
    if "olinowanie" in etapy or ctx.get("liny"):
        import olinowanie
        # 12b. Końce lin dociągnięte do części, na których z założenia się kończą (1–7 cm; gordingi do wałka żagla).
        olinowanie.zamocuj_konce(ctx)
        ctx["obj"]["liny"] = olinowanie.realizuj(ctx)
        # 13a. Zakres brasowania rej: do pierwszego styku z wantami / sztagami (zapis w rei, do extras GLB).
        przenikanie.zakres_rej(ctx)
        przenikanie.porzadki(ctx["obj"]["liny"])
    # 13b. Opis osi i zakresów ruchu (extras), fazy 6 mm na belkach widocznych z pokładu (modyfikatory, w GLB stosowane).
    przenikanie.opisz_ruchome(ctx)
    przenikanie.fazy(ctx)
    # 13c. Obroty obiektów stałych przeniesione do danych siatki (transformacje zastosowane).
    for o in bpy.data.objects:
        if o.type == "MESH" and o.parent is None and not o.get("os_ruchu") and o.data.users == 1 and \
                any(abs(r) > 1e-6 for r in o.rotation_euler) and not o.name.startswith(("reja_", "dzialo", "dzialko")):
            loc = o.location.copy()
            o.data.transform(o.matrix_basis.to_3x3().to_4x4())
            o.rotation_euler = (0, 0, 0)
            o.location = loc
    # 14. Parametry i tabela lin jako dane (JSON) dla innych narzędzi.
    PR.zapisz_json(os.path.join(out, "parametry.json"))
    with open(os.path.join(out, "liny.json"), "w", encoding="utf-8") as f:
        import json as _j
        def lok(nm, p):
            o_ = bpy.data.objects.get(nm) if nm else None
            return [round(v, 4) for v in (o_.matrix_world.inverted() @ p)] if o_ is not None else None
        _j.dump([dict(grupa=L["g"], srednica_m=L["d"], material=L["m"], rodzic=L["parent"].name if L["parent"] else None,
                      dlugosc_m=round(sum((L["p"][i + 1] - L["p"][i]).length for i in range(len(L["p"]) - 1)), 3),
                      od=[round(v, 3) for v in N.S(L["p"][0])], do=[round(v, 3) for v in N.S(L["p"][-1])],
                      od_obiekt=L.get("od"), do_obiekt=L.get("do"), wariant=L.get("wariant"),
                      od_lokalnie=lok(L.get("od"), L["p"][0]), do_lokalnie=lok(L.get("do"), L["p"][-1]),
                      przez=[[round(v, 3) for v in N.S(q)] for q in L["p"][1:-1]])
                 for L in ctx.get("liny", [])], f, ensure_ascii=False)
    # wariant napędu steru widoczny domyślnie (drugi ukryty w .blend i na renderach)
    import sterowanie
    sterowanie.pokaz(ctx, ctx.get("naped_domyslny", "naped_kolo"))
    print("BUDOWA %.1f s" % (time.time() - t0))
    if "--bez-blend" not in A["flags"]:
        os.makedirs(out, exist_ok=True)
        bpy.data.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "bryg.blend"), compress=True)
    glb = None
    if "--glb" in A["flags"]:
        import eksport
        glb = os.path.join(out, "bryg.glb" if schemat == "a" else "bryg_%s.glb" % schemat)
        ctx["bez_ao"] = "--bez-ao" in A["flags"]
        eksport.eksportuj(ctx, glb)
        # LOD1, LOD2 i bryły kolizji jako osobne pliki obok głównego
        import lod
        lod.zbuduj(ctx, glb)
    if "--kontrola" in A["flags"] or glb:
        import kontrola
        kontrola.zbuduj(ctx, glb)
    if bpy.data.collections.get("_eksport"):
        bpy.data.collections["_eksport"].hide_render = True
    if A["--rendery"] != "none":
        rendery.scena()
        rendery.woda()
        U = rendery.ujecia(ctx)
        U.update(rendery.ujecia_detali(ctx))
        lista = list(U) if A["--rendery"] == "all" else A["--rendery"].split(",")
        if A["--rendery"] == "detale":
            lista = [n for n in U if n.startswith("detal_")]
        elif A["--rendery"] == "porownanie":
            lista = ["burta_z_wody", "oczy_ku_dziobowi", "deski_zblizenie", "rufa_z_wody"]
        rdir = os.path.join(out, "rendery")
        if "plan" in lista or A["--rendery"] == "all":
            rendery.plan_tlo(ctx, os.path.join(rdir, "_plan_tlo.png"))
            subprocess.run(["python", os.path.join(HERE, "plan_pokladu.py"), out], check=False)
        for n in lista:
            if n not in U:
                continue
            pos, cel, ogn = U[n][:3]
            przywroc = U[n][3]() if len(U[n]) > 3 else None
            man = None
            if n.startswith("manekin_"):
                want = "stan_kabestan_3" if n == "manekin_kabestan" else "stan_dzialo_kapitan_3"
                st = [t for t in ctx.get("stanowiska", []) if t["nazwa"] == want]
                if st:
                    man = rendery.manekin(ctx, st[0]["x"], st[0]["s"], st[0]["yaw"])
            rendery.kamera(pos, cel, ogn)
            nm_out = "dzialo_polyhaven" if (n == "dzialo_zblizenie" and ctx.get("dzialo_polyhaven")) else n
            if A["--rendery"] == "porownanie":
                nm_out = "porownanie_%s_%s" % (n, "polyhaven" if cc0 else "proceduralne")
            rendery.renderuj(os.path.join(rdir, "%s_%s.png" % (nm_out, schemat)))
            if przywroc:
                przywroc()
            if man is not None:
                bpy.data.objects.remove(man, do_unlink=True)
    # 15. Kontrola plików GLB: obrazy materiałów wobec źródeł, rendery z wczytanego GLB wobec renderów z .blend.
    if glb:
        import kontrola_glb
        kontrola_glb.zbuduj(ctx, glb, os.path.join(out, "rendery") if A["--rendery"] == "all" else None, schemat)
    print("KONIEC %.1f s" % (time.time() - t0))


main()
