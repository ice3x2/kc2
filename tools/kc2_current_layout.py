"""OPS-ARCH-006/007: restore compatibility paths without duplicate active files.

Run with --apply after cloning. Default is a read-only plan. No design bytes,
release manifests or existing conflicting paths are overwritten.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
ALIASES={
    'hardware/kicad/kc2_left':'hardware/PCB/kc2_left',
    'hardware/kicad/kc2_right':'hardware/PCB/kc2_right',
    'hardware/case':'hardware/MODELS',
    'hardware/kicad/first_order/solid-floor-20260907-r4':'hardware/GERBER',
}


def setup(root=ROOT,*,apply=False):
    root=Path(root).resolve()
    pending=[]
    for old,new in ALIASES.items():
        source,target=root/old,root/new
        if not target.is_dir() or target.is_symlink() or (hasattr(target,'is_junction') and target.is_junction()):
            raise ValueError(f'Missing or redirected canonical directory: {target}')
        if not target.resolve().is_relative_to(root): raise ValueError('Target outside repository')
        if os.path.lexists(source):
            linked=source.is_symlink() or (hasattr(source,'is_junction') and source.is_junction())
            if not linked or source.resolve()!=target.resolve():
                raise ValueError(f'Conflicting legacy path; nothing overwritten: {source}')
        else:
            pending.append((old,new))
    # Preflight every alias before creating any of them.
    if apply:
        for old,new in pending:
            source,target=root/old,root/new
            source.parent.mkdir(parents=True,exist_ok=True)
            if os.name=='nt':
                env=dict(os.environ,KC2_ALIAS_PATH=str(source),KC2_TARGET_PATH=str(target))
                subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',
                    'New-Item -ItemType Junction -Path $env:KC2_ALIAS_PATH -Target $env:KC2_TARGET_PATH -ErrorAction Stop | Out-Null'],env=env,check=True)
            else:source.symlink_to(os.path.relpath(target,source.parent),target_is_directory=True)
    return pending


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    print(json.dumps({'applied':args.apply,'created_or_planned':setup(apply=args.apply)},indent=2))

if __name__=='__main__':main()
