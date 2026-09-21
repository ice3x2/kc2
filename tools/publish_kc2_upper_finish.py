"""CON-ARCH-006 / OPS-ARCH-006 reviewed upper-finish publication."""
from pathlib import Path
import argparse,json,shutil

from tools.kc2_upper_finish import ROOT,STAGE,digest,write

MODELS=ROOT/'hardware/MODELS';REPORT=ROOT/'docs/reports/upper-finish-20260921';MANIFEST=MODELS/'kc2_upper_finish_manifest.json'
BASELINE=MODELS/'kc2_wall_gap_fix_manifest.json'

def publish():
    plan=json.loads((STAGE/'plan.json').read_text());review=json.loads((STAGE/'review.json').read_text());tests=json.loads((STAGE/'tests.json').read_text())
    if review['status']!='pass' or review['errors'] or tests['status']!='pass' or tests['tests_run']<5:raise ValueError('Review/tests incomplete')
    if len(plan['jobs'])!=6 or set(review['rows'])!=set(plan['jobs']) or len(review['assembly'])!=12 or len(review['joined'])!=6 or len(review['ab'])!=3:
        raise ValueError('Incomplete model/assembly review')
    for name,sha in review['source_sha256'].items():
        if digest(ROOT/name)!=sha:raise ValueError('Reviewed input changed '+name)
    old=json.loads(BASELINE.read_text());oldsha=digest(BASELINE)
    for name,sha in old['preserved_pcb_gerber_sha256'].items():
        if digest(ROOT/name)!=sha:raise ValueError('PCB/Gerber changed '+name)
    lower={name:sha for name,sha in old['outputs'].items() if '_upper_housing' not in name}
    baseline_upper={name:sha for name,sha in old['outputs'].items() if '_upper_housing' in name}
    for name,sha in lower.items():
        if digest(ROOT/name)!=sha:raise ValueError('Lower housing changed '+name)
    copies=[];new_upper={};evidence={};aliases={}
    for name,sha in review['source_sha256'].items():
        path=ROOT/name
        if path.is_relative_to(STAGE):
            rel=path.relative_to(STAGE)
            if path.suffix.lower() in ('.step','.f3d','.stl'):
                dest=MODELS/path.name;new_upper[dest.relative_to(ROOT).as_posix()]=sha
            else:
                dest=REPORT/'evidence'/rel;evidence[dest.relative_to(ROOT).as_posix()]=sha
            aliases[name]=dest.relative_to(ROOT).as_posix();copies.append((path,dest,sha))
    for path in (STAGE/'review.json',STAGE/'tests.json'):
        dest=REPORT/'evidence'/path.name;copies.append((path,dest,digest(path)));evidence[dest.relative_to(ROOT).as_posix()]=digest(path)
    if len(new_upper)!=21 or sum(n.endswith('.stl') for n in new_upper)!=9:raise ValueError('Expected 21 upper files / 9 STL')
    for src,dest,sha in copies:
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
        if digest(dest)!=sha:raise ValueError('Copy mismatch '+str(dest))
    sources={n:s for n,s in review['source_sha256'].items() if n not in aliases and n not in baseline_upper}
    sources['tools/publish_kc2_upper_finish.py']=digest(Path(__file__))
    data=dict(requirements=['CON-ARCH-006','OPS-ARCH-006'],status='digital_review_pass',physical_qualified=False,
        baseline_manifest=BASELINE.relative_to(ROOT).as_posix(),baseline_manifest_sha256=oldsha,baseline_upper_sha256=baseline_upper,
        outputs={**lower,**new_upper},new_upper_outputs=new_upper,preserved_lower_outputs=lower,evidence_sha256=evidence,
        source_sha256=sources,historical_dependency_aliases=aliases,preserved_pcb_gerber_sha256=old['preserved_pcb_gerber_sha256'],
        scope='All MX/Choc V1/Deep Sea uppers: closed nonfunctional inner voids and one coplanar Z4.40 print datum; lowers and ordered PCB/Gerber unchanged')
    write(MANIFEST,data);return verify()

def verify():
    data=json.loads(MANIFEST.read_text())
    if digest(ROOT/data['baseline_manifest'])!=data['baseline_manifest_sha256']:raise ValueError('Baseline manifest changed')
    old=json.loads((ROOT/data['baseline_manifest']).read_text())
    if {n:s for n,s in old['outputs'].items() if '_upper_housing' in n}!=data['baseline_upper_sha256']:
        raise ValueError('Baseline upper provenance differs')
    for group in ('outputs','evidence_sha256','source_sha256','preserved_pcb_gerber_sha256'):
        for name,sha in data[group].items():
            if digest(ROOT/name)!=sha:raise ValueError('Changed/missing publication dependency '+name)
    print('PASS: 35 canonical CAD files; 9 revised upper STL, 6 F3D, 6 STEP; lower/PCB/Gerber preserved. Physical qualification pending.')
    return data

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true')
    publish() if parser.parse_args().publish else verify()
