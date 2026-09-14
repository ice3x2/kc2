"""CON-ARCH-006 explicit native feature proof by EXACT kernel material equality.

No feature Boolean/section is rerun and source STL evidence remains source STL
evidence. Any nonzero difference, including below ordinary audit tolerance,
requires the original direct native-feature checker instead.
"""
import argparse,json,math
from pathlib import Path
from tools.kc2_registered_release_gate import STAGE,stem,sha_bytes,passed
SCHEMA='lower-native-exact-material-transfer-v1'

def native_checker_paths(side):
    if side not in ('left','right'):raise ValueError('Unknown native checker side')
    names=['review_kc2_registered_native','test_review_kc2_registered_native','kc2_registered_native']
    if side=='right':names+=['review_kc2_right_lower_native','test_review_kc2_right_lower_native']
    return ['tools/'+name+'.py' for name in names]

def recipe(feature,side,kind):
    if side not in ('left','right') or feature not in ('void','floor','split','floor-capture','magnetic-entry'):raise ValueError('Unknown transfer predicate')
    if feature in ('floor','split','floor-capture'):
        if kind not in ('normal','magnetic') or feature in ('split','floor-capture') and side!='right':raise ValueError('Wrong transfer variant')
        folder=f'{STAGE}/lower/{side}-{kind}';source=folder+'/'+feature+'-review.json';output=folder+'/'+feature+'-native-review.json';variants=[kind]
    else:
        if kind is not None:raise ValueError('Cross-variant predicate requires both jobs')
        folder=STAGE+'/lower';source=f'{folder}/{side}-{feature}-review.json'
        if feature=='void' and side=='right':source=folder+'/right-receiver-strata-transfer.json'
        output=f'{folder}/{side}-native-void-review.json' if feature=='void' else f'{folder}/{side}-magnetic-entry-native-review.json'
        variants=['normal','magnetic']
    return dict(feature=feature,side=side,kind=kind,source=source,output=output,jobs=[f'lower:{side}:{v}' for v in variants])

def exact_native(record,label,required):
    passed(record);count=1 if label.split(':')[1]=='left' else 2
    if record.get('selected_job')!=label or record.get('independent_geometry_verified') is not True:raise ValueError('Wrong independent native identity')
    if len(record.get('parts',[]))!=count:raise ValueError('Missing valid matched native body')
    for part in record['parts']:
        passed(part)
        for name in ('missing_mm3','extra_mm3'):
            value=part.get(name)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value!=0.0:
                raise ValueError('Native material is not EXACTLY equal; direct native feature audit required')
    if any(record.get('source_sha256',{}).get(n)!=sha for n,sha in required.items()):raise ValueError('Stale/missing whole-material identity')

def inputs(spec,read):
    source_raw=read(spec['source']);source=json.loads(source_raw);passed(source)
    if source.get('schema')==SCHEMA:raise ValueError('Proof transfers cannot be chained')
    bindings={spec['source']:sha_bytes(source_raw)};equalities={}
    def merge(record):
        for name,sha in record.get('source_sha256',{}).items():
            if name in bindings and bindings[name]!=sha:raise ValueError('Conflicting source chain')
            if sha_bytes(read(name))!=sha:raise ValueError('Changed direct proof source '+name)
            bindings[name]=sha
    merge(source)
    for label in spec['jobs']:
        _,side,kind=label.split(':');folder=f'{STAGE}/lower/{side}-{kind}';name=stem('lower',side,kind)
        gp=folder+'/generation.json';step=folder+'/'+name+'.step';np=folder+'/native-generation.json';rp=folder+'/native-review.json'
        genraw=read(gp);g=json.loads(genraw);native_raw=read(np);native=json.loads(native_raw);audit_raw=read(rp);audit=json.loads(audit_raw)
        if g.get('status')!='generated_pending_independent_review' or g.get('side')!=side or g.get('magnetic') is not (kind=='magnetic') or type(g.get('body_count')) is not int or g.get('body_count')!=(1 if side=='left' else 2):raise ValueError('Wrong lower source generation')
        if native.get('status')!='pass' or native.get('phase')!='complete' or native.get('selected_job')!=label or set(native.get('outputs',{}))!={label}:raise ValueError('Wrong native generation')
        row=native['outputs'][label];step_sha=sha_bytes(read(step));gen_sha=sha_bytes(genraw)
        if row.get('source_step')!=name+'.step' or row.get('generation_record')!='generation.json' or any(len(row.get(k,[]))!=g['body_count'] for k in ('source_solids','reopened_solids')):raise ValueError('Native source filename or solid count mismatch')
        if g.get('outputs',{}).get(name+'.step')!=step_sha or row.get('source_sha256')!=step_sha or row.get('generation_sha256')!=gen_sha or row.get('round_trip_verified') is not True or type(row.get('expected_body_count')) is not int or row.get('expected_body_count')!=g['body_count']:raise ValueError('Native source/body identity mismatch')
        if row.get('f3d')!=name+'.f3d' or row.get('readback_step')!=name+'.native-readback.step':raise ValueError('Wrong native files')
        required={gp:gen_sha,step:step_sha,np:sha_bytes(native_raw)}
        for file_key,sha_key in [('f3d','f3d_sha256'),('readback_step','readback_sha256')]:
            path=folder+'/'+row[file_key];sha=sha_bytes(read(path))
            if sha!=row.get(sha_key):raise ValueError('Changed native artifact')
            required[path]=sha
        for path in native_checker_paths(side):
            required[path]=sha_bytes(read(path))
        exact_native(audit,label,required)
        for path in (gp,step):
            if source.get('source_sha256',{}).get(path)!=required[path]:raise ValueError('Feature audit not bound to same source material')
        merge(g);merge(native);merge(audit);bindings.update(required);bindings[rp]=sha_bytes(audit_raw)
        equalities[label]=dict(native_review=rp,sha256=sha_bytes(audit_raw),body_count=g['body_count'],missing_mm3=[0.0]*g['body_count'],extra_mm3=[0.0]*g['body_count'])
    from tools.publish_kc2_registered_housings import check_transfer_source
    check_transfer_source(source,spec,read)
    return source,bindings,equalities

