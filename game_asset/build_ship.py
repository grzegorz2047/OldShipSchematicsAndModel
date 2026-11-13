"""Build a sailing game asset from the published reference GLB and public data.

blender -b --factory-startup --python game_asset/build_ship.py -- --out build/game_ship
Tested in Blender 4.3.2. No external Python packages or texture downloads required.
The reference is retained unchanged; sail outlines are estimates, not period plans.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))
from deck_clearance import DeckEnvelope, inspect_glb

CANVAS_CLEARANCE_M = 2.25  # Game authoring target; validation allows 2.20 m.
SQUARES = {
    "fore_course": "fore_yard", "fore_topsail": "fore_topsail_yard",
    "fore_topgallant": "fore_topgallant_yard", "main_course": "main_yard",
    "main_topsail": "main_topsail_yard", "main_topgallant": "main_topgallant_yard",
    "spritsail": "spritsail_yard",
}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def ship_point(p):
    """Public [x,s,z] to Blender [x,-s,z]; export restores glTF [x,z,s]."""
    return Vector((p[0], -p[1], p[2]))


def values(group):
    return {k: v["value"] for k, v in PARAMETERS["groups"][group]["values"].items()}


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
    points = [p for i, p in enumerate(points) if not i or (p - points[i-1]).length > 1e-5]
    if len(points) < 2:
        return None
    verts, faces = [], []
    for i, p in enumerate(points):
        tangent = points[min(i+1, len(points)-1)] - points[max(i-1, 0)]
        tangent.normalize()
        normal = tangent.cross(Vector((0, 0, 1)))
        if normal.length < .01:
            normal = tangent.cross(Vector((1, 0, 0)))
        normal.normalize()
        second = tangent.cross(normal).normalized()
        for j in range(sides):
            a = 2 * math.pi * j / sides
            verts.append(p + diameter/2 * (normal*math.cos(a) + second*math.sin(a)))
    for i in range(len(points)-1):
        for j in range(sides):
            a = i*sides+j
            b = i*sides+(j+1)%sides
            faces.append((a, b, b+sides, a+sides))
    faces += [tuple(reversed(range(sides))), tuple((len(points)-1)*sides+j for j in range(sides))]
    obj=new_mesh(name, verts, faces, material)
    if material and material.name.startswith(("rope_tarred","rope_untarred")):
        RIGGING_PATHS[name]={"name":name,"mesh_object":name,"diameter_m":diameter,
            "points_gltf_m":[[p.x,p.z,-p.y] for p in points]}
    return obj


def parent_world(obj, parent):
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_world = world


def strip_reference():
    """Keep wheel steering only. Remove furled canvas, including baked static faces."""
    remove = set()
    for obj in list(ASSET.objects):
        if obj.get("variant") == "deck_tiller_variant" or obj.name == "deck_tiller_variant":
            remove.add(obj)
            remove.update(obj.children_recursive)
        if obj.name in SQUARES:
            remove.add(obj)
        if obj.get("visible_by_default") is False:
            remove.add(obj)
            remove.update(obj.children_recursive)
    for obj in remove:
        if obj.name in bpy.data.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
    for obj in list(ASSET.objects):
        if obj.type != "MESH":
            continue
        canvas = {i for i, m in enumerate(obj.data.materials) if m and m.name.startswith("canvas")}
        if not canvas:
            continue
        obj.data = obj.data.copy()
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in canvas], context="FACES")
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bm.to_mesh(obj.data)
        bm.free()
        if not len(obj.data.polygons):
            bpy.data.objects.remove(obj, do_unlink=True)
    # The reference's fixed leads to rolled sails are baked into rigging_static.
    # Remove their rope faces, leaving belayed coils and unrelated standing rigging.
    from mathutils.kdtree import KDTree
    samples=[]
    for line in RIG["lines"]:
        if line["dynamic"] or line["rope"].startswith("coil_"):
            continue
        if not any(t in line["rope"] for t in ("clewline","clew_garnet","buntline","sheet","brail")):
            continue
        path=[ship_point(p) for p in [line["from"],*line["via"],line["to"]]]
        radius=max(.007,line["diameter_m"]/2)+.009
        for a,b in zip(path,path[1:]):
            steps=max(1,math.ceil((b-a).length/.02))
            samples.extend((a.lerp(b,i/steps),radius) for i in range(steps+1))
    if samples:
        tree=KDTree(len(samples))
        for i,(p,_) in enumerate(samples): tree.insert(p,i)
        tree.balance()
        obj=bpy.data.objects.get("rigging_static")
        bm=bmesh.new(); bm.from_mesh(obj.data)
        doomed=[]
        for face in bm.faces:
            mat=obj.data.materials[face.material_index]
            if not mat or not mat.name.startswith("rope_untarred"):
                continue
            _,index,distance=tree.find(obj.matrix_world@face.calc_center_median())
            if distance<samples[index][1]: doomed.append(face)
        bmesh.ops.delete(bm,geom=doomed,context="FACES")
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context="VERTS")
        bm.to_mesh(obj.data); bm.free()


def hoist_yards():
    moved = {}
    for name in SQUARES.values():
        obj = bpy.data.objects[name]
        original = obj.matrix_world.copy()
        dz = float(obj.get("working_height_dz_m", 0))
        rake = values("spars")["fore_mast_rake_deg" if name.startswith("fore") else "main_mast_rake_deg"]
        world = obj.matrix_world.copy()
        world.translation += Vector((0, dz * math.tan(math.radians(rake)), dz))
        obj.matrix_world = world
        obj["sail_state"] = "set"
        obj["range_deg"] = obj.get("range_deg_hoisted", obj.get("range_deg", [-35, 35]))
        obj["hoist_applied_m"] = dz
        moved[name] = world @ original.inverted()
    bpy.context.view_layer.update()
    # Yard workstations have world positions in the source, not yard parents.
    for obj in list(ASSET.objects):
        if obj.name.startswith("station_yardarm_") and obj.get("object") in moved:
            obj.matrix_world = moved[obj["object"]] @ obj.matrix_world
            parent_world(obj, bpy.data.objects[obj["object"]])
    return moved


def join_rope_meshes(objects,name,parent=None):
    if not objects:
        return
    for obj in objects:
        if obj.name in RIGGING_PATHS: RIGGING_PATHS[obj.name]["mesh_object"]=name
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects: obj.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.object.join()
    obj=objects[0]; obj.name=name
    if parent: parent_world(obj,parent)
    return obj


def dynamic_ends(line):
    ends=[]
    for key in ("from","to"):
        node=line.get(key+"_object"); local=line.get(key+"_local")
        if node and local is not None and bpy.data.objects.get(node):
            p=bpy.data.objects[node].matrix_world@Vector(local)
            if node in SQUARES.values():p.y=max(p.y,bpy.data.objects[node].matrix_world.translation.y+.12)
        else:
            p=ship_point(line[key])
            if "brace_pendant" in line["rope"] and key=="to" and line.get("from_object") in YARD_MOVES:
                p=YARD_MOVES[line["from_object"]]@p
        ends.append(p)
    return ends


def move_point(point):
    matches=[((point-a).length,b) for a,b in ATTACHMENT_MOVES if (point-a).length<.065]
    return min(matches,key=lambda x:x[0])[1].copy() if matches else point.copy()


def prepare_attachment_moves():
    global ATTACHMENT_MOVES
    ATTACHMENT_MOVES=[]
    for line in RIG["lines"]:
        if line["dynamic"]:
            for key,new in zip(("from","to"),dynamic_ends(line)):
                old=ship_point(line[key])
                if (new-old).length>.015: ATTACHMENT_MOVES.append((old,new))
        if line["group"]=="running" and line["rope"].startswith("fore_") and "_brace_" in line["rope"] and line.get("belayed_to"):
            old=ship_point(line["from"]); new=old.copy()
            stay_name="main_topgallant_stay" if line["rope"].startswith("fore_topgallant") else "main_topmast_stay" if line["rope"].startswith("fore_topsail") else "main_stay"
            stay=next(l for l in RIG["lines"] if l["rope"]==stay_name)
            fraction=.98 if stay_name=="main_topgallant_stay" else .96 if stay_name=="main_topmast_stay" else .90
            new=ship_point(stay["from"]).lerp(ship_point(stay["to"]),fraction)
            new.x=.3 if "_port" in line["rope"] else -.3
            ATTACHMENT_MOVES.append((old,new))
    # Blocks that belong to the moved pendant ends must follow their attachments.
    obj=bpy.data.objects["rigging_static"]; mesh=obj.data
    adjacency=[set() for _ in mesh.vertices]
    for edge in mesh.edges:
        a,b=edge.vertices; adjacency[a].add(b);adjacency[b].add(a)
    seen=set(); inverse=obj.matrix_world.inverted()
    for start in range(len(mesh.vertices)):
        if start in seen:continue
        todo=[start];seen.add(start); component=[]
        while todo:
            i=todo.pop();component.append(i)
            for j in adjacency[i]:
                if j not in seen:seen.add(j);todo.append(j)
        points=[obj.matrix_world@mesh.vertices[i].co for i in component]
        if any(max(p[k] for p in points)-min(p[k] for p in points)>.6 for k in range(3)):continue
        centre=sum(points,Vector())/len(points)
        candidates=[((centre-a).length,b-a) for a,b in ATTACHMENT_MOVES if (centre-a).length<.3]
        if candidates:
            delta=min(candidates,key=lambda x:x[0])[1]
            for i in component: mesh.vertices[i].co=inverse@(obj.matrix_world@mesh.vertices[i].co+delta)


def rebuild_running_and_footropes(moved):
    """Replace baked running leads, and keep the crew's footropes abaft each yard."""
    obj=bpy.data.objects["rigging_static"]
    obj.data=obj.data.copy(); bm=bmesh.new(); bm.from_mesh(obj.data)
    bright={i for i,m in enumerate(obj.data.materials) if m and m.name.startswith("rope_untarred")}
    bmesh.ops.delete(bm,geom=[f for f in bm.faces if f.material_index in bright],context="FACES")
    bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context="VERTS")
    bm.to_mesh(obj.data); bm.free()
    for obj in list(ASSET.objects):
        if obj.name.startswith("rope_footropes_"):
            bpy.data.objects.remove(obj,do_unlink=True)
    static=[]; perts={}
    for line in RIG["lines"]:
        if line.get("variant")=="deck_tiller_variant" or line["dynamic"]:
            continue
        path=[ship_point(p) for p in [line["from"],*line["via"],line["to"]]]
        if line["group"]=="footropes":
            yard=bpy.data.objects[line["parent"]]
            delta=moved.get(yard.name,Matrix.Identity(4))
            path=[delta@p for p in path]
            c=yard.matrix_world.translation
            for p in path:
                drop=max(0.,min(1.,(c.z-p.z)/.7))
                p.y=c.y+.14+.45*drop
            rope=tube("rope_footrope_line_%d"%line["id"],path,max(.014,line["diameter_m"]),TAR)
            RIGGING_PATHS[rope.name].update(source_line_id=line["id"],parent=yard.name)
            perts.setdefault(yard.name,[]).append(rope)
            continue
        if line["material"]!="untarred" or line["parent"]:
            continue
        if not line["rope"].startswith("coil_") and any(t in line["rope"] for t in ("clewline","clew_garnet","buntline","sheet","brail")):
            continue
        path=[move_point(p) for p in path]
        if line["group"]=="running" and line["rope"].startswith("fore_") and "_brace_" in line["rope"] and line.get("belayed_to"):
            # Fixed lead blocks are near the forward end of the intermast stay.
            # Descend at the fore rail, then lead aft below the course and staysail.
            turning=path[-1].copy(); turning.y=-9.8;turning.x=math.copysign(2.25,turning.x)
            turning.z=2.2
            path=[path[0],turning,path[-1]]
            anchor=path[0].copy();anchor.x=0
            tube("brace_block_strop_%d"%line["id"],[anchor,path[0]],.025,TAR)
            bpy.ops.mesh.primitive_uv_sphere_add(segments=10,ring_count=6,location=turning)
            block=bpy.context.object; block.name="brace_turning_block_%d"%line["id"]
            block.scale=(.085,.07,.13); block.data.materials.append(bpy.data.materials["wood_dark"])
            for col in list(block.users_collection): col.objects.unlink(block)
            ASSET.objects.link(block)
        elif line["group"]=="running" and path[0].z>5 and path[-1].z<4 and -3<path[0].y<3:
            turning=path[-1].copy(); turning.y=max(path[0].y,2.4)
            turning.z=float(DECKS.heights(turning.x,-turning.y))+.14
            path=[path[0],turning,path[-1]]
            bpy.ops.mesh.primitive_uv_sphere_add(segments=10,ring_count=6,location=turning)
            block=bpy.context.object; block.name="deck_lead_block_%d"%line["id"]
            block.scale=(.075,.08,.12);block.data.materials.append(bpy.data.materials["wood_dark"])
            for col in list(block.users_collection):col.objects.unlink(block)
            ASSET.objects.link(block)
        rope=tube("rope_static_line_%d"%line["id"],path,max(.014,line["diameter_m"]),ROPE)
        if rope:
            RIGGING_PATHS[rope.name]["source_line_id"]=line["id"]
            static.append(rope)
    join_rope_meshes(static,"rigging_running_sailing")
    for name,objects in perts.items():
        join_rope_meshes(objects,"rope_footropes_"+name+"_glb",bpy.data.objects[name])


