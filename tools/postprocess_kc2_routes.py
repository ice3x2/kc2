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
X3_TOP_EDGE_RELIEF = 0.30


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


def shifted_y_if_in_band(vec: pcbnew.VECTOR2I, min_y: float, max_y: float, dy: float) -> pcbnew.VECTOR2I | None:
    y = mm(vec.y)
    if min_y - 0.001 <= y <= max_y + 0.001:
        return pcbnew.VECTOR2I(vec.x, pcbnew.FromMM(y + dy))
    return None


def apply_x3_top_edge_relief(board: pcbnew.BOARD, side: str) -> int:
    if side == "left":
        min_y, max_y, generated_top_y, dy = 61.5, 64.1, 62.0, -0.5
    elif side == "right":
        min_y, max_y, generated_top_y, dy = 61.0, 63.6, 61.5, -0.6
    else:
        raise ValueError(f"Unknown side: {side}")

    edge_drawings = [drawing for drawing in board.GetDrawings() if drawing.GetLayer() == pcbnew.Edge_Cuts]
    has_generated_top = False
    for drawing in edge_drawings:
        if not hasattr(drawing, "GetStart") or not hasattr(drawing, "GetEnd"):
            continue
        if abs(mm(drawing.GetStart().y) - generated_top_y) <= 0.001 or abs(mm(drawing.GetEnd().y) - generated_top_y) <= 0.001:
            has_generated_top = True
            break
    if not has_generated_top:
        return 0

    changed = 0
    for drawing in edge_drawings:
        if not hasattr(drawing, "GetStart") or not hasattr(drawing, "GetEnd"):
            continue
        start = drawing.GetStart()
        end = drawing.GetEnd()
        new_start = shifted_y_if_in_band(start, min_y, max_y, dy)
        new_end = shifted_y_if_in_band(end, min_y, max_y, dy)
        if new_start is not None:
            drawing.SetStart(new_start)
            changed += 1
        if new_end is not None:
            drawing.SetEnd(new_end)
            changed += 1
    return changed


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


def delete_vias_by_points(
    board: pcbnew.BOARD,
    net_name: str,
    points: list[Point],
) -> int:
    removed = 0
    for track in list(board.GetTracks()):
        if not isinstance(track, pcbnew.PCB_VIA):
            continue
        if track.GetNetname() != net_name:
            continue
        if any(point_matches(track.GetPosition(), point) for point in points):
            board.Delete(track)
            removed += 1
    return removed


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
        pcbnew.F_Cu,
        [
            ((170.0405, 129.7279), (171.6000, 127.8471)),
            ((171.6000, 127.8471), (171.6000, 116.7951)),
            ((171.6000, 116.7951), (168.0212, 112.8950)),
        ],
    )
    removed += delete_vias_by_points(
        board,
        "L_COL6",
        [(170.0405, 129.7279), (168.0212, 112.8950), (167.5875, 128.7750)],
    )
    return removed


def remove_left_col_dangling_stubs(board: pcbnew.BOARD) -> int:
    removed = 0
    for net_name, pair in [
        ("L_COL1", ((69.3692, 67.9809), (70.2590, 67.9809))),
        ("L_COL4", ((126.8083, 68.5455), (128.7007, 68.5455))),
    ]:
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            removed += delete_tracks_by_pairs(board, net_name, layer, [pair])
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


def move_antenna_label_inboard(board: pcbnew.BOARD) -> int:
    moved = 0
    for drawing in board.GetDrawings():
        if drawing.GetLayer() != pcbnew.F_SilkS or not hasattr(drawing, "GetText"):
            continue
        if drawing.GetText() != "ANTENNA_INWARD":
            continue
        x, _y = mm(drawing.GetPosition().x), mm(drawing.GetPosition().y)
        new_x = x - 5.0 if x > 100.0 else x + 5.0
        drawing.SetPosition(vxy((new_x, 39.0)))
        moved += 1
    return moved


def reroute_l_col0_top_edge_clearance(board: pcbnew.BOARD) -> int:
    removed = delete_tracks_by_pairs(
        board,
        "L_COL0",
        pcbnew.B_Cu,
        [
            ((136.9425, 57.8900), (130.8735, 63.9590)),
            ((130.8735, 63.9590), (54.4797, 63.9590)),
            ((54.4797, 63.9590), (48.5250, 69.9137)),
        ],
    )
    if removed:
        add_track(board, "L_COL0", pcbnew.B_Cu, (136.9425, 57.8900), (130.8735, 64.8000))
        add_track(board, "L_COL0", pcbnew.B_Cu, (130.8735, 64.8000), (54.4797, 64.8000))
        add_track(board, "L_COL0", pcbnew.B_Cu, (54.4797, 64.8000), (48.5250, 69.9137))
    return removed


