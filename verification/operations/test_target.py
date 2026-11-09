import json,os,unittest
from pathlib import Path
from unittest.mock import patch
from canonical_json import canonical_bytes
from compiler_contracts import Resources
from engineering.operations.target import OperationalTarget,source_digest
from engineering.identity.target import IdentityTarget
class TargetTests(unittest.TestCase):
 def test_parent_identity_is_unchanged(self):self.assertEqual(IdentityTarget().bundle,'c2f712a0411b1b75aec39ea47c43d28c4ea484a68496b5b4d695588c927e9615')
 def test_h6_identity_and_authority_boundary(self):
  t=OperationalTarget();d=t.descriptor();self.assertEqual(t.bundle,source_digest());self.assertNotEqual(t.generator,IdentityTarget().generator);self.assertEqual(d['scope'],'QUALIFICATION_ONLY');self.assertEqual(d['operationalApproval'],'NOT_APPROVED')
 def test_mutated_source_is_rejected(self):
  t=OperationalTarget()
  with patch('engineering.operations.target.source_digest',return_value='0'*64):
   with self.assertRaisesRegex(ValueError,'H6_SOURCE_CHANGED'):t._verify()
 def plan(self):return json.loads(Path(os.environ.get('ACP_H6_PLAN','.audit-artifacts/phase11-h6-20261108/generation-current/artifact-plan.json')).read_bytes())
 def test_default_output_limit_is_retained(self):
  self.assertEqual(Resources().output_bytes,1048576);self.assertLessEqual(len(canonical_bytes(self.plan())),Resources().output_bytes)
 def test_precise_pointer_origins_retain_complete_runtime_mapping(self):
  plan=self.plan();rows={a['path']:a for a in plan['artifacts']};model=json.loads(rows['backend/src/main/resources/acp-model.json']['content']['text']);nodes={n['id'] for n in model['nodes']};decisions={n['id'] for n in model['nodes'] if n['kind']=='Decision'}
  self.assertEqual({m['id'] for m in rows['backend/src/main/resources/acp-model.json']['mappings']},nodes)
  for n in ('contracts/target-ir.json','frontend/src/model.ts'):self.assertEqual({m['id'] for m in rows[n]['mappings']},decisions)
