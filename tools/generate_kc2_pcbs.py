from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import pcbnew

from tools.canonical_hash import HASH_POLICY, sha256_file
from tools.inset_specctra_boundary import (
    DEFAULT_INSET_MM as X3_V2_AUTOROUTE_BOUNDARY_INSET_MM,
    DEFAULT_PRESERVE_CONTROLLER_ABOVE_MM as X3_V2_AUTOROUTE_PRESERVE_CONTROLLER_ABOVE_MM,
)


ROOT = Path(__file__).resolve().parents[1]
KICAD_ROOT = ROOT / "hardware" / "kicad"
DRAFT_ROOT = KICAD_ROOT / "draft"


def canonical_x3_v2_route_record(side: str, final_count: int, route_digest: str) -> dict[str, object]:
    base = Path("hardware/kicad/draft/x3-v2/autoroute")
    dsn_relative = base / f"kc2_{side}-x3-v2-70-es1b-controller-r3.dsn"
    session_source_dsn_relative = dsn_relative
    ses_relative = base / f"kc2_{side}-x3-v2-70-es1b-controller-r3.ses"
    dsn_path = ROOT / dsn_relative
    session_source_dsn_path = ROOT / session_source_dsn_relative
    ses_path = ROOT / ses_relative
    dsn_text = dsn_path.read_text(encoding="utf-8")
    matches = {
        "global": re.search(
            r"\(structure\b[\s\S]*?\(rule\b[\s\S]*?\(clearance\s+(\d+)\)",
            dsn_text,
        ),
        "kicad_default": re.search(
            r"\(class\s+kicad_default\b[\s\S]*?\(rule\b[\s\S]*?\(clearance\s+(\d+)\)",
            dsn_text,
        ),
    }
    if any(match is None for match in matches.values()):
        raise RuntimeError(f"missing canonical global/default clearance in {dsn_path}")
    default_clearances = {
        label: int(match.group(1))
        for label, match in matches.items()
        if match is not None
    }
    return {
        "dsn": dsn_relative.as_posix(),
        "dsn_role": "current_mh_compact_controller_trackless_routing_input",
        "dsn_mounting_hole_count": len(re.findall(r"\(place\s+MH\d+\b", dsn_text)),
        "session_source_dsn": session_source_dsn_relative.as_posix(),
        "session_source_dsn_sha256": sha256_file(session_source_dsn_path),
        "ses": ses_relative.as_posix(),
        "ses_role": "reviewed_matrix_import_plus_exact_edge_cleanup_and_power_reset_service_routing",
        "dsn_sha256": sha256_file(dsn_path),
        "ses_sha256": sha256_file(ses_path),
        "dsn_default_clearance_internal_units": min(default_clearances.values()),
        "dsn_clearances_internal_units": default_clearances,
        "final_track_via_count": final_count,
        "route_digest_sha256": route_digest,
    }


def find_kicad_share() -> Path:
    for candidate in (
        Path(r"C:\Program Files\KiCad\10.0\share\kicad"),
        Path(r"C:\Program Files\KiCad\9.0\share\kicad"),
        Path(r"C:\Program Files\KiCad\8.0\share\kicad"),
    ):
        if candidate.exists():
            return candidate
    return Path(r"C:\Program Files\KiCad\9.0\share\kicad")


KICAD_SHARE = find_kicad_share()

SWITCH_LIB = ROOT / "third_party" / "key-switches.pretty"
SOLDERED_SWITCH_FP = "SW_Kailh_Choc_V1V2_THT_Hybrid"
HOTSWAP_SWITCH_FP = "SW_Kailh_Choc_V1V2_HotSwap_Hybrid"
X2_SWITCH_FP = "SW_Kailh_Choc_V1_HotSwap_THT"
X3_V2_SWITCH_FP = "SW_Choc_V2_Socket_MX_THT"
KC2_FP_LIB = ROOT / "third_party" / "kc2.pretty"
DIODE_LIB = KICAD_SHARE / "footprints" / "Diode_SMD.pretty"
DIODE_FP = "D_SOD-123"
X1_DIODE_LIB = KC2_FP_LIB
X1_DIODE_FP = "D_SOD123_HandSolder_14592018"
X1_DIODE_VALUE = "1N4148W_SOD123_DeviceMart_14592018"
X3_V2_DIODE_LIB = KC2_FP_LIB
X3_V2_DIODE_FP = "D_ES1B_SMA_HandSolder_C437840"
X3_V2_DIODE_VALUE = "ES1B_Jingdao_C437840_Eleparts9475342"
X3_V2_DIODE_PIN_MAPPING = {"1": "cathode_row", "2": "anode_switch"}
TACT_LIB = KC2_FP_LIB
TACT_FP = "SW_NW3_A06_B3_SMD"
MOUNT_LIB = KICAD_SHARE / "footprints" / "MountingHole.pretty"
MOUNT_FP = "MountingHole_2.2mm_M2"
X3_V2_MOUNT_LIB = KC2_FP_LIB
X3_V2_MOUNT_FP = "MH_M1.4_NPTH_1.60"
X3_V2_MOUNT_VALUE = "M1.4_NPTH_1.60"
REGISTRATION_LIB = KC2_FP_LIB
REGISTRATION_FP = "REG_NPTH_3.0"
BATTERY_LEAD_SLOT_LIB = KC2_FP_LIB
BATTERY_LEAD_SLOT_FP = "BAT_LEAD_NPTH_SLOT_3.6x2.2"
BATTERY_LEAD_SLOT_VALUE = "BAT_LEAD_NPTH_SLOT_3.6x2.2"
X3_V2_POWER_SWITCH_LIB = KC2_FP_LIB
X3_V2_POWER_SWITCH_FP = "SW_IMMS_12V_BSI10_THT"
X3_V2_POWER_SWITCH_VALUE = "IMMS-12V_BSI-10"
X3_V2_BATTERY_TERMINATION_LIB = KC2_FP_LIB
X3_V2_BATTERY_TERMINATION_FP = "BAT_2Pin_PTH_DirectSolder"
X3_V2_BATTERY_TERMINATION_VALUE = "301230_DIRECT_SOLDER"
X3_V2_BATTERY_BODY_LIB = KC2_FP_LIB
X3_V2_BATTERY_BODY_FP = "BAT_301230_30x12mm"
X3_V2_BATTERY_BODY_VALUE = "301230_3.7V_100mAh"
SIDE_MOUNT_UPPER_OFFSET_FROM_BOTTOM = 61.0
X3_H2_ADJACENT_UPPER_MOUNT_POINTS = {
    "left": (173.45, 66.50),
    "right": (225.8375, 66.20),
}
X3_BALANCED_SIDE_MOUNT_POINTS = {
    "left": [
        (39.50, 66.50),
        (170.50, 108.25),
    ],
    "right": [
        (39.00, 66.20),
        (42.00, 107.75),
        (39.00, 136.00),
    ],
}

UNIT = 19.05
GENERAL_MARGIN = 5.5
X3_GENERAL_MARGIN = 4.0
INNER_MARGIN = 2.8
X3_INNER_MARGIN_EXTRA = 0.8
X3_RIGHT_YH_HORIZONTAL_LEDGE_RELIEF = 0.8
X3_V2_KEYCELL_EDGE_INSET = 1.5
X3_V2_ONE_UNIT_JOIN_CENTER_TO_EDGE = UNIT / 2.0 - X3_V2_KEYCELL_EDGE_INSET
X3_V2_JOIN_KEYCAP_SETBACK = X3_V2_KEYCELL_EDGE_INSET - 0.5
X3_V2_JOIN_KEYCAP_GAP = 1.8
X3_V2_JOIN_PLACEMENT_OFFSET = 0.8
X3_V2_JOIN_CENTER_PITCH = UNIT + X3_V2_JOIN_PLACEMENT_OFFSET
X3_V2_ROW_CENTER_PCB_GAP = 3.8
X3_V2_MIN_JOINED_EDGE_CLEARANCE = 1.0
# Opposing stair transitions formerly occupied the same row-boundary Y and
# touched along horizontal Edge.Cuts.  Move the left transition upward and
# the right transition downward before corner rounding.
X3_V2_SEAM_TRANSITION_STAGGER = 0.55
X3_V2_TOP_SECOND_DIODE_OFFSET = (7.0, 7.0)
X3_V2_TOP_SECOND_DIODE_ROTATION = 90.0
X3_V2_TOP_OTHER_DIODE_OFFSET = (-8.75, -3.25)
X3_V2_TOP_OTHER_DIODE_ROTATION = 270.0
X3_V2_BOTTOM_FIRST_DIODE_OFFSET = (9.5, 3.25)
X3_V2_MIN_DIODE_EDGE_CLEARANCE = 1.30
X3_V2_OUTLINE_POLICY = "keycap_concealed_except_controller_service"
X3_V2_TOP_EDGE_Y_MM = 39.25
X3_V2_BOARD_DATUM_DY_MM = 68.0
X3_V2_CONTROLLER_Y_MM = 50.75
X3_V2_RESET_Y_MM = 63.45
X3_V2_POWER_Y_MM = 63.45
X3_V2_RESET_ROTATIONS_DEGREES = {"left": 0.0, "right": 180.0}
X3_V2_J_BAT1_ROTATIONS_DEGREES = {"left": 180.0, "right": 0.0}
X3_V2_J_BAT1_ASSEMBLY_MARKINGS = {
    "pad_1_marking": "B+",
    "pad_2_marking": "B-/GND",
    "nice_nano_equivalence": {
        "battery_positive": "U1 RAW / NN_B+",
        "battery_negative": "U1 GND_C / GND",
        "source": "https://nicekeyboards.com/docs/nice-nano/",
    },
}
X3_V2_BATTERY_SIZE_MM = (30.0, 12.0, 3.0)
X3_V2_POWER_SWITCH_BODY_SIZE_MM = (10.0, 2.5, 6.4)
X3_V2_POWER_SWITCH_ACTUATOR_TRAVEL_MM = 1.6
X3_V2_RESET_BODY_SIZE_MM = (6.1, 3.7)
X3_V2_RESET_KEYCAP_ENVELOPE_MM = 18.05
X3_V2_RESET_BODY_TO_KEYCAP_MIN_MM = 3.20
X3_V2_RESET_COURTYARD_TO_U1_SOCKET_COPPER_MIN_MM = 2.03
X3_V2_POWER_SWITCH_DATASHEET = (
    "https://amec-gmbh.de/wp-content/uploads/2022/11/BSI-10.pdf"
)
X3_V2_POWER_SWITCH_MODEL = (
    ROOT / "third_party/kc2.3dshapes/SW_IMMS_12V_BSI10_THT.step"
)
X3_V2_POWER_SWITCH_MODEL_GENERATOR = ROOT / "tools/generate_kc2_component_models.py"
X3_V2_REQUIREMENT_IDS = [
    "CON-ARCH-004",
    "CON-ARCH-006",
    "CON-ARCH-007",
    "REL-ARCH-001",
]
X3_V2_DEEP_SEA_SWITCH_IDENTITY = {
    "family": "Kailh Deep Sea low-profile / PG1353-family",
    "exact_mpn_status": "pending",
    "controlled_drawing_revision_status": "pending",
    "order_ready": False,
}
X3_V2_BATTERY_Y_MM = X3_V2_CONTROLLER_Y_MM
X3_V2_CONTROLLER_SERVICE_POSITIONS_MM = {
    "left": {
        "u1": (132.7125, X3_V2_CONTROLLER_Y_MM),
        "battery_slot": (117.9125, X3_V2_CONTROLLER_Y_MM),
        "battery": (131.7125, X3_V2_BATTERY_Y_MM),
        "j_bat": (115.8125, 59.40),
        "power": (115.8125, X3_V2_POWER_Y_MM),
        "reset": (126.0625, X3_V2_RESET_Y_MM),
    },
    "right": {
        "u1": (77.4000, X3_V2_CONTROLLER_Y_MM),
        "battery_slot": (92.2000, X3_V2_CONTROLLER_Y_MM),
        "battery": (78.4000, X3_V2_BATTERY_Y_MM),
        "j_bat": (94.3000, 59.40),
        "power": (94.3000, X3_V2_POWER_Y_MM),
        "reset": (84.0500, X3_V2_RESET_Y_MM),
    },
}
X3_V2_CONTROLLER_SERVICE_ROTATIONS_DEGREES = {
    "left": {
        "U1": 0.0,
        "BAT1": 0.0,
        "J_BAT1": X3_V2_J_BAT1_ROTATIONS_DEGREES["left"],
        "SW_PWR1": 0.0,
        "BAT_LEAD_SLOT1": 0.0,
        "SW_RST1": X3_V2_RESET_ROTATIONS_DEGREES["left"],
    },
    "right": {
        "U1": 0.0,
        "BAT1": 0.0,
        "J_BAT1": X3_V2_J_BAT1_ROTATIONS_DEGREES["right"],
        "SW_PWR1": 180.0,
        "BAT_LEAD_SLOT1": 0.0,
        "SW_RST1": X3_V2_RESET_ROTATIONS_DEGREES["right"],
    },
}
X3_V2_MATRIX_CONNECTIVITY_DETOURS = {
    "left": {
        "removals": (
            ("track", "L_COL0", "B.Cu", 131.4425, 58.3700, 132.1000, 60.0000, 0.250),
            ("track", "L_COL0", "B.Cu", 132.1000, 60.0000, 132.1000, 67.0000, 0.250),
            ("track", "L_COL0", "B.Cu", 132.1000, 67.0000, 117.9254, 71.8871, 0.250),
            ("via", "L_COL0", 117.9254, 71.8871, 0.600, 0.300),
            ("track", "L_COL1", "F.Cu", 135.1227, 59.7698, 132.0690, 59.7698, 0.250),
            ("track", "L_COL1", "B.Cu", 132.0690, 59.7698, 133.1000, 60.5000, 0.250),
            ("via", "L_COL1", 132.0690, 59.7698, 0.600, 0.300),
            ("track", "L_COL1", "B.Cu", 133.1000, 60.5000, 133.1000, 67.5000, 0.250),
            ("track", "L_COL1", "B.Cu", 133.1000, 67.5000, 119.2058, 72.6330, 0.250),
            ("via", "L_COL1", 119.2058, 72.6330, 0.600, 0.300),
        ),
        "additions": (
            ("track", "L_COL0", "B.Cu", 131.4425, 58.3700, 132.2000, 60.0000, 0.250),
            ("track", "L_COL0", "B.Cu", 132.2000, 60.0000, 132.2000, 66.5000, 0.250),
            ("track", "L_COL0", "B.Cu", 132.2000, 66.5000, 129.0000, 68.0000, 0.250),
            ("via", "L_COL0", 129.0000, 68.0000, 0.600, 0.300),
            ("track", "L_COL0", "F.Cu", 129.0000, 68.0000, 117.9254, 71.8871, 0.250),
            ("track", "L_COL1", "F.Cu", 135.1227, 59.7698, 136.5000, 59.4000, 0.250),
            ("via", "L_COL1", 136.5000, 59.4000, 0.600, 0.300),
            ("track", "L_COL1", "B.Cu", 136.5000, 59.4000, 136.5000, 68.5000, 0.250),
            ("track", "L_COL1", "B.Cu", 136.5000, 68.5000, 134.8000, 68.7000, 0.250),
            ("track", "L_COL1", "B.Cu", 134.8000, 68.7000, 132.0000, 69.1500, 0.250),
            ("track", "L_COL1", "B.Cu", 132.0000, 69.1500, 129.0000, 69.7500, 0.250),
            ("track", "L_COL1", "B.Cu", 129.0000, 69.7500, 128.5000, 70.0000, 0.250),
            ("via", "L_COL1", 128.5000, 70.0000, 0.600, 0.300),
            ("track", "L_COL1", "F.Cu", 128.5000, 70.0000, 125.6000, 70.5000, 0.250),
            ("track", "L_COL1", "F.Cu", 125.6000, 70.5000, 125.6000, 74.5000, 0.250),
            ("track", "L_COL1", "F.Cu", 125.6000, 74.5000, 119.5000, 74.5000, 0.250),
            ("track", "L_COL1", "F.Cu", 119.5000, 74.5000, 119.2058, 72.6330, 0.250),
        ),
    },
    "right": {
        "removals": (
            ("track", "R_COL5", "F.Cu", 73.5900, 58.3700, 83.1620, 67.9420, 0.250),
            ("track", "R_COL6", "F.Cu", 94.1212, 76.3612, 76.1300, 58.3700, 0.250),
            ("track", "R_COL7", "B.Cu", 90.9461, 59.9321, 82.7721, 59.9321, 0.250),
            ("track", "R_COL7", "B.Cu", 101.1625, 70.1485, 90.9461, 59.9321, 0.250),
            ("track", "R_COL2", "B.Cu", 71.2975, 63.6975, 84.4425, 63.6975, 0.250),
            ("track", "R_COL2", "B.Cu", 84.4425, 63.6975, 93.1900, 72.4450, 0.250),
            ("track", "R_COL3", "B.Cu", 71.8386, 61.6986, 90.4512, 61.6986, 0.250),
            ("track", "R_COL3", "B.Cu", 90.4512, 61.6986, 99.4528, 70.7002, 0.250),
            ("track", "R_ROW0", "F.Cu", 91.6389, 54.9233, 98.7624, 62.0468, 0.250),
            ("track", "R_ROW0", "F.Cu", 98.7624, 62.0468, 98.7624, 71.4811, 0.250),
            ("track", "R_ROW3", "F.Cu", 91.7219, 54.1770, 100.2000, 62.6551, 0.250),
        ),
        "additions": (
            ("track", "R_COL3", "B.Cu", 71.8386, 61.6986, 80.5000, 65.0000, 0.250),
            ("track", "R_COL3", "B.Cu", 80.5000, 65.0000, 99.4528, 70.7002, 0.250),
            ("track", "R_COL2", "B.Cu", 71.2975, 63.6975, 79.5000, 65.5000, 0.250),
            ("via", "R_COL2", 79.5000, 65.5000, 0.600, 0.300),
            ("track", "R_COL2", "F.Cu", 79.5000, 65.5000, 83.0000, 65.5000, 0.250),
            ("track", "R_COL2", "F.Cu", 83.0000, 65.5000, 86.0000, 68.5000, 0.250),
            ("via", "R_COL2", 86.0000, 68.5000, 0.600, 0.300),
            ("track", "R_COL2", "B.Cu", 86.0000, 68.5000, 90.5000, 70.5000, 0.250),
            ("via", "R_COL2", 90.5000, 70.5000, 0.600, 0.300),
            ("track", "R_COL2", "F.Cu", 90.5000, 70.5000, 93.1900, 72.4450, 0.250),
            ("track", "R_COL7", "B.Cu", 82.7721, 59.9321, 84.0000, 60.0000, 0.250),
            ("via", "R_COL7", 84.0000, 60.0000, 0.600, 0.300),
            ("track", "R_COL7", "F.Cu", 84.0000, 60.0000, 87.0000, 62.0000, 0.250),
            ("via", "R_COL7", 87.0000, 62.0000, 0.600, 0.300),
            ("track", "R_COL7", "B.Cu", 87.0000, 62.0000, 88.5000, 62.0000, 0.250),
            ("track", "R_COL7", "B.Cu", 88.5000, 62.0000, 92.0000, 65.5000, 0.250),
            ("track", "R_COL7", "B.Cu", 92.0000, 65.5000, 101.1625, 70.1485, 0.250),
            ("track", "R_COL6", "F.Cu", 76.1300, 58.3700, 85.0000, 65.0000, 0.250),
            ("track", "R_COL6", "F.Cu", 85.0000, 65.0000, 94.1212, 76.3612, 0.250),
            ("track", "R_COL5", "F.Cu", 73.5900, 58.3700, 73.5000, 59.5000, 0.250),
            ("via", "R_COL5", 73.5000, 59.5000, 0.600, 0.300),
            ("track", "R_COL5", "B.Cu", 73.5000, 59.5000, 72.5000, 61.0000, 0.250),
            ("via", "R_COL5", 72.5000, 61.0000, 0.600, 0.300),
            ("track", "R_COL5", "F.Cu", 72.5000, 61.0000, 77.5000, 66.0000, 0.250),
            ("via", "R_COL5", 77.5000, 66.0000, 0.600, 0.300),
            ("track", "R_COL5", "B.Cu", 77.5000, 66.0000, 82.0000, 67.5000, 0.250),
            ("via", "R_COL5", 82.0000, 67.5000, 0.600, 0.300),
            ("track", "R_COL5", "F.Cu", 82.0000, 67.5000, 83.1620, 67.9420, 0.250),
            ("track", "R_ROW0", "F.Cu", 91.6389, 54.9233, 98.0000, 55.0000, 0.250),
            ("via", "R_ROW0", 98.0000, 55.0000, 0.600, 0.300),
            ("track", "R_ROW0", "B.Cu", 98.0000, 55.0000, 98.5000, 60.5000, 0.250),
            ("track", "R_ROW0", "B.Cu", 98.5000, 60.5000, 98.5000, 67.5000, 0.250),
            ("via", "R_ROW0", 98.5000, 67.5000, 0.600, 0.300),
            ("track", "R_ROW0", "F.Cu", 98.5000, 67.5000, 98.7624, 71.4811, 0.250),
            ("track", "R_ROW3", "F.Cu", 91.7219, 54.1770, 92.5000, 54.2000, 0.250),
            ("track", "R_ROW3", "F.Cu", 92.5000, 54.2000, 100.2000, 54.2000, 0.250),
            ("track", "R_ROW3", "F.Cu", 100.2000, 54.2000, 100.2000, 62.6551, 0.250),
        ),
    },
}
X3_V2_RESET_ROUTE_POINTS_MM = {
    "left": {
        "RST": [
            (122.1875, 63.45),
            (122.1875, 67.0),
            (115.8, 67.0),
            (110.3, 67.0),
            (110.3, 60.0),
            (110.3, 53.0),
            (110.3, 46.0),
            (110.3, 40.5),
            (117.0, 40.5),
            (123.8225, 40.5),
            (123.8225, 43.13),
        ],
        "GND_F": [(129.9375, 63.45), (131.3, 63.45)],
        "GND_VIA": [(131.3, 63.45)],
        "GND_B": [
            (131.3, 63.45),
            (131.3, 65.8),
            (121.5, 65.8),
            (111.5, 65.8),
            (111.5, 60.0),
            (111.5, 54.0),
            (111.5, 47.0),
            (113.2725, 47.0),
        ],
    },
    "right": {
        "RST": [(87.925, 63.45), (87.925, 61.0), (86.29, 58.37)],
        "GND_F": [(80.175, 63.45), (78.8, 63.45)],
        "GND_VIA": [(78.8, 63.45)],
        "GND_B": [
            (78.8, 63.45),
            (78.8, 61.0),
            (87.56, 61.0),
            (88.83, 58.37),
        ],
    },
}
X3_V2_RESET_GND_ROUTE_ENDS_MM = {
    "left": (113.2725, 47.0),
    "right": (88.83, 58.37),
}
X3_V2_POWER_ROUTE_POINTS_MM = {
    "left": {
        "NN_B+": [
            (113.2725, 63.45),
            (111.3, 63.45),
            (111.3, 55.0),
            (111.3, 47.0),
            (118.7425, 43.13),
        ],
        "GND": [
            (113.2725, 59.4),
            (113.2725, 53.2),
            (113.2725, 47.0),
            (120.0125, 47.0),
            (121.2825, 43.13),
        ],
    },
    "right": {
        "NN_B+": [
            (96.84, 63.45),
            (98.8, 63.45),
            (98.8, 56.0),
            (91.37, 58.37),
        ],
        "GND": [
            (96.84, 59.4),
            (96.84, 54.5),
            (90.1, 54.5),
            (88.83, 58.37),
        ],
    },
}
X3_V2_MOUNT_HOLE_DIAMETER_MM = 1.60
X3_V2_MOUNT_HEAD_STYLE = "non_countersunk_rounded_pan_or_button"
X3_V2_MOUNT_HEAD_ENVELOPE_MM = (3.00, 1.20)
X3_V2_MOUNT_HEAD_XY_RESERVE_MM = 0.25
X3_V2_MOUNT_DRIVER_DIAMETER_MM = 3.00
X3_V2_MOUNT_SUPPORT_LAND_DIAMETER_MM = 3.00
X3_V2_MOUNT_PILOT_ENVELOPE_MM = (1.10, 2.80)
X3_V2_MOUNT_UNDER_HEAD_LENGTH_MM = 4.00
X3_V2_MOUNT_CLOSED_BOTTOM_MM = 0.70
X3_V2_MOUNT_REFERENCE_TEXT_SIZE_MM = 0.80
X3_V2_MOUNT_REFERENCE_STROKE_MM = 0.15
X3_V2_MOUNT_REFERENCE_OFFSET_MM = (0.0, -1.50)
X3_V2_MOUNTING_POINTS = {
    "left": [
        (112.8625, 43.0000),
        (144.1125, 66.2500),
        (38.6125, 111.0000),
        (63.6125, 123.0000),
        (81.1125, 151.7500),
        (137.3625, 153.5000),
        (166.3625, 148.7500),
        (75.0000, 134.0000),
    ],
    "right": [
        (97.1875, 43.2500),
        (72.4375, 67.0000),
        (169.9375, 95.2500),
        (194.9375, 98.7500),
        (156.1875, 112.5000),
        (69.9375, 146.2500),
        (97.4375, 152.0000),
        (122.6875, 151.0000),
        (177.5000, 118.0000),
    ],
}
EDGE_WIDTH = 0.10
TRACK_WIDTH = 0.25
POWER_TRACK_WIDTH = 0.75
VIA_SIZE = 0.60
VIA_DRILL = 0.30
DEFAULT_DIODE_Y_OFFSET = -6.8
X2_DIODE_Y_OFFSET = -7.6

