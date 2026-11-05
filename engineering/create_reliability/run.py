"""H4 uses the existing H3 qualification and native H1 generator, with observation only."""
import argparse,json,os,platform,subprocess,types
from pathlib import Path
from engineering.capacity import run as h3
from engineering.create_reliability import fixture,diagnostic
from engineering.reference_application import lifecycle as life
from engineering.source_intelligence.model import sha,require

PACKAGE=Path(__file__).parent

def inventory():return {p.relative_to(life.ROOT).as_posix():sha(p.read_bytes()) for p in sorted(PACKAGE.glob('*.py'))}


def qualify(workspace,*,maven_seed=None,npm_seed=None,offline=False):
    w=Path(workspace).absolute();require(not w.exists(),'H4_COLLISION');w.mkdir(mode=0o700);pins=inventory();commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
    life.save(w/'source.json',{'sourceCommit':commit,'files':pins,'scope':'QUALIFICATION_ONLY'})
    # Private test-fixture port; native generation, predicates and H3 stay intact.
    execute=types.FunctionType(h3.qualify.__code__,{**vars(h3),'fixture':fixture},'h4_native_qualification');execute.__kwdefaults__=h3.qualify.__kwdefaults__
    result=execute(w/'h3',maven_seed=maven_seed,npm_seed=npm_seed,offline=offline)
    for pool in (2,4):diagnostic.execute(w/('pool-'+str(pool)),w/'h3',pool=pool,expected_digest=sha((w/'h3/result.json').read_bytes()))
    require(inventory()==pins,'H4_SOURCE_CHANGED')
    require(result['generator']['generator']=='acp-h1-job-preview-generator/1+sha256:f982b13e43e0efd070ea1b0773da5aedcdbf2486363c6e902f27c36ba00bcb02','H4_GENERATOR_CHANGED')
    proof={'schema':'acp-h4-qualification/1','sourceCommit':commit,'sourceSHA256':pins,'scope':'QUALIFICATION_ONLY','nativeH3ResultSHA256':sha((w/'h3/result.json').read_bytes()),'adapterSHA256':sha(fixture.adapter_source().encode()),'controlledPoolExhaustion':'REPRODUCED_WITH_NATIVE_ERROR_MAPPING','originalH3Create500':'UNRESOLVED_NOT_CAUSALLY_ATTRIBUTED','productionCapacity':'NOT_APPROVED','queueLimit':'NO_NEW_SEMANTICS; H3_PROPOSAL_REMAINS_UNAPPROVED','sealed05':result['sealed05'],'releaseClosure':'BLOCKED','operationalSecurity':'NOT_ESTABLISHED','files':{f'pool-{pool}/{name}':sha((w/f'pool-{pool}'/name).read_bytes()) for pool in (2,4) for name in ('identity.json','pool-observation.json','postgres.log','resources.json','runtime/demo-backend-1011.log')}}
    for pool in (2,4):require(all(r['cleanup']=='OWN_CONTAINER_AND_VOLUME_REMOVED' for r in json.loads((w/f'pool-{pool}/resources.json').read_bytes())),'H4_RESOURCE_LEAK')
    life.save(w/'result.json',proof);return proof


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);p.add_argument('--maven-seed');p.add_argument('--npm-seed');p.add_argument('--offline',action='store_true');a=p.parse_args();qualify(a.workspace,maven_seed=a.maven_seed,npm_seed=a.npm_seed,offline=a.offline)
