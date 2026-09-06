"""CON-ARCH-004 AC-3/10: expose and enlarge controller/MX solder lands."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import sys

import pcbnew
from tools import generate_kc2_pcbs as generator
from tools.verify_kc2_x3_v2 import verify_v2_footprint, controller_power_geometry_report

ROOT = Path(__file__).resolve().parents[1]


class HandSolderPadTests(unittest.TestCase):
    def test_partial_mask_coverage_is_rejected(self):
        board = pcbnew.BOARD()
        fp, _, _ = generator.create_controller(board, {}, 'U1', 100, 50, 1, {}, 'x3-v2')
        pad = list(fp.Pads())[0]
        pad.SetLocalSolderMaskMargin(pcbnew.FromMM(-.05))
        with self.assertRaises(AssertionError):
            self.assert_land(pad, (1.8, 2.4), .95)

    def test_reset_clearance_contract_tracks_transverse_land_growth(self):
        # CON-ARCH-007 AC-7: same centers, 0.30 mm additional exposed copper.
        self.assertAlmostEqual(generator.X3_V2_RESET_COURTYARD_TO_U1_SOCKET_COPPER_MIN_MM,
                               2.03 - (2.4 - 1.8) / 2, places=6)

    def test_nominal_battery_gap_uses_enlarged_controller_lands(self):
        # CON-ARCH-007 AC-2 nominal plan gap, not physical insulation approval.
        for side in ('left', 'right'):
            board = pcbnew.LoadBoard(str(ROOT/f'hardware/kicad/kc2_{side}/kc2_{side}.kicad_pcb'))
            report = controller_power_geometry_report(board, side)
            self.assertAlmostEqual(report['battery_to_socket_pad_copper_mm'], .42, places=3)
            self.assertFalse(any('battery socket-pad clearance' in e for e in report['errors']))

    def test_saved_controller_masks_in_fresh_process(self):
        code = """import pcbnew
from pathlib import Path
for side in ('left', 'right'):
    board = pcbnew.LoadBoard(str(Path('hardware/kicad')/('kc2_'+side)/('kc2_'+side+'.kicad_pcb')))
    for pad in board.FindFootprintByReference('U1').Pads():
        assert pad.GetLayerSet().Contains(pcbnew.F_Mask), (side, pad.GetNumber(), 'F.Mask')
        assert pad.GetLayerSet().Contains(pcbnew.B_Mask), (side, pad.GetNumber(), 'B.Mask')
"""
        result = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_generator_does_not_mutate_global_copper_layer_set(self):
        code = """import pcbnew
from tools import generate_kc2_pcbs as generator
before = pcbnew.LSET.AllCuMask().FmtHex()
generator.create_controller(pcbnew.BOARD(), {}, 'U1', 100, 50, 1, {}, 'x3-v2')
assert pcbnew.LSET.AllCuMask().FmtHex() == before
"""
        result = subprocess.run([sys.executable, '-B', '-c', code], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_release_gate_rejects_regressed_mx_land_contract(self):
        # CON-ARCH-004 AC-3: a library and board changing together must not
        # bypass an independent dimensional/mask requirement check.
        source = ROOT/'third_party/kc2.pretty/SW_Choc_V2_Socket_MX_THT.kicad_mod'
        original = source.read_text(encoding='utf-8')
        self.assertEqual(verify_v2_footprint(source), [])
        mutations = [
            original.replace('(size 2.5 3.2)', '(size 2.5 2.5)'),
            original.replace('(drill 1.6)', '(drill 1.5)'),
            original.replace('thru_hole oval', 'thru_hole rect'),
            original.replace('(layers "*.Cu" "*.Mask")', '(layers "*.Cu")'),
        ]
        with TemporaryDirectory() as directory:
            candidate = Path(directory)/source.name
            for mutation in mutations:
                self.assertNotEqual(mutation, original)
                candidate.write_text(mutation, encoding='utf-8')
                self.assertTrue(any('MX solder land' in error for error in verify_v2_footprint(candidate)))

    def assert_land(self, pad, size, drill):
        self.assertEqual(tuple(round(pcbnew.ToMM(v), 3) for v in (pad.GetSize().x, pad.GetSize().y)), size)
        self.assertEqual(pad.GetShape(), pcbnew.PAD_SHAPE_OVAL)
        self.assertAlmostEqual(pcbnew.ToMM(pad.GetDrillSize().x), drill)
        for layer in (pcbnew.F_Mask, pcbnew.B_Mask):
            self.assertTrue(pad.GetLayerSet().Contains(layer), f'{pad.GetNumber()}: solder land is masked')
            self.assertEqual(pad.GetSolderMaskExpansion(layer), 0, 'nominal full-land mask opening required')
        for layer in (pcbnew.F_Paste, pcbnew.B_Paste):
            self.assertFalse(pad.GetLayerSet().Contains(layer))

    def test_controller_generator_retains_exposed_oval_lands(self):
        for direction in (1, -1):
            board = pcbnew.BOARD()
            fp, _, _ = generator.create_controller(board, {}, 'U1', 100, 50, direction, {}, 'x3-v2')
            self.assertEqual(len(list(fp.Pads())), 24)
            for pad in fp.Pads():
                self.assert_land(pad, (1.8, 2.4), 0.95)

    def test_controller_libraries_and_placed_boards(self):
        for side in ('left', 'right'):
            name = f'NiceNanoV2_Socket_24Pin_USB_OUT_{side.upper()}'
            source = pcbnew.FootprintLoad(str(ROOT/'third_party/kc2.pretty'), name)
            board = pcbnew.LoadBoard(str(ROOT/f'hardware/kicad/kc2_{side}/kc2_{side}.kicad_pcb'))
            for fp in (source, board.FindFootprintByReference('U1')):
                for pad in fp.Pads():
                    self.assert_land(pad, (1.8, 2.4), 0.95)

    def test_switch_library_and_all_seventy_positions(self):
        source = pcbnew.FootprintLoad(str(ROOT/'third_party/kc2.pretty'), 'SW_Choc_V2_Socket_MX_THT')
        footprints = [source]
        for side, count in (('left', 31), ('right', 39)):
            board = pcbnew.LoadBoard(str(ROOT/f'hardware/kicad/kc2_{side}/kc2_{side}.kicad_pcb'))
            switches = [fp for fp in board.GetFootprints() if fp.GetReference().startswith('SW') and fp.GetReference()[2:].isdigit()]
            self.assertEqual(len(switches), count)
            footprints.extend(switches)
        for fp in footprints:
            pads = [p for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
            self.assertEqual(len(pads), 2)
            for pad in pads:
                self.assert_land(pad, (2.5, 3.2), 1.6)
            # The duplicate-number Choc SMD contacts must not grow or acquire drills.
            for pad in fp.Pads():
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                    self.assertEqual(tuple(round(pcbnew.ToMM(v), 3) for v in (pad.GetSize().x, pad.GetSize().y)), (2.6, 2.6))


if __name__ == '__main__':
    unittest.main()
