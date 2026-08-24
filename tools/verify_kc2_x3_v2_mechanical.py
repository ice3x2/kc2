from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__:
    from tools.canonical_hash import HASH_POLICY, sha256_file
else:
    from canonical_hash import HASH_POLICY, sha256_file


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


def analyze_mechanical_outputs(
    manifest_path: Path = DEFAULT_MANIFEST, root: Path = ROOT
) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    products: dict[str, object] = {}
    for product, details in manifest["products"].items():
        board = root / details["board"]
        drawings: dict[str, object] = {}
        for face, drawing in details["drawings"].items():
            path = root / drawing["path"]
            data = path.read_bytes() if path.is_file() else b""
            drawings[face] = {
                "exists": path.is_file(),
                "size": len(data),
                "pdf_header_valid": data.startswith(b"%PDF-"),
                "sha256_matches": bool(data)
                and sha256_file(path) == drawing["sha256"],
            }
        products[product] = {
            "source_board_exists": board.is_file(),
            "source_board_sha256_matches": board.is_file()
            and sha256_file(board)
            == details.get("source_board_sha256"),
            "drawings": drawings,
        }
        outline = details.get("outline_svg")
        if outline is not None:
            outline_path = root / outline["path"]
            outline_data = outline_path.read_bytes() if outline_path.is_file() else b""
            products[product]["outline_svg"] = {
                "exists": outline_path.is_file(),
                "size": len(outline_data),
                "svg_header_valid": outline_data.startswith(b"<?xml") and b"<svg" in outline_data[:1000],
                "sha256_matches": bool(outline_data)
                and sha256_file(outline_path) == outline["sha256"],
                "scale": outline.get("scale"),
                "has_trailing_whitespace": any(
                    line.endswith((b" ", b"\t"))
                    for line in outline_data.splitlines()
                ),
            }
    return {
        "requirement": manifest["requirement"],
        "hash_policy": manifest.get("hash_policy"),
        "hash_policy_matches": manifest.get("hash_policy") == HASH_POLICY,
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
    if not report["hash_policy_matches"]:
        errors.append(f"hash policy must be {HASH_POLICY!r}")
    for product, details in report["products"].items():
        if not details["source_board_exists"]:
            errors.append(f"{product}: source board missing")
        if not details["source_board_sha256_matches"]:
            errors.append(f"{product}: source board SHA-256 mismatch")
        for face, drawing in details["drawings"].items():
            if not all((drawing["exists"], drawing["pdf_header_valid"], drawing["sha256_matches"])):
                errors.append(f"{product} {face}: invalid PDF or checksum")
        if product in {"left", "right"}:
            outline = details.get("outline_svg")
            if not outline or not all(
                (
                    outline["exists"],
                    outline["svg_header_valid"],
                    outline["sha256_matches"],
                    outline["scale"] == 1.0,
                    not outline["has_trailing_whitespace"],
                )
            ):
                errors.append(f"{product}: invalid 1:1 outline SVG or checksum")
    if errors:
        raise SystemExit("FAIL: KC2 X3 V2 mechanical drawings\n- " + "\n- ".join(errors))
    print(json.dumps(report, indent=2))
    print("PASS: CON-ARCH-004 1:1 top/bottom assembly drawings")


if __name__ == "__main__":
    main()
