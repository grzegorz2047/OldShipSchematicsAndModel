"""Poziomy szczegółów i bryły kolizji jako osobne pliki GLB obok głównego (wołane z buduj.py po eksporcie).

bryg_lod1.glb  – całość jako jedna siatka (części ruchome w położeniu spoczynkowym), Decimate ok. 50 % trójkątów
bryg_lod2.glb  – bez wyblinek, talrepów, pert, ściągaczy, podwantek, buchty i lin dział; cel Decimate 15 % to
                 górna granica, wynik wychodzi ok. 5–6 % trójkątów pełnego modelu (patrz lod())
bryg_kolizja.glb – proste bryły 'kolizja_*': kadłub (uproszczony), pokład główny i rufowy, nadburcia, maszty,
                   bukszpryt, większe sprzęty z listy przeszkód (działa, kabestan, luki, łódź, pompy, koło …)
"""
import math
import os

import bpy
from mathutils import Vector

import narzedzia as N
from narzedzia import P

POMIN_LOD2 = ("lina_wyblinki", "lina_talrepy", "lina_perty", "lina_sciagacze", "lina_podwantki", "lina_buchty",
              "lina_dziala", "lina_dyn_", "lina_stropy", "lina_ruchome", "lina_kabestan", "lina_lodz", "lina_dzwon",
              "okucia_pokladu", "bloki", "kolkownice", "wyposazenie_drobne", "rak_", "zagiel_", "knagi", "jufersy",
              "lina_talie", "lina_sterlina", "lina_kotwice", "lina_wiazanie", "nagielbank", "szafka", "dzwon",
              "latarnia", "zejsciowka", "kotwica", "pompa", "lodz", "balustrada", "schody", "rufa_rzezby",
              "galion_rzezby", "kolo_sterowe", "kolo_stojaki", "kabestan", "dzialko")


ctx_out = [""]


def _tekstury(maks):
    """Obrazy materiałów zmniejszone do maks px na czas eksportu LOD; zwraca listę do przywrócenia."""
    out = []
    for m in bpy.data.materials:
        if not m.use_nodes:
            continue
        for n in m.node_tree.nodes:
            if n.type == "TEX_IMAGE" and n.image and n.image.size[0] > maks:
                nm = "%s_%d" % (n.image.name.split("_1k")[0], maks)
                im = bpy.data.images.get(nm)
                if im is None:
                    im = n.image.copy()
                    im.name = nm
                    im.scale(maks, maks)
                    im.filepath_raw = os.path.join(ctx_out[0], "tekstury", "%s.jpg" % bpy.path.clean_name(nm))
                    im.file_format = "JPEG"
                    im.save()
                out.append((n, n.image))
                n.image = im
    return out


def _tris(ob):
    ob.data.calc_loop_triangles()
    return len(ob.data.loop_triangles)


def _scal(obs, nazwa, kol):
    bpy.ops.object.select_all(action="DESELECT")
    for c in obs:
        c.select_set(True)
    with bpy.context.temp_override(active_object=obs[0], selected_editable_objects=obs, selected_objects=obs):
        bpy.ops.object.join()
    j = obs[0]
    j.name = nazwa
    j.data.name = nazwa
    return j


def _eksport(obs, sciezka, materialy=True):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=sciezka, export_format="GLB", use_selection=True, export_yup=True,
                              export_apply=True, export_image_format="JPEG", export_texcoords=materialy,
                              export_normals=True, export_materials="EXPORT" if materialy else "NONE",
                              export_extras=True, export_cameras=False, export_lights=False, export_animations=False)
    import eksport
    eksport.spakuj_kolory(sciezka)      # COLOR_0: float → bajty


