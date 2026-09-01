from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

import pcbnew

from tools import generate_kc2_pcbs as gen


ALLOWED_WARNING_TYPES = {
    "track_dangling",
    "silk_edge_clearance",
    "silk_over_copper",
}


LEFT_CONTROLLER_COLUMN_NETS = {"L_COL0", "L_COL1"}
LEFT_CONTROLLER_COLUMN_ANCHORS_MM = {
    ("U1", "D3"): (132.4425, 56.6200),
    ("U1", "D5"): (137.5225, 56.6200),
    ("SW1", "1"): (41.4850, 82.6050),
    ("SW2", "1"): (65.6150, 72.4450),
}
LEFT_CONTROLLER_COLUMN_ROUTE = (
    ("track", "L_COL0", "F.Cu", 41.4850, 82.6050, 41.4850, 96.8925, 0.200),
    ("track", "L_COL0", "F.Cu", 46.2475, 101.6550, 47.7273, 103.1348, 0.200),
    ("track", "L_COL0", "F.Cu", 43.8663, 158.8050, 43.3239, 158.2626, 0.200),
    ("track", "L_COL0", "F.Cu", 47.7273, 103.1348, 47.7273, 119.8035, 0.200),
    ("track", "L_COL0", "F.Cu", 41.4850, 96.8925, 46.2475, 101.6550, 0.200),
    ("track", "L_COL0", "F.Cu", 43.3239, 140.2974, 43.8663, 139.7550, 0.200),
    ("track", "L_COL0", "F.Cu", 43.3239, 158.2626, 43.3239, 140.2974, 0.200),
    ("track", "L_COL0", "F.Cu", 47.7273, 119.8035, 48.6288, 120.7050, 0.200),
    ("track", "L_COL0", "B.Cu", 43.8663, 140.3402, 43.0413, 139.5152, 0.200),
    ("track", "L_COL0", "B.Cu", 132.4425, 56.6200, 118.6766, 70.3859, 0.200),
    ("track", "L_COL0", "B.Cu", 43.0413, 139.5152, 43.0413, 129.1100, 0.200),
    ("track", "L_COL0", "B.Cu", 46.2475, 108.5037, 47.4688, 109.7250, 0.200),
    ("track", "L_COL0", "B.Cu", 48.3021, 70.3859, 44.9744, 73.7136, 0.200),
    ("track", "L_COL0", "B.Cu", 43.0413, 129.1100, 42.7063, 128.7750, 0.200),
    ("track", "L_COL0", "B.Cu", 43.8663, 142.8650, 43.8663, 146.6650, 0.200),
    ("track", "L_COL0", "B.Cu", 48.6288, 122.8525, 48.6288, 120.7050, 0.200),
    ("track", "L_COL0", "B.Cu", 40.9216, 73.7136, 40.9216, 82.0416, 0.200),
    ("track", "L_COL0", "B.Cu", 118.6766, 70.3859, 48.3021, 70.3859, 0.200),
    ("track", "L_COL0", "B.Cu", 42.7063, 128.7750, 48.6288, 122.8525, 0.200),
    ("track", "L_COL0", "B.Cu", 45.0875, 90.6750, 41.4850, 87.0725, 0.200),
    ("track", "L_COL0", "B.Cu", 40.9216, 72.2216, 40.9216, 73.7136, 0.200),
    ("track", "L_COL0", "B.Cu", 43.8663, 142.8650, 43.8663, 140.3402, 0.200),
    ("track", "L_COL0", "B.Cu", 44.9744, 73.7136, 40.9216, 73.7136, 0.200),
    ("track", "L_COL0", "B.Cu", 40.9216, 82.0416, 41.4850, 82.6050, 0.200),
    ("track", "L_COL0", "B.Cu", 46.2475, 101.6550, 46.2475, 108.5037, 0.200),
    ("track", "L_COL0", "B.Cu", 43.8663, 146.6650, 42.7063, 147.8250, 0.200),
    ("track", "L_COL0", "B.Cu", 43.8663, 139.7550, 43.8663, 142.8650, 0.200),
    ("track", "L_COL0", "B.Cu", 40.3250, 71.6250, 40.9216, 72.2216, 0.200),
    ("track", "L_COL0", "B.Cu", 41.4850, 87.0725, 41.4850, 82.6050, 0.200),
    ("track", "L_COL1", "F.Cu", 113.5737, 72.1961, 113.5737, 56.3911, 0.200),
    ("track", "L_COL1", "F.Cu", 72.7588, 148.6450, 71.2791, 147.1653, 0.200),
    ("track", "L_COL1", "F.Cu", 79.1416, 95.4966, 75.1400, 91.4950, 0.200),
    ("track", "L_COL1", "F.Cu", 91.9031, 84.2569, 96.3348, 84.2569, 0.200),
    ("track", "L_COL1", "F.Cu", 99.4727, 81.1190, 104.6508, 81.1190, 0.200),
    ("track", "L_COL1", "F.Cu", 69.6142, 76.4442, 69.6142, 85.9692, 0.200),
    ("track", "L_COL1", "F.Cu", 96.3348, 84.2569, 99.4727, 81.1190, 0.200),
    ("track", "L_COL1", "F.Cu", 71.2791, 142.8559, 71.2791, 130.4966, 0.200),
    ("track", "L_COL1", "F.Cu", 71.2791, 130.4966, 70.3775, 129.5950, 0.200),
    ("track", "L_COL1", "F.Cu", 71.2791, 147.1653, 71.2791, 142.8559, 0.200),
    ("track", "L_COL1", "F.Cu", 65.6150, 72.4450, 69.6142, 76.4442, 0.200),
    ("track", "L_COL1", "F.Cu", 70.3775, 129.5950, 76.1382, 123.8343, 0.200),
    ("track", "L_COL1", "F.Cu", 79.9025, 96.2575, 91.9031, 84.2569, 0.200),
    ("track", "L_COL1", "F.Cu", 79.9025, 96.2575, 79.1416, 95.4966, 0.200),
    ("track", "L_COL1", "F.Cu", 79.9025, 101.1439, 79.9025, 96.2575, 0.200),
    ("track", "L_COL1", "F.Cu", 69.6142, 85.9692, 75.1400, 91.4950, 0.200),
    ("track", "L_COL1", "F.Cu", 79.9025, 110.5450, 79.9025, 101.1439, 0.200),
    ("track", "L_COL1", "F.Cu", 104.6508, 81.1190, 113.5737, 72.1961, 0.200),
    ("via", "L_COL1", 71.2791, 142.8559, 0.600, 0.300),
    ("via", "L_COL1", 76.1382, 123.8343, 0.600, 0.300),
    ("via", "L_COL1", 79.9025, 101.1439, 0.600, 0.300),
    ("via", "L_COL1", 113.5737, 56.3911, 0.600, 0.300),
    ("track", "L_COL1", "B.Cu", 80.8041, 111.4466, 80.8041, 121.2666, 0.200),
    ("track", "L_COL1", "B.Cu", 79.9025, 101.1439, 77.6311, 101.1439, 0.200),
    ("track", "L_COL1", "B.Cu", 80.8041, 121.2666, 81.0625, 121.5250, 0.200),
    ("track", "L_COL1", "B.Cu", 73.6604, 149.5466, 72.7588, 148.6450, 0.200),
    ("track", "L_COL1", "B.Cu", 73.6604, 159.3666, 73.6604, 149.5466, 0.200),
    ("track", "L_COL1", "B.Cu", 66.7750, 83.4250, 67.0700, 83.4250, 0.200),
    ("track", "L_COL1", "B.Cu", 136.3002, 55.3977, 137.5225, 56.6200, 0.200),
    ("track", "L_COL1", "B.Cu", 77.6311, 101.1439, 76.3000, 102.4750, 0.200),
    ("track", "L_COL1", "B.Cu", 114.5671, 55.3977, 136.3002, 55.3977, 0.200),
    ("track", "L_COL1", "B.Cu", 113.5737, 56.3911, 114.5671, 55.3977, 0.200),
    ("track", "L_COL1", "B.Cu", 79.9025, 110.5450, 80.8041, 111.4466, 0.200),
    ("track", "L_COL1", "B.Cu", 71.2791, 140.8334, 71.5375, 140.5750, 0.200),
    ("track", "L_COL1", "B.Cu", 71.2791, 142.8559, 71.2791, 140.8334, 0.200),
    ("track", "L_COL1", "B.Cu", 76.1382, 123.8343, 78.7532, 123.8343, 0.200),
    ("track", "L_COL1", "B.Cu", 78.7532, 123.8343, 81.0625, 121.5250, 0.200),
    ("track", "L_COL1", "B.Cu", 73.9188, 159.6250, 73.6604, 159.3666, 0.200),
    ("track", "L_COL1", "B.Cu", 67.0700, 83.4250, 75.1400, 91.4950, 0.200),
)


RIGHT_R12_FINAL_ROUTE_ITEM_COUNT = 697
RIGHT_R12_FINAL_ROUTE_SHA256 = "040d236ab756e294373e59556a778355cda0448c7127518caa70090d1257106a"
RIGHT_R12_IMPORTED_ONLY_ROUTE = (
    ("track", "R_COL6", "B.Cu", 79.3776, 85.2680, 79.3776, 87.5840, 0.200),
    ("track", "R_COL6", "F.Cu", 79.3776, 85.2680, 79.3776, 87.5840, 0.200),
    ("track", "R_COL6", "B.Cu", 79.3776, 87.5840, 79.3776, 85.2680, 0.200),
    ("track", "R_COL6", "F.Cu", 79.3776, 87.5840, 79.3776, 85.2680, 0.200),
    ("track", "R_COL6", "B.Cu", 78.8995, 60.4155, 78.8983, 60.4143, 0.200),
    ("track", "R_COL6", "F.Cu", 78.8995, 60.4155, 78.8983, 60.4143, 0.200),
    ("track", "R_COL6", "B.Cu", 78.8983, 60.4143, 78.8995, 60.4155, 0.200),
    ("track", "R_COL6", "F.Cu", 78.8983, 60.4143, 78.8995, 60.4155, 0.200),
    ("track", "R_COL3", "F.Cu", 111.1111, 86.5350, 111.1111, 85.9139, 0.200),
    ("track", "R_COL3", "F.Cu", 111.1111, 85.9139, 111.1111, 86.5350, 0.200),
    ("track", "R_COL3", "B.Cu", 117.0453, 126.3076, 117.0453, 121.5250, 0.200),
    ("track", "R_COL3", "F.Cu", 117.0453, 126.3076, 117.0453, 121.5250, 0.200),
    ("track", "R_COL3", "B.Cu", 117.0453, 121.5250, 117.0453, 126.3076, 0.200),
    ("track", "R_COL3", "F.Cu", 117.0453, 121.5250, 117.0453, 126.3076, 0.200),
    ("track", "R_COL3", "B.Cu", 114.0782, 80.5345, 114.0782, 81.5899, 0.200),
    ("track", "R_COL3", "F.Cu", 114.0782, 80.5345, 114.0782, 81.5899, 0.200),
    ("track", "R_COL3", "B.Cu", 114.0782, 81.5899, 114.0782, 80.5345, 0.200),
    ("track", "R_COL3", "F.Cu", 114.0782, 81.5899, 114.0782, 80.5345, 0.200),
)


