"""CON-ARCH-006 bounded planar precision for STL-derived lower patches."""
import unittest
from shapely.geometry import box
from tools.build_kc2_wall_gap_precision import stable_patch

class PrecisionTests(unittest.TestCase):
    def test_float32_boundaries_snap_with_submicron_error(self):
        p=box(78.28630828857422,124,81.74369049072266,124.1120034790039)
        q,proof=stable_patch(p)
        self.assertTrue(q.is_valid)
        self.assertLessEqual(proof['hausdorff_mm'],.00008)
        self.assertLess(proof['changed_area_mm2'],.001)
        self.assertEqual(q.bounds[2],81.7437)

    def test_actual_slit_interior_is_retained(self):
        p=box(135.012496948-.035,68.25,135.412506104+.035,84.5)
        q,_=stable_patch(p)
        self.assertTrue(q.covers(box(135.02,68.3,135.4,84.4)))

    def test_collapse_is_not_silently_accepted(self):
        with self.assertRaises(ValueError):stable_patch(box(0,0,.000001,10))

if __name__=='__main__':unittest.main()
