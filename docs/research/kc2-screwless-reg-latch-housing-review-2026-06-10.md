# KC2 Screwless REG Hole Housing Latch Review - 2026-06-10

## Summary

KC2 X3 하우징을 나사 없이 PCB에 고정하기 위해 기존 `REG_NPTH_3.0` 구멍에 막대 형태의 작은 걸쇠를 넣는 방안을 검토했다.

결론은 다음과 같다.

- `REG_NPTH_3.0` 구멍에 하우징 쪽 `peg`를 올려 위치를 잡고 PCB 휨을 줄이는 방식은 채택 가능하다.
- 그러나 PCB 상면 위로 튀어나오는 `hook`, `barb`, `mushroom head` 형태의 걸쇠는 권장하지 않는다.
- 실제 체결력은 외곽 rail/lip 및 서비스 가능한 snap tab으로 처리하고, REG 구멍은 위치결정과 보조 지지에 쓰는 편이 안전하다.
- 하우징 plastic은 joined inner interlock edge를 침범하지 않아야 하며, `CON-ARCH-001`의 1.0 mm joined Edge.Cuts clearance를 출력 팽창으로 소모하지 않아야 한다.

이 문서는 연구 기록이며, 요구사항의 source of truth는 `docs/spec/`이다.

## SRS Linkage

- Primary requirement: `CON-ARCH-003` - X3 screwless rail housing and registration holes
- Related requirements:
  - `CON-ARCH-001` - X3 interlocked placement clearance for 3D-printed housing
  - `CON-ARCH-002` - X3 compact controller tab without PCB battery pads
- Active target: `kc2-x3`
- Requirement state checked from `docs/spec/10.product-architecture.srs.md`:
  - `CON-ARCH-003`: `Status=verified`, `Stability=stable`
  - `CON-ARCH-001`: `Status=verified`, `Stability=stable`
  - `CON-ARCH-002`: `Status=verified`, `Stability=stable`

SpecKiwi MCP tools were not exposed in this session and `speckiwi` was not on PATH, so the checked-in SRS files were used directly.

## Committee Scope

Three read-only sub-agent reviews were used.

1. Mechanical and switch/keycap interference review
2. PCB, electrical, and component-clearance review
3. 3D-print, tolerance, serviceability, and failure-mode review

No files were changed during the review. This document records the resulting recommendation.

## Existing Design Facts

Current repo artifacts already contain a first-pass lower housing draft under `hardware/case/`.

Existing housing manifest parameters:

| Parameter | Value |
| --- | ---: |
| PCB thickness | `1.6 mm` |
| Floor thickness | `1.2 mm` |
| Bottom component cavity | `3.2 mm` |
| Rail width | `2.0 mm` |
| Support post diameter | `4.8 mm` |
| Registration peg diameter | `2.7 mm` |
| Peg top below PCB top | `0.3 mm` |
| Battery slot clearance | `0.7 mm` |

Current assumptions are appropriate for a fit-check draft: a 2.7 mm peg enters a 3.0 mm NPTH hole with FDM clearance, and the peg top remains below the PCB top surface.

## REG Coordinates

`H1` to `H9` labels correspond to `REG1` to `REG9`. Coordinates are KiCad board coordinates in mm.

| Hole | Left `(x, y)` | Right `(x, y)` |
| --- | ---: | ---: |
| H1 / REG1 | `(63.03, 102.03)` | `(103.12, 84.53)` |
| H2 / REG2 | `(124.71, 91.03)` | `(141.69, 84.03)` |
| H3 / REG3 | `(145.40, 90.53)` | `(200.75, 95.53)` |
| H4 / REG4 | `(66.53, 122.93)` | `(54.38, 127.17)` |
| H5 / REG5 | `(109.21, 122.93)` | `(131.69, 125.93)` |
| H6 / REG6 | `(146.90, 122.93)` | `(200.25, 121.93)` |
| H7 / REG7 | `(61.52, 151.32)` | `(54.88, 144.57)` |
| H8 / REG8 | `(109.21, 151.32)` | `(146.19, 141.82)` |
| H9 / REG9 | `(137.40, 142.32)` | `(205.75, 130.32)` |

