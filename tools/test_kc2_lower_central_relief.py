"""CON-ARCH-006 new perimeter must not immobilize central flexure cheeks."""
import unittest
from shapely.geometry import box
from tools.kc2_lower_central_relief import central_free_envelopes,wall_bands,male_insertion_envelopes,floor_relief
class FreeCheek(unittest.TestCase):
    def test_new_wall_leaves_side_and_top_free(self):
        envelope=central_free_envelopes()
        bands=wall_bands(box(140,80,160,125))
        self.assertEqual(bands[0][0:2],(-1,1.8))
        self.assertLess(bands[0][2].intersection(envelope).area,1e-8)
        self.assertGreater(bands[1][2].intersection(envelope).area,1)
    def test_insertion_channel_open_in_new_wall_and_floor(self):
        male=male_insertion_envelopes();wall=box(140,80,160,125)
        self.assertLess(wall_bands(wall)[0][2].intersection(male).area,1e-8)
        self.assertLess(floor_relief(wall).intersection(male).area,1e-8)
if __name__=='__main__':unittest.main()
