"""CON-ARCH-006 receiver throat is contiguous floor-level opening."""
import unittest
from shapely.geometry import box
from tools.kc2_floor_capture import contiguous_throat, motion_areas


class FloorCaptureTests(unittest.TestCase):
    def test_remote_gaps_do_not_inflate_throat(self):
        receiver = box(0, -3, 2, 3).difference(box(-1, -1.40004, 3, 1.40004))
        receiver = receiver.difference(box(.1, -2.8, 1, -2.4))
        self.assertAlmostEqual(contiguous_throat(receiver, .5, 0), 2.80008)

    def test_missing_either_shoulder_fails(self):
        with self.assertRaises(ValueError):
            contiguous_throat(box(0, 1.4, 2, 3), .5, 0)

    def test_motion_reports_planar_area_not_fabricated_3d_run(self):
        rows = motion_areas(box(0, 0, 1, 1), box(.5, -.5, 2, 2))
        self.assertAlmostEqual(rows[0]['collision_area_mm2'], 1)
        self.assertNotIn('collision_mm3', rows[0])


if __name__ == '__main__': unittest.main()
