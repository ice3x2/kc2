"""Generate the draft KC2 X3 V2 load-bearing lower housings.

The V2 design is intentionally independent of the promoted 77-key housing.
It derives a narrow perimeter rail and copper-aware underside support posts from
the current draft V2 KiCad boards and never uses REG/H holes, pegs, or pilots.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = Path(__file__).resolve()
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import generate_kc2_housings as legacy_geometry  # noqa: E402


REQUIREMENT = "CON-ARCH-006"
VARIANT = "x3-v2"
OUTPUT_DIR = ROOT / "hardware" / "case" / "draft" / VARIANT
MANIFEST_PATH = OUTPUT_DIR / "kc2_x3_v2_housing_manifest.json"
BOARD_PATHS = {
    "left": ROOT / "hardware" / "kicad" / "draft" / VARIANT / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb",
    "right": ROOT / "hardware" / "kicad" / "draft" / VARIANT / "kc2_right-x3-v2" / "kc2_right-x3-v2.kicad_pcb",
}

FLOOR_THICKNESS_MM = 1.20
BOTTOM_COMPONENT_CLEARANCE_MM = 2.70
PCB_BOTTOM_Z_MM = round(FLOOR_THICKNESS_MM + BOTTOM_COMPONENT_CLEARANCE_MM, 2)
PCB_THICKNESS_MM = 1.60
OUTLINE_INSET_MM = 0.10
RAIL_INSET_MM = 0.10
RAIL_WIDTH_MM = 0.65
POST_DIAMETER_MM = 3.20
POST_CLEARANCE_MM = 0.30
FILLET_ALLOWANCE_MM = 0.30
TRACK_CLEARANCE_MM = 0.15
BATTERY_ACCESS_CLEARANCE_MM = 0.70
MAX_LOAD_POINT_TO_SUPPORT_MM = 24.0
PRINT_VOLUME_LIMIT_MM = 150.0
RIGHT_SPLIT_CLEARANCE_MM = 0.20
RIGHT_LAP_OVERLAP_MM = 10.0
RIGHT_LAP_THICKNESS_MM = 0.75
RIGHT_LAP_VERTICAL_CLEARANCE_MM = 0.10
CASE_JOIN_BOSS_DIAMETER_MM = 3.20
CASE_JOIN_PILOT_DIAMETER_MM = 1.60
CASE_JOIN_RECEIVING_PILOT_START_Z_MM = 0.85
CASE_JOIN_RECEIVING_PILOT_TOP_Z_MM = 3.60
CASE_JOIN_BOSS_TOP_Z_MM = 3.85
CASE_JOIN_HEAD_SEAT_Z_MM = 0.70
CASE_JOIN_CLEARANCE_HOLE_DIAMETER_MM = 2.40
CASE_JOIN_CLAMP_COLLAR_DIAMETER_MM = 5.40
CASE_JOIN_CLAMP_COLLAR_TOP_Z_MM = 0.85
CASE_JOIN_HEAD_RECESS_DIAMETER_MM = 4.40
CASE_JOIN_SCREW_HEAD_DIAMETER_NOMINAL_MM = 4.00
CASE_JOIN_SCREW_HEAD_DIAMETER_MIN_MM = 3.50
CASE_JOIN_SCREW_HEAD_DIAMETER_MAX_MM = 4.00
CASE_JOIN_SCREW_HEAD_HEIGHT_NOMINAL_MM = 0.50
CASE_JOIN_SCREW_HEAD_HEIGHT_MIN_MM = 0.40
CASE_JOIN_SCREW_HEAD_HEIGHT_MAX_MM = 0.60
CASE_JOIN_HEAD_RECESS_DEPTH_MM = CASE_JOIN_HEAD_SEAT_Z_MM
CASE_JOIN_SCREW_HEAD_ENVELOPE_MM = CASE_JOIN_CLAMP_COLLAR_DIAMETER_MM
CASE_JOIN_FASTENER_PART_NUMBER = "SUNCO CSPSL-ST3W-M2-3"
CASE_JOIN_FASTENER_REFERENCE = (
    "https://jp.misumi-ec.com/vona2/detail/221005676627/?HissuCode=CSPSL-ST3W-M2-3"
)
CASE_JOIN_THREAD = "M2 x 0.4"
CASE_JOIN_UNDER_HEAD_LENGTH_MM = 3.00
CASE_JOIN_LENGTH_LOWER_TOLERANCE_MM = -0.30
CASE_JOIN_LENGTH_UPPER_TOLERANCE_MM = 0.00
CASE_JOIN_FDM_Z_TOLERANCE_MM = 0.05
CASE_JOIN_PART_A_SEAT_FDM_TOLERANCE_MM = 0.05
CASE_JOIN_PART_B_BOSS_FDM_TOLERANCE_MM = 0.05
CASE_JOIN_SUPPORT_PLANE_FDM_TOLERANCE_MM = 0.05
CASE_JOIN_MIN_INSTALLED_CLEARANCE_MM = 0.05
CASE_JOIN_TIP_ALLOWANCE_MM = 0.35
CASE_JOIN_MIN_EFFECTIVE_ENGAGEMENT_MM = 1.50
CASE_JOIN_MIN_HEAD_BEARING_MM = 0.40
CASE_JOIN_MIN_COLLAR_WALL_MM = 0.50
CASE_JOIN_MIN_RECESS_PRINT_CLEARANCE_MM = 0.20
CASE_JOIN_DRIVE = "Phillips #0"
CASE_JOIN_DRIVER_SHAFT_DIAMETER_MM = 3.00
CASE_JOIN_DRIVER_ACCESS_HEIGHT_MM = 20.00


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def has_trailing_horizontal_whitespace(path: Path) -> bool:
    return re.search(rb"[ \t]+(?=\r?\n|\Z)", path.read_bytes()) is not None


def normalize_exported_text(path: Path) -> None:
    """Strip only line-ending spaces/tabs while preserving all newline bytes."""

    original = path.read_bytes()
    normalized = re.sub(rb"[ \t]+(?=\r?\n|\Z)", b"", original)
    if normalized != original:
        path.write_bytes(normalized)


def _box(pcbnew: Any, item: Any) -> list[float]:
    bounds = item.GetBoundingBox()
    return [
        pcbnew.ToMM(bounds.GetX()),
        pcbnew.ToMM(bounds.GetY()),
        pcbnew.ToMM(bounds.GetX() + bounds.GetWidth()),
        pcbnew.ToMM(bounds.GetY() + bounds.GetHeight()),
    ]


def _point(pcbnew: Any, value: Any) -> list[float]:
    return [pcbnew.ToMM(value.x), pcbnew.ToMM(value.y)]


def extract_board(pcbnew: Any, path: Path) -> dict[str, Any]:
    board = pcbnew.LoadBoard(str(path))
    if board is None:
        raise RuntimeError(f"Cannot load board: {path}")

    edge_segments = []
    for item in board.GetDrawings():
        if item.GetLayer() != pcbnew.Edge_Cuts or not hasattr(item, "GetStart"):
            continue
        edge_segments.append([*_point(pcbnew, item.GetStart()), *_point(pcbnew, item.GetEnd())])

    classes: dict[str, list[dict[str, Any]]] = {
        "choc_socket_body": [],
        "choc_socket_fillets": [],
        "mx_pins_pads_fillets": [],
        "diode_body_pads_fillets": [],
        "bottom_copper_tracks": [],
        "vias": [],
        "controller_reset": [],
        "battery_slot": [],
    }
    switches: list[dict[str, Any]] = []
    legacy_refs: list[str] = []

    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        if (ref.startswith("REG") and ref[3:].isdigit()) or (
            ref.startswith("H") and ref[1:].isdigit()
        ):
            legacy_refs.append(ref)

        pads = list(footprint.Pads())
        graphics = list(footprint.GraphicalItems())
        if ref.startswith("SW") and ref[2:].isdigit():
            center = _point(pcbnew, footprint.GetPosition())
            switches.append({"ref": ref, "center": center})
            body_boxes = [
                _box(pcbnew, item)
                for item in graphics
                if item.GetLayer() in (pcbnew.B_Fab, pcbnew.B_SilkS)
            ]
            classes["choc_socket_body"].extend(
                {"kind": "box", "bounds": bounds, "ref": ref} for bounds in body_boxes
            )
            for pad in pads:
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and pad.IsOnLayer(pcbnew.B_Cu):
                    classes["choc_socket_fillets"].append(
                        {
                            "kind": "box",
                            "bounds": _box(pcbnew, pad),
                            "allowance_mm": FILLET_ALLOWANCE_MM,
                            "ref": ref,
                        }
                    )
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                    classes["mx_pins_pads_fillets"].append(
                        {
                            "kind": "box",
                            "bounds": _box(pcbnew, pad),
                            "allowance_mm": FILLET_ALLOWANCE_MM,
                            "ref": ref,
                        }
                    )
            continue

        if ref.startswith("D") and ref[1:].isdigit():
            for item in graphics:
                if item.GetLayer() in (pcbnew.B_Fab, pcbnew.B_SilkS):
                    classes["diode_body_pads_fillets"].append(
                        {"kind": "box", "bounds": _box(pcbnew, item), "ref": ref}
                    )
            for pad in pads:
                classes["diode_body_pads_fillets"].append(
                    {
                        "kind": "box",
                        "bounds": _box(pcbnew, pad),
                        "allowance_mm": FILLET_ALLOWANCE_MM,
                        "ref": ref,
                    }
                )
            continue

        if ref == "BAT_LEAD_SLOT1":
            for pad in pads:
                drill = pad.GetDrillSize()
                size_x = pcbnew.ToMM(drill.x) or pcbnew.ToMM(pad.GetSize().x)
                size_y = pcbnew.ToMM(drill.y) or pcbnew.ToMM(pad.GetSize().y)
                angle = float(pad.GetOrientation().AsDegrees())
                classes["battery_slot"].append(
                    {
                        "kind": "capsule",
                        "center": _point(pcbnew, pad.GetPosition()),
                        "size_x_mm": size_x,
                        "size_y_mm": size_y,
                        "angle_deg": angle,
                        "allowance_mm": BATTERY_ACCESS_CLEARANCE_MM,
                        "ref": ref,
                    }
                )
            continue

        # nice!nano socket pads and body include the controller and reset/service
        # geometry. Keep every such feature away from a rail or support contact.
        if ref == "U1" or "RESET" in ref.upper():
            for item in graphics:
                if item.GetLayer() in (pcbnew.B_Fab, pcbnew.B_SilkS, pcbnew.F_Fab, pcbnew.F_SilkS):
                    classes["controller_reset"].append(
                        {"kind": "box", "bounds": _box(pcbnew, item), "ref": ref}
                    )
            for pad in pads:
                classes["controller_reset"].append(
                    {
                        "kind": "box",
                        "bounds": _box(pcbnew, pad),
                        "allowance_mm": FILLET_ALLOWANCE_MM,
                        "ref": ref,
                    }
                )

    for track in board.GetTracks():
        if track.GetClass() == "PCB_VIA":
            classes["vias"].append(
                {
                    "kind": "circle",
                    "center": _point(pcbnew, track.GetPosition()),
                    "radius_mm": pcbnew.ToMM(track.GetWidth(pcbnew.F_Cu)) / 2.0,
                }
            )
            continue
        classes["bottom_copper_tracks"].append(
            {
                "kind": "line",
                "start": _point(pcbnew, track.GetStart()),
                "end": _point(pcbnew, track.GetEnd()),
                "radius_mm": pcbnew.ToMM(track.GetWidth()) / 2.0 + TRACK_CLEARANCE_MM,
            }
        )

    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "edge_segments": edge_segments,
        "switches": sorted(switches, key=lambda item: int(item["ref"][2:])),
        "legacy_registration_refs": sorted(legacy_refs),
        "feature_classes": classes,
    }


def extract_geometry() -> None:
    import pcbnew  # type: ignore[import-not-found]

    print(
        json.dumps(
            {"boards": {side: extract_board(pcbnew, path) for side, path in BOARD_PATHS.items()}},
            separators=(",", ":"),
        )
    )


def run_extractor(kicad_python: Path) -> dict[str, Any]:
    proc = subprocess.run(
        [str(kicad_python), str(Path(__file__).resolve()), "--extract-geometry"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    start, end = proc.stdout.find("{"), proc.stdout.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError(f"KiCad housing extractor returned no JSON:\n{proc.stdout}\n{proc.stderr}")
    return json.loads(proc.stdout[start : end + 1])


def _reflect_xy(bounds: tuple[float, float, float, float], x: float, y: float) -> tuple[float, float]:
    min_x, min_y, max_x, _max_y = bounds
    return max_x - x, y - min_y


def _feature_geometry(shp: dict[str, Any], feature: dict[str, Any], bounds: tuple[float, float, float, float]) -> Any:
    kind = feature["kind"]
    allowance = float(feature.get("allowance_mm", 0.0))
    if kind == "box":
        x0, y0, x1, y1 = feature["bounds"]
        ax, ay = _reflect_xy(bounds, x1, y0)
        bx, by = _reflect_xy(bounds, x0, y1)
        geometry = shp["box"](min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))
    elif kind == "circle":
        x, y = _reflect_xy(bounds, *feature["center"])
        geometry = shp["Point"](x, y).buffer(float(feature["radius_mm"]), quad_segs=16)
    elif kind == "line":
        start = _reflect_xy(bounds, *feature["start"])
        end = _reflect_xy(bounds, *feature["end"])
        geometry = shp["LineString"]([start, end]).buffer(float(feature["radius_mm"]), cap_style="round")
    elif kind == "capsule":
        x, y = _reflect_xy(bounds, *feature["center"])
        size_x = float(feature["size_x_mm"])
        size_y = float(feature["size_y_mm"])
        radius = min(size_x, size_y) / 2.0
        length = max(size_x, size_y) - min(size_x, size_y)
        if length <= 1e-9:
            geometry = shp["Point"](x, y).buffer(radius, quad_segs=12)
        else:
            geometry = shp["LineString"]([(x - length / 2.0, y), (x + length / 2.0, y)]).buffer(
                radius, cap_style="round", quad_segs=12
            )
        angle = -float(feature.get("angle_deg", 0.0))
        if abs(angle) > 1e-9:
            geometry = shp["affinity"].rotate(geometry, angle, origin=(x, y))
    else:
        raise ValueError(f"Unsupported feature kind: {kind}")
    return geometry.buffer(allowance, join_style="round", quad_segs=12) if allowance else geometry


def build_plan_geometry(shp: dict[str, Any], side: str, board_data: dict[str, Any]) -> dict[str, Any]:
    raw_board = legacy_geometry.board_polygon(shp, board_data["edge_segments"])
    bounds = tuple(float(value) for value in raw_board.bounds)
    min_x, min_y, max_x, max_y = bounds
    translated = shp["affinity"].translate(raw_board, xoff=-min_x, yoff=-min_y)
    board = shp["affinity"].scale(
        translated,
        xfact=-1.0,
        yfact=1.0,
        origin=((max_x - min_x) / 2.0, (max_y - min_y) / 2.0),
    )
    if board.geom_type != "Polygon":
        board = max(board.geoms, key=lambda item: item.area)

    feature_geometries: dict[str, Any] = {}
    for name, features in board_data["feature_classes"].items():
        parts = [_feature_geometry(shp, feature, bounds) for feature in features]
        feature_geometries[name] = shp["unary_union"](parts) if parts else shp["Polygon"]()

    rail_outer = board.buffer(-RAIL_INSET_MM, join_style="round", quad_segs=16)
    rail_inner = board.buffer(-(RAIL_INSET_MM + RAIL_WIDTH_MM), join_style="round", quad_segs=16)
    rail = rail_outer.difference(rail_inner)
    forbidden = shp["unary_union"]([geom for geom in feature_geometries.values() if not geom.is_empty])
    rail = rail.difference(forbidden.buffer(POST_CLEARANCE_MM / 2.0, join_style="round", quad_segs=12))
    if not rail.is_valid:
        rail = rail.buffer(0)

    switches = [
        {
            "ref": switch["ref"],
            "center": list(_reflect_xy(bounds, *switch["center"])),
        }
        for switch in board_data["switches"]
    ]
    posts = choose_support_posts(shp, side, board, rail, forbidden, switches)
    return {
        "board": board,
        "raw_bounds": bounds,
        "rail": rail,
        "feature_geometries": feature_geometries,
        "switches": switches,
        "support_posts": posts,
    }


def _candidate_offsets(radius_mm: float = 13.0, step_mm: float = 0.5) -> list[tuple[float, float]]:
    limit = int(round(radius_mm / step_mm))
    values = [
        (ix * step_mm, iy * step_mm)
        for ix in range(-limit, limit + 1)
        for iy in range(-limit, limit + 1)
        if math.hypot(ix * step_mm, iy * step_mm) <= radius_mm + 1e-9
    ]
    return sorted(values, key=lambda value: (math.hypot(*value), abs(value[1]), abs(value[0]), value))


def choose_support_posts(
    shp: dict[str, Any],
    side: str,
    board: Any,
    rail: Any,
    forbidden: Any,
    switches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    radius = POST_DIAMETER_MM / 2.0
    allowed = board.buffer(-(radius + POST_CLEARANCE_MM), join_style="round", quad_segs=16)
    blocked = forbidden.buffer(POST_CLEARANCE_MM, join_style="round", quad_segs=12)
    min_x, min_y, max_x, max_y = board.bounds
    key_xs = [item["center"][0] for item in switches]
    key_ys = [item["center"][1] for item in switches]
    key_min_y, key_max_y = min(key_ys), max(key_ys)
    seam_x = min_x if side == "left" else max_x
    seam_sign = 1.0 if side == "left" else -1.0

    anchors: list[tuple[str, float, float]] = []
    for fraction in (0.08, 0.52, 0.88):
        anchors.append(("seam", seam_x + seam_sign * 6.0, key_min_y + (key_max_y - key_min_y) * fraction))

    thumbs = sorted(
        (item for item in switches if item["center"][1] >= key_max_y - 11.0),
        key=lambda item: item["center"][0],
    )
    if thumbs:
        thumb_targets = thumbs if len(thumbs) <= 3 else [thumbs[0], thumbs[len(thumbs) // 2], thumbs[-1]]
        anchors.extend(("thumb", item["center"][0], item["center"][1] - 6.0) for item in thumb_targets)

    for x_fraction in (0.20, 0.42, 0.64, 0.84):
        for y_fraction in (0.27, 0.63):
            anchors.append(
                (
                    "span",
                    min(key_xs) + (max(key_xs) - min(key_xs)) * x_fraction,
                    key_min_y + (key_max_y - key_min_y) * y_fraction,
                )
            )

    posts: list[dict[str, Any]] = []

    def add_near(category: str, target_x: float, target_y: float) -> bool:
        for dx, dy in _candidate_offsets():
            x, y = target_x + dx, target_y + dy
            circle = shp["Point"](x, y).buffer(radius, quad_segs=20)
            if not allowed.covers(circle) or circle.intersects(blocked):
                continue
            if any(math.hypot(x - item["x_mm"], y - item["y_mm"]) < POST_DIAMETER_MM + 1.0 for item in posts):
                continue
            posts.append(
                {
                    "id": f"{side.upper()}-SUP-{len(posts) + 1:02d}",
                    "category": category,
                    "x_mm": round(x, 4),
                    "y_mm": round(y, 4),
                    "diameter_mm": POST_DIAMETER_MM,
                    "bottom_z_mm": FLOOR_THICKNESS_MM,
                    "top_z_mm": PCB_BOTTOM_Z_MM,
                    "nominal_vertical_gap_mm": 0.0,
                    "target_x_mm": round(target_x, 4),
                    "target_y_mm": round(target_y, 4),
                }
            )
            return True
        return False

    for category, x, y in anchors:
        add_near(category, x, y)

    # Close any load point left farther than the requirement's digital support
    # bound. This is conservative; the physical 2 N deflection test remains open.
    for switch in switches:
        point = shp["Point"](*switch["center"])
        post_clearance = min(
            (max(0.0, point.distance(shp["Point"](item["x_mm"], item["y_mm"])) - radius) for item in posts),
            default=float("inf"),
        )
        if min(point.distance(rail), post_clearance) > MAX_LOAD_POINT_TO_SUPPORT_MM:
            add_near("span", *switch["center"])

    categories = {item["category"] for item in posts}
    if not {"seam", "thumb", "span"}.issubset(categories) or len(posts) < 8:
        raise RuntimeError(f"{side}: could not place required safe support categories ({len(posts)} posts, {categories})")
    return posts


def _polygon_workplane(cq: Any, polygon: Any) -> Any:
    outer = [(float(x), float(y)) for x, y in list(polygon.exterior.coords)[:-1]]
    workplane = cq.Workplane("XY").polyline(outer).close()
    for ring in polygon.interiors:
        workplane = workplane.polyline([(float(x), float(y)) for x, y in list(ring.coords)[:-1]]).close()
    return workplane


def _extrude_geometry(cq: Any, geometry: Any, height: float, z_offset: float = 0.0) -> Any | None:
    if geometry.is_empty:
        return None
    parts = [geometry] if geometry.geom_type == "Polygon" else list(geometry.geoms)
    solids = []
    for polygon in parts:
        if polygon.area <= 1e-5:
            continue
        solid = _polygon_workplane(cq, polygon).extrude(height)
        if z_offset:
            solid = solid.translate((0.0, 0.0, z_offset))
        solids.append(solid)
    if not solids:
        return None
    result = solids[0]
    for solid in solids[1:]:
        result = result.union(solid)
    return result


def build_cad(cq: Any, shp: dict[str, Any], plan: dict[str, Any]) -> Any:
    outer = plan["board"].buffer(-OUTLINE_INSET_MM, join_style="round", quad_segs=16)
    housing = _extrude_geometry(cq, outer, FLOOR_THICKNESS_MM)
    rail = _extrude_geometry(cq, plan["rail"], PCB_BOTTOM_Z_MM - FLOOR_THICKNESS_MM, FLOOR_THICKNESS_MM)
    if rail is not None:
        housing = housing.union(rail)
    for post in plan["support_posts"]:
        solid = (
            cq.Workplane("XY")
            .center(post["x_mm"], post["y_mm"])
            .circle(post["diameter_mm"] / 2.0)
            .extrude(PCB_BOTTOM_Z_MM - FLOOR_THICKNESS_MM)
            .translate((0.0, 0.0, FLOOR_THICKNESS_MM))
        )
        housing = housing.union(solid)
    battery = plan["feature_geometries"]["battery_slot"]
    cut = _extrude_geometry(cq, battery, PCB_BOTTOM_Z_MM + 1.0)
    if cut is not None:
        housing = housing.cut(cut)
    return housing.clean()


def _cad_box(cq: Any, x0: float, y0: float, z0: float, x1: float, y1: float, z1: float) -> Any:
    return (
        cq.Workplane("XY")
        .box(x1 - x0, y1 - y0, z1 - z0, centered=(True, True, False))
        .translate(((x0 + x1) / 2.0, (y0 + y1) / 2.0, z0))
    )


def choose_case_join_points(shp: dict[str, Any], plan: dict[str, Any], split_x: float) -> list[dict[str, float]]:
    boss_radius = CASE_JOIN_SCREW_HEAD_ENVELOPE_MM / 2.0
    features = shp["unary_union"](
        [geometry for geometry in plan["feature_geometries"].values() if not geometry.is_empty]
    ).buffer(POST_CLEARANCE_MM, join_style="round", quad_segs=12)
    supports = _support_plan_union(shp, plan["support_posts"]).union(plan["rail"])
    _min_x, min_y, _max_x, _max_y = plan["board"].bounds
    points: list[dict[str, float]] = []
    for target_y_offset in (59.0, 78.5):
        target_y = min_y + target_y_offset
        found = False
        for x_offset in (0.0, 1.0, 2.0, 3.0, -1.0):
            x = split_x + RIGHT_LAP_OVERLAP_MM / 2.0 + x_offset
            for offset in [0.0, 1.0, -1.0, 2.0, -2.0, 3.0, -3.0, 4.0, -4.0, 5.0, -5.0, 6.0, -6.0, 8.0, -8.0, 10.0, -10.0]:
                y = target_y + offset
                envelope = shp["Point"](x, y).buffer(boss_radius, quad_segs=20)
                if not plan["board"].covers(envelope):
                    continue
                if envelope.intersects(features) or envelope.intersects(supports):
                    continue
                if any(abs(y - point["y_mm"]) < CASE_JOIN_SCREW_HEAD_ENVELOPE_MM + 4.0 for point in points):
                    continue
                points.append({"x_mm": round(x, 4), "y_mm": round(y, 4)})
                found = True
                break
            if found:
                break
    if len(points) != 2:
        raise RuntimeError(f"right: could not place two collision-free case-join fasteners ({points})")
    return points


def _support_plan_union(shp: dict[str, Any], posts: list[dict[str, Any]]) -> Any:
    return shp["unary_union"](
        [
            shp["Point"](post["x_mm"], post["y_mm"]).buffer(
                post["diameter_mm"] / 2.0,
                quad_segs=20,
            )
            for post in posts
        ]
    )


def split_right_housing(cq: Any, shp: dict[str, Any], housing: Any, plan: dict[str, Any]) -> tuple[list[Any], dict[str, Any]]:
    min_x, min_y, max_x, max_y = plan["board"].bounds
    split_x = (min_x + max_x) / 2.0
    half_gap = RIGHT_SPLIT_CLEARANCE_MM / 2.0
    margin = 2.0
    left_cutter = _cad_box(cq, min_x - margin, min_y - margin, -margin, split_x - half_gap, max_y + margin, PCB_BOTTOM_Z_MM + margin)
    right_cutter = _cad_box(cq, split_x + half_gap, min_y - margin, -margin, max_x + margin, max_y + margin, PCB_BOTTOM_Z_MM + margin)
    part_a = housing.intersect(left_cutter)
    part_b = housing.intersect(right_cutter)

    lap_region = _cad_box(
        cq,
        split_x - half_gap,
        min_y - margin,
        0.0,
        split_x + RIGHT_LAP_OVERLAP_MM,
        max_y + margin,
        RIGHT_LAP_THICKNESS_MM,
    )
    lower_lap = housing.intersect(lap_region)
    part_a = part_a.union(lower_lap)
    upper_relief = _cad_box(
        cq,
        split_x + half_gap,
        min_y - margin,
        0.0,
        split_x + RIGHT_LAP_OVERLAP_MM + half_gap,
        max_y + margin,
        RIGHT_LAP_THICKNESS_MM + RIGHT_LAP_VERTICAL_CLEARANCE_MM,
    )
    part_b = part_b.cut(upper_relief)

    joint_points = choose_case_join_points(shp, plan, split_x)
    for point in joint_points:
        x, y = point["x_mm"], point["y_mm"]
        clamp_collar = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(CASE_JOIN_CLAMP_COLLAR_DIAMETER_MM / 2.0)
            .extrude(CASE_JOIN_CLAMP_COLLAR_TOP_Z_MM)
        )
        head_recess = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(CASE_JOIN_HEAD_RECESS_DIAMETER_MM / 2.0)
            .extrude(CASE_JOIN_HEAD_SEAT_Z_MM + 0.01)
        )
        shank_clearance = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(CASE_JOIN_CLEARANCE_HOLE_DIAMETER_MM / 2.0)
            .extrude(CASE_JOIN_CLAMP_COLLAR_TOP_Z_MM + 0.1 - CASE_JOIN_HEAD_SEAT_Z_MM)
            .translate((0.0, 0.0, CASE_JOIN_HEAD_SEAT_Z_MM))
        )
        receiving_boss = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(CASE_JOIN_BOSS_DIAMETER_MM / 2.0)
            .extrude(CASE_JOIN_BOSS_TOP_Z_MM - CASE_JOIN_RECEIVING_PILOT_START_Z_MM)
            .translate((0.0, 0.0, CASE_JOIN_RECEIVING_PILOT_START_Z_MM))
        )
        receiving_pilot = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(CASE_JOIN_PILOT_DIAMETER_MM / 2.0)
            .extrude(CASE_JOIN_RECEIVING_PILOT_TOP_Z_MM - CASE_JOIN_RECEIVING_PILOT_START_Z_MM)
            .translate((0.0, 0.0, CASE_JOIN_RECEIVING_PILOT_START_Z_MM))
        )
        part_a = part_a.union(clamp_collar).cut(head_recess).cut(shank_clearance)
        part_b = part_b.union(receiving_boss).cut(receiving_pilot)

    parts = [part_a.clean(), part_b.clean()]
    if any(len(part.solids().vals()) != 1 for part in parts):
        raise RuntimeError(
            "right split did not produce two single-solid printable parts: "
            f"{[len(part.solids().vals()) for part in parts]}"
        )
    official_length_min = CASE_JOIN_UNDER_HEAD_LENGTH_MM + CASE_JOIN_LENGTH_LOWER_TOLERANCE_MM
    official_length_max = CASE_JOIN_UNDER_HEAD_LENGTH_MM + CASE_JOIN_LENGTH_UPPER_TOLERANCE_MM
    clamp_stack = CASE_JOIN_RECEIVING_PILOT_START_Z_MM - CASE_JOIN_HEAD_SEAT_Z_MM
    worst_clamp_stack_min = clamp_stack - 2.0 * CASE_JOIN_FDM_Z_TOLERANCE_MM
    worst_clamp_stack_max = clamp_stack + 2.0 * CASE_JOIN_FDM_Z_TOLERANCE_MM
    worst_head_exterior_face = (
        CASE_JOIN_HEAD_SEAT_Z_MM
        - CASE_JOIN_FDM_Z_TOLERANCE_MM
        - CASE_JOIN_SCREW_HEAD_HEIGHT_MAX_MM
    )
    worst_tip_top = (
        CASE_JOIN_HEAD_SEAT_Z_MM
        + CASE_JOIN_PART_A_SEAT_FDM_TOLERANCE_MM
        + official_length_max
    )
    installed_tip_to_boss_top_clearance = (
        CASE_JOIN_BOSS_TOP_Z_MM
        - CASE_JOIN_PART_B_BOSS_FDM_TOLERANCE_MM
        - worst_tip_top
    )
    installed_tip_to_pcb_clearance = (
        PCB_BOTTOM_Z_MM
        - CASE_JOIN_SUPPORT_PLANE_FDM_TOLERANCE_MM
        - worst_tip_top
    )
    worst_case = {
        "screw_length_min_mm": round(official_length_min, 4),
        "screw_length_max_mm": round(official_length_max, 4),
        "clamp_stack_min_mm": round(worst_clamp_stack_min, 4),
        "clamp_stack_max_mm": round(worst_clamp_stack_max, 4),
        "usable_pilot_depth_mm": round(
            CASE_JOIN_RECEIVING_PILOT_TOP_Z_MM
            - CASE_JOIN_FDM_Z_TOLERANCE_MM
            - (CASE_JOIN_RECEIVING_PILOT_START_Z_MM + CASE_JOIN_FDM_Z_TOLERANCE_MM),
            4,
        ),
        "maximum_threaded_penetration_into_pilot_mm": round(
            worst_tip_top
            - (CASE_JOIN_RECEIVING_PILOT_START_Z_MM - CASE_JOIN_FDM_Z_TOLERANCE_MM)
            - CASE_JOIN_TIP_ALLOWANCE_MM,
            4,
        ),
        "effective_thread_engagement_mm": round(
            official_length_min - worst_clamp_stack_max - CASE_JOIN_TIP_ALLOWANCE_MM,
            4,
        ),
        "receiving_pilot_blind_cap_mm": round(
            CASE_JOIN_BOSS_TOP_Z_MM
            - CASE_JOIN_FDM_Z_TOLERANCE_MM
            - (CASE_JOIN_RECEIVING_PILOT_TOP_Z_MM + CASE_JOIN_FDM_Z_TOLERANCE_MM),
            4,
        ),
        "head_exterior_face_z_mm": round(worst_head_exterior_face, 4),
        "head_exterior_protrusion_mm": round(max(0.0, -worst_head_exterior_face), 4),
        "screw_tip_top_z_mm": round(worst_tip_top, 4),
        "installed_screw_tip_to_boss_top_clearance_mm": round(
            installed_tip_to_boss_top_clearance, 4
        ),
        "installed_screw_tip_to_pcb_clearance_mm": round(
            installed_tip_to_pcb_clearance, 4
        ),
    }
    metadata = {
        "type": "overlap_lap_with_m2_case_join",
        "part_count": 2,
        "split_x_mm": round(split_x, 4),
        "nominal_plan_clearance_mm": RIGHT_SPLIT_CLEARANCE_MM,
        "lap_overlap_mm": RIGHT_LAP_OVERLAP_MM,
        "lap_thickness_mm": RIGHT_LAP_THICKNESS_MM,
        "lap_vertical_clearance_mm": RIGHT_LAP_VERTICAL_CLEARANCE_MM,
        "case_join_fastener_count": len(joint_points),
        "case_join_fasteners": joint_points,
        "case_join_boss_diameter_mm": CASE_JOIN_BOSS_DIAMETER_MM,
        "case_join_pilot_diameter_mm": CASE_JOIN_PILOT_DIAMETER_MM,
        "receiving_pilot_start_z_mm": CASE_JOIN_RECEIVING_PILOT_START_Z_MM,
        "receiving_pilot_top_z_mm": CASE_JOIN_RECEIVING_PILOT_TOP_Z_MM,
        "case_join_clearance_hole_diameter_mm": CASE_JOIN_CLEARANCE_HOLE_DIAMETER_MM,
        "case_join_clamp_collar_diameter_mm": CASE_JOIN_CLAMP_COLLAR_DIAMETER_MM,
        "case_join_clamp_collar_top_z_mm": CASE_JOIN_CLAMP_COLLAR_TOP_Z_MM,
        "case_join_head_recess_diameter_mm": CASE_JOIN_HEAD_RECESS_DIAMETER_MM,
        "case_join_screw_head_diameter_mm": CASE_JOIN_SCREW_HEAD_DIAMETER_NOMINAL_MM,
        "case_join_screw_head_height_mm": CASE_JOIN_SCREW_HEAD_HEIGHT_NOMINAL_MM,
        "case_join_screw_head_envelope_mm": CASE_JOIN_SCREW_HEAD_ENVELOPE_MM,
        "head_recess_depth_mm": CASE_JOIN_HEAD_RECESS_DEPTH_MM,
        "head_seat_z_mm": CASE_JOIN_HEAD_SEAT_Z_MM,
        "clamp_stack_mm": round(clamp_stack, 4),
        "assembly_direction": "bottom_up",
        "head_exterior_face_nominal_z_mm": round(
            CASE_JOIN_HEAD_SEAT_Z_MM - CASE_JOIN_SCREW_HEAD_HEIGHT_NOMINAL_MM, 4
        ),
        "head_exterior_protrusion_max_mm": worst_case["head_exterior_protrusion_mm"],
        "pcb_bottom_z_mm": PCB_BOTTOM_Z_MM,
        "screw_tip_to_pcb_clearance_mm": worst_case[
            "installed_screw_tip_to_pcb_clearance_mm"
        ],
        "case_join_boss_top_z_mm": CASE_JOIN_BOSS_TOP_Z_MM,
        "fastener_spec": {
            "part_number": CASE_JOIN_FASTENER_PART_NUMBER,
            "reference": CASE_JOIN_FASTENER_REFERENCE,
            "thread": CASE_JOIN_THREAD,
            "under_head_length_mm": CASE_JOIN_UNDER_HEAD_LENGTH_MM,
            "official_under_head_length_min_mm": round(official_length_min, 4),
            "official_under_head_length_max_mm": round(official_length_max, 4),
            "official_length_lower_tolerance_mm": CASE_JOIN_LENGTH_LOWER_TOLERANCE_MM,
            "official_length_upper_tolerance_mm": CASE_JOIN_LENGTH_UPPER_TOLERANCE_MM,
            "official_head_diameter_min_mm": CASE_JOIN_SCREW_HEAD_DIAMETER_MIN_MM,
            "official_head_diameter_max_mm": CASE_JOIN_SCREW_HEAD_DIAMETER_MAX_MM,
            "official_head_height_min_mm": CASE_JOIN_SCREW_HEAD_HEIGHT_MIN_MM,
            "official_head_height_max_mm": CASE_JOIN_SCREW_HEAD_HEIGHT_MAX_MM,
            "shank_clearance_hole_diameter_mm": CASE_JOIN_CLEARANCE_HOLE_DIAMETER_MM,
            "head_recess_diameter_mm": CASE_JOIN_HEAD_RECESS_DIAMETER_MM,
            "head_recess_radial_print_clearance_mm": round(
                (CASE_JOIN_HEAD_RECESS_DIAMETER_MM - CASE_JOIN_SCREW_HEAD_DIAMETER_MAX_MM) / 2.0,
                4,
            ),
            "minimum_radial_head_bearing_mm": round(
                (CASE_JOIN_SCREW_HEAD_DIAMETER_MIN_MM - CASE_JOIN_CLEARANCE_HOLE_DIAMETER_MM) / 2.0,
                4,
            ),
            "minimum_radial_collar_wall_mm": round(
                (CASE_JOIN_CLAMP_COLLAR_DIAMETER_MM - CASE_JOIN_HEAD_RECESS_DIAMETER_MM) / 2.0,
                4,
            ),
            "fdm_z_tolerance_mm": CASE_JOIN_FDM_Z_TOLERANCE_MM,
            "part_a_seat_fdm_tolerance_mm": CASE_JOIN_PART_A_SEAT_FDM_TOLERANCE_MM,
            "part_b_boss_fdm_tolerance_mm": CASE_JOIN_PART_B_BOSS_FDM_TOLERANCE_MM,
            "support_plane_fdm_tolerance_mm": CASE_JOIN_SUPPORT_PLANE_FDM_TOLERANCE_MM,
            "minimum_installed_clearance_mm": CASE_JOIN_MIN_INSTALLED_CLEARANCE_MM,
            "installed_screw_tip_to_boss_top_clearance_formula": (
                "(boss_top_nominal - part_b_boss_fdm_tolerance) - "
                "(head_seat_nominal + part_a_seat_fdm_tolerance + screw_length_max)"
            ),
            "installed_screw_tip_to_pcb_clearance_formula": (
                "(pcb_bottom_nominal - support_plane_fdm_tolerance) - "
                "(head_seat_nominal + part_a_seat_fdm_tolerance + screw_length_max)"
            ),
            "drive": CASE_JOIN_DRIVE,
            "driver_access_direction": "bottom_downward",
            "driver_shaft_diameter_mm": CASE_JOIN_DRIVER_SHAFT_DIAMETER_MM,
            "driver_access_height_mm": CASE_JOIN_DRIVER_ACCESS_HEIGHT_MM,
            "tip_allowance_mm": CASE_JOIN_TIP_ALLOWANCE_MM,
            "minimum_effective_thread_engagement_mm": CASE_JOIN_MIN_EFFECTIVE_ENGAGEMENT_MM,
            "usable_pilot_depth_mm": round(
                CASE_JOIN_RECEIVING_PILOT_TOP_Z_MM - CASE_JOIN_RECEIVING_PILOT_START_Z_MM, 4
            ),
            "effective_thread_engagement_mm": round(
                CASE_JOIN_UNDER_HEAD_LENGTH_MM - clamp_stack - CASE_JOIN_TIP_ALLOWANCE_MM, 4
            ),
            "worst_case": worst_case,
        },
        "glue_assumed": False,
        "assembly": (
            "Slide the lower lap under part B, then install exactly two SUNCO "
            "CSPSL-ST3W-M2-3 M2x3 Phillips #0 slim-head screws upward from the "
            "exterior bottom into part B's blind receiving pilots."
        ),
    }
    return parts, metadata


def model_bounds(model: Any) -> dict[str, list[float]]:
    bounds = model.val().BoundingBox()
    return {
        "bounds_xyz_mm": [
            round(float(bounds.xmin), 4),
            round(float(bounds.ymin), 4),
            round(float(bounds.zmin), 4),
            round(float(bounds.xmax), 4),
            round(float(bounds.ymax), 4),
            round(float(bounds.zmax), 4),
        ],
        "size_xyz_mm": [
            round(float(bounds.xlen), 4),
            round(float(bounds.ylen), 4),
            round(float(bounds.zlen), 4),
        ],
    }


def _maximum_load_distance(shp: dict[str, Any], plan: dict[str, Any]) -> float:
    radius = POST_DIAMETER_MM / 2.0
    distances = []
    for switch in plan["switches"]:
        point = shp["Point"](*switch["center"])
        post_distance = min(
            max(0.0, point.distance(shp["Point"](post["x_mm"], post["y_mm"])) - radius)
            for post in plan["support_posts"]
        )
        distances.append(min(point.distance(plan["rail"]), post_distance))
    return max(distances)


def generate_outputs(output_dir: Path, kicad_python: Path) -> Path:
    import cadquery as cq

    shp = legacy_geometry.require_shapely()
    extracted = run_extractor(kicad_python)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "requirement": REQUIREMENT,
        "variant": VARIANT,
        "generated_by": "tools/generate_kc2_x3_v2_housings.py",
        "generator_sha256": sha256_path(GENERATOR_PATH),
        "coordinate_system": "board-local, X-reflected physical lower-housing assembly view",
        "parameters": {
            "floor_thickness_mm": FLOOR_THICKNESS_MM,
            "bottom_component_clearance_mm": BOTTOM_COMPONENT_CLEARANCE_MM,
            "pcb_bottom_z_mm": PCB_BOTTOM_Z_MM,
            "pcb_thickness_mm": PCB_THICKNESS_MM,
            "outline_inset_mm": OUTLINE_INSET_MM,
            "rail_inset_mm": RAIL_INSET_MM,
            "rail_width_mm": RAIL_WIDTH_MM,
            "support_post_diameter_mm": POST_DIAMETER_MM,
            "support_clearance_mm": POST_CLEARANCE_MM,
            "fillet_allowance_mm": FILLET_ALLOWANCE_MM,
            "maximum_load_point_to_support_mm": MAX_LOAD_POINT_TO_SUPPORT_MM,
            "print_volume_limit_mm": PRINT_VOLUME_LIMIT_MM,
        },
        "retention": {
            "registration_peg_count": 0,
            "screw_pilot_count": 0,
            "fastener_boss_count": 0,
            "glue_assumed": False,
            "note": "PCB retention is intentionally unresolved; rails/posts are independent vertical load paths.",
        },
        "physical_deflection_test": {
            "status": "pending",
            "load_n": 2.0,
            "maximum_displacement_mm": 0.30,
        },
        "outputs": {},
    }

    for side in ("left", "right"):
        board_data = extracted["boards"][side]
        plan = build_plan_geometry(shp, side, board_data)
        housing = build_cad(cq, shp, plan)
        step_path = output_dir / f"kc2_{side}_x3_v2_lower_housing.step"
        split_joint = None
        if side == "right":
            parts, split_joint = split_right_housing(cq, shp, housing, plan)
            export_model = cq.Workplane(obj=cq.Compound.makeCompound([part.val() for part in parts]))
        else:
            parts = [housing]
            export_model = housing
        cq.exporters.export(export_model, str(step_path), exportType="STEP", tolerance=0.001, angularTolerance=0.1, unit="MM")
        normalize_exported_text(step_path)
        printable_parts = []
        for index, part in enumerate(parts):
            suffix = "" if side == "left" else f"_part_{chr(ord('a') + index)}"
            stl_path = output_dir / f"kc2_{side}_x3_v2_lower_housing{suffix}.stl"
            cq.exporters.export(part, str(stl_path), exportType="STL", tolerance=0.03, angularTolerance=0.08, opt={"ascii": True})
            normalize_exported_text(stl_path)
            dimensions = model_bounds(part)
            if any(value > PRINT_VOLUME_LIMIT_MM for value in dimensions["size_xyz_mm"]):
                raise RuntimeError(f"{stl_path.name} exceeds {PRINT_VOLUME_LIMIT_MM} mm: {dimensions['size_xyz_mm']}")
            printable_parts.append(
                {
                    "name": "whole" if side == "left" else f"part_{chr(ord('a') + index)}",
                    "stl": str(stl_path.relative_to(ROOT)).replace("\\", "/"),
                    "stl_sha256": sha256_path(stl_path),
                    "solid_count": len(part.solids().vals()),
                    "volume_mm3": round(sum(float(solid.Volume()) for solid in part.solids().vals()), 3),
                    **dimensions,
                }
            )
        stale_right_stl = output_dir / "kc2_right_x3_v2_lower_housing.stl"
        if side == "right" and stale_right_stl.exists():
            stale_right_stl.unlink()
        manifest["outputs"][side] = {
            "source_board": board_data["path"],
            "source_board_sha256": sha256_path(BOARD_PATHS[side]),
            "key_count": len(board_data["switches"]),
            "legacy_registration_refs": board_data["legacy_registration_refs"],
            "step": str(step_path.relative_to(ROOT)).replace("\\", "/"),
            "step_sha256": sha256_path(step_path),
            "step_has_trailing_whitespace": has_trailing_horizontal_whitespace(step_path),
            "printable_parts": printable_parts,
            "rail": {
                "top_z_mm": PCB_BOTTOM_Z_MM,
                "nominal_vertical_gap_mm": 0.0,
                "plan_area_mm2": round(plan["rail"].area, 4),
                "segment_count": 1 if plan["rail"].geom_type == "Polygon" else len(plan["rail"].geoms),
                "near_continuous": True,
                "clearance_cut_around_board_features": True,
            },
            "support_posts": plan["support_posts"],
            "maximum_load_point_to_support_mm": round(_maximum_load_distance(shp, plan), 4),
            "solid_count": len(parts),
            "volume_mm3": round(sum(float(solid.Volume()) for part in parts for solid in part.solids().vals()), 3),
        }
        if split_joint is not None:
            manifest["outputs"][side]["split_joint"] = split_joint

    manifest_path = output_dir / MANIFEST_PATH.name
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {manifest_path.relative_to(ROOT)}")
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate CON-ARCH-006 draft X3 V2 lower housings")
    parser.add_argument("--extract-geometry", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--kicad-python", type=Path)
    args = parser.parse_args()
    if args.extract_geometry:
        extract_geometry()
        return 0
    generate_outputs(args.output_dir, args.kicad_python or legacy_geometry.locate_kicad_python())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
