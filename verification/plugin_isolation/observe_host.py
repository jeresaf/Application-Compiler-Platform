"""Read-only installed-runtime observations. No sandbox launch, installation or privilege change."""
from pathlib import Path
import subprocess,json,hashlib,os,platform,time,argparse
from datetime import datetime,timezone
parser=argparse.ArgumentParser(description='Fixed read-only H10 observations, never execution qualification');parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();root=Path(__file__).resolve().parents[2];out=args.output
if out.exists():raise ValueError('OBSERVATION_COLLISION')
paths=['/etc/os-release','/proc/sys/kernel/unprivileged_userns_clone','/proc/sys/user/max_user_namespaces','/proc/sys/kernel/apparmor_restrict_unprivileged_userns','/proc/sys/kernel/apparmor_restrict_unprivileged_unconfined','/sys/module/apparmor/parameters/enabled','/sys/fs/cgroup/cgroup.controllers','/sys/fs/cgroup/cgroup.subtree_control','/proc/self/attr/current','/proc/self/cgroup']
reads={}
for name in paths:
 try:
  raw=Path(name).read_bytes();reads[name]={'status':'OBSERVED','text':raw.decode().strip(),'sha256':hashlib.sha256(raw).hexdigest()}
 except OSError as e:reads[name]={'status':'UNAVAILABLE','errorClass':type(e).__name__}
commands=[['/usr/bin/bwrap','--version'],['/usr/bin/dpkg-query','-W','-f=${Package} ${Version} ${Architecture}\n','bubblewrap','libseccomp2'],['/usr/bin/systemctl','--user','show','-p','ControlGroup']]
observations=[]
for command in commands:
 started=time.monotonic()
 try:
  p=subprocess.run(command,capture_output=True,text=True,timeout=15,close_fds=True,env={'PATH':'/usr/bin:/bin','LANG':'C'});row={'argv':command,'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
 except (OSError,subprocess.TimeoutExpired) as e:row={'argv':command,'exit':None,'errorClass':type(e).__name__}
 row['elapsedSeconds']=time.monotonic()-started;observations.append(row)
tools={}
for name in ['/usr/bin/bwrap','/usr/bin/dpkg-query','/usr/bin/systemctl','/usr/lib/x86_64-linux-gnu/libseccomp.so.2']:
 try:
  p=Path(name);resolved=p.resolve(strict=True);info=resolved.stat();tools[name]={'resolved':str(resolved),'sha256':hashlib.sha256(resolved.read_bytes()).hexdigest(),'uid':info.st_uid,'mode':oct(info.st_mode & 0o7777)}
 except OSError as e:tools[name]={'status':'UNAVAILABLE','errorClass':type(e).__name__}
r={'installedToolObservations':tools,'candidateIdentity':'NONE_EXECUTED','executionMechanism':'FIXED_READ_ONLY_COMMANDS_NO_SANDBOX','schema':'acp-h10-readonly-feasibility/1','capturedAt':datetime.now(timezone.utc).isoformat(),'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'observerSHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'kernel':platform.release(),'system':platform.system(),'architecture':platform.machine(),'reads':reads,'commands':observations,'status':'OBSERVED_NOT_QUALIFIED','isolationProfileIdentity':'NONE_ACTIVATED','securityPolicyDigest':None,'candidateExecuted':False,'hostilePayloadExecuted':False,'resourcesCreated':[],'cleanup':'NO_DISPOSABLE_EXECUTION_RESOURCES_CREATED','limitations':['Read-only visibility does not establish namespace creation, delegation, policy attachment or confinement.','No vDSO or hostile probe executed.','Installed Bubblewrap version is an observation, not distribution trust or security acceptance.']}
out.write_text(json.dumps(r,sort_keys=True,indent=2)+'\n');print(json.dumps(r,indent=2))
