/*
 * Copyright (c) 2026 The KC2 Contributors
 *
 * SPDX-License-Identifier: MIT
 */

#define DT_DRV_COMPAT kc2_behavior_power_off

#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/kernel.h>
#include <zephyr/sys/atomic.h>

#include <drivers/behavior.h>
#include <zmk/behavior.h>
#include <zmk/pm.h>

#if IS_ENABLED(CONFIG_ZMK_SPLIT_ROLE_CENTRAL)
#include <zmk/ble.h>
#include <zmk/event_manager.h>
#include <zmk/events/ble_active_profile_changed.h>
#endif

#define KC2_POWER_FLASH_GAP_MS 25
#define KC2_POWER_FLASH_MS 150
#define KC2_PAIRING_BLINK_MS 100
#define KC2_PAIRING_INITIAL_DELAY_MS 500

static const struct gpio_dt_spec blue_led =
    GPIO_DT_SPEC_GET(DT_NODELABEL(blue_led), gpios);
static atomic_t power_off_pending;

static int set_blue_led(bool on) { return gpio_pin_set_dt(&blue_led, on ? 1 : 0); }

static void power_off_work_handler(struct k_work *work) {
    set_blue_led(false);
    zmk_pm_soft_off();
}

K_WORK_DELAYABLE_DEFINE(power_off_work, power_off_work_handler);

static void power_flash_start_work_handler(struct k_work *work) {
    set_blue_led(true);
    k_work_reschedule(&power_off_work, K_MSEC(KC2_POWER_FLASH_MS));
}

K_WORK_DELAYABLE_DEFINE(power_flash_start_work, power_flash_start_work_handler);

#if IS_ENABLED(CONFIG_ZMK_SPLIT_ROLE_CENTRAL)
static bool pairing_led_on;
static void pairing_blink_work_handler(struct k_work *work);
K_WORK_DELAYABLE_DEFINE(pairing_blink_work, pairing_blink_work_handler);

static bool bluetooth_registration_active(void) {
    return zmk_ble_active_profile_is_open() && !zmk_ble_active_profile_is_connected();
}

static void pairing_blink_work_handler(struct k_work *work) {
    if (atomic_get(&power_off_pending) || !bluetooth_registration_active()) {
        pairing_led_on = false;
        set_blue_led(false);
        return;
    }

    pairing_led_on = !pairing_led_on;
    set_blue_led(pairing_led_on);
    k_work_reschedule(&pairing_blink_work, K_MSEC(KC2_PAIRING_BLINK_MS));
}

static int kc2_status_led_listener(const zmk_event_t *event) {
    if (as_zmk_ble_active_profile_changed(event) != NULL) {
        k_work_reschedule(&pairing_blink_work, K_NO_WAIT);
    }

    return ZMK_EV_EVENT_BUBBLE;
}

ZMK_LISTENER(kc2_status_led, kc2_status_led_listener);
ZMK_SUBSCRIPTION(kc2_status_led, zmk_ble_active_profile_changed);
#endif

static int on_power_off_pressed(struct zmk_behavior_binding *binding,
                                struct zmk_behavior_binding_event event) {
    if (!atomic_cas(&power_off_pending, 0, 1)) {
        return ZMK_BEHAVIOR_OPAQUE;
    }

#if IS_ENABLED(CONFIG_ZMK_SPLIT_ROLE_CENTRAL)
    k_work_cancel_delayable(&pairing_blink_work);
    pairing_led_on = false;
#endif

    set_blue_led(false);
    k_work_reschedule(&power_flash_start_work, K_MSEC(KC2_POWER_FLASH_GAP_MS));
    return ZMK_BEHAVIOR_OPAQUE;
}

static int on_power_off_released(struct zmk_behavior_binding *binding,
                                 struct zmk_behavior_binding_event event) {
    return ZMK_BEHAVIOR_OPAQUE;
}

static int kc2_status_led_init(const struct device *device) {
    if (!gpio_is_ready_dt(&blue_led)) {
        return -ENODEV;
    }

    int error = gpio_pin_configure_dt(&blue_led, GPIO_OUTPUT_INACTIVE);
    if (error != 0) {
        return error;
    }

#if IS_ENABLED(CONFIG_ZMK_SPLIT_ROLE_CENTRAL)
    k_work_reschedule(&pairing_blink_work, K_MSEC(KC2_PAIRING_INITIAL_DELAY_MS));
#endif

    return 0;
}

static const struct behavior_driver_api kc2_power_off_driver_api = {
    .binding_pressed = on_power_off_pressed,
    .binding_released = on_power_off_released,
    .locality = BEHAVIOR_LOCALITY_GLOBAL,
};

BEHAVIOR_DT_INST_DEFINE(0, kc2_status_led_init, NULL, NULL, NULL, POST_KERNEL, 90,
                        &kc2_power_off_driver_api);
