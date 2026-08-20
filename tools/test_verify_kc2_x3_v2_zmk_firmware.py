"""Focused tests for the CON-ARCH-004 KC2 X3 V2 ZMK firmware."""

from __future__ import annotations

import unittest

from tools import verify_kc2_x3_v2_zmk_firmware as verifier


class V2FirmwareContractTests(unittest.TestCase):
    def test_readme_documents_reproducible_pinned_build(self) -> None:
        readme = (verifier.SHIELD_DIR / "README.md").read_text(encoding="utf-8")

        self.assertIn("ZMK v0.3.0", readme)
        self.assertIn("edf5c0814fd3ea202e43aad2d68fd32e882a518c", readme)
        self.assertIn("-b nice_nano_v2", readme)
        self.assertIn("-DSHIELD=kc2_x3_v2_left", readme)
        self.assertIn("-DSHIELD=kc2_x3_v2_right", readme)
        self.assertIn("-DZMK_EXTRA_MODULES=", readme)
        self.assertIn("firmware/build/kc2_x3_v2_left", readme)
        self.assertIn("firmware/build/kc2_x3_v2_right", readme)
        self.assertIn("firmware/out/kc2_x3_v2_left.uf2", readme)
        self.assertIn("firmware/out/kc2_x3_v2_right.uf2", readme)

    def test_exact_v4_transform_and_half_counts(self) -> None:
        transform = verifier.read_transform()

        self.assertEqual(len(transform), 71)
        self.assertEqual(len(verifier.positions_for_half(transform, "left")), 32)
        self.assertEqual(len(verifier.positions_for_half(transform, "right")), 39)
        self.assertEqual(
            [len([position for position in transform if position[0] == row]) for row in range(5)],
            [15, 14, 14, 15, 13],
        )

    def test_default_layer_is_exact_v4_behavior_order(self) -> None:
        bindings = verifier.read_layer("default_layer")

        self.assertEqual(bindings, verifier.EXPECTED_DEFAULT_BINDINGS)
        self.assertEqual(len(bindings), 71)
        self.assertEqual(bindings[50:58], [
            "&kp N", "&kp M", "&kp COMMA", "&kp DOT", "&kp FSLH",
            "&kp RSHFT", "&kp UP", "&mo 1",
        ])
        self.assertNotIn("&kp HOME", bindings)
        self.assertNotIn("&kp PG_UP", bindings)
        self.assertNotIn("&kp PG_DN", bindings)
        self.assertEqual(bindings[68:71], ["&kp LEFT", "&kp DOWN", "&kp RIGHT"])

    def test_right_overlay_uses_eight_board_columns(self) -> None:
        pins = verifier.read_overlay_pins("right")

        self.assertEqual(pins["cols"], verifier.EXPECTED_PINS["right"]["cols"])
        self.assertEqual(len(pins["cols"]), 8)
        self.assertNotIn((0, 31), pins["cols"])
        self.assertEqual(pins["cols"][-1], (0, 29))

    def test_variant_metadata_states_supported_assembly_modes(self) -> None:
        metadata = verifier.read_variant_metadata()

        self.assertEqual(metadata["variant"], "kc2-x3-v2")
        self.assertEqual(metadata["key_count"], {"left": 32, "right": 39, "total": 71})
        self.assertEqual(metadata["supported_assembly"], ["choc-v2-bottom-socket", "mx-direct-solder"])
        self.assertEqual(metadata["unsupported_assembly"], ["choc-v1", "choc-v2-direct-solder", "mx-hotswap"])
        self.assertEqual(metadata["battery_leads"], "direct-to-nice-nano-b-plus-b-minus")


if __name__ == "__main__":
    unittest.main(verbosity=2)
