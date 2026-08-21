from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

import pcbnew

from tools import generate_kc2_pcbs as gen


ALLOWED_WARNING_TYPES = {
    "track_dangling",
    "silk_edge_clearance",
    "silk_over_copper",
}


LEFT_CONTROLLER_COLUMN_NETS = {"L_COL0", "L_COL1"}
LEFT_CONTROLLER_COLUMN_ANCHORS_MM = {
    ("U1", "D3"): (132.4425, 56.6200),
    ("U1", "D5"): (137.5225, 56.6200),
    ("SW1", "1"): (41.4850, 82.6050),
    ("SW2", "1"): (65.6150, 72.4450),
}
LEFT_CONTROLLER_COLUMN_ROUTE = (
    ("track", "L_COL0", "F.Cu", 41.4850, 82.6050, 41.4850, 96.8925, 0.200),
    ("track", "L_COL0", "F.Cu", 46.2475, 101.6550, 47.7273, 103.1348, 0.200),
    ("track", "L_COL0", "F.Cu", 43.8663, 158.8050, 43.3239, 158.2626, 0.200),
    ("track", "L_COL0", "F.Cu", 47.7273, 103.1348, 47.7273, 119.8035, 0.200),
    ("track", "L_COL0", "F.Cu", 41.4850, 96.8925, 46.2475, 101.6550, 0.200),
    ("track", "L_COL0", "F.Cu", 43.3239, 140.2974, 43.8663, 139.7550, 0.200),
    ("track", "L_COL0", "F.Cu", 43.3239, 158.2626, 43.3239, 140.2974, 0.200),
    ("track", "L_COL0", "F.Cu", 47.7273, 119.8035, 48.6288, 120.7050, 0.200),
    ("track", "L_COL0", "B.Cu", 43.8663, 140.3402, 43.0413, 139.5152, 0.200),
    ("track", "L_COL0", "B.Cu", 132.4425, 56.6200, 118.6766, 70.3859, 0.200),
    ("track", "L_COL0", "B.Cu", 43.0413, 139.5152, 43.0413, 129.1100, 0.200),
    ("track", "L_COL0", "B.Cu", 46.2475, 108.5037, 47.4688, 109.7250, 0.200),
    ("track", "L_COL0", "B.Cu", 48.3021, 70.3859, 44.9744, 73.7136, 0.200),
    ("track", "L_COL0", "B.Cu", 43.0413, 129.1100, 42.7063, 128.7750, 0.200),
    ("track", "L_COL0", "B.Cu", 43.8663, 142.8650, 43.8663, 146.6650, 0.200),
    ("track", "L_COL0", "B.Cu", 48.6288, 122.8525, 48.6288, 120.7050, 0.200),
    ("track", "L_COL0", "B.Cu", 40.9216, 73.7136, 40.9216, 82.0416, 0.200),
    ("track", "L_COL0", "B.Cu", 118.6766, 70.3859, 48.3021, 70.3859, 0.200),
    ("track", "L_COL0", "B.Cu", 42.7063, 128.7750, 48.6288, 122.8525, 0.200),
    ("track", "L_COL0", "B.Cu", 45.0875, 90.6750, 41.4850, 87.0725, 0.200),
    ("track", "L_COL0", "B.Cu", 40.9216, 72.2216, 40.9216, 73.7136, 0.200),
    ("track", "L_COL0", "B.Cu", 43.8663, 142.8650, 43.8663, 140.3402, 0.200),
    ("track", "L_COL0", "B.Cu", 44.9744, 73.7136, 40.9216, 73.7136, 0.200),
    ("track", "L_COL0", "B.Cu", 40.9216, 82.0416, 41.4850, 82.6050, 0.200),
    ("track", "L_COL0", "B.Cu", 46.2475, 101.6550, 46.2475, 108.5037, 0.200),
    ("track", "L_COL0", "B.Cu", 43.8663, 146.6650, 42.7063, 147.8250, 0.200),
    ("track", "L_COL0", "B.Cu", 43.8663, 139.7550, 43.8663, 142.8650, 0.200),
    ("track", "L_COL0", "B.Cu", 40.3250, 71.6250, 40.9216, 72.2216, 0.200),
    ("track", "L_COL0", "B.Cu", 41.4850, 87.0725, 41.4850, 82.6050, 0.200),
    ("track", "L_COL1", "F.Cu", 113.5737, 72.1961, 113.5737, 56.3911, 0.200),
    ("track", "L_COL1", "F.Cu", 72.7588, 148.6450, 71.2791, 147.1653, 0.200),
    ("track", "L_COL1", "F.Cu", 79.1416, 95.4966, 75.1400, 91.4950, 0.200),
    ("track", "L_COL1", "F.Cu", 91.9031, 84.2569, 96.3348, 84.2569, 0.200),
    ("track", "L_COL1", "F.Cu", 99.4727, 81.1190, 104.6508, 81.1190, 0.200),
    ("track", "L_COL1", "F.Cu", 69.6142, 76.4442, 69.6142, 85.9692, 0.200),
    ("track", "L_COL1", "F.Cu", 96.3348, 84.2569, 99.4727, 81.1190, 0.200),
    ("track", "L_COL1", "F.Cu", 71.2791, 142.8559, 71.2791, 130.4966, 0.200),
    ("track", "L_COL1", "F.Cu", 71.2791, 130.4966, 70.3775, 129.5950, 0.200),
    ("track", "L_COL1", "F.Cu", 71.2791, 147.1653, 71.2791, 142.8559, 0.200),
    ("track", "L_COL1", "F.Cu", 65.6150, 72.4450, 69.6142, 76.4442, 0.200),
    ("track", "L_COL1", "F.Cu", 70.3775, 129.5950, 76.1382, 123.8343, 0.200),
    ("track", "L_COL1", "F.Cu", 79.9025, 96.2575, 91.9031, 84.2569, 0.200),
    ("track", "L_COL1", "F.Cu", 79.9025, 96.2575, 79.1416, 95.4966, 0.200),
    ("track", "L_COL1", "F.Cu", 79.9025, 101.1439, 79.9025, 96.2575, 0.200),
    ("track", "L_COL1", "F.Cu", 69.6142, 85.9692, 75.1400, 91.4950, 0.200),
    ("track", "L_COL1", "F.Cu", 79.9025, 110.5450, 79.9025, 101.1439, 0.200),
    ("track", "L_COL1", "F.Cu", 104.6508, 81.1190, 113.5737, 72.1961, 0.200),
    ("via", "L_COL1", 71.2791, 142.8559, 0.600, 0.300),
    ("via", "L_COL1", 76.1382, 123.8343, 0.600, 0.300),
    ("via", "L_COL1", 79.9025, 101.1439, 0.600, 0.300),
    ("via", "L_COL1", 113.5737, 56.3911, 0.600, 0.300),
    ("track", "L_COL1", "B.Cu", 80.8041, 111.4466, 80.8041, 121.2666, 0.200),
    ("track", "L_COL1", "B.Cu", 79.9025, 101.1439, 77.6311, 101.1439, 0.200),
    ("track", "L_COL1", "B.Cu", 80.8041, 121.2666, 81.0625, 121.5250, 0.200),
    ("track", "L_COL1", "B.Cu", 73.6604, 149.5466, 72.7588, 148.6450, 0.200),
    ("track", "L_COL1", "B.Cu", 73.6604, 159.3666, 73.6604, 149.5466, 0.200),
    ("track", "L_COL1", "B.Cu", 66.7750, 83.4250, 67.0700, 83.4250, 0.200),
    ("track", "L_COL1", "B.Cu", 136.3002, 55.3977, 137.5225, 56.6200, 0.200),
    ("track", "L_COL1", "B.Cu", 77.6311, 101.1439, 76.3000, 102.4750, 0.200),
    ("track", "L_COL1", "B.Cu", 114.5671, 55.3977, 136.3002, 55.3977, 0.200),
    ("track", "L_COL1", "B.Cu", 113.5737, 56.3911, 114.5671, 55.3977, 0.200),
    ("track", "L_COL1", "B.Cu", 79.9025, 110.5450, 80.8041, 111.4466, 0.200),
    ("track", "L_COL1", "B.Cu", 71.2791, 140.8334, 71.5375, 140.5750, 0.200),
    ("track", "L_COL1", "B.Cu", 71.2791, 142.8559, 71.2791, 140.8334, 0.200),
    ("track", "L_COL1", "B.Cu", 76.1382, 123.8343, 78.7532, 123.8343, 0.200),
    ("track", "L_COL1", "B.Cu", 78.7532, 123.8343, 81.0625, 121.5250, 0.200),
    ("track", "L_COL1", "B.Cu", 73.9188, 159.6250, 73.6604, 159.3666, 0.200),
    ("track", "L_COL1", "B.Cu", 67.0700, 83.4250, 75.1400, 91.4950, 0.200),
)


