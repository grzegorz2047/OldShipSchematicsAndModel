"""Render the line layers for the drawing tutorial from the reference ship model.

Run inside Blender (background mode), on a COPY of the model file:

    blender -b --factory-startup ship_copy.blend --python render_lines.py -- \
        --out build/layers [--views side,bow,stern] [--res 2400x1270] [--passes all]

For every view it writes PNG layers (black strokes on a transparent background,
only the alpha channel matters) and one JSON file with the 2D guide shapes:

    <view>_<state>_new.png   lines added in that step
    <view>_<state>_old.png   lines from earlier steps (same occlusion)
    <view>_all.png           every line of the finished drawing
    <view>_sails_new/old.png set sails (bonus step)
    <view>_refl.png          reflection lines (mirrored camera, still mirrored)
    <view>_shade.png         grey shading render for hatching
    <view>_mask.png          silhouette mask of the ship above water
    <view>_dry.png           (side view) lines of the whole hull out of the water
    <view>_guides.json       guides, label anchors and numbers, in render pixels

The model is never saved; all changes live only in this Blender session.
"""
import bpy, bmesh, json, math, os, sys
import numpy as np
from mathutils import Vector, Matrix

# ---------------------------------------------------------------- arguments
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(name, default=None):
    if name in argv:
        return argv[argv.index(name) + 1]
    return default
OUT = os.path.abspath(arg('--out', 'layers'))
VIEWS = arg('--views', 'side,bow,stern').split(',')
RES = [int(v) for v in arg('--res', '2400x1270').split('x')]
PASSES = arg('--passes', 'all').split(',')
os.makedirs(OUT, exist_ok=True)
scene = bpy.context.scene
vl = bpy.context.view_layer

def want(p):
    return 'all' in PASSES or p in PASSES

# ---------------------------------------------------------------- groups
def objs(*names):
    out = []
    for n in names:
        if n.endswith('*'):
            out += [o for o in bpy.data.objects if o.name.startswith(n[:-1])]
        elif n in bpy.data.objects:
            out.append(bpy.data.objects[n])
    return [o for o in out if o.type == 'MESH' and not o.hide_render]

GROUPS = {
    'hull': objs('kadlub', 'kadlub_stepka', 'ster', 'kadlub_okucia_steru', 'pokrywa_trzonu',
                 'kadlub_reling', 'rufa_pawez', 'rufa_boki', 'galion', 'balustrada_progu'),
    'masts': objs('drzewca', 'bukszpryt'),
    'yards': objs('reja_*', 'rak_*', 'gafel', 'zagiel_*'),
    'rigging': objs('lina_sztagi', 'lina_wanty_fok', 'lina_wanty_grot', 'lina_wanty_stengowe',
                    'lina_wanty_bramstengowe', 'lina_paduny', 'lina_podwantki', 'lina_wyblinki',
                    'jufersy', 'lina_talrepy', 'sztagi_okucia', 'zagle_sztakslowe'),
    'details': objs('kadlub_listwy', 'furta_pokrywa_*', 'dzialo_*', 'dzialko_*', 'rufa_rzezby',
                    'latarnia_rufowa', 'galion_rzezby', 'kotbelki', 'kotwica_L', 'lodz', 'lina_lodz',
                    'kolo_sterowe', 'kolo_stojaki', 'lawy_wantowe', 'lina_wiazanie', 'kadlub_sciek_wregi',
                    'schody_rufowe', 'grodz_drzwi', 'kabestan_*', 'pompa_*', 'luk_*', 'nagielbank_*',
                    'kolkownice', 'szafka_kompasowa', 'dzwon*', 'zejsciowka', 'wyposazenie_drobne',
                    'okucia_pokladu', 'bloki', 'knagi_rufowe', 'bloki_kolo'),
}
# glass panes would only add duplicate frames
for g in GROUPS.values():
    g[:] = [o for o in g if not o.name.endswith('_szklo')]
ORDER = ['hull', 'masts', 'yards', 'rigging', 'details']
FURLED = [o for o in GROUPS['yards'] + GROUPS['rigging'] if o.name.startswith('zag')]
# thickness (px at 2400 wide) for (outline, crease); None = no crease lines
STYLE = {
    'hull': (3.6, 1.5), 'masts': (2.8, 1.2), 'yards': (2.3, 1.0), 'rigging': (1.25, None),
    'details': (2.0, 1.0), 'sails': (2.6, 1.0),
}
ALL_GROUP_OBJS = set(o for g in GROUPS.values() for o in g)
for o in bpy.data.objects:
    if o not in ALL_GROUP_OBJS:
        o.hide_render = True

# ---------------------------------------------------------------- geometry helpers
def world_verts(o):
    m = o.matrix_world
    return [m @ v.co for v in o.data.vertices]

def loose_parts(o):
    bm = bmesh.new(); bm.from_mesh(o.data); bm.transform(o.matrix_world)
    bm.verts.ensure_lookup_table()
    seen = set(); parts = []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack = [v]; comp = []; seen.add(v.index)
        while stack:
            a = stack.pop(); comp.append(a.co.copy())
            for e in a.link_edges:
                b = e.other_vert(a)
                if b.index not in seen:
                    seen.add(b.index); stack.append(b)
        parts.append(comp)
    bm.free()
    return parts

def bbox(points):
    a = np.array([tuple(p) for p in points])
    return a.min(0), a.max(0)

