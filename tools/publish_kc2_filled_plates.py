"""CON-ARCH-006/OPS-ARCH-006 source-bound three-family publication.

Portable verification uses only the standard library and the published bytes.
It checks the executed CAD evidence chain, not just a manifest's pass label.
"""
import argparse,hashlib,json,math,shutil,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STAGE='.codex-tmp/solid-filled-plates'
REPORT='docs/reports/solid-filled-plates-20260913'
MANIFEST='hardware/MODELS/kc2_filled_plate_manifest.json'
OLD='hardware/MODELS/kc2_local_cover_manifest.json'
JOBS=[(s,k) for s in ['left','right'] for k in ['mx','choc_v1','deep_sea']]


def stem(side,kind):return f'kc2_{side}_{kind}_upper_housing'


def output_names():
    names=set()
    for side,kind in JOBS:
        name=stem(side,kind);names.update([name+'.step',name+'.f3d'])
        names.update([name+'.stl'] if side=='left' else [name+'_part_a.stl',name+'_part_b.stl'])
    return names


def report_names():
    return {f'{s}-{k}{suffix}.json' for s,k in JOBS for suffix in ['', '-sectional-progress','-native-review']}|{'native-filled.json','mesh-contract-review.json','assembly-review.json'}


def portable(path):
    if ':' in path or '\\' in path or path.startswith('/') or '..' in Path(path).parts:raise ValueError('Unsafe path: '+path)
    if path==OLD:return REPORT+'/previous-local-cover-manifest.json'
    if path.startswith(STAGE+'/'):
        name=path[len(STAGE)+1:]
        if name in output_names():return 'hardware/MODELS/'+name
        if name in report_names() or name in {stem(s,k)+'.native-readback.step' for s,k in JOBS}:return REPORT+'/'+name
        raise ValueError('Unknown staged artifact: '+path)
    if path in ['.codex-tmp/review-filled-meshes.py','.codex-tmp/collect-filled-verifier-tests.py']:
        return REPORT+'/evidence-scripts/'+Path(path).name
    if path.startswith('.codex-tmp/'):raise ValueError('Unmapped temporary path: '+path)
    return path


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_pass(record):
    if record.get('status')!='pass' or record.get('errors') or record.get('error'):
        raise ValueError('Evidence is incomplete or failed')
    if record.get('physical_qualified',False) is not False:raise ValueError('Physical qualification not established')


def section_errors(result,layers,tolerance=.001):
    errors=[]
    try:
        require_pass(result)
        levels=sorted({z for r in layers for z in [r['z0'],r['z1']]})
        if result['levels_mm']!=levels:errors.append('wrong levels')
        sections=result['sections']
        if len(sections)!=len(levels)-1:errors.append('incomplete sections')
        for row,a,b in zip(sections,levels,levels[1:]):
            if not math.isfinite(row['z_mm']) or abs(row['z_mm']-(a+b)/2)>1e-6:errors.append('wrong section height')
            for key in ['missing_mm2','extra_mm2']:
                if not math.isfinite(row[key]) or not 0<=row[key]<=tolerance:errors.append('section coverage error')
        if not math.isfinite(result['volume_error_mm3']) or result['volume_error_mm3']<0:errors.append('invalid volume evidence')
    except (KeyError,TypeError,ValueError):errors.append('invalid sectional evidence')
    return errors