ES1B_ROUTE_ITEM_COUNTS = {"left": 564, "right": 732}
ES1B_ROUTE_SHA256 = {
    "left": "ba48ff17dd7f447e4cbededba09c1889b82713b1defef18d63aace4e59f92c7d",
    "right": "1592744e711eda0eef59d51062c3c2bab87e5ae05c8156f0708f0544a09b7e38",
}


CONTROLLER_COMPACT_IMPORTED_ITEM_COUNTS = {"left": 539, "right": 703}
CONTROLLER_COMPACT_IMPORTED_ROUTE_SHA256 = {
    "left": "4048da738ac3f3a5106ed86de5d7a8291014993daa73044c695f55f353d22967",
    "right": "15f7dd78eb1195d4697e0d6f0457cfcdfaf347fc9be28a749ae341ce5ecbae2d",
}
CONTROLLER_COMPACT_ROUTE_ITEM_COUNTS = {"left": 590, "right": 766}
CONTROLLER_COMPACT_ROUTE_SHA256 = {
    "left": "b8adeac705f846714f7f201b63487369ef486cb1624df8d0ddbb8cde3053e316",
    "right": "530d6927eacd7e57a48cb6c62e5c5916ef1f4b3f21d67b592e80962ef7af4c1b",
}


def center_1n4148w_diode_route_endpoints(
    board: pcbnew.BOARD,
    side: str,
) -> dict[str, int]:
    """Move reviewed ES1B-era route junctions onto exact SOD-123 pad centres."""
    expected_count = 31 if side == "left" else 39
    diodes = sorted(
        (
            footprint
            for footprint in board.GetFootprints()
            if footprint.GetReference().startswith("D")
            and footprint.GetReference()[1:].isdigit()
        ),
        key=lambda footprint: int(footprint.GetReference()[1:]),
    )
    if len(diodes) != expected_count:
        raise RuntimeError(
            f"{side} SOD-123 route centering expected {expected_count} diodes, "
            f"found {len(diodes)}"
        )

    endpoint_updates = 0
    centred_pads = 0
    for diode in diodes:
        for pad in diode.Pads():
            centre = pad.GetPosition()
            net_name = pad.GetNetname()
            centred: list[tuple[pcbnew.PCB_TRACK, str]] = []
            legacy: list[tuple[pcbnew.PCB_TRACK, str]] = []
            for item in board.GetTracks():
                if isinstance(item, pcbnew.PCB_VIA):
                    continue
                if item.GetNetname() != net_name or item.GetLayer() != pcbnew.B_Cu:
                    continue
                for endpoint_name, endpoint in (
                    ("start", item.GetStart()),
                    ("end", item.GetEnd()),
                ):
                    dx = pcbnew.ToMM(endpoint.x - centre.x)
                    dy = pcbnew.ToMM(endpoint.y - centre.y)
                    distance = (dx * dx + dy * dy) ** 0.5
                    if distance <= 0.001:
                        centred.append((item, endpoint_name))
                    elif abs(distance - 0.300) <= 0.001:
                        legacy.append((item, endpoint_name))
            if centred:
                if legacy:
                    raise RuntimeError(
                        f"{side} {diode.GetReference()} pad {pad.GetNumber()} has "
                        "mixed centred and legacy diode route endpoints"
                    )
                centred_pads += 1
                continue
            if not legacy:
                raise RuntimeError(
                    f"{side} {diode.GetReference()} pad {pad.GetNumber()} has no "
                    "exact centred or 0.30 mm legacy route endpoint"
                )
            for item, endpoint_name in legacy:
                if endpoint_name == "start":
                    item.SetStart(centre)
                else:
                    item.SetEnd(centre)
                endpoint_updates += 1
            centred_pads += 1

    if centred_pads != expected_count * 2:
        raise RuntimeError(f"{side} SOD-123 route centering was incomplete")
    return {
        "diode_pads_centered": centred_pads,
        "route_endpoints_updated": endpoint_updates,
    }
