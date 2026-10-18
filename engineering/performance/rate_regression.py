"""Real disposable PostgreSQL ordering regressions for both reference applications."""
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
from engineering.traceability.qualification import inputs, sha
from engineering.generator_builds.runtime import database
from engineering.generator_candidates.spring_vue_postgres_0_6.rate_clock_tests import sources
from filesystem_artifacts import FilesystemArtifactStore
from invocation_reference_tests import source, variants

def qualify(workspace):
    workspace=Path(workspace);workspace.mkdir(mode=0o700,exist_ok=False)
    results={}
    for domain in ('payment','case-management'):
        candidate,snapshot,request,plan=inputs(domain)
        project=workspace/domain;FilesystemArtifactStore(project).apply(plan)
        files=sources(domain)
        files['backend/src/test/java/acp/generated/InvocationCoreTest.java']=source(domain)
        files.update(variants(domain,snapshot.read()['content']['nodes']))
        root=Path(__file__).resolve().parents[2]
        files['backend/src/test/resources/invocation-profile-V1.sql']=(root/'targets/spring-vue-postgres/historical/invocation-0.1'/f'{domain}-V1__initial.sql').read_text()
        for relative,text in files.items():
            path=project/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
        with database():
            with (project/'maven.log').open('wb') as stream:
                subprocess.run(['mvn','-B','-ntp','-Dtest=InvocationCoreTest,RateClockTest','test'],cwd=project/'backend',stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=1200)
        count=0;reports={}
        for name in ('InvocationCoreTest','RateClockTest'):
            path=project/'backend/target/surefire-reports'/f'TEST-acp.generated.{name}.xml'
            tree=ET.fromstring(path.read_bytes())
            if any(int(tree.get(k,'0')) for k in ('failures','errors','skipped')):raise ValueError('RATE_REGRESSION_FAILED')
            count+=int(tree.get('tests'));reports[name]=sha(path.read_bytes())
        if count!=({'payment':18,'case-management':19}[domain]):raise ValueError('RATE_TEST_COUNT:'+str(count))
        results[domain]={'tests':count,'failures':0,'skipped':0,'reports':reports,'sources':{p:sha(v.encode()) for p,v in files.items()},'databaseCleanup':'REMOVED'}
    (workspace/'results.json').write_text(json.dumps(results,sort_keys=True,indent=2))
    return results
