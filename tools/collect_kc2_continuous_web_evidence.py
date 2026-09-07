"""CON-ARCH-006/OPS-ARCH-007: collect r5 checks, without fabrication packaging."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/reports/continuous-web-20260908-r5'

def collect(role):
    OUT.mkdir(parents=True,exist_ok=True)
    models=ROOT/'hardware/MODELS'
    paths=[p for p in models.glob('*') if p.is_file() and p.suffix in ('.json','.step','.stl','.f3d')]
    paths+=list((ROOT/'tools').glob('*housing*.py'))
    paths+=[ROOT/'tools/test_kc2_continuous_web.py',ROOT/'tools/test_kc2_closed_floor.py',Path(__file__)]
    def hashes():return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before=hashes()
    if role=='tests':
        args=['-m','unittest','tools.test_kc2_continuous_web','tools.test_kc2_closed_floor',
            'tools.test_verify_kc2_mx_housing_contract','tools.test_kc2_mx_housing',
            'tools.test_kc2_recessed_lid','tools.test_kc2_current_layout',
            'tools.test_verify_kc2_x3_v2_housing.ClosedFloorBRepTests',
            'tools.test_verify_kc2_x3_v2_housing.ServiceInterfaceContractUnitTests']
    elif role=='report-tests':
        # Reuse the completed canonical BRep analysis as the expensive fixture,
        # with its bytes bound above. This is not a second independent CAD run.
        args=['-c',"import json,unittest; from unittest.mock import patch; import tools.test_verify_kc2_x3_v2_housing as t; r=json.loads(t.housing_verifier.REPORT_PATH.read_text(encoding='utf8')); assert not t.verify_report(r); p=patch.object(t,'analyze_v2_housing',return_value=r); p.start(); result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(t.V2LoadBearingHousingTests)); p.stop(); raise SystemExit(not result.wasSuccessful())"]
    elif role=='digital':args=['-m','tools.verify_kc2_mx_housing_contract']
    elif role=='native':args=['-c','import json; from tools.verify_kc2_housing_f3d import verify_f3d_outputs; print(json.dumps(verify_f3d_outputs()))']
    else:raise ValueError(role)
    process=subprocess.run([sys.executable,'-B',*args],cwd=ROOT,capture_output=True,text=True,encoding='utf8',errors='replace')
    report={'requirements':['CON-ARCH-006','OPS-ARCH-007'],'command':args,
        'exit_code':process.returncode,'stdout':process.stdout,'stderr':process.stderr,
        'source_sha256':before,'sources_unchanged':before==hashes(),'physical_qualification_complete':False}
    if role in ('digital','native'):report['result']=json.loads(process.stdout)
    (OUT/(role+'.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(role,process.returncode,process.stdout[-1800:],process.stderr[-1800:])
    if not report['sources_unchanged']:raise RuntimeError('Evidence source changed during checks')
    if role in ('tests','report-tests') and process.returncode:raise RuntimeError('Regression tests failed')
    if role=='native' and (process.returncode or report['result']):raise RuntimeError('Native checks failed')
    if role=='digital' and (process.returncode not in (0,2) or report['result']['errors'] or report['result']['native_archive_blockers']):
        raise RuntimeError('Digital checks failed')

if __name__=='__main__':collect(sys.argv[1])
