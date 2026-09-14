"""CON-ARCH-006 whole-keyboard straight approach requires all geometry families."""
import unittest
from shapely.geometry import box,Polygon
from tools.kc2_joined_sweep import Envelope,REQUIRED_COMPONENTS,audit_sweep,horizontal_sweep


class JoinedSweepTests(unittest.TestCase):
    def args(self):
        return {(side,kind):[Envelope(n,box(0,0,1,1) if side=='left' else box(3,0,4,1),0,1)
                for n in REQUIRED_COMPONENTS] for side in ['left','right'] for kind in ['mx','choc_v1','deep_sea']}

    def test_CON_ARCH_006_clear_all_profiles(self):
        self.assertEqual(audit_sweep(self.args())['errors'],[])

    def test_CON_ARCH_006_intermediate_only_blocker_rejected(self):
        a=self.args();a['right','mx'][0]=Envelope(a['right','mx'][0].name,box(-4,0,-3,1),0,1)
        self.assertTrue(a['left','mx'][0].geometry.disjoint(a['right','mx'][0].geometry))
        self.assertTrue(audit_sweep(a)['errors'])

    def test_CON_ARCH_006_missing_profile_or_component_rejected(self):
        a=self.args();del a['right','deep_sea']
        with self.assertRaises(ValueError):audit_sweep(a)
        a=self.args();a['right','mx'].pop()
        with self.assertRaises(ValueError):audit_sweep(a)

    def test_CON_ARCH_006_exact_hole_and_nonconvex_sweep(self):
        g=box(0,0,5,5).difference(box(1,1,4,4));s=horizontal_sweep(g,-.5)
        self.assertAlmostEqual(s.area,20.)
        self.assertFalse(s.covers(box(1.1,1.1,3.4,3.9)))
        self.assertTrue(s.covers(box(3.6,1.1,4,3.9)))

    def test_CON_ARCH_006_height_disjoint_obstruction_not_collision(self):
        a=self.args();a['right','mx'][0]=Envelope(a['right','mx'][0].name,box(-4,0,-3,1),2,3)
        self.assertEqual(audit_sweep(a)['errors'],[])

    def test_CON_ARCH_006_invalid_geometry_or_travel_rejected(self):
        with self.assertRaises(ValueError):horizontal_sweep(box(0,0,1,1),1)
        a=self.args();a['left','mx'][0]=Envelope('pcb',Polygon(),0,1)
        with self.assertRaises(ValueError):audit_sweep(a)


if __name__=='__main__':unittest.main()
