"""Focused tests for the CON-ARCH-004 KC2 X3 V2 ZMK firmware."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from tools import verify_kc2_x3_v2_zmk_firmware as verifier


class V2FirmwareContractTests(unittest.TestCase):
    def test_build_evidence_hash_policy_accepts_crlf_and_exact_index_snapshot(self) -> None:
        from tools.canonical_hash import HASH_POLICY, sha256_file

        manifest = verifier.read_build_evidence()
        self.assertEqual(manifest.get("hash_policy"), HASH_POLICY)
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            lf = root / "lf.txt"
            crlf = root / "crlf.txt"
            lf.write_bytes(b"alpha\nbeta\n")
            crlf.write_bytes(b"alpha\r\nbeta\r\n")
            self.assertEqual(sha256_file(lf), sha256_file(crlf))

            manifest_relative = verifier.BUILD_EVIDENCE_PATH.relative_to(verifier.ROOT)
            snapshot_paths = (
                *verifier.BUILD_SOURCE_PATHS,
                *verifier.BUILD_METADATA_PATHS,
                manifest_relative,
            )
            candidate_index = root / "candidate.index"
            environment = os.environ.copy()
            environment["GIT_INDEX_FILE"] = str(candidate_index)
            subprocess.run(
                ["git", "read-tree", "HEAD"],
                cwd=verifier.ROOT,
                env=environment,
                check=True,
            )
            subprocess.run(
                ["git", "add", "-f", "--", *(path.as_posix() for path in snapshot_paths)],
                cwd=verifier.ROOT,
                env=environment,
                check=True,
            )
            for relative in snapshot_paths:
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(
                    subprocess.check_output(
                        ["git", "show", f":{relative.as_posix()}"],
                        cwd=verifier.ROOT,
                        env=environment,
                    )
                )
            manifest_path = root / manifest_relative
            errors, report = verifier.verify_build_evidence(
                manifest_path=manifest_path,
                root=root,
                artifact_paths={
                    "left": root / "missing-left.uf2",
                    "right": root / "missing-right.uf2",
                },
            )

        self.assertEqual(errors, [])
        self.assertTrue(report["hash_policy_verified"])
        self.assertTrue(report["manifest_provenance_verified"])
        direct = subprocess.run(
            [sys.executable, "-B", str(Path(verifier.__file__)), "--help"],
            cwd=verifier.ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(direct.returncode, 0, direct.stderr)

    def test_build_evidence_reports_present_artifacts_when_manifest_is_unreadable(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            present = root / "left.uf2"
            valid_uf2_block = bytearray(512)
            struct.pack_into(
                "<IIIIIIII",
                valid_uf2_block,
                0,
                0x0A324655,
                0x9E5D5157,
                0,
                0x2000,
                256,
                0,
                1,
                0,
            )
            struct.pack_into("<I", valid_uf2_block, 508, 0x0AB16F30)
            present.write_bytes(valid_uf2_block)
            manifests = {
                "missing": root / "missing-build-evidence.json",
                "corrupt": root / "corrupt-build-evidence.json",
            }
            manifests["corrupt"].write_text("{", encoding="utf-8")

            for case, manifest_path in manifests.items():
                with self.subTest(case=case):
                    errors, report = verifier.verify_build_evidence(
                        manifest_path=manifest_path,
                        artifact_paths={
                            "left": present,
                            "right": root / "missing-right.uf2",
                        },
                    )

                    self.assertTrue(any("Cannot read V2 build evidence" in error for error in errors))
                    self.assertFalse(report["manifest_provenance_verified"])
                    self.assertEqual(
                        report["local_artifacts"],
                        {
                            "left": {"present": True, "verified": False},
                            "right": {"present": False, "verified": False},
                        },
                    )

    def test_build_evidence_binds_every_current_input_and_local_uf2(self) -> None:
        errors, report = verifier.verify_build_evidence()

        self.assertEqual(errors, [])
        self.assertTrue(report["manifest_provenance_verified"])
        self.assertTrue(report["hash_policy_verified"])
        self.assertTrue(report["hardware_compatibility_verified"])
        self.assertEqual(
            set(report["source_digests_verified"]),
            {path.as_posix() for path in verifier.BUILD_SOURCE_PATHS},
        )
        self.assertEqual(
            set(report["metadata_digests_verified"]),
            {path.as_posix() for path in verifier.BUILD_METADATA_PATHS},
        )
        self.assertEqual(
            report["local_artifacts"],
            {
                side: {"present": path.is_file(), "verified": path.is_file()}
                for side, path in verifier.LOCAL_ARTIFACT_PATHS.items()
            },
        )

    def test_build_evidence_rejects_mutated_source_and_missing_digest(self) -> None:
        manifest = verifier.read_build_evidence()
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in (*verifier.BUILD_SOURCE_PATHS, *verifier.BUILD_METADATA_PATHS):
                destination = root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(verifier.ROOT / relative, destination)

            manifest_path = root / "build-evidence.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            (root / verifier.BUILD_SOURCE_PATHS[0]).write_bytes(
                (root / verifier.BUILD_SOURCE_PATHS[0]).read_bytes() + b"\n# mutation\n"
            )
            manifest["build_inputs"].pop(verifier.BUILD_SOURCE_PATHS[1].as_posix())
            manifest["hardware_compatibility"]["scan_timing"][
                "recorded_wait_between_outputs_us"
            ] = 1
            manifest["hash_policy"] = "raw-bytes-v0"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            errors, report = verifier.verify_build_evidence(
                manifest_path=manifest_path,
                root=root,
                artifact_paths={
                    "left": root / "missing-left.uf2",
                    "right": root / "missing-right.uf2",
                },
            )

        self.assertTrue(any("digest mismatch" in error for error in errors))
        self.assertTrue(any("build_inputs source set" in error for error in errors))
        self.assertTrue(any("1N4148W hardware compatibility" in error for error in errors))
        self.assertTrue(any("hash policy" in error for error in errors))
        self.assertFalse(report["manifest_provenance_verified"])
        self.assertFalse(report["hardware_compatibility_verified"])
        self.assertEqual(report["local_artifacts"]["left"], {"present": False, "verified": False})
        self.assertEqual(report["local_artifacts"]["right"], {"present": False, "verified": False})

    def test_build_evidence_rejects_present_artifact_with_mutated_uf2_magic(self) -> None:
        with TemporaryDirectory() as temporary:
            bad = Path(temporary) / "left.uf2"
            bad_block = bytearray(512)
            bad_block[0:4] = bytes.fromhex("5546320a")
            bad_block[4:8] = bytes.fromhex("57515d9e")
            bad.write_bytes(bad_block)
            errors, report = verifier.verify_build_evidence(
                artifact_paths={"left": bad, "right": Path(temporary) / "missing-right.uf2"}
            )

        self.assertTrue(any("left local UF2" in error for error in errors))
        self.assertTrue(any("magic is invalid" in error for error in errors))
        self.assertEqual(report["local_artifacts"]["left"], {"present": True, "verified": False})

    def test_build_evidence_allows_absent_ignored_local_artifacts_without_claiming_verification(self) -> None:
        with TemporaryDirectory() as temporary:
            missing_root = Path(temporary)
            errors, report = verifier.verify_build_evidence(
                artifact_paths={
                    "left": missing_root / "left.uf2",
                    "right": missing_root / "right.uf2",
                }
            )

        self.assertEqual(errors, [])
        self.assertTrue(report["manifest_provenance_verified"])
        self.assertEqual(
            report["local_artifacts"],
            {
                "left": {"present": False, "verified": False},
                "right": {"present": False, "verified": False},
            },
        )

    def test_readme_documents_reproducible_pinned_build(self) -> None:
        readme = (verifier.SHIELD_DIR / "README.md").read_text(encoding="utf-8")

        self.assertIn("ZMK v0.3.0", readme)
        self.assertIn("edf5c0814fd3ea202e43aad2d68fd32e882a518c", readme)
        self.assertIn("-b nice_nano_v2", readme)
        self.assertIn("86c9a777c29d7f1c6f178d8df8aa4f5ecf8e8f75b7fc3daa1ca4842e761c2561", readme)
        self.assertIn("92c8dd1175de2c19505d3ca3487bcc8baa1d03a581c6de13c191ca63743e9b35", readme)
        self.assertIn("423424 bytes", readme)
        self.assertIn("340992 bytes", readme)
        self.assertIn("-DSHIELD=kc2_x3_v2_left", readme)
        self.assertIn("-DSHIELD=kc2_x3_v2_right", readme)
        self.assertIn("-DZMK_EXTRA_MODULES=", readme)
        self.assertIn("firmware/build/kc2_x3_v2_left", readme)
        self.assertIn("firmware/build/kc2_x3_v2_right", readme)
        self.assertIn("firmware/out/kc2_x3_v2_left.uf2", readme)
        self.assertIn("firmware/out/kc2_x3_v2_right.uf2", readme)
        self.assertIn("kc2_x3_v2_build_evidence.json", readme)
        self.assertIn("manifest_provenance_verified", readme)
        self.assertIn("ignored and absent", readme)

    def test_srs_build_evidence_names_sha_bound_manifest_and_optional_local_artifacts(self) -> None:
        srs = (verifier.ROOT / "docs/spec/10.product-architecture.srs.md").read_text(encoding="utf-8")

        self.assertIn("kc2_x3_v2_build_evidence.json", srs)
        self.assertIn("all current shield build-input SHA-256", srs)
        self.assertIn("ignored local uf2", srs.lower())
        self.assertIn("Fourteen focused tests", srs)
        self.assertIn("lf-normalized-utf8-text-else-raw-v1", srs)
        self.assertIn("candidate staged snapshot", srs)
        self.assertIn("tracked build-evidence manifest", srs)
        self.assertNotIn("Eleven focused tests", srs)
        self.assertNotIn("Twelve focused tests", srs)
        self.assertNotIn("Thirteen focused tests", srs)
        self.assertNotIn("staged build-evidence manifest", srs)

    def test_exact_v5_transform_and_half_counts(self) -> None:
        transform = verifier.read_transform()

        self.assertEqual(len(transform), 70)
        self.assertEqual(len(verifier.positions_for_half(transform, "left")), 31)
        self.assertEqual(len(verifier.positions_for_half(transform, "right")), 39)
        self.assertEqual(
            [len([position for position in transform if position[0] == row]) for row in range(5)],
            [15, 14, 14, 15, 12],
        )
        self.assertEqual(
            [position for position in transform if position[0] == 4],
            [(4, 0), (4, 1), (4, 2), (4, 3), (4, 4), (4, 7), (4, 8), (4, 9), (4, 10), (4, 11), (4, 12), (4, 13)],
        )

    def test_default_layer_is_exact_v5_behavior_order(self) -> None:
        bindings = verifier.read_layer("default_layer")

        self.assertEqual(bindings, verifier.EXPECTED_DEFAULT_BINDINGS)
        self.assertEqual(len(bindings), 70)
        self.assertEqual(bindings[50:58], [
            "&kp N", "&kp M", "&kp COMMA", "&kp DOT", "&kp FSLH",
            "&kp RSHFT", "&kp UP", "&mo 1",
        ])
        self.assertNotIn("&kp HOME", bindings)
        self.assertNotIn("&kp PG_UP", bindings)
        self.assertNotIn("&kp PG_DN", bindings)
        self.assertEqual(bindings[58:63], ["&kp LCTRL", "&mo 1", "&kp LALT", "&kp SPACE", "&kp SPACE"])
        self.assertNotIn("&kp LGUI", bindings)
        self.assertEqual(bindings[67:70], ["&kp LEFT", "&kp DOWN", "&kp RIGHT"])

        fn_bindings = verifier.read_layer("fn_layer")
        fn2_bindings = verifier.read_layer("fn_layer2")
        self.assertEqual(fn_bindings, verifier.EXPECTED_FN_BINDINGS)
        self.assertEqual(fn2_bindings, verifier.EXPECTED_FN2_BINDINGS)
        self.assertEqual(len(fn_bindings), 70)
        self.assertEqual(len(fn2_bindings), 70)
        self.assertEqual(
            fn_bindings[58:70],
            ["&trans", "&mo 2", "&trans", "&kp ESC", "&kp ESC", "&trans", "&trans", "&trans", "&trans", "&kp HOME", "&kp PG_DN", "&kp END"],
        )

    def test_alt_fn_combo_produces_left_gui(self) -> None:
        combo = verifier.read_combo("left_alt_fn_win")

        self.assertEqual(combo["key_positions"], [59, 60])
        self.assertEqual(combo["binding"], "&kp LGUI")
        self.assertEqual(combo["timeout_ms"], 50)
        self.assertTrue(combo["global_layers"])
        self.assertTrue(combo["release_on_first_key"])

        restricted = verifier.parse_combo(
            "left_alt_fn_win { timeout-ms = <50>; key-positions = <59 60>; "
            "bindings = <&kp LGUI>; layers = <0>; slow-release;\n};",
            "left_alt_fn_win",
        )
        self.assertFalse(restricted["global_layers"])
        self.assertFalse(restricted["release_on_first_key"])

    def test_right_overlay_uses_eight_board_columns(self) -> None:
        pins = verifier.read_overlay_pins("right")

        self.assertEqual(pins["cols"], verifier.EXPECTED_PINS["right"]["cols"])
        self.assertEqual(len(pins["cols"]), 8)
        self.assertNotIn((0, 31), pins["cols"])
        self.assertEqual(pins["cols"][-1], (0, 29))

    def test_variant_metadata_states_supported_assembly_modes(self) -> None:
        metadata = verifier.read_variant_metadata()

        self.assertEqual(metadata["variant"], "kc2-x3-v2")
        self.assertEqual(metadata["key_count"], {"left": 31, "right": 39, "total": 70})
        self.assertEqual(metadata["layout"], "70-key-v5-no-stabilizer")
        self.assertEqual(
            metadata["left_alt_fn_win_combo"],
            {
                "positions": [59, 60],
                "timeout_ms": 50,
                "binding": "LGUI",
                "layers": "all",
                "release": "first-constituent-key",
            },
        )
        self.assertEqual(metadata["supported_assembly"], ["choc-v2-bottom-socket", "mx-direct-solder"])
        self.assertEqual(metadata["unsupported_assembly"], ["choc-v1", "choc-v2-direct-solder", "mx-hotswap"])
        self.assertEqual(metadata["battery_leads"], "direct-to-nice-nano-b-plus-b-minus")

    def test_1n4148w_transition_preserves_firmware_and_documents_pending_physical_scan_gate(self) -> None:
        evidence = verifier.read_build_evidence()

        self.assertEqual(
            evidence["hardware_compatibility"],
            verifier.EXPECTED_HARDWARE_COMPATIBILITY,
        )
        self.assertEqual(evidence["artifacts"], verifier.EXPECTED_BUILD_ARTIFACTS)
        self.assertEqual(
            evidence["build_inputs"],
            {
                path.as_posix(): verifier.sha256_file(verifier.ROOT / path)
                for path in verifier.BUILD_SOURCE_PATHS
            },
        )

        for side in ("left", "right"):
            overlay = (verifier.SHIELD_DIR / f"kc2_x3_v2_{side}.overlay").read_text(
                encoding="utf-8"
            )
            self.assertIn('diode-direction = "col2row";', overlay)
            self.assertNotIn("CONFIG_ZMK_KSCAN_MATRIX_WAIT", overlay)
            self.assertNotIn("wait-before-inputs", overlay)
            self.assertNotIn("wait-between-outputs", overlay)

        firmware_readme = (verifier.SHIELD_DIR / "README.md").read_text(encoding="utf-8")
        hardware_readme = (
            verifier.ROOT / "hardware/kicad/draft/x3-v2/README.md"
        ).read_text(encoding="utf-8")
        housing_readme = (
            verifier.ROOT / "hardware/case/draft/x3-v2/README.md"
        ).read_text(encoding="utf-8")
        summary = (verifier.ROOT / "docs/spec.md").read_text(encoding="utf-8")
        srs = (
            verifier.ROOT / "docs/spec/10.product-architecture.srs.md"
        ).read_text(encoding="utf-8")
        generation = json.loads(
            (
                verifier.ROOT
                / "hardware/kicad/draft/x3-v2/kc2_x3_v2_generation_manifest.json"
            ).read_text(encoding="utf-8")
        )

        for document in (firmware_readme, hardware_readme, summary, srs):
            self.assertIn("Diodes Incorporated", document)
            self.assertIn("1N4148W-13-F", document)
            self.assertIn("SOD-123", document)

        self.assertIn("70", hardware_readme)
        self.assertIn("B.Cu", hardware_readme)
        self.assertIn("pad 1", hardware_readme)
        self.assertIn("cathode", hardware_readme.lower())
        self.assertIn("mirrored", hardware_readme.lower())
        self.assertIn("3.0 V", hardware_readme)
        self.assertIn("3.3 V", hardware_readme)
        self.assertIn("same-row", hardware_readme)
        self.assertIn("same-column", hardware_readme)
        self.assertIn("zero-wait", hardware_readme)
        self.assertIn("not orderable", hardware_readme.lower())

        self.assertIn("kc2_left-x3-v2-70-1n4148w-p3.dsn", hardware_readme)
        self.assertIn("kc2_right-x3-v2-70-1n4148w-p3.dsn", hardware_readme)
        self.assertIn("reviewed controller-r3 SES", hardware_readme)
        self.assertIn("controller-r3", srs)
        self.assertIn("controller-r3", summary)
        self.assertNotIn("current-MH `kc2_left/right-x3-v2-70-es1b-mh-r2.dsn`", srs)
        self.assertNotIn("현재 M1.4-hole-aware trackless route input은 `kc2_left-x3-v2-70-es1b-mh-r2.dsn`", summary)
        self.assertNotIn("kc2_left-x3-v2-70-v5-r1", hardware_readme)
        self.assertNotIn("kc2_right-x3-v2-71-r12", hardware_readme)

        self.assertIn("no firmware source or UF2 change", firmware_readme)
        self.assertIn("zero-wait", firmware_readme)
        self.assertIn("physical coupon", firmware_readme)

        self.assertIn("`1.5250 mm`", housing_readme)
        self.assertIn("`1.55 mm`", housing_readme)
        self.assertIn("`4.3902 mm`", housing_readme)
        self.assertIn("31/39 key-load support network", housing_readme)
        self.assertIn("P3 reinforcement", summary)
        self.assertIn(
            "7de01a7f0c60585c1845ab3ad17c2b7d18e17ae8c2090a3594e6edf0cbf9d7cf",
            summary,
        )
        self.assertIn(
            "b4173e7bb16189690b06bc3a8d6487e8c56e7e69100e6c04d798d687213f2adc",
            summary,
        )
        self.assertNotIn("현재 둥근머리 P1", summary)
        self.assertIn("29/29 tests", srs)
        self.assertIn(
            "exact fastener, keycap-skirt, deflection, service, and RF gates remain open",
            srs,
        )
        self.assertNotIn("Seventeen focused housing tests pass", srs)
        self.assertNotIn("Fourteen focused housing tests pass", srs)
        self.assertNotIn("Twelve focused housing tests pass", srs)

        self.assertEqual(
            generation["canonical_route_evidence"],
            {
                "left": {
                    "dsn": "hardware/kicad/draft/x3-v2/autoroute/kc2_left-x3-v2-70-1n4148w-p3.dsn",
                    "dsn_role": "current_mh_compact_controller_trackless_routing_input",
                    "dsn_mounting_hole_count": 8,
                    "session_source_dsn": "hardware/kicad/draft/x3-v2/autoroute/kc2_left-x3-v2-70-1n4148w-p3.dsn",
                    "session_source_dsn_sha256": "3171f44d8c65a5881e6f9d3c52adaf22b5268c68559ef0d136fd6ab9f943a58c",
                    "ses": "hardware/kicad/draft/x3-v2/autoroute/kc2_left-x3-v2-70-1n4148w-p3.ses",
                    "ses_role": "reviewed_matrix_import_plus_exact_edge_cleanup_and_power_reset_service_routing",
                    "dsn_sha256": "3171f44d8c65a5881e6f9d3c52adaf22b5268c68559ef0d136fd6ab9f943a58c",
                    "ses_sha256": "eeb142f28e5077bb4f523c9f85a9e547c9f3a38f740596cbe6df4bf269d18c39",
                    "dsn_default_clearance_internal_units": 300,
                    "dsn_clearances_internal_units": {
                        "global": 300,
                        "kicad_default": 300,
                    },
                    "final_track_via_count": 590,
                    "route_digest_sha256": "b8adeac705f846714f7f201b63487369ef486cb1624df8d0ddbb8cde3053e316",
                },
                "right": {
                    "dsn": "hardware/kicad/draft/x3-v2/autoroute/kc2_right-x3-v2-70-1n4148w-p3.dsn",
                    "dsn_role": "current_mh_compact_controller_trackless_routing_input",
                    "dsn_mounting_hole_count": 9,
                    "session_source_dsn": "hardware/kicad/draft/x3-v2/autoroute/kc2_right-x3-v2-70-1n4148w-p3.dsn",
                    "session_source_dsn_sha256": "bf25cb75dbab88693fec22038a5b90583221bdb6fbc41036cd6e328c7a863a3b",
                    "ses": "hardware/kicad/draft/x3-v2/autoroute/kc2_right-x3-v2-70-1n4148w-p3.ses",
                    "ses_role": "reviewed_matrix_import_plus_exact_edge_cleanup_and_power_reset_service_routing",
                    "dsn_sha256": "bf25cb75dbab88693fec22038a5b90583221bdb6fbc41036cd6e328c7a863a3b",
                    "ses_sha256": "ac703dbde3f35e4dffdb35de5c8d09d4f12a56ba09439ef5b02473200e55b039",
                    "dsn_default_clearance_internal_units": 300,
                    "dsn_clearances_internal_units": {
                        "global": 300,
                        "kicad_default": 300,
                    },
                    "final_track_via_count": 766,
                    "route_digest_sha256": "530d6927eacd7e57a48cb6c62e5c5916ef1f4b3f21d67b592e80962ef7af4c1b",
                },
            },
        )
        self.assertEqual(
            generation["firmware_matrix_compatibility"],
            {
                "diode_direction": "col2row",
                "pad_1": "row_cathode",
                "pad_2": "per_key_switch_anode",
                "scan_delay_changed": False,
            },
        )
        self.assertEqual(
            generation["physical_scan_validation"],
            {
                "status": "pending",
                "supply_volts": [3.0, 3.3],
                "patterns": ["maximum_same_row", "maximum_same_column"],
                "orderable": False,
            },
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
