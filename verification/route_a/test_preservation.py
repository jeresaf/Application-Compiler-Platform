"""Executable preservation check against the independently reviewed source checkpoint."""
import hashlib
import subprocess
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
BASELINE='27cbccb34a9ae771c27c7720a967984d0c2d8fdc'


# Exact authorized engineering deltas, never a directory or arbitrary-byte waiver.
AUTHORIZED_ENGINEERING = {
    # Authorized current delivery docs; historical decisions remain unchanged.
    'DEV_LINUX.md': 'ae2d12b13228a71752f501294c97c63dab3ca3b4',
    'docs/roadmap.md': 'ae2d12b13228a71752f501294c97c63dab3ca3b4',
    'tooling/audit/criteria.py': '1e43974820427b8b1058cda2b00b8479b6b53de2',
    'tooling/audit/phase6.py': '1e43974820427b8b1058cda2b00b8479b6b53de2',
    'tooling/tests/test_retained_inventory.py': '6fe58c37a757fe4ff984e7221a2a6cd877164be2',
}


PHASE7_DOC_HASHES = {'DEV_LINUX.md': '5c695670cf16abc491a0e67814f738d933a21857e8984a2de9bdae012750262b', 'docs/roadmap.md': 'e624826a3de27f49d341a4f018eac1c6cbaaf4e27d5a67b22def7f12f67e75ad', 'README.md': '45e74e0455a8b06f89df1a96f615c2f516dd2dfd28824fffbdfbef2541ede6b9'}

PHASE8_DOC_HASHES = {'README.md': 'f509489a12080ffa69bb167ea4a1d7330f8f372c41fc60424de538ab18bc1623', 'DEV_LINUX.md': '039c6541c7858aca8f4bff7bac56c04776bbfaee7587f41b91f5ff1195371ff7', 'docs/roadmap.md': 'fa9b63945eab68c9ae565c3fd8535e0b202a86a17787ade9a731b3df75d3817e'}

PHASE9_DOC_HASHES = {'README.md': '404ee312fbdaac2e396d6279272d07266cf21ef4571def19c79a307f288a8e71', 'DEV_LINUX.md': 'de2b0d811715eb56670239d987b4d3f1fbe139bcbe1dea97ae4c40bad190ac97', 'docs/roadmap.md': '3d1199f5b662b05ce8ccfdb3334f2b0b421a7b39b447a44c5841424e34a2439b'}

PHASE10_DOC_HASHES = {'README.md': 'c2c0d72e705bf7c0d8f25f84e64bc9fecf97baf4f32eda382fd59d72076db375', 'DEV_LINUX.md': '942a286fc2a447746c13fac505521d0f59d30a1584dcdb2924d03abc8bacba79', 'docs/roadmap.md': '16e990c877188b9ac8e614091a1a2ca4ab39be5a63d0645db9aa837a259d2c68'}

def authorized_object(name, original):
    if name in PHASE10_DOC_HASHES:
        raw=(ROOT/name).read_bytes()
        assert not (ROOT/name).is_symlink() and hashlib.sha256(raw).hexdigest()==PHASE10_DOC_HASHES[name], name
        return subprocess.check_output(['git','hash-object','--stdin'],input=raw,cwd=ROOT).decode().strip()
    if name in PHASE9_DOC_HASHES:
        raw=(ROOT/name).read_bytes()
        assert not (ROOT/name).is_symlink() and hashlib.sha256(raw).hexdigest()==PHASE9_DOC_HASHES[name], name
        return subprocess.check_output(['git','hash-object','--stdin'],input=raw,cwd=ROOT).decode().strip()
    if name in PHASE8_DOC_HASHES:
        raw=(ROOT/name).read_bytes()
        assert not (ROOT/name).is_symlink() and hashlib.sha256(raw).hexdigest()==PHASE8_DOC_HASHES[name], name
        return subprocess.check_output(['git','hash-object','--stdin'],input=raw,cwd=ROOT).decode().strip()
    if name in PHASE7_DOC_HASHES:
        raw=(ROOT/name).read_bytes()
        assert not (ROOT/name).is_symlink() and hashlib.sha256(raw).hexdigest()==PHASE7_DOC_HASHES[name], name
        return subprocess.check_output(['git','hash-object','--stdin'],input=raw,cwd=ROOT).decode().strip()
    if name not in AUTHORIZED_ENGINEERING:return original
    commit=AUTHORIZED_ENGINEERING[name]
    raw=subprocess.check_output(['git','show',commit+':'+name],cwd=ROOT)
    assert hashlib.sha256((ROOT/name).read_bytes()).digest()==hashlib.sha256(raw).digest(), name
    return subprocess.check_output(['git','rev-parse',commit+':'+name],cwd=ROOT,text=True).strip()


class PreservationTests(unittest.TestCase):
    def test_authorized_engineering_bindings_reject_mutation(self):
        from unittest.mock import patch
        read=Path.read_bytes
        self.assertEqual(set(AUTHORIZED_ENGINEERING), {'tooling/audit/criteria.py','tooling/audit/phase6.py','tooling/tests/test_retained_inventory.py','DEV_LINUX.md','docs/roadmap.md'})
        self.assertEqual(authorized_object('unregistered.py','original'),'original')
        for name in AUTHORIZED_ENGINEERING:
            path=ROOT/name
            authorized_object(name,'old')
            with patch.object(Path,'read_bytes',lambda item: read(item)+b'unreviewed' if item==path else read(item)):
                with self.assertRaises(AssertionError):authorized_object(name,'old')

    def test_all_unauthorized_tracked_inputs_remain_exactly_unchanged(self):
        allowed=('engineering/route_a_gateway/','verification/route_a/',
                 'docs/phase6-route-a-',
                 'proposals/phase6-route-a-implementation-review/security-remediation/')
        # Explicit CI-only authorization at 0057b008 permits a checked scheduling delta.
        from engineering.ci.parity import verify
        verify()
        listing=subprocess.check_output(['git','ls-tree','-r',BASELINE],cwd=ROOT,text=True)
        checked=0
        for row in listing.splitlines():
            metadata,name=row.split('\t',1)
            if name.startswith(allowed) or name == '.github/workflows/acp-contracts.yml':continue
            expected=authorized_object(name,metadata.split()[2])
            self.assertTrue((ROOT/name).is_file(),name)
            actual=subprocess.check_output(['git','hash-object','--path='+name,name],cwd=ROOT,text=True).strip()
            self.assertEqual(expected,actual,name)
            checked+=1
        self.assertGreater(checked,697)
        # Clean filtering accounts for pre-existing working-tree CRLF. Committed
        # Canonical snapshots, historical approvals/inventories and sealed inputs
        # are preserved exactly; release verification separately checks bundle seals.


if __name__=='__main__':unittest.main()
