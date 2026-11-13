"""Wyposażenie pokładu (rozdział 09 przewodnika): działa na lawetach (lufa osobno, oś w czopach), kabestan (bęben z drągami
osobno), pompy wiązowe z dźwigniami, luki ze zrębnicami i kratami, nagielbanki i kołkownice z kołkami i buchtami,
sterowanie (sterowanie.py: koło albo rumpel), szafka kompasowa, dzwon w ramie, zejściówka, jol na legarach, kotwice (lewa na kotbelce,
prawa rzucona – lina z kluzy do wody), działka relingowe, komin kambuza, beczka, kojce, skrzynia z bronią, stojaki
na kule.

Każdy przedmiot zapisuje przeszkodę (ctx['przeszkody']) i stanowiska czynności (ctx['stanowiska']) – z nich
chodzenie.py robi bryg_poklad.json i puste obiekty stan_*.
"""
import math

import numpy as np
from mathutils import Matrix, Vector

import narzedzia as N
from narzedzia import P


def przeszkoda(ctx, nazwa, obiekt, typ, s, x, wym, h, poziom="glowny", rot=0.0, chodzic=False, prog=None, wariant=None):
    ctx.setdefault("przeszkody", []).append(dict(nazwa=nazwa, obiekt=obiekt, typ=typ, s=s, x=x, wym=wym, h=h,
                                                 poziom=poziom, rot=rot, chodzic=chodzic, prog=prog, wariant=wariant))


def stanowisko(ctx, czynnosc, s, x, z, patrz_s, patrz_x, obiekt=None, os=None, zakres=None, h_rak=1.0, liny=None,
               opis=None, wariant=None):
    lst = ctx.setdefault("stanowiska", [])
    nr = 1 + sum(1 for t in lst if t["czynnosc"] == czynnosc)
    yaw = math.atan2(patrz_x, patrz_s)
    lst.append(dict(nazwa="stan_%s_%d" % (czynnosc, nr), czynnosc=czynnosc, s=s, x=x, z=z, yaw=yaw, obiekt=obiekt,
                    os=os, zakres=zakres, h_rak=h_rak, liny=liny or [], opis=opis, wariant=wariant))


def deck(ctx, s, x, qd=None):
    kd, K = ctx["kd"], ctx["K"]
    if qd is None:
        qd = s < K["POLPOKLAD_S"]
    return float(kd.deck_z(s, x)) + (K["POLPOKLAD_H"] if qd else 0.0)


def inner_x(ctx, s, qd=False):
    from poklad import inner_at
    ps = ctx["poszycie"]
    (x, _, _), _, _ = inner_at(ps, ps.r_qd if qd else ps.r_deck, s)
    return x


def burta_min_x(ctx, s0, s1, z0, z1, n=9):
    """Najmniejsze x wewnętrznej powierzchni nadburcia (lewa burta) w prostokącie s0…s1 × z0…z1 – do ustawiania
    przedmiotów przy burcie z uwzględnieniem zawalenia burt (tumblehome) i zbiegania się burt ku dziobowi."""
    ps = ctx["poszycie"]
    best = min(ps.inner(s, z)[0] for s in np.linspace(s0, s1, n) for z in np.linspace(z0, z1, 5))
    # siatka nadburcia od środka (rzędy od pokładu w górę; przesunięcie w rzucie zmienia też s – ważne przy dziobie)
    c1 = ps.c_in1
    for r in range(ps.r_deck, ps.xin.shape[0]):
        ss, xs, zs = ps.sin[r, :c1 + 1], ps.xin[r, :c1 + 1], ps.zin[r, :c1 + 1]
        for s in np.linspace(s0, s1, n):
            z = float(np.interp(s, ss, zs))
            if z0 - 0.05 <= z <= z1 + 0.1:
                best = min(best, float(np.interp(s, ss, xs)))
    return best


def deck_max(ctx, s0, s1, x0, x1, qd=None):
    """Najwyższy punkt pokładu pod prostokątem (wypukłość i wznios) – przedmiot stawiany na nim nie wnika w deski."""
    return max(deck(ctx, s, x, qd=qd) for s in np.linspace(s0, s1, 5) for x in np.linspace(x0, x1, 5))


def poza_dziala(ctx, side, s0, xc):
    """Położenie lawety o czopach w odległości xc od osi: oba koła stoją na wypukłym pokładzie (pochylenie lawety
    wzdłuż osi lufy = spadek pokładu między osiami kół, luz 1,5 mm). Zwraca (location, rotation_euler)."""
    U = ctx["PR"].UKLAD["DZIALA"]
    xf_l = 0.42
    xw_f, r_f = xf_l - 0.2, 0.2                    # osie kół w układzie lawety (jak w laweta_mesh)
    xw_r, r_r = xf_l - U["lawa_dl"] + 0.2, 0.18
    w = U["lawa_szer"] / 2 + 0.07                   # koła na s0 ± w
    Df = [deck(ctx, s0 + d, side * (xc + xw_f)) for d in (-w, w)]
    Dr = [deck(ctx, s0 + d, side * (xc + xw_r)) for d in (-w, w)]
    p = (sum(Dr) - sum(Df)) / 2 / (xw_f - xw_r)     # rad, przód (ku burcie) niżej (wypukłość pokładu)
    q = ((Df[1] + Dr[1]) - (Df[0] + Dr[0])) / 2 / (2 * w)   # wznios pokładu wzdłuż okrętu
    roll = -side * q                                # lokalna +Y = ku rufie (lewa burta) / ku dziobowi (prawa)
    # luz 1,5 mm pod najniższym wierzchołkiem koła (wielokąt: dół koła leży ctx['_laweta_zmin'] nad osią z = 0)
    z0 = sum(Df) / 2 + xw_f * p + 0.0015 + r_f * (1 - math.cos(p)) - ctx.get("_laweta_zmin", 0.0)
    return P(side * xc, s0, z0), (roll, p, 0.0 if side > 0 else math.pi)


# ================================================================ działo
def lufa_mesh(sk, L=2.0):
    """Lufa wzdłuż +X od czopów (x = 0): profil (x, r) od gałki do wylotu, z przewodem."""
    a = 0.92                       # czopy 0,92 m od dna lufy
    prof = [(-a - 0.14, 0.0), (-a - 0.14, 0.03), (-a - 0.10, 0.045), (-a - 0.07, 0.03), (-a - 0.035, 0.05),
            (-a - 0.01, 0.15), (-a, 0.168), (-a + 0.05, 0.168), (-a + 0.06, 0.158), (-0.30, 0.152), (-0.28, 0.163),
            (-0.24, 0.163), (-0.22, 0.148), (0.25, 0.140), (0.27, 0.152), (0.31, 0.152), (0.33, 0.136),
            (L - a - 0.16, 0.112), (L - a - 0.10, 0.118), (L - a - 0.05, 0.132), (L - a - 0.015, 0.132),
            (L - a, 0.12), (L - a, 0.047), (L - a - 0.35, 0.047), (L - a - 0.35, 0.0)]
    N.lathe(sk, [(r, x) for (x, r) in prof], "zelazo", Vector((0, 0, 0)), axis=Vector((1, 0, 0)), sides=16,
            close_ends=False)
    for sg in (1, -1):
        N.cylinder(sk, Vector((0, sg * 0.13, 0)), Vector((0, sg * 0.235, 0)), 0.046, 0.046, "zelazo", sides=10)
    # otwór zapałowy (ciemna kropka) i delfiny nie w tej epoce
    N.cylinder(sk, Vector((-a + 0.08, 0, 0.16)), Vector((-a + 0.08, 0, 0.172)), 0.012, 0.012, "drewno_czarne",
               sides=6)


def laweta_mesh(sk, U):
    """Laweta wzdłuż +X (przód = ku furcie), środek osi lufy w (0, 0, os_lufy) nad pokładem; czopy w x = 0."""
    L, W, h = U["lawa_dl"], U["lawa_szer"], U["os_lufy"]
    xf = 0.42                     # przód lawety przed czopami
    xb = xf - L
    th = 0.10
    # policzki ze stopniami z tyłu (widok z boku: x, z)
    prof = [(xb, 0.14), (xf, 0.14), (xf, h - 0.02), (xf - 0.30, h - 0.02), (xf - 0.38, h - 0.10), (xf - 0.5, h - 0.10),
            (xf - 0.5, h - 0.2), (xf - 0.82, h - 0.2), (xf - 0.82, h - 0.29), (xb + 0.08, h - 0.29),
            (xb, h - 0.35)]
    for sg in (1, -1):
        y0 = sg * (W / 2 - th / 2) - th / 2
        y1 = y0 + th
        vb = [sk.vert((x, y0, z)) for (x, z) in prof]
        vt = [sk.vert((x, y1, z)) for (x, z) in prof]
        n = len(prof)
        sk.face_proj(vb[::-1], "laweta", axis=1)
        sk.face_proj(vt, "laweta", axis=1)
        for i in range(n):
            j = (i + 1) % n
            sk.face_proj([vb[i], vb[j], vt[j], vt[i]], "laweta")
        # wycięcie czopu: obejma (cap square) żelazna
        N.box(sk, (0.0, sg * (W / 2 - th / 2), h + 0.03), (0.14, th + 0.01, 0.025), "zelazo")
        # ucha na liny
        for (x, z) in ((xf - 0.2, 0.32), (xb + 0.25, 0.3)):
            N.lathe(sk, [(0.03, -0.01), (0.04, 0.0), (0.03, 0.01)], "zelazo", Vector((x, sg * (W / 2 + 0.005), z)),
                    axis=Vector((0, sg, 0)), sides=8)
    # poprzeczka, osie, koła
    N.box(sk, (xf - 0.06, 0, h - 0.17), (0.12, W - 2 * th, 0.30), "laweta")
    for (x, r) in ((xf - 0.2, 0.2), (xb + 0.2, 0.18)):
        N.box(sk, (x, 0, r), (0.13, W + 0.12, 0.13), "laweta")
        for sg in (1, -1):
            c = Vector((x, sg * (W / 2 + 0.07), r))
            N.lathe(sk, [(0.0, -0.045), (r, -0.045), (r, 0.045), (0.0, 0.045)], "drewno_ciemne", c,
                    axis=Vector((0, 1, 0)), sides=22, uv_obwod=True)
            N.cylinder(sk, c + Vector((0, sg * 0.045, 0)), c + Vector((0, sg * 0.075, 0)), 0.03, 0.03, "zelazo",
                       sides=6)
    # ława i klin pod dnem lufy
    N.box(sk, (xb + 0.35, 0, h - 0.27), (0.5, W - 2 * th - 0.02, 0.06), "laweta")
    q = [Vector((xb + 0.15, -0.12, h - 0.24)), Vector((xb + 0.55, -0.12, h - 0.24)), Vector((xb + 0.55, -0.12, h - 0.18)),
         Vector((xb + 0.15, -0.12, h - 0.13))]
    v0 = sk.verts(q)
    v1 = sk.verts([p + Vector((0, 0.24, 0)) for p in q])
    sk.face_proj(v0[::-1], "drewno")
    sk.face_proj(v1, "drewno")
    for i in range(4):
        j = (i + 1) % 4
        sk.face_proj([v0[i], v0[j], v1[j], v1[i]], "drewno")


