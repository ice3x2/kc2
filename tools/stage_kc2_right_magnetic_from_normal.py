"""CON-ARCH-006 optional right pockets as a bounded normal-source delta.

No original generator edits, no re-fusing common walls; independent void/native
and capture/floor reviews remain mandatory. Writes staged magnetic identity only.
"""
import json,hashlib,copy
from pathlib import Path
from tools.review_kc2_local_covers import cut_union,prism
from tools.kc2_magnetic_entry import entry_tools
ROOT=Path(__file__).resolve().parents[1]

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def volume_intersection(a,b):return sum(s.intersect(t).Volume() for s in a.Solids() for t in b.Solids())
def carve(normal,oldnormal,oldmag,blind,entries):
    if not blind:raise ValueError('Missing original blind tools')
    if any(cut_union(b,oldnormal).Volume()>.002 or volume_intersection(oldmag,b)>.002 for b in blind):
        raise ValueError('Original pocket contract mismatch')
    if any(volume_intersection(oldmag,e)>.002 for e in entries):raise ValueError('Entry cuts original magnetic material')
    result=normal
    for tool in [*blind,*entries]:result=cut_union(result,tool)
    result=result.clean()
    if not result.isValid() or len(result.Solids())!=len(normal.Solids()):raise ValueError('Invalid/disconnected variant')
    removed=cut_union(normal,result);unexpected=removed
    for tool in [*blind,*entries]:unexpected=cut_union(unexpected,tool)
    row=dict(removed_mm3=removed.Volume(),added_mm3=cut_union(result,normal).Volume(),
        off_pocket_or_entry_removed_mm3=unexpected.Volume(),
        original_magnetic_material_removed_mm3=volume_intersection(removed,oldmag),
        blind_obstruction_mm3=sum(volume_intersection(result,b) for b in blind),
        entry_obstruction_mm3=sum(volume_intersection(result,e) for e in entries))
    row['errors']=[k for k,v in row.items() if k!='removed_mm3' and v>.002]
    if row['errors']:raise ValueError(row)
    return result,row

def generate():
    import cadquery as cq
    from shapely import wkt
    from tools.generate_kc2_magnetic_housings import inspect_mesh,bounds
    stage=ROOT/'.codex-tmp/registered-housing-fit/lower';sourcefolder=stage/'right-normal';folder=stage/'right-magnetic'
    folder.mkdir(parents=True,exist_ok=True)
    rp=sourcefolder/'generation.json';source=sourcefolder/'kc2_right_lower_housing.step'
    record=json.loads(rp.read_text())
    if record.get('status')!='generated_pending_independent_review' or record.get('body_count')!=2 or record.get('magnetic') is not False:
        raise ValueError('Normal source identity/status')
    if digest(source)!=record['outputs'][source.name]:raise ValueError('Changed normal STEP')
    oldnormal=ROOT/'hardware/MODELS/kc2_right_lower_housing.step';oldmag=ROOT/'hardware/MODELS/kc2_right_lower_housing_magnetic.step'
    paths=[Path(__file__),ROOT/'tools/test_stage_kc2_right_magnetic_from_normal.py',ROOT/'tools/review_kc2_local_covers.py',
        ROOT/'tools/kc2_magnetic_entry.py',ROOT/'tools/test_kc2_magnetic_entry.py',ROOT/'tools/generate_kc2_magnetic_housings.py',rp,source,oldnormal,oldmag]
    for path,sha in record['source_sha256'].items():
        p=ROOT/path
        if digest(p)!=sha:raise ValueError('Stale normal source '+path)
        paths.append(p)
    frozen={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    print('import final normal and canonical pocket baselines',flush=True)
    normal=cq.importers.importStep(str(source)).val();originalnormal=cq.importers.importStep(str(oldnormal)).val();originalmag=cq.importers.importStep(str(oldmag)).val()
    blind=[cq.Solid.makeCylinder(1.2,1.2,cq.Vector(149.3,y,.75),cq.Vector(-1,0,0)) for y in (103.,111.)]
    print('bounded blind-pocket and new-wall access cuts',flush=True)
    actual,audit=carve(normal,originalnormal,originalmag,blind,entry_tools('right'))
    lost=cut_union(originalmag,actual)
    for part in record['parts']:
        cutter=wkt.loads(part['cutter_wkt'])
        if not cutter.is_empty:lost=cut_union(lost,prism(cutter,-2.3,5.1))
    audit['canonical_magnetic_removed_outside_relief_mm3']=lost.Volume()
    if lost.Volume()>.002:raise ValueError('Lost original magnetic material beyond approved receiver relief')
    solids=sorted(actual.Solids(),key=lambda s:s.Center().x)
    original_parts=sorted(originalmag.Solids(),key=lambda s:s.Center().x)
    if len(solids)!=2:raise ValueError('Wrong right body count')
    output=copy.deepcopy(record);output.update(magnetic=True,source_sha256=frozen,outputs={},magnetic_access=audit,
        derived_from_normal=rp.relative_to(ROOT).as_posix(),volume_mm3=actual.Volume(),
        access_contract=dict(diameter_mm=2.4,center_z_mm=.75,ys_mm=[103.,111.],outside_start_x_mm=151.,original_mouth_x_mm=149.3,original_blind_depth_mm=1.2))
    stem='kc2_right_lower_housing_magnetic';step=folder/(stem+'.step')
    cq.exporters.export(cq.Compound.makeCompound(solids),str(step));output['outputs'][step.name]=digest(step)
    reopened=cq.importers.importStep(str(step)).val()
    if not reopened.isValid() or len(reopened.Solids())!=2 or abs(reopened.Volume()-actual.Volume())>.01:raise ValueError('STEP roundtrip failed')
    for i,solid in enumerate(solids):
        stl=folder/('kc2_right_lower_housing_part_'+chr(97+i)+'_magnetic.stl')
        cq.exporters.export(solid,str(stl),tolerance=.005,angularTolerance=.08)
        output['parts'][i].update(volume_mm3=solid.Volume(),bounds_mm=bounds(solid),mesh=inspect_mesh(stl,solid),
            magnetic_access_scope='Whole-pair audit is generation.magnetic_access; no per-part rerun claim')
        output['parts'][i].pop('magnetic_access',None)
        output['parts'][i]['normal_generation_part_provenance']=dict(
            baseline_volume_mm3=output['parts'][i].pop('baseline_volume_mm3'),
            relieved_volume_mm3=output['parts'][i].pop('relieved_volume_mm3'),
            preservation=output['parts'][i].pop('preservation'))
        output['parts'][i]['canonical_magnetic_baseline_volume_mm3']=original_parts[i].Volume()
        output['outputs'][stl.name]=digest(stl)
    output['actual_ab_gap_mm']=solids[0].distance(solids[1])
    if output['actual_ab_gap_mm']<.39999:raise ValueError('A/B clearance lost')
    if frozen!={p.relative_to(ROOT).as_posix():digest(p) for p in paths}:raise ValueError('Source changed during generation')
    (folder/'generation.json').write_text(json.dumps(output,indent=2)+'\n');print(output['status'],flush=True)
    return output

if __name__=='__main__':generate()
