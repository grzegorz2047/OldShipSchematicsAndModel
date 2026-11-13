"""Narzędzia geometrii dla generatora statku: budowniczy siatek, rurki, bryły obrotowe, przeciągnięcia profili,
krzywe (PCHIP, Catmull-Rom, łańcuchowa) i obsługa kolekcji.

Układ statku: s – wzdłuż (+ ku dziobowi), x – w poprzek (+ lewa burta, bakburta), z – w górę od linii wodnej.
Blender: (x, −s, z), więc po eksporcie glTF (+Y w górę) dziób patrzy w +Z, a lewa burta w +X – jak w grze.
UV liczone w metrach (u wzdłuż włókien / splotu), skalowane przez kafel materiału przy tworzeniu obiektu.
"""
import math
import zlib

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector


def P(x, s, z):
    """Punkt w układzie statku → wektor Blendera."""
    return Vector((x, -s, z))


def S(v):
    """Wektor Blendera → (x, s, z) statku."""
    return (v[0], -v[1], v[2])


from narzedzia_math import catmull, pchip, pchip_slopes, polyline_len, resample, spline_nat  # noqa: F401


def catenary(p0, p1, sag, n=16):
    """Lina luźna między punktami (Vector) ze zwisem sag (m, w środku, w dół −Z) – parabola ≈ łańcuchowa dla
    małych zwisów, przybliżona przez cosh; dla sag ≤ 0 odcinek prosty."""
    p0, p1 = Vector(p0), Vector(p1)
    if sag <= 1e-4:
        return [p0.lerp(p1, i / (n - 1)) for i in range(n)]
    span = (p1 - p0).length
    lo, hi = 1e-3, 1e6            # parametr a krzywej: sag = a·(cosh(span/2a) − 1)
    a = 1.0
    for _ in range(80):
        a = (lo * hi) ** 0.5
        if a * (math.cosh(span / (2 * a)) - 1) > sag:
            lo = a
        else:
            hi = a
    top = a * math.cosh(span / (2 * a))
    out = []
    for i in range(n):
        t = i / (n - 1)
        xx = (t - 0.5) * span
        out.append(p0.lerp(p1, t) + Vector((0, 0, a * math.cosh(xx / a) - top)))
    out[0], out[-1] = p0.copy(), p1.copy()
    return out


# ---------------------------------------------------------------- budowniczy siatki

class Siatka:
    """Zbiera wierzchołki i ściany z UV w metrach i nazwą materiału na ścianę."""

    def __init__(self, nazwa):
        self.nazwa = nazwa
        self.v = []
        self.f = []
        self.uv = []
        self.mat = []
        self.flat = []
        self.odcien = []          # mnożnik koloru ściany (RGB) albo None – kolor wierzchołków 'odcien'

    def vert(self, p):
        self.v.append(tuple(p))
        return len(self.v) - 1

    def verts(self, ps):
        i0 = len(self.v)
        self.v.extend(tuple(p) for p in ps)
        return list(range(i0, len(self.v)))

    def face(self, idx, uvs, mat, flat=False):
        if len(set(idx)) < 3:
            return
        self.f.append(tuple(idx))
        self.uv.append(tuple(tuple(u) for u in uvs))
        self.mat.append(mat)
        self.flat.append(flat)
        self.odcien.append(None)

    def face_proj(self, idx, mat, flat=False, axis=None, rot=0.0):
        """Ściana z UV z rzutu na płaszczyznę prostopadłą do dominującej osi normalnej (metry)."""
        pts = [Vector(self.v[i]) for i in idx]
        n = Vector((0, 0, 0))
        for k in range(len(pts)):
            n += pts[k].cross(pts[(k + 1) % len(pts)])
        uvs = proj_uv(pts, n, axis, rot)
        self.face(idx, uvs, mat, flat)

    def extend(self, other, matrix=None):
        off = len(self.v)
        if matrix is None:
            self.v.extend(other.v)
        else:
            self.v.extend(tuple(matrix @ Vector(p)) for p in other.v)
        self.f.extend(tuple(i + off for i in f) for f in other.f)
        self.uv.extend(other.uv)
        self.mat.extend(other.mat)
        self.flat.extend(other.flat)
        self.odcien.extend(getattr(other, "odcien", None) or [None] * len(other.f))

    def ntris(self):
        return sum(len(f) - 2 for f in self.f)


