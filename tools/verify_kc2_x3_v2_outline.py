from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

from tools.generate_kc2_pcbs import (
    X3_V2_JOIN_CENTER_PITCH,
    X3_V2_JOIN_KEYCAP_GAP,
    X3_V2_MIN_JOINED_EDGE_CLEARANCE,
    X3_V2_ROW_CENTER_PCB_GAP,
)
from tools.render_kc2_x3_joined import (
    UNIT,
    BoardRenderData,
    build_context,
    intervals_at_y,
    x_crossings,
)


ROOT = Path(__file__).resolve().parents[1]
KEYCAP_EDGE_INSET_MM = 0.5
KEYCELL_EDGE_INSET_MM = 1.5
EXPECTED_CAP_RELATIVE_SETBACK_MM = KEYCELL_EDGE_INSET_MM - KEYCAP_EDGE_INSET_MM
EXPECTED_ONE_UNIT_JOIN_CENTER_TO_EDGE_MM = UNIT / 2.0 - KEYCELL_EDGE_INSET_MM
TOLERANCE_MM = 0.02
ONE_TO_ONE_TOLERANCE_MM = 0.05
PERIMETER_SAMPLE_STEP_MM = 0.05


def keycap_bounds(data: BoardRenderData, index: int) -> tuple[float, float, float, float]:
    key = data.keys[index - 1]
    cx, cy = data.switch_centers[index]
    half_width = key.w_u * UNIT / 2.0 - KEYCAP_EDGE_INSET_MM
    half_height = key.h_u * UNIT / 2.0 - KEYCAP_EDGE_INSET_MM
    return cx - half_width, cy - half_height, cx + half_width, cy + half_height


def interval_containing(
    intervals: list[tuple[float, float]],
    value: float,
) -> tuple[float, float]:
    for start, end in intervals:
        if start - TOLERANCE_MM <= value <= end + TOLERANCE_MM:
            return start, end
    raise RuntimeError(f"No board interval contains {value:.3f} mm")


def intervals_at_x(
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
    x: float,
) -> list[tuple[float, float]]:
    transposed = [((y1, x1), (y2, x2)) for (x1, y1), (x2, y2) in segments]
    crossings = x_crossings(transposed, x)
    if len(crossings) % 2:
        return []
    return list(zip(crossings[0::2], crossings[1::2]))


