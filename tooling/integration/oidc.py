"""Disposable standards-compatible issuer + deployed-adapter browser exercise.

The issuer is integration infrastructure, never generated or packaged. The
adapter is the deployment-owned PKCE fixture, not the browser-test authority.
"""
import argparse,base64,hashlib,json,os,secrets,subprocess,sys,tempfile,threading,time,urllib.parse,urllib.request
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'tooling'),str(ROOT/'tooling/tests')]

def b64(raw):return base64.urlsafe_b64encode(raw).decode().rstrip('=')

class Issuer:
 def __init__(self,root):
  self.key=root/'disposable-issuer.pem'
  subprocess.run(['openssl','genpkey','-algorithm','RSA','-pkeyopt','rsa_keygen_bits:2048','-out',str(self.key)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  modulus=subprocess.check_output(['openssl','rsa','-in',str(self.key),'-modulus','-noout'],stderr=subprocess.DEVNULL).decode().strip().split('=')[1]
  self.jwk={'kty':'RSA','use':'sig','alg':'RS256','kid':'disposable-integration','n':b64(bytes.fromhex(modulus)),'e':'AQAB'}
  self.codes={};self.tenant='tenant-one';self.expired=False
  issuer=self
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def response(self,value,status=200):
    raw=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Access-Control-Allow-Origin',self.headers.get('Origin','http://127.0.0.1:4173'));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
   def do_GET(self):
    url=urllib.parse.urlparse(self.path);q={k:v[0] for k,v in urllib.parse.parse_qs(url.query).items()}
    if url.path=='/.well-known/openid-configuration':self.response({'issuer':issuer.url,'authorization_endpoint':issuer.url+'/authorize','token_endpoint':issuer.url+'/token','jwks_uri':issuer.url+'/jwks','response_types_supported':['code'],'subject_types_supported':['public'],'id_token_signing_alg_values_supported':['RS256'],'code_challenge_methods_supported':['S256']})
    elif url.path=='/jwks':self.response({'keys':[issuer.jwk]})
    elif url.path=='/authorize':
     if q.get('client_id')!='acp-disposable' or q.get('response_type')!='code' or q.get('code_challenge_method')!='S256' or urllib.parse.urlparse(q.get('redirect_uri','')).hostname!='127.0.0.1':self.response({'error':'invalid_request'},400);return
     code=secrets.token_urlsafe(32);issuer.codes[code]=dict(q,tenant=issuer.tenant,expired=issuer.expired)
     self.send_response(302);self.send_header('Location',q['redirect_uri']+'?'+urllib.parse.urlencode({'code':code,'state':q['state']}));self.end_headers()
    elif url.path=='/fixture/select':issuer.tenant=q.get('tenant','tenant-one');issuer.expired=q.get('expired')=='true';self.response({'selected':True})
    else:self.response({'error':'not_found'},404)
   def do_POST(self):
    q={k:v[0] for k,v in urllib.parse.parse_qs(self.rfile.read(int(self.headers.get('Content-Length',0))).decode()).items()}
    code=issuer.codes.pop(q.get('code',''),None)
    if q.get('grant_type')!='authorization_code' or not code or code['client_id']!=q.get('client_id') or code['redirect_uri']!=q.get('redirect_uri') or code['code_challenge']!=b64(hashlib.sha256(q.get('code_verifier','').encode()).digest()):self.response({'error':'invalid_grant'},400);return
    token=issuer.token(code['tenant'],code['expired'],code['nonce']);self.response({'access_token':token,'id_token':token,'token_type':'Bearer','expires_in':600})
  self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.url='http://127.0.0.1:'+str(self.server.server_port)
  self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
 def token(self,tenant='tenant-one',expired=False,nonce='job-integration'):
  now=int(time.time());claims={'iss':self.url,'aud':'acp-disposable','sub':'fixture:operator','tenant':tenant,'sid':secrets.token_hex(12),'amr':['pwd','otp'],'auth_time':now,'iat':now-3600 if expired else now,'exp':now-600 if expired else now+600,'nonce':nonce}
  body=b64(json.dumps({'alg':'RS256','kid':self.jwk['kid']}).encode())+'.'+b64(json.dumps(claims).encode())
  signed=subprocess.check_output(['openssl','dgst','-sha256','-sign',str(self.key)],input=body.encode());return body+'.'+b64(signed)
 def close(self):self.server.shutdown();self.server.server_close()

def run(projects,output):
 import check_task_interface as gate
 from task_ui_browser import server_source
 output.mkdir(parents=True,exist_ok=False)
 with tempfile.TemporaryDirectory(prefix='acp-disposable-oidc-') as temp:
  issuer=Issuer(Path(temp))
  try:
   service_token=issuer.token();gate.tests=lambda domain:spec(issuer.url,service_token)
   adapter=(ROOT/'fixtures/deployment-oidc/identity.ts').read_text()
   gate.IDENTITY=adapter+'''\nimport {ui} from '../task-ui-model';
configure({issuer:ISSUER,clientId:'acp-disposable',redirectUri:location.origin+'/',scopes:['openid'],developmentLoopback:true,hints:claims=>({actor:ui.boundary.data.actor.id,subject:String(claims.sub),tenant:String(claims.tenant),permissions:new Set(ui.boundary.data.permissions.map(p=>p.id))})});
void callback().catch(()=>clearIdentity());
Object.assign(window,{integrationLogin:login,integrationLogout:clearIdentity});
'''.replace('ISSUER',json.dumps(issuer.url))
   def server(domain):
    source=server_source(domain);start=source.index(' @Bean JwtDecoder decoder()');end=source.index(' @RestController',start)
    source=source[:start]+source[end:]
    return source.replace('decoder.decode("browser-authorized")','decoder.decode('+json.dumps(service_token)+')')
   gate.server_source=server
   original_popen=gate.subprocess.Popen
   def popen(args,*a,**kw):
    if isinstance(args,list) and 'acp.browser.BrowserServer' in args:
     args=args+['--spring.security.oauth2.resourceserver.jwt.issuer-uri='+issuer.url,'--spring.security.oauth2.resourceserver.jwt.audiences=acp-disposable']
    return original_popen(args,*a,**kw)
   gate.subprocess.Popen=popen
   reports={}
   try:
    for domain in ('payment','case-management'):
     reports[domain]=gate.browser(projects/domain,domain,output)
   finally:gate.subprocess.Popen=original_popen
   from target_worker import bundle_digest
   (output/'oidc-integration.json').write_text(json.dumps({'fixture':'AUTHORIZATION_CODE_PKCE_RS256_JWKS','bundleDigest':bundle_digest(),'domains':reports,'productionProviderAcceptance':'OUTSTANDING'},indent=2)+'\n')
  finally:issuer.close()

def spec(url,token):
 return '''import {test,expect} from '@playwright/test';
const issuer=ISSUER,headers={Authorization:'Bearer '+TOKEN};
test('oidcAcquisitionIdentityChangeExpiredAndWrongTenant',async({page})=>{
 await page.request.get(issuer+'/fixture/select?tenant=tenant-one');
 expect((await page.request.post('/__test/reset',{headers})).status()).toBe(200);
 await page.goto('/');await page.evaluate(()=>(window as any).integrationLogin());
 await expect(page.getByRole('button',{name:'Select fixture-resource',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Select fixture-resource',exact:true}).click();
 await page.getByLabel('Task note').fill('protected draft');
 await page.evaluate(()=>(window as any).integrationLogout());
 await expect(page.locator('table')).toHaveCount(0);await expect(page.getByLabel('Task note')).toHaveValue('');
 await page.request.get(issuer+'/fixture/select?tenant=tenant-two');
 await page.evaluate(()=>(window as any).integrationLogin());
 await expect(page.locator('table tbody tr')).toHaveCount(0);
 await page.request.get(issuer+'/fixture/select?tenant=tenant-one&expired=true');
 await page.evaluate(()=>(window as any).integrationLogout());await page.evaluate(()=>(window as any).integrationLogin());
 await expect(page.getByRole('alert')).toBeVisible();await expect(page.locator('table')).toHaveCount(0);
});
'''.replace('ISSUER',json.dumps(url)).replace('TOKEN',json.dumps(token))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--projects',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.projects.resolve(),a.output.resolve())
