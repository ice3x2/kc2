"""CON-ARCH-006 localize failed actual right component envelope, no edits."""
import json, hashlib
from pathlib import Path
from shapely import wkt
from tools.kc2_required_lower_clearance import required_envelope
from tools.review_kc2_local_covers import prism
ROOT = Path(__file__).resolve().parents[1]


def run():
    import cadquery as cq
    rp = ROOT / '.codex-tmp/registered-housing-fit/lower/right-void-review.json'
    report = json.loads(rp.read_text())
    raw = {k: wkt.loads(v) for k,v in report['component_envelope']['raw_classes_wkt'].items()}
    paths = [Path(__file__), rp, ROOT / 'hardware/MODELS/kc2_right_lower_housing.step',
             ROOT / '.codex-tmp/registered-housing-fit/lower/right-normal/kc2_right_lower_housing.step',
             ROOT / 'tools/kc2_required_lower_clearance.py', ROOT / 'tools/review_kc2_local_covers.py']
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    frozen = {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}
    print('import canonical and current actual right pairs', flush=True)
    baseline = cq.importers.importStep(str(paths[2])).val()
    current = cq.importers.importStep(str(paths[3])).val()
    rows = []
    for name, geometry in raw.items():
        if geometry.is_empty: continue
        print('class', name, flush=True)
        tool = prism(required_envelope({name: geometry}), -.4, 2.5)
        row = dict(name=name, baseline=[], current=[])
        for label, shape in [('baseline', baseline), ('current', current)]:
            for i, solid in enumerate(sorted(shape.Solids(), key=lambda s:s.Center().x)):
                for j, t in enumerate(tool.Solids()):
                    hit = solid.intersect(t)
                    if hit.Volume() > .000001:
                        b = hit.BoundingBox()
                        row[label].append(dict(part=i, tool=j, volume_mm3=hit.Volume(),
                                               bounds_mm=[b.xmin,b.ymin,b.zmin,b.xmax,b.ymax,b.zmax],
                                               valid=hit.isValid()))
        rows.append(row)
        print(json.dumps(row), flush=True)
        result = dict(requirements=['CON-ARCH-006'], status='diagnostic_running', rows=rows,
                      source_sha256=frozen, physical_qualified=False)
        out = rp.with_name('right-component-failure-diagnosis.json')
        out.write_text(json.dumps(result, indent=2)+'\n')
    if frozen != {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}:
        raise ValueError('Diagnostic sources changed')
    result['status'] = 'diagnosed_not_accepted'
    out.write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__': run()
