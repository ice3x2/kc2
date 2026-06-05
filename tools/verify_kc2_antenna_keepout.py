from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    import pcbnew
except ImportError as exc:
    raise SystemExit(
        "FAIL: pcbnew is unavailable. Run with KiCad Python, for example "
        r"C:\Program Files\KiCad\10.0\bin\python.exe"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "hardware" / "kicad" / "kc2_generation_manifest.json"


Rect = tuple[float, float, float, float]


def to_mm_vec(vec: pcbnew.VECTOR2I) -> tuple[float, float]:
    return pcbnew.ToMM(vec.x), pcbnew.ToMM(vec.y)


def circle_intersects_rect(x: float, y: float, radius: float, rect: Rect) -> bool:
    nearest_x = min(max(x, rect[0]), rect[2])
    nearest_y = min(max(y, rect[1]), rect[3])
    return (x - nearest_x) ** 2 + (y - nearest_y) ** 2 <= radius**2


def point_inside_rect(x: float, y: float, rect: Rect, tolerance: float = 0.0) -> bool:
    return rect[0] - tolerance <= x <= rect[2] + tolerance and rect[1] - tolerance <= y <= rect[3] + tolerance


def has_copper_layer(item: pcbnew.BOARD_ITEM) -> bool:
    if isinstance(item, pcbnew.PCB_VIA):
        return True
    if isinstance(item, pcbnew.PCB_TRACK):
        return item.GetLayer() in {pcbnew.F_Cu, pcbnew.B_Cu}
    if isinstance(item, pcbnew.PAD):
        layer_set = item.GetLayerSet()
        return layer_set.Contains(pcbnew.F_Cu) or layer_set.Contains(pcbnew.B_Cu)
    return False


def pad_radius_mm(pad: pcbnew.PAD) -> float:
    size = pad.GetSize()
    drill = pad.GetDrillSize()
    return max(pcbnew.ToMM(size.x), pcbnew.ToMM(size.y), pcbnew.ToMM(drill.x), pcbnew.ToMM(drill.y)) / 2.0


def check_board(side: str, board_path: Path, keepout: Rect) -> list[str]:
    board = pcbnew.LoadBoard(str(board_path))
    errors: list[str] = []

    for fp in board.GetFootprints():
        ref = fp.GetReference()
        value = fp.GetValue()
        is_mount = ref.startswith("H") or "MountingHole" in fp.GetFPIDAsString() or value.startswith("M2_")
        if not is_mount:
            continue
        fx, fy = to_mm_vec(fp.GetPosition())
        for pad in fp.Pads():
            px, py = to_mm_vec(pad.GetPosition())
            radius = pad_radius_mm(pad)
            if circle_intersects_rect(px, py, radius, keepout):
                errors.append(
                    f"{side}: mounting hole {ref} intersects antenna keepout "
                    f"at ({fx:.3f}, {fy:.3f}); pad center=({px:.3f}, {py:.3f}), radius={radius:.3f}"
                )

    for fp in board.GetFootprints():
        for pad in fp.Pads():
            if not has_copper_layer(pad):
                continue
            x, y = to_mm_vec(pad.GetPosition())
            if point_inside_rect(x, y, keepout, tolerance=0.001):
                errors.append(
                    f"{side}: copper pad {fp.GetReference()}-{pad.GetNumber()} is inside antenna keepout "
                    f"at ({x:.3f}, {y:.3f})"
                )

    for track in board.GetTracks():
        if isinstance(track, pcbnew.PCB_VIA):
            x, y = to_mm_vec(track.GetPosition())
            if point_inside_rect(x, y, keepout, tolerance=0.001):
                errors.append(f"{side}: via on {track.GetNetname()} is inside antenna keepout at ({x:.3f}, {y:.3f})")
        elif has_copper_layer(track):
            sx, sy = to_mm_vec(track.GetStart())
            ex, ey = to_mm_vec(track.GetEnd())
            if point_inside_rect(sx, sy, keepout, tolerance=0.001) or point_inside_rect(ex, ey, keepout, tolerance=0.001):
                errors.append(
                    f"{side}: copper track {track.GetNetname()} endpoint intersects antenna keepout "
                    f"({sx:.3f}, {sy:.3f})->({ex:.3f}, {ey:.3f})"
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify KC2 X3 nice!nano antenna keepout has no mounting holes or copper.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--board-root",
        type=Path,
        default=ROOT / "hardware" / "kicad",
    )
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    keepouts = manifest["antenna_keepout_mm"]
    errors: list[str] = []
    for side in ("left", "right"):
        board_path = args.board_root / f"kc2_{side}" / f"kc2_{side}.kicad_pcb"
        keepout = tuple(float(v) for v in keepouts[side])
        errors.extend(check_board(side, board_path, keepout))  # type: ignore[arg-type]

    if errors:
        print("FAIL: KC2 antenna keepout verification")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: KC2 antenna keepout verification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
