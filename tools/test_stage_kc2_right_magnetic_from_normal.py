"""CON-ARCH-006 derive optional pockets without re-fusing unchanged normal walls."""
import unittest
from shapely.geometry import box
from tools.kc2_central_flexure import prism
from tools.stage_kc2_right_magnetic_from_normal import carve

class MagneticVariant(unittest.TestCase):
    def test_exact_original_blind_and_added_wall_entry(self):
        base=prism(box(0,0,5,5),0,2)
        blind=prism(box(0,1,1,2),.5,1.5)
        wall=prism(box(-2,0,-1,5),0,2)
        normal=base.fuse(wall)
        entry=prism(box(-3,1,0,2),.5,1.5)
        actual,row=carve(normal,base,base.cut(blind),[blind],[entry])
        self.assertAlmostEqual(normal.Volume()-actual.Volume(),2)
        self.assertEqual(row['errors'],[])
    def test_no_original_variant_difference_rejected(self):
        base=prism(box(0,0,5,5),0,2)
        with self.assertRaises(ValueError):carve(base,base,base,[],[])
    def test_entry_must_not_cut_original_magnetic_material(self):
        base=prism(box(0,0,5,5),0,2)
        blind=prism(box(0,1,1,2),0,2)
        with self.assertRaises(ValueError):carve(base,base,base.cut(blind),[blind],[prism(box(2,2,3,3),0,2)])

if __name__=='__main__':unittest.main()
