"""CON-ARCH-006 actual mesh containment cannot bypass height or evidence gates."""
import unittest
import numpy as np
from shapely.geometry import box
from tools.review_kc2_actual_envelopes import clip_triangle_z,audit_triangles,inventory_gate,evidence_gate
from tools import review_kc2_actual_envelopes as envelopes


class ActualEnvelopeTests(unittest.TestCase):
    def test_shared_full_void_semantics(self):
        from tools.review_kc2_registered_assembly import qualify_void,void_path
        self.assertIs(envelopes.qualify_void,qualify_void)
        self.assertIs(envelopes.void_path,void_path)
    def test_CON_ARCH_006_triangle_clipped_at_height_boundary(self):
        t=np.array([[0,0,0],[2,0,2],[0,2,2]],float)
        p=clip_triangle_z(t,.5,1.)
        self.assertTrue(all(.5-1e-9<=v[2]<=1+1e-9 for v in p))
        self.assertGreaterEqual(len(p),3)

    def test_CON_ARCH_006_upper_cannot_hide_in_low_contact_envelope(self):
        t=np.array([[[2,0,.5],[3,0,2.5],[2,1,2.5]]],float)
        r=audit_triangles(t,[(0,1,box(0,0,4,4)),(1,3,box(0,0,1,1))])
        self.assertTrue(r['errors'])

    def test_CON_ARCH_006_contained_and_vertical_triangles(self):
        t=np.array([[[.2,.2,0],[.8,.2,1],[.2,.8,1]],[[.2,.2,0],[.2,.8,0],[.2,.2,1]]])
        self.assertEqual(audit_triangles(t,[(0,1,box(0,0,1,1))])['errors'],[])

    def test_CON_ARCH_006_uncovered_z_and_nonconvex_crossing_fail(self):
        t=np.array([[[0,0,0],[2,0,0],[0,2,0]]],float)
        self.assertTrue(audit_triangles(t,[(1,2,box(-1,-1,3,3))])['errors'])
        allowed=box(-1,-1,3,3).difference(box(.4,.4,.6,.6))
        self.assertTrue(audit_triangles(t,[(-1,1,allowed)])['errors'])

    def test_CON_ARCH_006_all_ten_jobs_fifteen_STLs_required(self):
        counts={f'{f}:{s}:{k}':1 if s=='left' else 2 for f,ks in [('upper',['mx','choc_v1','deep_sea']),('lower',['normal','magnetic'])] for s in ['left','right'] for k in ks}
        inventory_gate(counts)
        del counts['lower:right:magnetic']
        with self.assertRaises(ValueError):inventory_gate(counts)

    def test_CON_ARCH_006_passing_report_must_bind_required_artifact(self):
        good={'status':'pass','errors':[],'source_sha256':{'a':'abc'}}
        evidence_gate(good,{'a':'abc'})
        for bad in [dict(good,status='running'),dict(good,source_sha256={}),dict(good,source_sha256={'a':'wrong'})]:
            with self.assertRaises(ValueError):evidence_gate(bad,{'a':'abc'})


if __name__=='__main__':unittest.main()
