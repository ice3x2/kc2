from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zlib

if __package__:
    from tools.canonical_hash import HASH_POLICY, sha256_file
    from tools.kc2_x3_v2_output_geometry import (
        REQUIREMENT_IDS,
        parse_board,
        source_control_flashes,
        source_drill_geometry,
        source_j_bat_markings,
    )
else:
    from canonical_hash import HASH_POLICY, sha256_file
    from kc2_x3_v2_output_geometry import (
        REQUIREMENT_IDS,
        parse_board,
        source_control_flashes,
        source_drill_geometry,
        source_j_bat_markings,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT
    / "hardware"
    / "kicad"
    / "mechanical"
    / "kc2_mechanical_manifest.json"
)
A4_LANDSCAPE_POINTS = (841.896, 595.296)
GEOMETRY_TOLERANCE_MM = 0.012
_NUMBER = r"-?(?:\d+(?:\.\d*)?|\.\d+)"
_PATH_RE = re.compile(
    rf"({_NUMBER}\s+{_NUMBER}\s+m(?:\s+(?:{_NUMBER}\s+{_NUMBER}\s+l|"
    rf"{_NUMBER}\s+{_NUMBER}\s+{_NUMBER}\s+{_NUMBER}\s+{_NUMBER}\s+{_NUMBER}\s+c))*)"
    rf"\s+([bBsS])"
)
EXPECTED_J_BAT_MARKING_BBOXES = {
    "B+": (20, (-0.704762, -0.436145, 0.704762, 0.363855)),
    "B-/GND": (51, (-2.342857, -0.47424, 2.380952, 0.554331)),
}
EXPECTED_J_BAT_PDF_ORIGIN_OFFSETS_MM = {
    "B+": (-0.995238, -0.606667),
    "B-/GND": (-2.633333, -0.606667),
}


def _close(left: float, right: float, tolerance: float = GEOMETRY_TOLERANCE_MM) -> bool:
    return abs(left - right) <= tolerance


def _bbox_close(left: tuple[float, ...], right: tuple[float, ...]) -> bool:
    return len(left) == len(right) and all(_close(a, b) for a, b in zip(left, right))


def _pdf_objects(data: bytes) -> dict[int, bytes]:
    return {
        int(number): payload
        for number, payload in re.findall(
            rb"(?ms)(\d+)\s+\d+\s+obj\b(.*?)\bendobj", data
        )
    }


def _pdf_stream_payload(
    obj: bytes, objects: dict[int, bytes] | None = None
) -> bytes:
    stream_match = re.search(rb"\bstream\r?\n", obj)
    if not stream_match:
        return b""
    start = stream_match.end()

    length: int | None = None
    indirect = re.search(rb"/Length\s+(\d+)\s+\d+\s+R", obj)
    if indirect and objects is not None:
        length_object = objects.get(int(indirect.group(1)), b"")
        value = re.match(rb"\s*(\d+)\s*$", length_object)
        if value:
            length = int(value.group(1))
    else:
        direct = re.search(rb"/Length\s+(\d+)(?!\s+\d+\s+R)", obj)
        if direct:
            length = int(direct.group(1))

    if length is not None and start + length <= len(obj):
        return obj[start : start + length]

    # The fallback deliberately finds the marker's leading EOL instead of a
    # regex with ``\r?\n``. A valid compressed stream may itself end in 0x0D;
    # consuming that payload byte as part of the delimiter truncates zlib data.
    end = obj.rfind(b"\nendstream")
    if end < start:
        end = obj.rfind(b"\rendstream")
    return obj[start:end] if end >= start else b""


def _decoded_pdf_stream(
    obj: bytes, objects: dict[int, bytes] | None = None
) -> bytes:
    payload = _pdf_stream_payload(obj, objects)
    return zlib.decompress(payload) if payload and b"/FlateDecode" in obj else payload


def _pdf_literal_bytes(value: str) -> bytes:
    data = value.encode("latin1")
    output = bytearray()
    index = 0
    escape_values = {ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12}
    while index < len(data):
        value_byte = data[index]
        if value_byte != ord("\\"):
            output.append(value_byte)
            index += 1
            continue
        index += 1
        if index >= len(data):
            break
        if ord("0") <= data[index] <= ord("7"):
            end = index
            while end < len(data) and end < index + 3 and ord("0") <= data[end] <= ord("7"):
                end += 1
            output.append(int(data[index:end], 8))
            index = end
        else:
            output.append(escape_values.get(data[index], data[index]))
            index += 1
    return bytes(output)


