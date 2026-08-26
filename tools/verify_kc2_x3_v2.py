from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
import math
from pathlib import Path
import re
from typing import Sequence

import pcbnew

from tools.canonical_hash import HASH_POLICY, sha256_file
from tools.generate_kc2_pcbs import (
    X3_V2_CONTROLLER_SERVICE_POSITIONS_MM,
    X3_V2_RESET_ROTATION_DEGREES,
    X3_V2_TOP_EDGE_Y_MM,
    x3_v2_join_geometry_by_row,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FOOTPRINT = ROOT / "third_party" / "kc2.pretty" / "SW_Choc_V2_Socket_MX_THT.kicad_mod"
DEFAULT_DIODE_FOOTPRINT = ROOT / "third_party" / "kc2.pretty" / "D_ES1B_SMA_HandSolder_C437840.kicad_mod"
DEFAULT_MOUNT_FOOTPRINT = ROOT / "third_party" / "kc2.pretty" / "MH_M1.4_NPTH_1.60.kicad_mod"
DEFAULT_RESET_FOOTPRINT = ROOT / "third_party" / "kc2.pretty" / "SW_NW3_A06_B3_SMD.kicad_mod"
DEFAULT_CONTROLLER_FOOTPRINTS = {
    "left": ROOT / "third_party" / "kc2.pretty" / "NiceNanoV2_Socket_24Pin_USB_OUT_LEFT.kicad_mod",
    "right": ROOT / "third_party" / "kc2.pretty" / "NiceNanoV2_Socket_24Pin_USB_OUT_RIGHT.kicad_mod",
}
V2_ROOT = ROOT / "hardware" / "kicad" / "draft" / "x3-v2"
DEFAULT_BOARDS = (
    V2_ROOT / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb",
    V2_ROOT / "kc2_right-x3-v2" / "kc2_right-x3-v2.kicad_pcb",
)
DEFAULT_MANIFEST = V2_ROOT / "kc2_x3_v2_generation_manifest.json"
DEFAULT_DRC_EVIDENCE = V2_ROOT / "kc2_x3_v2_drc_evidence.json"
DEFAULT_HOUSING_MANIFEST = (
    ROOT / "hardware" / "case" / "draft" / "x3-v2" / "kc2_x3_v2_housing_manifest.json"
)
EXPECTED_IGNORED_DRC_CHECKS = [
    "footprint_filters_mismatch",
    "footprint_type_mismatch",
    "missing_courtyard",
    "track_not_centered_on_via",
    "tuning_profile_track_geometries",
]
ALLOWED_DRC_SEVERITIES = {"error", "warning", "exclusion"}
REQUIRED_DRC_SEVERITIES = {"error", "warning"}
KICAD_10_VERSION_RE = re.compile(r"^10(?:\.\d+)+(?:[-+][0-9A-Za-z.-]+)?$")
ISO_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$"
)
EXPECTED_M1_4_MOUNTING_POINTS = {
    "left": [
        ("MH1", 142.6125, 68.0000),
        ("MH2", 128.6125, 86.5000),
        ("MH3", 100.1125, 93.5000),
        ("MH4", 57.1125, 99.0000),
        ("MH5", 133.6125, 131.5000),
        ("MH6", 55.1125, 144.0000),
        ("MH7", 165.6125, 145.0000),
        ("MH8", 102.6125, 147.0000),
    ],
    "right": [
        ("MH1", 71.6875, 68.0000),
        ("MH2", 181.1875, 85.5000),
        ("MH3", 147.6875, 93.5000),
        ("MH4", 109.6875, 96.5000),
        ("MH5", 71.6875, 105.5000),
        ("MH6", 42.1875, 106.0000),
        ("MH7", 181.1875, 134.5000),
        ("MH8", 143.1875, 134.5000),
        ("MH9", 51.6875, 144.0000),
        ("MH10", 95.6875, 147.0000),
    ],
}


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


def point_to_box_distance_mm(
    point: tuple[float, float],
    box: tuple[float, float, float, float],
) -> float:
    dx = max(box[0] - point[0], point[0] - box[2], 0.0)
    dy = max(box[1] - point[1], point[1] - box[3], 0.0)
    return math.hypot(dx, dy)


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


def _canonical_layer_names(pad: pcbnew.PAD, flipped_to_front: bool) -> tuple[str, ...]:
    if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH:
        # KiCad normalizes library `*.Cu *.Mask` NPTH declarations to mask-only
        # layer sets when a footprint is saved into a board. The NPTH attribute,
        # not that serialization difference, is the copper-free contract.
        return ("NPTH_COPPER_FREE",)
    names = []
    for layer in pad.GetLayerSet().Seq():
        name = pcbnew.LayerName(layer)
        if flipped_to_front and name.startswith("B."):
            name = "F." + name[2:]
        names.append(name)
    return tuple(sorted(names))


def normalized_pad_signatures(
    footprint: pcbnew.FOOTPRINT,
    *,
    normalize_flip: bool = False,
) -> list[tuple[object, ...]]:
    flipped = bool(normalize_flip and footprint.IsFlipped())
    signatures: list[tuple[object, ...]] = []
    for pad in footprint.Pads():
        relative = pad.GetFPRelativePosition()
        relative_y = -mm(relative.y) if flipped else mm(relative.y)
        signatures.append(
            (
                pad.GetNumber(),
                mm(relative.x),
                relative_y,
                *pad_size(pad),
                mm(pad.GetDrillSize().x),
                mm(pad.GetDrillSize().y),
                int(pad.GetAttribute()),
                int(pad.GetShape()),
                _canonical_layer_names(pad, flipped),
            )
        )
    return sorted(signatures, key=repr)


def normalized_diode_graphics(
    footprint: pcbnew.FOOTPRINT,
) -> list[tuple[object, ...]]:
    flipped = footprint.IsFlipped()
    signatures: list[tuple[object, ...]] = []
    for item in footprint.GraphicalItems():
        layer = pcbnew.LayerName(item.GetLayer())
        if layer not in {"F.Fab", "B.Fab", "F.Courtyard", "B.Courtyard", "F.Silkscreen", "B.Silkscreen"}:
            continue
        if flipped and layer.startswith("B."):
            layer = "F." + layer[2:]
        relative = item.GetFPRelativePosition()
        relative_y = -mm(relative.y) if flipped else mm(relative.y)
        if isinstance(item, pcbnew.PCB_SHAPE):
            signatures.append(
                (
                    "shape",
                    layer,
                    int(item.GetShape()),
                    mm(relative.x),
                    relative_y,
                    mm(item.GetLength()),
                    mm(item.GetWidth()),
                )
            )
        elif isinstance(item, pcbnew.PCB_TEXT):
            signatures.append(
                (
                    "text",
                    layer,
                    item.GetText(),
                    mm(relative.x),
                    relative_y,
                    mm(item.GetTextSize().x),
                    mm(item.GetTextSize().y),
                    mm(item.GetTextThickness()),
                )
            )
    return sorted(signatures, key=repr)


