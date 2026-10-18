"""Real native plans/stores; synthetic report fixtures test rejection only."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT),str(ROOT/'tooling')]
from engineering.traceability.qualification import (inputs, ownership_matrix, manifest, verify_manifest,
    instrument, runtime_links, STEPS, FilesystemArtifactStore, Owner, live_ownership)
from tooling.task_ui_browser import tests as browser_tests


class IntegratedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {d: inputs(d) for d in ('payment','case-management')}

    def test_integratedCrossOwnerTransitions(self):
        for domain, (_,_,_,plan) in self.cases.items():
            with self.subTest(domain=domain), tempfile.TemporaryDirectory() as temp:
                result = ownership_matrix(Path(temp)/'matrix', plan.artifacts[0])
                self.assertEqual(len(result['transitions']),16)
                self.assertEqual(sum(r[2]=='AUTHORIZED_EXACT_CAS' for r in result['transitions']),3)
                self.assertEqual(sum(r[2]=='REJECTED_UNCHANGED' for r in result['transitions']),13)

    def test_everyTargetObjectHasExactRevisionAndInputDigest(self):
        for domain,(candidate,snapshot,request,plan) in self.cases.items():
            with self.subTest(domain=domain), tempfile.TemporaryDirectory() as temp:
                root=Path(temp)/'application';store=FilesystemArtifactStore(root);store.apply(plan)
                human='frontend/src/extensions/identity.ts';store.adopt_human(human)
                from compiler_core import _ownership
                active=_ownership(candidate.plan(snapshot,request,inventory=store.inventory()),store.inventory())
                store.apply(active)
                live=live_ownership(root,plan)
                self.assertEqual(live['rejectedWithoutPublication'],9)
                self.assertEqual(live['compilerCASPublications'],2)
                (root/human).write_bytes(b'// HUMAN authorized test extension\n')
                expected=manifest(root,candidate,snapshot,request,plan,human_paths=(human,))
                verify_manifest(copy.deepcopy(expected),expected)
                human_row=next(r for r in expected['artifacts'] if r['artifact']==human)
                self.assertEqual(human_row['owner'],str(Owner.HUMAN))
                self.assertTrue(human_row['origins']);self.assertTrue(human_row['inputs'])
                for mutation in ('missing','extra','revision','owner','input','bytes','snapshot','generator','human-missing','human-forged'):
                    bad=copy.deepcopy(expected);row=bad['artifacts'][0]
                    if mutation=='missing':bad['artifacts'].pop()
                    elif mutation=='extra':bad['artifacts'].append(copy.deepcopy(row))
                    elif mutation=='revision':row['origins'][0]['revision']+=1
                    elif mutation=='owner':row['owner']=str(Owner.HUMAN)
                    elif mutation=='input':row['inputs']=['sha256:'+'0'*64]
                    elif mutation=='bytes':row['artifactSHA256']='0'*64
                    elif mutation in ('snapshot','generator'):bad[mutation]='forged'
                    elif mutation=='human-missing':bad['artifacts']=[r for r in bad['artifacts'] if r['artifact']!=human]
                    else:next(r for r in bad['artifacts'] if r['artifact']==human)['artifactSHA256']='0'*64
                    with self.subTest(mutation=mutation),self.assertRaises(ValueError):verify_manifest(bad,expected)
                with self.assertRaises(ValueError):manifest(root,candidate,snapshot,request,plan)
                (root/'unexpected.txt').write_bytes(b'orphan')
                with self.assertRaises(ValueError):manifest(root,candidate,snapshot,request,plan,human_paths=(human,))

    def fixture(self):
        rows=[{'artifact':'generated','origins':[{'id':i,'revision':1} for _,ids in STEPS.values() for i in ids]}]
        result={'status':'passed','errors':[],'steps':[{'title':'ACP:'+k,'duration':1} for k in STEPS if k!='boundary']}
        tests=[{'projectName':p,'status':'expected','expectedStatus':'passed','results':[copy.deepcopy(result)]} for p in ('COMPACT','EXPANDED')]
        report={'suites':[{'specs':[{'title':'production typed query, semantic order, keyboard journey, exact database effect and axe','ok':True,'tests':tests}]}]}
        boundary=copy.deepcopy(report['suites'][0]['specs'][0])
        boundary['title']='permissions, forged calls, wrong tenant and identity change clear protected state'
        for test in boundary['tests']:
            test['results'][0]['steps']=[{'title':'ACP:boundary','duration':1} for _ in range(2)]
        report['suites'][0]['specs'].append(boundary)
        return report,{'artifacts':rows}

    def test_representativeObjectRuntimeTraceability_result_binding(self):
        report,provenance=self.fixture()
        source=instrument(browser_tests('payment'))
        self.assertEqual(len(runtime_links(report,provenance,source,json.dumps(report).encode())),14)
        for mutation in ('missing','failed','retry','skip','unrelated','unmapped','source','raw'):
            bad=copy.deepcopy(report);mapping=copy.deepcopy(provenance);text=source
            spec=bad['suites'][0]['specs'][0];test=spec['tests'][0];result=test['results'][0]
            if mutation=='missing':result['steps'].pop()
            elif mutation=='failed':result['steps'][0]['error']={'message':'assertion failed'}
            elif mutation=='retry':test['results'].append(copy.deepcopy(result))
            elif mutation=='skip':test['status']='skipped'
            elif mutation=='unrelated':spec['title']='unrelated'
            elif mutation=='unmapped':mapping['artifacts']=[]
            elif mutation=='source':text='unrelated'
            raw=json.dumps(bad).encode() if mutation!='raw' else b'{}'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):runtime_links(bad,mapping,text,raw)

    def test_both_domains_instrument_exact_assertions_without_removing_them(self):
        for domain in self.cases:
            original=browser_tests(domain);changed=instrument(original)
            self.assertEqual(changed.count("test.step('ACP:"),7)
            self.assertEqual(changed.count('expect('),original.count('expect('))
            self.assertIn('f.rows[0]',changed);self.assertIn('f.idempotency',changed)
            with self.assertRaises(ValueError):instrument(changed)
            with self.assertRaises(ValueError):instrument(original.replace('expect(order)','expect(other)'))

    def test_runtime_wrapper_uses_existing_cleanup_and_retains_actual_sources(self):
        source=(ROOT/'engineering/traceability/runtime.py').read_text()
        for token in ('existing.runtime(workspace)','finally:', 'trace-browser-results.json', 'trace-task.spec.ts', 'trace-provenance.json', 'OIDC_BEFORE_TRACED_RUNTIME', 'return original(project, domain, logs)'):
            self.assertIn(token,source)
        self.assertNotIn('continue-on-error',source)

    def test_dependency_output_restored_on_failure_and_collisions_rejected(self):
        from engineering.traceability.runtime import source_tree
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'app';modules=root/'frontend/node_modules';modules.mkdir(parents=True)
            (modules/'exact').write_bytes(b'locked dependency bytes')
            retained=Path(temp)/'retained'
            with self.assertRaisesRegex(RuntimeError,'abort'):
                with source_tree(root,retained):
                    self.assertFalse(modules.exists())
                    raise RuntimeError('abort')
            self.assertEqual((modules/'exact').read_bytes(),b'locked dependency bytes')
            retained.mkdir()
            with self.assertRaises(FileExistsError):
                with source_tree(root,retained):pass
            self.assertTrue((modules/'exact').is_file())

    def test_oidc_dispatch_executes_separate_suite_and_rejects_replay(self):
        from engineering.traceability.runtime import dispatch_browser
        workspace=Path('/disposable');logs=workspace/'payment-runtime'/'oidc'
        calls=[]
        def original(*args):calls.append(('oidc',args));return 'actual original invocation'
        def traced(*args):calls.append(('trace',args));return 'actual traced invocation'
        kw=dict(workspace=workspace,records={},original=original,traced=traced)
        with self.assertRaises(ValueError):dispatch_browser(None,'payment',logs,**kw)
        self.assertEqual(calls,[])
        self.assertEqual(dispatch_browser(None,'payment',logs.parent,**kw),'actual traced invocation')
        kw['records']['payment']={}
        self.assertEqual(dispatch_browser(None,'payment',logs,**kw),'actual original invocation')
        self.assertEqual([c[0] for c in calls],['trace','oidc'])
        with self.assertRaises(ValueError):dispatch_browser(None,'payment',logs.parent,**kw)
        with self.assertRaises(ValueError):dispatch_browser(None,'payment',Path('/unrelated/oidc'),**kw)


if __name__=='__main__':unittest.main()
