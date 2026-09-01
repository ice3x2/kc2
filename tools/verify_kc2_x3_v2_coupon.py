from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path
import re

import pcbnew

from tools.canonical_hash import HASH_POLICY, sha256_file
from tools.verify_kc2_x3_v2 import (
    board_outline_segments_mm,
    bounding_box_clearance_mm,
    bounding_box_mm,
    inflate_box_mm,
    segment_to_box_clearance_mm,
)


ROOT = Path(__file__).resolve().parents[1]
COUPON_DIR = ROOT / "hardware" / "kicad" / "draft" / "x3-v2" / "coupon"
DEFAULT_BOARD = COUPON_DIR / "kc2_x3_v2_switch_coupon.kicad_pcb"
DEFAULT_MANIFEST = COUPON_DIR / "kc2_x3_v2_switch_coupon_manifest.json"
DEFAULT_DRC_REPORT = COUPON_DIR / "kc2_x3_v2_switch_coupon.drc.json"
DEFAULT_DRC_EVIDENCE = COUPON_DIR / "kc2_x3_v2_switch_coupon_drc_evidence.json"
CANONICAL_BOARD_PATH = DEFAULT_BOARD.relative_to(ROOT).as_posix()
CANONICAL_DRC_REPORT_PATH = DEFAULT_DRC_REPORT.relative_to(ROOT).as_posix()
EXACT_DRC_SEVERITIES = ["error", "warning", "exclusion"]
REVIEWED_IGNORED_DRC_CHECKS = [
    "footprint_filters_mismatch",
    "footprint_type_mismatch",
    "missing_courtyard",
    "track_not_centered_on_via",
    "tuning_profile_track_geometries",
]
REVIEWED_IGNORED_DRC_RATIONALE = {
    "footprint_filters_mismatch": "No schematic footprint-filter source is committed for this PCB-only coupon.",
    "footprint_type_mismatch": "Intentional hybrid plated and SMD switch contacts share one PCB-only footprint.",
    "missing_courtyard": "Board-only service-probe and text helpers without courtyard are visually reviewed.",
    "track_not_centered_on_via": "Reviewed coupon probe routes intentionally enter vias off-center.",
    "tuning_profile_track_geometries": "No impedance or length-tuning profiles are used by the coupon.",
}
KICAD_10_VERSION_RE = re.compile(r"^10(?:\.\d+)+(?:[-+][0-9A-Za-z.-]+)?$")
ISO_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$"
)
EXPECTED_DIODE_FOOTPRINT = "D_1N4148W_SOD123_HandSolder_DiodesInc"
EXPECTED_DIODE_VALUE = "1N4148W-13-F_DiodesInc_SOD123"


def mm(value: int) -> float:
    return pcbnew.ToMM(value)


def footprint_distance_mm(left: pcbnew.FOOTPRINT, right: pcbnew.FOOTPRINT) -> float:
    left_position = left.GetPosition()
    right_position = right.GetPosition()
    return math.hypot(
        mm(left_position.x - right_position.x),
        mm(left_position.y - right_position.y),
    )


def ignored_drc_check_keys(drc: dict[str, object]) -> list[str]:
    ignored_checks = drc.get("ignored_checks")
    if not isinstance(ignored_checks, list):
        return []
    return sorted(
        item.get("key")
        for item in ignored_checks
        if isinstance(item, dict) and isinstance(item.get("key"), str)
    )


def build_coupon_drc_evidence(
    board_path: Path = DEFAULT_BOARD,
    drc_report_path: Path = DEFAULT_DRC_REPORT,
) -> dict[str, object]:
    drc = json.loads(drc_report_path.read_text(encoding="utf-8"))
    return {
        "requirement_ids": ["CON-ARCH-004"],
        "variant": "x3-v2-switch-coupon",
        "status": "draft_not_orderable_pending_physical_evidence",
        "hash_policy": HASH_POLICY,
        "board": {
            "board_path": CANONICAL_BOARD_PATH,
            "board_sha256": sha256_file(board_path),
            "drc_report_path": CANONICAL_DRC_REPORT_PATH,
            "drc_report_sha256": sha256_file(drc_report_path),
            "schema": drc.get("$schema"),
            "source": drc.get("source"),
            "kicad_version": drc.get("kicad_version"),
            "date": drc.get("date"),
            "included_severities": drc.get("included_severities"),
            "ignored_checks": ignored_drc_check_keys(drc),
            "ignored_check_rationale": REVIEWED_IGNORED_DRC_RATIONALE,
        },
    }


