"""CON-ARCH-006 right-only actual native identity, explicit source proof."""
import unittest


class RightNativeTests(unittest.TestCase):
    def test_bounds_identity_reorders_but_rejects_ambiguous_or_moved(self):
        import cadquery as cq
        from tools.review_kc2_right_lower_native import match_bodies,bounds
        a=cq.Workplane('XY').box(2,2,2).val();b=a.translate((10,0,0))
        record={'parts':[dict(index=i,bounds_mm=bounds(s)) for i,s in enumerate((a,b))]}
        self.assertTrue(match_bodies([b,a],record)[0].isSame(a))
        with self.assertRaises(ValueError):match_bodies([a,a],record)
        with self.assertRaises(ValueError):match_bodies([a,b.translate((.01,0,0))],record)

    def test_actual_nd_comparison_and_frozen_acceptance_functions(self):
        import cadquery as cq
        from unittest.mock import patch
        from tools import review_kc2_right_lower_native as n
        from tools import review_kc2_registered_native as frozen
        a=cq.Workplane('XY').box(2,2,2).val()
        row=n.compare_body(a,a,0)
        self.assertEqual(row['status'],'pass');self.assertEqual(row['missing_mm3'],0)
        changed=a.cut(cq.Workplane('XY').box(.3,.3,.3).translate((1,1,1)).val())
        self.assertEqual(n.compare_body(a,changed,0)['status'],'failed')
        self.assertIs(n.check_source_binding,frozen.check_source_binding)
        self.assertIs(n.acceptance_errors,frozen.acceptance_errors)

    def test_nonfinite_difference_and_missing_binding_rejected(self):
        import cadquery as cq
        from unittest.mock import patch,MagicMock
        from tools import review_kc2_right_lower_native as n
        a=cq.Workplane('XY').box(2,2,2).val();bad=MagicMock();bad.Volume.return_value=float('nan')
        bad.isValid.return_value=True;bad.Solids.return_value=[];bad.Faces.return_value=[]
        with patch.object(n,'nd_cut',return_value=bad):
            self.assertEqual(n.compare_body(a,a,0)['status'],'failed')
        with self.assertRaises(ValueError):n.check_source_binding({'source_sha256':{}},{'actual.step':'hash'})


if __name__=='__main__':unittest.main()
