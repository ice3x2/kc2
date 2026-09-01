from __future__ import annotations

import json
import math
from pathlib import Path

import pcbnew

from tools import generate_kc2_pcbs as gen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "hardware" / "kicad" / "draft" / "x3-v2" / "coupon"
PROJECT_NAME = "kc2_x3_v2_switch_coupon"
BOARD_PATH = OUTPUT_DIR / f"{PROJECT_NAME}.kicad_pcb"
MANIFEST_PATH = OUTPUT_DIR / f"{PROJECT_NAME}_manifest.json"
TEST_POINT_LIB = gen.KICAD_SHARE / "footprints" / "TestPoint.pretty"
TEST_POINT_FP = "TestPoint_Plated_Hole_D2.0mm"
TEST_POINT_VALUE = "2.0mm_PTH_SERVICE_PROBE"
DIODE_OFFSET_MM = 8.6


def transform(point: tuple[float, float], center: tuple[float, float], angle_deg: float) -> tuple[float, float]:
    radians = math.radians(angle_deg)
    x, y = point
    return (
        center[0] + x * math.cos(radians) - y * math.sin(radians),
        center[1] + x * math.sin(radians) + y * math.cos(radians),
    )


def route_local_path(
    board: pcbnew.BOARD,
    net: pcbnew.NETINFO_ITEM,
    center: tuple[float, float],
    angle_deg: float,
    points: tuple[tuple[float, float], ...],
) -> None:
    absolute = [transform(point, center, angle_deg) for point in points]
    for start, end in zip(absolute, absolute[1:]):
        gen.add_track(board, net, start, end, pcbnew.B_Cu)


def pad_position(footprint: pcbnew.FOOTPRINT, number: str) -> tuple[float, float]:
    pad = next(pad for pad in footprint.Pads() if pad.GetNumber() == number)
    position = pad.GetPosition()
    return pcbnew.ToMM(position.x), pcbnew.ToMM(position.y)


def add_service_probe(
    board: pcbnew.BOARD,
    reference: str,
    center: tuple[float, float],
    net: pcbnew.NETINFO_ITEM,
) -> pcbnew.FOOTPRINT:
    probe = gen.load_footprint(
        board,
        TEST_POINT_LIB,
        TEST_POINT_FP,
        reference,
        TEST_POINT_VALUE,
        center[0],
        center[1],
        0.0,
    )
    next(iter(probe.Pads())).SetNet(net)
    probe.Reference().SetVisible(False)
    return probe


