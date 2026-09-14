"""CON-ARCH-006 true .30 mm envelope differs from nominal .35 tool cut."""
import unittest
from shapely.geometry import box,Point
from tools.kc2_required_lower_clearance import required_envelope
class RequiredClearance(unittest.TestCase):
    def test_coarse_circumscribed_bound_uses_small_edge_count(self):
        region=required_envelope({'part':Point(0,0)})
        self.assertEqual(len(region.exterior.coords),17)
        self.assertLess(Point(0,0).buffer(.3,quad_segs=256).difference(region).area,1e-10)
    def test_true_point_circle_is_conservatively_bounded(self):
        raw=Point(0,0).buffer(1,quad_segs=64)
        region=required_envelope({'part':raw})
        self.assertLess(raw.buffer(.3,quad_segs=256).difference(region).area,1e-10)
    def test_nominal_simplification_can_overlap_without_physical_collision(self):
        raw=Point(0,0).buffer(1,quad_segs=64)
        nominal=raw.buffer(.35,quad_segs=4)
        support=box(-3,-3,3,3).difference(nominal).simplify(.02,preserve_topology=True)
        self.assertGreater(support.intersection(nominal).area,1e-5)
        self.assertLess(support.intersection(required_envelope({'part':raw})).area,1e-10)
if __name__=='__main__':unittest.main()
