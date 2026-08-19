from __future__ import annotations

import argparse
import math
import re
from pathlib import Path


Point = tuple[float, float]
DEFAULT_INSET_MM = 0.35
DEFAULT_PRESERVE_CONTROLLER_ABOVE_MM = 67.5


def signed_area(points: list[Point]) -> float:
    return 0.5 * sum(
        x1 * y2 - x2 * y1
        for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])
    )


def line_intersection(
    a: tuple[float, float],
    av: tuple[float, float],
    b: tuple[float, float],
    bv: tuple[float, float],
) -> tuple[float, float]:
    cross = av[0] * bv[1] - av[1] * bv[0]
    if abs(cross) < 1e-9:
        return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
    delta = (b[0] - a[0], b[1] - a[1])
    scale = (delta[0] * bv[1] - delta[1] * bv[0]) / cross
    return (a[0] + scale * av[0], a[1] + scale * av[1])


def inset_polygon(
    points: list[Point],
    distance: int,
    preserve_y_at_or_above: float | None = None,
) -> list[Point]:
    cleaned: list[Point] = []
    for candidate in points:
        if not cleaned or candidate != cleaned[-1]:
            cleaned.append(candidate)
    if len(cleaned) > 1 and cleaned[0] == cleaned[-1]:
        cleaned.pop()
    points = cleaned
    if len(points) < 3:
        raise ValueError("A Specctra boundary requires at least three points")

    # The system-Python routing step has Shapely available; use its robust
    # topology handling for the interlocking concave outline. Keep the compact
    # line-intersection fallback so the pure geometry unit test can also run in
    # KiCad's bundled Python environment.
    try:
        from shapely.geometry import Polygon, box
    except ImportError:
        Polygon = None
    if Polygon is not None:
        original = Polygon(points)
        inset_geometry = original.buffer(-distance, join_style="mitre")
        if preserve_y_at_or_above is not None:
            min_x, _min_y, max_x, max_y = original.bounds
            controller_region = box(
                min_x - distance * 2,
                preserve_y_at_or_above,
                max_x + distance * 2,
                max_y + distance * 2,
            )
            inset_geometry = inset_geometry.union(original.intersection(controller_region))
        if inset_geometry.is_empty:
            raise ValueError("Inset collapsed the Specctra boundary")
        if inset_geometry.geom_type == "MultiPolygon":
            inset_geometry = max(inset_geometry.geoms, key=lambda geometry: geometry.area)
        result = [(round(x), round(y)) for x, y in list(inset_geometry.exterior.coords)[:-1]]
        if len(result) < 3:
            raise ValueError("Inset collapsed the Specctra boundary")
        return result

    orientation = 1.0 if signed_area(points) > 0 else -1.0
    offset_lines: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for start, end in zip(points, points[1:] + points[:1]):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            raise ValueError(f"Duplicate consecutive boundary point: {start}")
        nx = orientation * -dy / length
        ny = orientation * dx / length
        offset_lines.append(
            ((start[0] + nx * distance, start[1] + ny * distance), (dx, dy))
        )

    result: list[Point] = []
    for index in range(len(points)):
        previous = offset_lines[index - 1]
        current = offset_lines[index]
        x, y = line_intersection(previous[0], previous[1], current[0], current[1])
        candidate = (round(x), round(y))
        if not result or candidate != result[-1]:
            result.append(candidate)
    if len(result) < 3:
        raise ValueError("Inset collapsed the Specctra boundary")
    return result


BOUNDARY_PATTERN = re.compile(
    r"(\(boundary\s+\(path\s+pcb\s+0\s+)([^()]+?)(\)\s*\))",
    re.DOTALL,
)


def inset_dsn_text(
    text: str,
    inset_mm: float,
    preserve_controller_above_mm: float | None = DEFAULT_PRESERVE_CONTROLLER_ABOVE_MM,
) -> str:
    match = BOUNDARY_PATTERN.search(text)
    if match is None:
        raise ValueError("Specctra PCB boundary path was not found")
    values = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", match.group(2))]
    if len(values) % 2:
        raise ValueError("Specctra PCB boundary has an odd coordinate count")
    points = list(zip(values[0::2], values[1::2]))
    preserve_y = (
        None
        if preserve_controller_above_mm is None
        else -preserve_controller_above_mm * 1000.0
    )
    inset = inset_polygon(
        points,
        round(inset_mm * 1000.0),
        preserve_y_at_or_above=preserve_y,
    )
    coordinate_text = "  ".join(f"{x} {y}" for x, y in inset)
    replacement = f"{match.group(1)} {coordinate_text}{match.group(3)}"
    return text[: match.start()] + replacement + text[match.end() :]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inset only the autorouting boundary in a KiCad Specctra DSN."
    )
    parser.add_argument("dsn", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--inset-mm", type=float, default=DEFAULT_INSET_MM)
    parser.add_argument(
        "--preserve-controller-above-mm",
        type=float,
        default=DEFAULT_PRESERVE_CONTROLLER_ABOVE_MM,
        help="Preserve the original service-tab boundary above this physical board Y coordinate.",
    )
    args = parser.parse_args()
    output = args.out or args.dsn
    output.write_text(
        inset_dsn_text(
            args.dsn.read_text(encoding="utf-8"),
            args.inset_mm,
            args.preserve_controller_above_mm,
        ),
        encoding="utf-8",
    )
    print(f"Inset Specctra boundary by {args.inset_mm:.3f} mm: {output}")


if __name__ == "__main__":
    main()
