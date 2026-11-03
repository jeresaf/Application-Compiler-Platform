import copy,json,os,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
from engineering.reliability.fixture import adapter_source
from engineering.reliability import database
from engineering.hardening.target import HardeningTarget


class Contract(unittest.TestCase):
    def test_h1_generator_is_unchanged(self):
        self.assertEqual(HardeningTarget().bundle,'f982b13e43e0efd070ea1b0773da5aedcdbf2486363c6e902f27c36ba00bcb02')
    def test_response_buffer_is_outside_real_controller_transaction(self):
        text=adapter_source();self.assertIn('ContentCachingResponseWrapper',text)
        start=text.index('var buffered=');end=text.index('buffered.copyBodyToResponse()',start)
        self.assertLess(text.index('chain.doFilter(request,buffered)',start,end),text.index('pg_advisory_xact_lock',start,end))
    def test_session_initialization_uses_real_policy(self):
        text=adapter_source();self.assertIn('h2Policy.actor(jwt)',text);self.assertIn('WHERE tenant=? AND subject=? AND sid=?',text)
    def test_distinct_peer_has_bound_principal_and_tenant(self):
        text=adapter_source();self.assertIn('browser-report-tenant-two-peer',text);self.assertIn('h2-tenant-two-peer',text);self.assertEqual(text.count('token.startsWith("browser-report-tenant-two")'),2)
    def test_unowned_restart_rejected(self):
        with self.assertRaisesRegex(ValueError,'H2_UNOWNED_RESTART'):database.renew_connection('existing-production')
    def test_wrong_restart_owner_rejected(self):
        with patch.object(database,'docker',return_value='other'):
            with self.assertRaisesRegex(ValueError,'H2_RESTART_OWNER'):database.renew_connection('acp-06-runtime-h2-unit')
    def test_unregistered_evolution_target_rejected(self):
        from engineering.application_evolution.plan import preview
        import json
        from pathlib import Path
        before=json.loads(Path('proposals/phase10-r6-documents/candidate.json').read_bytes());after=json.loads(Path('proposals/phase10-r7-jobs/candidate.json').read_bytes())
        with self.assertRaisesRegex(ValueError,'EVOLUTION_UNREGISTERED_SUCCESSOR'):preview(before,after,None,None,None,None,successor=object())

    def test_h1_evolution_target_is_exactly_bound(self):
        from verification.application_evolution.test_plan import Planning
        from engineering.application_evolution.plan import preview
        Planning.setUpClass();p=Planning;target=HardeningTarget();identity={**p.i7,'generator':target.generator}
        result=preview(p.before,p.after,p.a,p.b,p.i6,identity,successor=target)
        self.assertEqual(result['after']['generator'],target.generator);self.assertEqual(result['change'],p.plan['change'])

    def test_mutated_h1_evolution_identity_rejected(self):
        from verification.application_evolution.test_plan import Planning
        from engineering.application_evolution.plan import preview
        Planning.setUpClass();p=Planning;target=HardeningTarget();target.generator='forged'
        with self.assertRaisesRegex(ValueError,'EVOLUTION_SUCCESSOR_BINDING'):preview(p.before,p.after,p.a,p.b,p.i6,{**p.i7,'generator':'forged'},successor=target)

    def test_default_r8_plan_is_byte_equivalent_to_h1_baseline(self):
        from verification.application_evolution.test_plan import Planning
        from engineering.application_evolution.plan import preview
        Planning.setUpClass();p=Planning
        source=subprocess.check_output(['git','show','e5dc9e0d5206e011e70c560270ef29084f8a2ead:engineering/application_evolution/plan.py'],text=True)
        namespace={'__name__':'h2_original_r8_unit','__file__':str(Path('engineering/application_evolution/plan.py').absolute())};exec(compile(source,'original-r8-unit','exec'),namespace)
        self.assertEqual(preview(p.before,p.after,p.a,p.b,p.i6,p.i7),namespace['preview'](p.before,p.after,p.a,p.b,p.i6,p.i7))

    def test_wrong_hosted_runner_rejected_before_work(self):
        from engineering.reliability.run import qualify
        with patch.dict(os.environ,{'GITHUB_ACTIONS':'true'}),patch('platform.system',return_value='Darwin'):
            with self.assertRaisesRegex(ValueError,'H2_WRONG_HOSTED_RUNNER'):qualify('/tmp/h2-must-not-create')

    def test_wrong_hosted_source_rejected_before_work(self):
        from engineering.reliability.run import qualify
        real=Path.read_text
        with patch.dict(os.environ,{'GITHUB_ACTIONS':'true','GITHUB_SHA':'wrong'}),patch('platform.system',return_value='Linux'),patch('platform.python_version',return_value='3.14.7'),patch.object(Path,'read_text',lambda p,*a,**k:'ID=ubuntu\nVERSION_ID="24.04"\n' if str(p)=='/etc/os-release' else real(p,*a,**k)):
            with self.assertRaisesRegex(ValueError,'H2_WRONG_HOSTED_SOURCE'):qualify('/tmp/h2-must-not-create')

    def test_bootstrap_socket_does_not_satisfy_readiness(self):
        from types import SimpleNamespace
        calls=[]
        def run(args,**kwargs):calls.append(args);return SimpleNamespace(returncode=0)
        with patch.object(database.subprocess,'run',side_effect=run):database.ready('unit-synthetic')
        self.assertEqual(calls[0][calls[0].index('-h')+1],'127.0.0.1')

    def test_framework_upgrade_rejects_unregistered_path(self):
        from types import SimpleNamespace
        from compiler_contracts import Owner
        from engineering.reliability.run import H2ArtifactStore
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            store=H2ArtifactStore(Path(folder)/'application')
            plan=SimpleNamespace(artifacts=(SimpleNamespace(owner=Owner.FRAMEWORK,intent='UPDATE',path='frontend/package.json'),))
            with self.assertRaisesRegex(ValueError,'H2_UNREGISTERED_FRAMEWORK_UPGRADE'):store.apply(plan)

    def test_framework_upgrade_rejects_substituted_pom(self):
        from types import SimpleNamespace
        from compiler_contracts import Owner,Document
        from engineering.reliability.run import H2ArtifactStore
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            store=H2ArtifactStore(Path(folder)/'application')
            plan=SimpleNamespace(artifacts=(SimpleNamespace(owner=Owner.FRAMEWORK,intent='UPDATE',path='backend/pom.xml',content=Document.of({'text':'unapproved replacement'})),))
            with self.assertRaisesRegex(ValueError,'H2_FRAMEWORK_CONTENT_BINDING'):store.apply(plan)

    def test_native_framework_rejection_publishes_nothing(self):
        from compiler_contracts import Artifact,ArtifactPlan,Document,Owner,Provenance,Subject,Stage,fingerprint
        from filesystem_artifacts import FilesystemArtifactStore,StoreConflict
        from engineering.reference_application.lifecycle import tree
        import tempfile
        origin=(Subject('UNIT','UNIT-REQUIREMENT',1),)
        def plan(text,prior=None):
            doc=Document.of({'encoding':'UTF-8','text':text})
            return ArtifactPlan((Artifact('backend/pom.xml','BUILD',doc,fingerprint(doc,'artifact-content'),Owner.FRAMEWORK,Provenance(origin,Stage.GENERATE,'unit','unit',()),origin,'CREATE' if prior is None else 'UPDATE',prior,'COMPARE_AND_SWAP',('unit-only',),()),),())
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'application';store=FilesystemArtifactStore(root);store.apply(plan('original'));before=tree(root)
            with self.assertRaisesRegex(StoreConflict,'FRAMEWORK_UPGRADE_REQUIRED'):store.apply(plan('changed',store.inventory()[0].digest))
            self.assertEqual(tree(root),before)

    def test_restore_authentication_is_fresh_and_separate_from_captured_session(self):
        from types import SimpleNamespace
        from engineering.reliability.run import restored_session,evolution
        old={'ACP_DEMO_AUTH_EVENT':'2020-01-01T00:00:00Z','ACP_H2_SESSION_NAMESPACE':'captured-'}
        def session(*a,**k):return SimpleNamespace(env=dict(old))
        with patch.object(evolution,'session',side_effect=session):
            one=restored_session();two=restored_session()
        self.assertNotEqual(one.env['ACP_DEMO_AUTH_EVENT'],old['ACP_DEMO_AUTH_EVENT'])
        self.assertNotEqual(one.env['ACP_H2_SESSION_NAMESPACE'],old['ACP_H2_SESSION_NAMESPACE'])
        self.assertNotEqual(one.env['ACP_H2_SESSION_NAMESPACE'],two.env['ACP_H2_SESSION_NAMESPACE'])
        self.assertEqual(old,{'ACP_DEMO_AUTH_EVENT':'2020-01-01T00:00:00Z','ACP_H2_SESSION_NAMESPACE':'captured-'})

    def test_reference_validation_is_equivalent_to_accepted_baseline(self):
        from engineering.source_intelligence.model import validate,sealed
        import copy
        source=subprocess.check_output(['git','show','e5dc9e0d5206e011e70c560270ef29084f8a2ead:engineering/source_intelligence/model.py'],text=True)
        old={'__name__':'h2_original_model_unit'};exec(compile(source,'original-model-unit','exec'),old)
        model={'schema':'acp-source-model/1','scope':'ANALYSIS_ONLY','bindingDigest':'unit','identity':{},'files':[{'path':'unit.java','sha256':'unit'}],'symbols':[{'id':i,'confidence':'KNOWN','location':{'file':'unit.java'},'sourceHash':'unit'} for i in ('a','b')],'externalSymbols':[{'id':'external'}],'references':[{'from':'a','to':i,'confidence':'KNOWN','location':{'file':'unit.java'}} for i in ('b','external')],'typeRelations':[{'from':None,'to':None,'confidence':'UNKNOWN','location':{'file':'unit.java'}}],'semanticMappings':[{'symbol':'a','confidence':'KNOWN','artifactSHA256':'unit','bindingDigest':'unit'}],'artifactMappings':[],'diagnostics':['explicitly synthetic unit model'],'drift':[],'completeness':{'confidence':'UNKNOWN','fullyResolved':False}}
        mutations=[lambda m:None,lambda m:m['references'][0].update(to='unbound'),lambda m:m['typeRelations'][0].update(to='a'),lambda m:m['references'][0].update(**{'from':'unbound'}),lambda m:m['symbols'][1].update(id='a'),lambda m:m['externalSymbols'][0].update(id='a'),lambda m:m['symbols'][0].update(sourceHash='forged'),lambda m:m['completeness'].update(fullyResolved=True)]
        for change in mutations:
            value=copy.deepcopy(model);change(value);value=sealed(value);out=[]
            for function in (old['validate'],validate):
                try:out.append(('PASS',function(value)))
                except ValueError as error:out.append(('REJECT',str(error)))
            self.assertEqual(out[0],out[1])
        self.assertEqual(validate(sealed(model)),old['validate'](sealed(model)))
