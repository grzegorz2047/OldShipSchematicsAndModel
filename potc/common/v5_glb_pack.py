"""Lossless compaction of repeated embedded GLB buffer-view payloads.

Accessor metadata, node hierarchy, mesh primitives and embedded image bytes are
preserved. In particular, identical UV0/UV1 streams and shared PBR maps need only
one physical byte range. No vertex, normal, UV or image quantization is used.
"""
import hashlib
import json
from pathlib import Path
import struct


def compact(path):
    path=Path(path)
    original=path.read_bytes()
    if len(original)<12:raise ValueError('Truncated GLB header')
    magic,version,length=struct.unpack_from('<III',original)
    if (magic,version,length)!=(0x46546C67,2,len(original)):
        raise ValueError('Expected complete GLB version 2')
    chunks=[];cursor=12
    while cursor<len(original):
        if cursor+8>len(original):raise ValueError('Truncated GLB chunk header')
        size,kind=struct.unpack_from('<II',original,cursor);cursor+=8
        if size%4:raise ValueError('GLB chunks must be four-byte aligned')
        payload=original[cursor:cursor+size];cursor+=size
        if len(payload)!=size:raise ValueError('Truncated GLB chunk')
        chunks.append((kind,payload))
    if [kind for kind,_ in chunks]!=[0x4E4F534A,0x004E4942]:
        raise ValueError('Expected one JSON and one embedded binary GLB chunk')
    doc=json.loads(chunks[0][1]);binary=chunks[1][1]
    if len(doc.get('buffers',[]))!=1 or 'uri' in doc['buffers'][0]:
        raise ValueError('Expected one embedded buffer')
    logical_size=doc['buffers'][0].get('byteLength')
    if type(logical_size) is not int or not 0<logical_size<=len(binary) or len(binary)-logical_size>3:
        raise ValueError('Invalid embedded buffer length')
    if not doc.get('bufferViews'):
        return {'before_bytes':len(original),'after_bytes':len(original),'reused_views':0}
    # Compressed-view extensions can carry their own absolute buffer offsets.
    # This packer deliberately supports standard uncompressed Blender output.
    if (doc['buffers'][0].get('extensions') or
            'EXT_meshopt_compression' in doc.get('extensionsUsed',[]) or
            any(view.get('extensions') for view in doc.get('bufferViews',[]))):
        raise ValueError('Extended/compressed buffer views require their own packer')
    packed=bytearray();seen={};reused=0;avoided=0
    for view in doc.get('bufferViews',[]):
        if view.get('buffer',0)!=0:raise ValueError('External buffer view')
        start=view.get('byteOffset',0);size=view['byteLength']
        if type(start) is not int or type(size) is not int or start<0 or size<=0 or start+size>logical_size:
            raise ValueError('Invalid buffer view range')
        payload=binary[start:start+size]
        if start<0 or len(payload)!=size:raise ValueError('Invalid buffer view')
        metadata={k:v for k,v in view.items() if k not in ('byteOffset','buffer')}
        key=(json.dumps(metadata,sort_keys=True,separators=(',',':')),
             hashlib.sha256(payload).digest())
        offset=seen.get(key)
        # Compare bytes as well as hashes; equality is the entire criterion.
        if offset is not None and packed[offset:offset+size]==payload:
            reused+=1;avoided+=size
        else:
            packed.extend(b'\0'*((-len(packed))%4))
            offset=len(packed);packed.extend(payload);seen[key]=offset
        view['byteOffset']=offset
    doc['buffers'][0]['byteLength']=len(packed)
    encoded=json.dumps(doc,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    encoded+=b' '*((-len(encoded))%4);packed.extend(b'\0'*((-len(packed))%4))
    total=12+8+len(encoded)+8+len(packed)
    result=(struct.pack('<III',0x46546C67,2,total)+
            struct.pack('<II',len(encoded),0x4E4F534A)+encoded+
            struct.pack('<II',len(packed),0x004E4942)+packed)
    if len(result)>len(original):
        return {'before_bytes':len(original),'after_bytes':len(original),'reused_views':0}
    temporary=path.with_name(path.name+'.packing')
    temporary.write_bytes(result);temporary.replace(path)
    return {'before_bytes':len(original),'after_bytes':len(result),
            'reused_views':reused,'duplicate_payload_bytes':avoided}