The existing case STL coordinate system translates board coordinates by `(-35, -35)`.

## Mechanical Assessment

Straight vertical pegs through the REG holes are viable if they stay flush with or below the PCB top. The holes are placed between switch areas and are useful for XY registration and anti-flex support.

Over-PCB latch hooks are the high-risk part. Using the local keycap envelope model, almost every REG center is inside a keycap top-view envelope or very close to one. A 3.0 mm hole edge effectively overlaps the modeled keycap envelope in many positions. Therefore any above-PCB hook, barb, mushroom head, or large snap cap can rub the keycap skirt or underside during travel unless proven against the exact switch and keycap set.

Best use of REG holes:

- `L-REG5` and `R-REG5`: strongest central anti-flex support points
- `L-REG2`, `L-REG4`, `R-REG3`, `R-REG6`, `R-REG8`: good secondary support/registration points

Worst latch candidates:

- `R-REG4` and `R-REG7`: near local board edge, only about `3.59 mm` and `4.09 mm` drill-edge-to-Edge.Cuts clearance
- Bottom-row holes such as `L-REG7/8/9` and `R-REG7/8/9`: high keycap envelope overlap risk

## PCB And Electrical Assessment

The REG holes are suitable for nonconductive plastic features:

- Both halves have exactly nine `REG_NPTH_3.0` holes.
- The holes are 3.0 mm NPTH, mask-only, and unnetted.
- They do not use `F.Cu` or `B.Cu`.
- No `M2_NPTH_2.2`, `MountingHole_2.2mm_M2`, `J_PWR1`, `BAT+`, `BAT-`, `NN_B+`, or `NN_B-` carrier PCB markers were found.

Tightest local clearances from the REG hole edge:

| Risk class | Tightest examples |
| --- | --- |
| Trace clearance | `L-REG9` to `L_COL4` B.Cu about `0.47 mm`; `R-REG5` to `R_ROW3` B.Cu about `0.49 mm`; `L-REG6` to `L_ROW3` B.Cu about `0.50 mm` |
| Switch pad/socket feature | `R-REG2` to `SW6-2` about `0.89 mm`; `R-REG1` to `SW3-1` about `1.03 mm`; `L-REG5` to `SW17-2` about `1.26 mm` |
| Diode body or footprint envelope | `L-REG5` and `L-REG6` about `1.17 mm`; `R-REG1` about `1.47 mm` |
| Board edge | `R-REG4` about `3.59 mm`; `R-REG7` about `4.09 mm` |

Hard gates:

- Use only nonconductive plastic through REG holes.
- Do not use metal screws, metal dowels, or heat-set inserts in REG holes.
- Do not force oversized pegs into 3.0 mm NPTH holes.
- Do not add large underside collars unless a CAD/PCB overlay proves diode, socket, trace, and pad clearance.
- Keep USB-C, reset tact switch, battery-lead slot, nice!nano socket, and antenna keepout service access open.

## Recommended Housing Architecture

Use a two-function approach:

1. REG pegs and bosses provide XY location, local support, and anti-flex control.
2. Perimeter rail/lip and serviceable snap tabs provide retention.

Recommended assembly sequence:

1. Slide or hook one PCB edge under fixed lips.
2. Lower the PCB onto the nine REG pegs.
3. Press the opposite edge past two or three flexible snap tabs.
4. For removal, release snap tabs through side notches or underside windows, lift one edge, then slide off the fixed lip.

Avoid requiring prying near controller, USB-C, reset switch, battery slot, hotswap sockets, or diode bodies.

## Recommended Dimensions

