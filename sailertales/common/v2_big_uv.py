"""Big-vessel timber UV finishing; preserves positions and material appearances.

Call finish_uv(visual, design) AFTER mesh cleanup/budget and PBR material upgrade.
Returns the complete visual list and ledger. Does not modify shared audit/materials.
Separate existing disconnected closed timber solids before measuring their grain;
a row of vertical timberheads must not inherit the entire ship's longitudinal axis.
"""
import fnmatch
import json
import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from v2_export import snake

WOOD=('wood','oak','pine','drew','deck','poklad','plank')
EXEMPT=('rope','lina','glass','szklo','canvas','flax','plotno','grating','krata')
MOTION=('motion_axis','range_deg','range_m','os_ruchu','control_type','control')


def wood(m):return m is not None and any(x in m.name.lower() for x in WOOD)
def exempt(m):return m is None or any(x in m.name.lower() for x in EXEMPT)


def connected_closed_islands(o):
    bm=bmesh.new();bm.from_mesh(o.data)
    unseen=set(bm.faces);count=0;closed=True
    while unseen:
        f=unseen.pop();stack=[f];faces=[f]
        while stack:
            for e in stack.pop().edges:
                for n in e.link_faces:
                    if n in unseen:unseen.remove(n);faces.append(n);stack.append(n)
        closed=closed and all(e.is_manifold for f in faces for e in f.edges)
        count+=1
    bm.free();return count,closed


def split_timbers(objects,design):
    result=list(objects);groups={}
    for o in list(objects):
        if o.type!='MESH' or any(k in o for k in MOTION) or not any(wood(m) for m in o.data.materials):continue
        count,closed=connected_closed_islands(o)
        if count<2 or not closed:continue
        old=o.name;before=set(bpy.context.scene.objects)
        bpy.ops.object.select_all(action='DESELECT');o.hide_set(False);o.select_set(True)
        bpy.context.view_layer.objects.active=o
        bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.separate(type='LOOSE');bpy.ops.object.mode_set(mode='OBJECT')
        added=list(set(bpy.context.scene.objects)-before)
        pieces=[o]+added
        # Keep the original assembly name on its largest physical timber.
        def stable_piece_key(p):
            coords=[p.matrix_world@v.co for v in p.data.vertices]
            center=sum(coords,Vector())/max(1,len(coords))
            bounds=tuple(round(fn(q[k] for q in coords),8)
                         for fn in (min,max) for k in range(3))
            return (-len(p.data.polygons),tuple(round(q,8) for q in center),bounds)
        pieces.sort(key=stable_piece_key)
        for i,p in enumerate(pieces):p.name='_uv_timber_temp_'+str(i)
        for i,p in enumerate(pieces):
            p.name=old if i==0 else snake(old)+'_timber_%03d'%i
            p['source_assembly']=old
            p['grain_measurement']='individual existing closed timber solid'
        result.extend(p for p in pieces if p is not o)
        groups[old]=[p.name for p in pieces]
    if groups:
        expanded=[]
        for rule in design.get('intended_joints',[]):
            aa=[rule.get('a','')];bb=[rule.get('b','')]
            for old,names in groups.items():
                if fnmatch.fnmatchcase(old,rule.get('a','')):
                    pattern=snake(old)+'_timber_*'
                    if any(n!=old and not fnmatch.fnmatchcase(n,rule.get('a','')) for n in names) and pattern not in aa:aa.append(pattern)
                if fnmatch.fnmatchcase(old,rule.get('b','')):
                    pattern=snake(old)+'_timber_*'
                    if any(n!=old and not fnmatch.fnmatchcase(n,rule.get('b','')) for n in names) and pattern not in bb:bb.append(pattern)
            for a in aa:
                for b in bb:
                    copy=dict(rule);copy.update(a=a,b=b);expanded.append(copy)
        design['intended_joints']=expanded
    return result,groups


def principal(points):
    p=np.asarray(points,dtype=np.float64)
    cov=np.cov(p.T) if len(p)>2 else np.eye(3)
    values,vectors=np.linalg.eigh(cov)
    return Vector(vectors[:,-1]),values


