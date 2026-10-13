"""Stage 1 must add only authorized paths and preserve every pinned baseline byte."""
import ast
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
BASELINE='c1a201c779621963b0334a1bee4423b23315884f'
ALLOWED=('engineering/evidence_admission/', 'verification/evidence_admission/')
DOC='docs/phase6-evidence-admission-contract.md'
BLOCKERS=[5,8,9,10,12,13,14,15,18,20,21,22,24,25,26,27,28,30,31,32,33]
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
                actual=path.read_bytes()
                if actual != expected:
                    self.assertEqual(hashlib.sha256(actual).hexdigest(),CHECKOUT_FORMS.get(name.decode()))
                    self.assertEqual(actual.replace(b'\r\n',b'\n'),expected.replace(b'\r\n',b'\n'))
                mode=metadata.split()[0]
                self.assertEqual(bool(path.stat().st_mode & 0o111),mode==b'100755')
        self.assertEqual(stream.read(),b'')
        subprocess.run(['git','diff','--exit-code','--diff-filter=MDRT',BASELINE,'--'],cwd=ROOT,check=True,capture_output=True)
        added=subprocess.check_output(['git','diff','--name-only','--diff-filter=A',BASELINE,'--'],cwd=ROOT,text=True).splitlines()
        new=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
        for path in new+added:self.assertTrue(path.startswith(ALLOWED) or path==DOC,path)

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
