"""CON-ARCH-006 floor-only actual receiver contract."""
import unittest
from shapely.geometry import box,Point
from shapely.ops import unary_union


def fixture():
    from tools.review_kc2_local_covers import prism
    a=box(-6,-6,-.1,19)
    for y in (0,13):
        a=a.union(box(-.2,y-1,3,y+1)).union(Point(3,y).buffer(2.25,quad_segs=24))
    b=box(.1,-6,9,19).difference(a.buffer(.40004,quad_segs=128))
    return [prism(a,-2.2,2.5).Solids()[0],prism(b,-2.2,2.5).Solids()[0]]


class FloorReceiverTests(unittest.TestCase):
    def test_valid_pair_has_two_rings_and_eight_actual_motion_tests(self):
        from tools.review_kc2_floor_receiver import inspect_pair
        result=inspect_pair(fixture(),0,(0,13))
        self.assertEqual(result['errors'],[])
        self.assertEqual(len(result['captures']),2)
        self.assertTrue(all(len(c['motions'])==4 for c in result['captures']))
        self.assertTrue(all(m['collision_mm3']>0 for c in result['captures'] for m in c['motions']))
        self.assertFalse(result['physical_qualified'])

    def test_missing_floor_ring_rejected_even_with_nominal_throat(self):
        from tools.review_kc2_floor_receiver import inspect_pair
        from tools.review_kc2_local_covers import prism
        a,b=fixture();b=b.cut(prism(box(6,-.3,7,.3),-2.2,-1))
        result=inspect_pair([a,b],0,(0,13))
        self.assertTrue(any('ring' in e for e in result['errors']))

    def test_missing_feature_and_sloped_floor_rejected(self):
        from tools.review_kc2_floor_receiver import inspect_pair
        from tools.review_kc2_local_covers import prism
        a,b=fixture()
        self.assertTrue(inspect_pair([a,b],0,(0,))['errors'])
        b=b.cut(prism(box(6,-.3,7,.3),-1.8,-1))
        result=inspect_pair([a,b],0,(0,13))
        self.assertTrue(any('floor' in e for e in result['errors']))


if __name__=='__main__':unittest.main()
