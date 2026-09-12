"""CON-ARCH-006 six native jobs; source preflight before Fusion mutation."""
import hashlib,json,tempfile,unittest
from pathlib import Path
from tools.kc2_filled_native import preflight_jobs


class FilledNativeTests(unittest.TestCase):
    def fixture(self,folder):
        for side in ['left','right']:
            for kind in ['mx','choc_v1','deep_sea']:
                name=f'kc2_{side}_{kind}_upper_housing.step';p=folder/name;p.touch()
                record=dict(status='generated_pending_independent_review',side=side,kind=kind,
                    parts=[{}]*(1 if side=='left' else 2),source_sha256={},outputs={name:hashlib.sha256(b'').hexdigest()})
                (folder/f'{side}-{kind}.json').write_text(json.dumps(record))

    def test_all_three_families_both_sides_and_expected_body_counts(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root);jobs=preflight_jobs(root,root)
            self.assertEqual(len(jobs),6)
            self.assertEqual(sum(j['count'] for j in jobs),9)

    def test_missing_deep_sea_cannot_silently_export_only_mx(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root);(root/'kc2_left_deep_sea_upper_housing.step').unlink()
            with self.assertRaises(FileNotFoundError):preflight_jobs(root,root)

    def test_changed_step_or_invalid_body_count_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root);(root/'kc2_right_mx_upper_housing.step').write_text('changed')
            with self.assertRaisesRegex(ValueError,'Changed'):preflight_jobs(root,root)
            self.fixture(root)
            path=root/'right-mx.json';r=json.loads(path.read_text());r['parts']=[];path.write_text(json.dumps(r))
            with self.assertRaisesRegex(ValueError,'body count'):preflight_jobs(root,root)


if __name__=='__main__':unittest.main()
