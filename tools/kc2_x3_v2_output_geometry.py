from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable


REQUIREMENT_IDS = (
    "CON-ARCH-004",
    "CON-ARCH-006",
    "CON-ARCH-007",
    "REL-ARCH-001",
    "OPS-ARCH-006",
)
_TOKEN_RE = re.compile(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+')


def _atom(token: str) -> str:
    return json.loads(token) if token.startswith('"') else token


def parse_sexpr(text: str) -> list[Any]:
    stack: list[list[Any]] = []
    roots: list[list[Any]] = []
    for match in _TOKEN_RE.finditer(text):
        token = match.group(0)
        if token == "(":
            node: list[Any] = []
            if stack:
                stack[-1].append(node)
            else:
                roots.append(node)
            stack.append(node)
        elif token == ")":
            if not stack:
                raise ValueError("unbalanced closing parenthesis")
            stack.pop()
        elif stack:
            stack[-1].append(_atom(token))
    if stack or len(roots) != 1:
        raise ValueError("invalid KiCad S-expression")
    return roots[0]


def _children(node: list[Any], name: str) -> list[list[Any]]:
    return [item for item in node[1:] if isinstance(item, list) and item and item[0] == name]


def _child(node: list[Any], name: str) -> list[Any] | None:
    items = _children(node, name)
    return items[0] if items else None


def _number(value: Any) -> float:
    return float(str(value))


def _xy(node: list[Any] | None, default: tuple[float, float] = (0.0, 0.0)) -> tuple[float, float]:
    if node is None or len(node) < 3:
        return default
    return (_number(node[1]), _number(node[2]))


def _angle(node: list[Any] | None) -> float:
    return _number(node[3]) if node is not None and len(node) > 3 else 0.0


def _rotate(point: tuple[float, float], angle_deg: float) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    cosine, sine = math.cos(angle), math.sin(angle)
    return (
        point[0] * cosine - point[1] * sine,
        point[0] * sine + point[1] * cosine,
    )


def _global_point(
    local: tuple[float, float], origin: tuple[float, float], rotation: float
) -> tuple[float, float]:
    x, y = _rotate(local, rotation)
    return (round(origin[0] + x, 6), round(origin[1] + y, 6))


def _property(node: list[Any], name: str) -> str:
    for item in _children(node, "property"):
        if len(item) >= 3 and item[1] == name:
            return str(item[2])
    return ""


def _layers(node: list[Any]) -> tuple[str, ...]:
    layer_node = _child(node, "layers")
    return tuple(str(value) for value in layer_node[1:]) if layer_node else ()


def _graphic_segments(
    footprint: list[Any], origin: tuple[float, float], rotation: float
) -> list[dict[str, object]]:
    segments: list[dict[str, object]] = []
    for graphic in footprint[1:]:
        if not isinstance(graphic, list) or not graphic:
            continue
        layer_node = _child(graphic, "layer")
        layer = str(layer_node[1]) if layer_node and len(layer_node) > 1 else ""
        if graphic[0] == "fp_line":
            start, end = _xy(_child(graphic, "start")), _xy(_child(graphic, "end"))
            segments.append(
                {
                    "layer": layer,
                    "start": _global_point(start, origin, rotation),
                    "end": _global_point(end, origin, rotation),
                }
            )
        elif graphic[0] == "fp_rect":
            start, end = _xy(_child(graphic, "start")), _xy(_child(graphic, "end"))
            x1, y1 = start
            x2, y2 = end
            corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
            for index, corner in enumerate(corners):
                segments.append(
                    {
                        "layer": layer,
                        "start": _global_point(corner, origin, rotation),
                        "end": _global_point(corners[(index + 1) % 4], origin, rotation),
                    }
                )
    return segments


def _footprint_texts(
    footprint: list[Any], origin: tuple[float, float], rotation: float
) -> list[dict[str, object]]:
    texts: list[dict[str, object]] = []
    for graphic in _children(footprint, "fp_text"):
        if len(graphic) < 3:
            continue
        local_at = _child(graphic, "at")
        layer_node = _child(graphic, "layer")
        effects = _child(graphic, "effects")
        font = _child(effects, "font") if effects else None
        size = _xy(_child(font, "size")) if font else (0.0, 0.0)
        thickness_node = _child(font, "thickness") if font else None
        thickness = _number(thickness_node[1]) if thickness_node and len(thickness_node) > 1 else 0.0
        local_center = _xy(local_at)
        local_rotation = round((rotation + _angle(local_at)) % 360.0, 6)
        texts.append(
            {
                "kind": str(graphic[1]),
                "text": str(graphic[2]),
                "layer": str(layer_node[1]) if layer_node and len(layer_node) > 1 else "",
                "hidden": "hide" in graphic[3:],
                "local_center": local_center,
                "center": _global_point(local_center, origin, rotation),
                "local_rotation": local_rotation,
                "rotation": local_rotation,
                "size": tuple(round(value, 6) for value in size),
                "thickness": round(thickness, 6),
            }
        )
    return texts


def parse_board(path: Path) -> dict[str, object]:
    root = parse_sexpr(path.read_text(encoding="utf-8"))
    footprints: dict[str, dict[str, object]] = {}
    vias: list[dict[str, object]] = []
    edge_lines: list[dict[str, tuple[float, float]]] = []
    edge_control_points: list[tuple[float, float]] = []
    for item in root[1:]:
        if not isinstance(item, list) or not item:
            continue
        if item[0] == "footprint":
            at = _child(item, "at")
            origin, rotation = _xy(at), _angle(at)
            footprint_layer = str((_child(item, "layer") or ["", ""])[1])
            geometry_rotation = -rotation if footprint_layer == "B.Cu" else rotation
            reference = _property(item, "Reference")
            pads: list[dict[str, object]] = []
            for pad_node in _children(item, "pad"):
                local_at = _child(pad_node, "at")
                # KiCad serializes the pad angle in board coordinates even though
                # the pad position remains footprint-local (and mirrored on B.Cu).
                total_rotation = _angle(local_at) % 360.0
                size = _xy(_child(pad_node, "size"))
                if round(total_rotation % 180.0, 6) in {90.0}:
                    size = (size[1], size[0])
                drill_node = _child(pad_node, "drill")
                drill: dict[str, object] | None = None
                if drill_node:
                    values = drill_node[1:]
                    if values and values[0] == "oval":
                        width, height = _number(values[1]), _number(values[2])
                        if round(total_rotation % 180.0, 6) == 90.0:
                            width, height = height, width
                        drill = {"shape": "slot", "size": (width, height)}
                    else:
                        diameter = _number(values[0])
                        drill = {"shape": "round", "size": (diameter, diameter)}
                pads.append(
                    {
                        "number": str(pad_node[1]),
                        "type": str(pad_node[2]),
                        "shape": str(pad_node[3]),
                        "center": _global_point(_xy(local_at), origin, geometry_rotation),
                        "size": tuple(round(value, 6) for value in size),
                        "rotation": round(total_rotation, 6),
                        "layers": _layers(pad_node),
                        "net": str((_child(pad_node, "net") or ["", ""])[1]),
                        "drill": drill,
                    }
                )
            footprints[reference] = {
                "reference": reference,
                "name": str(item[1]),
                "value": _property(item, "Value"),
                "layer": footprint_layer,
                "center": origin,
                "rotation": rotation,
                "pads": pads,
                "fab_segments": _graphic_segments(item, origin, geometry_rotation),
                "texts": _footprint_texts(item, origin, geometry_rotation),
            }
        elif item[0] == "via":
            at = _xy(_child(item, "at"))
            drill_node = _child(item, "drill")
            if drill_node:
                diameter = _number(drill_node[1])
                vias.append({"center": at, "diameter": diameter})
        elif item[0] in {"gr_line", "gr_arc"}:
            layer_node = _child(item, "layer")
            if not layer_node or layer_node[1] != "Edge.Cuts":
                continue
            points = [_xy(_child(item, name)) for name in ("start", "mid", "end") if _child(item, name)]
            edge_control_points.extend(points)
            if item[0] == "gr_line":
                edge_lines.append({"start": points[0], "end": points[-1]})
    return {
        "footprints": footprints,
        "vias": vias,
        "edge_lines": edge_lines,
        "edge_control_points": edge_control_points,
    }


def source_drill_geometry(board: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {"PTH": [], "NPTH": []}
    for reference, footprint in board["footprints"].items():
        for pad in footprint["pads"]:
            drill = pad["drill"]
            if not drill:
                continue
            plating = "NPTH" if pad["type"] == "np_thru_hole" else "PTH"
            result[plating].append(
                {
                    "reference": reference,
                    "pad": pad["number"],
                    "center": pad["center"],
                    "shape": drill["shape"],
                    "size": drill["size"],
                }
            )
    result["PTH"].extend(
        {
            "reference": "<via>",
            "pad": "",
            "center": via["center"],
            "shape": "round",
            "size": (via["diameter"], via["diameter"]),
        }
        for via in board["vias"]
    )
    for records in result.values():
        records.sort(key=lambda item: (item["size"], item["center"], item["reference"], item["pad"]))
    return result


def source_control_flashes(
    board: dict[str, object], layer: str
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for reference, footprint in board["footprints"].items():
        selected = (layer == "F.Paste" and reference == "SW_RST1") or (
            layer in {"B.Cu", "B.Mask", "B.Paste"} and re.fullmatch(r"D\d+", reference)
        )
        if not selected:
            continue
        for pad in footprint["pads"]:
            if layer not in pad["layers"]:
                continue
            records.append(
                {
                    "reference": reference,
                    "pad": pad["number"],
                    "center": pad["center"],
                    "size": pad["size"],
                }
            )
    records.sort(key=lambda item: (item["reference"], item["pad"], item["center"]))
    return records


def source_j_bat_markings(board: dict[str, object]) -> dict[str, object]:
    errors: list[str] = []
    footprint = board["footprints"].get("J_BAT1")
    if footprint is None:
        return {"markings": {}, "errors": ["J_BAT1 footprint missing"]}
    pads = {pad["number"]: pad for pad in footprint["pads"]}
    for number, net in (("1", "BAT+"), ("2", "GND")):
        pad = pads.get(number)
        if pad is None:
            errors.append(f"J_BAT1 pad {number} missing")
        elif pad.get("net") != net:
            errors.append(
                f"J_BAT1 pad {number} net {pad.get('net')!r}, expected {net!r}"
            )
    visible = [
        item
        for item in footprint["texts"]
        if item["kind"] == "user" and item["layer"] == "F.SilkS" and not item["hidden"]
    ]
    expected = {
        "B+": {"local_center": (0.0, -1.65), "pad": "1"},
        "B-/GND": {"local_center": (2.54, 1.8), "pad": "2"},
    }
    markings: dict[str, dict[str, object]] = {}
    for text, contract in expected.items():
        matches = [item for item in visible if item["text"] == text]
        if len(matches) != 1:
            errors.append(f"J_BAT1 F.SilkS {text!r} count {len(matches)}, expected 1")
            continue
        item = matches[0]
        markings[text] = item
        if item["local_center"] != contract["local_center"]:
            errors.append(
                f"J_BAT1 F.SilkS {text!r} local center {item['local_center']}, "
                f"expected {contract['local_center']} above pad {contract['pad']}"
            )
        if item["local_rotation"] != 0.0:
            errors.append(f"J_BAT1 F.SilkS {text!r} local rotation must be 0 degrees")
        if item["size"] != (0.8, 0.8) or item["thickness"] != 0.12:
            errors.append(
                f"J_BAT1 F.SilkS {text!r} font {item['size']}/{item['thickness']}, "
                "expected 0.8x0.8/0.12 mm"
            )
    unexpected = sorted(item["text"] for item in visible if item["text"] not in expected)
    if unexpected:
        errors.append(f"J_BAT1 unexpected visible F.SilkS user text {unexpected}")
    return {"markings": markings, "errors": errors}


def source_j_bat_marking_errors(board: dict[str, object]) -> list[str]:
    return source_j_bat_markings(board)["errors"]


def build_board_bom(
    product: str, board_path: str, source_board_sha256: str, board: dict[str, object]
) -> dict[str, object]:
    footprints = board["footprints"]
    refs = set(footprints)
    switch_refs = sorted(
        (ref for ref in refs if re.fullmatch(r"SW\d+", ref)),
        key=lambda value: int(value[2:]),
    )
    diode_refs = sorted(
        (ref for ref in refs if re.fullmatch(r"D\d+", ref)),
        key=lambda value: int(value[1:]),
    )
    mounting_refs = sorted(
        (ref for ref in refs if re.fullmatch(r"MH\d+", ref)),
        key=lambda value: int(value[2:]),
    )
    line_items: list[dict[str, object]] = []

    def add(category: str, references: Iterable[str], identity: str, **fields: object) -> None:
        ordered = list(references)
        line_items.append(
            {"category": category, "quantity": len(ordered), "references": ordered, "identity": identity, **fields}
        )

    add(
        "key_switch_positions",
        switch_refs,
        "Choc V2/PG1353 bottom socket OR Cherry MX 5-pin direct solder",
        assembly_options=["choc_v2_socket", "mx_5pin_direct_solder"],
        mutually_exclusive=True,
        purchased_switch_manufacturer_mpn="pending_physical_procurement_gate",
    )
    add(
        "matrix_diode",
        diode_refs,
        "Diodes Inc 1N4148W-13-F / LCSC C112342 / Eleparts 3417687",
        manufacturer="Diodes Incorporated",
        manufacturer_part_number="1N4148W-13-F",
        lcsc_part_number="C112342",
        jlcpcb_part_number="C112342",
        eleparts_goods_number="3417687",
        assembly_side="bottom",
        polarity="pad_1_cathode_band",
    )
    if product in {"left", "right"}:
        add("controller_socket", ["U1"] if "U1" in refs else [], "nice!nano v2 24-pin socket carrier")
        add(
            "battery_pack",
            ["BAT1"] if "BAT1" in refs else [],
            "301230-class 3.7 V 100 mAh Li-Po with insulated leads",
            manufacturer_part_number="pending_physical_procurement_gate",
            protection_status="pending_physical_procurement_gate",
            maximum_swollen_thickness_mm="pending_physical_procurement_gate",
            lead_exit_drawing_sha256="pending_physical_procurement_gate",
        )
        add(
            "battery_direct_solder_termination",
            ["J_BAT1"] if "J_BAT1" in refs else [],
            "BAT_2Pin_PTH_DirectSolder",
            purchased_lead_drill_mm="pending_physical_procurement_gate",
        )
        add(
            "power_switch",
            ["SW_PWR1"] if "SW_PWR1" in refs else [],
            "IMMS-12V/BSI-10 nominal collision proxy; equivalence not assumed",
            manufacturer_part_number="pending_physical_procurement_gate",
            controlled_drawing_sha256="pending_physical_procurement_gate",
        )
        add(
            "reset_switch",
            ["SW_RST1"] if "SW_RST1" in refs else [],
            "NW3-A06-B3 / DeviceMart 1322056",
            manufacturer_part_number="NW3-A06-B3",
            devicemart_goods_number="1322056",
        )
        add(
            "mounting_hole",
            mounting_refs,
            "M1.4 service/retention, 1.60 mm NPTH",
            fitted_component=False,
        )
    return {
        "schema_version": 1,
        "requirement_ids": list(REQUIREMENT_IDS),
        "variant": "x3-v2",
        "product": product,
        "source_board": board_path,
        "source_board_sha256": source_board_sha256,
        "order_ready": False,
        "line_items": line_items,
    }


def bom_csv_bytes(bom: dict[str, object]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("category", "quantity", "references", "identity", "physical_status"))
    for item in bom["line_items"]:
        pending = "pending" if "pending_physical_procurement_gate" in json.dumps(item) else "controlled"
        writer.writerow(
            (
                item["category"],
                item["quantity"],
                ";".join(item["references"]),
                item["identity"],
                pending,
            )
        )
    return output.getvalue().encode("utf-8")


def _numbered_reference_key(reference: str) -> tuple[str, int]:
    match = re.fullmatch(r"([A-Z_]+)(\d+)", reference)
    if match is None:
        raise ValueError(f"reference is not a numbered designator: {reference!r}")
    return (match.group(1), int(match.group(2)))


def _bottom_fab_body_centroid(footprint: dict[str, object]) -> tuple[float, float]:
    points: list[tuple[float, float]] = []
    for segment in footprint["fab_segments"]:
        if segment["layer"] == "B.Fab":
            points.extend((tuple(segment["start"]), tuple(segment["end"])))
    if not points:
        raise ValueError(f"{footprint['reference']}: no B.Fab body geometry")
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return (round((min(xs) + max(xs)) / 2.0, 6), round((min(ys) + max(ys)) / 2.0, 6))


def build_jlcpcb_pcba_quote(
    product: str, board_path: str, source_board_sha256: str, board: dict[str, object]
) -> dict[str, object]:
    if product not in {"left", "right"}:
        raise ValueError(f"PCBA quote is only defined for left/right boards, got {product!r}")
    footprints = board["footprints"]
    diode_refs = sorted(
        (ref for ref in footprints if re.fullmatch(r"D\d+", ref)),
        key=_numbered_reference_key,
    )
    socket_refs = sorted(
        (ref for ref in footprints if re.fullmatch(r"SW\d+", ref)),
        key=_numbered_reference_key,
    )
    expected_count = {"left": 31, "right": 39}[product]
    if len(diode_refs) != expected_count or len(socket_refs) != expected_count:
        raise ValueError(
            f"{product}: expected {expected_count} diodes/sockets, "
            f"got {len(diode_refs)}/{len(socket_refs)}"
        )
    placements: list[dict[str, object]] = []
    for reference in diode_refs:
        footprint = footprints[reference]
        if footprint["name"] != "D_1N4148W_SOD123_HandSolder_DiodesInc":
            raise ValueError(f"{reference}: unexpected diode footprint {footprint['name']!r}")
        center = tuple(footprint["center"])
        placements.append(
            {
                "designator": reference,
                "mid_x_mm": round(float(center[0]), 6),
                "mid_y_mm": round(-float(center[1]), 6),
                "layer": "Bottom",
                "rotation_degrees": round(float(footprint["rotation"]) % 360.0, 6),
                "centroid_source": "footprint_origin",
            }
        )
    for reference in socket_refs:
        footprint = footprints[reference]
        if footprint["name"] != "SW_Choc_V2_Socket_MX_THT":
            raise ValueError(f"{reference}: unexpected switch footprint {footprint['name']!r}")
        center = _bottom_fab_body_centroid(footprint)
        placements.append(
            {
                "designator": reference,
                "mid_x_mm": round(float(center[0]), 6),
                "mid_y_mm": round(-float(center[1]), 6),
                "layer": "Bottom",
                "rotation_degrees": round(float(footprint["rotation"]) % 360.0, 6),
                "centroid_source": "bottom_fab_body_bbox",
            }
        )
    return {
        "schema_version": 1,
        "requirement_ids": ["CON-ARCH-004"],
        "variant": "x3-v2",
        "product": product,
        "source_board": board_path,
        "source_board_sha256": source_board_sha256,
        "purpose": "jlcpcb_price_quote_only",
        "order_ready": False,
        "line_items": [
            {
                "comment": "Diodes Inc 1N4148W-13-F",
                "designators": diode_refs,
                "footprint": "SOD-123",
                "lcsc_part_number": "C112342",
            },
            {
                "comment": "Kailh CPG135001S30 Choc hot-swap socket",
                "designators": socket_refs,
                "footprint": "Kailh CPG135001S30",
                "lcsc_part_number": "C5333465",
            },
        ],
        "placements": placements,
    }


def jlcpcb_pcba_bom_csv_bytes(quote: dict[str, object]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("Comment", "Designator", "Footprint", "LCSC Part #"))
    for item in quote["line_items"]:
        writer.writerow(
            (
                item["comment"],
                ",".join(item["designators"]),
                item["footprint"],
                item["lcsc_part_number"],
            )
        )
    return output.getvalue().encode("utf-8")


def jlcpcb_pcba_cpl_csv_bytes(quote: dict[str, object]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("Designator", "Mid X", "Mid Y", "Layer", "Rotation"))
    for item in quote["placements"]:
        writer.writerow(
            (
                item["designator"],
                f"{float(item['mid_x_mm']):.4f}mm",
                f"{float(item['mid_y_mm']):.4f}mm",
                item["layer"],
                f"{float(item['rotation_degrees']):.3f}",
            )
        )
    return output.getvalue().encode("utf-8")
