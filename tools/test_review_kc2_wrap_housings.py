"""CON-ARCH-006 actual-output reviewer must reject old-height housings."""
import unittest
import tempfile
from pathlib import Path
import trimesh
from shapely.geometry import box
from tools.review_kc2_wrap_housings import required_section, check_bindings, clearance_section


class ActualSleeveReviewTests(unittest.TestCase):
    def test_changed_generation_source_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(ValueError):
                check_bindings(root, {'missing-source.py': '0'*64})

    def test_actual_mesh_cap_collision_rejected(self):
        mesh = trimesh.creation.box(extents=[2, 2, 2])
        self.assertFalse(clearance_section(mesh, 0, box(-.5, -.5, .5, .5), .3)['pass'])

    def test_actual_mesh_gap_not_just_zero_overlap(self):
        mesh = trimesh.creation.box(extents=[2, 2, 2])
        self.assertFalse(clearance_section(mesh, 0, box(1.1, -1, 2, 1), .3)['pass'])
        self.assertTrue(clearance_section(mesh, 0, box(1.31, -1, 2, 1), .3)['pass'])

    def test_nominal_shape_not_enough_if_wall_stops_at_pcb(self):
        m = trimesh.creation.box(extents=[1.2, 10, 6.3])
        m.apply_translation([.6, 5, .95])  # Z-2.20..4.10
        row = required_section(m, 5.5, box(0, 0, 1.2, 10))
        self.assertFalse(row['pass'])
        self.assertAlmostEqual(row['missing_mm2'], 12)

    def test_tall_wall_section_passes(self):
        m = trimesh.creation.box(extents=[1.2, 10, 7.8])
        m.apply_translation([.6, 5, 1.7])  # Z-2.20..5.60
        self.assertTrue(required_section(m, 5.5, box(0, 0, 1.2, 10))['pass'])

    def test_disappearing_wall_segment_is_not_tolerated(self):
        m = trimesh.creation.box(extents=[1.2, 9, 7.8])
        m.apply_translation([.6, 4.5, 1.7])
        self.assertFalse(required_section(m, 5.5, box(0, 0, 1.2, 10))['pass'])


if __name__ == '__main__':
    unittest.main()
