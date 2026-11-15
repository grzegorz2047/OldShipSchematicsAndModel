"""Deterministic, exportable physical PBR surfaces for the detailed POTC fleet.

The maps are project-authored imagery.  There are no runtime procedural shader
nodes: glTF receives image base colour, tangent normals and packed ORM.  This is
an additive implementation; the accepted guide assets and their cache are read
only.  Cache versioning prevents a partial old bake being silently reused.
"""
import gc
import hashlib
import json
import math
import struct
import sys
import zlib
from pathlib import Path

import bpy
import numpy as np

VERSION = 'potc-pbr-v5.6'
TAU = 2 * math.pi
# Width follows grain; height is across grain.  Main deck and hull maps retain
# the accepted detailed guide brig's full 8192 x 2048 pixels.
FAMILIES = {
    'deck': (8192, 2048, 3.52, .88),
    'hull': (8192, 2048, 4.4, 1.1),
    'paint': (8192, 2048, 4.4, 1.1),
    'wood': (2048, 2048, 2., 2.),
    'iron': (2048, 2048, 1., 1.),
    'brass': (2048, 2048, 1., 1.),
    'canvas': (2048, 2048, 2.4, 2.4),
    'rope': (2048, 1024, .12, .11),
    'glass': (512, 512, .5, .5),
    'leather': (1024, 1024, .5, .5),
    'paper': (1024, 1024, .5, .5),
    'brick': (1024, 1024, 1.04, 1.04),
}
# Tint factors are linear multipliers over baked sRGB imagery.  Only the two
# paint entries are changed during palette export.
ROLES = {
    'deck': ('deck', (1., 1., 1.), 0.),
    'wood': ('wood', (1., 1., 1.), 0.),
    'spar': ('wood', (.60, .53, .44), 0.),
    'paintHull': ('paint', (1., 1., 1.), 0.),
    'paintTrim': ('paint', (1., 1., 1.), 0.),
    'rope': ('rope', (1., 1., 1.), 0.),
    'ropeTar': ('rope', (.095, .105, .105), 0.),
    'canvas': ('canvas', (1., 1., 1.), 0.),
    'iron': ('iron', (1., 1., 1.), 1.),
    'brass': ('brass', (1., 1., 1.), 1.),
    'seam': ('wood', (.055, .065, .063), 0.),
    'glass': ('glass', (1., 1., 1.), 0.),
    'leather': ('leather', (1., 1., 1.), 0.),
    'paper': ('paper', (1., 1., 1.), 0.),
    'brick': ('brick', (1., 1., 1.), 0.),
}
NAMES = {
    'deck': 'natural_deck_wood', 'wood': 'natural_wood',
    'spar': 'natural_spar_wood', 'paintHull': 'paint_hull',
    'paintTrim': 'paint_trim', 'rope': 'natural_rope',
    'ropeTar': 'natural_rope_tarred', 'canvas': 'natural_canvas',
    'iron': 'natural_iron', 'brass': 'natural_brass',
    'seam': 'natural_seam_wood', 'glass': 'natural_glass',
    'leather': 'natural_leather', 'paper': 'natural_paper', 'brick': 'natural_brick',
}


def register_materials(ctx):
    """Add roles to the Context before authoring. Existing roles stay untouched."""
    for role in ROLES:
        if role in ctx.materials:
            continue
        material = bpy.data.materials.new('source_' + role)
        material.diffuse_color = (.45, .32, .2, 1.)
        material['material_role'] = role
        material['uv_tile_m'] = ([1., .5] if role in ('rope', 'ropeTar') else [2., 2.])
        ctx.materials[role] = material
    return ctx.materials


def _chunk(handle, kind, data):
    handle.write(struct.pack('>I', len(data)))
    handle.write(kind)
    handle.write(data)
    handle.write(struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff))


