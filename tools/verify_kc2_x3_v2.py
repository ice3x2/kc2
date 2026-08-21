from __future__ import annotations

import argparse
import json
from collections import Counter
import math
from pathlib import Path
import re
from typing import Sequence

import pcbnew

from tools.generate_kc2_pcbs import x3_v2_join_geometry_by_row


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FOOTPRINT = ROOT / "third_party" / "kc2.pretty" / "SW_Choc_V2_Socket_MX_THT.kicad_mod"
V2_ROOT = ROOT / "hardware" / "kicad" / "draft" / "x3-v2"
DEFAULT_BOARDS = (
    V2_ROOT / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb",
    V2_ROOT / "kc2_right-x3-v2" / "kc2_right-x3-v2.kicad_pcb",
)
DEFAULT_MANIFEST = V2_ROOT / "kc2_x3_v2_generation_manifest.json"
EXPECTED_IGNORED_DRC_CHECKS = [
    "footprint_filters_mismatch",
    "footprint_type_mismatch",
    "missing_courtyard",
    "track_not_centered_on_via",
    "tuning_profile_track_geometries",
]


def mm(value: int) -> float:
    return round(pcbnew.ToMM(value), 3)


def pad_position(pad: pcbnew.PAD) -> tuple[float, float]:
    position = pad.GetPosition()
    return mm(position.x), mm(position.y)


def pad_size(pad: pcbnew.PAD) -> tuple[float, float]:
    size = pad.GetSize()
    return mm(size.x), mm(size.y)


def bounding_box_mm(item: object) -> tuple[float, float, float, float]:
    box = item.GetBoundingBox()
    left = pcbnew.ToMM(box.GetX())
    top = pcbnew.ToMM(box.GetY())
    return (
        left,
        top,
        left + pcbnew.ToMM(box.GetWidth()),
        top + pcbnew.ToMM(box.GetHeight()),
    )