def canvas_material(name, width, depth, reefs):
    """Portable PBR texture: flax cloth, 0.57 m panel seams and period reef bands."""
    n = 512
    rng = np.random.default_rng(int.from_bytes(hashlib.sha256(name.encode()).digest()[:4], "little"))
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32) / (n-1)
    noise = rng.normal(0, .007, (n, n))
    panels = max(2, round(width/.57))
    seam_dist = np.abs((xx*panels+.5) % 1 - .5)
    seam = np.exp(-(seam_dist/.035)**2)
    dirt = .018*np.sin(xx*33+np.sin(yy*14)) + .015*np.cos(yy*24+xx*17)
    weave = .008*(np.sin(xx*n*2.8)+np.sin(yy*n*2.6))
    shade = 1 + noise + weave + dirt - .16*seam
    border = (xx<.012) | (xx>.988) | (yy<.012) | (yy>.988)
    shade[border] *= .83
    for distance in reefs:
        band = np.abs((1-yy) - distance/depth) < .035/depth
        shade[band] *= .8
    # Restrained rectangular repair patches, not white synthetic sailcloth.
    if "course" in name:
        shade[(xx>.28)&(xx<.36)&(yy>.19)&(yy<.29)] *= .94
    rgb = np.clip(shade[:,:,None] * np.array([.78,.69,.51]), 0, 1)
    rgba = np.concatenate([rgb, np.ones((n,n,1))], axis=2).astype(np.float32)
    im = bpy.data.images.new("flax_"+name, width=n, height=n, alpha=False)
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = str(OUT/"textures"/(name+".png"))
    im.file_format = "PNG"
    im.save()
    im.pack()
    mat = bpy.data.materials.new("flax_"+name)
    mat.use_nodes = True
    mat.use_backface_culling = False
    bs = mat.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Roughness"].default_value = .92
    bs.inputs["Specular IOR Level"].default_value = .18
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
            point.co.x += sign * .06 * weights[i] * math.sin(i*.47)
            point.co.y += sign * .07 * weights[i] * math.cos(i*.29)
        for frame, val in ((0,0),(24,.9 if sign>0 else .05),(48,0),(72,.9 if sign<0 else .05),(96,0)):
            key.value = val
            key.keyframe_insert(data_path="value", frame=frame)
        key.value = 0
    obj["sail_state"] = "set"
    obj["outline_confidence"] = "our inference"
    obj["wind_morphs"] = "wind_port,wind_starboard; pinned perimeter; 4-second loop at 24 fps"


