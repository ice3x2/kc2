"""Discardable CON-ARCH-006 read-only section plan, not CAD acceptance."""
import hashlib
import json
from pathlib import Path
from shapely import wkt
from shapely.geometry import box
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT / '.codex-tmp/registered-housing-fit/lower/right-normal'
source = folder / 'throat-diagnosis.json'
record = json.loads(source.read_text())
rows = []
seam = 81.84375
for row in record['rows']:
    y = row['y_mm']
    actual = wkt.loads(row['sections'][1]['actual_wkt'])
    opening = actual.buffer(-.6, quad_segs=128).buffer(.6, quad_segs=128)
    difference = actual.difference(opening)
    crop = box(seam-.5, y-4, seam+6, y+4)
    mouth = box(seam+.30003, y-3.3, seam+1.5, y+3.3)
    chosen = []
    rejected = []
    for piece in getattr(difference, 'geoms', [difference]):
        if piece.area < 1e-6:
            continue
        if piece.intersection(mouth).area <= 1e-6:
            continue
        guard = piece.distance(crop.boundary)
        if guard < .60001:
            rejected.append(dict(area_mm2=piece.area, bounds_mm=piece.bounds,
                                 crop_edge_distance_mm=guard))
        else:
            chosen.append(piece)
    cut = unary_union(chosen)
    retained = actual.difference(cut)
    residual = retained.difference(
        retained.buffer(-.6, quad_segs=128).buffer(.6, quad_segs=128))
    rows.append(dict(y_mm=y, radius_mm=.6, cut_z_mm=[-1, 2.5],
                     removed_area_mm2=cut.area, cut_wkt=cut.wkt,
                     rounded_section_wkt=retained.wkt,
                     removed_components=[dict(area_mm2=p.area, bounds_mm=p.bounds,
                                             crop_edge_distance_mm=p.distance(crop.boundary))
                                         for p in chosen],
                     rejected_guard_pieces=rejected,
                     residual_mouth_opening_area_mm2=residual.intersection(mouth).area,
                     mouth_audit_wkt=mouth.wkt))
out = dict(requirements=['CON-ARCH-006'], status='plan_pending_support_exclusion_and_actual_CAD',
           floor_unchanged_z_mm=[-2.2,-1], capture_floor_thickness_mm=1.2,
           selection='Whole opening-difference components touching mouth ROI; reject crop-edge distance <=0.60001 mm',
           limitation='Only mouth tips, not whole housing printability; existing body outside selected components unchanged. Z0 source section must be checked throughout proposed Z band before CAD execution.',
           source_sha256={source.relative_to(ROOT).as_posix():hashlib.sha256(source.read_bytes()).hexdigest(),
                          Path(__file__).relative_to(ROOT).as_posix():hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
           rows=rows, physical_qualified=False)
target=folder/'receiver-cleanup-candidate.json'
target.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps([{k:v for k,v in row.items() if not k.endswith('_wkt')} for row in rows],indent=2))
