# Skręcone ściany rurek lin: czworokąt, którego dwa trójkąty mają normalne w różne strony (rurka „klepsydra”).
# Użycie: blender -b --factory-startup --disable-autoexec plik.blend --python skrecone.py
import bpy, bmesh
tot = {}
for o in bpy.data.objects:
    if o.type != 'MESH' or o.name.startswith('##'):
        continue
    bm = bmesh.new(); bm.from_mesh(o.data)
    q = zle = 0
    dl = 0.0
    for f in bm.faces:
        if len(f.verts) != 4:
            continue
        q += 1
        v = [x.co for x in f.verts]
        n1 = (v[1] - v[0]).cross(v[2] - v[0])
        n2 = (v[2] - v[0]).cross(v[3] - v[0])
        if n1.length < 1e-12 or n2.length < 1e-12 or n1.normalized().dot(n2.normalized()) < 0.5:
            zle += 1
            dl += max((v[1] - v[0]).length, (v[2] - v[1]).length)
    bm.free()
    k = 'lina_dyn_*' if o.name.startswith('lina_dyn') else o.name
    t = tot.setdefault(k, [0, 0, 0.0])
    t[0] += q; t[1] += zle; t[2] += dl
print('%-28s %8s %8s %10s' % ('obiekt', 'czworok', 'skrecone', 'dlugosc_m'))
for k in sorted(tot):
    if tot[k][1] == 0: continue
    print('WIERSZ %-28s %8d %8d %10.1f' % (k, tot[k][0], tot[k][1], tot[k][2]))
print('RAZEM', sum(t[0] for t in tot.values()), sum(t[1] for t in tot.values()))
