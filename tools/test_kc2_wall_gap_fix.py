"""CON-ARCH-006 regression: bridge only same-part nonfunctional wall slits."""
import json
import unittest
from pathlib import Path
from shapely import wkt
from shapely.geometry import box, Point, GeometryCollection
from shapely.ops import unary_union
from tools.kc2_wall_gap_fix import bridge_slots

ROOT=Path(__file__).resolve().parents[1]

class WallGapTests(unittest.TestCase):
    def test_long_slot_is_continuously_joined(self):
        for width in (.2,.4):
            stock=box(0,0,5,20).union(box(5+width,0,6.5,20))
            patches=bridge_slots(stock,box(0,0,6.5,20),GeometryCollection())
            self.assertLess(box(4.99,1,5+width+.01,19).difference(stock.union(patches)).area,1e-8)

    def test_functional_rebate_is_not_filled(self):
        stock=box(0,0,5,20).union(box(5.2,0,6.5,20))
        protected=box(4.9,5,5.3,9)
        patch=bridge_slots(stock,box(0,0,6.5,20),protected)
        self.assertLess(patch.intersection(protected).area,1e-9)

    def test_preserves_outline_and_large_openings(self):
        domain=box(0,0,20,20)
        stock=domain.difference(box(3,3,17,17)).difference(box(1,4,1.2,16))
        patch=bridge_slots(stock,domain,box(3,3,17,17))
        self.assertLess(patch.difference(domain).area,1e-9)
        self.assertLess(patch.intersection(box(3,3,17,17)).area,1e-9)

    def test_caps_slot_from_actual_published_recipe(self):
        plan=json.loads((ROOT/'docs/reports/wrap-housings-20260920/plan.json').read_text())['sides']['left']
        old=json.loads((ROOT/'docs/reports/registered-housing-fit-20260913/evidence/upper/left-mx/generation.json').read_text())
        stock=wkt.loads(old['parts'][0]['layers'][2]['wkt']).union(wkt.loads(plan['upper_rim_parts_wkt']['mx'][0]))
        gap=box(135.03,69,135.19,84)
        self.assertGreater(gap.difference(stock).area,2)
        domain=wkt.loads(plan['domain_wkt'])
        allowed=domain.difference(domain.buffer(-3,join_style=2)).difference(wkt.loads(plan['central_wkt'])).difference(wkt.loads(plan['service_wkt']))
        patch=bridge_slots(stock,allowed,GeometryCollection())
        self.assertLess(gap.difference(stock.union(patch)).area,1e-7)

    def test_disallowed_interpart_gap_is_preserved(self):
        stock=box(0,0,5,20).union(box(5.4,0,7,20))
        allowed=box(0,0,5,20)
        patch=bridge_slots(stock,allowed,GeometryCollection())
        self.assertLess(patch.intersection(box(5,0,5.4,20)).area,1e-9)

if __name__=='__main__':unittest.main()
