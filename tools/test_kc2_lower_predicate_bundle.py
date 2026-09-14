"""CON-ARCH-006 preserve failed measurements and require complete clearance proof."""
import copy,unittest
from tools import kc2_lower_predicate_bundle as b
from tools import test_kc2_receiver_void_transfer as fixtures

class BundleTests(unittest.TestCase):
    def old(self):
        r=fixtures.ReceiverTransferTests().old();r['status']='fail';r['errors']=['normal: component_obstruction_mm3','magnetic: component_obstruction_mm3']
        for v in b.VARIANTS:r['variants'][v]['component_obstruction_mm3']=46.794929654225015
        return r
    def test_only_specific_failed_predicate_is_replaced_not_waived(self):
        old=self.old();before=copy.deepcopy(old);b.check_historical(old);self.assertEqual(old,before)
        for field,value in [('status','pass'),('errors',[]),('schema','anything')]:
            with self.assertRaises(ValueError):b.check_historical(dict(old,**{field:value}))
        for key in b.RETAINED_ZERO:
            for value in (False,.00001,-.00001,None,float('nan')):
                bad=copy.deepcopy(old);bad['variants']['magnetic'][key]=value
                with self.assertRaises(ValueError):b.check_historical(bad)
    def pairs(self):
        rows=[]
        for part in (0,1):
            for tool in range(153):
                aa=[1000.,0.,0.,1001.,1.,1.];bb=[float(tool),0.,-.40001,float(tool+1),1.,2.50001]
                rows.append(dict(part=part,tool=tool,clear=True,method='outward_padded_aabb',distance_lower_bound_mm=aa[0]-bb[3],a_bounds_mm=aa,b_bounds_mm=bb))
        return rows
    def test_exact_pair_inventory_no_duplicate_missing_or_boolean_indices(self):
        rows=self.pairs();b.check_pair_rows(rows,{})
        for bad in (rows[:-1],rows+[rows[0]],rows[:-1]+[rows[0]]):
            with self.assertRaises(ValueError):b.check_pair_rows(bad,{})
        bad=copy.deepcopy(rows);bad[0]['part']=False
        with self.assertRaises(ValueError):b.check_pair_rows(bad,{})
    def test_no_generic_distance_override_or_forged_aabb_margin(self):
        rows=self.pairs();bad=copy.deepcopy(rows);bad[0]['distance_lower_bound_mm']+=1
        with self.assertRaises(ValueError):b.check_pair_rows(bad,{})
        bad=copy.deepcopy(rows);bad[0].update(method='solid_solid_extrema',distance_mm=0.,is_done=True,clear=False)
        with self.assertRaises(ValueError):b.check_pair_rows(bad,{})
        with self.assertRaises(ValueError):b.check_pair_rows(bad,{(0,0):True})
    def test_all_three_records_must_bind_current_material_without_conflicts(self):
        from hashlib import sha256
        files={'actual.step':b'actual','generation.json':b'gen','checker.py':b'checker'}
        required={n:sha256(files[n]).hexdigest() for n in ('actual.step','generation.json')}
        records=[dict(source_sha256={**required,'checker.py':sha256(files['checker.py']).hexdigest()}) for _ in range(3)]
        b.check_current_sources(records,files.__getitem__,required)
        bad=copy.deepcopy(records);bad[2]['source_sha256']['actual.step']='0'*64
        with self.assertRaises(ValueError):b.check_current_sources(bad,files.__getitem__,required)
        bad=copy.deepcopy(records);bad[1]['source_sha256'].pop('generation.json')
        with self.assertRaises(ValueError):b.check_current_sources(bad,files.__getitem__,required)
        files['checker.py']=b'changed'
        with self.assertRaises(ValueError):b.check_current_sources(records,files.__getitem__,required)
    def test_tool_geometry_order_volume_and_section_proof_required(self):
        from shapely.geometry import box
        from shapely.ops import unary_union
        from hashlib import sha256
        polygons=[box(i*3,0,i*3+1,1) for i in range(153)]
        rows=[]
        for i,g in enumerate(polygons):
            x0,y0,x1,y1=g.bounds
            rows.append(dict(tool=i,expected_wkt=g.wkt,expected_sha256=sha256(g.wkt.encode()).hexdigest(),actual_bounds_mm=[x0,y0,-.4,x1,y1,2.5],actual_volume_mm3=2.9,actual_section_missing_mm2=0.,actual_section_extra_mm2=0.,actual_section_wkt=g.wkt,valid=True,closed=True,axis_prismatic=True,vertex_z_mm=[-.4,2.5]))
        c=dict(actual_tool_count=153,required_tool_union_wkt=unary_union(polygons).wkt,required_z_mm=[-.4,2.5],tool_inventory=rows)
        b.check_tool_inventory(polygons,c)
        for field,value in [('actual_volume_mm3',1.),('actual_section_missing_mm2',.0001),('axis_prismatic',False),('vertex_z_mm',[-.4,0.,2.5]),('expected_sha256','0'*64)]:
            bad=copy.deepcopy(c);bad['tool_inventory'][2][field]=value
            with self.assertRaises(ValueError):b.check_tool_inventory(polygons,bad)
        bad=copy.deepcopy(c);bad['tool_inventory'][2],bad['tool_inventory'][3]=bad['tool_inventory'][3],bad['tool_inventory'][2]
        with self.assertRaises(ValueError):b.check_tool_inventory(polygons,bad)
    def test_no_bundle_without_all_actual_records(self):
        with self.assertRaises((KeyError,FileNotFoundError)):b.assemble({}.__getitem__)

    def complete_fixture(self):
        from shapely.geometry import box,Point
        from shapely.ops import unary_union
        polygons=[box(i*3,0,i*3+1,1) for i in range(153)]
        polygons[2]=box(15.393103061379296,31.918103061379306,18.156896938620715,38.131896938620706)
        inventory=[]
        for i,g in enumerate(polygons):
            x0,y0,x1,y1=g.bounds
            inventory.append(dict(tool=i,expected_wkt=g.wkt,expected_sha256=b.sha_bytes(g.wkt.encode()),actual_bounds_mm=[x0,y0,-.4,x1,y1,2.5],actual_volume_mm3=g.area*2.9,actual_section_missing_mm2=0.,actual_section_extra_mm2=0.,actual_section_wkt=g.wkt,valid=True,closed=True,axis_prismatic=True,vertex_z_mm=[-.4,2.5]))
        partbounds=[[-10.,-10.,-.5,500.,50.,2.5],[1000.,0.,-.5,1001.,1.,2.5]];required={};cases=[];generations={};variants={}
        for variant in b.VARIANTS:
            folder=b.STAGE+'/lower/right-'+variant;step=folder+'/'+b.stem('lower','right',variant)+'.step';gp=folder+'/generation.json';required.update({step:'a'*64,gp:'b'*64})
            generations[variant]={'parts':[dict(bounds_mm=bb) for bb in partbounds]};g=polygons[2];point=g.centroid;crop=box(*g.buffer(1).bounds);section=crop.difference(g.buffer(.1,join_style=2))
            local=dict(eligible=True,errors=[],subject_valid=True,tool_valid=True,subject_closed=True,tool_closed=True,subject_not_contained_by_tool=True,a_shell_count=1,tool_shell_count=1,shell_pairs=[dict(a_shell=0,tool_shell=0,is_done=True,inner_solution=False,distance_mm=.03)],
              seed=dict(xyz=[point.x,point.y,1.05],tool_plan_contains=True,actual_classifier_inside=False,actual_section_inside=False,section_distance_mm=section.distance(point)),
              roi=dict(errors=[],valid=True,all_faces_planar_axis_aligned=True,levels_mm=[-.5,2.5],face_count=10,vertical_face_count=8,horizontal_face_count=2,section_z_mm=1.05,section_area_mm2=section.area,tool_overlap_mm2=0.,tool_outside_roi_mm2=0.,volume_error_mm3=0.,section_wkt=section.wkt,footprint_wkt=crop.wkt))
            cases.append(dict(variant=variant,part=0,tool=2,step_path=step,step_sha256=required[step],generation_path=gp,generation_sha256=required[gp],local=local));pairs=[]
            for part in (0,1):
                for tool,row in enumerate(inventory):
                    pad=lambda bb:[v+(-1e-5 if i<3 else 1e-5) for i,v in enumerate(bb)]
                    aa,bb=pad(partbounds[part]),pad(row['actual_bounds_mm']);sep=max([bb[i]-aa[i+3] for i in range(3)]+[aa[i]-bb[i+3] for i in range(3)])
                    pair=dict(part=part,tool=tool,clear=True,a_bounds_mm=aa,b_bounds_mm=bb)
                    if sep>1e-4:pair.update(method='outward_padded_aabb',distance_lower_bound_mm=sep)
                    else:pair.update(method='solid_solid_extrema',is_done=True,distance_mm=1.)
                    if (part,tool)==(0,2):pair.update(clear=False,method='solid_solid_extrema',is_done=True,distance_mm=0.)
                    pairs.append(pair)
            variants[variant]=dict(body_count=2,tool_count=153,pair_count=306,all_clear=False,minimum_distance_lower_bound_mm=0.,pairs=pairs)
        certificate=dict(schema='right-d8-local-certificate-v1',status='pass',errors=[],source_sha256=required,actual_tool_count=153,required_z_mm=[-.4,2.5],required_tool_union_wkt=unary_union(polygons).wkt,tool_inventory=inventory,cases=cases)
        area=sum(g.area for g in polygons)
        distance=dict(schema='lower-component-distance-v1',side='right',original_boolean_status='fail',original_boolean_failure_retained=True,bound_padding_mm=1e-5,positive_margin_mm=1e-4,variants=variants,status='fail',errors=[v+' required component clearance not proved' for v in b.VARIANTS],
          tool=dict(valid=True,solid_count=153,z_mm=[-.4,2.5],plan_area_mm2=area,expected_volume_mm3=area*2.9,actual_volume_mm3=area*2.9,required_clearance_mm=.3,conservative_offset_mm=.301,circumscribed_radius_mm=.301/b.math.cos(b.math.pi/16)))
        return distance,certificate,polygons,generations,required

    def test_complete_geometry_certificate_rejects_malformed_seed_empty_roi_and_missing_tool(self):
        args=self.complete_fixture();result=b.check_complete_component(*args);self.assertEqual(sum(v['pair_count'] for v in result.values()),612)
        for xyz in ([1,2],[True,35,1.05],[16,35,float('nan')]):
            bad=copy.deepcopy(args);bad[1]['cases'][0]['local']['seed']['xyz']=xyz
            with self.assertRaises(ValueError):b.check_complete_component(*bad)
        bad=copy.deepcopy(args);bad[1]['cases'][0]['local']['roi']['section_wkt']='POLYGON EMPTY'
        with self.assertRaises(ValueError):b.check_complete_component(*bad)
        bad[1]['cases'][0]['local']['roi']['section_area_mm2']=0.
        with self.assertRaises(ValueError):b.check_complete_component(*bad)
        bad=copy.deepcopy(args);bad[1]['tool_inventory'].pop()
        with self.assertRaises(ValueError):b.check_complete_component(*bad)

    def test_actual_tool_section_geometry_cannot_disagree_with_numeric_claim(self):
        args=self.complete_fixture();certificate=args[1];polygons=args[2]
        for text in ('POLYGON ((0 0,1 0,1 1,0 0))','POLYGON EMPTY','LINESTRING (0 0,1 1)',
                     'POLYGON ((0 0,Infinity 0,1 1,0 0))','POLYGON ((0 0,NaN 0,1 1,0 0))',None):
            bad=copy.deepcopy(certificate);bad['tool_inventory'][2]['actual_section_wkt']=text
            with self.subTest(section=text),self.assertRaises(ValueError):b.check_tool_inventory(polygons,bad)
        bad=copy.deepcopy(certificate);del bad['tool_inventory'][2]['actual_section_wkt']
        with self.assertRaises(ValueError):b.check_tool_inventory(polygons,bad)
        bad=copy.deepcopy(certificate);bad['tool_inventory'][2]['actual_section_extra_mm2']=1e-9
        with self.assertRaises(ValueError):b.check_tool_inventory(polygons,bad)

if __name__=='__main__':unittest.main()
