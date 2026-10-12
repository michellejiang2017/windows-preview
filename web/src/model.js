import {PDFDocument,StandardFonts,rgb,degrees} from 'pdf-lib';
export {PDFDocument,StandardFonts,rgb,degrees};
export class Workspace {
  constructor(){this.bytes=null;this.name='Untitled.pdf';this.history=[];this.future=[];this.dirty=false;this.fileHandle=null;}
  async load(bytes,name='Untitled.pdf'){
    const pdf=await PDFDocument.load(bytes);if(!pdf.getPageCount())throw Error('This PDF has no pages.');
    this.bytes=new Uint8Array(bytes);this.name=name;this.history=[];this.future=[];this.dirty=false;this.fileHandle=null;
  }
  async create(){const pdf=await PDFDocument.create();pdf.addPage();await this.load(await pdf.save());this.dirty=true;}
  commit(bytes){this.history.push(this.bytes.slice());this.history=this.history.slice(-20);this.future=[];this.bytes=new Uint8Array(bytes);this.dirty=true;}
  async edit(fn){if(!this.bytes)throw Error('Open a PDF first.');const pdf=await PDFDocument.load(this.bytes);await fn(pdf);this.commit(await pdf.save());}
  undo(){if(this.history.length){this.future.push(this.bytes);this.bytes=this.history.pop();this.dirty=true;}}
  redo(){if(this.future.length){this.history.push(this.bytes);this.bytes=this.future.pop();this.dirty=true;}}
  async blank(after){await this.edit(pdf=>{const size=pdf.getPage(after).getSize();pdf.insertPage(after+1,[size.width,size.height]);});}
  async insert(bytes,at){const source=await PDFDocument.load(bytes);await this.edit(async pdf=>{const pages=await pdf.copyPages(source,source.getPageIndices());pages.forEach((page,n)=>pdf.insertPage(at+n,page));});}
  async reorder(order){await this.edit(pdf=>{if(order.length!==pdf.getPageCount()||new Set(order).size!==order.length||order.some(i=>!Number.isInteger(i)||i<0||i>=order.length))throw Error('Invalid page order.');const pages=pdf.getPages();for(let i=pages.length-1;i>=0;i--)pdf.removePage(i);order.forEach(i=>pdf.addPage(pages[i]));});}
  async duplicate(indices){await this.edit(async pdf=>{for(const i of [...indices].sort((a,b)=>b-a)){const [page]=await pdf.copyPages(pdf,[i]);pdf.insertPage(i+1,page);}});}
  async remove(indices){await this.edit(pdf=>{if(indices.length>=pdf.getPageCount())throw Error('Keep at least one page.');[...indices].sort((a,b)=>b-a).forEach(i=>pdf.removePage(i));});}
  async rotate(indices){await this.edit(pdf=>indices.forEach(i=>{const p=pdf.getPage(i);p.setRotation(degrees((p.getRotation().angle+90)%360));}));}
  async extract(indices){const source=await PDFDocument.load(this.bytes);const target=await PDFDocument.create();(await target.copyPages(source,[...indices].sort((a,b)=>a-b))).forEach(p=>target.addPage(p));return target.save();}
  async image(bytes,index,rect){await this.edit(async pdf=>{const image=await pdf.embedPng(bytes);pdf.getPage(index).drawImage(image,rect);});}
  async text(index,text,rect,color='#202020',size=16){await this.edit(async pdf=>{const font=await pdf.embedFont(StandardFonts.Helvetica);pdf.getPage(index).drawText(text,{x:rect.x,y:rect.y,size,font,color:hexColor(color),maxWidth:rect.width});});}
}
export function hexColor(hex){return rgb(...[1,3,5].map(n=>parseInt(hex.slice(n,n+2),16)/255));}
export async function imagePdf(png,width,height){const pdf=await PDFDocument.create();const image=await pdf.embedPng(png);const page=pdf.addPage([width,height]);page.drawImage(image,{x:0,y:0,width,height});return pdf.save();}
