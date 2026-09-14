"""CON-ARCH-006 exact kernel material equivalence is not a tolerance waiver."""
import copy,json
import unittest
from tools import kc2_lower_native_transfer as t

class TransferTests(unittest.TestCase):
    def test_right_native_requires_new_and_reused_checker_bindings(self):
        paths=t.native_checker_paths('right')
        for name in ('review_kc2_right_lower_native','test_review_kc2_right_lower_native',
                     'review_kc2_registered_native','test_review_kc2_registered_native','kc2_registered_native'):
            self.assertIn('tools/'+name+'.py',paths)
        self.assertNotIn('tools/review_kc2_right_lower_native.py',t.native_checker_paths('left'))
        with self.assertRaises(ValueError):t.native_checker_paths('other')

    def record(self):
        return dict(status='pass',errors=[],selected_job='lower:right:normal',independent_geometry_verified=True,
          parts=[dict(status='pass',errors=[],missing_mm3=0.0,extra_mm3=0.0) for _ in range(2)],source_sha256={'current.step':'a'*64})
    def test_tiny_nonzero_delta_disallows_transfer(self):
        record=self.record();t.exact_native(record,'lower:right:normal',{'current.step':'a'*64})
        for value in (1e-15,-1e-15,float('nan'),float('inf'),True,False,None):
            bad=copy.deepcopy(record);bad['parts'][0]['missing_mm3']=value
            with self.assertRaises(ValueError):t.exact_native(bad,'lower:right:normal',{'current.step':'a'*64})
    def test_wrong_identity_stale_source_or_missing_part_rejected(self):
        record=self.record()
        for bad in (dict(record,selected_job='lower:left:normal'),dict(record,parts=record['parts'][:1]),dict(record,source_sha256={})):
            with self.assertRaises(ValueError):t.exact_native(bad,'lower:right:normal',{'current.step':'a'*64})
    def test_two_variant_predicates_need_both_exact_native_jobs(self):
        recipe=t.recipe('magnetic-entry','left',None)
        self.assertEqual(recipe['jobs'],['lower:left:normal','lower:left:magnetic'])
        self.assertEqual(len(t.recipe('floor','left','normal')['jobs']),1)
        with self.assertRaises(ValueError):t.recipe('split','left','normal')

    def chain(self,side='left'):
        files={};spec=t.recipe('floor',side,'normal');folder=t.STAGE+'/lower/'+side+'-normal';name=t.stem('lower',side,'normal');label='lower:'+side+':normal'
        count=1 if side=='left' else 2
        stls=[name+'.stl'] if side=='left' else [name+'_part_'+v+'.stl' for v in ('a','b')]
        def put(path,value):files[path]=json.dumps(value).encode();return t.sha_bytes(files[path])
        step=folder+'/'+name+'.step';files[step]=b'step';gp=folder+'/generation.json';np=folder+'/native-generation.json';rp=folder+'/native-review.json'
        gs=put(gp,dict(status='generated_pending_independent_review',side=side,magnetic=False,body_count=count,outputs={name+'.step':t.sha_bytes(files[step]),**{p:'a'*64 for p in stls}},source_sha256={}))
        required={gp:gs,step:t.sha_bytes(files[step])};row=dict(source_step=name+'.step',generation_record='generation.json',source_sha256=required[step],generation_sha256=gs,round_trip_verified=True,expected_body_count=count,source_solids=[{} for _ in range(count)],reopened_solids=[{} for _ in range(count)])
        for key,suffix,hkey in [('f3d','.f3d','f3d_sha256'),('readback_step','.native-readback.step','readback_sha256')]:
            row[key]=name+suffix;files[folder+'/'+row[key]]=suffix.encode();row[hkey]=t.sha_bytes(files[folder+'/'+row[key]]);required[folder+'/'+row[key]]=row[hkey]
        required[np]=put(np,dict(status='pass',phase='complete',selected_job=label,outputs={label:row},source_sha256={}))
        for path in t.native_checker_paths(side):
            files[path]=path.encode();required[path]=t.sha_bytes(files[path])
        put(rp,dict(status='pass',errors=[],selected_job=label,independent_geometry_verified=True,parts=[dict(status='pass',errors=[],missing_mm3=0.,extra_mm3=0.) for _ in range(count)],source_sha256=required))
        mesh=dict(stl=name+'.stl',sha256='a'*64,watertight=True,winding_consistent=True,components=1,volume_mm3=10,extents_mm=[1,2,3],bounds_error_mm=0,volume_error_mm3=0)
        floor=dict(part=0,errors=[],floor_z_mm=[-2.2,-1],floor_thickness_mm=1.2,section_z_mm=-1.6,section_area_mm2=10,section_type='Polygon',enclosed_floor_void_count=0,mesh=mesh)
        floors=[dict(copy.deepcopy(floor),part=i,mesh=dict(mesh,stl=stl)) for i,stl in enumerate(stls)]
        put(spec['source'],dict(status='pass',errors=[],side=side,magnetic=False,native_readback=False,body_count=count,parts=floors,source_sha256={gp:gs,step:required[step]}))
        return spec,files,np,rp

    def test_right_full_chain_rejects_each_new_checker_omission(self):
        spec,files,np,rp=self.chain('right')
        t.inputs(spec,files.__getitem__)
        for path in t.native_checker_paths('right'):
            changed=dict(files);audit=json.loads(changed[rp]);del audit['source_sha256'][path]
            changed[rp]=json.dumps(audit).encode()
            with self.assertRaises(ValueError):t.inputs(spec,changed.__getitem__)

    def test_full_current_chain_and_native_source_metadata(self):
        spec,files,np,rp=self.chain();t.inputs(spec,files.__getitem__)
        original=copy.deepcopy(files)
        for field,value in [('source_step','wrong.step'),('generation_record','wrong.json'),('source_solids',[]),('reopened_solids',[]),('expected_body_count',True)]:
            files=copy.deepcopy(original);n=json.loads(files[np]);n['outputs']['lower:left:normal'][field]=value;files[np]=json.dumps(n).encode()
            audit=json.loads(files[rp]);audit['source_sha256'][np]=t.sha_bytes(files[np]);files[rp]=json.dumps(audit).encode()
            with self.assertRaises(ValueError):t.inputs(spec,files.__getitem__)
        for path in original:
            files=copy.deepcopy(original);files[path]+=b' '
            if path in (spec['source'],rp):continue
            with self.assertRaises((ValueError,KeyError)):t.inputs(spec,files.__getitem__)

    def test_derived_validation_and_explicit_source_semantics(self):
        from tools.publish_kc2_registered_housings import feature_proof
        spec,files,np,rp=self.chain();source,bindings,equalities=t.inputs(spec,files.__getitem__)
        r=dict(schema=t.SCHEMA,status='pass',errors=[],feature='floor',side='left',kind='normal',source_actual_report=spec['source'],source_actual_sha256=bindings[spec['source']],native_equalities=equalities,source_sha256=bindings,native_feature_rerun=False,proof_method='exact_zero_whole_material_difference',kernel_computed_material_identity=True,physical_qualified=False)
        self.assertEqual(feature_proof(r,'floor','left','normal',True,files.__getitem__),(source,False))
        for field,value in [('native_feature_rerun',True),('kernel_computed_material_identity',False),('source_actual_sha256','0'*64),('native_equalities',{}),('physical_qualified',True)]:
            with self.assertRaises(ValueError):feature_proof(dict(r,**{field:value}),'floor','left','normal',True,files.__getitem__)
        with self.assertRaises(ValueError):feature_proof(r,'floor','left','normal',False,files.__getitem__)
        files[spec['source']]+=b' '
        with self.assertRaises(ValueError):feature_proof(r,'floor','left','normal',True,files.__getitem__)

    def test_missing_kernel_reviewer_binding_rejected(self):
        spec,files,np,rp=self.chain();audit=json.loads(files[rp]);audit['source_sha256'].pop('tools/review_kc2_registered_native.py');files[rp]=json.dumps(audit).encode()
        with self.assertRaises(ValueError):t.inputs(spec,files.__getitem__)

    def test_source_generation_bool_count_rejected_even_when_rebound(self):
        spec,files,np,rp=self.chain();gp=np.replace('native-generation','generation');g=json.loads(files[gp]);g['body_count']=True;files[gp]=json.dumps(g).encode();sha=t.sha_bytes(files[gp])
        n=json.loads(files[np]);n['outputs']['lower:left:normal']['generation_sha256']=sha;files[np]=json.dumps(n).encode()
        for path in (rp,spec['source']):
            record=json.loads(files[path]);record['source_sha256'][gp]=sha
            if path==rp:record['source_sha256'][np]=t.sha_bytes(files[np])
            files[path]=json.dumps(record).encode()
        with self.assertRaises(ValueError):t.inputs(spec,files.__getitem__)

    def test_source_actual_semantics_required_before_derived_report(self):
        for field,value in [('parts',[]),('native_readback',True),('side','right')]:
            spec,files,np,rp=self.chain();source=json.loads(files[spec['source']]);source[field]=value;files[spec['source']]=json.dumps(source).encode()
            with self.assertRaises(ValueError):t.inputs(spec,files.__getitem__)

if __name__=='__main__':unittest.main()
