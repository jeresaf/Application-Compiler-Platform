"""Executable preservation check against the independently reviewed source checkpoint."""
import hashlib
import subprocess
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
BASELINE='27cbccb34a9ae771c27c7720a967984d0c2d8fdc'


# Exact authorized engineering deltas, never a directory or arbitrary-byte waiver.
AUTHORIZED_ENGINEERING = {
    'tooling/audit/criteria.py': '1e43974820427b8b1058cda2b00b8479b6b53de2',
    'tooling/audit/phase6.py': '1e43974820427b8b1058cda2b00b8479b6b53de2',
    'tooling/tests/test_retained_inventory.py': '6fe58c37a757fe4ff984e7221a2a6cd877164be2',
}


def authorized_object(name, original):
    if name not in AUTHORIZED_ENGINEERING:return original
    commit=AUTHORIZED_ENGINEERING[name]
    raw=subprocess.check_output(['git','show',commit+':'+name],cwd=ROOT)
    assert hashlib.sha256((ROOT/name).read_bytes()).digest()==hashlib.sha256(raw).digest(), name
    return subprocess.check_output(['git','rev-parse',commit+':'+name],cwd=ROOT,text=True).strip()


class PreservationTests(unittest.TestCase):
    def test_authorized_engineering_bindings_reject_mutation(self):
        from unittest.mock import patch
        read=Path.read_bytes
        self.assertEqual(set(AUTHORIZED_ENGINEERING), {'tooling/audit/criteria.py','tooling/audit/phase6.py','tooling/tests/test_retained_inventory.py'})
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
