"""Build the full documented reference construction with a traced vessel profile.

Uses the repository's original blender/ modules, not common/build.py.
Blender: --python rebuild_reference.py -- brig/spec.json --out build/guide-brig
This stage produces the construction scene; interiors and export audits follow.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import types

import bpy
import numpy as np


def save_rgb(array, path):
    """Use Blender's image writer when Pillow is absent from its Python runtime."""
    height, width = array.shape[:2]
    pixels = np.ones((height, width, 4), dtype=np.float32)
    pixels[:, :, :3] = np.asarray(array, dtype=np.float32) / 255
    # Array rows use image coordinates; Blender's image rows start at the bottom.
    pixels = np.flipud(pixels).copy()
    im = bpy.data.images.new('_texture_writer', width, height, alpha=False)
    im.colorspace_settings.name = 'Non-Color'
    im.pixels.foreach_set(pixels.ravel())
    im.filepath_raw = str(path)
    im.file_format = 'JPEG'
    im.save()
    bpy.data.images.remove(im)


class ArrayImage:
    def __init__(self, array):
        self.array = array

    def save(self, path, **kwargs):
        save_rgb(self.array, path)


def textures(source, output):
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        pil = types.ModuleType('PIL')
        pil.Image = types.SimpleNamespace(fromarray=lambda array, *args: ArrayImage(array))
        sys.modules['PIL'] = pil
    ns = {'__file__': str(source/'tekstury.py'), '__name__': 'reference_textures'}
    exec((source/'tekstury.py').read_text(encoding='utf-8'), ns)
    output.mkdir(parents=True, exist_ok=True)
    for name, fn in ns['ALL'].items():
        if (output/(name+'_kolor.jpg')).exists():
            continue
        print('REFERENCE TEXTURE', name, flush=True)
        fn(512 if name == 'okno' else 2048, str(output))


