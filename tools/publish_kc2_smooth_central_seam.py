"""CON-ARCH-006 publish the filled guide windows only after CAD/STL/native checks."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.codex-tmp/smooth-central-seam'
REPORT=ROOT/'docs/reports/smooth-central-seam-20260914'
MANIFEST=ROOT/'hardware/MODELS/kc2_smooth_central_housing_manifest.json'
PARENT=ROOT/'hardware/MODELS/kc2_flat_central_housing_manifest.json'
BASELINE='9e0bb01d9ec8a0c93e5dc2f88271341e6ffd7513'
LABELS={'left:normal','left:magnetic','right:normal','right:magnetic'}


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf-8'))


def validate_records(review,native,native_review):
    for row,field in ((review,'rows'),(native,'outputs'),(native_review,'rows')):
        if row.get('status')!='pass' or row.get('errors')!=[] or set(row.get(field,{}))!=LABELS:
            raise ValueError('Incomplete actual CAD/STL/native evidence')
        if any(r.get('errors',[]) for r in row[field].values()):
            raise ValueError('Failed per-job evidence')
    if any(r.get('round_trip_verified') is not True or r.get('status')!='pass' for r in native['outputs'].values()):
        raise ValueError('F3D round trip missing')


def publish():
    review=read(STAGE/'review.json');native=read(STAGE/'native-generation.json');nr=read(STAGE/'native-review.json')
    validate_records(review,native,nr)
    parent=read(PARENT); outputs=dict(parent['outputs']);copies={}
    evidence={REPORT/n:STAGE/n for n in ('review.json','native-generation.json','native-review.json','wall-sections.png','tests.json')}
    sources={}
    for name,sha in review['source_sha256'].items():
        if digest(ROOT/name)!=sha: raise ValueError('Review input changed: '+name)
    for label in sorted(LABELS):
        folder=STAGE/'lower'/label.replace(':','-');generation=read(folder/'generation.json')
        n=native['outputs'][label]
        if generation['errors'] or generation['preservation']['errors']: raise ValueError('Failed additive proof')
        for name,sha in generation['source_sha256'].items():
            if digest(ROOT/name)!=sha: raise ValueError('Generation input changed: '+name)
            sources[name]=sha
        if (digest(folder/n['source_step'])!=n['source_sha256'] or
            digest(folder/'generation.json')!=n['generation_sha256'] or
            digest(folder/n['readback_step'])!=n['readback_sha256'] or
            nr['rows'][label]['f3d_sha256']!=n['f3d_sha256']):
            raise ValueError('Native identity differs')
        files={**generation['outputs'],n['f3d']:n['f3d_sha256']}
        for name,sha in files.items():
            source=folder/name
            if digest(source)!=sha: raise ValueError('Staged output changed')
            target=ROOT/'hardware/MODELS'/name;copies[target]=source
            outputs[target.relative_to(ROOT).as_posix()]=sha
        for name in ('generation.json','native-generation.json'):
            evidence[REPORT/'lower'/label.replace(':','-')/name]=folder/name
    if len(copies)!=14 or len(outputs)!=35: raise ValueError('Incomplete lower/upper inventory')
    for name,sha in parent['outputs'].items():
        if digest(ROOT/name)!=sha: raise ValueError('Canonical baseline changed')
    preserved=parent['preserved_pcb_gerber_sha256']
    if len(preserved)!=16 or any(digest(ROOT/n)!=s for n,s in preserved.items()):
        raise ValueError('Ordered PCB/Gerber changed')
    for target,source in evidence.items():
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    code=['tools/kc2_smooth_central_seam.py','tools/review_kc2_smooth_central_seam.py',
          'tools/test_kc2_smooth_central_seam.py','tools/publish_kc2_smooth_central_seam.py',
          'tools/test_publish_kc2_smooth_central_seam.py','tools/fusion/KC2SmoothCentral.py',
          'tools/kc2_flat_central_native.py','tools/review_kc2_flat_central_native.py',
          'tools/fusion/KC2FlatCentralToF3D/KC2FlatCentralToF3D.py']
    documents=['hardware/MODELS/README.md','hardware/MODELS/PRINT-smooth-central-housings.md',
               'docs/reports/smooth-central-seam-20260914/README.md','order.md']
    manifest=dict(status='digitally_verified_physical_pending',physical_qualified=False,
        requirement_ids=['CON-ARCH-006','CON-ARCH-007','OPS-ARCH-006'],
        baseline_revision=BASELINE,parent_manifest=PARENT.relative_to(ROOT).as_posix(),
        outputs=outputs,preserved_pcb_gerber_sha256=preserved,
        evidence_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in evidence},
        source_sha256={n:digest(ROOT/n) for n in code},documents_sha256={n:digest(ROOT/n) for n in documents},
        central_join=dict(guide_protrusions=0,former_guide_cavities_filled=True,ys_mm=[95,117],wall_thickness_mm=1.2),
        magnets=parent['magnets'])
    for target,source in copies.items():shutil.copy2(source,target)
    MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return verify()


def verify():
    m=read(MANIFEST)
    if m.get('status')!='digitally_verified_physical_pending' or m.get('physical_qualified') is not False or len(m.get('outputs',{}))!=35:
        raise ValueError('Invalid smooth-wall publication')
    for field in ('outputs','preserved_pcb_gerber_sha256','evidence_sha256','source_sha256','documents_sha256'):
        if not m.get(field):raise ValueError('Missing bindings')
        for name,sha in m[field].items():
            if digest(ROOT/name)!=sha:raise ValueError('Published file changed: '+name)
    validate_records(read(REPORT/'review.json'),read(REPORT/'native-generation.json'),read(REPORT/'native-review.json'))
    return m


if __name__=='__main__':
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--publish',action='store_true');g.add_argument('--verify',action='store_true')
    args=p.parse_args();r=publish() if args.publish else verify()
    print(json.dumps(dict(status=r['status'],outputs=len(r['outputs']),former_guide_cavities_filled=True)))
