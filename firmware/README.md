# KC2 ZMK Firmware

Requirement: CON-ARCH-005

Prerequisite: WSL2 with a default Ubuntu distribution. No Windows Python, Node.js, Git, CMake, Zephyr, or ZMK installation is required.

## Ubuntu shell (including WSL)

From the repository root, run setup once and build whenever the firmware changes:

```bash
./setup.ubuntu.sh    # installs the Zephyr/ZMK build environment only
./build.sh           # removes previous outputs, builds, and prints the output directory
```

`setup.ubuntu.sh` elevates with `sudo` for the Ubuntu packages, then downloads the pinned ZMK `v0.3.0` sources, Zephyr modules, Python packages, and Zephyr SDK into the user's cache. It builds no firmware and is safe to rerun; a completed cache is reused instead of downloaded again. It targets Ubuntu/Debian only — macOS and other distributions are not supported yet.

`build.sh` deletes `firmware/build` and `firmware/out`, performs the pristine left and right builds, and prints the absolute path of the directory holding the resulting UF2 files. It bootstraps the workspace automatically if `setup.ubuntu.sh` has not been run yet.

Both scripts delegate to `tools/build_kc2_zmk_wsl.sh`, which owns all pinned revisions and cache logic.

## Windows

From Command Prompt or PowerShell, run:

```bat
.\tools\build_kc2_zmk.bat
```

The BAT entry point installs only missing Ubuntu packages, checks out the pinned ZMK `v0.3.0` release, and installs its Zephyr modules, Python packages, and SDK in the WSL user's cache. A versioned completion marker prevents those dependencies from being downloaded again on later runs. Interrupted setup can be resumed by running the same command.

Every invocation performs pristine left and right firmware builds without deleting the download cache. The distinct controller images are written to `firmware/out/kc2_left.uf2` and `firmware/out/kc2_right.uf2`.

## Controller LED and software power

- While the active host Bluetooth profile is open for registration, the left-central nice!nano v2 blue LED blinks rapidly. It stops and remains off after registration and connection.
- On Fn2, left D31 and the right D9/Delete position invoke software power-off. Both controller blue LEDs flash once before the halves enter soft-off.
- To wake after software power-off, press a key on each half.