def normalized_footprint_graphics(
    footprint: pcbnew.FOOTPRINT,
) -> list[tuple[object, ...]]:
    """Return owned local graphic geometry without using shape GetLength()."""
    normalized = pcbnew.FOOTPRINT(footprint)
    normalized.SetPosition(pcbnew.VECTOR2I(0, 0))
    normalized.SetOrientationDegrees(0)
    signatures: list[tuple[object, ...]] = []
    for item in normalized.GraphicalItems():
        layer = pcbnew.LayerName(item.GetLayer())
        if layer not in {"F.Fab", "F.Courtyard", "F.Silkscreen"}:
            continue
        if isinstance(item, pcbnew.PCB_SHAPE):
            start = item.GetStart()
            end = item.GetEnd()
            signatures.append(
                (
                    "shape",
                    layer,
                    int(item.GetShape()),
                    mm(start.x),
                    mm(start.y),
                    mm(end.x),
                    mm(end.y),
                    mm(item.GetWidth()),
                )
            )
        elif isinstance(item, pcbnew.PCB_TEXT):
            position = item.GetPosition()
            signatures.append(
                (
                    "text",
                    layer,
                    item.GetText(),
                    mm(position.x),
                    mm(position.y),
                    mm(item.GetTextSize().x),
                    mm(item.GetTextSize().y),
                    mm(item.GetTextThickness()),
                )
            )
    return sorted(signatures, key=repr)


def verify_placed_footprint_contracts(
    board: pcbnew.BOARD,
    switches: Sequence[pcbnew.FOOTPRINT],
    diodes: Sequence[pcbnew.FOOTPRINT],
    side: str,
) -> tuple[list[str], list[str], list[str], list[str]]:
    diode_errors: list[str] = []
    switch_errors: list[str] = []
    controller_errors: list[str] = []
    reset_errors: list[str] = []

    diode_source = load_footprint(DEFAULT_DIODE_FOOTPRINT)
    expected_diode_pads = normalized_pad_signatures(diode_source, normalize_flip=True)
    expected_diode_graphics = normalized_diode_graphics(diode_source)
    for diode in diodes:
        if diode.GetLayer() != pcbnew.B_Cu or not diode.IsFlipped():
            diode_errors.append(
                f"{diode.GetReference()}: ES1B must be mirrored on B.Cu"
            )
        if normalized_pad_signatures(diode, normalize_flip=True) != expected_diode_pads:
            diode_errors.append(f"{diode.GetReference()}: pads differ from owned ES1B footprint")
        if normalized_diode_graphics(diode) != expected_diode_graphics:
            diode_errors.append(
                f"{diode.GetReference()}: B.Fab/courtyard/B.Silk cathode geometry differs from owned ES1B footprint"
            )

    switch_source = load_footprint(DEFAULT_FOOTPRINT)
    expected_switch_pads = normalized_pad_signatures(switch_source)
    for switch in switches:
        if normalized_pad_signatures(switch) != expected_switch_pads:
            switch_errors.append(
                f"{switch.GetReference()}: pad/NPTH geometry differs from owned hybrid-switch footprint"
            )

    controller = board.FindFootprintByReference("U1")
    controller_source = load_footprint(DEFAULT_CONTROLLER_FOOTPRINTS[side])
    expected_fpid = f"NiceNanoV2_Socket_24Pin_USB_OUT_{side.upper()}"
    if controller is None:
        controller_errors.append("U1 is missing")
    else:
        if str(controller.GetFPID().GetLibItemName()) != expected_fpid:
            controller_errors.append(f"U1 FPID must be {expected_fpid}")
        if len(list(controller.Pads())) != 24:
            controller_errors.append("U1 must have exactly 24 pads")
        if normalized_pad_signatures(controller) != normalized_pad_signatures(controller_source):
            controller_errors.append(
                "U1 pad labels/positions/sizes/drills/layers differ from the side-specific owned footprint"
            )
        expected_position = X3_V2_CONTROLLER_SERVICE_POSITIONS_MM[side]["u1"]
        controller_position = controller.GetPosition()
        actual_position = (
            round(pcbnew.ToMM(controller_position.x), 4),
            round(pcbnew.ToMM(controller_position.y), 4),
        )
        if actual_position != expected_position:
            controller_errors.append(
                f"U1 position {actual_position} differs from exact V2 position {expected_position}"
            )
    expected_usb_text = f"USB_OUT_{side.upper()}"
    usb_labels = [
        item
        for item in board.GetDrawings()
        if isinstance(item, pcbnew.PCB_TEXT) and item.GetText().startswith("USB_OUT_")
    ]
    if len(usb_labels) != 1 or usb_labels[0].GetText() != expected_usb_text:
        controller_errors.append(f"board USB direction label must be exactly {expected_usb_text}")
    elif usb_labels[0].GetLayer() != pcbnew.F_SilkS:
        controller_errors.append("board USB direction label must be on F.Silkscreen")

    reset = board.FindFootprintByReference("SW_RST1")
    if reset is None:
        reset_errors.append("SW_RST1 is missing")
    else:
        reset_source = load_footprint(DEFAULT_RESET_FOOTPRINT)
        if str(reset.GetFPID().GetLibItemName()) != "SW_NW3_A06_B3_SMD":
            reset_errors.append("SW_RST1 must use the owned SW_NW3_A06_B3_SMD footprint")
        if normalized_pad_signatures(reset) != normalized_pad_signatures(reset_source):
            reset_errors.append("SW_RST1 pad geometry differs from the owned footprint")
        if normalized_footprint_graphics(reset) != normalized_footprint_graphics(reset_source):
            reset_errors.append("SW_RST1 Fab/courtyard/silkscreen geometry differs from the owned footprint")
        expected_position = X3_V2_CONTROLLER_SERVICE_POSITIONS_MM[side]["reset"]
        reset_position = reset.GetPosition()
        actual_position = (
            round(pcbnew.ToMM(reset_position.x), 4),
            round(pcbnew.ToMM(reset_position.y), 4),
        )
        if actual_position != expected_position:
            reset_errors.append(
                f"SW_RST1 position {actual_position} differs from exact V2 position {expected_position}"
            )
        actual_rotation = round(reset.GetOrientation().AsDegrees() % 360.0, 3)
        if actual_rotation != X3_V2_RESET_ROTATION_DEGREES:
            reset_errors.append(
                f"SW_RST1 rotation {actual_rotation} differs from exact V2 rotation "
                f"{X3_V2_RESET_ROTATION_DEGREES}"
            )
        reset_pads = {pad.GetNumber(): pad.GetNetname() for pad in reset.Pads()}
        expected_reset_net = "RST"
        if reset_pads != {"1": expected_reset_net, "2": "GND"}:
            reset_errors.append(
                f"SW_RST1 must be pad1={expected_reset_net}, pad2=GND; found {reset_pads}"
            )
    return diode_errors, switch_errors, controller_errors, reset_errors