# masts: vertical segments of the spar mesh
def mast_info():
    segs = []
    for comp in loose_parts(bpy.data.objects['drzewca']):
        mn, mx = bbox(comp)
        if mx[2] - mn[2] > 4 and mx[0] - mn[0] < 0.7:
            segs.append((mn, mx))
    masts = {}
    for mn, mx in segs:
        yc = (mn[1] + mx[1]) / 2
        if yc < -5:
            key = 'fore'
        elif mx[1] - mn[1] < 0.5 and mx[2] < 13.5 and mn[0] > -0.15:
            key = 'snow'
        else:
            key = 'main'
        masts.setdefault(key, []).append((mn, mx))
    info = {}
    for k, lst in masts.items():
        lst.sort(key=lambda t: t[0][2])
        foot = Vector(((lst[0][0][0] + lst[0][1][0]) / 2, (lst[0][0][1] + lst[0][1][1]) / 2, lst[0][0][2]))
        top = Vector(((lst[-1][0][0] + lst[-1][1][0]) / 2, (lst[-1][0][1] + lst[-1][1][1]) / 2, lst[-1][1][2]))
        joints = [float(s[1][2]) for s in lst[:-1]]
        info[k] = {'foot': foot, 'top': top, 'joints': joints, 'segments': len(lst)}
    return info

MASTS = mast_info()

def bowsprit_axis():
    vs = world_verts(bpy.data.objects['bukszpryt'])
    heel = max(vs, key=lambda v: v.y - 0.3 * v.z)
    tip = min(vs, key=lambda v: v.y - 0.3 * v.z)
    return heel, tip
BSP = bowsprit_axis()

# ---------------------------------------------------------------- set sails (bonus step)
def yard(name):
    mn, mx = bbox(world_verts(bpy.data.objects[name]))
    c = Vector(((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2))
    return c, (mx[0] - mn[0]) / 2

def make_sheet(name, corners, belly, push, nu=14, nv=14):
    """corners: head-left, head-right, foot-right, foot-left (world). belly bulges along push."""
    hl, hr, fr, fl = corners
    verts = []; faces = []
    for j in range(nv + 1):
        t = j / nv
        for i in range(nu + 1):
            s = i / nu
            p = (hl.lerp(hr, s)).lerp(fl.lerp(fr, s), t)
            # bulge: zero on the head (on the yard), largest low in the middle
            b = belly * math.sin(math.pi * s) * math.sin(math.pi * min(1.0, t * 0.85 + 0.15)) * (0.35 + 0.65 * t)
            verts.append(p + push * b)
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            faces.append((a, a + 1, a + nu + 2, a + nu + 1))
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in verts], [], faces)
    ob = bpy.data.objects.new(name, me)
    return ob

def make_tri(name, a, b, c, belly, push, n=12):
    verts = []; faces = []; idx = {}
    for j in range(n + 1):
        for i in range(n + 1 - j):
            u = i / n; v = j / n; w = 1 - u - v
            p = a * w + b * u + c * v
            bb = belly * 6.0 * u * v * w * 1.5
            idx[(i, j)] = len(verts); verts.append(p + push * bb)
    for j in range(n):
        for i in range(n - j):
            faces.append((idx[(i, j)], idx[(i + 1, j)], idx[(i, j + 1)]))
            if i + 1 <= n - j - 1:
                faces.append((idx[(i + 1, j)], idx[(i + 1, j + 1)], idx[(i, j + 1)]))
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in verts], [], faces)
    return bpy.data.objects.new(name, me)

def stays():
    out = []
    for comp in loose_parts(bpy.data.objects['lina_sztagi']):
        lo = min(comp, key=lambda c: c.z); hi = max(comp, key=lambda c: c.z)
        out.append((lo, hi))
    return out

# ---------------------------------------------------------------- brace the yards
# The model has its yards squared (at anchor). For drawing we swing the square yards
# by a per-view angle (set_brace), so that yards and set sails show their faces.
YARD = {o.name: yard(o.name) for o in bpy.data.objects if o.name.startswith('reja_')}
ROT = Matrix.Identity(4)
YARD_KEYS = ('fok', 'fokmars', 'fokbram', 'grot', 'grotmars', 'grotbram', 'blinda')
BRACED_OBJS = {}   # object -> (yard name used as pivot, original matrix)
for key in YARD_KEYS:
    for nm in ('reja_' + key, 'rak_' + key, 'zagiel_' + key):
        if nm in bpy.data.objects:
            BRACED_OBJS[bpy.data.objects[nm]] = ('reja_' + key, bpy.data.objects[nm].matrix_world.copy())

def brace_pt(p, yname):
    if yname is None:
        return p.copy()
    c = YARD[yname][0]
    piv = Vector((0, c.y, 0))
    return (ROT @ (p - piv)) + piv

def yard_ends(yname, extra=0.0):
    c, hw = YARD[yname]
    a = Vector((-hw - extra, c.y, c.z)); b = Vector((hw + extra, c.y, c.z))
    return brace_pt(a, yname), brace_pt(b, yname)

def set_brace(deg):
    global ROT
    ROT = Matrix.Rotation(math.radians(deg), 4, 'Z')
    for ob, (yname, m0) in BRACED_OBJS.items():
        c = YARD[yname][0]
        piv = Vector((0, c.y, 0))
        ob.matrix_world = Matrix.Translation(piv) @ ROT @ Matrix.Translation(-piv) @ m0
    bpy.context.view_layer.update()