def dziala(ctx):
    K = ctx["K"]
    U = ctx["PR"].UKLAD["DZIALA"]
    kol = ctx["kol"]["wyposazenie"]
    ps = ctx["poszycie"]
    import bpy
    ph = ctx.get("dzialo_polyhaven")
    if ph:
        mesh_l, mesh_b, os_lufy = dzialo_polyhaven(ctx, ph)
        U = dict(U, os_lufy=os_lufy)
    else:
        # wspólne siatki (instancje): laweta i lufa
        sk = N.Siatka("dzialo_laweta")
        laweta_mesh(sk, U)
        me_l = N.to_object(sk, kol, recalc=True)
        me_l.data.set_sharp_from_angle(angle=math.radians(35))
        mesh_l = me_l.data
        bpy_remove(me_l)
        ctx["_laweta_zmin"] = min(v.co.z for v in mesh_l.vertices)
        sk = N.Siatka("dzialo_lufa")
        lufa_mesh(sk, U["lufa"])
        me_b = N.to_object(sk, kol, recalc=True)
        me_b.data.set_sharp_from_angle(angle=math.radians(30))
        mesh_b = me_b.data
        bpy_remove(me_b)
    guns = []
    nr = 0
    for s0 in sorted(K["FURTY_S"]):
        if any(abs(s0 - b) < 0.05 for b in U["bez_dziala"]):
            continue
        for side, tag in ((1, "L"), (-1, "P")):
            nr += 1
            xi = inner_x(ctx, s0)
            # przód lawety tuż przed ściekiem (ściek 0,25 m) i 3 cm od nadburcia na całej wysokości lawety
            # (zawalenie burt, zwężenie ku dziobowi) – w obrysie kół i policzków s0 ± 0,55 m
            zd0 = deck(ctx, s0, side * (xi - 0.6))
            xb_min = burta_min_x(ctx, s0 - 0.55, s0 + 0.55, zd0, zd0 + U["os_lufy"] + 0.05)
            xf = min(xi - 0.27, xb_min - 0.03)
            xc = xf - 0.42                          # czopy
            name = "dzialo_%s%d" % (tag, (nr + 1) // 2)
            ob = bpy.data.objects.new(name, mesh_l)
            kol.objects.link(ob)
            ob.location, ob.rotation_euler = poza_dziala(ctx, side, s0, xc)
            zd = ob.location.z
            ob["odrzut_m"] = U["odrzut"]
            ob["os_ruchu"] = "lokalna -X (wzdłuż lufy, do środka okrętu)"
            lb = bpy.data.objects.new(name + "_lufa", mesh_b)
            kol.objects.link(lb)
            lb.parent = ob
            lb.location = (0, 0, U["os_lufy"])
            lb["os_ruchu"] = "obrót wokół lokalnej Y (podniesienie lufy, ok. −5…+10°)"
            guns.append(dict(obj=ob, lufa=lb, s=s0, side=side, xc=xc, xf=xf, zd=zd, xi=xi))
            # przeszkoda: laweta + lufa wewnątrz okrętu; po odrzucie przesunięta o 1,5 m
            L_in = U["lawa_dl"]
            przeszkoda(ctx, name, name, "prostokat", s0, side * (xf - L_in / 2), (U["lawa_szer"] + 0.15, L_in), 0.95)
            # stanowiska obsługi (rozdział 09: 6 ludzi i chłopiec)
            xb = xf - U["lawa_dl"]
            pos = [("dzialo_kapitan", xb - 0.75, 0.55, 1, 0), ("dzialo_ladowniczy", xf - 0.35, 0.78, 0, -1),
                   ("dzialo_wyciorowy", xf - 0.35, -0.78, 0, 1), ("dzialo_talia", xb + 0.25, 0.9, 0.7, -0.7),
                   ("dzialo_talia", xb + 0.25, -0.9, 0.7, 0.7), ("dzialo_odciag", xb - 0.6, -0.55, 1, 0),
                   ("dzialo_chlopiec", xb - 1.6, 0.0, 1, 0)]
            for (cz, xx, ds, px, ps_) in pos:
                stanowisko(ctx, cz, s0 + ds * (1 if side > 0 else -1), side * xx, deck(ctx, s0, side * xx),
                           ps_ * (1 if side > 0 else -1), side * px, obiekt=name, os="lokalna -X: odrzut",
                           zakres=[0.0, U["odrzut"]], h_rak=0.75 if cz != "dzialo_kapitan" else 1.0)
            stanowisko(ctx, "furta", s0 - 0.62, side * (xi - 0.45), deck(ctx, s0 - 0.62, side * (xi - 0.45)),
                       0, side, obiekt="furta_pokrywa_%s%d" % (tag, sorted(K["FURTY_S"] + K.get("FURTY_ZAMKNIETE_S", [])).index(s0) + 1),
                       os="lokalna Z (zawias)", zakres=[0, 100], h_rak=1.2)
    ctx["dziala"] = guns
    # liny przy wybranych działach: lina hamująca, talie boczne, talia odciągowa
    from olinowanie import lina
    for g in guns:
        if not any(abs(g["s"] - s_) < 0.05 for s_ in U["z_linami"]):
            continue
        side, s0, xf, zd = g["side"], g["s"], g["xf"], g["zd"]
        hw = K["FURTA_SZER"] / 2 + 0.17
        ob = g["obj"]
        Mg = Matrix.Translation(ob.location) @ ob.rotation_euler.to_matrix().to_4x4()

        def Lg(lx, ds, lz):
            """Punkt w układzie lawety: lx wzdłuż lufy (+ ku burcie), ds wzdłuż okrętu (+ ku dziobowi)."""
            return Mg @ Vector((lx, -side * ds, lz))
        casc = Lg(-0.92 - 0.14, 0.0, U["os_lufy"])
        zb = deck(ctx, s0, side * (g["xi"] - 0.3))
        rb = [N_ring(ctx, s0 + d, zb + 0.52, side) for d in (-hw, hw)]     # nad kołami (wierzch kół 0,40 m)
        # lina hamująca: z pierścienia przy burcie po zewnętrznej stronie policzka, nad tylnym kołem, wokół gałki
        # (końce na lawecie – lina dynamiczna: od pierścienia w burcie do działa)
        for sg, r in ((-1, rb[0]), (1, rb[1])):
            pts = [r, Lg(-0.30, sg * 0.50, 0.46), Lg(-0.95, sg * 0.46, 0.52), casc + (Lg(0, sg * 0.07, 0) - Lg(0, 0, 0))]
            lina(ctx, "dziala", pts, 0.045, "lina_jasna", do=ob.name)
        # talie boczne: ucho w burcie nad pierścieniem → ucho w policzku lawety
        for sg in (-1, 1):
            a = N_ring(ctx, s0 + sg * hw, zb + 0.64, side)
            b = Lg(0.22, sg * 0.435, 0.32)
            for off in (-0.018, 0.018):
                lina(ctx, "dziala", [a + Vector((0, 0, off)), b + Vector((0, 0, off))], 0.016, "lina_jasna", do=ob.name)
            blok(ctx, a.lerp(b, 0.18), (b - a).normalized(), 0.13)
            blok(ctx, a.lerp(b, 0.55), (b - a).normalized(), 0.13)
        # zwój liny na pokładzie za działem
        zwoj(ctx, P(side * (xf - U["lawa_dl"] - 0.55), s0 + 0.6, zd + 0.01), 0.22, 0.018)
    return guns


def dzialo_polyhaven(ctx, sciezka):
    """Wariant działa z Poly Haven (cannon_01, CC0) wczytany ze ścieżki podanej argumentem: lufa i laweta
    jako osobne siatki w naszym układzie działa (czopy w początku, lufa ku +X, pokład z = 0), skala do lufy ok. 2,0 m,
    tekstury zmniejszone do 2K (JPEG w <out>/tekstury/polyhaven_*). Niczego nie kopiuje do katalogu skryptów."""
    import os
    import bpy
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=sciezka)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = {o.name: o for o in new if o.type == "MESH"}
    for o in meshes.values():
        for m in list(o.modifiers):
            o.modifiers.remove(m)
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
        o.data.transform(o.matrix_world)
        o.matrix_world = Matrix.Identity(4)
    piv = Vector((0.0, -0.425, 0.607))               # kość ctrl_barrel = czopy
    s = 2.0 / 2.225
    M = Matrix.Rotation(math.pi / 2, 4, "Z") @ Matrix.Scale(s, 4) @ Matrix.Translation(-Vector((0, piv.y, 0)))
    lufa = meshes["cannon_01_barrel"]
    lufa.data.transform(Matrix.Translation(Vector((0, 0, -piv.z * s))) @ M)
    parts = [meshes[n] for n in meshes if n.startswith(("cannon_01_frame", "cannon_01_wheel", "cannon_01_pusherblock"))]
    for o in parts:
        o.data.transform(M)
    bpy.ops.object.select_all(action="DESELECT")
    for o in parts:
        o.select_set(True)
    with bpy.context.temp_override(active_object=parts[0], selected_editable_objects=parts, selected_objects=parts):
        bpy.ops.object.join()
    lawa = parts[0]
    # tekstury 4K → 2K JPEG
    td = os.path.join(ctx["out"], "tekstury")
    for img in list(bpy.data.images):
        if not img.name.startswith("cannon_01"):
            continue
        if img.size[0] > 2048:
            img.scale(2048, 2048)
        nm = "polyhaven_" + img.name.replace(".", "_")
        p = os.path.join(td, nm + ".jpg")
        img.filepath_raw = p
        img.file_format = "JPEG"
        img.save(filepath=p, quality=92 if "nor" in img.name else 88)
        img.filepath = p
    mesh_l, mesh_b = lawa.data, lufa.data
    mesh_l.name, mesh_b.name = "dzialo_laweta_polyhaven", "dzialo_lufa_polyhaven"
    for o in new:
        try:
            bpy.data.objects.remove(o, do_unlink=True)
        except ReferenceError:
            pass
    return mesh_l, mesh_b, piv.z * s


def bpy_remove(ob):
    import bpy
    bpy.data.objects.remove(ob)


_RINGS = []


def N_ring(ctx, s, z, side, odst=0.075):
    """Śruba oczkowa w nadburciu od środka na (s, z): trzpień wpuszczony w burtę (zakryty), pierścień w płaszczyźnie
    pionowej prostopadłej do burty, środek pierścienia odst od powierzchni. Zwraca środek pierścienia (świat)."""
    ps = ctx["poszycie"]
    sk = ctx.setdefault("_sk_drobne", N.Siatka("okucia_pokladu"))
    xw, _ = ps.inner(s, z)
    c = P(side * (xw - odst), s, z)
    N.cylinder(sk, P(side * (xw + 0.03), s, z), P(side * (xw - odst + 0.05), s, z), 0.014, 0.014, "zelazo", sides=8)
    N.lathe(sk, [(0.04, -0.011), (0.051, 0.0), (0.04, 0.011), (0.029, 0.0)], "zelazo", c, axis=Vector((0, 1, 0)),
            sides=12, close_ends=False)
    return c


def blok(ctx, c, d, L, strop=None, strop_do=None):
    """Blok (jednokrążkowy): korpus wzdłuż d. Blok trafia do rejestru siatki (sk.bloki); przed zamianą siatki
    w obiekt stropy_blokow() dorabia strop każdemu blokowi, który niczego nie dotyka. strop – punkt, przez który
    strop ma iść (np. ucho w ławie wantowej pod blokiem talii), gdy najbliższa część nie jest właściwym zaczepem;
    strop_do – prefiksy nazw części, na których strop ma się wtedy kończyć (gdy są w zasięgu)."""
    sk = ctx.setdefault("_sk_bloki", N.Siatka("bloki"))
    d = Vector(d).normalized()
    # 6 boków, 4 pasy (runda 2e: bloków olinowania ruchomego jest kilkaset – budżet GLB)
    N.lathe(sk, [(0.0, -L / 2), (L * 0.28, -L * 0.42), (L * 0.36, 0.0), (L * 0.28, L * 0.42), (0.0, L / 2)],
            "drewno_ciemne", c, axis=d, sides=6)
    if not hasattr(sk, "bloki"):
        sk.bloki = []
    sk.bloki.append(dict(c=Vector(c), d=d, L=L, przez=None if strop is None else Vector(strop), do_pref=strop_do))


STROP_D = 0.014          # m: średnica stropu bloku (lina smołowana)
STROP_MAKS = 1.2         # m: najdalej tyle od bloku szukamy zaczepu


def _promien_bloku(b, u):
    """Odległość od środka bloku do jego powierzchni w kierunku u (elipsoida wpisana w korpus: 0,30 L w poprzek,
    0,48 L wzdłuż osi) – ostrożnie, żeby 'dotyka' znaczyło rzeczywisty styk z drewnem bloku."""
    t = abs(u.dot(b["d"]))
    a_, c_ = 0.30 * b["L"], 0.48 * b["L"]
    return 1.0 / math.sqrt((1 - t * t) / (a_ * a_) + (t * t) / (c_ * c_))


