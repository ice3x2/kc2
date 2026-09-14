"""CON-ARCH-006 actual free-wall central guide concept, not strength approval."""
import unittest
from shapely.geometry import box,Polygon
from tools.kc2_central_flexure import flexure_plan, audit_flexure


class CentralFlexureTests(unittest.TestCase):
    def test_actual_free_side_and_rear_space(self):
        p=flexure_plan()
        self.assertEqual(audit_flexure(p)['errors'],[])
        self.assertEqual(len(p['beams']),2)
        self.assertGreater(p['free_volume_mm3'],0)
        self.assertFalse(p['physical_qualified'])

    def test_beams_root_only_in_base_not_rigid_cheek(self):
        p=flexure_plan()
        for b in p['beams']:
            self.assertTrue(p['root_floor'].covers(b['plan']))
            self.assertLess(b['plan'].intersection(p['case_rigid']).area,1e-9)
            self.assertGreaterEqual(b['rear_clearance_mm'],.79)

    def test_backfill_rejected(self):
        p=flexure_plan()
        p['case_rigid']=p['case_rigid'].union(p['free_space'])
        self.assertIn('free deflection pocket obstructed',audit_flexure(p)['errors'])

    def test_no_unlabelled_interference(self):
        p=flexure_plan()
        a=audit_flexure(p)
        self.assertLess(a['rigid_overlap_mm2'],1e-9)
        self.assertGreater(a['intended_interference_mm2'],0)
        self.assertAlmostEqual(p['nominal_tip_deflection_mm'],.02)

    def test_geometry_not_force_qualification(self):
        a=audit_flexure(flexure_plan())
        self.assertFalse(a['force_qualified'])
        self.assertFalse(a['material_qualified'])

    def test_empty_free_space_and_false_deflection_are_rejected(self):
        p=flexure_plan();p['free_space']=Polygon();p['nominal_tip_deflection_mm']=.5
        self.assertIn('declared geometry differs from dimensional contract',audit_flexure(p)['errors'])

    def test_actual_mapping_and_component_root_trim(self):
        from tools.kc2_central_flexure import place_feature_solids,prism
        protect=box(.925,93.8,1.2,96.2)
        result=place_feature_solids('left',protect,ys=(95.,117.))
        self.assertEqual(len(result),2)
        for shape in result:
            self.assertEqual(len(shape.Solids()),1)
            self.assertLess(shape.intersect(prism(protect,-1.,2.5)).Volume(),1e-7)
        self.assertAlmostEqual(result[0].BoundingBox().xmin,-2.7,places=6)

    def test_actual_brep_is_connected_and_free_pocket_not_filled(self):
        from tools.kc2_central_flexure import build_central_solids, prism
        p=flexure_plan();a,b=build_central_solids(p)
        for s in (a,b):
            self.assertTrue(s.isValid())
            self.assertEqual(len(s.Solids()),1)
        pocket=prism(p['free_space'],-.99,1.51)
        self.assertLess(b.intersect(pocket).Volume(),1e-7)
        self.assertGreater(a.intersect(b).Volume(),0)
        contact=prism(p['contact'],.799,1.501)
        self.assertLess(a.intersect(b).cut(contact).Volume(),1e-7)


if __name__=='__main__':unittest.main()
