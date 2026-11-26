"""H10 review consistency and preservation; never a hostile-execution PASS."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
REVIEW=ROOT/'reviews/phase11-h10-20261123'
BASE='396b263683f0e57aa9ed0be431d863304279aafb'


def load(name):return json.loads((REVIEW/name).read_bytes())


def validate_packet(assessment, matrix):
    assert assessment['baseline']==BASE and assessment['scope']=='DESIGN_AND_READONLY_FEASIBILITY_ONLY'
    assert assessment['SEC-01']['disposition']=='BLOCKED' and assessment['operationalSecurity']=='NOT_ESTABLISHED'
    assert assessment['phase11']=='IN_PROGRESS' and assessment['phase12']=='NOT_STARTED' and assessment['phase6ReleaseClosure']=='BLOCKED'
    assert assessment['activeUntrustedExecutionProfile'] is None and assessment['policyDigest'] is None
    assert assessment['implementationAuthorized'] is False and assessment['productionProfileSelected'] is False
    assert assessment['preferredAlternative']=='B_RECOMMENDED_NOT_SELECTED'
    assert {d['id'] for d in assessment['decisions']}=={f'H10-D{n}' for n in range(1,7)}
    assert all(d['status']=='NOT_APPROVED' and d['owner'] and d['request'] for d in assessment['decisions'])
    assert matrix['scope']=='PROPOSED_TESTS_NOT_EXECUTED' and len(matrix['tests'])==22
    assert len({t['name'] for t in matrix['tests']})==22
    assert {t['id'] for t in matrix['tests']}=={f'H10-T{n:02d}' for n in range(1,23)}
    for t in matrix['tests']:
        assert t['executionStatus']=='NOT_RUN' and t['authorization']=='BLOCKED_PENDING_SECURITY_OWNER_AND_LAB_APPROVAL'
        for key in ('input','expectedRestriction','actualObservationRequired','verificationMethod','securityLimitation'):
            assert type(t[key]) is str and t[key]
        assert set(t['evidenceFormat'])=={'sourceCommit','candidateIdentity','isolationProfileIdentity','osKernel','executionMechanism','securityPolicyDigest','workload','observedResult','exitStatus','resourceMeasurements','cleanupResult','evidenceDigest'}
        assert 'never development host' in t['environment']
    return True


class ReviewTests(unittest.TestCase):
    def test_review_has_no_implementation_or_release_authority(self):
        self.assertTrue(validate_packet(load('assessment.json'),load('adversarial-tests.json')))

    def test_false_resolution_or_profile_activation_rejected(self):
        for key,value in [('implementationAuthorized',True),('activeUntrustedExecutionProfile','candidate'),('phase6ReleaseClosure','PASS'),('preferredAlternative','B_APPROVED')]:
            a=load('assessment.json');a[key]=value
            with self.subTest(key=key),self.assertRaises(AssertionError):validate_packet(a,load('adversarial-tests.json'))
        a=load('assessment.json');a['SEC-01']['disposition']='PASS'
        with self.assertRaises(AssertionError):validate_packet(a,load('adversarial-tests.json'))

    def test_fabricated_human_decision_rejected(self):
        a=load('assessment.json');a['decisions'][0]['status']='APPROVED'
        with self.assertRaises(AssertionError):validate_packet(a,load('adversarial-tests.json'))

    def test_missing_or_claimed_executed_probe_rejected(self):
        for change in ('missing','claim'):
            m=load('adversarial-tests.json')
            if change=='missing':m['tests'].pop()
            else:m['tests'][0]['executionStatus']='PASS'
            with self.subTest(change=change),self.assertRaises(AssertionError):validate_packet(load('assessment.json'),m)

    def test_all_required_attack_classes_present(self):
        names={t['name'] for t in load('adversarial-tests.json')['tests']}
        self.assertEqual(names,{'unauthorizedFileRead','unauthorizedFileWrite','networkConnect','childProcessCreation','executableSubstitution','environmentLeakage','descriptorLeakage','clockAccess','entropyAccess','crossTenantRead','cpuExhaustion','memoryExhaustion','processCountExhaustion','infiniteLoop','timeoutTermination','descendantCleanup','symlinkAttack','outputSubstitution','crashDuringGeneration','interruptedPublication','profileMismatch','protocolAbuse'})

    def test_inspected_source_is_exact_baseline_git_content(self):
        index=load('source-index.json');self.assertEqual(index['baseline'],BASE)
        self.assertTrue(subprocess.run(['git','merge-base','--is-ancestor',BASE,'HEAD'],cwd=ROOT).returncode==0)
        for name,pin in index['files'].items():
            with self.subTest(name=name):
                p=ROOT/name;self.assertFalse(p.is_symlink())
                if name == 'engineering/mcp_adapter/service.py':
                    from verification.evidence_admission.test_preservation import preserved_bytes
                    raw = preserved_bytes(p)
                else:
                    raw = p.read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(),pin)
                self.assertEqual(raw,subprocess.check_output(['git','show',BASE+':'+name],cwd=ROOT))

    def test_sealed_preload_and_request_order_are_reported_honestly(self):
        text=(ROOT/'targets/spring-vue-postgres/worker/main.py').read_text()
        self.assertLess(text.index('from generation import'),text.index('def sandbox'))
        main=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='main')
        source=ast.get_source_segment(text,main)
        self.assertLess(source.index('sandbox()'),source.index('sys.stdin.buffer.read'))
        self.assertIn('seccomp_init(0x7fff0000)',text)
        doc=(ROOT/'docs/phase11-h10-plugin-isolation.md').read_text()
        self.assertIn('after module/template loading',doc)
        self.assertIn('default ALLOW',doc)

    def test_successor_remains_explicitly_trusted_in_process(self):
        text=(ROOT/'engineering/generator_candidates/spring_vue_postgres_0_6/candidate.py').read_text()
        self.assertIn('from . import migrations, provenance, rate_clock, dependencies',text)
        self.assertIn('No confinement, authority, runtime or release admission claim.',text)
        self.assertLess(text.index("importlib.import_module('model')"),text.index('CANDIDATE_BACKEND_SOURCE'))

    def test_clock_entropy_and_root_limitations_are_explicit(self):
        text=(ROOT/'docs/phase11-h10-plugin-isolation.md').read_text()
        for phrase in ('vDSO','RDTSC/RDTSCP','RDRAND/RDSEED','host-root','not a proof','shared-kernel'):
            self.assertIn(phrase,text)
        matrix={t['name']:t for t in load('adversarial-tests.json')['tests']}
        self.assertIn('absolute clock-denial',matrix['clockAccess']['expectedRestriction'])
        self.assertIn('unsupported no-entropy',matrix['entropyAccess']['expectedRestriction'])

    def test_local_observation_is_not_execution_qualification(self):
        r=load('host-observation.json')
        self.assertEqual(r['status'],'OBSERVED_NOT_QUALIFIED')
        self.assertFalse(r['candidateExecuted']);self.assertFalse(r['hostilePayloadExecuted'])
        self.assertEqual(r['sourceCommit'],BASE);self.assertEqual(r['resourcesCreated'],[])
        self.assertIsNone(r['securityPolicyDigest'])
        self.assertEqual(r['observerSHA256'],hashlib.sha256((ROOT/'verification/plugin_isolation/observe_host.py').read_bytes()).hexdigest())
        for value in r['reads'].values():
            if value['status']=='OBSERVED':self.assertEqual(hashlib.sha256((value['text']+'\n').encode()).hexdigest(),value['sha256'])

    def test_observer_has_only_fixed_readonly_commands(self):
        text=(ROOT/'verification/plugin_isolation/observe_host.py').read_text();tree=ast.parse(text)
        commands=next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='commands' for t in n.targets))
        self.assertEqual(ast.literal_eval(commands),[['/usr/bin/bwrap','--version'],['/usr/bin/dpkg-query','-W','-f=${Package} ${Version} ${Architecture}\n','bubblewrap','libseccomp2'],['/usr/bin/systemctl','--user','show','-p','ControlGroup']])
        self.assertNotIn('shell=True',text)
        self.assertNotIn('namespace_probe',text);self.assertNotIn('resource_probe',text)

    def test_proposed_protocol_carries_only_bounded_data_not_publication_authority(self):
        p=load('assessment.json')['proposedProtocol']
        self.assertEqual(p['status'],'PROPOSAL_ONLY_NOT_REGISTERED')
        self.assertEqual(p['operations'],['lower','plan'])
        self.assertEqual(p['limits']['requestBytes'],4000000)
        self.assertEqual(p['limits']['resultBytes'],16000000)
        self.assertTrue({'nonce','candidateSourceDigest','canonicalDigest'}.issubset(p['requestFields']))
        self.assertNotIn('command',p['requestFields']);self.assertNotIn('hostPath',p['artifactFields'])
        self.assertIn('plugin cannot grant',p['hostDerives'])

    def test_existing_qualification_cannot_be_unblocked_by_declarations(self):
        from engineering.evidence_admission.isolation import qualification_result
        result=qualification_result(True,True,{}, {})
        self.assertEqual(result['status'],'ISOLATION_QUALIFICATION_BLOCKED')
        self.assertFalse(result['operationalSecurityEstablished'])


if __name__=='__main__':unittest.main()
