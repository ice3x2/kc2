"""CON-ARCH-006 retained silicone-foot stability regression."""
import unittest
from shapely.geometry import box
from tools.review_kc2_enclosure_feet import check_feet

class FeetTest(unittest.TestCase):
    def test_safe_four_contacts(self):
        self.assertFalse(check_feet(box(0,0,30,30),[(5,5),(25,5),(25,25),(5,25)],(15,15))['errors'])
    def test_seam_crossing_rejected(self):
        self.assertIn('foot disk crosses edge or seam',check_feet(box(0,0,30,30),[(2,5),(25,5),(25,25),(5,25)],(15,15))['errors'])
    def test_centroid_outside_contact_hull(self):
        self.assertIn('centroid outside foot contact hull',check_feet(box(0,0,40,40),[(5,5),(15,5),(15,15),(5,15)],(35,35))['errors'])
