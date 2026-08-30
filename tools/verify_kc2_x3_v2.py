from __future__ import annotations

import argparse
import heapq
import json
from collections import Counter
from datetime import datetime
import math
import os
from pathlib import Path
import re
import shutil
from statistics import median
import subprocess
import sys
from typing import Iterable, Sequence

import pcbnew

from tools.canonical_hash import HASH_POLICY, sha256_bytes, sha256_file
from tools.generate_kc2_pcbs import (
    X3_V2_CONTROLLER_SERVICE_POSITIONS_MM,
    X3_V2_J_BAT1_ROTATIONS_DEGREES,
    X3_V2_MOUNTING_POINTS,
    X3_V2_RESET_BODY_SIZE_MM,
    X3_V2_RESET_BODY_TO_KEYCAP_MIN_MM,
    X3_V2_RESET_COURTYARD_TO_U1_SOCKET_COPPER_MIN_MM,
    X3_V2_RESET_KEYCAP_ENVELOPE_MM,
    X3_V2_RESET_ROTATIONS_DEGREES,
    X3_V2_TOP_EDGE_Y_MM,
    make_left_keys_x3_v2,
    make_right_keys_x3_v2,
    x3_v2_join_geometry_by_row,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FOOTPRINT = ROOT / "third_party" / "kc2.pretty" / "SW_Choc_V2_Socket_MX_THT.kicad_mod"
DEFAULT_DIODE_FOOTPRINT = ROOT / "third_party" / "kc2.pretty" / "D_ES1B_SMA_HandSolder_C437840.kicad_mod"
DEFAULT_MOUNT_FOOTPRINT = ROOT / "third_party" / "kc2.pretty" / "MH_M1.4_NPTH_1.60.kicad_mod"
DEFAULT_RESET_FOOTPRINT = ROOT / "third_party" / "kc2.pretty" / "SW_NW3_A06_B3_SMD.kicad_mod"
DEFAULT_POWER_SWITCH_FOOTPRINT = ROOT / "third_party" / "kc2.pretty" / "SW_IMMS_12V_BSI10_THT.kicad_mod"
DEFAULT_BATTERY_TERMINATION_FOOTPRINT = ROOT / "third_party" / "kc2.pretty" / "BAT_2Pin_PTH_DirectSolder.kicad_mod"
DEFAULT_BATTERY_BODY_FOOTPRINT = ROOT / "third_party" / "kc2.pretty" / "BAT_301230_30x12mm.kicad_mod"
DEFAULT_CONTROLLER_FOOTPRINTS = {
    "left": ROOT / "third_party" / "kc2.pretty" / "NiceNanoV2_Socket_24Pin_USB_OUT_LEFT.kicad_mod",
    "right": ROOT / "third_party" / "kc2.pretty" / "NiceNanoV2_Socket_24Pin_USB_OUT_RIGHT.kicad_mod",
}
V2_ROOT = ROOT / "hardware" / "kicad" / "draft" / "x3-v2"
DEFAULT_BOARDS = (
    V2_ROOT / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb",
    V2_ROOT / "kc2_right-x3-v2" / "kc2_right-x3-v2.kicad_pcb",
)
DEFAULT_MANIFEST = V2_ROOT / "kc2_x3_v2_generation_manifest.json"
DEFAULT_DRC_EVIDENCE = V2_ROOT / "kc2_x3_v2_drc_evidence.json"
DEFAULT_HOUSING_MANIFEST = (
    ROOT / "hardware" / "case" / "draft" / "x3-v2" / "kc2_x3_v2_housing_manifest.json"
)
DEFAULT_PHYSICAL_EVIDENCE = (
    V2_ROOT / "kc2_x3_v2_physical_evidence.json"
)
DEFAULT_FABRICATION_MANIFEST = (
    V2_ROOT / "fabrication" / "kc2_x3_v2_fabrication_manifest.json"
)
DEFAULT_OUTLINE_REPORT = (
    V2_ROOT / "mechanical" / "kc2_x3_v2_outline_report.json"
)
DEFAULT_FIRMWARE_BUILD_EVIDENCE = (
    ROOT
    / "firmware"
    / "kc2_zmk"
    / "boards"
    / "shields"
    / "kc2_x3_v2"
    / "kc2_x3_v2_build_evidence.json"
)
PHYSICAL_EVIDENCE_SCHEMA = "kc2-x3-v2-physical-evidence-v1"
PHYSICAL_EVIDENCE_REQUIREMENT_IDS = [
    "CON-ARCH-004",
    "CON-ARCH-006",
    "CON-ARCH-007",
    "REL-ARCH-001",
]
PHYSICAL_EVIDENCE_BUNDLES = {
    "controller_service": "CON-ARCH-007: controller service physical evidence bundle",
    "physical_scan": "CON-ARCH-004: physical scan evidence bundle",
    "housing_fastener_deflection": "CON-ARCH-006: housing physical evidence bundle",
    "power_rf": "REL-ARCH-001: power/RF evidence bundle",
}
PHYSICAL_RAW_BUNDLE_SCHEMA = "kc2-x3-v2-physical-raw-bundle-v1"
PHYSICAL_RAW_ARTIFACT_KINDS = {
    "controller_service": "controller-service-raw-json",
    "physical_scan": "physical-scan-raw-json",
    "housing_fastener_deflection": "housing-fastener-deflection-raw-json",
    "power_rf": "power-rf-raw-json",
}
POSITIVE_ORDER_ARTIFACT_MODULES = {
    "fabrication": "tools.verify_kc2_x3_v2_fabrication",
    "mechanical": "tools.verify_kc2_x3_v2_mechanical",
    "render": "tools.verify_kc2_x3_v2_render",
    "firmware": "tools.verify_kc2_x3_v2_zmk_firmware",
    "coupon": "tools.verify_kc2_x3_v2_coupon",
    "outline": "tools.verify_kc2_x3_v2_outline",
}
DIRECT_PLASTIC_THREAD_FORMS = {"thread_forming_30_degree_flank"}
IDENTITY_PLACEHOLDER_TOKENS = {
    "PLACEHOLDER",
    "NA",
    "UNSET",
    "UNDECIDED",
    "UNSPECIFIED",
    "UNSELECTED",
    "UNRESOLVED",
    "UNCONFIRMED",
    "TBC",
    "TBD",
    "TBA",
    "PENDING",
    "UNKNOWN",
    "TODO",
    "FIXME",
    "PROVISIONAL",
    "DUMMY",
    "NONE",
    "NULL",
    "TEMP",
    "FAKE",
    "AWAITING",
    "DRAFT",
    "TENTATIVE",
    "DEFERRED",
    "LATER",
}
IDENTITY_PLACEHOLDER_PHRASES = {
    ("NOT", "AVAILABLE"),
    ("NOT", "KNOWN"),
    ("NOT", "SELECTED"),
    ("NOT", "YET", "SELECTED"),
    ("NO", "MPN"),
    ("AWAITING", "SELECTION"),
    ("PENDING", "SELECTION"),
    ("TO", "FOLLOW"),
    ("TO", "BE", "DECIDED"),
    ("TO", "BE", "CONFIRMED"),
    ("TO", "BE", "DETERMINED"),
}
IDENTITY_PLACEHOLDER_GENERIC_CONTEXT = {
    "ASSEMBLY",
    "BOARD",
    "CODE",
    "COMPONENT",
    "COUPON",
    "DATASHEET",
    "DOC",
    "DOCUMENT",
    "DRAWING",
    "DRIVER",
    "EVIDENCE",
    "FASTENER",
    "FOOTPRINT",
    "GATE",
    "HOUSING",
    "ID",
    "IDENTITY",
    "ITEM",
    "KEYCAP",
    "LOT",
    "MANUFACTURER",
    "MATERIAL",
    "MODEL",
    "MPN",
    "NUMBER",
    "ORDER",
    "PART",
    "PHYSICAL",
    "PRINTER",
    "PROCESS",
    "PROCUREMENT",
    "PRODUCT",
    "PROFILE",
    "PURCHASE",
    "RECORD",
    "REV",
    "REVISION",
    "SELECTED",
    "SELECTION",
    "SOCKET",
    "SOURCE",
    "SPECIMEN",
    "SKU",
    "SUPPLIER",
    "SWITCH",
    "VALUE",
    "VENDOR",
}
IDENTITY_PLACEHOLDER_NUMERIC_PREFIXES = {
    "AWAITING",
    "DEFERRED",
    "DRAFT",
    "DUMMY",
    "FAKE",
    "FIXME",
    "LATER",
    "NONE",
    "NULL",
    "PENDING",
    "PLACEHOLDER",
    "PROVISIONAL",
    "TEMP",
    "TBA",
    "TBD",
    "TENTATIVE",
    "TODO",
    "UNCONFIRMED",
    "UNDECIDED",
    "UNRESOLVED",
    "UNSELECTED",
    "UNSPECIFIED",
    "UNKNOWN",
    "UNSET",
}
EXPECTED_IGNORED_DRC_CHECKS = [
    "footprint_filters_mismatch",
    "footprint_type_mismatch",
    "missing_courtyard",
    "track_not_centered_on_via",
    "tuning_profile_track_geometries",
]
ALLOWED_DRC_SEVERITIES = {"error", "warning", "exclusion"}
REQUIRED_DRC_SEVERITIES = {"error", "warning"}
KICAD_10_VERSION_RE = re.compile(r"^10(?:\.\d+)+(?:[-+][0-9A-Za-z.-]+)?$")
ISO_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$"
)
FORBIDDEN_ACTIVE_V2_BOARD_TEXTS = {
    "Battery solders directly to nice!nano B+/B-; no carrier power pads",
    "BAT LEAD EXIT",
}
REQUIRED_ACTIVE_V2_BOARD_TEXTS = {"BAT STRAIN RELIEF"}
EXPECTED_BATTERY_TERMINATION_MARKINGS = [
    ("1", "B+", "F.Silkscreen", 0.0, -1.65, 0.8, 0.8, 0.12),
    ("2", "B-/GND", "F.Silkscreen", 2.54, 1.8, 0.8, 0.8, 0.12),
]
EXPECTED_M1_4_MOUNTING_POINTS = {
    "left": [
        ("MH1", 112.8625, 43.0000),
        ("MH2", 144.1125, 66.2500),
        ("MH3", 38.6125, 111.0000),
        ("MH4", 63.6125, 123.0000),
        ("MH5", 81.1125, 151.7500),
        ("MH6", 137.3625, 153.5000),
        ("MH7", 166.3625, 148.7500),
        ("MH8", 75.0000, 134.0000),
    ],
    "right": [
        ("MH1", 97.0625, 43.2500),
        ("MH2", 72.4375, 67.0000),
        ("MH3", 169.9375, 95.2500),
        ("MH4", 194.9375, 98.7500),
        ("MH5", 156.1875, 112.5000),
        ("MH6", 69.9375, 146.2500),
        ("MH7", 97.4375, 152.0000),
        ("MH8", 122.6875, 151.0000),
        ("MH9", 177.5000, 118.0000),
    ],
}


def mm(value: int) -> float:
    return round(pcbnew.ToMM(value), 3)


def pad_position(pad: pcbnew.PAD) -> tuple[float, float]:
    position = pad.GetPosition()
    return mm(position.x), mm(position.y)


def padless_footprint_position(footprint: pcbnew.FOOTPRINT) -> tuple[float, float]:
    position = footprint.GetPosition()
    return pcbnew.ToMM(position.x), pcbnew.ToMM(position.y)


def pad_size(pad: pcbnew.PAD) -> tuple[float, float]:
    size = pad.GetSize()
    return mm(size.x), mm(size.y)


def _point_key(point: tuple[float, float]) -> tuple[float, float]:
    return round(point[0], 4), round(point[1], 4)


def _pad_point(footprint: pcbnew.FOOTPRINT, number: str) -> tuple[float, float]:
    pad = next((item for item in footprint.Pads() if item.GetNumber() == number), None)
    if pad is None:
        raise ValueError(f"{footprint.GetReference()} pad {number} is missing")
    position = pad.GetPosition()
    return _point_key((pcbnew.ToMM(position.x), pcbnew.ToMM(position.y)))


def _net_path_points(
    board: pcbnew.BOARD,
    net_name: str,
    start: tuple[float, float],
    end: tuple[float, float],
) -> list[tuple[float, float]]:
    adjacency: dict[tuple[float, float], list[tuple[tuple[float, float], float]]] = {}
    for item in board.GetTracks():
        if item.GetClass() == "PCB_VIA" or item.GetNetname() != net_name:
            continue
        a = _point_key((pcbnew.ToMM(item.GetStart().x), pcbnew.ToMM(item.GetStart().y)))
        b = _point_key((pcbnew.ToMM(item.GetEnd().x), pcbnew.ToMM(item.GetEnd().y)))
        length = math.dist(a, b)
        adjacency.setdefault(a, []).append((b, length))
        adjacency.setdefault(b, []).append((a, length))
    start = _point_key(start)
    end = _point_key(end)
    if start not in adjacency or end not in adjacency:
        raise ValueError(f"{net_name} route does not terminate at {start} and {end}")
    queue: list[tuple[float, tuple[float, float], list[tuple[float, float]]]] = [
        (0.0, start, [start])
    ]
    best: dict[tuple[float, float], float] = {start: 0.0}
    while queue:
        distance, point, path = heapq.heappop(queue)
        if point == end:
            return path
        if distance > best.get(point, math.inf) + 1e-9:
            continue
        for neighbor, length in adjacency.get(point, []):
            candidate = distance + length
            if candidate + 1e-9 < best.get(neighbor, math.inf):
                best[neighbor] = candidate
                heapq.heappush(queue, (candidate, neighbor, [*path, neighbor]))
    raise ValueError(f"{net_name} route is disconnected between {start} and {end}")


