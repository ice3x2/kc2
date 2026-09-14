"""CON-ARCH-006 actual-section mutations must not pass plan-only gates."""
import unittest
from shapely.geometry import box,Point
from tools.review_kc2_profile_split_cad import section_errors,validate_features


class SectionReviewTests(unittest.TestCase):
    def test_narrow_neck_metadata_rejected(self):
        feature=dict(point=[0,0,0],donor='a',key_wkt=box(-.9,-.8,3,.8).union(Point(3,0).buffer(2,quad_segs=24)).wkt)
        with self.assertRaises(ValueError):validate_features([feature,feature])

    def test_missing_key_is_rejected(self):
        a,b=box(0,0,10,10),box(10.4,0,20,10)
        feature=dict(donor='a',key_wkt=box(8,4,9,5).wkt,
                     slot_wkt=box(10,4,10.4,5).wkt,receiver_wkt=box(10.4,4,11,5).wkt)
        errors=section_errors([a.difference(box(8,4,9,5)),b],[a,b],[feature],[],box(0,0,0,0))
        self.assertIn('missing actual key material',errors)

    def test_missing_clip_ring_is_rejected(self):
        opening=box(3,3,5,5)
        a=box(0,0,10,10).difference(opening.buffer(.8));b=box(10.4,0,20,10)
        errors=section_errors([a,b],[box(0,0,10,10),b],[],[opening],box(0,0,0,0))
        self.assertIn('actual clip ring interrupted',errors)

    def test_material_outside_assigned_mask_is_rejected(self):
        a,b=box(0,0,10,10),box(10.4,0,20,10)
        errors=section_errors([a.buffer(.1),b],[a,b],[],[],box(0,0,0,0))
        self.assertIn('actual material outside assigned partition',errors)

    def test_filled_receiver_slot_rejected(self):
        a,b=box(0,0,10,10),box(10.4,0,20,10)
        feature=dict(donor='a',key_wkt=box(8,4,9,5).wkt,
                     slot_wkt=box(11,4,12,5).wkt,receiver_wkt=box(10.4,3,13,6).wkt)
        self.assertIn('actual receiver fills slot',section_errors([a,b],[a,b],[feature],[],box(0,0,0,0)))

    def test_tight_actual_gap_rejected(self):
        a,b=box(0,0,10,10),box(10.2,0,20,10)
        self.assertIn('actual A/B gap below .40 mm',section_errors([a,b],[a,b],[],[],box(0,0,0,0)))


if __name__=='__main__':unittest.main()
