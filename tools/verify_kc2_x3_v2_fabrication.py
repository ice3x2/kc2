from __future__ import annotations

import argparse
from collections import Counter
import csv
import io
import json
import re
from pathlib import Path
from zipfile import ZipFile

if __package__:
    from tools.canonical_hash import HASH_POLICY, sha256_bytes, sha256_file
    from tools.kc2_x3_v2_output_geometry import (
        REQUIREMENT_IDS,
        bom_csv_bytes,
        build_board_bom,
        build_jlcpcb_pcba_quote,
        jlcpcb_pcba_bom_csv_bytes,
        jlcpcb_pcba_cpl_csv_bytes,
        parse_board,
        source_control_flashes,
        source_drill_geometry,
        source_j_bat_markings,
    )
else:
    from canonical_hash import HASH_POLICY, sha256_bytes, sha256_file
    from kc2_x3_v2_output_geometry import (
        REQUIREMENT_IDS,
        bom_csv_bytes,
        build_board_bom,
        build_jlcpcb_pcba_quote,
        jlcpcb_pcba_bom_csv_bytes,
        jlcpcb_pcba_cpl_csv_bytes,
        parse_board,
        source_control_flashes,
        source_drill_geometry,
        source_j_bat_markings,
    )


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
        "NPTH": {"1.600": 9, "1.650": 39, "1.700": 78, "2.200": 1, "3.000": 78, "5.000": 39},
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
    "right": [f"MH{index}" for index in range(1, 10)],
    "coupon": [],
}
EXPECTED_MOUNTING_REFERENCE_CENTERS_MM = {
    "left": {
        "MH1": (112.8625, 43.0),
        "MH2": (144.1125, 66.25),
        "MH3": (39.3625, 111.0),
        "MH4": (63.6125, 123.0),
        "MH5": (81.1125, 151.75),
        "MH6": (137.3625, 153.5),
        "MH7": (165.8625, 148.75),
        "MH8": (75.25, 134.0),
    },
    "right": {
        "MH1": (97.1875, 43.25),
        "MH2": (72.4375, 67.0),
        "MH3": (170.4375, 95.25),
        "MH4": (194.4375, 98.75),
        "MH5": (155.9375, 112.5),
        "MH6": (70.1875, 146.75),
        "MH7": (97.6875, 152.0),
        "MH8": (122.6875, 151.0),
        "MH9": (177.75, 117.25),
    },
    "coupon": {},
}
EXPECTED_JLCPCB_PROFILE = {
    "schema": "kc2-x3-v2-jlcpcb-profile-v1",
    "vendor": "JLCPCB",
    "purpose": "prototype_only_pending_physical_evidence",
    "layer_count": 2,
    "material": "FR-4",
    "board_thickness_mm": 1.6,
    "copper_weight_oz": 1.0,
    "surface_finish": "enig",
    "solder_mask_color": "green",
    "silkscreen_color": "white",
    "via_covering": "tented",
    "maximum_tented_via_drill_mm": 0.5,
    "assembly_service": "none_hand_assembly",
    "confirm_production_file": True,
    "order_ready": False,
}
EXPECTED_JLCPCB_PCBA_QUOTE_PROFILE = {
    "schema": "kc2-x3-v2-jlcpcb-pcba-quote-v2",
    "vendor": "JLCPCB",
    "purpose": "pricing_quote_only_not_order_authorization",
    "assembly_side": "bottom",
    "assembled_reference_families": ["D", "SW"],
    "assembled_parts": {
        "D": {
            "manufacturer": "Diodes Incorporated",
            "manufacturer_part_number": "1N4148W-13-F",
            "lcsc_part_number": "C112342",
            "jlcpcb_part_number": "C526199",
            "package": "SOD-123",
        },
        "SW": {
            "manufacturer_part_number": "CPG135001S30",
            "lcsc_part_number": "C5333465",
        },
    },
    "inventory_recheck_required": True,
    "exact_diode_if_unavailable": "dnp_and_hand_assemble_no_substitution",
    "placement_and_orientation_confirmation_required": True,
    "bom_only_1n4148_substitution_allowed": False,
    "board_revision_required_for_1n4148_family": False,
    "order_ready": False,
}
JLCPCB_FABRICATION_SUFFIXES = (
    "-F_Cu.gtl",
    "-B_Cu.gbl",
    "-F_Mask.gts",
    "-B_Mask.gbs",
    "-F_Paste.gtp",
    "-B_Paste.gbp",
    "-F_Silkscreen.gto",
    "-B_Silkscreen.gbo",
    "-Edge_Cuts.gm1",
    "-PTH.drl",
    "-NPTH.drl",
    "-PTH-drl_map.gbr",
    "-NPTH-drl_map.gbr",
    "-drill-report.txt",
    "-job.gbrjob",
)
EXPECTED_J_BAT_MARKING_GLYPHS = {
    "B+": {
        "stroke_count": 20,
        "stroke_width_mm": 0.12,
        "centerline_bbox_relative_mm": (-0.704762, -0.436145, 0.704762, 0.363855),
        "ink_bbox_relative_mm": (-0.764762, -0.496145, 0.764762, 0.423855),
        "centerline_height_mm": 0.8,
        "ink_height_mm": 0.92,
        "signature": "4774d5c0746c37505913056816ae981e7522c6a8822d2f50b128d51cff2c5a92",
    },
    "B-/GND": {
        "stroke_count": 51,
        "stroke_width_mm": 0.12,
        "centerline_bbox_relative_mm": (-2.342857, -0.47424, 2.380952, 0.554331),
        "ink_bbox_relative_mm": (-2.402857, -0.53424, 2.440952, 0.614331),
        "centerline_height_mm": 1.028571,
        "ink_height_mm": 1.148571,
        "signature": "29d82abfc452d9e43eb6562ac6496903d9305ecddbe3330047dfb6ef62179fe6",
    },
}
# Golden KiCad 10 vector-font records bind the actual plotted glyph strokes,
# not merely the Gerber X2 component attributes on mounting-hole flashes.
_COMMON_GLYPH_CENTERLINE_BBOX_MM = (-1.066667, -0.437705, 1.104761, 0.362295)
_COMMON_GLYPH_INK_BBOX_MM = (-1.141667, -0.512705, 1.179761, 0.437295)
_MOUNTING_GLYPH_GOLDEN_DATA = {
    "MH1": (
        12,
        _COMMON_GLYPH_CENTERLINE_BBOX_MM,
        _COMMON_GLYPH_INK_BBOX_MM,
        "4db699b5215900fda1bbcb88a7db88ee439cf9355d3c8a6befc5b3472ea22be2",
    ),
    "MH2": (
        17,
        _COMMON_GLYPH_CENTERLINE_BBOX_MM,
        _COMMON_GLYPH_INK_BBOX_MM,
        "33fefad39c833d0e3150a4bf7089b54c421f1174f23ef6842f6f2d1672749ccd",
    ),
    "MH3": (
        20,
        _COMMON_GLYPH_CENTERLINE_BBOX_MM,
        _COMMON_GLYPH_INK_BBOX_MM,
        "e4c71a011b8f48a2a32dcc1fd65ba122037ad1faaab80ce7c8c43166cdb300d3",
    ),
    "MH4": (
        10,
        (-1.066667, -0.4758, 1.142857, 0.362295),
        (-1.141667, -0.5508, 1.217857, 0.437295),
        "4dac779eeddfc5d43dbcbfa1d6baa1f8afa734441327d84c9953c7939a1fe44e",
    ),
    "MH5": (
        22,
        _COMMON_GLYPH_CENTERLINE_BBOX_MM,
        _COMMON_GLYPH_INK_BBOX_MM,
        "64da6e610ceb26f0dff9e43749671be426e5efcc27c53474e6db0e8ca59afc43",
    ),
    "MH6": (
        28,
        _COMMON_GLYPH_CENTERLINE_BBOX_MM,
        _COMMON_GLYPH_INK_BBOX_MM,
        "7d0d42aeeab10871a4efc19c06fbe0665b260fcfb9bec942da1a2de6778245e0",
    ),
    "MH7": (
        9,
        (-1.066667, -0.437705, 1.142857, 0.362295),
        (-1.141667, -0.512705, 1.217857, 0.437295),
        "42143a50981460c18a7a61a075c8503671198e6d64c449c1bed5ce640f43781b",
    ),
    "MH8": (
        38,
        _COMMON_GLYPH_CENTERLINE_BBOX_MM,
        _COMMON_GLYPH_INK_BBOX_MM,
        "83fc601e326cc86fd9849f097d77f58063fc4772a8f467c53768ed55a0790cfa",
    ),
    "MH9": (
        28,
        _COMMON_GLYPH_CENTERLINE_BBOX_MM,
        _COMMON_GLYPH_INK_BBOX_MM,
        "638ee835c64a8bc059d126f3b8d683e40b7328a1a07be7071a40aff8618aa88d",
    ),
    "MH10": (
        32,
        (-1.447619, -0.437705, 1.485714, 0.362295),
        (-1.522619, -0.512705, 1.560714, 0.437295),
        "769a8e4d73932593a8c96c0799782b50a7d633d62d7f616606211604dc89bc04",
    ),
}
EXPECTED_MOUNTING_REFERENCE_GLYPHS = {
    reference: {
        "stroke_count": stroke_count,
        "stroke_width_mm": 0.15,
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
GEOMETRY_TOLERANCE_MM = 0.002


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


def inspect_excellon(payload: bytes) -> list[dict[str, object]]:
    text = payload.decode("ascii", errors="replace")
    tools = {
        int(tool): float(diameter)
        for tool, diameter in re.findall(r"(?m)^T(\d+)C([0-9.]+)\r?$", text)
    }
    active_tool: int | None = None
    records: list[dict[str, object]] = []
    coordinate = r"X(-?[0-9.]+)Y(-?[0-9.]+)"
    for line in text.splitlines():
        tool_match = re.fullmatch(r"T(\d+)", line)
        if tool_match:
            active_tool = int(tool_match.group(1))
            continue
        if active_tool not in tools:
            continue
        slot_match = re.fullmatch(coordinate + r"G85" + coordinate, line)
        if slot_match:
            x1, y1, x2, y2 = map(float, slot_match.groups())
            y1, y2 = -y1, -y2
            diameter = tools[active_tool]
            records.append(
                {
                    "center": (round((x1 + x2) / 2, 6), round((y1 + y2) / 2, 6)),
                    "shape": "slot",
                    "size": (
                        round(abs(x2 - x1) + diameter, 6),
                        round(abs(y2 - y1) + diameter, 6),
                    ),
                }
            )
            continue
        point_match = re.fullmatch(coordinate, line)
        if point_match:
            x, y = map(float, point_match.groups())
            diameter = tools[active_tool]
            records.append(
                {
                    "center": (round(x, 6), round(-y, 6)),
                    "shape": "round",
                    "size": (diameter, diameter),
                }
            )
    records.sort(key=lambda item: (item["size"], item["center"]))
    return records


def _aperture_size(kind: str, parameters: str) -> tuple[float, float] | None:
    values = [float(value) for value in re.findall(r"-?[0-9.]+", parameters)]
    if not values:
        return None
    if kind == "C":
        return (values[0], values[0])
    if kind in {"R", "O"} and len(values) >= 2:
        return (values[0], values[1])
    if kind == "RoundRect" and len(values) >= 9:
        radius = values[0]
        xs, ys = values[1::2], values[2::2]
        return (
            round(max(xs) - min(xs) + 2 * radius, 6),
            round(max(ys) - min(ys) + 2 * radius, 6),
        )
    return None


def inspect_gerber_flashes(payload: bytes) -> list[dict[str, object]]:
    text = payload.decode("ascii", errors="replace")
    format_match = re.search(r"%FSLAX\d(\d)Y\d(\d)\*%", text)
    if not format_match or format_match.group(1) != format_match.group(2):
        return []
    scale = 10 ** int(format_match.group(1))
    apertures: dict[int, tuple[float, float]] = {}
    for code, kind, parameters in re.findall(r"%ADD(\d+)([A-Za-z]+),([^*]+)\*%", text):
        size = _aperture_size(kind, parameters)
        if size:
            apertures[int(code)] = size
    active_aperture: int | None = None
    reference = ""
    pad = ""
    records: list[dict[str, object]] = []
    for line in text.splitlines():
        aperture_match = re.fullmatch(r"D(\d+)\*", line)
        if aperture_match and int(aperture_match.group(1)) >= 10:
            active_aperture = int(aperture_match.group(1))
            continue
        component_match = re.fullmatch(r"%TO\.C,([^*]+)\*%", line)
        if component_match:
            reference, pad = component_match.group(1), ""
            continue
        pad_match = re.fullmatch(r"%TO\.P,([^,]+),([^*]+)\*%", line)
        if pad_match:
            reference, pad = pad_match.groups()
            continue
        if line == "%TD*%":
            reference, pad = "", ""
            continue
        flash_match = re.fullmatch(r"X(-?\d+)Y(-?\d+)D03\*", line)
        if flash_match and active_aperture in apertures:
            x, y = map(int, flash_match.groups())
            records.append(
                {
                    "reference": reference,
                    "pad": pad,
                    "center": (round(x / scale, 6), round(-y / scale, 6)),
                    "size": apertures[active_aperture],
                }
            )
    return records


def _geometry_delta_errors(
    expected: list[dict[str, object]],
    actual: list[dict[str, object]],
    label: str,
) -> list[str]:
    remaining = list(actual)
    errors: list[str] = []

    def close_pair(left: tuple[float, float], right: tuple[float, float]) -> bool:
        return all(abs(a - b) <= GEOMETRY_TOLERANCE_MM for a, b in zip(left, right))

    for wanted in expected:
        match_index = next(
            (
                index
                for index, candidate in enumerate(remaining)
                if wanted.get("shape") == candidate.get("shape")
                and close_pair(wanted["center"], candidate["center"])
                and close_pair(wanted["size"], candidate["size"])
                and (
                    not candidate.get("reference")
                    or candidate.get("reference") == wanted.get("reference")
                )
                and (not candidate.get("pad") or candidate.get("pad") == wanted.get("pad"))
            ),
            None,
        )
        if match_index is None:
            errors.append(
                f"{label}: missing {wanted.get('reference', '')}/{wanted.get('pad', '')} "
                f"{wanted['shape'] if 'shape' in wanted else 'flash'} "
                f"at {wanted['center']} size {wanted['size']}"
            )
        else:
            remaining.pop(match_index)
    if remaining:
        errors.append(f"{label}: {len(remaining)} unexpected geometries; first={remaining[0]}")
    return errors


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


def inspect_j_bat_marking_glyphs(
    payload: bytes, board: dict[str, object]
) -> dict[str, object]:
    source = source_j_bat_markings(board)
    errors = list(source["errors"])
    all_strokes = _gerber_linear_strokes(payload)
    glyphs: dict[str, dict[str, object]] = {}
    for text, expected in EXPECTED_J_BAT_MARKING_GLYPHS.items():
        marking = source["markings"].get(text)
        if marking is None:
            continue
        anchor = marking["center"]
        bbox = expected["centerline_bbox_relative_mm"]
        half_width = max(abs(bbox[0]), abs(bbox[2])) + 0.02
        half_height = max(abs(bbox[1]), abs(bbox[3])) + 0.02
        local_strokes = [
            stroke
            for stroke in all_strokes
            if all(
                abs(x - anchor[0]) <= half_width
                and abs(y - anchor[1]) <= half_height
                for x, y in ((stroke[0], stroke[1]), (stroke[2], stroke[3]))
            )
        ]
        actual = _normalized_glyph_record(local_strokes, anchor)
        glyphs[text] = actual
        mismatches = [field for field in expected if actual[field] != expected[field]]
        if mismatches:
            errors.append(
                f"J_BAT1 F.SilkS {text!r} plotted glyph mismatch in "
                f"{', '.join(mismatches)}"
            )
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


def jlcpcb_profile_errors(profile: object) -> list[str]:
    if not isinstance(profile, dict):
        return ["JLCPCB profile is missing or not an object"]
    errors = [
        f"JLCPCB profile {key}={profile.get(key)!r}, expected {expected!r}"
        for key, expected in EXPECTED_JLCPCB_PROFILE.items()
        if profile.get(key) != expected
    ]
    unexpected = sorted(set(profile) - set(EXPECTED_JLCPCB_PROFILE))
    if unexpected:
        errors.append(f"JLCPCB profile has unexpected fields {unexpected}")
    return errors


def jlcpcb_pcba_quote_profile_errors(profile: object) -> list[str]:
    if not isinstance(profile, dict):
        return ["JLCPCB PCBA quote profile is missing or not an object"]
    errors = [
        f"JLCPCB PCBA quote profile {key}={profile.get(key)!r}, expected {expected!r}"
        for key, expected in EXPECTED_JLCPCB_PCBA_QUOTE_PROFILE.items()
        if profile.get(key) != expected
    ]
    unexpected = sorted(set(profile) - set(EXPECTED_JLCPCB_PCBA_QUOTE_PROFILE))
    if unexpected:
        errors.append(f"JLCPCB PCBA quote profile has unexpected fields {unexpected}")
    return errors


def inspect_jlcpcb_pcba_quote(
    product: str,
    details: dict[str, object],
    board_geometry: dict[str, object] | None,
    source_board: Path,
    root: Path,
) -> dict[str, object]:
    quote_details = details.get("pcba_quote")
    errors: list[str] = []
    if not isinstance(quote_details, dict):
        return {
            "bom_exists": False,
            "cpl_exists": False,
            "bom_sha256_matches": False,
            "cpl_sha256_matches": False,
            "diode_count": 0,
            "socket_count": 0,
            "assembled_reference_count": 0,
            "layers": [],
            "lcsc_part_numbers": [],
            "socket_centroids_are_body_derived": False,
            "order_ready": None,
            "errors": ["manifest PCBA quote record missing"],
        }
    bom_path = root / str(quote_details.get("bom", "<missing-bom>"))
    cpl_path = root / str(quote_details.get("cpl", "<missing-cpl>"))
    bom_exists, cpl_exists = bom_path.is_file(), cpl_path.is_file()
    bom_hash_matches = bom_exists and sha256_file(bom_path) == quote_details.get("bom_sha256")
    cpl_hash_matches = cpl_exists and sha256_file(cpl_path) == quote_details.get("cpl_sha256")
    if not bom_exists:
        errors.append("JLCPCB PCBA quote BOM missing")
    if not cpl_exists:
        errors.append("JLCPCB PCBA quote CPL missing")
    if bom_exists and not bom_hash_matches:
        errors.append("JLCPCB PCBA quote BOM SHA-256 mismatch")
    if cpl_exists and not cpl_hash_matches:
        errors.append("JLCPCB PCBA quote CPL SHA-256 mismatch")

    expected: dict[str, object] | None = None
    if board_geometry is not None:
        expected = build_jlcpcb_pcba_quote(
            product,
            str(source_board.relative_to(root)),
            str(details.get("source_board_sha256")),
            board_geometry,
        )
        if bom_exists and bom_path.read_bytes() != jlcpcb_pcba_bom_csv_bytes(expected):
            errors.append("JLCPCB PCBA quote BOM is not the exact source-board selection")
        if cpl_exists and cpl_path.read_bytes() != jlcpcb_pcba_cpl_csv_bytes(expected):
            errors.append("JLCPCB PCBA quote CPL is not the exact source-board placement set")
        expected_diode_count = len(expected["line_items"][0]["designators"])
        expected_socket_count = len(expected["line_items"][1]["designators"])
        expected_placement_count = len(expected["placements"])
        for key, value in (
            ("diode_count", expected_diode_count),
            ("socket_count", expected_socket_count),
            ("assembled_reference_count", expected_placement_count),
        ):
            if quote_details.get(key) != value:
                errors.append(f"manifest PCBA quote {key}={quote_details.get(key)!r}, expected {value}")
    else:
        expected_diode_count = expected_socket_count = expected_placement_count = 0
    if quote_details.get("order_ready") is not False:
        errors.append("manifest PCBA quote order_ready must be false")

    bom_rows: list[dict[str, str]] = []
    cpl_rows: list[dict[str, str]] = []
    if bom_exists:
        bom_rows = list(csv.DictReader(io.StringIO(bom_path.read_text(encoding="utf-8"))))
    if cpl_exists:
        cpl_rows = list(csv.DictReader(io.StringIO(cpl_path.read_text(encoding="utf-8"))))
    layers = sorted({row.get("Layer", "") for row in cpl_rows if row.get("Layer")})
    lcsc_numbers = sorted(
        {row.get("LCSC Part #", "") for row in bom_rows if row.get("LCSC Part #")}
    )
    socket_centroids_are_body_derived = bool(expected) and all(
        item["centroid_source"] == "bottom_fab_body_bbox"
        for item in expected["placements"]
        if str(item["designator"]).startswith("SW")
    )
    return {
        "bom_exists": bom_exists,
        "cpl_exists": cpl_exists,
        "bom_sha256_matches": bom_hash_matches,
        "cpl_sha256_matches": cpl_hash_matches,
        "diode_count": expected_diode_count,
        "socket_count": expected_socket_count,
        "assembled_reference_count": expected_placement_count,
        "layers": layers,
        "lcsc_part_numbers": lcsc_numbers,
        "socket_centroids_are_body_derived": socket_centroids_are_body_derived,
        "order_ready": quote_details.get("order_ready"),
        "errors": errors,
    }


def source_board_tenting(path: Path) -> dict[str, bool]:
    if not path.is_file():
        return {"front": False, "back": False}
    text = path.read_text(encoding="utf-8")
    match = re.search(
        r"\(tenting\s+\(front\s+(yes|no)\)\s+\(back\s+(yes|no)\)\s*\)",
        text,
        flags=re.DOTALL,
    )
    if match is None:
        return {"front": False, "back": False}
    return {"front": match.group(1) == "yes", "back": match.group(2) == "yes"}


def mask_open_via_centers(
    board_geometry: dict[str, object], payload: bytes
) -> list[list[float]]:
    openings = inspect_gerber_flashes(payload)
    result: list[list[float]] = []
    for via in board_geometry.get("vias", []):
        center = tuple(via["center"])
        if any(
            abs(float(flash["center"][0]) - float(center[0])) <= 0.0001
            and abs(float(flash["center"][1]) - float(center[1])) <= 0.0001
            for flash in openings
        ):
            result.append([round(float(center[0]), 4), round(float(center[1]), 4)])
    return result


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
        jlcpcb_archive_value = details.get("jlcpcb_archive", "<missing-jlcpcb-archive>")
        jlcpcb_archive = root / jlcpcb_archive_value
        source_board = root / details["board"]
        output_dir = root / details["output_dir"]
        expected_drills = expected_drill_tools(product, source_board)
        board_geometry = parse_board(source_board) if source_board.is_file() else None
        expected_source_drills = (
            source_drill_geometry(board_geometry) if board_geometry is not None else {"PTH": [], "NPTH": []}
        )
        entries: list[str] = []
        archive_digest = ""
        file_hash_mismatches: list[str] = []
        output_file_hash_mismatches: list[str] = []
        drill_tools: dict[str, dict[str, int]] = {"PTH": {}, "NPTH": {}}
        gerber_layers: dict[str, dict[str, object]] = {}
        gerber_geometry_errors: list[str] = []
        mounting_reference_glyphs: dict[str, dict[str, object]] = {}
        mounting_reference_glyph_errors: list[str] = []
        j_bat_marking_glyphs: dict[str, dict[str, object]] = {}
        j_bat_marking_errors: list[str] = []
        drill_source_geometry_errors: list[str] = []
        gerber_source_geometry_errors: list[str] = []
        bom_errors: list[str] = []
        mask_open_vias: dict[str, list[list[float]]] = {"front": [], "back": []}
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
                for plating, suffix in (("PTH", "-PTH.drl"), ("NPTH", "-NPTH.drl")):
                    drill_entry = next((entry for entry in entries if entry.endswith(suffix)), None)
                    if drill_entry is None:
                        continue
                    expected_geometry = expected_source_drills[plating]
                    drill_source_geometry_errors.extend(
                        _geometry_delta_errors(
                            expected_geometry,
                            inspect_excellon(package.read(drill_entry)),
                            f"archive {plating}",
                        )
                    )
                    extracted_drill = output_dir / drill_entry
                    if extracted_drill.is_file():
                        drill_source_geometry_errors.extend(
                            _geometry_delta_errors(
                                expected_geometry,
                                inspect_excellon(extracted_drill.read_bytes()),
                                f"extracted {plating}",
                            )
                        )
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
                    if board_geometry is not None and layer in {
                        "F.Paste",
                        "B.Cu",
                        "B.Mask",
                        "B.Paste",
                    }:
                        expected_flashes = source_control_flashes(board_geometry, layer)

                        def selected_flashes(payload: bytes) -> list[dict[str, object]]:
                            flashes = inspect_gerber_flashes(payload)
                            return [
                                flash
                                for flash in flashes
                                if (layer == "F.Paste" and flash["reference"] == "SW_RST1")
                                or (
                                    layer != "F.Paste"
                                    and re.fullmatch(r"D\d+", str(flash["reference"]))
                                )
                            ]

                        gerber_source_geometry_errors.extend(
                            _geometry_delta_errors(
                                expected_flashes,
                                selected_flashes(package.read(entry)),
                                f"archive {layer}",
                            )
                        )
                        extracted_gerber = output_dir / entry
                        if extracted_gerber.is_file():
                            gerber_source_geometry_errors.extend(
                                _geometry_delta_errors(
                                    expected_flashes,
                                    selected_flashes(extracted_gerber.read_bytes()),
                                    f"extracted {layer}",
                                )
                            )
                    if layer == "F.Silkscreen":
                        glyph_inspection = inspect_mounting_reference_glyphs(
                            package.read(entry),
                            EXPECTED_MOUNTING_REFERENCE_CENTERS_MM[product],
                        )
                        mounting_reference_glyphs = glyph_inspection["glyphs"]
                        mounting_reference_glyph_errors = glyph_inspection["errors"]
                        if product in {"left", "right"} and board_geometry is not None:
                            marking_inspection = inspect_j_bat_marking_glyphs(
                                package.read(entry), board_geometry
                            )
                            j_bat_marking_glyphs = marking_inspection["glyphs"]
                            j_bat_marking_errors.extend(
                                f"archive {error}" for error in marking_inspection["errors"]
                            )
                            extracted_gerber = output_dir / entry
                            if extracted_gerber.is_file():
                                extracted_inspection = inspect_j_bat_marking_glyphs(
                                    extracted_gerber.read_bytes(), board_geometry
                                )
                                j_bat_marking_errors.extend(
                                    f"extracted {error}"
                                    for error in extracted_inspection["errors"]
                                )
                    if board_geometry is not None and layer in {"F.Mask", "B.Mask"}:
                        side = "front" if layer == "F.Mask" else "back"
                        mask_open_vias[side] = mask_open_via_centers(
                            board_geometry, package.read(entry)
                        )
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
        if product in {"left", "right"}:
            expected_bom = (
                build_board_bom(
                    product,
                    details["board"],
                    sha256_file(source_board),
                    board_geometry,
                )
                if board_geometry is not None
                else None
            )
            bom_details = details.get("bom", {})
            json_path = root / bom_details.get("json", "<missing-bom-json>")
            csv_path = root / bom_details.get("csv", "<missing-bom-csv>")
            if not bom_details:
                bom_errors.append("manifest product has no BOM paths")
            if expected_bom is not None:
                if not json_path.is_file():
                    bom_errors.append("board-derived BOM JSON missing")
                else:
                    try:
                        actual_bom = json.loads(json_path.read_text(encoding="utf-8"))
                    except (OSError, ValueError) as error:
                        bom_errors.append(f"BOM JSON parse failed: {error}")
                    else:
                        if actual_bom != expected_bom:
                            bom_errors.append("BOM JSON does not match source-board inventory contract")
                if not csv_path.is_file():
                    bom_errors.append("board-derived BOM CSV missing")
                elif csv_path.read_bytes() != bom_csv_bytes(expected_bom):
                    bom_errors.append("BOM CSV does not match source-board inventory contract")
        source_tenting = source_board_tenting(source_board)
        via_tenting_errors: list[str] = []
        source_vias = board_geometry.get("vias", []) if board_geometry is not None else []
        if source_vias and source_tenting != {"front": True, "back": True}:
            via_tenting_errors.append(
                f"source board tenting must be enabled on both sides, got {source_tenting}"
            )
        maximum_tented_drill = float(
            EXPECTED_JLCPCB_PROFILE["maximum_tented_via_drill_mm"]
        )
        oversized_vias = [
            [round(float(via["center"][0]), 4), round(float(via["center"][1]), 4)]
            for via in source_vias
            if float(via["diameter"]) > maximum_tented_drill + 0.0001
        ]
        if oversized_vias:
            via_tenting_errors.append(
                f"source vias exceed {maximum_tented_drill:.2f} mm tenting drill: {oversized_vias}"
            )
        for side, centers in mask_open_vias.items():
            if centers:
                via_tenting_errors.append(f"{side} solder mask opens at via centers {centers}")

        expected_jlcpcb_entries = sorted(
            item["name"]
            for item in details["files"]
            if any(item["name"].endswith(suffix) for suffix in JLCPCB_FABRICATION_SUFFIXES)
        )
        jlcpcb_entries: list[str] = []
        jlcpcb_file_hash_mismatches: list[str] = []
        jlcpcb_archive_digest = ""
        if jlcpcb_archive.is_file():
            jlcpcb_archive_digest = sha256_file(jlcpcb_archive)
            expected_hashes = {item["name"]: item["sha256"] for item in details["files"]}
            with ZipFile(jlcpcb_archive) as package:
                jlcpcb_entries = package.namelist()
                for entry in jlcpcb_entries:
                    if sha256_bytes(package.read(entry)) != expected_hashes.get(entry):
                        jlcpcb_file_hash_mismatches.append(entry)
        pcba_quote = (
            inspect_jlcpcb_pcba_quote(
                product,
                details,
                board_geometry,
                source_board,
                root,
            )
            if product in {"left", "right"}
            else None
        )
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
            "jlcpcb_archive_exists": jlcpcb_archive.is_file(),
            "jlcpcb_archive_entry_count": len(jlcpcb_entries),
            "jlcpcb_archive_sha256_matches": bool(jlcpcb_archive_digest)
            and jlcpcb_archive_digest == details.get("jlcpcb_archive_sha256"),
            "jlcpcb_nested_archive_entries": [
                entry for entry in jlcpcb_entries if "/" in entry or "\\" in entry
            ],
            "jlcpcb_unexpected_entries": sorted(
                set(jlcpcb_entries) - set(expected_jlcpcb_entries)
            ),
            "jlcpcb_missing_entries": sorted(
                set(expected_jlcpcb_entries) - set(jlcpcb_entries)
            ),
            "jlcpcb_file_hash_mismatches": jlcpcb_file_hash_mismatches,
            "file_hash_mismatches": file_hash_mismatches,
            "output_file_hash_mismatches": output_file_hash_mismatches,
            "drill_tools_mm": drill_tools,
            "source_board_via_drills_mm": source_board_via_drills(source_board),
            "source_board_tenting": source_tenting,
            "mask_open_via_centers": mask_open_vias,
            "via_tenting_errors": via_tenting_errors,
            "expected_drill_tools_mm": expected_drills,
            "drill_geometry_matches": drill_tools == expected_drills,
            "drill_source_geometry_errors": drill_source_geometry_errors,
            "gerber_layers": gerber_layers,
            "gerber_geometry_errors": gerber_geometry_errors,
            "gerber_source_geometry_errors": gerber_source_geometry_errors,
            "mounting_reference_labels": gerber_layers.get("F.Silkscreen", {}).get(
                "component_references", []
            ),
            "mounting_reference_glyphs": mounting_reference_glyphs,
            "mounting_reference_glyph_errors": mounting_reference_glyph_errors,
            "j_bat_marking_glyphs": j_bat_marking_glyphs,
            "j_bat_marking_errors": j_bat_marking_errors,
            "bottom_paste_flash_count": gerber_layers.get("B.Paste", {}).get(
                "flash_count", 0
            ),
            "bottom_paste_geometry_matches": gerber_layers.get("B.Paste", {}).get(
                "flash_count", 0
            )
            == EXPECTED_BOTTOM_PASTE_FLASHES[product],
            "bom_matches_source_board": not bom_errors if product in {"left", "right"} else None,
            "bom_errors": bom_errors,
            "pcba_quote": pcba_quote,
        }
    return {
        "requirement_ids": manifest.get("requirement_ids", []),
        "requirement_ids_match": tuple(manifest.get("requirement_ids", ())) == REQUIREMENT_IDS,
        "hash_policy": manifest.get("hash_policy"),
        "hash_policy_matches": manifest.get("hash_policy") == HASH_POLICY,
        "jlcpcb_profile": manifest.get("jlcpcb_profile"),
        "jlcpcb_profile_errors": jlcpcb_profile_errors(manifest.get("jlcpcb_profile")),
        "jlcpcb_pcba_quote_profile": manifest.get("jlcpcb_pcba_quote_profile"),
        "jlcpcb_pcba_quote_profile_errors": jlcpcb_pcba_quote_profile_errors(
            manifest.get("jlcpcb_pcba_quote_profile")
        ),
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
    if not report["requirement_ids_match"]:
        errors.append(f"requirement_ids must be {list(REQUIREMENT_IDS)!r}")
    if not report["hash_policy_matches"]:
        errors.append(f"hash policy must be {HASH_POLICY!r}")
    if report["jlcpcb_profile_errors"]:
        errors.extend(report["jlcpcb_profile_errors"])
    if report["jlcpcb_pcba_quote_profile_errors"]:
        errors.extend(report["jlcpcb_pcba_quote_profile_errors"])
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
        if not details["jlcpcb_archive_exists"]:
            errors.append(f"{product}: JLCPCB upload archive missing")
        if not details["jlcpcb_archive_sha256_matches"]:
            errors.append(f"{product}: JLCPCB upload archive SHA-256 mismatch")
        if details["jlcpcb_archive_entry_count"] != len(JLCPCB_FABRICATION_SUFFIXES):
            errors.append(
                f"{product}: JLCPCB upload archive has "
                f"{details['jlcpcb_archive_entry_count']} entries, expected "
                f"{len(JLCPCB_FABRICATION_SUFFIXES)}"
            )
        if details["jlcpcb_nested_archive_entries"]:
            errors.append(
                f"{product}: JLCPCB upload archive has nested entries "
                f"{details['jlcpcb_nested_archive_entries']}"
            )
        if details["jlcpcb_unexpected_entries"]:
            errors.append(
                f"{product}: JLCPCB upload archive has unexpected entries "
                f"{details['jlcpcb_unexpected_entries']}"
            )
        if details["jlcpcb_missing_entries"]:
            errors.append(
                f"{product}: JLCPCB upload archive is missing entries "
                f"{details['jlcpcb_missing_entries']}"
            )
        if details["jlcpcb_file_hash_mismatches"]:
            errors.append(
                f"{product}: JLCPCB upload file SHA-256 mismatches "
                f"{details['jlcpcb_file_hash_mismatches']}"
            )
        if details["via_tenting_errors"]:
            errors.append(f"{product}: via tenting {details['via_tenting_errors']}")
        if details["file_hash_mismatches"]:
            errors.append(f"{product}: file SHA-256 mismatches {details['file_hash_mismatches']}")
        if details["output_file_hash_mismatches"]:
            errors.append(
                f"{product}: extracted output SHA-256 mismatches "
                f"{details['output_file_hash_mismatches']}"
            )
        if details["gerber_geometry_errors"]:
            errors.append(f"{product}: Gerber geometry {details['gerber_geometry_errors']}")
        if details["drill_source_geometry_errors"]:
            errors.append(
                f"{product}: source/Excellon geometry {details['drill_source_geometry_errors']}"
            )
        if details["gerber_source_geometry_errors"]:
            errors.append(
                f"{product}: source/Gerber geometry {details['gerber_source_geometry_errors']}"
            )
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
        if details["j_bat_marking_errors"]:
            errors.append(
                f"{product}: J_BAT1 F.Silkscreen marking "
                f"{details['j_bat_marking_errors']}"
            )
        if product in {"left", "right"} and not details["bom_matches_source_board"]:
            errors.append(f"{product}: BOM {details['bom_errors']}")
        if product in {"left", "right"} and details["pcba_quote"]["errors"]:
            errors.append(f"{product}: JLCPCB PCBA quote {details['pcba_quote']['errors']}")
    if errors:
        raise SystemExit("FAIL: KC2 X3 V2 fabrication archives\n- " + "\n- ".join(errors))
    print(json.dumps(report, indent=2))
    print("PASS: CON-ARCH-004 draft Gerber/Excellon archives are structurally complete")


if __name__ == "__main__":
    main()
