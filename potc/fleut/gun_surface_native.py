"""Blender adapter for the frozen pure casting-surface mapper prototype."""
from __future__ import annotations
import hashlib,json
import numpy as np
import gun_surface_fix as F

def _plain(value):
    if hasattr(value,'to_dict'):return {str(k):_plain(v)for k,v in value.to_dict().items()}
    if hasattr(value,'to_list'):return [_plain(v)for v in value.to_list()]
    if isinstance(value,dict):return {str(k):_plain(v)for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [_plain(v)for v in value]
    return value

def _array(collection,field,width,dtype=np.float32):
    a=np.empty(len(collection)*width,dtype=dtype);collection.foreach_get(field,a)
    return a.reshape(len(collection),width)

def _sha(a):
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()

def canonical_corner_surface(obj,mesh=None):
    """Actual stored source surfaces in glTF world convention, including V flip."""
    mesh=obj.data if mesh is None else mesh;mesh.calc_loop_triangles()
    positions=_array(mesh.vertices,'co',3).astype(float)
    matrix=np.array(obj.matrix_world,dtype=float)
    world=positions@matrix[:3,:3].T+matrix[:3,3]
    triangles=np.array([tuple(t.vertices)for t in mesh.loop_triangles],dtype=int)
    loops=np.array([tuple(t.loops)for t in mesh.loop_triangles],dtype=int)
    normals=_array(mesh.corner_normals,'vector',3).astype(float)
    normals=normals@np.linalg.inv(matrix[:3,:3]);normals/=np.linalg.norm(normals,axis=1)[:,None]
    surface=next(q for q in mesh.uv_layers if q.name!='DetailAO')
    uv=_array(surface.data,'uv',2);ao=_array(mesh.uv_layers['DetailAO'].data,'uv',2)
    # Blender UV origin differs from glTF; do the same float32 flip as export.
    uv=uv.copy();ao=ao.copy();uv[:,1]=np.float32(1)-uv[:,1];ao[:,1]=np.float32(1)-ao[:,1]
    convert=lambda a:np.stack((a[...,0],a[...,2],-a[...,1]),axis=-1)
    return {'positions':convert(world),'triangles':triangles,'normals':convert(normals[loops]),'uv0':uv[loops],'uv1':ao[loops]}

def evaluated_corner_surface(obj):
    import bpy
    graph=bpy.context.evaluated_depsgraph_get();evaluated=obj.evaluated_get(graph)
    mesh=evaluated.to_mesh(preserve_all_data_layers=True,depsgraph=graph)
    try:return canonical_corner_surface(evaluated,mesh)
    finally:evaluated.to_mesh_clear()

def repair_object(obj,normal_mode='free'):
    """Change only this casting's smooth/crease state, custom normals and two UVs."""
    mesh=obj.data;mesh.calc_loop_triangles()
    positions=_array(mesh.vertices,'co',3);before_pos=_sha(positions)
    indices=_array(mesh.loops,'vertex_index',1,np.int32);before_indices=_sha(indices)
    matrix=np.array(obj.matrix_world,dtype=float);world=positions.astype(float)@matrix[:3,:3].T+matrix[:3,3]
    triangles=np.array([tuple(t.vertices)for t in mesh.loop_triangles],dtype=int)
    loops=np.array([tuple(t.loops)for t in mesh.loop_triangles],dtype=int)
    if any(len(p.vertices)!=3 for p in mesh.polygons):
        raise ValueError('Frozen casting must already be triangulated; topology changes are forbidden')
    metadata=json.loads(obj['rope_path_json']);assert metadata['axes']=='blender_world'
    a,b=map(np.array,[metadata['points'][0],metadata['points'][-1]])
    mat=mesh.materials[0];tile=tuple(mat['uv_tile_m'])
    cn,cu,info=F.map_corners(world,triangles,a,b,float(obj['diameter_m'])/2,(0,0,-1),tile)
    local=cn@matrix[:3,:3];local/=np.linalg.norm(local,axis=2)[:,:,None]
    normal_loops=np.empty((len(mesh.loops),3),np.float32)
    uv_loops=np.empty((len(mesh.loops),2),np.float32)
    for ti,ids in enumerate(loops):
        normal_loops[ids]=local[ti]
        uv_loops[ids,0]=cu[ti,:,0]
        uv_loops[ids,1]=1-cu[ti,:,1]
    rings=info['rings']
    desired_sharp=np.array([rings[e.vertices[0]]==rings[e.vertices[1]]for e in mesh.edges],dtype=bool)
    desired_smooth=np.array([1<=band<=7 or band==9 for band in info['bands']],dtype=bool)
    surface=next(q for q in mesh.uv_layers if q.name!='DetailAO')
    attr=mesh.attributes.get('custom_normal')
    already_fixed=bool(normal_mode=='free'and attr is not None and attr.data_type=='FLOAT_VECTOR'and attr.domain=='CORNER'
        and np.array_equal(_array(attr.data,'vector',3),normal_loops)
        and np.array_equal(_array(surface.data,'uv',2),uv_loops)
        and np.array_equal(_array(mesh.uv_layers['DetailAO'].data,'uv',2),uv_loops)
        and np.array_equal(_array(mesh.edges,'use_edge_sharp',1,np.int8).ravel().astype(bool),desired_sharp)
        and np.array_equal(_array(mesh.polygons,'use_smooth',1,np.int8).ravel().astype(bool),desired_smooth))
    for edge in mesh.edges:
        edge.use_edge_sharp=bool(rings[edge.vertices[0]]==rings[edge.vertices[1]])
    for ti,poly in enumerate(mesh.polygons):
        poly.use_smooth=bool(1<=info['bands'][ti]<=7 or info['bands'][ti]==9)
    if not hasattr(mesh,'normals_split_custom_set'):
        raise RuntimeError('This Blender lacks the required custom split normal API')
    if normal_mode=='custom':
        mesh.normals_split_custom_set(normal_loops.tolist())
    elif normal_mode=='auto':
        # Zero custom vectors explicitly request Blender's geometry-derived
        # smooth normals. The existing sharp profile edges still split them.
        mesh.normals_split_custom_set([(0.,0.,0.)]*len(mesh.loops))
    elif normal_mode=='free':
        # Modern FREE normals are explicit float3 CORNER data. The legacy
        # normals_split_custom_set API can first encode through tangent space.
        attr=mesh.attributes.get('custom_normal')
        if attr and(attr.data_type!='FLOAT_VECTOR'or attr.domain!='CORNER'):
            mesh.attributes.remove(attr);attr=None
        if attr is None:attr=mesh.attributes.new('custom_normal','FLOAT_VECTOR','CORNER')
        attr.data.foreach_set('vector',normal_loops.ravel())
    else:raise ValueError('Unknown native normal mode')
    surface=next(q for q in mesh.uv_layers if q.name!='DetailAO')
    surface.data.foreach_set('uv',uv_loops.ravel())
    mesh.uv_layers['DetailAO'].data.foreach_set('uv',uv_loops.ravel())
    mesh.update();mesh.calc_loop_triangles()
    assert _sha(_array(mesh.vertices,'co',3))==before_pos
    assert _sha(_array(mesh.loops,'vertex_index',1,np.int32))==before_indices
    stored=canonical_corner_surface(obj)
    # Ideal map expressed in glTF world for a direct stored-data check.
    ideal_norm=np.stack((cn[...,0],cn[...,2],-cn[...,1]),axis=-1)
    return {'node':obj.name,'positions_sha256_before_after':before_pos,
            'normal_mode':normal_mode,
            'already_fixed':already_fixed,
            'loop_indices_sha256_before_after':before_indices,
            'stored_normal_vs_ideal_max_error':float(np.max(np.abs(stored['normals']-ideal_norm))),
            'stored_uv_vs_ideal_max_error':float(np.max(np.abs(stored['uv0']-cu))),
            'stored_uv0_ao1_equal':bool(np.array_equal(stored['uv0'],stored['uv1'])),
            'density_compensation':F.DENSITY_COMPENSATION,
            'meridian':'world-down projected perpendicular to axis',
            'profile_match_max_m':info['profile_match_max_m']}

def mesh_signature(obj,include_surface=True):
    mesh=obj.data;h=hashlib.sha256()
    for a in (_array(mesh.vertices,'co',3),_array(mesh.loops,'vertex_index',1,np.int32),_array(mesh.polygons,'material_index',1,np.int32)):
        h.update(a.tobytes())
    if include_surface:
        h.update(_array(mesh.corner_normals,'vector',3).tobytes())
        for uv in mesh.uv_layers:h.update(uv.name.encode());h.update(_array(uv.data,'uv',2).tobytes())
        h.update(_array(mesh.polygons,'use_smooth',1,np.int8).tobytes())
        h.update(_array(mesh.edges,'use_edge_sharp',1,np.int8).tobytes())
    h.update(np.array(obj.matrix_world,dtype=np.float64).tobytes())
    h.update(json.dumps({str(k):_plain(v)for k,v in obj.items()},sort_keys=True).encode())
    h.update(repr([m.name if m else None for m in mesh.materials]).encode())
    return h.hexdigest()

def non_target_snapshot(target_names):
    import bpy
    result={}
    for obj in bpy.data.objects:
        if obj.type=='MESH':result[obj.name]=mesh_signature(obj,obj.name not in target_names)
        else:result[obj.name]=hashlib.sha256((repr(np.array(obj.matrix_world).tolist())+json.dumps({str(k):_plain(v)for k,v in obj.items()},sort_keys=True)).encode()).hexdigest()
    return result

def materials_images_snapshot():
    import bpy
    materials={}
    for mat in bpy.data.materials:
        if not mat.users:continue
        data={'diffuse':list(mat.diffuse_color),'extras':{str(k):_plain(v)for k,v in mat.items()},'nodes':[],'links':[]}
        if mat.use_nodes:
            for n in mat.node_tree.nodes:
                inputs=[]
                for i,s in enumerate(n.inputs):
                    if not hasattr(s,'default_value'):continue
                    value=s.default_value
                    try:value=list(value)
                    except TypeError:pass
                    inputs.append((i,str(value)))
                data['nodes'].append((n.name,n.bl_idname,inputs,getattr(getattr(n,'image',None),'name',None)))
            data['links']=[(l.from_node.name,l.from_socket.identifier,l.to_node.name,l.to_socket.identifier)for l in mat.node_tree.links]
        materials[mat.name]=data
    images={}
    for im in bpy.data.images:
        if not im.users:continue
        packed=bytes(im.packed_file.data)if im.packed_file else b''
        images[im.name]={'size':list(im.size),'colorspace':im.colorspace_settings.name,'filepath':im.filepath,'packed_sha256':hashlib.sha256(packed).hexdigest()}
    return {'materials':materials,'images':images}
