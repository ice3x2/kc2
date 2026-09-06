"""CON-ARCH-004/006: planner must not escape clipped obstacle boundaries."""
import unittest
from shapely.geometry import LineString, box, Point
from tools.repair_kc2_solder_routes import path_around, model_obstacles


class RoutePlanner(unittest.TestCase):
    def test_local_clipping_never_creates_false_open_path(self):
        obstacle=box(2,-3,3,3)
        path=path_around((0,0),(5,0),obstacle)
        self.assertFalse(LineString(path).intersects(obstacle))
        self.assertGreater(max(abs(p[1]) for p in path),3)

    def test_unreachable_wall_is_not_crossed_at_search_boundary(self):
        with self.assertRaises(RuntimeError):
            path_around((0,0),(5,0),box(2,-30,3,30))

    def test_support_keepout_applies_even_to_same_net(self):
        model={'pads':[],'tracks':[],'edges':[],'bcu':2,
            'supports':[{'x_mm':0,'y_mm':0,'copper_keepout_radius_mm':1.5}]}
        self.assertTrue(model_obstacles(model,15,2,0.25).intersects(Point(1.6,0)))
        self.assertTrue(model_obstacles(model,15,0,0.25).is_empty)


if __name__=='__main__':
    unittest.main()
