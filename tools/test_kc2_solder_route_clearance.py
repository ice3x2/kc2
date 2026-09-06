"""CON-ARCH-004 AC-3/4/8/10: fresh DRC on enlarged solder lands."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = Path('C:/Program Files/KiCad/10.0/bin/kicad-cli.exe')


class SolderRouteClearance(unittest.TestCase):
    def test_both_boards_fresh_drc(self):
        for side in ('left', 'right'):
            with self.subTest(side=side):
                board = ROOT / f'hardware/kicad/kc2_{side}/kc2_{side}.kicad_pcb'
                report = ROOT / f'.codex-tmp/{side}-solder-route-regression.drc.json'
                result = subprocess.run([str(CLI), 'pcb', 'drc', '--format', 'json',
                    '--refill-zones', '--all-track-errors', '-o', str(report), str(board)],
                    capture_output=True, text=True, encoding='utf-8', errors='replace')
                self.assertIn(result.returncode, (0, 5), result.stderr)
                data = json.loads(report.read_text(encoding='utf-8'))
                errors = [v for v in data['violations'] if v['severity'] == 'error']
                self.assertEqual([], errors)
                self.assertEqual([], data['violations'], 'Warnings/exclusions require review; do not silently ignore them')
                self.assertEqual([], data['unconnected_items'])


if __name__ == '__main__':
    unittest.main()
