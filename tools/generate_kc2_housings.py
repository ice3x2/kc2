from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "hardware" / "case"
BOARD_PATHS = {
    "left": ROOT / "hardware" / "kicad" / "kc2_left" / "kc2_left.kicad_pcb",
    "right": ROOT / "hardware" / "kicad" / "kc2_right" / "kc2_right.kicad_pcb",
}
HOTSWAP_SOCKET_FOOTPRINT = "SW_Kailh_Choc_V1_HotSwap_THT"


@dataclass(frozen=True)
class HousingParams:
    design_style: str = "hollow_rail_capture_tray"
    # The housing stays slightly inside the PCB outline so the joined inner
    # edges cannot be blocked by printed plastic swelling.
    outline_inset_mm: float = 0.10
    rail_inset_mm: float = 0.30
    rail_width_mm: float = 2.00
    outer_wall_width_mm: float = 2.40
    floor_thickness_mm: float = 1.20
    socket_body_height_mm: float = 2.20
    socket_safety_clearance_mm: float = 0.40
    # Add 0.01 mm so tessellated/offset geometry still verifies at >= 0.30 mm.
    socket_lateral_clearance_mm: float = 0.31
    pcb_thickness_mm: float = 1.60
    support_post_diameter_mm: float = 4.80
    registration_peg_diameter_mm: float = 2.55
    screw_pilot_hole_diameter_mm: float = 1.60
    peg_top_below_pcb_top_mm: float = 0.30
    battery_slot_clearance_mm: float = 0.70
    battery_floor_cutout_enabled: bool = False
    bottom_corner_radius_mm: float = 0.80
    bottom_edge_radius_mm: float = 0.00
    rear_height_ratio: float = 1.00
    print_volume_limit_mm: float = 150.0
    right_split_center_x_mm: float = 112.0
    right_split_zigzag_amplitude_mm: float = 5.0
    right_split_zigzag_pitch_mm: float = 8.0
    right_split_face_setback_mm: float = 0.20
    cylinder_segments: int = 32

    @property
    def bottom_component_clearance_mm(self) -> float:
        return self.socket_body_height_mm + self.socket_safety_clearance_mm

    @property
    def pcb_bottom_z(self) -> float:
        return self.floor_thickness_mm + self.bottom_component_clearance_mm

    @property
    def front_height_mm(self) -> float:
        return self.pcb_bottom_z

    @property
    def rear_height_mm(self) -> float:
        return self.front_height_mm * self.rear_height_ratio

    @property
    def rear_rise_mm(self) -> float:
        return self.rear_height_mm - self.front_height_mm

    @property
    def peg_top_z(self) -> float:
        return self.pcb_bottom_z + self.pcb_thickness_mm - self.peg_top_below_pcb_top_mm


Point3 = tuple[float, float, float]
Point = tuple[float, float]
Facet = tuple[Point3, Point3, Point3]
TRIANGLE_AREA_TOLERANCE_MM2 = 1e-8
TRIANGLE_OUTSIDE_AREA_TOLERANCE_MM2 = 1e-7


