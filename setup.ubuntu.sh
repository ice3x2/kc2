#!/usr/bin/env bash
# CON-ARCH-005 AC-9: install the Zephyr/ZMK build environment for KC2 firmware
# on Ubuntu/Debian, including WSL2. Other platforms are not supported yet.
#
# This is a thin entry point. All pinned revisions, download, and cache logic
# live in tools/build_kc2_zmk_wsl.sh, which is reused as-is so that the Windows
# BAT entry point and this script always bootstrap the same workspace.
#
# Usage: ./setup.ubuntu.sh
#
# Environment overrides (mainly for tests and non-sudo hosts):
#   KC2_ZMK_BOOTSTRAP_SCRIPT  path to the shared bootstrap script
#   KC2_SUDO                  privilege-elevation command (default: sudo)

set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BOOTSTRAP_SCRIPT="${KC2_ZMK_BOOTSTRAP_SCRIPT:-$REPO_ROOT/tools/build_kc2_zmk_wsl.sh}"

if [ ! -f "$BOOTSTRAP_SCRIPT" ]; then
    echo "ERROR: Missing bootstrap script: $BOOTSTRAP_SCRIPT" >&2
    exit 1
fi

echo "[1/2] Installing Linux/WSL build prerequisites..."
if [ "$(id -u)" -eq 0 ]; then
    bash "$BOOTSTRAP_SCRIPT" --install-dependencies
else
    SUDO="${KC2_SUDO:-sudo}"
    if ! command -v "${SUDO%% *}" >/dev/null 2>&1; then
        echo "ERROR: Package installation needs root. Install '${SUDO%% *}' or rerun as root." >&2
        exit 1
    fi
    $SUDO bash "$BOOTSTRAP_SCRIPT" --install-dependencies
fi

echo "[2/2] Preparing the pinned Zephyr/ZMK workspace and toolchain..."
bash "$BOOTSTRAP_SCRIPT" --setup "$REPO_ROOT"

echo
echo "Setup complete. Run ./build.sh to build the KC2 firmware."
