"""Same-origin demo API; bounded, cookie-isolated, ephemeral uploads."""
import os,secrets,time,threading,logging
from pathlib import Path
from fastapi import FastAPI,Request,Response,UploadFile,File,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field
from .ingestion import MAX_BYTES
from .service import RagService

app=FastAPI(title='Passage: document answers',docs_url='/docs')
service=None
init_error=False
sessions={}
session_lock=threading.Lock()
SESSION_TTL=3600

def initialize():
    global service,init_error
    try:
        svc=RagService(os.environ.get('RAG_DATA_DIR'))
        for collection in svc.db.list_collections():
            if collection.name.startswith('user_'):svc.db.delete_collection(collection.name)
        service=svc
    except Exception:
        init_error=True
        logging.exception('Document index initialization failed')

@app.on_event('startup')
def startup():threading.Thread(target=initialize,daemon=True).start()

def ready():
    if service is None:raise HTTPException(503,'Document index unavailable.' if init_error else 'Models are warming up. Please try again shortly.')
    return service

def session(request,response):
    now=time.monotonic()
    with session_lock:
        # Remove expired collections too: abandoned uploads cannot fill the free disk.
        for key in list(sessions):
            if now-sessions[key]['last']>SESSION_TTL:
                if service and service.lock.acquire(blocking=False):
                    name='user_'+__import__('hashlib').sha256(key.encode()).hexdigest()[:32]
                    try:service.db.delete_collection(name)
                    except Exception:pass
                    finally:service.lock.release()
                elif service:continue
                del sessions[key]
        key=request.cookies.get('rag_session')
        if key not in sessions:
            if len(sessions)>=20:raise HTTPException(503,'Demo session capacity reached. Please try later.')
            key=secrets.token_urlsafe(32);sessions[key]={'last':now,'calls':[]}
            response.set_cookie('rag_session',key,httponly=True,samesite='strict',secure=request.url.scheme=='https',max_age=SESSION_TTL)
        item=sessions[key];item['last']=now
        item['calls']=[t for t in item['calls'] if now-t<60]
        if len(item['calls'])>=20:raise HTTPException(429,'Please wait a minute before making more requests.')
        item['calls'].append(now)
    return key

def perform(fn):
    svc=ready()
    if not svc.lock.acquire(blocking=False):raise HTTPException(429,'Another document is being processed. Please retry shortly.')
    try:return fn(svc)
    except ValueError as error:raise HTTPException(400,str(error)) from error
    except HTTPException:raise
    except Exception:
        logging.exception('Document operation failed')
        raise HTTPException(500,'Document operation failed. Please retry with a smaller valid file.')
    finally:svc.lock.release()

@app.get('/')
def home():return FileResponse(Path(__file__).parents[1]/'static'/'index.html')

@app.get('/health')
def health():return {'status':'ok','ready':service is not None}

@app.get('/ready')
def readiness():ready();return {'status':'ready'}

@app.get('/api/documents')
def documents(request:Request,response:Response):
    ready();key=session(request,response)
    return perform(lambda svc:svc.documents(key))

@app.post('/api/ingest')
def upload(request:Request,response:Response,file:UploadFile=File(...)):
    ready();key=session(request,response);data=file.file.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES:raise HTTPException(413,'Files must be 5 MB or smaller.')
    return perform(lambda svc:svc.add(svc.user_collection(key),data,file.filename or 'upload'))

class Question(BaseModel):
    question:str=Field(min_length=3,max_length=500)
    filename:str|None=Field(default=None,max_length=150)

@app.post('/api/ask')
def ask(body:Question,request:Request,response:Response):
    ready();key=session(request,response)
    if len(body.question.strip())<3:raise HTTPException(400,'Enter a question with at least three characters.')
    return perform(lambda svc:svc.query(body.question.strip(),key,body.filename))

@app.delete('/api/uploads')
def clear(request:Request,response:Response):
    ready();key=session(request,response)
    def delete(svc):
        collection=svc.user_collection(key);svc.db.delete_collection(collection.name)
        return {'cleared':True}
    return perform(delete)
