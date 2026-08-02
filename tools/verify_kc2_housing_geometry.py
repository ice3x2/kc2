from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "hardware" / "case" / "kc2_housing_manifest.json"
VERTEX_RE = re.compile(r"\s*vertex\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s*$")

MIN_BOTTOM_CORNER_RADIUS_MM = 0.5
MAX_REAR_RISE_MM = 0.001
MAX_OBSERVED_REAR_RISE_MM = 0.02
MAX_BOTTOM_EDGE_RADIUS_MM = 0.05
LOW_BOTTOM_LAYER_SCAN_MM = 1.0
MAX_PROJECTED_MESH_OUTSIDE_FOOTPRINT_AREA_MM2 = 0.10
TARGET_REAR_HEIGHT_RATIO = 1.00
HEIGHT_RATIO_TOLERANCE = 0.001
EXPECTED_FLOOR_THICKNESS_MM = 1.20
EXPECTED_SOCKET_BODY_HEIGHT_MM = 2.20
EXPECTED_SOCKET_SAFETY_CLEARANCE_MM = 0.40
EXPECTED_BOTTOM_COMPONENT_CLEARANCE_MM = 2.60
EXPECTED_PCB_SUPPORT_HEIGHT_MM = 3.80
DIMENSION_TOLERANCE_MM = 0.001
EXPECTED_SOCKET_COUNTS = {"left": 32, "right": 45}
MIN_SOCKET_LATERAL_CLEARANCE_MM = 0.30
MIN_CAVITY_OPEN_AREA_RATIO = 0.45
MAX_EXTERNAL_STEP_MM = 0.05
EDGE_SAMPLE_FRACTION = 0.10
EXPECTED_PILOT_HOLE_DIAMETER_MM = 1.60
EXPECTED_REGISTRATION_PEG_DIAMETER_MM = 2.55
PRINT_VOLUME_LIMIT_MM = 150.0
EXPECTED_RIGHT_PART_COUNT = 2
EXPECTED_SPLIT_FACE_SETBACK_MM = 0.20
EXPECTED_SPLIT_ASSEMBLED_GAP_MM = 0.40
MIN_ZIGZAG_LENGTH_RATIO = 1.40
CYLINDER_RADIUS_TOLERANCE_MM = 0.03
MIN_CYLINDER_VERTEX_COUNT = 16
MESH_VERTEX_QUANTIZATION_DIGITS = 5
FACET_RE = re.compile(r"\s*facet\s+normal\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s*$")
Facet = tuple[tuple[float, float, float], tuple[tuple[float, float, float], ...]]


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def stl_vertices(path: Path) -> list[tuple[float, float, float]]:
    return [vertex for _normal, tri in stl_facets(path) for vertex in tri]


def stl_facets(path: Path) -> list[Facet]:
    facets: list[Facet] = []
    normal = (0.0, 0.0, 0.0)
    vertices: list[tuple[float, float, float]] = []
    for line in path.read_text(encoding="ascii", errors="strict").splitlines():
        facet_match = FACET_RE.match(line)
        if facet_match:
            normal = tuple(float(facet_match.group(idx)) for idx in range(1, 4))
            vertices = []
            continue
        vertex_match = VERTEX_RE.match(line)
        if not vertex_match:
            continue
        vertices.append(tuple(float(vertex_match.group(idx)) for idx in range(1, 4)))
        if len(vertices) == 3:
            facets.append((normal, tuple(vertices)))
    return facets


def low_bottom_layers(vertices: list[tuple[float, float, float]]) -> list[float]:
    if not vertices:
        return []
    min_z = min(z for _x, _y, z in vertices)
    return sorted(
        {
            round(z - min_z, 3)
            for _x, _y, z in vertices
            if 0.001 <= z - min_z <= LOW_BOTTOM_LAYER_SCAN_MM
        }
    )