def verify_coupon_drc_evidence(
    board_path: Path,
    drc_report_path: Path,
    evidence_path: Path,
) -> tuple[list[str], dict[str, object]]:
    errors: list[str] = []
    if not evidence_path.is_file():
        return ["missing coupon DRC evidence sidecar"], {}
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"coupon DRC evidence sidecar cannot be parsed: {error}"], {}
    record = evidence.get("board")
    if not isinstance(record, dict):
        return ["coupon DRC evidence board record is missing"], {}
    if evidence.get("requirement_ids") != ["CON-ARCH-004"]:
        errors.append("coupon DRC evidence requirement IDs differ")
    if evidence.get("variant") != "x3-v2-switch-coupon":
        errors.append("coupon DRC evidence variant differs")
    if evidence.get("status") != "draft_not_orderable_pending_physical_evidence":
        errors.append("coupon DRC evidence must remain draft and not order-ready")
    if evidence.get("hash_policy") != HASH_POLICY:
        errors.append("coupon DRC evidence canonical hash policy mismatch")
    if record.get("board_path") != CANONICAL_BOARD_PATH:
        errors.append("coupon DRC evidence canonical board path mismatch")
    if record.get("drc_report_path") != CANONICAL_DRC_REPORT_PATH:
        errors.append("coupon DRC evidence canonical report path mismatch")
    if not board_path.is_file():
        errors.append("coupon DRC evidence board is missing")
    elif record.get("board_sha256") != sha256_file(board_path):
        errors.append("coupon DRC evidence board SHA-256 mismatch")
    if not drc_report_path.is_file():
        errors.append("coupon DRC evidence report is missing")
        return errors, record
    if record.get("drc_report_sha256") != sha256_file(drc_report_path):
        errors.append("coupon DRC evidence report SHA-256 mismatch")
    try:
        drc = json.loads(drc_report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"coupon DRC report cannot be parsed: {error}")
        return errors, record
    for evidence_field, report_field in (
        ("schema", "$schema"),
        ("source", "source"),
        ("kicad_version", "kicad_version"),
        ("date", "date"),
        ("included_severities", "included_severities"),
    ):
        if record.get(evidence_field) != drc.get(report_field):
            errors.append(f"coupon DRC evidence {evidence_field} mismatch")
    report_ignored_checks = ignored_drc_check_keys(drc)
    if record.get("ignored_checks") != report_ignored_checks:
        errors.append("coupon DRC evidence ignored_checks mismatch")
    if drc.get("$schema") != "https://schemas.kicad.org/drc.v1.json":
        errors.append("coupon DRC schema differs")
    if drc.get("source") != DEFAULT_BOARD.name:
        errors.append("coupon DRC source does not name the canonical board")
    kicad_version = drc.get("kicad_version")
    if not isinstance(kicad_version, str) or KICAD_10_VERSION_RE.fullmatch(kicad_version) is None:
        errors.append("coupon DRC KiCad version must be 10.x")
    report_date = drc.get("date")
    valid_timestamp = isinstance(report_date, str) and ISO_TIMESTAMP_RE.fullmatch(report_date) is not None
    if valid_timestamp:
        try:
            dt.datetime.fromisoformat(report_date.replace("Z", "+00:00"))
        except ValueError:
            valid_timestamp = False
    if not valid_timestamp:
        errors.append("coupon DRC date must be a valid ISO timestamp")
    if drc.get("included_severities") != EXACT_DRC_SEVERITIES:
        errors.append("coupon DRC included_severities must exactly cover error, warning, exclusion")
    raw_ignored_checks = drc.get("ignored_checks")
    valid_ignored_shape = (
        isinstance(raw_ignored_checks, list)
        and all(
            isinstance(item, dict) and isinstance(item.get("key"), str)
            for item in raw_ignored_checks
        )
        and len(report_ignored_checks) == len(raw_ignored_checks)
    )
    if not valid_ignored_shape or report_ignored_checks != REVIEWED_IGNORED_DRC_CHECKS:
        errors.append("coupon DRC ignored_checks differ from the reviewed allowlist")
    if record.get("ignored_checks") != REVIEWED_IGNORED_DRC_CHECKS:
        errors.append("coupon DRC evidence ignored_checks differ from the reviewed allowlist")
    if record.get("ignored_check_rationale") != REVIEWED_IGNORED_DRC_RATIONALE:
        errors.append("coupon DRC evidence ignored-check rationale differs from the reviewed contract")
    return errors, record


