from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.verify_kc2_x3_v2_mechanical import (
    DEFAULT_MANIFEST,
    ROOT,
    analyze_mechanical_outputs,
    inspect_pdf,
    pdf_control_geometry_errors,
    pdf_j_bat_marking_errors,
    pdf_one_to_one_scale_matches,
)

REQUIREMENT_IDS = {
    "CON-ARCH-004",
    "CON-ARCH-006",
    "CON-ARCH-007",
    "REL-ARCH-001",
}


def update_manifest_file_digest(
    manifest_path: Path, root: Path, product: str, kind: str, face: str | None = None
) -> None:
    from tools.canonical_hash import sha256_file

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    item = (
        manifest["products"][product]["drawings"][face]
        if kind == "drawing"
        else manifest["products"][product]["outline_svg"]
    )
    path = root / item["path"]
    item["size"] = path.stat().st_size
    item["sha256"] = sha256_file(path)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def materialize_index_mechanical_snapshot(root: Path) -> Path:
    manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
    paths: set[Path] = set()
    for details in manifest["products"].values():
        paths.add(Path(details["board"]))
        paths.update(Path(item["path"]) for item in details["drawings"].values())
        if "outline_svg" in details:
            paths.add(Path(details["outline_svg"]["path"]))
    manifest_relative = DEFAULT_MANIFEST.relative_to(ROOT)
    paths.add(manifest_relative)
    environment = os.environ.copy()
    environment["GIT_INDEX_FILE"] = str(root / "candidate.index")
    subprocess.run(["git", "read-tree", "HEAD"], cwd=ROOT, env=environment, check=True)
    subprocess.run(
        ["git", "add", "-f", "--", *(relative.as_posix() for relative in sorted(paths))],
        cwd=ROOT,
        env=environment,
        check=True,
    )
    for relative in paths:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(
            subprocess.check_output(
                ["git", "show", f":{relative.as_posix()}"], cwd=ROOT, env=environment
            )
        )
    return root / manifest_relative


