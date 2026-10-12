import {createRequire} from 'node:module';
import {readFile} from 'node:fs/promises';
import {PDFDocument} from 'pdf-lib';
import assert from 'node:assert/strict';
const {chromium}=createRequire(import.meta.url)(process.env.PREVIEW_PLAYWRIGHT||'playwright');
process.env.PORT='4175';const {server}=await import('../serve.mjs');
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({serviceWorkers:'block',viewport:{width:1280,height:850}});const errors=[];
page.on('pageerror',error=>errors.push(error.message));page.on('console',msg=>{if(msg.type()==='error')console.log('Browser:',msg.text());});
await page.addInitScript(()=>window.showSaveFilePicker=undefined);
const idle=()=>page.waitForFunction(()=>!window.preview.isBusy,null,{timeout:180000});
async function open(bytes){await page.goto('http://127.0.0.1:4175');await page.locator('#file-input').setInputFiles({name:'test.pdf',mimeType:'application/pdf',buffer:Buffer.from(bytes)});await idle();await page.waitForFunction(()=>window.preview.pageCount>0);}
async function menu(name,action){await page.locator('summary').filter({hasText:new RegExp('^'+name+'$')}).click();await page.locator(`[data-action="${action}"]`).filter({visible:true}).first().click();}
try{
  const form=await PDFDocument.create();const p=form.addPage([400,500]);const field=form.getForm().createTextField('Your name');field.addToPage(p,{x:40,y:400,width:200,height:30});
  await open(await form.save());await menu('Tools','forms');await page.locator('[data-field="0"]').fill('Michelle');await page.locator('#dialog-ok').click();await idle();
  const changed=await PDFDocument.load(new Uint8Array(await page.evaluate(()=>Array.from(window.preview.bytes))));assert.equal(changed.getForm().getTextField('Your name').getText(),'Michelle');console.log('PASS fillable form persisted');
  await menu('Tools','signature');await page.locator('#signature-name').fill('Michelle Jiang');await page.locator('#dialog-ok').click();await idle();assert.equal(await page.locator('#object-kind').textContent(),'Image');assert.ok((await page.evaluate(()=>window.preview.objects)).some(o=>o.type===3));console.log('PASS typed signature becomes a movable PDF image');
  await menu('Tools','signature');const pad=await page.locator('#signature-pad').boundingBox();await page.mouse.move(pad.x+30,pad.y+60);await page.mouse.down();await page.mouse.move(pad.x+70,pad.y+30,{steps:4});await page.mouse.move(pad.x+120,pad.y+75,{steps:4});await page.mouse.up();await page.locator('#dialog-ok').click();await idle();assert.equal((await page.evaluate(()=>window.preview.objects)).filter(o=>o.type===3).length,2);console.log('PASS drawn signature becomes a movable PDF image');
  await page.goto('about:blank');const source=await PDFDocument.load(await readFile('public/demo.pdf')),sample=await PDFDocument.create();(await sample.copyPages(source,[1])).forEach(p=>sample.addPage(p));
  await open(await sample.save());await menu('Tools','ocr');await idle();const text=await page.locator('#text-layer').textContent();assert.match(text,/INVOICE|TOTAL/i);assert.deepEqual(errors,[]);console.log('PASS real scanned-page OCR adds selectable text');
  await page.goto('about:blank');const secret=await PDFDocument.create();secret.addPage([400,500]).drawText('SECRET CODE',{x:40,y:400,size:20});await open(await secret.save());
  await menu('Tools','searchredact');await page.locator('#entry').fill('SECRET');await page.locator('#dialog-ok').click();await page.locator('[data-hit="0"]').check();await page.locator('#dialog-ok').click();await page.locator('#dialog-title').filter({hasText:'Permanently redact'}).waitFor();await page.locator('#dialog-ok').click();await idle();assert.equal((await page.locator('#text-layer').textContent()).trim(),'');
  const redacted=await PDFDocument.load(new Uint8Array(await page.evaluate(()=>Array.from(window.preview.bytes))));assert.equal(redacted.getPageCount(),1);console.log('PASS reviewed redaction rebuilds page without original text');
}finally{await browser.close();server.closeAllConnections();server.close();}
