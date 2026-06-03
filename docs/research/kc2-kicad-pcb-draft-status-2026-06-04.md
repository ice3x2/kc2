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
  - left half controller tab toward the right edge, recessed 14 mm from the joining edge
  - right half controller tab toward the left edge, recessed 12 mm from the joining edge
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
| left | 39 | 0 | 39 | `track_dangling`, `lib_footprint_issues`, `text_height`, `silk_over_copper`, `silk_overlap`, `nonmirrored_text_on_back_layer` |
| right | 57 | 0 | 57 | `track_dangling`, `lib_footprint_issues`, `text_height`, `silk_over_copper`, `silk_overlap`, `nonmirrored_text_on_back_layer` |

The boards have no KiCad DRC errors and no unrouted nets in the current draft. Remaining warnings are review items rather than hard connectivity/clearance blockers.

## Routing Notes

- Manual lane routing was replaced by a Specctra DSN/Freerouting/SES flow.
- Freerouting v2.1.0 was used because the latest v2.2.4 jar requires a newer Java runtime than the local Java 21 installation.
- Switch footprint `Value` fields are generated as `KEY_XX`; actual legends remain as silkscreen text. This avoids Freerouting parser problems with legends such as `\`.
- Right-side `R_COL7` and `R_COL8` controller pins were swapped:
  - `R_COL7`: D21/A3
  - `R_COL8`: D20/A2
- The swap keeps the longer outer/right column on the easier fanout pin and leaves the one-key `Home` column on D20.

## Main Remaining Problems

- Remaining KiCad warnings include small silkscreen/text issues and library-footprint warnings from the third-party switch footprint.
- `track_dangling` warnings should be visually reviewed in KiCad before fabrication output, even though KiCad reports 0 unrouted nets.
- PCB-mounted stabilizer holes are present as MX-style 2u stabilizer NPTH markers, but low-profile stabilizer compatibility still needs real-part measurement.
- The PCB outline, M2 holes, battery space, controller socket, and tact switch should be checked with a 1:1 print before ordering.

## Next Work

- Review and optionally clean warning-only DRC items.
- Update ZMK pin definitions to match the right-side `R_COL7`/`R_COL8` swap.
- Verify stabilizer footprints against the exact low-profile stabilizer parts or measured keycap/stabilizer set.
- Verify the `NW3-A06-B3` tactile switch position and USB-C cable clearance with a 1:1 mechanical print.
- Generate Gerber/drill files only after 1:1 mechanical print review.
