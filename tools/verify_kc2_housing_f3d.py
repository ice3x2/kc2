"""Verify native Fusion archive exports for the KC2 X3 lower housings."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = ROOT / "hardware" / "case" / "kc2_fusion_export_result.json"
F3D_OUTPUTS = {
    "left": ROOT / "hardware" / "case" / "kc2_left_lower_housing.f3d",
    "right": ROOT / "hardware" / "case" / "kc2_right_lower_housing.f3d",
}
MIN_ARCHIVE_SIZE_BYTES = 1024
EXPECTED_MAX_Z_MM = 5.10
BOUNDING_BOX_TOLERANCE_MM = 0.001
PRINT_VOLUME_LIMIT_MM = 150.0
STEP_OUTPUTS = {
    "left": ROOT / "hardware" / "case" / "kc2_left_lower_housing.step",
    "right": ROOT / "hardware" / "case" / "kc2_right_lower_housing.step",
}
EXPECTED_BODY_COUNTS = {"left": 1, "right": 2}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_f3d_outputs() -> list[str]:
    errors: list[str] = []
    for side, path in F3D_OUTPUTS.items():
        if not path.exists():
            errors.append(f"{side}: missing Fusion archive {path.relative_to(ROOT)}")
        elif path.stat().st_size < MIN_ARCHIVE_SIZE_BYTES:
            errors.append(f"{side}: Fusion archive is unexpectedly small")

    if not RESULT_PATH.exists():
        errors.append(f"missing Fusion export result {RESULT_PATH.relative_to(ROOT)}")
        return errors

    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    if result.get("status") != "pass":
        errors.append(f"Fusion export status is {result.get('status', 'missing')}")
    for side in F3D_OUTPUTS:
        item = result.get("outputs", {}).get(side, {})
        expected_body_count = EXPECTED_BODY_COUNTS[side]
        step_path = STEP_OUTPUTS[side]
        if step_path.exists() and item.get("source_step_sha256") != sha256(step_path):
            errors.append(f"{side}: Fusion result STEP SHA-256 does not match the source file")
        if F3D_OUTPUTS[side].exists() and item.get("f3d_sha256") != sha256(F3D_OUTPUTS[side]):
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
        if len(source_box) != 6 or len(reimport_box) != 6:
            errors.append(f"{side}: Fusion archive round-trip bounding box is incomplete")
        elif any(abs(float(before) - float(after)) > 1e-6 for before, after in zip(source_box, reimport_box)):
            errors.append(f"{side}: Fusion archive round-trip changed the bounding box")
        elif abs(float(source_box[5]) - EXPECTED_MAX_Z_MM) > BOUNDING_BOX_TOLERANCE_MM:
            errors.append(
                f"{side}: Fusion archive max Z {float(source_box[5]):.3f} mm is not "
                f"the flat-housing target {EXPECTED_MAX_Z_MM:.3f} mm"
            )
        body_boxes = item.get("body_bounding_boxes_mm", [])
        reimport_body_boxes = item.get("archive_reimport_body_bounding_boxes_mm", [])
        if len(body_boxes) != expected_body_count:
            errors.append(f"{side}: Fusion body bounding boxes are incomplete")
        elif body_boxes != reimport_body_boxes:
            errors.append(f"{side}: Fusion body bounding boxes changed after archive re-import")
        else:
            for index, body_box in enumerate(body_boxes, start=1):
                if len(body_box) != 6:
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
        if step_path.exists() and F3D_OUTPUTS[side].stat().st_mtime < step_path.stat().st_mtime:
            errors.append(f"{side}: Fusion archive is older than its source STEP file")
    return errors


def main() -> int:
    errors = verify_f3d_outputs()
    if errors:
        print("FAIL: KC2 native Fusion archive verification")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: KC2 native Fusion archive verification")
    print("- left/right F3D archives were exported by the installed Fusion API")
    print("- Fusion imported one left BRep body and two right BRep bodies")
    print("- every Fusion body fits the 150 mm cube print envelope")
    print("- STEP and F3D SHA-256 values match the Fusion round-trip result")
    print("- round-trip max Z is 5.10 mm for the flat housing and registration pegs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
