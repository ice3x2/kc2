"""CON-ARCH-006 read-only actual receiver interval diagnosis, no acceptance waiver."""
import json,hashlib
from pathlib import Path
from shapely import wkt
from shapely.geometry import box,LineString
from tools.review_kc2_local_covers import prism
from tools.review_kc2_filled_plates import section_geometry
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run():
    import cadquery as cq
    folder=ROOT/'.codex-tmp/registered-housing-fit/lower/right-normal'
    gp=folder/'generation.json';sp=folder/'kc2_right_lower_housing.step';oldp=ROOT/'docs/reports/reinforced-covers-20260913/right-lower.json'
    g=json.loads(gp.read_text());old=json.loads(oldp.read_text())
    if digest(sp)!=g['outputs'][sp.name]:raise ValueError('Changed actual source')
    paths=[Path(__file__),gp,sp,oldp,ROOT/'tools/review_kc2_local_covers.py',ROOT/'tools/review_kc2_filled_plates.py']
    frozen={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    print('import exact failed source receiver',flush=True)
    receiver=sorted(cq.importers.importStep(str(sp)).solids().vals(),key=lambda s:s.Center().x)[1]
    seam=81.84375;mask=wkt.loads(g['parts'][1]['mask_wkt']);protected=wkt.loads(old['clearance_wkt']);rows=[]
    for y in (73.25,86.25):
        print('actual intervals and bounded full sections',y,flush=True)
        roi=box(seam-.5,y-4,seam+6,y+4)
        cropped=receiver.intersect(prism(roi,-2.2,2.5))
        row=dict(y_mm=y,receiver_mask_roi_wkt=mask.intersection(roi).wkt,protected_roi_wkt=protected.intersection(roi).wkt,probes=[],sections=[])
        for dx in (.35,.5,1.):
            x=seam+dx;planline=LineString([(x,y-3),(x,y+3)])
            for z in (-1.6,0.,2.4):
                line=cq.Edge.makeLine(cq.Vector(x,y-3,z),cq.Vector(x,y+3,z));hit=line.intersect(cropped)
                intervals=sorted((min(v.Y for v in e.Vertices()),max(v.Y for v in e.Vertices())) for e in hit.Edges())
                if any(lo<y<hi for lo,hi in intervals):central=None
                else:
                    below=[hi for lo,hi in intervals if hi<=y];above=[lo for lo,hi in intervals if lo>=y]
                    central=[max(below) if below else None,min(above) if above else None]
                row['probes'].append(dict(x_mm=x,z_mm=z,material_intervals_y_mm=intervals,
                    aggregate_empty_width_mm=6-sum(hi-lo for lo,hi in intervals),
                    contiguous_central_void_y_mm=central,
                    contiguous_width_mm=None if central is None or None in central else central[1]-central[0],
                    declared_mask_material_wkt=mask.intersection(planline).wkt,
                    protected_line_wkt=protected.intersection(planline).wkt))
        for z in (-1.6,0.):
            section=section_geometry(cropped,z)
            row['sections'].append(dict(z_mm=z,actual_wkt=section.wkt,actual_protected_overlap_mm2=section.intersection(protected).area))
        rows.append(row)
    if frozen!={p.relative_to(ROOT).as_posix():digest(p) for p in paths}:raise ValueError('Changed source during diagnosis')
    report=dict(requirements=['CON-ARCH-006'],status='diagnosed_not_accepted',rows=rows,source_sha256=frozen,physical_qualified=False)
    (folder/'throat-diagnosis.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps([dict(y_mm=r['y_mm'],probes=[{k:v for k,v in p.items() if not k.endswith('_wkt')} for p in r['probes']]) for r in rows]),flush=True)
    return report
if __name__=='__main__':run()