def add_coupon_switch(
    board: pcbnew.BOARD,
    nets: dict[str, pcbnew.NETINFO_ITEM],
    reference: str,
    diode_reference: str,
    center: tuple[float, float],
    rotation: float,
    diode_offset_y: float,
) -> None:
    switch = gen.load_footprint(
        board,
        gen.KC2_FP_LIB,
        gen.X3_V2_SWITCH_FP,
        reference,
        "CHOC_V2_SOCKET_OR_MX_5PIN_THT",
        center[0],
        center[1],
        rotation,
    )
    sample = reference.removeprefix("SW_")
    column = gen.add_net(board, nets, f"D_{sample}_COL")
    anode = gen.add_net(board, nets, f"D_{sample}_ANODE")
    row = gen.add_net(board, nets, f"D_{sample}_ROW")
    gen.set_pad_net(switch, "1", column)
    gen.set_pad_net(switch, "2", anode)
    route_local_path(
        board,
        column,
        center,
        rotation,
        ((2.54, -5.08), (3.3, -6.5), (6.5, -6.5), (6.5, 5.9), (3.7, 5.9)),
    )
    route_local_path(
        board,
        anode,
        center,
        rotation,
        ((-3.81, -2.54), (-7.0, -2.54), (-7.0, 3.8), (-8.7, 3.8)),
    )

    diode = gen.load_footprint(
        board,
        gen.X3_V2_DIODE_LIB,
        gen.X3_V2_DIODE_FP,
        diode_reference,
        gen.X3_V2_DIODE_VALUE,
        center[0],
        center[1] + diode_offset_y,
        rotation,
        bottom=True,
    )
    diode.Reference().SetLayer(pcbnew.B_Fab)
    gen.set_pad_net(diode, "1", row)
    gen.set_pad_net(diode, "2", anode)

    diode_pad_1 = pad_position(diode, "1")
    diode_pad_2 = pad_position(diode, "2")
    outside_y = 14.0 if diode_offset_y < 0 else 66.0
    column_y = 66.0 if diode_offset_y < 0 else 14.0
    row_probe = (diode_pad_1[0], outside_y)
    anode_probe = (diode_pad_2[0], outside_y)
    column_probe = (center[0], column_y)
    add_service_probe(board, f"TP_{sample}_ROW", row_probe, row)
    add_service_probe(board, f"TP_{sample}_ANODE", anode_probe, anode)
    add_service_probe(board, f"TP_{sample}_COL", column_probe, column)

    gen.add_track(board, row, diode_pad_1, row_probe, pcbnew.B_Cu)
    gen.add_track(board, anode, diode_pad_2, anode_probe, pcbnew.B_Cu)
    switch_pad_1_anchor = transform((3.7, 5.9), center, rotation)
    gen.add_track(board, column, switch_pad_1_anchor, column_probe, pcbnew.B_Cu)
    switch_pad_2_anchor = transform((-3.81, -2.54), center, rotation)
    approach_y = center[1] + diode_offset_y - math.copysign(3.0, diode_offset_y)
    gen.add_track(board, anode, switch_pad_2_anchor, (switch_pad_2_anchor[0], approach_y), pcbnew.B_Cu)
    gen.add_track(board, anode, (switch_pad_2_anchor[0], approach_y), (diode_pad_2[0], approach_y), pcbnew.B_Cu)
    gen.add_track(board, anode, (diode_pad_2[0], approach_y), diode_pad_2, pcbnew.B_Cu)

    mark_y = center[1] + diode_offset_y + (-2.5 if diode_offset_y < 0 else 2.5)
    label_y = center[1] + diode_offset_y + (-4.0 if diode_offset_y < 0 else 4.0)
    gen.add_board_text(
        board,
        f"{diode_reference} K/P1 ROW",
        center[0],
        mark_y,
        pcbnew.B_SilkS,
        0.8,
        0.12,
        mirrored=True,
    )
    gen.add_board_text(
        board,
        f"{diode_reference} A/P2 SWITCH",
        center[0],
        label_y,
        pcbnew.B_SilkS,
        0.8,
        0.12,
        mirrored=True,
    )
    probe_label_y = outside_y + (3.0 if outside_y < center[1] else -3.0)
    for label, point in (("K", row_probe), ("A", anode_probe)):
        gen.add_board_text(board, f"{sample}-{label}", point[0], probe_label_y, pcbnew.F_SilkS, 0.8, 0.12)
    column_label_y = column_y + (3.0 if column_y < center[1] else -3.0)
    gen.add_board_text(board, f"{sample}-COL", column_probe[0], column_label_y, pcbnew.F_SilkS, 0.8, 0.12)