CONTROLLER_COMPACT_ROUTE_REMOVALS = {
    "left": (
        ("track", "L_COL6", "B.Cu", 155.0477, 72.4450, 146.6825, 64.0798, 0.250),
        ("track", "L_ROW1", "B.Cu", 149.6467, 60.3252, 150.9160, 61.5945, 0.250),
        ("track", "L_ROW1", "F.Cu", 150.9160, 76.0243, 150.9160, 61.5945, 0.250),
        ("via", "L_COL2", 90.3462, 70.1926, 0.600, 0.300),
        ("via", "L_ROW1", 150.9160, 61.5945, 0.600, 0.300),
    ),
    "right": (
        ("track", "R_COL0", "B.Cu", 43.7521, 109.7250, 40.4850, 106.4579, 0.250),
        ("track", "R_COL1", "F.Cu", 63.4300, 61.8416, 70.9719, 69.3834, 0.250),
        ("track", "R_COL1", "F.Cu", 64.3743, 75.9810, 70.9719, 69.3834, 0.250),
        ("track", "R_COL1", "F.Cu", 70.9719, 69.3834, 74.0334, 72.4450, 0.250),
        ("track", "R_COL6", "B.Cu", 97.3280, 89.1791, 96.8259, 89.1791, 0.250),
        ("track", "R_COL6", "F.Cu", 96.8259, 89.1791, 94.1212, 86.4744, 0.250),
        ("track", "R_ROW3", "F.Cu", 100.4593, 62.9144, 91.7219, 54.1770, 0.250),
        ("track", "R_ROW3", "F.Cu", 100.4593, 91.6911, 100.4593, 62.9144, 0.250),
        ("via", "R_COL6", 96.8259, 89.1791, 0.600, 0.300),
    ),
}
CONTROLLER_COMPACT_ROUTE_ADDITIONS = {
    "left": (
        ("track", "L_COL2", "B.Cu", 90.3462, 70.1926, 91.5000, 70.3000, 0.250),
        ("track", "L_COL2", "F.Cu", 90.3462, 70.1926, 91.5000, 70.3000, 0.250),
        ("track", "L_COL6", "B.Cu", 146.6825, 64.0798, 150.9000, 68.2973, 0.250),
        ("track", "L_COL6", "B.Cu", 150.9000, 68.2973, 150.9000, 70.2000, 0.250),
        ("track", "L_COL6", "B.Cu", 150.9000, 70.2000, 155.0477, 72.4450, 0.250),
        ("track", "L_ROW1", "B.Cu", 149.6467, 60.3252, 150.8500, 61.5945, 0.250),
        ("track", "L_ROW1", "F.Cu", 150.9160, 76.0243, 150.8500, 61.5945, 0.250),
        ("via", "L_COL2", 91.5000, 70.3000, 0.600, 0.300),
        ("via", "L_ROW1", 150.8500, 61.5945, 0.600, 0.300),
    ),
    "right": (
        ("track", "R_COL0", "B.Cu", 40.4000, 108.0000, 43.7521, 109.7250, 0.250),
        ("track", "R_COL0", "B.Cu", 40.4850, 106.4579, 40.4000, 108.0000, 0.250),
        ("track", "R_COL1", "F.Cu", 63.4300, 61.8416, 69.5000, 67.0000, 0.250),
        ("track", "R_COL1", "F.Cu", 69.5000, 67.0000, 69.5000, 70.0000, 0.250),
        ("track", "R_COL1", "F.Cu", 69.5000, 70.0000, 64.3743, 75.9810, 0.250),
        ("track", "R_COL1", "F.Cu", 69.5000, 70.0000, 74.0334, 72.4450, 0.250),
        ("track", "R_COL6", "B.Cu", 97.3280, 89.1791, 97.0500, 89.1791, 0.250),
        ("track", "R_COL6", "F.Cu", 97.0500, 89.1791, 94.1212, 86.4744, 0.250),
        ("track", "R_ROW3", "F.Cu", 91.7219, 54.1770, 100.2000, 62.6551, 0.250),
        ("track", "R_ROW3", "F.Cu", 100.2000, 62.6551, 100.2000, 91.6911, 0.250),
        ("track", "R_ROW3", "F.Cu", 100.2000, 91.6911, 100.4593, 91.6911, 0.250),
        ("via", "R_COL6", 97.0500, 89.1791, 0.600, 0.300),
    ),
}
MATRIX_SERVICE_ROUTE_REMOVALS = {
    "left": (
        ("track", "L_COL0", "F.Cu", 131.4425, 58.3700, 117.9254, 71.8871, 0.250),
        ("track", "L_COL1", "F.Cu", 132.0690, 59.7698, 119.2058, 72.6330, 0.250),
        ("track", "L_COL2", "B.Cu", 122.1599, 70.1926, 133.9825, 58.3700, 0.250),
    ),
    "right": (),
}
MATRIX_SERVICE_ROUTE_ADDITIONS = {
    "left": (
        ("track", "L_COL0", "B.Cu", 131.4425, 58.3700, 132.1000, 60.0000, 0.250),
        ("track", "L_COL0", "B.Cu", 132.1000, 60.0000, 132.1000, 67.0000, 0.250),
        ("track", "L_COL0", "B.Cu", 132.1000, 67.0000, 117.9254, 71.8871, 0.250),
        ("via", "L_COL0", 117.9254, 71.8871, 0.600, 0.300),
        ("track", "L_COL1", "B.Cu", 132.0690, 59.7698, 133.1000, 60.5000, 0.250),
        ("via", "L_COL1", 132.0690, 59.7698, 0.600, 0.300),
        ("track", "L_COL1", "B.Cu", 133.1000, 60.5000, 133.1000, 67.5000, 0.250),
        ("track", "L_COL1", "B.Cu", 133.1000, 67.5000, 119.2058, 72.6330, 0.250),
        ("via", "L_COL1", 119.2058, 72.6330, 0.600, 0.300),
        ("track", "L_COL2", "B.Cu", 133.9825, 58.3700, 134.5000, 59.0000, 0.250),
        ("track", "L_COL2", "B.Cu", 134.5000, 59.0000, 134.5000, 68.0000, 0.250),
        ("track", "L_COL2", "B.Cu", 134.5000, 68.0000, 122.1599, 70.1926, 0.250),
    ),
    "right": (),
}
MATRIX_CONNECTIVITY_ROUTE_REMOVALS = {
    side: tuple(spec["removals"])
    for side, spec in gen.X3_V2_MATRIX_CONNECTIVITY_DETOURS.items()
}
MATRIX_CONNECTIVITY_ROUTE_ADDITIONS = {
    side: tuple(spec["additions"])
    for side, spec in gen.X3_V2_MATRIX_CONNECTIVITY_DETOURS.items()
}
V2_USB_UNDER_RESET_ROUTES = {
    "left": (
        ("track", "RST", "F.Cu", 113.7625, 54.6250, 115.1000, 48.8000, 0.250),
        ("track", "RST", "F.Cu", 115.1000, 48.8000, 122.4000, 44.5000, 0.250),
        ("track", "RST", "F.Cu", 122.4000, 44.5000, 122.6000, 44.5000, 0.250),
        ("track", "RST", "F.Cu", 122.6000, 44.5000, 123.8225, 43.1300, 0.250),
        ("track", "GND", "F.Cu", 113.7625, 46.8750, 116.0000, 46.6000, 0.250),
        ("via", "GND", 116.0000, 46.6000, 0.800, 0.400),
        ("track", "GND", "B.Cu", 116.0000, 46.6000, 120.0000, 44.5000, 0.250),
        ("track", "GND", "B.Cu", 120.0000, 44.5000, 121.2825, 43.1300, 0.250),
    ),
    "right": (
        ("track", "RST", "F.Cu", 96.3500, 54.6250, 93.9000, 54.7000, 0.250),
        ("via", "RST", 93.9000, 54.7000, 0.800, 0.400),
        ("track", "RST", "B.Cu", 93.9000, 54.7000, 92.7000, 55.5000, 0.250),
        ("track", "RST", "B.Cu", 92.7000, 55.5000, 89.7000, 56.9000, 0.250),
        ("track", "RST", "B.Cu", 89.7000, 56.9000, 87.6000, 57.0000, 0.250),
        ("track", "RST", "B.Cu", 87.6000, 57.0000, 86.2900, 58.3700, 0.250),
        ("track", "GND", "F.Cu", 96.3500, 46.8750, 95.0000, 52.7000, 0.250),
        ("track", "GND", "F.Cu", 95.0000, 52.7000, 94.1000, 53.6000, 0.250),
        ("via", "GND", 94.1000, 53.6000, 0.800, 0.400),
        ("track", "GND", "B.Cu", 94.1000, 53.6000, 90.0000, 55.7000, 0.250),
        ("via", "GND", 90.0000, 55.7000, 0.800, 0.400),
        ("track", "GND", "F.Cu", 90.0000, 55.7000, 88.8300, 58.3700, 0.250),
    ),
}
ES1B_IMPORTED_ITEM_COUNTS = {"left": 560, "right": 729}
ES1B_ROUTE_REMOVALS = {
    "left": (
        ("track", "L_ROW0", "B.Cu", 148.5750, 71.4872, 150.8671, 71.4872, 0.250),
        ("track", "L_COL0", "B.Cu", 122.6545, 104.9299, 46.4687, 104.9299, 0.250),
    ),
    "right": (
        ("track", "R_COL1", "B.Cu", 70.0985, 128.6218, 71.0717, 129.5950, 0.250),
        ("track", "R_COL1", "B.Cu", 70.0985, 121.9640, 70.0985, 128.6218, 0.250),
        ("via", "R_ROW4", 66.1387, 143.2420, 0.600, 0.300),
        ("track", "R_ROW4", "B.Cu", 70.8543, 147.9576, 66.1387, 143.2420, 0.250),
        ("track", "R_ROW4", "F.Cu", 66.1387, 143.2420, 66.1387, 130.9012, 0.250),
        ("track", "R_ROW1", "B.Cu", 60.3056, 88.2454, 60.3056, 80.1004, 0.250),
        ("track", "R_COL6", "B.Cu", 99.1009, 84.0393, 99.1009, 86.2026, 0.250),
        ("track", "R_COL6", "F.Cu", 99.1009, 84.0393, 99.1009, 86.2026, 0.250),
        ("track", "R_COL6", "B.Cu", 99.1009, 86.2026, 99.1009, 84.0393, 0.250),
        ("track", "R_COL6", "F.Cu", 99.1009, 86.2026, 99.1009, 84.0393, 0.250),
        ("track", "R_COL2", "B.Cu", 80.9822, 73.5207, 84.9343, 73.5207, 0.250),
        ("track", "R_COL2", "B.Cu", 79.2828, 71.8213, 80.9822, 73.5207, 0.250),
    ),
}
ES1B_ROUTE_ADDITIONS = {
    "left": (
        ("track", "L_COL0", "B.Cu", 46.4687, 104.9299, 50.8000, 104.9299, 0.250),
        ("track", "L_COL0", "B.Cu", 50.8000, 104.9299, 51.1000, 105.2500, 0.250),
        ("track", "L_COL0", "B.Cu", 51.1000, 105.2500, 58.4750, 105.2500, 0.250),
        ("track", "L_COL0", "B.Cu", 58.4750, 105.2500, 58.8000, 104.9299, 0.250),
        ("track", "L_COL0", "B.Cu", 58.8000, 104.9299, 122.6545, 104.9299, 0.250),
    ),
    "right": (
        ("track", "R_COL2", "B.Cu", 79.2828, 71.8213, 79.8000, 73.0000, 0.250),
        ("track", "R_COL2", "B.Cu", 79.8000, 73.0000, 79.8000, 74.2750, 0.250),
        ("track", "R_COL2", "B.Cu", 79.8000, 74.2750, 84.2000, 74.2750, 0.250),
        ("track", "R_COL2", "B.Cu", 84.2000, 74.2750, 84.9343, 73.5207, 0.250),
        ("via", "R_COL1", 70.0985, 121.9640, 0.600, 0.300),
        ("via", "R_COL1", 71.0717, 129.5950, 0.600, 0.300),
        ("track", "R_COL1", "F.Cu", 70.0985, 121.9640, 71.0717, 129.5950, 0.250),
        ("track", "R_ROW1", "B.Cu", 60.3056, 88.2454, 59.5500, 87.4898, 0.250),
        ("track", "R_ROW1", "B.Cu", 59.5500, 87.4898, 59.5500, 81.0000, 0.250),
        ("track", "R_ROW1", "B.Cu", 59.5500, 81.0000, 60.3056, 80.1004, 0.250),
        ("track", "R_ROW4", "F.Cu", 66.1387, 143.6000, 66.1387, 130.9012, 0.250),
        ("track", "R_ROW4", "B.Cu", 70.8543, 147.9576, 66.1387, 143.6000, 0.250),
        ("via", "R_ROW4", 66.1387, 143.6000, 0.600, 0.300),
    ),
}

M1_4_DRIVER_ROUTE_REMOVALS = {
    "left": (
        ("track", "L_COL5", "F.Cu", 144.1425, 56.6200, 144.1425, 69.1175, 0.250),
        ("track", "L_COL5", "F.Cu", 144.1425, 69.1175, 140.8150, 72.4450, 0.250),
    ),
    "right": (
        ("track", "RK30_D", "B.Cu", 143.8625, 136.0703, 147.7978, 132.1350, 0.250),
    ),
}
M1_4_DRIVER_ROUTE_ADDITIONS = {
    "left": (
        ("track", "L_COL5", "B.Cu", 144.1425, 56.6200, 140.8150, 64.5000, 0.250),
        ("via", "L_COL5", 140.8150, 64.5000, 0.600, 0.300),
        ("track", "L_COL5", "F.Cu", 140.8150, 64.5000, 140.8150, 72.4450, 0.250),
    ),
    "right": (
        ("track", "RK30_D", "B.Cu", 143.8625, 136.0703, 145.5000, 135.0000, 0.250),
        ("track", "RK30_D", "B.Cu", 145.5000, 135.0000, 147.0000, 132.5000, 0.250),
        ("track", "RK30_D", "B.Cu", 147.0000, 132.5000, 147.7978, 132.1350, 0.250),
    ),
}


