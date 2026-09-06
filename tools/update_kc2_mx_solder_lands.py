"""CON-ARCH-004 AC-3: update only duplicate-number MX PTHs, retaining Choc SMDs.

The KiCad MCP pad updater rejects duplicate numbers. Select by pad attribute
as well as number using KiCad's own API; never renumber the shared contacts.
"""
import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parents[1]


def update_board(path: Path, apply: bool) -> dict:
    board = pcbnew.LoadBoard(str(path))
    changed = []
    for fp in board.GetFootprints():
        if str(fp.GetFPID().GetLibItemName()) != 'SW_Choc_V2_Socket_MX_THT':
            continue
        pads = [p for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
        if sorted(p.GetNumber() for p in pads) != ['1', '2']:
            raise RuntimeError(f'{fp.GetReference()}: unexpected MX electrical contacts')
        for pad in pads:
            pad.SetShape(pcbnew.PAD_SHAPE_OVAL)
            pad.SetSize(pcbnew.VECTOR2I(pcbnew.FromMM(2.5), pcbnew.FromMM(3.2)))
            pad.SetDrillSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.6), pcbnew.FromMM(1.6)))
            layers = pcbnew.LSET(pcbnew.LSET.AllCuMask())
            layers.AddLayer(pcbnew.F_Mask)
            layers.AddLayer(pcbnew.B_Mask)
            pad.SetLayerSet(layers)
            pad.SetLocalSolderMaskMargin(0)
            changed.append(f'{fp.GetReference()}.{pad.GetNumber()}')
    if not changed:
        raise RuntimeError(f'No selected hybrid switch pads in {path}')
    result = {'board': str(path.relative_to(ROOT)), 'mx_pads': len(changed), 'written': apply}
    if apply:
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = ROOT / '.codex-tmp' / f'{path.stem}-before-mx-lands-{stamp}.kicad_pcb'
        backup.parent.mkdir(exist_ok=True)
        shutil.copy2(path, backup)
        if not pcbnew.SaveBoard(str(path), board):
            raise RuntimeError(f'Failed to save {path}; backup at {backup}')
        result['backup'] = str(backup.relative_to(ROOT))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    paths = [ROOT / f'hardware/kicad/kc2_{side}/kc2_{side}.kicad_pcb' for side in ('left', 'right')]
    # Validate both boards before writing either one.
    for path in paths:
        update_board(path, False)
    for path in paths:
        print(json.dumps(update_board(path, args.apply)))


if __name__ == '__main__':
    main()
