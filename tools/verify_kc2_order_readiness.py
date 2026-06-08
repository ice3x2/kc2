from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pcbnew

from tools import generate_kc2_pcbs as gen
from tools import render_kc2_x3_joined as joined


PRODUCT_ID_PREFIX = "KC2 v1.0"
KEYCAP_EDGE_INSET_MM = 0.50
MIN_KEYCAP_CLEARANCE_MM = 0.90
TEXT_FORBIDDEN_CLEARANCE_MM = 0.20
EDGE_CLEARANCE_MM = 0.30
BOARD_PATHS = {
    "left": ROOT / "hardware" / "kicad" / "kc2_left" / "kc2_left.kicad_pcb",
    "right": ROOT / "hardware" / "kicad" / "kc2_right" / "kc2_right.kicad_pcb",
}


@dataclass(frozen=True)
class Rect:
    x1: float
    y1: float
    x2: float
    y2: float
    label: str


def mm_box(box: pcbnew.BOX2I, label: str) -> Rect:
    x1 = pcbnew.ToMM(box.GetX())
    y1 = pcbnew.ToMM(box.GetY())
    x2 = pcbnew.ToMM(box.GetRight())
    y2 = pcbnew.ToMM(box.GetBottom())
    return Rect(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2), label)


def expand(rect: Rect, amount: float) -> Rect:
    return Rect(rect.x1 - amount, rect.y1 - amount, rect.x2 + amount, rect.y2 + amount, rect.label)


def intersects(a: Rect, b: Rect) -> bool:
    return a.x1 < b.x2 and a.x2 > b.x1 and a.y1 < b.y2 and a.y2 > b.y1


def rect_distance(a: Rect, b: Rect) -> float:
    dx = max(b.x1 - a.x2, a.x1 - b.x2, 0.0)
    dy = max(b.y1 - a.y2, a.y1 - b.y2, 0.0)
    return (dx * dx + dy * dy) ** 0.5


def edge_segments(board: pcbnew.BOARD) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    return joined.edge_segments(board)


def dist_point_segment(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> float:
    dx = bx - ax
    dy = by - ay
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    nx = ax + t * dx
    ny = ay + t * dy
    return ((px - nx) ** 2 + (py - ny) ** 2) ** 0.5


def rect_edge_clearance(
    rect: Rect,
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
) -> float:
    samples = [
        (rect.x1, rect.y1),
        (rect.x1, rect.y2),
        (rect.x2, rect.y1),
        (rect.x2, rect.y2),
        ((rect.x1 + rect.x2) / 2.0, rect.y1),
        ((rect.x1 + rect.x2) / 2.0, rect.y2),
        (rect.x1, (rect.y1 + rect.y2) / 2.0),
        (rect.x2, (rect.y1 + rect.y2) / 2.0),
    ]
    return min(
        dist_point_segment(px, py, a[0], a[1], b[0], b[1])
        for px, py in samples
        for a, b in segments
    )


def product_texts(board: pcbnew.BOARD, side: str) -> list[pcbnew.PCB_TEXT]:
    expected = f"{PRODUCT_ID_PREFIX} {side[0].upper()}"
    return [
        drawing
        for drawing in board.GetDrawings()
        if isinstance(drawing, pcbnew.PCB_TEXT)
        and drawing.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS)
        and drawing.GetText() == expected
    ]


def forbidden_rects(board: pcbnew.BOARD) -> list[Rect]:
    rects: list[Rect] = []
    for fp in board.GetFootprints():
        if fp.GetReference().startswith("SW") and fp.GetReference()[2:].isdigit():
            continue
        for pad in fp.Pads():
            layers = pad.GetLayerSet()
            if layers.Contains(pcbnew.F_Mask) or layers.Contains(pcbnew.B_Mask) or layers.Contains(pcbnew.F_Cu) or layers.Contains(pcbnew.B_Cu):
                rects.append(mm_box(pad.GetBoundingBox(), f"{fp.GetReference()} pad {pad.GetNumber()}"))
        if fp.GetReference() in {"U1", "SW_RST1", "BAT_LEAD_SLOT1"} or fp.GetReference().startswith("REG"):
            rects.append(mm_box(fp.GetBoundingBox(), fp.GetReference()))
    return rects


