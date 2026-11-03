"""Owned, disposable PG volume: restart persistence without touching existing volumes."""
from contextlib import contextmanager
import json,os,secrets,subprocess,time
from pathlib import Path
from engineering.generator_builds.runtime import IMAGE,docker
from engineering.source_intelligence.model import require


@contextmanager
def owned_database(active,inventory):
    execution=secrets.token_hex(12)
    name='acp-06-runtime-h2-'+execution
    volume='acp-h2-'+execution
    owner='acp.h2.owner='+execution
    password=secrets.token_hex(24)
    keys=('ACP_TEST_DATABASE_URL','ACP_TEST_DATABASE_USER','ACP_TEST_DATABASE_PASSWORD')
    previous={k:os.environ.get(k) for k in keys}
    record={'container':name,'volume':volume,'owner':execution,'scope':'NEW_DISPOSABLE_H2_DATABASE','image':IMAGE,'cleanup':'PENDING'}
    inventory.append(record)
    created=False;mounted=False
    require(subprocess.run(['docker','volume','inspect',volume],capture_output=True).returncode!=0,'H2_VOLUME_COLLISION')
    require(subprocess.run(['docker','inspect',name],capture_output=True).returncode!=0,'H2_CONTAINER_COLLISION')
    try:
        docker('volume','create','--label',owner,volume);mounted=True
        docker('run','--pull=never','--detach','--name',name,'--label',owner,
               '--publish','127.0.0.1::5432','--mount','type=volume,source='+volume+',target=/var/lib/postgresql',
               '--env','POSTGRES_USER=acp_runtime','--env','POSTGRES_DB=acp_runtime',
               '--env','POSTGRES_PASSWORD='+password,IMAGE,'-c','track_commit_timestamp=on')
        created=True
        port=docker('port',name,'5432/tcp').removeprefix('127.0.0.1:')
        ready(name)
        os.environ.update(ACP_TEST_DATABASE_URL='jdbc:postgresql://127.0.0.1:'+port+'/acp_runtime',
                          ACP_TEST_DATABASE_USER='acp_runtime',ACP_TEST_DATABASE_PASSWORD=password)
        active.append(name)
        yield name
    finally:
        active.clear()
        for k,v in previous.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
        if subprocess.run(['docker','inspect',name],capture_output=True).returncode==0:
            label=docker('inspect','--format','{{index .Config.Labels "acp.h2.owner"}}',name)
            require(label==execution,'H2_CONTAINER_OWNERSHIP_CHANGED')
            docker('stop','--time','5',name)
            docker('rm',name)
        if mounted:
            label=docker('volume','inspect','--format','{{index .Labels "acp.h2.owner"}}',volume)
            require(label==execution,'H2_VOLUME_OWNERSHIP_CHANGED')
            docker('volume','rm',volume)
        record['cleanup']='OWN_CONTAINER_AND_VOLUME_REMOVED'


def ready(container):
    deadline=time.monotonic()+40
    while time.monotonic()<deadline:
        # The image's bootstrap postmaster accepts Unix-socket connections, then
        # shuts down. TCP becomes ready only on the final application server.
        result=subprocess.run(['docker','exec',container,'pg_isready','-h','127.0.0.1','-U','acp_runtime','-d','acp_runtime'],capture_output=True)
        if result.returncode==0:return
        time.sleep(.1)
    raise TimeoutError('H2_DATABASE_READINESS')


def renew_connection(container):
    require(container.startswith('acp-06-runtime-h2-'),'H2_UNOWNED_RESTART')
    owner=container.removeprefix('acp-06-runtime-h2-')
    require(docker('inspect','--format','{{index .Config.Labels "acp.h2.owner"}}',container)==owner,'H2_RESTART_OWNER')
    binding=docker('port',container,'5432/tcp');require(binding.startswith('127.0.0.1:') and binding.count(':')==1,'H2_RESTART_BINDING')
    port=int(binding.split(':')[1]);require(0<port<65536,'H2_RESTART_PORT')
    os.environ['ACP_TEST_DATABASE_URL']='jdbc:postgresql://127.0.0.1:'+str(port)+'/acp_runtime'
    return binding