def _route_signature(item: pcbnew.BOARD_CONNECTED_ITEM) -> tuple[object, ...]:
    if isinstance(item, pcbnew.PCB_VIA):
        position = item.GetPosition()
        return (
            "via",
            item.GetNetname(),
            round(pcbnew.ToMM(position.x), 4),
            round(pcbnew.ToMM(position.y), 4),
            round(pcbnew.ToMM(item.GetWidth(pcbnew.F_Cu)), 3),
            round(pcbnew.ToMM(item.GetDrillValue()), 3),
        )
    start = item.GetStart()
    end = item.GetEnd()
    return (
        "track",
        item.GetNetname(),
        item.GetBoard().GetLayerName(item.GetLayer()),
        round(pcbnew.ToMM(start.x), 4),
        round(pcbnew.ToMM(start.y), 4),
        round(pcbnew.ToMM(end.x), 4),
        round(pcbnew.ToMM(end.y), 4),
        round(pcbnew.ToMM(item.GetWidth()), 3),
    )


def restore_left_controller_columns(board: pcbnew.BOARD) -> dict[str, int]:
    """Restore the reviewed L_COL0/L_COL1 fanout after the diode-edge autoroute."""

    for (reference, number), expected in LEFT_CONTROLLER_COLUMN_ANCHORS_MM.items():
        footprint = board.FindFootprintByReference(reference)
        if footprint is None:
            raise RuntimeError(f"missing reviewed route anchor {reference}")
        pad = next((candidate for candidate in footprint.Pads() if candidate.GetNumber() == number), None)
        if pad is None:
            raise RuntimeError(f"missing reviewed route anchor {reference}.{number}")
        position = pad.GetPosition()
        actual = (round(pcbnew.ToMM(position.x), 4), round(pcbnew.ToMM(position.y), 4))
        if actual != expected:
            raise RuntimeError(
                f"reviewed route anchor {reference}.{number} moved: expected {expected}, found {actual}"
            )

    existing = [
        item for item in board.GetTracks() if item.GetNetname() in LEFT_CONTROLLER_COLUMN_NETS
    ]
    if Counter(_route_signature(item) for item in existing) == Counter(LEFT_CONTROLLER_COLUMN_ROUTE):
        return {"track_and_via_items_removed": 0, "track_and_via_items_added": 0}

    for item in existing:
        board.Delete(item)
    for spec in LEFT_CONTROLLER_COLUMN_ROUTE:
        kind, net_name, *values = spec
        net = board.FindNet(net_name)
        if net is None:
            raise RuntimeError(f"missing reviewed route net {net_name}")
        if kind == "via":
            x, y, diameter, drill = values
            item = pcbnew.PCB_VIA(board)
            item.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
            item.SetWidth(pcbnew.FromMM(diameter))
            item.SetDrill(pcbnew.FromMM(drill))
            item.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        else:
            layer_name, x1, y1, x2, y2, width = values
            item = pcbnew.PCB_TRACK(board)
            item.SetLayer(board.GetLayerID(layer_name))
            item.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(x1), pcbnew.FromMM(y1)))
            item.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(x2), pcbnew.FromMM(y2)))
            item.SetWidth(pcbnew.FromMM(width))
        item.SetNet(net)
        board.Add(item)
    return {
        "track_and_via_items_removed": len(existing),
        "track_and_via_items_added": len(LEFT_CONTROLLER_COLUMN_ROUTE),
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
        description="Apply reviewed routing repair and non-electrical cleanup to KC2 X3 V2."
    )
    parser.add_argument("board", type=Path)
    parser.add_argument("--drc", type=Path)
    parser.add_argument("--restore-left-controller-columns", action="store_true")
    args = parser.parse_args()
    board = pcbnew.LoadBoard(str(args.board))
    side = "left" if "left" in args.board.name.lower() else "right"
    result: dict[str, object] = {}
    if args.restore_left_controller_columns:
        if side != "left":
            raise RuntimeError("left controller-column repair cannot be applied to a right board")
        result["left_controller_columns"] = restore_left_controller_columns(board)
    if args.drc:
        report = load_reviewed_drc(args.drc)
        result["reviewed_cleanup"] = apply_reviewed_cleanup(board, report, side)
    if not result:
        parser.error("provide --drc and/or --restore-left-controller-columns")
    pcbnew.SaveBoard(str(args.board), board)
    print(f"{side}: {result}")


if __name__ == "__main__":
    main()
