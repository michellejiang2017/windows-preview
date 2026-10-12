export function setupSignature(container){
  container.innerHTML='<p>Draw your signature below, or type your name. It will be added as a movable image.</p><canvas id="signature-pad" width="900" height="300" aria-label="Draw signature" style="width:100%;height:150px;background:white;border:1px solid #d1d1d5;border-radius:6px;touch-action:none"></canvas><button type="button" id="signature-clear">Clear</button><label>Or type your name<input id="signature-name" autocomplete="off" maxlength="100" placeholder="Your name"></label><small>This adds a visible signature, not a certificate-based digital signature.</small>';
  const canvas=container.querySelector('#signature-pad'),ctx=canvas.getContext('2d');ctx.strokeStyle='#17212d';ctx.lineWidth=3.5;ctx.lineJoin='round';ctx.lineCap='round';let last=null;
  const point=e=>{const r=canvas.getBoundingClientRect();return {x:(e.clientX-r.left)*canvas.width/r.width,y:(e.clientY-r.top)*canvas.height/r.height};};
  canvas.onpointerdown=e=>{e.preventDefault();last=point(e);canvas.setPointerCapture(e.pointerId);};
  canvas.onpointermove=e=>{if(!last)return;e.preventDefault();const p=point(e);ctx.beginPath();ctx.moveTo(last.x,last.y);ctx.lineTo(p.x,p.y);ctx.stroke();last=p;};
  canvas.onpointerup=canvas.onpointercancel=()=>last=null;
  container.querySelector('#signature-clear').onclick=()=>{ctx.clearRect(0,0,canvas.width,canvas.height);container.querySelector('#signature-name').value='';};
  container.querySelector('#signature-name').oninput=e=>{ctx.clearRect(0,0,canvas.width,canvas.height);ctx.font='italic 72px Georgia, serif';ctx.fillStyle='#17212d';ctx.fillText(e.target.value,30,185,840);};
  return async()=>{
    const pixels=ctx.getImageData(0,0,canvas.width,canvas.height).data;let x0=canvas.width,y0=canvas.height,x1=0,y1=0;
    for(let y=0;y<canvas.height;y++)for(let x=0;x<canvas.width;x++)if(pixels[(y*canvas.width+x)*4+3]){x0=Math.min(x0,x);y0=Math.min(y0,y);x1=Math.max(x1,x);y1=Math.max(y1,y);}
    if(x0>x1)throw Error('Draw a signature or type your name first.');
    const crop=document.createElement('canvas');crop.width=x1-x0+21;crop.height=y1-y0+21;crop.getContext('2d').drawImage(canvas,x0,y0,x1-x0+1,y1-y0+1,10,10,x1-x0+1,y1-y0+1);
    const blob=await new Promise(resolve=>crop.toBlob(resolve,'image/png'));return new File([blob],'signature.png',{type:'image/png'});
  };
}
