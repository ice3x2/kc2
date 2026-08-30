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
            ["CON-ARCH-004", "CON-ARCH-006", "CON-ARCH-007", "REL-ARCH-001"],
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
        from tools.verify_kc2_x3_v2 import (
            battery_termination_assembly_marking_errors,
            normalized_battery_termination_markings,
        )

        self.assertEqual(
            normalized_battery_termination_markings(battery),
            [
                ("1", "B+", "F.Silkscreen", 0.0, -1.65, 0.8, 0.8, 0.12),
                ("2", "B-/GND", "F.Silkscreen", 2.54, 1.8, 0.8, 0.8, 0.12),
            ],
        )
        self.assertEqual(battery_termination_assembly_marking_errors(battery), [])

        def swap_battery_markings(footprint: pcbnew.FOOTPRINT) -> None:
            items = {
                item.GetText(): item
                for item in footprint.GraphicalItems()
                if isinstance(item, pcbnew.PCB_TEXT)
                and item.GetText() in {"B+", "B-/GND"}
            }
            items["B+"].SetText("B-/GND")
            items["B-/GND"].SetText("B+")

        for label, mutate in (
            (
                "swapped",
                swap_battery_markings,
            ),
            (
                "missing",
                lambda footprint: footprint.Remove(
                    next(
                        item
                        for item in footprint.GraphicalItems()
                        if isinstance(item, pcbnew.PCB_TEXT) and item.GetText() == "B-/GND"
                    )
                ),
            ),
        ):
            with self.subTest(battery_marking_mutation=label):
                mutated = pcbnew.FOOTPRINT(battery)
                mutate(mutated)
                self.assertTrue(battery_termination_assembly_marking_errors(mutated))

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
            (0.8, 0.15, 0.0, -1.5),
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
        import pcbnew

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

        footprint = pcbnew.FootprintLoad(str(FOOTPRINT.parent), FOOTPRINT.stem)
        self.assertIsNotNone(footprint)
        back_courtyard_points = [
            (
                round(pcbnew.ToMM(point.x), 3),
                round(pcbnew.ToMM(point.y), 3),
            )
            for item in footprint.GraphicalItems()
            if item.GetLayer() == pcbnew.B_CrtYd
            for point in (item.GetStart(), item.GetEnd())
        ]
        self.assertEqual(
            (
                min(point[0] for point in back_courtyard_points),
                min(point[1] for point in back_courtyard_points),
                max(point[0] for point in back_courtyard_points),
                max(point[1] for point in back_courtyard_points),
            ),
            (-10.25, 1.2, 5.25, 8.5),
        )
        self.assertEqual(
            report["choc_socket_back_courtyard_mm"],
            {
                "bounds": (-10.25, 1.2, 5.25, 8.5),
                "manufacturing_allowance": 0.25,
                "encloses_body_and_lands": True,
            },
        )

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
    def test_procurement_identity_field_roles_reject_status_prose(self) -> None:
        from tools.verify_kc2_x3_v2 import (
            _procurement_object_identity_errors,
            _valid_drawing_revision,
            _valid_procurement_identifier,
            _valid_procurement_manufacturer,
        )

        status_prose = (
            "UNKNOWN SUPPLIER",
            "PENDING DATASHEET",
            "TBD SKU",
            "TBA SOURCE",
            "UNSET PURCHASE",
            "PROVISIONAL DOC",
            "TODO DATASHEET",
            "FIXME SUPPLIER",
            "TO BE CONFIRMED",
            "NOT KNOWN",
            "AWAITING SELECTION",
            "AWAITING",
            "UNSPECIFIED",
            "UNSELECTED",
            "UNDECIDED",
            "UNRESOLVED",
            "UNCONFIRMED",
            "NOT YET SELECTED",
            "TO FOLLOW",
            "DRAFT",
            "TENTATIVE",
            "DEFERRED",
            "LATER",
            "PENDING SELECTION",
        )
        for value in status_prose:
            with self.subTest(manufacturer_status=value):
                self.assertFalse(_valid_procurement_manufacturer(value))
            with self.subTest(identifier_status=value):
                self.assertFalse(_valid_procurement_identifier(value))
            with self.subTest(revision_status=value):
                self.assertFalse(_valid_drawing_revision(value))

        for value in (
            "Unknown Industries U-1",
            "Nakamura",
            "TBC Precision",
            "KAILH",
        ):
            with self.subTest(valid_manufacturer=value):
                self.assertTrue(_valid_procurement_manufacturer(value))
        for value in (
            "TBC-40",
            "NA-100",
            "CPG135301D01",
            "ORDER-M1.4-ROUND-4MM-ZINC-PH0",
        ):
            with self.subTest(valid_identifier=value):
                self.assertTrue(_valid_procurement_identifier(value))
        for value in (
            "NO-DIGIT",
            "ABC 123",
            "TBD-SKU-1",
            "PENDING123",
            "PROVISIONAL-1",
            "UNDECIDED-1",
            "AWAITING-SKU-1",
            "TBD-1",
            "TO-FOLLOW-1",
            "DRAFT-1",
            "TENTATIVE-SKU-1",
            "DEFERRED-1",
            "LATER-1",
        ):
            with self.subTest(invalid_identifier=value):
                self.assertFalse(_valid_procurement_identifier(value))
        for value in ("REV-C", "REV-2026-08", "R2", "V2"):
            with self.subTest(valid_revision=value):
                self.assertTrue(_valid_drawing_revision(value))
        for value in ("C", "revision C", "REV PENDING", "T.B.D."):
            with self.subTest(invalid_revision=value):
                self.assertFalse(_valid_drawing_revision(value))
        self.assertTrue(
            _procurement_object_identity_errors(
                {
                    "parts": {
                        "switch": {
                            "manufacturer": "UNKNOWN SUPPLIER",
                            "mpn": "TBD SKU",
                            "drawing_revision": "TO BE CONFIRMED",
                            "document_id": "PROVISIONAL-1",
                            "sku": "AWAITING-SKU-1",
                        }
                    }
                },
                label="synthetic BOM",
            )
        )
        self.assertEqual(
            _procurement_object_identity_errors(
                {
                    "parts": {
                        "switch": {
                            "manufacturer": "Unknown Industries U-1",
                            "mpn": "TBC-40",
                            "drawing_revision": "REV-C",
                            "document_id": "DOC-123",
                            "sku": "NA-100",
                        }
                    }
                },
                label="synthetic BOM",
            ),
            [],
        )

    def test_physical_identity_placeholder_taxonomy_rejects_reserved_sentinels(self) -> None:
        from tools.verify_kc2_x3_v2 import _contains_identity_placeholder

        sentinels = (
            "PLACEHOLDER",
            "N/A",
            "NA",
            "UNSET",
            "NOT SELECTED",
            "NOT_SELECTED",
            "NOT-SELECTED",
            "TBC",
            "PENDING123",
            "UNKNOWN_SOCKET",
            "TODO",
            "FIXME-part",
            "MPN_PLACEHOLDER",
            "ACME/UNKNOWN_SOCKET",
            "DUMMY",
            "TO BE DECIDED",
            "TO BE DETERMINED",
            "TO_BE_DECIDED",
            "TO-BE-DETERMINED",
            "TBA",
            "NONE",
            "NULL",
            "TEMP",
            "FAKE",
            "PENDING PHYSICAL PART",
            "UNKNOWN SOCKET",
            "TBD PART",
            "TODO PART",
            "FIXME PART",
            "PROVISIONAL FASTENER",
            "DUMMY PART",
            "TO BE DECIDED PART",
            "TO BE DETERMINED FASTENER",
            "TBA_PART",
            "TBA FASTENER",
            "TBC PART",
            "UNKNOWN FASTENER",
            "UNKNOWN PART",
            "TBD ITEM",
            "TBA PART",
            "TBC COMPONENT",
            "NONE-SELECTED",
            "NULL/FASTENER",
            "TEMP 42",
            "FAKE123",
            "ACME UNKNOWN SOCKET",
            "FASTENER TBA",
            "PART TBC",
            "FASTENER UNKNOWN",
            "ITEM TBD",
            "ACME / TBA / PART",
            "M1.4-FASTENER-TBC",
            "N.A.",
            r"N\A",
            "NOT AVAILABLE",
            "NO MPN",
            "TBD.PART",
            "T.B.D.",
            "T-B-D",
            "T/B/D",
            "T_B_D",
            "T B D",
            "T.B.A.",
            "T-B-A",
            "T/B/A",
            "T_B_A",
            "T B A",
            "T.B.C.",
            "T-B-C",
            "T/B/C",
            "T_B_C",
            "T B C",
            "U.N.K.N.O.W.N",
            "U-N-K-N-O-W-N",
            "U/N/K/N/O/W/N",
            "U_N_K_N_O_W_N",
            "U N K N O W N",
            "P.E.N.D.I.N.G",
            "P-E-N-D-I-N-G",
            "P/E/N/D/I/N/G",
            "P_E_N_D_I_N_G",
            "P E N D I N G",
            " pending_physical_procurement_gate ",
        )
        legitimate = (
            "Pendington PX-123",
            "Tbdale Components TD-10",
            "Temporary Works TW-1",
            "Fakewell Components FK-2",
            "Unknown Industries U-1",
            "Nakamura NA-100",
            "TBC Precision TBC-40",
            "KAILH CPG135301D01",
        )
        for value in sentinels:
            with self.subTest(reserved_sentinel=value):
                self.assertTrue(_contains_identity_placeholder(value))
        for value in legitimate:
            with self.subTest(legitimate_identity=value):
                self.assertFalse(_contains_identity_placeholder(value))

    def test_generator_declares_interference_minimized_m1_4_pattern(self) -> None:
        from tools import generate_kc2_pcbs as generator

        self.assertEqual(
            generator.X3_V2_MOUNTING_POINTS,
            {
                "left": [
                    (112.8625, 43.0),
                    (144.1125, 66.25),
                    (38.6125, 111.0),
                    (63.6125, 123.0),
                    (81.1125, 151.75),
                    (137.3625, 153.5),
                    (166.3625, 148.75),
                    (75.0, 134.0),
                ],
                "right": [
                    (97.0625, 43.25),
                    (72.4375, 67.0),
                    (169.9375, 95.25),
                    (194.9375, 98.75),
                    (156.1875, 112.5),
                    (69.9375, 146.25),
                    (97.4375, 152.0),
                    (122.6875, 151.0),
                    (177.5, 118.0),
                ],
            },
        )
        self.assertEqual(generator.X3_V2_MOUNT_HOLE_DIAMETER_MM, 1.6)
        self.assertEqual(generator.X3_V2_MOUNT_HEAD_ENVELOPE_MM, (3.0, 1.2))
        self.assertEqual(
            generator.X3_V2_MOUNT_HEAD_STYLE,
            "non_countersunk_rounded_pan_or_button",
        )
        self.assertEqual(generator.X3_V2_MOUNT_HEAD_XY_RESERVE_MM, 0.25)
        self.assertEqual(generator.X3_V2_MOUNT_DRIVER_DIAMETER_MM, 3.0)
        self.assertEqual(generator.X3_V2_MOUNT_SUPPORT_LAND_DIAMETER_MM, 3.0)
        self.assertEqual(generator.X3_V2_MOUNT_PILOT_ENVELOPE_MM, (1.1, 2.8))
        self.assertEqual(generator.X3_V2_MOUNT_UNDER_HEAD_LENGTH_MM, 4.0)
        self.assertEqual(generator.X3_V2_MOUNT_CLOSED_BOTTOM_MM, 0.7)
        self.assertEqual(generator.X3_V2_MOUNT_REFERENCE_TEXT_SIZE_MM, 0.8)
        self.assertEqual(generator.X3_V2_MOUNT_REFERENCE_STROKE_MM, 0.15)
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
        self.assertIn("`MH1..MH9` on the right", v2_readme)
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
                    8 if side == "left" else 9,
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
                        (0.8, 0.15, 0.0, -1.5),
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
                        "pad_1_marking": "B+",
                        "pad_2_marking": "B-/GND",
                        "nice_nano_equivalence": {
                            "battery_positive": "U1 RAW / NN_B+",
                            "battery_negative": "U1 GND_C / GND",
                            "source": "https://nicekeyboards.com/docs/nice-nano/",
                        },
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
                        "model_role": "nominal_collision_proxy",
                        "exact_purchased_mpn_status": "pending",
                        "controlled_drawing_status": "pending",
                        "imms_12v_bsi_10_equivalence_status": "pending",
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
                    "controller service physical evidence bundle" in blocker
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
            stale_marking = json.loads(json.dumps(manifest))
            stale_marking["controller_service_region"]["battery_termination"][
                "pad_2_marking"
            ] = "B+"
            self.assertTrue(verify_controller_service_model_binding(stale_marking))
            for field in (
                "model_role",
                "exact_purchased_mpn_status",
                "controlled_drawing_status",
                "imms_12v_bsi_10_equivalence_status",
            ):
                with self.subTest(field=field):
                    stale_contract = json.loads(json.dumps(manifest))
                    stale_contract["controller_service_region"]["power"][field] = "approved"
                    self.assertTrue(verify_controller_service_model_binding(stale_contract))
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

        v2_readme = (V2_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("pad 1 `B+`", v2_readme)
        self.assertIn("pad 2 `B-/GND`", v2_readme)
        self.assertIn("https://nicekeyboards.com/docs/nice-nano/", v2_readme)

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
                power = __import__("pcbnew").LoadBoard(str(board_path)).FindFootprintByReference(
                    "SW_PWR1"
                )
                self.assertEqual(
                    [model.m_Filename for model in power.Models()],
                    [
                        "${KIPRJMOD}/../../../../../third_party/kc2.3dshapes/"
                        "SW_IMMS_12V_BSI10_THT.step"
                    ],
                )
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
                ("MH1", 112.8625, 43.0),
                ("MH2", 144.1125, 66.25),
                ("MH3", 38.6125, 111.0),
                ("MH4", 63.6125, 123.0),
                ("MH5", 81.1125, 151.75),
                ("MH6", 137.3625, 153.5),
                ("MH7", 166.3625, 148.75),
                ("MH8", 75.0, 134.0),
            ],
            "right": [
                ("MH1", 97.0625, 43.25),
                ("MH2", 72.4375, 67.0),
                ("MH3", 169.9375, 95.25),
                ("MH4", 194.9375, 98.75),
                ("MH5", 156.1875, 112.5),
                ("MH6", 69.9375, 146.25),
                ("MH7", 97.4375, 152.0),
                ("MH8", 122.6875, 151.0),
                ("MH9", 177.5, 118.0),
            ],
        }
        for side, board_path in (("left", LEFT_BOARD), ("right", RIGHT_BOARD)):
            with self.subTest(side=side):
                report = analyze_v2_board(board_path)
                self.assertEqual(report["mounting_hole_positions_mm"], expected[side])
                self.assertEqual(report["mounting_hole_errors"], [])
                self.assertEqual(report["mounting_hole_silkscreen_errors"], [])
                self.assertEqual(report["mounting_hole_driver_copper_errors"], [])
                self.assertEqual(report["mounting_hole_head_clearance_errors"], [])
                self.assertGreaterEqual(
                    report["mounting_hole_clearances"][
                        "minimum_driver_to_copper_mm"
                    ],
                    0.85,
                )
                self.assertGreaterEqual(
                    report["mounting_hole_clearances"][
                        "minimum_head_to_installed_body_mm"
                    ],
                    1.20,
                )
                self.assertGreaterEqual(
                    report["mounting_hole_clearances"][
                        "minimum_head_to_exposed_copper_fillet_mm"
                    ],
                    0.85,
                )
                self.assertGreaterEqual(
                    report["mounting_hole_clearances"]["minimum_head_to_edge_cuts_mm"],
                    2.10,
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
            (
                "thin stroke",
                lambda board: board.FindFootprintByReference("MH1").Reference().SetTextThickness(
                    pcbnew.FromMM(0.1)
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

    def test_mounting_head_gate_rejects_missing_xy_reserve_to_body_fillet_route_and_edge(self) -> None:
        import pcbnew

        def add_near_via(board: pcbnew.BOARD) -> None:
            center = board.FindFootprintByReference("MH1").GetPosition()
            via = pcbnew.PCB_VIA(board)
            via.SetPosition(center + pcbnew.VECTOR2I(pcbnew.FromMM(1.9), 0))
            via.SetWidth(pcbnew.FromMM(0.6))
            via.SetDrill(pcbnew.FromMM(0.3))
            via.SetNetCode(board.FindNet("L_COL5").GetNetCode())
            board.Add(via)

        def move_switch_into_head_reserve(board: pcbnew.BOARD) -> None:
            center = board.FindFootprintByReference("MH1").GetPosition()
            board.FindFootprintByReference("SW1").SetPosition(
                center + pcbnew.VECTOR2I(pcbnew.FromMM(9.4), 0)
            )

        def move_diode_pad_into_fillet_reserve(board: pcbnew.BOARD) -> None:
            center = board.FindFootprintByReference("MH1").GetPosition()
            diode = board.FindFootprintByReference("D1")
            pad = next(pad for pad in diode.Pads() if pad.GetNumber() == "1")
            target = center + pcbnew.VECTOR2I(pcbnew.FromMM(2.8), 0)
            diode.Move(target - pad.GetPosition())

        def move_hole_near_edge(board: pcbnew.BOARD) -> None:
            hole = board.FindFootprintByReference("MH1")
            hole.SetPosition(
                pcbnew.VECTOR2I(pcbnew.FromMM(142.6125), pcbnew.FromMM(40.9))
            )

        for label, mutate in (
            ("installed switch body", move_switch_into_head_reserve),
            ("exposed diode pad fillet", move_diode_pad_into_fillet_reserve),
            ("routed via copper", add_near_via),
            ("PCB edge", move_hole_near_edge),
        ):
            with self.subTest(label=label), TemporaryDirectory(dir=ROOT) as temporary:
                copy = Path(temporary) / LEFT_BOARD.name
                board = pcbnew.LoadBoard(str(LEFT_BOARD))
                mutate(board)
                pcbnew.SaveBoard(str(copy), board)
                report = analyze_v2_board(copy)
                self.assertTrue(report["mounting_hole_head_clearance_errors"])

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
                "switch bottom courtyard",
                lambda board: next(
                    item
                    for item in board.FindFootprintByReference("SW1").GraphicalItems()
                    if item.GetLayer() == pcbnew.B_CrtYd
                ).Move(pcbnew.VECTOR2I(pcbnew.FromMM(0.1), 0)),
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
                "controller RAW wrong net",
                lambda board: next(
                    pad
                    for pad in board.FindFootprintByReference("U1").Pads()
                    if pad.GetNumber() == "RAW"
                ).SetNet(board.FindNet("GND")),
                "controller_contract_errors",
            ),
            (
                "controller GND_C wrong net",
                lambda board: next(
                    pad
                    for pad in board.FindFootprintByReference("U1").Pads()
                    if pad.GetNumber() == "GND_C"
                ).SetNet(board.FindNet("BAT+")),
                "controller_contract_errors",
            ),
            (
                "controller RST netless",
                lambda board: next(
                    pad
                    for pad in board.FindFootprintByReference("U1").Pads()
                    if pad.GetNumber() == "RST"
                ).SetNetCode(0),
                "controller_contract_errors",
            ),
            (
                "power switch STEP model",
                lambda board: board.FindFootprintByReference("SW_PWR1").Models().clear(),
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

    def test_battery_termination_gate_rejects_swapped_missing_marks_and_wrong_nets(self) -> None:
        import pcbnew

        def swap_markings(board: pcbnew.BOARD) -> None:
            footprint = board.FindFootprintByReference("J_BAT1")
            markings = {
                item.GetText(): item
                for item in footprint.GraphicalItems()
                if isinstance(item, pcbnew.PCB_TEXT)
                and item.GetText() in {"B+", "B-/GND"}
            }
            markings["B+"].SetText("B-/GND")
            markings["B-/GND"].SetText("B+")

        def remove_negative_marking(board: pcbnew.BOARD) -> None:
            footprint = board.FindFootprintByReference("J_BAT1")
            next(
                item
                for item in footprint.GraphicalItems()
                if isinstance(item, pcbnew.PCB_TEXT)
                and item.GetText() == "B-/GND"
            ).SetText("")

        def swap_pad_nets(board: pcbnew.BOARD) -> None:
            footprint = board.FindFootprintByReference("J_BAT1")
            pads = {pad.GetNumber(): pad for pad in footprint.Pads()}
            pads["1"].SetNet(board.FindNet("GND"))
            pads["2"].SetNet(board.FindNet("BAT+"))

        for label, mutate in (
            ("swapped markings", swap_markings),
            ("missing negative marking", remove_negative_marking),
            ("swapped pad nets", swap_pad_nets),
        ):
            with self.subTest(label=label), TemporaryDirectory(dir=ROOT) as temporary:
                copy = Path(temporary) / LEFT_BOARD.name
                board = pcbnew.LoadBoard(str(LEFT_BOARD))
                mutate(board)
                pcbnew.SaveBoard(str(copy), board)
                report = analyze_v2_board(copy)
                self.assertTrue(report["controller_contract_errors"])

    def test_current_projects_and_route_sources_bind_minimum_clearance_and_hashes(self) -> None:
        from tools import generate_kc2_pcbs as generator
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
            expected_positions = {
                f"MH{index}": position
                for index, position in enumerate(
                    generator.X3_V2_MOUNTING_POINTS[side], start=1
                )
            }
            self.assertEqual(
                route_reports[side]["dsn_mounting_hole_positions_mm"],
                expected_positions,
            )
            self.assertEqual(
                route_reports[side]["ses_mounting_hole_positions_mm"],
                expected_positions,
            )

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
        if (ROOT / ".git").exists():
            relative = MANIFEST.relative_to(ROOT).as_posix()
            staged = subprocess.run(
                ["git", "show", f":{relative}"],
                cwd=ROOT,
                check=True,
                stdout=subprocess.PIPE,
            ).stdout
            self.assertNotIn(b"\r\n", staged)
            self.assertEqual(sha256_file(MANIFEST), sha256_bytes(staged))
        self.assertEqual(report["generated"], "2026-08-30")
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
                "references": "MH1..MH8 left; MH1..MH9 right",
                "counts": {"left": 8, "right": 9, "total": 17},
                "positions_mm": {
                    "left": [
                        {"ref": "MH1", "x": 112.8625, "y": 43.0},
                        {"ref": "MH2", "x": 144.1125, "y": 66.25},
                        {"ref": "MH3", "x": 38.6125, "y": 111.0},
                        {"ref": "MH4", "x": 63.6125, "y": 123.0},
                        {"ref": "MH5", "x": 81.1125, "y": 151.75},
                        {"ref": "MH6", "x": 137.3625, "y": 153.5},
                        {"ref": "MH7", "x": 166.3625, "y": 148.75},
                        {"ref": "MH8", "x": 75.0, "y": 134.0},
                    ],
                    "right": [
                        {"ref": "MH1", "x": 97.0625, "y": 43.25},
                        {"ref": "MH2", "x": 72.4375, "y": 67.0},
                        {"ref": "MH3", "x": 169.9375, "y": 95.25},
                        {"ref": "MH4", "x": 194.9375, "y": 98.75},
                        {"ref": "MH5", "x": 156.1875, "y": 112.5},
                        {"ref": "MH6", "x": 69.9375, "y": 146.25},
                        {"ref": "MH7", "x": 97.4375, "y": 152.0},
                        {"ref": "MH8", "x": 122.6875, "y": 151.0},
                        {"ref": "MH9", "x": 177.5, "y": 118.0},
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
                    "stroke_mm": 0.15,
                    "relative_position_mm": {"x": 0.0, "y": -1.5},
                },
                "screw_head_style": "non_countersunk_rounded_pan_or_button",
                "screw_head_envelope_mm": {"diameter": 3.0, "height": 1.2},
                "screw_head_xy_reserve_mm": 0.25,
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
                "model_role": "nominal_collision_proxy",
                "exact_purchased_mpn_status": "pending",
                "controlled_drawing_status": "pending",
                "imms_12v_bsi_10_equivalence_status": "pending",
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
            report["deep_sea_switch_identity"],
            {
                "family": "Kailh Deep Sea low-profile / PG1353-family",
                "exact_mpn_status": "pending",
                "controlled_drawing_revision_status": "pending",
                "order_ready": False,
            },
        )
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
                    "session_source_dsn_sha256": "00e347ed6a197a3016f73b4ddc1cd72d4d5b22ff916d253a20ef1fc11094e30c",
                    "ses": "hardware/kicad/draft/x3-v2/autoroute/kc2_left-x3-v2-70-es1b-controller-r3.ses",
                    "ses_role": "reviewed_matrix_import_plus_exact_edge_cleanup_and_power_reset_service_routing",
                    "dsn_sha256": "00e347ed6a197a3016f73b4ddc1cd72d4d5b22ff916d253a20ef1fc11094e30c",
                    "ses_sha256": "4c97f1040bcbfbda39bc1e445edb81863d030629190be1ee50f6b3ab50441832",
                    "dsn_default_clearance_internal_units": 300,
                    "dsn_clearances_internal_units": {"global": 300, "kicad_default": 300},
                    "final_track_via_count": 590,
                    "route_digest_sha256": "94c49ca2749d83cd05969e46b2afb6b610c2067ce6a2acad84790a19e081be18",
                },
                "right": {
                    "dsn": "hardware/kicad/draft/x3-v2/autoroute/kc2_right-x3-v2-70-es1b-controller-r3.dsn",
                    "dsn_role": "current_mh_compact_controller_trackless_routing_input",
                    "dsn_mounting_hole_count": 9,
                    "session_source_dsn": "hardware/kicad/draft/x3-v2/autoroute/kc2_right-x3-v2-70-es1b-controller-r3.dsn",
                    "session_source_dsn_sha256": "cdb19dfbbfc3c9129df64aaa9f899142fbaf15de3a4775ea4826dbdd8519c425",
                    "ses": "hardware/kicad/draft/x3-v2/autoroute/kc2_right-x3-v2-70-es1b-controller-r3.ses",
                    "ses_role": "reviewed_matrix_import_plus_exact_edge_cleanup_and_power_reset_service_routing",
                    "dsn_sha256": "cdb19dfbbfc3c9129df64aaa9f899142fbaf15de3a4775ea4826dbdd8519c425",
                    "ses_sha256": "b5bd3f7f622af8bb50b1292fb05d08b6d3b7a6ce5f893c0d20ef51d814a48717",
                    "dsn_default_clearance_internal_units": 300,
                    "dsn_clearances_internal_units": {"global": 300, "kicad_default": 300},
                    "final_track_via_count": 764,
                    "route_digest_sha256": "b54d29e27f1f319863ec5808b31188420ad4c47fa001d21ece98db80044c6946",
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
        for side, expected_count in (("left", 8), ("right", 9)):
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

        scalar_only_blockers = controller_service_order_readiness_blockers(
            manifest,
            housing,
        )

        for expected in (
            "CON-ARCH-007: controller service physical evidence bundle",
            "CON-ARCH-004: physical scan evidence bundle",
            "CON-ARCH-006: housing physical evidence bundle",
            "REL-ARCH-001: power/RF evidence bundle",
        ):
            self.assertTrue(
                any(expected in blocker for blocker in scalar_only_blockers),
                scalar_only_blockers,
            )
        self.assertEqual(
            release_candidate_exit_code(
                {
                    "errors": [],
                    "order_readiness_blockers": scalar_only_blockers,
                }
            ),
            2,
        )

        minimal_housing = {
            "order_ready": True,
            "retention": {"physical_registration_status": "passed"},
            "physical_deflection_test": {"status": "passed"},
            "parameters": housing["parameters"],
        }
        minimal_blockers = controller_service_order_readiness_blockers(
            manifest,
            minimal_housing,
        )
        self.assertTrue(
            any(
                "CON-ARCH-006: housing physical evidence bundle" in blocker
                for blocker in minimal_blockers
            ),
            minimal_blockers,
        )
        conservative_manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        conservative_housing = json.loads(
            (ROOT / "hardware/case/draft/x3-v2/kc2_x3_v2_housing_manifest.json")
            .read_text(encoding="utf-8")
        )
        conservative_blockers = controller_service_order_readiness_blockers(
            conservative_manifest,
            conservative_housing,
        )
        self.assertFalse(
            any("must remain" in blocker for blocker in conservative_blockers),
            conservative_blockers,
        )
        self.assertEqual(
            release_candidate_exit_code(
                {"errors": [], "order_readiness_blockers": conservative_blockers}
            ),
            2,
        )

    def test_generation_manifest_requirement_and_pending_part_identity_contracts_fail_closed(self) -> None:
        from tools.verify_kc2_x3_v2 import verify_v2_part_identity_contract

        manifest = analyze_v2_manifest(MANIFEST)
        self.assertEqual(verify_v2_part_identity_contract(manifest), [])
        mutations = (
            (
                "missing housing requirement",
                lambda value: value.update(
                    requirement_ids=["CON-ARCH-004", "CON-ARCH-007", "REL-ARCH-001"]
                ),
            ),
            (
                "invented Deep Sea MPN",
                lambda value: value["deep_sea_switch_identity"].update(
                    exact_mpn_status="confirmed",
                    exact_mpn="UNVERIFIED-MPN",
                ),
            ),
            (
                "Deep Sea drawing claimed complete",
                lambda value: value["deep_sea_switch_identity"].update(
                    controlled_drawing_revision_status="confirmed"
                ),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                changed = json.loads(json.dumps(manifest))
                mutate(changed)
                self.assertTrue(verify_v2_part_identity_contract(changed))

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

    def test_physical_evidence_manifest_binds_files_hashes_and_thresholds(self) -> None:
        from tools.verify_kc2_x3_v2 import (
            POSITIVE_ORDER_ARTIFACT_MODULES,
            _housing_head_adjacency_contracts,
            _positive_package_identity_errors,
            controller_service_order_readiness_blockers,
            verify_physical_evidence_manifest,
        )

        self.assertEqual(
            set(POSITIVE_ORDER_ARTIFACT_MODULES),
            {
                "fabrication",
                "mechanical",
                "render",
                "firmware",
                "coupon",
                "outline",
            },
        )

        suite_patch = patch(
            "tools.verify_kc2_x3_v2._verify_positive_order_artifact_suite",
            return_value=[],
        )
        suite_mock = suite_patch.start()
        self.addCleanup(suite_patch.stop)
        index_patch = patch(
            "tools.verify_kc2_x3_v2._git_index_artifact_errors",
            return_value=[],
        )
        index_patch.start()
        self.addCleanup(index_patch.stop)
        with TemporaryDirectory(dir=ROOT) as temporary:
            temp_root = Path(temporary)

            def file_record(path: Path, kind: str) -> dict[str, object]:
                return {
                    "path": path.relative_to(ROOT).as_posix(),
                    "sha256": sha256_file(path),
                    "size_bytes": path.stat().st_size,
                    "kind": kind,
                }

            def write_document(name: str, kind: str) -> dict[str, object]:
                path = temp_root / name
                path.write_text(f"{kind} controlled test document\n", encoding="utf-8", newline="\n")
                return {
                    **file_record(path, kind),
                    "document_id": f"{kind.upper()}-DOC-1",
                }

            def write_json_document(
                name: str,
                kind: str,
                payload: dict[str, object],
            ) -> dict[str, object]:
                path = temp_root / name
                path.write_text(
                    json.dumps(payload, indent=2) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
                return {
                    **file_record(path, kind),
                    "document_id": f"{kind.upper()}-DOC-1",
                }

            source_paths = {
                "left_board": LEFT_BOARD,
                "right_board": RIGHT_BOARD,
                "generation_manifest": MANIFEST,
                "housing_manifest": ROOT
                / "hardware/case/draft/x3-v2/kc2_x3_v2_housing_manifest.json",
                "fabrication_manifest": V2_ROOT
                / "fabrication/kc2_x3_v2_fabrication_manifest.json",
                "mechanical_manifest": V2_ROOT
                / "mechanical/kc2_x3_v2_mechanical_manifest.json",
                "render_manifest": V2_ROOT
                / "renders/kc2_x3_v2_render_manifest.json",
                "outline_report": V2_ROOT
                / "mechanical/kc2_x3_v2_outline_report.json",
                "firmware_build_evidence": ROOT
                / "firmware/kc2_zmk/boards/shields/kc2_x3_v2/kc2_x3_v2_build_evidence.json",
            }
            source_bindings = {
                name: file_record(path, "release-source")
                for name, path in source_paths.items()
            }
            source_digests = {
                name: record["sha256"] for name, record in source_bindings.items()
            }

            arbitrary_path = temp_root / "arbitrary.json"
            arbitrary_path.write_text("{}\n", encoding="utf-8", newline="\n")
            arbitrary = file_record(arbitrary_path, "synthetic-test-fixture")
            arbitrary_measured = {
                **arbitrary,
                "measured_at": "2026-08-29T12:00:00+09:00",
                "equipment_id": "UNVERIFIED",
                "calibration_evidence": "not_applicable_nonmeasurement",
            }
            scalar_only_evidence = {
                "schema": "kc2-x3-v2-physical-evidence-v1",
                "requirement_ids": [
                    "CON-ARCH-004",
                    "CON-ARCH-006",
                    "CON-ARCH-007",
                    "REL-ARCH-001",
                ],
                "variant": "x3-v2",
                "status": "passed",
                "order_ready": True,
                "source_bindings": source_bindings,
                "bundles": {
                    "controller_service": {
                        "status": "passed",
                        "artifacts": [dict(arbitrary_measured)],
                        "metrics": {
                            "battery_manufacturer": "TEST",
                            "battery_mpn": "TEST-PACK",
                            "battery_lot": "LOT-1",
                            "protection_status": "protected",
                            "power_switch_manufacturer": "TEST",
                            "power_switch_mpn": "TEST-SWITCH",
                            "reset_switch_mpn": "TEST-RESET",
                            "lead_drawing_sha256": "1" * 64,
                            "maximum_swollen_thickness_mm": 3.2,
                            "minimum_stack_clearance_mm": 0.1,
                            "lead_pull_pass": True,
                            "service_pass": True,
                        },
                    },
                    "physical_scan": {
                        "status": "passed",
                        "artifacts": [dict(arbitrary_measured)],
                        "metrics": {
                            "supply_volts": [3.0, 3.3],
                            "patterns": ["maximum-same-row", "maximum-same-column"],
                            "sample_count_per_pattern": 1,
                            "fault_count": 0,
                        },
                    },
                    "housing_fastener_deflection": {
                        "status": "passed",
                        "artifacts": [dict(arbitrary_measured)],
                        "metrics": {
                            "install_remove_cycles": 10,
                            "torque_ratio": 2.0,
                            "maximum_displacement_mm": 0.30,
                            "rocking": False,
                            "loosening": False,
                            "permanent_deformation": False,
                            "support_disengagement": False,
                        },
                    },
                    "power_rf": {
                        "status": "passed",
                        "artifacts": [dict(arbitrary_measured)],
                        "metrics": {
                            "cold_cycles_per_voltage_and_direction": 20,
                            "brownout_count": 0,
                            "rssi_samples_per_state": 30,
                            "reports_per_state": 10000,
                            "packet_loss_ratio": 0.01,
                            "median_rssi_degradation_db": 3.0,
                            "disconnect_count": 0,
                            "reconnect_count": 0,
                        },
                    },
                },
            }
            arbitrary_reused_file_errors = verify_physical_evidence_manifest(
                scalar_only_evidence,
                source_paths,
            )
            self.assertTrue(
                all(arbitrary_reused_file_errors.values()),
                "CON-ARCH-007 AC-11 / REL-ARCH-001 AC-6 must reject one arbitrary "
                "file reused for every bundle with calibration marked not applicable and "
                "self-asserted aggregate metrics",
            )

            controller_documents = {
                kind: write_document(f"controller-{kind}.txt", kind)
                for kind in (
                    "battery_datasheet",
                    "battery_lead_drawing",
                    "battery_protection_declaration",
                    "controller_datasheet",
                    "controller_socket_drawing",
                    "choc_switch_drawing",
                    "choc_socket_drawing",
                    "mx_switch_drawing",
                    "power_switch_drawing",
                    "reset_switch_drawing",
                )
            }
            controller_data = {
                "parts": {
                    "battery": {
                        "manufacturer": "TEST-BATTERY-MAKER",
                        "mpn": "PACK-301230-PROTECTED",
                        "lot": "LOT-1",
                        "protection_status": "integral-protection-confirmed",
                        "maximum_swollen_thickness_mm": 3.2,
                        "lead_conductor_diameter_mm": 0.5,
                        "required_hole_clearance_mm": 0.1,
                    },
                    "controller": {
                        "manufacturer": "nice keyboards",
                        "mpn": "nice!nano-v2",
                        "hardware_revision": "v2",
                    },
                    "controller_socket": {
                        "manufacturer": "Mill-Max",
                        "mpn": "315-43-112-41-003000",
                        "drawing_revision": "REV-2026-08",
                    },
                    "choc_switch": {
                        "manufacturer": "KAILH",
                        "mpn": "CPG135301D01",
                        "drawing_revision": "REV-2026-08",
                    },
                    "choc_socket": {
                        "manufacturer": "KAILH",
                        "mpn": "CPG135001S30",
                        "drawing_revision": "REV-2026-08",
                    },
                    "mx_switch": {
                        "manufacturer": "CHERRY",
                        "mpn": "MX2A-L1NN",
                        "drawing_revision": "REV-2026-08",
                    },
                    "power_switch": {
                        "manufacturer": "TEST-SWITCH-MAKER",
                        "mpn": "IMMS-EXACT-MPN-1",
                        "drawing_revision": "REV-A",
                    },
                    "reset_switch": {
                        "manufacturer": "TEST-RESET-MAKER",
                        "mpn": "NW3-A06-B3",
                        "drawing_revision": "REV-B",
                    },
                },
                "documents": controller_documents,
                "stack_records": [
                    {
                        "half": half,
                        "fully_seated_gap_mm": 5.0,
                        "insulation_thickness_mm": 0.2,
                        "retainer_thickness_mm": 0.5,
                        "socket_pin_protrusion_mm": 0.2,
                        "solder_protrusion_mm": 0.2,
                        "assembly_tolerance_mm": 0.2,
                        "minimum_clearance_mm": 0.5,
                        "controller_install_remove_pass": True,
                        "pouch_compressed": False,
                        "sharp_contact": False,
                    }
                    for half in ("left", "right")
                ],
                "pull_records": [
                    {
                        "half": half,
                        "rated_load_n": 5.0,
                        "rated_duration_s": 10.0,
                        "applied_load_n": 5.0,
                        "applied_duration_s": 10.0,
                        "lead_movement_mm": 0.0,
                        "force_transfer_to_pouch_tab": False,
                    }
                    for half in ("left", "right")
                ],
                "service_records": [
                    {
                        "half": half,
                        "reset_bootloader_cycles": 10,
                        "continuity_on_max_ohm": 1.0,
                        "continuity_off_min_ohm": 1000000.0,
                        "power_on_resistance_ohm": 0.2,
                        "power_off_resistance_ohm": 10000000.0,
                        "reset_pressed_resistance_ohm": 0.2,
                        "reset_released_resistance_ohm": 10000000.0,
                        "power_actuator_travel_mm": 1.6,
                        "minimum_fingertip_access_clearance_mm": 1.0,
                        "power_full_travel_contact_with_reset": False,
                        "power_full_travel_contact_with_controller": False,
                        "power_full_travel_contact_with_keycap": False,
                        "reset_probe_diameter_mm": 1.0,
                        "reset_probe_access_pass": True,
                        "service_pass": True,
                        "controller_contact": False,
                        "adjacent_key_actuation": False,
                        "pad_peel": False,
                        "visible_pcb_flex": False,
                    }
                    for half in ("left", "right")
                ],
            }
            controller_metrics = {
                "battery_manufacturer": "TEST-BATTERY-MAKER",
                "battery_mpn": "PACK-301230-PROTECTED",
                "battery_lot": "LOT-1",
                "protection_status": "integral-protection-confirmed",
                "controller_manufacturer": "nice keyboards",
                "controller_mpn": "nice!nano-v2",
                "controller_hardware_revision": "v2",
                "controller_socket_manufacturer": "Mill-Max",
                "controller_socket_mpn": "315-43-112-41-003000",
                "controller_socket_drawing_revision": "REV-2026-08",
                "choc_switch_manufacturer": "KAILH",
                "choc_switch_mpn": "CPG135301D01",
                "choc_switch_drawing_revision": "REV-2026-08",
                "choc_socket_manufacturer": "KAILH",
                "choc_socket_mpn": "CPG135001S30",
                "choc_socket_drawing_revision": "REV-2026-08",
                "mx_switch_manufacturer": "CHERRY",
                "mx_switch_mpn": "MX2A-L1NN",
                "mx_switch_drawing_revision": "REV-2026-08",
                "power_switch_manufacturer": "TEST-SWITCH-MAKER",
                "power_switch_mpn": "IMMS-EXACT-MPN-1",
                "power_switch_drawing_revision": "REV-A",
                "reset_switch_manufacturer": "TEST-RESET-MAKER",
                "reset_switch_mpn": "NW3-A06-B3",
                "reset_switch_drawing_revision": "REV-B",
                "lead_drawing_sha256": controller_documents["battery_lead_drawing"]["sha256"],
                "protection_declaration_sha256": controller_documents[
                    "battery_protection_declaration"
                ]["sha256"],
                "controller_datasheet_sha256": controller_documents[
                    "controller_datasheet"
                ]["sha256"],
                "controller_socket_drawing_sha256": controller_documents[
                    "controller_socket_drawing"
                ]["sha256"],
                "choc_switch_drawing_sha256": controller_documents[
                    "choc_switch_drawing"
                ]["sha256"],
                "choc_socket_drawing_sha256": controller_documents[
                    "choc_socket_drawing"
                ]["sha256"],
                "mx_switch_drawing_sha256": controller_documents[
                    "mx_switch_drawing"
                ]["sha256"],
                "j_bat_drill_mm": 0.9,
                "lead_conductor_diameter_mm": 0.5,
                "lead_to_j_bat_diametral_clearance_mm": 0.4,
                "maximum_swollen_thickness_mm": 3.2,
                "minimum_stack_clearance_mm": 0.5,
                "lead_pull_pass": True,
                "service_pass": True,
            }

            scan_records = [
                {
                    "half": half,
                    "supply_voltage_v": voltage,
                    "pattern": pattern,
                    "assembly_mode": mode,
                    "sample_id": f"{half}-{voltage}-{pattern}-{mode}",
                    "fault_count": 0,
                }
                for half in ("left", "right")
                for voltage in (3.0, 3.3)
                for pattern in ("maximum-same-row", "maximum-same-column")
                for mode in ("choc_v2", "mx")
            ]
            switch_fit_records = [
                {
                    "half": half,
                    "assembly_mode": mode,
                    "orientation": "left_rotated" if half == "left" else "right_mirrored",
                    "switch_mpn": (
                        controller_data["parts"]["choc_switch"]["mpn"]
                        if mode == "choc_v2"
                        else controller_data["parts"]["mx_switch"]["mpn"]
                    ),
                    "socket_mpn": (
                        controller_data["parts"]["choc_socket"]["mpn"]
                        if mode == "choc_v2"
                        else "not_populated"
                    ),
                    "bottom_socket_fit_pass": mode == "choc_v2",
                    "mx_five_pin_fit_pass": mode == "mx",
                    "minimum_joint_clearance_mm": 0.2,
                    "minimum_housing_clearance_mm": 0.2,
                }
                for half in ("left", "right")
                for mode in ("choc_v2", "mx")
            ]
            keycap_fit_records = [
                {
                    "half": half,
                    "assembly_mode": mode,
                    "width_u": width,
                    "keycap_manufacturer": "TEST-KEYCAP-MAKER",
                    "keycap_mpn": f"{mode.upper()}-{width}U-TEST-CAP",
                    "is_3d_printed": mode == "choc_v2" and width == 1.5,
                    "fit_pass": True,
                    "minimum_spacing_mm": 1.8,
                }
                for half in ("left", "right")
                for mode in ("choc_v2", "mx")
                for width in (1.0, 1.25, 1.5, 1.75)
            ]
            keycap_identity_map = {
                f"{record['assembly_mode']}:{record['width_u']:.2f}": {
                    "assembly_mode": record["assembly_mode"],
                    "width_u": record["width_u"],
                    "manufacturer": record["keycap_manufacturer"],
                    "mpn": record["keycap_mpn"],
                    "is_3d_printed": record["is_3d_printed"],
                }
                for record in keycap_fit_records
            }
            diode_records = [
                {
                    "half": half,
                    "manufacturer": "Jingdao",
                    "mpn": "ES1B",
                    "pad1_cathode_polarity_pass": True,
                    "hand_solder_access_pass": True,
                    "minimum_joint_clearance_mm": 0.2,
                    "minimum_housing_clearance_mm": 0.2,
                }
                for half in ("left", "right")
            ]
            scan_data = {
                "coupon_id": "COUPON-LOT-1",
                "records": scan_records,
                "switch_fit_records": switch_fit_records,
                "keycap_fit_records": keycap_fit_records,
                "diode_records": diode_records,
            }
            scan_metrics = {
                "supply_volts": [3.0, 3.3],
                "patterns": ["maximum-same-row", "maximum-same-column"],
                "assembly_modes": ["choc_v2", "mx"],
                "sample_count_per_condition": 1,
                "fault_count": 0,
                "switch_fit_condition_count": 4,
                "keycap_widths": [1.0, 1.25, 1.5, 1.75],
                "keycap_fit_condition_count": 16,
                "three_d_keycap_record_count": 2,
                "es1b_half_count": 2,
            }

            fastener_identity = {
                "manufacturer": "TEST-FASTENER-MAKER",
                "mpn": "M1.4-ROUND-EXACT",
                "order_code": "ORDER-M1.4-ROUND-4MM-ZINC-PH0",
                "drawing_revision": "REV-C",
                "head_style": "rounded_pan_or_button",
                "nominal_thread_diameter_mm": 1.4,
                "thread_classification": "direct_plastic_thread_forming",
                "thread_form": "thread_forming_30_degree_flank",
                "thread_pitch_mm": 0.4,
                "thread_flank_angle_degrees": 30.0,
                "thread_major_diameter_mm": 1.4,
                "thread_minor_diameter_mm": 1.0,
                "material": "steel",
                "finish": "zinc",
                "drive_recess": "PH0",
                "driver_manufacturer": "TEST-DRIVER-MAKER",
                "driver_mpn": "PH0-3MM-SWEEP",
                "minimum_under_head_length_mm": 3.9,
                "maximum_under_head_length_mm": 4.1,
                "minimum_head_diameter_mm": 2.8,
                "maximum_head_diameter_mm": 3.0,
                "minimum_head_height_mm": 1.0,
                "maximum_head_height_mm": 1.2,
                "maximum_finished_pcb_hole_diameter_mm": 1.7,
                "minimum_radial_bearing_width_mm": 0.55,
                "maximum_driver_shaft_diameter_mm": 2.8,
                "maximum_driver_runout_mm": 0.1,
                "maximum_driver_sweep_mm": 3.0,
            }
            controlled_fastener_fields = (
                "manufacturer",
                "mpn",
                "order_code",
                "drawing_revision",
                "head_style",
                "nominal_thread_diameter_mm",
                "thread_classification",
                "thread_form",
                "thread_pitch_mm",
                "thread_flank_angle_degrees",
                "thread_major_diameter_mm",
                "thread_minor_diameter_mm",
                "material",
                "finish",
                "drive_recess",
                "minimum_under_head_length_mm",
                "maximum_under_head_length_mm",
                "minimum_head_diameter_mm",
                "maximum_head_diameter_mm",
                "minimum_head_height_mm",
                "maximum_head_height_mm",
            )
            housing_documents = {
                "driver_drawing": write_document(
                    "housing-driver_drawing.txt", "driver_drawing"
                ),
                "fastener_drawing": write_json_document(
                    "housing-fastener-drawing.json",
                    "fastener_drawing",
                    {
                        "schema": "kc2-x3-v2-fastener-drawing-v1",
                        **{
                            field: fastener_identity[field]
                            for field in controlled_fastener_fields
                        },
                    },
                ),
            }
            housing_specimen_id = "HOUSING-STRUCTURAL-SPECIMEN-1"
            production_lot_id = "HOUSING-PRINT-LOT-1"
            production_print = {
                "production_process": "FFF",
                "printer_manufacturer": "TEST-PRINTER-MAKER",
                "printer_model": "TEST-PRINTER-EXACT",
                "specimen_coupon_id": housing_specimen_id,
                "production_lot_id": production_lot_id,
                "material_manufacturer": "TEST-FILAMENT-MAKER",
                "material_product": "PLA+ STRUCTURAL",
                "material_mpn": "PLA-PLUS-BLACK-175",
                "material_lot": "FILAMENT-LOT-1",
                "nozzle_diameter_mm": 0.4,
                "layer_height_mm": 0.2,
                "print_orientation": "desk_contact_face_down",
                "slicer_name": "TEST-SLICER",
                "slicer_version": "1.0.0",
                "wall_perimeter_count": 4,
                "infill_pattern": "gyroid",
                "infill_density_percent": 40.0,
                "extrusion_width_mm": 0.45,
                "flow_percent": 100.0,
                "top_solid_layers": 5,
                "bottom_solid_layers": 5,
                "nozzle_temperature_c": 215.0,
                "bed_temperature_c": 60.0,
                "fan_percent": 100.0,
                "print_speed_mm_s": 50.0,
                "travel_speed_mm_s": 150.0,
                "print_acceleration_mm_s2": 1000.0,
                "travel_acceleration_mm_s2": 1500.0,
            }
            slicer_profile = {
                "schema": "kc2-x3-v2-slicer-profile-v1",
                **production_print,
            }
            housing_documents["slicer_profile"] = write_json_document(
                "housing-slicer-profile.json",
                "slicer_profile",
                slicer_profile,
            )
            production_print["slicer_profile_sha256"] = housing_documents[
                "slicer_profile"
            ]["sha256"]
            housing_documents["structural_specimen_trace"] = write_json_document(
                "housing-structural-specimen-trace.json",
                "structural_specimen_trace",
                {
                    "schema": "kc2-x3-v2-structural-specimen-trace-v1",
                    "production_lot_id": production_lot_id,
                    "specimen_coupon_id": housing_specimen_id,
                    "slicer_profile_sha256": production_print[
                        "slicer_profile_sha256"
                    ],
                },
            )
            assembly_identity = {
                "supported_modes": ["choc_v2", "mx"],
                "choc_switch_manufacturer": "KAILH",
                "choc_switch_mpn": "CPG135301D01",
                "mx_switch_manufacturer": "CHERRY",
                "mx_switch_mpn": "MX2A-L1NN",
                "keycap_identities": keycap_identity_map,
            }
            head_adjacency_contracts, head_adjacency_errors = (
                _housing_head_adjacency_contracts(source_paths)
            )
            self.assertEqual(head_adjacency_errors, [])
            self.assertEqual(len(head_adjacency_contracts), 16)
            head_adjacency_counts = Counter(
                (record["half"], record["mounting_hole_reference"])
                for record in head_adjacency_contracts.values()
            )
            self.assertEqual(
                sum(count > 1 for count in head_adjacency_counts.values()),
                2,
            )
            housing_data = {
                "fastener_identity": fastener_identity,
                "production_print": production_print,
                "assembly_identity": assembly_identity,
                "documents": housing_documents,
                "fastener_records": [
                    {
                        "half": half,
                        "production_lot_id": production_lot_id,
                        "specimen_coupon_id": housing_specimen_id,
                        "install_remove_cycles": 10,
                        "actual_under_head_length_mm": 4.0,
                        "printed_pilot_diameter_mm": 1.1,
                        "actual_pcb_thickness_mm": 1.6,
                        "installed_penetration_mm": 2.4,
                        "measured_blind_pilot_depth_mm": 2.8,
                        "measured_closed_bottom_thickness_mm": 0.7,
                        "measured_available_plastic_depth_mm": 3.5,
                        "tip_clearance_mm": 0.4,
                        "tapping_torque_n_m": 0.03,
                        "selected_installation_torque_n_m": 0.04,
                        "stripping_torque_n_m": 0.09,
                        "measured_driver_shaft_diameter_mm": 2.8,
                        "measured_driver_runout_mm": 0.1,
                        "measured_driver_sweep_mm": 3.0,
                        "pull_through_clamp_retention_pass": True,
                        "full_pattern_without_forcing": True,
                        "keycaps_off_switches_installed_access": True,
                        "cracking": False,
                        "spin": False,
                        "pull_out": False,
                        "loosening": False,
                    }
                    for half in ("left", "right")
                ],
                "assembly_fit_records": [
                    {
                        "half": half,
                        "production_lot_id": production_lot_id,
                        "specimen_coupon_id": housing_specimen_id,
                        "assembly_mode": keycap["assembly_mode"],
                        "width_u": keycap["width_u"],
                        "switch_manufacturer": assembly_identity[
                            "choc_switch_manufacturer"
                            if keycap["assembly_mode"] == "choc_v2"
                            else "mx_switch_manufacturer"
                        ],
                        "switch_mpn": assembly_identity[
                            "choc_switch_mpn"
                            if keycap["assembly_mode"] == "choc_v2"
                            else "mx_switch_mpn"
                        ],
                        "keycap_manufacturer": keycap["manufacturer"],
                        "keycap_mpn": keycap["mpn"],
                        "is_3d_printed": keycap["is_3d_printed"],
                        "keycap_skirt_clearance_at_rest_mm": 0.3,
                        "keycap_skirt_clearance_at_full_travel_mm": 0.2,
                    }
                    for half in ("left", "right")
                    for keycap in keycap_identity_map.values()
                ],
                "head_adjacent_fit_records": [
                    {
                        **contract,
                        "production_lot_id": production_lot_id,
                        "specimen_coupon_id": housing_specimen_id,
                        "assembly_mode": mode,
                        "keycap_manufacturer": keycap_identity_map[
                            f"{mode}:{float(contract['width_u']):.2f}"
                        ]["manufacturer"],
                        "keycap_mpn": keycap_identity_map[
                            f"{mode}:{float(contract['width_u']):.2f}"
                        ]["mpn"],
                        "is_3d_printed": keycap_identity_map[
                            f"{mode}:{float(contract['width_u']):.2f}"
                        ]["is_3d_printed"],
                        "keycap_head_clearance_at_rest_mm": 0.3,
                        "keycap_head_clearance_at_full_travel_mm": 0.2,
                    }
                    for contract in head_adjacency_contracts.values()
                    for mode in ("choc_v2", "mx")
                ],
                "deflection_records": [
                    {
                        "half": half,
                        "production_lot_id": production_lot_id,
                        "specimen_coupon_id": housing_specimen_id,
                        "switch_reference": f"SW{index}",
                        "load_n": 2.0,
                        "downward_displacement_mm": 0.2,
                        "rocking": False,
                        "permanent_deformation": False,
                        "support_disengagement": False,
                    }
                    for half, count in (("left", 31), ("right", 39))
                    for index in range(1, count + 1)
                ],
            }
            housing_metrics = {
                "fastener_manufacturer": "TEST-FASTENER-MAKER",
                "fastener_mpn": "M1.4-ROUND-EXACT",
                "fastener_order_code": "ORDER-M1.4-ROUND-4MM-ZINC-PH0",
                "fastener_drawing_revision": "REV-C",
                "fastener_drawing_sha256": housing_documents["fastener_drawing"]["sha256"],
                "head_style": "rounded_pan_or_button",
                "nominal_thread_diameter_mm": 1.4,
                "thread_classification": "direct_plastic_thread_forming",
                "thread_form": "thread_forming_30_degree_flank",
                "thread_pitch_mm": 0.4,
                "thread_flank_angle_degrees": 30.0,
                "thread_major_diameter_mm": 1.4,
                "thread_minor_diameter_mm": 1.0,
                "material": "steel",
                "finish": "zinc",
                "drive_recess": "PH0",
                "minimum_head_diameter_mm": 2.8,
                "maximum_head_diameter_mm": 3.0,
                "minimum_head_height_mm": 1.0,
                "maximum_head_height_mm": 1.2,
                "minimum_under_head_length_mm": 3.9,
                "maximum_under_head_length_mm": 4.1,
                "maximum_finished_pcb_hole_diameter_mm": 1.7,
                "minimum_radial_bearing_width_mm": 0.55,
                "driver_manufacturer": "TEST-DRIVER-MAKER",
                "driver_mpn": "PH0-3MM-SWEEP",
                "driver_drawing_sha256": housing_documents["driver_drawing"]["sha256"],
                "maximum_driver_shaft_diameter_mm": 2.8,
                "maximum_driver_runout_mm": 0.1,
                "maximum_driver_sweep_mm": 3.0,
                "production_print": production_print,
                "assembly_identity": assembly_identity,
                "assembly_fit_condition_count": 16,
                "head_adjacent_fit_condition_count": 32,
                "install_remove_cycles": 10,
                "torque_ratio": 3.0,
                "tested_switch_positions": 70,
                "maximum_displacement_mm": 0.2,
                "rocking": False,
                "loosening": False,
                "permanent_deformation": False,
                "support_disengagement": False,
            }

            transition_records = [
                {
                    "half": half,
                    "no_load_voltage_v": voltage,
                    "direction": direction,
                    "cycle": cycle,
                    "vbat_samples_v": [voltage, voltage, voltage],
                    "vdd_samples_v": [3.3, 3.3, 3.3],
                    "expected_vdd_v": 3.3,
                    "brownout_reset": False,
                    "boot_loop": False,
                    "usb_reenumeration_failure": False,
                    "stuck_power_state": False,
                    "visible_arcing": False,
                }
                for half in ("left", "right")
                for voltage in (3.3, 4.2)
                for direction in ("off_to_on", "on_to_off")
                for cycle in range(1, 21)
            ]
            rf_records = [
                {
                    "half": half,
                    "ble_channel": 37,
                    "state": state,
                    "orientation": orientation,
                    "hands": hands,
                    "distance_m": 5.0,
                    "both_halves_communicating": True,
                    "baseline_rssi_dbm": [-60.0] * 30,
                    "final_rssi_dbm": [-60.0] * 30,
                    "reports_expected": 10000,
                    "missing_sequence_numbers": [],
                    "disconnect_events": [],
                    "reconnect_events": [],
                }
                for half in ("left", "right")
                for state in (
                    "battery_only",
                    "usb_charging",
                    "charge_complete",
                    "usb_unplug_transition",
                )
                for orientation in ("normal", "90_degrees", "180_degrees")
                for hands in ("absent", "home_row")
            ]
            power_data = {
                "identity": {
                    "battery_mpn": "PACK-301230-PROTECTED",
                    "battery_lot": "LOT-1",
                    "power_switch_mpn": "IMMS-EXACT-MPN-1",
                    "firmware_build_sha256": source_digests["firmware_build_evidence"],
                    "housing_manifest_sha256": source_digests["housing_manifest"],
                    "host_id": "TEST-HOST",
                    "ble_channels": [37],
                },
                "transition_records": transition_records,
                "rf_records": rf_records,
            }
            power_metrics = {
                "cold_cycles_per_voltage_and_direction": 20,
                "brownout_count": 0,
                "power_fault_count": 0,
                "maximum_vbat_droop_v": 0.0,
                "maximum_vdd_droop_v": 0.0,
                "maximum_vbat_ringing_v": 0.0,
                "rssi_samples_per_state": 30,
                "reports_per_state": 10000,
                "packet_loss_ratio": 0.0,
                "median_rssi_degradation_db": 0.0,
                "disconnect_count": 0,
                "reconnect_count": 0,
            }

            procurement_identity = {
                "parts": json.loads(json.dumps(controller_data["parts"])),
                "keycaps": json.loads(json.dumps(keycap_identity_map)),
            }
            pending_package_errors = _positive_package_identity_errors(
                V2_ROOT / "fabrication/kc2_x3_v2_fabrication_manifest.json",
                controller_identity={
                    "purchased_parts": procurement_identity["parts"],
                },
                scan_identity={"keycaps": procurement_identity["keycaps"]},
                source_digests=source_digests,
                seen_paths=set(),
            )
            self.assertTrue(
                any("draft/not order-ready" in error for error in pending_package_errors),
                pending_package_errors,
            )
            self.assertTrue(
                any("pending" in error for error in pending_package_errors),
                pending_package_errors,
            )
            fabrication_products: dict[str, object] = {}
            for half, board_binding in (("left", "left_board"), ("right", "right_board")):
                bom_path = temp_root / f"positive-{half}-bom.json"
                bom_payload = {
                    "order_ready": True,
                    "source_board_sha256": source_digests[board_binding],
                    "procurement_identity": procurement_identity,
                    "line_items": [],
                }
                bom_path.write_text(
                    json.dumps(bom_payload, indent=2) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
                fabrication_products[half] = {
                    "source_board_sha256": source_digests[board_binding],
                    "files": [
                        {
                            "name": bom_path.name,
                            "size": bom_path.stat().st_size,
                            "sha256": sha256_file(bom_path),
                        }
                    ],
                    "bom": {"json": bom_path.relative_to(ROOT).as_posix()},
                }
            positive_fabrication_manifest_path = temp_root / "positive-fabrication-manifest.json"
            positive_fabrication_manifest_path.write_text(
                json.dumps(
                    {
                        "status": "order_ready_verified_physical_evidence",
                        "order_ready": True,
                        "products": fabrication_products,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            positive_identity_context = {
                "controller_identity": {
                    "purchased_parts": procurement_identity["parts"],
                },
                "scan_identity": {"keycaps": procurement_identity["keycaps"]},
                "source_digests": source_digests,
            }
            self.assertEqual(
                _positive_package_identity_errors(
                    positive_fabrication_manifest_path,
                    **positive_identity_context,
                    seen_paths=set(),
                ),
                [],
            )
            left_bom_path = temp_root / "positive-left-bom.json"
            left_bom_baseline = left_bom_path.read_text(encoding="utf-8")
            left_bom_mutation = json.loads(left_bom_baseline)
            left_bom_mutation["procurement_identity"]["parts"]["choc_switch"][
                "mpn"
            ] = "UNBOUND-CHOC-SWITCH"
            left_bom_path.write_text(
                json.dumps(left_bom_mutation, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            fabrication_products["left"]["files"][0].update(
                size=left_bom_path.stat().st_size,
                sha256=sha256_file(left_bom_path),
            )
            positive_fabrication_manifest_path.write_text(
                json.dumps(
                    {
                        "status": "order_ready_verified_physical_evidence",
                        "order_ready": True,
                        "products": fabrication_products,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            self.assertTrue(
                _positive_package_identity_errors(
                    positive_fabrication_manifest_path,
                    **positive_identity_context,
                    seen_paths=set(),
                )
            )
            left_bom_path.write_text(
                left_bom_baseline,
                encoding="utf-8",
                newline="\n",
            )
            fabrication_products["left"]["files"][0].update(
                size=left_bom_path.stat().st_size,
                sha256=sha256_file(left_bom_path),
            )
            positive_fabrication_manifest_path.write_text(
                json.dumps(
                    {
                        "status": "order_ready_verified_physical_evidence",
                        "order_ready": True,
                        "products": fabrication_products,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            source_paths["fabrication_manifest"] = positive_fabrication_manifest_path
            source_bindings["fabrication_manifest"] = file_record(
                positive_fabrication_manifest_path,
                "release-source",
            )
            source_digests["fabrication_manifest"] = source_bindings[
                "fabrication_manifest"
            ]["sha256"]

            def typed_bundle(
                bundle: str,
                data: dict[str, object],
                metrics: dict[str, object],
            ) -> dict[str, object]:
                if bundle == "housing_fastener_deflection":
                    calibration = write_json_document(
                        f"{bundle}-calibration.json",
                        "calibration-certificate",
                        {
                            "schema": "kc2-x3-v2-structural-calibration-v1",
                            "bundle": bundle,
                            "production_lot_id": production_lot_id,
                            "specimen_coupon_id": housing_specimen_id,
                        },
                    )
                else:
                    calibration = write_document(
                        f"{bundle}-calibration.txt",
                        "calibration-certificate",
                    )
                raw_path = temp_root / f"{bundle}-raw.json"
                raw_path.write_text(
                    json.dumps(
                        {
                            "schema": "kc2-x3-v2-physical-raw-bundle-v1",
                            "bundle": bundle,
                            "source_bindings": source_digests,
                            "data": data,
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
                return {
                    "status": "passed",
                    "artifacts": [
                        {
                            **file_record(
                                raw_path,
                                {
                                    "controller_service": "controller-service-raw-json",
                                    "physical_scan": "physical-scan-raw-json",
                                    "housing_fastener_deflection": "housing-fastener-deflection-raw-json",
                                    "power_rf": "power-rf-raw-json",
                                }[bundle],
                            ),
                            "measured_at": "2026-08-29T12:00:00+09:00",
                            "equipment_id": f"{bundle}-equipment",
                            "calibration_evidence": calibration,
                        }
                    ],
                    "metrics": metrics,
                }

            evidence = {
                "schema": "kc2-x3-v2-physical-evidence-v1",
                "requirement_ids": [
                    "CON-ARCH-004",
                    "CON-ARCH-006",
                    "CON-ARCH-007",
                    "REL-ARCH-001",
                ],
                "variant": "x3-v2",
                "status": "passed",
                "order_ready": True,
                "source_bindings": source_bindings,
                "bundles": {
                    "controller_service": typed_bundle(
                        "controller_service", controller_data, controller_metrics
                    ),
                    "physical_scan": typed_bundle(
                        "physical_scan", scan_data, scan_metrics
                    ),
                    "housing_fastener_deflection": typed_bundle(
                        "housing_fastener_deflection", housing_data, housing_metrics
                    ),
                    "power_rf": typed_bundle("power_rf", power_data, power_metrics),
                },
            }
            self.assertEqual(
                verify_physical_evidence_manifest(evidence, source_paths),
                {
                    "controller_service": [],
                    "physical_scan": [],
                    "housing_fastener_deflection": [],
                    "power_rf": [],
                },
            )
            self.assertTrue(suite_mock.called)
            for failed_module in ("coupon", "outline"):
                with self.subTest(positive_artifact_suite_failure=failed_module):
                    suite_mock.return_value = [
                        f"artifact suite {failed_module} verifier failed"
                    ]
                    self.assertTrue(
                        all(
                            verify_physical_evidence_manifest(
                                evidence, source_paths
                            ).values()
                        )
                    )
            suite_mock.return_value = []
            missing_render_binding = json.loads(json.dumps(evidence))
            del missing_render_binding["source_bindings"]["render_manifest"]
            self.assertTrue(
                all(
                    verify_physical_evidence_manifest(
                        missing_render_binding,
                        source_paths,
                    ).values()
                )
            )
            stale_outline_binding = json.loads(json.dumps(evidence))
            stale_outline_binding["source_bindings"]["outline_report"]["sha256"] = "0" * 64
            self.assertTrue(
                all(
                    verify_physical_evidence_manifest(
                        stale_outline_binding,
                        source_paths,
                    ).values()
                )
            )
            conservative_manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
            conservative_housing = json.loads(
                (ROOT / "hardware/case/draft/x3-v2/kc2_x3_v2_housing_manifest.json")
                .read_text(encoding="utf-8")
            )
            self.assertEqual(
                controller_service_order_readiness_blockers(
                    conservative_manifest,
                    conservative_housing,
                    evidence,
                    source_paths,
                ),
                [],
            )

            traversal = json.loads(json.dumps(evidence))
            traversal["bundles"]["controller_service"]["artifacts"][0]["path"] = "../escape.json"
            self.assertTrue(
                verify_physical_evidence_manifest(traversal)["controller_service"]
            )
            stale_hash = json.loads(json.dumps(evidence))
            stale_hash["source_bindings"]["left_board"]["sha256"] = "0" * 64
            self.assertTrue(
                all(verify_physical_evidence_manifest(stale_hash, source_paths).values())
            )
            insufficient = json.loads(json.dumps(evidence))
            insufficient["bundles"]["power_rf"]["metrics"]["reports_per_state"] = 9999
            self.assertTrue(
                verify_physical_evidence_manifest(insufficient, source_paths)["power_rf"]
            )
            waived_calibration = json.loads(json.dumps(evidence))
            waived_calibration["bundles"]["controller_service"]["artifacts"][0][
                "calibration_evidence"
            ] = "not_applicable_nonmeasurement"
            self.assertTrue(
                verify_physical_evidence_manifest(waived_calibration, source_paths)[
                    "controller_service"
                ]
            )
            reused = json.loads(json.dumps(evidence))
            reused["bundles"]["physical_scan"]["artifacts"] = json.loads(
                json.dumps(reused["bundles"]["controller_service"]["artifacts"])
            )
            self.assertTrue(
                verify_physical_evidence_manifest(reused, source_paths)["physical_scan"]
            )

            controller_artifact_template = evidence["bundles"]["controller_service"][
                "artifacts"
            ][0]
            controller_raw_path = ROOT / controller_artifact_template["path"]
            controller_raw_baseline = json.loads(
                controller_raw_path.read_text(encoding="utf-8")
            )
            for label, mutate in (
                (
                    "self-asserted stack clearance",
                    lambda payload, metrics: (
                        payload["data"]["stack_records"][0].update(
                            minimum_clearance_mm=0.6
                        ),
                        metrics.update(minimum_stack_clearance_mm=0.6),
                    ),
                ),
                (
                    "failed measured continuity",
                    lambda payload, _metrics: payload["data"]["service_records"][0].update(
                        power_on_resistance_ohm=2.0
                    ),
                ),
                (
                    "purchased battery lead exceeds J_BAT1 fit allowance",
                    lambda payload, metrics: (
                        payload["data"]["parts"]["battery"].update(
                            lead_conductor_diameter_mm=0.85
                        ),
                        metrics.update(
                            lead_conductor_diameter_mm=0.85,
                            lead_to_j_bat_diametral_clearance_mm=0.05,
                        ),
                    ),
                ),
                (
                    "pending exact Kailh switch identity",
                    lambda payload, metrics: (
                        payload["data"]["parts"]["choc_switch"].update(mpn="PENDING"),
                        metrics.update(choc_switch_mpn="PENDING"),
                    ),
                ),
                (
                    "status prose controller manufacturer",
                    lambda payload, metrics: (
                        payload["data"]["parts"]["controller"].update(
                            manufacturer="UNKNOWN SUPPLIER"
                        ),
                        metrics.update(controller_manufacturer="UNKNOWN SUPPLIER"),
                    ),
                ),
                (
                    "whitespace SKU used as switch MPN",
                    lambda payload, metrics: (
                        payload["data"]["parts"]["choc_switch"].update(mpn="TBD SKU"),
                        metrics.update(choc_switch_mpn="TBD SKU"),
                    ),
                ),
                (
                    "status prose drawing revision",
                    lambda payload, metrics: (
                        payload["data"]["parts"]["choc_socket"].update(
                            drawing_revision="TO BE CONFIRMED"
                        ),
                        metrics.update(
                            choc_socket_drawing_revision="TO BE CONFIRMED"
                        ),
                    ),
                ),
                (
                    "status prose controller datasheet identity",
                    lambda payload, _metrics: payload["data"]["documents"][
                        "controller_datasheet"
                    ].update(document_id="PENDING DATASHEET"),
                ),
                (
                    "coded provisional controller datasheet identity",
                    lambda payload, _metrics: payload["data"]["documents"][
                        "controller_datasheet"
                    ].update(document_id="PROVISIONAL-1"),
                ),
                (
                    "POWER travel below full actuator travel",
                    lambda payload, _metrics: payload["data"]["service_records"][0].update(
                        power_actuator_travel_mm=1.59
                    ),
                ),
                (
                    "POWER full-travel controller contact",
                    lambda payload, _metrics: payload["data"]["service_records"][0].update(
                        power_full_travel_contact_with_controller=True
                    ),
                ),
                (
                    "RESET service probe too large",
                    lambda payload, _metrics: payload["data"]["service_records"][0].update(
                        reset_probe_diameter_mm=3.01
                    ),
                ),
            ):
                with self.subTest(controller_raw_gate=label):
                    candidate = json.loads(json.dumps(evidence))
                    payload = json.loads(json.dumps(controller_raw_baseline))
                    metrics = candidate["bundles"]["controller_service"]["metrics"]
                    mutate(payload, metrics)
                    controller_raw_path.write_text(
                        json.dumps(payload, indent=2) + "\n",
                        encoding="utf-8",
                        newline="\n",
                    )
                    artifact = candidate["bundles"]["controller_service"]["artifacts"][0]
                    artifact["sha256"] = sha256_file(controller_raw_path)
                    artifact["size_bytes"] = controller_raw_path.stat().st_size
                    self.assertTrue(
                        verify_physical_evidence_manifest(candidate, source_paths)[
                            "controller_service"
                        ],
                        label,
                    )
            controller_raw_path.write_text(
                json.dumps(controller_raw_baseline, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            scan_artifact_template = evidence["bundles"]["physical_scan"]["artifacts"][0]
            scan_raw_path = ROOT / scan_artifact_template["path"]
            scan_raw_baseline = json.loads(scan_raw_path.read_text(encoding="utf-8"))
            scan_mutations = (
                (
                    "missing 1U keycap physical fit",
                    lambda payload: payload["data"]["keycap_fit_records"].pop(0),
                ),
                (
                    "wrong left Choc socket rotation",
                    lambda payload: payload["data"]["switch_fit_records"][0].update(
                        orientation="right_mirrored"
                    ),
                ),
                (
                    "failed Choc bottom socket fit",
                    lambda payload: payload["data"]["switch_fit_records"][0].update(
                        bottom_socket_fit_pass=False
                    ),
                ),
                (
                    "failed MX five-pin fit",
                    lambda payload: payload["data"]["switch_fit_records"][1].update(
                        mx_five_pin_fit_pass=False
                    ),
                ),
                (
                    "pending non-1U keycap identity",
                    lambda payload: payload["data"]["keycap_fit_records"][0].update(
                        keycap_mpn="PENDING"
                    ),
                ),
                (
                    "status prose keycap manufacturer",
                    lambda payload: payload["data"]["keycap_fit_records"][0].update(
                        keycap_manufacturer="UNKNOWN SUPPLIER"
                    ),
                ),
                (
                    "non-1U keycap spacing outside requirement",
                    lambda payload: payload["data"]["keycap_fit_records"][0].update(
                        minimum_spacing_mm=2.01
                    ),
                ),
                (
                    "ES1B polarity failure",
                    lambda payload: payload["data"]["diode_records"][0].update(
                        pad1_cathode_polarity_pass=False
                    ),
                ),
                (
                    "ES1B hand-solder access failure",
                    lambda payload: payload["data"]["diode_records"][0].update(
                        hand_solder_access_pass=False
                    ),
                ),
                (
                    "ES1B housing interference",
                    lambda payload: payload["data"]["diode_records"][0].update(
                        minimum_housing_clearance_mm=-0.01
                    ),
                ),
            )
            for label, mutate in scan_mutations:
                with self.subTest(physical_scan_gate=label):
                    candidate = json.loads(json.dumps(evidence))
                    payload = json.loads(json.dumps(scan_raw_baseline))
                    mutate(payload)
                    scan_raw_path.write_text(
                        json.dumps(payload, indent=2) + "\n",
                        encoding="utf-8",
                        newline="\n",
                    )
                    artifact = candidate["bundles"]["physical_scan"]["artifacts"][0]
                    artifact["sha256"] = sha256_file(scan_raw_path)
                    artifact["size_bytes"] = scan_raw_path.stat().st_size
                    self.assertTrue(
                        verify_physical_evidence_manifest(candidate, source_paths)[
                            "physical_scan"
                        ],
                        label,
                    )
            scan_raw_path.write_text(
                json.dumps(scan_raw_baseline, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            housing_artifact_template = evidence["bundles"]["housing_fastener_deflection"][
                "artifacts"
            ][0]
            housing_raw_path = ROOT / housing_artifact_template["path"]
            housing_raw_baseline = json.loads(housing_raw_path.read_text(encoding="utf-8"))

            def identity_mutation(key: str, value: object):
                def mutate(payload: dict[str, object], metrics: dict[str, object]) -> None:
                    payload["data"]["fastener_identity"][key] = value
                    metric_names = {
                        "manufacturer": "fastener_manufacturer",
                        "mpn": "fastener_mpn",
                        "order_code": "fastener_order_code",
                        "drawing_revision": "fastener_drawing_revision",
                    }
                    metric_key = metric_names.get(key, key)
                    if metric_key in metrics:
                        metrics[metric_key] = value

                return mutate

            def record_mutation(key: str, value: object):
                return lambda payload, _metrics: payload["data"]["fastener_records"][0].update(
                    {key: value}
                )

            housing_mutations = (
                (
                    "placeholder fastener manufacturer",
                    identity_mutation("manufacturer", "PENDING_PHYSICAL_GATE"),
                ),
                (
                    "status prose fastener manufacturer",
                    identity_mutation("manufacturer", "UNKNOWN SUPPLIER"),
                ),
                (
                    "fastener MPN lacks a numeric identity",
                    identity_mutation("mpn", "EXACT-FASTENER-MPN"),
                ),
                (
                    "coded provisional fastener order code",
                    identity_mutation("order_code", "PROVISIONAL-1"),
                ),
                (
                    "status prose fastener drawing revision",
                    identity_mutation("drawing_revision", "TO BE CONFIRMED"),
                ),
                ("missing exact order code", identity_mutation("order_code", "")),
                ("missing drawing revision", identity_mutation("drawing_revision", "")),
                ("wrong head style", identity_mutation("head_style", "ultra_low")),
                (
                    "non-direct-plastic thread classification",
                    identity_mutation("thread_classification", "metric_machine_thread"),
                ),
                (
                    "wrong nominal thread diameter",
                    identity_mutation("nominal_thread_diameter_mm", 1.3),
                ),
                ("missing thread form", identity_mutation("thread_form", "")),
                (
                    "uncontrolled direct-plastic thread form self-label",
                    identity_mutation("thread_form", "banana-thread-forming"),
                ),
                ("missing direct-plastic pitch", identity_mutation("thread_pitch_mm", 0.0)),
                (
                    "non-M1.4 measured thread major diameter",
                    identity_mutation("thread_major_diameter_mm", 1.3),
                ),
                (
                    "controlled thread form with non-30-degree flank",
                    identity_mutation("thread_flank_angle_degrees", 29.0),
                ),
                (
                    "thread pitch diverges from controlled drawing",
                    identity_mutation("thread_pitch_mm", 0.5),
                ),
                ("missing material", identity_mutation("material", "")),
                ("missing finish", identity_mutation("finish", "")),
                ("missing drive recess", identity_mutation("drive_recess", "")),
                (
                    "reversed length tolerance",
                    identity_mutation("maximum_under_head_length_mm", 3.8),
                ),
                (
                    "oversize head diameter",
                    identity_mutation("maximum_head_diameter_mm", 3.01),
                ),
                (
                    "oversize head height",
                    identity_mutation("maximum_head_height_mm", 1.21),
                ),
                (
                    "unrecomputed radial bearing",
                    identity_mutation("maximum_finished_pcb_hole_diameter_mm", 1.8),
                ),
                (
                    "missing driver MPN",
                    identity_mutation("driver_mpn", ""),
                ),
                (
                    "driver shaft/runout mismatch",
                    identity_mutation("maximum_driver_runout_mm", 0.2),
                ),
                (
                    "measured driver runout not included in sweep",
                    record_mutation("measured_driver_runout_mm", 0.2),
                ),
                (
                    "measured shaft exceeds controlled maximum despite fitting sweep",
                    lambda payload, _metrics: payload["data"]["fastener_records"][0].update(
                        measured_driver_shaft_diameter_mm=2.9,
                        measured_driver_runout_mm=0.05,
                        measured_driver_sweep_mm=3.0,
                    ),
                ),
                ("wrong measured length", record_mutation("actual_under_head_length_mm", 4.2)),
                (
                    "source-unbound pilot and PCB geometry",
                    lambda payload, _metrics: payload["data"]["fastener_records"][0].update(
                        actual_under_head_length_mm=3.9,
                        printed_pilot_diameter_mm=0.01,
                        actual_pcb_thickness_mm=1.0,
                        installed_penetration_mm=2.9,
                        measured_blind_pilot_depth_mm=3.2,
                        measured_closed_bottom_thickness_mm=0.7,
                        measured_available_plastic_depth_mm=3.9,
                        tip_clearance_mm=0.3,
                    ),
                ),
                (
                    "zero tip clearance self-consistent geometry",
                    lambda payload, _metrics: payload["data"]["fastener_records"][0].update(
                        measured_blind_pilot_depth_mm=2.4,
                        measured_closed_bottom_thickness_mm=0.7,
                        measured_available_plastic_depth_mm=3.1,
                        tip_clearance_mm=0.0,
                    ),
                ),
                ("missing pilot measurement", record_mutation("printed_pilot_diameter_mm", 0.0)),
                ("missing PCB thickness", record_mutation("actual_pcb_thickness_mm", 0.0)),
                ("wrong penetration", record_mutation("installed_penetration_mm", 2.0)),
                ("negative tip clearance", record_mutation("tip_clearance_mm", -0.1)),
                ("missing tapping torque", record_mutation("tapping_torque_n_m", 0.0)),
                (
                    "stripping ratio measured against installation instead of tapping",
                    lambda payload, metrics: (
                        [
                            record.update(
                                tapping_torque_n_m=0.04,
                                selected_installation_torque_n_m=0.01,
                                stripping_torque_n_m=0.06,
                            )
                            for record in payload["data"]["fastener_records"]
                        ],
                        metrics.update(torque_ratio=6.0),
                    ),
                ),
                (
                    "insufficient stripping ratio",
                    record_mutation("stripping_torque_n_m", 0.03),
                ),
                (
                    "selected torque outside seating window",
                    record_mutation("selected_installation_torque_n_m", 0.02),
                ),
                (
                    "missing clamp retention",
                    record_mutation("pull_through_clamp_retention_pass", False),
                ),
                (
                    "forced full pattern",
                    record_mutation("full_pattern_without_forcing", False),
                ),
                (
                    "missing rest skirt clearance",
                    lambda payload, _metrics: payload["data"]["assembly_fit_records"][0].update(
                        keycap_skirt_clearance_at_rest_mm=0.0
                    ),
                ),
                (
                    "missing travel skirt clearance",
                    lambda payload, _metrics: payload["data"]["assembly_fit_records"][0].update(
                        keycap_skirt_clearance_at_full_travel_mm=0.0
                    ),
                ),
                ("too few service cycles", record_mutation("install_remove_cycles", 9)),
                (
                    "independent pilot depth and impossible tip clearance",
                    lambda payload, _metrics: payload["data"]["fastener_records"][0].update(
                        measured_blind_pilot_depth_mm=0.01,
                        tip_clearance_mm=999.0,
                    ),
                ),
                (
                    "missing production material",
                    lambda payload, metrics: (
                        payload["data"]["production_print"].update(material_mpn=""),
                        metrics["production_print"].update(material_mpn=""),
                    ),
                ),
                (
                    "production material uses a whitespace SKU",
                    lambda payload, metrics: (
                        payload["data"]["production_print"].update(
                            material_mpn="TBD SKU"
                        ),
                        metrics["production_print"].update(material_mpn="TBD SKU"),
                    ),
                ),
                (
                    "production material uses awaiting lifecycle code",
                    lambda payload, metrics: (
                        payload["data"]["production_print"].update(
                            material_mpn="AWAITING-SKU-1"
                        ),
                        metrics["production_print"].update(
                            material_mpn="AWAITING-SKU-1"
                        ),
                    ),
                ),
                (
                    "production printer manufacturer is status prose",
                    lambda payload, metrics: (
                        payload["data"]["production_print"].update(
                            printer_manufacturer="PENDING DATASHEET"
                        ),
                        metrics["production_print"].update(
                            printer_manufacturer="PENDING DATASHEET"
                        ),
                    ),
                ),
                (
                    "production printer manufacturer is unspecified",
                    lambda payload, metrics: (
                        payload["data"]["production_print"].update(
                            printer_manufacturer="UNSPECIFIED"
                        ),
                        metrics["production_print"].update(
                            printer_manufacturer="UNSPECIFIED"
                        ),
                    ),
                ),
                (
                    "invalid production layer height",
                    lambda payload, metrics: (
                        payload["data"]["production_print"].update(layer_height_mm=0.5),
                        metrics["production_print"].update(layer_height_mm=0.5),
                    ),
                ),
                (
                    "missing load-affecting wall setting",
                    lambda payload, metrics: (
                        payload["data"]["production_print"].pop(
                            "wall_perimeter_count"
                        ),
                        metrics["production_print"].pop("wall_perimeter_count"),
                    ),
                ),
                (
                    "structural specimen reuses electrical scan coupon",
                    lambda payload, metrics: (
                        payload["data"]["production_print"].update(
                            specimen_coupon_id="COUPON-LOT-1"
                        ),
                        metrics["production_print"].update(
                            specimen_coupon_id="COUPON-LOT-1"
                        ),
                    ),
                ),
                (
                    "missing controlled print speed",
                    lambda payload, metrics: (
                        payload["data"]["production_print"].update(print_speed_mm_s=0.0),
                        metrics["production_print"].update(print_speed_mm_s=0.0),
                    ),
                ),
                (
                    "fastener record from a different print lot",
                    lambda payload, _metrics: payload["data"]["fastener_records"][0].update(
                        production_lot_id="HOUSING-PRINT-LOT-2"
                    ),
                ),
                (
                    "assembly fit from a different structural specimen",
                    lambda payload, _metrics: payload["data"]["assembly_fit_records"][0].update(
                        specimen_coupon_id="HOUSING-STRUCTURAL-SPECIMEN-2"
                    ),
                ),
                (
                    "mounting-head fit from a different print lot",
                    lambda payload, _metrics: payload["data"][
                        "head_adjacent_fit_records"
                    ][0].update(production_lot_id="HOUSING-PRINT-LOT-2"),
                ),
                (
                    "deflection from a different structural specimen",
                    lambda payload, _metrics: payload["data"]["deflection_records"][0].update(
                        specimen_coupon_id="HOUSING-STRUCTURAL-SPECIMEN-2"
                    ),
                ),
                (
                    "wrong production orientation",
                    lambda payload, metrics: (
                        payload["data"]["production_print"].update(
                            print_orientation="sideways"
                        ),
                        metrics["production_print"].update(print_orientation="sideways"),
                    ),
                ),
                (
                    "unbound slicer profile",
                    lambda payload, metrics: (
                        payload["data"]["production_print"].update(
                            slicer_profile_sha256="0" * 64
                        ),
                        metrics["production_print"].update(
                            slicer_profile_sha256="0" * 64
                        ),
                    ),
                ),
                (
                    "profile incompatible FDM process",
                    lambda payload, metrics: (
                        payload["data"]["production_print"].update(
                            production_process="FDM"
                        ),
                        metrics["production_print"].update(production_process="FDM"),
                    ),
                ),
                (
                    "placeholder printer identity",
                    lambda payload, metrics: (
                        payload["data"]["production_print"].update(
                            printer_model="TBD_PRINTER"
                        ),
                        metrics["production_print"].update(
                            printer_model="TBD_PRINTER"
                        ),
                    ),
                ),
                (
                    "incomplete supported assembly modes",
                    lambda payload, metrics: (
                        payload["data"]["assembly_identity"].update(
                            supported_modes=["choc_v2"]
                        ),
                        metrics["assembly_identity"].update(supported_modes=["choc_v2"]),
                    ),
                ),
                (
                    "wrong supported keycap identity",
                    lambda payload, _metrics: payload["data"]["assembly_fit_records"][0].update(
                        keycap_mpn="UNBOUND-CAP"
                    ),
                ),
                (
                    "missing 1U housing fit condition",
                    lambda payload, _metrics: payload["data"][
                        "assembly_fit_records"
                    ].pop(0),
                ),
                (
                    "missing mounting-head-adjacent condition",
                    lambda payload, _metrics: payload["data"][
                        "head_adjacent_fit_records"
                    ].pop(),
                ),
                (
                    "duplicate mounting-head-adjacent condition",
                    lambda payload, _metrics: payload["data"][
                        "head_adjacent_fit_records"
                    ].append(
                        dict(payload["data"]["head_adjacent_fit_records"][0])
                    ),
                ),
                (
                    "wrong board-derived limiting switch reference",
                    lambda payload, _metrics: payload["data"][
                        "head_adjacent_fit_records"
                    ][0].update(overlapping_switch_reference="SW999"),
                ),
                (
                    "housing switch identity self-consistently diverges from controller evidence",
                    lambda payload, metrics: (
                        payload["data"]["assembly_identity"].update(
                            choc_switch_mpn="UNBOUND-CHOC-SWITCH"
                        ),
                        [
                            record.update(switch_mpn="UNBOUND-CHOC-SWITCH")
                            for record in payload["data"]["assembly_fit_records"]
                            if record["assembly_mode"] == "choc_v2"
                        ],
                        metrics["assembly_identity"].update(
                            choc_switch_mpn="UNBOUND-CHOC-SWITCH"
                        ),
                    ),
                ),
                (
                    "placeholder housing keycap identity",
                    lambda payload, metrics: (
                        payload["data"]["assembly_identity"]["keycap_identities"][
                            "choc_v2:1.25"
                        ].update(mpn="TBD_KEYCAP"),
                        [
                            record.update(keycap_mpn="TBD_KEYCAP")
                            for record in payload["data"]["assembly_fit_records"]
                            if record["assembly_mode"] == "choc_v2"
                            and record["width_u"] == 1.25
                        ],
                        metrics["assembly_identity"]["keycap_identities"][
                            "choc_v2:1.25"
                        ].update(mpn="TBD_KEYCAP"),
                    ),
                ),
                (
                    "housing keycap identity diverges from physical scan",
                    lambda payload, metrics: (
                        payload["data"]["assembly_identity"]["keycap_identities"][
                            "mx:1.75"
                        ].update(mpn="UNBOUND-MX-1.75-CAP"),
                        [
                            record.update(keycap_mpn="UNBOUND-MX-1.75-CAP")
                            for record in payload["data"]["assembly_fit_records"]
                            if record["assembly_mode"] == "mx"
                            and record["width_u"] == 1.75
                        ],
                        metrics["assembly_identity"]["keycap_identities"][
                            "mx:1.75"
                        ].update(mpn="UNBOUND-MX-1.75-CAP"),
                    ),
                ),
                (
                    "wrong switch reference set",
                    lambda payload, _metrics: payload["data"]["deflection_records"][0].update(
                        switch_reference="SW999"
                    ),
                ),
            )
            for label, mutate in housing_mutations:
                with self.subTest(physical_housing_gate=label):
                    candidate = json.loads(json.dumps(evidence))
                    payload = json.loads(json.dumps(housing_raw_baseline))
                    metrics = candidate["bundles"]["housing_fastener_deflection"]["metrics"]
                    mutate(payload, metrics)
                    housing_raw_path.write_text(
                        json.dumps(payload, indent=2) + "\n",
                        encoding="utf-8",
                        newline="\n",
                    )
                    artifact = candidate["bundles"]["housing_fastener_deflection"][
                        "artifacts"
                    ][0]
                    artifact["sha256"] = sha256_file(housing_raw_path)
                    artifact["size_bytes"] = housing_raw_path.stat().st_size
                    self.assertTrue(
                        verify_physical_evidence_manifest(candidate, source_paths)[
                            "housing_fastener_deflection"
                        ],
                        label,
                    )
            housing_raw_path.write_text(
                json.dumps(housing_raw_baseline, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            raw_mutation = json.loads(json.dumps(evidence))
            power_artifact = raw_mutation["bundles"]["power_rf"]["artifacts"][0]
            power_path = ROOT / power_artifact["path"]
            raw_payload = json.loads(power_path.read_text(encoding="utf-8"))
            raw_payload["data"]["rf_records"][0]["reports_expected"] = 9999
            power_path.write_text(
                json.dumps(raw_payload, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            power_artifact["sha256"] = sha256_file(power_path)
            power_artifact["size_bytes"] = power_path.stat().st_size
            self.assertTrue(
                verify_physical_evidence_manifest(raw_mutation, source_paths)["power_rf"]
            )

    def test_physical_evidence_artifacts_must_match_candidate_git_index(self) -> None:
        from tools.verify_kc2_x3_v2 import _git_index_artifact_errors

        with TemporaryDirectory(dir=ROOT) as temporary:
            untracked = Path(temporary) / "plausible-but-untracked-measurement.json"
            untracked.write_text("{}\n", encoding="utf-8", newline="\n")
            errors = _git_index_artifact_errors(
                untracked,
                sha256_file(untracked),
                label="physical measurement",
            )
            self.assertTrue(any("not tracked" in error for error in errors), errors)

    def test_positive_outline_verification_is_read_only_and_checks_bound_report(self) -> None:
        from tools.verify_kc2_x3_v2 import _verify_positive_order_artifact_suite

        completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with (
            patch(
                "tools.verify_kc2_x3_v2.subprocess.run",
                return_value=completed,
            ) as run_mock,
            patch("tools.verify_kc2_x3_v2.shutil.which", return_value="py"),
        ):
            self.assertEqual(_verify_positive_order_artifact_suite(), [])
        commands = [call.args[0] for call in run_mock.call_args_list]
        outline_commands = [
            command
            for command in commands
            if "analyze_outline" in " ".join(str(part) for part in command)
        ]
        self.assertEqual(len(outline_commands), 1)
        outline_command = outline_commands[0]
        self.assertIn("-c", outline_command)
        inline_code = outline_command[outline_command.index("-c") + 1]
        self.assertIn("bound==actual", inline_code)
        self.assertNotIn("write_text", inline_code)
        self.assertNotIn("tools.verify_kc2_x3_v2_outline", [
            outline_command[index + 1]
            for index, value in enumerate(outline_command[:-1])
            if value == "-m"
        ])

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
                (
                    "historical low head envelope",
                    lambda record: record["screw_head_envelope_mm"].update(
                        diameter=2.0, height=0.5
                    ),
                ),
                (
                    "low head style",
                    lambda record: record.update(screw_head_style="ultra_low"),
                ),
                (
                    "flat head style",
                    lambda record: record.update(screw_head_style="flat"),
                ),
                (
                    "countersunk head style",
                    lambda record: record.update(screw_head_style="countersunk"),
                ),
                (
                    "missing head reserve",
                    lambda record: record.pop("screw_head_xy_reserve_mm", None),
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
                ("left", {"imported": 539, "removed": 34, "added": 85, "final": 590}),
                ("right", {"imported": 703, "removed": 38, "added": 99, "final": 764}),
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

            for side, original, replacement in (
                ("left", "(place MH1 1128625 -430000", "(place MH1 1128625 -430001"),
                ("right", "(place MH1 970625 -432500", "(place MH1 970625 -432501"),
            ):
                with self.subTest(side=side, stale_mounting_geometry=True):
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
                    source = session.read_text(encoding="utf-8")
                    self.assertEqual(source.count(original), 1)
                    mutated_session = Path(temporary) / f"mutated-mount-{side}.ses"
                    mutated_session.write_text(
                        source.replace(original, replacement, 1),
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        RuntimeError,
                        f"reviewed {side} controller-compaction session moved the P2 mounting pattern",
                    ):
                        import_reviewed_controller_compact_session(
                            board,
                            mutated_session,
                            side,
                        )

    def test_p1_rounded_head_detours_require_exact_signatures_and_are_idempotent(self) -> None:
        import pcbnew

        from tools import generate_kc2_pcbs as generator
        from tools.finalize_kc2_x3_v2_routes import (
            P1_ROUNDED_HEAD_ROUTE_ADDITIONS,
            P1_ROUNDED_HEAD_ROUTE_REMOVALS,
            _add_route_spec,
            _route_signature,
            apply_p1_rounded_head_route_detours,
        )

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
                    for item in list(board.GetTracks()):
                        board.Delete(item)
                    for spec in P1_ROUNDED_HEAD_ROUTE_REMOVALS[side]:
                        _add_route_spec(board, spec)

                    first = apply_p1_rounded_head_route_detours(board, side)
                    second = apply_p1_rounded_head_route_detours(board, side)
                    signatures = Counter(
                        _route_signature(item) for item in board.GetTracks()
                    )
                    self.assertEqual(
                        first,
                        {
                            "removed": len(P1_ROUNDED_HEAD_ROUTE_REMOVALS[side]),
                            "added": len(P1_ROUNDED_HEAD_ROUTE_ADDITIONS[side]),
                        },
                    )
                    self.assertEqual(second, {"removed": 0, "added": 0})
                    self.assertFalse(
                        set(P1_ROUNDED_HEAD_ROUTE_REMOVALS[side]) & set(signatures)
                    )
                    self.assertTrue(
                        set(P1_ROUNDED_HEAD_ROUTE_ADDITIONS[side]) <= set(signatures)
                    )

                    stale = pcbnew.LoadBoard(str(board_path))
                    for item in list(stale.GetTracks()):
                        stale.Delete(item)
                    for spec in P1_ROUNDED_HEAD_ROUTE_REMOVALS[side][1:]:
                        _add_route_spec(stale, spec)
                    with self.assertRaisesRegex(
                        RuntimeError,
                        f"reviewed {side} P1 rounded-head detour precondition failed",
                    ):
                        apply_p1_rounded_head_route_detours(stale, side)

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
        spec_index = (ROOT / "docs/spec/00.index.md").read_text(encoding="utf-8")

        self.assertIn(
            "| Current routes | Left `590`, SHA-256 prefix `94c49ca2749d`; right `764`, SHA-256 prefix `b54d29e27f1f` |",
            spec_index,
        )
        self.assertNotIn(
            "| Current routes | Left `580`, SHA-256 prefix `7eda6d670a2f`; right `739`, SHA-256 prefix `fc2a819d9ce8` |",
            spec_index,
        )
        self.assertIn(
            "| Left PCB | `hardware/kicad/draft/x3-v2/kc2_left-x3-v2/kc2_left-x3-v2.kicad_pcb` |",
            spec_index,
        )
        self.assertIn(
            "| Right PCB | `hardware/kicad/draft/x3-v2/kc2_right-x3-v2/kc2_right-x3-v2.kicad_pcb` |",
            spec_index,
        )
        self.assertNotIn("C:\\Work\\git\\_Snoworca\\kc2", spec_index)

        current_claims = (
            "디지털 검증을 통과했지만 물리 검증 대기 중인 `kc2-x3-v2` draft는 `CON-ARCH-004`의 70-key v5 배열(왼쪽 31, 오른쪽 39)",
            "70 for digitally verified but not orderable `kc2-x3-v2` under `CON-ARCH-004` (31 left / 39 right)",
            "current X3 V2 v5 rows 15 / 14 / 14 / 15 / 12",
            "active draft `kc2-x3-v2` uses exact Jingdao `ES1B`, LCSC `C437840`, Eleparts goods `9475342`, bottom-side SMA at each of its 70 positions",
            "물리 검증 대기 중인 `kc2-x3-v2` draft는 `CON-ARCH-004`의 70개 switch/diode 배치를 기준으로 별도 검증한다",
            "| KC2 X3 V2 target switch | Kailh low-profile Choc V2 / PG1353-family, 70개.",
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
