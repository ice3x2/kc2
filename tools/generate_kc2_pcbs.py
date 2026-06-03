from __future__ import annotations

import json
import math
import shutil
from dataclasses import dataclass
from pathlib import Path

import pcbnew


ROOT = Path(__file__).resolve().parents[1]
KICAD_ROOT = ROOT / "hardware" / "kicad"
KICAD_SHARE = Path(r"C:\Program Files\KiCad\9.0\share\kicad")

SWITCH_LIB = ROOT / "third_party" / "key-switches.pretty"
SWITCH_FP = "SW_Kailh_Choc_V1V2_THT_Hybrid"
KC2_FP_LIB = ROOT / "third_party" / "kc2.pretty"
DIODE_LIB = KICAD_SHARE / "footprints" / "Diode_SMD.pretty"
DIODE_FP = "D_SOD-123"
TACT_LIB = KC2_FP_LIB
TACT_FP = "SW_NW3_A06_B3_SMD"
MOUNT_LIB = KICAD_SHARE / "footprints" / "MountingHole.pretty"
MOUNT_FP = "MountingHole_2.2mm_M2"

UNIT = 19.05
GENERAL_MARGIN = 5.5
INNER_MARGIN = 2.8
EDGE_WIDTH = 0.10
TRACK_WIDTH = 0.25
POWER_TRACK_WIDTH = 0.75
VIA_SIZE = 0.60
VIA_DRILL = 0.30

CONTROLLER_LEN = 33.8
CONTROLLER_W = 18.3
SOCKET_ROW_SPACING = 17.78
PIN_PITCH = 2.54
PIN_COUNT = 12
PIN_SPAN = PIN_PITCH * (PIN_COUNT - 1)
CONTROLLER_TAB_W = 70.0
CONTROLLER_TAB_H = 28.0
CONTROLLER_CENTER_Y = -19.0
LEFT_CONTROLLER_JOIN_EDGE_RECESS = 14.0
RIGHT_CONTROLLER_JOIN_EDGE_RECESS = 12.0
ANTENNA_KEEP_START_FROM_CENTER = PIN_SPAN / 2.0 + 4.0
ANTENNA_KEEP_LENGTH = 10.0


@dataclass(frozen=True)
class Key:
    label: str
    row: int
    col: int
    x_u: float
    y_u: float
    w_u: float = 1.0
    h_u: float = 1.0

    @property
    def cx(self) -> float:
        return (self.x_u + self.w_u / 2.0) * UNIT

    @property
    def cy(self) -> float:
        return (self.y_u + self.h_u / 2.0) * UNIT

    @property
    def rect(self) -> tuple[float, float, float, float]:
        return (
            self.x_u * UNIT,
            self.y_u * UNIT,
            (self.x_u + self.w_u) * UNIT,
            (self.y_u + self.h_u) * UNIT,
        )


def mm(value: float) -> int:
    return pcbnew.FromMM(float(value))


