"""Stage 1 must add only authorized paths and preserve every pinned baseline byte."""
import ast
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
BASELINE='c1a201c779621963b0334a1bee4423b23315884f'
ALLOWED=('engineering/evidence_admission/', 'verification/evidence_admission/')
DOC='docs/phase6-evidence-admission-contract.md'
BLOCKERS=[5,8,9,10,12,13,14,15,18,20,21,22,24,25,26,27,28,30,31,32,33]
STAGE2A_FILES={
 'engineering/evidence_admission/signatures.py',
 'engineering/evidence_admission/trust.py',
 'engineering/evidence_admission/registration.py',
 'engineering/evidence_admission/requirements.txt',
 'verification/evidence_admission/stage2a/lab_fixtures.py',
 'verification/evidence_admission/stage2a/test_signatures.py',
 'verification/evidence_admission/stage2a/test_trust.py',
 'verification/evidence_admission/stage2a/test_registration.py',
 'docs/phase6-evidence-admission-stage2a.md',
}
# Existing local checkout representations, observed without rewriting any corpus.
# Fresh LF checkouts must match the Git blob; only these exact existing byte
# hashes are permitted as alternatives, never arbitrary normalized file changes.
CHECKOUT_FORMS={
 'test-corpus/canonical/byte-vectors.json':'25a205fe39eb4d2bbf435765110679880de8e99e0d5a39e9cbdd38bfc14158ea',
 'test-corpus/canonical/case-management.json':'6092dfba10dc94cafbb42e738d2ee94a379b6ca082f303f5b4a2dc61a3690d08',
 'test-corpus/canonical/manifest.json':'3ae456668c9ed03052e41e9a6ac8bf9b859ac0230443d943ca00d1fe50ed8215',
 'test-corpus/canonical/payment.json':'dc9ac48b6437182f2cc83d5c522e59bfacd018dbcbfa682391df4264fd0f537b',
 'test-corpus/change/evolution.json':'000703f0ad15085ab8e1e047a662e5a7b8ee212cb852e5ea198129f97a70f1a5',
 'test-corpus/phase1/case-management.json':'95f245c9b53550a778258e4effc7ff5511c9eb431f3f9a2a5ef7438073c38ca5',
 'test-corpus/phase1/cases.json':'c4fa5a1e6608ff99a0b7509f340bc8dc0d725a6f7269594ae38170b8261335a8',
 'test-corpus/phase1/payment.json':'4c08bcd214a7a83ae36e41008a0ceda0b9ee977040f76c226a95c3e697927c56',
 'test-corpus/semantic/approved.json':'c1ccc5692d0aa7e41cc46006ae8b6f73dc2a0351ae74b018f44d2a6a3ae3ea8f',
 'test-corpus/semantic/cases.json':'a7f7c16a63664acccb629a0afab08a990a118390708272d30f0942dc9a1572d0',
 'test-corpus/semantic/reference.json':'84c6c27469f7dc439c6b8b7f74631782c0880b398795e21e71ded1f381fe6b7a',
}


