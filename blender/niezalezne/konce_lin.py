# Niezależna kontrola: czy liny „latają”, czyli czy każdy koniec każdej liny jest do czegoś zamocowany.
# Obiekty o nazwie zaczynającej się od "lina_" są rozbijane na spójne części (jedna rurka = jedna lina albo odcinek).
# Końce rurki: środki otwartych pętli brzegowych; gdy rurka ma denka, dwa najdalsze od siebie pierścienie siatki.
# Koniec jest zamocowany, gdy leży przy powierzchni innej części (odstęp <= TOL), jest w środku zamkniętej bryły
# albo rurka przecina inną część w promieniu 0,3 m od końca. W przeciwnym razie koniec wisi w powietrzu.
# Użycie: blender -b --factory-startup --disable-autoexec plik.blend --python konce_lin.py -- wynik.json [tol_m]
import bpy, bmesh, sys, json, time
from collections import deque
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index('--') + 1:]
out_json = argv[0]
TOL = float(argv[1]) if len(argv) > 1 else 0.03
t0 = time.time()
dg = bpy.context.evaluated_depsgraph_get()


def is_rope(name):
    return name.startswith('lina_')


comps = []
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
        vid, vs, ts = {}, [], []
        closed = True
        bedges = []
        for f in faces:
            tri = []
            for v in f.verts:
                j = vid.get(v.index)
                if j is None:
                    j = vid[v.index] = len(vs)
                    vs.append(v.co[:])
                tri.append(j)
            ts.append(tri)
        for f in faces:
            for e in f.edges:
                if len(e.link_faces) != 2:
                    closed = False
                    if len(e.link_faces) == 1:
                        bedges.append((vid[e.verts[0].index], vid[e.verts[1].index]))
        if len(ts) < 2:
            continue
        v = np.array(vs, dtype=np.float64)
        comps.append({'ob': o.name, 'i': k, 'v': v, 't': ts, 'closed': closed, 'lo': v.min(axis=0), 'hi': v.max(axis=0),
                      'rope': is_rope(o.name), 'bedges': bedges})
        k += 1
    bm.free()
ropes = [ci for ci, c in enumerate(comps) if c['rope']]
print('CZESCI', len(comps), 'w tym lin', len(ropes), 'czas', round(time.time() - t0, 1))

CELL = 0.6
grid = {}
bigs = []
for ci, c in enumerate(comps):
    a = np.floor((c['lo'] - 0.35) / CELL).astype(int)
    b = np.floor((c['hi'] + 0.35) / CELL).astype(int)
    if int(np.prod(b - a + 1)) > 6000:
        bigs.append(ci)
        continue
    for x in range(a[0], b[0] + 1):
        for y in range(a[1], b[1] + 1):
            for z in range(a[2], b[2] + 1):
                grid.setdefault((x, y, z), []).append(ci)


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


def ends_of(c):
    """Lista (środek, promień) końców rurki."""
    v = c['v']
    if c['bedges']:
        adj = {}
        for a, b in c['bedges']:
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
        seen, out = set(), []
        for s in adj:
            if s in seen:
                continue
            loop, st = [], [s]
            seen.add(s)
            while st:
                x = st.pop()
                loop.append(x)
                for y in adj[x]:
                    if y not in seen:
                        seen.add(y)
                        st.append(y)
            p = v[loop].mean(axis=0)
            r = float(np.linalg.norm(v[loop] - p, axis=1).mean())
            out.append((p, r))
        return out
    # rurka z denkami: dwa najdalsze pierścienie (podwójne przeszukiwanie wszerz po krawędziach)
    nb = [[] for _ in range(len(v))]
    for t in c['t']:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            nb[a].append(b)
            nb[b].append(a)

    def bfs(src):
        dist = [-1] * len(v)
        dist[src] = 0
        q = deque([src])
        last = src
        while q:
            x = q.popleft()
            last = x
            for y in nb[x]:
                if dist[y] < 0:
                    dist[y] = dist[x] + 1
                    q.append(y)
        return dist, last

    _, a = bfs(0)
    da, b = bfs(a)
    db, _ = bfs(b)
    out = []
    for dist in (da, db):
        m = max(dist)
        ring = [i for i, d in enumerate(dist) if d >= m - 1]
        p = v[ring].mean(axis=0)
        r = float(np.linalg.norm(v[ring] - p, axis=1).mean())
        out.append((p, r))
    # pętla zamknięta (zwój): oba „końce” wypadają w tym samym miejscu albo rurka nie ma końców – zgłoś jako zwój
    return out


