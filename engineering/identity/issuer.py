"""Disposable HTTPS OIDC-compatible publisher. Private material exists only in memory/tmp."""
import base64,json,secrets,ssl,tempfile,threading,time,hmac,ipaddress
from pathlib import Path
from datetime import datetime,timezone,timedelta
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import jwt
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def public(key,kid):
    n=key.public_key().public_numbers();enc=lambda v:base64.urlsafe_b64encode(v.to_bytes((v.bit_length()+7)//8,'big')).decode().rstrip('=')
    return {'kty':'RSA','kid':kid,'alg':'RS256','use':'sig','n':enc(n.n),'e':enc(n.e)}

class Issuer:
    def __init__(self):
        self.auth_epoch=int(time.time());self.keys={k:rsa.generate_private_key(public_exponent=65537,key_size=2048) for k in ('h5-k1','h5-k2','untrusted')};self.active='h5-k1';self.tokens=[];self.paths=[];self.control=secrets.token_urlsafe(32);self.available=True
        self.temp=tempfile.TemporaryDirectory(prefix='acp-h5-private-');root=Path(self.temp.name)
        tls=rsa.generate_private_key(public_exponent=65537,key_size=2048);now=datetime.now(timezone.utc);name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'H5 disposable loopback issuer')])
        cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(tls.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1)).add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]),critical=False).add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True).sign(tls,hashes.SHA256())
        self.certificate=cert.public_bytes(serialization.Encoding.PEM);self.tls_private=tls.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption());(root/'cert.pem').write_bytes(self.certificate);(root/'key.pem').write_bytes(self.tls_private);(root/'key.pem').chmod(0o600)
        issuer=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def reply(self,value,status=200):
                raw=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
            def do_GET(self):
                issuer.paths.append(self.path)
                if not issuer.available:self.reply({'error':'unavailable'},503)
                elif self.path=='/.well-known/openid-configuration':self.reply({'issuer':issuer.url,'jwks_uri':issuer.url+'/jwks','token_endpoint':issuer.url+'/token','id_token_signing_alg_values_supported':['RS256'],'subject_types_supported':['public']})
                elif self.path=='/jwks':self.reply(issuer.jwks())
                else:self.reply({'error':'not_found'},404)
            def do_POST(self):
                issuer.paths.append(self.path)
                if self.path!='/token' or not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+issuer.control):self.reply({'error':'unauthorized'},401);return
                if int(self.headers.get('Content-Length','0'))>8192:self.reply({'error':'size'},400);return
                values=json.loads(self.rfile.read(int(self.headers['Content-Length'])));self.reply({'access_token':issuer.mint(**values),'token_type':'Bearer'})
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(root/'cert.pem',root/'key.pem');self.server.socket=context.wrap_socket(self.server.socket,server_side=True);self.url='https://127.0.0.1:'+str(self.server.server_port)
        self.context=ssl.create_default_context(cafile=str(root/'cert.pem'));self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def jwks(self,kids=('h5-k1','h5-k2')):return {'keys':[public(self.keys[k],k) for k in kids]}
    def mint(self,subject='fixture:operator',tenant='tenant-one',claims=None,headers=None,kid=None,algorithm='RS256'):
        now=int(time.time());payload={'iss':self.url,'aud':'acp-h5','sub':subject,'tenant':tenant,'sid':'h5-'+subject.replace(':','-')+'-'+tenant,'amr':['pwd','otp'],'auth_time':self.auth_epoch,'iat':now,'nbf':now-1,'exp':now+1800,'token_use':'access'}
        if claims:
            for k,v in claims.items():
                if v is None:payload.pop(k,None)
                else:payload[k]=v
        k=kid or self.active;head={'kid':k,'typ':'JWT',**(headers or {})}
        key=self.keys[k] if algorithm=='RS256' else b'h5-negative-algorithm-confusion-only' if algorithm=='HS256' else ''
        value=jwt.encode(payload,key,algorithm=algorithm,headers=head);self.tokens.append(value);return value
    def obtain(self,**values):
        import urllib.request
        r=urllib.request.Request(self.url+'/token',data=json.dumps(values).encode(),headers={'Authorization':'Bearer '+self.control,'Content-Type':'application/json'})
        with urllib.request.urlopen(r,context=self.context,timeout=5) as response:return json.load(response)['access_token']
    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=5);self.temp.cleanup()