def reroute_l_col6_controller_edge_clearance(board: pcbnew.BOARD) -> int:
    removed = delete_tracks_by_pairs(
        board,
        "L_COL6",
        pcbnew.F_Cu,
        [
            ((152.1825, 57.8900), (162.8250, 68.5325)),
            ((162.8250, 68.5325), (162.8250, 71.6250)),
        ],
    )
    if removed:
        add_track(board, "L_COL6", pcbnew.F_Cu, (152.1825, 57.8900), (155.8000, 64.8000))
        add_track(board, "L_COL6", pcbnew.F_Cu, (155.8000, 64.8000), (162.8250, 71.6250))
    return removed


def reroute_l_col6_preflight_edge_clearance(board: pcbnew.BOARD) -> int:
    removed = delete_tracks_by_pairs(
        board,
        "L_COL6",
        pcbnew.F_Cu,
        [
            ((167.5875, 128.7750), (165.5656, 126.7531)),
            ((165.5656, 126.7531), (165.5656, 74.3656)),
            ((165.5656, 74.3656), (162.8250, 71.6250)),
        ],
    )
    if removed:
        add_track(board, "L_COL6", pcbnew.F_Cu, (167.5875, 128.7750), (164.9500, 126.1375))
        add_track(board, "L_COL6", pcbnew.F_Cu, (164.9500, 126.1375), (164.9500, 73.7500))
        add_track(board, "L_COL6", pcbnew.F_Cu, (164.9500, 73.7500), (162.8250, 71.6250))
    return removed


def remove_left_top_dangling_stubs(board: pcbnew.BOARD) -> int:
    removed = 0
    removed += delete_tracks_by_pairs(
        board,
        "L_ROW3",
        pcbnew.B_Cu,
        [((142.7562, 115.8405), (142.7562, 119.4127))],
    )
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        removed += delete_tracks_by_pairs(
            board,
            "L_ROW3",
            layer,
            [
                ((146.1762, 119.4047), (146.6978, 119.4047)),
                ((146.6978, 119.4047), (146.1762, 119.4047)),
            ],
        )
        removed += delete_tracks_by_pairs(
            board,
            "L_ROW1",
            layer,
            [((152.6080, 86.8769), (152.6080, 86.3449))],
        )
        removed += delete_tracks_by_pairs(
            board,
            "GND",
            layer,
            [((153.4827, 60.2271), (152.3865, 60.2271))],
        )
    removed += delete_tracks_by_pairs(
        board,
        "L_ROW3",
        pcbnew.B_Cu,
        [
            ((147.8090, 72.4219), (147.7431, 72.4878)),
            ((147.7431, 72.4878), (146.1951, 72.4878)),
        ],
    )
    removed += delete_vias_by_points(board, "L_ROW3", [(147.8090, 72.4219)])
    return removed


def reroute_l_col1_top_edge_clearance(board: pcbnew.BOARD) -> int:
    removed = 0
    removed += delete_tracks_by_pairs(
        board,
        "L_COL1",
        pcbnew.F_Cu,
        [
            ((69.1447, 62.7053), (69.1447, 70.0553)),
            ((69.1447, 62.7053), (69.1447, 62.7053)),
        ],
    )
    removed += delete_tracks_by_pairs(
        board,
        "L_COL1",
        pcbnew.B_Cu,
        [
            ((140.2601, 56.1276), (136.9403, 56.1276)),
            ((135.7158, 57.3521), (135.7158, 58.3447)),
            ((135.7158, 58.3447), (131.5717, 62.4888)),
            ((69.3612, 62.4888), (69.1447, 62.7053)),
            ((131.5717, 62.4888), (69.3612, 62.4888)),
            ((142.0225, 57.8900), (140.2601, 56.1276)),
            ((136.9403, 56.1276), (135.7158, 57.3521)),
        ],
    )
    removed += delete_vias_by_points(board, "L_COL1", [(69.1447, 62.7053)])
    if removed:
        add_track(board, "L_COL1", pcbnew.B_Cu, (142.0225, 57.8900), (139.9000, 60.0125))
        add_track(board, "L_COL1", pcbnew.B_Cu, (139.9000, 60.0125), (135.8000, 65.8000))
        add_track(board, "L_COL1", pcbnew.B_Cu, (135.8000, 65.8000), (69.1447, 65.8000))
        add_via(board, "L_COL1", (69.1447, 65.8000))
        add_track(board, "L_COL1", pcbnew.F_Cu, (69.1447, 65.8000), (69.1447, 70.0553))
    return removed


