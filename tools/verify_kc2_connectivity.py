from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pcbnew

from tools import generate_kc2_pcbs as gen

Node = tuple[int, int, int]


class DisjointSet:
    def __init__(self) -> None:
        self.parent: dict[Node, Node] = {}

    def add(self, item: Node) -> None:
        self.parent.setdefault(item, item)

    def find(self, item: Node) -> Node:
        self.add(item)
        root = item
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[item] != item:
            item, self.parent[item] = self.parent[item], root
        return root

    def union(self, a: Node, b: Node) -> None:
        self.add(a)
        self.add(b)
        self.parent[self.find(b)] = self.find(a)


def coordinate_key(vec: pcbnew.VECTOR2I) -> tuple[int, int]:
    return round(pcbnew.ToMM(vec.x) * 1000), round(pcbnew.ToMM(vec.y) * 1000)


def node_key(vec: pcbnew.VECTOR2I, layer: int) -> Node:
    x, y = coordinate_key(vec)
    return x, y, layer


def copper_pad_nodes(pad: pcbnew.PAD) -> list[Node]:
    layers = []
    layer_set = pad.GetLayerSet()
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        if layer_set.Contains(layer):
            layers.append(layer)
    return [node_key(pad.GetPosition(), layer) for layer in layers]


def pin_map(side: str) -> dict[str, str]:
    if side == "left":
        return {
            "D3": "L_COL0",
            "D5": "L_COL1",
            "D4": "L_COL2",
            "D6": "L_COL3",
            "D7": "L_COL4",
            "D8": "L_COL5",
            "D9": "L_COL6",
            "D10": "L_ROW0",
            "D16": "L_ROW1",
            "D14": "L_ROW2",
            "D15": "L_ROW3",
            "D18": "L_ROW4",
            "RST": "RST",
        }
    if side == "right":
        return {
            "D9": "R_COL0",
            "D10": "R_COL1",
            "D16": "R_COL2",
            "D14": "R_COL3",
            "D15": "R_COL4",
            "D18": "R_COL5",
            "D19": "R_COL6",
            "D20": "R_COL8",
            "D21": "R_COL7",
            "D3": "R_ROW0",
            "D4": "R_ROW1",
            "D5": "R_ROW2",
            "D2": "R_ROW3",
            "D7": "R_ROW4",
            "RST": "RST",
        }
    raise ValueError(f"Unknown side: {side}")


def detect_side(board_path: Path) -> str:
    name = board_path.name.lower()
    if "_left" in name:
        return "left"
    if "_right" in name:
        return "right"
    raise ValueError(f"Cannot detect side from board path: {board_path}")


def expected_keys(side: str) -> list[gen.Key]:
    if side == "left":
        return gen.make_left_keys_no_stab()
    if side == "right":
        return gen.make_right_keys_no_stab()
    raise ValueError(f"Unknown side: {side}")


def footprints_by_ref(board: pcbnew.BOARD) -> dict[str, pcbnew.FOOTPRINT]:
    return {fp.GetReference(): fp for fp in board.GetFootprints()}


def pads(fp: pcbnew.FOOTPRINT, number: str) -> list[pcbnew.PAD]:
    return [pad for pad in fp.Pads() if pad.GetNumber() == number]


def require_pad_net(
    errors: list[str],
    fp: pcbnew.FOOTPRINT,
    number: str,
    expected_net: str,
) -> list[Node]:
    found = pads(fp, number)
    if not found:
        errors.append(f"{fp.GetReference()} has no pad {number}")
        return []
    out: list[Node] = []
    for pad in found:
        net = pad.GetNetname()
        if net != expected_net:
            errors.append(f"{fp.GetReference()} pad {number} net is {net!r}, expected {expected_net!r}")
        nodes = copper_pad_nodes(pad)
        if not nodes:
            errors.append(f"{fp.GetReference()} pad {number} has no F/B copper layer")
        out.extend(nodes)
    return out


def build_connectivity(board: pcbnew.BOARD) -> dict[str, DisjointSet]:
    graphs: dict[str, DisjointSet] = defaultdict(DisjointSet)
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            net = pad.GetNetname()
            if net:
                nodes = copper_pad_nodes(pad)
                for node in nodes:
                    graphs[net].add(node)
                for a, b in zip(nodes, nodes[1:]):
                    graphs[net].union(a, b)
    for track in board.GetTracks():
        net = track.GetNetname()
        if not net:
            continue
        if isinstance(track, pcbnew.PCB_VIA):
            f_node = node_key(track.GetPosition(), pcbnew.F_Cu)
            b_node = node_key(track.GetPosition(), pcbnew.B_Cu)
            graphs[net].union(f_node, b_node)
        elif hasattr(track, "GetStart") and hasattr(track, "GetEnd"):
            layer = track.GetLayer()
            graphs[net].union(node_key(track.GetStart(), layer), node_key(track.GetEnd(), layer))
    return graphs


