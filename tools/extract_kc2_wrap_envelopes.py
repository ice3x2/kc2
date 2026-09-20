"""CON-ARCH-006 read-only actual PCB and nominal layout envelope snapshot."""
import json
import subprocess
from pathlib import Path
from shapely import affinity
from shapely.geometry import box
from shapely.ops import unary_union
from tools.kc2_pcb_seating import digest

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT/'.codex-tmp/wrap-housing-20260920-r1'


def extract():
    from tools.generate_kc2_magnetic_housings import load_plans
    sources = [ROOT/f'hardware/PCB/kc2_{s}/kc2_{s}.kicad_pcb' for s in ('left', 'right')]
    sources += [ROOT/'tools'/name for name in ('extract_kc2_wrap_envelopes.py',
        'render_kc2_x3_joined.py', 'generate_kc2_magnetic_housings.py',
        'generate_kc2_x3_v2_housings.py', 'generate_kc2_housings.py')]
    before = {p.relative_to(ROOT).as_posix():digest(p) for p in sources}
    plans, _, _ = load_plans()
    code = ("from pathlib import Path; import json; from tools import render_kc2_x3_joined as r; "
            "c=r.build_context(Path.cwd(),1.,5.,'key-pitch',variant='x3-v2'); "
            "print(json.dumps({d.side:[{'label':k.label,'center':d.switch_centers[i],"
            "'width_mm':k.w_u*r.UNIT-1.,'height_mm':r.UNIT-1.} "
            "for i,k in enumerate(d.keys,start=1)] for d in (c.left,c.right)}))")
    result = subprocess.run(['C:/Program Files/KiCad/10.0/bin/python.exe', '-B', '-c', code],
                            cwd=ROOT, text=True, capture_output=True, check=True, timeout=180)
    caps = json.loads(result.stdout)
    rows = {}
    for side, plan in plans.items():
        polygons = []
        for key in caps[side]:
            x, y = key['center']; w, h = key['width_mm'], key['height_mm']
            polygon = box(x-w/2, y-h/2, x+w/2, y+h/2)
            polygon = affinity.translate(affinity.scale(polygon, xfact=-1, yfact=1, origin=(0, 0)),
                                         xoff=plan['raw_bounds'][2], yoff=-plan['raw_bounds'][1])
            polygons.append(polygon)
            key['local_wkt'] = polygon.wkt
        rows[side] = dict(board_wkt=plan['board'].wkt, keycaps_wkt=unary_union(polygons).wkt,
                         caps=caps[side], switches=len(plan['switches']), mounts=len(plan['mounting_holes']),
                         lower_protected_wkt=plan['all_component_cutouts'].wkt,
                         features_wkt={k:g.wkt for k,g in plan['feature_geometries'].items()})
    if before != {p.relative_to(ROOT).as_posix():digest(p) for p in sources}:
        raise ValueError('Extraction source changed')
    if sum(r['switches'] for r in rows.values()) != 70 or sum(r['mounts'] for r in rows.values()) != 17:
        raise ValueError('Wrong keyboard identity')
    value = dict(requirement='CON-ARCH-006', sides=rows, source_sha256=before,
                 physical_qualified=False, cap_contract='Nominal layout rectangles: pitch*U minus 1 mm; exact purchased cap/skirt and switch play remain unmeasured.')
    STAGE.mkdir(parents=True, exist_ok=True)
    (STAGE/'board-envelopes.json').write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    print('read-only PCB/nominal cap snapshot complete', flush=True)
    return value


if __name__ == '__main__':
    extract()
