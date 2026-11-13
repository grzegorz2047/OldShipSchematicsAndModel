# Niezależna kontrola przenikania brył w pliku .blend statku.
# Każdy obiekt siatkowy jest rozbijany na spójne części (po zszyciu wierzchołków), a pary części o zachodzących
# obwiedniach są sprawdzane drzewami BVH: liczba przecinających się par trójkątów oraz głębokość wniknięcia
# (wierzchołki jednej części wewnątrz drugiej, gdy ta jest zamkniętą bryłą; odległość do jej powierzchni).
# Wynik: JSON z parami części i zestawienie po parach obiektów, posortowane po głębokości.
# Użycie: blender -b --factory-startup --disable-autoexec plik.blend --python przenikanie.py -- wynik.json [próg_m]
import bpy, bmesh, sys, json, time
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index('--') + 1:]
out_json = argv[0]
THR = float(argv[1]) if len(argv) > 1 else 0.005
t0 = time.time()
dg = bpy.context.evaluated_depsgraph_get()

comps = []   # {'ob', 'i', 'v' (np n×3), 't' (list of triples), 'closed', 'lo', 'hi'}
for o in bpy.data.objects:
    if o.type != 'MESH' or o.hide_render:
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
        vid = {}
        vs = []
        ts = []
        closed = True
        for f in faces:
            tri = []
            for v in f.verts:
                j = vid.get(v.index)
                if j is None:
                    j = vid[v.index] = len(vs)
                    vs.append(v.co[:])
                tri.append(j)
            ts.append(tri)
            for e in f.edges:
                if len(e.link_faces) != 2:
                    closed = False
        if len(ts) < 2:
            continue
        v = np.array(vs, dtype=np.float64)
        comps.append({'ob': o.name, 'i': k, 'v': v, 't': ts, 'closed': closed, 'lo': v.min(axis=0), 'hi': v.max(axis=0)})
        k += 1
    bm.free()
print('CZESCI', len(comps), 'zamknietych', sum(1 for c in comps if c['closed']), 'czas', round(time.time() - t0, 1))

# kandydaci: siatka przestrzenna 0,6 m
CELL = 0.6
grid = {}
for ci, c in enumerate(comps):
    a = np.floor(c['lo'] / CELL).astype(int)
    b = np.floor(c['hi'] / CELL).astype(int)
    n = int(np.prod(b - a + 1))
    c['big'] = n > 6000
    if c['big']:
        continue
    for x in range(a[0], b[0] + 1):
        for y in range(a[1], b[1] + 1):
            for z in range(a[2], b[2] + 1):
                grid.setdefault((x, y, z), []).append(ci)
pairs = set()
for cell in grid.values():
    if len(cell) < 2:
        continue
    for ia in range(len(cell)):
        for ib in range(ia + 1, len(cell)):
            pairs.add((cell[ia], cell[ib]))
bigs = [ci for ci, c in enumerate(comps) if c['big']]
for bi in bigs:
    for ci in range(len(comps)):
        if ci != bi:
            pairs.add((min(ci, bi), max(ci, bi)))

def overlap_box(a, b, m=0.0):
    return bool(np.all(a['lo'] < b['hi'] - m) and np.all(b['lo'] < a['hi'] - m))

def bvh(c):
    if 'bvh' not in c:
        c['bvh'] = BVHTree.FromPolygons([Vector(p) for p in c['v']], c['t'], epsilon=0.0)
    return c['bvh']

DIRS = [Vector((1, 0.013, 0.007)).normalized(), Vector((0.011, 1, 0.017)).normalized(), Vector((0.009, 0.015, 1)).normalized()]
def inside(tree, p):
    votes = 0
    for d in DIRS:
        n = 0
        o = Vector(p)
        for _ in range(64):
            hit = tree.ray_cast(o, d)
            if hit[0] is None:
                break
            n += 1
            o = hit[0] + d * 1e-5
        votes += n & 1
    return votes >= 2

def depth_into(a, b):
    """Największa głębokość wierzchołków części a wewnątrz zamkniętej części b oraz punkt."""
    if not b['closed']:
        return None, None
    m = np.all((a['v'] > b['lo']) & (a['v'] < b['hi']), axis=1)
    idx = np.nonzero(m)[0]
    if len(idx) > 500:
        idx = idx[:: len(idx) // 500 + 1]
    tb = bvh(b)
    best, bp = 0.0, None
    for j in idx:
        p = a['v'][j]
        if inside(tb, p):
            near = tb.find_nearest(Vector(p))
            if near[0] is not None and near[3] > best:
                best, bp = near[3], p
    return best, bp

res = []
tested = 0
for (ia, ib) in pairs:
    a, b = comps[ia], comps[ib]
    if not overlap_box(a, b, 0.0):
        continue
    tested += 1
    ov = bvh(a).overlap(bvh(b))
    if not ov:
        continue
    dab, pab = depth_into(a, b)
    dba, pba = depth_into(b, a)
    cand = [(d, p) for d, p in ((dab, pab), (dba, pba)) if d is not None]
    depth = max((d for d, _ in cand), default=None)
    pt = None
    if depth:
        pt = [p for d, p in cand if d == depth][0]
    if pt is None:
        tri = a['t'][ov[0][0]]
        pt = a['v'][tri].mean(axis=0)
    res.append({'a': a['ob'], 'ai': a['i'], 'b': b['ob'], 'bi': b['i'], 'pary_trojkatow': len(ov),
                'glebokosc': None if depth is None else round(float(depth), 4),
                'punkt': [round(float(x), 3) for x in pt], 'a_zamk': a['closed'], 'b_zamk': b['closed'],
                'a_tris': len(a['t']), 'b_tris': len(b['t'])})
print('PARY kandydatow', len(pairs), 'sprawdzone', tested, 'przecinajace', len(res), 'czas', round(time.time() - t0, 1))

# zestawienie po parach obiektów
agg = {}
for r in res:
    key = tuple(sorted((r['a'], r['b'])))
    g = agg.setdefault(key, {'obiekty': list(key), 'par_czesci': 0, 'par_trojkatow': 0, 'glebokosc_max': None, 'bez_pomiaru': 0, 'punkt': None})
    g['par_czesci'] += 1
    g['par_trojkatow'] += r['pary_trojkatow']
    if r['glebokosc'] is None:
        g['bez_pomiaru'] += 1
        if g['punkt'] is None:
            g['punkt'] = r['punkt']
    elif g['glebokosc_max'] is None or r['glebokosc'] > g['glebokosc_max']:
        g['glebokosc_max'] = r['glebokosc']
        g['punkt'] = r['punkt']
rows = sorted(agg.values(), key=lambda g: -(g['glebokosc_max'] if g['glebokosc_max'] is not None else 0.0))
json.dump({'prog_m': THR, 'czesci': len(comps), 'pary_czesci': res, 'pary_obiektow': rows}, open(out_json, 'w'), ensure_ascii=False, indent=1)
deep = [g for g in rows if g['glebokosc_max'] is not None and g['glebokosc_max'] > THR]
print('PAR OBIEKTOW przecinajacych', len(rows), 'z wniknieciem ponad prog', len(deep), 'bez pomiaru glebokosci', len([g for g in rows if g['glebokosc_max'] is None]))
for g in rows:
    d = g['glebokosc_max']
    print('PARA %-26s %-26s czesci %4d trojkaty %5d glebokosc %s punkt %s' % (
        g['obiekty'][0], g['obiekty'][1], g['par_czesci'], g['par_trojkatow'],
        ('%.3f' % d) if d is not None else '  ?  ', g['punkt']))
