"""CON-ARCH-004: uncut V1 / MX shared locator candidate regression."""
import unittest
import pcbnew
import tempfile
from tools import update_kc2_v1_locator_slots as subject


class LocatorTests(unittest.TestCase):
    def test_board_geometry_signature_detects_oval_orientation(self):
        from tools.verify_kc2_x3_v2 import normalized_pad_signatures
        fp = pcbnew.FootprintLoad(str(subject.ROOT/'third_party/kc2.pretty'), 'SW_Choc_V2_Socket_MX_THT')
        before=normalized_pad_signatures(fp)
        for p in fp.Pads():
            if p.GetAttribute()==pcbnew.PAD_ATTRIB_PTH and p.GetNumber()=='2':
                p.SetFPRelativeOrientation(pcbnew.EDA_ANGLE(0,pcbnew.DEGREES_T))
        self.assertNotEqual(before, normalized_pad_signatures(fp))

    def test_verifier_rejects_legacy_locator_or_wrong_pad_orientation(self):
        from tools.verify_kc2_x3_v2 import verify_v2_footprint
        source = subject.ROOT/'third_party/kc2.pretty/SW_Choc_V2_Socket_MX_THT.kicad_mod'
        for before, after in (('(at -5.45 0) (size 2.6 2.6) (drill 2.6)', '(at -5.08 0) (size 1.7 1.7) (drill 1.7)'),
                              ('(at -3.81 -2.54 45)', '(at -3.81 -2.54 0)')):
            with tempfile.TemporaryDirectory() as folder:
                mutated = __import__('pathlib').Path(folder)/source.name
                mutated.write_text(source.read_text().replace(before, after))
                self.assertTrue(verify_v2_footprint(mutated))

    def test_owned_library_shared_locator_contract(self):
        fp = pcbnew.FootprintLoad(str(subject.ROOT/'third_party/kc2.pretty'), 'SW_Choc_V2_Socket_MX_THT')
        holes = {(p.GetFPRelativePosition().x/1e6,p.GetFPRelativePosition().y/1e6,p.GetDrillSize().x/1e6)
                 for p in fp.Pads() if p.GetAttribute()==pcbnew.PAD_ATTRIB_NPTH}
        self.assertIn((-5.45,0,2.6), holes)
        self.assertIn((5.45,0,2.6), holes)
        for p in fp.Pads():
            if p.GetAttribute()==pcbnew.PAD_ATTRIB_PTH and p.GetNumber()=='2':
                self.assertAlmostEqual(p.GetFPRelativeOrientation().AsDegrees(),45)

    def test_v1_worst_case_round_clearance(self):
        # V1 diameter+0.10 and each-axis switch±0.10 plus drillposition±0.05;
        # JLC round mechanical hole size-0.08. Assumes centered switch datum.
        for x in (5.5-.15, 5.5+.15):
            for y in (-.15,.15):
                self.assertGreaterEqual(subject.containment_margin(x, y, 1.9,
                                        width=subject.SLOT_WIDTH-.08,
                                        height=subject.SLOT_HEIGHT-.08), .05)

    def test_nominal_both_locator_patterns_are_contained(self):
        for x, diameter in ((5.5, 1.8), (5.08, 1.7)):
            self.assertGreaterEqual(subject.containment_margin(x, 0, diameter), 0)

    def test_canonical_boards_can_be_updated_without_touching_electrical_pads(self):
        for side, count in (("left", 31), ("right", 39)):
            board = pcbnew.LoadBoard(str(subject.ROOT / f"hardware/kicad/kc2_{side}/kc2_{side}.kicad_pcb"))
            before = subject.electrical_signature(board)
            self.assertEqual(subject.update(board), count * 2)
            self.assertEqual(before, subject.electrical_signature(board))
            for fp in board.GetFootprints():
                if str(fp.GetFPID().GetLibItemName()) == 'SW_Choc_V2_Socket_MX_THT':
                    for p in fp.Pads():
                        if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and p.GetNumber() == '2':
                            self.assertAlmostEqual(p.GetFPRelativeOrientation().AsDegrees(), 45)
            self.assertEqual(subject.update(board), count * 2)


if __name__ == "__main__":
    unittest.main()
