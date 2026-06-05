from __future__ import annotations

import argparse
import html
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pcbnew
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.generate_kc2_pcbs import (  # noqa: E402
    UNIT,
    Key,
    make_left_keys_no_stab,
    make_right_keys_no_stab,
)

DEFAULT_CLEARANCE_MM = 1.0
DEFAULT_SCALE = 5.0
FULL_MARGIN_PX = 40.0
ZOOM_WIDTH_MM = 64.0
SCAN_STEP_MM = 0.005
CORRIDOR_STEP_MM = 0.25
TY_ROW_CENTER_Y_MM = 96.575


Segment = tuple[tuple[float, float], tuple[float, float]]


@dataclass(frozen=True)
class BoardRenderData:
    side: str
    board: pcbnew.BOARD
    edge_segments: list[Segment]
    bounds: tuple[float, float, float, float]
    keys: list[Key]
    switch_centers: dict[int, tuple[float, float]]
    mount_centers: list[tuple[float, float]]
    controller_bounds: tuple[float, float, float, float]


@dataclass(frozen=True)
class ClearanceSample:
    y: float
    left_x: float
    right_x: float
    clearance: float


@dataclass(frozen=True)
class KeyHorizontalClearance:
    left_label: str
    right_label: str
    start: tuple[float, float]
    end: tuple[float, float]
    clearance: float


@dataclass(frozen=True)
class RenderContext:
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
    interlock_overlap_mm: float


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


def mount_centers(board: pcbnew.BOARD) -> list[tuple[float, float]]:
    centers: list[tuple[float, float]] = []
    for fp in board.GetFootprints():
        if fp.GetValue() == "M2_NPTH_2.2":
            centers.append(mm_vec(fp.GetPosition()))
    return centers


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


def load_board_data(side: str, path: Path, keys: list[Key]) -> BoardRenderData:
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
        board=board,
        edge_segments=segments,
        bounds=board_bounds(segments),
        keys=keys,
        switch_centers=centers,
        mount_centers=mount_centers(board),
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


def key_horizontal_clearance(left: BoardRenderData, right: BoardRenderData, right_dx: float, right_dy: float) -> KeyHorizontalClearance:
    left_rect = keycap_rect_by_label(left, "6")
    right_rect = keycap_rect_by_label(right, "Y", dx=right_dx, dy=right_dy)
    y = (left_rect[3] + right_rect[1]) / 2.0
    sample = opposing_sample(left, right, right_dx, right_dy, y)
    if sample is None:
        raise RuntimeError("No opposing Edge.Cuts sample found between 6 and Y")
    return KeyHorizontalClearance(
        left_label="6",
        right_label="Y",
        start=(sample.left_x, sample.y),
        end=(sample.right_x, sample.y),
        clearance=sample.clearance,
    )


