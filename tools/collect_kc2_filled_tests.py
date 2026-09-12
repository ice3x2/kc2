"""CON-ARCH-006/OPS-ARCH-006 executed, source-bound full development tests."""
import hashlib,json,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MODULES=['tools.'+n for n in ['test_kc2_solid_plate','test_kc2_filled_plate_profiles',
    'test_kc2_filled_plate_plan','test_review_kc2_filled_plates','test_verify_kc2_filled_plate_contract',
    'test_review_kc2_filled_mesh','test_kc2_filled_native','test_review_kc2_filled_native',
    'test_review_kc2_filled_assembly','test_publish_kc2_filled_plates']]


def main():
    sources=['kc2_solid_plate.py','kc2_filled_plate_profiles.py','generate_kc2_filled_plates.py',
        'review_kc2_filled_plates.py','verify_kc2_filled_plate_contract.py','review_kc2_filled_mesh.py',
        'kc2_filled_native.py','review_kc2_filled_native.py','review_kc2_filled_assembly.py','publish_kc2_filled_plates.py']
    paths=[ROOT/'tools'/n for n in sources+[m.split('.')[-1]+'.py' for m in MODULES]]
    paths += [Path(__file__),ROOT/'tools/fusion/KC2FilledPlatesToF3D/KC2FilledPlatesToF3D.py']
    hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before=hashes();command=[sys.executable,'-B','-m','unittest',*MODULES,'-v']
    run=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf8')
    unchanged=before==hashes()
    report=dict(requirements=['CON-ARCH-006','CON-ARCH-007','OPS-ARCH-006'],
        status='pass' if run.returncode==0 and unchanged else 'failed',source_sha256=before,
        command=command,stdout=run.stdout,stderr=run.stderr,sources_unchanged=unchanged,
        scope='Full filled-plate regression suite; actual six-model STEP/native and nine-STL evidence separate',
        physical_qualified=False)
    target=ROOT/'docs/reports/solid-filled-plates-20260913/final-tests.json'
    target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps(dict(status=report['status'],result=run.stderr[-140:])))
    return run.returncode or not unchanged


if __name__=='__main__':raise SystemExit(main())
