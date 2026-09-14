"""CON-ARCH-006 left-only relieved wall verification, not a physical fit test."""
import unittest
from shapely.geometry import box
from tools.review_kc2_left_central_voids import required_plan, metric_errors, generation_gate


class LeftCentralVoids(unittest.TestCase):
    def test_literal_plan_matches_independently_declared_producer(self):
        from tools.kc2_left_central_relief import relief_plan
        wall=box(-1.5,90,-.3,121);floor=box(-2,90,3,121)
        actual=required_plan(wall,floor);expected=relief_plan(wall,floor)
        self.assertEqual([(a,b) for a,b,_ in actual['bands']],[(-1,1.5),(1.5,1.8),(1.8,4.1)])
        for (_,_,g),key in zip(actual['bands'],('wall_low','wall_transition','wall_top')):
            self.assertLess(g.symmetric_difference(expected[key]).area,1e-10)
        self.assertLess(actual['floor'].symmetric_difference(expected['floor']).area,1e-10)
        self.assertGreater(wall.difference(actual['bands'][0][2]).area,0)
        self.assertLess(wall.intersection(actual['male']).difference(actual['bands'][0][2]).area,1e-10)
        self.assertLess(floor.intersection(actual['male']).difference(actual['floor']).area,1e-10)

    def test_metric_gate_rejects_nonfinite_boolean_negative_missing_and_loss(self):
        from tools.review_kc2_left_central_voids import ZERO_FIELDS
        row=dict(body_count=1,required_stock_count=2,required_stock_details_mm3=[0.,0.],protected_male_missing_mm3={'95':0.,'117':0.},
                 **{k:0. for k in ZERO_FIELDS})
        self.assertFalse(metric_errors(row))
        for bad in (True,float('nan'),float('inf'),-.1,.00201):
            with self.subTest(bad=bad):
                self.assertTrue(metric_errors(dict(row,required_missing_mm3=bad)))
        del row['pilot_obstruction_mm3']
        self.assertTrue(metric_errors(row))

    def test_individual_required_stock_cannot_cancel_or_disappear(self):
        from tools.review_kc2_left_central_voids import ZERO_FIELDS
        row=dict(body_count=1,required_stock_count=2,required_stock_details_mm3=[0.,0.],protected_male_missing_mm3={'95':0.,'117':0.},
                 **{k:0. for k in ZERO_FIELDS})
        for fields in ({'required_stock_details_mm3':[-1.,1.]},
                       {'required_stock_details_mm3':None},
                       {'required_stock_details_mm3':[0.]},
                       {'required_stock_details_mm3':[float('nan'),0.]},
                       {'required_stock_details_mm3':[True,0.]},
                       {'required_stock_count':True},
                       {'required_stock_details_mm3':[.001,0.]},
                       {'required_stock_details_mm3':[.003,0.],'required_missing_mm3':.003}):
            with self.subTest(fields=fields):self.assertTrue(metric_errors(dict(row,**fields)))
        self.assertFalse(metric_errors(dict(row,required_stock_details_mm3=[.001,0.],required_missing_mm3=.001)))
        for male in ({'95':-.1,'117':.1},{'95':0.},{'95':1e-15,'117':0.},{'95':False,'117':0.}):
            self.assertTrue(metric_errors(dict(row,protected_male_missing_mm3=male)))

    def test_actual_trimmed_attachment_not_untrimmed_nominal_prism_is_protected(self):
        from tools.review_kc2_local_covers import prism,cut_union
        from tools.review_kc2_left_central_voids import protected_male_missing
        nominal=prism(box(0,0,3,2),-2.2,1.5)
        trim=prism(box(0,0,.2,2),-1,1.5)
        actual=nominal.cut(trim)
        self.assertGreater(cut_union(nominal,actual).Volume(),.99)
        self.assertEqual(protected_male_missing(actual,{95:actual,117:actual}),{'95':0.,'117':0.})
        damaged=actual.cut(prism(box(1,0,1.2,2),-1,1.5))
        self.assertGreater(protected_male_missing(damaged,{95:actual,117:actual})['95'],.99)

    def test_actual_feature_loader_rejects_changed_bytes_or_missing_reference(self):
        import json,hashlib
        import cadquery as cq
        from tools.review_kc2_left_central_voids import load_males,FEATURES
        shape=cq.Workplane('XY').box(1,1,1).val()
        raw={FEATURES+'/left-central-y95.step':b'95',FEATURES+'/left-central-y117.step':b'117','tools/fixture.py':b'code'}
        manifest=dict(status='feature_geometry_pass_integration_pending',
            source_sha256={'tools/fixture.py':hashlib.sha256(b'code').hexdigest()},
            outputs={k.rsplit('/',1)[-1]:hashlib.sha256(v).hexdigest() for k,v in raw.items() if k.endswith('.step')},
            features=[dict(name='left-central-y'+str(y),volume_mm3=shape.Volume()) for y in (95,117)])
        raw[FEATURES+'/central-features.json']=json.dumps(manifest).encode()
        self.assertEqual(set(load_males(raw.__getitem__,lambda _:shape)),{95,117})
        raw[FEATURES+'/left-central-y95.step']=b'changed'
        with self.assertRaises(ValueError):load_males(raw.__getitem__,lambda _:shape)
        raw[FEATURES+'/left-central-y95.step']=b'95'
        del manifest['outputs']['left-central-y117.step']
        raw[FEATURES+'/central-features.json']=json.dumps(manifest).encode()
        with self.assertRaises(ValueError):load_males(raw.__getitem__,lambda _:shape)

    def test_whole_import_rejects_floating_face_edge_and_vertex(self):
        import cadquery as cq
        from tools.review_kc2_left_central_voids import validate_shape
        solid=cq.Workplane('XY').box(1,1,1).val()
        extras=[solid.Faces()[0].translate((10,0,0)),
                cq.Edge.makeLine((10,0,0),(11,0,0)),cq.Vertex.makeVertex(10,0,0)]
        for extra in extras:
            with self.subTest(kind=extra.ShapeType()):
                with self.assertRaises(ValueError):validate_shape(cq.Compound.makeCompound([solid,extra]))

    def test_no_old_generation_can_overwrite_current_report(self):
        with self.assertRaises(ValueError):generation_gate({'status':'generated_pending_independent_review'},False)
        from tools.review_kc2_left_central_voids import CONTRACT
        record=dict(status='generated_pending_independent_review',side='left',magnetic=False,
                    body_count=1,left_central_relief=CONTRACT)
        generation_gate(record,False)
        with self.assertRaises(ValueError):generation_gate(dict(record,side='right'),False)

    def test_closed_actual_solid_uses_shell_closure_not_topods_solid_flag(self):
        import cadquery as cq
        from tools.review_kc2_left_central_voids import validate_shape
        validate_shape(cq.Workplane('XY').box(1,1,1).val())
        with self.assertRaises(ValueError):validate_shape(cq.Compound.makeCompound([
            cq.Workplane('XY').box(1,1,1).val(),cq.Workplane('XY').box(1,1,1).val().translate((3,0,0))]))

    def test_original_stock_loss_is_not_relief_allowance(self):
        from tools.review_kc2_local_covers import prism
        from tools.review_kc2_lower_voids_v2 import removed_outside
        original=prism(box(0,0,2,2),-2.2,2.5)
        cut=prism(box(0,0,1,1),-1,1.5)
        self.assertGreater(removed_outside(original,original.cut(cut),[]),2.49)


if __name__=='__main__':unittest.main()
