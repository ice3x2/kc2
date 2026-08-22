from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.verify_kc2_x3_v2 import DEFAULT_DRC_EVIDENCE, build_drc_evidence


def write_drc_evidence(output: Path = DEFAULT_DRC_EVIDENCE) -> dict[str, object]:
    evidence = build_drc_evidence()
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bind KC2 X3 V2 KiCad DRC reports to exact board and report hashes."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_DRC_EVIDENCE)
    args = parser.parse_args()
    evidence = write_drc_evidence(args.output)
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
