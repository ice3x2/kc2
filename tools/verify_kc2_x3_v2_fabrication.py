from __future__ import annotations

import argparse
from collections import Counter
import json
import re
from pathlib import Path
from zipfile import ZipFile

if __package__:
    from tools.canonical_hash import HASH_POLICY, sha256_bytes, sha256_file
else:
    from canonical_hash import HASH_POLICY, sha256_bytes, sha256_file


ROOT = Path(__file__).resolve().parents[1]
FAB_ROOT = ROOT / "hardware" / "kicad" / "draft" / "x3-v2" / "fabrication"
MANIFEST = FAB_ROOT / "kc2_x3_v2_fabrication_manifest.json"
REQUIRED_SUFFIXES = {
    "F.Cu": "-F_Cu.gtl",
    "B.Cu": "-B_Cu.gbl",
    "F.Mask": "-F_Mask.gts",
    "B.Mask": "-B_Mask.gbs",
    "F.Paste": "-F_Paste.gtp",
    "B.Paste": "-B_Paste.gbp",
    "F.Silkscreen": "-F_Silkscreen.gto",
    "B.Silkscreen": "-B_Silkscreen.gbo",
    "Edge.Cuts": "-Edge_Cuts.gm1",
}
EXPECTED_FILE_FUNCTIONS = {
    "F.Cu": "Copper,L1,Top",
    "B.Cu": "Copper,L2,Bot",
    "F.Mask": "Soldermask,Top",
    "B.Mask": "Soldermask,Bot",
    "F.Paste": "Paste,Top",
    "B.Paste": "Paste,Bot",
    "F.Silkscreen": "Legend,Top",
    "B.Silkscreen": "Legend,Bot",
    "Edge.Cuts": "Profile,NP",
}
EXPECTED_FIXED_DRILL_TOOLS = {
    "left": {
        "PTH": {"0.950": 24, "1.500": 62},
        "NPTH": {"1.600": 8, "1.650": 31, "1.700": 62, "2.200": 1, "3.000": 62, "5.000": 31},
    },
    "right": {
        "PTH": {"0.950": 24, "1.500": 78},
        "NPTH": {"1.600": 10, "1.650": 39, "1.700": 78, "2.200": 1, "3.000": 78, "5.000": 39},
    },
    "coupon": {
        "PTH": {"1.500": 6, "2.000": 9},
        "NPTH": {"1.650": 3, "1.700": 6, "3.000": 6, "5.000": 3},
    },
}
EXPECTED_BOTTOM_PASTE_FLASHES = {"left": 124, "right": 156, "coupon": 12}
EXPECTED_KEY_COUNTS = {"left": 31, "right": 39, "coupon": 3}
GERBER_OPERATION_RE = re.compile(r"(?:X-?\d+)?(?:Y-?\d+)?D0[123]\*")


def parse_drill_tools(report: str) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {"PTH": {}, "NPTH": {}}
    section: str | None = None
    for line in report.splitlines():
        if "-NPTH.drl" in line:
            section = "NPTH"
        elif "-PTH.drl" in line:
            section = "PTH"
        match = re.search(r"T\d+\s+([0-9.]+)mm.*\((\d+) holes?\)", line)
        if section and match:
            result[section][match.group(1)] = int(match.group(2))
    return result


def inspect_gerber(payload: bytes) -> dict[str, object]:
    text = payload.decode("ascii", errors="replace")
    function_match = re.search(r"%TF\.FileFunction,([^*]+)\*%", text)
    return {
        "file_function": function_match.group(1) if function_match else "",
        "operation_count": len(GERBER_OPERATION_RE.findall(text)),
        "flash_count": text.count("D03*"),
        "has_end_of_file": text.rstrip().endswith("M02*"),
    }


