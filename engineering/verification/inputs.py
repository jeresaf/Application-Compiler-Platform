"""Reuse the exact accepted Phase 7 execution artifact, not a new trust registry."""
import json,zipfile
from pathlib import Path,PurePosixPath
from engineering.verification.integration import require,sha,load_model
ARCHIVE_SHA256='55ae6a899cd429628563fe3c65e035038c4f9d32d595305f16253f93325e07fe'
SOURCE_COMMIT='8b351ce75ca44da2bf7516414ff4e94c645563f9'
RUN=41081168320
ARTIFACT=12988799586
DOMAINS=('payment','case-management')

def reference_inputs(archive,destination):
 archive=Path(archive);destination=Path(destination)
 require(sha(archive.read_bytes())==ARCHIVE_SHA256,'PHASE7_ARCHIVE_DIGEST')
 expected={'acp-source.log','acp-source/execution-owner.json','acp-source/qualification.json'}|{f'acp-source/{d}/{n}' for d in DOMAINS for n in ('source-baseline.json','source-baseline.sha256','source-model.json')}
 with zipfile.ZipFile(archive) as z:
  members=z.infolist();require(len(members)==len(expected) and {m.filename for m in members}==expected,'PHASE7_ARCHIVE_INVENTORY')
  for m in members:
   path=PurePosixPath(m.filename);require(not path.is_absolute() and '..' not in path.parts and not (m.external_attr>>16)&0o170000==0o120000 and m.file_size<=12*1024*1024,'PHASE7_ARCHIVE_MEMBER')
  require(sum(m.file_size for m in members)<=24*1024*1024,'PHASE7_ARCHIVE_SIZE');require(z.testzip() is None,'PHASE7_ARCHIVE_CORRUPTION')
  owner=json.loads(z.read('acp-source/execution-owner.json'));require(owner['sourceCommit']==SOURCE_COMMIT and owner['scope']=='ANALYSIS_ONLY','PHASE7_EXECUTION_SOURCE')
  q=json.loads(z.read('acp-source/qualification.json'));require(q['scope']=='ANALYSIS_ONLY' and q['tests']==26 and all(q[k]==0 for k in ('errors','failures','skips')),'PHASE7_EXECUTION_RESULT')
  destination.mkdir(mode=0o700,exist_ok=False)
  for d in DOMAINS:
   target=destination/d;target.mkdir()
   for n in ('source-baseline.json','source-baseline.sha256','source-model.json'):(target/n).write_bytes(z.read(f'acp-source/{d}/{n}'))
   require(sha((target/'source-baseline.json').read_bytes())==(target/'source-baseline.sha256').read_text().strip(),'PHASE7_BASELINE_DIGEST')
   load_model(target/'source-model.json',q['applications'][d]['fileSHA256'])
 return q