SAIL_CORNERS = {}
SAIL_PIVOT = {}
def build_sails():
    """Built with square yards; set_brace() swings them together with the yards."""
    coll = bpy.data.collections.new('tut_sails'); scene.collection.children.link(coll)
    fwd = Vector((0, -1, 0))  # wind from astern, sails bulge toward the bow
    made = []
    rows = [('fok', 'fokmars', 'fokbram'), ('grot', 'grotmars', 'grotbram')]
    for course, top, tg in rows:
        cy = {k: YARD['reja_' + k] for k in (course, top, tg)}
        deck_z = 3.4 if course == 'fok' else 3.6
        spec = [
            (tg, top, 0.92, 0.85),
            (top, course, 0.92, 0.88),
            (course, None, 0.92, 0.80),
        ]
        for head, foot, wh, wf in spec:
            hc, hw = cy[head]
            if foot:
                fc, fw = cy[foot]
                fz = fc.z + 0.25; fy = fc.y; fwid = fw * wf
            else:
                fz = deck_z + 1.6; fy = hc.y + 0.2; fwid = hw * wf
            hwid = hw * wh
            hy = 'reja_' + head; fyn = 'reja_' + (foot or head)
            hl = brace_pt(Vector((-hwid, hc.y, hc.z - 0.15)), hy); hr = brace_pt(Vector((hwid, hc.y, hc.z - 0.15)), hy)
            fl = brace_pt(Vector((-fwid, fy, fz)), fyn); fr = brace_pt(Vector((fwid, fy, fz)), fyn)
            h = hc.z - fz
            ob = make_sheet('setsail_' + head, (hl, hr, fr, fl), 0.13 * h, fwd)
            coll.objects.link(ob); made.append(ob)
            SAIL_CORNERS[head] = [hl, hr, fr, fl]; SAIL_PIVOT[head] = hy
            BRACED_OBJS[ob] = (hy, ob.matrix_world.copy())
    # spritsail under the bowsprit
    bc, bw = YARD['reja_blinda']
    hl = Vector((-bw * 0.9, bc.y, bc.z - 0.1)); hr = Vector((bw * 0.9, bc.y, bc.z - 0.1))
    fl = Vector((-bw * 0.95, bc.y + 0.6, bc.z - 3.3)); fr = Vector((bw * 0.95, bc.y + 0.6, bc.z - 3.3))
    ob = make_sheet('setsail_blinda', (hl, hr, fr, fl), 0.5, fwd); coll.objects.link(ob); made.append(ob)
    SAIL_CORNERS['blinda'] = [hl, hr, fr, fl]; SAIL_PIVOT['blinda'] = 'reja_blinda'
    BRACED_OBJS[ob] = ('reja_blinda', ob.matrix_world.copy())
    # gaff sail on the snow mast: throat, peak, clew, tack
    gv = world_verts(bpy.data.objects['gafel'])
    throat = min(gv, key=lambda v: v.y); peak = max(gv, key=lambda v: v.y)
    throat = Vector((0, throat.y + 0.1, throat.z - 0.1)); peak = Vector((0, peak.y - 0.2, peak.z - 0.1))
    tack = Vector((0, MASTS['snow']['foot'].y + 0.1, 4.6))
    clew = Vector((0, peak.y + 2.6, 5.2))
    ob = make_sheet('setsail_gaff', (throat, peak, clew, tack), 0.45, Vector((1, 0, 0)), 12, 12)
    coll.objects.link(ob); made.append(ob)
    SAIL_CORNERS['gaff'] = [throat, peak, clew, tack]
    # two head sails on the forestays that end out on the bowsprit / jib-boom
    fst = [s for s in stays() if s[0].y < -15.5 and s[1].z > 15 and abs(s[0].x) < 0.1]
    fst.sort(key=lambda s: s[0].y)
    for i, (lo, hi) in enumerate(fst[:2]):
        d = hi - lo
        tack = lo + d * 0.04
        head = lo + d * 0.80
        clew = Vector((0, tack.y + (head.y - tack.y) * 0.62 + 1.2, tack.z + 0.6 - i * 0.3))
        ob = make_tri('setsail_jib%d' % i, tack, head, clew, 0.5, Vector((1, 0, 0)))
        coll.objects.link(ob); made.append(ob)
        SAIL_CORNERS['jib%d' % i] = [tack, head, clew]
    for ob in made:
        ob.hide_render = True
    return made

SET_SAILS = build_sails()
GROUPS['sails'] = SET_SAILS

# ---------------------------------------------------------------- simplify ratlines: keep every third rung
def thin_ratlines(o, keep_every=3):
    bm = bmesh.new(); bm.from_mesh(o.data)
    bm.verts.ensure_lookup_table()
    seen = set(); comps = []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack = [v]; comp = []; seen.add(v.index)
        while stack:
            a = stack.pop(); comp.append(a)
            for e in a.link_edges:
                b = e.other_vert(a)
                if b.index not in seen:
                    seen.add(b.index); stack.append(b)
        comps.append(comp)
    m = o.matrix_world
    # sort rungs by (side, mast, height) so "every third" keeps an even ladder
    def key(c):
        p = sum((m @ v.co for v in c), Vector()) / len(c)
        return (round(p.x > 0), round(p.y / 4), p.z)
    comps.sort(key=key)
    kill = []
    for i, c in enumerate(comps):
        if i % keep_every:
            kill += c
    bmesh.ops.delete(bm, geom=list(set(kill)), context='VERTS')
    bm.to_mesh(o.data); bm.free()

