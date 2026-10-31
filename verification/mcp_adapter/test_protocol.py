"""Real SDK client → subprocess stdio → existing ACP application/model/result ports."""
import asyncio,json,os,subprocess,sys,unittest
from pathlib import Path
from mcp import Client
from mcp.shared.exceptions import MCPError
from mcp.client.stdio import StdioServerParameters
from engineering.mcp_adapter.service import TOOLS,Service,encode,sha
ROOT=Path(__file__).resolve().parents[2]
CONFIG=Path(os.environ['ACP_MCP_HOST_CONFIG']).absolute()

class Protocol(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.client=Client(StdioServerParameters(command=sys.executable,args=['-B','-m','engineering.mcp_adapter.server','--host-config',str(CONFIG)],cwd=str(ROOT)),read_timeout_seconds=45,mode=self.mode if hasattr(self,'mode') else 'auto')
 async def call(self,name,**kw):return await self.client.call_tool(name,{'application':'payment',**kw})
 async def good(self,name,**kw):
  r=await self.call(name,**kw);self.assertFalse(r.is_error,str(r));v=r.structured_content;self.assertEqual(v['schema'],'acp-mcp-tool-result/1');self.assertIsNone(v['error']);return v['payload']
 async def bad(self,name,**kw):
  r=await self.call(name,**kw);self.assertTrue(r.is_error);self.assertNotIn(str(ROOT),str(r));return r
 async def test_discovery_schema_and_negotiation(self):
  self.assertEqual(self.client.protocol_version,'2026-07-28');self.assertIsNotNone(self.client.server_capabilities.tools)
  self.assertEqual({t.name for t in self.tools.tools},set(TOOLS))
  for t in self.tools.tools:
   self.assertTrue(t.annotations.read_only_hint);self.assertFalse(t.annotations.destructive_hint);self.assertFalse(t.input_schema['additionalProperties']);self.assertFalse(t.output_schema['additionalProperties'])
 async def test_both_actual_applications_complete_read_workflow(self):
  measurements={}
  for app in ('payment','case-management'):
   summary=await self.good('project.summary',application=app);self.assertIn('PHASE6_RELEASE_CLOSURE_BLOCKED',summary['restrictions']);self.assertFalse(summary['completeness']['fullyResolved'])
   nodes=await self.good('spec.query',application=app);semantic=nodes['items'][0]['id']
   exact=await self.good('spec.query',application=app,ids=[semantic]);self.assertEqual(exact['items'][0]['id'],semantic)
   await self.good('spec.validate',application=app)
   plan=await self.good('compiler.plan',application=app);self.assertTrue(plan['items'])
   symbols=await self.good('source.symbol',application=app);symbol=symbols['items'][0]['id']
   await self.good('source.symbol',application=app,symbol=symbol)
   await self.good('source.references',application=app,symbol=symbol)
   impact=await self.good('source.impact',application=app,symbol=symbol);self.assertEqual(impact['impact']['authority'],'NO_CHANGE_AUTHORIZATION')
   result=await self.good('compiler.verify',application=app);self.assertGreater(result['verificationSummary']['FAIL'],0);self.assertGreater(result['verificationSummary']['BLOCKED'],0)
   unresolved=await self.good('compiler.verify',application=app,status='NOT_RUN');self.assertTrue(unresolved['items']);self.assertTrue(all(r['result']=='NOT_RUN' for r in unresolved['items']))
   context=await self.good('project.context',application=app,ids=[semantic]);again=await self.good('project.context',application=app,ids=[semantic]);self.assertEqual(context,again);self.assertLessEqual(len(encode(context)),16384)
   cfg=json.loads(CONFIG.read_bytes())['applications'][app]
   application=Service(CONFIG).application(app)
   _,full_rows=application.context_rows({semantic});self.assertEqual(context['total'],len(full_rows))
   full={**context,'items':full_rows,'next':None,'complete':True}
   self.assertLessEqual(len(encode(context)),len(encode(full)))
   measurements[app]={'query':semantic,'boundedResponseUTF8Bytes':len(encode(context)),'equivalentFullResponseUTF8Bytes':len(encode(full)),'fullResponseSHA256':sha(encode(full)),'tokenCount':None,'tokenizer':'UNAVAILABLE_NOT_ESTIMATED','verificationSummary':result['verificationSummary']}

  output=Path(os.environ.get('ACP_MCP_RESULTS',str(CONFIG.parent/'measurements.json')));output.write_bytes(encode(measurements))
 async def test_continuation_determinism_and_binding(self):
  a=await self.good('spec.query',limit=1);self.assertIsNotNone(a['next'])
  b=await self.good('spec.query',limit=1,cursor=a['next']);self.assertNotEqual(a['items'],b['items'])
  await self.bad('spec.query',limit=2,cursor=a['next'])
  await self.bad('compiler.verify',limit=1,cursor=a['next'])
  await self.bad('spec.query',application='case-management',limit=1,cursor=a['next'])
 async def test_negative_identity_path_secret_and_approval_requests(self):
  for tool,args in [
   ('project.summary',{'application':'unknown'}),('spec.query',{'ids':['../../etc/passwd']}),
   ('spec.query',{'ids':['NONEXISTENT']}),('source.symbol',{'symbol':'symbol:missing'}),
   ('project.summary',{'path':'/etc/shadow'}),('compiler.verify',{'evidence':'/etc/passwd'}),
   ('project.context',{'task':'x'*257}),('project.context',{'ids':['REQ-MISSING']}),
   ('project.context',{'budget':1}),('project.summary',{'approve':True}),
   ('spec.validate',{'snapshot':{'approved':True}}),('source.symbol',{'path':'.aws/credentials'}),
   ('compiler.plan',{'command':'cat /etc/shadow'}),('source.references',{}),
   ('source.impact',{}),('spec.query',{'limit':True}),('project.summary',{'schemaVersion':'other'})]:
   with self.subTest(tool=tool,args=args):await self.bad(tool,**args)
 async def test_unsupported_mutations_are_not_discoverable_or_invocable(self):
  for name in ('spec.apply_change','compiler.build','source.patch','release.approve','shell.run'):
   # Modern MCP rejects unknown tool metadata before handler dispatch.
   try:r=await self.call(name)
   except MCPError:continue
   self.assertTrue(r.is_error)
 async def test_stale_source_and_evidence_fail_closed_over_protocol(self):
  cfg=json.loads(CONFIG.read_bytes())['applications']['payment'];root=Path(cfg['root']);model=json.loads(Path(cfg['model']['path']).read_bytes());path=root/model['files'][0]['path'];raw=path.read_bytes()
  try:
   path.write_bytes(raw+b'\n');await self.bad('project.summary');await self.bad('compiler.verify')
  finally:path.write_bytes(raw)
  m=Path(cfg['model']['path']);original=m.read_bytes()
  try:
   m.write_bytes(original+b' ');await self.bad('source.symbol')
  finally:m.write_bytes(original)
  p=Path(cfg['verification']['path']);raw=p.read_bytes()
  try:
   p.write_bytes(raw+b' ');await self.bad('compiler.verify')
  finally:p.write_bytes(raw)
  await self.good('project.summary')
 async def test_client_timeout_cancellation_leaves_server_usable(self):
  # Real request is cancelled at the client; no delayed/mock server operation.
  with self.assertRaises(TimeoutError):
   async with asyncio.timeout(0.000001):await self.call('project.summary')
  await self.good('project.summary')

class Legacy(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):self.mode='legacy';await Protocol.asyncSetUp(self)
 call=Protocol.call
 good=Protocol.good
 async def test_initialization_negotiation_and_invocation(self):
  self.assertIn(self.client.protocol_version,('2025-11-25','2025-06-18','2025-03-26','2024-11-05'));self.assertEqual(len(self.tools.tools),9);await self.good('project.summary')

# AnyIO cancel scopes must enter/exit in the same task. unittest runs setup and
# teardown in different tasks, so own each real SDK connection in the test task.
def connection(method):
 from functools import wraps
 @wraps(method)
 async def run(self):
  async with self.client:
   self.tools=await self.client.list_tools()
   await method(self)
 return run
for case in (Protocol,Legacy):
 for name,method in list(case.__dict__.items()):
  if name.startswith('test_'):setattr(case,name,connection(method))
del case,name,method

class Transport(unittest.TestCase):
 def test_oversized_raw_frame_connection_is_rejected(self):
  proc=subprocess.run([sys.executable,'-B','-m','engineering.mcp_adapter.server','--host-config',str(CONFIG)],input=b'x'*65537+b'\n',capture_output=True,timeout=45,cwd=ROOT)
  self.assertEqual(proc.returncode,2);self.assertNotIn(str(ROOT).encode(),proc.stdout+proc.stderr)
 def test_malformed_json_never_invokes_tool(self):
  proc=subprocess.run([sys.executable,'-B','-m','engineering.mcp_adapter.server','--host-config',str(CONFIG)],input=b'{invalid json}\n',capture_output=True,timeout=45,cwd=ROOT)
  self.assertNotIn(b'canonicalDigest',proc.stdout);self.assertNotIn(str(ROOT).encode(),proc.stdout)

if __name__=='__main__':unittest.main()
