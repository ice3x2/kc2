"""CON-ARCH-006 independent full-fill contract and mutation regression."""
import copy
from dataclasses import asdict
import unittest
from shapely.geometry import Point
from tools import generate_kc2_magnetic_housings as base
from tools.generate_kc2_filled_plates import build_plan
from tools.verify_kc2_filled_plate_contract import contract_plan,check_record


def record_for(p):
    return dict(side=p['side'],kind=p['kind'],profile=asdict(p['profile']),
        switch_count=p['switch_count'],mounting_centers=p['mounting_centers'],
        plan_wkt={k:p[k].wkt for k in ['domain','body','openings','service','bores','pockets','bosses','lands']},
        masks_wkt=[g.wkt for g in p['masks']],parts=[dict(index=i,layers=[dict(z0=r.z0,z1=r.z1,wkt=r.geometry.wkt) for r in rows]) for i,rows in enumerate(p['parts'])])


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.boards,_,_=base.load_plans()
        cls.plans={(s,k):build_plan(s,b,k) for s,b in cls.boards.items() for k in ['mx','choc_v1','deep_sea']}
        cls.expected={(s,k):contract_plan(s,b,k) for s,b in cls.boards.items() for k in ['mx','choc_v1','deep_sea']}

    def test_all_six_match_independent_numeric_and_section_contract(self):
        for key,p in self.plans.items():
            with self.subTest(key=key):self.assertEqual(check_record(record_for(p),self.expected[key]),[])

    def test_wrong_switch_profile_rejected(self):
        r=record_for(self.plans['left','deep_sea']);r['profile']['plate_top']=6.5
        self.assertIn('profile mismatch',check_record(r,self.expected['left','deep_sea']))

    def test_missing_screw_rejected_even_when_declared_valid(self):
        r=record_for(self.plans['left','mx']);r['plan_wkt']['bores']='POLYGON EMPTY'
        self.assertIn('bores mismatch',check_record(r,self.expected['left','mx']))

    def test_hollow_interior_and_filled_bore_rejected(self):
        p=self.plans['left','mx'];expected=self.expected['left','mx']
        for mutation in ['hollow','filled_bore']:
            r=record_for(p)
            row=p['parts'][0][1]
            altered=row.geometry.buffer(-.3) if mutation=='hollow' else row.geometry.union(p['bores'])
            r['parts'][0]['layers'][1]['wkt']=altered.wkt
            self.assertIn('part 0 fill mismatch',check_record(r,expected))

    def test_arbitrary_part_mask_cannot_excuse_missing_material(self):
        r=record_for(self.plans['right','choc_v1']);r['masks_wkt'][0]='POLYGON EMPTY'
        self.assertIn('part 0 mask mismatch',check_record(r,self.expected['right','choc_v1']))

    def test_wrong_z_and_mount_count_rejected(self):
        r=record_for(self.plans['left','choc_v1'])
        r['parts'][0]['layers'][0]['z0']=4.2;r['mounting_centers'].pop()
        errors=check_record(r,self.expected['left','choc_v1'])
        self.assertIn('mounting centers mismatch',errors)
        self.assertIn('part 0 fill mismatch',errors)


if __name__=='__main__':unittest.main()
