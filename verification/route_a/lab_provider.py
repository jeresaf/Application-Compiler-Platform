"""NON_AUTHORITATIVE_TEST_ONLY. Disposable keys, signed fixtures, loopback witness.

No key/session/proof is retained outside TemporaryDirectory/test memory.
Never import this module into the adapter or an operational host.
"""
import base64
from contextlib import closing
import json
import sqlite3
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from canonical_json import canonical_bytes,loads
from engineering.route_a_gateway.security import Host,LABEL,require,hashed,decode
from engineering.route_a_gateway.evidence import CHECKPOINT,verify_receipt,verify_witness_submission


class Lab:
    def __init__(self,directory):
        self.now=1000
        self.keys={p:Ed25519PrivateKey.generate() for p in ('authentication','approval','receipt','witness')}
        self.registration_key=Ed25519PrivateKey.generate()
        principals={'authentication':'LAB-IDP','approval':'LAB-REVIEWER','receipt':'LAB-SERVICE','witness':'LAB-WITNESS'}
        grants=[]
        for principal,actions,scopes in [
            ('author',['AUTHOR','PROPOSE','REVIEW','BOOTSTRAP','APPLY','RECEIPT_READ','RECOVER','AUDIT_READ','EXPORT_READ','RECOVERY_OPERATOR'],[]),
            ('LAB-REVIEWER',['APPROVE'],['SEMANTIC','SECURITY','MIGRATION','IRREVERSIBLE','LOCKED_DECISION']),
            ('other',['RECEIPT_READ'],[]),('limited',['APPROVE'],['SEMANTIC'])]:
            grants.append({'id':'LAB-GRANT-'+principal,'principal':principal,'actions':actions,'scopes':scopes,'validFrom':0,'validUntil':100000,'revokedAt':None})
        config={'version':'acp-route-a-host/1','classification':LABEL,'repositoryId':'LAB-REPOSITORY',
            'applicationId':'APP-ROUTE-A-LAB','serviceId':'LAB-SERVICE','issuer':'urn:test:route-a:issuer',
            'audience':'urn:test:route-a:audience','algorithm':'Ed25519','policyVersion':'LAB-POLICY-1',
            'keys':[{'id':'LAB-KEY-'+p,'principal':principals[p],'purpose':p,'publicKey':k.public_key().public_bytes_raw().hex(),
                     'validFrom':0,'validUntil':100000,'revokedAt':None} for p,k in self.keys.items()],
            'grants':grants,'maxSessionAge':300,'maxProofLifetime':300,'witnessMaxAge':30}
        self.host=self.authenticated_host(config)
        self.witness_path=str(directory/'independent-witness.sqlite')
        with closing(sqlite3.connect(self.witness_path)) as db, db:
            db.execute('CREATE TABLE checkpoints (sequence INTEGER PRIMARY KEY, body BLOB NOT NULL)')
            db.execute('CREATE TABLE entries (sequence INTEGER PRIMARY KEY, body BLOB NOT NULL)')
        self.outage=False;self.fork=False;self.stale=False
        lab=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                try:
                    require(not lab.outage,'laboratory witness unavailable')
                    req=decode(self.rfile.read(int(self.headers['Content-Length'])))
                    with closing(sqlite3.connect(lab.witness_path)) as db, db:
                        db.execute('BEGIN IMMEDIATE')
                        row=db.execute('SELECT body FROM checkpoints ORDER BY sequence DESC LIMIT 1').fetchone()
                        checkpoint=loads(row[0]) if row else None
                        if self.path=='/advance':
                            commit,receipt=req['commit'],bytes.fromhex(req['receipt'])
                            rd=verify_receipt(lab.host,receipt,commit,lab.now)
                            new={'head':commit['newHead'],'receiptDigest':rd}
                            if checkpoint!=new:
                                prior=db.execute('SELECT body FROM entries ORDER BY sequence DESC LIMIT 1').fetchone()
                                verify_witness_submission(lab.host,commit,receipt,req['nativeBundle'],checkpoint,loads(prior[0]) if prior else None)
                                require((checkpoint is None and commit['previousHead']=='EMPTY_UNINITIALIZED'
                                         and commit['newHead']['sequence']==0) or
                                        (checkpoint is not None and checkpoint['head']==commit['previousHead']
                                         and commit['newHead']['sequence']==checkpoint['head']['sequence']+1),'witness fork/stale update')
                                db.execute('INSERT INTO checkpoints VALUES (?,?)',(commit['newHead']['sequence'],canonical_bytes(new)))
                                db.execute('INSERT INTO entries VALUES (?,?)',(commit['newHead']['sequence'],canonical_bytes(req['nativeBundle']['row'][3])))
                                checkpoint=new
                        else:require(self.path=='/latest','unknown witness method')
                    if lab.fork and checkpoint:
                        checkpoint={**checkpoint,'head':{**checkpoint['head'],'journalDigest':'sha256:'+'f'*64}}
                    body={'repositoryId':lab.host.config['repositoryId'],'applicationId':lab.host.config['applicationId'],
                        'challenge':req['challenge'],'observedAt':lab.now-(100 if lab.stale else 0),'checkpoint':checkpoint}
                    raw=lab.sign('witness',CHECKPOINT,body)
                    self.send_response(200);self.end_headers();self.wfile.write(raw)
                except Exception:
                    self.send_response(409);self.end_headers();self.wfile.write(b'LABORATORY_WITNESS_REJECTED')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join()

    def authenticated_host(self,config):
        raw=canonical_bytes(config)
        body={'classification':LABEL,'repositoryId':config['repositoryId'],'applicationId':config['applicationId'],
            'serviceId':config['serviceId'],'configurationDigest':hashed(raw),'issuedAt':0,'notBefore':0,'expiresAt':100000}
        signature=self.registration_key.sign(b'acp-route-a-host-registration/1\0'+canonical_bytes(body))
        registration=canonical_bytes({'proofVersion':'acp-route-a-host-registration/1','body':body,
            'signature':base64.b64encode(signature).decode()})
        return Host(raw,registration,self.registration_key.public_key().public_bytes_raw())

    def sign(self,purpose,version,body):
        body={'classification':LABEL,'algorithm':'Ed25519','issuer':self.host.config['issuer'],
            'audience':self.host.config['audience'],'keyId':'LAB-KEY-'+purpose,**body}
        sig=self.keys[purpose].sign(version.encode()+b'\0'+canonical_bytes(body))
        return canonical_bytes({'proofVersion':version,'body':body,'signature':base64.b64encode(sig).decode()})

    def session(self,principal='author',**overrides):
        return self.sign('authentication','acp-route-a-session/1',{
            'repositoryId':self.host.config['repositoryId'],'applicationId':self.host.config['applicationId'],
            'serviceId':'LAB-SERVICE','principal':principal,'issuedAt':self.now,'notBefore':self.now,
            'expiresAt':self.now+200,'sessionId':LABEL+'-'+principal,**overrides})

    def approval(self,subject,**overrides):
        s=decode(subject)
        key=next(k for k in self.host.config['keys'] if k['purpose']=='approval')
        return self.sign('approval','acp-route-a-approval/2',{**s,'verificationPolicyVersion':'LAB-POLICY-1',
            'reviewerPrincipal':'LAB-REVIEWER','issuedAt':self.now,'notBefore':self.now,'expiresAt':self.now+200,
            'approvalId':'LAB-APPROVAL-'+s['operationId'],'nonce':secrets.token_hex(32),
            'identityEvidenceDigest':hashed(canonical_bytes(key)),
            'grantEvidenceDigest':self.host.grant('LAB-REVIEWER','APPROVE',s['requiredScopes'],self.now),
            'migrationDeclarationDecisionDigest':hashed(b'LAB-ONLY-DECLARATION') if 'MIGRATION' in s['requiredScopes'] else None,
            'permittedUse':'ACCEPTED_HISTORY_ONLY',**overrides})

    def service_sign(self,version,body):return self.sign('receipt',version,body)

    def _call(self,path,body):
        req=Request('http://127.0.0.1:'+str(self.server.server_port)+path,canonical_bytes(body),{'Content-Type':'application/json'},method='POST')
        try:
            with urlopen(req,timeout=5) as response:return response.read()
        except HTTPError as error:
            error.close()
            raise ValueError('laboratory witness rejected request') from None

    def latest(self,challenge):return self._call('/latest',{'challenge':challenge})
    def advance(self,challenge,commit,receipt_raw,native_bundle):
        return self._call('/advance',{'challenge':challenge,'commit':commit,'receipt':receipt_raw.hex(),'nativeBundle':native_bundle})


class RemoteWitness:
    """Spawned test processes talk to the independently stored parent loopback witness."""
    def __init__(self,port):self.port=port
    def _call(self,path,body):
        req=Request('http://127.0.0.1:'+str(self.port)+path,canonical_bytes(body),{'Content-Type':'application/json'},method='POST')
        try:
            with urlopen(req,timeout=10) as response:return response.read()
        except HTTPError as error:
            error.close();raise ValueError('laboratory witness rejected request') from None
    def latest(self,challenge):return self._call('/latest',{'challenge':challenge})
    def advance(self,challenge,commit,receipt_raw,native_bundle):
        return self._call('/advance',{'challenge':challenge,'commit':commit,'receipt':receipt_raw.hex(),'nativeBundle':native_bundle})
