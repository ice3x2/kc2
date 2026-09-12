import hashlib,json,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
modules=['tools.test_kc2_solid_plate','tools.test_kc2_filled_plate_profiles','tools.test_kc2_filled_plate_plan','tools.test_review_kc2_filled_plates','tools.test_verify_kc2_filled_plate_contract','tools.test_review_kc2_filled_mesh','tools.test_kc2_filled_native']
sources=['kc2_solid_plate.py','kc2_filled_plate_profiles.py','generate_kc2_filled_plates.py','review_kc2_filled_plates.py','verify_kc2_filled_plate_contract.py','review_kc2_filled_mesh.py','kc2_filled_native.py']+[m.split('.')[-1]+'.py' for m in modules]
paths=[root/'tools'/name for name in sources]+[Path(__file__),root/'tools/fusion/KC2FilledPlatesToF3D/KC2FilledPlatesToF3D.py']
hashes=lambda:{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
before=hashes();command=[sys.executable,'-B','-m','unittest',*modules,'-v']
run=subprocess.run(command,cwd=root,capture_output=True,text=True,encoding='utf8')
unchanged=before==hashes()
record=dict(requirements=['CON-ARCH-006','CON-ARCH-007'],status='pass' if unchanged and run.returncode==0 else 'failed',
 source_sha256=before,command=command,stdout=run.stdout,stderr=run.stderr,sources_unchanged=unchanged,
 scope='35 core, profile, actual-board plan, independent contract, BRep/STL mutation and native-job preflight regressions; actual exported CAD/native audits remain separate',physical_qualified=False)
folder=root/'docs/reports/solid-filled-plates-20260913'
(folder/'verifier-tests.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(status=record['status'],result=run.stderr[-170:])))
raise SystemExit(run.returncode or not unchanged)
