"""Eksport GLB: części ruchome jako osobne węzły (z dziećmi: żagle na rejach, perty, raki), reszta scalona w dwie
siatki statyczne – 'kadlub_statyczny' (kadłub, pokład, rufa, dziób, wyposażenie) i 'takielunek_statyczny' (drzewca,
olinowanie, żagle sztakslowe) – każda z prymitywem na materiał. Liny z dolną granicą średnicy D_MIN_GLB.
Działa i działka relingowe dzielą siatki (instancje w glTF). Stanowiska (stan_*) jako puste węzły.
glTF: metry, +Y w górę, dziób ku +Z; tekstury JPEG z dysku bez ponownej kompresji (mapy normalnych q92).
"""
import json
import os

import bpy
import numpy as np

import narzedzia as N

RUCHOME_PREFIX = ("ster", "rumpel", "kolo_sterowe", "kabestan_beben", "pompa_L_dzwignia", "pompa_P_dzwignia", "furta_pokrywa_",
                  "dzialo_", "reja_", "gafel", "bom", "dzwon", "dzialko_")


def ruchomy(ob):
    n = ob.name
    if n.startswith("dzialo_laweta") or n.startswith("dzialo_lufa"):
        return False
    if n in ("dzwon_rama",):
        return False
    return n.startswith(RUCHOME_PREFIX)


def _root_moving(ob):
    p = ob
    while p is not None:
        if p.type == "MESH" and ruchomy(p):
            return p
        p = p.parent
    return None


def _grupa_gltf():
    """Grupa węzłów 'glTF Material Output' z wejściem Occlusion – eksporter glTF czyta z niej occlusionTexture."""
    g = bpy.data.node_groups.get("glTF Settings")
    if g is None:
        g = bpy.data.node_groups.new("glTF Settings", "ShaderNodeTree")
        g.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
        g.nodes.new("NodeGroupInput")
    return g


# ------------------------------------------------------------------ okluzja otoczenia (AO)
# Mapa AO (occlusionTexture, UV_AO) dla dużych powierzchni kadłuba i drzewc; okluzja w kolorach wierzchołków (COLOR_0
# – 'zabrudzenia' × AO) dla sprzętów i gęstych drobnych siatek (okucia, snycerka, balustrady). Części ruchome tylko
# z własną bryłą (węzeł AO 'Only Local'), żeby po obrocie / przesunięciu nie zostawał cień sąsiada.
AO_ODL_KADLUB = 1.0          # m – zasięg promieni mapy kadłuba (przy dłuższych cały pokład ciemnieje od nadburć)
AO_ODL_DRZEWCA = 0.6
AO_ODL_SPRZET = 0.45         # m – kolory wierzchołków sprzętów (żebra bębna, gniazda, wręby)
AO_SILA_WIERZCH = 0.7        # COLOR_0 mnoży też światło bezpośrednie – okluzja złagodzona: 1 − s·(1 − ao)
AO_POLE_NA_TROJKAT = 0.003   # m² – siatki gęstsze (średnio mniej pola na trójkąt) dostają AO w wierzchołkach
AO_ODSTEP_PX = 8             # odstęp wysp w mapie AO (px); margines wypalania połowa minus 1
AO_BIALE_PX = 12             # kwadrat bieli (AO = 1) w rogu mapy – UV ścian bez okluzji z mapy


def do_mapy_ao(ob, grupa):
    """Czy część scalanej siatki statycznej dostaje okluzję z mapy (True), czy w kolorach wierzchołków (False)."""
    if ob.name.endswith("_szklo"):
        return False
    if grupa == "drzewca_statyczne":
        return True
    if grupa != "kadlub_statyczny" or ob.users_collection and ob.users_collection[0].name == "wyposazenie":
        return False
    me = ob.data
    tri = sum(len(p.vertices) - 2 for p in me.polygons)
    return sum(p.area for p in me.polygons) / max(tri, 1) >= AO_POLE_NA_TROJKAT


