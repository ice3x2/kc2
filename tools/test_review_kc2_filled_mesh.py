"""CON-ARCH-006 STL surface proof and full-stratum coverage mutations."""
import unittest
import trimesh
from shapely.geometry import box
from tools.kc2_solid_plate import Layer
from tools.review_kc2_filled_mesh import audit_mesh


class FilledMeshTests(unittest.TestCase):
    def setUp(self):
        self.mesh=trimesh.creation.box(extents=[10,10,2]);self.mesh.apply_translation([5,5,1])
        self.layers=[Layer(0,2,box(0,0,10,10))]

    def test_complete_solid_passes_full_sections(self):
        self.assertEqual(audit_mesh(self.mesh,self.layers)['errors'],[])

    def test_same_bounds_filled_reserved_hole_rejected(self):
        layers=[Layer(0,2,box(0,0,10,10).difference(box(4,4,6,6)))]
        self.assertIn('filled reserved space',audit_mesh(self.mesh,layers)['errors'])

    def test_missing_material_and_extra_transition_rejected(self):
        small=self.mesh.copy();small.apply_scale([.8,1,1])
        self.assertIn('unfilled structural interior',audit_mesh(small,self.layers)['errors'])
        shifted=self.mesh.copy();shifted.apply_translation([0,0,.1])
        self.assertIn('unexpected vertical transition',audit_mesh(shifted,self.layers)['errors'])

    def test_sloped_faces_cannot_use_midsection_shortcut(self):
        slope=self.mesh.copy();slope.vertices[slope.vertices[:,2]>1,0]+=.1
        self.assertIn('non-prismatic surface',audit_mesh(slope,self.layers)['errors'])

    def test_reversed_orientation_is_not_a_valid_volume(self):
        self.mesh.invert()
        self.assertIn('invalid closed positive solid',audit_mesh(self.mesh,self.layers)['errors'])


if __name__=='__main__':unittest.main()
