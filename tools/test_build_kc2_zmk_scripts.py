"""Contract tests for the dependency-free CON-ARCH-005 build entry points."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]

STUB_BOOTSTRAP = """#!/usr/bin/env bash
set -euo pipefail

printf '%s\\n' "$*" >>"$KC2_STUB_LOG"

if [ "${1:-}" = "--build" ]; then
    mkdir -p "$2/firmware/out"
    printf 'left' >"$2/firmware/out/kc2_left.uf2"
    printf 'right' >"$2/firmware/out/kc2_right.uf2"
fi
"""


def _make_stub_repository(repo: Path, *entry_points: str) -> Path:
    """Copy the given root entry points plus a recording bootstrap stub into repo."""
    (repo / "tools").mkdir(parents=True, exist_ok=True)
    (repo / "firmware" / "kc2_zmk" / "zephyr").mkdir(parents=True, exist_ok=True)
    (repo / "firmware" / "kc2_zmk" / "zephyr" / "module.yml").write_text(
        "name: zmk-keyboard-kc2\n", encoding="utf-8"
    )

    for entry_point in entry_points:
        shutil.copy2(ROOT / entry_point, repo / entry_point)

    stub = repo / "tools" / "stub_bootstrap.sh"
    stub.write_text(STUB_BOOTSTRAP, encoding="utf-8")
    stub.chmod(0o755)
    return stub


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

    def test_exposes_a_setup_mode_that_reuses_the_shared_bootstrap(self) -> None:
        """AC-9: the environment bootstrap is callable without building firmware."""
        source = (ROOT / "tools" / "build_kc2_zmk_wsl.sh").read_text(encoding="ascii")

        self.assertIn("--setup)", source)
        self.assertIn("bootstrap_workspace", source)

    def test_usage_documents_every_mode(self) -> None:
        """AC-9: an unknown mode reports install/setup/build usage and fails."""
        completed = subprocess.run(
            ["bash", str(ROOT / "tools" / "build_kc2_zmk_wsl.sh")],
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("--install-dependencies", completed.stderr)
        self.assertIn("--setup", completed.stderr)
        self.assertIn("--build", completed.stderr)


class PosixSetupEntryPointTests(unittest.TestCase):
    """AC-9: repository-root setup.ubuntu.sh prepares the build environment only."""

    def test_setup_script_is_executable(self) -> None:
        script = ROOT / "setup.ubuntu.sh"

        self.assertTrue(script.is_file(), "setup.ubuntu.sh must exist at the repository root")
        self.assertTrue(os.access(script, os.X_OK), "setup.ubuntu.sh must be executable")

    def test_setup_script_reuses_bootstrap_without_duplicating_pins(self) -> None:
        source = (ROOT / "setup.ubuntu.sh").read_text(encoding="utf-8")

        self.assertIn("tools/build_kc2_zmk_wsl.sh", source)
        self.assertNotIn("git clone", source)
        self.assertNotIn("ZEPHYR_SDK_VERSION=", source)
        self.assertNotIn("west build", source)

    def test_setup_installs_dependencies_then_bootstraps_and_never_builds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            stub = _make_stub_repository(repo, "setup.ubuntu.sh")
            log = repo / "stub.log"

            completed = subprocess.run(
                ["bash", str(repo / "setup.ubuntu.sh")],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "KC2_ZMK_BOOTSTRAP_SCRIPT": str(stub),
                    "KC2_STUB_LOG": str(log),
                    "KC2_SUDO": "env",
                },
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            invocations = log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(invocations), 2, invocations)
            self.assertEqual(invocations[0], "--install-dependencies")
            self.assertTrue(invocations[1].startswith("--setup"), invocations[1])
            self.assertNotIn("--build", "\n".join(invocations))
            self.assertFalse((repo / "firmware" / "out" / "kc2_left.uf2").exists())


class PosixBuildEntryPointTests(unittest.TestCase):
    """AC-10: repository-root build.sh cleans, builds, and prints the output path."""

    def test_build_script_is_executable(self) -> None:
        script = ROOT / "build.sh"

        self.assertTrue(script.is_file(), "build.sh must exist at the repository root")
        self.assertTrue(os.access(script, os.X_OK), "build.sh must be executable")

    def test_build_script_reuses_bootstrap_without_duplicating_west_calls(self) -> None:
        source = (ROOT / "build.sh").read_text(encoding="utf-8")

        self.assertIn("tools/build_kc2_zmk_wsl.sh", source)
        self.assertIn("--build", source)
        self.assertNotIn("west build", source)
        self.assertNotIn("git clone", source)

    def test_build_removes_previous_artifacts_and_prints_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            stub = _make_stub_repository(repo, "build.sh")
            log = repo / "stub.log"

            stale_build = repo / "firmware" / "build" / "left" / "stale.o"
            stale_build.parent.mkdir(parents=True)
            stale_build.write_text("stale", encoding="utf-8")
            stale_output = repo / "firmware" / "out" / "kc2_obsolete.uf2"
            stale_output.parent.mkdir(parents=True)
            stale_output.write_text("stale", encoding="utf-8")

            completed = subprocess.run(
                ["bash", str(repo / "build.sh")],
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "KC2_ZMK_BOOTSTRAP_SCRIPT": str(stub),
                    "KC2_STUB_LOG": str(log),
                },
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse(stale_build.exists(), "previous build tree must be removed")
            self.assertFalse(stale_output.exists(), "previous UF2 outputs must be removed")

            invocations = log.read_text(encoding="utf-8").splitlines()
            self.assertEqual(invocations, [f"--build {repo}"])

            output_dir = repo / "firmware" / "out"
            self.assertIn(str(output_dir), completed.stdout)
            self.assertIn("kc2_left.uf2", completed.stdout)
            self.assertIn("kc2_right.uf2", completed.stdout)

    def test_build_fails_when_the_delegated_build_produces_no_firmware(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp).resolve()
            _make_stub_repository(repo, "build.sh")
            silent_stub = repo / "tools" / "silent_stub.sh"
            silent_stub.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            silent_stub.chmod(0o755)

            completed = subprocess.run(
                ["bash", str(repo / "build.sh")],
                capture_output=True,
                text=True,
                env={**os.environ, "KC2_ZMK_BOOTSTRAP_SCRIPT": str(silent_stub)},
            )

            self.assertNotEqual(completed.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
