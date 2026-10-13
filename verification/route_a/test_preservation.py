"""Executable preservation check against the independently reviewed source checkpoint."""
import subprocess
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
BASELINE='27cbccb34a9ae771c27c7720a967984d0c2d8fdc'


class PreservationTests(unittest.TestCase):
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
            expected=metadata.split()[2]
            self.assertTrue((ROOT/name).is_file(),name)
            actual=subprocess.check_output(['git','hash-object','--path='+name,name],cwd=ROOT,text=True).strip()
            self.assertEqual(expected,actual,name)
            checked+=1
        self.assertGreater(checked,697)
        # Clean filtering accounts for pre-existing working-tree CRLF. Committed
        # Canonical snapshots, historical approvals/inventories and sealed inputs
        # are preserved exactly; release verification separately checks bundle seals.


if __name__=='__main__':unittest.main()
