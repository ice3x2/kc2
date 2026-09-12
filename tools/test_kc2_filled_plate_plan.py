"""CON-ARCH-006 actual-board filled-plan checks, not CAD/physical evidence."""
import unittest
from shapely.geometry import Point
from shapely.ops import unary_union
from tools.generate_kc2_filled_plates import build_plan
from tools import generate_kc2_magnetic_housings as base


class ActualFilledPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plans,_,_=base.load_plans()

    def test_all_three_modes_keep_all_screws_and_do_not_bridge_right_split(self):
        for side,board in self.plans.items():
            for kind in ['mx','choc_v1','deep_sea']:
                with self.subTest(side=side,kind=kind):
                    p=build_plan(side,board,kind)
                    self.assertEqual(len(p['parts']),1 if side=='left' else 2)
                    for rows in p['parts']:
                        for row in rows:
                            self.assertLess(row.geometry.intersection(p['bores']).area,1e-7)
                            b=row.geometry.bounds
                            self.assertLessEqual(max(b[2]-b[0],b[3]-b[1]),150)
                    unions=[unary_union([r.geometry for r in rows]) for rows in p['parts']]
                    if side=='right':
                        self.assertGreaterEqual(unions[0].distance(unions[1]),.1997)
                    for hole in board['mounting_holes']:
                        center=Point(*hole['housing_center_mm'])
                        annulus=center.buffer(1.5).difference(center.buffer(.801))
                        self.assertTrue(any(unary_union([r.geometry for r in rows if r.z0==4.1]).buffer(1e-5).covers(annulus) for rows in p['parts']))


if __name__=='__main__':unittest.main()
