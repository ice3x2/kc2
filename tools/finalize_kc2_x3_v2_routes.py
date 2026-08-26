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
CONTROLLER_COMPACT_ROUTE_ITEM_COUNTS = {"left": 543, "right": 706}
CONTROLLER_COMPACT_ROUTE_SHA256 = {
    "left": "9bc9cbf981da8d452b82e52d54a4e8ab3cafcc6121ec578f36a4cf43f3dde19d",
    "right": "83dcc6f764670b379b6c9104d643925cd6eff3c0b16286f12bae14dd1397c67f",
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


def export_current_mh_trackless_dsn(
    board: pcbnew.BOARD,
    output_path: Path,
    side: str,
) -> None:
    """Export the deterministic compact-controller routing input from a trackless board."""
    expected_holes = 8 if side == "left" else 10 if side == "right" else None
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
    canonical_name = f"kc2_{side}-x3-v2-70-es1b-controller-r3.dsn"
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
    return (
        sum(signatures.values()) == CONTROLLER_COMPACT_ROUTE_ITEM_COUNTS[side]
        and _route_counter_digest(signatures) == CONTROLLER_COMPACT_ROUTE_SHA256[side]
        and _matrix_pads_are_fully_connected(board, side)
    )


def _verify_controller_compact_service_geometry(
    board: pcbnew.BOARD,
    side: str,
) -> None:
    if side not in {"left", "right"}:
        raise RuntimeError(f"unsupported controller-compaction route side {side!r}")
    expected = gen.X3_V2_CONTROLLER_SERVICE_POSITIONS_MM[side]
    for reference, key in (
        ("U1", "u1"),
        ("BAT_LEAD_SLOT1", "battery_slot"),
        ("SW_RST1", "reset"),
    ):
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
    reset = board.FindFootprintByReference("SW_RST1")
    rotation = round(reset.GetOrientation().AsDegrees() % 360.0, 3)
    if rotation != gen.X3_V2_RESET_ROTATION_DEGREES:
        raise RuntimeError(
            "controller service geometry mismatch: "
            f"{side} SW_RST1 expected R{gen.X3_V2_RESET_ROTATION_DEGREES:g}, "
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
    expected_removals = Counter(CONTROLLER_COMPACT_ROUTE_REMOVALS[side])
    expected_count = CONTROLLER_COMPACT_IMPORTED_ITEM_COUNTS[side]
    if len(imported) != expected_count:
        raise RuntimeError(
            f"reviewed {side} controller-compaction session item count changed: "
            f"expected {expected_count}, found {len(imported)}"
        )
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
    if not _has_exact_reviewed_controller_compact_route(board, side):
        raise RuntimeError(
            f"reviewed {side} controller-compaction session did not reconstruct "
            "the exact route"
        )
    return {
        "imported_track_and_via_items": len(imported),
        "reviewed_items_removed": removed,
        "reviewed_items_added": len(CONTROLLER_COMPACT_ROUTE_ADDITIONS[side]),
        "final_track_and_via_items": len(list(board.GetTracks())),
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
