#!/usr/bin/env python3
"""Lightweight text guard for KC2 X3 screwless board invariants.

This intentionally avoids pcbnew/KiCad imports so it can run while heavier
KiCad/Freerouting verification is paused.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

BOARD_SPECS = {
    "left": {
        "path": ROOT / "hardware/kicad/kc2_left/kc2_left.kicad_pcb",
        "expected": {
            "REG1": (63.03, 102.03),
            "REG2": (124.71, 91.03),
            "REG3": (145.40, 90.53),
            "REG4": (66.53, 122.93),
            "REG5": (109.21, 122.93),
            "REG6": (146.90, 122.93),
            "REG7": (61.52, 151.32),
            "REG8": (109.21, 151.32),
            "REG9": (137.40, 142.32),
        },
    },
    "right": {
        "path": ROOT / "hardware/kicad/kc2_right/kc2_right.kicad_pcb",
        "expected": {
            "REG1": (103.12, 84.53),
            "REG2": (141.69, 84.03),
            "REG3": (200.75, 95.53),
            "REG4": (54.38, 127.17),
            "REG5": (131.69, 125.93),
            "REG6": (200.25, 121.93),
            "REG7": (54.88, 144.57),
            "REG8": (146.19, 141.82),
            "REG9": (205.75, 130.32),
        },
    },
}

REG_FOOTPRINT = "REG_NPTH_3.0"
COORD_TOLERANCE_MM = 0.02
LABEL_DISTANCE_MAX_MM = 4.5
GR_TEXT_RE = re.compile(
    r'\(gr_text\s+"([^"]+)"\s+\(at\s+([-0-9.]+)\s+([-0-9.]+)(?:\s+[-0-9.]+)?\)\s+\(layer\s+"([^"]+)"\)',
    re.DOTALL,
)


@dataclass(frozen=True)
class Footprint:
    name: str
    reference: str
    value: str
    x: float
    y: float
    block: str


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def find_matching_paren(text: str, start: int) -> int:
    depth = 0
    in_string = False
    escaped = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return idx + 1
    raise ValueError(f"unbalanced footprint block at offset {start}")


def iter_footprint_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    pos = 0
    needle = "(footprint "
    while True:
        start = text.find(needle, pos)
        if start < 0:
            return blocks
        end = find_matching_paren(text, start)
        blocks.append(text[start:end])
        pos = end


def extract_string(block: str, pattern: str) -> str:
    match = re.search(pattern, block)
    return match.group(1) if match else ""


def parse_footprint(block: str) -> Footprint | None:
    name = extract_string(block, r'^\(footprint "([^"]+)"')
    ref = extract_string(block, r'\(property "Reference" "([^"]+)"')
    value = extract_string(block, r'\(property "Value" "([^"]+)"')
    at_match = re.search(r"\(at\s+([-0-9.]+)\s+([-0-9.]+)(?:\s+[-0-9.]+)?\)", block)
    if not (name and ref and at_match):
        return None
    return Footprint(
        name=name,
        reference=ref,
        value=value,
        x=float(at_match.group(1)),
        y=float(at_match.group(2)),
        block=block,
    )


def has_line(block: str, pattern: str) -> bool:
    return re.search(pattern, block) is not None


def check_reg_footprint(side: str, fp: Footprint, expected_xy: tuple[float, float], errors: list[str]) -> None:
    expected_x, expected_y = expected_xy
    if fp.value != REG_FOOTPRINT:
        fail(f"{side} {fp.reference}: value is {fp.value!r}, expected {REG_FOOTPRINT!r}", errors)
    if abs(fp.x - expected_x) > COORD_TOLERANCE_MM or abs(fp.y - expected_y) > COORD_TOLERANCE_MM:
        fail(
            f"{side} {fp.reference}: at ({fp.x:.3f}, {fp.y:.3f}), expected "
            f"({expected_x:.3f}, {expected_y:.3f}) +/- {COORD_TOLERANCE_MM:.2f} mm",
            errors,
        )
    required = {
        "exclude from BOM/pos": r"\(attr\s+exclude_from_pos_files\s+exclude_from_bom\)",
        "NPTH circular pad": r'\(pad\s+""\s+np_thru_hole\s+circle',
        "3.0 mm pad size": r"\(size\s+3(?:\.0+)?\s+3(?:\.0+)?\)",
        "3.0 mm drill": r"\(drill\s+3(?:\.0+)?\)",
        "mask-only layers": r'\(layers\s+"\*\.Mask"\)',
    }
    for label, pattern in required.items():
        if not has_line(fp.block, pattern):
            fail(f"{side} {fp.reference}: missing {label}", errors)


def check_board(side: str, spec: dict[str, object]) -> tuple[list[str], list[str]]:
    path = spec["path"]
    expected = spec["expected"]
    assert isinstance(path, Path)
    assert isinstance(expected, dict)
    errors: list[str] = []
    notes: list[str] = []

    if not path.exists():
        return [f"{side}: board file missing: {path}"], notes

    text = path.read_text(encoding="utf-8")
    if not re.search(r"\(thickness\s+1\.6\)", text):
        fail(f"{side}: board thickness is not 1.6 mm", errors)
    for forbidden in ("M2_NPTH_2.2", "MountingHole_2.2mm_M2", 'property "Reference" "H'):
        if forbidden in text:
            fail(f"{side}: forbidden screw-mount marker remains: {forbidden}", errors)
    for forbidden in ("Stabilizer", "STAB"):
        if forbidden in text:
            fail(f"{side}: forbidden stabilizer marker remains: {forbidden}", errors)

    footprints = [fp for block in iter_footprint_blocks(text) if (fp := parse_footprint(block))]
    reg_footprints = {fp.reference: fp for fp in footprints if fp.name == REG_FOOTPRINT}
    expected_refs = set(expected)
    found_refs = set(reg_footprints)
    if found_refs != expected_refs:
        fail(
            f"{side}: REG refs mismatch, found {sorted(found_refs)}, expected {sorted(expected_refs)}",
            errors,
        )
    if len(reg_footprints) != 9:
        fail(f"{side}: expected 9 {REG_FOOTPRINT} footprints, found {len(reg_footprints)}", errors)

    for ref, xy in expected.items():
        fp = reg_footprints.get(ref)
        if fp is None:
            continue
        assert isinstance(xy, tuple)
        check_reg_footprint(side, fp, xy, errors)

    labels: dict[str, list[tuple[float, float, str]]] = {}
    for match in GR_TEXT_RE.finditer(text):
        label, raw_x, raw_y, layer = match.groups()
        if layer not in ("F.SilkS", "B.SilkS"):
            continue
        if not re.fullmatch(r"H[1-9]", label):
            continue
        labels.setdefault(label, []).append((float(raw_x), float(raw_y), layer))

    for idx, ref in enumerate(sorted(expected_refs, key=lambda value: int(value.removeprefix("REG"))), start=1):
        fp = reg_footprints.get(ref)
        if fp is None:
            continue
        label = f"H{idx}"
        candidates = labels.get(label, [])
        if not candidates:
            fail(f"{side}: missing visible {label} gr_text label near {ref}", errors)
            continue
        if all(((fp.x - x) ** 2 + (fp.y - y) ** 2) ** 0.5 > LABEL_DISTANCE_MAX_MM for x, y, _layer in candidates):
            fail(f"{side}: {label} gr_text label is not within {LABEL_DISTANCE_MAX_MM:.1f} mm of {ref}", errors)

    xs = sorted(fp.x for fp in reg_footprints.values())
    ys = sorted(fp.y for fp in reg_footprints.values())
    if len(xs) == 9 and len(ys) == 9:
        notes.append(
            f"{side}: 9 REG holes span x={xs[0]:.2f}..{xs[-1]:.2f} mm, "
            f"y={ys[0]:.2f}..{ys[-1]:.2f} mm"
        )

    return errors, notes


def main() -> int:
    all_errors: list[str] = []
    all_notes: list[str] = []
    for side, spec in BOARD_SPECS.items():
        errors, notes = check_board(side, spec)
        all_errors.extend(errors)
        all_notes.extend(notes)

    if all_notes:
        for note in all_notes:
            print(note)
    if all_errors:
        print("FAIL: KC2 X3 screwless board text guard found blockers:")
        for error in all_errors:
            print(f"- {error}")
        print("Note: this lightweight guard does not replace KiCad DRC, connectivity, preflight, or fabrication ZIP checks.")
        return 1
    print("PASS: KC2 X3 screwless board text guard")
    print("Checked: 1.6 mm PCB thickness, no M2/stabilizer markers, REG1-REG9 per half, 3.0 mm mask-only NPTH footprints, visible H1-H9 labels.")
    print("Note: KiCad DRC/connectivity/preflight/fabrication ZIP checks are still required before ordering.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
