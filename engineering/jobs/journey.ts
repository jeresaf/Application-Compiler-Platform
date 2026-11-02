import {test,expect} from '@playwright/test';import fs from 'node:fs';import {jobContract as c} from '../src/job-contract';
const headers={Authorization:'Bearer browser-authorized'};
test('actual generated service workers expose durable owner-scoped integrity results',async({page})=>{
 const saved=JSON.parse(fs.readFileSync(process.env.ACP_DEMO_COMMIT!+'.documents','utf8'));await page.goto('/');const request=async(data:unknown,token='browser-authorized')=>page.request.post(c.path+'/results',{headers:{Authorization:'Bearer '+token},data});
 const response=await request({resourceId:saved.resource});expect(response.status()).toBe(200);const value=await response.json();expect(value.items.length).toBeGreaterThanOrEqual(3);expect(value.items.some((r:any)=>r.state==='COMPLETED'&&r.result==='VALID')).toBeTruthy();expect(value.items.some((r:any)=>r.state==='FAILED'&&r.result==='HASH_MISMATCH')).toBeTruthy();
 for(const row of value.items){expect(Object.keys(row)).not.toContain('content');expect(Object.keys(row)).not.toContain('payload');expect(Object.keys(row)).not.toContain('owner');expect(row.error??'').not.toContain('Exception');}
 for(const [token,status] of [['browser-outsider',403],['browser-expired',401],['invalid',401],['browser-report-tenant-two',404]] as const)expect((await request({resourceId:saved.resource},token)).status()).toBe(status);
 expect((await request({resourceId:'hidden-owned'})).status()).toBe(404);expect((await request({resourceId:saved.resource,tenant:'tenant-two'})).status()).toBe(400);expect((await request({resourceId:'../bad'})).status()).toBe(400);
 await page.getByLabel('Job resource',{exact:true}).fill(saved.resource);await page.getByRole('button',{name:'Refresh jobs',exact:true}).click();await expect(page.getByRole('list',{name:'Integrity job results'})).toContainText('COMPLETED');await expect(page.getByRole('list',{name:'Integrity job results'})).toContainText('HASH_MISMATCH');await expect(page.getByRole('button',{name:'Run job',exact:true})).toHaveCount(0);
 const file=process.env.ACP_DEMO_COMMIT!+'.jobs';if(process.env.ACP_DEMO_PHASE==='jobs-commit')fs.writeFileSync(file,JSON.stringify(value));else expect(value).toEqual(JSON.parse(fs.readFileSync(file,'utf8')));
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:process.env.ACP_DEMO_SCREENSHOT!,fullPage:true});
});
