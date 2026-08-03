from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import generate_kc2_housings as housing_generator  # noqa: E402


HOUSING_MANIFEST = ROOT / "hardware" / "case" / "kc2_housing_manifest.json"
PROMOTED_BOARDS = {
    "left": ROOT / "hardware" / "kicad" / "kc2_left" / "kc2_left.kicad_pcb",
    "right": ROOT / "hardware" / "kicad" / "kc2_right" / "kc2_right.kicad_pcb",
}
V2_BOARDS = {
    "left": ROOT / "hardware" / "kicad" / "draft" / "x3-v2" / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb",
    "right": ROOT / "hardware" / "kicad" / "draft" / "x3-v2" / "kc2_right-x3-v2" / "kc2_right-x3-v2.kicad_pcb",
}
MX_SOLDER_FILLET_ALLOWANCE_MM = 0.30
CHOC_SOLDER_FILLET_ALLOWANCE_MM = 0.30
MAXIMUM_TRIMMED_MX_PROJECTION_MM = 2.20


def extract_board(pcbnew: Any, path: Path) -> dict[str, object]:
    board = pcbnew.LoadBoard(str(path))
    edge_segments = [
        [
            pcbnew.ToMM(item.GetStart().x),
            pcbnew.ToMM(item.GetStart().y),
            pcbnew.ToMM(item.GetEnd().x),
            pcbnew.ToMM(item.GetEnd().y),
        ]
        for item in board.GetDrawings()
        if item.GetLayer() == pcbnew.Edge_Cuts
        and hasattr(item, "GetStart")
        and hasattr(item, "GetEnd")
    ]
    switches: dict[str, object] = {}
    diodes: dict[str, object] = {}
    registrations: dict[str, list[float]] = {}
    for footprint in board.GetFootprints():
        reference = footprint.GetReference()
        position = footprint.GetPosition()
        center = [round(pcbnew.ToMM(position.x), 4), round(pcbnew.ToMM(position.y), 4)]
        if reference.startswith("REG") and reference[3:].isdigit():
            registrations[reference] = center
            continue
        if reference.startswith("D") and reference[1:].isdigit():
            body_boxes = [
                item.GetBoundingBox()
                for item in footprint.GraphicalItems()
                if item.GetLayer() == pcbnew.B_Fab
            ]
            pad_boxes = [
                pad.GetBoundingBox()
                for pad in footprint.Pads()
                if pad.IsOnLayer(pcbnew.B_Cu)
            ]
            if not body_boxes or not pad_boxes:
                raise RuntimeError(f"{path}: {reference} has incomplete bottom diode geometry")
            diodes[reference] = {
                "body_envelope": [
                    min(pcbnew.ToMM(box.GetX()) for box in body_boxes),
                    min(pcbnew.ToMM(box.GetY()) for box in body_boxes),
                    max(pcbnew.ToMM(box.GetX() + box.GetWidth()) for box in body_boxes),
                    max(pcbnew.ToMM(box.GetY() + box.GetHeight()) for box in body_boxes),
                ],
                "pad_envelopes": [
                    [
                        pcbnew.ToMM(box.GetX()),
                        pcbnew.ToMM(box.GetY()),
                        pcbnew.ToMM(box.GetX() + box.GetWidth()),
                        pcbnew.ToMM(box.GetY() + box.GetHeight()),
                    ]
                    for box in pad_boxes
                ],
            }
            continue
        if not (reference.startswith("SW") and reference[2:].isdigit()):
            continue
        body_boxes = [
            item.GetBoundingBox()
            for item in footprint.GraphicalItems()
            if item.GetLayer() in (pcbnew.B_SilkS, pcbnew.B_Fab)
        ]
        socket_pad_boxes = [
            pad.GetBoundingBox()
            for pad in footprint.Pads()
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD and pad.IsOnLayer(pcbnew.B_Cu)
        ]
        boxes = body_boxes + socket_pad_boxes
        if not boxes:
            raise RuntimeError(f"{path}: {reference} has no bottom socket envelope")
        envelope = [
            min(pcbnew.ToMM(box.GetX()) for box in boxes),
            min(pcbnew.ToMM(box.GetY()) for box in boxes),
            max(pcbnew.ToMM(box.GetX() + box.GetWidth()) for box in boxes),
            max(pcbnew.ToMM(box.GetY() + box.GetHeight()) for box in boxes),
        ]
        mx_pads = []
        for pad in footprint.Pads():
            if not pad.GetNumber() or pad.GetAttribute() != pcbnew.PAD_ATTRIB_PTH:
                continue
            pad_position = pad.GetPosition()
            pad_size = pad.GetSize()
            mx_pads.append(
                {
                    "x": pcbnew.ToMM(pad_position.x),
                    "y": pcbnew.ToMM(pad_position.y),
                    "radius_mm": max(pcbnew.ToMM(pad_size.x), pcbnew.ToMM(pad_size.y)) / 2.0,
                }
            )
        switches[reference] = {
            "center": center,
            "socket_envelope": [round(value, 4) for value in envelope],
            "socket_pad_envelopes": [
                [
                    pcbnew.ToMM(box.GetX()),
                    pcbnew.ToMM(box.GetY()),
                    pcbnew.ToMM(box.GetX() + box.GetWidth()),
                    pcbnew.ToMM(box.GetY() + box.GetHeight()),
                ]
                for box in socket_pad_boxes
            ],
            "mx_pads": mx_pads,
        }
    return {
        "path": str(path.relative_to(ROOT)),
        "edge_segments": edge_segments,
        "switches": switches,
        "diodes": diodes,
        "registrations": registrations,
    }


