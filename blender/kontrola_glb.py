"""Kontrola wyeksportowanych plików GLB (po eksporcie, wołana z buduj.py):

1. materiały: dla każdego materiału GLB – obrazy koloru, ORM i normalnych muszą być różne; średni kolor mapy koloru
   z GLB porównany ze źródłem w .blend (różnica kanału ≤ 0,05); rozmiar równy źródłu albo zmniejszony 2^k razy.
2. rendery z wczytanego GLB (te same kamery, słońce, niebo i woda co rendery z .blend): burta z wody, pokład z oczu,
   rufa, koło sterowe; średnia jasność i odcień kadru porównane z kadrem z .blend (progi PROG_JASNOSC, PROG_ODCIEN).
"""
import json
import os
import struct

import bpy
import numpy as np

PROG_KOLOR = 0.05
PROG_JASNOSC = 0.10       # względna różnica średniej jasności kadru
PROG_ODCIEN = 0.04        # różnica średniego udziału kanałów (r, g, b) / suma
KADRY = ("burta_z_wody", "oczy_ku_dziobowi", "rufa_z_wody", "detal_kolo_oczy_sternika")


def _glb(path):
    data = open(path, "rb").read()
    ln = struct.unpack("<I", data[12:16])[0]
    gj = json.loads(data[20:20 + ln].decode("utf-8"))
    off = 20 + ln
    bl = struct.unpack("<I", data[off:off + 4])[0]
    binc = data[off + 8:off + 8 + bl]
    return gj, binc


def _srednia(im, krok=7):
    px = np.empty(len(im.pixels), np.float32)
    im.pixels.foreach_get(px)
    a = px.reshape(-1, 4)[::krok, :3]
    return a.mean(0)


def _zrodlo(nazwa):
    m = bpy.data.materials.get(nazwa) or bpy.data.materials.get(nazwa.split("__")[0])
    if m is None or not m.use_nodes:
        return None
    for n in m.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image and n.image.colorspace_settings.name == "sRGB":
            return n.image
    return None


def materialy(path, tmp):
    gj, binc = _glb(path)
    os.makedirs(tmp, exist_ok=True)
    cache = {}

    def obraz(ti):
        if ti in cache:
            return cache[ti]
        src = gj["textures"][ti]["source"]
        im = gj["images"][src]
        bv = gj["bufferViews"][im["bufferView"]]
        raw = binc[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + bv["byteLength"]]
        ext = ".png" if im.get("mimeType") == "image/png" else ".jpg"
        p = os.path.join(tmp, "%s_%d%s" % (os.path.splitext(os.path.basename(path))[0], src, ext))
        open(p, "wb").write(raw)
        b = bpy.data.images.load(p, check_existing=False)
        cache[ti] = (src, im.get("name"), b)
        return cache[ti]
    wyn, zle = [], 0
    for m in gj.get("materials", []):
        pb = m.get("pbrMetallicRoughness", {})
        idx = {k: v["index"] for k, v in (("kolor", pb.get("baseColorTexture")), ("orm", pb.get("metallicRoughnessTexture")),
                                          ("normalne", m.get("normalTexture"))) if v}
        src = {k: obraz(v)[0] for k, v in idx.items()}
        rozne = len(set(src.values())) == len(src)
        r = dict(material=m["name"], obrazy={k: obraz(v)[1] for k, v in idx.items()}, rozne_obrazy=rozne)
        ok = rozne
        if "kolor" in idx:
            b = obraz(idx["kolor"])[2]
            z = _zrodlo(m["name"])
            if z is not None:
                dk = float(np.abs(_srednia(b) - _srednia(z)).max())
                sx, sz = b.size[0], z.size[0]
                rozm_ok = sz % max(sx, 1) == 0 and (sz // max(sx, 1)) in (1, 2, 4, 8)
                r.update(roznica_koloru=round(dk, 3), rozmiar=[sx, sz], rozmiar_ok=rozm_ok)
                ok = ok and dk <= PROG_KOLOR and rozm_ok
        r["ok"] = ok
        zle += 0 if ok else 1
        wyn.append(r)
    for (_, _, b) in cache.values():
        bpy.data.images.remove(b)
    return dict(plik=os.path.basename(path), materialy=len(wyn), bledne=zle, ok=zle == 0, szczegoly=wyn)


DREWNO_GLB = ("drewno", "drewno_ciemne", "drewno_czarne", "laweta")
PROG_ANIZO = 1.25


def _jpg_png_rozmiar(b):
    if b[:4] == b"\x89PNG":
        return struct.unpack(">II", b[16:24])
    i = 2
    while i < len(b) - 9:
        if b[i] != 0xFF:
            i += 1
            continue
        m = b[i + 1]
        if 0xC0 <= m <= 0xC3:
            h, w = struct.unpack(">HH", b[i + 5:i + 9])
            return w, h
        i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    return 0, 0


def _akcesor(gj, binc, i):
    a = gj["accessors"][i]
    bv = gj["bufferViews"][a["bufferView"]]
    dt = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}[a["componentType"]]
    nc = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[a["type"]]
    off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride", 0)
    isz = np.dtype(dt).itemsize * nc
    if stride and stride != isz:
        raw = np.frombuffer(binc, np.uint8, a["count"] * stride, off).reshape(-1, stride)[:, :isz]
        arr = np.frombuffer(raw.tobytes(), dt).reshape(-1, nc)
    else:
        arr = np.frombuffer(binc, dt, a["count"] * nc, off).reshape(-1, nc)
    if a.get("normalized"):
        arr = arr.astype(np.float64) / np.iinfo(dt).max
    return arr