def proj_uv(pts, n, axis=None, rot=0.0):
    ax = abs(n.x), abs(n.y), abs(n.z)
    if axis is None:
        axis = ax.index(max(ax))
    out = []
    c, s_ = math.cos(rot), math.sin(rot)
    for p in pts:
        if axis == 0:
            u, v = -p.y, p.z      # burta: u wzdłuż statku
        elif axis == 1:
            u, v = p.x, p.z       # poprzecznie (pawęż, grodzie)
        else:
            u, v = -p.y, p.x      # poziomo: u wzdłuż statku
        out.append((c * u - s_ * v, s_ * u + c * v))
    return out


MATERIALY_REJESTR = {}   # nazwa → bpy material (wypełnia materialy.py)
KAFLE = {}               # nazwa materiału → metry na kafel (u, v)
UV_ZEROWE_NAPRAWIONE = {}   # siatka → liczba ścian o zerowym polu UV przerzutowanych w to_object (kontrola.json)


def orientuj_na_zewnatrz(bm):
    """Normalne na zewnątrz w każdej zamkniętej części siatki (bmesh): część o ujemnej objętości ze znakiem
    (suma czworościanów od początku układu) – ściany odwrócone. Rozstrzyga jednoznacznie tam, gdzie
    recalc_face_normals zgaduje (długie walce z czołami, części nakładające się). Zwraca liczbę odwróconych."""
    bm.faces.ensure_lookup_table()
    seen = set()
    n_rev = 0
    for f0 in bm.faces:
        if f0.index in seen:
            continue
        st, fs = [f0], [f0]
        seen.add(f0.index)
        closed = True
        while st:
            g = st.pop()
            for e in g.edges:
                if len(e.link_faces) != 2:
                    closed = False
                for h in e.link_faces:
                    if h.index not in seen:
                        seen.add(h.index)
                        st.append(h)
                        fs.append(h)
        if not closed:
            continue
        c = fs[0].verts[0].co.copy()
        vol = 0.0
        for g in fs:
            vs = [v.co - c for v in g.verts]
            for i in range(1, len(vs) - 1):
                vol += vs[0].dot(vs[i].cross(vs[i + 1])) / 6.0
        if vol < -1e-12:
            bmesh.ops.reverse_faces(bm, faces=fs)
            n_rev += 1
    return n_rev


def scal_wierzcholki(sk, dist=0.002):
    """Scalenie wierzchołków Siatki bliższych niż dist (jak spaw w to_object, ale przed cięciem na deski – krawędzie
    wspólne części budowanych osobno muszą być wspólne także w indeksach). Zwraca (liczba scalonych, {stary indeks
    ściany: nowy}) – ściany zdegenerowane po scaleniu znikają."""
    from mathutils.kdtree import KDTree
    n = len(sk.v)
    kd = KDTree(n)
    for i, p in enumerate(sk.v):
        kd.insert(p, i)
    kd.balance()
    mapa = list(range(n))
    for i, p in enumerate(sk.v):
        if mapa[i] != i:
            continue
        for (_, j, _) in kd.find_range(p, dist):
            if j > i and mapa[j] == j:
                mapa[j] = i
    nf, nuv, nm, nfl, nod = [], [], [], [], []
    nowe = {}
    for fi, (f, uv, m, fl, od) in enumerate(zip(sk.f, sk.uv, sk.mat, sk.flat, sk.odcien)):
        g, guv = [], []
        for i, q in zip(f, uv):
            k = mapa[i]
            if g and g[-1] == k:
                continue
            g.append(k)
            guv.append(q)
        if len(g) > 1 and g[0] == g[-1]:
            g.pop()
            guv.pop()
        if len(set(g)) < 3:
            continue
        nowe[fi] = len(nf)
        nf.append(tuple(g)); nuv.append(tuple(guv)); nm.append(m); nfl.append(fl); nod.append(od)
    sk.f, sk.uv, sk.mat, sk.flat, sk.odcien = nf, nuv, nm, nfl, nod
    return sum(1 for i in range(n) if mapa[i] != i), nowe


DREWNO_SLOJE = ("drewno", "drewno_ciemne", "drewno_czarne", "laweta")   # materiały z kierunkiem słojów (elementy)
STATYSTYKA_SLOJOW = {"elementy": 0, "poprawione": 0}


def _grad_uv(P, uv):
    """Kierunki 3D przyrostu u i v na ścianie (dP/du, dP/dv) z trzech pierwszych narożników; None przy degeneracji."""
    e1, e2 = P[1] - P[0], P[2] - P[0]
    a, b = uv[1][0] - uv[0][0], uv[2][0] - uv[0][0]
    c, d = uv[1][1] - uv[0][1], uv[2][1] - uv[0][1]
    det = a * d - b * c
    if abs(det) < 1e-12:
        return None
    # [e1 e2] = [Pu Pv] [[a b] [c d]] → [Pu Pv] = [e1 e2] inv
    Pu = (e1 * d - e2 * c) / det
    Pv = (e2 * a - e1 * b) / det
    return Pu, Pv


