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
V2_ROOT = ROOT / "hardware" / "kicad" / "draft" / "x3-v2"
LEFT_BOARD = V2_ROOT / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb"
RIGHT_BOARD = V2_ROOT / "kc2_right-x3-v2" / "kc2_right-x3-v2.kicad_pcb"
MANIFEST = V2_ROOT / "kc2_x3_v2_generation_manifest.json"
DRC_EVIDENCE = V2_ROOT / "kc2_x3_v2_drc_evidence.json"
PRODUCT_SPEC = ROOT / "docs/spec.md"


class V2FootprintTests(unittest.TestCase):
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
        self.assertEqual(generator.X3_V2_RESET_ROTATION_DEGREES, 90.0)
        self.assertEqual(generator.X3_V2_BATTERY_Y_MM, 53.05)
        self.assertEqual(
            generator.X3_V2_CONTROLLER_SERVICE_POSITIONS_MM,
            {
                "left": {
                    "u1": (132.7125, 50.75),
                    "battery_slot": (117.9125, 50.75),
                    "battery": (133.2125, 53.05),
                    "reset": (115.8125, 63.45),
                },
                "right": {
                    "u1": (77.4, 50.75),
                    "battery_slot": (92.2, 50.75),
                    "battery": (76.9, 53.05),
                    "reset": (94.3, 63.45),
                },
            },
        )
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
        self.assertIn("supersedes_for_v2_reset_only", product_srs)
        self.assertIn("`SW_RST1` centers shall be `(115.8125, 63.4500)` and `(94.3000, 63.4500)`", product_srs)
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
                    ("BAT_LEAD_SLOT1", "battery_slot"),
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
                reset = generated_board.FindFootprintByReference("SW_RST1")
                self.assertEqual(round(reset.GetOrientation().AsDegrees(), 3), 90.0)
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
                        "1": (expected_service["reset"][0], 67.325, "RST"),
                        "2": (expected_service["reset"][0], 59.575, "GND"),
                    },
                )
                from tools.verify_kc2_compact_controller import board_rect_bbox

                self.assertEqual(
                    tuple(round(value, 4) for value in board_rect_bbox(generated_board, pcbnew.B_Fab)),
                    (
                        expected_service["battery"][0] - 7.5,
                        expected_service["battery"][1] - 12.5,
                        expected_service["battery"][0] + 7.5,
                        expected_service["battery"][1] + 12.5,
                    ),
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
                    if fp.GetReference().startswith("SW") and fp.GetReference() != "SW_RST1"
                )[0]
                self.assertEqual(top_row_y, 77.525)
                from tools.verify_kc2_compact_controller import check_side

                self.assertEqual(check_side(side, board_path), [])
                from tools.verify_kc2_x3_v2 import (
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
                            "battery": [133.2125, 53.05],
                            "reset": [115.8125, 63.45],
                        },
                        "right": {
                            "u1": [77.4, 50.75],
                            "battery_slot": [92.2, 50.75],
                            "battery": [76.9, 53.05],
                            "reset": [94.3, 63.45],
                        },
                    },
                    "reset": {
                        "footprint": "kc2.pretty:SW_NW3_A06_B3_SMD",
                        "rotation_degrees": 90.0,
                        "pad_1": "RST_key_side",
                        "pad_2": "GND_controller_side",
                        "probe_max_diameter_mm": 3.0,
                        "actuator_corridor_diameter_mm": 4.0,
                        "service_usb_state": "disconnected",
                    },
                    "nominal_clearances_mm": {
                        "controller_body_to_reset_body": 0.5,
                        "reset_body_to_keycap": 2.0,
                        "reset_courtyard_to_keycap": 0.075,
                        "reset_pad_to_keycap": 0.3,
                        "controller_body_to_top_edge": 2.35,
                        "battery_body_to_top_edge": 1.3,
                        "battery_housing_perimeter_land": 0.85,
                    },
                    "physical_validation": "pending_usb_reset_keycap_battery_first_article",
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
            self.assertEqual(
                manifest["diode_placement_policy"]["edge_safe_offsets_mm"],
                {
                    "top_second_key": {"x": 7.0, "y": 7.0, "rotation_degrees": 90.0},
                    "top_other_keys": {"x": -8.75, "y": -3.25, "rotation_degrees": 270.0},
                    "bottom_first_key": {"x": 9.5, "y": 3.25},
                },
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
                self.assertEqual(report["carrier_power_pad_refs"], [])
                self.assertEqual(report["battery_lead_slot_count"], 1)
                self.assertEqual(report["battery_lead_slot_errors"], [])
                self.assertTrue(report["battery_lead_slot_on_usb_side"])
                self.assertEqual(report["forbidden_carrier_power_nets"], [])
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
                    pcbnew.VECTOR2I(pcbnew.FromMM(115.8125), pcbnew.FromMM(63.5))
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
        self.assertEqual(report["generated"], "2026-08-26")
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
                    "ses_role": "reviewed_compact_controller_import_plus_exact_edge_cleanup",
                    "dsn_sha256": "0f1da995d92a6a121142125933e21ce0c1f1db05e5c1ef924f2a7c6dd38fa3db",
                    "ses_sha256": "41ba7adf4db9881cf6065b592fd81127de5753b7b23a94012a16e1230cdbf0b8",
                    "dsn_default_clearance_internal_units": 300,
                    "dsn_clearances_internal_units": {"global": 300, "kicad_default": 300},
                    "final_track_via_count": 543,
                    "route_digest_sha256": "9bc9cbf981da8d452b82e52d54a4e8ab3cafcc6121ec578f36a4cf43f3dde19d",
                },
                "right": {
                    "dsn": "hardware/kicad/draft/x3-v2/autoroute/kc2_right-x3-v2-70-es1b-controller-r3.dsn",
                    "dsn_role": "current_mh_compact_controller_trackless_routing_input",
                    "dsn_mounting_hole_count": 10,
                    "session_source_dsn": "hardware/kicad/draft/x3-v2/autoroute/kc2_right-x3-v2-70-es1b-controller-r3.dsn",
                    "session_source_dsn_sha256": "45f3bbf61f54d417ab97aeff137aa91db5f323a24ff3473011aaa84ccc9d7e45",
                    "ses": "hardware/kicad/draft/x3-v2/autoroute/kc2_right-x3-v2-70-es1b-controller-r3.ses",
                    "ses_role": "reviewed_compact_controller_import_plus_exact_edge_cleanup",
                    "dsn_sha256": "45f3bbf61f54d417ab97aeff137aa91db5f323a24ff3473011aaa84ccc9d7e45",
                    "ses_sha256": "58823efa51c642107623d60180f2431eff572c50a11f1dbad8091c35e82ef2fb",
                    "dsn_default_clearance_internal_units": 300,
                    "dsn_clearances_internal_units": {"global": 300, "kicad_default": 300},
                    "final_track_via_count": 706,
                    "route_digest_sha256": "83dcc6f764670b379b6c9104d643925cd6eff3c0b16286f12bae14dd1397c67f",
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
                    "reviewed_compact_controller_import_plus_exact_edge_cleanup",
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
                ("left", {"imported": 539, "removed": 5, "added": 9, "final": 543}),
                ("right", {"imported": 703, "removed": 9, "added": 12, "final": 706}),
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

    def test_controller_route_import_rejects_partial_and_stale_session(self) -> None:
        import pcbnew

        from tools.finalize_kc2_x3_v2_routes import import_reviewed_controller_compact_session

        session = V2_ROOT / "autoroute/kc2_right-x3-v2-70-es1b-controller-r3.ses"
        partial = pcbnew.LoadBoard(str(RIGHT_BOARD))
        partial.Delete(next(iter(partial.GetTracks())))
        with self.assertRaisesRegex(RuntimeError, "nonempty.*exact reviewed right controller-compaction route"):
            import_reviewed_controller_compact_session(partial, session, "right")

        wrong_geometry = pcbnew.LoadBoard(str(RIGHT_BOARD))
        for item in list(wrong_geometry.GetTracks()):
            wrong_geometry.Delete(item)
        reset = wrong_geometry.FindFootprintByReference("SW_RST1")
        reset.SetPosition(reset.GetPosition() + pcbnew.VECTOR2I(pcbnew.FromMM(0.1), 0))
        with self.assertRaisesRegex(RuntimeError, "controller service geometry mismatch"):
            import_reviewed_controller_compact_session(wrong_geometry, session, "right")

        with TemporaryDirectory(dir=ROOT) as temporary:
            stale_session = Path(temporary) / session.name
            source = session.read_text(encoding="utf-8")
            stale_session.write_text(
                source.replace("1134000 -834250", "1134000 -834251", 1),
                encoding="utf-8",
            )
            self.assertNotEqual(stale_session.read_bytes(), session.read_bytes())
            stale_board = pcbnew.LoadBoard(str(RIGHT_BOARD))
            for item in list(stale_board.GetTracks()):
                stale_board.Delete(item)
            with self.assertRaisesRegex(RuntimeError, "reviewed right controller"):
                import_reviewed_controller_compact_session(stale_board, stale_session, "right")

    def test_drc_evidence_binds_current_boards_and_reports(self) -> None:
        from tools.verify_kc2_x3_v2 import build_drc_evidence

        evidence = json.loads(DRC_EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(evidence, build_drc_evidence())
        self.assertEqual(evidence["requirement_ids"], ["CON-ARCH-004", "CON-ARCH-006"])
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
            "implemented draft `kc2-x3-v2`는 `CON-ARCH-004`의 70-key v5 배열(왼쪽 31, 오른쪽 39)",
            "70 for implemented draft `kc2-x3-v2` under `CON-ARCH-004` (31 left / 39 right)",
            "current X3 V2 v5 rows 15 / 14 / 14 / 15 / 12",
            "active draft `kc2-x3-v2` uses exact Jingdao `ES1B`, LCSC `C437840`, Eleparts goods `9475342`, bottom-side SMA at each of its 70 positions",
            "implemented draft `kc2-x3-v2`는 `CON-ARCH-004`의 70개 switch/diode 배치를 기준으로 별도 검증한다",
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

        self.assertGreaterEqual(
            product_spec.count(
                "X3 V2에서는 `CON-ARCH-004` AC-12가 reset 위치만 USB-side로 supersede한다."
            ),
            2,
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
            "Promoted/historical X3의 `NW3-A06-B3` SMD tact switch antenna-side 상면 위치와 1:1 출력물 기반 조작 검증; X3 V2는 `CON-ARCH-004` AC-12의 USB-side 물리 service gate 적용",
            product_spec,
        )
        self.assertNotIn(
            "`NW3-A06-B3` SMD tact switch의 antenna-side 상면 위치와 1:1 출력물 기반 조작 검증",
            product_spec,
        )
        self.assertIn(
            "The top-side `SW_RST1` actuator support required by AC-11 is an explicit exception",
            srs,
        )
        self.assertIn(
            "the provisional battery clearance is the AC-11 nominal value and remains subject to the pending physical tolerance gate",
            srs,
        )
        self.assertIn(
            "Their 564/732 driver-clearance result is the pre-controller-compaction M1.4 baseline and is superseded by the current controller-r3 543/706 route evidence",
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