def _segments(points: Sequence[tuple[float, float]]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    return list(zip(points, points[1:]))


def _parallel_separations(
    positive_segments: Sequence[tuple[tuple[float, float], tuple[float, float]]],
    ground_segments: Sequence[tuple[tuple[float, float], tuple[float, float]]],
) -> list[float]:
    separations: list[float] = []
    for start, end in positive_segments:
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            continue
        ux, uy = dx / length, dy / length
        matches = []
        for other_start, other_end in ground_segments:
            odx, ody = other_end[0] - other_start[0], other_end[1] - other_start[1]
            other_length = math.hypot(odx, ody)
            if other_length <= 1e-9:
                continue
            oux, ouy = odx / other_length, ody / other_length
            if abs(ux * ouy - uy * oux) > 1e-3:
                continue
            projection = sorted(
                (
                    (other_start[0] - start[0]) * ux + (other_start[1] - start[1]) * uy,
                    (other_end[0] - start[0]) * ux + (other_end[1] - start[1]) * uy,
                )
            )
            overlap = min(length, projection[1]) - max(0.0, projection[0])
            if overlap <= 0.10:
                continue
            matches.append(
                abs((other_start[0] - start[0]) * uy - (other_start[1] - start[1]) * ux)
            )
        if matches:
            separations.append(min(matches))
    return separations


def _rect_distance(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    dx = max(first[0] - second[2], second[0] - first[2], 0.0)
    dy = max(first[1] - second[3], second[1] - first[3], 0.0)
    return math.hypot(dx, dy)


def _defining_box_mm(items: Iterable[object]) -> tuple[float, float, float, float] | None:
    points = [
        (mm(point.x), mm(point.y))
        for item in items
        if hasattr(item, "GetStart") and hasattr(item, "GetEnd")
        for point in (item.GetStart(), item.GetEnd())
    ]
    if not points:
        return None
    return (
        min(point[0] for point in points),
        min(point[1] for point in points),
        max(point[0] for point in points),
        max(point[1] for point in points),
    )


def controller_service_clearance_report(board: pcbnew.BOARD) -> dict[str, object]:
    errors: list[str] = []
    reset = board.FindFootprintByReference("SW_RST1")
    u1 = board.FindFootprintByReference("U1")
    switches = matrix_footprints(board, "SW")
    if reset is None:
        errors.append("SW_RST1 is missing from controller service clearance check")
    if u1 is None:
        errors.append("U1 is missing from controller service clearance check")
    if not switches:
        errors.append("matrix switches are missing from controller service clearance check")

    body_box = None
    courtyard_box = None
    if reset is not None:
        body_candidates: list[object] = []
        for item in reset.GraphicalItems():
            if (
                isinstance(item, pcbnew.PCB_SHAPE)
                and item.GetLayer() == pcbnew.F_Fab
                and item.GetShape() == pcbnew.SHAPE_T_RECT
            ):
                start = item.GetStart()
                end = item.GetEnd()
                dimensions = sorted(
                    (
                        abs(mm(end.x - start.x)),
                        abs(mm(end.y - start.y)),
                    )
                )
                if all(
                    math.isclose(actual, expected, abs_tol=1e-6)
                    for actual, expected in zip(
                        dimensions,
                        sorted(X3_V2_RESET_BODY_SIZE_MM),
                        strict=True,
                    )
                ):
                    body_candidates.append(item)
        if len(body_candidates) != 1:
            errors.append(
                "SW_RST1 must contain exactly one controlled 6.10 x 3.70 mm F.Fab body"
            )
        else:
            body_box = _defining_box_mm(body_candidates)

        courtyard_box = _defining_box_mm(
            item
            for item in reset.GraphicalItems()
            if isinstance(item, pcbnew.PCB_SHAPE)
            and item.GetLayer() == pcbnew.F_CrtYd
        )
        if courtyard_box is None:
            errors.append("SW_RST1 F.CrtYd defining geometry is missing")

    body_clearance: float | None = None
    nearest_reference: str | None = None
    if body_box is not None and switches:
        keycap_half = X3_V2_RESET_KEYCAP_ENVELOPE_MM / 2.0
        keycap_clearances = []
        for switch in switches:
            position = switch.GetPosition()
            x = mm(position.x)
            y = mm(position.y)
            keycap_box = (
                x - keycap_half,
                y - keycap_half,
                x + keycap_half,
                y + keycap_half,
            )
            keycap_clearances.append(
                (_rect_distance(body_box, keycap_box), switch.GetReference())
            )
        body_clearance, nearest_reference = min(keycap_clearances)
        if not math.isclose(
            body_clearance,
            X3_V2_RESET_BODY_TO_KEYCAP_MIN_MM,
            abs_tol=1e-6,
        ):
            errors.append(
                "SW_RST1 controlled body to nearest 18.05 mm keycap envelope is "
                f"{body_clearance:.3f} mm; expected exactly "
                f"{X3_V2_RESET_BODY_TO_KEYCAP_MIN_MM:.3f} mm"
            )

    courtyard_to_copper: float | None = None
    if courtyard_box is not None and u1 is not None:
        socket_pad_boxes = [
            bounding_box_mm(pad)
            for pad in u1.Pads()
            if pad.IsOnLayer(pcbnew.F_Cu) or pad.IsOnLayer(pcbnew.B_Cu)
        ]
        if not socket_pad_boxes:
            errors.append("U1 socket copper pads are missing")
        else:
            courtyard_to_copper = min(
                _rect_distance(courtyard_box, pad_box)
                for pad_box in socket_pad_boxes
            )
            if (
                courtyard_to_copper
                < X3_V2_RESET_COURTYARD_TO_U1_SOCKET_COPPER_MIN_MM - 1e-6
            ):
                errors.append(
                    "SW_RST1 courtyard to U1 socket copper is "
                    f"{courtyard_to_copper:.3f} mm; expected at least "
                    f"{X3_V2_RESET_COURTYARD_TO_U1_SOCKET_COPPER_MIN_MM:.3f} mm"
                )

    return {
        "reset_body_to_nearest_18_05_keycap_mm": (
            round(body_clearance, 3) if body_clearance is not None else None
        ),
        "nearest_keycap_reference": nearest_reference,
        "reset_courtyard_to_u1_socket_copper_mm": (
            round(courtyard_to_copper, 3)
            if courtyard_to_copper is not None
            else None
        ),
        "errors": errors,
    }


def verify_controller_service_manifest_clearances(
    manifest: dict[str, object],
) -> list[str]:
    expected = {
        "reset_keycap_envelope_mm": X3_V2_RESET_KEYCAP_ENVELOPE_MM,
        "reset_body_to_keycap_min": X3_V2_RESET_BODY_TO_KEYCAP_MIN_MM,
        "reset_courtyard_to_u1_socket_copper_min": (
            X3_V2_RESET_COURTYARD_TO_U1_SOCKET_COPPER_MIN_MM
        ),
    }
    service = manifest.get("controller_service_region")
    clearances = (
        service.get("nominal_clearances_mm")
        if isinstance(service, dict)
        else None
    )
    if not isinstance(clearances, dict):
        return ["manifest: controller service nominal clearances are missing or stale"]
    return [
        f"manifest: controller service {field} is missing or stale"
        for field, value in expected.items()
        if clearances.get(field) != value
    ]


def controller_power_geometry_report(board: pcbnew.BOARD, side: str) -> dict[str, object]:
    errors: list[str] = []
    references = {
        reference: board.FindFootprintByReference(reference)
        for reference in ("U1", "BAT1", "J_BAT1", "SW_PWR1")
    }
    missing = [reference for reference, footprint in references.items() if footprint is None]
    if missing:
        return {"errors": [f"missing power geometry references {missing}"]}
    u1 = references["U1"]
    battery = references["BAT1"]
    j_bat = references["J_BAT1"]
    power = references["SW_PWR1"]
    assert u1 is not None and battery is not None and j_bat is not None and power is not None

    fab_points = [
        (pcbnew.ToMM(point.x), pcbnew.ToMM(point.y))
        for item in battery.GraphicalItems()
        if item.GetLayer() == pcbnew.F_Fab and hasattr(item, "GetStart")
        for point in (item.GetStart(), item.GetEnd())
    ]
    battery_box = (
        min(point[0] for point in fab_points),
        min(point[1] for point in fab_points),
        max(point[0] for point in fab_points),
        max(point[1] for point in fab_points),
    )
    antenna_zones = [
        zone for zone in board.Zones() if "ANTENNA_10MM" in zone.GetZoneName()
    ]
    if len(antenna_zones) != 1:
        errors.append(f"expected one antenna keepout, found {len(antenna_zones)}")
        antenna_clearance = -1.0
        antenna_box = None
    else:
        antenna_box = bounding_box_mm(antenna_zones[0])
        antenna_clearance = _rect_distance(battery_box, antenna_box)

    service_clearances: dict[str, float] = {}
    for reference in ("J_BAT1", "SW_PWR1", "SW_RST1", "BAT_LEAD_SLOT1"):
        footprint = board.FindFootprintByReference(reference)
        if footprint is None:
            errors.append(f"{reference} is missing from antenna service check")
            continue
        boxes = [
            bounding_box_mm(item)
            for item in footprint.GraphicalItems()
            if item.GetLayer() in {pcbnew.F_Fab, pcbnew.B_Fab}
        ]
        boxes.extend(bounding_box_mm(pad) for pad in footprint.Pads())
        if not boxes:
            errors.append(f"{reference} has no mechanical antenna envelope")
            continue
        feature_box = (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )
        clearance = -1.0 if antenna_box is None else _rect_distance(feature_box, antenna_box)
        service_clearances[reference] = clearance
        if clearance <= 1e-6:
            errors.append(f"{reference} antenna clearance {clearance:.3f} mm is not positive")
    minimum_service_clearance = min(service_clearances.values(), default=-1.0)

    socket_clearances = []
    for pad in u1.Pads():
        pad_box = bounding_box_mm(pad)
        socket_clearances.append(_rect_distance(battery_box, pad_box))
    socket_clearance = min(socket_clearances)

    try:
        bat_path = _net_path_points(board, "BAT+", _pad_point(j_bat, "1"), _pad_point(power, "1"))
        switched_path = _net_path_points(
            board,
            "NN_B+",
            _pad_point(power, "2"),
            _pad_point(u1, "RAW"),
        )
        ground_path = _net_path_points(
            board,
            "GND",
            _pad_point(j_bat, "2"),
            _pad_point(u1, "GND_C"),
        )
    except ValueError as error:
        errors.append(str(error))
        bat_path = switched_path = ground_path = []

    positive_segments = [*_segments(bat_path), *_segments(switched_path)]
    ground_segments = _segments(ground_path)
    all_positive_segments = [
        (
            _point_key((pcbnew.ToMM(item.GetStart().x), pcbnew.ToMM(item.GetStart().y))),
            _point_key((pcbnew.ToMM(item.GetEnd().x), pcbnew.ToMM(item.GetEnd().y))),
        )
        for item in board.GetTracks()
        if item.GetClass() != "PCB_VIA" and item.GetNetname() in {"BAT+", "NN_B+"}
    ]
    separations = _parallel_separations(positive_segments, ground_segments)
    maximum_parallel_separation = max(separations, default=0.0)
    maximum_antenna_parallel_segment = max(
        (
            math.dist(start, end)
            for start, end in [*all_positive_segments, *ground_segments]
            if abs(start[0] - end[0]) <= 1e-6 or abs(start[1] - end[1]) <= 1e-6
        ),
        default=0.0,
    )
    loop_points = []
    if bat_path and switched_path and ground_path:
        loop_points = [
            *bat_path,
            _pad_point(power, "2"),
            *switched_path[1:],
            _pad_point(u1, "GND_C"),
            *list(reversed(ground_path))[1:],
        ]
    loop_area = 0.0
    if len(loop_points) >= 3:
        loop_area = abs(
            sum(
                x1 * y2 - x2 * y1
                for (x1, y1), (x2, y2) in zip(loop_points, [*loop_points[1:], loop_points[0]])
            )
        ) / 2.0

    if antenna_clearance + 1e-6 < 3.97:
        errors.append(f"battery antenna clearance {antenna_clearance:.3f} mm is below 3.97 mm")
    if socket_clearance + 1e-6 < 0.72:
        errors.append(f"battery socket-pad clearance {socket_clearance:.3f} mm is below 0.72 mm")
    if maximum_parallel_separation > 2.0 + 1e-6:
        errors.append(
            f"power/ground parallel separation {maximum_parallel_separation:.3f} mm exceeds 2.00 mm"
        )
    if loop_area > 75.0 + 1e-6:
        errors.append(f"power loop area {loop_area:.3f} mm2 exceeds 75.00 mm2")
    if maximum_antenna_parallel_segment > 10.0 + 1e-6:
        errors.append(
            "power segment parallel to antenna keepout edge is "
            f"{maximum_antenna_parallel_segment:.3f} mm, above 10.00 mm"
        )
    return {
        "errors": errors,
        "battery_to_antenna_keepout_mm": round(antenna_clearance, 3),
        "battery_to_socket_pad_copper_mm": round(socket_clearance, 3),
        "service_feature_to_antenna_keepout_mm": {
            reference: round(clearance, 3)
            for reference, clearance in sorted(service_clearances.items())
        },
        "minimum_service_feature_to_antenna_keepout_mm": round(
            minimum_service_clearance,
            3,
        ),
        "maximum_parallel_centerline_separation_mm": round(maximum_parallel_separation, 3),
        "power_loop_area_mm2": round(loop_area, 3),
        "maximum_antenna_parallel_segment_mm": round(maximum_antenna_parallel_segment, 3),
    }


def bounding_box_mm(item: object) -> tuple[float, float, float, float]:
    box = item.GetBoundingBox()
    left = pcbnew.ToMM(box.GetX())
    top = pcbnew.ToMM(box.GetY())
    return (
        left,
        top,
        left + pcbnew.ToMM(box.GetWidth()),
        top + pcbnew.ToMM(box.GetHeight()),
    )


def bounding_box_clearance_mm(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    dx = max(first[0] - second[2], second[0] - first[2], 0.0)
    dy = max(first[1] - second[3], second[1] - first[3], 0.0)
    return math.hypot(dx, dy)


def inflate_box_mm(
    box: tuple[float, float, float, float],
    amount: float,
) -> tuple[float, float, float, float]:
    return (box[0] - amount, box[1] - amount, box[2] + amount, box[3] + amount)


def boxes_overlap_mm(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
    tolerance: float = 1e-6,
) -> bool:
    return (
        min(first[2], second[2]) - max(first[0], second[0]) > tolerance
        and min(first[3], second[3]) - max(first[1], second[1]) > tolerance
    )


def point_to_box_distance_mm(
    point: tuple[float, float],
    box: tuple[float, float, float, float],
) -> float:
    dx = max(box[0] - point[0], point[0] - box[2], 0.0)
    dy = max(box[1] - point[1], point[1] - box[3], 0.0)
    return math.hypot(dx, dy)


def point_to_segment_distance_mm(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared <= 1e-18:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    projection = (
        (point[0] - start[0]) * dx + (point[1] - start[1]) * dy
    ) / length_squared
    projection = min(1.0, max(0.0, projection))
    nearest = (start[0] + projection * dx, start[1] + projection * dy)
    return math.hypot(point[0] - nearest[0], point[1] - nearest[1])


def _orientation(
    first: tuple[float, float],
    second: tuple[float, float],
    third: tuple[float, float],
) -> float:
    return (second[0] - first[0]) * (third[1] - first[1]) - (
        second[1] - first[1]
    ) * (third[0] - first[0])


def segments_intersect_mm(
    first_start: tuple[float, float],
    first_end: tuple[float, float],
    second_start: tuple[float, float],
    second_end: tuple[float, float],
    tolerance: float = 1e-9,
) -> bool:
    orientations = (
        _orientation(first_start, first_end, second_start),
        _orientation(first_start, first_end, second_end),
        _orientation(second_start, second_end, first_start),
        _orientation(second_start, second_end, first_end),
    )
    if (
        orientations[0] * orientations[1] < -tolerance
        and orientations[2] * orientations[3] < -tolerance
    ):
        return True
    for point, start, end, orientation in (
        (second_start, first_start, first_end, orientations[0]),
        (second_end, first_start, first_end, orientations[1]),
        (first_start, second_start, second_end, orientations[2]),
        (first_end, second_start, second_end, orientations[3]),
    ):
        if abs(orientation) <= tolerance and (
            min(start[0], end[0]) - tolerance
            <= point[0]
            <= max(start[0], end[0]) + tolerance
            and min(start[1], end[1]) - tolerance
            <= point[1]
            <= max(start[1], end[1]) + tolerance
        ):
            return True
    return False


def segment_to_box_clearance_mm(
    start: tuple[float, float],
    end: tuple[float, float],
    box: tuple[float, float, float, float],
) -> float:
    corners = (
        (box[0], box[1]),
        (box[2], box[1]),
        (box[2], box[3]),
        (box[0], box[3]),
    )
    edges = tuple(zip(corners, (*corners[1:], corners[0])))
    if any(segments_intersect_mm(start, end, edge_start, edge_end) for edge_start, edge_end in edges):
        return 0.0

    def point_to_box(point: tuple[float, float]) -> float:
        dx = max(box[0] - point[0], point[0] - box[2], 0.0)
        dy = max(box[1] - point[1], point[1] - box[3], 0.0)
        return math.hypot(dx, dy)

    return min(
        point_to_box(start),
        point_to_box(end),
        *(point_to_segment_distance_mm(corner, start, end) for corner in corners),
    )


def board_outline_segments_mm(
    board: pcbnew.BOARD,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    outlines = pcbnew.SHAPE_POLY_SET()
    if not board.GetBoardPolygonOutlines(outlines, False):
        raise RuntimeError("KiCad could not resolve a closed Edge.Cuts outline")
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for outline_index in range(outlines.OutlineCount()):
        outline = outlines.Outline(outline_index)
        for segment_index in range(outline.SegmentCount()):
            segment = outline.CSegment(segment_index)
            segments.append(
                (
                    (pcbnew.ToMM(segment.A.x), pcbnew.ToMM(segment.A.y)),
                    (pcbnew.ToMM(segment.B.x), pcbnew.ToMM(segment.B.y)),
                )
            )
    return segments


def load_footprint(path: Path) -> pcbnew.FOOTPRINT:
    if not path.is_file():
        raise FileNotFoundError(path)
    footprint = pcbnew.FootprintLoad(str(path.parent), path.stem)
    if footprint is None:
        raise RuntimeError(f"KiCad could not load footprint: {path}")
    return footprint


def analyze_v2_footprint(path: Path = DEFAULT_FOOTPRINT) -> dict[str, object]:
    footprint = load_footprint(path)
    pads = list(footprint.Pads())
    numbered = [pad for pad in pads if pad.GetNumber()]
    smd = [pad for pad in numbered if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
    pth = [pad for pad in numbered if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
    npth = [pad for pad in pads if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH]

    choc_socket_smd_pads = {
        pad.GetNumber(): (*pad_position(pad), *pad_size(pad))
        for pad in smd
        if pad.IsOnLayer(pcbnew.B_Cu) and pad.IsOnLayer(pcbnew.B_Paste)
    }
    mx_tht_pads = {
        pad.GetNumber(): (*pad_position(pad), *pad_size(pad), mm(pad.GetDrillSize().x))
        for pad in pth
    }
    npth_holes = {
        (*pad_position(pad), mm(pad.GetDrillSize().x))
        for pad in npth
    }
    silk_layers = {pcbnew.F_SilkS, pcbnew.B_SilkS}
    footprint_items = [
        *footprint.GraphicalItems(),
        footprint.Reference(),
        footprint.Value(),
    ]
    back_courtyard_points = [
        point
        for item in footprint.GraphicalItems()
        if item.GetLayer() == pcbnew.B_CrtYd and isinstance(item, pcbnew.PCB_SHAPE)
        for point in (item.GetStart(), item.GetEnd())
    ]
    back_body_points = [
        point
        for item in footprint.GraphicalItems()
        if item.GetLayer() == pcbnew.B_Fab and isinstance(item, pcbnew.PCB_SHAPE)
        for point in (item.GetStart(), item.GetEnd())
    ]
    socket_feature_bounds = [
        (
            x - width / 2.0,
            y - height / 2.0,
            x + width / 2.0,
            y + height / 2.0,
        )
        for x, y, width, height in choc_socket_smd_pads.values()
    ]
    if back_body_points:
        socket_feature_bounds.append(
            (
                min(mm(point.x) for point in back_body_points),
                min(mm(point.y) for point in back_body_points),
                max(mm(point.x) for point in back_body_points),
                max(mm(point.y) for point in back_body_points),
            )
        )
    back_courtyard_bounds = (
        (
            min(mm(point.x) for point in back_courtyard_points),
            min(mm(point.y) for point in back_courtyard_points),
            max(mm(point.x) for point in back_courtyard_points),
            max(mm(point.y) for point in back_courtyard_points),
        )
        if back_courtyard_points
        else None
    )
    socket_bounds = (
        min(bounds[0] for bounds in socket_feature_bounds),
        min(bounds[1] for bounds in socket_feature_bounds),
        max(bounds[2] for bounds in socket_feature_bounds),
        max(bounds[3] for bounds in socket_feature_bounds),
    )
    courtyard_allowance = (
        min(
            socket_bounds[0] - back_courtyard_bounds[0],
            socket_bounds[1] - back_courtyard_bounds[1],
            back_courtyard_bounds[2] - socket_bounds[2],
            back_courtyard_bounds[3] - socket_bounds[3],
        )
        if back_courtyard_bounds is not None
        else -math.inf
    )

    return {
        "name": str(footprint.GetFPID().GetLibItemName()),
        "numbered_pad_counts": dict(sorted(Counter(pad.GetNumber() for pad in numbered).items())),
        "choc_socket_smd_pads": choc_socket_smd_pads,
        "mx_tht_pads": mx_tht_pads,
        "npth_holes": npth_holes,
        "has_choc_v1_locator_holes": any(
            abs(abs(x) - 5.5) < 0.01 and abs(y) < 0.01
            for x, y, _ in npth_holes
        ),
        "has_mx_hotswap_pads": any(
            y < -1.0 for _, y, _, _ in choc_socket_smd_pads.values()
        ),
        "has_choc_v2_direct_solder_pads": any(
            (abs(x) < 0.01 and abs(y - 5.9) < 0.01)
            or (abs(x + 5.0) < 0.01 and abs(y - 3.8) < 0.01)
            for x, y, _, _, _ in mx_tht_pads.values()
        ),
        "choc_socket_back_courtyard_mm": {
            "bounds": back_courtyard_bounds,
            "manufacturing_allowance": round(courtyard_allowance, 3),
            "encloses_body_and_lands": courtyard_allowance >= 0.25 - 1e-6,
        },
        "silkscreen_item_count": sum(item.GetLayer() in silk_layers for item in footprint_items),
    }


def matrix_footprints(board: pcbnew.BOARD, prefix: str) -> list[pcbnew.FOOTPRINT]:
    return sorted(
        (
            footprint
            for footprint in board.GetFootprints()
            if footprint.GetReference().startswith(prefix)
            and footprint.GetReference()[len(prefix):].isdigit()
        ),
        key=lambda footprint: int(footprint.GetReference()[len(prefix):]),
    )


def _canonical_layer_names(pad: pcbnew.PAD, flipped_to_front: bool) -> tuple[str, ...]:
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        # KiCad normalizes library `*.Cu *.Mask` NPTH declarations to mask-only
        # layer sets when a footprint is saved into a board. The NPTH attribute,
        # not that serialization difference, is the copper-free contract.
        return ("NPTH_COPPER_FREE",)
    names = []
    for layer in pad.GetLayerSet().Seq():
        name = pcbnew.LayerName(layer)
        if flipped_to_front and name.startswith("B."):
            name = "F." + name[2:]
        names.append(name)
    return tuple(sorted(names))


def normalized_pad_signatures(
    footprint: pcbnew.FOOTPRINT,
    *,
    normalize_flip: bool = False,
) -> list[tuple[object, ...]]:
    flipped = bool(normalize_flip and footprint.IsFlipped())
    signatures: list[tuple[object, ...]] = []
    for pad in footprint.Pads():
        relative = pad.GetFPRelativePosition()
        relative_y = -mm(relative.y) if flipped else mm(relative.y)
        signatures.append(
            (
                pad.GetNumber(),
                mm(relative.x),
                relative_y,
                *pad_size(pad),
                mm(pad.GetDrillSize().x),
                mm(pad.GetDrillSize().y),
                int(pad.GetAttribute()),
                int(pad.GetShape()),
                _canonical_layer_names(pad, flipped),
            )
        )
    return sorted(signatures, key=repr)


def normalized_diode_graphics(
    footprint: pcbnew.FOOTPRINT,
) -> list[tuple[object, ...]]:
    flipped = footprint.IsFlipped()
    signatures: list[tuple[object, ...]] = []
    for item in footprint.GraphicalItems():
        layer = pcbnew.LayerName(item.GetLayer())
        if layer not in {"F.Fab", "B.Fab", "F.Courtyard", "B.Courtyard", "F.Silkscreen", "B.Silkscreen"}:
            continue
        if flipped and layer.startswith("B."):
            layer = "F." + layer[2:]
        relative = item.GetFPRelativePosition()
        relative_y = -mm(relative.y) if flipped else mm(relative.y)
        if isinstance(item, pcbnew.PCB_SHAPE):
            signatures.append(
                (
                    "shape",
                    layer,
                    int(item.GetShape()),
                    mm(relative.x),
                    relative_y,
                    mm(item.GetLength()),
                    mm(item.GetWidth()),
                )
            )
        elif isinstance(item, pcbnew.PCB_TEXT):
            signatures.append(
                (
                    "text",
                    layer,
                    item.GetText(),
                    mm(relative.x),
                    relative_y,
                    mm(item.GetTextSize().x),
                    mm(item.GetTextSize().y),
                    mm(item.GetTextThickness()),
                )
            )
    return sorted(signatures, key=repr)


def normalized_footprint_graphics(
    footprint: pcbnew.FOOTPRINT,
) -> list[tuple[object, ...]]:
    """Return owned local graphic geometry without using shape GetLength()."""
    normalized = pcbnew.FOOTPRINT(footprint)
    normalized.SetPosition(pcbnew.VECTOR2I(0, 0))
    normalized.SetOrientationDegrees(0)
    signatures: list[tuple[object, ...]] = []
    for item in normalized.GraphicalItems():
        layer = pcbnew.LayerName(item.GetLayer())
        if layer not in {
            "F.Fab",
            "B.Fab",
            "F.Courtyard",
            "B.Courtyard",
            "F.Silkscreen",
            "B.Silkscreen",
        }:
            continue
        if isinstance(item, pcbnew.PCB_SHAPE):
            start = item.GetStart()
            end = item.GetEnd()
            if item.GetShape() == pcbnew.SHAPE_T_RECT:
                start_x, end_x = sorted((mm(start.x), mm(end.x)))
                start_y, end_y = sorted((mm(start.y), mm(end.y)))
            else:
                start_x, start_y = mm(start.x), mm(start.y)
                end_x, end_y = mm(end.x), mm(end.y)
            signatures.append(
                (
                    "shape",
                    layer,
                    int(item.GetShape()),
                    start_x,
                    start_y,
                    end_x,
                    end_y,
                    mm(item.GetWidth()),
                )
            )
        elif isinstance(item, pcbnew.PCB_TEXT) and item.GetText():
            position = item.GetPosition()
            signatures.append(
                (
                    "text",
                    layer,
                    item.GetText(),
                    mm(position.x),
                    mm(position.y),
                    mm(item.GetTextSize().x),
                    mm(item.GetTextSize().y),
                    mm(item.GetTextThickness()),
                )
            )
    return sorted(signatures, key=repr)


def normalized_battery_termination_markings(
    footprint: pcbnew.FOOTPRINT,
) -> list[tuple[object, ...]]:
    """Return pad-associated, local J_BAT1 assembly markings."""
    normalized = pcbnew.FOOTPRINT(footprint)
    normalized.SetPosition(pcbnew.VECTOR2I(0, 0))
    normalized.SetOrientationDegrees(0)
    pads = [pad for pad in normalized.Pads() if pad.GetNumber() in {"1", "2"}]
    if {pad.GetNumber() for pad in pads} != {"1", "2"}:
        return []
    signatures: list[tuple[object, ...]] = []
    for item in normalized.GraphicalItems():
        if not isinstance(item, pcbnew.PCB_TEXT) or item.GetLayer() != pcbnew.F_SilkS:
            continue
        position = item.GetPosition()
        nearest = min(
            pads,
            key=lambda pad: math.dist(
                (position.x, position.y),
                (pad.GetPosition().x, pad.GetPosition().y),
            ),
        )
        signatures.append(
            (
                nearest.GetNumber(),
                item.GetText(),
                pcbnew.LayerName(item.GetLayer()),
                mm(position.x),
                mm(position.y),
                mm(item.GetTextSize().x),
                mm(item.GetTextSize().y),
                mm(item.GetTextThickness()),
            )
        )
    return sorted(signatures, key=lambda item: str(item[0]))


def battery_termination_assembly_marking_errors(
    footprint: pcbnew.FOOTPRINT,
) -> list[str]:
    actual = normalized_battery_termination_markings(footprint)
    if actual != EXPECTED_BATTERY_TERMINATION_MARKINGS:
        return [
            "J_BAT1 assembly markings must identify pad1 B+ and pad2 B-/GND "
            f"with exact visible owned geometry; found {actual}"
        ]
    return []


def normalized_model_signatures(
    footprint: pcbnew.FOOTPRINT,
) -> list[tuple[object, ...]]:
    return sorted(
        (
            model.m_Filename,
            round(float(model.m_Offset.x), 6),
            round(float(model.m_Offset.y), 6),
            round(float(model.m_Offset.z), 6),
            round(float(model.m_Scale.x), 6),
            round(float(model.m_Scale.y), 6),
            round(float(model.m_Scale.z), 6),
            round(float(model.m_Rotation.x), 6),
            round(float(model.m_Rotation.y), 6),
            round(float(model.m_Rotation.z), 6),
            bool(model.m_Show),
            round(float(model.m_Opacity), 6),
        )
        for model in footprint.Models()
    )


def verify_placed_footprint_contracts(
    board: pcbnew.BOARD,
    switches: Sequence[pcbnew.FOOTPRINT],
    diodes: Sequence[pcbnew.FOOTPRINT],
    side: str,
) -> tuple[list[str], list[str], list[str], list[str]]:
    diode_errors: list[str] = []
    switch_errors: list[str] = []
    controller_errors: list[str] = []
    reset_errors: list[str] = []

    diode_source = load_footprint(DEFAULT_DIODE_FOOTPRINT)
    expected_diode_pads = normalized_pad_signatures(diode_source, normalize_flip=True)
    expected_diode_graphics = normalized_diode_graphics(diode_source)
    for diode in diodes:
        if diode.GetLayer() != pcbnew.B_Cu or not diode.IsFlipped():
            diode_errors.append(
                f"{diode.GetReference()}: ES1B must be mirrored on B.Cu"
            )
        if normalized_pad_signatures(diode, normalize_flip=True) != expected_diode_pads:
            diode_errors.append(f"{diode.GetReference()}: pads differ from owned ES1B footprint")
        if normalized_diode_graphics(diode) != expected_diode_graphics:
            diode_errors.append(
                f"{diode.GetReference()}: B.Fab/courtyard/B.Silk cathode geometry differs from owned ES1B footprint"
            )

    switch_source = load_footprint(DEFAULT_FOOTPRINT)
    expected_switch_pads = normalized_pad_signatures(switch_source)
    expected_switch_graphics = normalized_footprint_graphics(switch_source)
    for switch in switches:
        if normalized_pad_signatures(switch) != expected_switch_pads:
            switch_errors.append(
                f"{switch.GetReference()}: pad/NPTH geometry differs from owned hybrid-switch footprint"
            )
        if normalized_footprint_graphics(switch) != expected_switch_graphics:
            switch_errors.append(
                f"{switch.GetReference()}: Fab/courtyard geometry differs from owned hybrid-switch footprint"
            )

    controller = board.FindFootprintByReference("U1")
    controller_source = load_footprint(DEFAULT_CONTROLLER_FOOTPRINTS[side])
    expected_fpid = f"NiceNanoV2_Socket_24Pin_USB_OUT_{side.upper()}"
    if controller is None:
        controller_errors.append("U1 is missing")
    else:
        if str(controller.GetFPID().GetLibItemName()) != expected_fpid:
            controller_errors.append(f"U1 FPID must be {expected_fpid}")
        if len(list(controller.Pads())) != 24:
            controller_errors.append("U1 must have exactly 24 pads")
        if normalized_pad_signatures(controller) != normalized_pad_signatures(controller_source):
            controller_errors.append(
                "U1 pad labels/positions/sizes/drills/layers differ from the side-specific owned footprint"
            )
        expected_power_nets = {
            "RAW": "NN_B+",
            "GND_C": "GND",
            "RST": "RST",
        }
        actual_power_nets = {
            pad.GetNumber(): pad.GetNetname()
            for pad in controller.Pads()
            if pad.GetNumber() in expected_power_nets
        }
        if actual_power_nets != expected_power_nets:
            controller_errors.append(
                "U1 RAW/GND_C/RST pad nets differ from the exact controller power/reset contract: "
                f"expected {expected_power_nets}, got {actual_power_nets}"
            )
        expected_position = X3_V2_CONTROLLER_SERVICE_POSITIONS_MM[side]["u1"]
        controller_position = controller.GetPosition()
        actual_position = (
            round(pcbnew.ToMM(controller_position.x), 4),
            round(pcbnew.ToMM(controller_position.y), 4),
        )
        if actual_position != expected_position:
            controller_errors.append(
                f"U1 position {actual_position} differs from exact V2 position {expected_position}"
            )
    expected_usb_text = f"USB_OUT_{side.upper()}"
    usb_labels = [
        item
        for item in board.GetDrawings()
        if isinstance(item, pcbnew.PCB_TEXT) and item.GetText().startswith("USB_OUT_")
    ]
    if len(usb_labels) != 1 or usb_labels[0].GetText() != expected_usb_text:
        controller_errors.append(f"board USB direction label must be exactly {expected_usb_text}")
    elif usb_labels[0].GetLayer() != pcbnew.F_SilkS:
        controller_errors.append("board USB direction label must be on F.Silkscreen")

    reset = board.FindFootprintByReference("SW_RST1")
    if reset is None:
        reset_errors.append("SW_RST1 is missing")
    else:
        reset_source = load_footprint(DEFAULT_RESET_FOOTPRINT)
        if str(reset.GetFPID().GetLibItemName()) != "SW_NW3_A06_B3_SMD":
            reset_errors.append("SW_RST1 must use the owned SW_NW3_A06_B3_SMD footprint")
        if normalized_pad_signatures(reset) != normalized_pad_signatures(reset_source):
            reset_errors.append("SW_RST1 pad geometry differs from the owned footprint")
        if normalized_footprint_graphics(reset) != normalized_footprint_graphics(reset_source):
            reset_errors.append("SW_RST1 Fab/courtyard/silkscreen geometry differs from the owned footprint")
        expected_position = X3_V2_CONTROLLER_SERVICE_POSITIONS_MM[side]["reset"]
        reset_position = reset.GetPosition()
        actual_position = (
            round(pcbnew.ToMM(reset_position.x), 4),
            round(pcbnew.ToMM(reset_position.y), 4),
        )
        if actual_position != expected_position:
            reset_errors.append(
                f"SW_RST1 position {actual_position} differs from exact V2 position {expected_position}"
            )
        actual_rotation = round(reset.GetOrientation().AsDegrees() % 360.0, 3)
        expected_reset_rotation = X3_V2_RESET_ROTATIONS_DEGREES[side]
        if actual_rotation != expected_reset_rotation:
            reset_errors.append(
                f"SW_RST1 rotation {actual_rotation} differs from exact V2 rotation "
                f"{expected_reset_rotation}"
            )
        reset_pads = {pad.GetNumber(): pad.GetNetname() for pad in reset.Pads()}
        expected_reset_net = "RST"
        if reset_pads != {"1": expected_reset_net, "2": "GND"}:
            reset_errors.append(
                f"SW_RST1 must be pad1={expected_reset_net}, pad2=GND; found {reset_pads}"
            )

    expected_service = X3_V2_CONTROLLER_SERVICE_POSITIONS_MM[side]
    battery = board.FindFootprintByReference("BAT1")
    if battery is None:
        controller_errors.append("BAT1 is missing")
    else:
        battery_source = load_footprint(DEFAULT_BATTERY_BODY_FOOTPRINT)
        if str(battery.GetFPID().GetLibItemName()) != "BAT_301230_30x12mm":
            controller_errors.append("BAT1 must use the owned 301230 footprint")
        if list(battery.Pads()):
            controller_errors.append("BAT1 mechanical envelope must have no pads")
        if normalized_footprint_graphics(battery) != normalized_footprint_graphics(battery_source):
            controller_errors.append("BAT1 graphics differ from the owned 301230 footprint")
        actual = tuple(round(value, 4) for value in padless_footprint_position(battery))
        if actual != expected_service["battery"]:
            controller_errors.append(f"BAT1 position {actual} differs from {expected_service['battery']}")

    j_bat = board.FindFootprintByReference("J_BAT1")
    if j_bat is None:
        controller_errors.append("J_BAT1 is missing")
    else:
        source = load_footprint(DEFAULT_BATTERY_TERMINATION_FOOTPRINT)
        if str(j_bat.GetFPID().GetLibItemName()) != "BAT_2Pin_PTH_DirectSolder":
            controller_errors.append("J_BAT1 must use the owned direct-solder footprint")
        if normalized_pad_signatures(j_bat) != normalized_pad_signatures(source):
            controller_errors.append("J_BAT1 pad geometry differs from the owned footprint")
        if normalized_footprint_graphics(j_bat) != normalized_footprint_graphics(source):
            controller_errors.append("J_BAT1 graphics/assembly markings differ from the owned footprint")
        controller_errors.extend(
            f"J_BAT1: {error}"
            for error in battery_termination_assembly_marking_errors(source)
        )
        controller_errors.extend(
            f"J_BAT1: {error}"
            for error in battery_termination_assembly_marking_errors(j_bat)
        )
        if {pad.GetNumber(): pad.GetNetname() for pad in j_bat.Pads()} != {"1": "BAT+", "2": "GND"}:
            controller_errors.append("J_BAT1 must be pad1=BAT+, pad2=GND")
        actual = tuple(round(value, 4) for value in padless_footprint_position(j_bat))
        if actual != expected_service["j_bat"]:
            controller_errors.append(f"J_BAT1 position {actual} differs from {expected_service['j_bat']}")
        expected_rotation = X3_V2_J_BAT1_ROTATIONS_DEGREES[side]
        if round(j_bat.GetOrientation().AsDegrees() % 360.0, 3) != expected_rotation:
            controller_errors.append(f"J_BAT1 rotation differs from {expected_rotation}")

    power = board.FindFootprintByReference("SW_PWR1")
    if power is None:
        controller_errors.append("SW_PWR1 is missing")
    else:
        source = load_footprint(DEFAULT_POWER_SWITCH_FOOTPRINT)
        if str(power.GetFPID().GetLibItemName()) != "SW_IMMS_12V_BSI10_THT":
            controller_errors.append("SW_PWR1 must use the owned IMMS-12V footprint")
        if normalized_pad_signatures(power) != normalized_pad_signatures(source):
            controller_errors.append("SW_PWR1 pad geometry differs from the owned footprint")
        if normalized_model_signatures(power) != normalized_model_signatures(source):
            controller_errors.append("SW_PWR1 STEP models differ from the owned footprint")
        if {pad.GetNumber(): pad.GetNetname() for pad in power.Pads()} != {
            "2": "NN_B+",
            "1": "BAT+",
            "3": "",
        }:
            controller_errors.append("SW_PWR1 must be pad1=BAT+, pad2=NN_B+, pad3=NC")
        actual = tuple(round(value, 4) for value in padless_footprint_position(power))
        if actual != expected_service["power"]:
            controller_errors.append(f"SW_PWR1 position {actual} differs from {expected_service['power']}")
        expected_rotation = 0.0 if side == "left" else 180.0
        if round(power.GetOrientation().AsDegrees() % 360.0, 3) != expected_rotation:
            controller_errors.append(f"SW_PWR1 rotation differs from {expected_rotation}")
    return diode_errors, switch_errors, controller_errors, reset_errors


def expected_m1_4_mount_manifest() -> dict[str, object]:
    return {
        "footprint": "kc2.pretty:MH_M1.4_NPTH_1.60",
        "references": "MH1..MH8 left; MH1..MH9 right",
        "counts": {"left": 8, "right": 9, "total": 17},
        "positions_mm": {
            side: [
                {"ref": ref, "x": x, "y": y}
                for ref, x, y in points
            ]
            for side, points in EXPECTED_M1_4_MOUNTING_POINTS.items()
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
    }


def verify_m1_4_mounting_holes(
    board: pcbnew.BOARD,
    side: str,
) -> tuple[
    list[str],
    list[tuple[str, float, float]],
    dict[str, float | None],
    list[str],
    list[str],
    list[str],
]:
    errors: list[str] = []
    silkscreen_errors: list[str] = []
    holes = matrix_footprints(board, "MH")
    positions = [
        (
            hole.GetReference(),
            round(pcbnew.ToMM(hole.GetPosition().x), 4),
            round(pcbnew.ToMM(hole.GetPosition().y), 4),
        )
        for hole in holes
    ]
    expected_positions = EXPECTED_M1_4_MOUNTING_POINTS[side]
    if positions != expected_positions:
        errors.append(
            f"{side}: exact MH positions differ: expected {expected_positions}, found {positions}"
        )

    source = load_footprint(DEFAULT_MOUNT_FOOTPRINT)
    expected_pads = normalized_pad_signatures(source)
    for hole in holes:
        reference = hole.Reference()
        reference_position = reference.GetFPRelativePosition()
        reference_signature = (
            reference.IsVisible(),
            reference.GetLayer(),
            mm(reference.GetTextHeight()),
            mm(reference.GetTextThickness()),
            mm(reference_position.x),
            mm(reference_position.y),
        )
        if reference_signature != (True, pcbnew.F_SilkS, 0.8, 0.15, 0.0, -1.5):
            silkscreen_errors.append(
                f"{hole.GetReference()}: visible F.SilkS reference must be "
                "0.80 mm high / 0.15 mm stroke at relative (0.0,-1.5) mm; "
                f"found {reference_signature}"
            )
        if str(hole.GetFPID().GetLibItemName()) != "MH_M1.4_NPTH_1.60":
            errors.append(f"{hole.GetReference()}: unexpected mounting footprint")
        if str(hole.GetValue()) != "M1.4_NPTH_1.60":
            errors.append(f"{hole.GetReference()}: unexpected mounting value")
        if abs(float(hole.GetOrientationDegrees())) > 1e-6:
            errors.append(f"{hole.GetReference()}: mounting footprint rotation must be zero")
        pads = list(hole.Pads())
        if normalized_pad_signatures(hole) != expected_pads:
            errors.append(f"{hole.GetReference()}: pad geometry differs from owned M1.4 footprint")
        if len(pads) != 1:
            errors.append(f"{hole.GetReference()}: expected one NPTH pad, found {len(pads)}")
            continue
        pad = pads[0]
        if (
            pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH
            or pad.GetNumber()
            or pad.GetNetname()
            or pad_size(pad) != (1.6, 1.6)
            or (mm(pad.GetDrillSize().x), mm(pad.GetDrillSize().y)) != (1.6, 1.6)
        ):
            errors.append(
                f"{hole.GetReference()}: must be one unnumbered, unnetted, copper-free 1.60 mm NPTH"
            )

    hole_centers = [(x, y) for _, x, y in positions]
    copper_pads = [
        (f"{footprint.GetReference()}.{pad.GetNumber()}", bounding_box_mm(pad))
        for footprint in board.GetFootprints()
        if not re.fullmatch(r"MH\d+", footprint.GetReference())
        for pad in footprint.Pads()
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH
        and (pad.IsOnLayer(pcbnew.F_Cu) or pad.IsOnLayer(pcbnew.B_Cu))
    ]
    copper_clearances: list[float] = []
    for center in hole_centers:
        copper_clearances.extend(
            point_to_box_distance_mm(center, box) - 0.8
            for _label, box in copper_pads
        )
        for track in board.GetTracks():
            if isinstance(track, pcbnew.PCB_VIA):
                at = track.GetPosition()
                copper_clearances.append(
                    math.hypot(
                        center[0] - pcbnew.ToMM(at.x),
                        center[1] - pcbnew.ToMM(at.y),
                    )
                    - pcbnew.ToMM(track.GetWidth(pcbnew.F_Cu)) / 2.0
                    - 0.8
                )
            else:
                start = track.GetStart()
                end = track.GetEnd()
                copper_clearances.append(
                    point_to_segment_distance_mm(
                        center,
                        (pcbnew.ToMM(start.x), pcbnew.ToMM(start.y)),
                        (pcbnew.ToMM(end.x), pcbnew.ToMM(end.y)),
                    )
                    - pcbnew.ToMM(track.GetWidth()) / 2.0
                    - 0.8
                )
    minimum_copper_clearance = min(copper_clearances) if copper_clearances else math.inf
    if minimum_copper_clearance < 0.30 - 1e-6:
        errors.append(
            f"{side}: M1.4 NPTH edge-to-copper clearance {minimum_copper_clearance:.4f} mm is below 0.30 mm"
        )

    driver_copper_measurements: list[tuple[float, str]] = []
    for reference, x, y in positions:
        center = (x, y)
        driver_copper_measurements.extend(
            (
                point_to_box_distance_mm(center, box) - 1.5,
                f"{reference} vs pad {label}",
            )
            for label, box in copper_pads
        )
        for track in board.GetTracks():
            if isinstance(track, pcbnew.PCB_VIA):
                at = track.GetPosition()
                margin = (
                    math.hypot(x - pcbnew.ToMM(at.x), y - pcbnew.ToMM(at.y))
                    - pcbnew.ToMM(track.GetWidth(pcbnew.F_Cu)) / 2.0
                    - 1.5
                )
                label = (
                    f"{reference} vs via {track.GetNetname()} "
                    f"({pcbnew.ToMM(at.x):.4f},{pcbnew.ToMM(at.y):.4f})"
                )
            else:
                start = track.GetStart()
                end = track.GetEnd()
                start_mm = (pcbnew.ToMM(start.x), pcbnew.ToMM(start.y))
                end_mm = (pcbnew.ToMM(end.x), pcbnew.ToMM(end.y))
                margin = (
                    point_to_segment_distance_mm(center, start_mm, end_mm)
                    - pcbnew.ToMM(track.GetWidth()) / 2.0
                    - 1.5
                )
                label = (
                    f"{reference} vs {board.GetLayerName(track.GetLayer())} "
                    f"track {track.GetNetname()} {start_mm}->{end_mm}"
                )
            driver_copper_measurements.append((margin, label))
    minimum_driver_copper_clearance = min(
        (margin for margin, _label in driver_copper_measurements),
        default=math.inf,
    )
    driver_copper_errors = [
        f"{side}: final 3.00 mm PH0 driver intersects copper: {label}; margin {margin:.4f} mm"
        for margin, label in driver_copper_measurements
        if margin < -1e-6
    ]
    errors.extend(driver_copper_errors)

    def graphics_envelope(
        footprint: pcbnew.FOOTPRINT,
        layers: set[int],
    ) -> tuple[float, float, float, float] | None:
        boxes = [
            bounding_box_mm(item)
            for item in footprint.GraphicalItems()
            if isinstance(item, pcbnew.PCB_SHAPE) and item.GetLayer() in layers
        ]
        if not boxes:
            return None
        return (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )

    installed_body_boxes: list[tuple[str, tuple[float, float, float, float]]] = []
    for switch in matrix_footprints(board, "SW"):
        at = switch.GetPosition()
        center = (pcbnew.ToMM(at.x), pcbnew.ToMM(at.y))
        installed_body_boxes.append(
            (
                f"{switch.GetReference()} installed switch 15.60 mm envelope",
                (center[0] - 7.8, center[1] - 7.8, center[0] + 7.8, center[1] + 7.8),
            )
        )
        socket_box = graphics_envelope(switch, {pcbnew.B_Fab})
        if socket_box is not None:
            installed_body_boxes.append(
                (f"{switch.GetReference()} Choc socket B.Fab body", socket_box)
            )
    for diode in matrix_footprints(board, "D"):
        body_box = graphics_envelope(diode, {pcbnew.B_Fab})
        if body_box is not None:
            installed_body_boxes.append((f"{diode.GetReference()} ES1B body", body_box))

    controller = board.FindFootprintByReference("U1")
    if controller is not None:
        at = controller.GetPosition()
        center = (pcbnew.ToMM(at.x), pcbnew.ToMM(at.y))
        installed_body_boxes.append(
            ("U1 controlled 33.80 x 18.30 mm body", (center[0] - 16.9, center[1] - 9.15, center[0] + 16.9, center[1] + 9.15))
        )
    battery = board.FindFootprintByReference("BAT1")
    if battery is not None:
        at = battery.GetPosition()
        center = (pcbnew.ToMM(at.x), pcbnew.ToMM(at.y))
        installed_body_boxes.append(
            ("BAT1 nominal 301230 body", (center[0] - 15.0, center[1] - 6.0, center[0] + 15.0, center[1] + 6.0))
        )
    power = board.FindFootprintByReference("SW_PWR1")
    if power is not None:
        at = power.GetPosition()
        center = (pcbnew.ToMM(at.x), pcbnew.ToMM(at.y))
        installed_body_boxes.append(
            (
                "SW_PWR1 body plus actuator travel",
                (center[0] - 6.6, center[1] - 1.25, center[0] + 6.6, center[1] + 1.25),
            )
        )
    for reference, layers in (
        ("J_BAT1", {pcbnew.F_Fab}),
        ("SW_RST1", {pcbnew.F_Fab, pcbnew.F_CrtYd}),
        ("BAT_LEAD_SLOT1", {pcbnew.F_Fab, pcbnew.Dwgs_User}),
    ):
        footprint = board.FindFootprintByReference(reference)
        if footprint is None:
            continue
        body_box = graphics_envelope(footprint, layers)
        if body_box is None:
            body_box = bounding_box_mm(footprint)
        installed_body_boxes.append((f"{reference} physical envelope", body_box))

    body_measurements = [
        (
            point_to_box_distance_mm(center, box) - 1.5,
            f"{reference} vs {label}",
        )
        for reference, *coordinates in positions
        for center in [tuple(coordinates)]
        for label, box in installed_body_boxes
    ]
    driver_clearances = [margin for margin, _label in body_measurements]
    minimum_driver_clearance = min(driver_clearances) if driver_clearances else math.inf
    if minimum_driver_clearance < -1e-6:
        errors.append(
            f"{side}: final 3.00 mm PH0 driver envelope intersects an installed body by "
            f"{-minimum_driver_clearance:.4f} mm"
        )

    fillet_boxes = [
        (f"{label} plus 0.30 mm solder-fillet allowance", inflate_box_mm(box, 0.30))
        for label, box in copper_pads
    ]
    head_copper_measurements = [
        (
            point_to_box_distance_mm(center, box) - 1.5,
            f"{reference} vs pad {label}",
        )
        for reference, *coordinates in positions
        for center in [tuple(coordinates)]
        for label, box in fillet_boxes
    ]
    head_copper_measurements.extend(driver_copper_measurements)

    outline_segments = board_outline_segments_mm(board)
    edge_clearances = [
        point_to_segment_distance_mm(center, start, end) - 1.5
        for center in hole_centers
        for start, end in outline_segments
    ]
    minimum_head_body_clearance = min(
        (margin for margin, _label in body_measurements),
        default=math.inf,
    )
    minimum_head_copper_fillet_clearance = min(
        (margin for margin, _label in head_copper_measurements),
        default=math.inf,
    )
    minimum_head_edge_clearance = min(edge_clearances) if edge_clearances else math.inf
    head_clearance_errors = [
        f"{side}: 3.00 mm rounded screw head lacks 1.20 mm body clearance: {label}; margin {margin:.4f} mm"
        for margin, label in body_measurements
        if margin < 1.20 - 1e-6
    ]
    head_clearance_errors.extend(
        f"{side}: 3.00 mm rounded screw head lacks 0.85 mm copper/fillet clearance: {label}; margin {margin:.4f} mm"
        for margin, label in head_copper_measurements
        if margin < 0.85 - 1e-6
    )
    if minimum_head_edge_clearance < 2.10 - 1e-6:
        head_clearance_errors.append(
            f"{side}: 3.00 mm rounded screw-head-to-Edge.Cuts clearance "
            f"{minimum_head_edge_clearance:.4f} mm is below 2.10 mm"
        )
    errors.extend(head_clearance_errors)

    return errors, positions, {
        "minimum_npth_edge_to_copper_mm": round(minimum_copper_clearance, 4),
        "minimum_driver_to_copper_mm": round(minimum_driver_copper_clearance, 4),
        "minimum_driver_to_installed_body_mm": round(minimum_driver_clearance, 4),
        "minimum_head_to_installed_body_mm": round(minimum_head_body_clearance, 4),
        "minimum_head_to_exposed_copper_fillet_mm": round(
            minimum_head_copper_fillet_clearance, 4
        ),
        "minimum_head_to_edge_cuts_mm": round(minimum_head_edge_clearance, 4),
    }, driver_copper_errors, silkscreen_errors, head_clearance_errors


def project_default_clearance_mm(project_path: Path) -> float:
    project = json.loads(project_path.read_text(encoding="utf-8"))
    default = next(
        netclass
        for netclass in project["net_settings"]["classes"]
        if netclass.get("name") == "Default"
    )
    return float(default["clearance"])


def _dsn_default_clearances(dsn_path: Path) -> dict[str, int]:
    text = dsn_path.read_text(encoding="utf-8")
    global_match = re.search(
        r"\(structure\b[\s\S]*?\(rule\b[\s\S]*?\(clearance\s+(\d+)\)",
        text,
    )
    default_match = re.search(
        r"\(class\s+kicad_default\b[\s\S]*?\(rule\b[\s\S]*?\(clearance\s+(\d+)\)",
        text,
    )
    return {
        label: int(match.group(1))
        for label, match in (("global", global_match), ("kicad_default", default_match))
        if match is not None
    }


def verify_canonical_route_evidence(
    manifest: dict[str, object],
) -> tuple[list[str], dict[str, object]]:
    errors: list[str] = []
    reports: dict[str, object] = {}
    if manifest.get("hash_policy") != HASH_POLICY:
        errors.append("manifest: canonical hash policy mismatch")
    records = manifest.get("canonical_route_evidence")
    if not isinstance(records, dict):
        return ["manifest: canonical route evidence is missing"], reports
    for side in ("left", "right"):
        record = records.get(side)
        if not isinstance(record, dict):
            errors.append(f"{side}: canonical route evidence is missing")
            continue
        expected_dsn = (
            f"hardware/kicad/draft/x3-v2/autoroute/"
            f"kc2_{side}-x3-v2-70-es1b-controller-r3.dsn"
        )
        expected_session_source_dsn = expected_dsn
        expected_ses = (
            f"hardware/kicad/draft/x3-v2/autoroute/"
            f"kc2_{side}-x3-v2-70-es1b-controller-r3.ses"
        )
        if record.get("dsn") != expected_dsn:
            errors.append(f"{side}: canonical DSN path mismatch")
        if record.get("ses") != expected_ses:
            errors.append(f"{side}: canonical SES path mismatch")
        if record.get("session_source_dsn") != expected_session_source_dsn:
            errors.append(f"{side}: reviewed SES source DSN path mismatch")
        if record.get("dsn_role") != "current_mh_compact_controller_trackless_routing_input":
            errors.append(f"{side}: current MH DSN role mismatch")
        if record.get("ses_role") != (
            "reviewed_matrix_import_plus_exact_edge_cleanup_and_power_reset_service_routing"
        ):
            errors.append(f"{side}: reviewed SES/detour role mismatch")
        try:
            dsn_path = ROOT / str(record.get("dsn"))
            session_source_dsn_path = ROOT / str(record.get("session_source_dsn"))
            ses_path = ROOT / str(record.get("ses"))
            dsn_sha = sha256_file(dsn_path)
            session_source_dsn_sha = sha256_file(session_source_dsn_path)
            ses_sha = sha256_file(ses_path)
            clearances = _dsn_default_clearances(dsn_path)
            dsn_text = dsn_path.read_text(encoding="utf-8")
            ses_text = ses_path.read_text(encoding="utf-8")
        except OSError as error:
            errors.append(f"{side}: canonical route source cannot be read: {error}")
            continue
        minimum_clearance = min(clearances.values()) if clearances else None
        reports[side] = {
            "dsn_sha256": dsn_sha,
            "session_source_dsn_sha256": session_source_dsn_sha,
            "ses_sha256": ses_sha,
            "dsn_mounting_hole_count": len(
                re.findall(r"\(place\s+MH\d+\b", dsn_text)
            ),
            "dsn_default_clearance_internal_units": minimum_clearance,
            "dsn_clearances_internal_units": clearances,
            "dsn_mounting_hole_positions_mm": _specctra_mount_positions_mm(
                dsn_text, 1000.0
            ),
            "ses_mounting_hole_positions_mm": _specctra_mount_positions_mm(
                ses_text, 10000.0
            ),
        }
        if record.get("dsn_sha256") != dsn_sha:
            errors.append(f"{side}: DSN SHA-256 mismatch")
        if record.get("ses_sha256") != ses_sha:
            errors.append(f"{side}: SES SHA-256 mismatch")
        if record.get("session_source_dsn_sha256") != session_source_dsn_sha:
            errors.append(f"{side}: reviewed SES source DSN SHA-256 mismatch")
        expected_holes = len(X3_V2_MOUNTING_POINTS[side])
        if reports[side]["dsn_mounting_hole_count"] != expected_holes:
            errors.append(f"{side}: current DSN does not contain the exact MH pattern")
        if record.get("dsn_mounting_hole_count") != expected_holes:
            errors.append(f"{side}: current DSN MH count evidence mismatch")
        expected_positions = {
            f"MH{index}": position
            for index, position in enumerate(X3_V2_MOUNTING_POINTS[side], start=1)
        }
        if reports[side]["dsn_mounting_hole_positions_mm"] != expected_positions:
            errors.append(f"{side}: current DSN P2 mounting geometry mismatch")
        if reports[side]["ses_mounting_hole_positions_mm"] != expected_positions:
            errors.append(f"{side}: reviewed SES P2 mounting geometry mismatch")
        if set(clearances) != {"global", "kicad_default"} or minimum_clearance is None or minimum_clearance < 300:
            errors.append(f"{side}: DSN global/default clearance must be at least 300 internal units")
        if record.get("dsn_default_clearance_internal_units") != minimum_clearance:
            errors.append(f"{side}: DSN clearance evidence mismatch")
        if record.get("dsn_clearances_internal_units") != clearances:
            errors.append(f"{side}: DSN global/default clearance evidence mismatch")
    return errors, reports


def verify_switch_layout_against_generator(
    switches: Sequence[pcbnew.FOOTPRINT],
) -> tuple[list[str], float]:
    """Compare the committed switch pattern after removing one rigid translation."""
    from tools.generate_kc2_pcbs import (
        make_left_keys_x3_v2,
        make_right_keys_x3_v2,
        switch_rotation_for_key,
    )

    if len(switches) == 31:
        keys = make_left_keys_x3_v2()
    elif len(switches) == 39:
        keys = make_right_keys_x3_v2()
    else:
        return [f"cannot select generator layout for {len(switches)} switches"], math.inf

    errors: list[str] = []
    actual_anchor = switches[0].GetPosition()
    expected_anchor = keys[0]
    maximum_position_error = 0.0
    for index, (switch, key) in enumerate(zip(switches, keys, strict=True), start=1):
        expected_reference = f"SW{index}"
        if switch.GetReference() != expected_reference:
            errors.append(
                f"switch sequence mismatch: expected {expected_reference}, found {switch.GetReference()}"
            )

        position = switch.GetPosition()
        actual_dx = pcbnew.ToMM(position.x - actual_anchor.x)
        actual_dy = pcbnew.ToMM(position.y - actual_anchor.y)
        expected_dx = key.cx - expected_anchor.cx
        expected_dy = key.cy - expected_anchor.cy
        position_error = math.hypot(actual_dx - expected_dx, actual_dy - expected_dy)
        maximum_position_error = max(maximum_position_error, position_error)
        if position_error > 0.001:
            errors.append(
                f"{expected_reference} relative position drift: "
                f"expected ({expected_dx:.4f}, {expected_dy:.4f}) mm, "
                f"found ({actual_dx:.4f}, {actual_dy:.4f}) mm"
            )

        expected_rotation = switch_rotation_for_key(key, keys, "x3-v2") % 360.0
        actual_rotation = float(switch.GetOrientationDegrees()) % 360.0
        rotation_error = abs((actual_rotation - expected_rotation + 180.0) % 360.0 - 180.0)
        if rotation_error > 0.001:
            errors.append(
                f"{expected_reference} rotation drift: expected {expected_rotation:.3f} deg, "
                f"found {actual_rotation:.3f} deg"
            )

    return errors, round(maximum_position_error, 4)


def analyze_v2_board(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(path)
    board = pcbnew.LoadBoard(str(path))
    from tools.finalize_kc2_x3_v2_routes import (
        _route_counter_digest,
        _route_signature,
    )

    route_signatures = Counter(_route_signature(item) for item in board.GetTracks())
    switches = matrix_footprints(board, "SW")
    diodes = matrix_footprints(board, "D")
    side = "left" if "left" in path.name.lower() else "right"
    (
        mounting_hole_errors,
        mounting_hole_positions_mm,
        mounting_hole_clearances,
        mounting_hole_driver_copper_errors,
        mounting_hole_silkscreen_errors,
        mounting_hole_head_clearance_errors,
    ) = verify_m1_4_mounting_holes(board, side)
    (
        diode_footprint_geometry_errors,
        switch_footprint_geometry_errors,
        controller_contract_errors,
        reset_contract_errors,
    ) = verify_placed_footprint_contracts(board, switches, diodes, side)
    power_geometry = controller_power_geometry_report(board, side)
    service_clearance = controller_service_clearance_report(board)
    controller_contract_errors.extend(
        f"power geometry: {error}"
        for error in power_geometry["errors"]
    )
    switch_layout_errors, switch_layout_max_position_error_mm = (
        verify_switch_layout_against_generator(switches)
    )
    mismatches: list[str] = []
    for switch in switches:
        for number in ("1", "2"):
            contact_pads = [pad for pad in switch.Pads() if pad.GetNumber() == number]
            nets = {pad.GetNetname() for pad in contact_pads}
            if len(contact_pads) != 2 or len(nets) != 1 or "" in nets:
                mismatches.append(
                    f"{switch.GetReference()} pad {number}: count={len(contact_pads)} nets={sorted(nets)}"
                )

    footprints = list(board.GetFootprints())
    registration_holes = [
        footprint
        for footprint in footprints
        if footprint.GetReference().startswith("REG")
        and footprint.GetReference()[3:].isdigit()
    ]
    registration_hole_errors: list[str] = []
    for footprint in registration_holes:
        pads = list(footprint.Pads())
        if len(pads) != 1:
            registration_hole_errors.append(
                f"{footprint.GetReference()}: expected one NPTH pad, found {len(pads)}"
            )
            continue
        pad = pads[0]
        drill = mm(pad.GetDrillSize().x)
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH or drill != 3.0 or pad.GetNetname():
            registration_hole_errors.append(
                f"{footprint.GetReference()}: attr={pad.GetAttribute()} drill={drill} net={pad.GetNetname()!r}"
            )

    battery_slots = [
        footprint
        for footprint in footprints
        if str(footprint.GetFPID().GetLibItemName()) == "BAT_LEAD_NPTH_SLOT_3.6x2.2"
    ]
    battery_lead_slot_errors: list[str] = []
    for footprint in battery_slots:
        pads = list(footprint.Pads())
        if len(pads) != 1:
            battery_lead_slot_errors.append(
                f"{footprint.GetReference()}: expected one NPTH slot, found {len(pads)}"
            )
            continue
        pad = pads[0]
        drill = sorted((mm(pad.GetDrillSize().x), mm(pad.GetDrillSize().y)))
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH or drill != [2.2, 3.6] or pad.GetNetname():
            battery_lead_slot_errors.append(
                f"{footprint.GetReference()}: attr={pad.GetAttribute()} drill={drill} net={pad.GetNetname()!r}"
            )
    u1 = next((footprint for footprint in footprints if footprint.GetReference() == "U1"), None)
    controller_rows = sorted(
        {
            round(pcbnew.ToMM(pad.GetPosition().y), 3)
            for pad in (u1.Pads() if u1 is not None else [])
        }
    )
    controller_socket_row_spacing_mm = (
        round(controller_rows[1] - controller_rows[0], 3)
        if len(controller_rows) == 2
        else None
    )

    unused_npth_boxes = [
        bounding_box_mm(pad)
        for switch in switches
        for pad in switch.Pads()
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH
    ]
    legacy_mount_hole_refs = sorted(
        footprint.GetReference()
        for footprint in footprints
        if re.fullmatch(r"H\d+", footprint.GetReference())
    )
    switch_pad_items = [
        (switch.GetReference(), pad.GetNetname(), bounding_box_mm(pad), pad)
        for switch in switches
        for pad in switch.Pads()
        if pad.GetNumber()
    ]
    switch_pad_boxes = [item[2] for item in switch_pad_items]
    socket_body_boxes = [
        bounding_box_mm(item)
        for switch in switches
        for item in switch.GraphicalItems()
        if item.GetLayer() == pcbnew.B_Fab
    ]
    diode_clearances: list[dict[str, object]] = []
    diode_hand_solder_clearance_errors: list[str] = []
    diode_edge_clearance_errors: list[str] = []
    diode_tool_approach_errors: list[str] = []
    diode_tool_approaches: list[dict[str, object]] = []
    diode_to_unrelated_route_errors: list[str] = []
    diode_pin_net_errors: list[str] = []
    outline_segments = board_outline_segments_mm(board)
    bottom_exposed_pad_items = [
        (footprint.GetReference(), pad.GetNetname(), bounding_box_mm(pad))
        for footprint in footprints
        for pad in footprint.Pads()
        if pad.GetNumber() and pad.IsOnLayer(pcbnew.B_Mask)
    ]
    untented_bottom_vias = [
        track
        for track in board.GetTracks()
        if isinstance(track, pcbnew.PCB_VIA) and not track.IsTented(pcbnew.B_Mask)
    ]
    bottom_exposed_pad_items.extend(
        ("VIA", via.GetNetname(), bounding_box_mm(via))
        for via in untented_bottom_vias
    )
    switch_assembly_boxes = [
        inflate_box_mm(box, 0.30)
        for _, _, box, _ in switch_pad_items
    ] + unused_npth_boxes + socket_body_boxes
    all_diode_pad_items = [
        (diode.GetReference(), bounding_box_mm(pad))
        for diode in diodes
        for pad in diode.Pads()
    ]
    bottom_route_items: list[dict[str, object]] = []
    for track in board.GetTracks():
        if isinstance(track, pcbnew.PCB_VIA):
            bottom_route_items.append(
                {
                    "kind": "via",
                    "net": track.GetNetname(),
                    "box": bounding_box_mm(track),
                }
            )
        elif track.IsOnLayer(pcbnew.B_Cu):
            start = track.GetStart()
            end = track.GetEnd()
            bottom_route_items.append(
                {
                    "kind": "track",
                    "net": track.GetNetname(),
                    "start": (pcbnew.ToMM(start.x), pcbnew.ToMM(start.y)),
                    "end": (pcbnew.ToMM(end.x), pcbnew.ToMM(end.y)),
                    "half_width_mm": pcbnew.ToMM(track.GetWidth()) / 2.0,
                }
            )
    for diode in diodes:
        diode_pads = list(diode.Pads())
        diode_boxes = [bounding_box_mm(pad) for pad in diode_pads]
        diode_nets = {pad.GetNetname() for pad in diode_pads if pad.GetNetname()}

        pad_nets = {
            pad.GetNumber(): pad.GetNetname()
            for pad in diode_pads
            if pad.GetNumber()
        }
        switch = board.FindFootprintByReference("SW" + diode.GetReference()[1:])
        switch_pad_2_nets = {
            pad.GetNetname()
            for pad in (switch.Pads() if switch is not None else [])
            if pad.GetNumber() == "2"
        }
        expected_row_prefix = "L_ROW" if "left" in path.name.lower() else "R_ROW"
        if set(pad_nets) != {"1", "2"}:
            diode_pin_net_errors.append(
                f"{diode.GetReference()}: expected exactly pins 1/2, found {sorted(pad_nets)}"
            )
        elif not pad_nets["1"].startswith(expected_row_prefix):
            diode_pin_net_errors.append(
                f"{diode.GetReference()} pin 1 cathode must be a {expected_row_prefix} net; "
                f"found {pad_nets['1']!r}"
            )
        elif switch is None or switch_pad_2_nets != {pad_nets["2"]}:
            diode_pin_net_errors.append(
                f"{diode.GetReference()} pin 2 anode {pad_nets['2']!r} does not match "
                f"the paired switch pad-2 net {sorted(switch_pad_2_nets)}"
            )

        def clearance_to(targets: list[tuple[float, float, float, float]]) -> float:
            return min(
                bounding_box_clearance_mm(diode_box, target)
                for diode_box in diode_boxes
                for target in targets
            )

        unrelated_exposed_boxes = [
            box
            for reference, net, box in bottom_exposed_pad_items
            if reference != diode.GetReference() and net not in diode_nets
        ]
        fillet_boxes = [inflate_box_mm(box, 0.30) for box in diode_boxes]
        diode_body_boxes = [
            bounding_box_mm(item)
            for item in diode.GraphicalItems()
            if item.GetLayer() in (pcbnew.B_Fab, pcbnew.B_SilkS)
        ]
        diode_edge_envelope_boxes = [*fillet_boxes]
        if diode_body_boxes:
            diode_edge_envelope_boxes.append(
                (
                    min(box[0] for box in diode_body_boxes),
                    min(box[1] for box in diode_body_boxes),
                    max(box[2] for box in diode_body_boxes),
                    max(box[3] for box in diode_body_boxes),
                )
            )
        edge_cuts_clearance = min(
            segment_to_box_clearance_mm(start, end, envelope)
            for envelope in diode_edge_envelope_boxes
            for start, end in outline_segments
        )
        fillet_to_switch_assembly = min(
            bounding_box_clearance_mm(diode_box, target)
            for diode_box in fillet_boxes
            for target in switch_assembly_boxes
        )
        unrelated_route_clearances: list[float] = []
        for route in bottom_route_items:
            if route["net"] in diode_nets:
                continue
            for fillet_box in fillet_boxes:
                if route["kind"] == "via":
                    route_clearance = bounding_box_clearance_mm(
                        fillet_box,
                        route["box"],
                    )
                else:
                    route_clearance = segment_to_box_clearance_mm(
                        route["start"],
                        route["end"],
                        fillet_box,
                    ) - float(route["half_width_mm"])
                unrelated_route_clearances.append(route_clearance)
        fillet_to_unrelated_route = (
            min(unrelated_route_clearances)
            if unrelated_route_clearances
            else math.inf
        )
        clearances = {
            "reference": diode.GetReference(),
            "unused_npth_mm": clearance_to(unused_npth_boxes),
            "switch_pad_mm": clearance_to(switch_pad_boxes),
            "socket_body_mm": clearance_to(socket_body_boxes),
            "unrelated_exposed_copper_mm": clearance_to(unrelated_exposed_boxes),
            "fillet_to_switch_assembly_mm": fillet_to_switch_assembly,
            "fillet_to_unrelated_route_mm": fillet_to_unrelated_route,
            "edge_cuts_mm": edge_cuts_clearance,
        }
        diode_clearances.append(clearances)
        for label in (
            "unused_npth_mm",
            "switch_pad_mm",
            "unrelated_exposed_copper_mm",
        ):
            if float(clearances[label]) < 1.0 - 1e-6:
                diode_hand_solder_clearance_errors.append(
                    f"{diode.GetReference()} {label}={float(clearances[label]):.3f} mm"
                )
        if fillet_to_switch_assembly <= 1e-6:
            diode_hand_solder_clearance_errors.append(
                f"{diode.GetReference()} solder-fillet envelope intersects switch assembly"
            )
        if edge_cuts_clearance < 1.3 - 1e-6:
            diode_edge_clearance_errors.append(
                f"{diode.GetReference()} edge_cuts_mm={edge_cuts_clearance:.3f} mm"
            )
        if fillet_to_unrelated_route < 0.10 - 1e-6:
            diode_to_unrelated_route_errors.append(
                f"{diode.GetReference()} solder-fillet envelope to unrelated B.Cu routing "
                f"is {fillet_to_unrelated_route:.3f} mm; expected at least 0.100 mm"
            )

        if switch is None:
            diode_tool_approach_errors.append(
                f"{diode.GetReference()}: matching switch is missing"
            )
            continue
        approach_obstacles = switch_assembly_boxes + [
            inflate_box_mm(box, 0.30)
            for reference, box in all_diode_pad_items
            if reference != diode.GetReference()
        ]
        for pad, pad_box in zip(diode_pads, diode_boxes):
            corridors = {
                "north": (
                    pad_box[0] - 0.40,
                    pad_box[1] - 1.50,
                    pad_box[2] + 0.40,
                    pad_box[1],
                ),
                "south": (
                    pad_box[0] - 0.40,
                    pad_box[3],
                    pad_box[2] + 0.40,
                    pad_box[3] + 1.50,
                ),
                "west": (
                    pad_box[0] - 1.50,
                    pad_box[1] - 0.40,
                    pad_box[0],
                    pad_box[3] + 0.40,
                ),
                "east": (
                    pad_box[2],
                    pad_box[1] - 0.40,
                    pad_box[2] + 1.50,
                    pad_box[3] + 0.40,
                ),
            }
            direction = next(
                (
                    candidate_direction
                    for candidate_direction, corridor in corridors.items()
                    if not any(
                        boxes_overlap_mm(corridor, obstacle)
                        for obstacle in approach_obstacles
                    )
                ),
                None,
            )
            if direction is None:
                diode_tool_approach_errors.append(
                    f"{diode.GetReference()} pad {pad.GetNumber()}: no unobstructed "
                    "1.50 mm cardinal tool corridor"
                )
            else:
                diode_tool_approaches.append(
                    {
                        "reference": diode.GetReference(),
                        "pad": pad.GetNumber(),
                        "direction": direction,
                        "length_mm": 1.5,
                    }
                )
    diode_hand_solder_clearance_errors.extend(diode_tool_approach_errors)
    diode_hand_solder_clearance_errors.extend(diode_to_unrelated_route_errors)
    side = "left" if "left" in path.name.lower() else "right"
    antenna_direction = 1 if side == "left" else -1
    battery_lead_slot_on_usb_side = bool(
        u1
        and len(battery_slots) == 1
        and (
            pcbnew.ToMM(battery_slots[0].GetPosition().x - u1.GetPosition().x)
            * antenna_direction
            < 0
        )
    )

    forbidden_power_names = {"BAT-", "NN_B-"}
    forbidden_carrier_power_nets = sorted(
        {
            item.GetNetname()
            for footprint in footprints
            for item in footprint.Pads()
            if item.GetNetname() in forbidden_power_names
        }
        | {
            track.GetNetname()
            for track in board.GetTracks()
            if track.GetNetname() in forbidden_power_names
        }
    )
    controller_power_nets = sorted(
        {
            item.GetNetname()
            for footprint in footprints
            for item in footprint.Pads()
            if item.GetNetname() in {"BAT+", "NN_B+", "GND"}
        }
        | {
            track.GetNetname()
            for track in board.GetTracks()
            if track.GetNetname() in {"BAT+", "NN_B+", "GND"}
        }
    )
    drawings = list(board.GetDrawings())
    board_text = {
        drawing.GetText()
        for drawing in drawings
        if isinstance(drawing, pcbnew.PCB_TEXT)
    }
    registration_label_layers = {
        drawing.GetText(): pcbnew.LayerName(drawing.GetLayer())
        for drawing in drawings
        if isinstance(drawing, pcbnew.PCB_TEXT)
        and drawing.GetText().startswith("H")
        and drawing.GetText()[1:].isdigit()
    }
    drc_path = path.with_suffix(".drc.json")
    drc = json.loads(drc_path.read_text(encoding="utf-8")) if drc_path.is_file() else {}
    return {
        "switch_count": len(switches),
        "diode_count": len(diodes),
        "diode_footprint_names": {
            str(diode.GetFPID().GetLibItemName())
            for diode in diodes
        },
        "diode_values": {diode.GetValue() for diode in diodes},
        "diode_pin_net_errors": diode_pin_net_errors,
        "diode_footprint_geometry_errors": diode_footprint_geometry_errors,
        "switch_footprint_names": {
            str(switch.GetFPID().GetLibItemName())
            for switch in switches
        },
        "alternate_contact_net_mismatches": mismatches,
        "switch_footprint_geometry_errors": switch_footprint_geometry_errors,
        "switch_layout_errors": switch_layout_errors,
        "switch_layout_max_position_error_mm": switch_layout_max_position_error_mm,
        "stabilizer_refs": sorted(
            footprint.GetReference()
            for footprint in footprints
            if footprint.GetReference().startswith("STAB")
        ),
        "registration_hole_count": len(registration_holes),
        "registration_hole_errors": registration_hole_errors,
        "legacy_mount_hole_refs": legacy_mount_hole_refs,
        "mounting_hole_positions_mm": mounting_hole_positions_mm,
        "mounting_hole_errors": mounting_hole_errors,
        "mounting_hole_clearances": mounting_hole_clearances,
        "mounting_hole_driver_copper_errors": mounting_hole_driver_copper_errors,
        "mounting_hole_silkscreen_errors": mounting_hole_silkscreen_errors,
        "mounting_hole_head_clearance_errors": mounting_hole_head_clearance_errors,
        "route_track_via_count": sum(route_signatures.values()),
        "route_digest_sha256": _route_counter_digest(route_signatures),
        "registration_label_layers": registration_label_layers,
        "carrier_power_pad_refs": sorted(
            footprint.GetReference()
            for footprint in footprints
            if footprint.GetReference() in {"J_BAT1", "SW_PWR1"}
        ),
        "battery_lead_slot_count": len(battery_slots),
        "battery_lead_slot_errors": battery_lead_slot_errors,
        "battery_lead_slot_on_usb_side": battery_lead_slot_on_usb_side,
        "forbidden_carrier_power_nets": forbidden_carrier_power_nets,
        "controller_power_nets": controller_power_nets,
        "controller_power_geometry": power_geometry,
        "controller_service_clearance": service_clearance,
        "controller_service_clearance_errors": service_clearance["errors"],
        "controller_socket_row_spacing_mm": controller_socket_row_spacing_mm,
        "controller_contract_errors": controller_contract_errors,
        "reset_contract_errors": reset_contract_errors,
        "minimum_diode_to_unused_npth_clearance_mm": round(
            min(float(item["unused_npth_mm"]) for item in diode_clearances), 3
        ),
        "minimum_diode_to_unrelated_pad_clearance_mm": round(
            min(float(item["switch_pad_mm"]) for item in diode_clearances), 3
        ),
        "minimum_diode_to_unrelated_exposed_copper_clearance_mm": round(
            min(float(item["unrelated_exposed_copper_mm"]) for item in diode_clearances), 3
        ),
        "minimum_diode_to_socket_body_clearance_mm": round(
            min(float(item["socket_body_mm"]) for item in diode_clearances), 3
        ),
        "minimum_diode_fillet_to_switch_assembly_clearance_mm": round(
            min(float(item["fillet_to_switch_assembly_mm"]) for item in diode_clearances), 3
        ),
        "minimum_diode_fillet_to_unrelated_route_mm": (
            round(
                min(float(item["fillet_to_unrelated_route_mm"]) for item in diode_clearances),
                3,
            )
            if any(
                math.isfinite(float(item["fillet_to_unrelated_route_mm"]))
                for item in diode_clearances
            )
            else None
        ),
        "minimum_diode_fillet_to_edge_cuts_clearance_mm": round(
            min(float(item["edge_cuts_mm"]) for item in diode_clearances), 3
        ),
        "diode_clearances": diode_clearances,
        "untented_bottom_via_count": len(untented_bottom_vias),
        "diode_tool_approach_errors": diode_tool_approach_errors,
        "diode_tool_approaches": diode_tool_approaches,
        "diode_to_unrelated_route_errors": diode_to_unrelated_route_errors,
        "diode_edge_clearance_errors": diode_edge_clearance_errors,
        "diode_hand_solder_clearance_errors": diode_hand_solder_clearance_errors,
        "board_text": board_text,
        "drc_violation_count": len(drc.get("violations", [])),
        "drc_unconnected_count": len(drc.get("unconnected_items", [])),
        "drc_ignored_checks": sorted(item["key"] for item in drc.get("ignored_checks", [])),
    }


def analyze_v2_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def verify_active_v2_board_text_contract(board_text: Iterable[str]) -> list[str]:
    exact_text = set(board_text)
    errors = [
        f"forbidden stale board text remains: {text}"
        for text in sorted(FORBIDDEN_ACTIVE_V2_BOARD_TEXTS & exact_text)
    ]
    errors.extend(
        f"required board text is missing: {text}"
        for text in sorted(REQUIRED_ACTIVE_V2_BOARD_TEXTS - exact_text)
    )
    return errors


def _repository_artifact_errors(
    record: object,
    *,
    label: str,
    measurement: bool,
    seen_paths: set[str] | None = None,
) -> list[str]:
    if not isinstance(record, dict):
        return [f"{label} is not an artifact record"]
    errors: list[str] = []
    relative_path = record.get("path")
    if not isinstance(relative_path, str) or not relative_path:
        return [f"{label} path is missing"]
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return [f"{label} path must be a repository-relative path without '..'"]
    resolved = (ROOT / candidate).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        return [f"{label} path escapes the repository"]
    path_key = resolved.as_posix().casefold()
    if seen_paths is not None:
        if path_key in seen_paths:
            errors.append(f"{label} reuses an evidence path")
        else:
            seen_paths.add(path_key)
    if not resolved.is_file():
        return [f"{label} file is missing: {relative_path}"]
    actual_size = resolved.stat().st_size
    if record.get("size_bytes") != actual_size:
        errors.append(f"{label} size is missing or stale")
    digest = record.get("sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        errors.append(f"{label} SHA-256 is missing or malformed")
    elif digest != sha256_file(resolved):
        errors.append(f"{label} SHA-256 is stale")
    else:
        errors.extend(_git_index_artifact_errors(resolved, digest, label=label))
    if not isinstance(record.get("kind"), str) or not record.get("kind"):
        errors.append(f"{label} kind is missing")
    if measurement:
        measured_at = record.get("measured_at")
        try:
            datetime.fromisoformat(str(measured_at).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            errors.append(f"{label} measured_at is not an ISO timestamp")
        if not isinstance(record.get("equipment_id"), str) or not record.get("equipment_id"):
            errors.append(f"{label} equipment_id is missing")
        calibration = record.get("calibration_evidence")
        if calibration == "not_applicable_nonmeasurement":
            errors.append(f"{label} calibration evidence cannot be waived for a measurement")
        else:
            errors.extend(
                _repository_artifact_errors(
                    calibration,
                    label=f"{label} calibration evidence",
                    measurement=False,
                    seen_paths=seen_paths,
                )
            )
            if isinstance(calibration, dict) and calibration.get("kind") != "calibration-certificate":
                errors.append(f"{label} calibration evidence kind is not calibration-certificate")
    return errors


def _git_index_artifact_errors(path: Path, digest: str, *, label: str) -> list[str]:
    try:
        relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return [f"{label} path escapes the repository"]
    try:
        completed = subprocess.run(
            ["git", "show", f":{relative}"],
            cwd=ROOT,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return [f"{label} cannot be checked against the Git index: {error}"]
    if completed.returncode != 0:
        return [f"{label} is not tracked in the candidate Git index"]
    if sha256_bytes(completed.stdout) != digest:
        return [f"{label} does not match the candidate Git-index blob"]
    return []


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _contains_identity_placeholder(value: object) -> bool:
    if not isinstance(value, str):
        return False
    raw_tokens = re.findall(r"[A-Z0-9]+", value.upper())
    tokens: list[str] = []
    index = 0
    while index < len(raw_tokens):
        if len(raw_tokens[index]) == 1 and raw_tokens[index].isalpha():
            end = index
            while (
                end < len(raw_tokens)
                and len(raw_tokens[end]) == 1
                and raw_tokens[end].isalpha()
            ):
                end += 1
            if end - index >= 2:
                tokens.append("".join(raw_tokens[index:end]))
                index = end
                continue
        tokens.append(raw_tokens[index])
        index += 1
    if not tokens:
        return False
    if len(tokens) == 1 and tokens[0] in IDENTITY_PLACEHOLDER_TOKENS:
        return True
    for phrase in IDENTITY_PLACEHOLDER_PHRASES:
        width = len(phrase)
        if any(
            tuple(tokens[start : start + width]) == phrase
            for start in range(len(tokens) - width + 1)
        ):
            return True
    for token_index, token in enumerate(tokens):
        numeric_placeholder = re.fullmatch(r"([A-Z]+)(\d+)", token)
        if (
            numeric_placeholder is not None
            and numeric_placeholder.group(1) in IDENTITY_PLACEHOLDER_NUMERIC_PREFIXES
        ):
            return True
        if token not in IDENTITY_PLACEHOLDER_TOKENS:
            continue
        previous = tokens[token_index - 1] if token_index else None
        following = tokens[token_index + 1] if token_index + 1 < len(tokens) else None
        if (
            previous in IDENTITY_PLACEHOLDER_GENERIC_CONTEXT
            or following in IDENTITY_PLACEHOLDER_GENERIC_CONTEXT
            or token_index == len(tokens) - 1
            or (
                following is not None
                and following.isdigit()
                and token in IDENTITY_PLACEHOLDER_NUMERIC_PREFIXES
            )
        ):
            return True
    return False


def _valid_procurement_manufacturer(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and bool(re.search(r"[A-Za-z0-9]", value))
        and not _contains_identity_placeholder(value)
    )


def _valid_procurement_identifier(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.!+_:/-]*", value))
        and bool(re.search(r"\d", value))
        and not _contains_identity_placeholder(value)
    )


def _valid_drawing_revision(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(
            re.fullmatch(
                r"(?:REV[-_.]?[A-Za-z0-9][A-Za-z0-9._-]*|R\d[A-Za-z0-9._-]*|V\d[A-Za-z0-9._-]*)",
                value,
                re.IGNORECASE,
            )
        )
        and not _contains_identity_placeholder(value)
    )


def _valid_identity_for_field(key: str, value: object) -> bool:
    normalized = key.lower()
    if normalized in {"manufacturer", "supplier", "vendor"} or normalized.endswith(
        ("_manufacturer", "_supplier", "_vendor")
    ):
        return _valid_procurement_manufacturer(value)
    if normalized in {
        "coupon_id",
        "doc_id",
        "doc_identity",
        "document_code",
        "document_id",
        "document_identity",
        "drawing_id",
        "drawing_identity",
        "lot",
        "mpn",
        "order_code",
        "part_number",
        "pn",
        "production_lot_id",
        "sku",
        "specimen_coupon_id",
    } or normalized.endswith(
        (
            "_doc_id",
            "_doc_identity",
            "_document_id",
            "_document_identity",
            "_drawing_id",
            "_drawing_identity",
            "_lot",
            "_mpn",
            "_order_code",
            "_part_number",
            "_sku",
        )
    ):
        return _valid_procurement_identifier(value)
    if normalized in {"drawing_revision", "hardware_revision"} or normalized.endswith(
        ("_drawing_revision", "_hardware_revision")
    ):
        return _valid_drawing_revision(value)
    return (
        isinstance(value, str)
        and bool(value.strip())
        and not _contains_identity_placeholder(value)
    )


def _procurement_object_identity_errors(
    value: object,
    *,
    label: str,
) -> list[str]:
    errors: list[str] = []

    def visit(item: object, path: str, field: str | None = None) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                child_path = f"{path}.{key}"
                visit(child, child_path, str(key))
            return
        if isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, f"{path}[{index}]", field)
            return
        if isinstance(item, str) and field is not None and not _valid_identity_for_field(
            field, item
        ):
            errors.append(f"{path} is malformed or retains a pending procurement identity")

    visit(value, label)
    return errors


def _validate_document_set(
    documents: object,
    expected_kinds: set[str],
    *,
    label: str,
    seen_paths: set[str],
) -> tuple[dict[str, dict[str, object]], list[str]]:
    errors: list[str] = []
    if not isinstance(documents, dict) or set(documents) != expected_kinds:
        return {}, [f"{label} document set is incomplete or stale"]
    typed: dict[str, dict[str, object]] = {}
    document_ids: set[str] = set()
    for kind in sorted(expected_kinds):
        record = documents[kind]
        errors.extend(
            _repository_artifact_errors(
                record,
                label=f"{label} {kind}",
                measurement=False,
                seen_paths=seen_paths,
            )
        )
        if not isinstance(record, dict):
            continue
        typed[kind] = record
        if record.get("kind") != kind:
            errors.append(f"{label} {kind} artifact kind is missing or stale")
        document_id = record.get("document_id")
        if not _valid_procurement_identifier(document_id):
            errors.append(f"{label} {kind} document identity is malformed or pending")
        elif document_id in document_ids:
            errors.append(f"{label} {kind} document identity is duplicated")
        else:
            document_ids.add(str(document_id))
    return typed, errors


def _records_by_half(
    records: object,
    *,
    label: str,
) -> tuple[dict[str, dict[str, object]], list[str]]:
    if not isinstance(records, list):
        return {}, [f"{label} records are missing"]
    errors: list[str] = []
    by_half: dict[str, dict[str, object]] = {}
    for record in records:
        if not isinstance(record, dict):
            errors.append(f"{label} contains a non-record entry")
            continue
        half = record.get("half")
        if half not in {"left", "right"}:
            errors.append(f"{label} half must be left or right")
            continue
        if half in by_half:
            errors.append(f"{label} contains duplicate {half} records")
        by_half[str(half)] = record
    if set(by_half) != {"left", "right"}:
        errors.append(f"{label} must contain exact left and right records")
    return by_half, errors


def _controller_service_metrics(
    data: object,
    *,
    seen_paths: set[str],
) -> tuple[dict[str, object], list[str], dict[str, object]]:
    errors: list[str] = []
    if not isinstance(data, dict) or set(data) != {
        "parts",
        "documents",
        "stack_records",
        "pull_records",
        "service_records",
    }:
        return {}, ["controller service raw data schema is incomplete or stale"], {}
    documents, document_errors = _validate_document_set(
        data["documents"],
        {
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
        },
        label="controller service",
        seen_paths=seen_paths,
    )
    errors.extend(document_errors)
    parts = data.get("parts")
    if not isinstance(parts, dict) or set(parts) != {
        "battery",
        "controller",
        "controller_socket",
        "choc_switch",
        "choc_socket",
        "mx_switch",
        "power_switch",
        "reset_switch",
    }:
        return {}, errors + ["controller service exact purchased-part set is incomplete"], {}
    battery = parts.get("battery")
    controller = parts.get("controller")
    controller_socket = parts.get("controller_socket")
    choc_switch = parts.get("choc_switch")
    choc_socket = parts.get("choc_socket")
    mx_switch = parts.get("mx_switch")
    power = parts.get("power_switch")
    reset = parts.get("reset_switch")
    for name, record, required in (
        (
            "battery",
            battery,
            {
                "manufacturer",
                "mpn",
                "lot",
                "protection_status",
                "maximum_swollen_thickness_mm",
                "lead_conductor_diameter_mm",
                "required_hole_clearance_mm",
            },
        ),
        ("controller", controller, {"manufacturer", "mpn", "hardware_revision"}),
        ("controller socket", controller_socket, {"manufacturer", "mpn", "drawing_revision"}),
        ("Choc V2 switch", choc_switch, {"manufacturer", "mpn", "drawing_revision"}),
        ("Choc socket", choc_socket, {"manufacturer", "mpn", "drawing_revision"}),
        ("MX switch", mx_switch, {"manufacturer", "mpn", "drawing_revision"}),
        ("power switch", power, {"manufacturer", "mpn", "drawing_revision"}),
        ("reset switch", reset, {"manufacturer", "mpn", "drawing_revision"}),
    ):
        if not isinstance(record, dict) or set(record) != required:
            errors.append(f"controller service {name} identity schema is incomplete or stale")
    if errors:
        return {}, errors, {}
    assert all(
        isinstance(record, dict)
        for record in (
            battery,
            controller,
            controller_socket,
            choc_switch,
            choc_socket,
            mx_switch,
            power,
            reset,
        )
    )
    assert isinstance(battery, dict) and isinstance(controller, dict)
    assert isinstance(controller_socket, dict) and isinstance(choc_switch, dict)
    assert isinstance(choc_socket, dict) and isinstance(mx_switch, dict)
    assert isinstance(power, dict) and isinstance(reset, dict)
    for name, record in (
        ("battery", battery),
        ("controller", controller),
        ("controller socket", controller_socket),
        ("Choc V2 switch", choc_switch),
        ("Choc socket", choc_socket),
        ("MX switch", mx_switch),
        ("power switch", power),
        ("reset switch", reset),
    ):
        for key, value in record.items():
            if key in {
                "maximum_swollen_thickness_mm",
                "lead_conductor_diameter_mm",
                "required_hole_clearance_mm",
            }:
                continue
            if not isinstance(value, str) or not value.strip():
                errors.append(f"controller service {name} {key} is missing")
            elif not _valid_identity_for_field(key, value):
                errors.append(
                    f"controller service {name} {key} is malformed or retains a pending identity"
                )
    swollen = _finite_number(battery.get("maximum_swollen_thickness_mm"))
    if swollen is None or swollen <= 0.0:
        errors.append("controller service maximum swollen thickness is invalid")
    lead_diameter = _finite_number(battery.get("lead_conductor_diameter_mm"))
    required_hole_clearance = _finite_number(battery.get("required_hole_clearance_mm"))
    j_bat_drill = 0.90
    lead_hole_clearance = (
        j_bat_drill - lead_diameter if lead_diameter is not None else None
    )
    if (
        lead_diameter is None
        or lead_diameter <= 0.0
        or required_hole_clearance is None
        or required_hole_clearance < 0.0
        or lead_hole_clearance is None
        or lead_hole_clearance < required_hole_clearance
    ):
        errors.append("controller service purchased lead does not fit the 0.90 mm J_BAT1 drill")

    stacks, stack_errors = _records_by_half(data.get("stack_records"), label="controller stack")
    pulls, pull_errors = _records_by_half(data.get("pull_records"), label="lead pull")
    services, service_errors = _records_by_half(data.get("service_records"), label="POWER/RESET service")
    errors.extend(stack_errors + pull_errors + service_errors)
    stack_clearances: list[float] = []
    for half, record in stacks.items():
        required = {
            "half",
            "fully_seated_gap_mm",
            "insulation_thickness_mm",
            "retainer_thickness_mm",
            "socket_pin_protrusion_mm",
            "solder_protrusion_mm",
            "assembly_tolerance_mm",
            "minimum_clearance_mm",
            "controller_install_remove_pass",
            "pouch_compressed",
            "sharp_contact",
        }
        if set(record) != required:
            errors.append(f"controller stack {half} record schema is incomplete or stale")
            continue
        gap = _finite_number(record.get("fully_seated_gap_mm"))
        thicknesses = [
            _finite_number(record.get(key))
            for key in (
                "insulation_thickness_mm",
                "retainer_thickness_mm",
                "socket_pin_protrusion_mm",
                "solder_protrusion_mm",
                "assembly_tolerance_mm",
            )
        ]
        recorded_clearance = _finite_number(record.get("minimum_clearance_mm"))
        if (
            gap is None
            or gap <= 0.0
            or swollen is None
            or any(value is None or value < 0.0 for value in thicknesses)
            or recorded_clearance is None
        ):
            errors.append(f"controller stack {half} dimensions are invalid")
        else:
            recomputed_clearance = gap - swollen - sum(float(value) for value in thicknesses)
            if not math.isclose(recorded_clearance, recomputed_clearance, abs_tol=1e-9):
                errors.append(f"controller stack {half} clearance is not recomputed from raw dimensions")
            if recomputed_clearance < 0.0:
                errors.append(f"controller stack {half} has negative physical clearance")
            stack_clearances.append(recomputed_clearance)
        if (
            record.get("controller_install_remove_pass") is not True
            or record.get("pouch_compressed") is not False
            or record.get("sharp_contact") is not False
        ):
            errors.append(f"controller stack {half} fit result is not passed")
    pull_pass = True
    for half, record in pulls.items():
        required = {
            "half",
            "rated_load_n",
            "rated_duration_s",
            "applied_load_n",
            "applied_duration_s",
            "lead_movement_mm",
            "force_transfer_to_pouch_tab",
        }
        if set(record) != required:
            errors.append(f"lead pull {half} record schema is incomplete or stale")
            pull_pass = False
            continue
        rated_load = _finite_number(record.get("rated_load_n"))
        rated_duration = _finite_number(record.get("rated_duration_s"))
        applied_load = _finite_number(record.get("applied_load_n"))
        applied_duration = _finite_number(record.get("applied_duration_s"))
        movement = _finite_number(record.get("lead_movement_mm"))
        passed = (
            rated_load is not None
            and rated_load > 0.0
            and rated_duration is not None
            and rated_duration > 0.0
            and applied_load is not None
            and applied_load >= rated_load
            and applied_duration is not None
            and applied_duration >= rated_duration
            and movement is not None
            and movement <= 0.0
            and record.get("force_transfer_to_pouch_tab") is False
        )
        pull_pass = pull_pass and passed
        if not passed:
            errors.append(f"lead pull {half} raw result does not pass")
    service_pass = True
    for half, record in services.items():
        required = {
            "half",
            "reset_bootloader_cycles",
            "continuity_on_max_ohm",
            "continuity_off_min_ohm",
            "power_on_resistance_ohm",
            "power_off_resistance_ohm",
            "reset_pressed_resistance_ohm",
            "reset_released_resistance_ohm",
            "power_actuator_travel_mm",
            "minimum_fingertip_access_clearance_mm",
            "power_full_travel_contact_with_reset",
            "power_full_travel_contact_with_controller",
            "power_full_travel_contact_with_keycap",
            "reset_probe_diameter_mm",
            "reset_probe_access_pass",
            "service_pass",
            "controller_contact",
            "adjacent_key_actuation",
            "pad_peel",
            "visible_pcb_flex",
        }
        if set(record) != required:
            errors.append(f"POWER/RESET service {half} record schema is incomplete or stale")
            service_pass = False
            continue
        cycles = _finite_number(record.get("reset_bootloader_cycles"))
        on_max = _finite_number(record.get("continuity_on_max_ohm"))
        off_min = _finite_number(record.get("continuity_off_min_ohm"))
        power_on = _finite_number(record.get("power_on_resistance_ohm"))
        power_off = _finite_number(record.get("power_off_resistance_ohm"))
        reset_pressed = _finite_number(record.get("reset_pressed_resistance_ohm"))
        reset_released = _finite_number(record.get("reset_released_resistance_ohm"))
        power_travel = _finite_number(record.get("power_actuator_travel_mm"))
        fingertip_clearance = _finite_number(
            record.get("minimum_fingertip_access_clearance_mm")
        )
        reset_probe = _finite_number(record.get("reset_probe_diameter_mm"))
        passed = (
            cycles is not None
            and cycles >= 10
            and on_max is not None
            and on_max > 0.0
            and off_min is not None
            and off_min > on_max
            and power_on is not None
            and power_on <= on_max
            and power_off is not None
            and power_off >= off_min
            and reset_pressed is not None
            and reset_pressed <= on_max
            and reset_released is not None
            and reset_released >= off_min
            and power_travel is not None
            and power_travel >= 1.60
            and fingertip_clearance is not None
            and fingertip_clearance > 0.0
            and record.get("power_full_travel_contact_with_reset") is False
            and record.get("power_full_travel_contact_with_controller") is False
            and record.get("power_full_travel_contact_with_keycap") is False
            and reset_probe is not None
            and 0.0 < reset_probe <= 3.0
            and record.get("reset_probe_access_pass") is True
            and record.get("service_pass") is True
            and all(
                record.get(key) is False
                for key in (
                    "controller_contact",
                    "adjacent_key_actuation",
                    "pad_peel",
                    "visible_pcb_flex",
                )
            )
        )
        service_pass = service_pass and passed
        if not passed:
            errors.append(f"POWER/RESET service {half} raw result does not pass")
    metrics = {
        "battery_manufacturer": battery.get("manufacturer"),
        "battery_mpn": battery.get("mpn"),
        "battery_lot": battery.get("lot"),
        "protection_status": battery.get("protection_status"),
        "controller_manufacturer": controller.get("manufacturer"),
        "controller_mpn": controller.get("mpn"),
        "controller_hardware_revision": controller.get("hardware_revision"),
        "controller_socket_manufacturer": controller_socket.get("manufacturer"),
        "controller_socket_mpn": controller_socket.get("mpn"),
        "controller_socket_drawing_revision": controller_socket.get("drawing_revision"),
        "choc_switch_manufacturer": choc_switch.get("manufacturer"),
        "choc_switch_mpn": choc_switch.get("mpn"),
        "choc_switch_drawing_revision": choc_switch.get("drawing_revision"),
        "choc_socket_manufacturer": choc_socket.get("manufacturer"),
        "choc_socket_mpn": choc_socket.get("mpn"),
        "choc_socket_drawing_revision": choc_socket.get("drawing_revision"),
        "mx_switch_manufacturer": mx_switch.get("manufacturer"),
        "mx_switch_mpn": mx_switch.get("mpn"),
        "mx_switch_drawing_revision": mx_switch.get("drawing_revision"),
        "power_switch_manufacturer": power.get("manufacturer"),
        "power_switch_mpn": power.get("mpn"),
        "power_switch_drawing_revision": power.get("drawing_revision"),
        "reset_switch_manufacturer": reset.get("manufacturer"),
        "reset_switch_mpn": reset.get("mpn"),
        "reset_switch_drawing_revision": reset.get("drawing_revision"),
        "lead_drawing_sha256": documents.get("battery_lead_drawing", {}).get("sha256"),
        "protection_declaration_sha256": documents.get(
            "battery_protection_declaration", {}
        ).get("sha256"),
        "controller_datasheet_sha256": documents.get("controller_datasheet", {}).get(
            "sha256"
        ),
        "controller_socket_drawing_sha256": documents.get(
            "controller_socket_drawing", {}
        ).get("sha256"),
        "choc_switch_drawing_sha256": documents.get("choc_switch_drawing", {}).get(
            "sha256"
        ),
        "choc_socket_drawing_sha256": documents.get("choc_socket_drawing", {}).get(
            "sha256"
        ),
        "mx_switch_drawing_sha256": documents.get("mx_switch_drawing", {}).get("sha256"),
        "j_bat_drill_mm": j_bat_drill,
        "lead_conductor_diameter_mm": lead_diameter,
        "lead_to_j_bat_diametral_clearance_mm": lead_hole_clearance,
        "maximum_swollen_thickness_mm": swollen,
        "minimum_stack_clearance_mm": min(stack_clearances) if stack_clearances else None,
        "lead_pull_pass": pull_pass and set(pulls) == {"left", "right"},
        "service_pass": service_pass and set(services) == {"left", "right"},
    }
    identity = {
        "battery_mpn": str(battery.get("mpn", "")),
        "battery_lot": str(battery.get("lot", "")),
        "power_switch_mpn": str(power.get("mpn", "")),
        "choc_switch_mpn": str(choc_switch.get("mpn", "")),
        "choc_socket_mpn": str(choc_socket.get("mpn", "")),
        "mx_switch_mpn": str(mx_switch.get("mpn", "")),
        "purchased_parts": {
            "battery": dict(battery),
            "controller": dict(controller),
            "controller_socket": dict(controller_socket),
            "choc_switch": dict(choc_switch),
            "choc_socket": dict(choc_socket),
            "mx_switch": dict(mx_switch),
            "power_switch": dict(power),
            "reset_switch": dict(reset),
        },
    }
    return metrics, errors, identity


def _physical_scan_metrics(
    data: object,
    *,
    controller_identity: dict[str, object],
) -> tuple[dict[str, object], list[str], dict[str, object]]:
    errors: list[str] = []
    if not isinstance(data, dict) or set(data) != {
        "coupon_id",
        "records",
        "switch_fit_records",
        "keycap_fit_records",
        "diode_records",
    }:
        return {}, ["physical scan raw data schema is incomplete or stale"], {}
    if not _valid_identity_for_field("coupon_id", data.get("coupon_id")):
        errors.append("physical scan coupon identity is missing, malformed, or pending")
    records = data.get("records")
    if not isinstance(records, list):
        return {}, errors + ["physical scan records are missing"], {}
    expected_combinations = {
        (half, voltage, pattern, mode)
        for half in ("left", "right")
        for voltage in (3.0, 3.3)
        for pattern in ("maximum-same-row", "maximum-same-column")
        for mode in ("choc_v2", "mx")
    }
    counts: Counter[tuple[str, float, str, str]] = Counter()
    fault_count = 0
    sample_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {
            "half",
            "supply_voltage_v",
            "pattern",
            "assembly_mode",
            "sample_id",
            "fault_count",
        }:
            errors.append("physical scan contains an incomplete record")
            continue
        voltage = _finite_number(record.get("supply_voltage_v"))
        key = (
            str(record.get("half")),
            voltage if voltage is not None else -1.0,
            str(record.get("pattern")),
            str(record.get("assembly_mode")),
        )
        if key not in expected_combinations:
            errors.append(f"physical scan has an unexpected condition {key}")
            continue
        sample_id = record.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id or sample_id in sample_ids:
            errors.append("physical scan sample IDs are missing or duplicated")
            continue
        sample_ids.add(sample_id)
        faults = _finite_number(record.get("fault_count"))
        if faults is None or faults < 0 or not faults.is_integer():
            errors.append("physical scan fault count is invalid")
            continue
        counts[key] += 1
        fault_count += int(faults)
    if set(counts) != expected_combinations:
        errors.append("physical scan does not cover both halves, voltages, patterns, and assembly modes")
    switch_fit_records = data.get("switch_fit_records")
    expected_fit_keys = {
        (half, mode)
        for half in ("left", "right")
        for mode in ("choc_v2", "mx")
    }
    seen_fit_keys: set[tuple[str, str]] = set()
    if not isinstance(switch_fit_records, list):
        errors.append("physical scan switch/socket fit records are missing")
        switch_fit_records = []
    for record in switch_fit_records:
        if not isinstance(record, dict) or set(record) != {
            "half",
            "assembly_mode",
            "orientation",
            "switch_mpn",
            "socket_mpn",
            "bottom_socket_fit_pass",
            "mx_five_pin_fit_pass",
            "minimum_joint_clearance_mm",
            "minimum_housing_clearance_mm",
        }:
            errors.append("physical scan switch/socket fit contains an incomplete record")
            continue
        key = (str(record.get("half")), str(record.get("assembly_mode")))
        if key not in expected_fit_keys or key in seen_fit_keys:
            errors.append(f"physical scan switch/socket condition is unexpected or duplicated: {key}")
            continue
        seen_fit_keys.add(key)
        joint = _finite_number(record.get("minimum_joint_clearance_mm"))
        housing = _finite_number(record.get("minimum_housing_clearance_mm"))
        expected_orientation = "left_rotated" if key[0] == "left" else "right_mirrored"
        expected_switch = controller_identity.get(
            "choc_switch_mpn" if key[1] == "choc_v2" else "mx_switch_mpn"
        )
        expected_socket = (
            controller_identity.get("choc_socket_mpn") if key[1] == "choc_v2" else "not_populated"
        )
        mode_pass = (
            record.get("bottom_socket_fit_pass") is (key[1] == "choc_v2")
            and record.get("mx_five_pin_fit_pass") is (key[1] == "mx")
        )
        if (
            record.get("orientation") != expected_orientation
            or record.get("switch_mpn") != expected_switch
            or record.get("socket_mpn") != expected_socket
            or not mode_pass
            or joint is None
            or joint < 0.0
            or housing is None
            or housing < 0.0
        ):
            errors.append(f"physical scan switch/socket fit {key} does not pass")
    if seen_fit_keys != expected_fit_keys:
        errors.append("physical scan switch/socket fit does not cover both halves and modes")

    keycap_fit_records = data.get("keycap_fit_records")
    expected_keycap_conditions = {
        (half, mode, width)
        for half in ("left", "right")
        for mode in ("choc_v2", "mx")
        for width in (1.0, 1.25, 1.5, 1.75)
    }
    seen_keycap_conditions: set[tuple[str, str, float]] = set()
    keycap_identities: dict[str, dict[str, object]] = {}
    three_d_count = 0
    if not isinstance(keycap_fit_records, list):
        errors.append("physical scan non-1U/3D keycap records are missing")
        keycap_fit_records = []
    for record in keycap_fit_records:
        if not isinstance(record, dict) or set(record) != {
            "assembly_mode",
            "half",
            "width_u",
            "keycap_manufacturer",
            "keycap_mpn",
            "is_3d_printed",
            "fit_pass",
            "minimum_spacing_mm",
        }:
            errors.append("physical scan keycap fit contains an incomplete record")
            continue
        width = _finite_number(record.get("width_u"))
        mode = str(record.get("assembly_mode"))
        half = str(record.get("half"))
        condition = (half, mode, float(width) if width is not None else -1.0)
        spacing = _finite_number(record.get("minimum_spacing_mm"))
        if condition not in expected_keycap_conditions or condition in seen_keycap_conditions:
            errors.append("physical scan keycap mode/width is unexpected or duplicated")
            continue
        seen_keycap_conditions.add(condition)
        identity_key = f"{mode}:{float(width):.2f}"
        keycap_identity = {
            "assembly_mode": mode,
            "width_u": float(width),
            "manufacturer": record.get("keycap_manufacturer"),
            "mpn": record.get("keycap_mpn"),
            "is_3d_printed": record.get("is_3d_printed"),
        }
        if identity_key in keycap_identities and keycap_identities[identity_key] != keycap_identity:
            errors.append(f"physical scan keycap identity differs between halves: {identity_key}")
        keycap_identities[identity_key] = keycap_identity
        three_d_count += int(record.get("is_3d_printed") is True)
        if (
            not isinstance(record.get("keycap_manufacturer"), str)
            or not record.get("keycap_manufacturer")
            or not _valid_procurement_manufacturer(record.get("keycap_manufacturer"))
            or not isinstance(record.get("keycap_mpn"), str)
            or not record.get("keycap_mpn")
            or not _valid_procurement_identifier(record.get("keycap_mpn"))
            or record.get("fit_pass") is not True
            or spacing is None
            or not 1.60 <= spacing <= 2.00
        ):
            errors.append(f"physical scan keycap {width}U fit/spacing does not pass")
    if seen_keycap_conditions != expected_keycap_conditions or three_d_count < 1:
        errors.append(
            "physical scan does not cover 1U/every non-1U width in both modes and a 3D keycap"
        )

    diode_records = data.get("diode_records")
    seen_diode_halves: set[str] = set()
    if not isinstance(diode_records, list):
        errors.append("physical scan ES1B records are missing")
        diode_records = []
    for record in diode_records:
        if not isinstance(record, dict) or set(record) != {
            "half",
            "manufacturer",
            "mpn",
            "pad1_cathode_polarity_pass",
            "hand_solder_access_pass",
            "minimum_joint_clearance_mm",
            "minimum_housing_clearance_mm",
        }:
            errors.append("physical scan ES1B evidence contains an incomplete record")
            continue
        half = record.get("half")
        joint = _finite_number(record.get("minimum_joint_clearance_mm"))
        housing = _finite_number(record.get("minimum_housing_clearance_mm"))
        if half not in {"left", "right"} or half in seen_diode_halves:
            errors.append("physical scan ES1B half is invalid or duplicated")
            continue
        seen_diode_halves.add(str(half))
        if (
            record.get("manufacturer") != "Jingdao"
            or record.get("mpn") != "ES1B"
            or record.get("pad1_cathode_polarity_pass") is not True
            or record.get("hand_solder_access_pass") is not True
            or joint is None
            or joint < 0.0
            or housing is None
            or housing < 0.0
        ):
            errors.append(f"physical scan ES1B {half} result does not pass")
    if seen_diode_halves != {"left", "right"}:
        errors.append("physical scan ES1B records do not cover both halves")
    metrics = {
        "supply_volts": [3.0, 3.3],
        "patterns": ["maximum-same-row", "maximum-same-column"],
        "assembly_modes": ["choc_v2", "mx"],
        "sample_count_per_condition": min(counts.values()) if counts else 0,
        "fault_count": fault_count,
        "switch_fit_condition_count": len(seen_fit_keys),
        "keycap_widths": sorted(
            {width for _, _, width in seen_keycap_conditions}
        ),
        "keycap_fit_condition_count": len(seen_keycap_conditions),
        "three_d_keycap_record_count": three_d_count,
        "es1b_half_count": len(seen_diode_halves),
    }
    identity = {
        "coupon_id": data.get("coupon_id"),
        "keycaps": keycap_identities,
    }
    return metrics, errors, identity


def _housing_source_contracts(
    source_paths: dict[str, Path],
) -> tuple[dict[str, float], list[str]]:
    path = source_paths.get("housing_manifest")
    if path is None:
        return {}, ["housing raw measurements lack a bound housing manifest"]
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {}, [f"housing source contract cannot be parsed: {error}"]
    parameters = manifest.get("parameters") if isinstance(manifest, dict) else None
    if not isinstance(parameters, dict):
        return {}, ["housing source contract parameters are missing"]
    names = {
        "pilot_diameter_mm": "mounting_pilot_diameter_mm",
        "pilot_depth_mm": "mounting_pilot_depth_mm",
        "closed_bottom_mm": "mounting_closed_bottom_mm",
        "pcb_thickness_mm": "pcb_thickness_mm",
        "pcb_thickness_tolerance_fraction": "pcb_thickness_tolerance_fraction",
        "minimum_tip_clearance_mm": "minimum_tip_clearance_mm",
    }
    values = {
        name: _finite_number(parameters.get(source_name))
        for name, source_name in names.items()
    }
    penetration_range = parameters.get("pcb_tolerance_penetration_range_mm")
    if (
        any(value is None or value <= 0.0 for value in values.values())
        or not isinstance(penetration_range, list)
        or len(penetration_range) != 2
        or any(_finite_number(value) is None for value in penetration_range)
    ):
        return {}, ["housing source contract dimensions are incomplete or invalid"]
    contracts = {name: float(value) for name, value in values.items()}
    contracts["minimum_penetration_mm"] = float(penetration_range[0])
    contracts["maximum_penetration_mm"] = float(penetration_range[1])
    contracts["minimum_pcb_thickness_mm"] = contracts["pcb_thickness_mm"] * (
        1.0 - contracts["pcb_thickness_tolerance_fraction"]
    )
    contracts["maximum_pcb_thickness_mm"] = contracts["pcb_thickness_mm"] * (
        1.0 + contracts["pcb_thickness_tolerance_fraction"]
    )
    return contracts, []


def _housing_head_adjacency_contracts(
    source_paths: dict[str, Path],
) -> tuple[dict[str, dict[str, object]], list[str]]:
    contracts: dict[str, dict[str, object]] = {}
    errors: list[str] = []
    layouts = {
        "left": make_left_keys_x3_v2(),
        "right": make_right_keys_x3_v2(),
    }
    for half, binding in (("left", "left_board"), ("right", "right_board")):
        path = source_paths.get(binding)
        if path is None or not path.is_file():
            errors.append(f"housing head-adjacency lacks the bound {half} board")
            continue
        try:
            board = pcbnew.LoadBoard(str(path))
        except Exception as error:  # pragma: no cover - pcbnew exception types vary
            errors.append(f"housing head-adjacency cannot load {half} board: {error}")
            continue
        footprints = {item.GetReference(): item for item in board.GetFootprints()}
        switches = {
            f"SW{index}": (footprints.get(f"SW{index}"), key)
            for index, key in enumerate(layouts[half], start=1)
        }
        if any(footprint is None for footprint, _ in switches.values()):
            errors.append(f"housing head-adjacency {half} switch reference set is incomplete")
            continue
        mounting_refs = sorted(
            (
                reference
                for reference in footprints
                if re.fullmatch(r"MH\d+", reference)
            ),
            key=lambda reference: int(reference[2:]),
        )
        expected_count = 8 if half == "left" else 9
        if len(mounting_refs) != expected_count:
            errors.append(f"housing head-adjacency {half} mounting-hole set is incomplete")
            continue
        for mounting_ref in mounting_refs:
            mounting_position = footprints[mounting_ref].GetPosition()

            def keycap_distance(item: tuple[str, tuple[object, object]]) -> tuple[float, float, str]:
                reference, (footprint, key) = item
                assert footprint is not None
                position = footprint.GetPosition()
                dx = abs(pcbnew.ToMM(position.x - mounting_position.x))
                dy = abs(pcbnew.ToMM(position.y - mounting_position.y))
                half_width = (19.05 * float(key.w_u) - 1.0) / 2.0
                half_height = 18.05 / 2.0
                outside_x = max(dx - half_width, 0.0)
                outside_y = max(dy - half_height, 0.0)
                edge_distance = math.hypot(outside_x, outside_y)
                return edge_distance, math.hypot(dx, dy), reference

            for switch_ref, (_, switch_key) in switches.items():
                edge_distance, _, _ = keycap_distance(
                    (switch_ref, switches[switch_ref])
                )
                if edge_distance > 1.5 + 1e-9:
                    continue
                contract_key = f"{half}:{mounting_ref}:{switch_ref}"
                contracts[contract_key] = {
                    "half": half,
                    "mounting_hole_reference": mounting_ref,
                    "overlapping_switch_reference": switch_ref,
                    "width_u": float(switch_key.w_u),
                }
    per_hole_counts = Counter(
        (record["half"], record["mounting_hole_reference"])
        for record in contracts.values()
    )
    if (
        len(contracts) != 16
        or len(per_hole_counts) != 14
        or sum(count > 1 for count in per_hole_counts.values()) != 2
    ):
        errors.append(
            "housing head-adjacency is not the exact P2 reinforcement set of 16 overlaps at 14 holes "
            "(2 multi-switch)"
        )
    return contracts, errors


def _housing_metrics(
    data: object,
    *,
    seen_paths: set[str],
    controller_identity: dict[str, object],
    scan_identity: dict[str, object],
    source_contracts: dict[str, float],
    head_adjacency_contracts: dict[str, dict[str, object]],
    calibration_evidence: object,
) -> tuple[dict[str, object], list[str]]:
    errors: list[str] = []
    if not isinstance(data, dict) or set(data) != {
        "fastener_identity",
        "production_print",
        "assembly_identity",
        "documents",
        "fastener_records",
        "assembly_fit_records",
        "head_adjacent_fit_records",
        "deflection_records",
    }:
        return {}, ["housing raw data schema is incomplete or stale"]
    documents, document_errors = _validate_document_set(
        data["documents"],
        {
            "driver_drawing",
            "fastener_drawing",
            "slicer_profile",
            "structural_specimen_trace",
        },
        label="housing fastener",
        seen_paths=seen_paths,
    )
    errors.extend(document_errors)
    identity = data.get("fastener_identity")
    required_identity = {
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
        "driver_manufacturer",
        "driver_mpn",
        "minimum_under_head_length_mm",
        "maximum_under_head_length_mm",
        "minimum_head_diameter_mm",
        "maximum_head_diameter_mm",
        "minimum_head_height_mm",
        "maximum_head_height_mm",
        "maximum_finished_pcb_hole_diameter_mm",
        "minimum_radial_bearing_width_mm",
        "maximum_driver_shaft_diameter_mm",
        "maximum_driver_runout_mm",
        "maximum_driver_sweep_mm",
    }
    if not isinstance(identity, dict) or set(identity) != required_identity:
        return {}, errors + ["housing exact fastener/driver identity is incomplete"]
    numeric_identity_keys = {
        "nominal_thread_diameter_mm",
        "thread_pitch_mm",
        "thread_flank_angle_degrees",
        "thread_major_diameter_mm",
        "thread_minor_diameter_mm",
        "minimum_under_head_length_mm",
        "maximum_under_head_length_mm",
        "minimum_head_diameter_mm",
        "maximum_head_diameter_mm",
        "minimum_head_height_mm",
        "maximum_head_height_mm",
        "maximum_finished_pcb_hole_diameter_mm",
        "minimum_radial_bearing_width_mm",
        "maximum_driver_shaft_diameter_mm",
        "maximum_driver_runout_mm",
        "maximum_driver_sweep_mm",
    }
    for key in required_identity - numeric_identity_keys:
        if not isinstance(identity.get(key), str) or not identity.get(key):
            errors.append(f"housing fastener identity {key} is missing")
        elif not _valid_identity_for_field(key, identity.get(key)):
            errors.append(
                f"housing fastener identity {key} is malformed or retains a placeholder"
            )
    if identity.get("head_style") != "rounded_pan_or_button":
        errors.append("housing fastener head style is not rounded pan/button")
    if identity.get("thread_classification") != "direct_plastic_thread_forming":
        errors.append("housing fastener is not classified as direct-plastic thread-forming")
    if identity.get("thread_form") not in DIRECT_PLASTIC_THREAD_FORMS:
        errors.append("housing fastener thread form is not a controlled direct-plastic taxonomy value")
    numeric_identity = {
        key: _finite_number(identity.get(key)) for key in numeric_identity_keys
    }
    if any(value is None or value <= 0.0 for value in numeric_identity.values()):
        errors.append("housing fastener dimensional identity contains a missing/nonpositive value")
    else:
        minimum_length = float(numeric_identity["minimum_under_head_length_mm"])
        maximum_length = float(numeric_identity["maximum_under_head_length_mm"])
        minimum_head_diameter = float(numeric_identity["minimum_head_diameter_mm"])
        maximum_head_diameter = float(numeric_identity["maximum_head_diameter_mm"])
        minimum_head_height = float(numeric_identity["minimum_head_height_mm"])
        maximum_head_height = float(numeric_identity["maximum_head_height_mm"])
        maximum_hole = float(numeric_identity["maximum_finished_pcb_hole_diameter_mm"])
        bearing = float(numeric_identity["minimum_radial_bearing_width_mm"])
        shaft = float(numeric_identity["maximum_driver_shaft_diameter_mm"])
        runout = float(numeric_identity["maximum_driver_runout_mm"])
        sweep = float(numeric_identity["maximum_driver_sweep_mm"])
        if not math.isclose(
            float(numeric_identity["nominal_thread_diameter_mm"]),
            1.4,
            abs_tol=1e-9,
        ):
            errors.append("housing fastener nominal thread diameter is not exactly M1.4")
        pitch = float(numeric_identity["thread_pitch_mm"])
        flank_angle = float(numeric_identity["thread_flank_angle_degrees"])
        major = float(numeric_identity["thread_major_diameter_mm"])
        minor = float(numeric_identity["thread_minor_diameter_mm"])
        if (
            pitch <= 0.0
            or not math.isclose(flank_angle, 30.0, abs_tol=1e-9)
            or not 0.0 < minor < major
            or not math.isclose(major, 1.4, abs_tol=1e-9)
        ):
            errors.append("housing direct-plastic thread geometry is invalid or not M1.4")
        if minimum_length > maximum_length:
            errors.append("housing fastener under-head length tolerance is reversed")
        if minimum_head_diameter > maximum_head_diameter or maximum_head_diameter > 3.0 + 1e-9:
            errors.append("housing fastener head diameter tolerance exceeds the 3.00 mm envelope")
        if minimum_head_height > maximum_head_height or maximum_head_height > 1.2 + 1e-9:
            errors.append("housing fastener head height tolerance exceeds the 1.20 mm envelope")
        recomputed_bearing = (minimum_head_diameter - maximum_hole) / 2.0
        if recomputed_bearing <= 0.0 or not math.isclose(
            bearing, recomputed_bearing, abs_tol=1e-9
        ):
            errors.append("housing fastener radial bearing is not recomputed from head/hole limits")
        if not math.isclose(sweep, shaft + 2.0 * runout, abs_tol=1e-9) or sweep > 3.0 + 1e-9:
            errors.append("housing driver sweep is not shaft plus two-sided runout within 3.00 mm")

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
    fastener_drawing_record = documents.get("fastener_drawing", {})
    fastener_drawing: object = None
    if isinstance(fastener_drawing_record, dict) and isinstance(
        fastener_drawing_record.get("path"), str
    ):
        try:
            fastener_drawing = json.loads(
                (ROOT / str(fastener_drawing_record["path"])).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"housing controlled fastener drawing cannot be parsed: {error}")
    expected_fastener_drawing = {
        "schema": "kc2-x3-v2-fastener-drawing-v1",
        **{field: identity.get(field) for field in controlled_fastener_fields},
    }
    if fastener_drawing != expected_fastener_drawing:
        errors.append("housing fastener identity/geometry is not bound to its controlled drawing")

    production_print = data.get("production_print")
    required_print_fields = {
        "production_process",
        "printer_manufacturer",
        "printer_model",
        "specimen_coupon_id",
        "production_lot_id",
        "material_manufacturer",
        "material_product",
        "material_mpn",
        "material_lot",
        "nozzle_diameter_mm",
        "layer_height_mm",
        "print_orientation",
        "slicer_name",
        "slicer_version",
        "wall_perimeter_count",
        "infill_pattern",
        "infill_density_percent",
        "extrusion_width_mm",
        "flow_percent",
        "top_solid_layers",
        "bottom_solid_layers",
        "nozzle_temperature_c",
        "bed_temperature_c",
        "fan_percent",
        "print_speed_mm_s",
        "travel_speed_mm_s",
        "print_acceleration_mm_s2",
        "travel_acceleration_mm_s2",
        "slicer_profile_sha256",
    }
    if not isinstance(production_print, dict) or set(production_print) != required_print_fields:
        errors.append("housing production print identity/process schema is incomplete or stale")
        production_print = {}
    else:
        numeric_print_fields = {
            "nozzle_diameter_mm",
            "layer_height_mm",
            "wall_perimeter_count",
            "infill_density_percent",
            "extrusion_width_mm",
            "flow_percent",
            "top_solid_layers",
            "bottom_solid_layers",
            "nozzle_temperature_c",
            "bed_temperature_c",
            "fan_percent",
            "print_speed_mm_s",
            "travel_speed_mm_s",
            "print_acceleration_mm_s2",
            "travel_acceleration_mm_s2",
        }
        for key in required_print_fields - numeric_print_fields:
            if not isinstance(production_print.get(key), str) or not production_print.get(key):
                errors.append(f"housing production print {key} is missing")
            elif not _valid_identity_for_field(key, production_print.get(key)):
                errors.append(
                    f"housing production print {key} is malformed or retains a placeholder"
                )
        nozzle = _finite_number(production_print.get("nozzle_diameter_mm"))
        layer = _finite_number(production_print.get("layer_height_mm"))
        if nozzle is None or nozzle <= 0.0 or layer is None or layer <= 0.0 or layer > nozzle:
            errors.append("housing production nozzle/layer measurements are invalid")
        if production_print.get("print_orientation") != "desk_contact_face_down":
            errors.append("housing production print orientation is not desk_contact_face_down")
        if production_print.get("production_process") not in {"FFF", "FDM"}:
            errors.append("housing production process is not the controlled FFF/FDM enum")
        if production_print.get("specimen_coupon_id") == scan_identity.get("coupon_id"):
            errors.append("housing structural specimen identity reuses the electrical scan coupon")
        integer_settings = {
            "wall_perimeter_count": (2, 99),
            "top_solid_layers": (1, 99),
            "bottom_solid_layers": (1, 99),
        }
        for key, (minimum, maximum) in integer_settings.items():
            value = production_print.get(key)
            if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
                errors.append(f"housing production {key} is invalid")
        bounded_settings = {
            "infill_density_percent": (1.0, 100.0),
            "extrusion_width_mm": (0.1, 2.0),
            "flow_percent": (50.0, 150.0),
            "nozzle_temperature_c": (150.0, 350.0),
            "bed_temperature_c": (0.0, 150.0),
            "fan_percent": (0.0, 100.0),
            "print_speed_mm_s": (1.0, 500.0),
            "travel_speed_mm_s": (1.0, 1000.0),
            "print_acceleration_mm_s2": (1.0, 50000.0),
            "travel_acceleration_mm_s2": (1.0, 50000.0),
        }
        for key, (minimum, maximum) in bounded_settings.items():
            value = _finite_number(production_print.get(key))
            if value is None or not minimum <= value <= maximum:
                errors.append(f"housing production {key} is invalid")
        if production_print.get("infill_pattern") not in {
            "gyroid",
            "grid",
            "cubic",
            "rectilinear",
        }:
            errors.append("housing production infill pattern is not controlled")
        if production_print.get("slicer_profile_sha256") != documents.get(
            "slicer_profile", {}
        ).get("sha256"):
            errors.append("housing production slicer profile is not document-bound")
        profile_record = documents.get("slicer_profile", {})
        profile: object = None
        if isinstance(profile_record, dict) and isinstance(profile_record.get("path"), str):
            try:
                profile = json.loads(
                    (ROOT / str(profile_record["path"])).read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError) as error:
                errors.append(f"housing slicer profile cannot be parsed: {error}")
        expected_profile = {
            "schema": "kc2-x3-v2-slicer-profile-v1",
            **{
                key: value
                for key, value in production_print.items()
                if key != "slicer_profile_sha256"
            },
        }
        if profile != expected_profile:
            errors.append("housing slicer profile is incompatible with the production process")

    specimen_id = production_print.get("specimen_coupon_id")
    production_lot_id = production_print.get("production_lot_id")
    trace_record = documents.get("structural_specimen_trace", {})
    trace_payload: object = None
    if isinstance(trace_record, dict) and isinstance(trace_record.get("path"), str):
        try:
            trace_payload = json.loads(
                (ROOT / str(trace_record["path"])).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"housing structural specimen trace cannot be parsed: {error}")
    expected_trace = {
        "schema": "kc2-x3-v2-structural-specimen-trace-v1",
        "production_lot_id": production_lot_id,
        "specimen_coupon_id": specimen_id,
        "slicer_profile_sha256": production_print.get("slicer_profile_sha256"),
    }
    if trace_payload != expected_trace:
        errors.append("housing structural specimen trace is not production-profile bound")
    calibration_payload: object = None
    if isinstance(calibration_evidence, dict) and isinstance(
        calibration_evidence.get("path"), str
    ):
        try:
            calibration_payload = json.loads(
                (ROOT / str(calibration_evidence["path"])).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"housing structural calibration trace cannot be parsed: {error}")
    expected_calibration = {
        "schema": "kc2-x3-v2-structural-calibration-v1",
        "bundle": "housing_fastener_deflection",
        "production_lot_id": production_lot_id,
        "specimen_coupon_id": specimen_id,
    }
    if calibration_payload != expected_calibration:
        errors.append("housing calibration is not bound to the tested structural specimen")

    assembly_identity = data.get("assembly_identity")
    required_assembly_identity = {
        "supported_modes",
        "choc_switch_manufacturer",
        "choc_switch_mpn",
        "mx_switch_manufacturer",
        "mx_switch_mpn",
        "keycap_identities",
    }
    if not isinstance(assembly_identity, dict) or set(assembly_identity) != required_assembly_identity:
        errors.append("housing supported switch/keycap identity schema is incomplete or stale")
        assembly_identity = {}
    else:
        if assembly_identity.get("supported_modes") != ["choc_v2", "mx"]:
            errors.append("housing supported assembly modes are not exact Choc V2 and MX")
        for key in required_assembly_identity - {"supported_modes", "keycap_identities"}:
            if not isinstance(assembly_identity.get(key), str) or not assembly_identity.get(key):
                errors.append(f"housing assembly identity {key} is missing")
            elif not _valid_identity_for_field(key, assembly_identity.get(key)):
                errors.append(
                    f"housing assembly identity {key} is malformed or retains a placeholder"
                )
        purchased_parts = controller_identity.get("purchased_parts")
        for prefix, part_name in (("choc", "choc_switch"), ("mx", "mx_switch")):
            expected_part = (
                purchased_parts.get(part_name)
                if isinstance(purchased_parts, dict)
                else None
            )
            if not isinstance(expected_part, dict) or any(
                assembly_identity.get(f"{prefix}_switch_{field}")
                != expected_part.get(field)
                for field in ("manufacturer", "mpn")
            ):
                errors.append(
                    f"housing {prefix} switch identity is not bound to controller service evidence"
                )
        if assembly_identity.get("keycap_identities") != scan_identity.get("keycaps"):
            errors.append("housing keycap identities are not bound to physical scan evidence")
        keycap_identities = assembly_identity.get("keycap_identities")
        if not isinstance(keycap_identities, dict):
            errors.append("housing exact keycap identity set is missing")
        else:
            for condition, keycap_identity in keycap_identities.items():
                if not isinstance(keycap_identity, dict):
                    errors.append(f"housing keycap identity {condition} is malformed")
                    continue
                for field in ("assembly_mode", "manufacturer", "mpn"):
                    value = keycap_identity.get(field)
                    if (
                        not isinstance(value, str)
                        or not value
                        or not _valid_identity_for_field(field, value)
                    ):
                        errors.append(
                            f"housing keycap identity {condition} {field} is missing/placeholder"
                        )

    fasteners, fastener_errors = _records_by_half(
        data.get("fastener_records"), label="housing fastener"
    )
    errors.extend(fastener_errors)
    cycles: list[int] = []
    ratios: list[float] = []
    rocking = loosening = permanent = disengagement = False
    for half, record in fasteners.items():
        required = {
            "half",
            "production_lot_id",
            "specimen_coupon_id",
            "install_remove_cycles",
            "actual_under_head_length_mm",
            "printed_pilot_diameter_mm",
            "actual_pcb_thickness_mm",
            "installed_penetration_mm",
            "measured_blind_pilot_depth_mm",
            "measured_closed_bottom_thickness_mm",
            "measured_available_plastic_depth_mm",
            "tip_clearance_mm",
            "tapping_torque_n_m",
            "selected_installation_torque_n_m",
            "stripping_torque_n_m",
            "measured_driver_shaft_diameter_mm",
            "measured_driver_runout_mm",
            "measured_driver_sweep_mm",
            "pull_through_clamp_retention_pass",
            "full_pattern_without_forcing",
            "keycaps_off_switches_installed_access",
            "cracking",
            "spin",
            "pull_out",
            "loosening",
        }
        if set(record) != required:
            errors.append(f"housing fastener {half} record schema is incomplete or stale")
            continue
        cycle_value = _finite_number(record.get("install_remove_cycles"))
        actual_length = _finite_number(record.get("actual_under_head_length_mm"))
        pilot = _finite_number(record.get("printed_pilot_diameter_mm"))
        pcb_thickness = _finite_number(record.get("actual_pcb_thickness_mm"))
        penetration = _finite_number(record.get("installed_penetration_mm"))
        pilot_depth = _finite_number(record.get("measured_blind_pilot_depth_mm"))
        closed_bottom = _finite_number(record.get("measured_closed_bottom_thickness_mm"))
        available_depth = _finite_number(record.get("measured_available_plastic_depth_mm"))
        tip_clearance = _finite_number(record.get("tip_clearance_mm"))
        tapping = _finite_number(record.get("tapping_torque_n_m"))
        install = _finite_number(record.get("selected_installation_torque_n_m"))
        stripping = _finite_number(record.get("stripping_torque_n_m"))
        measured_shaft = _finite_number(record.get("measured_driver_shaft_diameter_mm"))
        measured_runout = _finite_number(record.get("measured_driver_runout_mm"))
        measured_sweep = _finite_number(record.get("measured_driver_sweep_mm"))
        minimum_length = _finite_number(identity.get("minimum_under_head_length_mm"))
        maximum_length = _finite_number(identity.get("maximum_under_head_length_mm"))
        if (
            cycle_value is None
            or record.get("production_lot_id") != production_lot_id
            or record.get("specimen_coupon_id") != specimen_id
            or not cycle_value.is_integer()
            or cycle_value < 10
            or actual_length is None
            or minimum_length is None
            or maximum_length is None
            or not minimum_length <= actual_length <= maximum_length
            or pilot is None
            or pilot <= 0.0
            or not source_contracts
            or not math.isclose(
                pilot,
                source_contracts.get("pilot_diameter_mm", -1.0),
                abs_tol=1e-6,
            )
            or pcb_thickness is None
            or pcb_thickness <= 0.0
            or not source_contracts.get("minimum_pcb_thickness_mm", 99.0)
            <= pcb_thickness
            <= source_contracts.get("maximum_pcb_thickness_mm", -1.0)
            or penetration is None
            or penetration <= 0.0
            or not math.isclose(actual_length - pcb_thickness, penetration, abs_tol=1e-6)
            or pilot_depth is None
            or pilot_depth <= 0.0
            or not math.isclose(
                pilot_depth,
                source_contracts.get("pilot_depth_mm", -1.0),
                abs_tol=1e-6,
            )
            or closed_bottom is None
            or closed_bottom <= 0.0
            or not math.isclose(
                closed_bottom,
                source_contracts.get("closed_bottom_mm", -1.0),
                abs_tol=1e-6,
            )
            or available_depth is None
            or not math.isclose(available_depth, pilot_depth + closed_bottom, abs_tol=1e-6)
            or tip_clearance is None
            or not math.isclose(tip_clearance, pilot_depth - penetration, abs_tol=1e-6)
            or tip_clearance
            < source_contracts.get("minimum_tip_clearance_mm", float("inf"))
            or penetration
            < source_contracts.get("minimum_penetration_mm", float("inf"))
            or penetration
            > source_contracts.get("maximum_penetration_mm", float("-inf"))
            or tapping is None
            or tapping <= 0.0
            or install is None
            or install <= 0.0
            or stripping is None
            or stripping / tapping < 2.0
            or not tapping <= install <= stripping / 2.0
            or measured_shaft is None
            or measured_shaft <= 0.0
            or measured_shaft
            > float(identity.get("maximum_driver_shaft_diameter_mm", 0.0)) + 1e-9
            or measured_runout is None
            or measured_runout < 0.0
            or measured_runout
            > float(identity.get("maximum_driver_runout_mm", -1.0)) + 1e-9
            or measured_sweep is None
            or not math.isclose(
                measured_sweep,
                measured_shaft + 2.0 * measured_runout,
                abs_tol=1e-6,
            )
            or measured_sweep
            > float(identity.get("maximum_driver_sweep_mm", 0.0)) + 1e-9
        ):
            errors.append(
                f"housing fastener {half} dimensional/cycle/torque/skirt record does not pass"
            )
        else:
            cycles.append(int(cycle_value))
            ratios.append(stripping / tapping)
        if not all(
            record.get(key) is True
            for key in (
                "pull_through_clamp_retention_pass",
                "full_pattern_without_forcing",
                "keycaps_off_switches_installed_access",
            )
        ) or not all(record.get(key) is False for key in ("cracking", "spin", "pull_out", "loosening")):
            errors.append(f"housing fastener {half} service result does not pass")
        loosening = loosening or record.get("loosening") is not False

    assembly_fit_records = data.get("assembly_fit_records")
    expected_fit_keys = {
        (half, mode, width)
        for half in ("left", "right")
        for mode in ("choc_v2", "mx")
        for width in (1.0, 1.25, 1.5, 1.75)
    }
    seen_fit_keys: set[tuple[str, str, float]] = set()
    if not isinstance(assembly_fit_records, list):
        errors.append("housing switch/keycap assembly fit records are missing")
        assembly_fit_records = []
    for record in assembly_fit_records:
        if not isinstance(record, dict) or set(record) != {
            "half",
            "production_lot_id",
            "specimen_coupon_id",
            "assembly_mode",
            "width_u",
            "switch_manufacturer",
            "switch_mpn",
            "keycap_manufacturer",
            "keycap_mpn",
            "is_3d_printed",
            "keycap_skirt_clearance_at_rest_mm",
            "keycap_skirt_clearance_at_full_travel_mm",
        }:
            errors.append("housing assembly fit contains an incomplete record")
            continue
        width = _finite_number(record.get("width_u"))
        key = (
            str(record.get("half")),
            str(record.get("assembly_mode")),
            float(width) if width is not None else -1.0,
        )
        if key not in expected_fit_keys or key in seen_fit_keys:
            errors.append(f"housing assembly fit condition is unexpected or duplicated: {key}")
            continue
        seen_fit_keys.add(key)
        prefix = "choc" if key[1] == "choc_v2" else "mx"
        keycap = scan_identity.get("keycaps", {})
        expected_keycap = (
            keycap.get(f"{key[1]}:{key[2]:.2f}") if isinstance(keycap, dict) else None
        )
        rest = _finite_number(record.get("keycap_skirt_clearance_at_rest_mm"))
        travel = _finite_number(record.get("keycap_skirt_clearance_at_full_travel_mm"))
        if (
            record.get("production_lot_id") != production_lot_id
            or record.get("specimen_coupon_id") != specimen_id
            or record.get("switch_manufacturer")
            != assembly_identity.get(f"{prefix}_switch_manufacturer")
            or record.get("switch_mpn") != assembly_identity.get(f"{prefix}_switch_mpn")
            or not isinstance(expected_keycap, dict)
            or record.get("keycap_manufacturer") != expected_keycap.get("manufacturer")
            or record.get("keycap_mpn") != expected_keycap.get("mpn")
            or record.get("is_3d_printed") is not expected_keycap.get("is_3d_printed")
            or rest is None
            or rest <= 0.0
            or travel is None
            or travel <= 0.0
        ):
            errors.append(f"housing assembly fit {key} identity/clearance does not pass")
    if seen_fit_keys != expected_fit_keys:
        errors.append(
            "housing assembly fit does not cover both halves, modes, and all non-1U keycaps"
        )

    head_fit_records = data.get("head_adjacent_fit_records")
    expected_head_fit_keys = {
        (contract_key, mode)
        for contract_key in head_adjacency_contracts
        for mode in ("choc_v2", "mx")
    }
    seen_head_fit_keys: set[tuple[str, str]] = set()
    if not isinstance(head_fit_records, list):
        errors.append("housing mounting-head-adjacent fit records are missing")
        head_fit_records = []
    for record in head_fit_records:
        required = {
            "half",
            "production_lot_id",
            "specimen_coupon_id",
            "mounting_hole_reference",
            "assembly_mode",
            "overlapping_switch_reference",
            "width_u",
            "keycap_manufacturer",
            "keycap_mpn",
            "is_3d_printed",
            "keycap_head_clearance_at_rest_mm",
            "keycap_head_clearance_at_full_travel_mm",
        }
        if not isinstance(record, dict) or set(record) != required:
            errors.append("housing mounting-head-adjacent fit contains an incomplete record")
            continue
        contract_key = (
            f"{record.get('half')}:{record.get('mounting_hole_reference')}:"
            f"{record.get('overlapping_switch_reference')}"
        )
        mode = str(record.get("assembly_mode"))
        key = (contract_key, mode)
        if key not in expected_head_fit_keys or key in seen_head_fit_keys:
            errors.append(
                f"housing mounting-head-adjacent fit is unexpected or duplicated: {key}"
            )
            continue
        seen_head_fit_keys.add(key)
        contract = head_adjacency_contracts[contract_key]
        width = _finite_number(record.get("width_u"))
        expected_keycap = scan_identity.get("keycaps", {})
        expected_keycap = (
            expected_keycap.get(f"{mode}:{float(width):.2f}")
            if isinstance(expected_keycap, dict) and width is not None
            else None
        )
        rest = _finite_number(record.get("keycap_head_clearance_at_rest_mm"))
        travel = _finite_number(record.get("keycap_head_clearance_at_full_travel_mm"))
        if (
            record.get("production_lot_id") != production_lot_id
            or record.get("specimen_coupon_id") != specimen_id
            or record.get("half") != contract.get("half")
            or record.get("mounting_hole_reference")
            != contract.get("mounting_hole_reference")
            or record.get("overlapping_switch_reference")
            != contract.get("overlapping_switch_reference")
            or width is None
            or not math.isclose(width, float(contract.get("width_u", -1.0)), abs_tol=1e-9)
            or not isinstance(expected_keycap, dict)
            or record.get("keycap_manufacturer") != expected_keycap.get("manufacturer")
            or record.get("keycap_mpn") != expected_keycap.get("mpn")
            or record.get("is_3d_printed") is not expected_keycap.get("is_3d_printed")
            or rest is None
            or rest <= 0.0
            or travel is None
            or travel <= 0.0
        ):
            errors.append(f"housing mounting-head-adjacent fit {key} does not pass")
    if seen_head_fit_keys != expected_head_fit_keys or len(seen_head_fit_keys) != 32:
        errors.append(
            "housing mounting-head-adjacent fit does not cover both modes for all 16 P2 reinforcement overlaps"
        )

    deflections = data.get("deflection_records")
    expected_counts = {"left": 31, "right": 39}
    seen_switches: set[tuple[str, str]] = set()
    displacements: list[float] = []
    if not isinstance(deflections, list):
        errors.append("housing deflection records are missing")
        deflections = []
    for record in deflections:
        if not isinstance(record, dict) or set(record) != {
            "half",
            "production_lot_id",
            "specimen_coupon_id",
            "switch_reference",
            "load_n",
            "downward_displacement_mm",
            "rocking",
            "permanent_deformation",
            "support_disengagement",
        }:
            errors.append("housing deflection contains an incomplete record")
            continue
        half = record.get("half")
        reference = record.get("switch_reference")
        key = (str(half), str(reference))
        if half not in expected_counts or not isinstance(reference, str) or not re.fullmatch(r"SW\d+", reference):
            errors.append("housing deflection half/reference is invalid")
            continue
        if key in seen_switches:
            errors.append("housing deflection switch record is duplicated")
            continue
        seen_switches.add(key)
        load = _finite_number(record.get("load_n"))
        displacement = _finite_number(record.get("downward_displacement_mm"))
        if (
            record.get("production_lot_id") != production_lot_id
            or record.get("specimen_coupon_id") != specimen_id
            or load is None
            or not math.isclose(load, 2.0, abs_tol=1e-9)
            or displacement is None
            or displacement < 0.0
        ):
            errors.append(f"housing deflection {half} {reference} measurement is invalid")
        else:
            displacements.append(displacement)
        rocking = rocking or record.get("rocking") is not False
        permanent = permanent or record.get("permanent_deformation") is not False
        disengagement = disengagement or record.get("support_disengagement") is not False
    expected_switches = {
        (half, f"SW{index}")
        for half, count in expected_counts.items()
        for index in range(1, count + 1)
    }
    if seen_switches != expected_switches:
        errors.append("housing deflection does not contain the exact 31 left and 39 right switch references")
    metrics = {
        "fastener_manufacturer": identity.get("manufacturer"),
        "fastener_mpn": identity.get("mpn"),
        "fastener_order_code": identity.get("order_code"),
        "fastener_drawing_revision": identity.get("drawing_revision"),
        "fastener_drawing_sha256": documents.get("fastener_drawing", {}).get("sha256"),
        "head_style": identity.get("head_style"),
        "nominal_thread_diameter_mm": identity.get("nominal_thread_diameter_mm"),
        "thread_classification": identity.get("thread_classification"),
        "thread_form": identity.get("thread_form"),
        "thread_pitch_mm": identity.get("thread_pitch_mm"),
        "thread_flank_angle_degrees": identity.get("thread_flank_angle_degrees"),
        "thread_major_diameter_mm": identity.get("thread_major_diameter_mm"),
        "thread_minor_diameter_mm": identity.get("thread_minor_diameter_mm"),
        "material": identity.get("material"),
        "finish": identity.get("finish"),
        "drive_recess": identity.get("drive_recess"),
        "minimum_head_diameter_mm": identity.get("minimum_head_diameter_mm"),
        "maximum_head_diameter_mm": identity.get("maximum_head_diameter_mm"),
        "minimum_head_height_mm": identity.get("minimum_head_height_mm"),
        "maximum_head_height_mm": identity.get("maximum_head_height_mm"),
        "minimum_under_head_length_mm": identity.get("minimum_under_head_length_mm"),
        "maximum_under_head_length_mm": identity.get("maximum_under_head_length_mm"),
        "maximum_finished_pcb_hole_diameter_mm": identity.get(
            "maximum_finished_pcb_hole_diameter_mm"
        ),
        "minimum_radial_bearing_width_mm": identity.get("minimum_radial_bearing_width_mm"),
        "driver_manufacturer": identity.get("driver_manufacturer"),
        "driver_mpn": identity.get("driver_mpn"),
        "driver_drawing_sha256": documents.get("driver_drawing", {}).get("sha256"),
        "maximum_driver_shaft_diameter_mm": identity.get("maximum_driver_shaft_diameter_mm"),
        "maximum_driver_runout_mm": identity.get("maximum_driver_runout_mm"),
        "maximum_driver_sweep_mm": identity.get("maximum_driver_sweep_mm"),
        "production_print": production_print,
        "assembly_identity": assembly_identity,
        "assembly_fit_condition_count": len(seen_fit_keys),
        "head_adjacent_fit_condition_count": len(seen_head_fit_keys),
        "install_remove_cycles": min(cycles) if cycles else 0,
        "torque_ratio": min(ratios) if ratios else 0.0,
        "tested_switch_positions": len(seen_switches),
        "maximum_displacement_mm": max(displacements) if displacements else None,
        "rocking": rocking,
        "loosening": loosening,
        "permanent_deformation": permanent,
        "support_disengagement": disengagement,
    }
    return metrics, errors


def _power_rf_metrics(
    data: object,
    *,
    source_digests: dict[str, str],
    controller_identity: dict[str, object],
) -> tuple[dict[str, object], list[str]]:
    errors: list[str] = []
    if not isinstance(data, dict) or set(data) != {"identity", "transition_records", "rf_records"}:
        return {}, ["power/RF raw data schema is incomplete or stale"]
    identity = data.get("identity")
    required_identity = {
        "battery_mpn",
        "battery_lot",
        "power_switch_mpn",
        "firmware_build_sha256",
        "housing_manifest_sha256",
        "host_id",
        "ble_channels",
    }
    if not isinstance(identity, dict) or set(identity) != required_identity:
        return {}, ["power/RF assembly, firmware, host, and channel identity is incomplete"]
    for key in ("battery_mpn", "battery_lot", "power_switch_mpn"):
        if identity.get(key) != controller_identity.get(key):
            errors.append(f"power/RF {key} does not match controller-service evidence")
    if identity.get("firmware_build_sha256") != source_digests.get("firmware_build_evidence"):
        errors.append("power/RF firmware build identity is not source-bound")
    if identity.get("housing_manifest_sha256") != source_digests.get("housing_manifest"):
        errors.append("power/RF housing identity is not source-bound")
    if not isinstance(identity.get("host_id"), str) or not identity.get("host_id"):
        errors.append("power/RF host identity is missing")
    channels = identity.get("ble_channels")
    if not isinstance(channels, list) or not channels or any(
        isinstance(channel, bool) or not isinstance(channel, int) for channel in channels
    ) or len(set(channels)) != len(channels):
        errors.append("power/RF BLE channel set is missing or invalid")
        channels = []

    transitions = data.get("transition_records")
    expected_transition_keys = {
        (half, voltage, direction, cycle)
        for half in ("left", "right")
        for voltage in (3.3, 4.2)
        for direction in ("off_to_on", "on_to_off")
        for cycle in range(1, 21)
    }
    seen_transition_keys: set[tuple[str, float, str, int]] = set()
    brownouts = boot_faults = 0
    vbat_droops: list[float] = []
    vdd_droops: list[float] = []
    ringing_values: list[float] = []
    if not isinstance(transitions, list):
        errors.append("power transition raw records are missing")
        transitions = []
    for record in transitions:
        if not isinstance(record, dict) or set(record) != {
            "half",
            "no_load_voltage_v",
            "direction",
            "cycle",
            "vbat_samples_v",
            "vdd_samples_v",
            "expected_vdd_v",
            "brownout_reset",
            "boot_loop",
            "usb_reenumeration_failure",
            "stuck_power_state",
            "visible_arcing",
        }:
            errors.append("power transition contains an incomplete record")
            continue
        voltage = _finite_number(record.get("no_load_voltage_v"))
        cycle = _finite_number(record.get("cycle"))
        key = (
            str(record.get("half")),
            voltage if voltage is not None else -1.0,
            str(record.get("direction")),
            int(cycle) if cycle is not None and cycle.is_integer() else -1,
        )
        if key not in expected_transition_keys or key in seen_transition_keys:
            errors.append(f"power transition condition is unexpected or duplicated: {key}")
            continue
        seen_transition_keys.add(key)
        vbat = record.get("vbat_samples_v")
        vdd = record.get("vdd_samples_v")
        expected_vdd = _finite_number(record.get("expected_vdd_v"))
        if not isinstance(vbat, list) or len(vbat) < 3 or not isinstance(vdd, list) or len(vdd) < 3:
            errors.append(f"power transition {key} lacks raw scope samples")
            continue
        vbat_values = [_finite_number(value) for value in vbat]
        vdd_values = [_finite_number(value) for value in vdd]
        if any(value is None for value in vbat_values + vdd_values) or expected_vdd is None:
            errors.append(f"power transition {key} has invalid raw scope samples")
            continue
        if key[2] == "off_to_on":
            vbat_numbers = [float(value) for value in vbat_values]
            vdd_numbers = [float(value) for value in vdd_values]
            vbat_droops.append(key[1] - min(vbat_numbers))
            vdd_droops.append(expected_vdd - min(vdd_numbers))
            ringing_values.append(max(vbat_numbers) - min(vbat_numbers))
        brownout = record.get("brownout_reset") is not False
        brownouts += int(brownout)
        other_fault = any(
            record.get(field) is not False
            for field in (
                "boot_loop",
                "usb_reenumeration_failure",
                "stuck_power_state",
                "visible_arcing",
            )
        )
        boot_faults += int(other_fault)
    if seen_transition_keys != expected_transition_keys:
        errors.append("power transition records do not cover 20 cycles for both halves, voltages, and directions")

    states = ("battery_only", "usb_charging", "charge_complete", "usb_unplug_transition")
    orientations = ("normal", "90_degrees", "180_degrees")
    hands = ("absent", "home_row")
    expected_rf_keys = {
        (half, channel, state, orientation, hand)
        for half in ("left", "right")
        for channel in channels
        for state in states
        for orientation in orientations
        for hand in hands
    }
    rf_records = data.get("rf_records")
    seen_rf_keys: set[tuple[str, int, str, str, str]] = set()
    rssi_counts: list[int] = []
    report_counts: list[int] = []
    loss_ratios: list[float] = []
    degradations: list[float] = []
    disconnects = reconnects = 0
    if not isinstance(rf_records, list):
        errors.append("RF raw records are missing")
        rf_records = []
    for record in rf_records:
        if not isinstance(record, dict) or set(record) != {
            "half",
            "ble_channel",
            "state",
            "orientation",
            "hands",
            "distance_m",
            "both_halves_communicating",
            "baseline_rssi_dbm",
            "final_rssi_dbm",
            "reports_expected",
            "missing_sequence_numbers",
            "disconnect_events",
            "reconnect_events",
        }:
            errors.append("RF evidence contains an incomplete record")
            continue
        key = (
            str(record.get("half")),
            record.get("ble_channel"),
            str(record.get("state")),
            str(record.get("orientation")),
            str(record.get("hands")),
        )
        if key not in expected_rf_keys or key in seen_rf_keys:
            errors.append(f"RF condition is unexpected or duplicated: {key}")
            continue
        seen_rf_keys.add(key)
        distance = _finite_number(record.get("distance_m"))
        baseline = record.get("baseline_rssi_dbm")
        final = record.get("final_rssi_dbm")
        expected_reports = _finite_number(record.get("reports_expected"))
        missing = record.get("missing_sequence_numbers")
        disconnect_events = record.get("disconnect_events")
        reconnect_events = record.get("reconnect_events")
        if (
            distance is None
            or not math.isclose(distance, 5.0, abs_tol=1e-9)
            or record.get("both_halves_communicating") is not True
            or not isinstance(baseline, list)
            or not isinstance(final, list)
            or len(baseline) < 30
            or len(final) < 30
            or expected_reports is None
            or not expected_reports.is_integer()
            or expected_reports < 10000
            or not isinstance(missing, list)
            or not isinstance(disconnect_events, list)
            or not isinstance(reconnect_events, list)
        ):
            errors.append(f"RF condition {key} lacks required raw samples or workload")
            continue
        baseline_values = [_finite_number(value) for value in baseline]
        final_values = [_finite_number(value) for value in final]
        if any(value is None for value in baseline_values + final_values):
            errors.append(f"RF condition {key} has invalid RSSI samples")
            continue
        expected_reports_int = int(expected_reports)
        if any(
            isinstance(sequence, bool)
            or not isinstance(sequence, int)
            or sequence < 1
            or sequence > expected_reports_int
            for sequence in missing
        ) or len(set(missing)) != len(missing):
            errors.append(f"RF condition {key} missing-sequence record is invalid")
            continue
        rssi_counts.append(min(len(baseline), len(final)))
        report_counts.append(expected_reports_int)
        loss_ratios.append(len(missing) / expected_reports_int)
        degradations.append(
            float(median(float(value) for value in baseline_values))
            - float(median(float(value) for value in final_values))
        )
        disconnects += len(disconnect_events)
        reconnects += len(reconnect_events)
    if seen_rf_keys != expected_rf_keys:
        errors.append("RF records do not cover every half/channel/state/orientation/hand condition")
    metrics = {
        "cold_cycles_per_voltage_and_direction": 20 if seen_transition_keys == expected_transition_keys else 0,
        "brownout_count": brownouts,
        "power_fault_count": boot_faults,
        "maximum_vbat_droop_v": max(vbat_droops) if vbat_droops else None,
        "maximum_vdd_droop_v": max(vdd_droops) if vdd_droops else None,
        "maximum_vbat_ringing_v": max(ringing_values) if ringing_values else None,
        "rssi_samples_per_state": min(rssi_counts) if rssi_counts else 0,
        "reports_per_state": min(report_counts) if report_counts else 0,
        "packet_loss_ratio": max(loss_ratios) if loss_ratios else None,
        "median_rssi_degradation_db": max(degradations) if degradations else None,
        "disconnect_count": disconnects,
        "reconnect_count": reconnects,
    }
    return metrics, errors


def _verify_positive_order_artifact_suite() -> list[str]:
    """Re-run every dedicated digital artifact verifier for a positive order claim."""
    errors: list[str] = []
    commands = {
        label: [sys.executable, "-B", "-m", module]
        for label, module in POSITIVE_ORDER_ARTIFACT_MODULES.items()
    }
    commands["firmware"].extend(["--kicad-python", sys.executable])
    outline_code = (
        "import json;"
        "from tools.verify_kc2_x3_v2_outline import ROOT,analyze_outline;"
        "p=ROOT/'hardware/kicad/draft/x3-v2/mechanical/kc2_x3_v2_outline_report.json';"
        "actual=analyze_outline(ROOT);"
        "bound=json.loads(p.read_text(encoding='utf-8'));"
        "errors=list(actual.get('errors',[]));"
        "errors.extend([] if bound==actual else ['bound outline report is stale']);"
        "raise SystemExit('\\n'.join(errors) if errors else 0)"
    )
    commands["outline"] = [sys.executable, "-B", "-c", outline_code]
    for label, command in commands.items():
        try:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            errors.append(f"artifact suite {label} verifier could not run: {error}")
            continue
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip().splitlines()
            errors.append(
                f"artifact suite {label} verifier failed"
                + (f": {detail[-1]}" if detail else "")
            )
    python_launcher = shutil.which("py")
    if python_launcher is None:
        errors.append("artifact suite housing verifier could not run: Windows py launcher is missing")
    else:
        housing_code = (
            "from tools.verify_kc2_x3_v2_housing import analyze_v2_housing,verify_report;"
            "errors=verify_report(analyze_v2_housing());"
            "raise SystemExit('\\n'.join(errors) if errors else 0)"
        )
        housing_environment = os.environ.copy()
        # KiCad sets a private PYTHONUSERBASE for its bundled Python.  Do not leak it
        # into the independent CadQuery interpreter used by the housing verifier.
        housing_environment.pop("PYTHONUSERBASE", None)
        try:
            completed = subprocess.run(
                [python_launcher, "-3.12", "-B", "-c", housing_code],
                cwd=ROOT,
                env=housing_environment,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            errors.append(f"artifact suite housing verifier could not run: {error}")
        else:
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout).strip().splitlines()
                errors.append(
                    "artifact suite housing verifier failed"
                    + (f": {detail[-1]}" if detail else "")
                )
    return errors


def _positive_package_identity_errors(
    fabrication_manifest_path: Path | None,
    *,
    controller_identity: dict[str, object],
    scan_identity: dict[str, object],
    source_digests: dict[str, str],
    seen_paths: set[str],
) -> list[str]:
    if fabrication_manifest_path is None:
        return ["positive fabrication package manifest is missing"]
    try:
        manifest = json.loads(fabrication_manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"positive fabrication package manifest cannot be parsed: {error}"]
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["positive fabrication package manifest is not an object"]
    if (
        manifest.get("status") != "order_ready_verified_physical_evidence"
        or manifest.get("order_ready") is not True
    ):
        errors.append("positive fabrication package remains draft/not order-ready")
    errors.extend(
        _procurement_object_identity_errors(
            manifest,
            label="positive fabrication package",
        )
    )
    purchased_parts = controller_identity.get("purchased_parts")
    keycaps = scan_identity.get("keycaps")
    expected_procurement_identity = {
        "parts": purchased_parts,
        "keycaps": keycaps,
    }
    if not isinstance(purchased_parts, dict) or not isinstance(keycaps, dict):
        errors.append("positive package lacks recomputed physical purchased-part identities")
    products = manifest.get("products")
    if not isinstance(products, dict):
        return errors + ["positive fabrication package products are missing"]
    for half, board_binding in (("left", "left_board"), ("right", "right_board")):
        product = products.get(half)
        if not isinstance(product, dict):
            errors.append(f"positive fabrication package {half} product is missing")
            continue
        if product.get("source_board_sha256") != source_digests.get(board_binding):
            errors.append(f"positive fabrication package {half} board digest is stale")
        bom = product.get("bom")
        files = product.get("files")
        if not isinstance(bom, dict) or not isinstance(bom.get("json"), str):
            errors.append(f"positive fabrication package {half} BOM path is missing")
            continue
        relative = Path(str(bom["json"]).replace("\\", "/"))
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"positive fabrication package {half} BOM path is unsafe")
            continue
        bom_path = ROOT / relative
        file_entry = None
        if isinstance(files, list):
            file_entry = next(
                (
                    item
                    for item in files
                    if isinstance(item, dict) and item.get("name") == relative.name
                ),
                None,
            )
        if not isinstance(file_entry, dict):
            errors.append(f"positive fabrication package {half} BOM file record is missing")
            continue
        errors.extend(
            _repository_artifact_errors(
                {
                    "path": relative.as_posix(),
                    "sha256": file_entry.get("sha256"),
                    "size_bytes": file_entry.get("size"),
                    "kind": "fabrication-bom-json",
                },
                label=f"positive fabrication package {half} BOM",
                measurement=False,
                seen_paths=seen_paths,
            )
        )
        try:
            bom_payload = json.loads(bom_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"positive fabrication package {half} BOM cannot be parsed: {error}")
            continue
        if not isinstance(bom_payload, dict):
            errors.append(f"positive fabrication package {half} BOM is not an object")
            continue
        if (
            bom_payload.get("order_ready") is not True
            or bom_payload.get("source_board_sha256") != source_digests.get(board_binding)
        ):
            errors.append(f"positive fabrication package {half} BOM is stale/not order-ready")
        if bom_payload.get("procurement_identity") != expected_procurement_identity:
            errors.append(
                f"positive fabrication package {half} BOM identities are not exact physical evidence"
            )
        errors.extend(
            _procurement_object_identity_errors(
                bom_payload,
                label=f"positive fabrication package {half} BOM",
            )
        )
    return errors


def verify_physical_evidence_manifest(
    evidence: object,
    expected_source_paths: dict[str, Path] | None = None,
) -> dict[str, list[str]]:
    bundle_errors = {name: [] for name in PHYSICAL_EVIDENCE_BUNDLES}
    if not isinstance(evidence, dict):
        for errors in bundle_errors.values():
            errors.append("physical evidence manifest is missing or invalid")
        return bundle_errors

    root_errors: list[str] = []
    if evidence.get("schema") != PHYSICAL_EVIDENCE_SCHEMA:
        root_errors.append("schema is missing or stale")
    if evidence.get("requirement_ids") != PHYSICAL_EVIDENCE_REQUIREMENT_IDS:
        root_errors.append("requirement IDs are missing or stale")
    if evidence.get("variant") != "x3-v2":
        root_errors.append("variant is missing or stale")
    if evidence.get("status") != "passed" or evidence.get("order_ready") is not True:
        root_errors.append("physical evidence status/order_ready is not passed/true")

    required_bindings = {
        "left_board",
        "right_board",
        "generation_manifest",
        "housing_manifest",
        "fabrication_manifest",
        "mechanical_manifest",
        "render_manifest",
        "outline_report",
        "firmware_build_evidence",
    }
    bindings = evidence.get("source_bindings")
    source_digests: dict[str, str] = {}
    bound_source_paths: dict[str, Path] = {}
    if not isinstance(bindings, dict) or set(bindings) != required_bindings:
        root_errors.append("source bindings are incomplete")
    else:
        for name in sorted(required_bindings):
            root_errors.extend(
                _repository_artifact_errors(
                    bindings[name],
                    label=f"source binding {name}",
                    measurement=False,
                )
            )
            if isinstance(bindings[name], dict) and isinstance(bindings[name].get("sha256"), str):
                source_digests[name] = str(bindings[name]["sha256"])
            if isinstance(bindings[name], dict) and isinstance(bindings[name].get("path"), str):
                bound_source_paths[name] = ROOT / str(bindings[name]["path"])
            if expected_source_paths is not None:
                expected_path = expected_source_paths.get(name)
                expected_relative = (
                    expected_path.resolve().relative_to(ROOT.resolve()).as_posix()
                    if expected_path is not None
                    else None
                )
                if bindings[name].get("path") != expected_relative:
                    root_errors.append(f"source binding {name} path is not canonical")
    if (
        evidence.get("status") == "passed"
        and evidence.get("order_ready") is True
        and not root_errors
    ):
        root_errors.extend(_verify_positive_order_artifact_suite())

    bundles = evidence.get("bundles")
    if not isinstance(bundles, dict) or set(bundles) != set(PHYSICAL_EVIDENCE_BUNDLES):
        root_errors.append("physical evidence bundle set is incomplete or stale")
        bundles = {}
    seen_paths: set[str] = set()
    controller_identity: dict[str, object] = {}
    scan_identity: dict[str, object] = {}
    housing_contracts, housing_contract_errors = _housing_source_contracts(
        bound_source_paths
    )
    head_adjacency_contracts, head_adjacency_contract_errors = (
        _housing_head_adjacency_contracts(bound_source_paths)
    )
    for name in bundle_errors:
        errors = bundle_errors[name]
        errors.extend(root_errors)
        bundle = bundles.get(name)
        if not isinstance(bundle, dict):
            errors.append(f"{name} bundle is missing")
            continue
        if bundle.get("status") != "passed":
            errors.append(f"{name} status is not passed")
        artifacts = bundle.get("artifacts")
        if not isinstance(artifacts, list) or len(artifacts) != 1:
            errors.append(f"{name} must contain exactly one typed raw JSON artifact")
            continue
        artifact = artifacts[0]
        errors.extend(
            _repository_artifact_errors(
                artifact,
                label=f"{name} artifact",
                measurement=True,
                seen_paths=seen_paths,
            )
        )
        if not isinstance(artifact, dict):
            continue
        if artifact.get("kind") != PHYSICAL_RAW_ARTIFACT_KINDS[name]:
            errors.append(f"{name} typed raw artifact kind is missing or stale")
        relative_path = artifact.get("path")
        payload: object = None
        if isinstance(relative_path, str):
            try:
                payload = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                errors.append(f"{name} typed raw JSON cannot be parsed: {error}")
        if not isinstance(payload, dict) or set(payload) != {
            "schema",
            "bundle",
            "source_bindings",
            "data",
        }:
            errors.append(f"{name} typed raw JSON schema is incomplete or stale")
            continue
        if payload.get("schema") != PHYSICAL_RAW_BUNDLE_SCHEMA or payload.get("bundle") != name:
            errors.append(f"{name} typed raw JSON identity is missing or stale")
        if payload.get("source_bindings") != source_digests:
            errors.append(f"{name} typed raw JSON is not bound to the exact release sources")
        metrics = bundle.get("metrics")
        if not isinstance(metrics, dict):
            errors.append(f"{name} metrics are missing")
            continue
        if name == "controller_service":
            recomputed, raw_errors, controller_identity = _controller_service_metrics(
                payload.get("data"),
                seen_paths=seen_paths,
            )
            errors.extend(raw_errors)
        elif name == "physical_scan":
            recomputed, raw_errors, scan_identity = _physical_scan_metrics(
                payload.get("data"),
                controller_identity=controller_identity,
            )
            errors.extend(raw_errors)
        elif name == "housing_fastener_deflection":
            recomputed, raw_errors = _housing_metrics(
                payload.get("data"),
                seen_paths=seen_paths,
                controller_identity=controller_identity,
                scan_identity=scan_identity,
                source_contracts=housing_contracts,
                head_adjacency_contracts=head_adjacency_contracts,
                calibration_evidence=artifact.get("calibration_evidence"),
            )
            errors.extend(
                housing_contract_errors + head_adjacency_contract_errors + raw_errors
            )
        elif name == "power_rf":
            recomputed, raw_errors = _power_rf_metrics(
                payload.get("data"),
                source_digests=source_digests,
                controller_identity=controller_identity,
            )
            errors.extend(raw_errors)
        else:  # pragma: no cover - bundle set is a constant
            recomputed = {}
        if metrics != recomputed:
            errors.append(f"{name} metrics are not an exact recomputation of typed raw records")
        if name == "controller_service" and (
            recomputed.get("lead_pull_pass") is not True
            or recomputed.get("service_pass") is not True
            or _finite_number(recomputed.get("minimum_stack_clearance_mm")) is None
        ):
            errors.append("controller service raw results do not pass")
        elif name == "physical_scan" and (
            recomputed.get("sample_count_per_condition", 0) < 1
            or recomputed.get("fault_count") != 0
        ):
            errors.append("physical scan raw results do not pass")
        elif name == "housing_fastener_deflection" and (
            _finite_number(recomputed.get("torque_ratio")) is None
            or float(recomputed.get("torque_ratio", 0.0)) < 2.0
            or _finite_number(recomputed.get("maximum_displacement_mm")) is None
            or float(recomputed.get("maximum_displacement_mm", 99.0)) > 0.30
            or any(
                recomputed.get(key) is not False
                for key in ("rocking", "loosening", "permanent_deformation", "support_disengagement")
            )
        ):
            errors.append("housing fastener/deflection raw results do not pass")
        elif name == "power_rf" and (
            recomputed.get("cold_cycles_per_voltage_and_direction") != 20
            or recomputed.get("brownout_count") != 0
            or recomputed.get("power_fault_count") != 0
            or recomputed.get("rssi_samples_per_state", 0) < 30
            or recomputed.get("reports_per_state", 0) < 10000
            or _finite_number(recomputed.get("packet_loss_ratio")) is None
            or float(recomputed.get("packet_loss_ratio", 99.0)) > 0.01
            or _finite_number(recomputed.get("median_rssi_degradation_db")) is None
            or float(recomputed.get("median_rssi_degradation_db", 99.0)) > 3.0
            or recomputed.get("disconnect_count") != 0
            or recomputed.get("reconnect_count") != 0
        ):
            errors.append("power/RF raw results do not pass")
    if evidence.get("status") == "passed" and evidence.get("order_ready") is True:
        package_errors = _positive_package_identity_errors(
            bound_source_paths.get("fabrication_manifest"),
            controller_identity=controller_identity,
            scan_identity=scan_identity,
            source_digests=source_digests,
            seen_paths=seen_paths,
        )
        for errors in bundle_errors.values():
            errors.extend(package_errors)
    return bundle_errors


def controller_service_order_readiness_blockers(
    manifest: dict[str, object],
    housing_manifest: dict[str, object] | None = None,
    physical_evidence: dict[str, object] | None = None,
    expected_source_paths: dict[str, Path] | None = None,
) -> list[str]:
    service = manifest.get("controller_service_region")
    if not isinstance(service, dict):
        return ["CON-ARCH-007 controller service manifest is missing"]
    blockers: list[str] = []
    # Generated design manifests remain conservative and are not an authority for
    # irreversible order readiness.  Only the repository-bound physical evidence
    # manifest below can establish a positive release result.
    if service.get("order_ready") is not False:
        blockers.append(
            "CON-ARCH-007: generated controller service order_ready must remain false"
        )
    physical_scan = manifest.get("physical_scan_validation")
    if not isinstance(physical_scan, dict) or physical_scan.get("orderable") is not False:
        blockers.append(
            "CON-ARCH-004: generated physical scan orderable must remain false"
        )

    if not isinstance(housing_manifest, dict):
        blockers.append("CON-ARCH-006: housing manifest is missing or invalid")
    else:
        required_housing_keys = {
            "requirement",
            "requirement_ids",
            "variant",
            "generated_by",
            "hash_policy",
            "generator_sha256",
            "coordinate_system",
            "order_ready",
            "parameters",
            "retention",
            "physical_deflection_test",
            "outputs",
        }
        if set(housing_manifest) != required_housing_keys:
            blockers.append("CON-ARCH-006: housing manifest schema is incomplete or stale")
        if housing_manifest.get("requirement") != "CON-ARCH-006" or housing_manifest.get(
            "requirement_ids"
        ) != ["CON-ARCH-006", "CON-ARCH-007", "REL-ARCH-001"]:
            blockers.append("CON-ARCH-006: housing manifest requirement IDs are stale")
        if housing_manifest.get("variant") != "x3-v2" or housing_manifest.get(
            "hash_policy"
        ) != HASH_POLICY:
            blockers.append("CON-ARCH-006: housing manifest identity/hash policy is stale")
        if housing_manifest.get("order_ready") is not False:
            blockers.append("CON-ARCH-006: generated housing order_ready must remain false")
        retention = housing_manifest.get("retention")
        if not isinstance(retention, dict) or retention.get("physical_registration_status") != (
            "pending"
        ):
            blockers.append("CON-ARCH-006: generated housing registration must remain pending")
        deflection = housing_manifest.get("physical_deflection_test")
        if not isinstance(deflection, dict) or deflection.get("status") != "pending":
            blockers.append("CON-ARCH-006: generated housing deflection must remain pending")
    evidence_errors = verify_physical_evidence_manifest(
        physical_evidence,
        expected_source_paths,
    )
    for bundle_name, label in PHYSICAL_EVIDENCE_BUNDLES.items():
        if evidence_errors[bundle_name]:
            blockers.append(f"{label} is missing or invalid: {evidence_errors[bundle_name][0]}")
    return blockers


def verify_controller_service_model_binding(
    manifest: dict[str, object],
) -> list[str]:
    service = manifest.get("controller_service_region")
    power = service.get("power") if isinstance(service, dict) else None
    battery_termination = (
        service.get("battery_termination") if isinstance(service, dict) else None
    )
    if not isinstance(power, dict):
        return ["manifest: controller POWER model contract is missing"]
    expected_model = "third_party/kc2.3dshapes/SW_IMMS_12V_BSI10_THT.step"
    expected_generator = "tools/generate_kc2_component_models.py"
    errors: list[str] = []
    if power.get("model") != expected_model:
        errors.append("manifest: IMMS STEP model path is missing or stale")
    if power.get("model_generator") != expected_generator:
        errors.append("manifest: IMMS model generator path is missing or stale")
    model_path = ROOT / expected_model
    generator_path = ROOT / expected_generator
    if not model_path.is_file() or power.get("model_sha256") != sha256_file(model_path):
        errors.append("manifest: IMMS STEP model SHA-256 is missing or stale")
    if not generator_path.is_file() or power.get("model_generator_sha256") != sha256_file(
        generator_path
    ):
        errors.append("manifest: IMMS model generator SHA-256 is missing or stale")
    if power.get("body_size_mm") != [10.0, 2.5, 6.4]:
        errors.append("manifest: IMMS 10x2.5x6.4 mm body contract is missing")
    if power.get("actuator_travel_mm") != 1.6:
        errors.append("manifest: IMMS 1.60 mm actuator travel is missing")
    expected_battery_termination_contract = {
        "pad_1": "BAT+",
        "pad_2": "GND",
        "pad_1_marking": "B+",
        "pad_2_marking": "B-/GND",
        "nice_nano_equivalence": {
            "battery_positive": "U1 RAW / NN_B+",
            "battery_negative": "U1 GND_C / GND",
            "source": "https://nicekeyboards.com/docs/nice-nano/",
        },
    }
    if not isinstance(battery_termination, dict):
        errors.append("manifest: J_BAT1 assembly-marking contract is missing")
    else:
        for field, expected in expected_battery_termination_contract.items():
            if battery_termination.get(field) != expected:
                errors.append(f"manifest: J_BAT1 {field} must be {expected!r}")
    expected_pending_contract = {
        "model_role": "nominal_collision_proxy",
        "exact_purchased_mpn_status": "pending",
        "controlled_drawing_status": "pending",
        "imms_12v_bsi_10_equivalence_status": "pending",
    }
    for field, expected in expected_pending_contract.items():
        if power.get(field) != expected:
            errors.append(
                f"manifest: POWER {field} must remain {expected!r} until exact purchased-part evidence exists"
            )
    return errors


def verify_v2_part_identity_contract(manifest: dict[str, object]) -> list[str]:
    errors: list[str] = []
    expected_requirements = [
        "CON-ARCH-004",
        "CON-ARCH-006",
        "CON-ARCH-007",
        "REL-ARCH-001",
    ]
    if manifest.get("requirement_ids") != expected_requirements:
        errors.append("manifest: requirement IDs are missing, stale, or out of order")
    expected_deep_sea = {
        "family": "Kailh Deep Sea low-profile / PG1353-family",
        "exact_mpn_status": "pending",
        "controlled_drawing_revision_status": "pending",
        "order_ready": False,
    }
    if manifest.get("deep_sea_switch_identity") != expected_deep_sea:
        errors.append(
            "manifest: exact Deep Sea MPN/drawing must remain pending without an invented part identity"
        )
    return errors


def release_candidate_exit_code(report: dict[str, object]) -> int:
    errors = report.get("errors")
    blockers = report.get("order_readiness_blockers")
    if not isinstance(errors, list) or not isinstance(blockers, list):
        return 1
    if errors:
        return 1
    if blockers:
        return 2
    return 0


def build_drc_evidence(
    board_paths: Sequence[Path] = DEFAULT_BOARDS,
) -> dict[str, object]:
    records: dict[str, object] = {}
    for board_path in board_paths:
        side = "left" if "left" in board_path.name.lower() else "right"
        report_path = board_path.with_suffix(".drc.json")
        project_path = board_path.with_suffix(".kicad_pro")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        records[side] = {
            "board_path": board_path.relative_to(ROOT).as_posix(),
            "board_sha256": sha256_file(board_path),
            "drc_report_path": report_path.relative_to(ROOT).as_posix(),
            "drc_report_sha256": sha256_file(report_path),
            "project_path": DEFAULT_BOARDS[0 if side == "left" else 1]
            .with_suffix(".kicad_pro")
            .relative_to(ROOT)
            .as_posix(),
            "project_sha256": sha256_file(project_path),
            "default_clearance_mm": project_default_clearance_mm(project_path),
            "schema": report.get("$schema"),
            "source": report.get("source"),
            "kicad_version": report.get("kicad_version"),
            "date": report.get("date"),
            "included_severities": report.get("included_severities"),
        }
    return {
        "requirement_ids": [
            "CON-ARCH-004",
            "CON-ARCH-006",
            "CON-ARCH-007",
            "REL-ARCH-001",
        ],
        "variant": "x3-v2",
        "status": "draft_not_orderable_pending_physical_evidence",
        "hash_policy": HASH_POLICY,
        "boards": records,
    }


def verify_drc_evidence_binding(
    board_path: Path,
    side: str,
    evidence: dict[str, object],
) -> tuple[list[str], dict[str, object]]:
    errors: list[str] = []
    boards = evidence.get("boards")
    record = boards.get(side) if isinstance(boards, dict) else None
    if not isinstance(record, dict):
        return [f"{side}: DRC evidence record is missing"], {}
    if evidence.get("hash_policy") != HASH_POLICY:
        errors.append(f"{side}: DRC evidence canonical hash policy mismatch")

    report_path = board_path.with_suffix(".drc.json")
    project_path = board_path.with_suffix(".kicad_pro")
    if not board_path.is_file():
        return [f"{side}: DRC evidence board is missing"], record
    if not report_path.is_file():
        return [f"{side}: DRC evidence report is missing"], record
    if not project_path.is_file():
        return [f"{side}: KiCad project is missing"], record

    board_sha256 = sha256_file(board_path)
    report_sha256 = sha256_file(report_path)
    project_sha256 = sha256_file(project_path)
    if record.get("board_sha256") != board_sha256:
        errors.append(f"{side}: DRC evidence board SHA-256 mismatch")
    if record.get("drc_report_sha256") != report_sha256:
        errors.append(f"{side}: DRC evidence report SHA-256 mismatch")
    if record.get("project_sha256") != project_sha256:
        errors.append(f"{side}: DRC evidence project SHA-256 mismatch")

    expected_board_path = DEFAULT_BOARDS[0 if side == "left" else 1].relative_to(ROOT).as_posix()
    expected_report_path = DEFAULT_BOARDS[0 if side == "left" else 1].with_suffix(".drc.json").relative_to(ROOT).as_posix()
    expected_project_path = DEFAULT_BOARDS[0 if side == "left" else 1].with_suffix(".kicad_pro").relative_to(ROOT).as_posix()
    if record.get("board_path") != expected_board_path:
        errors.append(f"{side}: DRC evidence canonical board path mismatch")
    if record.get("drc_report_path") != expected_report_path:
        errors.append(f"{side}: DRC evidence canonical report path mismatch")
    if record.get("project_path") != expected_project_path:
        errors.append(f"{side}: DRC evidence canonical project path mismatch")
    try:
        default_clearance = project_default_clearance_mm(project_path)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"{side}: KiCad project Default clearance cannot be parsed: {error}")
    else:
        if default_clearance < 0.30:
            errors.append(f"{side}: project Default clearance must be at least 0.30 mm")
        if record.get("default_clearance_mm") != default_clearance:
            errors.append(f"{side}: DRC evidence project Default clearance mismatch")

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"{side}: DRC evidence report cannot be parsed: {error}")
        return errors, record
    for field, report_field in (
        ("schema", "$schema"),
        ("source", "source"),
        ("kicad_version", "kicad_version"),
        ("date", "date"),
        ("included_severities", "included_severities"),
    ):
        if record.get(field) != report.get(report_field):
            errors.append(f"{side}: DRC evidence {field} mismatch")
    if report.get("$schema") != "https://schemas.kicad.org/drc.v1.json":
        errors.append(f"{side}: unsupported KiCad DRC schema")
    if report.get("source") != board_path.name:
        errors.append(f"{side}: DRC evidence source does not name the current board")
    kicad_version = report.get("kicad_version")
    if not isinstance(kicad_version, str) or KICAD_10_VERSION_RE.fullmatch(kicad_version) is None:
        errors.append(f"{side}: KiCad DRC version must be 10.x")
    report_date = report.get("date")
    valid_timestamp = isinstance(report_date, str) and ISO_TIMESTAMP_RE.fullmatch(report_date) is not None
    if valid_timestamp:
        try:
            datetime.fromisoformat(report_date.replace("Z", "+00:00"))
        except ValueError:
            valid_timestamp = False
    if not valid_timestamp:
        errors.append(f"{side}: KiCad DRC date is not a valid ISO timestamp")
    included_severities = report.get("included_severities")
    severity_set = set(included_severities) if isinstance(included_severities, list) else set()
    if (
        not isinstance(included_severities, list)
        or any(not isinstance(value, str) for value in included_severities)
        or len(severity_set) != len(included_severities)
        or not REQUIRED_DRC_SEVERITIES.issubset(severity_set)
    ):
        errors.append(f"{side}: KiCad DRC included_severities must contain error and warning")
    if severity_set - ALLOWED_DRC_SEVERITIES:
        errors.append(f"{side}: KiCad DRC included_severities contains an unsupported value")
    return errors, record


def verify_v2_footprint(path: Path = DEFAULT_FOOTPRINT) -> list[str]:
    report = analyze_v2_footprint(path)
    errors: list[str] = []
    if report["name"] != "SW_Choc_V2_Socket_MX_THT":
        errors.append(f"unexpected footprint name: {report['name']}")
    if report["numbered_pad_counts"] != {"1": 2, "2": 2}:
        errors.append(f"expected two alternate pads per contact: {report['numbered_pad_counts']}")
    if report["has_choc_v1_locator_holes"]:
        errors.append("Choc V1 locator holes are forbidden")
    if report["has_mx_hotswap_pads"]:
        errors.append("MX hot-swap pads are forbidden")
    if report["has_choc_v2_direct_solder_pads"]:
        errors.append("Choc V2 direct-solder pads are forbidden")
    if report["choc_socket_back_courtyard_mm"] != {
        "bounds": (-10.25, 1.2, 5.25, 8.5),
        "manufacturing_allowance": 0.25,
        "encloses_body_and_lands": True,
    }:
        errors.append(
            "bottom Choc socket courtyard must enclose the B.Fab body and both B.Cu lands with 0.25 mm allowance"
        )
    return errors


def verify_v2_release_candidate(
    footprint_path: Path = DEFAULT_FOOTPRINT,
    board_paths: Sequence[Path] = DEFAULT_BOARDS,
    manifest_path: Path = DEFAULT_MANIFEST,
    drc_evidence_path: Path = DEFAULT_DRC_EVIDENCE,
    housing_manifest_path: Path = DEFAULT_HOUSING_MANIFEST,
    physical_evidence_path: Path = DEFAULT_PHYSICAL_EVIDENCE,
) -> dict[str, object]:
    from tools.verify_kc2_antenna_keepout import check_board as check_antenna_keepout
    from tools.verify_kc2_compact_controller import check_side as check_compact_controller
    from tools.verify_kc2_connectivity import detect_side, verify_board as verify_connectivity

    board_paths = tuple(board_paths)
    detected_sides: list[str] = []
    board_set_errors: list[str] = []
    for board_path in board_paths:
        try:
            detected_sides.append(detect_side(board_path))
        except ValueError as error:
            board_set_errors.append(f"boards: {error}")
    if Counter(detected_sides) != Counter({"left": 1, "right": 1}):
        board_set_errors.append(
            "boards: expected exactly one detected left and one detected right board"
        )
    if board_set_errors:
        return {
            "requirement": "CON-ARCH-004",
            "status": "invalid_release_candidate",
            "boards": {},
            "connectivity_errors": {},
            "drc_evidence": {},
            "canonical_route_evidence": {},
            "order_readiness_blockers": [],
            "errors": board_set_errors,
        }

    errors = [f"footprint: {error}" for error in verify_v2_footprint(footprint_path)]
    manifest = analyze_v2_manifest(manifest_path)
    errors.extend(verify_v2_part_identity_contract(manifest))
    errors.extend(verify_controller_service_model_binding(manifest))
    errors.extend(verify_controller_service_manifest_clearances(manifest))
    drc_evidence = analyze_v2_manifest(drc_evidence_path)
    housing_manifest = analyze_v2_manifest(housing_manifest_path)
    physical_evidence = analyze_v2_manifest(physical_evidence_path)
    if drc_evidence.get("requirement_ids") != [
        "CON-ARCH-004",
        "CON-ARCH-006",
        "CON-ARCH-007",
        "REL-ARCH-001",
    ]:
        errors.append("DRC evidence: requirement IDs are missing or stale")
    if drc_evidence.get("variant") != "x3-v2":
        errors.append("DRC evidence: variant is missing or stale")
    if manifest.get("variant") != "x3-v2":
        errors.append(f"manifest: unexpected variant {manifest.get('variant')!r}")
    if manifest.get("assembly_modes") != [
        "choc_v2_bottom_socket",
        "mx_5pin_top_direct_solder",
    ]:
        errors.append("manifest: assembly modes are incomplete or out of order")
    if not manifest.get("assembly_modes_mutually_exclusive"):
        errors.append("manifest: switch assembly modes must be mutually exclusive")
    if manifest.get("key_count") != {"left": 31, "right": 39, "total": 70}:
        errors.append(f"manifest: unexpected key count {manifest.get('key_count')!r}")
    if manifest.get("keycell_edge_inset_mm") != 1.5:
        errors.append("manifest: V2 key-field edge inset must be 1.5 mm")
    if manifest.get("one_unit_join_center_to_edge_mm") != 8.025:
        errors.append("manifest: V2 one-unit join center-to-edge distance must be 8.025 mm")
    if "join_center_to_edge_mm" in manifest:
        errors.append("manifest: ambiguous scalar join_center_to_edge_mm is forbidden")
    if manifest.get("join_geometry_by_row") != x3_v2_join_geometry_by_row():
        errors.append("manifest: V2 per-row joined cap/edge geometry is missing or stale")
    if manifest.get("join_keycap_setback_mm") != 1.0:
        errors.append("manifest: V2 join keycap-relative setback must be 1.0 mm")
    if manifest.get("join_keycap_gap_mm") != 1.8:
        errors.append("manifest: V2 joined MX-envelope keycap gap must be 1.8 mm")
    if manifest.get("one_unit_join_center_pitch_mm") != 19.85:
        errors.append("manifest: V2 joined one-unit center pitch must be 19.85 mm")
    if "join_center_pitch_mm" in manifest:
        errors.append("manifest: ambiguous scalar join_center_pitch_mm is forbidden")
    if manifest.get("join_placement_offset_mm") != 0.8:
        errors.append("manifest: V2 safe joined placement offset must be 0.8 mm")
    if manifest.get("row_center_joined_pcb_gap_mm") != 3.8:
        errors.append("manifest: V2 row-center PCB gap must be 3.8 mm")
    if manifest.get("minimum_joined_edge_clearance_mm") != 1.0:
        errors.append("manifest: V2 exact joined Edge.Cuts clearance gate must be 1.0 mm")
    if manifest.get("seam_transition_stagger_mm") != 0.55:
        errors.append("manifest: V2 seam transition stagger must be 0.55 mm")
    if manifest.get("outline_policy") != "keycap_concealed_except_controller_service":
        errors.append("manifest: V2 compact outline policy is missing")
    if manifest.get("autoroute_boundary_policy") != {
        "inset_mm": 0.35,
        "preserve_controller_above_y_mm": 67.5,
        "edge_cuts_unchanged": True,
    }:
        errors.append("manifest: V2 autoroute edge-clearance boundary policy is missing")
    if manifest.get("pcb_fastener_holes") != expected_m1_4_mount_manifest():
        errors.append("manifest: exact selected M1.4 MH pattern and service envelope are missing or stale")
    pcb_closed_bottom = (
        (manifest.get("pcb_fastener_holes") or {})
        .get("housing_interface_mm", {})
        .get("desk_column_closed_bottom")
    )
    housing_closed_bottom = (housing_manifest.get("parameters") or {}).get(
        "mounting_closed_bottom_mm"
    )
    if pcb_closed_bottom != housing_closed_bottom:
        errors.append("manifest: PCB/housing mounting closed-bottom contract mismatch")
    if manifest.get("x3_tact_battery_clearance_mm") is not None:
        errors.append("manifest: legacy X3 tact-to-battery scalar is forbidden for V2")
    if manifest.get("screwless_registration_holes") is not None:
        errors.append("manifest: legacy H1-H9 registration holes are forbidden on V2")
    if manifest.get("controller_socket_geometry_mm") != {
        "longitudinal_pin_pitch": 2.54,
        "row_center_spacing": 15.24,
        "row_count": 2,
        "pins_per_row": 12,
    }:
        errors.append("manifest: nice!nano socket geometry must use 15.24 mm row spacing")
    diode_policy = manifest.get("diode_placement_policy") or {}
    if diode_policy.get("minimum_unused_feature_clearance_mm") != 1.0:
        errors.append("manifest: diode hand-solder clearance policy is missing")
    if manifest.get("matrix_route_clearance_mm") != 0.30:
        errors.append("manifest: V2 matrix route clearance must be 0.30 mm")
    if diode_policy.get("minimum_fillet_to_unrelated_route_mm") != 0.10:
        errors.append("manifest: diode-to-unrelated-route clearance policy is missing")
    if diode_policy.get("minimum_edge_cuts_clearance_mm") != 1.3:
        errors.append("manifest: diode Edge.Cuts clearance policy is missing")
    if diode_policy.get("edge_safe_offsets_mm") != {
        "top_second_key": {"x": 7.0, "y": 7.0, "rotation_degrees": 90.0},
        "top_other_keys": {"x": -8.75, "y": -3.25, "rotation_degrees": 270.0},
        "bottom_first_key": {"x": 9.5, "y": 3.25},
    }:
        errors.append("manifest: verified edge-safe diode offsets are missing")

    route_evidence_errors, route_evidence_reports = verify_canonical_route_evidence(manifest)
    errors.extend(route_evidence_errors)

    board_reports: dict[str, object] = {}
    connectivity_errors: dict[str, list[str]] = {}
    drc_evidence_reports: dict[str, object] = {}
    for board_path in board_paths:
        side = detect_side(board_path)
        drc_binding_errors, drc_evidence_record = verify_drc_evidence_binding(
            board_path,
            side,
            drc_evidence,
        )
        errors.extend(drc_binding_errors)
        drc_evidence_reports[side] = drc_evidence_record
        expected_keys = 31 if side == "left" else 39
        report = analyze_v2_board(board_path)
        board_reports[side] = report
        errors.extend(
            f"{side}: board text: {error}"
            for error in verify_active_v2_board_text_contract(report["board_text"])
        )
        checks = {
            "switch count": report["switch_count"] == expected_keys,
            "diode count": report["diode_count"] == expected_keys,
            "owned ES1B diode footprint": report["diode_footprint_names"]
            == {"D_ES1B_SMA_HandSolder_C437840"},
            "locked ES1B diode identity": report["diode_values"]
            == {"ES1B_Jingdao_C437840_Eleparts9475342"},
            "ES1B cathode/anode nets": not report["diode_pin_net_errors"],
            "placed ES1B owned geometry": not report["diode_footprint_geometry_errors"],
            "owned switch footprint": report["switch_footprint_names"]
            == {"SW_Choc_V2_Socket_MX_THT"},
            "placed switch owned geometry": not report["switch_footprint_geometry_errors"],
            "alternate contact nets": not report["alternate_contact_net_mismatches"],
            "switch placement matches generator": not report["switch_layout_errors"],
            "no stabilizers": not report["stabilizer_refs"],
            "no legacy key-field registration holes": report["registration_hole_count"] == 0,
            "registration hole safety": not report["registration_hole_errors"],
            "no legacy H-series mounting holes": not report["legacy_mount_hole_refs"],
            "exact copper-free M1.4 MH pattern": not report["mounting_hole_errors"],
            "visible numbered M1.4 MH front silkscreen": not report[
                "mounting_hole_silkscreen_errors"
            ],
            "M1.4 driver-to-copper clearance": not report[
                "mounting_hole_driver_copper_errors"
            ],
            "rounded M1.4 head 0.25 mm XY reserve": not report[
                "mounting_hole_head_clearance_errors"
            ],
            "canonical final route item count": report["route_track_via_count"]
            == manifest["canonical_route_evidence"][side]["final_track_via_count"],
            "canonical final route digest": report["route_digest_sha256"]
            == manifest["canonical_route_evidence"][side]["route_digest_sha256"],
            "M1.4 retention board identity": (
                any(
                    "SELECTED M1.4 MH RETENTION" in text.upper()
                    for text in report["board_text"]
                )
                and not any(
                    "NO KEY-FIELD HOLES" in text.upper()
                    for text in report["board_text"]
                )
            ),
            "exact carrier power interfaces": report["carrier_power_pad_refs"]
            == ["J_BAT1", "SW_PWR1"],
            "one battery lead slot": report["battery_lead_slot_count"] == 1,
            "copper-free battery lead slot": not report["battery_lead_slot_errors"],
            "battery slot on USB/B+ side": report["battery_lead_slot_on_usb_side"],
            "controller power nets": report["controller_power_nets"]
            == ["BAT+", "GND", "NN_B+"],
            "no obsolete carrier power nets": not report["forbidden_carrier_power_nets"],
            "side-specific controller footprint and USB label": not report["controller_contract_errors"],
            "reset pad contract": not report["reset_contract_errors"],
            "controller service mechanical clearances": not report[
                "controller_service_clearance_errors"
            ],
            "diode hand-solder clearance": not report["diode_hand_solder_clearance_errors"],
            "diode unrelated-route clearance": not report["diode_to_unrelated_route_errors"],
            "diode Edge.Cuts clearance": not report["diode_edge_clearance_errors"],
            "V2 assembly warning": any(
                "CHOC V1 UNSUPPORTED" in text.upper() for text in report["board_text"]
            ),
            "DRC violations": report["drc_violation_count"] == 0,
            "DRC unconnected items": report["drc_unconnected_count"] == 0,
            "reviewed DRC exclusions": report["drc_ignored_checks"]
            == EXPECTED_IGNORED_DRC_CHECKS,
        }
        errors.extend(f"{side}: failed {label}" for label, passed in checks.items() if not passed)

        connectivity_errors[side] = verify_connectivity(board_path)
        errors.extend(f"{side} connectivity: {error}" for error in connectivity_errors[side])
        errors.extend(f"{side} controller: {error}" for error in check_compact_controller(side, board_path))
        keepout = tuple(float(value) for value in manifest["antenna_keepout_mm"][side])
        errors.extend(
            f"{side} antenna: {error}"
            for error in check_antenna_keepout(side, board_path, keepout)
        )

    order_readiness_blockers = controller_service_order_readiness_blockers(
        manifest,
        housing_manifest,
        physical_evidence,
        {
            "left_board": board_paths[detected_sides.index("left")],
            "right_board": board_paths[detected_sides.index("right")],
            "generation_manifest": manifest_path,
            "housing_manifest": housing_manifest_path,
            "fabrication_manifest": DEFAULT_FABRICATION_MANIFEST,
            "mechanical_manifest": V2_ROOT
            / "mechanical"
            / "kc2_x3_v2_mechanical_manifest.json",
            "render_manifest": V2_ROOT
            / "renders"
            / "kc2_x3_v2_render_manifest.json",
            "outline_report": DEFAULT_OUTLINE_REPORT,
            "firmware_build_evidence": DEFAULT_FIRMWARE_BUILD_EVIDENCE,
        },
    )
    if errors:
        status = "invalid_release_candidate"
    elif order_readiness_blockers:
        status = "draft_not_orderable_pending_physical_evidence"
    else:
        status = "order_ready_verified_physical_evidence"

    return {
        "requirement": "CON-ARCH-004",
        "status": status,
        "boards": board_reports,
        "connectivity_errors": connectivity_errors,
        "drc_evidence": drc_evidence_reports,
        "canonical_route_evidence": route_evidence_reports,
        "physical_evidence": physical_evidence,
        "order_readiness_blockers": order_readiness_blockers,
        "reviewed_drc_exclusions": {
            "checks": EXPECTED_IGNORED_DRC_CHECKS,
            "rationale": (
                "Inherited project exclusions are limited to non-electrical library, courtyard, "
                "track-centering, and tuning-pattern diagnostics; all actual V2 violations and "
                "unconnected items remain hard failures."
            ),
        },
        "errors": errors,
    }


def _specctra_mount_positions_mm(
    text: str,
    coordinate_scale: float,
) -> dict[str, tuple[float, float]]:
    return {
        reference: (
            round(float(x) / coordinate_scale, 4),
            round(-float(y) / coordinate_scale, 4),
        )
        for reference, x, y in re.findall(
            r"\(place\s+(MH\d+)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\b",
            text,
        )
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify CON-ARCH-004 KC2 X3 V2 routed draft.")
    parser.add_argument("--footprint", type=Path, default=DEFAULT_FOOTPRINT)
    parser.add_argument("--boards", type=Path, nargs="*", default=DEFAULT_BOARDS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--drc-evidence", type=Path, default=DEFAULT_DRC_EVIDENCE)
    parser.add_argument("--housing-manifest", type=Path, default=DEFAULT_HOUSING_MANIFEST)
    parser.add_argument("--physical-evidence", type=Path, default=DEFAULT_PHYSICAL_EVIDENCE)
    args = parser.parse_args()
    report = verify_v2_release_candidate(
        args.footprint,
        args.boards,
        args.manifest,
        args.drc_evidence,
        args.housing_manifest,
        args.physical_evidence,
    )
    errors = report["errors"]
    exit_code = release_candidate_exit_code(report)
    if exit_code == 1:
        raise SystemExit("FAIL: KC2 X3 V2 routed draft verification\n- " + "\n- ".join(errors))
    print(json.dumps(report, indent=2, default=list))
    if exit_code == 2:
        print("DIGITAL PASS: routed boards, connectivity, controller, antenna, and housing bindings")
        print("NOT ORDER READY:\n- " + "\n- ".join(report["order_readiness_blockers"]))
        raise SystemExit(2)
    print("PASS: digital checks and order-readiness gates")


if __name__ == "__main__":
    main()
