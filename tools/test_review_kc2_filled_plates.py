"""CON-ARCH-006 actual-solid fill audit must reject hollow/blocked cavities."""
import unittest
import cadquery as cq
from shapely.geometry import box,Point
from tools.kc2_solid_plate import Void,fill_layers,build_solid
from tools.review_kc2_filled_plates import audit_prismatic_solid


class ActualSolidAuditTests(unittest.TestCase):
    def setUp(self):
        self.domain=box(0,0,20,20)
        self.rows=fill_layers(self.domain,0,4,[Void('bore',Point(5,5).buffer(.8),0,4)])
        self.correct=build_solid(self.rows)

    def test_complete_solid_passes(self):
        self.assertEqual(audit_prismatic_solid(self.correct,self.rows)['errors'],[])

    def test_filled_screw_hole_fails(self):
        full=build_solid(fill_layers(self.domain,0,4,[]))
        self.assertTrue(audit_prismatic_solid(full,self.rows)['errors'])

    def test_wall_only_fails(self):
        shell=build_solid(fill_layers(self.domain.difference(self.domain.buffer(-1.2)),0,4,[]))
        self.assertTrue(audit_prismatic_solid(shell,self.rows)['errors'])

    def test_hidden_internal_pocket_between_sample_planes_fails(self):
        hidden=cq.Solid.makeBox(1,1,.1,cq.Vector(10,10,1.1))
        bad=self.correct.cut(hidden)
        result=audit_prismatic_solid(bad,self.rows)
        self.assertIn('unexpected vertical transition',result['errors'])

    def test_sloped_surface_is_not_assumed_prismatic(self):
        cone=cq.Solid.makeCone(1,2,4,cq.Vector(10,10,0))
        self.assertTrue(audit_prismatic_solid(cone,self.rows)['errors'])


if __name__=='__main__':unittest.main()
