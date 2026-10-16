"""Wave 3: pure production planning boundary; no worker launch/build/database."""
import copy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parent)]
from compiler_contracts import ArtifactPlan, Document, Derived, Owner, Provenance, Stage, Subject, TargetIR, fingerprint
from compiler_core import _ownership, CompilerFault
from filesystem_artifacts import FilesystemArtifactStore, StoreConflict, source_bytes, byte_digest
from target_worker import ProductionTarget, PROFILE
from target_provenance import read_provenance, inspect_mapping
ROOT=Path(__file__).resolve().parents[2]
WORKER=ROOT/'targets/spring-vue-postgres/worker'
sys.path.insert(0,str(WORKER))
from model import lower
from generation import plan as generate, validate_plan as validate_rows


def real_plan(domain,version='0.3.0',inventory=()):
    directory='deterministic-v04' if version=='0.3.0' else 'execution-v03'
    suffix='canonical-candidate' if version=='0.3.0' else 'canonical'
    snapshot=json.loads((ROOT/f'test-corpus/{directory}/{domain}-{suffix}.json').read_text())
    model=lower(snapshot['content']['nodes'],PROFILE,version)
    objects=tuple(Derived(n['id'],'LOWER',Document.of(n),Provenance((Subject(snapshot['content']['applicationId'],n['id'],n['revision']),),Stage.LOWER,'compiler/test','pipeline/test',(snapshot['contentDigest'],))) for n in model['nodes'])
    target=TargetIR(PROFILE['profile'],objects,(),(),target_model=Document.of(model))
    request=SimpleNamespace(compiler='compiler/test',pipeline='pipeline/test',snapshot_digest=snapshot['contentDigest'],features=(),generator=PROFILE['generator']+'+sha256:UNSEALED_CANDIDATE')
    templates={p.relative_to(WORKER.parent/'templates').as_posix():p.read_text() for p in (WORKER.parent/'templates').rglob('*') if p.is_file()}
    adapter=object.__new__(ProductionTarget);adapter.bundle='UNSEALED_CANDIDATE'
    def call(operation,payload):
        if operation=='plan':return generate(payload['model'],templates,PROFILE,payload['inventory'],build=payload['build'])
        if operation=='validate-plan':return validate_rows(payload['artifacts'])
        raise AssertionError('Unexpected worker operation')
    # Real host ArtifactPlan adaptation, with pure generator port instead of a
    # subprocess. No release verification, worker confinement or runtime claim.
    with patch.object(adapter,'_call',side_effect=call):
        result=adapter.plan(target,request,inventory=inventory)
    return snapshot,target,request,result


def materialize(plan,root):
    FilesystemArtifactStore(root).apply(plan)
    return read_provenance(root/'acp/provenance.json')


class ProvenanceRedBeforeTests(unittest.TestCase):
    def test_real_generator_subset_is_not_expanded_to_all_nodes(self):
        _,_,_,plan=real_plan('payment')
        with tempfile.TemporaryDirectory() as temp:
            doc=materialize(plan,Path(temp)/'app')
            by_path={a.path:a for a in plan.artifacts}
            narrowed=[m for m in doc['artifacts'] if len(by_path[m['artifact']].mappings)<len(doc['originSets']['canonical-model'])]
            self.assertTrue(narrowed)
            for mapping in narrowed:
                expected={(o.id,o.revision) for o in by_path[mapping['artifact']].mappings}
                self.assertEqual(expected,{(o['id'],o['revision']) for o in mapping['origins']})


class Wave3ParserTests(unittest.TestCase):
    def test_complete_rows_and_first_row_attack(self):
        from test_canonical03_migrations import assert_encoded_rows
        expected={1:'65cc8100f09fa68b27',2:'',3:'27'}
        self.assertEqual(expected,assert_encoded_rows('1|65cc8100f09fa68b27\n2|\n3|27\n',expected))
        # Old [1:] loses this wrong first row; exact IDs/cardinality must reject.
        for text in ('1|ff\n2|\n3|27\n','2|\n3|27\n','1|65cc8100f09fa68b27\n2|\n3|27\n4|27\n','1|65cc8100f09fa68b27\n2|<NULL>\n3|27\n','1|65cc8100f09fa68b27\n2|\n2|27\n','1|zz\n2|\n3|27\n','1|65CC8100F09FA68B27\n2|\n3|27\n'):
            with self.subTest(text=text),self.assertRaises(ValueError):assert_encoded_rows(text,expected)
        self.assertEqual({1:None,2:''},assert_encoded_rows('1|<NULL>\n2|\n',{1:None,2:''}))


