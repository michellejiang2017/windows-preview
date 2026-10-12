"""PDF-only operations. Work on a private copy before committing to the editor."""
import difflib,re
from io import BytesIO
import fitz
import numpy as np
from PIL import Image,ImageOps,ImageEnhance
from engine import png_bytes,image_bytes

def open_copy(data):return fitz.open(stream=data,filetype='pdf')
def encoded(doc):return doc.tobytes(garbage=4,deflate=True)

def ocr_pdf(data,indices,recognizer=None):
    if recognizer is None:
        from rapidocr_onnxruntime import RapidOCR
        recognizer=RapidOCR()
    added=0; skipped=0
    with open_copy(data) as doc:
        for index in indices:
            page=doc[index]
            if page.get_text().strip():skipped+=1;continue
            rotation=page.rotation; page.set_rotation(0)
            pix=page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False)
            records,_=recognizer(np.array(Image.frombytes('RGB',(pix.width,pix.height),pix.samples)))
            for box,text,confidence in records or []:
                if not text or confidence<.5:continue
                points=np.asarray(box)/2; r=fitz.Rect(*points.min(axis=0),*points.max(axis=0))
                # Invisible Unicode text: the scan's appearance is preserved.
                size=max(4,min(r.height*.75,30)); font='china-s' if any(ord(c)>255 for c in text) else 'helv'
                width=fitz.get_text_length(text,fontname=font,fontsize=size)
                if width>r.width:size*=r.width/width
                page.insert_text((r.x0,r.y1-r.height*.15),text,fontname=font,fontsize=size,render_mode=3)
                added+=1
            page.set_rotation(rotation)
        return encoded(doc),{'recognized_lines':added,'skipped_text_pages':skipped}

def search_matches(doc,phrase):
    return [{'page':p.number,'rect':tuple(r),'text':phrase} for p in doc for r in p.search_for(phrase)]

def redact_matches(data,matches):
    with open_copy(data) as doc:
        grouped={}
        for match in matches:grouped.setdefault(match['page'],[]).append(match['rect'])
        for pn,rects in grouped.items():
            p=doc[pn]
            for r in rects:p.add_redact_annot(r,fill=(0,0,0))
            p.apply_redactions(images=2,graphics=1,text=0)
        return encoded(doc)

def objects(page):
    result=[];hidden_text={''.join(chr(c[0]) for c in span['chars']) for span in page.get_texttrace() if span['type']==3}
    for block in page.get_text('dict')['blocks']:
        if block['type']!=0:continue
        for line in block['lines']:
            for span in line['spans']:
                if span['text'].strip():result.append({'kind':'text','rect':tuple(span['bbox']),'text':span['text'],'size':span['size'],'color':span['color'],'direction':line['dir'],'hidden':span['text'] in hidden_text})
    for info in page.get_image_info(xrefs=True):
        if info.get('xref'):result.append({'kind':'image','rect':tuple(info['bbox']),'xref':info['xref'],'text':f'Image {info["xref"]} ({info["width"]} × {info["height"]})'})
    return result

def image_draw_spans(stream,name):
    """Locate an image operator without matching comments or PDF string literals."""
    tokens=[]; i=0; whitespace=b'\x00\t\n\x0c\r '; delimiters=whitespace+b'()<>[]{}/%'
    while i<len(stream):
        c=stream[i]
        if c in whitespace:i+=1;continue
        if c==37:
            while i<len(stream) and stream[i] not in b'\r\n':i+=1
            continue
        if c==40:
            depth=1;i+=1
            while i<len(stream) and depth:
                if stream[i]==92:i+=2;continue
                if stream[i]==40:depth+=1
                elif stream[i]==41:depth-=1
                i+=1
            tokens.append((b'STRING',i,i));continue
        if c==60 and stream[i:i+2]!=b'<<':
            end=stream.find(b'>',i+1);i=len(stream) if end<0 else end+1;tokens.append((b'STRING',i,i));continue
        start=i;i+=1
        if c==47:
            while i<len(stream) and stream[i] not in delimiters:i+=1
        elif c not in b'<>[]{}':
            while i<len(stream) and stream[i] not in delimiters:i+=1
        tokens.append((stream[start:i],start,i))
    return [(tokens[j-1][1],end) for j,(token,start,end) in enumerate(tokens) if j and token==b'Do' and tokens[j-1][0]==b'/'+name.encode()]