def sloje_wzdluz(sk, seed=0):
    """Słoje wzdłuż elementu: dla każdej spójnej części (prymitywu) z materiałem drewna – oś główna (PCA); jeśli
    więcej niż 20 % pola ścian ma UV niezgodne z osią (kierunek u odchylony > 25° albo anizotropia > 1,25), UV części
    liczone od nowa: u wzdłuż osi, v po obwodzie (część okrągła) albo w płaszczyźnie ściany prostopadle do osi
    (część kanciasta), czoła – rzut na płaszczyznę przekroju. Każda część dostaje losowe przesunięcie UV (inne słoje
    niż sąsiad) i odcień (jasność ±8 %, ciepło ±3 %) w sk.odcien."""
    if not sk.f:
        return
    wood = [m.split("__")[0] in DREWNO_SLOJE for m in sk.mat]
    if not any(wood):
        return
    nv = len(sk.v)
    par = list(range(nv))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    for f in sk.f:
        r0 = find(f[0])
        for i in f[1:]:
            ri = find(i)
            if ri != r0:
                par[ri] = r0
    comp = {}
    for fi, f in enumerate(sk.f):
        if wood[fi]:
            comp.setdefault(find(f[0]), []).append(fi)
    V = np.array(sk.v, np.float64)
    for root, fis in comp.items():
        vid = sorted({i for fi in fis for i in sk.f[fi]})
        Pc = V[vid]
        c0 = Pc.mean(0)
        w, E = np.linalg.eigh(np.cov((Pc - c0).T) + np.eye(3) * 1e-12)
        E = E[:, ::-1]
        proj = (Pc - c0) @ E
        ext = proj.max(0) - proj.min(0)
        # drobne części (< 0,4 m: segmenty jednej belki, kołki, kliny) – odcień i przesunięcie wspólne dla obiektu,
        # większe – własne (sąsiednie deski, stopnie, drągi różnią się)
        if ext[0] < 0.4:
            rng = np.random.default_rng(zlib.crc32(sk.nazwa.encode()) + seed)
        else:
            rng = np.random.default_rng(abs(hash((round(c0[0], 2), round(c0[1], 2), round(c0[2], 2), seed))) % (2 ** 32))
        du, dv = rng.uniform(0, 4.0), rng.uniform(0, 4.0)
        jas = 1.0 + rng.uniform(-0.08, 0.08)
        cie = rng.uniform(-0.03, 0.03)
        odc = (jas * (1 + cie), jas, jas * (1 - cie))
        STATYSTYKA_SLOJOW["elementy"] += 1
        wydl = ext[0] >= 2.5 * max(ext[1], 1e-6)
        if wydl:
            e1 = Vector(E[:, 0])
            zle, pole = 0.0, 0.0
            for fi in fis:
                P = [Vector(sk.v[i]) for i in sk.f[fi]]
                n = Vector((0, 0, 0))
                for k in range(len(P)):
                    n += P[k].cross(P[(k + 1) % len(P)])
                a = n.length / 2
                if a < 1e-9:
                    continue
                pole += a
                if abs(n.normalized().dot(e1)) > 0.7:
                    continue                        # czoło: kierunek dowolny
                g = _grad_uv(P, sk.uv[fi])
                if g is None:
                    zle += a
                    continue
                Pu, Pv = g
                lu, lv = Pu.length, Pv.length
                if lu < 1e-9 or lv < 1e-9 or max(lu, lv) / min(lu, lv) > 1.25 or abs(Pu.normalized().dot(e1)) < 0.906:
                    zle += a
            if pole > 0 and zle / pole > 0.2:
                STATYSTYKA_SLOJOW["poprawione"] += 1
                e2, e3 = Vector(E[:, 1]), Vector(E[:, 2])
                # przekrój okrągły: promień od osi stały w przekrojach (odchylenie < 10 % w przedziałach wzdłuż osi)
                t = proj[:, 0]
                r = np.hypot(proj[:, 1], proj[:, 2])
                okr = True
                bins = np.linspace(t.min(), t.max() + 1e-9, 9)
                for b0, b1 in zip(bins[:-1], bins[1:]):
                    m_ = (t >= b0) & (t < b1)
                    if m_.sum() >= 6 and r[m_].mean() > 1e-4 and r[m_].std() / r[m_].mean() > 0.10:
                        okr = False
                    if m_.sum() and m_.sum() < 6:
                        okr = False
                cv = Vector(c0)
                for fi in fis:
                    P = [Vector(sk.v[i]) for i in sk.f[fi]]
                    n = Vector((0, 0, 0))
                    for k in range(len(P)):
                        n += P[k].cross(P[(k + 1) % len(P)])
                    n = n.normalized() if n.length > 1e-12 else e3
                    if abs(n.dot(e1)) > 0.7:
                        uvs = [((p - cv).dot(e2), (p - cv).dot(e3)) for p in P]
                    elif okr:
                        ang = [math.atan2((p - cv).dot(e3), (p - cv).dot(e2)) for p in P]
                        for k in range(1, len(ang)):
                            while ang[k] - ang[0] > math.pi:
                                ang[k] -= 2 * math.pi
                            while ang[k] - ang[0] < -math.pi:
                                ang[k] += 2 * math.pi
                        rr = [math.hypot((p - cv).dot(e2), (p - cv).dot(e3)) for p in P]
                        rm = sum(rr) / len(rr)
                        uvs = [((p - cv).dot(e1), a_ * rm) for p, a_ in zip(P, ang)]
                    else:
                        ek = e2 if abs(n.dot(e2)) < abs(n.dot(e3)) else e3
                        uvs = [((p - cv).dot(e1), (p - cv).dot(ek)) for p in P]
                    sk.uv[fi] = tuple(uvs)
        for fi in fis:
            sk.uv[fi] = tuple((u + du, v + dv) for (u, v) in sk.uv[fi])
            if sk.odcien[fi] is None:
                sk.odcien[fi] = odc


