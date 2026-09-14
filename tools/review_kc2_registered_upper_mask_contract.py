"""CON-ARCH-006 supplemental right BRep contract, no new CAD sampling.

Retains the failed seam heuristic report unchanged. Its complete actual-solid
section comparisons are combined with an independently literal required field,
and the separately actual-audited/recalculated partition masks. No required
geometry is intersected with actual material to hide a missing region.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from shapely import wkt
from shapely.geometry import box,Point,LineString
from shapely.ops import unary_union
from tools.kc2_registered_release_gate import check_sections

ROOT=Path(__file__).resolve().parents[1]
SEAM_ERRORS={'missing structure is not between both split parts','unfilled area wider than nominal split'}
PROFILE={'mx':(7.8,9.3,7.8,9.3),'choc_v1':(5.3,6.5,5.1,6.6),'deep_sea':(5.05,6.25,5.1,6.6)}
SCHEMA='right-upper-mask-contract-v1'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def diagnostic_gate(record):
    errors=set(record.get('errors',[]))
    if record.get('status')!='failed' or not errors or not errors.issubset(SEAM_ERRORS):
        raise ValueError('Only the two diagnosed seam heuristics may be supplemented')
    if len(record.get('parts',[]))!=2:raise ValueError('Exactly two complete actual part audits required')
    for part in record['parts']:check_sections(part)
    if any(row.get('errors') for row in record.get('independent_features',[])):
        raise ValueError('Actual functional feature failure cannot be waived')

def merge_bindings(records):
    result={}
    for record in records:
        for name,sha in record.get('source_sha256',{}).items():
            if name in result and result[name]!=sha:raise ValueError('Conflicting evidence source '+name)
            result[name]=sha
    return result

def area_gate(expected,declared,actual_missing,actual_extra):
    missing=expected.difference(declared).area;extra=declared.difference(expected).area
    total_missing=missing+actual_missing;total_extra=extra+actual_extra
    return dict(contract_missing_mm2=missing,contract_extra_mm2=extra,
      actual_section_missing_mm2=actual_missing,actual_section_extra_mm2=actual_extra,
      combined_missing_bound_mm2=total_missing,combined_extra_bound_mm2=total_extra,
      errors=(['required structural material absent'] if total_missing>.001 else [])+
             (['material in functional void or exterior'] if total_extra>.001 else []))

def literal_contract(kind,old):
    geometry={k:wkt.loads(v) for k,v in old['plan_wkt'].items()}
    boxes=[(110,-1.5,116,-.3),(128,-1.5,134,-.3),(140.5875,10,141.7875,16)]
    grooves=unary_union([box(*v).buffer(.25,join_style=2) for v in boxes])
    patches=unary_union([box(x0-1.45,y0,x1+1.45,y1+1.45) if i<2 else box(x0-1.45,y0-1.45,x1,y1+1.45)
                         for i,(x0,y0,x1,y1) in enumerate(boxes)])
    domain=geometry['domain'].union(patches)
    bottom,top,bearing,boss=PROFILE[kind]
    def at(z):
        base=geometry['lands'] if z<4.4 else domain if z<top else geometry['bosses']
        switch=geometry['body'] if z<bottom or z>=top else geometry['openings']
        voids=geometry['bores'].union(geometry['service']).union(switch)
        if z>=bearing:voids=voids.union(geometry['pockets'])
        if 4.4<=z<5.2:voids=voids.union(grooves)
        return base.difference(voids)
    return at

def compare(kind,old,generation,diagnostic,profile):
    diagnostic_gate(diagnostic)
    if generation.get('side')!='right' or generation.get('kind')!=kind or generation.get('status')!='generated_pending_independent_review':
        raise ValueError('Wrong generation identity')
    if profile.get('status')!='pass' or profile.get('errors') or profile.get('kind')!=kind or profile.get('feature_count')!=2:
        raise ValueError('Current actual profile/mask qualification absent')
    for key,value in [('clip_ring_nominal_mm',.6),('neck_width_mm',2.),('head_diameter_mm',4.)]:
        if profile.get(key)!=value:raise ValueError('Actual protected profile contract differs')
    if profile.get('actual_full_projection_gap_mm',0)<.39999:raise ValueError('Actual gap below nominal minimum')
    masks=[wkt.loads(v) for v in profile.get('augmented_masks_wkt',[])]
    if len(masks)!=2 or any(m.geom_type!='Polygon' or not m.is_valid or m.is_empty for m in masks):
        raise ValueError('Missing two recalculated actual-audited masks')
    if masks[0].distance(masks[1])<.39999:raise ValueError('Recalculated mask gap is insufficient')
    contract=literal_contract(kind,old);parts=[];errors=[];wanted_heights=set()
    if len(generation.get('parts',[]))!=2:raise ValueError('Wrong declared part count')
    for index,(produced,audited,mask) in enumerate(zip(generation['parts'],diagnostic['parts'],masks)):
        layers=produced['layers'];levels=sorted({layer[k] for layer in layers for k in ('z0','z1')})
        if levels!=audited['levels_mm']:raise ValueError('Actual section audit omits declared height transition')
        wanted_heights.update(levels);rows=[]
        for lo,hi,actual in zip(levels,levels[1:],audited['sections']):
            z=(lo+hi)/2
            declared=unary_union([wkt.loads(l['wkt']) for l in layers if l['z0']<=z<l['z1']])
            row=area_gate(contract(z).intersection(mask),declared,actual['missing_mm2'],actual['extra_mm2'])
            row.update(z0_mm=lo,z1_mm=hi,z_mm=z);rows.append(row);errors.extend(row['errors'])
        parts.append(dict(part=index,sections=rows))
    bottom,top,bearing,boss=PROFILE[kind];wanted_heights.update([4.1,4.4,bottom,top,bearing,boss])
    profile_rows=profile.get('sections',[])
    if not profile_rows:raise ValueError('Missing actual whole-height profile sections')
    levels=[profile_rows[0]['z0_mm']]+[row['z1_mm'] for row in profile_rows]
    if levels!=sorted(wanted_heights):raise ValueError('Actual mask/profile height coverage differs')
    for lo,hi,row in zip(levels,levels[1:],profile_rows):
        if row['z0_mm']!=lo or row.get('errors'):raise ValueError('Actual profile section failed')
        capture=bottom<(lo+hi)/2<top
        if row.get('capture_required') is not capture:raise ValueError('Actual capture stratum missing')
        moves=row.get('one_mm_motion_collision_area_mm2',{})
        expected={'positive_x','negative_x','positive_y','negative_y'} if capture else set()
        if set(moves)!=expected or any(v<=1e-6 for v in moves.values()):raise ValueError('Actual in-plane capture evidence incomplete')
    feature_levels=sorted({4.1,4.4,5.2,bottom,top,bearing,boss})
    if [r.get('z') for r in diagnostic.get('independent_features',[])]!=[(a+b)/2 for a,b in zip(feature_levels,feature_levels[1:])]:
        raise ValueError('Original complete independent feature checks missing')
    return dict(status='pass' if not errors else 'failed',errors=sorted(set(errors)),parts=parts)

def review(kind):
    folder=ROOT/'.codex-tmp/registered-housing-fit/upper'/('right-'+kind)
    current=folder/'brep-review.json';archive=folder/'brep-review-seam-diagnostic.json'
    if not archive.exists():
        candidate=json.loads(current.read_bytes());diagnostic_gate(candidate)
        shutil.copy2(current,archive)
    elif current.exists():
        existing=json.loads(current.read_bytes())
        if existing.get('schema')==SCHEMA:
            if existing.get('diagnostic_sha256')!=digest(archive):raise ValueError('Preserved diagnostic identity changed')
        elif current.read_bytes()!=archive.read_bytes():raise ValueError('Refusing unmatched existing diagnostic replacement')
    diagnostic=json.loads(archive.read_bytes());diagnostic_gate(diagnostic)
    gp=folder/'generation.json';sp=folder/'split-review.json';oldpath=ROOT/f'docs/reports/solid-filled-plates-20260913/right-{kind}.json'
    generation=json.loads(gp.read_bytes());profile=json.loads(sp.read_bytes());old=json.loads(oldpath.read_bytes())
    bindings=merge_bindings([diagnostic,profile,generation])
    required={gp.relative_to(ROOT).as_posix():digest(gp)}
    for name,sha in generation['outputs'].items():required[(folder/name).relative_to(ROOT).as_posix()]=sha
    for name,sha in required.items():
        if diagnostic.get('source_sha256',{}).get(name)!=sha:raise ValueError('Actual diagnostic STEP/STL/generation identity differs')
    for name in [gp.relative_to(ROOT).as_posix(),(folder/f'kc2_right_{kind}_upper_housing.step').relative_to(ROOT).as_posix()]:
        if profile.get('source_sha256',{}).get(name)!=required[name]:raise ValueError('Actual profile source identity differs')
    for path in [archive,gp,sp,oldpath,Path(__file__),ROOT/'tools/test_review_kc2_registered_upper_mask_contract.py',ROOT/'tools/kc2_registered_release_gate.py']:
        key=path.relative_to(ROOT).as_posix();sha=digest(path)
        if key in bindings and bindings[key]!=sha:raise ValueError('Conflicting current source '+key)
        bindings[key]=sha
    for name,sha in bindings.items():
        if digest(ROOT/name)!=sha:raise ValueError('Changed bound source '+name)
    result=compare(kind,old,generation,diagnostic,profile)
    output=dict(schema=SCHEMA,status=result['status'],errors=result['errors'],side='right',kind=kind,
      requirements=['CON-ARCH-006','OPS-ARCH-006'],source_sha256=bindings,parts=diagnostic['parts'],
      independent_features=diagnostic['independent_features'],mask_contract=result['parts'],
      diagnostic_sha256=digest(archive),diagnostic_errors=diagnostic['errors'],physical_qualified=False,
      actual_CAD_reimported=False,nominal_slot_clearance_mm=.4,
      scope='Exact literal required material intersect independent actual-audited masks; sum with frozen complete actual BRep section error bounds')
    if kind=='mx':
        y=44.17789411959343;line=LineString([(80,y),(82,y)])
        masks=[wkt.loads(v) for v in profile['augmented_masks_wkt']]
        gap=line.difference(unary_union(masks))
        output['local_seam_corner_example']=dict(y_mm=y,x_interval_mm=list(gap.bounds)[::2],width_mm=gap.length,
          interpretation='Local ownership transition is not a universal .40 maximum gap; relative slot clearance and full minimum gap are separate')
    for name,sha in bindings.items():
        if digest(ROOT/name)!=sha:raise ValueError('Sources changed during supplemental audit')
    current.write_text(json.dumps(output,indent=2)+'\n')
    print(kind,output['status'],output['errors'],flush=True)
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('kind',choices=list(PROFILE));args=parser.parse_args()
    raise SystemExit(review(args.kind)['status']!='pass')