def analyze_board(data: BoardRenderData) -> tuple[dict[str, object], list[str]]:
    errors: list[str] = []
    outer_overhangs: list[float] = []
    outer_setbacks: list[float] = []
    join_setbacks: list[float] = []

    for row in range(5):
        indices = [index for index, key in enumerate(data.keys, start=1) if key.row == row]
        row_y = sum(data.switch_centers[index][1] for index in indices) / len(indices)
        cap_left = min(keycap_bounds(data, index)[0] for index in indices)
        cap_right = max(keycap_bounds(data, index)[2] for index in indices)
        interval = interval_containing(
            intervals_at_y(data.edge_segments, row_y),
            (cap_left + cap_right) / 2.0,
        )
        if data.side == "left":
            outer_overhang = max(0.0, cap_left - interval[0])
            outer_setback = interval[0] - cap_left
            join_setback = cap_right - interval[1]
        else:
            outer_overhang = max(0.0, interval[1] - cap_right)
            outer_setback = cap_right - interval[1]
            join_setback = interval[0] - cap_left
        outer_overhangs.append(outer_overhang)
        outer_setbacks.append(outer_setback)
        join_setbacks.append(join_setback)
        if outer_overhang > TOLERANCE_MM:
            errors.append(
                f"{data.side} row {row}: PCB outer edge exceeds keycap envelope by "
                f"{outer_overhang:.3f} mm"
            )
        if abs(outer_setback - EXPECTED_CAP_RELATIVE_SETBACK_MM) > TOLERANCE_MM:
            errors.append(
                f"{data.side} row {row}: actual outer cap-relative setback is "
                f"{outer_setback:.3f} mm, expected "
                f"{EXPECTED_CAP_RELATIVE_SETBACK_MM:.3f}+/-{TOLERANCE_MM:.3f} mm"
            )
        if abs(join_setback - EXPECTED_CAP_RELATIVE_SETBACK_MM) > TOLERANCE_MM:
            errors.append(
                f"{data.side} row {row}: actual mating-edge setback is {join_setback:.3f} mm, "
                f"expected {EXPECTED_CAP_RELATIVE_SETBACK_MM:.3f}+/-{TOLERANCE_MM:.3f} mm"
            )

    vertical_overhangs: list[float] = []
    top_bottom_setbacks: list[float] = []
    permitted_exceptions: list[dict[str, object]] = []
    controller_left, _controller_top, controller_right, _controller_bottom = data.controller_bounds
    for row, use_top in ((0, True), (4, False)):
        for index, key in enumerate(data.keys, start=1):
            if key.row != row:
                continue
            cx, cy = data.switch_centers[index]
            if use_top and controller_left - TOLERANCE_MM <= cx <= controller_right + TOLERANCE_MM:
                permitted_exceptions.append(
                    {
                        "edge": "top",
                        "key_index": index,
                        "key_label": key.label,
                        "clearance_driving_features": [
                            "U1 nice!nano socket",
                            "USB connector access",
                            "reset/service access",
                        ],
                        "controller_span_mm": [
                            round(controller_left, 4),
                            round(controller_right, 4),
                        ],
                    }
                )
                continue
            intervals = intervals_at_x(data.edge_segments, cx)
            if not intervals:
                errors.append(f"{data.side} {key.label}: no vertical Edge.Cuts interval")
                continue
            top, bottom = interval_containing(intervals, cy)
            cap = keycap_bounds(data, index)
            overhang = max(0.0, cap[1] - top) if use_top else max(0.0, bottom - cap[3])
            setback = top - cap[1] if use_top else cap[3] - bottom
            vertical_overhangs.append(overhang)
            top_bottom_setbacks.append(setback)
            if overhang > TOLERANCE_MM:
                edge_name = "top" if use_top else "bottom"
                errors.append(
                    f"{data.side} {key.label}: PCB {edge_name} exceeds keycap envelope by "
                    f"{overhang:.3f} mm"
                )
            if abs(setback - EXPECTED_CAP_RELATIVE_SETBACK_MM) > TOLERANCE_MM:
                edge_name = "top" if use_top else "bottom"
                errors.append(
                    f"{data.side} {key.label}: actual {edge_name} cap-relative setback is "
                    f"{setback:.3f} mm, expected "
                    f"{EXPECTED_CAP_RELATIVE_SETBACK_MM:.3f}+/-{TOLERANCE_MM:.3f} mm"
                )

    row_x_bounds: dict[int, tuple[float, float]] = {}
    row_y_bounds: dict[int, tuple[float, float]] = {}
    for row in range(5):
        indices = [index for index, key in enumerate(data.keys, start=1) if key.row == row]
        bounds = [keycap_bounds(data, index) for index in indices]
        row_x_bounds[row] = (
            min(bound[0] for bound in bounds),
            max(bound[2] for bound in bounds),
        )
        row_y_bounds[row] = (
            min(bound[1] for bound in bounds),
            max(bound[3] for bound in bounds),
        )

    perimeter_overhangs: list[float] = []
    for start, end in data.edge_segments:
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        sample_count = max(1, math.ceil(length / PERIMETER_SAMPLE_STEP_MM))
        for sample_index in range(sample_count + 1):
            ratio = sample_index / sample_count
            x = start[0] + (end[0] - start[0]) * ratio
            y = start[1] + (end[1] - start[1]) * ratio
            if y < row_y_bounds[0][0] or y > row_y_bounds[4][1]:
                continue
            active_rows = [
                row
                for row in range(5)
                if row_y_bounds[row][0] - 1e-6 <= y <= row_y_bounds[row][1] + 1e-6
            ]
            if not active_rows:
                for row in range(4):
                    if row_y_bounds[row][1] < y < row_y_bounds[row + 1][0]:
                        active_rows = [row, row + 1]
                        break
            if not active_rows:
                continue
            allowed_left = min(row_x_bounds[row][0] for row in active_rows)
            allowed_right = max(row_x_bounds[row][1] for row in active_rows)
            perimeter_overhangs.append(max(allowed_left - x, x - allowed_right, 0.0))
    maximum_perimeter_overhang = max(perimeter_overhangs, default=0.0)
    if maximum_perimeter_overhang > TOLERANCE_MM:
        errors.append(
            f"{data.side}: sampled key-field Edge.Cuts exceeds the cap-concealed silhouette by "
            f"{maximum_perimeter_overhang:.3f} mm"
        )

    return (
        {
            "maximum_outer_overhang_mm": round(max(outer_overhangs, default=0.0), 4),
            "maximum_top_bottom_overhang_mm": round(max(vertical_overhangs, default=0.0), 4),
            "maximum_keyfield_perimeter_overhang_mm": round(
                maximum_perimeter_overhang,
                4,
            ),
            "outer_cap_relative_setback_by_row_mm": [
                round(value, 4) for value in outer_setbacks
            ],
            "top_bottom_setback_mm": [
                round(value, 4) for value in top_bottom_setbacks
            ],
            "permitted_exceptions": permitted_exceptions,
            "perimeter_sample_step_mm": PERIMETER_SAMPLE_STEP_MM,
            "join_setback_by_row_mm": [round(value, 4) for value in join_setbacks],
        },
        errors,
    )


