# KC2 X3 V2 controller-region compaction review — 2026-08-26

This document records non-normative design research for `CON-ARCH-004` and `CON-ARCH-006`. The acceptance criteria in `docs/spec/10.product-architecture.srs.md` remain the only requirements source.

> **2026-09-01 supersession:** The TW301525, USB-under-reset, ES1B and eighteen-hole geometry below are historical; active controller service and P3 mount geometry are defined by `CON-ARCH-006` and `CON-ARCH-007`.

## User intent

At the time of this review, the key-field perimeter was already extremely thin, but the controller tab and the space between the controller and top-row switches looked disproportionately large. The historical proposal placed the reset tact switch portrait-oriented directly below the USB port and reduced the controller service region without moving the selected 70-key layout or the then-current eighteen M1.4 mounting points.

## Committee method

Three independent reviewers inspected the exact 31-left/39-right KiCad boards and current housing contract:

- an electrical/routing reviewer measured pad, net, route, antenna, battery, DRC, and reproducibility impacts;
- a mechanical/ergonomic reviewer measured controller, tact, keycap, outline, support, cable, and housing envelopes;
- a manufacturing/requirements reviewer checked the proposal against controlled dimensions, PCBWay tolerances, source-of-truth requirements, service access, and order-risk gates.

The reviewers first proposed independent layouts, then cross-checked the same selected seed. All three rejected an initial more aggressive `U1 Y=51.75 / reset Y=64.45` proposal because it cut into the moved battery envelope and left only body-only reset clearance. The selected candidate below is the common digital starting point, not physical-fit or order approval.

## Selected exact digital seed

All coordinates are KiCad board coordinates in millimetres.

| Feature | Left | Right | Contract |
| --- | ---: | ---: | --- |
| U1 | (132.7125, 50.7500) | (77.4000, 50.7500) | owned side-specific nice!nano socket, 0 deg |
| BAT_LEAD_SLOT1 | (117.9125, 50.7500) | (92.2000, 50.7500) | copper-free 3.60 x 2.20 NPTH slot |
| TW301525 nominal reference | (133.2125, 53.0500) | (76.9000, 53.0500) | 15.00 x 25.00 nominal body plan |
| SW_RST1 | (115.8125, 63.4500) | (94.3000, 63.4500) | owned NW3 footprint, 90 deg; pad 1 RST key-side, pad 2 GND controller-side |
| top Edge.Cuts centerline | Y=39.2500 | Y=39.2500 | preserve every key and MH center |

The modeled U1 body occupies `Y=41.60..59.90`; the reset body occupies `Y=60.40..66.50`; and the nearest selected keycap plan begins at `Y=68.50`. Nominal body clearances are therefore `0.50 mm` controller-to-reset and `2.00 mm` reset-to-keycap. The actual placed reset courtyard ends at `Y=68.425` and its lower pad copper ends at `Y=68.20`, giving only `0.075 mm` courtyard-to-keycap and `0.30 mm` pad-to-keycap plan gaps. These values must remain visible evidence and shall not be presented as production tolerance.

The controlled 18.30 mm U1 width leaves `2.35 mm` to the shortened top outline. The nominal 15 x 25 mm battery plan occupies `Y=40.55..65.55`, leaving `1.30 mm` to the PCB edge and, after a 0.10 mm housing inset plus 0.35 mm cutout allowance, exactly `0.85 mm` housing land. The board centerline height reduces from `126.75 mm` to `122.50 mm`, a `4.25 mm` reduction, while the key field and mounting datum remain unchanged.

## Rejected shortcuts and discovered blockers

1. `CON-ARCH-002` is stable and verified for historical X3 and requires antenna-side reset placement. X3 V2 must explicitly supersede only that placement clause; its no-carrier-power and direct battery-lead assumptions remain valid.
2. The generator normalizes the minimum Y to 35.00 mm. Cropping only the raw outline would therefore translate the key and mounting patterns or undo the crop. V2 needs a fixed datum with mutation tests for all 70 switch and 18 mounting centers.
3. Moving U1 invalidates the existing controller fanouts. The selected reset also overlaps current left `L_COL2`, right `R_COL7`, and the right `R_ROW2` clearance. Both halves need new deterministic routing, exact reconstruction/idempotence evidence, and fresh KiCad 10 DRC.
4. The current housing extractor matches `U1` but does not match the exact `SW_RST1` reference, and it models only `BAT_LEAD_SLOT1`, not the 15 x 25 battery body. Existing controller/reset and battery reports can therefore false-pass.
5. A top-side SMD reset should receive local zero-gap support beneath its actuator rather than an unconditional bottom opening. The nominal bottom battery body requires an exterior-open cutout and a desk-contact height that preserves at least 0.50 mm clearance for the provisional 3.00 mm thickness.
6. Existing USB and antenna legends approach or cross the new rounded outline and must be relocated and checked using complete text bounding boxes.

## Physical gates retained

Digital geometry does not establish the actual socketed nice!nano, mid-mount USB shell, cable overmold, soldered reset terminals, actuator travel, printed keycap skirt, battery swelling, adhesive retention, lead bend, or strain relief. The service assumption is USB disconnected, keycaps and controller installed, and a nonconductive probe no larger than 3.00 mm within a 4.00 mm actuator corridor. A first article shall complete ten double-reset cycles without adjacent-key actuation, pad damage, controller contact, or visible PCB flex, then enumerate the bootloader after USB reconnection.

The nominal battery edge and housing-land values have no remaining surplus for pouch and placement tolerance. Exact battery maximum dimensions, swelling allowance, retention, abrasion protection, and lead routing remain physical gates. The draft therefore remains `order_ready=false`; this research authorizes only the TDD-backed digital redesign and subsequent limited prototype preflight under the SRS.

The implemented digital housing keeps the `2.50 mm` structural plate and moves every coplanar desk contact to Z=`-1.00 mm`. The complete nominal `15 x 25 x 3.00 mm` battery envelope receives an exterior-open cutout with `0.35 mm` XY allowance and `0.50 mm` nominal desk clearance. The top-side reset actuator receives a separate `3.00 mm` zero-gap support/desk column rather than a bottom cutout. Existing 14-left/11-right distributed supports and their `15.4640/18.9619 mm` maximum load spans are unchanged. These are verified CAD values, not evidence for battery swelling, reset service, or physical deflection.
