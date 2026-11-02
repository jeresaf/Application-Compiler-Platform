import {test,expect} from '@playwright/test';import fs from 'node:fs';import {createContract} from '../src/create-contract';import {ui} from '../src/task-ui-model';
const headers={Authorization:'Bearer browser-authorized'};
test('successor accepts new case workflow and restart replays without duplicate effects',async({page})=>{
 await page.goto('/');const file=process.env.ACP_DEMO_COMMIT!+'.r8-successor';
 if(process.env.ACP_DEMO_PHASE==='successor-commit'){
  const before=await (await page.request.get('/__test/facts',{headers})).json();
  await page.getByLabel('title',{exact:true}).fill('R8 successor case');await page.getByLabel('summary',{exact:true}).fill('after evolution');const created=page.waitForResponse(r=>r.url().endsWith(createContract.path)&&r.request().method()==='POST');await page.getByRole('button',{name:'Create case',exact:true}).click();const response=await created;expect(response.status()).toBe(200);const value=await response.json();expect(value.state).toBe('STATE-OPEN');
  await page.getByRole('button',{name:'Search',exact:true}).click();await page.getByRole('button',{name:'Select '+value.resourceId,exact:true}).click();await page.getByLabel('Task note',{exact:true}).fill('R8 successor workflow');await page.getByRole('button',{name:'Complete task',exact:true}).click();const completed=page.waitForResponse(r=>r.url().includes(ui.actionPath)&&r.request().method()==='POST');await page.getByRole('button',{name:'Confirm',exact:true}).click();const result=await completed;expect(result.status()).toBe(200);expect(await result.json()).toMatchObject({resourceId:value.resourceId,version:3,state:'STATE-ARCHIVED'});
  const after=await (await page.request.get('/__test/facts',{headers})).json();expect(after.events).toBe(before.events+3);expect(after.idempotency).toBe(before.idempotency+4);expect(after.rows).toContainEqual({text:'R8 successor workflow',version:3,state:'STATE-ARCHIVED'});fs.writeFileSync(file,JSON.stringify({id:value.resourceId,create:response.request().postDataJSON(),action:result.request().postDataJSON(),facts:after}));
 }else{
  const saved=JSON.parse(fs.readFileSync(file,'utf8'));const created=await page.request.post(createContract.path,{headers,data:saved.create});expect(created.status()).toBe(200);expect((await created.json()).resourceId).toBe(saved.id);const completed=await page.request.post(ui.actionPath,{headers,data:saved.action});expect(completed.status()).toBe(200);expect(await completed.json()).toMatchObject({resourceId:saved.id,version:3,state:'STATE-ARCHIVED'});expect(await (await page.request.get('/__test/facts',{headers})).json()).toEqual(saved.facts);
 }
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:process.env.ACP_DEMO_SCREENSHOT!,fullPage:true});
});
