#!/usr/bin/env bash

set -euo pipefail

ZMK_REVISION="v0.3.0"
ZMK_COMMIT="edf5c0814fd3ea202e43aad2d68fd32e882a518c"
ZEPHYR_SDK_VERSION="0.16.9"

install_dependencies() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "Dependency installation must run as WSL root." >&2
        return 1
    fi
    if ! command -v apt-get >/dev/null 2>&1; then
        echo "This bootstrap requires an Ubuntu or Debian WSL distribution with apt-get." >&2
        return 1
    fi

    local packages=(
        git cmake ninja-build gperf ccache device-tree-compiler
        python3 python3-dev python3-pip python3-venv
        wget xz-utils file tar make gcc g++ libmagic1
    )
    local missing=()
    local package
    for package in "${packages[@]}"; do
        if ! dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q '^install ok installed$'; then
            missing+=("$package")
        fi
    done

    if [ "${#missing[@]}" -eq 0 ]; then
        echo "WSL build prerequisites are already installed; no package download is needed."
        return
    fi

    echo "Installing missing WSL packages: ${missing[*]}"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y --no-install-recommends "${missing[@]}"
}

install_zephyr_sdk() {
    local cache_base=$1
    local SDK_DIR=$2
    local host_arch
    local archive_name
    local archive_path
    local archive_sha256
    local download_url

    if [ -x "$SDK_DIR/arm-zephyr-eabi/bin/arm-zephyr-eabi-gcc" ]; then
        echo "Reusing Zephyr SDK $ZEPHYR_SDK_VERSION ARM toolchain at $SDK_DIR"
        return
    fi

    host_arch=$(uname -m)
    case "$host_arch" in
        aarch64)
            archive_sha256="e6b1f22a9727c4e5322676d9c18d95f7bd881218795f9e08ca4ef25e8f5d1551"
            ;;
        x86_64)
            archive_sha256="b433f19b334cd15f4d7696a958dda214a7737cf41432900d076adce4253782a5"
            ;;
        *)
            echo "Unsupported WSL architecture for Zephyr SDK: $host_arch" >&2
            return 1
            ;;
    esac

    archive_name="zephyr-sdk-${ZEPHYR_SDK_VERSION}_linux-${host_arch}_minimal.tar.xz"
    archive_path="$cache_base/$archive_name"
    download_url="https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${ZEPHYR_SDK_VERSION}/$archive_name"

    if [ ! -f "$archive_path" ]; then
        echo "Downloading Zephyr SDK $ZEPHYR_SDK_VERSION minimal bundle for $host_arch once"
        wget --continue -O "$archive_path.part" "$download_url"
        if ! printf '%s  %s\n' "$archive_sha256" "$archive_path.part" | sha256sum --check --status; then
            rm -f "$archive_path.part"
            echo "Zephyr SDK archive checksum verification failed." >&2
            return 1
        fi
        mv "$archive_path.part" "$archive_path"
    elif ! printf '%s  %s\n' "$archive_sha256" "$archive_path" | sha256sum --check --status; then
        echo "Cached Zephyr SDK archive checksum is invalid: $archive_path" >&2
        return 1
    else
        echo "Reusing downloaded Zephyr SDK archive at $archive_path"
    fi

    tar -xf "$archive_path" -C "$HOME"
    "$SDK_DIR/setup.sh" -t arm-zephyr-eabi -c
    test -x "$SDK_DIR/arm-zephyr-eabi/bin/arm-zephyr-eabi-gcc"
}

# Shared workspace paths, resolved by bootstrap_workspace for every mode.
KC2_REPO_ROOT=""
MODULE_DIR=""
BUILD_DIR=""
OUTPUT_DIR=""
CACHE_BASE=""
ZMK_DIR=""
SDK_DIR=""
BOOTSTRAP_MARKER=""