def uklad_uv_ao(me, maska, rozm, odstep=AO_ODSTEP_PX, biale=AO_BIALE_PX):
    """Własne pakowanie UV_AO (zamiast smart project, który przy kilku tysiącach wysp dawał układ w wąskim pasie
    i gęstość ok. 7 px/m): wyspy z UV wejściowego (ściany połączone krawędzią o tych samych UV na obu końcach),
    każda przeskalowana do skali świata (pole UV = pole 3D), obrócona osią główną wzdłuż u, pakowanie półkowe
    (od najwyższych) ze stałym odstępem w px, skala px/m z bisekcji – największa, przy której wszystko się mieści.
    Ściany spoza maski (sprzęty z AO w wierzchołkach, szkło) i wyspy zdegenerowane → kwadrat bieli w rogu.
    Zwraca opis (wyspy, gęstość px/m, zajętość)."""
    nl, nf = len(me.loops), len(me.polygons)
    uv = np.empty(nl * 2, np.float64)
    me.uv_layers["UV_AO"].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    ls = np.empty(nf, np.int64)
    lt = np.empty(nf, np.int64)
    me.polygons.foreach_get("loop_start", ls)
    me.polygons.foreach_get("loop_total", lt)
    vi = np.empty(nl, np.int64)
    me.loops.foreach_get("vertex_index", vi)
    a3 = np.empty(nf, np.float64)
    me.polygons.foreach_get("area", a3)
    fl = np.repeat(np.arange(nf), lt)                        # ściana pętli
    nx = ls[fl] + (np.arange(nl) - ls[fl] + 1) % lt[fl]      # następna pętla w ścianie
    # pary ścian sąsiednich w UV: ta sama krawędź i te same UV na jej końcach
    va, vb = vi, vi[nx]
    sw = va > vb
    u1 = np.where(sw[:, None], uv[nx], uv)
    u2 = np.where(sw[:, None], uv, uv[nx])
    klucz = np.c_[np.minimum(va, vb), np.maximum(va, vb), np.round(np.c_[u1, u2] * 1e6).astype(np.int64)]
    _, inv = np.unique(klucz, axis=0, return_inverse=True)
    inv = inv.ravel()
    o = np.argsort(inv, kind="stable")
    rowne = inv[o[1:]] == inv[o[:-1]]
    fa, fb = fl[o[:-1]][rowne], fl[o[1:]][rowne]
    m = maska[fa] & maska[fb]
    fa, fb = fa[m], fb[m]
    lab = np.arange(nf)
    while True:                                              # spójne składowe: propagacja minimum etykiet
        mn = np.minimum(lab[fa], lab[fb])
        nowe = lab.copy()
        np.minimum.at(nowe, fa, mn)
        np.minimum.at(nowe, fb, mn)
        nowe = nowe[nowe]
        if np.array_equal(nowe, lab):
            break
        lab = nowe
    # pole UV ściany (wzór Gaussa po pętlach)
    cr = uv[:, 0] * uv[nx, 1] - uv[nx, 0] * uv[:, 1]
    a2 = np.abs(np.bincount(fl, cr, nf)) / 2
    W = H = rozm
    nowe_uv = np.tile(np.array([biale / 2.0 / W, biale / 2.0 / H]), (nl, 1))
    el = []                                                  # (pętle, punkty w metrach po obrocie, w, h)
    labf = np.where(maska, lab, -1)
    A3w = np.bincount(np.maximum(labf, 0), np.where(maska, a3, 0), nf)
    A2w = np.bincount(np.maximum(labf, 0), np.where(maska, a2, 0), nf)
    labl = labf[fl]
    o = np.argsort(labl, kind="stable")
    wyspy, start = np.unique(labl[o], return_index=True)
    konce = np.r_[start[1:], len(o)]
    def dodaj(lp, p, glab=0):
        """Wyspa (pętle, punkty w metrach): oś główna wzdłuż u; wyspy wygięte (łuki listew i pokrywy relingu
        w rzucie z góry – obwiednia ≥ 2,5 × pole) dzielone na pół wzdłuż osi głównej, rekurencyjnie."""
        p = p - p.mean(0)
        if len(p) > 2:
            ev, evec = np.linalg.eigh(p.T @ p)
            p = p @ evec[:, ::-1]                            # oś główna wzdłuż u
        p = p - p.min(0)
        wd, ht = p.max(0)
        if ht > wd:
            p = p[:, ::-1].copy()
            wd, ht = ht, wd
        f_l = fl[lp]
        fs = np.unique(f_l)
        if glab < 8 and len(fs) > 1 and wd > 0.4 and wd * ht > 2.5 * a3[fs].sum():
            n_ = np.bincount(f_l, None, nf)[fs]
            cu = np.bincount(f_l, p[:, 0], nf)[fs] / n_
            strona = np.zeros(nf, bool)
            strona[fs[cu <= np.median(cu)]] = True
            m_ = strona[f_l]
            if m_.any() and not m_.all():
                dodaj(lp[m_], p[m_], glab + 1)
                dodaj(lp[~m_], p[~m_], glab + 1)
                return
        el.append((lp, p, wd, ht))
    for w, s0, s1 in zip(wyspy, start, konce):
        if w < 0:
            continue
        A3, A2 = A3w[w], A2w[w]
        if A3 < 1e-8 or A2 < 1e-14:
            continue
        lp = o[s0:s1]
        dodaj(lp, uv[lp] * np.sqrt(A3 / A2))
    el.sort(key=lambda e: -e[3])

    def poloz(k):
        x, y, rz, poz = 0.0, float(biale), 0.0, []
        for (_, _, wd, ht) in el:
            wp, hp = wd * k + odstep, ht * k + odstep
            if wp > W:
                return None
            if x + wp > W:
                y += rz
                x, rz = 0.0, 0.0
            poz.append((x, y))
            x += wp
            rz = max(rz, hp)
        return poz if y + rz <= H else None
    lo, hi = 0.5, 4000.0
    for _ in range(40):
        k = (lo + hi) / 2
        if poloz(k) is None:
            hi = k
        else:
            lo = k
    k = lo
    poz = poloz(k)
    zajete = 0.0
    for (lp, p, wd, ht), (x, y) in zip(el, poz):
        nowe_uv[lp] = (p * k + np.array([x + odstep / 2, y + odstep / 2])) / np.array([W, H])
        zajete += wd * ht * k * k
    me.uv_layers["UV_AO"].data.foreach_set("uv", nowe_uv.astype(np.float32).ravel())
    return dict(wyspy=len(el), gestosc_px_m=round(k, 1), zajetosc_obwiedni=round(zajete / (W * H), 3),
                sciany_bez_mapy=int((~maska).sum()))


