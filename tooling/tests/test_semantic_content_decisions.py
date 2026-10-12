"""Documentary semantic decisions are exact, isolated and never executable authority."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audit.semantic_content_decisions import (PINS, SOURCE, RECORDS, PROPOSALS, expected_record,
    verify_decision, immutable_write, NoExecutionAuthority, signing_request, json_bytes, sha)
from canonical_json import digest
from changes import request, ChangeError
from compiler_contracts import Document, fingerprint
from deterministic_approval import authority, WHEN
from target_migrations import plan_upgrade, MigrationBlocked

ROOT = Path(__file__).resolve().parents[2]


class SemanticContentDecisionTests(unittest.TestCase):
    def inputs(self, domain):
        return (json.loads((RECORDS/(domain+'.json')).read_bytes()),
                json.loads((PROPOSALS/(domain+'-canonical-candidate.json')).read_bytes()),
                (PROPOSALS/(domain+'-change.json')).read_bytes())

    def test_exact_records_are_independent_and_bound_to_reviewed_source(self):
        manifest = json.loads((RECORDS/'manifest.json').read_bytes())
        for domain in PINS:
            record,candidate,change = self.inputs(domain)
            self.assertEqual('APPROVED_CONTENT',verify_decision(domain,record,candidate,change,SOURCE)['status'])
            self.assertEqual(manifest['records'][domain]['decisionRecordDigest'],sha((RECORDS/(domain+'.json')).read_bytes()))
            other = 'case-management' if domain=='payment' else 'payment'
            with self.assertRaises(ValueError):verify_decision(other,record,*self.inputs(other)[1:],SOURCE)
            for key in ('commit','branch'):
                source = {**SOURCE,key:'changed'}
                with self.assertRaises(ValueError):verify_decision(domain,record,candidate,change,source)
            bad = copy.deepcopy(record);bad['source']['commit']='changed'
            with self.assertRaises(ValueError):verify_decision(domain,bad,candidate,change,SOURCE)

    def test_independent_binding_packages_remain_unapproved_and_application_scoped(self):
        folder=ROOT/'proposals/phase6-independent-data-binding-review'
        manifest=json.loads((folder/'manifest.json').read_bytes())
        self.assertFalse(manifest['approvalsIssued'])
        for domain,pin in PINS.items():
            package=json.loads((folder/(domain+'.json')).read_bytes())
            self.assertEqual('REVIEW_REQUIRED',package['status'])
            self.assertEqual(pin['applicationId'],package['applicationId'])
            self.assertEqual(sha((RECORDS/(domain+'.json')).read_bytes()),package['semanticDecisionDigest'])
            self.assertEqual([],package['approvals'])
            self.assertFalse(package['population']['populationApproved'])
            self.assertFalse(package['authenticatedProofIssued'])
            self.assertEqual('NOT_AUTHORIZED',package['migration'])
            self.assertEqual('NOT_AUTHORIZED',package['deployment'])
            self.assertEqual('65cc8100f09fa68b27',package['value'].encode().hex())
            self.assertEqual(fingerprint(package['proposedBinding'],'migration-bindings'),package['bindingDigest'])
            self.assertEqual(manifest['domains'][domain]['packageDigest'],sha((folder/(domain+'.json')).read_bytes()))
            self.assertEqual(manifest['domains'][domain]['notesDigest'],sha((folder/(domain+'.md')).read_bytes()))
            record,candidate,change=self.inputs(domain)
            for key,value in [('scope','SEMANTIC_SECURITY_MIGRATION'),('migration','AUTHORIZED')]:
                expanded=copy.deepcopy(record);expanded[key]=value
                with self.assertRaises(ValueError):verify_decision(domain,expanded,candidate,change,SOURCE)

    def test_candidate_requiredness_classification_and_operation_edits_reject(self):
        for domain in PINS:
            record,candidate,change = self.inputs(domain)
            for kind in ('candidate','requiredness','classification','operation'):
                with self.subTest(domain=domain,kind=kind):
                    edited = copy.deepcopy(candidate)
                    field = next(n for n in edited['content']['nodes'] if n['id']=='EVOLVE-REFERENCE-NOTE')
                    if kind=='requiredness':field['data']['optional']=True
                    elif kind=='classification':field['data']['classification']='SENSITIVE'
                    elif kind=='operation':
                        command=next(n for n in edited['content']['nodes'] if n['kind']=='Command')
                        command['data']['assignments'][0]['value']={'tag':'literal','type':{'kind':'String'},'value':'changed'}
                    else:field['name']='changed candidate'
                    # Even internally rehashed edits cannot inherit the approved decision.
                    edited['contentDigest']=digest(edited['content'],'canonical')
                    with self.assertRaises(ValueError):verify_decision(domain,record,edited,change,SOURCE)
            forged = copy.deepcopy(candidate)
            forged['content']['nodes'][0]['name']='edited without rehash'
            with self.assertRaises(ValueError):verify_decision(domain,record,forged,change,SOURCE)

    def test_changeset_and_compatibility_edits_reject(self):
        for domain in PINS:
            record,candidate,raw = self.inputs(domain)
            for variant in ('intent','compatibility','anchor'):
                changed=json.loads(raw)
                if variant=='intent':changed['intent']='changed'
                elif variant=='compatibility':changed['migration']['compatibility']='BACKWARD'
                else:changed['base']['sequence']=999
                with self.assertRaises(ValueError):verify_decision(domain,record,candidate,json_bytes(changed),SOURCE)

    def test_semantic_record_is_not_full_plan_authority_or_data_approval(self):
        denial=NoExecutionAuthority()
        for domain in PINS:
            record,candidate,change = self.inputs(domain)
            plan=json.loads((PROPOSALS/(domain+'-plan.json')).read_bytes())
            bindings=Document.of(json.loads((PROPOSALS/(domain+'-data-bindings.json')).read_bytes()))
            self.assertEqual({'SEMANTIC','SECURITY','MIGRATION'},set(request(plan)['requiredScopes']))
            # Existing bounded verifier rejects a documentary record as a proof.
            # It uses its existing historical key; no new identity/key/session is invented.
            with self.assertRaises(ChangeError):authority().verify(record,request(plan),WHEN)
            with self.assertRaises(PermissionError):denial.read_accepted_plan(plan['planDigest'])
            with self.assertRaises(PermissionError):denial.read_approved_bindings(plan['planDigest'],fingerprint(bindings,'migration-bindings'))
            before=json.loads((ROOT/'test-corpus/deterministic-v04'/(domain+'-canonical-candidate.json')).read_bytes())
            with self.assertRaisesRegex(MigrationBlocked,'UNACCEPTED_HISTORY'):
                plan_upgrade(Document.of(before),Document.of(candidate),Document.of(plan),bindings,denial)
            self.assertEqual(0,plan['change']['base']['sequence'])
            self.assertEqual('sha256:'+'0'*64,plan['change']['base']['journalDigest'])

    def test_signing_requests_are_exact_unsigned_and_cannot_grant_execution(self):
        for domain in PINS:
            record=(RECORDS/(domain+'.json')).read_bytes()
            stored=json.loads((RECORDS/(domain+'-signing-request.json')).read_bytes())
            self.assertEqual(signing_request(domain,record),stored)
            self.assertEqual(sha(bytes.fromhex(stored['messageHex'])),stored['messageSha256'])
            self.assertIsNone(stored['signature']);self.assertIsNone(stored['keyIdentity'])
            self.assertFalse(stored['payload']['executionAuthority'])
            self.assertNotEqual(stored['messageSha256'],signing_request(domain,record+b' ')['messageSha256'])
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'decision.json'
            immutable_write(path,b'first');immutable_write(path,b'first')
            with self.assertRaises(ValueError):immutable_write(path,b'changed')
            self.assertEqual(b'first',path.read_bytes())


if __name__=='__main__':
    unittest.main()
