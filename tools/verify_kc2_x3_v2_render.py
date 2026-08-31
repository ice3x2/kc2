"""Verify CON-ARCH-006/007 joined render evidence and reproducibility."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from tools.canonical_hash import HASH_POLICY, sha256_file
from tools.render_kc2_x3_joined import (
    DEFAULT_CLEARANCE_MM,
    DEFAULT_SCALE,
    FULL_MARGIN_PX,
    ROOT,
    X3_V2_SERVICE_REFERENCES,
    X3_V2_BATTERY_TERMINAL_LEGENDS,
    ZOOM_WIDTH_MM,
    RenderContext,
    build_context,
    battery_terminal_legend_counts,
    png_dimensions,
    mount_centers_mm,
    render_png,
    render_reference_counts,
    render_svg,
    shifted_service_component,
    shift_point,
)


RENDER_ROOT = ROOT / "hardware" / "kicad" / "draft" / "x3-v2" / "renders"
DEFAULT_MANIFEST = RENDER_ROOT / "kc2_x3_v2_render_manifest.json"
RENDERER_PATH = ROOT / "tools" / "render_kc2_x3_joined.py"
EXPECTED_SERVICE_REFERENCES = X3_V2_SERVICE_REFERENCES
EXPECTED_BATTERY_TERMINAL_LEGENDS = X3_V2_BATTERY_TERMINAL_LEGENDS
EXPECTED_BOARD_CANONICAL_SHA256 = {
    "left": "92c46f364f0cc647928029f6b42a54abfcc94485a491e5a6177e84cc7800d26f",
    "right": "8769b5792386357a876008f20152f836012a299a1230b359aaa530ffa85e7b0a",
}
EXPECTED_MOUNT_CENTERS_MM = {
    "left": {
        "MH1": [112.8625, 43.0],
        "MH2": [144.1125, 66.25],
        "MH3": [38.6125, 111.0],
        "MH4": [63.6125, 123.0],
        "MH5": [81.1125, 151.75],
        "MH6": [137.3625, 153.5],
        "MH7": [166.3625, 148.75],
        "MH8": [75.0, 134.0],
    },
    "right": {
        "MH1": [97.1875, 43.25],
        "MH2": [72.4375, 67.0],
        "MH3": [169.9375, 95.25],
        "MH4": [194.9375, 98.75],
        "MH5": [156.1875, 112.5],
        "MH6": [69.9375, 146.25],
        "MH7": [97.4375, 152.0],
        "MH8": [122.6875, 151.0],
        "MH9": [177.5, 118.0],
    },
}
EXPECTED_RENDER_PARAMETERS = {
    "clearance_mm": DEFAULT_CLEARANCE_MM,
    "scale_px_per_mm": DEFAULT_SCALE,
    "placement_mode": "key-pitch",
    "full_margin_px": FULL_MARGIN_PX,
    "zoom_width_mm": ZOOM_WIDTH_MM,
}
EXPECTED_OUTPUTS = {
    "joined_top_svg": ("kc2_x3_v2_joined_top.svg", False, "image/svg+xml", render_svg),
    "join_seam_zoom_svg": (
        "kc2_x3_v2_join_seam_zoom.svg",
        True,
        "image/svg+xml",
        render_svg,
    ),
    "joined_top_png": ("kc2_x3_v2_joined_top.png", False, "image/png", render_png),
    "join_seam_zoom_png": (
        "kc2_x3_v2_join_seam_zoom.png",
        True,
        "image/png",
        render_png,
    ),
}


def _raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected_board_path(repo_root: Path, side: str) -> Path:
    directory = f"kc2_{side}-x3-v2"
    return (
        repo_root
        / "hardware"
        / "kicad"
        / "draft"
        / "x3-v2"
        / directory
        / f"{directory}.kicad_pcb"
    )


def _expected_board_relative_path(side: str) -> str:
    return _expected_board_path(ROOT, side).relative_to(ROOT).as_posix()


def _expected_output_relative_path(filename: str) -> str:
    return (RENDER_ROOT / filename).relative_to(ROOT).as_posix()


def _output_path(
    repo_root: Path,
    output_root: Path | None,
    record: dict[str, object],
    filename: str,
) -> Path:
    if output_root is not None:
        return output_root / filename
    record_path = record.get("path")
    if not isinstance(record_path, str):
        return repo_root / "__missing_render_output__"
    return repo_root / Path(record_path)


def _float_attr(node: ET.Element, name: str) -> float:
    value = node.get(name)
    if value is None:
        raise ValueError(f"missing {name}")
    return float(value)


def _float_list_attr(node: ET.Element, name: str) -> tuple[float, ...]:
    value = node.get(name)
    if value is None:
        raise ValueError(f"missing {name}")
    return tuple(float(item) for item in value.split(","))


def _close(actual: float, expected: float) -> bool:
    return math.isclose(actual, expected, rel_tol=0.0, abs_tol=0.00011)


def _svg_dimensions(root: ET.Element) -> tuple[int, int]:
    return int(root.attrib["width"]), int(root.attrib["height"])


def _visible_texts(node: ET.Element) -> set[str]:
    return {
        (child.text or "").strip()
        for child in node.iter()
        if child.tag.endswith("text") and (child.text or "").strip()
    }


def verify_svg_semantics(path: Path, ctx: RenderContext) -> list[str]:
    errors: list[str] = []
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as error:
        return [f"{path.name}: SVG cannot be parsed: {error}"]

    service_nodes = [
        node for node in root.iter() if node.get("class") == "service-component"
    ]
    mount_nodes = [node for node in root.iter() if node.get("class") == "mounting-hole"]
    terminal_legend_nodes = [
        node for node in root.iter() if node.get("class") == "battery-terminal-legend"
    ]
    service_by_key: dict[tuple[str, str], list[ET.Element]] = {}
    mount_by_key: dict[tuple[str, str], list[ET.Element]] = {}
    terminal_legend_by_key: dict[tuple[str, str], list[ET.Element]] = {}
    for node in service_nodes:
        service_by_key.setdefault(
            (node.get("data-side", ""), node.get("data-reference", "")), []
        ).append(node)
    for node in mount_nodes:
        mount_by_key.setdefault(
            (node.get("data-side", ""), node.get("data-reference", "")), []
        ).append(node)
    for node in terminal_legend_nodes:
        terminal_legend_by_key.setdefault(
            (node.get("data-side", ""), node.get("data-text", "")), []
        ).append(node)

    expected_service_keys = {
        (data.side, component.reference)
        for data in (ctx.left, ctx.right)
        for component in data.service_components
    }
    if set(service_by_key) != expected_service_keys or any(
        len(nodes) != 1 for nodes in service_by_key.values()
    ):
        errors.append(
            f"{path.name}: service SVG semantics references/counts mismatch: "
            f"actual={sorted(service_by_key)}, expected={sorted(expected_service_keys)}"
        )
    for data in (ctx.left, ctx.right):
        for component in data.service_components:
            nodes = service_by_key.get((data.side, component.reference), [])
            if len(nodes) != 1:
                continue
            node = nodes[0]
            joined_center, joined_bounds = shifted_service_component(ctx, data.side, component)
            try:
                scalar_checks = {
                    "data-board-center-x-mm": component.center[0],
                    "data-board-center-y-mm": component.center[1],
                    "data-joined-center-x-mm": joined_center[0],
                    "data-joined-center-y-mm": joined_center[1],
                    "data-rotation-degrees": component.rotation_degrees,
                }
                for name, expected in scalar_checks.items():
                    if not _close(_float_attr(node, name), expected):
                        errors.append(
                            f"{path.name}: service SVG semantics {data.side} "
                            f"{component.reference} {name} mismatch"
                        )
                for name, expected in (
                    ("data-board-bounds-mm", component.bounds),
                    ("data-joined-bounds-mm", joined_bounds),
                ):
                    actual = _float_list_attr(node, name)
                    if len(actual) != 4 or any(
                        not _close(actual_value, expected_value)
                        for actual_value, expected_value in zip(actual, expected)
                    ):
                        errors.append(
                            f"{path.name}: service SVG semantics {data.side} "
                            f"{component.reference} {name} mismatch"
                        )
            except ValueError as error:
                errors.append(
                    f"{path.name}: service SVG semantics {data.side} "
                    f"{component.reference}: {error}"
                )
            if component.reference not in _visible_texts(node):
                errors.append(
                    f"{path.name}: service SVG semantics {data.side} "
                    f"{component.reference} visible label is missing"
                )

    expected_terminal_legend_keys = {
        (data.side, legend.text)
        for data in (ctx.left, ctx.right)
        for legend in data.battery_terminal_legends
    }
    if set(terminal_legend_by_key) != expected_terminal_legend_keys or any(
        len(nodes) != 1 for nodes in terminal_legend_by_key.values()
    ):
        errors.append(
            f"{path.name}: battery terminal SVG semantics labels/counts mismatch: "
            f"actual={sorted(terminal_legend_by_key)}, "
            f"expected={sorted(expected_terminal_legend_keys)}"
        )
    for data in (ctx.left, ctx.right):
        for legend in data.battery_terminal_legends:
            nodes = terminal_legend_by_key.get((data.side, legend.text), [])
            if len(nodes) != 1:
                continue
            node = nodes[0]
            joined_center = shift_point(ctx, data.side, legend.center)
            try:
                for name, expected in {
                    "data-board-center-x-mm": legend.center[0],
                    "data-board-center-y-mm": legend.center[1],
                    "data-joined-center-x-mm": joined_center[0],
                    "data-joined-center-y-mm": joined_center[1],
                }.items():
                    if not _close(_float_attr(node, name), expected):
                        errors.append(
                            f"{path.name}: battery terminal SVG semantics {data.side} "
                            f"{legend.text} {name} mismatch"
                        )
            except ValueError as error:
                errors.append(
                    f"{path.name}: battery terminal SVG semantics {data.side} "
                    f"{legend.text}: {error}"
                )
            if legend.text not in _visible_texts(node):
                errors.append(
                    f"{path.name}: battery terminal SVG semantics {data.side} "
                    f"{legend.text} visible label is missing"
                )

    expected_mount_keys = {
        (data.side, mount.reference)
        for data in (ctx.left, ctx.right)
        for mount in data.mounts
    }
    if set(mount_by_key) != expected_mount_keys or any(
        len(nodes) != 1 for nodes in mount_by_key.values()
    ):
        errors.append(
            f"{path.name}: mounting SVG semantics references/counts mismatch: "
            f"actual={sorted(mount_by_key)}, expected={sorted(expected_mount_keys)}"
        )
    for data in (ctx.left, ctx.right):
        for mount in data.mounts:
            nodes = mount_by_key.get((data.side, mount.reference), [])
            if len(nodes) != 1:
                continue
            node = nodes[0]
            joined_center = shift_point(ctx, data.side, mount.center)
            try:
                for name, expected in {
                    "data-board-center-x-mm": mount.center[0],
                    "data-board-center-y-mm": mount.center[1],
                    "data-joined-center-x-mm": joined_center[0],
                    "data-joined-center-y-mm": joined_center[1],
                }.items():
                    if not _close(_float_attr(node, name), expected):
                        errors.append(
                            f"{path.name}: mounting SVG semantics {data.side} "
                            f"{mount.reference} {name} mismatch"
                        )
            except ValueError as error:
                errors.append(
                    f"{path.name}: mounting SVG semantics {data.side} "
                    f"{mount.reference}: {error}"
                )
            if mount.reference not in _visible_texts(node):
                errors.append(
                    f"{path.name}: mounting SVG semantics {data.side} "
                    f"{mount.reference} visible label is missing"
                )
    return errors


def _verify_regeneration(
    ctx: RenderContext,
    records: dict[str, dict[str, object]],
    actual_paths: dict[str, Path],
) -> list[str]:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="kc2-render-verify-") as temporary:
        temp_root = Path(temporary)
        for key, (filename, zoom, _media_type, renderer) in EXPECTED_OUTPUTS.items():
            record = records[key]
            repeat_path = temp_root / filename
            try:
                dimensions = renderer(ctx, repeat_path, zoom=zoom)
            except Exception as error:  # pragma: no cover - exact backend error is environmental
                errors.append(f"{filename}: deterministic regeneration failed: {error}")
                continue
            if filename.endswith(".svg"):
                repeated_digest = sha256_file(repeat_path)
                if repeated_digest != record.get("regenerated_canonical_sha256"):
                    errors.append(f"{filename}: regenerated canonical SHA-256 mismatch")
                if repeated_digest != sha256_file(actual_paths[key]):
                    errors.append(f"{filename}: current output is not a deterministic regeneration")
            else:
                repeated_digest = _raw_sha256(repeat_path)
                if repeated_digest != record.get("regenerated_raw_sha256"):
                    errors.append(f"{filename}: regenerated raw SHA-256 mismatch")
                if repeated_digest != _raw_sha256(actual_paths[key]):
                    errors.append(f"{filename}: current output is not a deterministic regeneration")
            if dimensions != (record.get("width_px"), record.get("height_px")):
                errors.append(f"{filename}: regenerated dimensions mismatch")
            if filename.endswith(".png"):
                second_path = temp_root / f"second-{filename}"
                try:
                    renderer(ctx, second_path, zoom=zoom)
                except Exception as error:  # pragma: no cover
                    errors.append(f"{filename}: second PNG regeneration failed: {error}")
                    continue
                if _raw_sha256(second_path) != repeated_digest:
                    errors.append(f"{filename}: PNG regeneration is not byte-deterministic")
    return errors


def verify_render_manifest(
    manifest_path: Path = DEFAULT_MANIFEST,
    *,
    repo_root: Path = ROOT,
    output_root: Path | None = None,
    verify_regeneration: bool = True,
    enforce_release_board_hashes: bool = True,
) -> list[str]:
    errors: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"manifest cannot be read: {error}"]
    if manifest.get("schema") != "kc2-x3-v2-render-evidence-v1":
        errors.append("manifest: wrong render evidence schema")
    if manifest.get("requirement_ids") != ["CON-ARCH-006", "CON-ARCH-007"]:
        errors.append("manifest: requirement IDs are missing or stale")
    if manifest.get("variant") != "x3-v2":
        errors.append("manifest: variant is missing or stale")
    if manifest.get("hash_policy") != HASH_POLICY:
        errors.append("manifest: canonical hash policy is missing or stale")
    if manifest.get("render_parameters") != EXPECTED_RENDER_PARAMETERS:
        errors.append("manifest: render parameters are missing or stale")

    renderer_record = manifest.get("renderer")
    if not isinstance(renderer_record, dict):
        errors.append("manifest: renderer binding is missing")
    else:
        if renderer_record.get("path") != "tools/render_kc2_x3_joined.py":
            errors.append("manifest: renderer path is missing or stale")
        if renderer_record.get("canonical_sha256") != sha256_file(RENDERER_PATH):
            errors.append("manifest: renderer canonical SHA-256 mismatch")
        if "raw_sha256" in renderer_record:
            errors.append("manifest: renderer must not bind newline-sensitive raw text bytes")

    source_records = manifest.get("source_boards")
    if not isinstance(source_records, dict) or set(source_records) != {"left", "right"}:
        errors.append("manifest: source board bindings are missing")
        return errors
    for side in ("left", "right"):
        record = source_records.get(side)
        board_path = _expected_board_path(repo_root, side)
        if not isinstance(record, dict):
            errors.append(f"{side}: source board record is missing")
            continue
        if record.get("path") != _expected_board_relative_path(side):
            errors.append(f"{side}: source board path is missing or stale")
        if not board_path.is_file():
            errors.append(f"{side}: source board is missing")
            continue
        canonical_sha = sha256_file(board_path)
        if record.get("canonical_sha256") != canonical_sha:
            errors.append(f"{side}: source board canonical SHA-256 mismatch")
        if "raw_sha256" in record:
            errors.append(f"{side}: source board must not bind newline-sensitive raw text bytes")
        if enforce_release_board_hashes and canonical_sha != EXPECTED_BOARD_CANONICAL_SHA256[side]:
            errors.append(f"{side}: source board is not the final CON-ARCH-006/007 P2 board")

    try:
        ctx = build_context(
            repo_root.resolve(),
            DEFAULT_CLEARANCE_MM,
            DEFAULT_SCALE,
            "key-pitch",
            variant="x3-v2",
        )
    except Exception as error:
        errors.append(f"source board: {error}")
        return errors

    service_counts, mount_counts = render_reference_counts(ctx)
    terminal_legend_counts = battery_terminal_legend_counts(ctx)
    actual_mount_centers = mount_centers_mm(ctx)
    expected_terminal_legend_counts = {
        side: {text: 1 for text in EXPECTED_BATTERY_TERMINAL_LEGENDS}
        for side in ("left", "right")
    }
    if manifest.get("service_reference_counts") != service_counts:
        errors.append("manifest: service reference counts are missing or stale")
    if manifest.get("mount_reference_counts") != mount_counts:
        errors.append("manifest: mounting reference counts are missing or stale")
    if actual_mount_centers != EXPECTED_MOUNT_CENTERS_MM:
        errors.append("source board: mounting centers do not match final CON-ARCH-006 P2")
    if manifest.get("mount_centers_mm") != actual_mount_centers:
        errors.append("manifest: mounting centers are missing or stale")
    if manifest.get("battery_terminal_legend_counts") != terminal_legend_counts:
        errors.append("manifest: battery terminal legend counts are missing or stale")
    if terminal_legend_counts != expected_terminal_legend_counts:
        errors.append("source board: B+ and B-/GND F.Silkscreen legends are missing or stale")

    output_records = manifest.get("outputs")
    if not isinstance(output_records, dict) or set(output_records) != set(EXPECTED_OUTPUTS):
        errors.append("manifest: render output set is missing or stale")
        return errors
    typed_records: dict[str, dict[str, object]] = {}
    actual_paths: dict[str, Path] = {}
    for key, (filename, zoom, media_type, _renderer) in EXPECTED_OUTPUTS.items():
        record = output_records.get(key)
        if not isinstance(record, dict):
            errors.append(f"{key}: output record is missing")
            continue
        typed_records[key] = record
        if record.get("path") != _expected_output_relative_path(filename):
            errors.append(f"{key}: output path is missing or stale")
        if record.get("media_type") != media_type or record.get("zoom") is not zoom:
            errors.append(f"{key}: output media/zoom contract is missing or stale")
        if record.get("service_reference_counts") != service_counts:
            errors.append(f"{key}: service reference counts are missing or stale")
        if record.get("mount_reference_counts") != mount_counts:
            errors.append(f"{key}: mounting reference counts are missing or stale")
        if record.get("battery_terminal_legend_counts") != terminal_legend_counts:
            errors.append(f"{key}: battery terminal legend counts are missing or stale")
        if record.get("deterministic_regeneration") is not True:
            errors.append(f"{key}: deterministic regeneration is not proven")
        path = _output_path(repo_root, output_root, record, filename)
        actual_paths[key] = path
        if not path.is_file():
            errors.append(f"{key}: render output is missing")
            continue
        if path.suffix == ".svg":
            if record.get("digest_mode") != "canonical_text":
                errors.append(f"{key}: digest mode must be canonical_text")
            if "raw_sha256" in record or "regenerated_raw_sha256" in record:
                errors.append(f"{key}: SVG must not bind newline-sensitive raw text bytes")
            if record.get("regenerated_canonical_sha256") != record.get("canonical_sha256"):
                errors.append(f"{key}: recorded repeated canonical SHA-256 mismatch")
            if record.get("canonical_sha256") != sha256_file(path):
                errors.append(f"{key}: canonical SHA-256 mismatch")
        else:
            if record.get("digest_mode") != "raw_binary":
                errors.append(f"{key}: digest mode must be raw_binary")
            if record.get("regenerated_raw_sha256") != record.get("raw_sha256"):
                errors.append(f"{key}: recorded repeated raw SHA-256 mismatch")
            if record.get("raw_sha256") != _raw_sha256(path):
                errors.append(f"{key}: raw SHA-256 mismatch")
        try:
            if path.suffix == ".png":
                dimensions = png_dimensions(path)
            else:
                dimensions = _svg_dimensions(ET.parse(path).getroot())
        except (ET.ParseError, OSError, RuntimeError, KeyError, ValueError) as error:
            errors.append(f"{key}: output dimensions cannot be read: {error}")
        else:
            if dimensions != (record.get("width_px"), record.get("height_px")):
                errors.append(f"{key}: output dimensions mismatch")
        if path.suffix == ".svg":
            errors.extend(verify_svg_semantics(path, ctx))

    if verify_regeneration and set(typed_records) == set(EXPECTED_OUTPUTS) and all(
        path.is_file() for path in actual_paths.values()
    ):
        errors.extend(_verify_regeneration(ctx, typed_records, actual_paths))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify CON-ARCH-006/007 X3 V2 joined render evidence."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    errors = verify_render_manifest(args.manifest)
    report = {
        "requirements": ["CON-ARCH-006", "CON-ARCH-007"],
        "manifest": str(args.manifest),
        "deterministic_regeneration_checked": True,
        "errors": errors,
    }
    print(json.dumps(report, indent=2))
    if errors:
        return 1
    print("PASS: X3 V2 joined SVG/PNG render evidence is source-bound and deterministic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
