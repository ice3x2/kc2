"""CON-ARCH-006 / OPS-ARCH-006 generated upper remains staged until review."""
import unittest
from pathlib import Path
from tools.stage_kc2_registered_upper import stage_path
class StageTest(unittest.TestCase):
    def test_identity_and_location(self):
        p=stage_path('left','mx')
        self.assertIn('.codex-tmp',p.parts)
        self.assertEqual(p.name,'left-mx')
        for a,b in [('left','choc_v2'),('../hardware','mx')]:
            with self.assertRaises(ValueError):stage_path(a,b)
if __name__=='__main__':unittest.main()