def square_sail(name, yard_name, spec):
    yard = bpy.data.objects[yard_name]
    c = yard.matrix_world.translation.copy()
    nx, ny = 32, 24
    head, foot, depth = (spec[k] for k in ("head_m","foot_m","depth_m"))
    source_depth=depth
    lower_y=c.y
    if name.endswith(("topsail","topgallant")):
        lower_name=("fore_yard" if name=="fore_topsail" else "main_yard" if name=="main_topsail" else "fore_topsail_yard" if name.startswith("fore") else "main_topsail_yard")
        lower_y=bpy.data.objects[lower_name].matrix_world.translation.y
    if name.endswith("_course"):
        # The chapter-08 outline reaches the rail and is a sail-plan estimate,
        # not a tested playable mesh. Leave headroom over the deck, not the rail.
        foot_z=max(DECKS.required_height(0,-c.y+ds,CANVAS_CLEARANCE_M)
                   for ds in (-.8,0,.8))
        depth=min(depth,c.z-.06-foot_z)
    verts, uv, weights = [], [], []
    for j in range(ny+1):
        t = j/ny
        width = head*(1-t)+foot*t
        for i in range(nx+1):
            u = i/nx
            x = (u-.5)*width
            # Forward belly in a following wind; foot rises in the centre (roach).
            belly = .12 * head * math.sin(math.pi*u) * math.sin(math.pi*t)**2
            roach_height=.75 if name.endswith("_course") else 2.0 if name.endswith("topsail") else 1.8 if name.endswith("topgallant") else .38
            # Cut the foot upward in the column layout, rather than curling the
            # last rows back upward (which would fold a deeply cut topsail).
            roach = roach_height*math.sin(math.pi*u)*t
            course_foot=.35*t*math.sin(math.pi*u) if name.endswith("_course") else .35*t if name.endswith(("topsail","topgallant")) else 0
            p = Vector((c.x+x,c.y*(1-t)+lower_y*t-.18-belly-course_foot,c.z-depth*t+roach-.06))
            verts.append(p)
            uv.append((u,1-t))
            weights.append(math.sin(math.pi*u)*math.sin(math.pi*t))
    faces = [(j*(nx+1)+i, j*(nx+1)+i+1, (j+1)*(nx+1)+i+1, (j+1)*(nx+1)+i)
             for j in range(ny) for i in range(nx)]
    mat = canvas_material(name, max(head,foot), depth, [.9,1.8] if "topsail" in name else [])
    obj = new_mesh(name+"_set", verts, faces, mat, uv)
    obj["source_depth_m"]=source_depth
    obj["game_depth_m"]=depth
    obj["clearance_adjusted"]=name.endswith("_course")
    animate_sail(obj, weights)
    # The mesh is authored in world coordinates, then parented preserving that pose.
    parent_world(obj, yard)
    paths = [verts[:nx+1], verts[ny*(nx+1):], verts[::nx+1], verts[nx::nx+1]]
    for i, path in enumerate(paths):
        rope = tube(name+"_bolt_rope_"+str(i), path, .023, ROPE)
        parent_world(rope, yard)
    for side, index in (("port",nx),("starboard",0)):
        clew = Vector(verts[ny*(nx+1)+index])
        if name.endswith(("topsail","topgallant")):
            lower = "fore_yard" if name=="fore_topsail" else "main_yard" if name=="main_topsail" else "fore_topsail_yard" if name.startswith("fore") else "main_topsail_yard"
            target = bpy.data.objects[lower].matrix_world.translation.copy()
            target.x = clew.x
            target.y -= .15
        else:
            target = Vector((3.0 if side=="port" else -3.0, c.y+2.2, 2.1))
            if name=="spritsail":
                target = Vector((3 if side=="port" else -3, -12.7, 2.5))
        rope=tube(name+"_sheet_"+side, [clew, target], .024, ROPE)
        rope["dynamic"]=True
        rope["from_object"]=yard.name
        rope["from_local"]=list(yard.matrix_world.inverted()@clew)
        rope["to"]=list(target)
        rope["endpoint_coordinates"]="Blender XYZ; convert to glTF local (x,z,-y)"
        if name.endswith(("topsail","topgallant")):
            lower_yard=bpy.data.objects[lower]
            rope["to_object"]=lower
            rope["to_local"]=list(lower_yard.matrix_world.inverted()@target)
    return obj


