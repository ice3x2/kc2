"""CON-ARCH-006 TDD for independent flat central-seam acceptance."""
import unittest

from tools.review_kc2_flat_central_revision import evaluate


class FlatCentralReviewTests(unittest.TestCase):
    def valid(self):
        return dict(
            body_count=1,
            expected_body_count=1,
            removed_mm3=20.0,
            added_mm3=0.0,
            off_guide_removed_mm3=0.0,
            baseline_removed_mm3=0.0,
            remaining_protrusion_mm3=0.0,
            step_roundtrip_missing_mm3=0.0,
            step_roundtrip_extra_mm3=0.0,
            magnetic_missing_mm3=0.0,
            unexpected_magnetic_mm3=0.0,
            mesh_errors=[],
        )

    def test_exact_subtractive_revision_passes(self):
        self.assertEqual(evaluate(self.valid()), [])

    def test_material_or_topology_change_fails_closed(self):
        for name, value in (
            ("added_mm3", .01),
            ("off_guide_removed_mm3", .01),
            ("baseline_removed_mm3", .01),
            ("remaining_protrusion_mm3", .01),
            ("step_roundtrip_missing_mm3", .01),
            ("magnetic_missing_mm3", .01),
        ):
            row = self.valid(); row[name] = value
            self.assertTrue(evaluate(row), name)
        row = self.valid(); row["body_count"] = 2
        self.assertTrue(evaluate(row))
        row = self.valid(); row["mesh_errors"] = ["not watertight"]
        self.assertTrue(evaluate(row))

    def test_no_removed_guide_is_not_a_success(self):
        row = self.valid(); row["removed_mm3"] = 0.0
        self.assertTrue(evaluate(row))


if __name__ == "__main__":
    unittest.main()
