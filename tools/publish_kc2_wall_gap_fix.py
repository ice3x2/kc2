"""CON-ARCH-006 / OPS-ARCH-006: all-at-once reviewed gap-fix publication."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
from tools.kc2_wall_gap_fix import ROOT,STAGE,write,BASELINE
from tools.kc2_pcb_seating import digest

MODELS=ROOT/'hardware/MODELS'
REPORT=ROOT/'docs/reports/wall-gap-fix-20260921'
MANIFEST=MODELS/'kc2_wall_gap_fix_manifest.json'

def publish():
    plan=json.loads((STAGE/'plan.json').read_text())
    review=json.loads((STAGE/'review.json').read_text())
    tests=json.loads((STAGE/'tests.json').read_text())
    if review['status']!='pass' or review['errors'] or tests['status']!='pass' or tests['tests_run']<5:
        raise ValueError('Review or tests incomplete')
    if len(plan['jobs'])!=10 or set(review['rows'])!=set(plan['jobs']):
        raise ValueError('Missing jobs')
    if len(review['assembly'])!=12 or len(review['ab'])!=5 or len(review['joined'])!=6:
        raise ValueError('Missing assembly/motion checks')
    for name,sha in review['source_sha256'].items():
        if digest(ROOT/name)!=sha:raise ValueError('Reviewed input changed '+name)
    old=json.loads((MODELS/'kc2_wrap_housing_manifest.json').read_text())
    for name,sha in old['preserved_pcb_gerber_sha256'].items():
        if digest(ROOT/name)!=sha:raise ValueError('PCB/Gerber changed '+name)
    outputs={};aliases={};evidence={};baseline={}
    for name,sha in plan['source_sha256'].items():
        if name.startswith('hardware/MODELS/'):
            baseline[name]=sha
    # Resolve every reviewed staged dependency to a portable final path.
    copies=[]
    for name,sha in review['source_sha256'].items():
        path=ROOT/name
        if path.is_relative_to(STAGE):
            rel=path.relative_to(STAGE)
            dest=MODELS/path.name if path.suffix in ('.stl','.step','.f3d') else REPORT/'evidence'/rel
            aliases[name]=dest.relative_to(ROOT).as_posix()
            copies.append((path,dest,sha))
            (outputs if path.suffix in ('.stl','.step','.f3d') else evidence)[dest.relative_to(ROOT).as_posix()]=sha
    if len(outputs)!=35 or sum(n.endswith('.stl') for n in outputs)!=15:
        raise ValueError('Incomplete 35-file publication')
    for path in (STAGE/'tests.json',STAGE/'review.json'):
        dest=REPORT/'evidence'/path.name
        copies.append((path,dest,digest(path)));evidence[dest.relative_to(ROOT).as_posix()]=digest(path)
    for src,dest,sha in copies:
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dest)
        if digest(dest)!=sha:raise ValueError('Publication copy differs '+str(dest))
    sources={name:sha for name,sha in review['source_sha256'].items()
             if name not in aliases and name not in baseline}
    sources['tools/publish_kc2_wall_gap_fix.py']=digest(Path(__file__))
    data=dict(requirements=['CON-ARCH-006','OPS-ARCH-006'],status='digital_review_pass',
              physical_qualified=False,baseline_commit=BASELINE,baseline_source_sha256=baseline,
              outputs=outputs,evidence_sha256=evidence,source_sha256=sources,
              historical_dependency_aliases=aliases,preserved_pcb_gerber_sha256=old['preserved_pcb_gerber_sha256'],
              scope='Unintended same-part wall slits closed; original screw stack and functional clearances retained')
    write(MANIFEST,data)
    return verify()

def verify():
    data=json.loads(MANIFEST.read_text())
    for group in ('outputs','evidence_sha256','source_sha256','preserved_pcb_gerber_sha256'):
        for name,sha in data[group].items():
            if digest(ROOT/name)!=sha:raise ValueError('Changed/missing publication dependency '+name)
    # Baseline CAD is kept in Git history, never another active model folder.
    for name,sha in data['baseline_source_sha256'].items():
        import hashlib
        raw=subprocess.run(['git','show',data['baseline_commit']+':'+name],cwd=ROOT,check=True,capture_output=True).stdout
        if hashlib.sha256(raw).hexdigest()!=sha:raise ValueError('Wrong Git baseline '+name)
    print('PASS: 35 CAD files, 15 STL; source/evidence/PCB hashes match. Physical qualification remains pending.')
    return data

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true')
    publish() if parser.parse_args().publish else verify()
