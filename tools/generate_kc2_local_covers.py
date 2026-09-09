"""CON-ARCH-006 / OPS-ARCH-006 additive local covers on immutable r5 CAD."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import cadquery as cq
from shapely.ops import unary_union
from tools import generate_kc2_x3_v2_housings as base
from tools import generate_kc2_magnetic_housings as magnetic
from tools import kc2_local_covers as covers

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/'.codex-tmp/local-cover-build'
BASELINE='cc854a3e0e0f25ab3d63e2916cb4b99a487b6536'


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def baseline_step(name):
    path=STAGE/'baseline'/name
    path.parent.mkdir(parents=True,exist_ok=True)
    data=subprocess.check_output(['git','show',BASELINE+':hardware/MODELS/'+name],cwd=ROOT)
    path.write_bytes(data)
    return path


def attach_lower_cover(before,wall,floor_patch):
    additions=[]
    for shape,height,z in [(wall,3.5,-1.),(floor_patch,1.2,-2.2)]:
        if not shape.is_empty:
            additions.extend(base._extrude_geometry(cq,shape,height,z).val().Solids())
    return before.fuse(*additions).clean() if additions else before


def write_json(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf8')


def export_step(shape,path):
    cq.exporters.export(shape,str(path))
    base.normalize_exported_text(path)


def generate_lower(side):
    STAGE.mkdir(parents=True,exist_ok=True)
    source_paths=[Path(__file__),Path(covers.__file__),Path(base.__file__),Path(magnetic.__file__),
                  ROOT/f'hardware/PCB/kc2_{side}/kc2_{side}.kicad_pcb']
    bound={p.relative_to(ROOT).as_posix():digest(p) for p in source_paths}
    shp=base.legacy_geometry.require_shapely()
    board=base.run_extractor(Path('C:/Program Files/KiCad/10.0/bin/python.exe'))['boards'][side]
    plan=base.build_plan_geometry(shp,side,board)
    raw=unary_union(list(plan['component_geometries'].values()))
    clearance=plan['all_component_cutouts'].union(raw.buffer(.301/math.cos(math.pi/256),quad_segs=64))
    local=covers.lower_cover_plan(plan['housing_outline'],clearance)
    if local['opening_count']!=(5 if side=='left' else 7):
        raise ValueError('Actual local opening inventory changed; review scope')
    masks=[plan['housing_outline']]
    extended_masks=None
    if side=='right':
        split=base.build_right_split_plan(shp,plan)
        masks=[split['floor_part_a_mask'],split['floor_part_b_mask']]
        x0,y0,x1,y1=local['outer'].bounds
        sx=(plan['housing_outline'].bounds[0]+plan['housing_outline'].bounds[2])/2
        gap=base.RIGHT_SPLIT_CLEARANCE_MM/2
        extended_masks=[shp['box'](x0-1,y0-1,sx-gap,y1+1).union(split['key_union']),
                        shp['box'](sx+gap,y0-1,x1+1,y1+1).difference(split['slot_union'])]
        patches=covers.clip_patches_to_split(local['floor_patch'],extended_masks)
    else:
        patches=covers.assign_local_patches(list(getattr(local['floor_patch'],'geoms',[local['floor_patch']])),masks)
    walls=[patch.intersection(local['wall']) for patch in patches]
    report={'requirements':['CON-ARCH-006','OPS-ARCH-006'],'status':'generating',
            'baseline_commit':BASELINE,'source_sha256':bound,'physical_qualified':False,
            'opening_count':local['opening_count'],'wall_wkt':local['wall'].wkt,
            'floor_patch_wkt':local['floor_patch'].wkt,'clearance_wkt':clearance.wkt,
            'outline_wkt':plan['housing_outline'].wkt,'new_outline_wkt':local['outer'].wkt,
            'raw_bounds':plan['raw_bounds'],'wall_z_mm':[-1.,2.5],'floor_z_mm':[-2.2,-1.],
            'part_patches_wkt':[patch.wkt for patch in patches], 'outputs':{}}
    report['masks_wkt']=[mask.wkt for mask in (extended_masks or masks)]
    for variant in ['normal','magnetic']:
        suffix='' if variant=='normal' else '_magnetic'
        name=f'kc2_{side}_lower_housing{suffix}.step'
        path=baseline_step(name)
        before=cq.importers.importStep(str(path)).val()
        solids=sorted(before.Solids(),key=lambda s:s.Center().x)
        if len(solids)!=len(masks):raise ValueError('Unexpected baseline split')
        revised=[]
        print(side,variant,'adding only local covers',flush=True)
        for index,solid in enumerate(solids):
            after=attach_lower_cover(solid,walls[index],patches[index])
            if not after.isValid() or len(after.Solids())!=1:raise ValueError('Invalid/disconnected cover')
            revised.append(after)
        target=STAGE/name
        export_step(cq.Compound.makeCompound(revised),target)
        meshes={}
        for i,solid in enumerate(revised):
            part='' if side=='left' else f'_part_{chr(97+i)}'
            stl=STAGE/f'kc2_{side}_lower_housing{part}{suffix}.stl'
            cq.exporters.export(solid,str(stl),tolerance=.005,angularTolerance=.08)
            meshes[stl.name]=magnetic.inspect_mesh(stl,solid)
        report['outputs'][variant]={'step':name,'step_sha256':digest(target),'baseline_step_sha256':digest(path),
            'meshes':meshes,'solids':[{'bounds_mm':magnetic.bounds(s),'volume_mm3':s.Volume()} for s in revised]}
        write_json(STAGE/f'{side}-lower.json',report)
    if bound!={p.relative_to(ROOT).as_posix():digest(p) for p in source_paths}:
        raise ValueError('Source changed during generation')
    report['status']='generated_not_independently_verified'
    write_json(STAGE/f'{side}-lower.json',report)
    print(side,'lower generation complete',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--side',choices=['left','right'],required=True)
    args=parser.parse_args()
    generate_lower(args.side)
