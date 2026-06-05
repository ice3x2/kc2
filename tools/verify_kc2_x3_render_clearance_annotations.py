from __future__ import annotations

import re
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
RENDERS = ROOT / "hardware" / "kicad" / "renders"
EXPECTED = {
    "kc2_x3_joined_top": (1724, 749),
    "kc2_x3_join_seam_zoom": (320, 749),
}


def nonblank_png(path: Path) -> bool:
    with Image.open(path) as image:
        if image.size != EXPECTED[path.stem]:
            raise AssertionError(f"{path}: size {image.size} != {EXPECTED[path.stem]}")
        sampled = 0
        non_white = 0
        for y in range(0, image.height, 10):
            for x in range(0, image.width, 10):
                r, g, b = image.convert("RGB").getpixel((x, y))
                sampled += 1
                if not (r > 245 and g > 245 and b > 245):
                    non_white += 1
        return sampled > 0 and non_white > sampled // 10


def verify_svg(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    if 'id="key-horizontal-clearance"' not in text:
        errors.append(f"{path}: missing key-horizontal-clearance annotation")
    if "6-Y X" not in text:
        errors.append(f"{path}: missing 6-Y X clearance label")
    match = re.search(r'data-key-horizontal-clearance-mm="([0-9.]+)"', text)
    if not match:
        errors.append(f"{path}: missing data-key-horizontal-clearance-mm")
    elif float(match.group(1)) <= 0.0:
        errors.append(f"{path}: non-positive horizontal clearance {match.group(1)}")
    return errors


def main() -> None:
    errors: list[str] = []
    for stem in EXPECTED:
        svg = RENDERS / f"{stem}.svg"
        png = RENDERS / f"{stem}.png"
        if not svg.exists():
            errors.append(f"{svg}: missing")
        else:
            errors.extend(verify_svg(svg))
        if not png.exists():
            errors.append(f"{png}: missing")
        elif not nonblank_png(png):
            errors.append(f"{png}: blank or nearly blank")

    if errors:
        for error in errors:
            print(f"FAIL {error}")
        raise SystemExit(1)
    print("PASS KC2 X3 render clearance annotations")


if __name__ == "__main__":
    main()
