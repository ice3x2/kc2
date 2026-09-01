# KC2 X3 V2 ZMK shield

Requirement: `CON-ARCH-004` AC-5 and AC-7.

This isolated shield is the fixed 70-key v5 variant: 31 keys on `kc2_x3_v2_left` and 39 keys on `kc2_x3_v2_right`. It does not replace the verified 77-key `kc2_left` / `kc2_right` shield.

The default layer follows the physical switch-reference order recorded in `kc2_x3_v2.keymap`. On the left, the former Win position is `Fn`, the former standalone Fn switch is removed, and there is no standalone Win key. Pressing left Fn and left Alt within the 50 ms combo timeout emits `LGUI` on every layer and releases it when either constituent key is first released. An ordinary left Fn press remains the momentary layer-1 key, including its inherited layer-2 behavior while layer 1 is active. On the right, `Fn` is immediately right of `Up` and the bottom row has no `Fn`. `Home`, `PgUp`, and `PgDn` are absent from the default layer.

The PCB supports mutually exclusive Choc V2 bottom-socket or MX direct-solder assembly. Choc V1, Choc V2 direct solder, and MX hot-swap are unsupported. The compact nice!nano v2 carrier uses 15.24 mm socket-row spacing, no carrier battery nets, and direct battery-lead soldering to the nice!nano B+/B- pads.

The active V2 PCB uses exactly 70 Diodes Incorporated `1N4148W-13-F`
SOD-123 matrix diodes, locked to datasheet `DS30086 Rev. 31-2`. This package
change preserves the existing `col2row` electrical contract: B.Cu pad 1 is the
cathode/row and pad 2 is the anode/per-key switch net. Because the bottom
assembly view is mirrored, the cathode band must be checked against pad 1, not
an assumed screen-left or screen-right direction.

There is no firmware source or UF2 change for the 1N4148W PCB geometry change.
The recorded build remains zero-wait (`0 us` before input reads and `0 us`
between driven columns). Scan-delay changes are prohibited until a populated
physical coupon passes 3.0 V and 3.3 V maximum same-row and same-column stress
tests. That electrical/physical test is pending and the PCB remains not
orderable; the unchanged UF2 hashes below do not claim 1N4148W physical
qualification.

## Reproducible WSL build

The verified toolchain is ZMK v0.3.0 at commit `edf5c0814fd3ea202e43aad2d68fd32e882a518c`, Zephyr SDK 0.16.9, and the `nice_nano_v2` board. From PowerShell at the repository root, run the existing pinned bootstrap once if its WSL cache is not already installed:

```powershell
.\tools\build_kc2_zmk.bat
wsl.exe
```

The bootstrap also builds the preserved 77-key target, but does not alter this V2 shield. Then run the following commands in the WSL Ubuntu shell. Change `KC2_V2_REPO` only when the repository is checked out elsewhere.

```bash
set -euo pipefail

KC2_V2_REPO=/mnt/c/Work/git/kc2
KC2_V2_ZMK="$HOME/.cache/kc2-zmk"
KC2_V2_EXPECTED_COMMIT=edf5c0814fd3ea202e43aad2d68fd32e882a518c
KC2_V2_SDK="$HOME/zephyr-sdk-0.16.9"

test "$(git -C "$KC2_V2_ZMK" rev-parse HEAD)" = "$KC2_V2_EXPECTED_COMMIT"
source "$KC2_V2_ZMK/.venv/bin/activate"
export ZEPHYR_SDK_INSTALL_DIR="$KC2_V2_SDK"
mkdir -p "$KC2_V2_REPO/firmware/out"
cd "$KC2_V2_ZMK/app"

west build -d "$KC2_V2_REPO/firmware/build/kc2_x3_v2_left" -p always -b nice_nano_v2 -- \
  -DSHIELD=kc2_x3_v2_left \
  -DZMK_EXTRA_MODULES="$KC2_V2_REPO/firmware/kc2_zmk"
install -m 0644 \
  "$KC2_V2_REPO/firmware/build/kc2_x3_v2_left/zephyr/zmk.uf2" \
  "$KC2_V2_REPO/firmware/out/kc2_x3_v2_left.uf2"

west build -d "$KC2_V2_REPO/firmware/build/kc2_x3_v2_right" -p always -b nice_nano_v2 -- \
  -DSHIELD=kc2_x3_v2_right \
  -DZMK_EXTRA_MODULES="$KC2_V2_REPO/firmware/kc2_zmk"
install -m 0644 \
  "$KC2_V2_REPO/firmware/build/kc2_x3_v2_right/zephyr/zmk.uf2" \
  "$KC2_V2_REPO/firmware/out/kc2_x3_v2_right.uf2"

test -s "$KC2_V2_REPO/firmware/out/kc2_x3_v2_left.uf2"
test -s "$KC2_V2_REPO/firmware/out/kc2_x3_v2_right.uf2"
sha256sum \
  "$KC2_V2_REPO/firmware/out/kc2_x3_v2_left.uf2" \
  "$KC2_V2_REPO/firmware/out/kc2_x3_v2_right.uf2"
```

Left and right builds deliberately use separate build directories and output filenames so a peripheral image cannot overwrite the central image.

The 2026-08-22 v5 verification build produced:

- left: `423424 bytes`, SHA-256 `86c9a777c29d7f1c6f178d8df8aa4f5ecf8e8f75b7fc3daa1ca4842e761c2561`;
- right: `340992 bytes`, SHA-256 `92c8dd1175de2c19505d3ca3487bcc8baa1d03a581c6de13c191ca63743e9b35`.

`kc2_x3_v2_build_evidence.json` binds those recorded results to the pinned
toolchain, both shield names, and the SHA-256 of every current build input. It
also hashes the two non-build metadata inputs used by the focused verifier.
`tools.verify_kc2_x3_v2_zmk_firmware` reports
`manifest_provenance_verified=true` only when every recorded source digest and
all pinned metadata still match, and separately reports
`hardware_compatibility_verified=true` only when the 1N4148W polarity, unchanged
matrix contract, unchanged recorded zero-wait settings, and pending physical
stress gate match. The UF2 files under `firmware/out` are ignored
build products: in a fresh clone they may be ignored and absent without
invalidating source provenance. When either local UF2 is present, the verifier
separately requires its recorded byte size, SHA-256, block count, and UF2 magic
on every 512-byte block; absence is reported as absent, never as artifact
verification.

These hashes are verification evidence for the pinned sources in this revision,
not permanent release identifiers; rebuild and compare again after any
firmware-source change.