P1_ROUNDED_HEAD_ROUTE_REMOVALS = {
    "left": (
        ("track", "L_COL5", "F.Cu", 140.8150, 61.6975, 140.8150, 72.4450, 0.250),
        ("track", "L_COL4", "B.Cu", 130.9950, 91.4950, 122.9250, 83.4250, 0.250),
        ("track", "L_COL3", "B.Cu", 112.2400, 91.4950, 104.1700, 83.4250, 0.250),
        ("track", "L_ROW1", "B.Cu", 58.8115, 101.6510, 58.8115, 90.9855, 0.250),
        ("track", "L_COL4", "F.Cu", 124.6188, 124.4412, 126.5275, 126.3499, 0.250),
        ("via", "L_COL4", 124.6188, 124.4412, 0.600, 0.300),
        ("track", "L_COL4", "B.Cu", 133.6963, 124.4412, 124.6188, 124.4412, 0.250),
        ("track", "L_ROW3", "B.Cu", 120.4678, 126.2947, 138.1375, 126.2947, 0.250),
        ("track", "L_ROW4", "B.Cu", 98.5506, 145.3659, 116.7063, 145.3659, 0.250),
    ),
    "right": (
        ("track", "R_COL6", "B.Cu", 111.1497, 104.6982, 103.6462, 97.1947, 0.250),
        ("track", "R_COL6", "B.Cu", 132.9544, 104.6982, 111.1497, 104.6982, 0.250),
        ("track", "R_ROW2", "B.Cu", 63.3038, 107.2587, 80.9875, 107.2587, 0.250),
        ("track", "R_ROW1", "F.Cu", 62.0770, 87.3977, 62.0770, 57.1830, 0.250),
        ("track", "R_ROW2", "F.Cu", 61.0903, 88.1813, 61.0903, 55.6297, 0.250),
        ("track", "R_ROW4", "F.Cu", 60.5386, 80.0662, 60.5386, 51.1014, 0.250),
        ("track", "R_COL6", "B.Cu", 177.4877, 142.7502, 187.3077, 142.7502, 0.250),
        ("track", "R_COL4", "B.Cu", 150.9249, 142.6343, 139.2718, 142.6343, 0.250),
        ("track", "RK33_D", "B.Cu", 66.0125, 149.9250, 66.0125, 152.3891, 0.250),
        ("track", "RK33_D", "B.Cu", 66.0125, 152.3891, 62.1366, 156.2650, 0.250),
        ("track", "R_ROW4", "B.Cu", 80.0097, 145.3216, 105.7779, 145.3216, 0.250),
    ),
}
P1_ROUNDED_HEAD_ROUTE_ADDITIONS = {
    "left": (
        ("track", "L_COL5", "F.Cu", 140.8150, 61.6975, 140.5000, 71.7500, 0.250),
        ("track", "L_COL5", "F.Cu", 140.5000, 71.7500, 140.8150, 72.4450, 0.250),
        ("track", "L_COL4", "B.Cu", 130.9950, 91.4950, 123.5000, 84.2500, 0.250),
        ("track", "L_COL4", "B.Cu", 123.5000, 84.2500, 122.9250, 83.4250, 0.250),
        ("track", "L_COL3", "B.Cu", 112.2400, 91.4950, 110.2500, 86.0000, 0.250),
        ("track", "L_COL3", "B.Cu", 110.2500, 86.0000, 109.5000, 85.2500, 0.250),
        ("track", "L_COL3", "B.Cu", 109.5000, 85.2500, 108.0000, 85.0000, 0.250),
        ("track", "L_COL3", "B.Cu", 108.0000, 85.0000, 104.1700, 83.4250, 0.250),
        ("track", "L_ROW1", "B.Cu", 58.8115, 101.6510, 59.5000, 98.2500, 0.250),
        ("track", "L_ROW1", "B.Cu", 59.5000, 98.2500, 58.8115, 90.9855, 0.250),
        ("track", "L_COL4", "F.Cu", 126.5275, 126.3499, 127.5000, 125.7500, 0.250),
        ("via", "L_COL4", 127.5000, 125.7500, 0.600, 0.300),
        ("track", "L_COL4", "B.Cu", 127.5000, 125.7500, 133.6963, 124.4412, 0.250),
        ("track", "L_ROW3", "B.Cu", 120.4678, 126.2947, 124.5000, 127.0000, 0.250),
        ("track", "L_ROW3", "B.Cu", 124.5000, 127.0000, 132.5000, 126.5000, 0.250),
        ("track", "L_ROW3", "B.Cu", 132.5000, 126.5000, 133.2500, 126.2500, 0.250),
        ("track", "L_ROW3", "B.Cu", 133.2500, 126.2500, 138.1375, 126.2947, 0.250),
        ("track", "L_ROW4", "B.Cu", 98.5506, 145.3659, 104.5000, 145.0000, 0.250),
        ("track", "L_ROW4", "B.Cu", 104.5000, 145.0000, 116.7063, 145.3659, 0.250),
    ),
    "right": (
        ("track", "R_COL6", "B.Cu", 132.9544, 104.6982, 117.2500, 104.5000, 0.250),
        ("track", "R_COL6", "B.Cu", 117.2500, 104.5000, 108.7500, 102.0000, 0.250),
        ("track", "R_COL6", "B.Cu", 108.7500, 102.0000, 104.2500, 98.0000, 0.250),
        ("track", "R_COL6", "B.Cu", 104.2500, 98.0000, 103.6462, 97.1947, 0.250),
        ("track", "R_ROW2", "B.Cu", 63.3038, 107.2587, 75.5000, 107.5000, 0.250),
        ("track", "R_ROW2", "B.Cu", 75.5000, 107.5000, 75.7500, 107.2500, 0.250),
        ("track", "R_ROW2", "B.Cu", 75.7500, 107.2500, 80.9875, 107.2587, 0.250),
        ("track", "R_ROW1", "F.Cu", 62.0770, 87.3977, 64.0000, 69.2500, 0.250),
        ("track", "R_ROW1", "F.Cu", 64.0000, 69.2500, 62.7500, 61.2500, 0.250),
        ("track", "R_ROW1", "F.Cu", 62.7500, 61.2500, 62.0000, 59.2500, 0.250),
        ("track", "R_ROW1", "F.Cu", 62.0000, 59.2500, 62.0770, 57.1830, 0.250),
        ("track", "R_ROW2", "F.Cu", 61.0903, 88.1813, 61.2500, 71.2500, 0.250),
        ("via", "R_ROW2", 61.2500, 71.2500, 0.600, 0.300),
        ("track", "R_ROW2", "B.Cu", 61.2500, 71.2500, 60.2500, 70.2500, 0.250),
        ("track", "R_ROW2", "B.Cu", 60.2500, 70.2500, 60.0000, 68.2500, 0.250),
        ("track", "R_ROW2", "B.Cu", 60.0000, 68.2500, 60.7500, 67.5000, 0.250),
        ("via", "R_ROW2", 60.7500, 67.5000, 0.600, 0.300),
        ("track", "R_ROW2", "F.Cu", 60.7500, 67.5000, 61.0903, 55.6297, 0.250),
        ("track", "R_ROW4", "F.Cu", 60.5386, 80.0662, 60.2500, 79.7500, 0.250),
        ("via", "R_ROW4", 60.2500, 79.7500, 0.600, 0.300),
        ("track", "R_ROW4", "B.Cu", 60.2500, 79.7500, 62.2500, 76.0000, 0.250),
        ("track", "R_ROW4", "B.Cu", 62.2500, 76.0000, 63.0000, 75.2500, 0.250),
        ("track", "R_ROW4", "B.Cu", 63.0000, 75.2500, 64.0000, 69.2500, 0.250),
        ("track", "R_ROW4", "B.Cu", 64.0000, 69.2500, 62.0000, 59.0000, 0.250),
        ("track", "R_ROW4", "B.Cu", 62.0000, 59.0000, 61.0000, 54.5000, 0.250),
        ("via", "R_ROW4", 61.0000, 54.5000, 0.600, 0.300),
        ("track", "R_ROW4", "F.Cu", 61.0000, 54.5000, 60.5386, 51.1014, 0.250),
        ("track", "R_COL6", "B.Cu", 177.4877, 142.7502, 180.2500, 141.2500, 0.250),
        ("track", "R_COL6", "B.Cu", 180.2500, 141.2500, 181.7500, 141.0000, 0.250),
        ("track", "R_COL6", "B.Cu", 181.7500, 141.0000, 187.3077, 142.7502, 0.250),
        ("track", "R_COL4", "B.Cu", 150.9249, 142.6343, 142.7500, 141.0000, 0.250),
        ("track", "R_COL4", "B.Cu", 142.7500, 141.0000, 139.2718, 142.6343, 0.250),
        ("track", "RK33_D", "B.Cu", 66.0125, 149.9250, 63.7500, 154.7500, 0.250),
        ("track", "RK33_D", "B.Cu", 63.7500, 154.7500, 62.1366, 156.2650, 0.250),
        ("track", "R_ROW4", "B.Cu", 80.0097, 145.3216, 105.0000, 145.0000, 0.250),
        ("track", "R_ROW4", "B.Cu", 105.0000, 145.0000, 105.7779, 145.3216, 0.250),
    ),
}

SOD123_HAND_SOLDER_ROUTE_REMOVALS = {
    "left": (),
    "right": (
        ("track", "R_COL3", "B.Cu", 106.8100, 127.7935, 106.8100, 123.3525, 0.250),
        ("track", "R_COL3", "B.Cu", 108.6115, 129.5950, 106.8100, 127.7935, 0.250),
    ),
}
SOD123_HAND_SOLDER_ROUTE_ADDITIONS = {
    "left": (),
    "right": (
        ("via", "R_COL3", 108.6115, 129.5950, 0.600, 0.300),
        ("track", "R_COL3", "F.Cu", 108.6115, 129.5950, 111.8000, 125.3000, 0.250),
        ("via", "R_COL3", 111.8000, 125.3000, 0.600, 0.300),
        ("track", "R_COL3", "B.Cu", 111.8000, 125.3000, 106.8100, 123.3525, 0.250),
    ),
}


def _route_signature(item: pcbnew.BOARD_CONNECTED_ITEM) -> tuple[object, ...]:
    if isinstance(item, pcbnew.PCB_VIA):
        position = item.GetPosition()
        return (
            "via",
            item.GetNetname(),
            round(pcbnew.ToMM(position.x), 4),
            round(pcbnew.ToMM(position.y), 4),
            round(pcbnew.ToMM(item.GetWidth(pcbnew.F_Cu)), 3),
            round(pcbnew.ToMM(item.GetDrillValue()), 3),
        )
    start = item.GetStart()
    end = item.GetEnd()
    return (
        "track",
        item.GetNetname(),
        item.GetBoard().GetLayerName(item.GetLayer()),
        round(pcbnew.ToMM(start.x), 4),
        round(pcbnew.ToMM(start.y), 4),
        round(pcbnew.ToMM(end.x), 4),
        round(pcbnew.ToMM(end.y), 4),
        round(pcbnew.ToMM(item.GetWidth()), 3),
    )