def analyze_coupon(
    path: Path = DEFAULT_BOARD,
    manifest_path: Path | None = None,
    drc_evidence_path: Path | None = None,
) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(path)
    board = pcbnew.LoadBoard(str(path))
    switches = sorted(
        (fp for fp in board.GetFootprints() if fp.GetReference().startswith("SW_")),
        key=lambda fp: fp.GetReference(),
    )
    diodes = sorted(
        (fp for fp in board.GetFootprints() if fp.GetReference().startswith("D_")),
        key=lambda fp: fp.GetReference(),
    )
    probes = sorted(
        (fp for fp in board.GetFootprints() if fp.GetReference().startswith("TP_")),
        key=lambda fp: fp.GetReference(),
    )
    mismatches: list[str] = []
    for switch in switches:
        for number in ("1", "2"):
            pads = [pad for pad in switch.Pads() if pad.GetNumber() == number]
            nets = {pad.GetNetname() for pad in pads}
            if len(pads) != 2 or len(nets) != 1 or "" in nets:
                mismatches.append(
                    f"{switch.GetReference()} pad {number}: count={len(pads)} nets={sorted(nets)}"
                )
    diode_value_errors: list[str] = []
    diode_layer_errors: list[str] = []
    diode_pad_geometry_errors: list[str] = []
    diode_pin_net_errors: list[str] = []
    diode_clearance_errors: list[str] = []
    polarity_mark_errors: list[str] = []
    probe_pad_errors: list[str] = []
    probe_net_errors: list[str] = []
    diode_body_geometry_errors: list[str] = []
    diode_tool_approach_errors: list[str] = []
    diode_tool_approach_directions: dict[str, dict[str, str]] = {}
    edge_clearances: list[float] = []
    switch_clearances: list[float] = []
    npth_clearances: list[float] = []

    outline_segments = board_outline_segments_mm(board)
    switch_pads = [pad for switch in switches for pad in switch.Pads() if pad.GetNumber()]
    switch_npth = [
        pad
        for switch in switches
        for pad in switch.Pads()
        if pad.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH
    ]
    bottom_marks = [
        drawing
        for drawing in board.GetDrawings()
        if isinstance(drawing, pcbnew.PCB_TEXT)
        and drawing.GetLayer() == pcbnew.B_SilkS
        and drawing.IsMirrored()
    ]
    all_diode_fillet_boxes = {
        diode.GetReference(): [inflate_box_mm(bounding_box_mm(pad), 0.30) for pad in diode.Pads()]
        for diode in diodes
    }
    for diode in diodes:
        reference = diode.GetReference()
        sample = reference.removeprefix("D_")
        if diode.GetValue() != EXPECTED_DIODE_VALUE:
            diode_value_errors.append(f"{reference}: value={diode.GetValue()!r}")
        if diode.GetLayer() != pcbnew.B_Cu:
            diode_layer_errors.append(f"{reference}: layer={diode.GetLayerName()}")
        pads = sorted(diode.Pads(), key=lambda pad: pad.GetNumber())
        if [pad.GetNumber() for pad in pads] != ["1", "2"]:
            diode_pad_geometry_errors.append(f"{reference}: pad numbers")
            continue
        sizes = [(round(mm(pad.GetSize().x), 3), round(mm(pad.GetSize().y), 3)) for pad in pads]
        center_pitch = math.hypot(
            mm(pads[1].GetPosition().x - pads[0].GetPosition().x),
            mm(pads[1].GetPosition().y - pads[0].GetPosition().y),
        )
        inner_gap = bounding_box_clearance_mm(
            bounding_box_mm(pads[0]), bounding_box_mm(pads[1])
        )
        if sizes != [(1.4, 1.55), (1.4, 1.55)] or abs(center_pitch - 3.6) > 0.001 or abs(inner_gap - 2.2) > 0.001:
            diode_pad_geometry_errors.append(
                f"{reference}: sizes={sizes} pitch={center_pitch:.3f} gap={inner_gap:.3f}"
            )
        expected_nets = {"1": f"D_{sample}_ROW", "2": f"D_{sample}_ANODE"}
        actual_nets = {pad.GetNumber(): pad.GetNetname() for pad in pads}
        if actual_nets != expected_nets:
            diode_pin_net_errors.append(
                f"{reference}: expected={expected_nets} actual={actual_nets}"
            )

        body_boxes = [
            bounding_box_mm(item)
            for item in diode.GraphicalItems()
            if isinstance(item, pcbnew.PCB_SHAPE) and item.GetLayer() == pcbnew.B_Fab
        ]
        courtyard_boxes = [
            bounding_box_mm(item)
            for item in diode.GraphicalItems()
            if isinstance(item, pcbnew.PCB_SHAPE) and item.GetLayer() == pcbnew.B_CrtYd
        ]
        body_bounds = (
            min(box[0] for box in body_boxes), min(box[1] for box in body_boxes),
            max(box[2] for box in body_boxes), max(box[3] for box in body_boxes),
        )
        courtyard_bounds = (
            min(box[0] for box in courtyard_boxes), min(box[1] for box in courtyard_boxes),
            max(box[2] for box in courtyard_boxes), max(box[3] for box in courtyard_boxes),
        )
        body_size = sorted((round(body_bounds[2] - body_bounds[0], 3), round(body_bounds[3] - body_bounds[1], 3)))
        courtyard_size = sorted((round(courtyard_bounds[2] - courtyard_bounds[0], 3), round(courtyard_bounds[3] - courtyard_bounds[1], 3)))
        # KiCad bounding boxes include graphic stroke width and the cathode marker.
        # The underlying Fab rectangle endpoints are the official 2.85 x 1.70 mm body.
        if body_size != [1.8, 2.95] or courtyard_size != [2.35, 5.55]:
            diode_body_geometry_errors.append(
                f"{reference}: body={body_size} courtyard={courtyard_size}"
            )

        fillet_boxes = all_diode_fillet_boxes[reference]
        edge_clearance = min(
            segment_to_box_clearance_mm(start, end, box)
            for box in fillet_boxes
            for start, end in outline_segments
        )
        switch_clearance = min(
            bounding_box_clearance_mm(box, bounding_box_mm(pad))
            for box in fillet_boxes
            for pad in switch_pads
        )
        npth_clearance = min(
            bounding_box_clearance_mm(box, bounding_box_mm(pad))
            for box in fillet_boxes
            for pad in switch_npth
        )
        other_diode_clearance = min(
            (
                bounding_box_clearance_mm(box, other_box)
                for other_reference, other_boxes in all_diode_fillet_boxes.items()
                if other_reference != reference
                for box in fillet_boxes
                for other_box in other_boxes
            ),
            default=math.inf,
        )
        edge_clearances.append(edge_clearance)
        switch_clearances.append(switch_clearance)
        npth_clearances.append(npth_clearance)
        if edge_clearance < 1.30 - 1e-6:
            diode_clearance_errors.append(f"{reference}: edge={edge_clearance:.3f}")
        if switch_clearance < 1.00 - 1e-6:
            diode_clearance_errors.append(f"{reference}: switch={switch_clearance:.3f}")
        if npth_clearance < 1.00 - 1e-6:
            diode_clearance_errors.append(f"{reference}: npth={npth_clearance:.3f}")
        if other_diode_clearance <= 0.0:
            diode_clearance_errors.append(f"{reference}: overlaps another diode")

        assembly_obstacles = [
            inflate_box_mm(bounding_box_mm(pad), 0.30) for pad in switch_pads
        ] + [bounding_box_mm(pad) for pad in switch_npth] + [
            box
            for other_reference, boxes in all_diode_fillet_boxes.items()
            if other_reference != reference
            for box in boxes
        ]
        directions: dict[str, str] = {}
        for pad in pads:
            box = bounding_box_mm(pad)
            corridors = {
                "north": (box[0] - 0.40, box[1] - 1.50, box[2] + 0.40, box[1]),
                "south": (box[0] - 0.40, box[3], box[2] + 0.40, box[3] + 1.50),
                "west": (box[0] - 1.50, box[1] - 0.40, box[0], box[3] + 0.40),
                "east": (box[2], box[1] - 0.40, box[2] + 1.50, box[3] + 0.40),
            }
            open_directions = [
                name
                for name, corridor in corridors.items()
                if all(bounding_box_clearance_mm(corridor, obstacle) >= 0.0 for obstacle in assembly_obstacles)
            ]
            if not open_directions:
                diode_tool_approach_errors.append(
                    f"{reference} pad {pad.GetNumber()}: no open 1.50 mm cardinal approach"
                )
            else:
                directions[pad.GetNumber()] = open_directions[0]
        diode_tool_approach_directions[reference] = directions

        marks = [mark.GetText() for mark in bottom_marks]
        if f"{reference} K/P1 ROW" not in marks:
            polarity_mark_errors.append(f"{reference}: missing mirrored K/P1 ROW mark")
        if f"{reference} A/P2 SWITCH" not in marks:
            polarity_mark_errors.append(f"{reference}: missing mirrored A/P2 SWITCH mark")

    for probe in probes:
        pads = list(probe.Pads())
        if len(pads) != 1:
            probe_pad_errors.append(f"{probe.GetReference()}: pad count={len(pads)}")
            continue
        pad = pads[0]
        size = (round(mm(pad.GetSize().x), 3), round(mm(pad.GetSize().y), 3))
        drill = round(mm(pad.GetDrillSize().x), 3)
        if pad.GetAttribute() != pcbnew.PAD_ATTRIB_PTH or size != (3.0, 3.0) or drill != 2.0:
            probe_pad_errors.append(
                f"{probe.GetReference()}: attr={pad.GetAttribute()} size={size} drill={drill}"
            )
        suffix = probe.GetReference().removeprefix("TP_")
        sample, role = suffix.rsplit("_", 1)
        expected_net = f"D_{sample}_{role}"
        if pad.GetNetname() != expected_net:
            probe_net_errors.append(
                f"{probe.GetReference()}: expected={expected_net} actual={pad.GetNetname()}"
            )
    bounds = board.GetBoardEdgesBoundingBox()
    drc_path = path.with_suffix(".drc.json")
    drc = json.loads(drc_path.read_text(encoding="utf-8")) if drc_path.is_file() else {}
    if manifest_path is None:
        manifest_path = path.with_name("kc2_x3_v2_switch_coupon_manifest.json")
    if drc_evidence_path is None:
        drc_evidence_path = path.with_name(DEFAULT_DRC_EVIDENCE.name)
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.is_file()
        else {}
    )
    drc_evidence_errors, drc_evidence = verify_coupon_drc_evidence(
        path, drc_path, drc_evidence_path
    )
    if not drc:
        drc_evidence_errors.append("missing KiCad DRC JSON")
    else:
        if drc.get("$schema") != "https://schemas.kicad.org/drc.v1.json":
            drc_evidence_errors.append(f"DRC schema={drc.get('$schema')!r}")
        if drc.get("source") != path.name:
            drc_evidence_errors.append(f"DRC source={drc.get('source')!r}")
        if not str(drc.get("kicad_version", "")).startswith("10."):
            drc_evidence_errors.append(f"DRC KiCad version={drc.get('kicad_version')!r}")
        if not {"error", "warning"}.issubset(set(drc.get("included_severities", []))):
            drc_evidence_errors.append(
                f"DRC included severities={drc.get('included_severities')!r}"
            )
        try:
            dt.datetime.fromisoformat(str(drc.get("date")))
        except ValueError:
            drc_evidence_errors.append(f"DRC date={drc.get('date')!r}")
    manifest_errors: list[str] = []
    expected_part = {
        "manufacturer": "Diodes Incorporated",
        "mpn": "1N4148W-13-F",
        "lcsc": "C112342",
        "jlcpcb_part_number": "C112342",
        "eleparts_goods_no": "3417687",
        "footprint": "kc2.pretty:D_1N4148W_SOD123_HandSolder_DiodesInc",
        "assembly_side": "bottom",
        "pin_1": "cathode_row",
        "pin_2": "anode_switch",
        "official_suggested_land_mm": {
            "pad_size": [0.9, 0.95], "center_span": 4.05,
        },
        "implemented_hand_solder_land_mm": {
            "classification": "kc2_controlled_not_manufacturer_recommended",
            "pad_size": [1.4, 1.55], "center_span": 3.6,
            "inner_gap": 2.2, "outer_span": 5.0,
        },
    }
    if manifest.get("matrix_diode") != expected_part:
        manifest_errors.append("manifest exact 1N4148W identity/land/polarity differs")
    expected_probes = {
        "per_sample": ["COL", "ANODE", "ROW"],
        "footprint": "TestPoint:TestPoint_Plated_Hole_D2.0mm",
        "drill_mm": 2.0,
        "copper_diameter_mm": 3.0,
    }
    if manifest.get("service_probes") != expected_probes:
        manifest_errors.append("manifest service-probe contract differs")
    board_text_items = [
        drawing
        for drawing in board.GetDrawings()
        if isinstance(drawing, pcbnew.PCB_TEXT)
    ]
    board_text = "\n".join(drawing.GetText() for drawing in board_text_items)
    critical_mode_labels = (
        "CHOC LEFT",
        "CHOC RIGHT BOARD",
        "CHOC V1 UNSUPPORTED",
        "DO NOT POPULATE BOTH MODES",
        "MX 5PIN",
    )
    critical_mode_label_layers: dict[str, str] = {}
    critical_mode_label_errors: list[str] = []
    for label in critical_mode_labels:
        matches = [drawing for drawing in board_text_items if drawing.GetText() == label]
        if len(matches) != 1:
            critical_mode_label_errors.append(f"{label}: text count={len(matches)}")
            continue
        layer_name = board.GetLayerName(matches[0].GetLayer())
        critical_mode_label_layers[label] = layer_name
        if matches[0].GetLayer() != pcbnew.F_SilkS:
            critical_mode_label_errors.append(
                f"{label}: layer={layer_name!r}, expected='F.Silkscreen'"
            )
    return {
        "switch_refs": [switch.GetReference() for switch in switches],
        "switch_footprint_names": {
            str(switch.GetFPID().GetLibItemName()) for switch in switches
        },
        "switch_orientations_deg": {
            switch.GetReference(): round(float(switch.GetOrientation().AsDegrees()), 1)
            for switch in switches
        },
        "diode_count": len(diodes),
        "diode_refs": [diode.GetReference() for diode in diodes],
        "diode_footprint_names": {
            str(diode.GetFPID().GetLibItemName()) for diode in diodes
        },
        "diode_value_errors": diode_value_errors,
        "diode_layer_errors": diode_layer_errors,
        "diode_pad_geometry_errors": diode_pad_geometry_errors,
        "diode_pin_net_errors": diode_pin_net_errors,
        "diode_clearance_errors": diode_clearance_errors,
        "diode_body_geometry_errors": diode_body_geometry_errors,
        "diode_tool_approach_errors": diode_tool_approach_errors,
        "diode_tool_approach_directions": diode_tool_approach_directions,
        "minimum_diode_edge_clearance_mm": round(min(edge_clearances), 3),
        "minimum_diode_switch_pad_clearance_mm": round(min(switch_clearances), 3),
        "minimum_diode_npth_clearance_mm": round(min(npth_clearances), 3),
        "polarity_mark_errors": polarity_mark_errors,
        "probe_refs": [probe.GetReference() for probe in probes],
        "probe_pad_errors": probe_pad_errors,
        "probe_net_errors": probe_net_errors,
        "alternate_contact_net_mismatches": mismatches,
        "drc_violation_count": len(drc.get("violations", [])),
        "drc_unconnected_count": len(drc.get("unconnected_items", [])),
        "drc_evidence_errors": drc_evidence_errors,
        "drc_evidence": drc_evidence,
        "default_netclass_clearance_mm": round(
            mm(board.GetAllNetClasses()["Default"].GetClearance()), 3
        ),
        "board_size_mm": [
            round(pcbnew.ToMM(bounds.GetWidth()), 3),
            round(pcbnew.ToMM(bounds.GetHeight()), 3),
        ],
        "board_text": board_text,
        "critical_mode_label_layers": critical_mode_label_layers,
        "critical_mode_label_errors": critical_mode_label_errors,
        "order_ready": manifest.get("order_ready"),
        "physical_evidence_status": manifest.get("physical_evidence_status"),
        "coverage_limitations": manifest.get("coverage_limitations", {}),
        "planned_measurements": manifest.get("planned_measurements", []),
        "manifest_errors": manifest_errors,
    }


