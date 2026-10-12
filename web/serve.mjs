import http from 'node:http';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
const root=path.resolve('dist');
const types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.wasm':'application/wasm','.svg':'image/svg+xml','.json':'application/json','.webmanifest':'application/manifest+json','.pdf':'application/pdf'};
export const server=http.createServer(async(req,res)=>{try{let file=decodeURIComponent(new URL(req.url,'http://localhost').pathname);if(file==='/')file='/index.html';const resolved=path.resolve(root,'.'+file);if(!resolved.startsWith(root+path.sep))throw Error();res.setHeader('Content-Type',types[path.extname(resolved)]||'application/octet-stream');res.end(await readFile(resolved));}catch{res.writeHead(404);res.end('Not found');}}).listen(Number(process.env.PORT)||4173,'127.0.0.1',()=>console.log('Local: http://127.0.0.1:'+(process.env.PORT||4173)));
