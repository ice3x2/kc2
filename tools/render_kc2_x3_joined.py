from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pcbnew

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.generate_kc2_pcbs import (  # noqa: E402
    UNIT,
    Key,
    X3_V2_JOIN_CENTER_PITCH,
    make_left_keys_no_stab,
    make_left_keys_x3_v2,
    make_right_keys_no_stab,
    make_right_keys_x3_v2,
)
from tools.canonical_hash import HASH_POLICY, sha256_file  # noqa: E402

DEFAULT_CLEARANCE_MM = 1.0
DEFAULT_SCALE = 5.0
FULL_MARGIN_PX = 40.0
ZOOM_WIDTH_MM = 64.0
SCAN_STEP_MM = 0.005
CORRIDOR_STEP_MM = 0.25
TY_ROW_CENTER_Y_MM = 96.575
X3_V2_SERVICE_REFERENCES = ("BAT1", "J_BAT1", "SW_PWR1", "SW_RST1")
X3_V2_BATTERY_TERMINAL_LEGENDS = ("B+", "B-/GND")
SERVICE_STYLES = {
    "BAT1": ("#f1e7ff", "#7951a8"),
    "J_BAT1": ("#fff1d8", "#b66a13"),
    "SW_PWR1": ("#ffe5dd", "#b83d27"),
    "SW_RST1": ("#ffe8f2", "#a83267"),
}


Segment = tuple[tuple[float, float], tuple[float, float]]


@dataclass(frozen=True)
class MountRenderData:
    reference: str
    center: tuple[float, float]


@dataclass(frozen=True)
class ServiceRenderData:
    reference: str
    center: tuple[float, float]
    bounds: tuple[float, float, float, float]
    rotation_degrees: float


@dataclass(frozen=True)
class TerminalLegendRenderData:
    text: str
    center: tuple[float, float]


@dataclass(frozen=True)
class BoardRenderData:
    side: str
    source_path: Path
    board: pcbnew.BOARD
    edge_segments: list[Segment]
    bounds: tuple[float, float, float, float]
    keys: list[Key]
    switch_centers: dict[int, tuple[float, float]]
    mounts: list[MountRenderData]
    service_components: list[ServiceRenderData]
    battery_terminal_legends: list[TerminalLegendRenderData]
    controller_bounds: tuple[float, float, float, float]


@dataclass(frozen=True)
class ClearanceSample:
    y: float
    left_x: float
    right_x: float
    clearance: float


@dataclass(frozen=True)
class SegmentClearance:
    left_point: tuple[float, float]
    right_point: tuple[float, float]
    clearance: float


@dataclass(frozen=True)
class KeyHorizontalClearance:
    left_label: str
    right_label: str
    start: tuple[float, float]
    end: tuple[float, float]
    clearance: float


@dataclass(frozen=True)
class SeamKeyClearance:
    row: int
    left_label: str
    right_label: str
    left_cap_width_mm: float
    right_cap_width_mm: float
    center_pitch_mm: float
    cap_gap_mm: float
    left_center_to_pcb_edge_mm: float
    right_center_to_pcb_edge_mm: float
    pcb_gap_mm: float
    start: tuple[float, float]
    end: tuple[float, float]


@dataclass(frozen=True)
class RenderContext:
    variant: str
    scale: float
    clearance_mm: float
    placement_mode: str
    left: BoardRenderData
    right: BoardRenderData
    right_dx: float
    right_dy: float
    bounds: tuple[float, float, float, float]
    min_edge_clearance_mm: float
    min_clearance_y: float
    measurement: ClearanceSample
    clearance_samples: list[ClearanceSample]
    key_horizontal_clearance: KeyHorizontalClearance
    seam_key_clearances: list[SeamKeyClearance]
    outline_x_range_nesting_mm: float


def mm_vec(vec: pcbnew.VECTOR2I) -> tuple[float, float]:
    return pcbnew.ToMM(vec.x), pcbnew.ToMM(vec.y)


def edge_segments(board: pcbnew.BOARD) -> list[Segment]:
    segments: list[Segment] = []
    for item in board.GetDrawings():
        if item.GetLayer() != pcbnew.Edge_Cuts:
            continue
        if not hasattr(item, "GetStart") or not hasattr(item, "GetEnd"):
            continue
        segments.append((mm_vec(item.GetStart()), mm_vec(item.GetEnd())))
    if not segments:
        raise RuntimeError("No Edge.Cuts segments found")
    return segments


