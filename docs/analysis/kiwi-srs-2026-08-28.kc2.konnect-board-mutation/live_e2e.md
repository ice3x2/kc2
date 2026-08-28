# OPS-ARCH-004 installed-runtime evidence

Date: 2026-08-28

| Check | Result |
| --- | --- |
| KiCad | 10.0.3 |
| Installed runtime | `C:\Users\beom\Documents\KiCad\10.0\3rdparty\plugins\com.github.mixelpixx.konnect\bin\konnect.exe` |
| Reversible-E2E runtime SHA-256 | `DB1F3310C987CB090E1919211E3AFC33A74CD78995ADA9402462A5B27A8CA91C` |
| Current installed runtime SHA-256 | `DF9A361C5AB7C28F127C35F3C34B1A748698209D5F5F4C09292B4F5FAE234F1A` |
| Previous-runtime backup | `C:\Users\beom\Documents\KiCad\10.0\3rdparty\plugins\com.github.mixelpixx.konnect\bin\konnect.exe.pre-ops-arch-004-20260828.bak` |
| Previous-runtime SHA-256 | `DB6F49C9279B59C182EAD5ACD989197EEE6F135F5CD164A9CB72D90B40B30FDE` |
| Registered tools | 210 plus 6 meta-tools |
| Toolset counts | `pcb_components=20`, `pcb_routing=14`, `pcb_board=13` |
| Installed schemas | `edit_placed_pad_net`, `list_board_graphics`, `delete_board_items` |
| Rust regression | `konnect-ipc`: 136 passed, 4 ignored; `konnect-core`: 791 passed; `konnect`: 70 passed, 4 ignored |
| Static checks | Clippy `-D warnings`, format, and diff checks passed |

## Reversible KiCad IPC test

Board: `C:\Work\git\_Snoworca\kc2\hardware\kicad\draft\x3-v2\kc2_left-x3-v2\kc2_left-x3-v2.kicad_pcb`

| Sequence | Result |
| --- | --- |
| Pre-test exact `B.Fab` text query for `OPS-ARCH-004-E2E` | 0 items |
| Edit `SW_RST1` pad 1 from `RST` to existing `GND` | Success; 1 matched pad |
| Restore `SW_RST1` pad 1 from `GND` to `RST` | Success; 1 matched pad |
| Create `B.Fab` text `OPS-ARCH-004-E2E` | Success via IPC |
| Exact-text query | 1 item, UUID `214a45e1-7856-4e63-bb58-42615d540d00` |
| Delete captured UUID | Success; 1 item deleted |
| Post-test exact-text query | 0 items |
| Post-test pad readback | `SW_RST1.1=RST`, `SW_RST1.2=GND` |
| Pre-test saved-board SHA-256 | `097B32F09811939195E21297C038CC5ED09036E51CB3DBC4938E758FF2C55D7F` |
| Post-test saved-board SHA-256 | `097B32F09811939195E21297C038CC5ED09036E51CB3DBC4938E758FF2C55D7F` |

The reversible test used only installed Konnect MCP operations for board mutations. The sentinel was deleted rather than recreated, and the saved board is byte-identical to the pre-test snapshot. The current installed binary is a later regression-tested superset that adds OPS-ARCH-005 property visibility; its three OPS-ARCH-004 schemas were re-inspected after installation.
