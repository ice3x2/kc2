"""OPS-ARCH-007: Git must not normalize source-bound release bytes."""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class GitReleaseBytesTests(unittest.TestCase):
    def test_local_scratch_and_backups_are_ignored(self):
        for path in ('.codex-tmp/probe', 'hardware/kicad/kc2_left/probe.kicad_pcb.bak-20260907',
                     'hardware/kicad/kc2_left/.history/probe'):
            self.assertEqual(0, subprocess.run(['git', 'check-ignore', '-q', path],
                                              cwd=ROOT).returncode, path)

    def test_git_filter_preserves_current_board_bytes(self):
        path = 'hardware/kicad/kc2_left/kc2_left.kicad_pcb'
        def git(*args):
            return subprocess.check_output(['git', *args], cwd=ROOT).strip()
        self.assertEqual(git('hash-object', '--no-filters', path),
                         git('hash-object', '--path=' + path, path))


if __name__ == '__main__':
    unittest.main()
