"""CON-ARCH-006 corrected local MX concealment; staged artifacts only.

No lower/PCB/support/spacing redesign. The existing plate is retained, with
local roof additions outside its outline. Received keycap/print qualification
is explicitly pending. Controller-facing peripheral regions remain open.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from shapely.geometry import box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'cc854a3e0e0f25ab3d63e2916cb4b99a487b6536'
STAGE = ROOT / '.codex-tmp/local-cover-build'
SKIRT_BOTTOM, PLATE_BOTTOM, PLATE_TOP = 4.4, 7.8, 9.3


def cover_geometry(outline, body, service, locality=None):
    """Raw body at roof level; body + .301 clearance strictly below plate."""
    outer = outline.union(body.buffer(.702, quad_segs=32))
    inner = outline.buffer(-.401).union(body.buffer(.301, quad_segs=32))
    skirt = outer.difference(inner).difference(service)
    roof = outer.difference(outline.buffer(-.005)).intersection(body.buffer(.702, quad_segs=32)).difference(body).difference(service)
    if locality is not None:
        skirt, roof = skirt.intersection(locality), roof.intersection(locality)
    if skirt.distance(body) < .3 - 1e-7:
        raise ValueError('Skirt lacks nominal switch-body clearance')
    if skirt.difference(outline.union(roof)).area > 1e-7:
        raise ValueError('Skirt has no roof footprint')
    return dict(skirt=skirt, roof=roof, outer=outer)


def cover_plan(plan, locality=None):
    from tools import generate_kc2_mx_upper_housings as upper
    shp = upper.lower.legacy_geometry.require_shapely()
    stack = upper.stack_parameters(plate_top_above_pcb_mm=5.2,
                                   clip_thickness_mm=1.5, aperture_mm=14.)
    up = upper.upper_plan(shp, plan, stack)
    body = plan['switch_service_body_geometry']
    # Only the external key field is concealed. Do not enclose controller/USB
    # access by extending a ring around the controller-area protrusion.
    keyfield = body.buffer(2., quad_segs=32)
    locality = keyfield if locality is None else keyfield.intersection(locality)
    service = up['service'].union(up['pilots']).union(up['pockets'])
    result = cover_geometry(plan['housing_outline'], body, service, locality)
    result.update(upper=up, body=body, service=service, locality=locality)
    result['ownership_masks'] = extended_split_masks(plan,up)
    return result


def extended_split_masks(plan,up):
    """Original upper Voronoi split ownership, extended past only the old outline.

Same opening/collar ownership and .10 mm erosion as split_upper_plan. Existing
keyed plate solids themselves are neither regenerated nor changed here.
"""
    from shapely import voronoi_polygons
    from shapely.geometry import MultiPoint, Point
    centers=[s['center'] for s in plan['switches']]
    outline=plan['housing_outline'];mid=(outline.bounds[0]+outline.bounds[2])/2
    cells=voronoi_polygons(MultiPoint(centers),extend_to=outline.envelope.buffer(3).envelope)
    groups=[[],[]]
    for cell in cells.geoms:
        center=next(c for c in centers if cell.covers(Point(*c)))
        groups[0 if center[0]<mid else 1].append(cell)
    a,b=[unary_union(group) for group in groups]
    for opening in up['openings'].geoms:
        region=opening.buffer(1.)
        if opening.centroid.x<mid:a,b=a.union(region),b.difference(region)
        else:a,b=a.difference(region),b.union(region)
    for hole in plan['mounting_holes']:
        disk=Point(*hole['housing_center_mm']).buffer(2.6,quad_segs=24)
        if a.covers(Point(*hole['housing_center_mm'])):a,b=a.union(disk),b.difference(disk)
        else:a,b=a.difference(disk),b.union(disk)
    return [a.buffer(-.1),b.buffer(-.1)]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalize_step(path):
    from tools import generate_kc2_x3_v2_housings as lower
    lower.normalize_exported_text(path)
    if lower.has_trailing_horizontal_whitespace(path):
        raise ValueError('STEP contains trailing whitespace')


def partition_covers(cover, parts):
    """Preserve old split: each added skirt must have its own roof, not its neighbor's."""
    if len(parts)==1:
        return [(cover['skirt'],cover['roof'])]
    masks = cover.get('ownership_masks')
    if masks is None:
        masks = [p.buffer(2., quad_segs=32) for p in parts]
        masks[0] = masks[0].difference(parts[1].buffer(.1))
        masks[1] = masks[1].difference(masks[0].buffer(.2))
    # Captive puzzle keys modify the raw Voronoi ownership inside the original
    # plate. Preserve their actual owner; use extended masks only elsewhere.
    original_parts = unary_union(parts)
    masks = [mask.difference(original_parts).union(part) for mask,part in zip(masks,parts)]
    result = []
    for part, mask in zip(parts, masks):
        roof = cover['roof'].intersection(mask)
        skirt = cover['skirt'].intersection(mask).intersection(part.union(roof))
        result.append((skirt, roof))
    return result