def panel_sail(name, corners, parent=None, luff=None):
    """Triangle or four-sided sail, with a pinned perimeter and a leeward belly."""
    corners = [Vector(p) for p in corners]
    # A loose-footed gaff sail must also clear the raised quarterdeck.
    # Raising only the aft clew leaves its diagonal foot cutting through the crew.
    for point in corners:
        point.z=max(point.z,DECKS.required_height(point.x,-point.y,CANVAS_CLEARANCE_M))
    n = 24
    verts, uv, weights, faces = [], [], [], []
    if len(corners)==3:
        a,b,c = corners
        idx = {}
        for j in range(n+1):
            for i in range(n+1-j):
                u,v = i/n,j/n
                w = max(0., 27*u*v*(1-u-v))
                p = (luff(u/(1-v))*(1-v)+c*v) if luff and v<1 else a*(1-u-v)+b*u+c*v
                p.x += .48*w
                idx[i,j] = len(verts)
                verts.append(p); uv.append((u,v)); weights.append(w)
        for j in range(n):
            for i in range(n-j):
                faces.append((idx[i,j],idx[i+1,j],idx[i,j+1]))
                if i+j<n-1:
                    faces.append((idx[i+1,j],idx[i+1,j+1],idx[i,j+1]))
    else:
        a,b,c,d = corners
        for j in range(n+1):
            v=j/n
            for i in range(n+1):
                u=i/n
                w=math.sin(math.pi*u)*math.sin(math.pi*v)
                bottom=a*(1-v)+d*v
                if name=="gaff_sail":
                    bottom.z+=2.2*math.sin(math.pi*v)
                    bottom.z=max(bottom.z,DECKS.required_height(bottom.x,-bottom.y,CANVAS_CLEARANCE_M))
                top=b*(1-v)+c*v
                p=bottom*(1-u)+top*u
                p.x += .65*w
                verts.append(p); uv.append((u,v)); weights.append(w)
        faces=[(j*(n+1)+i,j*(n+1)+i+1,(j+1)*(n+1)+i+1,(j+1)*(n+1)+i)
               for j in range(n) for i in range(n)]
    width=max((a-b).length for a in corners for b in corners)
    obj=new_mesh(name+"_set",verts,faces,canvas_material(name,width,width,[]),uv)
    animate_sail(obj,weights)
    if parent:
        parent_world(obj,parent)
    if len(corners)==4:
        paths=[verts[:n+1],verts[n*(n+1):],verts[::n+1],verts[n::n+1]]
    else:
        paths=[[verts[idx[i,0]] for i in range(n+1)],
               [verts[idx[n-j,j]] for j in range(n+1)],
               [verts[idx[0,j]] for j in range(n+1)]]
    for i,path in enumerate(paths):
        rope=tube(name+"_bolt_rope_"+str(i),path,.023,ROPE)
        if parent:
            parent_world(rope,parent)
    return obj


