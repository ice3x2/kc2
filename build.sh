#!/usr/bin/env bash
# CON-ARCH-005 AC-10: clean and rebuild the KC2 left/right firmware.
#
# This is a thin POSIX entry point. The pristine build itself is delegated to
# tools/build_kc2_zmk_wsl.sh so that no build logic is duplicated here.
#
# Usage: ./build.sh
#
# Environment overrides (mainly for tests):
#   KC2_ZMK_BOOTSTRAP_SCRIPT  path to the shared bootstrap/build script

set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BOOTSTRAP_SCRIPT="${KC2_ZMK_BOOTSTRAP_SCRIPT:-$REPO_ROOT/tools/build_kc2_zmk_wsl.sh}"
BUILD_DIR="$REPO_ROOT/firmware/build"
OUTPUT_DIR="$REPO_ROOT/firmware/out"

if [ ! -f "$BOOTSTRAP_SCRIPT" ]; then
    echo "ERROR: Missing build script: $BOOTSTRAP_SCRIPT" >&2
    echo "Run ./setup.ubuntu.sh first." >&2
    exit 1
fi

echo "[1/3] Removing previously built firmware..."
rm -rf "$BUILD_DIR" "$OUTPUT_DIR"

echo "[2/3] Building kc2_left and kc2_right..."
bash "$BOOTSTRAP_SCRIPT" --build "$REPO_ROOT"

echo "[3/3] Verifying build outputs..."
for image in kc2_left.uf2 kc2_right.uf2; do
    if [ ! -s "$OUTPUT_DIR/$image" ]; then
        echo "ERROR: The build did not produce $OUTPUT_DIR/$image" >&2
        exit 1
    fi
done

echo
echo "Build complete."
echo "Firmware output directory: $OUTPUT_DIR"
for image in kc2_left.uf2 kc2_right.uf2; do
    echo "  - $OUTPUT_DIR/$image"
done
