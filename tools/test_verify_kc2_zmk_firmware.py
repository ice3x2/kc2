"""Focused tests for the CON-ARCH-005 ZMK firmware verifier."""

from __future__ import annotations

import unittest

import verify_kc2_zmk_firmware as verifier


class BindingParserTests(unittest.TestCase):
    def test_preserves_multi_token_zmk_bindings(self) -> None:
        bindings = verifier.parse_bindings(
            """
            bindings = <
                &kp A &bt BT_SEL 0 &out OUT_TOG &trans
            >;
            """
        )

        self.assertEqual(bindings, ["&kp A", "&bt BT_SEL 0", "&out OUT_TOG", "&trans"])


class MatrixTransformTests(unittest.TestCase):
    def test_extracts_matrix_positions_in_transform_order(self) -> None:
        transform = """
            map = <
                RC(0, 0) RC(0, 1)
                RC(1, 0)
            >;
        """

        self.assertEqual(verifier.parse_transform_positions(transform), [(0, 0), (0, 1), (1, 0)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
