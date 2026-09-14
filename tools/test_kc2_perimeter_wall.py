"""CON-ARCH-006 perimeter additions preserve PCB clearance and omission scope."""
import unittest
from shapely.geometry import box,GeometryCollection
from tools.kc2_perimeter_wall import perimeter_plan,APPROVED_WORLD_OMISSIONS


class PerimeterWallTests(unittest.TestCase):
    def args(self):
        return dict(board=box(0,0,20,20),lower_protected=GeometryCollection(),
                    mx_body=GeometryCollection(),service=GeometryCollection(),
                    floor=box(.1,.1,19.9,19.9),world_omissions=GeometryCollection(),
                    raw_bounds=(0,0,20,20),side='left')

    def test_CON_ARCH_006_full_wrap_nominal_width_and_height(self):
        a=self.args();p=perimeter_plan(**a)
        self.assertEqual(p.wall.bounds,(-1.5,-1.5,21.5,21.5))
        self.assertEqual(p.bands,((-1.,2.5),(2.5,4.10)))
        self.assertAlmostEqual(p.wall.distance(a['board']),.3)
        self.assertTrue(p.floor_addition.covers(p.wall))
        self.assertGreater(p.floor_addition.intersection(a['floor']).area,0)

    def test_CON_ARCH_006_bottom_and_MX_protection_cannot_be_filled(self):
        a=self.args();a['lower_protected']=box(19,8,21,12);a['mx_body']=box(19,14,21.2,17)
        p=perimeter_plan(**a)
        for k in ['board','lower_protected','mx_body']:self.assertLess(p.wall.intersection(a[k]).area,1e-8)

    def test_CON_ARCH_006_service_cut_is_explicit(self):
        a=self.args();a['service']=box(8,-4,12,2);p=perimeter_plan(**a)
        self.assertLess(p.wall.intersection(a['service']).area,1e-8)
        self.assertGreater(p.service_removed.area,0)

    def test_CON_ARCH_006_no_unapproved_omission(self):
        a=self.args();a['world_omissions']=box(0,0,1,1)
        with self.assertRaisesRegex(ValueError,'approved'):perimeter_plan(**a)

    def test_CON_ARCH_006_inputs_fail_closed(self):
        for k,v in [('side','middle'),('board',GeometryCollection()),('floor',box(30,30,40,40))]:
            a=self.args();a[k]=v
            with self.subTest(k=k),self.assertRaises(ValueError):perimeter_plan(**a)

    def test_CON_ARCH_006_three_bounded_rounded_omissions_only(self):
        self.assertEqual(len(APPROVED_WORLD_OMISSIONS.geoms),3)
        self.assertLess(APPROVED_WORLD_OMISSIONS.area,170)

    def test_CON_ARCH_006_actual_joined_perimeter_existing_enclosures(self):
        import json
        from pathlib import Path
        from shapely import wkt
        from tools.kc2_perimeter_wall import to_world
        from tools import generate_kc2_magnetic_housings as magnetic
        plans,_,_=magnetic.load_plans();root=Path(__file__).resolve().parents[1]
        result={};existing={};combined_floor={}
        for side,p in plans.items():
            old=json.loads((root/f'docs/reports/reinforced-covers-20260913/{side}-lower.json').read_text())
            floor=wkt.loads(old['new_outline_wkt'])
            d=json.loads((root/f'docs/reports/solid-filled-plates-20260913/{side}-mx.json').read_text())
            q=perimeter_plan(board=p['board'],lower_protected=p['all_component_cutouts'],
                mx_body=wkt.loads(d['plan_wkt']['body']),service=wkt.loads(d['plan_wkt']['service']),
                floor=floor,world_omissions=APPROVED_WORLD_OMISSIONS,raw_bounds=p['raw_bounds'],side=side)
            result[side]=to_world(q.wall,p['raw_bounds'],side)
            combined_floor[side]=to_world(q.wall.union(q.floor_addition).union(floor),p['raw_bounds'],side)
            self.assertLess(q.wall.intersection(p['board'].buffer(.3,join_style=2)).area,1e-8)
            self.assertLess(q.wall.intersection(p['all_component_cutouts']).area,1e-8)
            self.assertLess(q.wall.intersection(wkt.loads(d['plan_wkt']['body'])).area,1e-8)
            existing[side]={'lower':to_world(floor,p['raw_bounds'],side)}
            for kind in ['mx','choc_v1','deep_sea']:
                d=json.loads((root/f'docs/reports/solid-filled-plates-20260913/{side}-{kind}.json').read_text())
                existing[side][kind]=to_world(wkt.loads(d['plan_wkt']['domain']),p['raw_bounds'],side)
        self.assertGreaterEqual(result['left'].distance(result['right']),.3-1e-8)
        self.assertGreaterEqual(combined_floor['left'].distance(combined_floor['right']),.3-1e-8)
        for side,other in [('left','right'),('right','left')]:
            for kind,g in existing[other].items():
                with self.subTest(side=side,opposite=kind):
                    self.assertGreaterEqual(result[side].distance(g),.3-1e-8)


if __name__=='__main__':unittest.main()
