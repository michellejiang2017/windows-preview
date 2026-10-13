// Optional UI check using the existing Preview web development dependencies.
import {createRequire} from 'node:module';
import {mkdir} from 'node:fs/promises';
import assert from 'node:assert/strict';
const require=createRequire(new URL('../../web/package.json',import.meta.url));
const {chromium}=require('playwright');
const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1280,height:850}});const errors=[];
page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(120000);
try{
  await page.goto(process.env.RAG_URL||'http://127.0.0.1:8000');
  await page.locator('#status').filter({hasText:'Ready.'}).waitFor();
  await page.getByRole('button',{name:'Python author',exact:true}).click();
  await page.getByRole('button',{name:'Find an answer',exact:true}).click();
  await page.locator('.answer').filter({hasText:'Tim Peters [1]'}).waitFor();
  assert.match(await page.locator('.source').first().textContent(),/Author: Tim Peters/);
  await page.locator('#file').setInputFiles(new URL('../samples/preview-demo.pdf',import.meta.url).pathname.replace(/^\/(\w:)/,'$1'));
  await page.locator('#status').filter({hasText:'Added'}).waitFor();
  await page.locator('#file').setInputFiles({name:'office.txt',mimeType:'text/plain',buffer:Buffer.from('The fictional office is located in Lima.')});
  await page.locator('#status').filter({hasText:'Added'}).waitFor();
  await page.locator('#question').fill('Where is the fictional office located?');
  await page.locator('#ask').click();await page.locator('.answer').filter({hasText:'Lima [1]'}).waitFor();
  await page.locator('#drop').evaluate(el=>{const transfer=new DataTransfer();transfer.items.add(new File(['name,value\nalpha,42\n'],'dragged.csv',{type:'text/csv'}));el.dispatchEvent(new DragEvent('drop',{bubbles:true,dataTransfer:transfer}));});
  await page.locator('#status').filter({hasText:'Added'}).waitFor();
  assert.equal(await page.locator('#filter').inputValue(),'dragged.csv');
  await page.locator('#file').setInputFiles({name:'broken.pdf',mimeType:'application/pdf',buffer:Buffer.from('invalid pdf')});
  await page.locator('#status[role=alert]').waitFor();
  await page.locator('#clear').click();await page.locator('#status').filter({hasText:'removed'}).waitFor();
  assert.equal(await page.locator('#docs').getByText('office.txt',{exact:true}).count(),0);
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
  await mkdir('work',{recursive:true});await page.screenshot({path:'work/rag-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);console.log('PASS source answer, citations, PDF/text upload, CSV drag-and-drop, invalid-file errors, clear, mobile layout; no browser errors.');
}finally{await browser.close();}