def uv_gestosc(path):
    """Gęstość tekseli i anizotropia UV z siatek GLB (TEXCOORD_0 × rozmiar obrazu koloru): na trójkąt wartości
    osobliwe odwzorowania płaszczyzna trójkąta → piksele (s1 ≥ s2, px/m); gęstość = √(s1·s2), anizotropia = s1/s2;
    statystyki ważone polem (mediana, 5. percentyl; udział pola z anizotropią > PROG_ANIZO). Dla drewna kierunek
    słojów: części (wierzchołki scalone po położeniu) wydłużone (oś główna ≥ 2,5 × druga) – udział pola ścian
    bocznych, na których kierunek u odchyla się od osi części o mniej niż 25°."""
    gj, binc = _glb(path)
    rozm = {}
    for i, im in enumerate(gj.get("images", [])):
        bv = gj["bufferViews"][im["bufferView"]]
        rozm[i] = _jpg_png_rozmiar(binc[bv.get("byteOffset", 0):bv.get("byteOffset", 0) + min(bv["byteLength"], 65536)])
    zb = {}
    for me in gj["meshes"]:
        for pr in me["primitives"]:
            if "material" not in pr or "TEXCOORD_0" not in pr["attributes"] or "indices" not in pr:
                continue
            mat = gj["materials"][pr["material"]]
            bt = mat.get("pbrMetallicRoughness", {}).get("baseColorTexture")
            if bt is None or bt.get("texCoord", 0) != 0:
                continue
            W, H = rozm[gj["textures"][bt["index"]]["source"]]
            P = _akcesor(gj, binc, pr["attributes"]["POSITION"]).astype(np.float64)
            T = _akcesor(gj, binc, pr["attributes"]["TEXCOORD_0"]).astype(np.float64) * np.array([W, H])
            I = _akcesor(gj, binc, pr["indices"]).astype(np.int64).reshape(-1, 3)
            nm = mat["name"].split("__")[0]
            zb.setdefault(nm, []).append((P, T, I))
    wyn = {}
    for nm, lst in zb.items():
        dens, anis, area, zgod, pole_drewna = [], [], [], 0.0, 0.0
        for P, T, I in lst:
            p0, p1, p2 = P[I[:, 0]], P[I[:, 1]], P[I[:, 2]]
            e1, e2 = p1 - p0, p2 - p0
            n = np.cross(e1, e2)
            a2 = np.linalg.norm(n, axis=1)
            ok = a2 > 1e-10
            l1 = np.linalg.norm(e1, axis=1) + 1e-12
            x = e1 / l1[:, None]
            y = np.cross(n / (a2[:, None] + 1e-12), x)
            Lm = np.stack([np.stack([l1, np.zeros_like(l1)], 1), np.stack([(e2 * x).sum(1), (e2 * y).sum(1)], 1)], 2)
            t0, t1, t2 = T[I[:, 0]], T[I[:, 1]], T[I[:, 2]]
            Dm = np.stack([t1 - t0, t2 - t0], 2)                    # kolumny: przyrosty px
            det = Lm[:, 0, 0] * Lm[:, 1, 1] - Lm[:, 0, 1] * Lm[:, 1, 0]
            ok &= np.abs(det) > 1e-14
            inv = np.zeros_like(Lm)
            inv[:, 0, 0], inv[:, 1, 1] = Lm[:, 1, 1], Lm[:, 0, 0]
            inv[:, 0, 1], inv[:, 1, 0] = -Lm[:, 0, 1], -Lm[:, 1, 0]
            inv /= np.where(np.abs(det) > 1e-14, det, 1)[:, None, None]
            M = Dm @ inv
            sv = np.linalg.svd(M[ok], compute_uv=False)
            s1, s2 = sv[:, 0], np.maximum(sv[:, 1], 1e-9)
            dens.append(np.sqrt(s1 * s2))
            anis.append(s1 / s2)
            area.append(a2[ok] / 2)
            if nm in DREWNO_GLB:
                zg, pl = _sloje(P, T, I, n, a2)
                zgod += zg
                pole_drewna += pl
        d, an, ar = np.concatenate(dens), np.concatenate(anis), np.concatenate(area)
        o = np.argsort(d)
        cw = np.cumsum(ar[o]) / ar.sum()
        r = dict(mediana=round(float(d[o][np.searchsorted(cw, 0.5)]), 0), p05=round(float(d[o][np.searchsorted(cw, 0.05)]), 0),
                 anizo_mediana=round(float(an[np.argsort(an)][np.searchsorted(np.cumsum(ar[np.argsort(an)]) / ar.sum(), 0.5)]), 3),
                 anizo_ponad_prog=round(float(ar[an > PROG_ANIZO].sum() / ar.sum()), 3), pole_m2=round(float(ar.sum()), 1))
        if nm in DREWNO_GLB and pole_drewna > 0:
            r["sloje_wzdluz"] = round(zgod / pole_drewna, 3)
        wyn[nm] = r
    return wyn


