"""Materiały Blendera z kafelkujących tekstur (tekstury.py) w układzie zgodnym z eksportem glTF:
kolor = obraz × stały kolor (węzeł Mix/Multiply → baseColorFactor), mapa normalnych (Normal Map, przestrzeń
styczna), chropowatość i metaliczność z kanałów G i B jednego obrazu (glTF metallicRoughness).
"""
import os

import bpy

import narzedzia as N
import parametry as PR

_IMG = {}


def _img(path, noncolor):
    key = (path, noncolor)
    if key in _IMG:
        return _IMG[key]
    im = bpy.data.images.load(path, check_existing=True)
    im.colorspace_settings.name = "Non-Color" if noncolor else "sRGB"
    _IMG[key] = im
    return im


def material(nazwa, spec, texdir):
    m = bpy.data.materials.get(nazwa) or bpy.data.materials.new(nazwa)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bs.location = (300, 0)
    nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])
    tex = spec["tex"]
    nrm = spec.get("nrm", tex)
    col_p = spec.get("_col") or os.path.join(texdir, tex + "_kolor.jpg")
    nrm_p = spec.get("_nrm") or os.path.join(texdir, nrm + "_normalne.jpg")
    rm_p = spec.get("_rm") or os.path.join(texdir, spec.get("rm", tex) + "_szorstkosc.jpg")
    ti = nt.nodes.new("ShaderNodeTexImage")
    ti.image = _img(col_p, False)
    ti.location = (-500, 250)
    k = spec.get("kolor", (1, 1, 1))              # MATERIALY: mnożnik liniowy (jak dotąd)
    if tuple(k) != (1, 1, 1):
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        mx.blend_type = "MULTIPLY"
        mx.inputs["Factor"].default_value = 1.0
        mx.location = (-150, 250)
        nt.links.new(ti.outputs["Color"], mx.inputs[6])
        mx.inputs[7].default_value = (min(k[0], 1.0), min(k[1], 1.0), min(k[2], 1.0), 1.0)
        nt.links.new(mx.outputs[2], bs.inputs["Base Color"])
    else:
        nt.links.new(ti.outputs["Color"], bs.inputs["Base Color"])
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = _img(nrm_p, True)
    tn.location = (-500, -250)
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.location = (-150, -250)
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bs.inputs["Normal"])
    tr = nt.nodes.new("ShaderNodeTexImage")
    tr.image = _img(rm_p, True)
    tr.location = (-500, 0)
    sp = nt.nodes.new("ShaderNodeSeparateColor")
    sp.location = (-150, 0)
    nt.links.new(tr.outputs["Color"], sp.inputs["Color"])
    nt.links.new(sp.outputs["Green"], bs.inputs["Roughness"])
    nt.links.new(sp.outputs["Blue"], bs.inputs["Metallic"])
    if spec.get("_zabrudzenia"):
        ca = nt.nodes.new("ShaderNodeVertexColor")
        ca.layer_name = "zabrudzenia"
        ca.location = (-150, 450)
        mx2 = nt.nodes.new("ShaderNodeMix")
        mx2.data_type = "RGBA"
        mx2.blend_type = "MULTIPLY"
        mx2.inputs["Factor"].default_value = 1.0
        mx2.location = (100, 300)
        src = bs.inputs["Base Color"].links[0].from_socket
        nt.links.new(src, mx2.inputs[6])
        nt.links.new(ca.outputs["Color"], mx2.inputs[7])
        nt.links.new(mx2.outputs[2], bs.inputs["Base Color"])
    m.diffuse_color = (k[0] * 0.5, k[1] * 0.4, k[2] * 0.3, 1)
    m.use_backface_culling = nazwa not in ("plotno", "szklo")   # dwustronne: płótno i szyby (pojedynczy czworokąt)
    return m