def _png(path, pixels):
    """Lossless 8-bit RGB, row-streamed; never allocate a float RGBA 8k image."""
    pixels = np.asarray(pixels, dtype=np.uint8)
    height, width, channels = pixels.shape
    assert channels == 3
    partial = Path(str(path) + '.tmp')
    with partial.open('wb') as handle:
        handle.write(b'\x89PNG\r\n\x1a\n')
        _chunk(handle, b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
        compressor = zlib.compressobj(6)
        buffer = bytearray()
        for row in pixels:
            # Sub filtering preserves fine grain and compresses smooth normals.
            filtered = row.copy()
            filtered[1:] = row[1:] - row[:-1]
            buffer.extend(compressor.compress(b'\x01' + filtered.tobytes()))
            if len(buffer) >= 1024 * 1024:
                _chunk(handle, b'IDAT', bytes(buffer)); buffer.clear()
        buffer.extend(compressor.flush())
        if buffer:
            _chunk(handle, b'IDAT', bytes(buffer))
        _chunk(handle, b'IEND', b'')
    partial.replace(path)


def _stats(array):
    flat = array.reshape(-1, 3)
    # Statistics are computed over a regular spatial sample, not just metadata.
    sample = flat[::max(1, len(flat) // 262144)].astype(np.float32) / 255.
    return {'minimum': sample.min(axis=0).round(6).tolist(),
            'maximum': sample.max(axis=0).round(6).tolist(),
            'stddev': sample.std(axis=0).round(6).tolist()}


def _save(path, pixels):
    pixels = np.clip(pixels * 255. + .5, 0, 255).astype(np.uint8)
    stats = _stats(pixels)
    _png(path, pixels)
    stats.update({'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                  'bytes': path.stat().st_size})
    return stats


def _wave(x, y, seed, terms=6):
    """Periodic irregular low-frequency colour variation, fixed authored seed."""
    rng = np.random.default_rng(seed)
    result = np.zeros((y.shape[0], x.shape[1]), np.float32)
    for i in range(terms):
        fx = int(rng.integers(1, 15)); fy = int(rng.integers(1, 13))
        phase = float(rng.uniform(0, TAU))
        result += np.sin(TAU * (fx*x + fy*y) + phase).astype(np.float32) / (i + 2.)
    return result / 1.6


def _wood(family, x, y, tu, tv):
    cloud = _wave(x, y, 128, 7)
    rows = 4 if family in ('deck', 'hull', 'paint') else 0
    # Broad early/late wood and thin uneven fibres flow around the knots.
    warp = .0035*np.sin(TAU*(3*x + .17*np.sin(TAU*y)))
    warp += .0012*np.sin(TAU*(11*x-2*y))
    knots = np.zeros_like(cloud)
    for cx, cy, strength in ((.18,.12,.8),(.66,.39,1.),(.42,.68,.7),(.88,.90,.8)):
        dx = ((x-cx+.5)%1-.5)*tu
        dy = ((y-cy+.5)%1-.5)*tv
        radius = np.sqrt((dx/.075)**2 + (dy/.024)**2)
        mask = np.exp(-radius*radius*.35).astype(np.float32)
        warp += (.014/tv) * np.sin(np.arctan2(dy/.024, dx/.075)) * mask * strength
        knots += mask * (.62 + .08*np.cos(13*radius))
    warped = y + warp
    grain = np.sin(TAU*(157*warped + .42*np.sin(TAU*5*x)))
    grain += .40*np.sin(TAU*(479*warped + .7*np.sin(TAU*7*x)))
    grain += .19*np.sin(TAU*(887*warped + .3*np.sin(TAU*19*x)))
    grain = grain.astype(np.float32)
    latewood = np.maximum(0, np.sin(TAU*(29*warped + .21*np.sin(TAU*3*x))))**9
    earlywood = np.sin(TAU*(53*warped + .27*np.sin(TAU*2*x)))
    ray = np.maximum(0,np.sin(TAU*(31*x+27*y)))**18
    ray *= np.maximum(0,np.sin(TAU*(7*x-2*y)))**12
    pores = np.maximum(0, np.sin(TAU*(271*y + .1*np.sin(TAU*9*x))))**14
    pores *= .45+.55*np.sin(TAU*37*x)**2
    tone = .022*grain*(.8+.4*cloud) + .030*cloud - .11*knots - .025*pores - .035*latewood + .012*earlywood + .012*ray
    height = .000045*grain + .000035*cloud - .00007*pores - .00008*knots - .000035*latewood
    seam = np.zeros_like(cloud); peg = np.zeros_like(cloud); wear = np.zeros_like(cloud)
    if rows:
        row = np.floor(y*rows)
        local = (y*rows) % 1
        edge = np.minimum(local, 1-local)*(tv/rows)
        longitudinal = np.exp(-(edge/.0028)**4)
        # One butt in each row, staggered on a 4-shift pattern.  Both end-grain
        # joins and the paired fasteners are baked at physical dimensions.
        offset = (.11 + row*.25) % 1
        butt_distance = np.abs(((x-offset+.5)%1)-.5)*tu
        butt = np.exp(-(butt_distance/.0022)**4)
        seam = np.maximum(longitudinal, butt)
        wear = np.exp(-(edge/.009)**2) + np.exp(-(butt_distance/.008)**2)
        for sign in (-1, 1):
            along = np.abs(butt_distance - .038)
            cross = np.abs(local-(.26 if sign<0 else .74))*(tv/rows)
            r = np.sqrt(along*along+cross*cross)
            peg = np.maximum(peg, np.exp(-(r/.006)**8))
        # Thin annular dark ring reads as a wooden trunnel rather than a screw.
        peg_ring = np.clip(np.exp(-((np.sqrt((np.abs(butt_distance-.038))**2 +
                       (np.minimum(np.abs(local-.26),np.abs(local-.74))*(tv/rows))**2)-.006)/.0013)**2),0,1)
        plank = .018*np.sin(TAU*(row*.371 + np.floor((x-offset)%1)*.17))
        tone += plank - .43*seam + .018*wear + .019*peg - .038*peg_ring
        height += -.0011*seam + .00012*peg - .00010*peg_ring
    if family == 'paint':
        # Grayscale paint substrate is multiplied only by exported paint factors.
        tone = .88 + .48*tone
        color = np.repeat(tone[:,:,None], 3, axis=2)
        height *= .45
    else:
        base = np.array((.64,.565,.445) if family=='deck' else (.53,.365,.215), np.float32)
        color = np.clip(base[None,None,:] + tone[:,:,None]*np.array((1.,.86,.60),np.float32),0,1)
        color += (.007*cloud)[:,:,None]*np.array((.4,1.,.7),np.float32)
    roughness = np.clip(.67 + .055*cloud + .06*seam + .025*pores - .03*wear, .43, .90)
    ao = np.clip(1-.28*seam-.06*knots, .58, 1)
    return color, height, roughness, ao


def _surface(family, x, y, tu, tv):
    if family in ('deck','hull','paint','wood'):
        return _wood(family,x,y,tu,tv)
    cloud = _wave(x,y,79,7)
    if family == 'canvas':
        # 60cm linen panels, folded double seam, staggered hand stitching.
        panel = np.minimum((x*4)%1,1-(x*4)%1)*.6
        seam = np.exp(-(panel/.0038)**2)
        stitch_x = np.exp(-((panel-.006)/.0011)**2)
        stitch_y = (np.maximum(0,np.cos(TAU*240*y))**6)
        stitch = stitch_x*stitch_y
        weave = np.sin(TAU*509*x)*np.sin(TAU*503*y)
        threads = .6*np.sin(TAU*251*x)+.4*np.sin(TAU*241*y)
        tone = .014*cloud + .009*weave + .008*threads - .065*seam -.070*stitch
        color = np.array((.82,.785,.685),np.float32)[None,None,:]+tone[:,:,None]
        height = .000075*weave+.00004*threads+.00035*seam+.00012*stitch
        roughness = .88+.035*cloud+.015*weave
        ao = 1-.09*seam-.06*stitch
    elif family == 'rope':
        strand = np.cos(TAU*(3*y-x+.025*np.sin(TAU*x)))
        groove = np.exp(-((strand+1)/.22)**2)
        fibres = .6*np.sin(TAU*(167*y-53*x))+.4*np.sin(TAU*(283*y-91*x))
        tone = .045*strand+.016*fibres+.018*cloud-.085*groove
        color=np.array((.58,.485,.325),np.float32)[None,None,:]+tone[:,:,None]
        height=.0018*strand+.00012*fibres-.0004*groove
        roughness=.83+.025*cloud+.04*groove;ao=1-.17*groove
    elif family in ('iron', 'brass'):
        pits = np.maximum(0,np.sin(TAU*(151*x+.4*np.sin(TAU*31*y)))*np.sin(TAU*139*y))**8
        hammer = np.sin(TAU*(23*x+19*y))*.3 + cloud*.7
        rust = np.clip((cloud-.13)*2.7,0,1)
        color=np.array((.21,.22,.215),np.float32)[None,None,:]+(.045*hammer-.065*pits)[:,:,None]
        color+=rust[:,:,None]*np.array((.11,.029,-.045),np.float32)
        if family=='brass':
            color=np.array((.61,.43,.19),np.float32)[None,None,:]+(.035*hammer-.05*pits)[:,:,None]
            color+=rust[:,:,None]*np.array((-.20,-.08,.055),np.float32)
        height=.000045*hammer-.00016*pits
        roughness=.49+.11*cloud+.16*rust+.12*pits;ao=1-.15*pits
    elif family == 'brick':
        # Period hearth pavers: 248 x 118 mm fired-clay faces with 12 mm lime
        # mortar on a 260 x 130 mm staggered module, eight courses per tile.
        row=np.floor(y*8);column=np.floor(x*4+(row%2)*.5)%4
        bx=(x*4+(row%2)*.5)%1;by=(y*8)%1
        edge=np.minimum(np.minimum(bx,1-bx)*.26,np.minimum(by,1-by)*.13)
        mortar=np.exp(-(edge/.006)**6)
        bevel=np.exp(-(edge/.011)**2)
        fired=(np.sin(row*92.928+column*57.23)*43758.5453)%1-.5
        pores=np.maximum(0,np.sin(TAU*(211*x+2*np.sin(TAU*29*y)))*np.sin(TAU*193*y))**6
        clay=np.array((.47,.235,.135),np.float32)[None,None,:]
        clay=clay+(.09*fired+.026*cloud-.020*pores-.018*bevel)[:,:,None]*np.array((1.,.75,.50),np.float32)
        lime=np.array((.43,.415,.37),np.float32)[None,None,:]+(.018*cloud)[:,:,None]
        color=clay*(1-mortar[:,:,None])+lime*mortar[:,:,None]
        height=.00008*cloud-.00009*pores-.0035*mortar-.00035*bevel
        roughness=.86+.035*cloud+.025*mortar+.018*pores;ao=1-.23*mortar-.035*bevel
    elif family == 'glass':
        # Old blown glass has slight waviness and salt marks, not mirror chrome.
        color=np.array((.19,.28,.255),np.float32)[None,None,:]+(.013*cloud)[:,:,None]
        height=.000003*cloud;roughness=.14+.045*(cloud+.5);ao=np.ones_like(cloud)
    elif family == 'leather':
        pores=(np.sin(TAU*(167*x+3*np.sin(TAU*31*y)))*np.sin(TAU*173*y))**4
        creases=np.maximum(0,np.sin(TAU*(11*x+8*y)+.7*np.sin(TAU*5*y)))**18
        tone=.023*cloud-.025*pores-.06*creases
        color=np.array((.27,.135,.065),np.float32)[None,None,:]+tone[:,:,None]
        height=-.000075*pores-.0001*creases;roughness=.69+.06*cloud+.06*pores;ao=1-.10*creases
    else:
        fibres=.6*np.sin(TAU*(227*x+193*y))+.4*np.sin(TAU*(107*x-149*y))
        color=np.array((.78,.71,.53),np.float32)[None,None,:]+(.017*cloud+.006*fibres)[:,:,None]
        height=.000012*fibres+.000018*cloud;roughness=.91+.025*cloud;ao=np.ones_like(cloud)
    return np.clip(color,0,1),height.astype(np.float32),np.clip(roughness,.08,.98),np.clip(ao,.4,1)


def atlases(cache_dir):
    cache=Path(cache_dir).resolve();cache.mkdir(parents=True,exist_ok=True)
    manifest=cache/'provenance.json'
    metadata={}
    if manifest.exists():
        current=json.loads(manifest.read_text())
        # v5.6 appends only the hearth brick family; all v5.5 recipes are
        # byte-identical and their already-baked source images are immutable.
        if current.get('version') in (VERSION,'potc-pbr-v5.5'):metadata=current.get('images',{})
    expected=[family+'_'+kind+'.png' for family in FAMILIES for kind in ('color','normal','orm')]
    if all(name in metadata and (cache/name).exists() for name in expected):return cache
    for family,(w,h,tu,tv) in FAMILIES.items():
        family_names=[family+'_'+kind+'.png' for kind in ('color','normal','orm')]
        if all(name in metadata and (cache/name).exists() for name in family_names):continue
        print('V5_PBR_ATLAS',family,w,h,flush=True)
        x=(np.arange(w,dtype=np.float32)[None,:]+.5)/w
        y=(np.arange(h,dtype=np.float32)[:,None]+.5)/h
        color,height,roughness,ao=_surface(family,x,y,tu,tv)
        paths={kind:cache/(family+'_'+kind+'.png') for kind in ('color','normal','orm')}
        metadata[paths['color'].name]=_save(paths['color'],color);del color;gc.collect()
        height=np.broadcast_to(height,(h,w)).astype(np.float32)
        gx=(np.roll(height,-1,axis=1)-np.roll(height,1,axis=1))/(2*tu/w)
        gy=(np.roll(height,-1,axis=0)-np.roll(height,1,axis=0))/(2*tv/h)
        length=np.sqrt(gx*gx+gy*gy+1)
        normal=np.stack((-gx/length,gy/length,1/length),axis=2)
        metadata[paths['normal'].name]=_save(paths['normal'],normal*.5+.5)
        del normal,height,gx,gy,length;gc.collect()
        orm=np.empty((h,w,3),np.float32);orm[:,:,0]=ao;orm[:,:,1]=roughness
        # Corroded iron varies in roughness while retaining its metallic core.
        orm[:,:,2]=1. if family in ('iron','brass') else 0.
        metadata[paths['orm'].name]=_save(paths['orm'],orm)
        del orm,roughness,ao,x,y;gc.collect()
        for path in paths.values():metadata[path.name]['dimensions']=[w,h]
    provenance={'version':VERSION,'license':'project-authored procedural imagery; no external textures',
        'method':'baked metric wood fibres, knots, staggered butt caulking, paired trunnels, edge wear; sewn linen panels; twisted rope fibres; iron patina; fired-clay hearth pavers and lime mortar; tangent normals from metric height',
        'atlas_m':{key:list(value[2:]) for key,value in FAMILIES.items()},'images':metadata,
        'reference_floor':'Accepted detailed Bryg Mewa PR3: full 8192x2048 deck and hull PBR atlas resolution retained; old helper/cache unmodified',
        'palette_rule':'Only paint_hull and paint_trim multiplier factors change. Natural images, shader factors, and UV coordinates remain identical.'}
    manifest.write_text(json.dumps(provenance,indent=2)+'\n')
    return cache


def _occlusion_group():
    group=bpy.data.node_groups.get('glTF Material Output')
    if group:return group
    group=bpy.data.node_groups.new('glTF Material Output','ShaderNodeTree')
    group.interface.new_socket(name='Occlusion',in_out='INPUT',socket_type='NodeSocketFloat')
    return group


def _material(role, cache):
    family,tint,metallic=ROLES[role]
    material=bpy.data.materials.new(NAMES[role]);material.use_nodes=True
    nodes=material.node_tree.nodes;nodes.clear();links=material.node_tree.links
    output=nodes.new('ShaderNodeOutputMaterial');output.location=(620,100)
    bs=nodes.new('ShaderNodeBsdfPrincipled');bs.location=(350,100)
    links.new(bs.outputs['BSDF'],output.inputs['Surface'])
    col=nodes.new('ShaderNodeTexImage');col.name='baked_basecolor';col.location=(-620,300)
    col.image=bpy.data.images.load(str(cache/(family+'_color.png')),check_existing=True)
    col.image.colorspace_settings.name='sRGB';col.extension='REPEAT'
    mix=nodes.new('ShaderNodeMix');mix.data_type='RGBA';mix.name='palette_multiplier' if role.startswith('paint') else 'fixed_natural_multiplier'
    mix.blend_type='MULTIPLY';mix.inputs['Factor'].default_value=1.;mix.inputs[7].default_value=(*tint,1.)
    mix.location=(-270,300);links.new(col.outputs['Color'],mix.inputs[6]);links.new(mix.outputs[2],bs.inputs['Base Color'])
    nrm=nodes.new('ShaderNodeTexImage');nrm.name='baked_tangent_normal';nrm.location=(-620,0)
    nrm.image=bpy.data.images.load(str(cache/(family+'_normal.png')),check_existing=True)
    nrm.image.colorspace_settings.name='Non-Color';nrm.extension='REPEAT'
    normal=nodes.new('ShaderNodeNormalMap');normal.location=(40,-30)
    links.new(nrm.outputs['Color'],normal.inputs['Color']);links.new(normal.outputs['Normal'],bs.inputs['Normal'])
    orm=nodes.new('ShaderNodeTexImage');orm.name='baked_occlusion_roughness_metallic';orm.location=(-620,-300)
    orm.image=bpy.data.images.load(str(cache/(family+'_orm.png')),check_existing=True)
    orm.image.colorspace_settings.name='Non-Color';orm.extension='REPEAT'
    # The micro-occlusion atlas uses an explicit second coordinate channel.
    # It shares the authored metric layout of the surface maps, rather than
    # claiming a unique scene-lighting bake or depending on the active UV map.
    ao_uv=nodes.new('ShaderNodeUVMap');ao_uv.uv_map='DetailAO';ao_uv.location=(-850,-300)
    links.new(ao_uv.outputs['UV'],orm.inputs['Vector'])
    channels=nodes.new('ShaderNodeSeparateColor');channels.location=(-270,-300)
    links.new(orm.outputs['Color'],channels.inputs['Color']);links.new(channels.outputs['Green'],bs.inputs['Roughness'])
    links.new(channels.outputs['Blue'],bs.inputs['Metallic'])
    occlusion=nodes.new('ShaderNodeGroup');occlusion.node_tree=_occlusion_group();occlusion.location=(40,-300)
    links.new(channels.outputs['Red'],occlusion.inputs['Occlusion'])
    bs.inputs['Metallic'].default_value=metallic
    if role=='glass':
        bs.inputs['Transmission Weight'].default_value=.55;bs.inputs['IOR'].default_value=1.47
        # Transmission extension keeps the coloured glass physically readable.
    material.use_backface_culling=role!='canvas'
    material.diffuse_color=(*tint,1.)
    material['guide_pbr_v5']=True;material['material_role']=role;material['texture_family']=family
    material['uv_tile_m']=list(FAMILIES[family][2:]);material['baked_pbr_channels']='basecolor, tangent normal, packed occlusion/roughness/metallic'
    if role in ('paintHull','paintTrim'):material['palette_slot']=role
    return material


def _axial_uv(obj, roles):
    """Continuous cylindrical UVs for actual tube rings, including tarred ropes."""
    raw=obj.get('rope_path_json')
    if not raw:return False
    try:points=json.loads(raw)['points']
    except (ValueError,KeyError,TypeError):return False
    from mathutils import Vector
    points=list(map(Vector,points));n=len(points)
    if n<2 or len(obj.data.vertices)%n:return False
    sides=len(obj.data.vertices)//n
    if sides<3:return False
    distances=[0.]
    for a,b in zip(points,points[1:]):distances.append(distances[-1]+(b-a).length)
    radii=[(obj.data.vertices[i*sides].co-points[i]).length for i in range(n)]
    cyclic=any(abs((obj.data.loops[poly.loop_start].vertex_index//sides)-(obj.data.loops[poly.loop_start+1].vertex_index//sides))>n/2 for poly in obj.data.polygons) if n>3 else False
    total=distances[-1]+((points[-1]-points[0]).length if cyclic else 0)
    uv=obj.data.uv_layers.active
    for poly in obj.data.polygons:
        indices=[obj.data.loops[li].vertex_index for li in poly.loop_indices]
        rings=[vi//sides for vi in indices]
        if len(set(rings))==1:continue
        js=[vi%sides for vi in indices];wrap=max(js)-min(js)>sides/2
        seam=cyclic and max(rings)-min(rings)>n/2
        role=roles[min(poly.material_index,len(roles)-1)]
        rope=role in ('rope','ropeTar')
        for li in poly.loop_indices:
            ring,j=divmod(obj.data.loops[li].vertex_index,sides)
            if wrap and j==0:j=sides
            distance=total if seam and ring==0 else distances[ring]
            if rope:
                uv.data[li].uv=(distance/max(3.3*2*radii[ring],.003),j/sides)
            else:
                tile=FAMILIES[ROLES.get(role,ROLES['wood'])[0]][2:]
                uv.data[li].uv=(distance/tile[0],TAU*radii[ring]*j/sides/tile[1])
    obj['uv_method']='continuous physical axial/circumference mapping; rope repeat 3.3 diameters' if any(r in ('rope','ropeTar') for r in roles) else 'continuous metric axial/circumference timber UV'
    return True


def upgrade_scene(objects, cache_dir, materials=None, old_tiles=None):
    cache=atlases(cache_dir)
    source_roles={material.as_pointer():role for role,material in (materials or {}).items() if role in ROLES}
    replacements={};ledger=[];by_role={}
    for obj in objects:
        if obj.type!='MESH' or obj.get('asset_role')=='collision':continue
        for old in obj.data.materials:
            if old is None or old.get('guide_pbr_v5') or old.as_pointer() in replacements:continue
            role=source_roles.get(old.as_pointer(),old.get('material_role'))
            if role not in ROLES:continue
            if role not in by_role:by_role[role]=_material(role,cache)
            new=by_role[role];replacements[old.as_pointer()]=(new,role)
            family=ROLES[role][0]
            ledger.append({'source':old.name,'material':new.name,'role':role,'family':family,
                'old_uv_tile_m':list((old_tiles or {}).get(old.name,old.get('uv_tile_m',[2.,2.]))),
                'uv_tile_m':list(FAMILIES[family][2:]),'image_px':list(FAMILIES[family][:2]),
                'images':[family+'_'+suffix+'.png' for suffix in ('color','normal','orm')],
                'metallic':int(ROLES[role][2]),'palette_slot':role if role in ('paintHull','paintTrim') else None})
    seen=set()
    for obj in objects:
        if obj.type!='MESH' or obj.get('asset_role')=='collision' or obj.data.as_pointer() in seen:continue
        seen.add(obj.data.as_pointer());roles=[]
        for index,old in enumerate(list(obj.data.materials)):
            pair=replacements.get(old.as_pointer()) if old else None
            if not pair:
                roles.append(old.get('material_role','unknown') if old else 'unknown');continue
            new,role=pair;roles.append(role)
            old_tile=(old_tiles or {}).get(old.name,old.get('uv_tile_m',[2.,2.]))
            new_tile=FAMILIES[ROLES[role][0]][2:]
            if obj.data.uv_layers.active:
                for poly in obj.data.polygons:
                    if poly.material_index!=index:continue
                    for li in poly.loop_indices:
                        obj.data.uv_layers.active.data[li].uv.x*=old_tile[0]/new_tile[0]
                        obj.data.uv_layers.active.data[li].uv.y*=old_tile[1]/new_tile[1]
            obj.data.materials[index]=new
        _axial_uv(obj,roles)
        surface_uv=obj.data.uv_layers.active
        if surface_uv:
            # Boolean cutters can leave earlier charts behind. Preserve the
            # final authored active layout as UV0 and discard only unused
            # charts, so the explicit AO layout is consistently TEXCOORD_1.
            for unused_uv in list(obj.data.uv_layers):
                if unused_uv!=surface_uv:obj.data.uv_layers.remove(unused_uv)
            ao_uv=obj.data.uv_layers.new(name='DetailAO')
            # Keep UV0 active for base colour, normal and frozen density checks.
            for source_loop,ao_loop in zip(surface_uv.data,ao_uv.data):
                ao_loop.uv=source_loop.uv
            obj.data.uv_layers.active=surface_uv
            obj['occlusion_uv']='DetailAO: metric micro-occlusion; not scene-baked lighting'
        obj['material_roles_json']=json.dumps(roles)
    if materials:
        for role,new in by_role.items():materials[role]=new
    for material in by_role.values():
        for node in material.node_tree.nodes:
            if node.type=='TEX_IMAGE' and node.image and not node.image.packed_file:node.image.pack()
    return {'method':'v5 directly exportable full-resolution authored PBR','materials':ledger,
            'provenance':json.loads((cache/'provenance.json').read_text())}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--generate',required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    atlases(args.generate)