def expected_m1_4_mount_manifest() -> dict[str, object]:
    return {
        "footprint": "kc2.pretty:MH_M1.4_NPTH_1.60",
        "references": "MH1..MH8 left; MH1..MH10 right",
        "counts": {"left": 8, "right": 10, "total": 18},
        "positions_mm": {
            side: [
                {"ref": ref, "x": x, "y": y}
                for ref, x, y in points
            ]
            for side, points in EXPECTED_M1_4_MOUNTING_POINTS.items()
        },
        "hole": {
            "type": "NPTH",
            "diameter_mm": 1.6,
            "unnetted": True,
            "copper_free": True,
        },
        "front_silkscreen_reference": {
            "visible": True,
            "text_height_mm": 0.8,
            "stroke_mm": 0.1,
            "relative_position_mm": {"x": 0.0, "y": -1.5},
        },
        "screw_head_envelope_mm": {"diameter": 2.0, "height": 0.5},
        "vertical_driver_envelope_mm": {"diameter": 3.0},
        "provisional_under_head_screw_length_mm": 4.0,
        "service_state": {"keycaps": "removed", "switches": "installed"},
        "housing_interface_mm": {
            "zero_gap_support_land_diameter": 3.0,
            "provisional_blind_pilot_diameter": 1.1,
            "provisional_blind_pilot_depth": 2.8,
            "desk_column_closed_bottom": 0.7,
        },
        "registration_status": "pending_full_pattern_physical_fit",
        "physical_validation": "pending",
        "order_ready": False,
    }


