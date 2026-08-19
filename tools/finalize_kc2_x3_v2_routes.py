from __future__ import annotations

import argparse
import json
from pathlib import Path

import pcbnew

from tools import generate_kc2_pcbs as gen


ALLOWED_WARNING_TYPES = {
    "track_dangling",
    "silk_edge_clearance",
    "silk_over_copper",
}


def load_reviewed_drc(path: Path) -> dict[str, object]:
    report = json.loads(path.read_text(encoding="utf-8"))
    unconnected = report.get("unconnected_items", [])
    if unconnected:
        raise RuntimeError(f"Refusing cleanup with {len(unconnected)} unconnected items")
    violations = report.get("violations", [])
    hard_errors = [item for item in violations if item.get("severity") == "error"]
    if hard_errors:
        raise RuntimeError(f"Refusing cleanup with {len(hard_errors)} DRC errors")
    unexpected = sorted(
        {
            str(item.get("type"))
            for item in violations
            if item.get("type") not in ALLOWED_WARNING_TYPES
        }
    )
    if unexpected:
        raise RuntimeError(f"Refusing unreviewed DRC warning classes: {unexpected}")
    return report


def move_v2_key_labels_to_fab(board: pcbnew.BOARD, side: str) -> int:
    keys = gen.make_left_keys_x3_v2() if side == "left" else gen.make_right_keys_x3_v2()
    labels = {key.label for key in keys}
    changed = 0
    for drawing in board.GetDrawings():
        if not isinstance(drawing, pcbnew.PCB_TEXT):
            continue
        if drawing.GetLayer() != pcbnew.F_SilkS or drawing.GetText() not in labels:
            continue
        if pcbnew.ToMM(drawing.GetPosition().y) < 65.0:
            continue
        drawing.SetLayer(pcbnew.F_Fab)
        changed += 1
    return changed


def apply_reviewed_cleanup(board: pcbnew.BOARD, report: dict[str, object], side: str) -> dict[str, int]:
    violations = report.get("violations", [])
    dangling_uuids = {
        str(item["uuid"])
        for violation in violations
        if violation.get("type") == "track_dangling"
        for item in violation.get("items", [])
    }
    silk_item_uuids = {
        str(item["uuid"])
        for violation in violations
        if violation.get("type") in {"silk_edge_clearance", "silk_over_copper"}
        for item in violation.get("items", [])
    }

    removed = 0
    for track in list(board.GetTracks()):
        if track.m_Uuid.AsString() in dangling_uuids:
            board.Delete(track)
            removed += 1

    silk_moved = 0
    for drawing in board.GetDrawings():
        if not isinstance(drawing, pcbnew.PCB_TEXT):
            continue
        if drawing.m_Uuid.AsString() not in silk_item_uuids:
            continue
        if drawing.GetLayer() == pcbnew.F_SilkS:
            drawing.SetLayer(pcbnew.F_Fab)
            silk_moved += 1
        elif drawing.GetLayer() == pcbnew.B_SilkS:
            drawing.SetLayer(pcbnew.B_Fab)
            silk_moved += 1

    return {
        "dangling_tracks_removed": removed,
        "warning_silkscreen_texts_moved_to_fab": silk_moved,
        "v2_key_labels_moved_to_fab": move_v2_key_labels_to_fab(board, side),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply reviewed, non-electrical cleanup to a routed KC2 X3 V2 board."
    )
    parser.add_argument("board", type=Path)
    parser.add_argument("--drc", type=Path, required=True)
    args = parser.parse_args()
    report = load_reviewed_drc(args.drc)
    board = pcbnew.LoadBoard(str(args.board))
    side = "left" if "left" in args.board.name.lower() else "right"
    result = apply_reviewed_cleanup(board, report, side)
    pcbnew.SaveBoard(str(args.board), board)
    print(f"{side}: {result}")


if __name__ == "__main__":
    main()
