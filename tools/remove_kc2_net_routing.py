from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pcbnew


def remove_net_routing(
    board_path: Path,
    net_names: set[str],
    *,
    backup_dir: Path,
    dry_run: bool = False,
) -> dict[str, object]:
    board = pcbnew.LoadBoard(str(board_path))
    matching = [track for track in board.GetTracks() if track.GetNetname() in net_names]
    tracks = [track for track in matching if not isinstance(track, pcbnew.PCB_VIA)]
    vias = [track for track in matching if isinstance(track, pcbnew.PCB_VIA)]
    found_nets = {track.GetNetname() for track in matching}
    missing_nets = sorted(net_names - found_nets)
    if missing_nets:
        raise RuntimeError(f"No routing found for nets: {missing_nets}")
    backup_path = backup_dir / board_path.name
    if not dry_run:
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(board_path, backup_path)
        for item in matching:
            board.Delete(item)
        pcbnew.SaveBoard(str(board_path), board)
    return {
        "board": str(board_path),
        "backup": str(backup_path),
        "dry_run": dry_run,
        "nets": sorted(found_nets),
        "track_segments_removed": len(tracks),
        "vias_removed": len(vias),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove only named-net tracks and vias from a KC2 board before constrained rerouting."
    )
    parser.add_argument("board", type=Path)
    parser.add_argument("--net", action="append", required=True, dest="nets")
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = remove_net_routing(
        args.board.resolve(),
        set(args.nets),
        backup_dir=args.backup_dir.resolve(),
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
