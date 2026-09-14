"""CON-ARCH-006 TDD for explicit Fusion-native flat-seam jobs."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.kc2_flat_central_native import jobs, preflight, validate_native_output, compare_cad_signatures


class FlatCentralNativeTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory(); root = Path(temporary.name)
        stage = root / ".codex-tmp/flat-central-revision"; stage.mkdir(parents=True)
        inventory = {}
        for label, specification in jobs().items():
            folder = stage / specification["folder"]; folder.mkdir(parents=True)
            step = folder / specification["step"]; step.write_bytes(label.encode())
            generation = {"status": "generated_pending_independent_review", "errors": [],
                          "body_count": specification["body_count"],
                          "outputs": {step.name: hashlib.sha256(step.read_bytes()).hexdigest()}}
            (folder / "generation.json").write_text(json.dumps(generation))
            inventory[label] = (step, folder / "generation.json")
        return temporary, root, inventory

    def test_four_explicit_lower_jobs_preflight(self):
        temporary, root, _ = self.fixture()
        try:
            self.assertEqual(set(jobs()), {"left:normal", "left:magnetic", "right:normal", "right:magnetic"})
            self.assertEqual(preflight(root, "right:magnetic")["body_count"], 2)
        finally: temporary.cleanup()

    def test_stale_step_and_implicit_job_fail(self):
        temporary, root, inventory = self.fixture()
        try:
            with self.assertRaises(ValueError): preflight(root, "all")
            inventory["left:normal"][0].write_bytes(b"changed")
            with self.assertRaises(ValueError): preflight(root, "left:normal")
        finally: temporary.cleanup()

    def test_native_output_requires_roundtrip_identity(self):
        source = [{"volume_mm3": 1.0, "bounds_mm": [0, 0, 0, 1, 1, 1]}]
        self.assertEqual(validate_native_output(source, list(source)), [])
        self.assertTrue(validate_native_output(source, []))
        self.assertTrue(validate_native_output(source, [{"volume_mm3": 1.1, "bounds_mm": [0, 0, 0, 1, 1, 1]}]))

    def test_independent_cad_signature_detects_mass_or_position_change(self):
        signature = {"volume_mm3": 1.0, "area_mm2": 6.0, "center_mm": [.5, .5, .5],
                     "bounds_mm": [0, 0, 0, 1, 1, 1], "faces": 6, "edges": 12, "vertices": 8}
        self.assertEqual(compare_cad_signatures(signature, dict(signature)), [])
        changed = dict(signature); changed["edges"] = 13
        # Fusion STEP readback may legally repartition coincident faces/edges.
        self.assertEqual(compare_cad_signatures(signature, changed), [])
        changed = dict(signature); changed["center_mm"] = [.5, .5, .51]
        self.assertTrue(compare_cad_signatures(signature, changed))

    def test_fusion_addin_is_explicit_and_startup_capable(self):
        root = Path(__file__).resolve().parents[1]
        folder = root / "tools/fusion/KC2FlatCentralToF3D"
        manifest = json.loads((folder / "KC2FlatCentralToF3D.manifest").read_text())
        source = (folder / "KC2FlatCentralToF3D.py").read_text()
        self.assertTrue(manifest["runOnStartup"])
        self.assertIn("for label in jobs()", source)
        self.assertIn("validate_native_output", source)
        self.assertIn("native-readback.step", source)
        self.assertIn("startupCompleted.add", source)


if __name__ == "__main__":
    unittest.main()
