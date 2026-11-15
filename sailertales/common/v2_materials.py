"""Guide-sized procedural PBR atlases and consistent material/UV upgrade.

These are authored procedural textures, not third-party photographic CC0 maps.
Physical atlas dimensions follow parametry.DESKI (guide chapters 03,04,08,13).
Run once with Blender: --python v2_materials.py -- --generate CACHE_DIRECTORY
Call upgrade_scene(objects, cache_dir, old_tiles=None) before packing/export.
"""
import argparse
import gc
import json
import math
from pathlib import Path
import sys

import bpy
import numpy as np

PALETTE = {
    'poklad': (0.62,0.575,0.50), 'burta_drewno':(0.46,0.33,0.22),
    'drewno':(0.62,0.46,0.30), 'drewno_ciemne':(0.40,0.28,0.17),
    'drewno_czarne':(0.23,0.215,0.19), 'laweta':(0.40,0.15,0.09),
    'farba_czarna':(0.20,0.19,0.18), 'farba_czarna_gladka':(0.23,0.22,0.21),
    'farba_ochra':(0.68,0.52,0.27), 'farba_czerwona':(0.55,0.17,0.10),
    'farba_niebieska':(0.16,0.23,0.36), 'farba_dno_biala':(0.84,0.81,0.73),
    'farba_dno_czerwona':(0.42,0.18,0.12), 'rzezby_zlote':(0.82,0.63,0.30),
    'zelazo':(0.19,0.18,0.17), 'zelazo_lufa':(0.19,0.18,0.17),
    'braz':(0.62,0.42,0.20), 'lina_smolowana':(0.23,0.21,0.18),
    'lina_jasna':(0.64,0.57,0.43), 'plotno':(0.84,0.80,0.70),
    'szklo':(0.18,0.23,0.25),
}
ALIASES = {
 'deck_planking':'poklad','deck_pine':'poklad','side_oiled_oak':'burta_drewno',
 'wood':'drewno','wood_dark':'drewno_ciemne','wood_black':'drewno_czarne',
 'carriage_red_ochre':'laweta','paint_black':'farba_czarna',
 'paint_black_smooth':'farba_czarna_gladka','paint_ochre':'farba_ochra',
 'paint_red':'farba_czerwona','paint_blue':'farba_niebieska',
 'bottom_white_stuff':'farba_dno_biala','bottom_red_brown':'farba_dno_czerwona',
 'carvings_yellow_ochre':'rzezby_zlote','iron':'zelazo','iron_gun_barrel':'zelazo_lufa',
 'bronze':'braz','rope_tarred':'lina_smolowana','rope_untarred':'lina_jasna',
 'canvas':'plotno','glass':'szklo',
}
TILES = {'deck':(3.52,.88),'hull':(4.4,1.1),'paint':(4.4,1.1),
         'wood':(2.,2.),'iron':(1.,1.),'rope':(1.,1.),'canvas':(2.4,2.4)}
OLD_TILES = {k:((6.4,6.4) if k=='poklad' else (8.,8.) if k.startswith('farba_')
                  and k!='farba_czarna_gladka' or k=='burta_drewno' else
                  (2.4,2.4) if k=='plotno' else (1.,1.) if k.startswith('lina_') or
                  k in ('zelazo','zelazo_lufa','braz','szklo') else (2.,2.)) for k in PALETTE}


def linear(v):
    return v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4


def write_rgb(path, array):
    h,w = array.shape[:2]
    pix=np.ones((h,w,4),dtype=np.float32)
    pix[:,:,:3]=array
    pix=np.flipud(pix).copy()
    im=bpy.data.images.new('_v2_texture_writer',w,h,alpha=False)
    im.colorspace_settings.name='Non-Color'
    im.pixels.foreach_set(pix.ravel())
    im.filepath_raw=str(path);im.file_format='JPEG';im.save()
    bpy.data.images.remove(im)
    del pix


