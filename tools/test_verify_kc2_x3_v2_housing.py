from __future__ import annotations

import copy
import unittest

from tools.verify_kc2_x3_v2_housing import analyze_v2_housing, verify_report


class V2LoadBearingHousingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = analyze_v2_housing()

    def test_uses_only_current_draft_v2_boards(self) -> None:
        self.assertEqual(self.report["requirement"], "CON-ARCH-006")
        self.assertEqual(self.report["variant"], "x3-v2")
        self.assertTrue(self.report["generator_sha256_matches"])
        for side in ("left", "right"):
            board = self.report["sides"][side]
            self.assertIn("hardware/kicad/draft/x3-v2/", board["source_board"])
            self.assertTrue(board["source_board_sha256_matches"])
            self.assertEqual(board["key_count"], 32 if side == "left" else 39)
            self.assertEqual(board["legacy_registration_refs"], [])

    def test_rails_and_posts_are_zero_gap_load_paths(self) -> None:
        for side in ("left", "right"):
            housing = self.report["sides"][side]
            self.assertAlmostEqual(housing["rail_top_z_mm"], housing["pcb_bottom_z_mm"], places=6)
            self.assertAlmostEqual(housing["maximum_rail_vertical_gap_mm"], 0.0, places=6)
            self.assertAlmostEqual(housing["maximum_support_vertical_gap_mm"], 0.0, places=6)
            self.assertGreater(housing["rail_plan_area_mm2"], 0.0)
            self.assertTrue(housing["rail_plan_area_matches_manifest"])
            self.assertTrue(housing["support_plan_matches_generator"])
            categories = {post["category"] for post in housing["support_posts"]}
            self.assertTrue({"seam", "thumb", "span"}.issubset(categories))
            self.assertGreaterEqual(len(housing["support_posts"]), 8)
            self.assertLessEqual(housing["maximum_load_point_to_support_mm"], 24.0)
            for post in housing["support_posts"]:
                self.assertEqual(post["diameter_mm"], 3.20)
                self.assertEqual(post["bottom_z_mm"], 1.20)
                self.assertEqual(post["top_z_mm"], housing["pcb_bottom_z_mm"])
                self.assertEqual(post["nominal_vertical_gap_mm"], 0.0)

    def test_supports_do_not_reintroduce_legacy_fasteners(self) -> None:
        for side in ("left", "right"):
            housing = self.report["sides"][side]
            self.assertEqual(housing["registration_peg_count"], 0)
            self.assertEqual(housing["screw_pilot_count"], 0)
            self.assertEqual(housing["fastener_boss_count"], 0)

    def test_every_printable_part_fits_150_mm_cube(self) -> None:
        for side in ("left", "right"):
            parts = self.report["sides"][side]["printable_parts"]
            self.assertEqual(len(parts), 1 if side == "left" else 2)
            for part in parts:
                self.assertEqual(part["solid_count"], 1)
                self.assertTrue(part["watertight"])
                self.assertEqual(part["shell_count"], 1)
                self.assertTrue(part["sha256_matches"])
                self.assertTrue(all(value <= 150.0 for value in part["size_xyz_mm"]))
        self.assertFalse(self.report["stale_monolithic_right_stl_present"])

    def test_step_exports_have_no_trailing_whitespace(self) -> None:
        for side in ("left", "right"):
            self.assertFalse(self.report["sides"][side]["step_has_trailing_whitespace"])
        report = copy.deepcopy(self.report)
        report["sides"]["right"]["step_has_trailing_whitespace"] = True
        self.assertTrue(
            any("STEP has trailing whitespace" in error for error in verify_report(report))
        )

    def test_right_split_has_glueless_mechanical_lap_joint(self) -> None:
        joint = self.report["sides"]["right"]["split_joint"]
        self.assertEqual(joint["type"], "overlap_lap_with_m2_case_join")
        self.assertFalse(joint["glue_assumed"])
        self.assertEqual(joint["part_count"], 2)
        self.assertGreaterEqual(joint["lap_overlap_mm"], 6.0)
        self.assertGreaterEqual(joint["case_join_fastener_count"], 2)
        self.assertEqual(joint["feature_collision_count"], 0)
        self.assertEqual(joint["support_collision_count"], 0)
        self.assertTrue(joint["support_load_path_preserved"])
        self.assertGreater(joint["head_recess_depth_mm"], 0.0)
        self.assertLess(joint["receiving_pilot_top_z_mm"], joint["case_join_boss_top_z_mm"])
        self.assertEqual(joint["assembly_direction"], "bottom_up")
        self.assertLessEqual(joint["head_exterior_protrusion_max_mm"], 0.0)
        self.assertGreater(joint["screw_tip_to_pcb_clearance_mm"], 0.0)
        self.assertEqual(joint["head_driver_vertical_collision_count"], 0)
        self.assertTrue(joint["driver_access_from_exterior_bottom"])
        fastener = joint["fastener_spec"]
        self.assertEqual(fastener["part_number"], "SUNCO CSPSL-ST3W-M2-3")
        self.assertEqual(fastener["thread"], "M2 x 0.4")
        self.assertEqual(fastener["under_head_length_mm"], 3.0)
        self.assertEqual(fastener["official_under_head_length_min_mm"], 2.7)
        self.assertEqual(fastener["official_under_head_length_max_mm"], 3.0)
        self.assertEqual(fastener["official_head_diameter_min_mm"], 3.5)
        self.assertEqual(fastener["official_head_diameter_max_mm"], 4.0)
        self.assertEqual(fastener["official_head_height_min_mm"], 0.4)
        self.assertEqual(fastener["official_head_height_max_mm"], 0.6)
        self.assertGreaterEqual(fastener["shank_clearance_hole_diameter_mm"], 2.4)
        self.assertLessEqual(fastener["shank_clearance_hole_diameter_mm"], 2.6)
        self.assertEqual(fastener["head_recess_diameter_mm"], 4.4)
        self.assertGreaterEqual(fastener["head_recess_radial_print_clearance_mm"], 0.2)
        self.assertGreaterEqual(fastener["minimum_radial_head_bearing_mm"], 0.4)
        self.assertGreaterEqual(fastener["minimum_radial_collar_wall_mm"], 0.5)
        self.assertEqual(fastener["drive"], "Phillips #0")
        self.assertEqual(fastener["driver_shaft_diameter_mm"], 3.0)
        self.assertEqual(fastener["official_length_lower_tolerance_mm"], -0.3)
        self.assertEqual(fastener["official_length_upper_tolerance_mm"], 0.0)
        self.assertEqual(fastener["fdm_z_tolerance_mm"], 0.05)
        self.assertEqual(fastener["part_a_seat_fdm_tolerance_mm"], 0.05)
        self.assertEqual(fastener["part_b_boss_fdm_tolerance_mm"], 0.05)
        self.assertEqual(fastener["support_plane_fdm_tolerance_mm"], 0.05)
        self.assertIn(
            "boss_top_nominal - part_b_boss_fdm_tolerance",
            fastener["installed_screw_tip_to_boss_top_clearance_formula"],
        )
        self.assertIn(
            "pcb_bottom_nominal - support_plane_fdm_tolerance",
            fastener["installed_screw_tip_to_pcb_clearance_formula"],
        )
        self.assertEqual(fastener["driver_access_direction"], "bottom_downward")
        worst = fastener["worst_case"]
        self.assertGreaterEqual(
            worst["usable_pilot_depth_mm"],
            worst["maximum_threaded_penetration_into_pilot_mm"],
        )
        self.assertGreaterEqual(
            worst["effective_thread_engagement_mm"],
            fastener["minimum_effective_thread_engagement_mm"],
        )
        self.assertGreater(worst["receiving_pilot_blind_cap_mm"], 0.0)
        self.assertGreater(worst["head_exterior_face_z_mm"], 0.0)
        self.assertGreaterEqual(worst["installed_screw_tip_to_boss_top_clearance_mm"], 0.05)
        self.assertGreaterEqual(worst["installed_screw_tip_to_pcb_clearance_mm"], 0.05)
        self.assertEqual(joint["head_case_collision_volume_mm3"], 0.0)
        self.assertEqual(joint["driver_shaft_case_collision_volume_mm3"], 0.0)

    def test_all_required_collision_classes_are_clear(self) -> None:
        required = {
            "choc_socket_body",
            "choc_socket_fillets",
            "mx_pins_pads_fillets",
            "diode_body_pads_fillets",
            "bottom_copper_tracks",
            "vias",
            "controller_reset",
            "battery_slot",
            "switch_key_travel",
        }
        for side in ("left", "right"):
            collisions = self.report["sides"][side]["collision_checks"]
            self.assertEqual(set(collisions), required)
            for feature_class, result in collisions.items():
                self.assertEqual(result["collision_count"], 0, feature_class)

    def test_verifier_rejects_fastener_tolerance_regression(self) -> None:
        report = copy.deepcopy(self.report)
        fastener = report["sides"]["right"]["split_joint"]["fastener_spec"]
        fastener["shank_clearance_hole_diameter_mm"] = 3.5
        fastener["minimum_radial_head_bearing_mm"] = 0.0
        errors = verify_report(report)
        self.assertTrue(any("shank clearance" in error for error in errors))
        self.assertTrue(any("bearing annulus" in error for error in errors))

    def test_verifier_rejects_independent_z_tolerance_clearance_regression(self) -> None:
        report = copy.deepcopy(self.report)
        joint = report["sides"]["right"]["split_joint"]
        worst = joint["fastener_spec"]["worst_case"]
        joint["case_join_boss_top_z_mm"] = 3.84
        joint["pcb_bottom_z_mm"] = 3.84
        worst["installed_screw_tip_to_boss_top_clearance_mm"] = 0.04
        worst["installed_screw_tip_to_pcb_clearance_mm"] = 0.04
        errors = verify_report(report)
        self.assertTrue(any("boss-top clearance" in error for error in errors))
        self.assertTrue(any("support-plane clearance" in error for error in errors))

    def test_generated_artifacts_are_current_and_physical_gate_stays_pending(self) -> None:
        for side in ("left", "right"):
            housing = self.report["sides"][side]
            self.assertTrue(housing["step_sha256_matches"])
            self.assertTrue(housing["stl_sha256_matches"])
            self.assertEqual(housing["step_solid_count"], 1 if side == "left" else 2)
            self.assertAlmostEqual(housing["step_bounds_z_mm"][0], 0.0, places=4)
            self.assertAlmostEqual(housing["step_bounds_z_mm"][1], housing["pcb_bottom_z_mm"], places=4)
            self.assertTrue(housing["step_top_contact_area_matches_plan"])
            self.assertLessEqual(housing["step_top_contact_area_error_mm2"], 0.20)
        self.assertEqual(self.report["physical_deflection_test"]["status"], "pending")
        self.assertFalse(self.report["fabrication_or_order_ready"])
        self.assertEqual(verify_report(self.report), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