def verify_m1_4_mounting_holes(
    board: pcbnew.BOARD,
    side: str,
) -> tuple[
    list[str],
    list[tuple[str, float, float]],
    dict[str, float | None],
    list[str],
    list[str],
]:
    errors: list[str] = []
    silkscreen_errors: list[str] = []
    holes = matrix_footprints(board, "MH")
    positions = [
        (
            hole.GetReference(),
            round(pcbnew.ToMM(hole.GetPosition().x), 4),
            round(pcbnew.ToMM(hole.GetPosition().y), 4),
        )
        for hole in holes
    ]
    expected_positions = EXPECTED_M1_4_MOUNTING_POINTS[side]
    if positions != expected_positions:
        errors.append(
            f"{side}: exact MH positions differ: expected {expected_positions}, found {positions}"
        )

    source = load_footprint(DEFAULT_MOUNT_FOOTPRINT)
    expected_pads = normalized_pad_signatures(source)
    for hole in holes:
        reference = hole.Reference()
        reference_position = reference.GetFPRelativePosition()
        reference_signature = (
            reference.IsVisible(),
            reference.GetLayer(),
            mm(reference.GetTextHeight()),
            mm(reference.GetTextThickness()),
            mm(reference_position.x),
            mm(reference_position.y),
        )
        if reference_signature != (True, pcbnew.F_SilkS, 0.8, 0.1, 0.0, -1.5):
            silkscreen_errors.append(
                f"{hole.GetReference()}: visible F.SilkS reference must be "
                "0.80 mm high / 0.10 mm stroke at relative (0.0,-1.5) mm; "
                f"found {reference_signature}"
            )
        if str(hole.GetFPID().GetLibItemName()) != "MH_M1.4_NPTH_1.60":
            errors.append(f"{hole.GetReference()}: unexpected mounting footprint")
        if str(hole.GetValue()) != "M1.4_NPTH_1.60":
            errors.append(f"{hole.GetReference()}: unexpected mounting value")
        if abs(float(hole.GetOrientationDegrees())) > 1e-6:
            errors.append(f"{hole.GetReference()}: mounting footprint rotation must be zero")
        pads = list(hole.Pads())
        if normalized_pad_signatures(hole) != expected_pads:
            errors.append(f"{hole.GetReference()}: pad geometry differs from owned M1.4 footprint")
        if len(pads) != 1:
            errors.append(f"{hole.GetReference()}: expected one NPTH pad, found {len(pads)}")
            continue
        pad = pads[0]
        if (
            pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH
            or pad.GetNumber()
            or pad.GetNetname()
            or pad_size(pad) != (1.6, 1.6)
            or (mm(pad.GetDrillSize().x), mm(pad.GetDrillSize().y)) != (1.6, 1.6)
        ):
            errors.append(
                f"{hole.GetReference()}: must be one unnumbered, unnetted, copper-free 1.60 mm NPTH"
            )

    hole_centers = [(x, y) for _, x, y in positions]
    copper_pads = [
        (f"{footprint.GetReference()}.{pad.GetNumber()}", bounding_box_mm(pad))
        for footprint in board.GetFootprints()
        if not re.fullmatch(r"MH\d+", footprint.GetReference())
        for pad in footprint.Pads()
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH
        and (pad.IsOnLayer(pcbnew.F_Cu) or pad.IsOnLayer(pcbnew.B_Cu))
    ]
    copper_clearances: list[float] = []
    for center in hole_centers:
        copper_clearances.extend(
            point_to_box_distance_mm(center, box) - 0.8
            for _label, box in copper_pads
        )
        for track in board.GetTracks():
            if isinstance(track, pcbnew.PCB_VIA):
                at = track.GetPosition()
                copper_clearances.append(
                    math.hypot(
                        center[0] - pcbnew.ToMM(at.x),
                        center[1] - pcbnew.ToMM(at.y),
                    )
                    - pcbnew.ToMM(track.GetWidth(pcbnew.F_Cu)) / 2.0
                    - 0.8
                )
            else:
                start = track.GetStart()
                end = track.GetEnd()
                copper_clearances.append(
                    point_to_segment_distance_mm(
                        center,
                        (pcbnew.ToMM(start.x), pcbnew.ToMM(start.y)),
                        (pcbnew.ToMM(end.x), pcbnew.ToMM(end.y)),
                    )
                    - pcbnew.ToMM(track.GetWidth()) / 2.0
                    - 0.8
                )
    minimum_copper_clearance = min(copper_clearances) if copper_clearances else math.inf
    if minimum_copper_clearance < 0.30 - 1e-6:
        errors.append(
            f"{side}: M1.4 NPTH edge-to-copper clearance {minimum_copper_clearance:.4f} mm is below 0.30 mm"
        )

    driver_copper_measurements: list[tuple[float, str]] = []
    for reference, x, y in positions:
        center = (x, y)
        driver_copper_measurements.extend(
            (
                point_to_box_distance_mm(center, box) - 1.5,
                f"{reference} vs pad {label}",
            )
            for label, box in copper_pads
        )
        for track in board.GetTracks():
            if isinstance(track, pcbnew.PCB_VIA):
                at = track.GetPosition()
                margin = (
                    math.hypot(x - pcbnew.ToMM(at.x), y - pcbnew.ToMM(at.y))
                    - pcbnew.ToMM(track.GetWidth(pcbnew.F_Cu)) / 2.0
                    - 1.5
                )
                label = (
                    f"{reference} vs via {track.GetNetname()} "
                    f"({pcbnew.ToMM(at.x):.4f},{pcbnew.ToMM(at.y):.4f})"
                )
            else:
                start = track.GetStart()
                end = track.GetEnd()
                start_mm = (pcbnew.ToMM(start.x), pcbnew.ToMM(start.y))
                end_mm = (pcbnew.ToMM(end.x), pcbnew.ToMM(end.y))
                margin = (
                    point_to_segment_distance_mm(center, start_mm, end_mm)
                    - pcbnew.ToMM(track.GetWidth()) / 2.0
                    - 1.5
                )
                label = (
                    f"{reference} vs {board.GetLayerName(track.GetLayer())} "
                    f"track {track.GetNetname()} {start_mm}->{end_mm}"
                )
            driver_copper_measurements.append((margin, label))
    minimum_driver_copper_clearance = min(
        (margin for margin, _label in driver_copper_measurements),
        default=math.inf,
    )
    driver_copper_errors = [
        f"{side}: final 3.00 mm PH0 driver intersects copper: {label}; margin {margin:.4f} mm"
        for margin, label in driver_copper_measurements
        if margin < -1e-6
    ]
    errors.extend(driver_copper_errors)

    switch_driver_boxes = [
        (
            pcbnew.ToMM(switch.GetPosition().x) - 7.8,
            pcbnew.ToMM(switch.GetPosition().y) - 7.8,
            pcbnew.ToMM(switch.GetPosition().x) + 7.8,
            pcbnew.ToMM(switch.GetPosition().y) + 7.8,
        )
        for switch in matrix_footprints(board, "SW")
    ]
    controller_service_boxes = [
        bounding_box_mm(footprint)
        for footprint in board.GetFootprints()
        if footprint.GetReference() in {"U1", "SW_RST1"}
    ]
    driver_boxes = switch_driver_boxes + controller_service_boxes
    driver_clearances = [
        point_to_box_distance_mm(center, box) - 1.5
        for center in hole_centers
        for box in driver_boxes
    ]
    minimum_driver_clearance = min(driver_clearances) if driver_clearances else math.inf
    if minimum_driver_clearance < -1e-6:
        errors.append(
            f"{side}: final 3.00 mm PH0 driver envelope intersects an installed body by "
            f"{-minimum_driver_clearance:.4f} mm"
        )

    outline_segments = board_outline_segments_mm(board)
    edge_clearances = [
        point_to_segment_distance_mm(center, start, end) - 1.0
        for center in hole_centers
        for start, end in outline_segments
    ]
    minimum_head_edge_clearance = min(edge_clearances) if edge_clearances else math.inf
    if minimum_head_edge_clearance < 0.25 - 1e-6:
        errors.append(
            f"{side}: screw-head-to-Edge.Cuts clearance {minimum_head_edge_clearance:.4f} mm is below 0.25 mm"
        )

    return errors, positions, {
        "minimum_npth_edge_to_copper_mm": round(minimum_copper_clearance, 4),
        "minimum_driver_to_copper_mm": round(minimum_driver_copper_clearance, 4),
        "minimum_driver_to_installed_body_mm": round(minimum_driver_clearance, 4),
        "minimum_head_to_edge_cuts_mm": round(minimum_head_edge_clearance, 4),
    }, driver_copper_errors, silkscreen_errors


def project_default_clearance_mm(project_path: Path) -> float:
    project = json.loads(project_path.read_text(encoding="utf-8"))
    default = next(
        netclass
        for netclass in project["net_settings"]["classes"]
        if netclass.get("name") == "Default"
    )
    return float(default["clearance"])


def _dsn_default_clearances(dsn_path: Path) -> dict[str, int]:
    text = dsn_path.read_text(encoding="utf-8")
    global_match = re.search(
        r"\(structure\b[\s\S]*?\(rule\b[\s\S]*?\(clearance\s+(\d+)\)",
        text,
    )
    default_match = re.search(
        r"\(class\s+kicad_default\b[\s\S]*?\(rule\b[\s\S]*?\(clearance\s+(\d+)\)",
        text,
    )
    return {
        label: int(match.group(1))
        for label, match in (("global", global_match), ("kicad_default", default_match))
        if match is not None
    }


