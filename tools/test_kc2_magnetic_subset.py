"""CON-ARCH-006 fresh exported-material subset certificate."""
import copy
import math
import unittest
from unittest.mock import MagicMock,patch,call
from tools import kc2_magnetic_subset as subset
from tools import review_kc2_magnetic_subset as reviewer


class SubsetTests(unittest.TestCase):
    def test_import_ownership_parallel_cut_and_failure_exit(self):
        import cadquery as cq
        from tools.review_kc2_lower_strata import validate_import
        self.assertIs(reviewer.validate_import,validate_import)
        compound=cq.Compound.makeCompound([self.a,self.b])
        self.assertEqual(len(reviewer.validate_import(compound)),2)
        stray=cq.Workplane('XY').rect(1,1).toPending().extrude(.1).val().Faces()[0].translate((50,0,0))
        with self.assertRaises(ValueError):reviewer.validate_import(cq.Compound.makeCompound([self.a,self.b,stray]))
        op=MagicMock();op.IsDone.return_value=True;op.Shape.return_value=self.a.wrapped
        with patch('OCP.BRepAlgoAPI.BRepAlgoAPI_Cut',return_value=op):subset.nd_cut(self.a,self.b)
        op.SetNonDestructive.assert_called_once_with(True);op.SetRunParallel.assert_called_once_with(True)
        self.assertLess(op.method_calls.index(call.SetRunParallel(True)),op.method_calls.index(call.Build()))
        with patch.object(reviewer,'run',return_value={'errors':['fail']}):self.assertEqual(reviewer.main(),1)
        with patch.object(reviewer,'run',return_value={'errors':[]}):self.assertEqual(reviewer.main(),0)
    @classmethod
    def setUpClass(cls):
        import cadquery as cq
        cls.a=cq.Workplane('XY').box(5,5,5).val()
        cls.b=cq.Workplane('XY').box(10,10,5).translate((20,0,0)).val()
        cutters=[cq.Solid.makeCylinder(1.2,1.2,cq.Vector(x,y,1.3)) for x in (17,23) for y in (-3,3)]
        cls.m=cls.b.cut(*cutters).Solids()[0]

    def test_actual_two_body_subset_and_expected_removal(self):
        before=[s.Volume() for s in (self.a,self.b,self.m)]
        result=subset.audit([self.a,self.b],[self.a,self.m])
        subset.validate_metrics(result)
        self.assertEqual(result['parts'][0]['normal_minus_magnetic_mm3'],0)
        self.assertAlmostEqual(result['removed_total_mm3'],4*math.pi*1.2**2*1.2,places=8)
        self.assertEqual(before,[s.Volume() for s in (self.a,self.b,self.m)])

    def test_generation_bounds_variant_and_order_are_measured(self):
        parts=[self.a,self.b]
        record=dict(side='right',magnetic=False,status='generated_pending_independent_review',body_count=2,
            outputs={'kc2_right_lower_housing.step':'step-sha'},
            parts=[dict(index=i,bounds_mm=subset.bounds(s),volume_mm3=s.Volume()) for i,s in enumerate(parts)])
        subset.check_generation(record,'normal','step-sha',parts)
        for key,value in [('side','left'),('magnetic',True),('body_count',True)]:
            bad=copy.deepcopy(record);bad[key]=value
            with self.assertRaises(ValueError):subset.check_generation(bad,'normal','step-sha',parts)
        with self.assertRaises(ValueError):subset.check_generation(record,'normal','step-sha',parts[::-1])
        with self.assertRaises(ValueError):subset.check_generation(record,'normal','step-sha',[self.a,self.b.translate((.1,0,0))])

    def test_added_material_empty_wrong_order_and_open_body(self):
        import cadquery as cq
        bad=self.m.fuse(cq.Workplane('XY').box(.01,.01,.01).translate((25.004,0,0)).val())
        for normal,magnetic in (([self.a,self.b],[self.a,bad]),([self.a,self.b],[]),
                 ([self.a,self.b],[self.m,self.a]),([self.a,self.b],[self.a,self.m.Shells()[0]])):
            with self.assertRaises(ValueError):subset.validate_metrics(subset.audit(normal,magnetic))

    def test_strict_numeric_zero_topology_and_identity(self):
        result=subset.audit([self.a,self.b],[self.a,self.m])
        for value in (1e-15,-1e-15,False,float('nan')):
            bad=copy.deepcopy(result);bad['parts'][0]['magnetic_minus_normal_mm3']=value
            with self.assertRaises(ValueError):subset.validate_metrics(bad)
        bad=copy.deepcopy(result);bad['parts'][0]['magnetic_minus_normal_solids']=1
        with self.assertRaises(ValueError):subset.validate_metrics(bad)
        bad=copy.deepcopy(result);bad['parts'][0]['magnetic_minus_normal_faces']=1
        with self.assertRaises(ValueError):subset.validate_metrics(bad)
        bad=copy.deepcopy(result);bad['parts'][0]['magnetic_bounds_mm']=[]
        with self.assertRaises(ValueError):subset.validate_metrics(bad)
        with self.assertRaises(ValueError):subset.check_generation({'side':'left'},'normal','x',[])


if __name__=='__main__':unittest.main()
