# KC2 KiCad PCB Draft Status - 2026-06-04

## Generated Artifacts

- Left KiCad project: `hardware/kicad/kc2_left/kc2_left.kicad_pro`
- Left PCB: `hardware/kicad/kc2_left/kc2_left.kicad_pcb`
- Right KiCad project: `hardware/kicad/kc2_right/kc2_right.kicad_pro`
- Right PCB: `hardware/kicad/kc2_right/kc2_right.kicad_pcb`
- Generator: `tools/generate_kc2_pcbs.py`
- Manifest: `hardware/kicad/kc2_generation_manifest.json`
- Render previews:
  - `hardware/kicad/renders/kc2_left_top.png`
  - `hardware/kicad/renders/kc2_right_top.png`

## MCP Usage

The local KiCad MCP HTTP server was started with KiCad 9.0.7 and used for:

- tool inventory
- footprint inspection
- board footprint and net inspection
- antenna keepout dry-run and write operations
- unrouted net checks
- DRC execution and DRC report summaries

MCP backup files were produced beside the PCB files during keepout edits.

## Implemented Spec Coverage

- Two independent PCB projects, `kc2_left` and `kc2_right`.
- KC2 naming is used in project names, board title blocks, and silkscreen.
- Left half has 30 key footprints; right half has 41 key footprints.
- Right-hand Korean `B_RH` key is present on the right bottom row, left of the 2u Space.
- Controller is a horizontal nice!nano v2 24-pin socket representation above the number row.
- USB direction markers are present:
  - left: `USB_OUT_LEFT`
  - right: `USB_OUT_RIGHT`
- Antenna direction marker and 10 mm antenna keepout rectangle are present.
- Direct-solder power pads are present: `BAT+`, `BAT-`, `NN_B+`, `NN_B-`.
- No slide switch or A2506 connector footprint is used.
- Reset/programming tact switch footprint is present on each half.
- Reset/programming tact switch was changed to the smaller DeviceMart 1322056 `NW3-A06-B3` SMD micro tact footprint.
- M2 NPTH mounting holes are present on each half.
- PCB outline follows the row-staggered key envelope and includes a rounded controller protrusion tab.
- Inner attach edge uses the reduced-margin side by construction:
  - left half right edge
  - right half left edge
- Controller protrusion tabs are now X-aligned toward the joining edge:
  - left half controller tab toward the right edge, recessed 12 mm from the joining edge
  - right half controller tab toward the left edge, recessed 17 mm from the joining edge
- Controller protrusion tab width is 72 mm. The added width grows away from the joining edge and keeps the joining-edge recess unchanged.
- Top render PNGs were generated successfully with `kicad-cli pcb render`.

## Draft Footprint Decisions

- Switch footprint used in this draft: `SW_Kailh_Choc_V1V2_THT_Hybrid`.
- This keeps a low-profile multi-compatible THT footprint for Kailh Choc V1/V2 instead of locking the design to one switch model.
- Earlier `SW_MX_LowProfile_Kailh_Choc_V1V2_THT_Hybrid` produced much larger DRC conflict counts because of extra alternate holes and pads.
- Diode footprint used in this draft: `D_SOD-123`, value `1N4148W_SOD-123`.
- The DO-35 axial diode was not used in the routed draft because compact 19.05 mm pitch plus hybrid switch holes leaves insufficient DRC-clean routing space.
- Programming tact footprint used in the updated draft: local `KC2:SW_NW3_A06_B3_SMD`, based on the DeviceMart 1322056 drawing.

## Current Validation

MCP `kicad_find_unrouted_nets` result:

- left: 0 unrouted nets
- right: 0 unrouted nets

MCP/KiCad DRC summary after Freerouting/SES import and right-side pin-map adjustment:

| Board | Total | Errors | Warnings | Remaining Warning Rules |
| --- | ---: | ---: | ---: | --- |
| left | 38 | 0 | 38 | `lib_footprint_issues`, `text_height`, `silk_over_copper`, `silk_edge_clearance`, `silk_overlap`, `nonmirrored_text_on_back_layer` |
| right | 47 | 0 | 47 | `track_dangling`, `lib_footprint_issues`, `text_height`, `silk_over_copper`, `silk_overlap`, `nonmirrored_text_on_back_layer` |

The boards have no KiCad DRC errors and no unrouted nets in the current draft. Remaining warnings are review items rather than hard connectivity/clearance blockers.

## Hot-swap Variant - 2026-06-04

Separate hot-swap KiCad projects were generated so the soldered KC2 draft remains unchanged.

- Left KiCad project: `hardware/kicad/kc2_left-hotswap/kc2_left-hotswap.kicad_pro`
- Left PCB: `hardware/kicad/kc2_left-hotswap/kc2_left-hotswap.kicad_pcb`
- Right KiCad project: `hardware/kicad/kc2_right-hotswap/kc2_right-hotswap.kicad_pro`
- Right PCB: `hardware/kicad/kc2_right-hotswap/kc2_right-hotswap.kicad_pcb`
- Manifest: `hardware/kicad/kc2_hotswap_generation_manifest.json`
- Autoroute files:
  - `hardware/kicad/autoroute/kc2_left-hotswap.dsn`
  - `hardware/kicad/autoroute/kc2_left-hotswap.ses`
  - `hardware/kicad/autoroute/kc2_right-hotswap.dsn`
  - `hardware/kicad/autoroute/kc2_right-hotswap.ses`
