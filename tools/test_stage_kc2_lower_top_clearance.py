"""CON-ARCH-006 ordinary wall clearance must not lower registrar tips."""
import unittest
from shapely.geometry import box
from tools.stage_kc2_lower_top_clearance import lower_top
from tools.kc2_central_flexure import prism
class TopClearance(unittest.TestCase):
    def test_only_ordinary_top_strip_removed(self):
        wall=box(0,0,10,1);reg=box(2,0,3,1)
        shape=prism(wall,-1,4.35).fuse(prism(reg,-1,5))
        final=lower_top(shape,wall,reg)
        self.assertAlmostEqual(final.intersect(prism(wall.difference(reg),4.1,4.35)).Volume(),0,places=8)
        self.assertAlmostEqual(final.intersect(prism(reg,4.1,5)).Volume(),.9,places=8)
if __name__=='__main__':unittest.main()
