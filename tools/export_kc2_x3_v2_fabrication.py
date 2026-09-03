from __future__ import annotations

import json
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

if __package__:
    from tools.canonical_hash import HASH_POLICY, sha256_file
    from tools.kc2_x3_v2_output_geometry import (
        REQUIREMENT_IDS,
        bom_csv_bytes,
        build_board_bom,
        build_jlcpcb_pcba_quote,
        jlcpcb_pcba_bom_csv_bytes,
        jlcpcb_pcba_cpl_csv_bytes,
        parse_board,
    )
else:
    from canonical_hash import HASH_POLICY, sha256_file
    from kc2_x3_v2_output_geometry import (
        REQUIREMENT_IDS,
        bom_csv_bytes,
        build_board_bom,
        build_jlcpcb_pcba_quote,
        jlcpcb_pcba_bom_csv_bytes,
        jlcpcb_pcba_cpl_csv_bytes,
        parse_board,
    )


ROOT = Path(__file__).resolve().parents[1]
FAB_ROOT = ROOT / "hardware" / "kicad" / "fabrication"
KICAD_CLI = Path(r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe")
PRODUCTS = {
    "left": ROOT / "hardware" / "kicad" / "kc2_left" / "kc2_left.kicad_pcb",
    "right": ROOT / "hardware" / "kicad" / "kc2_right" / "kc2_right.kicad_pcb",
    "coupon": ROOT / "hardware" / "kicad" / "coupon" / "kc2_switch_coupon.kicad_pcb",
}
LAYERS = "F.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,Edge.Cuts"
JLCPCB_FABRICATION_SUFFIXES = (
    "-F_Cu.gtl",
    "-B_Cu.gbl",
    "-F_Mask.gts",
    "-B_Mask.gbs",
    "-F_Paste.gtp",
    "-B_Paste.gbp",
    "-F_Silkscreen.gto",
    "-B_Silkscreen.gbo",
    "-Edge_Cuts.gm1",
    "-PTH.drl",
    "-NPTH.drl",
    "-PTH-drl_map.gbr",
    "-NPTH-drl_map.gbr",
    "-drill-report.txt",
    "-job.gbrjob",
)
JLCPCB_PROFILE = {
    "schema": "kc2-x3-v2-jlcpcb-profile-v1",
    "vendor": "JLCPCB",
    "purpose": "prototype_only_pending_physical_evidence",
    "layer_count": 2,
    "material": "FR-4",
    "board_thickness_mm": 1.6,
    "copper_weight_oz": 1.0,
    "surface_finish": "enig",
    "solder_mask_color": "green",
    "silkscreen_color": "white",
    "via_covering": "tented",
    "maximum_tented_via_drill_mm": 0.5,
    "assembly_service": "none_hand_assembly",
    "confirm_production_file": True,
    "order_ready": False,
}
JLCPCB_PCBA_QUOTE_PROFILE = {
    "schema": "kc2-x3-v2-jlcpcb-pcba-quote-v2",
    "vendor": "JLCPCB",
    "purpose": "manual_assembly_reference_and_price_discovery_only_not_order_authorization",
    "assembly_service": "none_hand_assembly",
    "parts_procurement": "user_external_mall_procurement",
    "machine_placement_requested": False,
    "bom_cpl_upload_authorization": False,
    "selected_switch_assembly": "mx_direct_solder",
    "reference_switch_assembly": "choc_socket_alternative_not_selected",
    "switch_assemblies_mutually_exclusive": True,
    "socket_population_for_selected_assembly": False,
    "assembly_side": "bottom",
    "assembled_reference_families": ["D", "SW"],
    "assembled_parts": {
        "D": {
            "manufacturer": "Diodes Incorporated",
            "manufacturer_part_number": "1N4148W-13-F",
            "lcsc_part_number": "C112342",
            "jlcpcb_part_number": "C112342",
            "package": "SOD-123",
        },
        "SW": {
            "manufacturer_part_number": "CPG135001S30",
            "lcsc_part_number": "C5333465",
        },
    },
    "inventory_recheck_required": True,
    "exact_diode_if_unavailable": "dnp_and_hand_assemble_no_substitution",
    "placement_and_orientation_confirmation_required": True,
    "bom_only_1n4148_substitution_allowed": False,
    "board_revision_required_for_1n4148_family": False,
    "order_ready": False,
}


def clear_owned_output(path: Path) -> None:
    resolved = path.resolve()
    if resolved.parent != FAB_ROOT.resolve():
        raise RuntimeError(f"Refusing to clear unexpected fabrication path: {resolved}")
    path.mkdir(parents=True, exist_ok=True)
    for child in path.iterdir():
        if not child.is_file():
            raise RuntimeError(f"Unexpected nested fabrication path: {child}")
        child.unlink()


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def export_product(product: str, board: Path) -> dict[str, object]:
    if not board.is_file():
        raise FileNotFoundError(board)
    output_dir = FAB_ROOT / (f"kc2_{product}" if product in {"left", "right"} else product)
    clear_owned_output(output_dir)
    run(
        [
            str(KICAD_CLI),
            "pcb",
            "export",
            "gerbers",
            "--output",
            str(output_dir),
            "--layers",
            LAYERS,
            "--subtract-soldermask",
            "--check-zones",
            str(board),
        ]
    )
    report_path = output_dir / f"{board.stem}-drill-report.txt"
    run(
        [
            str(KICAD_CLI),
            "pcb",
            "export",
            "drill",
            "--output",
            str(output_dir),
            "--format",
            "excellon",
            "--excellon-units",
            "mm",
            "--excellon-separate-th",
            "--generate-map",
            "--map-format",
            "gerberx2",
            "--generate-report",
            "--report-path",
            str(report_path),
            str(board),
        ]
    )
    source_board_sha256 = sha256_file(board)
    bom: dict[str, str] | None = None
    pcba_quote: dict[str, object] | None = None
    if product in {"left", "right"}:
        bom_json = output_dir / f"{board.stem}-bom.json"
        bom_csv = output_dir / f"{board.stem}-bom.csv"
        bom_payload = build_board_bom(
            product,
            str(board.relative_to(ROOT)),
            source_board_sha256,
            parse_board(board),
        )
        bom_json.write_text(json.dumps(bom_payload, indent=2) + "\n", encoding="utf-8")
        bom_csv.write_bytes(bom_csv_bytes(bom_payload))
        bom = {
            "json": str(bom_json.relative_to(ROOT)),
            "csv": str(bom_csv.relative_to(ROOT)),
        }
        quote_payload = build_jlcpcb_pcba_quote(
            product,
            str(board.relative_to(ROOT)),
            source_board_sha256,
            parse_board(board),
        )
        quote_dir = FAB_ROOT / "pcba_quote"
        quote_dir.mkdir(parents=True, exist_ok=True)
        quote_bom = quote_dir / f"kc2_{product}_jlcpcb_pcba_bom.csv"
        quote_cpl = quote_dir / f"kc2_{product}_jlcpcb_pcba_cpl.csv"
        quote_bom.write_bytes(jlcpcb_pcba_bom_csv_bytes(quote_payload))
        quote_cpl.write_bytes(jlcpcb_pcba_cpl_csv_bytes(quote_payload))
        pcba_quote = {
            "bom": str(quote_bom.relative_to(ROOT)),
            "bom_sha256": sha256_file(quote_bom),
            "cpl": str(quote_cpl.relative_to(ROOT)),
            "cpl_sha256": sha256_file(quote_cpl),
            "diode_count": len(quote_payload["line_items"][0]["designators"]),
            "socket_count": len(quote_payload["line_items"][1]["designators"]),
            "assembled_reference_count": len(quote_payload["placements"]),
            "order_ready": False,
        }
    files = sorted(path for path in output_dir.iterdir() if path.is_file())
    archive = FAB_ROOT / f"kc2_{product}.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as package:
        for path in files:
            package.write(path, arcname=path.name)
    jlcpcb_files = [
        path
        for path in files
        if any(path.name.endswith(suffix) for suffix in JLCPCB_FABRICATION_SUFFIXES)
    ]
    jlcpcb_archive = FAB_ROOT / f"kc2_{product}_jlcpcb.zip"
    with ZipFile(jlcpcb_archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as package:
        for path in jlcpcb_files:
            package.write(path, arcname=path.name)
    result = {
        "board": str(board.relative_to(ROOT)),
        "source_board_sha256": source_board_sha256,
        "key_count": {"left": 31, "right": 39, "coupon": 3}[product],
        "output_dir": str(output_dir.relative_to(ROOT)),
        "archive": str(archive.relative_to(ROOT)),
        "archive_sha256": sha256_file(archive),
        "jlcpcb_archive": str(jlcpcb_archive.relative_to(ROOT)),
        "jlcpcb_archive_sha256": sha256_file(jlcpcb_archive),
        "jlcpcb_entry_count": len(jlcpcb_files),
        "files": [
            {
                "name": path.name,
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in files
        ],
    }
    if bom is not None:
        result["bom"] = bom
    if pcba_quote is not None:
        result["pcba_quote"] = pcba_quote
    return result


def main() -> None:
    if not KICAD_CLI.is_file():
        raise SystemExit(f"KiCad 10 CLI not found: {KICAD_CLI}")
    FAB_ROOT.mkdir(parents=True, exist_ok=True)
    clear_owned_output(FAB_ROOT / "pcba_quote")
    outputs = {
        product: export_product(product, board)
        for product, board in PRODUCTS.items()
    }
    manifest = {
        "requirement_ids": list(REQUIREMENT_IDS),
        "hash_policy": HASH_POLICY,
        "variant": "x3-v2",
        "status": "canonical_not_orderable_pending_physical_evidence",
        "kicad_cli": str(KICAD_CLI),
        "layers": LAYERS.split(","),
        "jlcpcb_profile": JLCPCB_PROFILE,
        "jlcpcb_pcba_quote_profile": JLCPCB_PCBA_QUOTE_PROFILE,
        "products": outputs,
    }
    manifest_path = FAB_ROOT / "kc2_fabrication_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
