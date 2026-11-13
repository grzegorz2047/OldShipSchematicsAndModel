# Niezależna kontrola: czy bloki i okucia olinowania nie wiszą w powietrzu.
# Test końców lin uznaje koniec za zamocowany, gdy dotyka bryły; nie sprawdza, czy sama bryła (blok) jest do czegoś
# przymocowana. Tutaj części obiektów blokowych są łączone w zespoły (części stykające się), a dla każdego zespołu
# liczone są styki z bryłami innymi niż bloki i liny oraz z linami (z kierunkiem, w którym lina odchodzi).
# Zespół podejrzany: nie dotyka żadnej bryły, liny stałej (sztag, wanta, padun) ani smołowanego wisiora, który się na
# nim kończy. Lina ruchoma załamująca się na bloku go nie trzyma (blok kierujący musi mieć zaczep); blok nawleczony
# na prostą, napiętą talię (lina przechodzi przez niego na wprost) trzyma talia.
# Użycie: blender -b --factory-startup --disable-autoexec plik.blend --python bloki_wiszace.py -- wynik.json [tol_m]
import bpy, bmesh, sys, json, time
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index('--') + 1:]
out_json = argv[0]
TOL = float(argv[1]) if len(argv) > 1 else 0.015
t0 = time.time()
dg = bpy.context.evaluated_depsgraph_get()
BLOKOWE = ('bloki',)


def rodzaj(name):
    if name.startswith('lina_'):
        return 'lina'
    if name.startswith(BLOKOWE):
        return 'blok'
    return 'bryla'


comps = []
for o in bpy.data.objects:
    if o.type != 'MESH' or o.hide_render or o.name.startswith('##'):
        continue
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    ev.to_mesh_clear()
    bm.transform(o.matrix_world)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0004)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.faces.ensure_lookup_table()
    seen = set()
    k = 0
    for f0 in bm.faces:
        if f0.index in seen:
            continue
        stack = [f0]
        seen.add(f0.index)
        faces = []
        while stack:
            f = stack.pop()
            faces.append(f)
            for e in f.edges:
                for lf in e.link_faces:
                    if lf.index not in seen:
                        seen.add(lf.index)
                        stack.append(lf)
        vid, vs, ts = {}, [], []
        mats = {}
        for f in faces:
            mats[f.material_index] = mats.get(f.material_index, 0) + 1
        mi = max(mats, key=mats.get)
        mat = o.material_slots[mi].material.name if mi < len(o.material_slots) and o.material_slots[mi].material else ''
        for f in faces:
            tri = []
            for v in f.verts:
                j = vid.get(v.index)
                if j is None:
                    j = vid[v.index] = len(vs)
                    vs.append(v.co[:])
                tri.append(j)
            ts.append(tri)
        if len(ts) < 2:
            continue
        v = np.array(vs, dtype=np.float64)
        comps.append({'ob': o.name, 'i': k, 'v': v, 't': ts, 'lo': v.min(axis=0), 'hi': v.max(axis=0),
                      'rodz': rodzaj(o.name), 'mat': mat})
        k += 1
    bm.free()
bl = [ci for ci, c in enumerate(comps) if c['rodz'] == 'blok']
print('CZESCI', len(comps), 'blokowych', len(bl), 'obiekty blokowe',
      sorted({comps[i]['ob'] for i in bl}), 'czas', round(time.time() - t0, 1))

CELL = 0.5
grid, bigs = {}, []
for ci, c in enumerate(comps):
    a = np.floor((c['lo'] - 0.05) / CELL).astype(int)
    b = np.floor((c['hi'] + 0.05) / CELL).astype(int)
    if int(np.prod(b - a + 1)) > 4000:
        bigs.append(ci)
        continue
    for x in range(a[0], b[0] + 1):
        for y in range(a[1], b[1] + 1):
            for z in range(a[2], b[2] + 1):
                grid.setdefault((x, y, z), set()).add(ci)


