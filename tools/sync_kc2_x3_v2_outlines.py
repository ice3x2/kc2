from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import pcbnew


ALIGNMENT_TOLERANCE_MM = 0.001


def mm(value: int) -> float:
    return pcbnew.ToMM(value)


def matrix_footprints(board: pcbnew.BOARD) -> dict[str, pcbnew.FOOTPRINT]:
    return {
        footprint.GetReference(): footprint
        for footprint in board.GetFootprints()
        if footprint.GetReference().startswith("SW")
        and footprint.GetReference()[2:].isdigit()
    }


def alignment_delta(
    source: pcbnew.BOARD,
    target: pcbnew.BOARD,
) -> tuple[pcbnew.VECTOR2I, float]:
    source_switches = matrix_footprints(source)
    target_switches = matrix_footprints(target)
    if source_switches.keys() != target_switches.keys():
        raise RuntimeError("Source and target switch reference sets differ")
    reference = sorted(source_switches, key=lambda item: int(item[2:]))[0]
    delta = target_switches[reference].GetPosition() - source_switches[reference].GetPosition()
    maximum_error = 0.0
    for ref in source_switches:
        aligned = source_switches[ref].GetPosition() + delta
        actual = target_switches[ref].GetPosition()
        error = max(abs(mm(aligned.x - actual.x)), abs(mm(aligned.y - actual.y)))
        maximum_error = max(maximum_error, error)
    if maximum_error > ALIGNMENT_TOLERANCE_MM:
        raise RuntimeError(
            f"Switch geometry differs after alignment by {maximum_error:.6f} mm"
        )
    return delta, maximum_error


def sync_outline(
    source_path: Path,
    target_path: Path,
    *,
    backup_dir: Path,
    dry_run: bool = False,
) -> dict[str, object]:
    source = pcbnew.LoadBoard(str(source_path))
    target = pcbnew.LoadBoard(str(target_path))
    delta, alignment_error = alignment_delta(source, target)
    source_edges = [
        drawing for drawing in source.GetDrawings() if drawing.GetLayer() == pcbnew.Edge_Cuts
    ]
    target_edges = [
        drawing for drawing in target.GetDrawings() if drawing.GetLayer() == pcbnew.Edge_Cuts
    ]
    if not source_edges or not target_edges:
        raise RuntimeError("Both source and target must contain Edge.Cuts items")

    backup_path = backup_dir / target_path.name
    if not dry_run:
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target_path, backup_path)
        for drawing in target_edges:
            target.Delete(drawing)
        for drawing in source_edges:
            clone = drawing.Duplicate()
            clone.Move(delta)
            target.Add(clone)
        pcbnew.SaveBoard(str(target_path), target)

    return {
        "source": str(source_path),
        "target": str(target_path),
        "backup": str(backup_path),
        "dry_run": dry_run,
        "source_edge_items": len(source_edges),
        "replaced_target_edge_items": len(target_edges),
        "alignment_delta_mm": [round(mm(delta.x), 6), round(mm(delta.y), 6)],
        "maximum_switch_alignment_error_mm": round(alignment_error, 6),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copy generated X3 V2 Edge.Cuts onto a routed board while preserving routing."
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = sync_outline(
        args.source.resolve(),
        args.target.resolve(),
        backup_dir=args.backup_dir.resolve(),
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
