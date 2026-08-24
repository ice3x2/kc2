from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.verify_kc2_x3_v2_coupon import (
    DEFAULT_DRC_EVIDENCE,
    build_coupon_drc_evidence,
)


def write_drc_evidence(output: Path = DEFAULT_DRC_EVIDENCE) -> dict[str, object]:
    evidence = build_coupon_drc_evidence()
    output.write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Bind the KC2 X3 V2 switch coupon KiCad DRC report to exact source "
            "and reviewed policy metadata."
        )
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_DRC_EVIDENCE)
    args = parser.parse_args()
    evidence = write_drc_evidence(args.output)
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
