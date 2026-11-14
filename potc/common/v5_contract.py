"""Explicit v5 H1/H2 applicability bridge; every other frozen gate is retained.

This does not make a failing v4 asset pass v4. New detail_schema=5 releases keep
the original H1/H2 rows, their original evidence and legacy status, and visibly
mark them SUPERSEDED. A separate mandatory fixed v5 resource budget replaces
only these two resource limits. No geometry predicate/threshold is changed.
"""
from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import struct

import v4_integrity as V

HERE = Path(__file__).resolve().parent
PROFILE = 'v5-detailed-pbr-resource-profile'
SUPERSEDED = {'H1', 'H2'}
REASON = ('Superseded only for detail_schema=5 by the required fixed v5 package_budget gate; '
          'the original simple-model byte/triangle limit and measured legacy result are retained verbatim.')
DETAIL_GATES = {'research', 'feature_inventory', 'interior_geometry', 'portal_voids',
                'connected_access', 'window_voids', 'material_detail', 'visual_review',
                'negative_controls', 'package_budget'}
AUDIT_SOURCES = {'potc/common/v5_audit.py', 'potc/common/v5_integrity.py',
                 'potc/common/v5_benchmark.json', 'potc/common/v5_review.py',
                 'potc/common/v5_joint_index.py', 'potc/common/v5_contract.py',
                 'potc/common/v5_uv_metrics.py', 'potc/common/v5_glb_pack.py',
                 'potc/common/v5_review_template.py',
                 'potc/common/v5_dispatch.py', 'potc/common/v5_budget.json',
                 '.github/workflows/potc-detail-integrity.yml'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def reviewed_gun_decks(contract, views, rendered):
    """Bind each declared battery room to its own intact reviewed image."""
    required={room['id'] for room in contract.get('interiors',[]) if room.get('kind')=='gun_deck'}
    reviewed=set()
    for view in views:
        actual=rendered.get(view.get('path'),{})
        if (view.get('category')=='interior' and actual.get('category')=='interior'
                and actual.get('room_kind')=='gun_deck' and not actual.get('hidden_nodes')
                and not actual.get('actual_hidden_nodes')):
            reviewed.add(actual.get('room_id'))
    missing=sorted(required-reviewed)
    V.require(not missing,'Declared gun decks lack reviewed intact interior evidence: '+', '.join(missing))
    return sorted(required)


def supersede_resources(quality, records_present):
    result = dict(quality)
    result['matrix'] = [dict(row) for row in quality['matrix']]
    legacy = {}
    for row in result['matrix']:
        if row['id'] in SUPERSEDED:
            legacy[row['id']] = copy.deepcopy(row)
            row.update(required=False, status='SUPERSEDED', legacy_status=row['status'],
                       scope='superseded', reason=REASON)
    V.require(set(legacy) == SUPERSEDED, 'Both original measured H1/H2 rows are required')
    result['legacy_resource_rows'] = legacy
    result['validation_profile'] = PROFILE
    result['scope'] = ('Every frozen geometry/material/rig threshold is retained. '
                       'Only H1/H2 resource applicability is explicitly superseded by fixed reviewed v5 package_budget limits, '
                       'with original measurements retained. Distance LODs retain the original UV applicability rules.')
    # This is exactly frozen v4.quality's predicate, with only the two visibly
    # superseded resource rows no longer required. All other rows stay verbatim.
    full_grain = not result['full_detail_uv_targets'] or any(
        row['id']=='F4' and row['required'] and row['status']=='PASS' for row in result['matrix'])
    result['passed'] = (bool(records_present) and result['topology']['passed']
                        and not result['missing_uv_objects'] and full_grain
                        and all(row['status']=='PASS' for row in result['matrix'] if row['required']))
    return result


@contextmanager
def release_quality_profile(v4):
    original = v4.quality
    def quality(records, doc, structural, design, full_detail):
        return supersede_resources(original(records,doc,structural,design,full_detail),bool(records))
    v4.quality = quality
    try:
        yield
    finally:
        v4.quality = original


def quality_check(value, full_detail, label):
    """Frozen quality_check, with explicit and auditable H1/H2 supersession."""
    V.require(isinstance(value,dict) and value.get('passed') is True, label+': missing/failing quality audit')
    V.require(value.get('full_detail_uv_targets') is full_detail, label+': wrong full-detail UV applicability')
    V.require(value.get('missing_uv_objects') == [], label+': UVs are missing or evidence is absent')
    V.require(value.get('validation_profile') == PROFILE, label+': missing explicit v5 profile')
    rows = V.passing_matrix(value.get('matrix'),label+' quality')
    expected = V.QUALITY_IDS | ({'F1','F2','F3','F4'} if full_detail else set())
    V.require(set(rows)==expected,label+': incomplete/unexpected quality gate set')
    legacy = value.get('legacy_resource_rows',{})
    V.require(set(legacy)==SUPERSEDED,label+': original H1/H2 evidence must be retained')
    for identifier,row in rows.items():
        if identifier in SUPERSEDED:
            old = legacy[identifier]
            metric,limit_key,limit = ('bytes','budget_bytes',33554432) if identifier=='H1' else ('triangles','budget',280000)
            evidence = old.get('evidence',{})
            V.require(old.get('id')==identifier and old.get('required') is True and old.get('scope')=='measured'
                      and type(evidence.get(metric)) is int and evidence[metric]>0
                      and evidence.get(limit_key)==limit
                      and old.get('status')==('PASS' if evidence[metric]<=limit else 'FAIL'),
                      label+': original H1/H2 result/evidence was altered')
            wanted = {**old,'required':False,'status':'SUPERSEDED','legacy_status':old['status'],
                      'scope':'superseded','reason':REASON}
            V.require(row==wanted,label+': invalid/hidden resource supersession')
        elif identifier=='F8' and row.get('status')=='NA':
            V.require(row.get('required') is False and row.get('scope')=='not_applicable'
                      and isinstance(row.get('reason'),str) and row['reason'].strip(),
                      label+': AO applicability needs an explicit reason')
        else:
            V.require(row.get('required') is True and row.get('status')=='PASS',
                      label+': mandatory quality gate is not PASS: '+identifier)


def bind_legacy_rows(asset, report, spec):
    V.require(spec.get('detail_schema')==5 and report.get('detail_schema')==5
              and report.get('validation_profile')==PROFILE,'H1/H2 bridge requires an explicit v5 release')
    for path,row in report['glb_files'].items():
        if row.get('palette')!='ochre':
            continue
        quality_check(row['quality'],row['level']==0,path)
        legacy=row['quality']['legacy_resource_rows']
        V.require(legacy['H1']['evidence']['bytes']==(asset/path).stat().st_size
                  and legacy['H2']['evidence']['triangles']==row['structure']['triangles'],
                  'Legacy resource measurements are not bound to actual delivered geometry: '+path)


@contextmanager
def resource_contract():
    original=V.quality_check
    V.quality_check=quality_check
    try:
        yield
    finally:
        V.quality_check=original


def check_base(asset, root):
    """Validate every frozen base invariant, explicitly using the v5 profile."""
    asset,root=Path(asset).resolve(),Path(root).resolve()
    bind_legacy_rows(asset,read(asset/'validation.json'),read(asset/'spec.json'))
    with resource_contract():
        result=V.check(asset,root)
    return {**result,'validation_profile':PROFILE,'legacy_resource_rows':'SUPERSEDED, not PASS'}


def allocation(path):
    doc,binary=V.frozen().read_glb(path)
    ranges=set()
    for image in doc.get('images',[]):
        if 'bufferView' in image:
            view=doc['bufferViews'][image['bufferView']]
            ranges.add((view.get('byteOffset',0),view['byteLength']))
    image_bytes=sum(length for offset,length in ranges)
    with Path(path).open('rb') as handle:
        header=handle.read(20)
    json_bytes=struct.unpack_from('<I',header,12)[0]
    total=Path(path).stat().st_size
    return {'bytes':total,'unique_embedded_image_bytes':image_bytes,'json_chunk_bytes':json_bytes,
            'other_buffer_and_container_bytes':total-image_bytes-json_bytes}


def package_budget(asset, spec, report, config=None):
    config=read(HERE/'v5_budget.json') if config is None else config
    rows,errors=[],[]
    try:
        V.require(config.get('schema')==5 and config.get('status')=='APPROVED',
                  'V5 fixed resource allocations are pending review; no release acceptance is possible')
        V.require(config.get('legacy_limits')=={'H1_bytes':33554432,'H2_triangles':280000},
                  'Original H1/H2 limits must be documented unchanged')
        limits=config.get('families',{}).get(spec['family'])
        V.require(isinstance(limits,dict) and set(limits)==set(V.LEVELS),'Missing fixed reviewed family/LOD allocations')
        for level in V.LEVELS:
            limit=limits[level]
            V.require(isinstance(limit,dict) and type(limit.get('max_bytes')) is int and limit['max_bytes']>0
                      and type(limit.get('max_triangles')) is int and limit['max_triangles']>0,
                      'Resource allocations must be fixed positive integer limits')
            for palette in V.PALETTES:
                path='model/%s/%s.glb'%(palette,level)
                measured=allocation(Path(asset)/path)
                measured['triangles']=report['glb_files'][path]['structure']['triangles']
                passed=measured['bytes']<=limit['max_bytes'] and measured['triangles']<=limit['max_triangles']
                rows.append({'path':path,'passed':passed,**measured,**limit})
                if not passed:errors.append('Fixed v5 resource allocation exceeded: '+path)
    except (ValueError,KeyError,TypeError,OSError) as error:
        errors.append(str(error))
    return {'passed':not errors,'family':spec['family'],'allocations':rows,'errors':errors,
            'policy_sha256':V.sha(V.canonical(config)),
            'scope':'Fixed reviewed v5 bytes and triangle caps; original H1/H2 evidence remains SUPERSEDED, never fabricated as PASS.'}


def validate_upgrade(upgrade):
    V.require(upgrade.get('schema')==5 and upgrade.get('passed') is True,'Missing/failing v5 upgrade')
    rows=V.passing_matrix(upgrade.get('matrix'),'v5 detail')
    checks=upgrade.get('checks',{})
    V.require(set(rows)==DETAIL_GATES and set(checks)==DETAIL_GATES,'Incomplete detail gate set')
    for key in DETAIL_GATES:
        V.require(rows[key].get('required') is True and rows[key].get('evidence')==checks[key]
                  and checks[key].get('passed') is True,'Missing/failing detail gate: '+key)


def check(asset, root):
    asset,root=Path(asset).resolve(),Path(root).resolve()
    spec,report=read(asset/'spec.json'),read(asset/'validation.json')
    validate_upgrade(report.get('detail_upgrade',{}))
    expected={path:V.digest(root/path) for path in sorted(AUDIT_SOURCES)}
    V.require(report['detail_upgrade'].get('audit_source_sha256')==expected,'Stale v5 audit/profile/CI provenance')
    budget=package_budget(asset,spec,report,read(root/'potc/common/v5_budget.json'))
    V.require(budget['passed'] and budget==report['detail_upgrade']['checks']['package_budget'],
              'Recomputed fixed v5 resource allocation failed or differs')
    return check_base(asset,root)


def self_test():
    matrix=[{'id':key,'required':True,'status':'PASS','scope':'measured','evidence':{}}
            for key in sorted(V.QUALITY_IDS|{'F1','F2','F3','F4'})]
    for row in matrix:
        if row['id']=='H1':row.update(status='FAIL',evidence={'bytes':40000000,'budget_bytes':33554432})
        if row['id']=='H2':row.update(status='FAIL',evidence={'triangles':350000,'budget':280000})
    source={'passed':False,'full_detail_uv_targets':True,'matrix':matrix,'topology':{'passed':True},'missing_uv_objects':[]}
    result=supersede_resources(source,True)
    quality_check(result,True,'synthetic v5')
    V.require(source['matrix']==matrix and next(r for r in matrix if r['id']=='H1')['status']=='FAIL',
              'Supersession mutated raw legacy evidence')
    rejected=[]
    for name in ['hide legacy FAIL','waive E1','waive F8','change old byte limit','change old triangle limit','drop H2']:
        bad=copy.deepcopy(result)
        if name=='hide legacy FAIL':bad['legacy_resource_rows']['H1']['status']='PASS'
        elif name in ('waive E1','waive F8'):
            key=name.split()[1];next(r for r in bad['matrix'] if r['id']==key).update(required=False,status='SUPERSEDED')
        elif name=='change old byte limit':bad['legacy_resource_rows']['H1']['evidence']['budget_bytes']+=1
        elif name=='change old triangle limit':bad['legacy_resource_rows']['H2']['evidence']['budget']+=1
        else:bad['matrix']=[r for r in bad['matrix'] if r['id']!='H2']
        try:quality_check(bad,True,name)
        except ValueError:rejected.append(name)
        else:raise ValueError('Supersession abuse accepted: '+name)
    V.require(not package_budget(Path('.'),{'family':'brig'},{},{'schema':5,'status':'PENDING_REVIEW'})['passed'],
              'Pending resource allocations must never pass')
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        asset=Path(folder)
        doc=V.canonical({'asset':{'version':'2.0'},'buffers':[{'byteLength':0}]})
        doc+=b' '*((-len(doc))%4)
        raw=(struct.pack('<4sII',b'glTF',2,28+len(doc))+struct.pack('<I4s',len(doc),b'JSON')
             +doc+struct.pack('<I4s',0,b'BIN\0'))
        report={'glb_files':{}}
        for level in V.LEVELS:
            for palette in V.PALETTES:
                relative='model/%s/%s.glb'%(palette,level)
                path=asset/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
                report['glb_files'][relative]={'structure':{'triangles':350000}}
        policy={'schema':5,'status':'APPROVED','legacy_limits':{'H1_bytes':33554432,'H2_triangles':280000},
                'families':{'brig':{level:{'max_bytes':len(raw),'max_triangles':350000} for level in V.LEVELS}}}
        V.require(package_budget(asset,{'family':'brig'},report,policy)['passed'],'Fixed exact resource boundary rejected')
        for metric in ('max_bytes','max_triangles'):
            bad=copy.deepcopy(policy);bad['families']['brig']['ship'][metric]-=1
            V.require(not package_budget(asset,{'family':'brig'},report,bad)['passed'],
                      'Oversized actual resource accepted: '+metric)
            rejected.append('fixed '+metric+' overflow rejected')
    # The unmodified v4 validator must reject the v5-only applicability profile.
    try:V.quality_check(result,True,'old v4')
    except ValueError:pass
    else:raise ValueError('Old v4 unexpectedly accepted superseded H1/H2')
    return {'passed':True,'negative_controls':rejected+['pending limits denied','unmodified v4 rejects v5 supersession'],
            'scope':'Explicit H1/H2 applicability only; every other frozen quality gate remains mandatory.'}


if __name__=='__main__':
    print(json.dumps(self_test(),indent=2))
