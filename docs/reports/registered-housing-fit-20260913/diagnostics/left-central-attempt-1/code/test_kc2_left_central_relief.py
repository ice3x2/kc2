"""CON-ARCH-006 regression for the actual left-added central collision."""
import unittest
from shapely.geometry import box
from shapely import affinity
from shapely.ops import unary_union
from tools.kc2_left_central_relief import relief_plan
from tools.kc2_central_flexure import flexure_plan


def place(g,y):
    return affinity.translate(affinity.scale(g,xfact=-1,origin=(0,0)),xoff=.1,yoff=y)


class LeftCentralReliefTests(unittest.TestCase):
    def fixture(self):
        wall=unary_union([place(box(.4,-6,1.6,6),y) for y in (95,117)])
        floor=unary_union([place(box(-2,-6,1.6,6),y) for y in (95,117)])
        return wall,floor,relief_plan(wall,floor)

    def test_actual_collision_regression_and_exact_male_retention(self):
        wall,floor,p=self.fixture();f=flexure_plan()
        for y in (95,117):
            male=place(f['male'],y);beams=place(f['beam_body'],y)
            root=place(f['root_floor'],y)
            self.assertAlmostEqual(wall.intersection(beams).area,.96)
            self.assertAlmostEqual(floor.intersection(root).area,.96)
            self.assertLess(p['wall_low'].intersection(beams).area,1e-10)
            self.assertLess(p['floor'].intersection(root).area,1e-10)
            for z0,z1,g in p['cuts']:
                if z0<1.5:self.assertLess(g.intersection(male).area,1e-10)
        self.assertEqual(p['wall_z'],[-1.,1.5,1.8,4.1])
        self.assertEqual(p['floor_z'],[-2.2,-1.])

    def test_full_wall_window_no_half_millimetre_cheek(self):
        wall,_,p=self.fixture()
        for y in (95,117):
            window=place(box(.4,-2.85,1.6,2.85),y)
            self.assertLess(p['wall_transition'].intersection(window).area,1e-10)
            self.assertLess(p['wall_low'].intersection(place(box(.4,1.21,1.6,2.85),y)).area,1e-10)
        self.assertTrue(p['wall_top'].equals(wall))
        self.assertEqual(p['lintel_span_mm'],5.7)
        self.assertEqual(p['floor_clearance_mm'],.3)

    def test_only_declared_new_additions_removed(self):
        wall,floor,p=self.fixture()
        for z0,z1,g in p['cuts']:
            allowed=floor if z0==-2.2 else wall
            self.assertLess(g.difference(allowed).area,1e-10)
            self.assertGreater(g.area,0)
        for y in (95,117):
            old=place(box(-5,-6,.1,6),y)
            for _,_,g in p['cuts']:self.assertLess(g.intersection(old).area,1e-10)
            part=p['floor'].intersection(place(box(-3,-7,2,7),y))
            self.assertEqual(part.geom_type,'Polygon')
            self.assertEqual(len(part.interiors),0)


if __name__=='__main__':unittest.main()
