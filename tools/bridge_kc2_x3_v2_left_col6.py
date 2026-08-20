from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pcbnew

from tools.postprocess_kc2_routes import add_track, add_via


BACK_PATH = (
    (162.025, 83.425),
    (162.025, 85.700),
    (155.800, 86.400),
    (155.800, 97.000),
    (155.000, 98.200),
)
FRONT_PATH = (
    (155.000, 98.200),
    (154.500, 99.000),
    (154.500, 112.500),
    (160.500, 112.500),
    (160.500, 124.000),
)
BACK_TAIL = (
    (160.500, 124.000),
    (165.6275, 129.595),
)
ENDPOINT_TOLERANCE_MM = 0.001


def validate_reviewed_endpoints(board: pcbnew.BOARD) -> None:
    actual = [
        (
            pcbnew.ToMM(pad.GetPosition().x),
            pcbnew.ToMM(pad.GetPosition().y),
        )
        for footprint in board.GetFootprints()
        for pad in footprint.Pads()
        if pad.GetNetname() == "L_COL6"
    ]
    for expected in (BACK_PATH[0], BACK_TAIL[1]):
        if not any(
            abs(position[0] - expected[0]) <= ENDPOINT_TOLERANCE_MM
            and abs(position[1] - expected[1]) <= ENDPOINT_TOLERANCE_MM
            for position in actual
        ):
            raise RuntimeError(
                "Board does not contain reviewed L_COL6 endpoint "
                f"({expected[0]:.4f}, {expected[1]:.4f})"
            )


def bridge_left_col6(board_path: Path, *, backup_dir: Path, dry_run: bool = False) -> dict[str, object]:
    if "left" not in board_path.name.lower():
        raise RuntimeError(f"Expected a left board, got {board_path.name}")
    board = pcbnew.LoadBoard(str(board_path))
    if board.FindNet("L_COL6") is None:
        raise RuntimeError("Board has no L_COL6 net")
    validate_reviewed_endpoints(board)

    before = len(list(board.GetTracks()))
    for start, end in zip(BACK_PATH, BACK_PATH[1:]):
        add_track(board, "L_COL6", pcbnew.B_Cu, start, end)
    add_via(board, "L_COL6", BACK_PATH[-1])
    for start, end in zip(FRONT_PATH, FRONT_PATH[1:]):
        add_track(board, "L_COL6", pcbnew.F_Cu, start, end)
    add_via(board, "L_COL6", FRONT_PATH[-1])
    add_track(board, "L_COL6", pcbnew.B_Cu, BACK_TAIL[0], BACK_TAIL[1])
    added = len(list(board.GetTracks())) - before

    backup_path = backup_dir / board_path.name
    if not dry_run:
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(board_path, backup_path)
        pcbnew.SaveBoard(str(board_path), board)
    return {
        "board": str(board_path),
        "backup": str(backup_path),
        "dry_run": dry_run,
        "net": "L_COL6",
        "track_and_via_items_added": added,
        "back_path": BACK_PATH,
        "front_path": FRONT_PATH,
        "back_tail": BACK_TAIL,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bridge the final L_COL6 gap around the compact X3 V2 stepped join edge."
    )
    parser.add_argument("board", type=Path)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = bridge_left_col6(
        args.board.resolve(),
        backup_dir=args.backup_dir.resolve(),
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
