"""Local document engine. Originals are never changed until explicitly saved."""
from pathlib import Path
from io import BytesIO
import os
import tempfile
import fitz
from PIL import Image, ImageOps, ImageEnhance, ImageFilter

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    pass

IMAGE_EXTS = {'.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff','.gif','.heic','.heif','.avif','.ico','.ppm','.pgm','.pbm','.psd','.tga','.eps','.jp2'}

def png_bytes(image):
    b = BytesIO(); image.save(b, format='PNG'); return b.getvalue()

def save_atomic(data, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as f: f.write(data)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)

def image_bytes(image, extension, quality=90, preserve_metadata=False):
    exif_bytes=image.info.get('exif')
    formats = {'.jpg':'JPEG','.jpeg':'JPEG','.png':'PNG','.webp':'WEBP','.bmp':'BMP','.tif':'TIFF','.tiff':'TIFF','.gif':'GIF','.ico':'ICO','.ppm':'PPM','.pbm':'PPM','.pgm':'PPM','.tga':'TGA','.jp2':'JPEG2000','.pdf':'PDF'}
    fmt = formats.get(extension.lower())
    if not fmt: raise ValueError('Choose a supported export format.')
    if fmt in ('JPEG','PDF'):
        bg = Image.new('RGB', image.size, 'white')
        if image.mode == 'RGBA': bg.paste(image, mask=image.getchannel('A'))
        else: bg.paste(image.convert('RGB'))
        image = bg
    elif extension.lower() == '.pbm': image = image.convert('1')
    elif extension.lower() == '.pgm': image = image.convert('L')
    kwargs = {'quality':quality}
    if preserve_metadata and exif_bytes: kwargs['exif'] = exif_bytes
    b=BytesIO(); image.save(b, format=fmt, **kwargs); return b.getvalue()

def remove_gps(image):
    result=image.copy(); result.info=dict(image.info)
    exif=image.getexif()
    if 34853 in exif: del exif[34853]
    result.info['exif']=exif.tobytes()
    return result

def instant_alpha(image, x, y, tolerance=35):
    import numpy as np
    pixels=np.array(image.convert('RGBA'))
    color=pixels[y,x,:3].astype(float)
    difference=np.linalg.norm(pixels[:,:,:3].astype(float)-color, axis=2)
    pixels[difference <= tolerance,3]=0
    return Image.fromarray(pixels)

def adjust(image, exposure=1, contrast=1, saturation=1, sharpness=1):
    alpha=image.getchannel('A') if image.mode=='RGBA' else None
    result=image.convert('RGB')
    for cls,value in [(ImageEnhance.Brightness,exposure),(ImageEnhance.Contrast,contrast),(ImageEnhance.Color,saturation),(ImageEnhance.Sharpness,sharpness)]: result=cls(result).enhance(value)
    if alpha is not None: result.putalpha(alpha)
    return result

