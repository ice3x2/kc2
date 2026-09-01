from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import pcbnew

from tools.canonical_hash import HASH_POLICY, sha256_bytes, sha256_file
from tools.verify_kc2_x3_v2_coupon import analyze_coupon


ROOT = Path(__file__).resolve().parents[1]
COUPON_RELATIVE_DIR = Path("hardware/kicad/draft/x3-v2/coupon")
COUPON_BOARD_NAME = "kc2_x3_v2_switch_coupon.kicad_pcb"
COUPON_DRC_NAME = "kc2_x3_v2_switch_coupon.drc.json"
COUPON_EVIDENCE_NAME = "kc2_x3_v2_switch_coupon_drc_evidence.json"
COUPON_DIR = ROOT / COUPON_RELATIVE_DIR
COUPON_BOARD = COUPON_DIR / COUPON_BOARD_NAME
COUPON_DRC_REPORT = COUPON_DIR / COUPON_DRC_NAME


def copy_coupon_drc_evidence_tree(destination: Path) -> tuple[Path, Path, Path]:
    source = ROOT / COUPON_RELATIVE_DIR
    target = destination / COUPON_RELATIVE_DIR
    target.mkdir(parents=True)
    for name in (COUPON_BOARD_NAME, COUPON_DRC_NAME, COUPON_EVIDENCE_NAME):
        shutil.copy2(source / name, target / name)
    return (
        target / COUPON_BOARD_NAME,
        target / COUPON_DRC_NAME,
        target / COUPON_EVIDENCE_NAME,
    )


