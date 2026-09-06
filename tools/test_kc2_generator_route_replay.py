"""CON-ARCH-004: reconstruct the reviewed routing from fresh generator output."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import pcbnew
from tools import kc2_solder_route_snapshot as snapshot

ROOT=Path(__file__).resolve().parents[1]


class GeneratorRouteReplay(unittest.TestCase):
    def test_fresh_generator_replays_reviewed_routes(self):
        target=Path(tempfile.mkdtemp(prefix='generator-route-replay-',dir=ROOT/'.codex-tmp'))
        result=subprocess.run([sys.executable,'-B','-m','tools.generate_kc2_pcbs',
            '--variant','x3-v2','--output-dir',str(target)],cwd=ROOT,capture_output=True)
        self.assertEqual(0,result.returncode,result.stderr)
        saved=json.loads(snapshot.DEFAULT.read_text(encoding='utf-8'))
        for side in ('left','right'):
            with self.subTest(side=side):
                path=target/f'kc2_{side}/kc2_{side}.kicad_pcb'
                board=pcbnew.LoadBoard(str(path))
                expected=saved['sides'][side]
                self.assertEqual(expected['pad_fingerprint_sha256'],snapshot.pad_fingerprint(board))
                snapshot.restore(board,expected)
                self.assertEqual(expected,snapshot.capture(board))
                pcbnew.SaveBoard(str(path),board)
                report=target/f'{side}.drc.json'
                result=subprocess.run(['C:/Program Files/KiCad/10.0/bin/kicad-cli.exe','pcb','drc',
                    '--format','json','--refill-zones','--all-track-errors','-o',str(report),str(path)],capture_output=True)
                self.assertIn(result.returncode,(0,5),result.stderr)
                drc=json.loads(report.read_text(encoding='utf-8'))
                self.assertEqual([],drc['violations'])
                self.assertEqual([],drc['unconnected_items'])


if __name__=='__main__':
    unittest.main()
