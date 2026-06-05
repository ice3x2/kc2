from __future__ import annotations

import argparse
import math
from pathlib import Path

try:
    import pcbnew
except ImportError as exc:
    raise SystemExit(
        "FAIL: pcbnew is unavailable. Run with KiCad Python, for example "
        r"C:\Program Files\KiCad\10.0\bin\python.exe"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
TRACK_WIDTH = 0.25
VIA_SIZE = 0.60
VIA_DRILL = 0.30


Point = tuple[float, float]


def mm(value: int) -> float:
    return pcbnew.ToMM(value)


def vxy(point: Point) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(pcbnew.FromMM(point[0]), pcbnew.FromMM(point[1]))


def point_matches(vec: pcbnew.VECTOR2I, point: Point, tolerance: float = 0.012) -> bool:
    return abs(mm(vec.x) - point[0]) <= tolerance and abs(mm(vec.y) - point[1]) <= tolerance


def track_length(track: pcbnew.PCB_TRACK) -> float:
    start = track.GetStart()
    end = track.GetEnd()
    return math.hypot(mm(end.x - start.x), mm(end.y - start.y))


def track_matches_pair(track: pcbnew.PCB_TRACK, a: Point, b: Point, tolerance: float = 0.012) -> bool:
    start = track.GetStart()
    end = track.GetEnd()
    return (
        point_matches(start, a, tolerance)
        and point_matches(end, b, tolerance)
    ) or (
        point_matches(start, b, tolerance)
        and point_matches(end, a, tolerance)
    )


def add_track(board: pcbnew.BOARD, net_name: str, layer: int, start: Point, end: Point) -> None:
    net = board.FindNet(net_name)
    if net is None:
        raise RuntimeError(f"Missing net {net_name}")
    for existing in board.GetTracks():
        if not isinstance(existing, pcbnew.PCB_TRACK) or isinstance(existing, pcbnew.PCB_VIA):
            continue
        if existing.GetNetname() == net_name and existing.GetLayer() == layer and track_matches_pair(existing, start, end):
            return
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(vxy(start))
    track.SetEnd(vxy(end))
    track.SetLayer(layer)
    track.SetWidth(pcbnew.FromMM(TRACK_WIDTH))
    track.SetNet(net)
    board.Add(track)


def add_via(board: pcbnew.BOARD, net_name: str, at: Point) -> None:
    net = board.FindNet(net_name)
    if net is None:
        raise RuntimeError(f"Missing net {net_name}")
    for existing in board.GetTracks():
        if isinstance(existing, pcbnew.PCB_VIA) and existing.GetNetname() == net_name and point_matches(existing.GetPosition(), at):
            return
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(vxy(at))
    via.SetWidth(pcbnew.FromMM(VIA_SIZE))
    via.SetDrill(pcbnew.FromMM(VIA_DRILL))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(net)
    board.Add(via)


def delete_tracks_by_pairs(
    board: pcbnew.BOARD,
    net_name: str,
    layer: int,
    pairs: list[tuple[Point, Point]],
) -> int:
    removed = 0
    for track in list(board.GetTracks()):
        if not isinstance(track, pcbnew.PCB_TRACK) or isinstance(track, pcbnew.PCB_VIA):
            continue
        if track.GetNetname() != net_name or track.GetLayer() != layer:
            continue
        if any(track_matches_pair(track, start, end) for start, end in pairs):
            board.Delete(track)
            removed += 1
    return removed


def move_l_col6_edge_segment(board: pcbnew.BOARD) -> int:
    targets = {(167.5680, 107.4258), (167.5680, 83.8820)}
    changed = 0
    for track in board.GetTracks():
        if not isinstance(track, pcbnew.PCB_TRACK) or isinstance(track, pcbnew.PCB_VIA):
            continue
        if track.GetNetname() != "L_COL6" or track.GetLayer() != pcbnew.B_Cu:
            continue
        for getter, setter in ((track.GetStart, track.SetStart), (track.GetEnd, track.SetEnd)):
            point = getter()
            if any(point_matches(point, target) for target in targets):
                setter(pcbnew.VECTOR2I(pcbnew.FromMM(166.2000), point.y))
                changed += 1
    return changed


def reroute_l_col6_d26_clearance(board: pcbnew.BOARD) -> int:
    removed = delete_tracks_by_pairs(
        board,
        "L_COL6",
        pcbnew.B_Cu,
        [
            ((170.0405, 129.7279), (171.9213, 127.8471)),
            ((171.9213, 127.8471), (171.9213, 116.7951)),
            ((171.9213, 116.7951), (168.0212, 112.8950)),
        ],
    )
    for point in ((170.0405, 129.7279), (168.0212, 112.8950)):
        add_via(board, "L_COL6", point)
    for start, end in [
        ((170.0405, 129.7279), (171.6000, 127.8471)),
        ((171.6000, 127.8471), (171.6000, 116.7951)),
        ((171.6000, 116.7951), (168.0212, 112.8950)),
    ]:
        add_track(board, "L_COL6", pcbnew.F_Cu, start, end)
    return removed


def remove_stubs_by_length(
    board: pcbnew.BOARD,
    specs: list[tuple[str, int, float]],
    *,
    tolerance: float = 0.010,
) -> int:
    removed = 0
    for track in list(board.GetTracks()):
        if not isinstance(track, pcbnew.PCB_TRACK) or isinstance(track, pcbnew.PCB_VIA):
            continue
        for net_name, layer, target_length in specs:
            if track.GetNetname() == net_name and track.GetLayer() == layer and abs(track_length(track) - target_length) <= tolerance:
                board.Delete(track)
                removed += 1
                break
    return removed


def postprocess_left(board: pcbnew.BOARD) -> dict[str, int]:
    return {
        "moved_l_col6_edge_endpoints": move_l_col6_edge_segment(board),
        "rerouted_l_col6_d26_segments": reroute_l_col6_d26_clearance(board),
        "removed_freerouting_stubs": remove_stubs_by_length(
            board,
            [
                ("L_ROW0", pcbnew.B_Cu, 0.9608),
                ("L_ROW2", pcbnew.F_Cu, 1.5046),
                ("L_ROW2", pcbnew.B_Cu, 1.5046),
                ("LK25_D", pcbnew.B_Cu, 1.0836),
            ],
        ),
    }


def postprocess_right(board: pcbnew.BOARD) -> dict[str, int]:
    removed = remove_stubs_by_length(
        board,
        [
            ("R_ROW1", pcbnew.F_Cu, 0.7685),
            ("R_ROW1", pcbnew.B_Cu, 0.7685),
            ("R_ROW4", pcbnew.F_Cu, 0.6766),
            ("R_ROW4", pcbnew.F_Cu, 1.2658),
            ("R_ROW4", pcbnew.B_Cu, 0.6766),
            ("R_ROW4", pcbnew.B_Cu, 1.2658),
            ("RK34_D", pcbnew.B_Cu, 2.6490),
        ],
    )
    add_track(board, "R_ROW1", pcbnew.F_Cu, (166.4173, 88.7529), (165.8703, 89.2999))
    add_track(board, "R_ROW4", pcbnew.B_Cu, (63.7341, 143.9637), (64.2125, 144.4421))
    return {
        "removed_freerouting_stubs": removed,
        "restored_required_row_bridges": 2,
    }


def process_board(path: Path, side: str) -> dict[str, int]:
    board = pcbnew.LoadBoard(str(path))
    result = postprocess_left(board) if side == "left" else postprocess_right(board)
    pcbnew.SaveBoard(str(path), board)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply deterministic KC2 X3 route cleanup after Freerouting SES import.")
    parser.add_argument(
        "boards",
        nargs="*",
        type=Path,
        default=[
            ROOT / "hardware" / "kicad" / "kc2_left" / "kc2_left.kicad_pcb",
            ROOT / "hardware" / "kicad" / "kc2_right" / "kc2_right.kicad_pcb",
        ],
    )
    args = parser.parse_args()
    for board_path in args.boards:
        name = board_path.name.lower()
        if "left" in name:
            side = "left"
        elif "right" in name:
            side = "right"
        else:
            raise SystemExit(f"Cannot infer side from board path: {board_path}")
        result = process_board(board_path, side)
        print(f"{side}: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
