"""Rendery EEVEE: woda, niebo, słońce, kamery w układzie statku, ujęcia kontrolne.

Ujęcia są nazwane i opisane w UJECIA (pozycja kamery i cel w układzie statku x, s, z; ogniskowa). Plansza zbiorcza
powstaje osobno (plansza.py, PIL).
"""
import math
import os

import bpy
from mathutils import Vector

from narzedzia import P


def scena(rozdz=(1280, 720), probki=48):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = rozdz
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    try:
        # rendery kontrolne w widoku Standard (bez podbicia kontrastu i nasycenia AgX Punchy) – kolory jak w grze
        sc.view_settings.view_transform = "Standard"
        sc.view_settings.look = "None"
    except Exception:
        pass
    ee = sc.eevee
    for attr, val in (("taa_render_samples", probki), ("use_shadows", True), ("use_raytracing", True),
                      ("shadow_ray_count", 2), ("shadow_step_count", 8), ("use_gtao", True)):
        try:
            setattr(ee, attr, val)
        except Exception:
            pass
    try:
        ee.ray_tracing_options.resolution_scale = "1"
        ee.fast_gi_method = "GLOBAL_ILLUMINATION"
    except Exception:
        pass
    # niebo: gradient od jasnego horyzontu do błękitu w zenicie (bez mgły), słońce osobno
    w = bpy.data.worlds.get("niebo") or bpy.data.worlds.new("niebo")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sx = nt.nodes.new("ShaderNodeSeparateXYZ")
    cr = nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(tc.outputs["Generated"], sx.inputs["Vector"])
    nt.links.new(sx.outputs["Z"], cr.inputs["Fac"])
    el = cr.color_ramp.elements
    el[0].position = 0.0
    el[0].color = (0.80, 0.84, 0.88, 1)
    el[1].position = 0.55
    el[1].color = (0.16, 0.30, 0.62, 1)
    e2 = el.new(0.10)
    e2.color = (0.50, 0.63, 0.82, 1)
    nt.links.new(cr.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.75
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    try:
        sc.view_settings.exposure = -0.2
    except Exception:
        pass
    # słońce
    sun = bpy.data.objects.get("##slonce")
    if sun is None:
        ld = bpy.data.lights.new("##slonce", "SUN")
        sun = bpy.data.objects.new("##slonce", ld)
        sc.collection.objects.link(sun)
    sun.data.energy = 4.5
    sun.data.angle = math.radians(0.8)
    sun.data.color = (1.0, 0.96, 0.9)
    sun.rotation_euler = (math.radians(52), 0, math.radians(215))
    return sc


def _obrys_maski_wody():
    """Obrys maski wody łodzi (węzeł 'lodz_maska_wody') w układzie świata albo None, gdy łodzi nie ma na wodzie."""
    import bmesh
    ob = bpy.data.objects.get("lodz_maska_wody")
    if ob is None or ob.type != "MESH":
        return None
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    brzeg = [e for e in bm.edges if len(e.link_faces) == 1]
    if len(brzeg) < 3:
        bm.free()
        return None
    sasiedzi = {}
    for e in brzeg:
        a, b = e.verts[0].index, e.verts[1].index
        sasiedzi.setdefault(a, []).append(b)
        sasiedzi.setdefault(b, []).append(a)
    bm.verts.ensure_lookup_table()
    start = brzeg[0].verts[0].index
    petla, poprz, akt = [start], None, start
    while len(petla) <= len(brzeg):
        dalej = [i for i in sasiedzi[akt] if i != poprz]
        if not dalej or dalej[0] == start:
            break
        petla.append(dalej[0])
        poprz, akt = akt, dalej[0]
    M = ob.matrix_world
    pts = [M @ bm.verts[i].co for i in petla]
    bm.free()
    if len(pts) < 3 or max(abs(p.z) for p in pts) > 0.05:
        return None
    return pts


def woda(rozmiar=600.0):
    """Tafla wody do rendrów. Gdy łódź stoi na wodzie, tafla ma otwór o obrysie maski wody łodzi: wnętrze łodzi
    leży poniżej wodnicy, więc pełna tafla przecinałaby łódź i wyglądała jak woda w kadłubie."""
    me = bpy.data.meshes.get("##woda")
    if me is None:
        import bmesh
        me = bpy.data.meshes.new("##woda")
        h = rozmiar / 2
        bm = bmesh.new()
        zewn = [bm.verts.new(p) for p in ((-h, -h, 0), (h, -h, 0), (h, h, 0), (-h, h, 0))]
        kraw = [bm.edges.new((zewn[i], zewn[(i + 1) % 4])) for i in range(4)]
        otwor = _obrys_maski_wody()
        if otwor:
            wewn = [bm.verts.new((p.x, p.y, 0.0)) for p in otwor]
            kraw += [bm.edges.new((wewn[i], wewn[(i + 1) % len(wewn)])) for i in range(len(wewn))]
        bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=kraw, normal=(0, 0, 1))
        for f in bm.faces:
            if f.normal.z < 0:
                f.normal_flip()
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new("##woda", me)
        bpy.context.scene.collection.objects.link(ob)
        m = bpy.data.materials.new("##woda")
        m.use_nodes = True
        nt = m.node_tree
        bs = nt.nodes.get("Principled BSDF")
        bs.inputs["Base Color"].default_value = (0.012, 0.045, 0.05, 1)
        bs.inputs["Roughness"].default_value = 0.06
        try:
            bs.inputs["IOR"].default_value = 1.33
        except Exception:
            pass
        tc = nt.nodes.new("ShaderNodeTexCoord")
        ns = nt.nodes.new("ShaderNodeTexNoise")
        ns.inputs["Scale"].default_value = 0.35
        try:
            ns.inputs["Detail"].default_value = 6
        except Exception:
            pass
        bm = nt.nodes.new("ShaderNodeBump")
        bm.inputs["Strength"].default_value = 0.10
        bm.inputs["Distance"].default_value = 0.4
        nt.links.new(tc.outputs["Object"], ns.inputs["Vector"])
        nt.links.new(ns.outputs["Fac"], bm.inputs["Height"])
        nt.links.new(bm.outputs["Normal"], bs.inputs["Normal"])
        me.materials.append(m)
    return bpy.data.objects["##woda"]