def _pdf_text_items(
    objects: dict[int, bytes], content_text: str, coordinate_to_mm: float
) -> list[dict[str, object]]:
    font_maps: dict[str, dict[int, str]] = {}
    visible_codes: dict[str, set[int]] = {}
    for font in objects.values():
        if not re.search(rb"/Type\s*/Font\b", font):
            continue
        name_match = re.search(rb"/Name\s*/([A-Za-z0-9_.-]+)", font)
        cmap_match = re.search(rb"/ToUnicode\s+(\d+)\s+\d+\s+R", font)
        charprocs_match = re.search(rb"/CharProcs\s+(\d+)\s+\d+\s+R", font)
        if not name_match or not cmap_match:
            continue
        name = name_match.group(1).decode("ascii")
        cmap_object = objects.get(int(cmap_match.group(1)), b"")
        cmap = _decoded_pdf_stream(cmap_object, objects)
        mapping = {
            int(code, 16): chr(int(unicode_value, 16))
            for code, unicode_value in re.findall(
                rb"<([0-9A-Fa-f]{2})>\s*<([0-9A-Fa-f]{4})>", cmap
            )
        }
        font_maps[name] = mapping
        drawn: set[int] = set()
        if charprocs_match:
            charprocs = objects.get(int(charprocs_match.group(1)), b"")
            for glyph, object_number in re.findall(
                rb"/g([0-9A-Fa-f]{2})\s+(\d+)\s+\d+\s+R", charprocs
            ):
                glyph_stream = _decoded_pdf_stream(
                    objects.get(int(object_number), b""), objects
                )
                if re.search(rb"(?:^|\s)m(?:\s|$)", glyph_stream) and re.search(
                    rb"(?:^|\s)[lc](?:\s|$)", glyph_stream
                ):
                    drawn.add(int(glyph, 16))
        visible_codes[name] = drawn
    number = _NUMBER
    text_re = re.compile(
        rf"q\s+({number})\s+({number})\s+({number})\s+({number})\s+"
        rf"({number})\s+({number})\s+cm\s+BT\b.*?/([A-Za-z0-9_.-]+)\s+"
        rf"({number})\s+Tf\s+\(((?:\\.|[^\\)])*)\)\s+Tj\s+ET\s+Q",
        flags=re.DOTALL,
    )
    items: list[dict[str, object]] = []
    for match in text_re.finditer(content_text):
        transform = tuple(float(match.group(index)) for index in range(1, 7))
        font_name = match.group(7)
        encoded = _pdf_literal_bytes(match.group(9))
        mapping = font_maps.get(font_name, {})
        items.append(
            {
                "text": "".join(mapping.get(value, "\ufffd") for value in encoded),
                "font": font_name,
                "font_size_mm": round(float(match.group(8)) * coordinate_to_mm, 6),
                "origin": (
                    round(transform[4] * coordinate_to_mm, 6),
                    round(transform[5] * coordinate_to_mm, 6),
                ),
                "transform": transform[:4],
                "glyphs_visible": bool(encoded)
                and all(value in visible_codes.get(font_name, set()) for value in encoded),
            }
        )
    return items


def _pdf_paths(content: str, coordinate_to_mm: float) -> list[dict[str, object]]:
    content = re.sub(r"(?s)BT\b.*?\bET", "", content)
    paths: list[dict[str, object]] = []
    texts: list[dict[str, object]] = []
    for match in _PATH_RE.finditer(content):
        commands = match.group(1)
        points: list[tuple[float, float]] = []
        segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
        current: tuple[float, float] | None = None
        token_re = re.compile(
            rf"({_NUMBER})\s+({_NUMBER})\s+([ml])|"
            rf"({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})\s+c"
        )
        for command in token_re.finditer(commands):
            if command.group(3):
                point = (
                    float(command.group(1)) * coordinate_to_mm,
                    float(command.group(2)) * coordinate_to_mm,
                )
                if command.group(3) == "l" and current is not None:
                    segments.append((current, point))
                current = point
                points.append(point)
            else:
                curve_points = [
                    (
                        float(command.group(index)) * coordinate_to_mm,
                        float(command.group(index + 1)) * coordinate_to_mm,
                    )
                    for index in (4, 6, 8)
                ]
                points.extend(curve_points)
                current = curve_points[-1]
        if points:
            xs, ys = [point[0] for point in points], [point[1] for point in points]
            paths.append(
                {
                    "bbox": (min(xs), min(ys), max(xs), max(ys)),
                    "segments": segments,
                    "operator": match.group(2),
                }
            )
    return paths


