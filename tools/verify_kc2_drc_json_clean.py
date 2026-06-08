from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DRC_PATHS = {
    "left": ROOT / "hardware" / "kicad" / "kc2_left" / "kc2_left.drc.json",
    "right": ROOT / "hardware" / "kicad" / "kc2_right" / "kc2_right.drc.json",
}

ALLOWED_WARNING_TYPES = {"silk_over_copper"}


def load_drc(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def describe_item(item: dict[str, Any]) -> str:
    description = item.get("description", "<no description>")
    pos = item.get("pos")
    if isinstance(pos, dict) and "x" in pos and "y" in pos:
        return f"{description} at ({pos['x']}, {pos['y']})"
    return description


def check_side(side: str, path: Path) -> list[str]:
    if not path.exists():
        return [f"{side}: missing DRC JSON {path}"]

    data = load_drc(path)
    violations = list(data.get("violations", []))
    unconnected = list(data.get("unconnected_items", []))
    errors: list[str] = []

    severity_counts = Counter(v.get("severity", "<missing>") for v in violations)
    type_counts = Counter(v.get("type", "<missing>") for v in violations)
    print(
        f"{side}: violations={len(violations)} "
        f"errors={severity_counts.get('error', 0)} "
        f"warnings={severity_counts.get('warning', 0)} "
        f"unconnected={len(unconnected)}"
    )
    if type_counts:
        print(f"{side}: violation types={dict(sorted(type_counts.items()))}")

    for item in unconnected:
        descriptions = "; ".join(describe_item(i) for i in item.get("items", []))
        errors.append(f"{side}: unconnected item remains: {descriptions}")

    for violation in violations:
        severity = violation.get("severity")
        rule = violation.get("type", "<missing>")
        if severity == "error":
            descriptions = "; ".join(describe_item(i) for i in violation.get("items", []))
            errors.append(f"{side}: DRC error {rule}: {descriptions}")
        elif severity == "warning" and rule not in ALLOWED_WARNING_TYPES:
            descriptions = "; ".join(describe_item(i) for i in violation.get("items", []))
            errors.append(f"{side}: non-waived DRC warning {rule}: {descriptions}")

    return errors


def main() -> int:
    errors: list[str] = []
    for side, path in DRC_PATHS.items():
        errors.extend(check_side(side, path))

    if errors:
        print("FAIL: KC2 DRC JSON is not fabrication-clean")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PASS: KC2 DRC JSON is fabrication-clean")
    print(f"- allowed warnings: {sorted(ALLOWED_WARNING_TYPES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
