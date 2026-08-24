from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools.verify_kc2_x3_v2_mechanical import DEFAULT_MANIFEST, ROOT, analyze_mechanical_outputs


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

        self.assertEqual(report["requirement"], "CON-ARCH-004")
        self.assertEqual(report["scale"], 1.0)
        self.assertEqual(set(report["products"]), {"left", "right", "coupon"})
        for name, product in report["products"].items():
            self.assertTrue(product["source_board_exists"])
            self.assertTrue(product["source_board_sha256_matches"])
            self.assertEqual(set(product["drawings"]), {"top", "bottom"})
            for drawing in product["drawings"].values():
                self.assertTrue(drawing["exists"])
                self.assertTrue(drawing["pdf_header_valid"])
                self.assertTrue(drawing["sha256_matches"])
                self.assertGreater(drawing["size"], 1000)
            if name in {"left", "right"}:
                self.assertTrue(product["outline_svg"]["exists"])
                self.assertTrue(product["outline_svg"]["svg_header_valid"])
                self.assertTrue(product["outline_svg"]["sha256_matches"])
                self.assertEqual(product["outline_svg"]["scale"], 1.0)
                self.assertFalse(product["outline_svg"]["has_trailing_whitespace"])

    def test_canonical_hash_policy_accepts_crlf_and_exact_index_snapshot(self) -> None:
        from tools.canonical_hash import HASH_POLICY, sha256_file

        manifest = json.loads(DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest.get("hash_policy"), HASH_POLICY)
        srs = (ROOT / "docs/spec/10.product-architecture.srs.md").read_text(encoding="utf-8")
        self.assertIn("three focused mechanical tests", srs)
        self.assertIn("candidate staged snapshot", srs)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
