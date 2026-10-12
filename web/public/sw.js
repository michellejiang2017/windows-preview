const CACHE='preview-v4.1.0';
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(['./','./index.html','./style.css','./layout-fixes.css','./icon.svg','./manifest.webmanifest','./assets/app.js','./assets/pdf.worker.min.mjs','./assets/pdfium.wasm','./demo.pdf'])).then(()=>self.skipWaiting()));});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('preview-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',e=>{if(e.request.method!=='GET'||new URL(e.request.url).origin!==self.location.origin)return;e.respondWith(caches.match(e.request).then(hit=>hit||fetch(e.request)));});
