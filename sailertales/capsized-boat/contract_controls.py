"""Positive/negative rescue-hook controls on the actual delivered main GLB.

Run in Blender: --python contract_controls.py -- ASSET_DIRECTORY
Only writes a control report; never edits model geometry or interaction anchors.
"""
import copy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'sailertales/common'))
import v2_audit as A
import v3_prop_audit as P

asset=Path(sys.argv[sys.argv.index('--')+1]).resolve()
states=P.read(asset/'states.json');spec=P.read(asset/'spec.json');nav=P.read(asset/'navigation.json')
records=A.object_records(asset/'model/ship.glb')
markers=P.anchors_current()
positive=P.seat_check(states,records,markers)
assert positive['passed'],positive
raised=copy.deepcopy(markers);raised['seat_anchor'][1]+=.50
negative=P.seat_check(states,records,raised)
assert not negative['passed'],'A seat floating half a metre above the real hull must fail'
wrong_offset=copy.deepcopy(markers);wrong_offset['seat_anchor'][0]+=.10
assert not P.seat_check(states,records,wrong_offset)['passed'],'Wrong lateral rescue position must fail'
wrong_float=copy.deepcopy(states);wrong_float['float']['span']=99
assert P.contract_errors(spec,wrong_float,nav),'Incorrect source flotation span must fail'
result={'passed':True,'scope':'Actual delivered main GLB and contract, static attachment controls',
        'actual_supported_seat':positive,'raised_seat_rejected':negative,
        'wrong_lateral_offset_rejected':True,'incorrect_float_span_rejected':True,
        'models_modified':False}
(asset/'contract-negative-controls.json').write_text(json.dumps(result,indent=2)+'\n')
print('CAPSIZED_CONTRACT_CONTROLS_PASS',json.dumps(result),flush=True)
