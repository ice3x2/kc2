import json
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CANONICAL_FILES = (
    "hardware/kicad/kc2_left/kc2_left.kicad_pro",
    "hardware/kicad/kc2_left/kc2_left.kicad_pcb",
    "hardware/kicad/kc2_left/kc2_left.kicad_prl",
    "hardware/kicad/kc2_left/fp-lib-table",
    "hardware/kicad/kc2_right/kc2_right.kicad_pro",
    "hardware/kicad/kc2_right/kc2_right.kicad_pcb",
    "hardware/kicad/kc2_right/kc2_right.kicad_prl",
    "hardware/kicad/kc2_right/fp-lib-table",
    "hardware/kicad/autoroute/kc2_left.dsn",
    "hardware/kicad/autoroute/kc2_left.ses",
    "hardware/kicad/autoroute/kc2_right.dsn",
    "hardware/kicad/autoroute/kc2_right.ses",
    "hardware/kicad/coupon/kc2_switch_coupon.kicad_pcb",
    "hardware/kicad/fabrication/kc2_fabrication_manifest.json",
    "hardware/kicad/fabrication/kc2_left_jlcpcb.zip",
    "hardware/kicad/fabrication/kc2_right_jlcpcb.zip",
    "hardware/kicad/fabrication/kc2_coupon_jlcpcb.zip",
    "hardware/kicad/mechanical/kc2_mechanical_manifest.json",
    "hardware/kicad/renders/kc2_render_manifest.json",
    "hardware/kicad/renders/kc2_left_top.png",
    "hardware/kicad/renders/kc2_left_bottom.png",
    "hardware/kicad/renders/kc2_right_top.png",
    "hardware/kicad/renders/kc2_right_bottom.png",
    "hardware/kicad/renders/kc2_coupon_top.png",
    "hardware/kicad/renders/kc2_coupon_bottom.png",
    "hardware/kicad/kc2_generation_manifest.json",
    "hardware/kicad/kc2_drc_evidence.json",
    "hardware/kicad/kc2_physical_evidence.json",
    "hardware/kicad/README.md",
    "hardware/case/kc2_housing_manifest.json",
    "hardware/case/kc2_housing_clearance.json",
    "hardware/case/kc2_left_lower_housing.step",
    "hardware/case/kc2_left_lower_housing.stl",
    "hardware/case/kc2_right_lower_housing.step",
    "hardware/case/kc2_right_lower_housing_part_a.stl",
    "hardware/case/kc2_right_lower_housing_part_b.stl",
)

ACTIVE_PATH_FILES = (
    "tools/generate_kc2_pcbs.py",
    "tools/finalize_kc2_x3_v2_routes.py",
    "tools/postprocess_kc2_x3_v2_routes.py",
    "tools/export_kc2_x3_v2_fabrication.py",
    "tools/export_kc2_x3_v2_mechanical.py",
    "tools/generate_kc2_x3_v2_housings.py",
    "tools/generate_kc2_x3_v2_drc_evidence.py",
    "tools/generate_kc2_x3_v2_coupon_drc_evidence.py",
    "tools/render_kc2_x3_joined.py",
    "tools/verify_kc2_x3_v2.py",
    "tools/verify_kc2_x3_v2_coupon.py",
    "tools/verify_kc2_x3_v2_fabrication.py",
    "tools/verify_kc2_x3_v2_housing.py",
    "tools/verify_kc2_x3_v2_mechanical.py",
    "tools/verify_kc2_x3_v2_outline.py",
    "tools/verify_kc2_x3_v2_render.py",
    "tools/verify_kc2_x3_v2_zmk_firmware.py",
)


class CanonicalPathContractTest(unittest.TestCase):
    def test_canonical_active_artifacts_exist(self) -> None:
        missing = [path for path in CANONICAL_FILES if not (ROOT / path).is_file()]
        self.assertEqual([], missing)

    def test_active_v2_draft_trees_are_retired(self) -> None:
        self.assertFalse((ROOT / "hardware/kicad/draft/x3-v2").exists())
        self.assertFalse((ROOT / "hardware/case/draft/x3-v2").exists())

    def test_runtime_tools_do_not_bind_active_v2_to_draft(self) -> None:
        forbidden = (
            "hardware/kicad/draft/x3-v2",
            "hardware/case/draft/x3-v2",
            "kc2_left-x3-v2.kicad_pcb",
            "kc2_right-x3-v2.kicad_pcb",
        )
        violations = []
        for relative in ACTIVE_PATH_FILES:
            text = (ROOT / relative).read_text(encoding="utf-8")
            for token in forbidden:
                if token in text:
                    violations.append(f"{relative}: {token}")
        self.assertEqual([], violations)

    def test_canonical_project_identity_has_no_v2_suffix(self) -> None:
        for side in ("left", "right"):
            project_dir = ROOT / f"hardware/kicad/kc2_{side}"
            names = {path.name for path in project_dir.iterdir() if path.is_file()}
            self.assertNotIn(f"kc2_{side}-x3-v2.kicad_pro", names)
            self.assertNotIn(f"kc2_{side}-x3-v2.kicad_pcb", names)

    def test_physical_evidence_remains_fail_closed(self) -> None:
        evidence_path = ROOT / "hardware/kicad/kc2_physical_evidence.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        self.assertIs(evidence["order_ready"], False)
        self.assertEqual("pending_physical_evidence", evidence["status"])

    def test_canonical_manifests_trace_promotion_requirement(self) -> None:
        manifest_paths = (
            "hardware/kicad/kc2_generation_manifest.json",
            "hardware/kicad/fabrication/kc2_fabrication_manifest.json",
            "hardware/kicad/mechanical/kc2_mechanical_manifest.json",
            "hardware/kicad/renders/kc2_render_manifest.json",
            "hardware/case/kc2_housing_manifest.json",
        )
        missing = []
        for relative in manifest_paths:
            manifest = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            if "OPS-ARCH-006" not in manifest["requirement_ids"]:
                missing.append(relative)
        self.assertEqual([], missing)

    def test_fabrication_manifest_uses_canonical_half_directories(self) -> None:
        manifest = json.loads(
            (ROOT / "hardware/kicad/fabrication/kc2_fabrication_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            "hardware\\kicad\\fabrication\\kc2_left",
            manifest["products"]["left"]["output_dir"],
        )
        self.assertEqual(
            "hardware\\kicad\\fabrication\\kc2_right",
            manifest["products"]["right"]["output_dir"],
        )

    def test_agents_policy_uses_git_for_replaced_canonical_revisions(self) -> None:
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("## Canonical Hardware Paths", text)
        self.assertIn("must not be duplicated under a `draft` hierarchy", text)
        self.assertIn("Git history, branches, or tags", text)
        self.assertIn("does not imply fabrication readiness", text)

    def test_non_active_historical_drafts_have_no_worktree_diff(self) -> None:
        result = subprocess.run(
            [
                "git",
                "diff",
                "--quiet",
                "--",
                "hardware/kicad/draft",
                ":(exclude)hardware/kicad/draft/x3-v2/**",
                "hardware/case/draft",
                ":(exclude)hardware/case/draft/x3-v2/**",
            ],
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(0, result.returncode)


if __name__ == "__main__":
    unittest.main()
