"""CON-ARCH-004/006: replay routing without altering pad/part identity."""
import json
from pathlib import Path
import unittest
import pcbnew
from tools import kc2_solder_route_snapshot as snapshot

ROOT=Path(__file__).resolve().parents[1]


class RouteReplay(unittest.TestCase):
    def synthetic_board(self):
        board=pcbnew.BOARD()
        footprint=pcbnew.FOOTPRINT(board)
        footprint.SetReference('U1')
        pad=pcbnew.PAD(footprint)
        pad.SetNumber('1')
        pad.SetSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.8),pcbnew.FromMM(2.4)))
        footprint.Add(pad)
        board.Add(footprint)
        return board,footprint,pad

    def test_fingerprint_detects_local_and_inherited_mask_expansion(self):
        for source in ('pad','footprint','board'):
            with self.subTest(source=source):
                board,footprint,pad=self.synthetic_board()
                before=snapshot.pad_fingerprint(board)
                if source=='pad':
                    pad.SetLocalSolderMaskMargin(pcbnew.FromMM(-.5))
                elif source=='footprint':
                    footprint.SetLocalSolderMaskMargin(pcbnew.FromMM(.1))
                else:
                    board.GetDesignSettings().m_SolderMaskExpansion=pcbnew.FromMM(.07)
                self.assertNotEqual(before,snapshot.pad_fingerprint(board))

    def test_capture_refuses_arc_instead_of_flattening_it(self):
        board=pcbnew.BOARD()
        board.Add(pcbnew.PCB_ARC(board))
        with self.assertRaisesRegex(ValueError,'unsupported.*PCB_ARC'):
            snapshot.capture(board)

    def test_restore_refuses_unsupported_kind_before_deleting_tracks(self):
        board=pcbnew.BOARD()
        board.Add(pcbnew.PCB_TRACK(board))
        captured=snapshot.capture(board)
        captured['tracks'][0]['kind']='arc'
        with self.assertRaisesRegex(ValueError,'unsupported.*arc'):
            snapshot.restore(board,captured)
        self.assertEqual(len(list(board.GetTracks())),1)

    def test_restore_refuses_existing_arc_before_deleting_it(self):
        board=pcbnew.BOARD()
        captured=snapshot.capture(board)
        board.Add(pcbnew.PCB_ARC(board))
        with self.assertRaisesRegex(ValueError,'unsupported.*PCB_ARC'):
            snapshot.restore(board,captured)
        self.assertEqual(len(list(board.GetTracks())),1)

    def test_saved_snapshot_matches_canonical_boards(self):
        saved=json.loads(snapshot.DEFAULT.read_text(encoding='utf-8'))
        self.assertEqual(saved['schema'],snapshot.SCHEMA)
        self.assertFalse(saved['order_ready'])
        for side in ('left','right'):
            board=pcbnew.LoadBoard(str(ROOT/f'hardware/kicad/kc2_{side}/kc2_{side}.kicad_pcb'))
            self.assertEqual(saved['sides'][side],snapshot.capture(board))

    def test_round_trip_both_halves(self):
        for side in ('left','right'):
            board=pcbnew.LoadBoard(str(ROOT/f'hardware/kicad/kc2_{side}/kc2_{side}.kicad_pcb'))
            captured=snapshot.capture(board)
            for t in list(board.GetTracks()):
                board.Delete(t)
            snapshot.restore(board,captured)
            self.assertEqual(captured,snapshot.capture(board))

    def test_rejects_changed_physical_pad_before_mutation(self):
        board=pcbnew.LoadBoard(str(ROOT/'hardware/kicad/kc2_left/kc2_left.kicad_pcb'))
        captured=snapshot.capture(board)
        before=len(list(board.GetTracks()))
        captured['pad_fingerprint_sha256']='bad'
        with self.assertRaisesRegex(ValueError,'pad fingerprint'):
            snapshot.restore(board,captured)
        self.assertEqual(before,len(list(board.GetTracks())))


if __name__=='__main__':
    unittest.main()
