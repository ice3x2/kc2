"""CON-ARCH-006 fail-closed actual SOLID/SOLID distance evidence."""
import math
import unittest
import cadquery as cq
from tools.kc2_solid_clearance import pair_clearance, padded_bounds


class SolidClearanceTests(unittest.TestCase):
    def setUp(self):
        self.outer = cq.Workplane('XY').box(10,10,10).val()
        self.inner = cq.Workplane('XY').box(1,1,1).val()

    def test_inside_contact_and_overlap_rejected(self):
        for other in (self.inner, self.inner.translate((5.5,0,0)), self.inner.translate((5,0,0))):
            self.assertFalse(pair_clearance(self.outer, other)['clear'])

    def test_cavity_uses_real_solid_distance(self):
        cavity = self.outer.cut(cq.Workplane('XY').box(4,4,4).val()).Solids()[0]
        row = pair_clearance(cavity, self.inner)
        self.assertTrue(row['clear'])
        self.assertEqual(row['method'], 'solid_solid_extrema')
        self.assertAlmostEqual(row['distance_mm'], 1.5)

    def test_compounds_are_rejected_even_one_solid(self):
        with self.assertRaises(ValueError):
            pair_clearance(cq.Compound.makeCompound([self.outer]), self.inner)

    def test_disjoint_bounds_are_padded_outward(self):
        row = pair_clearance(self.outer, self.inner.translate((7,0,0)))
        self.assertEqual(row['method'], 'outward_padded_aabb')
        self.assertTrue(row['clear'])
        self.assertLess(row['distance_lower_bound_mm'], 1.5)

    def test_missing_nonfinite_or_inverted_bounds_rejected(self):
        for bounds in (None, [0]*5, [0,0,0,math.inf,1,1], [1,0,0,0,1,1]):
            with self.assertRaises(ValueError): padded_bounds(bounds)

    def test_failed_or_nonfinite_solver_rejected(self):
        class Fake:
            def __init__(self,*args): pass
            def LoadS1(self,*args): pass
            def LoadS2(self,*args): pass
            def SetMultiThread(self,*args): pass
            def Perform(self): pass
            def IsDone(self): return False
            def Value(self): return math.nan
        for done in (False, True):
            Fake.IsDone = lambda self: done
            with self.assertRaises(ValueError):
                pair_clearance(self.outer,self.inner,distance_factory=Fake)

    def test_solver_is_loaded_then_multithread_performed_exactly_once(self):
        calls=[]
        class Fake:
            def __init__(self,*args):calls.append(('construct',len(args)))
            def LoadS1(self,shape):calls.append(('load1',))
            def LoadS2(self,shape):calls.append(('load2',))
            def SetMultiThread(self,value):calls.append(('threads',value))
            def Perform(self):calls.append(('perform',))
            def IsDone(self):return True
            def Value(self):return .1
        pair_clearance(self.outer,self.inner,distance_factory=Fake)
        self.assertEqual(calls,[('construct',0),('load1',),('load2',),('threads',True),('perform',)])

    def test_complete_pair_inventory_includes_failed_containment(self):
        from tools.kc2_solid_clearance import clearance_inventory
        rows=clearance_inventory([self.outer],[self.inner,self.inner.translate((7,0,0))])
        self.assertEqual([(r['part'],r['tool']) for r in rows],[(0,0),(0,1)])
        self.assertEqual([r['clear'] for r in rows],[False,True])


if __name__=='__main__': unittest.main()
