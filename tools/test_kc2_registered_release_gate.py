"""CON-ARCH-006 / OPS-ARCH-006 fail-closed release-preparation contracts."""
import hashlib
import tempfile
from pathlib import Path
import unittest
from tools.kc2_registered_release_gate import inventory,required_gate_ids,resolve_binding,check_sections,check_job_report,check_native_links,check_inventory,preparation_status,evidence_destination


class ReleaseGateTests(unittest.TestCase):
    def test_exact_35_canonical_names(self):
        rows=inventory()
        self.assertEqual(len(rows),35)
        self.assertEqual(sum(p.endswith('.step') for p in rows),10)
        self.assertEqual(sum(p.endswith('.f3d') for p in rows),10)
        self.assertEqual(sum(p.endswith('.stl') for p in rows),15)
        self.assertIn('hardware/MODELS/kc2_right_lower_housing_part_a_magnetic.stl',rows)
        self.assertNotIn('hardware/MODELS/kc2_right_lower_housing.stl',rows)

    def test_future_mechanical_gates_are_required(self):
        gates=required_gate_ids()
        for name in ['central_actual','full_joined_path','lower_ab_actual','lower_root_actual','printability_actual']:
            self.assertIn(name,gates)
        self.assertEqual(len(gates),54)
        self.assertFalse(preparation_status(gates)['publication_authorized'])

    def test_active_output_cannot_be_duplicated_as_evidence(self):
        with self.assertRaises(ValueError):evidence_destination(next(iter(inventory().values())))

    def test_changed_or_missing_output_cannot_pass_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);expected={}
            for target,source in inventory().items():
                path=root/source;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(source.encode())
                expected[target]=hashlib.sha256(source.encode()).hexdigest()
            self.assertEqual(len(check_inventory(root,expected)),35)
            first=next(iter(inventory().values()));(root/first).write_bytes(b'changed')
            with self.assertRaises(ValueError):check_inventory(root,expected)
            with self.assertRaises(ValueError):check_inventory(root,{})

    def test_baseline_model_binding_does_not_read_new_canonical_bytes(self):
        name='hardware/MODELS/kc2_left_mx_upper_housing.step'
        old=b'old model';new=b'new model'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/name).parent.mkdir(parents=True);(root/name).write_bytes(new)
            result=resolve_binding(root,name,hashlib.sha256(old).hexdigest(),git_reader=lambda rev,path:old)
            self.assertEqual(result['kind'],'git_blob')
            with self.assertRaises(ValueError):
                resolve_binding(root,name,hashlib.sha256(new).hexdigest(),git_reader=lambda rev,path:old)

    def test_missing_height_section_rejected(self):
        row=dict(status='pass',errors=[],levels_mm=[0,1,2],sections=[dict(z_mm=.5,missing_mm2=0,extra_mm2=0)],volume_error_mm3=0)
        with self.assertRaises(ValueError):check_sections(row)

    def test_large_volume_difference_rejected(self):
        row=dict(status='pass',errors=[],levels_mm=[0,1],sections=[dict(z_mm=.5,missing_mm2=0,extra_mm2=0,actual_area_mm2=10)],volume_error_mm3=5)
        with self.assertRaises(ValueError):check_sections(row)

    def test_failed_native_source_chain_rejected(self):
        context=dict(label='upper:left:mx',family='upper',side='left',kind='mx',count=1,
            generation='g.json',step='x.step',generation_sha256='a'*64,step_sha256='b'*64,stem='kc2_left_mx_upper_housing')
        output=dict(source_sha256='b'*64,generation_sha256='a'*64,round_trip_verified=True,expected_body_count=1,
                    source_step=context['stem']+'.step',f3d=context['stem']+'.f3d',readback_step=context['stem']+'.native-readback.step',
                    f3d_sha256='d'*64,readback_sha256='e'*64,source_solids=[{}],reopened_solids=[{}])
        record=dict(status='pass',selected_job=context['label'],phase='complete',source_sha256={'x.step':'b'*64,'g.json':'a'*64},
                    outputs={context['label']:output})
        check_job_report('native_generation',record,context)
        output['generation_sha256']='c'*64
        with self.assertRaises(ValueError):check_job_report('native_generation',record,context)

    def test_native_archive_readback_review_must_bind_same_bytes(self):
        context=dict(label='upper:left:mx',step='stage/model.step',native_generation_sha256='c'*64)
        produced=dict(outputs={context['label']:dict(f3d='model.f3d',f3d_sha256='a'*64,readback_step='model.native-readback.step',readback_sha256='b'*64)})
        reviewed=dict(source_sha256={'stage/model.f3d':'d'*64,'stage/model.native-readback.step':'b'*64,'stage/native-generation.json':'c'*64})
        with self.assertRaises(ValueError):check_native_links(produced,reviewed,context)


if __name__=='__main__':unittest.main()
