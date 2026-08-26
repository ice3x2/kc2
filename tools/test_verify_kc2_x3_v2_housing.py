from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.canonical_hash import HASH_POLICY, sha256_bytes, sha256_file
from tools import generate_kc2_x3_v2_housings as generator
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
            self.assertEqual(board["key_count"], 31 if side == "left" else 39)
            self.assertEqual(board["legacy_registration_refs"], [])

    def test_hash_policy_is_explicit_newline_stable_and_content_sensitive(self) -> None:
        manifest = json.loads(generator.MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(manifest["hash_policy"], HASH_POLICY)
        self.assertEqual(self.report["hash_policy"], HASH_POLICY)
        self.assertEqual(verify_report(self.report), [])
        wrong_policy = copy.deepcopy(self.report)
        wrong_policy["hash_policy"] = "raw-sha256"
        self.assertTrue(
            any("wrong hash policy" in error for error in verify_report(wrong_policy))
        )

        with tempfile.TemporaryDirectory() as directory:
            lf_path = Path(directory) / "lf.txt"
            crlf_path = Path(directory) / "crlf.txt"
            changed_path = Path(directory) / "changed.txt"
            lf_path.write_bytes(b"alpha\nbeta\n")
            crlf_path.write_bytes(b"alpha\r\nbeta\r\n")
            changed_path.write_bytes(b"alpha\nbeta changed\n")
            self.assertEqual(sha256_file(lf_path), sha256_file(crlf_path))
            self.assertNotEqual(sha256_file(lf_path), sha256_file(changed_path))

    def test_manifest_hashes_bind_canonical_files_and_reject_staged_snapshot_mutation(self) -> None:
        manifest = json.loads(generator.MANIFEST_PATH.read_text(encoding="utf-8"))
        bound_paths: list[tuple[str, str]] = []
        for side in ("left", "right"):
            output = manifest["outputs"][side]
            bound_paths.extend(
                [
                    (output["source_board"], output["source_board_sha256"]),
                    (output["step"], output["step_sha256"]),
                ]
            )
            bound_paths.extend(
                (part["stl"], part["stl_sha256"])
                for part in output["printable_parts"]
            )

        for relative_path, expected_hash in bound_paths:
            artifact_path = generator.ROOT / relative_path
            self.assertEqual(sha256_file(artifact_path), expected_hash, relative_path)
            self.assertNotEqual(
                sha256_bytes(artifact_path.read_bytes() + b"\nCON-ARCH-006 mutation\n"),
                expected_hash,
                relative_path,
            )

        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
            (repository / ".gitattributes").write_bytes(b"*.txt text eol=lf\n")
            fixture = repository / "housing-snapshot.txt"
            fixture.write_bytes(b"source board\r\nASCII STL\r\n")
            subprocess.run(
                ["git", "add", ".gitattributes", fixture.name], cwd=repository, check=True
            )
            staged_bytes = subprocess.check_output(
                ["git", "show", f":{fixture.name}"], cwd=repository
            )
            self.assertNotEqual(fixture.read_bytes(), staged_bytes)
            self.assertEqual(sha256_file(fixture), sha256_bytes(staged_bytes))
            self.assertNotEqual(
                sha256_file(fixture),
                sha256_bytes(staged_bytes + b"CON-ARCH-006 staged mutation\n"),
            )

    def test_nominal_2_5mm_plate_and_support_regions_are_zero_gap_load_paths(self) -> None:
        for side in ("left", "right"):
            housing = self.report["sides"][side]
            self.assertEqual(housing["exterior_bottom_z_mm"], 0.0)
            self.assertEqual(housing["housing_height_mm"], 2.50)
            self.assertEqual(housing["pcb_bottom_z_mm"], 2.50)
            self.assertEqual(housing["desk_standoff_nominal_mm"], 1.00)
            self.assertEqual(housing["desk_standoff_print_tolerance_mm"], 0.30)
            self.assertEqual(housing["desk_datum_z_mm"], -1.00)
            self.assertEqual(housing["minimum_open_component_to_desk_nominal_clearance_mm"], 0.50)
            self.assertGreaterEqual(housing["minimum_open_component_to_desk_clearance_mm"], 0.50)
            self.assertTrue(housing["desk_contacts_statically_stable"])
            self.assertTrue(housing["desk_contacts_hidden_in_top_view"])
            self.assertEqual(housing["desk_contact_component_cutout_collision_count"], 0)
            for part in housing["printable_parts"]:
                self.assertGreaterEqual(part["desk_contact_count"], 3)
                self.assertEqual(part["actual_desk_contact_count"], part["desk_contact_count"])
                self.assertTrue(part["desk_contacts_match_plan"])
                self.assertEqual(part["desk_contact_z_mm"], -1.00)
                self.assertEqual(part["desk_contact_coplanarity_mm"], 0.0)
                self.assertTrue(part["projected_centroid_inside_contact_hull"])
                self.assertTrue(part["desk_contacts_statically_stable"])
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

            reset = housing["reset_local_support"]
            expected_reset_center = (
                [115.8125, 63.4500] if side == "left" else [94.3000, 63.4500]
            )
            self.assertEqual(reset["ref"], "SW_RST1")
            self.assertEqual(reset["board_center_mm"], expected_reset_center)
            self.assertEqual(reset["footprint_side"], "top")
            self.assertEqual(reset["actuator_projection_size_mm"], [1.30, 2.70])
            self.assertEqual(reset["support_diameter_mm"], 3.00)
            self.assertEqual(reset["support_top_z_mm"], 2.50)
            self.assertEqual(reset["support_vertical_gap_mm"], 0.0)
            self.assertEqual(reset["desk_column_bottom_z_mm"], -1.00)
            self.assertTrue(reset["actuator_projection_covered"])
            self.assertTrue(reset["support_surface_covered"])
            self.assertEqual(reset["component_cutout_collision_count"], 0)
            self.assertEqual(reset["bottom_exposed_pad_collision_count"], 0)
            self.assertEqual(reset["via_collision_count"], 0)
            self.assertTrue(reset["bottom_routed_copper_solder_mask_protected"])
            self.assertTrue(reset["electrically_safe"])

    def test_bottom_component_cutouts_are_exterior_open_and_3d_clear(self) -> None:
        required = {
            "choc_socket_body_fillets",
            "switch_mechanical_pins",
            "mx_pins_pads_fillets",
            "diode_body_pads_fillets",
            "controller_socket",
            "battery_body",
            "battery_slot",
        }
        for side in ("left", "right"):
            housing = self.report["sides"][side]
            cutouts = housing["component_cutouts"]
            self.assertEqual(set(cutouts), required)
            key_count = 31 if side == "left" else 39
            for name in (
                "choc_socket_body_fillets",
                "switch_mechanical_pins",
                "mx_pins_pads_fillets",
                "diode_body_pads_fillets",
            ):
                self.assertEqual(cutouts[name]["opening_count"], key_count, name)
            self.assertEqual(cutouts["controller_socket"]["opening_count"], 1)
            self.assertEqual(cutouts["battery_body"]["opening_count"], 1)
            self.assertEqual(cutouts["battery_slot"]["opening_count"], 1)
            self.assertNotIn("controller_reset", cutouts)
            self.assertNotIn("reset_topside", cutouts)
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
            self.assertEqual(cutouts["diode_body_pads_fillets"]["manufacturer"], "Jingdao Microelectronics")
            self.assertEqual(cutouts["diode_body_pads_fillets"]["mpn"], "ES1B")
            self.assertEqual(cutouts["diode_body_pads_fillets"]["lcsc"], "C437840")
            self.assertEqual(cutouts["diode_body_pads_fillets"]["official_body_depth_max_mm"], 2.20)
            self.assertEqual(cutouts["diode_body_pads_fillets"]["official_plan_envelope_max_mm"], [5.20, 2.70])
            self.assertEqual(cutouts["diode_body_pads_fillets"]["solder_fillet_allowance_mm"], 0.30)
            self.assertGreaterEqual(
                cutouts["diode_body_pads_fillets"]["minimum_plate_bottom_clearance_mm"],
                0.0,
            )
            self.assertGreaterEqual(
                cutouts["diode_body_pads_fillets"]["minimum_desk_clearance_mm"],
                0.50,
            )
            self.assertFalse(
                cutouts["diode_body_pads_fillets"]["breaks_lateral_housing_perimeter"]
            )
            self.assertGreaterEqual(
                cutouts["diode_body_pads_fillets"]["minimum_housing_perimeter_land_mm"],
                0.85,
            )
            battery = cutouts["battery_body"]
            self.assertEqual(battery["reference"], "TW301525")
            self.assertEqual(battery["board_feature"], "B.Fab:TW301525 80mAh")
            self.assertEqual(battery["nominal_plan_envelope_mm"], [15.00, 25.00])
            self.assertNotIn("official_plan_envelope_max_mm", battery)
            self.assertFalse(any(key.startswith("official_") for key in battery))
            self.assertEqual(battery["modeled_max_depth_mm"], 3.00)
            self.assertEqual(battery["cutout_allowance_mm"], 0.35)
            self.assertEqual(battery["nominal_desk_clearance_mm"], 0.50)
            self.assertFalse(battery["breaks_lateral_housing_perimeter"])
            self.assertGreaterEqual(battery["minimum_housing_perimeter_land_mm"], 0.85)
            self.assertEqual(battery["physical_tolerance_status"], "pending")

    def test_m1_4_mounting_columns_preserve_the_primary_support_network(self) -> None:
        expected_coordinates = {
            "left": [
                [142.6125, 68.0000],
                [128.6125, 86.5000],
                [100.1125, 93.5000],
                [57.1125, 99.0000],
                [133.6125, 131.5000],
                [55.1125, 144.0000],
                [165.6125, 145.0000],
                [102.6125, 147.0000],
            ],
            "right": [
                [71.6875, 68.0000],
                [181.1875, 85.5000],
                [147.6875, 93.5000],
                [109.6875, 96.5000],
                [71.6875, 105.5000],
                [42.1875, 106.0000],
                [181.1875, 134.5000],
                [143.1875, 134.5000],
                [51.6875, 144.0000],
                [95.6875, 147.0000],
            ],
        }
        expected_support_counts = {"left": 14, "right": 11}
        expected_load_spans = {"left": 15.4640, "right": 18.9619}
        expected_part_distribution = {
            "left": {"whole": 8},
            "right": {"part_a": 4, "part_b": 6},
        }

        self.assertFalse(self.report["order_ready"])
        self.assertEqual(self.report["physical_registration_status"], "pending")
        for side in ("left", "right"):
            housing = self.report["sides"][side]
            mounting = housing["mounting_system"]
            self.assertEqual(housing["registration_peg_count"], 0)
            self.assertEqual(housing["fastener_boss_count"], 0)
            self.assertEqual(housing["screw_pilot_count"], len(expected_coordinates[side]))
            self.assertEqual(len(housing["support_posts"]), expected_support_counts[side])
            self.assertEqual(mounting["distributed_support_count"], expected_support_counts[side])
            self.assertEqual(mounting["board_coordinates_mm"], expected_coordinates[side])
            self.assertEqual(mounting["part_distribution"], expected_part_distribution[side])
            self.assertTrue(mounting["board_features_match_selected_pattern"])
            self.assertTrue(mounting["part_distribution_matches_plan"])
            self.assertTrue(mounting["primary_support_load_span_unchanged"])
            self.assertEqual(mounting["physical_registration_status"], "pending")
            self.assertAlmostEqual(
                housing["maximum_load_point_to_support_mm"],
                expected_load_spans[side],
                places=4,
            )
            for hole in mounting["holes"]:
                self.assertEqual(hole["pcb_npth_diameter_mm"], 1.60)
                self.assertEqual(hole["support_land_diameter_mm"], 3.00)
                self.assertEqual(hole["support_land_annular_width_mm"], 0.95)
                self.assertEqual(hole["support_land_top_z_mm"], 2.50)
                self.assertEqual(hole["support_land_vertical_gap_mm"], 0.0)
                self.assertEqual(hole["desk_column_diameter_mm"], 3.00)
                self.assertEqual(hole["desk_column_bottom_z_mm"], -1.00)
                self.assertEqual(hole["pilot_diameter_mm"], 1.10)
                self.assertEqual(hole["pilot_depth_mm"], 2.80)
                self.assertEqual(hole["pilot_top_z_mm"], 2.50)
                self.assertEqual(hole["pilot_bottom_z_mm"], -0.30)
                self.assertEqual(hole["pilot_extension_below_plate_mm"], 0.30)
                self.assertEqual(hole["closed_bottom_to_desk_datum_mm"], 0.70)
                self.assertFalse(hole["pilot_breaks_desk_contact_bottom"])
                self.assertEqual(hole["provisional_screw_under_head_length_mm"], 4.00)
                self.assertEqual(hole["pcb_tolerance_penetration_range_mm"], [2.24, 2.56])
                self.assertEqual(hole["minimum_tip_clearance_mm"], 0.24)
                self.assertTrue(hole["step_pilot_open_at_z_2_49"])
                self.assertTrue(hole["step_pilot_open_at_z_minus_0_25"])
                self.assertTrue(hole["step_pilot_closed_at_z_minus_0_35"])
                self.assertTrue(hole["step_pilot_closed_at_z_minus_0_79"])
                self.assertTrue(hole["step_pilot_closed_at_z_minus_0_99"])
                self.assertEqual(hole["head_envelope_mm"], [2.00, 0.50])
                self.assertEqual(hole["driver_envelope_diameter_mm"], 3.00)
                self.assertEqual(hole["collision_count"], 0)

    def test_verifier_rejects_mounting_contract_mutations(self) -> None:
        mutations = (
            ("wrong mounting-hole count", lambda item: item.__setitem__("count", 9)),
            ("board coordinate", lambda item: item["board_coordinates_mm"][0].__setitem__(0, 0.0)),
            ("board MH", lambda item: item.__setitem__("board_features_match_selected_pattern", False)),
            ("mounting manifest", lambda item: item.__setitem__("manifest_matches_generator", False)),
            ("physical registration", lambda item: item.__setitem__("physical_registration_status", "verified")),
            ("PCB NPTH", lambda item: item["holes"][0].__setitem__("pcb_npth_diameter_mm", 1.7)),
            ("support land", lambda item: item["holes"][0].__setitem__("support_land_diameter_mm", 2.9)),
            ("support land", lambda item: item["holes"][0].__setitem__("support_land_vertical_gap_mm", 0.1)),
            ("support land", lambda item: item["holes"][0].__setitem__("desk_column_bottom_z_mm", -0.7)),
            ("pilot diameter", lambda item: item["holes"][0].__setitem__("pilot_diameter_mm", 1.2)),
            ("pilot depth", lambda item: item["holes"][0].__setitem__("pilot_depth_mm", 2.7)),
            ("pilot depth", lambda item: item["holes"][0].__setitem__("closed_bottom_to_desk_datum_mm", 0.4)),
            ("pilot bottom break", lambda item: item["holes"][0].__setitem__("pilot_breaks_desk_contact_bottom", True)),
            ("pilot STEP depth", lambda item: item["holes"][0].__setitem__("step_pilot_closed_at_z_minus_0_35", False)),
            ("provisional screw penetration", lambda item: item["holes"][0].__setitem__("provisional_screw_under_head_length_mm", 3.0)),
            ("provisional screw penetration", lambda item: item["holes"][0].__setitem__("pcb_tolerance_penetration_range_mm", [1.0, 1.1])),
            ("provisional screw penetration", lambda item: item["holes"][0].__setitem__("minimum_tip_clearance_mm", 0.1)),
            ("head envelope", lambda item: item["holes"][0].__setitem__("head_envelope_mm", [2.1, 0.5])),
            ("driver envelope", lambda item: item["holes"][0].__setitem__("driver_envelope_diameter_mm", 2.9)),
            ("service condition", lambda item: item["holes"][0].__setitem__("service_condition", "switches-removed")),
            ("mounting collision", lambda item: item["holes"][0].__setitem__("collision_count", 1)),
            ("mounting collision", lambda item: item["holes"][0].__setitem__("geometry_collision_count", 1)),
            ("part distribution", lambda item: item.__setitem__("part_distribution", {"part_a": 10})),
            ("distributed support", lambda item: item.__setitem__("distributed_support_count", 10)),
            ("load span", lambda item: item.__setitem__("primary_support_load_span_unchanged", False)),
        )
        for expected_error, mutate in mutations:
            with self.subTest(expected_error=expected_error):
                report = copy.deepcopy(self.report)
                mutate(report["sides"]["right"]["mounting_system"])
                self.assertTrue(
                    any(expected_error in error for error in verify_report(report)),
                    verify_report(report),
                )

        report = copy.deepcopy(self.report)
        report["order_ready"] = True
        self.assertTrue(any("order readiness" in error for error in verify_report(report)))
        report = copy.deepcopy(self.report)
        report["physical_registration_status"] = "verified"
        self.assertTrue(any("physical registration" in error for error in verify_report(report)))

        report = copy.deepcopy(self.report)
        report["sides"]["right"]["reset_local_support"]["electrically_safe"] = False
        self.assertTrue(any("reset local support" in error for error in verify_report(report)))

        report = copy.deepcopy(self.report)
        report["sides"]["right"]["component_cutouts"]["battery_body"][
            "minimum_housing_perimeter_land_mm"
        ] = 0.84
        self.assertTrue(any("battery perimeter land" in error for error in verify_report(report)))

        report = copy.deepcopy(self.report)
        battery = report["sides"]["right"]["component_cutouts"]["battery_body"]
        battery["official_plan_envelope_max_mm"] = battery["nominal_plan_envelope_mm"]
        self.assertTrue(any("forbidden official" in error for error in verify_report(report)))

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
            "controller_socket",
            "reset_topside",
            "battery_body",
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
        diode["breaks_lateral_housing_perimeter"] = True
        diode["minimum_housing_perimeter_land_mm"] = 0.0
        diode["residual_collision_volume_mm3"] = 0.1
        diode["minimum_plate_bottom_clearance_mm"] = -0.1
        diode["minimum_desk_clearance_mm"] = 0.4
        errors = verify_report(report)
        self.assertTrue(any("diode_body_pads_fillets opening count" in error for error in errors))
        self.assertTrue(any("diode_body_pads_fillets is not exterior-open" in error for error in errors))
        self.assertTrue(any("diode cutout breaks the lateral perimeter" in error for error in errors))
        self.assertTrue(any("diode perimeter land" in error for error in errors))
        self.assertTrue(any("diode_body_pads_fillets 3D collision" in error for error in errors))
        self.assertTrue(any("diode plate-bottom clearance" in error for error in errors))
        self.assertTrue(any("diode desk clearance" in error for error in errors))

    def test_verifier_rejects_missing_or_unstable_desk_contacts(self) -> None:
        report = copy.deepcopy(self.report)
        left = report["sides"]["left"]
        left["desk_standoff_nominal_mm"] = 0.8
        left["minimum_open_component_to_desk_clearance_mm"] = 0.4
        left["desk_contacts_statically_stable"] = False
        left["desk_contact_component_cutout_collision_count"] = 1
        left["printable_parts"][0]["desk_contact_count"] = 2
        left["printable_parts"][0]["actual_desk_contact_count"] = 2
        left["printable_parts"][0]["desk_contacts_statically_stable"] = False
        errors = verify_report(report)
        self.assertTrue(any("desk standoff" in error for error in errors))
        self.assertTrue(any("open-component-to-desk clearance" in error for error in errors))
        self.assertTrue(any("desk contact collides" in error for error in errors))
        self.assertTrue(any("desk contacts are not statically stable" in error for error in errors))

    def test_verifier_rejects_coupled_vertical_clearance_overstatement(self) -> None:
        report = copy.deepcopy(self.report)
        for side in ("left", "right"):
            housing = report["sides"][side]
            housing["minimum_open_component_to_desk_nominal_clearance_mm"] = 9.9
            housing["minimum_open_component_to_desk_clearance_mm"] = 9.6
            diode = housing["component_cutouts"]["diode_body_pads_fillets"]
            diode["minimum_plate_bottom_clearance_mm"] = 9.1
            diode["nominal_desk_clearance_mm"] = 9.9
            diode["minimum_desk_clearance_mm"] = 9.6
        errors = verify_report(report)
        self.assertTrue(any("diode plate-bottom clearance formula" in error for error in errors))
        self.assertTrue(any("diode nominal desk-clearance formula" in error for error in errors))
        self.assertTrue(any("diode worst-case desk-clearance formula" in error for error in errors))
        self.assertTrue(any("open-component nominal desk-clearance formula" in error for error in errors))
        self.assertTrue(any("open-component worst-case desk-clearance formula" in error for error in errors))

    def test_verifier_rejects_coupled_contact_count_and_manifest_binding_mutation(self) -> None:
        report = copy.deepcopy(self.report)
        left = report["sides"]["left"]
        left["desk_contact_manifest_matches_generator"] = False
        part = left["printable_parts"][0]
        part["desk_contact_count"] -= 1
        part["actual_desk_contact_count"] -= 1
        part["manifest_desk_contact_ids"] = part["manifest_desk_contact_ids"][:-1]
        part["desk_contacts_match_plan"] = True
        part["desk_contacts_statically_stable"] = True
        errors = verify_report(report)
        self.assertTrue(any("desk-contact manifest differs from generator" in error for error in errors))
        self.assertTrue(any("planned desk-contact count is stale" in error for error in errors))
        self.assertTrue(any("STL desk-contact count is stale" in error for error in errors))
        self.assertTrue(any("desk-contact IDs differ from plan" in error for error in errors))

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
            self.assertAlmostEqual(housing["step_bounds_z_mm"][0], -1.00, places=4)
            self.assertAlmostEqual(housing["step_bounds_z_mm"][1], 2.50, places=4)
            self.assertTrue(housing["step_top_contact_area_matches_plan"])
            self.assertLessEqual(housing["step_top_contact_area_error_mm2"], 0.20)
        self.assertEqual(self.report["physical_deflection_test"]["status"], "pending")
        self.assertFalse(self.report["fabrication_or_order_ready"])
        expected_blocker = (
            "CON-ARCH-006 AC-7 physical coupon evidence is pending: exact screw MPN and "
            "drawing; minimum and maximum head diameter and height; maximum finished PCB-hole "
            "diameter and minimum radial bearing width or equivalent pull-through/clamp-retention "
            "evidence; exact driver MPN, maximum shaft diameter, and runout; printed pilot "
            "diameter, actual PCB thickness, installed penetration, and tip clearance; tapping "
            "torque, stripping torque with at least 2.0 ratio and 3.0 target, and selected "
            "installation torque; ten install/remove cycles without cracking, spin, or pull-out; "
            "full-pattern assembly without sequential forcing; actual installed switch and "
            "keycap-skirt clearance; and a 2.0 N deflection test at every worst-case support span "
            "with no more than 0.30 mm displacement, rocking, permanent deformation, support "
            "disengagement, or fastener loosening. CON-ARCH-006 AC-11 controller-service "
            "physical evidence is also pending: exact reset supplier Z/travel/force/reflow limits, "
            "actual socketed-controller and nonconductive-probe service, USB shell/cable clearance, "
            "ten successful double-reset cycles and bootloader enumeration, plus battery maximum "
            "thickness/swelling, adhesive retention, lead bend, strain relief, abrasion protection, "
            "actual placement tolerance, and desk clearance."
        )
        self.assertEqual(self.report["order_readiness_blocker"], expected_blocker)
        mutated = copy.deepcopy(self.report)
        mutated["order_readiness_blocker"] = (
            "CON-ARCH-006 AC-7 physical 2.0 N deflection evidence is pending."
        )
        self.assertTrue(
            any("order-readiness blocker" in error for error in verify_report(mutated))
        )
        self.assertEqual(verify_report(self.report), [])
        srs = (generator.ROOT / "docs/spec/10.product-architecture.srs.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Seventeen focused housing tests pass", srs)
        self.assertNotIn("Fourteen focused housing tests pass", srs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