def _route_counter_digest(signatures: Counter[tuple[object, ...]]) -> str:
    payload = "\n".join(
        repr((signature, count)) for signature, count in sorted(signatures.items())
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _has_exact_reviewed_right_route(board: pcbnew.BOARD) -> bool:
    signatures = Counter(_route_signature(item) for item in board.GetTracks())
    return (
        sum(signatures.values()) == RIGHT_R12_FINAL_ROUTE_ITEM_COUNT
        and _route_counter_digest(signatures) == RIGHT_R12_FINAL_ROUTE_SHA256
        and _matrix_pads_are_fully_connected(board, "right")
    )


def _matrix_pads_are_fully_connected(board: pcbnew.BOARD, side: str) -> bool:
    prefixes = ("L_ROW", "L_COL", "LK") if side == "left" else ("R_ROW", "R_COL", "RK")
    pads_by_net: dict[str, list[pcbnew.PAD]] = {}
    for footprint in board.GetFootprints():
        for pad in footprint.Pads():
            net_name = pad.GetNetname()
            if net_name.startswith(prefixes):
                pads_by_net.setdefault(net_name, []).append(pad)
    if not pads_by_net:
        return False
    board.BuildConnectivity()
    connectivity = board.GetConnectivity()
    for pads in pads_by_net.values():
        connected = {
            item.m_Uuid.AsString()
            for item in connectivity.GetConnectedItems(pads[0])
        }
        connected.add(pads[0].m_Uuid.AsString())
        if any(pad.m_Uuid.AsString() not in connected for pad in pads):
            return False
    return True


def _has_exact_current_mounting_geometry(board: pcbnew.BOARD, side: str) -> bool:
    expected = {
        f"MH{index}": position
        for index, position in enumerate(gen.X3_V2_MOUNTING_POINTS[side], start=1)
    }
    actual: dict[str, tuple[float, float]] = {}
    for footprint in board.GetFootprints():
        reference = footprint.GetReference()
        if not re.fullmatch(r"MH\d+", reference):
            continue
        position = footprint.GetPosition()
        actual[reference] = (
            round(pcbnew.ToMM(position.x), 4),
            round(pcbnew.ToMM(position.y), 4),
        )
    return actual == expected


def _add_route_spec(board: pcbnew.BOARD, spec: tuple[object, ...]) -> None:
    kind, net_name, *values = spec
    net = board.FindNet(str(net_name))
    if net is None:
        raise RuntimeError(f"missing reviewed route net {net_name}")
    if kind == "via":
        x, y, diameter, drill = values
        item = pcbnew.PCB_VIA(board)
        item.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
        item.SetWidth(pcbnew.FromMM(diameter))
        item.SetDrill(pcbnew.FromMM(drill))
        item.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    else:
        layer_name, x1, y1, x2, y2, width = values
        item = pcbnew.PCB_TRACK(board)
        item.SetLayer(board.GetLayerID(layer_name))
        item.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(x1), pcbnew.FromMM(y1)))
        item.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(x2), pcbnew.FromMM(y2)))
        item.SetWidth(pcbnew.FromMM(width))
    item.SetNet(net)
    board.Add(item)


def apply_matrix_service_detours(board: pcbnew.BOARD, side: str) -> dict[str, int]:
    if side not in MATRIX_SERVICE_ROUTE_REMOVALS:
        raise RuntimeError(f"unsupported matrix-service detour side {side!r}")
    removals = Counter(MATRIX_SERVICE_ROUTE_REMOVALS[side])
    additions = Counter(MATRIX_SERVICE_ROUTE_ADDITIONS[side])
    signatures = Counter(_route_signature(item) for item in board.GetTracks())
    if signatures & additions == additions and not signatures & removals:
        return {"removed": 0, "added": 0}
    if signatures & removals != removals:
        raise RuntimeError(f"{side} matrix-service detour precondition failed")
    remaining = removals.copy()
    removed = 0
    for item in list(board.GetTracks()):
        signature = _route_signature(item)
        if remaining[signature] <= 0:
            continue
        board.Delete(item)
        remaining[signature] -= 1
        removed += 1
    if any(remaining.values()):
        raise RuntimeError(f"{side} matrix-service detour removal was incomplete")
    for spec in MATRIX_SERVICE_ROUTE_ADDITIONS[side]:
        _add_route_spec(board, spec)
    return {"removed": removed, "added": len(MATRIX_SERVICE_ROUTE_ADDITIONS[side])}


def apply_matrix_connectivity_detours(board: pcbnew.BOARD, side: str) -> dict[str, int]:
    if side not in MATRIX_CONNECTIVITY_ROUTE_REMOVALS:
        raise RuntimeError(f"unsupported matrix-connectivity detour side {side!r}")
    removals = Counter(MATRIX_CONNECTIVITY_ROUTE_REMOVALS[side])
    additions = Counter(MATRIX_CONNECTIVITY_ROUTE_ADDITIONS[side])
    signatures = Counter(_route_signature(item) for item in board.GetTracks())
    if signatures & additions == additions and not signatures & removals:
        return {"removed": 0, "added": 0}
    if signatures & removals != removals:
        raise RuntimeError(f"{side} matrix-connectivity detour precondition failed")
    remaining = removals.copy()
    removed = 0
    for item in list(board.GetTracks()):
        signature = _route_signature(item)
        if remaining[signature] <= 0:
            continue
        board.Delete(item)
        remaining[signature] -= 1
        removed += 1
    if any(remaining.values()):
        raise RuntimeError(f"{side} matrix-connectivity detour removal was incomplete")
    for spec in MATRIX_CONNECTIVITY_ROUTE_ADDITIONS[side]:
        _add_route_spec(board, spec)
    return {
        "removed": removed,
        "added": len(MATRIX_CONNECTIVITY_ROUTE_ADDITIONS[side]),
    }


def replace_v2_usb_under_reset_routes(
    board: pcbnew.BOARD,
    side: str,
) -> dict[str, int]:
    """Replace controller-service RST/GND/BAT+ fanout for CON-ARCH-007."""

    existing = [
        item
        for item in board.GetTracks()
        if item.GetNetname() in {"RST", "GND", "BAT+", "NN_B+"}
    ]
    for item in existing:
        board.Delete(item)
    tact = board.FindFootprintByReference("SW_RST1")
    battery = board.FindFootprintByReference("J_BAT1")
    power = board.FindFootprintByReference("SW_PWR1")
    controller = board.FindFootprintByReference("U1")
    if any(item is None for item in (tact, battery, power, controller)):
        raise RuntimeError(f"{side} controller-service route is missing a required footprint")
    controller_pads = {
        pad.GetNumber(): gen.to_mm_vec(pad.GetPosition())
        for pad in controller.Pads()
    }
    nets = {
        name: board.FindNet(name)
        for name in ("RST", "GND", "BAT+", "NN_B+")
    }
    if any(net is None for net in nets.values()):
        raise RuntimeError(f"{side} controller-service route is missing a required net")
    gen.connect_tact_to_controller(board, nets, tact, controller_pads, side)
    gen.connect_x3_v2_power_service(
        board,
        nets,
        battery,
        power,
        controller_pads,
        side,
    )
    added = len(
        [
            item
            for item in board.GetTracks()
            if item.GetNetname() in {"RST", "GND", "BAT+", "NN_B+"}
        ]
    )
    return {
        "removed": len(existing),
        "added": added,
    }


def restore_v2_controller_service_placements(
    board: pcbnew.BOARD,
    side: str,
) -> None:
    """Restore placements that the historical controller-r3 SES carries."""

    expected = gen.X3_V2_CONTROLLER_SERVICE_POSITIONS_MM[side]
    rotations = gen.X3_V2_CONTROLLER_SERVICE_ROTATIONS_DEGREES[side]
    for reference, key in (
        ("BAT1", "battery"),
        ("J_BAT1", "j_bat"),
        ("SW_PWR1", "power"),
        ("SW_RST1", "reset"),
        ("BAT_LEAD_SLOT1", "battery_slot"),
    ):
        footprint = board.FindFootprintByReference(reference)
        if footprint is None:
            raise RuntimeError(f"missing controller service footprint {reference}")
        x, y = expected[key]
        footprint.SetPosition(
            pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))
        )
        footprint.SetOrientationDegrees(rotations[reference])


def apply_m1_4_driver_route_detours(
    board: pcbnew.BOARD,
    side: str,
) -> dict[str, int]:
    """Apply only the reviewed route detours needed by the final 3 mm driver."""
    if side not in M1_4_DRIVER_ROUTE_REMOVALS:
        raise RuntimeError(f"unsupported M1.4 driver detour side {side!r}")
    signatures = Counter(_route_signature(item) for item in board.GetTracks())
    removals = Counter(M1_4_DRIVER_ROUTE_REMOVALS[side])
    additions = Counter(M1_4_DRIVER_ROUTE_ADDITIONS[side])
    has_old = signatures & removals == removals
    has_new = signatures & additions == additions
    if has_new and not has_old:
        return {"removed": 0, "added": 0}
    if not has_old or has_new:
        raise RuntimeError(f"reviewed {side} M1.4 driver detour precondition failed")

    remaining = removals.copy()
    removed = 0
    for item in list(board.GetTracks()):
        signature = _route_signature(item)
        if remaining[signature] <= 0:
            continue
        board.Delete(item)
        remaining[signature] -= 1
        removed += 1
    if any(remaining.values()):
        raise RuntimeError(f"reviewed {side} M1.4 driver detour removal was incomplete")
    for spec in M1_4_DRIVER_ROUTE_ADDITIONS[side]:
        _add_route_spec(board, spec)
    updated = Counter(_route_signature(item) for item in board.GetTracks())
    if updated & removals or updated & additions != additions:
        raise RuntimeError(f"reviewed {side} M1.4 driver detour was incomplete")
    return {"removed": removed, "added": len(M1_4_DRIVER_ROUTE_ADDITIONS[side])}