def coupon_errors(report: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if report["switch_refs"] != ["SW_L", "SW_MX", "SW_R"]:
        errors.append(f"switch samples: {report['switch_refs']}")
    if report["switch_footprint_names"] != {"SW_Choc_V2_Socket_MX_THT"}:
        errors.append(f"switch footprints: {report['switch_footprint_names']}")
    expected_orientations = {"SW_L": 0.0, "SW_MX": 0.0, "SW_R": 180.0}
    if report["switch_orientations_deg"] != expected_orientations:
        errors.append(
            "switch orientations: "
            f"expected={expected_orientations} actual={report['switch_orientations_deg']}"
        )
    if report["diode_refs"] != ["D_L", "D_MX", "D_R"]:
        errors.append(f"diode samples: {report['diode_refs']}")
    if report["diode_footprint_names"] != {EXPECTED_DIODE_FOOTPRINT}:
        errors.append(f"diode footprints: {report['diode_footprint_names']}")
    for field in (
        "alternate_contact_net_mismatches",
        "diode_value_errors",
        "diode_layer_errors",
        "diode_pad_geometry_errors",
        "diode_pin_net_errors",
        "diode_clearance_errors",
        "diode_body_geometry_errors",
        "diode_tool_approach_errors",
        "polarity_mark_errors",
        "probe_pad_errors",
        "probe_net_errors",
        "drc_evidence_errors",
        "critical_mode_label_errors",
        "manifest_errors",
    ):
        errors.extend(report[field])
    expected_probe_refs = [
        "TP_L_ANODE", "TP_L_COL", "TP_L_ROW",
        "TP_MX_ANODE", "TP_MX_COL", "TP_MX_ROW",
        "TP_R_ANODE", "TP_R_COL", "TP_R_ROW",
    ]
    if report["probe_refs"] != expected_probe_refs:
        errors.append(f"service probes: {report['probe_refs']}")
    if report["drc_violation_count"] or report["drc_unconnected_count"]:
        errors.append(
            f"DRC violations={report['drc_violation_count']} unconnected={report['drc_unconnected_count']}"
        )
    if report["default_netclass_clearance_mm"] < 0.30:
        errors.append(
            f"coupon default netclass clearance={report['default_netclass_clearance_mm']} mm"
        )
    if report["order_ready"] is not False:
        errors.append("coupon manifest must remain not order-ready")
    if report["physical_evidence_status"] != "pending_fabrication_population_and_measurement":
        errors.append(f"physical evidence status: {report['physical_evidence_status']}")
    if "non_1u" not in report["coverage_limitations"]:
        errors.append("non-1U coverage limitation is missing")
    if "maximum same-row/same-column" not in report["coverage_limitations"].get("scan_stress", ""):
        errors.append("representative-only scan-stress limitation is missing")
    if set(report["planned_measurements"]) != {
        "low_current_vf",
        "row_high_3v0_3v3",
        "zero_wait_scan",
    }:
        errors.append(f"planned measurements: {report['planned_measurements']}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the CON-ARCH-004 physical fit coupon design.")
    parser.add_argument("board", nargs="?", type=Path, default=DEFAULT_BOARD)
    args = parser.parse_args()
    report = analyze_coupon(args.board)
    errors = coupon_errors(report)
    if errors:
        raise SystemExit("FAIL: KC2 X3 V2 coupon\n- " + "\n- ".join(errors))
    print(json.dumps(report, indent=2, default=list))
    print(
        "PASS: CON-ARCH-004 coupon CAD is structurally complete; "
        "fabrication/population evidence remains pending"
    )


if __name__ == "__main__":
    main()
