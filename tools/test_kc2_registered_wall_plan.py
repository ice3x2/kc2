"""CON-ARCH-006 open exterior rebates preserve robust walls and PCB spacing."""
import unittest
from shapely.geometry import box, GeometryCollection
from tools.kc2_registered_wall_plan import plan_registrars


class RegisteredWallPlanTests(unittest.TestCase):
    def args(self,side='left',kind='deep_sea'):
        x0,x1=(18.4,60.9) if side=='left' else (97.7875,140.2875)
        return dict(side=side,kind=kind,board=box(x0,0,x1,28.25),
                    lower_floor=box(x0+.1,.1,x1-.1,28.15),
                    upper_solid=box(x0+.1,.1,x1-.1,28.15),
                    lower_protected=GeometryCollection(),upper_protected=GeometryCollection(),
                    central_exclusion=GeometryCollection(),split_exclusion=GeometryCollection())

    def test_CON_ARCH_006_three_actual_candidates_and_full_dimensions(self):
        for side in ['left','right']:
            p=plan_registrars(**self.args(side))
            self.assertEqual(len(p),3)
            for r in p.values():
                self.assertAlmostEqual(r.wall.area,7.2)
                self.assertGreaterEqual(r.wall.distance(self.args(side)['board']),.3-1e-8)
                self.assertEqual((r.wall_z,r.upper_z,r.groove_z),((-1.,5.),(4.4,6.25),(4.4,5.2)))
                self.assertAlmostEqual(r.roof_thickness,1.05)
                self.assertAlmostEqual(r.addition.difference(self.args(side)['upper_solid']).area,14.24)

    def test_CON_ARCH_006_rebate_open_outside_closed_inside_and_ends(self):
        r=plan_registrars(**self.args())['top_a']
        self.assertEqual(r.wall.bounds,(30.,-1.5,36.,-.3))
        self.assertEqual(r.addition.bounds,(28.55,-1.5,37.45,1.15))
        self.assertTrue(r.groove.covers(box(30,-1.6,36,-1.4)))
        self.assertAlmostEqual(r.addition.bounds[3]-r.groove.bounds[3],1.2)
        self.assertAlmostEqual(r.groove.bounds[0]-r.addition.bounds[0],1.2)

    def test_CON_ARCH_006_each_profile_preserves_roof(self):
        for kind,top in [('mx',9.3),('choc_v1',6.5),('deep_sea',6.25)]:
            self.assertEqual(plan_registrars(**self.args(kind=kind))['top_a'].upper_z,(4.4,top))

    def test_CON_ARCH_006_reject_pcb_collision(self):
        a=self.args();a['board']=a['board'].buffer(.1)
        with self.assertRaisesRegex(ValueError,'PCB'):plan_registrars(**a)

    def test_CON_ARCH_006_reject_protected_and_exclusion_collisions(self):
        for name in ['lower_protected','upper_protected','central_exclusion','split_exclusion']:
            a=self.args();a[name]=box(30,-1.4,31,-.4)
            with self.subTest(name=name),self.assertRaises(ValueError):plan_registrars(**a)

    def test_CON_ARCH_006_floor_and_upper_must_have_area_attachment(self):
        for name in ['lower_floor','upper_solid']:
            a=self.args();a[name]=box(0,40,20,60)
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'attachment'):plan_registrars(**a)

    def test_CON_ARCH_006_reject_unknown_identity_and_invalid_inputs(self):
        for name,value in [('side','middle'),('kind','choc_v2'),('board',GeometryCollection())]:
            a=self.args();a[name]=value
            with self.subTest(name=name),self.assertRaises(ValueError):plan_registrars(**a)

    def test_CON_ARCH_006_actual_PCB_and_six_source_profiles(self):
        import json
        from pathlib import Path
        from shapely import wkt
        from shapely.ops import unary_union
        from tools import generate_kc2_magnetic_housings as magnetic
        plans,_,_=magnetic.load_plans()
        root=Path(__file__).resolve().parents[1]
        for side,p in plans.items():
            for kind in ['mx','choc_v1','deep_sea']:
                d=json.loads((root/f'docs/reports/solid-filled-plates-20260913/{side}-{kind}.json').read_text())
                gs={k:wkt.loads(v) for k,v in d['plan_wkt'].items()}
                common=None
                for z in [4.5,5.0,5.15,5.8,6.2]:
                    section=unary_union([wkt.loads(row['wkt']) for part in d['parts'] for row in part['layers'] if row['z0']<=z<row['z1']])
                    common=section if common is None else common.intersection(section)
                result=plan_registrars(side=side,kind=kind,board=p['board'],
                    lower_floor=p['housing_outline'],upper_solid=common,
                    lower_protected=p['all_component_cutouts'],
                    upper_protected=unary_union([gs[k] for k in ['body','openings','service','bores','pockets','bosses']]),
                    central_exclusion=box(-10,28,20,140) if side=='left' else box(145,28,175,140),
                    split_exclusion=GeometryCollection())
                with self.subTest(side=side,kind=kind):
                    self.assertEqual(len(result),3)
                    self.assertEqual(result['outer'].outward,'-x' if side=='left' else '+x')
                    self.assertLess(sum(r.addition.difference(gs['domain']).area for r in result.values()),42.721)


if __name__=='__main__':unittest.main()
