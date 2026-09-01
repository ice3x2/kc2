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
from canonical_hash import HASH_POLICY, sha256_file  # noqa: E402


REPORT_PATH = generator.OUTPUT_DIR / "kc2_x3_v2_housing_clearance.json"
ORDER_READINESS_BLOCKER = (
    "CON-ARCH-006 AC-7 physical coupon evidence is pending: exact screw MPN and "
    "drawing; minimum and maximum head diameter and height; maximum finished PCB-hole "
    "diameter and minimum radial bearing width or equivalent pull-through/clamp-retention "
    "evidence; confirmation that the provisional 3.00 x 1.20 mm non-countersunk "
    "rounded pan/button head envelope bounds the selected part; exact driver MPN, "
    "maximum shaft diameter, and runout; printed pilot "
    "diameter, actual PCB thickness, installed penetration, and tip clearance; tapping "
    "torque, stripping torque with at least 2.0 ratio and 3.0 target, and selected "
    "installation torque; ten install/remove cycles without cracking, spin, or pull-out; "
    "full-pattern assembly without sequential forcing; actual installed switch and "
    "keycap-skirt rest/full-travel clearance under the measured head height; and a 2.0 N "
    "deflection test at every worst-case support span "
    "with no more than 0.30 mm displacement, rocking, permanent deformation, support "
    "disengagement, or fastener loosening. CON-ARCH-006 AC-11 controller-service "
    "physical evidence is also pending: exact reset supplier Z/travel/force/reflow limits, "
    "actual socketed-controller and nonconductive-probe service, USB shell/cable clearance, "
    "ten successful double-reset cycles and bootloader enumeration, plus exact protected-pack "
    "MPN, maximum swollen thickness, socket/controller stack clearance, insulation, lead bend, "
    "strain relief, J_BAT1/IMMS solder protrusion, and actual POWER/RESET access. "
    "REL-ARCH-001 AC-3/4/5 evidence is also pending: 20 cold OFF-to-ON and 20 "
    "ON-to-OFF transitions at each required pack voltage, final-assembly RSSI and "
    "packet-loss/disconnect A/B limits, and battery-only, USB charging, charge-complete, "
    "and USB-unplug state coverage."
)
COLLISION_CLASSES = {
    "choc_socket_body",
    "choc_socket_fillets",
    "switch_mechanical_pins",
    "mx_pins_pads_fillets",
    "diode_body_pads_fillets",
    "bottom_copper_tracks",
    "vias",
    "controller_socket",
    "reset_topside",
    "battery_termination",
    "power_switch_leads",
    "battery_slot",
    "switch_key_travel",
}

# Independent CON-ARCH-006 vertical contract.  Keep these verifier values
# separate from generator constants so a coupled generator/manifest mutation
# cannot manufacture a larger clearance result.
VERIFIED_STRUCTURAL_PLATE_HEIGHT_MM = 2.50
VERIFIED_DIODE_DEPTH_MAX_MM = 1.35
VERIFIED_DIODE_SOLDER_ALLOWANCE_MM = 0.30
VERIFIED_DESK_STANDOFF_MM = 1.00
VERIFIED_DESK_STANDOFF_PRINT_TOLERANCE_MM = 0.30
VERIFIED_DIODE_PLATE_BOTTOM_CLEARANCE_MM = (
    VERIFIED_STRUCTURAL_PLATE_HEIGHT_MM
    - VERIFIED_DIODE_DEPTH_MAX_MM
    - VERIFIED_DIODE_SOLDER_ALLOWANCE_MM
)
VERIFIED_DIODE_NOMINAL_DESK_CLEARANCE_MM = (
    VERIFIED_DIODE_PLATE_BOTTOM_CLEARANCE_MM + VERIFIED_DESK_STANDOFF_MM
)
VERIFIED_DIODE_WORST_DESK_CLEARANCE_MM = (
    VERIFIED_DIODE_NOMINAL_DESK_CLEARANCE_MM
    - VERIFIED_DESK_STANDOFF_PRINT_TOLERANCE_MM
)
VERIFIED_CHOC_DEPTH_MAX_MM = 2.30
VERIFIED_CHOC_ASSEMBLY_ALLOWANCE_MM = 0.10
VERIFIED_CHOC_NOMINAL_DESK_CLEARANCE_MM = (
    VERIFIED_STRUCTURAL_PLATE_HEIGHT_MM
    - VERIFIED_CHOC_DEPTH_MAX_MM
    - VERIFIED_CHOC_ASSEMBLY_ALLOWANCE_MM
    + VERIFIED_DESK_STANDOFF_MM
)
VERIFIED_CHOC_WORST_DESK_CLEARANCE_MM = (
    VERIFIED_CHOC_NOMINAL_DESK_CLEARANCE_MM
    - VERIFIED_DESK_STANDOFF_PRINT_TOLERANCE_MM
)
VERIFIED_OPEN_COMPONENT_NOMINAL_DESK_CLEARANCE_MM = min(
    VERIFIED_DIODE_NOMINAL_DESK_CLEARANCE_MM,
    VERIFIED_CHOC_NOMINAL_DESK_CLEARANCE_MM,
)
VERIFIED_OPEN_COMPONENT_MINIMUM_DESK_CLEARANCE_MM = min(
    VERIFIED_DIODE_WORST_DESK_CLEARANCE_MM,
    VERIFIED_CHOC_WORST_DESK_CLEARANCE_MM,
)
VERIFIED_RESET_CENTERS_MM = {
    "left": [126.0625, 63.4500],
    "right": [84.0500, 63.4500],
}
VERIFIED_RESET_ROTATIONS_DEG = {"left": 0.0, "right": 180.0}
VERIFIED_RESET_ACTUATOR_PROJECTION_MM = [2.70, 1.30]
VERIFIED_RESET_SUPPORT_DIAMETER_MM = 3.00
VERIFIED_SERVICE_MINIMUM_HOUSING_LAND_MM = 0.85
VERIFIED_MOUNTING_COORDINATES_MM = {
    "left": [
        [112.8625, 43.0000],
        [144.1125, 66.2500],
        [39.3625, 111.0000],
        [63.6125, 123.0000],
        [81.1125, 151.7500],
        [137.3625, 153.5000],
        [165.8625, 148.7500],
        [75.2500, 134.0000],
    ],
    "right": [
        [97.1875, 43.2500],
        [72.4375, 67.0000],
        [170.4375, 95.2500],
        [194.4375, 98.7500],
        [155.9375, 112.5000],
        [70.1875, 146.7500],
        [97.6875, 152.0000],
        [122.6875, 151.0000],
        [177.7500, 117.2500],
    ],
}