CONTROLLER_LEN = 33.8
CONTROLLER_W = 18.3
# Keep the established placement datum above stable, but use the larger published
# nice!nano v2 plan envelope for collision and procurement evidence.  Nice!nano's
# official documentation is authoritative for the pinout; Mechboards publishes
# the 34.1 x 18.3 mm assembled-board dimensions pending first-article caliper data.
CONTROLLER_BODY_LEN_MAX = 34.1
CONTROLLER_BODY_SOURCE = {
    "kind": "retailer_published_dimensions_pending_physical_confirmation",
    "url": "https://mechboards.co.uk/products/nice-nano-v2",
}
CONTROLLER_PINOUT_SOURCE = "https://nicekeyboards.com/docs/nice-nano/pinout-schematic/"
# Pro Micro / nice!nano physical socket-row center spacing is 0.600 inch.
# 17.78 mm is the nominal controller board width and must not be used here.
SOCKET_ROW_SPACING = 15.24
PIN_PITCH = 2.54
PIN_COUNT = 12
PIN_SPAN = PIN_PITCH * (PIN_COUNT - 1)
CONTROLLER_TAB_W = 72.0
CONTROLLER_TAB_H = 28.0
CONTROLLER_CENTER_Y = -19.0
LEFT_CONTROLLER_JOIN_EDGE_RECESS = 12.0
RIGHT_CONTROLLER_JOIN_EDGE_RECESS = 17.0
X3_CONTROLLER_TAB_USB_SPAN = 23.5
X3_CONTROLLER_TAB_ANTENNA_SPAN = 19.0
X3_CONTROLLER_TAB_W = X3_CONTROLLER_TAB_USB_SPAN + X3_CONTROLLER_TAB_ANTENNA_SPAN
X3_CONTROLLER_TAB_INNER_SPAN = X3_CONTROLLER_TAB_ANTENNA_SPAN
X3_CONTROLLER_TAB_OUTER_SPAN = X3_CONTROLLER_TAB_USB_SPAN
X3_CONTROLLER_ANCHOR_INNER_SPAN = 30.5
X3_CONTROLLER_ANCHOR_OUTER_SPAN = X3_CONTROLLER_TAB_USB_SPAN
X3_TACT_BODY_W = 6.1
X3_TACT_BATTERY_CLEARANCE = 1.0
X3_BATTERY_CENTER_OFFSET_FROM_CONTROLLER = 0.5
ANTENNA_KEEP_START_FROM_CENTER = PIN_SPAN / 2.0 + 4.0
ANTENNA_KEEP_LENGTH = 10.0
MOUNT_HOLE_DIAMETER = 2.2
REGISTRATION_HOLE_DIAMETER = 3.0
REGISTRATION_TRACE_KEEP_OUT_RADIUS = 1.90
REGISTRATION_VALUE = "REG_NPTH_3.0"
BATTERY_LEAD_SLOT_LEN = 3.6
BATTERY_LEAD_SLOT_W = 2.2
BATTERY_LEAD_SLOT_KEEP_OUT_GAP = 0.30
ACTIVE_TRACE_KEEP_OUTS: list[tuple[float, float]] = []
EMBEDDED_FOOTPRINT_SOURCES = {
    SOLDERED_SWITCH_FP: DRAFT_ROOT / "soldered" / "kc2_left" / "kc2_left.kicad_pcb",
    HOTSWAP_SWITCH_FP: DRAFT_ROOT / "hotswap" / "kc2_left-hotswap" / "kc2_left-hotswap.kicad_pcb",
    X2_SWITCH_FP: DRAFT_ROOT / "x2" / "kc2_left-x2" / "kc2_left-x2.kicad_pcb",
}
_EMBEDDED_FOOTPRINT_CACHE: dict[str, pcbnew.FOOTPRINT] = {}
SUPPORTED_VARIANTS = ("soldered", "hotswap", "x1", "x2", "x3", "x3-v2")
X3_FAMILY_VARIANTS = frozenset({"x3", "x3-v2"})


def is_x3_family(variant: str) -> bool:
    return variant in X3_FAMILY_VARIANTS


def variant_output_dir(variant: str) -> Path:
    return KICAD_ROOT if variant == "x3" else DRAFT_ROOT / variant


def variant_project_suffix(variant: str) -> str:
    return "" if variant in {"soldered", "x3"} else f"-{variant}"


def variant_switch_footprint(variant: str) -> str:
    if variant == "x3-v2":
        return X3_V2_SWITCH_FP
    if variant in {"x2", "x3"}:
        return X2_SWITCH_FP
    if variant in {"hotswap", "x1"}:
        return HOTSWAP_SWITCH_FP
    if variant == "soldered":
        return SOLDERED_SWITCH_FP
    raise ValueError(f"Unknown variant: {variant}")


def variant_outline_margins(variant: str) -> dict[str, float]:
    if variant == "x3-v2":
        keycell_inset = -X3_V2_KEYCELL_EDGE_INSET
        return {
            "outer_mm": keycell_inset,
            "top_mm": keycell_inset,
            "bottom_mm": keycell_inset,
            "inner_mm": keycell_inset,
        }
    margin = X3_GENERAL_MARGIN if variant == "x3" else GENERAL_MARGIN
    inner = INNER_MARGIN + (X3_INNER_MARGIN_EXTRA if variant == "x3" else 0.0)
    return {
        "outer_mm": margin,
        "top_mm": margin,
        "bottom_mm": margin,
        "inner_mm": inner,
    }


@dataclass(frozen=True)
class Key:
    label: str
    row: int
    col: int
    x_u: float
    y_u: float
    w_u: float = 1.0
    h_u: float = 1.0

    @property
    def cx(self) -> float:
        return (self.x_u + self.w_u / 2.0) * UNIT

    @property
    def cy(self) -> float:
        return (self.y_u + self.h_u / 2.0) * UNIT

    @property
    def rect(self) -> tuple[float, float, float, float]:
        return (
            self.x_u * UNIT,
            self.y_u * UNIT,
            (self.x_u + self.w_u) * UNIT,
            (self.y_u + self.h_u) * UNIT,
        )


def mm(value: float) -> int:
    return pcbnew.FromMM(float(value))


