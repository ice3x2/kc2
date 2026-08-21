from __future__ import annotations

import argparse
from collections import Counter
import json
import shutil
from pathlib import Path

import pcbnew

from tools import generate_kc2_pcbs as gen


POSITION_TOLERANCE_IU = pcbnew.FromMM(0.001)
TOP_ROUTE_MIN_Y_MM = 68.2
TOP_ROUTE_MAX_Y_MM = 69.95
TOP_ROUTE_TARGET_Y_MM = 70.25


def _edge_drawings(board: pcbnew.BOARD) -> list[pcbnew.PCB_SHAPE]:
    drawings = [
        drawing
        for drawing in board.GetDrawings()
        if drawing.GetLayer() == pcbnew.Edge_Cuts
    ]
    if not drawings:
        raise RuntimeError("board has no Edge.Cuts drawings")
    if any(not isinstance(drawing, pcbnew.PCB_SHAPE) for drawing in drawings):
        raise RuntimeError("Edge.Cuts contains an unsupported non-shape item")
    return drawings


def _edge_signature(
    drawing: pcbnew.PCB_SHAPE,
    delta: pcbnew.VECTOR2I | None = None,
) -> tuple[int, int, int, int, int, int]:
    if drawing.GetShape() != pcbnew.SHAPE_T_SEGMENT:
        raise RuntimeError("X3 V2 generated Edge.Cuts must contain only line segments")
    offset = delta or pcbnew.VECTOR2I(0, 0)
    start = drawing.GetStart() + offset
    end = drawing.GetEnd() + offset
    first, second = sorted(((start.x, start.y), (end.x, end.y)))
    return (
        int(drawing.GetShape()),
        first[0],
        first[1],
        second[0],
        second[1],
        drawing.GetWidth(),
    )


def _generated_to_target_translation(
    target: pcbnew.BOARD,
    generated: pcbnew.BOARD,
) -> pcbnew.VECTOR2I:
    target_switches = {
        footprint.GetReference(): footprint
        for footprint in target.GetFootprints()
        if footprint.GetReference().startswith("SW")
        and footprint.GetReference()[2:].isdigit()
    }
    generated_switches = {
        footprint.GetReference(): footprint
        for footprint in generated.GetFootprints()
        if footprint.GetReference().startswith("SW")
        and footprint.GetReference()[2:].isdigit()
    }
    if not target_switches or target_switches.keys() != generated_switches.keys():
        raise RuntimeError("generated and routed boards do not have the same switch references")
    anchor = min(target_switches, key=lambda reference: int(reference[2:]))
    delta = target_switches[anchor].GetPosition() - generated_switches[anchor].GetPosition()
    for reference in sorted(target_switches):
        target_footprint = target_switches[reference]
        generated_footprint = generated_switches[reference]
        if not same_position(target_footprint.GetPosition(), generated_footprint.GetPosition() + delta):
            raise RuntimeError(f"{reference}: routed board is not a rigid translation of the generator")
        if abs(
            target_footprint.GetOrientation().AsDegrees()
            - generated_footprint.GetOrientation().AsDegrees()
        ) > 0.001:
            raise RuntimeError(f"{reference}: routed board rotation differs from the generator")
    return delta


def sync_edge_cuts_from_generated(
    target: pcbnew.BOARD,
    generated: pcbnew.BOARD,
) -> dict[str, object]:
    """Replace only Edge.Cuts using the generator's rigidly translated outline."""

    delta = _generated_to_target_translation(target, generated)
    target_edges = _edge_drawings(target)
    generated_edges = _edge_drawings(generated)
    target_signatures = Counter(_edge_signature(drawing) for drawing in target_edges)
    generated_signatures = Counter(
        _edge_signature(drawing, delta) for drawing in generated_edges
    )
    if target_signatures == generated_signatures:
        return {
            "edge_drawings_replaced": 0,
            "edge_drawing_count": len(target_edges),
            "translation_mm": [
                round(pcbnew.ToMM(delta.x), 4),
                round(pcbnew.ToMM(delta.y), 4),
            ],
        }

    for drawing in target_edges:
        target.Delete(drawing)
    for drawing in generated_edges:
        clone = drawing.Duplicate()
        clone.Move(delta)
        target.Add(clone)
    return {
        "edge_drawings_replaced": len(target_edges),
        "edge_drawing_count": len(generated_edges),
        "translation_mm": [
            round(pcbnew.ToMM(delta.x), 4),
            round(pcbnew.ToMM(delta.y), 4),
        ],
    }