def validate_records(records,sha):
    if set(records)!=report_names():raise ValueError('Incomplete executed audit inventory')
    mesh=records['mesh-contract-review.json'];assembly=records['assembly-review.json'];native=records['native-filled.json']
    for value in [mesh,assembly,native]:require_pass(value)
    if set(mesh['results'])!={s+'-'+k for s,k in JOBS}:raise ValueError('Incomplete actual STL audit')
    if set(native['outputs'])!={s+'_'+k for s,k in JOBS}:raise ValueError('Incomplete native run')
    preserved=assembly['preserved_pcb_gerber_lower_sha256']
    if len([n for n in preserved if n.startswith(('hardware/PCB/','hardware/GERBER/'))])!=16:raise ValueError('Missing ordered files')
    if len([n for n in preserved if n.startswith('hardware/MODELS/') and '_lower_housing' in n])!=14:raise ValueError('Missing lower variants')
    if set(assembly['joined'])!={'mx','choc_v1','deep_sea'}:raise ValueError('Incomplete joined assemblies')
    for r in assembly['joined'].values():
        if not math.isfinite(r['minimum_gap_mm']) or r['minimum_gap_mm']<.3 or not 0<=r['overlap_mm2']<1e-8:raise ValueError('Assembly clearance failed')
    for side,kind in JOBS:
        label=side+'-'+kind;name=stem(side,kind);count=1 if side=='left' else 2
        generation=records[label+'.json'];step=records[label+'-sectional-progress.json'];reopened=records[label+'-native-review.json']
        if generation['status']!='generated_pending_independent_review' or (generation['side'],generation['kind'])!=(side,kind):raise ValueError('Wrong generated model')
        stls=[name+'.stl'] if side=='left' else [name+'_part_a.stl',name+'_part_b.stl']
        if set(generation['outputs'])!=set([name+'.step',*stls]):raise ValueError('Wrong STEP/STL inventory')
        for audit in [step,reopened]:
            require_pass(audit)
            if len(audit['parts'])!=count or len(generation['parts'])!=count:raise ValueError('Wrong actual body count')
            for actual,part in zip(audit['parts'],generation['parts']):
                if section_errors(actual,part['layers']):raise ValueError(label+' incomplete actual sections')
            bindings=audit['source_sha256']
            if bindings.get(STAGE+'/'+label+'.json')!=sha(STAGE+'/'+label+'.json'):raise ValueError('Unbound generation record')
            if bindings.get(STAGE+'/'+name+'.step')!=generation['outputs'][name+'.step']:raise ValueError('Unbound actual STEP')
            for tool in ['tools/review_kc2_filled_plates.py','tools/test_review_kc2_filled_plates.py']:
                if bindings.get(tool)!=sha(tool):raise ValueError('Unbound actual section verifier')
        actual_mesh=mesh['results'][label]
        if actual_mesh['contract_errors'] or len(actual_mesh['parts'])!=count:raise ValueError('Independent contract failed')
        for actual,part,stl in zip(actual_mesh['parts'],generation['parts'],stls):
            if actual['stl']!=stl or section_errors(actual,part['layers'],.02):raise ValueError('Incomplete actual STL sections')
        n=native['outputs'][side+'_'+kind]
        for field,wanted in dict(source_step=name+'.step',f3d=name+'.f3d',readback_step=name+'.native-readback.step',generation_record=label+'.json').items():
            if n.get(field)!=wanted:raise ValueError('Wrong native identity')
        if n.get('round_trip_verified') is not True or n['source_sha256']!=generation['outputs'][name+'.step']:raise ValueError('Unverified native source')
        if n['generation_sha256']!=sha(STAGE+'/'+label+'.json'):raise ValueError('Stale native generation')
        for filename,key in [(n['f3d'],'f3d_sha256'),(n['readback_step'],'readback_sha256')]:
            if sha(STAGE+'/'+filename)!=n[key] or reopened['source_sha256'].get(STAGE+'/'+filename)!=n[key]:raise ValueError('Native byte chain mismatch')
        if reopened['source_sha256'].get(STAGE+'/native-filled.json')!=sha(STAGE+'/native-filled.json'):raise ValueError('Unbound Fusion execution record')
        for tool in ['tools/verify_kc2_filled_plate_contract.py','tools/test_verify_kc2_filled_plate_contract.py','tools/review_kc2_filled_native.py','tools/test_review_kc2_filled_native.py']:
            if reopened['source_sha256'].get(tool)!=sha(tool):raise ValueError('Unbound independent native contract')
    return preserved


