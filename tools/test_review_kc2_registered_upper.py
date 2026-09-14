"""CON-ARCH-006 independent feature contract catches lost rebates/voids."""
import unittest
from shapely.geometry import box
from tools.review_kc2_registered_upper import feature_errors

class FeatureTests(unittest.TestCase):
    def test_filled_hole_and_missing_roof_rejected(self):
        actual=box(0,0,10,10)
        errors=feature_errors(actual,required=box(0,0,12,10),voids=box(2,2,3,3))
        self.assertIn('required structural material absent',errors)
        self.assertIn('functional void obstructed',errors)
    def test_exact_geometry_passes(self):
        full=box(0,0,10,10);hole=box(2,2,3,3)
        self.assertEqual(feature_errors(full.difference(hole),required=full.difference(hole),voids=hole),[])

if __name__=='__main__':unittest.main()
