"""CON-ARCH-006 full actual lower voids; conservative .30 clearance, not .35 cutter.

Shares declared addition plans, independently checks actual source/native BRep.
No physical assembly, material strength or insertion force qualification.
"""
import argparse,hashlib,json,shutil,math
from pathlib import Path
from shapely import wkt
from shapely.ops import unary_union
from tools.review_kc2_local_covers import prism,cut_union
from tools.kc2_required_lower_clearance import required_envelope
from tools.kc2_magnetic_entry import entry_tools
ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.codex-tmp/registered-housing-fit/lower'

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def intersection_volume(shape,tool):
    return sum(s.intersect(t).Volume() for s in shape.Solids() for t in tool.Solids())
def removed_outside(base,final,allowed):
    removed=cut_union(base,final)
    for tool in allowed:removed=cut_union(removed,tool)
    return removed.Volume()
def magnet_delta(oldnormal,oldmag,normal,mag,entries):
    import cadquery as cq
    original=cut_union(oldnormal,oldmag);revised=cut_union(normal,mag)
    extra=cut_union(revised,original)
    for entry in entries:extra=cut_union(extra,entry)
    return dict(original_mm3=original.Volume(),revised_mm3=revised.Volume(),
        missing_mm3=cut_union(original,revised).Volume(),extra_mm3=extra.Volume(),
        blocked_mm3=intersection_volume(mag,original),
        entry_obstruction_mm3=sum(intersection_volume(mag,e) for e in entries))