# ---------------------------------------------------------------- water cut
def cut_below_water(o):
    if o.data.users > 1:
        o.data = o.data.copy()
    bm = bmesh.new(); bm.from_mesh(o.data)
    m = o.matrix_world; mi = m.inverted()
    bm.transform(m)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, 0), plane_no=(0, 0, 1), clear_inner=True)
    # close the cut so nobody can look into the hull from below (reflection camera)
    edges = [e for e in res['geom_cut'] if isinstance(e, bmesh.types.BMEdge) and e.is_valid
             and len(e.link_faces) == 1]
    if edges:
        try:
            bmesh.ops.holes_fill(bm, edges=edges, sides=0)
        except Exception as ex:
            print('holes_fill failed', o.name, ex)
    bm.transform(mi)
    bm.to_mesh(o.data); bm.free()

# ---------------------------------------------------------------- render setup
coll_of = {}
for g, lst in GROUPS.items():
    c = bpy.data.collections.new('tut_' + g + '_lines')
    scene.collection.children.link(c)
    for o in lst:
        try:
            c.objects.link(o)
        except RuntimeError:
            pass
    coll_of[g] = c

hold = bpy.data.materials.new('tut_holdout'); hold.use_nodes = True
nt = hold.node_tree; nt.nodes.clear()
hn = nt.nodes.new('ShaderNodeHoldout'); on = nt.nodes.new('ShaderNodeOutputMaterial')
nt.links.new(hn.outputs[0], on.inputs['Surface'])

white = bpy.data.materials.new('tut_white'); white.use_nodes = True
bsdf = white.node_tree.nodes.get('Principled BSDF')
bsdf.inputs['Base Color'].default_value = (0.8, 0.8, 0.8, 1)
bsdf.inputs['Roughness'].default_value = 0.9

r = scene.render
r.engine = 'BLENDER_EEVEE'
r.resolution_x, r.resolution_y = RES
r.resolution_percentage = 100
r.film_transparent = True
r.image_settings.file_format = 'PNG'
r.image_settings.color_mode = 'RGBA'
r.line_thickness_mode = 'ABSOLUTE'
r.line_thickness = 1.0
try:
    scene.eevee.taa_render_samples = 1
except Exception:
    pass
scene.view_settings.view_transform = 'Standard'
fs = vl.freestyle_settings
fs.crease_angle = math.radians(128)
fs.use_culling = False
fs.as_render_pass = False
SCALE = RES[0] / 2400.0

def clear_linesets():
    while len(fs.linesets):
        fs.linesets.remove(fs.linesets[0])

def add_lineset(group, crease):
    th = STYLE[group][1 if crease else 0]
    if th is None:
        return
    ls = fs.linesets.new('%s_%s' % (group, 'c' if crease else 'o'))
    ls.select_by_visibility = True; ls.visibility = 'VISIBLE'
    ls.select_by_edge_types = True; ls.select_by_face_marks = False
    ls.select_by_collection = True; ls.collection = coll_of[group]; ls.collection_negation = 'INCLUSIVE'
    for t in ('silhouette', 'border', 'crease', 'contour', 'external_contour', 'material_boundary',
              'edge_mark', 'suggestive_contour', 'ridge_valley'):
        setattr(ls, 'select_' + t, False)
    if crease:
        ls.select_crease = True
    else:
        ls.select_silhouette = True; ls.select_border = True; ls.select_external_contour = True
    st = ls.linestyle
    st.color = (0, 0, 0); st.thickness = th * SCALE; st.thickness_position = 'CENTER'
    st.caps = 'ROUND'; st.use_length_min = True; st.length_min = 3.0 * SCALE
    st.chaining = 'PLAIN'; st.use_same_object = True

def show_only(groups, extra_hide=()):
    vis = set(o for g in groups for o in GROUPS[g]) - set(extra_hide)
    for o in ALL_GROUP_OBJS | set(SET_SAILS):
        o.hide_render = o not in vis

def render_lines(path, line_groups, visible_groups, extra_hide=()):
    show_only(visible_groups, extra_hide)
    clear_linesets()
    n = 0
    for g in line_groups:
        for crease in (False, True):
            if STYLE[g][1 if crease else 0] is not None:
                add_lineset(g, crease); n += 1
    r.use_freestyle = True
    vl.material_override = hold
    vl.use_freestyle = True
    if n == 0:
        return
    r.filepath = path
    bpy.ops.render.render(write_still=True)
    print('wrote', path, flush=True)

# ---------------------------------------------------------------- camera
cam_data = bpy.data.cameras.new('tut_cam'); cam = bpy.data.objects.new('tut_cam', cam_data)
scene.collection.objects.link(cam); scene.camera = cam
cam_data.sensor_fit = 'HORIZONTAL'; cam_data.sensor_width = 36.0
cam_data.clip_start = 0.5; cam_data.clip_end = 2000

