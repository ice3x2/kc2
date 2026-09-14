"""CON-ARCH-006 one-job native export must reject incomplete/stale sources."""
import json,tempfile,unittest
from pathlib import Path
from tools.kc2_registered_native import preflight_job,revalidate_job,digest


class RegisteredNativeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        (self.root/'source.py').write_text('source')

    def fixture(self,label='upper:left:mx'):
        family,side,kind=label.split(':');folder=self.root/'.codex-tmp/registered-housing-fit'/family/(side+'-'+kind);folder.mkdir(parents=True)
        stem=f'kc2_{side}_{kind}_upper_housing' if family=='upper' else f'kc2_{side}_lower_housing'+('_magnetic' if kind=='magnetic' else '')
        step=folder/(stem+'.step');step.write_text('STEP source')
        d=dict(status='generated_pending_independent_review',side=side,source_sha256={'source.py':digest(self.root/'source.py')},outputs={step.name:digest(step)})
        if family=='upper':d.update(kind=kind,parts=[{}]*(1 if side=='left' else 2))
        else:d.update(magnetic=kind=='magnetic',body_count=1 if side=='left' else 2)
        path=folder/'generation.json';path.write_text(json.dumps(d));return path,d,step

    def test_CON_ARCH_006_only_selected_job_needed(self):
        self.fixture();job=preflight_job(self.root,'upper:left:mx');self.assertEqual(job['count'],1)
        self.assertEqual(job['label'],'upper:left:mx');revalidate_job(self.root,job)

    def test_CON_ARCH_006_all_ten_fixed_identities(self):
        for family,kinds in [('upper',['mx','choc_v1','deep_sea']),('lower',['normal','magnetic'])]:
            for side in ['left','right']:
                label=f'{family}:{side}:{kinds[0]}'
                for kind in kinds:
                    label=f'{family}:{side}:{kind}';self.fixture(label)
                    self.assertEqual(preflight_job(self.root,label)['count'],1 if side=='left' else 2)

    def test_CON_ARCH_006_unknown_or_bulk_jobs_rejected(self):
        for label in ['all','upper:left:normal','lower:left:mx','upper:middle:mx',None,{}]:
            with self.subTest(label=label),self.assertRaises(ValueError):preflight_job(self.root,label)

    def test_CON_ARCH_006_incomplete_identity_body_count_rejected(self):
        p,d,s=self.fixture()
        for key,value in [('status','building'),('kind','deep_sea'),('side','right'),('parts',[{},{}]),('source_sha256',{})]:
            bad=dict(d);bad[key]=value;p.write_text(json.dumps(bad))
            with self.subTest(key=key),self.assertRaises(ValueError):preflight_job(self.root,'upper:left:mx')

    def test_CON_ARCH_006_changed_STEP_or_source_rejected(self):
        p,d,s=self.fixture();s.write_text('changed')
        with self.assertRaises(ValueError):preflight_job(self.root,'upper:left:mx')
        d['outputs'][s.name]=digest(s);p.write_text(json.dumps(d));(self.root/'source.py').write_text('changed')
        with self.assertRaises(ValueError):preflight_job(self.root,'upper:left:mx')

    def test_CON_ARCH_006_freeze_checks_sources_and_record_after_export(self):
        p,d,s=self.fixture();job=preflight_job(self.root,'upper:left:mx');(self.root/'source.py').write_text('changed')
        with self.assertRaises(ValueError):revalidate_job(self.root,job)

    def test_CON_ARCH_006_path_escape_rejected(self):
        p,d,s=self.fixture();d['source_sha256']={'../outside':digest(s)};p.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError,'path'):preflight_job(self.root,'upper:left:mx')

    def test_CON_ARCH_006_lower_boolean_count_rejected(self):
        p,d,s=self.fixture('lower:left:normal');d['body_count']=True;p.write_text(json.dumps(d))
        with self.assertRaises(ValueError):preflight_job(self.root,'lower:left:normal')

    def test_CON_ARCH_006_Fusion_entry_rejects_missing_selection_before_API(self):
        import runpy
        path=Path(__file__).resolve().parent/'fusion/KC2RegisteredHousingToF3D/KC2RegisteredHousingToF3D.py'
        entry=runpy.run_path(str(path))['run']
        with self.assertRaisesRegex(ValueError,'exactly one'):entry()

    def test_CON_ARCH_006_record_rewrite_during_preflight_rejected(self):
        from unittest.mock import patch
        p,d,s=self.fixture();original=digest;changed=False
        def racing_digest(path):
            nonlocal changed
            if Path(path)==p and not changed:
                changed=True;d['status']='building';p.write_text(json.dumps(d))
            return original(path)
        with patch('tools.kc2_registered_native.digest',side_effect=racing_digest):
            with self.assertRaises(ValueError):preflight_job(self.root,'upper:left:mx')


if __name__=='__main__':unittest.main()
