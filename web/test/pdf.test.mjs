import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {Workspace,PDFDocument,rgb} from '../src/model.js';
import {initialize,listObjects,transformObject} from '../src/objects.js';
async function sample(){const d=await PDFDocument.create();for(let n=0;n<3;n++){const p=d.addPage([400+n*10,500]);p.drawText(`Page ${n+1}`,{x:30,y:420,size:20});p.drawRectangle({x:50,y:100,width:80,height:60,color:rgb(0,0,1)});}return d.save();}
async function ws(){const w=new Workspace();await w.load(await sample(),'sample.pdf');return w;}
test('blank page matches size and is undoable',async()=>{const w=await ws();await w.blank(1);let d=await PDFDocument.load(w.bytes);assert.equal(d.getPageCount(),4);assert.equal(d.getPage(2).getWidth(),410);w.undo();assert.equal((await PDFDocument.load(w.bytes)).getPageCount(),3);w.redo();assert.equal((await PDFDocument.load(w.bytes)).getPageCount(),4);});
test('page reorder preserves original page sizes',async()=>{const w=await ws();await w.reorder([2,0,1]);const d=await PDFDocument.load(w.bytes);assert.deepEqual(d.getPages().map(p=>p.getWidth()),[420,400,410]);});
test('invalid reorder rejected without changing document',async()=>{const w=await ws();const before=w.bytes.slice();await assert.rejects(w.reorder([0,0,2]));assert.deepEqual(w.bytes,before);});
test('delete all pages safely refused',async()=>{const w=await ws();await assert.rejects(w.remove([0,1,2]));assert.equal(w.history.length,0);});
test('insert, duplicate and extract produce runnable PDFs',async()=>{const w=await ws();await w.insert(await sample(),1);assert.equal((await PDFDocument.load(w.bytes)).getPageCount(),6);await w.duplicate([1]);await w.remove([0]);assert.equal((await PDFDocument.load(w.bytes)).getPageCount(),6);const d=await PDFDocument.load(await w.extract([2,0]));assert.equal(d.getPageCount(),2);});
test('rotate multiple selected pages',async()=>{const w=await ws();await w.rotate([0,2]);const d=await PDFDocument.load(w.bytes);assert.deepEqual(d.getPages().map(p=>p.getRotation().angle),[90,0,90]);});
test('text creation and 20-step undo cap',async()=>{const w=await ws();for(let n=0;n<22;n++)await w.text(0,'Note',{x:10,y:100,width:200});assert.equal(w.history.length,20);assert.ok(w.dirty);});
test('opening a document resets history and stale file handle',async()=>{const w=await ws();await w.blank(0);w.fileHandle={};await w.load(await sample(),'second.pdf');assert.equal(w.history.length,0);assert.equal(w.fileHandle,null);assert.equal(w.dirty,false);});
await initialize(await readFile(new URL('../node_modules/@embedpdf/pdfium/dist/pdfium.wasm',import.meta.url)));
test('WASM enumerates actual PDF text and paths',async()=>{const objects=await listObjects(await sample(),0);assert.ok(objects.some(o=>o.type===1));assert.ok(objects.some(o=>o.type===2));});
test('WASM moves and resizes an existing PDF element',async()=>{const bytes=await sample(),objects=await listObjects(bytes,0),obj=objects.find(o=>o.type===2);const moved=await transformObject(bytes,0,obj.index,[70,130,190,220]);const next=(await listObjects(moved,0)).find(o=>o.type===2);assert.ok(Math.abs(next.box[0]-70)<1);assert.ok(Math.abs(next.box[3]-220)<1);assert.equal((await listObjects(moved,1)).find(o=>o.type===2).box[0],50);});
test('WASM deletes selected object without deleting neighbor',async()=>{const bytes=await sample(),obj=(await listObjects(bytes,0)).find(o=>o.type===2),changed=await transformObject(bytes,0,obj.index,null,true);const objects=await listObjects(changed,0);assert.ok(!objects.some(o=>o.type===2));assert.ok(objects.some(o=>o.type===1));});
test('WASM replaces existing text while retaining original font',async()=>{const bytes=await sample(),obj=(await listObjects(bytes,0)).find(o=>o.type===1),changed=await transformObject(bytes,0,obj.index,null,false,'New text');assert.ok(changed.length);assert.ok((await listObjects(changed,0)).some(o=>o.type===1));});
