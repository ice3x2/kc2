from __future__ import annotations

import unittest

from tools.verify_kc2_x3_v2_housing import analyze_v2_housing_reuse


class V2HousingReuseTests(unittest.TestCase):
    def test_v2_switches_clear_verified_x3_housing(self) -> None:
        report = analyze_v2_housing_reuse()

        self.assertEqual(report["switch_center_mismatches"], [])
        self.assertEqual(report["registration_center_mismatches"], [])
        self.assertEqual(report["socket_envelope_mismatches"], [])
        self.assertEqual(report["socket_wall_collision_count"], 0)
        self.assertGreaterEqual(report["minimum_socket_wall_clearance_mm"], 0.30)
        self.assertEqual(report["mx_solder_wall_collision_count"], 0)
        self.assertGreaterEqual(report["minimum_mx_solder_wall_clearance_mm"], 0.30)
        self.assertEqual(report["mx_solder_post_collision_count"], 0)
        self.assertGreaterEqual(report["minimum_mx_solder_post_clearance_mm"], 0.30)
        self.assertEqual(report["socket_diode_collision_count"], 0)
        self.assertGreaterEqual(report["minimum_socket_diode_clearance_mm"], 0.30)
        self.assertEqual(report["choc_solder_fillet_wall_collision_count"], 0)
        self.assertGreaterEqual(report["minimum_choc_solder_fillet_wall_clearance_mm"], 0.0)
        self.assertEqual(report["choc_solder_fillet_diode_collision_count"], 0)
        self.assertGreaterEqual(report["minimum_choc_solder_fillet_diode_clearance_mm"], 0.30)
        self.assertEqual(report["choc_solder_fillet_lateral_allowance_mm"], 0.30)
        self.assertEqual(report["mx_solder_diode_body_collision_count"], 0)
        self.assertGreaterEqual(report["minimum_mx_solder_diode_body_clearance_mm"], 0.30)
        self.assertEqual(report["mx_solder_diode_pad_collision_count"], 0)
        self.assertGreaterEqual(report["minimum_mx_solder_diode_pad_clearance_mm"], 0.15)
        self.assertEqual(report["bottom_component_clearance_mm"], 2.60)
        self.assertEqual(report["maximum_trimmed_mx_projection_mm"], 2.20)
        self.assertEqual(report["minimum_vertical_clearance_mm"], 0.40)

    def test_reused_housing_preserves_flat_split_print_constraints(self) -> None:
        report = analyze_v2_housing_reuse()

        self.assertEqual(report["floor_thickness_mm"], 1.20)
        self.assertEqual(report["rear_rise_mm"], 0.0)
        self.assertLessEqual(report["largest_printable_part_dimension_mm"], 150.0)
        self.assertEqual(report["right_split_part_count"], 2)
        self.assertGreaterEqual(report["right_split_bond_length_ratio"], 1.50)
        self.assertEqual(report["right_split_assembled_gap_mm"], 0.40)


if __name__ == "__main__":
    unittest.main(verbosity=2)
