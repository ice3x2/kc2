from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "hardware" / "case" / "kc2_housing_manifest.json"
VERTEX_RE = re.compile(r"\s*vertex\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s+([-+0-9.eE]+)\s*$")

MIN_REAR_RISE_MM = 3.0
MIN_BOTTOM_CORNER_RADIUS_MM = 0.5
MIN_BOTTOM_EDGE_RADIUS_MM = 0.5
MIN_OBSERVED_REAR_RISE_MM = 2.0
MIN_OBSERVED_BOTTOM_EDGE_INSET_MM = 0.25
TARGET_REAR_HEIGHT_RATIO = 1.70
HEIGHT_RATIO_TOLERANCE = 0.03
MIN_CAVITY_OPEN_AREA_RATIO = 0.45
MAX_EXTERNAL_STEP_MM = 0.05
EDGE_SAMPLE_FRACTION = 0.10


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def stl_vertices(path: Path) -> list[tuple[float, float, float]]:
    vertices: list[tuple[float, float, float]] = []
    for line in path.read_text(encoding="ascii", errors="strict").splitlines():
        match = VERTEX_RE.match(line)
        if not match:
            continue
        vertices.append(tuple(float(match.group(idx)) for idx in range(1, 4)))
    return vertices


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


def observed_bottom_edge_inset(vertices: list[tuple[float, float, float]], edge_radius: float) -> float:
    if not vertices or edge_radius <= 0.0:
        return -999.0
    min_z = min(z for _x, _y, z in vertices)
    bottom = [(x, y) for x, y, z in vertices if z <= min_z + 0.02]
    shoulder = [
        (x, y)
        for x, y, z in vertices
        if min_z + edge_radius * 0.90 <= z <= min_z + edge_radius * 1.10
    ]
    if not bottom or not shoulder:
        return -999.0

    bottom_x = max(x for x, _y in bottom) - min(x for x, _y in bottom)
    bottom_y = max(y for _x, y in bottom) - min(y for _x, y in bottom)
    shoulder_x = max(x for x, _y in shoulder) - min(x for x, _y in shoulder)
    shoulder_y = max(y for _x, y in shoulder) - min(y for _x, y in shoulder)
    return min((shoulder_x - bottom_x) / 2.0, (shoulder_y - bottom_y) / 2.0)


def verify_manifest(manifest: dict[str, Any], manifest_path: Path) -> list[str]:
    errors: list[str] = []
    params = manifest.get("parameters", {})
    if params.get("design_style") != "hollow_one_piece_tray":
        errors.append("housing manifest must set design_style=hollow_one_piece_tray")

    if params.get("battery_floor_cutout_enabled") is not False:
        errors.append("housing manifest must set battery_floor_cutout_enabled=false")

    rear_rise = float(params.get("rear_rise_mm", 0.0))
    if rear_rise < MIN_REAR_RISE_MM:
        errors.append(f"rear_rise_mm {rear_rise:.3f} is below {MIN_REAR_RISE_MM:.3f} mm")

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
    if bottom_edge_radius < MIN_BOTTOM_EDGE_RADIUS_MM:
        errors.append(
            f"bottom_edge_radius_mm {bottom_edge_radius:.3f} is below "
            f"{MIN_BOTTOM_EDGE_RADIUS_MM:.3f} mm"
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

        height_profile = output.get("height_profile", {})
        if float(height_profile.get("rear_rise_mm", 0.0)) < MIN_REAR_RISE_MM:
            errors.append(f"{side}: height_profile rear_rise_mm is missing or too small")
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

        stl_value = output.get("stl")
        if not stl_value:
            errors.append(f"{side}: missing STL path")
            continue
        stl_path = ROOT / stl_value
        if not stl_path.exists():
            errors.append(f"{side}: STL not found: {stl_path.relative_to(ROOT)}")
            continue
        vertices = stl_vertices(stl_path)
        rise = observed_rear_rise(vertices)
        if rise < MIN_OBSERVED_REAR_RISE_MM:
            errors.append(
                f"{side}: observed rear/top-edge rise is {rise:.3f} mm, "
                f"expected >= {MIN_OBSERVED_REAR_RISE_MM:.3f} mm"
            )
        bottom_inset = observed_bottom_edge_inset(vertices, bottom_edge_radius)
        if bottom_inset < MIN_OBSERVED_BOTTOM_EDGE_INSET_MM:
            errors.append(
                f"{side}: observed bottom-edge inset is {bottom_inset:.3f} mm, "
                f"expected >= {MIN_OBSERVED_BOTTOM_EDGE_INSET_MM:.3f} mm"
            )

    if manifest_path != DEFAULT_MANIFEST and not manifest_path.is_absolute():
        errors.append("internal error: manifest path should be absolute")
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
    print("- one-piece tray metadata reports a hollow interior cavity")
    print("- bottom outline has an explicit rounded-corner radius")
    print("- bottom edge has a measurable bevel/roundover inset")
    print("- controller/rear edge height is 1.7x the front edge height")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
