"""Verify exact sealed build and immutable prior released identities."""
import json
from pathlib import Path
import subprocess
from target_worker import ROOT,PROFILE,bundle_digest
from target_release import verify_release,verify_preserved_releases

def check():
    current=json.loads((ROOT/'release-contract.json').read_text())
    verify_release(PROFILE,bundle_digest(),current)
    prior=subprocess.run(['git','show','HEAD^:targets/spring-vue-postgres/release-contract.json'],capture_output=True,text=True)
    if prior.returncode==0:verify_preserved_releases(json.loads(prior.stdout),current)
    elif subprocess.run(['git','rev-parse','--verify','HEAD^'],capture_output=True).returncode:raise ValueError('RELEASE_HISTORY_REQUIRED')
    print(json.dumps({'result':'PASS','profile':PROFILE['profile'],'generator':PROFILE['generator'],'bundleDigest':bundle_digest(),'history':'prior released entries immutable'}))
if __name__=='__main__':check()
