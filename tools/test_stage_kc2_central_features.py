"""CON-ARCH-006 candidate feature exports must not replace printable housings."""
import unittest
from pathlib import Path
from tools.stage_kc2_central_features import safe_stage

class StageTests(unittest.TestCase):
    def test_stage_only(self):
        root=Path(__file__).resolve().parents[1]
        self.assertEqual(safe_stage(root/'.codex-tmp/registered-housing-fit/central'),
                         root/'.codex-tmp/registered-housing-fit/central')
        with self.assertRaises(ValueError):safe_stage(root/'hardware/MODELS')

if __name__=='__main__':unittest.main()