def bounding_box_clearance_mm(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    dx = max(first[0] - second[2], second[0] - first[2], 0.0)
    dy = max(first[1] - second[3], second[1] - first[3], 0.0)
    return math.hypot(dx, dy)


def inflate_box_mm(
    box: tuple[float, float, float, float],
    amount: float,
) -> tuple[float, float, float, float]:
    return (box[0] - amount, box[1] - amount, box[2] + amount, box[3] + amount)


def boxes_overlap_mm(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
    tolerance: float = 1e-6,
) -> bool:
    return (
        min(first[2], second[2]) - max(first[0], second[0]) > tolerance
        and min(first[3], second[3]) - max(first[1], second[1]) > tolerance
    )


def point_to_segment_distance_mm(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared <= 1e-18:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    projection = (
        (point[0] - start[0]) * dx + (point[1] - start[1]) * dy
    ) / length_squared
    projection = min(1.0, max(0.0, projection))
    nearest = (start[0] + projection * dx, start[1] + projection * dy)
    return math.hypot(point[0] - nearest[0], point[1] - nearest[1])


def _orientation(
    first: tuple[float, float],
    second: tuple[float, float],
    third: tuple[float, float],
) -> float:
    return (second[0] - first[0]) * (third[1] - first[1]) - (
        second[1] - first[1]
    ) * (third[0] - first[0])


def segments_intersect_mm(
    first_start: tuple[float, float],
    first_end: tuple[float, float],
    second_start: tuple[float, float],
    second_end: tuple[float, float],
    tolerance: float = 1e-9,
) -> bool:
    orientations = (
        _orientation(first_start, first_end, second_start),
        _orientation(first_start, first_end, second_end),
        _orientation(second_start, second_end, first_start),
        _orientation(second_start, second_end, first_end),
    )
    if (
        orientations[0] * orientations[1] < -tolerance
        and orientations[2] * orientations[3] < -tolerance
    ):
        return True
    for point, start, end, orientation in (
        (second_start, first_start, first_end, orientations[0]),
        (second_end, first_start, first_end, orientations[1]),
        (first_start, second_start, second_end, orientations[2]),
        (first_end, second_start, second_end, orientations[3]),
    ):
        if abs(orientation) <= tolerance and (
            min(start[0], end[0]) - tolerance
            <= point[0]
            <= max(start[0], end[0]) + tolerance
            and min(start[1], end[1]) - tolerance
            <= point[1]
            <= max(start[1], end[1]) + tolerance
        ):
            return True
    return False


def segment_to_box_clearance_mm(
    start: tuple[float, float],
    end: tuple[float, float],
    box: tuple[float, float, float, float],
) -> float:
    corners = (
        (box[0], box[1]),
        (box[2], box[1]),
        (box[2], box[3]),
        (box[0], box[3]),
    )
    edges = tuple(zip(corners, (*corners[1:], corners[0])))
    if any(segments_intersect_mm(start, end, edge_start, edge_end) for edge_start, edge_end in edges):
        return 0.0

    def point_to_box(point: tuple[float, float]) -> float:
        dx = max(box[0] - point[0], point[0] - box[2], 0.0)
        dy = max(box[1] - point[1], point[1] - box[3], 0.0)
        return math.hypot(dx, dy)

    return min(
        point_to_box(start),
        point_to_box(end),
        *(point_to_segment_distance_mm(corner, start, end) for corner in corners),
    )


def board_outline_segments_mm(
    board: pcbnew.BOARD,
) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    outlines = pcbnew.SHAPE_POLY_SET()
    if not board.GetBoardPolygonOutlines(outlines, False):
        raise RuntimeError("KiCad could not resolve a closed Edge.Cuts outline")
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for outline_index in range(outlines.OutlineCount()):
        outline = outlines.Outline(outline_index)
        for segment_index in range(outline.SegmentCount()):
            segment = outline.CSegment(segment_index)
            segments.append(
                (
                    (pcbnew.ToMM(segment.A.x), pcbnew.ToMM(segment.A.y)),
                    (pcbnew.ToMM(segment.B.x), pcbnew.ToMM(segment.B.y)),
                )
            )
    return segments


def load_footprint(path: Path) -> pcbnew.FOOTPRINT:
    if not path.is_file():
        raise FileNotFoundError(path)
    footprint = pcbnew.FootprintLoad(str(path.parent), path.stem)
    if footprint is None:
        raise RuntimeError(f"KiCad could not load footprint: {path}")
    return footprint


def analyze_v2_footprint(path: Path = DEFAULT_FOOTPRINT) -> dict[str, object]:
    footprint = load_footprint(path)
    pads = list(footprint.Pads())
    numbered = [pad for pad in pads if pad.GetNumber()]
    smd = [pad for pad in numbered if pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
    pth = [pad for pad in numbered if pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
    npth = [pad for pad in pads if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH]

    choc_socket_smd_pads = {
        pad.GetNumber(): (*pad_position(pad), *pad_size(pad))
        for pad in smd
        if pad.IsOnLayer(pcbnew.B_Cu) and pad.IsOnLayer(pcbnew.B_Paste)
    }
    mx_tht_pads = {
        pad.GetNumber(): (*pad_position(pad), *pad_size(pad), mm(pad.GetDrillSize().x))
        for pad in pth
    }
    npth_holes = {
        (*pad_position(pad), mm(pad.GetDrillSize().x))
        for pad in npth
    }
    silk_layers = {pcbnew.F_SilkS, pcbnew.B_SilkS}
    footprint_items = [
        *footprint.GraphicalItems(),
        footprint.Reference(),
        footprint.Value(),
    ]

    return {
        "name": str(footprint.GetFPID().GetLibItemName()),
        "numbered_pad_counts": dict(sorted(Counter(pad.GetNumber() for pad in numbered).items())),
        "choc_socket_smd_pads": choc_socket_smd_pads,
        "mx_tht_pads": mx_tht_pads,
        "npth_holes": npth_holes,
        "has_choc_v1_locator_holes": any(
            abs(abs(x) - 5.5) < 0.01 and abs(y) < 0.01
            for x, y, _ in npth_holes
        ),
        "has_mx_hotswap_pads": any(
            y < -1.0 for _, y, _, _ in choc_socket_smd_pads.values()
        ),
        "has_choc_v2_direct_solder_pads": any(
            (abs(x) < 0.01 and abs(y - 5.9) < 0.01)
            or (abs(x + 5.0) < 0.01 and abs(y - 3.8) < 0.01)
            for x, y, _, _, _ in mx_tht_pads.values()
        ),
        "silkscreen_item_count": sum(item.GetLayer() in silk_layers for item in footprint_items),
    }


def matrix_footprints(board: pcbnew.BOARD, prefix: str) -> list[pcbnew.FOOTPRINT]:
    return sorted(
        (
            footprint
            for footprint in board.GetFootprints()
            if footprint.GetReference().startswith(prefix)
            and footprint.GetReference()[len(prefix):].isdigit()
        ),
        key=lambda footprint: int(footprint.GetReference()[len(prefix):]),
    )


def verify_switch_layout_against_generator(
    switches: Sequence[pcbnew.FOOTPRINT],
) -> tuple[list[str], float]:
    """Compare the committed switch pattern after removing one rigid translation."""
    from tools.generate_kc2_pcbs import (
        make_left_keys_x3_v2,
        make_right_keys_x3_v2,
        switch_rotation_for_key,
    )

    if len(switches) == 32:
        keys = make_left_keys_x3_v2()
    elif len(switches) == 39:
        keys = make_right_keys_x3_v2()
    else:
        return [f"cannot select generator layout for {len(switches)} switches"], math.inf

    errors: list[str] = []
    actual_anchor = switches[0].GetPosition()
    expected_anchor = keys[0]
    maximum_position_error = 0.0
    for index, (switch, key) in enumerate(zip(switches, keys, strict=True), start=1):
        expected_reference = f"SW{index}"
        if switch.GetReference() != expected_reference:
            errors.append(
                f"switch sequence mismatch: expected {expected_reference}, found {switch.GetReference()}"
            )

        position = switch.GetPosition()
        actual_dx = pcbnew.ToMM(position.x - actual_anchor.x)
        actual_dy = pcbnew.ToMM(position.y - actual_anchor.y)
        expected_dx = key.cx - expected_anchor.cx
        expected_dy = key.cy - expected_anchor.cy
        position_error = math.hypot(actual_dx - expected_dx, actual_dy - expected_dy)
        maximum_position_error = max(maximum_position_error, position_error)
        if position_error > 0.001:
            errors.append(
                f"{expected_reference} relative position drift: "
                f"expected ({expected_dx:.4f}, {expected_dy:.4f}) mm, "
                f"found ({actual_dx:.4f}, {actual_dy:.4f}) mm"
            )

        expected_rotation = switch_rotation_for_key(key, keys, "x3-v2") % 360.0
        actual_rotation = float(switch.GetOrientationDegrees()) % 360.0
        rotation_error = abs((actual_rotation - expected_rotation + 180.0) % 360.0 - 180.0)
        if rotation_error > 0.001:
            errors.append(
                f"{expected_reference} rotation drift: expected {expected_rotation:.3f} deg, "
                f"found {actual_rotation:.3f} deg"
            )

    return errors, round(maximum_position_error, 4)


def analyze_v2_board(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(path)
    board = pcbnew.LoadBoard(str(path))
    switches = matrix_footprints(board, "SW")
    diodes = matrix_footprints(board, "D")
    switch_layout_errors, switch_layout_max_position_error_mm = (
        verify_switch_layout_against_generator(switches)
    )
    mismatches: list[str] = []
    for switch in switches:
        for number in ("1", "2"):
            contact_pads = [pad for pad in switch.Pads() if pad.GetNumber() == number]
            nets = {pad.GetNetname() for pad in contact_pads}
            if len(contact_pads) != 2 or len(nets) != 1 or "" in nets:
                mismatches.append(
                    f"{switch.GetReference()} pad {number}: count={len(contact_pads)} nets={sorted(nets)}"
                )

    footprints = list(board.GetFootprints())
    registration_holes = [
        footprint
        for footprint in footprints
        if footprint.GetReference().startswith("REG")
        and footprint.GetReference()[3:].isdigit()
    ]
    registration_hole_errors: list[str] = []
    for footprint in registration_holes:
        pads = list(footprint.Pads())
        if len(pads) != 1:
            registration_hole_errors.append(
                f"{footprint.GetReference()}: expected one NPTH pad, found {len(pads)}"
            )
            continue
        pad = pads[0]
        drill = mm(pad.GetDrillSize().x)
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH or drill != 3.0 or pad.GetNetname():
            registration_hole_errors.append(
                f"{footprint.GetReference()}: attr={pad.GetAttribute()} drill={drill} net={pad.GetNetname()!r}"
            )

    battery_slots = [
        footprint
        for footprint in footprints
        if str(footprint.GetFPID().GetLibItemName()) == "BAT_LEAD_NPTH_SLOT_3.6x2.2"
    ]
    battery_lead_slot_errors: list[str] = []
    for footprint in battery_slots:
        pads = list(footprint.Pads())
        if len(pads) != 1:
            battery_lead_slot_errors.append(
                f"{footprint.GetReference()}: expected one NPTH slot, found {len(pads)}"
            )
            continue
        pad = pads[0]
        drill = sorted((mm(pad.GetDrillSize().x), mm(pad.GetDrillSize().y)))
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH or drill != [2.2, 3.6] or pad.GetNetname():
            battery_lead_slot_errors.append(
                f"{footprint.GetReference()}: attr={pad.GetAttribute()} drill={drill} net={pad.GetNetname()!r}"
            )
    u1 = next((footprint for footprint in footprints if footprint.GetReference() == "U1"), None)
    controller_rows = sorted(
        {
            round(pcbnew.ToMM(pad.GetPosition().y), 3)
            for pad in (u1.Pads() if u1 is not None else [])
        }
    )
    controller_socket_row_spacing_mm = (
        round(controller_rows[1] - controller_rows[0], 3)
        if len(controller_rows) == 2
        else None
    )

    unused_npth_boxes = [
        bounding_box_mm(pad)
        for switch in switches
        for pad in switch.Pads()
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH
    ]
    legacy_mount_hole_refs = sorted(
        footprint.GetReference()
        for footprint in footprints
        if re.fullmatch(r"H\d+", footprint.GetReference())
    )
    switch_pad_items = [
        (switch.GetReference(), pad.GetNetname(), bounding_box_mm(pad), pad)
        for switch in switches
        for pad in switch.Pads()
        if pad.GetNumber()
    ]
    switch_pad_boxes = [item[2] for item in switch_pad_items]
    socket_body_boxes = [
        bounding_box_mm(item)
        for switch in switches
        for item in switch.GraphicalItems()
        if item.GetLayer() == pcbnew.B_Fab
    ]
    diode_clearances: list[dict[str, object]] = []
    diode_hand_solder_clearance_errors: list[str] = []
    diode_edge_clearance_errors: list[str] = []
    diode_tool_approach_errors: list[str] = []
    outline_segments = board_outline_segments_mm(board)
    bottom_exposed_pad_items = [
        (footprint.GetReference(), pad.GetNetname(), bounding_box_mm(pad))
        for footprint in footprints
        for pad in footprint.Pads()
        if pad.GetNumber() and pad.IsOnLayer(pcbnew.B_Mask)
    ]
    untented_bottom_vias = [
        track
        for track in board.GetTracks()
        if isinstance(track, pcbnew.PCB_VIA) and not track.IsTented(pcbnew.B_Mask)
    ]
    bottom_exposed_pad_items.extend(
        ("VIA", via.GetNetname(), bounding_box_mm(via))
        for via in untented_bottom_vias
    )
    switch_assembly_boxes = [
        inflate_box_mm(box, 0.30)
        for _, _, box, _ in switch_pad_items
    ] + unused_npth_boxes + socket_body_boxes
    all_diode_pad_items = [
        (diode.GetReference(), bounding_box_mm(pad))
        for diode in diodes
        for pad in diode.Pads()
    ]
    for diode in diodes:
        diode_pads = list(diode.Pads())
        diode_boxes = [bounding_box_mm(pad) for pad in diode_pads]
        diode_nets = {pad.GetNetname() for pad in diode_pads if pad.GetNetname()}

        def clearance_to(targets: list[tuple[float, float, float, float]]) -> float:
            return min(
                bounding_box_clearance_mm(diode_box, target)
                for diode_box in diode_boxes
                for target in targets
            )

        unrelated_exposed_boxes = [
            box
            for reference, net, box in bottom_exposed_pad_items
            if reference != diode.GetReference() and net not in diode_nets
        ]
        fillet_boxes = [inflate_box_mm(box, 0.30) for box in diode_boxes]
        diode_body_boxes = [
            bounding_box_mm(item)
            for item in diode.GraphicalItems()
            if item.GetLayer() in (pcbnew.B_Fab, pcbnew.B_SilkS)
        ]
        diode_edge_envelope_boxes = [*fillet_boxes]
        if diode_body_boxes:
            diode_edge_envelope_boxes.append(
                (
                    min(box[0] for box in diode_body_boxes),
                    min(box[1] for box in diode_body_boxes),
                    max(box[2] for box in diode_body_boxes),
                    max(box[3] for box in diode_body_boxes),
                )
            )
        edge_cuts_clearance = min(
            segment_to_box_clearance_mm(start, end, envelope)
            for envelope in diode_edge_envelope_boxes
            for start, end in outline_segments
        )
        fillet_to_switch_assembly = min(
            bounding_box_clearance_mm(diode_box, target)
            for diode_box in fillet_boxes
            for target in switch_assembly_boxes
        )
        clearances = {
            "reference": diode.GetReference(),
            "unused_npth_mm": clearance_to(unused_npth_boxes),
            "switch_pad_mm": clearance_to(switch_pad_boxes),
            "socket_body_mm": clearance_to(socket_body_boxes),
            "unrelated_exposed_copper_mm": clearance_to(unrelated_exposed_boxes),
            "fillet_to_switch_assembly_mm": fillet_to_switch_assembly,
            "edge_cuts_mm": edge_cuts_clearance,
        }
        diode_clearances.append(clearances)
        for label in ("unused_npth_mm", "unrelated_exposed_copper_mm"):
            if float(clearances[label]) < 1.0 - 1e-6:
                diode_hand_solder_clearance_errors.append(
                    f"{diode.GetReference()} {label}={float(clearances[label]):.3f} mm"
                )
        if fillet_to_switch_assembly <= 1e-6:
            diode_hand_solder_clearance_errors.append(
                f"{diode.GetReference()} solder-fillet envelope intersects switch assembly"
            )
        if edge_cuts_clearance < 1.3 - 1e-6:
            diode_edge_clearance_errors.append(
                f"{diode.GetReference()} edge_cuts_mm={edge_cuts_clearance:.3f} mm"
            )

        switch = board.FindFootprintByReference(
            "SW" + diode.GetReference()[1:]
        )
        if switch is None:
            diode_tool_approach_errors.append(
                f"{diode.GetReference()}: matching switch is missing"
            )
            continue
        diode_y = pcbnew.ToMM(diode.GetPosition().y)
        switch_y = pcbnew.ToMM(switch.GetPosition().y)
        approach_obstacles = switch_assembly_boxes + [
            inflate_box_mm(box, 0.30)
            for reference, box in all_diode_pad_items
            if reference != diode.GetReference()
        ]
        for pad, pad_box in zip(diode_pads, diode_boxes):
            if diode_y < switch_y:
                corridor = (
                    pad_box[0] - 0.40,
                    pad_box[1] - 1.50,
                    pad_box[2] + 0.40,
                    pad_box[1],
                )
                direction = "north"
            else:
                corridor = (
                    pad_box[0] - 0.40,
                    pad_box[3],
                    pad_box[2] + 0.40,
                    pad_box[3] + 1.50,
                )
                direction = "south"
            if any(boxes_overlap_mm(corridor, obstacle) for obstacle in approach_obstacles):
                diode_tool_approach_errors.append(
                    f"{diode.GetReference()} pad {pad.GetNumber()}: {direction} tool corridor obstructed"
                )
    diode_hand_solder_clearance_errors.extend(diode_tool_approach_errors)
    side = "left" if "left" in path.name.lower() else "right"
    antenna_direction = 1 if side == "left" else -1
    battery_lead_slot_on_usb_side = bool(
        u1
        and len(battery_slots) == 1
        and (
            pcbnew.ToMM(battery_slots[0].GetPosition().x - u1.GetPosition().x)
            * antenna_direction
            < 0
        )
    )

    forbidden_power_names = {"BAT+", "BAT-", "NN_B+", "NN_B-"}
    forbidden_carrier_power_nets = sorted(
        {
            item.GetNetname()
            for footprint in footprints
            for item in footprint.Pads()
            if item.GetNetname() in forbidden_power_names
        }
        | {
            track.GetNetname()
            for track in board.GetTracks()
            if track.GetNetname() in forbidden_power_names
        }
    )
    drawings = list(board.GetDrawings())
    board_text = {
        drawing.GetText()
        for drawing in drawings
        if isinstance(drawing, pcbnew.PCB_TEXT)
    }
    registration_label_layers = {
        drawing.GetText(): pcbnew.LayerName(drawing.GetLayer())
        for drawing in drawings
        if isinstance(drawing, pcbnew.PCB_TEXT)
        and drawing.GetText().startswith("H")
        and drawing.GetText()[1:].isdigit()
    }
    drc_path = path.with_suffix(".drc.json")
    drc = json.loads(drc_path.read_text(encoding="utf-8")) if drc_path.is_file() else {}
    return {
        "switch_count": len(switches),
        "diode_count": len(diodes),
        "switch_footprint_names": {
            str(switch.GetFPID().GetLibItemName())
            for switch in switches
        },
        "alternate_contact_net_mismatches": mismatches,
        "switch_layout_errors": switch_layout_errors,
        "switch_layout_max_position_error_mm": switch_layout_max_position_error_mm,
        "stabilizer_refs": sorted(
            footprint.GetReference()
            for footprint in footprints
            if footprint.GetReference().startswith("STAB")
        ),
        "registration_hole_count": len(registration_holes),
        "registration_hole_errors": registration_hole_errors,
        "legacy_mount_hole_refs": legacy_mount_hole_refs,
        "registration_label_layers": registration_label_layers,
        "carrier_power_pad_refs": sorted(
            footprint.GetReference()
            for footprint in footprints
            if footprint.GetReference().startswith("J_PWR")
        ),
        "battery_lead_slot_count": len(battery_slots),
        "battery_lead_slot_errors": battery_lead_slot_errors,
        "battery_lead_slot_on_usb_side": battery_lead_slot_on_usb_side,
        "forbidden_carrier_power_nets": forbidden_carrier_power_nets,
        "controller_socket_row_spacing_mm": controller_socket_row_spacing_mm,
        "minimum_diode_to_unused_npth_clearance_mm": round(
            min(float(item["unused_npth_mm"]) for item in diode_clearances), 3
        ),
        "minimum_diode_to_unrelated_pad_clearance_mm": round(
            min(float(item["switch_pad_mm"]) for item in diode_clearances), 3
        ),
        "minimum_diode_to_unrelated_exposed_copper_clearance_mm": round(
            min(float(item["unrelated_exposed_copper_mm"]) for item in diode_clearances), 3
        ),
        "minimum_diode_to_socket_body_clearance_mm": round(
            min(float(item["socket_body_mm"]) for item in diode_clearances), 3
        ),
        "minimum_diode_fillet_to_switch_assembly_clearance_mm": round(
            min(float(item["fillet_to_switch_assembly_mm"]) for item in diode_clearances), 3
        ),
        "minimum_diode_fillet_to_edge_cuts_clearance_mm": round(
            min(float(item["edge_cuts_mm"]) for item in diode_clearances), 3
        ),
        "diode_clearances": diode_clearances,
        "untented_bottom_via_count": len(untented_bottom_vias),
        "diode_tool_approach_errors": diode_tool_approach_errors,
        "diode_edge_clearance_errors": diode_edge_clearance_errors,
        "diode_hand_solder_clearance_errors": diode_hand_solder_clearance_errors,
        "board_text": board_text,
        "drc_violation_count": len(drc.get("violations", [])),
        "drc_unconnected_count": len(drc.get("unconnected_items", [])),
        "drc_ignored_checks": sorted(item["key"] for item in drc.get("ignored_checks", [])),
    }


def analyze_v2_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def verify_v2_footprint(path: Path = DEFAULT_FOOTPRINT) -> list[str]:
    report = analyze_v2_footprint(path)
    errors: list[str] = []
    if report["name"] != "SW_Choc_V2_Socket_MX_THT":
        errors.append(f"unexpected footprint name: {report['name']}")
    if report["numbered_pad_counts"] != {"1": 2, "2": 2}:
        errors.append(f"expected two alternate pads per contact: {report['numbered_pad_counts']}")
    if report["has_choc_v1_locator_holes"]:
        errors.append("Choc V1 locator holes are forbidden")
    if report["has_mx_hotswap_pads"]:
        errors.append("MX hot-swap pads are forbidden")
    if report["has_choc_v2_direct_solder_pads"]:
        errors.append("Choc V2 direct-solder pads are forbidden")
    return errors


def verify_v2_release_candidate(
    footprint_path: Path = DEFAULT_FOOTPRINT,
    board_paths: Sequence[Path] = DEFAULT_BOARDS,
    manifest_path: Path = DEFAULT_MANIFEST,
) -> dict[str, object]:
    from tools.verify_kc2_antenna_keepout import check_board as check_antenna_keepout
    from tools.verify_kc2_compact_controller import check_side as check_compact_controller
    from tools.verify_kc2_connectivity import detect_side, verify_board as verify_connectivity

    errors = [f"footprint: {error}" for error in verify_v2_footprint(footprint_path)]
    manifest = analyze_v2_manifest(manifest_path)
    if manifest.get("variant") != "x3-v2":
        errors.append(f"manifest: unexpected variant {manifest.get('variant')!r}")
    if manifest.get("assembly_modes") != [
        "choc_v2_bottom_socket",
        "mx_5pin_top_direct_solder",
    ]:
        errors.append("manifest: assembly modes are incomplete or out of order")
    if not manifest.get("assembly_modes_mutually_exclusive"):
        errors.append("manifest: switch assembly modes must be mutually exclusive")
    if manifest.get("key_count") != {"left": 32, "right": 39, "total": 71}:
        errors.append(f"manifest: unexpected key count {manifest.get('key_count')!r}")
    if manifest.get("keycell_edge_inset_mm") != 1.5:
        errors.append("manifest: V2 key-field edge inset must be 1.5 mm")
    if manifest.get("one_unit_join_center_to_edge_mm") != 8.025:
        errors.append("manifest: V2 one-unit join center-to-edge distance must be 8.025 mm")
    if "join_center_to_edge_mm" in manifest:
        errors.append("manifest: ambiguous scalar join_center_to_edge_mm is forbidden")
    if manifest.get("join_geometry_by_row") != x3_v2_join_geometry_by_row():
        errors.append("manifest: V2 per-row joined cap/edge geometry is missing or stale")
    if manifest.get("join_keycap_setback_mm") != 1.0:
        errors.append("manifest: V2 join keycap-relative setback must be 1.0 mm")
    if manifest.get("join_keycap_gap_mm") != 1.8:
        errors.append("manifest: V2 joined MX-envelope keycap gap must be 1.8 mm")
    if manifest.get("one_unit_join_center_pitch_mm") != 19.85:
        errors.append("manifest: V2 joined one-unit center pitch must be 19.85 mm")
    if "join_center_pitch_mm" in manifest:
        errors.append("manifest: ambiguous scalar join_center_pitch_mm is forbidden")
    if manifest.get("join_placement_offset_mm") != 0.8:
        errors.append("manifest: V2 safe joined placement offset must be 0.8 mm")
    if manifest.get("row_center_joined_pcb_gap_mm") != 3.8:
        errors.append("manifest: V2 row-center PCB gap must be 3.8 mm")
    if manifest.get("minimum_joined_edge_clearance_mm") != 1.0:
        errors.append("manifest: V2 exact joined Edge.Cuts clearance gate must be 1.0 mm")
    if manifest.get("seam_transition_stagger_mm") != 0.55:
        errors.append("manifest: V2 seam transition stagger must be 0.55 mm")
    if manifest.get("outline_policy") != "keycap_concealed_except_controller_service":
        errors.append("manifest: V2 compact outline policy is missing")
    if manifest.get("autoroute_boundary_policy") != {
        "inset_mm": 0.35,
        "preserve_controller_above_y_mm": 67.5,
        "edge_cuts_unchanged": True,
    }:
        errors.append("manifest: V2 autoroute edge-clearance boundary policy is missing")
    if manifest.get("pcb_fastener_holes") != {
        "count_per_half": 0,
        "strategy": "external housing capture",
    }:
        errors.append("manifest: V2 must not use inaccessible key-field fastener holes")
    if manifest.get("screwless_registration_holes") is not None:
        errors.append("manifest: legacy H1-H9 registration holes are forbidden on V2")
    if manifest.get("controller_socket_geometry_mm") != {
        "longitudinal_pin_pitch": 2.54,
        "row_center_spacing": 15.24,
        "row_count": 2,
        "pins_per_row": 12,
    }:
        errors.append("manifest: nice!nano socket geometry must use 15.24 mm row spacing")
    diode_policy = manifest.get("diode_placement_policy") or {}
    if diode_policy.get("minimum_unused_feature_clearance_mm") != 1.0:
        errors.append("manifest: diode hand-solder clearance policy is missing")
    if diode_policy.get("minimum_edge_cuts_clearance_mm") != 1.3:
        errors.append("manifest: diode Edge.Cuts clearance policy is missing")
    if diode_policy.get("edge_safe_offsets_mm") != {
        "top_second_key": {"x": -5.0, "y": -5.6},
        "top_other_keys": {"x": -9.25, "y": -3.0},
        "bottom_first_key": {"x": 9.5, "y": 3.0},
    }:
        errors.append("manifest: verified edge-safe diode offsets are missing")

    board_reports: dict[str, object] = {}
    connectivity_errors: dict[str, list[str]] = {}
    for board_path in board_paths:
        side = detect_side(board_path)
        expected_keys = 32 if side == "left" else 39
        report = analyze_v2_board(board_path)
        board_reports[side] = report
        checks = {
            "switch count": report["switch_count"] == expected_keys,
            "diode count": report["diode_count"] == expected_keys,
            "owned switch footprint": report["switch_footprint_names"]
            == {"SW_Choc_V2_Socket_MX_THT"},
            "alternate contact nets": not report["alternate_contact_net_mismatches"],
            "switch placement matches generator": not report["switch_layout_errors"],
            "no stabilizers": not report["stabilizer_refs"],
            "no legacy key-field registration holes": report["registration_hole_count"] == 0,
            "registration hole safety": not report["registration_hole_errors"],
            "no legacy H-series mounting holes": not report["legacy_mount_hole_refs"],
            "no carrier power pads": not report["carrier_power_pad_refs"],
            "one battery lead slot": report["battery_lead_slot_count"] == 1,
            "copper-free battery lead slot": not report["battery_lead_slot_errors"],
            "battery slot on USB/B+ side": report["battery_lead_slot_on_usb_side"],
            "no carrier power nets": not report["forbidden_carrier_power_nets"],
            "diode hand-solder clearance": not report["diode_hand_solder_clearance_errors"],
            "diode Edge.Cuts clearance": not report["diode_edge_clearance_errors"],
            "V2 assembly warning": any(
                "CHOC V1 UNSUPPORTED" in text.upper() for text in report["board_text"]
            ),
            "DRC violations": report["drc_violation_count"] == 0,
            "DRC unconnected items": report["drc_unconnected_count"] == 0,
            "reviewed DRC exclusions": report["drc_ignored_checks"]
            == EXPECTED_IGNORED_DRC_CHECKS,
        }
        errors.extend(f"{side}: failed {label}" for label, passed in checks.items() if not passed)

        connectivity_errors[side] = verify_connectivity(board_path)
        errors.extend(f"{side} connectivity: {error}" for error in connectivity_errors[side])
        errors.extend(f"{side} controller: {error}" for error in check_compact_controller(side, board_path))
        keepout = tuple(float(value) for value in manifest["antenna_keepout_mm"][side])
        errors.extend(
            f"{side} antenna: {error}"
            for error in check_antenna_keepout(side, board_path, keepout)
        )

    return {
        "requirement": "CON-ARCH-004",
        "status": "draft_not_orderable_pending_physical_coupon",
        "boards": board_reports,
        "connectivity_errors": connectivity_errors,
        "reviewed_drc_exclusions": {
            "checks": EXPECTED_IGNORED_DRC_CHECKS,
            "rationale": (
                "Inherited project exclusions are limited to non-electrical library, courtyard, "
                "track-centering, and tuning-pattern diagnostics; all actual V2 violations and "
                "unconnected items remain hard failures."
            ),
        },
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify CON-ARCH-004 KC2 X3 V2 routed draft.")
    parser.add_argument("--footprint", type=Path, default=DEFAULT_FOOTPRINT)
    parser.add_argument("--boards", type=Path, nargs="*", default=DEFAULT_BOARDS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    report = verify_v2_release_candidate(args.footprint, args.boards, args.manifest)
    errors = report["errors"]
    if errors:
        raise SystemExit("FAIL: KC2 X3 V2 routed draft verification\n- " + "\n- ".join(errors))
    print(json.dumps(report, indent=2, default=list))
    print("PASS: CON-ARCH-004 routed boards, connectivity, controller, and antenna checks")


if __name__ == "__main__":
    main()
