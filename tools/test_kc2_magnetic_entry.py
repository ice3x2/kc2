"""CON-ARCH-006 preserve old blind magnets but reopen new-wall access."""
import unittest
from shapely.geometry import box
from tools.kc2_central_flexure import prism
from tools.kc2_magnetic_entry import open_entries,entry_tools
class MagneticEntry(unittest.TestCase):
    def test_new_wall_access_open_original_side_untouched(self):
        wall=prism(box(-1.5,100,-.3,114),-1,4.1)
        original=prism(box(.1,100,2,114),-1,2.5)
        opened=open_entries(wall,'left')
        self.assertGreater(wall.Volume()-opened.Volume(),10)
        self.assertLess(sum(opened.intersect(t).Volume() for t in entry_tools('left')),1e-8)
        self.assertLess(sum(original.intersect(t).Volume() for t in entry_tools('left')),1e-8)
    def test_right_direction_does_not_cut_original_body(self):
        original=prism(box(147,100,149.3,114),-1,2.5)
        self.assertLess(sum(original.intersect(t).Volume() for t in entry_tools('right')),1e-8)
    def test_invalid_identity_rejected(self):
        with self.assertRaises(ValueError):entry_tools('middle')
if __name__=='__main__':unittest.main()
