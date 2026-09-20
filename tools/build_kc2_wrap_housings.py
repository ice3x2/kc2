"""CON-ARCH-006 deterministic build with lossless conforming STL serialization.

The initial producer remains immutable for provenance of already-built jobs.
Future builds use this entry point; no tolerance repair or hole filling occurs.
"""
import argparse
from pathlib import Path
from tools.kc2_pcb_seating import digest
from tools.stage_kc2_wrap_housings import ROOT, STAGE, generate, write_json


def export_mesh(shape, path):
    import cadquery as cq
    from tools.kc2_stl_tjunction import normalize
    from tools.generate_kc2_magnetic_housings import inspect_mesh
    cq.exporters.export(shape, str(path), tolerance=.005, angularTolerance=.08)
    data, proof = normalize(path.read_bytes())
    path.write_bytes(data)
    return inspect_mesh(path, shape), proof


def source_bindings():
    names = ('tools/build_kc2_wrap_housings.py', 'tools/kc2_stl_tjunction.py',
             'tools/test_kc2_stl_tjunction.py', 'tools/kc2_stl_zero_area_filter.py')
    return {name:digest(ROOT/name) for name in names}


def build(side, kind):
    from tools import stage_kc2_flat_central_revision as exporter
    saved = exporter._export_mesh
    before = source_bindings()
    try:
        exporter._export_mesh = export_mesh
        row = generate(side, kind)
    finally:
        exporter._export_mesh = saved
    if before != source_bindings():
        raise ValueError('Serializer changed during build')
    row['source_sha256'].update(before)
    folder = STAGE/('lower' if kind in ('normal', 'magnetic') else 'upper')/(side+'-'+kind)
    write_json(folder/'generation.json', row)
    return row


def finalize_existing_step(side, kind):
    """Fresh CAD proof + STL export after an earlier serialization rejection."""
    import json
    import cadquery as cq
    from shapely import wkt
    from tools.kc2_central_flexure import prism
    from tools.stage_kc2_registered_lower import audit_additive
    from tools.review_kc2_flat_central_native import _signature
    plan = json.loads((STAGE/'plan.json').read_text())
    bindings = {**plan['source_sha256'], **source_bindings(),
                (STAGE/'plan.json').relative_to(ROOT).as_posix():digest(STAGE/'plan.json')}
    for name, sha in bindings.items():
        if digest(ROOT/name) != sha:
            raise ValueError('Changed input: '+name)
    if kind not in ('normal', 'magnetic'):
        raise ValueError('Recovery limited to the two lower variants')
    folder = STAGE/'lower'/(side+'-'+kind)
    if (folder/'generation.json').exists():
        raise ValueError('Do not overwrite a completed generation')
    stem = f'kc2_{side}_lower_housing'+('_magnetic' if kind == 'magnetic' else '')
    step = folder/(stem+'.step')
    print('fresh CAD recovery review', side, kind, flush=True)
    actual = cq.importers.importStep(str(step)).val()
    solids = sorted(actual.Solids(), key=lambda s:s.Center().x)
    baseline = sorted(cq.importers.importStep(str(ROOT/'hardware/MODELS'/(stem+'.step'))).solids().vals(),
                      key=lambda s:s.Center().x)
    if len(solids) != len(baseline) or len(solids) != (1 if side == 'left' else 2):
        raise ValueError('Wrong recovered body count')
    outputs = {step.name:digest(step)}
    p = plan['sides'][side]; d = p['dimensions']; rows = []
    for i, (base, solid) in enumerate(zip(baseline, solids)):
        additions = [prism(wkt.loads(p['wall_parts_wkt'][i]), d['floor_top'], d['wall_top']),
                     prism(wkt.loads(p['floor_parts_wkt'][i]), d['floor_bottom'], d['floor_top'])]
        proof = audit_additive(base, solid, additions)
        missing = sum(piece.cut(solid).Volume() for piece in additions)
        if proof['errors'] or missing > .002:
            raise ValueError('Recovered STEP fails material contract: '+str((proof, missing)))
        name = stem+'.stl' if side == 'left' else f'kc2_right_lower_housing_part_{chr(97+i)}'+('_magnetic' if kind == 'magnetic' else '')+'.stl'
        mesh, filtered = export_mesh(solid, folder/name)
        outputs[name] = digest(folder/name)
        rows.append(dict(mesh=mesh, filter=filtered, preservation=proof, missing_additions_mm3=missing))
        print('recovered part', i, 'exact edge splits', filtered['split_count'], flush=True)
    for name, sha in bindings.items():
        if digest(ROOT/name) != sha:
            raise ValueError('Recovery source changed: '+name)
    row = dict(status='generated_pending_independent_review', errors=[], body_count=len(solids),
               side=side, kind=kind, outputs=outputs, parts=rows, physical_qualified=False,
               signature=_signature(actual), source_sha256=bindings,
               recovery='Fresh baseline/added/missing CAD differences; conforming triangulation with no moved vertices')
    write_json(folder/'generation.json', row)
    return row


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('side', choices=['left', 'right'])
    parser.add_argument('kind', choices=['normal', 'magnetic', 'mx', 'choc_v1', 'deep_sea'])
    parser.add_argument('--existing-step', action='store_true')
    args = parser.parse_args()
    (finalize_existing_step if args.existing_step else build)(args.side, args.kind)
