from __future__ import annotations

import copy
import hashlib
import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.canonical_hash import HASH_POLICY, sha256_file
from tools.verify_kc2_x3_v2_render import (
    EXPECTED_BOARD_CANONICAL_SHA256,
    EXPECTED_SERVICE_REFERENCES,
    verify_render_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
V2_ROOT = ROOT / "hardware" / "kicad" / "draft" / "x3-v2"
RENDER_ROOT = V2_ROOT / "renders"
MANIFEST = RENDER_ROOT / "kc2_x3_v2_render_manifest.json"


def raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class X3V2RenderEvidenceTests(unittest.TestCase):
    maxDiff = None

    def test_manifest_binds_final_boards_outputs_parameters_and_references(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["requirement_ids"],
            ["CON-ARCH-006", "CON-ARCH-007"],
        )
        self.assertEqual(manifest["hash_policy"], HASH_POLICY)
        self.assertNotIn("raw_sha256", manifest["renderer"])
        for record in manifest["source_boards"].values():
            self.assertNotIn("raw_sha256", record)
        self.assertEqual(
            {
                side: record["canonical_sha256"]
                for side, record in manifest["source_boards"].items()
            },
            EXPECTED_BOARD_CANONICAL_SHA256,
        )
        self.assertEqual(
            manifest["render_parameters"],
            {
                "clearance_mm": 1.0,
                "scale_px_per_mm": 5.0,
                "placement_mode": "key-pitch",
                "full_margin_px": 40.0,
                "zoom_width_mm": 64.0,
            },
        )
        self.assertEqual(
            manifest["service_reference_counts"],
            {
                "left": {reference: 1 for reference in EXPECTED_SERVICE_REFERENCES},
                "right": {reference: 1 for reference in EXPECTED_SERVICE_REFERENCES},
            },
        )
        self.assertEqual(manifest["mount_reference_counts"], {"left": 8, "right": 9})
        self.assertEqual(
            manifest["mount_centers_mm"],
            {
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
                    "MH1": [97.0625, 43.25],
                    "MH2": [72.4375, 67.0],
                    "MH3": [169.9375, 95.25],
                    "MH4": [194.9375, 98.75],
                    "MH5": [156.1875, 112.5],
                    "MH6": [69.9375, 146.25],
                    "MH7": [97.4375, 152.0],
                    "MH8": [122.6875, 151.0],
                    "MH9": [177.5, 118.0],
                },
            },
        )
        self.assertEqual(
            manifest["battery_terminal_legend_counts"],
            {
                "left": {"B+": 1, "B-/GND": 1},
                "right": {"B+": 1, "B-/GND": 1},
            },
        )
        for record in manifest["outputs"].values():
            output = ROOT / record["path"]
            self.assertTrue(record["deterministic_regeneration"])
            if output.suffix == ".svg":
                self.assertEqual(record["digest_mode"], "canonical_text")
                self.assertEqual(record["canonical_sha256"], sha256_file(output))
                self.assertEqual(
                    record["canonical_sha256"],
                    record["regenerated_canonical_sha256"],
                )
                self.assertNotIn("raw_sha256", record)
                self.assertNotIn("regenerated_raw_sha256", record)
            else:
                self.assertEqual(record["digest_mode"], "raw_binary")
                self.assertEqual(record["raw_sha256"], raw_sha256(output))
                self.assertEqual(record["raw_sha256"], record["regenerated_raw_sha256"])
            self.assertEqual(
                record["battery_terminal_legend_counts"],
                manifest["battery_terminal_legend_counts"],
            )
        self.assertEqual(verify_render_manifest(MANIFEST, verify_regeneration=False), [])

    def test_png_outputs_regenerate_deterministically_from_current_boards(self) -> None:
        self.assertEqual(verify_render_manifest(MANIFEST, verify_regeneration=True), [])

    def test_svg_semantic_mutation_fails_even_after_hash_refresh(self) -> None:
        with TemporaryDirectory(prefix="kc2-render-semantic-") as temporary:
            temp_root = Path(temporary)
            shutil.copytree(RENDER_ROOT, temp_root / "renders")
            manifest_path = temp_root / "renders" / MANIFEST.name
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            record = manifest["outputs"]["joined_top_svg"]
            svg_path = temp_root / "renders" / Path(record["path"]).name
            payload = svg_path.read_text(encoding="utf-8")
            self.assertIn('data-reference="SW_PWR1"', payload)
            svg_path.write_text(
                payload.replace('data-reference="SW_PWR1"', 'data-reference="SW_FAKE1"', 1),
                encoding="utf-8",
            )
            record["canonical_sha256"] = sha256_file(svg_path)
            record["regenerated_canonical_sha256"] = record["canonical_sha256"]
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            errors = verify_render_manifest(
                manifest_path,
                output_root=temp_root / "renders",
                verify_regeneration=False,
            )
            self.assertTrue(any("service SVG semantics" in error for error in errors), errors)

    def test_source_service_reference_removal_fails_after_board_hash_refresh(self) -> None:
        with TemporaryDirectory(prefix="kc2-render-board-") as temporary:
            temp_root = Path(temporary)
            for side in ("left", "right"):
                source_dir = V2_ROOT / f"kc2_{side}-x3-v2"
                target_dir = temp_root / "hardware" / "kicad" / "draft" / "x3-v2" / source_dir.name
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_dir / f"kc2_{side}-x3-v2.kicad_pcb", target_dir)
            shutil.copytree(RENDER_ROOT, temp_root / "hardware" / "kicad" / "draft" / "x3-v2" / "renders")
            manifest_path = (
                temp_root
                / "hardware"
                / "kicad"
                / "draft"
                / "x3-v2"
                / "renders"
                / MANIFEST.name
            )
            left_board = (
                temp_root
                / "hardware"
                / "kicad"
                / "draft"
                / "x3-v2"
                / "kc2_left-x3-v2"
                / "kc2_left-x3-v2.kicad_pcb"
            )
            board_payload = left_board.read_text(encoding="utf-8")
            self.assertIn('(property "Reference" "BAT1"', board_payload)
            left_board.write_text(
                board_payload.replace('(property "Reference" "BAT1"', '(property "Reference" "BATX"', 1),
                encoding="utf-8",
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_boards"]["left"]["canonical_sha256"] = sha256_file(left_board)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            errors = verify_render_manifest(
                manifest_path,
                repo_root=temp_root,
                output_root=manifest_path.parent,
                verify_regeneration=False,
                enforce_release_board_hashes=False,
            )
            self.assertTrue(any("BAT1" in error and "missing" in error for error in errors), errors)

    def test_source_battery_terminal_legend_removal_fails_after_board_hash_refresh(self) -> None:
        with TemporaryDirectory(prefix="kc2-render-polarity-") as temporary:
            temp_root = Path(temporary)
            for side in ("left", "right"):
                source_dir = V2_ROOT / f"kc2_{side}-x3-v2"
                target_dir = temp_root / "hardware" / "kicad" / "draft" / "x3-v2" / source_dir.name
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_dir / f"kc2_{side}-x3-v2.kicad_pcb", target_dir)
            shutil.copytree(RENDER_ROOT, temp_root / "hardware" / "kicad" / "draft" / "x3-v2" / "renders")
            manifest_path = (
                temp_root
                / "hardware"
                / "kicad"
                / "draft"
                / "x3-v2"
                / "renders"
                / MANIFEST.name
            )
            left_board = (
                temp_root
                / "hardware"
                / "kicad"
                / "draft"
                / "x3-v2"
                / "kc2_left-x3-v2"
                / "kc2_left-x3-v2.kicad_pcb"
            )
            board_payload = left_board.read_text(encoding="utf-8")
            self.assertIn('(fp_text user "B-/GND"', board_payload)
            left_board.write_text(
                board_payload.replace('(fp_text user "B-/GND"', '(fp_text user "B-"', 1),
                encoding="utf-8",
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source_boards"]["left"]["canonical_sha256"] = sha256_file(left_board)
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

            errors = verify_render_manifest(
                manifest_path,
                repo_root=temp_root,
                output_root=manifest_path.parent,
                verify_regeneration=False,
                enforce_release_board_hashes=False,
            )
            self.assertTrue(
                any("B-/GND" in error and "missing" in error for error in errors),
                errors,
            )

    def test_render_parameter_mutation_is_rejected(self) -> None:
        with TemporaryDirectory(prefix="kc2-render-params-") as temporary:
            manifest_path = Path(temporary) / MANIFEST.name
            manifest = copy.deepcopy(json.loads(MANIFEST.read_text(encoding="utf-8")))
            manifest["render_parameters"]["scale_px_per_mm"] = 4.0
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            errors = verify_render_manifest(manifest_path, verify_regeneration=False)
            self.assertIn("manifest: render parameters are missing or stale", errors)

    def test_text_bindings_are_lf_crlf_invariant_but_binary_outputs_remain_raw(self) -> None:
        with TemporaryDirectory(prefix="kc2-render-eol-") as temporary:
            temp_root = Path(temporary)
            temp_v2_root = temp_root / "hardware" / "kicad" / "draft" / "x3-v2"
            for side in ("left", "right"):
                source_dir = V2_ROOT / f"kc2_{side}-x3-v2"
                target_dir = temp_v2_root / source_dir.name
                target_dir.mkdir(parents=True, exist_ok=True)
                board = target_dir / f"kc2_{side}-x3-v2.kicad_pcb"
                shutil.copy2(source_dir / board.name, board)
                board.write_bytes(board.read_bytes().replace(b"\r\n", b"\n"))
            shutil.copytree(RENDER_ROOT, temp_v2_root / "renders")
            temp_render_root = temp_v2_root / "renders"
            for svg in temp_render_root.glob("*.svg"):
                svg.write_bytes(svg.read_bytes().replace(b"\r\n", b"\n"))
            manifest_path = temp_render_root / MANIFEST.name
            self.assertEqual(
                verify_render_manifest(
                    manifest_path,
                    repo_root=temp_root,
                    output_root=temp_render_root,
                    verify_regeneration=False,
                ),
                [],
            )

            png_record = json.loads(manifest_path.read_text(encoding="utf-8"))["outputs"][
                "joined_top_png"
            ]
            png_path = temp_render_root / Path(png_record["path"]).name
            payload = bytearray(png_path.read_bytes())
            payload[-1] ^= 1
            png_path.write_bytes(payload)
            errors = verify_render_manifest(
                manifest_path,
                repo_root=temp_root,
                output_root=temp_render_root,
                verify_regeneration=False,
            )
            self.assertTrue(any("joined_top_png: raw SHA-256 mismatch" in error for error in errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
