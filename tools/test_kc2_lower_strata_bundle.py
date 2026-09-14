"""CON-ARCH-006 complete normal strata plus actual magnetic subset, no waiver."""
import copy
import math
import unittest
from shapely.geometry import box


class StrataBundleTests(unittest.TestCase):
    def subset_fixture(self):
        from tools.kc2_lower_strata_bundle import validate_subset,STAGE,stem
        from tools.kc2_magnetic_subset import EXPECTED_REMOVAL_MM3
        metrics=dict(body_count=2,non_destructive_cut=True,removed_total_mm3=EXPECTED_REMOVAL_MM3,
                     expected_removed_mm3=EXPECTED_REMOVAL_MM3,parts=[])
        generations={v:{'parts':[]} for v in ('normal','magnetic')};required={};variants={}
        for i in range(2):
            bb=[i*20,0,-2.2,i*20+10,10,5];n=100*(i+1);m=n-(EXPECTED_REMOVAL_MM3 if i else 0)
            row=dict(part=i,normal_bounds_mm=bb,magnetic_bounds_mm=bb,normal_volume_mm3=n,magnetic_volume_mm3=m,
                normal_valid_closed_positive=True,magnetic_valid_closed_positive=True,added_result_valid=True,removed_result_valid=True,
                magnetic_minus_normal_mm3=0,magnetic_minus_normal_solids=0,magnetic_minus_normal_faces=0,
                normal_minus_magnetic_mm3=EXPECTED_REMOVAL_MM3 if i else 0,normal_minus_magnetic_solids=4 if i else 0)
            metrics['parts'].append(row)
            for v in generations:generations[v]['parts'].append(dict(index=i,bounds_mm=bb,volume_mm3=n if v=='normal' else m))
        for v in generations:
            gp=STAGE+'/lower/right-'+v+'/generation.json';sp=STAGE+'/lower/right-'+v+'/'+stem('lower','right',v)+'.step'
            required.update({gp:'gen-'+v,sp:'step-'+v})
            variants[v]=dict(generation_path=gp,generation_sha256=required[gp],step_path=sp,step_sha256=required[sp],
                whole_import_topology_covered_by_two_solids=True,whole_import_positive_volume_mm3=sum(p['volume_mm3'] for p in generations[v]['parts']))
        record=dict(schema='right-magnetic-material-subset-v1',status='pass',errors=[],side='right',native_readback=False,
            actual_exported_STEP_reimported=True,kernel_computed_subset_proved=True,component_qualified=False,physical_qualified=False,
            variants=variants,actual_material_comparison=metrics)
        return record,generations,required

    def test_actual_subset_identity_and_nonzero_extra_are_hard_gates(self):
        from tools.kc2_lower_strata_bundle import validate_subset
        record,generations,required=self.subset_fixture()
        validate_subset(record,generations,required)
        for value in (False,1e-15):
            bad=copy.deepcopy(record);bad['actual_material_comparison']['parts'][0]['magnetic_minus_normal_mm3']=value
            with self.assertRaises(ValueError):validate_subset(bad,generations,required)
        bad=copy.deepcopy(record);bad['variants']['magnetic']['step_sha256']='other'
        with self.assertRaises(ValueError):validate_subset(bad,generations,required)
        bad=copy.deepcopy(generations);bad['normal']['parts'][1]['bounds_mm'][0]+=.1
        with self.assertRaises(ValueError):validate_subset(record,bad,required)

    def assembly_fixture(self):
        import json
        from tools import kc2_lower_strata_bundle as b
        subset,generations,_=self.subset_fixture();files={}
        def put(name,record):files[name]=json.dumps(record,sort_keys=True).encode()
        def sha(name):return b.sha_bytes(files[name])
        names=['generator','review_kc2_lower_voids_v2','test_review_kc2_lower_voids_v2',
               'review_kc2_lower_strata','kc2_lower_strata','test_kc2_lower_strata','kc2_component_local_certificate',
               'kc2_required_lower_clearance','review_kc2_magnetic_subset','kc2_magnetic_subset','test_kc2_magnetic_subset',
               'kc2_lower_strata_bundle','test_kc2_lower_strata_bundle','kc2_lower_predicate_bundle','kc2_registered_release_gate']
        for name in names:files['tools/'+name+'.py']=('executed fixture '+name).encode()
        put(b.MOUNTS,{'mounting_centers':[(i*.1,0) for i in range(9)]})
        required={}
        for variant,g in generations.items():
            identity=subset['variants'][variant];gp=identity['generation_path'];sp=identity['step_path']
            files[sp]=('actual '+variant+' step fixture').encode()
            g.update(status='generated_pending_independent_review',side='right',magnetic=variant=='magnetic',body_count=2,
                outputs={sp.rsplit('/',1)[1]:sha(sp)},source_sha256={'tools/generator.py':sha('tools/generator.py')})
            for part in g['parts']:part['mask_wkt']=box(-2,-2,40,20).wkt
            put(gp,g);identity.update(step_sha256=sha(sp),generation_sha256=sha(gp))
            required.update({gp:sha(gp),sp:sha(sp)})
        shared={**required,b.MOUNTS:sha(b.MOUNTS),'tools/generator.py':sha('tools/generator.py')}
        original=dict(schema='lower-void-v2',status='fail',errors=[v+': component_obstruction_mm3' for v in b.VARIANTS],
            side='right',native_readback=False,variants={v:dict(body_count=2,component_obstruction_mm3=46.794929654225015,
                **{k:0 for k in b.RETAINED_ZERO}) for v in b.VARIANTS},
            magnet=dict(original_mm3=10.8573442108,revised_mm3=21.7146884216,missing_mm3=0,extra_mm3=0,blocked_mm3=0,entry_obstruction_mm3=0),
            component_envelope={'fixture':'geometry validator mocked separately'},
            source_sha256={**shared,**{'tools/'+n+'.py':sha('tools/'+n+'.py') for n in names[1:3]}})
        put(b.ORIGINAL,original)
        strata=dict(original_v2_report=b.ORIGINAL,original_v2_sha256=sha(b.ORIGINAL),original_v2_status='fail',
            original_v2_errors=original['errors'],original_component_obstruction_mm3=46.794929654225015,
            source_sha256={**shared,b.ORIGINAL:sha(b.ORIGINAL),**{'tools/'+n+'.py':sha('tools/'+n+'.py') for n in names[3:8]}})
        subset.update(original_v2_report=b.ORIGINAL,original_v2_sha256=sha(b.ORIGINAL),original_v2_status='fail',
            original_v2_errors=original['errors'],original_component_obstruction_mm3={v:46.794929654225015 for v in b.VARIANTS},
            source_sha256={**shared,b.ORIGINAL:sha(b.ORIGINAL),**{'tools/'+n+'.py':sha('tools/'+n+'.py') for n in names[8:11]+['review_kc2_lower_strata','test_kc2_lower_strata']}})
        put(b.STRATA,strata);put(b.SUBSET,subset)
        return files

    def run_assembly_fixture(self,files,read=None):
        from unittest.mock import patch
        from tools import kc2_lower_strata_bundle as b
        # Mock only expensive geometry scope validation: source closure,
        # original failed predicates and actual subset metrics remain real.
        normal=dict(interval_count=11,critical_closure_count=12,minimum_xy_gap_mm=.02,normal_import_volume_mm3=300)
        with patch.object(b,'required_polygons',return_value=[box(i*2,40,i*2+1,41) for i in range(153)]),patch.object(b,'validate_strata',return_value=normal):
            return b.assemble(read or files.__getitem__)

    def test_complete_assemble_closure_and_failure_identity(self):
        import json
        from tools import kc2_lower_strata_bundle as b
        files=self.assembly_fixture();result=self.run_assembly_fixture(files)
        self.assertEqual(result['original_v2_status'],'fail')
        self.assertIsNone(result['component_clearance']['computed_common_volume_mm3'])
        self.assertEqual(result['historical_actual_predicate_measurements']['normal']['component_obstruction_mm3'],46.794929654225015)
        mutations=[(b.ORIGINAL,lambda r:r.update(status='pass')),
                   (b.SUBSET,lambda r:r['variants']['normal'].update(step_sha256='different')),
                   (b.SUBSET,lambda r:r['variants']['magnetic'].update(step_sha256='different')),
                   (b.STRATA,lambda r:r['source_sha256'].pop('tools/kc2_lower_strata.py')),
                   (b.STRATA,lambda r:r.update(original_component_obstruction_mm3=0))]
        for path,change in mutations:
            bad=copy.deepcopy(files);r=json.loads(bad[path]);change(r);bad[path]=json.dumps(r).encode()
            with self.assertRaises(ValueError):self.run_assembly_fixture(bad)
        for variant in b.VARIANTS:
            bad=copy.deepcopy(files);path=b.STAGE+'/lower/right-'+variant+'/generation.json';r=json.loads(bad[path]);r['source_sha256']={};bad[path]=json.dumps(r).encode()
            with self.assertRaises(ValueError):self.run_assembly_fixture(bad)
        # Even if every referencing record is rehashed consistently, an empty
        # generation closure is not a permissible replacement parent.
        bad=copy.deepcopy(files);path=b.STAGE+'/lower/right-normal/generation.json'
        g=json.loads(bad[path]);g['source_sha256']={};bad[path]=json.dumps(g).encode();sha=b.sha_bytes(bad[path])
        original=json.loads(bad[b.ORIGINAL]);original['source_sha256'][path]=sha;bad[b.ORIGINAL]=json.dumps(original).encode()
        for report in (b.STRATA,b.SUBSET):
            row=json.loads(bad[report]);row['source_sha256'][path]=sha
            row['source_sha256'][b.ORIGINAL]=b.sha_bytes(bad[b.ORIGINAL]);row['original_v2_sha256']=b.sha_bytes(bad[b.ORIGINAL])
            if report==b.SUBSET:row['variants']['normal']['generation_sha256']=sha
            bad[report]=json.dumps(row).encode()
        with self.assertRaisesRegex(ValueError,'Missing generation source closure'):self.run_assembly_fixture(bad)

    def test_source_changes_during_complete_assembly_fail_closed(self):
        from tools import kc2_lower_strata_bundle as b
        files=self.assembly_fixture();calls={}
        def changing(name):
            calls[name]=calls.get(name,0)+1
            if name=='tools/generator.py' and calls[name]>=5:return b'changed mid qualification'
            return files[name]
        with self.assertRaises(ValueError):self.run_assembly_fixture(files,changing)

    def fixture(self):
        from tools.kc2_lower_strata_bundle import LEVELS
        points=[(i*.1,0) for i in range(9)];material=box(-2,-2,2,2);required=box(4,0,5,1)
        r=dict(schema='right-lower-normal-strata-v1',status='pass',errors=[],side='right',variant='normal',
            native_readback=False,physical_qualified=False,magnetic_covered=False,required_tool_count=153,
            required_z_mm=[-.4,2.5],minimum_required_xy_gap_mm=.0001,whole_import_valid=True,
            whole_import_topology_covered_by_two_solids=True,whole_import_positive_volume_mm3=1,
            computed_boolean_common_volume_mm3=None,full_v2_boolean_rerun=False,
            levels_mm=list(LEVELS),face_counts={'PLANE':100,'CYLINDER':9},
            cylinders=[dict(part=0,center_mm=p,radius_mm=.55,z_bounds_mm=[-.3,2.5]) for p in points],
            required_tool_union_wkt=required.wkt,intervals=[],critical_closures=[])
        for lo,hi in zip(LEVELS,LEVELS[1:]):
            r['intervals'].append(dict(z_interval_mm=[lo,hi],z_mm=(lo+hi)/2,material_superset_wkt=material.wkt,
                clearance_mm=2,overlap_mm2=0,filled_inner_pilots=[] if hi<=-.3 else [dict(center_mm=p,radius_mm=.55) for p in points]))
        for z in LEVELS:
            methods=['qualified_blind_pilot_cap_outward_aabb']*9 if z==-.3 else []
            r['critical_closures'].append(dict(z_mm=z,material_superset_wkt=material.wkt,clearance_mm=2,overlap_mm2=0,actual_face_methods=methods))
        return r,required,points

    def test_complete_strata_reproduces_geometry_and_margin(self):
        from tools.kc2_lower_strata_bundle import validate_strata
        r,required,points=self.fixture()
        self.assertEqual(validate_strata(r,required,points)['minimum_xy_gap_mm'],2)
        bad=copy.deepcopy(r);bad['intervals'][3]['clearance_mm']=3
        with self.assertRaises(ValueError):validate_strata(bad,required,points)
        bad=copy.deepcopy(r);bad['intervals'][3]['material_superset_wkt']=box(4,0,5,1).wkt
        with self.assertRaises(ValueError):validate_strata(bad,required,points)

    def test_missing_hidden_level_duplicate_closure_or_pilot_rejected(self):
        from tools.kc2_lower_strata_bundle import validate_strata
        r,required,points=self.fixture()
        for key in ('levels_mm','intervals','critical_closures','cylinders'):
            bad=copy.deepcopy(r);bad[key].pop(2)
            with self.assertRaises(ValueError):validate_strata(bad,required,points)
        bad=copy.deepcopy(r);bad['critical_closures'][2]=bad['critical_closures'][1]
        with self.assertRaises(ValueError):validate_strata(bad,required,points)

    def test_no_false_boolean_zero_nonfinite_or_empty_material(self):
        from tools.kc2_lower_strata_bundle import validate_strata
        r,required,points=self.fixture()
        for field,value in [('computed_boolean_common_volume_mm3',0),('whole_import_valid',False),('required_tool_count',True)]:
            bad=copy.deepcopy(r);bad[field]=value
            with self.assertRaises(ValueError):validate_strata(bad,required,points)
        for value in (False,float('nan'),float('inf')):
            bad=copy.deepcopy(r);bad['critical_closures'][0]['clearance_mm']=value
            with self.assertRaises(ValueError):validate_strata(bad,required,points)
        bad=copy.deepcopy(r);bad['intervals'][0]['material_superset_wkt']='POLYGON EMPTY'
        with self.assertRaises(ValueError):validate_strata(bad,required,points)

    def test_closure_cannot_omit_adjacent_material_or_cap_inventory(self):
        from tools.kc2_lower_strata_bundle import validate_strata
        r,required,points=self.fixture();r['critical_closures'][2]['material_superset_wkt']=box(-1,-1,2,1).wkt
        with self.assertRaises(ValueError):validate_strata(r,required,points)
        r,required,points=self.fixture();r['critical_closures'][1]['actual_face_methods']=[]
        with self.assertRaises(ValueError):validate_strata(r,required,points)

    def test_emit_is_immutable_and_revalidates(self):
        import tempfile,hashlib
        from pathlib import Path
        from unittest.mock import patch
        from tools.kc2_lower_strata_bundle import emit,OUTPUT
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';source.write_bytes(b'fixed')
            record={'status':'pass','source_sha256':{'source':hashlib.sha256(b'fixed').hexdigest()}}
            with patch('tools.kc2_lower_strata_bundle.assemble',return_value=record) as check:
                emit(root);self.assertTrue((root/OUTPUT).exists());self.assertEqual(check.call_count,1)
                self.assertEqual(emit(root),record)
                (root/OUTPUT).write_bytes(b'conflicting')
                with self.assertRaises(ValueError):emit(root)
            with patch('tools.kc2_lower_strata_bundle.assemble',return_value=record):
                source.write_bytes(b'changed')
                with self.assertRaises(ValueError):emit(root)
            with patch('tools.kc2_lower_strata_bundle.assemble',side_effect=lambda read:read('../escape')):
                with self.assertRaises(ValueError):emit(root)


if __name__=='__main__':unittest.main()
