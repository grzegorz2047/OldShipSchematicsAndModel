# Igły (trójkąty o stosunku najdłuższej krawędzi do wysokości > 40) z podziałem: na płaskiej ściance (sąsiedzi przez
# krawędź współpłaszczyznowi albo za ostrą krawędzią > 30°) i na powierzchni gładko cieniowanej (krzywej).
import bpy, bmesh, math
tot = {}
for o in bpy.data.objects:
    if o.type != 'MESH' or o.name.startswith(('##', 'lina_', 'zagiel', 'zagle', 'lodz_maska')) or o.name.endswith('_szklo'):
        continue
    if o.users_collection and o.users_collection[0].name == '_eksport':
        continue
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.normal_update()
    n = k = 0
    for f in bm.faces:
        a, b, c = (v.co for v in f.verts)
        ls = [(a - b).length, (b - c).length, (c - a).length]
        L = max(ls); ar = f.calc_area()
        if L > 0.05 and ar > 0 and L / (2 * ar / L) > 40:
            n += 1
            krzywa = False
            for e in f.edges:
                for g in e.link_faces:
                    if g is f: continue
                    d = f.normal.dot(g.normal)
                    if 0.866 < d < 0.9994:
                        krzywa = True
            k += krzywa
    bm.free()
    if n: tot[o.name] = (n, k)
print('RAZEM igly', sum(v[0] for v in tot.values()), 'na gladko cieniowanych', sum(v[1] for v in tot.values()))
for nm, (n, k) in sorted(tot.items(), key=lambda x: -x[1][1])[:14]:
    print('OB %-26s igly %5d krzywe %5d' % (nm, n, k))