def unique_key_center(data: BoardRenderData, label: str) -> tuple[float, float]:
    matches = [
        data.switch_centers[index]
        for index, key in enumerate(data.keys, start=1)
        if key.label == label
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {data.side} key {label!r}, found {len(matches)}")
    return matches[0]


def analyze_one_to_one_svg(
    path: Path,
    data: BoardRenderData,
    repo: Path = ROOT,
) -> tuple[dict[str, object], list[str]]:
    errors: list[str] = []
    try:
        display_path = path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        display_path = path.name
    if not path.is_file():
        return ({"path": display_path, "missing": True}, [f"missing 1:1 SVG: {display_path}"])
    source = path.read_text(encoding="utf-8")
    width_match = re.search(r'width="([0-9.]+)mm"', source)
    height_match = re.search(r'height="([0-9.]+)mm"', source)
    if width_match is None or height_match is None:
        return (
            {"path": display_path, "missing_physical_mm_dimensions": True},
            [f"{display_path}: SVG does not declare physical width/height in mm"],
        )
    width = float(width_match.group(1))
    height = float(height_match.group(1))
    expected_width = data.bounds[2] - data.bounds[0]
    expected_height = data.bounds[3] - data.bounds[1]
    width_error = abs(width - expected_width)
    height_error = abs(height - expected_height)
    maximum_error = max(width_error, height_error)
    if maximum_error > ONE_TO_ONE_TOLERANCE_MM:
        errors.append(
            f"{display_path}: physical SVG dimension error {maximum_error:.4f} mm exceeds "
            f"{ONE_TO_ONE_TOLERANCE_MM:.3f} mm"
        )
    return (
        {
            "path": display_path,
            "declared_width_mm": round(width, 4),
            "declared_height_mm": round(height, 4),
            "edge_cuts_width_mm": round(expected_width, 4),
            "edge_cuts_height_mm": round(expected_height, 4),
            "maximum_dimension_error_mm": round(maximum_error, 4),
        },
        errors,
    )


def analyze_outline(repo: Path = ROOT) -> dict[str, object]:
    context = build_context(repo.resolve(), 1.0, 5.0, "key-pitch", variant="x3-v2")
    left_report, left_errors = analyze_board(context.left)
    right_report, right_errors = analyze_board(context.right)
    mechanical = repo / "hardware" / "kicad" / "mechanical"
    left_svg, left_svg_errors = analyze_one_to_one_svg(
        mechanical / "kc2_left_1to1.svg",
        context.left,
        repo,
    )
    right_svg, right_svg_errors = analyze_one_to_one_svg(
        mechanical / "kc2_right_1to1.svg",
        context.right,
        repo,
    )
    left_center = unique_key_center(context.left, "6")
    right_center = unique_key_center(context.right, "7")
    pitch = right_center[0] + context.right_dx - left_center[0]
    errors = left_errors + right_errors + left_svg_errors + right_svg_errors
    if abs(pitch - X3_V2_JOIN_CENTER_PITCH) > TOLERANCE_MM:
        errors.append(
            f"cross-seam key pitch is {pitch:.3f} mm, "
            f"expected {X3_V2_JOIN_CENTER_PITCH:.3f} mm"
        )
    seam_pair_reports = []
    for clearance in context.seam_key_clearances:
        expected_pitch = (
            clearance.left_cap_width_mm / 2.0
            + clearance.right_cap_width_mm / 2.0
            + X3_V2_JOIN_KEYCAP_GAP
        )
        expected_left_edge = clearance.left_cap_width_mm / 2.0 - EXPECTED_CAP_RELATIVE_SETBACK_MM
        expected_right_edge = clearance.right_cap_width_mm / 2.0 - EXPECTED_CAP_RELATIVE_SETBACK_MM
        pair_name = f"{clearance.left_label}-{clearance.right_label}"
        if abs(clearance.center_pitch_mm - expected_pitch) > TOLERANCE_MM:
            errors.append(
                f"row {clearance.row} {pair_name} center pitch is "
                f"{clearance.center_pitch_mm:.3f} mm, expected {expected_pitch:.3f} mm"
            )
        if abs(clearance.cap_gap_mm - X3_V2_JOIN_KEYCAP_GAP) > TOLERANCE_MM:
            errors.append(
                f"row {clearance.row} {pair_name} keycap gap is "
                f"{clearance.cap_gap_mm:.3f} mm, expected {X3_V2_JOIN_KEYCAP_GAP:.3f} mm"
            )
        if abs(clearance.left_center_to_pcb_edge_mm - expected_left_edge) > TOLERANCE_MM:
            errors.append(
                f"row {clearance.row} {pair_name} left center-to-PCB-edge is "
                f"{clearance.left_center_to_pcb_edge_mm:.3f} mm, expected {expected_left_edge:.3f} mm"
            )
        if abs(clearance.right_center_to_pcb_edge_mm - expected_right_edge) > TOLERANCE_MM:
            errors.append(
                f"row {clearance.row} {pair_name} right center-to-PCB-edge is "
                f"{clearance.right_center_to_pcb_edge_mm:.3f} mm, expected {expected_right_edge:.3f} mm"
            )
        if abs(clearance.pcb_gap_mm - X3_V2_ROW_CENTER_PCB_GAP) > TOLERANCE_MM:
            errors.append(
                f"row {clearance.row} {pair_name} PCB gap is "
                f"{clearance.pcb_gap_mm:.3f} mm, expected {X3_V2_ROW_CENTER_PCB_GAP:.3f} mm"
            )
        seam_pair_reports.append(
            {
                "row": clearance.row,
                "left_key": clearance.left_label,
                "right_key": clearance.right_label,
                "left_cap_width_mm": round(clearance.left_cap_width_mm, 4),
                "right_cap_width_mm": round(clearance.right_cap_width_mm, 4),
                "center_pitch_mm": round(clearance.center_pitch_mm, 4),
                "cap_gap_mm": round(clearance.cap_gap_mm, 4),
                "left_center_to_pcb_edge_mm": round(clearance.left_center_to_pcb_edge_mm, 4),
                "right_center_to_pcb_edge_mm": round(clearance.right_center_to_pcb_edge_mm, 4),
                "pcb_gap_mm": round(clearance.pcb_gap_mm, 4),
            }
        )
    if context.min_edge_clearance_mm + 1e-6 < X3_V2_MIN_JOINED_EDGE_CLEARANCE:
        errors.append(
            f"exact joined PCB Edge.Cuts clearance is {context.min_edge_clearance_mm:.3f} mm, "
            f"below {X3_V2_MIN_JOINED_EDGE_CLEARANCE:.3f} mm"
        )
    return {
        "requirement": "CON-ARCH-006",
        "boards": {"left": left_report, "right": right_report},
        "one_unit_cross_seam_center_pitch_mm": round(pitch, 4),
        "cross_seam_keycap_gap_mm": round(context.key_horizontal_clearance.clearance, 4),
        "row_center_joined_pcb_gap_mm": round(context.measurement.clearance, 4),
        "cross_seam_pairs": seam_pair_reports,
        "keycell_edge_inset_mm": KEYCELL_EDGE_INSET_MM,
        "one_unit_join_center_to_edge_mm": round(EXPECTED_ONE_UNIT_JOIN_CENTER_TO_EDGE_MM, 4),
        "minimum_joined_pcb_gap_mm": round(context.min_edge_clearance_mm, 4),
        "outline_x_range_nesting_mm": round(context.outline_x_range_nesting_mm, 4),
        "one_to_one_exports": {"left": left_svg, "right": right_svg},
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Verify actual KC2 X3 V2 concealed outline, safe 1.80 mm joined keycap gap, "
            "and exact full-outline PCB clearance."
        )
    )
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "hardware"
        / "kicad"
        / "mechanical"
        / "kc2_outline_report.json",
    )
    args = parser.parse_args()
    report = analyze_outline(args.repo)
    rendered = json.dumps(report, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    print(f"wrote {args.output}")
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