def stropy_blokow(ctx, sk, wariant=None):
    """Bloki z rejestru siatki sk, które niczego nie dotykają (wiszą obok masztu, pod marsem, obok sztagu), dostają
    strop: smołowaną linkę od korpusu do najbliższej części konstrukcji (drzewce, kadłub, okucia, jufersy) albo liny
    stałej (sztag, wanta, padun). Blok jest podparty bez stropu, gdy styka się z bryłą, kończy się na nim
    smołowany wisior (wisior brasu) albo jest blokiem przelotowym napiętej talii (lina przechodzi przez niego na
    wprost). Strop jest częścią siatki bloków (nie liną z rejestru – rejestr lin i dane
    publiczne bez zmian). Wynik w ctx['stropy_blokow'] (lista) i ctx['bloki_bez_zaczepu'] (powinna być pusta)."""
    import bpy
    from mathutils.bvhtree import BVHTree
    bloki = [b for b in getattr(sk, "bloki", []) if not b.get("sprawdzony")]
    if not bloki:
        return []
    cs = [b["c"] for b in bloki]
    lo = Vector([min(c[i] for c in cs) - STROP_MAKS for i in range(3)])
    hi = Vector([max(c[i] for c in cs) + STROP_MAKS for i in range(3)])
    bryly = []
    for o in bpy.data.objects:
        if o.type != "MESH" or not len(o.data.polygons) or \
                o.name.startswith(("lina_", "##", "bloki", "zagiel", "lodz_maska")):
            continue
        if o.users_collection and o.users_collection[0].name in ("_eksport", "stanowiska"):
            continue
        if o.get("wariant"):
            if o.get("wariant") != wariant:
                continue                    # część wariantu napędu steru: zaczep tylko dla bloków tego wariantu
        elif o.hide_render:
            continue
        bb = [o.matrix_world @ Vector(v) for v in o.bound_box]
        if any(max(v[i] for v in bb) < lo[i] or min(v[i] for v in bb) > hi[i] for i in range(3)):
            continue
        me = o.data
        M = o.matrix_world
        bryly.append((o.name, BVHTree.FromPolygons([M @ v.co for v in me.vertices],
                                                   [tuple(p.vertices) for p in me.polygons]),
                      Vector([min(v[i] for v in bb) for i in range(3)]),
                      Vector([max(v[i] for v in bb) for i in range(3)])))
    liny = ctx.get("liny", [])
    stale = [L for L in liny if L["g"].startswith(("sztagi", "wanty", "paduny", "podwantki"))]

    kier_par = [Vector((1, 0.013, 0.007)).normalized(), Vector((0.011, 1, 0.017)).normalized(),
                Vector((0.009, 0.015, 1)).normalized()]

    def w_bryle(p):
        """Punkt w środku zamkniętej bryły (parzystość przecięć trzech półprostych) – blok schowany, niewidoczny."""
        for nm, tr, blo, bhi in bryly:
            if any(p[i] < blo[i] or p[i] > bhi[i] for i in range(3)):
                continue
            g = 0
            for dv in kier_par:
                n_, o_ = 0, Vector(p)
                for _ in range(64):
                    hit = tr.ray_cast(o_, dv)
                    if hit[0] is None:
                        break
                    n_ += 1
                    o_ = hit[0] + dv * 1e-5
                g += n_ & 1
            if g >= 2:
                return nm
        return None

    def do_bryly(p, zasieg, pref=None):
        best = None
        for nm, tr, blo, bhi in bryly:
            if pref and not nm.startswith(pref):
                continue
            if any(p[i] < blo[i] - zasieg or p[i] > bhi[i] + zasieg for i in range(3)):
                continue
            loc, nrm, idx, dist = tr.find_nearest(p, zasieg)
            if loc is not None and (best is None or dist < best[0]):
                best = (dist, loc, nm)
        return best

    def do_liny_stalej(p, zasieg):
        best = None
        for L in stale:
            for a, b in zip(L["p"][:-1], L["p"][1:]):
                ab = b - a
                t = max(0.0, min(1.0, (p - a).dot(ab) / max(1e-9, ab.length_squared)))
                q = a + ab * t
                dist = (q - p).length - L["d"] / 2
                if dist <= zasieg and (best is None or dist < best[0]):
                    best = (dist, q, "lina:" + L["g"])
        return best

    def w_talii(b):
        """Lina z rejestru przechodzi przez blok na wprost (bez załamania), wzdłuż jego osi: blok przelotowy talii
        (talie boczne dział, talie rumpla). Trzyma go napięta talia między dwoma zamocowanymi końcami; strop do
        lawety zatrzymywałby odrzut działa (blok jest stały, laweta ruchoma)."""
        c = b["c"]
        ile = 0
        for L in liny:
            pts = L["p"]
            if len(pts) < 2 or (L.get("wariant") and L.get("wariant") != wariant):
                continue
            for a_, b_ in zip(pts[:-1], pts[1:]):
                ab = b_ - a_
                dl = ab.length
                if dl < 2 * b["L"]:
                    continue
                t = (c - a_).dot(ab) / (dl * dl)
                if t * dl < b["L"] or (1 - t) * dl < b["L"]:
                    continue                # blok przy końcu odcinka: lina się tu kończy albo załamuje
                if (a_ + ab * t - c).length <= 0.3 * b["L"] and abs(ab.normalized().dot(b["d"])) > 0.9:
                    ile += 1
                    break
        # talia ma co najmniej dwie liny w bloku; jedna obca lina przechodząca przypadkiem przez korpus (fał gafla
        # obok bloku fału marsrei) to nie talia
        return ile >= 2

    def na_wisiorze(b):
        """Smołowana lina z rejestru (wisior brasu, strop) kończąca się przy bloku – blok na niej wisi. Lina ruchoma
        przechodząca przez blok albo kończąca się na nim bloku nie trzyma: blok kierujący musi mieć zaczep do
        konstrukcji (inaczej wisi w powietrzu, trzymany tylko przez linę, której kierunek zmienia)."""
        c = b["c"]
        zas = b["L"] * 0.5 + 0.03
        for L in liny:
            pts = L["p"]
            if L["m"] != "lina_smolowana" or len(pts) < 2 or (L.get("wariant") and L.get("wariant") != wariant):
                continue
            if L["g"].startswith(("sztagi", "wanty", "paduny", "podwantki")):
                continue                    # liny stałe są zaczepem stropu (niżej), nie wisiorem bloku
            if (pts[0] - c).length <= zas or (pts[-1] - c).length <= zas:
                return True
        return False
    wynik = []
    for b in bloki:
        b["sprawdzony"] = True
        c = b["c"]
        ukryty = w_bryle(c)
        if ukryty:                          # np. krążki sterliny pod pokładem rufowym, póki kadłub nie ma wnętrza
            b["ukryty_w"] = ukryty
            continue
        nb = do_bryly(c, STROP_MAKS)
        if b["przez"] is None:
            if nb is not None and nb[0] > 1e-6 and nb[0] <= _promien_bloku(b, (nb[1] - c).normalized()):
                continue                    # korpus styka się z bryłą
            if nb is not None and nb[0] <= 1e-6:
                continue
            if na_wisiorze(b):
                continue
            if w_talii(b):
                b["w_talii"] = True
                continue
            nl = do_liny_stalej(c, 0.6)
            kand = [k for k in (nb, nl) if k is not None]
            if not kand:
                ctx.setdefault("bloki_bez_zaczepu", []).append([round(v, 3) for v in N.S(c)])
                continue
            dist, q, nm = min(kand, key=lambda k: k[0])
            # 2 cm w głąb bryły (strop obłożony na części); przy linie stałej – do jej osi
            kotw = q if nm.startswith("lina:") else q + (q - c).normalized() * 0.02
            sciezka = [kotw]
        else:
            p = b["przez"]
            nb2 = (do_bryly(p, 0.8, tuple(b["do_pref"])) if b.get("do_pref") else None) or do_bryly(p, 0.6)
            if nb2 is None:
                ctx.setdefault("bloki_bez_zaczepu", []).append([round(v, 3) for v in N.S(c)])
                continue
            dist, q, nm = nb2
            kier = (q - p).normalized() if dist > 1e-4 else (p - c).normalized()
            sciezka = ([p] if dist > 0.03 else []) + [q + kier * 0.02]
        u = (sciezka[0] - c).normalized()
        start = c + u * min(_promien_bloku(b, u) * 0.8, (sciezka[0] - c).length * 0.5)
        pts = [start] + sciezka
        N.tube(sk, pts, STROP_D / 2, "lina_smolowana", sides=5, cap=True, rope=True)
        dl = sum((b_ - a_).length for a_, b_ in zip(pts[:-1], pts[1:]))
        b["kotwica"], b["do"] = sciezka[-1], nm
        wynik.append(dict(blok=[round(v, 3) for v in N.S(c)], do=nm, dlugosc_m=round(dl, 3)))
    ctx.setdefault("stropy_blokow", []).extend(wynik)
    ctx.setdefault("bloki_rejestr", []).extend(dict(b, wariant=wariant) for b in bloki)
    return wynik


def zwoj(ctx, c, r, d, mat="lina_jasna", n=4):
    """Zwój liny leżący na pokładzie (kilka okręgów)."""
    from olinowanie import lina
    for k in range(n):
        rr = r - k * d * 1.05
        pts = [Vector(c) + Vector((rr * math.cos(t), rr * math.sin(t), d * 0.5 + 0.004 * k)) for t in
               np.linspace(0, 2 * math.pi, 15)]
        lina(ctx, "buchty", pts, d, mat)


def buchta(ctx, c, h, d=0.02, mat="lina_jasna"):
    """Buchta zawieszona na kołku: kilka wydłużonych pętli w płaszczyźnie (y, z)."""
    from olinowanie import lina
    c = Vector(c)
    for k in range(4):
        w = 0.07 + 0.012 * k
        pts = []
        for t in np.linspace(0, 2 * math.pi, 13):
            pts.append(c + Vector((0.006 * k, w * math.sin(t), -h * 0.5 * (1 - math.cos(t)))))
        lina(ctx, "buchty", pts, d, mat)


