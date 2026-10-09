"""Adversarial closure inputs cannot turn status labels into evidence."""
import copy
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'audit'))
import criteria


class ClosureEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.now=datetime.now(timezone.utc)
        self.binding={'bundleDigest':'sha256:'+'a'*64,'canonicalDigests':{'payment':'approved-payment','case-management':'approved-case'},'approvalDigest':'approved-record','executionCommit':__import__('subprocess').check_output(['git','rev-parse','HEAD'],text=True).strip()}
        self.xml=self.root/'startup.xml';self.xml.write_text('<testsuite><testcase classname="acp.domain.RuntimeConfigurationContractTest" name="productionConfigurationFailsBeforeActivation"/><testcase classname="acp.domain.RuntimeConfigurationContractTest" name="activeDeliveryRequiresTransport"/></testsuite>')
        self.record={'criterion':16,**self.binding,'evaluatedAt':self.now.isoformat(),'artifacts':[{'path':self.xml.name,'sha256':criteria.sha(self.xml.read_bytes())}]}
    def row(self,record=None,number=16):
        return next(r for r in criteria.assess({'criterionEvidence':{str(number):record or self.record}},root=self.root,binding=self.binding,now=self.now) if r['requirement']==number)
    def test_correct_specific_artifacts_pass_without_status_labels(self):
        self.assertEqual('PASS',self.row()['status'])
    def test_named_test_without_registered_class_is_rejected(self):
        self.xml.write_text('<testsuite><testcase classname="ForgedTest" name="productionConfigurationFailsBeforeActivation"/><testcase classname="ForgedTest" name="activeDeliveryRequiresTransport"/></testsuite>')
        self.record['artifacts'][0]['sha256']=criteria.sha(self.xml.read_bytes())
        self.assertIn('REGISTERED_TEST_SOURCE_REQUIRED',self.row()['failureReason'])
    def test_missing_evidence_never_passes(self):
        rows=criteria.assess({'result':'PASS'},root=self.root,binding=self.binding,now=self.now)
        self.assertTrue(all(r['status']=='BLOCKED' for r in rows))
    def test_stale_bundle_wrong_canonical_and_edited_approval_rejected(self):
        for key in ('bundleDigest','canonicalDigests','approvalDigest','executionCommit'):
            record=copy.deepcopy(self.record);record[key]='edited'
            self.assertEqual('BLOCKED',self.row(record)['status'])
    def test_forged_pass_and_unrelated_test_are_rejected(self):
        self.xml.write_text('<testsuite><testcase name="someOtherPassingTest"/></testsuite>')
        self.record['status']='PASS';self.record['artifacts'][0]['sha256']=criteria.sha(self.xml.read_bytes())
        self.assertIn('INCOMPLETE_CRITERION_TESTS',self.row()['failureReason'])
    def test_nonexistent_or_edited_artifact_rejected(self):
        record=copy.deepcopy(self.record);record['artifacts'][0]['path']='missing.xml'
        self.assertEqual('BLOCKED',self.row(record)['status'])
        self.xml.write_text('edited')
        self.assertIn('MISMATCHED_ARTIFACT_DIGEST',self.row()['failureReason'])
    def test_stale_or_malformed_evidence_rejected(self):
        for value in ('bad-date',(self.now-timedelta(days=2)).isoformat()):
            record=copy.deepcopy(self.record);record['evaluatedAt']=value
            self.assertEqual('BLOCKED',self.row(record)['status'])
    def test_failed_or_skipped_tests_rejected(self):
        for tag in ('failure','error','skipped'):
            self.xml.write_text('<testsuite><testcase name="productionConfigurationFailsBeforeActivation"><'+tag+'/></testcase></testsuite>')
            self.record['artifacts'][0]['sha256']=criteria.sha(self.xml.read_bytes())
            self.assertIn('TEST_NOT_GREEN',self.row()['failureReason'])
    def security(self):
        path=self.root/'security-assessment.json';package=self.root/'application.tar';package.write_bytes(b'production')
        value={'scanAt':self.now.isoformat(),'bundleDigest':self.binding['bundleDigest'],'coverage':['packaged-backend','npm-production','compiler','build-plugins'],'findings':[],'unknownComponents':[],'packages':[{'file':package.name,'sha256':criteria.sha(package.read_bytes())}]}
        path.write_text(json.dumps(value));return value,path,package
    def test_stale_security_scan_and_package_digest_rejected(self):
        value,path,package=self.security();files={p.name:p for p in (path,package)}
        criteria.security(files,self.binding,self.now)
        package.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'MISMATCHED_PACKAGE_DIGEST'):criteria.security(files,self.binding,self.now)
        value['scanAt']=(self.now-timedelta(days=2)).isoformat();path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'STALE_SECURITY_SCAN'):criteria.security(files,self.binding,self.now)
    def test_unsatisfied_deployment_obligation_cannot_be_presented_as_verified(self):
        path=self.root/'deployment-review.json';path.write_text(json.dumps({'criteria':{'27':{'status':'PASS','verification':'VERIFIED'}}}))
        with self.assertRaisesRegex(ValueError,'UNSATISFIED_DEPLOYMENT_OBLIGATION'):criteria.deployment({path.name:path},27,{})
    def test_unapproved_semantic_migration_rejected(self):
        path=self.root/'accepted-deployed-evolution.json';path.write_text(json.dumps({'domains':{'payment':{'snapshotDigest':'unapproved','planDigest':'invented'}}}))
        with self.assertRaisesRegex(ValueError,'UNAPPROVED_SEMANTIC_MIGRATION'):criteria.evolution({path.name:path},self.binding)
    def test_incomplete_database_upgrade_rejected(self):
        from deterministic_approval import record
        from unittest.mock import patch
        approved=record();domains={}
        for e in approved['examples']:
            domains[e['domain']]={'snapshotDigest':e['request']['contentDigest'],'planDigest':e['request']['planDigest'],'proof':e['proof'],'approvalRequest':e['request'],'appliedMigrationDigests':[],'expectedMigrationDigests':['required']}
        path=self.root/'accepted-deployed-evolution.json';path.write_text(json.dumps({'domains':domains}))
        with self.assertRaisesRegex(ValueError,'INCOMPLETE_DATABASE_UPGRADE'):criteria.evolution({path.name:path},self.binding)


if __name__=='__main__':unittest.main()