def configure(pr, spec):
    """Chapter 12: hull lines first, then spars, rope diameters and deck layout."""
    length, beam, draft = (spec[k] for k in ('length', 'beam', 'draft'))
    sl, sb = length/28.0, beam/7.6
    original = copy.deepcopy(pr.KADLUB)
    # Draft includes the keel, at the dead flat; source ref is 3.16 m here.
    ref_draft = -(original['ZK0'] + original['ZK_SPADEK']*1.96-original['STEPKA_WYS'])
    sz = draft/ref_draft
    # Preserve the depth/breadth family in ch. 01 while retaining game breadth.
    desired_deck = 0.42*beam - draft
    deck_extra = desired_deck - 0.90*sz

    def zmap(z):
        return z*sz + deck_extra*max(0, min(1, z/0.9))

    k = pr.KADLUB
    k['ZK0'] *= sz
    k['ZK_SPADEK'] *= sz/sl
    k['STEPKA_WYS'] *= sz
    for key in ['STEPKA_SZER','DZIOBNICA_GR','POSZYCIE_GR','NADBURCIE_GR',
                'RELING_SZER','RELING_GR','PILERS_ROZSTAW','RUFA_WYGIECIE']:
        k[key] *= sb
    for key in ['DZIOBNICA_SZER','TYLNICA_GR','PILERS','WODOSCIEK']:
        k[key] = tuple(v*sb for v in k[key])
    for key in ['DZIOB','RUFA','POKLAD_BOK']:
        k[key] = [(s*sl,zmap(z)) for s,z in k[key]]
    k['RUFA_SZER'] = [(zmap(z),x*sb) for z,x in k['RUFA_SZER']]
    for key in ['Z_PAWEZ_DOLNA','Z_NAWIS']:
        k[key] = zmap(k[key])
    k['TUCK_S0'] *= sl
    k['TUCK_RAKE'] = math.degrees(math.atan(math.tan(math.radians(k['TUCK_RAKE']))*sl/sz))
    k['POL_B'] *= sb
    k['WYPUKLOSC'] = beam*0.016
    k['POLPOKLAD_S'] *= sl
    k['POKLAD_GR'] *= sb
    # Keep the ordered waterline-to-wale rows monotone for low-freeboard
    # profiles. Original 0.74 m wale depth would fold below the paint line.
    wale_factor=min(1.0,(min(z for _,z in k['POKLAD_BOK'])-k['LINIA_WODNA_FARBA']-.10)/(.006+original['BERGHOLTY'][-1][1]))
    if wale_factor<=0:raise ValueError('Insufficient freeboard for structural wales')
    k['BERGHOLTY']=[(a*wale_factor,b*wale_factor,projection) for a,b,projection in original['BERGHOLTY']]
    k['RELING'] = [(s*sl,h) for s,h in k['RELING']]
    for key in ['FURTY_S','FURTY_ZAMKNIETE_S']:
        k[key] = [s*sl for s in k[key]]
    old_zk = original['ZK0']
    pr.RZEDNE_H = [zmap(old_zk+h)-zmap(old_zk) for h in pr.RZEDNE_H]
    pr.RZEDNE_S = [s*sl for s in pr.RZEDNE_S]
    pr.RZEDNE = [[None if x is None else x*sb for x in row] for row in pr.RZEDNE]
    # Recalculate, rather than stretch, every mast/yard from the guide's rules.
    old_mast = pr.DRZEWCA['GROT']
    pr.DRZEWCA.update(pr._drzewca(length,beam))
    d = pr.DRZEWCA
    d['FOK_S'] = length*(0.5-0.14)
    d['GROT_S'] = length*(0.5-0.55)
    d['SNOW_ODSTEP'] *= sb
    d['KILSON_NAD_WREBEM'] *= sb
    for key in pr.OLINOWANIE:
        if key.startswith('D_'):
            pr.OLINOWANIE[key] *= d['GROT']/old_mast
    # Keep fittings at full human scale, relocating their centres with the hull.
    def positions(value):
        if isinstance(value,dict):
            for key,v in value.items():
                if key in ['s','s0','s1'] and isinstance(v,(int,float)):
                    value[key] = v*sl
                elif key == 'x' and isinstance(v,(int,float)):
                    value[key] = v*sb
                else:
                    positions(v)
        elif isinstance(value,list):
            for v in value:
                positions(v)
    positions(pr.UKLAD)
    pr.UKLAD['KOLKOWNICE'] = [(a*sl,b*sl) for a,b in pr.UKLAD['KOLKOWNICE']]
    pr.UKLAD['DZIALKA_RELINGOWE'] = [s*sl for s in pr.UKLAD['DZIALKA_RELINGOWE']]
    pr.UKLAD['DZIALA']['bez_dziala'] = [-3.79*sl,8.46*sl]
    pr.UKLAD['LODZ']['stan'] = 'brak'
    # Label BRIG is from the game. The source's historical construction is snow.
    return {'method':'original reference generator, chapter 12 parameter chain',
            'length_m':length,'breadth_m':beam,'draft_at_dead_flat_m':draft,
            'main_mast_m':d['GROT'],'fore_mast_m':d['FOK'],
            'depth_breadth_target':0.42,'wale_vertical_offset_factor':wale_factor,
            'wale_basis':'Upper and lower wales retain reference protrusion; vertical offsets adapt to freeboard with 0.10 m waterline separation.','rig':'snow, c. 1710 reference',
            'confidence':'our inference adapting the reference model',
            'game_label':spec['label'],'reference_commit':'2e6f7e922e95396722376d42f3e2e0a12256029e'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('spec')
    parser.add_argument('--out', required=True)
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    spec_path = Path(args.spec).resolve()
    root = Path(__file__).resolve().parents[2]
    source = root/'blender'
    if not source.exists():
        source = root/'upstream'/'blender'
    output = Path(args.out).resolve()
    output.mkdir(parents=True,exist_ok=True)
    textures(source,output/'tekstury')
    sys.path.insert(0,str(source))
    ns = {'__file__':str(source/'buduj.py'),'__name__':'reference_builder'}
    code = (source/'buduj.py').read_text(encoding='utf-8')
    exec(code.rsplit('\nmain()',1)[0],ns)
    provenance = configure(ns['PR'],json.loads(spec_path.read_text(encoding='utf-8')))
    provenance['source_sha256'] = {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in sorted(source.glob('*.py'))}
    (output/'provenance.json').write_text(json.dumps(provenance,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    sys.argv = ['buduj.py','--','--out',str(output),'--rendery','none','--bez-ao']
    ns['main']()


if __name__ == '__main__':
    main()