def other_sails():
    # Use the same reconstruction as geometria.Statek.zagle(), chapter 08.
    sys.path.insert(0,str(ROOT/"blender"))
    import parametry
    import rzedne
    kd=rzedne.Kadlub(parametry.KADLUB,parametry.RZEDNE_H,parametry.RZEDNE_S,parametry.RZEDNE)
    rail=lambda s: float(kd.Zd(s)+kd.rail_r(s))
    g=SPARS["gaff"]
    jaw=ship_point([float(g["start_"+k+"_m"]) for k in ("x","s","z")])
    peak=ship_point([float(g["end_"+k+"_m"]) for k in ("x","s","z")])
    s_sn=-1.85
    tack=ship_point([0,s_sn-.1,float(kd.deck_c(s_sn))+1.4])
    jaw.z-=.15
    clew=ship_point([0,-13.6,rail(-13.6)+.6])
    panel_sail("gaff_sail",[tack,jaw,peak,clew],bpy.data.objects["gaff"])
    for name,stay,f0,f1,height in (
        ("jib","jib_stay",.06,.90,.50),
        ("fore_topmast_staysail","fore_topmast_stay",.10,.92,.55),
        ("main_topmast_staysail","main_topmast_stay",.12,.90,.50),
        ("main_staysail","main_stay",.30,.82,.55),
    ):
        line=next(l for l in RIG["lines"] if l["rope"]==stay)
        path=[ship_point(p) for p in [line["from"],*line["via"],line["to"]]]
        distances=[0.]
        for a,b in zip(path,path[1:]): distances.append(distances[-1]+(b-a).length)
        def on_stay(f):
            d=f*distances[-1]
            i=min(len(path)-2,max(0,int(np.searchsorted(distances,d,side="right")-1)))
            return path[i].lerp(path[i+1],(d-distances[i])/max(1e-8,distances[i+1]-distances[i]))
        def luff_edge(t):
            return on_stay(f0+(f1-f0)*t)+Vector((.14,0,0))
        head_world,tack_world=luff_edge(0),luff_edge(1)
        head=Vector((head_world.x,-head_world.y,head_world.z));tack=Vector((tack_world.x,-tack_world.y,tack_world.z))
        luff_length=(head-tack).length
        sc=tack.y-height*luff_length
        if name=="fore_topmast_staysail": sc=max(sc,15.3)
        if name=="jib": sc=max(sc,16.2)
        clew=Vector((0,sc,max(tack.z-.1*luff_length,rail(sc)+1)))
        clew_world=ship_point(clew)
        clew_world.x={"jib":2.8,"fore_topmast_staysail":1.4,"main_topmast_staysail":1.2,"main_staysail":1.2}[name]
        clew_world.z=max(clew_world.z,DECKS.required_height(clew_world.x,-clew_world.y,CANVAS_CLEARANCE_M))
        def luff_curve(t):
            return on_stay(f0+(f1-f0)*t)+Vector((.14,0,0))
        panel_sail(name,[head_world,tack_world,clew_world],luff=luff_curve)
        # Hanks bridge the luff offset and keep it visibly attached to its stay.
        for i,t in enumerate(np.linspace(0,1,max(3,round(luff_length/1.2)))):
            f=f0+(f1-f0)*float(t); centre=on_stay(f)
            axis=(on_stay(min(1,f+.002))-on_stay(max(0,f-.002))).normalized()
            normal=Vector((1,0,0));normal=(normal-axis*normal.dot(axis)).normalized()
            other=axis.cross(normal).normalized()
            radius=.12 if line["diameter_m"]>.06 else .095
            centre+=normal*(.14-radius)
            ring=[centre+radius*(normal*math.cos(a)+other*math.sin(a)) for a in np.linspace(0,2*math.pi,17)]
            tube(name+"_hank_%d"%i,ring,.008,bpy.data.materials["iron"],sides=5)
        anchor_x,anchor_s=(1.65,11.55) if name=="jib" else (1.8,10.9) if name=="fore_topmast_staysail" else (2.5,sc-1)
        tube(name+"_sheet",[clew_world,ship_point([anchor_x,anchor_s,rail(anchor_s)])],.022,ROPE)


def rebuild_dynamic():
    changed=[]
    for obj in list(ASSET.objects):
        if not obj.get("dynamic"):
            continue
        lid=obj.get("line_id")
        # Published GLB uses the ID at the end of the rope name.
        if lid is None:
            try:
                lid=int(obj.name.removesuffix("_glb").rsplit("_",1)[1])
            except ValueError:
                continue
        line=next((l for l in RIG["lines"] if l["id"]==lid),None)
        if line is None:
            raise ValueError("Unresolved dynamic rope: "+obj.name)
        # Clewlines/sheets ending at the old rolled canvas are replaced by sail sheets.
        if any(token in line["rope"] for token in ("clewline", "clew_garnet", "buntline", "sheet", "brail")):
            bpy.data.objects.remove(obj,do_unlink=True)
            continue
        ends=dynamic_ends(line)
        ends=[move_point(p) for p in ends]
        path=[ends[0]]+[ship_point(p) for p in line.get("via",[])]+[ends[1]]
        # Old sag samples would pin a raised rope to its lowered path.
        if any(line.get(k+"_object") in SQUARES.values() for k in ("from","to")):
            path=[ends[0].lerp(ends[1],i/12)-Vector((0,0,.025*math.sin(math.pi*i/12))) for i in range(13)]
        oldname=obj.name
        extras={k:obj[k] for k in obj.keys()}
        mat=obj.data.materials[0] if obj.type=="MESH" and len(obj.data.materials) else ROPE
        bpy.data.objects.remove(obj,do_unlink=True)
        new=tube(oldname,path,max(.014,line["diameter_m"]),mat)
        if new:
            for k,v in extras.items():
                new[k]=v
            for index,key in enumerate(("from","to")):
                node=line.get(key+"_object")
                if node and bpy.data.objects.get(node):
                    new[key+"_local"]=list(bpy.data.objects[node].matrix_world.inverted()@ends[index])
            new["rebuilt_for_set_sails"]=True
            new["line_id"]=lid
            if "brace_pendant" in line["rope"] and line.get("from_object") and not line.get("to_object"):
                node=line["from_object"]
                new["to_object"]=node
                new["to_local"]=list(bpy.data.objects[node].matrix_world.inverted()@ends[1])
            RIGGING_PATHS[new.name].update(source_line_id=lid)
            for key in ("from_object","to_object","from_local","to_local"):
                if key in new:
                    value=new[key]
                    RIGGING_PATHS[new.name][key]=list(value) if key.endswith("_local") else value
            changed.append(lid)
    return changed


