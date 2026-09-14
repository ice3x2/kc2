"""CON-ARCH-006 retained clip-root witness regression."""
import unittest
from shapely.geometry import box
from tools.review_kc2_ab_ligament import ligament_witness


class LigamentTests(unittest.TestCase):
    def test_detects_point_four_four_ligament(self):
        section=box(0,0,10,10).difference(box(0,0,10,4.56)).difference(box(0,5,10,10))
        result=ligament_witness(section,box(0,5,10,10),box(2,4,8,4.99))
        self.assertEqual(result['status'],'failed')
        self.assertAlmostEqual(result['minimum_local_mm'],.44)


if __name__=='__main__':unittest.main()