def review(side,native=False):
    if side not in ('left','right'):raise ValueError('Invalid side')
    import cadquery as cq
    from tools.generate_kc2_magnetic_housings import load_plans
    from tools.kc2_lower_central_relief import wall_bands,floor_relief
    paths=[];frozen={};shapes={};baselines={};rows={}
    def bind(p):
        key=p.relative_to(ROOT).as_posix();sha=digest(p)
        if key in frozen and frozen[key]!=sha:raise ValueError('Changed source '+key)
        frozen[key]=sha
        return p
    def read(p):return json.loads(bind(p).read_text())
    for name in ('review_kc2_lower_voids_v2.py','test_review_kc2_lower_voids_v2.py',
        'kc2_required_lower_clearance.py','test_kc2_required_lower_clearance.py',
        'review_kc2_local_covers.py','kc2_magnetic_entry.py','test_kc2_magnetic_entry.py',
        'kc2_lower_central_relief.py','generate_kc2_magnetic_housings.py',
        'generate_kc2_x3_v2_housings.py','generate_kc2_housings.py','render_kc2_x3_joined.py'):
        bind(ROOT/'tools'/name)
    for s in ('left','right'):bind(ROOT/f'hardware/PCB/kc2_{s}/kc2_{s}.kicad_pcb')
    per=read(ROOT/'.codex-tmp/perimeter-wall-plans.json')['sides'][side]
    old=read(ROOT/f'docs/reports/reinforced-covers-20260913/{side}-lower.json')
    print('extract actual read-only component envelopes',flush=True)
    plans,_,_=load_plans();raw=plans[side]['component_geometries']
    required_xy=required_envelope(raw)
    protected=prism(required_xy,-.4,2.5)
    nominal=prism(wkt.loads(old['clearance_wkt']),-1,2.5)
    upperold=read(ROOT/f'docs/reports/solid-filled-plates-20260913/{side}-mx.json')
    pilots=cq.Compound.makeCompound([cq.Solid.makeCylinder(.55,2.8,cq.Vector(x,y,-.3),cq.Vector(0,0,1)) for x,y in upperold['mounting_centers']])
    for variant in ('normal','magnetic'):
        folder=STAGE/f'{side}-{variant}';rp=folder/'generation.json';record=read(rp)
        if record['status']!='generated_pending_independent_review':raise ValueError('Incomplete generation')
        for path,sha in record['source_sha256'].items():
            if digest(bind(ROOT/path))!=sha:raise ValueError('Stale generation source '+path)
        name=f'kc2_{side}_lower_housing'+('_magnetic' if variant=='magnetic' else '')+'.step'
        actual=bind(folder/name);baseline=bind(ROOT/'hardware/MODELS'/name)
        if digest(actual)!=record['outputs'][name]:raise ValueError('Changed actual STEP')
        if native:
            from tools.kc2_lower_native_identity import native_output
            bind(ROOT/'tools/kc2_lower_native_identity.py');bind(ROOT/'tools/test_kc2_lower_native_identity.py')
            nr=read(folder/'native-generation.json');row=native_output(nr,side,variant,digest(rp),digest(actual))
            for path,sha in nr['source_sha256'].items():
                if digest(bind(ROOT/path))!=sha:raise ValueError('Stale native source '+path)
            for field in ('readback','f3d'):
                p=bind(folder/row['readback_step' if field=='readback' else 'f3d'])
                if digest(p)!=row[field+'_sha256']:raise ValueError('Changed native artifact')
            actual=folder/row['readback_step']
        print('import actual/baseline',variant,flush=True)
        shape=cq.importers.importStep(str(actual)).val();base=cq.importers.importStep(str(baseline)).val()
        expected=1 if side=='left' else 2
        if len(shape.Solids())!=expected or not shape.isValid():raise ValueError('Invalid body count/topology')
        shapes[variant]=shape;baselines[variant]=base
        regs=read(folder/'registrar-snapshot.json')['registrars'] if side=='left' else record['registrars']
        wall=wkt.loads(per['wall_wkt']);floor=wkt.loads(per['floor_addition_wkt'])
        bands=[(-1,4.1,wall)] if side=='left' else wall_bands(wall)
        if side=='right':floor=floor_relief(floor)
        requirements=[prism(g,a,b) for a,b,g in bands]+[prism(floor,-2.2,-1)]
        for r in regs.values():requirements.extend([prism(wkt.loads(r['wall']),-1,5),prism(wkt.loads(r['floor_addition']),-2.2,-1)])
        allowed=[]
        if side=='right':
            mask=unary_union([wkt.loads(p['mask_wkt']) for p in record['parts']]);masktool=prism(mask,-2.3,5.1)
            requirements=[r.intersect(masktool) for r in requirements]
            allowed=[prism(wkt.loads(p['cutter_wkt']),-2.3,5.1) for p in record['parts'] if not wkt.loads(p['cutter_wkt']).is_empty]
        entries=entry_tools(side) if variant=='magnetic' else []
        for entry in entries:requirements=[cut_union(r,entry) for r in requirements]
        ordinary=wall.difference(unary_union([wkt.loads(r['wall']) for r in regs.values()]))
        gap=prism(ordinary,4.10001,4.4)
        print('conservative required component envelope',variant,flush=True)
        obstruction=intersection_volume(shape,protected)
        print('actual addition and baseline preservation',variant,flush=True)
        added=cut_union(shape,base)
        rows[variant]=dict(body_count=expected,component_obstruction_mm3=obstruction,
            new_material_nominal_clearance_obstruction_mm3=intersection_volume(added,nominal),
            pilot_obstruction_mm3=intersection_volume(shape,pilots),
            required_missing_mm3=sum(cut_union(r,shape).Volume() for r in requirements),
            ordinary_wall_upper_gap_obstruction_mm3=intersection_volume(shape,gap),
            canonical_baseline_removed_outside_relief_mm3=removed_outside(base,shape,allowed))
    print('old blind pockets and external magnetic entry',flush=True)
    magnet=magnet_delta(baselines['normal'],baselines['magnetic'],shapes['normal'],shapes['magnetic'],entry_tools(side))
    errors=[f'{variant}: {key}' for variant,row in rows.items() for key,value in row.items() if key.endswith('_mm3') and value>.002]
    errors += [f'magnet {key}' for key in ('missing_mm3','extra_mm3','blocked_mm3','entry_obstruction_mm3') if magnet[key]>.002]
    for path,sha in frozen.items():
        if digest(ROOT/path)!=sha:raise ValueError('Source changed during review '+path)
    report=dict(requirements=['CON-ARCH-006'],schema='lower-void-v2',status='fail' if errors else 'pass',errors=errors,
        side=side,native_readback=native,variants=rows,magnet=magnet,physical_qualified=False,
        component_envelope=dict(scope='Aggregate actual union, not separate per-class BRep tests',
            required_clearance_mm=.3,conservative_offset_mm=.301,circumscribed_buffer_radius_mm=.301/math.cos(math.pi/16),quad_segs=4,z_mm=[-.4,2.5],
            raw_classes_wkt={k:g.wkt for k,g in raw.items()},required_union_wkt=required_xy.wkt),
        scope='Actual required component/pilot voids, new-material nominal clearance, permitted baseline relief, wall/registrar inclusion, original blind pockets and external entry; physical fit separate',source_sha256=frozen)
    output=STAGE/(side+('-native' if native else '')+'-void-review.json')
    if output.exists():
        prior=json.loads(output.read_text())
        if prior.get('schema')!='lower-void-v2':
            archive=output.with_name(output.stem+'-superseded-'+digest(output)[:12]+'.json')
            if not archive.exists():shutil.copy2(output,archive)
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('source_sha256','component_envelope')}),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('side',choices=['left','right']);p.add_argument('--native',action='store_true');a=p.parse_args()
    raise SystemExit(bool(review(a.side,a.native)['errors']))