def edit_object(data,index,obj,rect=None,text=None,replacement=None,delete=False):
    with open_copy(data) as doc:
        page=doc[index]; old=fitz.Rect(obj['rect']); target=fitz.Rect(rect or obj['rect'])
        if not delete and (target.is_empty or not (page.rect*page.derotation_matrix).contains(target)):raise ValueError('Place the object within the current page bounds.')
        if obj['kind']=='image':
            names=[i[7] for i in page.get_images(full=True) if i[0]==obj['xref'] and i[-1]==0]
            if len(set(names))!=1:raise ValueError('This image is inside a complex PDF drawing. Direct image placement is supported; this object cannot be edited safely.')
            if any(not info.get('xref') for info in page.get_image_info(xrefs=True)):raise ValueError('This page contains inline image data. Image editing is refused to preserve its content.')
            stream=b'\n'.join(doc.xref_stream(x) for x in page.get_contents()); spans=image_draw_spans(stream,names[0])
            if len(spans)!=1:raise ValueError('This image resource is placed multiple times. Editing it independently is not supported.')
            if replacement: payload=png_bytes(Image.open(replacement).convert('RGBA'))
            else:
                source=fitz.Pixmap(doc,obj['xref']); smask=next(i[1] for i in page.get_images(full=True) if i[0]==obj['xref'])
                if smask:source=fitz.Pixmap(source,fitz.Pixmap(doc,smask))
                payload=source.tobytes('png')
            # New page-local content stream avoids changing shared image resources or other pages.
            start,end=spans[0]; xref=doc.get_new_xref(); doc.update_object(xref,'<<>>'); doc.update_stream(xref,stream[:start]+stream[end:]); page.set_contents(xref)
            if not delete:page.insert_image(target,stream=payload,keep_proportion=False)
        else:
            if tuple(obj.get('direction',(1,0)))!=(1,0):raise ValueError('Rotated text spans are not yet editable. Use text overlay or a replacement page.')
            for other in objects(page):
                if other['kind']=='text' and other['rect']!=obj['rect'] and not (fitz.Rect(other['rect'])&old).is_empty:raise ValueError('This span overlaps other text; editing it could remove neighboring content. Choose a different span.')
            size=obj['size']; value=obj['text'] if text is None else text
            if not delete:
                size=min(size,target.height/1.4)
                if fitz.get_text_length(value,fontsize=size)>target.width+.5:raise ValueError('Text does not fit this width. Increase the width or shorten the replacement.')
            page.add_redact_annot(old,fill=False); page.apply_redactions(images=0,graphics=0,text=0)
            if not delete:
                color=tuple(((obj['color']>>shift)&255)/255 for shift in (16,8,0))
                page.insert_text((target.x0,target.y0+size),value,fontsize=size,color=color)
        return encoded(doc)

def blank_candidates(doc,indices,threshold=.001):
    candidates=[]
    for i in indices:
        p=doc[i]
        if p.get_text().strip() or list(p.annots() or []) or list(p.widgets() or []) or p.get_links():continue
        pix=p.get_pixmap(matrix=fitz.Matrix(.5,.5),colorspace=fitz.csGRAY,alpha=False); pixels=np.frombuffer(pix.samples,dtype=np.uint8)
        if np.mean(pixels<245)<=threshold:candidates.append(i)
    return candidates

def deskew_angle(image):
    # Projection profile: angle yielding the strongest horizontal text rows.
    small=ImageOps.grayscale(image); small.thumbnail((1000,1000)); mask=np.asarray(small)<180
    if mask.sum()<20:return 0
    binary=Image.fromarray(np.where(mask,0,255).astype('uint8')); best=(0,0)
    for angle in np.arange(-5,5.01,.25):
        rotated=np.asarray(binary.rotate(float(angle),fillcolor=255))<180; score=float(np.var(rotated.sum(axis=1)))
        if score>best[0]:best=(score,float(angle))
    return best[1]

