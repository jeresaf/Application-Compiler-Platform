"""Test-only real browser/server fixture. Never emitted in production source."""
import json
from phase6_reference_tests import seed_sql,symbol

def server_source(domain):
    root='ENT-PAYMENT' if domain=='payment' else 'CASE'
    table=symbol(root,'e');summary=symbol('FLD-TASK-SUMMARY','f')
    seed=''.join('jdbc.execute('+json.dumps(s)+');' for s in seed_sql(domain))
    return '''package acp.browser;
import java.time.Instant;
import java.util.*;
import org.springframework.boot.SpringApplication;
import org.springframework.context.annotation.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.oauth2.jwt.*;
import org.flywaydb.core.Flyway;
/** Test authority only; runs on loopback using test classpath. */
@Configuration @Import({acp.Application.class,BrowserServer.Fixture.class})
public class BrowserServer {
 public static void main(String[] args){SpringApplication.run(BrowserServer.class,args);}
 @Bean acp.infrastructure.JobRuntime.PrincipalPort principal(JwtDecoder decoder){return (id,revision,handle)->decoder.decode("browser-authorized");}
 @Bean JwtDecoder decoder(){return token->{
  if(!Set.of("browser-authorized","browser-competing","browser-outsider","browser-wrong-tenant","browser-expired").contains(token))throw new JwtException("TEST_AUTHORITY");
  if(token.equals("browser-expired"))throw new JwtException("TEST_EXPIRED");
  var now=Instant.now();return Jwt.withTokenValue(token).header("alg","test-only").subject(token.equals("browser-outsider")?"outsider":"fixture:operator")
   .claim("tenant",token.equals("browser-wrong-tenant")?"tenant-two":"tenant-one").claim("sid",token.equals("browser-competing")?"competing-session":"browser-session").claim("amr",List.of("pwd","otp")).claim("auth_time",now.getEpochSecond()).issuedAt(now).expiresAt(now.plusSeconds(3600)).build();};}
 @RestController static class Fixture {
  final JdbcTemplate jdbc;final Flyway flyway;final org.springframework.transaction.PlatformTransactionManager manager;
  Fixture(JdbcTemplate jdbc,Flyway flyway,org.springframework.transaction.PlatformTransactionManager manager){this.jdbc=jdbc;this.flyway=flyway;this.manager=manager;}
  @PostMapping("/__test/reset") Map<String,Object> reset(){flyway.clean();flyway.migrate();return new org.springframework.transaction.support.TransactionTemplate(manager).execute(status->{SEED return facts();});}
  @GetMapping("/__test/facts") Map<String,Object> facts(){return Map.of("rows",jdbc.queryForList("SELECT convert_from(SUMMARY,'UTF8') AS text,acp_version AS version,acp_state AS state FROM ROOT"),"events",jdbc.queryForObject("SELECT count(*) FROM acp_outbox",Integer.class),"idempotency",jdbc.queryForObject("SELECT count(*) FROM acp_idempotency WHERE status='COMMITTED_RESULT'",Integer.class));}
  @PostMapping("/__test/unicode") void unicode(){jdbc.update("UPDATE ROOT SET SUMMARY=?","Case e\u0301 🦋".getBytes(java.nio.charset.StandardCharsets.UTF_8));}
  @PostMapping("/__test/terminal") void terminal(){jdbc.execute("UPDATE ROOT SET acp_state='TERMINAL'");}
  @PostMapping("/__test/revoke") void revoke(){jdbc.execute("UPDATE acp_sessions SET revoked=true");}
 }
}
'''.replace('SEED',seed).replace('SUMMARY',summary).replace('ROOT',table).replace('TERMINAL','STATE-POSTED' if domain=='payment' else 'STATE-ARCHIVED')