def bounds_from_points(points: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    return (
        min(x for x, _ in points),
        min(y for _, y in points),
        max(x for x, _ in points),
        max(y for _, y in points),
    )


def board_bounds(segments: list[Segment]) -> tuple[float, float, float, float]:
    points = [point for segment in segments for point in segment]
    return bounds_from_points(points)


def switch_centers(board: pcbnew.BOARD) -> dict[int, tuple[float, float]]:
    centers: dict[int, tuple[float, float]] = {}
    for fp in board.GetFootprints():
        if not re.fullmatch(r"SW\d+", fp.GetReference()):
            continue
        match = re.fullmatch(r"KEY_(\d+)", fp.GetValue())
        if not match:
            continue
        centers[int(match.group(1))] = mm_vec(fp.GetPosition())
    return centers


def mount_records(board: pcbnew.BOARD) -> list[MountRenderData]:
    records: list[MountRenderData] = []
    for fp in board.GetFootprints():
        reference = fp.GetReference()
        if re.fullmatch(r"MH\d+", reference) or fp.GetValue() in {
            "M2_NPTH_2.2",
            "REG_NPTH_3.0",
        }:
            records.append(MountRenderData(reference, mm_vec(fp.GetPosition())))
    return sorted(records, key=lambda record: record.reference)


def _box_mm(box: pcbnew.BOX2I) -> tuple[float, float, float, float]:
    x = pcbnew.ToMM(box.GetX())
    y = pcbnew.ToMM(box.GetY())
    return x, y, x + pcbnew.ToMM(box.GetWidth()), y + pcbnew.ToMM(box.GetHeight())


def service_component_records(
    board: pcbnew.BOARD,
    expected_references: tuple[str, ...],
) -> list[ServiceRenderData]:
    records: list[ServiceRenderData] = []
    for reference in expected_references:
        matches = [fp for fp in board.GetFootprints() if fp.GetReference() == reference]
        if len(matches) != 1:
            state = "missing" if not matches else f"duplicated ({len(matches)})"
            raise RuntimeError(f"service reference {reference} is {state}")
        footprint = matches[0]
        records.append(
            ServiceRenderData(
                reference=reference,
                center=mm_vec(footprint.GetPosition()),
                bounds=_box_mm(footprint.GetBoundingBox(False, False)),
                rotation_degrees=float(footprint.GetOrientationDegrees()),
            )
        )
    return records


def battery_terminal_legend_records(board: pcbnew.BOARD) -> list[TerminalLegendRenderData]:
    matches = [fp for fp in board.GetFootprints() if fp.GetReference() == "J_BAT1"]
    if len(matches) != 1:
        state = "missing" if not matches else f"duplicated ({len(matches)})"
        raise RuntimeError(f"service reference J_BAT1 is {state}")
    footprint = matches[0]
    records: list[TerminalLegendRenderData] = []
    for expected_text in X3_V2_BATTERY_TERMINAL_LEGENDS:
        text_items = [
            item
            for item in footprint.GraphicalItems()
            if hasattr(item, "GetText")
            and item.GetText() == expected_text
            and item.IsVisible()
            and item.GetLayerName() == "F.Silkscreen"
        ]
        if len(text_items) != 1:
            state = "missing" if not text_items else f"duplicated ({len(text_items)})"
            raise RuntimeError(f"battery terminal legend {expected_text} is {state}")
        records.append(
            TerminalLegendRenderData(expected_text, mm_vec(text_items[0].GetPosition()))
        )
    return records


def controller_bounds(board: pcbnew.BOARD) -> tuple[float, float, float, float]:
    for fp in board.GetFootprints():
        if fp.GetReference() != "U1":
            continue
        xs: list[float] = []
        ys: list[float] = []
        for pad in fp.Pads():
            px, py = mm_vec(pad.GetPosition())
            sx, sy = pcbnew.ToMM(pad.GetSize().x), pcbnew.ToMM(pad.GetSize().y)
            xs.extend([px - sx / 2.0, px + sx / 2.0])
            ys.extend([py - sy / 2.0, py + sy / 2.0])
        if not xs:
            break
        return min(xs), min(ys), max(xs), max(ys)
    raise RuntimeError("U1 controller footprint not found")


def load_board_data(
    side: str,
    path: Path,
    keys: list[Key],
    service_references: tuple[str, ...] = (),
) -> BoardRenderData:
    board = pcbnew.LoadBoard(str(path))
    segments = edge_segments(board)
    centers = switch_centers(board)
    expected = set(range(1, len(keys) + 1))
    missing = sorted(expected - set(centers))
    extra = sorted(set(centers) - expected)
    if missing or extra:
        raise RuntimeError(f"{side} switch/key mismatch: missing={missing}, extra={extra}")
    return BoardRenderData(
        side=side,
        source_path=path,
        board=board,
        edge_segments=segments,
        bounds=board_bounds(segments),
        keys=keys,
        switch_centers=centers,
        mounts=mount_records(board),
        service_components=service_component_records(board, service_references),
        battery_terminal_legends=(
            battery_terminal_legend_records(board) if service_references else []
        ),
        controller_bounds=controller_bounds(board),
    )


def x_crossings(segments: list[Segment], y: float) -> list[float]:
    xs: list[float] = []
    for (x1, y1), (x2, y2) in segments:
        if abs(y2 - y1) < 1e-9:
            continue
        low = min(y1, y2)
        high = max(y1, y2)
        if low <= y < high:
            t = (y - y1) / (y2 - y1)
            xs.append(x1 + t * (x2 - x1))
    xs.sort()
    merged: list[float] = []
    for x in xs:
        if not merged or abs(x - merged[-1]) > 1e-4:
            merged.append(x)
    return merged


def _cross(first: tuple[float, float], second: tuple[float, float]) -> float:
    return first[0] * second[1] - first[1] * second[0]


def _subtract(first: tuple[float, float], second: tuple[float, float]) -> tuple[float, float]:
    return first[0] - second[0], first[1] - second[1]


def _orientation(
    first: tuple[float, float],
    second: tuple[float, float],
    third: tuple[float, float],
) -> float:
    return _cross(_subtract(second, first), _subtract(third, first))


def _point_on_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
    tolerance: float = 1e-9,
) -> bool:
    return abs(_orientation(start, end, point)) <= tolerance and (
        min(start[0], end[0]) - tolerance <= point[0] <= max(start[0], end[0]) + tolerance
        and min(start[1], end[1]) - tolerance <= point[1] <= max(start[1], end[1]) + tolerance
    )


def _segments_intersect(first: Segment, second: Segment, tolerance: float = 1e-9) -> bool:
    a, b = first
    c, d = second
    orientations = (
        _orientation(a, b, c),
        _orientation(a, b, d),
        _orientation(c, d, a),
        _orientation(c, d, b),
    )
    if orientations[0] * orientations[1] < -tolerance and orientations[2] * orientations[3] < -tolerance:
        return True
    return any(
        abs(orientation) <= tolerance and _point_on_segment(point, start, end, tolerance)
        for point, start, end, orientation in (
            (c, a, b, orientations[0]),
            (d, a, b, orientations[1]),
            (a, c, d, orientations[2]),
            (b, c, d, orientations[3]),
        )
    )


def _closest_point_on_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[tuple[float, float], float]:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared <= 1e-18:
        closest = start
    else:
        projection = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_squared
        projection = min(1.0, max(0.0, projection))
        closest = start[0] + projection * dx, start[1] + projection * dy
    return closest, math.hypot(point[0] - closest[0], point[1] - closest[1])


def _segment_pair_clearance(left: Segment, right: Segment) -> SegmentClearance:
    if _segments_intersect(left, right):
        left_start, left_end = left
        right_start, right_end = right
        for point, start, end in (
            (left_start, right_start, right_end),
            (left_end, right_start, right_end),
            (right_start, left_start, left_end),
            (right_end, left_start, left_end),
        ):
            if _point_on_segment(point, start, end):
                return SegmentClearance(point, point, 0.0)
        left_vector = _subtract(left_end, left_start)
        right_vector = _subtract(right_end, right_start)
        denominator = _cross(left_vector, right_vector)
        if abs(denominator) > 1e-12:
            offset = _subtract(right_start, left_start)
            ratio = _cross(offset, right_vector) / denominator
            intersection = (
                left_start[0] + ratio * left_vector[0],
                left_start[1] + ratio * left_vector[1],
            )
            return SegmentClearance(intersection, intersection, 0.0)
        return SegmentClearance(left_start, left_start, 0.0)

    candidates: list[SegmentClearance] = []
    for point in left:
        closest, distance = _closest_point_on_segment(point, right[0], right[1])
        candidates.append(SegmentClearance(point, closest, distance))
    for point in right:
        closest, distance = _closest_point_on_segment(point, left[0], left[1])
        candidates.append(SegmentClearance(closest, point, distance))
    return min(candidates, key=lambda candidate: candidate.clearance)


def minimum_segment_clearance(
    left_segments: list[Segment],
    right_segments: list[Segment],
    right_dx: float = 0.0,
    right_dy: float = 0.0,
) -> SegmentClearance:
    shifted_right = [
        (
            (start[0] + right_dx, start[1] + right_dy),
            (end[0] + right_dx, end[1] + right_dy),
        )
        for start, end in right_segments
    ]
    if not left_segments or not shifted_right:
        raise RuntimeError("Both joined Edge.Cuts segment lists must be non-empty")
    return min(
        (_segment_pair_clearance(left, right) for left in left_segments for right in shifted_right),
        key=lambda candidate: candidate.clearance,
    )


def intervals_at_y(segments: list[Segment], y: float) -> list[tuple[float, float]]:
    xs = x_crossings(segments, y)
    if len(xs) % 2 != 0:
        return []
    return list(zip(xs[0::2], xs[1::2]))


