"""Generate the draft KC2 X3 V2 2.50 mm lower support plates.

The V2 design is intentionally independent of the promoted 77-key housing.
It subtracts exterior-open underside-component envelopes from the current draft
V2 board outlines and never uses REG/H holes, pegs, pilots, or key-field screws.
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

EXTERIOR_BOTTOM_Z_MM = 0.00
HOUSING_HEIGHT_MM = 2.50
PCB_BOTTOM_Z_MM = HOUSING_HEIGHT_MM
PCB_THICKNESS_MM = 1.60
OUTLINE_INSET_MM = 0.10
RAIL_INSET_MM = 0.10
RAIL_WIDTH_MM = 0.65
POST_DIAMETER_MM = 2.00
POST_CLEARANCE_MM = 0.30
FILLET_ALLOWANCE_MM = 0.30
COMPONENT_MINIMUM_CLEARANCE_MM = 0.30
COMPONENT_CUTOUT_CLEARANCE_MM = 0.35
COMPONENT_CUTOUT_SIMPLIFY_MM = 0.02
MIN_DIODE_HOUSING_PERIMETER_LAND_MM = 0.85
CHOC_SOCKET_OFFICIAL_BODY_DEPTH_MAX_MM = 2.30
CHOC_SOCKET_ASSEMBLY_ALLOWANCE_MM = 0.10
DIODE_OFFICIAL_BODY_DEPTH_MAX_MM = 1.35
DIODE_SOLDER_FILLET_DEPTH_ALLOWANCE_MM = 0.30
CHOC_SOCKET_OFFICIAL_SOURCE = "https://www.kailhswitch.com/uploads/15927/files/CPG135001S30.pdf"
DIODE_OFFICIAL_SOURCE = "https://www.vishay.com/docs/86356/1n4148w.pdf"
TRACK_CLEARANCE_MM = 0.15
BATTERY_ACCESS_CLEARANCE_MM = 0.70
MAX_LOAD_POINT_TO_SUPPORT_MM = 24.0
PRINT_VOLUME_LIMIT_MM = 150.0
RIGHT_SPLIT_CLEARANCE_MM = 0.20
PUZZLE_CAPTURE_FEATURE_COUNT = 2
PUZZLE_NECK_WIDTH_MM = 2.00
PUZZLE_HEAD_DIAMETER_MM = 4.50
PUZZLE_NECK_LENGTH_MM = 3.00
PUZZLE_MIN_CAPTURE_PER_SIDE_MM = 1.00


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
        "switch_mechanical_pins": [],
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
            if body_boxes:
                classes["choc_socket_body"].append(
                    {
                        "kind": "box",
                        "bounds": [
                            min(bounds[0] for bounds in body_boxes),
                            min(bounds[1] for bounds in body_boxes),
                            max(bounds[2] for bounds in body_boxes),
                            max(bounds[3] for bounds in body_boxes),
                        ],
                        "ref": ref,
                    }
                )
            for pad in pads:
                if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
                    classes["switch_mechanical_pins"].append(
                        {
                            "kind": "box",
                            "bounds": _box(pcbnew, pad),
                            "ref": ref,
                        }
                    )
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
            body_boxes = [
                _box(pcbnew, item)
                for item in graphics
                if item.GetLayer() in (pcbnew.B_Fab, pcbnew.B_SilkS)
            ]
            if body_boxes:
                classes["diode_body_pads_fillets"].append(
                    {
                        "kind": "box",
                        "bounds": [
                            min(bounds[0] for bounds in body_boxes),
                            min(bounds[1] for bounds in body_boxes),
                            max(bounds[2] for bounds in body_boxes),
                            max(bounds[3] for bounds in body_boxes),
                        ],
                        "ref": ref,
                    }
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
    return geometry.buffer(allowance, join_style="round", quad_segs=4) if allowance else geometry


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

    cutout_sources = {
        "choc_socket_body_fillets": ("choc_socket_body", "choc_socket_fillets"),
        "switch_mechanical_pins": ("switch_mechanical_pins",),
        "mx_pins_pads_fillets": ("mx_pins_pads_fillets",),
        "diode_body_pads_fillets": ("diode_body_pads_fillets",),
        "controller_reset": ("controller_reset",),
        "battery_slot": ("battery_slot",),
    }
    component_geometries: dict[str, Any] = {}
    component_cutout_geometries: dict[str, Any] = {}
    component_cutout_counts: dict[str, int] = {}
    for name, source_names in cutout_sources.items():
        sources = [feature_geometries[source] for source in source_names]
        raw = shp["unary_union"]([geometry for geometry in sources if not geometry.is_empty])
        component_geometries[name] = raw
        component_cutout_geometries[name] = (
            raw.buffer(
                COMPONENT_CUTOUT_CLEARANCE_MM,
                join_style="round",
                quad_segs=4,
            )
            if not raw.is_empty
            else shp["Polygon"]()
        )
        refs = {
            feature.get("ref")
            for source in source_names
            for feature in board_data["feature_classes"][source]
            if feature.get("ref")
        }
        component_cutout_counts[name] = len(refs)

    housing_outline = board.buffer(-OUTLINE_INSET_MM, join_style="round", quad_segs=8)
    all_component_cutouts = shp["unary_union"](
        [geometry for geometry in component_cutout_geometries.values() if not geometry.is_empty]
    )
    support_surface = housing_outline.difference(all_component_cutouts)
    if not support_surface.is_valid:
        support_surface = support_surface.buffer(0)
    support_surface = support_surface.simplify(
        COMPONENT_CUTOUT_SIMPLIFY_MM,
        preserve_topology=True,
    )
    # Edge-adjacent component apertures can leave tiny disconnected slivers of
    # the inset outline. They cannot carry load or form a printable one-piece
    # plate, so retain only the connected primary support body.
    if support_surface.geom_type != "Polygon":
        support_surface = max(support_surface.geoms, key=lambda geometry: geometry.area)

    rail_outer = board.buffer(-RAIL_INSET_MM, join_style="round", quad_segs=16)
    rail_inner = board.buffer(-(RAIL_INSET_MM + RAIL_WIDTH_MM), join_style="round", quad_segs=16)
    rail = rail_outer.difference(rail_inner).intersection(support_surface)
    forbidden = shp["unary_union"]([geom for geom in feature_geometries.values() if not geom.is_empty])
    if not rail.is_valid:
        rail = rail.buffer(0)

    switches = [
        {
            "ref": switch["ref"],
            "center": list(_reflect_xy(bounds, *switch["center"])),
        }
        for switch in board_data["switches"]
    ]
    posts = choose_support_posts(
        shp,
        side,
        support_surface,
        rail,
        all_component_cutouts,
        switches,
    )
    return {
        "board": board,
        "housing_outline": housing_outline,
        "support_surface": support_surface,
        "raw_bounds": bounds,
        "rail": rail,
        "feature_geometries": feature_geometries,
        "component_geometries": component_geometries,
        "component_cutout_geometries": component_cutout_geometries,
        "component_cutout_counts": component_cutout_counts,
        "all_component_cutouts": all_component_cutouts,
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
        anchors.append(("seam", seam_x + seam_sign * 14.0, key_min_y + (key_max_y - key_min_y) * fraction))

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
                    "bottom_z_mm": EXTERIOR_BOTTOM_Z_MM,
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
    if not {"thumb", "span"}.issubset(categories) or len(posts) < 6:
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
    # Extrude the already-differenced support surface directly. This produces
    # the same exterior-open component apertures without an expensive sequence
    # of hundreds of 3D boolean cuts.
    housing = _extrude_geometry(cq, plan["support_surface"], HOUSING_HEIGHT_MM)
    if housing is None:
        raise RuntimeError("component cutouts removed the entire housing support surface")
    return housing.clean()


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




def _puzzle_key_geometry(shp: dict[str, Any], split_x: float, y: float) -> Any:
    half_gap = RIGHT_SPLIT_CLEARANCE_MM / 2.0
    head_x = split_x + PUZZLE_NECK_LENGTH_MM
    neck = shp["box"](
        split_x - half_gap,
        y - PUZZLE_NECK_WIDTH_MM / 2.0,
        head_x,
        y + PUZZLE_NECK_WIDTH_MM / 2.0,
    )
    head = shp["Point"](head_x, y).buffer(
        PUZZLE_HEAD_DIAMETER_MM / 2.0,
        quad_segs=24,
    )
    return neck.union(head)


def build_right_split_plan(shp: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    min_x, min_y, max_x, max_y = plan["housing_outline"].bounds
    split_x = (min_x + max_x) / 2.0
    half_gap = RIGHT_SPLIT_CLEARANCE_MM / 2.0
    margin = 2.0
    explicit_supports = _support_plan_union(shp, plan["support_posts"]).union(plan["rail"])
    component_cutouts = plan["all_component_cutouts"]
    capture_points: list[dict[str, float]] = []
    keys: list[Any] = []
    for target_offset in (78.0, 91.0):
        found = False
        for y_offset in (
            0.0,
            0.5,
            -0.5,
            1.0,
            -1.0,
            1.5,
            -1.5,
            2.0,
            -2.0,
            2.5,
            -2.5,
            3.0,
            -3.0,
            4.0,
            -4.0,
            5.0,
            -5.0,
        ):
            y = min_y + target_offset + y_offset
            key = _puzzle_key_geometry(shp, split_x, y)
            slot = key.buffer(RIGHT_SPLIT_CLEARANCE_MM, join_style="round", quad_segs=20)
            if not plan["housing_outline"].covers(slot):
                continue
            if slot.intersects(component_cutouts) or slot.intersects(explicit_supports):
                continue
            if any(abs(y - point["y_mm"]) < PUZZLE_HEAD_DIAMETER_MM + 4.0 for point in capture_points):
                continue
            capture_points.append(
                {
                    "x_mm": round(split_x + PUZZLE_NECK_LENGTH_MM, 4),
                    "y_mm": round(y, 4),
                }
            )
            keys.append(key)
            found = True
            break
        if not found:
            raise RuntimeError(f"right: could not place keyed puzzle feature near Y={min_y + target_offset}")
    if len(keys) != PUZZLE_CAPTURE_FEATURE_COUNT:
        raise RuntimeError(f"right: expected {PUZZLE_CAPTURE_FEATURE_COUNT} puzzle keys, got {len(keys)}")

    left_base = shp["box"](min_x - margin, min_y - margin, split_x - half_gap, max_y + margin)
    right_base = shp["box"](split_x + half_gap, min_y - margin, max_x + margin, max_y + margin)
    key_union = shp["unary_union"](keys)
    slot_union = key_union.buffer(RIGHT_SPLIT_CLEARANCE_MM, join_style="round", quad_segs=20)
    part_a_plan_raw = plan["support_surface"].intersection(left_base.union(key_union))
    part_b_plan_raw = plan["support_surface"].intersection(right_base.difference(slot_union))

    def primary_polygon(geometry: Any, name: str) -> tuple[Any, float]:
        if geometry.geom_type == "Polygon":
            return geometry, 0.0
        polygons = [polygon for polygon in geometry.geoms if polygon.area > 1e-6]
        primary = max(polygons, key=lambda polygon: polygon.area)
        discarded_ratio = 1.0 - float(primary.area) / float(sum(polygon.area for polygon in polygons))
        if discarded_ratio > 0.02:
            raise RuntimeError(
                f"right keyed split would discard {discarded_ratio:.3%} of {name}; "
                "the split path must be redesigned"
            )
        return primary, discarded_ratio

    part_a_plan, part_a_discarded = primary_polygon(part_a_plan_raw, "part_a")
    part_b_plan, part_b_discarded = primary_polygon(part_b_plan_raw, "part_b")
    return {
        "split_x_mm": round(split_x, 4),
        "capture_points": capture_points,
        "key_union": key_union,
        "slot_union": slot_union,
        "part_a_mask": part_a_plan,
        "part_b_mask": part_b_plan,
        "part_a_plan": part_a_plan,
        "part_b_plan": part_b_plan,
        "discarded_island_area_ratio": [
            round(part_a_discarded, 6),
            round(part_b_discarded, 6),
        ],
        "planned_top_contact_area_mm2": round(float(part_a_plan.area + part_b_plan.area), 4),
    }


def split_right_housing_keyed(
    cq: Any,
    shp: dict[str, Any],
    housing: Any,
    plan: dict[str, Any],
) -> tuple[list[Any], dict[str, Any]]:
    split_plan = build_right_split_plan(shp, plan)
    part_a_cutter = _extrude_geometry(
        cq,
        split_plan["part_a_mask"],
        HOUSING_HEIGHT_MM + 0.20,
        -0.10,
    )
    part_b_cutter = _extrude_geometry(
        cq,
        split_plan["part_b_mask"],
        HOUSING_HEIGHT_MM + 0.20,
        -0.10,
    )
    raw_parts = [housing.intersect(part_a_cutter).clean(), housing.intersect(part_b_cutter).clean()]
    parts: list[Any] = []
    discarded_island_volume_ratio: list[float] = []
    for name, raw_part in zip(("part_a", "part_b"), raw_parts):
        solids = raw_part.solids().vals()
        if not solids:
            raise RuntimeError(f"right keyed split produced no solid for {name}")
        total_volume = sum(float(solid.Volume()) for solid in solids)
        primary = max(solids, key=lambda solid: float(solid.Volume()))
        discarded_ratio = 1.0 - float(primary.Volume()) / total_volume
        if discarded_ratio > 0.02:
            raise RuntimeError(
                f"right keyed split would discard {discarded_ratio:.3%} of {name}; "
                "the split path must be redesigned"
            )
        parts.append(cq.Workplane(obj=primary).clean())
        discarded_island_volume_ratio.append(round(discarded_ratio, 6))
    capture = (PUZZLE_HEAD_DIAMETER_MM - PUZZLE_NECK_WIDTH_MM) / 2.0
    metadata = {
        "type": "full_depth_vertical_keyed_puzzle",
        "part_count": 2,
        "split_x_mm": split_plan["split_x_mm"],
        "nominal_plan_clearance_mm": RIGHT_SPLIT_CLEARANCE_MM,
        "joint_height_mm": HOUSING_HEIGHT_MM,
        "assembly_direction": "vertical",
        "capture_feature_count": len(split_plan["capture_points"]),
        "capture_points": split_plan["capture_points"],
        "neck_width_mm": PUZZLE_NECK_WIDTH_MM,
        "head_width_mm": PUZZLE_HEAD_DIAMETER_MM,
        "neck_length_mm": PUZZLE_NECK_LENGTH_MM,
        "minimum_in_plane_capture_per_side_mm": round(capture, 4),
        "positive_x_capture": capture >= PUZZLE_MIN_CAPTURE_PER_SIDE_MM,
        "fastener_count": 0,
        "discarded_island_area_ratio": split_plan["discarded_island_area_ratio"],
        "discarded_island_volume_ratio": discarded_island_volume_ratio,
        "glue_assumed": False,
        "feature_collision_count": 0,
        "support_collision_count": 0,
        "planned_top_contact_area_mm2": split_plan["planned_top_contact_area_mm2"],
        "assembly": (
            "Lower the two full-depth housing parts together vertically so both keyed "
            "neck-and-head features enter their print-cleared sockets; no screw or adhesive is used."
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


def _maximum_seam_support_distance(shp: dict[str, Any], side: str, plan: dict[str, Any]) -> float:
    min_x, _min_y, max_x, _max_y = plan["board"].bounds
    seam_x = min_x if side == "left" else max_x
    ordered = sorted(
        plan["switches"],
        key=lambda switch: abs(float(switch["center"][0]) - seam_x),
    )
    seam_switches = ordered[:5]
    return max(
        float(shp["Point"](*switch["center"]).distance(plan["support_surface"]))
        for switch in seam_switches
    )


def component_cutout_manifest(plan: dict[str, Any]) -> dict[str, Any]:
    modeled_depths = {
        "choc_socket_body_fillets": {
            "official_body_depth_max_mm": CHOC_SOCKET_OFFICIAL_BODY_DEPTH_MAX_MM,
            "assembly_allowance_mm": CHOC_SOCKET_ASSEMBLY_ALLOWANCE_MM,
            "modeled_max_depth_mm": round(
                CHOC_SOCKET_OFFICIAL_BODY_DEPTH_MAX_MM + CHOC_SOCKET_ASSEMBLY_ALLOWANCE_MM,
                2,
            ),
            "official_source": CHOC_SOCKET_OFFICIAL_SOURCE,
        },
        "switch_mechanical_pins": {
            "official_body_depth_max_mm": None,
            "assembly_allowance_mm": None,
            "modeled_max_depth_mm": None,
            "assembly_note": "Exterior-open cutouts continue every switch NPTH below the PCB.",
        },
        "mx_pins_pads_fillets": {
            "official_body_depth_max_mm": None,
            "assembly_allowance_mm": None,
            "modeled_max_depth_mm": None,
            "assembly_note": "Exterior-open cutouts permit soldering and post-solder lead trimming.",
        },
        "diode_body_pads_fillets": {
            "official_body_depth_max_mm": DIODE_OFFICIAL_BODY_DEPTH_MAX_MM,
            "solder_fillet_allowance_mm": DIODE_SOLDER_FILLET_DEPTH_ALLOWANCE_MM,
            "modeled_max_depth_mm": round(
                DIODE_OFFICIAL_BODY_DEPTH_MAX_MM + DIODE_SOLDER_FILLET_DEPTH_ALLOWANCE_MM,
                2,
            ),
            "official_source": DIODE_OFFICIAL_SOURCE,
        },
        "controller_reset": {
            "official_body_depth_max_mm": None,
            "assembly_allowance_mm": None,
            "modeled_max_depth_mm": None,
        },
        "battery_slot": {
            "official_body_depth_max_mm": None,
            "assembly_allowance_mm": None,
            "modeled_max_depth_mm": None,
        },
    }
    result: dict[str, Any] = {}
    for name, geometry in plan["component_cutout_geometries"].items():
        modeled_depth = modeled_depths[name].get("modeled_max_depth_mm")
        diode_perimeter_fields: dict[str, Any] = {}
        if name == "diode_body_pads_fillets":
            breaks_perimeter = not plan["housing_outline"].covers(geometry)
            diode_perimeter_fields = {
                "breaks_lateral_housing_perimeter": breaks_perimeter,
                "minimum_housing_perimeter_land_mm": round(
                    0.0 if breaks_perimeter else float(geometry.distance(plan["housing_outline"].boundary)),
                    4,
                ),
            }
        result[name] = {
            "opening_count": plan["component_cutout_counts"][name],
            "minimum_xy_clearance_mm": COMPONENT_CUTOUT_CLEARANCE_MM,
            "exterior_open": True,
            "through_opening_z_mm": [EXTERIOR_BOTTOM_Z_MM, HOUSING_HEIGHT_MM],
            "opening_plan_area_mm2": round(float(geometry.area), 4),
            "minimum_exterior_bottom_clearance_mm": (
                None if modeled_depth is None else round(HOUSING_HEIGHT_MM - float(modeled_depth), 2)
            ),
            **diode_perimeter_fields,
            **modeled_depths[name],
        }
    return result


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
            "exterior_bottom_z_mm": EXTERIOR_BOTTOM_Z_MM,
            "housing_height_mm": HOUSING_HEIGHT_MM,
            "pcb_bottom_z_mm": PCB_BOTTOM_Z_MM,
            "pcb_thickness_mm": PCB_THICKNESS_MM,
            "outline_inset_mm": OUTLINE_INSET_MM,
            "rail_inset_mm": RAIL_INSET_MM,
            "rail_width_mm": RAIL_WIDTH_MM,
            "support_post_diameter_mm": POST_DIAMETER_MM,
            "support_clearance_mm": POST_CLEARANCE_MM,
            "fillet_allowance_mm": FILLET_ALLOWANCE_MM,
            "component_minimum_clearance_mm": COMPONENT_MINIMUM_CLEARANCE_MM,
            "component_cutout_clearance_mm": COMPONENT_CUTOUT_CLEARANCE_MM,
            "component_cutout_simplify_mm": COMPONENT_CUTOUT_SIMPLIFY_MM,
            "minimum_diode_housing_perimeter_land_mm": MIN_DIODE_HOUSING_PERIMETER_LAND_MM,
            "maximum_load_point_to_support_mm": MAX_LOAD_POINT_TO_SUPPORT_MM,
            "print_volume_limit_mm": PRINT_VOLUME_LIMIT_MM,
        },
        "retention": {
            "registration_peg_count": 0,
            "screw_pilot_count": 0,
            "fastener_boss_count": 0,
            "glue_assumed": False,
            "note": (
                "PCB retention remains intentionally unresolved; the 2.50 mm plate, perimeter "
                "regions, and distributed contact regions provide the independent vertical load path."
            ),
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
            parts, split_joint = split_right_housing_keyed(cq, shp, housing, plan)
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
            "component_cutouts": component_cutout_manifest(plan),
            "support_posts": plan["support_posts"],
            "maximum_load_point_to_support_mm": round(_maximum_load_distance(shp, plan), 4),
            "maximum_seam_load_point_to_support_mm": round(
                _maximum_seam_support_distance(shp, side, plan),
                4,
            ),
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
