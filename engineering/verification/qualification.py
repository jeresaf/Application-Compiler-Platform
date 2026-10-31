"""Execute the first Phase 8 checks; reuse accepted Phase 7 results without reruns."""
import argparse,json,os,shutil,subprocess,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from engineering.verification.integration import *
from engineering.verification.inputs import reference_inputs,ARCHIVE_SHA256,SOURCE_COMMIT,DOMAINS
from engineering.source_intelligence.analysis import prepare

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,required=True);p.add_argument('--phase7-archive',type=Path,required=True);p.add_argument('--reuse-applications',type=Path);p.add_argument('--execution-evidence',type=Path,required=True);p.add_argument('--evaluated-at',required=True);a=p.parse_args();w=a.workspace.absolute();w.mkdir(mode=0o700,exist_ok=False)
 (w/'execution-owner.json').write_bytes(encode({'scope':'QUALIFICATION_ONLY','purpose':'DISPOSABLE_PHASE8_VERIFICATION','sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'executorSHA256':sha((ROOT/'engineering/verification/integration.py').read_bytes()),'phase7SourceCommit':SOURCE_COMMIT,'phase7ArchiveSHA256':ARCHIVE_SHA256,'cleanup':'RETAIN_REQUIRED_EVIDENCE_BEFORE_REMOVAL'}))
 reference_inputs(a.phase7_archive,w/'reference')
 for d in DOMAINS:
  if a.reuse_applications:
   (w/d).mkdir();shutil.copytree(a.reuse_applications/d/d,w/d/d)
  else:prepare(w/d,d)
 os.environ.update(ACP_VERIFICATION_WORKSPACE=str(w),ACP_EXECUTION_EVIDENCE=str(a.execution_evidence.absolute()),ACP_EXECUTION_EVALUATED_AT=a.evaluated_at)
 suite=unittest.defaultTestLoader.discover(str(ROOT/'verification/verification'));require(suite.countTestCases()==30,'VERIFICATION_TEST_COUNT')
 result=unittest.TextTestRunner(verbosity=2).run(suite);require(result.wasSuccessful() and result.testsRun==30 and not result.skipped,'VERIFICATION_QUALIFICATION_FAILED')
 report={'scope':'QUALIFICATION_ONLY','tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped),'applications':{}}
 for d in DOMAINS:
  raw=(w/d/'execution-verification-result.json').read_bytes();v=validate_result(json.loads(raw));report['applications'][d]={'inputs':v['inputs'],'fileSHA256':sha(raw),'resultDigest':v['digest'],'summary':v['summary'],'releaseDisposition':v['releaseDisposition']}
 (w/'qualification.json').write_bytes(encode(report));print(json.dumps(report,sort_keys=True,indent=2))
if __name__=='__main__':main()