def require_connected(
    errors: list[str],
    graphs: dict[str, DisjointSet],
    net: str,
    points: list[Node],
    label: str,
) -> None:
    if len(points) < 2:
        errors.append(f"{label} has fewer than two connection points")
        return
    graph = graphs.get(net)
    if graph is None:
        errors.append(f"{label} net {net!r} has no graph")
        return
    roots = {graph.find(point) for point in points}
    if len(roots) != 1:
        errors.append(f"{label} net {net!r} is split into {len(roots)} islands")


def verify_board(board_path: Path) -> list[str]:
    side = detect_side(board_path)
    keys = expected_keys(side)
    board = pcbnew.LoadBoard(str(board_path))
    fps = footprints_by_ref(board)
    graphs = build_connectivity(board)
    errors: list[str] = []

    expected_count = 32 if side == "left" else 45
    if len(keys) != expected_count:
        errors.append(f"{side} expected key model count is {len(keys)}, expected {expected_count}")
    if max(key.w_u for key in keys) >= 2.0:
        errors.append(f"{side} X3 layout still contains a >=2U key")

    switch_refs = [ref for ref in fps if ref.startswith("SW") and ref[2:].isdigit()]
    diode_refs = [ref for ref in fps if ref.startswith("D") and ref[1:].isdigit()]
    stab_refs = [ref for ref in fps if ref.startswith("STAB")]
    if len(switch_refs) != expected_count:
        errors.append(f"{side} has {len(switch_refs)} matrix switches, expected {expected_count}")
    if len(diode_refs) != expected_count:
        errors.append(f"{side} has {len(diode_refs)} matrix diodes, expected {expected_count}")
    if stab_refs:
        errors.append(f"{side} has stabilizer footprints: {', '.join(sorted(stab_refs))}")

    col_prefix = "L_COL" if side == "left" else "R_COL"
    row_prefix = "L_ROW" if side == "left" else "R_ROW"
    local_prefix = "L" if side == "left" else "R"
    row_points: dict[int, list[Node]] = defaultdict(list)
    col_points: dict[int, list[Node]] = defaultdict(list)

    for idx, key in enumerate(keys, start=1):
        sw_ref = f"SW{idx}"
        d_ref = f"D{idx}"
        sw = fps.get(sw_ref)
        diode = fps.get(d_ref)
        if sw is None:
            errors.append(f"Missing {sw_ref}")
            continue
        if diode is None:
            errors.append(f"Missing {d_ref}")
            continue

        col_net = f"{col_prefix}{key.col}"
        row_net = f"{row_prefix}{key.row}"
        local_net = f"{local_prefix}K{idx:02d}_D"
        if sw.GetValue() != f"KEY_{idx:02d}":
            errors.append(f"{sw_ref} value is {sw.GetValue()!r}, expected KEY_{idx:02d}")

        sw_col = require_pad_net(errors, sw, "1", col_net)
        sw_local = require_pad_net(errors, sw, "2", local_net)
        d_row = require_pad_net(errors, diode, "1", row_net)
        d_local = require_pad_net(errors, diode, "2", local_net)
        col_points[key.col].extend(sw_col)
        row_points[key.row].extend(d_row)
        require_connected(errors, graphs, local_net, sw_local + d_local, f"{side} {sw_ref}/{d_ref} local")

    inverse_pin_map = {net: pin for pin, net in pin_map(side).items()}
    controller = fps.get("U1")
    if controller is None:
        errors.append("Missing U1 controller")
    else:
        for row, points in row_points.items():
            net = f"{row_prefix}{row}"
            pin = inverse_pin_map.get(net)
            if pin is None:
                errors.append(f"{net} has no controller pin mapping")
                continue
            controller_points = require_pad_net(errors, controller, pin, net)
            require_connected(errors, graphs, net, points + controller_points, f"{side} {net}")
        for col, points in col_points.items():
            net = f"{col_prefix}{col}"
            pin = inverse_pin_map.get(net)
            if pin is None:
                errors.append(f"{net} has no controller pin mapping")
                continue
            controller_points = require_pad_net(errors, controller, pin, net)
            require_connected(errors, graphs, net, points + controller_points, f"{side} {net}")

        rst_points = []
        tact = fps.get("SW_RST1")
        if tact is None:
            errors.append("Missing SW_RST1")
        else:
            for pad in tact.Pads():
                if pad.GetNetname() == "RST":
                    rst_points.extend(copper_pad_nodes(pad))
        rst_points.extend(require_pad_net(errors, controller, "RST", "RST"))
        require_connected(errors, graphs, "RST", rst_points, f"{side} RST")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify KC2 X3 generated matrix connectivity.")
    parser.add_argument(
        "boards",
        nargs="*",
        type=Path,
        default=[
            ROOT / "hardware" / "kicad" / "kc2_left-x3" / "kc2_left-x3.kicad_pcb",
            ROOT / "hardware" / "kicad" / "kc2_right-x3" / "kc2_right-x3.kicad_pcb",
        ],
    )
    args = parser.parse_args()

    all_errors: list[str] = []
    for board_path in args.boards:
        errors = verify_board(board_path)
        if errors:
            all_errors.extend(f"{board_path}: {error}" for error in errors)
        else:
            print(f"PASS {board_path}")
    if all_errors:
        for error in all_errors:
            print(f"FAIL {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