def build_context(repo: Path, clearance_mm: float, scale: float, placement_mode: str) -> RenderContext:
    left = load_board_data(
        "left",
        repo / "hardware" / "kicad" / "kc2_left-x3" / "kc2_left-x3.kicad_pcb",
        make_left_keys_no_stab(),
    )
    right = load_board_data(
        "right",
        repo / "hardware" / "kicad" / "kc2_right-x3" / "kc2_right-x3.kicad_pcb",
        make_right_keys_no_stab(),
    )

    right_dy = left.bounds[1] - right.bounds[1]
    if placement_mode == "bounding-gap":
        right_dx = left.bounds[2] + clearance_mm - right.bounds[0]
    elif placement_mode == "interlock-clearance":
        right_dx = compute_interlocked_dx(left, right, right_dy, clearance_mm)
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
    corridor_samples = scan_clearances(left, right, right_dx, right_dy, CORRIDOR_STEP_MM)
    measurement = opposing_sample(left, right, right_dx, right_dy, TY_ROW_CENTER_Y_MM) or min_sample
    key_clearance = key_horizontal_clearance(left, right, right_dx, right_dy)
    interlock_overlap = max(0.0, left.bounds[2] - joined_right_bounds[0])

    return RenderContext(
        scale=scale,
        clearance_mm=clearance_mm,
        placement_mode=placement_mode,
        left=left,
        right=right,
        right_dx=right_dx,
        right_dy=right_dy,
        bounds=bounds,
        min_edge_clearance_mm=min_sample.clearance,
        min_clearance_y=min_sample.y,
        measurement=measurement,
        clearance_samples=corridor_samples,
        key_horizontal_clearance=key_clearance,
        interlock_overlap_mm=interlock_overlap,
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


def zoom_center_x(ctx: RenderContext) -> float:
    return (ctx.measurement.left_x + ctx.measurement.right_x) / 2.0


def clearance_polygon(ctx: RenderContext) -> list[tuple[float, float]]:
    left_side = [(sample.left_x, sample.y) for sample in ctx.clearance_samples]
    right_side = [(sample.right_x, sample.y) for sample in reversed(ctx.clearance_samples)]
    return left_side + right_side


def key_horizontal_clearance_label(ctx: RenderContext) -> str:
    gap = ctx.key_horizontal_clearance
    return f"{gap.left_label}-{gap.right_label} X {gap.clearance:.1f} mm"


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
    title_width = 760 if not zoom else min(width, 360)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f5ee"/>',
        (
            f'<g id="interlock-clearance" data-placement-mode="{ctx.placement_mode}" '
            f'data-clearance-mm="{ctx.min_edge_clearance_mm:.4f}" '
            f'data-clearance-width-px="{ctx.min_edge_clearance_mm * ctx.scale:.2f}" '
            f'data-measurement-width-px="{measurement_px_width:.2f}" '
            f'data-key-horizontal-clearance-mm="{ctx.key_horizontal_clearance.clearance:.4f}" '
            f'data-interlock-overlap-mm="{ctx.interlock_overlap_mm:.4f}">'
        ),
        f'<polygon points="{polygon_points}" fill="#f6b8a9" fill-opacity="0.55" stroke="none"/>',
        "</g>",
        '<rect x="8" y="8" width="{:.0f}" height="48" fill="#f7f5ee" fill-opacity="0.94" stroke="none"/>'.format(title_width),
        '<text x="16" y="24" font-family="Arial" font-size="15" fill="#222">KC2 X3 interlocked joined top view, board-coordinate composite</text>',
        (
            f'<text x="16" y="44" font-family="Arial" font-size="11" fill="#555">'
            f'Scale: {ctx.scale:g} px/mm. Min Edge.Cuts clearance: {ctx.min_edge_clearance_mm:.2f} mm. '
            f'Interlock overlap: {ctx.interlock_overlap_mm:.2f} mm.</text>'
        ),
    ]
    lines.append(line((ctx.measurement.left_x, measurement_y), (ctx.measurement.right_x, measurement_y), 'stroke="#d33b2f" stroke-width="2"'))
    lines.append(line((ctx.measurement.left_x, measurement_y - 1.2), (ctx.measurement.left_x, measurement_y + 1.2), 'stroke="#d33b2f" stroke-width="2"'))
    lines.append(line((ctx.measurement.right_x, measurement_y - 1.2), (ctx.measurement.right_x, measurement_y + 1.2), 'stroke="#d33b2f" stroke-width="2"'))
    mx, my = tx(((ctx.measurement.left_x + ctx.measurement.right_x) / 2.0, measurement_y))
    lines.append(f'<text x="{mx:.2f}" y="{my - 8:.2f}" text-anchor="middle" font-family="Arial" font-size="10" fill="#8b2318">{ctx.measurement.clearance:.1f} mm</text>')

    for data, color in ((ctx.left, "#102018"), (ctx.right, "#101b2a")):
        for start, end in data.edge_segments:
            lines.append(line(shift_point(ctx, data.side, start), shift_point(ctx, data.side, end), f'stroke="{color}" stroke-width="2" fill="none"'))

    for data, fill, stroke in ((ctx.left, "#e9fff4", "#2a8d66"), (ctx.right, "#eef5ff", "#467cc0")):
        for label, center, width_u in key_records(data, ctx):
            x, y = center
            w = width_u * UNIT
            key_rect = (x - w / 2.0 + 0.5, y - UNIT / 2.0 + 0.5, x + w / 2.0 - 0.5, y + UNIT / 2.0 - 0.5)
            lines.append(rect(key_rect, f'rx="2" ry="2" fill="{fill}" stroke="{stroke}" stroke-width="1" fill-opacity="0.86"'))
            cx, cy = tx(center)
            lines.append(f'<text x="{cx:.2f}" y="{cy + 3.46:.2f}" text-anchor="middle" font-family="Arial" font-size="10" fill="#101010">{html.escape(label)}</text>')
        ctrl = shifted_rect(ctx, data.side, data.controller_bounds)
        lines.append(rect(ctrl, 'fill="none" stroke="#252525" stroke-width="1.5" stroke-dasharray="4 3"'))
        cx, cy = tx(((ctrl[0] + ctrl[2]) / 2.0, ctrl[1] - 0.8))
        lines.append(f'<text x="{cx:.2f}" y="{cy:.2f}" text-anchor="middle" font-family="Arial" font-size="9" fill="#222">U1</text>')
        for mount in data.mount_centers:
            mx, my = tx(shift_point(ctx, data.side, mount))
            lines.append(f'<circle cx="{mx:.2f}" cy="{my:.2f}" r="7" fill="white" stroke="#555" stroke-width="1"/>')

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

    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return width, height


