"""CON-ARCH-006: distinguish height, engagement, roof and lateral budget."""
import unittest
from shapely.geometry import box
from tools.kc2_wall_engagement_study import height_budget, wrap_envelope


class WallEngagementStudyTests(unittest.TestCase):
    def test_old_general_wall_does_not_satisfy_user_height(self):
        self.assertFalse(height_budget(0, 9.3)['meets_user_height'])

    def test_tall_wall_has_overlap_after_pcb_and_air_gap(self):
        r = height_budget(1.5, 9.3)
        self.assertTrue(r['meets_user_height'])
        self.assertAlmostEqual(r['wall_top_mm'], 5.6)
        self.assertAlmostEqual(r['nominal_overlap_mm'], 1.2)
        self.assertAlmostEqual(r['roof_mm'], 3.4)

    def test_low_profile_roof_must_not_be_called_full_strength(self):
        for top, roof in ((6.5, .6), (6.25, .35)):
            r = height_budget(1.5, top)
            self.assertAlmostEqual(r['roof_mm'], roof)
            self.assertFalse(r['roof_at_least_1_2_mm'])

    def test_wrap_requires_space_not_just_height(self):
        inner, wall = wrap_envelope(box(0, 0, 10, 10))
        self.assertEqual(inner.bounds, (-.3, -.3, 10.3, 10.3))
        self.assertAlmostEqual(wall.bounds[0], -1.5)
        self.assertAlmostEqual(wall.distance(box(0, 0, 10, 10)), .3)
        self.assertAlmostEqual(wall.intersection(box(0, 0, 10, 10)).area, 0)


if __name__ == '__main__':
    unittest.main()
