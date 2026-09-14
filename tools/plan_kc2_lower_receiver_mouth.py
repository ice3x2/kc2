"""CON-ARCH-006 bounded planar mouth / nearby full-collar alternatives only."""
import json,hashlib,math
from pathlib import Path
from shapely import wkt
from shapely.geometry import Point,box
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run():
    path=ROOT/'docs/reports/reinforced-covers-20260913/right-lower.json';old=json.loads(path.read_text())
    protected=wkt.loads(old['clearance_wkt']);domain=wkt.loads(old['new_outline_wkt']);seam=81.84375
    rows=[];nearest=[]
    for mode in ('straight_mouth_only','full_collar'):
        offsets=[3.] if mode=='straight_mouth_only' else [round(2.75+i*.25,2) for i in range(22)]
        candidates=[]
        for offset in offsets:
            for i in range(701):
                y=45+i*.1
                if abs(y-73.25)<9:continue
                donor=Point(seam+offset,y).buffer(2.25,quad_segs=24).union(box(seam-.1,y-1,seam+offset,y+1))
                if donor.intersection(protected).area>1e-8:continue
                void=donor.buffer(.40004,quad_segs=128)
                if mode=='full_collar':
                    stock=void.buffer(1.2/math.cos(math.pi/128),quad_segs=32).difference(void).intersection(box(seam+.30004,y-10,seam+15,y+10))
                else:
                    # Only the straight functional mouth; this does NOT claim
                    # complete circumferential stock or a finished load path.
                    stock=box(seam+.30004,y-2.60004,seam+.70,y-1.40004).union(box(seam+.30004,y+1.40004,seam+.70,y+2.60004))
                material=donor.union(stock)
                if material.intersection(protected).area<1e-8 and material.difference(domain).area<1e-8:
                    candidates.append(dict(y_mm=round(y,4),head_offset_mm=offset,cost=abs(y-86.25)+abs(offset-3),
                        donor_wkt=donor.wkt,stock_wkt=stock.wkt))
        candidates.sort(key=lambda c:c['cost'])
        row=dict(mode=mode,stock_mm=1.2,count=len(candidates),nearest_candidates=candidates[:8]);rows.append(row)
        print(mode,'count',len(candidates),'nearest',[(c['y_mm'],c['head_offset_mm']) for c in candidates[:8]],flush=True)
    report=dict(requirements=['CON-ARCH-006'],status='proposed_plan_only_no_CAD_change',rows=rows,
        source_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in (Path(__file__),path)},physical_qualified=False)
    (ROOT/'.codex-tmp/registered-housing-fit/lower/right-normal/receiver-mouth-options.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
if __name__=='__main__':run()
