"""Independent observation of actual Maven plugin realms and fresh OSV responses."""
import json
import re
from pathlib import Path
from engineering.dependency_resolution.inputs import file_hash, require
from engineering.security.qualification import https_json, assess_response

IDENTITY = 'commons-io:commons-io'
VERSION = '2.22.0'
ARTIFACT = 'commons-io/commons-io/2.22.0/commons-io-2.22.0.jar'
SHA256 = '2b9a7b1f726fb86216dbd2c8321eabe0221dbd5b1be81c18e1cb53811b104758'


def parse_realms(text):
    """Inspect Maven's actual realm population, not a POM's declared intent."""
    realms = {}
    current = None
    for line in text.splitlines():
        match = re.search(r'Populating class realm (plugin>[^\s]+)', line)
        if match:
            current = match[1]
            require(current not in realms, 'H1_DUPLICATE_REALM')
            realms[current] = []
        match = re.search(r'Included: (commons-io:commons-io:jar:[^\s]+)', line)
        if match and current is not None:
            realms[current].append(match[1])
    required = ('maven-resources-plugin:3.5.0', 'maven-compiler-plugin:3.15.0')
    for suffix in required:
        key = 'plugin>org.apache.maven.plugins:'+suffix
        require(key in realms and realms[key] == [IDENTITY+':jar:'+VERSION],
                'H1_UNVERIFIED_PLUGIN_REALM:'+suffix)
    for realm, values in realms.items():
        require(all(v == IDENTITY+':jar:'+VERSION for v in values),
                'H1_VULNERABLE_PLUGIN_REALM:'+realm)
    return realms


def verify_realms(text, repo):
    realms = parse_realms(text)
    require(file_hash(Path(repo)/ARTIFACT) == SHA256, 'H1_DEPENDENCY_SUBSTITUTION')
    return {'scope': 'QUALIFICATION_ONLY', 'status': 'PASS', 'realms': realms,
            'artifact': ARTIFACT, 'sha256': SHA256}


def reassess(output):
    """Retain the live baseline and replacement query plus full advisory records."""
    output = Path(output)
    output.mkdir(mode=0o700, exist_ok=False)
    rows = [{'ecosystem': 'Maven', 'name': IDENTITY, 'version': v,
             'source': 'SELECTED_MAVEN_PLUGIN_REALM'} for v in ('2.11.0', VERSION)]
    query = {'queries': [{'package': {'ecosystem': r['ecosystem'], 'name': r['name']},
                          'version': r['version']} for r in rows]}
    save = lambda name, value: (output/name).write_text(json.dumps(value, sort_keys=True, indent=2)+'\n')
    save('request.json', query)
    response = https_json('https://api.osv.dev/v1/querybatch', query)
    save('response.json', response)
    def fetch(identity):
        value = https_json('https://api.osv.dev/v1/vulns/'+identity)
        save(identity+'.json', value)
        return value
    findings = assess_response(rows, response, fetch)
    result = {'scope': 'QUALIFICATION_ONLY', 'transport': 'HTTPS_SYSTEM_TRUST_VERIFICATION',
              'findings': findings, 'status': 'FAIL' if any(
                  f['component']['version'] == VERSION for f in findings) else 'PASS',
              'claim': 'Selected Commons IO identity only; other retained findings remain open.'}
    save('assessment.json', result)
    require(result['status'] == 'PASS', 'H1_REPLACEMENT_HAS_OSV_FINDINGS')
    return result