# Prepare the pinned ZMK workspace, Zephyr modules, Python tools, and SDK.
# Downloads happen only once; a completed cache is reused as-is.
bootstrap_workspace() {
    if [ "$#" -ne 1 ]; then
        echo "Usage: $0 --setup|--build WSL_REPOSITORY_PATH" >&2
        return 2
    fi

    KC2_REPO_ROOT=$1
    MODULE_DIR="$KC2_REPO_ROOT/firmware/kc2_zmk"
    BUILD_DIR="$KC2_REPO_ROOT/firmware/build"
    OUTPUT_DIR="$KC2_REPO_ROOT/firmware/out"
    CACHE_BASE="${XDG_CACHE_HOME:-$HOME/.cache}"
    ZMK_DIR="$CACHE_BASE/kc2-zmk"
    SDK_DIR="$HOME/zephyr-sdk-$ZEPHYR_SDK_VERSION"
    BOOTSTRAP_MARKER="$ZMK_DIR/.kc2-bootstrap-$ZMK_REVISION-sdk-$ZEPHYR_SDK_VERSION-complete"
    local actual_commit

    test -f "$MODULE_DIR/zephyr/module.yml"
    mkdir -p "$CACHE_BASE"

    if [ ! -d "$ZMK_DIR/.git" ]; then
        echo "Downloading pinned ZMK $ZMK_REVISION once into $ZMK_DIR"
        git clone --branch "$ZMK_REVISION" --depth 1 https://github.com/zmkfirmware/zmk.git "$ZMK_DIR"
    else
        echo "Reusing downloaded ZMK checkout at $ZMK_DIR"
    fi

    actual_commit=$(git -C "$ZMK_DIR" rev-parse HEAD)
    if [ "$actual_commit" != "$ZMK_COMMIT" ]; then
        echo "Cached ZMK commit is $actual_commit, expected $ZMK_COMMIT." >&2
        echo "Move the cache aside and rerun: $ZMK_DIR" >&2
        return 1
    fi
    if ! git -C "$ZMK_DIR" diff --quiet || ! git -C "$ZMK_DIR" diff --cached --quiet; then
        echo "Cached ZMK checkout contains local modifications: $ZMK_DIR" >&2
        return 1
    fi

    if [ ! -x "$ZMK_DIR/.venv/bin/west" ]; then
        echo "Installing the pinned workspace Python tools once"
        python3 -m venv "$ZMK_DIR/.venv"
        "$ZMK_DIR/.venv/bin/pip" install --upgrade pip west
    fi

    source "$ZMK_DIR/.venv/bin/activate"
    cd "$ZMK_DIR"
    if [ ! -f "$BOOTSTRAP_MARKER" ]; then
        echo "Downloading Zephyr modules, Python packages, and SDK once"
        if [ ! -d .west ]; then
            west init -l app
        fi
        west update --narrow
        west zephyr-export
        "$ZMK_DIR/.venv/bin/pip" install -r "$ZMK_DIR/zephyr/scripts/requirements-base.txt"
        install_zephyr_sdk "$CACHE_BASE" "$SDK_DIR"
        touch "$BOOTSTRAP_MARKER"
    else
        echo "Reusing completed ZMK/Zephyr/SDK cache; no dependency download is needed."
    fi

    export ZEPHYR_SDK_INSTALL_DIR="$SDK_DIR"
}

setup_workspace() {
    bootstrap_workspace "$@"
    echo "Zephyr workspace ready: $ZMK_DIR"
    echo "Zephyr SDK ready: $SDK_DIR"
}

build_firmware() {
    bootstrap_workspace "$@"
    mkdir -p "$BUILD_DIR" "$OUTPUT_DIR"

    cd "$ZMK_DIR/app"
    echo "Building kc2_left"
    west build -d "$BUILD_DIR/left" -p always -b nice_nano_v2 -- -DSHIELD=kc2_left -DZMK_EXTRA_MODULES="$MODULE_DIR"
    install -m 0644 "$BUILD_DIR/left/zephyr/zmk.uf2" "$OUTPUT_DIR/kc2_left.uf2"

    echo "Building kc2_right"
    west build -d "$BUILD_DIR/right" -p always -b nice_nano_v2 -- -DSHIELD=kc2_right -DZMK_EXTRA_MODULES="$MODULE_DIR"
    install -m 0644 "$BUILD_DIR/right/zephyr/zmk.uf2" "$OUTPUT_DIR/kc2_right.uf2"

    test -s "$OUTPUT_DIR/kc2_left.uf2"
    test -s "$OUTPUT_DIR/kc2_right.uf2"
    if cmp -s "$OUTPUT_DIR/kc2_left.uf2" "$OUTPUT_DIR/kc2_right.uf2"; then
        echo "Left and right UF2 files are unexpectedly identical." >&2
        return 1
    fi
    sha256sum "$OUTPUT_DIR/kc2_left.uf2" "$OUTPUT_DIR/kc2_right.uf2"
}

case "${1:-}" in
    --install-dependencies)
        install_dependencies
        ;;
    --setup)
        shift
        setup_workspace "$@"
        ;;
    --build)
        shift
        build_firmware "$@"
        ;;
    *)
        echo "Usage: $0 --install-dependencies | --setup REPOSITORY_PATH | --build REPOSITORY_PATH" >&2
        exit 2
        ;;
esac
