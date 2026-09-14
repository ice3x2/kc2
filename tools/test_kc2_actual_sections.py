"""CON-ARCH-006 face-wire sections preserve holes without solid classifiers."""
import unittest
import cadquery as cq
from shapely.geometry import box
from tools.kc2_solid_plate import Layer
from tools.kc2_actual_sections import section_geometry,audit_prismatic_solid

class ActualSectionTests(unittest.TestCase):
    def test_hole_and_separate_island_are_not_filled(self):
        base=cq.Workplane('XY').rect(8,8).rect(4,4).extrude(2).val()
        island=cq.Workplane('XY').rect(1,1).extrude(2).val()
        actual=section_geometry(cq.Compound.makeCompound([base,island]),1)
        expected=box(-4,-4,4,4).difference(box(-2,-2,2,2)).union(box(-.5,-.5,.5,.5))
        self.assertLess(actual.symmetric_difference(expected).area,1e-8)
    def test_empty_height(self):
        self.assertTrue(section_geometry(cq.Workplane('XY').rect(2,2).extrude(1).val(),3).is_empty)
    def test_missing_void_rejected(self):
        shape=cq.Workplane('XY').rect(4,4).extrude(2).val()
        layers=[Layer(0,2,box(-2,-2,2,2).difference(box(-1,-1,1,1)))]
        self.assertTrue(audit_prismatic_solid(shape,layers)['errors'])
    def test_hidden_height_transition_rejected(self):
        base=cq.Workplane('XY').rect(4,4).extrude(2).val()
        pocket=cq.Workplane('XY').workplane(offset=.7).rect(1,1).extrude(.2).val()
        self.assertIn('unexpected vertical transition',audit_prismatic_solid(base.cut(pocket),[Layer(0,2,box(-2,-2,2,2))])['errors'])
    def test_full_prism_passes(self):
        shape=cq.Workplane('XY').rect(4,4).extrude(2).val()
        self.assertEqual(audit_prismatic_solid(shape,[Layer(0,2,box(-2,-2,2,2))])['errors'],[])

if __name__=='__main__':unittest.main()
