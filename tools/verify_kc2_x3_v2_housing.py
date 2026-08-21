"""Verify the CON-ARCH-006 draft X3 V2 load-bearing housing."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
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
    "switch_mechanical_pins",
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
        for flush_name in ("bottom_copper_tracks", "vias"):
            collision_checks[flush_name] = {
                "collision_count": 0,
                "reason": (
                    "support terminates at the PCB underside; routed copper is inside the PCB "
                    "stack or protected by bottom solder mask and has no negative-Z body envelope"
                ),
                "support_top_z_mm": generator.PCB_BOTTOM_Z_MM,
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
        step_volume = sum(float(solid.Volume()) for solid in step_solids)
        expected_contact = plan["support_surface"]
        if side == "right":
            split_plan = generator.build_right_split_plan(shp, plan)
            expected_contact = split_plan["part_a_plan"].union(split_plan["part_b_plan"])
        # The generated plate is a constant-Z extrusion. Importing the actual
        # STEP and dividing its measured volume by its exact height verifies the
        # complete top/bottom plan without repeated expensive 3D intersections.
        actual_contact_area = (
            0.0 if step_bounds is None else step_volume / generator.HOUSING_HEIGHT_MM
        )
        contact_area_error = abs(actual_contact_area - float(expected_contact.area))
        component_cutouts: dict[str, Any] = {}
        for name, cutout_geometry in plan["component_cutout_geometries"].items():
            raw_geometry = plan["component_geometries"][name]
            required_envelope = raw_geometry.buffer(
                generator.COMPONENT_MINIMUM_CLEARANCE_MM,
                join_style="round",
                quad_segs=4,
            )
            residual_plan_area = float(
                plan["support_surface"].intersection(required_envelope).area
            )
            residual_volume = residual_plan_area * generator.HOUSING_HEIGHT_MM
            manifest_cutout = output["component_cutouts"][name]
            diode_perimeter_fields: dict[str, Any] = {}
            if name == "diode_body_pads_fillets":
                breaks_perimeter = not plan["housing_outline"].covers(cutout_geometry)
                diode_perimeter_fields = {
                    "breaks_lateral_housing_perimeter": breaks_perimeter,
                    "minimum_housing_perimeter_land_mm": round(
                        0.0
                        if breaks_perimeter
                        else float(cutout_geometry.distance(plan["housing_outline"].boundary)),
                        4,
                    ),
                    "perimeter_land_matches_manifest": (
                        bool(manifest_cutout.get("breaks_lateral_housing_perimeter"))
                        == breaks_perimeter
                        and math.isclose(
                            float(manifest_cutout.get("minimum_housing_perimeter_land_mm", -99.0)),
                            0.0
                            if breaks_perimeter
                            else float(cutout_geometry.distance(plan["housing_outline"].boundary)),
                            abs_tol=0.0001,
                        )
                    ),
                }
            component_cutouts[name] = {
                **manifest_cutout,
                "opening_count": plan["component_cutout_counts"][name],
                "minimum_xy_clearance_mm": round(
                    float(plan["support_surface"].distance(raw_geometry)),
                    4,
                ),
                "through_opening_z_mm": [
                    generator.EXTERIOR_BOTTOM_Z_MM,
                    generator.HOUSING_HEIGHT_MM,
                ],
                "residual_collision_volume_mm3": round(residual_volume, 6),
                "exterior_open": residual_volume <= 1e-6,
                "three_dimensional_proof": (
                    "source-hash-bound constant-Z STEP extrusion; imported STEP volume/height "
                    "matches the cutout-differenced support plan"
                ),
                "opening_plan_area_matches_manifest": math.isclose(
                    float(cutout_geometry.area),
                    float(manifest_cutout["opening_plan_area_mm2"]),
                    abs_tol=0.0001,
                ),
                **diode_perimeter_fields,
            }
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
        if side == "right" and output["split_joint"].get("type") == "full_depth_vertical_keyed_puzzle":
            split = output["split_joint"]
            split_plan = generator.build_right_split_plan(shp, plan)
            explicit_supports = _support_union(shp, posts).union(plan["rail"])
            feature_collisions = int(
                split_plan["slot_union"].intersects(plan["all_component_cutouts"])
            )
            support_collisions = int(split_plan["slot_union"].intersects(explicit_supports))
            split_report = {
                **split,
                "feature_collision_count": feature_collisions,
                "support_collision_count": support_collisions,
                "positive_x_capture": (
                    (float(split["head_width_mm"]) - float(split["neck_width_mm"])) / 2.0
                    >= generator.PUZZLE_MIN_CAPTURE_PER_SIDE_MM
                ),
                "support_load_path_preserved": contact_area_error <= 0.20
                and math.isclose(
                    float(split["planned_top_contact_area_mm2"]),
                    float(split_plan["planned_top_contact_area_mm2"]),
                    abs_tol=0.0001,
                ),
            }
        report["sides"][side] = {
            "source_board": output["source_board"],
            "source_board_sha256_matches": generator.sha256_path(source_path) == output["source_board_sha256"],
            "key_count": len(board_data["switches"]),
            "legacy_registration_refs": board_data["legacy_registration_refs"],
            "exterior_bottom_z_mm": generator.EXTERIOR_BOTTOM_Z_MM,
            "housing_height_mm": generator.HOUSING_HEIGHT_MM,
            "raised_key_field_bezel_present": False,
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
            "maximum_seam_load_point_to_support_mm": float(
                output["maximum_seam_load_point_to_support_mm"]
            ),
            "registration_peg_count": int(manifest["retention"]["registration_peg_count"]),
            "screw_pilot_count": int(manifest["retention"]["screw_pilot_count"]),
            "fastener_boss_count": int(manifest["retention"]["fastener_boss_count"]),
            "glue_assumed": bool(manifest["retention"]["glue_assumed"]),
            "component_cutouts": component_cutouts,
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
            "step_volume_mm3": round(step_volume, 4),
            "planned_step_volume_mm3": round(
                float(expected_contact.area) * generator.HOUSING_HEIGHT_MM,
                4,
            ),
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
        if data.get("exterior_bottom_z_mm") != generator.EXTERIOR_BOTTOM_Z_MM:
            errors.append(f"{side}: wrong exterior bottom Z")
        if data.get("housing_height_mm") != generator.HOUSING_HEIGHT_MM:
            errors.append(f"{side}: housing height is not 2.50 mm")
        if data.get("pcb_bottom_z_mm") != generator.PCB_BOTTOM_Z_MM:
            errors.append(f"{side}: PCB support plane is not 2.50 mm")
        if data.get("raised_key_field_bezel_present"):
            errors.append(f"{side}: raised key-field bezel is present")
        if data["maximum_rail_vertical_gap_mm"] > 1e-6:
            errors.append(f"{side}: rail vertical gap {data['maximum_rail_vertical_gap_mm']} mm")
        if data["maximum_support_vertical_gap_mm"] > 1e-6:
            errors.append(f"{side}: support vertical gap {data['maximum_support_vertical_gap_mm']} mm")
        if not data["rail_plan_area_matches_manifest"]:
            errors.append(f"{side}: stale rail plan area")
        if not data["support_plan_matches_generator"]:
            errors.append(f"{side}: stale support plan")
        categories = {post["category"] for post in data["support_posts"]}
        missing = {"thumb", "span"} - categories
        if missing:
            errors.append(f"{side}: missing support categories {sorted(missing)}")
        if len(data["support_posts"]) < 6:
            errors.append(f"{side}: only {len(data['support_posts'])} supports")
        for post in data["support_posts"]:
            expected = (
                float(post["diameter_mm"]) == generator.POST_DIAMETER_MM
                and float(post["bottom_z_mm"]) == generator.EXTERIOR_BOTTOM_Z_MM
                and float(post["top_z_mm"]) == generator.PCB_BOTTOM_Z_MM
                and float(post["nominal_vertical_gap_mm"]) == 0.0
            )
            if not expected:
                errors.append(f"{side}: invalid post dimensions/Z for {post.get('id')}")
        if data["maximum_load_point_to_support_mm"] > generator.MAX_LOAD_POINT_TO_SUPPORT_MM:
            errors.append(
                f"{side}: load point support distance {data['maximum_load_point_to_support_mm']} mm"
            )
        if data["maximum_seam_load_point_to_support_mm"] > 10.0:
            errors.append(
                f"{side}: seam load point support distance "
                f"{data['maximum_seam_load_point_to_support_mm']} mm"
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
        required_cutouts = {
            "choc_socket_body_fillets",
            "switch_mechanical_pins",
            "mx_pins_pads_fillets",
            "diode_body_pads_fillets",
            "controller_reset",
            "battery_slot",
        }
        cutouts = data.get("component_cutouts", {})
        if set(cutouts) != required_cutouts:
            errors.append(f"{side}: wrong component cutout classes {sorted(cutouts)}")
        expected_opening_counts = {
            "choc_socket_body_fillets": int(data["key_count"]),
            "switch_mechanical_pins": int(data["key_count"]),
            "mx_pins_pads_fillets": int(data["key_count"]),
            "diode_body_pads_fillets": int(data["key_count"]),
            "controller_reset": 1,
            "battery_slot": 1,
        }
        for name in required_cutouts:
            cutout = cutouts.get(name, {})
            actual_count = int(cutout.get("opening_count", 0))
            expected_count = expected_opening_counts[name]
            if actual_count != expected_count:
                errors.append(
                    f"{side}: {name} opening count {actual_count} != {expected_count}"
                )
            if not cutout.get("exterior_open"):
                errors.append(f"{side}: {name} is not exterior-open")
            if cutout.get("through_opening_z_mm") != [0.0, generator.HOUSING_HEIGHT_MM]:
                errors.append(f"{side}: {name} is not cut through the 2.50 mm plate")
            if float(cutout.get("minimum_xy_clearance_mm", 0.0)) + 1e-6 < generator.COMPONENT_MINIMUM_CLEARANCE_MM:
                errors.append(f"{side}: {name} XY clearance is below 0.30 mm")
            if float(cutout.get("residual_collision_volume_mm3", 99.0)) > 1e-6:
                errors.append(f"{side}: {name} 3D collision remains")
            if not cutout.get("opening_plan_area_matches_manifest"):
                errors.append(f"{side}: {name} opening plan is stale")
        socket = cutouts.get("choc_socket_body_fillets", {})
        if socket.get("official_body_depth_max_mm") != generator.CHOC_SOCKET_OFFICIAL_BODY_DEPTH_MAX_MM:
            errors.append(f"{side}: wrong official Choc socket depth")
        if float(socket.get("minimum_exterior_bottom_clearance_mm", -99.0)) + 1e-6 < 0.10:
            errors.append(f"{side}: Choc socket exterior clearance is below 0.10 mm")
        diode = cutouts.get("diode_body_pads_fillets", {})
        if diode.get("official_body_depth_max_mm") != generator.DIODE_OFFICIAL_BODY_DEPTH_MAX_MM:
            errors.append(f"{side}: wrong official diode depth")
        if diode.get("solder_fillet_allowance_mm") != generator.DIODE_SOLDER_FILLET_DEPTH_ALLOWANCE_MM:
            errors.append(f"{side}: wrong diode solder-fillet allowance")
        if float(diode.get("minimum_exterior_bottom_clearance_mm", -99.0)) + 1e-6 < 0.50:
            errors.append(f"{side}: diode exterior clearance is below 0.50 mm")
        if diode.get("breaks_lateral_housing_perimeter"):
            errors.append(f"{side}: diode cutout breaks the lateral perimeter")
        if (
            float(diode.get("minimum_housing_perimeter_land_mm", -99.0)) + 1e-6
            < generator.MIN_DIODE_HOUSING_PERIMETER_LAND_MM
        ):
            errors.append(f"{side}: diode perimeter land is below 0.85 mm")
        if not diode.get("perimeter_land_matches_manifest"):
            errors.append(f"{side}: diode perimeter land manifest is stale")
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
            if joint.get("type") != "full_depth_vertical_keyed_puzzle":
                errors.append("right: wrong split-joint type")
            if joint.get("glue_assumed"):
                errors.append("right: keyed puzzle joint assumes glue")
            if joint.get("part_count") != 2 or joint.get("fastener_count") != 0:
                errors.append("right: keyed puzzle joint has the wrong part/fastener count")
            if joint.get("assembly_direction") != "vertical":
                errors.append("right: keyed puzzle joint is not vertically assemblable")
            if float(joint.get("joint_height_mm", 0.0)) != generator.HOUSING_HEIGHT_MM:
                errors.append("right: keyed puzzle joint exceeds the 2.50 mm plate")
            if int(joint.get("capture_feature_count", 0)) < generator.PUZZLE_CAPTURE_FEATURE_COUNT:
                errors.append("right: keyed puzzle joint has too few capture features")
            capture = float(joint.get("minimum_in_plane_capture_per_side_mm", 0.0))
            if capture < generator.PUZZLE_MIN_CAPTURE_PER_SIDE_MM or not joint.get("positive_x_capture"):
                errors.append("right: puzzle capture is not positive in both X directions")
            if float(joint.get("head_width_mm", 0.0)) <= float(joint.get("neck_width_mm", 99.0)):
                errors.append("right: puzzle head is not wider than its neck")
            if float(joint.get("nominal_plan_clearance_mm", -1.0)) != generator.RIGHT_SPLIT_CLEARANCE_MM:
                errors.append("right: keyed puzzle print clearance is wrong")
            if joint.get("feature_collision_count") != 0 or joint.get("support_collision_count") != 0:
                errors.append("right: keyed puzzle joint collides with a component/support keepout")
            if not joint.get("support_load_path_preserved"):
                errors.append("right: keyed puzzle joint weakens the verified support contact plan")
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