def apply_p1_rounded_head_route_detours(
    board: pcbnew.BOARD,
    side: str,
) -> dict[str, int]:
    """Apply only the reviewed P1 detours required by the rounded 3 mm head."""
    if side not in P1_ROUNDED_HEAD_ROUTE_REMOVALS:
        raise RuntimeError(f"unsupported P1 rounded-head detour side {side!r}")
    signatures = Counter(_route_signature(item) for item in board.GetTracks())
    removals = Counter(P1_ROUNDED_HEAD_ROUTE_REMOVALS[side])
    additions = Counter(P1_ROUNDED_HEAD_ROUTE_ADDITIONS[side])
    has_old = signatures & removals == removals
    has_new = signatures & additions == additions
    if has_new and not has_old:
        return {"removed": 0, "added": 0}
    if not has_old or has_new:
        raise RuntimeError(
            f"reviewed {side} P1 rounded-head detour precondition failed"
        )

    remaining = removals.copy()
    removed = 0
    for item in list(board.GetTracks()):
        signature = _route_signature(item)
        if remaining[signature] <= 0:
            continue
        board.Delete(item)
        remaining[signature] -= 1
        removed += 1
    if any(remaining.values()):
        raise RuntimeError(
            f"reviewed {side} P1 rounded-head detour removal was incomplete"
        )
    for spec in P1_ROUNDED_HEAD_ROUTE_ADDITIONS[side]:
        _add_route_spec(board, spec)
    updated = Counter(_route_signature(item) for item in board.GetTracks())
    if updated & removals or updated & additions != additions:
        raise RuntimeError(
            f"reviewed {side} P1 rounded-head detour was incomplete"
        )
    return {
        "removed": removed,
        "added": len(P1_ROUNDED_HEAD_ROUTE_ADDITIONS[side]),
    }


def apply_sod123_hand_solder_route_detour(
    board: pcbnew.BOARD,
    side: str,
) -> dict[str, int]:
    """Keep unrelated routing outside the controlled SOD-123 fillet envelope."""
    if side not in SOD123_HAND_SOLDER_ROUTE_REMOVALS:
        raise RuntimeError(f"unsupported SOD-123 hand-solder detour side {side!r}")
    removals = Counter(SOD123_HAND_SOLDER_ROUTE_REMOVALS[side])
    additions = Counter(SOD123_HAND_SOLDER_ROUTE_ADDITIONS[side])
    if not removals:
        return {"removed": 0, "added": 0}
    signatures = Counter(_route_signature(item) for item in board.GetTracks())
    if signatures & additions == additions and not signatures & removals:
        return {"removed": 0, "added": 0}
    if signatures & removals != removals or signatures & additions:
        raise RuntimeError(f"reviewed {side} SOD-123 detour precondition failed")
    remaining = removals.copy()
    removed = 0
    for item in list(board.GetTracks()):
        signature = _route_signature(item)
        if remaining[signature] <= 0:
            continue
        board.Delete(item)
        remaining[signature] -= 1
        removed += 1
    if any(remaining.values()):
        raise RuntimeError(f"reviewed {side} SOD-123 detour removal was incomplete")
    for spec in SOD123_HAND_SOLDER_ROUTE_ADDITIONS[side]:
        _add_route_spec(board, spec)
    return {"removed": removed, "added": len(SOD123_HAND_SOLDER_ROUTE_ADDITIONS[side])}


