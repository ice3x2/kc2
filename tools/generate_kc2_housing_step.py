"""Generate Fusion-compatible BRep STEP files for the KC2 X3 lower housings."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "hardware" / "case"
CAD_MANIFEST_NAME = "kc2_housing_step_manifest.json"
STL_MANIFEST_NAME = "kc2_housing_manifest.json"

if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import generate_kc2_housings as stl_generator  # noqa: E402


def load_cadquery() -> Any:
    try:
        import cadquery as cq
    except ImportError as exc:
        raise SystemExit("CadQuery is required: python -m pip install cadquery") from exc
    return cq


def polygon_parts(shp: dict[str, Any], geometry: Any) -> list[Any]:
    if geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    if geometry.geom_type == "MultiPolygon":
        return list(geometry.geoms)
    raise RuntimeError(f"Unsupported geometry type: {geometry.geom_type}")


def polygon_workplane(cq: Any, polygon: Any) -> Any:
    points = [(float(x), float(y)) for x, y in polygon.exterior.coords[:-1]]
    if len(points) < 3:
        raise RuntimeError("Cannot build CAD face from fewer than three points")
    return cq.Workplane("XY").polyline(points).close()


def y_plane_volume(
    cq: Any,
    *,
    y_min: float,
    y_max: float,
    x_min: float,
    x_max: float,
    z_at_y_min: float,
    z_at_y_max: float,
    above: bool,
    top_z: float,
) -> Any:
    margin = 10.0
    y0 = y_min - margin
    y1 = y_max + margin
    span = y_max - y_min
    if span <= 1e-9:
        raise RuntimeError("Cannot construct a sloped plane for a zero-height outline")
    slope = (z_at_y_max - z_at_y_min) / span
    z0 = z_at_y_min + slope * (y0 - y_min)
    z1 = z_at_y_max + slope * (y1 - y_max)
    if above:
        profile = [
            (y0, z0),
            (y1, z1),
            (y1, top_z),
            (y0, top_z),
        ]
    else:
        profile = [
            (y0, 0.0),
            (y1, 0.0),
            (y1, z1),
            (y0, z0),
        ]
    return (
        cq.Workplane("YZ", origin=(x_min - margin, 0.0, 0.0))
        .polyline(profile)
        .close()
        .extrude((x_max - x_min) + 2.0 * margin)
    )


def reflected_board_geometry(shp: dict[str, Any], side_data: dict[str, Any]) -> tuple[Any, list[dict[str, float]]]:
    raw = stl_generator.board_polygon(shp, side_data["edge_segments"])
    minx, miny, _maxx, _maxy = raw.bounds
    board = shp["affinity"].translate(raw, xoff=-minx, yoff=-miny)
    board = shp["affinity"].scale(board, xfact=-1.0, yfact=1.0, origin="center")

    points = []
    width = raw.bounds[2] - raw.bounds[0]
    for hole in side_data["registration_holes"]:
        points.append(
            {
                **hole,
                "x": width - (hole["x"] - minx),
                "y": hole["y"] - miny,
            }
        )
    return board, points


def reflected_feature(
    feature: dict[str, Any] | None,
    source_bounds: tuple[float, float, float, float],
) -> dict[str, Any] | None:
    if feature is None:
        return None
    minx, miny, maxx, _maxy = source_bounds
    return {
        **feature,
        "x": (maxx - minx) - (float(feature["x"]) - minx),
        "y": float(feature["y"]) - miny,
    }


def reflected_socket_keepouts(
    shp: dict[str, Any],
    keepouts: list[dict[str, Any]],
    source_bounds: tuple[float, float, float, float],
) -> list[tuple[dict[str, Any], Any]]:
    minx, miny, maxx, maxy = source_bounds
    center = ((maxx - minx) / 2.0, (maxy - miny) / 2.0)
    reflected = []
    for keepout in keepouts:
        geometry = shp["box"](
            float(keepout["min_x"]),
            float(keepout["min_y"]),
            float(keepout["max_x"]),
            float(keepout["max_y"]),
        )
        geometry = shp["affinity"].translate(geometry, xoff=-minx, yoff=-miny)
        geometry = shp["affinity"].scale(
            geometry,
            xfact=-1.0,
            yfact=1.0,
            origin=center,
        )
        reflected.append((keepout, geometry))
    return reflected


def name_ascii_stl(path: Path, solid_name: str) -> None:
    lines = path.read_text(encoding="ascii").splitlines()
    if not lines or not lines[0].startswith("solid") or not lines[-1].startswith("endsolid"):
        raise RuntimeError(f"Unexpected ASCII STL structure: {path}")
    lines[0] = f"solid {solid_name}"
    lines[-1] = f"endsolid {solid_name}"
    path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")


def build_housing(cq: Any, shp: dict[str, Any], side_data: dict[str, Any], params: Any) -> tuple[Any, dict[str, Any]]:
    source_board = stl_generator.board_polygon(shp, side_data["edge_segments"])
    source_bounds = tuple(float(value) for value in source_board.bounds)
    board, reg_holes = reflected_board_geometry(shp, side_data)
    outer = board.buffer(-params.outline_inset_mm, join_style="round", resolution=16)
    if params.bottom_corner_radius_mm > 0:
        outer = outer.buffer(-params.bottom_corner_radius_mm / 2.0, join_style="round", resolution=16).buffer(
            params.bottom_corner_radius_mm / 2.0,
            join_style="round",
            resolution=16,
        )
    if outer.geom_type != "Polygon":
        outer = max(polygon_parts(shp, outer), key=lambda item: item.area)

    cavity = outer.buffer(-params.outer_wall_width_mm, join_style="round", resolution=16)
    if cavity.geom_type != "Polygon":
        cavity = max(polygon_parts(shp, cavity), key=lambda item: item.area)
    socket_keepouts = reflected_socket_keepouts(
        shp,
        side_data.get("socket_keepouts", []),
        source_bounds,
    )
    socket_reliefs = [
        geometry.buffer(
            params.socket_lateral_clearance_mm,
            join_style="round",
            resolution=12,
        )
        for _keepout, geometry in socket_keepouts
    ]
    for (keepout, _geometry), relief in zip(socket_keepouts, socket_reliefs):
        if not outer.covers(relief):
            raise RuntimeError(
                f"{keepout['ref']} socket clearance would break through the housing wall"
            )
    if socket_reliefs:
        cavity = cavity.union(shp["unary_union"](socket_reliefs))
    wall = outer.difference(cavity)
    wall_collision_count = sum(
        geometry.intersection(wall).area > 1e-6
        for _keepout, geometry in socket_keepouts
    )
    minimum_lateral_clearance = min(
        (geometry.distance(wall) for _keepout, geometry in socket_keepouts),
        default=0.0,
    )

    _minx, y_min, maxx, y_max = outer.bounds
    floor_at_min_y = stl_generator.z_at(params.floor_thickness_mm, y_min, y_min, y_max, params)
    floor_at_max_y = stl_generator.z_at(params.floor_thickness_mm, y_max, y_min, y_max, params)
    wall_at_min_y = stl_generator.z_at(params.pcb_bottom_z, y_min, y_min, y_max, params)
    wall_at_max_y = stl_generator.z_at(params.pcb_bottom_z, y_max, y_min, y_max, params)
    peg_at_min_y = stl_generator.z_at(params.peg_top_z, y_min, y_min, y_max, params)
    peg_at_max_y = stl_generator.z_at(params.peg_top_z, y_max, y_min, y_max, params)
    max_z = max(wall_at_min_y, wall_at_max_y, peg_at_min_y, peg_at_max_y) + 0.5

    outer_prism = polygon_workplane(cq, outer).extrude(max_z)
    below_wall_top = y_plane_volume(
        cq,
        y_min=y_min,
        y_max=y_max,
        x_min=_minx,
        x_max=maxx,
        z_at_y_min=wall_at_min_y,
        z_at_y_max=wall_at_max_y,
        above=False,
        top_z=max_z,
    )
    housing = outer_prism.intersect(below_wall_top)

    cavity_prism = polygon_workplane(cq, cavity).extrude(max_z)
    above_floor = y_plane_volume(
        cq,
        y_min=y_min,
        y_max=y_max,
        x_min=_minx,
        x_max=maxx,
        z_at_y_min=floor_at_min_y,
        z_at_y_max=floor_at_max_y,
        above=True,
        top_z=max_z,
    )
    housing = housing.cut(cavity_prism.intersect(above_floor))

    below_peg_top = y_plane_volume(
        cq,
        y_min=y_min,
        y_max=y_max,
        x_min=_minx,
        x_max=maxx,
        z_at_y_min=peg_at_min_y,
        z_at_y_max=peg_at_max_y,
        above=False,
        top_z=max_z,
    )

    for hole in reg_holes:
        x, y = hole["x"], hole["y"]
        support_column = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(params.support_post_diameter_mm / 2.0)
            .extrude(max_z)
        )
        peg_column = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(params.registration_peg_diameter_mm / 2.0)
            .extrude(max_z)
        )
        pilot_column = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(params.screw_pilot_hole_diameter_mm / 2.0)
            .extrude(max_z)
        )
        support = support_column.intersect(above_floor).intersect(below_wall_top)
        peg = peg_column.intersect(above_floor).intersect(below_peg_top)
        pilot = pilot_column.intersect(above_floor).intersect(below_peg_top)
        housing = housing.union(support).union(peg).cut(pilot)

    housing = housing.clean()
    pilot_holes = [
        {
            "ref": hole["ref"],
            "x": hole["x"],
            "y": hole["y"],
            "diameter_mm": params.screw_pilot_hole_diameter_mm,
            "depth_mm": params.peg_top_z - params.floor_thickness_mm,
            "blind_to_floor_top": True,
        }
        for hole in reg_holes
    ]
    battery_slot = reflected_feature(side_data.get("battery_slot"), source_bounds)
    if battery_slot:
        battery_slot = {
            **battery_slot,
            "clearance_mm": params.battery_slot_clearance_mm,
            "housing_floor_cutout": params.battery_floor_cutout_enabled,
        }
    metadata = {
        "source_board": side_data["path"],
        "source_bounds_mm": list(source_bounds),
        "orientation": "x_reflected_for_physical_assembly",
        "output_bounds_xy_mm": list(outer.bounds),
        "registration_holes": reg_holes,
        "pilot_holes": pilot_holes,
        "battery_slot": battery_slot,
        "front_height_mm": params.front_height_mm,
        "rear_height_mm": params.rear_height_mm,
        "rear_height_ratio": params.rear_height_ratio,
        "outer_wall_width_mm": params.outer_wall_width_mm,
        "floor_thickness_mm": params.floor_thickness_mm,
        "socket_body_height_mm": params.socket_body_height_mm,
        "socket_safety_clearance_mm": params.socket_safety_clearance_mm,
        "socket_lateral_clearance_mm": params.socket_lateral_clearance_mm,
        "bottom_component_clearance_mm": params.bottom_component_clearance_mm,
        "support_post_diameter_mm": params.support_post_diameter_mm,
        "registration_peg_diameter_mm": params.registration_peg_diameter_mm,
        "screw_pilot_hole_diameter_mm": params.screw_pilot_hole_diameter_mm,
        "height_profile": {
            "front_edge_y_mm": y_max,
            "rear_controller_edge_y_mm": y_min,
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
        "socket_clearance": {
            "socket_model": "Kailh CPG135001S30",
            "envelope_source": "footprint B.SilkS body plus bottom SMD pads",
            "socket_count": len(socket_keepouts),
            "wall_collision_count": wall_collision_count,
            "minimum_lateral_clearance_to_wall_mm": minimum_lateral_clearance,
            "vertical_clearance_to_floor_mm": params.socket_safety_clearance_mm,
        },
        "solid_count": len(housing.solids().vals()),
        "volume_mm3": housing.val().Volume(),
    }
    return housing, metadata


def generate_outputs(output_dir: Path, kicad_python: Path) -> int:
    cq = load_cadquery()
    shp = stl_generator.require_shapely()
    geometry = stl_generator.run_extractor(kicad_python)
    params = stl_generator.HousingParams()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "format": "STEP",
        "fusion_import": "Upload STEP into Fusion 360; Fusion converts it to a native design.",
        "requirement": "CON-ARCH-003",
        "orientation": "X-reflected to match the physical assembled left/right keyboard orientation.",
        "generator": "tools/generate_kc2_housing_step.py",
        "parameters": {
            **stl_generator.params_to_dict(params),
            "cylinder_segments": params.cylinder_segments,
        },
        "outputs": {},
    }
    stl_manifest = {
        "generated_by": "tools/generate_kc2_housing_step.py",
        "kicad_python": str(kicad_python),
        "requirement": "CON-ARCH-003",
        "parameters": stl_generator.params_to_dict(params),
        "assumptions": [
            "FDM PLA+ lower housing using a hollow one-piece rail-capture tray shell.",
            "The housing is flat with a uniform 3.80 mm PCB support height and no front-to-rear slope.",
            "A 2.60 mm cavity below the PCB covers the 2.20 mm Kailh CPG135001S30 socket envelope plus 0.40 mm assembly and FDM tolerance.",
            "The interior wall is relieved around extracted bottom-socket envelopes with at least 0.30 mm lateral clearance.",
            "Nine 2.55 mm registration pegs fit the PCB 3.0 mm NPTH holes with PLA expansion clearance.",
            "Each registration post has a centered 1.60 mm blind pilot bore for optional M2 self-tapping retention.",
            "Pilot bores terminate at the flat 1.20 mm floor top and do not penetrate the exterior bottom.",
            "The corrected physical left/right orientation is X-reflected from the raw PCB projection.",
        ],
        "outputs": {},
    }

    for side in ("left", "right"):
        housing, metadata = build_housing(cq, shp, geometry["boards"][side], params)
        path = output_dir / f"kc2_{side}_lower_housing.step"
        stl_path = output_dir / f"kc2_{side}_lower_housing.stl"
        cq.exporters.export(
            housing,
            str(path),
            exportType="STEP",
            tolerance=0.001,
            angularTolerance=0.1,
            unit="MM",
        )
        cq.exporters.export(
            housing,
            str(stl_path),
            exportType="STL",
            tolerance=0.02,
            angularTolerance=0.05,
            opt={"ascii": True},
        )
        name_ascii_stl(stl_path, f"kc2_{side}_lower_housing")
        manifest["outputs"][side] = {
            "step": str(path.relative_to(ROOT)),
            **metadata,
        }
        stl_manifest["outputs"][side] = {
            "stl": str(stl_path.relative_to(ROOT)),
            **metadata,
        }
        print(f"{side}: wrote {path.relative_to(ROOT)} solids={metadata['solid_count']} volume={metadata['volume_mm3']:.3f} mm3")
        print(f"{side}: wrote {stl_path.relative_to(ROOT)} from the same BRep solid")

    manifest_path = output_dir / CAD_MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    stl_manifest_path = output_dir / STL_MANIFEST_NAME
    stl_manifest_path.write_text(
        json.dumps(stl_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"manifest: {manifest_path.relative_to(ROOT)}")
    print(f"manifest: {stl_manifest_path.relative_to(ROOT)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate KC2 X3 STL and Fusion-compatible STEP lower housings.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--kicad-python", type=Path, default=None)
    args = parser.parse_args()
    kicad_python = args.kicad_python or stl_generator.locate_kicad_python()
    return generate_outputs(args.output_dir, kicad_python)


if __name__ == "__main__":
    raise SystemExit(main())
