"""CON-ARCH-006 actual lower pair capture/root and floor continuity gates."""
import unittest
from shapely.geometry import box,Point
from tools.kc2_central_flexure import prism
from tools.kc2_lower_split_extension import retained_key_relief
from tools.review_kc2_lower_split import inspect_pair
class LowerPairReview(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        key=box(4.9,9,8,11).union(Point(8,10).buffer(2.25,quad_segs=24))
        a=box(0,0,4.9,20).union(key);b=box(5.1,0,15,20).difference(key.buffer(.2))
        a,b=retained_key_relief(a,b,box(0,0,15,20),5,[10])
        cls.pair=[prism(a,-2.2,2.5),prism(b,-2.2,2.5)]
    def test_valid_pair_passes(self):self.assertEqual(inspect_pair(self.pair,5,[10])['errors'],[])
    def test_missing_root_rejected(self):
        a=self.pair[0].cut(prism(box(4.8,9,5.2,9.5),-2.2,2.5))
        self.assertIn('root material missing',inspect_pair([a,self.pair[1]],5,[10])['errors'])
    def test_hidden_head_hole_rejected(self):
        a=self.pair[0].cut(prism(box(7.8,9.8,8.2,10.2),-.5,.5))
        self.assertIn('head material missing',inspect_pair([a,self.pair[1]],5,[10])['errors'])
    def test_overwide_receiver_throat_rejected(self):
        b=self.pair[1].cut(prism(box(5.1,8.5,7,11.5),-2.2,2.5))
        self.assertIn('receiver throat differs from 2.80 mm',inspect_pair([self.pair[0],b],5,[10])['errors'])
if __name__=='__main__':unittest.main()
