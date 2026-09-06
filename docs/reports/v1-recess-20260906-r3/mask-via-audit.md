# Actual mask/via audit

Requirements: `CON-ARCH-004`, `CON-ARCH-006`, `OPS-ARCH-007`.

[Reproducible read-only driver](audit-mask-vias.py) parses all1558 flashes in the four actual r3 mask Gerbers, including rotated capsule and rounded-rectangle macro primitives. It compares these against all86 current physical vias on both layers. It verifies macro definitions and refuses unsupported drawing primitives, rather than substituting bounding boxes. Source files are byte-hashed before and after the run.

[Machine evidence](mask-via-support-replay-audit.json) reports exactly three physical same-net exposure exceptions:

| Side | Via center mm | Pad/net | Exposed layers |
|---|---|---|---|
| Left | 136.5000,59.4000 | U1/D5,L_COL1 | F.Mask,B.Mask |
| Right | 73.5000,59.5000 | U1/D18,R_COL5 | F.Mask,B.Mask |
| Right | 90.7545,127.9170 | D27/1,R_ROW3 | B.Mask |

There are no new exposures from the diagonal MX pads or locator revision. Other via copper discs are fully outside all mask-opening polygons: left26 on each face, right58 front/57 back. This is nominal Gerber geometry, not a manufacturing mask-registration guarantee. Existing exposed-via solder-wicking risk remains; do not claim every via is tented.

The same fresh extraction verifies both route replays, all70 original housing-support copper keepouts and all70 local NPTH/MX-copper gaps (minimum0.419502 mm). Original support coordinates are explicitly an unchanged-network compatibility check, not a replacement for the independently regenerated housing CAD review.

Permanent proof files are `current-board-extraction.json`, `left-canonical-drc.json`, `right-canonical-drc.json`, `original-support-keepouts.json` and the machine evidence above. Their sources/hashes are recorded in the machine evidence; the sealed release need not bind temporary `.codex-tmp` files. Hardware is never modified by this driver.