def grain_path(o):
    authored=o.get('grain_path_json')
    if not authored:return []
    p=json.loads(authored) if isinstance(authored,str) else authored
    coords=p.get('points',[]) if isinstance(p,dict) else p
    axes=p.get('axes','object_local') if isinstance(p,dict) else 'object_local'
    if axes.lower() in ('gltf','gltf_world'):return [Vector((q[0],-q[2],q[1])) for q in coords]
    if axes.lower() in ('blender','blender_world','world'):return [Vector(q) for q in coords]
    return [o.matrix_world@Vector(q) for q in coords]


def near_tangent(center,path,fallback):
    best=None
    for a,b in zip(path,path[1:]):
        d=b-a
        if d.length_squared<1e-20:continue
        t=max(0,min(1,(center-a).dot(d)/d.length_squared))
        dist=(center-a-t*d).length_squared
        if best is None or dist<best[0]:best=(dist,d.normalized())
    return best[1] if best else fallback


def image_and_tile(m):
    if not m.use_nodes:return None,None
    images=[n.image for n in m.node_tree.nodes if n.type=='TEX_IMAGE' and n.image]
    colors=[im for im in images if any(x in im.name.lower() for x in ('color','colour','kolor','albedo','base'))]
    if not colors:colors=[im for im in images if im.colorspace_settings.name=='sRGB']
    if not colors:return None,None
    im=colors[0];tile=m.get('uv_tile_m')
    if tile is None:
        # Original guide fittings: retain their declared physical 2m timber tile.
        tile=(im.size[0]/1024.,im.size[1]/1024.)
    return im,tuple(float(x) for x in tile)


def resize_big_atlases(objects):
    """Keep large-vessel hull/deck atlases near the guide's 1k px/m target.

    The 8k x 2k atlas working images oversample these physical timber tiles.
    A 4k x 1k delivery image retains 1163px/m deck and 931px/m hull paint.
    Repack the changed pixels so the standalone Blender scene keeps the resize.
    """
    seen=set();ledger=[]
    for o in objects:
        if o.type!='MESH':continue
        for material in o.data.materials:
            if not material or not material.use_nodes:continue
            for node in material.node_tree.nodes:
                if node.type!='TEX_IMAGE' or node.image is None:continue
                im=node.image
                if im.as_pointer() in seen:continue
                seen.add(im.as_pointer())
                before=tuple(im.size)
                if before!=(8192,2048):continue
                im.scale(4096,1024)
                im.pack()
                ledger.append({'image':im.name,'source_px':list(before),
                               'delivery_px':list(im.size),'physical_tiles_unchanged':True})
    return ledger