# ================================================================ kabestan
def kabestan(ctx):
    U = ctx["PR"].UKLAD["KABESTAN"]
    kol = ctx["kol"]["wyposazenie"]
    s0 = U["s"]
    zd = deck(ctx, s0, 0.0)
    c = P(0, s0, zd)
    # podstawa (stała): wieniec zapadkowy (pierścień na pokładzie) z zębami i trzy zapadki na słupkach
    sk = N.Siatka("kabestan_podstawa")
    N.lathe(sk, [(0.34, 0.0), (0.58, 0.0), (0.58, 0.10), (0.55, 0.12), (0.37, 0.12), (0.34, 0.10)], "drewno_ciemne", c,
            sides=32)
    for k in range(16):
        t = 2 * math.pi * k / 16
        q = Matrix.Rotation(t, 3, "Z")
        N.box(sk, c + q @ Vector((0.47, 0, 0.135)), (0.14, 0.05, 0.03), "zelazo", rot=q)
    for t in (0.35, 0.35 + 2 * math.pi / 3, 0.35 + 4 * math.pi / 3):
        post = c + Vector((0.68 * math.cos(t), 0.68 * math.sin(t), 0.0))
        N.box(sk, post + Vector((0, 0, 0.08)), (0.09, 0.09, 0.16), "drewno_ciemne", rot=Matrix.Rotation(t, 3, "Z"))
        tip = c + Vector((0.51 * math.cos(t + 0.22), 0.51 * math.sin(t + 0.22), 0.165))
        N.oriented_box(sk, post + Vector((0, 0, 0.165)), tip, 0.04, 0.03, "zelazo")
    N.to_object(sk, kol, recalc=True)
    # bęben (ruchomy): rdzeń ośmioboczny, 8 klinowatych żeber (whelps), wstawki między żebrami (chocks)
    sk = N.Siatka("kabestan_beben")
    zt0, zt1 = U["h"] - 0.23, U["h"]                 # głowica
    # rdzeń bębna (16 boków): żebra dosunięte do ścian (≤ 4 mm), rdzeń 4 mm w głowicy – bez części wkładanych
    N.lathe(sk, [(0.0, 0.005), (0.26, 0.005), (0.26, zt0 + 0.004), (0.0, zt0 + 0.004)], "drewno", c, sides=16)
    for k in range(8):
        t = 2 * math.pi * k / 8
        d = Vector((math.cos(t), math.sin(t), 0))
        sd = Vector((-d.y, d.x, 0)) * 0.045
        prof = [(0.256, 0.17), (0.40, 0.19), (0.40, 0.30), (0.36, zt0 - 0.06), (0.36, zt0), (0.256, zt0)]
        v0 = sk.verts([c + d * r + Vector((0, 0, z)) - sd for (r, z) in prof])
        v1 = sk.verts([c + d * r + Vector((0, 0, z)) + sd for (r, z) in prof])
        sk.face_proj(v0[::-1], "drewno")
        sk.face_proj(v1, "drewno")
        for i in range(len(prof)):
            j = (i + 1) % len(prof)
            sk.face_proj([v0[i], v0[j], v1[j], v1[i]], "drewno")
        # wstawka między tym a następnym żebrem
        t2 = t + math.pi / 8
        d2 = Vector((math.cos(t2), math.sin(t2), 0))
        N.box(sk, c + d2 * 0.30 + Vector((0, 0, 0.55)), (0.08, 0.15, 0.12), "drewno_ciemne",
              rot=Matrix.Rotation(t2, 3, "Z"))
    # głowica: okrągła, dwie żelazne obręcze, gniazda drągów
    rh = U["r_glowica"]
    N.lathe(sk, [(0.0, zt0), (rh - 0.02, zt0), (rh, zt0 + 0.02), (rh, zt1 - 0.02), (rh - 0.02, zt1), (0.0, zt1)],
            "drewno", c, sides=32)
    for zz in (zt0 + 0.035, zt1 - 0.035):
        N.lathe(sk, [(rh, zz - 0.022), (rh + 0.008, zz - 0.02), (rh + 0.008, zz + 0.02), (rh, zz + 0.022)], "zelazo", c,
                sides=32, close_ends=False)
    N.lathe(sk, [(0.0, zt1), (0.09, zt1), (0.08, zt1 + 0.03), (0.04, zt1 + 0.05), (0.0, zt1 + 0.055)], "drewno_ciemne",
            c, sides=12)
    zb = U["h_draga"]
    for k in range(U["dragi"]):
        t = 2 * math.pi * k / U["dragi"] + math.pi / U["dragi"]
        d = Vector((math.cos(t), math.sin(t), 0))
        q = Matrix.Rotation(t, 3, "Z")
        # gniazdo: ciemna ramka na obwodzie głowicy; drąg zaczyna się na powierzchni głowicy (3 mm w głąb) –
        # gniazda nie są modelowane jako otwory, więc drąg nie jest w nie wpuszczony
        N.box(sk, c + d * (rh + 0.004) + Vector((0, 0, zb)), (0.008, 0.11, 0.11), "drewno_czarne", rot=q)
        # drąg (rozdział 09: kwadratowe otwory głowicy): przy głowicy przekrój kwadratowy 0,10 m z małą fazą – wypełnia
        # gniazdo 0,11 m; pierwsza trzecia długości bez zmian, dalej zwęża się ku końcowi zewnętrznemu (0,62),
        # koniec tępy z fazą (nie szpic)
        r0, r1 = rh - 0.003, U["r_draga"] - 0.008
        rs = [r0, r0 + 0.33 * (r1 - r0), r0 + 0.55 * (r1 - r0), r0 + 0.78 * (r1 - r0), r1 - 0.014, r1]
        path = [c + d * r + Vector((0, 0, zb)) for r in rs]
        sc = [1.0, 1.0, 0.86, 0.72, 0.62, 0.48]
        h_, f_ = 0.05, 0.011
        kw = [(h_, -h_ + f_), (h_, h_ - f_), (h_ - f_, h_), (-h_ + f_, h_), (-h_, h_ - f_), (-h_, -h_ + f_),
              (-h_ + f_, -h_), (h_ - f_, -h_)]
        N.sweep(sk, path, kw, "drewno", scale=sc, up=Vector((0, 0, 1)))
    ob = N.to_object(sk, kol, recalc=True)
    ob.data.set_sharp_from_angle(angle=math.radians(35))
    N.ustaw_os(ob, c, Vector((0, 0, 1)), Vector((1, 0, 0)))
    ob["os_ruchu"] = "obrót wokół lokalnej Z (pion), bez ograniczeń"
    # linka (swifter) przez końce drągów
    from olinowanie import lina
    pts = []
    for k in range(U["dragi"] + 1):
        t = 2 * math.pi * k / U["dragi"]
        pts.append(c + Vector((math.cos(t), math.sin(t), 0)) * (U["r_draga"] - 0.06) + Vector((0, 0, U["h_draga"] + 0.05)))
    lina(ctx, "kabestan", pts, 0.022, "lina_jasna", parent=ob)
    przeszkoda(ctx, "kabestan", "kabestan_beben", "kolo", s0, 0.0, U["r_glowica"] + 0.05, U["h"])
    ctx["kabestan_kolo"] = dict(s=s0, x=0.0, r=U["r_draga"])
    for k in range(U["dragi"]):
        t = 2 * math.pi * k / U["dragi"] + math.pi / U["dragi"] * 0
        rr = U["r_draga"] - 0.25
        # człowiek przy drągu: z boku drąga, patrzy w kierunku obrotu (zgodnie z ruchem wskazówek zegara z góry)
        px, ps_ = rr * math.cos(t) * 1.0, rr * math.sin(t)
        # styczna w układzie Blendera (x, y = −s) dla obrotu zgodnego z ruchem wskazówek zegara widzianego z góry
        # (wcześniej znak był odwrócony: stanowiska patrzyły przeciwnie do opisu w rozdziale 09)
        fwd = (math.sin(t), -math.cos(t))
        # Blender (x, y) → statek (x, s = −y)
        sx, ss = px, -ps_
        ft_x, ft_s = fwd[0], -fwd[1]
        stanowisko(ctx, "kabestan", s0 + ss + 0.0, sx + 0.0, deck(ctx, s0 + ss, sx), ft_s, ft_x, obiekt="kabestan_beben",
                   os="lokalna Z (pion)", zakres=None, h_rak=U["h_draga"] + 0.02)
    return ob


# ================================================================ pompy
def pompy(ctx):
    U = ctx["PR"].UKLAD["POMPY"]
    kol = ctx["kol"]["wyposazenie"]
    for side, tag in ((1, "L"), (-1, "P")):
        s0, x0 = U["s"], side * U["x"]
        zd = deck(ctx, s0, x0)
        c = P(x0, s0, zd)
        sk = N.Siatka("pompa_" + tag)
        r = U["r"]
        N.lathe(sk, [(0.0, 0.0), (r + 0.03, 0.0), (r + 0.03, 0.06), (r, 0.08), (r, U["h"] - 0.08), (r + 0.025, U["h"] - 0.06),
                     (r + 0.025, U["h"]), (0.0, U["h"])], "drewno", c, sides=8)
        for z in (0.25, 0.55, 0.85):
            N.lathe(sk, [(r + 0.002, z - 0.025), (r + 0.012, z - 0.02), (r + 0.012, z + 0.02), (r + 0.002, z + 0.025)],
                    "zelazo", c, sides=8, close_ends=False)
        # wylew (dala) w bok, do ścieku
        N.oriented_box(sk, c + Vector((side * r * 0.8, 0, U["h"] - 0.25)), c + Vector((side * (r + 0.55), 0, U["h"] - 0.4)),
                       0.1, 0.08, "drewno")
        # widełki dźwigni
        for dy in (-0.05, 0.05):
            N.box(sk, c + Vector((0, dy, U["h"] + 0.12)), (0.04, 0.02, 0.24), "zelazo")
        N.to_object(sk, kol, recalc=True)
        # dźwignia (brake) – obiekt ruchomy, oś w widełkach (poprzecznie)
        sk = N.Siatka("pompa_%s_dzwignia" % tag)
        L = U["dzwignia"]
        piv = c + Vector((0, 0, U["h"] + 0.2))
        # dźwignia ku dziobowi (Blender −Y): ku rufie wchodziła w gródź pokładu rufowego
        N.oriented_box(sk, piv + Vector((0, 0.35, 0)), piv + Vector((0, -(L - 0.35), -0.02)), 0.07, 0.07, "drewno")
        N.oriented_box(sk, piv + Vector((-0.25, -(L - 0.38), -0.02)), piv + Vector((0.25, -(L - 0.38), -0.02)), 0.045,
                       0.045, "drewno")
        N.cylinder(sk, piv + Vector((0, 0.25, 0)), piv + Vector((0, 0.25, -0.8)), 0.02, 0.02, "zelazo", sides=6)
        ob = N.to_object(sk, kol, recalc=True)
        N.ustaw_os(ob, piv, Vector((1, 0, 0)), Vector((0, 1, 0)))
        ob["os_ruchu"] = "obrót wokół lokalnej Z (poprzecznie), wahanie ±%d°" % U["wahanie"]
        # dźwignia wystaje ku dziobowi od pompy o L − 0.35
        przeszkoda(ctx, "pompa_" + tag, "pompa_" + tag, "kolo", s0, x0, r + 0.04, U["h"])
        przeszkoda(ctx, "pompa_%s_dzwignia" % tag, ob.name, "prostokat", s0 + (L - 0.7) / 2, x0, (L, 0.12), U["h"] + 0.2)
        stanowisko(ctx, "pompa", s0 + (L - 0.38) + 0.35, x0, deck(ctx, s0 + L, x0), -1, 0, obiekt=ob.name,
                   os="lokalna Z (poprzecznie)", zakres=[-U["wahanie"], U["wahanie"]], h_rak=U["h"] + 0.2)
        stanowisko(ctx, "pompa", s0 + (L - 0.38), x0 + side * 0.45, deck(ctx, s0 + L - 0.4, x0), 0, -side,
                   obiekt=ob.name, os="lokalna Z (poprzecznie)", zakres=[-U["wahanie"], U["wahanie"]],
                   h_rak=U["h"] + 0.2)


# ================================================================ luki
def luk(ctx, nazwa, s0, s1, hx, h, krata=True):
    kol = ctx["kol"]["wyposazenie"]
    sk = N.Siatka(nazwa)
    sc = (s0 + s1) / 2
    zd = deck(ctx, sc, 0.0)
    L = s1 - s0
    t = 0.11
    for (cx, cs, w, l) in ((hx + t / 2, sc, t, L + 2 * t), (-hx - t / 2, sc, t, L + 2 * t), (0, s1 + t / 2, 2 * hx, t),
                           (0, s0 - t / 2, 2 * hx, t)):
        N.box(sk, P(cx, cs, zd + h / 2 - 0.02), (w, l, h + 0.04), "drewno_ciemne")
    if krata:
        # krata: płyta 0,035 m z obrazem listew (alfa – oczka przezroczyste); listwy jako bryły dawały ponad
        # 25 tys. trójkątów-igieł na dwa luki, płyta ma 12 na luk (porównanie z bliska: detal_luk_krata)
        zt = zd + h - 0.035
        N.box(sk, P(0, sc, zt + 0.0175), (2 * hx, L, 0.035), "krata")
        N.box(sk, P(0, sc, zt - 0.05), (0.08, L, 0.08), "drewno")       # wzdłużnik pod kratą
    ob = N.to_object(sk, kol, recalc=True)
    przeszkoda(ctx, nazwa, nazwa, "prostokat", sc, 0.0, (L + 2 * t, 2 * hx + 2 * t), h, chodzic=krata, prog=h)
    return ob


