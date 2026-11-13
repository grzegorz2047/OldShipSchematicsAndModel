"""Shared local geometry primitives for the independent 1715 sloop asset.
Adapted from the MIT-licensed game-asset helpers; no dependency on PR #1.
"""

import math
import hashlib
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector
import numpy as np

RIGGING_PATHS = {}


def new_mesh(name, verts, faces, material=None, uv=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    ASSET.objects.link(obj)
    if material:
        mesh.materials.append(material)
    if uv:
        layer = mesh.uv_layers.new(name="UVMap")
        for poly in mesh.polygons:
            for li in poly.loop_indices:
                layer.data[li].uv = uv[mesh.loops[li].vertex_index]
    for poly in mesh.polygons:
        poly.use_smooth = True
    return obj


def tube(name, points, diameter, material, sides=5):
    points = [Vector(p) for p in points]
    # Coincident endpoints must not create degenerate rings/faces.
    points = [
        p for i, p in enumerate(points) if not i or (p - points[i - 1]).length > 1e-5
    ]
    if len(points) < 2:
        return None
    verts, faces = [], []
    for i, p in enumerate(points):
        tangent = points[min(i + 1, len(points) - 1)] - points[max(i - 1, 0)]
        tangent.normalize()
        normal = tangent.cross(Vector((0, 0, 1)))
        if normal.length < 0.01:
            normal = tangent.cross(Vector((1, 0, 0)))
        normal.normalize()
        second = tangent.cross(normal).normalized()
        for j in range(sides):
            a = 2 * math.pi * j / sides
            verts.append(
                p + diameter / 2 * (normal * math.cos(a) + second * math.sin(a))
            )
    for i in range(len(points) - 1):
        for j in range(sides):
            a = i * sides + j
            b = i * sides + (j + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    faces += [
        tuple(reversed(range(sides))),
        tuple((len(points) - 1) * sides + j for j in range(sides)),
    ]
    obj = new_mesh(name, verts, faces, material)
    layer = obj.data.uv_layers.new(name="UVMap")
    distances = [0.0]
    for a, b in zip(points, points[1:]):
        distances.append(distances[-1] + (b - a).length)
    for poly in obj.data.polygons:
        for li in poly.loop_indices:
            idx = obj.data.loops[li].vertex_index
            layer.data[li].uv = ((idx % sides) / sides, distances[idx // sides] * 0.4)
    if material and material.name.startswith(("rope_tarred", "rope_untarred")):
        RIGGING_PATHS[name] = {
            "name": name,
            "mesh_object": name,
            "diameter_m": diameter,
            "points_gltf_m": [[p.x, p.z, -p.y] for p in points],
        }
    return obj


def parent_world(obj, parent):
    bpy.context.view_layer.update()
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_world = world


def canvas_material(name, width, depth, reefs):
    """Portable PBR texture: flax cloth, 0.57 m panel seams and period reef bands."""
    n = 512
    rng = np.random.default_rng(
        int.from_bytes(hashlib.sha256(name.encode()).digest()[:4], "little")
    )
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) / (n - 1)
    noise = rng.normal(0, 0.007, (n, n))
    panels = max(2, round(width / 0.57))
    seam_dist = np.abs((xx * panels + 0.5) % 1 - 0.5)
    seam = np.exp(-((seam_dist / 0.035) ** 2))
    dirt = 0.018 * np.sin(xx * 33 + np.sin(yy * 14)) + 0.015 * np.cos(yy * 24 + xx * 17)
    weave = 0.008 * (np.sin(xx * n * 2.8) + np.sin(yy * n * 2.6))
    shade = 1 + noise + weave + dirt - 0.16 * seam
    border = (xx < 0.012) | (xx > 0.988) | (yy < 0.012) | (yy > 0.988)
    shade[border] *= 0.83
    for distance in reefs:
        band = np.abs((1 - yy) - distance / depth) < 0.035 / depth
        shade[band] *= 0.8
    # Restrained rectangular repair patches, not white synthetic sailcloth.
    if "course" in name:
        shade[(xx > 0.28) & (xx < 0.36) & (yy > 0.19) & (yy < 0.29)] *= 0.94
    rgb = np.clip(shade[:, :, None] * np.array([0.78, 0.69, 0.51]), 0, 1)
    rgba = np.concatenate([rgb, np.ones((n, n, 1))], axis=2).astype(np.float32)
    im = bpy.data.images.new("flax_" + name, width=n, height=n, alpha=False)
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = str(OUT / "textures" / (name + ".png"))
    im.file_format = "PNG"
    im.save()
    im.pack()
    mat = bpy.data.materials.new("flax_" + name)
    mat.use_nodes = True
    mat.use_backface_culling = False
    bs = mat.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Roughness"].default_value = 0.92
    bs.inputs["Specular IOR Level"].default_value = 0.18
    tex = mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = im
    mat.node_tree.links.new(tex.outputs["Color"], bs.inputs["Base Color"])
    return mat


def animate_sail(obj, weights):
    obj.shape_key_add(name="Basis")
    for name, sign in (("wind_port", 1), ("wind_starboard", -1)):
        key = obj.shape_key_add(name=name)
        for i, point in enumerate(key.data):
            # Six centimetres maximum; all four edges stay on their ropes.
            point.co.x += sign * 0.06 * weights[i] * math.sin(i * 0.47)
            point.co.y += sign * 0.07 * weights[i] * math.cos(i * 0.29)
        for frame, val in (
            (0, 0),
            (24, 0.9 if sign > 0 else 0.05),
            (48, 0),
            (72, 0.9 if sign < 0 else 0.05),
            (96, 0),
        ):
            key.value = val
            key.keyframe_insert(data_path="value", frame=frame)
        key.value = 0
    obj["sail_state"] = "set"
    obj["outline_confidence"] = "our inference"
    obj["wind_morphs"] = (
        "wind_port,wind_starboard; pinned perimeter; 4-second loop at 24 fps"
    )


def export_glb(path, objects, animations=False):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_yup=True,
        export_apply=False,
        export_extras=True,
        export_cameras=False,
        export_lights=False,
        export_animations=animations,
        export_animation_mode="SCENE",
        export_frame_range=True,
        export_force_sampling=True,
        export_morph=True,
        export_anim_scene_split_object=False,
        export_image_format="AUTO",
    )


def triangles(objects):
    result = 0
    for obj in objects:
        if obj.type == "MESH":
            obj.data.calc_loop_triangles()
            result += len(obj.data.loop_triangles)
    return result


def reference_crew():
    """1.75 m scale figures for clearance review; never exported to the game GLBs."""
    cloth = bpy.data.materials.new("preview_crew_blue")
    cloth.diffuse_color = (0.035, 0.16, 0.24, 1)
    skin = bpy.data.materials.new("preview_crew_head")
    skin.diffuse_color = (0.52, 0.32, 0.19, 1)

    def present(obj):
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        PRESENTATION.objects.link(obj)
        obj["reference_height_m"] = 1.75
        return obj

    for idx, (x, s) in enumerate(((1.35, 0.0), (1.25, -8.7), (0.9, 5.6))):
        z = float(DECKS.heights(x, s))
        base = Vector((x, -s, z))

        def ball(name, offset, scale, mat):
            bpy.ops.mesh.primitive_uv_sphere_add(
                segments=16, ring_count=8, location=base + Vector(offset)
            )
            obj = bpy.context.object
            obj.name = "preview_crew_%d_%s" % (idx, name)
            obj.scale = scale
            obj.data.materials.append(mat)
            for p in obj.data.polygons:
                p.use_smooth = True
            present(obj)

        for side in (-1, 1):
            limb = tube(
                "preview_crew_%d_leg_%d" % (idx, side),
                [
                    base + Vector((side * 0.10, 0, 0.04)),
                    base + Vector((side * 0.10, 0, 0.84)),
                ],
                0.14,
                cloth,
                10,
            )
            present(limb)
            limb = tube(
                "preview_crew_%d_arm_%d" % (idx, side),
                [
                    base + Vector((side * 0.22, 0, 1.35)),
                    base + Vector((side * 0.28, 0.02, 0.95)),
                ],
                0.11,
                cloth,
                10,
            )
            present(limb)
        ball("hips", (0, 0, 0.85), (0.18, 0.13, 0.15), cloth)
        ball("torso", (0, 0, 1.14), (0.22, 0.14, 0.30), cloth)
        ball("head", (0, 0, 1.61), (0.13, 0.13, 0.14), skin)


def render_setup():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = False
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    if scene.world is None:
        scene.world = bpy.data.worlds.new("ocean_sky")
    scene.world.color = (0.15, 0.2, 0.28)
    world = scene.world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.36, 0.50, 0.65, 1)
    bg.inputs["Strength"].default_value = 0.45
    scene.view_settings.view_transform = "AgX"
    for name, location, power, size, color in [
        ("key", (10, -30, 52), 7000, 25, (1, 0.86, 0.65)),
        ("fill", (-30, -20, 25), 5000, 30, (0.6, 0.76, 1)),
        ("rim", (5, 30, 38), 7500, 20, (1, 0.77, 0.46)),
    ]:
        data = bpy.data.lights.new(name, "AREA")
        data.energy = power
        data.shape = "DISK"
        data.size = size
        data.color = color
        obj = bpy.data.objects.new(name, data)
        PRESENTATION.objects.link(obj)
        obj.location = location
        obj.rotation_euler = (
            (Vector((0, 0, 8)) - obj.location).to_track_quat("-Z", "Y").to_euler()
        )
    data = bpy.data.lights.new("sun", "SUN")
    data.energy = 2.0
    data.angle = 0.12
    sun = bpy.data.objects.new("sun", data)
    PRESENTATION.objects.link(sun)
    sun.rotation_euler = (0.45, -0.35, -0.6)
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.65
    reference_crew()
    # Modest geometric waves; this collection is excluded from every exported game mesh.
    n = 100
    size = 240
    vv = []
    ff = []
    for j in range(n + 1):
        for i in range(n + 1):
            x = (i / n - 0.5) * size
            y = (j / n - 0.5) * size
            z = (
                -0.08
                + 0.09 * math.sin(x * 0.48 + y * 0.32)
                + 0.045 * math.sin(y * 0.92 - x * 0.27)
            )
            vv.append((x, y, z))
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i
            ff.append((a, a + 1, a + n + 2, a + n + 1))
    water = new_mesh("preview_ocean", vv, ff)
    ASSET.objects.unlink(water)
    PRESENTATION.objects.link(water)
    mat = bpy.data.materials.new("preview_ocean")
    mat.use_nodes = True
    bs = mat.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = (0.012, 0.095, 0.13, 1)
    bs.inputs["Roughness"].default_value = 0.23
    bs.inputs["Metallic"].default_value = 0.25
    noise = mat.node_tree.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.8
    noise.inputs["Detail"].default_value = 3
    bump = mat.node_tree.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.28
    bump.inputs["Distance"].default_value = 0.10
    mat.node_tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    mat.node_tree.links.new(bump.outputs["Normal"], bs.inputs["Normal"])
    water.data.materials.append(mat)
    mask = bpy.data.objects.get("boat_water_mask")
    if mask:
        cutter = bpy.data.objects.new("preview_boat_water_cut", mask.data.copy())
        PRESENTATION.objects.link(cutter)
        cutter.matrix_world = mask.matrix_world.copy()
        solid = cutter.modifiers.new("mask_volume", "SOLIDIFY")
        solid.thickness = 3
        solid.offset = 0
        with bpy.context.temp_override(object=cutter, active_object=cutter):
            bpy.ops.object.modifier_apply(modifier=solid.name)
        cut = water.modifiers.new("keep_boat_dry", "BOOLEAN")
        cut.operation = "DIFFERENCE"
        cut.solver = "EXACT"
        cut.object = cutter
        with bpy.context.temp_override(object=water, active_object=water):
            bpy.ops.object.modifier_apply(modifier=cut.name)
        bpy.data.objects.remove(cutter, do_unlink=True)
    horizon = new_mesh(
        "preview_distant_ocean",
        [
            (-5000, -5000, -0.23),
            (5000, -5000, -0.23),
            (5000, 5000, -0.23),
            (-5000, 5000, -0.23),
        ],
        [(0, 1, 2, 3)],
        mat,
    )
    ASSET.objects.unlink(horizon)
    PRESENTATION.objects.link(horizon)
    if mask:
        mask.hide_render = True
    cam = bpy.data.cameras.new("asset_camera")
    obj = bpy.data.objects.new("asset_camera", cam)
    PRESENTATION.objects.link(obj)
    scene.camera = obj
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1200
    shots = {
        "hero": ((30, -39, 23), (0, -2, 7), 50),
        "stern": ((25, 35, 20), (0, -1, 7), 50),
        "deck": ((11, 17, 12), (0, 0, 2.8), 42),
        "side": ((47, 1, 16), (0, -2, 7), 49),
    }
    for name, (position, target, lens) in shots.items():
        obj.location = position
        obj.rotation_euler = (
            (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
        )
        cam.lens = lens
        scene.render.filepath = str(OUT / "previews" / (name + ".png"))
        bpy.ops.render.render(write_still=True)
    position, target, lens = shots["hero"]
    obj.location = position
    obj.rotation_euler = (
        (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    )
    cam.lens = lens
