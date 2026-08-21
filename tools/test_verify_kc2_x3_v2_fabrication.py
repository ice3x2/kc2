from __future__ import annotations

import unittest

from tools.verify_kc2_x3_v2_fabrication import analyze_fabrication


class V2FabricationTests(unittest.TestCase):
    def test_all_draft_fabrication_archives_are_complete(self) -> None:
        report = analyze_fabrication()

        self.assertEqual(report["variant"], "x3-v2")
        self.assertEqual(set(report["products"]), {"left", "right", "coupon"})
        for product, product_report in report["products"].items():
            with self.subTest(product=product):
                self.assertTrue(product_report["archive_exists"])
                self.assertTrue(product_report["source_board_exists"])
                self.assertTrue(product_report["source_board_sha256_matches"])
                self.assertTrue(product_report["key_count_matches"])
                self.assertEqual(product_report["missing_required_layers"], [])
                self.assertEqual(product_report["missing_drill_types"], [])
                self.assertEqual(product_report["nested_archive_entries"], [])
                self.assertTrue(product_report["has_bottom_paste"])
                self.assertTrue(product_report["has_job_file"])
                self.assertTrue(product_report["archive_sha256_matches"])
                self.assertEqual(product_report["file_hash_mismatches"], [])
                self.assertEqual(product_report["gerber_geometry_errors"], [])
                self.assertTrue(product_report["drill_geometry_matches"])
                self.assertEqual(
                    product_report["drill_tools_mm"],
                    product_report["expected_drill_tools_mm"],
                )
                self.assertGreaterEqual(product_report["archive_entry_count"], 13)

        self.assertEqual(report["products"]["left"]["bottom_paste_flash_count"], 128)
        self.assertEqual(report["products"]["right"]["bottom_paste_flash_count"], 156)
        self.assertEqual(report["products"]["coupon"]["bottom_paste_flash_count"], 12)

        self.assertEqual(
            report["products"]["left"]["drill_tools_mm"],
            {
                "PTH": {"0.300": 20, "0.950": 24, "1.500": 64},
                "NPTH": {"1.650": 32, "1.700": 64, "2.200": 1, "3.000": 64, "5.000": 32},
            },
        )
        self.assertEqual(
            report["products"]["left"]["source_board_via_drills_mm"],
            {"0.300": 20},
        )
        self.assertEqual(
            report["products"]["right"]["drill_tools_mm"],
            {
                "PTH": {"0.300": 28, "0.950": 24, "1.500": 78},
                "NPTH": {"1.650": 39, "1.700": 78, "2.200": 1, "3.000": 78, "5.000": 39},
            },
        )
        self.assertEqual(
            report["products"]["right"]["source_board_via_drills_mm"],
            {"0.300": 28},
        )
        self.assertEqual(
            report["products"]["coupon"]["drill_tools_mm"],
            {
                "PTH": {"1.500": 6},
                "NPTH": {"1.650": 3, "1.700": 6, "3.000": 6, "5.000": 3},
            },
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
