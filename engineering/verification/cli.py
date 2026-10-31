"""Read-only application verification through existing compiler/qualification code."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from engineering.verification.integration import *

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['run','verify-retained']);p.add_argument('--root',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--baseline-sha256',required=True);p.add_argument('--source-model',type=Path,required=True);p.add_argument('--source-model-sha256',required=True);p.add_argument('--output',type=Path);p.add_argument('--retained',type=Path);p.add_argument('--retained-sha256');p.add_argument('--execution-evidence',type=Path);p.add_argument('--evaluated-at');a=p.parse_args()
 execution=None
 if a.execution_evidence:
  from engineering.verification.execution import HostedExecutions
  require(a.evaluated_at,'EXPLICIT_EVALUATION_TIME_REQUIRED');execution=HostedExecutions(a.execution_evidence,a.evaluated_at)
 session=Session(a.root,a.baseline,a.baseline_sha256,a.source_model,a.source_model_sha256)
 if a.operation=='run':
  require(a.output is not None,'OUTPUT_REQUIRED');executor=ExistingEvidenceExecutor(session,a.output,execution);result=executor.execute(Document.of({'schema':'acp-verification-request/1','operation':'VERIFY','inputsDigest':digest(executor.inputs)}),executor.input_digests).read()
 else:
  require(a.retained is not None and a.retained_sha256,'RETAINED_RESULT_REQUIRED');raw=a.retained.read_bytes();require(sha(raw)==a.retained_sha256,'RETAINED_FILE_DIGEST');result=session.verify_retained(json.loads(raw),execution=execution);result={k:result[k] for k in ('schema','scope','digest','summary','releaseDisposition')}
 print(json.dumps(result,sort_keys=True,indent=2))
if __name__=='__main__':main()