def export_glb(path, objects, animations=False):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(path),export_format="GLB",use_selection=True,
        export_yup=True,export_apply=False,export_extras=True,export_cameras=False,
        export_lights=False,export_animations=animations,export_animation_mode="SCENE",
        export_frame_range=True,export_force_sampling=True,export_morph=True,
        export_anim_scene_split_object=False,export_image_format="AUTO")


def triangles(objects):
    result=0
    for obj in objects:
        if obj.type=="MESH":
            obj.data.calc_loop_triangles()
            result+=len(obj.data.loop_triangles)
    return result


def make_lod(level):
    copies=[]
    for src in list(ASSET.objects):
        if src.type!="MESH" or src.name=="boat_water_mask":
            continue
        if level==2 and (src.name.startswith(("rope_dynamic_","station_","rope_footropes_")) or "bolt_rope" in src.name or "sheet" in src.name or src.name=="rigging_running_sailing"):
            continue
        if level==2 and src.name=="rigging_static":
            continue
        obj=bpy.data.objects.new("lod_"+src.name,src.data.copy())
        LODS.objects.link(obj)
        obj.matrix_world=src.matrix_world.copy()
        if obj.data.shape_keys:
            obj.shape_key_clear()
        preserve=src.name.endswith("_set") or src.name.startswith("rope_") or src.name in ("rigging_static","rigging_running_sailing")
        if len(obj.data.polygons)>20 and not preserve:
            mod=obj.modifiers.new("distance_simplification","DECIMATE")
            mod.ratio=(.35 if level==1 else .035) if not src.name.endswith("_set") else (.5 if level==1 else .14)
            with bpy.context.temp_override(object=obj,active_object=obj):
                bpy.ops.object.modifier_apply(modifier=mod.name)
        copies.append(obj)
    if level==2:
        for line in RIG["lines"]:
            if line["kind"]=="standing" and line["diameter_m"]>=.028 and line["length_m"]>4:
                obj=tube("lod_stay_"+str(line["id"]),[ship_point(line["from"]),ship_point(line["to"])],max(.035,line["diameter_m"]),TAR,sides=3)
                ASSET.objects.unlink(obj); LODS.objects.link(obj); copies.append(obj)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in copies:
        obj.select_set(True)
    bpy.context.view_layer.objects.active=copies[0]
    bpy.ops.object.join()
    merged=copies[0]
    merged.name="snow_sailing_lod"+str(level)
    merged["lod_level"]=level
    merged["static_pose"]=True
    # Geometry LOD should also reduce texture memory, not just triangle count.
    swaps=[]; images={}; limit=512 if level==1 else 256
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        for node in mat.node_tree.nodes:
            if node.type=="TEX_IMAGE" and node.image and max(node.image.size)>limit:
                original=node.image
                if original.name not in images:
                    copy=original.copy()
                    factor=limit/max(original.size)
                    copy.scale(max(1,round(original.size[0]*factor)),max(1,round(original.size[1]*factor)))
                    copy.pack()
                    images[original.name]=copy
                swaps.append((node,original)); node.image=images[original.name]
    try:
        export_glb(OUT/(merged.name+".glb"),[merged])
    finally:
        for node,image in swaps:
            node.image=image
        for image in images.values():
            bpy.data.images.remove(image)
    count=triangles([merged])
    bpy.data.objects.remove(merged,do_unlink=True)
    return count


def reference_crew():
    """1.75 m scale figures for clearance review; never exported to the game GLBs."""
    cloth=bpy.data.materials.new("preview_crew_blue"); cloth.diffuse_color=(.035,.16,.24,1)
    skin=bpy.data.materials.new("preview_crew_head"); skin.diffuse_color=(.52,.32,.19,1)
    def present(obj):
        for collection in list(obj.users_collection): collection.objects.unlink(obj)
        PRESENTATION.objects.link(obj)
        obj["reference_height_m"]=1.75
        return obj
    for idx,(x,s) in enumerate(((1.35,-.9),(-1.1,10.3),(1.0,-8.0))):
        z=float(DECKS.heights(x,s)); base=Vector((x,-s,z))
        def ball(name,offset,scale,mat):
            bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,location=base+Vector(offset))
            obj=bpy.context.object; obj.name="preview_crew_%d_%s"%(idx,name); obj.scale=scale
            obj.data.materials.append(mat)
            for p in obj.data.polygons: p.use_smooth=True
            present(obj)
        for side in (-1,1):
            limb=tube("preview_crew_%d_leg_%d"%(idx,side),[base+Vector((side*.10,0,.04)),base+Vector((side*.10,0,.84))],.14,cloth,10)
            present(limb)
            limb=tube("preview_crew_%d_arm_%d"%(idx,side),[base+Vector((side*.22,0,1.35)),base+Vector((side*.28,.02,.95))],.11,cloth,10)
            present(limb)
        ball("hips",(0,0,.85),(.18,.13,.15),cloth)
        ball("torso",(0,0,1.14),(.22,.14,.30),cloth)
        ball("head",(0,0,1.61),(.13,.13,.14),skin)