def vxy(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(mm(x), mm(y))


def mask_only_layers() -> pcbnew.LSET:
    layers = pcbnew.LSET()
    layers.AddLayer(pcbnew.F_Mask)
    layers.AddLayer(pcbnew.B_Mask)
    return layers


def copper_layers() -> pcbnew.LSET:
    layers = pcbnew.LSET()
    layers.AddLayer(pcbnew.F_Cu)
    layers.AddLayer(pcbnew.B_Cu)
    return layers


def to_mm_vec(vec: pcbnew.VECTOR2I) -> tuple[float, float]:
    return pcbnew.ToMM(vec.x), pcbnew.ToMM(vec.y)


def add_net(board: pcbnew.BOARD, cache: dict[str, pcbnew.NETINFO_ITEM], name: str) -> pcbnew.NETINFO_ITEM:
    if name not in cache:
        net = pcbnew.NETINFO_ITEM(board, name)
        board.Add(net)
        cache[name] = net
    return cache[name]


def set_pad_net(fp: pcbnew.FOOTPRINT, pad_number: str, net: pcbnew.NETINFO_ITEM) -> None:
    for pad in fp.Pads():
        if pad.GetNumber() == pad_number:
            pad.SetNet(net)


def pad_positions(fp: pcbnew.FOOTPRINT, pad_number: str) -> list[tuple[float, float]]:
    return [to_mm_vec(pad.GetPosition()) for pad in fp.Pads() if pad.GetNumber() == pad_number]


def pads_by_number(fp: pcbnew.FOOTPRINT, pad_number: str) -> list[pcbnew.PAD]:
    return [pad for pad in fp.Pads() if pad.GetNumber() == pad_number]


def convert_empty_switch_pads_to_npth(fp: pcbnew.FOOTPRINT) -> None:
    for pad in fp.Pads():
        if pad.GetNumber() == "":
            pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
            pad.SetNetCode(0)
            pad.SetLayerSet(mask_only_layers())


def add_track(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    start: tuple[float, float],
    end: tuple[float, float],
    layer: int,
    width: float = TRACK_WIDTH,
) -> None:
    if abs(start[0] - end[0]) < 0.001 and abs(start[1] - end[1]) < 0.001:
        return
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(vxy(*start))
    track.SetEnd(vxy(*end))
    track.SetLayer(layer)
    track.SetWidth(mm(width))
    track.SetNet(net)
    board.Add(track)


def add_via(board: pcbnew.BOARD, net: pcbnew.NETINFO_ITEM, at: tuple[float, float]) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetPosition(vxy(*at))
    via.SetWidth(mm(VIA_SIZE))
    via.SetDrill(mm(VIA_DRILL))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    via.SetNet(net)
    board.Add(via)


def add_polyline(
    board: pcbnew.BOARD,
    points: list[tuple[float, float]],
    layer: int,
    width: float = EDGE_WIDTH,
    closed: bool = False,
) -> None:
    if closed:
        points = points + [points[0]]
    for start, end in zip(points, points[1:]):
        shape = pcbnew.PCB_SHAPE(board)
        shape.SetShape(pcbnew.SHAPE_T_SEGMENT)
        shape.SetStart(vxy(*start))
        shape.SetEnd(vxy(*end))
        shape.SetLayer(layer)
        shape.SetWidth(mm(width))
        board.Add(shape)


def add_rect_lines(
    board: pcbnew.BOARD,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    layer: int,
    width: float = 0.12,
) -> None:
    add_polyline(board, [(x1, y1), (x2, y1), (x2, y2), (x1, y2)], layer, width, closed=True)


def add_board_text(
    board: pcbnew.BOARD,
    text: str,
    x: float,
    y: float,
    layer: int = pcbnew.F_SilkS,
    size: float = 1.2,
    thickness: float = 0.15,
    angle_deg: float = 0.0,
) -> None:
    item = pcbnew.PCB_TEXT(board)
    item.SetText(text)
    item.SetPosition(vxy(x, y))
    item.SetLayer(layer)
    item.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    item.SetTextThickness(mm(thickness))
    item.SetTextAngleDegrees(angle_deg)
    board.Add(item)


def load_footprint(
    board: pcbnew.BOARD,
    lib: Path,
    name: str,
    ref: str,
    value: str,
    x: float,
    y: float,
    rotation: float = 0.0,
    bottom: bool = False,
) -> pcbnew.FOOTPRINT:
    fp = pcbnew.FootprintLoad(str(lib), name)
    if fp is None:
        raise RuntimeError(f"Failed to load footprint {lib}:{name}")
    fp.SetReference(ref)
    fp.SetValue(value)
    fp.SetPosition(vxy(x, y))
    fp.SetOrientationDegrees(rotation)
    board.Add(fp)
    if bottom:
        fp.Flip(fp.GetPosition(), False)
    return fp


def make_left_keys() -> list[Key]:
    rows = [
        [("~", 1.0), ("1", 1.0), ("2", 1.0), ("3", 1.0), ("4", 1.0), ("5", 1.0), ("6", 1.0)],
        [("TAB", 1.5), ("Q", 1.0), ("W", 1.0), ("E", 1.0), ("R", 1.0), ("T", 1.0)],
        [("Caps", 1.75), ("A", 1.0), ("S", 1.0), ("D", 1.0), ("F", 1.0), ("G", 1.0)],
        [("Shift", 2.25), ("Z", 1.0), ("X", 1.0), ("C", 1.0), ("V", 1.0), ("B", 1.0)],
        [("Ctrl", 1.25), ("Win", 1.25), ("Alt", 1.25), ("Fn", 1.25), ("Space", 2.25)],
    ]
    keys: list[Key] = []
    for row_idx, row in enumerate(rows):
        x = 0.0
        for col_idx, (label, width) in enumerate(row):
            keys.append(Key(label, row_idx, col_idx, x, float(row_idx), width))
            x += width
    return keys


def make_right_keys() -> list[Key]:
    rows = [
        (0.50, [("7", 1.0), ("8", 1.0), ("9", 1.0), ("0", 1.0), ("-", 1.0), ("=", 1.0), ("BSPC", 2.25), ("DEL", 1.0)]),
        (0.00, [("Y", 1.0), ("U", 1.0), ("I", 1.0), ("O", 1.0), ("P", 1.0), ("[", 1.0), ("]", 1.0), ("\\", 1.75), ("Home", 1.0)]),
        (0.25, [("H", 1.0), ("J", 1.0), ("K", 1.0), ("L", 1.0), (";", 1.0), ("'", 1.0), ("Enter", 2.5), ("PgUp", 1.0)]),
        (0.75, [("N", 1.0), ("M", 1.0), (",", 1.0), (".", 1.0), ("/", 1.0), ("RShift", 2.0), ("Up", 1.0), ("PgDn", 1.0)]),
        (0.75, [("B_RH", 1.0), ("Space", 2.0), ("RAlt", 1.0), ("Fn", 1.0), ("RCtrl", 1.0), ("Left", 1.0), ("Down", 1.0), ("Right", 1.0)]),
    ]
    keys: list[Key] = []
    for row_idx, (x0, row) in enumerate(rows):
        x = x0
        for col_idx, (label, width) in enumerate(row):
            keys.append(Key(label, row_idx, col_idx, x, float(row_idx), width))
            x += width
    return keys


def row_extents(keys: list[Key]) -> dict[int, tuple[float, float, float, float]]:
    out: dict[int, tuple[float, float, float, float]] = {}
    for row in sorted({k.row for k in keys}):
        rects = [k.rect for k in keys if k.row == row]
        out[row] = (
            min(r[0] for r in rects),
            min(r[1] for r in rects),
            max(r[2] for r in rects),
            max(r[3] for r in rects),
        )
    return out


def controller_center_x(keys: list[Key], side: str) -> float:
    ext = row_extents(keys)
    if side == "left":
        inner_edge = max(r[2] for r in ext.values()) + INNER_MARGIN
        return inner_edge - LEFT_CONTROLLER_JOIN_EDGE_RECESS - CONTROLLER_TAB_W / 2.0
    if side == "right":
        inner_edge = min(r[0] for r in ext.values()) - INNER_MARGIN
        return inner_edge + RIGHT_CONTROLLER_JOIN_EDGE_RECESS + CONTROLLER_TAB_W / 2.0
    raise ValueError(f"Unknown side: {side}")


def raw_outline(keys: list[Key], side: str, ctrl_cx: float) -> list[tuple[float, float]]:
    ext = row_extents(keys)
    rows = sorted(ext)
    left_margin = INNER_MARGIN if side == "right" else GENERAL_MARGIN
    right_margin = INNER_MARGIN if side == "left" else GENERAL_MARGIN

    lefts = {r: ext[r][0] - left_margin for r in rows}
    rights = {r: ext[r][2] + right_margin for r in rows}
    top_y = min(ext[r][1] for r in rows) - GENERAL_MARGIN
    bottom_y = max(ext[r][3] for r in rows) + GENERAL_MARGIN

    tab_left = ctrl_cx - CONTROLLER_TAB_W / 2.0
    tab_right = ctrl_cx + CONTROLLER_TAB_W / 2.0
    tab_top = CONTROLLER_CENTER_Y - CONTROLLER_TAB_H / 2.0

    r0 = rows[0]
    top_start = min(lefts[r0], tab_left)

    pts: list[tuple[float, float]] = []
    pts.append((top_start, top_y))
    if tab_left > top_start:
        pts.append((tab_left, top_y))
    pts.extend([(tab_left, tab_top), (tab_right, tab_top), (tab_right, top_y)])
    pts.append((rights[r0], top_y))

    for r in rows:
        y_bottom = ext[r][3]
        pts.append((rights[r], y_bottom))
        nxt = r + 1
        if nxt in rights:
            pts.append((rights[nxt], y_bottom))
    pts.append((rights[rows[-1]], bottom_y))
    pts.append((lefts[rows[-1]], bottom_y))

    for r in reversed(rows):
        y_top = ext[r][1]
        pts.append((lefts[r], y_top))
        prv = r - 1
        if prv in lefts:
            pts.append((lefts[prv], y_top))

    return remove_duplicate_points(pts)


def remove_duplicate_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for p in points:
        if not out or abs(out[-1][0] - p[0]) > 0.001 or abs(out[-1][1] - p[1]) > 0.001:
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < 0.001 and abs(out[0][1] - out[-1][1]) < 0.001:
        out.pop()
    return out


def rounded_polygon(points: list[tuple[float, float]], radius: float = 2.0, steps: int = 5) -> list[tuple[float, float]]:
    rounded: list[tuple[float, float]] = []
    n = len(points)
    for i, p in enumerate(points):
        prev = points[(i - 1) % n]
        nxt = points[(i + 1) % n]
        vin = (p[0] - prev[0], p[1] - prev[1])
        vout = (nxt[0] - p[0], nxt[1] - p[1])
        lin = math.hypot(*vin)
        lout = math.hypot(*vout)
        if lin < 0.001 or lout < 0.001:
            continue
        d = min(radius, lin * 0.45, lout * 0.45)
        p1 = (p[0] - vin[0] / lin * d, p[1] - vin[1] / lin * d)
        p2 = (p[0] + vout[0] / lout * d, p[1] + vout[1] / lout * d)
        # Quadratic trim is not a mathematically exact fillet, but it gives a
        # dense rounded Edge.Cuts contour without introducing arc-direction risk.
        for s in range(steps + 1):
            t = s / steps
            qx = (1 - t) * (1 - t) * p1[0] + 2 * (1 - t) * t * p[0] + t * t * p2[0]
            qy = (1 - t) * (1 - t) * p1[1] + 2 * (1 - t) * t * p[1] + t * t * p2[1]
            rounded.append((qx, qy))
    return remove_duplicate_points(rounded)


def shift_points(points: list[tuple[float, float]], dx: float, dy: float) -> list[tuple[float, float]]:
    return [(x + dx, y + dy) for x, y in points]


def make_project_file(project_dir: Path, name: str) -> None:
    data = {
        "board": {
            "design_settings": {
                "defaults": {
                    "board_outline_line_width": 0.05,
                    "copper_line_width": TRACK_WIDTH,
                    "silk_line_width": 0.1,
                    "track_width": TRACK_WIDTH,
                    "via_diameter": VIA_SIZE,
                    "via_drill": VIA_DRILL,
                    "zones": {"min_clearance": 0.2},
                },
                "rule_severities": {
                    "courtyards_overlap": "warning",
                    "silk_over_copper": "warning",
                    "silk_edge_clearance": "warning",
                },
                "rules": {
                    "min_clearance": 0.20,
                    "min_hole_clearance": 0.25,
                    "min_through_hole_diameter": 0.30,
                    "min_track_width": 0.15,
                    "min_via_diameter": 0.45,
                    "min_via_drill": 0.20,
                },
            }
        },
        "boards": [],
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": f"{name}.kicad_pro", "version": 1},
        "net_settings": {
            "classes": [
                {
                    "name": "Default",
                    "bus_width": 12.0,
                    "clearance": 0.20,
                    "diff_pair_gap": 0.25,
                    "diff_pair_via_gap": 0.25,
                    "diff_pair_width": 0.20,
                    "line_style": 0,
                    "microvia_diameter": 0.30,
                    "microvia_drill": 0.10,
                    "pcb_color": "rgba(0, 0, 0, 0.000)",
                    "schematic_color": "rgba(0, 0, 0, 0.000)",
                    "track_width": TRACK_WIDTH,
                    "via_diameter": VIA_SIZE,
                    "via_drill": VIA_DRILL,
                    "wire_width": 6.0,
                },
                {
                    "name": "Power",
                    "bus_width": 12.0,
                    "clearance": 0.20,
                    "diff_pair_gap": 0.25,
                    "diff_pair_via_gap": 0.25,
                    "diff_pair_width": 0.20,
                    "line_style": 0,
                    "microvia_diameter": 0.30,
                    "microvia_drill": 0.10,
                    "pcb_color": "rgba(0, 0, 0, 0.000)",
                    "schematic_color": "rgba(0, 0, 0, 0.000)",
                    "track_width": POWER_TRACK_WIDTH,
                    "via_diameter": 0.8,
                    "via_drill": 0.4,
                    "wire_width": 6.0,
                },
            ],
            "meta": {"version": 3},
            "net_colors": None,
            "netclass_assignments": [
                {"netclass": "Power", "pattern": "BAT+"},
                {"netclass": "Power", "pattern": "BAT-"},
                {"netclass": "Power", "pattern": "NN_B+"},
                {"netclass": "Power", "pattern": "NN_B-"},
            ],
        },
        "project": {"files": []},
        "schematic": {},
        "sheets": [],
        "text_variables": {},
    }
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / f"{name}.kicad_pro").write_text(json.dumps(data, indent=2), encoding="utf-8")


