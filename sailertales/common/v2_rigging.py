"""Working sailing rig for the guide-based SailerTales snow/BRIG profile.

The hull builder retains the original reference rig and context. This module
raises the reference yards, relocates their attachments, rebuilds affected
running leads and creates the chapter-08 sail-plan outlines with explicit
game-clearance cuts. It adapts the previously audited snow sailing algorithm
from codex/snow-sailing-game-asset; all dimensions come from the current ctx.
No wind animation is authored: verification is of this static working trim.

API: deploy(ctx, spec, out=None) -> numerical reconstruction report.
"""
from pathlib import Path
import collections
import hashlib
import json
import math
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

CANVAS_CLEARANCE_M = 2.25
SQUARES = {
    "fore_course":"fore_yard", "fore_topsail":"fore_topsail_yard",
    "fore_topgallant":"fore_topgallant_yard", "main_course":"main_yard",
    "main_topsail":"main_topsail_yard", "main_topgallant":"main_topgallant_yard",
    "spritsail":"spritsail_yard",
}
YARD_NAMES = {
    "reja_fok":"fore_yard", "reja_fokmars":"fore_topsail_yard",
    "reja_fokbram":"fore_topgallant_yard", "reja_grot":"main_yard",
    "reja_grotmars":"main_topsail_yard", "reja_grotbram":"main_topgallant_yard",
    "reja_blinda":"spritsail_yard", "gafel":"gaff", "bom":"boom",
}
OUT = ASSET = PARAMETERS = RIG = ROPE = TAR = DECKS = None
RIGGING_PATHS = {}
SCALE_S = SCALE_X = 1.0
CTX = {}
_CANVAS_IMAGES = None
_ATTACHMENT_TREES = {}


def ship_point(p):
    return Vector((p[0],-p[1],p[2]))


def values(group):
    return PARAMETERS["groups"][group]["values"]


class DeckEnvelope:
    def __init__(self, ctx):
        self.ctx=ctx
    def heights(self,x,s):
        result=float(self.ctx["kd"].deck_z(float(s),float(x)))
        if float(s) <= self.ctx["K"]["POLPOKLAD_S"]:
            result+=self.ctx["K"]["POLPOKLAD_H"]
        return result
    def required_height(self,x,s,clearance):
        return self.heights(x,s)+clearance


def _nearest_attachment(obj,p):
    key=(obj.as_pointer(),tuple(v for row in obj.matrix_world for v in row))
    if key not in _ATTACHMENT_TREES:
        _ATTACHMENT_TREES[key]=BVHTree.FromObject(obj,bpy.context.evaluated_depsgraph_get())
    tree=_ATTACHMENT_TREES[key]
    mi=obj.matrix_world.inverted()
    hit=tree.find_nearest(mi@p,.8)
    if hit[0] is None:
        return p
    return obj.matrix_world@(hit[0]-hit[1]*.002)


def _deck_anchor(side,s):
    side=1 if side=="port" or side==1 else -1
    k,kd=CTX["K"],CTX["kd"]
    z=float(kd.Zd(s)+kd.rail_r(s))
    width=float(kd.H(s,z))-k["NADBURCIE_GR"]/2
    p=Vector((side*width,-s,z+k["RELING_GR"]+.025))
    # Forged eye and short foot are actual attachment fittings, not free ends.
    key="sheet_eye_%d"%len([o for o in ASSET.objects if o.name.startswith("sheet_eye_")])
    bpy.ops.mesh.primitive_torus_add(major_radius=.045,minor_radius=.009,
        major_segments=12,minor_segments=6,location=p,
        rotation=(math.pi/2,0,0))
    obj=bpy.context.object;obj.name=key
    for col in list(obj.users_collection):col.objects.unlink(obj)
    ASSET.objects.link(obj);obj.data.materials.append(bpy.data.materials["iron"])
    obj["kind"]="fitting";obj["asset_role"]="visual";obj["intended_joint"]="eye fixed into rail cap"
    return p+Vector((0,0,.036))


def _image(name,pixels,noncolor=False):
    height,width=pixels.shape[:2]
    image=bpy.data.images.new(name,width=width,height=height,alpha=False)
    image.colorspace_settings.name="Non-Color" if noncolor else "sRGB"
    image.pixels.foreach_set(np.asarray(pixels,dtype=np.float32).ravel())
    image.filepath_raw=str(OUT/"textures"/(name+".png"))
    image.file_format="PNG";image.save();image.pack()
    return image


def canvas_material(name,width,depth,reefs):
    """Shared 1.14 m PBR weave tile; two 0.57 m cloth panels per repeat."""
    global _CANVAS_IMAGES
    if _CANVAS_IMAGES is None:
        n=1024
        yy,xx=np.mgrid[0:n,0:n].astype(np.float32)/(n-1)
        rng=np.random.default_rng(1710)
        panels=np.minimum(xx%.5,.5-(xx%.5))
        seam=np.exp(-(panels/.0035)**2)
        weave=np.sin(xx*n*math.pi)*np.cos(yy*n*math.pi)
        broad=.012*np.sin(xx*26+yy*9)+.009*np.cos(yy*31-xx*8)
        shade=1+broad+rng.normal(0,.004,(n,n))-.10*seam
        rgb=np.clip(shade[:,:,None]*np.array([.73,.65,.49]),.04,.90)
        color=np.concatenate((rgb,np.ones((n,n,1))),axis=2)
        height=.0003*weave+.0015*seam
        gy,gx=np.gradient(height,n and 1.14/n)
        normal=np.stack((-gx,gy,np.ones_like(gx)),axis=2)
        normal/=np.linalg.norm(normal,axis=2,keepdims=True)
        normals=np.concatenate((normal*.5+.5,np.ones((n,n,1))),axis=2)
        orm=np.stack((np.ones_like(xx),np.clip(.90+.025*weave,0,1),np.zeros_like(xx),np.ones_like(xx)),axis=2)
        _CANVAS_IMAGES=(_image("guide_flax_color",color),_image("guide_flax_normal",normals,True),_image("guide_flax_orm",orm,True))
    mat=bpy.data.materials.new("flax_"+name)
    mat.use_nodes=True;mat.use_backface_culling=False
    bs=mat.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Roughness"].default_value=.90
    bs.inputs["Metallic"].default_value=0
    tex=mat.node_tree.nodes.new("ShaderNodeTexImage");tex.image=_CANVAS_IMAGES[0]
    mat.node_tree.links.new(tex.outputs["Color"],bs.inputs["Base Color"])
    nt=mat.node_tree.nodes.new("ShaderNodeTexImage");nt.image=_CANVAS_IMAGES[1]
    nm=mat.node_tree.nodes.new("ShaderNodeNormalMap");nm.inputs["Strength"].default_value=.35
    mat.node_tree.links.new(nt.outputs["Color"],nm.inputs["Color"])
    mat.node_tree.links.new(nm.outputs["Normal"],bs.inputs["Normal"])
    rm=mat.node_tree.nodes.new("ShaderNodeTexImage");rm.image=_CANVAS_IMAGES[2]
    sep=mat.node_tree.nodes.new("ShaderNodeSeparateColor")
    mat.node_tree.links.new(rm.outputs["Color"],sep.inputs[0])
    mat.node_tree.links.new(sep.outputs["Green"],bs.inputs["Roughness"])
    mat.node_tree.links.new(sep.outputs["Blue"],bs.inputs["Metallic"])
    mat["tile_metres"]=[1.14,1.14]
    mat["panel_width_m"]=.57
    mat["source"]="docs/en/08-ropes-blocks-and-sails.md"
    return mat


