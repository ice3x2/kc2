from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.canonical_hash import HASH_POLICY, sha256_bytes, sha256_file
from tools import generate_kc2_x3_v2_housings as generator
from tools import verify_kc2_x3_v2_housing as housing_verifier
from tools.verify_kc2_x3_v2_housing import analyze_v2_housing, verify_report


class ServiceInterfaceContractUnitTests(unittest.TestCase):
    @staticmethod
    def _part_plans(shp: dict[str, object], side: str, plan: dict[str, object]) -> list[object]:
        if side == "left":
            return [plan["support_surface"]]
        split = generator.build_right_split_plan(shp, plan)
        return [split["part_a_plan"], split["part_b_plan"]]

    def test_housing_manifest_traces_all_active_mechanical_requirements(self) -> None:
        manifest = json.loads(generator.MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["requirement_ids"],
            ["CON-ARCH-006", "CON-ARCH-007", "REL-ARCH-001"],
        )

    def test_reset_support_centers_match_final_mirrored_service_layout(self) -> None:
        self.assertEqual(
            housing_verifier.VERIFIED_RESET_CENTERS_MM,
            {
                "left": [126.0625, 63.4500],
                "right": [84.0500, 63.4500],
            },
        )

    def test_j_bat1_requires_two_plated_pth_envelopes_inside_the_union_cutout(self) -> None:
        pads = [
            {
                "number": "1",
                "is_plated_through_hole": True,
                "shape": "circle",
                "drill_mm": [1.0, 1.0],
                "size_mm": [2.20, 2.20],
                "center": [0.0, 0.0],
            },
            {
                "number": "2",
                "is_plated_through_hole": True,
                "shape": "circle",
                "drill_mm": [1.0, 1.0],
                "size_mm": [2.20, 2.20],
                "center": [2.54, 0.0],
            },
        ]
        contract = generator.validate_battery_termination_pad_records("unit", pads)
        self.assertEqual(contract["pad_count"], 2)
        self.assertEqual(contract["plated_pth_count"], 2)
        self.assertEqual(contract["required_pad_envelope_count"], 2)
        self.assertTrue(contract["cutout_envelopes_overlap"])
        self.assertEqual(contract["expected_union_opening_count"], 1)
        self.assertNotIn("required_opening_count", contract)

        for mutate in (
            lambda items: items.pop(),
            lambda items: items[0].__setitem__("is_plated_through_hole", False),
        ):
            with self.subTest(mutate=mutate):
                invalid = copy.deepcopy(pads)
                mutate(invalid)
                with self.assertRaises(RuntimeError):
                    generator.validate_battery_termination_pad_records("unit", invalid)

    def test_sw_pwr1_requires_three_round_plated_080_pth_at_254_pitch(self) -> None:
        pads = [
            {
                "number": str(index + 1),
                "is_plated_through_hole": True,
                "shape": "circle",
                "drill_mm": [0.80, 0.80],
                "center": [index * 2.54, 0.0],
            }
            for index in range(3)
        ]
        contract = generator.validate_power_switch_pad_records("unit", pads)
        self.assertEqual(contract["pad_count"], 3)
        self.assertTrue(contract["all_round_plated_pth"])
        self.assertEqual(contract["drill_diameter_mm"], 0.80)
        self.assertEqual(contract["pitch_mm"], 2.54)

        mutations = (
            lambda items: items.pop(),
            lambda items: items[0].__setitem__("is_plated_through_hole", False),
            lambda items: items[0].__setitem__("shape", "oval"),
            lambda items: items[0].__setitem__("drill_mm", [0.80, 0.90]),
            lambda items: items[2].__setitem__("center", [5.20, 0.0]),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                invalid = copy.deepcopy(pads)
                mutate(invalid)
                with self.assertRaises(RuntimeError):
                    generator.validate_power_switch_pad_records("unit", invalid)

    def test_bat1_extraction_is_side_specific_and_source_bound(self) -> None:
        for side, center in (
            ("left", [131.7125, 50.7500]),
            ("right", [78.4000, 50.7500]),
        ):
            with self.subTest(side=side):
                record = {
                    "ref": "BAT1",
                    "center": center,
                    "size_mm": [30.0, 12.0],
                    "modeled_depth_mm": 3.0,
                    "housing_body_cutout": False,
                }
                bound = generator.bind_battery_extraction_record(
                    side,
                    record,
                    f"hardware/{side}.kicad_pcb",
                    f"{side}-sha256",
                )
                self.assertEqual(bound["side"], side)
                self.assertEqual(bound["center"], center)
                self.assertEqual(bound["source_board_sha256"], f"{side}-sha256")

                wrong = copy.deepcopy(record)
                wrong["center"][0] += 0.1
                with self.assertRaises(RuntimeError):
                    generator.bind_battery_extraction_record(
                        side,
                        wrong,
                        f"hardware/{side}.kicad_pcb",
                        f"{side}-sha256",
                    )

    def test_every_service_opening_has_a_perimeter_and_structure_land_gate(self) -> None:
        for name in ("battery_termination", "power_switch_leads", "battery_slot"):
            with self.subTest(name=name):
                valid = {
                    "breaks_lateral_housing_perimeter": False,
                    "minimum_housing_perimeter_land_mm": 0.85,
                    "perimeter_land_matches_manifest": True,
                }
                self.assertEqual(
                    housing_verifier.service_cutout_contract_errors("left", name, valid),
                    [],
                )
                invalid = copy.deepcopy(valid)
                invalid["breaks_lateral_housing_perimeter"] = True
                invalid["minimum_housing_perimeter_land_mm"] = 0.0
                invalid["perimeter_land_matches_manifest"] = False
                errors = housing_verifier.service_cutout_contract_errors(
                    "left", name, invalid
                )
                self.assertTrue(any("breaks the lateral perimeter" in error for error in errors))
                self.assertTrue(any("structural land" in error for error in errors))
                self.assertTrue(any("manifest is stale" in error for error in errors))

    def test_order_blocker_names_rel_arch_001_transition_radio_and_charging_gates(self) -> None:
        blocker = housing_verifier.ORDER_READINESS_BLOCKER
        for required in (
            "REL-ARCH-001",
            "20 cold OFF-to-ON",
            "RSSI",
            "packet-loss",
            "USB charging",
            "non-countersunk rounded pan/button",
            "keycap-skirt rest/full-travel",
        ):
            self.assertIn(required, blocker)

    def test_rounded_head_p1_contract_keeps_independent_quarter_mm_reserves(self) -> None:
        shp = generator.legacy_geometry.require_shapely()
        boards = generator.run_extractor(
            generator.legacy_geometry.locate_kicad_python()
        )["boards"]
        for side in ("left", "right"):
            plan = generator.build_plan_geometry(shp, side, boards[side])
            mounting = generator.mounting_system_manifest(
                shp,
                side,
                plan,
                self._part_plans(shp, side, plan),
            )
            self.assertEqual(
                mounting["fastener_head_style"],
                "non_countersunk_rounded_pan_or_button",
            )
            self.assertEqual(mounting["head_envelope_mm"], [3.00, 1.20])
            self.assertEqual(mounting["head_reserve_mm"], 0.25)
            self.assertIsNone(mounting["analytical_rail_relief"])
            self.assertEqual(
                mounting["head_height_and_keycap_skirt_physical_status"],
                "pending",
            )
            for hole in mounting["holes"]:
                self.assertEqual(hole["head_envelope_mm"], [3.00, 1.20])
                for field in (
                    "head_to_installed_component_mm",
                    "head_to_routed_copper_or_via_mm",
                    "head_to_board_edge_mm",
                    "head_to_housing_edge_mm",
                    "head_to_existing_support_mm",
                    "head_to_analytical_rail_mm",
                ):
                    self.assertGreaterEqual(hole[field] + 1e-6, 0.25, field)

        report = json.loads(housing_verifier.REPORT_PATH.read_text(encoding="utf-8"))
        report["sides"]["right"]["mounting_system"]["holes"][0][
            "head_to_installed_component_mm"
        ] = 0.249
        self.assertTrue(
            any("head reserve" in error for error in verify_report(report)),
            verify_report(report),
        )

    def test_mounting_driver_checks_full_battery_and_power_body_sweep_mutations(self) -> None:
        shp = generator.legacy_geometry.require_shapely()
        boards = generator.run_extractor(
            generator.legacy_geometry.locate_kicad_python()
        )["boards"]
        expected_checks = {
            "driver_battery_body",
            "driver_power_switch_body",
            "driver_power_switch_actuator_sweep",
        }
        for side in ("left", "right"):
            plan = generator.build_plan_geometry(shp, side, boards[side])
            mounting = generator.mounting_system_manifest(
                shp,
                side,
                plan,
                self._part_plans(shp, side, plan),
            )
            for hole in mounting["holes"]:
                self.assertTrue(expected_checks.issubset(hole["collision_checks"]))
                self.assertGreaterEqual(hole["driver_to_battery_body_mm"], 0.0)
                self.assertGreaterEqual(hole["driver_to_power_switch_body_mm"], 0.0)
                self.assertGreaterEqual(
                    hole["driver_to_power_switch_actuator_sweep_mm"],
                    0.0,
                )

            ref, mount_x, mount_y = generator.MOUNTING_HOLE_COORDINATES_MM[side][0]
            self.assertEqual(ref, "MH1")

            battery_mutation = copy.deepcopy(boards[side])
            battery_mutation["battery_above_carrier"]["center"] = [mount_x, mount_y]
            battery_mutation["battery_above_carrier"]["bounds"] = [
                mount_x - 15.0,
                mount_y - 6.0,
                mount_x + 15.0,
                mount_y + 6.0,
            ]
            battery_plan = generator.build_plan_geometry(shp, side, battery_mutation)
            battery_mounting = generator.mounting_system_manifest(
                shp,
                side,
                battery_plan,
                self._part_plans(shp, side, battery_plan),
            )
            battery_hole = next(
                item for item in battery_mounting["holes"] if item["ref"] == "MH1"
            )
            self.assertTrue(battery_hole["collision_checks"]["driver_battery_body"])

            power_mutation = copy.deepcopy(boards[side])
            power_mutation["power_switch_topside"]["center"] = [mount_x, mount_y]
            power_plan = generator.build_plan_geometry(shp, side, power_mutation)
            power_mounting = generator.mounting_system_manifest(
                shp,
                side,
                power_plan,
                self._part_plans(shp, side, power_plan),
            )
            power_hole = next(
                item for item in power_mounting["holes"] if item["ref"] == "MH1"
            )
            self.assertTrue(power_hole["collision_checks"]["driver_power_switch_body"])
            self.assertTrue(
                power_hole["collision_checks"]["driver_power_switch_actuator_sweep"]
            )

    def test_reset_projection_metadata_follows_actual_board_rotation(self) -> None:
        manifest = json.loads(generator.MANIFEST_PATH.read_text(encoding="utf-8"))
        expected_rotations = {"left": 0.0, "right": 180.0}
        for side, rotation in expected_rotations.items():
            reset = manifest["outputs"][side]["reset_local_support"]
            self.assertEqual(reset["footprint_rotation_deg"], rotation)
            self.assertEqual(reset["actuator_projection_size_mm"], [2.7, 1.3])

        report = json.loads(housing_verifier.REPORT_PATH.read_text(encoding="utf-8"))
        report["sides"]["left"]["reset_local_support"][
            "actuator_projection_size_mm"
        ] = [1.3, 2.7]
        self.assertTrue(
            any("actuator projection" in error for error in verify_report(report)),
            verify_report(report),
        )

    def test_reset_support_derives_bottom_mask_protection_and_rejects_exposure(self) -> None:
        manifest = json.loads(generator.MANIFEST_PATH.read_text(encoding="utf-8"))
        for side in ("left", "right"):
            reset = manifest["outputs"][side]["reset_local_support"]
            self.assertEqual(reset["bottom_routed_copper_overlap_count"], 0)
            self.assertEqual(reset["bottom_mask_opening_overlap_count"], 0)
            self.assertEqual(reset["bottom_exposed_routed_copper_overlap_count"], 0)
            self.assertEqual(
                reset["bottom_routed_copper_solder_mask_protection_basis"],
                "derived_from_exact_B.Cu_and_B.Mask_geometry",
            )

        shp = generator.legacy_geometry.require_shapely()
        boards = generator.run_extractor(
            generator.legacy_geometry.locate_kicad_python()
        )["boards"]
        mutated = copy.deepcopy(boards["left"])
        reset_x, reset_y = mutated["reset_topside"]["center"]
        mutated["routed_copper_exact"].append(
            {
                "kind": "line",
                "start": [reset_x - 2.0, reset_y],
                "end": [reset_x + 2.0, reset_y],
                "radius_mm": 0.125,
                "net": "MUTATED_EXPOSED_BCU",
                "layer": "B.Cu",
            }
        )
        mutated["bottom_mask_openings"].append(
            {
                "kind": "circle",
                "center": [reset_x, reset_y],
                "radius_mm": 0.75,
                "source": "mutation",
            }
        )
        with self.assertRaisesRegex(RuntimeError, "reset local support is not electrically safe"):
            generator.build_plan_geometry(shp, "left", mutated)


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
            self.assertEqual(housing["minimum_open_component_to_desk_nominal_clearance_mm"], 1.00)
            self.assertEqual(housing["minimum_open_component_to_desk_clearance_mm"], 0.70)
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
                [126.0625, 63.4500] if side == "left" else [84.0500, 63.4500]
            )
            self.assertEqual(reset["ref"], "SW_RST1")
            self.assertEqual(reset["board_center_mm"], expected_reset_center)
            self.assertEqual(reset["footprint_side"], "top")
            self.assertEqual(reset["actuator_projection_size_mm"], [2.70, 1.30])
            self.assertEqual(
                reset["footprint_rotation_deg"],
                0.0 if side == "left" else 180.0,
            )
            self.assertEqual(reset["support_diameter_mm"], 3.00)
            self.assertEqual(reset["support_top_z_mm"], 2.50)
            self.assertEqual(reset["support_vertical_gap_mm"], 0.0)
            self.assertEqual(reset["desk_column_bottom_z_mm"], -1.00)
            self.assertTrue(reset["actuator_projection_covered"])
            self.assertTrue(reset["support_surface_covered"])
            self.assertEqual(reset["component_cutout_collision_count"], 0)
            self.assertEqual(reset["bottom_exposed_pad_collision_count"], 0)
            self.assertEqual(reset["via_collision_count"], 0)
            self.assertEqual(reset["bottom_exposed_routed_copper_overlap_count"], 0)
            self.assertTrue(reset["bottom_routed_copper_solder_mask_protected"])
            self.assertTrue(reset["electrically_safe"])

    def test_bottom_component_cutouts_are_exterior_open_and_3d_clear(self) -> None:
        required = {
            "choc_socket_body_fillets",
            "switch_mechanical_pins",
            "mx_pins_pads_fillets",
            "diode_body_pads_fillets",
            "controller_socket",
            "battery_termination",
            "power_switch_leads",
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
            self.assertEqual(cutouts["battery_termination"]["opening_count"], 1)
            self.assertEqual(cutouts["power_switch_leads"]["opening_count"], 1)
            self.assertEqual(cutouts["battery_slot"]["opening_count"], 1)
            self.assertNotIn("battery_body", cutouts)
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
            termination = cutouts["battery_termination"]
            self.assertEqual(termination["reference"], "J_BAT1")
            self.assertEqual(termination["pad_count"], 2)
            self.assertEqual(termination["plated_pth_count"], 2)
            self.assertEqual(termination["required_pad_envelope_count"], 2)
            self.assertTrue(termination["cutout_envelopes_overlap"])
            self.assertEqual(termination["expected_union_opening_count"], 1)
            self.assertEqual(termination["pad_envelope_count"], 2)
            self.assertEqual(termination["covered_pad_envelope_count"], 2)
            self.assertEqual(termination["uncovered_pad_envelope_count"], 0)
            self.assertEqual(termination["opening_count"], 1)
            self.assertTrue(termination["exterior_open"])
            self.assertEqual(termination["residual_collision_volume_mm3"], 0.0)
            power = cutouts["power_switch_leads"]
            self.assertEqual(power["reference"], "SW_PWR1")
            self.assertEqual(power["opening_count"], 1)
            self.assertEqual(power["pad_count"], 3)
            self.assertTrue(power["all_round_plated_pth"])
            self.assertEqual(power["drill_count"], 3)
            self.assertEqual(power["drill_diameter_mm"], 0.80)
            self.assertEqual(power["pitch_mm"], 2.54)
            for name in ("battery_termination", "power_switch_leads", "battery_slot"):
                service = cutouts[name]
                self.assertFalse(service["breaks_lateral_housing_perimeter"])
                self.assertGreaterEqual(
                    service["minimum_housing_perimeter_land_mm"],
                    generator.MIN_SERVICE_HOUSING_PERIMETER_LAND_MM,
                )
                self.assertTrue(service["perimeter_land_matches_manifest"])
            battery = housing["battery_above_carrier"]
            self.assertEqual(battery["ref"], "BAT1")
            self.assertEqual(
                battery["center"],
                [131.7125, 50.7500] if side == "left" else [78.4000, 50.7500],
            )
            self.assertEqual(battery["size_mm"], [30.0, 12.0])
            self.assertEqual(battery["modeled_depth_mm"], 3.0)
            self.assertFalse(battery["housing_body_cutout"])
            self.assertTrue(battery["fresh_extraction_manifest_binding"])

    def test_m1_4_clamps_clear_components_and_every_key_has_a_local_load_path(self) -> None:
        expected_coordinates = {
            "left": [
                [112.8625, 43.0000],
                [144.1125, 66.2500],
                [38.6125, 111.0000],
                [63.6125, 123.0000],
                [81.1125, 151.7500],
                [137.3625, 153.5000],
                [166.3625, 148.7500],
            ],
            "right": [
                [97.0625, 43.2500],
                [72.4375, 67.0000],
                [169.9375, 95.2500],
                [194.9375, 98.7500],
                [156.1875, 112.5000],
                [69.9375, 146.2500],
                [97.4375, 152.0000],
                [122.6875, 151.0000],
            ],
        }
        expected_support_counts = {"left": 31, "right": 39}
        expected_load_spans = {"left": 3.5621, "right": 3.5621}
        expected_part_distribution = {
            "left": {"whole": 7},
            "right": {"part_a": 4, "part_b": 4},
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
            self.assertEqual(housing["key_count"], expected_support_counts[side])
            self.assertTrue(housing["all_key_loads_have_dedicated_support"])
            self.assertEqual(
                {post["switch_ref"] for post in housing["support_posts"]},
                {f"SW{index}" for index in range(1, housing["key_count"] + 1)},
            )
            self.assertTrue(
                all(post["category"] == "key_load" for post in housing["support_posts"])
            )
            self.assertLessEqual(
                max(post["load_point_to_support_edge_mm"] for post in housing["support_posts"]),
                3.60,
            )
            self.assertEqual(mounting["distributed_support_count"], expected_support_counts[side])
            self.assertEqual(mounting["board_coordinates_mm"], expected_coordinates[side])
            self.assertEqual(mounting["part_distribution"], expected_part_distribution[side])
            self.assertTrue(mounting["board_features_match_selected_pattern"])
            self.assertTrue(mounting["part_distribution_matches_plan"])
            self.assertTrue(mounting["primary_support_load_span_unchanged"])
            self.assertEqual(mounting["physical_registration_status"], "pending")
            self.assertEqual(
                mounting["fastener_head_style"],
                "non_countersunk_rounded_pan_or_button",
            )
            self.assertEqual(mounting["head_envelope_mm"], [3.00, 1.20])
            self.assertEqual(
                mounting["head_height_and_keycap_skirt_physical_status"],
                "pending",
            )
            self.assertAlmostEqual(
                housing["maximum_load_point_to_support_mm"],
                expected_load_spans[side],
                places=4,
            )
            for hole in mounting["holes"]:
                self.assertGreaterEqual(hole["head_to_installed_component_mm"], 1.20)
                self.assertGreaterEqual(hole["head_to_routed_copper_or_via_mm"], 0.85)
                self.assertGreaterEqual(hole["head_to_board_edge_mm"], 2.10)
                self.assertGreaterEqual(hole["head_to_housing_edge_mm"], 2.00)
                self.assertGreaterEqual(hole["head_to_support_posts_mm"], 3.70)
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
                self.assertEqual(hole["head_envelope_mm"], [3.00, 1.20])
                self.assertEqual(hole["driver_envelope_diameter_mm"], 3.00)
                self.assertEqual(hole["collision_count"], 0)

    def test_verifier_rejects_mounting_contract_mutations(self) -> None:
        mutations = (
            ("wrong mounting-hole count", lambda item: item.__setitem__("count", 9)),
            ("board coordinate", lambda item: item["board_coordinates_mm"][0].__setitem__(0, 0.0)),
            ("board MH", lambda item: item.__setitem__("board_features_match_selected_pattern", False)),
            ("mounting manifest", lambda item: item.__setitem__("manifest_matches_generator", False)),
            ("physical registration", lambda item: item.__setitem__("physical_registration_status", "verified")),
            ("fastener head style", lambda item: item.__setitem__("fastener_head_style", "low_head")),
            ("mounting head envelope", lambda item: item.__setitem__("head_envelope_mm", [2.0, 0.5])),
            ("mounting head reserve", lambda item: item.__setitem__("head_reserve_mm", 0.0)),
            ("head height/keycap-skirt", lambda item: item.__setitem__("head_height_and_keycap_skirt_physical_status", "verified")),
            ("obsolete analytical rail relief", lambda item: item.__setitem__("analytical_rail_relief", {"ref": "MH9"})),
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
            ("head envelope", lambda item: item["holes"][0].__setitem__("head_envelope_mm", [2.0, 0.5])),
            ("head reserve", lambda item: item["holes"][0].__setitem__("head_to_installed_component_mm", 0.249)),
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

        for forbidden_style in (
            "low_head",
            "ultra_low_head",
            "flat_head",
            "countersunk",
        ):
            with self.subTest(forbidden_style=forbidden_style):
                report = copy.deepcopy(self.report)
                report["sides"]["right"]["mounting_system"][
                    "fastener_head_style"
                ] = forbidden_style
                self.assertTrue(
                    any("fastener head style" in error for error in verify_report(report)),
                    verify_report(report),
                )

        report = copy.deepcopy(self.report)
        report["sides"]["right"]["mounting_system"]["holes"][0][
            "geometry_collision_checks"
        ].pop("head_installed_component_reserve", None)
        self.assertTrue(
            any("head reserve checks" in error for error in verify_report(report)),
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
        report["sides"]["right"]["component_cutouts"]["power_switch_leads"][
            "residual_collision_volume_mm3"
        ] = 0.1
        self.assertTrue(any("power_switch_leads 3D collision" in error for error in verify_report(report)))

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
            "battery_termination",
            "power_switch_leads",
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

    def test_verifier_rejects_service_pad_opening_binding_and_land_mutations(self) -> None:
        mutations = (
            (
                "J_BAT1 does not contain exactly two pads",
                lambda report: report["sides"]["left"]["component_cutouts"][
                    "battery_termination"
                ].__setitem__("pad_count", 1),
            ),
            (
                "J_BAT1 pads are not both plated PTH",
                lambda report: report["sides"]["left"]["component_cutouts"][
                    "battery_termination"
                ].__setitem__("plated_pth_count", 1),
            ),
            (
                "battery_termination opening count",
                lambda report: report["sides"]["left"]["component_cutouts"][
                    "battery_termination"
                ].__setitem__("opening_count", 2),
            ),
            (
                "J_BAT1 lead/solder envelopes are not all covered",
                lambda report: report["sides"]["left"]["component_cutouts"][
                    "battery_termination"
                ].__setitem__("covered_pad_envelope_count", 1),
            ),
            (
                "J_BAT1 union opening contract",
                lambda report: report["sides"]["left"]["component_cutouts"][
                    "battery_termination"
                ].__setitem__("expected_union_opening_count", 2),
            ),
            (
                "power-switch pads are not round plated PTH",
                lambda report: report["sides"]["right"]["component_cutouts"][
                    "power_switch_leads"
                ].__setitem__("all_round_plated_pth", False),
            ),
            (
                "power-switch pad pitch",
                lambda report: report["sides"]["right"]["component_cutouts"][
                    "power_switch_leads"
                ].__setitem__("pitch_mm", 2.50),
            ),
            (
                "above-carrier BAT1 center",
                lambda report: report["sides"]["right"]["battery_above_carrier"].__setitem__(
                    "center", [78.5, 50.75]
                ),
            ),
            (
                "BAT1 extraction-manifest binding",
                lambda report: report["sides"]["right"]["battery_above_carrier"].__setitem__(
                    "fresh_extraction_manifest_binding", False
                ),
            ),
        )
        for expected_error, mutate in mutations:
            with self.subTest(expected_error=expected_error):
                report = copy.deepcopy(self.report)
                mutate(report)
                self.assertTrue(
                    any(expected_error in error for error in verify_report(report)),
                    verify_report(report),
                )

        for name in ("battery_termination", "power_switch_leads", "battery_slot"):
            with self.subTest(perimeter=name):
                report = copy.deepcopy(self.report)
                cutout = report["sides"]["left"]["component_cutouts"][name]
                cutout["breaks_lateral_housing_perimeter"] = True
                cutout["minimum_housing_perimeter_land_mm"] = 0.0
                cutout["perimeter_land_matches_manifest"] = False
                errors = verify_report(report)
                self.assertTrue(
                    any(f"{name} cutout breaks the lateral perimeter" in error for error in errors)
                )
                self.assertTrue(any(f"{name} structural land" in error for error in errors))
                self.assertTrue(
                    any(f"{name} perimeter-land manifest is stale" in error for error in errors)
                )

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
            "evidence; confirmation that the provisional 3.00 x 1.20 mm non-countersunk "
            "rounded pan/button head envelope bounds the selected part; exact driver MPN, "
            "maximum shaft diameter, and runout; printed pilot "
            "diameter, actual PCB thickness, installed penetration, and tip clearance; tapping "
            "torque, stripping torque with at least 2.0 ratio and 3.0 target, and selected "
            "installation torque; ten install/remove cycles without cracking, spin, or pull-out; "
            "full-pattern assembly without sequential forcing; actual installed switch and "
            "keycap-skirt rest/full-travel clearance under the measured head height; and a 2.0 N "
            "deflection test at every worst-case support span "
            "with no more than 0.30 mm displacement, rocking, permanent deformation, support "
            "disengagement, or fastener loosening. CON-ARCH-006 AC-11 controller-service "
            "physical evidence is also pending: exact reset supplier Z/travel/force/reflow limits, "
            "actual socketed-controller and nonconductive-probe service, USB shell/cable clearance, "
            "ten successful double-reset cycles and bootloader enumeration, plus exact protected-pack "
            "MPN, maximum swollen thickness, socket/controller stack clearance, insulation, lead bend, "
            "strain relief, J_BAT1/IMMS solder protrusion, and actual POWER/RESET access. "
            "REL-ARCH-001 AC-3/4/5 evidence is also pending: 20 cold OFF-to-ON and 20 "
            "ON-to-OFF transitions at each required pack voltage, final-assembly RSSI and "
            "packet-loss/disconnect A/B limits, and battery-only, USB charging, charge-complete, "
            "and USB-unplug state coverage."
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
        con_arch_006 = srs.split("### CON-ARCH-006", 1)[1].split("### CON-ARCH-007", 1)[0]
        self.assertIn("| VE-3 | current-mount-housing-cad |", con_arch_006)
        self.assertIn("Physical validation remains required; order_ready=false", con_arch_006)
        self.assertIn("`order_ready` and `fabrication_or_order_ready` remain false", con_arch_006)


if __name__ == "__main__":
    unittest.main(verbosity=2)