- Render previews:
  - `hardware/kicad/renders/kc2_left-hotswap_top.png`
  - `hardware/kicad/renders/kc2_left-hotswap_bottom.png`
  - `hardware/kicad/renders/kc2_right-hotswap_top.png`
  - `hardware/kicad/renders/kc2_right-hotswap_bottom.png`

Hot-swap footprint decision:

- The applied footprint is `key-switches.pretty:SW_Kailh_Choc_V1V2_HotSwap_Hybrid`.
- This is the Kailh Choc V1/V2 low-profile hot-swap socket variant, not the MX-only Kailh hot-swap socket family.
- The target socket family is Kailh Choc/PG1350/PG1353, part-number family `CPG135001S30`.
- The hotswap board assumes bottom-side socket soldering and requires physical orientation verification before fabrication.

Freerouting v2.1.0 hotswap result:

| Board | Incomplete Connections | Clearance Violations |
| --- | ---: | ---: |
| left-hotswap | 0 | 0 |
| right-hotswap | 0 | 0 |

KiCad DRC hotswap summary after SES import:

| Board | Total | Errors | Warnings | Unconnected | Remaining Warning Rules |
| --- | ---: | ---: | ---: | ---: | --- |
| left-hotswap | 41 | 0 | 41 | 0 | `text_height`, `silk_over_copper`, `lib_footprint_issues`, `track_dangling`, `silk_overlap`, `nonmirrored_text_on_back_layer`, `silk_edge_clearance` |
| right-hotswap | 51 | 0 | 51 | 0 | `text_height`, `silk_over_copper`, `track_dangling`, `lib_footprint_issues`, `silk_overlap`, `nonmirrored_text_on_back_layer` |

The hot-swap variant is routed and DRC-clean for hard errors, with warning-only review items remaining. Because KC2 is plateless, hotswap socket retention, socket body clearance against the bottom plate, and stabilized-key behavior still need a 1:1 test coupon or physical print before ordering.

## X1 Variant - 2026-06-04

The `x1` variant copies the hot-swap board shape and switch socket choice, then replaces the diode footprint with a hand-solder-oriented SOD-123 footprint for DeviceMart 14592018 `1N4148W`.

- Left KiCad project: `hardware/kicad/kc2_left-x1/kc2_left-x1.kicad_pro`
- Left PCB: `hardware/kicad/kc2_left-x1/kc2_left-x1.kicad_pcb`
- Right KiCad project: `hardware/kicad/kc2_right-x1/kc2_right-x1.kicad_pro`
- Right PCB: `hardware/kicad/kc2_right-x1/kc2_right-x1.kicad_pcb`
- Manifest: `hardware/kicad/kc2_x1_generation_manifest.json`
- Diode footprint: `kc2.pretty:D_SOD123_HandSolder_14592018`
- Diode value: `1N4148W_SOD123_DeviceMart_14592018`
- Switch footprint: `key-switches.pretty:SW_Kailh_Choc_V1V2_HotSwap_Hybrid`
- The diode pad is enlarged to `1.4 mm x 1.55 mm`; KiCad's default `D_SOD-123` pad is `0.9 mm x 1.2 mm`.
- Right half top outline relief: `0.3 mm`, added to preserve edge clearance after autorouting with enlarged diode pads.

Freerouting v2.1.0 x1 result:

| Board | Incomplete Connections | Clearance Violations |
| --- | ---: | ---: |
| left-x1 | 0 | 0 |
| right-x1 | 0 | 0 |

KiCad DRC x1 summary after SES import:

| Board | Total | Errors | Warnings | Unconnected | Remaining Warning Rules |
| --- | ---: | ---: | ---: | ---: | --- |
| left-x1 | 70 | 0 | 70 | 0 | `silk_over_copper`, `text_height`, `lib_footprint_issues`, `silk_overlap`, `track_dangling`, `nonmirrored_text_on_back_layer`, `silk_edge_clearance` |
| right-x1 | 99 | 0 | 99 | 0 | `silk_over_copper`, `text_height`, `track_dangling`, `lib_footprint_issues`, `silk_overlap`, `nonmirrored_text_on_back_layer` |

X1 render previews:

- `hardware/kicad/renders/kc2_left-x1_top.png`
- `hardware/kicad/renders/kc2_left-x1_bottom.png`
- `hardware/kicad/renders/kc2_right-x1_top.png`
- `hardware/kicad/renders/kc2_right-x1_bottom.png`

The X1 boards have no KiCad DRC errors and no unrouted nets. Remaining warnings are review items, mostly silkscreen overlap/text height plus embedded generated KC2 placeholder footprints that are not yet standalone `.kicad_mod` library entries.

