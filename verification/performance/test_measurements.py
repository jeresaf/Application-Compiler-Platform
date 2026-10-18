import math
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'tooling')]
from engineering.performance.measure import summarize, digest, BROWSER
from engineering.performance.scaling import fixture
from canonical_ir import normalize_candidate
from canonical_json import load

class Measurements(unittest.TestCase):
    def test_statistics_preserve_samples_and_wall_throughput(self):
        values=list(range(1,101));result=summarize(values,elapsed_ms=2000)
        self.assertEqual(result['p50Ms'],50.5);self.assertEqual(result['p95Ms'],95)
        self.assertEqual(result['p99Ms'],99);self.assertEqual(result['throughputPerSecond'],50)
        self.assertEqual(result['samples'],values)
    def test_small_samples_do_not_claim_tail_precision(self):
        result=summarize([2,3,1]);self.assertIsNone(result['p95Ms']);self.assertIsNone(result['p99Ms'])
        self.assertIsNotNone(result['sampleStddevMs'])
    def test_reject_invalid_observations(self):
        for values in ([],[float('nan')],[float('inf')],[-1],[True],['1']):
            with self.subTest(values=values),self.assertRaises(ValueError):summarize(values)
        for wall in (0,-1,float('nan')):
            with self.assertRaises(ValueError):summarize([1],elapsed_ms=wall)
        with self.assertRaises(ValueError):summarize([1],failures=-1)
    def test_result_digest_rejects_nonfinite(self):
        with self.assertRaises(ValueError):digest({'x':math.inf})
        self.assertNotEqual(digest({'x':1}),digest({'x':2}))
    def test_valid_larger_fixture_preserves_original_business_nodes(self):
        for domain in ('payment','case-management'):
            original=load(ROOT/f'test-corpus/deterministic-v04/{domain}-canonical-candidate.json')
            for size in (0,3,8,16,32):
                model=fixture(domain,size);snapshot=normalize_candidate(model)
                by={n['id']:n for n in model['nodes']}
                self.assertEqual(len(by),len(original['content']['nodes'])+size)
                for node in original['content']['nodes']:
                    self.assertEqual(node,by[node['id']])
                self.assertEqual(snapshot['content']['applicationId'],original['content']['applicationId'])
                if not size:self.assertEqual(snapshot['contentDigest'],original['contentDigest'])
    def test_invalid_fixture_sizes(self):
        for size in (-1,True,1.1):
            with self.assertRaises(ValueError):fixture('payment',size)
    def test_bounded_workloads_preserve_rate_and_real_assertions(self):
        self.assertIn('expect(r.status()).toBe(200)',BROWSER)
        self.assertIn('expect([200,429,500]).toContain(r.status())',BROWSER)
        self.assertNotIn('sleep',BROWSER);self.assertNotIn('retry',BROWSER)
        self.assertIn("expect(facts.events).toBe(EVENTS)",BROWSER)

if __name__=='__main__':unittest.main()

class NativeBounds(unittest.TestCase):
    def test_exact_node_byte_depth_work_bounds_fail_closed(self):
        from types import SimpleNamespace
        from dataclasses import replace
        from compiler_core import Budget, CompilerFault
        from compiler_contracts import Resources, Cancellation
        def budget(**limits):
            return Budget(SimpleNamespace(request=SimpleNamespace(resources=replace(Resources(),**limits),cancellation=Cancellation(),allowed_ports=())))
        budget().inspect({'nodes':[{} for _ in range(2000)]})
        for value,limits in (({'nodes':[{} for _ in range(2001)]},{}),('x'*1048576,{}),({'x':{'y':1}},{'depth':1}),([1,2,3],{'work':2})):
            with self.subTest(limits=limits),self.assertRaises(CompilerFault) as error:budget(**limits).inspect(value)
            self.assertEqual(error.exception.code,'RESOURCE')
    def test_original_capacity_is_not_raised(self):
        from compiler_contracts import Resources
        r=Resources();self.assertEqual((r.nodes,r.input_bytes,r.output_bytes,r.depth),(2000,1048576,1048576,48))

class SupportedUI(unittest.TestCase):
    def test_additional_table_column_remains_unsupported(self):
        import copy
        from engineering.generator_candidates.spring_vue_postgres_0_6 import SuccessorCandidate
        candidate=SuccessorCandidate()
        model=fixture('payment',0);nodes=model['nodes'];by={n['id']:n for n in nodes}
        field=copy.deepcopy(by['OUTPUT-TASK-TEXT']);field.update(id='PERF-EXTRA-COLUMN',name='Test-only extra column',revision=1)
        nodes.append(field);ref={'id':field['id'],'revision':1}
        model['approvals'].append({'subject':ref,'reviewer':'synthetic-test-only','evidence':'NOT_HUMAN_APPROVAL'})
        by['TABLE-TASKS']['data']['columns'].append(ref)
        projection=copy.deepcopy(by['QUERY-TASKS']['data']['projection'][0]);projection['field']=ref
        by['QUERY-TASKS']['data']['projection'].append(projection)
        binding=copy.deepcopy(by['UC-TASK']['data']['outputBindings'][0]);binding['field']=ref
        by['UC-TASK']['data']['outputBindings'].append(binding)
        normalize_candidate(model)  # Semantically valid; rejection is the target's existing UI capacity.

        with self.assertRaisesRegex(ValueError,'TABLE_COLUMNS'):
            candidate._model.negotiate(nodes,['semantic.execution-dataflow/0.3','acp.deterministic-execution.0.4'],candidate.profile['decisions'],candidate.profile,'0.3.0')


class SchedulingVariability(unittest.TestCase):
    def test_timed_rejection_is_retained_not_mislabelled_semantic_nondeterminism(self):
        from engineering.performance.scaling import validate_trials
        passed={'status':'PASS','artifactPlanDigest':'a','diagnostics':[]}
        timeout={'status':'REJECTED','diagnostics':['ACP-COMPILER-RESOURCE']}
        validate_trials([passed,timeout,passed],baseline=True)
        with self.assertRaisesRegex(ValueError,'NONDETERMINISTIC'):
            validate_trials([passed,dict(passed,artifactPlanDigest='b')])
        with self.assertRaisesRegex(ValueError,'BASELINE_COMPILER_RESOURCE_FAILURE'):
            validate_trials([timeout],baseline=True)
        with self.assertRaisesRegex(ValueError,'INVALID_SCALING_FIXTURE'):
            validate_trials([{'status':'REJECTED','diagnostics':['ACP-COMPILER-INPUT']}])