def collect(root,staged):
    copies={};bindings={}
    def location(name):return root/(name if staged else portable(name))
    def sha(name):return digest(location(name))
    def bind(name,wanted):
        target=portable(name)
        if sha(name)!=wanted:raise ValueError('Changed input: '+name)
        if target in bindings and bindings[target]!=wanted:raise ValueError('Conflicting evidence: '+target)
        bindings[target]=wanted;copies[name]=target
    records={}
    for name in sorted(report_names()):
        path=STAGE+'/'+name;bind(path,sha(path))
        records[name]=json.loads(location(path).read_text(encoding='utf8'))
        for source,wanted in records[name].get('source_sha256',{}).items():bind(source,wanted)
    preserved=validate_records(records,sha)
    for side,kind in JOBS:
        for name,wanted in records[side+'-'+kind+'.json']['outputs'].items():bind(STAGE+'/'+name,wanted)
        n=records['native-filled.json']['outputs'][side+'_'+kind]
        bind(STAGE+'/'+n['f3d'],n['f3d_sha256']);bind(STAGE+'/'+n['readback_step'],n['readback_sha256'])
    for name,wanted in preserved.items():bind(name,wanted)
    for name in ['verifier-tests.json','final-tests.json']:
        path=REPORT+'/'+name;bind(path,sha(path));record=json.loads(location(path).read_text(encoding='utf8'));require_pass(record)
        if record.get('sources_unchanged') is not True or 'OK' not in record.get('stderr',''):raise ValueError('Test execution missing')
        for source,wanted in record['source_sha256'].items():bind(source,wanted)
    for path in ['tools/publish_kc2_filled_plates.py','tools/test_publish_kc2_filled_plates.py',
                 'hardware/MODELS/PRINT-filled-plates.md','hardware/MODELS/README.md']:
        bind(path,sha(path))
    return bindings,copies,preserved


def verify(root=ROOT):
    manifest=json.loads((root/MANIFEST).read_text(encoding='utf8'))
    require_pass(manifest)
    wanted,copies,preserved=collect(root,False)
    if manifest['source_sha256']!=wanted:raise ValueError('Missing, stale or unexpected publication bindings')
    if manifest['outputs']!=sorted('hardware/MODELS/'+n for n in output_names()):raise ValueError('Wrong final output inventory')
    if manifest['preserved_pcb_gerber_lower_sha256']!=preserved:raise ValueError('Wrong preservation inventory')
    return dict(status='pass',outputs=21,preserved_files=30,bindings=len(wanted),physical_qualified=False)


def publish():
    bindings,copies,preserved=collect(ROOT,True)
    # The replaced canonical MX revision must already be recoverable from Git.
    checkpoint=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    for name in ['kc2_left_mx_upper_housing.step','kc2_right_mx_upper_housing.step']:
        path='hardware/MODELS/'+name
        committed=subprocess.check_output(['git','show',checkpoint+':'+path],cwd=ROOT)
        if hashlib.sha256(committed).hexdigest()!=digest(ROOT/path):raise ValueError('Checkpoint current canonical MX in Git before replacement')
    manifest=dict(requirements=['CON-ARCH-006','CON-ARCH-007','OPS-ARCH-006'],status='pass',
        physical_qualified=False,new_fabrication_approval=False,replaced_revision_commit=checkpoint,
        outputs=sorted('hardware/MODELS/'+n for n in output_names()),source_sha256=bindings,
        preserved_pcb_gerber_lower_sha256=preserved)
    for source,target in copies.items():
        if source!=target:
            destination=ROOT/target;destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/source,destination)
    (ROOT/MANIFEST).write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    result=verify()
    # Historical manifest is preserved with its original bytes in the report.
    # The current print guide points only to the new complete three-family one.
    old=ROOT/OLD
    if old.is_file() and digest(old)==digest(ROOT/portable(OLD)):old.unlink()
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify',action='store_true');parser.add_argument('--preflight',action='store_true')
    args=parser.parse_args()
    if args.verify:result=verify()
    elif args.preflight:
        b,_,_=collect(ROOT,True);result=dict(status='pass',bindings=len(b),published=False)
    else:result=publish()
    print(json.dumps(result))
