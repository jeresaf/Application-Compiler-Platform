"""Nonsecret, version-bound laboratory settings; values are deployment inputs."""
from engineering.source_intelligence.model import encode,sha

def profile(*,workers=False,pool=34,stall=3):
    return {'profile':'acp-operational-lab/1','runtimeMode':'development','databaseUserRef':'ACP_DATABASE_USER','databasePasswordRef':'ACP_DATABASE_PASSWORD','poolConnections':pool,'acquisitionTimeoutMs':750,'workersEnabled':workers,'workerConcurrency':2,'workerStallSeconds':stall,'workerPolicy':'CANONICAL_UNMODIFIED','sessionPolicy':'CANONICAL_UNMODIFIED','metricsPolicy':'LOOPBACK_JWT_AND_HOST_READ_CAPABILITY','metricsReadKeyRef':'ACP_METRICS_READ_KEY','logEventsPerSecond':64,'maxHeapMiB':512,'maxProcessors':2}

def write(path,value):
    raw=encode(value)
    with path.open('xb') as f:f.write(raw)
    return {'ACP_OPERATIONAL_CONFIG':str(path.absolute()),'ACP_OPERATIONAL_CONFIG_SHA256':sha(raw)}