class Document:
    def __init__(self):
        self.pdf=None; self.images=[]; self.path=None; self.undo_stack=[]; self.redo_stack=[]; self.dirty=False;self.source_password='';self.source_print=True;self.source_copy=True
    @property
    def count(self): return len(self.pdf) if self.pdf is not None else len(self.images)
    @property
    def is_pdf(self): return self.pdf is not None
    def snapshot(self):
        return (self.pdf.tobytes(garbage=0,deflate=True) if self.is_pdf else [im.copy() for im in self.images], self.is_pdf)
    def checkpoint(self):
        self.undo_stack.append(self.snapshot()); self.undo_stack=self.undo_stack[-20:]; self.redo_stack.clear(); self.dirty=True
    def restore(self,snapshot):
        data,pdf=snapshot
        if self.pdf is not None: self.pdf.close()
        self.pdf=fitz.open(stream=data,filetype='pdf') if pdf else None
        self.images=[] if pdf else [im.copy() for im in data]
        self.dirty=True
    def undo(self):
        if self.undo_stack: self.redo_stack.append(self.snapshot()); self.restore(self.undo_stack.pop())
    def redo(self):
        if self.redo_stack: self.undo_stack.append(self.snapshot()); self.restore(self.redo_stack.pop())
    def open(self,paths,password=''):
        candidate=Document()
        if len(paths)==1 and Path(paths[0]).suffix.lower()=='.pdf':
            candidate.pdf=fitz.open(stream=Path(paths[0]).read_bytes(),filetype='pdf')
            if candidate.pdf.needs_pass and not candidate.pdf.authenticate(password):
                candidate.pdf.close(); raise ValueError('Password required or incorrect.')
            if not len(candidate.pdf): raise ValueError('PDF contains no pages.')
        else:
            for path in paths:
                with Image.open(path) as im:
                    original_info=dict(im.info)
                    for i in range(getattr(im,'n_frames',1)):
                        im.seek(i); frame=ImageOps.exif_transpose(im).convert('RGBA'); frame.info=original_info.copy(); candidate.images.append(frame)
            if not candidate.images: raise ValueError('No supported images found.')
        if self.pdf is not None: self.pdf.close()
        self.pdf=candidate.pdf; self.images=candidate.images; self.path=Path(paths[0]) if len(paths)==1 else None
        self.source_password=password;self.source_print=bool(self.pdf.permissions&fitz.PDF_PERM_PRINT) if self.is_pdf else True;self.source_copy=bool(self.pdf.permissions&fitz.PDF_PERM_COPY) if self.is_pdf else True
        self.undo_stack=[]; self.redo_stack=[]; self.dirty=False
    def render(self,index,scale=1):
        if not self.is_pdf: return self.images[index].copy()
        pix=self.pdf[index].get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
        return Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
    def insert(self,paths,at):
        if not self.is_pdf: raise ValueError('Open a PDF first.')
        addition=fitz.open()
        try:
            for path in paths:
                if Path(path).suffix.lower()=='.pdf':
                    with fitz.open(path) as src:
                        if src.needs_pass: raise ValueError('Unlock the inserted PDF first.')
                        addition.insert_pdf(src)
                else:
                    with Image.open(path) as im:
                        for n in range(getattr(im,'n_frames',1)):
                            im.seek(n); frame=ImageOps.exif_transpose(im).convert('RGBA')
                            page=addition.new_page(width=frame.width*.75,height=frame.height*.75)
                            page.insert_image(page.rect,stream=png_bytes(frame))
            self.checkpoint(); self.pdf.insert_pdf(addition,start_at=at)
        finally: addition.close()
    def reorder(self,order):
        if sorted(order)!=list(range(self.count)): raise ValueError('Invalid page order.')
        self.checkpoint()
        if self.is_pdf: self.pdf.select(order)
        else: self.images=[self.images[i] for i in order]
    def delete(self,indices):
        keep=[i for i in range(self.count) if i not in indices]
        if not keep: raise ValueError('Keep at least one page or image.')
        self.checkpoint()
        if self.is_pdf: self.pdf.select(keep)
        else: self.images=[self.images[i] for i in keep]
    def duplicate(self,indices):
        self.checkpoint()
        if self.is_pdf:
            order=[]
            for i in range(self.count): order.extend([i,i] if i in indices else [i])
            self.pdf.select(order)
        else:
            self.images=[copy for i,im in enumerate(self.images) for copy in ([im,im.copy()] if i in indices else [im])]
    def rotate(self,indices,degrees=90):
        self.checkpoint()
        for i in indices:
            if self.is_pdf: self.pdf[i].set_rotation((self.pdf[i].rotation+degrees)%360)
            else: self.images[i]=self.images[i].rotate(-degrees,expand=True)
    def extract(self,indices,path):
        out=fitz.open()
        try:
            for i in indices:
                if self.is_pdf: out.insert_pdf(self.pdf,from_page=i,to_page=i)
                else:
                    im=self.images[i]; p=out.new_page(width=im.width*.75,height=im.height*.75); p.insert_image(p.rect,stream=png_bytes(im))
            save_atomic(out.tobytes(garbage=4,deflate=True),path)
        finally: out.close()
    def redact(self,index,rect):
        self.checkpoint(); page=self.pdf[index]
        page.add_redact_annot(rect,fill=(0,0,0))
        page.apply_redactions(images=2,graphics=1,text=0)
    def clean_pdf(self,metadata=False,annotations=False,links=False,authors=False):
        self.checkpoint()
        if metadata:
            self.pdf.set_metadata({}); self.pdf.del_xml_metadata()
        for page in self.pdf:
            for ann in list(page.annots() or []):
                if annotations: page.delete_annot(ann)
                elif authors: ann.set_info(title='',subject=''); ann.update()
            if links:
                for link in page.get_links(): page.delete_link(link)
    def save_pdf(self,path,password='',allow_print=None,allow_copy=None):
        password=password or self.source_password;allow_print=self.source_print if allow_print is None else allow_print;allow_copy=self.source_copy if allow_copy is None else allow_copy
        args={'garbage':4,'deflate':True}
        if password:
            args.update(encryption=fitz.PDF_ENCRYPT_AES_256,user_pw=password,owner_pw=os.urandom(16).hex(),permissions=(fitz.PDF_PERM_PRINT if allow_print else 0)|(fitz.PDF_PERM_COPY if allow_copy else 0))
        else: args['encryption']=fitz.PDF_ENCRYPT_NONE
        with fitz.open(stream=self.pdf.tobytes(garbage=0),filetype='pdf') as export:
            save_atomic(export.tobytes(**args),path)
        self.path=Path(path); self.dirty=False;self.source_password=password;self.source_print=allow_print;self.source_copy=allow_copy
    def contact_sheet(self,path,indices=None,columns=3):
        indices=indices or list(range(self.count)); out=fitz.open()
        cellw,cellh=180,230
        try:
            for n,i in enumerate(indices):
                if n%9==0: page=out.new_page(width=612,height=792)
                col,row=n%columns,(n%9)//columns
                r=fitz.Rect(24+col*190,24+row*250,24+col*190+cellw,24+row*250+cellh)
                page.insert_image(r,stream=png_bytes(self.render(i,.4)),keep_proportion=True)
                page.insert_text((r.x0,r.y1+13),f'Page {i+1}',fontsize=10)
            save_atomic(out.tobytes(garbage=4,deflate=True),path)
        finally: out.close()
    def inspect(self,index):
        if self.is_pdf:
            return {'document':self.pdf.metadata,'annotations':[{'page':p.number+1,'id':a.xref,**a.info} for p in self.pdf for a in (p.annots() or [])], 'links':[{'page':p.number+1,**l} for p in self.pdf for l in p.get_links()]}
        im=self.images[index]; exif=im.getexif()
        return {'size':im.size,'mode':im.mode,'metadata':im.info,'EXIF':dict(exif),'GPS':exif.get_ifd(34853) if 34853 in exif else {},'AI provenance':'Embedded metadata is evidence only; absent tags do not prove an image is human-made.'}
