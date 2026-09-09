"""CON-ARCH-006: continuous component-clear exterior walls."""
import unittest
from shapely.geometry import box
from tools import kc2_enclosure_plan as e


class EnclosureTests(unittest.TestCase):
    def test_variable_walls_preserve_minimum_and_join_gap(self):
        a=e.wall_plan(box(0,0,10,10),box(3,3,4,4),.4)
        b=e.wall_plan(box(11.8,0,21.8,10),box(15,3,16,4),.4)
        l,r=e.allocate_outer_walls(a['inner'],b['inner'])
        self.assertLess(a['outer'].difference(l.buffer(1e-6)).area,1e-6)
        self.assertLess(b['outer'].difference(r.buffer(1e-6)).area,1e-6)
        self.assertTrue(e.join_review(l,r)['passes'])

    def test_wall_is_closed_and_component_clear(self):
        board=box(0,0,20,20)
        components=box(19,8,21,12)
        p=e.wall_plan(board,components,.8)
        self.assertTrue(p['inner'].covers(board.buffer(.3)))
        self.assertTrue(p['inner'].covers(components.buffer(.3)))
        self.assertEqual(p['wall'].intersection(components).area,0)
        self.assertEqual(p['outer'].geom_type,'Polygon')
        self.assertEqual(len(p['wall'].interiors),1)
        self.assertGreater(p['wall'].area,0)

    def test_reject_unprintably_thin_or_nonfinite_wall(self):
        for thickness in [0,.1,.39,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):e.wall_plan(box(0,0,20,20),box(5,5,6,6),thickness)

    def test_join_review_detects_contact_and_overlap(self):
        left=box(0,0,10,10)
        self.assertFalse(e.join_review(left,box(9,0,19,10))['passes'])
        self.assertFalse(e.join_review(left,box(10,0,20,10))['passes'])
        self.assertTrue(e.join_review(left,box(10.5,0,20.5,10))['passes'])


if __name__=='__main__':unittest.main(verbosity=2)