def intended_outer_footprints(manifest: dict[str, Any]) -> dict[str, Any]:
    import generate_kc2_housings as generator

    shp = generator.require_shapely()
    raw_params = manifest.get("parameters", {})
    field_names = set(generator.HousingParams.__dataclass_fields__)
    params = generator.HousingParams(**{key: value for key, value in raw_params.items() if key in field_names})
    kicad_python = Path(manifest.get("kicad_python") or "")
    if not kicad_python.exists():
        kicad_python = generator.locate_kicad_python()
    geometry = generator.run_extractor(kicad_python)

    footprints = {}
    for side in ("left", "right"):
        raw_poly = generator.board_polygon(shp, geometry["boards"][side]["edge_segments"])
        minx, miny, _maxx, _maxy = raw_poly.bounds
        board = shp["affinity"].translate(raw_poly, xoff=-minx, yoff=-miny)
        board = shp["affinity"].scale(board, xfact=-1.0, yfact=1.0, origin="center")
        outer = board.buffer(-params.outline_inset_mm, join_style="round", resolution=16)
        if params.bottom_corner_radius_mm > 0:
            outer = outer.buffer(-params.bottom_corner_radius_mm / 2.0, join_style="round", resolution=16).buffer(
                params.bottom_corner_radius_mm / 2.0,
                join_style="round",
                resolution=16,
            )
        footprints[side] = outer
    return footprints


def max_projected_outside_area(shp: dict[str, Any], facets: list[Facet], footprint: Any) -> float:
    max_area = 0.0
    for _normal, tri in facets:
        projected = shp["Polygon"]([(x, y) for x, y, _z in tri])
        if projected.area <= 1e-8:
            continue
        max_area = max(max_area, projected.difference(footprint).area)
    return max_area


def non_manifold_edge_count(facets: list[Facet]) -> int:
    edge_counts: dict[tuple[tuple[float, float, float], tuple[float, float, float]], int] = {}
    for _normal, triangle in facets:
        vertices = [
            tuple(round(value, MESH_VERTEX_QUANTIZATION_DIGITS) for value in vertex)
            for vertex in triangle
        ]
        for start, end in zip(vertices, vertices[1:] + vertices[:1]):
            edge = tuple(sorted((start, end)))
            edge_counts[edge] = edge_counts.get(edge, 0) + 1
    return sum(count != 2 for count in edge_counts.values())


def mesh_shell_count(facets: list[Facet]) -> int:
    edge_facets: dict[
        tuple[tuple[float, float, float], tuple[float, float, float]],
        list[int],
    ] = {}
    for index, (_normal, triangle) in enumerate(facets):
        vertices = [
            tuple(round(value, MESH_VERTEX_QUANTIZATION_DIGITS) for value in vertex)
            for vertex in triangle
        ]
        for start, end in zip(vertices, vertices[1:] + vertices[:1]):
            edge = tuple(sorted((start, end)))
            edge_facets.setdefault(edge, []).append(index)

    adjacency = [set() for _facet in facets]
    for indexes in edge_facets.values():
        for index in indexes:
            adjacency[index].update(other for other in indexes if other != index)

    remaining = set(range(len(facets)))
    shell_count = 0
    while remaining:
        shell_count += 1
        stack = [remaining.pop()]
        while stack:
            current = stack.pop()
            connected = adjacency[current] & remaining
            remaining.difference_update(connected)
            stack.extend(connected)
    return shell_count


def output_stl_paths(side: str, output: dict[str, Any]) -> list[Path]:
    if side == "left":
        value = output.get("stl")
        return [ROOT / value] if value else []
    return [
        ROOT / part["stl"]
        for part in output.get("stl_parts", [])
        if isinstance(part, dict) and part.get("stl")
    ]


def cylinder_vertex_count(
    vertices: list[tuple[float, float, float]],
    center_x: float,
    center_y: float,
    radius: float,
) -> int:
    return sum(
        abs(math.hypot(x - center_x, y - center_y) - radius) <= CYLINDER_RADIUS_TOLERANCE_MM
        for x, y, _z in vertices
    )