def animate_sail(obj,weights):
    # Static authored trim, not a simulated or visually animated cloth loop.
    obj["sail_state"]="set";obj["kind"]="sail";obj["asset_role"]="visual"
    obj["outline_confidence"]="our inference from chapter 08"
    obj["trim_scope"]="static working-yard pose; runtime rig motion requires rope recalculation"

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
    if obj and diameter > 0:
        uv=obj.data.uv_layers.new(name="UVMap")
        lengths=[0.0]
        for a,b in zip(points,points[1:]): lengths.append(lengths[-1]+(b-a).length)
        for poly in obj.data.polygons:
            if poly.index<(len(points)-1)*sides:
                ring,j=divmod(poly.index,sides)
                coords=[(lengths[ring]/(6.6*diameter),j/sides),
                        (lengths[ring]/(6.6*diameter),(j+1)/sides),
                        (lengths[ring+1]/(6.6*diameter),(j+1)/sides),
                        (lengths[ring+1]/(6.6*diameter),j/sides)]
            else:
                coords=[]
                for vi in poly.vertices:
                    a=2*math.pi*(vi%sides)/sides
                    coords.append((.5+.5*math.cos(a),.5+.5*math.sin(a)))
            for li,co in zip(poly.loop_indices,coords):uv.data[li].uv=co
    if material and material.name.startswith(("rope_tarred","rope_untarred")):
        RIGGING_PATHS[name]={"name":name,"mesh_object":name,"diameter_m":diameter,
            "points_gltf_m":[[p.x,p.z,-p.y] for p in points]}
    return obj


def parent_world(obj, parent):
    world = obj.matrix_world.copy()
    obj.parent = parent
    obj.matrix_world = world


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
    # Avoid an operator join on the reference's many custom-data layouts. A
    # world-space concatenation preserves every UV and colour attribute and is
    # independent of active-object/selection state after the source generator.
    uv_names=list(dict.fromkeys(layer.name for o in objects for layer in o.data.uv_layers))
    color_names=list(dict.fromkeys(layer.name for o in objects for layer in o.data.color_attributes))
    verts=[];faces=[];materials=[];material_map={};indices=[];smooth=[]
    uv_values={key:[] for key in uv_names};color_values={key:[] for key in color_names}
    for src in objects:
        offset=len(verts);me=src.data
        verts.extend(tuple(src.matrix_world@v.co) for v in me.vertices)
        remap={}
        for i,material in enumerate(me.materials):
            key=material.name if material else None
            if key not in material_map:
                material_map[key]=len(materials);materials.append(material)
            remap[i]=material_map[key]
        for poly in me.polygons:
            faces.append(tuple(offset+i for i in poly.vertices))
            indices.append(remap.get(poly.material_index,0));smooth.append(poly.use_smooth)
            for li in poly.loop_indices:
                for key in uv_names:
                    layer=me.uv_layers.get(key)
                    uv_values[key].append(tuple(layer.data[li].uv) if layer else (0.,0.))
                for key in color_names:
                    layer=me.color_attributes.get(key)
                    ci=li if layer and layer.domain=='CORNER' else me.loops[li].vertex_index
                    color_values[key].append(tuple(layer.data[ci].color) if layer else (1.,1.,1.,1.))
    me=bpy.data.meshes.new(name)
    me.from_pydata(verts,[],faces);me.update()
    for material in materials:me.materials.append(material)
    for poly,mi,sm in zip(me.polygons,indices,smooth):
        poly.material_index=mi;poly.use_smooth=sm
    for key,values_ in uv_values.items():
        layer=me.uv_layers.new(name=key)
        for datum,value in zip(layer.data,values_):datum.uv=value
    for key,values_ in color_values.items():
        layer=me.color_attributes.new(name=key,type='FLOAT_COLOR',domain='CORNER')
        for datum,value in zip(layer.data,values_):datum.color=value
    result=bpy.data.objects.new(name,me);ASSET.objects.link(result)
    for src in objects:bpy.data.objects.remove(src,do_unlink=True)
    result.name=name
    if parent:parent_world(result,parent)
    return result


