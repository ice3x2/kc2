"""Verify the isolated KC2 X3 V2 ZMK shield against the 70-key KiCad boards.

Requirement: CON-ARCH-004 AC-5 and AC-7.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
from typing import Iterable, Mapping

if __package__:
    from tools.canonical_hash import HASH_POLICY, sha256_file
else:
    from canonical_hash import HASH_POLICY, sha256_file


ROOT = Path(__file__).resolve().parents[1]
SHIELD_DIR = ROOT / "firmware" / "kc2_zmk" / "boards" / "shields" / "kc2_x3_v2"
BUILD_EVIDENCE_PATH = SHIELD_DIR / "kc2_x3_v2_build_evidence.json"
BUILD_SOURCE_PATHS = (
    Path("firmware/kc2_zmk/zephyr/module.yml"),
    Path("firmware/kc2_zmk/boards/shields/kc2_x3_v2/CMakeLists.txt"),
    Path("firmware/kc2_zmk/boards/shields/kc2_x3_v2/Kconfig.defconfig"),
    Path("firmware/kc2_zmk/boards/shields/kc2_x3_v2/Kconfig.shield"),
    Path("firmware/kc2_zmk/boards/shields/kc2_x3_v2/kc2_x3_v2.dtsi"),
    Path("firmware/kc2_zmk/boards/shields/kc2_x3_v2/kc2_x3_v2.keymap"),
    Path("firmware/kc2_zmk/boards/shields/kc2_x3_v2/kc2_x3_v2_left.overlay"),
    Path("firmware/kc2_zmk/boards/shields/kc2_x3_v2/kc2_x3_v2_right.overlay"),
)
BUILD_METADATA_PATHS = (
    Path("firmware/kc2_zmk/boards/shields/kc2_x3_v2/kc2_x3_v2.zmk.yml"),
    Path("firmware/kc2_zmk/boards/shields/kc2_x3_v2/kc2_x3_v2_variant.json"),
)
LOCAL_ARTIFACT_PATHS = {
    "left": ROOT / "firmware" / "out" / "kc2_x3_v2_left.uf2",
    "right": ROOT / "firmware" / "out" / "kc2_x3_v2_right.uf2",
}
EXPECTED_BUILD_TOOLCHAIN = {
    "zmk_version": "v0.3.0",
    "zmk_commit": "edf5c0814fd3ea202e43aad2d68fd32e882a518c",
    "zephyr_sdk_version": "0.16.9",
    "board": "nice_nano_v2",
    "extra_module": "firmware/kc2_zmk",
}
EXPECTED_BUILD_ARTIFACTS = {
    "left": {
        "shield": "kc2_x3_v2_left",
        "build_directory": "firmware/build/kc2_x3_v2_left",
        "output": "firmware/out/kc2_x3_v2_left.uf2",
        "size_bytes": 423424,
        "sha256": "86c9a777c29d7f1c6f178d8df8aa4f5ecf8e8f75b7fc3daa1ca4842e761c2561",
        "uf2_block_count": 827,
    },
    "right": {
        "shield": "kc2_x3_v2_right",
        "build_directory": "firmware/build/kc2_x3_v2_right",
        "output": "firmware/out/kc2_x3_v2_right.uf2",
        "size_bytes": 340992,
        "sha256": "92c8dd1175de2c19505d3ca3487bcc8baa1d03a581c6de13c191ca63743e9b35",
        "uf2_block_count": 666,
    },
}
EXPECTED_HARDWARE_COMPATIBILITY = {
    "matrix_diode": {
        "manufacturer": "Diodes Incorporated",
        "mpn": "1N4148W-13-F",
        "package": "SOD-123",
        "datasheet": "DS30086 Rev. 31-2",
        "quantity": 70,
        "assembly_side": "B.Cu",
        "bottom_view": "mirrored",
        "pad_1": "cathode-row",
        "pad_2": "anode-per-key-switch",
    },
    "matrix_contract": {
        "diode_direction": "col2row",
        "column_drive": "active-high",
        "row_input": "active-high-pull-down",
    },
    "scan_timing": {
        "recorded_wait_before_inputs_us": 0,
        "recorded_wait_between_outputs_us": 0,
        "firmware_source_changed_for_1n4148w": False,
        "change_policy": "physical-coupon-required-before-scan-delay-change",
        "physical_stress": {
            "status": "pending",
            "supply_volts": [3.0, 3.3],
            "patterns": ["maximum-same-row", "maximum-same-column"],
        },
    },
}
EXPECTED_UF2_MAGIC = {
    "start0_le_u32": "0x0a324655",
    "start1_le_u32": "0x9e5d5157",
    "end_le_u32": "0x0ab16f30",
    "block_size_bytes": 512,
}
BOARD_PATHS = {
    "left": ROOT / "hardware" / "kicad" / "draft" / "x3-v2" / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb",
    "right": ROOT / "hardware" / "kicad" / "draft" / "x3-v2" / "kc2_right-x3-v2" / "kc2_right-x3-v2.kicad_pcb",
}
EXPECTED_COUNTS = {"left": 31, "right": 39}
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
    "&kp LCTRL", "&mo 1", "&kp LALT", "&kp SPACE", "&kp SPACE",
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
    "&trans", "&mo 2", "&trans", "&kp ESC", "&kp ESC",
    "&trans", "&trans", "&trans", "&trans", "&kp HOME", "&kp PG_DN", "&kp END",
]
EXPECTED_FN2_BINDINGS = [
    "&out OUT_TOG", "&bt BT_SEL 0", "&bt BT_SEL 1", "&bt BT_SEL 2", "&bt BT_SEL 3", "&bt BT_SEL 4", "&trans",
    *("&trans" for _ in range(8)),
    "&out OUT_USB", "&out OUT_BLE", "&trans", "&trans", "&trans", "&trans",
    *("&trans" for _ in range(8)),
    *("&trans" for _ in range(14)),
    "&bt BT_CLR", *("&trans" for _ in range(14)),
    *("&trans" for _ in range(12)),
]
EXPECTED_LAYERS = {
    "default_layer": EXPECTED_DEFAULT_BINDINGS,
    "fn_layer": EXPECTED_FN_BINDINGS,
    "fn_layer2": EXPECTED_FN2_BINDINGS,
}
EXPECTED_METADATA = {
    "variant": "kc2-x3-v2",
    "requirement_id": "CON-ARCH-004",
    "layout": "70-key-v5-no-stabilizer",
    "key_count": {"left": 31, "right": 39, "total": 70},
    "matrix": {"rows": 5, "left_columns": 7, "right_columns": 8, "transform_columns": 15},
    "supported_assembly": ["choc-v2-bottom-socket", "mx-direct-solder"],
    "unsupported_assembly": ["choc-v1", "choc-v2-direct-solder", "mx-hotswap"],
    "controller": "nice-nano-v2-socket-15.24-mm-row-spacing",
    "compact_controller": True,
    "carrier_battery_nets": False,
    "battery_leads": "direct-to-nice-nano-b-plus-b-minus",
    "left_alt_fn_win_combo": {
        "positions": [59, 60],
        "timeout_ms": 50,
        "binding": "LGUI",
        "layers": "all",
        "release": "first-constituent-key",
    },
    "fn_position": "immediately-right-of-up",
    "bottom_row_right_fn": False,
}


def read_build_evidence(path: Path = BUILD_EVIDENCE_PATH) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_digest_group(
    manifest: Mapping[str, object],
    field: str,
    expected_paths: tuple[Path, ...],
    root: Path,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    verified: list[str] = []
    recorded = manifest.get(field)
    expected_names = {path.as_posix() for path in expected_paths}
    if not isinstance(recorded, dict) or set(recorded) != expected_names:
        actual_names = set(recorded) if isinstance(recorded, dict) else set()
        errors.append(
            f"build evidence {field} source set mismatch: "
            f"missing={sorted(expected_names - actual_names)}, extra={sorted(actual_names - expected_names)}"
        )
        recorded = recorded if isinstance(recorded, dict) else {}
    for relative in expected_paths:
        name = relative.as_posix()
        expected_digest = recorded.get(name)
        source = root / relative
        if not isinstance(expected_digest, str) or re.fullmatch(r"[0-9a-f]{64}", expected_digest) is None:
            errors.append(f"build evidence {field} missing valid SHA-256 for {name}")
            continue
        if not source.is_file():
            errors.append(f"build evidence source is missing: {name}")
            continue
        actual_digest = sha256_file(source)
        if actual_digest != expected_digest:
            errors.append(
                f"build evidence source digest mismatch for {name}: "
                f"recorded={expected_digest}, current={actual_digest}"
            )
            continue
        verified.append(name)
    return errors, verified


def _verify_local_uf2(path: Path, expected: Mapping[str, object], side: str) -> list[str]:
    errors: list[str] = []
    data = path.read_bytes()
    expected_size = expected["size_bytes"]
    if len(data) != expected_size:
        errors.append(f"{side} local UF2 size is {len(data)}, expected {expected_size}")
    actual_digest = sha256_file(path)
    if actual_digest != expected["sha256"]:
        errors.append(
            f"{side} local UF2 SHA-256 is {actual_digest}, expected {expected['sha256']}"
        )
    block_size = int(EXPECTED_UF2_MAGIC["block_size_bytes"])
    if not data or len(data) % block_size:
        errors.append(f"{side} local UF2 size is not a nonzero multiple of {block_size}")
        return errors
    block_count = len(data) // block_size
    if block_count != expected["uf2_block_count"]:
        errors.append(
            f"{side} local UF2 block count is {block_count}, expected {expected['uf2_block_count']}"
        )
    expected_magic = (
        int(str(EXPECTED_UF2_MAGIC["start0_le_u32"]), 16),
        int(str(EXPECTED_UF2_MAGIC["start1_le_u32"]), 16),
        int(str(EXPECTED_UF2_MAGIC["end_le_u32"]), 16),
    )
    for block_index, offset in enumerate(range(0, len(data), block_size)):
        actual_magic = (
            struct.unpack_from("<I", data, offset)[0],
            struct.unpack_from("<I", data, offset + 4)[0],
            struct.unpack_from("<I", data, offset + block_size - 4)[0],
        )
        if actual_magic != expected_magic:
            errors.append(
                f"{side} local UF2 block {block_index} magic is invalid: "
                f"{tuple(f'0x{value:08x}' for value in actual_magic)}"
            )
            break
    return errors


def verify_build_evidence(
    manifest_path: Path = BUILD_EVIDENCE_PATH,
    root: Path = ROOT,
    artifact_paths: Mapping[str, Path] | None = None,
) -> tuple[list[str], dict[str, object]]:
    """Verify pinned source provenance and, when present, ignored local UF2 files."""
    provenance_errors: list[str] = []
    selected_artifacts = dict(LOCAL_ARTIFACT_PATHS if artifact_paths is None else artifact_paths)
    local_artifact_report = {
        side: {
            "present": (path := selected_artifacts.get(side)) is not None and path.is_file(),
            "verified": False,
        }
        for side in ("left", "right")
    }
    try:
        manifest = read_build_evidence(manifest_path)
    except (OSError, json.JSONDecodeError) as error:
        report = {
            "manifest_provenance_verified": False,
            "hash_policy_verified": False,
            "hardware_compatibility_verified": False,
            "source_digests_verified": [],
            "metadata_digests_verified": [],
            "local_artifacts": local_artifact_report,
        }
        return [f"Cannot read V2 build evidence: {error}"], report

    if manifest.get("schema_version") != 1:
        provenance_errors.append("build evidence schema_version must be 1")
    hash_policy_verified = manifest.get("hash_policy") == HASH_POLICY
    if not hash_policy_verified:
        provenance_errors.append(f"build evidence hash policy must be {HASH_POLICY!r}")
    if manifest.get("requirement_id") != "CON-ARCH-004":
        provenance_errors.append("build evidence requirement_id must be CON-ARCH-004")
    if manifest.get("variant") != "kc2-x3-v2-70-key-v5":
        provenance_errors.append("build evidence variant must identify the 70-key v5 shield")
    if manifest.get("recorded_build_date") != "2026-08-22":
        provenance_errors.append("build evidence recorded_build_date must identify the verified v5 build")
    if manifest.get("toolchain") != EXPECTED_BUILD_TOOLCHAIN:
        provenance_errors.append("build evidence pinned toolchain metadata is stale or incomplete")
    if manifest.get("artifacts") != EXPECTED_BUILD_ARTIFACTS:
        provenance_errors.append("build evidence left/right artifact metadata is stale or incomplete")
    hardware_compatibility_verified = (
        manifest.get("hardware_compatibility") == EXPECTED_HARDWARE_COMPATIBILITY
    )
    if not hardware_compatibility_verified:
        provenance_errors.append(
            "build evidence 1N4148W hardware compatibility and pending scan gate are stale or incomplete"
        )
    if manifest.get("uf2_magic") != EXPECTED_UF2_MAGIC:
        provenance_errors.append("build evidence UF2 magic contract is stale or incomplete")
    if manifest.get("artifact_policy") != {
        "tracked_in_git": False,
        "local_presence_required_for_source_provenance": False,
        "when_present": "Verifier hard-checks size, SHA-256, block count, and UF2 magic for every block.",
    }:
        provenance_errors.append("build evidence ignored-artifact policy is stale or incomplete")

    source_errors, sources_verified = _verify_digest_group(
        manifest, "build_inputs", BUILD_SOURCE_PATHS, root
    )
    metadata_errors, metadata_verified = _verify_digest_group(
        manifest, "verification_metadata_inputs", BUILD_METADATA_PATHS, root
    )
    provenance_errors.extend(source_errors)
    provenance_errors.extend(metadata_errors)

    artifact_errors: list[str] = []
    for side in ("left", "right"):
        path = selected_artifacts.get(side)
        present = local_artifact_report[side]["present"]
        side_errors = _verify_local_uf2(path, EXPECTED_BUILD_ARTIFACTS[side], side) if present else []
        artifact_errors.extend(side_errors)
        local_artifact_report[side]["verified"] = present and not side_errors

    report = {
        "manifest_provenance_verified": not provenance_errors,
        "hash_policy_verified": hash_policy_verified,
        "hardware_compatibility_verified": hardware_compatibility_verified,
        "source_digests_verified": sources_verified,
        "metadata_digests_verified": metadata_verified,
        "local_artifacts": local_artifact_report,
    }
    return [*provenance_errors, *artifact_errors], report


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


def parse_combo(source: str, combo_name: str) -> dict[str, object]:
    match = re.search(rf"\b{re.escape(combo_name)}\s*\{{(.*?)\n\s*\}};", source, re.DOTALL)
    if match is None:
        raise ValueError(f"Missing {combo_name} combo")
    body = match.group(1)
    timeout_match = re.search(r"\btimeout-ms\s*=\s*<(\d+)>;", body)
    positions_match = re.search(r"\bkey-positions\s*=\s*<([^>]*)>;", body, re.DOTALL)
    binding_match = re.search(r"\bbindings\s*=\s*<([^>]*)>;", body, re.DOTALL)
    if timeout_match is None or positions_match is None or binding_match is None:
        raise ValueError(f"Incomplete {combo_name} combo")
    bindings = parse_bindings(f"bindings = <{binding_match.group(1)}>;")
    if len(bindings) != 1:
        raise ValueError(f"{combo_name} must emit exactly one binding")
    layers_match = re.search(r"\blayers\s*=", body)
    slow_release_match = re.search(r"\bslow-release\s*;", body)
    return {
        "key_positions": [int(value) for value in re.findall(r"\d+", positions_match.group(1))],
        "binding": bindings[0],
        "timeout_ms": int(timeout_match.group(1)),
        "global_layers": layers_match is None,
        "release_on_first_key": slow_release_match is None,
    }


def parse_gpio_list(source: str, property_name: str) -> list[tuple[int, int]]:
    match = re.search(rf"\b{re.escape(property_name)}\s*=\s*(.*?);", source, re.DOTALL)
    if match is None:
        raise ValueError(f"Missing {property_name} property")
    return [(int(port), int(pin)) for port, pin in re.findall(r"<&gpio(\d+)\s+(\d+)", match.group(1))]


def read_transform() -> list[tuple[int, int]]:
    return parse_transform_positions((SHIELD_DIR / "kc2_x3_v2.dtsi").read_text(encoding="utf-8"))


def read_layer(layer_name: str) -> list[str]:
    return parse_layer_bindings((SHIELD_DIR / "kc2_x3_v2.keymap").read_text(encoding="utf-8"), layer_name)


def read_combo(combo_name: str) -> dict[str, object]:
    return parse_combo((SHIELD_DIR / "kc2_x3_v2.keymap").read_text(encoding="utf-8"), combo_name)


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
    errors, _ = verify_build_evidence()
    try:
        transform = read_transform()
    except (OSError, ValueError) as error:
        return [f"Cannot read V2 matrix transform: {error}"]
    if len(transform) != 70:
        errors.append(f"V2 matrix transform contains {len(transform)} positions, expected 70")
    if len(set(transform)) != len(transform):
        errors.append("V2 matrix transform contains duplicate positions")
    if any(row not in range(5) or col not in range(15) for row, col in transform):
        errors.append("V2 matrix transform contains a position outside its 5x15 domain")

    try:
        for layer_name, expected in EXPECTED_LAYERS.items():
            actual = read_layer(layer_name)
            if actual != expected:
                errors.append(f"{layer_name} bindings do not match the KC2 X3 V2 behavior model")
            if len(actual) != 70:
                errors.append(f"{layer_name} has {len(actual)} bindings, expected 70")
    except (OSError, ValueError) as error:
        errors.append(f"Cannot read V2 keymap: {error}")

    try:
        combo = read_combo("left_alt_fn_win")
        expected_combo = {
            "key_positions": [59, 60],
            "binding": "&kp LGUI",
            "timeout_ms": 50,
            "global_layers": True,
            "release_on_first_key": True,
        }
        if combo != expected_combo:
            errors.append("left Alt+Fn combo does not match the CON-ARCH-004 Win/LGUI behavior")
    except (OSError, ValueError) as error:
        errors.append(f"Cannot read V2 Alt+Fn combo: {error}")

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
    _, build_report = verify_build_evidence()
    artifact_states = ", ".join(
        f"{side}=" + ("verified" if state["verified"] else "absent")
        for side, state in build_report["local_artifacts"].items()
    )
    print(
        "CON-ARCH-004 V2 firmware verification passed: 70 keys (31 left, 39 right); "
        f"manifest_provenance_verified={str(build_report['manifest_provenance_verified']).lower()}; "
        f"local_artifacts={artifact_states}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