class V2MechanicalOutputTests(unittest.TestCase):
    def test_all_boards_have_one_to_one_top_and_bottom_drawings(self) -> None:
        report = analyze_mechanical_outputs()

        self.assertEqual(set(report["requirement_ids"]), REQUIREMENT_IDS)
        self.assertTrue(report["requirement_ids_match"])
        self.assertEqual(report["scale"], 1.0)
        self.assertEqual(set(report["products"]), {"left", "right", "coupon"})
        for name, product in report["products"].items():
            self.assertTrue(product["source_board_exists"])
            self.assertTrue(product["source_board_sha256_matches"])
            self.assertEqual(set(product["drawings"]), {"top", "bottom"})
            for drawing in product["drawings"].values():
                self.assertTrue(drawing["exists"])
                self.assertTrue(drawing["pdf_header_valid"])
                self.assertEqual(drawing["pdf_parse_errors"], [])
                self.assertEqual(drawing["page_count"], 1)
                self.assertTrue(drawing["a4_landscape_media_box_matches"])
                self.assertTrue(drawing["one_to_one_scale_matches"])
                self.assertTrue(drawing["mirror_matches_manifest"])
                self.assertTrue(drawing["layers_match_contract"])
                self.assertEqual(drawing["control_geometry_errors"], [])
                self.assertTrue(drawing["sha256_matches"])
                self.assertGreater(drawing["size"], 1000)
            if name in {"left", "right"}:
                self.assertEqual(
                    product["drawings"]["top"]["j_bat_marking_errors"], []
                )
                self.assertTrue(product["outline_svg"]["exists"])
                self.assertTrue(product["outline_svg"]["svg_header_valid"])
                self.assertTrue(product["outline_svg"]["sha256_matches"])
                self.assertEqual(product["outline_svg"]["scale"], 1.0)
                self.assertTrue(product["outline_svg"]["physical_scale_matches"])
                self.assertTrue(product["outline_svg"]["view_box_matches_board"])
                self.assertEqual(product["outline_svg"]["control_geometry_errors"], [])
                self.assertEqual(product["outline_svg"]["j_bat_marking_errors"], [])
                self.assertFalse(product["outline_svg"]["has_trailing_whitespace"])

    def test_canonical_hash_policy_accepts_crlf_and_exact_index_snapshot(self) -> None:
        from tools.canonical_hash import HASH_POLICY, sha256_file

        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest.get("hash_policy"), HASH_POLICY)
        srs = (ROOT / "docs/spec/10.product-architecture.srs.md").read_text(encoding="utf-8")
        self.assertIn("candidate", srs)
        self.assertIn("mechanical", srs)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            lf = root / "lf.svg"
            crlf = root / "crlf.svg"
            lf.write_bytes(b"<svg>\n</svg>\n")
            crlf.write_bytes(b"<svg>\r\n</svg>\r\n")
            self.assertEqual(sha256_file(lf), sha256_file(crlf))
            snapshot_manifest = materialize_index_mechanical_snapshot(root)
            report = analyze_mechanical_outputs(snapshot_manifest, root=root)

        self.assertTrue(report["hash_policy_matches"])
        direct = subprocess.run(
            [sys.executable, "-B", str(ROOT / "tools/verify_kc2_x3_v2_mechanical.py"), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(direct.returncode, 0, direct.stderr)
        for product in report["products"].values():
            self.assertTrue(product["source_board_sha256_matches"])
            self.assertTrue(all(item["sha256_matches"] for item in product["drawings"].values()))
            if "outline_svg" in product:
                self.assertTrue(product["outline_svg"]["sha256_matches"])

    def test_hash_policy_gate_and_real_artifact_mutation(self) -> None:
        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            materialize_index_mechanical_snapshot(root)
            outline_path = root / manifest["products"]["left"]["outline_svg"]["path"]
            outline_path.write_bytes(outline_path.read_bytes() + b"<!-- mutation -->\n")
            bad_manifest = dict(manifest)
            bad_manifest["hash_policy"] = "raw-bytes-v0"
            bad_manifest_path = root / "bad-mechanical-manifest.json"
            bad_manifest_path.write_text(json.dumps(bad_manifest), encoding="utf-8")
            report = analyze_mechanical_outputs(bad_manifest_path, root=root)

        self.assertFalse(report["hash_policy_matches"])
        self.assertFalse(report["products"]["left"]["outline_svg"]["sha256_matches"])

    def test_pdf_parser_rejects_corrupt_and_unmirrored_coupled_files(self) -> None:
        for mode in ("corrupt", "unmirrored"):
            with self.subTest(mode=mode), TemporaryDirectory() as temporary:
                root = Path(temporary)
                manifest_path = materialize_index_mechanical_snapshot(root)
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                bottom = root / manifest["products"]["left"]["drawings"]["bottom"]["path"]
                if mode == "corrupt":
                    bottom.write_bytes(b"%PDF-1.4\n" + b"X" * 4096)
                else:
                    top = root / manifest["products"]["left"]["drawings"]["top"]["path"]
                    bottom.write_bytes(top.read_bytes())
                update_manifest_file_digest(manifest_path, root, "left", "drawing", "bottom")
                report = analyze_mechanical_outputs(manifest_path, root=root)
                drawing = report["products"]["left"]["drawings"]["bottom"]
                if mode == "corrupt":
                    self.assertTrue(drawing["pdf_parse_errors"])
                else:
                    self.assertFalse(drawing["mirror_matches_manifest"])

    def test_svg_parser_rejects_coupled_physical_scale_mutation(self) -> None:
        for mode in ("scale", "missing", "swapped"):
            with self.subTest(mode=mode), TemporaryDirectory() as temporary:
                root = Path(temporary)
                manifest_path = materialize_index_mechanical_snapshot(root)
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                outline = root / manifest["products"]["left"]["outline_svg"]["path"]
                payload = outline.read_text(encoding="utf-8")
                if mode == "scale":
                    old, new = 'width="135.1026mm"', 'width="270.2052mm"'
                    self.assertEqual(payload.count(old), 1)
                    payload = payload.replace(old, new, 1)
                elif mode == "missing":
                    old = "<desc>B-/GND</desc>"
                    self.assertEqual(payload.count(old), 1)
                    payload = payload.replace(old, "<desc></desc>", 1)
                else:
                    positive, negative = "<desc>B+</desc>", "<desc>B-/GND</desc>"
                    self.assertEqual(payload.count(positive), 1)
                    self.assertEqual(payload.count(negative), 1)
                    payload = payload.replace(positive, "<desc>SWAP</desc>", 1)
                    payload = payload.replace(negative, positive, 1)
                    payload = payload.replace("<desc>SWAP</desc>", negative, 1)
                outline.write_text(payload, encoding="utf-8")
                update_manifest_file_digest(manifest_path, root, "left", "outline")
                report = analyze_mechanical_outputs(manifest_path, root=root)
                result = report["products"]["left"]["outline_svg"]
                if mode == "scale":
                    self.assertFalse(result["physical_scale_matches"])
                else:
                    self.assertTrue(result["j_bat_marking_errors"], result)

    def test_pdf_scale_and_control_feature_mutations_fail_semantically(self) -> None:
        from tools.kc2_x3_v2_output_geometry import parse_board, source_control_flashes, source_drill_geometry

        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        board = parse_board(ROOT / manifest["products"]["left"]["board"])
        cases = (("top", "MH1"), ("bottom", "D1"))
        for face, reference in cases:
            with self.subTest(face=face, reference=reference):
                drawing = manifest["products"]["left"]["drawings"][face]
                inspection = inspect_pdf((ROOT / drawing["path"]).read_bytes())
                self.assertTrue(pdf_one_to_one_scale_matches(inspection))
                scaled = dict(inspection)
                scaled["matrix"] = (0.0144, 0.0, 0.0, 0.0144, 0.0, 0.0)
                self.assertFalse(pdf_one_to_one_scale_matches(scaled))
                self.assertEqual(
                    pdf_control_geometry_errors(
                        inspection, board, face, bool(drawing["mirrored"])
                    ),
                    [],
                )
                if reference == "MH1":
                    item = next(
                        item
                        for records in source_drill_geometry(board).values()
                        for item in records
                        if item["reference"] == reference
                    )
                else:
                    item = next(
                        item
                        for item in source_control_flashes(board, "B.Paste")
                        if item["reference"] == reference and item["pad"] == "1"
                    )
                media = inspection["media_box"]
                width_mm, height_mm = media[2] * 25.4 / 72.0, media[3] * 25.4 / 72.0
                center_x = width_mm - item["center"][0] if drawing["mirrored"] else item["center"][0]
                center_y = height_mm - item["center"][1]
                mutated = dict(inspection)
                mutated["paths"] = [
                    path
                    for path in inspection["paths"]
                    if not (
                        abs((path["bbox"][0] + path["bbox"][2]) / 2 - center_x) < 0.01
                        and abs((path["bbox"][1] + path["bbox"][3]) / 2 - center_y) < 0.01
                        and abs(path["bbox"][2] - path["bbox"][0] - item["size"][0]) < 0.01
                        and abs(path["bbox"][3] - path["bbox"][1] - item["size"][1]) < 0.01
                    )
                ]
                errors = pdf_control_geometry_errors(
                    mutated, board, face, bool(drawing["mirrored"])
                )
                self.assertTrue(any(reference in error for error in errors), errors)

        drawing = manifest["products"]["left"]["drawings"]["top"]
        board = parse_board(ROOT / manifest["products"]["left"]["board"])
        inspection = inspect_pdf((ROOT / drawing["path"]).read_bytes())
        self.assertEqual(pdf_j_bat_marking_errors(inspection, board, "top"), [])
        for mode in ("swapped", "missing"):
            with self.subTest(pdf_j_bat_marking=mode):
                mutated = dict(inspection)
                mutated["texts"] = [dict(item) for item in inspection["texts"]]
                positive = next(item for item in mutated["texts"] if item["text"] == "B+")
                negative = next(item for item in mutated["texts"] if item["text"] == "B-/GND")
                if mode == "swapped":
                    positive["text"], negative["text"] = negative["text"], positive["text"]
                else:
                    mutated["texts"].remove(negative)
                self.assertTrue(pdf_j_bat_marking_errors(mutated, board, "top"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
