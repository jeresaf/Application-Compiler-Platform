"""Differential native behavior and prohibition on laboratory release promotion."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from test_manifest import Fixture,ROOT,canonicalize
from tooling.audit import criteria
from tooling.audit.scoped_admission import release_bridge,inspect_submission

BASELINE='17ab4b2a533bc112cfbc8d73796347de94d938b6'


class BridgeTests(unittest.TestCase):
    def test_semantic_function_bodies_and_39_specs_are_unchanged(self):
        raw=subprocess.check_output(['git','show',BASELINE+':tooling/audit/criteria.py'],cwd=ROOT,text=True)
        old=ast.parse(raw);new=ast.parse((ROOT/'tooling/audit/criteria.py').read_text())
        functions=lambda t:{n.name:ast.dump(n) for n in t.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name!='junit'}
        self.assertEqual(functions(old),functions(new))
        assignments=lambda t:[ast.dump(n) for n in t.body if isinstance(n,(ast.Assign,ast.AugAssign,ast.For))]
        self.assertEqual(assignments(old),assignments(new))
        self.assertEqual(set(criteria.SPECS),set(range(1,40)))
        # Native junit AST is unchanged after removing exactly the explicit lab hook.
        jold=next(n for n in old.body if isinstance(n,ast.FunctionDef) and n.name=='junit')
        jnew=next(n for n in new.body if isinstance(n,ast.FunctionDef) and n.name=='junit')
        self.assertIsInstance(jnew.body[0],ast.If);self.assertEqual(ast.unparse(jnew.body[0].test),'external_registration is not None')
        jnew.body=jnew.body[1:];jnew.args=jold.args
        self.assertEqual(ast.dump(jold),ast.dump(jnew))

    def test_native_junit_differential_positive_and_negative(self):
        raw=subprocess.check_output(['git','show',BASELINE+':tooling/audit/criteria.py'],cwd=ROOT,text=True)
        # Trusted baseline evaluator only. No candidate-provided Python is evaluated.
        ns={'__file__':str(ROOT/'tooling/audit/criteria.py'),'__name__':'trusted_baseline_criteria'};exec(compile(raw,'trusted baseline','exec'),ns)
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'test.xml'
            for xml,required in [('<testsuite><testcase name="x"/></testsuite>',['x']),('<testsuite><testcase name="x"><skipped/></testcase></testsuite>',['x']),('<testsuite><testcase name="x"/></testsuite>',['missing'])]:
                p.write_text(xml)
                def result(fn):
                    try:return ('ok',fn({'test.xml':p},required))
                    except Exception as e:return (type(e).__name__,str(e))
                self.assertEqual(result(ns['junit']),result(criteria.junit))
            p.write_text('<testsuite><testcase classname="acp.domain.RuntimeConfigurationContractTest" name="productionConfigurationFailsBeforeActivation"/></testsuite>')
            for fn in (ns['junit'],criteria.junit):
                self.assertIsNone(fn({'test.xml':p},['productionConfigurationFailsBeforeActivation'],BASELINE))

    def test_all_39_native_rows_differential_missing_and_unrelated_evidence(self):
        raw=subprocess.check_output(['git','show',BASELINE+':tooling/audit/criteria.py'],cwd=ROOT,text=True)
        ns={'__file__':str(ROOT/'tooling/audit/criteria.py'),'__name__':'trusted_baseline_criteria'};exec(compile(raw,'trusted baseline','exec'),ns)
        from test_manifest import NOW
        for report in ({'criterionEvidence':{}},{'criterionEvidence':{'8':{'criterion':9}}}):
            self.assertEqual(ns['assess'](report,binding={'executionCommit':BASELINE},now=NOW),criteria.assess(report,binding={'executionCommit':BASELINE},now=NOW))

    def test_external_junit_is_explicit_and_never_reaches_release(self):
        f=Fixture();self.addCleanup(f.close);q=f.run()
        files={a['path']:f.artifacts/a['path'] for a in f.m['artifacts']}
        criteria.junit(files,['externalWitness'],q.application_commit,external_registration=q)
        with self.assertRaises(ValueError):criteria.junit(files,['externalWitness'],q.application_commit)
        with self.assertRaises(ValueError):release_bridge(q)
        wrong=dict(files);wrong['payment.xml']=f.source/'Witness.java'
        with self.assertRaisesRegex(ValueError,'UNRELATED_ARTIFACT_ROOT'):
            criteria.junit(wrong,['externalWitness'],q.application_commit,external_registration=q)
        self.assertEqual(inspect_submission(canonicalize(f.m))['releaseClosure'],'PHASE6_RELEASE_CLOSURE_BLOCKED')

    def test_no_other_phase6_infrastructure_changed(self):
        old=ast.parse(subprocess.check_output(['git','show',BASELINE+':tooling/audit/phase6.py'],cwd=ROOT,text=True))
        new=ast.parse((ROOT/'tooling/audit/phase6.py').read_text())
        new.body=[n for n in new.body if not(isinstance(n,ast.FunctionDef) and n.name=='laboratory_evidence_notice')]
        self.assertEqual(ast.dump(old),ast.dump(new))
