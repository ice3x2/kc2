"""Generate the draft KC2 X3 V2 2.50 mm lower support plates.

The V2 design is intentionally independent of the promoted 77-key housing.
It subtracts exterior-open underside-component envelopes from the current draft
V2 board outlines, preserves the distributed load path, and adds only the
CON-ARCH-006 M1.4 MH clamp/registration columns and provisional blind pilots.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = Path(__file__).resolve()
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import generate_kc2_housings as legacy_geometry  # noqa: E402
from canonical_hash import HASH_POLICY, sha256_file  # noqa: E402


REQUIREMENT = "CON-ARCH-006"
VARIANT = "x3-v2"
OUTPUT_DIR = ROOT / "hardware" / "case" / "draft" / VARIANT
MANIFEST_PATH = OUTPUT_DIR / "kc2_x3_v2_housing_manifest.json"
BOARD_PATHS = {
    "left": ROOT / "hardware" / "kicad" / "draft" / VARIANT / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb",
    "right": ROOT / "hardware" / "kicad" / "draft" / VARIANT / "kc2_right-x3-v2" / "kc2_right-x3-v2.kicad_pcb",
}

EXTERIOR_BOTTOM_Z_MM = 0.00
HOUSING_HEIGHT_MM = 2.50
PCB_BOTTOM_Z_MM = HOUSING_HEIGHT_MM
PCB_THICKNESS_MM = 1.60
OUTLINE_INSET_MM = 0.10
RAIL_INSET_MM = 0.10
RAIL_WIDTH_MM = 0.65
POST_DIAMETER_MM = 2.40
POST_CLEARANCE_MM = 0.30
FILLET_ALLOWANCE_MM = 0.30
COMPONENT_MINIMUM_CLEARANCE_MM = 0.30
COMPONENT_CUTOUT_CLEARANCE_MM = 0.35
COMPONENT_CUTOUT_SIMPLIFY_MM = 0.02
MIN_DIODE_HOUSING_PERIMETER_LAND_MM = 0.85
MIN_SERVICE_HOUSING_PERIMETER_LAND_MM = 0.85
CHOC_SOCKET_OFFICIAL_BODY_DEPTH_MAX_MM = 2.30
CHOC_SOCKET_ASSEMBLY_ALLOWANCE_MM = 0.10
DIODE_MANUFACTURER = "Diodes Incorporated"
DIODE_MPN = "1N4148W-13-F"
DIODE_ELEPARTS_GOODS_NO = "3417687"
DIODE_OFFICIAL_BODY_DEPTH_MAX_MM = 1.35
DIODE_OFFICIAL_PLAN_ENVELOPE_MAX_MM = (2.85, 1.70)
DIODE_OFFICIAL_TERMINAL_SPAN_MAX_MM = 3.85
DIODE_SOLDER_FILLET_DEPTH_ALLOWANCE_MM = 0.30
CHOC_SOCKET_OFFICIAL_SOURCE = "https://www.kailhswitch.com/uploads/15927/files/CPG135001S30.pdf"
DIODE_OFFICIAL_SOURCE = "https://www.diodes.com/datasheet/download/1N4148W.pdf"
TRACK_CLEARANCE_MM = 0.15
BATTERY_ACCESS_CLEARANCE_MM = 0.70
BATTERY_REFERENCE = "BAT1"
BATTERY_NOMINAL_PLAN_ENVELOPE_MM = (30.00, 12.00)
BATTERY_MODELED_DEPTH_MM = 3.00
BATTERY_CENTERS_MM = {
    "left": [131.7125, 50.7500],
    "right": [78.4000, 50.7500],
}
BATTERY_TERMINATION_REFERENCE = "J_BAT1"
POWER_SWITCH_REFERENCE = "SW_PWR1"
POWER_SWITCH_DRILL_COUNT = 3
POWER_SWITCH_DRILL_DIAMETER_MM = 0.80
POWER_SWITCH_PITCH_MM = 2.54
POWER_SWITCH_BODY_ENVELOPE_MM = (10.00, 2.50)
POWER_SWITCH_ACTUATOR_TRAVEL_MM = 1.60
# The controlled drawing gives travel but no separate actuator plan width.  Use
# the complete body plus the full travel in both longitudinal directions so a
# body-only placement mutation cannot hide behind unchanged through-hole pads.
POWER_SWITCH_ACTUATOR_SWEEP_ENVELOPE_MM = (
    POWER_SWITCH_BODY_ENVELOPE_MM[0] + 2.0 * POWER_SWITCH_ACTUATOR_TRAVEL_MM,
    POWER_SWITCH_BODY_ENVELOPE_MM[1],
)
RESET_REFERENCE = "SW_RST1"
RESET_BODY_ENVELOPE_MM = (6.10, 3.70)
RESET_ACTUATOR_ENVELOPE_MM = (2.70, 1.30)
RESET_LOCAL_SUPPORT_DIAMETER_MM = 3.00
MAX_LOAD_POINT_TO_SUPPORT_MM = 4.40
PRINT_VOLUME_LIMIT_MM = 150.0
RIGHT_SPLIT_CLEARANCE_MM = 0.20
PUZZLE_CAPTURE_FEATURE_COUNT = 2
PUZZLE_NECK_WIDTH_MM = 2.00
PUZZLE_HEAD_DIAMETER_MM = 4.50
PUZZLE_NECK_LENGTH_MM = 3.00
PUZZLE_MIN_CAPTURE_PER_SIDE_MM = 1.00
DESK_STANDOFF_NOMINAL_MM = 1.00
DESK_STANDOFF_PRINT_TOLERANCE_MM = 0.30
DESK_DATUM_Z_MM = EXTERIOR_BOTTOM_Z_MM - DESK_STANDOFF_NOMINAL_MM
DESK_CONTACT_DIAMETER_MM = POST_DIAMETER_MM
MOUNTING_NPTH_DIAMETER_MM = 1.60
MOUNTING_SUPPORT_LAND_DIAMETER_MM = 3.00
MOUNTING_PILOT_DIAMETER_MM = 1.10
MOUNTING_PILOT_DEPTH_MM = 2.80
MOUNTING_PILOT_BOTTOM_Z_MM = round(
    PCB_BOTTOM_Z_MM - MOUNTING_PILOT_DEPTH_MM,
    4,
)
MOUNTING_CLOSED_BOTTOM_MM = round(
    MOUNTING_PILOT_BOTTOM_Z_MM - DESK_DATUM_Z_MM,
    4,
)
MOUNTING_FASTENER_HEAD_STYLE = "non_countersunk_rounded_pan_or_button"
MOUNTING_HEAD_DIAMETER_MM = 3.00
MOUNTING_HEAD_HEIGHT_MM = 1.20
MOUNTING_DRIVER_DIAMETER_MM = 3.00
MOUNTING_UNRELATED_SUPPORT_RESERVE_MM = 0.25
MOUNTING_HEAD_RESERVE_MM = 0.25
MOUNTING_PROVISIONAL_SCREW_UNDER_HEAD_LENGTH_MM = 4.00
PCB_THICKNESS_TOLERANCE_FRACTION = 0.10
MOUNTING_PENETRATION_RANGE_MM = (
    MOUNTING_PROVISIONAL_SCREW_UNDER_HEAD_LENGTH_MM
    - PCB_THICKNESS_MM * (1.0 + PCB_THICKNESS_TOLERANCE_FRACTION),
    MOUNTING_PROVISIONAL_SCREW_UNDER_HEAD_LENGTH_MM
    - PCB_THICKNESS_MM * (1.0 - PCB_THICKNESS_TOLERANCE_FRACTION),
)
MOUNTING_MINIMUM_TIP_CLEARANCE_MM = (
    MOUNTING_PILOT_DEPTH_MM - MOUNTING_PENETRATION_RANGE_MM[1]
)
SWITCH_SERVICE_BODY_ENVELOPE_MM = 15.60
EXPECTED_DISTRIBUTED_SUPPORT_COUNTS = {"left": 31, "right": 39}
EXPECTED_PRIMARY_SUPPORT_LOAD_SPAN_MM = {"left": 4.3902, "right": 4.3902}
KEY_LOAD_SUPPORT_TO_MOUNT_CLEARANCE_MM = 2.50
MOUNTING_HOLE_COORDINATES_MM = {
    "left": (
        ("MH1", 112.8625, 43.0000),
        ("MH2", 144.1125, 66.2500),
        ("MH3", 39.3625, 111.0000),
        ("MH4", 63.6125, 123.0000),
        ("MH5", 81.1125, 151.7500),
        ("MH6", 137.3625, 153.5000),
        ("MH7", 165.8625, 148.7500),
        ("MH8", 75.2500, 134.0000),
    ),
    "right": (
        ("MH1", 97.1875, 43.2500),
        ("MH2", 72.4375, 67.0000),
        ("MH3", 170.4375, 95.2500),
        ("MH4", 194.4375, 98.7500),
        ("MH5", 155.9375, 112.5000),
        ("MH6", 70.1875, 146.7500),
        ("MH7", 97.6875, 152.0000),
        ("MH8", 122.6875, 151.0000),
        ("MH9", 177.7500, 117.2500),
    ),
}


def has_trailing_horizontal_whitespace(path: Path) -> bool:
    return re.search(rb"[ \t]+(?=\r?\n|\Z)", path.read_bytes()) is not None


def normalize_exported_text(path: Path) -> None:
    """Strip only line-ending spaces/tabs while preserving all newline bytes."""

    original = path.read_bytes()
    normalized = re.sub(rb"[ \t]+(?=\r?\n|\Z)", b"", original)
    if normalized != original:
        path.write_bytes(normalized)


def _box(pcbnew: Any, item: Any) -> list[float]:
    bounds = item.GetBoundingBox()
    return [
        pcbnew.ToMM(bounds.GetX()),
        pcbnew.ToMM(bounds.GetY()),
        pcbnew.ToMM(bounds.GetX() + bounds.GetWidth()),
        pcbnew.ToMM(bounds.GetY() + bounds.GetHeight()),
    ]


def _point(pcbnew: Any, value: Any) -> list[float]:
    return [pcbnew.ToMM(value.x), pcbnew.ToMM(value.y)]


def _shape_box(pcbnew: Any, shape: Any) -> list[float]:
    bounds = shape.BBox()
    return [
        pcbnew.ToMM(bounds.GetX()),
        pcbnew.ToMM(bounds.GetY()),
        pcbnew.ToMM(bounds.GetX() + bounds.GetWidth()),
        pcbnew.ToMM(bounds.GetY() + bounds.GetHeight()),
    ]


def _axis_aligned_projection_size(
    size_mm: tuple[float, float], angle_deg: float
) -> list[float]:
    angle = math.radians(float(angle_deg))
    cosine = abs(math.cos(angle))
    sine = abs(math.sin(angle))
    return [
        round(size_mm[0] * cosine + size_mm[1] * sine, 4),
        round(size_mm[0] * sine + size_mm[1] * cosine, 4),
    ]


def validate_battery_termination_pad_records(
    source_name: str, pads: list[dict[str, Any]]
) -> dict[str, Any]:
    if len(pads) != 2:
        raise RuntimeError(
            f"{source_name}: {BATTERY_TERMINATION_REFERENCE} must have exactly two pads"
        )
    plated_count = sum(bool(pad.get("is_plated_through_hole")) for pad in pads)
    if plated_count != 2:
        raise RuntimeError(
            f"{source_name}: {BATTERY_TERMINATION_REFERENCE} must have two plated PTH pads"
        )
    centers = [pad.get("center", []) for pad in pads]
    sizes = [pad.get("size_mm", []) for pad in pads]
    if any(len(center) != 2 for center in centers) or any(len(size) != 2 for size in sizes):
        raise RuntimeError(
            f"{source_name}: {BATTERY_TERMINATION_REFERENCE} pad envelope is missing"
        )
    center_distance = math.hypot(
        float(centers[1][0]) - float(centers[0][0]),
        float(centers[1][1]) - float(centers[0][1]),
    )
    cutout_radii = [
        max(float(size[0]), float(size[1])) / 2.0
        + FILLET_ALLOWANCE_MM
        + COMPONENT_CUTOUT_CLEARANCE_MM
        for size in sizes
    ]
    cutout_envelopes_overlap = center_distance < sum(cutout_radii) - 1e-6
    return {
        "pad_count": 2,
        "plated_pth_count": 2,
        "pad_numbers": sorted(str(pad.get("number", "")) for pad in pads),
        "required_pad_envelope_count": 2,
        "cutout_envelopes_overlap": cutout_envelopes_overlap,
        "expected_union_opening_count": 1 if cutout_envelopes_overlap else 2,
    }


def validate_power_switch_pad_records(
    source_name: str, pads: list[dict[str, Any]]
) -> dict[str, Any]:
    if len(pads) != POWER_SWITCH_DRILL_COUNT:
        raise RuntimeError(
            f"{source_name}: {POWER_SWITCH_REFERENCE} must have exactly three pads"
        )
    if any(
        not pad.get("is_plated_through_hole") or pad.get("shape") != "circle"
        for pad in pads
    ):
        raise RuntimeError(
            f"{source_name}: {POWER_SWITCH_REFERENCE} pads must be round plated PTH"
        )
    for pad in pads:
        drill = pad.get("drill_mm", [])
        if len(drill) != 2 or any(
            abs(float(value) - POWER_SWITCH_DRILL_DIAMETER_MM) > 1e-6
            for value in drill
        ):
            raise RuntimeError(
                f"{source_name}: {POWER_SWITCH_REFERENCE} drills must be round "
                f"{POWER_SWITCH_DRILL_DIAMETER_MM:.2f} mm"
            )
    centers = [pad.get("center", []) for pad in pads]
    if any(len(center) != 2 for center in centers):
        raise RuntimeError(f"{source_name}: {POWER_SWITCH_REFERENCE} pad center is missing")
    distances = sorted(
        round(
            math.hypot(
                float(centers[right][0]) - float(centers[left][0]),
                float(centers[right][1]) - float(centers[left][1]),
            ),
            4,
        )
        for left in range(3)
        for right in range(left + 1, 3)
    )
    expected_distances = [POWER_SWITCH_PITCH_MM, POWER_SWITCH_PITCH_MM, 5.08]
    if any(
        abs(actual - expected) > 1e-4
        for actual, expected in zip(distances, expected_distances, strict=True)
    ):
        raise RuntimeError(
            f"{source_name}: {POWER_SWITCH_REFERENCE} pad distances are {distances}, "
            f"expected {expected_distances} mm"
        )
    return {
        "pad_count": 3,
        "all_round_plated_pth": True,
        "drill_count": 3,
        "drill_diameter_mm": POWER_SWITCH_DRILL_DIAMETER_MM,
        "pitch_mm": POWER_SWITCH_PITCH_MM,
        "pad_numbers": sorted(str(pad.get("number", "")) for pad in pads),
    }


def bind_battery_extraction_record(
    side: str,
    record: dict[str, Any],
    source_board: str,
    source_board_sha256: str,
) -> dict[str, Any]:
    expected_center = BATTERY_CENTERS_MM.get(side)
    if expected_center is None:
        raise RuntimeError(f"unknown X3 V2 side: {side}")
    center = record.get("center", [])
    if len(center) != 2 or any(
        abs(float(actual) - expected) > 1e-6
        for actual, expected in zip(center, expected_center, strict=True)
    ):
        raise RuntimeError(
            f"{side}: {BATTERY_REFERENCE} center is {center}, expected {expected_center}"
        )
    if not source_board or not source_board_sha256:
        raise RuntimeError(f"{side}: {BATTERY_REFERENCE} source binding is missing")
    return {
        **record,
        "side": side,
        "source_board": source_board,
        "source_board_sha256": source_board_sha256,
    }


def _normalized_service_pad(pcbnew: Any, pad: Any) -> dict[str, Any]:
    drill = pad.GetDrillSize()
    size = pad.GetSize()
    return {
        "number": pad.GetNumber(),
        "is_plated_through_hole": pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH,
        "shape": "circle" if pad.GetShape() == pcbnew.PAD_SHAPE_CIRCLE else "other",
        "drill_mm": [pcbnew.ToMM(drill.x), pcbnew.ToMM(drill.y)],
        "size_mm": [pcbnew.ToMM(size.x), pcbnew.ToMM(size.y)],
        "center": _point(pcbnew, pad.GetPosition()),
    }


def extract_board(pcbnew: Any, path: Path) -> dict[str, Any]:
    board = pcbnew.LoadBoard(str(path))
    if board is None:
        raise RuntimeError(f"Cannot load board: {path}")

    edge_segments = []
    for item in board.GetDrawings():
        if item.GetLayer() != pcbnew.Edge_Cuts or not hasattr(item, "GetStart"):
            continue
        edge_segments.append([*_point(pcbnew, item.GetStart()), *_point(pcbnew, item.GetEnd())])

    classes: dict[str, list[dict[str, Any]]] = {
        "choc_socket_body": [],
        "choc_socket_fillets": [],
        "switch_mechanical_pins": [],
        "mx_pins_pads_fillets": [],
        "diode_body_pads_fillets": [],
        "bottom_copper_tracks": [],
        "vias": [],
        "controller_socket": [],
        "reset_topside": [],
        "battery_termination": [],
        "power_switch_leads": [],
        "battery_slot": [],
    }
    switches: list[dict[str, Any]] = []
    mounting_holes: list[dict[str, Any]] = []
    routed_copper_exact: list[dict[str, Any]] = []
    bottom_mask_openings: list[dict[str, Any]] = []
    legacy_refs: list[str] = []
    reset_topside: dict[str, Any] | None = None
    battery_above_carrier: dict[str, Any] | None = None
    battery_termination_contract: dict[str, Any] | None = None
    power_switch_contract: dict[str, Any] | None = None
    power_switch_topside: dict[str, Any] | None = None
    matching_sides = [side for side, board_path in BOARD_PATHS.items() if path.resolve() == board_path.resolve()]
    if len(matching_sides) != 1:
        raise RuntimeError(f"{path.name}: cannot bind board to one X3 V2 side")
    side = matching_sides[0]
    source_board = str(path.relative_to(ROOT)).replace("\\", "/")
    source_board_sha256 = sha256_file(path)

    for drawing in board.GetDrawings():
        if drawing.GetLayer() == pcbnew.B_Mask:
            bottom_mask_openings.append(
                {
                    "kind": "box",
                    "bounds": _box(pcbnew, drawing),
                    "source": "board_graphic",
                }
            )

    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        if (ref.startswith("REG") and ref[3:].isdigit()) or (
            ref.startswith("H") and ref[1:].isdigit()
        ):
            legacy_refs.append(ref)

        pads = list(footprint.Pads())
        graphics = list(footprint.GraphicalItems())
        for pad in pads:
            if pad.IsOnLayer(pcbnew.B_Mask):
                bottom_mask_openings.append(
                    {
                        "kind": "box",
                        "bounds": _shape_box(
                            pcbnew,
                            pad.GetEffectiveShape(pcbnew.B_Mask),
                        ),
                        "source": f"{ref}.{pad.GetNumber()}",
                    }
                )
        for graphic in graphics:
            if graphic.GetLayer() == pcbnew.B_Mask:
                bottom_mask_openings.append(
                    {
                        "kind": "box",
                        "bounds": _box(pcbnew, graphic),
                        "source": ref,
                    }
                )
        if ref.startswith("MH") and ref[2:].isdigit():
            pad_records = []
            for pad in pads:
                drill = pad.GetDrillSize()
                size = pad.GetSize()
                drill_x = pcbnew.ToMM(drill.x)
                drill_y = pcbnew.ToMM(drill.y)
                size_x = pcbnew.ToMM(size.x)
                size_y = pcbnew.ToMM(size.y)
                pad_records.append(
                    {
                        "attribute": int(pad.GetAttribute()),
                        "is_npth": pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH,
                        "drill_mm": [drill_x, drill_y],
                        "size_mm": [size_x, size_y],
                        "copper_annulus_mm": round(
                            max(size_x - drill_x, size_y - drill_y) / 2.0,
                            6,
                        ),
                        "net": pad.GetNetname(),
                    }
                )
            mounting_holes.append(
                {
                    "ref": ref,
                    "center": _point(pcbnew, footprint.GetPosition()),
                    "pad_count": len(pad_records),
                    "pads": pad_records,
                }
            )
            continue

        if ref.startswith("SW") and ref[2:].isdigit():
            center = _point(pcbnew, footprint.GetPosition())
            switches.append(
                {
                    "ref": ref,
                    "center": center,
                    "angle_deg": float(footprint.GetOrientationDegrees()),
                }
            )
            body_boxes = [
                _box(pcbnew, item)
                for item in graphics
                if item.GetLayer() in (pcbnew.B_Fab, pcbnew.B_SilkS)
            ]
            if body_boxes:
                classes["choc_socket_body"].append(
                    {
                        "kind": "box",
                        "bounds": [
                            min(bounds[0] for bounds in body_boxes),
                            min(bounds[1] for bounds in body_boxes),
                            max(bounds[2] for bounds in body_boxes),
                            max(bounds[3] for bounds in body_boxes),
                        ],
                        "ref": ref,
                    }
                )
            for pad in pads:
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    classes["switch_mechanical_pins"].append(
                        {
                            "kind": "box",
                            "bounds": _box(pcbnew, pad),
                            "ref": ref,
                        }
                    )
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and pad.IsOnLayer(pcbnew.B_Cu):
                    classes["choc_socket_fillets"].append(
                        {
                            "kind": "box",
                            "bounds": _box(pcbnew, pad),
                            "allowance_mm": FILLET_ALLOWANCE_MM,
                            "ref": ref,
                        }
                    )
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                    classes["mx_pins_pads_fillets"].append(
                        {
                            "kind": "box",
                            "bounds": _box(pcbnew, pad),
                            "allowance_mm": FILLET_ALLOWANCE_MM,
                            "ref": ref,
                        }
                    )
            continue

        if ref.startswith("D") and ref[1:].isdigit():
            # The housing keepout follows the official Diodes Incorporated
            # maximum body envelope rather than nominal Fab/Silk graphics. The
            # KC2 enlarged hand-solder pads below carry their own fillet allowance.
            classes["diode_body_pads_fillets"].append(
                {
                    "kind": "oriented_box",
                    "center": _point(pcbnew, footprint.GetPosition()),
                    "size_x_mm": DIODE_OFFICIAL_PLAN_ENVELOPE_MAX_MM[0],
                    "size_y_mm": DIODE_OFFICIAL_PLAN_ENVELOPE_MAX_MM[1],
                    "angle_deg": float(footprint.GetOrientationDegrees()),
                    "ref": ref,
                }
            )
            for pad in pads:
                classes["diode_body_pads_fillets"].append(
                    {
                        "kind": "box",
                        "bounds": _box(pcbnew, pad),
                        "allowance_mm": FILLET_ALLOWANCE_MM,
                        "ref": ref,
                    }
                )
            continue

        if ref == "BAT_LEAD_SLOT1":
            for pad in pads:
                drill = pad.GetDrillSize()
                size_x = pcbnew.ToMM(drill.x) or pcbnew.ToMM(pad.GetSize().x)
                size_y = pcbnew.ToMM(drill.y) or pcbnew.ToMM(pad.GetSize().y)
                angle = float(pad.GetOrientation().AsDegrees())
                classes["battery_slot"].append(
                    {
                        "kind": "capsule",
                        "center": _point(pcbnew, pad.GetPosition()),
                        "size_x_mm": size_x,
                        "size_y_mm": size_y,
                        "angle_deg": angle,
                        "allowance_mm": BATTERY_ACCESS_CLEARANCE_MM,
                        "ref": ref,
                    }
                )
            continue

        if ref == BATTERY_REFERENCE:
            fab_points = [
                point
                for item in graphics
                if item.GetLayer() == pcbnew.F_Fab
                and hasattr(item, "GetStart")
                and hasattr(item, "GetEnd")
                for point in (
                    _point(pcbnew, item.GetStart()),
                    _point(pcbnew, item.GetEnd()),
                )
            ]
            if not fab_points:
                raise RuntimeError(f"{path.name}: {BATTERY_REFERENCE} has no F.Fab body")
            bounds = [
                min(item[0] for item in fab_points),
                min(item[1] for item in fab_points),
                max(item[0] for item in fab_points),
                max(item[1] for item in fab_points),
            ]
            size = [round(bounds[2] - bounds[0], 4), round(bounds[3] - bounds[1], 4)]
            if size != list(BATTERY_NOMINAL_PLAN_ENVELOPE_MM):
                raise RuntimeError(
                    f"{path.name}: {BATTERY_REFERENCE} F.Fab body is {size}, expected "
                    f"{list(BATTERY_NOMINAL_PLAN_ENVELOPE_MM)} mm"
                )
            battery_above_carrier = bind_battery_extraction_record(
                side,
                {
                    "ref": ref,
                    "center": _point(pcbnew, footprint.GetPosition()),
                    "bounds": bounds,
                    "size_mm": size,
                    "modeled_depth_mm": BATTERY_MODELED_DEPTH_MM,
                    "housing_body_cutout": False,
                },
                source_board,
                source_board_sha256,
            )
            continue

        if ref == BATTERY_TERMINATION_REFERENCE:
            pad_records = [_normalized_service_pad(pcbnew, pad) for pad in pads]
            battery_termination_contract = validate_battery_termination_pad_records(
                path.name, pad_records
            )
            for pad in pads:
                classes["battery_termination"].append(
                    {
                        "kind": "box",
                        "bounds": _box(pcbnew, pad),
                        "allowance_mm": FILLET_ALLOWANCE_MM,
                        "ref": ref,
                    }
                )
            continue

        if ref == POWER_SWITCH_REFERENCE:
            pad_records = [_normalized_service_pad(pcbnew, pad) for pad in pads]
            power_switch_contract = validate_power_switch_pad_records(path.name, pad_records)
            power_switch_topside = {
                "ref": ref,
                "center": _point(pcbnew, footprint.GetPosition()),
                "angle_deg": float(footprint.GetOrientationDegrees()),
                "footprint_side": "top",
                "body_size_mm": list(POWER_SWITCH_BODY_ENVELOPE_MM),
                "actuator_travel_mm": POWER_SWITCH_ACTUATOR_TRAVEL_MM,
                "actuator_sweep_size_mm": list(
                    POWER_SWITCH_ACTUATOR_SWEEP_ENVELOPE_MM
                ),
            }
            for pad in pads:
                classes["power_switch_leads"].append(
                    {
                        "kind": "box",
                        "bounds": _box(pcbnew, pad),
                        "allowance_mm": FILLET_ALLOWANCE_MM,
                        "ref": ref,
                    }
                )
            continue

        # The nice!nano socket has underside PTH/service geometry and therefore
        # receives an exterior-open cutout.  The top-side SMD reset is modeled
        # separately below so it receives local backing instead of a false
        # bottom-component opening.
        if ref == "U1":
            for item in graphics:
                if item.GetLayer() in (pcbnew.B_Fab, pcbnew.B_SilkS, pcbnew.F_Fab, pcbnew.F_SilkS):
                    classes["controller_socket"].append(
                        {"kind": "box", "bounds": _box(pcbnew, item), "ref": ref}
                    )
            for pad in pads:
                classes["controller_socket"].append(
                    {
                        "kind": "box",
                        "bounds": _box(pcbnew, pad),
                        "allowance_mm": FILLET_ALLOWANCE_MM,
                        "ref": ref,
                    }
                )
            continue

        if ref == RESET_REFERENCE:
            center = _point(pcbnew, footprint.GetPosition())
            angle = float(footprint.GetOrientationDegrees())
            pad_layers = {
                pad.GetNumber(): {
                    "front_copper": bool(pad.IsOnLayer(pcbnew.F_Cu)),
                    "bottom_copper": bool(pad.IsOnLayer(pcbnew.B_Cu)),
                    "net": pad.GetNetname(),
                }
                for pad in pads
            }
            reset_topside = {
                "ref": ref,
                "center": center,
                "angle_deg": angle,
                "footprint_side": "top",
                "body_size_mm": list(RESET_BODY_ENVELOPE_MM),
                "actuator_projection_size_mm": _axis_aligned_projection_size(
                    RESET_ACTUATOR_ENVELOPE_MM,
                    angle,
                ),
                "pad_layers": pad_layers,
                "bottom_exposed_pad_count": sum(
                    1 for item in pad_layers.values() if item["bottom_copper"]
                ),
            }
            classes["reset_topside"].append(
                {
                    "kind": "oriented_box",
                    "center": center,
                    "size_x_mm": RESET_BODY_ENVELOPE_MM[0],
                    "size_y_mm": RESET_BODY_ENVELOPE_MM[1],
                    "angle_deg": angle,
                    "ref": ref,
                    "role": "body",
                }
            )
            classes["reset_topside"].append(
                {
                    "kind": "oriented_box",
                    "center": center,
                    "size_x_mm": RESET_ACTUATOR_ENVELOPE_MM[0],
                    "size_y_mm": RESET_ACTUATOR_ENVELOPE_MM[1],
                    "angle_deg": angle,
                    "ref": ref,
                    "role": "actuator_projection",
                }
            )
            for pad in pads:
                classes["reset_topside"].append(
                    {"kind": "box", "bounds": _box(pcbnew, pad), "ref": ref, "role": "top_pad"}
                )
            continue

    for track in board.GetTracks():
        if track.GetClass() == "PCB_VIA":
            feature = {
                "kind": "circle",
                "center": _point(pcbnew, track.GetPosition()),
                "radius_mm": pcbnew.ToMM(track.GetWidth(pcbnew.F_Cu)) / 2.0,
                "net": track.GetNetname(),
                "layer": "via",
            }
            classes["vias"].append(feature)
            routed_copper_exact.append(feature)
            continue
        exact_feature = {
            "kind": "line",
            "start": _point(pcbnew, track.GetStart()),
            "end": _point(pcbnew, track.GetEnd()),
            "radius_mm": pcbnew.ToMM(track.GetWidth()) / 2.0,
            "net": track.GetNetname(),
            "layer": board.GetLayerName(track.GetLayer()),
        }
        routed_copper_exact.append(exact_feature)
        classes["bottom_copper_tracks"].append(
            {
                **exact_feature,
                "radius_mm": exact_feature["radius_mm"] + TRACK_CLEARANCE_MM,
            }
        )

    if reset_topside is None:
        raise RuntimeError(f"{path.name}: exact {RESET_REFERENCE} footprint is missing")
    if battery_above_carrier is None:
        raise RuntimeError(f"{path.name}: exact {BATTERY_REFERENCE} footprint is missing")
    if battery_termination_contract is None:
        raise RuntimeError(f"{path.name}: exact {BATTERY_TERMINATION_REFERENCE} footprint is missing")
    if power_switch_contract is None:
        raise RuntimeError(f"{path.name}: exact {POWER_SWITCH_REFERENCE} footprint is missing")
    if power_switch_topside is None:
        raise RuntimeError(
            f"{path.name}: exact {POWER_SWITCH_REFERENCE} top-side body is missing"
        )

    return {
        "path": source_board,
        "edge_segments": edge_segments,
        "switches": sorted(switches, key=lambda item: int(item["ref"][2:])),
        "mounting_holes": sorted(
            mounting_holes,
            key=lambda item: int(item["ref"][2:]),
        ),
        "routed_copper_exact": routed_copper_exact,
        "bottom_mask_openings": bottom_mask_openings,
        "reset_topside": reset_topside,
        "battery_above_carrier": battery_above_carrier,
        "power_switch_topside": power_switch_topside,
        "service_pad_contracts": {
            "battery_termination": battery_termination_contract,
            "power_switch_leads": power_switch_contract,
        },
        "legacy_registration_refs": sorted(legacy_refs),
        "feature_classes": classes,
    }


def extract_geometry() -> None:
    import pcbnew  # type: ignore[import-not-found]

    print(
        json.dumps(
            {"boards": {side: extract_board(pcbnew, path) for side, path in BOARD_PATHS.items()}},
            separators=(",", ":"),
        )
    )


def run_extractor(kicad_python: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [str(kicad_python), str(Path(__file__).resolve()), "--extract-geometry"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    start, end = proc.stdout.find("{"), proc.stdout.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError(f"KiCad housing extractor returned no JSON:\n{proc.stdout}\n{proc.stderr}")
    return json.loads(proc.stdout[start : end + 1])


def _reflect_xy(bounds: tuple[float, float, float, float], x: float, y: float) -> tuple[float, float]:
    min_x, min_y, max_x, _max_y = bounds
    return max_x - x, y - min_y


def mounting_board_contract(side: str, board_data: dict[str, Any]) -> dict[str, Any]:
    expected = MOUNTING_HOLE_COORDINATES_MM[side]
    actual = board_data.get("mounting_holes", [])
    expected_by_ref = {ref: (x, y) for ref, x, y in expected}
    actual_by_ref = {item["ref"]: item for item in actual}
    holes = []
    for ref, x, y in expected:
        item = actual_by_ref.get(ref)
        pads = [] if item is None else item.get("pads", [])
        pad = pads[0] if len(pads) == 1 else {}
        center_matches = bool(
            item is not None
            and math.isclose(float(item["center"][0]), x, abs_tol=1e-6)
            and math.isclose(float(item["center"][1]), y, abs_tol=1e-6)
        )
        npth_matches = bool(
            len(pads) == 1
            and pad.get("is_npth")
            and all(
                math.isclose(float(value), MOUNTING_NPTH_DIAMETER_MM, abs_tol=1e-6)
                for value in pad.get("drill_mm", [])
            )
            and math.isclose(float(pad.get("copper_annulus_mm", -99.0)), 0.0, abs_tol=1e-6)
            and not pad.get("net")
        )
        holes.append(
            {
                "ref": ref,
                "center_mm": [x, y],
                "present": item is not None,
                "center_matches": center_matches,
                "npth_matches": npth_matches,
                "actual": item,
            }
        )
    exact_refs = set(actual_by_ref) == set(expected_by_ref)
    return {
        "expected_count": len(expected),
        "actual_count": len(actual),
        "exact_refs": exact_refs,
        "holes": holes,
        "matches": bool(
            exact_refs
            and len(actual) == len(expected)
            and all(item["center_matches"] and item["npth_matches"] for item in holes)
        ),
    }


def _feature_geometry(shp: dict[str, Any], feature: dict[str, Any], bounds: tuple[float, float, float, float]) -> Any:
    kind = feature["kind"]
    allowance = float(feature.get("allowance_mm", 0.0))
    if kind == "box":
        x0, y0, x1, y1 = feature["bounds"]
        ax, ay = _reflect_xy(bounds, x1, y0)
        bx, by = _reflect_xy(bounds, x0, y1)
        geometry = shp["box"](min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))
    elif kind == "circle":
        x, y = _reflect_xy(bounds, *feature["center"])
        geometry = shp["Point"](x, y).buffer(float(feature["radius_mm"]), quad_segs=16)
    elif kind == "oriented_box":
        x, y = _reflect_xy(bounds, *feature["center"])
        half_x = float(feature["size_x_mm"]) / 2.0
        half_y = float(feature["size_y_mm"]) / 2.0
        geometry = shp["box"](x - half_x, y - half_y, x + half_x, y + half_y)
        angle = -float(feature.get("angle_deg", 0.0))
        if abs(angle) > 1e-9:
            geometry = shp["affinity"].rotate(geometry, angle, origin=(x, y))
    elif kind == "line":
        start = _reflect_xy(bounds, *feature["start"])
        end = _reflect_xy(bounds, *feature["end"])
        geometry = shp["LineString"]([start, end]).buffer(float(feature["radius_mm"]), cap_style="round")
    elif kind == "capsule":
        x, y = _reflect_xy(bounds, *feature["center"])
        size_x = float(feature["size_x_mm"])
        size_y = float(feature["size_y_mm"])
        radius = min(size_x, size_y) / 2.0
        length = max(size_x, size_y) - min(size_x, size_y)
        if length <= 1e-9:
            geometry = shp["Point"](x, y).buffer(radius, quad_segs=12)
        else:
            geometry = shp["LineString"]([(x - length / 2.0, y), (x + length / 2.0, y)]).buffer(
                radius, cap_style="round", quad_segs=12
            )
        angle = -float(feature.get("angle_deg", 0.0))
        if abs(angle) > 1e-9:
            geometry = shp["affinity"].rotate(geometry, angle, origin=(x, y))
    else:
        raise ValueError(f"Unsupported feature kind: {kind}")
    return geometry.buffer(allowance, join_style="round", quad_segs=4) if allowance else geometry


def _mounting_service_geometries(
    shp: dict[str, Any],
    board_data: dict[str, Any],
    bounds: tuple[float, float, float, float],
) -> dict[str, Any]:
    battery = board_data["battery_above_carrier"]
    power = board_data["power_switch_topside"]
    battery_geometry = _feature_geometry(
        shp,
        {"kind": "box", "bounds": battery["bounds"]},
        bounds,
    )
    power_body_geometry = _feature_geometry(
        shp,
        {
            "kind": "oriented_box",
            "center": power["center"],
            "size_x_mm": power["body_size_mm"][0],
            "size_y_mm": power["body_size_mm"][1],
            "angle_deg": power["angle_deg"],
        },
        bounds,
    )
    power_sweep_geometry = _feature_geometry(
        shp,
        {
            "kind": "oriented_box",
            "center": power["center"],
            "size_x_mm": power["actuator_sweep_size_mm"][0],
            "size_y_mm": power["actuator_sweep_size_mm"][1],
            "angle_deg": power["angle_deg"],
        },
        bounds,
    )
    return {
        "battery_body": battery_geometry,
        "power_switch_body": power_body_geometry,
        "power_switch_actuator_sweep": power_sweep_geometry,
    }


def build_plan_geometry(shp: dict[str, Any], side: str, board_data: dict[str, Any]) -> dict[str, Any]:
    raw_board = legacy_geometry.board_polygon(shp, board_data["edge_segments"])
    bounds = tuple(float(value) for value in raw_board.bounds)
    min_x, min_y, max_x, max_y = bounds
    translated = shp["affinity"].translate(raw_board, xoff=-min_x, yoff=-min_y)
    board = shp["affinity"].scale(
        translated,
        xfact=-1.0,
        yfact=1.0,
        origin=((max_x - min_x) / 2.0, (max_y - min_y) / 2.0),
    )
    if board.geom_type != "Polygon":
        board = max(board.geoms, key=lambda item: item.area)

    feature_geometries: dict[str, Any] = {}
    for name, features in board_data["feature_classes"].items():
        parts = [_feature_geometry(shp, feature, bounds) for feature in features]
        feature_geometries[name] = shp["unary_union"](parts) if parts else shp["Polygon"]()
    routed_copper_exact_parts = [
        _feature_geometry(shp, feature, bounds)
        for feature in board_data.get("routed_copper_exact", [])
    ]
    routed_copper_exact_geometry = (
        shp["unary_union"](routed_copper_exact_parts)
        if routed_copper_exact_parts
        else shp["Polygon"]()
    )
    bottom_mask_opening_parts = [
        _feature_geometry(shp, feature, bounds)
        for feature in board_data.get("bottom_mask_openings", [])
    ]
    bottom_mask_opening_geometry = (
        shp["unary_union"](bottom_mask_opening_parts)
        if bottom_mask_opening_parts
        else shp["Polygon"]()
    )
    mounting_service_geometries = _mounting_service_geometries(
        shp,
        board_data,
        bounds,
    )

    cutout_sources = {
        "choc_socket_body_fillets": ("choc_socket_body", "choc_socket_fillets"),
        "switch_mechanical_pins": ("switch_mechanical_pins",),
        "mx_pins_pads_fillets": ("mx_pins_pads_fillets",),
        "diode_body_pads_fillets": ("diode_body_pads_fillets",),
        "controller_socket": ("controller_socket",),
        "battery_termination": ("battery_termination",),
        "power_switch_leads": ("power_switch_leads",),
        "battery_slot": ("battery_slot",),
    }
    component_geometries: dict[str, Any] = {}
    component_cutout_geometries: dict[str, Any] = {}
    component_cutout_counts: dict[str, int] = {}
    component_envelope_coverage: dict[str, dict[str, int]] = {}
    for name, source_names in cutout_sources.items():
        sources = [feature_geometries[source] for source in source_names]
        raw = shp["unary_union"]([geometry for geometry in sources if not geometry.is_empty])
        component_geometries[name] = raw
        component_cutout_geometries[name] = (
            raw.buffer(
                COMPONENT_CUTOUT_CLEARANCE_MM,
                join_style="round",
                quad_segs=4,
            )
            if not raw.is_empty
            else shp["Polygon"]()
        )
        refs = {
            feature.get("ref")
            for source in source_names
            for feature in board_data["feature_classes"][source]
            if feature.get("ref")
        }
        component_cutout_counts[name] = len(refs)
        feature_envelopes = [
            _feature_geometry(shp, feature, bounds)
            for source in source_names
            for feature in board_data["feature_classes"][source]
        ]
        covered_envelope_count = sum(
            component_cutout_geometries[name].covers(envelope)
            for envelope in feature_envelopes
        )
        component_envelope_coverage[name] = {
            "envelope_count": len(feature_envelopes),
            "covered_envelope_count": covered_envelope_count,
            "uncovered_envelope_count": len(feature_envelopes)
            - covered_envelope_count,
        }

    housing_outline = board.buffer(-OUTLINE_INSET_MM, join_style="round", quad_segs=8)
    all_component_cutouts = shp["unary_union"](
        [geometry for geometry in component_cutout_geometries.values() if not geometry.is_empty]
    )
    support_surface = housing_outline.difference(all_component_cutouts)
    if not support_surface.is_valid:
        support_surface = support_surface.buffer(0)
    support_surface = support_surface.simplify(
        COMPONENT_CUTOUT_SIMPLIFY_MM,
        preserve_topology=True,
    )
    # Edge-adjacent component apertures can leave tiny disconnected slivers of
    # the inset outline. They cannot carry load or form a printable one-piece
    # plate, so retain only the connected primary support body.
    if support_surface.geom_type != "Polygon":
        support_surface = max(support_surface.geoms, key=lambda geometry: geometry.area)

    rail_outer = board.buffer(-RAIL_INSET_MM, join_style="round", quad_segs=16)
    rail_inner = board.buffer(-(RAIL_INSET_MM + RAIL_WIDTH_MM), join_style="round", quad_segs=16)
    rail = rail_outer.difference(rail_inner).intersection(support_surface)
    # The P1 rounded-head coordinate pattern clears the unmodified analytical
    # perimeter rail.  Keep this explicit so a stale, MH-specific notch cannot
    # silently reduce the original load path.
    analytical_rail_relief = None
    forbidden = shp["unary_union"]([geom for geom in feature_geometries.values() if not geom.is_empty])
    if not rail.is_valid:
        rail = rail.buffer(0)

    switches = [
        {
            "ref": switch["ref"],
            "center": list(_reflect_xy(bounds, *switch["center"])),
            "angle_deg": -float(switch.get("angle_deg", 0.0)),
        }
        for switch in board_data["switches"]
    ]
    switch_service_bodies = []
    for switch in switches:
        x, y = switch["center"]
        half = SWITCH_SERVICE_BODY_ENVELOPE_MM / 2.0
        body = shp["box"](x - half, y - half, x + half, y + half)
        if abs(float(switch["angle_deg"])) > 1e-9:
            body = shp["affinity"].rotate(
                body,
                float(switch["angle_deg"]),
                origin=(x, y),
            )
        switch_service_bodies.append(body)
    switch_service_body_geometry = shp["unary_union"](switch_service_bodies)
    posts = choose_support_posts(
        shp,
        side,
        support_surface,
        rail,
        all_component_cutouts,
        switches,
        bounds,
    )
    board_mounting_contract = mounting_board_contract(side, board_data)
    mounting_holes = []
    for ref, board_x, board_y in MOUNTING_HOLE_COORDINATES_MM[side]:
        x, y = _reflect_xy(bounds, board_x, board_y)
        mounting_holes.append(
            {
                "ref": ref,
                "board_center_mm": [board_x, board_y],
                "housing_center_mm": [round(x, 4), round(y, 4)],
                "land_geometry": shp["Point"](x, y).buffer(
                    MOUNTING_SUPPORT_LAND_DIAMETER_MM / 2.0,
                    quad_segs=64,
                ),
                "pilot_geometry": shp["Point"](x, y).buffer(
                    MOUNTING_PILOT_DIAMETER_MM / 2.0,
                    quad_segs=64,
                ),
                "head_geometry": shp["Point"](x, y).buffer(
                    MOUNTING_HEAD_DIAMETER_MM / 2.0,
                    quad_segs=64,
                ),
                # This is already the final service envelope. Do not add a
                # second placement reserve or driver-runout buffer here.
                "driver_geometry": shp["Point"](x, y).buffer(
                    MOUNTING_DRIVER_DIAMETER_MM / 2.0,
                    quad_segs=64,
                ),
            }
        )
    mounting_land_geometry = shp["unary_union"](
        [item["land_geometry"] for item in mounting_holes]
    )
    mounting_pilot_geometry = shp["unary_union"](
        [item["pilot_geometry"] for item in mounting_holes]
    )
    mounting_driver_geometry = shp["unary_union"](
        [item["driver_geometry"] for item in mounting_holes]
    )
    if not support_surface.covers(mounting_land_geometry):
        raise RuntimeError(f"{side}: an MH support land leaves the structural support surface")

    reset_board = board_data["reset_topside"]
    reset_x, reset_y = _reflect_xy(bounds, *reset_board["center"])
    reset_actuator_geometry = shp["box"](
        reset_x - RESET_ACTUATOR_ENVELOPE_MM[0] / 2.0,
        reset_y - RESET_ACTUATOR_ENVELOPE_MM[1] / 2.0,
        reset_x + RESET_ACTUATOR_ENVELOPE_MM[0] / 2.0,
        reset_y + RESET_ACTUATOR_ENVELOPE_MM[1] / 2.0,
    )
    reset_angle = -float(reset_board["angle_deg"])
    if abs(reset_angle) > 1e-9:
        reset_actuator_geometry = shp["affinity"].rotate(
            reset_actuator_geometry,
            reset_angle,
            origin=(reset_x, reset_y),
        )
    reset_local_support_geometry = shp["Point"](reset_x, reset_y).buffer(
        RESET_LOCAL_SUPPORT_DIAMETER_MM / 2.0,
        quad_segs=64,
    )
    if not reset_local_support_geometry.covers(reset_actuator_geometry):
        raise RuntimeError(f"{side}: reset support does not cover the actuator projection")
    if not support_surface.covers(reset_local_support_geometry):
        raise RuntimeError(f"{side}: reset local support leaves the structural support surface")
    reset_via_collision_count = sum(
        int(
            reset_local_support_geometry.intersects(
                _feature_geometry(shp, feature, bounds)
            )
        )
        for feature in board_data["feature_classes"]["vias"]
    )
    reset_bottom_route_overlap_count = sum(
        int(
            feature.get("layer") == "B.Cu"
            and reset_local_support_geometry.intersects(
                _feature_geometry(shp, feature, bounds)
            )
        )
        for feature in board_data.get("routed_copper_exact", [])
    )
    reset_bottom_mask_opening_overlap_count = int(
        reset_local_support_geometry.intersects(bottom_mask_opening_geometry)
    )
    reset_bottom_exposed_route_overlap_count = sum(
        int(
            feature.get("layer") == "B.Cu"
            and reset_local_support_geometry.intersects(
                _feature_geometry(shp, feature, bounds)
            )
            and bottom_mask_opening_geometry.intersects(
                _feature_geometry(shp, feature, bounds)
            )
        )
        for feature in board_data.get("routed_copper_exact", [])
    )
    reset_component_cutout_collision_count = int(
        reset_local_support_geometry.intersects(all_component_cutouts)
    )
    reset_electrically_safe = bool(
        int(reset_board["bottom_exposed_pad_count"]) == 0
        and reset_via_collision_count == 0
        and reset_component_cutout_collision_count == 0
        and reset_bottom_exposed_route_overlap_count == 0
    )
    if not reset_electrically_safe:
        raise RuntimeError(f"{side}: reset local support is not electrically safe")
    reset_local_support = {
        "ref": RESET_REFERENCE,
        "board_center_mm": [round(float(value), 4) for value in reset_board["center"]],
        "housing_center_mm": [round(reset_x, 4), round(reset_y, 4)],
        "footprint_side": "top",
        "footprint_rotation_deg": round(float(reset_board["angle_deg"]), 4),
        "actuator_projection_size_mm": list(reset_board["actuator_projection_size_mm"]),
        "support_diameter_mm": RESET_LOCAL_SUPPORT_DIAMETER_MM,
        "support_top_z_mm": PCB_BOTTOM_Z_MM,
        "support_vertical_gap_mm": 0.0,
        "desk_column_bottom_z_mm": DESK_DATUM_Z_MM,
        "actuator_projection_covered": True,
        "support_surface_covered": True,
        "component_cutout_collision_count": reset_component_cutout_collision_count,
        "bottom_exposed_pad_collision_count": int(reset_board["bottom_exposed_pad_count"]),
        "via_collision_count": reset_via_collision_count,
        "bottom_routed_copper_overlap_count": reset_bottom_route_overlap_count,
        "bottom_mask_opening_overlap_count": reset_bottom_mask_opening_overlap_count,
        "bottom_exposed_routed_copper_overlap_count": (
            reset_bottom_exposed_route_overlap_count
        ),
        "bottom_routed_copper_solder_mask_protected": (
            reset_bottom_exposed_route_overlap_count == 0
        ),
        "bottom_routed_copper_solder_mask_protection_basis": (
            "derived_from_exact_B.Cu_and_B.Mask_geometry"
        ),
        "electrically_safe": reset_electrically_safe,
        "electrical_safety_basis": (
            "SW_RST1 pads are F.Cu-only; no via or exterior-open cutout intersects the "
            "support, and exact B.Cu route overlap is rejected wherever an exact B.Mask "
            "opening exposes it."
        ),
    }

    distributed_desk_contacts = [
        {
            "id": post["id"].replace("-SUP-", "-FOOT-"),
            "source_support_id": post["id"],
            "category": post["category"],
            "x_mm": post["x_mm"],
            "y_mm": post["y_mm"],
            "diameter_mm": DESK_CONTACT_DIAMETER_MM,
            "top_z_mm": EXTERIOR_BOTTOM_Z_MM,
            "bottom_z_mm": DESK_DATUM_Z_MM,
            "height_mm": DESK_STANDOFF_NOMINAL_MM,
        }
        for post in posts
    ]
    mounting_desk_contacts = [
        {
            "id": f"{side.upper()}-{item['ref']}-COLUMN",
            "source_support_id": item["ref"],
            "category": "mounting",
            "x_mm": item["housing_center_mm"][0],
            "y_mm": item["housing_center_mm"][1],
            "diameter_mm": MOUNTING_SUPPORT_LAND_DIAMETER_MM,
            "top_z_mm": EXTERIOR_BOTTOM_Z_MM,
            "bottom_z_mm": DESK_DATUM_Z_MM,
            "height_mm": DESK_STANDOFF_NOMINAL_MM,
        }
        for item in mounting_holes
    ]
    reset_desk_contacts = [
        {
            "id": f"{side.upper()}-RESET-COLUMN",
            "source_support_id": RESET_REFERENCE,
            "category": "reset",
            "x_mm": round(reset_x, 4),
            "y_mm": round(reset_y, 4),
            "diameter_mm": RESET_LOCAL_SUPPORT_DIAMETER_MM,
            "top_z_mm": EXTERIOR_BOTTOM_Z_MM,
            "bottom_z_mm": DESK_DATUM_Z_MM,
            "height_mm": DESK_STANDOFF_NOMINAL_MM,
        }
    ]
    desk_contacts = distributed_desk_contacts + mounting_desk_contacts + reset_desk_contacts
    desk_contact_geometry = shp["unary_union"](
        [
            shp["Point"](contact["x_mm"], contact["y_mm"]).buffer(
                contact["diameter_mm"] / 2.0,
                quad_segs=20,
            )
            for contact in desk_contacts
        ]
    )
    if not support_surface.covers(desk_contact_geometry):
        raise RuntimeError(f"{side}: desk contacts leave the cutout-differenced structural plate")
    return {
        "board": board,
        "housing_outline": housing_outline,
        "support_surface": support_surface,
        "raw_bounds": bounds,
        "rail": rail,
        "analytical_rail_relief": analytical_rail_relief,
        "feature_geometries": feature_geometries,
        "routed_copper_exact_geometry": routed_copper_exact_geometry,
        "bottom_mask_opening_geometry": bottom_mask_opening_geometry,
        "mounting_service_geometries": mounting_service_geometries,
        "component_geometries": component_geometries,
        "component_cutout_geometries": component_cutout_geometries,
        "component_cutout_counts": component_cutout_counts,
        "component_envelope_coverage": component_envelope_coverage,
        "service_pad_contracts": board_data["service_pad_contracts"],
        "all_component_cutouts": all_component_cutouts,
        "switches": switches,
        "switch_service_body_geometry": switch_service_body_geometry,
        "support_posts": posts,
        "board_mounting_contract": board_mounting_contract,
        "mounting_holes": mounting_holes,
        "mounting_land_geometry": mounting_land_geometry,
        "mounting_pilot_geometry": mounting_pilot_geometry,
        "mounting_driver_geometry": mounting_driver_geometry,
        "reset_actuator_geometry": reset_actuator_geometry,
        "reset_local_support_geometry": reset_local_support_geometry,
        "reset_local_support": reset_local_support,
        "distributed_desk_contacts": distributed_desk_contacts,
        "mounting_desk_contacts": mounting_desk_contacts,
        "reset_desk_contacts": reset_desk_contacts,
        "desk_contacts": desk_contacts,
        "desk_contact_geometry": desk_contact_geometry,
    }


def _candidate_offsets(radius_mm: float = 13.0, step_mm: float = 0.5) -> list[tuple[float, float]]:
    limit = int(round(radius_mm / step_mm))
    values = [
        (ix * step_mm, iy * step_mm)
        for ix in range(-limit, limit + 1)
        for iy in range(-limit, limit + 1)
        if math.hypot(ix * step_mm, iy * step_mm) <= radius_mm + 1e-9
    ]
    return sorted(values, key=lambda value: (math.hypot(*value), abs(value[1]), abs(value[0]), value))


def choose_support_posts(
    shp: dict[str, Any],
    side: str,
    board: Any,
    rail: Any,
    forbidden: Any,
    switches: list[dict[str, Any]],
    raw_bounds: tuple[float, float, float, float],
) -> list[dict[str, Any]]:
    radius = POST_DIAMETER_MM / 2.0
    # A center inside this inset guarantees the complete support disk
    # plus the declared 0.30 mm component/cutout reserve remains structural.
    # The former implementation inset once and then required the complete disk
    # inside that already-inset region, unintentionally double-counting the
    # radius and leaving 15.46/18.96 mm key-load spans.
    allowed_centers = board.buffer(
        -(radius + POST_CLEARANCE_MM),
        join_style="round",
        quad_segs=16,
    )
    mount_centers = [
        _reflect_xy(raw_bounds, board_x, board_y)
        for _ref, board_x, board_y in MOUNTING_HOLE_COORDINATES_MM[side]
    ]
    minimum_mount_center_distance = (
        radius
        + MOUNTING_HEAD_DIAMETER_MM / 2.0
        + KEY_LOAD_SUPPORT_TO_MOUNT_CLEARANCE_MM
    )
    posts: list[dict[str, Any]] = []
    for switch in switches:
        target_x, target_y = switch["center"]
        selected: tuple[float, float] | None = None
        for dx, dy in _candidate_offsets(radius_mm=9.0, step_mm=0.25):
            x, y = target_x + dx, target_y + dy
            point = shp["Point"](x, y)
            if not allowed_centers.covers(point):
                continue
            if any(
                math.hypot(x - mount_x, y - mount_y)
                + 1e-9
                < minimum_mount_center_distance
                for mount_x, mount_y in mount_centers
            ):
                continue
            if any(
                math.hypot(x - item["x_mm"], y - item["y_mm"])
                + 1e-9
                < POST_DIAMETER_MM + 0.25
                for item in posts
            ):
                continue
            selected = (x, y)
            break
        if selected is None:
            raise RuntimeError(
                f"{side}: could not place a dedicated safe load support for {switch['ref']}"
            )
        x, y = selected
        load_distance = max(0.0, math.hypot(x - target_x, y - target_y) - radius)
        rail_distance = float(shp["Point"](target_x, target_y).distance(rail))
        effective_load_distance = min(load_distance, rail_distance)
        posts.append(
            {
                "id": f"{side.upper()}-{switch['ref']}-LOAD",
                "category": "key_load",
                "switch_ref": switch["ref"],
                "x_mm": round(x, 4),
                "y_mm": round(y, 4),
                "diameter_mm": POST_DIAMETER_MM,
                "bottom_z_mm": EXTERIOR_BOTTOM_Z_MM,
                "top_z_mm": PCB_BOTTOM_Z_MM,
                "nominal_vertical_gap_mm": 0.0,
                "target_x_mm": round(target_x, 4),
                "target_y_mm": round(target_y, 4),
                "load_point_to_support_edge_mm": round(load_distance, 4),
                "load_point_to_perimeter_rail_mm": round(rail_distance, 4),
                "effective_load_point_to_support_edge_mm": round(
                    effective_load_distance,
                    4,
                ),
            }
        )

    expected_refs = {switch["ref"] for switch in switches}
    actual_refs = {post["switch_ref"] for post in posts}
    if actual_refs != expected_refs or len(posts) != len(expected_refs):
        raise RuntimeError(
            f"{side}: dedicated key-load support bijection failed "
            f"({len(posts)} posts for {len(expected_refs)} switches)"
        )
    worst_post = max(
        posts,
        key=lambda post: post["effective_load_point_to_support_edge_mm"],
    )
    worst = worst_post["effective_load_point_to_support_edge_mm"]
    if worst > MAX_LOAD_POINT_TO_SUPPORT_MM + 1e-9:
        raise RuntimeError(
            f"{side}: dedicated key-load support {worst_post['switch_ref']} span "
            f"{worst:.4f} mm exceeds "
            f"{MAX_LOAD_POINT_TO_SUPPORT_MM:.2f} mm "
            f"(disk={worst_post['load_point_to_support_edge_mm']}; "
            f"rail={worst_post['load_point_to_perimeter_rail_mm']})"
        )
    return posts


def _polygon_workplane(cq: Any, polygon: Any) -> Any:
    outer = [(float(x), float(y)) for x, y in list(polygon.exterior.coords)[:-1]]
    workplane = cq.Workplane("XY").polyline(outer).close()
    for ring in polygon.interiors:
        workplane = workplane.polyline([(float(x), float(y)) for x, y in list(ring.coords)[:-1]]).close()
    return workplane


def _extrude_geometry(cq: Any, geometry: Any, height: float, z_offset: float = 0.0) -> Any | None:
    if geometry.is_empty:
        return None
    parts = [geometry] if geometry.geom_type == "Polygon" else list(geometry.geoms)
    solids = []
    for polygon in parts:
        if polygon.area <= 1e-5:
            continue
        solid = _polygon_workplane(cq, polygon).extrude(height)
        if z_offset:
            solid = solid.translate((0.0, 0.0, z_offset))
        solids.append(solid)
    if not solids:
        return None
    result = solids[0]
    for solid in solids[1:]:
        result = result.union(solid)
    return result


def build_cad(cq: Any, shp: dict[str, Any], plan: dict[str, Any]) -> Any:
    # Extrude the already-differenced support surface directly. This produces
    # the same exterior-open component apertures without an expensive sequence
    # of hundreds of 3D boolean cuts.
    housing = _extrude_geometry(cq, plan["support_surface"], HOUSING_HEIGHT_MM)
    if housing is None:
        raise RuntimeError("component cutouts removed the entire housing support surface")
    feet = _extrude_geometry(
        cq,
        plan["desk_contact_geometry"],
        DESK_STANDOFF_NOMINAL_MM,
        DESK_DATUM_Z_MM,
    )
    if feet is None:
        raise RuntimeError("desk-contact generation produced no solid")
    pilot_solids = []
    for item in plan["mounting_holes"]:
        x, y = item["housing_center_mm"]
        cutter = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(MOUNTING_PILOT_DIAMETER_MM / 2.0)
            .extrude(MOUNTING_PILOT_DEPTH_MM + 0.10)
            .translate((0.0, 0.0, MOUNTING_PILOT_BOTTOM_Z_MM))
        )
        pilot_solids.append(cutter.val())
    pilot_cutters = cq.Workplane(obj=cq.Compound.makeCompound(pilot_solids))
    return housing.union(feet).cut(pilot_cutters).clean()


def _support_plan_union(shp: dict[str, Any], posts: list[dict[str, Any]]) -> Any:
    return shp["unary_union"](
        [
            shp["Point"](post["x_mm"], post["y_mm"]).buffer(
                post["diameter_mm"] / 2.0,
                quad_segs=20,
            )
            for post in posts
        ]
    )


def desk_contacts_for_part(
    shp: dict[str, Any],
    plan: dict[str, Any],
    part_plan: Any,
) -> list[dict[str, Any]]:
    contacts = []
    for contact in plan["desk_contacts"]:
        disk = shp["Point"](contact["x_mm"], contact["y_mm"]).buffer(
            contact["diameter_mm"] / 2.0,
            quad_segs=20,
        )
        if part_plan.covers(disk):
            contacts.append(contact)
    return contacts


def desk_contact_stability_manifest(
    shp: dict[str, Any],
    part_plan: Any,
    contacts: list[dict[str, Any]],
) -> dict[str, Any]:
    centers = [(float(item["x_mm"]), float(item["y_mm"])) for item in contacts]
    hull = shp["unary_union"]([shp["Point"](*center) for center in centers]).convex_hull
    centroid = part_plan.centroid
    non_collinear = len(contacts) >= 3 and float(hull.area) > 1e-6
    centroid_inside = non_collinear and hull.covers(centroid)
    bottom_z_values = [float(item["bottom_z_mm"]) for item in contacts]
    coplanarity = 0.0 if not bottom_z_values else max(bottom_z_values) - min(bottom_z_values)
    return {
        "desk_contact_ids": [item["id"] for item in contacts],
        "desk_contact_count": len(contacts),
        "desk_contact_z_mm": DESK_DATUM_Z_MM,
        "desk_contact_coplanarity_mm": round(coplanarity, 6),
        "desk_contact_hull_area_mm2": round(float(hull.area), 4),
        "projected_plate_centroid_mm": [round(float(centroid.x), 4), round(float(centroid.y), 4)],
        "projected_centroid_inside_contact_hull": bool(centroid_inside),
        "desk_contacts_non_collinear": bool(non_collinear),
        "desk_contacts_statically_stable": bool(
            len(contacts) >= 3 and non_collinear and centroid_inside and coplanarity <= 1e-6
        ),
    }


def mounting_system_manifest(
    shp: dict[str, Any],
    side: str,
    plan: dict[str, Any],
    part_plans: list[Any],
) -> dict[str, Any]:
    part_names = ["whole"] if side == "left" else ["part_a", "part_b"]
    existing_support_posts = _support_plan_union(
        shp,
        plan["support_posts"],
    ).union(
        plan["reset_local_support_geometry"]
    )
    analytical_rail = plan["rail"]
    existing_supports = existing_support_posts.union(analytical_rail)
    raised_or_component_features = shp["unary_union"](
        [
            geometry
            for name, geometry in plan["feature_geometries"].items()
            if name not in {"bottom_copper_tracks", "vias"}
            if not geometry.is_empty
        ]
    )
    installed_component_geometry = shp["unary_union"](
        [
            plan["switch_service_body_geometry"],
            raised_or_component_features,
            *plan["mounting_service_geometries"].values(),
        ]
    )
    split_slot = shp["Polygon"]()
    if side == "right":
        split_slot = build_right_split_plan(shp, plan)["slot_union"]
    board_holes = {
        item["ref"]: item
        for item in plan["board_mounting_contract"]["holes"]
    }
    holes = []
    distribution: dict[str, int] = {}
    for item in plan["mounting_holes"]:
        ref = item["ref"]
        support_land_to_existing_support = float(
            item["land_geometry"].distance(existing_supports)
        )
        head_to_existing_support = float(
            item["head_geometry"].distance(existing_supports)
        )
        head_to_support_posts = float(
            item["head_geometry"].distance(existing_support_posts)
        )
        head_to_analytical_rail = float(
            item["head_geometry"].distance(analytical_rail)
        )
        head_to_installed_component = float(
            item["head_geometry"].distance(installed_component_geometry)
        )
        head_to_routed_copper_or_via = float(
            item["head_geometry"].distance(plan["routed_copper_exact_geometry"])
        )
        head_to_board_edge = float(
            item["head_geometry"].distance(plan["board"].boundary)
        )
        head_to_housing_edge = float(
            item["head_geometry"].distance(plan["housing_outline"].boundary)
        )
        driver_to_battery_body = float(
            item["driver_geometry"].distance(
                plan["mounting_service_geometries"]["battery_body"]
            )
        )
        driver_to_power_switch_body = float(
            item["driver_geometry"].distance(
                plan["mounting_service_geometries"]["power_switch_body"]
            )
        )
        driver_to_power_switch_actuator_sweep = float(
            item["driver_geometry"].distance(
                plan["mounting_service_geometries"][
                    "power_switch_actuator_sweep"
                ]
            )
        )
        containing_parts = [
            name
            for name, part_plan in zip(part_names, part_plans)
            if part_plan.covers(item["land_geometry"])
        ]
        printable_part = containing_parts[0] if len(containing_parts) == 1 else "unassigned"
        distribution[printable_part] = distribution.get(printable_part, 0) + 1
        checks = {
            "support_land_leaves_support_surface": not plan["support_surface"].covers(
                item["land_geometry"]
            ),
            "support_land_component_cutout": item["land_geometry"].intersects(
                plan["all_component_cutouts"]
            ),
            "support_land_existing_support": item["land_geometry"].intersects(
                existing_supports
            ),
            "support_land_existing_support_reserve": (
                support_land_to_existing_support
                + 1e-9
                < MOUNTING_UNRELATED_SUPPORT_RESERVE_MM
            ),
            "head_existing_support_reserve": (
                head_to_existing_support
                + 1e-9
                < MOUNTING_UNRELATED_SUPPORT_RESERVE_MM
            ),
            "head_support_post_reserve": (
                head_to_support_posts + 1e-9 < MOUNTING_HEAD_RESERVE_MM
            ),
            "head_analytical_rail_reserve": (
                head_to_analytical_rail + 1e-9 < MOUNTING_HEAD_RESERVE_MM
            ),
            "head_installed_component_reserve": (
                head_to_installed_component + 1e-9 < MOUNTING_HEAD_RESERVE_MM
            ),
            "head_routed_copper_or_via_reserve": (
                head_to_routed_copper_or_via + 1e-9 < MOUNTING_HEAD_RESERVE_MM
            ),
            "head_board_edge_reserve": (
                not plan["board"].covers(item["head_geometry"])
                or head_to_board_edge + 1e-9 < MOUNTING_HEAD_RESERVE_MM
            ),
            "head_housing_edge_reserve": (
                not plan["housing_outline"].covers(item["head_geometry"])
                or head_to_housing_edge + 1e-9 < MOUNTING_HEAD_RESERVE_MM
            ),
            "pilot_component_cutout": item["pilot_geometry"].intersects(
                plan["all_component_cutouts"]
            ),
            "head_leaves_housing_outline": not plan["housing_outline"].covers(
                item["head_geometry"]
            ),
            "driver_leaves_housing_outline": not plan["housing_outline"].covers(
                item["driver_geometry"]
            ),
            "driver_switch_body": item["driver_geometry"].intersects(
                plan["switch_service_body_geometry"]
            ),
            "driver_component": item["driver_geometry"].intersects(
                raised_or_component_features
            ),
            "driver_battery_body": item["driver_geometry"].intersects(
                plan["mounting_service_geometries"]["battery_body"]
            ),
            "driver_power_switch_body": item["driver_geometry"].intersects(
                plan["mounting_service_geometries"]["power_switch_body"]
            ),
            "driver_power_switch_actuator_sweep": item[
                "driver_geometry"
            ].intersects(
                plan["mounting_service_geometries"][
                    "power_switch_actuator_sweep"
                ]
            ),
            "driver_routed_copper_or_via": item["driver_geometry"].intersects(
                plan["routed_copper_exact_geometry"]
            ),
            "right_split_feature": (
                side == "right"
                and (
                    item["land_geometry"].intersects(split_slot)
                    or item["pilot_geometry"].intersects(split_slot)
                )
            ),
            "part_assignment": len(containing_parts) != 1,
        }
        board_hole = board_holes[ref]
        holes.append(
            {
                "ref": ref,
                "board_center_mm": item["board_center_mm"],
                "housing_center_mm": item["housing_center_mm"],
                "printable_part": printable_part,
                "pcb_npth_diameter_mm": MOUNTING_NPTH_DIAMETER_MM,
                "board_feature_matches": bool(
                    board_hole["center_matches"] and board_hole["npth_matches"]
                ),
                "support_land_diameter_mm": MOUNTING_SUPPORT_LAND_DIAMETER_MM,
                "support_land_annular_width_mm": round(
                    (MOUNTING_SUPPORT_LAND_DIAMETER_MM - MOUNTING_PILOT_DIAMETER_MM)
                    / 2.0,
                    4,
                ),
                "support_land_top_z_mm": PCB_BOTTOM_Z_MM,
                "support_land_vertical_gap_mm": 0.0,
                "support_land_to_existing_support_mm": round(
                    support_land_to_existing_support,
                    4,
                ),
                "head_to_existing_support_mm": round(
                    head_to_existing_support,
                    4,
                ),
                "head_to_support_posts_mm": round(head_to_support_posts, 4),
                "head_to_analytical_rail_mm": round(
                    head_to_analytical_rail,
                    4,
                ),
                "head_to_installed_component_mm": round(
                    head_to_installed_component,
                    4,
                ),
                "head_to_routed_copper_or_via_mm": round(
                    head_to_routed_copper_or_via,
                    4,
                ),
                "head_to_board_edge_mm": round(head_to_board_edge, 4),
                "head_to_housing_edge_mm": round(head_to_housing_edge, 4),
                "head_reserve_mm": MOUNTING_HEAD_RESERVE_MM,
                "minimum_unrelated_support_reserve_mm": (
                    MOUNTING_UNRELATED_SUPPORT_RESERVE_MM
                ),
                "desk_column_diameter_mm": MOUNTING_SUPPORT_LAND_DIAMETER_MM,
                "desk_column_bottom_z_mm": DESK_DATUM_Z_MM,
                "pilot_diameter_mm": MOUNTING_PILOT_DIAMETER_MM,
                "pilot_depth_mm": MOUNTING_PILOT_DEPTH_MM,
                "pilot_top_z_mm": PCB_BOTTOM_Z_MM,
                "pilot_bottom_z_mm": MOUNTING_PILOT_BOTTOM_Z_MM,
                "pilot_extension_below_plate_mm": round(
                    EXTERIOR_BOTTOM_Z_MM - MOUNTING_PILOT_BOTTOM_Z_MM,
                    4,
                ),
                "closed_bottom_to_desk_datum_mm": MOUNTING_CLOSED_BOTTOM_MM,
                "pilot_breaks_desk_contact_bottom": (
                    MOUNTING_PILOT_BOTTOM_Z_MM <= DESK_DATUM_Z_MM
                ),
                "provisional_screw_under_head_length_mm": (
                    MOUNTING_PROVISIONAL_SCREW_UNDER_HEAD_LENGTH_MM
                ),
                "pcb_tolerance_penetration_range_mm": [
                    round(value, 4) for value in MOUNTING_PENETRATION_RANGE_MM
                ],
                "minimum_tip_clearance_mm": round(
                    MOUNTING_MINIMUM_TIP_CLEARANCE_MM,
                    4,
                ),
                "head_envelope_mm": [
                    MOUNTING_HEAD_DIAMETER_MM,
                    MOUNTING_HEAD_HEIGHT_MM,
                ],
                "driver_envelope_diameter_mm": MOUNTING_DRIVER_DIAMETER_MM,
                "driver_to_battery_body_mm": round(driver_to_battery_body, 4),
                "driver_to_power_switch_body_mm": round(
                    driver_to_power_switch_body,
                    4,
                ),
                "driver_to_power_switch_actuator_sweep_mm": round(
                    driver_to_power_switch_actuator_sweep,
                    4,
                ),
                "service_condition": "keycaps-off, switches-installed",
                "collision_checks": checks,
                "collision_count": sum(bool(value) for value in checks.values()),
            }
        )
    expected_distribution = (
        {"whole": len(MOUNTING_HOLE_COORDINATES_MM[side])}
        if side == "left"
        else {"part_a": 5, "part_b": 4}
    )
    support_refs = [post.get("switch_ref") for post in plan["support_posts"]]
    expected_support_refs = [switch["ref"] for switch in plan["switches"]]
    key_load_network_matches = bool(
        len(support_refs) == len(expected_support_refs)
        and len(set(support_refs)) == len(support_refs)
        and set(support_refs) == set(expected_support_refs)
        and all(post.get("category") == "key_load" for post in plan["support_posts"])
        and max(
            post.get("effective_load_point_to_support_edge_mm", float("inf"))
            for post in plan["support_posts"]
        )
        <= MAX_LOAD_POINT_TO_SUPPORT_MM
    )
    return {
        "fastener_envelope": (
            "M1.4 provisional direct-plastic prototype; non-countersunk "
            "rounded pan/button head"
        ),
        "fastener_head_style": MOUNTING_FASTENER_HEAD_STYLE,
        "head_envelope_mm": [
            MOUNTING_HEAD_DIAMETER_MM,
            MOUNTING_HEAD_HEIGHT_MM,
        ],
        "head_reserve_mm": MOUNTING_HEAD_RESERVE_MM,
        "head_height_and_keycap_skirt_physical_status": "pending",
        "physical_registration_status": "pending",
        "count": len(holes),
        "board_coordinates_mm": [
            [x, y] for _ref, x, y in MOUNTING_HOLE_COORDINATES_MM[side]
        ],
        "board_features_match_selected_pattern": bool(
            plan["board_mounting_contract"]["matches"]
        ),
        "holes": holes,
        "analytical_rail_relief": plan["analytical_rail_relief"],
        "minimum_unrelated_support_reserve_mm": (
            MOUNTING_UNRELATED_SUPPORT_RESERVE_MM
        ),
        "service_body_envelopes": {
            "battery_body_size_mm": list(BATTERY_NOMINAL_PLAN_ENVELOPE_MM),
            "power_switch_body_size_mm": list(POWER_SWITCH_BODY_ENVELOPE_MM),
            "power_switch_actuator_travel_mm": POWER_SWITCH_ACTUATOR_TRAVEL_MM,
            "power_switch_actuator_sweep_size_mm": list(
                POWER_SWITCH_ACTUATOR_SWEEP_ENVELOPE_MM
            ),
        },
        "part_distribution": distribution,
        "expected_part_distribution": expected_distribution,
        "part_distribution_matches_plan": distribution == expected_distribution,
        "distributed_support_count": len(plan["support_posts"]),
        "dedicated_key_load_support_count": len(plan["support_posts"]),
        "all_key_loads_have_dedicated_support": key_load_network_matches,
        "key_load_support_network_matches_contract": key_load_network_matches,
        "primary_support_load_span_unchanged": bool(
            key_load_network_matches
            and len(plan["support_posts"]) == EXPECTED_DISTRIBUTED_SUPPORT_COUNTS[side]
            and math.isclose(
                _maximum_load_distance(shp, plan),
                EXPECTED_PRIMARY_SUPPORT_LOAD_SPAN_MM[side],
                abs_tol=0.0001,
            )
        ),
    }




def _puzzle_key_geometry(shp: dict[str, Any], split_x: float, y: float) -> Any:
    half_gap = RIGHT_SPLIT_CLEARANCE_MM / 2.0
    head_x = split_x + PUZZLE_NECK_LENGTH_MM
    neck = shp["box"](
        split_x - half_gap,
        y - PUZZLE_NECK_WIDTH_MM / 2.0,
        head_x,
        y + PUZZLE_NECK_WIDTH_MM / 2.0,
    )
    head = shp["Point"](head_x, y).buffer(
        PUZZLE_HEAD_DIAMETER_MM / 2.0,
        quad_segs=24,
    )
    return neck.union(head)


def build_right_split_plan(shp: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    min_x, min_y, max_x, max_y = plan["housing_outline"].bounds
    split_x = (min_x + max_x) / 2.0
    half_gap = RIGHT_SPLIT_CLEARANCE_MM / 2.0
    margin = 2.0
    explicit_supports = (
        _support_plan_union(shp, plan["support_posts"])
        .union(plan["rail"])
        .union(plan["mounting_land_geometry"])
        .union(plan["reset_local_support_geometry"])
    )
    component_cutouts = plan["all_component_cutouts"]
    capture_points: list[dict[str, float]] = []
    keys: list[Any] = []
    # Preserve the proven absolute board-Y capture locations when the compact
    # controller crop changes the board-local minimum Y.  Offsets from the
    # housing top would silently move the joint relative to the fixed key/MH
    # datum after CON-ARCH-006 AC-11.
    # The enlarged P3 one-per-key desk contacts leave an exact collision-free
    # second capture lane at board Y=125.50 mm; the historical 125.60 mm lane
    # touches a support disk after the 2.40 mm support enlargement.
    for target_board_y in (113.10, 125.50):
        target_y = target_board_y - float(plan["raw_bounds"][1])
        found = False
        for y_offset in (
            0.0,
            0.5,
            -0.5,
            1.0,
            -1.0,
            1.5,
            -1.5,
            2.0,
            -2.0,
            2.5,
            -2.5,
            3.0,
            -3.0,
            4.0,
            -4.0,
            5.0,
            -5.0,
        ):
            y = target_y + y_offset
            key = _puzzle_key_geometry(shp, split_x, y)
            slot = key.buffer(RIGHT_SPLIT_CLEARANCE_MM, join_style="round", quad_segs=20)
            if not plan["housing_outline"].covers(slot):
                continue
            if slot.intersects(component_cutouts) or slot.intersects(explicit_supports):
                continue
            if any(abs(y - point["y_mm"]) < PUZZLE_HEAD_DIAMETER_MM + 4.0 for point in capture_points):
                continue
            capture_points.append(
                {
                    "x_mm": round(split_x + PUZZLE_NECK_LENGTH_MM, 4),
                    "y_mm": round(y, 4),
                }
            )
            keys.append(key)
            found = True
            break
        if not found:
            raise RuntimeError(
                f"right: could not place keyed puzzle feature near board Y={target_board_y}"
            )
    if len(keys) != PUZZLE_CAPTURE_FEATURE_COUNT:
        raise RuntimeError(f"right: expected {PUZZLE_CAPTURE_FEATURE_COUNT} puzzle keys, got {len(keys)}")

    left_base = shp["box"](min_x - margin, min_y - margin, split_x - half_gap, max_y + margin)
    right_base = shp["box"](split_x + half_gap, min_y - margin, max_x + margin, max_y + margin)
    key_union = shp["unary_union"](keys)
    slot_union = key_union.buffer(RIGHT_SPLIT_CLEARANCE_MM, join_style="round", quad_segs=20)
    part_a_plan_raw = plan["support_surface"].intersection(left_base.union(key_union))
    part_b_plan_raw = plan["support_surface"].intersection(right_base.difference(slot_union))

    def primary_polygon(geometry: Any, name: str) -> tuple[Any, float]:
        if geometry.geom_type == "Polygon":
            return geometry, 0.0
        polygons = [polygon for polygon in geometry.geoms if polygon.area > 1e-6]
        primary = max(polygons, key=lambda polygon: polygon.area)
        discarded_ratio = 1.0 - float(primary.area) / float(sum(polygon.area for polygon in polygons))
        if discarded_ratio > 0.02:
            raise RuntimeError(
                f"right keyed split would discard {discarded_ratio:.3%} of {name}; "
                "the split path must be redesigned"
            )
        return primary, discarded_ratio

    part_a_plan, part_a_discarded = primary_polygon(part_a_plan_raw, "part_a")
    part_b_plan, part_b_discarded = primary_polygon(part_b_plan_raw, "part_b")
    return {
        "split_x_mm": round(split_x, 4),
        "capture_points": capture_points,
        "key_union": key_union,
        "slot_union": slot_union,
        "part_a_mask": part_a_plan,
        "part_b_mask": part_b_plan,
        "part_a_plan": part_a_plan,
        "part_b_plan": part_b_plan,
        "discarded_island_area_ratio": [
            round(part_a_discarded, 6),
            round(part_b_discarded, 6),
        ],
        "planned_top_contact_area_mm2": round(
            float(
                part_a_plan.union(part_b_plan)
                .difference(plan["mounting_pilot_geometry"])
                .area
            ),
            4,
        ),
    }


def split_right_housing_keyed(
    cq: Any,
    shp: dict[str, Any],
    housing: Any,
    plan: dict[str, Any],
) -> tuple[list[Any], dict[str, Any]]:
    split_plan = build_right_split_plan(shp, plan)
    part_a_cutter = _extrude_geometry(
        cq,
        split_plan["part_a_mask"],
        HOUSING_HEIGHT_MM - DESK_DATUM_Z_MM + 0.20,
        DESK_DATUM_Z_MM - 0.10,
    )
    part_b_cutter = _extrude_geometry(
        cq,
        split_plan["part_b_mask"],
        HOUSING_HEIGHT_MM - DESK_DATUM_Z_MM + 0.20,
        DESK_DATUM_Z_MM - 0.10,
    )
    raw_parts = [housing.intersect(part_a_cutter).clean(), housing.intersect(part_b_cutter).clean()]
    parts: list[Any] = []
    discarded_island_volume_ratio: list[float] = []
    for name, raw_part in zip(("part_a", "part_b"), raw_parts):
        solids = raw_part.solids().vals()
        if not solids:
            raise RuntimeError(f"right keyed split produced no solid for {name}")
        total_volume = sum(float(solid.Volume()) for solid in solids)
        primary = max(solids, key=lambda solid: float(solid.Volume()))
        discarded_ratio = 1.0 - float(primary.Volume()) / total_volume
        if discarded_ratio > 0.02:
            raise RuntimeError(
                f"right keyed split would discard {discarded_ratio:.3%} of {name}; "
                "the split path must be redesigned"
            )
        parts.append(cq.Workplane(obj=primary).clean())
        discarded_island_volume_ratio.append(round(discarded_ratio, 6))
    capture = (PUZZLE_HEAD_DIAMETER_MM - PUZZLE_NECK_WIDTH_MM) / 2.0
    metadata = {
        "type": "full_depth_vertical_keyed_puzzle",
        "part_count": 2,
        "split_x_mm": split_plan["split_x_mm"],
        "nominal_plan_clearance_mm": RIGHT_SPLIT_CLEARANCE_MM,
        "joint_height_mm": HOUSING_HEIGHT_MM,
        "assembly_direction": "vertical",
        "capture_feature_count": len(split_plan["capture_points"]),
        "capture_points": split_plan["capture_points"],
        "neck_width_mm": PUZZLE_NECK_WIDTH_MM,
        "head_width_mm": PUZZLE_HEAD_DIAMETER_MM,
        "neck_length_mm": PUZZLE_NECK_LENGTH_MM,
        "minimum_in_plane_capture_per_side_mm": round(capture, 4),
        "positive_x_capture": capture >= PUZZLE_MIN_CAPTURE_PER_SIDE_MM,
        "fastener_count": 0,
        "discarded_island_area_ratio": split_plan["discarded_island_area_ratio"],
        "discarded_island_volume_ratio": discarded_island_volume_ratio,
        "glue_assumed": False,
        "feature_collision_count": 0,
        "support_collision_count": 0,
        "planned_top_contact_area_mm2": split_plan["planned_top_contact_area_mm2"],
        "assembly": (
            "Lower the two full-depth housing parts together vertically so both keyed "
            "neck-and-head features enter their print-cleared sockets; no screw or adhesive is used."
        ),
    }
    return parts, metadata


def model_bounds(model: Any) -> dict[str, list[float]]:
    bounds = model.val().BoundingBox()
    return {
        "bounds_xyz_mm": [
            round(float(bounds.xmin), 4),
            round(float(bounds.ymin), 4),
            round(float(bounds.zmin), 4),
            round(float(bounds.xmax), 4),
            round(float(bounds.ymax), 4),
            round(float(bounds.zmax), 4),
        ],
        "size_xyz_mm": [
            round(float(bounds.xlen), 4),
            round(float(bounds.ylen), 4),
            round(float(bounds.zlen), 4),
        ],
    }


def _maximum_load_distance(shp: dict[str, Any], plan: dict[str, Any]) -> float:
    radius = POST_DIAMETER_MM / 2.0
    distances = []
    for switch in plan["switches"]:
        point = shp["Point"](*switch["center"])
        post_distance = min(
            max(0.0, point.distance(shp["Point"](post["x_mm"], post["y_mm"])) - radius)
            for post in plan["support_posts"]
        )
        distances.append(min(point.distance(plan["rail"]), post_distance))
    return max(distances)


def _maximum_seam_support_distance(shp: dict[str, Any], side: str, plan: dict[str, Any]) -> float:
    min_x, _min_y, max_x, _max_y = plan["board"].bounds
    seam_x = min_x if side == "left" else max_x
    ordered = sorted(
        plan["switches"],
        key=lambda switch: abs(float(switch["center"][0]) - seam_x),
    )
    seam_switches = ordered[:5]
    return max(
        float(shp["Point"](*switch["center"]).distance(plan["support_surface"]))
        for switch in seam_switches
    )


def component_cutout_manifest(plan: dict[str, Any]) -> dict[str, Any]:
    battery_termination_contract = plan["service_pad_contracts"]["battery_termination"]
    power_switch_contract = plan["service_pad_contracts"]["power_switch_leads"]
    battery_termination_coverage = plan["component_envelope_coverage"][
        "battery_termination"
    ]
    modeled_depths = {
        "choc_socket_body_fillets": {
            "official_body_depth_max_mm": CHOC_SOCKET_OFFICIAL_BODY_DEPTH_MAX_MM,
            "assembly_allowance_mm": CHOC_SOCKET_ASSEMBLY_ALLOWANCE_MM,
            "modeled_max_depth_mm": round(
                CHOC_SOCKET_OFFICIAL_BODY_DEPTH_MAX_MM + CHOC_SOCKET_ASSEMBLY_ALLOWANCE_MM,
                2,
            ),
            "official_source": CHOC_SOCKET_OFFICIAL_SOURCE,
        },
        "switch_mechanical_pins": {
            "official_body_depth_max_mm": None,
            "assembly_allowance_mm": None,
            "modeled_max_depth_mm": None,
            "assembly_note": "Exterior-open cutouts continue every switch NPTH below the PCB.",
        },
        "mx_pins_pads_fillets": {
            "official_body_depth_max_mm": None,
            "assembly_allowance_mm": None,
            "modeled_max_depth_mm": None,
            "assembly_note": "Exterior-open cutouts permit soldering and post-solder lead trimming.",
        },
        "diode_body_pads_fillets": {
            "manufacturer": DIODE_MANUFACTURER,
            "mpn": DIODE_MPN,
            "eleparts_goods_no": DIODE_ELEPARTS_GOODS_NO,
            "official_body_depth_max_mm": DIODE_OFFICIAL_BODY_DEPTH_MAX_MM,
            "official_plan_envelope_max_mm": list(DIODE_OFFICIAL_PLAN_ENVELOPE_MAX_MM),
            "official_terminal_span_max_mm": DIODE_OFFICIAL_TERMINAL_SPAN_MAX_MM,
            "solder_fillet_allowance_mm": DIODE_SOLDER_FILLET_DEPTH_ALLOWANCE_MM,
            "modeled_max_depth_mm": round(
                DIODE_OFFICIAL_BODY_DEPTH_MAX_MM + DIODE_SOLDER_FILLET_DEPTH_ALLOWANCE_MM,
                2,
            ),
            "official_source": DIODE_OFFICIAL_SOURCE,
        },
        "controller_socket": {
            "official_body_depth_max_mm": None,
            "assembly_allowance_mm": None,
            "modeled_max_depth_mm": None,
        },
        "battery_termination": {
            "reference": BATTERY_TERMINATION_REFERENCE,
            **battery_termination_contract,
            "pad_envelope_count": battery_termination_coverage["envelope_count"],
            "covered_pad_envelope_count": battery_termination_coverage[
                "covered_envelope_count"
            ],
            "uncovered_pad_envelope_count": battery_termination_coverage[
                "uncovered_envelope_count"
            ],
            "official_body_depth_max_mm": None,
            "assembly_allowance_mm": FILLET_ALLOWANCE_MM,
            "modeled_max_depth_mm": None,
            "assembly_note": (
                "Exterior-open cutout clears both direct-solder lead holes and solder fillets."
            ),
        },
        "power_switch_leads": {
            "reference": POWER_SWITCH_REFERENCE,
            **power_switch_contract,
            "official_body_depth_max_mm": None,
            "assembly_allowance_mm": FILLET_ALLOWANCE_MM,
            "modeled_max_depth_mm": None,
            "assembly_note": (
                "Exterior-open cutout clears all three IMMS-12V leads and solder fillets."
            ),
        },
        "battery_slot": {
            "official_body_depth_max_mm": None,
            "assembly_allowance_mm": None,
            "modeled_max_depth_mm": None,
        },
    }
    result: dict[str, Any] = {}
    for name, geometry in plan["component_cutout_geometries"].items():
        modeled_depth = modeled_depths[name].get("modeled_max_depth_mm")
        plate_bottom_clearance = (
            None if modeled_depth is None else HOUSING_HEIGHT_MM - float(modeled_depth)
        )
        nominal_desk_clearance = (
            None
            if plate_bottom_clearance is None
            else plate_bottom_clearance + DESK_STANDOFF_NOMINAL_MM
        )
        minimum_desk_clearance = (
            None
            if nominal_desk_clearance is None
            else nominal_desk_clearance - DESK_STANDOFF_PRINT_TOLERANCE_MM
        )
        perimeter_fields: dict[str, Any] = {}
        if name == "diode_body_pads_fillets" or name in {
            "battery_termination",
            "power_switch_leads",
            "battery_slot",
        }:
            breaks_perimeter = not plan["housing_outline"].covers(geometry)
            perimeter_fields = {
                "breaks_lateral_housing_perimeter": breaks_perimeter,
                "minimum_housing_perimeter_land_mm": round(
                    0.0 if breaks_perimeter else float(geometry.distance(plan["housing_outline"].boundary)),
                    4,
                ),
            }
        result[name] = {
            "opening_count": plan["component_cutout_counts"][name],
            "minimum_xy_clearance_mm": COMPONENT_CUTOUT_CLEARANCE_MM,
            "exterior_open": True,
            "through_opening_z_mm": [EXTERIOR_BOTTOM_Z_MM, HOUSING_HEIGHT_MM],
            "opening_plan_area_mm2": round(float(geometry.area), 4),
            "minimum_exterior_bottom_clearance_mm": (
                None if plate_bottom_clearance is None else round(plate_bottom_clearance, 2)
            ),
            "minimum_plate_bottom_clearance_mm": (
                None if plate_bottom_clearance is None else round(plate_bottom_clearance, 2)
            ),
            "nominal_desk_clearance_mm": (
                None if nominal_desk_clearance is None else round(nominal_desk_clearance, 2)
            ),
            "desk_standoff_print_tolerance_mm": DESK_STANDOFF_PRINT_TOLERANCE_MM,
            "minimum_desk_clearance_mm": (
                None if minimum_desk_clearance is None else round(minimum_desk_clearance, 2)
            ),
            **perimeter_fields,
            **modeled_depths[name],
        }
    return result


def generate_outputs(output_dir: Path, kicad_python: Path) -> Path:
    import cadquery as cq

    shp = legacy_geometry.require_shapely()
    extracted = run_extractor(kicad_python)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "requirement": REQUIREMENT,
        "requirement_ids": ["CON-ARCH-006", "CON-ARCH-007", "REL-ARCH-001"],
        "variant": VARIANT,
        "generated_by": "tools/generate_kc2_x3_v2_housings.py",
        "hash_policy": HASH_POLICY,
        "generator_sha256": sha256_file(GENERATOR_PATH),
        "coordinate_system": "board-local, X-reflected physical lower-housing assembly view",
        "order_ready": False,
        "parameters": {
            "exterior_bottom_z_mm": EXTERIOR_BOTTOM_Z_MM,
            "housing_height_mm": HOUSING_HEIGHT_MM,
            "pcb_bottom_z_mm": PCB_BOTTOM_Z_MM,
            "pcb_thickness_mm": PCB_THICKNESS_MM,
            "outline_inset_mm": OUTLINE_INSET_MM,
            "rail_inset_mm": RAIL_INSET_MM,
            "rail_width_mm": RAIL_WIDTH_MM,
            "support_post_diameter_mm": POST_DIAMETER_MM,
            "support_clearance_mm": POST_CLEARANCE_MM,
            "fillet_allowance_mm": FILLET_ALLOWANCE_MM,
            "component_minimum_clearance_mm": COMPONENT_MINIMUM_CLEARANCE_MM,
            "component_cutout_clearance_mm": COMPONENT_CUTOUT_CLEARANCE_MM,
            "component_cutout_simplify_mm": COMPONENT_CUTOUT_SIMPLIFY_MM,
            "minimum_diode_housing_perimeter_land_mm": MIN_DIODE_HOUSING_PERIMETER_LAND_MM,
            "minimum_service_housing_perimeter_land_mm": MIN_SERVICE_HOUSING_PERIMETER_LAND_MM,
            "battery_reference": BATTERY_REFERENCE,
            "battery_nominal_plan_envelope_mm": list(
                BATTERY_NOMINAL_PLAN_ENVELOPE_MM
            ),
            "battery_modeled_depth_mm": BATTERY_MODELED_DEPTH_MM,
            "battery_housing_body_cutout": False,
            "battery_termination_reference": BATTERY_TERMINATION_REFERENCE,
            "power_switch_reference": POWER_SWITCH_REFERENCE,
            "power_switch_drill_count": POWER_SWITCH_DRILL_COUNT,
            "power_switch_drill_diameter_mm": POWER_SWITCH_DRILL_DIAMETER_MM,
            "power_switch_body_envelope_mm": list(POWER_SWITCH_BODY_ENVELOPE_MM),
            "power_switch_actuator_travel_mm": POWER_SWITCH_ACTUATOR_TRAVEL_MM,
            "power_switch_actuator_sweep_envelope_mm": list(
                POWER_SWITCH_ACTUATOR_SWEEP_ENVELOPE_MM
            ),
            "reset_reference": RESET_REFERENCE,
            "reset_local_support_diameter_mm": RESET_LOCAL_SUPPORT_DIAMETER_MM,
            "maximum_load_point_to_support_mm": MAX_LOAD_POINT_TO_SUPPORT_MM,
            "print_volume_limit_mm": PRINT_VOLUME_LIMIT_MM,
            "desk_standoff_nominal_mm": DESK_STANDOFF_NOMINAL_MM,
            "desk_standoff_print_tolerance_mm": DESK_STANDOFF_PRINT_TOLERANCE_MM,
            "desk_datum_z_mm": DESK_DATUM_Z_MM,
            "desk_contact_diameter_mm": DESK_CONTACT_DIAMETER_MM,
            "mounting_npth_diameter_mm": MOUNTING_NPTH_DIAMETER_MM,
            "mounting_support_land_diameter_mm": MOUNTING_SUPPORT_LAND_DIAMETER_MM,
            "mounting_pilot_diameter_mm": MOUNTING_PILOT_DIAMETER_MM,
            "mounting_pilot_depth_mm": MOUNTING_PILOT_DEPTH_MM,
            "mounting_pilot_bottom_z_mm": MOUNTING_PILOT_BOTTOM_Z_MM,
            "mounting_closed_bottom_mm": MOUNTING_CLOSED_BOTTOM_MM,
            "mounting_head_envelope_mm": [
                MOUNTING_HEAD_DIAMETER_MM,
                MOUNTING_HEAD_HEIGHT_MM,
            ],
            "mounting_fastener_head_style": MOUNTING_FASTENER_HEAD_STYLE,
            "mounting_head_reserve_mm": MOUNTING_HEAD_RESERVE_MM,
            "mounting_driver_envelope_diameter_mm": MOUNTING_DRIVER_DIAMETER_MM,
            "mounting_unrelated_support_reserve_mm": (
                MOUNTING_UNRELATED_SUPPORT_RESERVE_MM
            ),
            "mounting_analytical_rail_relief": None,
            "provisional_screw_under_head_length_mm": (
                MOUNTING_PROVISIONAL_SCREW_UNDER_HEAD_LENGTH_MM
            ),
            "pcb_thickness_tolerance_fraction": PCB_THICKNESS_TOLERANCE_FRACTION,
            "pcb_tolerance_penetration_range_mm": [
                round(value, 4) for value in MOUNTING_PENETRATION_RANGE_MM
            ],
            "minimum_tip_clearance_mm": round(
                MOUNTING_MINIMUM_TIP_CLEARANCE_MM,
                4,
            ),
        },
        "retention": {
            "registration_peg_count": 0,
            "screw_pilot_count": sum(
                len(points) for points in MOUNTING_HOLE_COORDINATES_MM.values()
            ),
            "screw_pilot_count_by_side": {
                side: len(points)
                for side, points in MOUNTING_HOLE_COORDINATES_MM.items()
            },
            "fastener_boss_count": 0,
            "glue_assumed": False,
            "physical_registration_status": "pending",
            "head_height_and_keycap_skirt_physical_status": "pending",
            "service_condition": "keycaps-off, switches-installed",
            "note": (
                "M1.4 features clamp/register the PCB but remain a provisional physical interface; "
                "the 2.50 mm plate, perimeter rail, and one dedicated desk-contact support per "
                "switch remain the independent vertical load path."
            ),
        },
        "physical_deflection_test": {
            "status": "pending",
            "load_n": 2.0,
            "maximum_displacement_mm": 0.30,
        },
        "outputs": {},
    }

    for side in ("left", "right"):
        board_data = extracted["boards"][side]
        plan = build_plan_geometry(shp, side, board_data)
        if not plan["board_mounting_contract"]["matches"]:
            raise RuntimeError(
                f"{side}: source PCB does not match the exact CON-ARCH-006 MH pattern: "
                f"{plan['board_mounting_contract']}"
            )
        housing = build_cad(cq, shp, plan)
        step_path = output_dir / f"kc2_{side}_x3_v2_lower_housing.step"
        split_joint = None
        part_plans = [plan["support_surface"]]
        if side == "right":
            parts, split_joint = split_right_housing_keyed(cq, shp, housing, plan)
            split_plan = build_right_split_plan(shp, plan)
            part_plans = [split_plan["part_a_plan"], split_plan["part_b_plan"]]
            export_model = cq.Workplane(obj=cq.Compound.makeCompound([part.val() for part in parts]))
        else:
            parts = [housing]
            export_model = housing
        mounting_system = mounting_system_manifest(shp, side, plan, part_plans)
        if (
            not mounting_system["part_distribution_matches_plan"]
            or not mounting_system["primary_support_load_span_unchanged"]
            or any(hole["collision_count"] for hole in mounting_system["holes"])
        ):
            raise RuntimeError(
                f"{side}: mounting-system contract failed: {mounting_system}"
            )
        cq.exporters.export(export_model, str(step_path), exportType="STEP", tolerance=0.001, angularTolerance=0.1, unit="MM")
        normalize_exported_text(step_path)
        printable_parts = []
        for index, (part, part_plan) in enumerate(zip(parts, part_plans)):
            suffix = "" if side == "left" else f"_part_{chr(ord('a') + index)}"
            stl_path = output_dir / f"kc2_{side}_x3_v2_lower_housing{suffix}.stl"
            cq.exporters.export(part, str(stl_path), exportType="STL", tolerance=0.03, angularTolerance=0.08, opt={"ascii": True})
            normalize_exported_text(stl_path)
            dimensions = model_bounds(part)
            if any(value > PRINT_VOLUME_LIMIT_MM for value in dimensions["size_xyz_mm"]):
                raise RuntimeError(f"{stl_path.name} exceeds {PRINT_VOLUME_LIMIT_MM} mm: {dimensions['size_xyz_mm']}")
            part_contacts = desk_contacts_for_part(shp, plan, part_plan)
            stability = desk_contact_stability_manifest(shp, part_plan, part_contacts)
            if not stability["desk_contacts_statically_stable"]:
                raise RuntimeError(
                    f"{side}:{stability['desk_contact_ids']} do not statically support printable part {index}"
                )
            printable_parts.append(
                {
                    "name": "whole" if side == "left" else f"part_{chr(ord('a') + index)}",
                    "stl": str(stl_path.relative_to(ROOT)).replace("\\", "/"),
                    "stl_sha256": sha256_file(stl_path),
                    "solid_count": len(part.solids().vals()),
                    "volume_mm3": round(sum(float(solid.Volume()) for solid in part.solids().vals()), 3),
                    **stability,
                    **dimensions,
                }
            )
        stale_right_stl = output_dir / "kc2_right_x3_v2_lower_housing.stl"
        if side == "right" and stale_right_stl.exists():
            stale_right_stl.unlink()
        manifest["outputs"][side] = {
            "source_board": board_data["path"],
            "source_board_sha256": sha256_file(BOARD_PATHS[side]),
            "key_count": len(board_data["switches"]),
            "legacy_registration_refs": board_data["legacy_registration_refs"],
            "battery_above_carrier": board_data["battery_above_carrier"],
            "step": str(step_path.relative_to(ROOT)).replace("\\", "/"),
            "step_sha256": sha256_file(step_path),
            "step_has_trailing_whitespace": has_trailing_horizontal_whitespace(step_path),
            "printable_parts": printable_parts,
            "desk_standoff_nominal_mm": DESK_STANDOFF_NOMINAL_MM,
            "desk_standoff_print_tolerance_mm": DESK_STANDOFF_PRINT_TOLERANCE_MM,
            "desk_datum_z_mm": DESK_DATUM_Z_MM,
            "minimum_open_component_to_desk_nominal_clearance_mm": round(
                min(
                    HOUSING_HEIGHT_MM
                    - float(depth)
                    + DESK_STANDOFF_NOMINAL_MM
                    for depth in (
                        CHOC_SOCKET_OFFICIAL_BODY_DEPTH_MAX_MM + CHOC_SOCKET_ASSEMBLY_ALLOWANCE_MM,
                        DIODE_OFFICIAL_BODY_DEPTH_MAX_MM + DIODE_SOLDER_FILLET_DEPTH_ALLOWANCE_MM,
                    )
                ),
                2,
            ),
            "minimum_open_component_to_desk_clearance_mm": round(
                min(
                    HOUSING_HEIGHT_MM
                    - float(depth)
                    + DESK_STANDOFF_NOMINAL_MM
                    - DESK_STANDOFF_PRINT_TOLERANCE_MM
                    for depth in (
                        CHOC_SOCKET_OFFICIAL_BODY_DEPTH_MAX_MM
                        + CHOC_SOCKET_ASSEMBLY_ALLOWANCE_MM,
                        DIODE_OFFICIAL_BODY_DEPTH_MAX_MM
                        + DIODE_SOLDER_FILLET_DEPTH_ALLOWANCE_MM,
                    )
                ),
                2,
            ),
            "minimum_open_component_to_desk_clearance_basis": (
                "minimum controlled post-print clearance beneath bottom-side Choc socket and "
                "1N4148W SOD-123 envelopes; BAT1 is above the carrier and has no lower-housing body cutout"
            ),
            "reset_local_support": plan["reset_local_support"],
            "desk_contacts": plan["desk_contacts"],
            "desk_contacts_hidden_in_top_view": plan["housing_outline"].covers(
                plan["desk_contact_geometry"]
            ),
            "desk_contact_component_cutout_collision_count": int(
                plan["desk_contact_geometry"].intersects(plan["all_component_cutouts"])
            ),
            "desk_contacts_statically_stable": all(
                part["desk_contacts_statically_stable"] for part in printable_parts
            ),
            "rail": {
                "top_z_mm": PCB_BOTTOM_Z_MM,
                "nominal_vertical_gap_mm": 0.0,
                "plan_area_mm2": round(plan["rail"].area, 4),
                "segment_count": 1 if plan["rail"].geom_type == "Polygon" else len(plan["rail"].geoms),
                "near_continuous": True,
                "clearance_cut_around_board_features": True,
            },
            "component_cutouts": component_cutout_manifest(plan),
            "support_posts": plan["support_posts"],
            "all_key_loads_have_dedicated_support": bool(
                mounting_system["all_key_loads_have_dedicated_support"]
            ),
            "key_load_support_network_matches_contract": bool(
                mounting_system["key_load_support_network_matches_contract"]
            ),
            "mounting_system": mounting_system,
            "maximum_load_point_to_support_mm": round(_maximum_load_distance(shp, plan), 4),
            "maximum_seam_load_point_to_support_mm": round(
                _maximum_seam_support_distance(shp, side, plan),
                4,
            ),
            "solid_count": len(parts),
            "volume_mm3": round(sum(float(solid.Volume()) for part in parts for solid in part.solids().vals()), 3),
        }
        if split_joint is not None:
            manifest["outputs"][side]["split_joint"] = split_joint

    manifest_path = output_dir / MANIFEST_PATH.name
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {manifest_path.relative_to(ROOT)}")
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate CON-ARCH-006 draft X3 V2 lower housings")
    parser.add_argument("--extract-geometry", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--kicad-python", type=Path)
    args = parser.parse_args()
    if args.extract_geometry:
        extract_geometry()
        return 0
    generate_outputs(args.output_dir, args.kicad_python or legacy_geometry.locate_kicad_python())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
