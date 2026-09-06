"""CON-ARCH-006: verify four native Fusion housing archives and round-trip evidence."""

from __future__ import annotations

import json
import hashlib
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = ROOT / "hardware" / "case" / "kc2_fusion_export_result.json"
F3D_OUTPUTS = {
    f"{side}_{kind}": ROOT / "hardware" / "case" / f"kc2_{side}_{kind}_housing.f3d"
    for kind in ("lower", "mx_upper") for side in ("left", "right")
}
MIN_ARCHIVE_SIZE_BYTES = 1024
BOUNDING_BOX_TOLERANCE_MM = 0.001
PRINT_VOLUME_LIMIT_MM = 150.0
STEP_OUTPUTS = {
    key: path.with_suffix('.step') for key, path in F3D_OUTPUTS.items()
}
EXPECTED_BODY_COUNTS = {
    "left_lower": 1, "right_lower": 2,
    "left_mx_upper": 1, "right_mx_upper": 2,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def valid_bounds(box) -> bool:
    return (isinstance(box, (list, tuple)) and len(box) == 6
            and all(type(value) in (int, float) and math.isfinite(value) for value in box)
            and all(box[axis + 3] > box[axis] for axis in range(3)))


def bounds_equal(before, after) -> bool:
    return (valid_bounds(before) and valid_bounds(after)
            and all(abs(a-b) <= BOUNDING_BOX_TOLERANCE_MM for a,b in zip(before,after)))


def body_bounds_equal(before, after) -> bool:
    if not isinstance(before,list) or not isinstance(after,list) or len(before)!=len(after):
        return False
    unmatched=list(after)
    for box in before:
        index=next((i for i,candidate in enumerate(unmatched) if bounds_equal(box,candidate)),None)
        if index is None:
            return False
        unmatched.pop(index)
    return True


def verify_f3d_outputs(root: Path = ROOT) -> list[str]:
    result_path = root / RESULT_PATH.relative_to(ROOT)
    f3d_outputs = {key: root / p.relative_to(ROOT) for key, p in F3D_OUTPUTS.items()}
    step_outputs = {key: root / p.relative_to(ROOT) for key, p in STEP_OUTPUTS.items()}
    errors: list[str] = []
    for side, path in f3d_outputs.items():
        if not path.exists():
            errors.append(f"{side}: missing Fusion archive {path.relative_to(root)}")
        elif path.stat().st_size < MIN_ARCHIVE_SIZE_BYTES:
            errors.append(f"{side}: Fusion archive is unexpectedly small")

    if not result_path.exists():
        errors.append(f"missing Fusion export result {result_path.relative_to(root)}")
        return errors

    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get('requirement') != 'CON-ARCH-006' or result.get('assembly_mode') != 'mx_receptacle_with_plate':
        errors.append('Fusion result is not the current MX plate-lid assembly')
    if set(result.get('outputs', {})) != set(f3d_outputs):
        errors.append('Fusion result must contain exactly the four lower and MX upper outputs')
    if result.get("status") != "pass":
        errors.append(f"Fusion export status is {result.get('status', 'missing')}")
    for side in f3d_outputs:
        item = result.get("outputs", {}).get(side, {})
        source_solids = item.get('source_solids', [])
        reopened_solids = item.get('archive_reimport_solids', [])
        expected_body_count = EXPECTED_BODY_COUNTS[side]
        if expected_body_count <= 0 or not source_solids or item.get('solid_round_trip_verified') is not True:
            errors.append(f'{side}: missing solid round-trip evidence')
        unmatched = list(reopened_solids)
        for solid in source_solids:
            volume = solid.get('volume_mm3', float('nan'))
            index = next((i for i, after in enumerate(unmatched)
                          if len(solid.get('bounds_mm', [])) == 6
                          and len(after.get('bounds_mm', [])) == 6
                          and all(math.isfinite(a) and math.isfinite(b) and abs(a-b) <= 0.001
                                  for a, b in zip(solid['bounds_mm'], after['bounds_mm']))
                          and math.isfinite(volume) and volume > 0
                          and math.isfinite(after.get('volume_mm3', float('nan')))
                          and abs(volume-after['volume_mm3']) <= max(0.001, volume*1e-6)), None)
            if index is None:
                errors.append(f'{side}: round-trip solid bounds/volume mismatch')
            else:
                unmatched.pop(index)
        if unmatched or len(source_solids) != expected_body_count:
            errors.append(f'{side}: round-trip solid records have incorrect body counts')
        step_path = step_outputs[side]
        if not step_path.exists():
            errors.append(f'{side}: missing source STEP')
        if step_path.exists() and item.get("source_step_sha256") != sha256(step_path):
            errors.append(f"{side}: Fusion result STEP SHA-256 does not match the source file")
        if f3d_outputs[side].exists() and item.get("f3d_sha256") != sha256(f3d_outputs[side]):
            errors.append(f"{side}: Fusion result F3D SHA-256 does not match the archive file")
        if item.get("body_count") != expected_body_count:
            errors.append(f"{side}: Fusion imported body count is {item.get('body_count')}")
        if not item.get("export_ok"):
            errors.append(f"{side}: Fusion archive export did not report success")
        if item.get("archive_reimport_body_count") != expected_body_count:
            errors.append(
                f"{side}: Fusion archive re-import body count is "
                f"{item.get('archive_reimport_body_count')}"
            )
        source_box = item.get("bounding_box_mm", [])
        reimport_box = item.get("archive_reimport_bounding_box_mm", [])
        if not valid_bounds(source_box) or not valid_bounds(reimport_box):
            errors.append(f"{side}: Fusion archive round-trip bounding box is incomplete")
        elif not bounds_equal(source_box,reimport_box):
            errors.append(f"{side}: Fusion archive round-trip changed the bounding box")
        body_boxes = item.get("body_bounding_boxes_mm", [])
        reimport_body_boxes = item.get("archive_reimport_body_bounding_boxes_mm", [])
        if len(body_boxes) != expected_body_count:
            errors.append(f"{side}: Fusion body bounding boxes are incomplete")
        elif not body_bounds_equal(body_boxes,reimport_body_boxes):
            errors.append(f"{side}: Fusion body bounding boxes changed after archive re-import")
        else:
            for index, body_box in enumerate(body_boxes, start=1):
                if not valid_bounds(body_box):
                    errors.append(f"{side}: Fusion body {index} bounding box is incomplete")
                    continue
                dimensions = [
                    float(body_box[axis + 3]) - float(body_box[axis])
                    for axis in range(3)
                ]
                for axis, dimension in zip("XYZ", dimensions):
                    if dimension > PRINT_VOLUME_LIMIT_MM + BOUNDING_BOX_TOLERANCE_MM:
                        errors.append(
                            f"{side}: Fusion body {index} {axis} size {dimension:.3f} mm "
                            f"exceeds the {PRINT_VOLUME_LIMIT_MM:.1f} mm print limit"
                        )
        # Content hashes, rather than checkout timestamps, bind the exact files.
    return errors


def main() -> int:
    errors = verify_f3d_outputs()
    if errors:
        print("FAIL: KC2 native Fusion archive verification")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: KC2 native Fusion archive verification")
    print("- both lower housings and both MX plate-lids have native Fusion archives")
    print("- solid body counts, bounds and volumes match after Fusion re-import")
    print("- every Fusion body fits the 150 mm cube print envelope")
    print("- STEP and F3D SHA-256 values match the Fusion round-trip result")
    print("- native conversion evidence does not establish physical fit or order readiness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
