"""CON-ARCH-006 additive lower integration must preserve the complete baseline."""
import unittest
from shapely.geometry import box
from tools.stage_kc2_registered_lower import compose_lower, audit_additive, stage_path
from tools.kc2_central_flexure import prism

class LowerIntegration(unittest.TestCase):
    def test_addition_preserves_baseline_and_roots(self):
        base=prism(box(0,0,10,10),-2.2,-1)
        additions=[prism(box(1,1,2,2),-1,5)]
        final=compose_lower(base,additions)
        self.assertEqual(audit_additive(base,final,additions)['errors'],[])
    def test_disconnected_addition_rejected(self):
        with self.assertRaises(ValueError):
            compose_lower(prism(box(0,0,10,10),-2.2,-1),[prism(box(20,20,21,21),-1,5)])
    def test_missing_baseline_rejected(self):
        base=prism(box(0,0,10,10),-2.2,-1)
        damaged=base.cut(prism(box(0,0,1,1),-3,0))
        self.assertTrue(audit_additive(base,damaged,[])['errors'])
    def test_unplanned_addition_rejected(self):
        base=prism(box(0,0,10,10),-2.2,-1)
        final=base.fuse(prism(box(1,1,2,2),-1,5))
        self.assertTrue(audit_additive(base,final,[])['errors'])
    def test_paths_staged_and_identity_checked(self):
        self.assertIn('.codex-tmp',stage_path('left',True).parts)
        with self.assertRaises(ValueError):stage_path('invalid',False)

if __name__=='__main__':unittest.main()