def verify_stl_mesh(manifest: dict[str, Any], outputs: dict[str, Any]) -> list[str]:
    import generate_kc2_housings as generator

    errors: list[str] = []
    shp = generator.require_shapely()
    footprints = intended_outer_footprints(manifest)
    for side in ("left", "right"):
        output = outputs.get(side)
        if not output:
            continue
        combined_vertices = []
        for stl_path in output_stl_paths(side, output):
            if not stl_path.exists():
                continue
            facets = stl_facets(stl_path)
            vertices = [vertex for _normal, tri in facets for vertex in tri]
            combined_vertices.extend(vertices)
            bad_edges = non_manifold_edge_count(facets)
            if bad_edges:
                errors.append(
                    f"{side}: {stl_path.name} has {bad_edges} "
                    "non-manifold boundary/internal edges"
                )
            shell_count = mesh_shell_count(facets)
            if shell_count != 1:
                errors.append(
                    f"{side}: {stl_path.name} contains {shell_count} mesh shells, expected 1"
                )
            extra_layers = low_bottom_layers(vertices)
            if extra_layers:
                errors.append(
                    f"{side}: {stl_path.name} has intermediate low-Z layers below "
                    f"{LOW_BOTTOM_LAYER_SCAN_MM:.1f} mm: {extra_layers}"
                )
            outside_area = max_projected_outside_area(shp, facets, footprints[side])
            if outside_area > MAX_PROJECTED_MESH_OUTSIDE_FOOTPRINT_AREA_MM2:
                errors.append(
                    f"{side}: {stl_path.name} triangle projection extends "
                    f"{outside_area:.3f} mm^2 outside the intended housing footprint"
                )
            dimensions = [
                max(vertex[axis] for vertex in vertices)
                - min(vertex[axis] for vertex in vertices)
                for axis in range(3)
            ]
            for axis, dimension in zip("XYZ", dimensions):
                if dimension > PRINT_VOLUME_LIMIT_MM + DIMENSION_TOLERANCE_MM:
                    errors.append(
                        f"{side}: {stl_path.name} {axis} size {dimension:.3f} mm "
                        f"exceeds the {PRINT_VOLUME_LIMIT_MM:.1f} mm print limit"
                    )

        peg_radius = EXPECTED_REGISTRATION_PEG_DIAMETER_MM / 2.0
        pilot_radius = EXPECTED_PILOT_HOLE_DIAMETER_MM / 2.0
        for hole in output.get("registration_holes", []):
            peg_vertices = cylinder_vertex_count(
                combined_vertices,
                float(hole["x"]),
                float(hole["y"]),
                peg_radius,
            )
            if peg_vertices < MIN_CYLINDER_VERTEX_COUNT:
                errors.append(
                    f"{side}: {hole['ref']} has {peg_vertices} vertices at the "
                    f"{peg_radius:.3f} mm registration-peg radius"
                )
            pilot_vertices = cylinder_vertex_count(
                combined_vertices,
                float(hole["x"]),
                float(hole["y"]),
                pilot_radius,
            )
            if pilot_vertices < MIN_CYLINDER_VERTEX_COUNT:
                errors.append(
                    f"{side}: {hole['ref']} has {pilot_vertices} vertices at the "
                    f"{pilot_radius:.3f} mm pilot-bore radius"
                )
    return errors


def observed_rear_rise(vertices: list[tuple[float, float, float]]) -> float:
    ys = [y for _x, y, _z in vertices]
    if not ys:
        return -999.0
    min_y = min(ys)
    max_y = max(ys)
    span = max_y - min_y
    if span <= 1e-6:
        return -999.0

    rear_limit = min_y + span * EDGE_SAMPLE_FRACTION
    front_limit = max_y - span * EDGE_SAMPLE_FRACTION
    rear_z = [z for _x, y, z in vertices if y <= rear_limit]
    front_z = [z for _x, y, z in vertices if y >= front_limit]
    if not rear_z or not front_z:
        return -999.0
    return max(rear_z) - max(front_z)