def render_setup():
    scene=bpy.context.scene
    scene.render.engine="CYCLES"
    scene.cycles.samples=64
    scene.cycles.use_denoising=False
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"
    if scene.world is None:
        scene.world=bpy.data.worlds.new("ocean_sky")
    scene.world.color=(.15,.2,.28)
    world=scene.world
    world.use_nodes=True
    bg=world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value=(.36,.50,.65,1)
    bg.inputs["Strength"].default_value=.45
    scene.view_settings.view_transform="AgX"
    for name,location,power,size,color in [
        ("key",(10,-30,52),7000,25,(1,.86,.65)),
        ("fill",(-30,-20,25),5000,30,(.6,.76,1)),
        ("rim",(5,30,38),7500,20,(1,.77,.46)),
    ]:
        data=bpy.data.lights.new(name,"AREA"); data.energy=power; data.shape="DISK"; data.size=size; data.color=color
        obj=bpy.data.objects.new(name,data); PRESENTATION.objects.link(obj); obj.location=location
        obj.rotation_euler=(Vector((0,0,8))-obj.location).to_track_quat("-Z","Y").to_euler()
    data=bpy.data.lights.new("sun","SUN"); data.energy=2.; data.angle=.12
    sun=bpy.data.objects.new("sun",data); PRESENTATION.objects.link(sun); sun.rotation_euler=(.45,-.35,-.6)
    scene.view_settings.look="AgX - Medium High Contrast"
    scene.view_settings.exposure=.65
    reference_crew()
    # Modest geometric waves; this collection is excluded from every exported game mesh.
    n=100; size=240
    vv=[]; ff=[]
    for j in range(n+1):
        for i in range(n+1):
            x=(i/n-.5)*size; y=(j/n-.5)*size
            z=-.08+.09*math.sin(x*.48+y*.32)+.045*math.sin(y*.92-x*.27)
            vv.append((x,y,z))
    for j in range(n):
        for i in range(n):
            a=j*(n+1)+i; ff.append((a,a+1,a+n+2,a+n+1))
    water=new_mesh("preview_ocean",vv,ff)
    ASSET.objects.unlink(water); PRESENTATION.objects.link(water)
    mat=bpy.data.materials.new("preview_ocean"); mat.use_nodes=True
    bs=mat.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value=(.012,.095,.13,1)
    bs.inputs["Roughness"].default_value=.23
    bs.inputs["Metallic"].default_value=.25
    noise=mat.node_tree.nodes.new("ShaderNodeTexNoise"); noise.inputs["Scale"].default_value=1.8; noise.inputs["Detail"].default_value=3
    bump=mat.node_tree.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value=.28; bump.inputs["Distance"].default_value=.10
    mat.node_tree.links.new(noise.outputs["Fac"],bump.inputs["Height"]); mat.node_tree.links.new(bump.outputs["Normal"],bs.inputs["Normal"])
    water.data.materials.append(mat)
    mask=bpy.data.objects.get("boat_water_mask")
    if mask:
        cutter=bpy.data.objects.new("preview_boat_water_cut",mask.data.copy())
        PRESENTATION.objects.link(cutter); cutter.matrix_world=mask.matrix_world.copy()
        solid=cutter.modifiers.new("mask_volume","SOLIDIFY"); solid.thickness=3; solid.offset=0
        with bpy.context.temp_override(object=cutter,active_object=cutter):
            bpy.ops.object.modifier_apply(modifier=solid.name)
        cut=water.modifiers.new("keep_boat_dry","BOOLEAN"); cut.operation="DIFFERENCE"; cut.solver="EXACT"; cut.object=cutter
        with bpy.context.temp_override(object=water,active_object=water):
            bpy.ops.object.modifier_apply(modifier=cut.name)
        bpy.data.objects.remove(cutter,do_unlink=True)
    horizon=new_mesh("preview_distant_ocean",[(-5000,-5000,-.23),(5000,-5000,-.23),(5000,5000,-.23),(-5000,5000,-.23)],[(0,1,2,3)],mat)
    ASSET.objects.unlink(horizon); PRESENTATION.objects.link(horizon)
    if mask:
        mask.hide_render=True
    cam=bpy.data.cameras.new("asset_camera"); obj=bpy.data.objects.new("asset_camera",cam)
    PRESENTATION.objects.link(obj); scene.camera=obj
    scene.render.resolution_x=1600; scene.render.resolution_y=1200
    shots={
        "hero":((39,-58,31),(0,-3,11),48),
        "stern":((35,51,29),(0,-1,11),46),
        "deck":((12,24,16),(0,0,3.7),42),
        "side":((65,2,22),(0,-3,12),48),
    }
    for name,(position,target,lens) in shots.items():
        obj.location=position; obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler(); cam.lens=lens
        scene.render.filepath=str(OUT/"previews"/(name+".png"))
        bpy.ops.render.render(write_still=True)
    position,target,lens=shots["hero"]
    obj.location=position; obj.rotation_euler=(Vector(target)-obj.location).to_track_quat("-Z","Y").to_euler(); cam.lens=lens


