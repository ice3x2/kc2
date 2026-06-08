from __future__ import annotations

import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FAB_DIR = ROOT / "hardware" / "kicad" / "fabrication"

EXPECTED_REGISTRATION_HOLES = {
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
BATT_LEAD_SLOTS = {
    "left": (154.08, 49.00),
    "right": (66.63, 49.00),
}

OLD_M2_COORDINATES = {
    "left": [
        (39.0, 164.75),
        (178.2125, 164.75),
        (121.7125, 44.0),
        (39.5, 107.75),
        (173.45, 66.50),
        (39.5, 66.50),
        (170.50, 108.25),
    ],
    "right": [
        (39.0, 164.75),
        (225.8375, 164.75),
        (100.5, 44.0),
        (225.8375, 107.75),
        (225.8375, 66.20),
        (39.0, 66.20),
        (42.0, 107.75),
        (39.0, 136.0),
    ],
}

TOOL_RE = re.compile(r"^T(\d+)C(\d+(?:\.\d+)?)")
COORD_RE = re.compile(r"^X(-?\d+(?:\.\d+)?)Y(-?\d+(?:\.\d+)?)$")
SLOT_RE = re.compile(r"^X(-?\d+(?:\.\d+)?)Y(-?\d+(?:\.\d+)?)G85X(-?\d+(?:\.\d+)?)Y(-?\d+(?:\.\d+)?)$")
GERBER_COORD_TEMPLATE = "X{0}Y-{1}D03*"
POSITION_TOLERANCE_MM = 0.015
DRILL_TOLERANCE_MM = 0.02
REG_DRILL_MM = 3.0
M2_DRILL_MM = 2.2
BATT_SLOT_LENGTH_MM = 3.6
BATT_SLOT_WIDTH_MM = 2.2
MIN_REGISTRATION_EDGE_CLEARANCE_MM = 1.0
GERBER_LINE_RE = re.compile(r"^X(-?\d+)Y(-?\d+)D0([12])\*$")
GERBER_FLASH_RE = re.compile(r"^X(-?\d+)Y(-?\d+)D03\*$")


def parse_npth_drills(zip_path: Path, side: str) -> list[tuple[float, float, float]]:
    with zipfile.ZipFile(zip_path) as archive:
        text = archive.read(f"kc2_{side}-NPTH.drl").decode("utf-8")

    tools: dict[str, float] = {}
    active_tool: str | None = None
    holes: list[tuple[float, float, float]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        tool_match = TOOL_RE.match(line)
        if tool_match:
            tools[tool_match.group(1)] = float(tool_match.group(2))
            continue
        if line.startswith("T") and line[1:].isdigit():
            active_tool = line[1:]
            continue
        coord_match = COORD_RE.match(line)
        if not coord_match or active_tool is None:
            continue
        drill = tools.get(active_tool)
        if drill is None:
            continue
        x = float(coord_match.group(1))
        y = abs(float(coord_match.group(2)))
        holes.append((x, y, drill))
    return holes


def parse_npth_slots(zip_path: Path, side: str) -> list[tuple[float, float, float, float]]:
    with zipfile.ZipFile(zip_path) as archive:
        text = archive.read(f"kc2_{side}-NPTH.drl").decode("utf-8")

    tools: dict[str, float] = {}
    active_tool: str | None = None
    slots: list[tuple[float, float, float, float]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        tool_match = TOOL_RE.match(line)
        if tool_match:
            tools[tool_match.group(1)] = float(tool_match.group(2))
            continue
        if line.startswith("T") and line[1:].isdigit():
            active_tool = line[1:]
            continue
        slot_match = SLOT_RE.match(line)
        if not slot_match or active_tool is None:
            continue
        drill = tools.get(active_tool)
        if drill is None:
            continue
        x1 = float(slot_match.group(1))
        y1 = abs(float(slot_match.group(2)))
        x2 = float(slot_match.group(3))
        y2 = abs(float(slot_match.group(4)))
        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0
        travel = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        slots.append((center_x, center_y, travel + drill, drill))
    return slots


def has_expected_drill(
    holes: list[tuple[float, float, float]],
    expected: tuple[float, float],
    expected_drill: float,
) -> bool:
    expected_x, expected_y = expected
    return any(
        abs(x - expected_x) <= POSITION_TOLERANCE_MM
        and abs(y - expected_y) <= POSITION_TOLERANCE_MM
        and abs(drill - expected_drill) <= DRILL_TOLERANCE_MM
        for x, y, drill in holes
    )


def has_expected_slot(
    slots: list[tuple[float, float, float, float]],
    expected: tuple[float, float],
) -> bool:
    expected_x, expected_y = expected
    return any(
        abs(x - expected_x) <= POSITION_TOLERANCE_MM
        and abs(y - expected_y) <= POSITION_TOLERANCE_MM
        and abs(length - BATT_SLOT_LENGTH_MM) <= DRILL_TOLERANCE_MM
        and abs(width - BATT_SLOT_WIDTH_MM) <= DRILL_TOLERANCE_MM
        for x, y, length, width in slots
    )


def gerber_coord(value_mm: float) -> str:
    scaled = int(round(value_mm * 1_000_000))
    return str(scaled)


def mask_has_opening(zip_path: Path, side: str, layer_suffix: str, point: tuple[float, float]) -> bool:
    with zipfile.ZipFile(zip_path) as archive:
        text = archive.read(f"kc2_{side}-{layer_suffix}").decode("utf-8")
    x, y = point
    for raw_line in text.splitlines():
        match = GERBER_FLASH_RE.match(raw_line.strip())
        if not match:
            continue
        flash_x = int(match.group(1)) / 1_000_000.0
        flash_y = abs(int(match.group(2)) / 1_000_000.0)
        if abs(flash_x - x) <= POSITION_TOLERANCE_MM and abs(flash_y - y) <= POSITION_TOLERANCE_MM:
            return True
    return False


def parse_edge_segments(zip_path: Path, side: str) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    with zipfile.ZipFile(zip_path) as archive:
        text = archive.read(f"kc2_{side}-Edge_Cuts.gm1").decode("utf-8")

    current: tuple[float, float] | None = None
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        match = GERBER_LINE_RE.match(line)
        if not match:
            continue
        x = int(match.group(1)) / 1_000_000.0
        y = abs(int(match.group(2)) / 1_000_000.0)
        op = match.group(3)
        point = (x, y)
        if op == "2":
            current = point
        elif op == "1":
            if current is not None:
                segments.append((current, point))
            current = point
    return segments


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


def drill_edge_clearance(
    point: tuple[float, float],
    drill: float,
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
) -> float:
    x, y = point
    center_to_edge = min(dist_point_segment(x, y, a[0], a[1], b[0], b[1]) for a, b in segments)
    return center_to_edge - drill / 2.0


def check_side(side: str) -> list[str]:
    errors: list[str] = []
    zip_path = FAB_DIR / f"kc2_{side}_jlcpcb.zip"
    if not zip_path.exists():
        return [f"{side}: missing {zip_path}"]

    holes = parse_npth_drills(zip_path, side)
    slots = parse_npth_slots(zip_path, side)
    edges = parse_edge_segments(zip_path, side)
    for ref, point in EXPECTED_REGISTRATION_HOLES[side].items():
        if not has_expected_drill(holes, point, REG_DRILL_MM):
            errors.append(f"{side}: missing {ref} 3.0 mm NPTH drill at ({point[0]:.4f}, {point[1]:.4f})")
            continue
        clearance = drill_edge_clearance(point, REG_DRILL_MM, edges)
        if clearance < MIN_REGISTRATION_EDGE_CLEARANCE_MM:
            errors.append(
                f"{side}: {ref} drill edge clearance to Edge_Cuts is {clearance:.3f} mm, "
                f"expected >= {MIN_REGISTRATION_EDGE_CLEARANCE_MM:.3f} mm"
            )
        for layer_suffix in ("F_Mask.gts", "B_Mask.gbs"):
            if not mask_has_opening(zip_path, side, layer_suffix, point):
                errors.append(f"{side}: missing {ref} mask opening in {layer_suffix}")

    for point in OLD_M2_COORDINATES[side]:
        if has_expected_drill(holes, point, M2_DRILL_MM):
            errors.append(f"{side}: old M2 2.2 mm NPTH drill still present at ({point[0]:.4f}, {point[1]:.4f})")
    slot_point = BATT_LEAD_SLOTS[side]
    if not has_expected_slot(slots, slot_point):
        errors.append(
            f"{side}: missing 3.6 x 2.2 mm battery lead NPTH slot centered at "
            f"({slot_point[0]:.4f}, {slot_point[1]:.4f})"
        )
    else:
        clearance = drill_edge_clearance(slot_point, max(BATT_SLOT_LENGTH_MM, BATT_SLOT_WIDTH_MM), edges)
        if clearance < MIN_REGISTRATION_EDGE_CLEARANCE_MM:
            errors.append(
                f"{side}: battery lead slot edge clearance to Edge_Cuts is {clearance:.3f} mm, "
                f"expected >= {MIN_REGISTRATION_EDGE_CLEARANCE_MM:.3f} mm"
            )
        for layer_suffix in ("F_Mask.gts", "B_Mask.gbs"):
            if not mask_has_opening(zip_path, side, layer_suffix, slot_point):
                errors.append(f"{side}: missing battery lead slot mask opening in {layer_suffix}")
    return errors


def main() -> int:
    errors: list[str] = []
    for side in ("left", "right"):
        errors.extend(check_side(side))

    if errors:
        print("FAIL: KC2 fabrication screwless registration verification")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PASS: KC2 fabrication screwless registration verification")
    print("- left/right: expected 3.0 mm REG_NPTH drills, F/B mask openings, and Edge_Cuts clearance are present")
    print("- left/right: expected battery lead NPTH slots and mask openings are present")
    print("- left/right: old 2.2 mm M2 drill coordinates are absent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