def _sloje(P, T, I, n, a2):
    """(pole zgodne, pole ścian bocznych) dla części wydłużonych – kierunek u wzdłuż osi części."""
    q = np.round(P / 1e-4).astype(np.int64)
    _, inv = np.unique(q, axis=0, return_inverse=True)
    inv = inv.ravel()
    par = np.arange(inv.max() + 1)

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    for t in inv[I]:
        a, b, c = find(t[0]), find(t[1]), find(t[2])
        par[b] = a
        par[find(c)] = a
    root = np.array([find(i) for i in range(len(par))])
    comp = root[inv[I[:, 0]]]
    zg, pl = 0.0, 0.0
    e1, e2 = P[I[:, 1]] - P[I[:, 0]], P[I[:, 2]] - P[I[:, 0]]
    du1, du2 = T[I[:, 1]] - T[I[:, 0]], T[I[:, 2]] - T[I[:, 0]]
    det = du1[:, 0] * du2[:, 1] - du2[:, 0] * du1[:, 1]
    Pu = (e1 * du2[:, 1:2] - e2 * du1[:, 1:2]) / np.where(np.abs(det) > 1e-12, det, 1)[:, None]
    for c in np.unique(comp):
        f = np.where(comp == c)[0]
        vs = np.unique(I[f])
        X = P[vs] - P[vs].mean(0)
        if len(vs) < 4:
            continue
        w, E = np.linalg.eigh(X.T @ X)
        ax = E[:, 2]
        pr = X @ E
        ext = pr.max(0) - pr.min(0)
        if ext[2] < 2.5 * max(ext[1], 1e-6):
            continue
        nn = n[f] / (a2[f][:, None] + 1e-12)
        bok = np.abs(nn @ ax) < 0.7
        if not bok.any():
            continue
        pu = Pu[f][bok]
        cos = np.abs(pu @ ax) / (np.linalg.norm(pu, axis=1) + 1e-12)
        ar = a2[f][bok] / 2
        zg += float(ar[cos >= 0.906].sum())
        pl += float(ar.sum())
    return zg, pl


def _png(path):
    im = bpy.data.images.load(path, check_existing=False)
    s = _srednia(im, krok=3)
    bpy.data.images.remove(im)
    return s