def vxy(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(mm(x), mm(y))


def mask_only_layers() -> pcbnew.LSET:
    layers = pcbnew.LSET()
    layers.AddLayer(pcbnew.F_Mask)
    layers.AddLayer(pcbnew.B_Mask)
    return layers


def copper_layers() -> pcbnew.LSET:
    layers = pcbnew.LSET()
    layers.AddLayer(pcbnew.F_Cu)
    layers.AddLayer(pcbnew.B_Cu)
    return layers


def to_mm_vec(vec: pcbnew.VECTOR2I) -> tuple[float, float]:
    return pcbnew.ToMM(vec.x), pcbnew.ToMM(vec.y)


def add_net(board: pcbnew.BOARD, cache: dict[str, pcbnew.NETINFO_ITEM], name: str) -> pcbnew.NETINFO_ITEM:
    if name not in cache:
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
        cache[name] = net
    return cache[name]


def set_pad_net(fp: pcbnew.FOOTPRINT, pad_number: str, net: pcbnew.NETINFO_ITEM) -> None:
    for pad in fp.Pads():
        if pad.GetNumber() == pad_number:
            pad.SetNet(net)


def pad_positions(fp: pcbnew.FOOTPRINT, pad_number: str) -> list[tuple[float, float]]:
    return [to_mm_vec(pad.GetPosition()) for pad in fp.Pads() if pad.GetNumber() == pad_number]


def pad_positions_on_layer(fp: pcbnew.FOOTPRINT, pad_number: str, layer: int) -> list[tuple[float, float]]:
    return [
        to_mm_vec(pad.GetPosition())
        for pad in fp.Pads()
        if pad.GetNumber() == pad_number and pad.GetLayerSet().Contains(layer)
    ]


def pads_by_number(fp: pcbnew.FOOTPRINT, pad_number: str) -> list[pcbnew.PAD]:
    return [pad for pad in fp.Pads() if pad.GetNumber() == pad_number]


def convert_empty_switch_pads_to_npth(fp: pcbnew.FOOTPRINT) -> None:
    for pad in fp.Pads():
        if pad.GetNumber() == "":
            pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
            pad.SetNetCode(0)
            pad.SetLayerSet(mask_only_layers())


def add_track(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    start: tuple[float, float],
    end: tuple[float, float],
    layer: int,
    width: float = TRACK_WIDTH,
) -> None:
    if abs(start[0] - end[0]) < 0.001 and abs(start[1] - end[1]) < 0.001:
        return
    for seg_start, seg_end in split_segment_around_registration_keepouts(start, end):
        add_track_segment(board, net, seg_start, seg_end, layer, width)


def add_track_segment(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    start: tuple[float, float],
    end: tuple[float, float],
    layer: int,
    width: float = TRACK_WIDTH,
) -> None:
    if abs(start[0] - end[0]) < 0.001 and abs(start[1] - end[1]) < 0.001:
        return
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(vxy(*start))
    track.SetEnd(vxy(*end))
    track.SetLayer(layer)
    track.SetWidth(mm(width))
    track.SetNet(net)
    board.Add(track)


def add_via(board: pcbnew.BOARD, net: pcbnew.NETINFO_ITEM, at: tuple[float, float]) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(vxy(*at))
    via.SetWidth(mm(VIA_SIZE))
    via.SetDrill(mm(VIA_DRILL))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(net)
    board.Add(via)


def split_segment_around_registration_keepouts(
    start: tuple[float, float],
    end: tuple[float, float],
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    if not ACTIVE_TRACE_KEEP_OUTS:
        return [(start, end)]

    radius = REGISTRATION_TRACE_KEEP_OUT_RADIUS
    segments = [(start, end)]
    for hole_x, hole_y in ACTIVE_TRACE_KEEP_OUTS:
        next_segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
        for seg_start, seg_end in segments:
            sx, sy = seg_start
            ex, ey = seg_end
            if abs(sy - ey) < 0.001:
                y = sy
                min_x, max_x = sorted((sx, ex))
                if abs(y - hole_y) >= radius or max_x <= hole_x - radius or min_x >= hole_x + radius:
                    next_segments.append((seg_start, seg_end))
                    continue
                direction = 1.0 if ex >= sx else -1.0
                entry_x = hole_x - direction * radius
                exit_x = hole_x + direction * radius
                jog_y = hole_y - radius if y <= hole_y else hole_y + radius
                entry = (entry_x, y)
                exit = (exit_x, y)
                entry_jog = (entry_x, jog_y)
                exit_jog = (exit_x, jog_y)
                next_segments.extend([(seg_start, entry), (entry, entry_jog), (entry_jog, exit_jog), (exit_jog, exit), (exit, seg_end)])
                continue
            if abs(sx - ex) < 0.001:
                x = sx
                min_y, max_y = sorted((sy, ey))
                if abs(x - hole_x) >= radius or max_y <= hole_y - radius or min_y >= hole_y + radius:
                    next_segments.append((seg_start, seg_end))
                    continue
                direction = 1.0 if ey >= sy else -1.0
                entry_y = hole_y - direction * radius
                exit_y = hole_y + direction * radius
                jog_x = hole_x - radius if x <= hole_x else hole_x + radius
                entry = (x, entry_y)
                exit = (x, exit_y)
                entry_jog = (jog_x, entry_y)
                exit_jog = (jog_x, exit_y)
                next_segments.extend([(seg_start, entry), (entry, entry_jog), (entry_jog, exit_jog), (exit_jog, exit), (exit, seg_end)])
                continue
            next_segments.append((seg_start, seg_end))
        segments = next_segments
    return segments


def add_polyline(
    board: pcbnew.BOARD,
    points: list[tuple[float, float]],
    layer: int,
    width: float = EDGE_WIDTH,
    closed: bool = False,
) -> None:
    if closed:
        points = points + [points[0]]
    for start, end in zip(points, points[1:]):
        shape = pcbnew.PCB_SHAPE(board)
        shape.SetShape(pcbnew.SHAPE_T_SEGMENT)
        shape.SetStart(vxy(*start))
        shape.SetEnd(vxy(*end))
        shape.SetLayer(layer)
        shape.SetWidth(mm(width))
        board.Add(shape)


def add_rect_lines(
    board: pcbnew.BOARD,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    layer: int,
    width: float = 0.12,
) -> None:
    add_polyline(board, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], layer, width, closed=True)


def add_board_text(
    board: pcbnew.BOARD,
    text: str,
    x: float,
    y: float,
    layer: int = pcbnew.F_SilkS,
    size: float = 1.2,
    thickness: float = 0.15,
    angle_deg: float = 0.0,
    mirrored: bool = False,
) -> None:
    item = pcbnew.PCB_TEXT(board)
    item.SetText(text)
    item.SetPosition(vxy(x, y))
    item.SetLayer(layer)
    item.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    item.SetTextThickness(mm(thickness))
    item.SetTextAngleDegrees(angle_deg)
    item.SetMirrored(mirrored)
    board.Add(item)


def registration_label_position(
    board: pcbnew.BOARD,
    hole_x: float,
    hole_y: float,
) -> tuple[float, float]:
    candidates = (
        (2.7, -2.7),
        (2.7, 2.7),
        (-2.7, -2.7),
        (-2.7, 2.7),
        (0.0, -3.4),
        (0.0, 3.4),
        (3.4, 0.0),
        (-3.4, 0.0),
    )
    mask_boxes = [
        pad.GetBoundingBox()
        for footprint in board.GetFootprints()
        for pad in footprint.Pads()
        if pad.IsOnLayer(pcbnew.B_Mask)
    ]
    for dx, dy in candidates:
        x = hole_x + dx
        y = hole_y + dy
        left, top, right, bottom = x - 0.95, y - 0.55, x + 0.95, y + 0.55
        blocked = any(
            left < pcbnew.ToMM(box.GetX() + box.GetWidth()) + 0.10
            and right > pcbnew.ToMM(box.GetX()) - 0.10
            and top < pcbnew.ToMM(box.GetY() + box.GetHeight()) + 0.10
            and bottom > pcbnew.ToMM(box.GetY()) - 0.10
            for box in mask_boxes
        )
        if not blocked:
            return x, y
    raise RuntimeError(f"No B.Silkscreen label position near REG hole ({hole_x}, {hole_y})")


def add_product_identity_text(
    board: pcbnew.BOARD,
    side: str,
    outline: list[tuple[float, float]],
    variant: str,
) -> None:
    if not is_x3_family(variant):
        return
    min_x = min(x for x, _ in outline)
    max_x = max(x for x, _ in outline)
    max_y = max(y for _, y in outline)
    add_board_text(
        board,
        f"KC2 {'X3 V2' if variant == 'x3-v2' else 'v1.0'} {side[0].upper()}",
        (min_x + max_x) / 2.0,
        max_y - 4.25,
        pcbnew.B_Fab if variant == "x3-v2" else pcbnew.B_SilkS,
        1.4,
        0.16,
        mirrored=True,
    )


def load_footprint(
    board: pcbnew.BOARD,
    lib: Path,
    name: str,
    ref: str,
    value: str,
    x: float,
    y: float,
    rotation: float = 0.0,
    bottom: bool = False,
) -> pcbnew.FOOTPRINT:
    try:
        fp = pcbnew.FootprintLoad(str(lib), name)
    except (AttributeError, RuntimeError):
        fp = None
    if fp is None:
        fp = load_embedded_footprint(name)
    if fp is None:
        raise RuntimeError(f"Failed to load footprint {lib}:{name}")
    fp.SetReference(ref)
    fp.SetValue(value)
    fp.SetPosition(vxy(x, y))
    fp.SetOrientationDegrees(rotation)
    board.Add(fp)
    if bottom:
        fp.Flip(fp.GetPosition(), False)
    return fp


def assign_footprint_pad_nets(
    board: pcbnew.BOARD,
    nets: dict[str, pcbnew.NETINFO_ITEM],
    footprint: pcbnew.FOOTPRINT,
    pad_net_names: dict[str, str | None],
) -> dict[str, tuple[float, float]]:
    positions: dict[str, tuple[float, float]] = {}
    for pad in footprint.Pads():
        number = pad.GetNumber()
        if number not in pad_net_names:
            continue
        net_name = pad_net_names[number]
        if net_name:
            pad.SetNet(add_net(board, nets, net_name))
        else:
            pad.SetNetCode(0)
        positions[number] = to_mm_vec(pad.GetPosition())
    missing = set(pad_net_names) - set(positions)
    if missing:
        raise RuntimeError(
            f"{footprint.GetReference()} is missing pads required by its net contract: "
            + ", ".join(sorted(missing))
        )
    return positions


def load_embedded_footprint(name: str) -> pcbnew.FOOTPRINT | None:
    template = preload_embedded_footprint(name)
    if template is None:
        return None
    return pcbnew.FOOTPRINT.Cast(template.Duplicate(False))


def preload_embedded_footprint(name: str) -> pcbnew.FOOTPRINT | None:
    source_path = EMBEDDED_FOOTPRINT_SOURCES.get(name)
    if source_path is None:
        return None
    template = _EMBEDDED_FOOTPRINT_CACHE.get(name)
    if template is None:
        if not source_path.exists():
            return None
        source_board = pcbnew.LoadBoard(str(source_path))
        for source_fp in source_board.GetFootprints():
            if source_fp.GetFPID().GetLibItemName() == name:
                template = pcbnew.FOOTPRINT.Cast(source_fp.Duplicate(False))
                break
        if template is None:
            return None
        _EMBEDDED_FOOTPRINT_CACHE[name] = template
    return template


def make_left_keys() -> list[Key]:
    rows = [
        [("~", 1.0), ("1", 1.0), ("2", 1.0), ("3", 1.0), ("4", 1.0), ("5", 1.0), ("6", 1.0)],
        [("TAB", 1.5), ("Q", 1.0), ("W", 1.0), ("E", 1.0), ("R", 1.0), ("T", 1.0)],
        [("Caps", 1.75), ("A", 1.0), ("S", 1.0), ("D", 1.0), ("F", 1.0), ("G", 1.0)],
        [("Shift", 2.25), ("Z", 1.0), ("X", 1.0), ("C", 1.0), ("V", 1.0), ("B", 1.0)],
        [("Ctrl", 1.25), ("Win", 1.25), ("Alt", 1.25), ("Fn", 1.25), ("Space", 2.25)],
    ]
    keys: list[Key] = []
    for row_idx, row in enumerate(rows):
        x = 0.0
        for col_idx, (label, width) in enumerate(row):
            keys.append(Key(label, row_idx, col_idx, x, float(row_idx), width))
            x += width
    return keys


def make_left_keys_no_stab() -> list[Key]:
    rows = [
        [("~", 1.0), ("1", 1.0), ("2", 1.0), ("3", 1.0), ("4", 1.0), ("5", 1.0), ("6", 1.0)],
        [("TAB", 1.5), ("Q", 1.0), ("W", 1.0), ("E", 1.0), ("R", 1.0), ("T", 1.0)],
        [("Caps", 1.75), ("A", 1.0), ("S", 1.0), ("D", 1.0), ("F", 1.0), ("G", 1.0)],
        [("LShift", 1.25), ("LShift", 1.0), ("Z", 1.0), ("X", 1.0), ("C", 1.0), ("V", 1.0), ("B", 1.0)],
        [("Ctrl", 1.25), ("Win", 1.25), ("Alt", 1.25), ("Fn", 1.25), ("Space", 1.0), ("Space", 1.25)],
    ]
    keys: list[Key] = []
    for row_idx, row in enumerate(rows):
        x = 0.0
        for col_idx, (label, width) in enumerate(row):
            keys.append(Key(label, row_idx, col_idx, x, float(row_idx), width))
            x += width
    return keys


def make_left_keys_x3_v2() -> list[Key]:
    rows = [
        [("~", 1.0), ("1", 1.0), ("2", 1.0), ("3", 1.0), ("4", 1.0), ("5", 1.0), ("6", 1.0)],
        [("TAB", 1.5), ("Q", 1.0), ("W", 1.0), ("E", 1.0), ("R", 1.0), ("T", 1.0)],
        [("Caps", 1.75), ("A", 1.0), ("S", 1.0), ("D", 1.0), ("F", 1.0), ("G", 1.0)],
        [("LShift", 1.0), ("LShift", 1.25), ("Z", 1.0), ("X", 1.0), ("C", 1.0), ("V", 1.0), ("B", 1.0)],
        [("Ctrl", 1.25), ("Fn", 1.25), ("Alt", 1.25), ("Space", 1.75), ("Space", 1.75)],
    ]
    keys: list[Key] = []
    for row_idx, row in enumerate(rows):
        x = 0.0
        for col_idx, (label, width) in enumerate(row):
            keys.append(Key(label, row_idx, col_idx, x, float(row_idx), width))
            x += width
    return keys


def make_right_keys() -> list[Key]:
    rows = [
        (0.50, [("7", 1.0), ("8", 1.0), ("9", 1.0), ("0", 1.0), ("-", 1.0), ("=", 1.0), ("BSPC", 2.25), ("DEL", 1.0)]),
        (0.00, [("Y", 1.0), ("U", 1.0), ("I", 1.0), ("O", 1.0), ("P", 1.0), ("[", 1.0), ("]", 1.0), ("\\", 1.75), ("Home", 1.0)]),
        (0.25, [("H", 1.0), ("J", 1.0), ("K", 1.0), ("L", 1.0), (";", 1.0), ("'", 1.0), ("Enter", 2.5), ("PgUp", 1.0)]),
        (0.75, [("N", 1.0), ("M", 1.0), (",", 1.0), (".", 1.0), ("/", 1.0), ("RShift", 2.0), ("Up", 1.0), ("PgDn", 1.0)]),
        (0.75, [("B_RH", 1.0), ("Space", 2.0), ("RAlt", 1.0), ("Fn", 1.0), ("RCtrl", 1.0), ("Left", 1.0), ("Down", 1.0), ("Right", 1.0)]),
    ]
    keys: list[Key] = []
    for row_idx, (x0, row) in enumerate(rows):
        x = x0
        for col_idx, (label, width) in enumerate(row):
            keys.append(Key(label, row_idx, col_idx, x, float(row_idx), width))
            x += width
    return keys


def make_right_keys_no_stab() -> list[Key]:
    rows = [
        (0.50, [("7", 1.0), ("8", 1.0), ("9", 1.0), ("0", 1.0), ("-", 1.0), ("=", 1.0), ("BSPC", 1.0), ("BSPC", 1.25), ("Del", 1.0)]),
        (0.00, [("Y", 1.0), ("U", 1.0), ("I", 1.0), ("O", 1.0), ("P", 1.0), ("[", 1.0), ("]", 1.0), ("\\", 1.75), ("Home", 1.0)]),
        (0.25, [("H", 1.0), ("J", 1.0), ("K", 1.0), ("L", 1.0), (";", 1.0), ("'", 1.0), ("Enter", 1.0), ("Enter", 1.5), ("PgUp", 1.0)]),
        (0.75, [("N", 1.0), ("M", 1.0), (",", 1.0), (".", 1.0), ("/", 1.0), ("RShift", 1.0), ("Fn", 1.0), ("Up", 1.0), ("PgDn", 1.0)]),
        (0.75, [("B", 1.0), ("Space", 1.0), ("Space", 1.0), ("RAlt", 1.0), ("Fn", 1.0), ("RCtrl", 1.0), ("Left", 1.0), ("Down", 1.0), ("Right", 1.0)]),
    ]
    keys: list[Key] = []
    for row_idx, (x0, row) in enumerate(rows):
        x = x0
        for col_idx, (label, width) in enumerate(row):
            keys.append(Key(label, row_idx, col_idx, x, float(row_idx), width))
            x += width
    return keys


def make_right_keys_x3_v2() -> list[Key]:
    rows = [
        (0.50, [("7", 1.0), ("8", 1.0), ("9", 1.0), ("0", 1.0), ("-", 1.0), ("=", 1.0), ("BSPC", 1.25), ("Del", 1.0)]),
        (0.00, [("Y", 1.0), ("U", 1.0), ("I", 1.0), ("O", 1.0), ("P", 1.0), ("[", 1.0), ("]", 1.0), ("\\", 1.75)]),
        (0.25, [("H", 1.0), ("J", 1.0), ("K", 1.0), ("L", 1.0), (";", 1.0), ("'", 1.0), ("Enter", 1.5), ("Enter", 1.0)]),
        (0.75, [("N", 1.0), ("M", 1.0), (",", 1.0), (".", 1.0), ("/", 1.0), ("RShift", 1.0), ("Up", 1.0), ("Fn", 1.0)]),
        (0.75, [("B", 1.0), ("Space", 1.75), ("RAlt", 1.25), ("RCtrl", 1.0), ("Left", 1.0), ("Down", 1.0), ("Right", 1.0)]),
    ]
    keys: list[Key] = []
    for row_idx, (x0, row) in enumerate(rows):
        x = x0
        for col_idx, (label, width) in enumerate(row):
            keys.append(Key(label, row_idx, col_idx, x, float(row_idx), width))
            x += width
    return keys


def x3_v2_join_geometry_by_row() -> list[dict[str, object]]:
    left_keys = make_left_keys_x3_v2()
    right_keys = make_right_keys_x3_v2()
    geometry: list[dict[str, object]] = []
    for row in sorted({key.row for key in left_keys} & {key.row for key in right_keys}):
        left_key = max(
            (key for key in left_keys if key.row == row),
            key=lambda key: key.x_u + key.w_u,
        )
        right_key = min(
            (key for key in right_keys if key.row == row),
            key=lambda key: key.x_u,
        )
        left_cap_width = left_key.w_u * UNIT - 1.0
        right_cap_width = right_key.w_u * UNIT - 1.0
        left_center_to_edge = left_key.w_u * UNIT / 2.0 - X3_V2_KEYCELL_EDGE_INSET
        right_center_to_edge = right_key.w_u * UNIT / 2.0 - X3_V2_KEYCELL_EDGE_INSET
        center_pitch = left_cap_width / 2.0 + right_cap_width / 2.0 + X3_V2_JOIN_KEYCAP_GAP
        geometry.append(
            {
                "row": row,
                "left_key": left_key.label,
                "right_key": right_key.label,
                "left_cap_width_mm": round(left_cap_width, 5),
                "right_cap_width_mm": round(right_cap_width, 5),
                "left_center_to_edge_mm": round(left_center_to_edge, 5),
                "right_center_to_edge_mm": round(right_center_to_edge, 5),
                "center_pitch_mm": round(center_pitch, 5),
                "cap_gap_mm": X3_V2_JOIN_KEYCAP_GAP,
                "pcb_gap_mm": round(center_pitch - left_center_to_edge - right_center_to_edge, 5),
            }
        )
    return geometry


def row_extents(keys: list[Key]) -> dict[int, tuple[float, float, float, float]]:
    out: dict[int, tuple[float, float, float, float]] = {}
    for row in sorted({k.row for k in keys}):
        rects = [k.rect for k in keys if k.row == row]
        out[row] = (
            min(r[0] for r in rects),
            min(r[1] for r in rects),
            max(r[2] for r in rects),
            max(r[3] for r in rects),
        )
    return out


def switch_rotation_for_key(key: Key, keys: list[Key], variant: str) -> float:
    """Turn V2's asymmetric Choc socket pad away from each left board edge."""
    if variant != "x3-v2":
        return 0.0
    row_left = min(candidate.cx for candidate in keys if candidate.row == key.row)
    return 180.0 if abs(key.cx - row_left) < 0.001 else 0.0


def diode_placement_for_key(
    key: Key,
    keys: list[Key],
    variant: str,
    default_y_offset: float = DEFAULT_DIODE_Y_OFFSET,
) -> tuple[float, float, float]:
    """Return a diode offset/rotation with an open hand-solder approach.

    V2 puts the exact ES1B SMA land in a verified hand-solder corner.
    This moves both manufacturer-recommended pads away from the hybrid
    footprint's unused NPTH features and MX solder pins.
    """
    if variant != "x3-v2":
        return 0.0, default_y_offset, 0.0
    dx, dy = (
        (7.0, 7.0)
        if switch_rotation_for_key(key, keys, variant) == 180.0
        else (-7.0, -7.0)
    )
    rotation = 0.0
    if key.row == 0 and key.col == 1:
        dx, dy = X3_V2_TOP_SECOND_DIODE_OFFSET
        rotation = X3_V2_TOP_SECOND_DIODE_ROTATION
    elif key.row == 0 and dy < 0:
        dx, dy = X3_V2_TOP_OTHER_DIODE_OFFSET
        rotation = X3_V2_TOP_OTHER_DIODE_ROTATION
    elif key.row == max(candidate.row for candidate in keys) and key.col == 0:
        dx, dy = X3_V2_BOTTOM_FIRST_DIODE_OFFSET
    return dx, dy, rotation


def controller_tab_spans(side: str, variant: str) -> tuple[float, float]:
    if is_x3_family(variant):
        if side == "left":
            return X3_CONTROLLER_TAB_OUTER_SPAN, X3_CONTROLLER_TAB_INNER_SPAN
        if side == "right":
            return X3_CONTROLLER_TAB_INNER_SPAN, X3_CONTROLLER_TAB_OUTER_SPAN
    half = CONTROLLER_TAB_W / 2.0
    return half, half


def controller_anchor_spans(side: str, variant: str) -> tuple[float, float]:
    if is_x3_family(variant):
        if side == "left":
            return X3_CONTROLLER_ANCHOR_OUTER_SPAN, X3_CONTROLLER_ANCHOR_INNER_SPAN
        if side == "right":
            return X3_CONTROLLER_ANCHOR_INNER_SPAN, X3_CONTROLLER_ANCHOR_OUTER_SPAN
    return controller_tab_spans(side, variant)


def controller_center_x(keys: list[Key], side: str, variant: str = "soldered") -> float:
    ext = row_extents(keys)
    inner_margin = INNER_MARGIN + (X3_INNER_MARGIN_EXTRA if is_x3_family(variant) else 0.0)
    left_span, right_span = controller_anchor_spans(side, variant)
    if side == "left":
        inner_edge = max(r[2] for r in ext.values()) + inner_margin
        tab_right = inner_edge - LEFT_CONTROLLER_JOIN_EDGE_RECESS
        return tab_right - right_span
    if side == "right":
        inner_edge = min(r[0] for r in ext.values()) - inner_margin
        tab_left = inner_edge + RIGHT_CONTROLLER_JOIN_EDGE_RECESS
        return tab_left + left_span
    raise ValueError(f"Unknown side: {side}")


def raw_outline(
    keys: list[Key],
    side: str,
    ctrl_cx: float,
    variant: str = "soldered",
    top_margin_extra: float = 0.0,
    inner_margin_extra: float = 0.0,
    general_margin: float = GENERAL_MARGIN,
) -> list[tuple[float, float]]:
    ext = row_extents(keys)
    rows = sorted(ext)
    left_margin = INNER_MARGIN + inner_margin_extra if side == "right" else general_margin
    right_margin = INNER_MARGIN + inner_margin_extra if side == "left" else general_margin

    lefts = {r: ext[r][0] - left_margin for r in rows}
    rights = {r: ext[r][2] + right_margin for r in rows}
    top_y = min(ext[r][1] for r in rows) - general_margin - top_margin_extra
    bottom_y = max(ext[r][3] for r in rows) + general_margin

    tab_left_span, tab_right_span = controller_tab_spans(side, variant)
    tab_left = ctrl_cx - tab_left_span
    tab_right = ctrl_cx + tab_right_span
    tab_top = (
        X3_V2_TOP_EDGE_Y_MM - X3_V2_BOARD_DATUM_DY_MM
        if variant == "x3-v2"
        else CONTROLLER_CENTER_Y - CONTROLLER_TAB_H / 2.0
    )

    r0 = rows[0]
    top_start = min(lefts[r0], tab_left)

    pts: list[tuple[float, float]] = []
    pts.append((top_start, top_y))
    if tab_left > top_start:
        pts.append((tab_left, top_y))
    pts.extend([(tab_left, tab_top), (tab_right, tab_top), (tab_right, top_y)])
    pts.append((rights[r0], top_y))

    for r in rows:
        # A negative bezel margin intentionally moves the perimeter under the
        # keycap.  Clamp the first/last row transitions to that inset instead
        # of walking out to the switch-cell boundary and then reversing back;
        # the latter creates a self-intersecting Edge.Cuts contour.
        nxt = r + 1
        y_bottom = min(ext[r][3], bottom_y)
        transition_y = y_bottom
        if variant == "x3-v2" and side == "left" and nxt in rights:
            seam_delta = rights[nxt] - rights[r]
            transition_y += math.copysign(X3_V2_SEAM_TRANSITION_STAGGER, seam_delta)
        pts.append((rights[r], transition_y))
        if nxt in rights:
            pts.append((rights[nxt], transition_y))
    pts.append((rights[rows[-1]], bottom_y))
    pts.append((lefts[rows[-1]], bottom_y))

    for r in reversed(rows):
        y_top = max(ext[r][1], top_y)
        prv = r - 1
        transition_y = y_top
        if variant == "x3-v2" and side == "right" and prv in lefts:
            seam_delta = lefts[r] - lefts[prv]
            transition_y -= math.copysign(X3_V2_SEAM_TRANSITION_STAGGER, seam_delta)
        pts.append((lefts[r], transition_y))
        if prv in lefts:
            pts.append((lefts[prv], transition_y))

    return remove_duplicate_points(pts)


def remove_duplicate_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for p in points:
        if not out or abs(out[-1][0] - p[0]) > 0.001 or abs(out[-1][1] - p[1]) > 0.001:
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < 0.001 and abs(out[0][1] - out[-1][1]) < 0.001:
        out.pop()
    return out


def rounded_polygon(points: list[tuple[float, float]], radius: float = 2.0, steps: int = 5) -> list[tuple[float, float]]:
    rounded: list[tuple[float, float]] = []
    n = len(points)
    for i, p in enumerate(points):
        prev = points[(i - 1) % n]
        nxt = points[(i + 1) % n]
        vin = (p[0] - prev[0], p[1] - prev[1])
        vout = (nxt[0] - p[0], nxt[1] - p[1])
        lin = math.hypot(*vin)
        lout = math.hypot(*vout)
        if lin < 0.001 or lout < 0.001:
            continue
        d = min(radius, lin * 0.45, lout * 0.45)
        p1 = (p[0] - vin[0] / lin * d, p[1] - vin[1] / lin * d)
        p2 = (p[0] + vout[0] / lout * d, p[1] + vout[1] / lout * d)
        # Quadratic trim is not a mathematically exact fillet, but it gives a
        # dense rounded Edge.Cuts contour without introducing arc-direction risk.
        for s in range(steps + 1):
            t = s / steps
            qx = (1 - t) * (1 - t) * p1[0] + 2 * (1 - t) * t * p[0] + t * t * p2[0]
            qy = (1 - t) * (1 - t) * p1[1] + 2 * (1 - t) * t * p[1] + t * t * p2[1]
            rounded.append((qx, qy))
    return remove_duplicate_points(rounded)


def x3_right_horizontal_ledge_relief(
    points: list[tuple[float, float]],
    keys: list[Key],
    radius: float = 2.0,
) -> list[tuple[float, float]]:
    ext = row_extents(keys)
    left_margin = INNER_MARGIN + X3_INNER_MARGIN_EXTRA
    lefts = {row: bounds[0] - left_margin for row, bounds in ext.items()}
    target_points = {
        (lefts[1] + radius, ext[0][3]),
        (lefts[1] + radius, ext[1][3]),
        (lefts[2] + radius, ext[1][3]),
        (lefts[2] + radius, ext[2][3]),
    }

    relieved: list[tuple[float, float]] = []
    for x, y in points:
        nx = x
        if any(abs(x - tx) < 0.001 and abs(y - ty) < 0.001 for tx, ty in target_points):
            nx = x + X3_RIGHT_YH_HORIZONTAL_LEDGE_RELIEF
        relieved.append((nx, y))
    return remove_duplicate_points(relieved)


def shift_points(points: list[tuple[float, float]], dx: float, dy: float) -> list[tuple[float, float]]:
    return [(x + dx, y + dy) for x, y in points]


def make_project_file(project_dir: Path, name: str, variant: str = "soldered") -> None:
    default_clearance = 0.30 if variant == "x3-v2" else 0.20
    net_classes = [
        {
            "name": "Default",
            "bus_width": 12.0,
            "clearance": default_clearance,
            "diff_pair_gap": 0.25,
            "diff_pair_via_gap": 0.25,
            "diff_pair_width": 0.20,
            "line_style": 0,
            "microvia_diameter": 0.30,
            "microvia_drill": 0.10,
            "pcb_color": "rgba(0, 0, 0, 0.000)",
            "schematic_color": "rgba(0, 0, 0, 0.000)",
            "track_width": TRACK_WIDTH,
            "via_diameter": VIA_SIZE,
            "via_drill": VIA_DRILL,
            "wire_width": 6.0,
        },
    ]
    netclass_assignments: list[dict[str, str]] = []
    if not is_x3_family(variant):
        net_classes.append(
            {
                "name": "Power",
                "bus_width": 12.0,
                "clearance": 0.20,
                "diff_pair_gap": 0.25,
                "diff_pair_via_gap": 0.25,
                "diff_pair_width": 0.20,
                "line_style": 0,
                "microvia_diameter": 0.30,
                "microvia_drill": 0.10,
                "pcb_color": "rgba(0, 0, 0, 0.000)",
                "schematic_color": "rgba(0, 0, 0, 0.000)",
                "track_width": POWER_TRACK_WIDTH,
                "via_diameter": 0.8,
                "via_drill": 0.4,
                "wire_width": 6.0,
            }
        )
        netclass_assignments = [
            {"netclass": "Power", "pattern": "BAT+"},
            {"netclass": "Power", "pattern": "BAT-"},
            {"netclass": "Power", "pattern": "NN_B+"},
            {"netclass": "Power", "pattern": "NN_B-"},
        ]
    data = {
        "board": {
            "design_settings": {
                "defaults": {
                    "board_outline_line_width": 0.05,
                    "copper_line_width": TRACK_WIDTH,
                    "silk_line_width": 0.1,
                    "track_width": TRACK_WIDTH,
                    "via_diameter": VIA_SIZE,
                    "via_drill": VIA_DRILL,
                    "zones": {"min_clearance": 0.2},
                },
                "rule_severities": {
                    "courtyards_overlap": "warning",
                    "silk_over_copper": "warning",
                    "silk_edge_clearance": "warning",
                    **(
                        {}
                        if variant == "x3-v2"
                        else {
                            "npth_inside_courtyard": "ignore",
                            "pth_inside_courtyard": "ignore",
                        }
                    ),
                },
                "rules": {
                    "min_clearance": 0.20,
                    "min_hole_clearance": 0.25,
                    "min_through_hole_diameter": 0.30,
                    "min_track_width": 0.15,
                    "min_via_diameter": 0.45,
                    "min_via_drill": 0.20,
                },
            }
        },
        "boards": [],
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": f"{name}.kicad_pro", "version": 1},
        "net_settings": {
            "classes": net_classes,
            "meta": {"version": 3},
            "net_colors": None,
            "netclass_assignments": netclass_assignments,
        },
        "project": {"files": []},
        "schematic": {},
        "sheets": [],
        "text_variables": {},
    }
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / f"{name}.kicad_pro").write_text(json.dumps(data, indent=2), encoding="utf-8")


