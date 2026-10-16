"""Future physical-only wrapper; not selected by offline qualification."""
import hashlib
import json
import os
import subprocess
from pathlib import Path
import time
from test_canonical03_migrations import PostgreSQL03MigrationTests


class PhysicalCapturedTests(PostgreSQL03MigrationTests):
    def psql(self,sql,check=True):
        root=Path(os.environ['ACP_WAVE2_ROOT']).resolve(strict=True)
        log=Path(os.environ['ACP_PHYSICAL_EVIDENCE_LOG'])
        if log.is_symlink() or log.resolve().parent!=root/'pglogs':raise ValueError('TASK_OWNED_CAPTURE_REQUIRED')
        failure=None
        try:
            result=super().psql(sql,check)
        except subprocess.CalledProcessError as error:
            failure=error
            result=subprocess.CompletedProcess(error.cmd,error.returncode,error.stdout or '',error.stderr or '')
        entry={'monotonicNs':time.monotonic_ns(),'sql':sql,'sqlSHA256':hashlib.sha256(sql.encode()).hexdigest(),
               'stdout':result.stdout,'stdoutSHA256':hashlib.sha256(result.stdout.encode()).hexdigest(),
               'stderr':result.stderr,'stderrSHA256':hashlib.sha256(result.stderr.encode()).hexdigest(),
               'exitCode':result.returncode,'proofLevel':'TEST_CLIENT_OBSERVATION_NOT_AUTHENTICATED_ATTESTATION'}
        if len(json.dumps(entry))>1000000:raise ValueError('CAPTURE_LIMIT')
        with log.open('a') as stream:stream.write(json.dumps(entry)+'\n')
        log.chmod(0o600)
        if failure is not None:raise failure
        return result