def bvh(c):
    if 'bvh' not in c:
        c['bvh'] = BVHTree.FromPolygons([Vector(p) for p in c['v']], c['t'], epsilon=0.0)
    return c['bvh']


def sasiedzi(ci):
    c = comps[ci]
    a = np.floor((c['lo'] - 0.05) / CELL).astype(int)
    b = np.floor((c['hi'] + 0.05) / CELL).astype(int)
    s = set(bigs)
    for x in range(a[0], b[0] + 1):
        for y in range(a[1], b[1] + 1):
            for z in range(a[2], b[2] + 1):
                s |= grid.get((x, y, z), set())
    s.discard(ci)
    return s


def odstep(ci, cj):
    """Najmniejszy odstęp między częściami (0, gdy się przecinają); liczone z wierzchołków obu stron."""
    a, b = comps[ci], comps[cj]
    if np.any(a['lo'] > b['hi'] + TOL) or np.any(b['lo'] > a['hi'] + TOL):
        return 9.0
    ta, tb = bvh(a), bvh(b)
    if ta.overlap(tb):
        return 0.0
    d = 9.0
    for p in a['v']:
        n = tb.find_nearest(Vector(p), TOL * 2)
        if n[0] is not None:
            d = min(d, n[3])
    if d > TOL and len(b['v']) < 4000:
        for p in b['v']:
            n = ta.find_nearest(Vector(p), TOL * 2)
            if n[0] is not None:
                d = min(d, n[3])
    return d


# styki części blokowych
styki = {ci: [] for ci in bl}
for ci in bl:
    for cj in sasiedzi(ci):
        d = odstep(ci, cj)
        if d <= TOL:
            styki[ci].append((cj, d))
# zespoły bloków (części blokowe stykające się ze sobą)
par = {ci: ci for ci in bl}


def find(x):
    while par[x] != x:
        par[x] = par[par[x]]
        x = par[x]
    return x


for ci in bl:
    for cj, d in styki[ci]:
        if comps[cj]['rodz'] == 'blok':
            par[find(ci)] = find(cj)
zesp = {}
for ci in bl:
    zesp.setdefault(find(ci), []).append(ci)
print('ZESPOLOW', len(zesp), 'czas', round(time.time() - t0, 1))

# drzewa całych obiektów (nie lin, nie bloków) do sprawdzenia, czy blok jest schowany w zamkniętej bryle
ob_trees = []
for o in bpy.data.objects:
    if o.type != 'MESH' or o.hide_render or o.name.startswith(('##', 'lina_', 'zagiel')) or o.name.startswith(BLOKOWE):
        continue
    me = o.data
    if not len(me.polygons):
        continue
    M = o.matrix_world
    bb = [M @ Vector(v) for v in o.bound_box]
    ob_trees.append((o.name, BVHTree.FromPolygons([M @ v.co for v in me.vertices], [tuple(q.vertices) for q in me.polygons]),
                     [min(v[i] for v in bb) for i in range(3)], [max(v[i] for v in bb) for i in range(3)]))
DIRS = [Vector((1, 0.013, 0.007)).normalized(), Vector((0.011, 1, 0.017)).normalized(), Vector((0.009, 0.015, 1)).normalized()]


def schowany(p):
    for nm, tr, blo, bhi in ob_trees:
        if any(p[i] < blo[i] or p[i] > bhi[i] for i in range(3)):
            continue
        g = 0
        for d in DIRS:
            k, q = 0, Vector(p)
            for _ in range(64):
                h = tr.ray_cast(q, d)
                if h[0] is None:
                    break
                k += 1
                q = h[0] + d * 1e-5
            g += k & 1
        if g >= 2:
            return nm
    return None