# ================================================================ nagielbanki i kołkownice
def nagielbank(ctx, key):
    U = ctx["PR"].UKLAD["NAGIELBANK"]
    D = ctx["PR"].DRZEWCA
    kol = ctx["kol"]["wyposazenie"]
    s0 = D[("FOK" if key == "fok" else "GROT") + "_S"]
    if key == "grot" and ctx["snow"]:
        s0 -= D["SNOW_ODSTEP"] / 2
    a = U["pol"]
    zd = deck(ctx, s0, 0.0)
    sk = N.Siatka("nagielbank_" + key)
    corners = [(-a, -a), (a, -a), (a, a), (-a, a)]
    for (x, s) in corners:
        N.box(sk, P(x, s0 + s, zd + U["h"] / 2), (0.14, 0.14, U["h"]), "drewno_ciemne")
        N.lathe(sk, [(0.08, 0), (0.09, 0.04), (0.05, 0.1), (0.0, 0.12)], "drewno_ciemne", P(x, s0 + s, zd + U["h"]),
                sides=8)
    pins = []
    for i in range(4):
        (x0, s_0), (x1, s_1) = corners[i], corners[(i + 1) % 4]
        if i == 1 and key == "fok":
            pass
        N.oriented_box(sk, P(x0, s0 + s_0, zd + U["h"] - 0.1), P(x1, s0 + s_1, zd + U["h"] - 0.1), 0.13, 0.11,
                       "drewno_ciemne")
        n = int(round(2 * a / U["kolki_co"]))
        for k in range(1, n):
            f = k / n
            x = x0 + (x1 - x0) * f
            s = s_0 + (s_1 - s_0) * f
            p = P(x, s0 + s, zd + U["h"] - 0.04)
            N.cylinder(sk, p + Vector((0, 0, -0.16)), p + Vector((0, 0, 0.16)), 0.017, 0.017, "drewno", sides=6)
            N.lathe(sk, [(0.0, 0.0), (0.03, 0.0), (0.03, 0.03), (0.0, 0.05)], "drewno", p + Vector((0, 0, 0.16)), sides=6)
            pins.append((x, s0 + s, zd + U["h"]))
    N.to_object(sk, kol, recalc=True)
    przeszkoda(ctx, "nagielbank_" + key, "nagielbank_" + key, "prostokat", s0, 0.0, (2 * a + 0.14, 2 * a + 0.14), U["h"])
    return pins


def kolkownice(ctx):
    U = ctx["PR"].UKLAD
    kol = ctx["kol"]["wyposazenie"]
    sk = N.Siatka("kolkownice")
    pins_all = []
    for (s0, s1) in U["KOLKOWNICE"]:
        for side in (1, -1):
            ss = np.arange(s0, s1 + 1e-6, 0.1)
            pw_ = ctx["K"]["PILERS"][1]

            def xr(s):
                zd_ = deck(ctx, s, side * (inner_x(ctx, s) - 0.2))
                xw = min(inner_x(ctx, s), burta_min_x(ctx, s - 0.06, s + 0.06, zd_ + U["KOLKOWNICA_H"] - 0.08,
                                                       zd_ + U["KOLKOWNICA_H"] + 0.08, n=3))
                return xw - pw_ - 0.075 + 0.004
            for i in range(len(ss) - 1):
                xa = xr(ss[i])
                xb = xr(ss[i + 1])
                za = deck(ctx, ss[i], side * xa) + U["KOLKOWNICA_H"]
                zb = deck(ctx, ss[i + 1], side * xb) + U["KOLKOWNICA_H"]
                N.oriented_box(sk, P(side * xa, ss[i], za), P(side * xb, ss[i + 1], zb), 0.15, 0.12, "drewno_ciemne")
            for s in np.arange(s0 + 0.15, s1 - 0.05, 0.2):
                x = xr(s)
                z = deck(ctx, s, side * x) + U["KOLKOWNICA_H"]
                p = P(side * x, s, z)
                N.cylinder(sk, p + Vector((0, 0, -0.2)), p + Vector((0, 0, 0.16)), 0.0175, 0.0175, "drewno", sides=6)
                N.lathe(sk, [(0.0, 0.0), (0.03, 0.0), (0.03, 0.03), (0.0, 0.05)], "drewno", p + Vector((0, 0, 0.16)),
                        sides=6)
                pins_all.append((side * x, s, z))
            sm = (s0 + s1) / 2
            przeszkoda(ctx, "kolkownica", "kolkownice", "prostokat", sm, side * (inner_x(ctx, sm) - 0.19),
                       (s1 - s0, 0.18), U["KOLKOWNICA_H"] + 0.1)
    N.to_object(sk, kol, recalc=True)
    return pins_all


# ================================================================ rumpel, szafka, dzwon, zejściówka
def szafka(ctx):
    U = ctx["PR"].UKLAD["SZAFKA_KOMPASOWA"]
    kol = ctx["kol"]["wyposazenie"]
    s0 = U["s"]
    w, g, h = U["szer"], U["gl"], U["h"]
    zq = deck_max(ctx, s0 - g / 2, s0 + g / 2, -w / 2, w / 2, qd=True) + 0.001
    sk = N.Siatka("szafka_kompasowa")
    # cokół i korpus z desek (słoje wzdłuż desek: UV pudeł wzdłuż najdłuższej osi)
    N.box(sk, P(0, s0, zq + 0.04), (w + 0.06, g + 0.06, 0.08), "drewno_ciemne")
    N.box(sk, P(0, s0 + 0.02, zq + 0.08 + (h - 0.08) / 2), (w, g - 0.04, h - 0.08), "drewno_ciemne")
    N.box(sk, P(0, s0, zq + h + 0.02), (w + 0.08, g + 0.08, 0.04), "drewno_ciemne")
    # dach dwuspadowy z dwóch desek i kalenicy
    for sg in (1, -1):
        a = P(sg * (w / 2 + 0.05), s0, zq + h + 0.05)
        b = P(0, s0, zq + h + 0.16)
        N.oriented_box(sk, a, b, g + 0.12, 0.025, "drewno_ciemne", up=Vector((0, 0, 1)))
    N.box(sk, P(0, s0, zq + h + 0.165), (0.05, g + 0.12, 0.04), "drewno")
    # przegrody (trzy komory) i drzwiczki z szybkami od strony sternika (rufa)
    fy = s0 - g / 2 + 0.01
    for xx in (-w / 2 + 0.02, -w / 6, w / 6, w / 2 - 0.02):
        N.box(sk, P(xx, fy - 0.012, zq + 0.08 + (h - 0.08) / 2), (0.04, 0.025, h - 0.08), "drewno")
    for xx in (-w / 3, 0.0, w / 3):
        dw = w / 3 - 0.06
        for (zz, hh) in ((zq + 0.12, 0.03), (zq + h - 0.06, 0.03), (zq + 0.43, 0.025)):
            N.box(sk, P(xx, fy - 0.014, zz), (dw, 0.02, hh), "drewno")
        q = [P(xx - dw / 2, fy - 0.006, zq + 0.45), P(xx + dw / 2, fy - 0.006, zq + 0.45),
             P(xx + dw / 2, fy - 0.006, zq + h - 0.075), P(xx - dw / 2, fy - 0.006, zq + h - 0.075)]
        v = sk.verts(q)
        sk.face(v[::-1], [(0, 0), (1, 0), (1, 1), (0, 1)], "szklo", flat=True)
        q = [P(xx - dw / 2, fy - 0.006, zq + 0.135), P(xx + dw / 2, fy - 0.006, zq + 0.135),
             P(xx + dw / 2, fy - 0.006, zq + 0.415), P(xx - dw / 2, fy - 0.006, zq + 0.415)]
        # płycina dolna: cienka deska (bryła zamknięta), tył schowany w korpusie
        N.box(sk, P(xx, fy + 0.011, zq + 0.275), (dw, 0.038, 0.28), "drewno_ciemne")
        N.cylinder(sk, P(xx + dw / 2 - 0.03, fy - 0.01, zq + 0.42), P(xx + dw / 2 - 0.03, fy - 0.03, zq + 0.42),
                   0.008, 0.01, "braz", sides=6)
    N.to_object(sk, kol, recalc=True)
    przeszkoda(ctx, "szafka_kompasowa", "szafka_kompasowa", "prostokat", s0, 0.0, (g, w), h, poziom="rufowy")
    stanowisko(ctx, "kompas", s0 - g / 2 - 0.5, 0.0, deck(ctx, s0 - 0.7, 0, qd=True), 1, 0, obiekt="szafka_kompasowa",
               h_rak=h)


def dzwon(ctx):
    U = ctx["PR"].UKLAD["DZWON"]
    kol = ctx["kol"]["wyposazenie"]
    s0, x0 = U["s"], U["x"]
    zq = deck_max(ctx, s0 - 0.08, s0 + 0.08, x0 - 0.33, x0 + 0.33, qd=True) + 0.001
    sk = N.Siatka("dzwon_rama")
    for dx in (-0.28, 0.28):
        N.box(sk, P(x0 + dx, s0, zq + 0.45), (0.1, 0.12, 0.9), "drewno_ciemne")
    N.box(sk, P(x0, s0, zq + 0.93), (0.75, 0.16, 0.1), "drewno_ciemne")
    # daszek: dwie deski 25 mm (bryły zamknięte) zamiast pojedynczych ścian
    for sg in (1, -1):
        N.oriented_box(sk, P(x0, s0 + sg * 0.15, zq + 0.975), P(x0, s0 - sg * 0.01, zq + 1.105), 0.84, 0.025,
                       "drewno_ciemne", up=Vector((0, 0, 1)))
    N.to_object(sk, kol, recalc=True)
    sk = N.Siatka("dzwon")
    c = P(x0, s0, zq + 0.88)
    r = U["r"]
    N.lathe(sk, [(0.0, 0.0), (0.03, 0.0), (r * 0.55, -0.02), (r * 0.62, -0.08), (r * 0.7, -0.16), (r * 0.95, -0.24),
                 (r, -0.27), (r * 0.9, -0.27), (r * 0.62, -0.17), (0.0, -0.16)], "braz", c, sides=20)
    N.cylinder(sk, c + Vector((0, 0, -0.15)), c + Vector((0, 0, -0.28)), 0.012, 0.012, "zelazo", sides=6)
    N.lathe(sk, [(0.0, -0.33), (0.028, -0.31), (0.03, -0.28), (0.0, -0.26)], "zelazo", c, sides=8)
    ob = N.to_object(sk, kol, recalc=True)
    N.ustaw_os(ob, c, Vector((0, 1, 0)), Vector((1, 0, 0)))
    ob["os_ruchu"] = "wahanie wokół lokalnej Z (wzdłuż okrętu)"
    from olinowanie import lina
    lina(ctx, "dzwon", [c + Vector((0, 0, -0.3)), c + Vector((0, 0.25, -0.55))], 0.014, "lina_jasna")
    przeszkoda(ctx, "dzwon", "dzwon_rama", "prostokat", s0, x0, (0.2, 0.75), 1.1, poziom="rufowy")
    stanowisko(ctx, "dzwon", s0 - 0.55, x0, deck(ctx, s0 - 0.55, x0, qd=True), 1, 0, obiekt="dzwon",
               os="lokalna Z", zakres=[-30, 30], h_rak=1.2)


def zejsciowka(ctx):
    U = ctx["PR"].UKLAD["ZEJSCIOWKA"]
    kol = ctx["kol"]["wyposazenie"]
    s0, s1, hx, h = U["s0"], U["s1"], U["pol_x"], U["h"]
    sc = (s0 + s1) / 2
    zq = deck(ctx, sc, 0.0, qd=True)
    sk = N.Siatka("zejsciowka")
    t = 0.07
    for (cx, cs, w, l, hh) in ((hx, sc, t, s1 - s0, h), (-hx, sc, t, s1 - s0, h), (0, s0, 2 * hx, t, h)):
        N.box(sk, P(cx, cs, zq + hh / 2), (w, l, hh), "drewno_ciemne")
    # daszek łukowy i przesuwna klapa, drzwiczki od dziobu (otwarte w głąb)
    pts = []
    for k in range(9):
        t_ = math.pi * k / 8
        pts.append((-math.cos(t_) * (hx + 0.04), h + 0.1 * math.sin(t_)))
    # daszek jako bryła zamknięta: łuk zewnętrzny, wewnętrzny 25 mm niżej, czoła i krawędzie podłużne
    gr = 0.025
    for i in range(len(pts) - 1):
        (xa, za), (xb, zb) = pts[i], pts[i + 1]
        q = [P(xa, s0 - 0.04, zq + za), P(xb, s0 - 0.04, zq + zb), P(xb, s1 + 0.04, zq + zb), P(xa, s1 + 0.04, zq + za)]
        sk.face_proj(sk.verts(q), "drewno_ciemne")
        q = [P(xa, s0 - 0.04, zq + za - gr), P(xa, s1 + 0.04, zq + za - gr), P(xb, s1 + 0.04, zq + zb - gr),
             P(xb, s0 - 0.04, zq + zb - gr)]
        sk.face_proj(sk.verts(q), "drewno_ciemne")
        for s_, odw in ((s0 - 0.04, False), (s1 + 0.04, True)):
            q = [P(xa, s_, zq + za), P(xa, s_, zq + za - gr), P(xb, s_, zq + zb - gr), P(xb, s_, zq + zb)]
            sk.face_proj(sk.verts(q[::-1] if odw else q), "drewno_ciemne")
    for (xe, ze), odw in ((pts[0], False), (pts[-1], True)):
        q = [P(xe, s0 - 0.04, zq + ze), P(xe, s1 + 0.04, zq + ze), P(xe, s1 + 0.04, zq + ze - gr),
             P(xe, s0 - 0.04, zq + ze - gr)]
        sk.face_proj(sk.verts(q[::-1] if odw else q), "drewno_ciemne")
    N.box(sk, P(0, s1 + 0.02, zq + 0.12), (2 * hx, 0.05, 0.24), "drewno_ciemne")
    # drabina w dół (widoczne 3 stopnie)
    for k in range(3):
        N.box(sk, P(0, s0 + 0.35 + k * 0.22, zq - 0.25 - k * 0.25), (2 * hx - 0.1, 0.18, 0.04), "drewno")
    N.to_object(sk, kol, recalc=True)
    przeszkoda(ctx, "zejsciowka", "zejsciowka", "prostokat", sc, 0.0, (s1 - s0 + 0.1, 2 * hx + 0.1), h, poziom="rufowy")
    ctx.setdefault("przejscia", []).append(dict(nazwa="zejsciowka_kabina", typ="schody_w_dol", s0=s1, s1=s0 + 0.3,
                                                x0=-hx + 0.05, x1=hx - 0.05, z0=zq, z1=zq - 2.0, stopnie=8,
                                                uwagi="wejście od dziobu; wnętrza jeszcze nie ma"))