def generation_sources(side):
    from tools import generate_kc2_mx_upper_housings as upper
    paths = [Path(__file__), ROOT/'tools/test_kc2_local_upper_covers.py',
             ROOT/'tools/generate_kc2_magnetic_housings.py',
             Path(upper.__file__), Path(upper.lower.__file__),
             Path(upper.lower.legacy_geometry.__file__), ROOT/'tools/render_kc2_x3_joined.py',
             *upper.lower.BOARD_PATHS.values()]
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}


def partition_clearance_errors(parts,cover_parts):
    if len(parts)==1:return []
    baseline=parts[0].distance(parts[1])
    a,b=[skirt.union(roof) for skirt,roof in cover_parts]
    measured=[a.distance(parts[1]),b.distance(parts[0]),a.distance(b)]
    # Nominal .20 mm polygon-offset joint measures .199759091241 mm in the
    # unchanged baseline. Preserve its measured clearance, not a rounded claim.
    return [] if baseline>0 and min(measured)>=baseline-1e-7 else ['New covers reduce original split clearance']


def generate(side):
    import cadquery as cq
    import trimesh
    from tools import generate_kc2_magnetic_housings as magnetic
    from tools import generate_kc2_mx_upper_housings as upper
    source_hashes = generation_sources(side)
    plans, _, transform = magnetic.load_plans()
    if abs(transform['dx']-124.625) > 1e-7 or abs(transform['dy']) > 1e-7:
        raise ValueError('Original joined placement changed')
    plan = plans[side]
    cover = cover_plan(plan)
    shp = upper.lower.legacy_geometry.require_shapely()
    parts = [cover['upper']['plate']] if side == 'left' else upper.split_upper_plan(shp, plan, cover['upper'])[0]
    # Expand only cover masks beyond the old perimeter, preserving the original
    # split parts themselves. Maintain .20 mm clearance between new additions.
    cover_parts = partition_covers(cover, parts)
    clearance_errors=partition_clearance_errors(parts,cover_parts)
    if clearance_errors:raise ValueError('; '.join(clearance_errors))
    STAGE.mkdir(parents=True, exist_ok=True)
    name = f'kc2_{side}_mx_upper_housing'
    source = STAGE / (name + '-baseline.step')
    source.write_bytes(subprocess.check_output(
        ['git', 'show', f'{BASELINE}:hardware/MODELS/{name}.step'], cwd=ROOT))
    old = sorted(cq.importers.importStep(str(source)).solids().vals(), key=lambda s:s.Center().x)
    if len(old) != len(parts):
        raise ValueError('Baseline solid count differs from retained split')
    def prism(g, z0, z1):
        return upper.lower._extrude_geometry(cq, g, z1-z0, z0).val()
    checks, solids, meshes = [], [], {}
    for index, (before, (skirt, roof)) in enumerate(zip(old, cover_parts)):
        additions = [prism(skirt, SKIRT_BOTTOM, PLATE_BOTTOM), prism(roof, PLATE_BOTTOM, PLATE_TOP)]
        after = before.fuse(*additions)
        added = after.cut(before)
        removed = before.cut(after).Volume()
        below_body = prism(cover['body'].buffer(.299), SKIRT_BOTTOM, PLATE_BOTTOM-.001)
        raw_roof_body = prism(cover['body'], PLATE_BOTTOM+.001, PLATE_TOP+.001)
        collisions = dict(underplate=added.intersect(below_body).Volume(),
                          roof_added_body=added.intersect(raw_roof_body).Volume(),
                          service=added.intersect(prism(cover['service'], SKIRT_BOTTOM, PLATE_TOP+.001)).Volume())
        bounds = magnetic.bounds(after)
        errors = []
        if removed > .001: errors.append('Baseline material removed')
        if not after.isValid() or len(after.Solids()) != 1: errors.append('Invalid/disconnected solid')
        if any(v > .001 for v in collisions.values()): errors.append('Added material intersects component/service envelope')
        if any(bounds[i+3]-bounds[i] > 150 for i in range(3)): errors.append('Exceeds 150 mm printable part')
        if skirt.difference(parts[index].union(roof)).area > .001: errors.append('Skirt missing local roof')
        row = dict(part=index, errors=errors, removed_mm3=removed, added_mm3=added.Volume(),
                   intersections_mm3=collisions, bounds_mm=bounds,
                   skirt_plan_wkt=skirt.wkt, roof_plan_wkt=roof.wkt)
        checks.append(row)
        if errors: raise ValueError(json.dumps(row))
        suffix = '' if side == 'left' else '_part_'+chr(97+index)
        stl = STAGE / (name+suffix+'.stl')
        cq.exporters.export(after, str(stl), tolerance=.005, angularTolerance=.08)
        mesh = trimesh.load_mesh(stl, process=True)
        if not mesh.is_watertight or not mesh.is_winding_consistent or len(mesh.split()) != 1:
            raise ValueError('Exported mesh invalid')
        meshes[stl.name] = dict(sha256=digest(stl), watertight=bool(mesh.is_watertight),
                                winding_consistent=bool(mesh.is_winding_consistent), shells=len(mesh.split()))
        solids.append(after)
    step = STAGE / (name+'.step')
    cq.exporters.export(cq.Compound.makeCompound(solids), str(step))
    normalize_step(step)
    imported = cq.importers.importStep(str(step)).solids().vals()
    if len(imported) != len(solids) or not all(s.isValid() for s in imported):
        raise ValueError('STEP round-trip invalid')
    if abs(sum(s.Volume() for s in imported)-sum(s.Volume() for s in solids)) > .01:
        raise ValueError('STEP volume changed')
    if generation_sources(side) != source_hashes:
        raise ValueError('Generation sources changed while work was running')
    outputs = {'normal':dict(step=step.name, step_sha256=digest(step), meshes=meshes,
               solids=[dict(bounds_mm=magnetic.bounds(s), volume_mm3=s.Volume()) for s in solids])}
    report = dict(requirements=['CON-ARCH-006','OPS-ARCH-006'],
                  status='generated_not_independently_verified', baseline_commit=BASELINE,
                  physical_qualified=False, canonical_promotion_approved=False,
                  transform=transform, checks=checks, outputs=outputs,
                  source_sha256=source_hashes, sources_unchanged=True,
                  git_source_sha256={BASELINE+':hardware/MODELS/'+name+'.step':digest(source)},
                  pending=['independent actual CAD review','local roof print overhang/support qualification',
                           'exact keycap inner skirt/full travel','supplied switch tolerance','Fusion native round trip'])
    (STAGE/(side+'-upper.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--side', choices=['left','right'], required=True)
    print(json.dumps(generate(parser.parse_args().side), indent=2))
