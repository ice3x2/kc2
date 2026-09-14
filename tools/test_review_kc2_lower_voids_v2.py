"""CON-ARCH-006 actual clearance, permitted relief and magnetic entry gates."""
import unittest
from shapely.geometry import box
from tools.kc2_central_flexure import prism
from tools.review_kc2_lower_voids_v2 import removed_outside, magnet_delta

class ActualVoids(unittest.TestCase):
    def test_permitted_receiver_relief_does_not_waive_other_loss(self):
        base=prism(box(0,0,10,10),0,2)
        relief=prism(box(0,0,1,10),0,2)
        final=base.cut(relief)
        self.assertLess(removed_outside(base,final,[relief]),1e-8)
        damaged=final.cut(prism(box(5,5,6,6),0,2))
        self.assertGreater(removed_outside(base,damaged,[relief]),1.9)
    def test_old_blind_void_and_added_entry_are_distinguished(self):
        old=prism(box(1,0,3,3),0,2)
        blind=prism(box(1,1,2,2),0,2)
        wall=prism(box(-1,0,0,3),0,2)
        access=prism(box(-2,1,1,2),0,2)
        normal=old.fuse(wall);magnetic=normal.cut(blind).cut(access)
        row=magnet_delta(old,old.cut(blind),normal,magnetic,[access])
        self.assertTrue(all(row[k]<1e-8 for k in ('missing_mm3','extra_mm3','blocked_mm3','entry_obstruction_mm3')))
        capped=normal.cut(blind)
        self.assertGreater(magnet_delta(old,old.cut(blind),normal,capped,[access])['entry_obstruction_mm3'],1.9)
    def test_unapproved_magnet_cut_rejected(self):
        normal=prism(box(0,0,5,5),0,2)
        blind=prism(box(0,1,1,2),0,2)
        mag=normal.cut(blind)
        damaged=mag.cut(prism(box(3,3,4,4),0,2))
        self.assertGreater(magnet_delta(normal,mag,normal,damaged,[])['extra_mm3'],1.9)

if __name__=='__main__':unittest.main()
