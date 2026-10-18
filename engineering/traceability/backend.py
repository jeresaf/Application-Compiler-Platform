"""Assertion witnesses for the existing approved-reference backend suites.

Instruments external test sources only. Markers follow real assertions and must
appear in the exact successful JUnit testcase; suite-level PASS is insufficient.
"""
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

from .qualification import require, sha, ROOT

FAMILIES = frozenset(('Entity Field Permission Policy Command Query UseCase Failure RatePolicy IdempotencyPolicy '
                     'DeliveryPolicy Schedule Job DataClassification DataLifecycle Retention DeletionPolicy LegalHold '
                     'Screen Form InputControl Action PermissionBoundary').split())
# Pick behavior-bearing representatives, rather than an arbitrary first ID.
REGISTRATION = {
 'Entity': ('ExplicitExecutionTest','exactEffectsResultsEventsAndUnchangedFields','assertEquals("fixture-resource",output.resourceId())'),
 'Field': ('ExplicitExecutionTest','exactEffectsResultsEventsAndUnchangedFields','assertEquals("new 🦋",jdbc.queryForObject'),
 'Command': ('ExplicitExecutionTest','exactEffectsResultsEventsAndUnchangedFields','assertEquals("new 🦋",output.output()'),
 'Permission': ('InvocationCoreTest','unauthorizedRequestsCreateNoRateOrIdempotencyState','assertThrows('),
 'Policy': ('InvocationCoreTest','unauthorizedRequestsCreateNoRateOrIdempotencyState','assertThrows('),
 'Failure': ('InvocationCoreTest','actualWorkflowFailureRollsBackAndStopsLaterSteps','assertEquals("FAIL-BUSINESS"'),
 'RatePolicy': ('InvocationCoreTest','exactApprovedInvocationReplayConflictAndAtomicResults','assertEquals(0,chargedBeforeConflict'),
 'IdempotencyPolicy': ('InvocationCoreTest','exactApprovedInvocationReplayConflictAndAtomicResults','assertEquals(first,again)'),
 'DeliveryPolicy': ('DeliveryJobTest','committedOccurrencesHaveExactIdentityAndOrderedPositions','assertEquals('),
 'Schedule': ('DeliveryJobTest','schedulerExactActivationUsesApprovedBindingsAndNormalAuthorization','assertEquals("COMPLETED"'),
 'Job': ('DeliveryJobTest','schedulerExactActivationUsesApprovedBindingsAndNormalAuthorization','assertEquals("COMPLETED"'),
 'DataClassification': ('ExplicitExecutionTest','exactEffectsResultsEventsAndUnchangedFields','assertTrue(jdbc.queryForObject("SELECT count(*) FROM acp_classification_audit WHERE mode=\'WRITE\'"'),
 'DataLifecycle': ('PrivacyLifecycleTest','exactClosureCommitAnchorAndReobservationNeverResets','assertEquals('),
 'Retention': ('PrivacyLifecycleTest','nanosecondRetentionAndDeletionBoundariesAndClockReversal','assertEquals(LifecycleRuntime.Result.NOT_DUE'),
 'DeletionPolicy': ('PrivacyLifecycleTest','nanosecondRetentionAndDeletionBoundariesAndClockReversal','assertEquals(LifecycleRuntime.Result.BLOCKED_HOLD'),
 'LegalHold': ('PrivacyLifecycleTest','permissionAloneDoesNotReleaseAndWrongExactReleaseFails','assertEquals(0,jdbc.queryForObject'),
}
# Ignore braces/parentheses in Java literals and comments. No arbitrary Java is
# accepted: exact fixture/method/assertion registrations below are mandatory.
TOKENS = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*.*?\*/|[{}()]', re.S)


def closing(source, start, opening, ending):
    require(source[start] == opening, 'JAVA_START')
    depth=0
    for token in TOKENS.finditer(source,start):
        value=token.group()
        if value==opening:depth+=1
        elif value==ending:
            depth-=1
            if depth==0:return token.end()
    raise ValueError('JAVA_UNCLOSED')


def instrument(source, kind, method, selector, node):
    require('ACP_ASSERT|'+kind+'|' not in source, 'JAVA_ALREADY_INSTRUMENTED')
    matches=list(re.finditer(r'@Test void '+re.escape(method)+r'\(\)[^{]*\{',source))
    require(len(matches)==1,'JAVA_TEST_REGISTRATION')
    start=matches[0].end()-1;end=closing(source,start,'{','}')
    body=source[start:end]
    require(selector in body,'JAVA_ASSERTION_REGISTRATION:'+kind)
    at=source.index(selector,start,end)
    bracket=source.index('(',at,end)
    last=closing(source,bracket,'(',')')
    require(source[last]==';','JAVA_ASSERTION_STATEMENT')
    last+=1
    assertion=source[at:last]
    marker='ACP_ASSERT|'+kind+'|'+node['id']+'|'+str(node['revision'])+'|'+method
    # Annotation follows the concrete assert, including assertThrows callbacks.
    changed=source[:last]+'System.out.println('+json.dumps(marker)+');'+source[last:]
    return changed,{'kind':kind,'object':node['id'],'revision':node['revision'],'method':method,
                    'assertion':assertion,'marker':marker}


