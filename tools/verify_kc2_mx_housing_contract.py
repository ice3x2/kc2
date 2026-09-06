"""CON-ARCH-006 lightweight nominal MX housing binding, not print approval.

No CAD regeneration or canonical writes. Artifact hashes and actual ASCII mesh
topology/bounds/volume are checked; exact switch/screw/print qualification and
Fusion round-trip evidence remain separate gates. The lower CAD verifier still
owns support/component/copper geometry validation.
"""
from __future__ import annotations

import json
import math
import re
import tempfile
from pathlib import Path

from tools.canonical_hash import HASH_POLICY, sha256_file

ROOT=Path(__file__).resolve().parents[1]
LOWER='hardware/case/kc2_housing_manifest.json'
UPPER='hardware/case/kc2_mx_upper_housing_manifest.json'
LOWER_GENERATOR='tools/generate_kc2_x3_v2_housings.py'
UPPER_GENERATOR='tools/generate_kc2_mx_upper_housings.py'
SOCKET={
    'selection':'open_bottom_hat','source':'https://ko.aliexpress.com/item/1005010364025678.html',
    'nominal_total_length_mm':3.,'nominal_barrel_outer_diameter_mm':1.45,
    'nominal_flange_outer_diameter_mm':2.,'nominal_flange_above_pcb_mm':.2,
    'nominal_barrel_below_pcb_mm':1.2,'nominal_socket_to_desk_clearance_mm':2.3,
    'qualified_minimum_desk_clearance_mm':None,'order_ready':False,
    'pending':['socket_tolerances','switch_pin_protrusion','solder_fillet_depth','physical_fit'],
}
CLOSED_FLOOR={
    'top_z_mm':-1.,'bottom_z_mm':-2.2,'thickness_mm':1.2,'continuous_per_part':True,
    'maximum_component_projection_mm':2.9,'nominal_projection_clearance_mm':.6,
    'print_allowance_mm':.3,'residual_clearance_mm':.3,
    'nominal_clearance_by_component_mm':{'choc_socket':1.1,'diode':1.85,'hat_socket':2.3},
    'unknown_projection_qualification':'measure_received_lead_post_and_solder_depth_before_assembly',
    'silicone_foot_diameter_mm':8.,'silicone_thickness_mm':None,'physical_qualification':False,
    'solder_access':'remove_PCB_from_lower_housing',
    'legacy_desk_datum_role':'internal_support_column_ends_and_floor_top',
}
PENDING=['exact_switch_drawing','socket_flange_relief','pin_engagement','printed_clip_fit',
         'long_screw_receiver_torque','full_travel','split_joint_qualification','2N_deflection','Fusion_native_round_trip']
QUALIFICATION_BLOCKERS=[
    'CON-ARCH-006: exact MX switch seating/clip datums, socket flange relief and pin engagement are unqualified',
    'CON-ARCH-006: socket tolerances, switch-pin/solder projection and post-print desk clearance are unqualified',
    'CON-ARCH-006: upper print material, printed clip/joint fit and full-travel head/driver/component clearances are unqualified',
    'CON-ARCH-006: long screw/receiver/driver identity, engagement/tip tolerance, torque and ten-cycle retention evidence are pending',
    'CON-ARCH-006: assembled 2 N / 0.30 mm deflection and full-pattern physical fit evidence are pending',
]


def _paths():
    paths=[LOWER_GENERATOR,UPPER_GENERATOR]
    for side in ('left','right'):
        paths += [f'hardware/kicad/kc2_{side}/kc2_{side}.kicad_pcb',f'hardware/case/kc2_{side}_mx_upper_housing.step']
        paths += [f'hardware/case/kc2_{side}_mx_upper_housing{s}.stl' for s in ([''] if side=='left' else ['_part_a','_part_b'])]
        paths += [f'hardware/case/kc2_{side}_lower_housing{s}.stl' for s in ([''] if side=='left' else ['_part_a','_part_b'])]
    return paths


