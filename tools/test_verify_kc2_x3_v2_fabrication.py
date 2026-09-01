from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from tools.verify_kc2_x3_v2_fabrication import (
    EXPECTED_JLCPCB_PCBA_QUOTE_PROFILE,
    EXPECTED_JLCPCB_PROFILE,
    EXPECTED_MOUNTING_REFERENCE_CENTERS_MM,
    MANIFEST,
    ROOT,
    analyze_fabrication,
    inspect_gerber,
    inspect_mounting_reference_glyphs,
    jlcpcb_pcba_quote_profile_errors,
    jlcpcb_profile_errors,
)
from tools.kc2_x3_v2_output_geometry import (
    parse_board,
    source_j_bat_marking_errors,
)

REQUIREMENT_IDS = {
    "CON-ARCH-004",
    "CON-ARCH-006",
    "CON-ARCH-007",
    "REL-ARCH-001",
}


def rewrite_coupled_archive_entry(
    root: Path,
    manifest_path: Path,
    product: str,
    suffix: str,
    mutate,
) -> None:
    from tools.canonical_hash import sha256_file

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    details = manifest["products"][product]
    archive = root / details["archive"]
    output_dir = root / details["output_dir"]
    with ZipFile(archive) as package:
        payloads = {name: package.read(name) for name in package.namelist()}
    entry = next(name for name in payloads if name.endswith(suffix))
    payloads[entry] = mutate(payloads[entry])
    extracted = output_dir / entry
    extracted.write_bytes(payloads[entry])
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as package:
        for name, payload in payloads.items():
            package.writestr(name, payload)
    for item in details["files"]:
        if item["name"] == entry:
            item["size"] = extracted.stat().st_size
            item["sha256"] = sha256_file(extracted)
    details["archive_sha256"] = sha256_file(archive)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def materialize_index_fabrication_snapshot(root: Path) -> Path:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    paths: set[Path] = set()
    for details in manifest["products"].values():
        paths.add(Path(details["board"]))
        paths.add(Path(details["archive"]))
        paths.add(Path(details["jlcpcb_archive"]))
        output_dir = Path(details["output_dir"])
        paths.update(output_dir / item["name"] for item in details["files"])
        quote = details.get("pcba_quote")
        if quote:
            paths.add(Path(quote["bom"]))
            paths.add(Path(quote["cpl"]))
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

        self.assertEqual(set(report["requirement_ids"]), REQUIREMENT_IDS)
        self.assertTrue(report["requirement_ids_match"])
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
                self.assertEqual(product_report["mounting_reference_glyph_errors"], [])
                self.assertTrue(product_report["drill_geometry_matches"])
                self.assertEqual(product_report["drill_source_geometry_errors"], [])
                self.assertEqual(product_report["gerber_source_geometry_errors"], [])
                self.assertEqual(
                    product_report["drill_tools_mm"],
                    product_report["expected_drill_tools_mm"],
                )
                self.assertGreaterEqual(product_report["archive_entry_count"], 13)
                if product in {"left", "right"}:
                    self.assertEqual(product_report["j_bat_marking_errors"], [])
                    self.assertTrue(product_report["bom_matches_source_board"])
                    self.assertEqual(product_report["bom_errors"], [])

        self.assertEqual(report["products"]["left"]["bottom_paste_flash_count"], 124)
        self.assertEqual(report["products"]["right"]["bottom_paste_flash_count"], 156)
        self.assertEqual(report["products"]["coupon"]["bottom_paste_flash_count"], 12)
        self.assertEqual(
            report["products"]["left"]["mounting_reference_labels"],
            [f"MH{index}" for index in range(1, 9)],
        )
        self.assertEqual(
            report["products"]["right"]["mounting_reference_labels"],
            [f"MH{index}" for index in range(1, 10)],
        )
        self.assertEqual(report["products"]["coupon"]["mounting_reference_labels"], [])
        self.assertEqual(
            list(report["products"]["left"]["mounting_reference_glyphs"]),
            [f"MH{index}" for index in range(1, 9)],
        )
        self.assertEqual(
            list(report["products"]["right"]["mounting_reference_glyphs"]),
            [f"MH{index}" for index in range(1, 10)],
        )

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
            {"1.600": 9, "1.650": 39, "1.700": 78, "2.200": 1, "3.000": 78, "5.000": 39},
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

    def test_jlcpcb_order_archives_and_tented_via_profile_fail_closed(self) -> None:
        report = analyze_fabrication()
        self.assertEqual(report["jlcpcb_profile"], EXPECTED_JLCPCB_PROFILE)
        self.assertEqual(report["jlcpcb_profile_errors"], [])
        for product, details in report["products"].items():
            with self.subTest(product=product):
                self.assertTrue(details["jlcpcb_archive_exists"])
                self.assertTrue(details["jlcpcb_archive_sha256_matches"])
                self.assertEqual(details["jlcpcb_nested_archive_entries"], [])
                self.assertEqual(details["jlcpcb_unexpected_entries"], [])
                self.assertEqual(details["jlcpcb_missing_entries"], [])
                self.assertEqual(details["jlcpcb_archive_entry_count"], 15)
                self.assertEqual(details["via_tenting_errors"], [])
                self.assertEqual(details["mask_open_via_centers"], {"front": [], "back": []})

        mutated = deepcopy(EXPECTED_JLCPCB_PROFILE)
        mutated["via_covering"] = "untented"
        self.assertTrue(jlcpcb_profile_errors(mutated))
        mutated = deepcopy(EXPECTED_JLCPCB_PROFILE)
        mutated["surface_finish"] = "lead_free_hasl"
        self.assertTrue(jlcpcb_profile_errors(mutated))
        mutated = deepcopy(EXPECTED_JLCPCB_PROFILE)
        mutated["confirm_production_file"] = False
        self.assertTrue(jlcpcb_profile_errors(mutated))

    def test_jlcpcb_pcba_quote_contains_only_bottom_diodes_and_choc_sockets(self) -> None:
        from tools.canonical_hash import sha256_file

        report = analyze_fabrication()
        self.assertEqual(
            report["jlcpcb_pcba_quote_profile"],
            EXPECTED_JLCPCB_PCBA_QUOTE_PROFILE,
        )
        self.assertEqual(
            report["jlcpcb_pcba_quote_profile"]["assembled_parts"]["D"][
                "jlcpcb_part_number"
            ],
            "C112342",
        )
        self.assertEqual(
            report["jlcpcb_pcba_quote_profile"]["assembly_service"],
            "none_hand_assembly",
        )
        self.assertEqual(
            report["jlcpcb_pcba_quote_profile"]["parts_procurement"],
            "user_external_mall_procurement",
        )
        self.assertFalse(
            report["jlcpcb_pcba_quote_profile"]["machine_placement_requested"]
        )
        self.assertFalse(
            report["jlcpcb_pcba_quote_profile"]["bom_cpl_upload_authorization"]
        )
        self.assertEqual(
            report["jlcpcb_pcba_quote_profile"]["selected_switch_assembly"],
            "mx_direct_solder",
        )
        self.assertEqual(
            report["jlcpcb_pcba_quote_profile"]["reference_switch_assembly"],
            "choc_socket_alternative_not_selected",
        )
        self.assertTrue(
            report["jlcpcb_pcba_quote_profile"][
                "switch_assemblies_mutually_exclusive"
            ]
        )
        self.assertFalse(
            report["jlcpcb_pcba_quote_profile"][
                "socket_population_for_selected_assembly"
            ]
        )
        self.assertEqual(report["jlcpcb_pcba_quote_profile_errors"], [])
        for product, expected_count in (("left", 31), ("right", 39)):
            with self.subTest(product=product):
                quote = report["products"][product]["pcba_quote"]
                self.assertTrue(quote["bom_exists"])
                self.assertTrue(quote["cpl_exists"])
                self.assertTrue(quote["bom_sha256_matches"])
                self.assertTrue(quote["cpl_sha256_matches"])
                self.assertEqual(quote["errors"], [])
                self.assertEqual(quote["diode_count"], expected_count)
                self.assertEqual(quote["socket_count"], expected_count)
                self.assertEqual(quote["assembled_reference_count"], expected_count * 2)
                self.assertEqual(quote["layers"], ["Bottom"])
                self.assertEqual(quote["lcsc_part_numbers"], ["C112342", "C5333465"])
                self.assertTrue(quote["socket_centroids_are_body_derived"])
                self.assertFalse(quote["order_ready"])

        mutated = deepcopy(EXPECTED_JLCPCB_PCBA_QUOTE_PROFILE)
        mutated["order_ready"] = True
        self.assertTrue(jlcpcb_pcba_quote_profile_errors(mutated))
        mutated = deepcopy(EXPECTED_JLCPCB_PCBA_QUOTE_PROFILE)
        mutated["assembled_reference_families"] = ["D", "SW", "U"]
        self.assertTrue(jlcpcb_pcba_quote_profile_errors(mutated))
        mutated = deepcopy(EXPECTED_JLCPCB_PCBA_QUOTE_PROFILE)
        mutated["selected_switch_assembly"] = "choc_socket"
        mutated["socket_population_for_selected_assembly"] = True
        self.assertTrue(jlcpcb_pcba_quote_profile_errors(mutated))
        mutated = deepcopy(EXPECTED_JLCPCB_PCBA_QUOTE_PROFILE)
        mutated["bom_cpl_upload_authorization"] = True
        self.assertTrue(jlcpcb_pcba_quote_profile_errors(mutated))

        mutations = (
            ("bom", b"Diodes Inc 1N4148W-13-F", b"U1,Diodes Inc 1N4148W-13-F"),
            ("cpl", b"SW1,45.5250mm", b"SW1,45.6250mm"),
        )
        for field, old, new in mutations:
            with self.subTest(coupled_quote_mutation=field), TemporaryDirectory() as temporary:
                root = Path(temporary)
                manifest_path = materialize_index_fabrication_snapshot(root)
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                record = manifest["products"]["left"]["pcba_quote"]
                path = root / record[field]
                payload = path.read_bytes()
                self.assertEqual(payload.count(old), 1)
                path.write_bytes(payload.replace(old, new, 1))
                record[f"{field}_sha256"] = sha256_file(path)
                manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
                mutated_report = analyze_fabrication(manifest_path, root=root)
                self.assertTrue(mutated_report["products"]["left"]["pcba_quote"]["errors"])

    def test_canonical_hash_policy_accepts_crlf_and_exact_index_snapshot(self) -> None:
        from tools.canonical_hash import HASH_POLICY, sha256_file

        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest.get("hash_policy"), HASH_POLICY)
        srs = (ROOT / "docs/spec/10.product-architecture.srs.md").read_text(encoding="utf-8")
        self.assertIn("candidate", srs)
        self.assertIn("fabrication", srs)
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

        payload = (
            ROOT
            / "hardware/kicad/draft/x3-v2/fabrication/left/"
            "kc2_left-x3-v2-F_Silkscreen.gto"
        ).read_bytes()
        original = b"X111795833Y-41062295D01*"
        self.assertEqual(payload.count(original), 1)

        baseline = inspect_mounting_reference_glyphs(
            payload,
            EXPECTED_MOUNTING_REFERENCE_CENTERS_MM["left"],
        )
        self.assertEqual(baseline["errors"], [])
        self.assertEqual(list(baseline["glyphs"]), [f"MH{index}" for index in range(1, 9)])
        self.assertEqual(baseline["glyphs"]["MH1"]["stroke_width_mm"], 0.15)
        self.assertEqual(baseline["glyphs"]["MH1"]["ink_height_mm"], 0.95)

        mutations = {
            "deleted actual glyph stroke": payload.replace(original, b"", 1),
            "changed actual glyph stroke endpoint": payload.replace(
                original,
                b"X111795833Y-41072295D01*",
                1,
            ),
        }
        for name, mutated in mutations.items():
            with self.subTest(name=name):
                # The X2 component attribute survives both mutations, so the old
                # attribute-only check would false-pass.
                self.assertIn("MH1", inspect_gerber(mutated)["component_references"])
                inspection = inspect_mounting_reference_glyphs(
                    mutated,
                    EXPECTED_MOUNTING_REFERENCE_CENTERS_MM["left"],
                )
                self.assertTrue(
                    any(error.startswith("MH1:") for error in inspection["errors"]),
                    inspection,
                )

    def test_source_geometry_rejects_coupled_excellon_and_gerber_coordinate_mutations(self) -> None:
        mutations = (
            ("-PTH.drl", b"X113.272Y-63.45", b"X113.372Y-63.45", "drill_source_geometry_errors"),
            ("-F_Paste.gtp", b"X122187500Y-63450000D03*", b"X122287500Y-63450000D03*", "gerber_source_geometry_errors"),
            ("-B_Paste.gbp", b"X51825000Y-84525000D03*", b"X51925000Y-84525000D03*", "gerber_source_geometry_errors"),
            ("-B_Cu.gbl", b"X51825000Y-84525000D03*", b"X51925000Y-84525000D03*", "gerber_source_geometry_errors"),
            ("-B_Mask.gbs", b"X51825000Y-84525000D03*", b"X51925000Y-84525000D03*", "gerber_source_geometry_errors"),
            (
                "-F_Silkscreen.gto",
                b"X115107738Y-60613855D01*",
                b"",
                "j_bat_marking_errors",
            ),
        )
        for suffix, old, new, field in mutations:
            with self.subTest(suffix=suffix), TemporaryDirectory() as temporary:
                root = Path(temporary)
                manifest_path = materialize_index_fabrication_snapshot(root)
                baseline_report = analyze_fabrication(manifest_path, root=root)
                self.assertEqual(baseline_report["products"]["left"][field], [])

                def mutate(payload: bytes) -> bytes:
                    self.assertEqual(payload.count(old), 1)
                    return payload.replace(old, new, 1)

                rewrite_coupled_archive_entry(root, manifest_path, "left", suffix, mutate)
                report = analyze_fabrication(manifest_path, root=root)
                self.assertTrue(report["products"]["left"][field], report)

    def test_manifest_requirement_and_bom_contracts_fail_closed(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = materialize_index_fabrication_snapshot(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["requirement_ids"] = sorted(REQUIREMENT_IDS - {"CON-ARCH-007"})
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            report = analyze_fabrication(manifest_path, root=root)
        self.assertFalse(report["requirement_ids_match"])

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path = materialize_index_fabrication_snapshot(root)

            def mutate_bom(payload: bytes) -> bytes:
                old = b'"manufacturer_part_number": "pending_physical_procurement_gate"'
                self.assertGreaterEqual(payload.count(old), 1)
                return payload.replace(
                    old,
                    b'"manufacturer_part_number": "unbound_false_confirmation"',
                    1,
                )

            rewrite_coupled_archive_entry(
                root, manifest_path, "left", "-bom.json", mutate_bom
            )
            report = analyze_fabrication(manifest_path, root=root)
        self.assertFalse(report["products"]["left"]["bom_matches_source_board"])
        self.assertTrue(report["products"]["left"]["bom_errors"])

        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        board = parse_board(ROOT / manifest["products"]["left"]["board"])
        self.assertEqual(source_j_bat_marking_errors(board), [])
        for mode in ("swapped", "missing"):
            with self.subTest(j_bat_marking=mode):
                mutated = deepcopy(board)
                texts = mutated["footprints"]["J_BAT1"]["texts"]
                positive = next(item for item in texts if item["text"] == "B+")
                negative = next(item for item in texts if item["text"] == "B-/GND")
                if mode == "swapped":
                    positive["text"], negative["text"] = negative["text"], positive["text"]
                else:
                    negative["text"] = ""
                self.assertTrue(source_j_bat_marking_errors(mutated))


if __name__ == "__main__":
    unittest.main(verbosity=2)