def _widoczne_tylko(obiekty):
    """Na czas wypalania renderowane tylko podane obiekty; zwraca funkcję przywracającą."""
    stan = {o.name: o.hide_render for o in bpy.data.objects}
    zbior = set(o.name for o in obiekty)
    for o in bpy.data.objects:
        o.hide_render = o.name not in zbior

    def przywroc():
        for o in bpy.data.objects:
            if o.name in stan:
                o.hide_render = stan[o.name]
    return przywroc


def _cycles(probki):
    sc = bpy.context.scene
    stan = (sc.render.engine, sc.cycles.samples)
    sc.render.engine = "CYCLES"
    sc.cycles.samples = probki
    sc.cycles.device = "CPU"

    def przywroc():
        sc.render.engine, sc.cycles.samples = stan
    return przywroc


def ao_wierzcholki(cele, widoczne, lokalnie, odl=AO_ODL_SPRZET, sila=AO_SILA_WIERZCH, probki=32):
    """Okluzja wypalona do kolorów wierzchołków (Cycles, EMIT z węzła Ambient Occlusion, rogi ścian) i wmnożona
    w 'zabrudzenia' (w GLB COLOR_0 × kolor bazowy): z ← z · (1 − sila·(1 − ao)). lokalnie=True – tylko własna bryła
    obiektu (części ruchome); False – przeszkodami są obiekty 'widoczne'. Siatki wspólne liczone raz."""
    pom = {}
    for o in cele:
        if o.type == "MESH" and len(o.data.polygons) and o.data.name not in pom and \
                "zabrudzenia" in o.data.color_attributes:
            pom[o.data.name] = o
    cele = list(pom.values())
    if not cele:
        return 0
    przywroc_w = _widoczne_tylko(list(widoczne) + cele)
    przywroc_c = _cycles(probki)
    mat = bpy.data.materials.new("_ao_wierzcholki")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    wy = nt.nodes.new("ShaderNodeOutputMaterial")
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.only_local = lokalnie
    ao.samples = 16
    ao.inputs["Distance"].default_value = odl
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(ao.outputs["AO"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], wy.inputs["Surface"])
    stare = {}
    for o in cele:
        me = o.data
        stare[o.name] = [s.material for s in o.material_slots]
        if not o.material_slots:
            me.materials.append(mat)
        for s in o.material_slots:
            s.material = mat
        at = me.color_attributes.get("_ao") or me.color_attributes.new("_ao", "FLOAT_COLOR", "CORNER")
        me.color_attributes.active_color = at
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in cele:
        o.select_set(True)
    bpy.context.view_layer.objects.active = cele[0]
    bpy.ops.object.bake(type="EMIT", target="VERTEX_COLORS")
    for o in cele:
        me = o.data
        nl = len(me.loops)
        a = np.empty(nl * 4, np.float32)
        me.color_attributes["_ao"].data.foreach_get("color", a)
        ao_v = np.clip(a.reshape(-1, 4)[:, 0], 0, 1)
        z = me.color_attributes["zabrudzenia"]
        c = np.empty(nl * 4, np.float32)
        z.data.foreach_get("color", c)
        c = c.reshape(-1, 4)
        c[:, :3] *= (1 - sila * (1 - ao_v))[:, None]
        z.data.foreach_set("color", c.ravel())
        me.color_attributes.remove(me.color_attributes["_ao"])
        me.color_attributes.active_color = me.color_attributes["zabrudzenia"]
        for s, m0 in zip(o.material_slots, stare[o.name]):
            s.material = m0
        if not stare[o.name]:
            me.materials.clear()
    bpy.data.materials.remove(mat)
    przywroc_c()
    przywroc_w()
    return len(cele)


