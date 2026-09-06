"""CON-ARCH-004/006: PCB success cannot waive the selected lid/native gates."""
import unittest
from unittest.mock import patch

from tools.verify_kc2_x3_v2 import selected_mx_housing_readiness_blockers
from tools.verify_kc2_x3_v2 import (
    controller_service_order_readiness_blockers, verify_physical_evidence_manifest,
    PHYSICAL_EVIDENCE_BUNDLES, PHYSICAL_EVIDENCE_REQUIREMENT_IDS, MX_HOUSING_SOURCE_PATHS,
)


class MXHousingReleaseIntegrationTests(unittest.TestCase):
    def report(self, **changes):
        result = dict(requirement='CON-ARCH-006', digital_valid=True, errors=[],
                      qualification_blockers=[], native_archive_blockers=[],
                      order_ready=False, print_ready=False)
        result.update(changes)
        return result

    def check(self, report):
        with patch('tools.verify_kc2_x3_v2._analyze_selected_mx_housing_contract', return_value=report):
            return selected_mx_housing_readiness_blockers()

    def test_missing_upper_or_native_evidence_cannot_pass(self):
        for changes in (
            dict(digital_valid=False, errors=['missing upper manifest']),
            dict(native_archive_blockers=['missing right MX F3D']),
            dict(qualification_blockers=['long screw not qualified']),
        ):
            self.assertTrue(self.check(self.report(**changes)))

    def test_malformed_helper_result_fails_closed(self):
        for report in (None, {}, self.report(digital_valid=False), self.report(errors='not a list')):
            self.assertTrue(self.check(report))

    def test_complete_independently_verified_contract_adds_no_blocker(self):
        self.assertEqual([], self.check(self.report()))

    def test_missing_helper_dependency_fails_closed(self):
        with patch('tools.verify_kc2_x3_v2._analyze_selected_mx_housing_contract', side_effect=ImportError('missing dependency')):
            self.assertTrue(selected_mx_housing_readiness_blockers())

    def test_legacy_physical_pass_cannot_waive_selected_upper(self):
        manifest = dict(selected_switch_assembly='mx_receptacle_with_plate',
                        controller_service_region={'order_ready':False},
                        physical_scan_validation={'orderable':False})
        with patch('tools.verify_kc2_x3_v2.verify_physical_evidence_manifest',
                   return_value={name:[] for name in PHYSICAL_EVIDENCE_BUNDLES}), patch(
                   'tools.verify_kc2_x3_v2._analyze_selected_mx_housing_contract',
                   return_value=self.report(native_archive_blockers=['missing required native archive'])):
            blockers=controller_service_order_readiness_blockers(manifest, {})
        self.assertTrue(any('missing required native archive' in error for error in blockers))

    def test_physical_bindings_must_include_upper_and_all_native_outputs(self):
        old_names=('left_board','right_board','generation_manifest','housing_manifest',
                   'fabrication_manifest','mechanical_manifest','render_manifest',
                   'outline_report','firmware_build_evidence')
        evidence=dict(schema='kc2-x3-v2-physical-evidence-v1', variant='x3-v2',
                      requirement_ids=PHYSICAL_EVIDENCE_REQUIREMENT_IDS,
                      status='passed',order_ready=True,
                      source_bindings={name:{} for name in old_names}, bundles={})
        errors=verify_physical_evidence_manifest(evidence)
        self.assertTrue(all('source bindings are incomplete' in items for items in errors.values()))
        self.assertEqual(len(MX_HOUSING_SOURCE_PATHS),6)
        self.assertEqual(sum(path.suffix=='.f3d' for path in MX_HOUSING_SOURCE_PATHS.values()),4)


if __name__ == '__main__':
    unittest.main()