def make_fp_lib_table(project_dir: Path) -> None:
    switch_rel = SWITCH_LIB.resolve()
    kc2_rel = KC2_FP_LIB.resolve()
    content = (
        "(fp_lib_table\n"
        f"\t(lib (name \"key-switches\")(type \"KiCad\")(uri \"{switch_rel}\")(options \"\")(descr \"Third-party keyboard switch footprints, CERN-OHL-P v2\"))\n"
        f"\t(lib (name \"KC2\")(type \"KiCad\")(uri \"{kc2_rel}\")(options \"\")(descr \"KC2 local footprints\"))\n"
        ")\n"
    )
    (project_dir / "fp-lib-table").write_text(content, encoding="utf-8")


def add_antenna_keepout_zone(
    board: pcbnew.BOARD,
    side: str,
    keepout: tuple[float, float, float, float],
) -> None:
    x1, y1, x2, y2 = keepout
    chain = pcbnew.SHAPE_LINE_CHAIN()
    for x, y in ((x1, y1), (x2, y1), (x2, y2), (x1, y2)):
        chain.Append(vxy(x, y))
    chain.SetClosed(True)

    zone = pcbnew.ZONE(board)
    zone.SetZoneName(f"{side.upper()}_ANTENNA_10MM_NO_COPPER_TRACE_VIA")
    zone.SetNetCode(0)
    zone.SetLayerSet(copper_layers())
    zone.SetIsRuleArea(True)
    zone.SetMinThickness(mm(0.10))
    zone.SetDoNotAllowTracks(True)
    zone.SetDoNotAllowVias(True)
    zone.SetDoNotAllowCopperPour(True)
    zone.SetDoNotAllowPads(False)
    zone.SetDoNotAllowFootprints(False)
    zone.SetRuleAreaPlacementEnabled(False)
    zone.AddPolygon(chain)
    board.Add(zone)


