"""CON-ARCH-006 reuse the verified Fusion exporter for smooth-wall jobs.

Run in Fusion's Python text console with run(). All writes stay in the new
staging directory; the previous flat-seam evidence is left intact.
"""
from pathlib import Path
import sys

ROOT = Path(r'C:\Work\git\kc2')


def run():
    if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
    from tools import kc2_flat_central_native as contract
    from tools.fusion.KC2FlatCentralToF3D import KC2FlatCentralToF3D as exporter
    old_stage, old_write = contract.STAGE, exporter._write
    new_stage = Path('.codex-tmp/smooth-central-seam')
    def write(path, value):
        try: relative = path.relative_to(ROOT / old_stage)
        except ValueError: return old_write(path,value)
        return old_write(ROOT / new_stage / relative,value)
    try:
        contract.STAGE = new_stage
        exporter._write = write
        exporter._execute()
    finally:
        contract.STAGE = old_stage
        exporter._write = old_write
