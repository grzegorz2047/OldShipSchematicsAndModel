"""Surface-only cannon repair prototype. No architecture/material changes.

Pure numpy mapper shared by host GLB and the forthcoming Blender adapter.
The outer casting has one continuous cylindrical chart and one meridian.
Planar end/annulus charts and the inner cylinder are separate physical charts.
"""
from __future__ import annotations
import copy, hashlib, json, math, struct
from pathlib import Path
import numpy as np

VERSION = 'casting-surface-3-down-meridian-density105'
DENSITY_COMPENSATION = 1.05
GLTF_MERIDIAN_REFERENCE = (0., -1., 0.)
PROFILE = np.array([(0,0),(0,.70),(.035,.90),(.10,1.03),(.20,1.),
                    (.58,.92),(.87,.84),(.95,.94),(1,.94),(1,.57),
                    (.69,.57),(.67,0)],dtype=float)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def map_corners(positions, triangles, a, b, radius, reference_u, tile=(1.,1.), density_compensation=DENSITY_COMPENSATION):
    """Return per-corner normals/UV, preserving every input position/index.

    All coordinates use one world frame. Profile hard breaks remain hard;
    only circumferential normals of each actual side surface are smoothed.
    """
    positions=np.asarray(positions,dtype=float);triangles=np.asarray(triangles,dtype=int)
    a=np.asarray(a,dtype=float);b=np.asarray(b,dtype=float)
    axis=b-a;length=float(np.linalg.norm(axis));axis/=length
    u=np.asarray(reference_u,dtype=float);u-=axis*np.dot(u,axis);u/=np.linalg.norm(u)
    v=np.cross(axis,u)
    relative=positions-a
    t=relative@axis
    radial=relative-t[:,None]*axis
    r=np.linalg.norm(radial,axis=1)
    theta=np.mod(np.arctan2(radial@v,radial@u),2*math.pi)
    stations=np.mod(np.rint(theta*20/(2*math.pi)).astype(int),20)
    canonical_theta=stations*(2*math.pi/20)
    angular_error=np.abs(np.arctan2(np.sin(theta-canonical_theta),np.cos(theta-canonical_theta)))
    angular_error=angular_error[r>radius*.1]
    if angular_error.size and float(angular_error.max())>5e-4:
        raise ValueError('Casting does not have the expected twenty angular stations')
    theta=canonical_theta
    expected=PROFILE*np.array([length,radius])
    distances=(t[:,None]-expected[None,:,0])**2+(r[:,None]-expected[None,:,1])**2
    rings=np.argmin(distances,axis=1)
    error=np.sqrt(distances[np.arange(len(positions)),rings])
    tolerance=max(3e-5,radius*2e-4)
    if float(error.max())>tolerance:
        raise ValueError('Casting does not match the actual frozen 12-station profile: '+str(float(error.max())))
    ring_tri=rings[triangles]
    bands=ring_tri.min(axis=1)
    if not np.all(ring_tri.max(axis=1)==bands+1):
        raise ValueError('Unexpected nonadjacent profile face')
    profile_delta=np.diff(expected,axis=0)
    slants=np.linalg.norm(profile_delta,axis=1)
    cumulative=np.r_[0.,np.cumsum(slants)]
    # Minimax reference circumference over the complete visible outer wall.
    # Its .70..1.03 radial range has a <1.25 metric scale ratio at this radius.
    outer_radius=math.sqrt(float(expected[1:9,1].min()*expected[1:9,1].max()))
    inner_radius=float(expected[9,1])
    points=positions[triangles]
    face=np.cross(points[:,1]-points[:,0],points[:,2]-points[:,0])
    face/=np.linalg.norm(face,axis=1)[:,None]
    normals=np.empty_like(points);uv=np.empty((len(triangles),3,2),float)
    for fi,(indices,band) in enumerate(zip(triangles,bands)):
        band=int(band);angles=theta[indices].copy()
        if angles.max()-angles.min()>math.pi:
            angles[angles<math.pi]+=2*math.pi
        if 1<=band<=7 or band==9:
            ds,dr=profile_delta[band]
            rr=np.cos(theta[indices,None])*u+np.sin(theta[indices,None])*v
            nn=ds*rr-dr*axis
            normals[fi]=nn/np.linalg.norm(nn,axis=1)[:,None]
            if band==9:
                uv[fi,:,0]=length-t[indices]
                uv[fi,:,1]=inner_radius*angles
            else:
                uv[fi,:,0]=cumulative[rings[indices]]-cumulative[1]
                uv[fi,:,1]=outer_radius*angles
        else:
            # Back disk, muzzle annulus and recessed drill-end cone have
            # continuous planar charts and their existing hard face normals.
            normals[fi]=face[fi]
            uv[fi,:,0]=radial[indices]@u
            uv[fi,:,1]=radial[indices]@v
    uv/=np.asarray(tile,dtype=float)
    # Explicit authored density compensation, not a changed tile or gate:
    # the minimax continuous cylinder chart otherwise undershoots the frozen
    # iron weighted-median density floor. Both UV0 and DetailAO use this scale.
    uv*=float(density_compensation)
    if not np.isfinite(normals).all() or not np.isfinite(uv).all():
        raise ValueError('Nonfinite output surface')
    return normals,uv,{'bands':bands,'rings':rings,'profile_match_max_m':float(error.max()),
                       'outer_reference_radius_m':outer_radius,'axis':axis.tolist(),
                       'validated_twenty_station_snap_max_rad':float(angular_error.max())if angular_error.size else 0.,
                       'authored_continuous_chart_density_compensation':float(density_compensation),
                       'outer_chart_meridian':'world-down projected perpendicular to actual axis; one seam through all seven outer bands',
                       'separate_charts':['back disk','muzzle annulus','inner cylinder','drill-end cone']}