def verify_canonical_route_evidence(
    manifest: dict[str, object],
) -> tuple[list[str], dict[str, object]]:
    errors: list[str] = []
    reports: dict[str, object] = {}
    if manifest.get("hash_policy") != HASH_POLICY:
        errors.append("manifest: canonical hash policy mismatch")
    records = manifest.get("canonical_route_evidence")
    if not isinstance(records, dict):
        return ["manifest: canonical route evidence is missing"], reports
    for side in ("left", "right"):
        record = records.get(side)
        if not isinstance(record, dict):
            errors.append(f"{side}: canonical route evidence is missing")
            continue
        expected_dsn = (
            f"hardware/kicad/draft/x3-v2/autoroute/"
            f"kc2_{side}-x3-v2-70-es1b-controller-r3.dsn"
        )
        expected_session_source_dsn = expected_dsn
        expected_ses = (
            f"hardware/kicad/draft/x3-v2/autoroute/"
            f"kc2_{side}-x3-v2-70-es1b-controller-r3.ses"
        )
        if record.get("dsn") != expected_dsn:
            errors.append(f"{side}: canonical DSN path mismatch")
        if record.get("ses") != expected_ses:
            errors.append(f"{side}: canonical SES path mismatch")
        if record.get("session_source_dsn") != expected_session_source_dsn:
            errors.append(f"{side}: reviewed SES source DSN path mismatch")
        if record.get("dsn_role") != "current_mh_compact_controller_trackless_routing_input":
            errors.append(f"{side}: current MH DSN role mismatch")
        if record.get("ses_role") != "reviewed_compact_controller_import_plus_exact_edge_cleanup":
            errors.append(f"{side}: reviewed SES/detour role mismatch")
        try:
            dsn_path = ROOT / str(record.get("dsn"))
            session_source_dsn_path = ROOT / str(record.get("session_source_dsn"))
            ses_path = ROOT / str(record.get("ses"))
            dsn_sha = sha256_file(dsn_path)
            session_source_dsn_sha = sha256_file(session_source_dsn_path)
            ses_sha = sha256_file(ses_path)
            clearances = _dsn_default_clearances(dsn_path)
            dsn_text = dsn_path.read_text(encoding="utf-8")
        except OSError as error:
            errors.append(f"{side}: canonical route source cannot be read: {error}")
            continue
        minimum_clearance = min(clearances.values()) if clearances else None
        reports[side] = {
            "dsn_sha256": dsn_sha,
            "session_source_dsn_sha256": session_source_dsn_sha,
            "ses_sha256": ses_sha,
            "dsn_mounting_hole_count": len(
                re.findall(r"\(place\s+MH\d+\b", dsn_text)
            ),
            "dsn_default_clearance_internal_units": minimum_clearance,
            "dsn_clearances_internal_units": clearances,
        }
        if record.get("dsn_sha256") != dsn_sha:
            errors.append(f"{side}: DSN SHA-256 mismatch")
        if record.get("ses_sha256") != ses_sha:
            errors.append(f"{side}: SES SHA-256 mismatch")
        if record.get("session_source_dsn_sha256") != session_source_dsn_sha:
            errors.append(f"{side}: reviewed SES source DSN SHA-256 mismatch")
        expected_holes = 8 if side == "left" else 10
        if reports[side]["dsn_mounting_hole_count"] != expected_holes:
            errors.append(f"{side}: current DSN does not contain the exact MH pattern")
        if record.get("dsn_mounting_hole_count") != expected_holes:
            errors.append(f"{side}: current DSN MH count evidence mismatch")
        if set(clearances) != {"global", "kicad_default"} or minimum_clearance is None or minimum_clearance < 300:
            errors.append(f"{side}: DSN global/default clearance must be at least 300 internal units")
        if record.get("dsn_default_clearance_internal_units") != minimum_clearance:
            errors.append(f"{side}: DSN clearance evidence mismatch")
        if record.get("dsn_clearances_internal_units") != clearances:
            errors.append(f"{side}: DSN global/default clearance evidence mismatch")
    return errors, reports