def inspect_pdf(data: bytes) -> dict[str, object]:
    errors: list[str] = []
    if not data.startswith(b"%PDF-"):
        errors.append("missing PDF header")
    if not data.rstrip().endswith(b"%%EOF"):
        errors.append("missing PDF EOF marker")
    if b"xref" not in data or b"trailer" not in data:
        errors.append("missing PDF xref/trailer")
    objects = _pdf_objects(data)
    page_objects = [
        payload
        for payload in objects.values()
        if re.search(rb"/Type\s*/Page\b", payload)
        and not re.search(rb"/Type\s*/Pages\b", payload)
    ]
    page_count = len(page_objects)
    media_box: tuple[float, float, float, float] | None = None
    content_text = ""
    coordinate_to_mm = 0.0
    paths: list[dict[str, object]] = []
    texts: list[dict[str, object]] = []
    if page_count != 1:
        errors.append(f"expected one PDF page, found {page_count}")
    else:
        page = page_objects[0]
        media_match = re.search(
            rb"/MediaBox\s*\[\s*([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+)\s*\]",
            page,
        )
        if media_match:
            media_box = tuple(float(value) for value in media_match.groups())
        else:
            errors.append("page MediaBox missing")
        content_match = re.search(rb"/Contents\s+(\d+)\s+\d+\s+R", page)
        if not content_match or int(content_match.group(1)) not in objects:
            errors.append("page Contents reference missing")
        else:
            stream_object = objects[int(content_match.group(1))]
            payload = _pdf_stream_payload(stream_object, objects)
            if not payload:
                errors.append("page content stream missing")
            else:
                try:
                    if b"/FlateDecode" in stream_object:
                        payload = zlib.decompress(payload)
                    content_text = payload.decode("latin1")
                except (zlib.error, UnicodeDecodeError) as error:
                    errors.append(f"page content decode failed: {error}")
    matrix: tuple[float, ...] | None = None
    if content_text:
        matrix_match = re.search(
            rf"^\s*({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})\s+({_NUMBER})\s+cm\b",
            content_text,
        )
        if matrix_match:
            matrix = tuple(float(value) for value in matrix_match.groups())
            coordinate_to_mm = abs(matrix[0]) * 25.4 / 72.0
            paths = _pdf_paths(content_text, coordinate_to_mm)
            texts = _pdf_text_items(objects, content_text, coordinate_to_mm)
        else:
            errors.append("page plot transform missing")
    return {
        "parse_errors": errors,
        "page_count": page_count,
        "media_box": media_box,
        "matrix": matrix,
        "coordinate_to_mm": coordinate_to_mm,
        "paths": paths,
        "texts": texts,
    }


def pdf_one_to_one_scale_matches(inspection: dict[str, object]) -> bool:
    matrix = inspection.get("matrix")
    return bool(matrix) and all(
        _close(left, right, tolerance=0.000001)
        for left, right in zip(matrix, (0.0072, 0.0, 0.0, 0.0072, 0.0, 0.0))
    )


def _transform_pdf_point(
    point: tuple[float, float], mirrored: bool, page_width_mm: float, page_height_mm: float
) -> tuple[float, float]:
    return (
        page_width_mm - point[0] if mirrored else point[0],
        page_height_mm - point[1],
    )


def _expected_bbox(
    center: tuple[float, float],
    size: tuple[float, float],
    mirrored: bool,
    page_width_mm: float,
    page_height_mm: float,
) -> tuple[float, float, float, float]:
    x, y = _transform_pdf_point(center, mirrored, page_width_mm, page_height_mm)
    return (x - size[0] / 2, y - size[1] / 2, x + size[0] / 2, y + size[1] / 2)


