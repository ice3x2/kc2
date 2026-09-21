"""CON-ARCH-006 upper inner-void closure and coplanar print-face correction.

The current canonical gap-fixed CAD is an immutable input.  This revision
closes verified nonfunctional voids and removes only material below the common
upper print datum; it never edits the ordered PCB or lower housings.
"""
from pathlib import Path
import argparse
import hashlib
import json

import trimesh
from shapely import wkt, set_precision
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from tools.kc2_pcb_seating import horizontal_section

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.codex-tmp/upper-finish-20260921'
KINDS=('mx','choc_v1','deep_sea')


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))
def write(path,data):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')


def component_at(geometry,point):
    parts=list(getattr(geometry,'geoms',[geometry]))
    covered=[part for part in parts if part.buffer(1e-7).covers(point)]
    if len(covered)!=1:raise ValueError('Expected one mounting component at '+point.wkt)
    return covered[0]


def _shells(section):
    return unary_union([Polygon(p.exterior) for p in getattr(section,'geoms',[section])
                        if not p.is_empty])


def enclosed_nonfunctional_voids(section,protected):
    """Return genuine holes inside the part silhouette, minus functional space."""
    raw=_shells(section).difference(section).difference(protected)
    kept=[]
    for p in getattr(raw,'geoms',[raw]):
        if p.area>.02 and max(p.bounds[2]-p.bounds[0],p.bounds[3]-p.bounds[1])<6:
            kept.append(p)
    return unary_union(kept) if kept else Polygon()


def clip_to_print_datum(body,datum=4.4):
    """Remove only material below ``datum`` and retain the complete upper solid."""
    import cadquery as cq
    bb=body.BoundingBox();margin=2.;cut_z0=bb.zmin-margin;cut_height=datum-cut_z0
    cutter=(cq.Workplane('XY').box(bb.xlen+2*margin,bb.ylen+2*margin,cut_height,
                                  centered=(True,True,False))
            .translate(((bb.xmin+bb.xmax)/2,(bb.ymin+bb.ymax)/2,cut_z0)).val())
    clipped=body.cut(cutter).clean();removed=body.Volume()-clipped.Volume()
    proof=dict(datum_mm=datum,source_min_z_mm=bb.zmin,
               result_min_z_mm=clipped.BoundingBox().zmin,
               removed_below_datum_mm3=removed,
               removed_at_or_above_datum_mm3=0.,added_material_mm3=0.,
               operation='bounded half-space subtraction; independent above-datum section comparison required')
    if (not clipped.isValid() or len(clipped.Solids())!=1 or
            abs(proof['result_min_z_mm']-datum)>1e-6 or
            proof['removed_below_datum_mm3']<=.01 or
            proof['added_material_mm3']>.002):
        raise ValueError('Unsafe print-datum clip '+json.dumps(proof))
    return clipped,proof


def names(side,kind):
    stem=f'kc2_{side}_{kind}_upper_housing'
    stls=[stem+'.stl'] if side=='left' else [stem+'_part_a.stl',stem+'_part_b.stl']
    return stem,stls


