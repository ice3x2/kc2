"""CON-ARCH-006 independent lower actual-void and addition inclusion gates."""
import unittest
from shapely.geometry import box
from tools.kc2_central_flexure import prism
from tools.review_kc2_registered_lower import check_inclusion,check_void
class LowerReview(unittest.TestCase):
    def test_missing_required_wall_rejected(self):
        base=prism(box(0,0,10,10),-2.2,-1)
        self.assertGreater(check_inclusion(base,prism(box(1,1,2,2),-1,5)),1)
    def test_included_wall_passes(self):
        shape=prism(box(0,0,10,10),-2.2,5)
        self.assertLess(check_inclusion(shape,prism(box(1,1,2,2),-1,5)),1e-8)
    def test_obstructed_void_rejected(self):
        shape=prism(box(0,0,10,10),-2.2,5)
        self.assertGreater(check_void(shape,prism(box(1,1,2,2),-1,5)),1)
if __name__=='__main__':unittest.main()
