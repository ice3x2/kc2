"""CON-ARCH-006 regression runner producing source-bound test evidence."""
from pathlib import Path
import hashlib
import json
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULES = [
    'tools.test_kc2_wrap_wall_plan', 'tools.test_kc2_wrap_partition',
    'tools.test_kc2_stl_tjunction', 'tools.test_kc2_wrap_native',
    'tools.test_review_kc2_wrap_housings', 'tools.test_review_kc2_wrap_native',
    'tools.test_review_kc2_wrap_cad', 'tools.test_publish_kc2_wrap_housings',
    'tools.test_kc2_smooth_central_seam', 'tools.test_publish_kc2_smooth_central_seam',
    'tools.test_kc2_flat_central_native', 'tools.test_kc2_flat_central_revision',
    'tools.test_kc2_magnetic_entry', 'tools.test_kc2_stl_zero_area_filter',
    'tools.test_kc2_wall_engagement_study', 'tools.test_review_kc2_wrap_motion',
    'tools.test_kc2_step_whitespace',
]


if __name__ == '__main__':
    names = [module.replace('.', '/')+'.py' for module in MODULES]
    names += ['tools/run_kc2_wrap_tests.py']
    bindings = {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}
    started = time.monotonic()
    suite = unittest.defaultTestLoader.loadTestsFromNames(MODULES)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    for name, sha in bindings.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != sha:
            raise ValueError('Test source changed during execution: '+name)
    record = dict(status='pass' if result.wasSuccessful() else 'failed',
        requirements=['CON-ARCH-006'], modules=MODULES, tests=result.testsRun,
        failures=len(result.failures), errors=len(result.errors),
        seconds=time.monotonic()-started, source_sha256=bindings, physical_qualified=False)
    target = ROOT/'.codex-tmp/wrap-housing-20260920-r1/tests.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    raise SystemExit(not result.wasSuccessful())
