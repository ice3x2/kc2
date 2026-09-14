"""CON-ARCH-006 tests for the user-approved flat central seam revision."""
import math
import unittest

from shapely.geometry import box

from tools.kc2_flat_central_revision import (
    CONTROLLER_MAX_Y,
    EXISTING_MAGNET_YS,
    FLAT_FACE_X,
    GUIDE_YS,
    choose_controller_magnet,
    flat_join_cutters,
)


class FlatCentralRevisionTests(unittest.TestCase):
    def test_all_old_guide_windows_are_cut_flush_on_both_sides(self):
        self.assertEqual(GUIDE_YS, (95.0, 117.0))
        self.assertEqual(EXISTING_MAGNET_YS, (103.0, 111.0))
        for side in ("left", "right"):
            cutters = flat_join_cutters(side)
            self.assertEqual(len(cutters), 2)
            for y, cutter in zip(GUIDE_YS, cutters):
                self.assertTrue(cutter["plan"].covers(box(
                    cutter["x0"], y - 2.55, cutter["x1"], y + 2.55)))
                self.assertEqual((cutter["z0"], cutter["z1"]), (-2.2, 1.8))
                if side == "left":
                    self.assertEqual(cutter["x1"], FLAT_FACE_X[side])
                else:
                    self.assertEqual(cutter["x0"], FLAT_FACE_X[side])

    def test_controller_pair_requires_complete_material_and_existing_spacing(self):
        valid = dict(y=92.0, face_gap_mm=4.4,
                     reserve_missing_left_mm3=0.0,
                     reserve_missing_right_mm3=0.0,
                     forbidden_left_mm2=0.0, forbidden_right_mm2=0.0)
        self.assertEqual(CONTROLLER_MAX_Y, 97.0)
        self.assertEqual(choose_controller_magnet([valid]), valid)
        for field, value in (
            ("reserve_missing_left_mm3", 1e-9),
            ("reserve_missing_right_mm3", 1e-9),
            ("forbidden_left_mm2", 1e-9),
            ("forbidden_right_mm2", 1e-9),
            ("face_gap_mm", 4.400001),
            ("y", 97.000001),
        ):
            bad = dict(valid); bad[field] = value
            self.assertIsNone(choose_controller_magnet([bad]), field)

    def test_invalid_or_boolean_measurements_are_rejected(self):
        base = dict(y=92.0, face_gap_mm=4.4,
                    reserve_missing_left_mm3=0.0,
                    reserve_missing_right_mm3=0.0,
                    forbidden_left_mm2=0.0, forbidden_right_mm2=0.0)
        for value in (True, math.nan, math.inf, "0"):
            bad = dict(base); bad["reserve_missing_left_mm3"] = value
            with self.assertRaises((TypeError, ValueError)):
                choose_controller_magnet([bad])

    def test_no_candidate_is_an_explicit_safe_outcome(self):
        near_miss = dict(y=92.0, face_gap_mm=4.4,
                         reserve_missing_left_mm3=0.077,
                         reserve_missing_right_mm3=0.0,
                         forbidden_left_mm2=0.0, forbidden_right_mm2=0.0)
        remote = dict(near_miss, y=20.0, face_gap_mm=31.9,
                      reserve_missing_left_mm3=0.0)
        self.assertIsNone(choose_controller_magnet([near_miss, remote]))


if __name__ == "__main__":
    unittest.main()