class PreservationTests(unittest.TestCase):
    def test_stage2a_exact_inventory_preserves_accepted_stage1(self):
        accepted='f44f8952ba7e86f879b0c21e1b56de9fbd3d01aa'
        additions=set(subprocess.check_output(['git','diff','--name-only','--diff-filter=A',accepted,'--'],cwd=ROOT,text=True).splitlines())
        additions.update(subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines())
        # Retain only the pre-existing, separately validated transient exception.
        if '.ci-evidence/contracts.json' in additions:
            head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
            self.check_source_additions(['.ci-evidence/contracts.json'],[],head)
            self.assertNotIn('.ci-evidence/contracts.json',subprocess.check_output(['git','diff','--name-only','--diff-filter=A',accepted,'--'],cwd=ROOT,text=True).splitlines())
            additions.remove('.ci-evidence/contracts.json')
        self.assertEqual(additions,STAGE2A_FILES)
        modified=set(subprocess.check_output(['git','diff','--name-only','--diff-filter=MDRT',accepted,'--'],cwd=ROOT,text=True).splitlines())
        self.assertEqual(modified,{'verification/evidence_admission/test_preservation.py'})
        path='verification/evidence_admission/test_preservation.py'
        before=ast.parse(subprocess.check_output(['git','show',accepted+':'+path],cwd=ROOT,text=True))
        after=ast.parse((ROOT/path).read_text())
        old_class=next(n for n in before.body if isinstance(n,ast.ClassDef))
        new_class=next(n for n in after.body if isinstance(n,ast.ClassDef))
        methods={n.name:n for n in new_class.body if isinstance(n,ast.FunctionDef)}
        for method in old_class.body:
            if isinstance(method,ast.FunctionDef):
                if method.name=='check_source_additions':
                    calls=[n for n in ast.walk(method) if isinstance(n,ast.Call) and
                           isinstance(n.func,ast.Attribute) and n.func.attr=='assertTrue']
                    self.assertEqual(len(calls),2)
                    for call in calls:
                        self.assertIsInstance(call.args[0],ast.BoolOp)
                        call.args[0].values.append(ast.parse('path in STAGE2A_FILES',mode='eval').body)
                self.assertEqual(ast.dump(method),ast.dump(methods[method.name]),method.name)
        for node in before.body:
            if not isinstance(node,ast.ClassDef):
                self.assertIn(ast.dump(node),[ast.dump(n) for n in after.body])

    def check_source_additions(self, untracked, added, head):
        # Committed or staged additions never receive the transient exception.
        for path in added:self.assertTrue(path.startswith(ALLOWED) or path==DOC or path in STAGE2A_FILES,path)
        for path in untracked:
            if path == '.ci-evidence/contracts.json':
                self.check_contracts_binding(ROOT/path,head)
            else:self.assertTrue(path.startswith(ALLOWED) or path==DOC or path in STAGE2A_FILES,path)

    def check_contracts_binding(self, path, head):
        self.assertFalse(path.parent.is_symlink(),'SYMLINK_EVIDENCE_DIRECTORY')
        self.assertFalse(path.is_symlink(),'SYMLINK_EVIDENCE_FILE')
        self.assertTrue(path.is_file(),'BINDING_FILE_REQUIRED')
        self.assertLessEqual(path.stat().st_size,4096,'OVERSIZED_SOURCE_BINDING')
        def unique_pairs(pairs):
            result={}
            for key,value in pairs:
                self.assertNotIn(key,result,'DUPLICATE_BINDING_KEY')
                result[key]=value
            return result
        value=json.loads(path.read_bytes().decode('utf-8'),object_pairs_hook=unique_pairs)
        self.assertIs(type(value),dict)
        self.assertEqual(set(value),{'source','run','attempt','job'})
        for item in value.values():self.assertIs(type(item),str)
        self.assertIsNotNone(re.fullmatch(r'[0-9a-f]{40}',value['source']))
        self.assertEqual(value['source'],head,'WRONG_CHECKOUT_SOURCE')
        self.assertEqual(value['job'],'contracts','WRONG_BINDING_JOB')
        for key in ('run','attempt'):
            self.assertIsNotNone(re.fullmatch(r'[1-9][0-9]*',value[key]),'INVALID_CI_IDENTITY')
        for key,variable in (('source','GITHUB_SHA'),('run','GITHUB_RUN_ID'),
                             ('attempt','GITHUB_RUN_ATTEMPT'),('job','GITHUB_JOB')):
            if variable in os.environ:
                self.assertEqual(value[key],os.environ[variable],'WRONG_'+variable)

    def test_transient_contracts_binding_has_exact_structure_and_identity(self):
        head='a'*40
        binding={'source':head,'run':'123','attempt':'2','job':'contracts'}
        environment={'GITHUB_SHA':head,'GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'2','GITHUB_JOB':'contracts'}
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,environment):
            path=Path(directory)/'contracts.json';path.write_text(json.dumps(binding))
            self.check_contracts_binding(path,head)
            for variable in environment:
                with self.subTest(environment=variable),patch.dict(os.environ,{variable:'wrong-current-identity'}):
                    with self.assertRaises(AssertionError):self.check_contracts_binding(path,head)
            for key,bad in (('source','b'*40),('run','124'),('attempt','3'),('job','phase6-target'),
                            ('run',123),('run','01'),('attempt','0'),('attempt','2\n'),('source',head+'\n')):
                value=dict(binding);value[key]=bad;path.write_text(json.dumps(value))
                with self.subTest(key=key,bad=bad),self.assertRaises(AssertionError):
                    self.check_contracts_binding(path,head)
            for missing in binding:
                value=dict(binding);del value[missing];path.write_text(json.dumps(value))
                with self.subTest(missing=missing),self.assertRaises(AssertionError):
                    self.check_contracts_binding(path,head)
            malformed=[json.dumps(dict(binding,extra=True)), 'null', '[]', '{bad',
                       '{"source":"'+head+'","source":"'+head+'","run":"123","attempt":"2","job":"contracts"}']
            for raw in malformed:
                path.write_text(raw)
                with self.subTest(raw=raw),self.assertRaises((AssertionError,ValueError)):
                    self.check_contracts_binding(path,head)
            path.write_bytes(b'\xff')
            with self.assertRaises(UnicodeError):self.check_contracts_binding(path,head)
            path.write_bytes(b' ' * 4097)
            with self.assertRaises(AssertionError):self.check_contracts_binding(path,head)

    def test_transient_exception_never_allows_tracked_or_other_files(self):
        head='a'*40
        with tempfile.TemporaryDirectory() as directory,patch(__name__+'.ROOT',Path(directory)):
            path=ROOT/'.ci-evidence/contracts.json';path.parent.mkdir()
            path.write_text(json.dumps({'source':head,'run':'123','attempt':'2','job':'contracts'}))
            # Clear only hosted identity variables for this synthetic local case.
            with patch.dict(os.environ):
                for key in ('GITHUB_SHA','GITHUB_RUN_ID','GITHUB_RUN_ATTEMPT','GITHUB_JOB'):os.environ.pop(key,None)
                self.check_source_additions(['.ci-evidence/contracts.json'],[],head)
                for untracked,added in (([],['.ci-evidence/contracts.json']),
                                         (['.ci-evidence/contracts.json'],['.ci-evidence/contracts.json']),
                                         (['.ci-evidence/other.json'],[]),
                                         (['.ci-evidence/contracts.json.bak'],[]),
                                         (['unauthorized-source.py'],[]),
                                         ([],['unauthorized-source.py'])):
                    with self.subTest(untracked=untracked,added=added),self.assertRaises(AssertionError):
                        self.check_source_additions(untracked,added,head)
                path.write_text('{}')
                with self.assertRaises(AssertionError):self.check_source_additions(['.ci-evidence/contracts.json'],[],head)

    def test_transient_binding_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);target=root/'target.json'
            target.write_text(json.dumps({'source':'a'*40,'run':'123','attempt':'2','job':'contracts'}))
            link=root/'contracts.json';link.symlink_to(target)
            with self.assertRaises(AssertionError):self.check_contracts_binding(link,'a'*40)
            real=root/'real';real.mkdir();(real/'contracts.json').write_bytes(target.read_bytes())
            alias=root/'alias';alias.symlink_to(real,target_is_directory=True)
            with self.assertRaises(AssertionError):self.check_contracts_binding(alias/'contracts.json','a'*40)

    def test_only_exact_ci_insertion_is_allowed(self):
        workflow=ROOT/'.github/workflows/acp-contracts.yml'
        original=workflow.read_bytes()
        mutations=[
            (workflow,b'node tooling/check_canonical_vectors.mjs',b'true'),
            (workflow,b'needs: [contracts, phase5c-hard-gates]',b'needs: [contracts]'),
            (workflow,b'path: .ci-evidence/contracts.json',b'path: omitted.json'),
            (workflow,b'contents: read',b'contents: write'),
            (workflow,b'run: python3.14 engineering/ci/aggregate.py hosted',b'run: true'),
            (workflow,b'      - name: Verify Stage 1 evidence contract structures\n',b'      - name: Renamed Stage 1 check\n'),
            (ROOT/'tooling/target_worker.py',b'def bundle_digest():',b'def changed_digest():'),
            (ROOT/'test-corpus/deterministic-v04/payment-canonical-candidate.json',None,None),
        ]
        real_read=Path.read_bytes
        for target,old,new in mutations:
            before=real_read(target)
            if old is not None:
                self.assertIn(old,before);changed=before.replace(old,new,1)
            else:changed=before+b' '
            def read(path):return changed if path==target else real_read(path)
            with self.subTest(path=target,change=old),patch.object(Path,'read_bytes',read):
                probe=PreservationTests('test_baseline_bytes_and_pinned_existing_checkout_forms')
                with self.assertRaises(AssertionError):probe.test_baseline_bytes_and_pinned_existing_checkout_forms()
        self.assertEqual(workflow.read_bytes(),original)

    def test_baseline_bytes_and_pinned_existing_checkout_forms(self):
        listing=subprocess.check_output(['git','ls-tree','-r','-z',BASELINE],cwd=ROOT)
        rows=[row.split(b'\t',1) for row in listing.split(b'\0') if row]
        ids=[metadata.split()[2] for metadata,_ in rows]
        raw=subprocess.check_output(['git','cat-file','--batch'],cwd=ROOT,input=b'\n'.join(ids)+b'\n')
        stream=io.BytesIO(raw)
        self.assertEqual(len(rows),852)
        for metadata,name in rows:
            _,kind,size=stream.readline().split();expected=stream.read(int(size));self.assertEqual(stream.read(1),b'\n')
            path=ROOT/name.decode()
            with self.subTest(path=name.decode()):
                self.assertEqual(kind,b'blob')
                self.assertTrue(path.is_file());self.assertFalse(path.is_symlink())
                if name == b'.github/workflows/acp-contracts.yml':
                    marker=b'\n  phase5-experiments:'
                    step=(b'      - name: Verify Stage 1 evidence contract structures\n'
                          b'        run: python3.14 -m unittest discover -s verification/evidence_admission -v\n')
                    self.assertEqual(expected.count(marker),1)
                    expected=expected.replace(marker,step+marker,1)
                actual=path.read_bytes()
                if actual != expected:
                    self.assertEqual(hashlib.sha256(actual).hexdigest(),CHECKOUT_FORMS.get(name.decode()))
                    self.assertEqual(actual.replace(b'\r\n',b'\n'),expected.replace(b'\r\n',b'\n'))
                mode=metadata.split()[0]
                self.assertEqual(bool(path.stat().st_mode & 0o111),mode==b'100755')
        self.assertEqual(stream.read(),b'')
        subprocess.run(['git','diff','--exit-code','--diff-filter=MDRT',BASELINE,'--',':(exclude).github/workflows/acp-contracts.yml'],cwd=ROOT,check=True,capture_output=True)
        added=subprocess.check_output(['git','diff','--name-only','--diff-filter=A',BASELINE,'--'],cwd=ROOT,text=True).splitlines()
        new=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
        head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        self.check_source_additions(new,added,head)

    def test_all_39_criterion_definitions_and_historical_blockers_preserved(self):
        source=(ROOT/'tooling/audit/criteria.py').read_text()
        tree=ast.parse(source)
        numbers=[]
        for node in tree.body:
            if isinstance(node,ast.Assign):
                for target in node.targets:
                    if isinstance(target,ast.Subscript) and isinstance(target.value,ast.Name) and target.value.id=='SPECS' and isinstance(target.slice,ast.Constant):
                        numbers.append(target.slice.value)
        self.assertEqual(numbers,list(range(1,40)))
        evidence=ROOT/'proposals/phase6-route-a-implementation-review/security-remediation/governance-finalization/hosted/38365033881/closure-report.json.gz'
        report=json.loads(gzip.decompress(evidence.read_bytes()))
        self.assertEqual([r['requirement'] for r in report['blockers']],BLOCKERS)
        self.assertEqual(sum(r['status']=='PASS' for r in report['criteria']),18)
        # This is preservation of historical evidence, not a newly executed audit.
        self.assertEqual(report['recommendation'],'PHASE6_CLOSURE_BLOCKED')
        self.assertEqual(report['phase6'],'IN_PROGRESS');self.assertEqual(report['phase7'],'NOT_STARTED')

    def test_exact_current_seal_and_approved_snapshot_bytes(self):
        sys.path.insert(0,str(ROOT/'tooling'))
        from target_worker import bundle_digest
        from deterministic_approval import approved_snapshot
        self.assertEqual(bundle_digest(),'ea19da2aed4182b0f8bc781a2011f949de52a2d4375e67bb7b59346dc75296bb')
        expected={'payment':'sha256:d0f6e8d96a07e8e8358ad8f1f558f9ec3d69fd8008cceb75e82f4f695e3cf47d',
                  'case-management':'sha256:5b3a69bb1d6e0e69ed620cd1dd32d10e8a07cec276583055b53ec03bfdcc6b90'}
        for domain,digest in expected.items():self.assertEqual(approved_snapshot(domain)['contentDigest'],digest)


if __name__=='__main__':unittest.main()
