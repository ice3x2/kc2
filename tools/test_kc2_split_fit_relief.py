"""CON-ARCH-006: local A/B print-fit relief, not central keyboard fit."""
import unittest
import json
from pathlib import Path

from shapely import wkt
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from tools.kc2_split_fit_relief import RequiredRoot, plan_split_relief


class SplitFitReliefTests(unittest.TestCase):
    def setUp(self):
        self.a = box(0, 0, 10, 10)
        self.b = box(10.2, 0, 20.2, 10)

    def test_nominal_gap_and_no_global_erosion(self):
        plan = plan_split_relief(self.a, self.b)
        self.assertGreaterEqual(plan.core.part_a.distance(plan.core.part_b), .4 - 1e-8)
        self.assertAlmostEqual(plan.core.part_a.bounds[2], 9.9, places=4)
        self.assertAlmostEqual(plan.core.part_b.bounds[0], 10.3, places=4)
        self.assertTrue(plan.core.part_a.covers(box(0, 0, 9.8, 10)))
        self.assertTrue(plan.core.part_b.covers(box(10.4, 0, 20.2, 10)))
        for original, trimmed, cutter in ((self.a, plan.core.part_a, plan.core.cutter_a),
                                           (self.b, plan.core.part_b, plan.core.cutter_b)):
            self.assertTrue(original.covers(trimmed))
            self.assertLess(original.difference(cutter).symmetric_difference(trimmed).area, 1e-9)

    def test_entry_bands_larger_and_nested(self):
        plan = plan_split_relief(self.a, self.b, z_min=-2.2, z_max=2.5)
        self.assertGreaterEqual(plan.entry.part_a.distance(plan.entry.part_b), .6 - 1e-8)
        self.assertTrue(plan.core.part_a.covers(plan.entry.part_a))
        self.assertTrue(plan.core.part_b.covers(plan.entry.part_b))
        self.assertIs(plan.at_z(-2.1), plan.entry)
        self.assertIs(plan.at_z(2.4), plan.entry)
        self.assertIs(plan.at_z(0), plan.core)
        with self.assertRaises(ValueError):
            plan.at_z(99)

    def test_protected_core_or_entry_cut_fails_closed(self):
        for protected in (box(9.95, 4, 10, 6), box(9.85, 4, 9.9, 6)):
            with self.subTest(protected=protected.wkt), self.assertRaisesRegex(ValueError, 'protected'):
                plan_split_relief(self.a, self.b, protected_a=protected)
        with self.assertRaisesRegex(ValueError, 'protected'):
            plan_split_relief(self.a, self.b, protected_b=box(10.2, 4, 10.3, 6))

    def test_far_geometry_unchanged(self):
        b = box(12, 0, 20, 10)
        p = plan_split_relief(self.a, b)
        self.assertTrue(p.entry.part_a.equals(self.a))
        self.assertTrue(p.entry.part_b.equals(b))
        self.assertTrue(p.core.cutter_a.is_empty)

    def test_numeric_inputs_fail_closed(self):
        for field in ('target_gap', 'entry_extra', 'entry_height', 'z_min', 'z_max'):
            for bad in (float('nan'), float('inf'), 'x', True):
                with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                    plan_split_relief(self.a, self.b, **{field: bad})
        for kw in ({'target_gap': 0}, {'entry_extra': -.1}, {'entry_height': -.1},
                   {'z_min': 3}, {'z_max': .5}, {'entry_height': 0}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                plan_split_relief(self.a, self.b, **kw)

    def test_invalid_overlap_or_disconnected_input_rejected(self):
        for bad in (Polygon(), box(5, 0, 15, 10),
                    unary_union([box(12, 0, 13, 1), box(12, 3, 13, 4)])):
            with self.assertRaises(ValueError):
                plan_split_relief(self.a, bad)

    def test_relief_cannot_sever_neck(self):
        a = unary_union([box(0, 0, 2, 2), box(4, 0, 6, 2), box(2, .9, 4, 1.1)])
        b = box(2.5, 1.3, 3.5, 3)
        with self.assertRaisesRegex(ValueError, 'connected'):
            plan_split_relief(a, b, target_gap=.8, entry_extra=0)

    def test_corner_and_captive_shape_clearance(self):
        a = unary_union([box(0, 0, 8, 10), box(8, 3, 10, 7)])
        b = box(8.2, 0, 15, 10).difference(box(8, 2.8, 10.2, 7.2))
        plan = plan_split_relief(a, b)
        for section in (plan.core, plan.entry):
            self.assertGreaterEqual(section.part_a.distance(section.part_b), section.target_gap - 1e-8)
            self.assertEqual(section.part_a.geom_type, 'Polygon')
            self.assertEqual(section.part_b.geom_type, 'Polygon')

    def test_retained_actual_mask_high_vertex_clearance(self):
        path = Path(__file__).resolve().parents[1] / 'docs/reports/solid-filled-plates-20260913/right-mx.json'
        record = json.loads(path.read_text())
        domain = wkt.loads(record['plan_wkt']['domain'])
        a, b = (wkt.loads(value).intersection(domain) for value in record['masks_wkt'])
        root = RequiredRoot('retained MH8 contact land', Point(76, 111.75).buffer(1.5))
        plan = plan_split_relief(a, b, required_roots_b=(root,))
        self.assertGreaterEqual(plan.core.part_a.distance(plan.core.part_b), .4 - 1e-8)
        self.assertGreaterEqual(plan.entry.part_a.distance(plan.entry.part_b), .6 - 1e-8)

    def test_connected_but_thinned_root_is_not_accepted_as_strength(self):
        a = unary_union([box(0, 0, 2, 2), box(4, 0, 6, 2), box(2, .9, 4, 1.3)])
        b = box(2.5, 1.5, 3.5, 3)
        root = RequiredRoot('minimum .30 mm neck', box(1.9, .9, 4.1, 1.2))
        with self.assertRaisesRegex(ValueError, 'minimum .30 mm neck'):
            plan_split_relief(a, b, target_gap=.5, entry_extra=0, required_roots_a=(root,))

    def test_required_root_must_exist_in_original_and_remain(self):
        for root in (RequiredRoot('outside', box(-1, 1, 1, 2)),
                     RequiredRoot('empty', Polygon()), RequiredRoot('', box(1, 1, 2, 2))):
            with self.subTest(root=root), self.assertRaises(ValueError):
                plan_split_relief(self.a, self.b, required_roots_a=(root,))
        root = RequiredRoot('safe neck', box(1, 1, 2, 2))
        result = plan_split_relief(self.a, self.b, required_roots_a=(root,))
        self.assertTrue(result.entry.part_a.covers(root.region))


if __name__ == '__main__':
    unittest.main()
