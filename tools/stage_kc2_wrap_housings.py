"""CON-ARCH-006 source-bound sleeve candidates, never canonical publication.

Additions only: current support/plate/screw/component shapes stay intact.
Actual solids, native round trips and an independent output review are still
required before replacing printable artifacts.
"""
from pathlib import Path
import argparse
import json
from dataclasses import asdict
from shapely import wkt, affinity
from shapely.geometry import box
from shapely.ops import unary_union
from tools.kc2_wrap_wall_plan import sleeve_plan, mating_outline, cad_outline
from tools.kc2_pcb_seating import digest

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / '.codex-tmp/wrap-housing-20260920-r1'
EVIDENCE = ROOT / 'docs/reports/registered-housing-fit-20260913/evidence'


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')


def make_plan():
    sources = set()
    def read(path):
        sources.add(path)
        return json.loads(path.read_text(encoding='utf-8'))
    publication = ROOT/'hardware/MODELS/kc2_smooth_central_housing_manifest.json'
    manifest = read(publication)
    for name, sha in manifest['outputs'].items():
        if digest(ROOT/name) != sha:
            raise ValueError('Canonical publication changed: '+name)
        sources.add(ROOT/name)
    sides = {}
    extracted = read(STAGE/'board-envelopes.json')
    for name, sha in extracted['source_sha256'].items():
        if digest(ROOT/name) != sha:
            raise ValueError('Changed PCB envelope source: '+name)
        sources.add(ROOT/name)
    # Prepare both complete interface envelopes before deciding where the
    # central exception is actually needed. Include the existing lower floor
    # projection so magnetic access/old center walls are not screened by a new
    # sleeve merely because an upper plate is locally recessed.
    import trimesh
    from tools.kc2_pcb_seating import horizontal_section
    partner_envelopes = {}
    for s in ('left', 'right'):
        old = read(ROOT/f'docs/reports/solid-filled-plates-20260913/{s}-mx.json')
        u = read(EVIDENCE/f'upper/{s}-mx/generation.json')
        outer = wkt.loads(old['plan_wkt']['domain']).union(unary_union([wkt.loads(r['addition']) for r in u['registrars'].values()]))
        outer = mating_outline(outer, wkt.loads(extracted['sides'][s]['keycaps_wkt']),
                               wkt.loads(extracted['sides'][s]['board_wkt']))
        names = ['kc2_left_lower_housing.stl'] if s == 'left' else [f'kc2_right_lower_housing_part_{part}.stl' for part in ('a', 'b')]
        mesh = trimesh.util.concatenate([trimesh.load(ROOT/'hardware/MODELS'/name, force='mesh') for name in names])
        partner_envelopes[s] = outer.union(horizontal_section(mesh, -1.6))
    for side in ('left', 'right'):
        profiles = {kind: read(ROOT/f'docs/reports/solid-filled-plates-20260913/{side}-{kind}.json')
                    for kind in ('mx', 'choc_v1', 'deep_sea')}
        upper = read(EVIDENCE/f'upper/{side}-mx/generation.json')
        mx = {k: wkt.loads(v) for k, v in profiles['mx']['plan_wkt'].items()}
        original_domain = mx['domain'].union(unary_union([wkt.loads(r['addition']) for r in upper['registrars'].values()]))
        caps = wkt.loads(extracted['sides'][side]['keycaps_wkt'])
        board = wkt.loads(extracted['sides'][side]['board_wkt'])
        domain = mating_outline(original_domain, caps, board)
        other = 'right' if side == 'left' else 'left'
        offset = -153.2 if side == 'left' else 153.2
        partner = affinity.translate(partner_envelopes[other], xoff=offset)
        # Other sleeve can extend 1.50 mm beyond its interface outline; an
        # additional .40 mm preserves noncontact between the complete halves.
        exclusion = partner.buffer(1.9, join_style=2)
        p = sleeve_plan(side, domain, mx['service'], central_exclusion=exclusion)
        if p.wall.distance(board) < .3-1e-8:
            raise ValueError('New sleeve reduces existing PCB seating clearance')
        if p.wall.intersection(caps).area > 1e-8 or p.wall.distance(caps) < .3-1e-8:
            raise ValueError('Tall wall blocks nominal cap travel envelope')
        protected = read(ROOT/f'docs/reports/reinforced-covers-20260913/{side}-lower.json')
        collision = p.wall.intersection(wkt.loads(protected['clearance_wkt'])).area
        if collision > 1e-7:
            raise ValueError('Sleeve blocks existing lower component clearance: '+str(collision))
        if side == 'left':
            wall_parts, floor_parts = [p.wall], [p.floor]
        else:
            lower = read(EVIDENCE/'lower/right-normal/generation.json')
            masks = [wkt.loads(v['mask_wkt']) for v in lower['parts']]
            seam = lower['split_x_mm']
            ownership = [box(-100, -100, seam-.2001, 300), box(seam+.2001, -100, 300, 300)]
            # Retain old ownership in existing material; extend only the new
            # exterior. Never add within .4001 of the opposite original mask.
            wall_parts, floor_parts = [], []
            for i in (0, 1):
                owner = masks[i].union(ownership[i]).difference(masks[1-i].buffer(.4001, join_style=2))
                wall_parts.append(p.wall.intersection(owner))
                floor_parts.append(p.floor.intersection(owner))
            if wall_parts[0].distance(wall_parts[1]) < .4-1e-7 or floor_parts[0].distance(floor_parts[1]) < .4-1e-7:
                raise ValueError('New sleeve closes the A/B gap')
        additions, upper_plan_checks = {}, {}
        raw = None
        if side == 'right':
            from tools.kc2_wrap_partition import raw_owners
            raw = raw_owners(original_domain, mx['openings'], profiles['mx']['mounting_centers'])
        for kind, old in profiles.items():
            gs = {k: wkt.loads(v) for k, v in old['plan_wkt'].items()}
            # Outward growth to the MX mating envelope with .80 mm inward
            # overlap at roots. Keep every original functional void reserved.
            rim = domain.difference(gs['domain'].buffer(-.8, join_style=2))
            rim = rim.difference(p.central).difference(p.service)
            # Add interface stock only where a real sleeve remains. This avoids
            # unnecessary small additions along the exempt central mating face.
            rim = rim.intersection(p.wall.buffer(1.2, join_style=2))
            reserved = unary_union([gs[k] for k in ('body', 'openings', 'service', 'bores', 'pockets')])
            reserved = reserved.union(unary_union([wkt.loads(r['groove']) for r in upper['registrars'].values()]))
            rim = rim.difference(reserved)
            pieces = []
            for i, part in enumerate(upper['parts']):
                owner = unary_union([wkt.loads(layer['wkt']) for layer in part['layers']])
                owner = domain if side == 'left' else owner.union(domain.difference(original_domain).intersection(raw[i]))
                pieces.append(rim.intersection(owner))
            current = read(EVIDENCE/f'upper/{side}-{kind}/generation.json')
            occupied = [unary_union([wkt.loads(layer['wkt']) for layer in part['layers']])
                        for part in current['parts']]
            if side == 'right':
                pieces = [g.difference(occupied[1-i].buffer(.4001, join_style=2)) for i,g in enumerate(pieces)]
                if pieces[0].distance(pieces[1]) < .39999:
                    raise ValueError('Upper rim additions close the A/B gap')
            pieces = [cad_outline(g) for g in pieces]
            complete_upper = unary_union(occupied+pieces)
            upper_gap = p.wall.distance(complete_upper)
            if upper_gap < .3-1e-7:
                raise ValueError('Sleeve interferes with upper outline: '+kind)
            root_areas = [[g.intersection(occupied[i]).area for g in getattr(part, 'geoms', [part])]
                          for i, part in enumerate(pieces)]
            if any(v <= .001 for part in root_areas for v in part):
                raise ValueError('Rim addition lacks an existing upper root')
            upper_plan_checks[kind] = dict(sleeve_gap_mm=upper_gap, root_overlap_areas_mm2=root_areas)
            additions[kind] = [g.wkt for g in pieces]
        sides[side] = dict(domain_wkt=domain.wkt, original_domain_wkt=original_domain.wkt,
            keycaps_wkt=caps.wkt, nominal_cap_gap_mm=p.wall.distance(caps),
            counterpart_envelope_wkt=partner.wkt, counterpart_exclusion_offset_mm=1.9,
            discarded_center_nubs_wkt=p.discarded_center_nubs.wkt,
            discarded_center_nubs_mm2=p.discarded_center_nubs.area,
            service_wkt=p.service.wkt, central_wkt=p.central.wkt,
            wall_wkt=p.wall.wkt, floor_wkt=p.floor.wkt,
            wall_parts_wkt=[g.wkt for g in wall_parts], floor_parts_wkt=[g.wkt for g in floor_parts],
            upper_rim_parts_wkt=additions, dimensions=asdict(p.dimensions),
            upper_plan_checks=upper_plan_checks,
            lower_protected_overlap_mm2=collision,
            wall_area_mm2=p.wall.area, wall_split_omission_mm2=p.wall.difference(unary_union(wall_parts)).area)
    for feature in ('wall_wkt', 'floor_wkt'):
        def joined(side):
            return affinity.translate(affinity.scale(wkt.loads(sides[side][feature]), xfact=-1,
                yfact=1, origin=(0, 0)), xoff=170.1125 if side == 'left' else 323.3125)
        a, b = joined('left'), joined('right')
        if a.intersection(b).area > 1e-8 or a.distance(b) < .4-1e-8:
            raise ValueError('New sleeve candidates collide at the central transition')
    for name in ('tools/kc2_wrap_wall_plan.py', 'tools/test_kc2_wrap_wall_plan.py',
                 'tools/stage_kc2_wrap_housings.py', 'tools/kc2_pcb_seating.py',
                 'tools/kc2_wrap_partition.py', 'tools/test_kc2_wrap_partition.py'):
        sources.add(ROOT/name)
    for folder in ('hardware/PCB', 'hardware/GERBER'):
        sources.update(p for p in (ROOT/folder).rglob('*') if p.is_file())
    result = dict(requirement='CON-ARCH-006', status='plan_pending_actual_cad', sides=sides,
                  source_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in sorted(sources)},
                  physical_qualified=False)
    write_json(STAGE/'plan.json', result)
    print('plan created; actual CAD/native/assembly checks pending', flush=True)
    return result


