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


class SoftOffTests(unittest.TestCase):
    def test_detects_matrix_soft_off_waker(self) -> None:
        overlay = """
            soft_off_wakers: soft_off_wakers {
                compatible = "zmk,soft-off-wakeup-sources";
                wakeup-sources = <&kscan0>;
            };
        """

        self.assertTrue(verifier.has_matrix_soft_off_waker(overlay))

    def test_rejects_soft_off_waker_without_matrix(self) -> None:
        overlay = """
            soft_off_wakers: soft_off_wakers {
                compatible = "zmk,soft-off-wakeup-sources";
            };
        """

        self.assertFalse(verifier.has_matrix_soft_off_waker(overlay))

    def test_detects_soft_off_kconfig(self) -> None:
        source = """
            config ZMK_PM_SOFT_OFF
                default y
        """

        self.assertTrue(verifier.has_soft_off_config(source))

    def test_maps_numbered_switches_to_global_transform_indices(self) -> None:
        transform = [(0, 0), (0, 1), (0, 7), (0, 8)]

        self.assertEqual(
            verifier.transform_index_for_switch(transform, [(0, 0), (0, 1)], "left", 2),
            1,
        )
        self.assertEqual(
            verifier.transform_index_for_switch(transform, [(0, 0), (0, 1)], "right", 2),
            3,
        )

    def test_detects_complete_status_led_implementation(self) -> None:
        source = """
            #define KC2_POWER_FLASH_MS 150
            #define KC2_PAIRING_BLINK_MS 100
            GPIO_DT_SPEC_GET(DT_NODELABEL(blue_led), gpios)
            zmk_pm_soft_off();
            zmk_ble_active_profile_is_open();
            zmk_ble_active_profile_is_connected();
            CONFIG_ZMK_SPLIT_ROLE_CENTRAL
            BEHAVIOR_LOCALITY_GLOBAL
            ZMK_SUBSCRIPTION(kc2_status_led, zmk_ble_active_profile_changed)
        """

        self.assertTrue(verifier.has_status_led_implementation(source))

    def test_rejects_status_led_without_pairing_feedback(self) -> None:
        source = """
            #define KC2_POWER_FLASH_MS 150
            GPIO_DT_SPEC_GET(DT_NODELABEL(blue_led), gpios)
            zmk_pm_soft_off();
            BEHAVIOR_LOCALITY_GLOBAL
        """

        self.assertFalse(verifier.has_status_led_implementation(source))


if __name__ == "__main__":
    unittest.main(verbosity=2)
