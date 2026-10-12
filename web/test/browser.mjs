import {createRequire} from 'node:module';
import {mkdir,readFile} from 'node:fs/promises';
import {PDFDocument} from 'pdf-lib';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
let ownedServer;
if(!process.env.PREVIEW_URL){process.env.PORT='4174';ownedServer=(await import('../serve.mjs')).server;}
const {chromium}=require(process.env.PREVIEW_PLAYWRIGHT||'playwright');
const browser=await chromium.launch({channel:'chrome',headless:true});
const errors=[];const page=await browser.newPage({viewport:{width:1280,height:850},serviceWorkers:'block'});
await page.addInitScript(()=>window.showSaveFilePicker=undefined);
page.on('pageerror',error=>errors.push(error.message));
const idle=()=>page.waitForFunction(()=>window.preview&&!window.preview.isBusy);
const count=n=>page.waitForFunction(n=>window.preview.pageCount===n,n);
async function click(action){await page.locator(`[data-action="${action}"]`).filter({visible:true}).first().click();await page.waitForFunction(()=>!window.preview.isBusy||document.querySelector('#dialog').open);}
async function menu(name,action){await page.locator('summary').filter({hasText:new RegExp('^'+name+'$')}).click();await click(action);}
await mkdir('work',{recursive:true});
try{
  await page.goto(process.env.PREVIEW_URL||'http://127.0.0.1:4174');await click('demo');await count(4);console.log('PASS open/render example');
  await click('blank');await count(5);await page.keyboard.press('Control+z');await idle();await count(4);console.log('PASS blank page and undo');
  await page.locator('[data-page="3"]').click();await idle();await click('markup');await page.waitForFunction(()=>window.preview.objectCount>0);
  const bounds=await page.locator('#page-wrap').boundingBox(),scale=bounds.width/612;await page.screenshot({path:'work/before-selection.png'});await page.mouse.click(bounds.x+132*scale,bounds.y+310*scale);
  await page.locator('#inspector').waitFor({state:'visible'});assert.equal(await page.locator('#object-kind').textContent(),'Image');
  const oldX=Number(await page.locator('#obj-x').inputValue());await page.mouse.move(bounds.x+132*scale,bounds.y+310*scale);await page.mouse.down();await page.mouse.move(bounds.x+132*scale+30,bounds.y+310*scale+20,{steps:5});await page.mouse.up();await idle();assert.ok(Number(await page.locator('#obj-x').inputValue())>oldX+10);console.log('PASS select and drag existing PDF image');
  const corner=await page.locator('.resize-handle').boundingBox();const oldWidth=Number(await page.locator('#obj-w').inputValue());await page.mouse.move(corner.x+5,corner.y+5);await page.mouse.down();await page.mouse.move(corner.x+35,corner.y+25,{steps:5});await page.mouse.up();await idle();console.log('Resize result',oldWidth,await page.locator('#obj-w').inputValue(),await page.locator('#status').textContent());await page.screenshot({path:'work/resize-debug.png'});assert.ok(Number(await page.locator('#obj-w').inputValue())>oldWidth);console.log('PASS resize existing PDF image');
  await page.screenshot({path:'work/web-editing.png'});
  await menu('Pages','number');await page.locator('#entry').fill('PAGE {n}');await page.locator('#dialog-ok').click();await idle();
  await menu('Pages','labels');await page.locator('#entry').fill('P-');await page.locator('#dialog-ok').click();await idle();
  await menu('Pages','bookmark');await page.locator('#entry').fill('Objects');await page.locator('#dialog-ok').click();await idle();console.log('PASS page numbers, labels and bookmark dialogs');
  const downloadPromise=page.waitForEvent('download');await click('save');const download=await downloadPromise;await download.saveAs('work/saved.pdf');assert.equal((await PDFDocument.load(await readFile('work/saved.pdf'))).getPageCount(),4);console.log('PASS saving edited PDF');
  await page.locator('button[data-mode="textselect"]').click();await idle();const text=page.locator('#text-layer span').filter({hasText:'Object editing'}).first();const r=await text.boundingBox();await page.mouse.move(r.x+2,r.y+r.height/2);await page.mouse.down();await page.mouse.move(r.x+r.width-2,r.y+r.height/2,{steps:5});await page.mouse.up();const selection=await page.evaluate(()=>window.getSelection().toString());console.log('Selected text:',selection);assert.ok(selection.includes('editing'));console.log('PASS native browser text selection');
  await page.setViewportSize({width:390,height:844});await click('fit');await page.screenshot({path:'work/web-mobile.png'});assert.ok(await page.locator('#page-wrap').isVisible());console.log('PASS mobile document layout');
  assert.deepEqual(errors,[]);console.log('Browser checks passed without page errors');
}finally{await browser.close();ownedServer?.close();}