def atlases(cache):
    cache=Path(cache).resolve();cache.mkdir(parents=True,exist_ok=True)
    definitions=[('deck',8192,2048,3.52,.88,4),('hull',8192,2048,4.4,1.1,4),
                 ('paint',8192,2048,4.4,1.1,4),('wood',2048,2048,2.,2.,0),
                 ('iron',2048,2048,1.,1.,0),('canvas',2048,2048,2.4,2.4,0),
                 ('rope',1024,512,1.,1.,0)]
    for family,w,h,tu,tv,rows in definitions:
        files=[cache/(family+'_'+suffix+'.jpg') for suffix in ('color','normal','orm')]
        if all(f.exists() for f in files):
            continue
        print('PBR_ATLAS',family,w,h,flush=True)
        x=(np.arange(w,dtype=np.float32)[None,:]+.5)/w
        y=(np.arange(h,dtype=np.float32)[:,None]+.5)/h
        u=2*math.pi*x;v=2*math.pi*y
        warp=2*np.sin(u)+.6*np.sin(3*u)+.2*np.sin(11*u)
        fiber=np.sin(2*math.pi*(437*y+.4*warp))
        fiber+=.4*np.sin(2*math.pi*(719*y+.7*warp))
        cloud=.5*np.sin(u*7+np.sin(v*3))+.5*np.sin(u*13-np.cos(v*5))
        height=.00004*fiber+.00009*cloud
        tone=.895+.015*fiber+.018*cloud
        if rows:
            local=(y*rows)%1
            seam_dist=np.minimum(local,1-local)*(tv/rows)
            seam=np.exp(-np.square(seam_dist/.0035))
            height=height-.0014*seam
            tone=tone-.46*seam
            # Trunnels at frame/deck-beam spacing; diameter about 14 mm.
            pitch=.55 if family!='deck' else 1.1733333333
            dx=np.abs(((x*tu-.20*pitch+pitch/2)%pitch)-pitch/2)
            peg=np.zeros((h,w),np.float32)
            for fraction in (.27,.73):
                dy=np.abs(local-fraction)*(tv/rows)
                d=np.sqrt(dx*dx+dy*dy)
                peg=np.maximum(peg,np.exp(-np.power(d/.007,6)))
            height=height+.00018*peg
            tone=tone+.025*peg
            if family=='paint':
                tone=.78+.16*(tone-.40)/.55
                height*=.60
        if family=='canvas':
            stitch=np.exp(-np.square(np.minimum((x*4)%1,1-(x*4)%1)/.025))
            weave=.5*np.sin(2*math.pi*511*x)*np.sin(2*math.pi*509*y)
            height=.00015*stitch+.00004*weave+.00002*cloud
            tone=.9-.035*stitch+.012*cloud+.005*weave
        elif family=='rope':
            strand=np.cos(2*math.pi*(6*x+3*y))
            strand+=.2*np.cos(2*math.pi*(70*x-40*y))
            height=.0001*strand
            tone=.86+.055*strand
        elif family=='iron':
            pits=np.sin(211*u+2*np.sin(37*v))*np.sin(167*v)
            height=.000035*pits
            tone=.90+.025*cloud+.012*pits
        height=np.broadcast_to(height,(h,w)).astype(np.float32)
        tone=np.clip(np.broadcast_to(tone,(h,w)),.38,.97).astype(np.float32)
        color=np.repeat(tone[:,:,None],3,axis=2)
        write_rgb(files[0],color);del color,tone
        gx=(np.roll(height,-1,axis=1)-np.roll(height,1,axis=1))/(2*tu/w)
        gy=(np.roll(height,-1,axis=0)-np.roll(height,1,axis=0))/(2*tv/h)
        normal=np.stack((-gx,gy,np.ones_like(gx)),axis=2)
        normal/=np.linalg.norm(normal,axis=2,keepdims=True)
        write_rgb(files[1],normal*.5+.5);del normal,gx,gy,height
        rough=.83 if family=='canvas' else .78 if family=='rope' else .55 if family=='iron' else .66
        orm=np.zeros((h,w,3),np.float32);orm[:,:,0]=1
        orm[:,:,1]=np.clip(rough+.025*np.broadcast_to(cloud,(h,w)),.12,.95)
        orm[:,:,2]=1 if family=='iron' else 0
        write_rgb(files[2],orm);del orm
        gc.collect()
    (cache/'provenance.json').write_text(json.dumps({
       'license':'project-authored procedural textures; no external imagery',
       'basis':['docs/en/03-hull-construction.md','docs/en/04-decks-bulwarks-stern-head.md',
                'docs/en/08-ropes-blocks-and-sails.md','docs/en/13-3d-quality-checklist.md'],
       'atlas_m':TILES,'method':'continuous authored grain, physical seams/trunnels, normal from metric height derivatives',
       'palette_srgb':PALETTE},indent=2)+'\n',encoding='utf-8')
    return cache


def canonical(name):
    base=name.split('.')[0].lower()
    if base.startswith('v2_'):
        base=base[3:]
    return ALIASES.get(base,base)


def family_for(role):
    if role=='poklad':return 'deck'
    if role=='burta_drewno':return 'hull'
    if role.startswith('farba_') or role=='rzezby_zlote':return 'paint'
    if role.startswith('lina_'):return 'rope'
    if role=='plotno':return 'canvas'
    if role in ('zelazo','zelazo_lufa','braz'):return 'iron'
    return 'wood'