def representatives(snapshot):
    nodes=snapshot.read()['content']['nodes'];by={n['id']:n for n in nodes}
    root='ENT-PAYMENT' if 'ENT-PAYMENT' in by else 'CASE'
    command=by[by['UC-TASK']['data']['steps'][0]['id']]['data']['operation']['id']
    policy=next(n for n in nodes if n['kind']=='Policy' and n['data']['action']['id']==command)
    ids={'Command':command,'Policy':policy['id'],'Permission':policy['data']['permission']['id'],'Entity':root,'Field':'FLD-TASK-SUMMARY','DataClassification':by['FLD-TASK-SUMMARY']['data']['classificationRef']['id']}
    # Invocation fixture executes the exact ordered UseCase, hence every bound
    # command/rate/delivery; choose the first supported object of those families.
    for kind in REGISTRATION:
        ids.setdefault(kind,next(n['id'] for n in nodes if n['kind']==kind))
    for kind,id in ids.items():require(by[id]['kind']==kind,'REPRESENTATIVE_KIND')
    return {kind:by[id] for kind,id in ids.items()}


def sources(domain,snapshot):
    from phase6_reference_tests import source as execution, http_source as execution_http, variants as execution_variants
    from invocation_reference_tests import source as invocation,http_source as invocation_http, variants
    from privacy_lifecycle_reference_tests import http_source as privacy_http,variants as privacy_variants
    from engineering.generator_builds.privacy_fixture import source as privacy
    from delivery_components import delivery_source
    # Test-only variant classes are retained as supporting negative tests, never
    # accepted snapshots, generated application artifacts or semantic approvals.
    values={'ExplicitExecutionTest':execution(domain),'InvocationCoreTest':invocation(domain),
            'InvocationHttpTest':invocation_http(domain),'DeliveryJobTest':delivery_source(domain),
            'PrivacyLifecycleTest':privacy(domain),'PrivacyHttpTest':privacy_http(domain)}
    bindings=[];representative=representatives(snapshot)
    for kind,(cls,method,selector) in REGISTRATION.items():
        values[cls],binding=instrument(values[cls],kind,method,selector,representative[kind])
        binding['class']='acp.generated.'+cls;bindings.append(binding)
    files={'backend/src/test/java/acp/generated/'+cls+'.java':text for cls,text in values.items()}
    files.update(execution_variants(domain));files.update(variants(domain,snapshot.read()['content']['nodes']))
    files.update(privacy_variants(domain,snapshot.read()['content']['nodes']))
    files['backend/src/test/resources/invocation-profile-V1.sql']=(ROOT/'targets/spring-vue-postgres/historical/invocation-0.1'/f'{domain}-V1__initial.sql').read_text()
    for row in bindings:
        row['source']='backend/src/test/java/'+row['class'].replace('.','/')+'.java'
        row['sourceSHA256']=sha(files[row['source']].encode())
    count=sum(len(re.findall(r'@Test void ',text)) for text in values.values())
    return files,bindings,count,tuple(values)


def verify_results(reports, bindings, provenance, files, expected_count):
    cases={};total=0
    for path in reports:
        suite=ET.fromstring(path.read_bytes())
        require(not any(int(suite.attrib.get(k,'0')) for k in ('failures','errors','skipped')),'JAVA_FAILURE_OR_SKIP')
        for case in suite.iter('testcase'):
            key=(case.attrib['classname'],case.attrib['name'])
            require(key not in cases and not any(case.find(k) is not None for k in ('failure','error','skipped')),'JAVA_TEST_NOT_GREEN')
            cases[key]=(case,path);total+=1
    require(total==expected_count,'JAVA_TEST_COUNT')
    links=[]
    for binding in bindings:
        require(sha(files[binding['source']].encode())==binding['sourceSHA256'],'JAVA_SOURCE_BINDING')
        statement='System.out.println('+json.dumps(binding['marker'])+');'
        pattern=re.escape(binding['assertion'])+r'(?:System\.out\.println\("ACP_ASSERT\|[^"\n]+"\);)*'+re.escape(statement)
        require(re.search(pattern,files[binding['source']]) is not None,'JAVA_ASSERTION_BINDING')
        require((binding['class'],binding['method']) in cases,'JAVA_MISSING_TEST')
        case,path=cases[(binding['class'],binding['method'])]
        require(binding['marker'] in [line.strip() for line in case.findtext('system-out','').splitlines()],'JAVA_MISSING_ASSERTION')
        mapped=[r for r in provenance['artifacts'] if any(o['id']==binding['object'] and o['revision']==binding['revision'] for o in r['origins'])]
        require(mapped,'JAVA_MISSING_MAPPING')
        links.append({**binding,'artifacts':mapped,'result':path.name,'resultSHA256':sha(path.read_bytes())})
    require({b['kind'] for b in links}==set(REGISTRATION),'JAVA_FAMILY_COVERAGE')
    return links


def verify_sources(project, files):
    for name,text in files.items():
        path=project/name
        require(path.is_file() and not path.is_symlink() and sha(path.read_bytes())==sha(text.encode()),'JAVA_LIVE_SOURCE_CHANGED')


def execute(project, domain, snapshot, provenance, logs):
    from engineering.generator_builds.qualify import run
    files,bindings,count,classes=sources(domain,snapshot)
    for name,text in files.items():
        path=project/name
        require(not path.exists() and not path.is_symlink(),'TEST_SOURCE_COLLISION')
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    # Retain the exact external test inputs and original Surefire results.
    output=logs/'backend-traces';output.mkdir()
    for name,text in files.items():
        destination=output/'sources'/name;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(text)
    import subprocess
    verify_sources(project,files)
    with (output/'maven.log').open('wb') as stream:
        subprocess.run(['mvn','-B','-ntp','-Dtest='+','.join(classes),'test'],cwd=project/'backend',stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=1200)
    verify_sources(project,files)
    reports=[]
    for name in classes:
        original=project/'backend/target/surefire-reports'/('TEST-acp.generated.'+name+'.xml')
        destination=output/original.name;shutil.copyfile(original,destination);reports.append(destination)
    links=verify_results(reports,bindings,provenance,files,count)
    return {'scope':'QUALIFICATION_ONLY','tests':count,'skipped':0,'links':links}
