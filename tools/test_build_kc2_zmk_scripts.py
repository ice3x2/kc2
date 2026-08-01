"""Contract tests for the dependency-free CON-ARCH-005 Windows build entry point."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WindowsEntryPointTests(unittest.TestCase):
    def test_bat_requires_only_wsl_and_runs_bootstrap_as_root(self) -> None:
        source = (ROOT / "tools" / "build_kc2_zmk.bat").read_text(encoding="ascii")

        self.assertIn("where wsl.exe", source)
        self.assertIn("wsl.exe -u root", source)
        self.assertIn("build_kc2_zmk_wsl.sh", source)
        self.assertNotIn("node ", source.lower())


class WslBootstrapTests(unittest.TestCase):
    def test_pins_downloads_and_reuses_completed_bootstrap(self) -> None:
        source = (ROOT / "tools" / "build_kc2_zmk_wsl.sh").read_text(encoding="ascii")

        self.assertIn('ZMK_REVISION="v0.3.0"', source)
        self.assertIn('ZEPHYR_SDK_VERSION="0.16.9"', source)
        self.assertIn('BOOTSTRAP_MARKER="$ZMK_DIR/.kc2-bootstrap-$ZMK_REVISION-sdk-$ZEPHYR_SDK_VERSION-complete"', source)
        self.assertIn('if [ ! -f "$BOOTSTRAP_MARKER" ]; then', source)
        self.assertIn("west update --narrow", source)
        self.assertIn('pip" install -r "$ZMK_DIR/zephyr/scripts/requirements-base.txt"', source)
        self.assertIn('"$SDK_DIR/setup.sh" -t arm-zephyr-eabi -c', source)
        self.assertNotIn("west packages", source)
        self.assertNotIn("west sdk", source)
        self.assertIn('touch "$BOOTSTRAP_MARKER"', source)
        self.assertIn('west build -d "$BUILD_DIR/left" -p always', source)
        self.assertIn('west build -d "$BUILD_DIR/right" -p always', source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
