"""CON-ARCH-004 AC-3/7: dimensional selected MX assembly in regenerated metadata."""
import unittest
from tools import generate_kc2_pcbs as generator


class MXManifestContractTests(unittest.TestCase):
    def test_revised_board_warning_includes_selected_socket_plate_dependency(self):
        from tools.verify_kc2_x3_v2 import has_v2_mx_assembly_warning
        self.assertTrue(has_v2_mx_assembly_warning([
            'X3 V2: Choc V1+ring / V2 socket OR MX direct solder / receptacles+plate; contact qualification pending']))
        self.assertFalse(has_v2_mx_assembly_warning(['Choc V1 unsupported']))

    def test_incremental_manifest_preserves_historical_route_provenance(self):
        from tools.refresh_kc2_mx_revision_manifest import build_manifest
        from tools.verify_kc2_x3_v2 import verify_mx_revision_metadata
        manifest = build_manifest()
        self.assertEqual(verify_mx_revision_metadata(manifest), [])
        self.assertEqual(manifest['canonical_route_evidence_role'], 'historical_pre_mx_revision_base_only')
        self.assertEqual(manifest['selected_switch_assembly'], 'mx_receptacle_with_plate')
        self.assertEqual(manifest['mx_solder_route_replay']['path'], 'hardware/kicad/autoroute/kc2_mx_solder_support_routes.json')
        self.assertEqual(manifest['canonical_route_evidence']['left']['final_track_via_count'], 616)
        self.assertEqual(manifest['controller_service_region']['battery']['socket_pad_clearance_mm'], .42)
        manifest['mx_revision']['source_board_sha256']['left'] = '0'*64
        self.assertTrue(verify_mx_revision_metadata(manifest))
        manifest = build_manifest()
        manifest['mx_revision']['pcb_generator_sha256'] = '0'*64
        self.assertTrue(verify_mx_revision_metadata(manifest))

    def test_release_rejects_legacy_or_changed_dimensional_selection(self):
        from tools.verify_kc2_x3_v2 import verify_mx_assembly_manifest
        contract = generator.x3_v2_switch_assembly_contract()
        self.assertEqual(verify_mx_assembly_manifest(contract), [])
        self.assertTrue(verify_mx_assembly_manifest({'selected_switch_assembly': 'mx_direct_solder'}))
        contract['mx_receptacle']['nominal_dimensions_mm']['barrel_od'] = 1.5
        self.assertTrue(verify_mx_assembly_manifest(contract))

    def test_selected_assembly_and_dimension_contract(self):
        contract = generator.x3_v2_switch_assembly_contract()
        self.assertEqual(contract['selected_switch_assembly'], 'mx_receptacle_with_plate')
        self.assertEqual(contract['assembly_modes'], ['choc_v1_bottom_socket_with_ring', 'choc_v2_bottom_socket', 'mx_5pin_top_direct_solder', 'mx_receptacle_with_plate'])
        self.assertTrue(contract['assembly_modes_mutually_exclusive'])
        self.assertEqual(contract['unsupported_switch_geometry'], ['choc_v2_direct_solder', 'one_piece_mx_smd_socket'])
        socket = contract['mx_receptacle']
        self.assertEqual(socket['nominal_dimensions_mm'], dict(length=3.0, barrel_od=1.45, flange_od=2.0, flange_thickness=.2))
        self.assertTrue(socket['open_bottom'])
        self.assertEqual(socket['count_per_switch'], 2)
        self.assertTrue(socket['plate_lid_required'])
        self.assertEqual(socket['qualification_status'], 'pending')
        self.assertFalse(socket['production_hole_fit_confirmed'])


if __name__ == '__main__':
    unittest.main()