def candidates(p):
    k = tuple(np.floor(np.asarray(p) / CELL).astype(int))
    return set(grid.get(k, [])) | set(bigs)


res = []
stat = {}
for ci in ropes:
    c = comps[ci]
    ends = ends_of(c)
    tc = bvh(c)
    for (p, r) in ends:
        pv = Vector(p)
        best_solid, best_rope = (9.0, None), (9.0, None)
        how = None
        for cj in candidates(p):
            if cj == ci:
                continue
            o = comps[cj]
            if np.any(p < o['lo'] - 0.35) or np.any(p > o['hi'] + 0.35):
                continue
            tb = bvh(o)
            near = tb.find_nearest(pv, 0.35)
            d = near[3] if near[0] is not None else 9.0
            if o['closed'] and not o['rope'] and d > r + TOL and np.all(p > o['lo']) and np.all(p < o['hi']) and inside(tb, p):
                d = 0.0   # koniec schowany w bryle
            if d > r + TOL:
                # rurka przecina tę część blisko końca?
                ov = tc.overlap(tb)
                for ia, _ in ov:
                    q = c['v'][c['t'][ia]].mean(axis=0)
                    if np.linalg.norm(q - p) < 0.30:
                        d = min(d, r)
                        break
            if o['rope']:
                if d < best_rope[0]:
                    best_rope = (d, o['ob'])
            else:
                if d < best_solid[0]:
                    best_solid = (d, o['ob'])
        gap_solid = best_solid[0] - r
        gap_rope = best_rope[0] - r
        if gap_solid <= TOL:
            status = 'bryla'
        elif gap_rope <= TOL:
            status = 'lina'
        else:
            status = 'powietrze'
        res.append({'ob': c['ob'], 'i': c['i'], 'p': [round(float(x), 3) for x in p], 'r': round(r, 4), 'status': status,
                    'odstep_bryla': round(float(gap_solid), 3) if best_solid[1] else None, 'bryla': best_solid[1],
                    'odstep_lina': round(float(gap_rope), 3) if best_rope[1] else None, 'lina': best_rope[1],
                    'koncow': len(ends), 'tris': len(c['t'])})
        s = stat.setdefault(c['ob'] if not c['ob'].startswith('lina_dyn_') else 'lina_dyn_*', {'bryla': 0, 'lina': 0, 'powietrze': 0})
        s[status] += 1
print('KONCE', len(res), 'czas', round(time.time() - t0, 1))
fly = [r for r in res if r['status'] == 'powietrze']
json.dump({'tol_m': TOL, 'koncow': len(res), 'w_powietrzu': len(fly), 'po_obiektach': stat, 'konce': res},
          open(out_json, 'w'), ensure_ascii=False, indent=1)
print('%-28s %7s %7s %9s' % ('obiekt', 'bryla', 'lina', 'powietrze'))
for k in sorted(stat):
    s = stat[k]
    print('%-28s %7d %7d %9d' % (k, s['bryla'], s['lina'], s['powietrze']))
print('W POWIETRZU', len(fly), 'z', len(res))
for r in sorted(fly, key=lambda r: -min(x for x in (r['odstep_bryla'], r['odstep_lina'], 9.0) if x is not None)):
    print('WISI %-26s cz %4d punkt %-26s promien %.3f  do bryly %s (%s)  do liny %s (%s)' % (
        r['ob'], r['i'], r['p'], r['r'], r['odstep_bryla'], r['bryla'], r['odstep_lina'], r['lina']))
