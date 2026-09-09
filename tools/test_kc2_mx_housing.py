"""CON-ARCH-006: selected socket and real oval-pad housing envelopes."""
import math
import json
import unittest
import tempfile
from pathlib import Path

from tools import generate_kc2_x3_v2_housings as housing
from tools.historical_housing_test_fixture import historical_json


class MXHousingTests(unittest.TestCase):
    def test_verifier_accepts_improved_span_but_rejects_worse_span(self):
        from tools.verify_kc2_x3_v2_housing import verify_report
        # Historical validator mutation fixture, not current local-cover CAD evidence.
        report = historical_json('kc2_housing_clearance.json')
        for value, rejected in ((3.899, False), (4.41, True), (-1, True), (math.nan, True)):
            report['sides']['left']['maximum_load_point_to_support_mm'] = value
            errors = verify_report(report)
            span_errors = [e for e in errors if 'left: primary-support load span' in e]
            self.assertEqual(bool(span_errors), rejected)

    def test_upper_stack_requires_explicit_switch_datums(self):
        from tools.generate_kc2_mx_upper_housings import stack_parameters
        with self.assertRaises(ValueError):
            stack_parameters(plate_top_above_pcb_mm=1.0, clip_thickness_mm=1.5,
                             aperture_mm=14.0)
        stack = stack_parameters(plate_top_above_pcb_mm=5.2, clip_thickness_mm=1.5,
                                 aperture_mm=14.0)
        self.assertAlmostEqual(stack['plate_top_z_mm'], 9.3)
        self.assertAlmostEqual(stack['standoff_height_mm'], 3.7)
        self.assertIsNone(stack['qualified_long_screw_length_mm'])
        self.assertFalse(stack['order_ready'])

    def test_revised_actual_boards_keep_all_key_supports_without_worsening_span(self):
        shp = housing.legacy_geometry.require_shapely()
        from tools.generate_kc2_mx_upper_housings import snapshot_board_geometry
        with tempfile.TemporaryDirectory(dir=housing.ROOT/'.codex-tmp') as directory:
            extracted, _ = snapshot_board_geometry(Path(directory),Path('C:/Program Files/KiCad/10.0/bin/python.exe'))
        boards = extracted['boards']
        for side, data in boards.items():
            plan = housing.build_plan_geometry(shp, side, data)
            from tools.generate_kc2_mx_upper_housings import upper_plan, stack_parameters
            upper = upper_plan(shp, plan, stack_parameters(
                plate_top_above_pcb_mm=5.2, clip_thickness_mm=1.5, aperture_mm=14))
            self.assertTrue(upper['plate'].is_valid)
            self.assertEqual(upper['plate'].geom_type, 'Polygon')
            self.assertAlmostEqual(upper['plate'].intersection(upper['openings']).area, 0)
            self.assertTrue(upper['plate'].covers(upper['lands']))
            if side == 'right':
                from tools.generate_kc2_mx_upper_housings import split_upper_plan
                pieces, joint = split_upper_plan(shp, plan, upper)
                self.assertEqual(len(pieces), 2)
                self.assertEqual(joint['capture_count'], 2)
                self.assertTrue(all(v>0 for v in joint['one_mm_in_plane_motion_collision_area_mm2'].values()))
                self.assertTrue(all(p.geom_type=='Polygon' and p.is_valid for p in pieces))
                for collar in upper['collars'].geoms:
                    self.assertTrue(any(p.buffer(1e-6).covers(collar) for p in pieces))
                self.assertAlmostEqual(pieces[0].intersection(pieces[1]).area, 0)
                self.assertTrue(all(max(p.bounds[2]-p.bounds[0],p.bounds[3]-p.bounds[1])<=150 for p in pieces))
            parts = [plan['support_surface']]
            if side == 'right':
                split = housing.build_right_split_plan(shp, plan)
                self.assertEqual(len(split['capture_points']),2)
                self.assertAlmostEqual(split['capture_points'][0]['y_mm']+plan['raw_bounds'][1],112.5,places=3)
                self.assertFalse(split['slot_union'].intersects(plan['all_component_cutouts']))
                self.assertFalse(split['slot_union'].intersects(
                    housing._support_plan_union(shp,plan['support_posts'])))
                self.assertFalse(split['slot_union'].intersects(plan['mounting_land_geometry']))
                parts = [split['part_a_plan'], split['part_b_plan']]
            result = housing.mounting_system_manifest(shp, side, plan, parts)
            self.assertTrue(result['primary_support_load_span_unchanged'])
            self.assertEqual(len(plan['support_posts']), {'left':31,'right':39}[side])
            self.assertLessEqual(housing._maximum_load_distance(shp, plan), 4.40)
            self.assertTrue(all(hole['collision_count']==0 for hole in result['holes']))
            routed = shp['unary_union'](list(plan['routed_copper_wear_geometries'].values()))
            for post in plan['support_posts']:
                disk = shp['Point'](post['x_mm'],post['y_mm']).buffer(post['diameter_mm']/2)
                self.assertGreaterEqual(disk.distance(routed)+1e-5,.3)

    def test_oriented_oval_preserves_major_axis_and_area(self):
        shp = housing.legacy_geometry.require_shapely()
        for angle, expected in ((0, (2.5, 3.2)), (90, (3.2, 2.5))):
            feature = dict(kind="oriented_oval", center=[0, 0],
                           size_x_mm=2.5, size_y_mm=3.2, angle_deg=angle)
            polygon = housing._feature_geometry(shp, feature, (0, 0, 0, 0))
            x0, y0, x1, y1 = polygon.bounds
            self.assertAlmostEqual(x1-x0, expected[0], places=4)
            self.assertAlmostEqual(y1-y0, expected[1], places=4)
            self.assertAlmostEqual(polygon.area, math.pi*1.25**2 + .7*2.5, delta=.015)

    def test_nominal_socket_depth_is_not_qualification(self):
        stack = housing.mx_socket_stack_manifest()
        self.assertEqual(stack["nominal_barrel_below_pcb_mm"], 1.2)
        self.assertEqual(stack["nominal_flange_above_pcb_mm"], .2)
        self.assertEqual(stack["nominal_socket_to_desk_clearance_mm"], 2.3)
        self.assertIsNone(stack["qualified_minimum_desk_clearance_mm"])
        self.assertFalse(stack["order_ready"])
        self.assertIn("switch_pin_protrusion", stack["pending"])


if __name__ == "__main__":
    unittest.main()
