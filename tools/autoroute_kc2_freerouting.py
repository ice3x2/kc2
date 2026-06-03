from __future__ import annotations

import argparse
from pathlib import Path

import pcbnew


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("board")
    parser.add_argument("dsn")
    parser.add_argument("--strip-tracks", action="store_true")
    parser.add_argument("--ses")
    parser.add_argument("--out")
    args = parser.parse_args()

    board_path = Path(args.board)
    board = pcbnew.LoadBoard(str(board_path))

    if args.strip_tracks:
        for track in list(board.GetTracks()):
            board.Delete(track)

    dsn_path = Path(args.dsn)
    dsn_path.parent.mkdir(parents=True, exist_ok=True)
    if not pcbnew.ExportSpecctraDSN(board, str(dsn_path)):
        raise SystemExit(f"Failed to export DSN: {dsn_path}")

    if args.ses:
        if not pcbnew.ImportSpecctraSES(board, str(args.ses)):
            raise SystemExit(f"Failed to import SES: {args.ses}")
        out_path = Path(args.out) if args.out else board_path
        pcbnew.SaveBoard(str(out_path), board)


if __name__ == "__main__":
    main()
