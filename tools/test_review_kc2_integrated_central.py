"""CON-ARCH-006 actual central BRep must retain free cheeks and insertion."""
import unittest
from tools.review_kc2_integrated_central import contract_solids,audit_pair,extrude
from shapely.geometry import box


class IntegratedCentralTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.c=contract_solids()

    def test_CON_ARCH_006_reference_contact_only_and_free_volume(self):
        r=audit_pair(self.c['male'],self.c['female'],self.c['male'],self.c['female'])
        self.assertEqual(r['errors'],[])
        self.assertGreater(r['expected_contact_mm3'],0)

    def test_CON_ARCH_006_added_rigid_floor_or_wall_blocks_insertion(self):
        for z in [(-2.2,-1.),(-1.,.7)]:
            right=self.c['female'].fuse(extrude(box(1.5,-1.1,1.8,1.1),*z))
            with self.subTest(z=z):
                self.assertIn('rigid insertion obstruction',audit_pair(self.c['male'],right,self.c['male'],self.c['female'])['errors'])

    def test_CON_ARCH_006_upper_attachment_at_tip_must_fail(self):
        right=self.c['female'].fuse(extrude(box(1.2,1.35,3.2,2.55),1.5,1.8))
        self.assertIn('overhead free space obstructed',audit_pair(self.c['male'],right,self.c['male'],self.c['female'])['errors'])

    def test_CON_ARCH_006_rear_or_outer_bridge_must_fail(self):
        right=self.c['female'].fuse(extrude(box(3.2,1.35,4.,2.55),-.8,.5))
        self.assertIn('lateral/rear free space obstructed',audit_pair(self.c['male'],right,self.c['male'],self.c['female'])['errors'])

    def test_CON_ARCH_006_missing_contact_or_feature_must_fail(self):
        right=self.c['female'].cut(self.c['contact'])
        r=audit_pair(self.c['male'],right,self.c['male'],self.c['female'])
        self.assertIn('required isolated feature missing',r['errors'])
        self.assertIn('intended contact missing',r['errors'])


if __name__=='__main__':unittest.main()
