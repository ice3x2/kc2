"""CON-ARCH-006 independent literal left relief and complete actual void scope.

Does not execute the frozen unrelieved V2 review, change its sources, or waive
any original baseline stock. Actual emission requires explicitly revised input.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from shapely import affinity,wkt
from shapely.geometry import box,Polygon
from shapely.ops import unary_union
from tools.review_kc2_local_covers import prism,cut_union
from tools.review_kc2_lower_voids_v2 import intersection_volume,removed_outside,magnet_delta
from tools.kc2_required_lower_clearance import required_envelope
from tools.kc2_magnetic_entry import entry_tools

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.codex-tmp/registered-housing-fit/lower'
FEATURES='.codex-tmp/registered-housing-fit/central'
ZERO_FIELDS=('component_obstruction_mm3','new_material_nominal_clearance_obstruction_mm3',
    'pilot_obstruction_mm3','required_missing_mm3','ordinary_wall_upper_gap_obstruction_mm3',
    'canonical_baseline_removed_outside_relief_mm3')
CONTRACT=dict(wall_z_mm=[-1,1.5,1.8,4.1],floor_z_mm=[-2.2,-1],ys_mm=[95,117])


def required_plan(wall,floor):
    if any(g.is_empty or not g.is_valid for g in (wall,floor)):
        raise ValueError('Invalid declared addition')
    # Literal approved central dimensions; no producer relief helper is used.
    tongue=Polygon([(-1,-1.2),(2.4,-1.2),(2.8,-.8),(2.8,.8),(2.4,1.2),(-1,1.2)])
    root=box(1.2,1.35,5,2.55).union(box(1.2,-2.55,5,-1.35))
    def placed(g):
        return unary_union([affinity.translate(affinity.scale(g,xfact=-1,origin=(0,0)),xoff=.1,yoff=y)
                            for y in (95.,117.)])
    male=placed(tongue);window=placed(box(0,-2.85,2,2.85))
    low=wall.intersection(window).difference(male)
    transition=wall.intersection(window)
    floor_cut=floor.intersection(placed(root.buffer(.3,join_style=2))).difference(male)
    return dict(bands=[(-1,1.5,wall.difference(low)),(1.5,1.8,wall.difference(transition)),
                       (1.8,4.1,wall)],floor=floor.difference(floor_cut),male=male)


def metric_errors(row):
    errors=[]
    if type(row.get('body_count')) is not int or row['body_count']!=1:errors.append('body_count')
    for key in ZERO_FIELDS:
        value=row.get(key)
        if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=.002:
            errors.append(key)
    details=row.get('required_stock_details_mm3');count=row.get('required_stock_count')
    if (type(count) is not int or count<=0 or not isinstance(details,list) or len(details)!=count
        or any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=.002 for v in details)):
        errors.append('required_stock_details_mm3')
    elif sum(details)!=row.get('required_missing_mm3'):
        errors.append('required_stock_sum')
    males=row.get('protected_male_missing_mm3')
    if (not isinstance(males,dict) or set(males)!={'95','117'}
        or any(type(v) not in (int,float) or not math.isfinite(v) or v!=0 for v in males.values())):
        errors.append('protected_male_missing_mm3')
    return errors


def generation_gate(record,magnetic):
    marker=record.get('left_central_relief',{})
    if (record.get('status')!='generated_pending_independent_review' or record.get('side')!='left'
        or record.get('magnetic') is not magnetic or type(record.get('body_count')) is not int
        or record['body_count']!=1 or any(marker.get(k)!=v for k,v in CONTRACT.items())):
        raise ValueError('Revised left-only generation with exact relief contract required')


def validate_shape(shape):
    solids=shape.Solids();volume=shape.Volume()
    if (not shape.isValid() or len(solids)!=1 or not math.isfinite(volume) or volume<=0
        or not solids[0].isValid() or not solids[0].Shells()
        or any(not shell.Closed() for shell in solids[0].Shells())):
        raise ValueError('Invalid actual left body')
    # Same exact identity ownership pattern as the frozen strata import audit.
    for kind in ('Faces','Edges','Vertices'):
        whole=list(getattr(shape,kind)());owned=[p for solid in solids for p in getattr(solid,kind)()]
        if len(whole)!=len(owned):raise ValueError('Extraneous/shared topology: '+kind)
        buckets={}
        for p in owned:buckets.setdefault(hash(p),[]).append(p)
        for p in whole:
            candidates=buckets.get(hash(p),[])
            match=next((i for i,q in enumerate(candidates) if p.isSame(q)),None)
            if match is None:raise ValueError('Unowned topology: '+kind)
            candidates.pop(match)
        if any(buckets.values()):raise ValueError('Missing topology: '+kind)


def load_males(read,importer):
    """Independently authenticate and import actual historically trimmed roots."""
    record=json.loads(read(FEATURES+'/central-features.json'))
    if record.get('status')!='feature_geometry_pass_integration_pending' or not record.get('source_sha256'):
        raise ValueError('Missing original feature provenance')
    for name,sha in record['source_sha256'].items():
        if hashlib.sha256(read(name)).hexdigest()!=sha:raise ValueError('Changed original feature source')
    rows=[r for r in record.get('features',[]) if r.get('name','').startswith('left-')]
    if len(rows)!=2 or {r.get('name') for r in rows}!={'left-central-y95','left-central-y117'}:
        raise ValueError('Missing or duplicate protected left features')
    males={}
    for y in (95,117):
        name='left-central-y'+str(y);path=FEATURES+'/'+name+'.step'
        if hashlib.sha256(read(path)).hexdigest()!=record.get('outputs',{}).get(name+'.step'):
            raise ValueError('Changed or unbound isolated male STEP')
        shape=importer(path);validate_shape(shape)
        expected=next(r['volume_mm3'] for r in rows if r['name']==name)
        if type(expected) not in (int,float) or not math.isfinite(expected) or expected<=0 or abs(shape.Volume()-expected)>.002:
            raise ValueError('Isolated male identity differs')
        males[y]=shape
    return males


def protected_male_missing(shape,males):
    if set(males)!={95,117}:raise ValueError('Both actual protected male references required')
    return {str(y):cut_union(male,shape).Volume() for y,male in males.items()}


def review(native=False):
    import cadquery as cq
    from tools.generate_kc2_magnetic_housings import load_plans
    frozen={};shapes={};baselines={};rows={}
    def bind(path):
        path=Path(path);key=path.relative_to(ROOT).as_posix()
        data=path.read_bytes();sha=hashlib.sha256(data).hexdigest()
        if key in frozen and frozen[key]!=sha:raise ValueError('Changed source '+key)
        frozen[key]=sha
        return data
    def read(path):return json.loads(bind(path))
    dependencies=('review_kc2_left_central_voids.py','test_review_kc2_left_central_voids.py',
        'review_kc2_lower_voids_v2.py','test_review_kc2_lower_voids_v2.py',
        'review_kc2_local_covers.py','kc2_required_lower_clearance.py','test_kc2_required_lower_clearance.py',
        'kc2_magnetic_entry.py','test_kc2_magnetic_entry.py','generate_kc2_magnetic_housings.py',
        'generate_kc2_x3_v2_housings.py','generate_kc2_housings.py','render_kc2_x3_joined.py')
    for name in dependencies:bind(ROOT/'tools'/name)
    for side in ('left','right'):bind(ROOT/f'hardware/PCB/kc2_{side}/kc2_{side}.kicad_pcb')
    # Fail before expensive CAD or report emission if either variant is stale.
    records={v:read(STAGE/f'left-{v}/generation.json') for v in ('normal','magnetic')}
    for variant,record in records.items():generation_gate(record,variant=='magnetic')
    per=read(ROOT/'.codex-tmp/perimeter-wall-plans.json')['sides']['left']
    old=read(ROOT/'docs/reports/reinforced-covers-20260913/left-lower.json')
    upper=read(ROOT/'docs/reports/solid-filled-plates-20260913/left-mx.json')
    print('extract full actual left component envelopes',flush=True)
    plans,_,_=load_plans();raw=plans['left']['component_geometries'];required_xy=required_envelope(raw)
    protected=prism(required_xy,-.4,2.5);nominal=prism(wkt.loads(old['clearance_wkt']),-1,2.5)
    pilots=cq.Compound.makeCompound([cq.Solid.makeCylinder(.55,2.8,cq.Vector(x,y,-.3),cq.Vector(0,0,1))
                                    for x,y in upper['mounting_centers']])
    wall=wkt.loads(per['wall_wkt']);plan=required_plan(wall,wkt.loads(per['floor_addition_wkt']))
    males=load_males(lambda name:bind(ROOT/name),lambda name:cq.importers.importStep(str(ROOT/name)).val())
    for variant,record in records.items():
        folder=STAGE/f'left-{variant}';generation=folder/'generation.json'
        for name,sha in record['source_sha256'].items():
            if hashlib.sha256(bind(ROOT/name)).hexdigest()!=sha:raise ValueError('Stale generation source '+name)
        name='kc2_left_lower_housing'+('_magnetic' if variant=='magnetic' else '')+'.step'
        actual=folder/name;baseline=ROOT/'hardware/MODELS'/name
        if hashlib.sha256(bind(actual)).hexdigest()!=record['outputs'][name]:raise ValueError('Changed STEP')
        bind(baseline)
        if native:
            from tools.kc2_lower_native_identity import native_output
            for dependency in ('kc2_lower_native_identity.py','test_kc2_lower_native_identity.py'):
                bind(ROOT/'tools'/dependency)
            nr=read(folder/'native-generation.json')
            identity=native_output(nr,'left',variant,hashlib.sha256(bind(generation)).hexdigest(),
                                   hashlib.sha256(bind(actual)).hexdigest())
            for path,sha in nr['source_sha256'].items():
                if hashlib.sha256(bind(ROOT/path)).hexdigest()!=sha:raise ValueError('Stale native source')
            for field,key in (('readback','readback_step'),('f3d','f3d')):
                if hashlib.sha256(bind(folder/identity[key])).hexdigest()!=identity[field+'_sha256']:
                    raise ValueError('Changed native artifact')
            actual=folder/identity['readback_step']
        print('import actual/baseline left',variant,flush=True)
        shape=cq.importers.importStep(str(actual)).val();base=cq.importers.importStep(str(baseline)).val()
        validate_shape(shape);validate_shape(base)
        shapes[variant]=shape;baselines[variant]=base
        regs=read(folder/'registrar-snapshot.json')['registrars']
        requirements=[prism(g,a,b) for a,b,g in plan['bands']]+[prism(plan['floor'],-2.2,-1)]
        for registrar in regs.values():
            requirements.extend([prism(wkt.loads(registrar['wall']),-1,5),
                                 prism(wkt.loads(registrar['floor_addition']),-2.2,-1)])
        # The actual isolated Y95 root was trimmed for components historically;
        # an untrimmed nominal prism invents .9976846887 mm3 of missing stock.
        for entry in entry_tools('left') if variant=='magnetic' else []:
            requirements=[cut_union(r,entry) for r in requirements]
        ordinary=wall.difference(unary_union([wkt.loads(r['wall']) for r in regs.values()]))
        print('actual left full voids, inclusion and original-stock preservation',variant,flush=True)
        added=cut_union(shape,base)
        missing=[cut_union(r,shape).Volume() for r in requirements]
        rows[variant]=dict(body_count=1,component_obstruction_mm3=intersection_volume(shape,protected),
            protected_male_missing_mm3=protected_male_missing(shape,males),
            new_material_nominal_clearance_obstruction_mm3=intersection_volume(added,nominal),
            pilot_obstruction_mm3=intersection_volume(shape,pilots),
            required_missing_mm3=sum(missing),required_stock_details_mm3=missing,required_stock_count=len(missing),
            ordinary_wall_upper_gap_obstruction_mm3=intersection_volume(shape,prism(ordinary,4.10001,4.4)),
            canonical_baseline_removed_outside_relief_mm3=removed_outside(base,shape,[]))
    magnet=magnet_delta(baselines['normal'],baselines['magnetic'],shapes['normal'],shapes['magnetic'],entry_tools('left'))
    errors=[variant+': '+key for variant,row in rows.items() for key in metric_errors(row)]
    for key in ('missing_mm3','extra_mm3','blocked_mm3','entry_obstruction_mm3'):
        value=magnet[key]
        if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=.002:errors.append('magnet '+key)
    for path,sha in frozen.items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=sha:raise ValueError('Source changed during review '+path)
    report=dict(requirements=['CON-ARCH-006'],schema='lower-void-v2',status='fail' if errors else 'pass',errors=errors,
        side='left',native_readback=native,variants=rows,magnet=magnet,physical_qualified=False,
        left_central_relief=CONTRACT,baseline_relief_allowed=False,
        component_envelope=dict(scope='Aggregate actual union, not separate per-class BRep tests',
            required_clearance_mm=.3,conservative_offset_mm=.301,circumscribed_buffer_radius_mm=.301/math.cos(math.pi/16),
            quad_segs=4,z_mm=[-.4,2.5],raw_classes_wkt={k:g.wkt for k,g in raw.items()},required_union_wkt=required_xy.wkt),
        scope='Full actual left component/pilot voids and original stock, independent relieved new wall/floor and male/registrar inclusion; physical and joined checks separate',
        source_sha256=frozen)
    output=STAGE/('left'+('-native' if native else '')+'-void-review.json')
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'],errors,flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--native',action='store_true')
    raise SystemExit(bool(review(parser.parse_args().native)['errors']))