def footprint_lib_uri(project_dir: Path, lib_path: Path) -> str:
    rel = Path(os.path.relpath(lib_path.resolve(), project_dir.resolve()))
    return "${KIPRJMOD}/" + rel.as_posix()


def make_fp_lib_table(project_dir: Path, include_switch_lib: bool = True) -> None:
    switch_rel = footprint_lib_uri(project_dir, SWITCH_LIB)
    kc2_rel = footprint_lib_uri(project_dir, KC2_FP_LIB)
    lines = ["(fp_lib_table"]
    if include_switch_lib:
        lines.append(
            f"\t(lib (name \"key-switches\")(type \"KiCad\")(uri \"{switch_rel}\")(options \"\")(descr \"Third-party keyboard switch footprints, CERN-OHL-P v2\"))"
        )
    lines.append(f"\t(lib (name \"KC2\")(type \"KiCad\")(uri \"{kc2_rel}\")(options \"\")(descr \"KC2 local footprints\"))")
    lines.append(")")
    content = "\n".join(lines) + "\n"
    (project_dir / "fp-lib-table").write_text(content, encoding="utf-8")


def add_antenna_keepout_zone(
    board: pcbnew.BOARD,
    side: str,
    keepout: tuple[float, float, float, float],
) -> None:
    x1, y1, x2, y2 = keepout
    chain = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
        chain.Append(vxy(x, y))
    chain.SetClosed(True)

    zone = pcbnew.ZONE(board)
    zone.SetZoneName(f"{side.upper()}_ANTENNA_10MM_NO_COPPER_TRACE_VIA")
    zone.SetNetCode(0)
    zone.SetLayerSet(copper_layers())
    zone.SetIsRuleArea(True)
    zone.SetMinThickness(mm(0.10))
    zone.SetDoNotAllowTracks(True)
    zone.SetDoNotAllowVias(True)
    if hasattr(zone, "SetDoNotAllowCopperPour"):
        zone.SetDoNotAllowCopperPour(True)
    else:
        zone.SetDoNotAllowZoneFills(True)
    zone.SetDoNotAllowPads(False)
    zone.SetDoNotAllowFootprints(False)
    if hasattr(zone, "SetRuleAreaPlacementEnabled"):
        zone.SetRuleAreaPlacementEnabled(False)
    zone.AddPolygon(chain)
    board.Add(zone)


def add_battery_lead_slot_keepout_zone(
    board: pcbnew.BOARD,
    side: str,
    slot_center: tuple[float, float],
) -> None:
    slot_x, slot_y = slot_center
    margin = 0.80
    x1 = slot_x - BATTERY_LEAD_SLOT_LEN / 2.0 - margin
    y1 = slot_y - BATTERY_LEAD_SLOT_W / 2.0 - margin
    x2 = slot_x + BATTERY_LEAD_SLOT_LEN / 2.0 + margin
    y2 = slot_y + BATTERY_LEAD_SLOT_W / 2.0 + margin
    chain = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
        chain.Append(vxy(x, y))
    chain.SetClosed(True)

    zone = pcbnew.ZONE(board)
    zone.SetZoneName(f"{side.upper()}_BATTERY_LEAD_SLOT_NO_COPPER_TRACE_VIA")
    zone.SetNetCode(0)
    zone.SetLayerSet(copper_layers())
    zone.SetIsRuleArea(True)
    zone.SetMinThickness(mm(0.10))
    zone.SetDoNotAllowTracks(True)
    zone.SetDoNotAllowVias(True)
    if hasattr(zone, "SetDoNotAllowCopperPour"):
        zone.SetDoNotAllowCopperPour(True)
    else:
        zone.SetDoNotAllowZoneFills(True)
    zone.SetDoNotAllowPads(False)
    zone.SetDoNotAllowFootprints(False)
    if hasattr(zone, "SetRuleAreaPlacementEnabled"):
        zone.SetRuleAreaPlacementEnabled(False)
    zone.AddPolygon(chain)
    board.Add(zone)


