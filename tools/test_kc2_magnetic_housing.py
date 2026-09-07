"""CON-ARCH-006 / OPS-ARCH-006: subtractive optional magnet pockets."""
import math
import ast
import unittest
from pathlib import Path

import cadquery as cq
from shapely.geometry import box
from tools import generate_kc2_magnetic_housings as m


class MagneticContract(unittest.TestCase):
    def test_native_export_only_magnetic_lower(self):
        source = Path('tools/fusion/KC2MagneticToF3D/KC2MagneticToF3D.py')
        tree = ast.parse(source.read_text(encoding='utf8'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'export_jobs')
        namespace = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        jobs = namespace['export_jobs'](Path('hardware/MODELS'))
        self.assertEqual(set(jobs), {'left', 'right'})
        for side, path in jobs.items():
            self.assertEqual(path.name, f'kc2_{side}_lower_housing_magnetic.step')

    def test_variant_names_preserve_originals(self):
        for name in ['kc2_left_lower_housing.step', 'kc2_right_lower_housing_part_b.stl']:
            self.assertEqual(m.variant_path(Path(name)).stem, Path(name).stem + '_magnetic')
        with self.assertRaises(ValueError):
            m.variant_path(Path('already_magnetic.step'))

    def test_dimensions_and_rims(self):
        self.assertEqual((m.DIAMETER, m.DEPTH), (2.4, 1.2))
        self.assertGreater(m.DIAMETER, 2.0)
        self.assertGreater(m.DEPTH, 1.0)
        self.assertGreaterEqual(m.CENTER_Z - m.DIAMETER / 2 + 1, .5)
        self.assertGreaterEqual(2.5 - m.CENTER_Z - m.DIAMETER / 2, .5)
        self.assertGreaterEqual(m.BACK_WALL, .6)

    def test_correct_axis_and_removed_volume(self):
        for sign, face_x in [(1, 0), (-1, 5)]:
            before = cq.Solid.makeBox(5, 10, 4.7, cq.Vector(0, 0, -2.2))
            after = before.cut(m.pocket_cutter(face_x, 5, sign))
            self.assertAlmostEqual(before.Volume() - after.Volume(), math.pi * 1.2**2 * 1.2, places=5)
            self.assertTrue(after.isValid())
            self.assertEqual(len(after.Solids()), 1)
            for z in [-1.5, 2.3]:
                self.assertTrue(after.isInside(cq.Vector(face_x + sign * .1, 5, z)))
            self.assertFalse(after.isInside(cq.Vector(face_x + sign * .6, 5, .75)))
            self.assertTrue(after.isInside(cq.Vector(face_x + sign * 1.3, 5, .75)))

    def test_reject_invalid_axes(self):
        for sign in [0, 2, -2]:
            with self.assertRaises(ValueError):
                m.pocket_cutter(0, 5, sign)

    def test_clearance_rejects_thin_wall_and_support(self):
        clear = box(0, 0, 5, 10)
        empty = box(20, 20, 21, 21)
        self.assertTrue(m.safe_pocket(clear, empty, 0, 5, 1))
        self.assertFalse(m.safe_pocket(box(0, 0, 1.5, 10), empty, 0, 5, 1))
        self.assertFalse(m.safe_pocket(clear, box(.4, 4, .8, 6), 0, 5, 1))
        self.assertFalse(m.safe_pocket(clear, empty, 0, .5, 1))

    def test_pair_selection_and_fallback(self):
        points = [{'y': y, 'gap': 4.0} for y in [104, 107, 110]]
        self.assertEqual([v['y'] for v in m.choose_pairs(points)], [104, 110])
        self.assertEqual(len(m.choose_pairs(points[:1])), 1)
        self.assertEqual(m.choose_pairs([]), [])
        self.assertEqual(len(m.choose_pairs(points[:2])), 1)
        self.assertEqual([v['y'] for v in m.choose_pairs(points + [{'y': 10, 'gap': 31.5}])], [104, 110])

    def test_cad_audit_rejects_added_material_or_wrong_bore(self):
        before = cq.Solid.makeBox(5, 10, 4.7, cq.Vector(0, 0, -2.2))
        pockets = [{'x': 0, 'y': 5, 'sign': 1}]
        after = before.cut(m.pocket_cutter(0, 5, 1))
        self.assertEqual(m.audit_delta(before, after, pockets)['errors'], [])
        self.assertTrue(m.audit_delta(before, before, pockets)['errors'])
        added = after.fuse(cq.Solid.makeBox(1, 1, 1, cq.Vector(-1, 0, 0)))
        self.assertTrue(m.audit_delta(before, added, pockets)['errors'])
        wrong = before.cut(m.pocket_cutter(0, 7, 1))
        self.assertTrue(m.audit_delta(before, wrong, pockets)['errors'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
