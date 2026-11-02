import {test,expect} from '@playwright/test';import fs from 'node:fs';
import {reportContract as c} from '../src/report-contract';import {createContract} from '../src/create-contract';
const headers={Authorization:'Bearer browser-authorized'},other={Authorization:'Bearer browser-report-tenant-two'};
const saved=process.env.ACP_DEMO_COMMIT!+'.report';
test('generated reports isolate tenants and owners, bind history and persist across regeneration',async({page})=>{
 const query=async(body:unknown={},auth=headers)=>page.request.post(c.path,{headers:auth,data:body});
 const history=async(id:string,auth=headers)=>page.request.post(c.path+'/history',{headers:auth,data:{resourceId:id,page:0,size:20}});
 await page.goto('/');
 if(process.env.ACP_DEMO_PHASE==='report-commit'){
  const old=JSON.parse(fs.readFileSync(process.env.ACP_DEMO_COMMIT!,'utf8'));
  const ids:Record<string,string>={archived:old.result.resourceId};
  for(const [key,title,summary,auth] of [['alpha','Alpha case','Alpha active',headers],['beta','Beta case','Beta active',headers],['gamma','Gamma case','Gamma active',headers],['foreign','Foreign case','tenant two confidential',other]] as const){
   const response=await page.request.post(createContract.path,{headers:auth,data:{title,summary,idempotencyKey:'r5-'+key}});expect(response.status()).toBe(200);ids[key]=(await response.json()).resourceId;
  }
  const response=await query();expect(response.status()).toBe(200);const all=await response.json();expect(all.total).toBe(4);expect(all.items).toHaveLength(2);
  expect(Object.fromEntries(all.counts.map((r:any)=>[r.state,Number(r.count)]))).toEqual({'STATE-ARCHIVED':1,'STATE-OPEN':3});
  const next=await (await query({page:1,size:2})).json();expect(new Set([...all.items,...next.items].map((r:any)=>r.resourceId)).size).toBe(4);
  for(const item of [...all.items,...next.items])expect(Object.keys(item.values).sort()).toEqual(['FLD-CASE-TITLE','FLD-TASK-SUMMARY']);
  const foreign=await (await query({},other)).json();expect(foreign.total).toBe(1);expect(foreign.items[0].resourceId).toBe(ids.foreign);
  expect((await history(ids.foreign)).status()).toBe(404);expect((await history(ids.archived,other)).status()).toBe(404);expect((await history('hidden-owned')).status()).toBe(404);
  expect((await history('not-existing')).status()).toBe(404);
  for(const token of ['browser-outsider','browser-expired','invalid']){const status=token==='browser-outsider'?403:401;expect((await query({},{Authorization:'Bearer '+token})).status()).toBe(status);expect((await history(ids.archived,{Authorization:'Bearer '+token})).status()).toBe(status);}
  for(const body of [{tenant:'tenant-two'},{filters:{tenant:'tenant-two'}},{filters:{sql:'SELECT *'}},{filters:{summary:null}},{filters:{summary:3}},{filters:{state:'UNKNOWN'}},{sort:{field:'FLD-NOTE',direction:'ASC'}},{sort:{field:'STATE',direction:'DROP'}},{sort:{field:'STATE',direction:'ASC',sql:'x'}},{page:-1},{page:1001},{size:0},{size:21},{page:1.5},[],null])expect((await query(body)).status()).toBe(400);
  expect((await (await query({filters:{summary:"' OR 1=1 --"}})).json()).total).toBe(0);
  expect((await (await query({page:1000})).json()).items).toHaveLength(0);
  const audit=await (await history(ids.archived)).json();expect(audit.total).toBe(4);expect(audit.items.map((r:any)=>r.operation)).toEqual(['CREATE-CASE','CMD-REVIEW','CMD-APPROVE','CMD-ARCHIVE']);
  for(const entry of audit.items)expect(Object.keys(entry).sort()).toEqual(['occurredAt','operation']);
  await page.getByRole('button',{name:'Refresh report',exact:true}).click();await expect(page.getByText('4 permitted cases',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Next report page',exact:true}).click();await expect(page.getByText('Page 2',{exact:true})).toBeVisible();
  await page.getByLabel('Report summary',{exact:true}).fill('Alpha');await page.getByRole('button',{name:'Refresh report',exact:true}).click();await expect(page.getByText('1 permitted cases',{exact:true})).toBeVisible();await expect(page.getByRole('table',{name:'Report results'})).toContainText('Alpha active');
  await page.getByLabel('Report summary',{exact:true}).fill('nothing matches');await page.getByRole('button',{name:'Refresh report',exact:true}).click();await expect(page.getByText('No report results',{exact:true})).toBeVisible();
  await page.getByLabel('Report summary',{exact:true}).fill('');await page.getByLabel('Report state',{exact:true}).selectOption('STATE-ARCHIVED');await page.getByRole('button',{name:'Refresh report',exact:true}).click();await expect(page.getByText('1 permitted cases',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'History '+ids.archived,exact:true}).click();await expect(page.getByRole('region',{name:'Selected audit history'})).toContainText('CMD-ARCHIVE');
  await page.getByRole('button',{name:'Refresh report',exact:true}).focus();expect(await page.evaluate(()=>document.activeElement?.tagName)).toBe('BUTTON');
  await page.evaluate(()=>(window as any).testIdentity('expired'));await page.getByRole('button',{name:'Refresh report',exact:true}).click();await expect(page.getByText('Reporting unavailable',{exact:true})).toBeVisible();await page.evaluate(()=>(window as any).testIdentity('authorized'));
  await page.reload();await expect(page.getByText('4 permitted cases',{exact:true})).toBeVisible();
  fs.writeFileSync(saved,JSON.stringify({ids,all,audit,foreign}));
 }else{
  const before=JSON.parse(fs.readFileSync(saved,'utf8'));await expect(page.getByText('4 permitted cases',{exact:true})).toBeVisible();
  expect(await (await query()).json()).toEqual(before.all);expect(await (await history(before.ids.archived)).json()).toEqual(before.audit);expect(await (await query({},other)).json()).toEqual(before.foreign);
  expect((await history(before.ids.foreign)).status()).toBe(404);
 }
 await page.setViewportSize({width:390,height:844});await expect(page.getByRole('button',{name:'Refresh report',exact:true})).toBeVisible();
 await page.screenshot({path:process.env.ACP_DEMO_SCREENSHOT!,fullPage:true});
});
