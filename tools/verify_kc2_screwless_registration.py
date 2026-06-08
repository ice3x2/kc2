from __future__ import annotations

from pathlib import Path

import pcbnew


ROOT = Path(__file__).resolve().parents[1]
BOARD_PATHS = {
    "left": ROOT / "hardware" / "kicad" / "kc2_left" / "kc2_left.kicad_pcb",
    "right": ROOT / "hardware" / "kicad" / "kc2_right" / "kc2_right.kicad_pcb",
}

REGISTRATION_VALUE = "REG_NPTH_3.0"
EXPECTED_REGISTRATION_COUNT = 9
EXPECTED_DRILL_MM = 3.0
DRILL_TOLERANCE_MM = 0.02
POSITION_TOLERANCE_MM = 0.03
MIN_REGISTRATION_EDGE_CLEARANCE_MM = 1.0
MIN_REGISTRATION_COPPER_CLEARANCE_MM = 0.25
EXPECTED_REGISTRATION_POSITIONS = {
    "left": {
        "REG1": (63.03, 102.03),
        "REG2": (124.71, 91.03),
        "REG3": (145.40, 90.53),
        "REG4": (66.53, 122.93),
        "REG5": (109.21, 122.93),
        "REG6": (146.90, 122.93),
        "REG7": (61.52, 151.32),
        "REG8": (109.21, 151.32),
        "REG9": (137.40, 142.32),
    },
    "right": {
        "REG1": (103.12, 84.53),
        "REG2": (141.69, 84.03),
        "REG3": (200.75, 95.53),
        "REG4": (54.38, 127.17),
        "REG5": (131.69, 125.93),
        "REG6": (200.25, 121.93),
        "REG7": (54.88, 144.57),
        "REG8": (146.19, 141.82),
        "REG9": (205.75, 130.32),
    },
}
LABEL_DISTANCE_MAX_MM = 4.5


def to_mm_vec(vec: pcbnew.VECTOR2I) -> tuple[float, float]:
    return pcbnew.ToMM(vec.x), pcbnew.ToMM(vec.y)


def registration_holes(board: pcbnew.BOARD) -> list[tuple[str, float, float, float]]:
    holes: list[tuple[str, float, float, float]] = []
    for fp in board.GetFootprints():
        if fp.GetValue() != REGISTRATION_VALUE:
            continue
        pads = list(fp.Pads())
        if len(pads) != 1:
            holes.append((fp.GetReference(), *to_mm_vec(fp.GetPosition()), -1.0))
            continue
        drill = pcbnew.ToMM(pads[0].GetDrillSize().x)
        holes.append((fp.GetReference(), *to_mm_vec(fp.GetPosition()), drill))
    return sorted(holes, key=lambda item: item[0])


def m2_holes(board: pcbnew.BOARD) -> list[str]:
    refs: list[str] = []
    for fp in board.GetFootprints():
        if fp.GetValue() == "M2_NPTH_2.2" or "MountingHole_2.2mm_M2" in fp.GetFPIDAsString():
            refs.append(fp.GetReference())
    return sorted(refs)


def switch_centers(board: pcbnew.BOARD) -> list[tuple[float, float]]:
    centers: list[tuple[float, float]] = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref.startswith("SW") and ref != "SW_RST1":
            centers.append(to_mm_vec(fp.GetPosition()))
    return centers


def visible_hole_labels(board: pcbnew.BOARD) -> dict[str, list[tuple[float, float, int]]]:
    labels: dict[str, list[tuple[float, float, int]]] = {}
    for drawing in board.GetDrawings():
        if not hasattr(drawing, "GetText") or not hasattr(drawing, "GetPosition"):
            continue
        layer = drawing.GetLayer()
        if layer not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            continue
        text = drawing.GetText()
        if not text.startswith("H") or not text[1:].isdigit():
            continue
        x, y = to_mm_vec(drawing.GetPosition())
        labels.setdefault(text, []).append((x, y, layer))
    return labels


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
    nearest_x = ax + t * dx
    nearest_y = ay + t * dy
    return ((px - nearest_x) ** 2 + (py - nearest_y) ** 2) ** 0.5