def validate(record,spec,read):
    passed(record)
    expected={k:spec[k] for k in ('feature','side','kind')}
    if record.get('schema')!=SCHEMA or any(record.get(k)!=v for k,v in expected.items()):raise ValueError('Wrong derived-proof identity')
    if record.get('native_feature_rerun') is not False or record.get('proof_method')!='exact_zero_whole_material_difference' or record.get('kernel_computed_material_identity') is not True or record.get('physical_qualified') is not False:raise ValueError('Derived proof mislabels a direct rerun or physical identity')
    source,bindings,equalities=inputs(spec,read)
    if record.get('source_actual_report')!=spec['source'] or record.get('source_actual_sha256')!=bindings[spec['source']] or record.get('native_equalities')!=equalities:raise ValueError('Derived proof evidence identity differs')
    if any(record.get('source_sha256',{}).get(n)!=sha for n,sha in bindings.items()):raise ValueError('Derived proof source chain incomplete')
    return source

def build(feature,side,kind=None,root=None):
    from tools.publish_kc2_registered_housings import contained
    root=Path(root or Path(__file__).resolve().parents[1]).resolve();spec=recipe(feature,side,kind)
    read=lambda name:contained(root,name).read_bytes()
    source,bindings,equalities=inputs(spec,read)
    for name in ('tools/kc2_lower_native_transfer.py','tools/test_kc2_lower_native_transfer.py','tools/kc2_registered_release_gate.py',
                 'tools/publish_kc2_registered_housings.py','tools/test_publish_kc2_registered_housings.py'):
        bindings[name]=sha_bytes(read(name))
    record=dict(schema=SCHEMA,status='pass',errors=[],feature=feature,side=side,kind=kind,source_actual_report=spec['source'],
      source_actual_sha256=bindings[spec['source']],native_equalities=equalities,source_sha256=bindings,
      native_feature_rerun=False,proof_method='exact_zero_whole_material_difference',kernel_computed_material_identity=True,physical_qualified=False,
      requirements=['CON-ARCH-006','OPS-ARCH-006'],limitations=['Kernel material equality, not a repeated native feature test','STL metrics remain original source STL evidence','Physical printing/strength/fit unqualified'])
    validate(record,spec,read)
    for name,sha in bindings.items():
        if sha_bytes(read(name))!=sha:raise ValueError('Source changed during proof transfer')
    output=contained(root,spec['output'])
    if output.exists() and json.loads(output.read_bytes()).get('schema')!=SCHEMA:raise ValueError('Existing direct native report retained; no replacement')
    output.write_text(json.dumps(record,indent=2)+'\n');return record

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('feature',choices=['void','floor','split','floor-capture','magnetic-entry']);p.add_argument('side',choices=['left','right']);p.add_argument('--kind',choices=['normal','magnetic']);args=p.parse_args()
    result=build(args.feature,args.side,args.kind);print(result['status'],result['proof_method'])
