"""CON-ARCH-006 / OPS-ARCH-006 fail-closed publication regressions."""
import copy
import math
import tempfile
import unittest
from unittest.mock import patch
from tools import publish_kc2_registered_housings as p

class ReleaseTests(unittest.TestCase):
    def test_exact_inventory_and_no_feet(self):
        self.assertEqual(len(p.inventory()),35)
        self.assertFalse(any('feet' in x for x in p.report_paths()))
        self.assertEqual(sum(x.endswith(':floor-review') for x in p.report_paths()),4)
    def test_missing_actual_reports_blocks_without_writes(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as root:
            result=p.preflight(root)
            self.assertEqual(result['status'],'blocked')
            self.assertFalse(list(Path(root).iterdir()))
    def test_central_contact_cannot_be_empty_or_missing(self):
        row=dict(status='pass',errors=[],expected_contact_mm3=.01,actual_contact_mm3=.01)
        row.update({k:0 for k in p.CENTRAL_ZERO})
        report=dict(status='pass',errors=[],rows={f'{v}-y{y}':copy.deepcopy(row) for v in ('normal','magnetic') for y in (95,117)})
        p.check_central(report)
        for field in ('expected_contact_mm3','actual_contact_mm3'):
            bad=copy.deepcopy(report);bad['rows']['normal-y95'][field]=0
            with self.assertRaises(ValueError):p.check_central(bad)
        del report['rows']['normal-y95']
        with self.assertRaises(ValueError):p.check_central(report)
    def test_root_floor_capture_and_pose(self):
        row=dict(status='pass',errors=[],side='right',magnetic=False,native_readback=False,gap_mm=.4,
          captures=[dict(y_mm=y,root_width_mm=2,head_diameter_mm=4.5,root_missing_mm3=0,head_missing_mm3=0,actual_throat_mm=2.80008,minimum_shoulder_capture_mm=.84996) for y in (73.25,86.25)],
          motions=[dict(dx=x,dy=y,collision_mm3=1) for x,y in ((1,0),(-1,0),(0,1),(0,-1))],
          floor=[dict(part=i,section_z=-1.6,geometry_type='Polygon',area_mm2=100) for i in (0,1)])
        p.check_lower_split(row,False,False)
        for section,key,value in [('captures','root_missing_mm3',1),('motions','dx',12),('floor','geometry_type','MultiPolygon')]:
            bad=copy.deepcopy(row);bad[section][0][key]=value
            with self.assertRaises(ValueError):p.check_lower_split(bad,False,False)
    def test_temp_mapping_explicit(self):
        self.assertIn('/evidence/',p.destination('.codex-tmp/perimeter-wall-plans.json'))
        with self.assertRaises(ValueError):p.destination('.codex-tmp/unknown.json')
    def test_mesh_must_be_closed_positive_single_shell_small(self):
        row=dict(watertight=True,winding_consistent=True,shells=1,volume_mm3=1,bounds_mm=[0,0,0,150,100,10])
        p.check_print_mesh(row)
        for key,value in [('shells',2),('watertight',False),('volume_mm3',0),('bounds_mm',[0,0,0,151,100,10])]:
            bad=dict(row);bad[key]=value
            with self.assertRaises(ValueError):p.check_print_mesh(bad)
    def test_stack_full_height_and_profile_inventory(self):
        levels=[2.5,4.1,4.35,4.4,5,5.2]
        checks=[dict(kind=k,z_mm=(a+b)/2,overlap_mm2=0,gap_mm=.3) for a,b in zip(levels,levels[1:]) if (a+b)/2>=4.1 for k in ('mx','choc_v1','deep_sea')]
        row=dict(status='pass',errors=[],side='left',variants={v:dict(levels_mm=levels,checks=copy.deepcopy(checks)) for v in ('normal','magnetic')})
        p.check_stack(row,'left')
        row['variants']['normal']['checks'].pop()
        with self.assertRaises(ValueError):p.check_stack(row,'left')
        row['variants']['normal']['checks']=copy.deepcopy(checks)
        for v in row['variants'].values():v['levels_mm']=[4.1,4.35,4.4,5,5.2]
        with self.assertRaises(ValueError):p.check_stack(row,'left')
    def test_expected_section_levels_not_self_declared(self):
        generation=dict(parts=[dict(layers=[dict(z0=4.1,z1=5),dict(z0=5,z1=6)])])
        p.check_expected_levels(dict(parts=[dict(levels_mm=[4.1,5,6])]),generation)
        with self.assertRaises(ValueError):p.check_expected_levels(dict(parts=[dict(levels_mm=[4.1,6])]),generation)
    def test_actual_profile_missing_ring_or_capture_blocks(self):
        generation=dict(parts=[dict(layers=[dict(z0=4.1,z1=9.3)])]*2)
        levels=[4.1,4.4,7.8,9.3]
        rows=[dict(z0_mm=a,z1_mm=b,errors=[],actual_area_mm2=[10,10],capture_required=7.8<(a+b)/2<9.3,
            one_mm_motion_collision_area_mm2={k:1 for k in ('positive_x','negative_x','positive_y','negative_y')} if 7.8<(a+b)/2<9.3 else {}) for a,b in zip(levels,levels[1:])]
        record=dict(status='pass',errors=[],kind='mx',feature_count=2,clip_ring_nominal_mm=.6,neck_width_mm=2,head_diameter_mm=4,actual_full_projection_gap_mm=.4,sections=rows)
        p.check_profile(record,'mx',generation)
        record['sections'][2]['one_mm_motion_collision_area_mm2']['positive_x']=0
        with self.assertRaises(ValueError):p.check_profile(record,'mx',generation)
    def test_actual_envelope_inventory_and_approach_band(self):
        record=dict(status='pass',errors=[],actual_envelope_verified=True,central_contact_audited_separately=True,jobs={},expanded_envelope_sweep=dict(errors=[],rows=[]))
        for family,side,kind in p.jobs():
            record['jobs'][':'.join((family,side,kind))]=[dict(status='pass',errors=[],stl=name,triangles=20,
                outside_projection_area_sum_mm2=0,outside_triangle_count=0,envelope_allowance_mm=.005) for name in p.job_names(family,side,kind) if name.endswith('.stl')]
        for kind in ('mx','choc_v1','deep_sea'):
            levels=[-2.2,-1,1.5,1.8,2.5,4.1,5,9.3 if kind=='mx' else 6.6]
            record['expanded_envelope_sweep']['rows'] += [dict(kind=kind,z=[a,b],minimum_gap_mm=.3,outside_central_clearance_violation_mm2=0) for a,b in zip(levels,levels[1:])]
        p.check_envelopes(record)
        record['expanded_envelope_sweep']['rows'].pop()
        with self.assertRaises(ValueError):p.check_envelopes(record)
    def test_baseline_bytes_must_not_be_rebound_to_new_output(self):
        from pathlib import Path
        names=list(p.inventory())
        preserved={'hardware/PCB/p'+str(i):p.sha_bytes(b'old') for i in range(16)}
        with tempfile.TemporaryDirectory() as root:
            for name in names+list(preserved):
                file=Path(root)/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(b'old')
            with patch.object(p,'baseline_inventory',return_value=preserved),patch.object(p,'git_blob',return_value=b'old'):
                original,pcb=p.check_baseline_bytes(root)
                self.assertEqual(len(original),35);self.assertEqual(len(pcb),16)
                (Path(root)/names[0]).write_bytes(b'new')
                with self.assertRaises(ValueError):p.check_baseline_bytes(root)
                (Path(root)/names[0]).write_bytes(b'old')
                (Path(root)/next(iter(preserved))).write_bytes(b'changed PCB')
                with self.assertRaises(ValueError):p.check_baseline_bytes(root)
    def test_joined_exact_pose_and_component_pair_inventory(self):
        r=dict(status='pass',errors=[],approach_world_x_mm=[-7.8,0],minimum_clearance_mm=.3,central_actual_audit_required=True,profiles={})
        for kind in ('mx','choc_v1','deep_sea'):
            r['profiles'][kind]=[dict(left=a,right=b,z=[lo,hi],minimum_xy_gap_mm=.3,outside_exception_clearance_violation_mm2=0,central_exception_applied=False) for a,b,lo,hi in p.joined_pairs(kind)]
        p.check_joined(r)
        r['approach_world_x_mm']=[-1,0]
        with self.assertRaises(ValueError):p.check_joined(r)
    def test_actual_reports_must_bind_current_step_and_generation(self):
        wanted={'a.step':'0'*64,'generation.json':'1'*64}
        p.check_required_bindings(dict(source_sha256=wanted),wanted)
        with self.assertRaises(ValueError):p.check_required_bindings(dict(source_sha256={'a.step':'0'*64}),wanted)
        with self.assertRaises(ValueError):p.check_required_bindings(dict(source_sha256={**wanted,'a.step':'2'*64}),wanted)
    def test_floor_identity_continuity_and_mesh(self):
        name=p.job_names('lower','left','normal')[-1]
        mesh=dict(stl=name,sha256='a'*64,watertight=True,winding_consistent=True,components=1,volume_mm3=10,extents_mm=[10,10,1.2],bounds_error_mm=0,volume_error_mm3=0)
        row=dict(status='pass',errors=[],side='left',magnetic=False,native_readback=False,body_count=1,
          parts=[dict(part=0,errors=[],floor_z_mm=[-2.2,-1],floor_thickness_mm=1.2,section_z_mm=-1.6,section_area_mm2=10,section_type='Polygon',enclosed_floor_void_count=0,mesh=mesh)])
        p.check_floor(row,'left','normal',False,{name:'a'*64})
        row['parts'][0]['enclosed_floor_void_count']=1
        with self.assertRaises(ValueError):p.check_floor(row,'left','normal',False,{name:'a'*64})
        row['parts'][0]['enclosed_floor_void_count']=0
        row['parts'][0]['section_type']='MultiPolygon'
        with self.assertRaises(ValueError):p.check_floor(row,'left','normal',False,{name:'a'*64})
    def test_magnetic_access_requires_clear_corridor_and_exact_added_void(self):
        metric={k:0 for k in p.MAGNET_ZERO}
        metric.update(corridor_volume_mm3=math.pi*1.2**2*2.9,back_web_required_mm3=math.pi*1.2**2*.6,entry_expected_removed_mm3=1)
        report=dict(status='pass',errors=[],side='left',native=False,rows={key:copy.deepcopy(metric) for key in ('y103','y111')},
          delta=dict(original_void_mm3=10,actual_void_mm3=12,expected_void_mm3=12,expected_vs_actual_missing_mm3=0,expected_vs_actual_extra_mm3=0,magnetic_extra_material_mm3=0))
        p.check_magnetic_entry(report,'left',False)
        report['rows']['y103']['external_corridor_obstruction_mm3']=.1
        with self.assertRaises(ValueError):p.check_magnetic_entry(report,'left',False)
    def test_lower_v2_requires_conservative_clearance_and_all_variants(self):
        row=dict(body_count=2,**{k:0 for k in p.LOWER_VOID_ZERO})
        report=dict(status='pass',errors=[],schema='lower-void-v2',side='right',native_readback=False,
          variants={v:copy.deepcopy(row) for v in ('normal','magnetic')},
          magnet=dict(original_mm3=10,revised_mm3=12,missing_mm3=0,extra_mm3=0,blocked_mm3=0,entry_obstruction_mm3=0),
          component_envelope=dict(required_clearance_mm=.3,conservative_offset_mm=.301,quad_segs=4,circumscribed_buffer_radius_mm=.301/math.cos(math.pi/16),z_mm=[-.4,2.5],
              raw_classes_wkt={k:'POLYGON EMPTY' for k in p.COMPONENT_CLASSES},required_union_wkt='POLYGON ((0 0,1 0,1 1,0 0))'))
        p.check_lower_void(report,'right',False)
        report['component_envelope']['conservative_offset_mm']=.299
        with self.assertRaises(ValueError):p.check_lower_void(report,'right',False)
    def test_supplemental_combined_area_cannot_hide_diagnostic_failure(self):
        audit=dict(status='pass',errors=[],levels_mm=[4.1,4.4],sections=[dict(z_mm=4.25,missing_mm2=.0001,extra_mm2=.0001,actual_area_mm2=1)],volume_error_mm3=0)
        diagnostic=dict(status='failed',errors=['unfilled area wider than nominal split'],parts=[copy.deepcopy(audit),copy.deepcopy(audit)],independent_features=[])
        bound=dict(z0_mm=4.1,z1_mm=4.4,z_mm=4.25,contract_missing_mm2=0,contract_extra_mm2=0,
            actual_section_missing_mm2=.0001,actual_section_extra_mm2=.0001,combined_missing_bound_mm2=.0001,combined_extra_bound_mm2=.0001,errors=[])
        report=dict(schema='right-upper-mask-contract-v1',status='pass',errors=[],parts=copy.deepcopy(diagnostic['parts']),independent_features=[],
            diagnostic_errors=diagnostic['errors'],diagnostic_sha256='a'*64,mask_contract=[dict(part=i,sections=[copy.deepcopy(bound)]) for i in (0,1)])
        p.check_supplemental(report,diagnostic,'a'*64)
        report['mask_contract'][0]['sections'][0]['combined_missing_bound_mm2']=0
        with self.assertRaises(ValueError):p.check_supplemental(report,diagnostic,'a'*64)
    def test_eligibility_cannot_be_granted_by_pass_flags_or_missing_gates(self):
        records={key:dict(status='pass') for key in p.report_paths()}
        outputs={name:'a'*64 for name in p.inventory()};docs={name:'b'*64 for name in p.PUBLICATION_DOCS}
        old={name:'c'*64 for name in p.inventory()};pcb={str(i):'d'*64 for i in range(16)}
        self.assertFalse(p.publication_eligibility([],records,outputs,docs,old,pcb))
        for key,row in records.items():
            row['source_sha256']={'current.py':'a'*64}
            if key.endswith(':generation'):row['status']='generated_pending_independent_review'
        self.assertTrue(p.publication_eligibility([],records,outputs,docs,old,pcb))
        self.assertFalse(p.publication_eligibility(['stale actual source'],records,outputs,docs,old,pcb))
        records.pop(next(iter(records)))
        self.assertFalse(p.publication_eligibility([],records,outputs,docs,old,pcb))
    def test_preflight_freeze_detects_concurrent_source_change(self):
        binding={'tool.py':dict(sha256=p.sha_bytes(b'original'))}
        self.assertFalse(p.freeze_errors(binding,lambda name:b'original'))
        self.assertTrue(p.freeze_errors(binding,lambda name:b'changed'))
    def test_direct_actual_schema_needs_complete_independent_contract(self):
        part=dict(status='pass',errors=[],levels_mm=[4.1,4.4],volume_error_mm3=0,sections=[dict(z_mm=4.25,missing_mm2=0,extra_mm2=0,actual_area_mm2=10)])
        record=dict(schema='right-upper-direct-mask-contract-v1',status='pass',errors=[],actual_CAD_reimported=True,
          parts=[copy.deepcopy(part),copy.deepcopy(part)],independent_contract=[dict(part=i,levels_mm=[4.1,4.4],sections=[dict(z_mm=4.25,declared_missing_mm2=0,declared_extra_mm2=0,required_area_mm2=10)]) for i in (0,1)])
        p.check_direct_contract(record)
        record['independent_contract'][0]['sections'][0]['required_area_mm2']=9
        with self.assertRaises(ValueError):p.check_direct_contract(record)

if __name__=='__main__':unittest.main()