def opposing_sample(left: BoardRenderData, right: BoardRenderData, right_dx: float, right_dy: float, y: float) -> ClearanceSample | None:
    left_intervals = intervals_at_y(left.edge_segments, y)
    right_intervals = intervals_at_y(right.edge_segments, y - right_dy)
    if not left_intervals or not right_intervals:
        return None
    left_x = max(end for _, end in left_intervals)
    right_x = min(start for start, _ in right_intervals) + right_dx
    return ClearanceSample(y=y, left_x=left_x, right_x=right_x, clearance=right_x - left_x)


def scan_clearances(
    left: BoardRenderData,
    right: BoardRenderData,
    right_dx: float,
    right_dy: float,
    step_mm: float,
) -> list[ClearanceSample]:
    y_min = max(left.bounds[1], right.bounds[1] + right_dy)
    y_max = min(left.bounds[3], right.bounds[3] + right_dy)
    samples: list[ClearanceSample] = []
    y = y_min + step_mm / 2.0
    while y < y_max:
        sample = opposing_sample(left, right, right_dx, right_dy, y)
        if sample is not None:
            samples.append(sample)
        y += step_mm
    if not samples:
        raise RuntimeError("No opposing Edge.Cuts samples found")
    return samples


def compute_interlocked_dx(left: BoardRenderData, right: BoardRenderData, right_dy: float, clearance_mm: float) -> float:
    base_samples = scan_clearances(left, right, 0.0, right_dy, SCAN_STEP_MM)
    base_min = min(sample.clearance for sample in base_samples)
    return clearance_mm - base_min


def shifted_bounds(bounds: tuple[float, float, float, float], dx: float, dy: float) -> tuple[float, float, float, float]:
    return bounds[0] + dx, bounds[1] + dy, bounds[2] + dx, bounds[3] + dy


def keycap_rect_by_label(
    data: BoardRenderData,
    label: str,
    *,
    dx: float = 0.0,
    dy: float = 0.0,
) -> tuple[float, float, float, float]:
    matches: list[tuple[float, float, float, float]] = []
    for idx, key in enumerate(data.keys, start=1):
        if key.label != label:
            continue
        x, y = data.switch_centers[idx]
        x += dx
        y += dy
        w = key.w_u * UNIT
        matches.append((x - w / 2.0 + 0.5, y - UNIT / 2.0 + 0.5, x + w / 2.0 - 0.5, y + UNIT / 2.0 - 0.5))
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one key label {label!r} on {data.side}, found {len(matches)}")
    return matches[0]


def key_horizontal_clearance(
    left: BoardRenderData,
    right: BoardRenderData,
    right_dx: float,
    right_dy: float,
    right_label: str,
) -> KeyHorizontalClearance:
    left_rect = keycap_rect_by_label(left, "6")
    right_rect = keycap_rect_by_label(right, right_label, dx=right_dx, dy=right_dy)
    y = (left_rect[3] + right_rect[1]) / 2.0
    return KeyHorizontalClearance(
        left_label="6",
        right_label=right_label,
        start=(left_rect[2], y),
        end=(right_rect[0], y),
        clearance=right_rect[0] - left_rect[2],
    )


def seam_key_clearances(
    left: BoardRenderData,
    right: BoardRenderData,
    right_dx: float,
    right_dy: float,
) -> list[SeamKeyClearance]:
    clearances: list[SeamKeyClearance] = []
    rows = sorted({key.row for key in left.keys} & {key.row for key in right.keys})
    for row in rows:
        left_candidates = [
            (index, key)
            for index, key in enumerate(left.keys, start=1)
            if key.row == row
        ]
        right_candidates = [
            (index, key)
            for index, key in enumerate(right.keys, start=1)
            if key.row == row
        ]
        left_index, left_key = max(
            left_candidates,
            key=lambda item: left.switch_centers[item[0]][0] + item[1].w_u * UNIT / 2.0,
        )
        right_index, right_key = min(
            right_candidates,
            key=lambda item: right.switch_centers[item[0]][0] - item[1].w_u * UNIT / 2.0,
        )
        left_center = left.switch_centers[left_index]
        right_local_center = right.switch_centers[right_index]
        right_center = (right_local_center[0] + right_dx, right_local_center[1] + right_dy)
        y = (left_center[1] + right_center[1]) / 2.0
        edge_sample = opposing_sample(left, right, right_dx, right_dy, y)
        if edge_sample is None:
            raise RuntimeError(f"No joined Edge.Cuts interval at seam row {row}")
        left_cap_width = left_key.w_u * UNIT - 1.0
        right_cap_width = right_key.w_u * UNIT - 1.0
        left_cap_edge = left_center[0] + left_cap_width / 2.0
        right_cap_edge = right_center[0] - right_cap_width / 2.0
        clearances.append(
            SeamKeyClearance(
                row=row,
                left_label=left_key.label,
                right_label=right_key.label,
                left_cap_width_mm=left_cap_width,
                right_cap_width_mm=right_cap_width,
                center_pitch_mm=right_center[0] - left_center[0],
                cap_gap_mm=right_cap_edge - left_cap_edge,
                left_center_to_pcb_edge_mm=edge_sample.left_x - left_center[0],
                right_center_to_pcb_edge_mm=right_center[0] - edge_sample.right_x,
                pcb_gap_mm=edge_sample.clearance,
                start=(left_cap_edge, y),
                end=(right_cap_edge, y),
            )
        )
    return clearances


