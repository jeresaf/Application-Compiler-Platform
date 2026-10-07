"""Versioned execution/dataflow contracts; all approvals here are synthetic."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from canonical_ir import admit, normalize_candidate, validate_snapshot, CanonicalError
from canonical_json import load
from compiler_contracts import Success, Failure, Document
from compiler_core import compile_pipeline
from compiler_reference import fixture_context, StructuredFrontend, FixtureApproval
from execution_contract import authoring_schema, canonical_schema, change_schema
from execution_canonical import migration_review
from execution_model import validate_execution
from execution_reference import ReferenceExecution, ExecutionFailure
from execution_fixtures import DEST, evolution
from changes import prepare, request, semantic_diff, ChangeError
from change_fixtures import change, revise
from history_repository import HistoryRepository
from reference_authority import ReferenceAuthority
from validate import ROOT


class ExecutionV03Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.models = {d: load(DEST / (d + '-authoring.json')) for d in ('payment', 'case-management')}
        cls.snapshots = {d: load(DEST / (d + '-canonical.json')) for d in cls.models}

    def model(self, domain='payment'):
        return copy.deepcopy(self.models[domain])

    def node(self, model, id):
        return next(n for n in model['nodes'] if n['id'] == id)

    def ref(self, model, id):
        n = self.node(model, id)
        return {'id': id, 'revision': n['revision']}

    def codes(self, model):
        return {d['code'] for d in validate_execution(model, 'compile')}

    def resources(self, domain='payment'):
        model = self.models[domain]
        root, identity, tenant, actor_tenant, machine, initial = (
            ('ENT-PAYMENT', 'FLD-PAYMENT-ID', 'FLD-PAYMENT-TENANT', 'FLD-MEMBER-TENANT', 'WF-PAYMENT', 'STATE-DRAFT') if domain == 'payment'
            else ('CASE', 'CASE-ID', 'CASE-TENANT', 'USER-TENANT', 'WF-CASE', 'STATE-OPEN'))
        # Discover exact tenant/identity field IDs; no behavior is inferred.
        entity = self.node(model, root)['data']
        identity = entity['identity'][0]['id']
        tenant = entity['tenantField']['id']
        scope = next(n['data'] for n in model['nodes'] if n['kind'] == 'Scope' and n['data']['resource']['id'] == root)
        actor_tenant = scope['actorTenant']['id']
        record = {identity: 'fixture-resource', tenant: 'tenant-a', 'FLD-TASK-SUMMARY': 'old',
                  '@state:' + machine: initial}
        if domain == 'payment':
            record['FLD-AMOUNT'] = '12.50'
        else:
            record['FLD-CASE-TITLE'] = {'FLD-TITLE': 'Explicit title'}
        return {(root, 'fixture-resource'): record}, {actor_tenant: 'tenant-a'}

    def execute(self, model=None, domain='payment', **kwargs):
        model = model or self.models[domain]
        resources, actor = self.resources(domain)
        return ReferenceExecution(normalize_candidate(model)).execute('UC-TASK',
            {'INPUT-TASK-TEXT': 'new', 'INPUT-TASK-RESOURCE': 'fixture-resource'}, resources,
            actor=actor, authorize=lambda *args: True, **kwargs)

    def test_separate_closed_schema_builders_and_vectors(self):
        for name, builder in [('authoring-0.3', authoring_schema), ('canonical-0.2', canonical_schema), ('change-0.2', change_schema)]:
            self.assertEqual(load(ROOT / ('contracts/' + name + '.schema.json')), builder())
        for domain, model in self.models.items():
            self.assertEqual([], validate_execution(model, 'compile'))
            self.assertEqual(self.snapshots[domain], normalize_candidate(model))
            validate_snapshot(self.snapshots[domain])
        model = self.model()
        self.node(model, 'CMD-RECORD')['data']['script'] = 'arbitrary host expression'
        self.assertIn('ACP-FLOW_SHAPE', self.codes(model))

    def test_assignment_and_required_input_output_and_event_construction(self):
        for domain in self.models:
            resources, actor = self.resources(domain)
            before = copy.deepcopy(resources)
            result = self.execute(domain=domain)
            self.assertEqual({'OUTPUT-TASK-TEXT': 'new'}, result['output'])
            self.assertEqual(before, resources)
            self.assertEqual('new', next(iter(result['resources'].values()))['FLD-TASK-SUMMARY'])
            self.assertEqual(1 if domain == 'payment' else 3, len(result['events']))
            for event in result['events']:
                self.assertTrue(event['payload'])
            self.assertEqual('12.50', result['events'][0]['payload']['FLD-AMOUNT']) if domain == 'payment' else None

    def test_wrong_type_assignment(self):
        m = self.model()
        self.node(m, 'CMD-RECORD')['data']['assignments'][0]['value'] = {'tag': 'literal', 'type': {'kind': 'Boolean'}, 'value': True}
        self.assertIn('ACP-FLOW_TYPE', self.codes(m))

    def test_dataflow_supports_typed_money_effects_beyond_text_summary(self):
        m = self.model()
        amount = self.node(m, 'FLD-AMOUNT')['data']['type']
        self.node(m, 'INPUT-TASK-TEXT')['data']['type'] = copy.deepcopy(amount)
        self.node(m, 'OPERATION-TEXT')['data']['type'] = copy.deepcopy(amount)
        for binding in self.node(m, 'JOB-TASK')['data']['inputBindings']:
            if binding['field']['id'] == 'INPUT-TASK-TEXT':
                binding['value'] = {'tag': 'literal', 'type': copy.deepcopy(amount), 'value': '4.50'}
        cmd = self.node(m, 'CMD-RECORD')['data']
        cmd['writeFields'] = [self.ref(m, 'FLD-AMOUNT')]
        cmd['assignments'][0]['field'] = self.ref(m, 'FLD-AMOUNT')
        self.assertEqual([], validate_execution(m, 'compile'))
        resources, actor = self.resources()
        result = ReferenceExecution(normalize_candidate(m)).execute('UC-TASK',
            {'INPUT-TASK-TEXT': '4.50', 'INPUT-TASK-RESOURCE': 'fixture-resource'}, resources,
            actor=actor, authorize=lambda *args: True)
        self.assertEqual('4.50', next(iter(result['resources'].values()))['FLD-AMOUNT'])
        self.assertEqual('old', result['output']['OUTPUT-TASK-TEXT'])

    def test_query_input_predicate_projection_and_step_result(self):
        m = self.model()
        step = self.node(m, 'STEP-CMD-RECORD')['data']
        step.pop('transaction')
        step['operation'] = self.ref(m, 'QUERY-TASKS')
        step['inputBindings'][0]['field'] = self.ref(m, 'QUERY-TEXT')
        self.node(m, 'UC-TASK')['data']['outputBindings'][0]['value']['field'] = self.ref(m, 'OUTPUT-TASK-TEXT')
        permission = next(n for n in m['nodes'] if n['kind'] == 'Permission' and n['data']['action']['id'] == 'QUERY-TASKS')
        for n in m['nodes']:
            if n['kind'] in {'Action', 'PermissionBoundary'}:
                n['data']['permissions'] = [self.ref(m, permission['id'])]
        self.assertEqual([], validate_execution(m, 'compile'))
        resources, actor = self.resources()
        execution = ReferenceExecution(normalize_candidate(m))
        invocation = {'INPUT-TASK-TEXT': 'ol', 'INPUT-TASK-RESOURCE': 'fixture-resource'}
        result = execution.execute('UC-TASK', invocation, resources, actor=actor, authorize=lambda *args: True)
        self.assertEqual({'OUTPUT-TASK-TEXT': 'old'}, result['output'])
        self.assertEqual(resources, result['resources'])
        self.assertEqual([], result['events'])
        invocation['INPUT-TASK-TEXT'] = 'no-match'
        with self.assertRaisesRegex(ExecutionFailure, 'QUERY_NO_RESULT'):
            execution.execute('UC-TASK', invocation, resources, actor=actor, authorize=lambda *args: True)

    def test_historical_assets_are_preserved(self):
        import hashlib
        manifest = load(DEST / 'historical-preservation.json')
        for path, expected in manifest['files'].items():
            raw = (ROOT / path).read_bytes().replace(b'\r\n', b'\n')
            self.assertEqual(expected, hashlib.sha256(raw).hexdigest(), path)

    def test_step_input_type_and_payload_source_cannot_be_guessed(self):
        m = self.model()
        self.node(m, 'STEP-CMD-RECORD')['data']['inputBindings'][0]['value'] = {'tag': 'literal', 'type': {'kind': 'Boolean'}, 'value': True}
        self.assertIn('ACP-FLOW_TYPE', self.codes(m))
        m = self.model()
        self.node(m, 'CMD-RECORD')['data']['eventBindings'][0]['payload'][0]['value'] = {'tag': 'literal', 'type': {'kind': 'String'}, 'value': '12.50'}
        self.assertIn('ACP-FLOW_TYPE', self.codes(m))

    def test_scheduled_inputs_queries_and_transition_payloads_are_explicit(self):
        m = self.model()
        self.node(m, 'JOB-TASK')['data']['inputBindings'] = []
        self.assertIn('ACP-FLOW_REQUIRED', self.codes(m))
        m = self.model()
        self.node(m, 'QUERY-TASKS')['data']['predicate'] = {'tag': 'literal', 'type': {'kind': 'Boolean'}, 'value': True}
        self.assertIn('ACP-FLOW_UNUSED', self.codes(m))
        m = self.model()
        self.node(m, 'TRANS-RECORD')['data']['eventBindings'][0]['payload'] = []
        self.assertIn('ACP-FLOW_REQUIRED', self.codes(m))

    def test_conflicting_duplicate_emissions_and_classification_downgrade_reject(self):
        m = self.model()
        self.node(m, 'TRANS-RECORD')['data']['eventBindings'][0]['payload'][0]['value'] = {
            'tag': 'literal', 'type': self.node(m, 'FLD-AMOUNT')['data']['type'], 'value': '1'}
        self.assertIn('ACP-FLOW_EVENT', self.codes(m))
        m = self.model()
        summary = self.node(m, 'FLD-TASK-SUMMARY')['data']
        summary['classification'] = 'PUBLIC'
        summary['classificationRef'] = self.ref(m, 'CLASS-PUBLIC')
        self.assertIn('ACP-FLOW_CLASSIFICATION', self.codes(m))

    def test_absence_requires_coalesce_and_exact_reference_versions(self):
        m = self.model()
        f = self.node(m, 'OPERATION-TEXT')['data']
        f['optional'] = True
        self.assertIn('ACP-FLOW_TYPE', self.codes(m))
        value = self.node(m, 'CMD-RECORD')['data']['assignments'][0]['value']
        self.node(m, 'CMD-RECORD')['data']['assignments'][0]['value'] = {
            'tag': 'coalesce', 'value': value, 'fallback': {'tag': 'literal', 'type': {'kind': 'String'}, 'value': 'explicit fallback'}}
        self.assertEqual([], validate_execution(m, 'compile'))
        m = self.model()
        self.node(m, 'CMD-RECORD')['data']['assignments'][0]['field']['revision'] += 1
        self.assertIn('ACP-FLOW_REF', self.codes(m))

    def test_coordination_contract_is_preserved_beyond_reference_executor_boundary(self):
        m = self.model('case-management')
        self.node(m, 'STEP-CMD-REVIEW')['data'].pop('transaction')
        self.assertEqual([], validate_execution(m, 'compile'))
        with self.assertRaisesRegex(ExecutionFailure, 'MULTI_COMMIT_EXECUTOR_REQUIRED'):
            self.execute(m, domain='case-management')

    def test_compensation_is_explicit_and_never_an_inferred_inverse(self):
        m = self.model('case-management')
        step = self.node(m, 'STEP-CMD-REVIEW')['data']
        step.update(onFailure='COMPENSATE', compensation=self.ref(m, 'CMD-APPROVE'))
        self.assertIn('ACP-FLOW_COMPENSATION', self.codes(m))
        step['compensationBindings'] = [{'field': self.ref(m, 'OPERATION-TEXT'),
                                        'value': {'tag': 'input', 'scope': 'USE_CASE', 'field': self.ref(m, 'INPUT-TASK-TEXT')}}]
        self.assertEqual([], validate_execution(m, 'compile'))
        with self.assertRaisesRegex(ExecutionFailure, 'COMPENSATION_EXECUTOR_REQUIRED'):
            self.execute(m, domain='case-management')

    def test_write_set_cross_resource_identity_and_tenant_mutations_reject(self):
        for variant in ('write-set', 'cross-resource', 'identity', 'tenant'):
            m = self.model()
            cmd = self.node(m, 'CMD-RECORD')['data']
            if variant == 'write-set':
                cmd['writeFields'] = []
            elif variant == 'cross-resource':
                cmd['assignments'][0]['resource'] = self.ref(m, 'ENT-MEMBER')
            else:
                entity = self.node(m, 'ENT-PAYMENT')['data']
                field = entity['identity'][0] if variant == 'identity' else entity['tenantField']
                cmd['writeFields'] = [field]
                cmd['assignments'][0]['field'] = field
            self.assertIn('ACP-FLOW_WRITE', self.codes(m), variant)

    def test_missing_command_binding_and_unused_required_input(self):
        m = self.model()
        self.node(m, 'STEP-CMD-RECORD')['data']['inputBindings'] = []
        self.assertIn('ACP-FLOW_REQUIRED', self.codes(m))
        m = self.model()
        self.node(m, 'STEP-CMD-RECORD')['data']['inputBindings'][0]['value'] = {'tag': 'literal', 'type': {'kind': 'String'}, 'value': 'explicit constant'}
        self.assertIn('ACP-FLOW_UNUSED', self.codes(m))

    def test_later_step_and_wrong_step_output_reject(self):
        m = self.model('case-management')
        self.node(m, 'STEP-CMD-REVIEW')['data']['inputBindings'][0]['value'] = {
            'tag': 'stepResult', 'step': self.ref(m, 'STEP-CMD-ARCHIVE'), 'field': self.ref(m, 'RESULT-TEXT')}
        self.assertIn('ACP-FLOW_CONTEXT', self.codes(m))
        m = self.model('case-management')
        self.node(m, 'STEP-CMD-APPROVE')['data']['inputBindings'][0]['value']['field'] = self.ref(m, 'QUERY-TEXT')
        self.assertIn('ACP-FLOW_CONTEXT', self.codes(m))

    def test_missing_use_case_command_output_and_event_payload_reject(self):
        for id, key, code in [('UC-TASK', 'outputBindings', 'ACP-FLOW_REQUIRED'),
                              ('CMD-RECORD', 'outputBindings', 'ACP-FLOW_REQUIRED'),
                              ('CMD-RECORD', 'eventBindings', 'ACP-FLOW_EVENT')]:
            m = self.model()
            self.node(m, id)['data'][key] = []
            self.assertIn(code, self.codes(m))
        m = self.model()
        self.node(m, 'CMD-RECORD')['data']['eventBindings'][0]['payload'] = []
        self.assertIn('ACP-FLOW_REQUIRED', self.codes(m))

    def test_deterministic_multi_effect_order_and_pre_post_reads(self):
        m = self.model()
        cmd = self.node(m, 'CMD-RECORD')['data']
        effect = copy.deepcopy(cmd['assignments'][0])
        effect['value'] = {'tag': 'literal', 'type': {'kind': 'String'}, 'value': 'last'}
        cmd['assignments'].append(effect)
        self.assertEqual('last', self.execute(m)['output']['OUTPUT-TASK-TEXT'])
        cmd['assignments'].reverse()
        self.assertEqual('new', self.execute(m)['output']['OUTPUT-TASK-TEXT'])
        self.assertNotEqual(normalize_candidate(m), self.snapshots['payment'])

    def test_rollback_and_invariants_observe_final_staged_state(self):
        resources, actor = self.resources('case-management')
        original = copy.deepcopy(resources)
        execution = ReferenceExecution(self.snapshots['case-management'])
        def fail(step):
            if step == 'STEP-CMD-APPROVE':
                raise ExecutionFailure('FAIL-BUSINESS')
        with self.assertRaises(ExecutionFailure):
            execution.execute('UC-TASK', {'INPUT-TASK-TEXT': 'new', 'INPUT-TASK-RESOURCE': 'fixture-resource'}, resources,
                              actor=actor, authorize=lambda *args: True, after_step=fail)
        self.assertEqual(original, resources)
        m = self.model()
        cmd = self.node(m, 'CMD-RECORD')['data']
        amount = self.ref(m, 'FLD-AMOUNT')
        cmd['writeFields'].append(amount)
        cmd['assignments'].append({'resource': cmd['resource'], 'field': amount,
                                  'value': {'tag': 'literal', 'type': self.node(m, 'FLD-AMOUNT')['data']['type'], 'value': '-1'}})
        with self.assertRaisesRegex(ExecutionFailure, 'INVARIANT'):
            self.execute(m)
        cmd['assignments'].append({**copy.deepcopy(cmd['assignments'][-1]), 'value': {'tag': 'literal', 'type': self.node(m, 'FLD-AMOUNT')['data']['type'], 'value': '4'}})
        self.assertEqual('4', self.execute(m)['events'][0]['payload']['FLD-AMOUNT'])

    def test_tenant_and_trusted_authorization_cannot_be_supplied_by_input(self):
        resources, actor = self.resources()
        execution = ReferenceExecution(self.snapshots['payment'])
        invocation = {'INPUT-TASK-TEXT': 'new', 'INPUT-TASK-RESOURCE': 'fixture-resource'}
        with self.assertRaisesRegex(ExecutionFailure, 'DENIED'):
            execution.execute('UC-TASK', invocation, resources, actor=actor)
        actor = {k: 'tenant-b' for k in actor}
        with self.assertRaisesRegex(ExecutionFailure, 'TENANT'):
            execution.execute('UC-TASK', invocation, resources, actor=actor, authorize=lambda *args: True)
        invocation['approved'] = True
        with self.assertRaisesRegex(ExecutionFailure, 'INPUT_OR_OUTPUT_TYPE'):
            execution.execute('UC-TASK', invocation, resources, actor=actor, authorize=lambda *args: True)

    def test_null_empty_and_missing_tenants_deny_even_when_equal(self):
        execution = ReferenceExecution(self.snapshots['payment'])
        invocation = {'INPUT-TASK-TEXT': 'new', 'INPUT-TASK-RESOURCE': 'fixture-resource'}
        entity = self.node(self.models['payment'], 'ENT-PAYMENT')['data']
        for value in (None, '', '   '):
            resources, actor = self.resources()
            next(iter(resources.values()))[entity['tenantField']['id']] = value
            actor = {key: value for key in actor}
            with self.subTest(value=value), self.assertRaisesRegex(ExecutionFailure, 'TENANT'):
                execution.execute('UC-TASK', invocation, resources, actor=actor, authorize=lambda *args: True)

    def test_reference_execution_detaches_validated_snapshot(self):
        snapshot = copy.deepcopy(self.snapshots['payment'])
        execution = ReferenceExecution(snapshot)
        command = next(n for n in snapshot['content']['nodes'] if n['id'] == 'CMD-RECORD')
        identity = self.node(self.models['payment'], 'ENT-PAYMENT')['data']['identity'][0]
        command['data']['assignments'][0]['field'] = identity
        resources, actor = self.resources()
        result = execution.execute('UC-TASK', {'INPUT-TASK-TEXT': 'new', 'INPUT-TASK-RESOURCE': 'fixture-resource'},
                                   resources, actor=actor, authorize=lambda *args: True)
        record = next(iter(result['resources'].values()))
        self.assertEqual('fixture-resource', record[identity['id']])
        self.assertEqual('new', record['FLD-TASK-SUMMARY'])

    def test_atomic_transaction_cannot_switch_root_instance(self):
        m = self.model('case-management')
        for id in ('STEP-CMD-APPROVE', 'STEP-CMD-ARCHIVE'):
            self.node(m, id)['data']['resource'] = {'tag': 'literal',
                'type': {'kind': 'Identifier', 'entity': self.ref(m, 'CASE')}, 'value': 'other-resource'}
        self.assertEqual([], validate_execution(m, 'compile'))
        resources, actor = self.resources('case-management')
        other = copy.deepcopy(next(iter(resources.values())))
        identity = self.node(m, 'CASE')['data']['identity'][0]['id']
        other[identity] = 'other-resource'
        other['@state:WF-CASE'] = 'STATE-REVIEWED'
        resources[('CASE', 'other-resource')] = other
        before = copy.deepcopy(resources)
        with self.assertRaisesRegex(ExecutionFailure, 'TRANSACTION_RESOURCE'):
            ReferenceExecution(normalize_candidate(m)).execute('UC-TASK',
                {'INPUT-TASK-TEXT': 'new', 'INPUT-TASK-RESOURCE': 'fixture-resource'}, resources,
                actor=actor, authorize=lambda *args: True)
        self.assertEqual(before, resources)

    def test_equivalent_source_order_is_identical_and_assignment_order_is_semantic(self):
        m = self.model('case-management')
        random.Random(7).shuffle(m['nodes'])
        for n in m['nodes']:
            n['basis'].reverse()
            n['origins'].reverse()
        self.assertEqual(self.snapshots['case-management'], normalize_candidate(m))

    def test_no_inferred_migration_or_inherited_approval(self):
        for domain in self.models:
            old = load(ROOT / ('test-corpus/canonical/' + domain + '.json'))
            source = {'modelVersion': '0.2.0', 'applicationId': old['content']['applicationId'], 'snapshotId': 'OLD',
                      'nodes': old['content']['nodes'], 'issues': [], 'approvals': self.models[domain]['approvals']}
            from canonical_fixtures import synthetic_approved
            review = migration_review(synthetic_approved(source))
            self.assertIsNone(review['candidate'])
            self.assertEqual('REVIEW_REQUIRED', review['status'])
            with self.assertRaises(CanonicalError):
                admit(self.snapshots[domain], lambda q: q['contentDigest'] == old['contentDigest'])
            with self.assertRaisesRegex(ExecutionFailure, 'EXPLICIT_EFFECTS_REQUIRED'):
                ReferenceExecution(old)

    def test_behavior_free_migration_clears_approval_and_exact_versions_fail_closed(self):
        from compiler_fixtures import small_model
        from canonical_fixtures import synthetic_approved
        from canonical_ir import migrate_authoring
        source = small_model()
        review = migration_review(source)
        self.assertEqual('REQUIRES_NEW_APPROVAL', review['status'])
        self.assertEqual([], review['candidate']['approvals'])
        candidate = synthetic_approved(review['candidate'])
        snapshot = normalize_candidate(candidate)
        self.assertEqual('0.2.0', snapshot['content']['schemaVersion'])
        with self.assertRaises(CanonicalError):
            migrate_authoring(candidate, '0.1.0')
        for key, value in [('semanticModelVersion', '0.2.0'), ('requiredFeatures', ['unknown']), ('schemaVersion', '0.2.1')]:
            bad = copy.deepcopy(snapshot)
            bad['content'][key] = value
            with self.assertRaises(CanonicalError):
                validate_snapshot(bad)

    def test_new_genesis_is_versioned_and_needs_new_authority(self):
        from changes import genesis
        plan = genesis(self.models['payment'], 'author')
        self.assertEqual('0.2.0', plan['planVersion'])
        self.assertEqual(self.snapshots['payment'], plan['candidate'])

    def test_compiler_accepts_exact_new_feature_and_approval_but_rejects_old_frontend(self):
        for domain, model in self.models.items():
            source, ctx = fixture_context(model)
            compiled = compile_pipeline(source, ctx).result
            self.assertIsInstance(compiled, Success, getattr(compiled, 'diagnostics', ()))
            wrong = replace(ctx, frontend=StructuredFrontend(), request=replace(ctx.request, frontend=StructuredFrontend.identity, features=('acp.phase1.0.2',)))
            self.assertIsInstance(compile_pipeline(source, wrong).result, Failure)
            ctx.approval.revoked = True
            self.assertIsInstance(compile_pipeline(source, ctx).result, Failure)

    def test_compiler_requires_explicit_execution_capability(self):
        source, ctx = fixture_context(self.models['payment'])
        request = replace(ctx.request, required_capabilities=('reference.obligations/1', 'reference.records/1'))
        result = compile_pipeline(source, replace(ctx, request=request)).result
        self.assertIsInstance(result, Failure)
        self.assertEqual('ACP-COMPILER-CAPABILITY', result.diagnostics[0].code)

    def test_history_version_upgrade_lookup_revision_diff_stale_base_and_rename(self):
        for domain in self.models:
            old, _ = evolution(domain)
            app = old['content']['applicationId']
            scopes = [app + ':' + s for s in ('SEMANTIC', 'SECURITY', 'MIGRATION', 'IRREVERSIBLE', 'LOCKED_DECISION')]
            auth = ReferenceAuthority(b'explicit-test-key-only' * 3, {'author-session': 'author', 'reviewer-session': 'reviewer'}, {'author': scopes, 'reviewer': scopes})
            from changes import genesis
            from canonical_fixtures import synthetic_approved
            source = synthetic_approved({'modelVersion': '0.2.0', 'applicationId': app, 'snapshotId': 'HISTORICAL', 'nodes': old['content']['nodes'], 'issues': [], 'approvals': []})
            with tempfile.TemporaryDirectory() as temporary:
                repo = HistoryRepository(Path(temporary) / 'history.sqlite')
                initial = genesis(source, 'author')
                repo.bootstrap(initial, auth.issue('reviewer-session', request(initial), 1000), auth, 1000, 'author-session')
                _, proposal = evolution(domain, repo.head())
                plan = repo.propose(proposal, auth, 'author-session')
                self.assertEqual(self.snapshots[domain], plan['candidate'])
                self.assertTrue(any(d['id'].startswith('CMD-') and d['before']['data'] != d['after']['data'] for d in plan['diff']))
                old_proof = auth.issue('reviewer-session', request(initial), 1000)
                repo.review(proposal['id'], auth, 'author-session')
                with self.assertRaises(ChangeError):
                    repo.approve(proposal['id'], old_proof, auth, 1000)
                repo.approve(proposal['id'], auth.issue('reviewer-session', request(plan), 1000), auth, 1000)
                repo.apply(proposal['id'], 'upgrade', auth, 1000)
                self.assertEqual(old, repo.snapshot(0))
                self.assertEqual(self.snapshots[domain], repo.snapshot(1))
                self.assertEqual('0.2.0', repo.snapshot()['content']['schemaVersion'])
                id = 'CMD-RECORD' if domain == 'payment' else 'CMD-REVIEW'
                self.assertEqual(1, repo.revision(id, 1)['revision'])
                self.assertGreater(repo.snapshot()['content']['nodes'][0]['revision'], 0)
                stale = copy.deepcopy(proposal)
                stale['id'] = 'CHANGE-STALE'
                with self.assertRaises(ChangeError):
                    repo.propose(stale, auth, 'author-session')
                renamed = change('CHANGE-RENAME', repo.head(), [revise(repo.snapshot(), id, name='Display rename')])
                renamed.update(changeVersion='0.2.0', canonicalVersion='0.2.0')
                next_plan = repo.propose(renamed, auth, 'author-session')
                self.assertEqual(id, next(d for d in next_plan['diff'] if d['id'] == id)['after']['id'])
                legacy = copy.deepcopy(renamed)
                legacy.pop('canonicalVersion')
                legacy['changeVersion'] = '0.1.0'
                with self.assertRaises(ChangeError):
                    prepare(repo.snapshot(), legacy)
                self.assertEqual(2, repo.audit()['entries'])


if __name__ == '__main__':
    unittest.main()
