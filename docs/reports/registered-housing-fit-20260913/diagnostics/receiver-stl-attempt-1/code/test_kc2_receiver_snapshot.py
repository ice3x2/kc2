"""CON-ARCH-006 immutable parent selection and fail-closed emission."""
import json
import tempfile
import unittest
import sys
import types
from pathlib import Path
from unittest.mock import patch
from tools import stage_kc2_receiver_cleanup as stage
from tools import kc2_lower_predicate_bundle as bundle


class SnapshotTests(unittest.TestCase):
    def test_strata_snapshot_archives_both_actual_proofs_and_parent(self):
        mapping=stage.snapshot_mapping('strata_bundle')
        cache=stage.STAGE+'/lower-development/receiver-cleanup-inputs'
        for name in ('right-normal-strata-review.json','right-magnetic-subset-review.json',
                     'right-strata-predicate-bundle.json','right-void-review.json'):
            self.assertEqual(stage.resolve_alias(stage.STAGE+'/lower/'+name,mapping),cache+'/'+name)
        for variant in ('normal','magnetic'):
            self.assertEqual(stage.resolve_alias(stage.STAGE+'/lower/right-'+variant+'/generation.json',mapping),
                             cache+'/right-'+variant+'/generation.json')
        with self.assertRaises(ValueError):stage.snapshot_mapping('unknown')

    def test_strata_parent_requires_its_complete_validator(self):
        from unittest.mock import Mock
        validator=Mock(side_effect=ValueError('incomplete strata proof'))
        module=types.ModuleType('tools.kc2_lower_strata_bundle')
        module.validate_bundle=validator
        raw=json.dumps({'schema':'right-lower-strata-predicate-bundle-v1'}).encode()
        read=lambda name:raw
        with patch.dict(sys.modules,{'tools.kc2_lower_strata_bundle':module}):
            with self.assertRaises(ValueError):stage.validate_parent('strata_bundle',read)
        validator.assert_called_once_with(json.loads(raw),read)
        validator.side_effect=None
        validator.return_value=False
        with patch.dict(sys.modules,{'tools.kc2_lower_strata_bundle':module}):
            with self.assertRaises(ValueError):stage.validate_parent('strata_bundle',read)

    def test_strata_parent_has_distinct_identity(self):
        self.assertEqual(stage.parent_path('strata_bundle'),
                         stage.STAGE+'/lower/right-strata-predicate-bundle.json')
        self.assertNotEqual(stage.parent_path('strata_bundle'),
                            stage.parent_path('predicate_bundle'))

    def test_snapshot_reuse_requires_parent_and_full_historical_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); cache=f'{stage.STAGE}/lower-development/receiver-cleanup-inputs'
            mapping={f'{stage.STAGE}/lower/right-{v}':f'{cache}/right-{v}' for v in ('normal','magnetic')}
            for name in ('right-void-review.json','right-component-distance-review.json','right-d8-local-certificate.json','right-predicate-bundle.json'):
                mapping[f'{stage.STAGE}/lower/{name}']=f'{cache}/{name}'
            mapping['.codex-tmp/receiver_cleanup_candidate.py']=cache+'/provenance/receiver_cleanup_candidate.py'
            parent=stage.parent_path('predicate_bundle'); archived=stage.resolve_alias(parent,mapping)
            path=root/archived; path.parent.mkdir(parents=True); path.write_text('{}')
            sha=stage.digest(path)
            record=dict(status='verified_historical_snapshot',parent_proof_kind='predicate_bundle',parent_proof_path=parent,parent_proof_sha256=sha,
                historical_original_sha256={parent:sha},source_sha256={archived:sha},path_mapping=mapping)
            manifest=root/cache/'snapshot-map.json'; manifest.write_text(json.dumps(record))
            with patch.object(stage,'ROOT',root):
                with self.assertRaises(ValueError):stage.prepare('direct_v2')
                def check(row,read):
                    self.assertEqual(read(parent),b'{}')
                    read('missing-evidence')
                with patch.object(bundle,'validate_bundle',side_effect=check):
                    with self.assertRaises(ValueError):stage.prepare('predicate_bundle')
                path.write_text('changed')
                with patch.object(bundle,'validate_bundle') as check:
                    with self.assertRaises(ValueError):stage.prepare('predicate_bundle')
                    check.assert_not_called()

    def test_alias_conflict_preflight_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'a').write_bytes(b'a'); (root/'b').write_bytes(b'b')
            (root/'taken').write_bytes(b'wrong')
            with self.assertRaises(ValueError):
                stage.snapshot_sources(root, {'a':stage.digest(root/'a'),'b':stage.digest(root/'b')}, {'a':'new','b':'taken'})
            self.assertFalse((root/'new').exists())

    def test_alias_collision_and_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'a').write_bytes(b'a'); (root/'b').write_bytes(b'a')
            sources={p:stage.digest(root/p) for p in ('a','b')}
            for mapping in ({'a':'same','b':'same'}, {'a':'../escape'}):
                with self.assertRaises(ValueError): stage.snapshot_sources(root,sources,mapping)

    def test_parent_kind_requires_explicit_semantics(self):
        raw={'schema':'lower-void-v2','status':'fail'}
        read=lambda p:json.dumps(raw).encode()
        with self.assertRaises((ValueError,KeyError)): stage.validate_parent('direct_v2',read)
        with self.assertRaises(ValueError): stage.validate_parent('other',read)
        with patch.object(bundle,'validate_bundle',side_effect=ValueError('incomplete')) as check:
            with self.assertRaises(ValueError): stage.validate_parent('predicate_bundle',read)
            check.assert_called_once()

    def test_emitter_missing_or_changing_sources_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaises(FileNotFoundError): bundle.emit(root)
            self.assertFalse((root/bundle.OUTPUT).exists())
            (root/'input').write_bytes(b'new')
            fake={'source_sha256':{'input':'0'*64}}
            with patch.object(bundle,'assemble',return_value=fake):
                with self.assertRaises(ValueError): bundle.emit(root)
            self.assertFalse((root/bundle.OUTPUT).exists())

    def test_emitter_distinct_output_and_immutable_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); original=root/bundle.ORIGINAL
            original.parent.mkdir(parents=True); original.write_bytes(b'failed original')
            record={'source_sha256':{bundle.ORIGINAL:stage.digest(original)}}
            with patch.object(bundle,'assemble',return_value=record):
                bundle.emit(root)
                self.assertEqual(original.read_bytes(),b'failed original')
                (root/bundle.OUTPUT).write_bytes(b'conflict')
                with self.assertRaises(ValueError):bundle.emit(root)


if __name__=='__main__': unittest.main()
