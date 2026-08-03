from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pcbnew

from tools import generate_kc2_pcbs as gen
from tools.postprocess_kc2_routes import (
    add_track,
    add_via,
    apply_x3_top_edge_relief,
    delete_tracks_by_pairs,
    point_matches,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOARDS = (
    ROOT / "hardware" / "kicad" / "draft" / "x3-v2" / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb",
    ROOT / "hardware" / "kicad" / "draft" / "x3-v2" / "kc2_right-x3-v2" / "kc2_right-x3-v2.kicad_pcb",
)


def move_battery_slot_to_usb_side(board: pcbnew.BOARD, side: str) -> int:
    footprints = {footprint.GetReference(): footprint for footprint in board.GetFootprints()}
    controller = footprints.get("U1")
    slot = footprints.get("BAT_LEAD_SLOT1")
    if controller is None or slot is None:
        raise RuntimeError(f"{side}: missing U1 or BAT_LEAD_SLOT1")
    direction = 1 if side == "left" else -1
    controller_position = controller.GetPosition()
    target = gen.x3_battery_lead_slot_point(
        pcbnew.ToMM(controller_position.x),
        pcbnew.ToMM(controller_position.y),
        direction,
        "x3-v2",
    )
    old_position = slot.GetPosition()
    old = (pcbnew.ToMM(old_position.x), pcbnew.ToMM(old_position.y))
    if abs(old[0] - target[0]) <= 0.001 and abs(old[1] - target[1]) <= 0.001:
        return 0

    dx = target[0] - old[0]
    dy = target[1] - old[1]
    slot.SetPosition(gen.vxy(*target))
    for drawing in board.GetDrawings():
        if drawing.GetLayer() != pcbnew.Cmts_User:
            continue
        if isinstance(drawing, pcbnew.PCB_TEXT) and drawing.GetText() == "BAT LEAD EXIT":
            position = drawing.GetPosition()
            drawing.SetPosition(
                pcbnew.VECTOR2I(position.x + pcbnew.FromMM(dx), position.y + pcbnew.FromMM(dy))
            )
        elif hasattr(drawing, "GetStart") and hasattr(drawing, "GetEnd"):
            start = drawing.GetStart()
            end = drawing.GetEnd()
            points = (start, end)
            if all(
                abs(pcbnew.ToMM(point.x) - old[0]) <= gen.BATTERY_LEAD_SLOT_LEN / 2.0 + 0.05
                and abs(pcbnew.ToMM(point.y) - old[1]) <= gen.BATTERY_LEAD_SLOT_W / 2.0 + 0.05
                for point in points
            ):
                drawing.Move(gen.vxy(dx, dy))

    zone_name = f"{side.upper()}_BATTERY_LEAD_SLOT_NO_COPPER_TRACE_VIA"
    for zone in list(board.Zones()):
        if zone.GetZoneName() == zone_name:
            board.Remove(zone)
    gen.add_battery_lead_slot_keepout_zone(board, side, target)
    return 1


def relieve_left_col6_edge(board: pcbnew.BOARD) -> int:
    old_points = (
        (166.5050, 88.3300),
        (166.4250, 89.0500),
        (166.4250, 104.1000),
        (166.5050, 104.8200),
    )
    changed = 0
    for drawing in board.GetDrawings():
        if drawing.GetLayer() != pcbnew.Edge_Cuts or not hasattr(drawing, "GetStart"):
            continue
        for getter, setter in ((drawing.GetStart, drawing.SetStart), (drawing.GetEnd, drawing.SetEnd)):
            point = getter()
            if any(point_matches(point, target) for target in old_points):
                setter(pcbnew.VECTOR2I(pcbnew.FromMM(166.7000), point.y))
                changed += 1
    return changed


def remove_left_dangling_col3_stubs(board: pcbnew.BOARD) -> int:
    pair = ((116.7895, 83.4251), (116.7895, 86.3263))
    return sum(
        delete_tracks_by_pairs(board, "L_COL3", layer, [pair])
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu)
    )


def move_v2_assembly_graphics_to_fab(board: pcbnew.BOARD) -> int:
    changed = 0
    for footprint in board.GetFootprints():
        reference = footprint.GetReference()
        if reference.startswith("D") and footprint.Reference().GetLayer() == pcbnew.B_SilkS:
            footprint.Reference().SetLayer(pcbnew.B_Fab)
            changed += 1
        if not reference.startswith("SW"):
            continue
        for item in footprint.GraphicalItems():
            if item.GetLayer() == pcbnew.F_SilkS:
                item.SetLayer(pcbnew.F_Fab)
                changed += 1
            elif item.GetLayer() == pcbnew.B_SilkS:
                item.SetLayer(pcbnew.B_Fab)
                changed += 1
        if footprint.Reference().GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            footprint.Reference().SetLayer(pcbnew.F_Fab)
            changed += 1

    for drawing in board.GetDrawings():
        if not isinstance(drawing, pcbnew.PCB_TEXT):
            continue
        text = drawing.GetText()
        if text == "ANTENNA_INWARD" and drawing.GetLayer() == pcbnew.F_SilkS:
            drawing.SetLayer(pcbnew.F_Fab)
            changed += 1
        elif text.startswith("H") and text[1:].isdigit() and drawing.GetLayer() == pcbnew.B_Fab:
            drawing.SetLayer(pcbnew.B_SilkS)
            changed += 1
    return changed


