from __future__ import annotations

import argparse
import json
from pathlib import Path

import pcbnew


ROOT = Path(__file__).resolve().parents[1]
COUPON_DIR = ROOT / "hardware" / "kicad" / "draft" / "x3-v2" / "coupon"
DEFAULT_BOARD = COUPON_DIR / "kc2_x3_v2_switch_coupon.kicad_pcb"


def analyze_coupon(path: Path = DEFAULT_BOARD) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(path)
    board = pcbnew.LoadBoard(str(path))
    switches = sorted(
        (fp for fp in board.GetFootprints() if fp.GetReference().startswith("SW_")),
        key=lambda fp: fp.GetReference(),
    )
    diodes = [fp for fp in board.GetFootprints() if fp.GetReference().startswith("D_")]
    mismatches: list[str] = []
    for switch in switches:
        for number in ("1", "2"):
            pads = [pad for pad in switch.Pads() if pad.GetNumber() == number]
            nets = {pad.GetNetname() for pad in pads}
            if len(pads) != 2 or len(nets) != 1 or "" in nets:
                mismatches.append(
                    f"{switch.GetReference()} pad {number}: count={len(pads)} nets={sorted(nets)}"
                )
    bounds = board.GetBoardEdgesBoundingBox()
    drc_path = path.with_suffix(".drc.json")
    drc = json.loads(drc_path.read_text(encoding="utf-8")) if drc_path.is_file() else {}
    board_text = "\n".join(
        drawing.GetText()
        for drawing in board.GetDrawings()
        if isinstance(drawing, pcbnew.PCB_TEXT)
    )
    return {
        "switch_refs": [switch.GetReference() for switch in switches],
        "switch_footprint_names": {
            str(switch.GetFPID().GetLibItemName()) for switch in switches
        },
        "switch_orientations_deg": {
            switch.GetReference(): round(float(switch.GetOrientation().AsDegrees()), 1)
            for switch in switches
        },
        "diode_count": len(diodes),
        "alternate_contact_net_mismatches": mismatches,
        "drc_violation_count": len(drc.get("violations", [])),
        "drc_unconnected_count": len(drc.get("unconnected_items", [])),
        "board_size_mm": [
            round(pcbnew.ToMM(bounds.GetWidth()), 3),
            round(pcbnew.ToMM(bounds.GetHeight()), 3),
        ],
        "board_text": board_text,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the CON-ARCH-004 physical fit coupon design.")
    parser.add_argument("board", nargs="?", type=Path, default=DEFAULT_BOARD)
    args = parser.parse_args()
    report = analyze_coupon(args.board)
    errors: list[str] = []
    if report["switch_refs"] != ["SW_L", "SW_MX", "SW_R"]:
        errors.append(f"switch samples: {report['switch_refs']}")
    expected_orientations = {"SW_L": 0.0, "SW_MX": 0.0, "SW_R": 180.0}
    if report["switch_orientations_deg"] != expected_orientations:
        errors.append(
            "switch orientations: "
            f"expected={expected_orientations} actual={report['switch_orientations_deg']}"
        )
    if report["alternate_contact_net_mismatches"]:
        errors.extend(report["alternate_contact_net_mismatches"])
    if report["drc_violation_count"] or report["drc_unconnected_count"]:
        errors.append(
            f"DRC violations={report['drc_violation_count']} unconnected={report['drc_unconnected_count']}"
        )
    if errors:
        raise SystemExit("FAIL: KC2 X3 V2 coupon\n- " + "\n- ".join(errors))
    print(json.dumps(report, indent=2, default=list))
    print(
        "PASS: CON-ARCH-004 coupon CAD is structurally complete; "
        "fabrication/population evidence remains pending"
    )


if __name__ == "__main__":
    main()
