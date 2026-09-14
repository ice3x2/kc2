"""CON-ARCH-006 staged profile partition evidence, not CAD publication."""
import hashlib
import io
import json
from pathlib import Path
import unittest
from shapely import wkt
import shapely
from tools.kc2_profile_split import profile_split

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.codex-tmp/registered-housing-fit/ab/profiles'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def collect():
    sources=[ROOT/'tools/kc2_profile_split.py',ROOT/'tools/test_kc2_profile_split.py',Path(__file__)]
    sources.extend(ROOT/f'docs/reports/solid-filled-plates-20260913/right-{k}.json' for k in ['mx','choc_v1','deep_sea'])
    before={p.relative_to(ROOT).as_posix():digest(p) for p in sources}
    STAGE.mkdir(parents=True,exist_ok=True)
    outputs={}
    for kind in ['mx','choc_v1','deep_sea']:
        print('profile partition',kind,flush=True)
        source=ROOT/f'docs/reports/solid-filled-plates-20260913/right-{kind}.json'
        r=json.loads(source.read_text());p={k:wkt.loads(v) for k,v in r['plan_wkt'].items()}
        a,b,report=profile_split(p['domain'],p['openings'],p['service'],r['mounting_centers'])
        report.update(requirements=['CON-ARCH-006'],kind=kind,masks_wkt=[a.wkt,b.wkt],
            source_sha256=before,shapely_version=shapely.__version__,actual_cad_verified=False,
            design_change='Head diameter4.00 vs historical4.50; neck2.00, clearance0.40, nominal capture lip0.60 each side. Receiver ownership rerouted. Physical strength pending.')
        output=STAGE/f'{kind}-split-plan.json'
        output.write_text(json.dumps(report,indent=2)+'\n')
        outputs[output.name]=digest(output)
        print(kind,report['capture_points'],report['clearance_mm'],flush=True)
    stream=io.StringIO()
    suite=unittest.defaultTestLoader.loadTestsFromName('tools.test_kc2_profile_split')
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    if before!={p.relative_to(ROOT).as_posix():digest(p) for p in sources}:raise ValueError('Sources changed during collection')
    final=dict(requirements=['CON-ARCH-006'],status='plan_tests_pass' if result.wasSuccessful() else 'failed',
        tests_run=result.testsRun,families=['mx','choc_v1','deep_sea'],test_output=stream.getvalue(),
        source_sha256=before,outputs=outputs,actual_cad_verified=False,native_verified=False,physical_qualified=False)
    (STAGE/'summary.json').write_text(json.dumps(final,indent=2)+'\n')
    print(json.dumps({k:v for k,v in final.items() if k not in ['source_sha256','test_output']}),flush=True)
    if not result.wasSuccessful():raise SystemExit(1)


if __name__=='__main__':collect()
