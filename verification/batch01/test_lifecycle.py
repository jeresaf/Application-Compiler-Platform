"""Batch 01 integration at the compiler and publication boundary."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from compiler_contracts import fingerprint
from filesystem_artifacts import FilesystemArtifactStore, StoreConflict
from engineering.application_evolution.plan import preview
from engineering.demo.pipeline import inputs
from engineering.documents import application as documents
from engineering.jobs import application as jobs
from engineering.reference_application.inspection import HUMAN


def binding(candidate, snapshot, request, plan):
    return {
        'candidate': snapshot.read()['contentDigest'],
        'generator': candidate.generator,
        'compiler': request.compiler,
        'pipeline': request.pipeline,
        'artifactPlan': fingerprint(plan),
    }


class LifecycleIntegrationTests(unittest.TestCase):
    def test_approved_domains_compile_and_reject_stale_generated_source(self):
        for domain in ('payment', 'case-management'):
            with self.subTest(domain=domain), TemporaryDirectory() as temporary:
                root = Path(temporary) / domain
                candidate, snapshot, request, initial = inputs(domain)
                store = FilesystemArtifactStore(root)
                store.apply(initial)
                candidate.verify_materialized(root, initial, snapshot, request)

                refreshed = candidate.plan(snapshot, request, inventory=store.inventory())
                store.apply(refreshed)
                candidate.verify_materialized(root, refreshed, snapshot, request)
                observed = candidate.executions[-1]
                self.assertEqual(observed['canonicalDigest'], snapshot.read()['contentDigest'])
                self.assertEqual(observed['artifactPlanDigest'], fingerprint(refreshed))

                generated = root / 'backend/src/main/java/acp/Application.java'
                changed = generated.read_bytes() + b'\n// unauthorized generated source edit\n'
                generated.write_bytes(changed)
                with self.assertRaises(StoreConflict):
                    store.apply(refreshed)
                self.assertEqual(generated.read_bytes(), changed)

    def test_case_management_preview_regenerates_with_prior_ownership_and_migrations(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary) / 'application'
            old, before, old_request, _ = documents.materialize(root)
            store = FilesystemArtifactStore(root)
            store.adopt_human(HUMAN)
            human = root / HUMAN
            expected_human = human.read_bytes() + b'\n// Batch 01 reviewer continuity.\n'
            human.write_bytes(expected_human)
            old_plan = old.plan(before, old_request, store.inventory())
            store.apply(old_plan)
            old.verify_materialized(root, old_plan, before, old_request)

            new = jobs.JobApplication()
            new_request = new.context.request
            after = new.context.snapshots.read_exact(new_request.application, new_request.snapshot_digest)
            new_plan = new.plan(after, new_request, store.inventory())
            plan = preview(
                before.read(), after.read(), old_plan, new_plan,
                binding(old, before, old_request, old_plan),
                binding(new, after, new_request, new_plan),
            )
            self.assertEqual(plan['semanticApproval'], 'NOT_APPROVED')
            self.assertEqual(plan['migration']['productionApproval'], 'NOT_AUTHORIZED')
            self.assertEqual(plan['migration']['mode'], 'STOP_MIGRATE_RESTART')
            self.assertEqual(len(plan['migration']['existing']), 4)
            self.assertEqual(list(plan['migration']['additions']), [
                'backend/src/main/resources/db/migration/V5__integrity_jobs.sql',
            ])
            old_sql = {name: (root / name).read_bytes() for name in plan['migration']['existing']}

            store.apply(new_plan)
            new.verify_materialized(root, new_plan, after, new_request)
            self.assertEqual(human.read_bytes(), expected_human)
            self.assertEqual({name: (root / name).read_bytes() for name in old_sql}, old_sql)
