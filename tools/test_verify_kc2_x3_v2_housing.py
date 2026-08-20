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

    def test_nominal_2_5mm_plate_and_support_regions_are_zero_gap_load_paths(self) -> None:
        for side in ("left", "right"):
            housing = self.report["sides"][side]
            self.assertEqual(housing["exterior_bottom_z_mm"], 0.0)
            self.assertEqual(housing["housing_height_mm"], 2.50)
            self.assertEqual(housing["pcb_bottom_z_mm"], 2.50)
            self.assertFalse(housing["raised_key_field_bezel_present"])
            self.assertAlmostEqual(housing["rail_top_z_mm"], housing["pcb_bottom_z_mm"], places=6)
            self.assertAlmostEqual(housing["maximum_rail_vertical_gap_mm"], 0.0, places=6)
            self.assertAlmostEqual(housing["maximum_support_vertical_gap_mm"], 0.0, places=6)
            self.assertGreater(housing["rail_plan_area_mm2"], 0.0)
            self.assertTrue(housing["rail_plan_area_matches_manifest"])
            self.assertTrue(housing["support_plan_matches_generator"])
            categories = {post["category"] for post in housing["support_posts"]}
            self.assertTrue({"thumb", "span"}.issubset(categories))
            self.assertGreaterEqual(len(housing["support_posts"]), 6)
            self.assertLessEqual(housing["maximum_load_point_to_support_mm"], 24.0)
            self.assertLessEqual(housing["maximum_seam_load_point_to_support_mm"], 10.0)
            for post in housing["support_posts"]:
                self.assertEqual(post["diameter_mm"], 2.00)
                self.assertEqual(post["bottom_z_mm"], 0.00)
                self.assertEqual(post["top_z_mm"], housing["pcb_bottom_z_mm"])
                self.assertEqual(post["nominal_vertical_gap_mm"], 0.0)

    def test_bottom_component_cutouts_are_exterior_open_and_3d_clear(self) -> None:
        required = {
            "choc_socket_body_fillets",
            "switch_mechanical_pins",
            "mx_pins_pads_fillets",
            "diode_body_pads_fillets",
            "controller_reset",
            "battery_slot",
        }
        for side in ("left", "right"):
            housing = self.report["sides"][side]
            cutouts = housing["component_cutouts"]
            self.assertEqual(set(cutouts), required)
            key_count = 32 if side == "left" else 39
            for name in (
                "choc_socket_body_fillets",
                "switch_mechanical_pins",
                "mx_pins_pads_fillets",
                "diode_body_pads_fillets",
            ):
                self.assertEqual(cutouts[name]["opening_count"], key_count, name)
            self.assertEqual(cutouts["controller_reset"]["opening_count"], 1)
            self.assertEqual(cutouts["battery_slot"]["opening_count"], 1)
            for name, result in cutouts.items():
                self.assertGreater(result["opening_count"], 0, name)
                self.assertTrue(result["exterior_open"], name)
                self.assertEqual(result["through_opening_z_mm"], [0.0, 2.5], name)
                self.assertGreaterEqual(result["minimum_xy_clearance_mm"], 0.30, name)
                self.assertEqual(result["residual_collision_volume_mm3"], 0.0, name)
            self.assertEqual(cutouts["choc_socket_body_fillets"]["official_body_depth_max_mm"], 2.30)
            self.assertGreaterEqual(
                cutouts["choc_socket_body_fillets"]["minimum_exterior_bottom_clearance_mm"],
                0.10,
            )
            self.assertEqual(cutouts["diode_body_pads_fillets"]["official_body_depth_max_mm"], 1.35)
            self.assertEqual(cutouts["diode_body_pads_fillets"]["solder_fillet_allowance_mm"], 0.30)
            self.assertGreaterEqual(
                cutouts["diode_body_pads_fillets"]["minimum_exterior_bottom_clearance_mm"],
                0.50,
            )

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

    def test_right_split_has_full_depth_glueless_keyed_puzzle_joint(self) -> None:
        joint = self.report["sides"]["right"]["split_joint"]
        self.assertEqual(joint["type"], "full_depth_vertical_keyed_puzzle")
        self.assertFalse(joint["glue_assumed"])
        self.assertEqual(joint["part_count"], 2)
        self.assertEqual(joint["fastener_count"], 0)
        self.assertEqual(joint["assembly_direction"], "vertical")
        self.assertEqual(joint["joint_height_mm"], 2.50)
        self.assertGreaterEqual(joint["capture_feature_count"], 2)
        self.assertGreater(joint["head_width_mm"], joint["neck_width_mm"])
        self.assertGreaterEqual(joint["minimum_in_plane_capture_per_side_mm"], 1.0)
        self.assertEqual(joint["nominal_plan_clearance_mm"], 0.20)
        self.assertTrue(joint["positive_x_capture"])
        self.assertEqual(joint["feature_collision_count"], 0)
        self.assertEqual(joint["support_collision_count"], 0)
        self.assertTrue(joint["support_load_path_preserved"])

    def test_all_required_collision_classes_are_clear(self) -> None:
        required = {
            "choc_socket_body",
            "choc_socket_fillets",
            "switch_mechanical_pins",
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

    def test_verifier_rejects_missing_diode_cutout_or_vertical_clearance(self) -> None:
        report = copy.deepcopy(self.report)
        diode = report["sides"]["left"]["component_cutouts"]["diode_body_pads_fillets"]
        diode["opening_count"] = 1
        diode["exterior_open"] = False
        diode["residual_collision_volume_mm3"] = 0.1
        diode["minimum_exterior_bottom_clearance_mm"] = 0.4
        errors = verify_report(report)
        self.assertTrue(any("diode_body_pads_fillets opening count" in error for error in errors))
        self.assertTrue(any("diode_body_pads_fillets is not exterior-open" in error for error in errors))
        self.assertTrue(any("diode_body_pads_fillets 3D collision" in error for error in errors))
        self.assertTrue(any("diode exterior clearance" in error for error in errors))

    def test_verifier_rejects_puzzle_capture_regression(self) -> None:
        report = copy.deepcopy(self.report)
        joint = report["sides"]["right"]["split_joint"]
        joint["type"] = "overlap_lap_with_m2_case_join"
        joint["minimum_in_plane_capture_per_side_mm"] = 0.0
        joint["positive_x_capture"] = False
        errors = verify_report(report)
        self.assertTrue(any("split-joint type" in error for error in errors))
        self.assertTrue(any("puzzle capture" in error for error in errors))

    def test_generated_artifacts_are_current_and_physical_gate_stays_pending(self) -> None:
        for side in ("left", "right"):
            housing = self.report["sides"][side]
            self.assertTrue(housing["step_sha256_matches"])
            self.assertTrue(housing["stl_sha256_matches"])
            self.assertEqual(housing["step_solid_count"], 1 if side == "left" else 2)
            self.assertAlmostEqual(housing["step_bounds_z_mm"][0], 0.0, places=4)
            self.assertAlmostEqual(housing["step_bounds_z_mm"][1], 2.50, places=4)
            self.assertTrue(housing["step_top_contact_area_matches_plan"])
            self.assertLessEqual(housing["step_top_contact_area_error_mm2"], 0.20)
        self.assertEqual(self.report["physical_deflection_test"]["status"], "pending")
        self.assertFalse(self.report["fabrication_or_order_ready"])
        self.assertEqual(verify_report(self.report), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