def tree_identity(root):
    return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}


class Wave3CompilerIntegrationTests(unittest.TestCase):
    def test_real_plans_upgrade_ownership_and_strict_provenance_both_domains(self):
        from target_provenance import verify_plan_provenance
        for domain in ('payment','case-management'):
            with self.subTest(domain=domain),tempfile.TemporaryDirectory() as temp:
                root=Path(temp)/'app';store=FilesystemArtifactStore(root)
                old_snapshot,_,_,old=real_plan(domain,'0.2.0')
                store.apply(old)
                extension='frontend/src/extensions/identity.ts'
                original_extension=next(a for a in old.artifacts if a.path==extension)
                store.adopt_human(extension)
                human=b'// HUMAN retained exact extension\nexport const identity = "human";\n'
                (root/extension).write_bytes(human)
                inventory=store.inventory()
                snapshot,target,request,new=real_plan(domain,inventory=inventory)
                self.assertNotEqual(old_snapshot['contentDigest'],snapshot['contentDigest'])
                self.assertNotIn(extension,{a.path for a in new.artifacts})
                new=_ownership(new,inventory)
                changed=[a for a in new.artifacts if a.intent=='UPDATE' and a.owner==Owner.COMPILER]
                self.assertTrue(changed)
                before=tree_identity(root)
                ai=replace(changed[0],path='frontend/src/extensions/ai-candidate.ts',owner=Owner.AI,intent='CREATE',expected_digest=None)
                attempt=replace(new,artifacts=(*new.artifacts,ai))
                frameworks=tuple(a.path for a in new.artifacts if a.owner==Owner.FRAMEWORK and a.intent=='UPDATE')
                with self.assertRaisesRegex(StoreConflict,'AI_APPROVAL_REQUIRED'):store.apply(attempt,framework_upgrades=frameworks)
                self.assertEqual(before,tree_identity(root))
                self.assertEqual(inventory,store.inventory())
                store.apply(new,framework_upgrades=frameworks)
                self.assertEqual(human,(root/extension).read_bytes())
                self.assertNotEqual(before,tree_identity(root))
                document=read_provenance(root/'acp/provenance.json')
                required=tuple(Subject(snapshot['content']['applicationId'],n['id'],n['revision']) for n in snapshot['content']['nodes'] if n['kind'] in {'Field','Requirement'})
                result=verify_plan_provenance(root,new,document,target=target,request=request,required_origins=required)
                self.assertEqual('VERIFIED_OFFLINE',result['status'])
                after=tree_identity(root);post_inventory=store.inventory()
                common=dict(target=target,request=request,required_origins=required)
                # Each independent mutation must reject, never a CURRENT shortcut.
                for kind in ('missing','extra','duplicate','stale','digest','ownership','confidence','origin-duplicate','unknown-target'):
                    mutated=copy.deepcopy(document);row=mutated['artifacts'][0]
                    if kind=='missing':mutated['artifacts'].pop()
                    elif kind=='extra':mutated['artifacts'].append({**copy.deepcopy(row),'artifact':'orphan.txt'})
                    elif kind=='duplicate':mutated['artifacts'].append(copy.deepcopy(row))
                    elif kind=='stale':row['origins'][0]['revision']+=1
                    elif kind=='digest':row['artifactDigest']='sha256:'+'0'*64
                    elif kind=='ownership':row['ownership']='HUMAN_OWNED'
                    elif kind=='confidence':row['locationConfidence']='UNKNOWN'
                    elif kind=='origin-duplicate':row['origins'].append(copy.deepcopy(row['origins'][0]))
                    else:row['origins'][0]['id']='UNKNOWN-SEMANTIC-OBJECT'
                    with self.subTest(mutation=kind),self.assertRaises(ValueError):verify_plan_provenance(root,new,mutated,**common)
                with self.assertRaisesRegex(ValueError,'PROVENANCE_SEMANTIC_COVERAGE'):
                    verify_plan_provenance(root,new,document,target=target,request=request,required_origins=(*required,Subject(snapshot['content']['applicationId'],'MISSING',1)))
                bad=replace(new,artifacts=(replace(new.artifacts[0],provenance=replace(new.artifacts[0].provenance,inputs=('wrong',))),*new.artifacts[1:]))
                with self.assertRaisesRegex(ValueError,'PROVENANCE_INPUTS'):verify_plan_provenance(root,bad,document,**common)
                for mutation in ('stale-cas','reassigned','unknown-owner','human-overwrite'):
                    current=_ownership(new,post_inventory)
                    item=next(a for a in current.artifacts if a.owner==Owner.COMPILER)
                    if mutation=='stale-cas':bad=replace(item,expected_digest='sha256:'+'0'*64)
                    elif mutation=='reassigned':bad=replace(item,owner=Owner.AI)
                    elif mutation=='unknown-owner':bad=replace(item,owner='UNKNOWN')
                    else:
                        prior=next(a for a in post_inventory if a.path==extension)
                        bad=replace(original_extension,owner=Owner.HUMAN,intent='UPDATE',expected_digest=prior.digest)
                    with self.subTest(mutation=mutation),self.assertRaises(CompilerFault):store.apply(ArtifactPlan((bad,),()))
                    self.assertEqual(after,tree_identity(root));self.assertEqual(post_inventory,store.inventory())
                # Direct filesystem tampering is independently rejected; the
                # failed publication must preserve the observed tampered tree.
                item=changed[0];(root/item.path).write_bytes(b'tampered\n');tampered=tree_identity(root)
                with self.assertRaisesRegex(StoreConflict,'MANUAL_EDIT'):store.apply(_ownership(new,post_inventory))
                self.assertEqual(tampered,tree_identity(root));self.assertEqual(human,(root/extension).read_bytes())
                print('WAVE3_COMPILER_EVIDENCE '+json.dumps({'domain':domain,'oldSnapshot':old_snapshot['contentDigest'],'newSnapshot':snapshot['contentDigest'],'updatedCompilerFiles':[a.path for a in changed],'beforeTree':before,'afterTree':after,'humanExtensionSHA256':hashlib.sha256(human).hexdigest(),'linkage':result,'authority':'TRACKED_APPROVED_REFERENCE_SEMANTICS_NOT_DEPLOYED_HISTORY','plannerBoundary':'PURE_GENERATOR_AND_REAL_PRODUCTION_TARGET_PLAN_ADAPTER','candidate':'UNSEALED_CANDIDATE'}),flush=True)

    def test_unknown_confidence_and_duplicate_origins_are_not_current(self):
        _,_,_,plan=real_plan('payment')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'app';doc=materialize(plan,root)
            for kind in ('confidence','duplicate'):
                mapping=copy.deepcopy(doc['artifacts'][0])
                if kind=='confidence':mapping['locationConfidence']='UNKNOWN'
                else:mapping['origins'].append(copy.deepcopy(mapping['origins'][0]))
                self.assertEqual('INVALID_MAPPING',inspect_mapping(root,mapping)['status'])

    def test_legacy_provenance_read_preserved_and_target_sets_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'provenance.json'
            legacy={'version':'0.2.0','artifacts':[]};p.write_text(json.dumps(legacy));self.assertEqual(legacy,read_provenance(p))
            for targets in (['unknown'],['target_x','target_x'],[],[False]):
                value={'version':'0.3.0','originSets':{'set':[{'id':'FIELD','revision':1}]},'artifacts':[{'originSet':'set','targetObjects':targets}]}
                p.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError,'PROVENANCE_TARGET_OBJECTS'):read_provenance(p)


