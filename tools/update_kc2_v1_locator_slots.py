"""CON-ARCH-004 candidate shared V1/MX NPTH geometry; never writes canonical input.

Multiple blank-number NPTH pads prevent safe selection by the MCP pad-number
updater. Select by attribute and local position using KiCad's native API.
This tool establishes nominal geometry only, not manufacturing fit approval.
"""
import argparse
import json
import math
import shutil
from pathlib import Path
import pcbnew

ROOT = Path(__file__).resolve().parents[1]
LOCATOR_X = 5.45
SLOT_WIDTH = 2.60
SLOT_HEIGHT = 2.60


def containment_margin(x, y, diameter, width=SLOT_WIDTH, height=SLOT_HEIGHT):
    segment = (width - height) / 2
    distance = math.hypot(max(0, abs(abs(x) - LOCATOR_X) - segment), y)
    return height / 2 - distance - diameter / 2


def electrical_signature(board):
    return sorted((fp.GetReference(), p.GetNumber(), p.GetAttribute(), p.GetPosition().x,
                   p.GetPosition().y, p.GetSize().x, p.GetSize().y, p.GetDrillSize().x,
                   p.GetDrillSize().y, p.GetNetname(), str(p.GetLayerSet().FmtHex()))
                  for fp in board.GetFootprints() for p in fp.Pads()
                  if p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH)


def update(board, width=SLOT_WIDTH, height=SLOT_HEIGHT, center=LOCATOR_X):
    changed = 0
    for fp in board.GetFootprints():
        if str(fp.GetFPID().GetLibItemName()) != 'SW_Choc_V2_Socket_MX_THT':
            continue
        selected = []
        for pad in fp.Pads():
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and pad.GetNumber() == '2':
                pad.SetFPRelativeOrientation(pcbnew.EDA_ANGLE(45, pcbnew.DEGREES_T))
            local = pad.GetFPRelativePosition()
            x, y = local.x / 1e6, local.y / 1e6
            if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH and abs(y) < 1e-5 and any(abs(abs(x)-v)<1e-5 for v in (5.08, center)):
                selected.append((pad, x))
        if len(selected) != 2:
            raise ValueError(f'{fp.GetReference()}: expected exactly2 locator pads')
        for pad, x in selected:
            pad.SetFPRelativePosition(pcbnew.VECTOR2I(round(math.copysign(center, x)*1e6), 0))
            pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE if width == height else pcbnew.PAD_SHAPE_OVAL)
            pad.SetDrillShape(pcbnew.PAD_DRILL_SHAPE_CIRCLE if width == height else pcbnew.PAD_DRILL_SHAPE_OBLONG)
            size = pcbnew.VECTOR2I(round(width*1e6), round(height*1e6))
            pad.SetSize(size)
            pad.SetDrillSize(size)
            layers = pcbnew.LSET()
            layers.AddLayer(pcbnew.F_Mask)
            layers.AddLayer(pcbnew.B_Mask)
            pad.SetLayerSet(layers)
            changed += 1
    return changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--width', type=float, default=SLOT_WIDTH)
    parser.add_argument('--height', type=float, default=SLOT_HEIGHT)
    parser.add_argument('--center', type=float, default=LOCATOR_X)
    args = parser.parse_args()
    out = Path(args.output_dir).resolve()
    if not out.is_relative_to(ROOT / '.codex-tmp'):
        raise ValueError('Candidate output must be inside .codex-tmp')
    out.mkdir(parents=True, exist_ok=True)
    for side in ('left', 'right'):
        source = ROOT / f'hardware/kicad/kc2_{side}/kc2_{side}.kicad_pcb'
        dest = out / source.name
        if dest.exists():
            raise FileExistsError(dest)
        board = pcbnew.LoadBoard(str(source))
        before = electrical_signature(board)
        count = update(board, args.width, args.height, args.center)
        assert before == electrical_signature(board)
        pcbnew.SaveBoard(str(dest), board)
        shutil.copy2(source.with_suffix('.kicad_pro'), dest.with_suffix('.kicad_pro'))
        if source.with_suffix('.kicad_dru').exists():
            shutil.copy2(source.with_suffix('.kicad_dru'), dest.with_suffix('.kicad_dru'))
        print(json.dumps({'candidate': str(dest), 'changed_locators': count, 'electrical_unchanged': True}))


if __name__ == '__main__':
    main()