def verify_switch_layout_against_generator(
    switches: Sequence[pcbnew.FOOTPRINT],
) -> tuple[list[str], float]:
    """Compare the committed switch pattern after removing one rigid translation."""
    from tools.generate_kc2_pcbs import (
        make_left_keys_x3_v2,
        make_right_keys_x3_v2,
        switch_rotation_for_key,
    )

    if len(switches) == 31:
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
    from tools.finalize_kc2_x3_v2_routes import (
        _route_counter_digest,
        _route_signature,
    )

    route_signatures = Counter(_route_signature(item) for item in board.GetTracks())
    switches = matrix_footprints(board, "SW")
    diodes = matrix_footprints(board, "D")
    side = "left" if "left" in path.name.lower() else "right"
    (
        mounting_hole_errors,
        mounting_hole_positions_mm,
        mounting_hole_clearances,
        mounting_hole_driver_copper_errors,
        mounting_hole_silkscreen_errors,
    ) = verify_m1_4_mounting_holes(board, side)
    (
        diode_footprint_geometry_errors,
        switch_footprint_geometry_errors,
        controller_contract_errors,
        reset_contract_errors,
    ) = verify_placed_footprint_contracts(board, switches, diodes, side)
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
    diode_tool_approaches: list[dict[str, object]] = []
    diode_to_unrelated_route_errors: list[str] = []
    diode_pin_net_errors: list[str] = []
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
    bottom_route_items: list[dict[str, object]] = []
    for track in board.GetTracks():
        if isinstance(track, pcbnew.PCB_VIA):
            bottom_route_items.append(
                {
                    "kind": "via",
                    "net": track.GetNetname(),
                    "box": bounding_box_mm(track),
                }
            )
        elif track.IsOnLayer(pcbnew.B_Cu):
            start = track.GetStart()
            end = track.GetEnd()
            bottom_route_items.append(
                {
                    "kind": "track",
                    "net": track.GetNetname(),
                    "start": (pcbnew.ToMM(start.x), pcbnew.ToMM(start.y)),
                    "end": (pcbnew.ToMM(end.x), pcbnew.ToMM(end.y)),
                    "half_width_mm": pcbnew.ToMM(track.GetWidth()) / 2.0,
                }
            )
    for diode in diodes:
        diode_pads = list(diode.Pads())
        diode_boxes = [bounding_box_mm(pad) for pad in diode_pads]
        diode_nets = {pad.GetNetname() for pad in diode_pads if pad.GetNetname()}

        pad_nets = {
            pad.GetNumber(): pad.GetNetname()
            for pad in diode_pads
            if pad.GetNumber()
        }
        switch = board.FindFootprintByReference("SW" + diode.GetReference()[1:])
        switch_pad_2_nets = {
            pad.GetNetname()
            for pad in (switch.Pads() if switch is not None else [])
            if pad.GetNumber() == "2"
        }
        expected_row_prefix = "L_ROW" if "left" in path.name.lower() else "R_ROW"
        if set(pad_nets) != {"1", "2"}:
            diode_pin_net_errors.append(
                f"{diode.GetReference()}: expected exactly pins 1/2, found {sorted(pad_nets)}"
            )
        elif not pad_nets["1"].startswith(expected_row_prefix):
            diode_pin_net_errors.append(
                f"{diode.GetReference()} pin 1 cathode must be a {expected_row_prefix} net; "
                f"found {pad_nets['1']!r}"
            )
        elif switch is None or switch_pad_2_nets != {pad_nets["2"]}:
            diode_pin_net_errors.append(
                f"{diode.GetReference()} pin 2 anode {pad_nets['2']!r} does not match "
                f"the paired switch pad-2 net {sorted(switch_pad_2_nets)}"
            )

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
        unrelated_route_clearances: list[float] = []
        for route in bottom_route_items:
            if route["net"] in diode_nets:
                continue
            for fillet_box in fillet_boxes:
                if route["kind"] == "via":
                    route_clearance = bounding_box_clearance_mm(
                        fillet_box,
                        route["box"],
                    )
                else:
                    route_clearance = segment_to_box_clearance_mm(
                        route["start"],
                        route["end"],
                        fillet_box,
                    ) - float(route["half_width_mm"])
                unrelated_route_clearances.append(route_clearance)
        fillet_to_unrelated_route = (
            min(unrelated_route_clearances)
            if unrelated_route_clearances
            else math.inf
        )
        clearances = {
            "reference": diode.GetReference(),
            "unused_npth_mm": clearance_to(unused_npth_boxes),
            "switch_pad_mm": clearance_to(switch_pad_boxes),
            "socket_body_mm": clearance_to(socket_body_boxes),
            "unrelated_exposed_copper_mm": clearance_to(unrelated_exposed_boxes),
            "fillet_to_switch_assembly_mm": fillet_to_switch_assembly,
            "fillet_to_unrelated_route_mm": fillet_to_unrelated_route,
            "edge_cuts_mm": edge_cuts_clearance,
        }
        diode_clearances.append(clearances)
        for label in (
            "unused_npth_mm",
            "switch_pad_mm",
            "unrelated_exposed_copper_mm",
        ):
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
        if fillet_to_unrelated_route < 0.10 - 1e-6:
            diode_to_unrelated_route_errors.append(
                f"{diode.GetReference()} solder-fillet envelope to unrelated B.Cu routing "
                f"is {fillet_to_unrelated_route:.3f} mm; expected at least 0.100 mm"
            )

        if switch is None:
            diode_tool_approach_errors.append(
                f"{diode.GetReference()}: matching switch is missing"
            )
            continue
        approach_obstacles = switch_assembly_boxes + [
            inflate_box_mm(box, 0.30)
            for reference, box in all_diode_pad_items
            if reference != diode.GetReference()
        ]
        for pad, pad_box in zip(diode_pads, diode_boxes):
            corridors = {
                "north": (
                    pad_box[0] - 0.40,
                    pad_box[1] - 1.50,
                    pad_box[2] + 0.40,
                    pad_box[1],
                ),
                "south": (
                    pad_box[0] - 0.40,
                    pad_box[3],
                    pad_box[2] + 0.40,
                    pad_box[3] + 1.50,
                ),
                "west": (
                    pad_box[0] - 1.50,
                    pad_box[1] - 0.40,
                    pad_box[0],
                    pad_box[3] + 0.40,
                ),
                "east": (
                    pad_box[2],
                    pad_box[1] - 0.40,
                    pad_box[2] + 1.50,
                    pad_box[3] + 0.40,
                ),
            }
            direction = next(
                (
                    candidate_direction
                    for candidate_direction, corridor in corridors.items()
                    if not any(
                        boxes_overlap_mm(corridor, obstacle)
                        for obstacle in approach_obstacles
                    )
                ),
                None,
            )
            if direction is None:
                diode_tool_approach_errors.append(
                    f"{diode.GetReference()} pad {pad.GetNumber()}: no unobstructed "
                    "1.50 mm cardinal tool corridor"
                )
            else:
                diode_tool_approaches.append(
                    {
                        "reference": diode.GetReference(),
                        "pad": pad.GetNumber(),
                        "direction": direction,
                        "length_mm": 1.5,
                    }
                )
    diode_hand_solder_clearance_errors.extend(diode_tool_approach_errors)
    diode_hand_solder_clearance_errors.extend(diode_to_unrelated_route_errors)
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
        "diode_footprint_names": {
            str(diode.GetFPID().GetLibItemName())
            for diode in diodes
        },
        "diode_values": {diode.GetValue() for diode in diodes},
        "diode_pin_net_errors": diode_pin_net_errors,
        "diode_footprint_geometry_errors": diode_footprint_geometry_errors,
        "switch_footprint_names": {
            str(switch.GetFPID().GetLibItemName())
            for switch in switches
        },
        "alternate_contact_net_mismatches": mismatches,
        "switch_footprint_geometry_errors": switch_footprint_geometry_errors,
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
        "mounting_hole_positions_mm": mounting_hole_positions_mm,
        "mounting_hole_errors": mounting_hole_errors,
        "mounting_hole_clearances": mounting_hole_clearances,
        "mounting_hole_driver_copper_errors": mounting_hole_driver_copper_errors,
        "mounting_hole_silkscreen_errors": mounting_hole_silkscreen_errors,
        "route_track_via_count": sum(route_signatures.values()),
        "route_digest_sha256": _route_counter_digest(route_signatures),
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
        "controller_contract_errors": controller_contract_errors,
        "reset_contract_errors": reset_contract_errors,
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
        "minimum_diode_fillet_to_unrelated_route_mm": (
            round(
                min(float(item["fillet_to_unrelated_route_mm"]) for item in diode_clearances),
                3,
            )
            if any(
                math.isfinite(float(item["fillet_to_unrelated_route_mm"]))
                for item in diode_clearances
            )
            else None
        ),
        "minimum_diode_fillet_to_edge_cuts_clearance_mm": round(
            min(float(item["edge_cuts_mm"]) for item in diode_clearances), 3
        ),
        "diode_clearances": diode_clearances,
        "untented_bottom_via_count": len(untented_bottom_vias),
        "diode_tool_approach_errors": diode_tool_approach_errors,
        "diode_tool_approaches": diode_tool_approaches,
        "diode_to_unrelated_route_errors": diode_to_unrelated_route_errors,
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