def render_png(ctx: RenderContext, path: Path, *, zoom: bool) -> tuple[int, int]:
    if zoom:
        center = zoom_center_x(ctx)
        tx, width, height = make_transform(ctx, crop_min_x=center - ZOOM_WIDTH_MM / 2.0, crop_width_mm=ZOOM_WIDTH_MM)
    else:
        tx, width, height = make_transform(ctx)
    img = Image.new("RGB", (width, height), "#f7f5ee")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    draw.polygon([tx(point) for point in clearance_polygon(ctx)], fill="#f6d2ca")
    title_width = 760 if not zoom else min(width, 360)
    draw.rectangle((8, 8, title_width, 56), fill="#f7f5ee")
    draw.text((16, 14), "KC2 X3 interlocked joined top view, board-coordinate composite", fill="#222222", font=font)
    draw.text(
        (16, 34),
        f"Scale: {ctx.scale:g} px/mm. Min Edge.Cuts clearance: {ctx.min_edge_clearance_mm:.2f} mm. Interlock overlap: {ctx.interlock_overlap_mm:.2f} mm.",
        fill="#555555",
        font=font,
    )
    p1 = tx((ctx.measurement.left_x, ctx.measurement.y))
    p2 = tx((ctx.measurement.right_x, ctx.measurement.y))
    draw.line((p1, p2), fill="#d33b2f", width=2)
    for x, y in (p1, p2):
        draw.line((x, y - 6, x, y + 6), fill="#d33b2f", width=2)
    draw.text(((p1[0] + p2[0]) / 2.0, p1[1] - 10), f"{ctx.measurement.clearance:.1f} mm", fill="#8b2318", font=font, anchor="mm")

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
        for mount in data.mount_centers:
            mx, my = tx(shift_point(ctx, data.side, mount))
            draw.ellipse((mx - 7, my - 7, mx + 7, my + 7), fill="white", outline="#555555", width=1)

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

    img.save(path)
    return width, height


def main() -> int:
    parser = argparse.ArgumentParser(description="Render KC2 X3 joined left/right board-coordinate composite.")
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--clearance-mm", "--gap-mm", dest="clearance_mm", type=float, default=DEFAULT_CLEARANCE_MM)
    parser.add_argument("--placement-mode", choices=("interlock-clearance", "bounding-gap"), default="interlock-clearance")
    parser.add_argument("--scale", type=float, default=DEFAULT_SCALE)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "hardware" / "kicad" / "renders")
    args = parser.parse_args()

    ctx = build_context(args.repo.resolve(), args.clearance_mm, args.scale, args.placement_mode)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = [
        (args.output_dir / "kc2_x3_joined_top.svg", False, render_svg),
        (args.output_dir / "kc2_x3_joined_top.png", False, render_png),
        (args.output_dir / "kc2_x3_join_seam_zoom.svg", True, render_svg),
        (args.output_dir / "kc2_x3_join_seam_zoom.png", True, render_png),
    ]
    for path, zoom, renderer in outputs:
        width, height = renderer(ctx, path, zoom=zoom)
        print(f"{path} {width}x{height}")

    print(f"placement_mode={ctx.placement_mode}")
    print(f"target_clearance_mm={ctx.clearance_mm:.4f}")
    print(f"min_edge_clearance_mm={ctx.min_edge_clearance_mm:.4f}")
    print(f"min_clearance_y_mm={ctx.min_clearance_y:.4f}")
    print(f"measurement_y_mm={ctx.measurement.y:.4f}")
    print(f"measurement_clearance_mm={ctx.measurement.clearance:.4f}")
    print(f"key_horizontal_clearance_mm={ctx.key_horizontal_clearance.clearance:.4f}")
    print(f"interlock_overlap_mm={ctx.interlock_overlap_mm:.4f}")
    print(f"right_shift_dx_mm={ctx.right_dx:.4f}")
    print(f"right_shift_dy_mm={ctx.right_dy:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
