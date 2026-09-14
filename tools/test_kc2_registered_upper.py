"""CON-ARCH-006 whole-upper rebate must remove old AND new material."""
import unittest
from shapely.geometry import box,GeometryCollection
from tools.kc2_registered_wall_plan import Registrar
from tools.kc2_registered_upper import compose_upper

class UpperTests(unittest.TestCase):
    def data(self):
        empty=GeometryCollection()
        return dict(domain=box(0,0,20,20),body=box(8,8,12,12),openings=box(8,8,12,12),
                    service=empty,bores=box(1,1,2,2),pockets=box(.9,.9,2.1,2.1),
                    bosses=box(.5,.5,2.5,2.5),lands=box(.5,.5,2.5,2.5))
    def test_groove_removes_existing_material_and_ceiling_stays(self):
        reg=Registrar(box(5,-1.2,11,0),box(3.55,-1.2,12.45,1.45),
                      box(4.75,-1.45,11.25,.25),box(3.55,-1.2,12.45,1.45))
        layers=compose_upper('deep_sea',self.data(),[reg])[0]
        low=next(l.geometry for l in layers if l.z0<=4.6<l.z1)
        roof=next(l.geometry for l in layers if l.z0<=5.3<l.z1)
        self.assertLess(low.intersection(reg.groove).area,1e-9)
        self.assertGreater(roof.intersection(reg.groove).area,0)
        self.assertTrue(any(abs(l.z0-5.2)<1e-9 for l in layers))
    def test_holes_and_body_remain_empty(self):
        p=self.data();layers=compose_upper('mx',p,[])[0]
        for l in layers:
            self.assertLess(l.geometry.intersection(p['bores']).area,1e-9)
            self.assertLess(l.geometry.intersection(p['body']).area,1e-9)
    def test_parts_do_not_fill_split_gap(self):
        layers=compose_upper('mx',self.data(),[],masks=[box(-1,-1,9.8,21),box(10.2,-1,21,21)])
        self.assertEqual(len(layers),2)
        for part in layers:
            for l in part:self.assertLess(l.geometry.intersection(box(9.8,0,10.2,20)).area,1e-9)

if __name__=='__main__':unittest.main()
