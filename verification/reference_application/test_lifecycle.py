"""Focused lifecycle invariants, genuine store transactions and existing authority boundaries."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'tooling')]
from engineering.reference_application.lifecycle import evolution_request,detach_outputs,restore_modules,tree,adapter_source,original_rows_preserved,generated_outputs_equivalent
from engineering.reference_application.inspection import extension_baseline,HUMAN
from engineering.demo.pipeline import inputs
from engineering.source_intelligence.model import sha
from filesystem_artifacts import FilesystemArtifactStore,StoreConflict
from compiler_contracts import Owner

class Lifecycle(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.c,cls.s,cls.r,cls.plan=inputs('case-management')
 def test_actual_compilation_has_all_eight_stages_and_original_approved_identity(self):
  self.assertEqual(len(self.c.executions[0]['audit']['stages']),8)
  self.assertEqual(self.s.read()['contentDigest'],'sha256:5b3a69bb1d6e0e69ed620cd1dd32d10e8a07cec276583055b53ec03bfdcc6b90')
 def test_real_regeneration_preserves_human_bytes_and_rejects_unmanaged_drift(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'case';store=FilesystemArtifactStore(root);store.apply(self.plan);store.adopt_human(HUMAN)
   p=root/HUMAN;p.write_bytes(p.read_bytes()+b'\n// reviewer owned\n');human=p.read_bytes()
   plan=self.c.plan(self.s,self.r,inventory=store.inventory());store.apply(plan);self.c.verify_materialized(root,plan,self.s,self.r)
   before=root.stat().st_ino;data=tree(root);store.apply(self.c.plan(self.s,self.r,inventory=store.inventory()))
   self.assertNotEqual(root.stat().st_ino,before);self.assertEqual(p.read_bytes(),human);self.assertEqual(tree(root),data)
   f=root/'frontend/src/App.vue';old=f.read_bytes();f.write_bytes(old+b'\n<!-- unauthorized -->\n')
   with self.assertRaisesRegex(StoreConflict,'MANUAL_EDIT'):store.inventory()
   f.write_bytes(old);self.assertEqual(next(a for a in store.inventory() if a.path==HUMAN).owner,Owner.HUMAN)
 def test_r2_existing_content_approval_does_not_authorize_migration(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'rows.json').write_text(json.dumps({'e_d35114736c127b0a4f015cde':[{'f_bf60325b4cdc299c2172f24c':'resource-bytes','f_883bd4a687ba22abd76d5b51':'tenant-bytes'}]}));r=evolution_request(p/'rows.json',p/'request.json')
   self.assertEqual(r['semanticContent'],'APPROVED_CONTENT');self.assertEqual(r['status'],'BLOCKED');self.assertFalse(r['migrationExecuted']);self.assertFalse(r['historicalBindingReusable']);self.assertEqual(len(r['missing']),4)
 def test_r2_rejects_modified_proposal_bytes(self):
  original=Path.read_bytes
  with tempfile.TemporaryDirectory() as t,patch.object(Path,'read_bytes',lambda p: original(p)+b' ' if p.name=='case-management-change.json' else original(p)):
   with self.assertRaisesRegex(ValueError,'R2_PROPOSAL_SUBSTITUTION'):evolution_request(Path(t)/'not-read',Path(t)/'out')
 def test_native_publication_detaches_and_retains_only_external_execution_files(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'source';root.mkdir();(root/'owned').write_text('original');(root/'external').write_text('fixture')
   for n in ('backend/target','frontend/node_modules','frontend/dist'):
    p=root/n;p.mkdir(parents=True);(p/'input').write_text(n)
   out=Path(t)/'outputs';detach_outputs(root,{'owned':'hash'},out);self.assertEqual(tree(root),{'owned':sha(b'original')});self.assertEqual((out/'external/external').read_text(),'fixture');restore_modules(root,out);self.assertTrue((root/'frontend/node_modules/input').is_file())
 def test_output_collisions_are_not_overwritten(self):
  with tempfile.TemporaryDirectory() as t:
   with self.assertRaises(FileExistsError):detach_outputs(Path(t),{},Path(t))
 def test_external_seed_adapter_guards_existing_records_without_weakening_authentication(self):
  source=adapter_source();self.assertIn('REFERENCE_ALREADY_INITIALIZED',source);self.assertIn('ACP_DEMO_AUTH_EVENT',source);self.assertIn('JwtException("TEST_AUTHORITY")',source)
  self.assertLess(source.index('REFERENCE_ALREADY_INITIALIZED'),source.index('flyway.clean()'))
  for endpoint in ('unicode','terminal','revoke'):self.assertNotIn('/__test/'+endpoint,source)
 def test_output_equivalence_preserves_everything_except_cas_state(self):
  from dataclasses import replace
  original=self.plan;artifact=original.artifacts[0]
  changed=replace(original,artifacts=(replace(artifact,intent='NO_OP',expected_digest=artifact.content_digest),*original.artifacts[1:]))
  proof=generated_outputs_equivalent(original,changed);self.assertTrue(proof['generatedOutputsEquivalent']);self.assertNotEqual(proof['originalPublicationPlanDigest'],proof['regenerationPlanDigest'])
  for bad in (replace(artifact,content_digest='changed'),replace(artifact,owner=Owner.HUMAN),replace(artifact,verification=())):
   with self.assertRaisesRegex(ValueError,'OUTPUT_BINDING_CHANGED'):generated_outputs_equivalent(original,replace(original,artifacts=(bad,*original.artifacts[1:])))
 def test_original_row_preservation_rejects_loss_and_mutation(self):
  before={'case':[{'id':'old','value':'kept'}]};original_rows_preserved(before,{'case':before['case']+[{'id':'new','value':'added'}]})
  for bad in ({'case':[]},{'case':[{'id':'old','value':'changed'}]},{}):
   with self.assertRaises(ValueError):original_rows_preserved(before,bad)
 def test_observation_baseline_cannot_rebless_compiler_owned_bytes(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);root=p/'case';store=FilesystemArtifactStore(root);store.apply(self.plan)
   rows={x.path:{'owner':str(x.owner),'sha256':sha((root/x.path).read_bytes()),'contentDigest':x.digest} for x in store.inventory()}
   name='frontend/src/App.vue';rows[name]['sha256']='0'*64
   original=p/'baseline.json';original.write_text(json.dumps({'files':rows}))
   with self.assertRaisesRegex(ValueError,'MANAGED_BASELINE_REPLACEMENT'):extension_baseline(original,root,p/'new-baseline.json')
   self.assertFalse((p/'new-baseline.json').exists())
 def test_frozen_releases_and_core_predicates_are_unchanged(self):
  from target_worker import bundle_digest
  from engineering.generator_candidates.spring_vue_postgres_0_6.candidate import source_digest
  self.assertEqual(bundle_digest(),'ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb');self.assertEqual(source_digest(),'600a552287cc1121be7578c31ba2a379332c9b0d55c60a79b2a5d054c92271aa')
  import subprocess
  for name in ('tooling/audit/criteria.py','tooling/audit/phase6.py'):
   self.assertEqual((ROOT/name).read_bytes(),subprocess.check_output(['git','show','4a3db4ca30dcdc41f598c098f3de02534072035b:'+name],cwd=ROOT))
if __name__=='__main__':unittest.main()