VIEWDEF = {
    # direction from ship to camera (deg from bow, measured towards starboard), lens, eye height
    # brace: how far the square yards are swung (deg), chosen so the sails face this camera
    'side':  {'az': 90.0, 'lens': 100.0, 'h': 3.0, 'brace': -30.0, 'margins': (0.04, 0.04, 0.06, 0.14)},
    'bow':   {'az': 52.0, 'lens': 50.0, 'h': 3.0, 'brace': -30.0, 'margins': (0.04, 0.04, 0.06, 0.14)},
    'stern': {'az': 128.0, 'lens': 50.0, 'h': 3.0, 'brace': 30.0, 'margins': (0.04, 0.04, 0.06, 0.14)},
}

def project_np(P):
    """world points (N,3) -> pixel coords (N,2), y down, using current camera."""
    M = np.array(cam.matrix_world.inverted())
    Ph = np.c_[P, np.ones(len(P))] @ M.T
    x, y, z = Ph[:, 0], Ph[:, 1], -Ph[:, 2]
    W, H = RES
    f = cam_data.lens / cam_data.sensor_width
    u = (f * x / z - cam_data.shift_x) * W + W / 2
    v = H / 2 - (f * y / z - cam_data.shift_y) * W
    return np.c_[u, v]

def check_projection():
    from bpy_extras.object_utils import world_to_camera_view
    p = Vector((1.0, -10.0, 12.0))
    a = proj(p)
    b = world_to_camera_view(scene, cam, p)
    print('projection check', a, (b.x * RES[0], (1 - b.y) * RES[1]), flush=True)

def proj(p):
    return [float(c) for c in project_np(np.array([tuple(p)]))[0]]

def place_camera(view, fit_points):
    d = VIEWDEF[view]
    a = math.radians(d['az'])
    # bow is -Y, starboard is -X
    dirv = Vector((-math.sin(a), -math.cos(a), 0))
    target = Vector((0, 0, d['h']))
    dist = 120.0
    cam_data.lens = d['lens']; cam_data.shift_x = 0; cam_data.shift_y = 0
    ml, mr, mt, mb = d['margins']
    W, H = RES
    for it in range(12):
        cam.location = target + dirv * dist
        cam.rotation_euler = (-dirv).to_track_quat('-Z', 'Y').to_euler()
        bpy.context.view_layer.update()
        uv = project_np(fit_points)
        x0, y0 = uv.min(0); x1, y1 = uv.max(0)
        sx = (x1 - x0) / (W * (1 - ml - mr)); sy = (y1 - y0) / (H * (1 - mt - mb))
        k = max(sx, sy)
        dist *= k ** 0.9
        cx = (x0 + x1) / 2; cy = (y0 + y1) / 2
        want_cx = W * (ml + (1 - ml - mr) / 2); want_cy = H * (mt + (1 - mt - mb) / 2)
        cam_data.shift_x += (cx - want_cx) / W
        cam_data.shift_y -= (cy - want_cy) / W
    cam.location = target + dirv * dist
    bpy.context.view_layer.update()
    return dirv, dist

def mirror_camera(on):
    loc = cam.location.copy()
    cam.location = Vector((loc.x, loc.y, -abs(loc.z) if on else abs(loc.z)))
    if on != getattr(mirror_camera, 'state', False):
        cam_data.shift_y = -cam_data.shift_y
    mirror_camera.state = on
    bpy.context.view_layer.update()

# ---------------------------------------------------------------- shading render
sun_d = bpy.data.lights.new('tut_sun', 'SUN'); sun_d.energy = 2.2; sun_d.angle = math.radians(2)
sun = bpy.data.objects.new('tut_sun', sun_d); scene.collection.objects.link(sun)
sun.hide_render = True