IDENTITY='''export type IdentityHints={actor:string;subject:string;tenant:string;permissions:ReadonlySet<string>};
import {ui} from '../task-ui-model';
let token='browser-authorized';let hints:IdentityHints={actor:ui.boundary.data.actor.id,subject:'fixture:operator',tenant:'tenant-one',permissions:new Set(ui.boundary.data.permissions.map(p=>p.id))};
const listeners=new Set<()=>void>();
export function identity(){return hints;}
export function permissions(){return hints.permissions;}
export async function accessToken(){return token;}
export function onIdentityChange(f:()=>void){listeners.add(f);return ()=>{listeners.delete(f);};}
Object.assign(window,{testIdentity:(mode:string)=>{token=mode==='wrong-tenant'?'browser-wrong-tenant':mode==='expired'?'browser-expired':mode==='missing-action'||mode==='missing-query'?'browser-outsider':'browser-authorized';hints={actor:ui.boundary.data.actor.id,subject:token==='browser-outsider'?'outsider':'fixture:operator',tenant:mode==='wrong-tenant'?'tenant-two':'tenant-one',permissions:new Set(mode==='missing-action'?ui.boundary.data.permissions.filter(p=>!ui.action.data.permissions.some(a=>a.id===p.id)).map(p=>p.id):mode==='missing-query'?ui.action.data.permissions.map(p=>p.id):ui.boundary.data.permissions.map(p=>p.id))};listeners.forEach(f=>f());}});
'''

CONFIG='''import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./browser-tests',workers:1,timeout:60000,use:{baseURL:'http://127.0.0.1:4173',browserName:'chromium',trace:'retain-on-failure'},reporter:[['list'],['json',{outputFile:'browser-results.json'}]],projects:[{name:'COMPACT',use:{viewport:{width:390,height:844}}},{name:'EXPANDED',use:{viewport:{width:1280,height:900}}}]});
'''

