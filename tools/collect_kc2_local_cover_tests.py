"""CON-ARCH-006/OPS-ARCH-006 source-bound regression evidence for local covers."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
MODULES=['tools.test_kc2_local_covers','tools.test_kc2_local_upper_covers',
    'tools.test_review_kc2_local_covers','tools.test_review_kc2_local_upper_covers',
    'tools.test_review_kc2_local_assembly','tools.test_publish_kc2_local_covers',
    'tools.test_review_kc2_local_native',
    'tools.test_historical_housing_fixture',
    'tools.test_kc2_continuous_web','tools.test_kc2_closed_floor',
    'tools.test_verify_kc2_mx_housing_contract','tools.test_kc2_mx_housing',
    'tools.test_kc2_recessed_lid','tools.test_kc2_current_layout',
    'tools.test_verify_kc2_x3_v2_housing.ClosedFloorBRepTests',
    'tools.test_verify_kc2_x3_v2_housing.ServiceInterfaceContractUnitTests']


def main():
    paths={ROOT/('/'.join(m.split('.')[:2])+'.py') for m in MODULES}
    paths.update((ROOT/'tools').glob('*local*cover*.py'))
    paths.update((ROOT/'tools').glob('*local_assembly.py'))
    paths.update((ROOT/'tools').glob('*local_native.py'))
    paths.add(ROOT/'tools/fusion/KC2LocalNativeReview/KC2LocalNativeReview.py')
    for name in ['generate_kc2_x3_v2_housings.py','generate_kc2_mx_upper_housings.py',
                 'generate_kc2_magnetic_housings.py','verify_kc2_x3_v2_housing.py',
                 'historical_housing_test_fixture.py']:
        if (ROOT/'tools'/name).exists():paths.add(ROOT/'tools'/name)
    def hashes():return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    before=hashes()
    command=[sys.executable,'-B','-m','unittest',*MODULES,'-v']
    run=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf8',errors='replace')
    unchanged=before==hashes()
    report={'requirements':['CON-ARCH-006','OPS-ARCH-006'],'command':command,
        'status':'pass' if run.returncode==0 and unchanged else 'failed',
        'exit_code':run.returncode,'sources_unchanged':unchanged,'source_sha256':before,
        'stdout':run.stdout,'stderr':run.stderr,'physical_qualified':False,
        'scope':'Local geometry/publication mutation tests plus baseline r5 legacy unit regressions; actual new STEP/mesh/native evidence is separate.'}
    folder=ROOT/'docs/reports/local-covers-20260910';folder.mkdir(parents=True,exist_ok=True)
    (folder/'regressions.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'status':report['status'],'result':run.stderr[-1300:]}))
    return report['status']!='pass'


if __name__=='__main__':raise SystemExit(main())
