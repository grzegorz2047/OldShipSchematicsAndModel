"""Dependency-free CI dispatcher: strict v4 or explicit v5 applicability profile.

The separate v5 detail CI installs numpy/Pillow and recomputes actual interior
and image evidence. This base dispatcher retains all frozen v4 file/signature
checks and verifies the fixed v5 resource policy without extra dependencies.
"""
import argparse
import json
from pathlib import Path
import v4_integrity as V
import v5_contract as C


def dispatch(asset,root,v4_check=None,v5_check=None):
    spec=json.loads((Path(asset)/'spec.json').read_text())
    if spec.get('detail_schema')==5:
        return (v5_check or C.check)(asset,root)
    V.require('detail_schema' not in spec,'Unknown detail schema cannot fall back to v4')
    return (v4_check or V.check)(asset,root)


def self_test():
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder);asset=root/'asset';asset.mkdir()
        write=lambda value:(asset/'spec.json').write_text(json.dumps(value))
        calls=[]
        def old(a,r):calls.append('v4');return {'passed':True}
        def new(a,r):calls.append('v5');return {'passed':True}
        write({'schema':4});dispatch(asset,root,old,new)
        write({'schema':4,'detail_schema':5});dispatch(asset,root,old,new)
        V.require(calls==['v4','v5'],'Legacy/new dispatcher selected an incorrect verifier')
        write({'schema':4,'detail_schema':99})
        try:dispatch(asset,root,old,new)
        except ValueError:pass
        else:raise ValueError('Unknown detail schema silently fell back to old v4')
    return {'passed':True,'controls':['old v4 dispatched unchanged','explicit v5 dispatched to profile','unknown schema rejected']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--all',action='store_true');group.add_argument('--asset-dir',type=Path);group.add_argument('--self-test',action='store_true')
    parser.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parents[2]);args=parser.parse_args()
    if args.self_test:result=self_test()
    elif args.all:
        paths=sorted((args.source_root/'potc').glob('*/spec.json'));V.require(paths,'No PoTC assets found')
        result={'passed':True,'assets':[dispatch(path.parent,args.source_root) for path in paths]}
    else:result=dispatch(args.asset_dir,args.source_root)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