def tests(domain):
    return '''import {test,expect,type Page} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {ui} from '../src/task-ui-model';
const headers={Authorization:'Bearer browser-authorized'};
const events=EVENTS;
async function axe(page:Page,label:string){const r=await new AxeBuilder({page}).analyze();await test.info().attach('axe-'+label,{body:JSON.stringify(r),contentType:'application/json'});expect(r.violations.filter(v=>v.impact==='serious'||v.impact==='critical')).toEqual([]);}
async function facts(page:Page){return (await page.request.get('/__test/facts',{headers})).json();}
async function select(page:Page){await page.getByRole('button',{name:'Select fixture-resource',exact:true}).click();}
async function note(page:Page,text='browser note 🦋'){await page.getByLabel('Task note',{exact:true}).fill(text);}
async function invoke(page:Page){await page.getByRole('button',{name:'Complete task',exact:true}).click();await expect(page.getByRole('dialog')).toBeVisible();}
test.beforeEach(async({page})=>{expect((await page.request.post('/__test/reset',{headers})).status()).toBe(200);await page.goto('/');await expect(page.getByRole('button',{name:'Select fixture-resource',exact:true})).toBeVisible();});
test('production typed query, semantic order, keyboard journey, exact database effect and axe',async({page,browser})=>{
 await test.info().attach('browser-profile',{body:JSON.stringify({version:browser.version(),engine:'chromium',viewport:page.viewportSize(),profile:ui.browserProfile}),contentType:'application/json'});
 const order=await page.locator('section[data-semantic-id]').evaluateAll(es=>es.map(e=>e.getAttribute('data-semantic-id')));expect(order).toEqual(ui.screen.data.content.map(r=>r.id));
 expect(await page.locator('thead th').allTextContents()).toEqual([ui.columns[0].name,'Selection']);await axe(page,'results');
 await page.keyboard.press('Tab');await expect(page.getByLabel('Find a task')).toBeFocused();await page.keyboard.type('not-found');await page.keyboard.press('Tab');await page.keyboard.press('Enter');
 await expect(page.getByText('Task view: empty',{exact:true})).toBeVisible();await axe(page,'empty');
 await page.getByLabel('Find a task').focus();await page.keyboard.press('ControlOrMeta+A');await page.keyboard.press('Backspace');
 const query=page.waitForRequest(r=>r.url().includes(ui.queryPath)&&r.method()==='POST');await page.keyboard.press('Tab');await page.keyboard.press('Enter');expect((await query).postDataJSON()).toEqual({'QUERY-TEXT':''});
 await expect(page.getByRole('button',{name:'Select fixture-resource'})).toBeVisible();await page.keyboard.press('Tab');await page.keyboard.press('Enter');
 await expect(page.getByLabel('Resource identity')).toHaveValue('fixture-resource');await page.keyboard.press('Tab');await page.keyboard.press('Tab');
 await expect(page.getByLabel('Task note')).toBeFocused();await page.keyboard.press('Tab');await page.keyboard.press('Enter');await expect(page.getByRole('alert')).toBeFocused();await expect(page.getByText('Enter a task note.',{exact:true}).first()).toBeVisible();await axe(page,'validation');
 await page.getByLabel('Task note').focus();await page.keyboard.type('browser note 🦋');await page.keyboard.press('Tab');await page.keyboard.press('Enter');await expect(page.getByRole('dialog')).toBeVisible();await axe(page,'confirmation');
 await page.keyboard.press('Enter');await expect(page.getByRole('dialog')).not.toBeVisible();await expect(page.getByRole('button',{name:'Complete task',exact:true})).toBeFocused();expect((await facts(page)).events).toBe(0);
 await page.keyboard.press('Enter');await page.keyboard.press('Tab');await page.keyboard.press('Enter');await expect(page.getByText('Task view: success',{exact:true})).toBeVisible();await expect(page.locator('section[role="status"]')).toBeFocused();expect(await page.evaluate(()=>{const r=document.activeElement!.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight;})).toBe(true);await axe(page,'success');
 const f=await facts(page);expect(f.events).toBe(events);expect(f.rows[0]).toEqual({text:'browser note 🦋',version:events,state:FINAL_STATE});expect(f.idempotency).toBe(events);
 await expect(page.locator('tbody')).toContainText('browser note 🦋');expect(await page.locator('input,textarea,button').evaluateAll(es=>es.every(e=>{const r=e.getBoundingClientRect();return r.width===0||(r.left>=0&&r.right<=innerWidth);}))).toBe(true);
});
test('rapid confirmation and committed response loss replay one logical key',async({page})=>{
 await select(page);await note(page,'lost response');await invoke(page);
 let lost=false;const keys:string[]=[];
 await page.route('**'+ui.actionPath,async route=>{keys.push(route.request().postDataJSON().idempotencyKey);if(!lost){lost=true;const response=await route.fetch();expect(response.status()).toBe(200);await route.abort('connectionreset');}else await route.continue();});
 await page.getByRole('button',{name:'Confirm',exact:true}).evaluate(e=>{(e as HTMLButtonElement).click();(e as HTMLButtonElement).click();});
 await expect(page.getByRole('alert')).toBeVisible();expect((await facts(page)).events).toBe(events);
 await page.getByRole('button',{name:'Complete task — recovery',exact:true}).click();await page.getByRole('button',{name:'Confirm',exact:true}).click();await expect(page.getByText('Task view: success',{exact:true})).toBeVisible();expect(keys.length).toBe(2);expect(keys[0]).toBe(keys[1]);expect((await facts(page)).events).toBe(events);
});
test('permissions, forged calls, wrong tenant and identity change clear protected state',async({page})=>{
 for(const mode of ['missing-action','missing-query']){await page.evaluate(m=>(window as any).testIdentity(m),mode);await expect(page.getByRole('alert')).toBeVisible();await expect(page.locator('table')).toHaveCount(0);await expect(page.getByRole('button',{name:'Complete task',exact:true})).toHaveCount(0);await axe(page,'denied-'+mode);
 const denied=await page.request.post(ui.actionPath,{headers:{Authorization:'Bearer browser-outsider'},data:{expectedVersion:0,idempotencyKey:'forged',input:{'INPUT-TASK-RESOURCE':'fixture-resource','INPUT-TASK-TEXT':'forged'}}});expect(denied.status()).toBe(403);}
 await page.evaluate(()=>(window as any).testIdentity('wrong-tenant'));await page.getByRole('button',{name:'Search',exact:true}).click();await expect(page.getByText('Task view: empty',{exact:true})).toBeVisible();expect((await facts(page)).events).toBe(0);
});
test('semantic workflow failure rolls back and announces safely',async({page})=>{
 const keys:string[]=[];page.on('request',r=>{if(r.url().includes(ui.actionPath)&&r.method()==='POST')keys.push(r.postDataJSON().idempotencyKey);});
 await page.request.post('/__test/terminal',{headers});await select(page);await note(page);await invoke(page);await page.getByRole('button',{name:'Confirm',exact:true}).click();await expect(page.getByRole('alert')).toBeFocused();await expect(page.getByRole('alert')).toContainText('Task view: error');expect((await facts(page)).events).toBe(0);expect((await facts(page)).rows[0].text).toBe('old');expect(await page.locator('body').textContent()).not.toMatch(/SQLException|stacktrace|private-note/);
 await page.getByRole('button',{name:'Complete task — recovery',exact:true}).click();await page.getByRole('button',{name:'Confirm',exact:true}).click();await expect(page.getByRole('alert')).toBeFocused();expect(keys.length).toBe(2);expect(keys[0]).toBe(keys[1]);expect((await facts(page)).events).toBe(0);
});
test('exact Unicode case-sensitive filter transport and expired identity clear data',async({page})=>{
 expect((await page.request.post('/__test/unicode',{headers})).status()).toBe(200);
 for(const [value,count] of [['Case',1],['case',0],['e\u0301',1],['é',0],['🦋',1],['',1]] as const){
  await expect(page.getByLabel('Find a task')).toBeEnabled();await page.getByLabel('Find a task').fill(value);
  const request=page.waitForRequest(r=>r.url().includes(ui.queryPath)&&r.method()==='POST');
  await page.getByRole('button',{name:'Search',exact:true}).click();expect((await request).postDataJSON()).toEqual({'QUERY-TEXT':value});
  await expect(page.locator('tbody tr')).toHaveCount(count);
 }
 await page.evaluate(()=>(window as any).testIdentity('expired'));await expect(page.locator('table')).toHaveCount(0);await page.getByRole('button',{name:'Search',exact:true}).click();await expect(page.getByRole('alert')).toBeVisible();await expect(page.getByLabel('Task note')).toHaveValue('');
});
test('stale version rejects without overwrite; revoked session clears data',async({page})=>{
 await select(page);await note(page);const peer=await page.request.post(ui.actionPath,{headers:{Authorization:'Bearer browser-competing'},data:{expectedVersion:0,idempotencyKey:'competing-session-action',input:{[ui.resourceInputField]:'fixture-resource',[ui.textInputField]:'competing note'}}});expect(peer.status()).toBe(200);const committed=await facts(page);expect(committed.rows[0]).toEqual({text:'competing note',version:events,state:FINAL_STATE});expect(committed.events).toBe(events);await invoke(page);await page.getByRole('button',{name:'Confirm',exact:true}).click();await expect(page.getByRole('alert')).toBeFocused();expect(await facts(page)).toEqual(committed);await expect(page.getByLabel('Resource identity')).toHaveValue('');
 await page.getByRole('button',{name:'Retry search',exact:true}).click();await expect(page.getByRole('button',{name:'Select fixture-resource'})).toBeVisible();await page.request.post('/__test/revoke',{headers});await page.getByRole('button',{name:'Search',exact:true}).click();await expect(page.locator('table')).toHaveCount(0);await expect(page.getByRole('alert')).toBeVisible();
});
'''.replace('EVENTS','1' if domain=='payment' else '3').replace('FINAL_STATE',json.dumps('STATE-POSTED' if domain=='payment' else 'STATE-ARCHIVED'))
