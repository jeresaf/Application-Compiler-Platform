"""Strict admission with a deterministic scheduler observation in one fixture.

The invocation clock still observes real PostgreSQL commit time. The separate
scheduler clock remains immediately after the original logical occurrence.
Production source and semantics are unchanged.
"""
from pathlib import Path
import runpy
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tooling'),str(ROOT/'tooling/tests')]
from delivery_components import delivery_source as scoped_source
import delivery_job_reference_tests


def deterministic_source(domain):
    source=scoped_source(domain)
    old='var recovered=jobs(action);recovered.activate("JOB-TASK","tenant-one",time.fixed);'
    new='''var schedulerNow=scheduled().add(java.math.BigInteger.ONE);
        var schedulerClock=new InvocationCore.Time(){public java.math.BigInteger now(){return schedulerNow;}public void sleep(long seconds){time.sleep(seconds);}};
        var recovered=new JobRuntime(jdbc,new DataSourceTransactionManager(ds),model,schedulerClock,
            (id,rev,handle)->identity("tenant-one","fixture:operator"),
            java.util.Map.of("JOB-TASK@3","opaque-test-handle"),action);
        recovered.activate("JOB-TASK","tenant-one",schedulerNow);'''
    assert source.count(old)==1
    return source.replace(old,new)


if __name__=='__main__':
    delivery_job_reference_tests.source=deterministic_source
    path=ROOT/'tooling/check_phase6_target.py';sys.argv[0]=str(path)
    runpy.run_path(str(path),run_name='__main__')