def remove_l_col2_top_dangling_stubs(board: pcbnew.BOARD) -> int:
    removed = 0
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        removed += delete_tracks_by_pairs(
            board,
            "L_COL2",
            layer,
            [
                ((89.9893, 63.1155), (95.9449, 63.1155)),
                ((95.9449, 63.1155), (89.9893, 63.1155)),
                ((95.9449, 63.1155), (95.9449, 63.1155)),
            ],
        )
    return removed


def postprocess_left(board: pcbnew.BOARD) -> dict[str, int]:
    return {
        "x3_top_edge_relief_points": apply_x3_top_edge_relief(board, "left"),
        "moved_antenna_label_inboard": move_antenna_label_inboard(board),
        "removed_l_col2_top_dangling_stubs": remove_l_col2_top_dangling_stubs(board),
        "moved_l_col6_edge_endpoints": move_l_col6_edge_segment(board),
        "rerouted_l_col6_d26_segments": reroute_l_col6_d26_clearance(board),
        "rerouted_l_col6_preflight_edge_clearance": reroute_l_col6_preflight_edge_clearance(board),
        "removed_left_col_dangling_stubs": remove_left_col_dangling_stubs(board),
        "removed_left_top_dangling_stubs": remove_left_top_dangling_stubs(board),
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


def reroute_r_col6_top_spacing(board: pcbnew.BOARD) -> int:
    removed = delete_tracks_by_pairs(
        board,
        "R_COL6",
        pcbnew.B_Cu,
        [
            ((81.8554, 60.1189), (102.7799, 60.1189)),
            ((102.7799, 60.1189), (106.3487, 63.6877)),
            ((106.3487, 63.6877), (167.4032, 63.6877)),
            ((167.4032, 63.6877), (169.8855, 63.6877)),
        ],
    )
    removed += delete_tracks_by_pairs(
        board,
        "R_COL6",
        pcbnew.F_Cu,
        [
            ((167.4032, 63.6877), (169.8855, 63.6877)),
            ((169.8855, 63.6877), (167.4032, 63.6877)),
            ((167.4032, 63.6877), (169.8855, 66.1700)),
        ],
    )
    removed += delete_vias_by_points(board, "R_COL6", [(167.4032, 63.6877)])
    if removed:
        add_track(board, "R_COL6", pcbnew.B_Cu, (81.8554, 60.1189), (102.7799, 65.8000))
        add_track(board, "R_COL6", pcbnew.B_Cu, (102.7799, 65.8000), (167.4032, 65.8000))
        add_via(board, "R_COL6", (167.4032, 65.8000))
        add_track(board, "R_COL6", pcbnew.F_Cu, (167.4032, 65.8000), (169.8855, 66.1700))
    return removed


def reroute_r_col7_top_edge_clearance(board: pcbnew.BOARD) -> int:
    removed = delete_tracks_by_pairs(
        board,
        "R_COL7",
        pcbnew.B_Cu,
        [
            ((91.4370, 59.5684), (94.7973, 62.9287)),
            ((94.7973, 62.9287), (192.8019, 62.9287)),
            ((192.8019, 62.9287), (194.9473, 65.0741)),
        ],
    )
    if removed:
        add_track(board, "R_COL7", pcbnew.B_Cu, (91.4370, 59.5684), (98.4686, 66.6000))
        add_track(board, "R_COL7", pcbnew.B_Cu, (98.4686, 66.6000), (192.8019, 66.6000))
        add_track(board, "R_COL7", pcbnew.B_Cu, (192.8019, 66.6000), (194.9473, 65.0741))
    return removed


def reroute_r_col0_preflight_edge_clearance(board: pcbnew.BOARD) -> int:
    removed = delete_tracks_by_pairs(
        board,
        "R_COL0",
        pcbnew.F_Cu,
        [((65.3748, 59.5311), (57.6500, 67.2559))],
    )
    if removed:
        add_track(board, "R_COL0", pcbnew.F_Cu, (65.3748, 59.5311), (65.3748, 67.2559))
        add_track(board, "R_COL0", pcbnew.F_Cu, (65.3748, 67.2559), (57.6500, 67.2559))
    return removed


def reroute_right_battery_slot_clearance(board: pcbnew.BOARD) -> int:
    removed = 0
    removed += delete_tracks_by_pairs(
        board,
        "R_COL0",
        pcbnew.F_Cu,
        [
            ((66.5108, 42.1292), (66.5108, 58.5174)),
            ((68.5300, 40.1100), (66.5108, 42.1292)),
            ((66.5108, 58.5174), (57.6500, 67.3782)),
        ],
    )
    if removed:
        add_track(board, "R_COL0", pcbnew.F_Cu, (68.5300, 40.1100), (63.0000, 42.7000))
        add_track(board, "R_COL0", pcbnew.F_Cu, (63.0000, 42.7000), (63.0000, 58.0000))
        add_track(board, "R_COL0", pcbnew.F_Cu, (63.0000, 58.0000), (57.6500, 67.3782))

    row_removed = delete_tracks_by_pairs(
        board,
        "R_ROW4",
        pcbnew.F_Cu,
        [
            ((67.3027, 46.4173), (73.6100, 40.1100)),
            ((67.3027, 58.6427), (67.3027, 46.4173)),
        ],
    )
    if row_removed:
        add_track(board, "R_ROW4", pcbnew.F_Cu, (73.6100, 40.1100), (75.8000, 42.3000))
        add_track(board, "R_ROW4", pcbnew.F_Cu, (75.8000, 42.3000), (75.8000, 59.1167))
        add_track(board, "R_ROW4", pcbnew.F_Cu, (75.8000, 59.1167), (67.7767, 59.1167))
    return removed + row_removed


def reroute_r_col7_top_edge_clearance_current(board: pcbnew.BOARD) -> int:
    removed = 0
    removed += delete_tracks_by_pairs(
        board,
        "R_COL7",
        pcbnew.F_Cu,
        [
            ((188.2464, 62.9205), (188.2464, 66.4901)),
            ((188.2464, 62.9205), (188.2464, 62.9205)),
        ],
    )
    removed += delete_tracks_by_pairs(
        board,
        "R_COL7",
        pcbnew.B_Cu,
        [
            ((188.2464, 62.9205), (187.3198, 61.9939)),
            ((187.3198, 61.9939), (104.9429, 61.9939)),
            ((104.9429, 61.9939), (99.1445, 56.1955)),
        ],
    )
    removed += delete_vias_by_points(board, "R_COL7", [(188.2464, 62.9205)])
    if removed:
        add_track(board, "R_COL7", pcbnew.B_Cu, (99.1445, 56.1955), (104.9429, 66.6000))
        add_track(board, "R_COL7", pcbnew.B_Cu, (104.9429, 66.6000), (188.2464, 66.6000))
        add_via(board, "R_COL7", (188.2464, 66.6000))
        add_track(board, "R_COL7", pcbnew.F_Cu, (188.2464, 66.6000), (193.3813, 71.6250))
    return removed


def remove_r_col6_tiny_dangling_stub(board: pcbnew.BOARD) -> int:
    return delete_tracks_by_pairs(
        board,
        "R_COL6",
        pcbnew.B_Cu,
        [((173.3584, 142.3311), (173.4101, 142.3311))],
    )


def remove_right_top_dangling_stubs(board: pcbnew.BOARD) -> int:
    removed = 0
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        removed += delete_tracks_by_pairs(
            board,
            "R_COL3",
            layer,
            [
                ((104.6874, 55.2641), (104.6874, 59.9159)),
                ((104.6874, 59.9159), (104.6874, 55.2641)),
            ],
        )
        removed += delete_tracks_by_pairs(
            board,
            "R_COL2",
            layer,
            [
                ((89.9856, 66.2609), (93.6855, 66.2609)),
                ((93.6855, 66.2609), (89.9856, 66.2609)),
            ],
        )
        removed += delete_tracks_by_pairs(
            board,
            "R_COL5",
            layer,
            [
                ((146.5588, 63.4602), (152.9000, 63.4602)),
                ((152.9000, 63.4602), (146.5588, 63.4602)),
            ],
        )
    removed += delete_tracks_by_pairs(
        board,
        "R_ROW1",
        pcbnew.B_Cu,
        [((164.2250, 88.9750), (165.3621, 87.8379))],
    )
    removed += delete_tracks_by_pairs(
        board,
        "RST",
        pcbnew.F_Cu,
        [((67.6418, 55.6664), (67.6418, 56.4972))],
    )
    removed += delete_tracks_by_pairs(
        board,
        "RST",
        pcbnew.B_Cu,
        [((67.6418, 55.6664), (67.6418, 56.4972))],
    )
    removed += delete_tracks_by_pairs(
        board,
        "GND",
        pcbnew.F_Cu,
        [((77.4200, 54.0303), (78.0764, 54.0303))],
    )
    removed += delete_tracks_by_pairs(
        board,
        "GND",
        pcbnew.B_Cu,
        [((77.4200, 54.0303), (78.0764, 54.0303))],
    )
    removed += delete_tracks_by_pairs(
        board,
        "R_COL3",
        pcbnew.B_Cu,
        [((103.8811, 60.7222), (105.1318, 61.9729))],
    )
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        removed += delete_tracks_by_pairs(
            board,
            "RK42_D",
            layer,
            [((157.0937, 145.8877), (157.6143, 145.8877))],
        )
        removed += delete_tracks_by_pairs(
            board,
            "R_COL4",
            layer,
            [((131.6720, 67.3486), (131.6720, 67.9616))],
        )
        removed += delete_tracks_by_pairs(
            board,
            "R_COL6",
            layer,
            [((167.4032, 63.6877), (169.8855, 63.6877))],
        )
        removed += delete_tracks_by_pairs(
            board,
            "R_COL7",
            layer,
            [
                ((191.2240, 63.7205), (191.2240, 64.9740)),
                ((89.9856, 64.0882), (89.9856, 64.9740)),
            ],
        )
    removed += delete_tracks_by_pairs(
        board,
        "R_ROW3",
        pcbnew.F_Cu,
        [
            ((98.9968, 118.7839), (99.0408, 118.7839)),
            ((98.9968, 124.5923), (98.9968, 125.7800)),
        ],
    )
    removed += delete_tracks_by_pairs(
        board,
        "R_ROW3",
        pcbnew.B_Cu,
        [((98.9968, 124.5923), (98.9968, 125.7800))],
    )
    return removed


def postprocess_right(board: pcbnew.BOARD) -> dict[str, int]:
    top_edge_relief_points = apply_x3_top_edge_relief(board, "right")
    removed = remove_stubs_by_length(
        board,
        [
            ("R_ROW1", pcbnew.F_Cu, 0.7685),
            ("R_ROW1", pcbnew.B_Cu, 0.7685),
            ("R_ROW4", pcbnew.F_Cu, 0.6766),
            ("R_ROW4", pcbnew.F_Cu, 1.2658),
            ("R_ROW4", pcbnew.B_Cu, 0.6766),
            ("R_ROW4", pcbnew.B_Cu, 1.2658),
        ],
    )
    removed += delete_tracks_by_pairs(
        board,
        "R_ROW1",
        pcbnew.F_Cu,
        [((166.4173, 88.7529), (165.8703, 89.2999))],
    )
    add_track(board, "R_ROW1", pcbnew.B_Cu, (164.2250, 88.9750), (165.3621, 87.8379))
    removed += delete_tracks_by_pairs(
        board,
        "R_ROW4",
        pcbnew.B_Cu,
            [((63.7341, 143.9637), (64.2125, 144.4421))],
    )
    r_col0_edge = reroute_r_col0_preflight_edge_clearance(board)
    r_col6_stub = remove_r_col6_tiny_dangling_stub(board)
    right_top_stubs = remove_right_top_dangling_stubs(board)
    return {
        "x3_top_edge_relief_points": top_edge_relief_points,
        "moved_antenna_label_inboard": move_antenna_label_inboard(board),
        "removed_freerouting_stubs": removed,
        "rerouted_r_col0_preflight_edge_clearance": r_col0_edge,
        "removed_r_col6_tiny_dangling_stub": r_col6_stub,
        "restored_required_row_bridges": 1,
        "removed_right_top_dangling_stubs": right_top_stubs,
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