def main():
    global OUT, ASSET, LODS, PRESENTATION, PARAMETERS, SPARS, RIG, ROPE, TAR, DECKS, RIGGING_PATHS, YARD_MOVES
    RIGGING_PATHS={}
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",default=str(ROOT/"build"/"game_ship"))
    parser.add_argument("--no-renders",action="store_true")
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    OUT=Path(args.out).resolve(); OUT.mkdir(parents=True,exist_ok=True)
    for name in ("textures","previews","data"):
        (OUT/name).mkdir(exist_ok=True)
    PARAMETERS=load_json(ROOT/"data"/"parameters.json"); RIG=load_json(ROOT/"data"/"rigging-lines.json")
    DECKS=DeckEnvelope(load_json(ROOT/"data"/"deck-layout.json"))
    with (ROOT/"data"/"spars.csv").open(encoding="utf-8") as f:
        SPARS={r["spar"]:r for r in csv.DictReader(l for l in f if not l.startswith("#"))}
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(ROOT/"model"/"snow.glb"))
    ASSET=bpy.data.collections.new("SHIP | snow 1710 | sailing"); bpy.context.scene.collection.children.link(ASSET)
    for obj in list(bpy.context.scene.objects):
        for c in list(obj.users_collection): c.objects.unlink(obj)
        ASSET.objects.link(obj)
    LODS=bpy.data.collections.new("LOD export scratch"); bpy.context.scene.collection.children.link(LODS)
    PRESENTATION=bpy.data.collections.new("PRESENTATION | excluded from GLB"); bpy.context.scene.collection.children.link(PRESENTATION)
    strip_reference(); moved=hoist_yards()
    YARD_MOVES=moved
    ROPE=bpy.data.materials["rope_untarred"]; TAR=bpy.data.materials["rope_tarred"]
    prepare_attachment_moves()
    rebuild_running_and_footropes(moved)
    changed=rebuild_dynamic()
    for name,yard in SQUARES.items():
        square_sail(name,yard,values("sails")["set_sail_estimates"][name])
    other_sails()
    bpy.context.view_layer.update()
    root=bpy.data.objects.new("snow_sailing",None); ASSET.objects.link(root)
    for obj in list(ASSET.objects):
        if obj!=root and obj.parent is None:
            parent_world(obj,root)
    root["units"]="metres"; root["era"]="circa 1710; reconstruction, not a documented individual ship"
    root["coordinate_system"]="glTF +Y up, bow +Z, +X port, origin on design waterline"
    root["sails_set"]=True; root["steering_variant"]="steering_wheel_variant"
    root["runtime_rigging"]="Recompute dynamic rope endpoints after moving yards, guns, rudder or gaff. See data/rigging-lines.json."
    root["sail_outline_source"]="data/parameters.json / groups/sails/values/set_sail_estimates; chapter 08; our inference"
    scene=bpy.context.scene; scene.unit_settings.system="METRIC"; scene.unit_settings.scale_length=1
    scene.name="Sail_Wind"
    scene.render.fps=24; scene.frame_start=0; scene.frame_end=96; scene.frame_set(0)
    from rigging_collisions import audit_scene
    rigging_check=audit_scene()
    (OUT/"rigging_collisions.json").write_text(json.dumps(rigging_check,indent=2),encoding="utf-8")
    if not rigging_check["passed"]:
        raise ValueError("Ropes or other sails intersect canvas; see rigging_collisions.json")
    export_glb(OUT/"snow_sailing.glb",list(ASSET.objects),animations=True)
    (OUT/"sailing-rigging.json").write_text(json.dumps({"coordinate_system":"glTF metres: +Y up, +Z bow; *_local points retain Blender local XYZ as in the reference data", "scope":"Generated and rerouted ropes; unchanged standing rigging uses data/rigging-lines.json", "paths":list(RIGGING_PATHS.values())},indent=2),encoding="utf-8")
    clearance=inspect_glb(OUT/"snow_sailing.glb",load_json(ROOT/"data"/"deck-layout.json"))
    (OUT/"deck_clearance.json").write_text(json.dumps(clearance,indent=2),encoding="utf-8")
    if not clearance["passed"]:
        raise ValueError("Canvas intrudes into crew headroom: see deck_clearance.json")
    stats={"lod0":triangles(ASSET.objects),"lod1":make_lod(1),"lod2":make_lod(2)}
    shutil.copy2(ROOT/"model"/"snow_collision.glb",OUT/"snow_collision.glb")
    for name in ("parameters.json","stations.csv","moving-parts.csv","deck-layout.json","rigging-lines.json","names-map.csv","spars.csv"):
        shutil.copy2(ROOT/"data"/name,OUT/"data"/name)
    manifest={"asset":"snow_sailing","source":"https://github.com/grzegorz2047/OldShipSchematicsAndModel",
        "source_glb_sha256":hashlib.sha256((ROOT/"model"/"snow.glb").read_bytes()).hexdigest(),
        "blender_version":bpy.app.version_string,"triangles":stats,"sail_count":12,
        "steering_variant":"steering_wheel_variant","rebuilt_dynamic_line_ids":changed,
        "lod_distances_m":[0,75,250],"lod_hysteresis":.15,
        "canvas_minimum_deck_clearance_m":clearance["minimum_clearance_m"],
        "cloth_area_m2":clearance["cloth_area_m2"],
        "rope_canvas_audit_passed":rigging_check["passed"],"rope_canvas_audit_frames":rigging_check["frames"],
        "notes":["Sail outlines and belly are reconstructions, not period plans.",
          "No hold or cabin interior; original hull fairness limitations remain.",
          "LODs are static sailing poses; animate the close-range asset only.",
          "Collision file is the reference geometry: filter the tiller variant; generate engine physics explicitly.",
          "Wind animation is visual only, not a sailing or cloth physics simulation."]}
    (OUT/"asset_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    shutil.copy2(ROOT/"LICENSE",OUT/"LICENSE")
    shutil.copy2(ROOT/"blender"/"tekstury_cc0_spis.json",OUT/"reference_texture_sources.json")
    shutil.copy2(Path(__file__),OUT/"build_ship.py")
    shutil.copy2(ROOT/"game_asset"/"validate_asset.py",OUT/"validate_asset.py")
    shutil.copy2(ROOT/"game_asset"/"deck_clearance.py",OUT/"deck_clearance.py")
    shutil.copy2(ROOT/"game_asset"/"rigging_collisions.py",OUT/"rigging_collisions.py")
    shutil.copy2(ROOT/"game_asset"/"verify_exports.py",OUT/"verify_exports.py")
    if (ROOT/"game_asset"/"README.pl.md").exists():
        shutil.copy2(ROOT/"game_asset"/"README.pl.md",OUT/"README.pl.md")
    if not args.no_renders:
        render_setup()
    # Packed images ensure the native scene works after moving the directory.
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/"snow_sailing.blend"),compress=True)
    print("GAME_ASSET_DONE",json.dumps(stats),flush=True)


if __name__=="__main__":
    main()
