"""CON-ARCH-006 only exterior additions may extend the established split."""
import unittest
from shapely.geometry import box, MultiPolygon
from tools.kc2_wrap_partition import raw_owners


class WrapPartitionTests(unittest.TestCase):
    def test_outside_continuation_keeps_point_four_gap(self):
        openings = MultiPolygon([box(5, 5, 15, 15), box(85, 5, 95, 15)])
        a, b = raw_owners(box(0, 0, 100, 20), openings, [])
        self.assertGreaterEqual(a.distance(b), .4)
        self.assertTrue(a.covers(box(-1, -1, 20, 0)))
        self.assertTrue(b.covers(box(80, -1, 101, 0)))


if __name__ == '__main__':
    unittest.main()