def build_context(
    repo: Path,
    clearance_mm: float,
    scale: float,
    placement_mode: str,
    *,
    variant: str = "x3",
) -> RenderContext:
    if variant == "x3-v2":
        board_root = repo / "hardware" / "kicad" / "draft" / "x3-v2"
        left_path = board_root / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb"
        right_path = board_root / "kc2_right-x3-v2" / "kc2_right-x3-v2.kicad_pcb"
        left_keys = make_left_keys_x3_v2()
        right_keys = make_right_keys_x3_v2()
        right_seam_label = "7"
        service_references = X3_V2_SERVICE_REFERENCES
    elif variant == "x3":
        left_path = repo / "hardware" / "kicad" / "kc2_left" / "kc2_left.kicad_pcb"
        right_path = repo / "hardware" / "kicad" / "kc2_right" / "kc2_right.kicad_pcb"
        left_keys = make_left_keys_no_stab()
        right_keys = make_right_keys_no_stab()
        right_seam_label = "Y"
        service_references = ()
    else:
        raise ValueError(f"Unknown variant: {variant}")
    left = load_board_data(
        "left",
        left_path,
        left_keys,
        service_references,
    )
    right = load_board_data(
        "right",
        right_path,
        right_keys,
        service_references,
    )
    if variant == "x3-v2":
        for data, count in ((left, 8), (right, 9)):
            expected_mounts = {f"MH{index}" for index in range(1, count + 1)}
            actual_mounts = {mount.reference for mount in data.mounts}
            if actual_mounts != expected_mounts:
                missing = sorted(expected_mounts - actual_mounts)
                extra = sorted(actual_mounts - expected_mounts)
                raise RuntimeError(
                    f"{data.side} mounting references mismatch: missing={missing}, extra={extra}"
                )

    right_dy = left.bounds[1] - right.bounds[1]
    if placement_mode == "bounding-gap":
        right_dx = left.bounds[2] + clearance_mm - right.bounds[0]
    elif placement_mode == "interlock-clearance":
        right_dx = compute_interlocked_dx(left, right, right_dy, clearance_mm)
    elif placement_mode == "key-pitch":
        left_six = keycap_rect_by_label(left, "6")
        right_seam = keycap_rect_by_label(right, right_seam_label)
        left_center_x = (left_six[0] + left_six[2]) / 2.0
        right_center_x = (right_seam[0] + right_seam[2]) / 2.0
        joined_pitch = X3_V2_JOIN_CENTER_PITCH if variant == "x3-v2" else UNIT
        right_dx = left_center_x + joined_pitch - right_center_x
    else:
        raise ValueError(f"Unknown placement mode: {placement_mode}")

    joined_right_bounds = shifted_bounds(right.bounds, right_dx, right_dy)
    bounds = (
        min(left.bounds[0], joined_right_bounds[0]),
        min(left.bounds[1], joined_right_bounds[1]),
        max(left.bounds[2], joined_right_bounds[2]),
        max(left.bounds[3], joined_right_bounds[3]),
    )
    fine_samples = scan_clearances(left, right, right_dx, right_dy, SCAN_STEP_MM)
    min_sample = min(fine_samples, key=lambda sample: sample.clearance)
    exact_clearance = minimum_segment_clearance(
        left.edge_segments,
        right.edge_segments,
        right_dx,
        right_dy,
    )
    corridor_samples = scan_clearances(left, right, right_dx, right_dy, CORRIDOR_STEP_MM)
    measurement = opposing_sample(left, right, right_dx, right_dy, TY_ROW_CENTER_Y_MM) or min_sample
    seam_clearances = seam_key_clearances(left, right, right_dx, right_dy)
    if variant == "x3-v2":
        first_seam = seam_clearances[0]
        key_clearance = KeyHorizontalClearance(
            left_label=first_seam.left_label,
            right_label=first_seam.right_label,
            start=first_seam.start,
            end=first_seam.end,
            clearance=first_seam.cap_gap_mm,
        )
    else:
        key_clearance = key_horizontal_clearance(
            left,
            right,
            right_dx,
            right_dy,
            right_seam_label,
        )
    outline_x_range_nesting = max(0.0, left.bounds[2] - joined_right_bounds[0])

    return RenderContext(
        variant=variant,
        scale=scale,
        clearance_mm=clearance_mm,
        placement_mode=placement_mode,
        left=left,
        right=right,
        right_dx=right_dx,
        right_dy=right_dy,
        bounds=bounds,
        min_edge_clearance_mm=exact_clearance.clearance,
        min_clearance_y=(exact_clearance.left_point[1] + exact_clearance.right_point[1]) / 2.0,
        measurement=measurement,
        clearance_samples=corridor_samples,
        key_horizontal_clearance=key_clearance,
        seam_key_clearances=seam_clearances,
        outline_x_range_nesting_mm=outline_x_range_nesting,
    )


def shift_point(ctx: RenderContext, side: str, point: tuple[float, float]) -> tuple[float, float]:
    if side == "right":
        return point[0] + ctx.right_dx, point[1] + ctx.right_dy
    return point


def make_transform(
    ctx: RenderContext,
    *,
    crop_min_x: float | None = None,
    crop_width_mm: float | None = None,
) -> tuple[Callable[[tuple[float, float]], tuple[float, float]], int, int]:
    min_x, min_y, max_x, max_y = ctx.bounds
    if crop_min_x is None:
        origin_x = min_x
        width_mm = max_x - min_x
        margin_x = FULL_MARGIN_PX
    else:
        origin_x = crop_min_x
        width_mm = crop_width_mm if crop_width_mm is not None else ZOOM_WIDTH_MM
        margin_x = 0.0
    margin_y = FULL_MARGIN_PX
    height_mm = max_y - min_y
    width_px = int(round(width_mm * ctx.scale + margin_x * 2.0))
    height_px = int(round(height_mm * ctx.scale + margin_y * 2.0))

    def tx(point: tuple[float, float]) -> tuple[float, float]:
        return (
            (point[0] - origin_x) * ctx.scale + margin_x,
            (point[1] - min_y) * ctx.scale + margin_y,
        )

    return tx, width_px, height_px


def key_records(data: BoardRenderData, ctx: RenderContext) -> list[tuple[str, tuple[float, float], float]]:
    records: list[tuple[str, tuple[float, float], float]] = []
    for idx, key in enumerate(data.keys, start=1):
        center = data.switch_centers[idx]
        records.append((key.label, shift_point(ctx, data.side, center), key.w_u))
    return records


