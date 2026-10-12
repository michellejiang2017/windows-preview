import {createRequire} from 'node:module';
import {mkdir,writeFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const {chromium}=createRequire(import.meta.url)(process.env.PREVIEW_PLAYWRIGHT||'playwright');
process.env.PORT='4178';const {server}=await import('../serve.mjs');
const browser=await chromium.launch({channel:process.env.PREVIEW_BROWSER||'chrome',headless:true});
const page=await browser.newPage({serviceWorkers:'block',viewport:{width:785,height:704},deviceScaleFactor:2});
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const idle=()=>page.waitForFunction(()=>window.preview&&!window.preview.isBusy);
async function layout(){const dimensions=await page.evaluate(()=>({height:innerHeight,body:document.body.getBoundingClientRect().bottom,footer:document.querySelector('body>footer').getBoundingClientRect().bottom,viewer:document.querySelector('#viewer').getBoundingClientRect().height,rows:getComputedStyle(document.body).gridTemplateRows,items:[...document.body.children].filter(e=>getComputedStyle(e).display!=='none').map(e=>({tag:e.tagName,id:e.id,position:getComputedStyle(e).position,row:getComputedStyle(e).gridRow,bottom:e.getBoundingClientRect().bottom}))}));if(Math.abs(dimensions.height-dimensions.footer)>=2)console.log('Layout failure',dimensions);assert.ok(Math.abs(dimensions.height-dimensions.body)<2,'Body must cover the viewport');assert.ok(Math.abs(dimensions.height-dimensions.footer)<2,'Footer must stay at the bottom');assert.ok(dimensions.viewer>dimensions.height*.5,'Document area must not collapse');}
async function colors(){return page.evaluate(()=>{const c=document.querySelector('#page-canvas'),ctx=c.getContext('2d'),data=ctx.getImageData(0,0,c.width,c.height).data;let black=0,white=0;for(let i=0;i<data.length;i+=4){if(data[i]<10&&data[i+1]<10&&data[i+2]<10)black++;if(data[i]>245&&data[i+1]>245&&data[i+2]>245)white++;}const sample=(x,y)=>Array.from(ctx.getImageData(Math.floor(c.width*x/612),Math.floor(c.height*y/792),1,1).data);return {black:black/(data.length/4),white:white/(data.length/4),paper:sample(400,500),image:sample(100,300),secret:sample(100,135)};});}
await mkdir('work',{recursive:true});
try{
  await page.goto('http://127.0.0.1:4178');await layout();await page.locator('[data-action="demo"]').click();await layout();await idle();await layout();await page.locator('[data-page="3"]').click();await layout();await idle();await layout();
  await page.locator('[data-action="markup"]').click();await idle();await layout();await page.locator('button[data-mode="redact"]').click();await idle();await layout();
  const before=await colors(),b=await page.locator('#page-wrap').boundingBox(),s=b.width/612;
  await page.mouse.move(b.x+40*s,b.y+120*s);await page.mouse.down();await page.mouse.move(b.x+305*s,b.y+155*s,{steps:8});await page.mouse.up();await page.locator('#dialog-ok').click();await idle();
  await layout();const after=await colors();console.log('Before',before,'After',after);await page.screenshot({path:'work/redaction-demo.png'});await writeFile('work/redaction-demo.pdf',Buffer.from(await page.evaluate(()=>Array.from(window.preview.bytes))));
  assert.ok(after.white>.85,'Redaction must preserve white paper outside the selected area');assert.deepEqual(after.paper,before.paper,'Unselected paper must remain unchanged');assert.ok(after.image[2]>150&&after.image[0]<100,'The blue image outside redaction must remain blue');assert.ok(after.secret.slice(0,3).every(x=>x<10),'Selected secret must be black');assert.deepEqual(errors,[]);
  console.log('PASS drawn demo redaction preserves unselected page content');
  for(const name of ['select','textselect','pen','rectangle','highlight','redact','crop']){await page.locator(`button[data-mode="${name}"]`).click();await idle();await layout();}
  for(const action of ['zoomout','fit','next','prev','rotate']){await page.locator(`[data-action="${action}"]`).filter({visible:true}).first().click();await idle();await layout();}
  await page.setViewportSize({width:390,height:844});await page.locator('[data-action="fit"]').click();await idle();await layout();
  console.log('PASS viewport remains filled across editing tools, page actions and mobile resize');
}finally{await browser.close();server.closeAllConnections();server.close();}
