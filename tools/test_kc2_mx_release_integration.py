"""CON-ARCH-004 AC-9: legacy raw scan cannot qualify selected receptacles."""
import unittest
from unittest.mock import patch
from tools.verify_kc2_x3_v2 import _physical_scan_metrics


class MXReleaseIntegrationTests(unittest.TestCase):
    def run_binding(self, mutate=None, mutate_documents=None):
        documents = {
            'mx_socket_specification': {'path': 'evidence/socket.pdf'},
            'mx_switch_specification': {'path': 'evidence/switch.pdf', 'part_number': 'MX1A-11NW'},
            'mx_contact_limits': {'path': 'evidence/limits.pdf'},
        }
        qualification = dict(socket_specification='evidence/socket.pdf',
            switch_specification='evidence/switch.pdf', limits_source_artifact='evidence/limits.pdf',
            coupon_id='coupon-2026-09', switch_mpn='MX1A-11NW')
        data = dict(coupon_id='coupon-2026-09', records=None, switch_fit_records=[],
                    keycap_fit_records=[], diode_records=[], mx_receptacle_qualification=qualification,
                    mx_receptacle_documents=documents)
        if mutate:
            mutate(qualification)
        if mutate_documents:
            mutate_documents(documents)
        # Isolate integration binding from independently tested file/hash/contact validation.
        with patch('tools.verify_kc2_x3_v2._validate_document_set', return_value=(documents, [])), patch(
            'tools.verify_kc2_mx_receptacle_evidence.verify_mx_receptacle_evidence', return_value=[]):
            return _physical_scan_metrics(data, controller_identity={'mx_switch_mpn': 'MX1A-11NW'})[1]

    def test_matching_bindings_do_not_raise_binding_error(self):
        self.assertFalse(any('binding' in error for error in self.run_binding()))

    def test_semantic_document_swap_is_rejected(self):
        errors = self.run_binding(lambda q: q.update(socket_specification='evidence/switch.pdf'))
        self.assertTrue(any('socket_specification binding' in error for error in errors))

    def test_unrelated_coupon_is_rejected(self):
        errors = self.run_binding(lambda q: q.update(coupon_id='other-coupon'))
        self.assertTrue(any('coupon identity binding' in error for error in errors))

    def test_different_switch_is_rejected(self):
        errors = self.run_binding(lambda q: q.update(switch_mpn='OTHER-MX'))
        self.assertTrue(any('switch identity binding' in error for error in errors))

    def test_wrong_document_switch_identity_is_rejected(self):
        errors = self.run_binding(mutate_documents=lambda d: d['mx_switch_specification'].update(part_number='OTHER-MX'))
        self.assertTrue(any('switch identity binding' in error for error in errors))

    def test_legacy_raw_schema_does_not_bypass_contact_gate(self):
        data = dict(coupon_id='coupon-2026-09', records=[], switch_fit_records=[],
                    keycap_fit_records=[], diode_records=[])
        metrics, errors, _ = _physical_scan_metrics(data, controller_identity={})
        self.assertTrue(any('MX receptacle' in error for error in errors))
        self.assertIn('mx_receptacle_with_plate', metrics['assembly_modes'])


if __name__ == '__main__':
    unittest.main()
