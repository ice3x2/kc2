"""CON-ARCH-006: independent actual upper delta must reject misleading CAD."""
import unittest
import cadquery as cq
from tools.review_kc2_local_upper_covers import delta_errors, approach_geometries, outside_volume, coverage_areas, split_clearance_records
from shapely.geometry import box,Point

class UpperReviewTests(unittest.TestCase):
    def test_original_polygonized_nominal_gap_is_preserved_without_redesign(self):
        gap=.199759091241
        a=cq.Solid.makeBox(10,10,1,cq.Vector(0,0,8));b=cq.Solid.makeBox(10,10,1,cq.Vector(10+gap,0,8))
        aa=cq.Solid.makeBox(10,1,1,cq.Vector(0,0,7));bb=cq.Solid.makeBox(10,1,1,cq.Vector(10+gap,0,7))
        self.assertEqual(split_clearance_records([a,b],[a.fuse(aa),b.fuse(bb)],[aa,bb])['errors'],[])
    def test_near_touching_cover_cannot_close_retained_point_two_gap(self):
        a=cq.Solid.makeBox(10,10,1,cq.Vector(0,0,8));b=cq.Solid.makeBox(10,10,1,cq.Vector(10.2,0,8))
        aa=cq.Solid.makeBox(.1,1,1,cq.Vector(10,0,8));bb=cq.Solid.makeBox(.1,1,1,cq.Vector(10.2,0,7))
        row=split_clearance_records([a,b],[a.fuse(aa),b.fuse(bb)],[aa,bb])
        self.assertTrue(row['errors'])
        self.assertAlmostEqual(row['added_a_to_old_b_mm'],.1)
    def test_only_exact_original_gap_can_explain_missing_coverage(self):
        required=box(0,0,10,1);gap=box(4,0,6,1)
        row=coverage_areas(required,[required.difference(gap)],gap)
        self.assertEqual(row['unexplained_mm2'],0.)
        row=coverage_areas(required,[box(0,0,4,1)],gap)
        self.assertEqual(row['unexplained_mm2'],4.)
    def test_touching_allowance_solids_are_separate_boolean_tools(self):
        # OCP can retain false residuals when touching roof/skirt solids are
        # passed as one compound; actual left STEP reproduced 423.969 vs zero.
        from unittest.mock import Mock
        solids=[object(),object()]
        allowed=Mock();allowed.Solids.return_value=solids
        added=Mock();added.cut.return_value.Volume.return_value=0.
        self.assertEqual(outside_volume(added,allowed),0.)
        added.cut.assert_called_once_with(*solids)
    def fixture(self):
        base=cq.Solid.makeBox(10,10,1.5,cq.Vector(0,0,7.8))
        cover=cq.Solid.makeBox(.4,10,3.4,cq.Vector(0,0,4.4))
        return base,cover
    def test_missing_cover_is_not_a_pass(self):
        base,cover=self.fixture()
        self.assertTrue(delta_errors(base,base,cover)['errors'])
    def test_additive_local_cover_passes(self):
        base,cover=self.fixture()
        self.assertEqual(delta_errors(base,base.fuse(cover),cover)['errors'],[])
    def test_global_wall_rejected(self):
        base,cover=self.fixture()
        global_wall=cq.Solid.makeBox(10,.4,3.4,cq.Vector(0,0,4.4))
        self.assertTrue(delta_errors(base,base.fuse(cover,global_wall),cover)['errors'])
    def test_original_support_material_cannot_be_removed(self):
        base,cover=self.fixture()
        removed=cq.Solid.makeBox(1,1,2,cq.Vector(5,5,7.5))
        self.assertTrue(delta_errors(base,base.fuse(cover).cut(removed),cover)['errors'])
    def test_approach_corridors_extend_outside_not_only_body_cutouts(self):
        plan={'feature_geometries':{'controller_socket':box(10,5,20,18)},
              'mounting_service_geometries':{'power_switch_actuator_sweep':box(15,23,17,25)},
              'reset_actuator_geometry':Point(12,24).buffer(1),'mounting_holes':[]}
        r=approach_geometries('left',plan,box(0,0,30,40))
        self.assertGreater(r['usb_nominal_9_6mm_cable'][0].bounds[2],30)
        self.assertAlmostEqual(r['usb_nominal_9_6mm_cable'][0].bounds[3]-r['usb_nominal_9_6mm_cable'][0].bounds[1],10.2)
        self.assertEqual(r['reset_3mm_probe'][1:],[4.1,15.])

if __name__=='__main__':unittest.main()