# ================================================================ jol na legarach
def lodz_mesh(sk, L, B, D):
    """Jol klinkierowy w układzie lokalnym: stępka wzdłuż +Y Blendera od pawężki (y = 0) do dziobnicy (y = −L),
    spód stępki z = 0. Pasy poszycia na zakładkę (każdy dolny brzeg pasa wysunięty o grubość klepki), wręgi od środka,
    stępka, dziobnica, pawężka, wręgi, ławki, wiosła w środku, dulki na burcie."""
    NP = 6                      # pasy na burtę
    nu = 18

    def section(u):
        """Półszerokość i wysokość burty dla u ∈ [0, 1] (0 – pawężka, 1 – dziobnica) oraz kształt przekroju."""
        hb = B / 2 * (0.66 + 0.34 * math.sin(math.pi * min(u / 0.55, 1.0) * 0.5)) if u < 0.55 else \
            B / 2 * max(0.02, math.cos((u - 0.55) / 0.45 * math.pi / 2) ** 0.8)
        sheer = D + 0.10 * ((u - 0.42) / 0.58) ** 2
        rise = 0.10 * u ** 4                       # stępka wznosi się do dziobnicy
        return hb, sheer, rise

    def pt(u, v, off=0.0):
        hb, sh, rise = section(u)
        th = v * math.pi / 2
        x = hb * math.sin(th) ** 0.75
        z = rise + (sh - rise) * (1 - math.cos(th)) ** 1.15 if v > 0 else rise
        # normalna przybliżona w przekroju
        nx, nz = math.sin(th), -math.cos(th) * 0.6
        ln = math.hypot(nx, nz) + 1e-9
        return Vector((x + off * nx / ln, -L * u, z + 0.06 + off * nz / ln))
    lap = 0.012
    tk = 0.02
    us = [k / nu for k in range(nu + 1)]
    for side in (1, -1):
        def M(p):
            return Vector((side * p.x, p.y, p.z))
        for k in range(NP):
            # pas od v0 = 0,012 (stępka zakrywa brzeg) – wcześniej od 0,05: szczelina między stępką a pasem dennym
            # (przy dziobie dziura w dnie); każdy pas bryłą zamkniętą: dolny brzeg zachodzi 0,012 na pas niżej,
            # wnętrze dolnego brzegu 4 mm w pasie niżej, górny brzeg wnętrza 1 mm płycej (bez wspólnych wierzchołków)
            v0, v1 = 0.012 + 0.988 * k / NP, 0.012 + 0.988 * (k + 1) / NP
            if k > 0:
                v0 -= 0.012
            ofb = -tk + (0.004 if k > 0 else 0.0)
            oft = -tk + (0.001 if k < NP - 1 else 0.0)
            bot = [M(pt(u, v0, lap)) for u in us]
            top = [M(pt(u, v1, 0.0)) for u in us]
            ib = [M(pt(u, v0, ofb)) for u in us]
            it = [M(pt(u, v1, oft)) for u in us]
            vb, vt = sk.verts(bot), sk.verts(top)
            wb, wt = sk.verts(ib), sk.verts(it)
            for i in range(nu):
                q = [vb[i], vb[i + 1], vt[i + 1], vt[i]]
                sk.face_proj(q if side < 0 else q[::-1], "drewno", rot=0.0)
                q = [wb[i], wt[i], wt[i + 1], wb[i + 1]]
                sk.face_proj(q if side < 0 else q[::-1], "drewno_ciemne")
                q = [vb[i], wb[i], wb[i + 1], vb[i + 1]]
                sk.face_proj(q if side > 0 else q[::-1], "drewno")
                q = [vt[i], vt[i + 1], wt[i + 1], wt[i]]
                sk.face_proj(q if side > 0 else q[::-1], "drewno")
            # końce pasa (na pawężce i na dziobnicy)
            for i, odw in ((0, side > 0), (nu, side < 0)):
                q = [vb[i], vt[i], wt[i], wb[i]]
                sk.face_proj(q[::-1] if odw else q, "drewno")
        # wręgi od środka co ok. 0,3 m
        for u in np.arange(0.06, 0.93, 0.42 / L):
            path = [M(pt(u, v, -tk - 0.012)) for v in np.linspace(0.06, 0.98, 6)]
            N.sweep(sk, path, N.rect_prof(0.035, 0.024), "drewno_ciemne", up=Vector((0, 1, 0)))
        # burta górą: listwa odbojowa (malowana) i wewnętrzna, dulki
        path = [M(pt(u, 1.0, 0.012)) + Vector((0, 0, -0.02)) for u in us[:-1]]
        N.sweep(sk, path, N.rect_prof(0.04, 0.05), R_("burta_gorna"))
        path = [M(pt(u, 1.0, -tk - 0.02)) + Vector((0, 0, -0.025)) for u in us[:-1]]
        N.sweep(sk, path, N.rect_prof(0.04, 0.05), "drewno_ciemne")
        for u in (0.36, 0.56):
            c = M(pt(u, 1.0, -0.004)) + Vector((0, 0, 0.02))
            for dy in (-0.06, 0.06):
                N.cylinder(sk, c + Vector((0, dy, 0)), c + Vector((0, dy, 0.13)), 0.012, 0.01, "drewno_ciemne", sides=6)
    # stępka, dziobnica, pawężka
    # stępka (wzdłuż wzniosu dna, 0,11 × 0,09 – brzegi pasów dennych w jej wnętrzu) i dziobnica: wzdłuż dna do
    # samego dziobu, potem pionowo do burty (wcześniej łuk od 0,85 L szedł wyżej niż dno – dziura w dnie przy dziobie)
    rise_ = lambda u: section(u)[2]
    keel = [Vector((0, 0.03, rise_(0.0) + 0.045))] + [Vector((0, -L * u, rise_(u) + 0.045)) for u in
                                                      np.linspace(0.0, 0.88, 10)[1:]]
    N.sweep(sk, keel, N.rect_prof(0.09, 0.11), "drewno_ciemne", up=Vector((1, 0, 0)))
    r1 = rise_(1.0)
    stem = [Vector((0, -L * u, rise_(u) + 0.05)) for u in (0.85, 0.9, 0.94, 0.97, 0.99)] + \
        [Vector((0, -L - 0.005, r1 + 0.09)), Vector((0, -L - 0.015, r1 + 0.2)), Vector((0, -L - 0.015, (D + 0.17) * 0.6)),
         Vector((0, -L - 0.015, D + 0.17 + 0.035))]
    N.sweep(sk, stem, N.rect_prof(0.06, 0.08), "drewno_ciemne", up=Vector((1, 0, 0)))
    hb0, sh0, _ = section(0.0)
    tr = []
    for v in np.linspace(0.0, 1.0, 10):
        p = pt(0.0, v, 0.012)
        tr.append(p)
    poly = [Vector((x.x, 0.015, x.z)) for x in tr] + [Vector((-x.x, 0.015, x.z)) for x in reversed(tr)]
    v0 = sk.verts(poly)
    v1 = sk.verts([p + Vector((0, -0.035, 0)) for p in poly])
    sk.face_proj(v0, "drewno", axis=1)
    sk.face_proj(v1[::-1], "drewno", axis=1)
    for i in range(len(poly)):
        j = (i + 1) % len(poly)
        sk.face_proj([v0[i], v0[j], v1[j], v1[i]], "drewno_ciemne")
    # ławki, ławka rufowa, deski dna, wiosła
    def do_burty(u, z):
        """Półszerokość wnętrza (wręgi od środka) na wysokości z – ławka dochodzi do wręgów, nie przebija burty."""
        best = 0.0
        for v in np.linspace(0.05, 1.0, 60):
            p = pt(u, v, -tk - 0.024)
            if p.z <= z:
                best = p.x
        return best
    zl = []
    for u in (0.27, 0.45, 0.63):                 # ławki prostopadłe do osi, od burty do burty
        hb, sh, rise = section(u)
        z = sh * 0.72
        x_in = min(do_burty(u - 0.02, z - 0.02), do_burty(u + 0.02, z - 0.02))
        N.box(sk, Vector((0, -L * u, z)), (2 * x_in, 0.2, 0.035), "drewno")
        zl.append(z)
    hb, sh, _ = section(0.09)
    z = sh * 0.62
    x_in = min(do_burty(0.07, z - 0.02), do_burty(0.11, z - 0.02))
    N.box(sk, Vector((0, -L * 0.09, z)), (2 * x_in, 0.24, 0.035), "drewno")
    for x in (-0.18, 0.0, 0.18):
        N.oriented_box(sk, Vector((x, -L * 0.16, 0.175)), Vector((x, -L * 0.70, 0.185)), 0.11, 0.02, "drewno")
    for k, x in enumerate((-0.27, -0.09, 0.09, 0.27)):
        z = max(zl) + 0.0175 + 0.022            # na najwyższej ławce, wzdłuż osi
        a0, a1 = Vector((x, -L * 0.20, z)), Vector((x, -L * 0.74, z))
        N.cylinder(sk, a0, a0.lerp(a1, 0.78), 0.022, 0.022, "drewno", sides=6)
        d = (a1 - a0).normalized()
        c = a0.lerp(a1, 0.88)
        N.box(sk, c, (0.12, (a1 - a0).length * 0.22, 0.012), "drewno", rot=N.rot_to(d, up=Vector((0, 0, 1))) @
              __import__("mathutils").Matrix.Rotation(math.pi / 2, 3, "X"))


