"""CON-ARCH-006 continuous nominal insertion, not just final-position fit."""
import unittest
import trimesh
from shapely.geometry import box
from tools.review_kc2_wrap_motion import sweep_overlap, prismatic_band, project_mesh, sweep_right, validate_height_band


class MotionTests(unittest.TestCase):
    def test_material_outside_certified_contact_height_is_rejected(self):
        mesh = trimesh.creation.box(extents=[2,2,2])
        with self.assertRaises(ValueError):
            validate_height_band(mesh, False)
        mesh.apply_translation([0,0,6])
        with self.assertRaises(ValueError):
            validate_height_band(mesh, True)
        validate_height_band(mesh, False)

    def test_final_clear_but_intermediate_vertical_collision_detected(self):
        fixed = [(3., 4., box(0, 0, 2, 2))]
        moving = [(1., 2., box(0, 0, 2, 2))]
        rows = sweep_overlap(fixed, moving, 5.)
        self.assertTrue(any(r['overlap_mm2'] > 3.99 for r in rows))

    def test_final_support_contact_is_not_a_volume_collision(self):
        self.assertEqual(sweep_overlap([(0., 1., box(0,0,1,1))],
                                      [(1., 2., box(0,0,1,1))], 5.), [])

    def test_sloped_relevant_faces_cannot_use_prismatic_proof(self):
        mesh = trimesh.creation.box(extents=[2,2,2])
        self.assertTrue(prismatic_band(mesh, -.9, .9))
        mesh.apply_transform(trimesh.transformations.rotation_matrix(.3, [1,0,0]))
        self.assertFalse(prismatic_band(mesh, -.9, .9))

    def test_bounded_float_serialization_drift_is_explicit(self):
        mesh = trimesh.creation.box(extents=[2,2,2])
        transform = trimesh.transformations.identity_matrix()
        transform[0,2] = 1e-6
        mesh.apply_transform(transform)
        self.assertTrue(prismatic_band(mesh, -.9, .9))

    def test_mesh_projection_and_horizontal_sweep_include_middle(self):
        projected = project_mesh(trimesh.creation.box(extents=[2,2,2]))
        self.assertAlmostEqual(projected.area, 4.)
        swept = sweep_right(projected, 10.)
        self.assertTrue(swept.covers(box(4,-.9,6,.9)))
        self.assertAlmostEqual(swept.area, 24.)


if __name__ == '__main__':
    unittest.main()