def generate_coupon() -> dict[str, object]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(2)
    title = board.GetTitleBlock()
    title.SetTitle("KC2 X3 V2 1N4148W switch and electrical coupon")
    title.SetDate("2026-08-24")
    title.SetRevision("coupon-2-es1b")
    gen.add_rect_lines(board, 15.0, 10.0, 79.0, 70.0, pcbnew.Edge_Cuts, gen.EDGE_WIDTH)

    nets: dict[str, pcbnew.NETINFO_ITEM] = {"": board.GetNetInfo().GetNetItem(0)}
    samples = (
        ("SW_L", "D_L", (28.0, 40.0), 0.0, -DIODE_OFFSET_MM),
        ("SW_MX", "D_MX", (47.05, 40.0), 0.0, -DIODE_OFFSET_MM),
        ("SW_R", "D_R", (66.10, 40.0), 180.0, DIODE_OFFSET_MM),
    )
    for reference, diode_reference, center, rotation, diode_offset_y in samples:
        add_coupon_switch(
            board,
            nets,
            reference,
            diode_reference,
            center,
            rotation,
            diode_offset_y,
        )

    gen.add_board_text(board, "CHOC V1 UNSUPPORTED", 18.0, 21.0, pcbnew.F_Fab, 0.9)
    gen.add_board_text(board, "DO NOT POPULATE BOTH MODES", 43.0, 21.0, pcbnew.F_Fab, 0.9)
    gen.add_board_text(board, "CHOC LEFT", 23.0, 57.0, pcbnew.F_Fab, 0.8)
    gen.add_board_text(board, "MX 5PIN", 43.0, 57.0, pcbnew.F_Fab, 0.8)
    gen.add_board_text(board, "CHOC RIGHT BOARD", 60.0, 57.0, pcbnew.F_Fab, 0.8)
    gen.add_board_text(
        board,
        "1N4148W-13-F SOD-123: K/P1=ROW A/P2=SWITCH",
        30.0,
        11.5,
        pcbnew.Cmts_User,
        0.7,
    )
    gen.add_board_text(board, "PHYSICAL VF / ROW-HIGH / ZERO-WAIT TEST PENDING", 23.0, 68.5, pcbnew.Cmts_User, 0.7)
    pcbnew.SaveBoard(str(BOARD_PATH), board)
    gen.make_project_file(OUTPUT_DIR, PROJECT_NAME, variant="x3-v2")
    gen.make_fp_lib_table(OUTPUT_DIR, include_switch_lib=False)

    manifest = {
        "requirement": "CON-ARCH-004",
        "purpose": "1:1 physical fit coupon; fabrication and populated fit results are required before orderable status",
        "orientation_scope": (
            "SW_L 0-degree and SW_R 180-degree conservatively exercise both "
            "representative bottom-socket orientations required by CON-ARCH-004 AC-9"
        ),
        "board": str(BOARD_PATH.relative_to(ROOT)),
        "samples": [
            {
                "reference": reference,
                "diode_reference": diode_reference,
                "center_mm": list(center),
                "rotation_deg": rotation,
                "intended_assembly": (
                    "mx_5pin_top_direct_solder"
                    if reference == "SW_MX"
                    else "choc_v2_bottom_socket"
                ),
            }
            for reference, diode_reference, center, rotation, _diode_offset_y in samples
        ],
        "key_pitch_mm": 19.05,
        "switch_footprint": "kc2.pretty:SW_Choc_V2_Socket_MX_THT",
        "matrix_diode": {
            "manufacturer": "Diodes Incorporated",
            "mpn": "1N4148W-13-F",
            "lcsc": "C112342",
            "jlcpcb_part_number": "C526199",
            "eleparts_goods_no": "3417687",
            "footprint": "kc2.pretty:D_1N4148W_SOD123_HandSolder_DiodesInc",
            "assembly_side": "bottom",
            "pin_1": "cathode_row",
            "pin_2": "anode_switch",
            "official_suggested_land_mm": {
                "pad_size": [0.9, 0.95],
                "center_span": 4.05,
            },
            "implemented_hand_solder_land_mm": {
                "classification": "kc2_controlled_not_manufacturer_recommended",
                "pad_size": [1.4, 1.55],
                "center_span": 3.6,
                "inner_gap": 2.2,
                "outer_span": 5.0,
            },
        },
        "service_probes": {
            "per_sample": ["COL", "ANODE", "ROW"],
            "footprint": "TestPoint:TestPoint_Plated_Hole_D2.0mm",
            "drill_mm": 2.0,
            "copper_diameter_mm": 3.0,
        },
        "planned_measurements": {
            "low_current_vf": {
                "connect": "external current source between each ANODE and ROW probe",
                "currents_ua": [100, 1000],
                "record": "forward voltage and polarity for all three populated 1N4148W samples",
            },
            "row_high_3v0_3v3": {
                "connect": "external tester drives COL, closes the matching switch, and senses ROW",
                "supply_v": [3.0, 3.3],
                "record": "ROW high voltage and noise margin for press and release",
            },
            "zero_wait_scan": {
                "connect": "external zero-wait matrix harness uses the labeled COL and ROW probes",
                "record": "missing, false, or stuck events during representative three-key stress",
            },
        },
        "assembly_modes_mutually_exclusive": True,
        "coverage_limitations": {
            "non_1u": "not_covered_by_this_three-switch_coupon; use revised coupon or first article",
            "keycap_spacing": "not_covered_by_this_three-switch_coupon",
            "housing_clearance": "requires printed housing or first-article fit",
            "scan_stress": "representative_three_sample_only; maximum same-row/same-column matrix stress requires first article",
        },
        "order_ready": False,
        "physical_evidence_status": "pending_fabrication_population_and_measurement",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    generate_coupon()
