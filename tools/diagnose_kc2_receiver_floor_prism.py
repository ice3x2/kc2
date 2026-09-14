"""CON-ARCH-006 bounded actual floor-ring/prism diagnosis; no CAD edits."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def transitions(shape,lo,hi):
    levels=sorted({lo,hi}|{round(v.Z,7) for v in shape.Vertices() if lo+1e-6<v.Z<hi-1e-6})
    errors=['interior Z transition'] if len(levels)>2 else []
    for face in shape.Faces():
        if face.geomType()!='PLANE':errors.append('nonplanar face');continue
        nz=abs(face.normalAt().z)
        if min(nz,abs(nz-1))>1e-7:errors.append('non-axis face')
    return levels,sorted(set(errors))

def run():
    import cadquery as cq
    from shapely import wkt
    from shapely.geometry import box,Point
    from tools.review_kc2_local_covers import prism,cut_union
    from tools.kc2_actual_sections import section_geometry
    folder=ROOT/'.codex-tmp/registered-housing-fit/lower/right-normal'
    gp=folder/'generation.json';sp=folder/'kc2_right_lower_housing.step';cp=folder/'receiver-cleanup-candidate.json'
    g=json.loads(gp.read_text());candidate=json.loads(cp.read_text())
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    if digest(sp)!=g['outputs'][sp.name]:raise ValueError('Stale source STEP')
    paths=[gp,sp,cp,Path(__file__),ROOT/'tools/test_diagnose_kc2_receiver_floor_prism.py',ROOT/'tools/kc2_actual_sections.py',ROOT/'tools/review_kc2_local_covers.py',ROOT/'tools/kc2_lower_split_extension.py']
    for name,sha in candidate['source_sha256'].items():
        p=ROOT/name
        if digest(p)!=sha:raise ValueError('Stale candidate input')
        paths.append(p)
    frozen={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    print('import current right normal B once',flush=True)
    bodies=sorted(cq.importers.importStep(str(sp)).solids().vals(),key=lambda s:s.Center().x)
    if len(bodies)!=2 or not all(s.isValid() for s in bodies):raise ValueError('Wrong valid source bodies')
    receiver=bodies[1];mask=wkt.loads(g['parts'][1]['mask_wkt']);rows=[]
    for candidate_row in candidate['rows']:
        y=candidate_row['y_mm'];seam=81.84375
        male=box(seam-.1,y-1,seam+3,y+1).union(Point(seam+3,y).buffer(2.25,quad_segs=24))
        void=male.buffer(.40004,quad_segs=128)
        ring=void.buffer(1.2,quad_segs=128).difference(void).intersection(box(seam+.30004,y-5,seam+8,y+5));b=ring.bounds
        roi=box(b[0]-1,b[1]-1,b[2]+1,b[3]+1)
        print('full receiver floor ring',y,roi.bounds,flush=True)
        floor=receiver.intersect(prism(roi,-2.2,-1));levels,errors=transitions(floor,-2.2,-1)
        sections=[]
        for lo,hi in zip(levels,levels[1:]):
            z=(lo+hi)/2;actual=section_geometry(floor,z)
            sections.append(dict(z_mm=z,actual_area_mm2=actual.area,required_ring_missing_mm2=ring.difference(actual).area,actual_wkt=actual.wkt))
        wanted=prism(ring,-2.2,-1)
        missing=cut_union(wanted,floor).Volume()
        floor_volume_error=abs(floor.Volume()-sum(s['actual_area_mm2']*(hi-lo) for s,(lo,hi) in zip(sections,zip(levels,levels[1:]))))
        floor_ok=not errors and missing<=.002 and floor_volume_error<=.002 and all(s['required_ring_missing_mm2']<=.001 for s in sections)
        print('full ring missing volume',missing,'check abovefloor full original diagnosis ROI',flush=True)
        above_roi=box(81.84375-.5,y-4,81.84375+6,y+4)
        above=receiver.intersect(prism(above_roi,-1,2.5));az,ae=transitions(above,-1,2.5)
        zero=section_geometry(above,0);asections=[]
        for lo,hi in zip(az,az[1:]):
            z=(lo+hi)/2;actual=section_geometry(above,z)
            asections.append(dict(z_mm=z,area_mm2=actual.area,missing_vs_z0_mm2=zero.difference(actual).area,extra_vs_z0_mm2=actual.difference(zero).area))
        volerror=abs(above.Volume()-zero.area*3.5)
        cut=wkt.loads(candidate_row['cut_wkt']);oldzero=wkt.loads(candidate_row['rounded_section_wkt']).union(cut)
        z0diff=zero.symmetric_difference(oldzero).area
        above_ok=not ae and volerror<=.002 and z0diff<=.001 and all(max(s['missing_vs_z0_mm2'],s['extra_vs_z0_mm2'])<=.001 for s in asections)
        rows.append(dict(y_mm=y,required_ring_wkt=ring.wkt,ring_bounds_mm=b,ring_missing_from_full_declared_B_mask_mm2=ring.difference(mask).area,
          floor=dict(eligible=floor_ok,roi_wkt=roi.wkt,levels_mm=levels,errors=errors,required_ring_missing_mm3=missing,actual_volume_mm3=floor.Volume(),stratified_section_volume_error_mm3=floor_volume_error,sections=sections),
          above_floor=dict(constant_prism_eligible=above_ok,roi_wkt=above_roi.wkt,levels_mm=az,errors=ae,sections=asections,z0_actual_wkt=zero.wkt,z0_candidate_source_difference_mm2=z0diff,volume_vs_z0_extrusion_error_mm3=volerror,cut_outside_roi_mm2=cut.difference(above_roi).area)))
    if frozen!={p.relative_to(ROOT).as_posix():digest(p) for p in paths}:raise ValueError('Source changed during diagnosis')
    result=dict(requirements=['CON-ARCH-006'],status='diagnosed_not_accepted',source_sha256=frozen,rows=rows,physical_qualified=False,
      scope='Full 1.2 XY ring through floor; whole old mouth ROI axis-face/Z-transition/section/volume constancy, not final cleanup approval')
    out=folder/'receiver-floor-prism-diagnosis.json';out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps([dict(y_mm=r['y_mm'],floor_eligible=r['floor']['eligible'],ring_missing_mm3=r['floor']['required_ring_missing_mm3'],above_prism_eligible=r['above_floor']['constant_prism_eligible'],above_errors=r['above_floor']['errors']) for r in rows]),flush=True)
    return result

if __name__=='__main__':run()