def lodz(ctx):
    """Jol okrętowy w jednym z trzech stanów (parametr LODZ.stan): 'za_rufa' – na wodzie za rufą na falenie
    (domyślnie: okręt na kotwicy), 'na_pokladzie' – nisko na legarach nad lukiem głównym (wtedy działa przy łodzi mają
    krótszy odrzut, co odnotowuje test), 'brak'."""
    U = ctx["PR"].UKLAD["LODZ"]
    stan = ctx.get("lodz_stan") or U.get("stan", "za_rufa")
    ctx["lodz_stan"] = stan
    if stan == "brak":
        return
    kol = ctx["kol"]["wyposazenie"]
    L = U["s1"] - U["s0"]
    B, D = U["szer"], U["glebokosc"]
    sk = N.Siatka("lodz")
    lodz_mesh(sk, L, B, D)
    ob = N.to_object(sk, kol, recalc=True)
    ob.data.set_sharp_from_angle(angle=math.radians(40))
    from olinowanie import lina
    if stan == "za_rufa":
        # na wodzie za rufą: zanurzenie ok. 0,25 m, lekki skręt; faleń z pierścienia na relingu rufowym
        s_t = -15.0
        ob.location = P(0.9, s_t - 1.7 - L, -0.27)        # pawężka łodzi najdalej od okrętu, dziób ku rufie okrętu
        ob.rotation_euler = (0, 0, math.radians(7))
        bpy_update()
        bow = ob.matrix_world @ Vector((0, -L - 0.015, D + 0.12))    # faleń w dziobnicy (oś dziobnicy y = −L − 0,015)
        zt = float(ctx["kd"].deck_c(-14.0)) + ctx["K"]["POLPOKLAD_H"] + 0.95
        # faleń na śrubie oczkowej w pokrywie relingu rufowego (wierzch pokrywy zt − 0,007), poza koroną pawęży
        # (sięga x ≈ 1,3 m); wcześniej koniec wisiał nad relingiem przy koronie bez okucia
        zr = zt - 0.007
        skr = ctx.setdefault("_sk_drobne", N.Siatka("okucia_pokladu"))
        N.cylinder(skr, P(1.55, -15.12, zr - 0.05), P(1.55, -15.12, zr + 0.02), 0.012, 0.012, "zelazo", sides=8)
        ring = P(1.55, -15.12, zr + 0.055)          # przy tylnej krawędzi pokrywy (lina od razu w dół)
        N.lathe(skr, [(0.027, -0.009), (0.036, 0.0), (0.027, 0.009), (0.018, 0.0)], "zelazo", ring,
                axis=Vector((1, 0, 0)), sides=8, close_ends=False)
        lina(ctx, "lodz", [ring, bow], 0.02, "lina_jasna")
        stanowisko(ctx, "lodz", -14.1, 1.0, deck(ctx, -14.1, 1.0, qd=True), -1, 0, obiekt="lodz",
                   os="faleń: przyciągnąć łódź pod rufę", h_rak=1.1)
        ob["stan"] = "za_rufa"
        lodz_maska_wody(ctx, ob, z_wl=0.27)
        return ob
    # na pokładzie: nisko, na legarach opartych o zrębnicę luku głównego
    s0, s1 = U["s0"], U["s1"]
    sc = (s0 + s1) / 2
    zd = deck(ctx, sc, 0.0)
    zk = zd + 0.42
    ob.location = P(0, s0, zk)
    ob.rotation_euler = (0, 0, math.pi)
    sk2 = N.Siatka("lodz_legary")
    for s in (s0 + 0.9, s1 - 1.1):
        N.box(sk2, P(0, s, zk - 0.09), (B * 0.8, 0.18, 0.18), "drewno_ciemne")
        for sg in (1, -1):
            N.box(sk2, P(sg * 0.38, s, zk + 0.03), (0.28, 0.18, 0.1), "drewno_ciemne")
    N.to_object(sk2, kol, recalc=True)
    przeszkoda(ctx, "lodz", "lodz", "prostokat", sc, 0.0, (L, B), zk + D - zd)
    stanowisko(ctx, "lodz", sc, B / 2 + 0.9, deck(ctx, sc, B / 2 + 0.9), 0, -1, obiekt="lodz",
               os="opuszczanie taliami z noków rej", h_rak=1.6)
    stanowisko(ctx, "lodz", sc, -(B / 2 + 0.9), deck(ctx, sc, -(B / 2 + 0.9)), 0, 1, obiekt="lodz",
               os="opuszczanie taliami z noków rej", h_rak=1.6)
    ob["stan"] = "na_pokladzie"
    return ob


def lodz_maska_wody(ctx, ob, z_wl):
    """Maska wody wewnątrz łodzi na wodzie: płaski wielokąt obrysu zewnętrznej strony poszycia na wysokości wodnicy
    łodzi (z_wl nad spodem stępki, lokalnie), osobny węzeł 'lodz_maska_wody' z tym samym położeniem co łódź.
    Gra rysuje go do bufora szablonu / głębi i nie rysuje wody wewnątrz obrysu (extras: opis, wodnica)."""
    import bpy
    import bmesh
    from mathutils.bvhtree import BVHTree
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    tree = BVHTree.FromBMesh(bm)
    ys = [v.co.y for v in bm.verts]
    y0, y1 = max(ys), min(ys)                 # pawężka (y ≈ 0) … dziobnica (y = −L)
    bm.free()
    half = []
    # gęściej przy dziobie (ostatnie 0,4 m): obrys szybko się zwęża, rzadkie próbki zostawiały przy dziobnicy klin
    # tafli wewnątrz łodzi
    ys = list(np.linspace(y0 - 0.002, y1 + 0.4, 36)) + list(np.linspace(y1 + 0.4, y1 + 0.002, 14))[1:]
    for y in ys:
        hit = tree.ray_cast(Vector((3.0, y, z_wl)), Vector((-1, 0, 0)), 6.0)
        if hit[0] is not None and hit[0].x > 0.002:
            half.append((hit[0].x, y))
    if len(half) < 3:
        return None
    # czubek obrysu: przód dziobnicy na wodnicy (promień wzdłuż osi łodzi od strony dziobu)
    czubek = tree.ray_cast(Vector((0.0, y1 - 1.0, z_wl)), Vector((0, 1, 0)), 3.0)
    dziob = [Vector((0.0, czubek[0].y, z_wl))] if czubek[0] is not None and czubek[0].y < half[-1][1] - 1e-4 else []
    pts = [Vector((x, y, z_wl)) for (x, y) in half] + dziob + [Vector((-x, y, z_wl)) for (x, y) in reversed(half)]
    me = bpy.data.meshes.new("lodz_maska_wody")
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in pts]
    f = bm.faces.new(vs)
    if f.normal.z < 0:
        f.normal_flip()
    bmesh.ops.triangulate(bm, faces=[f], quad_method="BEAUTY", ngon_method="BEAUTY")
    bm.to_mesh(me)
    bm.free()
    mat = bpy.data.materials.get("maska_wody") or bpy.data.materials.new("maska_wody")
    mat.diffuse_color = (0.5, 0.5, 0.5, 0.0)
    mat.use_backface_culling = True            # jednostronna (glTF doubleSided = false): normalna w górę
    # niewidoczna w każdej przeglądarce glTF (hide_render nie przechodzi do glTF): alfa 0 i mieszanie (alphaMode
    # BLEND, baseColorFactor[3] = 0); gra podmienia materiał na rysowany tylko do głębi / szablonu
    mat.use_nodes = True
    bs = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bs is None:
        bs = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        wy = next((n for n in mat.node_tree.nodes if n.type == "OUTPUT_MATERIAL"), None) or \
            mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
        mat.node_tree.links.new(bs.outputs["BSDF"], wy.inputs["Surface"])
    bs.inputs["Base Color"].default_value = (0.5, 0.5, 0.5, 1.0)
    bs.inputs["Alpha"].default_value = 0.0
    for atr, w in (("surface_render_method", "BLENDED"), ("blend_method", "BLEND")):
        try:
            setattr(mat, atr, w)
        except Exception:
            pass
    me.materials.append(mat)
    m = bpy.data.objects.new("lodz_maska_wody", me)
    ob.users_collection[0].objects.link(m)
    m.matrix_world = ob.matrix_world.copy()
    m["osobny_wezel"] = True
    m["opis"] = ("maska wody wewnątrz łodzi: obrys zewnętrznej strony poszycia na wodnicy łodzi (%.2f m nad spodem "
                 "stępki, w świecie z = 0); gra nie rysuje wody wewnątrz obrysu (szablon/głębia), węzeł niewidoczny"
                 % z_wl)
    m["wodnica_lodzi_m"] = z_wl
    # węzeł pomocniczy: w przeglądarkach niewidoczny (materiał z alfą 0), gra podmienia jego materiał na rysowany
    # tylko do bufora głębi albo szablonu
    m["pomocniczy"] = True
    m["pomocniczy_opis"] = "gra podmienia materiał na rysowany tylko do głębi albo szablonu"
    m.hide_render = True
    return m


def bpy_update():
    import bpy
    bpy.context.view_layer.update()


def R_(nm):
    from materialy import region
    return region(nm)


# ================================================================ kotwice
def kotwica_mesh(sk, L=3.3):
    """Kotwica w układzie lokalnym: trzon wzdłuż −Z od pierścienia (0,0,0), ramiona w płaszczyźnie XZ, poprzeczka
    wzdłuż Y."""
    a = L
    N.oriented_box(sk, Vector((0, 0, -0.12)), Vector((0, 0, -a)), 0.11, 0.11, "zelazo")
    N.lathe(sk, [(0.11, -0.02), (0.135, 0.0), (0.11, 0.02), (0.085, 0.0)], "zelazo", Vector((0, 0, 0.03)),
            axis=Vector((0, 1, 0)), sides=12, close_ends=False)
    N.cylinder(sk, Vector((0, 0, -0.04)), Vector((0, 0, -0.14)), 0.05, 0.06, "zelazo", sides=8)
    # ramiona: łuk od korony w górę na obie strony
    for sg in (1, -1):
        pts = []
        for t in np.linspace(0, 1, 9):
            ang = t * math.radians(52)
            r = 1.05
            pts.append(Vector((sg * r * math.sin(ang), 0, -a + r * (1 - math.cos(ang)) + 0.02)))
        N.sweep(sk, pts, N.rect_prof(0.10, 0.12), "zelazo", scale=[1.0 - 0.3 * k / 8 for k in range(9)])
        tip = pts[-1]
        dirv = (pts[-1] - pts[-2]).normalized()
        # łapa (palm): trójkątna płyta
        n = Vector((0, 1, 0))
        b0 = tip - dirv * 0.45
        q = [b0 + Vector((0, 0.17, 0)), tip + dirv * 0.06, b0 + Vector((0, -0.17, 0))]
        v0 = sk.verts([p + Vector((-sg * 0.02, 0, 0)) for p in q])
        v1 = sk.verts([p + Vector((sg * 0.02, 0, 0)) for p in q])
        sk.face_proj(v0, "zelazo")
        sk.face_proj(v1[::-1], "zelazo")
        for i in range(3):
            j = (i + 1) % 3
            sk.face_proj([v0[i], v0[j], v1[j], v1[i]], "zelazo")
    N.lathe(sk, [(0.0, -0.1), (0.1, -0.06), (0.12, 0.0), (0.1, 0.06), (0.0, 0.1)], "zelazo",
            Vector((0, 0, -a + 0.02)), axis=Vector((0, 1, 0)), sides=10)
    # drewniana poprzeczka (dwie połówki) z obręczami
    N.sweep(sk, [Vector((0, -1.75, -0.35)), Vector((0, -0.6, -0.33)), Vector((0, 0.6, -0.33)), Vector((0, 1.75, -0.35))],
            N.rect_prof(0.2, 0.2), "drewno_ciemne", scale=[0.6, 1.0, 1.0, 0.6])
    for y in (-1.2, -0.55, 0.55, 1.2):
        N.cylinder(sk, Vector((0, y - 0.02, -0.34)), Vector((0, y + 0.02, -0.34)), 0.13, 0.13, "zelazo", sides=8)