def to_object(sk, kolekcja, origin=None, smooth_angle=None, weld=0.0, parent=None, recalc=False):
    """Siatka → obiekt Blendera. origin – punkt (Blender) dla osi obiektu (wierzchołki przesuwane)."""
    if not getattr(sk, "bez_slojow", False):
        sloje_wzdluz(sk)
    me = bpy.data.meshes.new(sk.nazwa)
    o = Vector(origin) if origin is not None else Vector((0, 0, 0))
    verts = [tuple(Vector(p) - o) for p in sk.v]
    mats = []
    for m in sk.mat:
        if m not in mats:
            mats.append(m)
    me.from_pydata(verts, [], sk.f)
    uvl = me.uv_layers.new(name="UVMap")
    uv = np.array([c for f in sk.uv for c in f], np.float64).reshape(-1, 2)
    tiles = {m: KAFLE.get(m, (1.0, 1.0)) for m in mats}
    tl = np.repeat(np.array([tiles[m] for m in sk.mat], np.float64), [len(f) for f in sk.f], axis=0)
    uvm = uv / tl
    # ściany o zerowym polu UV (szczyty toczeń i przeciągnięć, ściany prostopadłe do rzutu): rzut na płaszczyznę
    # prostopadłą do dominującej osi normalnej (metry / kafel) – inaczej cała ściana bierze jeden teksel
    if len(uvm) == len(me.loops):
        lt = np.array([len(f) for f in sk.f], np.int64)
        ls = np.r_[0, np.cumsum(lt)[:-1]]
        fl = np.repeat(np.arange(len(sk.f)), lt)
        nx = ls[fl] + (np.arange(len(fl)) - ls[fl] + 1) % lt[fl]
        a2 = np.abs(np.bincount(fl, uvm[:, 0] * uvm[nx, 1] - uvm[nx, 0] * uvm[:, 1], len(sk.f))) / 2
        V = np.array(verts, np.float64)
        vi = np.array([i for f in sk.f for i in f], np.int64)
        pv = V[vi]
        cr = np.cross(pv, pv[nx])
        nrm = np.zeros((len(sk.f), 3))
        for k in range(3):
            nrm[:, k] = np.bincount(fl, cr[:, k], len(sk.f))
        a3 = np.linalg.norm(nrm, axis=1) / 2
        tile_f = np.array([tiles[m] for m in sk.mat], np.float64)
        zle = np.where((a2 < 1e-12) & (a3 > 1e-7))[0]
        for fi in zle:
            ax = int(np.argmax(np.abs(nrm[fi])))
            osie = [k for k in range(3) if k != ax]
            l0, l1 = ls[fi], ls[fi] + lt[fi]
            uvm[l0:l1] = pv[l0:l1][:, osie] / tile_f[fi]
        if len(zle):
            UV_ZEROWE_NAPRAWIONE[sk.nazwa] = UV_ZEROWE_NAPRAWIONE.get(sk.nazwa, 0) + int(len(zle))
    data = uvm.astype(np.float32).ravel()
    if len(data) == len(me.loops) * 2:
        uvl.data.foreach_set("uv", data)
    # jeden slot na materiał (regiony malowania wskazujące ten sam materiał dzielą slot): zdublowane sloty myliły
    # Boolean (otwór steru, solver Manifold) – po nim pas furt dostawał materiał pokładu
    sloty, klucz_slot = [], {}
    for m in mats:
        bm_ = MATERIALY_REJESTR.get(m)
        if bm_ not in sloty:
            sloty.append(bm_)
        klucz_slot[m] = sloty.index(bm_)
    for bm_ in sloty:
        me.materials.append(bm_)
    idx = np.array([klucz_slot[m] for m in sk.mat], np.int32)
    me.polygons.foreach_set("material_index", idx)
    # odcień elementu / deski (mnożnik koloru, kolor wierzchołków w rogach ścian; łączony z 'zabrudzenia')
    od = getattr(sk, "odcien", None)
    if od and any(o is not None for o in od):
        at = me.color_attributes.new("odcien", "BYTE_COLOR", "CORNER")
        col = np.ones((len(me.loops), 4), np.float32)
        st = 0
        for f, oc in zip(sk.f, od):
            if oc is not None:
                col[st:st + len(f), :3] = oc          # jeden kolor na ścianę albo lista na narożnik
            st += len(f)
        at.data.foreach_set("color", col.ravel())
    sm = np.array([not fl for fl in sk.flat], bool)
    me.polygons.foreach_set("use_smooth", sm)
    me.validate(clean_customdata=False)
    me.update()
    ob = bpy.data.objects.new(sk.nazwa, me)
    ob.location = o
    kolekcja.objects.link(ob)
    if weld > 0:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld)
        bm.to_mesh(me)
        bm.free()
    if recalc:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        orientuj_na_zewnatrz(bm)
        bm.to_mesh(me)
        bm.free()
    if smooth_angle is not None:
        try:
            me.set_sharp_from_angle(angle=math.radians(smooth_angle))
        except Exception:
            pass
    if parent is not None:
        ob.parent = parent
        ob.matrix_parent_inverse = parent.matrix_world.inverted()
    return ob