def render_shade(path, view, groups, extra_hide=()):
    show_only(groups, extra_hide)
    r.use_freestyle = False; vl.use_freestyle = False
    vl.material_override = white
    sun.hide_render = False
    # light from the upper left of the picture, a little from the viewer's side
    cd = (cam.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()   # towards camera
    right = (cam.matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized()
    ldir = (cd * 0.15 - right * 0.85 + Vector((0, 0, 0.75))).normalized()  # direction light comes from
    sun.rotation_euler = (-ldir).to_track_quat('-Z', 'Y').to_euler()
    world = scene.world or bpy.data.worlds.new('tut_world'); scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get('Background')
    if bg:
        bg.inputs[0].default_value = (0.06, 0.06, 0.06, 1); bg.inputs[1].default_value = 1.0
    try:
        scene.eevee.taa_render_samples = 16
    except Exception:
        pass
    r.filepath = path
    bpy.ops.render.render(write_still=True)
    print('wrote', path, flush=True)
    sun.hide_render = True
    try:
        scene.eevee.taa_render_samples = 1
    except Exception:
        pass

# ---------------------------------------------------------------- guides (3D -> 2D)
def hull_numbers():
    hv = world_verts(bpy.data.objects['kadlub']) + world_verts(bpy.data.objects['kadlub_reling'])
    A = np.array([tuple(v) for v in hv])
    above = A[A[:, 2] >= 0]
    stem_y = float(above[:, 1].min())
    head_y = float(min(v.y for v in world_verts(bpy.data.objects['galion']) if v.z >= 0))
    stern_y = float(max(v.y for v in world_verts(bpy.data.objects['rufa_pawez'])))
    beam = float(np.abs(A[:, 0]).max())
    mid = A[np.abs(A[:, 1]) < 1.0]
    rail_mid = float(mid[:, 2].max())
    bow = A[A[:, 1] < stem_y + 2.0]
    rail_bow = float(bow[:, 2].max())
    qd = [v for v in world_verts(bpy.data.objects['rufa_boki'])]
    qd_y = float(min(v.y for v in qd))
    stern_top = float(max(v.z for v in world_verts(bpy.data.objects['rufa_pawez'])))
    # waterline half-breadth near midships
    wl = above[(above[:, 2] < 0.15) & (np.abs(above[:, 1]) < 1.0)]
    wl_beam = float(np.abs(wl[:, 0]).max()) if len(wl) else beam
    return dict(stem_y=stem_y, head_y=head_y, stern_y=stern_y, beam=beam, rail_mid=rail_mid,
                rail_bow=rail_bow, qd_y=qd_y, stern_top=stern_top, wl_beam=wl_beam)

def build_guides(view, dirv):
    H = hull_numbers()
    W_, Hh = RES
    G = {'view': view, 'res': RES, 'items': [], 'anchors': {}, 'numbers': {}}
    def add(step, kind, pts3=None, pts2=None, closed=False, label=None, role='guide', **kw):
        pts = pts2 if pts2 is not None else [proj(p) for p in pts3]
        it = {'step': step, 'kind': kind, 'pts': pts, 'closed': closed, 'label': label, 'role': role}
        it.update(kw)
        G['items'].append(it)
    # horizon and vanishing points
    fwd = (cam.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
    hz = proj(cam.location + fwd * 1e5)[1]
    G['numbers']['horizon_y'] = hz
    add(1, 'line', pts2=[[0, hz], [W_, hz]], label='horizon', role='horizon')
    vps = {}
    if view != 'side':      # the pure side view has no useful vanishing points
        for name, d in (('vp_long', Vector((0, 1, 0))), ('vp_beam', Vector((1, 0, 0)))):
            # pick the direction that points away from the camera
            if d.dot(fwd) < 0:
                d = -d
            if abs(d.dot(fwd)) > 0.05:
                vps[name] = proj(cam.location + d * 1e6)
    G['numbers']['vps'] = vps
    # whole-ship rectangle (picture plane) from the final silhouette, filled in later from the mask
    # hull-length square grid on the centre plane
    L0, L1 = H['head_y'], H['stern_y']
    N = 7
    unit = (L1 - L0) / N
    top = MASTS['main']['top'].z
    rows = math.ceil(top / unit * 2) / 2.0     # whole or half squares
    G['numbers'].update(unit=unit, grid_cols=N, grid_rows=rows, hull_len=L1 - L0, main_top=top,
                        fore_top=MASTS['fore']['top'].z, beam=H['beam'] * 2)
    G['numbers']['mast_pos_units'] = {k: (MASTS[k]['foot'].y - L0) / unit for k in MASTS}
    G['numbers']['mast_top_units'] = {k: MASTS[k]['top'].z / unit for k in MASTS}
    G['numbers']['bowsprit_units'] = (L0 - BSP[1].y) / unit
    gridlines = []
    for i in range(N + 1):
        y = L0 + i * unit
        gridlines.append([Vector((0, y, 0)), Vector((0, y, rows * unit))])
    for j in range(int(rows) + 1):
        gridlines.append([Vector((0, L0, j * unit)), Vector((0, L1, j * unit))])
    if rows != int(rows):
        gridlines.append([Vector((0, L0, rows * unit)), Vector((0, L1, rows * unit))])
    for gl in gridlines:
        add(1, 'line', gl, role='grid')
    # waterline (centre plane), extended a bit
    add(1, 'line', [Vector((0, L0 - 9, 0)), Vector((0, L1 + 9, 0))], label='waterline', role='water')
    # mast position marks
    for k, m in MASTS.items():
        add(1, 'tick', [Vector((0, m['foot'].y, 0)), Vector((0, m['foot'].y, unit * 0.35))], role='mark', mast=k)
        add(1, 'tick', [Vector((0, m['top'].y, m['top'].z)), Vector((0, m['top'].y, m['top'].z))], role='dot', mast=k)
    add(1, 'tick', [BSP[1], BSP[1]], role='dot', mast='bowsprit')
    # step 2: hull blocks
    b = H['beam'] * 0.98; ys = H['stem_y'] + (L1 - L0) * 0.16; yq = H['qd_y']
    zr = H['rail_mid']; zb = H['rail_bow']; zs = H['stern_top']
    def box(x0, x1, y0, y1, z0, z1):
        c = [Vector((x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
        edges = [(0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)]
        return [[c[a], c[bb]] for a, bb in edges]
    for e in box(-b, b, ys, yq, 0, zr):
        add(2, 'line', e, role='block')
    for e in box(-b * 0.92, b * 0.92, yq, H['stern_y'], 0, zs):
        add(2, 'line', e, role='block')
    stem_top = Vector((0, H['stem_y'], zb)); stem_bot = Vector((0, H['stem_y'] + 0.6, 0))
    for sx in (-b, b):
        add(2, 'line', [Vector((sx, ys, 0)), stem_bot], role='block')
        add(2, 'line', [Vector((sx, ys, zb)), stem_top], role='block')
        add(2, 'line', [Vector((sx, ys, zr)), Vector((sx, ys, zb))], role='block')
    add(2, 'line', [stem_bot, stem_top], role='block')
    head = Vector((0, H['head_y'], (zb + 0.6) * 0.55))
    add(2, 'poly', [stem_top, head, Vector((0, H['stem_y'] + 0.3, 0.9))], role='block')
    # lines to the vanishing points (from the near box corners)
    vpl = []
    sd = -1 if cam.location.x < 0 else 1
    if vps:
        if cam.location.y < 0:      # bow view: near face is the forward end of the main box
            starts = [Vector((sd * b, ys, 0)), Vector((sd * b, ys, zr))]
        else:                       # stern view: the stern box
            starts = [Vector((sd * b * 0.92, H['stern_y'], 0)), Vector((sd * b * 0.92, H['stern_y'], zs))]
        for name, vp in vps.items():
            for s in starts:
                vpl.append([proj(s), vp])
    G['numbers']['vp_lines'] = vpl
    # mast axes and bowsprit axis
    for k, m in MASTS.items():
        add(2, 'line', [Vector((m['foot'].x, m['foot'].y, 0)), m['top']], role='axis', mast=k)
    add(2, 'line', [BSP[0], BSP[1]], role='axis', mast='bowsprit')
    # step 4: mast joints (where the next piece starts)
    for k, m in MASTS.items():
        for jz in m['joints']:
            p = Vector((m['foot'].x, m['foot'].y + (m['top'].y - m['foot'].y) * jz / m['top'].z, jz))
            add(4, 'cross', [p - Vector((0, 0.9, 0)), p + Vector((0, 0.9, 0))], role='mark')
            add(4, 'cross', [p - Vector((0.9, 0, 0)), p + Vector((0.9, 0, 0))], role='mark')
    # step 5: yard centre lines
    for o in GROUPS['yards']:
        if o.name.startswith('reja_'):
            add(5, 'line', list(yard_ends(o.name, 0.6)), role='axis')
    gv = world_verts(bpy.data.objects['gafel'])
    g0 = min(gv, key=lambda v: v.y); g1 = max(gv, key=lambda v: v.y)
    add(5, 'line', [g0 - (g1 - g0) * 0.08, g1 + (g1 - g0) * 0.08], role='axis')
    # step 6: shroud triangles (one per mast piece and side)
    for name in ('lina_wanty_fok', 'lina_wanty_grot', 'lina_wanty_stengowe', 'lina_wanty_bramstengowe'):
        vs = world_verts(bpy.data.objects[name])
        for side in (-1, 1):
            sv = [v for v in vs if v.x * side > 0.02]
            if not sv:
                continue
            # split by mast
            for lo_y, hi_y in ((-99, -4), (-4, 99)):
                mv = [v for v in sv if lo_y < v.y < hi_y]
                if len(mv) < 4:
                    continue
                apex = max(mv, key=lambda v: v.z)
                low = [v for v in mv if v.z < min(w.z for w in mv) + 1.2]
                f = min(low, key=lambda v: v.y); a_ = max(low, key=lambda v: v.y)
                add(6, 'poly', [apex, f, a_], closed=True, role='block', side=side)
    # step 7: gunport line, near side
    side = -1 if dirv.x < 0 else 1
    ports = [o for o in bpy.data.objects if o.name.startswith('furta_pokrywa_' + ('P' if side < 0 else 'L'))]
    pc = []
    for o in ports:
        mn, mx = bbox(world_verts(o))
        pc.append(Vector(((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2)))
    pc.sort(key=lambda v: v.y)
    if pc:
        add(7, 'poly', pc, role='axis')
    # step 9: sail outlines, straight first
    for k, cs in SAIL_CORNERS.items():
        add(9, 'poly', [brace_pt(p, SAIL_PIVOT.get(k)) for p in cs], closed=True, role='block')
    # label anchors (for the 'meet the ship' page)
    def ctr(name):
        mn, mx = bbox(world_verts(bpy.data.objects[name]))
        return Vector(((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2))
    A = G['anchors']
    fm = MASTS['fore']; mm = MASTS['main']; sm = MASTS['snow']
    A['foremast'] = proj(fm['foot'].lerp(fm['top'], 0.30))
    A['mainmast'] = proj(mm['foot'].lerp(mm['top'], 0.27))
    A['snowmast'] = proj(Vector((sm['foot'].x, sm['foot'].y, 8.6)))
    A['topmast'] = proj(Vector((0, mm['foot'].y + 0.2, 18.5)))
    A['top'] = proj(Vector((side * 1.5, mm['foot'].y + 0.9, 13.2)))
    A['bowsprit'] = proj(BSP[0].lerp(BSP[1], 0.45))
    e0, e1 = yard_ends('reja_grot')
    near_end = e0 if (e0.x * side) > 0 else e1
    A['yard'] = proj(Vector((0, YARD['reja_grot'][0].y, YARD['reja_grot'][0].z)).lerp(near_end, 0.85))
    A['furled_sail'] = proj(Vector((0, YARD['reja_grot'][0].y, YARD['reja_grot'][0].z + 0.3)).lerp(near_end, 0.35))
    A['gaff'] = proj(g0.lerp(g1, 0.6))
    shr = [v for v in world_verts(bpy.data.objects['lina_wanty_grot']) if v.x * side > 0]
    lo = min(shr, key=lambda v: v.z); hi = max(shr, key=lambda v: v.z)
    A['shrouds'] = proj(lo.lerp(hi, 0.35))
    st = sorted(stays(), key=lambda s: -(s[1].z - s[0].z))
    fore_stay = [s for s in stays() if s[1].z > 10 and s[1].z < 12.5 and s[0].y < -12]
    s0 = fore_stay[0] if fore_stay else st[0]
    A['stay'] = proj(s0[0].lerp(s0[1], 0.5))
    bs = [s for s in stays() if s[0].y > 1.0 and s[1].z > 20]
    if bs:
        A['stay2'] = proj(bs[0][0].lerp(bs[0][1], 0.5))
    pad = [v for v in world_verts(bpy.data.objects['lina_paduny']) if v.x * side > 0 and v.y > 0]
    if pad:
        lo = min(pad, key=lambda v: v.z); hi = max(pad, key=lambda v: v.z)
        A['backstay'] = proj(lo.lerp(hi, 0.3))
    rt = [v for v in world_verts(bpy.data.objects['lina_wyblinki']) if v.x * side > 0 and v.y < -4 and v.z < 9]
    if rt:
        A['ratlines'] = proj(sum(rt, Vector()) / len(rt))
    A['gunport'] = proj(pc[len(pc) // 2]) if pc else None
    A['rudder'] = proj(Vector((0, ctr('ster').y + 0.6, 1.0)))
    A['wheel'] = proj(ctr('kolo_sterowe') + Vector((0, 0, 0.5)))
    A['anchor'] = proj(ctr('kotwica_L') + Vector((0, 0, 0.5)))
    A['cathead'] = proj(Vector((side * 2.6, -12.8, 2.6)))
    A['head'] = proj(Vector((0, H['head_y'] + 0.6, 2.2)))
    A['stern'] = proj(Vector((side * 1.8, H['stern_y'] - 0.3, 2.7)))
    A['lantern'] = proj(ctr('latarnia_rufowa'))
    A['boat'] = proj(ctr('lodz'))
    A['wale'] = proj(Vector((side * H['beam'], -5.0, 1.0)))
    A['quarterdeck'] = proj(Vector((side * 2.5, 9.0, 4.0)))
    A['waterline'] = proj(Vector((side * H['wl_beam'], -2.0, 0)))
    A['hull'] = proj(Vector((side * H['beam'], 4.0, 1.8)))
    G['numbers']['hull'] = H
    return G

# ---------------------------------------------------------------- main
def fit_points():
    pts = []
    for g in ORDER + ['sails']:
        for o in GROUPS[g]:
            vs = world_verts(o)
            step = max(1, len(vs) // 400)
            pts += [tuple(v) for v in vs[::step] if v.z >= -0.05]
    return np.array(pts)

# out-of-water version of the hull first (side view only, for the 'common mistakes' page)
if 'side' in VIEWS and want('dry'):
    set_brace(VIEWDEF['side']['brace'])
    dirv, dist = place_camera('side', fit_points())
    render_lines(os.path.join(OUT, 'side_dry.png'), ['hull', 'masts', 'yards', 'rigging', 'details'],
                 ['hull', 'masts', 'yards', 'rigging', 'details'])

for g in ORDER:
    for o in GROUPS[g]:
        mn, mx = bbox(world_verts(o))
        if mn[2] < 0:
            cut_below_water(o)
thin_ratlines(bpy.data.objects['lina_wyblinki'])

for view in VIEWS:
    set_brace(VIEWDEF[view]['brace'])
    dirv, dist = place_camera(view, fit_points())
    print('view', view, 'dist', round(dist, 1), 'shift', cam_data.shift_x, cam_data.shift_y, flush=True)
    check_projection()
    G = build_guides(view, dirv)
    G['camera'] = {'location': list(cam.location), 'lens': cam_data.lens, 'shift': [cam_data.shift_x, cam_data.shift_y],
                   'matrix_world': [list(r_) for r_ in cam.matrix_world]}
    with open(os.path.join(OUT, view + '_guides.json'), 'w', encoding='utf-8') as f:
        json.dump(G, f, indent=1)
    p = lambda name: os.path.join(OUT, '%s_%s.png' % (view, name))
    for i, g in enumerate(ORDER):
        if want('steps') or want(g):
            vis = ORDER[:i + 1]
            render_lines(p(g + '_new'), [g], vis)
            render_lines(p(g + '_old'), ORDER[:i], vis)
    if want('final'):
        render_lines(p('all'), ORDER, ORDER)
    if want('sails'):
        vis = ORDER + ['sails']
        render_lines(p('sails_new'), ['sails'], vis, extra_hide=FURLED)
        render_lines(p('sails_old'), ORDER, vis, extra_hide=FURLED)
    if want('refl'):
        mirror_camera(True)
        render_lines(p('refl'), ['hull', 'masts', 'yards', 'details'], ORDER)
        render_lines(p('refl_sails'), ['hull', 'masts', 'yards', 'details', 'sails'], ORDER + ['sails'], extra_hide=FURLED)
        mirror_camera(False)
    if want('shade'):
        render_shade(p('shade'), view, ['hull', 'masts', 'yards', 'details'])
        render_shade(p('shade_sails'), view, ['hull', 'masts', 'yards', 'details', 'sails'], extra_hide=FURLED)
print('DONE', flush=True)
