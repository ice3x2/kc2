"""CON-ARCH-006: actual section-based enclosure checks reject open walls."""
import unittest
from shapely.geometry import box
from tools.generate_kc2_enclosed_housings import prism
from tools import audit_kc2_enclosure as a


class SectionTests(unittest.TestCase):
    def test_full_disk_backing_rejects_off_axis_void(self):
        q={'x':0.,'y':0.,'z':.75,'sign':1}
        required=a.magnet_backing(q)
        stock=prism(box(0,-2,3,2),-1,3)
        self.assertLess(required.cut(stock).Volume(),1e-7)
        damaged=stock.cut(prism(box(1.3,.5,1.7,1.0),.8,1.3))
        self.assertGreater(required.cut(damaged).Volume(),.09)

    def test_actual_section_catches_missing_wall_and_component_collision(self):
        outer=box(-1,-1,11,11);inner=box(0,0,10,10);ring=outer.difference(inner)
        whole=prism(ring,-1,4.1)
        section=a.section_plan(whole,1.)
        self.assertLess(a.coverage(section,ring)['missing_area_mm2'],1e-6)
        missing=whole.cut(prism(box(-2,4,2,6),0,2))
        self.assertGreater(a.coverage(a.section_plan(missing,1.),ring)['missing_area_mm2'],1.)
        self.assertEqual(section.intersection(box(2,2,8,8)).area,0)
        self.assertGreater(section.intersection(box(-2,4,2,6)).area,1.)


if __name__=='__main__':unittest.main(verbosity=2)
