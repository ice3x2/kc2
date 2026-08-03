from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V2_ROOT = ROOT / "hardware" / "kicad" / "draft" / "x3-v2"
OUTPUT_DIR = V2_ROOT / "mechanical"
MANIFEST = OUTPUT_DIR / "kc2_x3_v2_mechanical_manifest.json"
DEFAULT_KICAD_CLI = Path(r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe")
BOARDS = {
    "left": V2_ROOT / "kc2_left-x3-v2" / "kc2_left-x3-v2.kicad_pcb",
    "right": V2_ROOT / "kc2_right-x3-v2" / "kc2_right-x3-v2.kicad_pcb",
    "coupon": V2_ROOT / "coupon" / "kc2_x3_v2_switch_coupon.kicad_pcb",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_mechanical(kicad_cli: Path = DEFAULT_KICAD_CLI) -> dict[str, object]:
    if not kicad_cli.is_file():
        raise FileNotFoundError(kicad_cli)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    products: dict[str, object] = {}
    for product, board in BOARDS.items():
        drawings: dict[str, object] = {}
        for face, layer, mirror in (
            ("top", "F.Fab,Edge.Cuts", False),
            ("bottom", "B.Fab,Edge.Cuts", True),
        ):
            output = OUTPUT_DIR / f"{product}_{face}_1to1.pdf"
            command = [
                str(kicad_cli),
                "pcb",
                "export",
                "pdf",
                "--mode-single",
                "--output",
                str(output),
                "--layers",
                layer,
                "--scale",
                "1",
                "--black-and-white",
                "--sketch-pads-on-fab-layers",
            ]
            if mirror:
                command.append("--mirror")
            command.append(str(board))
            subprocess.run(command, cwd=ROOT, check=True)
            drawings[face] = {
                "path": str(output.relative_to(ROOT)),
                "layer": layer.split(",")[0],
                "mirrored": mirror,
                "size": output.stat().st_size,
                "sha256": sha256(output),
            }
        products[product] = {
            "board": str(board.relative_to(ROOT)),
            "drawings": drawings,
        }
    manifest = {
        "requirement": "CON-ARCH-004",
        "status": "draft_not_orderable_pending_physical_coupon",
        "scale": 1.0,
        "units": "mm",
        "kicad_cli": str(kicad_cli),
        "products": products,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Export KC2 X3 V2 1:1 assembly drawings.")
    parser.add_argument("--kicad-cli", type=Path, default=DEFAULT_KICAD_CLI)
    args = parser.parse_args()
    print(json.dumps(export_mechanical(args.kicad_cli), indent=2))


if __name__ == "__main__":
    main()
