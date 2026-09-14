"""CON-ARCH-006 actual right-upper complete-height split audit.

Actual planar horizontal/vertical faces establish constant sections between
every actual vertex height. All those strata are inspected, not a selected
pretty view. Profile masks are explicitly recalculated for registrar-augmented
domain, compared with recorded producer features and base-domain evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
from shapely import affinity,wkt
from shapely.geometry import Point,GeometryCollection,box
from shapely.ops import unary_union

ROOT=Path(__file__).resolve().parents[1]
PROFILE={'mx':(7.8,9.3,7.8,9.3),'choc_v1':(5.3,6.5,5.1,6.6),'deep_sea':(5.05,6.25,5.1,6.6)}


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def validate_features(features):
    if len(features)!=2:raise ValueError('Exactly two capture features required')
    for feature in features:
        x,y,angle=feature['point']
        key=box(x-.9,y-1,x+3,y+1).union(Point(x+3,y).buffer(2.0,quad_segs=24))
        key=affinity.rotate(key,angle,origin=(x,y))
        if key.symmetric_difference(wkt.loads(feature['key_wkt'])).area>1e-7:
            raise ValueError('Key does not preserve 2.00 mm neck and 4.00 mm head')
        slot=key.buffer(.40004,quad_segs=128)
        if slot.symmetric_difference(wkt.loads(feature['slot_wkt'])).area>1e-7:
            raise ValueError('Incorrect capture clearance')
    if wkt.loads(features[0]['zone_wkt']).intersection(wkt.loads(features[1]['zone_wkt'])).area>1e-8:
        raise ValueError('Capture zones are not distinct')


def section_errors(actual,masks,features,openings,reserved):
    errors=[]
    for section,mask in zip(actual,masks):
        if section.difference(mask).area>.001:errors.append('actual material outside assigned partition')
    if not any(s.is_empty for s in actual) and actual[0].distance(actual[1])<.39999:
        errors.append('actual A/B gap below .40 mm')
    for opening in openings:
        ring=opening.buffer(.6).difference(opening)
        if not any(ring.difference(s).area<.001 for s in actual):errors.append('actual clip ring interrupted')
    for feature in features:
        donor=0 if feature['donor']=='a' else 1;receiver=1-donor
        key=wkt.loads(feature['key_wkt']);slot=wkt.loads(feature['slot_wkt'])
        collar=wkt.loads(feature['receiver_wkt']).difference(slot).difference(reserved)
        if key.difference(actual[donor]).area>.001:errors.append('missing actual key material')
        if collar.difference(actual[receiver]).area>.001:errors.append('missing actual receiver material')
        if slot.intersection(actual[receiver]).area>.001:errors.append('actual receiver fills slot')
    return sorted(set(errors))


def review(kind):
    import cadquery as cq
    from tools.kc2_profile_split import profile_split
    from tools.kc2_actual_sections import section_geometry
    folder=ROOT/'.codex-tmp/registered-housing-fit/upper'/('right-'+kind)
    generation=folder/'generation.json'
    produced=json.loads(generation.read_text())
    if produced['status']!='generated_pending_independent_review':raise ValueError('Actual generation not complete')
    step=folder/f'kc2_right_{kind}_upper_housing.step'
    if digest(step)!=produced['outputs'][step.name]:raise ValueError('STEP identity mismatch')
    for name,sha in produced['source_sha256'].items():
        if digest(ROOT/name)!=sha:raise ValueError('Changed producer source '+name)
    original=ROOT/f'docs/reports/solid-filled-plates-20260913/right-{kind}.json'
    baseplan=ROOT/f'.codex-tmp/registered-housing-fit/ab/profiles/{kind}-split-plan.json'
    sources=[generation,step,original,baseplan,Path(__file__),ROOT/'tools/test_review_kc2_profile_split_cad.py',
             ROOT/'tools/kc2_profile_split.py',ROOT/'tools/kc2_actual_sections.py',ROOT/'tools/test_kc2_actual_sections.py']
    before={p.relative_to(ROOT).as_posix():digest(p) for p in sources}
    old=json.loads(original.read_text());geometry={k:wkt.loads(v) for k,v in old['plan_wkt'].items()}
    additions=unary_union([wkt.loads(r['addition']) for r in produced['registrars'].values()])
    domain=geometry['domain'].union(additions)
    print(kind,'recalculate augmented profile mask',flush=True)
    a,b,expected=profile_split(domain,geometry['openings'],geometry['service'],old['mounting_centers'])
    masks=[a,b];features=produced['partition']['capture_features'];errors=[]
    validate_features(features)
    if len(features)!=2 or len(expected['capture_features'])!=2:raise ValueError('Exactly two capture features required')
    for recorded,recomputed in zip(features,expected['capture_features']):
        if recorded['donor']!=recomputed['donor']:raise ValueError('Recalculated feature donor differs')
        for field in ['key_wkt','slot_wkt','receiver_wkt','zone_wkt']:
            if wkt.loads(recorded[field]).symmetric_difference(wkt.loads(recomputed[field])).area>1e-7:
                raise ValueError('Recalculated feature differs: '+field)
    baseline=json.loads(baseplan.read_text())
    base_delta=[mask.symmetric_difference(wkt.loads(saved)).area for mask,saved in zip(masks,baseline['masks_wkt'])]
    print(kind,'import actual STEP',flush=True)
    solids=cq.importers.importStep(str(step)).solids().vals()
    if len(solids)!=2 or any(not s.isValid() for s in solids):raise ValueError('Invalid actual two-solid STEP')
    for s,p in zip(solids,produced['parts']):
        if abs(s.Volume()-p['volume_mm3'])>.01:raise ValueError('Actual part order/volume mismatch')
    for solid in solids:
        for face in solid.Faces():
            if face.geomType()!='PLANE':raise ValueError('Actual shape not prismatic: nonplanar face')
            nz=face.normalAt().z
            if min(abs(nz),abs(abs(nz)-1))>1e-7:raise ValueError('Actual shape contains sloped face')
    plate_bottom,plate_top,bearing,boss_top=PROFILE[kind]
    heights=sorted({round(v.Z,7) for s in solids for v in s.Vertices()}|
                   {4.1,4.4,plate_bottom,plate_top,bearing,boss_top})
    sections=[];projections=[GeometryCollection(),GeometryCollection()]
    for lo,hi in zip(heights,heights[1:]):
        if hi-lo<1e-6:continue
        z=(lo+hi)/2
        print(kind,'actual height interval',lo,hi,flush=True)
        actual=[section_geometry(s,z) if s.BoundingBox().zmin<z<s.BoundingBox().zmax else GeometryCollection() for s in solids]
        in_plate=plate_bottom<z<plate_top
        reserved=geometry['openings'].union(geometry['service']).union(geometry['bores'] if z<bearing else geometry['pockets'])
        interval_errors=section_errors(actual,masks,features if in_plate else [],
                                       list(geometry['openings'].geoms) if in_plate else [],reserved)
        motions={}
        if in_plate:
            for name,dx,dy in [('positive_x',1,0),('negative_x',-1,0),('positive_y',0,1),('negative_y',0,-1)]:
                area=affinity.translate(actual[0],xoff=dx,yoff=dy).intersection(actual[1]).area
                motions[name]=area
                if area<=1e-6:interval_errors.append('actual in-plane capture missing '+name)
        if 4.1<z<boss_top:
            for center in old['mounting_centers']:
                point=Point(*center)
                outer=1.5 if z<4.4 else 2.3
                inner=.8 if z<bearing else 1.7
                ring=point.buffer(outer,quad_segs=64).difference(point.buffer(inner,quad_segs=64))
                if not any(ring.difference(s).area<.001 for s in actual):interval_errors.append('actual mounting annulus interrupted')
        for index,section in enumerate(actual):projections[index]=projections[index].union(section)
        sections.append(dict(z0_mm=lo,z1_mm=hi,errors=sorted(set(interval_errors)),
                             actual_area_mm2=[s.area for s in actual],capture_required=in_plate,
                             one_mm_motion_collision_area_mm2=motions))
        errors.extend(interval_errors)
    projected_gap=projections[0].distance(projections[1])
    if projected_gap<.39999:errors.append('Actual full projection gap below .40 mm')
    if before!={p.relative_to(ROOT).as_posix():digest(p) for p in sources}:raise ValueError('Sources changed during review')
    evidence=dict(requirements=['CON-ARCH-006'],status='pass' if not errors else 'failed',kind=kind,
        errors=sorted(set(errors)),source_sha256=before,sections=sections,physical_qualified=False,native_verified=False,
        actual_full_projection_gap_mm=projected_gap,
        mask_provenance='Recalculated from published old domain plus exact recorded registrar additions; producer did not record masks',
        augmented_masks_wkt=[s.wkt for s in masks],base_mask_symmetric_difference_mm2=base_delta,
        feature_count=2,clip_ring_nominal_mm=.6,neck_width_mm=2.0,head_diameter_mm=4.0,
        section_backend='Actual kernel section face outer/inner wires, independent area cross-check',
        scope='Actual STEP prismatic whole-height partition, plate-band clip rings/keys/receivers/capture, mounting annuli; not STL/native/physical approval')
    (folder/'split-review.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({k:v for k,v in evidence.items() if k not in ['sections','source_sha256','augmented_masks_wkt']}),flush=True)
    if errors:raise SystemExit(1)
    return evidence


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('kind',choices=list(PROFILE));review(parser.parse_args().kind)