def pdf_control_geometry_errors(
    inspection: dict[str, object], board: dict[str, object], face: str, mirrored: bool
) -> list[str]:
    media_box = inspection["media_box"]
    if not media_box or not inspection["paths"]:
        return ["PDF control geometry unavailable"]
    page_width_mm = (media_box[2] - media_box[0]) * 25.4 / 72.0
    page_height_mm = (media_box[3] - media_box[1]) * 25.4 / 72.0
    paths = inspection["paths"]
    bboxes = [path["bbox"] for path in paths]
    segments = [segment for path in paths for segment in path["segments"]]
    errors: list[str] = []

    def require_bbox(label: str, bbox: tuple[float, float, float, float]) -> None:
        if not any(_bbox_close(bbox, actual) for actual in bboxes):
            errors.append(f"{label}: expected plotted bbox {tuple(round(v, 4) for v in bbox)} missing")

    drill_geometry = source_drill_geometry(board)
    selected_drills = [
        item
        for records in drill_geometry.values()
        for item in records
        if re.fullmatch(r"MH\d+", str(item["reference"]))
        or item["reference"] in {"U1", "J_BAT1", "SW_PWR1", "BAT_LEAD_SLOT1"}
    ]
    for item in selected_drills:
        if item["shape"] == "slot":
            width, height = item["size"]
            half_run = abs(width - height) / 2
            center = item["center"]
            if width >= height:
                endpoints = ((center[0] - half_run, center[1]), (center[0] + half_run, center[1]))
            else:
                endpoints = ((center[0], center[1] - half_run), (center[0], center[1] + half_run))
            wanted = tuple(
                sorted(
                    _transform_pdf_point(point, mirrored, page_width_mm, page_height_mm)
                    for point in endpoints
                )
            )
            if not any(
                _bbox_close(wanted[0] + wanted[1], tuple(sorted(actual))[0] + tuple(sorted(actual))[1])
                for actual in segments
            ):
                errors.append(f"drill {item['reference']}/{item['pad']}: plotted slot missing")
        else:
            require_bbox(
                f"drill {item['reference']}/{item['pad']}",
                _expected_bbox(
                    item["center"], item["size"], mirrored, page_width_mm, page_height_mm
                ),
            )
    control_layer = "F.Paste" if face == "top" else "B.Paste"
    for item in source_control_flashes(board, control_layer):
        require_bbox(
            f"{control_layer} {item['reference']}/{item['pad']}",
            _expected_bbox(
                item["center"], item["size"], mirrored, page_width_mm, page_height_mm
            ),
        )

    def normalized_segment(
        start: tuple[float, float], end: tuple[float, float]
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        return tuple(sorted((start, end)))

    actual_segments = [normalized_segment(start, end) for start, end in segments]

    def require_segment(label: str, start: tuple[float, float], end: tuple[float, float]) -> None:
        wanted = normalized_segment(
            _transform_pdf_point(start, mirrored, page_width_mm, page_height_mm),
            _transform_pdf_point(end, mirrored, page_width_mm, page_height_mm),
        )
        if not any(
            _bbox_close(wanted[0] + wanted[1], actual[0] + actual[1])
            for actual in actual_segments
        ):
            errors.append(f"{label}: expected plotted segment missing")

    for edge in board["edge_lines"]:
        require_segment("Edge.Cuts", edge["start"], edge["end"])
    fab_layer = "F.Fab" if face == "top" else "B.Fab"
    control_refs = {
        reference
        for reference in {"U1", "BAT1", "J_BAT1", "SW_PWR1", "SW_RST1"}
        if reference in board["footprints"]
    }
    for reference in sorted(control_refs):
        footprint = board["footprints"].get(reference)
        for segment in footprint["fab_segments"]:
            if segment["layer"] == fab_layer:
                require_segment(f"{fab_layer} {reference}", segment["start"], segment["end"])
    return errors


def pdf_j_bat_marking_errors(
    inspection: dict[str, object], board: dict[str, object], face: str
) -> list[str]:
    if face != "top":
        return []
    source = source_j_bat_markings(board)
    errors = list(source["errors"])
    media_box = inspection.get("media_box")
    if not media_box:
        return errors + ["J_BAT1 PDF marking unavailable"]
    page_width_mm = (media_box[2] - media_box[0]) * 25.4 / 72.0
    page_height_mm = (media_box[3] - media_box[1]) * 25.4 / 72.0
    for text, offset in EXPECTED_J_BAT_PDF_ORIGIN_OFFSETS_MM.items():
        marking = source["markings"].get(text)
        if marking is None:
            continue
        matches = [item for item in inspection.get("texts", []) if item["text"] == text]
        if len(matches) != 1:
            errors.append(f"J_BAT1 PDF {text!r} count {len(matches)}, expected 1")
            continue
        item = matches[0]
        anchor = _transform_pdf_point(
            marking["center"], False, page_width_mm, page_height_mm
        )
        expected_origin = (anchor[0] + offset[0], anchor[1] + offset[1])
        if not _bbox_close(item["origin"], expected_origin):
            errors.append(
                f"J_BAT1 PDF {text!r} origin {item['origin']}, "
                f"expected {tuple(round(value, 6) for value in expected_origin)}"
            )
        if not _close(item["font_size_mm"], 0.8, tolerance=0.001):
            errors.append(f"J_BAT1 PDF {text!r} font size is not 0.8 mm")
        if not all(
            _close(left, right, tolerance=0.000001)
            for left, right in zip(item["transform"], (1.0, 0.0, 0.0, 1.0))
        ):
            errors.append(f"J_BAT1 PDF {text!r} text transform is not upright")
        if not item["glyphs_visible"]:
            errors.append(f"J_BAT1 PDF {text!r} Type3 glyph geometry is missing")
    return errors


def inspect_svg(data: bytes, board: dict[str, object]) -> dict[str, object]:
    errors: list[str] = []
    width_mm = height_mm = 0.0
    view_box: tuple[float, float, float, float] | None = None
    shape_bboxes: list[tuple[float, float, float, float]] = []
    shape_segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    stroked_text_groups: list[dict[str, object]] = []
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        return {"parse_errors": [f"SVG parse failed: {error}"], "physical_scale_matches": False,
                "view_box_matches_board": False, "control_geometry_errors": ["SVG unavailable"],
                "j_bat_marking_glyphs": {},
                "j_bat_marking_errors": ["SVG J_BAT1 marking unavailable"]}
    width_match = re.fullmatch(r"([0-9.]+)mm", root.get("width", ""))
    height_match = re.fullmatch(r"([0-9.]+)mm", root.get("height", ""))
    if width_match and height_match:
        width_mm, height_mm = float(width_match.group(1)), float(height_match.group(1))
    else:
        errors.append("SVG width/height must be explicit mm")
    try:
        values = tuple(float(value) for value in root.get("viewBox", "").split())
        if len(values) == 4:
            view_box = values
        else:
            errors.append("SVG viewBox must contain four values")
    except ValueError:
        errors.append("SVG viewBox is invalid")
    parent_map = {child: parent for parent in root.iter() for child in parent}
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        try:
            if tag == "circle":
                cx, cy, radius = (float(element.get(name, "nan")) for name in ("cx", "cy", "r"))
                shape_bboxes.append((cx - radius, cy - radius, cx + radius, cy + radius))
            elif tag == "ellipse":
                cx, cy, rx, ry = (float(element.get(name, "nan")) for name in ("cx", "cy", "rx", "ry"))
                shape_bboxes.append((cx - rx, cy - ry, cx + rx, cy + ry))
            elif tag == "rect":
                x, y, width, height = (
                    float(element.get(name, "nan")) for name in ("x", "y", "width", "height")
                )
                shape_bboxes.append((x, y, x + width, y + height))
            elif tag == "path":
                path_data = element.get("d", "")
                values = [float(value) for value in re.findall(_NUMBER, path_data)]
                points = list(zip(values[0::2], values[1::2]))
                if points:
                    xs, ys = zip(*points)
                    shape_bboxes.append((min(xs), min(ys), max(xs), max(ys)))
                for match in re.finditer(
                    rf"M\s*({_NUMBER})\s+({_NUMBER})\s*L\s*({_NUMBER})\s+({_NUMBER})",
                    path_data,
                    flags=re.IGNORECASE,
                ):
                    shape_segments.append(
                        (
                            (float(match.group(1)), float(match.group(2))),
                            (float(match.group(3)), float(match.group(4))),
                        )
                    )
            elif tag == "g" and element.get("class") == "stroked-text":
                desc = next(
                    (
                        child.text or ""
                        for child in element
                        if child.tag.rsplit("}", 1)[-1] == "desc"
                    ),
                    "",
                )
                segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
                for child in element.iter():
                    if child.tag.rsplit("}", 1)[-1] != "path":
                        continue
                    path_data = child.get("d", "")
                    for match in re.finditer(
                        rf"M\s*({_NUMBER})\s+({_NUMBER})\s*L\s*({_NUMBER})\s+({_NUMBER})",
                        path_data,
                        flags=re.IGNORECASE,
                    ):
                        segments.append(
                            (
                                (float(match.group(1)), float(match.group(2))),
                                (float(match.group(3)), float(match.group(4))),
                            )
                        )
                parent_style = parent_map.get(element).get("style", "") if parent_map.get(element) is not None else ""
                stroked_text_groups.append(
                    {
                        "text": desc,
                        "segments": segments,
                        "visible": "stroke-width:0.1200" in parent_style
                        and "stroke-opacity:1" in parent_style,
                    }
                )
        except ValueError:
            errors.append(f"SVG {tag} geometry is invalid")
    edge_points = board["edge_control_points"]
    min_x, max_x = min(point[0] for point in edge_points), max(point[0] for point in edge_points)
    min_y, max_y = min(point[1] for point in edge_points), max(point[1] for point in edge_points)
    board_width, board_height = max_x - min_x, max_y - min_y
    physical_scale_matches = bool(view_box) and all(
        _close(left, right)
        for left, right in ((width_mm, view_box[2]), (height_mm, view_box[3]))
    )
    view_box_matches_board = bool(view_box) and all(
        _close(left, right, tolerance=0.03)
        for left, right in (
            (view_box[0], 0.0),
            (view_box[1], 0.0),
            (view_box[2], board_width),
            (view_box[3], board_height),
        )
    )
    control_errors: list[str] = []
    drills = source_drill_geometry(board)
    for item in [
        item
        for records in drills.values()
        for item in records
        if re.fullmatch(r"MH\d+", str(item["reference"]))
        or item["reference"] in {"U1", "J_BAT1", "SW_PWR1", "BAT_LEAD_SLOT1"}
    ]:
        center = (item["center"][0] - min_x, item["center"][1] - min_y)
        if item["shape"] == "slot":
            width, height = item["size"]
            half_run = abs(width - height) / 2
            if width >= height:
                endpoints = ((center[0] - half_run, center[1]), (center[0] + half_run, center[1]))
            else:
                endpoints = ((center[0], center[1] - half_run), (center[0], center[1] + half_run))
            wanted = tuple(sorted(endpoints))
            if not any(
                _bbox_close(wanted[0] + wanted[1], tuple(sorted(actual))[0] + tuple(sorted(actual))[1])
                for actual in shape_segments
            ):
                control_errors.append(f"drill {item['reference']}/{item['pad']}: SVG slot missing")
        else:
            wanted = (
                center[0] - item["size"][0] / 2,
                center[1] - item["size"][1] / 2,
                center[0] + item["size"][0] / 2,
                center[1] + item["size"][1] / 2,
            )
            if not any(_bbox_close(wanted, actual) for actual in shape_bboxes):
                control_errors.append(f"drill {item['reference']}/{item['pad']}: SVG geometry missing")
    marking_source = source_j_bat_markings(board)
    marking_errors = list(marking_source["errors"])
    marking_glyphs: dict[str, dict[str, object]] = {}
    for text, (expected_count, expected_bbox) in EXPECTED_J_BAT_MARKING_BBOXES.items():
        marking = marking_source["markings"].get(text)
        if marking is None:
            continue
        matches = [group for group in stroked_text_groups if group["text"] == text]
        if len(matches) != 1:
            marking_errors.append(
                f"J_BAT1 SVG visible stroked {text!r} count {len(matches)}, expected 1"
            )
            continue
        group = matches[0]
        anchor = (marking["center"][0] - min_x, marking["center"][1] - min_y)
        x_values = [point[0] - anchor[0] for segment in group["segments"] for point in segment]
        y_values = [point[1] - anchor[1] for segment in group["segments"] for point in segment]
        actual_bbox = (
            round(min(x_values), 6),
            round(min(y_values), 6),
            round(max(x_values), 6),
            round(max(y_values), 6),
        ) if x_values and y_values else None
        marking_glyphs[text] = {
            "stroke_count": len(group["segments"]),
            "centerline_bbox_relative_mm": actual_bbox,
            "visible": group["visible"],
        }
        if len(group["segments"]) != expected_count:
            marking_errors.append(
                f"J_BAT1 SVG {text!r} stroke count {len(group['segments'])}, "
                f"expected {expected_count}"
            )
        if actual_bbox is None or not _bbox_close(actual_bbox, expected_bbox):
            marking_errors.append(
                f"J_BAT1 SVG {text!r} bbox {actual_bbox}, expected {expected_bbox}"
            )
        if not group["visible"]:
            marking_errors.append(f"J_BAT1 SVG {text!r} stroked geometry is not visible")
    return {
        "parse_errors": errors,
        "width_mm": width_mm,
        "height_mm": height_mm,
        "view_box": view_box,
        "physical_scale_matches": physical_scale_matches,
        "view_box_matches_board": view_box_matches_board,
        "control_geometry_errors": control_errors,
        "j_bat_marking_glyphs": marking_glyphs,
        "j_bat_marking_errors": marking_errors,
    }


def analyze_mechanical_outputs(
    manifest_path: Path = DEFAULT_MANIFEST, root: Path = ROOT
) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    products: dict[str, object] = {}
    for product, details in manifest["products"].items():
        board = root / details["board"]
        board_geometry = parse_board(board) if board.is_file() else None
        drawings: dict[str, object] = {}
        for face, drawing in details["drawings"].items():
            path = root / drawing["path"]
            data = path.read_bytes() if path.is_file() else b""
            inspection = inspect_pdf(data) if data else {
                "parse_errors": ["PDF missing"],
                "page_count": 0,
                "media_box": None,
                "matrix": None,
                "paths": [],
                "texts": [],
            }
            media_box = inspection["media_box"]
            media_matches = bool(media_box) and all(
                _close(left, right, tolerance=0.02)
                for left, right in zip(
                    (media_box[0], media_box[1], media_box[2], media_box[3]),
                    (0.0, 0.0, *A4_LANDSCAPE_POINTS),
                )
            )
            scale_matches = pdf_one_to_one_scale_matches(inspection)
            expected_mirrored = drawing.get("mirrored") is True
            control_errors = (
                pdf_control_geometry_errors(
                    inspection, board_geometry, face, expected_mirrored
                )
                if board_geometry is not None
                else ["source board unavailable"]
            )
            marking_errors = (
                pdf_j_bat_marking_errors(inspection, board_geometry, face)
                if product in {"left", "right"} and board_geometry is not None
                else []
            )
            expected_layers = (
                ["F.Fab", "F.Silkscreen", "Edge.Cuts"]
                if face == "top"
                else ["B.Fab", "Edge.Cuts"]
            )
            drawings[face] = {
                "exists": path.is_file(),
                "size": len(data),
                "pdf_header_valid": data.startswith(b"%PDF-"),
                "sha256_matches": bool(data)
                and sha256_file(path) == drawing["sha256"],
                "pdf_parse_errors": inspection["parse_errors"],
                "page_count": inspection["page_count"],
                "media_box_points": media_box,
                "a4_landscape_media_box_matches": media_matches,
                "one_to_one_scale_matches": scale_matches,
                "control_geometry_errors": control_errors,
                "mirror_matches_manifest": not control_errors,
                "layers_match_contract": drawing.get("layers") == expected_layers,
                "j_bat_marking_errors": marking_errors,
            }
        products[product] = {
            "source_board_exists": board.is_file(),
            "source_board_sha256_matches": board.is_file()
            and sha256_file(board)
            == details.get("source_board_sha256"),
            "drawings": drawings,
        }
        outline = details.get("outline_svg")
        if outline is not None:
            outline_path = root / outline["path"]
            outline_data = outline_path.read_bytes() if outline_path.is_file() else b""
            svg_inspection = (
                inspect_svg(outline_data, board_geometry)
                if outline_data and board_geometry is not None
                else {
                    "parse_errors": ["SVG or source board unavailable"],
                    "physical_scale_matches": False,
                    "view_box_matches_board": False,
                    "control_geometry_errors": ["SVG control geometry unavailable"],
                    "j_bat_marking_errors": ["SVG J_BAT1 marking unavailable"],
                }
            )
            products[product]["outline_svg"] = {
                "exists": outline_path.is_file(),
                "size": len(outline_data),
                "svg_header_valid": outline_data.startswith(b"<?xml") and b"<svg" in outline_data[:1000],
                "sha256_matches": bool(outline_data)
                and sha256_file(outline_path) == outline["sha256"],
                "scale": outline.get("scale"),
                "has_trailing_whitespace": any(
                    line.endswith((b" ", b"\t"))
                    for line in outline_data.splitlines()
                ),
                **svg_inspection,
            }
    return {
        "requirement_ids": manifest.get("requirement_ids", []),
        "requirement_ids_match": tuple(manifest.get("requirement_ids", ())) == REQUIREMENT_IDS,
        "hash_policy": manifest.get("hash_policy"),
        "hash_policy_matches": manifest.get("hash_policy") == HASH_POLICY,
        "scale": manifest["scale"],
        "products": products,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify KC2 X3 V2 1:1 assembly drawings.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()
    report = analyze_mechanical_outputs(args.manifest)
    errors: list[str] = []
    if report["scale"] != 1.0:
        errors.append(f"unexpected scale {report['scale']}")
    if not report["requirement_ids_match"]:
        errors.append(f"requirement_ids must be {list(REQUIREMENT_IDS)!r}")
    if not report["hash_policy_matches"]:
        errors.append(f"hash policy must be {HASH_POLICY!r}")
    for product, details in report["products"].items():
        if not details["source_board_exists"]:
            errors.append(f"{product}: source board missing")
        if not details["source_board_sha256_matches"]:
            errors.append(f"{product}: source board SHA-256 mismatch")
        for face, drawing in details["drawings"].items():
            if not all((drawing["exists"], drawing["pdf_header_valid"], drawing["sha256_matches"])):
                errors.append(f"{product} {face}: invalid PDF or checksum")
            if drawing["pdf_parse_errors"]:
                errors.append(f"{product} {face}: PDF parse {drawing['pdf_parse_errors']}")
            if drawing["page_count"] != 1:
                errors.append(f"{product} {face}: expected one PDF page")
            if not drawing["a4_landscape_media_box_matches"]:
                errors.append(f"{product} {face}: expected A4 landscape MediaBox")
            if not drawing["one_to_one_scale_matches"]:
                errors.append(f"{product} {face}: PDF plot transform is not 1:1")
            if not drawing["mirror_matches_manifest"]:
                errors.append(f"{product} {face}: mirror/control geometry mismatch")
            if drawing["control_geometry_errors"]:
                errors.append(
                    f"{product} {face}: PDF control geometry "
                    f"{drawing['control_geometry_errors'][:10]}"
                )
            if not drawing["layers_match_contract"]:
                errors.append(f"{product} {face}: PDF layer contract mismatch")
            if drawing["j_bat_marking_errors"]:
                errors.append(
                    f"{product} {face}: J_BAT1 marking "
                    f"{drawing['j_bat_marking_errors']}"
                )
        if product in {"left", "right"}:
            outline = details.get("outline_svg")
            if not outline or not all(
                (
                    outline["exists"],
                    outline["svg_header_valid"],
                    outline["sha256_matches"],
                    outline["scale"] == 1.0,
                    not outline["has_trailing_whitespace"],
                    not outline["parse_errors"],
                    outline["physical_scale_matches"],
                    outline["view_box_matches_board"],
                    not outline["control_geometry_errors"],
                    not outline["j_bat_marking_errors"],
                )
            ):
                errors.append(f"{product}: invalid 1:1 outline SVG or checksum")
    if errors:
        raise SystemExit("FAIL: KC2 X3 V2 mechanical drawings\n- " + "\n- ".join(errors))
    print(json.dumps(report, indent=2))
    print("PASS: CON-ARCH-004 1:1 top/bottom assembly drawings")


if __name__ == "__main__":
    main()
