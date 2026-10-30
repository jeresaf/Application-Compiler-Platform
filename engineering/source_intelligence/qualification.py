"""Focused native Source Intelligence qualification; no databases or app execution."""
import argparse,json,os,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from engineering.source_intelligence.analysis import prepare
from engineering.source_intelligence.model import require,sha,encode

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--maven-repo',type=Path);p.add_argument('--node-modules',type=Path);p.add_argument('--provision-runner-inputs',action='store_true');a=p.parse_args();w=a.workspace.absolute()
 if not w.exists():w.mkdir(mode=0o700)
 (w/'execution-owner.json').write_bytes(encode({'scope':'ANALYSIS_ONLY','repository':str(ROOT),'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'cleanup':'RETAIN_REQUIRED_EVIDENCE_BEFORE_REMOVAL'}))
 for domain in ('payment','case-management'):
  if not (w/domain).exists():prepare(w/domain,domain)
 if a.provision_runner_inputs:
  require(os.environ.get('GITHUB_ACTIONS')=='true' and w.is_relative_to(Path(os.environ['RUNNER_TEMP']).resolve()),'DISPOSABLE_RUNNER_ONLY')
  from engineering.dependency_resolution.inputs import seed_maven
  seed=w/'empty-m2';seed.mkdir();reference=json.loads((ROOT/'engineering/dependency_resolution/maven-artifacts.lock.json').read_bytes());a.maven_repo=w/'m2';seed_maven(seed,a.maven_repo,reference,online=True)
  front=w/'payment/payment/frontend';other=w/'case-management/case-management/frontend'
  require((front/'package-lock.json').read_bytes()==(other/'package-lock.json').read_bytes(),'DOMAIN_DEPENDENCY_LOCK_MISMATCH')
  subprocess.run(['npm','ci','--ignore-scripts','--no-audit','--no-fund','--cache',str(w/'npm-cache')],cwd=front,check=True);a.node_modules=front/'node_modules'
 require(a.maven_repo and a.node_modules,'EXACT_NATIVE_DEPENDENCIES_REQUIRED')
 os.environ.update(ACP_SOURCE_APPLICATIONS=str(w),ACP_SOURCE_MAVEN_REPO=str(a.maven_repo.absolute()),ACP_SOURCE_NODE_MODULES=str(a.node_modules.absolute()))
 suite=unittest.defaultTestLoader.discover(str(ROOT/'verification/source_intelligence'));require(suite.countTestCases()==26,'SOURCE_TEST_COUNT')
 result=unittest.TextTestRunner(verbosity=2).run(suite);require(result.wasSuccessful() and result.testsRun==26 and not result.skipped,'SOURCE_QUALIFICATION_FAILED')
 summary={'scope':'ANALYSIS_ONLY','tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),'applications':{}}
 for domain in ('payment','case-management'):
  path=w/domain/'source-model.json';m=json.loads(path.read_bytes());summary['applications'][domain]={'fileSHA256':sha(path.read_bytes()),'modelDigest':m['digest'],'symbols':len(m['symbols']),'references':len(m['references']),'typeRelations':len(m['typeRelations']),'semanticMappings':len(m['semanticMappings']),'completeness':m['completeness'],'drift':m['drift']}
 (w/'qualification.json').write_bytes(encode(summary));print(json.dumps(summary,sort_keys=True,indent=2))
if __name__=='__main__':main()