def same_position(a: pcbnew.VECTOR2I, b: pcbnew.VECTOR2I) -> bool:
    return (
        abs(a.x - b.x) <= POSITION_TOLERANCE_IU
        and abs(a.y - b.y) <= POSITION_TOLERANCE_IU
    )


def remove_dangling_tracks(board: pcbnew.BOARD) -> int:
    """Remove autorouter branches whose endpoint is not connected to copper or a pad."""

    removed = 0
    while True:
        board.BuildConnectivity()
        connectivity = board.GetConnectivity()
        dangling = []
        for item in board.GetTracks():
            if isinstance(item, pcbnew.PCB_VIA):
                continue
            if connectivity.TestTrackEndpointDangling(item, False, item.GetStart()) or (
                connectivity.TestTrackEndpointDangling(item, False, item.GetEnd())
            ):
                dangling.append(item)
        if not dangling:
            return removed
        for item in dangling:
            board.Delete(item)
            removed += 1


def move_footprint_with_attached_track_ends(
    board: pcbnew.BOARD,
    footprint: pcbnew.FOOTPRINT,
    delta: pcbnew.VECTOR2I,
) -> int:
    old_pad_positions = [pad.GetPosition() for pad in footprint.Pads()]
    moved_ends = 0
    for track in board.GetTracks():
        if isinstance(track, pcbnew.PCB_VIA):
            continue
        start = track.GetStart()
        end = track.GetEnd()
        if any(same_position(start, position) for position in old_pad_positions):
            track.SetStart(start + delta)
            moved_ends += 1
        if any(same_position(end, position) for position in old_pad_positions):
            track.SetEnd(end + delta)
            moved_ends += 1
    footprint.Move(delta)
    return moved_ends


def lift_top_row_route(board: pcbnew.BOARD, row_net: str) -> dict[str, int]:
    min_y = pcbnew.FromMM(TOP_ROUTE_MIN_Y_MM)
    max_y = pcbnew.FromMM(TOP_ROUTE_MAX_Y_MM)
    target_y = pcbnew.FromMM(TOP_ROUTE_TARGET_Y_MM)
    moved_vias = 0
    moved_track_ends = 0
    removed_zero_length = 0

    for item in board.GetTracks():
        if item.GetNetname() != row_net or not isinstance(item, pcbnew.PCB_VIA):
            continue
        position = item.GetPosition()
        if min_y <= position.y <= max_y:
            item.SetPosition(pcbnew.VECTOR2I(position.x, target_y))
            moved_vias += 1

    for item in list(board.GetTracks()):
        if item.GetNetname() != row_net or isinstance(item, pcbnew.PCB_VIA):
            continue
        start = item.GetStart()
        end = item.GetEnd()
        if min_y <= start.y <= max_y:
            item.SetStart(pcbnew.VECTOR2I(start.x, target_y))
            moved_track_ends += 1
        if min_y <= end.y <= max_y:
            item.SetEnd(pcbnew.VECTOR2I(end.x, target_y))
            moved_track_ends += 1
        if same_position(item.GetStart(), item.GetEnd()):
            board.Delete(item)
            removed_zero_length += 1

    return {
        "moved_vias": moved_vias,
        "moved_track_ends": moved_track_ends,
        "removed_zero_length_tracks": removed_zero_length,
    }


