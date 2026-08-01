# KC2 ZMK Firmware

Requirement: CON-ARCH-005

Prerequisite: WSL2 with a default Ubuntu distribution. No Windows Python, Node.js, Git, CMake, Zephyr, or ZMK installation is required.

From Command Prompt or PowerShell, run:

```bat
.\tools\build_kc2_zmk.bat
```

The BAT entry point installs only missing Ubuntu packages, checks out the pinned ZMK `v0.3.0` release, and installs its Zephyr modules, Python packages, and SDK in the WSL user's cache. A versioned completion marker prevents those dependencies from being downloaded again on later runs. Interrupted setup can be resumed by running the same command.

Every invocation performs pristine left and right firmware builds without deleting the download cache. The distinct controller images are written to `firmware/out/kc2_left.uf2` and `firmware/out/kc2_right.uf2`.
