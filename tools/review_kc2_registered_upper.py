"""CON-ARCH-006 source-frozen actual upper BRep sections and feature audit.

Does not call the producer's layer compositor. Fixed registrar dimensions and
physical voids are reconstructed independently from SRS and original records.
"""
from pathlib import Path
import json,hashlib,argparse
from shapely import wkt
from shapely.geometry import box
from shapely.ops import unary_union
from tools.kc2_solid_plate import Layer
from tools.review_kc2_filled_plates import audit_prismatic_solid,section_geometry

ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def feature_errors(actual,*,required,voids):
    errors=[]
    if required.difference(actual).area>.001:errors.append('required structural material absent')
    if actual.intersection(voids).area>.001:errors.append('functional void obstructed')
    return errors

def review(side,kind):
    import cadquery as cq
    if side not in ('left','right') or kind not in ('mx','choc_v1','deep_sea'):raise ValueError('Unknown identity')
    folder=ROOT/'.codex-tmp/registered-housing-fit/upper'/(side+'-'+kind)
    record_path=folder/'generation.json';r=json.loads(record_path.read_text())
    if r['status']!='generated_pending_independent_review':raise ValueError('Generation not complete')
    step=folder/f'kc2_{side}_{kind}_upper_housing.step'
    oldpath=ROOT/f'docs/reports/solid-filled-plates-20260913/{side}-{kind}.json'
    old=json.loads(oldpath.read_text());p={k:wkt.loads(v) for k,v in old['plan_wkt'].items()}
    sources=dict(r['source_sha256'])
    for path in (Path(__file__),ROOT/'tools/test_review_kc2_registered_upper.py',ROOT/'tools/review_kc2_filled_plates.py',
                 record_path,step,oldpath):sources[path.relative_to(ROOT).as_posix()]=digest(path)
    for name,sha in r['outputs'].items():
        path=folder/name
        if digest(path)!=sha:raise ValueError('Changed output')
        sources[path.relative_to(ROOT).as_posix()]=sha
    for name,sha in sources.items():
        if digest(ROOT/name)!=sha:raise ValueError('Changed review source: '+name)
    solids=cq.importers.importStep(str(step)).solids().vals()
    if len(solids)!=len(r['parts']):raise ValueError('Body count differs')
    rows=[];errors=[]
    for i,(shape,part) in enumerate(zip(solids,r['parts'])):
        print('actual complete-section audit',side,kind,i,flush=True)
        layers=[Layer(v['z0'],v['z1'],wkt.loads(v['wkt'])) for v in part['layers']]
        audit=audit_prismatic_solid(shape,layers);rows.append(audit);errors+=audit['errors']
    # Independently specified controller-edge rebate footprint (same on all profiles).
    boxes=([(30,-1.5,36,-.3),(48,-1.5,54,-.3),(16.9,10,18.1,16)] if side=='left' else
           [(110,-1.5,116,-.3),(128,-1.5,134,-.3),(140.5875,10,141.7875,16)])
    walls=[box(*v) for v in boxes];grooves=unary_union([g.buffer(.25,join_style=2) for g in walls])
    patches=[]
    for i,(x0,y0,x1,y1) in enumerate(boxes):
        patches.append(box(x0-1.45,y0,x1+1.45,y1+1.45) if i<2 else
                       (box(x0,y0-1.45,x1+1.45,y1+1.45) if side=='left' else box(x0-1.45,y0-1.45,x1,y1+1.45)))
    domain=p['domain'].union(unary_union(patches))
    bottom,top,bearing,boss_top={'mx':(7.8,9.3,7.8,9.3),'choc_v1':(5.3,6.5,5.1,6.6),'deep_sea':(5.05,6.25,5.1,6.6)}[kind]
    levels=sorted({4.1,4.4,5.2,bottom,top,bearing,boss_top});feature_rows=[]
    for lo,hi in zip(levels,levels[1:]):
        z=(lo+hi)/2
        sections=[section_geometry(s,z) for s in solids]
        actual=unary_union(sections)
        base=p['lands'] if z<4.4 else (domain if z<top else p['bosses'])
        switch=p['body'] if z<bottom or z>=top else p['openings']
        voids=p['bores'].union(p['service']).union(switch)
        if z>=bearing:voids=voids.union(p['pockets'])
        if 4.4<=z<5.2:voids=voids.union(grooves)
        required=base.difference(voids)
        if side=='right':
            # Only a thin, genuinely between-parts seam may be unfilled.
            allowed=sections[0].buffer(.205).union(sections[1].buffer(.205))
            missing=required.difference(actual)
            if missing.difference(allowed).area>.001:errors.append('unfilled area wider than nominal split')
            if missing.difference(sections[0].buffer(.4101).intersection(sections[1].buffer(.4101))).area>.001:
                errors.append('missing structure is not between both split parts')
            required=required.intersection(actual)
        errs=feature_errors(actual,required=required,voids=voids);errors+=errs
        if actual.difference(base).area>.001:errors.append('unplanned exterior material')
        feature_rows.append(dict(z=z,errors=errs,area_mm2=actual.area))
    for name,sha in sources.items():
        if digest(ROOT/name)!=sha:raise ValueError('Review source changed while running')
    result=dict(status='pass' if not errors else 'failed',errors=sorted(set(errors)),requirements=['CON-ARCH-006'],
                physical_qualified=False,source_sha256=sources,parts=rows,independent_features=feature_rows)
    (folder/'brep-review.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result['status'],result['errors'],flush=True);return result

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('side');a.add_argument('kind');v=a.parse_args()
    raise SystemExit(0 if review(v.side,v.kind)['status']=='pass' else 1)
