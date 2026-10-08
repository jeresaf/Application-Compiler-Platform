"""Fail-closed negotiation and deterministic typed execution source planning."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from canonical_json import load
from execution_fixtures import DEST
from target_worker import PROFILE, ROOT, TargetWorker, TargetWorkerError
sys.path.insert(0, str(ROOT / 'worker'))
from execution_codegen import ExecutionGenerator
from generation import plan
from model import CapabilityError, lower


class Phase6ExecutionLoweringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshots = {d: load(DEST / (d + '-canonical.json')) for d in ('payment', 'case-management')}

    def nodes(self, domain='payment'):
        return copy.deepcopy(self.snapshots[domain]['content']['nodes'])

    def payload(self, nodes, version='0.2.0'):
        return {'nodes': nodes, 'required': ['semantic.execution-dataflow/0.3'],
                'decisions': PROFILE['decisions'], 'canonicalVersion': version}

    def test_host_adapter_reports_unsupported_worker_result_as_capability_failure(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from compiler_core import CompilerFault
        from target_worker import ProductionTarget
        target = ProductionTarget()
        request = SimpleNamespace(required_capabilities=('semantic.execution-dataflow/0.3',), features=('acp.execution.0.3',))
        realization = SimpleNamespace(architecture=(), design=(), objects=())
        with patch.object(target, '_call', side_effect=TargetWorkerError('UNSUPPORTED:Job/0.2.0')):
            with self.assertRaises(CompilerFault) as error:
                target.lower(realization, request)
        self.assertEqual('CAPABILITY', error.exception.code)

    def test_new_version_is_validated_but_complete_domains_still_fail_unimplemented_capabilities(self):
        for domain in self.snapshots:
            with self.assertRaises(TargetWorkerError) as error:
                TargetWorker().call('lower', self.payload(self.nodes(domain)))
            self.assertIn('UNSUPPORTED:Job/0.2.0', str(error.exception))
            self.assertNotIn('SEMANTIC_VALIDATION', str(error.exception))
            self.assertNotIn('WORKER_', str(error.exception))

    def test_unknown_version_and_old_incomplete_effects_cannot_be_enabled_by_version_label(self):
        with self.assertRaisesRegex(TargetWorkerError, 'CANONICAL_VERSION'):
            TargetWorker().call('negotiate', self.payload([], '0.99.0'))
        old = load(DEST.parent / 'canonical/payment.json')['content']['nodes']
        with self.assertRaisesRegex(TargetWorkerError, 'SEMANTIC_VALIDATION'):
            TargetWorker().call('lower', self.payload(old))

    def test_neutral_write_and_classification_rules_are_checked_inside_confined_worker(self):
        for variant in ('identity', 'classification'):
            nodes = self.nodes(); by = {n['id']: n for n in nodes}
            if variant == 'identity':
                by['CMD-RECORD']['data']['assignments'][0]['field'] = copy.deepcopy(by['ENT-PAYMENT']['data']['identity'][0])
            else:
                by['FLD-TASK-SUMMARY']['data'].update(classification='PUBLIC', classificationRef={'id': 'CLASS-PUBLIC', 'revision': 1})
            with self.assertRaisesRegex(TargetWorkerError, 'SEMANTIC_VALIDATION'):
                TargetWorker().call('lower', self.payload(nodes))

    def test_valid_unimplemented_coordination_rejects_before_source_generation(self):
        nodes = self.nodes('case-management')
        next(n for n in nodes if n['id'] == 'STEP-CMD-REVIEW')['data'].pop('transaction')
        with self.assertRaisesRegex(CapabilityError, 'COORDINATION_MULTI_COMMIT_UNSUPPORTED'):
            ExecutionGenerator(nodes).source()

    def test_display_names_and_source_map_order_cannot_change_generated_business_behavior(self):
        for domain in self.snapshots:
            nodes = self.nodes(domain)
            expected = ExecutionGenerator(nodes).source()
            for n in nodes:
                n['name'] = 'Completely different display name'
            nodes.reverse()
            self.assertEqual(expected, ExecutionGenerator(nodes).source())

    def test_execution_plans_exclude_prototype_request_and_task_execution(self):
        templates = {p.relative_to(ROOT / 'templates').as_posix(): p.read_text() for p in (ROOT / 'templates').rglob('*') if p.is_file()}
        for domain in self.snapshots:
            nodes = self.nodes(domain)
            artifacts = {a['path']: a for a in plan(lower(nodes, PROFILE, '0.2.0'), templates, PROFILE)}
            self.assertNotIn('backend/src/main/java/acp/application/TaskService.java', artifacts)
            self.assertNotIn('backend/src/main/java/acp/api/TaskController.java', artifacts)
            controller = artifacts['backend/src/main/java/acp/generated/TypedController.java']['text']
            self.assertNotIn('Map<', controller)
            self.assertIn('@RequestBody T_', controller)
            self.assertIn('input', controller)
            ui = artifacts['frontend/src/task-contract.ts']['text']
            self.assertIn('"QUERY-TEXT": text', ui)
            self.assertNotIn('?search=', ui)


if __name__ == '__main__':
    unittest.main()
