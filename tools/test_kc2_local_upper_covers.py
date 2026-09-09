"""CON-ARCH-006: local MX covers do not redesign the support stack."""
import unittest
import tempfile
from pathlib import Path
from shapely.geometry import box, GeometryCollection
from shapely.ops import unary_union
from tools import kc2_local_upper_covers as c


class LocalUpperTests(unittest.TestCase):
    def test_partition_clearance_rejects_new_contact_or_worse_gap(self):
        parts=[box(0,0,9.9,10),box(10.1,0,20,10)]
        good=[(box(0,0,9.9,1),box(0,0,9.9,1)),(box(10.1,0,20,1),box(10.1,0,20,1))]
        self.assertEqual(c.partition_clearance_errors(parts,good),[])
        bad=[(box(0,0,10.1,1),good[0][1]),good[1]]
        self.assertTrue(c.partition_clearance_errors(parts,bad))

    def test_actual_both_halves_cover_every_required_corner_except_split(self):
        from tools import generate_kc2_magnetic_housings as m
        from tools import generate_kc2_mx_upper_housings as u
        plans, _, _ = m.load_plans()
        for side, plan in plans.items():
            cover = c.cover_plan(plan)
            parts = [cover['upper']['plate']] if side=='left' else u.split_upper_plan(
                u.lower.legacy_geometry.require_shapely(),plan,cover['upper'])[0]
            partition = c.partition_covers(cover,parts)
            self.assertEqual(c.partition_clearance_errors(parts,partition),[])
            for n, key in enumerate(['skirt','roof']):
                declared = [row[n] for row in partition]
                seam = unary_union([a.buffer(.201).intersection(b.buffer(.201))
                    for i,a in enumerate(declared) for b in declared[i+1:]])
                # Exact existing keyed-plate void is retained, not filled by a
                # floating skirt. No buffered/general missing-area allowance.
                original_gap = cover['upper']['plate'].difference(unary_union(parts))
                missing = cover[key].difference(unary_union(declared)).difference(seam.union(original_gap))
                with self.subTest(side=side,kind=key):
                    self.assertLess(missing.area,.001)

    def test_step_normalization_keeps_content_and_removes_line_padding(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'part.step'
            p.write_bytes(b'ISO-10303-21; \r\nENDSEC;\t\n')
            c.normalize_step(p)
            self.assertEqual(p.read_bytes(), b'ISO-10303-21;\r\nENDSEC;\n')

    def test_cover_partition_keeps_each_skirt_under_its_own_roof(self):
        cover = dict(skirt=box(0, 0, 20, 1), roof=box(0, -1, 20, 0))
        parts = [box(0, 0, 9.9, 10), box(10.1, 0, 20, 10)]
        pieces = c.partition_covers(cover, parts)
        for part, (skirt, roof) in zip(parts, pieces):
            self.assertLess(skirt.difference(part.union(roof)).area, 1e-9)
        self.assertLess(pieces[0][0].intersection(pieces[1][0]).area, 1e-9)

    def test_both_boards_and_join_renderer_bound_before_and_after(self):
        sources = c.generation_sources('left')
        self.assertIn('tools/render_kc2_x3_joined.py', sources)
        self.assertTrue(any('kc2_left.kicad_pcb' in p for p in sources))
        self.assertTrue(any('kc2_right.kicad_pcb' in p for p in sources))

    def fixture(self):
        return box(0, 0, 30, 30), box(-.2, 10, 15.4, 25.6), GeometryCollection()

    def test_body_clearance_and_local_roof_attachment(self):
        outline, body, service = self.fixture()
        r = c.cover_geometry(outline, body, service)
        self.assertGreaterEqual(r['skirt'].distance(body), .3)
        self.assertLess(r['roof'].intersection(body).area, 1e-9)
        self.assertLess(r['skirt'].difference(outline.union(r['roof'])).area, 1e-8)
        self.assertEqual(c.SKIRT_BOTTOM, 4.4)
        self.assertEqual(c.PLATE_BOTTOM, 7.8)
        self.assertEqual(c.PLATE_TOP, 9.3)

    def test_service_and_locality_are_not_filled(self):
        outline, body, _ = self.fixture()
        service = box(-5, 18, 5, 22)
        locality = box(-5, 5, 5, 30)
        r = c.cover_geometry(outline, body, service, locality)
        for key in ['skirt', 'roof']:
            self.assertLess(r[key].intersection(service).area, 1e-9)
            self.assertLess(r[key].difference(locality).area, 1e-9)

    def test_no_global_growth_away_from_switch_bulge(self):
        outline, body, service = self.fixture()
        r = c.cover_geometry(outline, body, service)
        self.assertLess(r['roof'].difference(body.buffer(.703)).area, 1e-8)
        self.assertLess(r['roof'].intersection(box(29, 0, 35, 30)).area, 1e-9)


if __name__ == '__main__':
    unittest.main()
