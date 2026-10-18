import copy
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'tooling'),str(ROOT/'tooling/tests')]
from engineering.traceability.backend import instrument,closing,sources,REGISTRATION,FAMILIES,verify_results
from compiler_contracts import Document
from canonical_json import load


class BackendTraceTests(unittest.TestCase):
    def test_all_23_families_have_exact_backend_or_browser_assertions(self):
        from engineering.traceability.qualification import STEPS
        self.assertEqual(len(FAMILIES),23)
        for domain in ('payment','case-management'):
            snapshot=Document.of(load(ROOT/f'test-corpus/deterministic-v04/{domain}-canonical-candidate.json'))
            files,bindings,count,classes=sources(domain,snapshot)
            self.assertEqual(len(bindings),16);self.assertGreater(count,60);self.assertEqual(len(classes),6)
            self.assertTrue(all(b['assertion'].startswith('assert') for b in bindings))
            self.assertEqual({b['kind'] for b in bindings},set(REGISTRATION))
            self.assertIn('concurrentWorkersFenceOneSuccessfulLogicalDisposal',files['backend/src/test/java/acp/generated/PrivacyLifecycleTest.java'])
            self.assertIn('contentionProof(2, false, 10_000)',files['backend/src/test/java/acp/generated/PrivacyLifecycleTest.java'])

    def test_literal_braces_lambda_assertions_and_duplicate_registration_fail_closed(self):
        source='class X { @Test void exact() { assertThrows(Exception.class,()->{throw new Exception("{}()");}); } }'
        node={'id':'OBJECT','revision':3}
        changed,binding=instrument(source,'Failure','exact','assertThrows(',node)
        self.assertIn('assertThrows(Exception.class,()->{throw new Exception("{}()");});System.out',changed)
        with self.assertRaises(ValueError):instrument(changed,'Failure','exact','assertThrows(',node)
        with self.assertRaises(ValueError):instrument(source,'Failure','absent','assertThrows(',node)
        with self.assertRaises(ValueError):instrument(source,'Failure','exact','assertFalse(',node)
        with self.assertRaises(ValueError):closing('{',0,'{','}')

    def test_junit_assertion_marker_not_suite_pass_is_required(self):
        # Synthetic fixtures test rejection mechanics; never runtime evidence.
        import json
        from engineering.traceability.qualification import sha
        rows=[];files={};cases=[]
        for kind,(cls,method,_) in REGISTRATION.items():
            src='assertTrue(true);System.out.println('+json.dumps('ACP_ASSERT|'+kind)+');'
            path='test/'+kind+'.java';files[path]=src
            rows.append({'kind':kind,'class':cls,'method':method+kind,'source':path,'sourceSHA256':sha(src.encode()),'assertion':'assertTrue(true);','marker':'ACP_ASSERT|'+kind,'object':kind,'revision':1})
            cases.append('<testcase classname="'+cls+'" name="'+method+kind+'"><system-out>ACP_ASSERT|'+kind+'</system-out></testcase>')
        provenance={'artifacts':[{'origins':[{'id':k,'revision':1} for k in REGISTRATION]}]}
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'TEST.xml'
            xml='<testsuite>'+''.join(cases)+'</testsuite>';path.write_text(xml)
            self.assertEqual(len(verify_results([path],rows,provenance,files,16)),16)
            for bad in (xml.replace('ACP_ASSERT|Entity','forged'),xml.replace('<testcase ','<testcase skipped="1" ',1).replace('<system-out>','<skipped/><system-out>',1),xml.replace(cases[0],'')):
                path.write_text(bad)
                with self.assertRaises(ValueError):verify_results([path],rows,provenance,files,16)
            path.write_text(xml)
            with self.assertRaises(ValueError):verify_results([path],rows,{'artifacts':[]},files,16)
            with self.assertRaises(ValueError):verify_results([path],rows,provenance,{**files,rows[0]['source']:'forged'},16)

    def test_live_test_source_replacement_missing_and_symlink_rejected(self):
        from engineering.traceability.backend import verify_sources
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);files={'test.java':'exact assertion source'}
            path=root/'test.java';path.write_text(files['test.java']);verify_sources(root,files)
            path.write_text('substituted')
            with self.assertRaises(ValueError):verify_sources(root,files)
            path.unlink()
            with self.assertRaises(ValueError):verify_sources(root,files)
            other=root/'other';other.write_text(files['test.java']);path.symlink_to(other)
            with self.assertRaises(ValueError):verify_sources(root,files)
