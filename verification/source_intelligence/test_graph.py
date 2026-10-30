"""Real generated applications; native compilers, original provenance and ownership."""
import copy,json,os,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from engineering.source_intelligence.analysis import analyze,binding
from engineering.source_intelligence.model import *

class GraphTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.base=Path(os.environ['ACP_SOURCE_APPLICATIONS']);cls.maven=Path(os.environ['ACP_SOURCE_MAVEN_REPO']);cls.modules=Path(os.environ['ACP_SOURCE_NODE_MODULES']);cls.models={}
  for domain in ('payment','case-management'):
   cls.models[domain]=cls.analyze(domain)
   (cls.base/domain/'source-model.json').write_bytes(encode(cls.models[domain]))
 @classmethod
 def analyze(cls,domain):
  w=cls.base/domain
  return analyze(w/domain,w/'source-baseline.json',(w/'source-baseline.sha256').read_text().strip(),maven_repo=cls.maven,node_modules=cls.modules)
 def root(self,domain='payment'):return self.base/domain/domain
 def mutation(self,name,change,assertion):
  p=self.root()/name;original=p.read_bytes() if p.exists() else None
  try:
   replacement=change(original)
   if replacement is None:p.unlink()
   else:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(replacement)
   assertion(self.analyze('payment'))
  finally:
   if original is None:p.unlink(missing_ok=True)
   else:p.write_bytes(original)
 def test_both_native_graphs_and_exact_semantic_carriers(self):
  for domain,m in self.models.items():
   with self.subTest(domain=domain):
    self.assertFalse(m['drift']);self.assertEqual({t['language'] for t in m['completeness']['nativeTools']},{'JAVA','TYPESCRIPT'})
    self.assertTrue(m['symbols'] and m['references'] and m['typeRelations'])
    self.assertEqual({next(s['language'] for s in m['symbols'] if s['id']==r['symbol']) for r in m['semanticMappings']},{'JAVA','TYPESCRIPT'})
    self.assertTrue(all(r['relationship']=='EMBEDS_SEMANTIC_ID' for r in m['semanticMappings']))
    self.assertTrue(any(r['locationConfidence']=='ARTIFACT_ONLY' for r in m['artifactMappings']))
    self.assertFalse(m['completeness']['fullyResolved']);self.assertTrue(m['completeness']['unsupportedFiles'])
    selected=impact(m,self.root(domain),semantic='UC-TASK');self.assertTrue(selected['seeds']);self.assertEqual(selected['authority'],'NO_CHANGE_AUTHORIZATION')
 def test_repeated_models_are_identical_and_analysis_is_read_only(self):
  for domain,m in self.models.items():
   root=self.root(domain);before={p.relative_to(root).as_posix():sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
   self.assertEqual(encode(m),encode(self.analyze(domain)))
   self.assertEqual(before,{p.relative_to(root).as_posix():sha(p.read_bytes()) for p in root.rglob('*') if p.is_file()})
 def test_generated_references_to_human_extension_are_real(self):
  for m in self.models.values():
   by={s['id']:s for s in m['symbols']};human={s['id'] for s in m['symbols'] if s['ownership']=='HUMAN_OWNED'}
   self.assertTrue(human)
   self.assertTrue(any(r['to'] in human and r['from'] in by and by[r['from']]['ownership']=='COMPILER_OWNED' and r['confidence']=='KNOWN' for r in m['references']))
 def test_genuine_rename_impact_on_both_generated_applications(self):
  for domain,m in self.models.items():
   root=self.root(domain);s=next(s for s in m['symbols'] if s['name']=='accessToken' and s['ownership']=='HUMAN_OWNED' and s['kind']=='FUNCTION')
   result=impact(m,root,symbol=s['id']);self.assertTrue(any(r['kind']=='CALL' and r['location']['file']=='frontend/src/api.ts' for r in result['provenDependencies']))
   # Rename declaration and all actual native identifier references in disposable source.
   positions=[s['nameLocation']]+[r['location'] for r in m['references'] if r['to']==s['id'] and r['kind'] in ('REFERENCE','IMPORT') and (root/r['location']['file']).read_bytes()[r['location']['byteStart']:r['location']['byteEnd']]==b'accessToken']
   grouped={}
   for loc in positions:grouped.setdefault(loc['file'],set()).add((loc['byteStart'],loc['byteEnd']))
   originals={name:(root/name).read_bytes() for name in grouped}
   try:
    for name,spans in grouped.items():
     raw=originals[name]
     for start,end in sorted(spans,reverse=True):
      self.assertEqual(raw[start:end],b'accessToken');raw=raw[:start]+b'accessTokenRenamed'+raw[end:]
     (root/name).write_bytes(raw)
    after=self.analyze(domain);delta=compare(m,after)
    self.assertGreater(delta['nativeDefinitionsAdded'],0);self.assertTrue(delta['invalidatedLocations']);self.assertEqual(delta['semanticChange'],'UNKNOWN')
    renamed=next(s for s in after['symbols'] if s['name']=='accessTokenRenamed' and s['kind']=='FUNCTION')
    self.assertTrue(any(r['to']==renamed['id'] and r['kind']=='CALL' and r['location']['file']=='frontend/src/api.ts' for r in after['references']))
    self.assertEqual(after['completeness']['unresolvedRelationships'],m['completeness']['unresolvedRelationships'])
    self.assertTrue(any(d['code']=='HUMAN_EXTENSION_CHANGED' for d in after['drift']))
    with self.assertRaisesRegex(ValueError,'STALE_SOURCE_MODEL'):impact(m,root,symbol=s['id'])
   finally:
    for name,raw in originals.items():(root/name).write_bytes(raw)
 def test_formatting_drift_does_not_invent_semantic_change(self):
  name=next(f['path'] for f in self.models['payment']['files'] if f['path'].endswith('Contracts.java'))
  def check(m):
   delta=compare(self.models['payment'],m);self.assertEqual(delta['semanticChange'],'UNKNOWN');self.assertEqual(delta['nativeDefinitionsAdded']+delta['nativeDefinitionsRemoved']+delta['nativeRelationsAdded']+delta['nativeRelationsRemoved'],0)
   self.assertTrue(any(d['file']==name and d['code']=='MODIFIED_GENERATED_FILE' for d in m['drift']))
   self.assertFalse(any(r['literalLocation']['file']==name for r in m['semanticMappings']))
  self.mutation(name,lambda raw:b'\n'+raw,check)
 def test_missing_source_is_explicit_incomplete_drift(self):
  self.mutation('frontend/src/extensions/identity.ts',lambda _:None,lambda m:self.assertTrue(any(d['code']=='MISSING_GENERATED_FILE' for d in m['drift']) and not m['completeness']['fullyResolved']))
 def test_stale_or_forged_provenance_cannot_promote_symbols(self):
  def change(raw):
   v=json.loads(raw);v['forged']='unapproved';return encode(v)
  self.mutation('acp/provenance.json',change,lambda m:self.assertTrue(not m['semanticMappings'] and any(d['code']=='STALE_OR_FORGED_PROVENANCE' for d in m['drift'])))
 def test_conflicting_ownership_is_unknown(self):
  name='frontend/src/extensions/identity.ts'
  def change(raw):
   v=json.loads(raw);v[name]['owner']='COMPILER_OWNED';return encode(v)
  self.mutation('.acp-store.json',change,lambda m:self.assertTrue(any(d['code']=='OWNERSHIP_CONFLICT' and d['file']==name for d in m['drift']) and all(s['ownership']=='UNKNOWN' for s in m['symbols'] if s['location']['file']==name)))
 def test_missing_ownership_is_reported(self):
  def change(raw):
   v=json.loads(raw);del v['frontend/src/extensions/identity.ts'];return encode(v)
  self.mutation('.acp-store.json',change,lambda m:self.assertTrue(any(d['code']=='MISSING_OWNERSHIP' for d in m['drift'])))
 def test_new_unknown_source_and_unresolved_reference(self):
  self.mutation('frontend/src/unregistered.ts',lambda _:b'export const unknown=missingSymbol();\n',lambda m:self.assertTrue(any(d['code']=='UNEXPECTED_SOURCE' for d in m['drift']) and any(r['confidence']=='UNRESOLVED' for r in m['references']) and not m['completeness']['fullyResolved']))
 def test_forged_baseline_mapping_is_rejected_even_with_recomputed_pin(self):
  w=self.base/'payment';original=(w/'source-baseline.json').read_bytes();value=json.loads(original);next(f for f in value['files'].values() if f['origins'])['origins'][0]['revision']+=1
  temp=w/'forged-baseline.json'
  try:
   temp.write_bytes(encode(value))
   with self.assertRaisesRegex(ValueError,'FORGED_SEMANTIC_MAPPING'):binding(temp,sha(temp.read_bytes()))
   with self.assertRaisesRegex(ValueError,'BASELINE_DIGEST'):binding(temp,sha(original))
  finally:temp.unlink(missing_ok=True)
 def test_mutated_model_source_hash_and_forged_reference_fail_closed(self):
  for kind in ('source','reference','complete'):
   m=copy.deepcopy(self.models['payment'])
   if kind=='source':m['symbols'][0]['sourceHash']='0'*64
   elif kind=='reference':next(r for r in m['references'] if r['confidence']=='KNOWN')['to']='invented'
   else:m['completeness']['fullyResolved']=True
   m=sealed({k:v for k,v in m.items() if k!='digest'})
   with self.subTest(kind=kind),self.assertRaises(ValueError):validate(m)
 def test_analysis_configuration_change_invalidates_impact(self):
  p=self.root()/'frontend/tsconfig.json';raw=p.read_bytes()
  try:
   p.write_bytes(raw+b'\n')
   with self.assertRaisesRegex(ValueError,'STALE_ANALYSIS_CONFIGURATION'):impact(self.models['payment'],self.root(),semantic='UC-TASK')
  finally:p.write_bytes(raw)
 def test_path_and_file_bounds_reject_symlink(self):
  p=self.root()/'frontend/src/untrusted.ts';p.symlink_to('/etc/passwd')
  try:
   with self.assertRaisesRegex(ValueError,'SOURCE_SYMLINK'):sources(self.root())
  finally:p.unlink()

 def test_forged_inventory_content_digest_is_not_trusted(self):
  def change(raw):
   v=json.loads(raw);v['frontend/src/extensions/identity.ts']['digest']='sha256:'+'0'*64;return encode(v)
  self.mutation('.acp-store.json',change,lambda m:self.assertTrue(any(d['code']=='OWNERSHIP_RECORD_CONFLICT' for d in m['drift']) and all(s['ownership']=='UNKNOWN' for s in m['symbols'] if s['location']['file']=='frontend/src/extensions/identity.ts')))
 def test_existing_source_analyzer_port_returns_the_same_bound_model(self):
  from compiler_contracts import Document
  from engineering.source_intelligence.analysis import NativeSourceAnalyzer
  w=self.base/'payment';adapter=NativeSourceAnalyzer(self.root(),w/'source-baseline.json',(w/'source-baseline.sha256').read_text().strip(),self.maven,self.modules,w/'port-model.json')
  source=Document.of({'schema':'acp-source-input/1','bindingDigest':adapter.baseline_sha256,'files':sources(self.root())})
  try:
   result=adapter.analyze(source,Document.of({'schema':'acp-source-query/1','operation':'MODEL'}))
   self.assertEqual(result.read()['modelDigest'],self.models['payment']['digest'])
   self.assertEqual(result.read()['modelFileSHA256'],sha(adapter.output.read_bytes()))
   self.assertEqual(json.loads(adapter.output.read_bytes()),self.models['payment'])
  finally:adapter.output.unlink(missing_ok=True)
 def test_port_rejects_client_context_changes_and_unsupported_queries(self):
  from compiler_contracts import Document
  from engineering.source_intelligence.analysis import NativeSourceAnalyzer
  from dataclasses import FrozenInstanceError
  w=self.base/'payment';adapter=NativeSourceAnalyzer(self.root(),w/'source-baseline.json',(w/'source-baseline.sha256').read_text().strip(),self.maven,self.modules,w/'port-model.json')
  source=Document.of({'schema':'acp-source-input/1','bindingDigest':adapter.baseline_sha256,'files':sources(self.root())})
  with self.assertRaises(FrozenInstanceError):adapter.root=Path('/untrusted')
  with self.assertRaisesRegex(ValueError,'UNSUPPORTED_SOURCE_QUERY'):adapter.analyze(source,Document.of({'schema':'acp-source-query/1','operation':'REWRITE'}))
  with self.assertRaisesRegex(ValueError,'PORT_SOURCE_BINDING'):adapter.analyze(Document.of({}),Document.of({'schema':'acp-source-query/1','operation':'MODEL'}))
