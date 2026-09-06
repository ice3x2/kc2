"""OPS-ARCH-007 AC-1/3: bound machine failures cannot be human-checkbox passes."""
import copy
import json
import unittest

from tools import test_prepare_kc2_first_order as fixtures
from tools import prepare_kc2_first_order as release


class MachineReviewSemantics(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.FirstOrderGate()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root, self.evidence = self.fixture.root, self.fixture.evidence
        self.reports = {}
        for role, filename in [('board', 'kc2-first-order-digital-checks-2026-09-06.json'),
                               ('housing', 'kc2-first-order-housing-digital-2026-09-06.json')]:
            self.reports[role] = json.loads((fixtures.ROOT / 'docs/reports' / filename).read_text())
            if role=='housing':
                # Historical machine file supplies non-floor fields only; synthetic
                # current contract is not real physical or geometry qualification.
                self.reports[role]['closed_floor']={'digital_valid':True,'errors':[],
                    'floor_thickness_mm':1.2,'floor_top_z_mm':-1.0,'floor_bottom_z_mm':-2.2,
                    'bonding_pad_diameter_mm':8,'bonding_pad_count':12,'printable_part_count':3}
            self.reports[role]['source_sha256'] = {
                rel: self.evidence['bindings'][rel] for rel in release.digital_report_inputs(role)}
            self.save(role)

    def test_physical_pending_does_not_fail_valid_machine_reports(self):
        result = release.validate(self.evidence, self.root)
        self.assertEqual([], result['errors'])
        self.assertTrue(result['eligible_to_build'])
        self.assertFalse(result['physical_qualification_complete'])

    def test_missing_wrong_typed_or_stale_report_fails(self):
        for role in ('board', 'housing'):
            for mutation in ('requirement', 'source_sha256', 'errors'):
                with self.subTest(role=role, mutation=mutation):
                    original = copy.deepcopy(self.reports[role])
                    self.reports[role].pop(mutation)
                    self.save(role)
                    self.assertFalse(release.validate(self.evidence, self.root)['eligible_to_build'])
                    self.reports[role] = original
                    self.save(role)

    def save(self, role):
        rel = self.evidence['digital_reports'][role]
        path = self.root / rel
        path.write_text(json.dumps(self.reports[role]), encoding='utf-8')
        self.evidence['bindings'][rel] = release.sha256(path)
        if rel not in self.evidence['reviews']['digital_verification']:
            self.evidence['reviews']['digital_verification'].append(rel)

    def test_rebound_failed_housing_report_is_not_overridden_by_checkboxes(self):
        self.reports['housing']['digital_valid'] = False
        self.reports['housing']['errors'] = ['Synthetic known socket/upper solid interference']
        self.save('housing')
        self.assertFalse(release.validate(self.evidence, self.root)['eligible_to_build'])

    def test_rebound_native_archive_failure_blocks(self):
        self.reports['housing']['native_archive_blockers'] = ['Synthetic reopened body count mismatch']
        self.save('housing')
        self.assertFalse(release.validate(self.evidence, self.root)['eligible_to_build'])

    def test_nested_board_error_is_not_hidden_by_empty_summary(self):
        self.reports['board']['boards']['left']['controller_contract_errors'] = ['Synthetic wrong B+ pin']
        self.save('board')
        self.assertFalse(release.validate(self.evidence, self.root)['eligible_to_build'])

    def test_current_source_hash_does_not_refresh_stale_machine_provenance(self):
        rel = 'hardware/case/kc2_mx_upper_housing_manifest.json'
        (self.root / rel).write_text('Synthetic changed upper geometry manifest', encoding='utf-8')
        self.evidence['bindings'][rel] = release.sha256(self.root / rel)
        result = release.validate(self.evidence, self.root)
        self.assertFalse(result['eligible_to_build'])
        self.assertTrue(any('stale/missing machine report source' in e for e in result['errors']))

    def test_untyped_or_substituted_human_review_cannot_replace_machine_record(self):
        for role in ('board', 'housing'):
            original = self.evidence['digital_reports'][role]
            self.evidence['digital_reports'][role] = 'review.txt'
            self.assertFalse(release.validate(self.evidence, self.root)['eligible_to_build'])
            self.evidence['digital_reports'][role] = original

    def test_missing_machine_roles_and_malformed_machine_payload_fail_closed(self):
        candidate = copy.deepcopy(self.evidence)
        candidate.pop('digital_reports')
        self.assertFalse(release.validate(candidate, self.root)['eligible_to_build'])
        self.reports['housing'] = []
        self.save('housing')
        self.assertFalse(release.validate(self.evidence, self.root)['eligible_to_build'])


if __name__ == '__main__':
    unittest.main()
