"""CON-ARCH-006 read-only PCB insertion/registration diagnostics on current STL.

This samples horizontal sections, not a general continuous collision solver.
Print-error scenarios are sensitivity inputs, not measured printer accuracy.
No fabrication or model files are modified.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import trimesh
from shapely.geometry import GeometryCollection, Polygon

ROOT = Path(__file__).resolve().parents[1]


def horizontal_section(mesh, z):
    section = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
    result = GeometryCollection()
    if section is not None:
        for points in section.discrete:
            polygon = Polygon(points[:, :2])
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            result = result.symmetric_difference(polygon)
    return result


def insertion_sections(mesh, board, seat):
    # Include every distinct mesh vertex-height band above the support plane.
    levels = sorted(set([seat] + [float(v) for v in np.unique(np.round(mesh.vertices[:, 2], 5)) if v > seat + 1e-5]))
    result = []
    for lo, hi in zip(levels, levels[1:]):
        z = (lo + hi) / 2
        section = horizontal_section(mesh, z)
        result.append(dict(z_mm=z, pcb_overlap_mm2=board.intersection(section).area,
                           gap_mm=board.distance(section) if not section.is_empty else None))
    return result


def overlap_depth(tip, entrance, roof, lift):
    return max(0., min(tip, roof + lift) - (entrance + lift))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    from tools.generate_kc2_magnetic_housings import load_plans
    models = ROOT / 'hardware/MODELS'
    paths = sorted((ROOT / 'hardware/PCB').rglob('*.kicad_pcb'))
    paths += sorted(models.glob('*.stl'))
    paths += [Path(__file__), ROOT / 'tools/test_kc2_pcb_seating.py']
    bindings = {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}
    plans, _, _ = load_plans()
    rows = {}
    for side in ('left', 'right'):
        board = plans[side]['board']
        for magnetic in (False, True):
            suffix = '_magnetic' if magnetic else ''
            names = [f'kc2_left_lower_housing{suffix}.stl'] if side == 'left' else [
                f'kc2_right_lower_housing_part_{part}{suffix}.stl' for part in ('a', 'b')]
            mesh = trimesh.util.concatenate([trimesh.load(models / name, force='mesh') for name in names])
            print('Inspect', side, suffix or 'normal', flush=True)
            sections = insertion_sections(mesh, board, 2.5)
            wall = horizontal_section(mesh, 3.3)
            scenarios = []
            for extra in (0., .1, .2, .3, .35, .4):
                envelope = board.buffer(extra, join_style=2) if extra else board
                scenarios.append(dict(combined_inward_xy_error_mm=extra,
                    overlap_mm2=envelope.intersection(wall).area,
                    residual_gap_mm=envelope.distance(wall)))
            rows[side + (':magnetic' if magnetic else ':normal')] = dict(
                files=names, board_bounds_mm=list(board.bounds), sections=sections,
                maximum_sampled_pcb_overlap_mm2=max((r['pcb_overlap_mm2'] for r in sections), default=0),
                minimum_sampled_gap_mm=min(r['gap_mm'] for r in sections if r['gap_mm'] is not None),
                support_section_overlap_mm2=board.intersection(horizontal_section(mesh, 2.49)).area,
                error_scenarios=scenarios)
    if any(digest(ROOT / name) != sha for name, sha in bindings.items()):
        raise ValueError('Input changed during inspection')
    report = dict(requirement='CON-ARCH-006',
        status='nominal_sections_clear_physical_seating_failure_unresolved' if all(
            r['maximum_sampled_pcb_overlap_mm2'] < 1e-5 for r in rows.values()) else 'nominal_collision_detected',
        physical_qualified=False, rows=rows,
        registration_design_sensitivity=[dict(pcb_lift_mm=h, overlap_mm=overlap_depth(5, 4.4, 5.2, h))
                                         for h in (0., .2, .4, .6, 1.6)],
        limitations=['Aligned nominal bare PCB outline only; populated underside not requalified.',
                     'Horizontal samples at vertex-height band midpoints, not continuous swept-volume proof.',
                     'XY error and PCB lift are assumed sensitivity inputs, not measured manufacturing errors.',
                     'Registration heights are current design datums, not new upper-STL measurements.',
                     'Actual printed file, dimensions, scale, flatness and obstruction location unknown.'],
        source_sha256=bindings)
    output = ROOT / 'docs/reports/pcb-seating-20260920/sections.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(report['status'], flush=True)
    return report


if __name__ == '__main__':
    run()