def kolekcja(nazwa, rodzic=None):
    c = bpy.data.collections.get(nazwa)
    if c is None:
        c = bpy.data.collections.new(nazwa)
        (rodzic or bpy.context.scene.collection).children.link(c)
    return c


def empty(nazwa, loc, kol, rot=None, size=0.3, typ="PLAIN_AXES"):
    e = bpy.data.objects.new(nazwa, None)
    e.empty_display_type = typ
    e.empty_display_size = size
    e.location = loc
    if rot is not None:
        e.rotation_euler = rot
    kol.objects.link(e)
    return e


# ---------------------------------------------------------------- bryły

def frame_from_dir(d, up=Vector((0, 0, 1))):
    d = Vector(d).normalized()
    if abs(d.dot(up)) > 0.99:
        up = Vector((1, 0, 0))
    a = d.cross(up).normalized()
    b = a.cross(d).normalized()
    return a, b


def sweep(sk, path, prof, mat, closed_prof=True, cap0=True, cap1=True, up=None, scale=None, uv_u_scale=1.0,
          twist=None, flat=False, rope=False, u0=0.0, scale_b=None):
    """Przeciągnięcie profilu 2D (lista (a, b) w metrach, płaszczyzna prostopadła do ścieżki) wzdłuż ścieżki
    (lista Vector). Ramki transportowane równolegle (bez skręcania) albo z wektorem up (stałym lub listą).
    scale – lista mnożników profilu na punkt (zbieżność). UV: u – długość ścieżki, v – obwód profilu w metrach
    (rope=True: v = ułamek obwodu, u = długość / uv_u_scale)."""
    path = [Vector(p) for p in path]
    n = len(path)
    T = []
    for i in range(n):
        if i == 0:
            t = path[1] - path[0]
        elif i == n - 1:
            t = path[-1] - path[-2]
        else:
            t = (path[i + 1] - path[i]).normalized() + (path[i] - path[i - 1]).normalized()
        T.append(t.normalized())
    frames = []
    if up is None:
        a, b = frame_from_dir(T[0])
        # ramka początkowa w tej samej skrętności co następne (b = T × a). Wcześniej zostawało b = a × T
        # z frame_from_dir: pierwszy pierścień był lustrzanym odbiciem drugiego, więc pierwszy odcinek każdej rurki
        # (a przy ścieżce z dwóch punktów – cała lina, wanta, talrep, walec) był skręcony w „klepsydrę”: w połowie
        # długości przekrój spłaszczał się do zera, a w rurkach o nieparzystej liczbie boków jedna ścianka miała
        # zerowe pole i była usuwana przy porządkach siatek.
        b = T[0].cross(a).normalized()
        frames.append((a, b))
        for i in range(1, n):
            q = T[i - 1].rotation_difference(T[i])
            a = (q @ frames[-1][0]).normalized()
            b = T[i].cross(a).normalized()
            a = b.cross(T[i]).normalized()
            frames.append((a, b))
    else:
        for i in range(n):
            u = up[i] if isinstance(up, (list, tuple)) and len(up) == n and not isinstance(up[0], (int, float)) else up
            a = T[i].cross(Vector(u)).normalized()
            if a.length < 1e-6:
                a, b = frame_from_dir(T[i])
            else:
                b = a.cross(T[i]).normalized()
            frames.append((-a, b))
    m = len(prof)
    rings = []
    L = [0.0]
    for i in range(1, n):
        L.append(L[-1] + (path[i] - path[i - 1]).length)
    per = [0.0]
    for j in range(1, m + (1 if closed_prof else 0)):
        pa, pb = prof[(j - 1) % m], prof[j % m]
        per.append(per[-1] + math.hypot(pa[0] - pb[0], pa[1] - pb[1]))
    for i in range(n):
        a, b = frames[i]
        sc = scale[i] if scale is not None else 1.0
        tw = twist[i] if twist is not None else 0.0
        ct, st = math.cos(tw), math.sin(tw)
        ring = []
        for (pa, pb) in prof:
            qa = ct * pa - st * pb
            qb = st * pa + ct * pb
            scb = scale_b[i] if scale_b is not None else sc
            ring.append(path[i] + a * (qa * sc) + b * (qb * scb))
        rings.append(sk.verts(ring))
    jn = m if closed_prof else m - 1
    for i in range(n - 1):
        for j in range(jn):
            j2 = (j + 1) % m
            idx = [rings[i][j], rings[i + 1][j], rings[i + 1][j2], rings[i][j2]]
            if rope:
                v0, v1 = per[j] / per[-1], per[j + 1] / per[-1]
                uvs = [(u0 + L[i] / uv_u_scale, v0), (u0 + L[i + 1] / uv_u_scale, v0),
                       (u0 + L[i + 1] / uv_u_scale, v1), (u0 + L[i] / uv_u_scale, v1)]
            else:
                sc0 = scale[i] if scale is not None else 1.0
                sc1 = scale[i + 1] if scale is not None else 1.0
                uvs = [(u0 + L[i] * uv_u_scale, per[j] * sc0), (u0 + L[i + 1] * uv_u_scale, per[j] * sc1),
                       (u0 + L[i + 1] * uv_u_scale, per[j + 1] * sc1), (u0 + L[i] * uv_u_scale, per[j + 1] * sc0)]
            sk.face(idx, uvs, mat, flat)
    if closed_prof:
        if cap0:
            idx = list(reversed(rings[0]))
            sk.face_proj(idx, mat, flat=True)
        if cap1:
            sk.face_proj(list(rings[-1]), mat, flat=True)
    return rings


