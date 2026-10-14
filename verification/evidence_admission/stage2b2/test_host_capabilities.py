"""Identity verification negatives; these do not constitute kernel enforcement."""
import copy
import unittest
from lab_fixtures import runtime
from engineering.evidence_admission.encoding import canonicalize
from engineering.evidence_admission.host_capabilities import digest,verify_runtime
from engineering.evidence_admission.signatures import LabVerificationError


class RuntimeTests(unittest.TestCase):
    def test_exact_synthetic_runtime_identity(self):
        value=runtime();raw=canonicalize(value)
        self.assertEqual(verify_runtime(value,raw,digest(raw)),digest(raw))

    def test_unsupported_version_even_if_pinned(self):
        value=runtime();value['package']='bubblewrap 0.8.0 amd64';raw=canonicalize(value)
        with self.assertRaises(LabVerificationError):verify_runtime(value,raw,digest(raw))

    def test_binary_substitution(self):self.reject_change('binaryDigest','sha256:'+'c'*64)
    def test_library_substitution(self):self.reject_change('libraries',[])
    def test_architecture_substitution(self):self.reject_change('architecture','aarch64')
    def test_kernel_substitution(self):self.reject_change('kernel','changed-kernel')
    def test_feature_substitution(self):self.reject_change('features',[])
    def test_unknown_runtime_fields(self):self.reject_change('unknown','candidate')

    def reject_change(self,key,value):
        original=runtime();raw=canonicalize(original);changed=copy.deepcopy(original);changed[key]=value
        with self.assertRaises(LabVerificationError):verify_runtime(changed,raw,digest(raw))

    def test_no_arbitrary_command_observation(self):
        from engineering.evidence_admission.host_capabilities import _observe_command
        for candidate in [['/bin/sh','-c','candidate'],'candidate','/bin/sh']:
            with self.assertRaises(LabVerificationError):_observe_command(candidate)

    def test_wrong_pin_digest(self):
        value=runtime()
        with self.assertRaises(LabVerificationError):verify_runtime(value,canonicalize(value),'sha256:'+'f'*64)

    def test_missing_namespace_control(self):
        value=runtime();value['features'].remove('--unshare-user');raw=canonicalize(value)
        with self.assertRaises(LabVerificationError):verify_runtime(value,raw,digest(raw))


if __name__=='__main__':unittest.main()
