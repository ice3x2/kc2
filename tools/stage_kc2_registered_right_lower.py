"""CON-ARCH-006 right lower: original bodies, local relief, registered additions.

No canonical writes. Digital source generation only; independent root, capture,
populated assembly, native and print-force review remain separate gates.
"""
from pathlib import Path
import argparse,json,hashlib
from shapely import wkt
from shapely.geometry import box,Point,GeometryCollection
from shapely.ops import unary_union
from tools.kc2_lower_split_extension import retained_key_relief
from tools.kc2_registered_wall_plan import plan_registrars
from tools.kc2_central_flexure import prism,place_feature_solids
from tools.kc2_lower_central_relief import wall_bands,central_free_envelopes,male_insertion_envelopes,floor_relief
from tools.stage_kc2_registered_lower import stage_path,compose_lower,audit_additive
from tools.kc2_magnetic_entry import entry_tools,open_entries

ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def generate(magnetic=False):
    import cadquery as cq
    from tools.generate_kc2_magnetic_housings import load_plans,inspect_mesh,bounds
    side='right';folder=stage_path(side,magnetic);folder.mkdir(parents=True,exist_ok=True)
    stem='kc2_right_lower_housing'+('_magnetic' if magnetic else '')
    baselinepath=ROOT/'hardware/MODELS'/(stem+'.step')
    oldpath=ROOT/'docs/reports/reinforced-covers-20260913/right-lower.json'
    upperpath=ROOT/'docs/reports/solid-filled-plates-20260913/right-deep_sea.json'
    perimeterpath=ROOT/'.codex-tmp/perimeter-wall-plans.json'
    paths=[Path(__file__),baselinepath,oldpath,upperpath,perimeterpath]
    paths += [ROOT/'tools'/n for n in ['kc2_lower_split_extension.py','test_kc2_lower_split_extension.py',
        'kc2_split_fit_relief.py','kc2_registered_wall_plan.py','kc2_central_flexure.py','kc2_central_fit.py',
        'stage_kc2_registered_lower.py','test_stage_kc2_registered_lower.py','kc2_perimeter_wall.py',
        'kc2_lower_central_relief.py','test_kc2_lower_central_relief.py',
        'kc2_magnetic_entry.py','test_kc2_magnetic_entry.py',
        'generate_kc2_magnetic_housings.py','generate_kc2_x3_v2_housings.py','generate_kc2_housings.py','render_kc2_x3_joined.py']]
    paths += [ROOT/f'hardware/PCB/kc2_{s}/kc2_{s}.kicad_pcb' for s in ('left','right')]
    perimeter=json.loads(perimeterpath.read_text())
    for path,sha in perimeter['source_sha256'].items():
        p=ROOT/path
        if digest(p)!=sha:raise ValueError('Stale perimeter source '+path)
        paths.append(p)
    before={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    print('extract read-only actual board and registrar plans',flush=True)
    plans,_,transform=load_plans();p=plans[side]
    old=json.loads(oldpath.read_text());upper=json.loads(upperpath.read_text())
    gs={k:wkt.loads(v) for k,v in upper['plan_wkt'].items()}
    layers=[(r['z0'],r['z1'],wkt.loads(r['wkt'])) for part in upper['parts'] for r in part['layers']]
    levels=sorted({4.4,6.25}|{z for a,b,g in layers for z in (a,b) if 4.4<=z<=6.25})
    common=None
    for a,b in zip(levels,levels[1:]):
        section=unary_union([g for lo,hi,g in layers if lo<=(a+b)/2<hi])
        common=section if common is None else common.intersection(section)
    regs=plan_registrars(side='right',kind='deep_sea',board=p['board'],lower_floor=p['housing_outline'],
        upper_solid=common,lower_protected=p['all_component_cutouts'],
        upper_protected=unary_union([gs[k] for k in ('body','openings','service','bores','pockets','bosses')]),
        central_exclusion=box(145,28,175,140),split_exclusion=GeometryCollection())
    row=perimeter['sides'][side];wall=wkt.loads(row['wall_wkt']);floor=wkt.loads(row['floor_addition_wkt'])
    masks=[wkt.loads(v) for v in old['masks_wkt']]
    domain=unary_union([wall,floor,wkt.loads(old['new_outline_wkt']),*[r.floor_addition for r in regs.values()]])
    # Pilot/support land geometry is protected against local A/B relief.
    protected=p['mounting_land_geometry']
    old_bounds=wkt.loads(old['outline_wkt']).bounds
    seam=(old_bounds[0]+old_bounds[2])/2
    key_pieces=masks[0].difference(box(-100,-100,seam-.1,300))
    capture_ys=sorted(round(g.centroid.y,8) for g in key_pieces.geoms)
    if len(capture_ys)!=2:raise ValueError('Expected two original capture keys')
    revised_masks=list(retained_key_relief(*masks,domain,seam,capture_ys))
    cutters=[a.difference(b) for a,b in zip(masks,revised_masks)]
    if any(c.intersection(protected).area>1e-8 for c in cutters):raise ValueError('Relief cuts mounting support')
    from tools import generate_kc2_x3_v2_housings as legacy
    supports=legacy._support_plan_union(legacy.legacy_geometry.require_shapely(),p['support_posts']).union(p['rail']).union(p['mounting_land_geometry']).union(p['reset_local_support_geometry'])
    capture_local=unary_union([Point(seam+3,y).buffer(3.) for y in capture_ys])
    cut_support=sum(c.intersection(capture_local).intersection(supports).area for c in cutters)
    if cut_support>1e-8:raise ValueError('Receiver relief cuts capture-local support')
    for r in regs.values():
        if not any(m.buffer(1e-7).covers(r.floor_addition) for m in revised_masks):raise ValueError('Registrar split')
    print('import baseline bodies',flush=True)
    baselines=sorted(cq.importers.importStep(str(baselinepath)).solids().vals(),key=lambda s:s.Center().x)
    if len(baselines)!=2:raise ValueError('Expected two lower parts')
    additions=[prism(g,a,b) for a,b,g in wall_bands(wall)]+[prism(floor_relief(floor),-2.2,-1)]
    for r in regs.values():additions.extend([prism(r.wall,-1,5),prism(r.floor_addition,-2.2,-1)])
    features=place_feature_solids('right',wkt.loads(old['clearance_wkt']))
    additions += features
    solids=[];partrows=[]
    for i,(base,mask,cutter) in enumerate(zip(baselines,revised_masks,cutters)):
        print('local relief and addition part',i,flush=True)
        revised=base if cutter.is_empty else base.cut(*prism(cutter,-2.3,5.1).Solids()).clean()
        if not revised.isValid() or len(revised.Solids())!=1:raise ValueError('Relief disconnects part')
        masktool=prism(mask,-2.3,5.1)
        clipped=[piece for addition in additions for piece in addition.intersect(masktool).Solids()]
        solid=compose_lower(revised,clipped)
        access=None
        if magnetic:
            opened=open_entries(solid,'right');removed=solid.cut(opened)
            access=dict(removed_mm3=removed.Volume(),old_material_removed_mm3=removed.intersect(base).Volume(),
                off_access_removed_mm3=removed.cut(*entry_tools('right')).Volume(),
                entry_obstruction_mm3=sum(opened.intersect(t).Volume() for t in entry_tools('right')))
            if max(access[k] for k in ('old_material_removed_mm3','off_access_removed_mm3','entry_obstruction_mm3'))>.002:
                raise ValueError('Magnet access preservation/clearance failed')
            solid=opened
        audit=audit_additive(revised,solid,clipped)
        if audit['errors']:raise ValueError(audit)
        solids.append(solid);partrows.append(dict(index=i,baseline_volume_mm3=base.Volume(),
            relieved_volume_mm3=revised.Volume(),volume_mm3=solid.Volume(),bounds_mm=bounds(solid),
            cutter_wkt=cutter.wkt,mask_wkt=mask.wkt,preservation=audit,magnetic_access=access))
    gap=solids[0].distance(solids[1])
    if gap<.39999:raise ValueError('Actual A/B gap below .40')
    # Actual side/rear/top free volume excludes ONLY the intended feature.
    free=prism(central_free_envelopes(),-1,1.8).cut(*features)
    blocked_free=sum(s.intersect(free).Volume() for s in solids)
    if blocked_free>.002:raise ValueError('Central flexure free volume obstructed: '+str(blocked_free))
    insertion=prism(male_insertion_envelopes(),-2.2,1.8).cut(*features)
    blocked_insertion=sum(s.intersect(insertion).Volume() for s in solids)
    if blocked_insertion>.002:raise ValueError('Central insertion clearance obstructed: '+str(blocked_insertion))
    outputs={};step=folder/(stem+'.step');cq.exporters.export(cq.Compound.makeCompound(solids),str(step))
    reopened=cq.importers.importStep(str(step)).solids().vals()
    if len(reopened)!=2 or not all(s.isValid() for s in reopened):raise ValueError('STEP roundtrip invalid')
    if abs(sum(s.Volume() for s in reopened)-sum(s.Volume() for s in solids))>.01:raise ValueError('STEP volume error')
    outputs[step.name]=digest(step)
    for i,solid in enumerate(solids):
        stl=folder/('kc2_right_lower_housing_part_'+chr(97+i)+('_magnetic' if magnetic else '')+'.stl')
        cq.exporters.export(solid,str(stl),tolerance=.005,angularTolerance=.08)
        partrows[i]['mesh']=inspect_mesh(stl,solid);outputs[stl.name]=digest(stl)
    if before!={p.relative_to(ROOT).as_posix():digest(p) for p in paths}:raise ValueError('Sources changed during build')
    report=dict(requirements=['CON-ARCH-006'],side=side,magnetic=magnetic,status='generated_pending_independent_review',
        body_count=2,physical_qualified=False,canonical_changed=False,source_sha256=before,outputs=outputs,
        parts=partrows,actual_ab_gap_mm=gap,split_x_mm=seam,capture_ys=capture_ys,
        nominal_capture=dict(head_diameter_mm=4.5,neck_width_mm=2.,throat_width_mm=2.80008,shoulder_mm=.84996),
        capture_local_support_removed_mm2=cut_support,
        central_free_obstruction_mm3=blocked_free,
        central_insertion_obstruction_mm3=blocked_insertion,
        central_wall_relief=dict(envelope_wkt=central_free_envelopes().wkt,z0=-1,z1=1.8,top_clearance_mm=.3),
        transform=transform,volume_mm3=sum(s.Volume() for s in solids),
        registrars={name:{key:getattr(r,key).wkt for key in ('wall','addition','groove','floor_addition')} for name,r in regs.items()})
    (folder/'generation.json').write_text(json.dumps(report,indent=2)+'\n');print(report['status'],flush=True)
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--magnetic',action='store_true');args=p.parse_args();generate(args.magnetic)
