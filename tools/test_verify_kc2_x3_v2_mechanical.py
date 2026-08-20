from __future__ import annotations

import unittest

from tools.verify_kc2_x3_v2_mechanical import analyze_mechanical_outputs


class V2MechanicalOutputTests(unittest.TestCase):
    def test_all_boards_have_one_to_one_top_and_bottom_drawings(self) -> None:
        report = analyze_mechanical_outputs()

        self.assertEqual(report["requirement"], "CON-ARCH-004")
        self.assertEqual(report["scale"], 1.0)
        self.assertEqual(set(report["products"]), {"left", "right", "coupon"})
        for name, product in report["products"].items():
            self.assertTrue(product["source_board_exists"])
            self.assertTrue(product["source_board_sha256_matches"])
            self.assertEqual(set(product["drawings"]), {"top", "bottom"})
            for drawing in product["drawings"].values():
                self.assertTrue(drawing["exists"])
                self.assertTrue(drawing["pdf_header_valid"])
                self.assertTrue(drawing["sha256_matches"])
                self.assertGreater(drawing["size"], 1000)
            if name in {"left", "right"}:
                self.assertTrue(product["outline_svg"]["exists"])
                self.assertTrue(product["outline_svg"]["svg_header_valid"])
                self.assertTrue(product["outline_svg"]["sha256_matches"])
                self.assertEqual(product["outline_svg"]["scale"], 1.0)
                self.assertFalse(product["outline_svg"]["has_trailing_whitespace"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