def place_registration_labels_on_silkscreen(board: pcbnew.BOARD) -> int:
    registrations = {
        footprint.GetReference()[3:]: footprint
        for footprint in board.GetFootprints()
        if footprint.GetReference().startswith("REG")
        and footprint.GetReference()[3:].isdigit()
    }
    changed = 0
    for drawing in board.GetDrawings():
        if not isinstance(drawing, pcbnew.PCB_TEXT):
            continue
        text = drawing.GetText()
        if not text.startswith("H") or not text[1:].isdigit():
            continue
        registration = registrations.get(text[1:])
        if registration is None:
            raise RuntimeError(f"Missing REG{text[1:]} for {text}")
        center = registration.GetPosition()
        target = gen.registration_label_position(
            board,
            pcbnew.ToMM(center.x),
            pcbnew.ToMM(center.y),
        )
        current = drawing.GetPosition()
        if drawing.GetLayer() != pcbnew.B_SilkS:
            drawing.SetLayer(pcbnew.B_SilkS)
            changed += 1
        if not point_matches(current, target):
            drawing.SetPosition(gen.vxy(*target))
            changed += 1
    return changed


def bridge_right_r_col7(board: pcbnew.BOARD) -> int:
    controller_front_start = (
        (86.3100, 57.8900),
        (86.3100, 64.0000),
    )
    controller_back_start = (
        (86.3100, 64.0000),
        (149.5000, 64.0000),
    )
    controller_front_bridge = (
        (149.5000, 64.0000),
        (171.5000, 64.0000),
    )
    controller_back_end = (
        (171.5000, 64.0000),
        (196.5337, 64.0000),
    )
    controller_front_end = (
        (196.5337, 64.0000),
        (196.5337, 73.0574),
    )
    lower_path = (
        (194.7000, 121.5250),
        (199.0000, 124.0250),
        (199.0000, 129.5950),
        (198.3025, 129.5950),
    )
    for point in (
        controller_back_start[0],
        controller_back_start[-1],
        controller_back_end[0],
        controller_back_end[-1],
    ):
        add_via(board, "R_COL7", point)
    add_via(board, "R_COL7", lower_path[0])
    count = 0
    for path, layer in (
        (controller_front_start, pcbnew.F_Cu),
        (controller_back_start, pcbnew.B_Cu),
        (controller_front_bridge, pcbnew.F_Cu),
        (controller_back_end, pcbnew.B_Cu),
        (controller_front_end, pcbnew.F_Cu),
        (lower_path, pcbnew.F_Cu),
    ):
        for start, end in zip(path, path[1:]):
            before = len(list(board.GetTracks()))
            add_track(board, "R_COL7", layer, start, end)
            count += len(list(board.GetTracks())) - before
    return count


def process_board(path: Path, backup_dir: Path | None = None) -> dict[str, int]:
    side = "left" if "left" in path.name.lower() else "right"
    if backup_dir is not None:
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, backup_dir / path.name)
    board = pcbnew.LoadBoard(str(path))
    title = board.GetTitleBlock()
    title.SetDate("2026-08-03")
    title.SetRevision("draft-v2")
    result = {
        "x3_top_edge_relief_points": apply_x3_top_edge_relief(board, side),
        "assembly_graphics_moved_to_fab": move_v2_assembly_graphics_to_fab(board),
        "registration_labels_on_silkscreen": place_registration_labels_on_silkscreen(board),
        "battery_slot_moved_to_usb_side": move_battery_slot_to_usb_side(board, side),
    }
    if side == "left":
        result["left_col6_edge_relief_points"] = relieve_left_col6_edge(board)
        result["left_col3_dangling_stubs_removed"] = remove_left_dangling_col3_stubs(board)
    else:
        result["r_col7_bridge_segments"] = bridge_right_r_col7(board)
    pcbnew.SaveBoard(str(path), board)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply deterministic KC2 X3 V2 route completion.")
    parser.add_argument("boards", nargs="*", type=Path, default=list(DEFAULT_BOARDS))
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()
    for board in args.boards:
        print(f"{board}: {process_board(board, args.backup_dir)}")


if __name__ == "__main__":
    main()
