import sys
from pathlib import Path
from io import BytesIO
import pytest,fitz
from PIL import Image
from engine import Document,png_bytes,image_bytes,instant_alpha,remove_gps,adjust

@pytest.fixture
def sample(tmp_path):
    path=tmp_path/'source.pdf'; d=fitz.open()
    for text in ['FIRST SECRET','SECOND','THIRD']:
        p=d.new_page(width=300,height=400); p.insert_text((30,50),text)
    d.set_metadata({'author':'Private author'}); d.save(path); d.close(); return path

def test_merge_extract_and_original_unchanged(sample,tmp_path):
    original=sample.read_bytes(); d=Document(); d.open([sample]); image=tmp_path/'photo.png'; Image.new('RGB',(80,60),'red').save(image)
    d.insert([image,sample],1); assert d.count==7
    d.extract([1,0],tmp_path/'out.pdf')
    with fitz.open(tmp_path/'out.pdf') as out: assert len(out)==2 and 'FIRST' in out[1].get_text() and out[0].get_images()
    assert sample.read_bytes()==original

def test_order_delete_duplicate_undo(sample):
    d=Document(); d.open([sample]); d.reorder([2,0,1]); assert 'THIRD' in d.pdf[0].get_text(); d.delete([1]); assert d.count==2
    d.undo(); assert d.count==3; d.redo(); assert d.count==2; d.duplicate([0]); assert d.count==3

def test_redaction_removes_text(sample,tmp_path):
    d=Document(); d.open([sample]); r=d.pdf[0].search_for('SECRET')[0]; d.redact(0,r); path=tmp_path/'redacted.pdf'; d.save_pdf(path)
    with fitz.open(path) as out: assert 'SECRET' not in out[0].get_text() and 'FIRST' in out[0].get_text()
    assert b'SECRET' not in path.read_bytes()

def test_redaction_removes_image_pixels(tmp_path):
    d=Document(); d.pdf=fitz.open(); p=d.pdf.new_page(width=100,height=100); p.insert_image(p.rect,stream=png_bytes(Image.new('RGB',(100,100),'red')))
    d.redact(0,fitz.Rect(20,20,80,80)); d.save_pdf(tmp_path/'image-redact.pdf')
    with fitz.open(tmp_path/'image-redact.pdf') as out:
        pix=out[0].get_pixmap(); assert pix.pixel(50,50)==(0,0,0)
        # Original red samples are replaced in the image stream too.
        raw=out.extract_image(out[0].get_images()[0][0]); im=Image.open(BytesIO(raw['image'])); assert im.getpixel((50,50))!=(255,0,0)

def test_encryption(sample,tmp_path):
    d=Document(); d.open([sample]); d.save_pdf(tmp_path/'secure.pdf','test-password',allow_copy=False)
    with fitz.open(tmp_path/'secure.pdf') as out:
        assert out.needs_pass; assert not out.authenticate('wrong'); assert out.authenticate('test-password'); assert not out.permissions & fitz.PDF_PERM_COPY

def test_metadata_annotations_links(sample,tmp_path):
    d=Document(); d.open([sample]); p=d.pdf[0]; a=p.add_rect_annot(fitz.Rect(20,20,80,80)); a.set_info(title='Name'); a.update(); p.insert_link({'kind':fitz.LINK_URI,'from':fitz.Rect(10,100,80,120),'uri':'https://example.com'})
    d.clean_pdf(metadata=True,annotations=True,links=True); d.save_pdf(tmp_path/'clean.pdf')
    with fitz.open(tmp_path/'clean.pdf') as out: assert not out.metadata['author']; assert not list(out[0].annots() or []); assert not out[0].get_links()

def test_image_alpha_gps_and_export():
    im=Image.new('RGBA',(40,20),'white'); im.putpixel((10,10),(255,0,0,255)); cut=instant_alpha(im,0,0,10); assert cut.getpixel((0,0))[3]==0; assert cut.getpixel((10,10))[3]==255
    exif=im.getexif(); exif[34853]={1:'N',2:(1,2,3)}; exif[270]='retain description'; im.info['exif']=exif.tobytes(); cleaned=remove_gps(im); assert 34853 not in cleaned.getexif(); assert cleaned.getexif()[270]=='retain description'
    for ext in ['.png','.jpg','.webp','.bmp','.tiff','.gif','.ppm','.pgm','.pbm','.tga','.jp2']:
        data=image_bytes(cut,ext); assert len(data)>0
        with Image.open(BytesIO(data)) as out: assert out.size==(40,20)
    assert adjust(cut,2).getpixel((0,0))[3]==0

def test_contact_sheet_and_form(sample,tmp_path):
    d=Document(); d.open([sample]); p=d.pdf[0]; w=fitz.Widget(); w.field_name='name'; w.field_type=fitz.PDF_WIDGET_TYPE_TEXT; w.rect=fitz.Rect(20,120,150,145); w.field_value='Original'; p.add_widget(w)
    p=d.pdf[0]; w=next(p.widgets()); w.field_value='Filled'; w.update(); d.save_pdf(tmp_path/'form.pdf')
    with fitz.open(tmp_path/'form.pdf') as out: assert next(out[0].widgets()).field_value=='Filled'
    d.contact_sheet(tmp_path/'sheet.pdf')
    with fitz.open(tmp_path/'sheet.pdf') as out: assert len(out)==1 and len(out[0].get_images())==3

def test_native_ui_smoke(sample,tmp_path,monkeypatch):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt,QPoint
    from app import Window
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox,'warning',lambda parent,title,message:pytest.fail(message))
    from PySide6.QtCore import QSettings
    QSettings.setDefaultFormat(QSettings.Format.IniFormat); QSettings.setPath(QSettings.Format.IniFormat,QSettings.Scope.UserScope,str(tmp_path/'settings'))
    app=QApplication.instance() or QApplication([]); w=Window(); w.settings=QSettings(str(tmp_path/'settings.ini'),QSettings.Format.IniFormat); w.settings.setValue('versions_dir',str(tmp_path/'versions')); w.load([str(sample)]); w.show(); QTest.qWait(100)
    assert w.pages.count()==3; w.actions['Add blank page'].trigger(); assert w.doc.count==4; w.actions['Undo'].trigger(); assert w.doc.count==3
    w.navigate(2); w.back(); assert w.index==0; w.forward(); assert w.index==2
    from PySide6.QtCore import QPointF,QItemSelectionModel
    from PIL.ImageQt import ImageQt
    w.pages.item(0).setSelected(True); w.pages.item(1).setSelected(True); assert {0,1}.issubset(set(w.selected()))
    from PySide6.QtGui import QImage
    clipboard_image=QImage(ImageQt(Image.new('RGBA',(32,32),'red'))).copy()
    class TestClipboard:
        def image(self):return clipboard_image
    monkeypatch.setattr(QApplication,'clipboard',lambda:TestClipboard())
    w.paste_at(fitz.Rect(20,20,70,70)); assert w.doc.pdf[2].get_images()
    w.rotate(90); assert w.doc.pdf[2].rotation==90
    w.mark('crop',QPointF(30,30),QPointF(270,360),[]); assert w.doc.pdf[2].cropbox.width<300
    w.doc.save_pdf(tmp_path/'edited.pdf'); w.save_version(tmp_path/'edited.pdf'); assert list((tmp_path/'versions').rglob('*.pdf'))
    before=w.doc.render(2).tobytes(); w.toggle_dark(); assert before==w.doc.render(2).tobytes()
    w.dark=False; w.navigate(0); w.canvas.fit(); w.grab().save(str(tmp_path/'ui.png'))
    w.doc.dirty=False; w.close()

