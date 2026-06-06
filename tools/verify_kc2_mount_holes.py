from __future__ import annotations

from pathlib import Path

try:
    import pcbnew
except ImportError as exc:
    raise SystemExit(
        "FAIL: pcbnew is unavailable. Run with KiCad Python, for example "
        r"C:\Program Files\KiCad\10.0\bin\python.exe"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
BOARD_PATHS = {
    "left": ROOT / "hardware" / "kicad" / "kc2_left" / "kc2_left.kicad_pcb",
    "right": ROOT / "hardware" / "kicad" / "kc2_right" / "kc2_right.kicad_pcb",
}
EXPECTED_HOLES = {
    "left": {
        "H4": (39.5, 107.75),
        "H5": (173.45, 66.50),
    },
    "right": {
        "H4": (225.8375, 107.75),
        "H5": (225.8375, 66.20),
    },
}
POSITION_TOLERANCE_MM = 0.02


def to_mm_vec(vec: pcbnew.VECTOR2I) -> tuple[float, float]:
    return pcbnew.ToMM(vec.x), pcbnew.ToMM(vec.y)


def mount_holes(board: pcbnew.BOARD) -> dict[str, tuple[float, float]]:
    holes: dict[str, tuple[float, float]] = {}
    for fp in board.GetFootprints():
        if fp.GetValue() == "M2_NPTH_2.2":
            holes[fp.GetReference()] = to_mm_vec(fp.GetPosition())
    return holes


def check_side(side: str, board_path: Path) -> list[str]:
    board = pcbnew.LoadBoard(str(board_path))
    holes = mount_holes(board)
    errors: list[str] = []
    expected_refs = {"H1", "H2", "H3", "H4", "H5"}
    if set(holes) != expected_refs:
        errors.append(f"{side}: expected H1-H5 M2 holes, got {sorted(holes)}")

    for ref, (expected_x, expected_y) in EXPECTED_HOLES[side].items():
        actual = holes.get(ref)
        if actual is None:
            errors.append(f"{side}: missing {ref}")
            continue

        actual_x, actual_y = actual
        if abs(actual_x - expected_x) > POSITION_TOLERANCE_MM or abs(actual_y - expected_y) > POSITION_TOLERANCE_MM:
            errors.append(
                f"{side}: {ref} at ({actual_x:.4f}, {actual_y:.4f}) mm, "
                f"expected ({expected_x:.4f}, {expected_y:.4f}) mm"
            )
    return errors


def main() -> int:
    errors: list[str] = []
    for side, path in BOARD_PATHS.items():
        errors.extend(check_side(side, path))

    if errors:
        print("FAIL: KC2 X3 mount-hole verification")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PASS: KC2 X3 mount-hole verification")
    for side, holes in EXPECTED_HOLES.items():
        for ref, expected in holes.items():
            print(f"- {side} {ref}: ({expected[0]:.4f}, {expected[1]:.4f}) mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