def export_current_mh_trackless_dsn(
    board: pcbnew.BOARD,
    output_path: Path,
    side: str,
) -> None:
    """Export the deterministic compact-controller routing input from a trackless board."""
    expected_holes = 8 if side == "left" else 9 if side == "right" else None
    if expected_holes is None:
        raise RuntimeError(f"unsupported current-MH DSN side {side!r}")
    holes = [
        footprint
        for footprint in board.GetFootprints()
        if re.fullmatch(r"MH\d+", footprint.GetReference())
    ]
    if len(holes) != expected_holes:
        raise RuntimeError(
            f"{side} current-MH DSN requires {expected_holes} mounting holes, found {len(holes)}"
        )
    if list(board.GetTracks()):
        raise RuntimeError(f"{side} current-MH DSN export requires a trackless board")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not pcbnew.ExportSpecctraDSN(board, str(output_path)):
        raise RuntimeError(f"failed to export current-MH DSN {output_path}")
    text = output_path.read_text(encoding="utf-8")
    canonical_name = f"kc2_{side}-x3-v2-70-1n4148w-p3.dsn"
    normalized, count = re.subn(
        r'^\(pcb\s+(?:"[^"]*"|[^\r\n]+)',
        f'(pcb "{canonical_name}"',
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError(f"failed to normalize current-MH DSN identity {output_path}")
    output_path.write_text(normalized, encoding="utf-8", newline="\n")


def _has_exact_reviewed_es1b_route(board: pcbnew.BOARD, side: str) -> bool:
    signatures = Counter(_route_signature(item) for item in board.GetTracks())
    return (
        sum(signatures.values()) == ES1B_ROUTE_ITEM_COUNTS[side]
        and _route_counter_digest(signatures) == ES1B_ROUTE_SHA256[side]
        and _matrix_pads_are_fully_connected(board, side)
    )


def _has_exact_reviewed_controller_compact_route(
    board: pcbnew.BOARD,
    side: str,
) -> bool:
    signatures = Counter(_route_signature(item) for item in board.GetTracks())
    expected_pad_nets = {
        ("U1", "RAW"): "NN_B+",
        ("U1", "GND_C"): "GND",
        ("J_BAT1", "1"): "BAT+",
        ("J_BAT1", "2"): "GND",
        ("SW_PWR1", "1"): "BAT+",
        ("SW_PWR1", "2"): "NN_B+",
        ("SW_PWR1", "3"): "",
        ("SW_RST1", "1"): "RST",
        ("SW_RST1", "2"): "GND",
    }
    for (reference, number), net_name in expected_pad_nets.items():
        footprint = board.FindFootprintByReference(reference)
        if footprint is None:
            return False
        pad = next((item for item in footprint.Pads() if item.GetNumber() == number), None)
        if pad is None or pad.GetNetname() != net_name:
            return False
    routed_service_nets = {
        item.GetNetname()
        for item in board.GetTracks()
        if item.GetNetname() in {"RST", "GND", "BAT+", "NN_B+"}
    }
    return (
        sum(signatures.values()) == CONTROLLER_COMPACT_ROUTE_ITEM_COUNTS[side]
        and _route_counter_digest(signatures) == CONTROLLER_COMPACT_ROUTE_SHA256[side]
        and routed_service_nets == {"RST", "GND", "BAT+", "NN_B+"}
        and _has_exact_current_mounting_geometry(board, side)
        and _matrix_pads_are_fully_connected(board, side)
        and _controller_service_pads_are_physically_connected(board)
    )


def _controller_service_pads_are_physically_connected(
    board: pcbnew.BOARD,
) -> bool:
    endpoint_groups = {
        "RST": (("SW_RST1", "1"), ("U1", "RST")),
        "GND": (("J_BAT1", "2"), ("SW_RST1", "2"), ("U1", "GND_C")),
        "BAT+": (("J_BAT1", "1"), ("SW_PWR1", "1")),
        "NN_B+": (("SW_PWR1", "2"), ("U1", "RAW")),
    }
    tracks_by_net: dict[str, set[str]] = {
        net_name: {
            item.m_Uuid.AsString()
            for item in board.GetTracks()
            if item.GetNetname() == net_name
        }
        for net_name in endpoint_groups
    }
    if any(not track_ids for track_ids in tracks_by_net.values()):
        return False

    pads_by_net: dict[str, list[pcbnew.PAD]] = {}
    for net_name, endpoints in endpoint_groups.items():
        pads: list[pcbnew.PAD] = []
        for reference, number in endpoints:
            footprint = board.FindFootprintByReference(reference)
            if footprint is None:
                return False
            pad = next(
                (item for item in footprint.Pads() if item.GetNumber() == number),
                None,
            )
            if pad is None or pad.GetNetname() != net_name:
                return False
            pads.append(pad)
        pads_by_net[net_name] = pads

    board.BuildConnectivity()
    connectivity = board.GetConnectivity()
    for net_name, pads in pads_by_net.items():
        connected = {
            item.m_Uuid.AsString()
            for item in connectivity.GetConnectedItems(pads[0])
        }
        connected.add(pads[0].m_Uuid.AsString())
        if any(pad.m_Uuid.AsString() not in connected for pad in pads):
            return False
        for pad in pads:
            pad_connected = {
                item.m_Uuid.AsString()
                for item in connectivity.GetConnectedItems(pad)
            }
            if not pad_connected & tracks_by_net[net_name]:
                return False
    return True


def _verify_controller_compact_service_geometry(
    board: pcbnew.BOARD,
    side: str,
) -> None:
    if side not in {"left", "right"}:
        raise RuntimeError(f"unsupported controller-compaction route side {side!r}")
    expected = gen.X3_V2_CONTROLLER_SERVICE_POSITIONS_MM[side]
    service_footprints = (
        ("U1", "u1"),
        ("BAT1", "battery"),
        ("J_BAT1", "j_bat"),
        ("SW_PWR1", "power"),
        ("BAT_LEAD_SLOT1", "battery_slot"),
        ("SW_RST1", "reset"),
    )
    for reference, key in service_footprints:
        footprint = board.FindFootprintByReference(reference)
        if footprint is None:
            raise RuntimeError(
                f"controller service geometry mismatch: missing {side} {reference}"
            )
        position = footprint.GetPosition()
        actual = (
            round(pcbnew.ToMM(position.x), 4),
            round(pcbnew.ToMM(position.y), 4),
        )
        if actual != expected[key]:
            raise RuntimeError(
                "controller service geometry mismatch: "
                f"{side} {reference} expected {expected[key]}, found {actual}"
            )
    expected_rotations = gen.X3_V2_CONTROLLER_SERVICE_ROTATIONS_DEGREES[side]
    for reference, _key in service_footprints:
        footprint = board.FindFootprintByReference(reference)
        rotation = round(footprint.GetOrientation().AsDegrees() % 360.0, 3)
        expected_rotation = expected_rotations[reference]
        if rotation != expected_rotation:
            raise RuntimeError(
                "controller service geometry mismatch: "
                f"{side} {reference} expected R{expected_rotation:g}, "
                f"found R{rotation:g}"
            )


def import_reviewed_controller_compact_session(
    board: pcbnew.BOARD,
    session_path: Path,
    side: str,
) -> dict[str, int]:
    """Import the reviewed compact-controller route and exact edge-safe cleanup."""
    _verify_controller_compact_service_geometry(board, side)
    existing = list(board.GetTracks())
    if existing:
        if not _has_exact_reviewed_controller_compact_route(board, side):
            raise RuntimeError(
                f"refusing a nonempty board that is not the exact reviewed {side} "
                "controller-compaction route"
            )
        return {
            "imported_track_and_via_items": 0,
            "reviewed_items_removed": 0,
            "reviewed_items_added": 0,
            "final_track_and_via_items": len(existing),
            "diode_pads_centered": (31 if side == "left" else 39) * 2,
            "route_endpoints_updated": 0,
        }
    if not session_path.is_file():
        raise RuntimeError(
            f"missing reviewed {side} controller-compaction session: {session_path}"
        )
    if not pcbnew.ImportSpecctraSES(board, str(session_path)):
        raise RuntimeError(
            f"failed to import reviewed {side} controller-compaction session: "
            f"{session_path}"
        )
    imported = list(board.GetTracks())
    imported_signatures = Counter(_route_signature(item) for item in imported)
    expected_count = CONTROLLER_COMPACT_IMPORTED_ITEM_COUNTS[side]
    if len(imported) != expected_count:
        raise RuntimeError(
            f"reviewed {side} controller-compaction session item count changed: "
            f"expected {expected_count}, found {len(imported)}"
        )
    imported_digest = _route_counter_digest(imported_signatures)
    expected_imported_digest = CONTROLLER_COMPACT_IMPORTED_ROUTE_SHA256[side]
    if imported_digest != expected_imported_digest:
        raise RuntimeError(
            f"reviewed {side} controller-compaction imported route digest changed: "
            f"expected {expected_imported_digest}, found {imported_digest}"
        )

    restore_v2_controller_service_placements(board, side)
    if not _has_exact_current_mounting_geometry(board, side):
        raise RuntimeError(
            f"reviewed {side} controller-compaction session moved the P3 mounting pattern"
        )

    expected_removals = Counter(CONTROLLER_COMPACT_ROUTE_REMOVALS[side])
    if imported_signatures & expected_removals != expected_removals:
        raise RuntimeError(
            f"reviewed {side} controller-compaction cleanup precondition failed"
        )

    remaining = expected_removals.copy()
    removed = 0
    for item in list(board.GetTracks()):
        signature = _route_signature(item)
        if remaining[signature] <= 0:
            continue
        board.Delete(item)
        remaining[signature] -= 1
        removed += 1
    if any(remaining.values()):
        raise RuntimeError(
            f"reviewed {side} controller-compaction removal was incomplete"
        )
    for spec in CONTROLLER_COMPACT_ROUTE_ADDITIONS[side]:
        _add_route_spec(board, spec)
    reset_route = replace_v2_usb_under_reset_routes(board, side)
    matrix_detours = apply_matrix_service_detours(board, side)
    connectivity_detours = apply_matrix_connectivity_detours(board, side)
    rounded_head_detours = apply_p1_rounded_head_route_detours(board, side)
    diode_clearance_detour = apply_sod123_hand_solder_route_detour(board, side)
    diode_route_centres = center_1n4148w_diode_route_endpoints(board, side)
    if not _has_exact_reviewed_controller_compact_route(board, side):
        raise RuntimeError(
            f"reviewed {side} controller-compaction session did not reconstruct "
            "the exact route"
        )
    return {
        "imported_track_and_via_items": len(imported),
        "reviewed_items_removed": (
            removed
            + reset_route["removed"]
            + matrix_detours["removed"]
            + connectivity_detours["removed"]
            + rounded_head_detours["removed"]
            + diode_clearance_detour["removed"]
        ),
        "reviewed_items_added": (
            len(CONTROLLER_COMPACT_ROUTE_ADDITIONS[side])
            + reset_route["added"]
            + matrix_detours["added"]
            + connectivity_detours["added"]
            + rounded_head_detours["added"]
            + diode_clearance_detour["added"]
        ),
        "final_track_and_via_items": len(list(board.GetTracks())),
        **diode_route_centres,
    }


def import_reviewed_es1b_session(
    board: pcbnew.BOARD,
    session_path: Path,
    side: str,
) -> dict[str, int]:
    """Reconstruct the exact ES1B route and apply reviewed solder-envelope detours."""
    from tools.verify_kc2_x3_v2 import verify_switch_layout_against_generator

    if side not in {"left", "right"}:
        raise RuntimeError(f"unsupported ES1B route side {side!r}")
    expected_switches = 31 if side == "left" else 39
    switches = sorted(
        (
            footprint
            for footprint in board.GetFootprints()
            if footprint.GetReference().startswith("SW")
            and footprint.GetReference()[2:].isdigit()
        ),
        key=lambda footprint: int(footprint.GetReference()[2:]),
    )
    if len(switches) != expected_switches:
        raise RuntimeError(
            f"reviewed {side} ES1B route requires {expected_switches} switches, "
            f"found {len(switches)}"
        )
    layout_errors, _maximum_error = verify_switch_layout_against_generator(switches)
    if layout_errors:
        raise RuntimeError(
            f"reviewed {side} ES1B switch geometry mismatch: {layout_errors[0]}"
        )

    existing = list(board.GetTracks())
    if existing:
        if not _has_exact_reviewed_es1b_route(board, side):
            raise RuntimeError(
                f"refusing a nonempty board that is not the exact reviewed {side} ES1B route"
            )
        return {
            "imported_track_and_via_items": 0,
            "reviewed_items_removed": 0,
            "reviewed_items_added": 0,
            "final_track_and_via_items": len(existing),
        }
    if not session_path.is_file():
        raise RuntimeError(f"missing reviewed {side} ES1B route session: {session_path}")
    if not pcbnew.ImportSpecctraSES(board, str(session_path)):
        raise RuntimeError(f"failed to import reviewed {side} ES1B route session: {session_path}")

    imported = list(board.GetTracks())
    imported_signatures = Counter(_route_signature(item) for item in imported)
    expected_removals = Counter(ES1B_ROUTE_REMOVALS[side])
    if len(imported) != ES1B_IMPORTED_ITEM_COUNTS[side]:
        raise RuntimeError(
            f"reviewed {side} ES1B session item count changed: expected "
            f"{ES1B_IMPORTED_ITEM_COUNTS[side]}, found {len(imported)}"
        )
    if imported_signatures & expected_removals != expected_removals:
        raise RuntimeError(f"reviewed {side} ES1B removal precondition failed")

    remaining = expected_removals.copy()
    removed = 0
    for item in list(board.GetTracks()):
        signature = _route_signature(item)
        if remaining[signature] <= 0:
            continue
        board.Delete(item)
        remaining[signature] -= 1
        removed += 1
    if any(remaining.values()):
        raise RuntimeError(f"reviewed {side} ES1B route removal was incomplete")
    for spec in ES1B_ROUTE_ADDITIONS[side]:
        _add_route_spec(board, spec)
    driver_detour = apply_m1_4_driver_route_detours(board, side)
    if not _has_exact_reviewed_es1b_route(board, side):
        raise RuntimeError(f"reviewed {side} ES1B session did not reconstruct the exact route")
    return {
        "imported_track_and_via_items": len(imported),
        "reviewed_items_removed": removed + driver_detour["removed"],
        "reviewed_items_added": len(ES1B_ROUTE_ADDITIONS[side]) + driver_detour["added"],
        "final_track_and_via_items": len(list(board.GetTracks())),
    }


def import_reviewed_left_v5_session(
    board: pcbnew.BOARD,
    session_path: Path,
) -> dict[str, int]:
    """Import the exact 31-key v5 SES once and reject stale or partial geometry."""
    from tools.verify_kc2_x3_v2 import verify_switch_layout_against_generator

    switches = sorted(
        (
            footprint
            for footprint in board.GetFootprints()
            if footprint.GetReference().startswith("SW")
            and footprint.GetReference()[2:].isdigit()
        ),
        key=lambda footprint: int(footprint.GetReference()[2:]),
    )
    if len(switches) != 31:
        raise RuntimeError(f"reviewed left v5 route requires 31 switches, found {len(switches)}")
    layout_errors, _maximum_error = verify_switch_layout_against_generator(switches)
    if layout_errors:
        raise RuntimeError(f"reviewed left v5 switch geometry mismatch: {layout_errors[0]}")

    before = len(list(board.GetTracks()))
    if before:
        if not _matrix_pads_are_fully_connected(board, "left"):
            raise RuntimeError("refusing to replace a nonempty but incomplete left route")
        return {"track_and_via_items_added": 0}
    if not session_path.is_file():
        raise RuntimeError(f"missing reviewed left v5 route session: {session_path}")
    if not pcbnew.ImportSpecctraSES(board, str(session_path)):
        raise RuntimeError(f"failed to import reviewed left v5 route session: {session_path}")
    after = len(list(board.GetTracks()))
    if after <= before or not _matrix_pads_are_fully_connected(board, "left"):
        raise RuntimeError("reviewed left v5 route session did not connect the complete matrix")
    return {"track_and_via_items_added": after - before}


def import_reviewed_right_r12_session(
    board: pcbnew.BOARD,
    session_path: Path,
) -> dict[str, int]:
    """Import r12 and remove only its reviewed 18-item duplicate/dangling residue."""
    from tools.verify_kc2_x3_v2 import verify_switch_layout_against_generator

    switches = sorted(
        (
            footprint
            for footprint in board.GetFootprints()
            if footprint.GetReference().startswith("SW")
            and footprint.GetReference()[2:].isdigit()
        ),
        key=lambda footprint: int(footprint.GetReference()[2:]),
    )
    if len(switches) != 39:
        raise RuntimeError(f"reviewed right r12 route requires 39 switches, found {len(switches)}")
    layout_errors, _maximum_error = verify_switch_layout_against_generator(switches)
    if layout_errors:
        raise RuntimeError(f"reviewed right r12 switch geometry mismatch: {layout_errors[0]}")

    existing = list(board.GetTracks())
    if existing:
        if not _has_exact_reviewed_right_route(board):
            raise RuntimeError("refusing a nonempty board that is not the exact reviewed right route")
        return {
            "imported_track_and_via_items": 0,
            "reviewed_extras_removed": 0,
            "final_track_and_via_items": len(existing),
        }
    if not session_path.is_file():
        raise RuntimeError(f"missing reviewed right r12 route session: {session_path}")
    if not pcbnew.ImportSpecctraSES(board, str(session_path)):
        raise RuntimeError(f"failed to import reviewed right r12 route session: {session_path}")

    imported = list(board.GetTracks())
    expected_extras = Counter(RIGHT_R12_IMPORTED_ONLY_ROUTE)
    actual_signatures = Counter(_route_signature(item) for item in imported)
    if sum(actual_signatures.values()) != RIGHT_R12_FINAL_ROUTE_ITEM_COUNT + sum(expected_extras.values()):
        raise RuntimeError(
            "reviewed right r12 session item count changed: "
            f"expected {RIGHT_R12_FINAL_ROUTE_ITEM_COUNT + sum(expected_extras.values())}, "
            f"found {sum(actual_signatures.values())}"
        )
    if actual_signatures & expected_extras != expected_extras:
        raise RuntimeError("reviewed right r12 imported-only signature precondition failed")

    remaining = expected_extras.copy()
    removed = 0
    for item in list(board.GetTracks()):
        signature = _route_signature(item)
        if remaining[signature] <= 0:
            continue
        board.Delete(item)
        remaining[signature] -= 1
        removed += 1
    if any(remaining.values()) or removed != len(RIGHT_R12_IMPORTED_ONLY_ROUTE):
        raise RuntimeError("reviewed right r12 imported-only removal was incomplete")
    if not _has_exact_reviewed_right_route(board):
        raise RuntimeError("reviewed right r12 session did not reconstruct the exact committed route")
    return {
        "imported_track_and_via_items": len(imported),
        "reviewed_extras_removed": removed,
        "final_track_and_via_items": len(list(board.GetTracks())),
    }


def restore_left_controller_columns(board: pcbnew.BOARD) -> dict[str, int]:
    """Restore the reviewed L_COL0/L_COL1 fanout after the diode-edge autoroute."""

    for (reference, number), expected in LEFT_CONTROLLER_COLUMN_ANCHORS_MM.items():
        footprint = board.FindFootprintByReference(reference)
        if footprint is None:
            raise RuntimeError(f"missing reviewed route anchor {reference}")
        pad = next((candidate for candidate in footprint.Pads() if candidate.GetNumber() == number), None)
        if pad is None:
            raise RuntimeError(f"missing reviewed route anchor {reference}.{number}")
        position = pad.GetPosition()
        actual = (round(pcbnew.ToMM(position.x), 4), round(pcbnew.ToMM(position.y), 4))
        if actual != expected:
            raise RuntimeError(
                f"reviewed route anchor {reference}.{number} moved: expected {expected}, found {actual}"
            )

    existing = [
        item for item in board.GetTracks() if item.GetNetname() in LEFT_CONTROLLER_COLUMN_NETS
    ]
    if Counter(_route_signature(item) for item in existing) == Counter(LEFT_CONTROLLER_COLUMN_ROUTE):
        return {"track_and_via_items_removed": 0, "track_and_via_items_added": 0}

    for item in existing:
        board.Delete(item)
    for spec in LEFT_CONTROLLER_COLUMN_ROUTE:
        kind, net_name, *values = spec
        net = board.FindNet(net_name)
        if net is None:
            raise RuntimeError(f"missing reviewed route net {net_name}")
        if kind == "via":
            x, y, diameter, drill = values
            item = pcbnew.PCB_VIA(board)
            item.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
            item.SetWidth(pcbnew.FromMM(diameter))
            item.SetDrill(pcbnew.FromMM(drill))
            item.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        else:
            layer_name, x1, y1, x2, y2, width = values
            item = pcbnew.PCB_TRACK(board)
            item.SetLayer(board.GetLayerID(layer_name))
            item.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(x1), pcbnew.FromMM(y1)))
            item.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(x2), pcbnew.FromMM(y2)))
            item.SetWidth(pcbnew.FromMM(width))
        item.SetNet(net)
        board.Add(item)
    return {
        "track_and_via_items_removed": len(existing),
        "track_and_via_items_added": len(LEFT_CONTROLLER_COLUMN_ROUTE),
    }


