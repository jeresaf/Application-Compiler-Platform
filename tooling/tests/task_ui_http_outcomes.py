"""Supplement full UI journeys with exact real HTTP outcome assertions."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import check_task_interface as gate
from target_worker import bundle_digest
SPEC='''import {test,expect,type Page} from '@playwright/test';
import {ui} from '../src/task-ui-model';
const headers={Authorization:'Bearer browser-authorized'};
const events=EVENTS;
async function facts(page:Page){return (await page.request.get('/__test/facts',{headers})).json();}
async function prepare(page:Page){await page.getByRole('button',{name:'Select fixture-resource',exact:true}).click();await page.getByLabel('Task note').fill('original note');}
async function confirm(page:Page){await page.getByRole('button',{name:'Complete task',exact:true}).click();await expect(page.getByRole('dialog')).toBeVisible();const response=page.waitForResponse(r=>r.url().includes(ui.actionPath)&&r.request().method()==='POST');await page.getByRole('button',{name:'Confirm',exact:true}).click();return response;}
test.beforeEach(async({page})=>{expect((await page.request.post('/__test/reset',{headers})).status()).toBe(200);await page.goto('/');await expect(page.getByRole('button',{name:'Select fixture-resource',exact:true})).toBeVisible();});
test('supplemental HTTP semantic Failure is the exact versioned envelope',async({page})=>{
 await page.request.post('/__test/terminal',{headers});await prepare(page);const response=await confirm(page);expect(response.status()).toBe(422);expect(response.headers()['acp-failure-profile']).toBe('1.0.0');const body=await response.json();expect(Object.keys(body).sort()).toEqual(['category','code','correlationId','failureId','failureRevision','operationId','operationRevision','retryable']);expect(body.failureId).toBe('FAIL-BUSINESS');expect(body.failureRevision).toBe(1);expect(body.retryable).toBe(false);expect(body.correlationId).toBeTruthy();await expect(page.getByRole('alert')).toBeFocused();expect((await facts(page)).events).toBe(0);await test.info().attach('http-failure',{body:JSON.stringify({status:response.status(),envelope:body,database:await facts(page)}),contentType:'application/json'});
});
test('supplemental HTTP stale version is 409 after a real competing session',async({page})=>{
 await prepare(page);const peer=await page.request.post(ui.actionPath,{headers:{Authorization:'Bearer browser-competing'},data:{expectedVersion:0,idempotencyKey:'supplemental-peer',input:{[ui.resourceInputField]:'fixture-resource',[ui.textInputField]:'competing note'}}});expect(peer.status()).toBe(200);const committed=await facts(page);expect(committed.events).toBe(events);const response=await confirm(page);expect(response.status()).toBe(409);await expect(page.getByRole('alert')).toBeFocused();await expect(page.getByLabel('Resource identity')).toHaveValue('');expect(await facts(page)).toEqual(committed);await test.info().attach('http-stale',{body:JSON.stringify({peerStatus:peer.status(),staleStatus:response.status(),before:committed,after:await facts(page)}),contentType:'application/json'});
});
test('supplemental HTTP expired identity is 401 and clears protected data',async({page})=>{
 await prepare(page);await page.evaluate(()=>(window as any).testIdentity('expired'));const response=page.waitForResponse(r=>r.url().includes(ui.queryPath)&&r.request().method()==='POST');await page.getByRole('button',{name:'Search',exact:true}).click();expect((await response).status()).toBe(401);await expect(page.locator('table')).toHaveCount(0);await expect(page.getByLabel('Task note')).toHaveValue('');await test.info().attach('http-expired',{body:JSON.stringify({status:401,protectedDataCleared:true}),contentType:'application/json'});
});
test('supplemental HTTP revoked session is denied and clears protected data',async({page})=>{
 await prepare(page);await page.request.post('/__test/revoke',{headers});const response=page.waitForResponse(r=>r.url().includes(ui.queryPath)&&r.request().method()==='POST');await page.getByRole('button',{name:'Search',exact:true}).click();const status=(await response).status();expect([401,403]).toContain(status);await expect(page.locator('table')).toHaveCount(0);await expect(page.getByLabel('Task note')).toHaveValue('');await expect(page.getByRole('alert')).toBeFocused();await test.info().attach('http-revoked',{body:JSON.stringify({status,protectedDataCleared:true}),contentType:'application/json'});
});
'''
def run(root):
 out=root/'supplemental-http';out.mkdir(exist_ok=False)
 report={'bundleDigest':bundle_digest(),'mode':'REAL_HTTP_OUTCOMES','domains':{}}
 original=gate.command
 def command(cmd,cwd,log,timeout=900):
  if cmd==['npm','run','e2e']:cmd=cmd+['--','--grep','supplemental HTTP']
  return original(cmd,cwd,log,timeout)
 gate.command=command
 try:
  for domain in ('payment','case-management'):
   front=root/domain/'frontend';p=front/'browser-tests/http-outcomes.spec.ts';p.parent.mkdir(exist_ok=True);p.write_text(SPEC.replace('EVENTS','1' if domain=='payment' else '3'))
   results=front/'browser-results.json';previous=results.read_bytes() if results.exists() else None
   try:
    browser=gate.browser(root/domain,domain,out);stats=browser['stats'];assert stats['expected']==8 and stats['unexpected']==0 and stats['flaky']==0
    report['domains'][domain]=browser
    (out/(domain+'-http-results.json')).write_text(json.dumps(browser,indent=2)+'\n')
   finally:
    if previous is not None:results.write_bytes(previous)
   print(domain+' HTTP OUTCOMES PASS',flush=True)
 finally:gate.command=original
 report['result']='PASS';(out/'http-outcomes-report.json').write_text(json.dumps(report,indent=2)+'\n')
 return 0
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();raise SystemExit(run(a.root.resolve()))