def kamera(pos, cel, ogn=35.0, nazwa="##kamera"):
    sc = bpy.context.scene
    cam = bpy.data.objects.get(nazwa)
    if cam is None:
        cam = bpy.data.objects.new(nazwa, bpy.data.cameras.new(nazwa))
        sc.collection.objects.link(cam)
    cam.data.lens = ogn
    cam.data.clip_start = 0.05
    cam.data.clip_end = 2000
    p = P(*pos)
    t = P(*cel)
    cam.location = p
    cam.rotation_euler = (t - p).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    # słońce: zza lewego ramienia kamery, ok. 40° nad horyzontem (obiekt zawsze oświetlony z przodu)
    sun = bpy.data.objects.get("##slonce")
    if sun is not None:
        v = (t - p)
        v.z = 0
        if v.length < 1e-3:
            v = Vector((0, 1, 0))
        v.normalize()
        side = Vector((-v.y, v.x, 0))
        d = (v * 0.75 + side * 0.55)
        d.normalize()
        d = Vector((d.x * 0.72, d.y * 0.72, -0.69))
        sun.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    return cam


def renderuj(sciezka):
    sc = bpy.context.scene
    os.makedirs(os.path.dirname(sciezka), exist_ok=True)
    sc.render.filepath = sciezka
    bpy.ops.render.render(write_still=True)


