"""CON-ARCH-006 PLAN ONLY: printable receiver collar feasibility, no CAD edits.

Fixed seam/head/neck/gap; evaluate collision-free stock against the existing
conservative component cutout and case domain. Candidate relocation is NOT an
approved implementation and does not prove actual support or insertion force.
"""
import json,hashlib,math
from pathlib import Path
from shapely import wkt
from shapely.geometry import Point,box
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def geometry(y,stock):
    seam=81.84375
    donor=Point(seam+3,y).buffer(2.25,quad_segs=24).union(box(seam-.1,y-1,seam+3,y+1))
    void=donor.buffer(.40004,quad_segs=128)
    collar=void.buffer(stock/math.cos(math.pi/128),quad_segs=32).difference(void).intersection(box(seam+.30004,y-10,seam+12,y+10))
    return donor,collar
def run():
    p=ROOT/'docs/reports/reinforced-covers-20260913/right-lower.json'
    old=json.loads(p.read_text());protected=wkt.loads(old['clearance_wkt']);domain=wkt.loads(old['new_outline_wkt'])
    report=dict(requirements=['CON-ARCH-006'],status='proposed_plan_only_no_CAD_change',
        source_sha256={q.relative_to(ROOT).as_posix():digest(q) for q in [Path(__file__),p]},
        fixed_geometry=dict(seam_x_mm=81.84375,head_diameter_mm=4.5,neck_width_mm=2.,gap_mm=.40004),
        source_protection='Existing nominal .35 component exclusion, more conservative than required .30',levels=[])
    for stock in (1.2,1.,.8,.6):
        valid=[];oldrows=[]
        for y in [73.25,86.25]+[round(45+i*.05,2) for i in range(1401)]:
            donor,collar=geometry(y,stock);material=donor.union(collar)
            collision=material.intersection(protected).area;outside=material.difference(domain).area
            row=dict(y_mm=y,protected_overlap_mm2=collision,outside_case_mm2=outside)
            if y in (73.25,86.25):oldrows.append(row)
            if collision<1e-8 and outside<1e-8:valid.append(y)
        valid=sorted(set(valid));bands=[]
        for y in valid:
            if bands and y-bands[-1][1]<.050001:bands[-1][1]=y
            else:bands.append([y,y])
        nearest=sorted((y for y in valid if abs(y-73.25)>=9.),key=lambda y:abs(y-86.25))[:5]
        examples=[]
        for y in nearest:
            donor,collar=geometry(y,stock);examples.append(dict(y_mm=y,donor_wkt=donor.wkt,receiver_collar_wkt=collar.wkt))
        report['levels'].append(dict(minimum_requested_stock_mm=stock,existing_locations=oldrows,valid_y_bands_mm=bands,
            nearest_second_key_candidates_with_9mm_first_key_spacing=nearest,examples=examples))
        print(stock,'bands',bands,'nearest second',nearest,flush=True)
    out=ROOT/'.codex-tmp/registered-housing-fit/lower/right-normal/receiver-repair-plan.json'
    out.write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':run()