def create_controller(
    board: pcbnew.BOARD,
    nets: dict[str, pcbnew.NETINFO_ITEM],
    ref: str,
    cx: float,
    cy: float,
    direction: int,
    pin_net_map: dict[str, str],
) -> tuple[pcbnew.FOOTPRINT, dict[str, tuple[float, float]], tuple[float, float, float, float]]:
    fp = pcbnew.FOOTPRINT(board)
    fp.SetFPIDAsString("KC2:NiceNanoV2_Socket_24Pin")
    fp.SetReference(ref)
    fp.SetValue("nice!nano_v2_socket_24pin")
    fp.SetPosition(vxy(cx, cy))

    row_a = ["D1", "D0", "GND_A", "GND_B", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9"]
    row_b = ["RAW", "GND_C", "RST", "VCC", "D21", "D20", "D19", "D18", "D15", "D14", "D16", "D10"]
    pad_pos: dict[str, tuple[float, float]] = {}

    for row_index, row in enumerate((row_a, row_b)):
        local_y = (-SOCKET_ROW_SPACING / 2.0) if row_index == 0 else (SOCKET_ROW_SPACING / 2.0)
        y = cy + direction * local_y
        for i, label in enumerate(row):
            local_x = -PIN_SPAN / 2.0 + i * PIN_PITCH
            x = cx + direction * local_x
            pad = pcbnew.PAD(fp)
            pad.SetNumber(label)
            pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
            pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
            pad.SetSize(pcbnew.VECTOR2I(mm(1.8), mm(1.8)))
            pad.SetDrillSize(pcbnew.VECTOR2I(mm(0.95), mm(0.95)))
            pad.SetLayerSet(pcbnew.LSET.AllCuMask())
            pad.SetPosition(vxy(x, y))
            net_name = pin_net_map.get(label)
            if label == "GND_C":
                net_name = "GND"
            if net_name:
                pad.SetNet(add_net(board, nets, net_name))
            fp.Add(pad)
            pad_pos[label] = (x, y)

            label_text = pcbnew.PCB_TEXT(fp)
            label_text.SetText(label.replace("_", ""))
            label_text.SetPosition(vxy(x, y + (2.1 if row_index == 0 else -2.1) * direction))
            label_text.SetLayer(pcbnew.F_SilkS)
            label_text.SetTextSize(pcbnew.VECTOR2I(mm(0.65), mm(0.65)))
            label_text.SetTextThickness(mm(0.10))
            fp.Add(label_text)

    board.Add(fp)
    add_rect_lines(
        board,
        cx - CONTROLLER_LEN / 2.0,
        cy - CONTROLLER_W / 2.0,
        cx + CONTROLLER_LEN / 2.0,
        cy + CONTROLLER_W / 2.0,
        pcbnew.F_Fab,
        0.10,
    )
    usb_x = cx - direction * CONTROLLER_LEN / 2.0
    ant_x = cx + direction * CONTROLLER_LEN / 2.0
    add_board_text(board, "USB_OUT_LEFT" if direction == 1 else "USB_OUT_RIGHT", usb_x, cy - 12.5, pcbnew.F_SilkS, 1.0)
    add_board_text(board, "ANTENNA_INWARD", ant_x, cy - 12.5, pcbnew.F_SilkS, 1.0)

    keepout_start = cx + direction * ANTENNA_KEEP_START_FROM_CENTER
    keepout_x1 = keepout_start
    keepout_x2 = keepout_start + direction * ANTENNA_KEEP_LENGTH
    keepout = (min(keepout_x1, keepout_x2), cy - CONTROLLER_W / 2.0, max(keepout_x1, keepout_x2), cy + CONTROLLER_W / 2.0)
    add_rect_lines(board, *keepout, pcbnew.Dwgs_User, width=0.12)
    add_board_text(board, "ANT KEEPOUT", (keepout[0] + keepout[2]) / 2.0, keepout[1] - 1.6, pcbnew.Dwgs_User, 0.9)
    return fp, pad_pos, keepout


def connect_controller_ground_pads(
    board: pcbnew.BOARD,
    nets: dict[str, pcbnew.NETINFO_ITEM],
    controller_pads: dict[str, tuple[float, float]],
) -> None:
    # Only one controller ground socket pad is electrically needed for KC2's
    # reset switch reference. Other nice!nano GND pins remain unconnected on
    # the carrier PCB to avoid crossing active pins in the controller escape.
    return


def create_power_pads(
    board: pcbnew.BOARD,
    nets: dict[str, pcbnew.NETINFO_ITEM],
    ref: str,
    x: float,
    y: float,
) -> dict[str, tuple[float, float]]:
    fp = pcbnew.FOOTPRINT(board)
    fp.SetFPIDAsString("KC2:DirectSolderPowerPads")
    fp.SetReference(ref)
    fp.SetValue("BAT_NN_direct_solder")
    fp.SetPosition(vxy(x, y))

    positions = {
        "BAT+": (-3.0, -2.2),
        "BAT-": (-3.0, 2.2),
        "NN_B+": (3.0, -2.2),
        "NN_B-": (3.0, 2.2),
    }
    abs_pos: dict[str, tuple[float, float]] = {}
    pad_net_names = {
        "BAT+": "BAT+",
        "BAT-": "BAT-",
        "NN_B+": "BAT+",
        "NN_B-": "BAT-",
    }
    for label, (dx, dy) in positions.items():
        pad = pcbnew.PAD(fp)
        pad.SetNumber(label)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_PTH)
        pad.SetShape(pcbnew.PAD_SHAPE_OVAL)
        pad.SetSize(pcbnew.VECTOR2I(mm(2.6), mm(1.8)))
        pad.SetDrillSize(pcbnew.VECTOR2I(mm(0.9), mm(0.9)))
        pad.SetLayerSet(pcbnew.LSET.AllCuMask())
        pad.SetPosition(vxy(x + dx, y + dy))
        pad.SetNet(add_net(board, nets, pad_net_names[label]))
        fp.Add(pad)
        abs_pos[label] = (x + dx, y + dy)

        text = pcbnew.PCB_TEXT(fp)
        text.SetText(label)
        text.SetPosition(vxy(x + dx, y + dy - 2.1))
        text.SetLayer(pcbnew.F_SilkS)
        text.SetTextSize(pcbnew.VECTOR2I(mm(0.8), mm(0.8)))
        text.SetTextThickness(mm(0.10))
        fp.Add(text)

    for idx, (dx, dy) in enumerate([(-6.5, -2.2), (-6.5, 2.2), (6.5, -2.2), (6.5, 2.2)], start=1):
        pad = pcbnew.PAD(fp)
        pad.SetNumber("")
        pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
        pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        pad.SetSize(pcbnew.VECTOR2I(mm(1.3), mm(1.3)))
        pad.SetDrillSize(pcbnew.VECTOR2I(mm(1.3), mm(1.3)))
        pad.SetLayerSet(mask_only_layers())
        pad.SetPosition(vxy(x + dx, y + dy))
        fp.Add(pad)

    board.Add(fp)
    add_track(board, add_net(board, nets, "BAT+"), abs_pos["BAT+"], abs_pos["NN_B+"], pcbnew.B_Cu, POWER_TRACK_WIDTH)
    add_track(board, add_net(board, nets, "BAT-"), abs_pos["BAT-"], abs_pos["NN_B-"], pcbnew.B_Cu, POWER_TRACK_WIDTH)
    return abs_pos