def krata(texdir):
    """Krata luku: płyta z obrazem listew (kolor + alfa) i mapą normalnych, alfa odcinana (glTF alphaMode MASK).
    Kafel 0,56 m = 8 oczek po 0,07 m, listwa 0,028 m (rozdział 09). Obrazy liczone tu (numpy), zapis PNG w tekstury/."""
    import numpy as np
    n, cel = 512, 8
    pitch = n // cel
    bar = int(round(pitch * 0.4))
    y, x = np.mgrid[0:n, 0:n]
    bx = (x % pitch) < bar
    by = (y % pitch) < bar
    hgt = np.where(by, 1.0, np.where(bx, 0.55, 0.0))
    rng = np.random.default_rng(3)
    szum = 0.9 + 0.1 * rng.random((n, n))
    col = np.stack([0.40 * szum, 0.30 * szum, 0.21 * szum], -1) * np.where(by, 1.0, 0.82)[..., None]
    a = (bx | by).astype(float)
    rgba = np.concatenate([col, a[..., None]], -1).astype(np.float32)
    gy, gx = np.gradient(hgt * 6.0)
    nrm = np.stack([-gx, gy, np.ones_like(gx)], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    nrm_rgba = np.concatenate([nrm * 0.5 + 0.5, np.ones((n, n, 1))], -1).astype(np.float32)
    ims = []
    for nazwa, px, noncolor in (("krata_kolor", rgba, False), ("krata_normalne", nrm_rgba, True)):
        im = bpy.data.images.get(nazwa) or bpy.data.images.new(nazwa, n, n, alpha=True)
        im.pixels.foreach_set(px.ravel())
        im.filepath_raw = os.path.join(texdir, nazwa + ".png")
        im.file_format = "PNG"
        im.save()
        im.colorspace_settings.name = "Non-Color" if noncolor else "sRGB"
        ims.append(im)
    m = bpy.data.materials.get("krata") or bpy.data.materials.new("krata")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])
    ti = nt.nodes.new("ShaderNodeTexImage")
    ti.image = ims[0]
    nt.links.new(ti.outputs["Color"], bs.inputs["Base Color"])
    mt = nt.nodes.new("ShaderNodeMath")
    mt.operation = "GREATER_THAN"
    mt.inputs[1].default_value = 0.5
    nt.links.new(ti.outputs["Alpha"], mt.inputs[0])
    nt.links.new(mt.outputs[0], bs.inputs["Alpha"])
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = ims[1]
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bs.inputs["Normal"])
    bs.inputs["Roughness"].default_value = 0.8
    bs.inputs["Metallic"].default_value = 0.0
    m.use_backface_culling = False if False else True
    N.MATERIALY_REJESTR["krata"] = m
    N.KAFLE["krata"] = (0.56, 0.56)
    return m


def spec_cc0(nazwa, spec, cc0):
    """Materiał z zestawu fotograficznego CC0: obrazy z katalogu kopii roboczych, kafel z liczby desek na obraz
    (szerokość deski z parametru) albo z fizycznego rozmiaru tekstury, mnożnik koloru: farby i płótno – kolor
    materiału na odbarwionym obrazie, drewno – kolor z MATERIALY_CC0 (albo z MATERIALY dla ciemniejszych odmian)."""
    import json
    c = PR.MATERIALY_CC0[nazwa]
    info = json.load(open(os.path.join(cc0, "_kafle.json"), encoding="utf-8"))[c["id"]]
    s = dict(spec)
    s["_col"] = os.path.join(cc0, c["id"] + "_kolor.jpg")
    s["_nrm"] = os.path.join(cc0, c["id"] + "_normalne.jpg")
    s["_rm"] = os.path.join(cc0, c["id"] + "_szorstkosc.jpg")
    if c.get("deski") and info.get("deski"):
        k = info["deski"] * c["szer_deski"]
        s["kafel"] = (k, k)
    else:
        k0, k1 = info["kafel_m"]
        s["kafel"] = (k1, k0) if info.get("obrot") else (k0, k1)
    if c.get("szarosc"):
        s["kolor"] = c.get("kolor_plotna", spec.get("kolor", (1, 1, 1)))
    elif "kolor" in c:
        s["kolor"] = c["kolor"]
    s["szorstkosc"] = None
    return s


BEZ_KOLORU_WIERZCHOLKOW = ("zelazo", "zelazo_lufa", "braz", "plotno")