def lod(ctx, sciezka, cel, pomin=()):
    """cel – górna granica: ułamek trójkątów pełnego modelu (po pominięciu drobnych lin). Przy cel < 0,3 (LOD2) każde
    źródło jest najpierw zmniejszane osobno w dwóch przebiegach, więc wynik wychodzi wyraźnie poniżej celu
    (cel 15 % → ok. 5–6 % trójkątów pełnego modelu)."""
    kol = N.kolekcja("_eksport")
    dg = bpy.context.evaluated_depsgraph_get()
    zrodla = [o for o in ctx["eksport"]["sel"] if o.type == "MESH" and not o.name.startswith(pomin)
              and not (o.get("wariant") and o.get("wariant") != ctx.get("naped_domyslny")) and not o.get("pomocniczy")]
    pelne = sum(_tris(o) for o in ctx["eksport"]["sel"] if o.type == "MESH")
    cps = []
    t_zr = sum(_tris(o) for o in zrodla)
    for o in zrodla:
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
        c = bpy.data.objects.new(o.name + "__lod", me)
        c.matrix_world = o.matrix_world.copy()
        kol.objects.link(c)
        if cel < 0.3 and _tris(c) > 60:
            for _ in range(2):
                m = c.modifiers.new("d", "DECIMATE")
                m.ratio = max(0.03, min(1.0, cel * pelne / max(t_zr, 1)))
                with bpy.context.temp_override(object=c, active_object=c):
                    bpy.ops.object.modifier_apply(modifier=m.name)
        cps.append(c)
    j = _scal(cps, os.path.splitext(os.path.basename(sciezka))[0], kol)
    t0 = _tris(j)
    ratio = min(1.0, cel * pelne / max(t0, 1))
    if cel < 0.3:
        # LOD2: każde źródło zmniejszane osobno przed scaleniem (Decimate na całości zatrzymuje się na wyspach)
        pass
    for _ in range(3):                 # kilka przebiegów: jeden Decimate zatrzymuje się na drobnych wyspach
        m = j.modifiers.new("decimate", "DECIMATE")
        m.ratio = max(0.05, min(1.0, cel * pelne / max(_tris(j), 1)))
        m.use_collapse_triangulate = True
        with bpy.context.temp_override(object=j, active_object=j):
            bpy.ops.object.modifier_apply(modifier=m.name)
        if _tris(j) <= cel * pelne * 1.05:
            break
    t1 = _tris(j)
    przyw = _tekstury(1024 if cel >= 0.3 else 512)        # LOD1 – tekstury 1K, LOD2 – 512 px
    _eksport([j], sciezka)
    for n, im in przyw:
        n.image = im
    wynik = dict(plik=os.path.basename(sciezka), bajty=os.path.getsize(sciezka), trojkaty=t1, pelny_model=pelne,
                 udzial=round(t1 / pelne, 3))
    bpy.data.objects.remove(j, do_unlink=True)
    return wynik