def circle_prof(r, sides, phase=0.0):
    return [(r * math.cos(2 * math.pi * k / sides + phase), r * math.sin(2 * math.pi * k / sides + phase))
            for k in range(sides)]


def rect_prof(w, h, cx=0.0, cy=0.0):
    return [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]


def tube(sk, path, r, mat, sides=8, cap=True, rope=True, lay=None):
    """Rurka (lina): u = długość / (2 skoki splotu), v = obwód."""
    if lay is None:
        lay = max(3.2 * 2 * r, 0.02)
    return sweep(sk, path, circle_prof(r, sides), mat, cap0=cap, cap1=cap, rope=rope, uv_u_scale=2 * lay)


def cylinder(sk, p0, p1, r0, r1, mat, sides=12, cap0=True, cap1=True, segs=1, prof=None, flat=False):
    p0, p1 = Vector(p0), Vector(p1)
    path = [p0.lerp(p1, i / segs) for i in range(segs + 1)]
    sc = [1.0 + (r1 / r0 - 1.0) * i / segs for i in range(segs + 1)]
    return sweep(sk, path, prof or circle_prof(r0, sides), mat, cap0=cap0, cap1=cap1, scale=sc, flat=flat)


def lathe(sk, prof_rz, mat, center, axis=Vector((0, 0, 1)), sides=16, uv_scale=1.0, flat=False, ref=None,
          close_ends=True, uv_obwod=False):
    """Bryła obrotowa: prof_rz – lista (r, h) wzdłuż osi. u – obwód (m), v – długość profilu (m)."""
    center = Vector(center)
    axis = Vector(axis).normalized()
    a, b = frame_from_dir(axis, ref or Vector((0, 0, 1)))
    rings = []
    for (r, h) in prof_rz:
        ring = []
        for k in range(sides):
            t = 2 * math.pi * k / sides
            ring.append(center + axis * h + (a * math.cos(t) + b * math.sin(t)) * r)
        rings.append(sk.verts(ring))
    L = [0.0]
    for i in range(1, len(prof_rz)):
        L.append(L[-1] + math.hypot(prof_rz[i][0] - prof_rz[i - 1][0], prof_rz[i][1] - prof_rz[i - 1][1]))
    for i in range(len(prof_rz) - 1):
        rr = max(prof_rz[i][0], prof_rz[i + 1][0], 0.01)
        circ = 2 * math.pi * rr
        for k in range(sides):
            k2 = (k + 1) % sides
            idx = [rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]]
            u0, u1 = circ * k / sides, circ * (k + 1) / sides
            if uv_obwod:                     # słoje po obwodzie (u = obwód)
                sk.face(idx, [(u0, L[i]), (u1, L[i]), (u1, L[i + 1]), (u0, L[i + 1])], mat, flat)
            else:
                sk.face(idx, [(L[i], u0), (L[i], u1), (L[i + 1], u1), (L[i + 1], u0)], mat, flat)
    if close_ends:
        if prof_rz[0][0] > 1e-4:
            sk.face_proj(list(reversed(rings[0])), mat, flat=True)
        if prof_rz[-1][0] > 1e-4:
            sk.face_proj(list(rings[-1]), mat, flat=True)
    elif len(prof_rz) > 2 and (abs(prof_rz[0][0] - prof_rz[-1][0]) > 1e-6 or abs(prof_rz[0][1] - prof_rz[-1][1]) > 1e-6):
        # profil otwarty (obręcz, okucie leżące na innej powierzchni): pas zamykający od ostatniego do pierwszego
        # punktu profilu – bryła zamknięta, ściana zamykająca leży na powierzchni pod okuciem (niewidoczna)
        n_ = len(prof_rz) - 1
        for k in range(sides):
            k2 = (k + 1) % sides
            sk.face_proj([rings[n_][k], rings[n_][k2], rings[0][k2], rings[0][k]], mat, flat=True)
    return rings