def service_cutout_contract_errors(
    side: str, name: str, cutout: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    if cutout.get("breaks_lateral_housing_perimeter"):
        errors.append(f"{side}: {name} cutout breaks the lateral perimeter")
    if (
        float(cutout.get("minimum_housing_perimeter_land_mm", -99.0)) + 1e-6
        < VERIFIED_SERVICE_MINIMUM_HOUSING_LAND_MM
    ):
        errors.append(
            f"{side}: {name} structural land is below "
            f"{VERIFIED_SERVICE_MINIMUM_HOUSING_LAND_MM:.2f} mm"
        )
    if not cutout.get("perimeter_land_matches_manifest"):
        errors.append(f"{side}: {name} perimeter-land manifest is stale")
    return errors


VERIFIED_MOUNTING_PART_DISTRIBUTION = {
    "left": {"whole": 8},
    "right": {"part_a": 5, "part_b": 4},
}
VERIFIED_DISTRIBUTED_SUPPORT_COUNTS = {"left": 31, "right": 39}
VERIFIED_PRIMARY_SUPPORT_LOAD_SPAN_MM = {"left": 4.3902, "right": 4.3902}
VERIFIED_MOUNTING_MINIMUM_COMPONENT_CLEARANCE_MM = 1.20
VERIFIED_MOUNTING_MINIMUM_COPPER_CLEARANCE_MM = 0.85
VERIFIED_MOUNTING_MINIMUM_BOARD_EDGE_CLEARANCE_MM = 2.10
VERIFIED_MOUNTING_MINIMUM_HOUSING_EDGE_CLEARANCE_MM = 2.00
VERIFIED_MOUNTING_MINIMUM_KEY_SUPPORT_CLEARANCE_MM = 2.50
VERIFIED_MOUNTING_NPTH_DIAMETER_MM = 1.60
VERIFIED_MOUNTING_SUPPORT_LAND_DIAMETER_MM = 3.00
VERIFIED_MOUNTING_PILOT_DIAMETER_MM = 1.10
VERIFIED_MOUNTING_PILOT_DEPTH_MM = 2.80
VERIFIED_MOUNTING_PILOT_BOTTOM_Z_MM = -0.30
VERIFIED_MOUNTING_CLOSED_BOTTOM_MM = 0.70
VERIFIED_MOUNTING_FASTENER_HEAD_STYLE = "non_countersunk_rounded_pan_or_button"
VERIFIED_MOUNTING_HEAD_ENVELOPE_MM = [3.00, 1.20]
VERIFIED_MOUNTING_HEAD_RESERVE_MM = 0.25
VERIFIED_MOUNTING_DRIVER_DIAMETER_MM = 3.00
VERIFIED_PROVISIONAL_SCREW_UNDER_HEAD_LENGTH_MM = 4.00
VERIFIED_PCB_TOLERANCE_PENETRATION_RANGE_MM = [2.24, 2.56]
VERIFIED_MINIMUM_TIP_CLEARANCE_MM = 0.24
VERIFIED_MOUNTING_UNRELATED_SUPPORT_RESERVE_MM = 0.25
VERIFIED_MOUNTING_SERVICE_BODY_ENVELOPES = {
    "battery_body_size_mm": [30.00, 12.00],
    "power_switch_body_size_mm": [10.00, 2.50],
    "power_switch_actuator_travel_mm": 1.60,
    "power_switch_actuator_sweep_size_mm": [13.20, 2.50],
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
    bottom_z = mins[2]
    bottom_adjacency: dict[tuple[float, float, float], set[tuple[float, float, float]]] = defaultdict(set)
    for index in range(0, len(vertices), 3):
        triangle = [tuple(round(value, 6) for value in vertex) for vertex in vertices[index : index + 3]]
        if not all(abs(vertex[2] - bottom_z) <= 1e-5 for vertex in triangle):
            continue
        for start, end in zip(triangle, (triangle[1], triangle[2], triangle[0])):
            bottom_adjacency[start].add(end)
            bottom_adjacency[end].add(start)
    bottom_components: list[set[tuple[float, float, float]]] = []
    unseen_bottom = set(bottom_adjacency)
    while unseen_bottom:
        component = {unseen_bottom.pop()}
        stack = list(component)
        while stack:
            current = stack.pop()
            neighbors = bottom_adjacency[current] & unseen_bottom
            unseen_bottom.difference_update(neighbors)
            component.update(neighbors)
            stack.extend(neighbors)
        bottom_components.append(component)
    bottom_centers = sorted(
        [
            [
                round((min(vertex[0] for vertex in component) + max(vertex[0] for vertex in component)) / 2.0, 4),
                round((min(vertex[1] for vertex in component) + max(vertex[1] for vertex in component)) / 2.0, 4),
            ]
            for component in bottom_components
        ]
    )
    return {
        "solid_count": solid_count,
        "watertight": bool(edge_counts) and all(count == 2 for count in edge_counts.values()),
        "shell_count": shell_count,
        "bounds_xyz_mm": [round(value, 4) for value in (*mins, *maxs)],
        "size_xyz_mm": [round(maxs[index] - mins[index], 4) for index in range(3)],
        "desk_contact_z_mm": round(bottom_z, 4),
        "desk_contact_count": len(bottom_components),
        "desk_contact_centers_mm": bottom_centers,
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
        "hash_policy": manifest.get("hash_policy"),
        "generator_sha256_matches": sha256_file(generator.GENERATOR_PATH)
        == manifest.get("generator_sha256"),
        "order_ready": bool(manifest.get("order_ready", False)),
        "physical_registration_status": manifest.get("retention", {}).get(
            "physical_registration_status"
        ),
        "sides": {},
        "physical_deflection_test": manifest["physical_deflection_test"],
        "fabrication_or_order_ready": False,
        "order_readiness_blocker": ORDER_READINESS_BLOCKER,
        "stale_monolithic_right_stl_present": (
            generator.OUTPUT_DIR / "kc2_right_x3_v2_lower_housing.stl"
        ).exists(),
    }

    for side in ("left", "right"):
        board_data = extracted["boards"][side]
        output = manifest["outputs"][side]
        plan = generator.build_plan_geometry(shp, side, board_data)
        desk_contact_manifest_matches_generator = output.get("desk_contacts") == plan[
            "desk_contacts"
        ]
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
        expected_part_plans = [plan["support_surface"]]
        if side == "right":
            split_plan = generator.build_right_split_plan(shp, plan)
            expected_contact = split_plan["part_a_plan"].union(split_plan["part_b_plan"])
            expected_part_plans = [split_plan["part_a_plan"], split_plan["part_b_plan"]]
        expected_mounting = generator.mounting_system_manifest(
            shp,
            side,
            plan,
            expected_part_plans,
        )
        expected_desk_contact_geometry = plan["desk_contact_geometry"].intersection(expected_contact)
        expected_pilot_geometry = plan["mounting_pilot_geometry"].intersection(
            expected_contact
        )
        expected_step_volume = (
            float(expected_contact.area) * generator.HOUSING_HEIGHT_MM
            + float(expected_desk_contact_geometry.area) * generator.DESK_STANDOFF_NOMINAL_MM
            - float(expected_pilot_geometry.area) * generator.MOUNTING_PILOT_DEPTH_MM
        )
        # Subtract the independently planned underside-contact volume before
        # dividing by the structural height, so the imported STEP still proves
        # the complete zero-gap PCB support plan after feet are added.
        actual_support_surface_area = (
            0.0
            if step_bounds is None
            else (
                step_volume
                - float(expected_desk_contact_geometry.area)
                * generator.DESK_STANDOFF_NOMINAL_MM
                + float(expected_pilot_geometry.area)
                * generator.MOUNTING_PILOT_DEPTH_MM
            )
            / generator.HOUSING_HEIGHT_MM
        )
        actual_contact_area = actual_support_surface_area - float(
            expected_pilot_geometry.area
        )
        expected_top_contact_area = float(
            expected_contact.difference(expected_pilot_geometry).area
        )
        contact_area_error = abs(actual_contact_area - expected_top_contact_area)
        step_volume_error = abs(step_volume - expected_step_volume)
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
            perimeter_fields: dict[str, Any] = {}
            if name == "diode_body_pads_fillets" or name in {
                "battery_termination",
                "power_switch_leads",
                "battery_slot",
            }:
                breaks_perimeter = not plan["housing_outline"].covers(cutout_geometry)
                perimeter_fields = {
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
                **perimeter_fields,
            }
        printable_parts = []
        for part, part_plan in zip(output["printable_parts"], expected_part_plans):
            stl_path = ROOT / part["stl"]
            inspected = inspect_ascii_stl(stl_path) if stl_path.is_file() else {
                "solid_count": 0,
                "watertight": False,
                "shell_count": 0,
                "bounds_xyz_mm": [],
                "size_xyz_mm": [],
                "desk_contact_z_mm": None,
                "desk_contact_count": 0,
                "desk_contact_centers_mm": [],
            }
            expected_contacts = generator.desk_contacts_for_part(shp, plan, part_plan)
            expected_ids = [item["id"] for item in expected_contacts]
            manifest_ids = list(part.get("desk_contact_ids", []))
            expected_centers = sorted(
                [[round(float(item["x_mm"]), 4), round(float(item["y_mm"]), 4)] for item in expected_contacts]
            )
            actual_centers = inspected["desk_contact_centers_mm"]
            actual_centers_match = len(actual_centers) == len(expected_centers) and all(
                abs(float(actual_value) - float(expected_value)) <= 0.05
                for actual, expected in zip(actual_centers, expected_centers)
                for actual_value, expected_value in zip(actual, expected)
            )
            actual_contact_records = [
                {
                    "id": f"ACTUAL-{index + 1:02d}",
                    "x_mm": center[0],
                    "y_mm": center[1],
                    "diameter_mm": generator.DESK_CONTACT_DIAMETER_MM,
                    "bottom_z_mm": inspected["desk_contact_z_mm"],
                }
                for index, center in enumerate(actual_centers)
            ]
            actual_stability = generator.desk_contact_stability_manifest(
                shp,
                part_plan,
                actual_contact_records,
            )
            printable_parts.append(
                {
                    "name": part["name"],
                    "stl": part["stl"],
                    "sha256_matches": stl_path.is_file()
                    and sha256_file(stl_path) == part["stl_sha256"],
                    "solid_count": inspected["solid_count"],
                    "watertight": inspected["watertight"],
                    "shell_count": inspected["shell_count"],
                    "bounds_xyz_mm": inspected["bounds_xyz_mm"],
                    "size_xyz_mm": inspected["size_xyz_mm"],
                    "desk_contact_count": int(part.get("desk_contact_count", 0)),
                    "expected_desk_contact_count": len(expected_contacts),
                    "actual_desk_contact_count": inspected["desk_contact_count"],
                    "expected_desk_contact_ids": expected_ids,
                    "manifest_desk_contact_ids": manifest_ids,
                    "expected_desk_contact_centers_mm": expected_centers,
                    "actual_desk_contact_centers_mm": actual_centers,
                    "desk_contact_z_mm": inspected["desk_contact_z_mm"],
                    "desk_contact_coplanarity_mm": actual_stability[
                        "desk_contact_coplanarity_mm"
                    ],
                    "projected_centroid_inside_contact_hull": actual_stability[
                        "projected_centroid_inside_contact_hull"
                    ],
                    "desk_contacts_match_plan": bool(
                        actual_centers_match
                        and manifest_ids == expected_ids
                        and int(part.get("desk_contact_count", 0)) == len(expected_contacts)
                    ),
                    "desk_contacts_statically_stable": bool(
                        actual_centers_match
                        and manifest_ids == expected_ids
                        and part.get("desk_contacts_statically_stable")
                        and actual_stability["desk_contacts_statically_stable"]
                    ),
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
            explicit_supports = (
                _support_union(shp, posts)
                .union(plan["rail"])
                .union(plan["mounting_land_geometry"])
                .union(plan["reset_local_support_geometry"])
            )
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
        manifest_mounting = output.get("mounting_system", {})
        manifest_holes = {
            item.get("ref"): item
            for item in manifest_mounting.get("holes", [])
        }
        mounting_holes = []
        for expected_hole in expected_mounting["holes"]:
            manifest_hole = manifest_holes.get(expected_hole["ref"], {})
            center_x, center_y = expected_hole["housing_center_mm"]

            def step_contains(z_mm: float) -> bool:
                return any(
                    solid.isInside(
                        cq.Vector(center_x, center_y, z_mm),
                        1e-6,
                    )
                    for solid in step_solids
                )

            mounting_holes.append(
                {
                    **manifest_hole,
                    "geometry_collision_checks": expected_hole["collision_checks"],
                    "geometry_collision_count": expected_hole["collision_count"],
                    "geometry_printable_part": expected_hole["printable_part"],
                    "geometry_board_feature_matches": expected_hole[
                        "board_feature_matches"
                    ],
                    "geometry_support_land_to_existing_support_mm": expected_hole[
                        "support_land_to_existing_support_mm"
                    ],
                    "geometry_head_to_existing_support_mm": expected_hole[
                        "head_to_existing_support_mm"
                    ],
                    "geometry_head_to_support_posts_mm": expected_hole[
                        "head_to_support_posts_mm"
                    ],
                    "geometry_head_to_analytical_rail_mm": expected_hole[
                        "head_to_analytical_rail_mm"
                    ],
                    "geometry_head_to_installed_component_mm": expected_hole[
                        "head_to_installed_component_mm"
                    ],
                    "geometry_head_to_routed_copper_or_via_mm": expected_hole[
                        "head_to_routed_copper_or_via_mm"
                    ],
                    "geometry_head_to_board_edge_mm": expected_hole[
                        "head_to_board_edge_mm"
                    ],
                    "geometry_head_to_housing_edge_mm": expected_hole[
                        "head_to_housing_edge_mm"
                    ],
                    "geometry_driver_to_battery_body_mm": expected_hole[
                        "driver_to_battery_body_mm"
                    ],
                    "geometry_driver_to_power_switch_body_mm": expected_hole[
                        "driver_to_power_switch_body_mm"
                    ],
                    "geometry_driver_to_power_switch_actuator_sweep_mm": expected_hole[
                        "driver_to_power_switch_actuator_sweep_mm"
                    ],
                    "step_pilot_open_at_z_2_49": not step_contains(2.49),
                    "step_pilot_open_at_z_minus_0_25": not step_contains(-0.25),
                    "step_pilot_closed_at_z_minus_0_35": step_contains(-0.35),
                    "step_pilot_closed_at_z_minus_0_79": step_contains(-0.79),
                    "step_pilot_closed_at_z_minus_0_99": step_contains(-0.99),
                }
            )
        mounting_report = {
            **manifest_mounting,
            "holes": mounting_holes,
            "manifest_matches_generator": manifest_mounting == expected_mounting,
            "geometry_part_distribution": expected_mounting["part_distribution"],
            "geometry_part_distribution_matches_plan": expected_mounting[
                "part_distribution_matches_plan"
            ],
            "geometry_primary_support_load_span_unchanged": expected_mounting[
                "primary_support_load_span_unchanged"
            ],
            "geometry_fastener_head_style": expected_mounting[
                "fastener_head_style"
            ],
            "geometry_head_envelope_mm": expected_mounting["head_envelope_mm"],
            "geometry_head_reserve_mm": expected_mounting["head_reserve_mm"],
            "geometry_head_height_and_keycap_skirt_physical_status": (
                expected_mounting[
                    "head_height_and_keycap_skirt_physical_status"
                ]
            ),
            "geometry_analytical_rail_relief": expected_mounting[
                "analytical_rail_relief"
            ],
            "geometry_service_body_envelopes": expected_mounting[
                "service_body_envelopes"
            ],
        }
        manifest_reset_support = output.get("reset_local_support", {})
        expected_reset_support = plan["reset_local_support"]
        reset_local_support_report = {
            **manifest_reset_support,
            "manifest_matches_generator": manifest_reset_support == expected_reset_support,
            "geometry_board_center_mm": expected_reset_support["board_center_mm"],
            "geometry_footprint_rotation_deg": expected_reset_support[
                "footprint_rotation_deg"
            ],
            "geometry_actuator_projection_covered": expected_reset_support[
                "actuator_projection_covered"
            ],
            "geometry_support_surface_covered": expected_reset_support[
                "support_surface_covered"
            ],
            "geometry_component_cutout_collision_count": expected_reset_support[
                "component_cutout_collision_count"
            ],
            "geometry_bottom_exposed_pad_collision_count": expected_reset_support[
                "bottom_exposed_pad_collision_count"
            ],
            "geometry_via_collision_count": expected_reset_support["via_collision_count"],
            "geometry_bottom_routed_copper_overlap_count": expected_reset_support[
                "bottom_routed_copper_overlap_count"
            ],
            "geometry_bottom_mask_opening_overlap_count": expected_reset_support[
                "bottom_mask_opening_overlap_count"
            ],
            "geometry_bottom_exposed_routed_copper_overlap_count": expected_reset_support[
                "bottom_exposed_routed_copper_overlap_count"
            ],
            "geometry_bottom_routed_copper_solder_mask_protected": expected_reset_support[
                "bottom_routed_copper_solder_mask_protected"
            ],
            "geometry_electrically_safe": expected_reset_support["electrically_safe"],
        }
        report["sides"][side] = {
            "source_board": output["source_board"],
            "source_board_sha256": output["source_board_sha256"],
            "source_board_sha256_matches": sha256_file(source_path) == output["source_board_sha256"],
            "key_count": len(board_data["switches"]),
            "legacy_registration_refs": board_data["legacy_registration_refs"],
            "battery_above_carrier": {
                **output.get("battery_above_carrier", {}),
                "fresh_extraction_manifest_binding": bool(
                    output.get("battery_above_carrier", {}).get("source_board")
                    == output.get("source_board")
                    and output.get("battery_above_carrier", {}).get(
                        "source_board_sha256"
                    )
                    == output.get("source_board_sha256")
                    and output.get("battery_above_carrier", {}).get(
                        "source_board_sha256"
                    )
                    == sha256_file(source_path)
                ),
            },
            "exterior_bottom_z_mm": generator.EXTERIOR_BOTTOM_Z_MM,
            "housing_height_mm": generator.HOUSING_HEIGHT_MM,
            "desk_standoff_nominal_mm": float(output["desk_standoff_nominal_mm"]),
            "desk_standoff_print_tolerance_mm": float(
                output["desk_standoff_print_tolerance_mm"]
            ),
            "desk_datum_z_mm": float(output["desk_datum_z_mm"]),
            "minimum_open_component_to_desk_nominal_clearance_mm": float(
                output["minimum_open_component_to_desk_nominal_clearance_mm"]
            ),
            "minimum_open_component_to_desk_clearance_mm": float(
                output["minimum_open_component_to_desk_clearance_mm"]
            ),
            "desk_contacts_hidden_in_top_view": bool(
                plan["housing_outline"].covers(plan["desk_contact_geometry"])
            )
            and bool(output.get("desk_contacts_hidden_in_top_view")),
            "desk_contact_component_cutout_collision_count": int(
                not plan["desk_contact_geometry"].intersection(
                    plan["all_component_cutouts"]
                ).is_empty
            ),
            "desk_contact_manifest_matches_generator": bool(
                desk_contact_manifest_matches_generator
            ),
            "desk_contacts_statically_stable": all(
                part["desk_contacts_statically_stable"] for part in printable_parts
            )
            and bool(output.get("desk_contacts_statically_stable")),
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
            "all_key_loads_have_dedicated_support": bool(
                output.get("all_key_loads_have_dedicated_support")
            )
            and bool(mounting_report.get("all_key_loads_have_dedicated_support")),
            "key_load_support_network_matches_contract": bool(
                output.get("key_load_support_network_matches_contract")
            )
            and bool(
                mounting_report.get("key_load_support_network_matches_contract")
            ),
            "reset_local_support": reset_local_support_report,
            "mounting_system": mounting_report,
            "maximum_load_point_to_support_mm": float(output["maximum_load_point_to_support_mm"]),
            "maximum_seam_load_point_to_support_mm": float(
                output["maximum_seam_load_point_to_support_mm"]
            ),
            "registration_peg_count": int(manifest["retention"]["registration_peg_count"]),
            "screw_pilot_count": int(
                manifest["retention"]["screw_pilot_count_by_side"][side]
            ),
            "fastener_boss_count": int(manifest["retention"]["fastener_boss_count"]),
            "glue_assumed": bool(manifest["retention"]["glue_assumed"]),
            "component_cutouts": component_cutouts,
            "collision_checks": collision_checks,
            "step": output["step"],
            "step_sha256_matches": step_path.is_file() and sha256_file(step_path) == output["step_sha256"],
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
            "planned_step_volume_mm3": round(expected_step_volume, 4),
            "step_volume_error_mm3": round(step_volume_error, 4),
            "step_volume_matches_plan": step_volume_error <= 0.20,
            "step_top_contact_area_mm2": round(actual_contact_area, 4),
            "planned_top_contact_area_mm2": round(expected_top_contact_area, 4),
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
    if report.get("hash_policy") != HASH_POLICY:
        errors.append(f"wrong hash policy: {report.get('hash_policy')}")
    if not report.get("generator_sha256_matches"):
        errors.append("housing generator SHA is stale")
    if report.get("order_ready"):
        errors.append("order readiness must remain false for the provisional mounting interface")
    if report.get("physical_registration_status") != "pending":
        errors.append("physical registration status must remain pending")
    if report.get("order_readiness_blocker") != ORDER_READINESS_BLOCKER:
        errors.append("order-readiness blocker does not enumerate the full AC-7 physical coupon gate")
    for side in ("left", "right"):
        data = report["sides"][side]
        if not data["source_board_sha256_matches"]:
            errors.append(f"{side}: stale source board SHA")
        if data["legacy_registration_refs"]:
            errors.append(f"{side}: legacy registration refs {data['legacy_registration_refs']}")
        if data.get("exterior_bottom_z_mm") != generator.EXTERIOR_BOTTOM_Z_MM:
            errors.append(f"{side}: wrong exterior bottom Z")
        if data.get("housing_height_mm") != VERIFIED_STRUCTURAL_PLATE_HEIGHT_MM:
            errors.append(f"{side}: housing height is not 2.50 mm")
        if data.get("pcb_bottom_z_mm") != generator.PCB_BOTTOM_Z_MM:
            errors.append(f"{side}: PCB support plane is not 2.50 mm")
        if data.get("desk_standoff_nominal_mm") != VERIFIED_DESK_STANDOFF_MM:
            errors.append(f"{side}: desk standoff is not 1.00 mm")
        if (
            data.get("desk_standoff_print_tolerance_mm")
            != VERIFIED_DESK_STANDOFF_PRINT_TOLERANCE_MM
        ):
            errors.append(f"{side}: desk standoff print tolerance is wrong")
        if data.get("desk_datum_z_mm") != generator.DESK_DATUM_Z_MM:
            errors.append(f"{side}: desk datum Z is wrong")
        battery = data.get("battery_above_carrier", {})
        if battery.get("ref") != generator.BATTERY_REFERENCE:
            errors.append(f"{side}: above-carrier battery is not bound to exact BAT1")
        if battery.get("center") != generator.BATTERY_CENTERS_MM[side]:
            errors.append(f"{side}: above-carrier BAT1 center is wrong")
        if battery.get("size_mm") != list(generator.BATTERY_NOMINAL_PLAN_ENVELOPE_MM):
            errors.append(f"{side}: above-carrier battery plan envelope is not 30x12 mm")
        if battery.get("modeled_depth_mm") != generator.BATTERY_MODELED_DEPTH_MM:
            errors.append(f"{side}: above-carrier battery depth is not 3.00 mm")
        if battery.get("housing_body_cutout") is not False:
            errors.append(f"{side}: lower housing still declares a battery-body cutout")
        if battery.get("source_board") != data.get("source_board"):
            errors.append(f"{side}: BAT1 extraction source board is stale")
        if battery.get("source_board_sha256") != data.get("source_board_sha256"):
            errors.append(f"{side}: BAT1 extraction source hash is stale")
        if not battery.get("fresh_extraction_manifest_binding"):
            errors.append(f"{side}: BAT1 extraction-manifest binding is not fresh")
        if float(data.get("minimum_open_component_to_desk_clearance_mm", -99.0)) + 1e-6 < 0.50:
            errors.append(f"{side}: open-component-to-desk clearance is below 0.50 mm")
        if not math.isclose(
            float(data.get("minimum_open_component_to_desk_nominal_clearance_mm", -99.0)),
            VERIFIED_OPEN_COMPONENT_NOMINAL_DESK_CLEARANCE_MM,
            abs_tol=1e-9,
        ):
            errors.append(f"{side}: open-component nominal desk-clearance formula is stale")
        if not math.isclose(
            float(data.get("minimum_open_component_to_desk_clearance_mm", -99.0)),
            VERIFIED_OPEN_COMPONENT_MINIMUM_DESK_CLEARANCE_MM,
            abs_tol=1e-9,
        ):
            errors.append(f"{side}: open-component worst-case desk-clearance formula is stale")
        if not data.get("desk_contacts_hidden_in_top_view"):
            errors.append(f"{side}: desk contacts widen the visible top-view outline")
        if int(data.get("desk_contact_component_cutout_collision_count", 99)) != 0:
            errors.append(f"{side}: desk contact collides with an exterior-open component cutout")
        if not data.get("desk_contacts_statically_stable"):
            errors.append(f"{side}: desk contacts are not statically stable")
        if not data.get("desk_contact_manifest_matches_generator"):
            errors.append(f"{side}: desk-contact manifest differs from generator")
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
        categories = {post.get("category") for post in data["support_posts"]}
        if categories != {"key_load"}:
            errors.append(f"{side}: support categories are not exclusively key_load")
        if len(data["support_posts"]) != VERIFIED_DISTRIBUTED_SUPPORT_COUNTS[side]:
            errors.append(
                f"{side}: distributed support count {len(data['support_posts'])} "
                f"!= {VERIFIED_DISTRIBUTED_SUPPORT_COUNTS[side]}"
            )
        expected_switch_refs = {
            f"SW{index}" for index in range(1, int(data["key_count"]) + 1)
        }
        actual_switch_refs = [post.get("switch_ref") for post in data["support_posts"]]
        if (
            set(actual_switch_refs) != expected_switch_refs
            or len(actual_switch_refs) != len(set(actual_switch_refs))
        ):
            errors.append(f"{side}: key-load support references are not a switch bijection")
        if not data.get("all_key_loads_have_dedicated_support"):
            errors.append(f"{side}: not every key load has a dedicated support")
        if not data.get("key_load_support_network_matches_contract"):
            errors.append(f"{side}: key-load support network does not match the generator")
        for post in data["support_posts"]:
            expected = (
                float(post["diameter_mm"]) == generator.POST_DIAMETER_MM
                and float(post["bottom_z_mm"]) == generator.EXTERIOR_BOTTOM_Z_MM
                and float(post["top_z_mm"]) == generator.PCB_BOTTOM_Z_MM
                and float(post["nominal_vertical_gap_mm"]) == 0.0
            )
            if not expected:
                errors.append(f"{side}: invalid post dimensions/Z for {post.get('id')}")
            if float(post.get("effective_load_point_to_support_edge_mm", 99.0)) > (
                generator.MAX_LOAD_POINT_TO_SUPPORT_MM + 1e-6
            ):
                errors.append(
                    f"{side}: {post.get('switch_ref')} support/rail network is too far from its load point"
                )
        if data["maximum_load_point_to_support_mm"] > generator.MAX_LOAD_POINT_TO_SUPPORT_MM:
            errors.append(
                f"{side}: load point support distance {data['maximum_load_point_to_support_mm']} mm"
            )
        if data["maximum_seam_load_point_to_support_mm"] > 10.0:
            errors.append(
                f"{side}: seam load point support distance "
                f"{data['maximum_seam_load_point_to_support_mm']} mm"
            )
        if not math.isclose(
            float(data["maximum_load_point_to_support_mm"]),
            VERIFIED_PRIMARY_SUPPORT_LOAD_SPAN_MM[side],
            abs_tol=0.0001,
        ):
            errors.append(
                f"{side}: primary-support load span changed from "
                f"{VERIFIED_PRIMARY_SUPPORT_LOAD_SPAN_MM[side]} mm"
            )
        for name in COLLISION_CLASSES:
            result = data["collision_checks"].get(name)
            if result is None:
                errors.append(f"{side}: missing collision class {name}")
            elif result["collision_count"] != 0:
                errors.append(f"{side}: {name} collisions={result['collision_count']}")
        for field in ("registration_peg_count", "fastener_boss_count"):
            if data[field] != 0:
                errors.append(f"{side}: {field}={data[field]}")
        if data["screw_pilot_count"] != len(VERIFIED_MOUNTING_COORDINATES_MM[side]):
            errors.append(f"{side}: wrong screw-pilot count {data['screw_pilot_count']}")
        if data["glue_assumed"]:
            errors.append(f"{side}: glue must not be assumed")

        reset = data.get("reset_local_support", {})
        if reset.get("ref") != generator.RESET_REFERENCE:
            errors.append(f"{side}: reset local support is not bound to exact SW_RST1")
        if reset.get("board_center_mm") != VERIFIED_RESET_CENTERS_MM[side]:
            errors.append(f"{side}: reset local support board coordinate is wrong")
        if reset.get("footprint_side") != "top":
            errors.append(f"{side}: reset local support is not top-side")
        if (
            reset.get("footprint_rotation_deg") != VERIFIED_RESET_ROTATIONS_DEG[side]
            or reset.get("geometry_footprint_rotation_deg")
            != VERIFIED_RESET_ROTATIONS_DEG[side]
        ):
            errors.append(f"{side}: reset local support rotation is wrong")
        if reset.get("actuator_projection_size_mm") != VERIFIED_RESET_ACTUATOR_PROJECTION_MM:
            errors.append(f"{side}: reset local support actuator projection is wrong")
        if (
            reset.get("support_diameter_mm") != VERIFIED_RESET_SUPPORT_DIAMETER_MM
            or reset.get("support_top_z_mm") != VERIFIED_STRUCTURAL_PLATE_HEIGHT_MM
            or reset.get("support_vertical_gap_mm") != 0.0
            or reset.get("desk_column_bottom_z_mm") != -VERIFIED_DESK_STANDOFF_MM
        ):
            errors.append(f"{side}: reset local support diameter/Z contract is wrong")
        if not reset.get("manifest_matches_generator"):
            errors.append(f"{side}: reset local support manifest differs from generator")
        if reset.get("geometry_board_center_mm") != VERIFIED_RESET_CENTERS_MM[side]:
            errors.append(f"{side}: reset local support geometry coordinate is wrong")
        if not reset.get("actuator_projection_covered") or not reset.get(
            "geometry_actuator_projection_covered"
        ):
            errors.append(f"{side}: reset local support does not cover the actuator")
        if not reset.get("support_surface_covered") or not reset.get(
            "geometry_support_surface_covered"
        ):
            errors.append(f"{side}: reset local support leaves the zero-gap support surface")
        if (
            int(reset.get("component_cutout_collision_count", 99)) != 0
            or int(reset.get("geometry_component_cutout_collision_count", 99)) != 0
            or int(reset.get("bottom_exposed_pad_collision_count", 99)) != 0
            or int(reset.get("geometry_bottom_exposed_pad_collision_count", 99)) != 0
            or int(reset.get("via_collision_count", 99)) != 0
            or int(reset.get("geometry_via_collision_count", 99)) != 0
        ):
            errors.append(f"{side}: reset local support has an electrical/mechanical collision")
        if (
            int(reset.get("bottom_routed_copper_overlap_count", 99))
            != int(reset.get("geometry_bottom_routed_copper_overlap_count", 98))
            or int(reset.get("bottom_mask_opening_overlap_count", 99))
            != int(reset.get("geometry_bottom_mask_opening_overlap_count", 98))
            or int(reset.get("bottom_exposed_routed_copper_overlap_count", 99))
            != 0
            or int(reset.get("geometry_bottom_exposed_routed_copper_overlap_count", 99))
            != 0
        ):
            errors.append(f"{side}: reset local support B.Cu/B.Mask derivation is unsafe or stale")
        if reset.get("bottom_routed_copper_solder_mask_protection_basis") != (
            "derived_from_exact_B.Cu_and_B.Mask_geometry"
        ):
            errors.append(f"{side}: reset local support B.Cu/B.Mask basis is stale")
        if not reset.get("bottom_routed_copper_solder_mask_protected") or not reset.get(
            "geometry_bottom_routed_copper_solder_mask_protected"
        ):
            errors.append(f"{side}: reset local support bottom-route protection is not documented")
        if not reset.get("electrically_safe") or not reset.get("geometry_electrically_safe"):
            errors.append(f"{side}: reset local support is not electrically safe")

        mounting = data.get("mounting_system", {})
        if mounting.get("physical_registration_status") != "pending":
            errors.append(f"{side}: mounting physical registration status is not pending")
        if int(mounting.get("count", 0)) != len(VERIFIED_MOUNTING_COORDINATES_MM[side]):
            errors.append(f"{side}: wrong mounting-hole count")
        if mounting.get("board_coordinates_mm") != VERIFIED_MOUNTING_COORDINATES_MM[side]:
            errors.append(f"{side}: board coordinate contract differs from CON-ARCH-006")
        if not mounting.get("board_features_match_selected_pattern"):
            errors.append(f"{side}: board MH features do not match the selected pattern")
        if not mounting.get("manifest_matches_generator"):
            errors.append(f"{side}: mounting manifest differs from generator")
        if mounting.get("part_distribution") != VERIFIED_MOUNTING_PART_DISTRIBUTION[side]:
            errors.append(f"{side}: part distribution is wrong")
        if mounting.get("geometry_part_distribution") != VERIFIED_MOUNTING_PART_DISTRIBUTION[side]:
            errors.append(f"{side}: geometry part distribution is wrong")
        if not mounting.get("part_distribution_matches_plan") or not mounting.get(
            "geometry_part_distribution_matches_plan"
        ):
            errors.append(f"{side}: part distribution does not match the split plan")
        if int(mounting.get("distributed_support_count", 0)) != VERIFIED_DISTRIBUTED_SUPPORT_COUNTS[side]:
            errors.append(f"{side}: mounting contract changed the distributed support count")
        if int(mounting.get("dedicated_key_load_support_count", 0)) != (
            VERIFIED_DISTRIBUTED_SUPPORT_COUNTS[side]
        ):
            errors.append(f"{side}: dedicated key-load support count is wrong")
        if not mounting.get("all_key_loads_have_dedicated_support") or not mounting.get(
            "key_load_support_network_matches_contract"
        ):
            errors.append(f"{side}: mounting contract lost the per-key support network")
        if not mounting.get("primary_support_load_span_unchanged") or not mounting.get(
            "geometry_primary_support_load_span_unchanged"
        ):
            errors.append(f"{side}: primary-support load span changed")
        if (
            mounting.get("analytical_rail_relief") is not None
            or mounting.get("geometry_analytical_rail_relief") is not None
        ):
            errors.append(f"{side}: obsolete analytical rail relief remains")
        if (
            mounting.get("fastener_head_style")
            != VERIFIED_MOUNTING_FASTENER_HEAD_STYLE
            or mounting.get("geometry_fastener_head_style")
            != VERIFIED_MOUNTING_FASTENER_HEAD_STYLE
        ):
            errors.append(f"{side}: fastener head style is wrong")
        if (
            mounting.get("head_envelope_mm")
            != VERIFIED_MOUNTING_HEAD_ENVELOPE_MM
            or mounting.get("geometry_head_envelope_mm")
            != VERIFIED_MOUNTING_HEAD_ENVELOPE_MM
        ):
            errors.append(f"{side}: mounting head envelope contract is wrong")
        if (
            mounting.get("head_reserve_mm") != VERIFIED_MOUNTING_HEAD_RESERVE_MM
            or mounting.get("geometry_head_reserve_mm")
            != VERIFIED_MOUNTING_HEAD_RESERVE_MM
        ):
            errors.append(f"{side}: mounting head reserve contract is wrong")
        if (
            mounting.get("head_height_and_keycap_skirt_physical_status")
            != "pending"
            or mounting.get(
                "geometry_head_height_and_keycap_skirt_physical_status"
            )
            != "pending"
        ):
            errors.append(
                f"{side}: head height/keycap-skirt physical gate is not pending"
            )
        if (
            mounting.get("minimum_unrelated_support_reserve_mm")
            != VERIFIED_MOUNTING_UNRELATED_SUPPORT_RESERVE_MM
        ):
            errors.append(f"{side}: mounting support reserve contract is wrong")
        if (
            mounting.get("service_body_envelopes")
            != VERIFIED_MOUNTING_SERVICE_BODY_ENVELOPES
            or mounting.get("geometry_service_body_envelopes")
            != VERIFIED_MOUNTING_SERVICE_BODY_ENVELOPES
        ):
            errors.append(f"{side}: mounting BAT1/SW_PWR1 service envelopes are wrong")
        mounting_holes = mounting.get("holes", [])
        if len(mounting_holes) != len(VERIFIED_MOUNTING_COORDINATES_MM[side]):
            errors.append(f"{side}: mounting-hole manifest length is wrong")
        for index, expected_center in enumerate(VERIFIED_MOUNTING_COORDINATES_MM[side]):
            if index >= len(mounting_holes):
                break
            hole = mounting_holes[index]
            expected_ref = f"MH{index + 1}"
            if hole.get("ref") != expected_ref or hole.get("board_center_mm") != expected_center:
                errors.append(f"{side}:{expected_ref}: board coordinate is wrong")
            if hole.get("pcb_npth_diameter_mm") != VERIFIED_MOUNTING_NPTH_DIAMETER_MM:
                errors.append(f"{side}:{expected_ref}: PCB NPTH diameter is wrong")
            if not hole.get("board_feature_matches") or not hole.get(
                "geometry_board_feature_matches"
            ):
                errors.append(f"{side}:{expected_ref}: PCB MH feature does not match")
            if (
                hole.get("support_land_diameter_mm")
                != VERIFIED_MOUNTING_SUPPORT_LAND_DIAMETER_MM
                or hole.get("support_land_annular_width_mm") != 0.95
                or hole.get("support_land_top_z_mm") != VERIFIED_STRUCTURAL_PLATE_HEIGHT_MM
                or hole.get("support_land_vertical_gap_mm") != 0.0
                or hole.get("desk_column_diameter_mm")
                != VERIFIED_MOUNTING_SUPPORT_LAND_DIAMETER_MM
                or hole.get("desk_column_bottom_z_mm") != -VERIFIED_DESK_STANDOFF_MM
            ):
                errors.append(f"{side}:{expected_ref}: support land/desk column contract is wrong")
            if hole.get("pilot_diameter_mm") != VERIFIED_MOUNTING_PILOT_DIAMETER_MM:
                errors.append(f"{side}:{expected_ref}: pilot diameter is wrong")
            if (
                hole.get("pilot_depth_mm") != VERIFIED_MOUNTING_PILOT_DEPTH_MM
                or hole.get("pilot_top_z_mm") != VERIFIED_STRUCTURAL_PLATE_HEIGHT_MM
                or hole.get("pilot_bottom_z_mm") != VERIFIED_MOUNTING_PILOT_BOTTOM_Z_MM
                or hole.get("pilot_extension_below_plate_mm") != 0.30
                or hole.get("closed_bottom_to_desk_datum_mm")
                != VERIFIED_MOUNTING_CLOSED_BOTTOM_MM
            ):
                errors.append(f"{side}:{expected_ref}: pilot depth/Z/closed-bottom contract is wrong")
            if hole.get("pilot_breaks_desk_contact_bottom"):
                errors.append(f"{side}:{expected_ref}: pilot bottom break reaches the desk datum")
            if not (
                hole.get("step_pilot_open_at_z_2_49")
                and hole.get("step_pilot_open_at_z_minus_0_25")
                and hole.get("step_pilot_closed_at_z_minus_0_35")
                and hole.get("step_pilot_closed_at_z_minus_0_79")
                and hole.get("step_pilot_closed_at_z_minus_0_99")
            ):
                errors.append(
                    f"{side}:{expected_ref}: pilot STEP depth or closed bottom is wrong"
                )
            if (
                hole.get("provisional_screw_under_head_length_mm")
                != VERIFIED_PROVISIONAL_SCREW_UNDER_HEAD_LENGTH_MM
                or hole.get("pcb_tolerance_penetration_range_mm")
                != VERIFIED_PCB_TOLERANCE_PENETRATION_RANGE_MM
                or hole.get("minimum_tip_clearance_mm")
                != VERIFIED_MINIMUM_TIP_CLEARANCE_MM
            ):
                errors.append(f"{side}:{expected_ref}: provisional screw penetration contract is wrong")
            if hole.get("head_envelope_mm") != VERIFIED_MOUNTING_HEAD_ENVELOPE_MM:
                errors.append(f"{side}:{expected_ref}: head envelope is wrong")
            if hole.get("driver_envelope_diameter_mm") != VERIFIED_MOUNTING_DRIVER_DIAMETER_MM:
                errors.append(f"{side}:{expected_ref}: driver envelope is wrong")
            for field in (
                "support_land_to_existing_support_mm",
                "head_to_existing_support_mm",
                "geometry_support_land_to_existing_support_mm",
                "geometry_head_to_existing_support_mm",
            ):
                if (
                    float(hole.get(field, -99.0)) + 1e-6
                    < VERIFIED_MOUNTING_UNRELATED_SUPPORT_RESERVE_MM
                ):
                    errors.append(
                        f"{side}:{expected_ref}: support reserve {field} is below "
                        f"{VERIFIED_MOUNTING_UNRELATED_SUPPORT_RESERVE_MM:.2f} mm"
                    )
            for field in (
                "head_to_support_posts_mm",
                "head_to_analytical_rail_mm",
                "head_to_installed_component_mm",
                "head_to_routed_copper_or_via_mm",
                "head_to_board_edge_mm",
                "head_to_housing_edge_mm",
                "geometry_head_to_support_posts_mm",
                "geometry_head_to_analytical_rail_mm",
                "geometry_head_to_installed_component_mm",
                "geometry_head_to_routed_copper_or_via_mm",
                "geometry_head_to_board_edge_mm",
                "geometry_head_to_housing_edge_mm",
            ):
                if (
                    float(hole.get(field, -99.0)) + 1e-6
                    < VERIFIED_MOUNTING_HEAD_RESERVE_MM
                ):
                    errors.append(
                        f"{side}:{expected_ref}: head reserve {field} is below "
                        f"{VERIFIED_MOUNTING_HEAD_RESERVE_MM:.2f} mm"
                    )
            stronger_clearances = {
                "head_to_installed_component_mm": VERIFIED_MOUNTING_MINIMUM_COMPONENT_CLEARANCE_MM,
                "geometry_head_to_installed_component_mm": VERIFIED_MOUNTING_MINIMUM_COMPONENT_CLEARANCE_MM,
                "head_to_routed_copper_or_via_mm": VERIFIED_MOUNTING_MINIMUM_COPPER_CLEARANCE_MM,
                "geometry_head_to_routed_copper_or_via_mm": VERIFIED_MOUNTING_MINIMUM_COPPER_CLEARANCE_MM,
                "head_to_board_edge_mm": VERIFIED_MOUNTING_MINIMUM_BOARD_EDGE_CLEARANCE_MM,
                "geometry_head_to_board_edge_mm": VERIFIED_MOUNTING_MINIMUM_BOARD_EDGE_CLEARANCE_MM,
                "head_to_housing_edge_mm": VERIFIED_MOUNTING_MINIMUM_HOUSING_EDGE_CLEARANCE_MM,
                "geometry_head_to_housing_edge_mm": VERIFIED_MOUNTING_MINIMUM_HOUSING_EDGE_CLEARANCE_MM,
                "head_to_support_posts_mm": VERIFIED_MOUNTING_MINIMUM_KEY_SUPPORT_CLEARANCE_MM,
                "geometry_head_to_support_posts_mm": VERIFIED_MOUNTING_MINIMUM_KEY_SUPPORT_CLEARANCE_MM,
            }
            for field, minimum in stronger_clearances.items():
                if float(hole.get(field, -99.0)) + 1e-6 < minimum:
                    errors.append(
                        f"{side}:{expected_ref}: P3 clearance {field} is below {minimum:.2f} mm"
                    )
            if hole.get("head_reserve_mm") != VERIFIED_MOUNTING_HEAD_RESERVE_MM:
                errors.append(f"{side}:{expected_ref}: head reserve contract is wrong")
            if hole.get("minimum_unrelated_support_reserve_mm") != (
                VERIFIED_MOUNTING_UNRELATED_SUPPORT_RESERVE_MM
            ):
                errors.append(f"{side}:{expected_ref}: support reserve contract is wrong")
            for field in (
                "driver_to_battery_body_mm",
                "driver_to_power_switch_body_mm",
                "driver_to_power_switch_actuator_sweep_mm",
                "geometry_driver_to_battery_body_mm",
                "geometry_driver_to_power_switch_body_mm",
                "geometry_driver_to_power_switch_actuator_sweep_mm",
            ):
                if float(hole.get(field, -99.0)) < -1e-6:
                    errors.append(
                        f"{side}:{expected_ref}: full service body clearance {field} is negative"
                    )
            required_service_checks = {
                "driver_battery_body",
                "driver_power_switch_body",
                "driver_power_switch_actuator_sweep",
            }
            geometry_checks = hole.get("geometry_collision_checks", {})
            if not required_service_checks.issubset(geometry_checks):
                errors.append(f"{side}:{expected_ref}: full service body checks are missing")
            required_head_reserve_checks = {
                "head_support_post_reserve",
                "head_analytical_rail_reserve",
                "head_installed_component_reserve",
                "head_routed_copper_or_via_reserve",
                "head_board_edge_reserve",
                "head_housing_edge_reserve",
            }
            if not required_head_reserve_checks.issubset(geometry_checks):
                errors.append(f"{side}:{expected_ref}: head reserve checks are missing")
            if hole.get("service_condition") != "keycaps-off, switches-installed":
                errors.append(f"{side}:{expected_ref}: service condition is wrong")
            if int(hole.get("collision_count", 99)) != 0 or int(
                hole.get("geometry_collision_count", 99)
            ) != 0:
                errors.append(f"{side}:{expected_ref}: mounting collision remains")
            if hole.get("printable_part") != hole.get("geometry_printable_part"):
                errors.append(f"{side}:{expected_ref}: mounting part assignment is stale")
        required_cutouts = {
            "choc_socket_body_fillets",
            "switch_mechanical_pins",
            "mx_pins_pads_fillets",
            "diode_body_pads_fillets",
            "controller_socket",
            "battery_termination",
            "power_switch_leads",
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
            "controller_socket": 1,
            "battery_termination": 1,
            "power_switch_leads": 1,
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
        if diode.get("manufacturer") != generator.DIODE_MANUFACTURER:
            errors.append(f"{side}: wrong diode manufacturer")
        if (
            diode.get("mpn") != generator.DIODE_MPN
            or diode.get("eleparts_goods_no") != generator.DIODE_ELEPARTS_GOODS_NO
        ):
            errors.append(f"{side}: wrong 1N4148W ordering identity")
        if diode.get("official_body_depth_max_mm") != VERIFIED_DIODE_DEPTH_MAX_MM:
            errors.append(f"{side}: wrong official diode depth")
        if diode.get("official_plan_envelope_max_mm") != list(
            generator.DIODE_OFFICIAL_PLAN_ENVELOPE_MAX_MM
        ):
            errors.append(f"{side}: wrong official 1N4148W plan envelope")
        if (
            diode.get("official_terminal_span_max_mm")
            != generator.DIODE_OFFICIAL_TERMINAL_SPAN_MAX_MM
        ):
            errors.append(f"{side}: wrong official 1N4148W terminal span")
        if diode.get("solder_fillet_allowance_mm") != VERIFIED_DIODE_SOLDER_ALLOWANCE_MM:
            errors.append(f"{side}: wrong diode solder-fillet allowance")
        if float(diode.get("minimum_plate_bottom_clearance_mm", -99.0)) < -1e-6:
            errors.append(f"{side}: diode plate-bottom clearance is negative")
        if float(diode.get("minimum_desk_clearance_mm", -99.0)) + 1e-6 < 0.50:
            errors.append(f"{side}: diode desk clearance is below 0.50 mm")
        if not math.isclose(
            float(diode.get("minimum_plate_bottom_clearance_mm", -99.0)),
            VERIFIED_DIODE_PLATE_BOTTOM_CLEARANCE_MM,
            abs_tol=1e-9,
        ):
            errors.append(f"{side}: diode plate-bottom clearance formula is stale")
        if not math.isclose(
            float(diode.get("nominal_desk_clearance_mm", -99.0)),
            VERIFIED_DIODE_NOMINAL_DESK_CLEARANCE_MM,
            abs_tol=1e-9,
        ):
            errors.append(f"{side}: diode nominal desk-clearance formula is stale")
        if not math.isclose(
            float(diode.get("minimum_desk_clearance_mm", -99.0)),
            VERIFIED_DIODE_WORST_DESK_CLEARANCE_MM,
            abs_tol=1e-9,
        ):
            errors.append(f"{side}: diode worst-case desk-clearance formula is stale")
        if diode.get("breaks_lateral_housing_perimeter"):
            errors.append(f"{side}: diode cutout breaks the lateral perimeter")
        if (
            float(diode.get("minimum_housing_perimeter_land_mm", -99.0)) + 1e-6
            < generator.MIN_DIODE_HOUSING_PERIMETER_LAND_MM
        ):
            errors.append(f"{side}: diode perimeter land is below 0.85 mm")
        if not diode.get("perimeter_land_matches_manifest"):
            errors.append(f"{side}: diode perimeter land manifest is stale")
        termination = cutouts.get("battery_termination", {})
        if termination.get("reference") != generator.BATTERY_TERMINATION_REFERENCE:
            errors.append(f"{side}: battery termination is not bound to exact J_BAT1")
        if termination.get("pad_count") != 2:
            errors.append(f"{side}: J_BAT1 does not contain exactly two pads")
        if termination.get("plated_pth_count") != 2:
            errors.append(f"{side}: J_BAT1 pads are not both plated PTH")
        if termination.get("required_pad_envelope_count") != 2:
            errors.append(f"{side}: J_BAT1 does not require both lead/solder envelopes")
        if termination.get("cutout_envelopes_overlap") is not True:
            errors.append(f"{side}: J_BAT1 2.54 mm cutout envelopes do not overlap")
        if termination.get("expected_union_opening_count") != 1:
            errors.append(f"{side}: J_BAT1 union opening contract is not one")
        if termination.get("pad_envelope_count") != 2:
            errors.append(f"{side}: J_BAT1 pad-envelope count is not two")
        if (
            termination.get("covered_pad_envelope_count") != 2
            or termination.get("uncovered_pad_envelope_count") != 0
        ):
            errors.append(f"{side}: J_BAT1 lead/solder envelopes are not all covered")
        power = cutouts.get("power_switch_leads", {})
        if power.get("reference") != generator.POWER_SWITCH_REFERENCE:
            errors.append(f"{side}: power-switch opening is not bound to exact SW_PWR1")
        if power.get("pad_count") != generator.POWER_SWITCH_DRILL_COUNT:
            errors.append(f"{side}: power-switch does not contain exactly three pads")
        if power.get("all_round_plated_pth") is not True:
            errors.append(f"{side}: power-switch pads are not round plated PTH")
        if power.get("drill_count") != generator.POWER_SWITCH_DRILL_COUNT:
            errors.append(f"{side}: power-switch opening does not cover three drills")
        if power.get("drill_diameter_mm") != generator.POWER_SWITCH_DRILL_DIAMETER_MM:
            errors.append(f"{side}: power-switch drill diameter is not 0.80 mm")
        if power.get("pitch_mm") != generator.POWER_SWITCH_PITCH_MM:
            errors.append(f"{side}: power-switch pad pitch is not 2.54 mm")
        for service_name in (
            "battery_termination",
            "power_switch_leads",
            "battery_slot",
        ):
            errors.extend(
                service_cutout_contract_errors(
                    side, service_name, cutouts.get(service_name, {})
                )
            )
        if not data["step_sha256_matches"] or not data["stl_sha256_matches"]:
            errors.append(f"{side}: stale or missing STEP/STL")
        if data.get("step_has_trailing_whitespace"):
            errors.append(f"{side}: STEP has trailing whitespace")
        if not data.get("step_whitespace_contract_matches_manifest"):
            errors.append(f"{side}: STEP whitespace contract is stale or missing")
        expected_step_solids = 1 if side == "left" else 2
        if data["step_solid_count"] != expected_step_solids:
            errors.append(f"{side}: STEP solid count {data['step_solid_count']}")
        if data["step_bounds_z_mm"] != [generator.DESK_DATUM_Z_MM, generator.PCB_BOTTOM_Z_MM]:
            errors.append(f"{side}: STEP Z bounds {data['step_bounds_z_mm']}")
        if not data.get("step_volume_matches_plan"):
            errors.append(
                f"{side}: STEP volume differs by {data.get('step_volume_error_mm3')} mm3"
            )
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
            if int(part.get("desk_contact_count", 0)) < 3:
                errors.append(f"{side}:{part['name']}: fewer than 3 desk contacts")
            if int(part.get("desk_contact_count", 0)) != int(
                part.get("expected_desk_contact_count", -1)
            ):
                errors.append(f"{side}:{part['name']}: planned desk-contact count is stale")
            if int(part.get("actual_desk_contact_count", 0)) != int(
                part.get("expected_desk_contact_count", -1)
            ):
                errors.append(f"{side}:{part['name']}: STL desk-contact count is stale")
            if part.get("manifest_desk_contact_ids") != part.get("expected_desk_contact_ids"):
                errors.append(f"{side}:{part['name']}: desk-contact IDs differ from plan")
            if len(part.get("actual_desk_contact_centers_mm", [])) != int(
                part.get("expected_desk_contact_count", -1)
            ):
                errors.append(f"{side}:{part['name']}: actual desk-contact center count is stale")
            if part.get("desk_contact_z_mm") != generator.DESK_DATUM_Z_MM:
                errors.append(f"{side}:{part['name']}: desk-contact Z is wrong")
            if float(part.get("desk_contact_coplanarity_mm", 99.0)) > 1e-6:
                errors.append(f"{side}:{part['name']}: desk contacts are not coplanar")
            if not part.get("desk_contacts_match_plan"):
                errors.append(f"{side}:{part['name']}: STL desk contacts differ from plan")
            if not part.get("projected_centroid_inside_contact_hull"):
                errors.append(f"{side}:{part['name']}: projected centroid leaves desk-contact hull")
            if not part.get("desk_contacts_statically_stable"):
                errors.append(f"{side}:{part['name']}: desk contacts are not statically stable")
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