def dynamic_ends(line):
    ends=[]
    for key in ("from","to"):
        node=line.get(key+"_object"); local=line.get(key+"_local")
        if node and local is not None and bpy.data.objects.get(node):
            p=bpy.data.objects[node].matrix_world@Vector(local)
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
    # The original furled-rig topsail-sheet lead blocks sit directly beneath
    # each lower yard. In the working trim they belong abaft the hanging course.
    # Move these small block/strop components together and add a supported
    # pendant back to the yard after the running rig has been rebuilt.
    for source in ('fok','grot'):
        y=CTX['rig']['reje'][source]
        c=Vector(y['c'])
        for side in (-1,1):
            old=c+Vector((side*.45,0,-y['sr']*.62))
            ATTACHMENT_MOVES.append((old,old+Vector((0,.28,0))))
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
            c=_yard_center(yard.name)
            updated=[]
            for p in path:
                attachment=_nearest_attachment(yard,p)
                if (attachment-p).length<line['diameter_m']/2+.07:
                    p=attachment
                else:
                    drop=max(0.,min(1.,(c.z-p.z)/.7))
                    p.y=max(p.y,c.y+.10+.40*drop)
                updated.append(p)
            path=updated
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
            anchor=_deck_anchor(1 if path[-1].x>0 else -1,9.8*SCALE_S)
            turning=anchor+Vector((0,0,.12))
            path=[path[0],turning,path[-1]]
            anchor=path[0].copy();anchor.x=0
            tube("brace_block_strop_%d"%line["id"],[anchor,path[0]],.025,TAR)
            bpy.ops.mesh.primitive_uv_sphere_add(segments=10,ring_count=6,location=turning)
            block=bpy.context.object; block.name="brace_turning_block_%d"%line["id"]
            block.scale=(.085,.07,.13); block.data.materials.append(bpy.data.materials["wood_dark"])
            for col in list(block.users_collection): col.objects.unlink(block)
            ASSET.objects.link(block)
            block["kind"]="fitting";block["asset_role"]="visual"
            block["intended_joint"]="turning block stropped to forged rail eye"
            tube("brace_turning_strop_%d"%line["id"],[anchor,turning],.018,TAR)
        elif line["group"]=="running" and path[0].z>5 and path[-1].z<4 and -3<path[0].y<3:
            turning=path[-1].copy(); turning.y=max(path[0].y,2.4)
            turning.z=float(DECKS.heights(turning.x,-turning.y))+.14
            path=[path[0],turning,path[-1]]
            bpy.ops.mesh.primitive_uv_sphere_add(segments=10,ring_count=6,location=turning)
            block=bpy.context.object; block.name="deck_lead_block_%d"%line["id"]
            block.scale=(.075,.08,.12);block.data.materials.append(bpy.data.materials["wood_dark"])
            for col in list(block.users_collection):col.objects.unlink(block)
            ASSET.objects.link(block)
            block["kind"]="fitting";block["asset_role"]="visual"
            block["intended_joint"]="lead block strapped to deck eye"
            foot=turning.copy();foot.z=DECKS.heights(foot.x,-foot.y)+.005
            tube("deck_lead_strop_%d"%line["id"],[foot,turning],.014,TAR)
        rope=tube("rope_static_line_%d"%line["id"],path,max(.014,line["diameter_m"]),ROPE)
        if rope:
            RIGGING_PATHS[rope.name]["source_line_id"]=line["id"]
            static.append(rope)
    join_rope_meshes(static,"rigging_running_sailing")
    for name,objects in perts.items():
        join_rope_meshes(objects,"rope_footropes_"+name+"_glb",bpy.data.objects[name])


def square_sail(name, yard_name, spec):
    yard = bpy.data.objects[yard_name]
    c = _yard_center(yard_name)
    head_drop = _yard_radius(yard_name)+.02
    nx, ny = 32, 24
    head, foot, depth = (spec[k] for k in ("head_m","foot_m","depth_m"))
    source_depth=depth
    lower_y=c.y
    if name.endswith(("topsail","topgallant")):
        lower_name=("fore_yard" if name=="fore_topsail" else "main_yard" if name=="main_topsail" else "fore_topsail_yard" if name.startswith("fore") else "main_topsail_yard")
        lower_y=_yard_center(lower_name).y
    if name.endswith("_course"):
        # The chapter-08 outline reaches the rail and is a sail-plan estimate,
        # not a tested playable mesh. Leave headroom over the deck, not the rail.
        foot_z=max(DECKS.required_height(0,-c.y+ds,CANVAS_CLEARANCE_M)
                   for ds in (-.8,0,.8))
        depth=min(depth,c.z-head_drop-foot_z)
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
            p = Vector((c.x+x,c.y*(1-t)+lower_y*t-belly-course_foot,c.z-depth*t+roach-head_drop))
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
            target = _nearest_attachment(bpy.data.objects[lower],target)
        else:
            target = _deck_anchor(side,-c.y-2.2*SCALE_S)
            if name=="spritsail":
                target = _deck_anchor(side,12.7*SCALE_S)
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


