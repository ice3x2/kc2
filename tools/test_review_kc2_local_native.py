"""CON-ARCH-006: native mass comparison must not loosen tolerance."""
import ast
from pathlib import Path
import unittest


class NativeKernelTests(unittest.TestCase):
    def test_adaptive_mass_uses_error_control_and_rejects_unconverged_result(self):
        from unittest.mock import patch
        from tools.review_kc2_local_native import adaptive_volume
        import cadquery as cq
        from OCP.BRepGProp import BRepGProp
        shape=cq.Workplane('XY').box(10,10,10).val()
        self.assertAlmostEqual(adaptive_volume(shape),1000.,places=8)
        with patch.object(BRepGProp,'VolumeProperties_s',return_value=.01):
            with self.assertRaisesRegex(ValueError,'integration'):adaptive_volume(shape)

    def test_same_kernel_match_and_tolerance_mutations(self):
        from tools.review_kc2_local_native import compare_records
        a=[{'bounds_mm':[0,0,0,10,10,10],'volume_mm3':1000.}]
        self.assertEqual(compare_records(a,a),[])
        self.assertTrue(compare_records(a,[dict(a[0],volume_mm3=1000.003)]))
        self.assertTrue(compare_records(a,[dict(a[0],bounds_mm=[0,0,0,10.002,10,10])]))
        self.assertTrue(compare_records(a,[dict(a[0],volume_mm3=float('nan'))]))
        self.assertTrue(compare_records(a,[]))

    def test_fusion_diagnostic_never_exports_or_replaces_f3d(self):
        path=Path(__file__).parents[1]/'tools/fusion/KC2LocalNativeReview/KC2LocalNativeReview.py'
        tree=ast.parse(path.read_text(encoding='utf8'))
        calls={n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)}
        self.assertIn('createFusionArchiveImportOptions',calls)
        self.assertIn('createSTEPExportOptions',calls)
        self.assertNotIn('createFusionArchiveExportOptions',calls)


if __name__=='__main__':unittest.main()