def verify_product_text(side: str, board: pcbnew.BOARD) -> list[str]:
    errors: list[str] = []
    texts = product_texts(board, side)
    expected = f"{PRODUCT_ID_PREFIX} {side[0].upper()}"
    if len(texts) != 1:
        return [f"{side}: expected exactly one visible silkscreen {expected!r}, found {len(texts)}"]

    text = texts[0]
    if text.GetLayer() != pcbnew.B_SilkS:
        errors.append(f"{side}: {expected!r} should be on B.SilkS, got {pcbnew.BOARD_ITEM.GetLayerName(text.GetLayer())}")
    if not text.IsMirrored():
        errors.append(f"{side}: {expected!r} on B.SilkS should be mirrored for bottom silkscreen readability")
    text_rect = mm_box(text.GetBoundingBox(), expected)
    clearance = rect_edge_clearance(text_rect, edge_segments(board))
    if clearance < EDGE_CLEARANCE_MM:
        errors.append(f"{side}: {expected!r} edge clearance is {clearance:.3f} mm, expected >= {EDGE_CLEARANCE_MM:.3f} mm")
    for forbidden in forbidden_rects(board):
        if intersects(expand(text_rect, TEXT_FORBIDDEN_CLEARANCE_MM), forbidden):
            errors.append(f"{side}: {expected!r} overlaps/approaches {forbidden.label}")
    return errors


def keycap_rects(data: joined.BoardRenderData, *, dx: float = 0.0, dy: float = 0.0) -> list[Rect]:
    rects: list[Rect] = []
    for idx, key in enumerate(data.keys, start=1):
        x, y = data.switch_centers[idx]
        x += dx
        y += dy
        width = key.w_u * gen.UNIT
        height = key.h_u * gen.UNIT
        rects.append(
            Rect(
                x - width / 2.0 + KEYCAP_EDGE_INSET_MM,
                y - height / 2.0 + KEYCAP_EDGE_INSET_MM,
                x + width / 2.0 - KEYCAP_EDGE_INSET_MM,
                y + height / 2.0 - KEYCAP_EDGE_INSET_MM,
                f"{data.side} SW{idx} {key.label}",
            )
        )
    return rects


def verify_keycap_clearance() -> list[str]:
    errors: list[str] = []
    ctx = joined.build_context(ROOT, joined.DEFAULT_CLEARANCE_MM, joined.DEFAULT_SCALE, "interlock-clearance")
    rects = keycap_rects(ctx.left) + keycap_rects(ctx.right, dx=ctx.right_dx, dy=ctx.right_dy)
    min_distance = 999.0
    min_pair = ("", "")
    for i, first in enumerate(rects):
        for second in rects[i + 1 :]:
            distance = rect_distance(first, second)
            if distance < min_distance:
                min_distance = distance
                min_pair = (first.label, second.label)
            if intersects(first, second):
                errors.append(f"keycap overlap: {first.label} intersects {second.label}")
    if min_distance < MIN_KEYCAP_CLEARANCE_MM:
        errors.append(
            f"minimum keycap clearance is {min_distance:.3f} mm between {min_pair[0]} and {min_pair[1]}, "
            f"expected >= {MIN_KEYCAP_CLEARANCE_MM:.3f} mm"
        )
    else:
        print(f"keycap minimum clearance: {min_distance:.3f} mm between {min_pair[0]} and {min_pair[1]}")
    return errors


def main() -> int:
    errors: list[str] = []
    for side, path in BOARD_PATHS.items():
        board = pcbnew.LoadBoard(str(path))
        errors.extend(verify_product_text(side, board))
    errors.extend(verify_keycap_clearance())

    if errors:
        print("FAIL: KC2 order-readiness guard")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: KC2 order-readiness guard")
    print("- product/version silkscreen is present, readable on B.SilkS, and clear of pads/holes/Edge.Cuts")
    print("- all keycap envelopes are non-overlapping in the interlocked joined placement")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