def edge_segments(board: pcbnew.BOARD) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for drawing in board.GetDrawings():
        if not hasattr(drawing, "GetLayer") or drawing.GetLayer() != pcbnew.Edge_Cuts:
            continue
        if not hasattr(drawing, "GetStart") or not hasattr(drawing, "GetEnd"):
            continue
        segments.append((to_mm_vec(drawing.GetStart()), to_mm_vec(drawing.GetEnd())))
    return segments


def registration_edge_clearance(board: pcbnew.BOARD, x: float, y: float, drill: float) -> float:
    segments = edge_segments(board)
    if not segments:
        return -999.0
    center_to_edge = min(dist_point_segment(x, y, a[0], a[1], b[0], b[1]) for a, b in segments)
    return center_to_edge - drill / 2.0


def pad_has_copper(pad: pcbnew.PAD) -> bool:
    layers = pad.GetLayerSet()
    return layers.Contains(pcbnew.F_Cu) or layers.Contains(pcbnew.B_Cu)


def registration_copper_clearance(board: pcbnew.BOARD, x: float, y: float, drill: float) -> tuple[float, str]:
    radius = drill / 2.0
    best = (999.0, "")
    for track in board.GetTracks():
        if isinstance(track, pcbnew.PCB_VIA):
            pos = to_mm_vec(track.GetPosition())
            clearance = (
                ((x - pos[0]) ** 2 + (y - pos[1]) ** 2) ** 0.5
                - radius
                - pcbnew.ToMM(track.GetWidth(pcbnew.F_Cu)) / 2.0
            )
            label = f"via {track.GetNetname()} at ({pos[0]:.3f}, {pos[1]:.3f})"
        elif isinstance(track, pcbnew.PCB_TRACK):
            start = to_mm_vec(track.GetStart())
            end = to_mm_vec(track.GetEnd())
            clearance = (
                dist_point_segment(x, y, start[0], start[1], end[0], end[1])
                - radius
                - pcbnew.ToMM(track.GetWidth()) / 2.0
            )
            label = (
                f"track {track.GetNetname()} {pcbnew.LayerName(track.GetLayer())} "
                f"({start[0]:.3f}, {start[1]:.3f})->({end[0]:.3f}, {end[1]:.3f})"
            )
        else:
            continue
        if clearance < best[0]:
            best = (clearance, label)

    for fp in board.GetFootprints():
        if fp.GetValue() == REGISTRATION_VALUE:
            continue
        for pad in fp.Pads():
            if not pad_has_copper(pad):
                continue
            pos = to_mm_vec(pad.GetPosition())
            size = pad.GetSize()
            pad_radius = max(pcbnew.ToMM(size.x), pcbnew.ToMM(size.y)) / 2.0
            clearance = ((x - pos[0]) ** 2 + (y - pos[1]) ** 2) ** 0.5 - radius - pad_radius
            label = f"pad {fp.GetReference()}-{pad.GetNumber()} {pad.GetNetname()} at ({pos[0]:.3f}, {pos[1]:.3f})"
            if clearance < best[0]:
                best = (clearance, label)
    return best


def band_index(value: float, bounds: list[float]) -> int | None:
    for idx in range(3):
        if bounds[idx] <= value <= bounds[idx + 1]:
            return idx
    return None


def distribution_errors(side: str, board: pcbnew.BOARD, holes: list[tuple[str, float, float, float]]) -> list[str]:
    centers = switch_centers(board)
    if not centers:
        return [f"{side}: no switch centers found"]
    min_x = min(x for x, _ in centers)
    max_x = max(x for x, _ in centers)
    min_y = min(y for _, y in centers)
    max_y = max(y for _, y in centers)
    x_bounds = [min_x + (max_x - min_x) * n / 3.0 for n in range(4)]
    y_bounds = [min_y + (max_y - min_y) * n / 3.0 for n in range(4)]
    cells: dict[tuple[int, int], list[str]] = {(x, y): [] for x in range(3) for y in range(3)}
    errors: list[str] = []
    for ref, x, y, _drill in holes:
        xi = band_index(x, x_bounds)
        yi = band_index(y, y_bounds)
        if xi is None or yi is None:
            errors.append(f"{side}: {ref} at ({x:.2f}, {y:.2f}) is outside the switch-field 3x3 registration area")
            continue
        cells[(xi, yi)].append(ref)
    for cell, refs in sorted(cells.items()):
        if len(refs) != 1:
            errors.append(f"{side}: registration cell {cell} has {len(refs)} holes: {refs}")
    return errors


