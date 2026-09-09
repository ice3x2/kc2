"""CON-ARCH-006: retain original joined position, not enlarged enclosure."""
import unittest
from shapely.geometry import box
from tools.review_kc2_local_assembly import check_join, original_transform


class JoinedCoverTests(unittest.TestCase):
    def test_transform_accepts_float_roundoff_but_rejects_changed_or_invalid_values(self):
        self.assertTrue(original_transform({'dx':124.62499999999999,'dy':0.0}))
        for transform in [{'dx':129.225,'dy':0},{'dx':float('nan'),'dy':0},{}]:
            self.assertFalse(original_transform(transform))

    def test_gap_is_checked_on_complete_polygons(self):
        self.assertEqual(check_join(box(0,0,10,10),box(11.3,0,20,10))['errors'],[])
        self.assertTrue(check_join(box(0,0,10,10),box(9.9,5,20,10))['errors'])


if __name__=='__main__':unittest.main()
