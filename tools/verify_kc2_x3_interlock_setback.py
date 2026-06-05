from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import generate_kc2_pcbs as gen  # noqa: E402
from tools.render_kc2_x3_joined import intervals_at_y  # noqa: E402


VERTICAL_MARGIN_MM = gen.INNER_MARGIN + gen.X3_INNER_MARGIN_EXTRA
HORIZONTAL_LEDGE_RELIEF_MM = gen.X3_RIGHT_YH_HORIZONTAL_LEDGE_RELIEF
ROUNDED_CORNER_RADIUS_MM = 2.0
TOLERANCE_MM = 0.08


def mm_vec(vec: pcbnew.VECTOR2I) -> tuple[float, float]:
    return pcbnew.ToMM(vec.x), pcbnew.ToMM(vec.y)


def edge_segments(board: pcbnew.BOARD) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    segments = []
    for item in board.GetDrawings():
        if item.GetLayer() != pcbnew.Edge_Cuts:
            continue
        if hasattr(item, "GetStart") and hasattr(item, "GetEnd"):
            segments.append((mm_vec(item.GetStart()), mm_vec(item.GetEnd())))
    return segments


def switch_center(board: pcbnew.BOARD, ref: str) -> tuple[float, float]:
    for fp in board.GetFootprints():
        if fp.GetReference() == ref:
            return mm_vec(fp.GetPosition())
    raise RuntimeError(f"Missing switch footprint: {ref}")


def horizontal_segment_min_x(
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
    y: float,
    *,
    x_limit: float,
) -> float | None:
    matches: list[float] = []
    for (x1, y1), (x2, y2) in segments:
        if abs(y1 - y2) > 1e-4 or abs(y1 - y) > TOLERANCE_MM:
            continue
        if min(x1, x2) <= x_limit:
            matches.append(min(x1, x2))
    return min(matches) if matches else None


def verify(board_path: Path) -> list[str]:
    board = pcbnew.LoadBoard(str(board_path))
    segments = edge_segments(board)
    if not segments:
        return [f"{board_path}: no Edge.Cuts segments found"]

    errors: list[str] = []
    for idx, key in enumerate(gen.make_right_keys_no_stab(), start=1):
        if key.label not in {"Y", "H"}:
            continue
        cx, cy = switch_center(board, f"SW{idx}")
        key_left = cx - key.w_u * gen.UNIT / 2.0
        intervals = intervals_at_y(segments, cy)
        if not intervals:
            errors.append(f"{board_path}: no outline interval at {key.label} center y={cy:.3f}")
            continue
        outline_left = min(start for start, _ in intervals)
        margin = key_left - outline_left
        if abs(margin - VERTICAL_MARGIN_MM) > TOLERANCE_MM:
            errors.append(
                f"{board_path}: {key.label} vertical protrusion edge margin {margin:.3f} mm, "
                f"expected {VERTICAL_MARGIN_MM:.3f}+/-{TOLERANCE_MM:.3f} mm"
            )
        if key.label == "Y":
            for name, y in (("Y top", cy - gen.UNIT / 2.0), ("Y bottom", cy + gen.UNIT / 2.0)):
                expected = outline_left + ROUNDED_CORNER_RADIUS_MM + HORIZONTAL_LEDGE_RELIEF_MM
                actual = horizontal_segment_min_x(segments, y, x_limit=expected + 1.0)
                if actual is None:
                    errors.append(f"{board_path}: no {name} horizontal ledge segment near y={y:.3f}")
                elif abs(actual - expected) > TOLERANCE_MM:
                    errors.append(
                        f"{board_path}: {name} horizontal ledge starts at x={actual:.3f} mm, "
                        f"expected {expected:.3f}+/-{TOLERANCE_MM:.3f} mm"
                    )
        elif key.label == "H":
            y = cy + gen.UNIT / 2.0
            expected = outline_left + ROUNDED_CORNER_RADIUS_MM + HORIZONTAL_LEDGE_RELIEF_MM
            actual = horizontal_segment_min_x(segments, y, x_limit=expected + 1.0)
            if actual is None:
                errors.append(f"{board_path}: no H bottom horizontal ledge segment near y={y:.3f}")
            elif abs(actual - expected) > TOLERANCE_MM:
                errors.append(
                    f"{board_path}: H bottom horizontal ledge starts at x={actual:.3f} mm, "
                    f"expected {expected:.3f}+/-{TOLERANCE_MM:.3f} mm"
                )
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify KC2 X3 right Y/H interlock horizontal ledge relief.")
    parser.add_argument(
        "board",
        nargs="?",
        type=Path,
        default=ROOT / "hardware" / "kicad" / "kc2_right" / "kc2_right.kicad_pcb",
    )
    args = parser.parse_args()

    errors = verify(args.board)
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        raise SystemExit(1)
    print(f"PASS {args.board}")


if __name__ == "__main__":
    main()
