"""CON-ARCH-006 seating diagnostics, including deliberate failure cases."""
import unittest
import trimesh
from shapely.geometry import box
from tools.kc2_pcb_seating import horizontal_section, insertion_sections, overlap_depth


class SeatingTests(unittest.TestCase):
    def test_section_preserves_internal_void(self):
        m = trimesh.creation.annulus(r_min=4, r_max=6, height=2, sections=4)
        m.apply_translation([0, 0, 3])
        section = horizontal_section(m, 3)
        self.assertAlmostEqual(section.area, 40)
        self.assertAlmostEqual(section.intersection(box(-1, -1, 1, 1)).area, 0)

    def test_insertion_detects_obstruction_above_final_pcb(self):
        m = trimesh.creation.box(extents=[1, 1, .2])
        m.apply_translation([0, 0, 4.8])
        rows = insertion_sections(m, box(-1, -1, 1, 1), 2.5)
        self.assertTrue(any(r['pcb_overlap_mm2'] > .9 for r in rows))

    def test_support_below_seat_is_not_insertion_obstruction(self):
        m = trimesh.creation.box(extents=[1, 1, 2.5])
        m.apply_translation([0, 0, 1.25])
        self.assertEqual(insertion_sections(m, box(-1, -1, 1, 1), 2.5), [])

    def test_missing_or_extra_pcb_height_loses_registration(self):
        self.assertAlmostEqual(overlap_depth(5, 4.4, 5.2, 0), .6)
        self.assertAlmostEqual(overlap_depth(5, 4.4, 5.2, .2), .4)
        self.assertEqual(overlap_depth(5, 4.4, 5.2, 1.6), 0)


if __name__ == '__main__':
    unittest.main()
