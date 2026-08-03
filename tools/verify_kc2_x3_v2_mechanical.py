from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT
    / "hardware"
    / "kicad"
    / "draft"
    / "x3-v2"
    / "mechanical"
    / "kc2_x3_v2_mechanical_manifest.json"
)


def analyze_mechanical_outputs(manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    products: dict[str, object] = {}
    for product, details in manifest["products"].items():
        drawings: dict[str, object] = {}
        for face, drawing in details["drawings"].items():
            path = ROOT / drawing["path"]
            data = path.read_bytes() if path.is_file() else b""
            drawings[face] = {
                "exists": path.is_file(),
                "size": len(data),
                "pdf_header_valid": data.startswith(b"%PDF-"),
                "sha256_matches": bool(data)
                and hashlib.sha256(data).hexdigest() == drawing["sha256"],
            }
        products[product] = {"drawings": drawings}
    return {
        "requirement": manifest["requirement"],
        "scale": manifest["scale"],
        "products": products,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify KC2 X3 V2 1:1 assembly drawings.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    report = analyze_mechanical_outputs(args.manifest)
    errors: list[str] = []
    if report["scale"] != 1.0:
        errors.append(f"unexpected scale {report['scale']}")
    for product, details in report["products"].items():
        for face, drawing in details["drawings"].items():
            if not all((drawing["exists"], drawing["pdf_header_valid"], drawing["sha256_matches"])):
                errors.append(f"{product} {face}: invalid PDF or checksum")
    if errors:
        raise SystemExit("FAIL: KC2 X3 V2 mechanical drawings\n- " + "\n- ".join(errors))
    print(json.dumps(report, indent=2))
    print("PASS: CON-ARCH-004 1:1 top/bottom assembly drawings")


if __name__ == "__main__":
    main()
