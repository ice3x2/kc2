from __future__ import annotations

import argparse
import re
from pathlib import Path

try:
    import pcbnew
except ImportError as exc:
    raise SystemExit(
        "FAIL: pcbnew is unavailable. Run with KiCad Python, for example "
        r"C:\Program Files\KiCad\10.0\bin\python.exe"
    ) from exc


ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_LEN = 33.8
CONTROLLER_W = 18.3
TACT_BODY_W = 6.1
TACT_BODY_H = 3.7
PIN_PITCH = 2.54
PIN_COUNT = 12
PIN_SPAN = PIN_PITCH * (PIN_COUNT - 1)
ANTENNA_KEEP_START_FROM_CENTER = PIN_SPAN / 2.0 + 4.0
BATTERY_LEAD_SLOT_REF = "BAT_LEAD_SLOT1"
BATTERY_LEAD_SLOT_VALUE = "BAT_LEAD_NPTH_SLOT_3.6x2.2"
BATTERY_LEAD_SLOT_LEN = 3.6
BATTERY_LEAD_SLOT_W = 2.2
BATTERY_LEAD_SLOT_KEEP_OUT_GAP = 0.3
V2_RESET_SLOT_CLEARANCE_MIN = 0.50
COMPACT_TOP_STRAIGHT_SPAN_MAX = 39.0
ANTENNA_SIDE_CENTER_MAX_FROM_ANTENNA_EDGE = 8.0
KEY_SIDE_MIN_GAP = 1.0
KEY_SIDE_MAX_GAP = 7.0
BATTERY_CLEARANCE = 0.75
SLOT_POSITION_TOLERANCE = 0.03
SLOT_DIMENSION_TOLERANCE = 0.02
SLOT_EDGE_CLEARANCE_MIN = 1.0
V2_CONTROLLER_SERVICE_POSITIONS_MM = {
    "left": {
        "u1": (132.7125, 50.75),
        "battery": (131.7125, 50.75),
        "j_bat": (115.8125, 59.40),
        "power": (115.8125, 63.45),
        "reset": (126.0625, 63.45),
    },
    "right": {
        "u1": (77.4, 50.75),
        "battery": (78.4, 50.75),
        "j_bat": (94.3, 59.40),
        "power": (94.3, 63.45),
        "reset": (84.05, 63.45),
    },
}
V2_POSITION_TOLERANCE_MM = 0.001
V2_RESET_ROTATIONS_DEGREES = {"left": 0.0, "right": 180.0}
V2_J_BAT1_ROTATIONS_DEGREES = {"left": 180.0, "right": 0.0}
FORBIDDEN_POWER_NETS = {"BAT+", "BAT-", "NN_B+", "NN_B-"}
V2_EXPECTED_POWER_NETS = {"BAT+", "NN_B+", "GND"}


def to_mm_vec(vec: pcbnew.VECTOR2I) -> tuple[float, float]:
    return pcbnew.ToMM(vec.x), pcbnew.ToMM(vec.y)


def pads_by_number(fp: pcbnew.FOOTPRINT, number: str) -> list[pcbnew.PAD]:
    return [pad for pad in fp.Pads() if pad.GetNumber() == number]


def fp_center(fp: pcbnew.FOOTPRINT) -> tuple[float, float]:
    return to_mm_vec(fp.GetPosition())


def edge_points(board: pcbnew.BOARD) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for drawing in board.GetDrawings():
        if drawing.GetLayer() != pcbnew.Edge_Cuts:
            continue
        if hasattr(drawing, "GetStart") and hasattr(drawing, "GetEnd"):
            points.append(to_mm_vec(drawing.GetStart()))
            points.append(to_mm_vec(drawing.GetEnd()))
    return points


def controller_top_straight_span(board: pcbnew.BOARD) -> float:
    points = edge_points(board)
    if not points:
        return 0.0
    min_y = min(y for _, y in points)
    top_xs = [x for x, y in points if abs(y - min_y) <= 0.05]
    if not top_xs:
        return 0.0
    return max(top_xs) - min(top_xs)


