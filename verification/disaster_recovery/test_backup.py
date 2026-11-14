"""Synthetic file/capability regressions; actual PG evidence is separate."""
from dataclasses import replace,FrozenInstanceError
from pathlib import Path
from unittest.mock import patch
import json,tempfile,unittest
from engineering.disaster_recovery import backup as b
from engineering.disaster_recovery.run import PUBLIC,public_paths
from engineering.source_intelligence.model import sha,encode
class Backups(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='h7-unit-');self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.directory=self.root/'backup';self.directory.mkdir();dump=b'PGDMP synthetic unit bytes';toc=b'; synthetic unit TOC';(self.directory/'database.dump').write_bytes(dump);(self.directory/'objects.list').write_bytes(toc)
  manifest={'schema':'acp-lab-logical-backup/1','scope':'QUALIFICATION_ONLY','type':'PG_DUMP_CUSTOM_EXPORTED_SNAPSHOT','dumpSHA256':sha(dump),'objectsSHA256':sha(toc),'size':len(dump),'boundary':{'snapshot':'00000001-00000002-1'},'source':{'systemIdentifier':'synthetic-unit-only'}};raw=encode(manifest);(self.directory/'manifest.json').write_bytes(raw)
  self.backup=b.Backup(self.directory,sha(dump),sha(raw),sha(toc),len(dump),manifest['boundary']['snapshot'],'synthetic-unit-only')
 def test_valid_hash_bound_components(self):self.assertEqual(b.verify(self.backup)['scope'],'QUALIFICATION_ONLY')
 def test_dump_corruption(self):
  (self.directory/'database.dump').write_bytes(b'corrupt')
  with self.assertRaisesRegex(ValueError,'SUBSTITUTION'):b.verify(self.backup)
 def test_substituted_manifest(self):
  (self.directory/'manifest.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'SUBSTITUTION'):b.verify(self.backup)
 def test_substituted_toc(self):
  (self.directory/'objects.list').write_bytes(b'wrong')
  with self.assertRaisesRegex(ValueError,'SUBSTITUTION'):b.verify(self.backup)
 def test_missing_dump(self):
  (self.directory/'database.dump').unlink()
  with self.assertRaisesRegex(ValueError,'COMPONENT'):b.verify(self.backup)
 def test_missing_manifest(self):
  (self.directory/'manifest.json').unlink()
  with self.assertRaisesRegex(ValueError,'COMPONENT'):b.verify(self.backup)
 def test_missing_toc(self):
  (self.directory/'objects.list').unlink()
  with self.assertRaisesRegex(ValueError,'COMPONENT'):b.verify(self.backup)
 def test_symlink_component(self):
  p=self.directory/'database.dump';p.unlink();p.symlink_to(self.directory/'objects.list')
  with self.assertRaisesRegex(ValueError,'COMPONENT'):b.verify(self.backup)
 def test_symlink_directory(self):
  link=self.root/'linked';link.symlink_to(self.directory,target_is_directory=True)
  with self.assertRaisesRegex(ValueError,'DIRECTORY'):b.verify(replace(self.backup,directory=link))
 def test_incomplete_size(self):
  with self.assertRaisesRegex(ValueError,'INCOMPLETE'):b.verify(replace(self.backup,size=0))
 def test_backup_binding_is_immutable(self):
  with self.assertRaises(FrozenInstanceError):self.backup.digest='0'*64
 def test_fake_target_has_no_live_capability(self):
  with self.assertRaisesRegex(ValueError,'RESTORE_TARGET'):b.target_guard(b.Target('acp-06-runtime-h2-'+'0'*24,'0'*24,'synthetic'))
 def target(self):
  t=b.Target('acp-06-runtime-h2-'+'1'*24,'1'*24,'synthetic');return t
 def test_wrong_owner_rejected(self):
  t=self.target()
  with patch.dict(b._LIVE,{t.container:t.owner}),patch.object(b,'_TARGET_CAPABILITIES',{id(t)}),patch.object(b,'docker',return_value='other'):
   with self.assertRaisesRegex(ValueError,'OWNER'):b.target_guard(t)
 def test_wrong_database_identity(self):
  t=self.target()
  with patch.dict(b._LIVE,{t.container:t.owner}),patch.object(b,'_TARGET_CAPABILITIES',{id(t)}),patch.object(b,'docker',return_value=t.owner),patch.object(b,'identity',return_value={'systemIdentifier':'other'}):
   with self.assertRaisesRegex(ValueError,'IDENTITY'):b.target_guard(t)
 def test_nonempty_target_rejected(self):
  t=self.target()
  with patch.dict(b._LIVE,{t.container:t.owner}),patch.object(b,'_TARGET_CAPABILITIES',{id(t)}),patch.object(b,'docker',return_value=t.owner),patch.object(b,'identity',return_value={'systemIdentifier':t.system}),patch.object(b,'sql',return_value=1):
   with self.assertRaisesRegex(ValueError,'NOT_EMPTY'):b.target_guard(t)
 def test_no_unverified_startup(self):
  with patch.object(b,'target_guard'):
   with self.assertRaisesRegex(ValueError,'NOT_VERIFIED'):b.admit_application(self.backup,self.target())
 def test_changed_state_cannot_activate(self):
  t=self.target()
  with patch.object(b,'target_guard'),patch.dict(b._VERIFIED_TARGETS,{id(t):(self.backup.digest,'0'*64)}),patch.object(b,'state',return_value={'changed':[]}):
   with self.assertRaisesRegex(ValueError,'CHANGED_BEFORE'):b.admit_application(self.backup,t)
 def test_public_missing_evidence(self):
  with self.assertRaisesRegex(ValueError,'MISSING_OR_ESCAPE'):public_paths(self.root)
 def public(self):
  for name in PUBLIC:p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}')
 def test_public_does_not_export_backups_or_sql(self):
  self.public();(self.root/'database.dump').write_bytes(b'secret backup');(self.root/'database.sql').write_text('private SQL');selected={p.relative_to(self.root).as_posix() for p in public_paths(self.root)};self.assertEqual(selected,set(PUBLIC));self.assertNotIn('database.dump',selected)
 def test_public_symlink_rejected(self):
  self.public();p=self.root/PUBLIC[0];p.unlink();p.symlink_to(self.root/PUBLIC[1])
  with self.assertRaisesRegex(ValueError,'MISSING_OR_ESCAPE'):public_paths(self.root)
