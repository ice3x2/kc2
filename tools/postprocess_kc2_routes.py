from __future__ import annotations

from pathlib import Path

import pcbnew


ROOT = Path(__file__).resolve().parents[1]
TRACK_WIDTH = 0.25
VIA_SIZE = 0.60
VIA_DRILL = 0.30


def mm(value: float) -> int:
    return pcbnew.FromMM(float(value))


def vxy(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(mm(x), mm(y))


def net(board: pcbnew.BOARD, name: str) -> pcbnew.NETINFO_ITEM:
    item = board.FindNet(name)
    if item is None:
        raise RuntimeError(f"Missing net {name}")
    return item


def add_track(
    board: pcbnew.BOARD,
    net_item: pcbnew.NETINFO_ITEM,
    start: tuple[float, float],
    end: tuple[float, float],
    layer: int,
    width: float = TRACK_WIDTH,
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(vxy(*start))
    track.SetEnd(vxy(*end))
    track.SetWidth(mm(width))
    track.SetLayer(layer)
    track.SetNet(net_item)
    board.Add(track)


def add_via(
    board: pcbnew.BOARD,
    net_item: pcbnew.NETINFO_ITEM,
    pos: tuple[float, float],
) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(vxy(*pos))
    via.SetWidth(mm(VIA_SIZE))
    via.SetDrill(mm(VIA_DRILL))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(net_item)
    board.Add(via)


def add_polyline(
    board: pcbnew.BOARD,
    net_item: pcbnew.NETINFO_ITEM,
    points: list[tuple[float, float]],
    layer: int,
) -> None:
    for start, end in zip(points, points[1:]):
        add_track(board, net_item, start, end, layer)


def postprocess_left() -> None:
    path = ROOT / "hardware" / "kicad" / "kc2_left" / "kc2_left.kicad_pcb"
    board = pcbnew.LoadBoard(str(path))
    add_polyline(
        board,
        net(board, "L_COL2"),
        [(97.65, 102.475), (100.0, 104.825), (112.0, 104.825), (112.0, 118.0), (102.4125, 121.525)],
        pcbnew.B_Cu,
    )
    add_polyline(
        board,
        net(board, "L_COL3"),
        [(116.7, 102.475), (119.0, 104.825), (130.0, 104.825), (130.0, 118.0), (121.4625, 121.525)],
        pcbnew.B_Cu,
    )
    pcbnew.SaveBoard(str(path), board)


def postprocess_right() -> None:
    path = ROOT / "hardware" / "kicad" / "kc2_right" / "kc2_right.kicad_pcb"
    board = pcbnew.LoadBoard(str(path))
    add_polyline(
        board,
        net(board, "R_COL6"),
        [(183.0563, 83.425), (176.0, 83.425), (176.0, 99.0), (172.525, 102.475), (161.625, 102.475)],
        pcbnew.B_Cu,
    )
    pcbnew.SaveBoard(str(path), board)


def main() -> None:
    postprocess_left()
    postprocess_right()


if __name__ == "__main__":
    main()