def make_plan():
    manifest=read('hardware/MODELS/kc2_wall_gap_fix_manifest.json')
    if manifest['status']!='digital_review_pass':raise ValueError('Gap-fix baseline is not reviewed')
    for group in ('outputs','preserved_pcb_gerber_sha256'):
        for name,sha in manifest[group].items():
            if digest(ROOT/name)!=sha:raise ValueError('Changed baseline '+name)
    oldplan=read('docs/reports/wall-gap-fix-20260921/evidence/plan.json')
    sources={'hardware/MODELS/kc2_wall_gap_fix_manifest.json':digest(ROOT/'hardware/MODELS/kc2_wall_gap_fix_manifest.json'),
             'docs/reports/wall-gap-fix-20260921/evidence/plan.json':digest(ROOT/'docs/reports/wall-gap-fix-20260921/evidence/plan.json')}
    jobs={}
    for side in ('left','right'):
        for kind in KINDS:
            label=f'{side}:{kind}';stem,stls=names(side,kind)
            profile_path=f'docs/reports/solid-filled-plates-20260913/{side}-{kind}.json'
            layers_path=f'docs/reports/registered-housing-fit-20260913/evidence/upper/{side}-{kind}/generation.json'
            profile=read(profile_path);layerdata=read(layers_path);gapjob=oldplan['jobs'][label]
            sources[profile_path]=digest(ROOT/profile_path);sources[layers_path]=digest(ROOT/layers_path)
            for name in [stem+'.step',stem+'.f3d',*stls]:
                rel='hardware/MODELS/'+name;sources[rel]=digest(ROOT/rel)
            for name in stls:
                rel='hardware/MODELS/STL_FROM_FUSION_20260921/'+name;sources[rel]=digest(ROOT/rel)
            meshes=[trimesh.load_mesh(ROOT/'hardware/MODELS'/name,force='mesh') for name in stls]
            pw=profile['plan_wkt'];lands=wkt.loads(pw['lands'])
            parts=[]
            for i,(mesh,oldpart) in enumerate(zip(meshes,gapjob['parts'])):
                protected=wkt.loads(oldpart['protected_wkt']);patches=[]
                for layer in layerdata['parts'][i]['layers']:
                    if layer['z1']<=4.4:continue
                    z=(layer['z0']+layer['z1'])/2
                    stock=horizontal_section(mesh,z)
                    required=enclosed_nonfunctional_voids(stock,protected)
                    if required.is_empty:continue
                    patch=set_precision(required.buffer(.02,join_style=2).intersection(_shells(stock)).difference(protected),.0001)
                    if patch.is_empty:continue
                    patches.append(dict(type='inner_void',z0=layer['z0'],z1=layer['z1'],wkt=patch.wkt,
                        required_wkt=required.wkt,required_area_mm2=required.area,
                        added_plan_area_mm2=patch.difference(stock).area))
                if not 4.099<=mesh.bounds[0,2]<=4.101:
                    raise ValueError(label+' unexpected source minimum Z')
                parts.append(dict(patches=patches,protected_wkt=protected.wkt,
                                  print_datum_mm=4.4,source_min_z_mm=float(mesh.bounds[0,2]),
                                  below_datum_section_area_mm2=horizontal_section(mesh,4.15).area,
                                  owned_mounts=[]))
            bottom=[horizontal_section(mesh,4.15) for mesh in meshes]
            for center in profile['mounting_centers']:
                point=Point(*center);land=component_at(lands,point)
                owners=[i for i,s in enumerate(bottom) if s.intersection(land).area>4.9]
                if len(owners)!=1:raise ValueError(label+' mount ownership '+str(center))
                parts[owners[0]]['owned_mounts'].append(center)
            jobs[label]=dict(side=side,kind=kind,stem=stem,stl_names=stls,parts=parts,
                             mount_count=len(profile['mounting_centers']))
    for name in ('tools/kc2_upper_finish.py','tools/test_kc2_upper_finish.py','tools/kc2_pcb_seating.py'):
        sources[name]=digest(ROOT/name)
    result=dict(requirements=['CON-ARCH-006','OPS-ARCH-006'],baseline_manifest='hardware/MODELS/kc2_wall_gap_fix_manifest.json',
        jobs=jobs,source_sha256=sources,physical_qualified=False,
        method='Close only nonfunctional holes; remove all source material below Z4.40 so every upper has one coplanar print datum; preserve bores and reinforce only above datum')
    write(STAGE/'plan.json',result);return result


def build(label):
    import cadquery as cq
    from tools.kc2_central_flexure import prism
    from tools.kc2_step_whitespace import normalize
    from tools.stage_kc2_registered_lower import audit_additive
    plan=json.loads((STAGE/'plan.json').read_text())
    for name,sha in plan['source_sha256'].items():
        if digest(ROOT/name)!=sha:raise ValueError('Changed plan source '+name)
    job=plan['jobs'][label];folder=STAGE/label.replace(':','-');folder.mkdir(parents=True,exist_ok=True)
    base=sorted(cq.importers.importStep(str(ROOT/'hardware/MODELS'/(job['stem']+'.step'))).solids().vals(),key=lambda s:s.Center().x)
    if len(base)!=len(job['parts']):raise ValueError('Wrong source body count')
    finals=[];proofs=[]
    for i,(body,part) in enumerate(zip(base,job['parts'])):
        clipped,clipproof=clip_to_print_datum(body,part['print_datum_mm'])
        specs=part['patches']
        additions=[prism(wkt.loads(p['wkt']),p['z0'],p['z1']) for p in specs]
        solids=[s for a in additions for s in a.Solids()]
        print('fuse',label,i,'additions',len(solids),flush=True)
        final=clipped.fuse(*solids).clean() if solids else clipped
        proof=(audit_additive(clipped,final,additions) if additions else
               dict(errors=[],removed_baseline_mm3=0.,unplanned_added_mm3=0.))
        proof['missing_addition_mm3']=sum(abs(a.cut(final).Volume()) for a in additions)
        proof.update(base_volume_mm3=body.Volume(),clipped_volume_mm3=clipped.Volume(),
                     final_volume_mm3=final.Volume(),addition_count=len(additions),clip=clipproof)
        if proof['errors'] or proof['missing_addition_mm3']>.002:raise ValueError(proof)
        finals.append(final);proofs.append(proof)
    path=folder/(job['stem']+'.step')
    cq.exporters.export(cq.Compound.makeCompound(finals),str(path));path.write_bytes(normalize(path.read_bytes())[0])
    reopened=cq.importers.importStep(str(path)).val()
    if not reopened.isValid() or len(reopened.Solids())!=len(finals) or abs(reopened.Volume()-sum(s.Volume() for s in finals))>.02:
        raise ValueError('STEP round trip failed')
    result=dict(status='cad_generated',label=label,parts=proofs,step=path.name,step_sha256=digest(path),
                plan_sha256=digest(STAGE/'plan.json'),source_sha256=plan['source_sha256'])
    write(folder/'generation.json',result);print('done',label,flush=True);return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('job');arg=parser.parse_args().job
    make_plan() if arg=='plan' else build(arg)
