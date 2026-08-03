from __future__ import annotations

import unittest

from tools.verify_kc2_x3_v2_mechanical import analyze_mechanical_outputs


class V2MechanicalOutputTests(unittest.TestCase):
    def test_all_boards_have_one_to_one_top_and_bottom_drawings(self) -> None:
        report = analyze_mechanical_outputs()

        self.assertEqual(report["requirement"], "CON-ARCH-004")
        self.assertEqual(report["scale"], 1.0)
        self.assertEqual(set(report["products"]), {"left", "right", "coupon"})
        for product in report["products"].values():
            self.assertEqual(set(product["drawings"]), {"top", "bottom"})
            for drawing in product["drawings"].values():
                self.assertTrue(drawing["exists"])
                self.assertTrue(drawing["pdf_header_valid"])
                self.assertTrue(drawing["sha256_matches"])
                self.assertGreater(drawing["size"], 1000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