def create_stabilizer(
    board: pcbnew.BOARD,
    ref: str,
    key: Key,
    dx: float,
    dy: float,
) -> None:
    fp = pcbnew.FOOTPRINT(board)
    fp.SetFPIDAsString("KC2:PCB_Mount_2u_Stabilizer_NPTH")
    fp.SetReference(ref)
    fp.SetValue(f"PCB_mount_stab_for_{key.w_u:.2f}u")
    fp.SetPosition(vxy(key.cx + dx, key.cy + dy))
    for xoff in (-11.9, 11.9):
        for yoff, drill in ((-7.0, 3.05), (8.24, 4.0)):
            pad = pcbnew.PAD(fp)
            pad.SetNumber("")
            pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
            pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
            pad.SetSize(pcbnew.VECTOR2I(mm(drill), mm(drill)))
            pad.SetDrillSize(pcbnew.VECTOR2I(mm(drill), mm(drill)))
            pad.SetLayerSet(mask_only_layers())
            pad.SetPosition(vxy(key.cx + dx + xoff, key.cy + dy + yoff))
            fp.Add(pad)
    board.Add(fp)


def make_board(side: str, keys: list[Key], out_dir: Path) -> tuple[Path, tuple[float, float, float, float]]:
    name = f"kc2_{side}"
    project_dir = out_dir / name
    if project_dir.exists():
        for child in project_dir.iterdir():
            if child.is_file() and child.suffix in {".kicad_pcb", ".kicad_pro", ".kicad_prl", ".json", ".rpt"}:
                child.unlink()
    project_dir.mkdir(parents=True, exist_ok=True)

    ctrl_cx = controller_center_x(keys, side)
    outline = raw_outline(keys, side, ctrl_cx)
    rounded = rounded_polygon(outline, radius=2.0, steps=5)
    min_x = min(x for x, _ in rounded)
    min_y = min(y for _, y in rounded)
    dx = 35.0 - min_x
    dy = 35.0 - min_y

    shifted_keys = [
        Key(k.label, k.row, k.col, k.x_u + dx / UNIT, k.y_u + dy / UNIT, k.w_u, k.h_u)
        for k in keys
    ]
    ctrl_cx += dx
    ctrl_cy = CONTROLLER_CENTER_Y + dy
    shifted_outline = shift_points(rounded, dx, dy)

    board = pcbnew.BOARD()
    board.SetCopperLayerCount(2)
    title = board.GetTitleBlock()
    title.SetTitle(f"KC2 {side.capitalize()} PCB Draft")
    title.SetDate("2026-06-04")
    title.SetRevision("draft-1")
    add_polyline(board, shifted_outline, pcbnew.Edge_Cuts, EDGE_WIDTH, closed=True)

    nets: dict[str, pcbnew.NETINFO_ITEM] = {"": board.GetNetInfo().GetNetItem(0)}
    add_net(board, nets, "GND")
    add_net(board, nets, "RST")
    for pwr in ("BAT+", "BAT-"):
        add_net(board, nets, pwr)

    if side == "left":
        pin_map = {
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
        col_prefix = "L_COL"
        row_prefix = "L_ROW"
        usb_direction = 1
    else:
        pin_map = {
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
        col_prefix = "R_COL"
        row_prefix = "R_ROW"
        usb_direction = -1

    for net_name in pin_map.values():
        add_net(board, nets, net_name)

    _, controller_pads, antenna_keepout = create_controller(
        board, nets, "U1", ctrl_cx, ctrl_cy, usb_direction, pin_map
    )
    add_antenna_keepout_zone(board, side, antenna_keepout)

    power_y = ctrl_cy + 1.0
    power_x = ctrl_cx - usb_direction * 28.0
    power_pads = create_power_pads(board, nets, "J_PWR1", power_x, power_y)
    add_board_text(board, "B+/B- direct cable solder only", power_x - 12, power_y + 7.0, pcbnew.F_SilkS, 0.9)

    batt_w, batt_h = 15.0, 25.0
    batt_cx = ctrl_cx - usb_direction * 7.0
    batt_cy = ctrl_cy + 2.0
    add_rect_lines(board, batt_cx - batt_w / 2, batt_cy - batt_h / 2, batt_cx + batt_w / 2, batt_cy + batt_h / 2, pcbnew.B_Fab, 0.10)
    add_board_text(board, "TW301525 80mAh", batt_cx - 7.0, batt_cy, pcbnew.B_Fab, 0.9)

    tact_x = ctrl_cx - usb_direction * (CONTROLLER_LEN / 2.0 - 7.0)
    tact_y = ctrl_cy + CONTROLLER_W / 2.0 + 4.0
    tact = load_footprint(board, TACT_LIB, TACT_FP, "SW_RST1", "NW3-A06-B3 RST", tact_x, tact_y, 0)

    mount_points = mounting_points(side, shifted_keys, shifted_outline, ctrl_cx, ctrl_cy)
    for idx, (mx, my) in enumerate(mount_points, start=1):
        fp = load_footprint(board, MOUNT_LIB, MOUNT_FP, f"H{idx}", "M2_NPTH_2.2", mx, my)
        add_rect_lines(board, mx - 2.5, my - 2.5, mx + 2.5, my + 2.5, pcbnew.Cmts_User, 0.08)

    switch_refs: dict[str, pcbnew.FOOTPRINT] = {}
    diode_refs: dict[str, pcbnew.FOOTPRINT] = {}
    row_diodes: dict[int, list[tuple[float, float]]] = {}
    col_switches: dict[int, list[tuple[float, float]]] = {}

    for idx, key in enumerate(shifted_keys, start=1):
        col_net_name = f"{col_prefix}{key.col}"
        row_net_name = f"{row_prefix}{key.row}"
        local_net_name = f"{side[0].upper()}K{idx:02d}_D"
        col_net = add_net(board, nets, col_net_name)
        row_net = add_net(board, nets, row_net_name)
        local_net = add_net(board, nets, local_net_name)

        sw = load_footprint(board, SWITCH_LIB, SWITCH_FP, f"SW{idx}", f"KEY_{idx:02d}", key.cx, key.cy)
        convert_empty_switch_pads_to_npth(sw)
        set_pad_net(sw, "1", col_net)
        set_pad_net(sw, "2", local_net)
        switch_refs[key.label + str(idx)] = sw
        add_board_text(board, key.label, key.cx - 3.0, key.cy - 9.2, pcbnew.F_SilkS, 0.9)

        dio = load_footprint(board, DIODE_LIB, DIODE_FP, f"D{idx}", "1N4148W_SOD-123", key.cx, key.cy - 6.8, bottom=True)
        set_pad_net(dio, "1", row_net)
        set_pad_net(dio, "2", local_net)
        diode_refs[key.label + str(idx)] = dio

        sw_p1 = pad_positions(sw, "1")
        sw_p2 = pad_positions(sw, "2")
        d_p1 = pad_positions(dio, "1")[0]
        d_p2 = pad_positions(dio, "2")[0]

        for a, b in zip(sw_p1, sw_p1[1:]):
            add_track(board, col_net, a, b, pcbnew.F_Cu)

        row_bus_y = key.cy - 10.8
        row_tap = (d_p1[0], row_bus_y)
        add_track(board, row_net, d_p1, row_tap, pcbnew.B_Cu)

        left_switch_pad2 = sorted(sw_p2, key=lambda p: p[0])[0]
        right_switch_pad2 = sorted(sw_p2, key=lambda p: p[0])[-1]
        local_lane_x = key.cx - 8.0
        add_track(board, local_net, d_p2, (local_lane_x, d_p2[1]), pcbnew.B_Cu)
        add_track(board, local_net, (local_lane_x, d_p2[1]), (local_lane_x, left_switch_pad2[1]), pcbnew.B_Cu)
        add_track(board, local_net, (local_lane_x, left_switch_pad2[1]), left_switch_pad2, pcbnew.B_Cu)
        add_track(board, local_net, left_switch_pad2, right_switch_pad2, pcbnew.B_Cu)

        col_tap = (key.cx + 8.0, sw_p1[0][1])
        add_track(board, col_net, sw_p1[0], col_tap, pcbnew.F_Cu)
        row_diodes.setdefault(key.row, []).append(row_tap)
        col_switches.setdefault(key.col, []).append(col_tap)

        if key.w_u >= 2.0:
            create_stabilizer(board, f"STAB{idx}", key, 0, 0)

    for row, points in row_diodes.items():
        net = add_net(board, nets, f"{row_prefix}{row}")
        points = sorted(points, key=lambda p: p[0])
        for a, b in zip(points, points[1:]):
            add_track(board, net, a, b, pcbnew.B_Cu)

    for col, points in col_switches.items():
        net = add_net(board, nets, f"{col_prefix}{col}")
        points = sorted(points, key=lambda p: p[1])
        for a, b in zip(points, points[1:]):
            add_track(board, net, a, b, pcbnew.F_Cu)

    connect_matrix_to_controller(
        board,
        nets,
        side,
        col_prefix,
        row_prefix,
        col_switches,
        row_diodes,
        controller_pads,
        pin_map,
        shifted_outline,
    )
    connect_controller_ground_pads(board, nets, controller_pads)
    connect_tact_to_controller(board, nets, tact, controller_pads)
    connect_power_labels(board, nets, power_pads)

    add_board_text(board, f"KC2 {side.upper()} - 71-key split successor to KC1", 35, 24, pcbnew.F_SilkS, 1.2)
    add_board_text(board, "No top housing / PCB is switch plate / bottom plate M2+adhesive", 35, 27, pcbnew.F_SilkS, 0.9)
    add_board_text(board, "Diode fallback: 1N4148W SOD-123 because DO-35 conflicts with compact hybrid footprint", 35, 30, pcbnew.Cmts_User, 0.9)

    make_project_file(project_dir, name)
    make_fp_lib_table(project_dir)
    board_path = project_dir / f"{name}.kicad_pcb"
    pcbnew.SaveBoard(str(board_path), board)
    return board_path, antenna_keepout


def mounting_points(
    side: str,
    keys: list[Key],
    outline: list[tuple[float, float]],
    ctrl_cx: float,
    ctrl_cy: float,
) -> list[tuple[float, float]]:
    min_x = min(x for x, _ in outline)
    max_x = max(x for x, _ in outline)
    max_y = max(y for _, y in outline)
    points = [
        (min_x + 4.0, max_y - 4.0),
        (max_x - 4.0, max_y - 4.0),
        (ctrl_cx - 18.0, ctrl_cy - 5.0),
        (ctrl_cx + 18.0, ctrl_cy - 5.0),
    ]
    if side == "right":
        points.append((max_x - 4.0, max_y - 45.0))
    else:
        points.append((min_x + 4.5, max_y - 42.0))
    return points


def connect_matrix_to_controller(
    board: pcbnew.BOARD,
    nets: dict[str, pcbnew.NETINFO_ITEM],
    side: str,
    col_prefix: str,
    row_prefix: str,
    col_switches: dict[int, list[tuple[float, float]]],
    row_diodes: dict[int, list[tuple[float, float]]],
    controller_pads: dict[str, tuple[float, float]],
    pin_map: dict[str, str],
    outline: list[tuple[float, float]],
) -> None:
    net_to_pin = {net: pin for pin, net in pin_map.items()}
    min_outline_x = min(x for x, _ in outline)
    max_outline_x = max(x for x, _ in outline)

    for col, points in col_switches.items():
        net_name = f"{col_prefix}{col}"
        pin = net_to_pin.get(net_name)
        if not pin:
            continue
        net = add_net(board, nets, net_name)
        src = sorted(points, key=lambda p: p[1])[0]
        dst = controller_pads[pin]
        route_to_controller(
            board,
            net,
            src,
            dst,
            controller_pads,
            pcbnew.F_Cu,
            jog_y=dst[1] + 22.0 + col * 0.45,
        )

    for row, points in row_diodes.items():
        net_name = f"{row_prefix}{row}"
        pin = net_to_pin.get(net_name)
        if not pin:
            continue
        net = add_net(board, nets, net_name)
        points = sorted(points, key=lambda p: p[0])
        if side == "left":
            src = points[0]
            exit_x = min_outline_x + 3.5 + row * 0.8
        else:
            src = points[-1]
            exit_x = max_outline_x - 3.5 - row * 0.8
        exit_point = (exit_x, src[1])
        add_track(board, net, src, exit_point, pcbnew.B_Cu)
        dst = controller_pads[pin]
        route_to_controller(
            board,
            net,
            exit_point,
            dst,
            controller_pads,
            pcbnew.B_Cu,
            jog_y=max(y for _, y in controller_pads.values()) + 5.1 + row * 0.7,
        )


def route_manhattan(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    src: tuple[float, float],
    dst: tuple[float, float],
    layer: int,
    jog_y: float,
    width: float = TRACK_WIDTH,
) -> None:
    p1 = (src[0], jog_y)
    p2 = (dst[0], jog_y)
    add_track(board, net, src, p1, layer, width)
    add_track(board, net, p1, p2, layer, width)
    add_track(board, net, p2, dst, layer, width)


def route_to_controller(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    src: tuple[float, float],
    dst: tuple[float, float],
    controller_pads: dict[str, tuple[float, float]],
    layer: int,
    jog_y: float,
    width: float = TRACK_WIDTH,
) -> None:
    top_y = min(y for _, y in controller_pads.values())
    bottom_y = max(y for _, y in controller_pads.values())
    if abs(dst[1] - top_y) < 0.05 and jog_y > bottom_y:
        escape_x = dst[0] + PIN_PITCH / 2.0
        p0 = (escape_x, dst[1])
        p1 = (escape_x, jog_y)
        p2 = (src[0], jog_y)
        add_track(board, net, dst, p0, layer, width)
        add_track(board, net, p0, p1, layer, width)
        add_track(board, net, p1, p2, layer, width)
        add_track(board, net, p2, src, layer, width)
        return
    route_manhattan(board, net, src, dst, layer, jog_y, width)


def connect_tact_to_controller(
    board: pcbnew.BOARD,
    nets: dict[str, pcbnew.NETINFO_ITEM],
    tact: pcbnew.FOOTPRINT,
    controller_pads: dict[str, tuple[float, float]],
) -> None:
    rst = add_net(board, nets, "RST")
    gnd = add_net(board, nets, "GND")
    rst_pad_obj = min(
        pads_by_number(tact, "1"),
        key=lambda pad: abs(to_mm_vec(pad.GetPosition())[0] - controller_pads["RST"][0])
        + abs(to_mm_vec(pad.GetPosition())[1] - controller_pads["RST"][1]),
    )
    gnd_pad_obj = min(
        pads_by_number(tact, "2"),
        key=lambda pad: abs(to_mm_vec(pad.GetPosition())[0] - controller_pads["GND_C"][0])
        + abs(to_mm_vec(pad.GetPosition())[1] - controller_pads["GND_C"][1]),
    )
    for pad in pads_by_number(tact, "1") + pads_by_number(tact, "2"):
        pad.SetNetCode(0)
    rst_pad_obj.SetNet(rst)
    gnd_pad_obj.SetNet(gnd)
    rst_pad = to_mm_vec(rst_pad_obj.GetPosition())
    gnd_pad = to_mm_vec(gnd_pad_obj.GetPosition())
    route_to_controller(board, rst, rst_pad, controller_pads["RST"], controller_pads, pcbnew.F_Cu, jog_y=max(y for _, y in controller_pads.values()) + 2.0)
    route_to_controller(board, gnd, gnd_pad, controller_pads["GND_C"], controller_pads, pcbnew.F_Cu, jog_y=controller_pads["GND_C"][1] + 3.0)


def connect_power_labels(
    board: pcbnew.BOARD,
    nets: dict[str, pcbnew.NETINFO_ITEM],
    power_pads: dict[str, tuple[float, float]],
) -> None:
    # The actual nice!nano B+/B- top pads are wired by hand to NN_B+/NN_B-.
    # Keep short wide PCB traces only between the same-polarity solder pads.
    add_board_text(board, "+", power_pads["BAT+"][0] - 1.0, power_pads["BAT+"][1] - 3.8, pcbnew.F_SilkS, 1.2)
    add_board_text(board, "-", power_pads["BAT-"][0] - 1.0, power_pads["BAT-"][1] + 3.0, pcbnew.F_SilkS, 1.2)


def copy_license() -> None:
    src = SWITCH_LIB / "LICENSE"
    if src.exists():
        dest = ROOT / "third_party" / "key-switches.pretty.LICENSE"
        if not dest.exists():
            shutil.copyfile(src, dest)


def main() -> None:
    if not SWITCH_LIB.exists():
        raise SystemExit(f"Missing switch library: {SWITCH_LIB}")
    if not KC2_FP_LIB.exists():
        raise SystemExit(f"Missing KC2 footprint library: {KC2_FP_LIB}")
    KICAD_ROOT.mkdir(parents=True, exist_ok=True)
    copy_license()

    left_path, left_keepout = make_board("left", make_left_keys(), KICAD_ROOT)
    right_path, right_keepout = make_board("right", make_right_keys(), KICAD_ROOT)
    manifest = {
        "generated": "2026-06-04",
        "boards": {
            "left": str(left_path.relative_to(ROOT)),
            "right": str(right_path.relative_to(ROOT)),
        },
        "antenna_keepout_mm": {
            "left": left_keepout,
            "right": right_keepout,
        },
        "switch_footprint": f"{SWITCH_LIB.name}:{SWITCH_FP}",
        "diode_footprint": f"Diode_SMD:{DIODE_FP}",
        "tact_footprint": f"{KC2_FP_LIB.name}:{TACT_FP}",
        "notes": [
            "SOD-123 1N4148W fallback is used because DO-35 conflicts with the compact hybrid switch footprint at 19.05 mm pitch.",
            "Antenna keepout rule areas are generated directly in the board files.",
            "Switch footprint values are sanitized as KEY_XX so Specctra DSN export does not expose legend characters such as backslash to Freerouting.",
            "Right-half R_COL7 uses D21 and R_COL8 uses D20 to keep the longer outer column on the easier controller fanout pin.",
            "Controller protrusion tabs are aligned toward the inner joining edge: left recessed 14 mm, right recessed 12 mm.",
            "Programming tact switch uses the smaller DeviceMart 1322056 NW3-A06-B3 SMD footprint.",
        ],
    }
    (KICAD_ROOT / "kc2_generation_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
