"""CON-ARCH-006 no generic waiver for failed actual feature evidence."""
import copy
import unittest
from shapely.geometry import box
from tools import review_kc2_registered_upper_mask_contract as r

class MaskContractTests(unittest.TestCase):
    def part(self):
        return dict(status='pass',errors=[],levels_mm=[4.1,4.4],sections=[dict(z_mm=4.25,missing_mm2=0,extra_mm2=0,actual_area_mm2=1)],volume_error_mm3=0)
    def test_only_known_seam_diagnostics_and_all_actual_parts_pass(self):
        d=dict(status='failed',errors=list(r.SEAM_ERRORS),parts=[self.part(),self.part()])
        r.diagnostic_gate(d)
        for mutant in [dict(d,errors=['functional void obstructed']),dict(d,parts=[self.part()]),dict(d,status='pass')]:
            with self.assertRaises(ValueError):r.diagnostic_gate(mutant)
        bad=copy.deepcopy(d);bad['parts'][0]['sections']=[]
        with self.assertRaises(ValueError):r.diagnostic_gate(bad)
    def test_strict_combined_actual_and_contract_area_budget(self):
        actual=box(0,0,1,1);expected=actual
        self.assertFalse(r.area_gate(expected,actual,.0002,.0002)['errors'])
        self.assertTrue(r.area_gate(expected,actual.difference(box(0,0,.1,.1)),0,0)['errors'])
        self.assertTrue(r.area_gate(expected,actual.union(box(2,2,3,3)),0,0)['errors'])
        self.assertTrue(r.area_gate(expected,actual,.0011,0)['errors'])
    def test_source_conflicts_fail(self):
        with self.assertRaises(ValueError):r.merge_bindings([{'source_sha256':{'a':'1'*64}},{'source_sha256':{'a':'2'*64}}])
    def fixture(self):
        domain=box(0,0,10,10);empty=domain.difference(domain)
        old=dict(plan_wkt={k:(domain if k in ('domain','lands','bosses') else empty).wkt for k in ('domain','lands','bosses','body','openings','service','bores','pockets')})
        masks=[box(0,0,4.8,10),box(5.2,0,10,10)];levels=[4.1,4.4,5.2,7.8,9.3]
        generation=dict(side='right',kind='mx',status='generated_pending_independent_review',parts=[dict(layers=[dict(z0=a,z1=b,wkt=m.wkt) for a,b in zip(levels,levels[1:])]) for m in masks])
        diag=dict(status='failed',errors=list(r.SEAM_ERRORS),parts=[dict(status='pass',errors=[],levels_mm=levels,volume_error_mm3=0,
          sections=[dict(z_mm=(a+b)/2,missing_mm2=0,extra_mm2=0,actual_area_mm2=m.area) for a,b in zip(levels,levels[1:])]) for m in masks],
          independent_features=[dict(z=(a+b)/2,errors=[]) for a,b in zip(levels,levels[1:])])
        profile=dict(status='pass',errors=[],kind='mx',feature_count=2,clip_ring_nominal_mm=.6,neck_width_mm=2,head_diameter_mm=4,
          actual_full_projection_gap_mm=.4,augmented_masks_wkt=[m.wkt for m in masks],sections=[dict(z0_mm=a,z1_mm=b,errors=[],capture_required=a>=7.8,
          one_mm_motion_collision_area_mm2={k:1 for k in ('positive_x','negative_x','positive_y','negative_y')} if a>=7.8 else {}) for a,b in zip(levels,levels[1:])])
        return old,generation,diag,profile
    def test_omitted_stratum_and_changed_mask_are_not_waived(self):
        old,g,d,p=self.fixture();self.assertEqual(r.compare('mx',old,g,d,p)['status'],'pass')
        bad=copy.deepcopy(d);bad['parts'][0]['sections'].pop()
        with self.assertRaises(ValueError):r.compare('mx',old,g,bad,p)
        bad=copy.deepcopy(p);bad['augmented_masks_wkt'][0]=box(0,0,4.7,10).wkt
        self.assertEqual(r.compare('mx',old,g,d,bad)['status'],'failed')
    def test_added_or_missing_functional_material_is_rejected(self):
        old,g,d,p=self.fixture()
        for geometry in (box(0,0,4.7,10),box(0,0,4.9,10)):
            changed=copy.deepcopy(g);changed['parts'][0]['layers'][2]['wkt']=geometry.wkt
            self.assertEqual(r.compare('mx',old,changed,d,p)['status'],'failed')

if __name__=='__main__':unittest.main()