## X2 Variant - 2026-06-04

The `x2` variant copies X1's DeviceMart 14592018 hand-solder diode choice, then changes the switch footprint to support both a Kailh Choc V1 hot-swap socket and direct through-hole switch soldering.

- Left KiCad project: `hardware/kicad/kc2_left-x2/kc2_left-x2.kicad_pro`
- Left PCB: `hardware/kicad/kc2_left-x2/kc2_left-x2.kicad_pcb`
- Right KiCad project: `hardware/kicad/kc2_right-x2/kc2_right-x2.kicad_pro`
- Right PCB: `hardware/kicad/kc2_right-x2/kc2_right-x2.kicad_pcb`
- Manifest: `hardware/kicad/kc2_x2_generation_manifest.json`
- Switch footprint: `key-switches.pretty:SW_Kailh_Choc_V1_HotSwap_THT`
- Diode footprint: `kc2.pretty:D_SOD123_HandSolder_14592018`
- Diode y offset: `-7.6 mm`

X2 switch-footprint research:

- `SW_Kailh_Choc_V1_HotSwap_THT` describes itself as a Kailh Choc V1 / PG1350 low-profile switch footprint with both hot-swap socket pads and through-hole soldering.
- The `key-switches.pretty` compatibility table marks `Kailh_Choc_V1_HotSwap_THT` as compatible with Kailh Choc V1, THT, and Hot-Swap.
- This is a Choc V1 / PG1350-centered decision. X2 does not preserve X1's Choc V1/V2 hot-swap-only footprint because the existing library does not provide an equivalent Choc V1/V2 + Hot-Swap + THT footprint.
- The first X2 DRC attempt showed clearance errors between the added switch THT pads and the original X1 diode position. Moving the X2 diodes from `-6.8 mm` to `-7.6 mm` from switch center cleared those hard errors.

Freerouting v2.1.0 x2 result:

| Board | Incomplete Connections | Clearance Violations |
| --- | ---: | ---: |
| left-x2 | 0 | 0 |
| right-x2 | 0 | 0 |

KiCad DRC x2 summary after SES import:

| Board | Total | Errors | Warnings | Unconnected | Remaining Warning Rules |
| --- | ---: | ---: | ---: | ---: | --- |
| left-x2 | 100 | 0 | 100 | 0 | `silk_over_copper`, `text_height`, `lib_footprint_issues`, `silk_overlap`, `track_dangling`, `nonmirrored_text_on_back_layer`, `silk_edge_clearance` |
| right-x2 | 131 | 0 | 131 | 0 | `silk_over_copper`, `text_height`, `track_dangling`, `lib_footprint_issues`, `silk_overlap`, `nonmirrored_text_on_back_layer` |

X2 render previews:

- `hardware/kicad/renders/kc2_left-x2_top.png`
- `hardware/kicad/renders/kc2_left-x2_bottom.png`
- `hardware/kicad/renders/kc2_right-x2_top.png`
- `hardware/kicad/renders/kc2_right-x2_bottom.png`

The X2 boards have no KiCad DRC errors and no unrouted nets. Remaining warnings are review items. The main tradeoff is that X2 solves socket-or-solder flexibility for Choc V1 / PG1350, not for the broader X1 Choc V1/V2 hot-swap-only footprint.

## Routing Notes

- Manual lane routing was replaced by a Specctra DSN/Freerouting/SES flow.
- Freerouting v2.1.0 was used because the latest v2.2.4 jar requires a newer Java runtime than the local Java 21 installation.
- Switch footprint `Value` fields are generated as `KEY_XX`; actual legends remain as silkscreen text. This avoids Freerouting parser problems with legends such as `\`.
- Right-side `R_COL7` and `R_COL8` controller pins were swapped:
  - `R_COL7`: D21/A3
  - `R_COL8`: D20/A2
- The swap keeps the longer outer/right column on the easier fanout pin and leaves the one-key `Home` column on D20.

## Main Remaining Problems

- Remaining KiCad warnings include small silkscreen/text issues and library-footprint warnings for generated KC2 placeholder/custom footprints that are embedded in the board but not yet saved as standalone `.kicad_mod` library entries.
- `track_dangling` warnings should be visually reviewed in KiCad before fabrication output, even though KiCad reports 0 unrouted nets.
- PCB-mounted stabilizer holes are present as MX-style 2u stabilizer NPTH markers, but low-profile stabilizer compatibility still needs real-part measurement.
- The PCB outline, M2 holes, battery space, controller socket, and tact switch should be checked with a 1:1 print before ordering.

## Next Work

- Review and optionally clean warning-only DRC items.
- Update ZMK pin definitions to match the right-side `R_COL7`/`R_COL8` swap.
- Verify stabilizer footprints against the exact low-profile stabilizer parts or measured keycap/stabilizer set.
- Verify the `NW3-A06-B3` tactile switch position and USB-C cable clearance with a 1:1 mechanical print.
- Generate Gerber/drill files only after 1:1 mechanical print review.
