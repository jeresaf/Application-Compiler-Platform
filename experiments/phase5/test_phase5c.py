"""Final unknown-gate tests, not repetition of Phase 5B performance evidence."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import copy,json,sys,time,unittest
from pathlib import Path
from threading import Event,Timer
AREA=Path(__file__).resolve().parent
sys.path.insert(0,str(AREA))
from run import ROOT,canonical_bytes
sys.path.insert(0,str(ROOT/"tooling/tests"))
from native_frontend import NativeFrontend,client,native_command
from frontend_worker import PROTOCOL,WireFailure,Client
from compiler_contracts import Source,Document,Stage,Success,Failure,fingerprint,wire
from compiler_core import execute,compile_pipeline
from canonical_fixtures import synthetic_approved
from canonical_ir import normalize_candidate
from generate import encode
from test_phase5b import source_context
from source_tokens import syntax_diagnostics

CANDIDATES=('antlr','langium','xtext')
def record(name,candidate,result):
    target=AREA/'results/phase5c/diagnostics.json';target.parent.mkdir(exist_ok=True)
    data=json.loads(target.read_text()) if target.exists() else {}
    data.setdefault(candidate,{})[name]=wire(result)
    target.write_text(json.dumps(data,indent=2)+'\n')

def model(domain='payment'):return synthetic_approved(json.loads((ROOT/f'test-corpus/phase1/{domain}.json').read_text()))
def source(candidate,m):return source_context(candidate,m)
def request(candidate,m,identity='request'):
    s,ctx=source(candidate,m);return {'protocol':PROTOCOL,'frontend':ctx.frontend.identity,'id':identity,'source':s.document.read()}

class NativeIsolationTests(unittest.TestCase):
    def test_native_runtime_stays_alive_and_independent_requests_are_deterministic(self):
        for candidate in CANDIDATES:
            with client(candidate) as worker:
                a=worker.call(request(candidate,model(),'a'));b=worker.call(request(candidate,model(),'b'))
                self.assertEqual(a['payload']['documents'],b['payload']['documents'])
                self.assertEqual(worker.process.pid,a['payload']['metrics']['pid'])
                self.assertEqual(a['payload']['metrics']['pid'],b['payload']['metrics']['pid'])
                self.assertEqual(2,b['payload']['metrics']['sequence'])
            def task(domain):
                m=model(domain)
                with client(candidate) as worker:
                    r=worker.call(request(candidate,m,domain));actual=r['payload']['documents'][0]['output']['model']
                    return domain,normalize_candidate(actual)['contentDigest']
            for domains in (['payment','payment'],['payment','case-management']):
                with ThreadPoolExecutor(max_workers=2) as pool:values=list(pool.map(task,domains))
                self.assertEqual([(d,normalize_candidate(model(d))['contentDigest']) for d in domains],values)

    def test_real_crash_restart_retry_cancel_versions_duplicate_and_oversize(self):
        for candidate in CANDIDATES:
            r=request(candidate,model())
            with client(candidate) as worker:
                expected=worker.call(r)['payload']['documents']
                with self.assertRaisesRegex(WireFailure,'DUPLICATE_ID'):worker.call(r)
                worker.process.kill()
                with self.assertRaisesRegex(WireFailure,'CRASH'):worker.call({**r,'id':'crash'})
            with client(candidate) as restarted:self.assertEqual(expected,restarted.call(r)['payload']['documents'])
            with client(candidate) as worker,self.assertRaisesRegex(WireFailure,'PROTOCOL_VERSION'):worker.call({**r,'protocol':'other/2'})
            # Warm native runtime, then cancel an oversized-output parse workload
            # while the supervisor is actively servicing the request.
            with client(candidate) as worker:
                worker.call(r);raw=copy.deepcopy(r);raw['id']='active';raw['source']['documents'][0]['text']='application {};\n'+''.join(f'Entity "ENT-{i}" @ 1 {{"name":"Entity {i}"}};\n' for i in range(12000))
                event=Event();timer=Timer(.03,event.set)
                with self.assertRaisesRegex(WireFailure,'CANCELLED'):worker.call(raw,cancelled=event,on_sent=timer.start)
                timer.join()
            with client(candidate) as retry:self.assertEqual(expected,retry.call(r)['payload']['documents'])

    def test_native_oversized_output_server_duplicate_and_cancellation_race(self):
        for candidate in CANDIDATES:
            r=request(candidate,model())
            with client(candidate) as worker:
                worker.call(r);worker.seen.clear()
                with self.assertRaisesRegex(WireFailure,'DUPLICATE_ID'):worker.call(r)
            raw=copy.deepcopy(r);raw['source']['documents'][0]['text']='application {};\n'+''.join(f'Entity "ENT-{i}" @ 1 {{"name":"Entity {i}"}};\n' for i in range(12000))
            with client(candidate) as worker,self.assertRaisesRegex(WireFailure,'RESPONSE_SIZE'):worker.call(raw,timeout=90)
            raw['source']['documents'][0]['text']='x'*(1048577)
            with client(candidate) as worker,self.assertRaisesRegex(WireFailure,'INPUT_SIZE'):worker.call(raw)
            for delay in (0,.001):
                with client(candidate) as worker:
                    worker.call(r);r['id']=f'race-{delay}';event=Event();timer=Timer(delay,event.set)
                    try:
                        result=worker.call(r,cancelled=event,on_sent=timer.start);self.assertEqual('SUCCESS',result['status'])
                    except WireFailure as error:self.assertEqual('CANCELLED',str(error))
                    finally:timer.join()

    def test_full_pipeline_concurrency_and_queued_restart(self):
        for candidate in CANDIDATES:
            def compile_task(domain):
                m=model(domain);s,ctx=source(candidate,m)
                with client(candidate) as worker:
                    port=NativeFrontend(candidate,worker);result=compile_pipeline(s,replace(ctx,frontend=port))
                    self.assertIsInstance(result.result,Success,result.result)
                    return result.result.output_digest
            # Independent full pipelines share no parser objects or authority state.
            expected={d:compile_task(d) for d in ('payment','case-management')}
            with ThreadPoolExecutor(max_workers=2) as pool:
                actual=list(pool.map(compile_task,['payment','payment','case-management']))
            self.assertEqual([expected['payment'],expected['payment'],expected['case-management']],actual)
            with client(candidate) as worker:
                worker.call(request(candidate,model(),'warm'))
                def crash():
                    worker.process.kill()
                    with self.assertRaisesRegex(WireFailure,'CRASH'):worker.call(request(candidate,model(),'crash'))
                    return 'discarded'
                def queued_retry():
                    with client(candidate) as restarted:return restarted.call(request(candidate,model(),'retry'))['payload']['documents'][0]['output']['model']
                with ThreadPoolExecutor(max_workers=1) as pool:
                    first=pool.submit(crash);second=pool.submit(queued_retry)
                    self.assertEqual('discarded',first.result());self.assertEqual(model(),second.result())

    def test_real_native_response_transport_corruption(self):
        for candidate in CANDIDATES:
            for mode,code in [('malformed','MALFORMED_RESPONSE'),('oversize','RESPONSE_SIZE'),('stale','STALE_RESPONSE')]:
                command=[sys.executable,str(AREA/'native_fault_proxy.py'),candidate,mode]
                with Client(candidate,command=command) as worker,self.assertRaisesRegex(WireFailure,code):worker.call(request(candidate,model()))

class FailureDiagnosticTests(unittest.TestCase):
    def test_exact_syntax_and_semantic_tokens_transport_as_failure(self):
        from test_contracts import apply_edits
        cases=json.loads((ROOT/'test-corpus/semantic/cases.json').read_text())
        expected={}
        for candidate in CANDIDATES:
            good=model();s,ctx=source(candidate,good)
            with client(candidate) as worker:
                port=NativeFrontend(candidate,worker);ctx=replace(ctx,frontend=port)
                for name,text in [('malformed','application ???'),('incomplete',encode(good)[:-3])]:
                    raw=s.document.read();raw['documents'][0]['text']=text;bad=Source(Document.of(raw));context=replace(ctx,request=replace(ctx.request,source_digest=fingerprint(bad,'source')))
                    result=execute(Stage.INGEST,bad,context);self.assertIsInstance(result,Failure,result);self.assertFalse(hasattr(result,'output'))
                    self.assertTrue(all(d.location_confidence in {'TOKEN','END_OF_INPUT','UNRECOVERABLE'} for d in result.diagnostics))
                    self.assertTrue(any(d.location is not None for d in result.diagnostics),result);record(name,candidate,result)
                for name in ('missing-reference','stale-reference','ambiguous-transition'):
                    case=next(c for c in cases if c['name']==name);m=copy.deepcopy(good);apply_edits(m,case['edits']);m=synthetic_approved(m)
                    if name in {'missing-reference','stale-reference'}:next(n for n in m['nodes'] if n['id']=='FLD-AMOUNT')['name']='😀 Amount'
                    raw=s.document.read();raw['documents'][0]['text']=encode(m);bad=Source(Document.of(raw));context=replace(ctx,request=replace(ctx.request,source_digest=fingerprint(bad,'source')))
                    parsed=execute(Stage.INGEST,bad,context);self.assertIsInstance(parsed,Success,parsed)
                    ast=execute(Stage.ELABORATE,parsed.output,context);self.assertIsInstance(ast,Success,ast)
                    result=execute(Stage.ANALYZE,ast.output,context);self.assertIsInstance(result,Failure,result)
                    self.assertTrue(all(d.subjects and d.location and d.location_confidence=='TOKEN' for d in result.diagnostics),result)
                    for diagnostic in result.diagnostics:
                        line,column=map(int,diagnostic.location.split('#L')[1].split('C'))
                        actual_token=raw['documents'][0]['text'].splitlines()[line-1][column-1:]
                        self.assertTrue(actual_token.startswith('2' if name=='stale-reference' else '"ENT-MISSING"' if name=='missing-reference' else '"CMD-RECORD"'),(name,diagnostic.location,actual_token[:32]))
                    record(name,candidate,result)
                    projected=[(d.code,d.subjects,d.location,d.related,d.related_locations,d.location_confidence) for d in result.diagnostics]
                    expected.setdefault(name,projected);self.assertEqual(expected[name],projected)
                    if name=='stale-reference':self.assertTrue(any(d.related and d.related_locations for d in result.diagnostics))
    def test_ambiguous_import_failure_transport_has_related_semantic_ids(self):
        import test_phase5b as previous
        expected=None
        for candidate in CANDIDATES:
            project=previous.ModulePolicyTests().project();previous.ModulePolicyTests.ambiguous_import(project);documents=[]
            for path,o in project:
                text='module '+json.dumps(o['module'])+';\n'+''.join('import '+json.dumps(x)+';\n' for x in o['imports'])+encode(o['model'])
                if o['exports']:text=text.replace('\nEntity ','\nexport Entity ')
                documents.append({'path':path,'text':text})
            _,ctx=source(candidate,model())
            with client(candidate) as worker:
                port=NativeFrontend(candidate,worker);bad=Source(Document.of({'version':'acp-text/1','frontend':port.identity,'documents':documents}))
                context=replace(ctx,frontend=port,request=replace(ctx.request,source_digest=fingerprint(bad,'source')))
                result=execute(Stage.INGEST,bad,context);self.assertIsInstance(result,Failure,result)
                d=result.diagnostics[0];self.assertEqual('ACP-MODULE-AMBIGUOUS_IMPORT',d.code);self.assertEqual(('ENT-B',),tuple(s.id for s in d.subjects));self.assertEqual({'ENT-A','ENT-C'},{s.id for s in d.related});self.assertEqual(2,len(d.related_locations));self.assertEqual('TOKEN',d.location_confidence)
                record('ambiguous-import',candidate,result)
                projection=(d.code,d.location,d.related,d.related_locations)
                if expected is None:expected=projection
                else:self.assertEqual(expected,projection)

    def test_module_and_permission_related_tokens_and_safe_unrecoverable(self):
        for candidate in CANDIDATES:
            good=model();s,ctx=source(candidate,good)
            with client(candidate) as worker:
                port=NativeFrontend(candidate,worker);ctx=replace(ctx,frontend=port)
                raw=s.document.read();raw['documents'][0]['text']='module "main";\nimport "missing";\n'+encode(good)
                bad=Source(Document.of(raw));context=replace(ctx,request=replace(ctx.request,source_digest=fingerprint(bad,'source')))
                result=execute(Stage.INGEST,bad,context);self.assertIsInstance(result,Failure,result);self.assertEqual('domain.acp#L2C8',result.diagnostics[0].location);record('missing-module',candidate,result)
                wrong=copy.deepcopy(good);next(n for n in wrong['nodes'] if n['id']=='POL-TENANT')['data']['permission']={'id':'PERM-QUERY-TASKS','revision':1}
                raw=s.document.read();raw['documents'][0]['text']=encode(wrong);bad=Source(Document.of(raw));context=replace(ctx,request=replace(ctx.request,source_digest=fingerprint(bad,'source')))
                parsed=execute(Stage.INGEST,bad,context);ast=execute(Stage.ELABORATE,parsed.output,context);result=execute(Stage.ANALYZE,ast.output,context)
                self.assertIsInstance(result,Failure,result);self.assertTrue(any(d.related and d.related_locations and d.location_confidence=='TOKEN' for d in result.diagnostics));record('permission-conflict',candidate,result)
        unknown=syntax_diagnostics('antlr',{'path':'source.acp','text':'?'},[{}])[0]
        self.assertIsNone(unknown.location);self.assertEqual('UNRECOVERABLE',unknown.confidence)

if __name__=='__main__':unittest.main()
