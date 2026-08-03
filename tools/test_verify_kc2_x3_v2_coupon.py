from __future__ import annotations

import unittest

from tools.verify_kc2_x3_v2_coupon import analyze_coupon


class V2CouponTests(unittest.TestCase):
    def test_coupon_covers_left_right_socket_and_mx_fit(self) -> None:
        report = analyze_coupon()

        self.assertEqual(report["switch_refs"], ["SW_L", "SW_MX", "SW_R"])
        self.assertEqual(
            report["switch_footprint_names"], {"SW_Choc_V2_Socket_MX_THT"}
        )
        self.assertEqual(
            report["switch_orientations_deg"],
            {"SW_L": 0.0, "SW_MX": 0.0, "SW_R": 180.0},
        )
        self.assertEqual(report["diode_count"], 3)
        self.assertEqual(report["alternate_contact_net_mismatches"], [])
        self.assertEqual(report["drc_violation_count"], 0)
        self.assertEqual(report["drc_unconnected_count"], 0)
        self.assertLessEqual(report["board_size_mm"][0], 80.0)
        self.assertLessEqual(report["board_size_mm"][1], 40.0)
        self.assertIn("CHOC V1 UNSUPPORTED", report["board_text"].upper())
        self.assertIn("DO NOT POPULATE BOTH MODES", report["board_text"].upper())
        self.assertIn("CHOC RIGHT BOARD", report["board_text"].upper())


if __name__ == "__main__":
    unittest.main(verbosity=2)