def verify_side(side: str, path: Path) -> list[str]:
    board = pcbnew.LoadBoard(str(path))
    errors: list[str] = []
    screws = m2_holes(board)
    if screws:
        errors.append(f"{side}: expected zero M2 screw holes, got {screws}")
    holes = registration_holes(board)
    if len(holes) != EXPECTED_REGISTRATION_COUNT:
        errors.append(f"{side}: expected {EXPECTED_REGISTRATION_COUNT} registration holes, got {len(holes)}")
    expected_refs = {f"REG{idx}" for idx in range(1, EXPECTED_REGISTRATION_COUNT + 1)}
    actual_refs = {ref for ref, *_ in holes}
    if actual_refs != expected_refs:
        errors.append(f"{side}: expected registration refs {sorted(expected_refs)}, got {sorted(actual_refs)}")
    for ref, _x, _y, drill in holes:
        if abs(drill - EXPECTED_DRILL_MM) > DRILL_TOLERANCE_MM:
            errors.append(f"{side}: {ref} drill is {drill:.3f} mm, expected {EXPECTED_DRILL_MM:.3f} mm")
    for ref, x, y, drill in holes:
        clearance = registration_edge_clearance(board, x, y, drill)
        if clearance < MIN_REGISTRATION_EDGE_CLEARANCE_MM:
            errors.append(
                f"{side}: {ref} hole edge clearance to Edge.Cuts is {clearance:.3f} mm, "
                f"expected >= {MIN_REGISTRATION_EDGE_CLEARANCE_MM:.3f} mm"
            )
        copper_clearance, copper_label = registration_copper_clearance(board, x, y, drill)
        if copper_clearance < MIN_REGISTRATION_COPPER_CLEARANCE_MM:
            errors.append(
                f"{side}: {ref} copper clearance is {copper_clearance:.3f} mm, "
                f"expected >= {MIN_REGISTRATION_COPPER_CLEARANCE_MM:.3f} mm ({copper_label})"
            )
    by_ref = {ref: (x, y) for ref, x, y, _drill in holes}
    for ref, (expected_x, expected_y) in EXPECTED_REGISTRATION_POSITIONS[side].items():
        actual = by_ref.get(ref)
        if actual is None:
            continue
        actual_x, actual_y = actual
        if abs(actual_x - expected_x) > POSITION_TOLERANCE_MM or abs(actual_y - expected_y) > POSITION_TOLERANCE_MM:
            errors.append(
                f"{side}: {ref} at ({actual_x:.3f}, {actual_y:.3f}) mm, "
                f"expected ({expected_x:.3f}, {expected_y:.3f}) mm"
            )
    labels = visible_hole_labels(board)
    for idx, ref in enumerate((f"REG{n}" for n in range(1, EXPECTED_REGISTRATION_COUNT + 1)), start=1):
        actual = by_ref.get(ref)
        if actual is None:
            continue
        expected_label = f"H{idx}"
        candidates = labels.get(expected_label, [])
        if not candidates:
            errors.append(f"{side}: missing visible {expected_label} label near {ref}")
            continue
        x, y = actual
        if all(((x - lx) ** 2 + (y - ly) ** 2) ** 0.5 > LABEL_DISTANCE_MAX_MM for lx, ly, _layer in candidates):
            errors.append(f"{side}: {expected_label} label is not within {LABEL_DISTANCE_MAX_MM:.1f} mm of {ref}")
    if len(holes) == EXPECTED_REGISTRATION_COUNT:
        errors.extend(distribution_errors(side, board, holes))
    return errors


def main() -> int:
    errors: list[str] = []
    for side, path in BOARD_PATHS.items():
        errors.extend(verify_side(side, path))
    if errors:
        print("FAIL: KC2 X3 screwless registration verification")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: KC2 X3 screwless registration verification")
    print("- left/right: zero M2 screw holes")
    print("- left/right: 9 REG_NPTH_3.0 holes at verified anti-flex 3x3 registration coordinates")
    print("- left/right: visible H1-H9 labels are present near the registration holes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