def kolizja(ctx, sciezka):
    kol = N.kolekcja("_eksport")
    if "kolizja" not in N.MATERIALY_REJESTR:
        N.MATERIALY_REJESTR["kolizja"] = bpy.data.materials.get("kolizja") or bpy.data.materials.new("kolizja")
        N.KAFLE["kolizja"] = (1.0, 1.0)
    kd, K = ctx["kd"], ctx["K"]
    ps = ctx["poszycie"]
    obs = []

    def nowy(sk, nazwa, **ex):
        o = N.to_object(sk, kol, recalc=True)
        o.name = nazwa
        for k, v in ex.items():
            o[k] = v
        obs.append(o)
        return o
    # kadłub uproszczony (zamknięta powłoka, ok. 1500 trójkątów)
    h = ctx["obj"]["kadlub"]
    c = h.copy()
    c.data = h.data.copy()
    kol.objects.link(c)
    m = c.modifiers.new("decimate", "DECIMATE")
    m.ratio = 1500 / max(_tris(h), 1)
    with bpy.context.temp_override(object=c, active_object=c):
        bpy.ops.object.modifier_apply(modifier=m.name)
    c.name = "kolizja_kadlub"
    c.data.materials.clear()
    obs.append(c)
    # pokłady: płyty 0,05 m z wielokątów chodzenia
    for pw in ctx.get("chodzenie_json", {}).get("powierzchnie", [])[:2]:
        sk = N.Siatka("kolizja_" + pw["nazwa"])
        lift = K["POLPOKLAD_H"] if pw["poziom"] == "rufowy" else 0.0
        top = [P(x, s, float(kd.deck_c(s)) + lift) for (x, s) in pw["wielokat"]]
        vt = sk.verts(top)
        vb = sk.verts([p + Vector((0, 0, -0.05)) for p in top])
        sk.face_proj(vt[::-1], "kolizja", flat=True)
        sk.face_proj(vb, "kolizja", flat=True)
        for i in range(len(vt)):
            j = (i + 1) % len(vt)
            sk.face_proj([vt[i], vt[j], vb[j], vb[i]], "kolizja", flat=True)
        nowy(sk, "kolizja_" + pw["nazwa"])
    # nadburcia: belki co ok. 2 m od pokładu do wierzchu pokrywy relingu
    for side, tag in ((1, "L"), (-1, "P")):
        sk = N.Siatka("kolizja_nadburcie_" + tag)
        ss = [s for s in range(int(ps.ra[ps.r_top]) + 1, int(ps.rf[ps.r_top]) - 1, 2)]
        for a, b in zip(ss[:-1], ss[1:]):
            za = float(ps.Zd((a + b) / 2)) + (K["POLPOKLAD_H"] if (a + b) / 2 < K["POLPOKLAD_S"] else 0.0)
            zt = ps.rail_top((a + b) / 2) + K["RELING_GR"]
            xa, _ = ps.outer(a, zt - 0.1)
            xb, _ = ps.outer(b, zt - 0.1)
            pa, pb = P(side * (xa - 0.1), a, (za + zt) / 2), P(side * (xb - 0.1), b, (za + zt) / 2)
            N.oriented_box(sk, pa, pb, 0.22, zt - za, "kolizja")
        nowy(sk, "kolizja_nadburcie_" + tag)
    # maszty i bukszpryt: walce 8-boczne
    for key, R_ in ctx["rig"]["maszty"].items():
        mm = R_.get("m")
        if mm is None or not hasattr(mm, "p"):
            continue
        sk = N.Siatka("kolizja_maszt_" + key)
        N.cylinder(sk, mm.p(mm.z_d), mm.p(mm.z_top), mm.r(mm.z_d), mm.r(mm.z_top), "kolizja", sides=8)
        nowy(sk, "kolizja_maszt_" + key)
    bs = ctx["rig"].get("bukszpryt")
    if bs:
        sk = N.Siatka("kolizja_bukszpryt")
        N.cylinder(sk, bs["path"][0], bs["path"][-1], bs["r0"], bs["r0"] * 0.6, "kolizja", sides=8)
        nowy(sk, "kolizja_bukszpryt")
    # większe sprzęty z listy przeszkód (prostopadłościany / walce na pokładzie)
    from wyposazenie import deck
    ile = {}
    for o in ctx.get("przeszkody", []):
        ile[o["nazwa"]] = ile.get(o["nazwa"], 0) + 1
    for o in ctx.get("przeszkody", []):
        if o["h"] < 0.3 or o["nazwa"].startswith(("kolkownica", "maszt")):
            continue
        qd = o["poziom"] == "rufowy"
        z0 = deck(ctx, o["s"], o["x"], qd=qd)
        # dwie przeszkody o tej samej nazwie (kojce na obu burtach): przyrostek burty zamiast '.001' Blendera
        nz = o["nazwa"] + (("_L" if o["x"] > 0 else "_P") if ile[o["nazwa"]] > 1 else "")
        sk = N.Siatka("kolizja_" + nz)
        if o["typ"] == "kolo":
            N.cylinder(sk, P(o["x"], o["s"], z0), P(o["x"], o["s"], z0 + o["h"]), o["wym"], o["wym"], "kolizja", sides=8)
        else:
            dl, sz = o["wym"]
            N.box(sk, P(o["x"], o["s"], z0 + o["h"] / 2), (sz, dl, o["h"]), "kolizja",
                  rot=__import__("mathutils").Matrix.Rotation(o.get("rot", 0.0), 3, "Z"))
        ex = {"wariant": o["wariant"]} if o.get("wariant") else {}
        nowy(sk, "kolizja_" + nz, **ex)
    for o in obs:
        o.data.materials.clear()
    _eksport(obs, sciezka, materialy=False)
    wynik = dict(plik=os.path.basename(sciezka), bajty=os.path.getsize(sciezka), bryly=len(obs),
                 trojkaty=sum(_tris(o) for o in obs))
    for o in obs:
        bpy.data.objects.remove(o, do_unlink=True)
    return wynik


def zbuduj(ctx, glb):
    d = os.path.dirname(glb)
    ctx_out[0] = ctx["out"]
    w = dict(lod1=lod(ctx, os.path.join(d, "bryg_lod1.glb"), 0.5),
             lod2=lod(ctx, os.path.join(d, "bryg_lod2.glb"), 0.15, POMIN_LOD2),
             kolizja=kolizja(ctx, os.path.join(d, "bryg_kolizja.glb")))
    ctx["lod"] = w
    print("LOD " + str(w))
    return w