def kotwice(ctx):
    kol = ctx["kol"]["wyposazenie"]
    ends = dict(ctx["kotbelki"])
    from olinowanie import lina
    from rufa_dziob import GALION
    ps = ctx["poszycie"]
    # lewa: zawieszona na kotbelce, trzon wzdłuż burty
    sk = N.Siatka("kotwica_L")
    kotwica_mesh(sk)
    ob = N.to_object(sk, kol, recalc=True)
    b1 = ends[1]
    ob.location = b1 + Vector((0.02, 0.0, -0.45))
    ob.rotation_euler = (0, math.radians(-6), math.radians(18))
    ob["opis"] = "kotwica lewa na kotbelce (catted)"
    lina(ctx, "kotwice", [b1 + Vector((0, 0, -0.05)), ob.location + Vector((0, 0, 0.03))], 0.04, "lina_jasna")
    # lina kotwiczna lewej: z kluzy do pierścienia
    s0, z0 = GALION["KLUZA_S"], GALION["KLUZA_Z"]
    x0, _ = ps.outer(s0, z0)
    lina(ctx, "kotwice", [P(x0 + 0.05, s0, z0), Vector(ob.location) + Vector((0, 0, 0.0))], 0.16, sag=0.25)
    # prawa: lina z kluzy w wodę przed dziobem usunięta (runda 2e) – okręt w drodze, kotwice na kotbelkach; na pokładzie
    # zostaje lina kotwiczna od kluzy do pachołków przy fokmaszcie
    # lina kotwiczna na pokładzie: od kluzy do pachołków przy fokmaszcie
    D = ctx["PR"].DRZEWCA
    sf = D["FOK_S"] + 0.75
    zd = deck(ctx, sf, -0.4)
    xi = inner_x(ctx, s0 - 0.4)
    pts = [P(-(xi - 0.05), s0 - 0.25, deck(ctx, s0 - 0.25, -(xi - 0.05)) + 0.12),
           P(-(xi - 0.4), s0 - 0.9, deck(ctx, s0 - 0.9, -(xi - 0.4)) + 0.09),
           P(-0.55, sf + 0.4, zd + 0.09), P(-0.72, sf, zd + 0.3)]
    lina(ctx, "kotwice", N.catmull(pts, 6), 0.16)
    przeszkoda(ctx, "lina_kotwiczna", "lina_kotwice", "prostokat", (s0 + sf) / 2, -1.2, (s0 - sf, 0.3), 0.2,
               chodzic=True, prog=0.2, rot=0.0)
    # prawa burta: kotwica rzucona (nie ma jej w modelu) – stanowisko przy linie kotwicznej na pokładzie i przy
    # prawej kotbelce wskazują linę i kotbelkę, nie lewą kotwicę
    stanowisko(ctx, "kotwica", s0 - 0.9, -(xi - 0.6), deck(ctx, s0 - 0.9, -(xi - 0.6)), 0.4, -1, obiekt="lina_kotwice",
               os=None, h_rak=1.1)
    stanowisko(ctx, "kotbelka", 12.0, xi - 0.55, deck(ctx, 12.0, xi - 0.55), 0.6, 1, obiekt="kotwica_L",
               os="talia kotbelki", h_rak=1.2)
    stanowisko(ctx, "kotbelka", 12.0, -(xi - 0.55), deck(ctx, 12.0, -(xi - 0.55)), 0.6, -1, obiekt="kotbelki",
               os="talia kotbelki", h_rak=1.2)


# ================================================================ drobne
def dzialka_relingowe(ctx):
    kol = ctx["kol"]["wyposazenie"]
    ps = ctx["poszycie"]
    U = ctx["PR"].UKLAD["DZIALKA_RELINGOWE"]
    sk = N.Siatka("dzialko_relingowe")
    # w układzie lokalnym: słupek w dół, widełki, lufa wzdłuż +X
    # trzpień tylko w gnieździe pokrywy relingu (0,06 m w głąb pokrywy grubości 0,07 m), żelazna tuleja na pokrywie
    N.cylinder(sk, Vector((0, 0, -0.06)), Vector((0, 0, 0.0)), 0.035, 0.035, "zelazo", sides=10)
    N.cylinder(sk, Vector((0, 0, -0.012)), Vector((0, 0, 0.02)), 0.06, 0.055, "zelazo", sides=12)
    N.box(sk, Vector((0, 0, 0.03)), (0.04, 0.16, 0.03), "zelazo")
    for sg in (1, -1):
        N.box(sk, Vector((0, sg * 0.07, 0.11)), (0.04, 0.02, 0.15), "zelazo")
    N.lathe(sk, [(0.0, -0.3), (0.04, -0.3), (0.06, -0.26), (0.055, 0.0), (0.045, 0.55), (0.05, 0.6), (0.02, 0.6),
                 (0.02, 0.45), (0.0, 0.45)], "zelazo", Vector((0, 0, 0.17)), axis=Vector((1, 0, 0)), sides=10)
    N.cylinder(sk, Vector((-0.3, 0, 0.17)), Vector((-0.65, 0, 0.12)), 0.018, 0.012, "zelazo", sides=6)
    tmp = N.to_object(sk, kol, recalc=True)
    mesh = tmp.data
    bpy_remove(tmp)
    import bpy
    k = 0
    for s in U:
        for side, tag in ((1, "L"), (-1, "P")):
            k += 1
            zt = ps.rail_top(s) + 0.07
            x, (nx, ns) = ps.outer(s, ps.rail_top(s))
            ob = bpy.data.objects.new("dzialko_%s%d" % (tag, (k + 1) // 2), mesh)
            kol.objects.link(ob)
            ob.location = P(side * (x - 0.1), s, zt)
            ob.rotation_euler = (0, 0, 0 if side > 0 else math.pi)
            ob["os_ruchu"] = "obrót wokół lokalnej Z 360°, przechył ±30°"


def drobne(ctx):
    U = ctx["PR"].UKLAD
    kol = ctx["kol"]["wyposazenie"]
    sk = N.Siatka("wyposazenie_drobne")
    # komin kambuza z daszkiem
    k = U["KOMIN"]
    zd = deck(ctx, k["s"], k["x"])
    N.box(sk, P(k["x"], k["s"], zd + k["h"] / 2), (k["a"], k["a"], k["h"]), "zelazo")
    N.box(sk, P(k["x"], k["s"], zd + 0.06), (k["a"] + 0.2, k["a"] + 0.2, 0.12), "drewno_ciemne")
    N.lathe(sk, [(0.0, 0.0), (0.28, 0.0), (0.12, 0.18), (0.0, 0.2)], "zelazo", P(k["x"], k["s"], zd + k["h"] + 0.12),
            sides=4)
    przeszkoda(ctx, "komin", "wyposazenie_drobne", "prostokat", k["s"], k["x"], (0.55, 0.55), k["h"])
    # beczka do picia
    b = U["BECZKA_WODY"]
    zd = deck(ctx, b["s"], b["x"])
    r = b["r"]
    prof = [(0.0, 0.0), (r * 0.86, 0.0), (r * 0.95, 0.15), (r, b["h"] / 2), (r * 0.95, b["h"] - 0.15), (r * 0.86, b["h"]),
            (0.0, b["h"])]
    N.lathe(sk, prof, "drewno", P(b["x"], b["s"], zd), sides=16)
    for z in (0.08, 0.25, b["h"] - 0.25, b["h"] - 0.08):
        rr = float(np.interp(z, [p[1] for p in prof[1:-1]], [p[0] for p in prof[1:-1]])) + 0.004
        N.lathe(sk, [(rr, z - 0.025), (rr + 0.006, z), (rr, z + 0.025)], "zelazo", P(b["x"], b["s"], zd), sides=16,
                close_ends=False)
    przeszkoda(ctx, "beczka_wody", "wyposazenie_drobne", "kolo", b["s"], b["x"], r + 0.03, b["h"])
    stanowisko(ctx, "beczka", b["s"] + 0.7, b["x"], deck(ctx, b["s"] + 0.7, b["x"]), -1, 0, obiekt=None, h_rak=1.0)
    # kojce z kratą
    for kk in U["KOJCE"]:
        for side in (1, -1):
            zq0 = deck(ctx, kk["s"], side * kk["x"], qd=True)
            xw = burta_min_x(ctx, kk["s"] - 0.77, kk["s"] + 0.77, zq0, zq0 + 0.62)
            # poza knagami na nadburciu (knaga sięga 0,09 od burty, burta zawalona ku górze – zapas 4 cm)
            s0, x0 = kk["s"], side * min(kk["x"], xw - 0.32 - 0.13)
            zq = deck(ctx, s0, x0, qd=True)
            N.box(sk, P(x0, s0, zq + 0.08), (0.6, 1.5, 0.16), "drewno_ciemne")
            N.box(sk, P(x0, s0, zq + 0.58), (0.64, 1.54, 0.05), "drewno_ciemne")
            for dz in np.arange(-0.68, 0.7, 0.085):
                N.box(sk, P(x0 - side * 0.3, s0 + dz, zq + 0.37), (0.03, 0.025, 0.4), "drewno")
            for e in (-0.74, 0.74):
                N.box(sk, P(x0, s0 + e, zq + 0.37), (0.6, 0.04, 0.42), "drewno_ciemne")
            przeszkoda(ctx, "kojec_" + ("L" if side > 0 else "P"), "wyposazenie_drobne", "prostokat", s0, x0,
                       (1.55, 0.65), 0.6, poziom="rufowy")
    # skrzynia z bronią
    c = U["SKRZYNIA_BRONI"]
    zq = deck(ctx, c["s"], c["x"], qd=True)
    N.box(sk, P(c["x"], c["s"], zq + 0.23), (0.5, 1.2, 0.46), "drewno_ciemne")
    N.box(sk, P(c["x"], c["s"], zq + 0.48), (0.54, 1.24, 0.05), "drewno_ciemne")
    for e in (-0.4, 0.4):
        N.box(sk, P(c["x"], c["s"] + e, zq + 0.25), (0.52, 0.04, 0.47), "zelazo")
    przeszkoda(ctx, "skrzynia_broni", "wyposazenie_drobne", "prostokat", c["s"], c["x"], (1.25, 0.55), 0.5,
               poziom="rufowy")
    # stojaki na kule przy działach (na ścieku, między furtami)
    for g in ctx.get("dziala", []):
        s = g["s"] + 0.9 * (1 if g["side"] > 0 else -1)
        xi = g["xi"] - 0.42                       # na pokładzie, przed ściekiem i wręgami
        side = g["side"]
        zd = deck(ctx, s, side * xi)
        N.box(sk, P(side * xi, s, zd + 0.03), (0.12, 0.62, 0.06), "drewno_ciemne")
        for kk in range(5):
            N.lathe(sk, [(0.0, -0.044), (0.031, -0.031), (0.044, 0.0), (0.031, 0.031), (0.0, 0.044)], "zelazo",
                    P(side * xi, s - 0.24 + kk * 0.12, zd + 0.1), sides=8)
    ob = N.to_object(sk, kol, recalc=True)
    ob.name = "wyposazenie_drobne"
    ob.data.set_sharp_from_angle(angle=math.radians(35))


def zbuduj(ctx):
    U = ctx["PR"].UKLAD
    dziala(ctx)
    kabestan(ctx)
    pompy(ctx)
    L = U["LUK_GLOWNY"]
    luk(ctx, "luk_glowny", L["s0"], L["s1"], L["pol_x"], L["h"])
    stanowisko(ctx, "luk", L["s0"] + 0.6, L["pol_x"] + 0.5, deck(ctx, L["s0"] + 0.6, L["pol_x"] + 0.5), 0, -1,
               obiekt="luk_glowny", h_rak=0.5)
    L = U["LUK_DZIOBOWY"]
    luk(ctx, "luk_dziobowy", L["s0"], L["s1"], L["pol_x"], L["h"])
    sm = (L["s0"] + L["s1"]) / 2
    for sg in (1, -1):
        stanowisko(ctx, "luk", sm, sg * (L["pol_x"] + 0.5), deck(ctx, sm, sg * (L["pol_x"] + 0.5)), 0, -sg,
                   obiekt="luk_dziobowy", h_rak=0.5)
    ctx.setdefault("przejscia", []).append(dict(nazwa="luk_glowny_drabina", typ="drabina_w_dol",
                                                s0=U["LUK_GLOWNY"]["s0"] + 0.3, s1=U["LUK_GLOWNY"]["s0"] + 0.3,
                                                x0=-0.4, x1=0.4, z0=deck(ctx, 3.0, 0), z1=deck(ctx, 3.0, 0) - 2.6,
                                                stopnie=10, uwagi="pod kratą; ładownia jeszcze nie istnieje"))
    pins = {"fok": nagielbank(ctx, "fok"), "grot": nagielbank(ctx, "grot")}
    ctx["kolki_nagielbankow"] = pins
    ctx["kolki_kolkownic"] = kolkownice(ctx)
    import sterowanie
    sterowanie.zbuduj(ctx)               # koło sterowe (domyślnie) i rumpel na pokładzie – dwa warianty napędu steru
    szafka(ctx)
    dzwon(ctx)
    zejsciowka(ctx)
    lodz(ctx)
    kotwice(ctx)
    dzialka_relingowe(ctx)
    drobne(ctx)
    # zebrane drobne okucia i bloki
    for key in ("_sk_drobne", "_sk_bloki"):
        if key in ctx and ctx[key].f:
            if key == "_sk_bloki":          # okucia są już obiektem: blok bez styku dostaje strop
                stropy_blokow(ctx, ctx[key])
            N.to_object(ctx[key], ctx["kol"]["wyposazenie"], recalc=False)
