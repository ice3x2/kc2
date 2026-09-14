"""CON-ARCH-006 bounded alternative must reject real collisions and missing proof."""
import hashlib
import copy
import tempfile
import unittest
from pathlib import Path
from shapely.geometry import box
from tools.review_kc2_local_covers import prism
from tools.kc2_component_local_certificate import certify_local, inspect_local_prism, verify_bindings


class LocalCertificateTests(unittest.TestCase):
    def test_clear_cavity_has_positive_boundaries_and_outside_seed(self):
        xy=box(-1,-1,1,1)
        subject=prism(box(-4,-4,4,4).difference(box(-2,-2,2,2)),-.5,2.5).Solids()[0]
        tool=prism(xy,-.4,2.5).Solids()[0]
        result=certify_local(subject,tool,xy,box(-3,-3,3,3))
        self.assertTrue(result['eligible'],result['errors'])
        self.assertEqual(result['roi']['tool_overlap_mm2'],0)

    def test_pure_validator_rejects_zero_nonfinite_and_boolean_metrics(self):
        from tools.kc2_component_local_certificate import validate_local_evidence
        xy=box(-1,-1,1,1)
        subject=prism(box(-4,-4,4,4).difference(box(-2,-2,2,2)),-.5,2.5).Solids()[0]
        result=certify_local(subject,prism(xy,-.4,2.5).Solids()[0],xy,box(-3,-3,3,3))
        validate_local_evidence(result)
        for value in (0.,-1.,float('nan'),True):
            bad=copy.deepcopy(result);bad['shell_pairs'][0]['distance_mm']=value
            with self.assertRaises(ValueError):validate_local_evidence(bad)
        for value in (-1.,float('nan'),False):
            bad=copy.deepcopy(result);bad['roi']['volume_error_mm3']=value
            with self.assertRaises(ValueError):validate_local_evidence(bad)
        bad=copy.deepcopy(result);bad['shell_pairs'][0]['a_shell']=False
        with self.assertRaises(ValueError):validate_local_evidence(bad)
        bad=copy.deepcopy(result);bad['roi']['section_wkt']=box(-3,-3,3,3).wkt
        with self.assertRaises(ValueError):validate_local_evidence(bad)

    def test_overlap_touch_and_containment_rejected(self):
        xy=box(-1,-1,1,1);tool=prism(xy,-.4,2.5).Solids()[0]
        for body in (box(.5,-4,4,4),box(1,-4,4,4),box(-4,-4,4,4)):
            subject=prism(body,-.5,2.5).Solids()[0]
            result=certify_local(subject,tool,xy,box(-3,-3,3,3))
            self.assertFalse(result['eligible'])

    def test_hidden_upper_shelf_rejected_by_prism_proof(self):
        base=prism(box(-3,-3,3,3).difference(box(-2,-2,2,2)),-.5,2.5)
        shelf=prism(box(-2,-1,0,1),1,1.5)
        changed=base.fuse(shelf).clean()
        result=inspect_local_prism(changed,box(-1,-1,1,1),1.05)
        self.assertIn('unexpected intermediate Z transition',result['errors'])

    def test_empty_or_stale_source_binding_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'step').write_text('actual')
            actual=hashlib.sha256((root/'step').read_bytes()).hexdigest()
            verify_bindings(root,{'step':actual},['step'])
            for bindings in ({},{'step':'0'*64}):
                with self.assertRaises(ValueError):verify_bindings(root,bindings,['step'])

    def test_actual_tool_order_identity_requires_full_xy_and_z(self):
        from tools.kc2_component_local_certificate import inspect_tool_prism
        expected=box(-1,-1,1,1)
        solid=prism(expected,-.4,2.5).Solids()[0]
        row=inspect_tool_prism(solid,expected,2)
        self.assertEqual(row['actual_section_missing_mm2'],0)
        self.assertEqual(row['actual_section_extra_mm2'],0)
        wrong=inspect_tool_prism(solid,box(-2,-2,2,2),2)
        self.assertGreater(wrong['actual_section_missing_mm2'],0)
        with self.assertRaises(ValueError):
            inspect_tool_prism(prism(expected,-.4,2.4).Solids()[0],expected,2)


if __name__=='__main__':unittest.main()