def repair_board(
    board_path: Path,
    *,
    backup_dir: Path,
    dry_run: bool = False,
    lift_top_route: bool = False,
    cleanup_dangling_tracks: bool = False,
    sync_edge_cuts_from: Path | None = None,
) -> dict[str, object]:
    board = pcbnew.LoadBoard(str(board_path))
    outline_result = (
        sync_edge_cuts_from_generated(board, pcbnew.LoadBoard(str(sync_edge_cuts_from)))
        if sync_edge_cuts_from is not None
        else None
    )
    side = "left" if "left" in board_path.name.lower() else "right"
    keys = gen.make_left_keys_x3_v2() if side == "left" else gen.make_right_keys_x3_v2()
    final_row = max(key.row for key in keys)
    footprints = {footprint.GetReference(): footprint for footprint in board.GetFootprints()}
    top_diodes: list[str] = []
    bottom_diodes: list[str] = []
    moved_attached_track_ends = 0
    for footprint in board.GetFootprints():
        reference = footprint.GetReference()
        if not reference.startswith("D") or not reference[1:].isdigit():
            continue
        index = int(reference[1:]) - 1
        if not 0 <= index < len(keys):
            raise RuntimeError(f"{side}: unexpected diode reference {reference}")
        key = keys[index]
        if key.row not in (0, final_row):
            continue
        switch = footprints.get(f"SW{index + 1}")
        if switch is None:
            raise RuntimeError(f"{side}: missing SW{index + 1} for {reference}")
        dx_mm, dy_mm, _rotation = gen.diode_placement_for_key(key, keys, "x3-v2")
        switch_position = switch.GetPosition()
        expected = pcbnew.VECTOR2I(
            switch_position.x + pcbnew.FromMM(dx_mm),
            switch_position.y + pcbnew.FromMM(dy_mm),
        )
        current = footprint.GetPosition()
        if same_position(current, expected):
            continue
        if key.row == 0:
            top_diodes.append(reference)
        else:
            bottom_diodes.append(reference)
        moved_attached_track_ends += move_footprint_with_attached_track_ends(
            board,
            footprint,
            expected - current,
        )

    row_result = (
        lift_top_row_route(board, f"{side[0].upper()}_ROW0")
        if lift_top_route
        else {
            "moved_vias": 0,
            "moved_track_ends": 0,
            "removed_zero_length_tracks": 0,
        }
    )
    dangling_tracks_removed = remove_dangling_tracks(board) if cleanup_dangling_tracks else 0
    backup_path = backup_dir / board_path.name
    if not dry_run:
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(board_path, backup_path)
        pcbnew.SaveBoard(str(board_path), board)
    return {
        "board": str(board_path),
        "backup": str(backup_path),
        "dry_run": dry_run,
        "top_diodes_shifted_inward": sorted(top_diodes),
        "bottom_diodes_shifted_inward": sorted(bottom_diodes),
        "attached_track_ends_shifted": moved_attached_track_ends,
        "lift_top_route": lift_top_route,
        "top_row_route": row_result,
        "dangling_tracks_removed": dangling_tracks_removed,
        "edge_cuts_sync": outline_result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Move X3 V2 perimeter diode envelopes to the verified edge-safe offsets and "
            "optionally remove dangling branches after the affected board is rerouted."
        )
    )
    parser.add_argument("board", type=Path)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--lift-top-route", action="store_true")
    parser.add_argument("--cleanup-dangling-tracks", action="store_true")
    parser.add_argument(
        "--sync-edge-cuts-from",
        type=Path,
        help="fresh generated board whose Edge.Cuts will be rigidly translated onto the routed board",
    )
    args = parser.parse_args()
    result = repair_board(
        args.board.resolve(),
        backup_dir=args.backup_dir.resolve(),
        dry_run=args.dry_run,
        lift_top_route=args.lift_top_route,
        cleanup_dangling_tracks=args.cleanup_dangling_tracks,
        sync_edge_cuts_from=(args.sync_edge_cuts_from.resolve() if args.sync_edge_cuts_from else None),
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
