from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "third_party" / "kc2.3dshapes"
IMMS_MODEL_NAME = "SW_IMMS_12V_BSI10_THT.step"
IMMS_BODY_SIZE_MM = (10.0, 2.5, 6.4)
IMMS_ACTUATOR_TRAVEL_MM = 1.6


def normalize_exported_text(path: Path) -> None:
    """Strip only line-ending spaces/tabs while preserving all newline bytes."""

    original = path.read_bytes()
    normalized = re.sub(rb"[ \t]+(?=\r?\n|\Z)", b"", original)
    if normalized != original:
        path.write_bytes(normalized)


def generate_imms_model(output_dir: Path = OUTPUT_DIR) -> Path:
    import cadquery as cq

    output_dir.mkdir(parents=True, exist_ok=True)
    width, depth, height = IMMS_BODY_SIZE_MM
    body = cq.Workplane("XY").box(
        width,
        depth,
        height,
        centered=(True, True, False),
    )
    output = output_dir / IMMS_MODEL_NAME
    cq.exporters.export(body, str(output))
    normalize_exported_text(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate KC2-owned component STEP models.")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    print(generate_imms_model(args.output_dir))


if __name__ == "__main__":
    main()
