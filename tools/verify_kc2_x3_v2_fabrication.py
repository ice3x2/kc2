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
        "PTH": {"0.800": 3, "0.900": 2, "0.950": 24, "1.500": 62},
        "NPTH": {"1.600": 8, "1.650": 31, "1.700": 62, "2.200": 1, "3.000": 62, "5.000": 31},
    },
    "right": {
        "PTH": {"0.800": 3, "0.900": 2, "0.950": 24, "1.500": 78},
        "NPTH": {"1.600": 10, "1.650": 39, "1.700": 78, "2.200": 1, "3.000": 78, "5.000": 39},
    },
    "coupon": {
        "PTH": {"1.500": 6, "2.000": 9},
        "NPTH": {"1.650": 3, "1.700": 6, "3.000": 6, "5.000": 3},
    },
}
EXPECTED_BOTTOM_PASTE_FLASHES = {"left": 124, "right": 156, "coupon": 12}
EXPECTED_KEY_COUNTS = {"left": 31, "right": 39, "coupon": 3}
EXPECTED_MOUNTING_REFERENCE_LABELS = {
    "left": [f"MH{index}" for index in range(1, 9)],
    "right": [f"MH{index}" for index in range(1, 11)],
    "coupon": [],
}
EXPECTED_MOUNTING_REFERENCE_CENTERS_MM = {
    "left": {
        "MH1": (142.6125, 68.0),
        "MH2": (128.6125, 86.5),
        "MH3": (100.1125, 93.5),
        "MH4": (57.1125, 99.0),
        "MH5": (133.6125, 131.5),
        "MH6": (55.1125, 144.0),
        "MH7": (165.6125, 145.0),
        "MH8": (102.6125, 147.0),
    },
    "right": {
        "MH1": (71.6875, 68.0),
        "MH2": (181.1875, 85.5),
        "MH3": (147.6875, 93.5),
        "MH4": (109.6875, 96.5),
        "MH5": (71.6875, 105.5),
        "MH6": (42.1875, 106.0),
        "MH7": (181.1875, 134.5),
        "MH8": (143.1875, 134.5),
        "MH9": (51.6875, 144.0),
        "MH10": (95.6875, 147.0),
    },
    "coupon": {},
}
# Golden KiCad 10 vector-font records bind the actual plotted glyph strokes,
# not merely the Gerber X2 component attributes on mounting-hole flashes.
_COMMON_GLYPH_CENTERLINE_BBOX_MM = (-1.066667, -0.435105, 1.104761, 0.364895)
_COMMON_GLYPH_INK_BBOX_MM = (-1.116667, -0.485105, 1.154761, 0.414895)
_MOUNTING_GLYPH_GOLDEN_DATA = {
    "MH1": (
        12,
        _COMMON_GLYPH_CENTERLINE_BBOX_MM,
        _COMMON_GLYPH_INK_BBOX_MM,
        "8e5082a8177d787c3db7d945ae6adc77fbdc378d90ab27843d3ebd817fdeeaae",
    ),
    "MH2": (
        17,
        _COMMON_GLYPH_CENTERLINE_BBOX_MM,
        _COMMON_GLYPH_INK_BBOX_MM,
        "241c70f56df447e1a216ceccb958af2dac9d8fa6c383f4fd6200f629c22baefb",
    ),
    "MH3": (
        20,
        _COMMON_GLYPH_CENTERLINE_BBOX_MM,
        _COMMON_GLYPH_INK_BBOX_MM,
        "56c595efa15d153a37a68aa9a02e3db453e34a1da62efc9eb44e3b60d66f85f0",
    ),
    "MH4": (
        10,
        (-1.066667, -0.4732, 1.142857, 0.364895),
        (-1.116667, -0.5232, 1.192857, 0.414895),
        "3ab23741b98fef79304e79673ee7b18835e8c4e5259a6cca9d150e4b3abefa05",
    ),
    "MH5": (
        22,
        _COMMON_GLYPH_CENTERLINE_BBOX_MM,
        _COMMON_GLYPH_INK_BBOX_MM,
        "6dbcd3cddf691021cec560b087b01d21c41c78b44bf1acd576f4192e323b4d8b",
    ),
    "MH6": (
        28,
        _COMMON_GLYPH_CENTERLINE_BBOX_MM,
        _COMMON_GLYPH_INK_BBOX_MM,
        "880a349c18302894d8e78fa3aff5305265851d8dc540df9cdd3caad53035a34a",
    ),
    "MH7": (
        9,
        (-1.066667, -0.435105, 1.142857, 0.364895),
        (-1.116667, -0.485105, 1.192857, 0.414895),
        "b7a5c88e39c1e63deb2be54f69fd244e3cf6c190d52df9bc152d266807075a7a",
    ),
    "MH8": (
        38,
        _COMMON_GLYPH_CENTERLINE_BBOX_MM,
        _COMMON_GLYPH_INK_BBOX_MM,
        "55380bc1fc823280cc279df87ec52e87c29bf53391517d4aec43fb12f885e9db",
    ),
    "MH9": (
        28,
        _COMMON_GLYPH_CENTERLINE_BBOX_MM,
        _COMMON_GLYPH_INK_BBOX_MM,
        "5f821ce10dc89b3c37130ad1b9abea26b9907caa7537b4b8211b1a8e145a31fc",
    ),
    "MH10": (
        32,
        (-1.447619, -0.435105, 1.485714, 0.364895),
        (-1.497619, -0.485105, 1.535714, 0.414895),
        "7fe358165a4156cc535c4f6decdf82ea218ed123cdbac57f412bf1a12f04a392",
    ),
}
EXPECTED_MOUNTING_REFERENCE_GLYPHS = {
    reference: {
        "stroke_count": stroke_count,
        "stroke_width_mm": 0.1,
        "centerline_bbox_relative_mm": centerline_bbox,
        "ink_bbox_relative_mm": ink_bbox,
        "centerline_height_mm": round(centerline_bbox[3] - centerline_bbox[1], 6),
        "ink_height_mm": round(ink_bbox[3] - ink_bbox[1], 6),
        "signature": signature,
    }
    for reference, (stroke_count, centerline_bbox, ink_bbox, signature) in (
        _MOUNTING_GLYPH_GOLDEN_DATA.items()
    )
}
MOUNTING_REFERENCE_OFFSET_MM = (0.0, -1.5)
MOUNTING_GLYPH_WINDOW_HALF_WIDTH_MM = 1.75
MOUNTING_GLYPH_WINDOW_HALF_HEIGHT_MM = 0.50
GERBER_OPERATION_RE = re.compile(r"(?:X-?\d+)?(?:Y-?\d+)?D0[123]\*")
GERBER_DRAW_RE = re.compile(
    r"^(?:X(?P<x>-?\d+))?(?:Y(?P<y>-?\d+))?(?P<operation>D0[123])\*$"
)


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
        "component_references": sorted(
            set(re.findall(r"%TO\.C,(MH\d+)\*%", text)),
            key=lambda reference: int(reference[2:]),
        ),
        "has_end_of_file": text.rstrip().endswith("M02*"),
    }