def dysk(sk, c, n, r, mat, sides=6, ref=None):
    """Płaski wielokąt foremny (otwór, łeb śruby) o normalnej n."""
    n = Vector(n).normalized()
    a, b = frame_from_dir(n, ref or Vector((0, 0, 1)))
    v = sk.verts([Vector(c) + (a * math.cos(2 * math.pi * k / sides) + b * math.sin(2 * math.pi * k / sides)) * r
                  for k in range(sides)])
    sk.face_proj(v, mat, flat=True)


def box(sk, center, size, mat, rot=None, flat=True, bevel=0.0):
    """Prostopadłościan: size (dx, dy, dz) w osiach Blendera, rot – Matrix 3x3 albo None. UV: u wzdłuż
    najdłuższej osi (słoje)."""
    c = Vector(center)
    R = rot if rot is not None else Matrix.Identity(3)
    hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    corners = [Vector((sx * hx, sy * hy, sz * hz)) for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)]
    vid = sk.verts([c + R @ p for p in corners])
    faces = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    longest = max(range(3), key=lambda k: size[k])
    for f in faces:
        pts = [corners[i] for i in f]
        n = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        nax = max(range(3), key=lambda k: abs(n[k]))
        axes = [k for k in range(3) if k != nax]
        ua = longest if longest in axes else axes[0]
        va = [k for k in axes if k != ua][0]
        uvs = [(p[ua], p[va]) for p in pts]
        sk.face([vid[i] for i in f], uvs, mat, flat)
    return vid


def oriented_box(sk, p0, p1, w, h, mat, up=Vector((0, 0, 1)), flat=True):
    """Belka od p0 do p1 o przekroju w × h (h wzdłuż 'up')."""
    p0, p1 = Vector(p0), Vector(p1)
    d = p1 - p0
    L = d.length
    x = d.normalized()
    y = Vector(up).cross(x)
    if y.length < 1e-6:
        y = Vector((0, 1, 0)).cross(x)
    y.normalize()
    z = x.cross(y).normalized()
    R = Matrix((x, y, z)).transposed()
    return box(sk, (p0 + p1) / 2, (L, w, h), mat, rot=R, flat=flat)


def rot_to(d, up=Vector((0, 0, 1))):
    """Macierz obrotu: lokalna oś Z → d, lokalna X możliwie poziomo."""
    z = Vector(d).normalized()
    x = Vector(up).cross(z)
    if x.length < 1e-6:
        x = Vector((1, 0, 0))
    x.normalize()
    y = z.cross(x).normalized()
    return Matrix((x, y, z)).transposed()


