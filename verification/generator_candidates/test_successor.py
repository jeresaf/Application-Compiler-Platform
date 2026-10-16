"""Offline successor tests. Fixture history is synthetic, never acceptance evidence."""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'tooling'), str(ROOT / 'tooling/tests')]
from engineering.generator_candidates.spring_vue_postgres_0_6 import SuccessorCandidate
from engineering.generator_candidates.spring_vue_postgres_0_6 import candidate as implementation
from engineering.generator_candidates.spring_vue_postgres_0_6 import migrations, provenance
from canonical_json import load
from change_fixtures import evolution_change
from changes import prepare
from compiler_contracts import ArtifactPlan, Document, Owner, Subject
from compiler_core import _ownership, CompilerFault
from filesystem_artifacts import FilesystemArtifactStore, StoreConflict
from target_release import verify_release, verify_preserved_releases, verify_production_upgrade
from target_worker import bundle_digest, PROFILE, ProductionTarget
from test_canonical03_migrations import fixture
from test_target_migrations import FixtureAcceptedHistory


def cross_version(domain, value="e\u0301\x00🦋'"):
    before = load(ROOT / f'test-corpus/execution-v03/{domain}-canonical.json')
    change = load(ROOT / f'test-corpus/deterministic-v04/{domain}-change.json')
    addition = evolution_change(before, change['base'], 'required-field')
    change['id'] = 'TEST-SUCCESSOR-ONLY'
    change['intent'] = 'Synthetic offline successor fixture; no human approval'
    change['operations'].extend(addition['operations'])
    change['migration'] = addition['migration']
    plan = Document.of(prepare(before, change))
    bindings = Document.of({'requiredFieldBackfills': {'EVOLUTION-required-field': value}})
    return Document.of(before), Document.of(plan.read()['candidate']), plan, bindings, FixtureAcceptedHistory(plan, bindings)


def request(candidate, snapshot):
    return SimpleNamespace(compiler='compiler/test', pipeline='pipeline/test',
                           snapshot_digest=snapshot.read()['contentDigest'], features=(),
                           generator=candidate.generator)


class SuccessorIdentityTests(unittest.TestCase):
    def test_exact_v3_corrections_and_all_prior_release_bytes(self):
        candidate = SuccessorCandidate()
        ancestry = json.loads((implementation.PACKAGE / 'ancestry.json').read_text())
        for name, binding in ancestry['corrections'].items():
            original = subprocess.check_output(['git', 'show', ancestry['sourceCommit'] + ':' + binding['path']], cwd=ROOT)
            self.assertEqual(binding['sourceSHA256'], hashlib.sha256(original).hexdigest())
            expected = original
            if 'relocation' in binding:
                expected = expected.replace(binding['relocation']['before'].encode(), binding['relocation']['after'].encode())
            actual = (implementation.PACKAGE / name).read_bytes()
            self.assertEqual(expected, actual)
            self.assertEqual(binding['sha256'], hashlib.sha256(actual).hexdigest())
        release = ROOT / 'targets/spring-vue-postgres/release-contract.json'
        previous = subprocess.check_output(['git', 'show', '8f936d2b6178d2487fbe98075a101296b277023f:' + release.relative_to(ROOT).as_posix()], cwd=ROOT)
        self.assertEqual(previous, release.read_bytes())
        self.assertTrue(verify_preserved_releases(json.loads(previous), json.loads(release.read_bytes())))
        self.assertEqual(ancestry['parentBundleDigest'], bundle_digest())
        verify_release(PROFILE, bundle_digest())
        self.assertTrue(ProductionTarget().generator.startswith('acp-spring-vue-generator/0.5.0+'))
        self.assertEqual('UNSEALED_CANDIDATE', candidate.descriptor()['status'])

    def test_no_successor_release_or_upgrade_admission(self):
        candidate = SuccessorCandidate()
        self.assertEqual('acp-spring-vue-postgres/0.6.0', candidate.profile['profile'])
        with self.assertRaisesRegex(ValueError, 'GENERATOR_VERSION_UNRELEASED'):
            verify_release(candidate.profile, candidate.bundle)
        with self.assertRaisesRegex(ValueError, 'PRODUCTION_UPGRADE_OUTSIDE_WINDOW'):
            verify_production_upgrade(PROFILE['profile'], candidate.profile['profile'])
        with self.assertRaisesRegex(ValueError, 'PRODUCTION_UPGRADE_OUTSIDE_WINDOW'):
            verify_production_upgrade('acp-spring-vue-postgres/0.1.0', PROFILE['profile'])
        profile = candidate.profile
        profile['profile'] = PROFILE['profile']
        self.assertEqual('acp-spring-vue-postgres/0.6.0', candidate.profile['profile'])

    def test_source_changes_missing_files_and_symlinks_fail_closed(self):
        candidate = SuccessorCandidate()
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / 'candidate'
            shutil.copytree(implementation.PACKAGE, copied)
            with patch.object(implementation, 'PACKAGE', copied):
                original = (copied / 'migrations.py').read_bytes()
                (copied / 'migrations.py').write_bytes(original + b'\n')
                with self.assertRaisesRegex(ValueError, 'CANDIDATE_SOURCE_CHANGED'):candidate.descriptor()
                (copied / 'migrations.py').unlink()
                with self.assertRaisesRegex(ValueError, 'CANDIDATE_SOURCE_CHANGED'):candidate.descriptor()
                (copied / 'migrations.py').symlink_to(implementation.WORKER / 'model.py')
                with self.assertRaisesRegex(ValueError, 'CANDIDATE_SOURCE_PATH'):candidate.descriptor()


class SuccessorMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.candidate = SuccessorCandidate()

    def test_storage_presence_and_entity_only_bytea_guards(self):
        args = fixture()
        sql = self.candidate.plan_upgrade(*args).read()['sql']
        self.assertIn('IF NOT EXISTS (SELECT 1 FROM information_schema.columns', sql)
        self.assertIn("udt_name='bytea'", sql)
        self.assertLess(sql.index('ACP_INCOMPATIBLE_STORAGE_REPRESENTATION'), sql.index('ADD COLUMN'))
        nodes = {n['id']: n for n in args[0].read()['content']['nodes']}
        expected = [n for n in nodes.values() if n['kind'] == 'Field' and n['data']['type']['kind'] == 'String'
                    and nodes[n['data']['owner']['id']]['kind'] == 'Entity']
        self.assertEqual(len(expected), sql.count('information_schema.columns'))
        for n in nodes.values():
            if n['kind'] == 'Field' and nodes[n['data']['owner']['id']]['kind'] == 'ValueObject':
                self.assertNotIn(migrations.identifier(n['data']['owner']['id'], 'e'), sql)

    def test_both_domains_cross_version_explicit_binary_backfill(self):
        for domain in ('payment', 'case-management'):
            with self.subTest(domain=domain):
                result = self.candidate.plan_upgrade(*cross_version(domain)).read()
                self.assertIn("decode('65cc8100f09fa68b27','hex')", result['sql'])
                self.assertIn('SET NOT NULL', result['sql'])
                self.assertNotIn('DEFAULT', result['sql'])
                self.assertNotIn('DROP', result['sql'])
                self.assertEqual(['EXPAND', 'BACKFILL', 'VERIFY', 'SWITCH'], result['changes'][0]['phases'])
                self.assertEqual('NOT_CLAIMED', result['productionRollback'])

    def test_existing_canonical02_optional_relation_ddl_remains_supported(self):
        before = load(ROOT / 'test-corpus/execution-v03/payment-canonical.json')
        change = evolution_change(before, {'sequence': 0, 'digest': before['contentDigest'],
                                  'journalDigest': 'sha256:' + '0' * 64}, 'optional-relationship')
        change.update(changeVersion='0.2.0', canonicalVersion='0.2.0')
        plan = Document.of(prepare(before, change));bindings = Document.of({})
        result = self.candidate.plan_upgrade(Document.of(before), Document.of(plan.read()['candidate']),
                    plan, bindings, FixtureAcceptedHistory(plan, bindings)).read()
        self.assertIn('CREATE TABLE', result['sql'])
        self.assertEqual(['EXPAND', 'VERIFY'], result['changes'][0]['phases'])

    def test_empty_boolean_nullable_presence_and_authority_rejections(self):
        for value in ('', "'\\n"):
            result = self.candidate.plan_upgrade(*fixture(value=value)).read()
            self.assertIn("decode('" + value.encode().hex() + "','hex')", result['sql'])
        boolean = self.candidate.plan_upgrade(*fixture(value=True, typ={'kind': 'Boolean'})).read()['sql']
        self.assertIn('=TRUE WHERE', boolean)
        optional = self.candidate.plan_upgrade(*fixture(optional=True, nullable=True)).read()['sql']
        self.assertIn('boolean NOT NULL DEFAULT false', optional)
        self.assertIn('ADD CHECK', optional)
        with self.assertRaisesRegex(migrations.MigrationBlocked, 'BACKFILL_TYPE'):
            self.candidate.plan_upgrade(*fixture(value=False))
        args = list(fixture()); args[-1].revoked = True
        with self.assertRaisesRegex(migrations.MigrationBlocked, 'UNACCEPTED_HISTORY'):
            self.candidate.plan_upgrade(*args)
        args = list(fixture()); args[3] = Document.of({'requiredFieldBackfills': {}})
        with self.assertRaisesRegex(migrations.MigrationBlocked, 'UNAPPROVED_DATA_BINDINGS'):
            self.candidate.plan_upgrade(*args)


class SuccessorArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate = SuccessorCandidate()
        cls.inputs = {}
        for domain in ('payment', 'case-management'):
            snapshot = Document.of(load(ROOT / f'test-corpus/deterministic-v04/{domain}-canonical-candidate.json'))
            req = request(cls.candidate, snapshot)
            plan = cls.candidate.plan(snapshot, req)
            target = cls.candidate.lower(snapshot, compiler=req.compiler, pipeline=req.pipeline)
            cls.inputs[domain] = snapshot, req, plan, target

    def test_real_both_domain_artifact_plans_exact_origin_subsets_and_identity(self):
        for domain, (snapshot, req, plan, target) in self.inputs.items():
            with self.subTest(domain=domain), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / 'application'
                FilesystemArtifactStore(root).apply(plan)
                document = provenance.read_provenance(root / 'acp/provenance.json')
                self.assertEqual('acp-spring-vue-generator/0.6.0', document['build']['generator'])
                self.assertEqual('acp-spring-vue-postgres/0.6.0', document['build']['targetProfile'])
                self.assertEqual('sha256:' + self.candidate.bundle, document['build']['bundleDigest'])
                rows = {a.path: a for a in plan.artifacts}
                narrower = 0
                for row in document['artifacts']:
                    expected = {(o.id, o.revision) for o in rows[row['artifact']].mappings}
                    self.assertEqual(expected, {(o['id'], o['revision']) for o in row['origins']})
                    narrower += len(expected) < len(document['originSets']['canonical-model'])
                self.assertGreater(narrower, 0)
                result = provenance.verify_plan_provenance(root, plan, document, target=target, request=req)
                self.assertEqual('VERIFIED_OFFLINE', result['status'])
                self.assertEqual('NOT_PROVEN', result['runtime'])

    def test_provenance_tampering_and_incomplete_coverage_rejected(self):
        for domain, (snapshot, req, plan, target) in self.inputs.items():
            with self.subTest(domain=domain), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / 'application'; FilesystemArtifactStore(root).apply(plan)
                document = provenance.read_provenance(root / 'acp/provenance.json')
                for kind in ('missing', 'extra', 'duplicate', 'revision', 'digest', 'owner', 'confidence', 'origin-duplicate'):
                    changed = copy.deepcopy(document); row = changed['artifacts'][0]
                    if kind == 'missing':changed['artifacts'].pop()
                    elif kind == 'extra':changed['artifacts'].append({**row, 'artifact': 'orphan.txt'})
                    elif kind == 'duplicate':changed['artifacts'].append(copy.deepcopy(row))
                    elif kind == 'revision':row['origins'][0]['revision'] += 1
                    elif kind == 'digest':row['artifactDigest'] = 'sha256:' + '0' * 64
                    elif kind == 'owner':row['ownership'] = 'HUMAN_OWNED'
                    elif kind == 'confidence':row['locationConfidence'] = 'UNKNOWN'
                    else:row['origins'].append(copy.deepcopy(row['origins'][0]))
                    with self.subTest(kind=kind), self.assertRaises(ValueError):
                        provenance.verify_plan_provenance(root, plan, changed, target=target, request=req)
                with self.assertRaisesRegex(ValueError, 'PROVENANCE_SEMANTIC_COVERAGE'):
                    provenance.verify_plan_provenance(root, plan, document, target=target, request=req,
                        required_origins=(Subject(snapshot.read()['content']['applicationId'], 'MISSING', 1),))
                bad = replace(plan, artifacts=(replace(plan.artifacts[0], provenance=replace(plan.artifacts[0].provenance, inputs=('wrong',))), *plan.artifacts[1:]))
                with self.assertRaisesRegex(ValueError, 'PROVENANCE_INPUTS'):
                    provenance.verify_plan_provenance(root, bad, document, target=target, request=req)

    def test_regeneration_preserves_human_and_rejects_ai_stale_cas_and_manual_edits(self):
        for domain, (snapshot, req, plan, target) in self.inputs.items():
            with self.subTest(domain=domain), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / 'application'; store = FilesystemArtifactStore(root);store.apply(plan)
                path = 'frontend/src/extensions/identity.ts'; store.adopt_human(path)
                human = b'// HUMAN exact bytes\nexport const identity = "human";\n';(root / path).write_bytes(human)
                inventory = store.inventory()
                new = _ownership(self.candidate.plan(snapshot, req, inventory=inventory), inventory)
                self.assertNotIn(path, {a.path for a in new.artifacts})
                store.apply(new)
                self.assertEqual(human, (root / path).read_bytes())
                item = next(a for a in new.artifacts if a.owner == Owner.COMPILER)
                ai = replace(item, path='frontend/src/extensions/ai.ts', owner=Owner.AI, intent='CREATE', expected_digest=None)
                with self.assertRaisesRegex(StoreConflict, 'AI_APPROVAL_REQUIRED'):store.apply(ArtifactPlan((ai,), ()))
                bad = replace(item, intent='UPDATE', expected_digest='sha256:' + '0' * 64)
                with self.assertRaises(CompilerFault):store.apply(ArtifactPlan((bad,), ()))
                (root / item.path).write_bytes(b'tampered\n')
                with self.assertRaisesRegex(StoreConflict, 'MANUAL_EDIT'):store.apply(_ownership(new, store.inventory()))
                self.assertEqual(human, (root / path).read_bytes())

    def test_request_cannot_relabel_snapshot_or_reuse_old_generator_identity(self):
        snapshot, req, plan, target = self.inputs['payment']
        for key, value in [('generator', 'acp-spring-vue-generator/0.5.0'), ('snapshot_digest', 'sha256:' + '0' * 64)]:
            bad = SimpleNamespace(**{**vars(req), key: value})
            with self.assertRaisesRegex(ValueError, 'CANDIDATE_REQUEST_IDENTITY'):
                self.candidate.plan(snapshot, bad)
        self.assertEqual(plan, self.candidate.plan(snapshot, req))

    def test_materialized_verification_rejects_wrong_generator_and_stored_bytes(self):
        snapshot, req, plan, target = self.inputs['payment']
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'application'; FilesystemArtifactStore(root).apply(plan)
            self.assertEqual('VERIFIED_OFFLINE', self.candidate.verify_materialized(root, plan, snapshot, req)['status'])
            bad = SimpleNamespace(**{**vars(req), 'generator': req.generator + 'changed'})
            with self.assertRaisesRegex(ValueError, 'CANDIDATE_REQUEST_IDENTITY'):
                self.candidate.verify_materialized(root, plan, snapshot, bad)
            item = next(a for a in plan.artifacts if a.role != 'PROVENANCE')
            (root / item.path).write_bytes(b'changed stored bytes')
            with self.assertRaises(ValueError):self.candidate.verify_materialized(root, plan, snapshot, req)

    def test_legacy_sidecars_and_invalid_shared_target_objects(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'provenance.json'
            legacy = {'version': '0.2.0', 'artifacts': [{'origins': [{'id': 'A', 'revision': 1}]}]}
            path.write_text(json.dumps(legacy));self.assertEqual(legacy, provenance.read_provenance(path))
            target = 'target_' + hashlib.sha256(b'A').hexdigest()[:24]
            body = {'version': '0.3.0', 'originSets': {'shared': [{'id': 'A', 'revision': 1}]},
                    'artifacts': [{'originSet': 'shared', 'targetObjects': [target]}]}
            path.write_text(json.dumps(body));self.assertEqual([{'id': 'A', 'revision': 1}], provenance.read_provenance(path)['artifacts'][0]['origins'])
            for targets in ([], ['unknown'], [target, target]):
                body['artifacts'][0]['targetObjects'] = targets;path.write_text(json.dumps(body))
                with self.assertRaisesRegex(ValueError, 'PROVENANCE_TARGET_OBJECTS'):provenance.read_provenance(path)