def _mesh_volume(path):
    triangle=[]
    volume=0.
    with path.open(encoding='ascii') as stream:
        for line in stream:
            fields=line.split()
            if fields[:1]!=['vertex']: continue
            triangle.append(tuple(map(float,fields[1:])))
            if len(triangle)==3:
                a,b,c=triangle
                volume += (a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0]))/6
                triangle=[]
    return abs(volume)


def collect_artifacts(root=ROOT):
    from tools.verify_kc2_x3_v2_housing import inspect_ascii_stl
    result={}
    for relative in _paths():
        path=root/relative
        try:
            record={'sha256':sha256_file(path)}
            if path.suffix=='.stl':
                record.update(inspect_ascii_stl(path), volume_mm3=_mesh_volume(path))
            elif path.suffix=='.step':
                content=path.read_bytes()
                record['step_has_trailing_whitespace']=re.search(rb'[ \t]+(?=\r?\n|\Z)',content) is not None
                record['solid_count']=len(re.findall(rb'\bMANIFOLD_SOLID_BREP\s*\(',content))
            result[relative]=record
        except (OSError,ValueError,RuntimeError,UnicodeError) as exc:
            result[relative]={'error':str(exc)}
    return result


def validate_manifests(lower,upper,*,artifacts,rebinding_signatures=None):
    errors=[]
    def reject_qualification_claims(value,label):
        if isinstance(value,dict):
            for key,item in value.items():
                if key in {'order_ready','print_ready','qualified'} and item is not False:
                    errors.append(f'{label}.{key}: unsupported qualification/readiness claim')
                reject_qualification_claims(item,f'{label}.{key}')
        elif isinstance(value,list):
            for index,item in enumerate(value): reject_qualification_claims(item,f'{label}.{index}')
    def equal(value,expected,label):
        if isinstance(expected,float):
            ok=type(value) in (int,float) and math.isfinite(value) and abs(value-expected)<=1e-7
        else: ok=type(value) is type(expected) and value==expected
        if not ok: errors.append(f'{label}: expected {expected!r}, got {value!r}')
    def fields(record,expected,label):
        if not isinstance(record,dict):
            errors.append(f'{label}: malformed object'); return
        for key,value in expected.items():
            if key not in record: errors.append(f'{label}.{key}: missing')
            else: equal(record[key],value,f'{label}.{key}')
    def binding(record,path,hashkey,label,pathkey=None):
        if pathkey: equal(record.get(pathkey),path,label+'.'+pathkey)
        actual=artifacts.get(path,{})
        digest=record.get(hashkey)
        if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest) or actual.get('sha256')!=digest:
            errors.append(f'{label}.{hashkey}: missing/stale artifact binding: {path}')
        return actual
    try:
        reject_qualification_claims(lower,'lower')
        reject_qualification_claims(upper,'upper')
        fields(lower,{'order_ready':False,'hash_policy':HASH_POLICY,'requirement':'CON-ARCH-006'},'lower')
        fields(lower['mx_receptacle_stack'],SOCKET,'lower.mx_receptacle_stack')
        fields(lower.get('closed_floor'),CLOSED_FLOOR,'lower.closed_floor')
        fields(lower['parameters'],{'pcb_thickness_mm':1.6,'pcb_bottom_z_mm':2.5,'desk_datum_z_mm':-1.},'lower.parameters')
        binding(lower,LOWER_GENERATOR,'generator_sha256','lower')
        fields(upper,{'order_ready':False,'print_ready':False,'hash_policy':HASH_POLICY,'generated_by':UPPER_GENERATOR},'upper')
        binding(upper,UPPER_GENERATOR,'generator_sha256','upper')
        binding(upper,LOWER_GENERATOR,'lower_generator_sha256','upper')
        stack=upper['stack']
        fields(stack,{'requirement':'CON-ARCH-006','order_ready':False,
               'qualification_status':'pending_exact_switch_and_fastener','qualified_long_screw_length_mm':None,
               'receiver_qualification_status':'pending_not_inherited_from_lower_only','print_material':None,
               'print_orientation':'plate_top_on_bed_standoffs_up','pending':PENDING,
               'plate_top_above_pcb_mm':5.2,'clip_thickness_mm':1.5,'aperture_mm':14.,
               'pcb_top_z_mm':4.1,'plate_top_z_mm':9.3,'plate_bottom_z_mm':7.8,'standoff_height_mm':3.7,
               'nominal_under_head_to_receiver_entry_mm':5.3,'nominal_receiver_pilot_depth_mm':2.8,
               'head_pocket_diameter_mm':3.4,'head_pocket_depth_mm':1.5,
               'upper_collar_diameter_mm':4.6,'pcb_landing_diameter_mm':3.,
               'nominal_collar_wall_mm':.6,
               'collar_strength_qualification':'engineering_geometry_only_not_strength_pass'},'upper.stack')
        # Derived Z values must agree with the independently locked base datums.
        fields(stack,{'head_bearing_z_mm':stack['plate_top_z_mm']-1.5,
                      'head_top_z_mm':stack['plate_top_z_mm']-.3,
                      'collar_bottom_z_mm':stack['pcb_top_z_mm']+1.2},'upper.stack')
        equal(set(lower['outputs']),{'left','right'},'lower sides')
        equal(set(upper['outputs']),{'left','right'},'upper sides')
        for side,count,clamps,parts_count in [('left',31,8,1),('right',39,9,2)]:
            lo,up=lower['outputs'][side],upper['outputs'][side]
            fields(lo.get('closed_floor'),CLOSED_FLOOR,f'lower.{side}.closed_floor')
            floorparts=lo.get('closed_floor',{}).get('printable_parts',[])
            if len(floorparts)!=parts_count:
                errors.append(f'lower.{side}.closed_floor: missing printable part evidence')
            for index,record in enumerate(floorparts):
                fields(record,{'geometry_errors':[],'floor_mask_has_holes':False},f'lower.{side}.closed_floor.{index}')
                feet=record.get('silicone_feet',{})
                fields(feet,{'diameter_mm':8.,'bonding_z_mm':-2.2,'flat_bonding_regions':True,
                    'centroid_inside_support_polygon':True},f'lower.{side}.closed_floor.{index}.feet')
                centers=feet.get('centers_xy_mm',[])
                if not isinstance(centers,list) or len(centers)<3:
                    errors.append(f'lower.{side}.closed_floor.{index}: missing bonding regions')
            for index,part in enumerate(lo['printable_parts']):
                suffix='' if side=='left' else f'_part_{chr(97+index)}'
                actual=binding(part,f'hardware/case/kc2_{side}_lower_housing{suffix}.stl','stl_sha256',f'lower.{side}.{index}','stl')
                fields(actual,{'watertight':True,'shell_count':1,'solid_count':1,'desk_contact_z_mm':-2.2},f'lower.{side}.{index}.closed_floor actual STL')
            source=f'hardware/kicad/kc2_{side}/kc2_{side}.kicad_pcb'
            for item,label in [(lo,'lower'),(up,'upper')]:
                binding(item,source,'source_board_sha256',f'{label}.{side}','source_board')
            fields(lo['component_cutouts']['mx_pins_pads_fillets']['selected_receptacle'],SOCKET,f'lower.{side}.socket')
            equal(lo['battery_above_carrier']['source_board_sha256'],lo['source_board_sha256'],f'lower.{side}.battery binding')
            fields(up,{'switch_opening_count':count,'hard_stop_count':clamps,'solid_count':parts_count,
                       'order_ready':False,'print_ready':False,'fits_print_envelope':True,'step_has_trailing_whitespace':False},f'upper.{side}')
            recess=up.get('recess_geometry_checks')
            if not isinstance(recess,list) or len(recess)!=clamps:
                errors.append(f'upper.{side}.recess_geometry_checks: incomplete mounting coverage')
            else:
                equal({row.get('ref') for row in recess},
                      {f'MH{i+1}' for i in range(clamps)},f'upper.{side}.recess refs')
                for row in recess:
                    fields(row,{'head_intersection_mm3':0.,'collar_slice_mm3':math.pi,
                                'outside_landing_mm3':0.,'collar_contained_in_one_part':True},
                           f'upper.{side}.{row.get("ref")}.recess')
            step=binding(up,f'hardware/case/kc2_{side}_mx_upper_housing.step','step_sha256',f'upper.{side}','step')
            fields(step,{'solid_count':parts_count,'step_has_trailing_whitespace':False},f'actual STEP {side}')
            parts=up['printable_parts']
            if not isinstance(parts,list) or len(parts)!=parts_count: raise ValueError(f'{side}: incorrect printable part count/type')
            for index,part in enumerate(parts):
                suffix='' if side=='left' else f'_part_{chr(97+index)}'
                actual=binding(part,f'hardware/case/kc2_{side}_mx_upper_housing{suffix}.stl','stl_sha256',f'upper.{side}.{index}','stl')
                for obj,label in [(part,'manifest'),(actual,'actual mesh')]:
                    fields(obj,{'watertight':True,'shell_count':1,'solid_count':1},f'{side}.{index}.{label}')
                for field,length in [('bounds_xyz_mm',6),('size_xyz_mm',3)]:
                    values=part[field]
                    if not isinstance(values,list) or len(values)!=length or any(type(v) not in (float,int) or not math.isfinite(v) for v in values):
                        raise ValueError(f'{side}.{index}: malformed {field}')
                    actual_values=actual.get(field,[])
                    if (not isinstance(actual_values,list) or len(actual_values)!=length
                            or any(type(v) not in (int,float) or not math.isfinite(v) for v in actual_values)
                            or any(abs(a-b)>.001 for a,b in zip(values,actual_values))):
                        errors.append(f'{side}.{index}: {field} disagrees with actual mesh')
                bounds,size=part['bounds_xyz_mm'],part['size_xyz_mm']
                if any(not 0<v<=150 for v in size) or any(abs(bounds[i+3]-bounds[i]-size[i])>.001 for i in range(3)):
                    errors.append(f'{side}.{index}: invalid print bounds')
                equal(bounds[2],4.1,f'{side}.{index}.hard-stop bottom')
                equal(bounds[5],9.3,f'{side}.{index}.plate top')
                volume=part['volume_mm3']
                actual_volume=actual.get('volume_mm3')
                if (type(volume) not in (int,float) or not math.isfinite(volume) or volume<=0
                        or type(actual_volume) not in (int,float) or not math.isfinite(actual_volume) or actual_volume<=0
                        or abs(volume-actual_volume)>max(.01,volume*.001)):
                    errors.append(f'{side}.{index}: invalid/stale volume')
            if side=='left': equal(up['split_joint'],None,'left split')
            else:
                joint=up['split_joint']
                fields(joint,{'capture_count':2,'clamp_count_by_part':[4,5],'neck_width_mm':2.,'head_diameter_mm':4.5,'clearance_mm':.2},'right split')
                points=joint['capture_points']
                if len(points)!=2 or any(len(p)!=3 or any(type(v) not in (int,float) or not math.isfinite(v) for v in p) for p in points):
                    raise ValueError('right split capture points malformed')
                motion=joint['one_mm_in_plane_motion_collision_area_mm2']
                equal(set(motion),{'positive_x','negative_x','positive_y','negative_y'},'right split motions')
                if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in motion.values()):
                    errors.append('right split: unretained in-plane motion')
        if 'source_rebinding_evidence' in lower:
            rebind=lower['source_rebinding_evidence']
            equal(set(rebind),{'left','right'},'rebind sides')
            for side in ('left','right'):
                record=rebind[side]
                for key in ('old_source_sha256','new_source_sha256','identical_full_extraction_sha256'):
                    if not isinstance(record.get(key),str) or not re.fullmatch('[0-9a-f]{64}',record[key]):
                        errors.append(f'rebind.{side}.{key}: malformed SHA')
                equal(record['new_source_sha256'],lower['outputs'][side]['source_board_sha256'],f'rebind.{side}.new source')
                if not rebinding_signatures or record['identical_full_extraction_sha256']!=rebinding_signatures.get(side):
                    errors.append(f'rebind.{side}: missing/stale independently recomputed extraction SHA')
    except (KeyError,TypeError,ValueError,AttributeError,IndexError,OverflowError) as exc:
        errors.append(f'malformed MX housing contract: {exc}')
    # Typed packaging summary. This does not replace the independently imported
    # full-STEP floor proof in kc2_housing_clearance.json.
    floor_summary=dict(digital_valid=not errors,errors=list(errors),
        floor_thickness_mm=1.2,floor_top_z_mm=-1.,floor_bottom_z_mm=-2.2,
        bonding_pad_diameter_mm=8.,bonding_pad_count=0,printable_part_count=0,
        evidence_scope='validated manifest contract and hash-bound actual STL; full STEP proof is separate',
        physical_qualification_complete=False)
    try:
        floorparts=[p for s in ('left','right') for p in lower['outputs'][s]['closed_floor']['printable_parts']]
        floor_summary['printable_part_count']=len(floorparts)
        floor_summary['bonding_pad_count']=sum(len(p['silicone_feet']['centers_xy_mm']) for p in floorparts)
    except (KeyError,TypeError,AttributeError):
        floor_summary['digital_valid']=False
        floor_summary['errors'].append('closed_floor typed summary unavailable')
    return {'requirement':'CON-ARCH-006','digital_valid':not errors,'errors':errors,
            'closed_floor':floor_summary,
            'qualification_blockers':list(QUALIFICATION_BLOCKERS),'native_archive_blockers':[],
            'order_ready':False,'print_ready':False}


