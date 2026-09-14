"""CON-ARCH-006 fail-closed review of the optional controller-side pair."""
import unittest

from tools.review_kc2_controller_magnet_feasibility import validate


class ControllerMagnetFeasibilityTests(unittest.TestCase):
    def base(self):
        return dict(status="pass_no_safe_candidate", errors=[], selected=None,
                    controller_y_range_mm=[31.0, 97.0], search_step_mm=.1,
                    safely_aligned_candidates=[],
                    remote_candidates=[dict(y=20.0, face_gap_mm=31.9)],
                    actual_near_misses=[
                        dict(y=92.0, reserve_missing_left_mm3=.01,
                             reserve_missing_right_mm3=0.0),
                        dict(y=97.0, reserve_missing_left_mm3=.1,
                             reserve_missing_right_mm3=.1)],
                    wall_expansion_required=True, added_pair=False,
                    physical_qualified=False)

    def test_no_safe_pair_is_valid_only_with_actual_near_miss_evidence(self):
        self.assertEqual(validate(self.base()), [])
        for mutation in (
            lambda r: r.update(actual_near_misses=[]),
            lambda r: r.update(wall_expansion_required=False),
            lambda r: r.update(added_pair=True),
            lambda r: r["actual_near_misses"][0].update(reserve_missing_left_mm3=0.0),
        ):
            row = self.base(); mutation(row)
            self.assertTrue(validate(row))

    def test_a_safe_pair_requires_selected_and_added(self):
        row = self.base()
        row.update(status="pass_safe_candidate", selected=dict(y=80.0, face_gap_mm=4.4),
                   safely_aligned_candidates=[dict(y=80.0, face_gap_mm=4.4)],
                   remote_candidates=[], actual_near_misses=[],
                   wall_expansion_required=False, added_pair=True)
        self.assertEqual(validate(row), [])
        row["added_pair"] = False
        self.assertTrue(validate(row))


if __name__ == "__main__":
    unittest.main()
