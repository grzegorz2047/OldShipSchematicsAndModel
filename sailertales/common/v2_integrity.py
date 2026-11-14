"""Portable integrity checks for the actual shipped vessel package (standard Python).

This checks a SHA-bound v2 report, not historical accuracy or navigation physics.
Usage: python v2_integrity.py --asset-dir <folder> --source-root <repository>
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import struct
from pathlib import Path


COMPONENTS = {5120: ('b', 1), 5121: ('B', 1), 5122: ('h', 2),
              5123: ('H', 2), 5125: ('I', 4), 5126: ('f', 4)}
WIDTH = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4,
         'MAT2': 4, 'MAT3': 9, 'MAT4': 16}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def resolve_source(root,relative):
    root=Path(root).resolve()
    relative=Path(relative)
    direct=(root/relative).resolve()
    if not direct.is_relative_to(root):
        raise ValueError('Source fingerprint escapes repository root')
    if direct.is_file():return direct
    if relative.parts and relative.parts[0]=='blender':
        fallback=(root/'upstream'/relative).resolve()
        if fallback.is_relative_to(root) and fallback.is_file():return fallback
    return direct


def read_glb(path):
    raw = Path(path).read_bytes()
    if len(raw) < 20:
        raise ValueError('GLB is too short')
    magic, version, declared = struct.unpack_from('<4sII', raw)
    if magic != b'glTF' or version != 2 or declared != len(raw):
        raise ValueError('Invalid GLB magic, version or byte length')
    at, document, binary = 12, None, b''
    while at < len(raw):
        if at + 8 > len(raw):
            raise ValueError('Truncated GLB chunk header')
        size, kind = struct.unpack_from('<I4s', raw, at)
        at += 8
        if size % 4 or at + size > len(raw):
            raise ValueError('Invalid GLB chunk size')
        data = raw[at:at+size]
        at += size
        if kind == b'JSON':
            if document is not None:
                raise ValueError('Duplicate JSON chunk')
            document = json.loads(data.rstrip(b' \0').decode('utf-8'))
        elif kind == b'BIN\0':
            if binary:
                raise ValueError('Duplicate BIN chunk')
            binary = data
    if document is None or document.get('asset', {}).get('version') != '2.0':
        raise ValueError('Missing glTF 2.0 JSON asset')
    return document, binary


def accessor_values(doc, binary, index):
    a = doc['accessors'][index]
    if a.get('sparse'):
        raise ValueError('Sparse accessor requires explicit audit support')
    if 'bufferView' not in a:
        return [(0,) * WIDTH[a['type']] for _ in range(a['count'])]
    v = doc['bufferViews'][a['bufferView']]
    fmt, size = COMPONENTS[a['componentType']]
    n = WIDTH[a['type']]
    start = v.get('byteOffset', 0) + a.get('byteOffset', 0)
    stride = v.get('byteStride', size*n)
    if stride < size*n:
        raise ValueError('Accessor stride smaller than element')
    end = start + max(0, a['count']-1)*stride + size*n
    view_end = v.get('byteOffset', 0) + v['byteLength']
    if start < v.get('byteOffset', 0) or end > view_end or end > len(binary):
        raise ValueError('Accessor runs beyond its buffer view')
    unpack = struct.Struct('<' + fmt*n).unpack_from
    result = [unpack(binary, start+i*stride) for i in range(a['count'])]
    if a['componentType'] == 5126 and any(not math.isfinite(x) for v in result for x in v):
        raise ValueError('Non-finite accessor value')
    return result


def image_bytes(doc, binary, image):
    if 'bufferView' in image:
        v = doc['bufferViews'][image['bufferView']]
        start = v.get('byteOffset', 0)
        return binary[start:start+v['byteLength']]
    uri = image.get('uri', '')
    if uri.startswith('data:') and ';base64,' in uri:
        return base64.b64decode(uri.split(',', 1)[1], validate=True)
    raise ValueError('Image resource is external or missing')


def image_size(raw):
    if raw.startswith(b'\x89PNG\r\n\x1a\n') and len(raw) >= 24:
        return struct.unpack_from('>II', raw, 16)
    if raw.startswith(b'\xff\xd8'):
        i = 2
        while i+3 < len(raw):
            if raw[i] != 255:
                i += 1
                continue
            while i < len(raw) and raw[i] == 255:
                i += 1
            marker = raw[i]
            i += 1
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                continue
            size = struct.unpack_from('>H', raw, i)[0]
            if marker in (0xC0,0xC1,0xC2,0xC3,0xC5,0xC6,0xC7,0xC9,0xCA,0xCB,0xCD,0xCE,0xCF):
                h,w = struct.unpack_from('>HH', raw, i+3)
                return w,h
            i += size
    raise ValueError('Unsupported or invalid embedded PNG/JPEG')


def inspect_glb(path):
    doc, binary = read_glb(path)
    errors = []
    for b in doc.get('buffers', []):
        if 'uri' in b and not b['uri'].startswith('data:'):
            errors.append('external buffer')
        if b.get('byteLength', 0) > len(binary):
            errors.append('buffer byteLength exceeds BIN chunk')
    for i,v in enumerate(doc.get('bufferViews', [])):
        if v.get('buffer', 0) != 0 or v.get('byteOffset', 0)+v['byteLength'] > len(binary):
            errors.append(f'bufferView {i} out of range')
    accessors = {}
    try:
        for i in range(len(doc.get('accessors', []))):
            accessors[i] = accessor_values(doc,binary,i)
    except (ValueError,KeyError,IndexError,struct.error) as e:
        errors.append(str(e))
    triangles = 0
    for mesh in doc.get('meshes', []):
        for p in mesh.get('primitives', []):
            try:
                pos = p['attributes']['POSITION']
                n = len(accessors[pos])
                for attr, index in p['attributes'].items():
                    if len(accessors[index]) != n:
                        errors.append('attribute count mismatch '+attr)
                if 'indices' in p:
                    indices = [v[0] for v in accessors[p['indices']]]
                    if indices and (min(indices)<0 or max(indices)>=n):
                        errors.append('index beyond POSITION count')
                    count = len(indices)
                else:
                    count = n
                if p.get('mode',4)==4:
                    if count%3:
                        errors.append('triangle index count not divisible by 3')
                    triangles += count//3
            except (KeyError,IndexError) as e:
                errors.append('invalid primitive reference '+str(e))
    images=[]
    for i,im in enumerate(doc.get('images', [])):
        try:
            raw=image_bytes(doc,binary,im);w,h=image_size(raw)
            images.append({'index':i,'name':im.get('name',str(i)),'width':w,'height':h,
                           'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
                           'power_of_two':bool(w and h and not w&(w-1) and not h&(h-1))})
        except (ValueError,KeyError,IndexError) as e:
            errors.append('image '+str(i)+': '+str(e))
    nodes=doc.get('nodes',[])
    for i,n in enumerate(nodes):
        for child in n.get('children',[]):
            if not 0<=child<len(nodes):
                errors.append(f'invalid child node {i}->{child}')
    return {'passed':not errors,'errors':errors,'bytes':Path(path).stat().st_size,
            'triangles':triangles,'nodes':len(nodes),'meshes':len(doc.get('meshes',[])),
            'materials':len(doc.get('materials',[])),'images':images},doc,binary


def check_report(asset_dir,source_root=None):
    asset_dir=Path(asset_dir).resolve()
    report=json.loads((asset_dir/'validation.json').read_text(encoding='utf-8'))
    if report.get('schema',0)<2 or not report.get('passed'):
        raise ValueError('Missing v2 passing acceptance report')
    required={'model/ship.glb','model/collision.glb','model/ship.blend',
              'model/ship_lod1.glb','model/ship_lod2.glb',
              'navigation.json','design.json','spec.json','export-review.json',
              'previews/hero.png','previews/deck.png'}
    if not required.issubset(report.get('sha256',{})):
        raise ValueError('Incomplete asset fingerprint manifest')
    for rel,expected in report['sha256'].items():
        f=(asset_dir/rel).resolve()
        if not f.is_relative_to(asset_dir):
            raise ValueError('Asset fingerprint escapes package root')
        if not f.is_file() or digest(f)!=expected:
            raise ValueError('Missing or stale asset: '+rel)
    if source_root is not None:
        source_root=Path(source_root).resolve()
        for rel,expected in report.get('source_sha256',{}).items():
            f=resolve_source(source_root,rel)
            if not f.is_file() or digest(f)!=expected:
                raise ValueError('Missing or stale source: '+rel)
    matrix=report.get('matrix',[])
    if not matrix or any(c.get('required') and c.get('status')!='PASS' for c in matrix):
        raise ValueError('Required checklist item is not PASS')
    review=json.loads((asset_dir/'export-review.json').read_text(encoding='utf-8'))
    if not review.get('passed') or not review.get('triangle_match'):
        raise ValueError('Source/export render comparison did not pass')
    if review.get('source_triangles') != review.get('export_triangles'):
        raise ValueError('Source/export triangle counts differ')
    for rel in ('model/ship.glb','model/ship.blend'):
        if review.get('sha256',{}).get(rel) != digest(asset_dir/rel):
            raise ValueError('Source/export render comparison is stale: '+rel)
    views=review.get('views',{})
    if not {'hero','deck'}.issubset(views):
        raise ValueError('Missing canonical source/export views')
    for name,view in views.items():
        brightness=view.get('brightness_fraction',math.inf)
        channels=view.get('maximum_channel_share_difference',math.inf)
        if not view.get('passed') or not (0<=brightness<=.10 and 0<=channels<=.04):
            raise ValueError('Source/export render threshold failed: '+name)
        if 'previews/'+name+'.png' not in report['sha256']:
            raise ValueError('Unbound exported preview: '+name)
    return {'passed':True,'asset_files':len(report['sha256']),
            'source_files':len(report.get('source_sha256',{})),
            'required_checks':sum(bool(c.get('required')) for c in matrix)}


def main():
    p=argparse.ArgumentParser();p.add_argument('--asset-dir',required=True)
    p.add_argument('--source-root')
    a=p.parse_args()
    print(json.dumps(check_report(a.asset_dir,a.source_root),indent=2))


if __name__=='__main__':
    main()
