"""CON-ARCH-006 continuous tall external sleeve, failing-first contract tests."""
import unittest
from shapely.geometry import box, GeometryCollection, Polygon
from tools.kc2_wrap_wall_plan import sleeve_plan, SleeveDimensions, validate_dimensions, mating_outline, cad_outline


class SleevePlanTests(unittest.TestCase):
    def test_boolean_roundoff_edges_are_removed_without_losing_voids(self):
        p = Polygon([(0, 0), (1e-15, 0), (10, 0), (10, 10), (0, 10)],
                    holes=[[(2, 2), (3, 2), (3, 3), (2, 3)]])
        actual = cad_outline(p)
        self.assertEqual(len(actual.exterior.coords), 5)
        self.assertEqual(len(actual.interiors), 1)
        self.assertLess(actual.symmetric_difference(p).area, 1e-9)

    def test_pcb_extending_beyond_plate_keeps_seating_clearance(self):
        plate = box(0, 0, 100, 100)
        board = box(0, 0, 100.1, 100)
        cap = box(10, 10, 90, 90)
        outline = mating_outline(plate, cap, board)
        p = sleeve_plan('left', outline, GeometryCollection())
        self.assertGreaterEqual(p.wall.distance(board), .3-1e-8)

    def test_wide_keycap_cannot_be_inside_new_tall_wall(self):
        old_domain = box(0, 0, 100, 100)
        wide_cap = box(95, 40, 101, 60)
        old = sleeve_plan('left', old_domain, GeometryCollection())
        self.assertGreater(old.wall.intersection(wide_cap).area, 0)
        common = mating_outline(old_domain, wide_cap)
        revised = sleeve_plan('left', common, GeometryCollection())
        self.assertEqual(revised.wall.intersection(wide_cap).area, 0)
        self.assertGreaterEqual(revised.wall.distance(wide_cap), .3-1e-8)

    def test_user_height_and_overlap_include_pcb_thickness(self):
        d = SleeveDimensions()
        self.assertAlmostEqual(d.wall_top-d.pcb_top, 1.5)
        self.assertAlmostEqual(d.wall_top-d.upper_bottom, 1.2)
        self.assertEqual(d.pcb_top, 4.1)

    def test_old_flush_wall_and_short_posts_are_rejected(self):
        for top in (4.1, 5.0):
            with self.assertRaises(ValueError):
                validate_dimensions(SleeveDimensions(wall_top=top))

    def test_complete_noncentral_perimeter_not_three_posts(self):
        p = sleeve_plan('left', box(0, 0, 100, 100), GeometryCollection())
        self.assertTrue(p.wall.covers(box(100.31, 1, 101.49, 99)))
        self.assertTrue(p.wall.covers(box(21, 100.31, 99, 101.49)))
        self.assertEqual(p.wall.intersection(p.central).area, 0)
        self.assertAlmostEqual(p.wall.distance(box(0, 0, 100, 100)), .3)

    def test_service_corridor_remains_open_through_new_outer_wall(self):
        domain = box(0, 0, 100, 100)
        p = sleeve_plan('left', domain, box(80, 10, 101, 15))
        self.assertEqual(p.wall.intersection(box(80, 10, 103, 15)).area, 0)
        self.assertTrue(p.floor.covers(p.wall))

    def test_right_central_exclusion_and_no_new_lock(self):
        p = sleeve_plan('right', box(0, 0, 160, 120), GeometryCollection(),
                        central_exclusion=box(145, 27, 300, 200))
        self.assertTrue(p.wall.covers(box(-1.49, 30, -.31, 115)))
        self.assertEqual(p.wall.intersection(box(145, 28, 300, 200)).area, 0)

    def test_central_transition_includes_first_row_cap_corners(self):
        p = sleeve_plan('left', box(0, 28.973, 100, 100), GeometryCollection(),
                        central_exclusion=box(-100, 27, 20, 200))
        self.assertEqual(p.wall.intersection(box(-100, 27, 20, 28)).area, 0)

    def test_center_exception_must_not_remove_twenty_mm_of_outer_bottom(self):
        other_half = box(-102, 0, -2, 100)
        p = sleeve_plan('left', box(0, 0, 100, 100), GeometryCollection(),
                        central_exclusion=other_half.buffer(1.9, join_style=2))
        self.assertTrue(p.wall.covers(box(1, 100.31, 19, 101.49)))
        self.assertGreaterEqual(p.wall.distance(other_half), 1.9-1e-8)

    def test_proximity_cut_must_not_leave_unprintable_center_wall_nub(self):
        tiny = box(10.3, 5, 10.4, 5.2)
        exclusion = box(10.2, -2, 12, 12).difference(tiny)
        p = sleeve_plan('left', box(0, 0, 10, 10), GeometryCollection(), central_exclusion=exclusion)
        self.assertEqual(p.wall.intersection(tiny).area, 0)


if __name__ == '__main__':
    unittest.main()
