"""CON-ARCH-006 exhaustive actual normal-material strata proof."""
import unittest
from shapely.geometry import box


class LowerStrataTests(unittest.TestCase):
    def test_empty_and_nonfinite_actual_section_evidence_rejected(self):
        from unittest.mock import patch
        from shapely.geometry import GeometryCollection
        from tools.kc2_lower_strata import audit_normal
        with patch('tools.kc2_lower_strata.section_superset',return_value=(GeometryCollection(),[])):
            self.assertTrue(audit_normal(self.fixture(),box(7,1,8,2),[(2,2),(12,2)])['errors'])
        for value in (float('nan'),float('inf'),float('-inf')):
            with patch('shapely.geometry.base.BaseGeometry.distance',return_value=value):
                self.assertTrue(audit_normal(self.fixture(),box(7,1,8,2),[(2,2),(12,2)])['errors'])

    def test_empty_actual_common_rejected_for_spanning_body(self):
        import cadquery as cq
        from unittest.mock import patch
        from tools.kc2_lower_strata import section_superset
        with patch('tools.kc2_component_local_certificate._non_destructive_common',return_value=cq.Compound.makeCompound([])):
            with self.assertRaises(ValueError):section_superset(self.fixture()[0],0,[(2,2)])

    def test_whole_import_cannot_hide_extra_face(self):
        import cadquery as cq
        from tools.review_kc2_lower_strata import validate_import
        solids=self.fixture();whole=cq.Compound.makeCompound(solids)
        self.assertEqual(len(validate_import(whole)),2)
        extra=cq.Face.makePlane(1,1,(50,50,0))
        with self.assertRaises(ValueError):validate_import(cq.Compound.makeCompound(solids+[extra]))

    def test_source_closure_rejects_missing_changed_or_escaping_paths(self):
        import tempfile,hashlib
        from pathlib import Path
        from tools.review_kc2_lower_strata import verify_sources
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'a';p.write_bytes(b'old');sources={'a':hashlib.sha256(b'old').hexdigest()}
            verify_sources(root,sources)
            p.write_bytes(b'new')
            with self.assertRaises(ValueError):verify_sources(root,sources)
            with self.assertRaises(ValueError):verify_sources(root,{})
            with self.assertRaises(ValueError):verify_sources(root,{'../elsewhere':'x'})

    def fixture(self):
        import cadquery as cq
        a=cq.Workplane('XY').box(6,6,3.5,centered=(False,False,False)).translate((0,0,-1)).val()
        b=a.translate((10,0,0))
        a=a.cut(cq.Solid.makeCylinder(.55,2.8,cq.Vector(2,2,-.3)))
        b=b.cut(cq.Solid.makeCylinder(.55,2.8,cq.Vector(12,2,-.3)))
        return [a,b]

    def test_filled_inner_pilots_are_conservative_not_missing_material(self):
        from tools.kc2_lower_strata import audit_normal
        progress=[]
        r=audit_normal(self.fixture(),box(7,1,8,2),[(2,2),(12,2)],progress=progress.append)
        self.assertEqual(r['errors'],[])
        self.assertEqual(len(progress),len(r['intervals'])+len(r['critical_closures']))
        self.assertIn(-.3,r['levels_mm'])
        # A protected component located inside a real pilot cavity must still
        # fail this conservative method, never exploit the filled-hole shortcut.
        r=audit_normal(self.fixture(),box(1.9,1.9,2.1,2.1),[(2,2),(12,2)])
        self.assertTrue(r['errors'])

    def test_only_exact_known_blind_bottom_cap_can_use_outer_circle(self):
        import cadquery as cq
        from tools.kc2_lower_strata import critical_face_superset
        def disk(radius=.55,z=-.3,x=2):
            return cq.Face.makeFromWires(cq.Wire.makeCircle(radius,cq.Vector(x,2,z),cq.Vector(0,0,1)))
        polygon,method=critical_face_superset(disk(),-.3,[(2,2)])
        self.assertEqual(method,'qualified_blind_pilot_cap_outward_aabb')
        self.assertGreater(polygon.area,3.14159*.55**2)
        for face,z in ((disk(.56),-.3),(disk(x=3),-.3),(disk(z=.2),.2)):
            with self.assertRaises(ValueError):critical_face_superset(face,z,[(2,2)])

    def test_wrong_pilot_and_outer_arc_fail(self):
        import cadquery as cq
        from tools.kc2_lower_strata import audit_normal
        self.assertTrue(audit_normal(self.fixture(),box(7,1,8,2),[(2,2),(12.1,2)])['errors'])
        cylinder=cq.Solid.makeCylinder(.55,2.8,cq.Vector(12,2,-.3))
        self.assertTrue(audit_normal([self.fixture()[0],cylinder],box(7,1,8,2),[(2,2),(12,2)])['errors'])

    def test_sloped_face_and_hidden_horizontal_stratum(self):
        import cadquery as cq
        from tools.kc2_lower_strata import audit_normal
        a,b=self.fixture()
        self.assertTrue(audit_normal([a.rotate((0,0,0),(1,0,0),5),b],box(7,1,8,2),[(2,2),(12,2)])['errors'])
        # Thin ledge would be missed by one arbitrary slab sample.
        ledge=cq.Workplane('XY').box(2,1,.02,centered=(False,False,False)).translate((5.5,1,.71)).val()
        a=a.fuse(ledge).clean()
        result=audit_normal([a,b],box(6.5,1.1,7,1.9),[(2,2),(12,2)])
        self.assertTrue(result['errors'])
        self.assertTrue(any(abs(z-.71)<1e-8 for z in result['levels_mm']))


if __name__=='__main__':unittest.main()