# ujęcia: nazwa → (pozycja (x, s, z), cel (x, s, z), ogniskowa); x > 0 = lewa burta
def ujecia(ctx):
    d = ctx.get("pokl_z", 1.0)
    q = ctx.get("qd_z", 2.7)
    U = {
        "burta_z_wody": ((12.0, 1.0, 1.4), (0.0, 1.0, 1.2), 24),
        "rufa_z_wody": ((5.0, -27.0, 1.6), (0.0, -14.0, 2.0), 30),
        "dziob_z_wody": ((6.5, 26.0, 1.5), (0.0, 12.5, 1.8), 30),
        "bok_calosc": ((60.0, 0.5, 9.0), (0.0, 0.5, 9.0), 35),
        "z_gory": ((0.0, 0.8, 62.0), (0.0, 0.8, 0.0), 55),
        "poklad_z_rufy": ((0.0, -12.8, q + 3.3), (0.0, 5.0, d), 24),
        "oczy_ku_dziobowi": ((0.6, -1.0, d + 1.6), (0.3, 12.0, d + 1.2), 24),
        "oczy_ku_rufie": ((-0.6, 2.5, d + 1.6), (0.0, -12.0, d + 1.8), 24),
        "deski_zblizenie": ((1.2, 3.0, d + 1.5), (1.6, 4.3, d), 35),
        "pawez_okna": ((3.0, -21.0, 2.8), (0.0, -15.0, 3.0), 45),
        "galion": ((4.5, 19.5, 2.3), (0.0, 14.8, 2.2), 35),
        "dzialo_zblizenie": ((0.3, 2.0, d + 1.5), (2.7, 3.56, d + 0.45), 30),
        "kabestan_zblizenie": ((-2.3, 3.4, d + 1.75), (0.0, 0.95, d + 0.75), 30),
        "lawa_wantowa": ((6.2, -1.6, 2.6), (4.05, -3.1, 2.25), 32),
        "mars_z_gory": ((2.6, -5.4, 17.2), (0.0, -1.55, 13.3), 30),
        "bok_rufy": ((7.5, -6.5, 2.2), (0.0, -10.5, 2.4), 32),
        "manekin_kabestan": ((-1.3, 4.6, d + 1.6), (0.3, 0.9, d + 1.0), 28),
        "manekin_dzialo": ((-0.6, 3.6, d + 1.6), (2.0, 1.2, d + 0.9), 28),
    }
    return U


def manekin(ctx, x, s, yaw, nazwa="##manekin"):
    """Manekin 1,75 m (stopy w (x, s), patrzy w kierunku yaw) – tylko do renderów skali."""
    import narzedzia as N
    from wyposazenie import deck
    z0 = deck(ctx, s, x, qd=s < ctx["K"]["POLPOKLAD_S"])
    sk = N.Siatka(nazwa)
    c = P(x, s, z0)
    for dx in (-0.1, 0.1):
        N.cylinder(sk, c + Vector((dx, 0, 0.0)), c + Vector((dx, 0, 0.86)), 0.07, 0.085, "##manekin", sides=10)
    N.cylinder(sk, c + Vector((0, 0, 0.86)), c + Vector((0, 0, 1.45)), 0.16, 0.19, "##manekin", sides=12)
    for dx in (-0.24, 0.24):
        N.cylinder(sk, c + Vector((dx, 0, 1.42)), c + Vector((dx * 1.1, -0.18, 0.95)), 0.05, 0.045, "##manekin", sides=8)
    N.cylinder(sk, c + Vector((0, 0, 1.45)), c + Vector((0, 0, 1.53)), 0.06, 0.06, "##manekin", sides=8)
    N.lathe(sk, [(0.0, 0.0), (0.08, 0.02), (0.1, 0.11), (0.08, 0.2), (0.0, 0.22)], "##manekin", c + Vector((0, 0, 1.53)),
            sides=12)
    m = bpy.data.materials.get("##manekin") or bpy.data.materials.new("##manekin")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.55, 0.62, 0.7, 1)
    N.MATERIALY_REJESTR["##manekin"] = m
    kol = bpy.context.scene.collection
    ob = N.to_object(sk, kol)
    import math as _m
    ob.rotation_euler = (0, 0, 0)
    N.ustaw_os(ob, c, Vector((0, 0, 1)), Vector((1, 0, 0)))
    ob.rotation_euler = (0, 0, yaw)
    return ob


