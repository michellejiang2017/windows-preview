from io import BytesIO
import fitz,numpy as np,pytest
from PIL import Image,ImageDraw,ImageFont
import pdf_tools as tools
from engine import png_bytes

def text_pdf(lines):
    with fitz.open() as d:
        for text in lines:p=d.new_page(width=400,height=500);p.insert_text((30,60),text,fontsize=16)
        return tools.encoded(d)

def scan_pdf(text='INVOICE NUMBER 12345'):
    im=Image.new('RGB',(1000,600),'white'); font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',46);ImageDraw.Draw(im).text((55,180),text,font=font,fill='black')
    with fitz.open() as d:p=d.new_page(width=500,height=300);p.insert_image(p.rect,stream=png_bytes(im));return tools.encoded(d)

def test_reviewed_redaction_selection():
    data=text_pdf(['SECRET first','SECRET second'])
    with tools.open_copy(data) as d:matches=tools.search_matches(d,'SECRET');assert len(matches)==2
    result=tools.redact_matches(data,[matches[0]])
    with tools.open_copy(result) as d:assert 'SECRET' not in d[0].get_text();assert 'SECRET' in d[1].get_text()
    with tools.open_copy(data) as d:assert 'SECRET' in d[0].get_text()

def test_text_move_replace_delete():
    data=text_pdf(['Original'])
    with tools.open_copy(data) as d:obj=tools.objects(d[0])[0]
    moved=tools.edit_object(data,0,obj,(60,80,260,120),'Replacement')
    with tools.open_copy(moved) as d:
        assert 'Replacement' in d[0].get_text() and 'Original' not in d[0].get_text();new=tools.objects(d[0])[0];assert abs(new['rect'][0]-60)<1
    deleted=tools.edit_object(moved,0,new,delete=True)
    with tools.open_copy(deleted) as d:assert not d[0].get_text().strip()

def test_image_move_resize_and_shared_resource(tmp_path):
    with fitz.open() as d:
        p=d.new_page(width=300,height=300);xref=p.insert_image(fitz.Rect(10,10,70,70),stream=png_bytes(Image.new('RGB',(40,40),'red')));p.insert_text((15,120),'KEEP ME')
        p=d.new_page(width=300,height=300);p.insert_image(fitz.Rect(10,10,70,70),xref=xref);data=tools.encoded(d);obj=next(o for o in tools.objects(d[0]) if o['kind']=='image')
    result=tools.edit_object(data,0,obj,(100,100,220,180))
    with tools.open_copy(result) as d:
        assert 'KEEP ME' in d[0].get_text();assert d[0].get_pixmap().pixel(30,30)==(255,255,255);assert d[0].get_pixmap().pixel(150,150)==(255,0,0);assert d[1].get_pixmap().pixel(30,30)==(255,0,0)
        obj=next(o for o in tools.objects(d[0]) if o['kind']=='image')
    replacement=tmp_path/'blue.png';Image.new('RGB',(40,40),'blue').save(replacement);result=tools.edit_object(result,0,obj,replacement=str(replacement))
    with tools.open_copy(result) as d:assert d[0].get_pixmap().pixel(150,150)==(0,0,255)

def test_repeated_image_refused():
    with fitz.open() as d:
        p=d.new_page();xref=p.insert_image(fitz.Rect(10,10,50,50),stream=png_bytes(Image.new('RGB',(20,20),'red')));p.insert_image(fitz.Rect(80,80,120,120),xref=xref);data=tools.encoded(d);obj=tools.objects(p)[0]
    with pytest.raises(ValueError,match='complex|multiple times'):tools.edit_object(data,0,obj,delete=True)

def test_blank_detection_and_cleanup_navigation():
    with fitz.open() as d:
        d.new_page();p=d.new_page();p.insert_text((40,60),'Visible content');d.set_toc([[1,'Keep destination',2]]);data=tools.encoded(d);assert tools.blank_candidates(d,[0,1])==[0]
    cleaned=tools.clean_scans(data,[1],False)
    with tools.open_copy(cleaned) as d:assert len(d)==2;assert d[1].get_images();assert not d[1].get_text().strip();assert d.get_toc()[0][2]==2

def test_cleanup_refuses_forms():
    with fitz.open() as d:
        p=d.new_page();w=fitz.Widget();w.field_name='name';w.field_type=fitz.PDF_WIDGET_TYPE_TEXT;w.rect=fitz.Rect(10,10,100,40);p.add_widget(w);data=tools.encoded(d)
    with pytest.raises(ValueError,match='forms'):tools.clean_scans(data,[0])

def test_deskew():
    im=Image.new('L',(700,450),255);draw=ImageDraw.Draw(im)
    for y in range(80,380,45):draw.rectangle((60,y,600,y+8),fill=0)
    tilted=im.rotate(3,fillcolor=255);assert abs(tools.deskew_angle(tilted)+3)<=.5