def load_reviewed_drc(path: Path) -> dict[str, object]:
    report = json.loads(path.read_text(encoding="utf-8"))
    unconnected = report.get("unconnected_items", [])
    if unconnected:
        raise RuntimeError(f"Refusing cleanup with {len(unconnected)} unconnected items")
    violations = report.get("violations", [])
    hard_errors = [item for item in violations if item.get("severity") == "error"]
    if hard_errors:
        raise RuntimeError(f"Refusing cleanup with {len(hard_errors)} DRC errors")
    unexpected = sorted(
        {
            str(item.get("type"))
            for item in violations
            if item.get("type") not in ALLOWED_WARNING_TYPES
        }
    )
    if unexpected:
        raise RuntimeError(f"Refusing unreviewed DRC warning classes: {unexpected}")
    return report


def move_v2_key_labels_to_fab(board: pcbnew.BOARD, side: str) -> int:
    keys = gen.make_left_keys_x3_v2() if side == "left" else gen.make_right_keys_x3_v2()
    labels = {key.label for key in keys}
    changed = 0
    for drawing in board.GetDrawings():
        if not isinstance(drawing, pcbnew.PCB_TEXT):
            continue
        if drawing.GetLayer() != pcbnew.F_SilkS or drawing.GetText() not in labels:
            continue
        if pcbnew.ToMM(drawing.GetPosition().y) < 65.0:
            continue
        drawing.SetLayer(pcbnew.F_Fab)
        changed += 1
    return changed


def apply_reviewed_cleanup(board: pcbnew.BOARD, report: dict[str, object], side: str) -> dict[str, int]:
    violations = report.get("violations", [])
    dangling_uuids = {
        str(item["uuid"])
        for violation in violations
        if violation.get("type") == "track_dangling"
        for item in violation.get("items", [])
    }
    silk_item_uuids = {
        str(item["uuid"])
        for violation in violations
        if violation.get("type") in {"silk_edge_clearance", "silk_over_copper"}
        for item in violation.get("items", [])
    }

    removed = 0
    for track in list(board.GetTracks()):
        if track.m_Uuid.AsString() in dangling_uuids:
            board.Delete(track)
            removed += 1

    silk_moved = 0
    for drawing in board.GetDrawings():
        if not isinstance(drawing, pcbnew.PCB_TEXT):
            continue
        if drawing.m_Uuid.AsString() not in silk_item_uuids:
            continue
        if drawing.GetLayer() == pcbnew.F_SilkS:
            drawing.SetLayer(pcbnew.F_Fab)
            silk_moved += 1
        elif drawing.GetLayer() == pcbnew.B_SilkS:
            drawing.SetLayer(pcbnew.B_Fab)
            silk_moved += 1

    return {
        "dangling_tracks_removed": removed,
        "warning_silkscreen_texts_moved_to_fab": silk_moved,
        "v2_key_labels_moved_to_fab": move_v2_key_labels_to_fab(board, side),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply reviewed routing repair and non-electrical cleanup to KC2 X3 V2."
    )
    parser.add_argument("board", type=Path)
    parser.add_argument("--drc", type=Path)
    parser.add_argument("--restore-left-controller-columns", action="store_true")
    parser.add_argument("--import-left-v5-session", type=Path)
    parser.add_argument("--import-right-r12-session", type=Path)
    parser.add_argument("--import-es1b-session", type=Path)
    parser.add_argument("--import-controller-compact-session", type=Path)
    args = parser.parse_args()
    board = pcbnew.LoadBoard(str(args.board))
    side = "left" if "left" in args.board.name.lower() else "right"
    result: dict[str, object] = {}
    if args.import_controller_compact_session:
        result["controller_compact_session"] = import_reviewed_controller_compact_session(
            board,
            args.import_controller_compact_session,
            side,
        )
    if args.import_es1b_session:
        result["es1b_session"] = import_reviewed_es1b_session(
            board,
            args.import_es1b_session,
            side,
        )
    if args.import_left_v5_session:
        if side != "left":
            raise RuntimeError("left v5 session cannot be applied to a right board")
        result["left_v5_session"] = import_reviewed_left_v5_session(
            board,
            args.import_left_v5_session,
        )
    if args.import_right_r12_session:
        if side != "right":
            raise RuntimeError("right r12 session cannot be applied to a left board")
        result["right_r12_session"] = import_reviewed_right_r12_session(
            board,
            args.import_right_r12_session,
        )
    if args.restore_left_controller_columns:
        if side != "left":
            raise RuntimeError("left controller-column repair cannot be applied to a right board")
        result["left_controller_columns"] = restore_left_controller_columns(board)
    if args.drc:
        report = load_reviewed_drc(args.drc)
        result["reviewed_cleanup"] = apply_reviewed_cleanup(board, report, side)
    if not result:
        parser.error(
            "provide --drc, --restore-left-controller-columns, --import-left-v5-session, "
            "--import-right-r12-session, --import-es1b-session, and/or "
            "--import-controller-compact-session"
        )
    pcbnew.SaveBoard(str(args.board), board)
    print(f"{side}: {result}")


if __name__ == "__main__":
    main()
