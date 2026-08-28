from __future__ import annotations

import json
import re
import unittest
import shutil
import struct
import subprocess
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from tools.canonical_hash import HASH_POLICY, sha256_bytes, sha256_file

from tools.verify_kc2_x3_v2 import (
    analyze_v2_board,
    analyze_v2_footprint,
    analyze_v2_manifest,
    verify_v2_release_candidate,
)


ROOT = Path(__file__).resolve().parents[1]
FOOTPRINT = ROOT / "third_party" / "kc2.pretty" / "SW_Choc_V2_Socket_MX_THT.kicad_mod"
DIODE_FOOTPRINT = ROOT / "third_party" / "kc2.pretty" / "D_ES1B_SMA_HandSolder_C437840.kicad_mod"
MOUNT_FOOTPRINT = ROOT / "third_party" / "kc2.pretty" / "MH_M1.4_NPTH_1.60.kicad_mod"
POWER_SWITCH_FOOTPRINT = ROOT / "third_party" / "kc2.pretty" / "SW_IMMS_12V_BSI10_THT.kicad_mod"
POWER_SWITCH_MODEL = ROOT / "third_party" / "kc2.3dshapes" / "SW_IMMS_12V_BSI10_THT.step"
BATTERY_TERMINATION_FOOTPRINT = ROOT / "third_party" / "kc2.pretty" / "BAT_2Pin_PTH_DirectSolder.kicad_mod"
BATTERY_BODY_FOOTPRINT = ROOT / "third_party" / "kc2.pretty" / "BAT_301230_30x12mm.kicad_mod"
V2_ROOT = ROOT / "hardware" / "kicad" / "draft" / "x3-v2"
LEFT_BOARD = V2_ROOT / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb"
RIGHT_BOARD = V2_ROOT / "kc2_right-x3-v2" / "kc2_right-x3-v2.kicad_pcb"
MANIFEST = V2_ROOT / "kc2_x3_v2_generation_manifest.json"
DRC_EVIDENCE = V2_ROOT / "kc2_x3_v2_drc_evidence.json"
PRODUCT_SPEC = ROOT / "docs/spec.md"


class V2FootprintTests(unittest.TestCase):
    def test_generation_manifest_traces_all_active_digital_requirements(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["requirement_ids"],
            ["CON-ARCH-004", "CON-ARCH-007", "REL-ARCH-001"],
        )

    def test_controller_power_footprints_match_con_arch_007(self) -> None:
        import pcbnew

        power = pcbnew.FootprintLoad(
            str(POWER_SWITCH_FOOTPRINT.parent), POWER_SWITCH_FOOTPRINT.stem
        )
        self.assertIsNotNone(power)
        self.assertEqual(str(power.GetValue()), "SW_IMMS_12V_BSI10_THT")
        self.assertIn("6.40 mm nominal installed height", power.GetLibDescription())
        self.assertIn("1.60 mm actuator travel", power.GetLibDescription())
        self.assertIn("amec-gmbh.de", power.GetLibDescription())
        self.assertTrue(POWER_SWITCH_MODEL.is_file())
        self.assertEqual(
            [model.m_Filename for model in power.Models()],
            [
                "${KIPRJMOD}/../../../../../third_party/kc2.3dshapes/"
                "SW_IMMS_12V_BSI10_THT.step"
            ],
        )
        power_pads = {
            pad.GetNumber(): (
                round(pcbnew.ToMM(pad.GetPosition().x), 3),
                round(pcbnew.ToMM(pad.GetPosition().y), 3),
                round(pcbnew.ToMM(pad.GetSize().x), 3),
                round(pcbnew.ToMM(pad.GetDrillSize().x), 3),
            )
            for pad in power.Pads()
        }
        self.assertEqual(
            power_pads,
            {
                "2": (-2.54, 0.0, 1.6, 0.8),
                "1": (0.0, 0.0, 1.6, 0.8),
                "3": (2.54, 0.0, 1.6, 0.8),
            },
        )

        fab_points = [
            (round(pcbnew.ToMM(point.x), 3), round(pcbnew.ToMM(point.y), 3))
            for item in power.GraphicalItems()
            if item.GetLayer() == pcbnew.F_Fab and hasattr(item, "GetStart")
            for point in (item.GetStart(), item.GetEnd())
        ]
        self.assertEqual(
            (
                min(point[0] for point in fab_points),
                min(point[1] for point in fab_points),
                max(point[0] for point in fab_points),
                max(point[1] for point in fab_points),
            ),
            (-5.0, -1.25, 5.0, 1.25),
        )

        battery = pcbnew.FootprintLoad(
            str(BATTERY_TERMINATION_FOOTPRINT.parent), BATTERY_TERMINATION_FOOTPRINT.stem
        )
        self.assertIsNotNone(battery)
        self.assertEqual(str(battery.GetValue()), "BAT_2Pin_PTH_DirectSolder")
        battery_pads = {
            pad.GetNumber(): (
                round(pcbnew.ToMM(pad.GetPosition().x), 3),
                round(pcbnew.ToMM(pad.GetPosition().y), 3),
                round(pcbnew.ToMM(pad.GetSize().x), 3),
                round(pcbnew.ToMM(pad.GetSize().y), 3),
                round(pcbnew.ToMM(pad.GetDrillSize().x), 3),
            )
            for pad in battery.Pads()
        }
        self.assertEqual(
            battery_pads,
            {
                "1": (0.0, 0.0, 2.2, 1.8, 0.9),
                "2": (2.54, 0.0, 2.2, 1.8, 0.9),
            },
        )
        battery_pad_edge_gap = (
            battery_pads["2"][0]
            - battery_pads["2"][2] / 2.0
            - (battery_pads["1"][0] + battery_pads["1"][2] / 2.0)
        )
        self.assertGreaterEqual(battery_pad_edge_gap, 0.30)

        body = pcbnew.FootprintLoad(
            str(BATTERY_BODY_FOOTPRINT.parent), BATTERY_BODY_FOOTPRINT.stem
        )
        self.assertIsNotNone(body)
        self.assertEqual(str(body.GetValue()), "BAT_301230_30x12mm")
        self.assertEqual(len(list(body.Pads())), 0)
        body_fab = [
            (round(pcbnew.ToMM(point.x), 3), round(pcbnew.ToMM(point.y), 3))
            for item in body.GraphicalItems()
            if item.GetLayer() == pcbnew.F_Fab and hasattr(item, "GetStart")
            for point in (item.GetStart(), item.GetEnd())
        ]
        self.assertEqual(
            (
                min(point[0] for point in body_fab),
                min(point[1] for point in body_fab),
                max(point[0] for point in body_fab),
                max(point[1] for point in body_fab),
            ),
            (-15.0, -6.0, 15.0, 6.0),
        )

    def test_m1_4_mounting_hole_is_owned_copper_free_npth(self) -> None:
        import pcbnew

        footprint = pcbnew.FootprintLoad(str(MOUNT_FOOTPRINT.parent), MOUNT_FOOTPRINT.stem)
        self.assertIsNotNone(footprint)
        self.assertEqual(str(footprint.GetValue()), "M1.4_NPTH_1.60")
        reference = footprint.Reference()
        self.assertTrue(reference.IsVisible())
        self.assertEqual(reference.GetLayer(), pcbnew.F_SilkS)
        self.assertEqual(
            (
                round(pcbnew.ToMM(reference.GetTextHeight()), 3),
                round(pcbnew.ToMM(reference.GetTextThickness()), 3),
                round(pcbnew.ToMM(reference.GetFPRelativePosition().x), 3),
                round(pcbnew.ToMM(reference.GetFPRelativePosition().y), 3),
            ),
            (0.8, 0.1, 0.0, -1.5),
        )
        pads = list(footprint.Pads())
        self.assertEqual(len(pads), 1)
        pad = pads[0]
        self.assertEqual(pad.GetNumber(), "")
        self.assertEqual(pad.GetAttribute(), pcbnew.PAD_ATTRIB_NPTH)
        self.assertEqual(
            (
                round(pcbnew.ToMM(pad.GetSize().x), 3),
                round(pcbnew.ToMM(pad.GetSize().y), 3),
                round(pcbnew.ToMM(pad.GetDrillSize().x), 3),
                round(pcbnew.ToMM(pad.GetDrillSize().y), 3),
            ),
            (1.6, 1.6, 1.6, 1.6),
        )
        self.assertEqual(pad.GetNetname(), "")

    def test_supports_only_choc_v2_socket_and_mx_tht(self) -> None:
        report = analyze_v2_footprint(FOOTPRINT)

        self.assertEqual(report["numbered_pad_counts"], {"1": 2, "2": 2})
        self.assertEqual(
            report["choc_socket_smd_pads"],
            {
                "1": (3.7, 5.9, 2.6, 2.6),
                "2": (-8.7, 3.8, 2.6, 2.6),
            },
        )
        self.assertEqual(
            report["mx_tht_pads"],
            {
                "1": (2.54, -5.08, 2.5, 2.5, 1.5),
                "2": (-3.81, -2.54, 2.5, 2.5, 1.5),
            },
        )
        self.assertEqual(
            report["npth_holes"],
            {
                (0.0, 0.0, 5.0),
                (-5.0, 3.8, 3.0),
                (0.0, 5.9, 3.0),
                (5.0, -5.15, 1.65),
                (-5.08, 0.0, 1.7),
                (5.08, 0.0, 1.7),
            },
        )
        self.assertFalse(report["has_choc_v1_locator_holes"])
        self.assertFalse(report["has_mx_hotswap_pads"])
        self.assertFalse(report["has_choc_v2_direct_solder_pads"])
        self.assertEqual(report["silkscreen_item_count"], 0)

    def test_es1b_sma_footprint_matches_official_land_pattern(self) -> None:
        import pcbnew

        footprint = pcbnew.FootprintLoad(str(DIODE_FOOTPRINT.parent), DIODE_FOOTPRINT.stem)
        self.assertIsNotNone(footprint)
        self.assertEqual(str(footprint.GetValue()), "ES1B_Jingdao_C437840_Eleparts9475342")
        pads = {
            pad.GetNumber(): (
                round(pcbnew.ToMM(pad.GetPosition().x), 3),
                round(pcbnew.ToMM(pad.GetPosition().y), 3),
                round(pcbnew.ToMM(pad.GetSize().x), 3),
                round(pcbnew.ToMM(pad.GetSize().y), 3),
            )
            for pad in footprint.Pads()
        }
        self.assertEqual(pads, {"1": (-2.1, 0.0, 1.8, 1.8), "2": (2.1, 0.0, 1.8, 1.8)})
        inner_gap = pads["2"][0] - pads["2"][2] / 2 - (pads["1"][0] + pads["1"][2] / 2)
        copper_span = pads["2"][0] + pads["2"][2] / 2 - (pads["1"][0] - pads["1"][2] / 2)
        self.assertEqual(round(inner_gap, 3), 2.4)
        self.assertEqual(round(copper_span, 3), 6.0)
        self.assertGreaterEqual((copper_span - 5.2) / 2, 0.4 - 1e-6)
        self.assertEqual(
            {
                pad.GetNumber(): round(pcbnew.ToMM(pad.GetLocalClearance() or 0), 3)
                for pad in footprint.Pads()
            },
            {"1": 0.3, "2": 0.3},
        )
        courtyard_points = [
            (
                round(pcbnew.ToMM(point.x), 3),
                round(pcbnew.ToMM(point.y), 3),
            )
            for item in footprint.GraphicalItems()
            if item.GetLayer() == pcbnew.F_CrtYd
            for point in (item.GetStart(), item.GetEnd())
        ]
        self.assertEqual(
            (
                min(point[0] for point in courtyard_points),
                min(point[1] for point in courtyard_points),
                max(point[0] for point in courtyard_points),
                max(point[1] for point in courtyard_points),
            ),
            (-3.25, -1.6, 3.25, 1.6),
        )


