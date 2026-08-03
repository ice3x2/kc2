from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Sequence

import pcbnew


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
    "npth_inside_courtyard",
    "pth_inside_courtyard",
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


def analyze_v2_board(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(path)
    board = pcbnew.LoadBoard(str(path))
    switches = matrix_footprints(board, "SW")
    diodes = matrix_footprints(board, "D")
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
        "stabilizer_refs": sorted(
            footprint.GetReference()
            for footprint in footprints
            if footprint.GetReference().startswith("STAB")
        ),
        "registration_hole_count": len(registration_holes),
        "registration_hole_errors": registration_hole_errors,
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

    board_reports: dict[str, object] = {}
    connectivity_errors: dict[str, list[str]] = {}
    for board_path in board_paths:
        side = detect_side(board_path)
        expected_keys = 32 if side == "left" else 45
        report = analyze_v2_board(board_path)
        board_reports[side] = report
        checks = {
            "switch count": report["switch_count"] == expected_keys,
            "diode count": report["diode_count"] == expected_keys,
            "owned switch footprint": report["switch_footprint_names"]
            == {"SW_Choc_V2_Socket_MX_THT"},
            "alternate contact nets": not report["alternate_contact_net_mismatches"],
            "no stabilizers": not report["stabilizer_refs"],
            "nine registration holes": report["registration_hole_count"] == 9,
            "copper-free registration holes": not report["registration_hole_errors"],
            "visible registration labels": report["registration_label_layers"]
            == {f"H{index}": "B.Silkscreen" for index in range(1, 10)},
            "no carrier power pads": not report["carrier_power_pad_refs"],
            "one battery lead slot": report["battery_lead_slot_count"] == 1,
            "copper-free battery lead slot": not report["battery_lead_slot_errors"],
            "battery slot on USB/B+ side": report["battery_lead_slot_on_usb_side"],
            "no carrier power nets": not report["forbidden_carrier_power_nets"],
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
