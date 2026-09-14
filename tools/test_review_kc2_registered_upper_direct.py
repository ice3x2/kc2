"""CON-ARCH-006 independent-mask direct actual reviewer regressions."""
import copy
import unittest
from shapely.geometry import box
from tools import test_review_kc2_registered_upper_mask_contract as fixture_module
from tools import review_kc2_registered_upper_direct as r

class DirectTests(unittest.TestCase):
    def test_independent_layers_reject_changed_masks_and_material(self):
        old,g,d,p=fixture_module.MaskContractTests().fixture()
        layers,rows=r.independent_layers('mx',old,g,p)
        self.assertEqual(len(layers),2);self.assertEqual(len(rows[0]['sections']),4)
        bad=copy.deepcopy(p);bad['augmented_masks_wkt'][0]=box(0,0,4.7,10).wkt
        with self.assertRaises(ValueError):r.independent_layers('mx',old,g,bad)
        for shape in (box(0,0,4.7,10),box(0,0,4.9,10)):
            bad=copy.deepcopy(g);bad['parts'][0]['layers'][1]['wkt']=shape.wkt
            with self.assertRaises(ValueError):r.independent_layers('mx',old,bad,p)
    def test_missing_height_or_unqualified_profile_rejected(self):
        old,g,d,p=fixture_module.MaskContractTests().fixture()
        bad=copy.deepcopy(g);bad['parts'][0]['layers'][1]['z1']=7.8;bad['parts'][0]['layers'].pop(2)
        with self.assertRaises(ValueError):r.independent_layers('mx',old,bad,p)
        p['status']='failed'
        with self.assertRaises(ValueError):r.independent_layers('mx',old,g,p)
    def test_changed_bound_source_rejected_before_import(self):
        with self.assertRaises(ValueError):r.require_current({'a':'0'*64},lambda name:'1'*64)

if __name__=='__main__':unittest.main()