class V2GeneratorTests(unittest.TestCase):
    def test_generator_declares_exact_selected_m1_4_pattern(self) -> None:
        from tools import generate_kc2_pcbs as generator

        self.assertEqual(
            generator.X3_V2_MOUNTING_POINTS,
            {
                "left": [
                    (142.6125, 68.0),
                    (128.6125, 86.5),
                    (100.1125, 93.5),
                    (57.1125, 99.0),
                    (133.6125, 131.5),
                    (55.1125, 144.0),
                    (165.6125, 145.0),
                    (102.6125, 147.0),
                ],
                "right": [
                    (71.6875, 68.0),
                    (181.1875, 85.5),
                    (147.6875, 93.5),
                    (109.6875, 96.5),
                    (71.6875, 105.5),
                    (42.1875, 106.0),
                    (181.1875, 134.5),
                    (143.1875, 134.5),
                    (51.6875, 144.0),
                    (95.6875, 147.0),
                ],
            },
        )
        self.assertEqual(generator.X3_V2_MOUNT_HOLE_DIAMETER_MM, 1.6)
        self.assertEqual(generator.X3_V2_MOUNT_HEAD_ENVELOPE_MM, (2.0, 0.5))
        self.assertEqual(generator.X3_V2_MOUNT_DRIVER_DIAMETER_MM, 3.0)
        self.assertEqual(generator.X3_V2_MOUNT_SUPPORT_LAND_DIAMETER_MM, 3.0)
        self.assertEqual(generator.X3_V2_MOUNT_PILOT_ENVELOPE_MM, (1.1, 2.8))
        self.assertEqual(generator.X3_V2_MOUNT_UNDER_HEAD_LENGTH_MM, 4.0)
        self.assertEqual(generator.X3_V2_MOUNT_CLOSED_BOTTOM_MM, 0.7)
        self.assertEqual(generator.X3_V2_MOUNT_REFERENCE_TEXT_SIZE_MM, 0.8)
        self.assertEqual(generator.X3_V2_MOUNT_REFERENCE_STROKE_MM, 0.1)
        self.assertEqual(generator.X3_V2_MOUNT_REFERENCE_OFFSET_MM, (0.0, -1.5))

    def test_generator_uses_the_fixed_70_key_v5_layout(self) -> None:
        from tools import generate_kc2_pcbs as generator

        left = generator.make_left_keys_x3_v2()
        right = generator.make_right_keys_x3_v2()

        self.assertEqual((len(left), len(right)), (31, 39))
        self.assertEqual(
            [(key.label, key.w_u) for key in left if key.row == 3],
            [
                ("LShift", 1.0),
                ("LShift", 1.25),
                ("Z", 1.0),
                ("X", 1.0),
                ("C", 1.0),
                ("V", 1.0),
                ("B", 1.0),
            ],
        )
        self.assertEqual(
            [(key.label, key.w_u) for key in left if key.row == 4],
            [
                ("Ctrl", 1.25),
                ("Fn", 1.25),
                ("Alt", 1.25),
                ("Space", 1.75),
                ("Space", 1.75),
            ],
        )
        self.assertNotIn("Win", [key.label for key in left])
        self.assertEqual(
            [[(key.label, key.w_u) for key in right if key.row == row] for row in range(5)],
            [
                [("7", 1.0), ("8", 1.0), ("9", 1.0), ("0", 1.0), ("-", 1.0), ("=", 1.0), ("BSPC", 1.25), ("Del", 1.0)],
                [("Y", 1.0), ("U", 1.0), ("I", 1.0), ("O", 1.0), ("P", 1.0), ("[", 1.0), ("]", 1.0), ("\\", 1.75)],
                [("H", 1.0), ("J", 1.0), ("K", 1.0), ("L", 1.0), (";", 1.0), ("'", 1.0), ("Enter", 1.5), ("Enter", 1.0)],
                [("N", 1.0), ("M", 1.0), (",", 1.0), (".", 1.0), ("/", 1.0), ("RShift", 1.0), ("Up", 1.0), ("Fn", 1.0)],
                [("B", 1.0), ("Space", 1.75), ("RAlt", 1.25), ("RCtrl", 1.0), ("Left", 1.0), ("Down", 1.0), ("Right", 1.0)],
            ],
        )
        self.assertEqual(
            [round(max(key.x_u + key.w_u for key in right if key.row == row), 2) for row in range(5)],
            [8.75] * 5,
        )
        self.assertLessEqual(max(key.w_u for key in left + right), 1.75)

    def test_v2_declares_exact_concealed_outline_and_join_setback(self) -> None:
        from tools import generate_kc2_pcbs as generator

        self.assertEqual(generator.X3_V2_KEYCELL_EDGE_INSET, 1.5)
        self.assertEqual(generator.X3_V2_ONE_UNIT_JOIN_CENTER_TO_EDGE, 8.025)
        self.assertEqual(generator.X3_V2_JOIN_KEYCAP_GAP, 1.8)
        self.assertEqual(generator.X3_V2_JOIN_CENTER_PITCH, 19.85)
        self.assertEqual(generator.X3_V2_MIN_JOINED_EDGE_CLEARANCE, 1.0)
        self.assertEqual(generator.X3_V2_OUTLINE_POLICY, "keycap_concealed_except_controller_service")
        self.assertEqual(generator.X3_V2_TOP_EDGE_Y_MM, 39.25)
        self.assertEqual(generator.X3_V2_BOARD_DATUM_DY_MM, 68.0)
        self.assertEqual(generator.X3_V2_CONTROLLER_Y_MM, 50.75)
        self.assertEqual(generator.X3_V2_RESET_Y_MM, 63.45)
        self.assertEqual(
            generator.X3_V2_RESET_ROTATIONS_DEGREES,
            {"left": 0.0, "right": 180.0},
        )
        self.assertEqual(
            generator.X3_V2_J_BAT1_ROTATIONS_DEGREES,
            {"left": 180.0, "right": 0.0},
        )
        self.assertEqual(generator.X3_V2_POWER_Y_MM, 63.45)
        self.assertEqual(generator.X3_V2_BATTERY_SIZE_MM, (30.0, 12.0, 3.0))
        self.assertEqual(generator.X3_V2_BATTERY_Y_MM, 50.75)
        self.assertEqual(
            generator.X3_V2_CONTROLLER_SERVICE_POSITIONS_MM,
            {
                "left": {
                    "u1": (132.7125, 50.75),
                    "battery_slot": (117.9125, 50.75),
                    "battery": (131.7125, 50.75),
                    "j_bat": (115.8125, 59.4),
                    "power": (115.8125, 63.45),
                    "reset": (126.0625, 63.45),
                },
                "right": {
                    "u1": (77.4, 50.75),
                    "battery_slot": (92.2, 50.75),
                    "battery": (78.4, 50.75),
                    "j_bat": (94.3, 59.4),
                    "power": (94.3, 63.45),
                    "reset": (84.05, 63.45),
                },
            },
        )
        for positions in generator.X3_V2_CONTROLLER_SERVICE_POSITIONS_MM.values():
            self.assertEqual(positions["reset"][1], positions["power"][1])
            self.assertAlmostEqual(abs(positions["reset"][0] - positions["power"][0]), 10.25)
            self.assertAlmostEqual(abs(positions["battery"][1] - positions["u1"][1]), 0.0)
        self.assertEqual(
            generator.variant_outline_margins("x3-v2"),
            {
                "outer_mm": -1.5,
                "top_mm": -1.5,
                "bottom_mm": -1.5,
                "inner_mm": -1.5,
            },
        )

    def test_v2_raw_outline_never_reverses_past_the_concealed_top_or_bottom_edge(self) -> None:
        from tools import generate_kc2_pcbs as generator

        for side, keys in (
            ("left", generator.make_left_keys_x3_v2()),
            ("right", generator.make_right_keys_x3_v2()),
        ):
            with self.subTest(side=side):
                controller_x = generator.controller_center_x(keys, side, "x3-v2")
                margins = generator.variant_outline_margins("x3-v2")
                outline = generator.raw_outline(
                    keys,
                    side,
                    controller_x,
                    variant="x3-v2",
                    inner_margin_extra=margins["inner_mm"] - generator.INNER_MARGIN,
                    general_margin=margins["outer_mm"],
                )
                extents = generator.row_extents(keys)
                concealed_top = min(bounds[1] for bounds in extents.values()) - margins["top_mm"]
                concealed_bottom = max(bounds[3] for bounds in extents.values()) + margins["bottom_mm"]

                key_field_points = [(x, y) for x, y in outline if y >= 0.0]
                self.assertTrue(key_field_points)
                self.assertGreaterEqual(min(y for _, y in key_field_points), concealed_top)
                self.assertLessEqual(max(y for _, y in key_field_points), concealed_bottom)

    def test_v2_rotates_each_left_edge_socket_inward(self) -> None:
        from tools import generate_kc2_pcbs as generator

        for side, keys in (
            ("left", generator.make_left_keys_x3_v2()),
            ("right", generator.make_right_keys_x3_v2()),
        ):
            with self.subTest(side=side):
                leftmost_by_row = {
                    row: min(key.cx for key in keys if key.row == row)
                    for row in range(5)
                }
                self.assertEqual(
                    [
                        generator.switch_rotation_for_key(key, keys, "x3-v2")
                        for key in keys
                    ],
                    [
                        180.0 if key.cx == leftmost_by_row[key.row] else 0.0
                        for key in keys
                    ],
                )

    def test_v2_uses_physical_nice_nano_pin_row_spacing(self) -> None:
        from tools import generate_kc2_pcbs as generator
        import pcbnew

        self.assertEqual(generator.PIN_PITCH, 2.54)
        self.assertEqual(generator.SOCKET_ROW_SPACING, 15.24)
        for name in (
            "NiceNanoV2_Socket_24Pin_USB_OUT_LEFT",
            "NiceNanoV2_Socket_24Pin_USB_OUT_RIGHT",
        ):
            footprint = pcbnew.FootprintLoad(str(ROOT / "third_party" / "kc2.pretty"), name)
            self.assertIsNotNone(footprint)
            rows = sorted(
                {
                    round(pcbnew.ToMM(pad.GetPosition().y), 3)
                    for pad in footprint.Pads()
                }
            )
            self.assertEqual(rows, [-7.62, 7.62])

    def test_v2_moves_diodes_to_a_hand_solderable_corner(self) -> None:
        from tools import generate_kc2_pcbs as generator

        for keys in (
            generator.make_left_keys_x3_v2(),
            generator.make_right_keys_x3_v2(),
        ):
            for index, key in enumerate(keys):
                rotated = generator.switch_rotation_for_key(key, keys, "x3-v2") == 180.0
                dx, dy = ((7.0, 7.0) if rotated else (-7.0, -7.0))
                rotation = 0.0
                if key.row == 0 and key.col == 1:
                    dx, dy = (7.0, 7.0)
                    rotation = 90.0
                elif key.row == 0 and dy < 0:
                    dx, dy = (-8.75, -3.25)
                    rotation = 270.0
                elif key.row == max(candidate.row for candidate in keys) and key.col == 0:
                    dx, dy = (9.5, 3.25)
                self.assertEqual(
                    generator.diode_placement_for_key(key, keys, "x3-v2"),
                    (dx, dy, rotation),
                )

    def test_v2_selects_exact_jingdao_es1b_sma_diode(self) -> None:
        from tools import generate_kc2_pcbs as generator

        self.assertEqual(generator.X3_V2_DIODE_FP, "D_ES1B_SMA_HandSolder_C437840")
        self.assertEqual(generator.X3_V2_DIODE_VALUE, "ES1B_Jingdao_C437840_Eleparts9475342")
        self.assertEqual(generator.X3_V2_DIODE_PIN_MAPPING, {"1": "cathode_row", "2": "anode_switch"})

    def test_specctra_routing_boundary_can_be_inset_without_changing_edge_cuts(self) -> None:
        from tools.inset_specctra_boundary import (
            DEFAULT_INSET_MM,
            DEFAULT_PRESERVE_CONTROLLER_ABOVE_MM,
            inset_polygon,
        )

        self.assertEqual(DEFAULT_INSET_MM, 0.35)
        self.assertEqual(DEFAULT_PRESERVE_CONTROLLER_ABOVE_MM, 67.5)

        result = inset_polygon(
            [(0, 0), (10_000, 0), (10_000, 10_000), (0, 10_000)],
            400,
        )
        self.assertEqual(
            (min(x for x, _ in result), min(y for _, y in result), max(x for x, _ in result), max(y for _, y in result)),
            (400, 400, 9_600, 9_600),
        )

    def test_generator_keeps_x3_v2_in_a_dedicated_draft_output(self) -> None:
        from tools import generate_kc2_pcbs as generator

        self.assertIn("x3-v2", generator.SUPPORTED_VARIANTS)
        self.assertEqual(generator.variant_output_dir("x3-v2"), generator.DRAFT_ROOT / "x3-v2")
        self.assertEqual(generator.variant_project_suffix("x3-v2"), "-x3-v2")
        self.assertEqual(generator.variant_switch_footprint("x3-v2"), "SW_Choc_V2_Socket_MX_THT")

    def test_joined_v2_render_uses_safe_cross_seam_key_pitch(self) -> None:
        from tools import generate_kc2_pcbs as generator
        from tools.render_kc2_x3_joined import build_context

        context = build_context(ROOT, 1.0, 5.0, "key-pitch", variant="x3-v2")

        self.assertEqual((len(context.left.keys), len(context.right.keys)), (31, 39))
        self.assertEqual(context.key_horizontal_clearance.left_label, "6")
        self.assertEqual(context.key_horizontal_clearance.right_label, "7")
        self.assertAlmostEqual(
            context.key_horizontal_clearance.clearance,
            generator.X3_V2_JOIN_KEYCAP_GAP,
            places=3,
        )
        self.assertGreaterEqual(
            context.min_edge_clearance_mm,
            generator.X3_V2_MIN_JOINED_EDGE_CLEARANCE,
        )

        expected_pairs = [
            (0, "6", "7", 18.05, 18.05, 19.85, 8.025, 8.025),
            (1, "T", "Y", 18.05, 18.05, 19.85, 8.025, 8.025),
            (2, "G", "H", 18.05, 18.05, 19.85, 8.025, 8.025),
            (3, "B", "N", 18.05, 18.05, 19.85, 8.025, 8.025),
            (4, "Space", "B", 32.3375, 18.05, 26.9937, 15.1687, 8.025),
        ]
        self.assertEqual(len(context.seam_key_clearances), len(expected_pairs))
        for clearance, expected in zip(context.seam_key_clearances, expected_pairs):
            row, left_label, right_label, left_width, right_width, pitch, left_edge, right_edge = expected
            with self.subTest(row=row):
                self.assertEqual(clearance.row, row)
                self.assertEqual((clearance.left_label, clearance.right_label), (left_label, right_label))
                self.assertAlmostEqual(clearance.left_cap_width_mm, left_width, places=4)
                self.assertAlmostEqual(clearance.right_cap_width_mm, right_width, places=4)
                self.assertAlmostEqual(clearance.center_pitch_mm, pitch, places=4)
                self.assertAlmostEqual(clearance.cap_gap_mm, generator.X3_V2_JOIN_KEYCAP_GAP, places=3)
                self.assertAlmostEqual(clearance.left_center_to_pcb_edge_mm, left_edge, places=4)
                self.assertAlmostEqual(clearance.right_center_to_pcb_edge_mm, right_edge, places=4)
                self.assertAlmostEqual(clearance.pcb_gap_mm, generator.X3_V2_ROW_CENTER_PCB_GAP, places=3)

        for row in range(5):
            left_candidates = [
                (index, key)
                for index, key in enumerate(context.left.keys, start=1)
                if key.row == row
            ]
            right_candidates = [
                (index, key)
                for index, key in enumerate(context.right.keys, start=1)
                if key.row == row
            ]
            left_index, left_key = max(
                left_candidates,
                key=lambda item: context.left.switch_centers[item[0]][0]
                + item[1].w_u * generator.UNIT / 2.0,
            )
            right_index, right_key = min(
                right_candidates,
                key=lambda item: context.right.switch_centers[item[0]][0]
                - item[1].w_u * generator.UNIT / 2.0,
            )
            left_center = context.left.switch_centers[left_index][0]
            right_center = context.right.switch_centers[right_index][0] + context.right_dx
            cap_gap = (
                right_center
                - right_key.w_u * generator.UNIT / 2.0
                + 0.5
                - left_center
                - left_key.w_u * generator.UNIT / 2.0
                + 0.5
            )
            with self.subTest(row=row):
                self.assertAlmostEqual(cap_gap, generator.X3_V2_JOIN_KEYCAP_GAP, places=3)

    def test_exact_joined_clearance_detects_horizontal_contact(self) -> None:
        from tools.render_kc2_x3_joined import minimum_segment_clearance

        touching = minimum_segment_clearance(
            [((0.0, 0.0), (2.0, 0.0))],
            [((1.0, 0.0), (3.0, 0.0))],
        )
        separated = minimum_segment_clearance(
            [((0.0, 0.0), (2.0, 0.0))],
            [((0.0, 1.0), (2.0, 1.0))],
        )

        self.assertAlmostEqual(touching.clearance, 0.0, places=6)
        self.assertAlmostEqual(separated.clearance, 1.0, places=6)

    def test_joined_v2_render_explains_clearance_corridor_without_calling_it_overlap(self) -> None:
        from tools.render_kc2_x3_joined import build_context, render_svg

        context = build_context(ROOT, 1.0, 5.0, "key-pitch", variant="x3-v2")
        with TemporaryDirectory(dir=ROOT) as temporary:
            output = Path(temporary) / "joined.svg"
            render_svg(context, output, zoom=False)
            svg = output.read_text(encoding="utf-8")

        self.assertIn("Empty PCB clearance corridor", svg)
        self.assertIn("Outline X-range nesting", svg)
        self.assertIn("Row-center PCB gap", svg)
        self.assertIn('data-seam-pair-count="5"', svg)
        for pair in ("6-7", "T-Y", "G-H", "B-N", "Space-B"):
            self.assertIn(f'data-pair="{pair}"', svg)
        self.assertNotIn("Interlock overlap:", svg)
        self.assertIn('data-outline-x-range-nesting-mm="', svg)
        self.assertNotIn("data-interlock-overlap-mm", svg)
        self.assertGreater(
            svg.rfind('<rect x="8" y="8"'),
            svg.rfind('id="key-horizontal-clearance"'),
        )

    def test_joined_v2_renderer_cli_produces_fresh_pngs_with_kicad_python(self) -> None:
        with TemporaryDirectory(dir=ROOT) as temporary:
            output_dir = Path(temporary) / "render"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "tools.render_kc2_x3_joined",
                    "--repo",
                    str(ROOT),
                    "--variant",
                    "x3-v2",
                    "--placement-mode",
                    "key-pitch",
                    "--scale",
                    "2",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=60,
            )

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertIn("outline_x_range_nesting_mm=", completed.stdout)
            self.assertNotIn("interlock_overlap_mm=", completed.stdout)
            for stem in ("kc2_x3_v2_joined_top", "kc2_x3_v2_join_seam_zoom"):
                self.assertTrue((output_dir / f"{stem}.svg").is_file())
                png = output_dir / f"{stem}.png"
                payload = png.read_bytes()
                self.assertEqual(payload[:8], b"\x89PNG\r\n\x1a\n")
                width, height = struct.unpack(">II", payload[16:24])
                self.assertGreater(width, 0)
                self.assertGreater(height, 0)

    def test_actual_v2_edge_cuts_are_keycap_concealed_and_recessed_at_join(self) -> None:
        from tools.verify_kc2_x3_v2_outline import analyze_outline

        report = analyze_outline(ROOT)

        self.assertEqual(report["requirement"], "CON-ARCH-006")
        self.assertEqual(report["errors"], [])
        self.assertAlmostEqual(report["one_unit_cross_seam_center_pitch_mm"], 19.85, places=3)
        self.assertNotIn("cross_seam_key_pitch_mm", report)
        self.assertAlmostEqual(report["cross_seam_keycap_gap_mm"], 1.8, places=3)
        self.assertAlmostEqual(report["row_center_joined_pcb_gap_mm"], 3.8, places=3)
        self.assertGreaterEqual(report["minimum_joined_pcb_gap_mm"], 1.0)
        self.assertAlmostEqual(report["outline_x_range_nesting_mm"], 10.4875, places=4)
        self.assertNotIn("interlock_overlap_mm", report)
        self.assertEqual(len(report["cross_seam_pairs"]), 5)
        self.assertEqual(
            [(pair["left_key"], pair["right_key"]) for pair in report["cross_seam_pairs"]],
            [("6", "7"), ("T", "Y"), ("G", "H"), ("B", "N"), ("Space", "B")],
        )
        self.assertEqual(report["cross_seam_pairs"][4]["left_cap_width_mm"], 32.3375)
        self.assertEqual(report["cross_seam_pairs"][4]["left_center_to_pcb_edge_mm"], 15.1687)
        for pair in report["cross_seam_pairs"]:
            self.assertAlmostEqual(pair["cap_gap_mm"], 1.8, places=3)
            self.assertAlmostEqual(pair["pcb_gap_mm"], 3.8, places=3)
        for side in ("left", "right"):
            self.assertLessEqual(report["boards"][side]["maximum_outer_overhang_mm"], 0.001)
            self.assertLessEqual(report["boards"][side]["maximum_top_bottom_overhang_mm"], 0.001)
            self.assertLessEqual(
                report["boards"][side]["maximum_keyfield_perimeter_overhang_mm"],
                0.001,
            )
            for setback in report["boards"][side]["join_setback_by_row_mm"]:
                self.assertAlmostEqual(setback, 1.0, places=3)
            for setback in report["boards"][side]["top_bottom_setback_mm"]:
                self.assertAlmostEqual(setback, 1.0, places=3)
            for exception in report["boards"][side]["permitted_exceptions"]:
                self.assertIn("clearance_driving_features", exception)
                self.assertTrue(exception["clearance_driving_features"])
            self.assertLessEqual(
                report["one_to_one_exports"][side]["maximum_dimension_error_mm"],
                0.05,
            )
            self.assertFalse(Path(report["one_to_one_exports"][side]["path"]).is_absolute())

    def test_layout_spec_uses_current_v2_safe_joined_geometry(self) -> None:
        layout_spec = (ROOT / "docs" / "spec" / "20.kc2-no-stabilizer-layout.md").read_text(
            encoding="utf-8"
        )
        product_srs = (ROOT / "docs" / "spec" / "10.product-architecture.srs.md").read_text(
            encoding="utf-8"
        )
        v2_readme = (V2_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("`19.85 mm` one-unit seam pitch", layout_spec)
        self.assertIn("`1.80 mm` nominal gap", layout_spec)
        self.assertIn("`3.80 mm` nominal joined PCB gap", layout_spec)
        self.assertIn("`32.3375 mm` / `18.05 mm`", layout_spec)
        self.assertIn("fixed 70-key v5 layout", layout_spec)
        self.assertIn("Pressing the left Fn and left Alt positions within a `50 ms` combo timeout produces Win/LGUI", product_srs)
        self.assertNotIn("nominal `19.05 mm` one-unit pitch", layout_spec)
        self.assertNotIn("same `18.05 mm` MX-envelope keycaps", product_srs)
        self.assertNotIn("each row-center seam edge is 8.025 mm", product_srs)
        self.assertIn("actual selected keycap envelope for each corresponding physical key", product_srs)
        self.assertIn("-m tools.render_kc2_x3_joined", v2_readme)
        self.assertIn("KC2_HEADLESS_BROWSER", v2_readme)
        self.assertIn("visibly numbered `MH1..MH8`", v2_readme)
        self.assertIn("`MH1..MH10` on the right", v2_readme)
        self.assertIn("CON-ARCH-007", product_srs)
        self.assertIn("SW_PWR1 is (115.8125, 63.4500) mm left and (94.3000, 63.4500) mm right", product_srs)
        self.assertIn("SW_RST1 is (126.0625, 63.4500) mm left and (84.0500, 63.4500) mm right", product_srs)
        self.assertIn("BAT_LEAD_SLOT1 is retained only as the electrically unconnected", product_srs)
        self.assertNotIn("supersedes_for_v2_reset_only", product_srs)
        self.assertIn("top Edge.Cuts centerline to `Y=39.2500 mm`", product_srs)

    def test_generator_accepts_an_isolated_output_override(self) -> None:
        from tools import generate_kc2_pcbs as generator

        with TemporaryDirectory(dir=ROOT) as temporary:
            output_dir = Path(temporary) / "x3-v2"
            manifest = generator.generate_variant("x3-v2", output_dir=output_dir)

            self.assertTrue((output_dir / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb").is_file())
            self.assertTrue((output_dir / "kc2_right-x3-v2" / "kc2_right-x3-v2.kicad_pcb").is_file())
            for side in ("left", "right"):
                board_path = (
                    output_dir
                    / f"kc2_{side}-x3-v2"
                    / f"kc2_{side}-x3-v2.kicad_pcb"
                )
                import pcbnew

                generated_board = pcbnew.LoadBoard(str(board_path))
                expected_service = generator.X3_V2_CONTROLLER_SERVICE_POSITIONS_MM[side]
                for reference, key in (
                    ("U1", "u1"),
                    ("BAT1", "battery"),
                    ("BAT_LEAD_SLOT1", "battery_slot"),
                    ("J_BAT1", "j_bat"),
                    ("SW_PWR1", "power"),
                    ("SW_RST1", "reset"),
                ):
                    footprint = generated_board.FindFootprintByReference(reference)
                    self.assertIsNotNone(footprint)
                    self.assertEqual(
                        (
                            round(pcbnew.ToMM(footprint.GetPosition().x), 4),
                            round(pcbnew.ToMM(footprint.GetPosition().y), 4),
                        ),
                        expected_service[key],
                    )
                for reference in ("J_BAT1", "SW_PWR1", "SW_RST1"):
                    footprint = generated_board.FindFootprintByReference(reference)
                    self.assertEqual(footprint.GetReference(), reference)
                    self.assertFalse(footprint.Reference().IsVisible())
                reset = generated_board.FindFootprintByReference("SW_RST1")
                self.assertEqual(
                    round(reset.GetOrientation().AsDegrees() % 360.0, 3),
                    0.0 if side == "left" else 180.0,
                )
                power = generated_board.FindFootprintByReference("SW_PWR1")
                self.assertEqual(
                    round(power.GetOrientation().AsDegrees(), 3),
                    0.0 if side == "left" else 180.0,
                )
                j_bat = generated_board.FindFootprintByReference("J_BAT1")
                self.assertEqual(
                    round(j_bat.GetOrientation().AsDegrees(), 3),
                    180.0 if side == "left" else 0.0,
                )
                self.assertEqual(
                    {
                        pad.GetNumber(): (
                            round(pcbnew.ToMM(pad.GetPosition().x), 4),
                            round(pcbnew.ToMM(pad.GetPosition().y), 4),
                            pad.GetNetname(),
                        )
                        for pad in reset.Pads()
                    },
                    {
                        "1": (
                            expected_service["reset"][0]
                            + (-3.875 if side == "left" else 3.875),
                            expected_service["reset"][1],
                            "RST",
                        ),
                        "2": (
                            expected_service["reset"][0]
                            + (3.875 if side == "left" else -3.875),
                            expected_service["reset"][1],
                            "GND",
                        ),
                    },
                )
                self.assertEqual(
                    {
                        pad.GetNumber(): pad.GetNetname()
                        for pad in power.Pads()
                    },
                    {"1": "BAT+", "2": "NN_B+", "3": ""},
                )
                self.assertEqual(
                    {pad.GetNumber(): pad.GetNetname() for pad in j_bat.Pads()},
                    {"1": "BAT+", "2": "GND"},
                )
                u1 = generated_board.FindFootprintByReference("U1")
                self.assertEqual(
                    {
                        pad.GetNumber(): pad.GetNetname()
                        for pad in u1.Pads()
                        if pad.GetNumber() in {"RAW", "GND_C"}
                    },
                    {"RAW": "NN_B+", "GND_C": "GND"},
                )
                battery = generated_board.FindFootprintByReference("BAT1")
                battery_fab = [
                    (
                        round(pcbnew.ToMM(point.x), 4),
                        round(pcbnew.ToMM(point.y), 4),
                    )
                    for item in battery.GraphicalItems()
                    if item.GetLayer() == pcbnew.F_Fab and hasattr(item, "GetStart")
                    for point in (item.GetStart(), item.GetEnd())
                ]

                self.assertEqual(
                    (
                        min(point[0] for point in battery_fab),
                        min(point[1] for point in battery_fab),
                        max(point[0] for point in battery_fab),
                        max(point[1] for point in battery_fab),
                    ),
                    (
                        round(expected_service["battery"][0] - 15.0, 4),
                        round(expected_service["battery"][1] - 6.0, 4),
                        round(expected_service["battery"][0] + 15.0, 4),
                        round(expected_service["battery"][1] + 6.0, 4),
                    ),
                )
                self.assertFalse(
                    any(
                        isinstance(item, pcbnew.PCB_TEXT)
                        and "TW301525" in item.GetText()
                        for item in generated_board.GetDrawings()
                    )
                )
                service_texts = {
                    item.GetText()
                    for item in generated_board.GetDrawings()
                    if isinstance(item, pcbnew.PCB_TEXT)
                }
                self.assertIn("BAT STRAIN RELIEF", service_texts)
                self.assertNotIn("BAT LEAD EXIT", service_texts)
                self.assertIn("RST", service_texts)
                service_legends = [
                    item
                    for item in generated_board.GetDrawings()
                    if isinstance(item, pcbnew.PCB_TEXT)
                    and (item.GetText() == "RST" or "PWR" in item.GetText())
                ]
                self.assertEqual(
                    sorted(item.GetText() for item in service_legends),
                    sorted(
                        [
                            "RST",
                            "PWR OFF< >ON" if side == "left" else "ON< >OFF PWR",
                        ]
                    ),
                )
                for legend in service_legends:
                    self.assertEqual(
                        (
                            round(pcbnew.ToMM(legend.GetTextSize().x), 3),
                            round(pcbnew.ToMM(legend.GetTextSize().y), 3),
                        ),
                        (0.8, 0.8),
                    )
                from tools.verify_kc2_x3_v2 import board_outline_segments_mm

                outline_segments = board_outline_segments_mm(generated_board)
                self.assertAlmostEqual(
                    min(point[1] for segment in outline_segments for point in segment),
                    39.25,
                    places=3,
                )
                top_row_y = sorted(
                    round(pcbnew.ToMM(fp.GetPosition().y), 4)
                    for fp in generated_board.GetFootprints()
                    if fp.GetReference().startswith("SW")
                    and fp.GetReference() not in {"SW_RST1", "SW_PWR1"}
                )[0]
                self.assertEqual(top_row_y, 77.525)
                from tools.verify_kc2_compact_controller import check_side

                self.assertEqual(check_side(side, board_path), [])

                from tools.verify_kc2_x3_v2 import (
                    controller_power_geometry_report,
                    matrix_footprints,
                    verify_placed_footprint_contracts,
                )

                contract_errors = verify_placed_footprint_contracts(
                    generated_board,
                    matrix_footprints(generated_board, "SW"),
                    matrix_footprints(generated_board, "D"),
                    side,
                )
                self.assertEqual(contract_errors, ([], [], [], []))
                power_geometry = controller_power_geometry_report(generated_board, side)
                self.assertEqual(power_geometry["errors"], [])
                self.assertGreaterEqual(
                    power_geometry["battery_to_antenna_keepout_mm"],
                    3.97,
                )
                self.assertGreaterEqual(
                    power_geometry["battery_to_socket_pad_copper_mm"],
                    0.72,
                )
                self.assertGreater(
                    power_geometry["minimum_service_feature_to_antenna_keepout_mm"],
                    0.0,
                )
                self.assertLessEqual(
                    power_geometry["maximum_parallel_centerline_separation_mm"],
                    2.0,
                )
                self.assertLessEqual(power_geometry["power_loop_area_mm2"], 75.0)
                self.assertLessEqual(
                    power_geometry["maximum_antenna_parallel_segment_mm"],
                    10.0,
                )
                generated_mounts = sorted(
                    (
                        footprint
                        for footprint in generated_board.GetFootprints()
                        if footprint.GetReference().startswith("MH")
                    ),
                    key=lambda footprint: int(footprint.GetReference()[2:]),
                )
                self.assertEqual(
                    len(generated_mounts),
                    8 if side == "left" else 10,
                )
                self.assertEqual(
                    [
                        (
                            footprint.GetReference(),
                            round(pcbnew.ToMM(footprint.GetPosition().x), 4),
                            round(pcbnew.ToMM(footprint.GetPosition().y), 4),
                        )
                        for footprint in generated_mounts
                    ],
                    [
                        (f"MH{index}", x, y)
                        for index, (x, y) in enumerate(
                            generator.X3_V2_MOUNTING_POINTS[side], start=1
                        )
                    ],
                )
                for footprint in generated_mounts:
                    reference = footprint.Reference()
                    self.assertTrue(reference.IsVisible())
                    self.assertEqual(reference.GetLayer(), pcbnew.F_SilkS)
                    self.assertEqual(
                        (
                            round(pcbnew.ToMM(reference.GetTextHeight()), 3),
                            round(pcbnew.ToMM(reference.GetTextThickness()), 3),
                            round(pcbnew.ToMM(reference.GetFPRelativePosition().x), 3),
                            round(pcbnew.ToMM(reference.GetFPRelativePosition().y), 3),
                        ),
                        (0.8, 0.1, 0.0, -1.5),
                    )
                usb_label = next(
                    item
                    for item in generated_board.GetDrawings()
                    if isinstance(item, pcbnew.PCB_TEXT)
                    and item.GetText() == f"USB_OUT_{side.upper()}"
                )
                self.assertEqual(
                    (
                        round(pcbnew.ToMM(usb_label.GetTextHeight()), 3),
                        round(usb_label.GetTextAngle().AsDegrees(), 3),
                    ),
                    (0.8, 90.0),
                )
                project = json.loads(
                    (
                        output_dir
                        / f"kc2_{side}-x3-v2"
                        / f"kc2_{side}-x3-v2.kicad_pro"
                    ).read_text(encoding="utf-8")
                )
                default_netclass = next(
                    item
                    for item in project["net_settings"]["classes"]
                    if item["name"] == "Default"
                )
                self.assertEqual(default_netclass["clearance"], 0.30)
            self.assertEqual(manifest["variant"], "x3-v2")
            self.assertEqual(manifest["matrix_route_clearance_mm"], 0.30)
            self.assertEqual(
                manifest["diode_placement_policy"]["minimum_fillet_to_unrelated_route_mm"],
                0.10,
            )
            self.assertEqual(manifest["key_count"], {"left": 31, "right": 39, "total": 70})
            self.assertTrue(any("15.16875 mm left / 8.02500 mm right" in note for note in manifest["notes"]))
            self.assertFalse(any("10.40625 mm left" in note for note in manifest["notes"]))
            self.assertEqual(manifest["keycell_edge_inset_mm"], 1.5)
            self.assertEqual(manifest["one_unit_join_center_to_edge_mm"], 8.025)
            self.assertEqual(
                manifest["join_geometry_by_row"],
                [
                    {"row": 0, "left_key": "6", "right_key": "7", "left_cap_width_mm": 18.05, "right_cap_width_mm": 18.05, "left_center_to_edge_mm": 8.025, "right_center_to_edge_mm": 8.025, "center_pitch_mm": 19.85, "cap_gap_mm": 1.8, "pcb_gap_mm": 3.8},
                    {"row": 1, "left_key": "T", "right_key": "Y", "left_cap_width_mm": 18.05, "right_cap_width_mm": 18.05, "left_center_to_edge_mm": 8.025, "right_center_to_edge_mm": 8.025, "center_pitch_mm": 19.85, "cap_gap_mm": 1.8, "pcb_gap_mm": 3.8},
                    {"row": 2, "left_key": "G", "right_key": "H", "left_cap_width_mm": 18.05, "right_cap_width_mm": 18.05, "left_center_to_edge_mm": 8.025, "right_center_to_edge_mm": 8.025, "center_pitch_mm": 19.85, "cap_gap_mm": 1.8, "pcb_gap_mm": 3.8},
                    {"row": 3, "left_key": "B", "right_key": "N", "left_cap_width_mm": 18.05, "right_cap_width_mm": 18.05, "left_center_to_edge_mm": 8.025, "right_center_to_edge_mm": 8.025, "center_pitch_mm": 19.85, "cap_gap_mm": 1.8, "pcb_gap_mm": 3.8},
                    {"row": 4, "left_key": "Space", "right_key": "B", "left_cap_width_mm": 32.3375, "right_cap_width_mm": 18.05, "left_center_to_edge_mm": 15.16875, "right_center_to_edge_mm": 8.025, "center_pitch_mm": 26.99375, "cap_gap_mm": 1.8, "pcb_gap_mm": 3.8},
                ],
            )
            self.assertEqual(manifest["join_keycap_gap_mm"], 1.8)
            self.assertEqual(manifest["one_unit_join_center_pitch_mm"], 19.85)
            self.assertNotIn("join_center_pitch_mm", manifest)
            self.assertEqual(manifest["join_placement_offset_mm"], 0.8)
            self.assertEqual(manifest["row_center_joined_pcb_gap_mm"], 3.8)
            self.assertEqual(manifest["minimum_joined_edge_clearance_mm"], 1.0)
            self.assertEqual(manifest["seam_transition_stagger_mm"], 0.55)
            self.assertEqual(manifest["outline_policy"], "keycap_concealed_except_controller_service")
            self.assertEqual(
                manifest["controller_service_region"],
                {
                    "top_edge_y_mm": 39.25,
                    "nominal_board_height_mm": 122.5,
                    "controller_body_mm": [33.8, 18.3],
                    "positions_mm": {
                        "left": {
                            "u1": [132.7125, 50.75],
                            "battery_slot": [117.9125, 50.75],
                            "battery": [131.7125, 50.75],
                            "j_bat": [115.8125, 59.4],
                            "power": [115.8125, 63.45],
                            "reset": [126.0625, 63.45],
                        },
                        "right": {
                            "u1": [77.4, 50.75],
                            "battery_slot": [92.2, 50.75],
                            "battery": [78.4, 50.75],
                            "j_bat": [94.3, 59.4],
                            "power": [94.3, 63.45],
                            "reset": [84.05, 63.45],
                        },
                    },
                    "battery": {
                        "footprint": "kc2.pretty:BAT_301230_30x12mm",
                        "nominal_size_mm": [30.0, 12.0, 3.0],
                        "placement": "between_carrier_and_socketed_controller",
                        "antenna_keepout_clearance_mm": 3.97,
                        "socket_pad_clearance_mm": 0.72,
                        "physical_stack_measurement": "pending",
                    },
                    "battery_termination": {
                        "footprint": "kc2.pretty:BAT_2Pin_PTH_DirectSolder",
                        "left_rotation_degrees": 180.0,
                        "right_rotation_degrees": 0.0,
                        "pad_1": "BAT+",
                        "pad_2": "GND",
                        "strain_relief_ref": "BAT_LEAD_SLOT1",
                        "lead_drawing_status": "pending_exact_purchased_pack",
                    },
                    "power": {
                        "footprint": "kc2.pretty:SW_IMMS_12V_BSI10_THT",
                        "left_rotation_degrees": 0.0,
                        "right_rotation_degrees": 180.0,
                        "pad_1": "BAT+_common",
                        "pad_2": "NN_B+_on_throw",
                        "pad_3": "NC",
                        "body_size_mm": [10.0, 2.5, 6.4],
                        "actuator_travel_mm": 1.6,
                        "datasheet": "https://amec-gmbh.de/wp-content/uploads/2022/11/BSI-10.pdf",
                        "model": "third_party/kc2.3dshapes/SW_IMMS_12V_BSI10_THT.step",
                        "model_sha256": sha256_file(POWER_SWITCH_MODEL),
                        "model_generator": "tools/generate_kc2_component_models.py",
                        "model_generator_sha256": sha256_file(
                            ROOT / "tools/generate_kc2_component_models.py"
                        ),
                    },
                    "reset": {
                        "footprint": "kc2.pretty:SW_NW3_A06_B3_SMD",
                        "left_rotation_degrees": 0.0,
                        "right_rotation_degrees": 180.0,
                        "pad_1": "RST",
                        "pad_2": "GND",
                        "probe_max_diameter_mm": 3.0,
                        "placement_mode": "controller_key_gap",
                        "service_access": "nonconductive_probe",
                        "service_usb_state": "disconnected",
                    },
                    "nominal_clearances_mm": {
                        "reset_keycap_envelope_mm": 18.05,
                        "reset_body_to_keycap_min": 3.2,
                        "reset_courtyard_to_u1_socket_copper_min": 2.03,
                        "controller_body_to_top_edge": 2.35,
                        "battery_to_socket_pad": 0.72,
                        "battery_to_antenna_keepout": 3.97,
                        "power_to_reset_body": 2.2,
                    },
                    "physical_validation": "pending_battery_power_reset_rf_first_article",
                    "order_ready": False,
                },
            )
            self.assertEqual(
                manifest["autoroute_boundary_policy"],
                {
                    "inset_mm": 0.35,
                    "preserve_controller_above_y_mm": 67.5,
                    "edge_cuts_unchanged": True,
                },
            )
            from tools.verify_kc2_x3_v2 import (
                controller_service_order_readiness_blockers,
                release_candidate_exit_code,
                verify_controller_service_model_binding,
            )

            blockers = controller_service_order_readiness_blockers(manifest)
            self.assertTrue(
                any(
                    "J_BAT1 0.90 mm drill is provisional" in blocker
                    for blocker in blockers
                )
            )
            self.assertEqual(
                release_candidate_exit_code(
                    {"errors": [], "order_readiness_blockers": blockers}
                ),
                2,
            )
            self.assertEqual(
                verify_controller_service_model_binding(manifest),
                [],
            )
            stale_model = json.loads(json.dumps(manifest))
            stale_model["controller_service_region"]["power"]["model_sha256"] = "0" * 64
            self.assertTrue(verify_controller_service_model_binding(stale_model))
            self.assertEqual(
                manifest["diode_placement_policy"]["edge_safe_offsets_mm"],
                {
                    "top_second_key": {"x": 7.0, "y": 7.0, "rotation_degrees": 90.0},
                    "top_other_keys": {"x": -8.75, "y": -3.25, "rotation_degrees": 270.0},
                    "bottom_first_key": {"x": 9.5, "y": 3.25},
                },
            )

    def test_v2_power_reset_routes_match_the_safe_exact_contract(self) -> None:
        import pcbnew

        from tools import generate_kc2_pcbs as generator

        expected_reset = {
            "left": ((126.0625, 63.45), 0.0),
            "right": ((84.05, 63.45), 180.0),
        }
        expected_j_bat_rotation = {"left": 180.0, "right": 0.0}
        expected_routes = {
            "left": {
                ("BAT+", "F.Cu", 115.8125, 59.4, 115.8125, 63.45, 0.75),
                ("NN_B+", "F.Cu", 113.2725, 63.45, 111.3, 63.45, 0.75),
                ("NN_B+", "F.Cu", 111.3, 63.45, 111.3, 55.0, 0.75),
                ("NN_B+", "F.Cu", 111.3, 55.0, 111.3, 47.0, 0.75),
                ("NN_B+", "F.Cu", 111.3, 47.0, 118.7425, 43.13, 0.75),
                ("GND", "B.Cu", 113.2725, 59.4, 113.2725, 53.2, 0.75),
                ("GND", "B.Cu", 113.2725, 53.2, 113.2725, 47.0, 0.75),
                ("GND", "B.Cu", 113.2725, 47.0, 120.0125, 47.0, 0.75),
                ("GND", "B.Cu", 120.0125, 47.0, 121.2825, 43.13, 0.75),
                ("RST", "F.Cu", 122.1875, 63.45, 122.1875, 67.0, 0.25),
                ("RST", "F.Cu", 122.1875, 67.0, 115.8, 67.0, 0.25),
                ("RST", "F.Cu", 115.8, 67.0, 110.3, 67.0, 0.25),
                ("RST", "F.Cu", 110.3, 67.0, 110.3, 60.0, 0.25),
                ("RST", "F.Cu", 110.3, 60.0, 110.3, 53.0, 0.25),
                ("RST", "F.Cu", 110.3, 53.0, 110.3, 46.0, 0.25),
                ("RST", "F.Cu", 110.3, 46.0, 110.3, 40.5, 0.25),
                ("RST", "F.Cu", 110.3, 40.5, 117.0, 40.5, 0.25),
                ("RST", "F.Cu", 117.0, 40.5, 123.8225, 40.5, 0.25),
                ("RST", "F.Cu", 123.8225, 40.5, 123.8225, 43.13, 0.25),
                ("GND", "F.Cu", 129.9375, 63.45, 131.3, 63.45, 0.25),
                ("GND", "B.Cu", 131.3, 63.45, 131.3, 65.8, 0.25),
                ("GND", "B.Cu", 131.3, 65.8, 121.5, 65.8, 0.25),
                ("GND", "B.Cu", 121.5, 65.8, 111.5, 65.8, 0.25),
                ("GND", "B.Cu", 111.5, 65.8, 111.5, 60.0, 0.25),
                ("GND", "B.Cu", 111.5, 60.0, 111.5, 54.0, 0.25),
                ("GND", "B.Cu", 111.5, 54.0, 111.5, 47.0, 0.25),
                ("GND", "B.Cu", 111.5, 47.0, 113.2725, 47.0, 0.25),
            },
            "right": {
                ("BAT+", "F.Cu", 94.3, 59.4, 94.3, 63.45, 0.75),
                ("NN_B+", "F.Cu", 96.84, 63.45, 98.8, 63.45, 0.75),
                ("NN_B+", "F.Cu", 98.8, 63.45, 98.8, 56.0, 0.75),
                ("NN_B+", "F.Cu", 98.8, 56.0, 91.37, 58.37, 0.75),
                ("GND", "B.Cu", 96.84, 59.4, 96.84, 54.5, 0.75),
                ("GND", "B.Cu", 96.84, 54.5, 90.1, 54.5, 0.75),
                ("GND", "B.Cu", 90.1, 54.5, 88.83, 58.37, 0.75),
                ("RST", "F.Cu", 87.925, 63.45, 87.925, 61.0, 0.25),
                ("RST", "F.Cu", 87.925, 61.0, 86.29, 58.37, 0.25),
                ("GND", "F.Cu", 80.175, 63.45, 78.8, 63.45, 0.25),
                ("GND", "B.Cu", 78.8, 63.45, 78.8, 61.0, 0.25),
                ("GND", "B.Cu", 78.8, 61.0, 87.56, 61.0, 0.25),
                ("GND", "B.Cu", 87.56, 61.0, 88.83, 58.37, 0.25),
            },
        }
        expected_vias = {
            "left": {("GND", 131.3, 63.45, 0.6, 0.3)},
            "right": {("GND", 78.8, 63.45, 0.6, 0.3)},
        }

        with TemporaryDirectory(dir=ROOT) as temporary:
            output_dir = Path(temporary) / "x3-v2"
            generator.generate_variant("x3-v2", output_dir=output_dir)
            for side in ("left", "right"):
                with self.subTest(side=side):
                    board_path = (
                        output_dir
                        / f"kc2_{side}-x3-v2"
                        / f"kc2_{side}-x3-v2.kicad_pcb"
                    )
                    board = pcbnew.LoadBoard(str(board_path))
                    reset = board.FindFootprintByReference("SW_RST1")
                    reset_position = reset.GetPosition()
                    self.assertEqual(
                        (
                            round(pcbnew.ToMM(reset_position.x), 4),
                            round(pcbnew.ToMM(reset_position.y), 4),
                        ),
                        expected_reset[side][0],
                    )
                    self.assertEqual(
                        round(reset.GetOrientation().AsDegrees() % 360.0, 3),
                        expected_reset[side][1],
                    )
                    j_bat = board.FindFootprintByReference("J_BAT1")
                    self.assertEqual(
                        round(j_bat.GetOrientation().AsDegrees() % 360.0, 3),
                        expected_j_bat_rotation[side],
                    )
                    actual_routes = {
                        (
                            item.GetNetname(),
                            board.GetLayerName(item.GetLayer()),
                            round(pcbnew.ToMM(item.GetStart().x), 4),
                            round(pcbnew.ToMM(item.GetStart().y), 4),
                            round(pcbnew.ToMM(item.GetEnd().x), 4),
                            round(pcbnew.ToMM(item.GetEnd().y), 4),
                            round(pcbnew.ToMM(item.GetWidth()), 3),
                        )
                        for item in board.GetTracks()
                        if item.GetClass() != "PCB_VIA"
                        and item.GetNetname() in {"RST", "GND", "BAT+", "NN_B+"}
                    }
                    self.assertEqual(actual_routes, expected_routes[side])
                    actual_vias = {
                        (
                            item.GetNetname(),
                            round(pcbnew.ToMM(item.GetPosition().x), 4),
                            round(pcbnew.ToMM(item.GetPosition().y), 4),
                            round(pcbnew.ToMM(item.GetWidth(pcbnew.F_Cu)), 3),
                            round(pcbnew.ToMM(item.GetDrill()), 3),
                        )
                        for item in board.GetTracks()
                        if item.GetClass() == "PCB_VIA"
                        and item.GetNetname() in {"RST", "GND", "BAT+", "NN_B+"}
                    }
                    self.assertEqual(actual_vias, expected_vias[side])

    def test_controller_power_service_manifest_note_is_v2_only(self) -> None:
        from tools import generate_kc2_pcbs as generator

        with TemporaryDirectory(dir=ROOT) as temporary:
            for variant, expected, forbidden in (
                (
                    "x3",
                    "places SW_RST1 on the antenna side outside the TW301525 battery reference clearance",
                    "stacks SW_RST1 beneath the elevated nice!nano USB end",
                ),
                (
                    "x3-v2",
                    "places the 301230 battery beneath socketed U1 and mirrors POWER then RESET from each USB-facing edge",
                    "places SW_RST1 on the antenna side outside the TW301525 battery reference clearance",
                ),
            ):
                output_dir = Path(temporary) / variant
                generator.generate_variant(variant, output_dir=output_dir)
                manifest_name = (
                    "kc2_generation_manifest.json"
                    if variant == "x3"
                    else "kc2_x3_v2_generation_manifest.json"
                )
                manifest = json.loads(
                    (output_dir / manifest_name).read_text(encoding="utf-8")
                )
                notes = "\n".join(manifest["notes"])
                self.assertIn(expected, notes)
                self.assertNotIn(forbidden, notes)

    def test_controller_power_geometry_rejects_keepout_and_route_mutations(self) -> None:
        import pcbnew

        from tools import generate_kc2_pcbs as generator
        from tools.verify_kc2_x3_v2 import controller_power_geometry_report

        with TemporaryDirectory(dir=ROOT) as temporary:
            output_dir = Path(temporary) / "x3-v2"
            generator.generate_variant("x3-v2", output_dir=output_dir)
            board_path = output_dir / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb"

            battery_mutation = pcbnew.LoadBoard(str(board_path))
            battery_mutation.FindFootprintByReference("BAT1").Move(
                pcbnew.VECTOR2I(pcbnew.FromMM(0.5), 0)
            )
            battery_report = controller_power_geometry_report(battery_mutation, "left")
            self.assertTrue(
                any("antenna clearance" in error for error in battery_report["errors"])
            )

            socket_mutation = pcbnew.LoadBoard(str(board_path))
            socket_mutation.FindFootprintByReference("BAT1").Move(
                pcbnew.VECTOR2I(0, pcbnew.FromMM(0.5))
            )
            socket_report = controller_power_geometry_report(socket_mutation, "left")
            self.assertTrue(
                any("socket-pad clearance" in error for error in socket_report["errors"])
            )

            service_mutation = pcbnew.LoadBoard(str(board_path))
            service_mutation.FindFootprintByReference("SW_PWR1").SetPosition(
                pcbnew.VECTOR2I(pcbnew.FromMM(155.0), pcbnew.FromMM(50.0))
            )
            service_report = controller_power_geometry_report(service_mutation, "left")
            self.assertTrue(
                any("SW_PWR1 antenna clearance" in error for error in service_report["errors"])
            )

            parallel_mutation = pcbnew.LoadBoard(str(board_path))
            ground_corridor_points = {(113.2725, 53.2), (113.2725, 47.0)}
            for item in parallel_mutation.GetTracks():
                if item.GetClass() == "PCB_VIA" or item.GetNetname() != "GND":
                    continue
                for getter, setter in (
                    (item.GetStart, item.SetStart),
                    (item.GetEnd, item.SetEnd),
                ):
                    point = getter()
                    point_mm = (
                        round(pcbnew.ToMM(point.x), 4),
                        round(pcbnew.ToMM(point.y), 4),
                    )
                    if point_mm in ground_corridor_points:
                        setter(point + pcbnew.VECTOR2I(pcbnew.FromMM(3.0), 0))
            parallel_report = controller_power_geometry_report(parallel_mutation, "left")
            self.assertTrue(
                any("parallel separation" in error for error in parallel_report["errors"])
            )

            loop_mutation = pcbnew.LoadBoard(str(board_path))
            termination = loop_mutation.FindFootprintByReference("J_BAT1")
            old_pad_points = {
                pad.GetNumber(): pad.GetPosition()
                for pad in termination.Pads()
            }
            termination.Move(pcbnew.VECTOR2I(pcbnew.FromMM(20.0), 0))
            new_pad_points = {
                pad.GetNumber(): pad.GetPosition()
                for pad in termination.Pads()
            }
            for item in loop_mutation.GetTracks():
                if item.GetClass() == "PCB_VIA":
                    continue
                number = "1" if item.GetNetname() == "BAT+" else "2" if item.GetNetname() == "GND" else None
                if number is None:
                    continue
                if item.GetStart() == old_pad_points[number]:
                    item.SetStart(new_pad_points[number])
                if item.GetEnd() == old_pad_points[number]:
                    item.SetEnd(new_pad_points[number])
            loop_report = controller_power_geometry_report(loop_mutation, "left")
            self.assertTrue(
                any("loop area" in error for error in loop_report["errors"]),
                loop_report,
            )

            antenna_parallel_mutation = pcbnew.LoadBoard(str(board_path))
            switch_on = next(
                pad
                for pad in antenna_parallel_mutation.FindFootprintByReference("SW_PWR1").Pads()
                if pad.GetNumber() == "2"
            )
            branch = pcbnew.PCB_TRACK(antenna_parallel_mutation)
            branch.SetStart(switch_on.GetPosition())
            branch.SetEnd(
                switch_on.GetPosition() + pcbnew.VECTOR2I(pcbnew.FromMM(11.0), 0)
            )
            branch.SetLayer(pcbnew.F_Cu)
            branch.SetWidth(pcbnew.FromMM(0.5))
            branch.SetNetCode(antenna_parallel_mutation.FindNet("NN_B+").GetNetCode())
            antenna_parallel_mutation.Add(branch)
            antenna_parallel_report = controller_power_geometry_report(
                antenna_parallel_mutation,
                "left",
            )
            self.assertTrue(
                any(
                    "parallel to antenna keepout edge" in error
                    for error in antenna_parallel_report["errors"]
                )
            )

    def test_compact_edge_repair_is_idempotent_against_generated_diode_positions(self) -> None:
        from tools import generate_kc2_pcbs as generator
        from tools.repair_kc2_x3_v2_compact_edge import repair_board

        with TemporaryDirectory(dir=ROOT) as temporary:
            output_dir = Path(temporary) / "x3-v2"
            generator.generate_variant("x3-v2", output_dir=output_dir)
            board = output_dir / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb"
            backup = Path(temporary) / "backup"

            first = repair_board(board, backup_dir=backup)
            second = repair_board(board, backup_dir=backup)

            self.assertEqual(first["top_diodes_shifted_inward"], [])
            self.assertEqual(first["bottom_diodes_shifted_inward"], [])
            self.assertEqual(first["attached_track_ends_shifted"], 0)
            self.assertEqual(second["top_diodes_shifted_inward"], [])
            self.assertEqual(second["bottom_diodes_shifted_inward"], [])
            self.assertEqual(second["attached_track_ends_shifted"], 0)

    def test_compact_edge_cleanup_removes_an_isolated_autorouter_stub(self) -> None:
        import pcbnew

        from tools import generate_kc2_pcbs as generator
        from tools.repair_kc2_x3_v2_compact_edge import remove_dangling_tracks

        with TemporaryDirectory(dir=ROOT) as temporary:
            output_dir = Path(temporary) / "x3-v2"
            generator.generate_variant("x3-v2", output_dir=output_dir)
            board_path = output_dir / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb"
            board = pcbnew.LoadBoard(str(board_path))
            net = board.FindNet("L_ROW0")
            self.assertIsNotNone(net)
            stub = pcbnew.PCB_TRACK(board)
            stub.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(100.0), pcbnew.FromMM(100.0)))
            stub.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(101.0), pcbnew.FromMM(100.0)))
            stub.SetLayer(pcbnew.B_Cu)
            stub.SetWidth(pcbnew.FromMM(0.25))
            stub.SetNetCode(net.GetNetCode())
            board.Add(stub)

            self.assertEqual(remove_dangling_tracks(board), 1)
            self.assertNotIn(stub, list(board.GetTracks()))

    def test_edge_cut_sync_preserves_routes_and_footprints_and_is_idempotent(self) -> None:
        import pcbnew

        from tools import generate_kc2_pcbs as generator
        from tools.finalize_kc2_x3_v2_routes import _route_signature
        from tools.repair_kc2_x3_v2_compact_edge import sync_edge_cuts_from_generated

        with TemporaryDirectory(dir=ROOT) as temporary:
            output_dir = Path(temporary) / "generated"
            generator.generate_variant("x3-v2", output_dir=output_dir)
            for side, actual_path in (("left", LEFT_BOARD), ("right", RIGHT_BOARD)):
                target = pcbnew.LoadBoard(str(actual_path))
                source_path = (
                    output_dir
                    / f"kc2_{side}-x3-v2"
                    / f"kc2_{side}-x3-v2.kicad_pcb"
                )
                source = pcbnew.LoadBoard(str(source_path))
                route_before = sorted(_route_signature(item) for item in target.GetTracks())
                footprint_before = sorted(
                    (
                        footprint.GetReference(),
                        footprint.GetPosition().x,
                        footprint.GetPosition().y,
                        round(footprint.GetOrientation().AsDegrees(), 3),
                    )
                    for footprint in target.GetFootprints()
                )
                edge = next(
                    drawing
                    for drawing in target.GetDrawings()
                    if drawing.GetLayer() == pcbnew.Edge_Cuts
                )
                edge.Move(pcbnew.VECTOR2I(pcbnew.FromMM(0.1), 0))

                first = sync_edge_cuts_from_generated(target, source)
                second = sync_edge_cuts_from_generated(target, source)

                self.assertGreater(first["edge_drawings_replaced"], 0)
                self.assertEqual(second["edge_drawings_replaced"], 0)
                self.assertEqual(
                    sorted(_route_signature(item) for item in target.GetTracks()),
                    route_before,
                )
                self.assertEqual(
                    sorted(
                        (
                            footprint.GetReference(),
                            footprint.GetPosition().x,
                            footprint.GetPosition().y,
                            round(footprint.GetOrientation().AsDegrees(), 3),
                        )
                        for footprint in target.GetFootprints()
                    ),
                    footprint_before,
                )

    def test_generated_boards_preserve_x3_and_dual_contact_invariants(self) -> None:
        for side, board_path, expected_keys in (
            ("left", LEFT_BOARD, 31),
            ("right", RIGHT_BOARD, 39),
        ):
            with self.subTest(side=side):
                report = analyze_v2_board(board_path)
                self.assertEqual(report["switch_count"], expected_keys)
                self.assertEqual(report["diode_count"], expected_keys)
                self.assertEqual(report["diode_footprint_names"], {"D_ES1B_SMA_HandSolder_C437840"})
                self.assertEqual(report["diode_values"], {"ES1B_Jingdao_C437840_Eleparts9475342"})
                self.assertEqual(report["diode_pin_net_errors"], [])
                self.assertIn(
                    "Diode: Jingdao ES1B / C437840 / Eleparts 9475342; pad 1 = row cathode",
                    report["board_text"],
                )
                self.assertFalse(
                    any("Diode fallback: 1N4148W SOD-123" in text for text in report["board_text"])
                )
                self.assertEqual(report["switch_footprint_names"], {"SW_Choc_V2_Socket_MX_THT"})
                self.assertEqual(report["alternate_contact_net_mismatches"], [])
                self.assertEqual(report["stabilizer_refs"], [])
                self.assertEqual(report["registration_hole_count"], 0)
                self.assertEqual(report["registration_hole_errors"], [])
                self.assertEqual(report["legacy_mount_hole_refs"], [])
                self.assertEqual(report["carrier_power_pad_refs"], ["J_BAT1", "SW_PWR1"])
                self.assertEqual(report["battery_lead_slot_count"], 1)
                self.assertEqual(report["battery_lead_slot_errors"], [])
                self.assertTrue(report["battery_lead_slot_on_usb_side"])
                self.assertEqual(report["forbidden_carrier_power_nets"], [])
                self.assertEqual(report["controller_power_nets"], ["BAT+", "GND", "NN_B+"])
                self.assertEqual(report["controller_socket_row_spacing_mm"], 15.24)
                self.assertEqual(report["switch_layout_errors"], [])
                self.assertLessEqual(report["switch_layout_max_position_error_mm"], 0.001)
                self.assertGreaterEqual(report["minimum_diode_to_unused_npth_clearance_mm"], 1.0)
                self.assertGreaterEqual(report["minimum_diode_to_unrelated_pad_clearance_mm"], 1.0)
                self.assertGreaterEqual(
                    report["minimum_diode_to_unrelated_exposed_copper_clearance_mm"],
                    1.0,
                )
                self.assertGreaterEqual(report["minimum_diode_to_socket_body_clearance_mm"], 1.0)
                self.assertGreaterEqual(
                    report["minimum_diode_fillet_to_switch_assembly_clearance_mm"],
                    0.0,
                )
                self.assertGreaterEqual(
                    report["minimum_diode_fillet_to_edge_cuts_clearance_mm"],
                    1.3,
                )
                self.assertGreaterEqual(
                    report["minimum_diode_fillet_to_unrelated_route_mm"],
                    0.10,
                )
                self.assertEqual(report["diode_edge_clearance_errors"], [])
                self.assertEqual(report["untented_bottom_via_count"], 0)
                self.assertEqual(report["diode_tool_approach_errors"], [])
                self.assertEqual(report["diode_hand_solder_clearance_errors"], [])
                self.assertEqual(report["diode_to_unrelated_route_errors"], [])
                self.assertEqual(len(report["diode_tool_approaches"]), expected_keys * 2)
                self.assertTrue(
                    all(
                        approach["direction"] in {"north", "south", "west", "east"}
                        and approach["length_mm"] == 1.5
                        for approach in report["diode_tool_approaches"]
                    )
                )
                self.assertTrue(
                    any("CHOC V1 UNSUPPORTED" in text.upper() for text in report["board_text"])
                )
                identity_text = " ".join(report["board_text"]).upper()
                self.assertIn("70-KEY V5 NO-STABILIZER SPLIT LAYOUT", identity_text)
                self.assertNotIn("71-KEY V4 NO-STABILIZER SPLIT LAYOUT", identity_text)
                self.assertEqual(report["drc_violation_count"], 0)
                self.assertEqual(report["drc_unconnected_count"], 0)
                self.assertEqual(
                    report["drc_ignored_checks"],
                    [
                        "footprint_filters_mismatch",
                        "footprint_type_mismatch",
                        "missing_courtyard",
                        "track_not_centered_on_via",
                        "tuning_profile_track_geometries",
                    ],
                )

    def test_diode_clearance_gate_rejects_a_pad_moved_into_switch_geometry(self) -> None:
        import pcbnew

        with TemporaryDirectory(dir=ROOT) as temporary:
            copy = Path(temporary) / "kc2_left-x3-v2.kicad_pcb"
            shutil.copy2(LEFT_BOARD, copy)
            board = pcbnew.LoadBoard(str(copy))
            diode = board.FindFootprintByReference("D2")
            self.assertIsNotNone(diode)
            position = diode.GetPosition()
            diode.SetPosition(
                pcbnew.VECTOR2I(
                    position.x - pcbnew.FromMM(1.1),
                    position.y,
                )
            )
            pcbnew.SaveBoard(str(copy), board)

            report = analyze_v2_board(copy)

            self.assertTrue(report["diode_hand_solder_clearance_errors"])

    def test_diode_edge_gate_rejects_a_perimeter_diode_moved_outward(self) -> None:
        import pcbnew

        with TemporaryDirectory(dir=ROOT) as temporary:
            copy = Path(temporary) / "kc2_left-x3-v2.kicad_pcb"
            shutil.copy2(LEFT_BOARD, copy)
            board = pcbnew.LoadBoard(str(copy))
            diode = board.FindFootprintByReference("D3")
            self.assertIsNotNone(diode)
            diode.Move(pcbnew.VECTOR2I(0, -pcbnew.FromMM(0.2)))
            pcbnew.SaveBoard(str(copy), board)

            report = analyze_v2_board(copy)

            self.assertTrue(
                any("D3 edge_cuts_mm=" in error for error in report["diode_edge_clearance_errors"])
            )

    def test_switch_layout_gate_rejects_non_rigid_switch_drift(self) -> None:
        import pcbnew

        with TemporaryDirectory(dir=ROOT) as temporary:
            copy = Path(temporary) / "kc2_left-x3-v2.kicad_pcb"
            shutil.copy2(LEFT_BOARD, copy)
            board = pcbnew.LoadBoard(str(copy))
            switch = board.FindFootprintByReference("SW2")
            self.assertIsNotNone(switch)
            switch.Move(pcbnew.VECTOR2I(pcbnew.FromMM(0.1), 0))
            pcbnew.SaveBoard(str(copy), board)

            report = analyze_v2_board(copy)

            self.assertTrue(report["switch_layout_errors"])
            self.assertGreaterEqual(report["switch_layout_max_position_error_mm"], 0.1)

    def test_switch_layout_gate_rejects_rotation_drift(self) -> None:
        import pcbnew

        with TemporaryDirectory(dir=ROOT) as temporary:
            copy = Path(temporary) / "kc2_right-x3-v2.kicad_pcb"
            shutil.copy2(RIGHT_BOARD, copy)
            board = pcbnew.LoadBoard(str(copy))
            switch = board.FindFootprintByReference("SW2")
            self.assertIsNotNone(switch)
            switch.SetOrientationDegrees(15.0)
            pcbnew.SaveBoard(str(copy), board)

            report = analyze_v2_board(copy)

            self.assertTrue(
                any("SW2 rotation drift" in error for error in report["switch_layout_errors"])
            )

    def test_production_boards_match_owned_placed_footprint_geometry(self) -> None:
        for side, board_path in (("left", LEFT_BOARD), ("right", RIGHT_BOARD)):
            with self.subTest(side=side):
                report = analyze_v2_board(board_path)
                self.assertEqual(report["diode_footprint_geometry_errors"], [])
                self.assertEqual(report["switch_footprint_geometry_errors"], [])
                self.assertEqual(report["controller_contract_errors"], [])
                self.assertEqual(report["reset_contract_errors"], [])

    def test_production_boards_use_exact_selected_m1_4_mounting_pattern(self) -> None:
        expected = {
            "left": [
                ("MH1", 142.6125, 68.0),
                ("MH2", 128.6125, 86.5),
                ("MH3", 100.1125, 93.5),
                ("MH4", 57.1125, 99.0),
                ("MH5", 133.6125, 131.5),
                ("MH6", 55.1125, 144.0),
                ("MH7", 165.6125, 145.0),
                ("MH8", 102.6125, 147.0),
            ],
            "right": [
                ("MH1", 71.6875, 68.0),
                ("MH2", 181.1875, 85.5),
                ("MH3", 147.6875, 93.5),
                ("MH4", 109.6875, 96.5),
                ("MH5", 71.6875, 105.5),
                ("MH6", 42.1875, 106.0),
                ("MH7", 181.1875, 134.5),
                ("MH8", 143.1875, 134.5),
                ("MH9", 51.6875, 144.0),
                ("MH10", 95.6875, 147.0),
            ],
        }
        for side, board_path in (("left", LEFT_BOARD), ("right", RIGHT_BOARD)):
            with self.subTest(side=side):
                report = analyze_v2_board(board_path)
                self.assertEqual(report["mounting_hole_positions_mm"], expected[side])
                self.assertEqual(report["mounting_hole_errors"], [])
                self.assertEqual(report["mounting_hole_silkscreen_errors"], [])
                self.assertEqual(report["mounting_hole_driver_copper_errors"], [])
                self.assertGreaterEqual(
                    report["mounting_hole_clearances"][
                        "minimum_driver_to_copper_mm"
                    ],
                    0.0,
                )
                route_record = analyze_v2_manifest(MANIFEST)[
                    "canonical_route_evidence"
                ][side]
                self.assertEqual(
                    report["route_track_via_count"],
                    route_record["final_track_via_count"],
                )
                self.assertEqual(
                    report["route_digest_sha256"],
                    route_record["route_digest_sha256"],
                )
                identity = " ".join(report["board_text"]).lower()
                self.assertIn("selected m1.4 mh retention", identity)
                self.assertNotIn("no key-field holes", identity)

    def test_mounting_hole_gate_rejects_position_and_npth_contract_mutations(self) -> None:
        import pcbnew

        mutations = (
            (
                "position",
                lambda board: board.FindFootprintByReference("MH1").Move(
                    pcbnew.VECTOR2I(pcbnew.FromMM(0.1), 0)
                ),
            ),
            (
                "drill",
                lambda board: next(
                    iter(board.FindFootprintByReference("MH1").Pads())
                ).SetDrillSize(
                    pcbnew.VECTOR2I(pcbnew.FromMM(1.7), pcbnew.FromMM(1.7))
                ),
            ),
            (
                "plated/netted",
                lambda board: (
                    next(iter(board.FindFootprintByReference("MH1").Pads())).SetAttribute(
                        pcbnew.PAD_ATTRIB_PTH
                    ),
                    next(iter(board.FindFootprintByReference("MH1").Pads())).SetNumber("1"),
                    next(iter(board.FindFootprintByReference("MH1").Pads())).SetNet(
                        board.FindNet("L_COL0")
                    ),
                ),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(label=label), TemporaryDirectory(dir=ROOT) as temporary:
                copy = Path(temporary) / LEFT_BOARD.name
                board = pcbnew.LoadBoard(str(LEFT_BOARD))
                mutate(board)
                pcbnew.SaveBoard(str(copy), board)
                report = analyze_v2_board(copy)
                self.assertTrue(report["mounting_hole_errors"])

    def test_mounting_hole_gate_rejects_hidden_or_wrong_layer_numbering(self) -> None:
        import pcbnew

        mutations = (
            ("hidden", lambda board: board.FindFootprintByReference("MH1").Reference().SetVisible(False)),
            (
                "wrong layer",
                lambda board: board.FindFootprintByReference("MH1").Reference().SetLayer(pcbnew.F_Fab),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(label=label), TemporaryDirectory(dir=ROOT) as temporary:
                copy = Path(temporary) / LEFT_BOARD.name
                board = pcbnew.LoadBoard(str(LEFT_BOARD))
                mutate(board)
                pcbnew.SaveBoard(str(copy), board)
                report = analyze_v2_board(copy)
                self.assertTrue(report["mounting_hole_silkscreen_errors"])

    def test_mounting_hole_gate_rejects_driver_to_route_intersection(self) -> None:
        import pcbnew

        with TemporaryDirectory(dir=ROOT) as temporary:
            copy = Path(temporary) / LEFT_BOARD.name
            board = pcbnew.LoadBoard(str(LEFT_BOARD))
            center = board.FindFootprintByReference("MH1").GetPosition()
            track = pcbnew.PCB_TRACK(board)
            track.SetStart(center - pcbnew.VECTOR2I(pcbnew.FromMM(3.0), 0))
            track.SetEnd(center + pcbnew.VECTOR2I(pcbnew.FromMM(3.0), 0))
            track.SetLayer(pcbnew.F_Cu)
            track.SetWidth(pcbnew.FromMM(0.25))
            track.SetNetCode(board.FindNet("L_COL5").GetNetCode())
            board.Add(track)
            pcbnew.SaveBoard(str(copy), board)
            report = analyze_v2_board(copy)
            self.assertTrue(report["mounting_hole_driver_copper_errors"])
            self.assertLess(
                report["mounting_hole_clearances"]["minimum_driver_to_copper_mm"],
                0.0,
            )

    def test_placed_footprint_gate_rejects_diode_switch_controller_and_reset_mutations(self) -> None:
        import pcbnew

        mutations = (
            (
                "diode pad",
                lambda board: next(
                    pad
                    for pad in board.FindFootprintByReference("D1").Pads()
                    if pad.GetNumber() == "1"
                ).SetSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.9), pcbnew.FromMM(1.8))),
                "diode_footprint_geometry_errors",
            ),
            (
                "diode assembly side",
                lambda board: board.FindFootprintByReference("D1").Flip(
                    board.FindFootprintByReference("D1").GetPosition(), False
                ),
                "diode_footprint_geometry_errors",
            ),
            (
                "diode cathode mark",
                lambda board: next(
                    item
                    for item in board.FindFootprintByReference("D1").GraphicalItems()
                    if item.GetLayer() == pcbnew.B_SilkS
                ).SetFPRelativePosition(
                    pcbnew.VECTOR2I(pcbnew.FromMM(-1.0), pcbnew.FromMM(1.2))
                ),
                "diode_footprint_geometry_errors",
            ),
            (
                "diode fab body",
                lambda board: next(
                    item
                    for item in board.FindFootprintByReference("D1").GraphicalItems()
                    if item.GetLayer() == pcbnew.B_Fab
                    and isinstance(item, pcbnew.PCB_SHAPE)
                ).SetFPRelativePosition(
                    pcbnew.VECTOR2I(pcbnew.FromMM(2.15), pcbnew.FromMM(1.35))
                ),
                "diode_footprint_geometry_errors",
            ),
            (
                "diode courtyard",
                lambda board: next(
                    item
                    for item in board.FindFootprintByReference("D1").GraphicalItems()
                    if item.GetLayer() == pcbnew.B_CrtYd
                ).SetFPRelativePosition(
                    pcbnew.VECTOR2I(pcbnew.FromMM(3.15), pcbnew.FromMM(1.6))
                ),
                "diode_footprint_geometry_errors",
            ),
            (
                "switch mechanical hole",
                lambda board: next(
                    pad
                    for pad in board.FindFootprintByReference("SW1").Pads()
                    if not pad.GetNumber()
                ).SetDrillSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.8), pcbnew.FromMM(1.8))),
                "switch_footprint_geometry_errors",
            ),
            (
                "controller label coordinate",
                lambda board: next(
                    pad
                    for pad in board.FindFootprintByReference("U1").Pads()
                    if pad.GetNumber() == "D0"
                ).SetFPRelativePosition(
                    pcbnew.VECTOR2I(pcbnew.FromMM(-11.33), pcbnew.FromMM(7.62))
                ),
                "controller_contract_errors",
            ),
            (
                "controller position",
                lambda board: board.FindFootprintByReference("U1").SetPosition(
                    pcbnew.VECTOR2I(pcbnew.FromMM(132.7125), pcbnew.FromMM(50.8))
                ),
                "controller_contract_errors",
            ),
            (
                "reset position",
                lambda board: board.FindFootprintByReference("SW_RST1").SetPosition(
                    pcbnew.VECTOR2I(pcbnew.FromMM(113.7625), pcbnew.FromMM(50.8))
                ),
                "reset_contract_errors",
            ),
            (
                "reset rotation",
                lambda board: board.FindFootprintByReference("SW_RST1").SetOrientationDegrees(270),
                "reset_contract_errors",
            ),
            (
                "reset pad2 net",
                lambda board: next(
                    pad
                    for pad in board.FindFootprintByReference("SW_RST1").Pads()
                    if pad.GetNumber() == "2"
                ).SetNet(board.FindNet("RST")),
                "reset_contract_errors",
            ),
        )
        for label, mutate, error_field in mutations:
            with self.subTest(label=label), TemporaryDirectory(dir=ROOT) as temporary:
                copy = Path(temporary) / LEFT_BOARD.name
                board = pcbnew.LoadBoard(str(LEFT_BOARD))
                mutate(board)
                pcbnew.SaveBoard(str(copy), board)
                report = analyze_v2_board(copy)
                self.assertTrue(report[error_field])

    def test_current_projects_and_route_sources_bind_minimum_clearance_and_hashes(self) -> None:
        from tools.verify_kc2_x3_v2 import (
            build_drc_evidence,
            verify_canonical_route_evidence,
        )

        evidence = build_drc_evidence()
        self.assertEqual(evidence["hash_policy"], HASH_POLICY)
        for side in ("left", "right"):
            record = evidence["boards"][side]
            self.assertEqual(record["default_clearance_mm"], 0.3)
            self.assertEqual(
                record["project_sha256"],
                sha256_file(
                    (LEFT_BOARD if side == "left" else RIGHT_BOARD).with_suffix(
                        ".kicad_pro"
                    )
                ),
            )

        route_errors, route_reports = verify_canonical_route_evidence(
            analyze_v2_manifest(MANIFEST)
        )
        self.assertEqual(route_errors, [])
        for side in ("left", "right"):
            self.assertEqual(route_reports[side]["dsn_default_clearance_internal_units"], 300)
            self.assertEqual(
                route_reports[side]["dsn_clearances_internal_units"],
                {"global": 300, "kicad_default": 300},
            )
            self.assertRegex(route_reports[side]["dsn_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(route_reports[side]["ses_sha256"], r"^[0-9a-f]{64}$")

    def test_controller_service_clearances_are_board_derived_and_mutation_sensitive(self) -> None:
        import pcbnew

        from tools.verify_kc2_x3_v2 import controller_service_clearance_report

        for side, board_path, nearest_key in (
            ("left", LEFT_BOARD, "SW5"),
            ("right", RIGHT_BOARD, "SW3"),
        ):
            with self.subTest(side=side):
                board = pcbnew.LoadBoard(str(board_path))
                report = controller_service_clearance_report(board)
                self.assertEqual(report["errors"], [])
                self.assertEqual(report["reset_body_to_nearest_18_05_keycap_mm"], 3.2)
                self.assertEqual(report["nearest_keycap_reference"], nearest_key)
                self.assertEqual(
                    report["reset_courtyard_to_u1_socket_copper_mm"],
                    2.03,
                )

                keycap_mutation = pcbnew.LoadBoard(str(board_path))
                key = keycap_mutation.FindFootprintByReference(nearest_key)
                key_position = key.GetPosition()
                key.SetPosition(
                    pcbnew.VECTOR2I(
                        key_position.x,
                        key_position.y - pcbnew.FromMM(0.1),
                    )
                )
                keycap_report = controller_service_clearance_report(keycap_mutation)
                self.assertEqual(
                    keycap_report["reset_body_to_nearest_18_05_keycap_mm"],
                    3.1,
                )
                self.assertTrue(
                    any("keycap envelope" in error for error in keycap_report["errors"])
                )

                copper_mutation = pcbnew.LoadBoard(str(board_path))
                u1 = copper_mutation.FindFootprintByReference("U1")
                lower_socket_y = max(pad.GetPosition().y for pad in u1.Pads())
                for pad in u1.Pads():
                    if pad.GetPosition().y == lower_socket_y:
                        position = pad.GetPosition()
                        pad.SetPosition(
                            pcbnew.VECTOR2I(
                                position.x,
                                position.y + pcbnew.FromMM(0.1),
                            )
                        )
                copper_report = controller_service_clearance_report(copper_mutation)
                self.assertEqual(
                    copper_report["reset_courtyard_to_u1_socket_copper_mm"],
                    1.93,
                )
                self.assertTrue(
                    any("socket copper" in error for error in copper_report["errors"])
                )

    def test_controller_service_manifest_clearances_reject_missing_or_stale_fields(self) -> None:
        from tools.verify_kc2_x3_v2 import verify_controller_service_manifest_clearances

        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        expected = {
            "reset_keycap_envelope_mm": 18.05,
            "reset_body_to_keycap_min": 3.2,
            "reset_courtyard_to_u1_socket_copper_min": 2.03,
        }
        self.assertEqual(
            {
                key: manifest["controller_service_region"]["nominal_clearances_mm"].get(key)
                for key in expected
            },
            expected,
        )
        self.assertEqual(verify_controller_service_manifest_clearances(manifest), [])

        for field in expected:
            with self.subTest(field=field, mutation="missing"):
                mutated = json.loads(json.dumps(manifest))
                del mutated["controller_service_region"]["nominal_clearances_mm"][field]
                self.assertTrue(verify_controller_service_manifest_clearances(mutated))
            with self.subTest(field=field, mutation="stale"):
                mutated = json.loads(json.dumps(manifest))
                mutated["controller_service_region"]["nominal_clearances_mm"][field] = 0.0
                self.assertTrue(verify_controller_service_manifest_clearances(mutated))

    def test_clearance_bindings_reject_029_project_299_dsn_and_stale_route_hash(self) -> None:
        from tools.verify_kc2_x3_v2 import (
            build_drc_evidence,
            verify_canonical_route_evidence,
            verify_drc_evidence_binding,
        )

        with TemporaryDirectory(dir=ROOT) as temporary:
            temp = Path(temporary)
            board = temp / LEFT_BOARD.name
            shutil.copy2(LEFT_BOARD, board)
            shutil.copy2(LEFT_BOARD.with_suffix(".drc.json"), board.with_suffix(".drc.json"))
            project = json.loads(LEFT_BOARD.with_suffix(".kicad_pro").read_text(encoding="utf-8"))
            next(
                netclass
                for netclass in project["net_settings"]["classes"]
                if netclass["name"] == "Default"
            )["clearance"] = 0.29
            board.with_suffix(".kicad_pro").write_text(
                json.dumps(project, indent=2) + "\n", encoding="utf-8"
            )
            evidence = build_drc_evidence((board,))
            errors, _ = verify_drc_evidence_binding(board, "left", evidence)
            self.assertIn("left: project Default clearance must be at least 0.30 mm", errors)

        manifest = analyze_v2_manifest(MANIFEST)
        with TemporaryDirectory(dir=ROOT) as temporary:
            temp = Path(temporary)
            dsn = temp / "route.dsn"
            ses = temp / "route.ses"
            source_record = manifest["canonical_route_evidence"]["left"]
            source_dsn = ROOT / source_record["dsn"]
            source_ses = ROOT / source_record["ses"]
            dsn.write_text(
                source_dsn.read_text(encoding="utf-8").replace("(clearance 300)", "(clearance 299)"),
                encoding="utf-8",
            )
            shutil.copy2(source_ses, ses)
            mutated = json.loads(json.dumps(manifest))
            record = mutated["canonical_route_evidence"]["left"]
            record.update(
                dsn=str(dsn.relative_to(ROOT)).replace("\\", "/"),
                ses=str(ses.relative_to(ROOT)).replace("\\", "/"),
                dsn_sha256=sha256_file(dsn),
                ses_sha256=sha256_file(ses),
            )
            errors, _ = verify_canonical_route_evidence(mutated)
            self.assertTrue(any("DSN clearance" in error for error in errors))

        stale = json.loads(json.dumps(manifest))
        stale["canonical_route_evidence"]["right"]["ses_sha256"] = "0" * 64
        errors, _ = verify_canonical_route_evidence(stale)
        self.assertTrue(any("right: SES SHA-256 mismatch" in error for error in errors))

        wrong_policy = json.loads(json.dumps(manifest))
        wrong_policy["hash_policy"] = "raw-v0"
        errors, _ = verify_canonical_route_evidence(wrong_policy)
        self.assertIn("manifest: canonical hash policy mismatch", errors)

    def test_manifest_identifies_mutually_exclusive_v2_modes(self) -> None:
        report = analyze_v2_manifest(MANIFEST)
        self.assertEqual(report["hash_policy"], HASH_POLICY)
        self.assertNotIn(b"\r\n", MANIFEST.read_bytes())
        self.assertEqual(report["generated"], "2026-08-29")
        self.assertEqual(report["variant"], "x3-v2")
        self.assertEqual(report["key_count"], {"left": 31, "right": 39, "total": 70})
        self.assertEqual(report["max_key_width_u"], 1.75)
        self.assertEqual(report["keycell_edge_inset_mm"], 1.5)
        self.assertEqual(report["one_unit_join_center_to_edge_mm"], 8.025)
        self.assertNotIn("join_center_to_edge_mm", report)
        self.assertEqual(report["join_keycap_setback_mm"], 1.0)
        self.assertEqual(report["join_keycap_gap_mm"], 1.8)
        self.assertEqual(report["one_unit_join_center_pitch_mm"], 19.85)
        self.assertNotIn("join_center_pitch_mm", report)
        self.assertEqual(report["minimum_joined_edge_clearance_mm"], 1.0)
        self.assertEqual(report["outline_policy"], "keycap_concealed_except_controller_service")
        self.assertIsNone(report.get("x3_tact_battery_clearance_mm"))
        self.assertEqual(
            report["autoroute_boundary_policy"],
            {
                "inset_mm": 0.35,
                "preserve_controller_above_y_mm": 67.5,
                "edge_cuts_unchanged": True,
            },
        )
        self.assertEqual(
            report["pcb_fastener_holes"],
            {
                "footprint": "kc2.pretty:MH_M1.4_NPTH_1.60",
                "references": "MH1..MH8 left; MH1..MH10 right",
                "counts": {"left": 8, "right": 10, "total": 18},
                "positions_mm": {
                    "left": [
                        {"ref": "MH1", "x": 142.6125, "y": 68.0},
                        {"ref": "MH2", "x": 128.6125, "y": 86.5},
                        {"ref": "MH3", "x": 100.1125, "y": 93.5},
                        {"ref": "MH4", "x": 57.1125, "y": 99.0},
                        {"ref": "MH5", "x": 133.6125, "y": 131.5},
                        {"ref": "MH6", "x": 55.1125, "y": 144.0},
                        {"ref": "MH7", "x": 165.6125, "y": 145.0},
                        {"ref": "MH8", "x": 102.6125, "y": 147.0},
                    ],
                    "right": [
                        {"ref": "MH1", "x": 71.6875, "y": 68.0},
                        {"ref": "MH2", "x": 181.1875, "y": 85.5},
                        {"ref": "MH3", "x": 147.6875, "y": 93.5},
                        {"ref": "MH4", "x": 109.6875, "y": 96.5},
                        {"ref": "MH5", "x": 71.6875, "y": 105.5},
                        {"ref": "MH6", "x": 42.1875, "y": 106.0},
                        {"ref": "MH7", "x": 181.1875, "y": 134.5},
                        {"ref": "MH8", "x": 143.1875, "y": 134.5},
                        {"ref": "MH9", "x": 51.6875, "y": 144.0},
                        {"ref": "MH10", "x": 95.6875, "y": 147.0},
                    ],
                },
                "hole": {
                    "type": "NPTH",
                    "diameter_mm": 1.6,
                    "unnetted": True,
                    "copper_free": True,
                },
                "front_silkscreen_reference": {
                    "visible": True,
                    "text_height_mm": 0.8,
                    "stroke_mm": 0.1,
                    "relative_position_mm": {"x": 0.0, "y": -1.5},
                },
                "screw_head_envelope_mm": {"diameter": 2.0, "height": 0.5},
                "vertical_driver_envelope_mm": {"diameter": 3.0},
                "provisional_under_head_screw_length_mm": 4.0,
                "service_state": {"keycaps": "removed", "switches": "installed"},
                "housing_interface_mm": {
                    "zero_gap_support_land_diameter": 3.0,
                    "provisional_blind_pilot_diameter": 1.1,
                    "provisional_blind_pilot_depth": 2.8,
                    "desk_column_closed_bottom": 0.7,
                },
                "registration_status": "pending_full_pattern_physical_fit",
                "physical_validation": "pending",
                "order_ready": False,
            },
        )
        self.assertIsNone(report["screwless_registration_holes"])
        self.assertEqual(
            report["controller_socket_geometry_mm"],
            {
                "longitudinal_pin_pitch": 2.54,
                "row_center_spacing": 15.24,
                "row_count": 2,
                "pins_per_row": 12,
            },
        )
        self.assertEqual(
            report["controller_service_region"]["positions_mm"],
            {
                "left": {
                    "u1": [132.7125, 50.75],
                    "battery_slot": [117.9125, 50.75],
                    "battery": [131.7125, 50.75],
                    "j_bat": [115.8125, 59.4],
                    "power": [115.8125, 63.45],
                    "reset": [126.0625, 63.45],
                },
                "right": {
                    "u1": [77.4, 50.75],
                    "battery_slot": [92.2, 50.75],
                    "battery": [78.4, 50.75],
                    "j_bat": [94.3, 59.4],
                    "power": [94.3, 63.45],
                    "reset": [84.05, 63.45],
                },
            },
        )
        self.assertEqual(
            report["controller_service_region"]["power"],
            {
                "footprint": "kc2.pretty:SW_IMMS_12V_BSI10_THT",
                "left_rotation_degrees": 0.0,
                "right_rotation_degrees": 180.0,
                "pad_1": "BAT+_common",
                "pad_2": "NN_B+_on_throw",
                "pad_3": "NC",
                "body_size_mm": [10.0, 2.5, 6.4],
                "actuator_travel_mm": 1.6,
                "datasheet": "https://amec-gmbh.de/wp-content/uploads/2022/11/BSI-10.pdf",
                "model": "third_party/kc2.3dshapes/SW_IMMS_12V_BSI10_THT.step",
                "model_sha256": sha256_file(POWER_SWITCH_MODEL),
                "model_generator": "tools/generate_kc2_component_models.py",
                "model_generator_sha256": sha256_file(
                    ROOT / "tools/generate_kc2_component_models.py"
                ),
            },
        )
        self.assertEqual(
            report["controller_service_region"]["reset"],
            {
                "footprint": "kc2.pretty:SW_NW3_A06_B3_SMD",
                "left_rotation_degrees": 0.0,
                "right_rotation_degrees": 180.0,
                "pad_1": "RST",
                "pad_2": "GND",
                "probe_max_diameter_mm": 3.0,
                "placement_mode": "controller_key_gap",
                "service_access": "nonconductive_probe",
                "service_usb_state": "disconnected",
            },
        )
        self.assertTrue(report["carrier_power_pads"])
        self.assertEqual(
            report["battery_lead_pass_through_slot"],
            {
                "footprint": "kc2.pretty:BAT_LEAD_NPTH_SLOT_3.6x2.2",
                "value": "BAT_LEAD_NPTH_SLOT_3.6x2.2",
                "size_mm": [3.6, 2.2],
                "count_per_half": 1,
                "layers": "mask-only NPTH, no copper",
                "purpose": (
                    "J_BAT1 strain relief for pre-attached insulated battery leads; "
                    "not a bottom battery exit"
                ),
            },
        )
        self.assertEqual(report["diode_placement_policy"]["minimum_unused_feature_clearance_mm"], 1.0)
        self.assertEqual(
            report["diode_placement_policy"]["edge_safe_offsets_mm"],
            {
                "top_second_key": {"x": 7.0, "y": 7.0, "rotation_degrees": 90.0},
                "top_other_keys": {"x": -8.75, "y": -3.25, "rotation_degrees": 270.0},
                "bottom_first_key": {"x": 9.5, "y": 3.25},
            },
        )
        self.assertEqual(
            report["diode_placement_policy"]["minimum_edge_cuts_clearance_mm"],
            1.3,
        )
        self.assertEqual(report["switch_footprint"], "kc2.pretty:SW_Choc_V2_Socket_MX_THT")
        self.assertEqual(
            report["matrix_diode"],
            {
                "manufacturer": "Jingdao Microelectronics",
                "mpn": "ES1B",
                "lcsc": "C437840",
                "eleparts_goods_no": "9475342",
                "footprint": "kc2.pretty:D_ES1B_SMA_HandSolder_C437840",
                "package": "SMA",
                "assembly_side": "bottom",
                "pin_1": "cathode_row",
                "pin_2": "anode_switch",
                "recommended_land_mm": {"pad_size": [1.8, 1.8], "inner_gap": 2.4},
                "implemented_land_mm": {"pad_size": [1.8, 1.8], "inner_gap": 2.4, "outer_span": 6.0},
                "maximum_package_mm": {"lead_span": 5.2, "body_length": 4.5, "body_width": 2.7, "height": 2.2},
            },
        )
        self.assertEqual(report["assembly_modes"], ["choc_v2_bottom_socket", "mx_5pin_top_direct_solder"])
        self.assertTrue(report["assembly_modes_mutually_exclusive"])
        self.assertEqual(
            report["unsupported_switch_geometry"],
            ["choc_v1", "choc_v2_direct_solder", "mx_hotswap"],
        )
        self.assertEqual(
            report["canonical_route_evidence"],
            {
                "left": {
                    "dsn": "hardware/kicad/draft/x3-v2/autoroute/kc2_left-x3-v2-70-es1b-controller-r3.dsn",
                    "dsn_role": "current_mh_compact_controller_trackless_routing_input",
                    "dsn_mounting_hole_count": 8,
                    "session_source_dsn": "hardware/kicad/draft/x3-v2/autoroute/kc2_left-x3-v2-70-es1b-controller-r3.dsn",
                    "session_source_dsn_sha256": "0f1da995d92a6a121142125933e21ce0c1f1db05e5c1ef924f2a7c6dd38fa3db",
                    "ses": "hardware/kicad/draft/x3-v2/autoroute/kc2_left-x3-v2-70-es1b-controller-r3.ses",
                    "ses_role": "reviewed_matrix_import_plus_exact_edge_cleanup_and_power_reset_service_routing",
                    "dsn_sha256": "0f1da995d92a6a121142125933e21ce0c1f1db05e5c1ef924f2a7c6dd38fa3db",
                    "ses_sha256": "41ba7adf4db9881cf6065b592fd81127de5753b7b23a94012a16e1230cdbf0b8",
                    "dsn_default_clearance_internal_units": 300,
                    "dsn_clearances_internal_units": {"global": 300, "kicad_default": 300},
                    "final_track_via_count": 580,
                    "route_digest_sha256": "7eda6d670a2fd3b99ab06548be4c635dbff03904ec251197f547110864fcb5e6",
                },
                "right": {
                    "dsn": "hardware/kicad/draft/x3-v2/autoroute/kc2_right-x3-v2-70-es1b-controller-r3.dsn",
                    "dsn_role": "current_mh_compact_controller_trackless_routing_input",
                    "dsn_mounting_hole_count": 10,
                    "session_source_dsn": "hardware/kicad/draft/x3-v2/autoroute/kc2_right-x3-v2-70-es1b-controller-r3.dsn",
                    "session_source_dsn_sha256": "45f3bbf61f54d417ab97aeff137aa91db5f323a24ff3473011aaa84ccc9d7e45",
                    "ses": "hardware/kicad/draft/x3-v2/autoroute/kc2_right-x3-v2-70-es1b-controller-r3.ses",
                    "ses_role": "reviewed_matrix_import_plus_exact_edge_cleanup_and_power_reset_service_routing",
                    "dsn_sha256": "45f3bbf61f54d417ab97aeff137aa91db5f323a24ff3473011aaa84ccc9d7e45",
                    "ses_sha256": "58823efa51c642107623d60180f2431eff572c50a11f1dbad8091c35e82ef2fb",
                    "dsn_default_clearance_internal_units": 300,
                    "dsn_clearances_internal_units": {"global": 300, "kicad_default": 300},
                    "final_track_via_count": 739,
                    "route_digest_sha256": "fc2a819d9ce840ffc0c9e9b5ac6fc7dac54d51a441addb5b0005b4fa89cdbf1a",
                },
            },
        )
        self.assertEqual(
            report["firmware_matrix_compatibility"],
            {
                "diode_direction": "col2row",
                "pad_1": "row_cathode",
                "pad_2": "per_key_switch_anode",
                "scan_delay_changed": False,
            },
        )
        self.assertEqual(
            report["physical_scan_validation"],
            {
                "status": "pending",
                "supply_volts": [3.0, 3.3],
                "patterns": ["maximum_same_row", "maximum_same_column"],
                "orderable": False,
            },
        )

    def test_canonical_dsn_truthfully_binds_compact_controller_board_and_session(self) -> None:
        manifest = analyze_v2_manifest(MANIFEST)
        for side, expected_count in (("left", 8), ("right", 10)):
            with self.subTest(side=side):
                record = manifest["canonical_route_evidence"][side]
                self.assertTrue(record["dsn"].endswith("-controller-r3.dsn"))
                self.assertEqual(record["dsn_role"], "current_mh_compact_controller_trackless_routing_input")
                self.assertEqual(record["dsn_mounting_hole_count"], expected_count)
                self.assertEqual(record["session_source_dsn"], record["dsn"])
                self.assertEqual(
                    record["ses_role"],
                    "reviewed_matrix_import_plus_exact_edge_cleanup_and_power_reset_service_routing",
                )

    def test_current_mh_trackless_dsn_export_preserves_compact_controller_contract(self) -> None:
        import pcbnew

        from tools.finalize_kc2_x3_v2_routes import export_current_mh_trackless_dsn
        from tools.verify_kc2_x3_v2 import _dsn_default_clearances

        manifest = analyze_v2_manifest(MANIFEST)
        with TemporaryDirectory(dir=ROOT) as temporary:
            for side, board_path in (("left", LEFT_BOARD), ("right", RIGHT_BOARD)):
                with self.subTest(side=side):
                    board = pcbnew.LoadBoard(str(board_path))
                    for item in list(board.GetTracks()):
                        board.Delete(item)
                    exported = Path(temporary) / f"{side}.dsn"
                    export_current_mh_trackless_dsn(board, exported, side)
                    canonical = ROOT / manifest["canonical_route_evidence"][side]["dsn"]
                    exported_text = exported.read_text(encoding="utf-8")
                    canonical_text = canonical.read_text(encoding="utf-8")
                    self.assertTrue(
                        exported_text.startswith(
                            f'(pcb "kc2_{side}-x3-v2-70-es1b-controller-r3.dsn"'
                        )
                    )
                    self.assertEqual(_dsn_default_clearances(exported), _dsn_default_clearances(canonical))
                    self.assertEqual(
                        len(re.findall(r"\(place\s+MH\d+\b", exported_text)),
                        manifest["canonical_route_evidence"][side]["dsn_mounting_hole_count"],
                    )

    def test_release_candidate_verifier_covers_both_routed_boards(self) -> None:
        report = verify_v2_release_candidate(
            footprint_path=FOOTPRINT,
            board_paths=(LEFT_BOARD, RIGHT_BOARD),
            manifest_path=MANIFEST,
        )

        self.assertEqual(report["requirement"], "CON-ARCH-004")
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["connectivity_errors"], {"left": [], "right": []})

    def test_release_candidate_verifier_wires_exact_board_text_contract_per_side(self) -> None:
        forbidden = "Battery solders directly to nice!nano B+/B-; no carrier power pads"
        required = "BAT STRAIN RELIEF"
        left_report = analyze_v2_board(LEFT_BOARD)
        right_report = analyze_v2_board(RIGHT_BOARD)
        self.assertNotIn(forbidden, left_report["board_text"])
        self.assertIn(required, right_report["board_text"])
        left_report["board_text"] = {*left_report["board_text"], forbidden}
        right_report["board_text"] = {
            text for text in right_report["board_text"] if text != required
        }

        with patch(
            "tools.verify_kc2_x3_v2.analyze_v2_board",
            side_effect=(left_report, right_report),
        ):
            report = verify_v2_release_candidate(
                footprint_path=FOOTPRINT,
                board_paths=(LEFT_BOARD, RIGHT_BOARD),
                manifest_path=MANIFEST,
            )

        self.assertEqual(
            [error for error in report["errors"] if ": board text: " in error],
            [
                f"left: board text: forbidden stale board text remains: {forbidden}",
                f"right: board text: required board text is missing: {required}",
            ],
        )

    def test_release_candidate_verifier_requires_exact_left_and_right_board_set(self) -> None:
        invalid_board_sets = (
            (),
            (Path("candidate_left.kicad_pcb"),),
            (
                Path("candidate_left.kicad_pcb"),
                Path("duplicate_left.kicad_pcb"),
            ),
        )

        for board_paths in invalid_board_sets:
            with self.subTest(board_paths=board_paths), patch(
                "tools.verify_kc2_x3_v2.verify_v2_footprint",
                side_effect=AssertionError("invalid board set touched footprint input"),
            ), patch(
                "tools.verify_kc2_x3_v2.analyze_v2_manifest",
                side_effect=AssertionError("invalid board set touched manifest input"),
            ), patch(
                "tools.verify_kc2_x3_v2.analyze_v2_board",
                side_effect=AssertionError("invalid board set touched board input"),
            ):
                report = verify_v2_release_candidate(
                    footprint_path=Path("missing-footprint.kicad_mod"),
                    board_paths=board_paths,
                    manifest_path=Path("missing-generation-manifest.json"),
                    drc_evidence_path=Path("missing-drc-evidence.json"),
                    housing_manifest_path=Path("missing-housing-manifest.json"),
                )

            self.assertEqual(
                report["errors"],
                ["boards: expected exactly one detected left and one detected right board"],
            )
            self.assertEqual(report["boards"], {})

    def test_release_exit_code_fails_closed_for_malformed_report(self) -> None:
        from tools.verify_kc2_x3_v2 import release_candidate_exit_code

        malformed_reports = (
            {},
            {"errors": []},
            {"order_readiness_blockers": []},
            {"errors": None, "order_readiness_blockers": []},
            {"errors": [], "order_readiness_blockers": {}},
        )

        for report in malformed_reports:
            with self.subTest(report=report):
                self.assertEqual(release_candidate_exit_code(report), 1)

    def test_release_gate_requires_valid_housing_manifest(self) -> None:
        from tools.verify_kc2_x3_v2 import controller_service_order_readiness_blockers

        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        expected = "CON-ARCH-006: housing manifest is missing or invalid"
        for housing_manifest in (None, []):
            with self.subTest(housing_manifest=housing_manifest):
                blockers = controller_service_order_readiness_blockers(
                    manifest,
                    housing_manifest,
                )
                self.assertIn(expected, blockers)

    def test_release_gate_aggregates_physical_order_blockers(self) -> None:
        from tools.verify_kc2_x3_v2 import (
            controller_service_order_readiness_blockers,
            release_candidate_exit_code,
        )

        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        service = manifest["controller_service_region"]
        service["battery_termination"]["lead_drawing_status"] = (
            "confirmed_exact_purchased_pack"
        )
        service["physical_validation"] = (
            "passed_battery_power_reset_rf_first_article"
        )
        service["order_ready"] = True
        manifest["physical_scan_validation"].update(
            status="passed",
            orderable=True,
        )
        housing = json.loads(
            (ROOT / "hardware/case/draft/x3-v2/kc2_x3_v2_housing_manifest.json")
            .read_text(encoding="utf-8")
        )
        housing["order_ready"] = True
        housing["retention"]["physical_registration_status"] = "passed"
        housing["physical_deflection_test"]["status"] = "passed"

        self.assertEqual(
            controller_service_order_readiness_blockers(manifest, housing),
            [],
        )
        for label, mutate, expected in (
            (
                "physical scan pending",
                lambda generation, _housing: generation[
                    "physical_scan_validation"
                ].update(status="pending"),
                "physical scan validation status is not passed",
            ),
            (
                "physical scan not orderable",
                lambda generation, _housing: generation[
                    "physical_scan_validation"
                ].update(orderable=False),
                "physical scan validation is not orderable",
            ),
            (
                "housing not order ready",
                lambda _generation, case_housing: case_housing.update(
                    order_ready=False
                ),
                "housing manifest order_ready is not true",
            ),
            (
                "retention registration pending",
                lambda _generation, case_housing: case_housing["retention"].update(
                    physical_registration_status="pending"
                ),
                "housing physical registration status is not passed",
            ),
            (
                "deflection test pending",
                lambda _generation, case_housing: case_housing[
                    "physical_deflection_test"
                ].update(status="pending"),
                "housing physical deflection test status is not passed",
            ),
        ):
            with self.subTest(label=label):
                case_manifest = json.loads(json.dumps(manifest))
                case_housing = json.loads(json.dumps(housing))
                mutate(case_manifest, case_housing)
                blockers = controller_service_order_readiness_blockers(
                    case_manifest,
                    case_housing,
                )
                self.assertTrue(any(expected in blocker for blocker in blockers))
                self.assertEqual(
                    release_candidate_exit_code(
                        {"errors": [], "order_readiness_blockers": blockers}
                    ),
                    2,
                )

    def test_active_v2_board_text_contract_rejects_exact_stale_service_texts(self) -> None:
        from tools.verify_kc2_x3_v2 import verify_active_v2_board_text_contract

        required = "BAT STRAIN RELIEF"
        forbidden = (
            "Battery solders directly to nice!nano B+/B-; no carrier power pads",
            "BAT LEAD EXIT",
        )
        self.assertEqual(verify_active_v2_board_text_contract({required}), [])
        for stale_text in forbidden:
            with self.subTest(stale_text=stale_text):
                errors = verify_active_v2_board_text_contract(
                    {required, stale_text}
                )
                self.assertTrue(
                    any(stale_text in error and "forbidden" in error for error in errors)
                )
        self.assertTrue(
            any(
                required in error and "required" in error
                for error in verify_active_v2_board_text_contract(set())
            )
        )

    def test_release_gate_rejects_stale_m1_4_mount_manifest(self) -> None:
        with TemporaryDirectory(dir=ROOT) as temporary:
            for label, mutate in (
                (
                    "wrong coordinate",
                    lambda record: record["positions_mm"]["right"][5].update(x=42.2875),
                ),
                (
                    "premature registration",
                    lambda record: record.update(registration_status="verified"),
                ),
                (
                    "premature order state",
                    lambda record: record.update(order_ready=True),
                ),
            ):
                with self.subTest(label=label):
                    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
                    mutate(manifest["pcb_fastener_holes"])
                    path = Path(temporary) / f"{label.replace(' ', '-')}.json"
                    path.write_text(json.dumps(manifest), encoding="utf-8")
                    report = verify_v2_release_candidate(
                        footprint_path=FOOTPRINT,
                        board_paths=(LEFT_BOARD, RIGHT_BOARD),
                        manifest_path=path,
                    )
                    self.assertIn(
                        "manifest: exact selected M1.4 MH pattern and service envelope are missing or stale",
                        report["errors"],
                    )

    def test_release_gate_cross_binds_pcb_and_housing_closed_bottom(self) -> None:
        with TemporaryDirectory(dir=ROOT) as temporary:
            housing = json.loads(
                (ROOT / "hardware/case/draft/x3-v2/kc2_x3_v2_housing_manifest.json")
                .read_text(encoding="utf-8")
            )
            housing["parameters"]["mounting_closed_bottom_mm"] = 0.5
            path = Path(temporary) / "stale-housing-manifest.json"
            path.write_text(json.dumps(housing), encoding="utf-8")

            report = verify_v2_release_candidate(
                footprint_path=FOOTPRINT,
                board_paths=(LEFT_BOARD, RIGHT_BOARD),
                manifest_path=MANIFEST,
                housing_manifest_path=path,
            )
            self.assertIn(
                "manifest: PCB/housing mounting closed-bottom contract mismatch",
                report["errors"],
            )

    def test_route_finalizer_is_idempotent_on_committed_route(self) -> None:
        import pcbnew

        from tools.finalize_kc2_x3_v2_routes import apply_reviewed_cleanup, load_reviewed_drc

        with TemporaryDirectory(dir=ROOT) as temporary:
            copy = Path(temporary) / "kc2_right-x3-v2.kicad_pcb"
            shutil.copy2(RIGHT_BOARD, copy)
            report = load_reviewed_drc(RIGHT_BOARD.with_suffix(".drc.json"))
            board = pcbnew.LoadBoard(str(copy))

            first = apply_reviewed_cleanup(board, report, "right")
            second = apply_reviewed_cleanup(board, report, "right")

            self.assertEqual(first["dangling_tracks_removed"], 0)
            self.assertEqual(first["warning_silkscreen_texts_moved_to_fab"], 0)
            self.assertEqual(first["v2_key_labels_moved_to_fab"], 0)
            self.assertEqual(second, first)

    def test_controller_compact_sessions_reconstruct_exactly_and_are_idempotent(self) -> None:
        import pcbnew

        from tools import generate_kc2_pcbs as generator
        from tools.finalize_kc2_x3_v2_routes import (
            CONTROLLER_COMPACT_ROUTE_ITEM_COUNTS,
            CONTROLLER_COMPACT_ROUTE_SHA256,
            _route_counter_digest,
            _route_signature,
            import_reviewed_controller_compact_session,
        )
        from tools.verify_kc2_connectivity import verify_board as verify_connectivity

        with TemporaryDirectory(dir=ROOT) as temporary:
            output_dir = Path(temporary) / "x3-v2"
            generator.generate_variant("x3-v2", output_dir=output_dir)
            for side, expected in (
                ("left", {"imported": 539, "removed": 25, "added": 66, "final": 580}),
                ("right", {"imported": 703, "removed": 27, "added": 63, "final": 739}),
            ):
                with self.subTest(side=side):
                    board_path = (
                        output_dir
                        / f"kc2_{side}-x3-v2"
                        / f"kc2_{side}-x3-v2.kicad_pcb"
                    )
                    board = pcbnew.LoadBoard(str(board_path))
                    for item in list(board.GetTracks()):
                        board.Delete(item)
                    session = (
                        V2_ROOT
                        / "autoroute"
                        / f"kc2_{side}-x3-v2-70-es1b-controller-r3.ses"
                    )
                    first = import_reviewed_controller_compact_session(board, session, side)
                    second = import_reviewed_controller_compact_session(board, session, side)
                    pcbnew.SaveBoard(str(board_path), board)

                    self.assertEqual(
                        first,
                        {
                            "imported_track_and_via_items": expected["imported"],
                            "reviewed_items_removed": expected["removed"],
                            "reviewed_items_added": expected["added"],
                            "final_track_and_via_items": expected["final"],
                        },
                    )
                    self.assertEqual(
                        second,
                        {
                            "imported_track_and_via_items": 0,
                            "reviewed_items_removed": 0,
                            "reviewed_items_added": 0,
                            "final_track_and_via_items": expected["final"],
                        },
                    )
                    signatures = Counter(_route_signature(item) for item in board.GetTracks())
                    self.assertEqual(sum(signatures.values()), CONTROLLER_COMPACT_ROUTE_ITEM_COUNTS[side])
                    self.assertEqual(
                        _route_counter_digest(signatures),
                        CONTROLLER_COMPACT_ROUTE_SHA256[side],
                    )
                    self.assertEqual(verify_connectivity(board_path), [])

                    stale = pcbnew.LoadBoard(str(board_path))
                    for item in list(stale.GetTracks()):
                        stale.Delete(item)
                    reset = stale.FindFootprintByReference("SW_RST1")
                    reset.Move(pcbnew.VECTOR2I(pcbnew.FromMM(0.1), 0))
                    with self.assertRaisesRegex(RuntimeError, "controller service geometry mismatch"):
                        import_reviewed_controller_compact_session(stale, session, side)

    def test_controller_import_pins_complete_imported_route_before_transformations(self) -> None:
        import pcbnew

        from tools import generate_kc2_pcbs as generator
        from tools.finalize_kc2_x3_v2_routes import (
            CONTROLLER_COMPACT_IMPORTED_ROUTE_SHA256,
            _route_counter_digest,
            _route_signature,
            import_reviewed_controller_compact_session,
        )

        with TemporaryDirectory(dir=ROOT) as temporary:
            output_dir = Path(temporary) / "x3-v2"
            generator.generate_variant("x3-v2", output_dir=output_dir)
            for side, original, replacement in (
                ("left", "1167392 -673250", "1166392 -673250"),
                ("right", "933733 -673250", "932733 -673250"),
            ):
                with self.subTest(side=side):
                    board_path = (
                        output_dir
                        / f"kc2_{side}-x3-v2"
                        / f"kc2_{side}-x3-v2.kicad_pcb"
                    )
                    board = pcbnew.LoadBoard(str(board_path))
                    for item in list(board.GetTracks()):
                        board.Delete(item)
                    session = (
                        V2_ROOT
                        / "autoroute"
                        / f"kc2_{side}-x3-v2-70-es1b-controller-r3.ses"
                    )
                    mutated_session = Path(temporary) / f"mutated-{side}.ses"
                    source = session.read_text(encoding="utf-8")
                    self.assertGreaterEqual(source.count(original), 2)
                    mutated_session.write_text(
                        source.replace(original, replacement, 1),
                        encoding="utf-8",
                    )

                    with self.assertRaisesRegex(
                        RuntimeError,
                        f"reviewed {side} controller-compaction imported route digest changed",
                    ):
                        import_reviewed_controller_compact_session(
                            board,
                            mutated_session,
                            side,
                        )

                    imported = Counter(
                        _route_signature(item) for item in board.GetTracks()
                    )
                    self.assertNotEqual(
                        _route_counter_digest(imported),
                        CONTROLLER_COMPACT_IMPORTED_ROUTE_SHA256[side],
                    )
                    reset = board.FindFootprintByReference("SW_RST1")
                    reset_position = reset.GetPosition()
                    self.assertNotEqual(
                        (
                            round(pcbnew.ToMM(reset_position.x), 4),
                            round(pcbnew.ToMM(reset_position.y), 4),
                        ),
                        generator.X3_V2_CONTROLLER_SERVICE_POSITIONS_MM[side]["reset"],
                    )

    def test_controller_idempotent_path_rejects_service_rotation_and_pad_disconnects(self) -> None:
        import pcbnew

        from tools import generate_kc2_pcbs as generator
        from tools.finalize_kc2_x3_v2_routes import (
            import_reviewed_controller_compact_session,
        )

        expected_rotations = {
            "left": {
                "U1": 0.0,
                "BAT1": 0.0,
                "J_BAT1": 180.0,
                "SW_PWR1": 0.0,
                "BAT_LEAD_SLOT1": 0.0,
                "SW_RST1": 0.0,
            },
            "right": {
                "U1": 0.0,
                "BAT1": 0.0,
                "J_BAT1": 0.0,
                "SW_PWR1": 180.0,
                "BAT_LEAD_SLOT1": 0.0,
                "SW_RST1": 180.0,
            },
        }
        disconnected_pads = (
            ("U1", "RST", "RST"),
            ("U1", "GND_C", "GND"),
            ("J_BAT1", "1", "BAT+"),
            ("U1", "RAW", "NN_B+"),
        )

        with TemporaryDirectory(dir=ROOT) as temporary:
            output_dir = Path(temporary) / "x3-v2"
            generator.generate_variant("x3-v2", output_dir=output_dir)
            for side in ("left", "right"):
                board_path = (
                    output_dir
                    / f"kc2_{side}-x3-v2"
                    / f"kc2_{side}-x3-v2.kicad_pcb"
                )
                board = pcbnew.LoadBoard(str(board_path))
                for item in list(board.GetTracks()):
                    board.Delete(item)
                session = (
                    V2_ROOT
                    / "autoroute"
                    / f"kc2_{side}-x3-v2-70-es1b-controller-r3.ses"
                )
                import_reviewed_controller_compact_session(board, session, side)
                final_path = Path(temporary) / f"final-{side}.kicad_pcb"
                pcbnew.SaveBoard(str(final_path), board)

                for reference, rotation in expected_rotations[side].items():
                    with self.subTest(side=side, rotated=reference):
                        rotated = pcbnew.LoadBoard(str(final_path))
                        rotated.FindFootprintByReference(reference).SetOrientationDegrees(
                            (rotation + 90.0) % 360.0
                        )
                        with self.assertRaisesRegex(
                            RuntimeError,
                            "controller service geometry mismatch",
                        ):
                            import_reviewed_controller_compact_session(
                                rotated,
                                session,
                                side,
                            )

                for reference, number, net_name in disconnected_pads:
                    with self.subTest(side=side, disconnected=net_name):
                        disconnected = pcbnew.LoadBoard(str(final_path))
                        footprint = disconnected.FindFootprintByReference(reference)
                        pad = next(
                            item
                            for item in footprint.Pads()
                            if item.GetNumber() == number
                        )
                        pad.Move(pcbnew.VECTOR2I(pcbnew.FromMM(5.0), 0))
                        with self.assertRaisesRegex(
                            RuntimeError,
                            f"nonempty.*exact reviewed {side} controller-compaction route",
                        ):
                            import_reviewed_controller_compact_session(
                                disconnected,
                                session,
                                side,
                            )

    def test_left_matrix_service_detours_replace_only_cataloged_signatures(self) -> None:
        import pcbnew

        from tools import generate_kc2_pcbs as generator
        from tools.finalize_kc2_x3_v2_routes import (
            _add_route_spec,
            _route_signature,
            apply_matrix_service_detours,
        )

        with TemporaryDirectory(dir=ROOT) as temporary:
            output_dir = Path(temporary) / "x3-v2"
            generator.generate_variant("x3-v2", output_dir=output_dir)
            board_path = output_dir / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb"
            board = pcbnew.LoadBoard(str(board_path))
            for item in list(board.GetTracks()):
                board.Delete(item)
            expected_removed = {
                ("track", "L_COL0", "F.Cu", 131.4425, 58.37, 117.9254, 71.8871, 0.25),
                ("track", "L_COL1", "F.Cu", 132.069, 59.7698, 119.2058, 72.633, 0.25),
                ("track", "L_COL2", "B.Cu", 122.1599, 70.1926, 133.9825, 58.37, 0.25),
            }
            expected_added = {
                ("track", "L_COL0", "B.Cu", 131.4425, 58.37, 132.1, 60.0, 0.25),
                ("track", "L_COL0", "B.Cu", 132.1, 60.0, 132.1, 67.0, 0.25),
                ("track", "L_COL0", "B.Cu", 132.1, 67.0, 117.9254, 71.8871, 0.25),
                ("via", "L_COL0", 117.9254, 71.8871, 0.6, 0.3),
                ("track", "L_COL1", "B.Cu", 132.069, 59.7698, 133.1, 60.5, 0.25),
                ("via", "L_COL1", 132.069, 59.7698, 0.6, 0.3),
                ("track", "L_COL1", "B.Cu", 133.1, 60.5, 133.1, 67.5, 0.25),
                ("track", "L_COL1", "B.Cu", 133.1, 67.5, 119.2058, 72.633, 0.25),
                ("via", "L_COL1", 119.2058, 72.633, 0.6, 0.3),
                ("track", "L_COL2", "B.Cu", 133.9825, 58.37, 134.5, 59.0, 0.25),
                ("track", "L_COL2", "B.Cu", 134.5, 59.0, 134.5, 68.0, 0.25),
                ("track", "L_COL2", "B.Cu", 134.5, 68.0, 122.1599, 70.1926, 0.25),
            }
            for spec in expected_removed:
                _add_route_spec(board, spec)
            before = Counter(_route_signature(item) for item in board.GetTracks())
            self.assertTrue(expected_removed <= set(before))

            result = apply_matrix_service_detours(board, "left")
            after = Counter(_route_signature(item) for item in board.GetTracks())
            self.assertEqual(result, {"removed": 3, "added": 12})
            self.assertFalse(expected_removed & set(after))
            self.assertTrue(expected_added <= set(after))
            self.assertEqual(
                sum(after.values()),
                sum(before.values()) - len(expected_removed) + len(expected_added),
            )

    def test_left_cycle3_matrix_connectivity_detours_replace_only_minimum_hitting_set(self) -> None:
        import pcbnew

        from tools import generate_kc2_pcbs as generator
        from tools.finalize_kc2_x3_v2_routes import (
            MATRIX_CONNECTIVITY_ROUTE_ADDITIONS,
            MATRIX_CONNECTIVITY_ROUTE_REMOVALS,
            _add_route_spec,
            _route_signature,
            apply_matrix_connectivity_detours,
        )

        expected_removed = {
            ("track", "L_COL0", "B.Cu", 131.4425, 58.37, 132.1, 60.0, 0.25),
            ("track", "L_COL0", "B.Cu", 132.1, 60.0, 132.1, 67.0, 0.25),
            ("track", "L_COL0", "B.Cu", 132.1, 67.0, 117.9254, 71.8871, 0.25),
            ("via", "L_COL0", 117.9254, 71.8871, 0.6, 0.3),
            ("track", "L_COL1", "F.Cu", 135.1227, 59.7698, 132.069, 59.7698, 0.25),
            ("track", "L_COL1", "B.Cu", 132.069, 59.7698, 133.1, 60.5, 0.25),
            ("via", "L_COL1", 132.069, 59.7698, 0.6, 0.3),
            ("track", "L_COL1", "B.Cu", 133.1, 60.5, 133.1, 67.5, 0.25),
            ("track", "L_COL1", "B.Cu", 133.1, 67.5, 119.2058, 72.633, 0.25),
            ("via", "L_COL1", 119.2058, 72.633, 0.6, 0.3),
        }
        expected_added = {
            ("track", "L_COL0", "B.Cu", 131.4425, 58.37, 132.2, 60.0, 0.25),
            ("track", "L_COL0", "B.Cu", 132.2, 60.0, 132.2, 66.5, 0.25),
            ("track", "L_COL0", "B.Cu", 132.2, 66.5, 129.0, 68.0, 0.25),
            ("via", "L_COL0", 129.0, 68.0, 0.6, 0.3),
            ("track", "L_COL0", "F.Cu", 129.0, 68.0, 117.9254, 71.8871, 0.25),
            ("track", "L_COL1", "F.Cu", 135.1227, 59.7698, 136.5, 59.4, 0.25),
            ("via", "L_COL1", 136.5, 59.4, 0.6, 0.3),
            ("track", "L_COL1", "B.Cu", 136.5, 59.4, 136.5, 68.5, 0.25),
            ("track", "L_COL1", "B.Cu", 136.5, 68.5, 134.8, 68.7, 0.25),
            ("track", "L_COL1", "B.Cu", 134.8, 68.7, 132.0, 69.15, 0.25),
            ("track", "L_COL1", "B.Cu", 132.0, 69.15, 129.0, 69.75, 0.25),
            ("track", "L_COL1", "B.Cu", 129.0, 69.75, 128.5, 70.0, 0.25),
            ("via", "L_COL1", 128.5, 70.0, 0.6, 0.3),
            ("track", "L_COL1", "F.Cu", 128.5, 70.0, 125.6, 70.5, 0.25),
            ("track", "L_COL1", "F.Cu", 125.6, 70.5, 125.6, 74.5, 0.25),
            ("track", "L_COL1", "F.Cu", 125.6, 74.5, 119.5, 74.5, 0.25),
            ("track", "L_COL1", "F.Cu", 119.5, 74.5, 119.2058, 72.633, 0.25),
        }
        self.assertEqual(set(MATRIX_CONNECTIVITY_ROUTE_REMOVALS["left"]), expected_removed)
        self.assertEqual(set(MATRIX_CONNECTIVITY_ROUTE_ADDITIONS["left"]), expected_added)
        self.assertEqual(
            generator.X3_V2_MATRIX_CONNECTIVITY_DETOURS["left"],
            {
                "removals": MATRIX_CONNECTIVITY_ROUTE_REMOVALS["left"],
                "additions": MATRIX_CONNECTIVITY_ROUTE_ADDITIONS["left"],
            },
        )

        with TemporaryDirectory(dir=ROOT) as temporary:
            output_dir = Path(temporary) / "x3-v2"
            generator.generate_variant("x3-v2", output_dir=output_dir)
            board_path = output_dir / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb"
            board = pcbnew.LoadBoard(str(board_path))
            for item in list(board.GetTracks()):
                board.Delete(item)
            for spec in expected_removed:
                _add_route_spec(board, spec)
            before = Counter(_route_signature(item) for item in board.GetTracks())

            result = apply_matrix_connectivity_detours(board, "left")
            after = Counter(_route_signature(item) for item in board.GetTracks())
            self.assertEqual(result, {"removed": 10, "added": 17})
            self.assertFalse(expected_removed & set(after))
            self.assertTrue(expected_added <= set(after))
            self.assertEqual(sum(after.values()), sum(before.values()) + 7)

            second = apply_matrix_connectivity_detours(board, "left")
            self.assertEqual(second, {"removed": 0, "added": 0})

    def test_right_service_matrix_detours_replace_only_colliding_fanout(self) -> None:
        import pcbnew

        from tools import generate_kc2_pcbs as generator
        from tools.finalize_kc2_x3_v2_routes import (
            MATRIX_CONNECTIVITY_ROUTE_ADDITIONS,
            MATRIX_CONNECTIVITY_ROUTE_REMOVALS,
            _add_route_spec,
            _route_signature,
            apply_matrix_connectivity_detours,
        )

        expected_removed = {
            ("track", "R_COL5", "F.Cu", 73.59, 58.37, 83.162, 67.942, 0.25),
            ("track", "R_COL6", "F.Cu", 94.1212, 76.3612, 76.13, 58.37, 0.25),
            ("track", "R_COL7", "B.Cu", 90.9461, 59.9321, 82.7721, 59.9321, 0.25),
            ("track", "R_COL7", "B.Cu", 101.1625, 70.1485, 90.9461, 59.9321, 0.25),
            ("track", "R_COL2", "B.Cu", 71.2975, 63.6975, 84.4425, 63.6975, 0.25),
            ("track", "R_COL2", "B.Cu", 84.4425, 63.6975, 93.19, 72.445, 0.25),
            ("track", "R_COL3", "B.Cu", 71.8386, 61.6986, 90.4512, 61.6986, 0.25),
            ("track", "R_COL3", "B.Cu", 90.4512, 61.6986, 99.4528, 70.7002, 0.25),
            ("track", "R_ROW0", "F.Cu", 91.6389, 54.9233, 98.7624, 62.0468, 0.25),
            ("track", "R_ROW0", "F.Cu", 98.7624, 62.0468, 98.7624, 71.4811, 0.25),
            ("track", "R_ROW3", "F.Cu", 91.7219, 54.177, 100.2, 62.6551, 0.25),
        }
        expected_added = {
            ("track", "R_COL3", "B.Cu", 71.8386, 61.6986, 80.5, 65.0, 0.25),
            ("track", "R_COL3", "B.Cu", 80.5, 65.0, 99.4528, 70.7002, 0.25),
            ("track", "R_COL2", "B.Cu", 71.2975, 63.6975, 79.5, 65.5, 0.25),
            ("via", "R_COL2", 79.5, 65.5, 0.6, 0.3),
            ("track", "R_COL2", "F.Cu", 79.5, 65.5, 83.0, 65.5, 0.25),
            ("track", "R_COL2", "F.Cu", 83.0, 65.5, 86.0, 68.5, 0.25),
            ("via", "R_COL2", 86.0, 68.5, 0.6, 0.3),
            ("track", "R_COL2", "B.Cu", 86.0, 68.5, 90.5, 70.5, 0.25),
            ("via", "R_COL2", 90.5, 70.5, 0.6, 0.3),
            ("track", "R_COL2", "F.Cu", 90.5, 70.5, 93.19, 72.445, 0.25),
            ("track", "R_COL7", "B.Cu", 82.7721, 59.9321, 84.0, 60.0, 0.25),
            ("via", "R_COL7", 84.0, 60.0, 0.6, 0.3),
            ("track", "R_COL7", "F.Cu", 84.0, 60.0, 87.0, 62.0, 0.25),
            ("via", "R_COL7", 87.0, 62.0, 0.6, 0.3),
            ("track", "R_COL7", "B.Cu", 87.0, 62.0, 88.5, 62.0, 0.25),
            ("track", "R_COL7", "B.Cu", 88.5, 62.0, 92.0, 65.5, 0.25),
            ("track", "R_COL7", "B.Cu", 92.0, 65.5, 101.1625, 70.1485, 0.25),
            ("track", "R_COL6", "F.Cu", 76.13, 58.37, 85.0, 65.0, 0.25),
            ("track", "R_COL6", "F.Cu", 85.0, 65.0, 94.1212, 76.3612, 0.25),
            ("track", "R_COL5", "F.Cu", 73.59, 58.37, 73.5, 59.5, 0.25),
            ("via", "R_COL5", 73.5, 59.5, 0.6, 0.3),
            ("track", "R_COL5", "B.Cu", 73.5, 59.5, 72.5, 61.0, 0.25),
            ("via", "R_COL5", 72.5, 61.0, 0.6, 0.3),
            ("track", "R_COL5", "F.Cu", 72.5, 61.0, 77.5, 66.0, 0.25),
            ("via", "R_COL5", 77.5, 66.0, 0.6, 0.3),
            ("track", "R_COL5", "B.Cu", 77.5, 66.0, 82.0, 67.5, 0.25),
            ("via", "R_COL5", 82.0, 67.5, 0.6, 0.3),
            ("track", "R_COL5", "F.Cu", 82.0, 67.5, 83.162, 67.942, 0.25),
            ("track", "R_ROW0", "F.Cu", 91.6389, 54.9233, 98.0, 55.0, 0.25),
            ("via", "R_ROW0", 98.0, 55.0, 0.6, 0.3),
            ("track", "R_ROW0", "B.Cu", 98.0, 55.0, 98.5, 60.5, 0.25),
            ("track", "R_ROW0", "B.Cu", 98.5, 60.5, 98.5, 67.5, 0.25),
            ("via", "R_ROW0", 98.5, 67.5, 0.6, 0.3),
            ("track", "R_ROW0", "F.Cu", 98.5, 67.5, 98.7624, 71.4811, 0.25),
            ("track", "R_ROW3", "F.Cu", 91.7219, 54.177, 92.5, 54.2, 0.25),
            ("track", "R_ROW3", "F.Cu", 92.5, 54.2, 100.2, 54.2, 0.25),
            ("track", "R_ROW3", "F.Cu", 100.2, 54.2, 100.2, 62.6551, 0.25),
        }
        self.assertEqual(set(MATRIX_CONNECTIVITY_ROUTE_REMOVALS["right"]), expected_removed)
        self.assertEqual(set(MATRIX_CONNECTIVITY_ROUTE_ADDITIONS["right"]), expected_added)
        self.assertEqual(
            generator.X3_V2_MATRIX_CONNECTIVITY_DETOURS["right"],
            {
                "removals": MATRIX_CONNECTIVITY_ROUTE_REMOVALS["right"],
                "additions": MATRIX_CONNECTIVITY_ROUTE_ADDITIONS["right"],
            },
        )

        with TemporaryDirectory(dir=ROOT) as temporary:
            output_dir = Path(temporary) / "x3-v2"
            generator.generate_variant("x3-v2", output_dir=output_dir)
            board_path = output_dir / "kc2_right-x3-v2" / "kc2_right-x3-v2.kicad_pcb"
            board = pcbnew.LoadBoard(str(board_path))
            for item in list(board.GetTracks()):
                board.Delete(item)
            for spec in expected_removed:
                _add_route_spec(board, spec)
            before = Counter(_route_signature(item) for item in board.GetTracks())

            result = apply_matrix_connectivity_detours(board, "right")
            after = Counter(_route_signature(item) for item in board.GetTracks())
            self.assertEqual(result, {"removed": 11, "added": 37})
            self.assertFalse(expected_removed & set(after))
            self.assertTrue(expected_added <= set(after))
            self.assertEqual(sum(after.values()), sum(before.values()) + 26)

            second = apply_matrix_connectivity_detours(board, "right")
            self.assertEqual(second, {"removed": 0, "added": 0})

    def test_controller_route_import_rejects_partial_and_stale_session(self) -> None:
        import pcbnew

        from tools import generate_kc2_pcbs as generator
        from tools.finalize_kc2_x3_v2_routes import import_reviewed_controller_compact_session

        session = V2_ROOT / "autoroute/kc2_right-x3-v2-70-es1b-controller-r3.ses"
        with TemporaryDirectory(dir=ROOT) as temporary:
            output_dir = Path(temporary) / "x3-v2"
            generator.generate_variant("x3-v2", output_dir=output_dir)
            board_path = output_dir / "kc2_right-x3-v2" / "kc2_right-x3-v2.kicad_pcb"

            partial = pcbnew.LoadBoard(str(board_path))
            for item in list(partial.GetTracks()):
                partial.Delete(item)
            import_reviewed_controller_compact_session(partial, session, "right")
            partial.Delete(next(iter(partial.GetTracks())))
            with self.assertRaisesRegex(
                RuntimeError,
                "nonempty.*exact reviewed right controller-compaction route",
            ):
                import_reviewed_controller_compact_session(partial, session, "right")

            wrong_geometry = pcbnew.LoadBoard(str(board_path))
            for item in list(wrong_geometry.GetTracks()):
                wrong_geometry.Delete(item)
            reset = wrong_geometry.FindFootprintByReference("SW_RST1")
            reset.SetPosition(reset.GetPosition() + pcbnew.VECTOR2I(pcbnew.FromMM(0.1), 0))
            with self.assertRaisesRegex(RuntimeError, "controller service geometry mismatch"):
                import_reviewed_controller_compact_session(wrong_geometry, session, "right")

            stale_session = Path(temporary) / session.name
            source = session.read_text(encoding="utf-8")
            stale_session.write_text(
                source.replace("1134000 -834250", "1134000 -834251", 1),
                encoding="utf-8",
            )
            self.assertNotEqual(stale_session.read_bytes(), session.read_bytes())
            stale_board = pcbnew.LoadBoard(str(board_path))
            for item in list(stale_board.GetTracks()):
                stale_board.Delete(item)
            with self.assertRaisesRegex(RuntimeError, "reviewed right controller"):
                import_reviewed_controller_compact_session(stale_board, stale_session, "right")

    def test_drc_evidence_binds_current_boards_and_reports(self) -> None:
        from tools.verify_kc2_x3_v2 import build_drc_evidence

        evidence = json.loads(DRC_EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(evidence, build_drc_evidence())
        self.assertEqual(
            evidence["requirement_ids"],
            ["CON-ARCH-004", "CON-ARCH-006", "CON-ARCH-007", "REL-ARCH-001"],
        )
        self.assertEqual(evidence["hash_policy"], HASH_POLICY)
        self.assertEqual(evidence["variant"], "x3-v2")
        self.assertEqual(set(evidence["boards"]), {"left", "right"})
        for side, board in (("left", LEFT_BOARD), ("right", RIGHT_BOARD)):
            record = evidence["boards"][side]
            report = board.with_suffix(".drc.json")
            parsed = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(record["board_sha256"], sha256_file(board))
            self.assertEqual(record["drc_report_sha256"], sha256_file(report))
            self.assertEqual(record["schema"], parsed["$schema"])
            self.assertEqual(record["source"], parsed["source"])
            self.assertEqual(record["kicad_version"], parsed["kicad_version"])
            self.assertEqual(record["date"], parsed["date"])
            self.assertEqual(record["included_severities"], parsed["included_severities"])

    def test_product_spec_uses_current_70_key_v5_quantities(self) -> None:
        product_spec = PRODUCT_SPEC.read_text(encoding="utf-8")

        current_claims = (
            "디지털 검증을 통과했지만 물리 검증 대기 중인 `kc2-x3-v2` draft는 `CON-ARCH-004`의 70-key v5 배열(왼쪽 31, 오른쪽 39)",
            "70 for digitally verified but not orderable `kc2-x3-v2` under `CON-ARCH-004` (31 left / 39 right)",
            "current X3 V2 v5 rows 15 / 14 / 14 / 15 / 12",
            "active draft `kc2-x3-v2` uses exact Jingdao `ES1B`, LCSC `C437840`, Eleparts goods `9475342`, bottom-side SMA at each of its 70 positions",
            "물리 검증 대기 중인 `kc2-x3-v2` draft는 `CON-ARCH-004`의 70개 switch/diode 배치를 기준으로 별도 검증한다",
            "| KC2 X3 V2 target switch | Kailh Deep Sea Whale low-profile Choc V2 / PG1353-class, 70개.",
            "| KC2 X3 V2 socket | Kailh Choc hot-swap socket `CPG135001S30` class, 70개",
            "| KC2 X3 V2 MX alternative | Cherry MX-style 5-pin PCB-mount switches, 70개",
        )
        for claim in current_claims:
            self.assertIn(claim, product_spec)

        stale_current_claims = (
            "implemented draft `kc2-x3-v2`는 `CON-ARCH-004`의 71-key v4",
            "implemented draft `kc2-x3-v2` 71-key v4",
            "71 for implemented draft `kc2-x3-v2` under `CON-ARCH-004` (32 left / 39 right)",
            "current X3 V2 v4 rows 15 / 14 / 14 / 15 / 13",
            "implemented draft `kc2-x3-v2` uses the same SOD-123 diode at each of its 71 positions",
            "implemented draft `kc2-x3-v2`는 `CON-ARCH-004` switch footprint와 SOD-123 diode 71개",
            "implemented draft `kc2-x3-v2` uses the same SOD-123 diode at each of its 70 positions",
            "implemented draft `kc2-x3-v2`는 `CON-ARCH-004` switch footprint와 SOD-123 diode 70개",
        )
        for stale_claim in stale_current_claims:
            self.assertNotIn(stale_claim, product_spec)

    def test_product_spec_and_srs_scope_the_v2_reset_and_battery_exceptions(self) -> None:
        product_spec = PRODUCT_SPEC.read_text(encoding="utf-8")
        srs = (ROOT / "docs/spec/10.product-architecture.srs.md").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "X3 V2에서는 `CON-ARCH-007`에 따라 controller-key gap에 mirrored POWER/RESET pair를 둔다.",
            product_spec,
        )
        self.assertIn(
            "Lower housing에는 TW301525 또는 301230 battery-body cavity를 만들지 않는다.",
            product_spec,
        )
        self.assertNotIn(
            "X3 compact controller tab의 프로그래밍용 tact switch는 antenna-side controller-tab edge 쪽 상면에 두며",
            product_spec,
        )
        self.assertNotIn(
            "프로그래밍용 tact switch는 antenna-side controller-tab edge 쪽으로 이동하되",
            product_spec,
        )
        self.assertIn(
            "Promoted/historical X3의 `NW3-A06-B3` antenna-side 상면 위치 검증; X3 V2는 `CON-ARCH-007`의 mirrored controller-key-gap service gate 적용",
            product_spec,
        )
        self.assertNotIn(
            "`NW3-A06-B3` SMD tact switch의 antenna-side 상면 위치와 1:1 출력물 기반 조작 검증",
            product_spec,
        )
        self.assertIn(
            "The top-side SW_RST1 actuator support is an explicit exception",
            srs,
        )
        self.assertIn(
            "The 8 mm estimate is not fit evidence and remains subject to AC-3 caliper and first-article gates.",
            srs,
        )
        self.assertIn(
            "Old TW301525, no-carrier-power, USB-under-reset, battery-body-cutout and controller-r3 route hashes are historical only.",
            srs,
        )
        self.assertNotIn(
            "The implemented driver-clearance detours produce the current 564/732 route-item result.",
            srs,
        )

    def test_drc_evidence_rejects_self_consistent_invalid_metadata(self) -> None:
        from tools.verify_kc2_x3_v2 import (
            build_drc_evidence,
            verify_drc_evidence_binding,
        )

        mutations = (
            ("kicad_version", "9.0.6", "KiCad DRC version must be 10.x"),
            ("date", "not-an-iso-timestamp", "KiCad DRC date is not a valid ISO timestamp"),
            ("included_severities", ["error"], "KiCad DRC included_severities must contain error and warning"),
            (
                "included_severities",
                ["error", "warning", "info"],
                "KiCad DRC included_severities contains an unsupported value",
            ),
        )
        for field, value, expected_error in mutations:
            with self.subTest(field=field), TemporaryDirectory(dir=ROOT) as temporary:
                temp = Path(temporary)
                board = temp / LEFT_BOARD.name
                report_path = board.with_suffix(".drc.json")
                shutil.copy2(LEFT_BOARD, board)
                shutil.copy2(LEFT_BOARD.with_suffix(".kicad_pro"), board.with_suffix(".kicad_pro"))
                report = json.loads(LEFT_BOARD.with_suffix(".drc.json").read_text(encoding="utf-8"))
                report[field] = value
                report_path.write_text(json.dumps(report, indent=4) + "\n", encoding="utf-8")
                evidence = build_drc_evidence((board,))

                errors, _record = verify_drc_evidence_binding(board, "left", evidence)

                self.assertIn(f"left: {expected_error}", errors)

        evidence = build_drc_evidence()
        evidence["hash_policy"] = "raw-v0"
        errors, _record = verify_drc_evidence_binding(LEFT_BOARD, "left", evidence)
        self.assertIn("left: DRC evidence canonical hash policy mismatch", errors)

    def test_canonical_hashes_match_exact_git_index_blobs(self) -> None:
        if not (ROOT / ".git").exists():
            self.skipTest("exact Git index is unavailable in an exported snapshot")
        paths = (
            LEFT_BOARD,
            RIGHT_BOARD,
            LEFT_BOARD.with_suffix(".kicad_pro"),
            RIGHT_BOARD.with_suffix(".kicad_pro"),
            LEFT_BOARD.with_suffix(".drc.json"),
            RIGHT_BOARD.with_suffix(".drc.json"),
            ROOT / "hardware/kicad/draft/x3-v2/autoroute/kc2_left-x3-v2-70-es1b-controller-r3.dsn",
            ROOT / "hardware/kicad/draft/x3-v2/autoroute/kc2_left-x3-v2-70-es1b-controller-r3.ses",
            ROOT / "hardware/kicad/draft/x3-v2/autoroute/kc2_right-x3-v2-70-es1b-controller-r3.dsn",
            ROOT / "hardware/kicad/draft/x3-v2/autoroute/kc2_right-x3-v2-70-es1b-controller-r3.ses",
        )
        for path in paths:
            relative = path.relative_to(ROOT).as_posix()
            staged = subprocess.run(
                ["git", "show", f":{relative}"],
                cwd=ROOT,
                check=True,
                stdout=subprocess.PIPE,
            ).stdout
            with self.subTest(path=relative):
                self.assertEqual(sha256_file(path), sha256_bytes(staged))

    def test_drc_evidence_writer_is_reproducible(self) -> None:
        from tools.generate_kc2_x3_v2_drc_evidence import write_drc_evidence

        with TemporaryDirectory(dir=ROOT) as temporary:
            output = Path(temporary) / "drc-evidence.json"
            first = write_drc_evidence(output)
            first_bytes = output.read_bytes()
            second = write_drc_evidence(output)

            self.assertEqual(first, second)
            self.assertEqual(output.read_bytes(), first_bytes)
            self.assertNotIn(b"\r\n", first_bytes)
            self.assertEqual(first, json.loads(DRC_EVIDENCE.read_text(encoding="utf-8")))

    def test_release_verifier_rejects_mutated_board_with_stale_drc_evidence(self) -> None:
        with TemporaryDirectory(dir=ROOT) as temporary:
            temp = Path(temporary)
            boards = []
            for source in (LEFT_BOARD, RIGHT_BOARD):
                board = temp / source.name
                report = board.with_suffix(".drc.json")
                shutil.copy2(source, board)
                shutil.copy2(source.with_suffix(".drc.json"), report)
                shutil.copy2(source.with_suffix(".kicad_pro"), board.with_suffix(".kicad_pro"))
                boards.append(board)
            boards[0].write_bytes(boards[0].read_bytes() + b"\n")

            report = verify_v2_release_candidate(
                footprint_path=FOOTPRINT,
                board_paths=boards,
                manifest_path=MANIFEST,
                drc_evidence_path=DRC_EVIDENCE,
            )

            self.assertIn("left: DRC evidence board SHA-256 mismatch", report["errors"])

    def test_release_verifier_rejects_mutated_drc_report_with_stale_evidence(self) -> None:
        with TemporaryDirectory(dir=ROOT) as temporary:
            temp = Path(temporary)
            boards = []
            for source in (LEFT_BOARD, RIGHT_BOARD):
                board = temp / source.name
                report = board.with_suffix(".drc.json")
                shutil.copy2(source, board)
                shutil.copy2(source.with_suffix(".drc.json"), report)
                shutil.copy2(source.with_suffix(".kicad_pro"), board.with_suffix(".kicad_pro"))
                boards.append(board)
            reports = [board.with_suffix(".drc.json") for board in boards]
            reports[1].write_bytes(reports[1].read_bytes() + b"\n")

            report = verify_v2_release_candidate(
                footprint_path=FOOTPRINT,
                board_paths=boards,
                manifest_path=MANIFEST,
                drc_evidence_path=DRC_EVIDENCE,
            )

            self.assertIn("right: DRC evidence report SHA-256 mismatch", report["errors"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
