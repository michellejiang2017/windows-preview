import fitz
import pytest
from PIL import Image
from PySide6.QtCore import QPointF,QRectF,QSettings,QMimeData,QUrl,Qt
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QApplication,QMessageBox,QFileDialog
from app import Window
import pdf_tools as tools

@pytest.fixture
def window(tmp_path,monkeypatch):
    application=QApplication.instance() or QApplication([])
    w=Window();w.settings=QSettings(str(tmp_path/'settings.ini'),QSettings.Format.IniFormat);w.settings.setValue('versions_dir',str(tmp_path/'versions'))
    monkeypatch.setattr(QMessageBox,'warning',lambda parent,title,msg:pytest.fail(msg))
    d=fitz.open();p=d.new_page();p.insert_text((50,80),'Selectable text',fontsize=16);d.save(tmp_path/'source.pdf');d.close()
    w.load([str(tmp_path/'source.pdf')]);w.show();application.processEvents()
    yield w
    w.doc.dirty=False;w.close()

def test_text_selection_and_copy(window):
    w=window;box=w.doc.pdf[0].search_for('Selectable text')[0];before=w.canvas.scene().items()
    w.mark('select text',QPointF(box.x0*1.5,box.y0*1.5),QPointF(box.x1*1.5,box.y1*1.5),[])
    w.canvas.set_mode('select text');w.copy()
    assert 'Selectable text' in QApplication.clipboard().text()
    assert len(w.canvas.scene().items())>len(before) and not w.doc.dirty

def test_image_move_resize_delete_and_undo(window,tmp_path):
    w=window;path=tmp_path/'image.png';Image.new('RGB',(80,50),'blue').save(path)
    w.drop_image(str(path),QPointF(150,250));assert w.active_object
    original=w.active_object['scene_rect'];changed=QRectF(original);changed.translate(30,40);changed.setWidth(changed.width()*1.4)
    w.transform_selected_object(changed)
    obj=[o for o in tools.objects(w.doc.pdf[0]) if o['kind']=='image'][0]
    assert obj['rect'][0]==pytest.approx(changed.x()/1.5,abs=1)
    assert fitz.Rect(obj['rect']).width==pytest.approx(changed.width()/1.5,abs=1)
    w.canvas.setFocus();w.delete();assert not [o for o in tools.objects(w.doc.pdf[0]) if o['kind']=='image']
    w.undo();assert [o for o in tools.objects(w.doc.pdf[0]) if o['kind']=='image']

def test_save_existing_without_dialog(window,monkeypatch):
    w=window;w.doc.checkpoint();w.doc.pdf[0].insert_text((50,150),'Saved change')
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a:pytest.fail('Ctrl+S opened Save As'))
    w.save_current()
    with fitz.open(w.doc.path) as d:assert 'Saved change' in d[0].get_text()
    assert not w.doc.dirty

def test_save_as_adds_extension(window,tmp_path,monkeypatch):
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a:(str(tmp_path/'newfile'),'PDF (*.pdf)'))
    window.save();assert (tmp_path/'newfile.pdf').exists()

def test_drop_pdf_and_image(window,tmp_path):
    d=fitz.open();d.new_page();path=tmp_path/'added.pdf';d.save(path);d.close()
    mime=QMimeData();mime.setUrls([QUrl.fromLocalFile(str(path))]);event=QDropEvent(QPointF(20,20),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
    window.pages.dropEvent(event);assert window.doc.count==2
    image=tmp_path/'drop.png';Image.new('RGB',(40,30),'red').save(image);mime.setUrls([QUrl.fromLocalFile(str(image))])
    event=QDropEvent(QPointF(250,250),Qt.DropAction.CopyAction,mime,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
    window.canvas.dropEvent(event);assert window.active_object

def test_encrypted_save_preserves_password(tmp_path):
    from engine import Document
    d=fitz.open();d.new_page();path=tmp_path/'private.pdf';d.save(path,encryption=fitz.PDF_ENCRYPT_AES_256,user_pw='secret',owner_pw='owner');d.close()
    document=Document();document.open([str(path)],password='secret');document.save_pdf(path)
    with fitz.open(path) as d:assert d.needs_pass and d.authenticate('secret')

def test_mouse_drag_moves_object(window,tmp_path):
    from PySide6.QtTest import QTest
    path=tmp_path/'drag.png';Image.new('RGB',(120,80),'green').save(path)
    w=window;w.drop_image(str(path),QPointF(150,250));QApplication.processEvents()
    before=QRectF(w.active_object['scene_rect']);start=w.canvas.mapFromScene(before.center());finish=start+__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(25,20)
    QTest.mousePress(w.canvas.viewport(),Qt.MouseButton.LeftButton,pos=start)
    QTest.mouseMove(w.canvas.viewport(),finish)
    QTest.mouseRelease(w.canvas.viewport(),Qt.MouseButton.LeftButton,pos=finish)
    assert w.active_object['scene_rect'].x()>before.x()+10

def test_signature_pad_draw_and_type(window):
    from signature_ui import SignaturePad
    from PySide6.QtTest import QTest
    from PySide6.QtCore import QPoint
    pad=SignaturePad();pad.show();QApplication.processEvents();assert pad.image() is None
    QTest.mousePress(pad,Qt.MouseButton.LeftButton,pos=QPoint(30,50));QTest.mouseMove(pad,QPoint(90,80));QTest.mouseRelease(pad,Qt.MouseButton.LeftButton,pos=QPoint(90,80));assert pad.image().getbbox()
    pad.clear();pad.name='Michelle';assert pad.image().getbbox();pad.close()

def test_signature_action_places_editable_image(window,monkeypatch):
    import signature_ui
    monkeypatch.setattr(signature_ui,'capture_signature',lambda parent:Image.new('RGBA',(120,35),'black'))
    window.actions['Signature…'].trigger();assert window.active_object['object']['kind']=='image'