def source_board_via_drills(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {}
    drills = re.findall(
        r"\(via\s+.*?\(drill\s+([0-9.]+)\)",
        path.read_text(encoding="utf-8"),
        flags=re.DOTALL,
    )
    return dict(sorted(Counter(f"{float(value):.3f}" for value in drills).items()))


def expected_drill_tools(product: str, source_board: Path) -> dict[str, dict[str, int]]:
    fixed = EXPECTED_FIXED_DRILL_TOOLS[product]
    pth = dict(fixed["PTH"])
    pth.update(source_board_via_drills(source_board))
    return {"PTH": dict(sorted(pth.items())), "NPTH": fixed["NPTH"]}


def analyze_fabrication(manifest_path: Path = MANIFEST, root: Path = ROOT) -> dict[str, object]:
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    products: dict[str, object] = {}
    for product, details in manifest["products"].items():
        archive = root / details["archive"]
        source_board = root / details["board"]
        output_dir = root / details["output_dir"]
        expected_drills = expected_drill_tools(product, source_board)
        entries: list[str] = []
        archive_digest = ""
        file_hash_mismatches: list[str] = []
        output_file_hash_mismatches: list[str] = []
        drill_tools: dict[str, dict[str, int]] = {"PTH": {}, "NPTH": {}}
        gerber_layers: dict[str, dict[str, object]] = {}
        gerber_geometry_errors: list[str] = []
        if archive.is_file():
            archive_digest = sha256_file(archive)
            with ZipFile(archive) as package:
                entries = package.namelist()
                expected_hashes = {item["name"]: item["sha256"] for item in details["files"]}
                for entry in entries:
                    expected = expected_hashes.get(entry)
                    actual = sha256_bytes(package.read(entry))
                    if expected != actual:
                        file_hash_mismatches.append(entry)
                report_entry = next(
                    (entry for entry in entries if entry.endswith("-drill-report.txt")),
                    None,
                )
                if report_entry:
                    drill_tools = parse_drill_tools(package.read(report_entry).decode("utf-8"))
                for layer, suffix in REQUIRED_SUFFIXES.items():
                    entry = next((name for name in entries if name.endswith(suffix)), None)
                    if entry is None:
                        continue
                    inspection = inspect_gerber(package.read(entry))
                    gerber_layers[layer] = inspection
                    expected_function = EXPECTED_FILE_FUNCTIONS[layer]
                    if inspection["file_function"] != expected_function:
                        gerber_geometry_errors.append(
                            f"{layer}: FileFunction={inspection['file_function']!r}, "
                            f"expected {expected_function!r}"
                        )
                    geometry_may_be_empty = product == "coupon" and layer == "F.Paste"
                    if not geometry_may_be_empty and inspection["operation_count"] == 0:
                        gerber_geometry_errors.append(f"{layer}: no plotted geometry")
                    if not inspection["has_end_of_file"]:
                        gerber_geometry_errors.append(f"{layer}: missing M02 terminator")
        missing_layers = [
            layer
            for layer, suffix in REQUIRED_SUFFIXES.items()
            if not any(entry.endswith(suffix) for entry in entries)
        ]
        drill_types = {
            "PTH": any(entry.endswith("-PTH.drl") for entry in entries),
            "NPTH": any(entry.endswith("-NPTH.drl") for entry in entries),
        }
        for item in details["files"]:
            output_path = output_dir / item["name"]
            if not output_path.is_file() or sha256_file(output_path) != item["sha256"]:
                output_file_hash_mismatches.append(item["name"])
        products[product] = {
            "source_board_exists": source_board.is_file(),
            "source_board_sha256_matches": source_board.is_file()
            and sha256_file(source_board)
            == details.get("source_board_sha256"),
            "key_count_matches": details.get("key_count") == EXPECTED_KEY_COUNTS[product],
            "archive_exists": archive.is_file(),
            "archive_entry_count": len(entries),
            "missing_required_layers": missing_layers,
            "missing_drill_types": [name for name, present in drill_types.items() if not present],
            "nested_archive_entries": [entry for entry in entries if "/" in entry or "\\" in entry],
            "has_bottom_paste": any(entry.endswith("-B_Paste.gbp") for entry in entries),
            "has_job_file": any(entry.endswith(".gbrjob") for entry in entries),
            "archive_sha256_matches": bool(archive_digest)
            and archive_digest == details["archive_sha256"],
            "file_hash_mismatches": file_hash_mismatches,
            "output_file_hash_mismatches": output_file_hash_mismatches,
            "drill_tools_mm": drill_tools,
            "source_board_via_drills_mm": source_board_via_drills(source_board),
            "expected_drill_tools_mm": expected_drills,
            "drill_geometry_matches": drill_tools == expected_drills,
            "gerber_layers": gerber_layers,
            "gerber_geometry_errors": gerber_geometry_errors,
            "bottom_paste_flash_count": gerber_layers.get("B.Paste", {}).get(
                "flash_count", 0
            ),
            "bottom_paste_geometry_matches": gerber_layers.get("B.Paste", {}).get(
                "flash_count", 0
            )
            == EXPECTED_BOTTOM_PASTE_FLASHES[product],
        }
    return {
        "requirement": manifest["requirement"],
        "hash_policy": manifest.get("hash_policy"),
        "hash_policy_matches": manifest.get("hash_policy") == HASH_POLICY,
        "variant": manifest.get("variant"),
        "products": products,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify CON-ARCH-004 draft Gerber and Excellon archives.")
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args()
    report = analyze_fabrication(args.manifest)
    errors: list[str] = []
    if report["variant"] != "x3-v2":
        errors.append(f"unexpected variant {report['variant']!r}")
    if not report["hash_policy_matches"]:
        errors.append(f"hash policy must be {HASH_POLICY!r}")
    for product, details in report["products"].items():
        if not details["archive_exists"]:
            errors.append(f"{product}: archive missing")
        if not details["source_board_exists"]:
            errors.append(f"{product}: source board missing")
        if not details["source_board_sha256_matches"]:
            errors.append(f"{product}: source board SHA-256 mismatch")
        if not details["key_count_matches"]:
            errors.append(f"{product}: manifest key count mismatch")
        if details["missing_required_layers"]:
            errors.append(f"{product}: layers {details['missing_required_layers']}")
        if details["missing_drill_types"]:
            errors.append(f"{product}: drills {details['missing_drill_types']}")
        if details["nested_archive_entries"]:
            errors.append(f"{product}: nested entries {details['nested_archive_entries']}")
        if not details["archive_sha256_matches"]:
            errors.append(f"{product}: archive SHA-256 mismatch")
        if details["file_hash_mismatches"]:
            errors.append(f"{product}: file SHA-256 mismatches {details['file_hash_mismatches']}")
        if details["output_file_hash_mismatches"]:
            errors.append(
                f"{product}: extracted output SHA-256 mismatches "
                f"{details['output_file_hash_mismatches']}"
            )
        if details["gerber_geometry_errors"]:
            errors.append(f"{product}: Gerber geometry {details['gerber_geometry_errors']}")
        if not details["drill_geometry_matches"]:
            errors.append(
                f"{product}: drill geometry {details['drill_tools_mm']} "
                f"!= {details['expected_drill_tools_mm']}"
            )
        if not details["bottom_paste_geometry_matches"]:
            errors.append(
                f"{product}: B.Paste flashes={details['bottom_paste_flash_count']} "
                f"expected={EXPECTED_BOTTOM_PASTE_FLASHES[product]}"
            )
    if errors:
        raise SystemExit("FAIL: KC2 X3 V2 fabrication archives\n- " + "\n- ".join(errors))
    print(json.dumps(report, indent=2))
    print("PASS: CON-ARCH-004 draft Gerber/Excellon archives are structurally complete")


if __name__ == "__main__":
    main()
