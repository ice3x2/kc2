"""CON-ARCH-006 intact old pockets alone do not prove magnet insertion access."""
import unittest
from tools.review_kc2_magnetic_entry import cylinders,audit_entry


class MagneticEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import cadquery as cq
        cls.old=cq.Workplane('XY').box(2.4,20,3.5,centered=(False,False,False)).val().translate((.1,97,-1))
        cls.tools=cylinders('left');cls.oldmag=cls.old.cut(*[r['pocket'] for r in cls.tools.values()])
        cls.wall=cq.Workplane('XY').box(1.2,20,3.5,centered=(False,False,False)).val().translate((-1.5,97,-1))
        cls.normal=cls.old.fuse(cls.wall)
        cls.mag=cls.oldmag.fuse(cls.wall).cut(*[r['entry'] for r in cls.tools.values()])

    def test_CON_ARCH_006_open_entries_retained_back_web_and_exact_delta(self):
        r=audit_entry('left',self.normal,self.mag,self.old,self.oldmag)
        self.assertEqual(r['errors'],[])

    def test_CON_ARCH_006_old_void_preserved_but_wall_cap_blocks(self):
        blocked=self.oldmag.fuse(self.wall)
        r=audit_entry('left',self.normal,blocked,self.old,self.oldmag)
        self.assertTrue(any('external corridor' in e for e in r['errors']))

    def test_CON_ARCH_006_deep_cut_through_back_wall_rejected(self):
        through=self.mag.cut(*[r['back_web'] for r in self.tools.values()])
        r=audit_entry('left',self.normal,through,self.old,self.oldmag)
        self.assertTrue(any('back web' in e for e in r['errors']))
        self.assertGreater(r['delta']['expected_vs_actual_extra_mm3'],.002)

    def test_CON_ARCH_006_unrelated_material_removal_rejected(self):
        import cadquery as cq
        bad=self.mag.cut(cq.Solid.makeCylinder(.3,1,cq.Vector(.1,99,.5),cq.Vector(1,0,0)))
        self.assertTrue(audit_entry('left',self.normal,bad,self.old,self.oldmag)['errors'])

    def test_CON_ARCH_006_no_new_wall_cannot_fake_access_revision(self):
        self.assertTrue(audit_entry('left',self.old,self.oldmag,self.old,self.oldmag)['errors'])


if __name__=='__main__':unittest.main()
