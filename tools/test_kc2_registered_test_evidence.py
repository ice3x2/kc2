"""OPS-ARCH-006 final executed regression evidence must not be fabricated."""
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from tools import kc2_registered_test_evidence as t

class EvidenceTests(unittest.TestCase):
    def test_receiver_and_component_regressions_are_mandatory_without_report_hints(self):
        required = {'tools.' + name for name in (
            'test_kc2_solid_clearance', 'test_kc2_component_local_certificate',
            'test_kc2_lower_predicate_bundle', 'test_kc2_receiver_cleanup',
            'test_kc2_receiver_snapshot',
            'test_kc2_receiver_bundle_transfer',
            'test_kc2_lower_strata', 'test_kc2_magnetic_subset',
            'test_kc2_lower_strata_bundle',
            'test_kc2_floor_capture_gate','test_kc2_registered_void_proof',
            'test_review_kc2_right_lower_native','test_kc2_stl_zero_area_filter',
            'test_kc2_left_central_relief','test_stage_kc2_left_central_relief',
            'test_review_kc2_left_central_voids',
            'test_kc2_step_whitespace','test_kc2_registered_step_publication',
            'test_review_kc2_receiver_cleanup', 'test_kc2_receiver_void_transfer',
            'test_kc2_floor_capture', 'test_review_kc2_floor_receiver',
            'test_diagnose_kc2_receiver_floor_prism')}
        self.assertTrue(required.issubset(t.selected_modules({})))

    def test_requires_real_successful_unittest_summary(self):
        self.assertEqual(t.execution_result(0,'','Ran 41 tests in 0.4s\n\nOK\n'),41)
        for code,log in [(1,'Ran 41 tests in 0.4s\nFAILED'),(0,'OK'),(0,'Ran 41 tests in 0.4s\nOK (skipped=1)')]:
            with self.assertRaises(ValueError):t.execution_result(code,'',log)
    def test_failed_missing_or_changed_tests_block(self):
        row=dict(status='pass',errors=[],returncode=0,stdout='',stderr='Ran 2 tests in 0.1s\n\nOK\n',tests_run=2,
            test_modules=['tools.test_a'],source_sha256={'tools/test_a.py':'a'*64,'r.json':'b'*64},report_sha256={'r.json':'b'*64})
        t.check_evidence(row,['tools.test_a'],{'r.json':'b'*64})
        with self.assertRaises(ValueError):t.check_evidence(row,['tools.test_a','tools.test_b'],{'r.json':'b'*64})
        with self.assertRaises(ValueError):t.check_evidence(row,['tools.test_a'],{'r.json':'c'*64})
    def test_collector_executes_real_subprocess_and_detects_source_change(self):
        for mutate in (None,'publish_kc2_registered_housings.py','kc2_step_whitespace.py'):
            with self.subTest(mutate=mutate),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/'tools').mkdir();(root/t.STAGE).mkdir(parents=True)
                (root/'report.json').write_text(json.dumps(dict(status='pass',errors=[],source_sha256={})))
                for name in ('kc2_registered_test_evidence.py','publish_kc2_registered_housings.py','kc2_registered_release_gate.py','kc2_step_whitespace.py'):
                    (root/'tools'/name).write_text('# frozen fixture\n')
                action="Path('tools/"+mutate+"').write_text('changed')" if mutate else 'self.assertEqual(1,1)'
                (root/'test_fixture.py').write_text('import unittest\nfrom pathlib import Path\nclass Test(unittest.TestCase):\n def test_one(self): '+action+'\n')
                with patch('tools.publish_kc2_registered_housings.report_paths',return_value={'actual':'report.json'}),patch('tools.publish_kc2_registered_housings.PUBLICATION_DOCS',{}),patch.object(t,'selected_modules',return_value=['test_fixture']):
                    result=t.collect(root)
                self.assertEqual(result['tests_run'],1)
                self.assertEqual(result['status'],'fail' if mutate else 'pass')

if __name__=='__main__':unittest.main()
