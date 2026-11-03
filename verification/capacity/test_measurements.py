"""Statistics and instrumentation unit tests, never application-capacity evidence."""
import math,unittest
from unittest.mock import patch
from engineering.capacity.metrics import aggregate,distribution,process
from engineering.capacity.fixture import adapter_source
from engineering.capacity.workload import PROFILE,principal,token
from engineering.hardening.target import HardeningTarget


class Measurements(unittest.TestCase):
    def test_small_population_has_no_tail_claim(self):
        r=distribution([1,2,3,4]);self.assertEqual(r['p50Ms'],2.5);self.assertIsNone(r['p95Ms']);self.assertIsNone(r['p99Ms'])
    def test_p95_requires_twenty_observations(self):
        self.assertEqual(distribution(list(range(1,21)))['p95Ms'],19);self.assertIsNone(distribution(list(range(1,20)))['p95Ms'])
    def test_p99_requires_hundred_observations(self):
        self.assertEqual(distribution(list(range(1,101)))['p99Ms'],99);self.assertIsNone(distribution(list(range(1,100)))['p99Ms'])
    def test_invalid_samples_rejected(self):
        for values in ([],[-1],[float('nan')],[float('inf')]):
            with self.subTest(values=values),self.assertRaises(ValueError):distribution(values)
    def test_rejections_are_separate_population(self):
        r=aggregate([{'milliseconds':10,'status':200,'disposition':'SUCCESS'},{'milliseconds':1,'status':429,'disposition':'EXPECTED_REJECTION'}],2)
        self.assertEqual((r['successful'],r['expectedRejections'],r['requestsPerSecond']),(1,1,1));self.assertEqual(r['successfulRequests']['p50Ms'],10)
    def test_unexpected_failure_cannot_be_summarized_as_pass(self):
        with self.assertRaises(ValueError):aggregate([{'milliseconds':1,'status':500,'disposition':'UNEXPECTED_ERROR'}],1)
    def test_invalid_elapsed_rejected(self):
        for value in (0,-1,float('inf'),float('nan')):
            with self.assertRaises(ValueError):aggregate([{'milliseconds':1,'status':200,'disposition':'SUCCESS'}],value)
    def test_process_observation_is_actual_and_identity_bound(self):
        import os
        r=process(os.getpid());self.assertGreater(r['rssBytes'],0);self.assertGreater(r['startTicks'],0);self.assertGreaterEqual(r['cpuSeconds'],0)
    def test_dead_process_is_not_live_measurement(self):self.assertTrue(process(999999999)['exited'])
    def test_profile_is_bounded_and_does_not_change_rate_policy(self):
        self.assertEqual(PROFILE['clients'],[4,8,16]);self.assertEqual(PROFILE['measuredCyclesPerClient'],8);self.assertIn('UNCHANGED',PROFILE['ratePolicy'])
    def test_fixture_uses_valid_bound_existing_principals(self):
        text=adapter_source();self.assertIn('browser-h3-(?:[0-9]|1[0-5])',text);self.assertIn('Jwt.withTokenValue(originalToken)',text);self.assertIn('originalToken.startsWith("browser-h3-")?originalToken:',text)
        self.assertEqual(principal(0),('tenant-one','fixture:operator'));self.assertEqual(principal(15),('tenant-two','fixture:reporter-two'))
    def test_metrics_do_not_acquire_another_application_connection(self):
        text=adapter_source();method=text[text.index('Map<String,Object> h3Resources()'):text.index('@GetMapping("/__test/facts")')]
        self.assertIn('getHikariPoolMXBean()',method);self.assertNotIn('queryFor',method);self.assertNotIn('getConnection()',method)
    def test_h1_generator_unchanged(self):self.assertEqual(HardeningTarget().bundle,'f982b13e43e0efd070ea1b0773da5aedcdbf2486363c6e902f27c36ba00bcb02')

    def test_source_preview_is_bound_before_build_outputs_exist(self):
        from pathlib import Path
        source=Path('engineering/capacity/run.py').read_text()
        self.assertLess(source.index('preview=Preview('),source.index("demo.command(['npm'"))
        self.assertLess(source.index('session=analyze('),source.index("build(root,w/'build'"))

    def test_resource_sampler_keeps_authentication_enabled(self):
        from pathlib import Path
        for name in ('metrics.py','scenarios.py'):
            text=(Path('engineering/capacity')/name).read_text()
            self.assertIn("headers={'Authorization':'Bearer browser-authorized'}",text)

    def test_profile_accounts_for_nested_connection_demand_without_unbounded_pool(self):
        self.assertEqual(PROFILE['applicationPoolConnections'],2*max(PROFILE['clients'])+2)
        self.assertEqual(PROFILE['pressurePoolConnections'],2)
        self.assertEqual(PROFILE['pressureAcquisitionTimeoutMs'],750)
        self.assertEqual(PROFILE['applicationPoolAcquisitionTimeoutMs'],30000)

    def test_scope_boundary_exercises_a_due_schedule(self):
        from pathlib import Path
        text=Path('engineering/capacity/scenarios.py').read_text().split('def scope_limit',1)[1]
        self.assertLess(text.index("{'action':'MISSED'}"),text.index('lab.start(workers=True)'))
        self.assertIn("r['error']=='SCOPE_LIMIT_EXCEEDED'",text)
