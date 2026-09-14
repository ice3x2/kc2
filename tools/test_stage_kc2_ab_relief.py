"""CON-ARCH-006 actual subtractive A/B CAD staging guards."""
import unittest
import cadquery as cq
from shapely.geometry import box
from tools.stage_kc2_ab_relief import cut_pair, safe_stage


class StageTests(unittest.TestCase):
    def test_only_ignored_stage(self):
        with self.assertRaises(ValueError):
            safe_stage('hardware/MODELS')

    def test_actual_gap_and_hole_preserved(self):
        a=cq.Workplane('XY').box(10,10,2,centered=False).val()
        bore=cq.Workplane('XY').center(5,5).circle(.8).extrude(2).val()
        a=a.cut(bore)
        b=cq.Workplane('XY').box(10,10,2,centered=False).translate((10.2,0,0)).val()
        revised, evidence=cut_pair([a,b],[box(0,0,10,10),box(10.2,0,20.2,10)])
        self.assertGreaterEqual(revised[0].distance(revised[1]),.39999)
        self.assertLess(revised[0].intersect(bore).Volume(),1e-8)
        self.assertTrue(all(s.isValid() and len(s.Solids())==1 for s in revised))
        self.assertGreater(evidence['removed_volume_mm3'],0)
        self.assertFalse(evidence['physical_qualified'])

    def test_protected_root_rejects(self):
        a=cq.Workplane('XY').box(10,10,2,centered=False).val()
        b=cq.Workplane('XY').box(10,10,2,centered=False).translate((10.2,0,0)).val()
        with self.assertRaises(ValueError):
            cut_pair([a,b],[box(0,0,10,10),box(10.2,0,20.2,10)],protected=box(9.8,4,10,6))


if __name__=='__main__': unittest.main()
