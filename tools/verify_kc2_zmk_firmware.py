"""Verify KC2 X3 ZMK firmware against the generated KiCad matrix boards.

Requirement: CON-ARCH-005
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
MODULE_DIR = ROOT / "firmware" / "kc2_zmk"
SHIELD_DIR = MODULE_DIR / "boards" / "shields" / "kc2"
BOARD_PATHS = {
    "left": ROOT / "hardware" / "kicad" / "kc2_left" / "kc2_left.kicad_pcb",
    "right": ROOT / "hardware" / "kicad" / "kc2_right" / "kc2_right.kicad_pcb",
}
EXPECTED_PINS = {
    "left": {
        "cols": [(0, 20), (0, 24), (0, 22), (1, 0), (0, 11), (1, 4), (1, 6)],
        "rows": [(0, 9), (0, 10), (1, 11), (1, 13), (1, 15)],
    },
    "right": {
        "cols": [(1, 6), (0, 9), (0, 10), (1, 11), (1, 13), (1, 15), (0, 2), (0, 31), (0, 29)],
        "rows": [(0, 20), (0, 22), (0, 24), (0, 17), (0, 11)],
    },
}

DEFAULT_BINDINGS = [
    "&kp GRAVE", "&kp N1", "&kp N2", "&kp N3", "&kp N4", "&kp N5", "&kp N6",
    "&kp N7", "&kp N8", "&kp N9", "&kp N0", "&kp MINUS", "&kp EQUAL", "&kp BSPC", "&kp BSPC", "&kp DEL",
    "&kp TAB", "&kp Q", "&kp W", "&kp E", "&kp R", "&kp T",
    "&kp Y", "&kp U", "&kp I", "&kp O", "&kp P", "&kp LBKT", "&kp RBKT", "&kp BSLH", "&kp HOME",
    "&kp CAPS", "&kp A", "&kp S", "&kp D", "&kp F", "&kp G",
    "&kp H", "&kp J", "&kp K", "&kp L", "&kp SEMI", "&kp SQT", "&kp RET", "&kp RET", "&kp PG_UP",
    "&kp LSHFT", "&kp LSHFT", "&kp Z", "&kp X", "&kp C", "&kp V", "&kp B",
    "&kp N", "&kp M", "&kp COMMA", "&kp DOT", "&kp FSLH", "&kp RSHFT", "&kp RSHFT", "&kp RSHFT", "&kp PG_DN",
    "&kp LCTRL", "&kp LGUI", "&kp LALT", "&mo 1", "&kp SPACE", "&kp SPACE",
    "&kp B", "&kp SPACE", "&kp SPACE", "&kp RALT", "&mo 1", "&kp RCTRL", "&kp LEFT", "&kp DOWN", "&kp RIGHT",
]
FN_BINDINGS = [
    "&kp ESC", "&kp F1", "&kp F2", "&kp F3", "&kp F4", "&kp F5", "&kp F6",
    "&kp F7", "&kp F8", "&kp F9", "&kp F10", "&kp F11", "&kp F12", "&trans", "&trans", "&kp PSCRN",
    "&kp BSPC", "&kp DEL", "&kp UP", "&trans", "&trans", "&trans",
    "&trans", "&trans", "&trans", "&trans", "&trans", "&trans", "&trans", "&trans", "&trans",
    "&kp RALT", "&kp LEFT", "&kp DOWN", "&kp RIGHT", "&trans", "&trans",
    "&trans", "&trans", "&trans", "&trans", "&trans", "&trans", "&trans", "&trans", "&trans",
    "&kp LSHFT", "&kp LSHFT", "&trans", "&trans", "&trans", "&trans", "&bt BT_CLR",
    "&trans", "&trans", "&trans", "&trans", "&trans", "&trans", "&mo 2", "&kp PG_UP", "&trans",
    "&trans", "&trans", "&trans", "&mo 2", "&kp ESC", "&kp ESC",
    "&trans", "&trans", "&trans", "&trans", "&mo 2", "&trans", "&kp HOME", "&kp PG_DN", "&kp END",
]
FN2_BINDINGS = [
    "&out OUT_TOG", "&bt BT_SEL 0", "&bt BT_SEL 1", "&bt BT_SEL 2", "&bt BT_SEL 3", "&bt BT_SEL 4", "&trans",
    *(["&trans"] * 8), "&kc2_power",
    "&out OUT_USB", "&out OUT_BLE", "&trans", "&trans", "&trans", "&trans",
    *(["&trans"] * 9),
    *(["&trans"] * 6),
    *(["&trans"] * 9),
    "&bt BT_CLR", "&trans", "&trans", "&trans", "&trans", "&trans", "&trans",
    *(["&trans"] * 9),
    *(["&trans"] * 4), "&kc2_power", "&trans",
    *(["&trans"] * 9),
]
EXPECTED_LAYERS = {
    "default_layer": DEFAULT_BINDINGS,
    "fn_layer": FN_BINDINGS,
    "fn_layer2": FN2_BINDINGS,
}
SOFT_OFF_SWITCHES = {"left": 31, "right": 9}
RIGHT_DEFAULT_SWITCH_BINDINGS = {34: "&kp RSHFT", 35: "&kp RSHFT"}


def parse_bindings(source: str) -> list[str]:
    """Return ZMK bindings as complete behavior expressions in source order."""
    match = re.search(r"bindings\s*=\s*<(.*?)>;", source, re.DOTALL)
    if match is None:
        raise ValueError("No bindings property found")
    return [" ".join(binding.split()) for binding in re.findall(r"&[A-Za-z_][A-Za-z0-9_]*(?:\s+[-A-Za-z0-9_]+)*", match.group(1))]


def parse_transform_positions(source: str) -> list[tuple[int, int]]:
    """Return (row, column) positions from the matrix-transform map property."""
    match = re.search(r"map\s*=\s*<(.*?)>;", source, re.DOTALL)
    if match is None:
        raise ValueError("No matrix-transform map property found")
    return [(int(row), int(col)) for row, col in re.findall(r"RC\(\s*(\d+)\s*,\s*(\d+)\s*\)", match.group(1))]


def parse_layer_bindings(source: str, layer_name: str) -> list[str]:
    match = re.search(rf"\b{re.escape(layer_name)}\s*\{{(.*?)\n\s*\}};", source, re.DOTALL)
    if match is None:
        raise ValueError(f"Missing {layer_name} layer")
    return parse_bindings(match.group(1))


def parse_gpio_list(source: str, property_name: str) -> list[tuple[int, int]]:
    match = re.search(rf"\b{re.escape(property_name)}\s*=\s*(.*?);", source, re.DOTALL)
    if match is None:
        raise ValueError(f"Missing {property_name} property")
    return [(int(port), int(pin)) for port, pin in re.findall(r"<&gpio(\d+)\s+(\d+)", match.group(1))]


def has_matrix_soft_off_waker(source: str) -> bool:
    """Return whether an overlay registers kscan0 as a soft-off wake source."""
    match = re.search(
        r"\bsoft_off_wakers\s*:\s*soft_off_wakers\s*\{(.*?)\};",
        source,
        re.DOTALL,
    )
    if match is None:
        return False
    node = match.group(1)
    return (
        re.search(r'compatible\s*=\s*"zmk,soft-off-wakeup-sources"\s*;', node) is not None
        and re.search(r"wakeup-sources\s*=\s*<&kscan0>\s*;", node) is not None
    )


def has_soft_off_config(source: str) -> bool:
    """Return whether the shield enables ZMK soft-off for both halves."""
    return re.search(
        r"config\s+ZMK_PM_SOFT_OFF\s+default\s+y",
        source,
        re.DOTALL,
    ) is not None


def has_status_led_implementation(source: str) -> bool:
    """Return whether the KC2 status LED source covers power and pairing feedback."""
    required_tokens = (
        "GPIO_DT_SPEC_GET(DT_NODELABEL(blue_led), gpios)",
        "KC2_POWER_FLASH_MS 150",
        "KC2_PAIRING_BLINK_MS 100",
        "zmk_pm_soft_off()",
        "zmk_ble_active_profile_is_open()",
        "zmk_ble_active_profile_is_connected()",
        "CONFIG_ZMK_SPLIT_ROLE_CENTRAL",
        "BEHAVIOR_LOCALITY_GLOBAL",
        "ZMK_SUBSCRIPTION(kc2_status_led, zmk_ble_active_profile_changed)",
    )
    return all(token in source for token in required_tokens)


def kicad_python_path(requested: str | None) -> Path:
    candidates: list[Path] = []
    if requested:
        candidates.append(Path(requested))
    if os.environ.get("KICAD_PYTHON"):
        candidates.append(Path(os.environ["KICAD_PYTHON"]))
    program_files = Path(os.environ.get("ProgramFiles", r"C:\\Program Files"))
    candidates.extend(
        program_files / "KiCad" / version / "bin" / "python.exe"
        for version in ("10.0", "9.0", "8.0")
    )
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

    col_prefix = "L_COL" if side == "left" else "R_COL"
    row_prefix = "L_ROW" if side == "left" else "R_ROW"
    expected_count = 32 if side == "left" else 45
    if len(entries) != expected_count:
        raise ValueError(f"{side} board has {len(entries)} matrix switches, expected {expected_count}")

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


def expected_transform_positions(transform: Iterable[tuple[int, int]], side: str) -> list[tuple[int, int]]:
    if side == "left":
        return [(row, col) for row, col in transform if col < 7]
    return [(row, col - 7) for row, col in transform if col >= 7]


def transform_index_for_switch(
    transform: list[tuple[int, int]],
    board_positions: list[tuple[int, int]],
    side: str,
    switch_number: int,
) -> int:
    """Return the global keymap index for a side-local numbered switch."""
    row, col = board_positions[switch_number - 1]
    global_position = (row, col if side == "left" else col + 7)
    return transform.index(global_position)


def verify(kicad_python: Path) -> list[str]:
    errors: list[str] = []
    actual_layers: dict[str, list[str]] = {}
    dtsi_path = SHIELD_DIR / "kc2.dtsi"
    keymap_path = SHIELD_DIR / "kc2.keymap"
    try:
        transform = parse_transform_positions(dtsi_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        return [f"Cannot read matrix transform: {error}"]
    if len(transform) != 77:
        errors.append(f"Matrix transform contains {len(transform)} positions, expected 77")

    try:
        kconfig_source = (SHIELD_DIR / "Kconfig.defconfig").read_text(encoding="utf-8")
        if not has_soft_off_config(kconfig_source):
            errors.append("shield Kconfig does not enable ZMK_PM_SOFT_OFF")
    except OSError as error:
        errors.append(f"Cannot read shield Kconfig: {error}")

    try:
        status_led_source = (SHIELD_DIR / "src" / "kc2_status_led.c").read_text(encoding="utf-8")
        if not has_status_led_implementation(status_led_source):
            errors.append("KC2 status LED source does not cover power-off and Bluetooth registration feedback")
    except OSError as error:
        errors.append(f"Cannot read KC2 status LED source: {error}")

    try:
        shield_cmake = (SHIELD_DIR / "CMakeLists.txt").read_text(encoding="utf-8")
        if "src/kc2_status_led.c" not in shield_cmake:
            errors.append("shield CMake does not compile kc2_status_led.c")
        module_manifest = (MODULE_DIR / "zephyr" / "module.yml").read_text(encoding="utf-8")
        if "dts_root: ." not in module_manifest:
            errors.append("KC2 module manifest does not expose its devicetree bindings")
        binding_source = (MODULE_DIR / "dts" / "bindings" / "behaviors" / "kc2,behavior-power-off.yaml").read_text(encoding="utf-8")
        if 'compatible: "kc2,behavior-power-off"' not in binding_source:
            errors.append("KC2 power-off behavior binding has the wrong compatible")
        vendor_prefixes = (MODULE_DIR / "dts" / "bindings" / "vendor-prefixes.txt").read_text(encoding="utf-8")
        if re.search(r"^kc2\tKC2 Project$", vendor_prefixes, re.MULTILINE) is None:
            errors.append("KC2 devicetree vendor prefix is not registered")
    except OSError as error:
        errors.append(f"Cannot read KC2 status LED build metadata: {error}")

    try:
        keymap_source = keymap_path.read_text(encoding="utf-8")
        for layer_name, expected in EXPECTED_LAYERS.items():
            actual = parse_layer_bindings(keymap_source, layer_name)
            actual_layers[layer_name] = actual
            if actual != expected:
                errors.append(f"{layer_name} bindings do not match the KC2 X3 behavior model")
            if len(actual) != 77:
                errors.append(f"{layer_name} has {len(actual)} bindings, expected 77")
    except (OSError, ValueError) as error:
        errors.append(f"Cannot read keymap: {error}")

    for side in ("left", "right"):
        overlay_path = SHIELD_DIR / f"kc2_{side}.overlay"
        try:
            overlay = overlay_path.read_text(encoding="utf-8")
            actual_pins = {
                "cols": parse_gpio_list(overlay, "col-gpios"),
                "rows": parse_gpio_list(overlay, "row-gpios"),
            }
            if actual_pins != EXPECTED_PINS[side]:
                errors.append(f"{side} overlay GPIO matrix does not match the KC2 board pin assignment")
            if not has_matrix_soft_off_waker(overlay):
                errors.append(f"{side} overlay does not register kscan0 as a soft-off wake source")
            board_positions = extract_board_positions(BOARD_PATHS[side], kicad_python, side)
            transform_positions = expected_transform_positions(transform, side)
            if transform_positions != board_positions:
                errors.append(f"{side} matrix-transform order does not match KiCad switch row/column order")
            switch_number = SOFT_OFF_SWITCHES[side]
            soft_off_index = transform_index_for_switch(transform, board_positions, side, switch_number)
            if actual_layers.get("fn_layer2", [])[soft_off_index:soft_off_index + 1] != ["&kc2_power"]:
                errors.append(f"{side} D{switch_number} is not the LED-confirmed power-off behavior on Fn2")
            if side == "right" and actual_layers.get("default_layer", [])[soft_off_index:soft_off_index + 1] != ["&kp DEL"]:
                errors.append("right D9 is not the default-layer Delete position")
            if side == "right":
                default_bindings = actual_layers.get("default_layer", [])
                for switch_number, expected_binding in RIGHT_DEFAULT_SWITCH_BINDINGS.items():
                    binding_index = transform_index_for_switch(
                        transform, board_positions, side, switch_number
                    )
                    actual_binding = default_bindings[binding_index : binding_index + 1]
                    if actual_binding != [expected_binding]:
                        errors.append(
                            f"right D{switch_number} default binding is not {expected_binding}"
                        )
        except (OSError, RuntimeError, ValueError, FileNotFoundError) as error:
            errors.append(f"Cannot verify {side} matrix: {error}")
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
        print("CON-ARCH-005 firmware verification failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("CON-ARCH-005 firmware verification passed: 77 keys (32 left, 45 right).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
