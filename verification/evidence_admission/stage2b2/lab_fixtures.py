"""Closed synthetic identity fixtures. No operational authority or workload input."""
from engineering.evidence_admission.encoding import canonicalize
from engineering.evidence_admission.host_capabilities import FEATURES,digest
from engineering.evidence_admission.isolation import profile_for


def runtime():
    return {'qualificationInterpreterDigest':'sha256:'+'c'*64,'schema':'acp-phase6-lab-runtime/1','binaryPath':'/usr/bin/bwrap','binaryDigest':'sha256:'+'a'*64,
            'package':'bubblewrap 0.9.0-1ubuntu0.3 amd64','architecture':'x86_64','kernel':'synthetic-kernel',
            'osRelease':'synthetic Ubuntu 24.04','libraries':[{'path':'/synthetic/libc','sha256':'sha256:'+'b'*64}],
            'features':list(FEATURES)}


def profile():
    return profile_for(digest(canonicalize(runtime())))
