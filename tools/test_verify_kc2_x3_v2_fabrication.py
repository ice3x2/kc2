from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.verify_kc2_x3_v2_fabrication import MANIFEST, ROOT, analyze_fabrication


def materialize_index_fabrication_snapshot(root: Path) -> Path:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    paths: set[Path] = set()
    for details in manifest["products"].values():
        paths.add(Path(details["board"]))
        paths.add(Path(details["archive"]))
        output_dir = Path(details["output_dir"])
        paths.update(output_dir / item["name"] for item in details["files"])
    manifest_relative = MANIFEST.relative_to(ROOT)
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


class V2FabricationTests(unittest.TestCase):
    def test_all_draft_fabrication_archives_are_complete(self) -> None:
        report = analyze_fabrication()

        self.assertEqual(report["variant"], "x3-v2")
        self.assertEqual(set(report["products"]), {"left", "right", "coupon"})
        for product, product_report in report["products"].items():
            with self.subTest(product=product):
                self.assertTrue(product_report["archive_exists"])
                self.assertTrue(product_report["source_board_exists"])
                self.assertTrue(product_report["source_board_sha256_matches"])
                self.assertTrue(product_report["key_count_matches"])
                self.assertEqual(product_report["missing_required_layers"], [])
                self.assertEqual(product_report["missing_drill_types"], [])
                self.assertEqual(product_report["nested_archive_entries"], [])
                self.assertTrue(product_report["has_bottom_paste"])
                self.assertTrue(product_report["has_job_file"])
                self.assertTrue(product_report["archive_sha256_matches"])
                self.assertEqual(product_report["file_hash_mismatches"], [])
                self.assertEqual(product_report["gerber_geometry_errors"], [])
                self.assertTrue(product_report["drill_geometry_matches"])
                self.assertEqual(
                    product_report["drill_tools_mm"],
                    product_report["expected_drill_tools_mm"],
                )
                self.assertGreaterEqual(product_report["archive_entry_count"], 13)

        self.assertEqual(report["products"]["left"]["bottom_paste_flash_count"], 124)
        self.assertEqual(report["products"]["right"]["bottom_paste_flash_count"], 156)
        self.assertEqual(report["products"]["coupon"]["bottom_paste_flash_count"], 12)

        left_product = report["products"]["left"]
        self.assertEqual(left_product["drill_tools_mm"]["PTH"]["0.950"], 24)
        self.assertEqual(left_product["drill_tools_mm"]["PTH"]["1.500"], 62)
        self.assertEqual(
            left_product["drill_tools_mm"]["NPTH"],
            {"1.600": 8, "1.650": 31, "1.700": 62, "2.200": 1, "3.000": 62, "5.000": 31},
        )
        self.assertEqual(
            left_product["drill_tools_mm"]["PTH"].get("0.300", 0),
            left_product["source_board_via_drills_mm"].get("0.300", 0),
        )
        right_product = report["products"]["right"]
        self.assertEqual(right_product["drill_tools_mm"]["PTH"]["0.950"], 24)
        self.assertEqual(right_product["drill_tools_mm"]["PTH"]["1.500"], 78)
        self.assertEqual(
            right_product["drill_tools_mm"]["NPTH"],
            {"1.600": 10, "1.650": 39, "1.700": 78, "2.200": 1, "3.000": 78, "5.000": 39},
        )
        self.assertEqual(
            right_product["drill_tools_mm"]["PTH"].get("0.300", 0),
            right_product["source_board_via_drills_mm"].get("0.300", 0),
        )
        self.assertEqual(
            report["products"]["coupon"]["drill_tools_mm"],
            {
                "PTH": {"1.500": 6, "2.000": 9},
                "NPTH": {"1.650": 3, "1.700": 6, "3.000": 6, "5.000": 3},
            },
        )

    def test_canonical_hash_policy_accepts_crlf_and_exact_index_snapshot(self) -> None:
        from tools.canonical_hash import HASH_POLICY, sha256_file

        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest.get("hash_policy"), HASH_POLICY)
        srs = (ROOT / "docs/spec/10.product-architecture.srs.md").read_text(encoding="utf-8")
        self.assertIn("Three focused fabrication tests", srs)
        self.assertIn("candidate staged snapshot", srs)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            lf = root / "lf.gbr"
            crlf = root / "crlf.gbr"
            lf.write_bytes(b"G04 alpha*\nM02*\n")
            crlf.write_bytes(b"G04 alpha*\r\nM02*\r\n")
            self.assertEqual(sha256_file(lf), sha256_file(crlf))
            snapshot_manifest = materialize_index_fabrication_snapshot(root)
            report = analyze_fabrication(snapshot_manifest, root=root)
            snapshot_data = json.loads(snapshot_manifest.read_text(encoding="utf-8"))
            for details in snapshot_data["products"].values():
                archive = root / details["archive"]
                self.assertEqual(
                    details["archive_sha256"], hashlib.sha256(archive.read_bytes()).hexdigest()
                )

        self.assertTrue(report["hash_policy_matches"])
        direct = subprocess.run(
            [sys.executable, "-B", str(ROOT / "tools/verify_kc2_x3_v2_fabrication.py"), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(direct.returncode, 0, direct.stderr)
        for product in report["products"].values():
            self.assertTrue(product["source_board_sha256_matches"])
            self.assertTrue(product["archive_sha256_matches"])
            self.assertEqual(product["file_hash_mismatches"], [])
            self.assertEqual(product["output_file_hash_mismatches"], [])

    def test_hash_policy_gate_and_real_artifact_mutation(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            materialize_index_fabrication_snapshot(root)
            mutated_output = (
                root
                / manifest["products"]["left"]["output_dir"]
                / manifest["products"]["left"]["files"][0]["name"]
            )
            mutated_output.write_bytes(mutated_output.read_bytes() + b"G04 mutation*\n")
            bad_manifest = dict(manifest)
            bad_manifest["hash_policy"] = "raw-bytes-v0"
            bad_manifest_path = root / "bad-fabrication-manifest.json"
            bad_manifest_path.write_text(json.dumps(bad_manifest), encoding="utf-8")
            report = analyze_fabrication(bad_manifest_path, root=root)

        self.assertFalse(report["hash_policy_matches"])
        self.assertTrue(report["products"]["left"]["output_file_hash_mismatches"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
