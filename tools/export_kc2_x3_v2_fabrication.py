from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
FAB_ROOT = ROOT / "hardware" / "kicad" / "draft" / "x3-v2" / "fabrication"
KICAD_CLI = Path(r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe")
PRODUCTS = {
    "left": ROOT / "hardware" / "kicad" / "draft" / "x3-v2" / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb",
    "right": ROOT / "hardware" / "kicad" / "draft" / "x3-v2" / "kc2_right-x3-v2" / "kc2_right-x3-v2.kicad_pcb",
    "coupon": ROOT / "hardware" / "kicad" / "draft" / "x3-v2" / "coupon" / "kc2_x3_v2_switch_coupon.kicad_pcb",
}
LAYERS = "F.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,Edge.Cuts"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    output_dir = FAB_ROOT / product
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
    files = sorted(path for path in output_dir.iterdir() if path.is_file())
    archive = FAB_ROOT / f"kc2_x3_v2_{product}.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED, compresslevel=9) as package:
        for path in files:
            package.write(path, arcname=path.name)
    return {
        "board": str(board.relative_to(ROOT)),
        "source_board_sha256": sha256(board),
        "key_count": {"left": 31, "right": 39, "coupon": 3}[product],
        "output_dir": str(output_dir.relative_to(ROOT)),
        "archive": str(archive.relative_to(ROOT)),
        "archive_sha256": sha256(archive),
        "files": [
            {
                "name": path.name,
                "size": path.stat().st_size,
                "sha256": sha256(path),
            }
            for path in files
        ],
    }


def main() -> None:
    if not KICAD_CLI.is_file():
        raise SystemExit(f"KiCad 10 CLI not found: {KICAD_CLI}")
    FAB_ROOT.mkdir(parents=True, exist_ok=True)
    outputs = {
        product: export_product(product, board)
        for product, board in PRODUCTS.items()
    }
    manifest = {
        "requirement": "CON-ARCH-004",
        "variant": "x3-v2",
        "status": "draft_not_orderable_pending_physical_coupon",
        "kicad_cli": str(KICAD_CLI),
        "layers": LAYERS.split(","),
        "products": outputs,
    }
    manifest_path = FAB_ROOT / "kc2_x3_v2_fabrication_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