def plan_tlo(ctx, sciezka):
    """Render ortogonalny z góry (bez drzewc, lin i żagli) jako tło planu pokładu: 2400 × 800, 75 px/m."""
    sc = bpy.context.scene
    hide = [ctx["kol"][k] for k in ("drzewca", "olinowanie", "zagle_zwiniete") if k in ctx["kol"]]
    for c in hide:
        c.hide_render = True
    ro = (sc.render.resolution_x, sc.render.resolution_y)
    sc.render.resolution_x, sc.render.resolution_y = 2400, 800
    cam = bpy.data.objects.get("##plan")
    if cam is None:
        cam = bpy.data.objects.new("##plan", bpy.data.cameras.new("##plan"))
        sc.collection.objects.link(cam)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 32.0
    cam.data.clip_end = 200
    cam.location = (0, 0, 40)
    cam.rotation_euler = (0, 0, -math.pi / 2)
    sc.camera = cam
    sun = bpy.data.objects.get("##slonce")
    if sun is not None:
        sun.rotation_euler = (math.radians(25), math.radians(10), 0)
    renderuj(sciezka)
    for c in hide:
        c.hide_render = False
    sc.render.resolution_x, sc.render.resolution_y = ro


from mathutils import Vector  # noqa: E402


def _S(v):
    return (v[0], -v[1], v[2])


