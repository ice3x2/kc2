"""CON-ARCH-006: all four native housing exports and solid round trips."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from tools import verify_kc2_housing_f3d as verifier

SCRIPT = Path(__file__).parent / 'fusion' / 'KC2StepToF3D' / 'KC2StepToF3D.py'


def load_exporter():
    adsk = ModuleType('adsk')
    adsk.core = ModuleType('adsk.core')
    adsk.fusion = ModuleType('adsk.fusion')
    with patch.dict('sys.modules', {'adsk': adsk, 'adsk.core': adsk.core, 'adsk.fusion': adsk.fusion}):
        spec = importlib.util.spec_from_file_location('kc2_fusion_export_test', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class FusionExportTests(unittest.TestCase):
    def test_exporter_counts_are_fixed_for_all_four_jobs(self):
        self.assertEqual(load_exporter().EXPECTED_BODY_COUNTS, verifier.EXPECTED_BODY_COUNTS)

    def test_component_collection_uses_assembly_context_proxies(self):
        def collection(items):
            return SimpleNamespace(count=len(items), item=lambda index:items[index])
        native=object()
        proxy_a,proxy_b=object(),object()
        component=SimpleNamespace(bRepBodies=collection([native]))
        occurrences=[SimpleNamespace(component=component,bRepBodies=collection([proxy]))
                     for proxy in (proxy_a,proxy_b)]
        root=SimpleNamespace(bRepBodies=collection([]),allOccurrences=collection(occurrences))
        self.assertEqual(load_exporter().component_bodies(root),[proxy_a,proxy_b])

    def test_verifier_uses_point_zero_zero_one_mm_bounds_tolerance(self):
        source=[[0.,0.,0.,20.,20.,1.5],[20.,0.,0.,40.,20.,1.5]]
        shifted=[[v+.0005 for v in box] for box in reversed(source)]
        self.assertTrue(verifier.body_bounds_equal(source,shifted))
        shifted[0][0]+=.002
        self.assertFalse(verifier.body_bounds_equal(source,shifted))
        self.assertFalse(verifier.body_bounds_equal(source,source[:1]))
        self.assertFalse(verifier.bounds_equal(source[0],[float('nan'),0,0,20,20,1.5]))
        self.assertFalse(verifier.bounds_equal([0,0,0,-1,20,1.5],[0,0,0,-1,20,1.5]))

    def test_current_upper_body_counts_are_not_self_declared(self):
        self.assertEqual(verifier.EXPECTED_BODY_COUNTS, {
            'left_lower': 1, 'right_lower': 2,
            'left_mx_upper': 1, 'right_mx_upper': 2,
        })

    def test_verifier_reports_all_four_missing_archives_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            errors = verifier.verify_f3d_outputs(Path(tmp))
            self.assertEqual(sum('missing Fusion archive' in e for e in errors), 4)
            self.assertTrue(any('mx_upper' in e for e in errors))

    def test_requires_upper_sources_before_exporting_any_lower(self):
        exporter = load_exporter()
        with tempfile.TemporaryDirectory() as tmp:
            case = Path(tmp)
            for side in ('left', 'right'):
                (case / f'kc2_{side}_lower_housing.step').touch()
            with self.assertRaisesRegex(FileNotFoundError, 'mx_upper'):
                exporter.export_jobs(case)
            for side in ('left', 'right'):
                (case / f'kc2_{side}_mx_upper_housing.step').touch()
            jobs = exporter.export_jobs(case)
            self.assertEqual(set(jobs), {'left_lower', 'right_lower', 'left_mx_upper', 'right_mx_upper'})
            self.assertTrue(all(p.parent == case for p in jobs.values()))

    def test_round_trip_rejects_internal_shape_loss_with_same_bounds(self):
        exporter = load_exporter()
        source = [{'bounds_mm': [0, 0, 0, 20, 20, 1.5], 'volume_mm3': 300.0}]
        altered = [{'bounds_mm': [0, 0, 0, 20, 20, 1.5], 'volume_mm3': 310.0}]
        with self.assertRaisesRegex(RuntimeError, 'volume'):
            exporter.validate_round_trip(source, altered)

    def test_round_trip_handles_body_order_and_rejects_oversized_parts(self):
        exporter = load_exporter()
        source = [
            {'bounds_mm': [0, 0, 0, 20, 20, 1.5], 'volume_mm3': 300.0},
            {'bounds_mm': [20, 0, 0, 40, 20, 1.5], 'volume_mm3': 250.0},
        ]
        exporter.validate_round_trip(source, list(reversed(source)))
        wide = [{'bounds_mm': [0, 0, 0, 151, 20, 1.5], 'volume_mm3': 300.0}]
        with self.assertRaisesRegex(RuntimeError, '150'):
            exporter.validate_round_trip(wide, wide)

    def test_round_trip_rejects_missing_or_invalid_solids(self):
        exporter = load_exporter()
        source = [{'bounds_mm': [0, 0, 0, 20, 20, 1.5], 'volume_mm3': 300.0}]
        for changed in ([], [{'bounds_mm': [0, 0, 0, 20, 20, 1.5], 'volume_mm3': float('nan')}],
                        [{'bounds_mm': [0, 0, 0, 20, 20, 1.5], 'volume_mm3': 0}]):
            with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                exporter.validate_round_trip(source, changed)


if __name__ == '__main__':
    unittest.main()
