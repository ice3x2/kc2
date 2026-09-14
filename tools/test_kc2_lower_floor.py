"""CON-ARCH-006 print-continuous structural floor; no silicone-foot checks."""
import unittest
from shapely.geometry import box
from tools.kc2_central_flexure import prism
from tools.kc2_lower_floor import inspect_floor
class Floor(unittest.TestCase):
    def test_full_constant_floor(self):
        self.assertEqual(inspect_floor(prism(box(0,0,10,10),-2.2,0))['errors'],[])
    def test_hidden_recess_rejected(self):
        solid=prism(box(0,0,10,10),-2.2,0).cut(prism(box(2,2,3,3),-2,-1.8))
        self.assertIn('unexpected floor transition',inspect_floor(solid)['errors'])
    def test_constant_through_floor_hole_rejected(self):
        solid=prism(box(0,0,10,10),-2.2,0).cut(prism(box(2,2,3,3),-2.3,-.9))
        self.assertIn('enclosed through-floor void',inspect_floor(solid)['errors'])
    def test_disconnected_floor_under_connected_roof_rejected(self):
        solid=prism(box(0,0,2,10),-2.2,0).fuse(prism(box(8,0,10,10),-2.2,0),prism(box(0,0,10,10),-.5,0)).clean()
        self.assertEqual(len(solid.Solids()),1)
        self.assertIn('floor is not one connected polygon',inspect_floor(solid)['errors'])
if __name__=='__main__':unittest.main()
