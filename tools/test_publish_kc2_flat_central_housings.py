"""CON-ARCH-006 TDD for the flat-seam canonical publication gate."""
import unittest

from tools.publish_kc2_flat_central_housings import lower_inventory, validate_evidence


class FlatCentralPublicationTests(unittest.TestCase):
    def valid(self):
        return dict(
            generation={"status": "generated_pending_independent_review", "errors": [],
                        "controller_magnet_pair_added": False},
            feasibility={"status": "pass_no_safe_candidate", "errors": [], "selected": None,
                         "added_pair": False, "wall_expansion_required": True},
            independent={"status": "pass", "errors": [], "controller_magnet_pair_added": False,
                         "rows": {label: {"errors": []} for label in (
                             "left:normal", "left:magnetic", "right:normal", "right:magnetic")}},
            native_generation={"status": "pass", "errors": [], "outputs": {
                label: {"status": "pass", "round_trip_verified": True}
                for label in ("left:normal", "left:magnetic", "right:normal", "right:magnetic")}},
            native_review={"status": "pass", "errors": [], "rows": {
                label: {"status": "pass"}
                for label in ("left:normal", "left:magnetic", "right:normal", "right:magnetic")}},
        )

    def test_exact_fourteen_lower_artifacts_are_selected(self):
        inventory = lower_inventory()
        self.assertEqual(len(inventory), 14)
        self.assertEqual(len(set(inventory.values())), 14)
        self.assertEqual(sum(name.endswith(".f3d") for name in inventory), 4)
        self.assertEqual(sum(name.endswith(".step") for name in inventory), 4)
        self.assertEqual(sum(name.endswith(".stl") for name in inventory), 6)

    def test_safe_fallback_and_all_actual_reviews_pass(self):
        self.assertEqual(validate_evidence(self.valid()), [])

    def test_added_pair_or_missing_native_review_fails_closed(self):
        value = self.valid(); value["generation"]["controller_magnet_pair_added"] = True
        self.assertTrue(validate_evidence(value))
        value = self.valid(); value["native_review"]["rows"].pop("right:magnetic")
        self.assertTrue(validate_evidence(value))
        value = self.valid(); value["feasibility"]["wall_expansion_required"] = False
        self.assertTrue(validate_evidence(value))


if __name__ == "__main__":
    unittest.main()