def wypal_ao(ctx, ob, nazwa, rozm=2048, probki=48, maska=None, przeszkody=None, odl=AO_ODL_KADLUB):
    """Okluzja otoczenia wypalona (Cycles) na unikalnym drugim UV 'UV_AO' (smart project → własne pakowanie,
    uklad_uv_ao), obraz JPEG w <out>/tekstury/<nazwa>_ao.jpg. Przeszkody: tylko scalone siatki statyczne (oryginały
    leżą w tym samym miejscu – widoczne dawały okluzję od współpłaszczyznowych ścian: mapa prawie czarna, pasy).
    Materiały scalonej siatki kopiowane (<materiał>__<nazwa>) z węzłem occlusion → w GLB occlusionTexture z texCoord 1.
    Zwraca opis (rozmiar, czas, materiały, układ UV)."""
    import time
    t0 = time.time()
    me = ob.data
    uv0 = me.uv_layers[0].name
    uvao = me.uv_layers.get("UV_AO") or me.uv_layers.new(name="UV_AO")
    me.uv_layers.active = uvao
    # wyspy z UV materiałów (metry / kafel – bez zniekształceń rzutu smart project), przepakowane w unikalne 0–1
    a = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers[uv0].data.foreach_get("uv", a)
    uvao.data.foreach_set("uv", a)
    if maska is None:
        maska = np.ones(len(me.polygons), bool)
    uklad = uklad_uv_ao(me, maska, rozm)
    img = bpy.data.images.new(nazwa + "_ao", rozm, rozm, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    # tło znacznikiem (magenta): po wypaleniu niewypalone teksele dostają średnią okluzję (mipmapy bez czerni)
    tlo = np.tile(np.array([1.0, 0.0, 1.0, 1.0], np.float32), rozm * rozm)
    img.pixels.foreach_set(tlo)
    # kopie materiałów z obrazem do wypalania (aktywny węzeł)
    for i, slot in enumerate(ob.material_slots):
        m = slot.material
        if m is None:
            continue
        m2 = m.copy()
        m2.name = m.name + "__" + nazwa
        nt = m2.node_tree
        ti = nt.nodes.new("ShaderNodeTexImage")
        ti.image = img
        ti.name = "AO_wypalanie"
        uvn = nt.nodes.new("ShaderNodeUVMap")
        uvn.uv_map = "UV_AO"
        nt.links.new(uvn.outputs["UV"], ti.inputs["Vector"])
        nt.nodes.active = ti
        ob.material_slots[i].material = m2
    sc = bpy.context.scene
    przywroc_c = _cycles(probki)
    przywroc_w = _widoczne_tylko([ob] + list(przeszkody or []))
    marg = AO_ODSTEP_PX // 2 - 1
    sc.render.bake.margin = marg
    sc.world = sc.world or bpy.data.worlds.new("swiat_ao")
    odl0 = sc.world.light_settings.distance
    sc.world.light_settings.distance = odl
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.bake(type="AO", margin=marg, use_clear=False)
    sc.world.light_settings.distance = odl0
    przywroc_w()
    przywroc_c()
    px = np.empty(rozm * rozm * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(rozm, rozm, 4)
    # wypalone teksele są szare (R = G = B); znacznik i jego mieszanki z marginesu – tło
    tlo = (np.abs(px[..., 0] - px[..., 1]) > 0.02) | (np.abs(px[..., 1] - px[..., 2]) > 0.02)
    srednia = float(px[..., 0][~tlo].mean()) if (~tlo).any() else 1.0
    # szum próbkowania (48 próbek) wygładzony filtrem 3 × 3 tylko po tekselach wypalonych (bez mieszania z tłem):
    # mniejszy JPEG, okluzja i tak jest gładka
    w_ = (~tlo).astype(np.float32)
    v_ = px[..., 0] * w_
    sv, sw = np.zeros_like(v_), np.zeros_like(w_)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            sv += np.roll(np.roll(v_, dy, 0), dx, 1)
            sw += np.roll(np.roll(w_, dy, 0), dx, 1)
    px[..., 0] = np.where(tlo, px[..., 0], sv / np.maximum(sw, 1e-6))
    px[tlo, :3] = srednia
    px[..., 1] = px[..., 0]
    px[..., 2] = px[..., 0]
    px[:AO_BIALE_PX, :AO_BIALE_PX, :3] = 1.0           # kwadrat bieli (ściany z AO w wierzchołkach)
    img.pixels.foreach_set(px.ravel())
    uklad.update(srednia_ao=round(srednia, 3), wypalone_teksele=round(float((~tlo).mean()), 3), odleglosc_m=odl)
    sciezka = os.path.join(ctx["out"], "tekstury", nazwa + "_ao.jpg")
    img.filepath_raw = sciezka
    img.file_format = "JPEG"
    # AO gładka (filtr 3 × 3) – JPEG 60 wystarcza (jakość podana jawnie: Image.save bez niej zapisywał 90)
    img.save(filepath=sciezka, quality=60)
    img.source = "FILE"
    img.filepath = sciezka
    img.reload()
    # podłączenie: obraz (UV_AO) → R → grupa glTF Material Output (Occlusion)
    g = _grupa_gltf()
    for slot in ob.material_slots:
        m2 = slot.material
        if m2 is None:
            continue
        nt = m2.node_tree
        ti = nt.nodes.get("AO_wypalanie")
        sp = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(ti.outputs["Color"], sp.inputs["Color"])
        gn = nt.nodes.new("ShaderNodeGroup")
        gn.node_tree = g
        nt.links.new(sp.outputs["Red"], gn.inputs["Occlusion"])
    me.uv_layers.active = me.uv_layers[uv0]
    for lay in me.uv_layers:
        lay.active_render = lay.name == uv0
    return dict(obraz=os.path.basename(sciezka), rozmiar=rozm, probki=probki, czas_s=round(time.time() - t0, 1),
                materialy=len(ob.material_slots), uv=uklad)


def popraw_pomocnicze(sciezka):
    """Materiały węzłów pomocniczych (extras.pomocniczy, np. maska wody w łodzi) w zapisanym GLB: alphaMode BLEND
    i alfa 0 w baseColorFactor (eksporter glTF zapisuje stałą alfę 0 jako MASK z progiem); JSON przepisany w miejscu."""
    import struct
    with open(sciezka, "rb") as f:
        data = f.read()
    ln = struct.unpack("<I", data[12:16])[0]
    gj = json.loads(data[20:20 + ln].decode("utf-8"))
    mats = set()
    for n in gj.get("nodes", []):
        if (n.get("extras") or {}).get("pomocniczy") and "mesh" in n:
            for p in gj["meshes"][n["mesh"]]["primitives"]:
                if "material" in p:
                    mats.add(p["material"])
    if not mats:
        return 0
    for i in mats:
        m = gj["materials"][i]
        m["alphaMode"] = "BLEND"
        m.pop("alphaCutoff", None)
        pb = m.setdefault("pbrMetallicRoughness", {})
        bc = list(pb.get("baseColorFactor", [1, 1, 1, 1]))
        pb["baseColorFactor"] = bc[:3] + [0.0]
    js = json.dumps(gj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    reszta = data[20 + ln:]
    calosc = 12 + 8 + len(js) + len(reszta)
    with open(sciezka, "wb") as f:
        f.write(data[:8] + struct.pack("<I", calosc) + struct.pack("<I", len(js)) + data[16:20] + js + reszta)
    return len(mats)


def spakuj_kolory(sciezka):
    """Kolory wierzchołków COLOR_0 w zapisanym GLB: eksporter glTF zapisuje je jako liczby zmiennoprzecinkowe
    (12 B na wierzchołek), tu przepisane na znormalizowane bajty RGBA (4 B; glTF 2.0 dopuszcza oba zapisy).
    Kolory są mnożnikami zabrudzeń i cieniowania zagłębień, 256 poziomów wystarcza. Zwraca liczbę zaoszczędzonych
    bajtów (0, gdy nie było czego przepisać)."""
    import struct
    with open(sciezka, "rb") as f:
        data = f.read()
    ln = struct.unpack("<I", data[12:16])[0]
    gj = json.loads(data[20:20 + ln].decode("utf-8"))
    b0 = 20 + ln
    blen, btyp = struct.unpack("<II", data[b0:b0 + 8])
    if btyp != 0x004E4942 or len(gj.get("buffers", [])) != 1:
        return 0
    B = data[b0 + 8:b0 + 8 + blen]
    acc, bvs = gj["accessors"], gj["bufferViews"]
    kol = {p["attributes"]["COLOR_0"] for m in gj["meshes"] for p in m["primitives"] if "COLOR_0" in p["attributes"]}
    uzycie = {}
    for i, a in enumerate(acc):
        if "bufferView" in a:
            uzycie.setdefault(a["bufferView"], []).append(i)
    for im in gj.get("images", []):
        if "bufferView" in im:
            uzycie.setdefault(im["bufferView"], []).append(-1)
    nowe = {}
    for ai in sorted(kol):
        a = acc[ai]
        bi = a.get("bufferView")
        if a.get("componentType") != 5126 or a.get("type") not in ("VEC3", "VEC4") or "sparse" in a or bi is None:
            continue
        if uzycie.get(bi) != [ai] or bvs[bi].get("byteStride") or a.get("byteOffset", 0):
            continue
        n, k = a["count"], (3 if a["type"] == "VEC3" else 4)
        arr = np.frombuffer(B, dtype="<f4", count=n * k, offset=bvs[bi].get("byteOffset", 0)).reshape(n, k)
        out = np.full((n, 4), 255, dtype=np.uint8)
        out[:, :k] = np.clip(np.rint(arr * 255.0), 0, 255).astype(np.uint8)
        nowe[bi] = out.tobytes()
        a["componentType"], a["normalized"], a["type"] = 5121, True, "VEC4"
        a.pop("min", None)
        a.pop("max", None)
    if not nowe:
        return 0
    wyj = bytearray()
    for i in sorted(range(len(bvs)), key=lambda j: bvs[j].get("byteOffset", 0)):
        bv = bvs[i]
        o = bv.get("byteOffset", 0)
        kawalek = nowe[i] if i in nowe else B[o:o + bv["byteLength"]]
        wyj += b"\0" * ((4 - len(wyj) % 4) % 4)
        bv["byteOffset"], bv["byteLength"] = len(wyj), len(kawalek)
        wyj += kawalek
    wyj += b"\0" * ((4 - len(wyj) % 4) % 4)
    gj["buffers"][0]["byteLength"] = len(wyj)
    js = json.dumps(gj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    calosc = 12 + 8 + len(js) + 8 + len(wyj)
    with open(sciezka, "wb") as f:
        f.write(data[:8] + struct.pack("<I", calosc) + struct.pack("<I", len(js)) + data[16:20] + js +
                struct.pack("<II", len(wyj), 0x004E4942) + bytes(wyj))
    return len(data) - calosc


def eksportuj(ctx, sciezka):
    import olinowanie
    PR = ctx["PR"]
    d_min = PR.OLINOWANIE["D_MIN_GLB"]
    sc = bpy.context.scene
    ekol = N.kolekcja("_eksport")
    # liny z dolną granicą grubości (osobne obiekty), oryginały pomijane
    liny_orig = set(o.name for o in ctx["obj"].get("liny", []))
    liny_glb = olinowanie.realizuj(ctx, d_min=d_min, kol=ekol, sufiks="_glb")
    # oba warianty napędu steru w GLB: odkryte na czas eksportu (widoczność domyślna w extras grup)
    for o in bpy.data.objects:
        if o.get("wariant"):
            o.hide_viewport = False
            o.hide_render = False
    static_groups = {"kadlub_statyczny": ("kadlub", "rufa_dziob", "wyposazenie"),
                     "drzewca_statyczne": ("drzewca",),
                     "takielunek_statyczny": ("olinowanie", "zagle_zwiniete")}
    # okluzja w kolorach wierzchołków (przed kopiami do scalenia): części ruchome tylko własną bryłą, sprzęty stałe
    # i gęste drobne siatki kadłuba z przeszkodami ze wszystkich stałych obiektów (bez lin i części ruchomych)
    ao_w = {}
    if not ctx.get("bez_ao"):
        def _mesh_ok(o):
            return o.type == "MESH" and not o.name.startswith(("lina_", "##", "zagiel", "zagle")) and \
                o.name not in liny_orig and o.users_collection and o.users_collection[0].name != "_eksport" and \
                not o.get("osobny_wezel") and not o.name.endswith("_szklo")
        ruch = [o for o in bpy.data.objects if _mesh_ok(o) and _root_moving(o) is not None]
        stale = [o for o in bpy.data.objects if _mesh_ok(o) and _root_moving(o) is None]
        cele_st = [o for o in stale if o.get("wariant") or o.users_collection[0].name == "wyposazenie" or
                   (o.users_collection[0].name in ("kadlub", "rufa_dziob") and not do_mapy_ao(o, "kadlub_statyczny"))]
        ao_w["ruchome_siatki"] = ao_wierzcholki(ruch, [], True)
        ao_w["stale_siatki"] = ao_wierzcholki(cele_st, stale, False)
        ao_w["obiekty_stale"] = sorted(o.name for o in cele_st)
    joined = {}
    for gname, cols in static_groups.items():
        parts = []
        for cn in cols:
            for ob in ctx["kol"][cn].all_objects:
                if ob.type != "MESH" or ob.name in liny_orig:
                    continue
                if _root_moving(ob) is not None or ob.get("wariant") or ob.get("osobny_wezel"):
                    continue
                parts.append(ob)
        if gname == "takielunek_statyczny":
            parts += [o for o in liny_glb if o.parent is None and not o.get("lina_dynamiczna")]
        cp = []
        for ob in parts:
            c = ob.copy()
            c.data = ob.data.copy()
            if "zabrudzenia" not in c.data.color_attributes or "odcien" in c.data.color_attributes:
                # części bez zabrudzeń: odcień elementu albo biel (scalanie wypełniłoby brak czernią)
                import kadlub
                kadlub.zapisz_kolory(c.data, None)
            # ściany z okluzją z mapy (1) albo z kolorów wierzchołków / bez okluzji (0) – maska dla UV_AO
            at = c.data.attributes.new("_ao_mapa", "INT", "FACE")
            at.data.foreach_set("value", [1 if do_mapy_ao(ob, gname) else 0] * len(c.data.polygons))
            c.parent = None
            c.matrix_world = ob.matrix_world.copy()
            ekol.objects.link(c)
            cp.append(c)
        if not cp:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        for c in cp:
            c.select_set(True)
        bpy.context.view_layer.objects.active = cp[0]
        with bpy.context.temp_override(active_object=cp[0], selected_editable_objects=cp, selected_objects=cp):
            bpy.ops.object.join()
        j = bpy.context.view_layer.objects.active
        j.name = gname
        j.data.name = gname
        joined[gname] = j
    maski = {}
    for gname, j in joined.items():
        at = j.data.attributes.get("_ao_mapa")
        if at is not None:
            v = np.zeros(len(j.data.polygons), np.int32)
            at.data.foreach_get("value", v)
            maski[gname] = v > 0
            j.data.attributes.remove(at)
    # AO na drugim UV (UV_AO, unikalne 0–1) dla kadłuba i drzewc – occlusionTexture, texCoord 1; przeszkody: tylko
    # scalone siatki kadłuba i drzewc (bez lin, żagli i części ruchomych)
    ao = {}
    if not ctx.get("bez_ao"):
        przeszk = [joined[g] for g in ("kadlub_statyczny", "drzewca_statyczne") if g in joined]
        for gname in ("kadlub_statyczny", "drzewca_statyczne"):
            if gname in joined:
                # drzewca: AO 1K (zmiany okluzji na drzewcach łagodne), kadłub 2K
                ao[gname] = wypal_ao(ctx, joined[gname], gname, rozm=1024 if gname == "drzewca_statyczne" else 2048,
                                     maska=maski.get(gname), przeszkody=przeszk,
                                     odl=AO_ODL_DRZEWCA if gname == "drzewca_statyczne" else AO_ODL_KADLUB)
        ao["kolory_wierzcholkow"] = ao_w
    # do eksportu: scalone + ruchome (z dziećmi) + liny ruchome z rodzicami w wersji GLB + stanowiska
    sel = list(joined.values())
    for ob in bpy.data.objects:
        if ob.type == "MESH" and ruchomy(ob) and ob.users_collection and ob.users_collection[0].name != "_eksport":
            sel.append(ob)
            for ch in ob.children_recursive:
                if ch.type == "MESH" and ch.name not in liny_orig:
                    sel.append(ch)
    # liny dzieci rej: oryginały (prawdziwa grubość) zamieniamy na wersje GLB; liny dynamiczne jako osobne węzły
    for o in liny_glb:
        if o.parent is not None or o.get("lina_dynamiczna"):
            sel.append(o)
    # grupy wariantów napędu steru (puste węzły z extras.wariant) z częściami stałymi i kołem
    for o in bpy.data.objects:
        if o.get("wariant") and o.type in ("EMPTY", "MESH") and not o.name.startswith("lina_") and \
                o.users_collection and o.users_collection[0].name != "_eksport" and \
                o.users_collection[0].name != "stanowiska":
            sel.append(o)
    # osobne węzły danych dla gry (np. maska wody wewnątrz łodzi) – nie scalane z kadłubem
    sel += [o for o in bpy.data.objects if o.type == "MESH" and o.get("osobny_wezel") and o.users_collection
            and o.users_collection[0].name != "_eksport"]
    sel = list(dict.fromkeys(o for o in sel if o.name not in liny_orig))
    for e in ctx["kol"]["stanowiska"].objects:
        sel.append(e)
    bpy.ops.object.select_all(action="DESELECT")
    for o in sel:
        try:
            o.select_set(True)
        except RuntimeError:
            pass
    # ukryj oryginalne liny-dzieci rej, by nie weszły przez hierarchię
    hidden = []
    for n in liny_orig:
        ob = bpy.data.objects.get(n)
        if ob is not None:
            ob.hide_set(True)
            ob.select_set(False)
            hidden.append(ob)
    os.makedirs(os.path.dirname(sciezka), exist_ok=True)
    # tekstury o połowę mniejsze tam, gdzie po zmniejszeniu 5. percentyl gęstości zostaje ≥ celu materiału
    # (parametry.GESTOSC_CEL: deski 800 px/m, wyposażenie 1000 px/m); mapy AO bez zmian
    import kontrola
    gt = kontrola.gestosc_tekseli([o for o in sel if o.type == "MESH"])
    cel = ctx["PR"].GESTOSC_CEL
    gesto = {m for m, v in gt.items() if v["p05"] / 2 >= cel.get(m, cel["*"])}
    podmiana = []
    for m in bpy.data.materials:
        if not m.use_nodes or m.name.split("__")[0] not in gesto:
            continue
        for n in m.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image and n.image.size[0] > 512 and not n.image.name.endswith("_ao"):
                im1 = bpy.data.images.get(n.image.name + "_1k")
                if im1 is None:
                    im1 = n.image.copy()
                    im1.name = n.image.name + "_1k"
                    im1.scale(n.image.size[0] // 2, n.image.size[1] // 2)
                    p1 = os.path.join(ctx["out"], "tekstury", "%s_1k.jpg" % bpy.path.clean_name(n.image.name))
                    im1.filepath_raw = p1
                    im1.file_format = "JPEG"
                    im1.save()
                podmiana.append((n, n.image))
                n.image = im1
    ctx["tekstury_1k"] = sorted(gesto)
    bpy.ops.export_scene.gltf(filepath=sciezka, export_format="GLB", use_selection=True, export_yup=True,
                              export_apply=True, export_image_format="JPEG", export_texcoords=True,
                              export_normals=True, export_tangents=False, export_materials="EXPORT",
                              export_extras=True,
                              export_cameras=False, export_lights=False, export_draco_mesh_compression_enable=False,
                              export_animations=False)
    popraw_pomocnicze(sciezka)          # maska wody w łodzi: niewidoczna w przeglądarkach (BLEND, alfa 0)
    ctx["kolory_spakowane_bajty"] = spakuj_kolory(sciezka)      # COLOR_0: float → bajty (ok. 1,7 MB mniej)
    for n, im in podmiana:
        n.image = im
    for ob in hidden:
        ob.hide_set(False)
    import sterowanie
    sterowanie.pokaz(ctx, ctx.get("naped_domyslny", "naped_kolo"))
    info = dict(plik=sciezka, bajty=os.path.getsize(sciezka), wezly=len(sel),
                scalone={k: len(v.data.polygons) for k, v in joined.items()}, ao=ao, tekstury_1k=ctx.get("tekstury_1k"))
    ctx["eksport"] = dict(joined=joined, sel=sel, liny_glb=liny_glb, info=info)
    print("EKSPORT " + json.dumps(info, ensure_ascii=False))
    return info
