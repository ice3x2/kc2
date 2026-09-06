"""CON-ARCH-004/006: current routing must bind to replay, not old SES counts."""
import copy
import unittest
from pathlib import Path
import pcbnew
from tools.canonical_hash import sha256_file

ROOT = Path(__file__).resolve().parents[1]


class MXRouteBindingTests(unittest.TestCase):
    def test_exact_replay_and_reject_changed_manifest_or_route(self):
        from tools.verify_kc2_mx_route_binding import verify_mx_route_binding
        path = 'hardware/kicad/autoroute/kc2_mx_solder_support_routes.json'
        manifest = {'mx_solder_route_replay': {'path': path, 'sha256': sha256_file(ROOT/path)}}
        board = pcbnew.LoadBoard(str(ROOT/'hardware/kicad/kc2_left/kc2_left.kicad_pcb'))
        self.assertEqual(verify_mx_route_binding(manifest, board, 'left'), [])
        stale = copy.deepcopy(manifest)
        stale['mx_solder_route_replay']['sha256'] = '0'*64
        self.assertTrue(verify_mx_route_binding(stale, board, 'left'))
        board.Delete(list(board.GetTracks())[0])
        self.assertTrue(verify_mx_route_binding(manifest, board, 'left'))


if __name__ == '__main__':
    unittest.main()