def ustaw_os(ob, pivot, z_dir=None, x_dir=None):
    """Przenosi oś obiektu do punktu pivot (Blender) i obraca ją tak, by lokalna Z = z_dir (oś obrotu części
    ruchomej), lokalna X możliwie wzdłuż x_dir; siatka zostaje na miejscu."""
    pivot = Vector(pivot)
    if z_dir is None:
        R = Matrix.Identity(3)
    else:
        z = Vector(z_dir).normalized()
        x = Vector(x_dir) if x_dir is not None else Vector((1, 0, 0))
        x = (x - z * x.dot(z))
        if x.length < 1e-6:
            x = Vector((0, 1, 0)) - z * z.y
        x.normalize()
        y = z.cross(x).normalized()
        R = Matrix((x, y, z)).transposed()
    M = Matrix.Translation(pivot) @ R.to_4x4()
    ob.data.transform(M.inverted() @ ob.matrix_world)
    ob.matrix_world = M
    ob.data.update()
    return ob


def solid_strip(sk, inner, outer, half_w, mats, caps=True, uv_scale=1.0):
    """Bryła wzdłuż krzywej w płaszczyźnie symetrii: inner[i], outer[i] – punkty (Vector) krawędzi wewn./zewn.,
    half_w[i] – półszerokość; mats[i] – materiał odcinka i→i+1. Cztery ściany + denka."""
    n = len(inner)
    rings = []
    for i in range(n):
        w = half_w[i]
        a, b = inner[i], outer[i]
        rings.append(sk.verts([a + Vector((w, 0, 0)), b + Vector((w, 0, 0)), b + Vector((-w, 0, 0)),
                               a + Vector((-w, 0, 0))]))
    L = [0.0]
    for i in range(1, n):
        L.append(L[-1] + (outer[i] - outer[i - 1]).length)
    for i in range(n - 1):
        r0, r1 = rings[i], rings[i + 1]
        for j in range(4):
            j2 = (j + 1) % 4
            q = [r0[j], r1[j], r1[j2], r0[j2]]
            sk.face_proj(q, mats[i])
    if caps:
        sk.face_proj(list(reversed(rings[0])), mats[0], flat=True)
        sk.face_proj(list(rings[-1]), mats[-1], flat=True)
    return rings


def polacz_bryly(ob, prog_pola=0.75):
    """Złożenie części nachodzących na siebie w jedną czystą bryłę (Intersect Boolean, union z samą sobą, solver
    EXACT): znikają ściany wewnętrzne i wnikające końce. Jeśli wynik traci więcej niż (1 − prog_pola) pola
    powierzchni (otwarte powierzchnie), zostaje stan sprzed operacji. Zwraca (zastosowano, krawędzie niemanifold)."""
    if ob.type != "MESH" or len(ob.data.polygons) == 0:
        return False, 0

    def pole(me):
        bm_ = bmesh.new()
        bm_.from_mesh(me)
        a_ = sum(f.calc_area() for f in bm_.faces)
        bm_.free()
        return a_
    def niemanifold(me):
        bm_ = bmesh.new()
        bm_.from_mesh(me)
        n_ = sum(1 for e in bm_.edges if len(e.link_faces) != 2)
        bm_.free()
        return n_
    zapas = ob.data.copy()
    a0 = pole(ob.data)
    nm0 = niemanifold(ob.data)
    vl = bpy.context.view_layer
    prev = vl.objects.active
    for o in vl.objects:
        if o.select_get():
            o.select_set(False)
    if ob.name not in vl.objects:
        return False, 0
    ob.select_set(True)
    vl.objects.active = ob
    try:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.remove_doubles(threshold=0.0002)
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.intersect_boolean(operation="UNION", use_self=True, solver="EXACT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.delete_loose()
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.dissolve_degenerate(threshold=0.00005)
        bpy.ops.object.mode_set(mode="OBJECT")
    except Exception:
        try:
            bpy.ops.object.mode_set(mode="OBJECT")
        except Exception:
            pass
    a1 = pole(ob.data)
    ok = a1 >= prog_pola * a0 and niemanifold(ob.data) <= nm0
    if not ok:
        # przywrócenie geometrii w tej samej siatce (siatka bywa współdzielona przez instancje – nie podmieniać)
        bm_ = bmesh.new()
        bm_.from_mesh(zapas)
        bm_.to_mesh(ob.data)
        bm_.free()
        ob.data.update()
    bpy.data.meshes.remove(zapas)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    if orientuj_na_zewnatrz(bm):
        bm.to_mesh(ob.data)
        ob.data.update()
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    ob.select_set(False)
    vl.objects.active = prev
    return ok, nm
