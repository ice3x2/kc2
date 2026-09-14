"""CON-ARCH-006 immutable pair and exact subtractive left repair contracts."""
import json
import tempfile
import unittest
from pathlib import Path


class LeftCentralProducerTests(unittest.TestCase):
    def test_actual_trimmed_males_are_hash_bound_individually(self):
        import cadquery as cq
        from tools.stage_kc2_left_central_relief import load_protected_males,digest,STAGE
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/STAGE/'central';folder.mkdir(parents=True)
            outputs={};sources={}
            nominal=cq.Workplane('XY').box(2,2,2).val()
            trim=cq.Workplane('XY').box(1,1,1).val().translate((1,1,1))
            for y in (95,117):
                shape=(nominal.cut(trim) if y==95 else nominal).translate((0,y,0))
                path=folder/f'left-central-y{y}.step';cq.exporters.export(shape,str(path))
                outputs[path.name]=digest(path);sources[path.relative_to(root).as_posix()]=digest(path)
            path=folder/'central-features.json'
            path.write_text(json.dumps(dict(status='feature_geometry_pass_integration_pending',outputs=outputs,source_sha256={})))
            sources[path.relative_to(root).as_posix()]=digest(path)
            shapes=load_protected_males(root,sources)
            self.assertEqual(set(shapes),{95,117})
            self.assertLess(shapes[95].Volume(),shapes[117].Volume())
            key=(folder/'left-central-y95.step').relative_to(root).as_posix()
            for bad in ({k:v for k,v in sources.items() if k!=key},dict(sources,**{key:'0'*64})):
                with self.assertRaises(ValueError):load_protected_males(root,bad)

    def test_archived_output_removed_from_manifest_is_rejected(self):
        from tools.stage_kc2_left_central_relief import prepare,digest,STAGE,CACHE
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def write(name,data):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(json.dumps(data));return path
            for variant in ('normal','magnetic'):
                folder=STAGE+'/lower/left-'+variant
                stem='kc2_left_lower_housing'+('_magnetic' if variant=='magnetic' else '')
                outputs={}
                for suffix in ('.step','.stl'):
                    path=write(folder+'/'+stem+suffix,{'synthetic':suffix});outputs[stem+suffix]=digest(path)
                registrar=write(folder+'/registrar-snapshot.json',{'source_sha256':{}})
                write(folder+'/generation.json',dict(status='generated_pending_independent_review',side='left',
                    magnetic=variant=='magnetic',body_count=1,ordinary_wall_top_mm=4.1,registrar_top_mm=5.,
                    outputs=outputs,source_sha256={folder+'/registrar-snapshot.json':digest(registrar)}))
            write(STAGE+'/central/integrated-review.json',dict(status='failed',
                rows={f'{v}-y{y}':{} for v in ('normal','magnetic') for y in (95,117)},source_sha256={}))
            write(STAGE+'/central/overlap-localization.json',dict(status='diagnosed_not_accepted',
                rows=[dict(y=y,unexpected_in_old_left_mm3=0,unexpected_in_isolated_left_mm3=0) for y in (95,117)],source_sha256={}))
            write('.codex-tmp/perimeter-wall-plans.json',{'source_sha256':{}})
            prepare(root)
            manifest=root/CACHE/'snapshot-map.json';record=json.loads(manifest.read_text())
            original=STAGE+'/lower/left-normal/kc2_left_lower_housing.step'
            del record['historical_original_sha256'][original]
            del record['source_sha256'][CACHE+'/left-normal/kc2_left_lower_housing.step']
            manifest.write_text(json.dumps(record))
            with self.assertRaises(ValueError):prepare(root)

    def test_existing_snapshot_cannot_drop_critical_binding(self):
        from unittest.mock import patch
        from tools.stage_kc2_left_central_relief import prepare,seal_snapshot,digest,CACHE,MAPPING
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'critical').write_bytes(b'original');sha=digest(root/'critical')
            seal_snapshot(root,{'critical':sha},MAPPING,root/CACHE/'snapshot-map.json')
            with patch('tools.stage_kc2_left_central_relief.collect_original_sources',return_value={'critical':sha,'required.step':'0'*64}):
                with self.assertRaises(ValueError):prepare(root)

    def test_one_solid_rejects_unowned_topology(self):
        import cadquery as cq
        from tools.stage_kc2_left_central_relief import single
        solid=cq.Workplane('XY').box(2,2,2).val()
        face=cq.Face.makePlane(1,1,basePnt=(10,10,10))
        edge=cq.Edge.makeLine((10,10,10),(11,10,10))
        vertex=cq.Vertex.makeVertex(10,10,10)
        single(cq.Compound.makeCompound([solid]))
        for orphan in (face,edge,vertex):
            with self.assertRaises(ValueError):single(cq.Compound.makeCompound([solid,orphan]))

    def test_snapshot_missing_stale_and_collision_rejected_before_copy(self):
        from tools.stage_kc2_left_central_relief import seal_snapshot,digest
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'a').write_bytes(b'a');(root/'b').write_bytes(b'a');sha=digest(root/'a')
            for sources,mapping in (({'a':'0'*64},{'a':'cache/a'}),({'missing':sha},{'missing':'cache/a'}),
                                    ({'a':sha},{'a':'../escape'}),
                                    ({'a':sha,'b':sha},{'a':'cache/a','b':'cache/a'})):
                with self.assertRaises((ValueError,OSError)):seal_snapshot(root,sources,mapping,root/'cache/map.json')
                self.assertFalse((root/'cache/a').exists())
            record=seal_snapshot(root,{'a':sha},{'a':'cache/a'},root/'cache/map.json')
            self.assertEqual((root/'cache/a').read_bytes(),b'a')
            self.assertEqual(record['source_sha256'],{'cache/a':sha})
            (root/'cache/a').write_bytes(b'changed')
            with self.assertRaises(ValueError):seal_snapshot(root,{'a':sha},{'a':'cache/a'},root/'cache/map.json')

    def test_generation_requires_exact_pair_identity_and_outputs(self):
        from tools.stage_kc2_left_central_relief import validate_original
        record=dict(status='generated_pending_independent_review',side='left',magnetic=False,body_count=1,
                    ordinary_wall_top_mm=4.1,registrar_top_mm=5.,source_sha256={'a':'0'*64},
                    outputs={'kc2_left_lower_housing.step':'a'*64,'kc2_left_lower_housing.stl':'b'*64})
        validate_original(record,'normal')
        for change in ({'magnetic':True},{'body_count':True},{'ordinary_wall_top_mm':4.35},
                       {'source_sha256':{}},{'outputs':{'wrong.step':'a'*64}},
                       {'left_central_relief':{'done':True}}):
            with self.assertRaises(ValueError):validate_original(dict(record,**change),'normal')

    def test_exact_change_protects_full_old_stock_and_male(self):
        import cadquery as cq
        from tools.stage_kc2_left_central_relief import apply_relief
        base=cq.Workplane('XY').box(4,4,2,centered=(False,False,False)).val()
        added=cq.Workplane('XY').box(2,2,2,centered=(False,False,False)).val().translate((4,0,0))
        before=base.fuse(added)
        male=cq.Workplane('XY').box(1,1,1,centered=(False,False,False)).val().translate((4,0,0))
        cutter=cq.Workplane('XY').box(1,2,2,centered=(False,False,False)).val().translate((5,0,0))
        males={95:male,117:male.translate((0,1,0))}
        after,audit=apply_relief(before,[cutter],base,males)
        self.assertEqual(len(after.Solids()),1)
        self.assertAlmostEqual(audit['removed_mm3'],4.)
        for k,v in audit.items():
            if k=='remaining_cut_per_tool_mm3':self.assertEqual(v,[0.])
            elif k in ('male_missing_before_per_y_mm3','male_missing_after_per_y_mm3'):self.assertEqual(v,{'95':0.,'117':0.})
            elif k!='removed_mm3':self.assertEqual(v,0.,k)
        for bad in (base,male):
            with self.assertRaises(ValueError):apply_relief(before,[bad],base,males)
        with self.assertRaises(ValueError):apply_relief(before,[],base,males)
        # Equal nonzero before/after missing material must never be waived.
        with self.assertRaises(ValueError):apply_relief(before,[cutter],base,{95:male.translate((20,0,0)),117:males[117]})
        with self.assertRaises(ValueError):apply_relief(before,[cutter],base,{95:male})


if __name__=='__main__':unittest.main()