def _gerber_linear_strokes(payload: bytes) -> list[tuple[float, float, float, float, float]]:
    text = payload.decode("ascii", errors="replace")
    format_match = re.search(r"%FSLAX\d(\d)Y\d(\d)\*%", text)
    if not format_match or format_match.group(1) != format_match.group(2):
        return []
    scale = 10 ** int(format_match.group(1))
    apertures = {
        int(code): float(diameter)
        for code, diameter in re.findall(r"%ADD(\d+)C,([0-9.]+)(?:X[^*]+)?\*%", text)
    }
    current_x: int | None = None
    current_y: int | None = None
    current_aperture: int | None = None
    strokes: list[tuple[float, float, float, float, float]] = []
    for line in text.splitlines():
        aperture_match = re.fullmatch(r"D(\d+)\*", line)
        if aperture_match and int(aperture_match.group(1)) >= 10:
            current_aperture = int(aperture_match.group(1))
            continue
        operation_match = GERBER_DRAW_RE.fullmatch(line)
        if not operation_match:
            continue
        next_x = (
            int(operation_match.group("x"))
            if operation_match.group("x") is not None
            else current_x
        )
        next_y = (
            int(operation_match.group("y"))
            if operation_match.group("y") is not None
            else current_y
        )
        if next_x is None or next_y is None:
            continue
        if (
            operation_match.group("operation") == "D01"
            and current_x is not None
            and current_y is not None
            and current_aperture in apertures
        ):
            # KiCad's plotted Gerber Y coordinate is the negative of the board Y.
            strokes.append(
                (
                    current_x / scale,
                    -current_y / scale,
                    next_x / scale,
                    -next_y / scale,
                    apertures[current_aperture],
                )
            )
        current_x, current_y = next_x, next_y
    return strokes