def corner_to_vertices(triangles, corner_values, old_values, tolerance=2e-5):
    result=np.array(old_values,dtype=float,copy=True);seen={}
    for indices,values in zip(triangles,corner_values):
        for index,value in zip(indices,values):
            index=int(index)
            if index in seen and np.max(np.abs(seen[index]-value))>tolerance:
                raise ValueError('Existing vertex split cannot represent the new surface without changing indices: '+str(index))
            seen[index]=value;result[index]=value
    return result

def uv_metrics(positions,triangles,corner_uv,image_size=(2048,2048)):
    pts=np.asarray(positions)[triangles];e1=pts[:,1]-pts[:,0];e2=pts[:,2]-pts[:,0]
    cr=np.cross(e1,e2);double=np.linalg.norm(cr,axis=1);area=double/2
    a1=e1/np.linalg.norm(e1,axis=1)[:,None];normal=cr/double[:,None];a2=np.cross(normal,a1)
    dot=lambda a,b:np.einsum('ij,ij->i',a,b)
    domain=np.stack((np.stack((dot(e1,a1),dot(e2,a1)),axis=1),np.stack((dot(e1,a2),dot(e2,a2)),axis=1)),axis=1)
    uv=np.stack((corner_uv[:,1]-corner_uv[:,0],corner_uv[:,2]-corner_uv[:,0]),axis=2)
    matrix=uv@np.linalg.inv(domain);singular=np.linalg.svd(np.diag(image_size)@matrix,compute_uv=False)
    anisotropy=singular[:,0]/np.maximum(singular[:,1],1e-30)
    uvarea=np.abs(np.linalg.det(uv))/2
    density=np.sqrt(uvarea*np.prod(image_size)/area)
    order=np.argsort(density);cumulative=np.cumsum(area[order]);weighted=[]
    for percentile in (.05,.50,.95):
        at=min(int(np.searchsorted(cumulative,cumulative[-1]*percentile)),len(order)-1)
        weighted.append(float(density[order[at]]))
    return {'density_min_p50_max_px_m':np.quantile(density,[0,.5,1]).tolist(),
            'density_area_weighted_p5_p50_p95_px_m':weighted,
            'anisotropy_max':float(anisotropy.max()),
            'anisotropy_over_1_25_area_share':float(area[anisotropy>1.25].sum()/area.sum()),
            'degenerate_uv_triangles':int((uvarea<1e-14).sum()),'surface_area_m2':float(area.sum())}

