"""CON-ARCH-006 central engagement is not the right A/B print split."""
import unittest
from shapely.geometry import Polygon
from shapely import affinity
from tools.kc2_central_fit import CentralFit, central_sections, insertion_audit


class CentralFitTests(unittest.TestCase):
    def test_fixed_four_mm_gap_and_two_point_eight_projection(self):
        p=CentralFit()
        s=central_sections(p)
        self.assertAlmostEqual(p.gap,4.)
        self.assertAlmostEqual(s['engagement_mm'],1.6)
        self.assertFalse(s['physical_qualified'])

    def test_rigid_guides_do_not_collide_and_contact_is_explicit(self):
        s=central_sections(CentralFit())
        self.assertLess(s['male'].intersection(s['female_rigid']).area,1e-9)
        self.assertGreater(s['male'].intersection(s['contact']).area,0)
        self.assertLess(s['male'].intersection(s['female']).difference(s['contact']).area,1e-9)

    def test_non_latching_insertion_only_contacts_declared_ribs(self):
        s=central_sections(CentralFit())
        a=insertion_audit(s)
        self.assertEqual(a['errors'],[])
        self.assertGreater(a['maximum_intended_contact_mm2'],0)
        self.assertFalse(a['force_qualified'])

    def test_rigid_obstruction_rejected(self):
        s=central_sections(CentralFit())
        s['female_rigid']=s['female_rigid'].union(s['male'])
        self.assertIn('rigid insertion obstruction',insertion_audit(s)['errors'])

    def test_invalid_tolerances_rejected(self):
        for fields in ({'gap':float('nan')},{'projection':0},{'running_clearance':-.1},
                       {'contact_deflection':.3},{'wall':.4}):
            with self.subTest(fields=fields),self.assertRaises(ValueError):
                central_sections(CentralFit(**fields))

    def test_contact_deflection_is_not_ab_clearance(self):
        s=central_sections(CentralFit(contact_deflection=0))
        self.assertLess(s['male'].intersection(s['contact']).area,1e-9)

    def test_missing_requested_contact_is_not_a_pass(self):
        s=central_sections(CentralFit())
        s['contact']=Polygon()
        self.assertIn('requested contact geometry missing or changed',insertion_audit(s)['errors'])

    def test_bool_dimensions_are_not_real_measurements(self):
        with self.assertRaises(ValueError):central_sections(CentralFit(root=True))


if __name__=='__main__':unittest.main()