def _normalized_glyph_record(
    strokes: list[tuple[float, float, float, float, float]],
    anchor: tuple[float, float],
) -> dict[str, object]:
    normalized = sorted(
        (
            round(x1 - anchor[0], 6),
            round(y1 - anchor[1], 6),
            round(x2 - anchor[0], 6),
            round(y2 - anchor[1], 6),
            round(width, 6),
        )
        for x1, y1, x2, y2, width in strokes
    )
    signature_payload = "\n".join(
        ",".join(f"{value:.6f}" for value in segment) for segment in normalized
    ).encode("ascii")
    if not strokes:
        return {
            "stroke_count": 0,
            "stroke_width_mm": None,
            "centerline_bbox_relative_mm": None,
            "ink_bbox_relative_mm": None,
            "centerline_height_mm": 0.0,
            "ink_height_mm": 0.0,
            "signature": sha256_bytes(signature_payload),
        }
    widths = sorted({round(segment[4], 6) for segment in normalized})
    x_values = [coordinate for segment in normalized for coordinate in (segment[0], segment[2])]
    y_values = [coordinate for segment in normalized for coordinate in (segment[1], segment[3])]
    centerline_bbox = (
        round(min(x_values), 6),
        round(min(y_values), 6),
        round(max(x_values), 6),
        round(max(y_values), 6),
    )
    stroke_width = widths[0] if len(widths) == 1 else None
    ink_bbox = None
    ink_height = 0.0
    if stroke_width is not None:
        radius = stroke_width / 2
        ink_bbox = tuple(
            round(value + adjustment * radius, 6)
            for value, adjustment in zip(centerline_bbox, (-1, -1, 1, 1))
        )
        ink_height = round(ink_bbox[3] - ink_bbox[1], 6)
    return {
        "stroke_count": len(normalized),
        "stroke_width_mm": stroke_width,
        "centerline_bbox_relative_mm": centerline_bbox,
        "ink_bbox_relative_mm": ink_bbox,
        "centerline_height_mm": round(centerline_bbox[3] - centerline_bbox[1], 6),
        "ink_height_mm": ink_height,
        "signature": sha256_bytes(signature_payload),
    }


def inspect_mounting_reference_glyphs(
    payload: bytes,
    expected_centers: dict[str, tuple[float, float]],
) -> dict[str, object]:
    all_strokes = _gerber_linear_strokes(payload)
    glyphs: dict[str, dict[str, object]] = {}
    errors: list[str] = []
    for reference, center in expected_centers.items():
        anchor = (
            center[0] + MOUNTING_REFERENCE_OFFSET_MM[0],
            center[1] + MOUNTING_REFERENCE_OFFSET_MM[1],
        )
        local_strokes = [
            stroke
            for stroke in all_strokes
            if all(
                abs(x - anchor[0]) <= MOUNTING_GLYPH_WINDOW_HALF_WIDTH_MM
                and abs(y - anchor[1]) <= MOUNTING_GLYPH_WINDOW_HALF_HEIGHT_MM
                for x, y in ((stroke[0], stroke[1]), (stroke[2], stroke[3]))
            )
        ]
        actual = _normalized_glyph_record(local_strokes, anchor)
        glyphs[reference] = actual
        expected = EXPECTED_MOUNTING_REFERENCE_GLYPHS.get(reference)
        if expected is None:
            errors.append(f"{reference}: no expected plotted-glyph record")
            continue
        mismatches = [
            field
            for field in (
                "stroke_count",
                "stroke_width_mm",
                "centerline_bbox_relative_mm",
                "ink_bbox_relative_mm",
                "centerline_height_mm",
                "ink_height_mm",
                "signature",
            )
            if actual[field] != expected[field]
        ]
        if mismatches:
            errors.append(f"{reference}: plotted glyph mismatch in {', '.join(mismatches)}")
    return {"glyphs": glyphs, "errors": errors}


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
        mounting_reference_glyphs: dict[str, dict[str, object]] = {}
        mounting_reference_glyph_errors: list[str] = []
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
                    if layer == "F.Silkscreen":
                        glyph_inspection = inspect_mounting_reference_glyphs(
                            package.read(entry),
                            EXPECTED_MOUNTING_REFERENCE_CENTERS_MM[product],
                        )
                        mounting_reference_glyphs = glyph_inspection["glyphs"]
                        mounting_reference_glyph_errors = glyph_inspection["errors"]
        if EXPECTED_MOUNTING_REFERENCE_CENTERS_MM[product] and not mounting_reference_glyphs:
            mounting_reference_glyph_errors.append(
                "F.Silkscreen: no mounting-reference glyph geometry"
            )
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
            "mounting_reference_labels": gerber_layers.get("F.Silkscreen", {}).get(
                "component_references", []
            ),
            "mounting_reference_glyphs": mounting_reference_glyphs,
            "mounting_reference_glyph_errors": mounting_reference_glyph_errors,
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
        if details["mounting_reference_labels"] != EXPECTED_MOUNTING_REFERENCE_LABELS[product]:
            errors.append(
                f"{product}: F.Silkscreen MH labels {details['mounting_reference_labels']} "
                f"!= {EXPECTED_MOUNTING_REFERENCE_LABELS[product]}"
            )
        if details["mounting_reference_glyph_errors"]:
            errors.append(
                f"{product}: F.Silkscreen MH plotted glyphs "
                f"{details['mounting_reference_glyph_errors']}"
            )
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