def _plain_id(value):
    if hasattr(value,'to_list'):
        return [_plain_id(v) for v in value.to_list()]
    if hasattr(value,'to_dict'):
        return {k:_plain_id(v) for k,v in value.to_dict().items()}
    if isinstance(value,dict):return {k:_plain_id(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [_plain_id(v) for v in value]
    return value


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
        # IDPropertyArray/Group values belong to their Blender owner. Copy them
        # into Python before deleting the old node, otherwise Blender5.2 may
        # dereference freed property storage while assigning the replacement.
        extras={k:_plain_id(obj[k]) for k in obj.keys()}
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


def geometry(obj,evaluated=False,rope_only=False,material_indices=None):
    evaluated_obj=obj.evaluated_get(bpy.context.evaluated_depsgraph_get()) if evaluated else None
    mesh=evaluated_obj.to_mesh() if evaluated else obj.data
    matrix=obj.matrix_world
    rope_materials={i for i,m in enumerate(mesh.materials) if m and m.name.startswith(("rope_tarred","rope_untarred"))}
    selected=rope_materials if rope_only else material_indices
    faces=[tuple(p.vertices) for p in mesh.polygons if selected is None or p.material_index in selected]
    if not faces:
        if evaluated_obj: evaluated_obj.to_mesh_clear()
        return None
    used=set(i for f in faces for i in f)
    remap={old:new for new,old in enumerate(sorted(used))}
    verts=[matrix@mesh.vertices[i].co for i in sorted(used)]
    faces=[tuple(remap[i] for i in f) for f in faces]
    edges=collections.Counter(tuple(sorted((a,b))) for f in faces for a,b in zip(f,f[1:]+f[:1]))
    lo=Vector(tuple(min(v[k] for v in verts) for k in range(3)))
    hi=Vector(tuple(max(v[k] for v in verts) for k in range(3)))
    record={"vertices":verts,"edges":list(edges),"lo":lo,"hi":hi}
    if not rope_only:
        record["bvh"]=BVHTree.FromPolygons(verts,faces,all_triangles=False,epsilon=1e-7)
        samples=[]
        for (a,b),count in edges.items():
            if count!=1: continue
            n=max(1,math.ceil((verts[a]-verts[b]).length/.015))
            samples.extend(verts[a].lerp(verts[b],i/n) for i in range(n+1))
        kd=KDTree(len(samples))
        for i,p in enumerate(samples):kd.insert(p,i)
        kd.balance(); record["boundary"]=kd
    if evaluated_obj: evaluated_obj.to_mesh_clear()
    return record


def intersections(source,target):
    if any(source["hi"][k]<target["lo"][k] or source["lo"][k]>target["hi"][k] for k in range(3)):
        return [],0
    hits=[]; boundary_contacts=0
    lo,hi=target["lo"],target["hi"]
    for i,j in source["edges"]:
        a,b=source["vertices"][i],source["vertices"][j]
        if any(max(a[k],b[k])<lo[k]-1e-5 or min(a[k],b[k])>hi[k]+1e-5 for k in range(3)):continue
        delta=b-a; length=delta.length
        if length<1e-7:continue
        point,_,_,_=target["bvh"].ray_cast(a,delta/length,length)
        if point is None:continue
        if target["boundary"].find(point)[2]<=.025:
            boundary_contacts+=1
        elif all((point-p).length>.08 for p in hits):hits.append(point)
    return hits,boundary_contacts


def audit_scene(frames=(0,),check_sails=True):
    old_frame=bpy.context.scene.frame_current
    bpy.context.scene.frame_set(0)
    ropes={}
    for obj in bpy.data.objects:
        if obj.type=="MESH" and not obj.name.startswith("preview_"):
            record=geometry(obj,rope_only=True)
            if record:ropes[obj.name]=record
    sail_specs=[]
    for obj in bpy.data.objects:
        if obj.type!="MESH":continue
        for index,material in enumerate(obj.data.materials):
            if material and material.name.startswith("flax_"):
                sail_specs.append((material.name.removeprefix("flax_")+"_set",obj,{index}))
    if len(sail_specs)!=12:
        raise ValueError("Expected all 12 cloth materials, found %d"%len(sail_specs))
    result={"frames":list(frames),"rope_objects":len(ropes),"sails":len(sail_specs),
            "boundary_tolerance_m":.025,"scope":"Rope mesh edges versus cloth interior; own bolt ropes are expected edge attachments. Sail edges versus other cloth interiors are checked in both directions.","per_frame":[],"hits":[]}
    for frame in frames:
        bpy.context.scene.frame_set(frame)
        sails={name:geometry(o,evaluated=True,material_indices=indices) for name,o,indices in sail_specs}
        crossing_pairs=0; contacts=0
        for rope,record in ropes.items():
            for sail,target in sails.items():
                if rope.startswith(sail.removesuffix("_set")+"_bolt_rope_"):continue
                hits,touch=intersections(record,target);contacts+=touch
                if hits:
                    crossing_pairs+=1
                    result["hits"].append({"frame":frame,"kind":"rope_canvas","rope":rope,"sail":sail,"points_blender_m":[[round(v,5) for v in p] for p in hits]})
        sail_pairs=0
        if check_sails:
            names=list(sails)
            for i,a in enumerate(names):
                for b in names[i+1:]:
                    h1,t1=intersections(sails[a],sails[b]);h2,t2=intersections(sails[b],sails[a]);contacts+=t1+t2
                    if h1 or h2:
                        sail_pairs+=1
                        result["hits"].append({"frame":frame,"kind":"canvas_canvas","a":a,"b":b,"points_blender_m":[[round(v,5) for v in p] for p in (h1+h2)[:16]]})
        result["per_frame"].append({"frame":frame,"rope_canvas_pairs":crossing_pairs,"canvas_canvas_pairs":sail_pairs,"perimeter_contacts":contacts})
    bpy.context.scene.frame_set(old_frame)
    result["passed"]=not result["hits"]
    return result




def _public_lines(ctx):
    import dane_publiczne as dp
    import nazwy_publiczne as npub
    trace=[dict(line,opis=line.get("_opis",[])) for line in ctx["liny"]]
    names=dp.nazwy_lin({"liny":trace})
    records=[]
    for index,(line,(pl,en,kind)) in enumerate(zip(ctx["liny"],names)):
        parent=line.get("parent")
        start,end=line["p"][0],line["p"][-1]
        od=YARD_NAMES.get(line.get("od"),line.get("od"))
        do=YARD_NAMES.get(line.get("do"),line.get("do"))
        group=npub.SLOWA.get(line["g"],line["g"])
        record={"id":index,"rope":en,"group":group,
            "kind":"standing" if line["m"]=="lina_smolowana" else "running",
            "material":"tarred" if line["m"]=="lina_smolowana" else "untarred",
            "diameter_m":line["d"],"length_m":sum((b-a).length for a,b in zip(line["p"],line["p"][1:])),
            "from":[start.x,-start.y,start.z],"to":[end.x,-end.y,end.z],
            "via":[[p.x,-p.y,p.z] for p in line["p"][1:-1]],
            "parent":parent.name if parent else None,
            "from_object":od,"to_object":do,"dynamic":bool(od or do),
            "variant":"deck_tiller_variant" if line.get("wariant")=="naped_rumpel" else None,
            "belayed_to":pl if line.get("_opis") and line["_opis"][0].get("fn")=="belay" else None}
        for key,node,p in [("from",od,start),("to",do,end)]:
            obj=bpy.data.objects.get(node) if node else None
            record[key+"_local"]=list(obj.matrix_world.inverted()@p) if obj else None
        records.append(record)
    return records


def _prepare_source(ctx):
    global ASSET,PARAMETERS,RIG,ROPE,TAR,DECKS
    print('V2_RIG_PREPARE_NAMES',flush=True)
    # Keep the reference hull/body names, so interior construction is unaffected.
    for old,new in YARD_NAMES.items():
        obj=bpy.data.objects.get(old)
        if obj:
            obj.name=new
            obj["working_height_dz_m"]=float(obj.get("wysokosc_robocza_dz_m",0))
    materials={"lina_smolowana":"rope_tarred","lina_jasna":"rope_untarred",
               "drewno_ciemne":"wood_dark","zelazo":"iron"}
    for old,new in materials.items():
        mat=bpy.data.materials.get(old)
        if mat:
            if bpy.data.materials.get(new) and bpy.data.materials[new]!=mat:
                bpy.data.materials[new].name=new+"_previous"
            mat.name=new
    ROPE=bpy.data.materials["rope_untarred"];TAR=bpy.data.materials["rope_tarred"]
    # Rolled canvas is replaced, while its spars, fittings and original rig survive.
    for obj in list(bpy.context.scene.objects):
        if obj.name.startswith(("zagiel_","zagle_sztakslowe")):
            bpy.data.objects.remove(obj,do_unlink=True)
    print('V2_RIG_PREPARE_COLLECTION',flush=True)
    ASSET=bpy.data.collections.new("V2_WORKING_RIG")
    bpy.context.scene.collection.children.link(ASSET)
    for obj in list(bpy.context.scene.objects):
        if obj.type not in ("MESH","EMPTY"):
            continue
        if obj.hide_render:
            obj["asset_role"]="presentation"
            continue
        ASSET.objects.link(obj)
    PARAMETERS={"groups":{"spars":{"values":{
        "fore_mast_rake_deg":ctx["PR"].DRZEWCA["FOK_POCHYL"],
        "main_mast_rake_deg":ctx["PR"].DRZEWCA["GROT_POCHYL"]}}}}
    RIG={"lines":_public_lines(ctx)}
    print('V2_RIG_PUBLIC_LINES',len(RIG['lines']),flush=True)
    DECKS=DeckEnvelope(ctx)
    # The old exported snow algorithm expects consolidated static rope+block mesh.
    # Original dynamic and yard-owned ropes retain separate nodes and explicit IDs.
    static=[]
    for obj in list(ASSET.objects):
        if obj.type!="MESH":continue
        if obj.name.startswith("lina_dyn_"):
            source_id=int(obj.name.rsplit("_",1)[1])
            line=RIG["lines"][source_id]
            obj.name="rope_dynamic_"+str(source_id)
            obj["dynamic"]=True;obj["line_id"]=source_id
            obj["from_object"]=line.get("from_object") or ""
            obj["to_object"]=line.get("to_object") or ""
            for key in ("from_local","to_local"):
                if line.get(key) is not None:obj[key]=line[key]
        elif obj.name.startswith("lina_perty"):
            obj.name="rope_footropes_"+(obj.parent.name if obj.parent else "unparented")+"_legacy"
        elif obj.name.startswith("lina_") and obj.parent is None or obj.name=="bloki":
            static.append(obj)
    if not static:
        raise ValueError("Original standing rig or blocks missing")
    print('V2_RIG_JOIN_STATIC',len(static),flush=True)
    join_rope_meshes(static,"rigging_static")
    print('V2_RIG_STATIC_READY',flush=True)
    for obj in list(ASSET.objects):
        if obj.type=="MESH" and obj.name.startswith("lina_") and obj.parent is not None:
            obj["kind"]="rope";obj["asset_role"]="visual"


def _yard_center(name):
    for y in CTX['rig']['reje'].values():
        if y['obj'].name==name:
            p=Vector(y['c'])
            return YARD_MOVES.get(name,Matrix.Identity(4))@p
    return bpy.data.objects[name].matrix_world.translation.copy()


def _yard_radius(name):
    for y in CTX['rig']['reje'].values():
        if y['obj'].name==name:return y['sr']/2
    raise KeyError(name)


def _square_specs(ctx):
    result={}
    mapping={"fore":"fok","main":"grot"}
    for public,source in mapping.items():
        low=ctx["rig"]["reje"][source]
        tops=ctx["rig"]["reje"][source+"mars"]
        topg=ctx["rig"]["reje"][source+"bram"]
        lower_world=bpy.data.objects[SQUARES[public+"_course"]].matrix_world.translation
        top_world=bpy.data.objects[SQUARES[public+"_topsail"]].matrix_world.translation
        tg_world=bpy.data.objects[SQUARES[public+"_topgallant"]].matrix_world.translation
        deck_foot=float(ctx["kd"].Zd(-lower_world.y)+ctx["kd"].rail_r(-lower_world.y))+.3
        result[public+"_course"]={"head_m":.9*low["L"],"foot_m":.95*low["L"],"depth_m":lower_world.z-deck_foot}
        result[public+"_topsail"]={"head_m":.9*tops["L"],"foot_m":.9*low["L"],"depth_m":top_world.z-lower_world.z}
        result[public+"_topgallant"]={"head_m":.9*topg["L"],"foot_m":.9*tops["L"],"depth_m":tg_world.z-top_world.z}
    y=ctx["rig"]["reje"]["blinda"];c=bpy.data.objects["spritsail_yard"].matrix_world.translation
    result["spritsail"]={"head_m":.9*y["L"],"foot_m":.95*y["L"],"depth_m":min(3.6,max(.4,c.z-.6))}
    return result


def _other_sails(ctx):
    # Same chapter-08 shapes as geometria.Statek.zagle, using current reference axes.
    kd=ctx["kd"]
    rail=lambda s:float(kd.Zd(s)+kd.rail_r(s))
    gf=ctx["rig"]["reje"]["gafel"]
    jaw,peak=Vector(gf["c"]),Vector(gf["end"])
    sn=ctx["rig"].get("snow")
    s_sn=sn["s"] if sn else ctx["PR"].DRZEWCA["GROT_S"]-.45
    tack=ship_point([0,s_sn-.1,float(kd.deck_c(s_sn))+1.4])
    axis=(peak-jaw).normalized()
    below=Vector((0,axis.z,-axis.y))
    jaw+=below*.24;peak+=below*(gf['sr']/2+.025)
    aft=-13.6*SCALE_S
    clew=ship_point([0,aft,rail(aft)+.6])
    panel_sail("gaff_sail",[tack,jaw,peak,clew],bpy.data.objects["gaff"])
    for name,stay,f0,f1,height in [
        ("jib","jib_stay",.06,.90,.50),
        ("fore_topmast_staysail","fore_topmast_stay",.10,.92,.55),
        ("main_topmast_staysail","main_topmast_stay",.12,.90,.50),
        ("main_staysail","main_stay",.30,.82,.55)]:
        line=next(l for l in RIG["lines"] if l["rope"]==stay)
        path=[ship_point(p) for p in [line["from"],*line["via"],line["to"]]]
        distances=[0.]
        for a,b in zip(path,path[1:]):distances.append(distances[-1]+(b-a).length)
        def on_stay(f):
            d=f*distances[-1]
            i=min(len(path)-2,max(0,int(np.searchsorted(distances,d,side="right")-1)))
            return path[i].lerp(path[i+1],(d-distances[i])/max(1e-8,distances[i+1]-distances[i]))
        def luff_curve(t):
            return on_stay(f0+(f1-f0)*t)+Vector((.14,0,0))
        head,tack=luff_curve(0),luff_curve(1)
        luff_length=(head-tack).length
        sc=-tack.y-height*luff_length
        if name=="fore_topmast_staysail":sc=max(sc,15.3*SCALE_S)
        if name=="jib":sc=max(sc,16.2*SCALE_S)
        clew=ship_point([0,sc,max(tack.z-.1*luff_length,rail(sc)+1)])
        clew.x={"jib":2.8,"fore_topmast_staysail":1.4,
                "main_topmast_staysail":1.2,"main_staysail":1.2}[name]*SCALE_X
        clew.z=max(clew.z,DECKS.required_height(clew.x,-clew.y,CANVAS_CLEARANCE_M))
        panel_sail(name,[head,tack,clew],luff=luff_curve)
        for i,t in enumerate(np.linspace(0,1,max(3,round(luff_length/1.2)))):
            f=f0+(f1-f0)*float(t);centre=on_stay(f)
            axis=(on_stay(min(1,f+.002))-on_stay(max(0,f-.002))).normalized()
            normal=Vector((1,0,0));normal=(normal-axis*normal.dot(axis)).normalized()
            other=axis.cross(normal).normalized()
            radius=.12 if line["diameter_m"]>.06 else .095
            centre+=normal*(.14-radius)
            ring=[centre+radius*(normal*math.cos(a)+other*math.sin(a))
                  for a in np.linspace(0,2*math.pi,17)]
            obj=tube(name+"_hank_%d"%i,ring,.008,bpy.data.materials["iron"],sides=5)
            obj["kind"]="fitting";obj["asset_role"]="visual"
            obj["intended_joint"]="hank fastens sail luff to supporting stay"
        anchor_s=11.55*SCALE_S if name=="jib" else 10.9*SCALE_S if name=="fore_topmast_staysail" else sc-1
        anchor=_deck_anchor(1,anchor_s)
        tube(name+"_sheet",[clew,anchor],.022,ROPE)


def _cloth_uv_and_tags(obj):
    mesh=obj.data
    points=[obj.matrix_world@v.co for v in mesh.vertices]
    if obj.name.startswith(tuple(SQUARES)):
        u,v=Vector((1,0,0)),Vector((0,0,-1))
    else:
        # First row of the panel generator follows the luff from tack to head.
        origin=points[0]
        v=(points[min(24,len(points)-1)]-origin).normalized()
        normal=Vector()
        for p in mesh.polygons:
            normal+=obj.matrix_world.to_3x3()@p.normal
        normal.normalize()
        u=v.cross(normal).normalized()
    uv=mesh.uv_layers.active or mesh.uv_layers.new(name="UVMap")
    colors=mesh.color_attributes.new(name="ThreadTone",type="FLOAT_COLOR",domain="CORNER")
    maxz=max(p.z for p in points)
    for face in mesh.polygons:
        for li in face.loop_indices:
            co=points[mesh.loops[li].vertex_index]
            uv.data[li].uv=(co.dot(u)/1.14,co.dot(v)/1.14)
            zdist=maxz-co.z
            tone=.77 if "topsail" in obj.name and min(abs(zdist-.9),abs(zdist-1.8))<.04 else 1.
            colors.data[li].color=(tone,tone,tone,1)
    material=mesh.materials[0]
    nt=material.node_tree;bs=nt.nodes.get("Principled BSDF")
    source=bs.inputs["Base Color"].links[0].from_socket
    vertex=nt.nodes.new("ShaderNodeVertexColor");vertex.layer_name="ThreadTone"
    mix=nt.nodes.new("ShaderNodeMixRGB");mix.blend_type="MULTIPLY";mix.inputs[0].default_value=1
    nt.links.new(source,mix.inputs[1]);nt.links.new(vertex.outputs["Color"],mix.inputs[2])
    nt.links.new(mix.outputs[0],bs.inputs["Base Color"])
    obj["source"]="docs/en/08-ropes-blocks-and-sails.md; chapter-08 plan estimates, game clearance cuts"


def _tag_final(ctx):
    spars={o.name for o in [ctx["obj"].get("drzewca"),ctx["obj"].get("bukszpryt")] if o}
    spars|={y["obj"].name for y in ctx["rig"]["reje"].values() if y.get("obj")}
    for obj in ASSET.objects:
        if obj.type!="MESH":continue
        obj["asset_role"]="visual"
        if obj.name.endswith("_set") and any(m and m.name.startswith("flax_") for m in obj.data.materials):
            obj["kind"]="sail";_cloth_uv_and_tags(obj)
        elif "bolt_rope_" in obj.name:
            obj["kind"]="rope";obj["edge_attachment"]=True
            obj["attachment_sail"]=obj.name.split("_bolt_rope_")[0]+"_set"
        elif obj.name in spars:
            obj["kind"]="spar"
        elif obj.get('kind')!='fitting' and (obj.name.startswith(('lina_','rope_')) or
                obj.name in ('rigging_static','rigging_running_sailing') or obj.name in RIGGING_PATHS):
            obj["kind"]="rope"
    # Enforce actual canvas head attachment to the wood by short robands.
    for name,yard in SQUARES.items():
        obj=bpy.data.objects[name+"_set"]
        n=32
        points=[obj.matrix_world@v.co for v in obj.data.vertices[:n+1]]
        target=bpy.data.objects[yard]
        for k in range(0,n+1,2):
            p=points[k];q=_nearest_attachment(target,p)
            tie=tube(name+"_roband_%02d"%k,[p,q],.010,ROPE,sides=5)
            if tie:
                tie["kind"]="rope";tie["asset_role"]="visual";tie["edge_attachment"]=True
                tie["attachment_sail"]=obj.name
                RIGGING_PATHS[tie.name].update(from_object=obj.name,to_object=target.name)
    obj=bpy.data.objects['gaff_sail_set']
    for edge,target in [('head',bpy.data.objects['gaff']),
                        ('luff',ctx['obj']['drzewca'])]:
        indices=[j*25+24 for j in range(25)] if edge=='head' else list(range(25))
        for k in range(0,25,2):
            p=obj.matrix_world@obj.data.vertices[indices[k]].co
            q=_nearest_attachment(target,p)
            tie=tube('gaff_sail_roband_'+edge+'_%02d'%k,[p,q],.010,ROPE,sides=5)
            if tie:
                tie['kind']='rope';tie['asset_role']='visual';tie['edge_attachment']=True
                tie['attachment_sail']=obj.name
                RIGGING_PATHS[tie.name].update(from_object=obj.name,to_object=target.name)


def _split_static_blocks():
    """Keep block targets separate from rope geometry for endpoint verification."""
    obj=bpy.data.objects.get('rigging_static')
    if not obj:return
    rope_slots={i for i,m in enumerate(obj.data.materials) if m and
                m.name.startswith(('rope_tarred','rope_untarred'))}
    block=obj.copy();block.data=obj.data.copy();block.name='rigging_static_blocks'
    ASSET.objects.link(block)
    for source,remove_rope in [(block,True),(obj,False)]:
        bm=bmesh.new();bm.from_mesh(source.data)
        faces=[f for f in bm.faces if (f.material_index in rope_slots)==remove_rope]
        bmesh.ops.delete(bm,geom=faces,context='FACES')
        bmesh.ops.delete(bm,geom=[v for v in bm.verts if not v.link_faces],context='VERTS')
        bm.to_mesh(source.data);bm.free()
    block['kind']='fitting';block['asset_role']='visual'
    block['intended_joint']='original running-rigging blocks and strops; attachment relocation follows hoisted yards'


def _support_sheet_blocks():
    block=bpy.data.objects.get('rigging_static_blocks')
    if block is None:return
    for source in ('fok','grot'):
        y=CTX['rig']['reje'][source];yard=y['obj']
        c=Vector(y['c'])
        for side in (-1,1):
            old=c+Vector((side*.45,0,-y['sr']*.62))
            end=_nearest_attachment(block,old+Vector((0,.28,0)))
            start=_nearest_attachment(yard,end)
            obj=tube('sheet_lead_pendant_'+source+'_'+str(side),[start,end],.016,TAR)
            if obj:
                obj['kind']='rope';obj['asset_role']='visual'
                RIGGING_PATHS[obj.name].update(from_object=yard.name,to_object=block.name)


def _paths_report():
    result=list(RIGGING_PATHS.values())
    changed_ids={r.get("source_line_id") for r in result}
    for line in RIG["lines"]:
        if line["id"] in changed_ids:continue
        if line["dynamic"] or line["group"]=="footropes" or line["material"]=="untarred":
            continue
        result.append({"name":line["rope"]+"_"+str(line["id"]),"mesh_object":"rigging_static",
            "diameter_m":line["diameter_m"],"points_gltf_m":[[p[0],p[2],p[1]] for p in [line["from"],*line["via"],line["to"]]],
            "from_object":line.get("from_object"),"to_object":line.get("to_object"),
            "source_line_id":line["id"]})
    # Bolt ropes are explicitly closed/edge attachments; audit their cloth boundary.
    for record in result:
        name=record["name"]
        source=record.get('source_line_id')
        record['source_rope']=RIG['lines'][source]['rope'] if source is not None else name
        if "_bolt_rope_" in name or "_roband_" in name:
            record["attachment_sail"]=name.split("_bolt_rope_")[0].split("_roband_")[0]+"_set"
    return result


def audit_attachment_paths(paths):
    """Quantify physical rope termini without using their own mesh as target.

    Other ropes are tested against distinct centreline segments and their true
    radii. Solids/cloth use BVHs of the current scene. A terminal in a closed
    solid passes only after consistent parity in two oblique directions.
    """
    bodies=[]
    for obj in bpy.context.scene.objects:
        if obj.type!='MESH' or obj.hide_render or obj.get('asset_role') in ('presentation','collision'):
            continue
        if obj.get('kind')=='rope' or obj.name.startswith(('lina_','rope_','COL_')):
            continue
        if not obj.data.polygons:continue
        vertices=[obj.matrix_world@v.co for v in obj.data.vertices]
        lo=Vector(tuple(min(v[k] for v in vertices) for k in range(3)))
        hi=Vector(tuple(max(v[k] for v in vertices) for k in range(3)))
        bodies.append({'name':obj.name,'kind':obj.get('kind'),'lo':lo,'hi':hi,
                       'tree':BVHTree.FromPolygons(vertices,[list(p.vertices) for p in obj.data.polygons])})
    records=[];segments=[];samples=[]
    max_radius=0.
    for i,record in enumerate(paths):
        points=[Vector((p[0],-p[2],p[1])) for p in record['points_gltf_m']]
        radius=float(record['diameter_m'])/2
        max_radius=max(max_radius,radius)
        records.append((record,points,radius))
        for a,b in zip(points,points[1:]):
            if (b-a).length<1e-7:continue
            si=len(segments);segments.append((i,a,b,radius))
            steps=max(1,math.ceil((b-a).length/.10))
            samples.extend((a.lerp(b,k/steps),si) for k in range(steps+1))
    kd=KDTree(len(samples))
    for i,(p,_) in enumerate(samples):kd.insert(p,i)
    kd.balance()
    def solid_inside(body,p):
        if body['kind']=='sail':return False
        if any(p[k]<body['lo'][k]-1e-5 or p[k]>body['hi'][k]+1e-5 for k in range(3)):
            return False
        parity=[]
        for direction in (Vector((.019,.011,1)).normalized(),Vector((.017,1,.023)).normalized()):
            origin=p.copy();count=0
            for _ in range(128):
                hit=body['tree'].ray_cast(origin,direction)
                if hit[0] is None:break
                count+=1;origin=hit[0]+direction*1e-5
            parity.append(bool(count%2))
        return all(parity)
    tested=[];failures=[];exceptions=[];closed=[]
    for i,(record,points,radius) in enumerate(records):
        if len(points)<2:continue
        if (points[0]-points[-1]).length<.001:
            closed.append(record['name']);continue
        for endpoint,p in [('from',points[0]),('to',points[-1])]:
            result={'rope':record['name'],'endpoint':endpoint,'point_gltf_m':[p.x,p.z,-p.y]}
            # Own mesh is never considered an attachment solid.
            best=None
            for body in bodies:
                if body['name']==record.get('mesh_object'):continue
                reach=radius+.012
                if any(p[k]<body['lo'][k]-reach or p[k]>body['hi'][k]+reach for k in range(3)):
                    continue
                nearest=body['tree'].find_nearest(p,reach)
                if nearest[0] is not None:
                    distance=max(0.,nearest[3]-radius)
                    if distance<=.01 and (best is None or distance<best[0]):
                        best=(distance,body['name'],'surface contact')
                if best is None and solid_inside(body,p):
                    best=(0.,body['name'],'inside intended solid')
            if best is None:
                candidates=set(samples[index][1] for _,index,_ in kd.find_range(p,radius+max_radius+.12))
                for si in candidates:
                    j,a,b,other_radius=segments[si]
                    if j==i:continue
                    delta=b-a
                    t=max(0.,min(1.,(p-a).dot(delta)/delta.length_squared))
                    distance=max(0.,(p-(a+delta*t)).length-radius-other_radius)
                    if distance<=.01 and (best is None or distance<best[0]):
                        other=records[j][0]
                        relation='continuous rope segment joint' if other.get('source_rope')==record.get('source_rope') else 'other rope'
                        best=(distance,other['name'],relation)
            if best is not None:
                result.update(passed=True,surface_gap_m=best[0],target=best[1],connection=best[2])
            else:
                logical=record.get('source_rope',record['name'])
                free=None
                if logical.startswith('coil_') and endpoint=='to':
                    free='free tail of a stored belayed coil; its first end remains subject to attachment test'
                elif logical=='bell_rope' and p.z<=min(points[0].z,points[-1].z)+.001:
                    free='intentional free lower end of the bell pull, chapter13 exception'
                if free:
                    result.update(passed=True,listed_exception=free);exceptions.append(result.copy())
                else:
                    result.update(passed=False);failures.append(result.copy())
            tested.append(result)
    return {'passed':not failures,'tolerance_m':.01,'rope_records':len(records),
            'tested_termini':len(tested),'closed_loops_without_ends':closed,
            'listed_free_end_exceptions':exceptions,'failure_count':len(failures),
            'failures':failures,'termini':tested,
            'scope':'current scene geometry and distinct declared rope paths; own rope mesh excluded; two-ray parity for solid interiors; surface gap accounts for true rope radius'}


def _sail_metrics():
    area=0.;moment=Vector()
    sails=[]
    for obj in ASSET.objects:
        if obj.type!="MESH" or obj.get("kind")!="sail":continue
        obj.data.calc_loop_triangles()
        sa=0.;sm=Vector()
        for tri in obj.data.loop_triangles:
            p=[obj.matrix_world@obj.data.vertices[i].co for i in tri.vertices]
            a=(p[1]-p[0]).cross(p[2]-p[0]).length/2
            sa+=a;sm+=(p[0]+p[1]+p[2])/3*a
        area+=sa;moment+=sm
        sails.append({"name":obj.name,"area_m2":sa,
            "centre_gltf_m":list(Vector((sm.x,sm.z,-sm.y))/sa) if sa else [0,0,0],
            "source_depth_m":obj.get("source_depth_m"),"game_depth_m":obj.get("game_depth_m")})
    centre=moment/area
    return {"total_surface_area_m2":area,"centre_of_area_gltf_m":[centre.x,centre.z,-centre.y],"sails":sails}


def audit_spars():
    sails={o.name:geometry(o) for o in ASSET.objects if o.type=="MESH" and o.get("kind")=="sail"}
    hits=[]
    for obj in ASSET.objects:
        if obj.type!="MESH" or obj.get("kind") not in ('spar','fitting'):continue
        record=geometry(obj)
        for name,target in sails.items():
            points,contacts=intersections(record,target)
            if points:
                hits.append({"spar":obj.name,"sail":name,"points":[list(p) for p in points[:12]]})
    return {"passed":not hits,"intersections":hits,"scope":"spar mesh edges vs cloth interior; 25 mm actual-boundary tolerance"}


def deploy(ctx,spec,out=None,strict=True):
    global OUT,CTX,SCALE_S,SCALE_X,RIGGING_PATHS,YARD_MOVES,_CANVAS_IMAGES,_ATTACHMENT_TREES
    CTX=ctx;SCALE_S=spec["length"]/28;SCALE_X=spec["beam"]/7.6
    OUT=Path(out or ctx["out"]).resolve();OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"textures").mkdir(exist_ok=True)
    RIGGING_PATHS={};_CANVAS_IMAGES=None;_ATTACHMENT_TREES={}
    _prepare_source(ctx)
    print('V2_RIG_HOIST',flush=True)
    moved=hoist_yards();YARD_MOVES=moved
    print('V2_RIG_ATTACHMENTS',flush=True)
    prepare_attachment_moves()
    print('V2_RIG_RUNNING',flush=True)
    rebuild_running_and_footropes(moved)
    print('V2_RIG_DYNAMIC',flush=True)
    changed=rebuild_dynamic()
    print('V2_RIG_CANVAS',flush=True)
    for name,yard in SQUARES.items():
        square_sail(name,yard,_square_specs(ctx)[name])
    _other_sails(ctx)
    print('V2_RIG_TAG',flush=True)
    _split_static_blocks()
    _support_sheet_blocks()
    _tag_final(ctx)
    bpy.context.view_layer.update()
    print('V2_RIG_AUDIT',flush=True)
    ctx["_v2_running_rebuilt"]=True
    for source,y in ctx["rig"]["reje"].items():
        name=y["obj"].name
        if name in moved:
            for key in ("c","axis_pt"):
                if key in y:y[key]=moved[name]@Vector(y[key])
            if "z" in y:y["z"]=y["c"].z
    report={"source":"original repo chapters 05–08 plus validated snow working-rig reconstruction",
        "source_reference_commit":"2e6f7e922e95396722376d42f3e2e0a12256029e",
        "authored_state":"static working trim; no wind animation",
        "game_label":spec["label"],"historical_rig":"snow c.1710; game BRIG label retained",
        "canvas_clearance_target_m":CANVAS_CLEARANCE_M,
        "main_lower_mast_m":ctx["PR"].DRZEWCA["GROT"],
        "fore_lower_mast_m":ctx["PR"].DRZEWCA["FOK"],
        "main_lower_yard_m":ctx["PR"].DRZEWCA["GROTREJA"],
        "rebuilt_dynamic_line_ids":changed,"rigging_paths":_paths_report(),
        "sail_metrics":_sail_metrics(),"rope_canvas":audit_scene(frames=(0,)),
        "spar_canvas":audit_spars()}
    report["passed"]=report["rope_canvas"]["passed"] and report["spar_canvas"]["passed"]
    report['attachments']=audit_attachment_paths(report['rigging_paths'])
    ctx['obj']['liny']=[o for o in ASSET.objects if o.type=='MESH' and o.get('kind')=='rope']
    if 'bloki' in ctx['obj']:
        ctx['obj']['bloki']=bpy.data.objects.get('rigging_static_blocks')
    ctx["_v2_rigging_report"]=report
    (OUT/"rigging-working.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    if strict and not report["passed"]:
        raise ValueError("Working rig intersects cloth; inspect rigging-working.json")
    return report

