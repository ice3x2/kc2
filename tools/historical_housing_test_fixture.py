"""CON-ARCH-006 / OPS-ARCH-006 historical r5 unit-test inputs only.

Never imported by a production verifier. No fallback to current canonical CAD:
new enclosed outputs require the enclosure audit and independent review.
"""
import json
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'cc854a3e0e0f25ab3d63e2916cb4b99a487b6536'


def historical_bytes(relative):
    relative = str(relative).replace('\\', '/')
    if relative.startswith('hardware/case/'):
        relative = 'hardware/MODELS/' + relative[len('hardware/case/'):]
    elif relative.startswith('hardware/kicad/'):
        relative = 'hardware/PCB/' + relative[len('hardware/kicad/'):]
    if Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('Historical fixture requires a repository-relative path')
    return subprocess.check_output(['git', 'show', f'{BASELINE}:{relative}'], cwd=ROOT)


def historical_json(name):
    """Read immutable model metadata; missing baseline objects fail the test."""
    return json.loads(historical_bytes('hardware/MODELS/' + name))


@contextmanager
def historical_artifact_root(paths):
    """Materialize only requested Git blobs outside canonical artifact paths."""
    with tempfile.TemporaryDirectory(prefix='kc2-historical-r5-test-') as directory:
        root = Path(directory)
        for relative in paths:
            data = historical_bytes(relative)
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        yield root