def test_compression_and_bookmarks():
    rng=np.random.default_rng(42);im=Image.fromarray(rng.integers(0,256,(800,800,3),dtype=np.uint8))
    with fitz.open() as d:p=d.new_page(width=400,height=400);p.insert_image(p.rect,stream=png_bytes(im));p.insert_text((20,30),'SEARCHABLE');d.set_toc([[1,'Chapter',1]]);data=tools.encoded(d)
    result,info=tools.compress_pdf(data,250000)
    assert len(result)<len(data) and info['target_met']
    with tools.open_copy(result) as d:assert 'SEARCHABLE' in d[0].get_text();assert d.get_toc()[0][1]=='Chapter'

def test_comparison_including_image_only_changes():
    a=text_pdf(['One','Two']);b=text_pdf(['One changed','Two','Three']);report=tools.compare_pdfs(a,b);assert report[0]['page']==1 and 'One changed' in report[0]['diff'];assert report[-1]['status']=='Added page'
    with tools.open_copy(a) as d:d[1].insert_image(fitz.Rect(20,100,70,150),stream=png_bytes(Image.new('RGB',(40,40),'red')));b=tools.encoded(d)
    report=tools.compare_pdfs(a,b);assert report==[{'page':2,'status':'Appearance changed','diff':''}]

def test_organization_roundtrip():
    data=tools.set_bookmarks(text_pdf(['Body','Body']),[[1,'First',1],[2,'Second',2]])
    data=tools.decorate(data,[0,1],header='Report',footer='Private',start=5)
    with tools.open_copy(data) as d:
        assert d.get_toc()==[[1,'First',1],[2,'Second',2]];assert 'Report' in d[0].get_text();assert 'Private' in d[1].get_text();assert '6' in d[1].get_text()

def test_ocr_real_model():
    data=scan_pdf();result,info=tools.ocr_pdf(data,[0]);assert info['recognized_lines']>0
    with tools.open_copy(result) as d:assert '12345' in d[0].get_text();assert d[0].search_for('INVOICE');after=d[0].get_pixmap().samples
    with tools.open_copy(data) as d:assert after==d[0].get_pixmap().samples
    second,info=tools.ocr_pdf(result,[0]);assert info['skipped_text_pages']==1

def test_pdf_dialogs_wired(tmp_path,monkeypatch):
    from PySide6.QtWidgets import QApplication,QDialog,QInputDialog,QLineEdit,QTextEdit,QMessageBox
    from PySide6.QtCore import QSettings
    from app import Window
    app=QApplication.instance() or QApplication([]);w=Window();w.settings=QSettings(str(tmp_path/'ui.ini'),QSettings.Format.IniFormat);w.doc.pdf=tools.open_copy(text_pdf(['SECRET original','Second']));w.refresh()
    monkeypatch.setattr(QMessageBox,'warning',lambda parent,title,message:pytest.fail(message))
    def accept(dlg):
        if dlg.windowTitle()=='Edit text or image object':dlg.findChild(QLineEdit,'replacement_text').setText('Edited')
        if dlg.windowTitle()=='Bookmarks':dlg.findChildren(QTextEdit)[0].setPlainText('1 | Opening | 1')
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(QDialog,'exec',accept);monkeypatch.setattr(QInputDialog,'getText',lambda *args,**kwargs:('SECRET',True))
    for title in ['OCR whole document…','Edit page objects…','Search and redact…','Compare with another PDF…','Page labels…']:assert title in w.actions
    w.actions['Search and redact…'].trigger();assert 'SECRET' not in w.doc.pdf[0].get_text();w.undo()
    w.actions['Edit page objects…'].trigger();assert w.canvas.mode=='object'
    w.actions['Object properties…'].trigger();assert 'Edited' in w.doc.pdf[0].get_text()
    w.actions['Bookmarks…'].trigger();assert w.doc.pdf.get_toc()==[[1,'Opening',1]]
    w.actions['Page labels…'].trigger();assert w.doc.pdf[0].get_label()=='1'
    w.actions['Headers, footers and numbering…'].trigger();assert '1' in w.doc.pdf[0].get_text()
    w.doc.dirty=False;w.close()

def test_image_operator_parser_ignores_pdf_strings():
    stream=b'q /Im1 Do Q (text says /Im1 Do) Tj % /Im1 Do\n'
    spans=tools.image_draw_spans(stream,'Im1');assert len(spans)==1;assert stream[slice(*spans[0])]==b'/Im1 Do'

def test_ocr_textbox_selection():
    data=scan_pdf('HELLO WORLD 123');result,info=tools.ocr_pdf(data,[0])
    with tools.open_copy(result) as d:
        hits=d[0].search_for('HELLO');assert hits;assert 'HELLO' in d[0].get_textbox(hits[0])
