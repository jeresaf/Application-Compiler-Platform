"""Fail-closed profile/observation contracts, distinct from actual host probes."""
import copy
import unittest
from lab_fixtures import profile,runtime
from engineering.evidence_admission.encoding import canonicalize
from engineering.evidence_admission.host_capabilities import digest
from engineering.evidence_admission.isolation import validate_profile,qualification_result,resource_probe,SECCOMP_SPEC
from engineering.evidence_admission.signatures import LabVerificationError


class IsolationTests(unittest.TestCase):
    def test_exact_closed_profile(self):
        value=profile();raw=canonicalize(value)
        self.assertEqual(validate_profile(raw,digest(raw),value['runtimeDigest']),digest(raw))

    def reject_change(self,key,value):
        changed=copy.deepcopy(profile());changed[key]=value;raw=canonicalize(changed)
        with self.assertRaises(LabVerificationError):validate_profile(raw,digest(raw),profile()['runtimeDigest'])

    def test_unapproved_mounts(self):self.reject_change('readOnlyMounts',['/'])
    def test_environment_substitution(self):self.reject_change('environment',{'PATH':'/candidate'})
    def test_namespace_substitution(self):self.reject_change('namespaces',[])
    def test_capability_escalation(self):self.reject_change('capabilities',['CAP_SYS_ADMIN'])
    def test_seccomp_substitution(self):self.reject_change('seccompDigest','sha256:'+'c'*64)
    def test_apparmor_substitution(self):self.reject_change('apparmorProposalDigest','sha256:'+'c'*64)
    def test_runtime_substitution(self):self.reject_change('runtimeDigest','sha256:'+'c'*64)
    def test_unknown_fields(self):self.reject_change('unknown',True)
    def test_unenforced_limits(self):self.reject_change('limits',{'memoryBytes':0})

    def test_unknown_profile_identity(self):
        with self.assertRaises(LabVerificationError):validate_profile(canonicalize(profile()),'sha256:'+'f'*64,profile()['runtimeDigest'])

    def test_closed_seccomp_rejects_forbidden_syscalls(self):
        self.assertEqual(SECCOMP_SPEC['defaultAction'],'ERRNO:EPERM')
        self.assertTrue(set(['mount','unshare','setns','socket','ptrace','bpf']).isdisjoint(SECCOMP_SPEC['allow']))

    def test_missing_or_fabricated_kernel_evidence_never_qualifies(self):
        required=['namespaces','filesystem','controls','descriptors','environment','network','seccomp','capabilities','privateProcesses']
        namespace={'status':'SYNTHETIC_PROBE_PASSED','checks':dict.fromkeys(required,True)}
        resources={m:{'mode':m,'status':'SYNTHETIC_PROBE_PASSED','checks':{'limits':True,'enforcement':True,'cleanup':True},'survivingPids':[]} for m in ['memory','pids','cpu','deadline']}
        for missing in required:
            changed=copy.deepcopy(namespace);changed['checks'][missing]=False
            with self.subTest(missing=missing):
                result=qualification_result(True,True,changed,resources)
                self.assertFalse(result['observationsComplete'])
                self.assertEqual(result['status'],'ISOLATION_QUALIFICATION_BLOCKED')
        for mode in resources:
            changed=copy.deepcopy(resources);changed[mode]['checks']['enforcement']=False
            with self.subTest(mode=mode):self.assertFalse(qualification_result(True,True,namespace,changed)['observationsComplete'])
        for mode in resources:
            changed=copy.deepcopy(resources);changed[mode]['survivingPids']=[123]
            self.assertFalse(qualification_result(True,True,namespace,changed)['observationsComplete'])
        self.assertFalse(qualification_result(True,False,namespace,resources)['observationsComplete'])
        # Complete caller declarations still cannot bypass independent review.
        self.assertEqual(qualification_result(True,True,namespace,resources)['status'],'ISOLATION_QUALIFICATION_BLOCKED')
        self.assertFalse(qualification_result(True,True,{'status':'SYNTHETIC_PROBE_PASSED'}, {})['observationsComplete'])

    def test_no_arbitrary_probe_mode(self):
        with self.assertRaises(LabVerificationError):resource_probe('candidate command')

    def test_no_candidate_or_release_api(self):
        import ast
        from pathlib import Path
        root=Path(__file__).resolve().parents[3]/'engineering/evidence_admission'
        for name in ['isolation.py','host_capabilities.py']:
            tree=ast.parse((root/name).read_text())
            strings={n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)}
            self.assertTrue(strings.isdisjoint({'EVIDENCE_ADMITTED','RELEASE_APPROVED','PHASE6_CLOSURE_RECOMMENDED','LAB_EXECUTION_VERIFIED'}))


if __name__=='__main__':unittest.main()