def read_glb(path):
    raw=Path(path).read_bytes();magic,version,total=struct.unpack_from('<III',raw)
    assert magic==0x46546c67 and version==2 and total==len(raw)
    jl,jt=struct.unpack_from('<II',raw,12);assert jt==0x4e4f534a
    doc=json.loads(raw[20:20+jl]);offset=20+jl;bl,bt=struct.unpack_from('<II',raw,offset);assert bt==0x004e4942
    return doc,raw[offset+8:offset+8+bl],raw

def accessor(doc,binary,index):
    a=doc['accessors'][index];view=doc['bufferViews'][a['bufferView']]
    dtype=np.dtype({5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1',5122:'<i2',5120:'i1'}[a['componentType']])
    n={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[a['type']]
    return np.ndarray((a['count'],n),dtype=dtype,buffer=binary,
        offset=view.get('byteOffset',0)+a.get('byteOffset',0),
        strides=(view.get('byteStride',dtype.itemsize*n),dtype.itemsize)).copy()

def append_attribute(doc,binary,array):
    while len(binary)%4:binary.extend(b'\x00')
    array=np.asarray(array,dtype='<f4');offset=len(binary);payload=array.tobytes();binary.extend(payload)
    view=len(doc['bufferViews']);doc['bufferViews'].append({'buffer':0,'byteOffset':offset,'byteLength':len(payload),'target':34962})
    index=len(doc['accessors']);doc['accessors'].append({'bufferView':view,'componentType':5126,'count':len(array),'type':'VEC'+str(array.shape[1])})
    return index

def encode_glb(doc,binary):
    while len(binary)%4:binary.extend(b'\x00')
    doc['buffers'][0]['byteLength']=len(binary)
    js=json.dumps(doc,separators=(',',':'),ensure_ascii=False).encode()
    js+=b' '*((-len(js))%4)
    return struct.pack('<III',0x46546c67,2,12+8+len(js)+8+len(binary))+struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(binary),0x004e4942)+binary

def _world_matrix(doc,index):
    parents={c:i for i,n in enumerate(doc['nodes'])for c in n.get('children',[])}
    def local(n):
        if 'matrix'in n:return np.array(n['matrix'],dtype=float).reshape(4,4).T
        t=np.array(n.get('translation',[0,0,0]),float);s=np.array(n.get('scale',[1,1,1]),float)
        x,y,z,w=n.get('rotation',[0,0,0,1])
        r=np.array([[1-2*y*y-2*z*z,2*x*y-2*z*w,2*x*z+2*y*w],[2*x*y+2*z*w,1-2*x*x-2*z*z,2*y*z-2*x*w],[2*x*z-2*y*w,2*y*z+2*x*w,1-2*x*x-2*y*y]])
        m=np.eye(4);m[:3,:3]=r@np.diag(s);m[:3,3]=t;return m
    m=local(doc['nodes'][index])
    while index in parents:index=parents[index];m=local(doc['nodes'][index])@m
    return m

def patch_glb(source,destination,exact_nodes):
    doc,oldbin,oldraw=read_glb(source);before=copy.deepcopy(doc);binary=bytearray(oldbin);ledgers=[];changed=False
    for name in exact_nodes:
        ni=next(i for i,n in enumerate(doc['nodes'])if n.get('name')==name)
        node=doc['nodes'][ni];assert node.get('extras',{}).get('role')=='cannon_barrel'
        mi=node['mesh'];assert sum(n.get('mesh')==mi for n in doc['nodes'])==1
        primitives=doc['meshes'][mi]['primitives'];assert len(primitives)==1
        primitive=primitives[0];attrs=primitive['attributes'];assert 'TANGENT'not in attrs
        local=accessor(doc,oldbin,attrs['POSITION']).astype(float);world=_world_matrix(doc,ni)
        positions=local@world[:3,:3].T+world[:3,3]
        triangles=accessor(doc,oldbin,primitive['indices']).astype(int).ravel().reshape(-1,3)
        metadata=json.loads(node['extras']['rope_path_json']);assert metadata['axes']=='blender_world'
        convert=lambda q:np.array([q[0],q[2],-q[1]],float)
        a,b=map(convert,[metadata['points'][0],metadata['points'][-1]])
        radius=float(node['extras']['diameter_m'])/2
        material=doc['materials'][primitive['material']];tile=material['extras']['uv_tile_m']
        oldnormal=accessor(doc,oldbin,attrs['NORMAL']);olduv=accessor(doc,oldbin,attrs['TEXCOORD_0'])
        cn,cu,details=map_corners(positions,triangles,a,b,radius,GLTF_MERIDIAN_REFERENCE,tile)
        # Transform world normals to the unchanged node-local frame.
        cn=cn@world[:3,:3];cn/=np.linalg.norm(cn,axis=2)[:,:,None]
        normals=corner_to_vertices(triangles,cn,oldnormal)
        uvs=corner_to_vertices(triangles,cu,olduv)
        oldao=accessor(doc,oldbin,attrs['TEXCOORD_1'])
        already_fixed=np.array_equal(normals.astype('<f4'),oldnormal)and np.array_equal(uvs.astype('<f4'),olduv)and np.array_equal(uvs.astype('<f4'),oldao)
        if not already_fixed:
            changed=True
            attrs['NORMAL']=append_attribute(doc,binary,normals)
            uv_accessor=append_attribute(doc,binary,uvs)
            attrs['TEXCOORD_0']=uv_accessor;attrs['TEXCOORD_1']=uv_accessor
        ledgers.append({'node':name,'mesh':mi,'triangles':len(triangles),'vertices':len(local),
            'profile_match_max_m':details['profile_match_max_m'],
            'angular_snap_max_rad':details['validated_twenty_station_snap_max_rad'],
            'authored_density_compensation':details['authored_continuous_chart_density_compensation'],
            'already_fixed':bool(already_fixed),
            'unit_normal_max_error':float(np.abs(np.linalg.norm(normals,axis=1)-1).max()),
            'before_uv':uv_metrics(positions,triangles,olduv[triangles]),
            'after_uv':uv_metrics(positions,triangles,cu),
            'outer_chart_meridian':details['outer_chart_meridian'],'separate_charts':details['separate_charts']})
    output=encode_glb(doc,binary)if changed else oldraw
    if changed or Path(destination).resolve()!=Path(source).resolve():Path(destination).write_bytes(output)
    # Byte-level proof: only target attribute references and appended streams
    # may differ. Shared original views/accessors/payloads remain untouched.
    restored=copy.deepcopy(doc)
    for entry in ledgers:
        restored['meshes'][entry['mesh']]['primitives'][0]['attributes']=before['meshes'][entry['mesh']]['primitives'][0]['attributes']
    restored['accessors']=restored['accessors'][:len(before['accessors'])]
    restored['bufferViews']=restored['bufferViews'][:len(before['bufferViews'])]
    restored['buffers']=before['buffers']
    assert restored==before and bytes(binary[:len(oldbin)])==oldbin
    return {'version':VERSION,'source':str(source),'destination':str(destination),
            'before_sha256':digest(oldraw),'after_sha256':digest(output),
            'before_bytes':len(oldraw),'after_bytes':len(output),
            'original_BIN_prefix_identical':True,'original_accessors_views_identical':True,
            'non_target_document_identical':True,'target_POSITION_indices_identical':True,
            'nodes_transforms_extras_materials_textures_images_samplers_identical':True,
            'helper_sha256':digest(Path(__file__).read_bytes()),'targets':ledgers}