def generate(side, kind):
    import cadquery as cq
    from tools.kc2_central_flexure import prism
    from tools.stage_kc2_registered_lower import compose_lower, audit_additive
    from tools.stage_kc2_flat_central_revision import _export_mesh
    from tools.review_kc2_flat_central_native import _signature
    from tools.kc2_flat_central_native import compare_cad_signatures
    plan = json.loads((STAGE/'plan.json').read_text())
    for name, sha in plan['source_sha256'].items():
        if digest(ROOT/name) != sha:
            raise ValueError('Plan source changed: '+name)
    row = plan['sides'][side]
    lower = kind in ('normal', 'magnetic')
    stem = f'kc2_{side}_lower_housing'+('_magnetic' if kind == 'magnetic' else '') if lower else f'kc2_{side}_{kind}_upper_housing'
    path = ROOT/'hardware/MODELS'/(stem+'.step')
    folder = STAGE/('lower' if lower else 'upper')/(side+'-'+kind)
    folder.mkdir(parents=True, exist_ok=True)
    print('import', side, kind, flush=True)
    before = sorted(cq.importers.importStep(str(path)).solids().vals(), key=lambda s:s.Center().x)
    wanted = 1 if side == 'left' else 2
    if len(before) != wanted:
        raise ValueError('Unexpected input body count')
    finals, proofs, part_rows = [], [], []
    for i, base in enumerate(before):
        print('build', side, kind, i, flush=True)
        if lower:
            d = row['dimensions']
            additions = [prism(wkt.loads(row['wall_parts_wkt'][i]), d['floor_top'], d['wall_top']),
                         prism(wkt.loads(row['floor_parts_wkt'][i]), d['floor_bottom'], d['floor_top'])]
        else:
            top = {'mx':9.3, 'choc_v1':6.5, 'deep_sea':6.25}[kind]
            additions = [prism(wkt.loads(row['upper_rim_parts_wkt'][kind][i]), 4.4, top)]
        final = compose_lower(base, additions)
        proof = audit_additive(base, final, additions)
        if proof['errors']:
            raise ValueError(proof)
        finals.append(final); proofs.append(proof)
    compound = cq.Compound.makeCompound(finals)
    step = folder/(stem+'.step')
    print('export/reopen STEP', side, kind, flush=True)
    cq.exporters.export(compound, str(step))
    actual = cq.importers.importStep(str(step)).val()
    errors = compare_cad_signatures(_signature(compound), _signature(actual))
    if errors:
        raise ValueError(errors)
    solids = sorted(actual.Solids(), key=lambda s:s.Center().x)
    outputs = {step.name:digest(step)}
    for i, solid in enumerate(solids):
        if side == 'left':
            name = stem+'.stl'
        elif lower:
            name = f'kc2_right_lower_housing_part_{chr(97+i)}'+('_magnetic' if kind == 'magnetic' else '')+'.stl'
        else:
            name = stem+f'_part_{chr(97+i)}.stl'
        mesh, filtered = _export_mesh(solid, folder/name)
        outputs[name] = digest(folder/name)
        part_rows.append(dict(mesh=mesh, filter=filtered, preservation=proofs[i]))
    result = dict(status='generated_pending_independent_review', errors=[], body_count=len(solids),
        side=side, kind=kind, outputs=outputs, parts=part_rows, physical_qualified=False,
        signature=_signature(actual),
        source_sha256={**plan['source_sha256'], (STAGE/'plan.json').relative_to(ROOT).as_posix():digest(STAGE/'plan.json')})
    for name, sha in result['source_sha256'].items():
        if digest(ROOT/name) != sha:
            raise ValueError('Source changed during generation: '+name)
    write_json(folder/'generation.json', result)
    print('generated', side, kind, flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('side', choices=['plan', 'left', 'right'])
    parser.add_argument('kind', nargs='?', choices=['normal', 'magnetic', 'mx', 'choc_v1', 'deep_sea'])
    args = parser.parse_args()
    make_plan() if args.side == 'plan' else generate(args.side, args.kind)