def upgrade_scene(objects=None, cache_dir=None, old_tiles=None):
    """Upgrade known original materials; unrecognized/alpha materials stay intact.

    UVs originating in original Siatka objects are normalized by source tile m;
    restore physical size by old_tile/new_tile. Set material['uv_tile_m'] on
    custom geometry, or pass old_tiles={material_name:(u_m,v_m)} explicitly.
    Returns an exact material/atlas ledger for design.json.
    """
    objects=list(objects) if objects is not None else list(bpy.context.scene.objects)
    if cache_dir is None:
        cache_dir=Path(__file__).resolve().parents[2]/'build'/'pbr-v2'
    cache=atlases(cache_dir)
    replacements={};scales={};ledger=[]
    for o in objects:
        if o.type!='MESH' or o.get('asset_role')=='collision' or o.name.lower().startswith('col_'):
            continue
        for old in o.data.materials:
            if old is None or old.get('guide_pbr_v2') or old.name in replacements:
                continue
            role=canonical(old.name)
            if role not in PALETTE or role=='szklo':
                continue
            family=family_for(role)
            new=bpy.data.materials.new('v2_'+role);new.use_nodes=True
            nt=new.node_tree;nt.nodes.clear()
            output=nt.nodes.new('ShaderNodeOutputMaterial')
            bs=nt.nodes.new('ShaderNodeBsdfPrincipled');nt.links.new(bs.outputs['BSDF'],output.inputs['Surface'])
            palette=PALETTE[role]
            col=nt.nodes.new('ShaderNodeTexImage');col.image=bpy.data.images.load(str(cache/(family+'_color.jpg')),check_existing=True)
            col.image.colorspace_settings.name='sRGB'
            mix=nt.nodes.new('ShaderNodeMix');mix.data_type='RGBA';mix.blend_type='MULTIPLY'
            mix.inputs['Factor'].default_value=1
            nt.links.new(col.outputs['Color'],mix.inputs[6])
            mix.inputs[7].default_value=(*[min(1,linear(c)/linear(.90)) for c in palette],1)
            nt.links.new(mix.outputs[2],bs.inputs['Base Color'])
            nrm=nt.nodes.new('ShaderNodeTexImage');nrm.image=bpy.data.images.load(str(cache/(family+'_normal.jpg')),check_existing=True)
            nrm.image.colorspace_settings.name='Non-Color'
            normal=nt.nodes.new('ShaderNodeNormalMap');nt.links.new(nrm.outputs['Color'],normal.inputs['Color']);nt.links.new(normal.outputs['Normal'],bs.inputs['Normal'])
            orm=nt.nodes.new('ShaderNodeTexImage');orm.image=bpy.data.images.load(str(cache/(family+'_orm.jpg')),check_existing=True)
            orm.image.colorspace_settings.name='Non-Color'
            channels=nt.nodes.new('ShaderNodeSeparateColor');nt.links.new(orm.outputs['Color'],channels.inputs['Color'])
            nt.links.new(channels.outputs['Green'],bs.inputs['Roughness'])
            bs.inputs['Metallic'].default_value=1. if family=='iron' else 0.
            new.use_backface_culling=role!='plotno'
            new.diffuse_color=(*[linear(c) for c in palette],1)
            new['guide_pbr_v2']=True;new['uv_tile_m']=TILES[family]
            new['source_material']=old.name;new['source_palette']='parametry.TEKSTURY_TD with documented authored adjustments'
            old_tile=(old_tiles or {}).get(old.name,old.get('uv_tile_m',OLD_TILES[role]))
            new_tile=TILES[family]
            # Rope UV already represents strand pitch and circumference.
            scales[old.name]=tuple(old_tile[i]/new_tile[i] for i in (0,1)) if family!='rope' else (1.,1.)
            replacements[old.name]=new
            ledger.append({'source':old.name,'material':new.name,'palette_srgb':palette,
                           'old_uv_tile_m':list(old_tile),'uv_tile_m':new_tile,
                           'image_px':list(col.image.size),'family':family,'metallic':int(family=='iron')})
    seen=set()
    for o in objects:
        if o.type!='MESH' or o.get('asset_role')=='collision' or o.name.lower().startswith('col_'):
            continue
        if o.data.as_pointer() in seen:
            continue
        seen.add(o.data.as_pointer())
        uv=o.data.uv_layers.active
        for i,old in enumerate(list(o.data.materials)):
            if old is None or old.name not in replacements:
                continue
            sx,sy=scales[old.name]
            if uv:
                for poly in o.data.polygons:
                    if poly.material_index==i:
                        for li in poly.loop_indices:
                            uv.data[li].uv.x*=sx;uv.data[li].uv.y*=sy
            o.data.materials[i]=replacements[old.name]
    for image in bpy.data.images:
        if image.source=='FILE' and not image.packed_file:
            try:image.pack()
            except RuntimeError:pass
    return {'method':'guide-sized authored PBR atlas upgrade','materials':ledger,
            'provenance':json.loads((cache/'provenance.json').read_text(encoding='utf-8'))}


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--generate',required=True)
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    atlases(args.generate)
