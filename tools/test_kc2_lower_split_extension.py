"""CON-ARCH-006 lower A/B extension preserves old keys and widens local gap."""
import unittest
from shapely.geometry import box
from tools.kc2_lower_split_extension import extend_relieve,retained_key_relief
from shapely.geometry import Point,LineString
class LowerSplitExtension(unittest.TestCase):
    def test_new_floor_extension_clear_and_connected(self):
        a,b=box(0,0,4.9,10),box(5.1,0,10,10)
        p=extend_relieve(a,b,box(-1,-1,11,11),5)
        self.assertGreaterEqual(p.core.part_a.distance(p.core.part_b),.39999)
        self.assertEqual(p.core.part_a.geom_type,'Polygon')
        self.assertTrue(p.core.part_a.covers(box(0,0,4,10)))
    def test_reject_split_outside_old_gap(self):
        with self.assertRaises(ValueError):extend_relieve(box(0,0,4.9,10),box(5.1,0,10,10),box(-1,-1,11,11),50)
    def test_full_head_and_two_mm_root_survive_relief(self):
        key=box(4.9,9,8,11).union(Point(8,10).buffer(2.25,quad_segs=24))
        a=box(0,0,4.9,20).union(key);b=box(5.1,0,15,20).difference(key.buffer(.2))
        aa,bb=retained_key_relief(a,b,box(0,0,15,20),5,[10])
        self.assertGreaterEqual(aa.distance(bb),.39999)
        self.assertTrue(aa.buffer(1e-8).covers(Point(8,10).buffer(2.25,quad_segs=24)))
        neck=aa.intersection(LineString([(5.1,8),(5.1,12)]))
        self.assertAlmostEqual(neck.length,2.0,places=5)
    def test_actual_lower_two_captures_and_roots(self):
        import json
        from pathlib import Path
        from shapely import wkt,affinity
        root=Path(__file__).resolve().parents[1]
        record=json.loads((root/'docs/reports/reinforced-covers-20260913/right-lower.json').read_text())
        a,b=[wkt.loads(v) for v in record['masks_wkt']]
        bounds=wkt.loads(record['outline_wkt']).bounds;seam=(bounds[0]+bounds[2])/2
        ys=sorted(round(g.centroid.y,8) for g in a.difference(box(-100,-100,seam-.1,300)).geoms)
        self.assertEqual(ys,[73.25,86.25])
        aa,bb=retained_key_relief(a,b,wkt.loads(record['new_outline_wkt']),seam,ys)
        for y in ys:
            self.assertAlmostEqual(aa.intersection(LineString([(seam+.1,y-2),(seam+.1,y+2)])).length,2.,places=6)
            self.assertTrue(aa.buffer(1e-7).covers(Point(seam+3,y).buffer(2.25,quad_segs=24)))
        for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
            self.assertGreater(affinity.translate(aa,xoff=dx,yoff=dy).intersection(bb).area,1e-6)
    def test_actual_capture_local_supports_survive_receiver_relief(self):
        import json
        from pathlib import Path
        from shapely import wkt
        from shapely.ops import unary_union
        from tools import generate_kc2_magnetic_housings as magnetic
        from tools import generate_kc2_x3_v2_housings as base
        root=Path(__file__).resolve().parents[1]
        record=json.loads((root/'docs/reports/reinforced-covers-20260913/right-lower.json').read_text())
        a,b=[wkt.loads(v) for v in record['masks_wkt']]
        bounds=wkt.loads(record['outline_wkt']).bounds;seam=(bounds[0]+bounds[2])/2
        ys=[73.25,86.25]
        aa,bb=retained_key_relief(a,b,wkt.loads(record['new_outline_wkt']),seam,ys)
        plans,_,_=magnetic.load_plans();p=plans['right'];shp=base.legacy_geometry.require_shapely()
        supports=base._support_plan_union(shp,p['support_posts']).union(p['rail']).union(p['mounting_land_geometry']).union(p['reset_local_support_geometry'])
        local=unary_union([Point(seam+3,y).buffer(3.0) for y in ys])
        self.assertLess(b.difference(bb).intersection(local).intersection(supports).area,1e-8)
if __name__=='__main__':unittest.main()
