"""CON-ARCH-006/OPS-ARCH-007 closed-floor release contract."""
import unittest
import copy
import json
from tools import prepare_kc2_first_order as release


class SolidFloorReleaseTests(unittest.TestCase):
    def test_both_floor_bonding_drawings_are_required_source_inputs(self):
        paths=release.digital_report_inputs('housing')
        for side in ('left','right'):
            self.assertIn(f'hardware/case/kc2_{side}_silicone_foot_layout.svg',paths)

    def test_legacy_no_floor_housing_report_fails_even_with_fresh_bindings(self):
        from tools.test_prepare_kc2_first_order import FirstOrderGate
        fixture=FirstOrderGate();fixture.setUp();self.addCleanup(fixture.doCleanups)
        path=fixture.root/fixture.evidence['digital_reports']['housing']
        report=json.loads(path.read_text());report.pop('closed_floor',None)
        path.write_text(json.dumps(report))
        fixture.evidence['bindings'][str(path.relative_to(fixture.root))]=release.sha256(path)
        self.assertTrue(release.inspect_digital_reports(fixture.evidence,fixture.root))

    def test_closed_floor_semantics_fail_closed_on_changed_dimensions_or_errors(self):
        from tools.test_prepare_kc2_first_order import FirstOrderGate
        fixture=FirstOrderGate();fixture.setUp();self.addCleanup(fixture.doCleanups)
        path=fixture.root/fixture.evidence['digital_reports']['housing']
        original=json.loads(path.read_text())
        self.assertEqual(release.inspect_digital_reports(fixture.evidence,fixture.root),[])
        for key,value in [('floor_thickness_mm',0),('floor_top_z_mm',0),('floor_bottom_z_mm',-1.2),
                          ('bonding_pad_count',0),('printable_part_count',2),('digital_valid',False),
                          ('errors',['floor has through-holes'])]:
            report=copy.deepcopy(original);report['closed_floor'][key]=value
            path.write_text(json.dumps(report))
            fixture.evidence['bindings'][str(path.relative_to(fixture.root))]=release.sha256(path)
            self.assertTrue(release.inspect_digital_reports(fixture.evidence,fixture.root),key)

    def test_new_output_identity_reuses_exact_reviewed_pcb_raw(self):
        self.assertEqual(release.DEFAULT_OUTPUT.name,'solid-floor-20260907-r4')
        self.assertEqual(release.RAW,'hardware/kicad/fabrication_review/v1-recess-20260906-r3')

    def test_bom_identifies_closed_floor_and_unqualified_feet(self):
        board=release.parse_board(release.ROOT/'hardware/kicad/kc2_left/kc2_left.kicad_pcb')
        bom=release.manual_bom(board,'left')
        self.assertEqual(bom['closed_floor']['thickness_mm'],1.2)
        self.assertEqual(bom['closed_floor']['top_z_mm'],-1)
        self.assertEqual(bom['closed_floor']['bottom_z_mm'],-2.2)
        self.assertEqual(bom['closed_floor']['maximum_under_pcb_projection_mm'],2.9)
        self.assertIn('7.5 mm',bom['fasteners'])
        self.assertEqual(bom['silicone_feet']['total_keyboard_quantity'],12)
        self.assertEqual(bom['silicone_feet']['bonding_diameter_mm'],8)
        self.assertFalse(bom['silicone_feet']['physical_qualification_complete'])


if __name__=='__main__':unittest.main()
