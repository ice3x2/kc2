"""CON-ARCH-006 left final magnetic access-only revision; normal unchanged."""
from pathlib import Path
import json,hashlib,shutil
from tools.kc2_magnetic_entry import entry_tools,open_entries
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def generate():
    import cadquery as cq
    from tools.generate_kc2_magnetic_housings import inspect_mesh,bounds
    folder=ROOT/'.codex-tmp/registered-housing-fit/lower/left-magnetic'
    cached=ROOT/'.codex-tmp/registered-housing-fit/lower-development/left-magnetic-before-access'
    cached.mkdir(parents=True,exist_ok=True);stem='kc2_left_lower_housing_magnetic'
    for name in ('generation.json',stem+'.step'):
        if not (cached/name).exists():shutil.copyfile(folder/name,cached/name)
    rp=cached/'generation.json';old=json.loads(rp.read_text());source=cached/(stem+'.step')
    if old['status']!='generated_pending_independent_review' or old.get('ordinary_wall_top_mm')!=4.1 or digest(source)!=old['outputs'][source.name]:
        raise ValueError('Wrong pre-access source')
    baseline=ROOT/'hardware/MODELS'/(stem+'.step')
    paths=[Path(__file__),ROOT/'tools/kc2_magnetic_entry.py',ROOT/'tools/test_kc2_magnetic_entry.py',
        ROOT/'tools/generate_kc2_magnetic_housings.py',rp,source,baseline]
    for path,sha in old['source_sha256'].items():
        p=ROOT/path
        if digest(p)!=sha:raise ValueError('Stale pre-access source '+path)
        paths.append(p)
    frozen={p.relative_to(ROOT).as_posix():digest(p) for p in paths}
    print('import pre-access/current canonical magnetic',flush=True)
    before=cq.importers.importStep(str(source)).val();original=cq.importers.importStep(str(baseline)).val()
    print('open ONLY new-wall coaxial access',flush=True);after=open_entries(before,'left');removed=before.cut(after)
    tools=entry_tools('left')
    audit=dict(removed_mm3=removed.Volume(),added_mm3=after.cut(before).Volume(),old_material_removed_mm3=removed.intersect(original).Volume(),
        off_access_removed_mm3=removed.cut(*tools).Volume(),entry_obstruction_mm3=sum(after.intersect(t).Volume() for t in tools))
    if max(audit[k] for k in ('added_mm3','old_material_removed_mm3','off_access_removed_mm3','entry_obstruction_mm3'))>.002:
        raise ValueError('Access delta/old-cover/entry clearance failed: '+str(audit))
    step=folder/(stem+'.step');stl=folder/(stem+'.stl')
    cq.exporters.export(after,str(step));cq.exporters.export(after,str(stl),tolerance=.005,angularTolerance=.08)
    reopened=cq.importers.importStep(str(step)).val()
    if not reopened.isValid() or len(reopened.Solids())!=1 or abs(reopened.Volume()-after.Volume())>.01:raise ValueError('STEP roundtrip')
    if frozen!={p.relative_to(ROOT).as_posix():digest(p) for p in paths}:raise ValueError('Source changed')
    result=dict(requirements=['CON-ARCH-006'],side='left',magnetic=True,status='generated_pending_independent_review',body_count=1,
        ordinary_wall_top_mm=4.1,registrar_top_mm=5.,magnetic_access=audit,
        access_contract=dict(diameter_mm=2.4,center_z_mm=.75,ys_mm=[103.,111.],outside_start_x_mm=-1.6,original_mouth_x_mm=.1,
            original_blind_depth_mm=1.2,inter_wall_airgap_mm=.4,minimum_lower_wall_rim_mm=.55),
        source_sha256=frozen,outputs={p.name:digest(p) for p in (step,stl)},volume_mm3=after.Volume(),bounds_mm=bounds(after),
        mesh=inspect_mesh(stl,after),physical_qualified=False,canonical_changed=False,
        development_provenance=rp.relative_to(ROOT).as_posix())
    (folder/'generation.json').write_text(json.dumps(result,indent=2)+'\n');print(result['status'],flush=True);return result
if __name__=='__main__':generate()