def finish_uv(objects,design,split=True):
    resized=resize_big_atlases(objects)
    objects,groups=split_timbers(objects,design) if split else (list(objects),{})
    changed=0;triangles=0;annotated=[];instance_cache={};reused_instances=0
    for o in objects:
        if o.type!='MESH' or not any(not exempt(m) for m in o.data.materials):continue
        # Rigidly moved physical instances have the same UV solution. Keep one
        # processed mesh so the GLB retains the original indexed mesh budget.
        linear=o.matrix_world.to_3x3();metric=linear.transposed()@linear
        inverse=o.matrix_world.inverted_safe()
        local_path=tuple(tuple(round(v,8) for v in inverse@q) for q in grain_path(o))
        # Unit rigid transforms carry float32 noise around 1e-7 in the source.
        # Six decimals groups the same physical scale across rotated instances.
        cache_key=(o.data.as_pointer(),tuple(round(metric[i][j],6) for i in range(3) for j in range(3)),local_path)
        if cache_key in instance_cache:
            entry=instance_cache[cache_key];o.data=entry['mesh']
            if entry.get('grain_path_json') and not o.get('grain_path_json'):
                o['grain_path_json']=entry['grain_path_json']
                o['grain_axis_basis']=entry['grain_axis_basis']
            o['uv_finish']='metric triangle charts, original phase; U follows actual timber axis/path'
            reused_instances+=1
            continue
        if o.data.users>1:o.data=o.data.copy()
        bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.triangulate(bm,faces=list(bm.faces))
        bm.to_mesh(o.data);bm.free();o.data.update()
        me=o.data;uv=me.uv_layers.active or me.uv_layers.new(name='uv_metre')
        world=[o.matrix_world@v.co for v in me.vertices]
        axis,values=principal(world)
        path=grain_path(o)
        if not path:
            # Metal/wood assemblies such as anchors: the wood stock has its own
            # real timber axis; the iron shank's principal axis is irrelevant.
            ids={i for face in me.polygons if face.material_index<len(me.materials) and wood(me.materials[face.material_index]) for i in face.vertices}
            if len(ids)>3:
                wp=[world[i] for i in ids];wax,wvals=principal(wp)
                if wvals[-1]>6.25*max(wvals[-2],1e-12) and abs(wax.dot(axis))<math.cos(math.radians(20)):
                    center=sum(wp,Vector())/len(wp);dist=[(q-center).dot(wax) for q in wp]
                    path=[center+wax*min(dist),center+wax*max(dist)]
                    o['grain_path_json']=json.dumps({'axes':'object_local','points':[list(inverse@q) for q in path]})
                    o['grain_axis_basis']='principal axis of actual wooden stock, excluding iron fittings'
                    annotated.append(o.name)
        settings={i:image_and_tile(m) for i,m in enumerate(me.materials) if not exempt(m)}
        for face in me.polygons:
            if face.material_index not in settings:continue
            im,tile=settings[face.material_index]
            if im is None:continue
            ids=list(face.vertices);qs=[world[i] for i in ids]
            if len(qs)!=3:continue
            e1,e2=qs[1]-qs[0],qs[2]-qs[0];normal=e1.cross(e2)
            if normal.length<1e-13:continue
            normal.normalize();center=sum(qs,Vector())/3
            tangent=near_tangent(center,path,axis)
            u=tangent-normal*tangent.dot(normal)
            if u.length<1e-7:u=e1.copy()
            u.normalize();v=normal.cross(u).normalized()
            old=np.array([tuple(uv.data[li].uv) for li in face.loop_indices])
            # Preserve good original charts and their continuity; repair actual
            # distortion or a cross-grain timber face. UV centroids preserve phase.
            a1=e1.normalized();a2=normal.cross(a1)
            domain=np.array([[e1.dot(a1),e2.dot(a1)],[e1.dot(a2),e2.dot(a2)]])
            edges=np.stack((old[1]-old[0],old[2]-old[0]),axis=1)
            bad=True
            try:
                jac=edges@np.linalg.inv(domain)
                singular=np.linalg.svd(np.diag(tuple(im.size))@jac,compute_uv=False)
                bad=singular[0]/max(singular[1],1e-15)>1.24
                if wood(me.materials[face.material_index]) and abs(normal.dot(tangent))<.5:
                    direction=np.linalg.solve(jac,np.array([1.,0.]));old_u=a1*direction[0]+a2*direction[1]
                    bad=bad or abs(old_u.normalized().dot(tangent))<math.cos(math.radians(20))
            except np.linalg.LinAlgError:pass
            if not bad:continue
            # Pixel-isometric axes. Existing physical atlas proportions are
            # retained; rectangular atlases have matching rectangle metre tiles.
            anchor=old.mean(axis=0)
            for li,q in zip(face.loop_indices,qs):
                delta=q-center
                uv.data[li].uv=(anchor[0]+delta.dot(u)/tile[0],anchor[1]+delta.dot(v)/tile[1])
            triangles+=1;changed+=1
        o['uv_finish']='metric triangle charts, original phase; U follows actual timber axis/path'
        instance_cache[cache_key]={'mesh':o.data,'grain_path_json':o.get('grain_path_json'),
                                   'grain_axis_basis':o.get('grain_axis_basis')}
    ledger={'method':'repair distorted charts and transverse timber grain at real atlas metre scale',
            'delivery_atlas_resize':resized,
            'split_existing_closed_timber_assemblies':groups,'material_specific_timber_axes':annotated,
            'repaired_triangles':triangles,'reused_mesh_instances':reused_instances,
            'positions_changed':False,'material_images_changed':False}
    design['uv_finish']=ledger
    return objects,ledger