def create_controller(
    board: pcbnew.BOARD,
    nets: dict[str, pcbnew.NETINFO_ITEM],
    ref: str,
    cx: float,
    cy: float,
    direction: int,
    pin_net_map: dict[str, str],
    variant: str,
) -> tuple[pcbnew.FOOTPRINT, dict[str, tuple[float, float]], tuple[float, float, float, float]]:
    fp = pcbnew.FOOTPRINT(board)
    controller_fp = "NiceNanoV2_Socket_24Pin_USB_OUT_LEFT" if direction == 1 else "NiceNanoV2_Socket_24Pin_USB_OUT_RIGHT"
    fp.SetFPIDAsString(f"KC2:{controller_fp}")
    fp.SetReference(ref)
    fp.SetValue("nice!nano_v2_socket_24pin")
    fp.SetPosition(vxy(cx, cy))

    row_a = ["D1", "D0", "GND_A", "GND_B", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9"]
    row_b = ["RAW", "GND_C", "RST", "VCC", "D21", "D20", "D19", "D18", "D15", "D14", "D16", "D10"]
    pad_pos: dict[str, tuple[float, float]] = {}

    physical_rows = (row_b, row_a) if direction == 1 else (row_a, row_b)
    for row_index, row in enumerate(physical_rows):
        local_y = (-SOCKET_ROW_SPACING / 2.0) if row_index == 0 else (SOCKET_ROW_SPACING / 2.0)
        y = cy + local_y
        for i, label in enumerate(row):
            local_x = -PIN_SPAN / 2.0 + i * PIN_PITCH
            x = cx + direction * local_x
            pad = pcbnew.PAD(fp)
            pad.SetNumber(label)
            pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
            pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
            pad.SetSize(pcbnew.VECTOR2I(mm(1.8), mm(1.8)))
            pad.SetDrillSize(pcbnew.VECTOR2I(mm(0.95), mm(0.95)))
            pad.SetLayerSet(pcbnew.LSET.AllCuMask())
            pad.SetPosition(vxy(x, y))
            net_name = pin_net_map.get(label)
            if label == "GND_C":
                net_name = "GND"
            if net_name:
                pad.SetNet(add_net(board, nets, net_name))
            fp.Add(pad)
            pad_pos[label] = (x, y)

            label_text = pcbnew.PCB_TEXT(fp)
            display_label = {"GND_A": "G", "GND_B": "G", "GND_C": "G"}.get(label, label.replace("_", ""))
            label_text.SetText(display_label)
            label_text.SetPosition(vxy(x, y + (2.1 if row_index == 0 else -2.1)))
            label_text.SetLayer(pcbnew.F_SilkS)
            label_text.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
            label_text.SetTextThickness(mm(0.10))
            fp.Add(label_text)

    board.Add(fp)
    add_rect_lines(
        board,
        cx - CONTROLLER_LEN / 2.0,
        cy - CONTROLLER_W / 2.0,
        cx + CONTROLLER_LEN / 2.0,
        cy + CONTROLLER_W / 2.0,
        pcbnew.F_Fab,
        0.10,
    )
    usb_x = cx - direction * CONTROLLER_LEN / 2.0
    ant_x = cx + direction * CONTROLLER_LEN / 2.0
    if variant == "x3-v2":
        # The shortened top edge has no room for the former horizontal labels.
        # Keep the exact USB direction visible in the clear outer service lane.
        add_board_text(
            board,
            "USB_OUT_LEFT" if direction == 1 else "USB_OUT_RIGHT",
            usb_x - direction * 3.2,
            cy,
            pcbnew.F_SilkS,
            0.8,
            0.10,
            90.0,
        )
    else:
        add_board_text(board, "USB_OUT_LEFT" if direction == 1 else "USB_OUT_RIGHT", usb_x, cy - 10.5, pcbnew.F_SilkS, 1.0)
    add_board_text(
        board,
        "ANTENNA_INWARD",
        ant_x - direction * 1.2 if variant == "x3-v2" else ant_x,
        cy if variant == "x3-v2" else cy - 10.5,
        pcbnew.F_Fab if variant == "x3-v2" else pcbnew.F_SilkS,
        0.6 if variant == "x3-v2" else 1.0,
        0.10 if variant == "x3-v2" else 0.15,
        90.0 if variant == "x3-v2" else 0.0,
    )

    keepout_start = cx + direction * ANTENNA_KEEP_START_FROM_CENTER
    keepout_x1 = keepout_start
    keepout_x2 = keepout_start + direction * ANTENNA_KEEP_LENGTH
    keepout = (min(keepout_x1, keepout_x2), cy - CONTROLLER_W / 2.0, max(keepout_x1, keepout_x2), cy + CONTROLLER_W / 2.0)
    add_rect_lines(board, *keepout, pcbnew.Dwgs_User, width=0.12)
    add_board_text(
        board,
        "ANT KEEPOUT",
        ant_x - direction * 0.4 if variant == "x3-v2" else (keepout[0] + keepout[2]) / 2.0,
        cy if variant == "x3-v2" else keepout[1] - 1.6,
        pcbnew.Dwgs_User,
        0.6 if variant == "x3-v2" else 0.9,
        0.10 if variant == "x3-v2" else 0.15,
        90.0 if variant == "x3-v2" else 0.0,
    )
    return fp, pad_pos, keepout


def connect_controller_ground_pads(
    board: pcbnew.BOARD,
    nets: dict[str, pcbnew.NETINFO_ITEM],
    controller_pads: dict[str, tuple[float, float]],
) -> None:
    # Only one controller ground socket pad is electrically needed for KC2's
    # reset switch reference. Other nice!nano GND pins remain unconnected on
    # the carrier PCB to avoid crossing active pins in the controller escape.
    return


def create_power_pads(
    board: pcbnew.BOARD,
    nets: dict[str, pcbnew.NETINFO_ITEM],
    ref: str,
    x: float,
    y: float,
) -> dict[str, tuple[float, float]]:
    fp = pcbnew.FOOTPRINT(board)
    fp.SetFPIDAsString("KC2:DirectSolderPowerPads")
    fp.SetReference(ref)
    fp.Reference().SetVisible(False)
    fp.SetValue("BAT_NN_direct_solder")
    fp.SetPosition(vxy(x, y))

    positions = {
        "BAT+": (-3.0, -2.2),
        "BAT-": (-3.0, 2.2),
        "NN_B+": (3.0, -2.2),
        "NN_B-": (3.0, 2.2),
    }
    abs_pos: dict[str, tuple[float, float]] = {}
    pad_net_names = {
        "BAT+": "BAT+",
        "BAT-": "BAT-",
        "NN_B+": "BAT+",
        "NN_B-": "BAT-",
    }
    for label, (dx, dy) in positions.items():
        pad = pcbnew.PAD(fp)
        pad.SetNumber(label)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
        pad.SetShape(pcbnew.PAD_SHAPE_OVAL)
        pad.SetSize(pcbnew.VECTOR2I(mm(2.6), mm(1.8)))
        pad.SetDrillSize(pcbnew.VECTOR2I(mm(0.9), mm(0.9)))
        pad.SetLayerSet(pcbnew.LSET.AllCuMask())
        pad.SetPosition(vxy(x + dx, y + dy))
        pad.SetNet(add_net(board, nets, pad_net_names[label]))
        fp.Add(pad)
        abs_pos[label] = (x + dx, y + dy)

        text = pcbnew.PCB_TEXT(fp)
        text.SetText(label)
        text.SetPosition(vxy(x + dx, y + dy - 2.1))
        text.SetLayer(pcbnew.F_SilkS)
        text.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
        text.SetTextThickness(mm(0.10))
        fp.Add(text)

    for idx, (dx, dy) in enumerate([(-6.5, -2.2), (-6.5, 2.2), (6.5, -2.2), (6.5, 2.2)], start=1):
        pad = pcbnew.PAD(fp)
        pad.SetNumber("")
        pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
        pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        pad.SetSize(pcbnew.VECTOR2I(mm(1.3), mm(1.3)))
        pad.SetDrillSize(pcbnew.VECTOR2I(mm(1.3), mm(1.3)))
        pad.SetLayerSet(mask_only_layers())
        pad.SetPosition(vxy(x + dx, y + dy))
        fp.Add(pad)

    board.Add(fp)
    add_track(board, add_net(board, nets, "BAT+"), abs_pos["BAT+"], abs_pos["NN_B+"], pcbnew.B_Cu, POWER_TRACK_WIDTH)
    add_track(board, add_net(board, nets, "BAT-"), abs_pos["BAT-"], abs_pos["NN_B-"], pcbnew.B_Cu, POWER_TRACK_WIDTH)
    return abs_pos


def create_stabilizer(
    board: pcbnew.BOARD,
    ref: str,
    key: Key,
    dx: float,
    dy: float,
) -> None:
    fp = pcbnew.FOOTPRINT(board)
    fp.SetFPIDAsString("KC2:PCB_Mount_2u_Stabilizer_NPTH")
    fp.SetReference(ref)
    fp.SetValue(f"PCB_mount_stab_for_{key.w_u:.2f}u")
    fp.SetPosition(vxy(key.cx + dx, key.cy + dy))
    for xoff in (-11.9, 11.9):
        for yoff, drill in ((-7.0, 3.05), (8.24, 4.0)):
            pad = pcbnew.PAD(fp)
            pad.SetNumber("")
            pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
            pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
            pad.SetSize(pcbnew.VECTOR2I(mm(drill), mm(drill)))
            pad.SetDrillSize(pcbnew.VECTOR2I(mm(drill), mm(drill)))
            pad.SetLayerSet(mask_only_layers())
            pad.SetPosition(vxy(key.cx + dx + xoff, key.cy + dy + yoff))
            fp.Add(pad)
    board.Add(fp)


def make_board(
    side: str,
    keys: list[Key],
    out_dir: Path,
    *,
    project_suffix: str = "",
    switch_lib: Path = SWITCH_LIB,
    switch_fp: str = SOLDERED_SWITCH_FP,
    diode_lib: Path = DIODE_LIB,
    diode_fp: str = DIODE_FP,
    diode_value: str = "1N4148W_SOD-123",
    diode_y_offset: float = DEFAULT_DIODE_Y_OFFSET,
    variant: str = "soldered",
) -> tuple[Path, tuple[float, float, float, float]]:
    name = f"kc2_{side}{project_suffix}"
    project_dir = out_dir / name
    if project_dir.exists():
        for child in project_dir.iterdir():
            if child.is_file() and child.suffix in {".kicad_pcb", ".kicad_pro", ".kicad_prl", ".json", ".rpt"}:
                child.unlink()
    project_dir.mkdir(parents=True, exist_ok=True)

    ctrl_cx = controller_center_x(keys, side, variant=variant)
    top_margin_extra = 0.0
    if variant in {"x1", "x2"} and side == "right":
        top_margin_extra = 0.3
    elif variant == "x3":
        top_margin_extra = 2.5 if side == "right" else 2.0
    outline_margins = variant_outline_margins(variant)
    inner_margin_extra = outline_margins["inner_mm"] - INNER_MARGIN
    general_margin = outline_margins["outer_mm"]
    top_margin_extra += outline_margins["top_mm"] - general_margin
    outline = raw_outline(
        keys,
        side,
        ctrl_cx,
        variant=variant,
        top_margin_extra=top_margin_extra,
        inner_margin_extra=inner_margin_extra,
        general_margin=general_margin,
    )
    rounded = rounded_polygon(outline, radius=2.0, steps=5)
    if variant == "x3" and side == "right":
        rounded = x3_right_horizontal_ledge_relief(rounded, keys, radius=2.0)
    min_x = min(x for x, _ in rounded)
    min_y = min(y for _, y in rounded)
    dx = 35.0 - min_x
    dy = X3_V2_BOARD_DATUM_DY_MM if variant == "x3-v2" else 35.0 - min_y

    shifted_keys = [
        Key(k.label, k.row, k.col, k.x_u + dx / UNIT, k.y_u + dy / UNIT, k.w_u, k.h_u)
        for k in keys
    ]
    ctrl_cx += dx
    ctrl_cy = X3_V2_CONTROLLER_Y_MM if variant == "x3-v2" else CONTROLLER_CENTER_Y + dy
    shifted_outline = shift_points(rounded, dx, dy)

    board = pcbnew.BOARD()
    board.SetCopperLayerCount(2)
    title = board.GetTitleBlock()
    variant_title = "" if variant == "soldered" else f" {variant.upper()}"
    title.SetTitle(f"KC2 {side.capitalize()}{variant_title} PCB Draft")
    title.SetDate("2026-08-20" if variant == "x3-v2" else "2026-06-04")
    title.SetRevision("draft-v2" if variant == "x3-v2" else "draft-1")
    add_polyline(board, shifted_outline, pcbnew.Edge_Cuts, EDGE_WIDTH, closed=True)

    nets: dict[str, pcbnew.NETINFO_ITEM] = {"": board.GetNetInfo().GetNetItem(0)}
    add_net(board, nets, "GND")
    add_net(board, nets, "RST")
    if variant == "x3-v2":
        add_net(board, nets, "BAT+")
        add_net(board, nets, "NN_B+")
    elif not is_x3_family(variant):
        for pwr in ("BAT+", "BAT-"):
            add_net(board, nets, pwr)

    if side == "left":
        pin_map = {
            "D3": "L_COL0",
            "D5": "L_COL1",
            "D4": "L_COL2",
            "D6": "L_COL3",
            "D7": "L_COL4",
            "D8": "L_COL5",
            "D9": "L_COL6",
            "D10": "L_ROW0",
            "D16": "L_ROW1",
            "D14": "L_ROW2",
            "D15": "L_ROW3",
            "D18": "L_ROW4",
            "RST": "RST",
            **({"RAW": "NN_B+"} if variant == "x3-v2" else {}),
        }
        col_prefix = "L_COL"
        row_prefix = "L_ROW"
        usb_direction = 1
    else:
        pin_map = {
            "D9": "R_COL0",
            "D10": "R_COL1",
            "D16": "R_COL2",
            "D14": "R_COL3",
            "D15": "R_COL4",
            "D18": "R_COL5",
            "D19": "R_COL6",
            "D20": "R_COL8",
            "D21": "R_COL7",
            "D3": "R_ROW0",
            "D4": "R_ROW1",
            "D5": "R_ROW2",
            "D2": "R_ROW3",
            "D7": "R_ROW4",
            "RST": "RST",
            **({"RAW": "NN_B+"} if variant == "x3-v2" else {}),
        }
        col_prefix = "R_COL"
        row_prefix = "R_ROW"
        usb_direction = -1

    for net_name in pin_map.values():
        add_net(board, nets, net_name)

    _, controller_pads, antenna_keepout = create_controller(
        board, nets, "U1", ctrl_cx, ctrl_cy, usb_direction, pin_map, variant
    )
    add_antenna_keepout_zone(board, side, antenna_keepout)

    power_pads: dict[str, tuple[float, float]] | None = None
    battery_termination: pcbnew.FOOTPRINT | None = None
    power_switch: pcbnew.FOOTPRINT | None = None
    if variant == "x3-v2":
        service = X3_V2_CONTROLLER_SERVICE_POSITIONS_MM[side]
        service_rotations = X3_V2_CONTROLLER_SERVICE_ROTATIONS_DEGREES[side]
        battery_body = load_footprint(
            board,
            X3_V2_BATTERY_BODY_LIB,
            X3_V2_BATTERY_BODY_FP,
            "BAT1",
            X3_V2_BATTERY_BODY_VALUE,
            *service["battery"],
            service_rotations["BAT1"],
        )
        battery_body.Reference().SetVisible(False)
        battery_body.Value().SetVisible(False)

        battery_termination = load_footprint(
            board,
            X3_V2_BATTERY_TERMINATION_LIB,
            X3_V2_BATTERY_TERMINATION_FP,
            "J_BAT1",
            X3_V2_BATTERY_TERMINATION_VALUE,
            *service["j_bat"],
            service_rotations["J_BAT1"],
        )
        battery_termination.Reference().SetVisible(False)
        assign_footprint_pad_nets(
            board,
            nets,
            battery_termination,
            {"1": "BAT+", "2": "GND"},
        )
        power_switch = load_footprint(
            board,
            X3_V2_POWER_SWITCH_LIB,
            X3_V2_POWER_SWITCH_FP,
            "SW_PWR1",
            X3_V2_POWER_SWITCH_VALUE,
            *service["power"],
            service_rotations["SW_PWR1"],
        )
        power_switch.Reference().SetVisible(False)
        assign_footprint_pad_nets(
            board,
            nets,
            power_switch,
            {"1": "BAT+", "2": "NN_B+", "3": None},
        )
        add_board_text(
            board,
            "PWR OFF< >ON" if side == "left" else "ON< >OFF PWR",
            service["power"][0],
            service["power"][1] + 2.8,
            pcbnew.F_SilkS,
            0.8,
            0.10,
        )
    elif not is_x3_family(variant):
        power_y = ctrl_cy + 1.0
        power_x = ctrl_cx - usb_direction * 28.0
        power_pads = create_power_pads(board, nets, "J_PWR1", power_x, power_y)
        add_board_text(board, "B+/B- direct cable solder only", power_x - 12, power_y + 7.0, pcbnew.Cmts_User, 0.9)
    else:
        add_board_text(board, "Battery solders directly to nice!nano B+/B-; no carrier power pads", ctrl_cx - 23.0, ctrl_cy + 15.0, pcbnew.Cmts_User, 0.8)

    if variant != "x3-v2":
        batt_w, batt_h = 15.0, 25.0
        batt_cx = ctrl_cx + (
            usb_direction * X3_BATTERY_CENTER_OFFSET_FROM_CONTROLLER
            if is_x3_family(variant)
            else -usb_direction * 7.0
        )
        batt_cy = ctrl_cy + 2.0
        add_rect_lines(
            board,
            batt_cx - batt_w / 2,
            batt_cy - batt_h / 2,
            batt_cx + batt_w / 2,
            batt_cy + batt_h / 2,
            pcbnew.B_Fab,
            0.10,
        )
        add_board_text(
            board,
            "TW301525 80mAh",
            batt_cx - 7.0,
            batt_cy,
            pcbnew.B_Fab,
            0.9,
            mirrored=True,
        )

    battery_lead_slot_points: list[tuple[float, float]] = []
    if is_x3_family(variant):
        slot_x, slot_y = x3_battery_lead_slot_point(
            ctrl_cx, ctrl_cy, usb_direction, variant
        )
        battery_lead_slot_points.append((slot_x, slot_y))
        slot_fp = load_footprint(
            board,
            BATTERY_LEAD_SLOT_LIB,
            BATTERY_LEAD_SLOT_FP,
            "BAT_LEAD_SLOT1",
            BATTERY_LEAD_SLOT_VALUE,
            slot_x,
            slot_y,
        )
        slot_fp.Reference().SetVisible(False)
        slot_fp.Value().SetVisible(False)
        add_battery_lead_slot_keepout_zone(board, side, (slot_x, slot_y))
        add_rect_lines(
            board,
            slot_x - BATTERY_LEAD_SLOT_LEN / 2.0,
            slot_y - BATTERY_LEAD_SLOT_W / 2.0,
            slot_x + BATTERY_LEAD_SLOT_LEN / 2.0,
            slot_y + BATTERY_LEAD_SLOT_W / 2.0,
            pcbnew.Cmts_User,
            0.08,
        )
        add_board_text(
            board,
            "BAT STRAIN RELIEF" if variant == "x3-v2" else "BAT LEAD EXIT",
            slot_x - 4.5,
            slot_y + 3.2,
            pcbnew.Cmts_User,
            0.7,
        )

    if variant == "x3-v2":
        tact_x, tact_y = X3_V2_CONTROLLER_SERVICE_POSITIONS_MM[side]["reset"]
    elif is_x3_family(variant):
        tact_x = batt_cx + usb_direction * (batt_w / 2.0 + X3_TACT_BATTERY_CLEARANCE + X3_TACT_BODY_W / 2.0)
        tact_y = ctrl_cy + CONTROLLER_W / 2.0 + 4.0
    else:
        tact_offset_from_center = CONTROLLER_LEN / 2.0 - 7.0
        tact_x = ctrl_cx - usb_direction * tact_offset_from_center
        tact_y = ctrl_cy + CONTROLLER_W / 2.0 + 4.0
    tact_rotation = (
        X3_V2_CONTROLLER_SERVICE_ROTATIONS_DEGREES[side]["SW_RST1"]
        if variant == "x3-v2"
        else 0.0
    )
    tact = load_footprint(
        board,
        TACT_LIB,
        TACT_FP,
        "SW_RST1",
        "NW3-A06-B3 RST",
        tact_x,
        tact_y,
        tact_rotation,
    )
    if variant == "x3-v2":
        tact.Reference().SetVisible(False)
        add_board_text(
            board,
            "RST",
            tact_x,
            tact_y + 4.2,
            pcbnew.F_SilkS,
            0.8,
            0.10,
        )

    registration_points = x3_registration_points(side, shifted_keys) if variant == "x3" else []
    v2_mount_points = X3_V2_MOUNTING_POINTS[side] if variant == "x3-v2" else []
    global ACTIVE_TRACE_KEEP_OUTS
    previous_trace_keep_outs = ACTIVE_TRACE_KEEP_OUTS
    ACTIVE_TRACE_KEEP_OUTS = registration_points + battery_lead_slot_points + v2_mount_points

    mount_points = mounting_points(side, shifted_keys, shifted_outline, ctrl_cx, ctrl_cy)
    if is_x3_family(variant):
        mount_points = []
    for idx, (mx, my) in enumerate(mount_points, start=1):
        fp = load_footprint(board, MOUNT_LIB, MOUNT_FP, f"H{idx}", "M2_NPTH_2.2", mx, my)
        add_rect_lines(board, mx - 2.5, my - 2.5, mx + 2.5, my + 2.5, pcbnew.Cmts_User, 0.08)
    for idx, (mx, my) in enumerate(v2_mount_points, start=1):
        fp = load_footprint(
            board,
            X3_V2_MOUNT_LIB,
            X3_V2_MOUNT_FP,
            f"MH{idx}",
            X3_V2_MOUNT_VALUE,
            mx,
            my,
        )
        reference = fp.Reference()
        reference.SetVisible(True)
        reference.SetLayer(pcbnew.F_SilkS)
        reference.SetTextSize(
            vxy(
                X3_V2_MOUNT_REFERENCE_TEXT_SIZE_MM,
                X3_V2_MOUNT_REFERENCE_TEXT_SIZE_MM,
            )
        )
        reference.SetTextThickness(mm(X3_V2_MOUNT_REFERENCE_STROKE_MM))
        reference.SetFPRelativePosition(vxy(*X3_V2_MOUNT_REFERENCE_OFFSET_MM))
        fp.Value().SetVisible(False)
    for idx, (rx, ry) in enumerate(registration_points, start=1):
        fp = load_footprint(board, REGISTRATION_LIB, REGISTRATION_FP, f"REG{idx}", REGISTRATION_VALUE, rx, ry)
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        add_rect_lines(board, rx - 2.0, ry - 2.0, rx + 2.0, ry + 2.0, pcbnew.Cmts_User, 0.08)

    switch_refs: dict[str, pcbnew.FOOTPRINT] = {}
    diode_refs: dict[str, pcbnew.FOOTPRINT] = {}
    row_diodes: dict[int, list[tuple[float, float]]] = {}
    col_switches: dict[int, list[tuple[float, float]]] = {}

    for idx, key in enumerate(shifted_keys, start=1):
        col_net_name = f"{col_prefix}{key.col}"
        row_net_name = f"{row_prefix}{key.row}"
        local_net_name = f"{side[0].upper()}K{idx:02d}_D"
        col_net = add_net(board, nets, col_net_name)
        row_net = add_net(board, nets, row_net_name)
        local_net = add_net(board, nets, local_net_name)

        sw = load_footprint(
            board,
            switch_lib,
            switch_fp,
            f"SW{idx}",
            f"KEY_{idx:02d}",
            key.cx,
            key.cy,
            switch_rotation_for_key(key, shifted_keys, variant),
        )
        convert_empty_switch_pads_to_npth(sw)
        set_pad_net(sw, "1", col_net)
        set_pad_net(sw, "2", local_net)
        switch_refs[key.label + str(idx)] = sw
        key_label_layer = pcbnew.F_Fab if variant == "x3-v2" else pcbnew.F_SilkS
        add_board_text(board, key.label, key.cx - 3.0, key.cy - 9.2, key_label_layer, 0.9)

        diode_dx, diode_dy, diode_rotation = diode_placement_for_key(
            key,
            shifted_keys,
            variant,
            diode_y_offset,
        )
        dio = load_footprint(
            board,
            diode_lib,
            diode_fp,
            f"D{idx}",
            diode_value,
            key.cx + diode_dx,
            key.cy + diode_dy,
            diode_rotation,
            bottom=True,
        )
        if variant == "x3-v2":
            dio.Reference().SetLayer(pcbnew.B_Fab)
        set_pad_net(dio, "1", row_net)
        set_pad_net(dio, "2", local_net)
        diode_refs[key.label + str(idx)] = dio

        sw_p1 = pad_positions(sw, "1")
        sw_p2 = pad_positions(sw, "2")
        d_p1 = pad_positions(dio, "1")[0]
        d_p2 = pad_positions(dio, "2")[0]

        for a, b in zip(sw_p1, sw_p1[1:]):
            add_track(board, col_net, a, b, pcbnew.B_Cu)

        row_bus_y = key.cy - 10.8
        row_tap = (d_p1[0], row_bus_y)
        add_track(board, row_net, d_p1, row_tap, pcbnew.B_Cu)

        left_switch_pad2 = sorted(sw_p2, key=lambda p: p[0])[0]
        right_switch_pad2 = sorted(sw_p2, key=lambda p: p[0])[-1]
        local_lane_x = key.cx - 8.0
        add_track(board, local_net, d_p2, (local_lane_x, d_p2[1]), pcbnew.B_Cu)
        add_track(board, local_net, (local_lane_x, d_p2[1]), (local_lane_x, left_switch_pad2[1]), pcbnew.B_Cu)
        add_track(board, local_net, (local_lane_x, left_switch_pad2[1]), left_switch_pad2, pcbnew.B_Cu)
        add_track(board, local_net, left_switch_pad2, right_switch_pad2, pcbnew.B_Cu)

        sw_p1_fcu = pad_positions_on_layer(sw, "1", pcbnew.F_Cu)
        col_anchor = sorted(sw_p1_fcu, key=lambda p: p[0])[0]
        col_tap_dx = -1.5 if side == "left" else 1.5
        col_tap = (col_anchor[0] + col_tap_dx, col_anchor[1])
        add_track(board, col_net, col_anchor, col_tap, pcbnew.F_Cu)
        row_diodes.setdefault(key.row, []).append(row_tap)
        col_switches.setdefault(key.col, []).append(col_tap)

        if key.w_u >= 2.0:
            create_stabilizer(board, f"STAB{idx}", key, 0, 0)

    for idx, (rx, ry) in enumerate(registration_points, start=1):
        label_x, label_y = registration_label_position(board, rx, ry)
        add_board_text(
            board,
            f"H{idx}",
            label_x,
            label_y,
            pcbnew.B_SilkS,
            0.8,
            0.10,
            mirrored=True,
        )

    for row, points in row_diodes.items():
        net = add_net(board, nets, f"{row_prefix}{row}")
        points = sorted(points, key=lambda p: p[0])
        for a, b in zip(points, points[1:]):
            add_track(board, net, a, b, pcbnew.B_Cu)

    for col, points in col_switches.items():
        net = add_net(board, nets, f"{col_prefix}{col}")
        points = sorted(points, key=lambda p: p[1])
        spine_x = (min(x for x, _ in points) - 1.5) if side == "left" else (max(x for x, _ in points) + 1.5)
        route_via_vertical_spine(board, net, points, pcbnew.F_Cu, spine_x)

    connect_matrix_to_controller(
        board,
        nets,
        side,
        col_prefix,
        row_prefix,
        col_switches,
        row_diodes,
        controller_pads,
        pin_map,
        shifted_outline,
    )
    connect_controller_ground_pads(board, nets, controller_pads)
    connect_tact_to_controller(
        board,
        nets,
        tact,
        controller_pads,
        side if variant == "x3-v2" else None,
    )
    if battery_termination is not None and power_switch is not None:
        connect_x3_v2_power_service(
            board,
            nets,
            battery_termination,
            power_switch,
            controller_pads,
            side,
        )
    if power_pads is not None:
        connect_power_labels(board, nets, power_pads)

    variant_label = "" if variant == "soldered" else f" {variant.upper()}"
    layout_name = (
        "70-key v5 no-stabilizer split layout"
        if variant == "x3-v2"
        else "77-key no-stabilizer split layout"
        if variant == "x3"
        else "71-key split successor to KC1"
    )
    add_board_text(board, f"KC2 {side.upper()}{variant_label} - {layout_name}", 35, 24, pcbnew.F_SilkS, 1.2)
    housing_note = (
        "No top housing / selected M1.4 MH retention + independent underside supports"
        if variant == "x3-v2"
        else "No top housing / screwless PLA+ rail tray / REG holes"
        if variant == "x3"
        else "No top housing / PCB is switch plate / bottom plate M2+adhesive"
    )
    add_board_text(board, housing_note, 35, 27, pcbnew.F_SilkS, 0.9)
    diode_note = (
        "Diode: Jingdao ES1B / C437840 / Eleparts 9475342; pad 1 = row cathode"
        if variant == "x3-v2"
        else "Diode fallback: 1N4148W SOD-123 because DO-35 conflicts with compact hybrid footprint"
    )
    add_board_text(board, diode_note, 35, 30, pcbnew.Cmts_User, 0.9)
    if variant == "hotswap":
        add_board_text(board, "Hot-swap variant: Kailh Choc V1/V2 socket footprint, not MX-only socket", 35, 33, pcbnew.Cmts_User, 0.9)
    elif variant == "x1":
        add_board_text(board, "X1: DeviceMart 14592018 1N4148W SOD-123, enlarged hand-solder pads", 35, 33, pcbnew.Cmts_User, 0.9)
    elif variant == "x2":
        add_board_text(board, "X2: Kailh Choc V1 socket plus direct THT solder, X1 hand-solder diodes", 35, 33, pcbnew.Cmts_User, 0.9)
    elif variant == "x3":
        add_board_text(board, "X3: X2 electrical stack, no-stabilizer 77-key split layout", 35, 33, pcbnew.Cmts_User, 0.9)
    elif variant == "x3-v2":
        add_board_text(board, "X3 V2: Choc V2 socket OR rotated MX 5-pin direct solder; Choc V1 unsupported", 35, 33, pcbnew.Cmts_User, 0.9)
    add_product_identity_text(board, side, shifted_outline, variant)

    make_project_file(project_dir, name, variant=variant)
    make_fp_lib_table(project_dir, include_switch_lib=switch_lib == SWITCH_LIB)
    board_path = project_dir / f"{name}.kicad_pcb"
    pcbnew.SaveBoard(str(board_path), board)
    make_project_file(project_dir, name, variant=variant)
    ACTIVE_TRACE_KEEP_OUTS = previous_trace_keep_outs
    return board_path, antenna_keepout


def mounting_points(
    side: str,
    keys: list[Key],
    outline: list[tuple[float, float]],
    ctrl_cx: float,
    ctrl_cy: float,
) -> list[tuple[float, float]]:
    min_x = min(x for x, _ in outline)
    max_x = max(x for x, _ in outline)
    max_y = max(y for _, y in outline)
    points = [
        (min_x + 4.0, max_y - 4.0),
        (max_x - 4.0, max_y - 4.0),
        (ctrl_cx - 18.0, ctrl_cy - 5.0),
        (ctrl_cx + 18.0, ctrl_cy - 5.0),
    ]
    if side == "right":
        points.append((max_x - 4.0, max_y - SIDE_MOUNT_UPPER_OFFSET_FROM_BOTTOM))
    else:
        points.append((min_x + 4.5, max_y - SIDE_MOUNT_UPPER_OFFSET_FROM_BOTTOM))
    return points


def x3_registration_points(side: str, keys: list[Key]) -> list[tuple[float, float]]:
    min_x = min(key.cx for key in keys)
    min_y = min(key.cy for key in keys)
    if side == "left":
        offsets = (
            (14.505, 24.505),
            (76.185, 13.505),
            (96.875, 13.005),
            (18.005, 45.405),
            (60.685, 45.405),
            (98.375, 45.405),
            (12.995, 73.795),
            (60.685, 73.795),
            (88.875, 64.795),
        )
    elif side == "right":
        offsets = (
            (54.995, 7.005),
            (93.565, 6.505),
            (152.625, 18.005),
            (6.255, 49.645),
            (83.565, 48.405),
            (152.125, 44.405),
            (6.755, 67.045),
            (98.065, 64.295),
            (157.625, 52.795),
        )
    else:
        raise ValueError(f"Unknown side: {side}")
    return [(min_x + dx, min_y + dy) for dx, dy in offsets]


def x3_battery_lead_slot_point(
    ctrl_cx: float,
    ctrl_cy: float,
    usb_direction: int,
    variant: str = "x3",
) -> tuple[float, float]:
    if variant == "x3-v2":
        usb_edge_x = ctrl_cx - usb_direction * CONTROLLER_LEN / 2.0
        slot_x = usb_edge_x + usb_direction * (
            BATTERY_LEAD_SLOT_LEN / 2.0 + BATTERY_LEAD_SLOT_KEEP_OUT_GAP
        )
        return slot_x, ctrl_cy
    keepout_near_edge_x = ctrl_cx + usb_direction * ANTENNA_KEEP_START_FROM_CENTER
    slot_x = keepout_near_edge_x - usb_direction * (BATTERY_LEAD_SLOT_LEN / 2.0 + BATTERY_LEAD_SLOT_KEEP_OUT_GAP)
    return slot_x, ctrl_cy


def circle_intersects_rect(
    x: float,
    y: float,
    radius: float,
    rect: tuple[float, float, float, float],
) -> bool:
    nearest_x = min(max(x, rect[0]), rect[2])
    nearest_y = min(max(y, rect[1]), rect[3])
    return (x - nearest_x) ** 2 + (y - nearest_y) ** 2 <= radius**2


def connect_matrix_to_controller(
    board: pcbnew.BOARD,
    nets: dict[str, pcbnew.NETINFO_ITEM],
    side: str,
    col_prefix: str,
    row_prefix: str,
    col_switches: dict[int, list[tuple[float, float]]],
    row_diodes: dict[int, list[tuple[float, float]]],
    controller_pads: dict[str, tuple[float, float]],
    pin_map: dict[str, str],
    outline: list[tuple[float, float]],
) -> None:
    net_to_pin = {net: pin for pin, net in pin_map.items()}
    min_outline_x = min(x for x, _ in outline)
    max_outline_x = max(x for x, _ in outline)

    for col, points in col_switches.items():
        net_name = f"{col_prefix}{col}"
        pin = net_to_pin.get(net_name)
        if not pin:
            continue
        net = add_net(board, nets, net_name)
        src = sorted(points, key=lambda p: p[1])[0]
        dst = controller_pads[pin]
        route_to_controller(
            board,
            net,
            src,
            dst,
            controller_pads,
            pcbnew.F_Cu,
            jog_y=dst[1] + 22.0 + col * 0.45,
        )

    for row, points in row_diodes.items():
        net_name = f"{row_prefix}{row}"
        pin = net_to_pin.get(net_name)
        if not pin:
            continue
        net = add_net(board, nets, net_name)
        dst = controller_pads[pin]
        src = min(points, key=lambda p: abs(p[0] - dst[0]) + abs(p[1] - dst[1]))
        route_to_controller(
            board,
            net,
            src,
            dst,
            controller_pads,
            pcbnew.B_Cu,
            jog_y=max(y for _, y in controller_pads.values()) + 5.1 + row * 0.7,
        )


def route_manhattan(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    src: tuple[float, float],
    dst: tuple[float, float],
    layer: int,
    jog_y: float,
    width: float = TRACK_WIDTH,
) -> None:
    p1 = (src[0], jog_y)
    p2 = (dst[0], jog_y)
    add_track(board, net, src, p1, layer, width)
    add_track(board, net, p1, p2, layer, width)
    add_track(board, net, p2, dst, layer, width)


def route_via_vertical_spine(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    points: list[tuple[float, float]],
    layer: int,
    spine_x: float,
) -> None:
    for a, b in zip(points, points[1:]):
        a_spine = (spine_x, a[1])
        b_spine = (spine_x, b[1])
        add_track(board, net, a, a_spine, layer)
        add_track(board, net, a_spine, b_spine, layer)
        add_track(board, net, b_spine, b, layer)


def route_to_controller(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    src: tuple[float, float],
    dst: tuple[float, float],
    controller_pads: dict[str, tuple[float, float]],
    layer: int,
    jog_y: float,
    width: float = TRACK_WIDTH,
) -> None:
    top_y = min(y for _, y in controller_pads.values())
    bottom_y = max(y for _, y in controller_pads.values())
    if abs(dst[1] - top_y) < 0.05 and jog_y > bottom_y:
        escape_x = dst[0] + PIN_PITCH / 2.0
        p0 = (escape_x, dst[1])
        p1 = (escape_x, jog_y)
        p2 = (src[0], jog_y)
        add_track(board, net, dst, p0, layer, width)
        add_track(board, net, p0, p1, layer, width)
        add_track(board, net, p1, p2, layer, width)
        add_track(board, net, p2, src, layer, width)
        return
    route_manhattan(board, net, src, dst, layer, jog_y, width)


def add_exact_service_polyline(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    points: list[tuple[float, float]],
    expected_start: tuple[float, float],
    expected_end: tuple[float, float],
    width: float,
    layer: int = pcbnew.F_Cu,
) -> None:
    if not points:
        raise RuntimeError(f"{net.GetNetname()} service route has no points")
    for label, actual, expected in (
        ("start", points[0], expected_start),
        ("end", points[-1], expected_end),
    ):
        if max(abs(actual[index] - expected[index]) for index in (0, 1)) > 1e-4:
            raise RuntimeError(
                f"{net.GetNetname()} service route {label} {actual} does not match "
                f"the placed pad {expected}"
            )
    for start, end in zip(points, points[1:]):
        add_track(board, net, start, end, layer, width)


def connect_tact_to_controller(
    board: pcbnew.BOARD,
    nets: dict[str, pcbnew.NETINFO_ITEM],
    tact: pcbnew.FOOTPRINT,
    controller_pads: dict[str, tuple[float, float]],
    side: str | None = None,
) -> None:
    if side is not None and side not in X3_V2_RESET_ROUTE_POINTS_MM:
        raise RuntimeError(f"unsupported X3 V2 reset route side {side!r}")
    rst = add_net(board, nets, "RST")
    gnd = add_net(board, nets, "GND")
    rst_pad_obj = min(
        pads_by_number(tact, "1"),
        key=lambda pad: abs(to_mm_vec(pad.GetPosition())[0] - controller_pads["RST"][0])
        + abs(to_mm_vec(pad.GetPosition())[1] - controller_pads["RST"][1]),
    )
    gnd_pad_obj = min(
        pads_by_number(tact, "2"),
        key=lambda pad: abs(to_mm_vec(pad.GetPosition())[0] - controller_pads["GND_C"][0])
        + abs(to_mm_vec(pad.GetPosition())[1] - controller_pads["GND_C"][1]),
    )
    for pad in pads_by_number(tact, "1") + pads_by_number(tact, "2"):
        pad.SetNetCode(0)
    rst_pad_obj.SetNet(rst)
    gnd_pad_obj.SetNet(gnd)
    rst_pad = to_mm_vec(rst_pad_obj.GetPosition())
    gnd_pad = to_mm_vec(gnd_pad_obj.GetPosition())
    if side is None:
        route_to_controller(
            board,
            rst,
            rst_pad,
            controller_pads["RST"],
            controller_pads,
            pcbnew.F_Cu,
            jog_y=max(y for _, y in controller_pads.values()) + 2.0,
        )
        route_to_controller(
            board,
            gnd,
            gnd_pad,
            controller_pads["GND_C"],
            controller_pads,
            pcbnew.F_Cu,
            jog_y=controller_pads["GND_C"][1] + 3.0,
        )
        return
    reset_routes = X3_V2_RESET_ROUTE_POINTS_MM[side]
    add_exact_service_polyline(
        board,
        rst,
        reset_routes["RST"],
        rst_pad,
        controller_pads["RST"],
        TRACK_WIDTH,
    )
    gnd_vias = reset_routes["GND_VIA"]
    if len(gnd_vias) != 1:
        raise RuntimeError(f"{side} reset GND route must contain exactly one via")
    gnd_via = gnd_vias[0]
    add_exact_service_polyline(
        board,
        gnd,
        reset_routes["GND_F"],
        gnd_pad,
        gnd_via,
        TRACK_WIDTH,
    )
    add_via(board, gnd, gnd_via)
    add_exact_service_polyline(
        board,
        gnd,
        reset_routes["GND_B"],
        gnd_via,
        X3_V2_RESET_GND_ROUTE_ENDS_MM[side],
        TRACK_WIDTH,
        pcbnew.B_Cu,
    )


def connect_power_labels(
    board: pcbnew.BOARD,
    nets: dict[str, pcbnew.NETINFO_ITEM],
    power_pads: dict[str, tuple[float, float]],
) -> None:
    # The actual nice!nano B+/B- top pads are wired by hand to NN_B+/NN_B-.
    # Keep short wide PCB traces only between the same-polarity solder pads.
    add_board_text(board, "+", power_pads["BAT+"][0] - 1.0, power_pads["BAT+"][1] - 3.8, pcbnew.F_SilkS, 1.2)
    add_board_text(board, "-", power_pads["BAT-"][0] - 1.0, power_pads["BAT-"][1] + 3.0, pcbnew.F_SilkS, 1.2)


def connect_x3_v2_power_service(
    board: pcbnew.BOARD,
    nets: dict[str, pcbnew.NETINFO_ITEM],
    battery_termination: pcbnew.FOOTPRINT,
    power_switch: pcbnew.FOOTPRINT,
    controller_pads: dict[str, tuple[float, float]],
    side: str,
) -> None:
    if side not in X3_V2_POWER_ROUTE_POINTS_MM:
        raise RuntimeError(f"unsupported X3 V2 power route side {side!r}")
    bat = add_net(board, nets, "BAT+")
    switched = add_net(board, nets, "NN_B+")
    gnd = add_net(board, nets, "GND")
    j_bat_plus = to_mm_vec(pads_by_number(battery_termination, "1")[0].GetPosition())
    j_bat_gnd = to_mm_vec(pads_by_number(battery_termination, "2")[0].GetPosition())
    switch_common = to_mm_vec(pads_by_number(power_switch, "1")[0].GetPosition())
    switch_on = to_mm_vec(pads_by_number(power_switch, "2")[0].GetPosition())
    add_track(board, bat, j_bat_plus, switch_common, pcbnew.F_Cu, POWER_TRACK_WIDTH)
    power_routes = X3_V2_POWER_ROUTE_POINTS_MM[side]
    add_exact_service_polyline(
        board,
        switched,
        power_routes["NN_B+"],
        switch_on,
        controller_pads["RAW"],
        POWER_TRACK_WIDTH,
    )
    add_exact_service_polyline(
        board,
        gnd,
        power_routes["GND"],
        j_bat_gnd,
        controller_pads["GND_C"],
        POWER_TRACK_WIDTH,
        pcbnew.B_Cu,
    )
def copy_license() -> None:
    src = SWITCH_LIB / "LICENSE"
    if src.exists():
        dest = ROOT / "third_party" / "key-switches.pretty.LICENSE"
        if not dest.exists():
            shutil.copyfile(src, dest)


def generate_variant(variant: str, output_dir: Path | None = None) -> dict[str, object]:
    if variant == "soldered":
        out_dir = DRAFT_ROOT / "soldered"
        project_suffix = ""
        switch_lib = SWITCH_LIB
        switch_fp = SOLDERED_SWITCH_FP
        diode_lib = DIODE_LIB
        diode_fp = DIODE_FP
        diode_value = "1N4148W_SOD-123"
        diode_y_offset = DEFAULT_DIODE_Y_OFFSET
        manifest_name = "kc2_generation_manifest.json"
    elif variant == "hotswap":
        out_dir = DRAFT_ROOT / "hotswap"
        project_suffix = "-hotswap"
        switch_lib = SWITCH_LIB
        switch_fp = HOTSWAP_SWITCH_FP
        diode_lib = DIODE_LIB
        diode_fp = DIODE_FP
        diode_value = "1N4148W_SOD-123"
        diode_y_offset = DEFAULT_DIODE_Y_OFFSET
        manifest_name = "kc2_hotswap_generation_manifest.json"
    elif variant == "x1":
        out_dir = DRAFT_ROOT / "x1"
        project_suffix = "-x1"
        switch_lib = SWITCH_LIB
        switch_fp = HOTSWAP_SWITCH_FP
        diode_lib = X1_DIODE_LIB
        diode_fp = X1_DIODE_FP
        diode_value = X1_DIODE_VALUE
        diode_y_offset = DEFAULT_DIODE_Y_OFFSET
        manifest_name = "kc2_x1_generation_manifest.json"
    elif variant == "x2":
        out_dir = DRAFT_ROOT / "x2"
        project_suffix = "-x2"
        switch_lib = KC2_FP_LIB
        switch_fp = X2_SWITCH_FP
        diode_lib = X1_DIODE_LIB
        diode_fp = X1_DIODE_FP
        diode_value = X1_DIODE_VALUE
        diode_y_offset = X2_DIODE_Y_OFFSET
        manifest_name = "kc2_x2_generation_manifest.json"
        left_keys = make_left_keys()
        right_keys = make_right_keys()
    elif is_x3_family(variant):
        out_dir = variant_output_dir(variant)
        project_suffix = variant_project_suffix(variant)
        switch_lib = KC2_FP_LIB
        switch_fp = variant_switch_footprint(variant)
        diode_lib = X3_V2_DIODE_LIB if variant == "x3-v2" else X1_DIODE_LIB
        diode_fp = X3_V2_DIODE_FP if variant == "x3-v2" else X1_DIODE_FP
        diode_value = X3_V2_DIODE_VALUE if variant == "x3-v2" else X1_DIODE_VALUE
        diode_y_offset = X2_DIODE_Y_OFFSET
        manifest_name = "kc2_generation_manifest.json" if variant == "x3" else "kc2_x3_v2_generation_manifest.json"
        if variant == "x3-v2":
            left_keys = make_left_keys_x3_v2()
            right_keys = make_right_keys_x3_v2()
        else:
            left_keys = make_left_keys_no_stab()
            right_keys = make_right_keys_no_stab()
    else:
        raise ValueError(f"Unknown variant: {variant}")

    if output_dir is not None:
        out_dir = output_dir.resolve()

    if variant in {"soldered", "hotswap", "x1"}:
        left_keys = make_left_keys()
        right_keys = make_right_keys()

    preload_embedded_footprint(switch_fp)

    left_path, left_keepout = make_board(
        "left",
        left_keys,
        out_dir,
        project_suffix=project_suffix,
        switch_lib=switch_lib,
        switch_fp=switch_fp,
        diode_lib=diode_lib,
        diode_fp=diode_fp,
        diode_value=diode_value,
        diode_y_offset=diode_y_offset,
        variant=variant,
    )
    right_path, right_keepout = make_board(
        "right",
        right_keys,
        out_dir,
        project_suffix=project_suffix,
        switch_lib=switch_lib,
        switch_fp=switch_fp,
        diode_lib=diode_lib,
        diode_fp=diode_fp,
        diode_value=diode_value,
        diode_y_offset=diode_y_offset,
        variant=variant,
    )
    notes = [
        "Antenna keepout rule areas are generated directly in the board files.",
        "Switch footprint values are sanitized as KEY_XX so Specctra DSN export does not expose legend characters such as backslash to Freerouting.",
        "Right-half R_COL7 uses D21 and R_COL8 uses D20 to keep the longer outer column on the easier controller fanout pin.",
        f"Controller protrusion tabs are aligned toward the inner joining edge: left recessed {LEFT_CONTROLLER_JOIN_EDGE_RECESS:g} mm, right recessed {RIGHT_CONTROLLER_JOIN_EDGE_RECESS:g} mm.",
        "Programming tact switch uses the smaller DeviceMart 1322056 NW3-A06-B3 SMD footprint.",
    ]
    if variant != "x3-v2":
        notes.insert(
            0,
            "SOD-123 1N4148W fallback is used because DO-35 conflicts with the compact hybrid switch footprint at 19.05 mm pitch.",
        )
    if variant == "hotswap":
        notes.append("Hot-swap variant uses the Kailh Choc V1/V2 low-profile socket footprint. MX-only Kailh sockets are not compatible with this variant.")
    elif variant == "x1":
        notes.append("X1 copies the hot-swap switch layout and replaces the diode with a local hand-solder SOD-123 footprint for DeviceMart 14592018 1N4148W.")
        notes.append("X1 right half adds 0.3 mm top outline relief to preserve board-edge clearance after autorouting with enlarged diode pads.")
    elif variant == "x2":
        notes.append("X2 copies X1's hand-solder diode choice and uses a Kailh Choc V1 footprint with both hot-swap socket pads and through-hole direct-solder pads.")
        notes.append("X2 is centered on Kailh Choc V1 / PG1350 compatibility; it does not preserve the x1 Choc V1/V2 hot-swap-only footprint.")
        notes.append(f"X2 moves diodes to y offset {X2_DIODE_Y_OFFSET:g} mm from switch center to clear the added switch THT pads.")
        notes.append("X2 right half keeps the same 0.3 mm top outline relief as X1 for board-edge clearance.")
    elif variant == "x3":
        notes.append("X3 copies X2's Kailh Choc V1 hot-swap plus direct-THT switch footprint and X1 hand-solder diode choice.")
        notes.append("X3 follows docs/spec/20.kc2-no-stabilizer-layout.md and splits every >=2U key below 2U.")
        notes.append("X3 key count is 77 total: 32 left, 45 right. Maximum physical key width is 1.75U, so no stabilizer markers are generated.")
        notes.append(f"X3 keeps X2's diode y offset of {X2_DIODE_Y_OFFSET:g} mm and uses top outline relief of 2.0 mm left / 2.5 mm right for preflight copper-edge clearance.")
        notes.append("X3 right half uses nine columns in every row; R_COL8 remains on D20 and R_COL7 remains on D21.")
        notes.append("X3 adds 0.8 mm inner-edge routing relief on both halves for the denser 77-key matrix.")
        notes.append("X3 right Y/H interlock protrusion keeps the vertical face at the 3.6 mm inner-edge margin and relieves the horizontal ledges inward by 0.8 mm.")
        notes.append(
            f"X3 compact controller tab removes J_PWR1 and carrier BAT+/BAT- nets, "
            f"trims the antenna-side tab to {X3_CONTROLLER_TAB_ANTENNA_SPAN:g} mm from U1 center, "
            f"and places SW_RST1 on the antenna side outside the TW301525 battery reference clearance."
        )
        notes.append(
            f"X3 adds one {BATTERY_LEAD_SLOT_LEN:g} x {BATTERY_LEAD_SLOT_W:g} mm mask-only NPTH "
            f"battery lead pass-through slot per half below the nice!nano B+/B- top-pin area."
        )
        notes.append("X3 screwless housing direction removes all M2 screw holes from both halves.")
        notes.append(f"X3 adds nine {REGISTRATION_HOLE_DIAMETER:g} mm NPTH REG_NPTH_3.0 registration holes per half for a PLA+ rail/capture lower tray, with visible H1-H9 support labels.")
        notes.append(f"X3 uses a {X3_GENERAL_MARGIN:g} mm nominal outer rail land, with 3.6 mm as the verified hard lower bound where local clearance requires it.")
    elif variant == "x3-v2":
        bottom_join = x3_v2_join_geometry_by_row()[-1]
        notes.append("X3 V2 uses the KC2-owned Choc V2/PG1353 bottom-side hot-swap socket plus Cherry MX 5-pin direct-solder geometry.")
        notes.append(
            "The exact Kailh Deep Sea low-profile switch MPN and controlled drawing revision "
            "remain pending; no family name or reseller nickname is order approval."
        )
        notes.append("Choc V1 switch geometry, Choc V2 direct-solder pads, and MX hot-swap socket pads are intentionally excluded.")
        notes.append("The Choc socket and MX switch are mutually exclusive assembly options at every key position.")
        notes.append("X3 V2 uses the fixed 70-key v5 no-stabilizer layout: 31 left keys and 39 right keys, with no key wider than 1.75U.")
        notes.append(
            f"X3 V2 insets every non-controller key-field edge {X3_V2_KEYCELL_EDGE_INSET:g} mm "
            f"from the nominal switch-cell perimeter. Rows 0-3 use "
            f"{X3_V2_ONE_UNIT_JOIN_CENTER_TO_EDGE:g} mm center-to-edge offsets on both sides; "
            f"bottom Space-B uses {bottom_join['left_center_to_edge_mm']:.5f} mm left / "
            f"{bottom_join['right_center_to_edge_mm']:.5f} mm right."
        )
        notes.append("X3 V2 contains no legacy H1-H9 or REG1-REG9 key-field through-holes.")
        notes.append("BAT_LEAD_SLOT1 is retained as a netless copper-free strain-relief slot; the 301230 battery remains above the carrier beneath socketed U1.")
        notes.append(
            "X3 V2 places the 301230 battery beneath socketed U1 and mirrors POWER then RESET "
            "from each USB-facing edge. J_BAT1 direct-solders insulated leads, SW_PWR1 switches "
            "BAT+ into U1 RAW/NN_B+, and B- remains on local GND. Physical stack, service, and RF validation are pending."
        )
        notes.append(
            "X3 V2 uses the exact Jingdao ES1B / LCSC C437840 / Eleparts 9475342 "
            "manufacturer-recommended SMA land on B.Cu: 1.8 x 1.8 mm pads, 2.4 mm "
            "inner gap, pin 1 cathode to row and pin 2 anode to the per-key switch net."
        )
        notes.append(
            "The ES1B placements and rotations preserve at least 1.30 mm to Edge.Cuts, "
            "1.00 mm to switch copper/unused NPTH/unrelated exposed copper, and one "
            "unobstructed 1.50 mm cardinal hand-solder approach per pad."
        )
        notes.append(
            f"X3 V2 uses the selected {len(X3_V2_MOUNTING_POINTS['left'])}-left / "
            f"{len(X3_V2_MOUNTING_POINTS['right'])}-right M1.4 retention prototype: "
            f"{X3_V2_MOUNT_HOLE_DIAMETER_MM:.2f} mm copper-free NPTHs, keycaps removed "
            "and switches installed for PH0 service. Physical pilot, torque, full-pattern "
            "fit, and deflection evidence remain pending; the board is not order-ready."
        )
    else:
        notes.append(f"Controller protrusion tab width is {CONTROLLER_TAB_W:g} mm and grows away from the inner joining edge.")
    switch_footprint_file_present = (switch_lib / f"{switch_fp}.kicad_mod").exists()
    manifest: dict[str, object] = {
        "generated": "2026-08-30" if variant == "x3-v2" else "2026-06-08",
        "variant": variant,
        **(
            {"requirement_ids": X3_V2_REQUIREMENT_IDS}
            if variant == "x3-v2"
            else {}
        ),
        **({"hash_policy": HASH_POLICY} if variant == "x3-v2" else {}),
        "generator": "tools/generate_kc2_pcbs.py",
        "generation_command": f"python tools/generate_kc2_pcbs.py --variant {variant}",
        "pcbnew_version": pcbnew.GetBuildVersion() if hasattr(pcbnew, "GetBuildVersion") else "unknown",
        "kicad_share": str(KICAD_SHARE),
        "boards": {
            "left": str(left_path.relative_to(ROOT)),
            "right": str(right_path.relative_to(ROOT)),
        },
        "antenna_keepout_mm": {
            "left": left_keepout,
            "right": right_keepout,
        },
        "switch_footprint": f"{switch_lib.name}:{switch_fp}",
        "deep_sea_switch_identity": (
            X3_V2_DEEP_SEA_SWITCH_IDENTITY if variant == "x3-v2" else None
        ),
        "assembly_modes": (
            ["choc_v2_bottom_socket", "mx_5pin_top_direct_solder"]
            if variant == "x3-v2"
            else None
        ),
        "assembly_modes_mutually_exclusive": variant == "x3-v2",
        "unsupported_switch_geometry": (
            ["choc_v1", "choc_v2_direct_solder", "mx_hotswap"]
            if variant == "x3-v2"
            else None
        ),
        "switch_footprint_file_present": switch_footprint_file_present,
        "switch_footprint_fallback_source": (
            str(EMBEDDED_FOOTPRINT_SOURCES.get(switch_fp, Path("")).relative_to(ROOT))
            if switch_fp in EMBEDDED_FOOTPRINT_SOURCES and not switch_footprint_file_present
            else None
        ),
        "diode_footprint": f"{diode_lib.name}:{diode_fp}",
        "diode_value": diode_value,
        "matrix_diode": (
            {
                "manufacturer": "Jingdao Microelectronics",
                "mpn": "ES1B",
                "lcsc": "C437840",
                "eleparts_goods_no": "9475342",
                "footprint": f"{diode_lib.name}:{diode_fp}",
                "package": "SMA",
                "assembly_side": "bottom",
                "pin_1": X3_V2_DIODE_PIN_MAPPING["1"],
                "pin_2": X3_V2_DIODE_PIN_MAPPING["2"],
                "recommended_land_mm": {"pad_size": [1.8, 1.8], "inner_gap": 2.4},
                "implemented_land_mm": {"pad_size": [1.8, 1.8], "inner_gap": 2.4, "outer_span": 6.0},
                "maximum_package_mm": {
                    "lead_span": 5.2,
                    "body_length": 4.5,
                    "body_width": 2.7,
                    "height": 2.2,
                },
            }
            if variant == "x3-v2"
            else None
        ),
        "matrix_route_clearance_mm": 0.30 if variant == "x3-v2" else None,
        "canonical_route_evidence": (
            {
                "left": canonical_x3_v2_route_record(
                    "left", 590,
                    "94c49ca2749d83cd05969e46b2afb6b610c2067ce6a2acad84790a19e081be18",
                ),
                "right": canonical_x3_v2_route_record(
                    "right", 764,
                    "b54d29e27f1f319863ec5808b31188420ad4c47fa001d21ece98db80044c6946",
                ),
            }
            if variant == "x3-v2"
            else None
        ),
        "firmware_matrix_compatibility": (
            {
                "diode_direction": "col2row",
                "pad_1": "row_cathode",
                "pad_2": "per_key_switch_anode",
                "scan_delay_changed": False,
            }
            if variant == "x3-v2"
            else None
        ),
        "physical_scan_validation": (
            {
                "status": "pending",
                "supply_volts": [3.0, 3.3],
                "patterns": ["maximum_same_row", "maximum_same_column"],
                "orderable": False,
            }
            if variant == "x3-v2"
            else None
        ),
        "diode_y_offset_mm": None if variant == "x3-v2" else diode_y_offset,
        "diode_placement_policy": (
            {
                "unrotated_switch_offset_mm": [-7.0, -7.0],
                "rotated_switch_offset_mm": [7.0, 7.0],
                "edge_safe_offsets_mm": {
                    "top_second_key": {
                        "x": X3_V2_TOP_SECOND_DIODE_OFFSET[0],
                        "y": X3_V2_TOP_SECOND_DIODE_OFFSET[1],
                        "rotation_degrees": X3_V2_TOP_SECOND_DIODE_ROTATION,
                    },
                    "top_other_keys": {
                        "x": X3_V2_TOP_OTHER_DIODE_OFFSET[0],
                        "y": X3_V2_TOP_OTHER_DIODE_OFFSET[1],
                        "rotation_degrees": X3_V2_TOP_OTHER_DIODE_ROTATION,
                    },
                    "bottom_first_key": {
                        "x": X3_V2_BOTTOM_FIRST_DIODE_OFFSET[0],
                        "y": X3_V2_BOTTOM_FIRST_DIODE_OFFSET[1],
                    },
                },
                "minimum_unused_feature_clearance_mm": 1.0,
                "minimum_fillet_to_unrelated_route_mm": 0.10,
                "minimum_edge_cuts_clearance_mm": X3_V2_MIN_DIODE_EDGE_CLEARANCE,
                "purpose": (
                    "hand-solder approach opposite the bottom-side Choc socket body while "
                    "preserving the lower-housing perimeter land"
                ),
            }
            if variant == "x3-v2"
            else None
        ),
        "controller_socket_geometry_mm": (
            {
                "longitudinal_pin_pitch": PIN_PITCH,
                "row_center_spacing": SOCKET_ROW_SPACING,
                "row_count": 2,
                "pins_per_row": 12,
            }
            if variant == "x3-v2"
            else None
        ),
        "controller_service_region": (
            {
                "top_edge_y_mm": X3_V2_TOP_EDGE_Y_MM,
                "nominal_board_height_mm": 122.50,
                "controller_body_mm": [CONTROLLER_BODY_LEN_MAX, CONTROLLER_W],
                "controller_body_source": CONTROLLER_BODY_SOURCE,
                "controller_pinout_source": CONTROLLER_PINOUT_SOURCE,
                "positions_mm": {
                    side: {
                        name: [position[0], position[1]]
                        for name, position in positions.items()
                    }
                    for side, positions in X3_V2_CONTROLLER_SERVICE_POSITIONS_MM.items()
                },
                "battery": {
                    "footprint": f"{KC2_FP_LIB.name}:{X3_V2_BATTERY_BODY_FP}",
                    "nominal_size_mm": list(X3_V2_BATTERY_SIZE_MM),
                    "placement": "between_carrier_and_socketed_controller",
                    "antenna_keepout_clearance_mm": 3.97,
                    "socket_pad_clearance_mm": 0.72,
                    "physical_stack_measurement": "pending",
                },
                "battery_termination": {
                    "footprint": f"{KC2_FP_LIB.name}:{X3_V2_BATTERY_TERMINATION_FP}",
                    "left_rotation_degrees": X3_V2_J_BAT1_ROTATIONS_DEGREES["left"],
                    "right_rotation_degrees": X3_V2_J_BAT1_ROTATIONS_DEGREES["right"],
                    "pad_1": "BAT+",
                    "pad_2": "GND",
                    **X3_V2_J_BAT1_ASSEMBLY_MARKINGS,
                    "strain_relief_ref": "BAT_LEAD_SLOT1",
                    "lead_drawing_status": "pending_exact_purchased_pack",
                },
                "power": {
                    "footprint": f"{KC2_FP_LIB.name}:{X3_V2_POWER_SWITCH_FP}",
                    "left_rotation_degrees": 0.0,
                    "right_rotation_degrees": 180.0,
                    "pad_1": "BAT+_common",
                    "pad_2": "NN_B+_on_throw",
                    "pad_3": "NC",
                    "body_size_mm": list(X3_V2_POWER_SWITCH_BODY_SIZE_MM),
                    "actuator_travel_mm": X3_V2_POWER_SWITCH_ACTUATOR_TRAVEL_MM,
                    "datasheet": X3_V2_POWER_SWITCH_DATASHEET,
                    "model": X3_V2_POWER_SWITCH_MODEL.relative_to(ROOT).as_posix(),
                    "model_sha256": sha256_file(X3_V2_POWER_SWITCH_MODEL),
                    "model_generator": X3_V2_POWER_SWITCH_MODEL_GENERATOR.relative_to(
                        ROOT
                    ).as_posix(),
                    "model_generator_sha256": sha256_file(
                        X3_V2_POWER_SWITCH_MODEL_GENERATOR
                    ),
                    "model_role": "nominal_collision_proxy",
                    "exact_purchased_mpn_status": "pending",
                    "controlled_drawing_status": "pending",
                    "imms_12v_bsi_10_equivalence_status": "pending",
                },
                "reset": {
                    "footprint": f"{KC2_FP_LIB.name}:{TACT_FP}",
                    "left_rotation_degrees": X3_V2_RESET_ROTATIONS_DEGREES["left"],
                    "right_rotation_degrees": X3_V2_RESET_ROTATIONS_DEGREES["right"],
                    "pad_1": "RST",
                    "pad_2": "GND",
                    "probe_max_diameter_mm": 3.0,
                    "placement_mode": "controller_key_gap",
                    "service_access": "nonconductive_probe",
                    "service_usb_state": "disconnected",
                },
                "nominal_clearances_mm": {
                    "controller_body_to_top_edge": 2.35,
                    "battery_to_socket_pad": 0.72,
                    "battery_to_antenna_keepout": 3.97,
                    "power_to_reset_body": 2.20,
                    "reset_keycap_envelope_mm": X3_V2_RESET_KEYCAP_ENVELOPE_MM,
                    "reset_body_to_keycap_min": X3_V2_RESET_BODY_TO_KEYCAP_MIN_MM,
                    "reset_courtyard_to_u1_socket_copper_min": (
                        X3_V2_RESET_COURTYARD_TO_U1_SOCKET_COPPER_MIN_MM
                    ),
                },
                "physical_validation": "pending_battery_power_reset_rf_first_article",
                "order_ready": False,
            }
            if variant == "x3-v2"
            else None
        ),
        "carrier_power_pads": variant == "x3-v2" or not is_x3_family(variant),
        "battery_lead_pass_through_slot": (
            {
                "footprint": f"{BATTERY_LEAD_SLOT_LIB.name}:{BATTERY_LEAD_SLOT_FP}",
                "value": BATTERY_LEAD_SLOT_VALUE,
                "size_mm": [BATTERY_LEAD_SLOT_LEN, BATTERY_LEAD_SLOT_W],
                "count_per_half": 1,
                "layers": "mask-only NPTH, no copper",
                "purpose": (
                    "J_BAT1 strain relief for pre-attached insulated battery leads; not a bottom battery exit"
                    if variant == "x3-v2"
                    else "optional bottom-side battery lead exit"
                ),
            }
            if is_x3_family(variant)
            else None
        ),
        "pcb_thickness_mm": 1.6 if is_x3_family(variant) else None,
        "housing_assumption": (
            "FDM PLA+ lower tray with external perimeter capture and independent underside supports"
            if variant == "x3-v2"
            else "FDM PLA+ screwless lower tray with printed rail/capture lips"
            if variant == "x3"
            else None
        ),
        "pcb_fastener_holes": (
            {
                "footprint": f"{X3_V2_MOUNT_LIB.name}:{X3_V2_MOUNT_FP}",
                "references": "MH1..MH8 left; MH1..MH9 right",
                "counts": {
                    "left": len(X3_V2_MOUNTING_POINTS["left"]),
                    "right": len(X3_V2_MOUNTING_POINTS["right"]),
                    "total": sum(len(points) for points in X3_V2_MOUNTING_POINTS.values()),
                },
                "positions_mm": {
                    side: [
                        {"ref": f"MH{index}", "x": x, "y": y}
                        for index, (x, y) in enumerate(points, start=1)
                    ]
                    for side, points in X3_V2_MOUNTING_POINTS.items()
                },
                "hole": {
                    "type": "NPTH",
                    "diameter_mm": X3_V2_MOUNT_HOLE_DIAMETER_MM,
                    "unnetted": True,
                    "copper_free": True,
                },
                "front_silkscreen_reference": {
                    "visible": True,
                    "text_height_mm": X3_V2_MOUNT_REFERENCE_TEXT_SIZE_MM,
                    "stroke_mm": X3_V2_MOUNT_REFERENCE_STROKE_MM,
                    "relative_position_mm": {
                        "x": X3_V2_MOUNT_REFERENCE_OFFSET_MM[0],
                        "y": X3_V2_MOUNT_REFERENCE_OFFSET_MM[1],
                    },
                },
                "screw_head_envelope_mm": {
                    "diameter": X3_V2_MOUNT_HEAD_ENVELOPE_MM[0],
                    "height": X3_V2_MOUNT_HEAD_ENVELOPE_MM[1],
                },
                "screw_head_style": X3_V2_MOUNT_HEAD_STYLE,
                "screw_head_xy_reserve_mm": X3_V2_MOUNT_HEAD_XY_RESERVE_MM,
                "vertical_driver_envelope_mm": {
                    "diameter": X3_V2_MOUNT_DRIVER_DIAMETER_MM,
                },
                "provisional_under_head_screw_length_mm": X3_V2_MOUNT_UNDER_HEAD_LENGTH_MM,
                "service_state": {"keycaps": "removed", "switches": "installed"},
                "housing_interface_mm": {
                    "zero_gap_support_land_diameter": X3_V2_MOUNT_SUPPORT_LAND_DIAMETER_MM,
                    "provisional_blind_pilot_diameter": X3_V2_MOUNT_PILOT_ENVELOPE_MM[0],
                    "provisional_blind_pilot_depth": X3_V2_MOUNT_PILOT_ENVELOPE_MM[1],
                    "desk_column_closed_bottom": X3_V2_MOUNT_CLOSED_BOTTOM_MM,
                },
                "registration_status": "pending_full_pattern_physical_fit",
                "physical_validation": "pending",
                "order_ready": False,
            }
            if variant == "x3-v2"
            else None
        ),
        "screwless_registration_holes": (
            {
                "footprint": f"{REGISTRATION_LIB.name}:{REGISTRATION_FP}",
                "diameter_mm": REGISTRATION_HOLE_DIAMETER,
                "count_per_half": 9,
                "total_count": 18,
                "purpose": "non-screw housing registration, center anti-flex support, and auxiliary capture",
                "visible_labels": "H1-H9 on B.SilkS",
            }
            if variant == "x3"
            else None
        ),
        "rail_land_mm": (
            {
                "nominal": X3_GENERAL_MARGIN,
                "hard_lower_bound": 3.6,
                "local_max_when_required": 5.0,
            }
            if variant == "x3"
            else None
        ),
        "controller_tab_width_mm": X3_CONTROLLER_TAB_W if is_x3_family(variant) else CONTROLLER_TAB_W,
        "x3_controller_tab_inner_span_mm": X3_CONTROLLER_TAB_INNER_SPAN if is_x3_family(variant) else None,
        "x3_controller_tab_outer_span_mm": X3_CONTROLLER_TAB_OUTER_SPAN if is_x3_family(variant) else None,
        "x3_controller_anchor_inner_span_mm": X3_CONTROLLER_ANCHOR_INNER_SPAN if is_x3_family(variant) else None,
        "x3_tact_battery_clearance_mm": (
            X3_TACT_BATTERY_CLEARANCE
            if is_x3_family(variant) and variant != "x3-v2"
            else None
        ),
        "key_count": {
            "left": len(left_keys),
            "right": len(right_keys),
            "total": len(left_keys) + len(right_keys),
        },
        "max_key_width_u": max(k.w_u for k in left_keys + right_keys),
        "keycell_edge_inset_mm": X3_V2_KEYCELL_EDGE_INSET if variant == "x3-v2" else None,
        "one_unit_join_center_to_edge_mm": X3_V2_ONE_UNIT_JOIN_CENTER_TO_EDGE if variant == "x3-v2" else None,
        "join_geometry_by_row": x3_v2_join_geometry_by_row() if variant == "x3-v2" else None,
        "join_keycap_setback_mm": X3_V2_JOIN_KEYCAP_SETBACK if variant == "x3-v2" else None,
        "join_keycap_gap_mm": X3_V2_JOIN_KEYCAP_GAP if variant == "x3-v2" else None,
        "one_unit_join_center_pitch_mm": X3_V2_JOIN_CENTER_PITCH if variant == "x3-v2" else None,
        "join_placement_offset_mm": X3_V2_JOIN_PLACEMENT_OFFSET if variant == "x3-v2" else None,
        "row_center_joined_pcb_gap_mm": X3_V2_ROW_CENTER_PCB_GAP if variant == "x3-v2" else None,
        "minimum_joined_edge_clearance_mm": X3_V2_MIN_JOINED_EDGE_CLEARANCE if variant == "x3-v2" else None,
        "seam_transition_stagger_mm": X3_V2_SEAM_TRANSITION_STAGGER if variant == "x3-v2" else None,
        "outline_policy": X3_V2_OUTLINE_POLICY if variant == "x3-v2" else None,
        "autoroute_boundary_policy": (
            {
                "inset_mm": X3_V2_AUTOROUTE_BOUNDARY_INSET_MM,
                "preserve_controller_above_y_mm": X3_V2_AUTOROUTE_PRESERVE_CONTROLLER_ABOVE_MM,
                "edge_cuts_unchanged": True,
            }
            if variant == "x3-v2"
            else None
        ),
        "tact_footprint": f"{KC2_FP_LIB.name}:{TACT_FP}",
        "notes": notes,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / manifest_name).write_text(
        json.dumps(manifest, indent=2), encoding="utf-8", newline="\n"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate KC2 KiCad PCB outputs.")
    parser.add_argument(
        "--variant",
        choices=(*SUPPORTED_VARIANTS, "all"),
        default="x3",
        help="PCB variant to generate. Default writes the promoted X3 main KC2 output.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Optional isolated output directory; valid only when generating one variant.",
    )
    args = parser.parse_args()

    if args.variant == "all" and args.output_dir is not None:
        parser.error("--output-dir cannot be combined with --variant all")

    if not KC2_FP_LIB.exists():
        raise SystemExit(f"Missing KC2 footprint library: {KC2_FP_LIB}")
    KICAD_ROOT.mkdir(parents=True, exist_ok=True)
    variants = SUPPORTED_VARIANTS if args.variant == "all" else (args.variant,)
    if any(variant in {"soldered", "hotswap", "x1"} for variant in variants):
        if not SWITCH_LIB.exists():
            raise SystemExit(f"Missing switch library: {SWITCH_LIB}")
        copy_license()
    manifests = [generate_variant(variant, output_dir=args.output_dir) for variant in variants]
    print(json.dumps(manifests[0] if len(manifests) == 1 else manifests, indent=2))


if __name__ == "__main__":
    main()