def ujecia_detali(ctx):
    """Kadry kontrolne z bliska (0,5–1,5 m) do przeglądu styków; pozycje liczone z modelu. Wartość:
    (pozycja, cel, ogniskowa[, przygotuj]) – przygotuj() ustawia stan (odrzut, wychylenie steru, wariant)
    i zwraca funkcję przywracającą."""
    from mathutils import Matrix
    import przenikanie as PZ
    import sterowanie
    d = ctx.get("pokl_z", 1.0)
    q = ctx.get("qd_z", 2.7)
    K = ctx["K"]
    ps = ctx["poszycie"]
    U = {}
    g1 = [g for g in ctx.get("dziala", []) if g["side"] > 0]
    if g1:
        g = min(g1, key=lambda g_: abs(g_["s"] - (-1.34)))
        s0, xc, xi = g["s"], g["xc"], g["xi"]
        zd = g["zd"]
        xo, _ = ps.outer(s0, zd + 0.6)
        U["detal_lufa_w_furcie_zewn"] = ((xo + 1.25, s0 - 0.55, zd + 0.95), (xo + 0.2, s0, zd + 0.6), 35)
        U["detal_lufa_w_furcie_wewn"] = ((xc - 0.55, s0 + 0.95, zd + 1.15), (xi - 0.05, s0, zd + 0.62), 30)
        U["detal_laweta_przy_burcie"] = ((xi - 1.05, s0 - 1.0, zd + 0.75), (xi - 0.35, s0, zd + 0.25), 32)
        U["detal_pokrywa_przy_lawie"] = ((xo + 1.5, s0 + 1.3, zd + 0.95), (xo + 0.25, s0, zd + 0.85), 30)
        g2 = [g_ for g_ in g1 if g_ is not g]
        gr = g2[0] if g2 else g

        def odrzut(gr=gr):
            ob = gr["obj"]
            M0 = ob.matrix_world.copy()
            ob.matrix_world = PZ.macierz_dziala(ctx, gr, float(ob.get("odrzut_m", 1.0)))

            def back():
                ob.matrix_world = M0
            return back
        r = float(gr["obj"].get("odrzut_m", 1.0))
        U["detal_dzialo_po_odrzucie"] = ((gr["xc"] - r - 2.1, gr["s"] + 0.9, gr["zd"] + 1.25),
                                         (gr["xc"] - r - 0.7, gr["s"], gr["zd"] + 0.45), 30, odrzut)
    lw = ctx.get("rig", {}).get("lawy", {}).get("grot")
    if lw:
        de = lw["dead"][1]
        U["detal_jufersy_talrepy"] = ((de["x"] + 1.25, de["s"] + 0.9, de["z"] + 0.75), (de["x"], de["s"], de["z"] + 0.3), 35)
    U["detal_luk_krata"] = ((1.15, 5.9, d + 1.05), (0.0, 4.4, d + 0.25), 35)
    U["detal_stopa_masztu_nagielbank"] = ((1.55, -0.15, d + 1.55), (0.0, -1.4, d + 0.55), 28)
    U["detal_kabestan_z_gory"] = ((0.35, 1.55, d + 3.0), (0.0, 0.95, d + 0.6), 30)
    U["detal_kabestan_z_boku"] = ((2.3, 1.6, d + 1.05), (0.0, 0.95, d + 0.6), 30)
    P_ = ctx["PR"].UKLAD["POMPY"]
    U["detal_pompa"] = ((P_["x"] + 1.3, P_["s"] + 1.0, d + 1.45), (P_["x"], P_["s"], d + 0.6), 30)
    kz = ctx.get("kolo")
    if kz:
        sw, za = kz["s"], kz["za"]
        U["detal_kolo_oczy_sternika"] = ((0.45, sw - 0.95, q + 1.62), (0.0, sw + 0.4, za - 0.15), 30)
        U["detal_kolo_z_boku_beben"] = ((1.55, sw + 0.5, za - 0.05), (0.0, sw + 0.45, za - 0.35), 32)
        U["detal_szafka_i_kolo"] = ((1.6, sw - 1.4, q + 1.9), (0.0, sw + 0.6, q + 0.6), 28)
    ster = ctx["obj"].get("ster")

    def wychyl(wariant):
        def prep():
            M0 = ster.matrix_world.copy()
            ster.matrix_world = M0 @ Matrix.Rotation(0.6109, 4, "Z")
            sterowanie.pokaz(ctx, wariant)

            def back():
                ster.matrix_world = M0
                sterowanie.pokaz(ctx, ctx.get("naped_domyslny", "naped_kolo"))
            return back
        return prep
    if ster is not None:
        s_h = ctx["ster_glowica"][0]
        U["detal_rumpel_wychylony"] = ((2.6, s_h + 4.6, q + 2.2), (0.6, s_h + 1.6, q + 0.6), 28, wychyl("naped_rumpel"))
        U["detal_ster_wychylony_z_wody"] = ((-3.4, s_h - 5.0, 0.9), (0.0, s_h - 0.3, 0.3), 30, wychyl("naped_kolo"))
    sq = K["POLPOKLAD_S"]
    U["detal_schody"] = ((1.45, sq + 2.9, d + 1.6), (0.0, sq + 0.6, d + 0.9), 28)
    U["detal_prog_pokladu_rufowego"] = ((2.4, sq + 2.6, d + 2.3), (0.9, sq, d + 1.5), 28)
    import bpy
    lo = bpy.data.objects.get("lodz")
    if lo is not None:
        bb = [lo.matrix_world @ Vector(v) for v in lo.bound_box]
        cc = sum(bb, Vector()) / 8
        c = _S(cc)
        U["detal_wnetrze_lodzi"] = ((c[0] + 1.4, c[1] - 1.8, c[2] + 2.5), (c[0], c[1] + 0.2, c[2] - 0.1), 28)
    kb = ctx.get("kotbelki")
    if kb:
        sg, b1 = [e for e in kb if e[0] > 0][0]
        c = _S(b1)
        U["detal_kotwica_przy_kotbelce"] = ((c[0] + 1.3, c[1] - 1.0, c[2] + 0.35), (c[0] - 0.1, c[1], c[2] - 0.55), 32)
    U["detal_galion_od_dolu"] = ((1.9, 15.6, 0.55), (0.25, 14.1, 2.0), 30)
    U["detal_pawez_ze_sterem"] = ((2.6, -19.8, 2.4), (0.0, -15.0, 2.3), 32)
    t = ctx.get("rig", {}).get("maszty", {}).get("grot", {}).get("top")
    if t:
        U["detal_mars_od_dolu"] = ((1.4, t["c_s"] - 1.3, t["z"] - 1.1), (0.7, t["c_s"] - 0.2, t["z"] + 0.1), 30)
    Y = ctx.get("rig", {}).get("reje", {}).get("grot")
    if Y:
        c = _S(Y["c"])
        h = Y["L"] / 2
        U["detal_nok_rei_perta_bloki"] = ((c[0] + h - 1.1, c[1] + 1.4, c[2] - 0.5), (c[0] + h - 0.4, c[1], c[2] - 0.3), 32)
    return U