def rendery(ctx, glb, rdir, schemat="a"):
    import rendery as RD
    sc = bpy.context.scene
    root = ctx["root"]
    root.hide_render = True
    kol = bpy.data.collections.new("_z_glb")
    sc.collection.children.link(kol)
    lc = bpy.context.view_layer.layer_collection.children[kol.name]
    bpy.context.view_layer.active_layer_collection = lc
    przed = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=glb)
    nowe = [o for o in bpy.data.objects if o not in przed]
    dom = ctx.get("naped_domyslny", "naped_kolo")
    for o in nowe:
        w = o.get("wariant")
        if w and w != dom:
            o.hide_render = True
    U = RD.ujecia(ctx)
    U.update(RD.ujecia_detali(ctx))
    wyn, zle = [], 0
    for n in KADRY:
        if n not in U:
            continue
        RD.kamera(*U[n][:3])
        p = os.path.join(rdir, "z_glb_%s_%s.png" % (n, schemat))
        RD.renderuj(p)
        q = os.path.join(rdir, "%s_%s.png" % (n, schemat))
        if not os.path.exists(q):
            continue
        a, b = _png(p), _png(q)
        ja, jb = float(a.mean()), float(b.mean())
        dj = abs(ja - jb) / max(jb, 1e-3)
        do = float(np.abs(a / max(a.sum(), 1e-6) - b / max(b.sum(), 1e-6)).max())
        ok = dj <= PROG_JASNOSC and do <= PROG_ODCIEN
        zle += 0 if ok else 1
        wyn.append(dict(kadr=n, jasnosc_glb=round(ja, 3), jasnosc_blend=round(jb, 3), roznica_jasnosci=round(dj, 3),
                        roznica_odcienia=round(do, 3), ok=ok, plik=os.path.basename(p)))
    for o in nowe:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.collections.remove(kol)
    root.hide_render = False
    return dict(progi=dict(jasnosc=PROG_JASNOSC, odcien=PROG_ODCIEN), kadry=wyn, ok=zle == 0 and bool(wyn))


def pomocnicze(path):
    """Węzły pomocnicze (extras.pomocniczy, np. maska wody w łodzi): każdy prymityw z materiałem o alfie 0
    (baseColorFactor[3]) i alphaMode BLEND – w przeglądarkach glTF niewidoczne."""
    gj, _ = _glb(path)
    wyn, zle = [], 0
    for n in gj.get("nodes", []):
        if not (n.get("extras") or {}).get("pomocniczy") or "mesh" not in n:
            continue
        for p in gj["meshes"][n["mesh"]]["primitives"]:
            m = gj["materials"][p["material"]] if "material" in p else {}
            a = m.get("pbrMetallicRoughness", {}).get("baseColorFactor", [1, 1, 1, 1])[3]
            ok = m.get("alphaMode") == "BLEND" and a == 0
            zle += 0 if ok else 1
            wyn.append(dict(wezel=n.get("name"), material=m.get("name"), alphaMode=m.get("alphaMode", "OPAQUE"),
                            alfa=a, ok=ok))
    return dict(wezly=wyn, ok=zle == 0 and bool(wyn))


def zbuduj(ctx, glb, rdir, schemat="a"):
    tmp = os.path.join(ctx["out"], "_glb_obrazy")
    J = dict(materialy={}, rendery=None)
    J["pomocnicze"] = pomocnicze(glb)
    for nazwa in ("bryg.glb", "bryg_lod1.glb", "bryg_lod2.glb"):
        p = os.path.join(os.path.dirname(glb), nazwa)
        if os.path.exists(p):
            J["materialy"][nazwa] = materialy(p, tmp)
    try:
        J["uv"] = uv_gestosc(glb)
    except Exception as e:                       # kontrola pomocnicza – błąd nie przerywa budowy
        J["uv"] = dict(blad=repr(e))
    if rdir:
        J["rendery"] = rendery(ctx, glb, rdir, schemat)
    J["ok"] = all(v["ok"] for v in J["materialy"].values()) and (J["rendery"] is None or J["rendery"]["ok"]) and \
        J["pomocnicze"]["ok"]
    kp = os.path.join(ctx["out"], "kontrola.json")
    K = json.load(open(kp, encoding="utf-8")) if os.path.exists(kp) else {}
    K["kontrola_glb"] = J
    json.dump(K, open(kp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("KONTROLA_GLB ok=%s %s" % (J["ok"], {k: (v["bledne"], v["materialy"]) for k, v in J["materialy"].items()}))
    return J
