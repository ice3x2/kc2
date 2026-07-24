"""Verify Fusion-compatible STEP exports for the KC2 X3 lower housings."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEP_OUTPUTS = {
    "left": ROOT / "hardware" / "case" / "kc2_left_lower_housing.step",
    "right": ROOT / "hardware" / "case" / "kc2_right_lower_housing.step",
}
STEP_MANIFEST = ROOT / "hardware" / "case" / "kc2_housing_step_manifest.json"
SOURCE_MANIFEST = ROOT / "hardware" / "case" / "kc2_housing_manifest.json"
EXPECTED_XY_SIZE_MM = {
    "left": (145.5125, 132.05),
    "right": (193.1375, 132.05),
}
MIN_SOLID_VOLUME_MM3 = 1000.0
SIZE_TOLERANCE_MM = 0.05
MAX_REAR_RISE_MM = 0.001
MAX_PLANAR_FACE_SLOPE = 0.00001
EXPECTED_PCB_SUPPORT_HEIGHT_MM = 3.80
EXPECTED_FLOOR_THICKNESS_MM = 1.20
EXPECTED_BOTTOM_COMPONENT_CLEARANCE_MM = 2.60
EXPECTED_PILOT_HOLE_DIAMETER_MM = 1.60
EXPECTED_REGISTRATION_PEG_DIAMETER_MM = 2.55
CYLINDER_RADIUS_TOLERANCE_MM = 0.001
CENTER_TOLERANCE_MM = 0.002


def verify_step_outputs() -> list[str]:
    errors: list[str] = []
    if not STEP_MANIFEST.exists():
        errors.append(f"missing STEP manifest {STEP_MANIFEST.relative_to(ROOT)}")
    if not SOURCE_MANIFEST.exists():
        errors.append(f"missing source manifest {SOURCE_MANIFEST.relative_to(ROOT)}")
    for side, path in STEP_OUTPUTS.items():
        if not path.exists():
            errors.append(f"{side}: missing STEP output {path.relative_to(ROOT)}")
            continue
        header = path.read_text(encoding="ascii", errors="strict")[:256]
        if "ISO-10303-21" not in header:
            errors.append(f"{side}: output is not an ISO-10303 STEP file")

    if errors:
        return errors

    step_manifest = json.loads(STEP_MANIFEST.read_text(encoding="utf-8"))
    source_manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    params = step_manifest.get("parameters", {})
    if abs(
        float(params.get("screw_pilot_hole_diameter_mm", 0.0))
        - EXPECTED_PILOT_HOLE_DIAMETER_MM
    ) > 1e-6:
        errors.append("STEP manifest does not declare the 1.60 mm pilot-hole diameter")
    if abs(
        float(params.get("registration_peg_diameter_mm", 0.0))
        - EXPECTED_REGISTRATION_PEG_DIAMETER_MM
    ) > 1e-6:
        errors.append("STEP manifest does not declare the 2.55 mm registration-peg diameter")
    if abs(float(params.get("rear_rise_mm", 999.0))) > MAX_REAR_RISE_MM:
        errors.append("STEP manifest does not declare a flat zero-rise housing")
    if abs(float(params.get("rear_height_ratio", 0.0)) - 1.0) > 1e-6:
        errors.append("STEP manifest does not declare a 1.00 rear/front height ratio")
    if (
        abs(
            float(params.get("floor_thickness_mm", 0.0))
            - EXPECTED_FLOOR_THICKNESS_MM
        )
        > 1e-6
    ):
        errors.append("STEP manifest does not declare a 1.20 mm floor")
    if (
        abs(
            float(params.get("bottom_component_clearance_mm", 0.0))
            - EXPECTED_BOTTOM_COMPONENT_CLEARANCE_MM
        )
        > 1e-6
    ):
        errors.append("STEP manifest does not declare 2.60 mm bottom-component clearance")
    for side in STEP_OUTPUTS:
        output = step_manifest.get("outputs", {}).get(side, {})
        source = source_manifest.get("outputs", {}).get(side, {})
        if output.get("orientation") != "x_reflected_for_physical_assembly":
            errors.append(f"{side}: STEP manifest does not declare corrected X orientation")
        source_bounds = source.get("output_bounds_xy_mm", [])
        source_holes = source.get("registration_holes", [])
        step_holes = output.get("registration_holes", [])
        if len(source_bounds) != 4 or len(source_holes) != len(step_holes):
            errors.append(f"{side}: registration metadata is incomplete")
            continue
        x_sum = float(source_bounds[0]) + float(source_bounds[2])
        for source_hole, step_hole in zip(source_holes, step_holes):
            if source.get("orientation") == "x_reflected_for_physical_assembly":
                expected_x = float(source_hole["x"])
            else:
                expected_x = x_sum - float(source_hole["x"])
            if abs(float(step_hole["x"]) - expected_x) > 1e-6 or abs(
                float(step_hole["y"]) - float(source_hole["y"])
            ) > 1e-6:
                errors.append(f"{side}: {source_hole['ref']} registration hole is not X-reflected")

    try:
        import cadquery as cq
    except ImportError as exc:
        errors.append(f"CadQuery is required to inspect STEP solids: {exc}")
        return errors

    for side, path in STEP_OUTPUTS.items():
        try:
            model = cq.importers.importStep(str(path))
            solids = model.solids().vals()
        except Exception as exc:  # pragma: no cover - backend error text is useful
            errors.append(f"{side}: STEP import failed: {exc}")
            continue

        if len(solids) != 1:
            errors.append(f"{side}: expected one solid, found {len(solids)}")
            continue
        solid = solids[0]
        if not solid.isValid():
            errors.append(f"{side}: imported solid is invalid")
        if solid.Volume() < MIN_SOLID_VOLUME_MM3:
            errors.append(f"{side}: solid volume {solid.Volume():.3f} mm^3 is too small")

        bbox = solid.BoundingBox()
        actual = (bbox.xlen, bbox.ylen)
        expected = EXPECTED_XY_SIZE_MM[side]
        for axis, measured, target in zip(("X", "Y"), actual, expected):
            if abs(measured - target) > SIZE_TOLERANCE_MM:
                errors.append(
                    f"{side}: {axis} size {measured:.4f} mm differs from "
                    f"expected {target:.4f} mm"
                )

        sloped_faces = []
        for face in solid.Faces():
            if face.geomType() != "PLANE":
                continue
            normal = face.normalAt()
            if abs(normal.z) < 0.9:
                continue
            slope = abs(normal.y / normal.z)
            if slope > MAX_PLANAR_FACE_SLOPE:
                sloped_faces.append(face)
        if sloped_faces:
            errors.append(
                f"{side}: found {len(sloped_faces)} sloped floor/top planar faces"
            )

        if abs(bbox.zmax - (EXPECTED_PCB_SUPPORT_HEIGHT_MM + 1.30)) > SIZE_TOLERANCE_MM:
            errors.append(
                f"{side}: total peg-top height {bbox.zmax:.3f} mm does not match "
                "the 3.80 mm flat PCB support height"
            )

        output = step_manifest["outputs"][side]
        expected_centers = [
            (float(hole["x"]), float(hole["y"]))
            for hole in output["registration_holes"]
        ]
        pilot_radius = EXPECTED_PILOT_HOLE_DIAMETER_MM / 2.0
        peg_radius = EXPECTED_REGISTRATION_PEG_DIAMETER_MM / 2.0
        pilot_centers = []
        peg_centers = []
        for face in solid.Faces():
            if face.geomType() != "CYLINDER":
                continue
            cylinder = face._geomAdaptor().Cylinder()
            radius = float(cylinder.Radius())
            location = cylinder.Location()
            center = (float(location.X()), float(location.Y()))
            if abs(radius - pilot_radius) <= CYLINDER_RADIUS_TOLERANCE_MM:
                pilot_centers.append(center)
                if face.BoundingBox().zmin <= 1.0:
                    errors.append(f"{side}: pilot bore at {center} penetrates the exterior floor")
            if abs(radius - peg_radius) <= CYLINDER_RADIUS_TOLERANCE_MM:
                peg_centers.append(center)

        def centers_match(actual: list[tuple[float, float]]) -> bool:
            return len(actual) == len(expected_centers) and all(
                any(
                    abs(actual_x - expected_x) <= CENTER_TOLERANCE_MM
                    and abs(actual_y - expected_y) <= CENTER_TOLERANCE_MM
                    for actual_x, actual_y in actual
                )
                for expected_x, expected_y in expected_centers
            )

        if not centers_match(pilot_centers):
            errors.append(
                f"{side}: pilot-bore centers differ from registration centers "
                f"(expected {len(expected_centers)}, found {len(pilot_centers)})"
            )
        if not centers_match(peg_centers):
            errors.append(
                f"{side}: 2.55 mm peg centers differ from registration centers "
                f"(expected {len(expected_centers)}, found {len(peg_centers)})"
            )
    return errors


def main() -> int:
    errors = verify_step_outputs()
    if errors:
        print("FAIL: KC2 Fusion STEP verification")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: KC2 Fusion STEP verification")
    print("- left/right STEP files import as valid single solids")
    print("- exported XY sizes match the corrected lower-housing outlines")
    print("- floor and PCB support faces are flat with a uniform 3.80 mm support height")
    print("- each solid has nine centered 1.60 mm blind bores and nine 2.55 mm pegs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
