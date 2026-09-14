"""CON-ARCH-006 direct actual right-upper audit against independent masked fill."""
import argparse,json,hashlib,shutil
from pathlib import Path
from shapely import wkt
from shapely.ops import unary_union
from tools.kc2_solid_plate import Layer
from tools.review_kc2_registered_upper_mask_contract import PROFILE,literal_contract,merge_bindings
ROOT=Path(__file__).resolve().parents[1]
SCHEMA='right-upper-direct-mask-contract-v1'

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require_current(bindings,reader):
    for name,sha in bindings.items():
        if reader(name)!=sha:raise ValueError('Changed bound source '+name)

def independent_layers(kind,old,generation,profile):
    if generation.get('side')!='right' or generation.get('kind')!=kind or generation.get('status')!='generated_pending_independent_review':raise ValueError('Wrong generation')
    if profile.get('status')!='pass' or profile.get('errors') or profile.get('kind')!=kind:raise ValueError('Actual profile not qualified')
    if any(profile.get(k)!=v for k,v in [('feature_count',2),('clip_ring_nominal_mm',.6),('neck_width_mm',2),('head_diameter_mm',4)]):raise ValueError('Wrong protected profile')
    masks=[wkt.loads(v) for v in profile.get('augmented_masks_wkt',[])]
    if len(masks)!=2 or any(m.geom_type!='Polygon' or not m.is_valid or m.is_empty for m in masks):raise ValueError('Wrong actual masks')
    if profile.get('actual_full_projection_gap_mm',0)<.39999 or masks[0].distance(masks[1])<.39999:raise ValueError('Insufficient gap')
    if len(generation.get('parts',[]))!=2:raise ValueError('Wrong parts')
    required_heights={4.1,4.4,5.2,*PROFILE[kind]};contract=literal_contract(kind,old);parts=[];rows=[]
    for index,(part,mask) in enumerate(zip(generation['parts'],masks)):
        levels=sorted({layer[k] for layer in part['layers'] for k in ('z0','z1')})
        if not required_heights.issubset(levels):raise ValueError('Missing required height transition')
        if levels[0]!=4.1 or levels[-1]!=PROFILE[kind][3]:raise ValueError('Wrong vertical extent')
        layers=[];sections=[]
        for lo,hi in zip(levels,levels[1:]):
            z=(lo+hi)/2;expected=contract(z).intersection(mask)
            declared=unary_union([wkt.loads(v['wkt']) for v in part['layers'] if v['z0']<=z<v['z1']])
            missing=expected.difference(declared).area;extra=declared.difference(expected).area
            if missing>1e-7 or extra>1e-7:raise ValueError('Declared material differs from independent mask contract')
            layers.append(Layer(lo,hi,expected));sections.append(dict(z_mm=z,declared_missing_mm2=missing,declared_extra_mm2=extra,required_area_mm2=expected.area))
        parts.append(layers);rows.append(dict(part=index,levels_mm=levels,sections=sections))
    heights=sorted({z for part in parts for layer in part for z in (layer.z0,layer.z1)})
    profile_rows=profile.get('sections',[])
    if len(profile_rows)!=len(heights)-1:raise ValueError('Missing actual profile strata')
    for lo,hi,row in zip(heights,heights[1:],profile_rows):
        if row.get('z0_mm')!=lo or row.get('z1_mm')!=hi or row.get('errors'):raise ValueError('Actual profile stratum differs')
        capture=PROFILE[kind][0]<(lo+hi)/2<PROFILE[kind][1];motions=row.get('one_mm_motion_collision_area_mm2',{})
        if row.get('capture_required') is not capture or set(motions)!=({'positive_x','negative_x','positive_y','negative_y'} if capture else set()) or any(v<=1e-6 for v in motions.values()):raise ValueError('Missing actual capture proof')
    return parts,rows

def review(kind):
    folder=ROOT/'.codex-tmp/registered-housing-fit/upper'/('right-'+kind)
    gp=folder/'generation.json';pp=folder/'split-review.json';op=ROOT/f'docs/reports/solid-filled-plates-20260913/right-{kind}.json'
    gen=json.loads(gp.read_bytes());profile=json.loads(pp.read_bytes());old=json.loads(op.read_bytes())
    bindings=merge_bindings([gen,profile]);step=folder/f'kc2_right_{kind}_upper_housing.step'
    for path in (gp,step,op):
        if profile.get('source_sha256',{}).get(path.relative_to(ROOT).as_posix())!=digest(path):raise ValueError('Actual profile identity differs')
    for name,sha in gen['outputs'].items():
        path=folder/name
        if digest(path)!=sha:raise ValueError('Changed generated output')
        bindings[path.relative_to(ROOT).as_posix()]=sha
    paths=[gp,pp,op,Path(__file__),ROOT/'tools/test_review_kc2_registered_upper_direct.py',ROOT/'tools/review_kc2_registered_upper_mask_contract.py',
           ROOT/'tools/kc2_solid_plate.py',ROOT/'tools/kc2_actual_sections.py',ROOT/'tools/test_kc2_actual_sections.py']
    for path in paths:
        name=path.relative_to(ROOT).as_posix();sha=digest(path)
        if name in bindings and bindings[name]!=sha:raise ValueError('Conflicting source '+name)
        bindings[name]=sha
    require_current(bindings,lambda name:digest(ROOT/name));layers,contract=independent_layers(kind,old,gen,profile)
    import cadquery as cq
    from tools.kc2_actual_sections import audit_prismatic_solid
    print('direct independent actual STEP import',kind,flush=True)
    solids=cq.importers.importStep(str(step)).solids().vals()
    if len(solids)!=2:raise ValueError('Actual two-part identity differs')
    parts=[]
    for index,(solid,required) in enumerate(zip(solids,layers)):
        print('direct independent actual part',kind,index,flush=True);parts.append(audit_prismatic_solid(solid,required))
    errors=sorted({e for part in parts for e in part['errors']});require_current(bindings,lambda name:digest(ROOT/name))
    result=dict(schema=SCHEMA,status='failed' if errors else 'pass',errors=errors,side='right',kind=kind,parts=parts,
        independent_contract=contract,source_sha256=bindings,actual_CAD_reimported=True,physical_qualified=False,
        requirements=['CON-ARCH-006','OPS-ARCH-006'],scope='Complete actual BRep against independently literal required fill intersect actual-qualified masks; no seam heuristic waiver')
    path=folder/'brep-review.json'
    if path.exists() and json.loads(path.read_bytes()).get('schema')!=SCHEMA:
        archive=folder/('brep-review-before-direct-'+digest(path)[:12]+'.json')
        if not archive.exists():shutil.copy2(path,archive)
    path.write_text(json.dumps(result,indent=2)+'\n');print(kind,result['status'],errors,flush=True);return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('kind',choices=list(PROFILE));args=parser.parse_args()
    raise SystemExit(review(args.kind)['status']!='pass')