def build_drc_evidence(
    board_paths: Sequence[Path] = DEFAULT_BOARDS,
) -> dict[str, object]:
    records: dict[str, object] = {}
    for board_path in board_paths:
        side = "left" if "left" in board_path.name.lower() else "right"
        report_path = board_path.with_suffix(".drc.json")
        project_path = board_path.with_suffix(".kicad_pro")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        records[side] = {
            "board_path": board_path.relative_to(ROOT).as_posix(),
            "board_sha256": sha256_file(board_path),
            "drc_report_path": report_path.relative_to(ROOT).as_posix(),
            "drc_report_sha256": sha256_file(report_path),
            "project_path": DEFAULT_BOARDS[0 if side == "left" else 1]
            .with_suffix(".kicad_pro")
            .relative_to(ROOT)
            .as_posix(),
            "project_sha256": sha256_file(project_path),
            "default_clearance_mm": project_default_clearance_mm(project_path),
            "schema": report.get("$schema"),
            "source": report.get("source"),
            "kicad_version": report.get("kicad_version"),
            "date": report.get("date"),
            "included_severities": report.get("included_severities"),
        }
    return {
        "requirement_ids": ["CON-ARCH-004", "CON-ARCH-006"],
        "variant": "x3-v2",
        "status": "draft_not_orderable_pending_physical_evidence",
        "hash_policy": HASH_POLICY,
        "boards": records,
    }