def shifted_rect(ctx: RenderContext, side: str, rect: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x1, y1 = shift_point(ctx, side, (rect[0], rect[1]))
    x2, y2 = shift_point(ctx, side, (rect[2], rect[3]))
    return x1, y1, x2, y2


def shifted_service_component(
    ctx: RenderContext,
    side: str,
    component: ServiceRenderData,
) -> tuple[tuple[float, float], tuple[float, float, float, float]]:
    return (
        shift_point(ctx, side, component.center),
        shifted_rect(ctx, side, component.bounds),
    )


def zoom_center_x(ctx: RenderContext) -> float:
    return (ctx.measurement.left_x + ctx.measurement.right_x) / 2.0


def clearance_polygon(ctx: RenderContext) -> list[tuple[float, float]]:
    left_side = [(sample.left_x, sample.y) for sample in ctx.clearance_samples]
    right_side = [(sample.right_x, sample.y) for sample in reversed(ctx.clearance_samples)]
    return left_side + right_side


def key_horizontal_clearance_label(ctx: RenderContext) -> str:
    gap = ctx.key_horizontal_clearance
    return f"{gap.left_label}-{gap.right_label} X {gap.clearance:.1f} mm"


def seam_clearance_summary(ctx: RenderContext) -> str:
    pairs = "/".join(
        f"{clearance.left_label}-{clearance.right_label}"
        for clearance in ctx.seam_key_clearances
    )
    minimum = min(clearance.cap_gap_mm for clearance in ctx.seam_key_clearances)
    maximum = max(clearance.cap_gap_mm for clearance in ctx.seam_key_clearances)
    if abs(maximum - minimum) <= 0.001:
        return f"{len(ctx.seam_key_clearances)} actual cap pairs {pairs} = {minimum:.1f} mm"
    return f"{len(ctx.seam_key_clearances)} actual cap pairs {pairs} = {minimum:.1f}-{maximum:.1f} mm"


def render_svg(ctx: RenderContext, path: Path, *, zoom: bool) -> tuple[int, int]:
    if zoom:
        center = zoom_center_x(ctx)
        tx, width, height = make_transform(ctx, crop_min_x=center - ZOOM_WIDTH_MM / 2.0, crop_width_mm=ZOOM_WIDTH_MM)
    else:
        tx, width, height = make_transform(ctx)

    def line(p1: tuple[float, float], p2: tuple[float, float], attrs: str) -> str:
        x1, y1 = tx(p1)
        x2, y2 = tx(p2)
        return f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" {attrs}/>'

    def rect(rect_mm: tuple[float, float, float, float], attrs: str) -> str:
        x1, y1 = tx((rect_mm[0], rect_mm[1]))
        x2, y2 = tx((rect_mm[2], rect_mm[3]))
        return f'<rect x="{x1:.2f}" y="{y1:.2f}" width="{x2 - x1:.2f}" height="{y2 - y1:.2f}" {attrs}/>'

    polygon_points = " ".join(f"{tx(point)[0]:.2f},{tx(point)[1]:.2f}" for point in clearance_polygon(ctx))
    measurement_y = ctx.measurement.y
    measurement_px_width = ctx.measurement.clearance * ctx.scale
    title_width = max(0, width - 16)
    if zoom:
        summary_text = (
            f"Exact PCB min {ctx.min_edge_clearance_mm:.2f} mm; "
            f"row-center {ctx.measurement.clearance:.2f} mm."
        )
        corridor_text = f"Empty PCB corridor; {seam_clearance_summary(ctx)}."
    else:
        summary_text = (
            f"Scale: {ctx.scale:g} px/mm. Min Edge.Cuts clearance: "
            f"{ctx.min_edge_clearance_mm:.2f} mm. Row-center PCB gap: "
            f"{ctx.measurement.clearance:.2f} mm. Outline X-range nesting: "
            f"{ctx.outline_x_range_nesting_mm:.2f} mm."
        )
        corridor_text = f"Empty PCB clearance corridor (salmon); {seam_clearance_summary(ctx)}."
    header_lines = [
        '<rect x="8" y="8" width="{:.0f}" height="66" fill="#f7f5ee" fill-opacity="0.98" stroke="none"/>'.format(title_width),
        f'<text x="16" y="24" font-family="Arial" font-size="15" fill="#222">KC2 {html.escape(ctx.variant.upper())} joined top view, board-coordinate composite</text>',
        f'<text x="16" y="44" font-family="Arial" font-size="11" fill="#555">{html.escape(summary_text)}</text>',
        f'<text x="16" y="61" font-family="Arial" font-size="11" fill="#7a2f25">{html.escape(corridor_text)}</text>',
    ]
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f5ee"/>',
        (
            f'<g id="joined-clearance" data-placement-mode="{ctx.placement_mode}" '
            f'data-clearance-mm="{ctx.min_edge_clearance_mm:.4f}" '
            f'data-clearance-width-px="{ctx.min_edge_clearance_mm * ctx.scale:.2f}" '
            f'data-measurement-width-px="{measurement_px_width:.2f}" '
            f'data-key-horizontal-clearance-mm="{ctx.key_horizontal_clearance.clearance:.4f}" '
            f'data-outline-x-range-nesting-mm="{ctx.outline_x_range_nesting_mm:.4f}">'
        ),
        f'<polygon points="{polygon_points}" fill="#f6b8a9" fill-opacity="0.55" stroke="none"/>',
        "</g>",
        f'<g id="seam-key-clearances" data-seam-pair-count="{len(ctx.seam_key_clearances)}">',
    ]
    for clearance in ctx.seam_key_clearances:
        pair = html.escape(f"{clearance.left_label}-{clearance.right_label}")
        lines.append(
            f'<g data-row="{clearance.row}" data-pair="{pair}" '
            f'data-left-cap-width-mm="{clearance.left_cap_width_mm:.4f}" '
            f'data-right-cap-width-mm="{clearance.right_cap_width_mm:.4f}" '
            f'data-center-pitch-mm="{clearance.center_pitch_mm:.4f}" '
            f'data-cap-gap-mm="{clearance.cap_gap_mm:.4f}" '
            f'data-left-center-to-pcb-edge-mm="{clearance.left_center_to_pcb_edge_mm:.4f}" '
            f'data-right-center-to-pcb-edge-mm="{clearance.right_center_to_pcb_edge_mm:.4f}" '
            f'data-pcb-gap-mm="{clearance.pcb_gap_mm:.4f}"/>'
        )
    lines.append("</g>")
    lines.append(line((ctx.measurement.left_x, measurement_y), (ctx.measurement.right_x, measurement_y), 'stroke="#d33b2f" stroke-width="2"'))
    lines.append(line((ctx.measurement.left_x, measurement_y - 1.2), (ctx.measurement.left_x, measurement_y + 1.2), 'stroke="#d33b2f" stroke-width="2"'))
    lines.append(line((ctx.measurement.right_x, measurement_y - 1.2), (ctx.measurement.right_x, measurement_y + 1.2), 'stroke="#d33b2f" stroke-width="2"'))
    for data, color in ((ctx.left, "#102018"), (ctx.right, "#101b2a")):
        for start, end in data.edge_segments:
            lines.append(line(shift_point(ctx, data.side, start), shift_point(ctx, data.side, end), f'stroke="{color}" stroke-width="2" fill="none"'))

    for data, fill, stroke in ((ctx.left, "#e9fff4", "#2a8d66"), (ctx.right, "#eef5ff", "#467cc0")):
        for label, center, width_u in key_records(data, ctx):
            x, y = center
            w = width_u * UNIT
            key_rect = (x - w / 2.0 + 0.5, y - UNIT / 2.0 + 0.5, x + w / 2.0 - 0.5, y + UNIT / 2.0 - 0.5)
            lines.append(rect(key_rect, f'rx="2" ry="2" fill="{fill}" stroke="{stroke}" stroke-width="1"'))
            cx, cy = tx(center)
            lines.append(f'<text x="{cx:.2f}" y="{cy + 3.46:.2f}" text-anchor="middle" font-family="Arial" font-size="10" fill="#101010">{html.escape(label)}</text>')
        ctrl = shifted_rect(ctx, data.side, data.controller_bounds)
        lines.append(rect(ctrl, 'fill="none" stroke="#252525" stroke-width="1.5" stroke-dasharray="4 3"'))
        cx, cy = tx(((ctrl[0] + ctrl[2]) / 2.0, ctrl[1] - 0.8))
        lines.append(f'<text x="{cx:.2f}" y="{cy:.2f}" text-anchor="middle" font-family="Arial" font-size="9" fill="#222">U1</text>')
        lines.append(
            f'<g id="{data.side}-service-components" data-service-reference-count="{len(data.service_components)}">'
        )
        for component in data.service_components:
            joined_center, joined_bounds = shifted_service_component(ctx, data.side, component)
            fill_color, stroke_color = SERVICE_STYLES[component.reference]
            lines.append(
                f'<g class="service-component" data-side="{data.side}" '
                f'data-reference="{component.reference}" '
                f'data-board-center-x-mm="{component.center[0]:.4f}" '
                f'data-board-center-y-mm="{component.center[1]:.4f}" '
                f'data-joined-center-x-mm="{joined_center[0]:.4f}" '
                f'data-joined-center-y-mm="{joined_center[1]:.4f}" '
                f'data-board-bounds-mm="{",".join(f"{value:.4f}" for value in component.bounds)}" '
                f'data-joined-bounds-mm="{",".join(f"{value:.4f}" for value in joined_bounds)}" '
                f'data-rotation-degrees="{component.rotation_degrees:.4f}">'
            )
            lines.append(
                rect(
                    joined_bounds,
                    f'rx="2" ry="2" fill="{fill_color}" fill-opacity="0.82" '
                    f'stroke="{stroke_color}" stroke-width="1.4"',
                )
            )
            service_x, service_y = tx(joined_center)
            lines.append(
                f'<text x="{service_x:.2f}" y="{service_y + 3.0:.2f}" text-anchor="middle" '
                f'font-family="Arial" font-size="9" font-weight="bold" fill="{stroke_color}">'
                f'{component.reference}</text>'
            )
            lines.append("</g>")
        lines.append("</g>")
        lines.append(
            f'<g id="{data.side}-battery-terminal-legends" '
            f'data-terminal-legend-count="{len(data.battery_terminal_legends)}">'
        )
        for legend in data.battery_terminal_legends:
            joined_center = shift_point(ctx, data.side, legend.center)
            legend_x, legend_y = tx(joined_center)
            lines.append(
                f'<g class="battery-terminal-legend" data-side="{data.side}" '
                f'data-text="{html.escape(legend.text)}" '
                f'data-board-center-x-mm="{legend.center[0]:.4f}" '
                f'data-board-center-y-mm="{legend.center[1]:.4f}" '
                f'data-joined-center-x-mm="{joined_center[0]:.4f}" '
                f'data-joined-center-y-mm="{joined_center[1]:.4f}">'
            )
            lines.append(
                f'<text x="{legend_x:.2f}" y="{legend_y + 2.4:.2f}" text-anchor="middle" '
                f'font-family="Arial" font-size="7" font-weight="bold" fill="#5f2e00">'
                f'{html.escape(legend.text)}</text>'
            )
            lines.append("</g>")
        lines.append("</g>")
        lines.append(
            f'<g id="{data.side}-mounting-holes" data-mount-reference-count="{len(data.mounts)}">'
        )
        for mount in data.mounts:
            joined_center = shift_point(ctx, data.side, mount.center)
            mx, my = tx(joined_center)
            lines.append(
                f'<g class="mounting-hole" data-side="{data.side}" '
                f'data-reference="{mount.reference}" '
                f'data-board-center-x-mm="{mount.center[0]:.4f}" '
                f'data-board-center-y-mm="{mount.center[1]:.4f}" '
                f'data-joined-center-x-mm="{joined_center[0]:.4f}" '
                f'data-joined-center-y-mm="{joined_center[1]:.4f}">'
            )
            lines.append(
                f'<circle cx="{mx:.2f}" cy="{my:.2f}" r="7" fill="white" '
                f'fill-opacity="0.94" stroke="#555" stroke-width="1"/>'
            )
            lines.append(
                f'<text x="{mx:.2f}" y="{my + 2.7:.2f}" text-anchor="middle" '
                f'font-family="Arial" font-size="7" font-weight="bold" fill="#333">'
                f'{html.escape(mount.reference)}</text>'
            )
            lines.append("</g>")
        lines.append("</g>")

    gap = ctx.key_horizontal_clearance
    gap_label = html.escape(key_horizontal_clearance_label(ctx))
    lines.append(
        (
            f'<g id="key-horizontal-clearance" data-key-horizontal-clearance-mm="{gap.clearance:.4f}" '
            f'data-left-key="{html.escape(gap.left_label)}" data-right-key="{html.escape(gap.right_label)}">'
        )
    )
    lines.append(line(gap.start, gap.end, 'stroke="#1c5fb8" stroke-width="2.4"'))
    for point, direction in ((gap.start, 1.0), (gap.end, -1.0)):
        x, y = point
        lines.append(line((x, y), (x + direction * 1.2, y - 0.8), 'stroke="#1c5fb8" stroke-width="2.4"'))
        lines.append(line((x, y), (x + direction * 1.2, y + 0.8), 'stroke="#1c5fb8" stroke-width="2.4"'))
    gx, gy = tx(((gap.start[0] + gap.end[0]) / 2.0, gap.start[1]))
    lines.append(
        f'<text x="{gx:.2f}" y="{gy - 8:.2f}" text-anchor="middle" font-family="Arial" font-size="10" fill="#123e7d">{gap_label}</text>'
    )
    lines.append("</g>")

    lines.extend(header_lines)
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return width, height