res = []
for root, cz in zesp.items():
    lo = np.min([comps[i]['lo'] for i in cz], axis=0)
    hi = np.max([comps[i]['hi'] for i in cz], axis=0)
    c0 = (lo + hi) / 2
    bryly, liny = {}, []
    for ci in cz:
        for cj, d in styki[ci]:
            o = comps[cj]
            if o['rodz'] == 'bryla':
                bryly[o['ob']] = min(bryly.get(o['ob'], 9.0), d)
            elif o['rodz'] == 'lina':
                # kierunek odejścia liny: najdalszy od bloku wierzchołek liny w promieniu 1,5 m od bloku
                w = o['v']
                dd = np.linalg.norm(w - c0, axis=1)
                m = dd < 1.5
                if m.any():
                    far = w[m][np.argmax(dd[m])]
                    kier = (far - c0) / max(1e-6, np.linalg.norm(far - c0))
                else:
                    kier = np.zeros(3)
                stala = o['ob'].startswith(('lina_sztagi', 'lina_wanty', 'lina_paduny', 'lina_podwantki'))
                # wisior: lina smołowana, której koniec (jeden z dwóch najdalszych punktów) leży przy bloku
                wisior = False
                if o['mat'].startswith('lina_smolowana') and not stala:
                    w2 = o['v']
                    i0 = int(np.argmax(np.linalg.norm(w2 - w2[0], axis=1)))
                    i1 = int(np.argmax(np.linalg.norm(w2 - w2[i0], axis=1)))
                    half = float(np.linalg.norm(hi - lo)) / 2 + 0.04
                    wisior = min(np.linalg.norm(w2[i0] - c0), np.linalg.norm(w2[i1] - c0)) <= half
                # talia na wprost: lina przechodzi przez blok bez załamania (wierzchołki liny po obu stronach bloku,
                # w przeciwnych kierunkach, co najmniej 15 cm od środka)
                na_wprost = False
                w3 = o['v']
                d3 = np.linalg.norm(w3 - c0, axis=1)
                m3 = (d3 < 1.0) & (d3 > 0.15)
                if m3.any():
                    W = w3[m3] - c0
                    p1 = W[np.argmax(np.linalg.norm(W, axis=1))]
                    u1 = p1 / np.linalg.norm(p1)
                    cosy = (W @ u1) / np.linalg.norm(W, axis=1)
                    na_wprost = bool(cosy.min() < -0.94)
                    # odległość osi liny od środka bloku mała (lina przez korpus)
                    if na_wprost:
                        t_ = (w3 - c0) @ u1
                        poprzeczna = np.linalg.norm((w3 - c0) - np.outer(t_, u1), axis=1)
                        na_wprost = bool(poprzeczna[d3 < 1.0].max() < 0.08)
                liny.append({'ob': o['ob'], 'i': o['i'], 'dz': round(float(kier[2]), 2), 'stala': bool(stala), 'wisior': bool(wisior),
                             'na_wprost': na_wprost})
    trzyma = [l for l in liny if l['stala'] or l['wisior']]
    w_bryle = schowany(Vector(c0))
    if w_bryle:
        st = 'schowany_w_bryle'
        bryly = dict(bryly, **{w_bryle: 0.0})
    elif bryly:
        st = 'bryla'
    elif trzyma:
        st = 'lina_stala_lub_wisior'
    elif sum(1 for l in liny if l['na_wprost']) >= 2:
        st = 'talia_na_wprost'
    elif liny:
        st = 'tylko_liny_ruchome'
    else:
        st = 'nic'
    res.append({'srodek': [round(float(x), 3) for x in c0], 'wymiar': round(float(np.linalg.norm(hi - lo)), 3),
                'czesci': len(cz), 'status': st, 'bryly': {k: round(v, 3) for k, v in bryly.items()}, 'liny': liny})
import collections
cnt = collections.Counter(r['status'] for r in res)
print('WYNIK', dict(cnt))
json.dump({'tol_m': TOL, 'zespolow': len(res), 'statusy': dict(cnt), 'zespoly': res}, open(out_json, 'w'),
          ensure_ascii=False, indent=1)
for r in res:
    if r['status'] in ('nic', 'tylko_liny_ruchome'):
        print('PODEJRZANY %-26s srodek %-26s wymiar %.2f liny %s' % (
            r['status'], r['srodek'], r['wymiar'], [(l['ob'][:22], l['dz']) for l in r['liny']]))
