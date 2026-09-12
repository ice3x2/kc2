"""CON-ARCH-006 actual reopened F3D geometry against independent full sections.

Requires a completed six-job Fusion run. Reads only staging CAD and writes
source-bound evidence; never publishes or qualifies physical strength/fit.
"""
import argparse,hashlib,json
from pathlib import Path
import cadquery as cq
from tools import generate_kc2_magnetic_housings as base
from tools.verify_kc2_filled_plate_contract import contract_plan,check_record
from tools.review_kc2_filled_plates import audit_prismatic_solid

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.codex-tmp/solid-filled-plates'


def identity_errors(native):
    errors=[]
    labels={s+'_'+k:(s,k) for s in ['left','right'] for k in ['mx','choc_v1','deep_sea']}
    if native.get('status')!='pass':errors.append('native export incomplete')
    if native.get('physical_qualified') is not False:errors.append('physical qualification not established')
    outputs=native.get('outputs',{})
    if set(outputs)!=set(labels):errors.append('incomplete native variants')
    for label,(side,kind) in labels.items():
        row=outputs.get(label,{})
        stem=f'kc2_{side}_{kind}_upper_housing'
        for key,wanted in dict(source_step=stem+'.step',f3d=stem+'.f3d',
            readback_step=stem+'.native-readback.step',generation_record=f'{side}-{kind}.json').items():
            if row.get(key)!=wanted:errors.append(label+' '+key+' identity')
        if row.get('round_trip_verified') is not True:errors.append(label+' not reopened')
    return errors


def review(side,kind):
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    native_path=STAGE/'native-filled.json'
    native=json.loads(native_path.read_text(encoding='utf8'))
    identity=identity_errors(native)
    if identity:raise ValueError('Native identity: '+str(identity))
    row=native['outputs'][side+'_'+kind]
    generation_path=STAGE/f'{side}-{kind}.json'
    if row['generation_sha256']!=digest(generation_path):raise ValueError('Changed generation record')
    record=json.loads(generation_path.read_text(encoding='utf8'))
    bindings={**record['source_sha256'],**native['source_sha256']}
    for p in [Path(__file__),ROOT/'tools/test_review_kc2_filled_native.py',native_path,generation_path,
              ROOT/'tools/verify_kc2_filled_plate_contract.py',ROOT/'tools/test_verify_kc2_filled_plate_contract.py',
              ROOT/'tools/review_kc2_filled_plates.py',ROOT/'tools/test_review_kc2_filled_plates.py']:
        bindings[p.relative_to(ROOT).as_posix()]=digest(p)
    for name,sha in [(row['source_step'],row['source_sha256']),
                     (row['f3d'],row['f3d_sha256']),(row['readback_step'],row['readback_sha256'])]:
        bindings[(STAGE/name).relative_to(ROOT).as_posix()]=sha
    if record['outputs'][row['source_step']]!=row['source_sha256']:raise ValueError('Wrong native source')
    for name,sha in bindings.items():
        if digest(ROOT/name)!=sha:raise ValueError('Changed source: '+name)
    boards,_,_=base.load_plans();expected=contract_plan(side,boards[side],kind)
    errors=check_record(record,expected)
    if errors:raise ValueError('Contract mismatch: '+str(errors))
    print('Import actual native readback',side,kind,flush=True)
    solids=sorted(cq.importers.importStep(str(STAGE/row['readback_step'])).solids().vals(),key=lambda s:s.Center().x)
    if len(solids)!=(1 if side=='left' else 2):raise ValueError('Wrong native body count')
    results=[]
    for i,(shape,layers) in enumerate(zip(solids,expected['parts'])):
        print('Audit actual native sections',side,kind,i,flush=True)
        result=audit_prismatic_solid(shape,layers);results.append(result);errors.extend(result['errors'])
    for name,sha in bindings.items():
        if digest(ROOT/name)!=sha:raise ValueError('Source changed during native review: '+name)
    report=dict(requirements=['CON-ARCH-006','CON-ARCH-007','OPS-ARCH-006'],
        status='failed' if errors else 'pass',side=side,kind=kind,errors=errors,
        source_sha256=bindings,parts=results,physical_qualified=False,
        scope='Actual reopened F3D readback STEP against independently reconstructed complete physical design sections')
    (STAGE/f'{side}-{kind}-native-review.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--side',required=True,choices=['left','right'])
    parser.add_argument('--kind',required=True,choices=['mx','choc_v1','deep_sea'])
    args=parser.parse_args();r=review(args.side,args.kind)
    print(json.dumps(dict(status=r['status'],errors=r['errors'])))
    raise SystemExit(0 if r['status']=='pass' else 1)