def verify_drc_evidence_binding(
    board_path: Path,
    side: str,
    evidence: dict[str, object],
) -> tuple[list[str], dict[str, object]]:
    errors: list[str] = []
    boards = evidence.get("boards")
    record = boards.get(side) if isinstance(boards, dict) else None
    if not isinstance(record, dict):
        return [f"{side}: DRC evidence record is missing"], {}
    if evidence.get("hash_policy") != HASH_POLICY:
        errors.append(f"{side}: DRC evidence canonical hash policy mismatch")

    report_path = board_path.with_suffix(".drc.json")
    project_path = board_path.with_suffix(".kicad_pro")
    if not board_path.is_file():
        return [f"{side}: DRC evidence board is missing"], record
    if not report_path.is_file():
        return [f"{side}: DRC evidence report is missing"], record
    if not project_path.is_file():
        return [f"{side}: KiCad project is missing"], record

    board_sha256 = sha256_file(board_path)
    report_sha256 = sha256_file(report_path)
    project_sha256 = sha256_file(project_path)
    if record.get("board_sha256") != board_sha256:
        errors.append(f"{side}: DRC evidence board SHA-256 mismatch")
    if record.get("drc_report_sha256") != report_sha256:
        errors.append(f"{side}: DRC evidence report SHA-256 mismatch")
    if record.get("project_sha256") != project_sha256:
        errors.append(f"{side}: DRC evidence project SHA-256 mismatch")

    expected_board_path = DEFAULT_BOARDS[0 if side == "left" else 1].relative_to(ROOT).as_posix()
    expected_report_path = DEFAULT_BOARDS[0 if side == "left" else 1].with_suffix(".drc.json").relative_to(ROOT).as_posix()
    expected_project_path = DEFAULT_BOARDS[0 if side == "left" else 1].with_suffix(".kicad_pro").relative_to(ROOT).as_posix()
    if record.get("board_path") != expected_board_path:
        errors.append(f"{side}: DRC evidence canonical board path mismatch")
    if record.get("drc_report_path") != expected_report_path:
        errors.append(f"{side}: DRC evidence canonical report path mismatch")
    if record.get("project_path") != expected_project_path:
        errors.append(f"{side}: DRC evidence canonical project path mismatch")
    try:
        default_clearance = project_default_clearance_mm(project_path)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        errors.append(f"{side}: KiCad project Default clearance cannot be parsed: {error}")
    else:
        if default_clearance < 0.30:
            errors.append(f"{side}: project Default clearance must be at least 0.30 mm")
        if record.get("default_clearance_mm") != default_clearance:
            errors.append(f"{side}: DRC evidence project Default clearance mismatch")

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"{side}: DRC evidence report cannot be parsed: {error}")
        return errors, record
    for field, report_field in (
        ("schema", "$schema"),
        ("source", "source"),
        ("kicad_version", "kicad_version"),
        ("date", "date"),
        ("included_severities", "included_severities"),
    ):
        if record.get(field) != report.get(report_field):
            errors.append(f"{side}: DRC evidence {field} mismatch")
    if report.get("$schema") != "https://schemas.kicad.org/drc.v1.json":
        errors.append(f"{side}: unsupported KiCad DRC schema")
    if report.get("source") != board_path.name:
        errors.append(f"{side}: DRC evidence source does not name the current board")
    kicad_version = report.get("kicad_version")
    if not isinstance(kicad_version, str) or KICAD_10_VERSION_RE.fullmatch(kicad_version) is None:
        errors.append(f"{side}: KiCad DRC version must be 10.x")
    report_date = report.get("date")
    valid_timestamp = isinstance(report_date, str) and ISO_TIMESTAMP_RE.fullmatch(report_date) is not None
    if valid_timestamp:
        try:
            datetime.fromisoformat(report_date.replace("Z", "+00:00"))
        except ValueError:
            valid_timestamp = False
    if not valid_timestamp:
        errors.append(f"{side}: KiCad DRC date is not a valid ISO timestamp")
    included_severities = report.get("included_severities")
    severity_set = set(included_severities) if isinstance(included_severities, list) else set()
    if (
        not isinstance(included_severities, list)
        or any(not isinstance(value, str) for value in included_severities)
        or len(severity_set) != len(included_severities)
        or not REQUIRED_DRC_SEVERITIES.issubset(severity_set)
    ):
        errors.append(f"{side}: KiCad DRC included_severities must contain error and warning")
    if severity_set - ALLOWED_DRC_SEVERITIES:
        errors.append(f"{side}: KiCad DRC included_severities contains an unsupported value")
    return errors, record


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
    drc_evidence_path: Path = DEFAULT_DRC_EVIDENCE,
    housing_manifest_path: Path = DEFAULT_HOUSING_MANIFEST,
) -> dict[str, object]:
    from tools.verify_kc2_antenna_keepout import check_board as check_antenna_keepout
    from tools.verify_kc2_compact_controller import check_side as check_compact_controller
    from tools.verify_kc2_connectivity import detect_side, verify_board as verify_connectivity

    errors = [f"footprint: {error}" for error in verify_v2_footprint(footprint_path)]
    manifest = analyze_v2_manifest(manifest_path)
    drc_evidence = analyze_v2_manifest(drc_evidence_path)
    housing_manifest = analyze_v2_manifest(housing_manifest_path)
    if drc_evidence.get("requirement_ids") != ["CON-ARCH-004", "CON-ARCH-006"]:
        errors.append("DRC evidence: requirement IDs are missing or stale")
    if drc_evidence.get("variant") != "x3-v2":
        errors.append("DRC evidence: variant is missing or stale")
    if manifest.get("variant") != "x3-v2":
        errors.append(f"manifest: unexpected variant {manifest.get('variant')!r}")
    if manifest.get("assembly_modes") != [
        "choc_v2_bottom_socket",
        "mx_5pin_top_direct_solder",
    ]:
        errors.append("manifest: assembly modes are incomplete or out of order")
    if not manifest.get("assembly_modes_mutually_exclusive"):
        errors.append("manifest: switch assembly modes must be mutually exclusive")
    if manifest.get("key_count") != {"left": 31, "right": 39, "total": 70}:
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
    if manifest.get("pcb_fastener_holes") != expected_m1_4_mount_manifest():
        errors.append("manifest: exact selected M1.4 MH pattern and service envelope are missing or stale")
    pcb_closed_bottom = (
        (manifest.get("pcb_fastener_holes") or {})
        .get("housing_interface_mm", {})
        .get("desk_column_closed_bottom")
    )
    housing_closed_bottom = (housing_manifest.get("parameters") or {}).get(
        "mounting_closed_bottom_mm"
    )
    if pcb_closed_bottom != housing_closed_bottom:
        errors.append("manifest: PCB/housing mounting closed-bottom contract mismatch")
    if manifest.get("x3_tact_battery_clearance_mm") is not None:
        errors.append("manifest: legacy X3 tact-to-battery scalar is forbidden for V2")
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
    if manifest.get("matrix_route_clearance_mm") != 0.30:
        errors.append("manifest: V2 matrix route clearance must be 0.30 mm")
    if diode_policy.get("minimum_fillet_to_unrelated_route_mm") != 0.10:
        errors.append("manifest: diode-to-unrelated-route clearance policy is missing")
    if diode_policy.get("minimum_edge_cuts_clearance_mm") != 1.3:
        errors.append("manifest: diode Edge.Cuts clearance policy is missing")
    if diode_policy.get("edge_safe_offsets_mm") != {
        "top_second_key": {"x": 7.0, "y": 7.0, "rotation_degrees": 90.0},
        "top_other_keys": {"x": -8.75, "y": -3.25, "rotation_degrees": 270.0},
        "bottom_first_key": {"x": 9.5, "y": 3.25},
    }:
        errors.append("manifest: verified edge-safe diode offsets are missing")

    route_evidence_errors, route_evidence_reports = verify_canonical_route_evidence(manifest)
    errors.extend(route_evidence_errors)

    board_reports: dict[str, object] = {}
    connectivity_errors: dict[str, list[str]] = {}
    drc_evidence_reports: dict[str, object] = {}
    for board_path in board_paths:
        side = detect_side(board_path)
        drc_binding_errors, drc_evidence_record = verify_drc_evidence_binding(
            board_path,
            side,
            drc_evidence,
        )
        errors.extend(drc_binding_errors)
        drc_evidence_reports[side] = drc_evidence_record
        expected_keys = 31 if side == "left" else 39
        report = analyze_v2_board(board_path)
        board_reports[side] = report
        checks = {
            "switch count": report["switch_count"] == expected_keys,
            "diode count": report["diode_count"] == expected_keys,
            "owned ES1B diode footprint": report["diode_footprint_names"]
            == {"D_ES1B_SMA_HandSolder_C437840"},
            "locked ES1B diode identity": report["diode_values"]
            == {"ES1B_Jingdao_C437840_Eleparts9475342"},
            "ES1B cathode/anode nets": not report["diode_pin_net_errors"],
            "placed ES1B owned geometry": not report["diode_footprint_geometry_errors"],
            "owned switch footprint": report["switch_footprint_names"]
            == {"SW_Choc_V2_Socket_MX_THT"},
            "placed switch owned geometry": not report["switch_footprint_geometry_errors"],
            "alternate contact nets": not report["alternate_contact_net_mismatches"],
            "switch placement matches generator": not report["switch_layout_errors"],
            "no stabilizers": not report["stabilizer_refs"],
            "no legacy key-field registration holes": report["registration_hole_count"] == 0,
            "registration hole safety": not report["registration_hole_errors"],
            "no legacy H-series mounting holes": not report["legacy_mount_hole_refs"],
            "exact copper-free M1.4 MH pattern": not report["mounting_hole_errors"],
            "visible numbered M1.4 MH front silkscreen": not report[
                "mounting_hole_silkscreen_errors"
            ],
            "M1.4 driver-to-copper clearance": not report[
                "mounting_hole_driver_copper_errors"
            ],
            "canonical final route item count": report["route_track_via_count"]
            == manifest["canonical_route_evidence"][side]["final_track_via_count"],
            "canonical final route digest": report["route_digest_sha256"]
            == manifest["canonical_route_evidence"][side]["route_digest_sha256"],
            "M1.4 retention board identity": (
                any(
                    "SELECTED M1.4 MH RETENTION" in text.upper()
                    for text in report["board_text"]
                )
                and not any(
                    "NO KEY-FIELD HOLES" in text.upper()
                    for text in report["board_text"]
                )
            ),
            "no carrier power pads": not report["carrier_power_pad_refs"],
            "one battery lead slot": report["battery_lead_slot_count"] == 1,
            "copper-free battery lead slot": not report["battery_lead_slot_errors"],
            "battery slot on USB/B+ side": report["battery_lead_slot_on_usb_side"],
            "no carrier power nets": not report["forbidden_carrier_power_nets"],
            "side-specific controller footprint and USB label": not report["controller_contract_errors"],
            "reset pad contract": not report["reset_contract_errors"],
            "diode hand-solder clearance": not report["diode_hand_solder_clearance_errors"],
            "diode unrelated-route clearance": not report["diode_to_unrelated_route_errors"],
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
        "drc_evidence": drc_evidence_reports,
        "canonical_route_evidence": route_evidence_reports,
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
    parser.add_argument("--drc-evidence", type=Path, default=DEFAULT_DRC_EVIDENCE)
    parser.add_argument("--housing-manifest", type=Path, default=DEFAULT_HOUSING_MANIFEST)
    args = parser.parse_args()
    report = verify_v2_release_candidate(
        args.footprint,
        args.boards,
        args.manifest,
        args.drc_evidence,
        args.housing_manifest,
    )
    errors = report["errors"]
    if errors:
        raise SystemExit("FAIL: KC2 X3 V2 routed draft verification\n- " + "\n- ".join(errors))
    print(json.dumps(report, indent=2, default=list))
    print("PASS: CON-ARCH-004 routed boards, connectivity, controller, and antenna checks")


if __name__ == "__main__":
    main()