class V2CouponTests(unittest.TestCase):
    def test_coupon_covers_left_right_socket_and_mx_fit(self) -> None:
        report = analyze_coupon()

        self.assertEqual(report["switch_refs"], ["SW_L", "SW_MX", "SW_R"])
        self.assertEqual(
            report["switch_footprint_names"], {"SW_Choc_V2_Socket_MX_THT"}
        )
        self.assertEqual(
            report["switch_orientations_deg"],
            {"SW_L": 0.0, "SW_MX": 0.0, "SW_R": 180.0},
        )
        self.assertEqual(report["diode_count"], 3)
        self.assertEqual(report["diode_refs"], ["D_L", "D_MX", "D_R"])
        self.assertEqual(
            report["diode_footprint_names"],
            {"D_1N4148W_SOD123_HandSolder_DiodesInc"},
        )
        self.assertEqual(report["diode_value_errors"], [])
        self.assertEqual(report["diode_layer_errors"], [])
        self.assertEqual(report["diode_pad_geometry_errors"], [])
        self.assertEqual(report["diode_pin_net_errors"], [])
        self.assertEqual(report["diode_clearance_errors"], [])
        self.assertEqual(report["diode_body_geometry_errors"], [])
        self.assertEqual(report["diode_tool_approach_errors"], [])
        self.assertEqual(
            set(report["diode_tool_approach_directions"]), {"D_L", "D_MX", "D_R"}
        )
        self.assertGreaterEqual(report["minimum_diode_edge_clearance_mm"], 1.3)
        self.assertGreaterEqual(report["minimum_diode_switch_pad_clearance_mm"], 1.0)
        self.assertGreaterEqual(report["minimum_diode_npth_clearance_mm"], 1.0)
        self.assertEqual(report["polarity_mark_errors"], [])
        self.assertEqual(report["probe_refs"], [
            "TP_L_ANODE", "TP_L_COL", "TP_L_ROW",
            "TP_MX_ANODE", "TP_MX_COL", "TP_MX_ROW",
            "TP_R_ANODE", "TP_R_COL", "TP_R_ROW",
        ])
        self.assertEqual(report["probe_pad_errors"], [])
        self.assertEqual(report["probe_net_errors"], [])
        self.assertEqual(report["manifest_errors"], [])
        self.assertEqual(report["alternate_contact_net_mismatches"], [])
        self.assertEqual(report["drc_violation_count"], 0)
        self.assertEqual(report["drc_unconnected_count"], 0)
        self.assertEqual(report["drc_evidence_errors"], [])
        self.assertGreaterEqual(report["default_netclass_clearance_mm"], 0.3)
        self.assertLessEqual(report["board_size_mm"][0], 80.0)
        self.assertLessEqual(report["board_size_mm"][1], 60.1)
        self.assertIn("CHOC V1 UNSUPPORTED", report["board_text"].upper())
        self.assertIn("DO NOT POPULATE BOTH MODES", report["board_text"].upper())
        self.assertIn("CHOC RIGHT BOARD", report["board_text"].upper())
        self.assertIn("1N4148W-13-F", report["board_text"].upper())
        self.assertFalse(report["order_ready"])
        self.assertEqual(
            report["physical_evidence_status"],
            "pending_fabrication_population_and_measurement",
        )
        self.assertIn("non_1u", report["coverage_limitations"])
        self.assertIn("scan_stress", report["coverage_limitations"])
        self.assertIn(
            "maximum same-row/same-column",
            report["coverage_limitations"]["scan_stress"],
        )
        self.assertEqual(
            set(report["planned_measurements"]),
            {"low_current_vf", "row_high_3v0_3v3", "zero_wait_scan"},
        )

    def test_coupon_rejects_wrong_1n4148w_pin_net(self) -> None:
        source = Path(
            "hardware/kicad/draft/x3-v2/coupon/kc2_x3_v2_switch_coupon.kicad_pcb"
        )
        board = pcbnew.LoadBoard(str(source))
        diode = board.FindFootprintByReference("D_L")
        wrong_net = board.FindNet("D_L_ANODE")
        next(pad for pad in diode.Pads() if pad.GetNumber() == "1").SetNet(wrong_net)
        with tempfile.TemporaryDirectory() as temporary_directory:
            mutated = Path(temporary_directory) / source.name
            pcbnew.SaveBoard(str(mutated), board)
            report = analyze_coupon(mutated)
        self.assertTrue(report["diode_pin_net_errors"])

    def test_coupon_rejects_noncontrolled_1n4148w_hand_solder_land(self) -> None:
        source = Path(
            "hardware/kicad/draft/x3-v2/coupon/kc2_x3_v2_switch_coupon.kicad_pcb"
        )
        board = pcbnew.LoadBoard(str(source))
        diode = board.FindFootprintByReference("D_MX")
        next(pad for pad in diode.Pads() if pad.GetNumber() == "2").SetSize(
            pcbnew.VECTOR2I(pcbnew.FromMM(2.0), pcbnew.FromMM(1.8))
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            mutated = Path(temporary_directory) / source.name
            pcbnew.SaveBoard(str(mutated), board)
            report = analyze_coupon(mutated)
        self.assertTrue(report["diode_pad_geometry_errors"])

    def test_coupon_rejects_missing_bottom_mirrored_polarity_mark(self) -> None:
        source = Path(
            "hardware/kicad/draft/x3-v2/coupon/kc2_x3_v2_switch_coupon.kicad_pcb"
        )
        board = pcbnew.LoadBoard(str(source))
        mark = next(
            drawing
            for drawing in board.GetDrawings()
            if isinstance(drawing, pcbnew.PCB_TEXT)
            and drawing.GetText() == "D_R K/P1 ROW"
        )
        mark.SetMirrored(False)
        with tempfile.TemporaryDirectory() as temporary_directory:
            mutated = Path(temporary_directory) / source.name
            pcbnew.SaveBoard(str(mutated), board)
            report = analyze_coupon(mutated)
        self.assertTrue(report["polarity_mark_errors"])

    def test_coupon_rejects_1n4148w_switch_clearance_regression(self) -> None:
        source = Path(
            "hardware/kicad/draft/x3-v2/coupon/kc2_x3_v2_switch_coupon.kicad_pcb"
        )
        board = pcbnew.LoadBoard(str(source))
        board.FindFootprintByReference("D_L").SetPosition(
            board.FindFootprintByReference("SW_L").GetPosition()
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            mutated = Path(temporary_directory) / source.name
            pcbnew.SaveBoard(str(mutated), board)
            report = analyze_coupon(mutated)
        self.assertTrue(report["diode_clearance_errors"])

    def test_coupon_rejects_probe_net_regression(self) -> None:
        source = Path(
            "hardware/kicad/draft/x3-v2/coupon/kc2_x3_v2_switch_coupon.kicad_pcb"
        )
        board = pcbnew.LoadBoard(str(source))
        probe = board.FindFootprintByReference("TP_MX_ROW")
        next(iter(probe.Pads())).SetNet(board.FindNet("D_MX_ANODE"))
        with tempfile.TemporaryDirectory() as temporary_directory:
            mutated = Path(temporary_directory) / source.name
            pcbnew.SaveBoard(str(mutated), board)
            report = analyze_coupon(mutated)
        self.assertTrue(report["probe_net_errors"])

    def test_coupon_rejects_stale_board_drc_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            board, _, evidence = copy_coupon_drc_evidence_tree(
                Path(temporary_directory)
            )
            board.write_bytes(board.read_bytes() + b"\n")
            report = analyze_coupon(board, drc_evidence_path=evidence)
        self.assertIn(
            "coupon DRC evidence board SHA-256 mismatch",
            report["drc_evidence_errors"],
        )

    def test_coupon_rejects_stale_drc_report_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            board, drc_report, evidence = copy_coupon_drc_evidence_tree(
                Path(temporary_directory)
            )
            drc_report.write_bytes(drc_report.read_bytes() + b"\n")
            report = analyze_coupon(board, drc_evidence_path=evidence)
        self.assertIn(
            "coupon DRC evidence report SHA-256 mismatch",
            report["drc_evidence_errors"],
        )

    def test_coupon_rejects_self_consistent_extra_drc_ignore(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            board, drc_report, evidence_path = copy_coupon_drc_evidence_tree(
                Path(temporary_directory)
            )
            drc = json.loads(drc_report.read_text(encoding="utf-8"))
            drc["ignored_checks"].append(
                {"key": "silk_over_copper", "description": "unreviewed mutation"}
            )
            drc_report.write_text(json.dumps(drc, indent=2) + "\n", encoding="utf-8")
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["board"]["drc_report_sha256"] = sha256_file(drc_report)
            evidence["board"]["ignored_checks"] = sorted(
                item["key"] for item in drc["ignored_checks"]
            )
            evidence_path.write_text(
                json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
            )
            report = analyze_coupon(board, drc_evidence_path=evidence_path)
        self.assertIn(
            "coupon DRC ignored_checks differ from the reviewed allowlist",
            report["drc_evidence_errors"],
        )

    def test_coupon_rejects_missing_reviewed_ignore_rationale(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            board, _, evidence_path = copy_coupon_drc_evidence_tree(
                Path(temporary_directory)
            )
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            evidence["board"]["ignored_check_rationale"].pop("footprint_type_mismatch")
            evidence_path.write_text(
                json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
            )
            report = analyze_coupon(board, drc_evidence_path=evidence_path)
        self.assertIn(
            "coupon DRC evidence ignored-check rationale differs from the reviewed contract",
            report["drc_evidence_errors"],
        )

    def test_coupon_rejects_self_consistent_drc_policy_and_path_mutations(self) -> None:
        mutations = {
            "board_path": ("board_path", "wrong/coupon.kicad_pcb"),
            "report_path": ("drc_report_path", "wrong/coupon.drc.json"),
            "kicad_version": ("kicad_version", "9.0.0"),
            "date": ("date", "not-an-iso-timestamp"),
            "included_severities": ("included_severities", ["error", "warning"]),
        }
        for label, (field, value) in mutations.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary_directory:
                board, drc_report, evidence_path = copy_coupon_drc_evidence_tree(
                    Path(temporary_directory)
                )
                evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
                if field in {"kicad_version", "date", "included_severities"}:
                    drc = json.loads(drc_report.read_text(encoding="utf-8"))
                    drc[field] = value
                    drc_report.write_text(
                        json.dumps(drc, indent=2) + "\n", encoding="utf-8"
                    )
                    evidence["board"]["drc_report_sha256"] = sha256_file(drc_report)
                evidence["board"][field] = value
                evidence_path.write_text(
                    json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
                )
                report = analyze_coupon(board, drc_evidence_path=evidence_path)
            self.assertTrue(report["drc_evidence_errors"], label)

    def test_coupon_drc_evidence_writer_is_reproducible(self) -> None:
        from tools.generate_kc2_x3_v2_coupon_drc_evidence import write_drc_evidence

        tracked = ROOT / COUPON_RELATIVE_DIR / COUPON_EVIDENCE_NAME
        with tempfile.TemporaryDirectory() as temporary_directory:
            generated = Path(temporary_directory) / COUPON_EVIDENCE_NAME
            write_drc_evidence(generated)
            self.assertEqual(generated.read_bytes(), tracked.read_bytes())
            self.assertNotIn(b"\r\n", generated.read_bytes())
            from tools.verify_kc2_x3_v2_coupon import verify_coupon_drc_evidence

            evidence = json.loads(tracked.read_text(encoding="utf-8"))
            self.assertEqual(evidence["hash_policy"], HASH_POLICY)
            copy = Path(temporary_directory) / "mutated-evidence.json"
            mutated = json.loads(json.dumps(evidence))
            mutated["hash_policy"] = "raw-v0"
            copy.write_text(json.dumps(mutated, indent=2) + "\n", encoding="utf-8")
            errors, _ = verify_coupon_drc_evidence(
                COUPON_BOARD, COUPON_DRC_REPORT, copy
            )
            self.assertIn("coupon DRC evidence canonical hash policy mismatch", errors)

            if (ROOT / ".git").exists():
                for path in (COUPON_BOARD, COUPON_DRC_REPORT):
                    relative = path.relative_to(ROOT).as_posix()
                    staged = subprocess.run(
                        ["git", "show", f":{relative}"],
                        cwd=ROOT,
                        check=True,
                        stdout=subprocess.PIPE,
                    ).stdout
                    with self.subTest(path=relative):
                        self.assertEqual(sha256_file(path), sha256_bytes(staged))

    def test_srs_marks_only_digitally_satisfied_v2_acceptance_criteria(self) -> None:
        srs = (ROOT / "docs/spec/10.product-architecture.srs.md").read_text(
            encoding="utf-8"
        )
        con_arch_004 = srs.split("### CON-ARCH-004", 1)[1].split("\n### ", 1)[0]
        con_arch_006 = srs.split("### CON-ARCH-006", 1)[1].split("\n### ", 1)[0]
        for acceptance_criterion in ("AC-11",):
            self.assertIn(f"- [x] {acceptance_criterion}:", con_arch_004)
        for acceptance_criterion in ("AC-2", "AC-7", "AC-8", "AC-9", "AC-10"):
            self.assertIn(f"- [ ] {acceptance_criterion}:", con_arch_004)
        for acceptance_criterion in ("AC-5", "AC-6", "AC-9", "AC-10"):
            self.assertIn(f"- [x] {acceptance_criterion}:", con_arch_006)
        for acceptance_criterion in ("AC-4", "AC-7", "AC-8", "AC-11"):
            self.assertIn(f"- [ ] {acceptance_criterion}:", con_arch_006)
        self.assertIn("Thirteen focused coupon tests pass", con_arch_004)
        self.assertIn(COUPON_EVIDENCE_NAME, con_arch_004)
        self.assertIn("29/29 housing tests", con_arch_006)
        self.assertNotIn("Twenty-five focused housing tests pass", con_arch_006)
        self.assertNotIn("Seventeen focused housing tests pass", con_arch_006)
        self.assertNotIn("Fourteen focused housing tests pass", con_arch_006)
        self.assertNotIn("Twelve focused housing tests pass", srs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
