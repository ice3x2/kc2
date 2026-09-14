"""CON-ARCH-006 complete actual print-file inventory gate."""
import unittest
from tools.review_kc2_registered_mesh import required_stls

class InventoryTests(unittest.TestCase):
    def test_left_one_and_right_two(self):
        self.assertEqual(required_stls('left','mx'),['kc2_left_mx_upper_housing.stl'])
        self.assertEqual(len(required_stls('right','deep_sea')),2)
    def test_unknown_identity_rejected(self):
        for side,kind in [('Left','mx'),('left','choc'),('right','')]:
            with self.assertRaises(ValueError):required_stls(side,kind)

if __name__=='__main__':unittest.main()