def analyze_contract(root=ROOT):
    root=Path(root).resolve()
    try:
        lower=json.loads((root/LOWER).read_text(encoding='utf-8'))
        upper=json.loads((root/UPPER).read_text(encoding='utf-8'))
        signatures=None
        if isinstance(lower,dict) and 'source_rebinding_evidence' in lower:
            from tools.generate_kc2_mx_upper_housings import snapshot_board_geometry
            from tools.rebind_kc2_housing_source import geometry_signature
            if root!=ROOT: raise ValueError('fresh PCB extraction currently requires canonical repository root')
            with tempfile.TemporaryDirectory(prefix='mx-contract-',dir=root/'.codex-tmp') as directory:
                data,_=snapshot_board_geometry(Path(directory),Path('C:/Program Files/KiCad/10.0/bin/python.exe'))
            signatures={side:geometry_signature(value) for side,value in data['boards'].items()}
        report=validate_manifests(lower,upper,artifacts=collect_artifacts(root),rebinding_signatures=signatures)
    except Exception as exc:
        report={'requirement':'CON-ARCH-006','digital_valid':False,'errors':[f'MX housing evidence unavailable: {exc}'],
                'qualification_blockers':list(QUALIFICATION_BLOCKERS),'native_archive_blockers':[],
                'order_ready':False,'print_ready':False}
    try:
        from tools.verify_kc2_housing_f3d import verify_f3d_outputs
        report['native_archive_blockers']=verify_f3d_outputs(root)
    except Exception as exc:
        report['native_archive_blockers']=[f'Fusion native round-trip evidence malformed: {exc}']
    return report


def main():
    report=analyze_contract()
    print(json.dumps(report,indent=2))
    return 1 if report['errors'] else (2 if report['qualification_blockers'] or report['native_archive_blockers'] else 0)


if __name__=='__main__': raise SystemExit(main())
