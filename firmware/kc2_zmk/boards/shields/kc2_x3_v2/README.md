# KC2 X3 V2 ZMK shield

Requirement: `CON-ARCH-004` AC-5 and AC-7.

This isolated shield is the fixed 71-key v4 variant: 32 keys on `kc2_x3_v2_left` and 39 keys on `kc2_x3_v2_right`. It does not replace the verified 77-key `kc2_left` / `kc2_right` shield.

The default layer follows the physical switch-reference order recorded in `kc2_x3_v2.keymap`. `Fn` is immediately right of `Up`; the right bottom row has no `Fn`. `Home`, `PgUp`, and `PgDn` are absent from the default layer.

The PCB supports mutually exclusive Choc V2 bottom-socket or MX direct-solder assembly. Choc V1, Choc V2 direct solder, and MX hot-swap are unsupported. The compact nice!nano v2 carrier uses 15.24 mm socket-row spacing, no carrier battery nets, and direct battery-lead soldering to the nice!nano B+/B- pads.

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
