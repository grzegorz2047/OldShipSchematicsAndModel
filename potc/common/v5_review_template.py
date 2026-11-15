"""Create a pending manual review bound to current actual GLB render evidence.

Run after v5_review.py. This never writes PASS or invents observations. Inspect
the images, add at least two concrete findings per view, and only then change
decision to PASS. A stale review can be explicitly reset with --replace-stale.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import v5_contract as C


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def safe(asset,relative):
    path=PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or '\\' in relative or ':' in relative:
        raise ValueError('Review evidence path must stay inside its asset')
    result=(asset/relative).resolve()
    if not result.is_relative_to(asset):raise ValueError('Review evidence symlink leaves its asset')
    return result


def create(asset,reviewer,replace_stale=False):
    asset=Path(asset).resolve()
    manifest=json.loads((asset/'detail-render.json').read_text())
    if manifest.get('schema')!=5 or manifest.get('model_sha256')!=digest(safe(asset,manifest['model_path'])):
        raise ValueError('Render evidence is stale: regenerate actual GLB detail views first')
    if manifest.get('renderer_sha256')!=digest(Path(__file__).with_name('v5_review.py')):
        raise ValueError('Renderer changed: regenerate evidence with the frozen current renderer')
    output=asset/'detail-review.json'
    if output.exists():
        previous=json.loads(output.read_text())
        stale=previous.get('model_sha256')!=manifest['model_sha256'] or previous.get('renderer_sha256')!=manifest['renderer_sha256']
        rendered={view['path']:view['sha256'] for view in manifest.get('views',[])}
        stale=stale or any(rendered.get(view.get('path'))!=view.get('sha256') for view in previous.get('views',[]))
        if not replace_stale or not stale:
            raise ValueError('Existing review preserved; --replace-stale only resets evidence from another model, renderer or image set')
    views=[]
    for view in manifest.get('views',[]):
        if view.get('category') not in {'deck','interior','hull_rig'}:
            raise ValueError('Unknown render evidence category')
        if view['sha256']!=digest(safe(asset,view['path'])):
            raise ValueError('Render image bytes changed after the manifest was written')
        entry={'category':view['category'],'path':view['path'],'sha256':view['sha256'],
               'name':view.get('name'),'findings':[]}
        for key in ('label','room_id','room_kind','scope','hidden_nodes','actual_hidden_nodes'):
            if key in view:entry[key]=view[key]
        views.append(entry)
    if {view['category'] for view in views}!={'deck','interior','hull_rig'}:
        raise ValueError('Full hull/rig, deck and intact interior evidence is required')
    design=json.loads((asset/'design.json').read_text())
    required_batteries=C.reviewed_gun_decks(design.get('detail_contract',{}),views,
                                           {view['path']:view for view in manifest.get('views',[])})
    review={'schema':5,'reference':'Bryg Mewa PR 3','decision':'PENDING','reviewer':reviewer,
            'model_path':manifest['model_path'],'model_sha256':manifest['model_sha256'],
            'renderer_sha256':manifest['renderer_sha256'],'views':views,
            'required_intact_gun_decks':required_batteries,
            'limitations':['Static geometry and PBR inspection only; gameplay controllers and historical exactness are not certified.'],
            'instructions':'Inspect every listed actual image and the matched old Brig reference views. Add at least two concrete observations per view. Set decision PASS only after inspection. A cutaway remains supplementary to the separate intact interior view.'}
    output.write_text(json.dumps(review,indent=2)+'\n')
    return {'path':str(output),'decision':'PENDING','views':len(views),'automatic_PASS':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--asset-dir',type=Path,required=True)
    parser.add_argument('--reviewer',required=True)
    parser.add_argument('--replace-stale',action='store_true')
    args=parser.parse_args()
    print(json.dumps(create(args.asset_dir,args.reviewer,args.replace_stale),indent=2))


if __name__=='__main__':main()
