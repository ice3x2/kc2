"""Verify native Fusion archive exports for the KC2 X3 lower housings."""

from __future__ import annotations

import json
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
STEP_OUTPUTS = {
    "left": ROOT / "hardware" / "case" / "kc2_left_lower_housing.step",
    "right": ROOT / "hardware" / "case" / "kc2_right_lower_housing.step",
}


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
        if item.get("body_count") != 1:
            errors.append(f"{side}: Fusion imported body count is {item.get('body_count')}")
        if not item.get("export_ok"):
            errors.append(f"{side}: Fusion archive export did not report success")
        if item.get("archive_reimport_body_count") != 1:
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
        step_path = STEP_OUTPUTS[side]
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
    print("- Fusion imported one BRep body for each housing")
    print("- round-trip max Z is 5.10 mm for the flat housing and registration pegs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