class Wave3HistoryTests(unittest.TestCase):
    def test_reference_history_classification_and_exact_replay_both_domains(self):
        from execution_approval import approved_snapshot as execution_snapshot
        from deterministic_approval import approved_snapshot as deterministic_snapshot
        from changes import prepare
        for domain in ('payment','case-management'):
            old=execution_snapshot(domain);new=deterministic_snapshot(domain)
            change_path=ROOT/f'test-corpus/deterministic-v04/{domain}-change.json'
            change=json.loads(change_path.read_text())
            stored=json.loads((ROOT/f'test-corpus/deterministic-v04/{domain}-plan.json').read_text())
            replay=prepare(old,change)
            self.assertEqual(new,replay['candidate']);self.assertEqual(stored['planDigest'],replay['planDigest'])
            self.assertEqual(old['contentDigest'],change['base']['digest'])
            old_nodes={n['id']:n for n in old['content']['nodes']};new_nodes={n['id']:n for n in new['content']['nodes']}
            for id,node in old_nodes.items():
                if node['kind']=='Field' and id in new_nodes:
                    # References legitimately advance their semantic revisions.
                    # Admission above validates exact current references; compare
                    # the type structure/IDs rather than freezing old revisions.
                    def shape(value):
                        if isinstance(value,dict):return {k:shape(v) for k,v in value.items() if k!='revision'}
                        if isinstance(value,list):return [shape(v) for v in value]
                        return value
                    self.assertEqual(shape(node['data']['type']),shape(new_nodes[id]['data']['type']))
            paths=[f'test-corpus/execution-v03/{domain}-{suffix}.json' for suffix in ('canonical','change','plan','authoring')]
            paths += [f'test-corpus/deterministic-v04/{domain}-{suffix}.json' for suffix in ('canonical-candidate','change','plan','proposal-authoring')]
            paths += [f'test-corpus/{corpus}/human-approval.json' for corpus in ('execution-v03','deterministic-v04')]
            paths += [f'proposals/phase6-measured-data-binding-review/{domain}.json','proposals/phase6-evolution-review/historical-authority-inventory.json','docs/phase6-retained-data-inventory-review.md']
            inputs=[]
            for path in paths:
                data=(ROOT/path).read_bytes();value=json.loads(data) if path.endswith('.json') else {}
                version=value.get('content',{}).get('schemaVersion',value.get('changeVersion',value.get('planVersion',value.get('modelVersion',value.get('versions','UNVERSIONED_DOCUMENT')))))
                inputs.append({'path':path,'sha256':hashlib.sha256(data).hexdigest(),'version':version,'offlineReadable':True,'acceptance':'DOCUMENTARY_REFERENCE_ONLY_NOT_DEPLOYED_HISTORY'})
            binding=json.loads((ROOT/f'proposals/phase6-measured-data-binding-review/{domain}.json').read_text())
            self.assertEqual('REVIEW_REQUIRED',binding['status'])
            self.assertIn('AUTHENTIC_HISTORY_UNAVAILABLE',(ROOT/'docs/phase6-retained-data-inventory-review.md').read_text())
            print('WAVE3_HISTORY '+json.dumps({'domain':domain,'inputs':inputs,'semanticContent':'EXISTING_APPROVED_REFERENCE_SEMANTICS','authentication':'EXISTING_PUBLIC_TEST_AUTHORITY_PROOFS_VERIFIED_HISTORICALLY_NOT_OPERATIONAL_HUMAN_AUTHENTICATION','referenceReplay':'EXACT_CANDIDATE_AND_PLAN_DIGEST','planDigest':replay['planDigest'],'baseDigest':old['contentDigest'],'candidateDigest':new['contentDigest'],'anchor':change['base'],'independentDataBindings':'REVIEW_REQUIRED_NOT_APPROVED','syntheticWave12Backfills':'SYNTHETIC_TEST_ONLY','authenticHistory':'AUTHENTIC_HISTORY_UNAVAILABLE_IN_TRACKED_INPUTS','deployment':'ACCEPTED_DEPLOYED_UPGRADE_NOT_PROVEN','offlineSteps':['historical reference proof verification','exact prepare replay','pure generator plans','artifact store materialization'],'unrun':['live PostgreSQL','accepted deployed journal verification','runtime verification']}),flush=True)
