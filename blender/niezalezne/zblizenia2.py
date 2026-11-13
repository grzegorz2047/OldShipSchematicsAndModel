# Zbliżenia z GLB według listy kadrów w pliku JSON: {"nazwa": [[cel x,y,z], [kamera x,y,z], obiektyw_mm?], ...}
# Współrzędne jak w pliku .blend (x w poprzek, y ku rufie, z w górę).
# Użycie: blender -b --factory-startup --python zblizenia2.py -- model.glb katalog kadry.json
import bpy, sys, os, math, json
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
# ścieżki bezwzględne: Blender rozwija ścieżki względne od katalogu dysku, nie od katalogu roboczego
src, out, kadry = os.path.abspath(argv[0]), os.path.abspath(argv[1]), json.load(open(argv[2], encoding='utf-8'))
os.makedirs(out, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
scene = bpy.context.scene
for name in ('BLENDER_EEVEE', 'BLENDER_EEVEE_NEXT'):
    try:
        scene.render.engine = name
        break
    except Exception:
        pass
scene.render.resolution_x = 1300
scene.render.resolution_y = 900
scene.render.image_settings.file_format = 'PNG'
try:
    scene.view_settings.view_transform = 'Standard'
except Exception:
    pass
world = bpy.data.worlds.new('w'); scene.world = world; world.use_nodes = True
bg = world.node_tree.nodes.get('Background')
bg.inputs[0].default_value = (0.75, 0.82, 0.92, 1.0); bg.inputs[1].default_value = 1.1
sd = bpy.data.lights.new('sun', 'SUN'); sd.energy = 3.0
sun = bpy.data.objects.new('sun', sd); scene.collection.objects.link(sun)
sun.rotation_euler = (math.radians(48), math.radians(6), math.radians(-150))
cd = bpy.data.cameras.new('cam'); cd.clip_start = 0.02; cd.clip_end = 300
cam = bpy.data.objects.new('cam', cd); scene.collection.objects.link(cam); scene.camera = cam
for name, v in kadry.items():
    t, p = Vector(v[0]), Vector(v[1])
    cd.lens = v[2] if len(v) > 2 else 32
    cam.location = p
    cam.rotation_euler = (t - p).normalized().to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = os.path.join(out, name + '.png')
    bpy.ops.render.render(write_still=True)
    print('WROTE', scene.render.filepath)