def board_rect_bbox(board: pcbnew.BOARD, layer: int) -> tuple[float, float, float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for drawing in board.GetDrawings():
        if drawing.GetLayer() != layer:
            continue
        if hasattr(drawing, "GetStart") and hasattr(drawing, "GetEnd"):
            for point in (drawing.GetStart(), drawing.GetEnd()):
                x, y = to_mm_vec(point)
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def footprint_rect_bbox(
    footprint: pcbnew.FOOTPRINT,
    layer: int,
) -> tuple[float, float, float, float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for item in footprint.GraphicalItems():
        if item.GetLayer() != layer or not hasattr(item, "GetStart"):
            continue
        for point in (item.GetStart(), item.GetEnd()):
            x, y = to_mm_vec(point)
            xs.append(x)
            ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def expanded(rect: tuple[float, float, float, float], amount: float) -> tuple[float, float, float, float]:
    return rect[0] - amount, rect[1] - amount, rect[2] + amount, rect[3] + amount


def rects_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def dist_point_segment(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> float:
    dx = bx - ax
    dy = by - ay
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    nearest_x = ax + t * dx
    nearest_y = ay + t * dy
    return ((px - nearest_x) ** 2 + (py - nearest_y) ** 2) ** 0.5


def edge_segments(board: pcbnew.BOARD) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for drawing in board.GetDrawings():
        if not hasattr(drawing, "GetLayer") or drawing.GetLayer() != pcbnew.Edge_Cuts:
            continue
        if not hasattr(drawing, "GetStart") or not hasattr(drawing, "GetEnd"):
            continue
        segments.append((to_mm_vec(drawing.GetStart()), to_mm_vec(drawing.GetEnd())))
    return segments


def slot_edge_clearance(board: pcbnew.BOARD, x: float, y: float) -> float:
    segments = edge_segments(board)
    if not segments:
        return -999.0
    radius = max(BATTERY_LEAD_SLOT_LEN, BATTERY_LEAD_SLOT_W) / 2.0
    center_to_edge = min(dist_point_segment(x, y, a[0], a[1], b[0], b[1]) for a, b in segments)
    return center_to_edge - radius


def expected_slot_center(
    side: str,
    u1_x: float,
    u1_y: float,
    board_path: Path | None = None,
) -> tuple[float, float]:
    usb_direction = 1 if side == "left" else -1
    if board_path is not None and "x3-v2" in str(board_path).lower():
        usb_edge_x = u1_x - usb_direction * CONTROLLER_LEN / 2.0
        return (
            usb_edge_x
            + usb_direction
            * (BATTERY_LEAD_SLOT_LEN / 2.0 + BATTERY_LEAD_SLOT_KEEP_OUT_GAP),
            u1_y,
        )
    keepout_near_edge_x = u1_x + usb_direction * ANTENNA_KEEP_START_FROM_CENTER
    slot_x = keepout_near_edge_x - usb_direction * (BATTERY_LEAD_SLOT_LEN / 2.0 + BATTERY_LEAD_SLOT_KEEP_OUT_GAP)
    return slot_x, u1_y


def text_contains_power_net_declaration(board_path: Path) -> list[str]:
    text = board_path.read_text(encoding="utf-8")
    found: list[str] = []
    for net in FORBIDDEN_POWER_NETS:
        pattern = r'\(net\s+\d+\s+"?' + re.escape(net) + r'"?\)'
        if re.search(pattern, text):
            found.append(net)
    return found


def check_side(side: str, board_path: Path) -> list[str]:
    errors: list[str] = []
    board = pcbnew.LoadBoard(str(board_path))
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    is_v2 = "x3-v2" in str(board_path).lower()

    if not is_v2 and "J_PWR1" in fps:
        errors.append(f"{side}: J_PWR1 carrier power pad footprint is still present")

    if not is_v2:
        declared_power_nets = text_contains_power_net_declaration(board_path)
        if declared_power_nets:
            errors.append(f"{side}: carrier board still declares power nets {declared_power_nets}")

        used_power_nets: set[str] = set()
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                if pad.GetNetname() in FORBIDDEN_POWER_NETS:
                    used_power_nets.add(pad.GetNetname())
        for track in board.GetTracks():
            if track.GetNetname() in FORBIDDEN_POWER_NETS:
                used_power_nets.add(track.GetNetname())
        if used_power_nets:
            errors.append(f"{side}: carrier board still uses power nets {sorted(used_power_nets)}")

    top_span = controller_top_straight_span(board)
    if top_span <= 0:
        errors.append(f"{side}: cannot measure controller top Edge.Cuts span")
    elif top_span > COMPACT_TOP_STRAIGHT_SPAN_MAX:
        errors.append(
            f"{side}: controller top straight span {top_span:.3f} mm > "
            f"{COMPACT_TOP_STRAIGHT_SPAN_MAX:.3f} mm compact limit"
        )

    u1 = fps.get("U1")
    tact = fps.get("SW_RST1")
    if not u1:
        errors.append(f"{side}: missing U1")
    if not tact:
        errors.append(f"{side}: missing SW_RST1")
    if not u1 or not tact:
        return errors

    u1_x, u1_y = fp_center(u1)
    tact_x, tact_y = fp_center(tact)
    usb_direction = 1 if side == "left" else -1
    if is_v2:
        expected = V2_CONTROLLER_SERVICE_POSITIONS_MM[side]
        required_v2 = {
            "BAT1": "battery",
            "J_BAT1": "j_bat",
            "SW_PWR1": "power",
            "SW_RST1": "reset",
        }
        for reference in required_v2:
            if reference not in fps:
                errors.append(f"{side}: missing {reference}")
        for label, actual, target in [
            ("U1", (u1_x, u1_y), expected["u1"]),
            *(
                (reference, fp_center(fps[reference]), expected[key])
                for reference, key in required_v2.items()
                if reference in fps
            ),
        ]:
            if max(abs(actual[index] - target[index]) for index in (0, 1)) > V2_POSITION_TOLERANCE_MM:
                errors.append(
                    f"{side}: {label} center ({actual[0]:.4f}, {actual[1]:.4f}) mm, "
                    f"expected ({target[0]:.4f}, {target[1]:.4f}) mm"
                )
        rotation = tact.GetOrientation().AsDegrees() % 360.0
        expected_reset_rotation = V2_RESET_ROTATIONS_DEGREES[side]
        if abs(rotation - expected_reset_rotation) > 0.001:
            errors.append(
                f"{side}: SW_RST1 rotation is {rotation:.3f} deg, expected "
                f"{expected_reset_rotation:.3f} deg"
            )
        power = fps.get("SW_PWR1")
        j_bat = fps.get("J_BAT1")
        battery = fps.get("BAT1")
        if power is not None:
            expected_rotation = 0.0 if side == "left" else 180.0
            if abs((power.GetOrientation().AsDegrees() % 360.0) - expected_rotation) > 0.001:
                errors.append(f"{side}: SW_PWR1 rotation is not {expected_rotation:.1f} deg")
            power_nets = {pad.GetNumber(): pad.GetNetname() for pad in power.Pads()}
            if power_nets != {"2": "NN_B+", "1": "BAT+", "3": ""}:
                errors.append(f"{side}: SW_PWR1 pad nets differ from BAT+/NN_B+/NC: {power_nets}")
        if j_bat is not None:
            expected_rotation = V2_J_BAT1_ROTATIONS_DEGREES[side]
            if abs((j_bat.GetOrientation().AsDegrees() % 360.0) - expected_rotation) > 0.001:
                errors.append(f"{side}: J_BAT1 rotation is not {expected_rotation:.1f} deg")
            j_bat_nets = {pad.GetNumber(): pad.GetNetname() for pad in j_bat.Pads()}
            if j_bat_nets != {"1": "BAT+", "2": "GND"}:
                errors.append(f"{side}: J_BAT1 pad nets differ from BAT+/GND: {j_bat_nets}")
        u1_power_nets = {
            pad.GetNumber(): pad.GetNetname()
            for pad in u1.Pads()
            if pad.GetNumber() in {"RAW", "GND_C"}
        }
        if u1_power_nets != {"RAW": "NN_B+", "GND_C": "GND"}:
            errors.append(f"{side}: U1 RAW/GND_C power contract differs: {u1_power_nets}")
        if battery is not None:
            battery_rect = footprint_rect_bbox(battery, pcbnew.F_Fab)
            if battery_rect is None:
                errors.append(f"{side}: BAT1 has no F.Fab 301230 body")
            else:
                expected_rect = (
                    expected["battery"][0] - 15.0,
                    expected["battery"][1] - 6.0,
                    expected["battery"][0] + 15.0,
                    expected["battery"][1] + 6.0,
                )
                if max(abs(a - b) for a, b in zip(battery_rect, expected_rect)) > 0.001:
                    errors.append(f"{side}: BAT1 body is not exact 30 x 12 mm at the target center")
    else:
        antenna_edge_x = u1_x + usb_direction * (CONTROLLER_LEN / 2.0)
        antenna_side_distance = abs(tact_x - antenna_edge_x)
        if antenna_side_distance > ANTENNA_SIDE_CENTER_MAX_FROM_ANTENNA_EDGE:
            errors.append(
                f"{side}: SW_RST1 center is {antenna_side_distance:.3f} mm from antenna-side edge, "
                f"expected <= {ANTENNA_SIDE_CENTER_MAX_FROM_ANTENNA_EDGE:.3f} mm"
            )
        if (tact_x - u1_x) * usb_direction <= 0:
            errors.append(f"{side}: SW_RST1 is not on the antenna-side half of U1")

    if not is_v2:
        key_side_gap = tact_y - (u1_y + CONTROLLER_W / 2.0)
        if key_side_gap < KEY_SIDE_MIN_GAP or key_side_gap > KEY_SIDE_MAX_GAP:
            errors.append(
                f"{side}: SW_RST1 key-side gap {key_side_gap:.3f} mm is outside "
                f"{KEY_SIDE_MIN_GAP:.3f}-{KEY_SIDE_MAX_GAP:.3f} mm"
            )

    rst_pads = pads_by_number(tact, "1")
    gnd_pads = pads_by_number(tact, "2")
    if len(rst_pads) != 1 or rst_pads[0].GetNetname() != "RST":
        errors.append(f"{side}: SW_RST1 pad 1 is not exactly RST")
    if len(gnd_pads) != 1 or gnd_pads[0].GetNetname() != "GND":
        errors.append(f"{side}: SW_RST1 pad 2 is not exactly GND")

    tact_w, tact_h = (
        (TACT_BODY_H, TACT_BODY_W)
        if round(tact.GetOrientation().AsDegrees() % 180.0, 3) == 90.0
        else (TACT_BODY_W, TACT_BODY_H)
    )
    tact_rect = (
        tact_x - tact_w / 2.0,
        tact_y - tact_h / 2.0,
        tact_x + tact_w / 2.0,
        tact_y + tact_h / 2.0,
    )
    battery_rect = (
        footprint_rect_bbox(fps["BAT1"], pcbnew.F_Fab)
        if is_v2 and "BAT1" in fps
        else board_rect_bbox(board, pcbnew.B_Fab)
    )
    if battery_rect is None:
        errors.append(
            f"{side}: missing {'BAT1 F.Fab 301230' if is_v2 else 'TW301525 B.Fab'} battery reference rectangle"
        )
    elif rects_overlap(tact_rect, expanded(battery_rect, BATTERY_CLEARANCE)):
        errors.append(
            f"{side}: SW_RST1 body overlaps battery reference clearance; "
            f"tact={tuple(round(v, 3) for v in tact_rect)} "
            f"battery={tuple(round(v, 3) for v in battery_rect)}"
        )

    slot = fps.get(BATTERY_LEAD_SLOT_REF)
    if not slot:
        errors.append(f"{side}: missing {BATTERY_LEAD_SLOT_REF} battery lead pass-through slot")
        return errors
    if slot.GetValue() != BATTERY_LEAD_SLOT_VALUE:
        errors.append(f"{side}: {BATTERY_LEAD_SLOT_REF} value is {slot.GetValue()!r}")
    slot_x, slot_y = fp_center(slot)
    expected_x, expected_y = expected_slot_center(side, u1_x, u1_y, board_path)
    if abs(slot_x - expected_x) > SLOT_POSITION_TOLERANCE or abs(slot_y - expected_y) > SLOT_POSITION_TOLERANCE:
        errors.append(
            f"{side}: {BATTERY_LEAD_SLOT_REF} at ({slot_x:.3f}, {slot_y:.3f}) mm, "
            f"expected ({expected_x:.3f}, {expected_y:.3f}) mm"
        )
    slot_pads = list(slot.Pads())
    if len(slot_pads) != 1:
        errors.append(f"{side}: {BATTERY_LEAD_SLOT_REF} expected exactly one NPTH pad, got {len(slot_pads)}")
    else:
        pad = slot_pads[0]
        layers = pad.GetLayerSet()
        size = pad.GetSize()
        drill = pad.GetDrillSize()
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
            errors.append(f"{side}: {BATTERY_LEAD_SLOT_REF} pad is not NPTH")
        if pad.GetDrillShape() != pcbnew.PAD_DRILL_SHAPE_OBLONG:
            errors.append(f"{side}: {BATTERY_LEAD_SLOT_REF} drill is not oblong")
        if layers.Contains(pcbnew.F_Cu) or layers.Contains(pcbnew.B_Cu):
            errors.append(f"{side}: {BATTERY_LEAD_SLOT_REF} pad has copper layers")
        if pad.GetNetname():
            errors.append(f"{side}: {BATTERY_LEAD_SLOT_REF} pad is electrically netted to {pad.GetNetname()}")
        if abs(pcbnew.ToMM(size.x) - BATTERY_LEAD_SLOT_LEN) > SLOT_DIMENSION_TOLERANCE:
            errors.append(f"{side}: {BATTERY_LEAD_SLOT_REF} pad length is {pcbnew.ToMM(size.x):.3f} mm")
        if abs(pcbnew.ToMM(size.y) - BATTERY_LEAD_SLOT_W) > SLOT_DIMENSION_TOLERANCE:
            errors.append(f"{side}: {BATTERY_LEAD_SLOT_REF} pad width is {pcbnew.ToMM(size.y):.3f} mm")
        if abs(pcbnew.ToMM(drill.x) - BATTERY_LEAD_SLOT_LEN) > SLOT_DIMENSION_TOLERANCE:
            errors.append(f"{side}: {BATTERY_LEAD_SLOT_REF} drill length is {pcbnew.ToMM(drill.x):.3f} mm")
        if abs(pcbnew.ToMM(drill.y) - BATTERY_LEAD_SLOT_W) > SLOT_DIMENSION_TOLERANCE:
            errors.append(f"{side}: {BATTERY_LEAD_SLOT_REF} drill width is {pcbnew.ToMM(drill.y):.3f} mm")

    keepout_x1 = u1_x + usb_direction * ANTENNA_KEEP_START_FROM_CENTER
    keepout_x2 = keepout_x1 + usb_direction * 10.0
    antenna_keepout = (
        min(keepout_x1, keepout_x2),
        u1_y - CONTROLLER_W / 2.0,
        max(keepout_x1, keepout_x2),
        u1_y + CONTROLLER_W / 2.0,
    )
    slot_rect = (
        slot_x - BATTERY_LEAD_SLOT_LEN / 2.0,
        slot_y - BATTERY_LEAD_SLOT_W / 2.0,
        slot_x + BATTERY_LEAD_SLOT_LEN / 2.0,
        slot_y + BATTERY_LEAD_SLOT_W / 2.0,
    )
    if rects_overlap(slot_rect, antenna_keepout):
        errors.append(f"{side}: {BATTERY_LEAD_SLOT_REF} overlaps antenna keepout")
    if (
        not is_v2
        and battery_rect is not None
        and rects_overlap(slot_rect, expanded(battery_rect, BATTERY_CLEARANCE))
    ):
        errors.append(f"{side}: {BATTERY_LEAD_SLOT_REF} overlaps battery reference clearance")
    if not is_v2 and rects_overlap(slot_rect, tact_rect):
        errors.append(f"{side}: {BATTERY_LEAD_SLOT_REF} overlaps SW_RST1 body")
    clearance = slot_edge_clearance(board, slot_x, slot_y)
    if clearance < SLOT_EDGE_CLEARANCE_MIN:
        errors.append(
            f"{side}: {BATTERY_LEAD_SLOT_REF} edge clearance is {clearance:.3f} mm, "
            f"expected >= {SLOT_EDGE_CLEARANCE_MIN:.3f} mm"
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify KC2 X3 compact controller tab, no carrier battery pads, and battery lead pass-through slot.")
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

    errors: list[str] = []
    for board_path in args.boards:
        side = "left" if "left" in board_path.name else "right"
        errors.extend(check_side(side, board_path))

    if errors:
        print("FAIL: KC2 compact controller verification")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: KC2 compact controller verification")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
