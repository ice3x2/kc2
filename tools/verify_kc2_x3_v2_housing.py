"""Verify the CON-ARCH-006 draft X3 V2 load-bearing housing."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import generate_kc2_housings as geometry_helpers  # noqa: E402
import generate_kc2_x3_v2_housings as generator  # noqa: E402


REPORT_PATH = generator.OUTPUT_DIR / "kc2_x3_v2_housing_clearance.json"
COLLISION_CLASSES = {
    "choc_socket_body",
    "choc_socket_fillets",
    "mx_pins_pads_fillets",
    "diode_body_pads_fillets",
    "bottom_copper_tracks",
    "vias",
    "controller_reset",
    "battery_slot",
    "switch_key_travel",
}


def has_trailing_horizontal_whitespace(path: Path) -> bool:
    return re.search(rb"[ \t]+(?=\r?\n|\Z)", path.read_bytes()) is not None


def inspect_ascii_stl(path: Path) -> dict[str, Any]:
    vertices: list[tuple[float, float, float]] = []
    solid_count = 0
    with path.open("r", encoding="ascii", errors="strict") as stream:
        for line in stream:
            stripped = line.strip()
            if stripped == "solid" or stripped.startswith("solid "):
                solid_count += 1
            elif stripped.startswith("vertex "):
                _tag, x, y, z = stripped.split()
                vertices.append((float(x), float(y), float(z)))
    if not vertices:
        raise RuntimeError(f"No ASCII STL vertices: {path}")
    if len(vertices) % 3:
        raise RuntimeError(f"Incomplete ASCII STL facets: {path}")
    edge_counts: Counter[tuple[tuple[float, float, float], tuple[float, float, float]]] = Counter()
    adjacency: dict[tuple[float, float, float], set[tuple[float, float, float]]] = defaultdict(set)
    for index in range(0, len(vertices), 3):
        triangle = [tuple(round(value, 6) for value in vertex) for vertex in vertices[index : index + 3]]
        for start, end in zip(triangle, (triangle[1], triangle[2], triangle[0])):
            edge = tuple(sorted((start, end)))
            edge_counts[edge] += 1
            adjacency[start].add(end)
            adjacency[end].add(start)
    unseen = set(adjacency)
    shell_count = 0
    while unseen:
        shell_count += 1
        stack = [unseen.pop()]
        while stack:
            current = stack.pop()
            neighbors = adjacency[current] & unseen
            unseen.difference_update(neighbors)
            stack.extend(neighbors)
    mins = [min(vertex[index] for vertex in vertices) for index in range(3)]
    maxs = [max(vertex[index] for vertex in vertices) for index in range(3)]
    return {
        "solid_count": solid_count,
        "watertight": bool(edge_counts) and all(count == 2 for count in edge_counts.values()),
        "shell_count": shell_count,
        "bounds_xyz_mm": [round(value, 4) for value in (*mins, *maxs)],
        "size_xyz_mm": [round(maxs[index] - mins[index], 4) for index in range(3)],
    }


def _support_union(shp: dict[str, Any], posts: list[dict[str, Any]]) -> Any:
    return shp["unary_union"](
        [
            shp["Point"](float(post["x_mm"]), float(post["y_mm"])).buffer(
                float(post["diameter_mm"]) / 2.0,
                quad_segs=20,
            )
            for post in posts
        ]
    )


def _collision_result(contact: Any, feature: Any) -> dict[str, Any]:
    if contact.is_empty or feature.is_empty:
        return {"collision_count": 0, "intersection_area_mm2": 0.0}
    intersection = contact.intersection(feature)
    count = 0
    if not intersection.is_empty and intersection.area > 1e-7:
        count = 1 if not hasattr(intersection, "geoms") else len(
            [item for item in intersection.geoms if getattr(item, "area", 0.0) > 1e-7]
        )
    return {
        "collision_count": count,
        "intersection_area_mm2": round(float(intersection.area), 6),
        "minimum_plan_clearance_mm": round(float(contact.distance(feature)), 4),
    }


def analyze_v2_housing() -> dict[str, Any]:
    import cadquery as cq

    manifest = json.loads(generator.MANIFEST_PATH.read_text(encoding="utf-8"))
    extracted = generator.run_extractor(geometry_helpers.locate_kicad_python())
    shp = geometry_helpers.require_shapely()
    report: dict[str, Any] = {
        "requirement": manifest["requirement"],
        "variant": manifest["variant"],
        "manifest": str(generator.MANIFEST_PATH.relative_to(ROOT)).replace("\\", "/"),
        "generator_sha256_matches": generator.sha256_path(generator.GENERATOR_PATH)
        == manifest.get("generator_sha256"),
        "sides": {},
        "physical_deflection_test": manifest["physical_deflection_test"],
        "fabrication_or_order_ready": False,
        "order_readiness_blocker": "CON-ARCH-006 AC-7 physical 2.0 N deflection evidence is pending.",
        "stale_monolithic_right_stl_present": (
            generator.OUTPUT_DIR / "kc2_right_x3_v2_lower_housing.stl"
        ).exists(),
    }

    for side in ("left", "right"):
        board_data = extracted["boards"][side]
        output = manifest["outputs"][side]
        plan = generator.build_plan_geometry(shp, side, board_data)
        posts = output["support_posts"]
        contacts = _support_union(shp, posts).union(plan["rail"])
        collision_checks = {
            name: _collision_result(contacts, geometry)
            for name, geometry in plan["feature_geometries"].items()
        }
        # Key/switch travel is entirely above the PCB top while support geometry
        # ends at the PCB bottom. Record the disjoint Z proof explicitly.
        collision_checks["switch_key_travel"] = {
            "collision_count": 0,
            "reason": "support_top_z <= pcb_bottom_z < pcb_top_z <= switch/key travel",
            "support_top_z_mm": generator.PCB_BOTTOM_Z_MM,
            "switch_travel_min_z_mm": generator.PCB_BOTTOM_Z_MM + generator.PCB_THICKNESS_MM,
        }

        maximum_support_gap = max(
            abs(generator.PCB_BOTTOM_Z_MM - float(post["top_z_mm"]))
            for post in posts
        )
        step_path = ROOT / output["step"]
        source_path = ROOT / output["source_board"]
        step_model = cq.importers.importStep(str(step_path)) if step_path.is_file() else None
        step_solids = [] if step_model is None else step_model.solids().vals()
        step_bounds = None if not step_solids else step_model.val().BoundingBox()
        expected_contact = contacts.difference(plan["feature_geometries"]["battery_slot"])
        if side == "right":
            split = output["split_joint"]
            seam_half = float(split["nominal_plan_clearance_mm"]) / 2.0
            min_x, min_y, max_x, max_y = plan["board"].bounds
            seam_cut = shp["box"](
                float(split["split_x_mm"]) - seam_half,
                min_y - 1.0,
                float(split["split_x_mm"]) + seam_half,
                max_y + 1.0,
            )
            expected_contact = expected_contact.difference(seam_cut)
        actual_contact_area = 0.0
        if step_model is not None and step_bounds is not None:
            slice_height = 0.01
            slice_box = (
                cq.Workplane("XY")
                .box(
                    step_bounds.xlen + 2.0,
                    step_bounds.ylen + 2.0,
                    slice_height,
                    centered=(True, True, False),
                )
                .translate(
                    (
                        (step_bounds.xmin + step_bounds.xmax) / 2.0,
                        (step_bounds.ymin + step_bounds.ymax) / 2.0,
                        generator.PCB_BOTTOM_Z_MM - slice_height,
                    )
                )
            )
            top_slice = step_model.intersect(slice_box)
            actual_contact_area = sum(solid.Volume() for solid in top_slice.solids().vals()) / slice_height
        contact_area_error = abs(actual_contact_area - float(expected_contact.area))
        printable_parts = []
        for part in output["printable_parts"]:
            stl_path = ROOT / part["stl"]
            inspected = inspect_ascii_stl(stl_path) if stl_path.is_file() else {
                "solid_count": 0,
                "watertight": False,
                "shell_count": 0,
                "bounds_xyz_mm": [],
                "size_xyz_mm": [],
            }
            printable_parts.append(
                {
                    "name": part["name"],
                    "stl": part["stl"],
                    "sha256_matches": stl_path.is_file()
                    and generator.sha256_path(stl_path) == part["stl_sha256"],
                    "solid_count": inspected["solid_count"],
                    "watertight": inspected["watertight"],
                    "shell_count": inspected["shell_count"],
                    "bounds_xyz_mm": inspected["bounds_xyz_mm"],
                    "size_xyz_mm": inspected["size_xyz_mm"],
                    "bounds_match_manifest": len(inspected["bounds_xyz_mm"]) == 6
                    and all(
                        abs(float(actual) - float(expected)) <= 0.001
                        for actual, expected in zip(inspected["bounds_xyz_mm"], part["bounds_xyz_mm"])
                    ),
                }
            )
        split_report = None
        if side == "right":
            split = output["split_joint"]
            feature_collisions = 0
            support_collisions = 0
            head_case_collision_volume = 0.0
            driver_case_collision_volume = 0.0
            support_geometry = _support_union(shp, posts).union(plan["rail"])
            all_features = shp["unary_union"](
                [geometry for geometry in plan["feature_geometries"].values() if not geometry.is_empty]
            )
            for point in split["case_join_fasteners"]:
                envelope = shp["Point"](point["x_mm"], point["y_mm"]).buffer(
                    float(split["case_join_screw_head_envelope_mm"]) / 2.0,
                    quad_segs=20,
                )
                feature_collisions += int(envelope.intersects(all_features))
                support_collisions += int(envelope.intersects(support_geometry))
                if step_model is not None:
                    head = (
                        cq.Workplane("XY")
                        .center(point["x_mm"], point["y_mm"])
                        .circle(float(split["fastener_spec"]["official_head_diameter_max_mm"]) / 2.0)
                        .extrude(float(split["fastener_spec"]["official_head_height_max_mm"]))
                        .translate(
                            (
                                0.0,
                                0.0,
                                float(split["head_seat_z_mm"])
                                - float(split["fastener_spec"]["official_head_height_max_mm"]),
                            )
                        )
                    )
                    driver = (
                        cq.Workplane("XY")
                        .center(point["x_mm"], point["y_mm"])
                        .circle(float(split["fastener_spec"]["driver_shaft_diameter_mm"]) / 2.0)
                        .extrude(
                            float(split["fastener_spec"]["driver_access_height_mm"])
                            + float(split["head_exterior_face_nominal_z_mm"])
                        )
                        .translate(
                            (
                                0.0,
                                0.0,
                                -float(split["fastener_spec"]["driver_access_height_mm"]),
                            )
                        )
                    )
                    head_case_collision_volume += sum(
                        float(solid.Volume())
                        for solid in step_model.intersect(head).solids().vals()
                    )
                    driver_case_collision_volume += sum(
                        float(solid.Volume())
                        for solid in step_model.intersect(driver).solids().vals()
                    )
            head_case_collision_volume = round(head_case_collision_volume, 6)
            driver_case_collision_volume = round(driver_case_collision_volume, 6)
            split_report = {
                **split,
                "feature_collision_count": feature_collisions,
                "support_collision_count": support_collisions,
                "head_case_collision_volume_mm3": head_case_collision_volume,
                "driver_shaft_case_collision_volume_mm3": driver_case_collision_volume,
                "head_driver_vertical_collision_count": feature_collisions
                + support_collisions
                + int(head_case_collision_volume > 1e-6)
                + int(driver_case_collision_volume > 1e-6),
                "driver_access_from_exterior_bottom": feature_collisions == 0
                and support_collisions == 0
                and head_case_collision_volume <= 1e-6
                and driver_case_collision_volume <= 1e-6,
                "support_load_path_preserved": contact_area_error <= 0.20,
            }
        report["sides"][side] = {
            "source_board": output["source_board"],
            "source_board_sha256_matches": generator.sha256_path(source_path) == output["source_board_sha256"],
            "key_count": len(board_data["switches"]),
            "legacy_registration_refs": board_data["legacy_registration_refs"],
            "rail_top_z_mm": float(output["rail"]["top_z_mm"]),
            "pcb_bottom_z_mm": generator.PCB_BOTTOM_Z_MM,
            "maximum_rail_vertical_gap_mm": abs(
                generator.PCB_BOTTOM_Z_MM - float(output["rail"]["top_z_mm"])
            ),
            "maximum_support_vertical_gap_mm": maximum_support_gap,
            "rail_plan_area_mm2": round(float(plan["rail"].area), 4),
            "rail_plan_area_matches_manifest": math.isclose(
                float(plan["rail"].area),
                float(output["rail"]["plan_area_mm2"]),
                abs_tol=0.0001,
            ),
            "rail_segment_count": output["rail"]["segment_count"],
            "support_posts": posts,
            "support_plan_matches_generator": posts == plan["support_posts"],
            "maximum_load_point_to_support_mm": float(output["maximum_load_point_to_support_mm"]),
            "registration_peg_count": int(manifest["retention"]["registration_peg_count"]),
            "screw_pilot_count": int(manifest["retention"]["screw_pilot_count"]),
            "fastener_boss_count": int(manifest["retention"]["fastener_boss_count"]),
            "glue_assumed": bool(manifest["retention"]["glue_assumed"]),
            "collision_checks": collision_checks,
            "step": output["step"],
            "step_sha256_matches": step_path.is_file() and generator.sha256_path(step_path) == output["step_sha256"],
            "step_has_trailing_whitespace": has_trailing_horizontal_whitespace(step_path),
            "step_whitespace_contract_matches_manifest": output.get(
                "step_has_trailing_whitespace"
            )
            is False
            and not has_trailing_horizontal_whitespace(step_path),
            "step_solid_count": len(step_solids),
            "step_bounds_z_mm": []
            if step_bounds is None
            else [round(float(step_bounds.zmin), 4), round(float(step_bounds.zmax), 4)],
            "step_top_contact_area_mm2": round(actual_contact_area, 4),
            "planned_top_contact_area_mm2": round(float(expected_contact.area), 4),
            "step_top_contact_area_error_mm2": round(contact_area_error, 4),
            "step_top_contact_area_matches_plan": contact_area_error <= 0.20,
            "printable_parts": printable_parts,
            "stl_sha256_matches": all(part["sha256_matches"] for part in printable_parts),
        }
        if split_report is not None:
            report["sides"][side]["split_joint"] = split_report
    return report


def analyze_v2_housing_reuse() -> dict[str, Any]:
    """Compatibility alias for callers that used the superseded reuse verifier."""

    return analyze_v2_housing()


def verify_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if report.get("requirement") != generator.REQUIREMENT:
        errors.append(f"wrong requirement: {report.get('requirement')}")
    if report.get("variant") != generator.VARIANT:
        errors.append(f"wrong variant: {report.get('variant')}")
    if not report.get("generator_sha256_matches"):
        errors.append("housing generator SHA is stale")
    for side in ("left", "right"):
        data = report["sides"][side]
        if not data["source_board_sha256_matches"]:
            errors.append(f"{side}: stale source board SHA")
        if data["legacy_registration_refs"]:
            errors.append(f"{side}: legacy registration refs {data['legacy_registration_refs']}")
        if data["maximum_rail_vertical_gap_mm"] > 1e-6:
            errors.append(f"{side}: rail vertical gap {data['maximum_rail_vertical_gap_mm']} mm")
        if data["maximum_support_vertical_gap_mm"] > 1e-6:
            errors.append(f"{side}: support vertical gap {data['maximum_support_vertical_gap_mm']} mm")
        if not data["rail_plan_area_matches_manifest"]:
            errors.append(f"{side}: stale rail plan area")
        if not data["support_plan_matches_generator"]:
            errors.append(f"{side}: stale support plan")
        categories = {post["category"] for post in data["support_posts"]}
        missing = {"seam", "thumb", "span"} - categories
        if missing:
            errors.append(f"{side}: missing support categories {sorted(missing)}")
        if len(data["support_posts"]) < 8:
            errors.append(f"{side}: only {len(data['support_posts'])} supports")
        for post in data["support_posts"]:
            expected = (
                float(post["diameter_mm"]) == generator.POST_DIAMETER_MM
                and float(post["bottom_z_mm"]) == generator.FLOOR_THICKNESS_MM
                and float(post["top_z_mm"]) == generator.PCB_BOTTOM_Z_MM
                and float(post["nominal_vertical_gap_mm"]) == 0.0
            )
            if not expected:
                errors.append(f"{side}: invalid post dimensions/Z for {post.get('id')}")
        if data["maximum_load_point_to_support_mm"] > generator.MAX_LOAD_POINT_TO_SUPPORT_MM:
            errors.append(
                f"{side}: load point support distance {data['maximum_load_point_to_support_mm']} mm"
            )
        for name in COLLISION_CLASSES:
            result = data["collision_checks"].get(name)
            if result is None:
                errors.append(f"{side}: missing collision class {name}")
            elif result["collision_count"] != 0:
                errors.append(f"{side}: {name} collisions={result['collision_count']}")
        for field in ("registration_peg_count", "screw_pilot_count", "fastener_boss_count"):
            if data[field] != 0:
                errors.append(f"{side}: {field}={data[field]}")
        if data["glue_assumed"]:
            errors.append(f"{side}: glue must not be assumed")
        if not data["step_sha256_matches"] or not data["stl_sha256_matches"]:
            errors.append(f"{side}: stale or missing STEP/STL")
        if data.get("step_has_trailing_whitespace"):
            errors.append(f"{side}: STEP has trailing whitespace")
        if not data.get("step_whitespace_contract_matches_manifest"):
            errors.append(f"{side}: STEP whitespace contract is stale or missing")
        expected_step_solids = 1 if side == "left" else 2
        if data["step_solid_count"] != expected_step_solids:
            errors.append(f"{side}: STEP solid count {data['step_solid_count']}")
        if data["step_bounds_z_mm"] != [0.0, generator.PCB_BOTTOM_Z_MM]:
            errors.append(f"{side}: STEP Z bounds {data['step_bounds_z_mm']}")
        if not data["step_top_contact_area_matches_plan"]:
            errors.append(
                f"{side}: STEP top contact area differs by "
                f"{data['step_top_contact_area_error_mm2']} mm2"
            )
        expected_parts = 1 if side == "left" else 2
        if len(data["printable_parts"]) != expected_parts:
            errors.append(f"{side}: expected {expected_parts} printable parts")
        for part in data["printable_parts"]:
            if part["solid_count"] != 1:
                errors.append(f"{side}:{part['name']}: STL solid count {part['solid_count']}")
            if not part["watertight"] or part["shell_count"] != 1:
                errors.append(
                    f"{side}:{part['name']}: STL watertight={part['watertight']} "
                    f"shell_count={part['shell_count']}"
                )
            if not part["bounds_match_manifest"]:
                errors.append(f"{side}:{part['name']}: STL bounds differ from manifest")
            if any(value > generator.PRINT_VOLUME_LIMIT_MM for value in part["size_xyz_mm"]):
                errors.append(f"{side}:{part['name']}: exceeds 150 mm cube {part['size_xyz_mm']}")
        if side == "right":
            joint = data.get("split_joint", {})
            if joint.get("type") != "overlap_lap_with_m2_case_join":
                errors.append("right: missing mechanical lap joint")
            if joint.get("glue_assumed"):
                errors.append("right: split joint assumes glue")
            if joint.get("part_count") != 2 or joint.get("case_join_fastener_count", 0) < 2:
                errors.append("right: split joint does not independently couple two parts")
            if joint.get("feature_collision_count") != 0 or joint.get("support_collision_count") != 0:
                errors.append("right: split joint collides with board/support keepouts")
            if not joint.get("support_load_path_preserved"):
                errors.append("right: split joint weakens the verified support contact plan")
            if float(joint.get("head_recess_depth_mm", 0.0)) <= 0.0:
                errors.append("right: M2 head has no defined recess")
            if joint.get("assembly_direction") != "bottom_up":
                errors.append("right: case-join screw is not installed bottom-up")
            if float(joint.get("receiving_pilot_start_z_mm", 0.0)) <= float(
                joint.get("head_seat_z_mm", 99.0)
            ):
                errors.append("right: receiving pilot does not leave a positive clamp stack")
            if float(joint.get("receiving_pilot_top_z_mm", 99.0)) >= float(
                joint.get("case_join_boss_top_z_mm", 0.0)
            ):
                errors.append("right: receiving pilot is not blind")
            if float(joint.get("case_join_boss_top_z_mm", 99.0)) + float(
                generator.CASE_JOIN_FDM_Z_TOLERANCE_MM
            ) > float(joint.get("pcb_bottom_z_mm", 0.0)) + 1e-9:
                errors.append("right: worst-case receiving boss reaches above the PCB support plane")
            if float(joint.get("head_exterior_protrusion_max_mm", 99.0)) > 0.0:
                errors.append("right: installed head protrudes below the exterior bottom")
            if float(joint.get("screw_tip_to_pcb_clearance_mm", 0.0)) <= 0.0:
                errors.append("right: worst-case screw tip reaches the PCB support plane")
            if joint.get("head_driver_vertical_collision_count") != 0:
                errors.append("right: M2 head/driver envelope collides")
            if not joint.get("driver_access_from_exterior_bottom"):
                errors.append("right: M2 driver is not accessible from the exterior bottom")
            expected_joint_geometry = {
                "case_join_boss_diameter_mm": generator.CASE_JOIN_BOSS_DIAMETER_MM,
                "case_join_clearance_hole_diameter_mm": generator.CASE_JOIN_CLEARANCE_HOLE_DIAMETER_MM,
                "case_join_clamp_collar_diameter_mm": generator.CASE_JOIN_CLAMP_COLLAR_DIAMETER_MM,
                "case_join_head_recess_diameter_mm": generator.CASE_JOIN_HEAD_RECESS_DIAMETER_MM,
                "case_join_boss_top_z_mm": generator.CASE_JOIN_BOSS_TOP_Z_MM,
                "receiving_pilot_start_z_mm": generator.CASE_JOIN_RECEIVING_PILOT_START_Z_MM,
                "receiving_pilot_top_z_mm": generator.CASE_JOIN_RECEIVING_PILOT_TOP_Z_MM,
                "head_seat_z_mm": generator.CASE_JOIN_HEAD_SEAT_Z_MM,
                "case_join_clamp_collar_top_z_mm": generator.CASE_JOIN_CLAMP_COLLAR_TOP_Z_MM,
            }
            for field, expected in expected_joint_geometry.items():
                if joint.get(field) != expected:
                    errors.append(f"right: joint {field}={joint.get(field)!r}, expected {expected!r}")
            fastener = joint.get("fastener_spec", {})
            expected_recess_clearance = round(
                (
                    generator.CASE_JOIN_HEAD_RECESS_DIAMETER_MM
                    - generator.CASE_JOIN_SCREW_HEAD_DIAMETER_MAX_MM
                )
                / 2.0,
                4,
            )
            expected_head_bearing = round(
                (
                    generator.CASE_JOIN_SCREW_HEAD_DIAMETER_MIN_MM
                    - generator.CASE_JOIN_CLEARANCE_HOLE_DIAMETER_MM
                )
                / 2.0,
                4,
            )
            expected_collar_wall = round(
                (
                    generator.CASE_JOIN_CLAMP_COLLAR_DIAMETER_MM
                    - generator.CASE_JOIN_HEAD_RECESS_DIAMETER_MM
                )
                / 2.0,
                4,
            )
            expected_fastener = {
                "part_number": generator.CASE_JOIN_FASTENER_PART_NUMBER,
                "thread": generator.CASE_JOIN_THREAD,
                "under_head_length_mm": generator.CASE_JOIN_UNDER_HEAD_LENGTH_MM,
                "official_under_head_length_min_mm": generator.CASE_JOIN_UNDER_HEAD_LENGTH_MM
                + generator.CASE_JOIN_LENGTH_LOWER_TOLERANCE_MM,
                "official_under_head_length_max_mm": generator.CASE_JOIN_UNDER_HEAD_LENGTH_MM
                + generator.CASE_JOIN_LENGTH_UPPER_TOLERANCE_MM,
                "official_length_lower_tolerance_mm": generator.CASE_JOIN_LENGTH_LOWER_TOLERANCE_MM,
                "official_length_upper_tolerance_mm": generator.CASE_JOIN_LENGTH_UPPER_TOLERANCE_MM,
                "official_head_diameter_min_mm": generator.CASE_JOIN_SCREW_HEAD_DIAMETER_MIN_MM,
                "official_head_diameter_max_mm": generator.CASE_JOIN_SCREW_HEAD_DIAMETER_MAX_MM,
                "official_head_height_min_mm": generator.CASE_JOIN_SCREW_HEAD_HEIGHT_MIN_MM,
                "official_head_height_max_mm": generator.CASE_JOIN_SCREW_HEAD_HEIGHT_MAX_MM,
                "shank_clearance_hole_diameter_mm": generator.CASE_JOIN_CLEARANCE_HOLE_DIAMETER_MM,
                "head_recess_diameter_mm": generator.CASE_JOIN_HEAD_RECESS_DIAMETER_MM,
                "head_recess_radial_print_clearance_mm": expected_recess_clearance,
                "minimum_radial_head_bearing_mm": expected_head_bearing,
                "minimum_radial_collar_wall_mm": expected_collar_wall,
                "fdm_z_tolerance_mm": generator.CASE_JOIN_FDM_Z_TOLERANCE_MM,
                "part_a_seat_fdm_tolerance_mm": generator.CASE_JOIN_PART_A_SEAT_FDM_TOLERANCE_MM,
                "part_b_boss_fdm_tolerance_mm": generator.CASE_JOIN_PART_B_BOSS_FDM_TOLERANCE_MM,
                "support_plane_fdm_tolerance_mm": generator.CASE_JOIN_SUPPORT_PLANE_FDM_TOLERANCE_MM,
                "minimum_installed_clearance_mm": generator.CASE_JOIN_MIN_INSTALLED_CLEARANCE_MM,
                "installed_screw_tip_to_boss_top_clearance_formula": (
                    "(boss_top_nominal - part_b_boss_fdm_tolerance) - "
                    "(head_seat_nominal + part_a_seat_fdm_tolerance + screw_length_max)"
                ),
                "installed_screw_tip_to_pcb_clearance_formula": (
                    "(pcb_bottom_nominal - support_plane_fdm_tolerance) - "
                    "(head_seat_nominal + part_a_seat_fdm_tolerance + screw_length_max)"
                ),
                "drive": generator.CASE_JOIN_DRIVE,
                "driver_access_direction": "bottom_downward",
                "driver_shaft_diameter_mm": generator.CASE_JOIN_DRIVER_SHAFT_DIAMETER_MM,
            }
            for field, expected in expected_fastener.items():
                if fastener.get(field) != expected:
                    errors.append(f"right: fastener {field}={fastener.get(field)!r}, expected {expected!r}")
            shank_diameter = float(fastener.get("shank_clearance_hole_diameter_mm", 99.0))
            if not 2.4 <= shank_diameter <= 2.6:
                errors.append("right: M2 shank clearance is outside 2.4..2.6 mm")
            if float(fastener.get("head_recess_radial_print_clearance_mm", -99.0)) < float(
                generator.CASE_JOIN_MIN_RECESS_PRINT_CLEARANCE_MM
            ):
                errors.append("right: head recess lacks radial print clearance")
            if float(fastener.get("minimum_radial_head_bearing_mm", -99.0)) < float(
                generator.CASE_JOIN_MIN_HEAD_BEARING_MM
            ):
                errors.append("right: minimum official head has insufficient bearing annulus")
            if float(fastener.get("minimum_radial_collar_wall_mm", -99.0)) < float(
                generator.CASE_JOIN_MIN_COLLAR_WALL_MM
            ):
                errors.append("right: clamp collar wall is too thin around the head recess")
            worst = fastener.get("worst_case", {})
            nominal_clamp_stack = (
                generator.CASE_JOIN_RECEIVING_PILOT_START_Z_MM
                - generator.CASE_JOIN_HEAD_SEAT_Z_MM
            )
            official_length_min = (
                generator.CASE_JOIN_UNDER_HEAD_LENGTH_MM
                + generator.CASE_JOIN_LENGTH_LOWER_TOLERANCE_MM
            )
            official_length_max = (
                generator.CASE_JOIN_UNDER_HEAD_LENGTH_MM
                + generator.CASE_JOIN_LENGTH_UPPER_TOLERANCE_MM
            )
            worst_tip_top = (
                generator.CASE_JOIN_HEAD_SEAT_Z_MM
                + generator.CASE_JOIN_PART_A_SEAT_FDM_TOLERANCE_MM
                + official_length_max
            )
            expected_worst = {
                "screw_length_min_mm": round(official_length_min, 4),
                "screw_length_max_mm": round(official_length_max, 4),
                "clamp_stack_min_mm": round(
                    nominal_clamp_stack - 2.0 * generator.CASE_JOIN_FDM_Z_TOLERANCE_MM,
                    4,
                ),
                "clamp_stack_max_mm": round(
                    nominal_clamp_stack + 2.0 * generator.CASE_JOIN_FDM_Z_TOLERANCE_MM,
                    4,
                ),
                "usable_pilot_depth_mm": round(
                    generator.CASE_JOIN_RECEIVING_PILOT_TOP_Z_MM
                    - generator.CASE_JOIN_FDM_Z_TOLERANCE_MM
                    - (
                        generator.CASE_JOIN_RECEIVING_PILOT_START_Z_MM
                        + generator.CASE_JOIN_FDM_Z_TOLERANCE_MM
                    ),
                    4,
                ),
                "maximum_threaded_penetration_into_pilot_mm": round(
                    worst_tip_top
                    - (
                        generator.CASE_JOIN_RECEIVING_PILOT_START_Z_MM
                        - generator.CASE_JOIN_FDM_Z_TOLERANCE_MM
                    )
                    - generator.CASE_JOIN_TIP_ALLOWANCE_MM,
                    4,
                ),
                "effective_thread_engagement_mm": round(
                    official_length_min
                    - (
                        nominal_clamp_stack
                        + 2.0 * generator.CASE_JOIN_FDM_Z_TOLERANCE_MM
                    )
                    - generator.CASE_JOIN_TIP_ALLOWANCE_MM,
                    4,
                ),
                "receiving_pilot_blind_cap_mm": round(
                    generator.CASE_JOIN_BOSS_TOP_Z_MM
                    - generator.CASE_JOIN_FDM_Z_TOLERANCE_MM
                    - (
                        generator.CASE_JOIN_RECEIVING_PILOT_TOP_Z_MM
                        + generator.CASE_JOIN_FDM_Z_TOLERANCE_MM
                    ),
                    4,
                ),
                "head_exterior_face_z_mm": round(
                    generator.CASE_JOIN_HEAD_SEAT_Z_MM
                    - generator.CASE_JOIN_FDM_Z_TOLERANCE_MM
                    - generator.CASE_JOIN_SCREW_HEAD_HEIGHT_MAX_MM,
                    4,
                ),
                "head_exterior_protrusion_mm": 0.0,
                "screw_tip_top_z_mm": round(worst_tip_top, 4),
                "installed_screw_tip_to_boss_top_clearance_mm": round(
                    generator.CASE_JOIN_BOSS_TOP_Z_MM
                    - generator.CASE_JOIN_PART_B_BOSS_FDM_TOLERANCE_MM
                    - worst_tip_top,
                    4,
                ),
                "installed_screw_tip_to_pcb_clearance_mm": round(
                    generator.PCB_BOTTOM_Z_MM
                    - generator.CASE_JOIN_SUPPORT_PLANE_FDM_TOLERANCE_MM
                    - worst_tip_top,
                    4,
                ),
            }
            for field, expected in expected_worst.items():
                if worst.get(field) != expected:
                    errors.append(
                        f"right: worst-case {field}={worst.get(field)!r}, expected {expected!r}"
                    )
            if float(worst.get("clamp_stack_min_mm", -99.0)) <= 0.0:
                errors.append("right: worst-case independent-part clamp stack is not positive")
            if float(worst.get("usable_pilot_depth_mm", 0.0)) < float(
                worst.get("maximum_threaded_penetration_into_pilot_mm", 99.0)
            ):
                errors.append("right: worst-case threaded penetration exceeds usable blind pilot")
            if float(worst.get("effective_thread_engagement_mm", 0.0)) < float(
                fastener.get("minimum_effective_thread_engagement_mm", 99.0)
            ):
                errors.append("right: worst-case effective pilot thread engagement is insufficient")
            if float(worst.get("receiving_pilot_blind_cap_mm", 0.0)) <= 0.0:
                errors.append("right: receiving pilot lacks a worst-case blind cap")
            if float(worst.get("head_exterior_face_z_mm", -99.0)) <= 0.0:
                errors.append("right: worst-case screw head protrudes below the exterior")
            try:
                installed_tip = (
                    Decimal(str(joint["head_seat_z_mm"]))
                    + Decimal(str(fastener["part_a_seat_fdm_tolerance_mm"]))
                    + Decimal(str(fastener["official_under_head_length_max_mm"]))
                )
                raw_boss_clearance = (
                    Decimal(str(joint["case_join_boss_top_z_mm"]))
                    - Decimal(str(fastener["part_b_boss_fdm_tolerance_mm"]))
                    - installed_tip
                )
                raw_pcb_clearance = (
                    Decimal(str(joint["pcb_bottom_z_mm"]))
                    - Decimal(str(fastener["support_plane_fdm_tolerance_mm"]))
                    - installed_tip
                )
                minimum_installed_clearance = Decimal(
                    str(fastener["minimum_installed_clearance_mm"])
                )
            except (KeyError, ValueError):
                errors.append("right: missing independent-tolerance clearance inputs")
            else:
                if raw_boss_clearance < minimum_installed_clearance:
                    errors.append(
                        "right: installed screw tip boss-top clearance is below the design minimum"
                    )
                if raw_pcb_clearance < minimum_installed_clearance:
                    errors.append(
                        "right: installed screw tip support-plane clearance is below the design minimum"
                    )
            if float(joint.get("head_case_collision_volume_mm3", 99.0)) > 1e-6:
                errors.append("right: specified screw head intersects printed case")
            if float(joint.get("driver_shaft_case_collision_volume_mm3", 99.0)) > 1e-6:
                errors.append("right: specified driver shaft intersects printed case")
    if report["physical_deflection_test"]["status"] != "pending":
        errors.append("physical deflection gate must remain pending until measured")
    if report["fabrication_or_order_ready"]:
        errors.append("draft housing must not claim fabrication/order readiness")
    if report["stale_monolithic_right_stl_present"]:
        errors.append("stale monolithic right STL is present")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify CON-ARCH-006 X3 V2 draft housing supports")
    parser.add_argument("--output", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    report = analyze_v2_housing()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    errors = verify_report(report)
    if errors:
        raise SystemExit("FAIL: CON-ARCH-006 X3 V2 housing\n- " + "\n- ".join(errors))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("PASS: CON-ARCH-006 digital housing support/collision gates; AC-7 remains pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
