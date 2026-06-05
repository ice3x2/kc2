# KC2 X3 Antenna Keepout Hole Removal Review

| Field | Value |
|---|---|
| Target | kc2-x3 |
| Date | 2026-06-06 |
| Requirement IDs | CON-ARCH-002, OPS-ARCH-001, OPS-ARCH-002 |
| Decision | PASS / ORDER READY |
| Sub-agent result | 5 / 5 PASS |

## Summary

The M2 mounting holes that intersected the nice!nano v2 antenna keepout were removed from both halves.

- Left: the previous antenna-keepout-intersecting M2 hole was removed.
- Right: the previous antenna-keepout-intersecting M2 hole was removed.
- Current left board: 4 M2 mounting holes, none inside antenna keepout.
- Current right board: 4 M2 mounting holes, none inside antenna keepout.
- Gerber, drill, Gerber job, JLCPCB ZIP, and joined render outputs were regenerated after the change.

## Official nice!nano References

- Pinout and schematic: https://nicekeyboards.com/docs/nice-nano/pinout-schematic/
- v2 pinout image: https://nicekeyboards.com/static/1788ac663060fd510f4894b286cd97b1/a6d36/pinout-v2.png
- Battery / B+ / B- guidance: https://nicekeyboards.com/docs/nice-nano/getting-started/

## Current Board Evidence

### Antenna Keepout

`tools/verify_kc2_antenna_keepout.py`: PASS

- Left keepout: `(157.6825, 39.85, 167.6825, 58.15)`
- Right keepout: `(54.53, 39.85, 64.53, 58.15)`
- No M2 mounting hole drill circle intersects either keepout.
- No copper pads, vias, or tracks are inside either keepout.

### nice!nano v2 Pinout / U1 Orientation

- Left `U1` top row matches `USB_OUT_LEFT`:
  `RAW,GND_C,RST,VCC,D21,D20,D19,D18,D15,D14,D16,D10`
- Right `U1` top row matches `USB_OUT_RIGHT`:
  `D9,D8,D7,D6,D5,D4,D3,D2,GND_B,GND_A,D0,D1`
- Matrix nets use GPIO pads only.
- Matrix nets do not use `RAW`, `VCC`, `GND_A`, `GND_B`, `GND_C`, `RST`, `D0`, or `D1`.

### Matrix Wiring

`tools/verify_kc2_connectivity.py`: PASS

- Left: 32 switches, 32 diodes, no stabilizer footprints.
- Right: 45 switches, 45 diodes, no stabilizer footprints.
- Switch pad 1 goes to the expected column net.
- Switch pad 2 goes to the matching local key-diode net.
- Diode pad 2 goes to the matching local key-diode net.
- Diode pad 1 goes to the expected row net.
- Row, column, local, and reset nets are connected to the expected U1 pins.

### Reset / Power / Battery Nets

`tools/verify_kc2_compact_controller.py`: PASS

- `SW_RST1` pad 1 is `RST`.
- `SW_RST1` pad 2 is `GND`.
- `J_PWR1` is absent.
- Carrier PCB nets `BAT+`, `BAT-`, `NN_B+`, and `NN_B-` are absent.
- Battery leads must be soldered directly to nice!nano v2 `B+` and `B-`.

### DRC and Fabrication

- KiCad CLI DRC left: 0 violations, 0 unconnected.
- KiCad CLI DRC right: 0 violations, 0 unconnected.
- `kc2-pcb-preflight`: ORDER READY.
- `kc2_left_jlcpcb.zip`: 15 root-level files, no nested directory.
- `kc2_right_jlcpcb.zip`: 15 root-level files, no nested directory.
- `kc2_fabrication.zip`: 30 side-scoped files.

## Five Sub-agent Review Results

| # | Review Scope | Result |
|---:|---|---|
| 1 | nice!nano v2 pinout and U1 socket orientation | PASS |
| 2 | Left switch / diode / matrix wiring | PASS |
| 3 | Right switch / diode / matrix wiring | PASS |
| 4 | Reset, ground, power, and battery net safety | PASS / ORDER READY |
| 5 | Component, footprint, antenna keepout, and fabrication review | PASS |

All five post-fix sub-agents reported PASS. The previous blocker, M2 mounting holes intersecting the antenna keepout, is resolved.

## Residual Non-blocking Notes

- Battery leads must be soldered directly to nice!nano v2 `B+` and `B-`; there are no carrier PCB battery pads.
- `kc2-pcb-preflight` reports minimum copper-edge clearance as left `0.963 mm` and right `2.594 mm`; both are above the configured gate.

## Final Decision

PASS / ORDER READY.

The antenna-interfering holes have been removed, current automated checks pass, fabrication packages were regenerated, and five independent post-fix sub-agent reviews reached unanimous PASS.
