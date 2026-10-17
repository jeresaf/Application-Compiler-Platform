"""One individually reported rejection for each Stage A N01--N32 threat."""
import unittest
from dataclasses import replace
from test_manifest import Fixture,canonicalize,digest,D
from tooling.audit.scoped_admission import release_bridge
from engineering.evidence_admission.scoped.verify import qualify


def rebind(f):
    # Deliberately authorize new lab observations to reach deep content validation.
    from test_manifest import sha
    for a in f.m['artifacts']:
        raw=(f.artifacts/a['path']).read_bytes();a['size']=len(raw);a['sha256']=sha(raw)
    f.payload['manifestDigest']=digest(canonicalize(f.m))
    f.context=replace(f.context,observations=(canonicalize(f.payload),))
    f.review['manifestDigest']=digest(canonicalize(f.m));f.reviews=(f.sign(f.review,('REVIEWER',)),)


def attack(f,n):
    run=f.run
    if n==1:
        return lambda:qualify(canonicalize(f.m),canonicalize({'payload':f.payload,'signatures':[]}),f.reviews,f.context,f.source,f.artifacts)
    if n==2:(f.artifacts/'payment.xml').write_bytes(b'fabricated')
    elif n==3:f.payload['execution']['startedAt']='2026-10-15T11:59:59Z';f.m['createdAt']='2026-10-17T12:00:00Z'
    elif n==4:f.m['applicationSource']['commit']='b'*40
    elif n==5:f.m['release']['candidateSourceDigest']=f.m['release']['parentBundleSeal']
    elif n==6:f.m['release']={'kind':'SEALED_RELEASE','profile':'unknown/9','generator':'unknown/9','releaseContractDigest':D('x'),'bundleSeal':D('x')};f.m['purpose']='SEALED_RELEASE_EVALUATION'
    elif n==7:(f.source/'Unregistered.java').write_text('extra')
    elif n==8:f.payload['observedInputs']['executableDigest']=D('substituted executable')
    elif n==9:f.m['criteria'][0]['criterion']=9
    elif n==10:f.m['criteria'][0]['witnesses'].pop()
    elif n==11:
        p=f.artifacts/'payment.xml';p.write_bytes(p.read_bytes().replace(b'/></testsuite>',b'><skipped/></testcase></testsuite>'));rebind(f)
    elif n==12:f.payload['candidateControlledCollectorVerified']=True
    elif n==13:f.payload['descendantCleanup']='INCOMPLETE'
    elif n==14:
        record=f.sign(f.payload);from test_manifest import parse_canonical
        v=parse_canonical(record);v['signatures'][0]['keyId']='key:unknown'
        return lambda:qualify(canonicalize(f.m),canonicalize(v),f.reviews,f.context,f.source,f.artifacts)
    elif n==15:return lambda:replace(f.context,laboratory=False)
    elif n==16:return lambda:replace(f.context,provider_available=False)
    elif n==17:f.payload['nonce']='d'*32
    elif n==18:f.context=replace(f.context,review_grants=())
    elif n==19:f.review['reviewDigest']=D('changed raw review');f.reviews=(f.sign(f.review,('REVIEWER',)),)
    elif n==20:f.context=replace(f.context,author_ids=frozenset({'principal:reviewer'}))
    elif n==21:f.review['disposition']='ACCEPT_WITH_RESERVATIONS';f.review['reservations']=['T09 laboratory only'];f.reviews=(f.sign(f.review,('REVIEWER',)),)
    elif n==22:f.review['purpose']='MIGRATION_EXECUTION';f.reviews=(f.sign(f.review,('REVIEWER',)),)
    elif n==23:f.m['evaluator']['predicateSetDigest']=D('changed predicate set')
    elif n==24:f.payload['observedInputs']['argv']=['/bin/sh','-c','candidate-controlled']
    elif n==25:
        p=f.artifacts/'payment.xml';p.unlink();p.symlink_to(f.source/'Witness.java')
    elif n==26:
        p=f.artifacts/'payment.xml';p.write_bytes(p.read_bytes().replace(b'/></testsuite>',b'><failure/></testcase></testsuite>'));rebind(f)
    elif n==27:f.m['executions'][0]['provider']={'kind':'GITHUB_ACTIONS','repository':f.m['repository'],'runId':1,'attempt':99,'jobId':2,'workflowPath':'.github/workflows/forged.yml','workflowCommit':'b'*40,'testedCommit':f.m['applicationSource']['commit']}
    elif n==28:f.m['applications'].pop()
    elif n==29:f.m['schema']='acp-phase6-evaluation-manifest/999'
    elif n==30:return lambda:replace(f.context,recovery_verified=False)
    elif n==31:return lambda:release_bridge({'status':'ELIGIBLE','accepted_reviews':{'12':D('fake')}})
    elif n==32:return lambda:release_bridge(f.run())
    return run


class AdversarialTests(unittest.TestCase):
    pass


def rejection(n):
    def test(self):
        f=Fixture(human=True);self.addCleanup(f.close)
        # The valid fixture must qualify before mutation; rejection is not a broken baseline.
        self.assertEqual(f.run().status,'QUALIFICATION_ONLY')
        with self.assertRaises((ValueError,OSError)):
            attack(f,n)()
    return test


for n in range(1,33):
    setattr(AdversarialTests,'test_N%02d_reject'%n,rejection(n))