def extract_geometry() -> None:
    import pcbnew  # type: ignore[import-not-found]

    result: dict[str, object] = {"boards": {}}
    for side in ("left", "right"):
        result["boards"][side] = {
            "baseline": extract_board(pcbnew, PROMOTED_BOARDS[side]),
            "v2": extract_board(pcbnew, V2_BOARDS[side]),
        }
    print(json.dumps(result))


def run_extractor() -> dict[str, Any]:
    proc = subprocess.run(
        [
            str(housing_generator.locate_kicad_python()),
            str(Path(__file__).resolve()),
            "--extract-geometry",
        ],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    start = proc.stdout.find("{")
    end = proc.stdout.rfind("}")
    if start < 0 or end < start:
        raise RuntimeError(f"KiCad V2 housing extractor returned no JSON:\n{proc.stdout}\n{proc.stderr}")
    return json.loads(proc.stdout[start : end + 1])


def reflected_box(
    shp: dict[str, Any],
    bounds: tuple[float, float, float, float],
    envelope: list[float],
) -> Any:
    min_x, min_y, max_x, max_y = bounds
    geometry = shp["box"](*envelope)
    geometry = shp["affinity"].translate(geometry, xoff=-min_x, yoff=-min_y)
    return shp["affinity"].scale(
        geometry,
        xfact=-1.0,
        yfact=1.0,
        origin=((max_x - min_x) / 2.0, (max_y - min_y) / 2.0),
    )


def reflected_circle(
    shp: dict[str, Any],
    bounds: tuple[float, float, float, float],
    x: float,
    y: float,
    radius: float,
) -> Any:
    min_x, min_y, max_x, _max_y = bounds
    return shp["Point"]((max_x - min_x) - (x - min_x), y - min_y).buffer(
        radius, resolution=16
    )


def housing_wall(
    shp: dict[str, Any],
    baseline: dict[str, Any],
    params: housing_generator.HousingParams,
) -> tuple[Any, tuple[float, float, float, float], list[Any]]:
    raw = housing_generator.board_polygon(shp, baseline["edge_segments"])
    bounds = tuple(float(value) for value in raw.bounds)
    min_x, min_y, max_x, max_y = bounds
    translated = shp["affinity"].translate(raw, xoff=-min_x, yoff=-min_y)
    physical_board = shp["affinity"].scale(
        translated,
        xfact=-1.0,
        yfact=1.0,
        origin=((max_x - min_x) / 2.0, (max_y - min_y) / 2.0),
    )
    outer = physical_board.buffer(-params.outline_inset_mm, join_style="round", resolution=16)
    if params.bottom_corner_radius_mm > 0:
        outer = outer.buffer(
            -params.bottom_corner_radius_mm / 2.0,
            join_style="round",
            resolution=16,
        ).buffer(
            params.bottom_corner_radius_mm / 2.0,
            join_style="round",
            resolution=16,
        )
    cavity = outer.buffer(-params.outer_wall_width_mm, join_style="round", resolution=16)
    sockets = [
        reflected_box(shp, bounds, switch["socket_envelope"])
        for switch in baseline["switches"].values()
    ]
    cavity = cavity.union(
        shp["unary_union"](
            [
                geometry.buffer(
                    params.socket_lateral_clearance_mm,
                    join_style="round",
                    resolution=12,
                )
                for geometry in sockets
            ]
        )
    )
    return outer.difference(cavity), bounds, sockets


def point_mismatches(
    baseline: dict[str, list[float]], candidate: dict[str, list[float]]
) -> list[str]:
    refs = sorted(set(baseline) | set(candidate))
    return [
        ref
        for ref in refs
        if ref not in baseline or ref not in candidate or baseline[ref] != candidate[ref]
    ]


def analyze_v2_housing_reuse() -> dict[str, object]:
    manifest = json.loads(HOUSING_MANIFEST.read_text(encoding="utf-8"))
    raw_params = manifest["parameters"]
    param_fields = set(housing_generator.HousingParams.__dataclass_fields__)
    params = housing_generator.HousingParams(
        **{key: value for key, value in raw_params.items() if key in param_fields}
    )
    geometry = run_extractor()
    shp = housing_generator.require_shapely()

    switch_center_mismatches: list[str] = []
    registration_center_mismatches: list[str] = []
    socket_envelope_mismatches: list[str] = []
    socket_wall_distances: list[float] = []
    mx_wall_distances: list[float] = []
    mx_post_distances: list[float] = []
    socket_diode_distances: list[float] = []
    choc_fillet_wall_distances: list[float] = []
    choc_fillet_diode_distances: list[float] = []
    mx_diode_body_distances: list[float] = []
    mx_diode_pad_distances: list[float] = []
    socket_wall_collisions = 0
    mx_wall_collisions = 0
    mx_post_collisions = 0
    socket_diode_collisions = 0
    choc_fillet_wall_collisions = 0
    choc_fillet_diode_collisions = 0
    mx_diode_body_collisions = 0
    mx_diode_pad_collisions = 0

    for side in ("left", "right"):
        baseline = geometry["boards"][side]["baseline"]
        v2 = geometry["boards"][side]["v2"]
        baseline_switches = baseline["switches"]
        v2_switches = v2["switches"]
        baseline_centers = {
            ref: switch["center"] for ref, switch in baseline_switches.items()
        }
        v2_centers = {ref: switch["center"] for ref, switch in v2_switches.items()}
        switch_center_mismatches.extend(
            f"{side}:{ref}"
            for ref in point_mismatches(baseline_centers, v2_centers)
        )
        registration_center_mismatches.extend(
            f"{side}:{ref}"
            for ref in point_mismatches(
                baseline["registrations"], v2["registrations"]
            )
        )
        for ref in sorted(set(baseline_switches) & set(v2_switches)):
            if (
                baseline_switches[ref]["socket_envelope"]
                != v2_switches[ref]["socket_envelope"]
            ):
                socket_envelope_mismatches.append(f"{side}:{ref}")

        wall, bounds, socket_geometries = housing_wall(shp, baseline, params)
        for socket in socket_geometries:
            socket_wall_collisions += socket.intersection(wall).area > 1e-6
            socket_wall_distances.append(socket.distance(wall))
        posts = [
            reflected_circle(
                shp,
                bounds,
                center[0],
                center[1],
                params.support_post_diameter_mm / 2.0,
            )
            for center in baseline["registrations"].values()
        ]
        for reference, switch in v2_switches.items():
            diode = v2["diodes"][f"D{reference[2:]}"]
            socket = reflected_box(shp, bounds, switch["socket_envelope"])
            diode_body = reflected_box(shp, bounds, diode["body_envelope"])
            diode_pads = shp["unary_union"](
                [
                    reflected_box(shp, bounds, envelope)
                    for envelope in diode["pad_envelopes"]
                ]
            )
            diode_bottom = diode_body.union(diode_pads)
            socket_diode_collisions += socket.intersection(diode_bottom).area > 1e-6
            socket_diode_distances.append(socket.distance(diode_bottom))
            choc_fillets = shp["unary_union"](
                [
                    reflected_box(shp, bounds, envelope).buffer(
                        CHOC_SOLDER_FILLET_ALLOWANCE_MM,
                        join_style="round",
                        resolution=12,
                    )
                    for envelope in switch["socket_pad_envelopes"]
                ]
            )
            choc_fillet_wall_collisions += choc_fillets.intersection(wall).area > 1e-6
            choc_fillet_wall_distances.append(choc_fillets.distance(wall))
            choc_fillet_diode_collisions += (
                choc_fillets.intersection(diode_bottom).area > 1e-6
            )
            choc_fillet_diode_distances.append(choc_fillets.distance(diode_bottom))
            for pad in switch["mx_pads"]:
                solder = reflected_circle(
                    shp,
                    bounds,
                    float(pad["x"]),
                    float(pad["y"]),
                    float(pad["radius_mm"]) + MX_SOLDER_FILLET_ALLOWANCE_MM,
                )
                mx_wall_collisions += solder.intersection(wall).area > 1e-6
                mx_wall_distances.append(solder.distance(wall))
                for post in posts:
                    mx_post_collisions += solder.intersection(post).area > 1e-6
                    mx_post_distances.append(solder.distance(post))
                mx_diode_body_collisions += solder.intersection(diode_body).area > 1e-6
                mx_diode_body_distances.append(solder.distance(diode_body))
                mx_diode_pad_collisions += solder.intersection(diode_pads).area > 1e-6
                mx_diode_pad_distances.append(solder.distance(diode_pads))

    left = manifest["outputs"]["left"]
    right = manifest["outputs"]["right"]
    left_xy = left["output_bounds_xy_mm"]
    printable_dimensions = [
        left_xy[2] - left_xy[0],
        left_xy[3] - left_xy[1],
        left["height_profile"]["front_height_mm"]
        + params.pcb_thickness_mm
        - params.peg_top_below_pcb_top_mm,
    ]
    printable_dimensions.extend(
        dimension
        for part in right["stl_parts"]
        for dimension in part["size_mm"]
    )
    split = right["split"]
    bottom_clearance = float(raw_params["bottom_component_clearance_mm"])
    return {
        "requirement": "CON-ARCH-004",
        "housing_source_requirement": manifest["requirement"],
        "switch_center_mismatches": switch_center_mismatches,
        "registration_center_mismatches": registration_center_mismatches,
        "socket_envelope_mismatches": socket_envelope_mismatches,
        "socket_wall_collision_count": socket_wall_collisions,
        "minimum_socket_wall_clearance_mm": round(min(socket_wall_distances), 3),
        "mx_solder_wall_collision_count": mx_wall_collisions,
        "minimum_mx_solder_wall_clearance_mm": round(min(mx_wall_distances), 3),
        "mx_solder_post_collision_count": mx_post_collisions,
        "minimum_mx_solder_post_clearance_mm": round(min(mx_post_distances), 3),
        "socket_diode_collision_count": socket_diode_collisions,
        "minimum_socket_diode_clearance_mm": round(min(socket_diode_distances), 3),
        "choc_solder_fillet_wall_collision_count": choc_fillet_wall_collisions,
        "minimum_choc_solder_fillet_wall_clearance_mm": round(
            min(choc_fillet_wall_distances), 3
        ),
        "choc_solder_fillet_diode_collision_count": choc_fillet_diode_collisions,
        "minimum_choc_solder_fillet_diode_clearance_mm": round(
            min(choc_fillet_diode_distances), 3
        ),
        "choc_solder_fillet_lateral_allowance_mm": CHOC_SOLDER_FILLET_ALLOWANCE_MM,
        "mx_solder_diode_body_collision_count": mx_diode_body_collisions,
        "minimum_mx_solder_diode_body_clearance_mm": round(
            min(mx_diode_body_distances), 3
        ),
        "mx_solder_diode_pad_collision_count": mx_diode_pad_collisions,
        "minimum_mx_solder_diode_pad_clearance_mm": round(
            min(mx_diode_pad_distances), 3
        ),
        "mx_solder_fillets_lateral_allowance_mm": MX_SOLDER_FILLET_ALLOWANCE_MM,
        "bottom_component_clearance_mm": bottom_clearance,
        "maximum_trimmed_mx_projection_mm": MAXIMUM_TRIMMED_MX_PROJECTION_MM,
        "minimum_vertical_clearance_mm": round(
            bottom_clearance - MAXIMUM_TRIMMED_MX_PROJECTION_MM, 3
        ),
        "floor_thickness_mm": float(raw_params["floor_thickness_mm"]),
        "rear_rise_mm": float(raw_params["rear_rise_mm"]),
        "largest_printable_part_dimension_mm": round(max(printable_dimensions), 3),
        "right_split_part_count": int(split["part_count"]),
        "right_split_bond_length_ratio": round(
            float(split["minimum_floor_bond_length_ratio"]), 3
        ),
        "right_split_assembled_gap_mm": float(split["assembled_gap_mm"]),
        "assembly_constraint": (
            "Trim both MX electrical terminals to no more than 2.20 mm below the PCB "
            "after soldering; do not install a Choc socket and MX switch at the same key."
        ),
    }


def verify_report(report: dict[str, object]) -> list[str]:
    errors: list[str] = []
    for key in (
        "switch_center_mismatches",
        "registration_center_mismatches",
        "socket_envelope_mismatches",
    ):
        if report[key]:
            errors.append(f"{key}: {report[key]}")
    for key in (
        "socket_wall_collision_count",
        "mx_solder_wall_collision_count",
        "mx_solder_post_collision_count",
        "socket_diode_collision_count",
        "choc_solder_fillet_wall_collision_count",
        "choc_solder_fillet_diode_collision_count",
        "mx_solder_diode_body_collision_count",
        "mx_solder_diode_pad_collision_count",
    ):
        if report[key] != 0:
            errors.append(f"{key}: {report[key]}")
    for key in (
        "minimum_socket_wall_clearance_mm",
        "minimum_mx_solder_wall_clearance_mm",
        "minimum_mx_solder_post_clearance_mm",
        "minimum_socket_diode_clearance_mm",
        "minimum_choc_solder_fillet_diode_clearance_mm",
        "minimum_mx_solder_diode_body_clearance_mm",
        "minimum_vertical_clearance_mm",
    ):
        if float(report[key]) < 0.30:
            errors.append(f"{key}: {report[key]} mm")
    if float(report["minimum_mx_solder_diode_pad_clearance_mm"]) < 0.15:
        errors.append(
            "minimum_mx_solder_diode_pad_clearance_mm: "
            f"{report['minimum_mx_solder_diode_pad_clearance_mm']} mm"
        )
    if float(report["largest_printable_part_dimension_mm"]) > 150.0:
        errors.append(
            f"largest printable dimension: {report['largest_printable_part_dimension_mm']} mm"
        )
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify CON-ARCH-004 reuse of the KC2 X3 split lower housing."
    )
    parser.add_argument("--extract-geometry", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.extract_geometry:
        extract_geometry()
        return
    report = analyze_v2_housing_reuse()
    errors = verify_report(report)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if errors:
        raise SystemExit("FAIL: KC2 X3 V2 housing clearance\n- " + "\n- ".join(errors))
    print(json.dumps(report, indent=2))
    print(
        "PASS: CON-ARCH-004 reuses the flat split X3 housing with verified V2 clearances"
    )


if __name__ == "__main__":
    main()