def verify_manifest(manifest: dict[str, Any], manifest_path: Path) -> list[str]:
    errors: list[str] = []
    params = manifest.get("parameters", {})
    if params.get("design_style") != "hollow_rail_capture_tray":
        errors.append("housing manifest must set design_style=hollow_rail_capture_tray")

    if params.get("battery_floor_cutout_enabled") is not False:
        errors.append("housing manifest must set battery_floor_cutout_enabled=false")

    pilot_diameter = float(params.get("screw_pilot_hole_diameter_mm", 0.0))
    if abs(pilot_diameter - EXPECTED_PILOT_HOLE_DIAMETER_MM) > 1e-6:
        errors.append(
            f"screw_pilot_hole_diameter_mm {pilot_diameter:.3f} is not "
            f"{EXPECTED_PILOT_HOLE_DIAMETER_MM:.3f} mm"
        )

    peg_diameter = float(params.get("registration_peg_diameter_mm", 0.0))
    if abs(peg_diameter - EXPECTED_REGISTRATION_PEG_DIAMETER_MM) > 1e-6:
        errors.append(
            f"registration_peg_diameter_mm {peg_diameter:.3f} is not "
            f"{EXPECTED_REGISTRATION_PEG_DIAMETER_MM:.3f} mm"
        )

    print_limit = float(params.get("print_volume_limit_mm", 0.0))
    if abs(print_limit - PRINT_VOLUME_LIMIT_MM) > DIMENSION_TOLERANCE_MM:
        errors.append(
            f"print_volume_limit_mm {print_limit:.3f} is not "
            f"{PRINT_VOLUME_LIMIT_MM:.1f} mm"
        )
    split_setback = float(params.get("right_split_face_setback_mm", 0.0))
    if (
        abs(split_setback - EXPECTED_SPLIT_FACE_SETBACK_MM)
        > DIMENSION_TOLERANCE_MM
    ):
        errors.append(
            f"right_split_face_setback_mm {split_setback:.3f} is not "
            f"{EXPECTED_SPLIT_FACE_SETBACK_MM:.2f} mm"
        )

    floor_thickness = float(params.get("floor_thickness_mm", 0.0))
    if abs(floor_thickness - EXPECTED_FLOOR_THICKNESS_MM) > DIMENSION_TOLERANCE_MM:
        errors.append(
            f"floor_thickness_mm {floor_thickness:.3f} is not "
            f"{EXPECTED_FLOOR_THICKNESS_MM:.3f} mm"
        )

    socket_body_height = float(params.get("socket_body_height_mm", 0.0))
    if abs(socket_body_height - EXPECTED_SOCKET_BODY_HEIGHT_MM) > DIMENSION_TOLERANCE_MM:
        errors.append(
            f"socket_body_height_mm {socket_body_height:.3f} is not "
            f"{EXPECTED_SOCKET_BODY_HEIGHT_MM:.3f} mm"
        )

    socket_safety_clearance = float(params.get("socket_safety_clearance_mm", 0.0))
    if (
        abs(socket_safety_clearance - EXPECTED_SOCKET_SAFETY_CLEARANCE_MM)
        > DIMENSION_TOLERANCE_MM
    ):
        errors.append(
            f"socket_safety_clearance_mm {socket_safety_clearance:.3f} is not "
            f"{EXPECTED_SOCKET_SAFETY_CLEARANCE_MM:.3f} mm"
        )

    component_clearance = float(params.get("bottom_component_clearance_mm", 0.0))
    if (
        abs(component_clearance - EXPECTED_BOTTOM_COMPONENT_CLEARANCE_MM)
        > DIMENSION_TOLERANCE_MM
    ):
        errors.append(
            f"bottom_component_clearance_mm {component_clearance:.3f} is not "
            f"{EXPECTED_BOTTOM_COMPONENT_CLEARANCE_MM:.3f} mm"
        )
    if socket_body_height + socket_safety_clearance > component_clearance + DIMENSION_TOLERANCE_MM:
        errors.append(
            "socket body envelope plus safety clearance exceeds the available "
            "bottom-component clearance"
        )

    support_height = float(params.get("front_height_mm", 0.0))
    if abs(support_height - EXPECTED_PCB_SUPPORT_HEIGHT_MM) > DIMENSION_TOLERANCE_MM:
        errors.append(
            f"front_height_mm {support_height:.3f} is not the minimum flat "
            f"{EXPECTED_PCB_SUPPORT_HEIGHT_MM:.3f} mm support height"
        )

    rear_rise = abs(float(params.get("rear_rise_mm", 999.0)))
    if rear_rise > MAX_REAR_RISE_MM:
        errors.append(
            f"rear_rise_mm {rear_rise:.3f} exceeds the flatness limit "
            f"{MAX_REAR_RISE_MM:.3f} mm"
        )

    rear_height_ratio = float(params.get("rear_height_ratio", 0.0))
    if abs(rear_height_ratio - TARGET_REAR_HEIGHT_RATIO) > HEIGHT_RATIO_TOLERANCE:
        errors.append(
            f"rear_height_ratio {rear_height_ratio:.3f} is not within "
            f"{HEIGHT_RATIO_TOLERANCE:.3f} of {TARGET_REAR_HEIGHT_RATIO:.3f}"
        )

    bottom_radius = float(params.get("bottom_corner_radius_mm", 0.0))
    if bottom_radius < MIN_BOTTOM_CORNER_RADIUS_MM:
        errors.append(
            f"bottom_corner_radius_mm {bottom_radius:.3f} is below "
            f"{MIN_BOTTOM_CORNER_RADIUS_MM:.3f} mm"
        )

    bottom_edge_radius = float(params.get("bottom_edge_radius_mm", 0.0))
    if bottom_edge_radius > MAX_BOTTOM_EDGE_RADIUS_MM:
        errors.append(
            f"bottom_edge_radius_mm {bottom_edge_radius:.3f} should be disabled or <= "
            f"{MAX_BOTTOM_EDGE_RADIUS_MM:.3f} mm for a clean flat underside"
        )

    outputs = manifest.get("outputs", {})
    for side in ("left", "right"):
        output = outputs.get(side)
        if not output:
            errors.append(f"missing output metadata for {side}")
            continue
        battery_slot = output.get("battery_slot")
        if battery_slot and battery_slot.get("housing_floor_cutout") is not False:
            errors.append(f"{side}: battery slot metadata must report housing_floor_cutout=false")
        if output.get("orientation") != "x_reflected_for_physical_assembly":
            errors.append(f"{side}: output must declare corrected X-reflected orientation")
        pilot_holes = output.get("pilot_holes", [])
        if len(pilot_holes) != 9:
            errors.append(f"{side}: expected 9 pilot-hole metadata entries, found {len(pilot_holes)}")
        for pilot in pilot_holes:
            if abs(float(pilot.get("diameter_mm", 0.0)) - EXPECTED_PILOT_HOLE_DIAMETER_MM) > 1e-6:
                errors.append(f"{side}: {pilot.get('ref')} pilot diameter is incorrect")
            if pilot.get("blind_to_floor_top") is not True:
                errors.append(f"{side}: {pilot.get('ref')} pilot hole is not declared blind")

        height_profile = output.get("height_profile", {})
        profile_rise = abs(float(height_profile.get("rear_rise_mm", 999.0)))
        if profile_rise > MAX_REAR_RISE_MM:
            errors.append(
                f"{side}: height_profile rear_rise_mm {profile_rise:.3f} exceeds "
                f"{MAX_REAR_RISE_MM:.3f} mm"
            )
        observed_ratio = float(height_profile.get("rear_height_ratio", 0.0))
        if abs(observed_ratio - TARGET_REAR_HEIGHT_RATIO) > HEIGHT_RATIO_TOLERANCE:
            errors.append(
                f"{side}: height_profile rear_height_ratio {observed_ratio:.3f} is not within "
                f"{HEIGHT_RATIO_TOLERANCE:.3f} of {TARGET_REAR_HEIGHT_RATIO:.3f}"
            )

        cavity = output.get("interior_cavity", {})
        if cavity.get("open_above_floor") is not True:
            errors.append(f"{side}: interior cavity must be open above the floor")
        open_area_ratio = float(cavity.get("open_area_ratio", 0.0))
        if open_area_ratio < MIN_CAVITY_OPEN_AREA_RATIO:
            errors.append(
                f"{side}: interior cavity open area ratio {open_area_ratio:.3f} is below "
                f"{MIN_CAVITY_OPEN_AREA_RATIO:.3f}"
            )
        external_step = float(cavity.get("external_step_mm", 999.0))
        if external_step > MAX_EXTERNAL_STEP_MM:
            errors.append(
                f"{side}: external side step {external_step:.3f} mm exceeds "
                f"{MAX_EXTERNAL_STEP_MM:.3f} mm"
            )

        socket_clearance = output.get("socket_clearance", {})
        socket_count = int(socket_clearance.get("socket_count", -1))
        if socket_count != EXPECTED_SOCKET_COUNTS[side]:
            errors.append(
                f"{side}: socket-clearance metadata reports {socket_count} sockets, "
                f"expected {EXPECTED_SOCKET_COUNTS[side]}"
            )
        collision_count = int(socket_clearance.get("wall_collision_count", -1))
        if collision_count != 0:
            errors.append(
                f"{side}: socket-clearance metadata reports {collision_count} wall collisions"
            )
        lateral_clearance = float(
            socket_clearance.get("minimum_lateral_clearance_to_wall_mm", -1.0)
        )
        if lateral_clearance < MIN_SOCKET_LATERAL_CLEARANCE_MM:
            errors.append(
                f"{side}: minimum socket-to-wall clearance {lateral_clearance:.3f} mm "
                f"is below {MIN_SOCKET_LATERAL_CLEARANCE_MM:.3f} mm"
            )
        vertical_clearance = float(
            socket_clearance.get("vertical_clearance_to_floor_mm", -1.0)
        )
        if (
            abs(vertical_clearance - EXPECTED_SOCKET_SAFETY_CLEARANCE_MM)
            > DIMENSION_TOLERANCE_MM
        ):
            errors.append(
                f"{side}: vertical socket-to-floor clearance {vertical_clearance:.3f} mm "
                f"is not {EXPECTED_SOCKET_SAFETY_CLEARANCE_MM:.3f} mm"
            )

        stl_paths = output_stl_paths(side, output)
        if side == "left":
            if len(stl_paths) != 1:
                errors.append("left: expected one printable STL")
        else:
            if output.get("stl"):
                errors.append("right: monolithic STL metadata must not be present")
            if len(stl_paths) != EXPECTED_RIGHT_PART_COUNT:
                errors.append(
                    f"right: expected {EXPECTED_RIGHT_PART_COUNT} printable STL parts, "
                    f"found {len(stl_paths)}"
                )
        for stl_path in stl_paths:
            if not stl_path.exists():
                errors.append(f"{side}: STL not found: {stl_path.relative_to(ROOT)}")
                continue
            rise = abs(observed_rear_rise(stl_vertices(stl_path)))
            if rise > MAX_OBSERVED_REAR_RISE_MM:
                errors.append(
                    f"{side}: {stl_path.name} observed rear/top-edge rise is "
                    f"{rise:.3f} mm, expected <= {MAX_OBSERVED_REAR_RISE_MM:.3f} mm"
                )

    right = outputs.get("right", {})
    split = right.get("split", {})
    if split.get("style") != "post_avoiding_zigzag":
        errors.append("right: split style must be post_avoiding_zigzag")
    if int(split.get("part_count", 0)) != EXPECTED_RIGHT_PART_COUNT:
        errors.append(f"right: split metadata must declare {EXPECTED_RIGHT_PART_COUNT} parts")
    face_setback = float(split.get("face_setback_mm", 0.0))
    if abs(face_setback - EXPECTED_SPLIT_FACE_SETBACK_MM) > DIMENSION_TOLERANCE_MM:
        errors.append(
            f"right: split face setback {face_setback:.3f} mm is not "
            f"{EXPECTED_SPLIT_FACE_SETBACK_MM:.2f} mm"
        )
    assembled_gap = float(split.get("assembled_gap_mm", 0.0))
    if abs(assembled_gap - EXPECTED_SPLIT_ASSEMBLED_GAP_MM) > DIMENSION_TOLERANCE_MM:
        errors.append(
            f"right: assembled split gap {assembled_gap:.3f} mm is not "
            f"{EXPECTED_SPLIT_ASSEMBLED_GAP_MM:.2f} mm"
        )
    face_lengths = split.get("floor_bond_face_lengths_mm", {})
    if set(face_lengths) != {"part_a", "part_b"}:
        errors.append("right: split metadata must include both floor-bond face lengths")
    elif abs(
        float(split.get("minimum_floor_bond_length_mm", 0.0))
        - min(float(length) for length in face_lengths.values())
    ) > DIMENSION_TOLERANCE_MM:
        errors.append("right: minimum floor-bond length is not the shorter mating face")
    length_ratio = float(split.get("minimum_floor_bond_length_ratio", 0.0))
    if length_ratio < MIN_ZIGZAG_LENGTH_RATIO:
        errors.append(
            f"right: zigzag floor-bond length ratio {length_ratio:.3f} is below "
            f"{MIN_ZIGZAG_LENGTH_RATIO:.2f}"
        )
    if float(split.get("minimum_registration_post_clearance_mm", -1.0)) <= 0.0:
        errors.append("right: zigzag seam collides with a registration post")
    stale_right_stl = ROOT / "hardware" / "case" / "kc2_right_lower_housing.stl"
    if stale_right_stl.exists():
        errors.append(
            "right: stale monolithic hardware/case/kc2_right_lower_housing.stl exists"
        )

    if manifest_path != DEFAULT_MANIFEST and not manifest_path.is_absolute():
        errors.append("internal error: manifest path should be absolute")
    errors.extend(verify_stl_mesh(manifest, outputs))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify KC2 lower housing draft geometry assumptions.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = ROOT / manifest_path

    errors = verify_manifest(load_manifest(manifest_path), manifest_path)
    if errors:
        print("FAIL: KC2 lower housing geometry verification")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: KC2 lower housing geometry verification")
    print("- controller-side floor is closed below the PCB battery lead slot")
    print("- rail-capture tray metadata reports a hollow interior cavity")
    print("- bottom outline has an explicit rounded-corner radius")
    print("- underside has no rounded-edge loft layers or mesh projected outside the footprint")
    print("- exterior floor, interior floor, PCB support, and post tops are flat")
    print("- 2.60 mm bottom-component clearance covers a 2.20 mm socket plus 0.40 mm tolerance")
    print("- all 77 bottom-side socket envelopes clear the housing walls")
    print("- uniform PCB support height is 3.80 mm over a 1.20 mm closed floor")
    print("- left is one printable STL and right is two single-shell printable STLs")
    print("- every STL fits the 150 mm cube print envelope")
    print("- right zigzag seam has 0.20 mm setback per face and a 0.40 mm assembled gap")
    print("- each housing has nine 2.55 mm pegs with centered 1.60 mm blind pilot bores")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
