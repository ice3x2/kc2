"""OPS-ARCH-007: source-bound first-product PCB-only release (default dry run).

Review booleans are signed-off engineering claims, not self-generated evidence.
This tool independently checks their byte bindings and plotted geometry. Physical
qualification remains false; it does not place an order or authorize PCBA uploads.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import tempfile
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from tools.kc2_x3_v2_output_geometry import parse_board, source_drill_geometry, source_control_flashes
from tools.canonical_hash import sha256_file as canonical_sha256
from tools.verify_kc2_x3_v2_fabrication import (
    REQUIRED_SUFFIXES, EXPECTED_FILE_FUNCTIONS, inspect_excellon,
    inspect_gerber, inspect_gerber_flashes, _geometry_delta_errors,
    parse_drill_tools, inspect_mounting_reference_glyphs, inspect_j_bat_marking_glyphs,
)

ROOT = Path(__file__).resolve().parents[1]
RAW = 'hardware/kicad/fabrication_review/v1-recess-20260906-r3'
DEFAULT_OUTPUT = ROOT / 'hardware/kicad/first_order/solid-floor-20260907-r4'
CHECKS = ('current_drc', 'board_geometry_and_connectivity', 'component_pinout_review',
          'socket_nominal_fit_review', 'housing_clearance_review', 'gerber_drill_inspection',
          'fullboard_and_zoom_visual_review', 'one_to_one_mechanical_review',
          'regeneration_reproducibility', 'independent_review')
REVIEWS = ('component_pinout', 'socket_fit', 'visual', 'mechanical_1to1', 'independent', 'digital_verification')
FABRICATION_PROFILE = {
    'scope': 'PCB fabrication only; no PCBA upload or purchasing operation',
    'layers': 2, 'material': 'FR4', 'thickness_mm': 1.6, 'copper_oz': 1,
    'order_finish_selection': 'ENIG', 'gerber_job_finish': 'None (not an order finish selection)',
    'soldermask': 'green', 'silkscreen': 'white', 'via_drill_mm': 0.30,
    'via_tenting': 'Isolated vias tented; same-net pad-mask overlap exceptions remain exposed',
    'via_mask_overlap_exceptions': [
        {'side': 'left', 'xy_mm': [136.5, 59.4], 'layers': ['F.Mask', 'B.Mask'], 'pad': 'U1/D5', 'net': 'L_COL1'},
        {'side': 'right', 'xy_mm': [73.5, 59.5], 'layers': ['F.Mask', 'B.Mask'], 'pad': 'U1/D18', 'net': 'R_COL5'},
        {'side': 'right', 'xy_mm': [90.7545, 127.917], 'layers': ['B.Mask'], 'pad': 'D27/1', 'net': 'R_ROW3'},
    ],
    'filled_or_capped_via_service': False,
    'via_residual_risk': 'Hand-solder wicking at exposed same-net vias; not a claim that all vias are mask covered',
    'shared_locator_npth': {'diameter_mm': 2.60, 'local_x_mm': [-5.45,5.45],
        'shape': 'circular_drilled_not_routed_slot', 'assumed_diameter_tolerance_mm': .08,
        'assumed_position_tolerance_per_axis_mm': .05,
        'basis': 'JLCPCB NPTH guide states approximately+/-0.08 mm; capability table position+/-0.05 mm. Bounded supplier assumption, not measured lot guarantee; confirm in order remarks. Non-plated slot+/-0.20 mm is not interchangeable.',
        'source': 'https://jlcpcb.com/blog/npth-design-guide'},
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_inputs(side: str) -> list[str]:
    suffixes = list(REQUIRED_SUFFIXES.values()) + [
        '-job.gbrjob', '-PTH.drl', '-NPTH.drl', '-PTH-drl_map.gbr',
        '-NPTH-drl_map.gbr', '-drill-report.txt']
    return [f'{RAW}/{side}/kc2_{side}{suffix}' for suffix in suffixes]


def required_inputs() -> list[str]:
    return [f'hardware/kicad/kc2_{side}/kc2_{side}.{ext}'
            for side in ('left', 'right') for ext in ('kicad_pcb', 'kicad_pro', 'drc.json')] + [
                'hardware/kicad/kc2_drc_evidence.json',
                'hardware/kicad/autoroute/kc2_mx_solder_support_routes.json',
            ] + raw_inputs('left') + raw_inputs('right')


def safe_path(root: Path, rel: str) -> Path:
    if not isinstance(rel, str) or '\\' in rel or Path(rel).is_absolute() or '..' in Path(rel).parts:
        raise ValueError(f'unsafe evidence path: {rel!r}')
    path = (root / rel).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f'evidence escapes repository: {rel}')
    return path


def manual_bom(board: dict, side: str) -> dict:
    fps = board['footprints']
    switches = sorted((r for r in fps if re.fullmatch(r'SW\d+', r)), key=lambda r: int(r[2:]))
    diodes = sorted((r for r in fps if re.fullmatch(r'D\d+', r)), key=lambda r: int(r[1:]))
    contacts = [{'reference': r, 'pads': [p['number'] for p in fps[r]['pads']
                 if p['type'] == 'thru_hole']} for r in switches]
    if len(switches) != {'left': 31, 'right': 39}[side] or len(diodes) != len(switches):
        raise ValueError(f'{side}: unexpected switch/diode count')
    if any(len(c['pads']) != 2 for c in contacts):
        raise ValueError(f'{side}: expected exactly two electrical MX receptacles per switch')
    return {
        'selected_switch_assembly': 'mx_receptacle_with_plate',
        'assembly_service': 'none_hand_assembly', 'parts_procurement': 'user_external_mall_procurement',
        'machine_placement_requested': False, 'bom_cpl_upload_authorization': False,
        'choc_socket_population_for_selected_assembly': False,
        'alternative_assemblies_mutually_exclusive': True,
        'alternative_assemblies': ['choc_v1_bottom_socket_with_ring', 'choc_v2_bottom_socket', 'mx_5pin_top_direct_solder'],
        'alternative_assembly_warning': 'Do not populate a Choc socket and MX receptacles/switch on the same key. V1 uses uncut side posts with shared NPTHs and its central ring; contact engagement remains post-receipt pending. The MX plate-lid is not a low-profile Choc retention plate.',
        'mx_receptacles': {'quantity': 2 * len(switches), 'contacts': contacts,
            'specification': 'Open-bottom hat: length 3.00 mm; barrel OD 1.45 mm; flange OD 2.00 mm, thickness 0.20 mm',
            'supplier_trace': 'https://ko.aliexpress.com/item/1005010364025678.html',
            'drawing': 'https://ae-pic-a1.aliexpress-media.com/kf/S4b47dab427cd4b539a50618bf16a62d9J.jpg',
            'nominal_pth_mm': 1.60, 'nominal_diametral_clearance_mm': 0.15,
            'tolerances_and_flat_blade_limits': 'unknown; nominal clearance is not worst-case fit',
            'qualification': 'post_receipt_pending', 'plate_lid_required': True},
        'diodes': {'quantity': len(diodes), 'references': diodes, 'manufacturer': 'Diodes Incorporated',
                   'mpn': '1N4148W-13-F', 'package': 'SOD-123', 'drawing': 'DS30086 Rev. 31-2',
                   'orientation': 'Bottom side; cathode band to pad 1 / row; pad 2 anode to per-key switch'},
        'other_board_items': [{'reference': r, 'value': fp['value'], 'footprint': fp['name'],
                               'quantity': 1, 'procurement_status': 'see source-bound component review'}
                              for r, fp in sorted(fps.items()) if r not in switches + diodes and not r.startswith('MH')],
        'mx_switches': {'quantity': len(switches), 'references': switches,
                        'specification': 'Selected TTC Bluish White / Tactile Silent 42gf 3-pin MX switch; existing generic5-pin locator support retained. Exact blade/spring contact limits unknown; post-receipt qualification pending',
                        'supplier_trace': 'https://ko.aliexpress.com/item/1005012442816250.html',
                        'variant_identity': 'User-selected seller listing; do not infer V2 or another manufacturer order code'},
        'stack': 'Closed-floor lower housing / 1.60 mm PCB / recessed printed MX plate-lid; PCB bottom/top2.50/4.10 mm unchanged; floor top-1.00 mm, bottom-2.20 mm. Existing M1.4 holes; no stabilizers. Remove PCB before soldering or lead trimming.',
        'closed_floor': {'thickness_mm':1.2,'top_z_mm':-1.0,'bottom_z_mm':-2.2,
            'maximum_under_pcb_projection_mm':2.9,'nominal_floor_clearance_at_limit_mm':.6,
            'engineering_print_allowance_mm':.3,'remaining_clearance_mm':.3,
            'qualification':'Inspect all actual leads/posts/solder before closing; unknown dimensions are not zero. Do not grind or force functional switch/socket parts.'},
        'silicone_feet': {'total_keyboard_quantity':12,'nominal_quantity_this_side':4 if side=='left' else 8,
            'bonding_diameter_mm':8,'physical_qualification_complete':False,
            'specification':'Four non-collinear flat diameter8 mm adhesive bonding regions per printable lower part. Silicone thickness, adhesive, slip resistance and retention are not yet qualified physical-part specifications.'},
        'fasteners': '7.5 mm nominal under-head M1.4 screw for the recessed lid; 2.20 mm nominal receiver insertion / 0.60 mm tip reserve. Monotaro40411061 M1.4x7.5 pitch0.3 is the dimensional candidate. No8/9/10 mm substitution without recalculation. Length tolerance, receiver/material and physical retention remain post-receipt pending.',
    }


def inspect_solder_land_flashes(payload: bytes) -> list[dict]:
    """Read actual O or strictly recognized KiCad rounded-line macros.

    Unknown macros, changed primitive exposure, missing circles and unsupported
    transformations are rejected by omission, causing the exact expected-land
    comparison to fail. A macro's name alone is never trusted as geometry.
    """
    text = payload.decode('ascii', errors='strict')
    fmt = re.search(r'%FSLAX\d(\d)Y\d(\d)\*%', text)
    if not fmt or fmt[1] != fmt[2] or '%MOMM*%' not in text or re.search(r'%(?:LR|LM|LS)',text):
        return []
    scale = 10**int(fmt[1])
    recognized = set()
    template = ['20,1,$1,$2,$3,$4,$5,0','1,1,$1,$2,$3','1,1,$1,$4,$5']
    for name, body in re.findall(r'%AM([A-Za-z][A-Za-z0-9_]*)\*([^%]*)%',text):
        primitives = [line.strip() for line in body.split('*') if line.strip() and not line.strip().startswith('0 ')]
        if primitives == template:
            recognized.add(name)
    apertures = {}
    for code, kind, params in re.findall(r'%ADD(\d+)([A-Za-z][A-Za-z0-9_]*),([^*]+)\*%',text):
        try:
            values = [float(x) for x in params.split('X')]
        except ValueError:
            continue
        if not all(math.isfinite(x) for x in values):
            continue
        if kind == 'O' and len(values) == 2 and min(values) > 0:
            width,height=values
            diameter=min(values)
            extent=(max(values)-diameter)/2
            ends=[(-extent,0),(extent,0)] if width>=height else [(0,-extent),(0,extent)]
            apertures[int(code)]=dict(size=(width,height),capsule={'diameter':diameter,'ends':ends})
        elif kind in recognized and len(values)==6 and values[0]>0 and values[5]==0:
            diameter,x1,y1,x2,y2,_=values
            if abs(x1+x2)>1e-6 or abs(y1+y2)>1e-6:
                continue
            apertures[int(code)]=dict(size=(diameter,round(diameter+math.hypot(x2-x1,y2-y1),6)),
                capsule={'diameter':diameter,'ends':sorted([(x1,-y1),(x2,-y2)])})
    active=None
    reference=pad=''
    result=[]
    for line in text.splitlines():
        match=re.fullmatch(r'D(\d+)\*',line)
        if match:
            active=int(match[1]); continue
        match=re.fullmatch(r'%TO\.C,([^*]+)\*%',line)
        if match:
            reference,pad=match[1],''; continue
        match=re.fullmatch(r'%TO\.P,([^,]+),([^*]+)\*%',line)
        if match:
            reference,pad=match.groups(); continue
        if line=='%TD*%':
            reference=pad=''; continue
        match=re.fullmatch(r'X(-?\d+)Y(-?\d+)D03\*',line)
        if match and active in apertures:
            result.append(dict(reference=reference,pad=pad,
                center=(round(int(match[1])/scale,6),round(-int(match[2])/scale,6)),**apertures[active]))
    return result


def source_solder_land(pad: dict, reference: str) -> dict:
    width,height=pad['size']
    angle=pad['rotation']
    # parse_board exposes swapped dimensions only for orthogonal90-degree pads.
    if round(angle % 180,6)==90:
        width,height=height,width
    extent=(max(width,height)-min(width,height))/2
    dx,dy=(extent,0) if width>=height else (0,extent)
    radians=math.radians(angle)
    x=dx*math.cos(radians)+dy*math.sin(radians)
    y=-dx*math.sin(radians)+dy*math.cos(radians)
    return dict(reference=reference,pad=pad['number'],center=pad['center'],size=pad['size'],
                capsule={'diameter':min(width,height),'ends':sorted([(-x,-y),(x,y)])})


def solder_land_errors(expected: list[dict], actual: list[dict], label: str) -> list[str]:
    errors=_geometry_delta_errors(expected,actual,label)
    for wanted in expected:
        found=next((p for p in actual if all(abs(a-b)<=.0001 for a,b in zip(p['center'],wanted['center']))),None)
        if found is None:
            continue
        w,a=wanted['capsule'],found['capsule']
        ends_match=any(all(abs(x-y)<=.0001 for left,right in zip(w['ends'],order)
                          for x,y in zip(left,right))
                       for order in (a['ends'],list(reversed(a['ends']))))
        if abs(w['diameter']-a['diameter'])>.0001 or not ends_match:
            errors.append(f"{label}: {wanted['reference']}/{wanted['pad']} oval capsule orientation/shape mismatch")
    return errors


def inspect_side(root: Path, side: str) -> dict:
    errors = []
    source = root / f'hardware/kicad/kc2_{side}/kc2_{side}.kicad_pcb'
    board = parse_board(source)
    bom = manual_bom(board, side)
    drc = json.loads(source.with_suffix('.drc.json').read_text(encoding='utf-8'))
    for key in ('violations', 'unconnected_items', 'schematic_parity'):
        if drc.get(key) != []:
            errors.append(f'{side}: DRC {key} missing or not empty')
    folder = root / RAW / side
    drill_geometry = source_drill_geometry(board)
    report = (folder / f'kc2_{side}-drill-report.txt').read_text(encoding='utf-8')
    tools = parse_drill_tools(report)
    for plating in ('PTH', 'NPTH'):
        actual = inspect_excellon((folder / f'kc2_{side}-{plating}.drl').read_bytes())
        errors += _geometry_delta_errors(drill_geometry[plating], actual, f'{side} {plating}')
        expected_tools = dict(Counter(f"{min(item['size']):.3f}" for item in actual))
        if tools[plating] != expected_tools:
            errors.append(f'{side} {plating}: drill report tool/count mismatch')
        if f"Total {'unplated' if plating == 'NPTH' else 'plated'} holes count {len(actual)}" not in report:
            errors.append(f'{side} {plating}: drill report total mismatch')
        map_data = inspect_gerber((folder / f'kc2_{side}-{plating}-drl_map.gbr').read_bytes())
        if not map_data['has_end_of_file'] or not map_data['operation_count']:
            errors.append(f'{side} {plating}: invalid drill map')
    job = json.loads((folder / f'kc2_{side}-job.gbrjob').read_text(encoding='utf-8'))
    specs = job.get('GeneralSpecs', {})
    if specs.get('LayerNumber') != 2 or specs.get('BoardThickness') != 1.6:
        errors.append(f'{side}: job stack must be two-layer 1.60 mm')
    if {x.get('Path') for x in job.get('FilesAttributes', [])} != {f'kc2_{side}{s}' for s in REQUIRED_SUFFIXES.values()}:
        errors.append(f'{side}: job Gerber inventory mismatch')
    for layer, suffix in REQUIRED_SUFFIXES.items():
        payload = (folder / f'kc2_{side}{suffix}').read_bytes()
        info = inspect_gerber(payload)
        if info['file_function'] != EXPECTED_FILE_FUNCTIONS[layer] or not info['has_end_of_file'] or not info['operation_count']:
            errors.append(f'{side} {layer}: invalid Gerber content/function')
        actual = inspect_gerber_flashes(payload)
        expected = source_control_flashes(board, layer)
        selected = [p for p in actual if (layer == 'F.Paste' and p['reference'] == 'SW_RST1') or
                    (layer in ('B.Cu', 'B.Mask', 'B.Paste') and re.fullmatch(r'D\d+', p['reference']))]
        errors += _geometry_delta_errors(expected, selected, f'{side} {layer} controls')
        # Actual enlarged U1/MX exposed land flashes, not just drill diameters.
        if layer in ('F.Cu', 'B.Cu', 'F.Mask', 'B.Mask'):
            wanted = [source_solder_land(p,r)
                      for r, fp in board['footprints'].items() for p in fp['pads']
                      if (r == 'U1' or re.fullmatch(r'SW\d+', r)) and p['type'] == 'thru_hole']
            # Mask attributes omit pad numbers; B.Cu has other same-number
            # Choc lands. Select the exact PTH centers, not duplicate pad IDs.
            selected = [p for p in inspect_solder_land_flashes(payload) if any(
                all(abs(a - b) <= 0.0001 for a, b in zip(p['center'], w['center']))
                for w in wanted)]
            errors += solder_land_errors(wanted, selected, f'{side} {layer} solder lands')
        if layer == 'F.Silkscreen':
            centers = {r: fp['center'] for r, fp in board['footprints'].items() if re.fullmatch(r'MH\d+', r)}
            if len(centers) != {'left': 8, 'right': 9}[side]:
                errors.append(f'{side}: mounting count mismatch')
            errors += inspect_mounting_reference_glyphs(payload, centers)['errors']
            errors += inspect_j_bat_marking_glyphs(payload, board)['errors']
    return {'errors': errors, 'bom': bom, 'drill_counts': {k: len(v) for k, v in drill_geometry.items()}}


def digital_report_inputs(role: str) -> list[str]:
    """Fixed report provenance inventory, using RAW byte hashes (not canonical)."""
    if role == 'board':
        return required_inputs() + ['tools/verify_kc2_x3_v2.py']
    if role != 'housing':
        raise ValueError(f'Unknown digital report role: {role}')
    paths = ['hardware/case/kc2_housing_manifest.json',
             'hardware/case/kc2_left_silicone_foot_layout.svg',
             'hardware/case/kc2_right_silicone_foot_layout.svg',
             'hardware/case/kc2_mx_upper_housing_manifest.json',
             'hardware/case/kc2_fusion_export_result.json',
             'tools/generate_kc2_x3_v2_housings.py',
             'tools/generate_kc2_mx_upper_housings.py',
             'tools/verify_kc2_mx_housing_contract.py',
             'tools/verify_kc2_housing_f3d.py']
    for side in ('left', 'right'):
        paths.append(f'hardware/kicad/kc2_{side}/kc2_{side}.kicad_pcb')
        for kind in ('lower', 'mx_upper'):
            stem = f'hardware/case/kc2_{side}_{kind}_housing'
            paths += [stem + ext for ext in ('.step', '.f3d')]
            paths += [stem + suffix + '.stl' for suffix in
                      ([''] if side == 'left' else ['_part_a', '_part_b'])]
    return paths


def inspect_digital_reports(evidence: dict, root: Path) -> list[str]:
    """Machine errors cannot be waived by human checkboxes or post-receipt policy."""
    errors = []
    roles = evidence.get('digital_reports')
    if not isinstance(roles, dict) or set(roles) != {'board', 'housing'}:
        return ['typed board/housing digital_reports are required']
    bindings = evidence['bindings']
    refs = evidence['reviews']['digital_verification']
    for role, requirement in [('board', 'CON-ARCH-004'), ('housing', 'CON-ARCH-006')]:
        try:
            rel = roles[role]
            if not isinstance(rel, str) or rel not in bindings or rel not in refs:
                raise ValueError('report must be a bound digital_verification reference')
            report = json.loads(safe_path(root, rel).read_text(encoding='utf-8'))
            if not isinstance(report, dict) or report.get('requirement') != requirement:
                raise ValueError('wrong report requirement/type')
            if report.get('errors') != []:
                raise ValueError('machine report has missing or nonempty errors')
            sources = report.get('source_sha256')
            if not isinstance(sources, dict):
                raise ValueError('missing raw source_sha256 report provenance')
            for path in digital_report_inputs(role):
                if path not in sources or sources[path] != bindings.get(path) or sources[path] != sha256(safe_path(root, path)):
                    raise ValueError(f'stale/missing machine report source: {path}')
            if role == 'housing':
                if report.get('digital_valid') is not True or report.get('native_archive_blockers') != []:
                    raise ValueError('housing digital/native archive verification failed')
                pending = report.get('qualification_blockers')
                if not isinstance(pending, list) or any(not isinstance(v, str) for v in pending):
                    raise ValueError('malformed physical qualification blockers')
                floor = report.get('closed_floor')
                if not isinstance(floor, dict) or floor.get('digital_valid') is not True or floor.get('errors') != []:
                    raise ValueError('current closed-floor geometry verification is required')
                for key, expected in [('floor_thickness_mm',1.2),('floor_top_z_mm',-1.0),
                                      ('floor_bottom_z_mm',-2.2),('bonding_pad_diameter_mm',8)]:
                    value=floor.get(key)
                    if type(value) not in (int,float) or not math.isfinite(value) or abs(value-expected)>1e-6:
                        raise ValueError(f'closed-floor {key} does not match current SRS')
                if (type(floor.get('bonding_pad_count')) is not int or floor['bonding_pad_count']<9
                        or type(floor.get('printable_part_count')) is not int or floor['printable_part_count']!=3):
                    raise ValueError('closed-floor three-part bonding layout verification missing')
            else:
                if report.get('connectivity_errors') != {'left': [], 'right': []}:
                    raise ValueError('board connectivity verification failed or missing')
                boards = report.get('boards')
                if not isinstance(boards, dict) or set(boards) != {'left', 'right'}:
                    raise ValueError('both board reports are required')
                for side, board in boards.items():
                    if not isinstance(board, dict) or not board:
                        raise ValueError(f'{side}: board report is missing')
                    for key, value in board.items():
                        if (key.endswith('_errors') or key.endswith('_mismatches')) and value != []:
                            raise ValueError(f'{side}: reported {key}')
                    for key in ('drc_violation_count', 'drc_unconnected_count'):
                        if type(board.get(key)) is not int or board[key] != 0:
                            raise ValueError(f'{side}: invalid {key}')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f'{role} digital report invalid: {exc}')
    return errors


def validate(evidence: dict, root: Path = ROOT) -> dict:
    errors = []
    result = {'requirement': 'OPS-ARCH-007', 'eligible_to_build': False,
              'first_order_ready': False, 'physical_qualification_complete': False,
              'bom_cpl_upload_authorization': False, 'errors': errors, 'sides': {}}
    for key, expected in (('schema_version', 1), ('target', 'kc2-x3-v2'),
                          ('selected_switch_assembly', 'mx_receptacle_with_plate'),
                          ('known_blockers', []), ('digital_errors', [])):
        if evidence.get(key) != expected:
            errors.append(f'evidence {key} missing or invalid')
    checks = evidence.get('checks', {})
    for key in CHECKS:
        if not isinstance(checks, dict) or checks.get(key) is not True:
            errors.append(f'unchecked digital review: {key}')
    bindings = evidence.get('bindings', {})
    if not isinstance(bindings, dict):
        bindings = {}
        errors.append('bindings must be a path-to-SHA256 object')
    for rel in required_inputs():
        if rel not in bindings:
            errors.append(f'missing required binding: {rel}')
    reviews = evidence.get('reviews', {})
    for role in REVIEWS:
        refs = reviews.get(role) if isinstance(reviews, dict) else None
        if not isinstance(refs, list) or not refs or any(not isinstance(r, str) or r not in bindings for r in refs):
            errors.append(f'missing bound review: {role}')
    for key in ('residual_risks', 'post_receipt_acceptance'):
        values = evidence.get(key)
        if not isinstance(values, list) or not values or any(not isinstance(v, str) or not v.strip() for v in values):
            errors.append(f'missing explicit {key}')
    for rel, digest in bindings.items():
        try:
            path = safe_path(root, rel)
            if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest) or sha256(path) != digest:
                errors.append(f'stale hash: {rel}')
        except (ValueError, OSError) as exc:
            errors.append(str(exc))
    if errors:
        return result
    errors.extend(inspect_digital_reports(evidence, root))
    try:
        sidecar = json.loads((root / 'hardware/kicad/kc2_drc_evidence.json').read_text(encoding='utf-8'))
        for side in ('left', 'right'):
            record = sidecar['boards'][side]
            for field, ext in (('board', 'kicad_pcb'), ('project', 'kicad_pro'), ('drc_report', 'drc.json')):
                rel = f'hardware/kicad/kc2_{side}/kc2_{side}.{ext}'
                if record[f'{field}_path'] != rel or record[f'{field}_sha256'] != canonical_sha256(root / rel):
                    errors.append(f'{side}: stale DRC sidecar {field} binding')
            if record.get('default_clearance_mm') != 0.3:
                errors.append(f'{side}: DRC clearance evidence is not 0.30 mm')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f'DRC binding invalid: {exc}')
    for side in ('left', 'right'):
        try:
            result['sides'][side] = inspect_side(root, side)
            errors.extend(result['sides'][side]['errors'])
        except (ValueError, KeyError, OSError, TypeError) as exc:
            errors.append(f'{side}: inspection failed: {exc}')
    result['eligible_to_build'] = not errors
    return result


def verify_package(output: Path) -> list[str]:
    errors = []
    try:
        manifest = json.loads((output / 'manifest.json').read_text(encoding='utf-8'))
        evidence = json.loads((output / 'review-evidence.json').read_text(encoding='utf-8'))
        if manifest['source_sha256'] != evidence['bindings']:
            errors.append('review/source binding mismatch')
        if (manifest.get('bom_cpl_upload_authorization') is not False
                or manifest.get('physical_qualification_complete') is not False
                or manifest.get('machine_placement_requested') is not False
                or manifest.get('assembly_service') != 'none_hand_assembly'):
            errors.append('package conflates first-order and assembly/physical approval')
        expected_outputs = {'review-evidence.json', 'digital-validation.json',
                            'fabrication-profile.json'} | {
            f'kc2_{side}-{suffix}' for side in ('left', 'right')
            for suffix in ('manual-mx-bom.json', 'pcb-fabrication-only.zip')}
        if (not isinstance(manifest.get('output_sha256'), dict)
                or set(manifest['output_sha256']) != expected_outputs):
            errors.append('package output hashes must bind the exact seven required outputs')
        if {p.name for p in output.iterdir()} != expected_outputs | {'manifest.json'}:
            errors.append('package directory inventory differs from required delivery')
        for side in ('left', 'right'):
            item = manifest['packages'][side]
            if item['file'] != f'kc2_{side}-pcb-fabrication-only.zip':
                errors.append(f'{side}: unexpected archive path')
            archive = safe_path(output, item['file'])
            expected_entries = {Path(rel).name: manifest['source_sha256'][rel] for rel in raw_inputs(side)}
            if item['entries'] != expected_entries:
                errors.append(f'{side}: ZIP inventory/hash is not exact reviewed fabrication inputs')
            if sha256(archive) != item['sha256']:
                errors.append(f'{side}: ZIP hash mismatch')
            with ZipFile(archive) as package:
                if sorted(package.namelist()) != sorted(item['entries']):
                    errors.append(f'{side}: ZIP inventory mismatch')
                for name, digest in item['entries'].items():
                    if hashlib.sha256(package.read(name)).hexdigest() != digest:
                        errors.append(f'{side}: ZIP entry hash mismatch: {name}')
        for name, digest in manifest['output_sha256'].items():
            if sha256(safe_path(output, name)) != digest:
                errors.append(f'output hash mismatch: {name}')
    except (OSError, ValueError, KeyError, TypeError, BadZipFile) as exc:
        errors.append(f'package invalid: {exc}')
    return errors


def build(evidence: dict, root: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(f'No overwrite allowed: {output}')
    if not output.resolve().is_relative_to((root / 'hardware/kicad/first_order').resolve()):
        raise ValueError('Output must be beneath hardware/kicad/first_order/')
    report = validate(evidence, root)
    if not report['eligible_to_build']:
        raise ValueError(json.dumps(report['errors'], ensure_ascii=False))
    output.parent.mkdir(parents=True, exist_ok=True)
    # Never expose a half-written release or overwrite a historical artifact.
    with tempfile.TemporaryDirectory(prefix='.building-', dir=output.parent) as temp:
        stage = Path(temp) / 'release'
        stage.mkdir()
        def save(name, data):
            (stage / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        save('review-evidence.json', evidence)
        save('digital-validation.json', report)
        save('fabrication-profile.json', FABRICATION_PROFILE)
        manifest = {'schema_version': 1, 'requirement': 'OPS-ARCH-007',
                    'first_order_ready': False, 'physical_qualification_complete': False,
                    'assembly_service': 'none_hand_assembly', 'machine_placement_requested': False,
                    'bom_cpl_upload_authorization': False, 'packages': {}, 'output_sha256': {},
                    'source_sha256': evidence['bindings'], 'residual_risks': evidence['residual_risks'],
                    'post_receipt_acceptance': evidence['post_receipt_acceptance']}
        for side in ('left', 'right'):
            save(f'kc2_{side}-manual-mx-bom.json', report['sides'][side]['bom'])
            name = f'kc2_{side}-pcb-fabrication-only.zip'
            entries = {}
            with ZipFile(stage / name, 'x', compression=ZIP_DEFLATED) as package:
                for rel in raw_inputs(side):
                    payload = (root / rel).read_bytes()
                    digest = hashlib.sha256(payload).hexdigest()
                    if digest != evidence['bindings'][rel]:
                        raise ValueError(f'Input changed during packaging: {rel}')
                    entry = Path(rel).name
                    package.writestr(entry, payload)
                    entries[entry] = digest
            manifest['packages'][side] = {'file': name, 'sha256': sha256(stage / name), 'entries': entries}
        for path in stage.iterdir():
            manifest['output_sha256'][path.name] = sha256(path)
        # Recheck every source/review byte before publication, not only ZIP inputs.
        for rel, digest in evidence['bindings'].items():
            if sha256(safe_path(root, rel)) != digest:
                raise ValueError(f'Input changed during packaging: {rel}')
        save('manifest.json', manifest)
        failures = verify_package(stage)
        if failures:
            raise ValueError(str(failures))
        manifest['first_order_ready'] = True
        save('manifest.json', manifest)
        stage.rename(output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--evidence', type=Path)
    mode.add_argument('--verify-package', type=Path, help='Recheck package bytes and current source-bound evidence')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--build', action='store_true', help='Create PCB-only ZIPs after validation; never order or upload')
    args = parser.parse_args()
    try:
        if args.verify_package:
            if args.build:
                raise ValueError('--build cannot accompany --verify-package')
            errors = verify_package(args.verify_package)
            evidence = json.loads((args.verify_package / 'review-evidence.json').read_text(encoding='utf-8'))
            errors.extend(validate(evidence)['errors'])
            print(json.dumps({'first_order_ready': not errors, 'physical_qualification_complete': False, 'errors': errors}, indent=2))
            return 2 if errors else 0
        evidence = json.loads(args.evidence.read_text(encoding='utf-8'))
        report = build(evidence, ROOT, args.output) if args.build else validate(evidence)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report.get('first_order_ready') or report.get('eligible_to_build') else 2
    except (OSError, ValueError) as exc:
        print(json.dumps({'first_order_ready': False, 'errors': [str(exc)]}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
