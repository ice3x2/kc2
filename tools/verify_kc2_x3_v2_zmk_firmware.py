"""Verify the isolated KC2 X3 V2 ZMK shield against the 71-key KiCad boards.

Requirement: CON-ARCH-004 AC-5 and AC-7.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SHIELD_DIR = ROOT / "firmware" / "kc2_zmk" / "boards" / "shields" / "kc2_x3_v2"
BOARD_PATHS = {
    "left": ROOT / "hardware" / "kicad" / "draft" / "x3-v2" / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb",
    "right": ROOT / "hardware" / "kicad" / "draft" / "x3-v2" / "kc2_right-x3-v2" / "kc2_right-x3-v2.kicad_pcb",
}
EXPECTED_COUNTS = {"left": 32, "right": 39}
EXPECTED_PINS = {
    "left": {
        "cols": [(0, 20), (0, 24), (0, 22), (1, 0), (0, 11), (1, 4), (1, 6)],
        "rows": [(0, 9), (0, 10), (1, 11), (1, 13), (1, 15)],
    },
    "right": {
        "cols": [(1, 6), (0, 9), (0, 10), (1, 11), (1, 13), (1, 15), (0, 2), (0, 29)],
        "rows": [(0, 20), (0, 22), (0, 24), (0, 17), (0, 11)],
    },
}

EXPECTED_DEFAULT_BINDINGS = [
    "&kp GRAVE", "&kp N1", "&kp N2", "&kp N3", "&kp N4", "&kp N5", "&kp N6",
    "&kp N7", "&kp N8", "&kp N9", "&kp N0", "&kp MINUS", "&kp EQUAL", "&kp BSPC", "&kp DEL",
    "&kp TAB", "&kp Q", "&kp W", "&kp E", "&kp R", "&kp T",
    "&kp Y", "&kp U", "&kp I", "&kp O", "&kp P", "&kp LBKT", "&kp RBKT", "&kp BSLH",
    "&kp CAPS", "&kp A", "&kp S", "&kp D", "&kp F", "&kp G",
    "&kp H", "&kp J", "&kp K", "&kp L", "&kp SEMI", "&kp SQT", "&kp RET", "&kp RET",
    "&kp LSHFT", "&kp LSHFT", "&kp Z", "&kp X", "&kp C", "&kp V", "&kp B",
    "&kp N", "&kp M", "&kp COMMA", "&kp DOT", "&kp FSLH", "&kp RSHFT", "&kp UP", "&mo 1",
    "&kp LCTRL", "&kp LGUI", "&kp LALT", "&mo 1", "&kp SPACE", "&kp SPACE",
    "&kp B", "&kp SPACE", "&kp RALT", "&kp RCTRL", "&kp LEFT", "&kp DOWN", "&kp RIGHT",
]
EXPECTED_FN_BINDINGS = [
    "&kp ESC", "&kp F1", "&kp F2", "&kp F3", "&kp F4", "&kp F5", "&kp F6",
    "&kp F7", "&kp F8", "&kp F9", "&kp F10", "&kp F11", "&kp F12", "&trans", "&kp PSCRN",
    "&kp BSPC", "&kp DEL", "&kp UP", "&trans", "&trans", "&trans",
    *("&trans" for _ in range(8)),
    "&kp RALT", "&kp LEFT", "&kp DOWN", "&kp RIGHT", "&trans", "&trans",
    *("&trans" for _ in range(8)),
    "&kp LSHFT", "&kp LSHFT", "&trans", "&trans", "&trans", "&trans", "&bt BT_CLR",
    "&trans", "&trans", "&trans", "&trans", "&trans", "&trans", "&kp PG_UP", "&mo 2",
    "&trans", "&trans", "&trans", "&mo 2", "&kp ESC", "&kp ESC",
    "&trans", "&trans", "&trans", "&trans", "&kp HOME", "&kp PG_DN", "&kp END",
]
EXPECTED_FN2_BINDINGS = [
    "&out OUT_TOG", "&bt BT_SEL 0", "&bt BT_SEL 1", "&bt BT_SEL 2", "&bt BT_SEL 3", "&bt BT_SEL 4", "&trans",
    *("&trans" for _ in range(8)),
    "&out OUT_USB", "&out OUT_BLE", "&trans", "&trans", "&trans", "&trans",
    *("&trans" for _ in range(8)),
    *("&trans" for _ in range(14)),
    "&bt BT_CLR", *("&trans" for _ in range(14)),
    *("&trans" for _ in range(13)),
]
EXPECTED_LAYERS = {
    "default_layer": EXPECTED_DEFAULT_BINDINGS,
    "fn_layer": EXPECTED_FN_BINDINGS,
    "fn_layer2": EXPECTED_FN2_BINDINGS,
}
EXPECTED_METADATA = {
    "variant": "kc2-x3-v2",
    "requirement_id": "CON-ARCH-004",
    "layout": "71-key-v4-no-stabilizer",
    "key_count": {"left": 32, "right": 39, "total": 71},
    "matrix": {"rows": 5, "left_columns": 7, "right_columns": 8, "transform_columns": 15},
    "supported_assembly": ["choc-v2-bottom-socket", "mx-direct-solder"],
    "unsupported_assembly": ["choc-v1", "choc-v2-direct-solder", "mx-hotswap"],
    "controller": "nice-nano-v2-socket-15.24-mm-row-spacing",
    "compact_controller": True,
    "carrier_battery_nets": False,
    "battery_leads": "direct-to-nice-nano-b-plus-b-minus",
    "fn_position": "immediately-right-of-up",
    "bottom_row_right_fn": False,
}


def parse_bindings(source: str) -> list[str]:
    match = re.search(r"bindings\s*=\s*<(.*?)>;", source, re.DOTALL)
    if match is None:
        raise ValueError("No bindings property found")
    return [
        " ".join(binding.split())
        for binding in re.findall(r"&[A-Za-z_][A-Za-z0-9_]*(?:\s+[-A-Za-z0-9_]+)*", match.group(1))
    ]


def parse_layer_bindings(source: str, layer_name: str) -> list[str]:
    match = re.search(rf"\b{re.escape(layer_name)}\s*\{{(.*?)\n\s*\}};", source, re.DOTALL)
    if match is None:
        raise ValueError(f"Missing {layer_name} layer")
    return parse_bindings(match.group(1))


def parse_transform_positions(source: str) -> list[tuple[int, int]]:
    match = re.search(r"map\s*=\s*<(.*?)>;", source, re.DOTALL)
    if match is None:
        raise ValueError("No matrix-transform map property found")
    return [(int(row), int(col)) for row, col in re.findall(r"RC\(\s*(\d+)\s*,\s*(\d+)\s*\)", match.group(1))]


def parse_gpio_list(source: str, property_name: str) -> list[tuple[int, int]]:
    match = re.search(rf"\b{re.escape(property_name)}\s*=\s*(.*?);", source, re.DOTALL)
    if match is None:
        raise ValueError(f"Missing {property_name} property")
    return [(int(port), int(pin)) for port, pin in re.findall(r"<&gpio(\d+)\s+(\d+)", match.group(1))]


def read_transform() -> list[tuple[int, int]]:
    return parse_transform_positions((SHIELD_DIR / "kc2_x3_v2.dtsi").read_text(encoding="utf-8"))


def read_layer(layer_name: str) -> list[str]:
    return parse_layer_bindings((SHIELD_DIR / "kc2_x3_v2.keymap").read_text(encoding="utf-8"), layer_name)


def read_overlay_pins(side: str) -> dict[str, list[tuple[int, int]]]:
    source = (SHIELD_DIR / f"kc2_x3_v2_{side}.overlay").read_text(encoding="utf-8")
    return {"cols": parse_gpio_list(source, "col-gpios"), "rows": parse_gpio_list(source, "row-gpios")}


def read_variant_metadata() -> dict[str, object]:
    return json.loads((SHIELD_DIR / "kc2_x3_v2_variant.json").read_text(encoding="utf-8"))


def positions_for_half(transform: Iterable[tuple[int, int]], side: str) -> list[tuple[int, int]]:
    if side == "left":
        return [(row, col) for row, col in transform if col < 7]
    if side == "right":
        return [(row, col - 7) for row, col in transform if col >= 7]
    raise ValueError(f"Unknown side: {side}")


def kicad_python_path(requested: str | None) -> Path:
    candidates: list[Path] = []
    if requested:
        candidates.append(Path(requested))
    if os.environ.get("KICAD_PYTHON"):
        candidates.append(Path(os.environ["KICAD_PYTHON"]))
    program_files = Path(os.environ.get("ProgramFiles", r"C:\\Program Files"))
    candidates.extend(program_files / "KiCad" / version / "bin" / "python.exe" for version in ("10.0", "9.0", "8.0"))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("KiCad Python was not found; pass --kicad-python or set KICAD_PYTHON")


KICAD_MATRIX_EXTRACTOR = r'''
import json
import re
import sys
import pcbnew

board = pcbnew.LoadBoard(sys.argv[1])
footprints = {footprint.GetReference(): footprint for footprint in board.GetFootprints()}
matrix = []
for reference, switch in footprints.items():
    match = re.fullmatch(r"SW(\d+)", reference)
    if match is None:
        continue
    diode = footprints.get(f"D{match.group(1)}")
    switch_pad = switch.FindPadByNumber("1")
    diode_pad = diode.FindPadByNumber("1") if diode else None
    matrix.append({
        "switch": int(match.group(1)),
        "column": switch_pad.GetNetname() if switch_pad else "",
        "row": diode_pad.GetNetname() if diode_pad else "",
    })
print(json.dumps(sorted(matrix, key=lambda item: item["switch"])))
'''


def extract_board_positions(board_path: Path, kicad_python: Path, side: str) -> list[tuple[int, int]]:
    result = subprocess.run(
        [str(kicad_python), "-c", KICAD_MATRIX_EXTRACTOR, str(board_path)],
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"KiCad extraction failed for {board_path}: {result.stderr.strip()}")
    try:
        entries = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"KiCad extraction returned invalid JSON for {board_path}: {result.stdout!r}") from error
    if len(entries) != EXPECTED_COUNTS[side]:
        raise ValueError(f"{side} board has {len(entries)} matrix switches, expected {EXPECTED_COUNTS[side]}")

    col_prefix = "L_COL" if side == "left" else "R_COL"
    row_prefix = "L_ROW" if side == "left" else "R_ROW"
    positions: list[tuple[int, int]] = []
    for expected_ref, entry in enumerate(entries, start=1):
        if entry["switch"] != expected_ref:
            raise ValueError(f"{side} switch sequence expected SW{expected_ref}, found SW{entry['switch']}")
        col_match = re.fullmatch(rf"{col_prefix}(\d+)", entry["column"])
        row_match = re.fullmatch(rf"{row_prefix}(\d+)", entry["row"])
        if col_match is None or row_match is None:
            raise ValueError(f"{side} SW{expected_ref} has unexpected nets {entry['row']!r}/{entry['column']!r}")
        positions.append((int(row_match.group(1)), int(col_match.group(1))))
    return positions


def verify(kicad_python: Path) -> list[str]:
    errors: list[str] = []
    try:
        transform = read_transform()
    except (OSError, ValueError) as error:
        return [f"Cannot read V2 matrix transform: {error}"]
    if len(transform) != 71:
        errors.append(f"V2 matrix transform contains {len(transform)} positions, expected 71")
    if len(set(transform)) != len(transform):
        errors.append("V2 matrix transform contains duplicate positions")
    if any(row not in range(5) or col not in range(15) for row, col in transform):
        errors.append("V2 matrix transform contains a position outside its 5x15 domain")

    try:
        for layer_name, expected in EXPECTED_LAYERS.items():
            actual = read_layer(layer_name)
            if actual != expected:
                errors.append(f"{layer_name} bindings do not match the KC2 X3 V2 behavior model")
            if len(actual) != 71:
                errors.append(f"{layer_name} has {len(actual)} bindings, expected 71")
    except (OSError, ValueError) as error:
        errors.append(f"Cannot read V2 keymap: {error}")

    try:
        metadata = read_variant_metadata()
        if metadata != EXPECTED_METADATA:
            errors.append("V2 variant metadata does not match the CON-ARCH-004 identity and assembly contract")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"Cannot read V2 variant metadata: {error}")

    for side in ("left", "right"):
        try:
            if read_overlay_pins(side) != EXPECTED_PINS[side]:
                errors.append(f"{side} V2 overlay GPIO matrix does not match the board pin assignment")
            board_positions = extract_board_positions(BOARD_PATHS[side], kicad_python, side)
            transform_positions = positions_for_half(transform, side)
            if transform_positions != board_positions:
                errors.append(f"{side} V2 matrix-transform order does not match KiCad SW reference/matrix order")
        except (OSError, RuntimeError, ValueError) as error:
            errors.append(f"Cannot verify {side} V2 matrix: {error}")

    try:
        right_overlay = (SHIELD_DIR / "kc2_x3_v2_right.overlay").read_text(encoding="utf-8")
        if not re.search(r"&kc2_x3_v2_transform\s*\{.*?col-offset\s*=\s*<7>;", right_overlay, re.DOTALL):
            errors.append("right V2 overlay does not declare the required transform column offset of 7")
        defconfig = (SHIELD_DIR / "Kconfig.defconfig").read_text(encoding="utf-8")
        if "SHIELD_KC2_X3_V2_LEFT" not in defconfig or "ZMK_SPLIT_ROLE_CENTRAL" not in defconfig:
            errors.append("V2 left shield is not declared as the split central role")
    except OSError as error:
        errors.append(f"Cannot verify V2 split configuration: {error}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kicad-python", help="Path to KiCad's bundled python.exe")
    args = parser.parse_args()
    try:
        errors = verify(kicad_python_path(args.kicad_python))
    except FileNotFoundError as error:
        errors = [str(error)]
    if errors:
        print("CON-ARCH-004 V2 firmware verification failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("CON-ARCH-004 V2 firmware verification passed: 71 keys (32 left, 39 right).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