def material_td(nazwa, spec, cc0):
    """Materiał z tekstur td_* (tekstury_deski.py): kolor × mnożnik × kolor wierzchołków 'zabrudzenia' (glTF:
    baseColorTexture, baseColorFactor, COLOR_0), normalne, ORM: G – chropowatość; metaliczność z kanału B tylko dla
    metali (spec['metal']), poza tym 0 bez tekstury (glTF metallicFactor 0)."""
    m = bpy.data.materials.get(nazwa) or bpy.data.materials.new(nazwa)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])
    td = spec["td"]
    ti = nt.nodes.new("ShaderNodeTexImage")
    ti.image = _img(os.path.join(cc0, td + "_kolor.jpg"), False)
    src = ti.outputs["Color"]
    # mnożnik podany w sRGB (jak kolory w arkuszach), węzeł i glTF baseColorFactor są liniowe
    k = tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in spec.get("kolor", (1, 1, 1)))
    if tuple(k) != (1, 1, 1):
        mx = nt.nodes.new("ShaderNodeMix")
        mx.data_type = "RGBA"
        mx.blend_type = "MULTIPLY"
        mx.inputs["Factor"].default_value = 1.0
        nt.links.new(src, mx.inputs[6])
        mx.inputs[7].default_value = (k[0], k[1], k[2], 1.0)
        src = mx.outputs[2]
    if nazwa not in BEZ_KOLORU_WIERZCHOLKOW:
        ca = nt.nodes.new("ShaderNodeVertexColor")
        ca.layer_name = "zabrudzenia"
        mx2 = nt.nodes.new("ShaderNodeMix")
        mx2.data_type = "RGBA"
        mx2.blend_type = "MULTIPLY"
        mx2.inputs["Factor"].default_value = 1.0
        nt.links.new(src, mx2.inputs[6])
        nt.links.new(ca.outputs["Color"], mx2.inputs[7])
        src = mx2.outputs[2]
    nt.links.new(src, bs.inputs["Base Color"])
    tn = nt.nodes.new("ShaderNodeTexImage")
    tn.image = _img(os.path.join(cc0, spec.get("nrm", td) + "_normalne.jpg"), True)
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bs.inputs["Normal"])
    tr = nt.nodes.new("ShaderNodeTexImage")
    tr.image = _img(os.path.join(cc0, spec.get("orm", td) + "_orm.jpg"), True)
    sp = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(tr.outputs["Color"], sp.inputs["Color"])
    nt.links.new(sp.outputs["Green"], bs.inputs["Roughness"])
    if spec.get("metal"):
        nt.links.new(sp.outputs["Blue"], bs.inputs["Metallic"])
    else:
        bs.inputs["Metallic"].default_value = 0.0
    m.diffuse_color = (k[0] * 0.5, k[1] * 0.4, k[2] * 0.3, 1)
    m.use_backface_culling = nazwa not in ("plotno", "szklo")
    return m


def zbuduj(texdir, schemat, cc0=None):
    """cc0 – katalog kopii roboczych tekstur CC0 (tekstury_cc0.py); None – zestaw proceduralny."""
    S = PR.SCHEMATY[schemat]
    burta = {S[r] for r in ("dno", "burta", "bergholt", "burta_gorna", "pas_furt", "listwa", "reling", "pawez") if r in S}
    td_ok = cc0 and os.path.exists(os.path.join(cc0, "_td.json"))
    for nazwa, spec in PR.MATERIALY.items():
        if td_ok and nazwa in PR.MATERIALY_TD:
            st = PR.MATERIALY_TD[nazwa]
            N.MATERIALY_REJESTR[nazwa] = material_td(nazwa, st, cc0)
            N.KAFLE[nazwa] = tuple(st["kafel"])
            continue
        if cc0 and nazwa in PR.MATERIALY_CC0 and PR.MATERIALY_CC0[nazwa].get("wybor", True):
            spec = spec_cc0(nazwa, spec, cc0)
        if nazwa in burta:
            spec = dict(spec, _zabrudzenia=True)          # kolor wierzchołków 'zabrudzenia' (kadlub.zabrudzenia)
        N.MATERIALY_REJESTR[nazwa] = material(nazwa, spec, texdir)
        N.KAFLE[nazwa] = tuple(spec["kafel"])
    # nazwy regionów (malowanie) → materiał wg schematu
    krata(texdir)
    for region, mat in PR.SCHEMATY[schemat].items():
        N.MATERIALY_REJESTR["@" + region] = N.MATERIALY_REJESTR[mat]
        N.KAFLE["@" + region] = N.KAFLE[mat]


def region(nazwa):
    """Nazwa materiału dla regionu malowania (rozwiązywana przy tworzeniu obiektu)."""
    return "@" + nazwa
