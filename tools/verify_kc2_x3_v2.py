from __future__ import annotations

import argparse
import heapq
import json
from collections import Counter
from datetime import datetime
import math
from pathlib import Path
import re
from typing import Iterable, Sequence

import pcbnew

from tools.canonical_hash import HASH_POLICY, sha256_file
from tools.generate_kc2_pcbs import (
    X3_V2_CONTROLLER_SERVICE_POSITIONS_MM,
    X3_V2_J_BAT1_ROTATIONS_DEGREES,
    X3_V2_RESET_BODY_SIZE_MM,
    X3_V2_RESET_BODY_TO_KEYCAP_MIN_MM,
    X3_V2_RESET_COURTYARD_TO_U1_SOCKET_COPPER_MIN_MM,
    X3_V2_RESET_KEYCAP_ENVELOPE_MM,
    X3_V2_RESET_ROTATIONS_DEGREES,
    X3_V2_TOP_EDGE_Y_MM,
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
EXPECTED_M1_4_MOUNTING_POINTS = {
    "left": [
        ("MH1", 142.6125, 68.0000),
        ("MH2", 128.6125, 86.5000),
        ("MH3", 100.1125, 93.5000),
        ("MH4", 57.1125, 99.0000),
        ("MH5", 133.6125, 131.5000),
        ("MH6", 55.1125, 144.0000),
        ("MH7", 165.6125, 145.0000),
        ("MH8", 102.6125, 147.0000),
    ],
    "right": [
        ("MH1", 71.6875, 68.0000),
        ("MH2", 181.1875, 85.5000),
        ("MH3", 147.6875, 93.5000),
        ("MH4", 109.6875, 96.5000),
        ("MH5", 71.6875, 105.5000),
        ("MH6", 42.1875, 106.0000),
        ("MH7", 181.1875, 134.5000),
        ("MH8", 143.1875, 134.5000),
        ("MH9", 51.6875, 144.0000),
        ("MH10", 95.6875, 147.0000),
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
        if layer not in {"F.Fab", "F.Courtyard", "F.Silkscreen"}:
            continue
        if isinstance(item, pcbnew.PCB_SHAPE):
            start = item.GetStart()
            end = item.GetEnd()
            signatures.append(
                (
                    "shape",
                    layer,
                    int(item.GetShape()),
                    mm(start.x),
                    mm(start.y),
                    mm(end.x),
                    mm(end.y),
                    mm(item.GetWidth()),
                )
            )
        elif isinstance(item, pcbnew.PCB_TEXT):
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
    for switch in switches:
        if normalized_pad_signatures(switch) != expected_switch_pads:
            switch_errors.append(
                f"{switch.GetReference()}: pad/NPTH geometry differs from owned hybrid-switch footprint"
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
        "references": "MH1..MH8 left; MH1..MH10 right",
        "counts": {"left": 8, "right": 10, "total": 18},
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
        if reference_signature != (True, pcbnew.F_SilkS, 0.8, 0.1, 0.0, -1.5):
            silkscreen_errors.append(
                f"{hole.GetReference()}: visible F.SilkS reference must be "
                "0.80 mm high / 0.10 mm stroke at relative (0.0,-1.5) mm; "
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

    switch_driver_boxes = [
        (
            pcbnew.ToMM(switch.GetPosition().x) - 7.8,
            pcbnew.ToMM(switch.GetPosition().y) - 7.8,
            pcbnew.ToMM(switch.GetPosition().x) + 7.8,
            pcbnew.ToMM(switch.GetPosition().y) + 7.8,
        )
        for switch in matrix_footprints(board, "SW")
    ]
    controller_service_boxes = [
        bounding_box_mm(footprint)
        for footprint in board.GetFootprints()
        if footprint.GetReference() in {"U1", "SW_RST1"}
    ]
    driver_boxes = switch_driver_boxes + controller_service_boxes
    driver_clearances = [
        point_to_box_distance_mm(center, box) - 1.5
        for center in hole_centers
        for box in driver_boxes
    ]
    minimum_driver_clearance = min(driver_clearances) if driver_clearances else math.inf
    if minimum_driver_clearance < -1e-6:
        errors.append(
            f"{side}: final 3.00 mm PH0 driver envelope intersects an installed body by "
            f"{-minimum_driver_clearance:.4f} mm"
        )

    outline_segments = board_outline_segments_mm(board)
    edge_clearances = [
        point_to_segment_distance_mm(center, start, end) - 1.0
        for center in hole_centers
        for start, end in outline_segments
    ]
    minimum_head_edge_clearance = min(edge_clearances) if edge_clearances else math.inf
    if minimum_head_edge_clearance < 0.25 - 1e-6:
        errors.append(
            f"{side}: screw-head-to-Edge.Cuts clearance {minimum_head_edge_clearance:.4f} mm is below 0.25 mm"
        )

    return errors, positions, {
        "minimum_npth_edge_to_copper_mm": round(minimum_copper_clearance, 4),
        "minimum_driver_to_copper_mm": round(minimum_driver_copper_clearance, 4),
        "minimum_driver_to_installed_body_mm": round(minimum_driver_clearance, 4),
        "minimum_head_to_edge_cuts_mm": round(minimum_head_edge_clearance, 4),
    }, driver_copper_errors, silkscreen_errors


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
        }
        if record.get("dsn_sha256") != dsn_sha:
            errors.append(f"{side}: DSN SHA-256 mismatch")
        if record.get("ses_sha256") != ses_sha:
            errors.append(f"{side}: SES SHA-256 mismatch")
        if record.get("session_source_dsn_sha256") != session_source_dsn_sha:
            errors.append(f"{side}: reviewed SES source DSN SHA-256 mismatch")
        expected_holes = 8 if side == "left" else 10
        if reports[side]["dsn_mounting_hole_count"] != expected_holes:
            errors.append(f"{side}: current DSN does not contain the exact MH pattern")
        if record.get("dsn_mounting_hole_count") != expected_holes:
            errors.append(f"{side}: current DSN MH count evidence mismatch")
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


def controller_service_order_readiness_blockers(
    manifest: dict[str, object],
    housing_manifest: dict[str, object] | None = None,
) -> list[str]:
    service = manifest.get("controller_service_region")
    if not isinstance(service, dict):
        return ["CON-ARCH-007 controller service manifest is missing"]
    blockers: list[str] = []
    termination = service.get("battery_termination")
    if not isinstance(termination, dict) or termination.get("lead_drawing_status") != (
        "confirmed_exact_purchased_pack"
    ):
        blockers.append(
            "CON-ARCH-007 AC-4: J_BAT1 0.90 mm drill is provisional until the exact "
            "purchased battery lead drawing is confirmed"
        )
    if service.get("physical_validation") != "passed_battery_power_reset_rf_first_article":
        blockers.append(
            "CON-ARCH-007/REL-ARCH-001: battery stack, POWER/RESET access, 20-cycle "
            "power transition, RSSI/PER, disconnect, and USB charging-state evidence is pending"
        )
    if service.get("order_ready") is not True:
        blockers.append("CON-ARCH-007: controller service order_ready is not true")

    physical_scan = manifest.get("physical_scan_validation")
    if not isinstance(physical_scan, dict) or physical_scan.get("status") != "passed":
        blockers.append("CON-ARCH-004: physical scan validation status is not passed")
    if not isinstance(physical_scan, dict) or physical_scan.get("orderable") is not True:
        blockers.append("CON-ARCH-004: physical scan validation is not orderable")

    if not isinstance(housing_manifest, dict):
        blockers.append("CON-ARCH-006: housing manifest is missing or invalid")
    else:
        if housing_manifest.get("order_ready") is not True:
            blockers.append("CON-ARCH-006: housing manifest order_ready is not true")
        retention = housing_manifest.get("retention")
        if not isinstance(retention, dict) or retention.get(
            "physical_registration_status"
        ) != "passed":
            blockers.append(
                "CON-ARCH-006: housing physical registration status is not passed"
            )
        deflection = housing_manifest.get("physical_deflection_test")
        if not isinstance(deflection, dict) or deflection.get("status") != "passed":
            blockers.append(
                "CON-ARCH-006: housing physical deflection test status is not passed"
            )
    return blockers


def verify_controller_service_model_binding(
    manifest: dict[str, object],
) -> list[str]:
    service = manifest.get("controller_service_region")
    power = service.get("power") if isinstance(service, dict) else None
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
    return errors


def verify_v2_release_candidate(
    footprint_path: Path = DEFAULT_FOOTPRINT,
    board_paths: Sequence[Path] = DEFAULT_BOARDS,
    manifest_path: Path = DEFAULT_MANIFEST,
    drc_evidence_path: Path = DEFAULT_DRC_EVIDENCE,
    housing_manifest_path: Path = DEFAULT_HOUSING_MANIFEST,
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
    errors.extend(verify_controller_service_model_binding(manifest))
    errors.extend(verify_controller_service_manifest_clearances(manifest))
    drc_evidence = analyze_v2_manifest(drc_evidence_path)
    housing_manifest = analyze_v2_manifest(housing_manifest_path)
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

    return {
        "requirement": "CON-ARCH-004",
        "status": "draft_not_orderable_pending_physical_coupon",
        "boards": board_reports,
        "connectivity_errors": connectivity_errors,
        "drc_evidence": drc_evidence_reports,
        "canonical_route_evidence": route_evidence_reports,
        "order_readiness_blockers": controller_service_order_readiness_blockers(
            manifest,
            housing_manifest,
        ),
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify CON-ARCH-004 KC2 X3 V2 routed draft.")
    parser.add_argument("--footprint", type=Path, default=DEFAULT_FOOTPRINT)
    parser.add_argument("--boards", type=Path, nargs="*", default=DEFAULT_BOARDS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--drc-evidence", type=Path, default=DEFAULT_DRC_EVIDENCE)
    parser.add_argument("--housing-manifest", type=Path, default=DEFAULT_HOUSING_MANIFEST)
    args = parser.parse_args()
    report = verify_v2_release_candidate(
        args.footprint,
        args.boards,
        args.manifest,
        args.drc_evidence,
        args.housing_manifest,
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