def clean_scans(data,indices,deskew=True,contrast=1.3,grayscale=True,dpi=150):
    with open_copy(data) as doc:
        for index in indices:
            old=doc[index]
            if list(old.widgets() or []) or list(old.annots() or []) or old.get_links():raise ValueError(f'Page {index+1} contains forms, annotations or links. Cleanup would flatten them; remove them or choose other pages.')
            rotation=old.rotation; old.set_rotation(0); size=old.rect; pix=old.get_pixmap(matrix=fitz.Matrix(dpi/72,dpi/72),alpha=False); im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
            if grayscale:im=ImageOps.grayscale(im)
            if deskew:im=im.rotate(deskew_angle(im),resample=Image.Resampling.BICUBIC,fillcolor='white')
            im=ImageEnhance.Contrast(im).enhance(contrast)
            xref=doc.get_new_xref(); doc.update_object(xref,'<<>>'); doc.update_stream(xref,b''); old.set_contents(xref); old.insert_image(size,stream=png_bytes(im)); old.clean_contents(); old.set_rotation(rotation)
        return encoded(doc)

def compress_pdf(data,target_bytes):
    # Lossless first. Rasterized candidates only if needed; never exceed the source size.
    with open_copy(data) as src:
        lossless=min(data,encoded(src),key=len)
        if len(lossless)<=target_bytes:return lossless,{'rasterized':False,'target_met':True}
        if any(list(p.widgets() or []) or list(p.annots() or []) or p.get_links() for p in src):return lossless,{'rasterized':False,'target_met':False,'reason':'Forms, annotations or links require lossless preservation.'}
        best=min(data,lossless,key=len); rasterized=False
        for dpi,quality in [(150,80),(110,65),(85,50),(60,35)]:
            with fitz.open() as out:
                for page in src:
                    pix=page.get_pixmap(matrix=fitz.Matrix(dpi/72,dpi/72),alpha=False); im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples); p=out.new_page(width=page.rect.width,height=page.rect.height); p.insert_image(p.rect,stream=image_bytes(im,'.jpg',quality))
                    # Carry searchable text in an invisible layer (simple span placement).
                    for obj in objects(page):
                        if obj['kind']=='text':
                            r=fitz.Rect(obj['rect'])*page.rotation_matrix; p.insert_text((r.x0,r.y0+min(obj['size'],r.height)),obj['text'],fontsize=min(obj['size'],r.height),render_mode=3)
                out.set_metadata(src.metadata); out.set_toc(src.get_toc()); out.set_page_labels(src.get_page_labels()); candidate=encoded(out)
                if len(candidate)<len(best):best=candidate;rasterized=True
                if len(best)<=target_bytes:break
        return best,{'rasterized':rasterized,'target_met':len(best)<=target_bytes}

def compare_pdfs(left,right):
    results=[]
    with open_copy(left) as a,open_copy(right) as b:
        for i in range(max(len(a),len(b))):
            if i>=len(a):results.append({'page':i+1,'status':'Added page','diff':''});continue
            if i>=len(b):results.append({'page':i+1,'status':'Removed page','diff':''});continue
            old=a[i].get_text(); new=b[i].get_text(); image_a=a[i].get_pixmap(matrix=fitz.Matrix(.75,.75)); image_b=b[i].get_pixmap(matrix=fitz.Matrix(.75,.75))
            text_changed=old!=new; visual_changed=image_a.width!=image_b.width or image_a.height!=image_b.height or image_a.samples!=image_b.samples
            if text_changed or visual_changed:results.append({'page':i+1,'status':('Text and appearance changed' if text_changed else 'Appearance changed'),'diff':'\n'.join(difflib.unified_diff(old.splitlines(),new.splitlines(),fromfile='Current',tofile='Other',lineterm=''))})
    return results

def set_bookmarks(data,toc):
    with open_copy(data) as doc:doc.set_toc(toc);return encoded(doc)

def decorate(data,indices,header='',footer='',numbering=True,start=1,label_prefix=''):
    with open_copy(data) as doc:
        for n,i in enumerate(indices):
            p=doc[i]; area=p.rect*p.derotation_matrix
            if header:p.insert_text((24,18),header,fontsize=10)
            bottom=' • '.join(v for v in [footer,str(start+n) if numbering else ''] if v)
            if bottom:p.insert_text((24,area.height-14),bottom,fontsize=10)
        return encoded(doc)
