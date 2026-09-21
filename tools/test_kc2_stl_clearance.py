"""CON-ARCH-006: float32 clearance never overrides a failing CAD gap."""
import unittest
from tools.kc2_stl_clearance import assess

class ClearanceTests(unittest.TestCase):
    def test_float32_rounding_with_passing_cad(self):
        self.assertTrue(assess(.39989471435546875,.3999,150)['pass'])
    def test_real_cad_shortfall_is_rejected(self):
        self.assertFalse(assess(.39989471435546875,.39989,150)['pass'])
    def test_mesh_shortfall_beyond_quantization_is_rejected(self):
        self.assertFalse(assess(.3998,.3999,150)['pass'])
    def test_nonfinite_values_are_rejected(self):
        self.assertFalse(assess(float('nan'),.4,150)['pass'])
    def test_global_coordinates_are_not_part_print_extents(self):
        self.assertTrue(assess(.39989471435546875,.3999,165)['pass'])
    def test_excessively_coarse_coordinates_are_rejected(self):
        self.assertFalse(assess(.4,.4,1e6)['pass'])

if __name__=='__main__':unittest.main()