def png_dimensions(path: Path) -> tuple[int, int]:
    payload = path.read_bytes()
    if len(payload) < 24 or payload[:8] != b"\x89PNG\r\n\x1a\n" or payload[12:16] != b"IHDR":
        raise RuntimeError(f"browser did not create a valid PNG: {path}")
    return struct.unpack(">II", payload[16:24])


def find_headless_browser() -> Path | None:
    override = os.environ.get("KC2_HEADLESS_BROWSER")
    candidates = [
        Path(override) if override else None,
        *(Path(found) if found else None for found in (
            shutil.which("msedge.exe"),
            shutil.which("msedge"),
            shutil.which("microsoft-edge"),
            shutil.which("google-chrome"),
            shutil.which("chromium"),
        )),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ]
    return next((candidate for candidate in candidates if candidate and candidate.is_file()), None)


def render_png_with_browser(ctx: RenderContext, path: Path, *, zoom: bool) -> tuple[int, int]:
    browser = find_headless_browser()
    if browser is None:
        raise RuntimeError(
            "PNG rendering needs Pillow or a Chromium-family browser; "
            "install Pillow or set KC2_HEADLESS_BROWSER to the browser executable"
        )

    svg_path = path.with_suffix(".svg")
    width, height = render_svg(ctx, svg_path, zoom=zoom)
    profile_dir = Path(tempfile.mkdtemp(prefix="kc2-render-edge-"))
    try:
        completed = subprocess.run(
            [
                str(browser),
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-device-scale-factor=1",
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={profile_dir}",
                f"--screenshot={path.resolve()}",
                f"--window-size={width},{height}",
                svg_path.resolve().as_uri(),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if completed.returncode != 0:
            detail = (completed.stdout + completed.stderr).strip()
            raise RuntimeError(f"headless browser PNG rendering failed: {detail}")
        actual_size = png_dimensions(path)
        if actual_size != (width, height):
            raise RuntimeError(
                f"headless browser PNG size {actual_size} does not match SVG viewport {(width, height)}"
            )
        return actual_size
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)


def render_png(ctx: RenderContext, path: Path, *, zoom: bool) -> tuple[int, int]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ModuleNotFoundError as exc:
        if not (exc.name or "").startswith("PIL"):
            raise
        return render_png_with_browser(ctx, path, zoom=zoom)

    if zoom:
        center = zoom_center_x(ctx)
        tx, width, height = make_transform(ctx, crop_min_x=center - ZOOM_WIDTH_MM / 2.0, crop_width_mm=ZOOM_WIDTH_MM)
    else:
        tx, width, height = make_transform(ctx)
    img = Image.new("RGB", (width, height), "#f7f5ee")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    draw.polygon([tx(point) for point in clearance_polygon(ctx)], fill="#f6d2ca")
    title_width = max(0, width - 8)
    if zoom:
        summary_text = (
            f"Exact PCB min {ctx.min_edge_clearance_mm:.2f} mm; "
            f"row-center {ctx.measurement.clearance:.2f} mm."
        )
        corridor_text = f"Empty PCB corridor; {seam_clearance_summary(ctx)}."
    else:
        summary_text = (
            f"Scale: {ctx.scale:g} px/mm. Min Edge.Cuts clearance: "
            f"{ctx.min_edge_clearance_mm:.2f} mm. Row-center PCB gap: "
            f"{ctx.measurement.clearance:.2f} mm. Outline X-range nesting: "
            f"{ctx.outline_x_range_nesting_mm:.2f} mm."
        )
        corridor_text = f"Empty PCB clearance corridor (salmon); {seam_clearance_summary(ctx)}."
    p1 = tx((ctx.measurement.left_x, ctx.measurement.y))
    p2 = tx((ctx.measurement.right_x, ctx.measurement.y))
    draw.line((p1, p2), fill="#d33b2f", width=2)
    for x, y in (p1, p2):
        draw.line((x, y - 6, x, y + 6), fill="#d33b2f", width=2)
    for data, color in ((ctx.left, "#102018"), (ctx.right, "#101b2a")):
        for start, end in data.edge_segments:
            p1_edge = tx(shift_point(ctx, data.side, start))
            p2_edge = tx(shift_point(ctx, data.side, end))
            draw.line((p1_edge, p2_edge), fill=color, width=2)

    for data, fill, stroke in ((ctx.left, "#e9fff4", "#2a8d66"), (ctx.right, "#eef5ff", "#467cc0")):
        for label, center, width_u in key_records(data, ctx):
            x, y = center
            w = width_u * UNIT
            x1, y1 = tx((x - w / 2.0 + 0.5, y - UNIT / 2.0 + 0.5))
            x2, y2 = tx((x + w / 2.0 - 0.5, y + UNIT / 2.0 - 0.5))
            draw.rounded_rectangle((x1, y1, x2, y2), radius=2, fill=fill, outline=stroke, width=1)
            cx, cy = tx(center)
            draw.text((cx, cy), label, fill="#101010", font=font, anchor="mm")
        ctrl = shifted_rect(ctx, data.side, data.controller_bounds)
        x1, y1 = tx((ctrl[0], ctrl[1]))
        x2, y2 = tx((ctrl[2], ctrl[3]))
        draw.rectangle((x1, y1, x2, y2), outline="#252525", width=1)
        draw.text(((x1 + x2) / 2.0, y1 - 7), "U1", fill="#222222", font=font, anchor="mm")
        for component in data.service_components:
            joined_center, joined_bounds = shifted_service_component(ctx, data.side, component)
            fill_color, stroke_color = SERVICE_STYLES[component.reference]
            x1, y1 = tx((joined_bounds[0], joined_bounds[1]))
            x2, y2 = tx((joined_bounds[2], joined_bounds[3]))
            draw.rounded_rectangle(
                (x1, y1, x2, y2),
                radius=2,
                fill=fill_color,
                outline=stroke_color,
                width=1,
            )
            service_x, service_y = tx(joined_center)
            draw.text(
                (service_x, service_y),
                component.reference,
                fill=stroke_color,
                font=font,
                anchor="mm",
            )
        for legend in data.battery_terminal_legends:
            legend_x, legend_y = tx(shift_point(ctx, data.side, legend.center))
            draw.text(
                (legend_x, legend_y),
                legend.text,
                fill="#5f2e00",
                font=font,
                anchor="mm",
            )
        for mount in data.mounts:
            mx, my = tx(shift_point(ctx, data.side, mount.center))
            draw.ellipse((mx - 7, my - 7, mx + 7, my + 7), fill="white", outline="#555555", width=1)
            draw.text((mx, my), mount.reference, fill="#333333", font=font, anchor="mm")

    gap = ctx.key_horizontal_clearance
    p1 = tx(gap.start)
    p2 = tx(gap.end)
    gap_color = "#1c5fb8"
    draw.line((p1, p2), fill=gap_color, width=2)
    for point, direction in ((p1, 1.0), (p2, -1.0)):
        x, y = point
        draw.line((x, y, x + direction * 6, y - 4), fill=gap_color, width=2)
        draw.line((x, y, x + direction * 6, y + 4), fill=gap_color, width=2)
    label = key_horizontal_clearance_label(ctx)
    label_x = (p1[0] + p2[0]) / 2.0
    label_y = p1[1] - 10
    bbox = draw.textbbox((label_x, label_y), label, font=font, anchor="mm")
    draw.rectangle((bbox[0] - 2, bbox[1] - 1, bbox[2] + 2, bbox[3] + 1), fill="#f7f5ee")
    draw.text((label_x, label_y), label, fill="#123e7d", font=font, anchor="mm")

    draw.rectangle((8, 8, title_width, 74), fill="#f7f5ee")
    draw.text((16, 14), f"KC2 {ctx.variant.upper()} joined top view, board-coordinate composite", fill="#222222", font=font)
    draw.text((16, 34), summary_text, fill="#555555", font=font)
    draw.text((16, 51), corridor_text, fill="#7a2f25", font=font)

    img.save(path)
    return width, height


def raw_sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def render_reference_counts(ctx: RenderContext) -> tuple[dict[str, dict[str, int]], dict[str, int]]:
    service_counts = {
        data.side: {
            reference: sum(
                component.reference == reference for component in data.service_components
            )
            for reference in X3_V2_SERVICE_REFERENCES
        }
        for data in (ctx.left, ctx.right)
    }
    mount_counts = {data.side: len(data.mounts) for data in (ctx.left, ctx.right)}
    return service_counts, mount_counts


def battery_terminal_legend_counts(ctx: RenderContext) -> dict[str, dict[str, int]]:
    return {
        data.side: {
            text: sum(legend.text == text for legend in data.battery_terminal_legends)
            for text in X3_V2_BATTERY_TERMINAL_LEGENDS
        }
        for data in (ctx.left, ctx.right)
    }


def mount_centers_mm(ctx: RenderContext) -> dict[str, dict[str, list[float]]]:
    return {
        data.side: {
            mount.reference: [round(mount.center[0], 4), round(mount.center[1], 4)]
            for mount in data.mounts
        }
        for data in (ctx.left, ctx.right)
    }


def write_x3_v2_render_manifest(
    ctx: RenderContext,
    output_records: dict[str, dict[str, object]],
    output_dir: Path,
) -> Path:
    if ctx.variant != "x3-v2":
        raise ValueError("render evidence manifest is defined only for x3-v2")
    service_counts, mount_counts = render_reference_counts(ctx)
    terminal_legend_counts = battery_terminal_legend_counts(ctx)
    source_boards = {
        data.side: {
            "path": _repo_relative(data.source_path),
            "canonical_sha256": sha256_file(data.source_path),
        }
        for data in (ctx.left, ctx.right)
    }
    manifest = {
        "schema": "kc2-x3-v2-render-evidence-v1",
        "requirement_ids": ["CON-ARCH-006", "CON-ARCH-007"],
        "variant": "x3-v2",
        "hash_policy": HASH_POLICY,
        "renderer": {
            "path": _repo_relative(Path(__file__)),
            "canonical_sha256": sha256_file(Path(__file__)),
        },
        "render_parameters": {
            "clearance_mm": ctx.clearance_mm,
            "scale_px_per_mm": ctx.scale,
            "placement_mode": ctx.placement_mode,
            "full_margin_px": FULL_MARGIN_PX,
            "zoom_width_mm": ZOOM_WIDTH_MM,
        },
        "source_boards": source_boards,
        "service_reference_counts": service_counts,
        "mount_reference_counts": mount_counts,
        "mount_centers_mm": mount_centers_mm(ctx),
        "battery_terminal_legend_counts": terminal_legend_counts,
        "semantic_contract": (
            "SVG service-component, battery-terminal-legend, and mounting-hole groups are "
            "recomputed from exact board references, positions, footprint bounds, rotations, "
            "visible F.Silkscreen B+/B-/GND text, and joined transforms; PNGs "
            "must regenerate byte-identically from the same RenderContext."
        ),
        "outputs": output_records,
    }
    manifest_path = output_dir / "kc2_x3_v2_render_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Render KC2 X3 joined left/right board-coordinate composite.")
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--variant", choices=("x3", "x3-v2"), default="x3")
    parser.add_argument("--clearance-mm", "--gap-mm", dest="clearance_mm", type=float, default=DEFAULT_CLEARANCE_MM)
    parser.add_argument(
        "--placement-mode",
        choices=("interlock-clearance", "bounding-gap", "key-pitch"),
        default=None,
    )
    parser.add_argument("--scale", type=float, default=DEFAULT_SCALE)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--svg-only", action="store_true")
    args = parser.parse_args()

    placement_mode = args.placement_mode or ("key-pitch" if args.variant == "x3-v2" else "interlock-clearance")
    ctx = build_context(
        args.repo.resolve(),
        args.clearance_mm,
        args.scale,
        placement_mode,
        variant=args.variant,
    )
    output_dir = args.output_dir or (
        ROOT / "hardware" / "kicad" / "draft" / "x3-v2" / "renders"
        if args.variant == "x3-v2"
        else ROOT / "hardware" / "kicad" / "renders"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = "kc2_x3_v2" if args.variant == "x3-v2" else "kc2"
    outputs = [
        ("joined_top_svg", output_dir / f"{stem}_joined_top.svg", False, render_svg),
        ("join_seam_zoom_svg", output_dir / f"{stem}_join_seam_zoom.svg", True, render_svg),
    ]
    if not args.svg_only:
        outputs.extend(
            [
                ("joined_top_png", output_dir / f"{stem}_joined_top.png", False, render_png),
                ("join_seam_zoom_png", output_dir / f"{stem}_join_seam_zoom.png", True, render_png),
            ]
        )
    dimensions: dict[str, tuple[int, int]] = {}
    repeat_raw_hashes: dict[str, str] = {}
    repeat_canonical_hashes: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="kc2-render-repeat-") as temporary:
        repeat_root = Path(temporary)
        for key, path, zoom, renderer in outputs:
            width, height = renderer(ctx, path, zoom=zoom)
            repeat_path = repeat_root / path.name
            repeat_width, repeat_height = renderer(ctx, repeat_path, zoom=zoom)
            if (repeat_width, repeat_height) != (width, height):
                raise RuntimeError(
                    f"{path.name} regenerated viewport {(repeat_width, repeat_height)} "
                    f"does not match {(width, height)}"
                )
            repeat_raw_hash = raw_sha256_file(repeat_path)
            if repeat_raw_hash != raw_sha256_file(path):
                raise RuntimeError(f"{path.name} is not byte-deterministic across two renders")
            dimensions[key] = (width, height)
            repeat_raw_hashes[key] = repeat_raw_hash
            repeat_canonical_hashes[key] = sha256_file(repeat_path)
            print(f"{path} {width}x{height}")

    if args.variant == "x3-v2" and not args.svg_only:
        service_counts, mount_counts = render_reference_counts(ctx)
        terminal_legend_counts = battery_terminal_legend_counts(ctx)
        output_records: dict[str, dict[str, object]] = {}
        for key, path, zoom, _renderer in outputs:
            width, height = dimensions[key]
            record: dict[str, object] = {
                "path": _repo_relative(path),
                "media_type": "image/svg+xml" if path.suffix == ".svg" else "image/png",
                "zoom": zoom,
                "width_px": width,
                "height_px": height,
                "deterministic_regeneration": True,
                "service_reference_counts": service_counts,
                "mount_reference_counts": mount_counts,
                "battery_terminal_legend_counts": terminal_legend_counts,
            }
            if path.suffix == ".svg":
                record.update(
                    {
                        "digest_mode": "canonical_text",
                        "canonical_sha256": sha256_file(path),
                        "regenerated_canonical_sha256": repeat_canonical_hashes[key],
                    }
                )
            else:
                record.update(
                    {
                        "digest_mode": "raw_binary",
                        "raw_sha256": raw_sha256_file(path),
                        "regenerated_raw_sha256": repeat_raw_hashes[key],
                    }
                )
            output_records[key] = record
        manifest_path = write_x3_v2_render_manifest(ctx, output_records, output_dir)
        print(f"{manifest_path} manifest")

    print(f"placement_mode={ctx.placement_mode}")
    print(f"target_clearance_mm={ctx.clearance_mm:.4f}")
    print(f"min_edge_clearance_mm={ctx.min_edge_clearance_mm:.4f}")
    print(f"min_clearance_y_mm={ctx.min_clearance_y:.4f}")
    print(f"measurement_y_mm={ctx.measurement.y:.4f}")
    print(f"measurement_clearance_mm={ctx.measurement.clearance:.4f}")
    print(f"key_horizontal_clearance_mm={ctx.key_horizontal_clearance.clearance:.4f}")
    for clearance in ctx.seam_key_clearances:
        print(
            f"seam_pair_row_{clearance.row}={clearance.left_label}-{clearance.right_label},"
            f"caps={clearance.left_cap_width_mm:.4f}/{clearance.right_cap_width_mm:.4f},"
            f"pitch={clearance.center_pitch_mm:.4f},gap={clearance.cap_gap_mm:.4f},"
            f"pcb_edges={clearance.left_center_to_pcb_edge_mm:.4f}/"
            f"{clearance.right_center_to_pcb_edge_mm:.4f},pcb_gap={clearance.pcb_gap_mm:.4f}"
        )
    print(f"outline_x_range_nesting_mm={ctx.outline_x_range_nesting_mm:.4f}")
    print(f"right_shift_dx_mm={ctx.right_dx:.4f}")
    print(f"right_shift_dy_mm={ctx.right_dy:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