def locate_kicad_python() -> Path:
    candidates = [
        Path(r"C:\Program Files\KiCad\10.0\bin\python.exe"),
        Path(r"C:\Program Files\KiCad\9.0\bin\python.exe"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise SystemExit("KiCad Python was not found. Install KiCad 10 or pass --kicad-python.")


def mm_vec(pcbnew: Any, vec: Any) -> Point:
    return pcbnew.ToMM(vec.x), pcbnew.ToMM(vec.y)


def extract_geometry() -> None:
    import pcbnew  # type: ignore[import-not-found]

    out: dict[str, Any] = {"boards": {}}
    for side, board_path in BOARD_PATHS.items():
        board = pcbnew.LoadBoard(str(board_path))
        if board is None:
            raise RuntimeError(f"Cannot load board: {board_path}")

        edge_segments = []
        registration_holes = []
        socket_keepouts = []
        battery_slot = None
        for item in board.GetDrawings():
            if not hasattr(item, "GetLayer") or item.GetLayer() != pcbnew.Edge_Cuts:
                continue
            if not hasattr(item, "GetStart") or not hasattr(item, "GetEnd"):
                continue
            sx, sy = mm_vec(pcbnew, item.GetStart())
            ex, ey = mm_vec(pcbnew, item.GetEnd())
            edge_segments.append([sx, sy, ex, ey])

        for fp in board.GetFootprints():
            ref = fp.GetReference()
            value = fp.GetValue()
            x, y = mm_vec(pcbnew, fp.GetPosition())
            if value == "REG_NPTH_3.0":
                drill = 3.0
                pads = list(fp.Pads())
                if pads:
                    drill = pcbnew.ToMM(pads[0].GetDrillSize().x)
                registration_holes.append({"ref": ref, "x": x, "y": y, "drill_mm": drill})
            elif ref == "BAT_LEAD_SLOT1":
                pads = list(fp.Pads())
                size_x = 3.6
                size_y = 2.2
                angle_deg = 0.0
                if pads:
                    pad = pads[0]
                    size = pad.GetSize()
                    size_x = pcbnew.ToMM(size.x)
                    size_y = pcbnew.ToMM(size.y)
                    try:
                        angle_deg = float(pad.GetOrientation().AsDegrees())
                    except AttributeError:
                        angle_deg = 0.0
                battery_slot = {
                    "ref": ref,
                    "x": x,
                    "y": y,
                    "size_x_mm": size_x,
                    "size_y_mm": size_y,
                    "angle_deg": angle_deg,
                }
            if str(fp.GetFPID().GetLibItemName()) == HOTSWAP_SOCKET_FOOTPRINT:
                bounds = []
                for item in fp.GraphicalItems():
                    if item.GetLayer() == pcbnew.B_SilkS:
                        bounds.append(item.GetBoundingBox())
                for pad in fp.Pads():
                    if (
                        pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD
                        and pad.IsOnLayer(pcbnew.B_Cu)
                    ):
                        bounds.append(pad.GetBoundingBox())
                if not bounds:
                    raise RuntimeError(f"{side} {ref}: no bottom socket envelope geometry")
                min_x = min(pcbnew.ToMM(box.GetX()) for box in bounds)
                min_y = min(pcbnew.ToMM(box.GetY()) for box in bounds)
                max_x = max(pcbnew.ToMM(box.GetX() + box.GetWidth()) for box in bounds)
                max_y = max(pcbnew.ToMM(box.GetY() + box.GetHeight()) for box in bounds)
                socket_keepouts.append(
                    {
                        "ref": ref,
                        "min_x": min_x,
                        "min_y": min_y,
                        "max_x": max_x,
                        "max_y": max_y,
                    }
                )

        out["boards"][side] = {
            "path": str(board_path.relative_to(ROOT)),
            "edge_segments": edge_segments,
            "registration_holes": sorted(registration_holes, key=lambda h: h["ref"]),
            "socket_keepouts": sorted(socket_keepouts, key=lambda item: item["ref"]),
            "battery_slot": battery_slot,
        }
    print(json.dumps(out, ensure_ascii=False))


def run_extractor(kicad_python: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [str(kicad_python), str(Path(__file__).resolve()), "--extract-geometry"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    text = proc.stdout.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError(f"KiCad extractor did not return JSON:\n{text}\n{proc.stderr}")
    return json.loads(text[start : end + 1])


def require_shapely() -> Any:
    try:
        import shapely  # noqa: F401
        from shapely import affinity
        from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
        from shapely.ops import polygonize, unary_union
        from shapely import constrained_delaunay_triangles
    except ImportError as exc:
        raise SystemExit("Install geometry dependency first: python -m pip install shapely") from exc
    return {
        "affinity": affinity,
        "LineString": LineString,
        "MultiPolygon": MultiPolygon,
        "Point": Point,
        "Polygon": Polygon,
        "box": box,
        "polygonize": polygonize,
        "unary_union": unary_union,
        "constrained_delaunay_triangles": constrained_delaunay_triangles,
    }


def board_polygon(shp: dict[str, Any], segments: list[list[float]]) -> Any:
    lines = [shp["LineString"]([(x1, y1), (x2, y2)]) for x1, y1, x2, y2 in segments]
    merged = shp["unary_union"](lines)
    polygons = [poly for poly in shp["polygonize"](merged) if poly.area > 1.0]
    if not polygons:
        raise RuntimeError("No closed Edge.Cuts polygon could be built")
    polygon = max(polygons, key=lambda poly: poly.area)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.geom_type != "Polygon":
        polygon = max(polygon.geoms, key=lambda poly: poly.area)
    return polygon


def capsule(shp: dict[str, Any], x: float, y: float, size_x: float, size_y: float, angle_deg: float, clearance: float) -> Any:
    # KiCad slot sizes are already local pad dimensions. Build a rounded slot
    # and rotate it if a future board turns the pass-through slot.
    radius = min(size_x, size_y) / 2.0 + clearance
    length = max(size_x, size_y) - min(size_x, size_y)
    if length <= 0:
        geom = shp["Point"](x, y).buffer(radius, resolution=12)
    else:
        line = shp["LineString"]([(x - length / 2.0, y), (x + length / 2.0, y)])
        geom = line.buffer(radius, cap_style="round", resolution=12)
    if abs(angle_deg) > 1e-6:
        geom = shp["affinity"].rotate(geom, angle_deg, origin=(x, y))
    return geom


def translate_points(points: list[dict[str, float]], dx: float, dy: float) -> list[dict[str, float]]:
    return [{**point, "x": point["x"] + dx, "y": point["y"] + dy} for point in points]


def height_offset(y: float, y_min: float, y_max: float, params: HousingParams) -> float:
    span = y_max - y_min
    if span <= 1e-9:
        return 0.0
    # In KC2 case coordinates, the controller/USB side is the smaller Y edge.
    rear_fraction = 1.0 - max(0.0, min(1.0, (y - y_min) / span))
    return params.rear_rise_mm * rear_fraction


def z_at(base_z: float, y: float, y_min: float, y_max: float, params: HousingParams) -> float:
    return base_z + height_offset(y, y_min, y_max, params)


def normal(a: Point3, b: Point3, c: Point3) -> Point3:
    ux, uy, uz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
    vx, vy, vz = c[0] - a[0], c[1] - a[1], c[2] - a[2]
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length <= 1e-12:
        return 0.0, 0.0, 0.0
    return nx / length, ny / length, nz / length


def add_triangle(facets: list[Facet], a: Point3, b: Point3, c: Point3) -> None:
    if normal(a, b, c) != (0.0, 0.0, 0.0):
        facets.append((a, b, c))


def ring_points(coords: Any) -> list[Point]:
    pts = [(float(x), float(y)) for x, y in coords]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    return pts


def add_side_faces(facets: list[Facet], coords: Any, z0: float, z1: float, reverse: bool = False) -> None:
    pts = ring_points(coords)
    for i, p0 in enumerate(pts):
        p1 = pts[(i + 1) % len(pts)]
        a = (p0[0], p0[1], z0)
        b = (p1[0], p1[1], z0)
        c = (p1[0], p1[1], z1)
        d = (p0[0], p0[1], z1)
        if reverse:
            add_triangle(facets, a, c, b)
            add_triangle(facets, a, d, c)
        else:
            add_triangle(facets, a, b, c)
            add_triangle(facets, a, c, d)


def polygon_parts(shp: dict[str, Any], geom: Any) -> list[Any]:
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type == "MultiPolygon":
        return list(geom.geoms)
    raise RuntimeError(f"Unsupported geometry type: {geom.geom_type}")


def triangle_is_inside_polygon(poly: Any, tri: Any) -> bool:
    if tri.area <= TRIANGLE_AREA_TOLERANCE_MM2:
        return False
    allowed_outside_area = max(TRIANGLE_OUTSIDE_AREA_TOLERANCE_MM2, tri.area * 1e-9)
    return tri.difference(poly).area <= allowed_outside_area


def add_extrusion(shp: dict[str, Any], facets: list[Facet], geom: Any, z0: float, z1: float) -> None:
    for poly in polygon_parts(shp, geom):
        triangles = shp["constrained_delaunay_triangles"](poly)
        for tri in triangles.geoms:
            if not triangle_is_inside_polygon(poly, tri):
                continue
            coords = ring_points(tri.exterior.coords)
            if len(coords) != 3:
                continue
            a, b, c = coords
            add_triangle(facets, (a[0], a[1], z0), (c[0], c[1], z0), (b[0], b[1], z0))
            add_triangle(facets, (a[0], a[1], z1), (b[0], b[1], z1), (c[0], c[1], z1))

        add_side_faces(facets, poly.exterior.coords, z0, z1)
        for interior in poly.interiors:
            add_side_faces(facets, interior.coords, z0, z1, reverse=True)


def add_variable_side_faces(
    facets: list[Facet],
    coords: Any,
    z0_fn: Any,
    z1_fn: Any,
    reverse: bool = False,
) -> None:
    pts = ring_points(coords)
    for i, p0 in enumerate(pts):
        p1 = pts[(i + 1) % len(pts)]
        a = (p0[0], p0[1], z0_fn(p0[0], p0[1]))
        b = (p1[0], p1[1], z0_fn(p1[0], p1[1]))
        c = (p1[0], p1[1], z1_fn(p1[0], p1[1]))
        d = (p0[0], p0[1], z1_fn(p0[0], p0[1]))
        if reverse:
            add_triangle(facets, a, c, b)
            add_triangle(facets, a, d, c)
        else:
            add_triangle(facets, a, b, c)
            add_triangle(facets, a, c, d)


def add_variable_extrusion(shp: dict[str, Any], facets: list[Facet], geom: Any, z0_fn: Any, z1_fn: Any) -> None:
    for poly in polygon_parts(shp, geom):
        triangles = shp["constrained_delaunay_triangles"](poly)
        for tri in triangles.geoms:
            if not triangle_is_inside_polygon(poly, tri):
                continue
            coords = ring_points(tri.exterior.coords)
            if len(coords) != 3:
                continue
            a, b, c = coords
            add_triangle(
                facets,
                (a[0], a[1], z0_fn(a[0], a[1])),
                (c[0], c[1], z0_fn(c[0], c[1])),
                (b[0], b[1], z0_fn(b[0], b[1])),
            )
            add_triangle(
                facets,
                (a[0], a[1], z1_fn(a[0], a[1])),
                (b[0], b[1], z1_fn(b[0], b[1])),
                (c[0], c[1], z1_fn(c[0], c[1])),
            )

        add_variable_side_faces(facets, poly.exterior.coords, z0_fn, z1_fn)
        for interior in poly.interiors:
            add_variable_side_faces(facets, interior.coords, z0_fn, z1_fn, reverse=True)


def largest_polygon(shp: dict[str, Any], geom: Any) -> Any | None:
    parts = polygon_parts(shp, geom) if not geom.is_empty else []
    if not parts:
        return None
    return max(parts, key=lambda poly: poly.area)


def add_variable_cap(shp: dict[str, Any], facets: list[Facet], geom: Any, z_fn: Any, reverse: bool = False) -> None:
    for poly in polygon_parts(shp, geom):
        triangles = shp["constrained_delaunay_triangles"](poly)
        for tri in triangles.geoms:
            if not triangle_is_inside_polygon(poly, tri):
                continue
            coords = ring_points(tri.exterior.coords)
            if len(coords) != 3:
                continue
            a, b, c = coords
            pa = (a[0], a[1], z_fn(a[0], a[1]))
            pb = (b[0], b[1], z_fn(b[0], b[1]))
            pc = (c[0], c[1], z_fn(c[0], c[1]))
            if reverse:
                add_triangle(facets, pa, pc, pb)
            else:
                add_triangle(facets, pa, pb, pc)


def sample_ring(shp: dict[str, Any], coords: Any, count: int) -> list[Point]:
    line = shp["LineString"](list(coords))
    if line.length <= 1e-9:
        return []
    return [
        (float(point.x), float(point.y))
        for point in (line.interpolate(line.length * i / count) for i in range(count))
    ]


def add_ring_loft(facets: list[Facet], lower: list[Point], upper: list[Point], z0: float, z1: float) -> None:
    if len(lower) != len(upper) or len(lower) < 3:
        return
    for i, p0 in enumerate(lower):
        p1 = lower[(i + 1) % len(lower)]
        q0 = upper[i]
        q1 = upper[(i + 1) % len(upper)]
        a = (p0[0], p0[1], z0)
        b = (p1[0], p1[1], z0)
        c = (q1[0], q1[1], z1)
        d = (q0[0], q0[1], z1)
        add_triangle(facets, a, b, c)
        add_triangle(facets, a, c, d)


def add_bottom_rounded_variable_extrusion(
    shp: dict[str, Any],
    facets: list[Facet],
    geom: Any,
    top_z_fn: Any,
    bottom_edge_radius: float,
) -> None:
    if bottom_edge_radius <= 1e-6:
        add_variable_extrusion(shp, facets, geom, lambda _x, _y: 0.0, top_z_fn)
        return

    for poly in polygon_parts(shp, geom):
        if len(poly.interiors) > 0:
            add_variable_extrusion(shp, facets, poly, lambda _x, _y: 0.0, top_z_fn)
            continue

        bottom_profile = largest_polygon(
            shp,
            poly.buffer(-bottom_edge_radius, join_style="round", resolution=16),
        )
        if bottom_profile is None or bottom_profile.area <= 1e-8:
            add_variable_extrusion(shp, facets, poly, lambda _x, _y: 0.0, top_z_fn)
            continue

        add_variable_cap(shp, facets, bottom_profile, lambda _x, _y: 0.0, reverse=True)
        add_variable_cap(shp, facets, poly, top_z_fn)
        add_variable_side_faces(facets, poly.exterior.coords, lambda _x, _y: bottom_edge_radius, top_z_fn)

        sample_count = max(
            96,
            min(
                640,
                max(len(ring_points(poly.exterior.coords)), len(ring_points(bottom_profile.exterior.coords))) * 4,
            ),
        )
        layer_count = 6
        layers: list[tuple[Any, float]] = []
        for step in range(layer_count + 1):
            t = step / layer_count
            inset = bottom_edge_radius * (1.0 - math.sin(t * math.pi / 2.0))
            z = bottom_edge_radius * (1.0 - math.cos(t * math.pi / 2.0))
            profile = poly if inset <= 1e-6 else largest_polygon(
                shp,
                poly.buffer(-inset, join_style="round", resolution=16),
            )
            if profile is not None and profile.area > 1e-8:
                layers.append((profile, z))

        for (lower_profile, z0), (upper_profile, z1) in zip(layers, layers[1:]):
            lower_ring = sample_ring(shp, lower_profile.exterior.coords, sample_count)
            upper_ring = sample_ring(shp, upper_profile.exterior.coords, sample_count)
            add_ring_loft(facets, lower_ring, upper_ring, z0, z1)


def add_cylinder(facets: list[Facet], x: float, y: float, radius: float, z0: float, z1: float, segments: int) -> None:
    bottom_center = (x, y, z0)
    top_center = (x, y, z1)
    pts = [
        (x + radius * math.cos(2.0 * math.pi * i / segments), y + radius * math.sin(2.0 * math.pi * i / segments))
        for i in range(segments)
    ]
    for i, p0 in enumerate(pts):
        p1 = pts[(i + 1) % len(pts)]
        b0 = (p0[0], p0[1], z0)
        b1 = (p1[0], p1[1], z0)
        t0 = (p0[0], p0[1], z1)
        t1 = (p1[0], p1[1], z1)
        add_triangle(facets, bottom_center, b1, b0)
        add_triangle(facets, top_center, t0, t1)
        add_triangle(facets, b0, b1, t1)
        add_triangle(facets, b0, t1, t0)


def add_sloped_cylinder(
    facets: list[Facet],
    x: float,
    y: float,
    radius: float,
    z0: float,
    z1: float,
    y_min: float,
    y_max: float,
    params: HousingParams,
    segments: int,
) -> None:
    bottom_center = (x, y, z_at(z0, y, y_min, y_max, params))
    top_center = (x, y, z_at(z1, y, y_min, y_max, params))
    pts = [
        (x + radius * math.cos(2.0 * math.pi * i / segments), y + radius * math.sin(2.0 * math.pi * i / segments))
        for i in range(segments)
    ]
    for i, p0 in enumerate(pts):
        p1 = pts[(i + 1) % len(pts)]
        b0 = (p0[0], p0[1], z_at(z0, p0[1], y_min, y_max, params))
        b1 = (p1[0], p1[1], z_at(z0, p1[1], y_min, y_max, params))
        t0 = (p0[0], p0[1], z_at(z1, p0[1], y_min, y_max, params))
        t1 = (p1[0], p1[1], z_at(z1, p1[1], y_min, y_max, params))
        add_triangle(facets, bottom_center, b1, b0)
        add_triangle(facets, top_center, t0, t1)
        add_triangle(facets, b0, b1, t1)
        add_triangle(facets, b0, t1, t0)


def write_stl(path: Path, name: str, facets: list[Facet]) -> None:
    with path.open("w", encoding="ascii", newline="\n") as fh:
        fh.write(f"solid {name}\n")
        for a, b, c in facets:
            nx, ny, nz = normal(a, b, c)
            fh.write(f"  facet normal {nx:.8g} {ny:.8g} {nz:.8g}\n")
            fh.write("    outer loop\n")
            for x, y, z in (a, b, c):
                fh.write(f"      vertex {x:.6f} {y:.6f} {z:.6f}\n")
            fh.write("    endloop\n")
            fh.write("  endfacet\n")
        fh.write(f"endsolid {name}\n")


def build_housing(shp: dict[str, Any], side_data: dict[str, Any], params: HousingParams) -> tuple[list[Facet], dict[str, Any]]:
    raw_poly = board_polygon(shp, side_data["edge_segments"])
    minx, miny, maxx, maxy = raw_poly.bounds
    dx = -minx
    dy = -miny
    board = shp["affinity"].translate(raw_poly, xoff=dx, yoff=dy)
    reg_holes = translate_points(side_data["registration_holes"], dx, dy)
    slot = side_data.get("battery_slot")
    board_min_y, board_max_y = board.bounds[1], board.bounds[3]

    outer = board.buffer(-params.outline_inset_mm, join_style="round", resolution=16)
    if params.bottom_corner_radius_mm > 0:
        outer = outer.buffer(-params.bottom_corner_radius_mm / 2.0, join_style="round", resolution=16).buffer(
            params.bottom_corner_radius_mm / 2.0,
            join_style="round",
            resolution=16,
        )
    cavity = outer.buffer(-params.outer_wall_width_mm, join_style="round", resolution=16)
    if not cavity.is_valid:
        cavity = cavity.buffer(0)
    wall = outer.difference(cavity)

    cutouts = []
    if slot and params.battery_floor_cutout_enabled:
        cutouts.append(
            capsule(
                shp,
                slot["x"] + dx,
                slot["y"] + dy,
                slot["size_x_mm"],
                slot["size_y_mm"],
                slot.get("angle_deg", 0.0),
                params.battery_slot_clearance_mm,
            )
        )
    for cutout in cutouts:
        outer = outer.difference(cutout)
        wall = wall.difference(cutout)

    if outer.is_empty or cavity.is_empty or wall.is_empty:
        raise RuntimeError("Generated empty housing geometry")

    facets: list[Facet] = []
    floor_top = lambda _x, y: z_at(params.floor_thickness_mm, y, board_min_y, board_max_y, params)
    wall_top = lambda _x, y: z_at(params.pcb_bottom_z, y, board_min_y, board_max_y, params)
    add_bottom_rounded_variable_extrusion(shp, facets, outer, floor_top, params.bottom_edge_radius_mm)
    add_variable_extrusion(shp, facets, wall, floor_top, wall_top)

    for hole in reg_holes:
        x = hole["x"]
        y = hole["y"]
        add_sloped_cylinder(
            facets,
            x,
            y,
            params.support_post_diameter_mm / 2.0,
            params.floor_thickness_mm,
            params.pcb_bottom_z,
            board_min_y,
            board_max_y,
            params,
            params.cylinder_segments,
        )
        add_sloped_cylinder(
            facets,
            x,
            y,
            params.registration_peg_diameter_mm / 2.0,
            params.pcb_bottom_z,
            params.peg_top_z,
            board_min_y,
            board_max_y,
            params,
            params.cylinder_segments,
        )

    metadata = {
        "source_board": side_data["path"],
        "source_bounds_mm": [minx, miny, maxx, maxy],
        "stl_translation_mm": [dx, dy],
        "output_bounds_xy_mm": list(outer.bounds),
        "registration_holes": reg_holes,
        "battery_slot": None
        if slot is None
        else {
            **slot,
            "x": slot["x"] + dx,
            "y": slot["y"] + dy,
            "clearance_mm": params.battery_slot_clearance_mm,
            "housing_floor_cutout": params.battery_floor_cutout_enabled,
        },
        "height_profile": {
            "front_edge_y_mm": board_max_y,
            "rear_controller_edge_y_mm": board_min_y,
            "front_height_mm": params.front_height_mm,
            "rear_height_mm": params.rear_height_mm,
            "rear_height_ratio": params.rear_height_ratio,
            "rear_rise_mm": params.rear_rise_mm,
        },
        "interior_cavity": {
            "open_above_floor": True,
            "outer_wall_width_mm": params.outer_wall_width_mm,
            "floor_top_front_mm": params.floor_thickness_mm,
            "outer_area_mm2": outer.area,
            "open_area_mm2": cavity.area,
            "open_area_ratio": cavity.area / outer.area,
            "external_step_mm": 0.0,
        },
        "facet_count": len(facets),
    }
    return facets, metadata


def params_to_dict(params: HousingParams) -> dict[str, Any]:
    return {
        "design_style": params.design_style,
        "outline_inset_mm": params.outline_inset_mm,
        "rail_inset_mm": params.rail_inset_mm,
        "rail_width_mm": params.rail_width_mm,
        "outer_wall_width_mm": params.outer_wall_width_mm,
        "floor_thickness_mm": params.floor_thickness_mm,
        "socket_body_height_mm": params.socket_body_height_mm,
        "socket_safety_clearance_mm": params.socket_safety_clearance_mm,
        "socket_lateral_clearance_mm": params.socket_lateral_clearance_mm,
        "bottom_component_clearance_mm": params.bottom_component_clearance_mm,
        "pcb_thickness_mm": params.pcb_thickness_mm,
        "support_post_diameter_mm": params.support_post_diameter_mm,
        "registration_peg_diameter_mm": params.registration_peg_diameter_mm,
        "screw_pilot_hole_diameter_mm": params.screw_pilot_hole_diameter_mm,
        "peg_top_below_pcb_top_mm": params.peg_top_below_pcb_top_mm,
        "battery_slot_clearance_mm": params.battery_slot_clearance_mm,
        "battery_floor_cutout_enabled": params.battery_floor_cutout_enabled,
        "bottom_corner_radius_mm": params.bottom_corner_radius_mm,
        "bottom_edge_radius_mm": params.bottom_edge_radius_mm,
        "front_height_mm": params.front_height_mm,
        "rear_height_mm": params.rear_height_mm,
        "rear_height_ratio": params.rear_height_ratio,
        "rear_rise_mm": params.rear_rise_mm,
        "print_volume_limit_mm": params.print_volume_limit_mm,
        "right_split_center_x_mm": params.right_split_center_x_mm,
        "right_split_zigzag_amplitude_mm": params.right_split_zigzag_amplitude_mm,
        "right_split_zigzag_pitch_mm": params.right_split_zigzag_pitch_mm,
        "right_split_face_setback_mm": params.right_split_face_setback_mm,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate KC2 rail-capture lower housing CAD from KiCad Edge.Cuts.")
    parser.add_argument("--extract-geometry", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--kicad-python", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    if args.extract_geometry:
        extract_geometry()
        return 0

    kicad_python = args.kicad_python or locate_kicad_python()
    import generate_kc2_housing_step as cad_generator

    return cad_generator.generate_outputs(args.output_dir, kicad_python)


if __name__ == "__main__":
    raise SystemExit(main())
