"""Hosted hard-gate evidence checks; UNKNOWN may remain explicitly blocked."""
import json
from pathlib import Path
AREA=Path(__file__).resolve().parent

def check():
    root=AREA/'results/phase5c'
    tests=json.loads((root/'native-tests.json').read_text());assert tests['status']=='PASS' and tests['testsRun']>=8
    diagnostics=json.loads((root/'diagnostics.json').read_text());assert set(diagnostics)=={'antlr','langium','xtext'}
    faults=json.loads((root/'core-faults.json').read_text())
    assert set(faults['runtimes'])=={'java','typescript','rust'}
    for runtime in faults['runtimes'].values():
        assert runtime['persistentRequests']>=15
        for r in runtime['faultFixtures']:
            if r['status']=='FAILURE':assert set(r)=={'protocol','id','status','diagnostics'}
        assert runtime['timeout']['retryEquivalent'] and runtime['crash']['retryEquivalent']
    integration=json.loads((root/'integration.json').read_text())
    assert integration['phase6']=='NOT_STARTED'
    for candidate in integration['candidates'].values():
        assert len(candidate['persistent'])==3
        for run in candidate['persistent']:
            assert len(run['warm'])==5 and run['nativeRequestsSamePid']==6
            for request in run['warm']:assert request['rssBytes']<=1024*1024*1024
        assert set(candidate['splitRuntime'])=={'java','typescript','rust'}
        for split in candidate['splitRuntime'].values():assert len(split['coldAndFiveWarm'])==6
        a,b,c=candidate['orderedChangeDigests'];assert a==c and a!=b
    maintenance=json.loads((root/'maintenance.json').read_text());assert all(p['license'] for p in maintenance['rustInventory'])
    assert all(v['status']=='PASS' for v in maintenance['toolchainUpgrades'].values())
    assert maintenance['xtext']['candidateDisposition']=='REJECTED_FOR_PRODUCTION'
    gates=json.loads((AREA/'results/gates.json').read_text());assert gates['phase6']=='NOT_STARTED'
    assert gates['softWeights']=={'editor':25,'performance':20,'memory':15,'integration':20,'ergonomics':10,'operations':10}
    if gates['weightedScores'] is not None:assert all(g['status']=='PASS' for g in gates['hardGates'].values())
    assert gates['phase5'] in {'EXPLICITLY_BLOCKED_ON_EVIDENCE','CLOSED_AND_GREEN'}
    if gates['phase5']=='EXPLICITLY_BLOCKED_ON_EVIDENCE':assert any(g['status']!='PASS' and g.get('missing') for g in gates['hardGates'].values())
    print('Phase 5C reproducible evidence checks PASS; unresolved gates cannot silently pass')
if __name__=='__main__':check()
