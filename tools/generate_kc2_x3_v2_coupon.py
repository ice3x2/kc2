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
    contact_1 = gen.add_net(board, nets, f"{reference}_CONTACT_1")
    contact_2 = gen.add_net(board, nets, f"{reference}_CONTACT_2")
    gen.set_pad_net(switch, "1", contact_1)
    gen.set_pad_net(switch, "2", contact_2)
    route_local_path(
        board,
        contact_1,
        center,
        rotation,
        ((2.54, -5.08), (3.3, -6.5), (6.5, -6.5), (6.5, 5.9), (3.7, 5.9)),
    )
    route_local_path(
        board,
        contact_2,
        center,
        rotation,
        ((-3.81, -2.54), (-7.0, -2.54), (-7.0, 3.8), (-8.7, 3.8)),
    )

    diode = gen.load_footprint(
        board,
        gen.KC2_FP_LIB,
        gen.X1_DIODE_FP,
        diode_reference,
        gen.X1_DIODE_VALUE,
        center[0],
        center[1] + diode_offset_y,
        rotation,
        bottom=True,
    )
    diode.Reference().SetLayer(pcbnew.B_Fab)


def generate_coupon() -> dict[str, object]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(2)
    title = board.GetTitleBlock()
    title.SetTitle("KC2 X3 V2 switch fit coupon")
    title.SetDate("2026-08-03")
    title.SetRevision("coupon-1")
    gen.add_rect_lines(board, 15.0, 24.0, 79.0, 56.0, pcbnew.Edge_Cuts, gen.EDGE_WIDTH)

    nets: dict[str, pcbnew.NETINFO_ITEM] = {"": board.GetNetInfo().GetNetItem(0)}
    samples = (
        ("SW_L", "D_L", (28.0, 40.0), 0.0, -7.6),
        ("SW_MX", "D_MX", (47.05, 40.0), 0.0, -7.6),
        ("SW_R", "D_R", (66.10, 40.0), 180.0, 7.6),
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

    gen.add_board_text(board, "CHOC V1 UNSUPPORTED", 18.0, 26.5, pcbnew.F_Fab, 0.9)
    gen.add_board_text(board, "DO NOT POPULATE BOTH MODES", 43.0, 26.5, pcbnew.F_Fab, 0.9)
    gen.add_board_text(board, "CHOC LEFT", 23.0, 53.5, pcbnew.F_Fab, 0.8)
    gen.add_board_text(board, "MX 5PIN", 43.0, 53.5, pcbnew.F_Fab, 0.8)
    gen.add_board_text(board, "CHOC RIGHT BOARD", 60.0, 53.5, pcbnew.F_Fab, 0.8)
    pcbnew.SaveBoard(str(BOARD_PATH), board)
    gen.make_project_file(OUTPUT_DIR, PROJECT_NAME, variant="x3-v2")
    gen.make_fp_lib_table(OUTPUT_DIR, include_switch_lib=False)

    manifest = {
        "requirement": "CON-ARCH-004",
        "purpose": "1:1 physical fit coupon; fabrication and populated fit results are required before orderable status",
        "orientation_scope": (
            "SW_L 0-degree and SW_R 180-degree conservatively exercise both "
            "representative bottom-socket orientations required by CON-ARCH-004 AC-8"
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
        "assembly_modes_mutually_exclusive": True,
        "physical_evidence_status": "pending_fabrication_and_populated_fit_test",
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return manifest


if __name__ == "__main__":
    generate_coupon()