| Feature | Recommendation |
| --- | ---: |
| PCB pocket XY clearance | `0.20-0.35 mm` per side |
| Housing outer inset from PCB outline | `0.10-0.20 mm`; use `0.25-0.35 mm` near joined/interlock edges |
| Support rail width | keep `2.0 mm`; do not go below `1.6 mm` in PLA+ |
| Rail top height | nominal PCB underside, with `0.05-0.10 mm` relief if fit is tight |
| Bottom component cavity | keep `3.2 mm`; prototype `3.4 mm` if sockets or diodes rub |
| Floor | `1.2 mm` for fit-check; prefer `1.6 mm` or ribs for regular use |
| REG support boss OD | current `4.8 mm` is reasonable; acceptable `4.6-5.2 mm` |
| Straight REG peg OD | `2.60-2.70 mm` for 3.0 mm NPTH |
| Peg lead-in | `0.3-0.5 mm` chamfer or rounded lead-in |
| Peg top | keep `0.3-0.5 mm` below PCB top |
| Optional split-pin experiment | only 2-4 central holes; `2.45-2.55 mm` split stem; no meaningful above-PCB hook height |
| Top/side capture lip overlap | `0.5-0.8 mm` horizontal |
| PCB slot gap for lip capture | `1.70-1.85 mm` vertical |

## Failure Modes

- Pegs print oversized and bind or crack the 3.0 mm NPTH hole wall.
- Peg or rail tops print too high and bow the PCB.
- PCB preload stresses Choc hot-swap sockets, switch solder joints, or SOD-123 diodes.
- PLA+ snap tabs creep or fatigue after repeated service.
- Printed plastic intrudes into the joined interlock edge and prevents the two halves from fitting.
- Battery lead slot, reset access, USB access, or nice!nano access is blocked.
- Large thin tray warps and creates uneven rail height or key feel.
- Non-serviceable snap geometry forces destructive removal.

## Verification Performed

Commands and checks performed during the review:

```powershell
python .\tools\verify_kc2_screwless_board_text.py
& 'C:\Program Files\KiCad\10.0\bin\python.exe' .\tools\verify_kc2_screwless_registration.py
& 'C:\Program Files\KiCad\10.0\bin\python.exe' .\tools\verify_kc2_compact_controller.py
& 'C:\Program Files\KiCad\10.0\bin\python.exe' .\tools\verify_kc2_antenna_keepout.py
& 'C:\Program Files\KiCad\10.0\bin\python.exe' .\tools\verify_kc2_drc_json_clean.py
```

Results:

- `verify_kc2_screwless_board_text.py`: PASS
- `verify_kc2_screwless_registration.py`: PASS
- `verify_kc2_compact_controller.py`: PASS
- `verify_kc2_antenna_keepout.py`: PASS
- `verify_kc2_drc_json_clean.py`: PASS
- DRC JSON summary: left and right both have `0` errors and `0` unconnected items; only allowed `silk_over_copper` warnings remain.

## Prototype Checklist

Before treating the housing as production-ready:

1. Print a peg coupon with `2.55`, `2.60`, `2.65`, `2.70`, and `2.75 mm` peg diameters.
2. Measure printed peg OD, rail height, floor thickness, and PCB pocket width with calipers.
3. Dry-fit a bare PCB first; it must seat without visible bow.
4. Confirm all nine REG holes drop onto pegs without sequential forcing.
5. Check bottom socket, diode, and battery-lead clearance with paper or feeler gauge.
6. Assemble both halves and verify joined interlock clearance with housings installed.
7. Cycle install/remove at least 10 times and inspect snap whitening, peg wear, and PCB hole wear.
8. Type/flex test center zones; confirm posts reduce flex without creating pressure points.
9. Verify USB-C, reset switch, battery lead routing, and nice!nano service access after assembly.
10. Before fabrication or production approval, rerun the KC2 hardware fabrication gate and treat FDM housing fit as separate physical evidence.

## Final Stance

Adopt the hole-based support idea as straight plastic registration pegs. Do not make the REG holes carry primary retention by over-PCB hooks. The safer screwless housing is a rail/capture tray: 9 REG pegs for location/support, perimeter lips for capture, and a few accessible outer-edge snap tabs for retention.
