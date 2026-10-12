"""Preview for Windows — native Qt desktop document workbench."""
import sys, json, traceback, uuid
from pathlib import Path
from io import BytesIO
from functools import wraps
import fitz
from PIL import Image, ImageOps
from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt, QSize, QTimer, QSettings, QMimeData, QUrl, Signal, QThread,QRectF,QStandardPaths
from PySide6.QtGui import QAction, QPixmap, QImage, QColor, QPen, QPainterPath, QDrag, QDesktopServices,QFont,QFontDatabase
import preview_ui
from PySide6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QToolBar,QFileDialog,QMessageBox,QInputDialog,QLineEdit,QSpinBox,QDoubleSpinBox,QDialog,QDialogButtonBox,QFormLayout,QCheckBox,QComboBox,QListWidget,QListWidgetItem,QAbstractItemView,QSplitter,QGraphicsView,QGraphicsScene,QGraphicsPixmapItem,QGraphicsPathItem,QGraphicsRectItem,QTextEdit,QColorDialog,QProgressDialog,QMenu)
from PySide6.QtPrintSupport import QPrinter,QPrintDialog
from engine import Document,IMAGE_EXTS,png_bytes,image_bytes,save_atomic,remove_gps,instant_alpha,adjust
from pdf_ui import PdfToolsMixin

def guarded(fn):
    @wraps(fn)
    def wrapped(self,*args,**kwargs):
        try: return fn(self,*args,**kwargs)
        except Exception as e:
            QMessageBox.warning(self,'Could not complete action',str(e)); return None
    return wrapped

def pil_pixmap(im): return QPixmap.fromImage(ImageQt(im.convert('RGBA')))
def qimage_pil(im):
    from PySide6.QtCore import QBuffer,QIODevice
    buffer=QBuffer(); buffer.open(QIODevice.OpenModeFlag.WriteOnly); im.save(buffer,'PNG')
    return Image.open(BytesIO(bytes(buffer.data()))).convert('RGBA')

class Worker(QThread):
    result=Signal(object); failed=Signal(str)
    def __init__(self,job,parent): super().__init__(parent); self.job=job
    def run(self):
        try: self.result.emit(self.job())
        except Exception as e: self.failed.emit(str(e))

class Canvas(QGraphicsView):
    def __init__(self,owner):
        super().__init__(); self.owner=owner; self.setScene(QGraphicsScene(self)); self.mode='view'; self.start=None; self.preview=None; self.points=[]
        self.setRenderHints(self.renderHints()); self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAcceptDrops(True);self.viewport().setAcceptDrops(True);self.setMouseTracking(True);self.object_drag=None
    def display(self,im):
        self.scene().clear();self.owner.active_object=None;self.owner.selected_text='';self.pix=self.scene().addPixmap(pil_pixmap(im)); self.scene().setSceneRect(self.pix.boundingRect()); self.fit()
    def fit(self):
        if self.scene().items(): self.fitInView(self.scene().sceneRect(),Qt.AspectRatioMode.KeepAspectRatio)
    def set_mode(self,mode):
        self.mode=mode; self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if mode=='view' else QGraphicsView.DragMode.NoDrag)
        self.setCursor(Qt.CursorShape.ArrowCursor if mode=='view' else Qt.CursorShape.CrossCursor)
        self.owner.statusBar().showMessage('Drag on the page to '+mode if mode!='view' else 'Ready')
        if hasattr(self.owner,'mode_buttons'):
            for name,button in self.owner.mode_buttons.items():button.setChecked(name==mode)
            if mode!='view':self.owner.markup_toolbar.show()
    def mousePressEvent(self,e):
        if self.mode=='object':
            pt=self.mapToScene(e.position().toPoint());selected=self.owner.active_object
            if selected:
                rect=selected['scene_rect'];tolerance=10/max(self.transform().m11(),.01)
                if abs(pt.x()-rect.right())<tolerance and abs(pt.y()-rect.bottom())<tolerance:self.object_drag=(pt,QRectF(rect),True);return
            selected=self.owner.pick_object(pt)
            if selected:self.object_drag=(pt,QRectF(selected['scene_rect']),False)
            return
        if self.mode=='view':
            if self.owner.doc.is_pdf and e.button()==Qt.MouseButton.LeftButton:
                pt=self.mapToScene(e.position().toPoint()); self.owner.follow_link(pt)
            return super().mousePressEvent(e)
        if not self.owner.doc.count: return
        self.start=self.mapToScene(e.position().toPoint()); self.points=[self.start]
        if self.mode=='alpha': self.owner.alpha(self.start); self.start=None
    def mouseMoveEvent(self,e):
        if self.mode=='object' and self.object_drag:
            pt=self.mapToScene(e.position().toPoint());start,rect,resize=self.object_drag;result=QRectF(rect)
            if resize:result.setRight(max(rect.left()+8,pt.x()));result.setBottom(max(rect.top()+8,pt.y()))
            else:result.translate(pt-start)
            self.owner.object_outline.setRect(result);self.owner.object_grip.setRect(QRectF(result.right()-5,result.bottom()-5,10,10));return
        if self.mode=='view': return super().mouseMoveEvent(e)
        if self.start is None: return
        pt=self.mapToScene(e.position().toPoint()); self.points.append(pt)
        if self.preview: self.scene().removeItem(self.preview)
        if self.mode=='pen':
            path=QPainterPath(self.start)
            for p in self.points[1:]: path.lineTo(p)
            self.preview=self.scene().addPath(path,QPen(QColor(self.owner.ink),3))
        else:
            self.preview=self.scene().addRect(QRectF(self.start,pt).normalized(),QPen(QColor(self.owner.ink),2))
    def mouseReleaseEvent(self,e):
        if self.mode=='object':
            if self.object_drag:
                start,original,resize=self.object_drag;self.object_drag=None;result=self.owner.object_outline.rect()
                if result!=original:self.owner.transform_selected_object(result)
            return
        if self.mode=='view': return super().mouseReleaseEvent(e)
        if self.start is None: return
        pt=self.mapToScene(e.position().toPoint()); start=self.start; self.start=None
        if self.preview: self.scene().removeItem(self.preview); self.preview=None
        self.owner.mark(self.mode,start,pt,self.points)
    def wheelEvent(self,e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier: self.scale(1.15 if e.angleDelta().y()>0 else 1/1.15,1.15 if e.angleDelta().y()>0 else 1/1.15)
        else: super().wheelEvent(e)
    def mouseDoubleClickEvent(self,e):
        if self.mode=='object' and self.owner.active_object:self.owner.edit_page_objects();return
        if not self.owner.doc.count:self.owner.open_dialog();return
        super().mouseDoubleClickEvent(e)
    def keyPressEvent(self,e):
        if self.mode=='object' and e.key()==Qt.Key.Key_Delete:self.owner.delete_selected_object();return
        super().keyPressEvent(e)
    def dragEnterEvent(self,e):
        if e.mimeData().hasUrls():e.acceptProposedAction()
    def dragMoveEvent(self,e):e.acceptProposedAction()
    def dropEvent(self,e):
        paths=[u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if self.owner.doc.count and len(paths)==1 and Path(paths[0]).suffix.lower() in IMAGE_EXTS:
            self.owner.drop_image(paths[0],self.mapToScene(e.position().toPoint()))
        elif self.owner.doc.is_pdf:self.owner.insert_at(paths,self.owner.index+1)
        elif paths:self.owner.load(paths)
        e.acceptProposedAction()

class Pages(QListWidget):
    def __init__(self,owner):
        super().__init__(); self.owner=owner; self.setIconSize(QSize(112,145)); self.setSpacing(8)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop);self.setDefaultDropAction(Qt.DropAction.MoveAction);self.setDropIndicatorShown(True)
        self.currentRowChanged.connect(owner.navigate)
        self.model().rowsMoved.connect(self.reordered)
    def reordered(self,*args):
        order=[self.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.count())]
        self.owner.doc.reorder(order); self.owner.refresh()
    def keyPressEvent(self,e):
        if e.key()==Qt.Key.Key_Delete: self.owner.delete()
        else: super().keyPressEvent(e)
    def mimeData(self,items):
        data=super().mimeData(items)
        if self.owner.doc.count:
            folder=Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation))/'PreviewWindows-extracted';folder.mkdir(parents=True,exist_ok=True);path=folder/f'Pages-{uuid.uuid4().hex[:8]}.pdf';self.owner.doc.extract(sorted(self.row(item) for item in items),path);data.setUrls([QUrl.fromLocalFile(str(path))])
        return data
    def dragEnterEvent(self,e):
        if e.mimeData().hasUrls():e.acceptProposedAction()
        else:super().dragEnterEvent(e)
    def dragMoveEvent(self,e):e.acceptProposedAction()
    def dropEvent(self,e):
        if e.source() is self:super().dropEvent(e);return
        paths=[u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()];row=self.indexAt(e.position().toPoint()).row()
        at=self.count() if row<0 else row+(e.position().y()>self.visualItemRect(self.item(row)).center().y())
        if self.owner.doc.is_pdf:self.owner.insert_at(paths,at)
        else:self.owner.load(paths)
        e.acceptProposedAction()

class FileHandle(QPushButton):
    def __init__(self,owner): super().__init__('Drag file'); self.owner=owner; self.setToolTip('Drag the saved file into Explorer, email, or a notes app. Unsaved edits must be exported first.')
    def mouseMoveEvent(self,e):
        path=self.owner.doc.path
        if path and path.exists() and not self.owner.doc.dirty:
            drag=QDrag(self); data=QMimeData(); data.setUrls([QUrl.fromLocalFile(str(path.resolve()))]); drag.setMimeData(data); drag.exec(Qt.DropAction.CopyAction)

class Window(PdfToolsMixin,QMainWindow):
    def __init__(self):
        super().__init__(); self.doc=Document(); self.index=0; self.history=[]; self.forward_history=[]; self.render_scale=1.5; self.ink='#2563eb'; self.author=''; self.worker=None
        if sys.platform=='win32':
            font_path=Path('C:/Windows/Fonts/segoeui.ttf')
            if font_path.exists():QFontDatabase.addApplicationFont(str(font_path))
            QApplication.instance().setFont(QFont('Segoe UI',10))
        self.settings=QSettings('LocalPreview','PreviewWindows'); self.author=self.settings.value('author',''); self.dark=self.settings.value('dark',False,type=bool)
        self.setWindowTitle('Preview for Windows'); self.resize(1180,820); self.setAcceptDrops(True)
        self.canvas=Canvas(self); self.pages=Pages(self); splitter=QSplitter(); splitter.addWidget(self.pages); splitter.addWidget(self.canvas); splitter.setSizes([185,995]); self.setCentralWidget(splitter)
        self.actions={}; self.build_actions(); self.apply_theme(); self.canvas.setBackgroundBrush(QColor(self.settings.value('canvas','#d6d6d6')))
        self.active_object=None
        self.statusBar().showMessage('Open a PDF, image, or folder. Drop files here to begin.'); self.update_title()
    def action(self,menu,text,callback,shortcut=None,toolbar=None):
        a=QAction(text,self); a.triggered.connect(lambda checked=False: callback())
        if shortcut: a.setShortcut(shortcut)
        menu.addAction(a); self.actions[text]=a
        if toolbar: toolbar.addAction(a)
        return a
    def build_actions(self):
        main=QToolBar('Document tools'); main.setObjectName('main'); self.addToolBar(main); self.main_toolbar=main
        markup=QToolBar('Markup tools'); markup.setObjectName('markup'); self.addToolBar(Qt.ToolBarArea.BottomToolBarArea,markup)
        file=self.menuBar().addMenu('File'); edit=self.menuBar().addMenu('Edit'); pdf=self.menuBar().addMenu('PDF'); image=self.menuBar().addMenu('Image'); view=self.menuBar().addMenu('View'); helpmenu=self.menuBar().addMenu('Help')
        for text,fn,key in [('Open…',self.open_dialog,'Ctrl+O'),('Open folder…',self.open_folder,None),('New blank PDF',self.new_pdf,'Ctrl+N'),('New from clipboard',self.clipboard_new,'Ctrl+Shift+N'),('Save as…',self.save,'Ctrl+Shift+S'),('Print…',self.print_doc,'Ctrl+P')]: self.action(file,text,fn,key,main if text in ['Open…','Save as…'] else None)
        self.action(file,'Save',self.save_current,'Ctrl+S')
        self.action(file,'Export selected pages…',self.extract,'Ctrl+E'); self.action(file,'Export contact sheet…',self.contact_sheet); self.action(file,'Export images / render pages…',self.export_images); self.action(file,'Browse saved versions…',self.versions); self.action(file,'Reveal saved file',self.reveal)
        for text,fn,key in [('Undo',self.undo,'Ctrl+Z'),('Redo',self.redo,'Ctrl+Y'),('Copy page / image',self.copy,'Ctrl+C'),('Paste image onto page',self.paste,'Ctrl+V'),('Delete selected pages',self.delete,'Delete'),('Duplicate selected pages',self.duplicate,'Ctrl+D')]: self.action(edit,text,fn,key)
        self.action(pdf,'Insert PDFs or images…',self.insert,None,main); self.action(pdf,'Add blank page',self.blank); self.action(pdf,'Replace current page…',self.replace); self.action(pdf,'Rotate selected right',lambda:self.rotate(90),'Ctrl+R',main); self.action(pdf,'Rotate selected left',lambda:self.rotate(-90),'Ctrl+L'); self.action(pdf,'Crop page',lambda:self.canvas.set_mode('crop')); self.action(pdf,'Fill form fields…',self.forms); self.action(pdf,'Extract text…',self.text_export); self.action(pdf,'Extract embedded images…',self.embedded_images); self.action(pdf,'Password and permissions…',self.encrypt); self.action(pdf,'Remove document metadata',lambda:self.cleanup('metadata')); self.action(pdf,'Delete all annotations',lambda:self.cleanup('annotations')); self.action(pdf,'Delete all hyperlinks',lambda:self.cleanup('links')); self.action(pdf,'Remove annotation author names',lambda:self.cleanup('authors')); self.action(pdf,'Annotation author…',self.set_author)
        self.add_pdf_tools(pdf)
        self.action(edit,'Signature…',self.add_signature)
        for mode in ['view','select text','text','pen','rectangle','highlight','redact','crop','stamp','alpha']:
            self.action(edit,mode.title(),lambda m=mode:self.canvas.set_mode(m),None,markup)
        self.action(edit,'Ink color…',self.ink_color); self.action(edit,'Find text…',self.find,'Ctrl+F'); self.action(view,'Inspector',self.inspector,'Ctrl+I',main)
        self.action(image,'Remove background (local AI)',self.remove_background,None,main); self.action(image,'Copy subject',lambda:self.remove_background(copy=True)); self.action(image,'Instant Alpha tolerance…',self.alpha_tolerance); self.tolerance=35
        self.action(image,'Resize selected images…',self.resize_images); self.action(image,'Adjust color…',self.adjust_images); self.action(image,'Rotate images freely…',self.free_rotate); self.action(image,'Remove GPS location',self.strip_gps); self.action(image,'Strip all image metadata',self.strip_metadata)
        prev=QPushButton('‹'); next=QPushButton('›')
        for button,delta in [(prev,-1),(next,1)]:
            button.setAutoRepeat(True); button.setAutoRepeatDelay(350); button.setAutoRepeatInterval(75); button.clicked.connect(lambda checked=False,d=delta:self.navigate(self.index+d)); main.addWidget(button)
        self.action(view,'Back',self.back,'Alt+Left'); self.action(view,'Forward',self.forward,'Alt+Right'); self.page_number=QSpinBox(); self.page_number.setPrefix('Page '); self.page_number.setRange(1,1); self.page_number.valueChanged.connect(lambda n:self.navigate(n-1)); main.addWidget(self.page_number)
        self.action(view,'Fit to window',self.canvas.fit,'Ctrl+0'); self.action(view,'Zoom in',lambda:self.canvas.scale(1.2,1.2),'Ctrl++'); self.action(view,'Zoom out',lambda:self.canvas.scale(1/1.2,1/1.2),'Ctrl+-'); self.action(view,'Contact sheet overview',self.toggle_overview); self.action(view,'Dark PDF appearance',self.toggle_dark); self.action(view,'Canvas color…',self.canvas_color); self.action(view,'Customize toolbar…',self.customize)
        main.addWidget(FileHandle(self)); view.addAction(main.toggleViewAction()); view.addAction(markup.toggleViewAction()); self.action(helpmenu,'Features and limitations',self.help)
        hidden=set(self.settings.value('hidden_tools',[]))
        for a in main.actions():
            if a.text() in hidden: a.setVisible(False)
        preview_ui.install(self,main,markup)
    def apply_theme(self):
        self.setStyleSheet(preview_ui.STYLE)
    def update_title(self):
        name=self.doc.path.name if self.doc.path else 'Untitled'
        self.setWindowTitle(f'{name}{" *" if self.doc.dirty else ""} — Preview for Windows')
        if hasattr(self,'document_title'):
            self.document_title.setText(name+(' · Edited' if self.doc.dirty else ''));self.document_subtitle.setText(f'{self.doc.count} pages' if self.doc.is_pdf else (f'{self.doc.count} images' if self.doc.count else 'Open a document'))
        if hasattr(self,'mode_buttons'):
            for mode,button in self.mode_buttons.items():button.setEnabled(bool(self.doc.count) and (mode not in ['object','select text','redact'] or self.doc.is_pdf) and (mode!='alpha' or not self.doc.is_pdf))
            for label in ['Save','Save as…','Print…','Export selected pages…','Export images / render pages…']:self.actions[label].setEnabled(bool(self.doc.count))
    def selected(self): return sorted(self.pages.row(item) for item in self.pages.selectedItems()) or [self.index]
    def require(self,pdf=None):
        if not self.doc.count: raise ValueError('Open a document first.')
        if pdf is True and not self.doc.is_pdf: raise ValueError('This tool works on PDFs. Export your images as a PDF first.')
        if pdf is False and self.doc.is_pdf: raise ValueError('This tool works on images. Export the PDF pages as images first.')
    def discard(self):
        return not self.doc.dirty or QMessageBox.question(self,'Unsaved changes','Discard unsaved changes?',QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes
    def refresh(self):
        from PySide6.QtGui import QIcon
        self.index=max(0,min(self.index,self.doc.count-1)); self.pages.blockSignals(True); self.pages.clear()
        for i in range(self.doc.count):
            im=self.doc.render(i,.18); im.thumbnail((112,145)); item=QListWidgetItem(QIcon(pil_pixmap(im)),f'{i+1}'); item.setData(Qt.ItemDataRole.UserRole,i); self.pages.addItem(item)
        self.pages.setCurrentRow(self.index); self.pages.blockSignals(False); self.page_number.blockSignals(True); self.page_number.setRange(1,max(1,self.doc.count)); self.page_number.setValue(self.index+1); self.page_number.blockSignals(False)
        self.show_page(); self.update_title()
    def show_page(self):
        if not self.doc.count: return
        im=self.doc.render(self.index,self.render_scale)
        if self.dark and self.doc.is_pdf: im=ImageOps.invert(im.convert('RGB'))
        self.canvas.display(im); self.statusBar().showMessage(f'Page {self.index+1} of {self.doc.count}' if self.doc.is_pdf else f'Image {self.index+1} of {self.doc.count}');self.update_title()
    def navigate(self,index,remember=True):
        if not 0<=index<self.doc.count: return
        if remember and index!=self.index: self.history.append(self.index); self.forward_history.clear()
        self.index=index; self.pages.blockSignals(True)
        if self.pages.currentRow()!=index:self.pages.setCurrentRow(index)
        self.pages.blockSignals(False); self.page_number.blockSignals(True); self.page_number.setValue(index+1); self.page_number.blockSignals(False); self.show_page()
    def back(self):
        if self.history: self.forward_history.append(self.index); self.navigate(self.history.pop(),False)
    def forward(self):
        if self.forward_history: self.history.append(self.index); self.navigate(self.forward_history.pop(),False)
    @guarded
    def load(self,paths):
        if not self.discard(): return
        expanded=[]
        for path in paths:
            p=Path(path)
            if p.is_dir(): expanded.extend(str(f) for f in sorted(p.iterdir()) if f.suffix.lower() in IMAGE_EXTS)
            else: expanded.append(str(p))
        if not expanded: raise ValueError('No supported images in this folder.')
        if len(expanded)==1 and Path(expanded[0]).suffix.lower() in {'.obj','.stl','.ply','.glb','.gltf','.usd','.usda','.usdc','.usdz'}:raise ValueError('This build focuses on PDFs and images; 3D is outside its scope.')
        if any(Path(p).suffix.lower()=='.pdf' for p in expanded) and len(expanded)>1:
            self.doc.open([next(p for p in expanded if Path(p).suffix.lower()=='.pdf')]); remaining=list(expanded); remaining.remove(str(self.doc.path)); self.doc.insert(remaining,self.doc.count)
        else:
            password=''
            if Path(expanded[0]).suffix.lower()=='.pdf':
                with fitz.open(expanded[0]) as d:
                    if d.needs_pass:
                        password,ok=QInputDialog.getText(self,'Unlock PDF','Password:',QLineEdit.EchoMode.Password)
                        if not ok: return
            self.doc.open(expanded,password)
        self.index=0; self.history.clear(); self.forward_history.clear(); self.refresh(); return True
    def open_dialog(self):
        paths,_=QFileDialog.getOpenFileNames(self,'Open PDFs or images','','Documents (*.pdf *.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.gif *.heic *.heif *.avif *.psd *.ico *.ppm *.tga *.jp2);;All files (*)')
        if paths: self.load(paths)
    def open_folder(self):
        path=QFileDialog.getExistingDirectory(self,'Open image folder')
        if path: self.load([path])
    def dragEnterEvent(self,e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
    def dropEvent(self,e):
        paths=[u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if self.doc.is_pdf and self.doc.count: self.insert(paths)
        else: self.load(paths)
        e.acceptProposedAction()
    @guarded
    def new_pdf(self):
        if not self.discard(): return
        self.doc=Document(); self.doc.pdf=fitz.open(); self.doc.pdf.new_page(); self.doc.dirty=True; self.index=0; self.refresh()
    @guarded
    def insert(self,paths=None):
        self.require(True)
        if paths is None: paths,_=QFileDialog.getOpenFileNames(self,'Insert PDFs or images')
        if paths:self.insert_at(paths,self.index+1)
    @guarded
    def insert_at(self,paths,at):
        self.require(True);expanded=[]
        for path in paths:
            p=Path(path)
            if p.is_dir():expanded.extend(str(f) for f in sorted(p.iterdir()) if f.suffix.lower() in IMAGE_EXTS|{'.pdf'})
            else:expanded.append(str(p))
        if expanded:self.doc.insert(expanded,at);self.index=min(at,self.doc.count-1);self.refresh()
    @guarded
    def blank(self):
        self.require(True); self.doc.checkpoint(); self.doc.pdf.new_page(pno=self.index+1); self.refresh()
    @guarded
    def replace(self):
        self.require(True); paths,_=QFileDialog.getOpenFileNames(self,'Replace page with PDF or image')
        if paths:
            self.doc.insert(paths,self.index+1); self.doc.pdf.delete_page(self.index); self.refresh()
    @guarded
    def delete(self):
        self.require()
        if self.canvas.mode=='object' and self.active_object and not self.pages.hasFocus():self.delete_selected_object();return
        self.doc.delete(self.selected()); self.refresh()
    @guarded
    def duplicate(self): self.require(); self.doc.duplicate(self.selected()); self.refresh()
    @guarded
    def rotate(self,degrees): self.require(); self.doc.rotate(self.selected(),degrees); self.refresh()
    def undo(self): self.doc.undo(); self.refresh()
    def redo(self): self.doc.redo(); self.refresh()
    def save_version(self,path):
        path=Path(path)
        if path.exists():
            import hashlib,datetime
            folder=Path(self.settings.value('versions_dir',str(Path.home()/'AppData'/'Local'/'PreviewWindows'/'versions')))/hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:20]
            folder.mkdir(parents=True,exist_ok=True); stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f'); save_atomic(path.read_bytes(),folder/(stamp+path.suffix))
    @guarded
    def save(self):
        self.require(); default=str(self.doc.path or ('Untitled.pdf' if self.doc.is_pdf else 'Untitled.png'))
        path,selected_filter=QFileDialog.getSaveFileName(self,'Save As',default,'PDF (*.pdf)' if self.doc.is_pdf else 'PNG (*.png);;JPEG (*.jpg);;WebP (*.webp);;TIFF (*.tiff);;BMP (*.bmp);;PDF (*.pdf)')
        if not path: return
        if not Path(path).suffix:
            import re
            extension=re.search(r'\*\.(\w+)',selected_filter);path+='.'+(extension.group(1) if extension else ('pdf' if self.doc.is_pdf else 'png'))
        if self.doc.is_pdf:
            if Path(path).suffix.lower()!='.pdf': path+='.pdf'
            self.save_version(path); self.doc.save_pdf(path)
        elif Path(path).suffix.lower()=='.pdf': self.save_version(path); self.doc.extract(list(range(self.doc.count)),path)
        else:
            self.save_version(path); save_atomic(image_bytes(self.doc.images[self.index],Path(path).suffix,preserve_metadata=True),path)
            # A multi-image session stays dirty because only its current image was saved.
            if self.doc.count==1: self.doc.path=Path(path); self.doc.dirty=False
        self.update_title(); self.statusBar().showMessage('Saved '+path)
    @guarded
    def save_current(self):
        self.require()
        if not self.doc.path:return self.save()
        path=self.doc.path;self.save_version(path)
        if self.doc.is_pdf:self.doc.save_pdf(path)
        else:
            save_atomic(image_bytes(self.doc.images[self.index],path.suffix,preserve_metadata=True),path)
            if self.doc.count==1:self.doc.dirty=False
        self.update_title();self.statusBar().showMessage('Saved '+path.name)
    @guarded
    def extract(self):
        self.require(); path,_=QFileDialog.getSaveFileName(self,'Extract selected pages','Extracted.pdf','PDF (*.pdf)')
        if path: self.doc.extract(self.selected(),path)
    @guarded
    def contact_sheet(self):
        self.require(); path,_=QFileDialog.getSaveFileName(self,'Export contact sheet','Contact sheet.pdf','PDF (*.pdf)')
        if path: self.doc.contact_sheet(path)
    @guarded
    def export_images(self):
        self.require(); fmt,ok=QInputDialog.getItem(self,'Batch export','Format (extra formats are always visible):',['PNG','JPEG','WEBP','TIFF','BMP','GIF','ICO','PPM','PGM','PBM','TGA','JP2'],0,False)
        if not ok:return
        folder=QFileDialog.getExistingDirectory(self,'Export selected pages/images into folder')
        if not folder:return
        ext={'JPEG':'jpg','TIFF':'tiff'}.get(fmt,fmt.lower())
        for i in self.selected():
            path=Path(folder)/f'page-{i+1}-{uuid.uuid4().hex[:6]}.{ext}'; save_atomic(image_bytes(self.doc.render(i,2),'.'+ext),path)
        self.statusBar().showMessage('Exported selected pages/images to '+folder)
    @guarded
    def text_export(self):
        self.require(True); path,_=QFileDialog.getSaveFileName(self,'Extract all PDF text','Extracted.txt','Text (*.txt)')
        if path: save_atomic('\n\n'.join(p.get_text() for p in self.doc.pdf).encode('utf-8'),path)
    @guarded
    def embedded_images(self):
        self.require(True); folder=QFileDialog.getExistingDirectory(self,'Extract embedded images')
        if not folder:return
        seen=set()
        for page in self.doc.pdf:
            for im in page.get_images():
                if im[0] in seen:continue
                seen.add(im[0]); data=self.doc.pdf.extract_image(im[0]); save_atomic(data['image'],Path(folder)/f'image-{im[0]}-{uuid.uuid4().hex[:6]}.{data["ext"]}')
        self.statusBar().showMessage(f'Extracted {len(seen)} embedded image streams (soft masks may be separate).')
    @guarded
    def encrypt(self):
        self.require(True); dialog=QDialog(self); dialog.setWindowTitle('Encrypted PDF copy'); form=QFormLayout(dialog); pw=QLineEdit(); pw.setEchoMode(QLineEdit.EchoMode.Password); printing=QCheckBox(); copying=QCheckBox(); printing.setChecked(True); copying.setChecked(True); form.addRow('Open password',pw); form.addRow('Allow printing',printing); form.addRow('Allow copying',copying); buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); form.addRow(buttons); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        if dialog.exec() and pw.text():
            path,_=QFileDialog.getSaveFileName(self,'Save encrypted copy','Encrypted.pdf','PDF (*.pdf)')
            if path: self.save_version(path); self.doc.save_pdf(path,pw.text(),printing.isChecked(),copying.isChecked()); self.update_title()
    @guarded
    def cleanup(self,kind): self.require(True); self.doc.clean_pdf(**{kind:True}); self.refresh()
    def set_author(self):
        name,ok=QInputDialog.getText(self,'Annotation author','Name (leave empty for anonymous):',text=self.author)
        if ok:self.author=name; self.settings.setValue('author',name)
    @guarded
    def inspector(self):
        self.require(); data=self.doc.inspect(self.index); dialog=QDialog(self); dialog.setWindowTitle('Metadata, annotations and links'); dialog.resize(750,580); layout=QVBoxLayout(dialog); text=QTextEdit(); text.setReadOnly(True); text.setPlainText(json.dumps(data,indent=2,default=str)); layout.addWidget(text); dialog.exec()
    @guarded
    def forms(self):
        self.require(True); widgets=[(p.number,w.xref,w.field_name,w.field_value,w.field_type) for p in self.doc.pdf for w in (p.widgets() or [])]
        if not widgets: raise ValueError('No fillable fields found. Use the Text tool to write on a flat form.')
        dlg=QDialog(self); dlg.setWindowTitle('Fill PDF form'); layout=QFormLayout(dlg); fields=[]
        for page,xref,name,value,kind in widgets:
            if kind==fitz.PDF_WIDGET_TYPE_SIGNATURE: continue
            control=QCheckBox() if kind==fitz.PDF_WIDGET_TYPE_CHECKBOX else QLineEdit(str(value or ''))
            if isinstance(control,QCheckBox): control.setChecked(value not in ('Off',False,None))
            layout.addRow(f'Page {page+1}: {name}',control); fields.append((page,xref,control))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); layout.addRow(buttons); buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject)
        if dlg.exec():
            self.doc.checkpoint()
            for pn,xref,c in fields:
                p=self.doc.pdf[pn]; w=p.load_widget(xref); w.field_value=w.on_state() if isinstance(c,QCheckBox) and c.isChecked() else ('Off' if isinstance(c,QCheckBox) else c.text()); w.update()
            self.refresh()
    @guarded
    def find(self,query=None):
        self.require(True)
        if query is None:query,ok=QInputDialog.getText(self,'Find PDF text','Find:')
        else:ok=True
        if not ok or not query:return
        for offset in range(self.doc.count):
            pn=(self.index+offset)%self.doc.count; hits=self.doc.pdf[pn].search_for(query)
            if hits:
                self.navigate(pn)
                from PySide6.QtCore import QRectF
                for r in hits:
                    r=r*self.doc.pdf[pn].rotation_matrix; self.canvas.scene().addRect(QRectF(r.x0*1.5,r.y0*1.5,r.width*1.5,r.height*1.5),QPen(QColor('#ffb700'),2))
                return
        self.statusBar().showMessage('No matching text. Scanned pages need OCR, which is not included.')
    def pdf_point(self,pt): return fitz.Point(pt.x()/self.render_scale,pt.y()/self.render_scale)*self.doc.pdf[self.index].derotation_matrix
    @guarded
    def mark(self,mode,start,end,points):
        self.require(); from PIL import ImageDraw
        x0,y0,x1,y1=sorted([start.x(),end.x()])[0],sorted([start.y(),end.y()])[0],sorted([start.x(),end.x()])[1],sorted([start.y(),end.y()])[1]
        if self.doc.is_pdf:
            p=self.doc.pdf[self.index]; a,b=self.pdf_point(start),self.pdf_point(end); r=fitz.Rect(min(a.x,b.x),min(a.y,b.y),max(a.x,b.x),max(a.y,b.y))&(p.rect*p.derotation_matrix)
            color=QColor(self.ink); rgb=(color.redF(),color.greenF(),color.blueF())
            if mode=='select text':
                self.selected_text=p.get_textbox(r);self.canvas.scene().addRect(QRectF(x0,y0,x1-x0,y1-y0),QPen(Qt.PenStyle.NoPen),QColor(65,135,225,55));self.statusBar().showMessage('Text selected — press Ctrl+C to copy' if self.selected_text else 'No text here. Use PDF → OCR for a scanned page.');return
            if mode=='text':
                text,ok=QInputDialog.getText(self,'Add text','Text:')
                if not ok or not text:return
                self.doc.checkpoint(); p.insert_text(a,text,fontsize=14,color=rgb)
            elif mode=='stamp': return self.paste_at(r)
            elif mode=='redact':
                if r.is_empty:return
                self.doc.redact(self.index,r)
            elif mode=='crop':
                if r.width<4 or r.height<4:return
                self.doc.checkpoint(); offset=p.cropbox.tl; p.set_cropbox(fitz.Rect(r.tl+offset,r.br+offset))
            elif mode=='pen':
                self.doc.checkpoint(); annot=p.add_ink_annot([[self.pdf_point(pt) for pt in points]]); annot.set_colors(stroke=rgb); annot.set_info(title=self.author); annot.update()
            elif mode in ('rectangle','highlight'):
                if r.is_empty:return
                self.doc.checkpoint(); annot=p.add_highlight_annot(r) if mode=='highlight' else p.add_rect_annot(r); annot.set_info(title=self.author); annot.set_colors(stroke=rgb); annot.update()
        else:
            im=self.doc.images[self.index]; rect=(max(0,int(x0)),max(0,int(y0)),min(im.width,int(x1)),min(im.height,int(y1)))
            if mode=='redact': raise ValueError('Use redaction on a PDF. For images, crop or paint the pixels and export a new copy.')
            if mode=='stamp':return self.paste_at(rect)
            text=None
            if mode=='text':
                text,ok=QInputDialog.getText(self,'Add image text','Text:')
                if not ok or not text:return
            self.doc.checkpoint(); draw=ImageDraw.Draw(im)
            if mode=='crop':
                if rect[2]<=rect[0] or rect[3]<=rect[1]:return
                self.doc.images[self.index]=im.crop(rect)
            elif mode=='pen':draw.line([(pt.x(),pt.y()) for pt in points],fill=self.ink,width=3)
            elif mode=='rectangle':draw.rectangle(rect,outline=self.ink,width=3)
            elif mode=='highlight':
                layer=Image.new('RGBA',im.size); ImageDraw.Draw(layer).rectangle(rect,fill=(255,210,0,80)); self.doc.images[self.index]=Image.alpha_composite(im.convert('RGBA'),layer)
            elif mode=='text':draw.text((start.x(),start.y()),text,fill=self.ink,font_size=24)
        self.refresh()
    @guarded
    def follow_link(self,pt):
        if not self.doc.is_pdf:return
        point=self.pdf_point(pt)
        for l in self.doc.pdf[self.index].get_links():
            if point in l['from'] and l['kind']==fitz.LINK_GOTO: self.navigate(l['page']); return
    @guarded
    def copy(self):
        self.require()
        if self.canvas.mode=='select text' and getattr(self,'selected_text',''):QApplication.clipboard().setText(self.selected_text)
        else:QApplication.clipboard().setImage(ImageQt(self.doc.render(self.index,2)))
    @guarded
    def drop_image(self,path,point):
        self.require();im=path.copy().convert('RGBA') if isinstance(path,Image.Image) else Image.open(path).convert('RGBA');bounds=self.canvas.sceneRect();width=min(im.width,bounds.width()*.35);height=width*im.height/im.width
        if height>bounds.height()*.4:height=bounds.height()*.4;width=height*im.width/im.height
        x=max(0,min(point.x(),bounds.width()-width));y=max(0,min(point.y(),bounds.height()-height));self.doc.checkpoint()
        if self.doc.is_pdf:
            r=fitz.Rect(x/1.5,y/1.5,(x+width)/1.5,(y+height)/1.5)*self.doc.pdf[self.index].derotation_matrix;self.doc.pdf[self.index].insert_image(r,stream=png_bytes(im));self.refresh();self.canvas.set_mode('object')
            from PySide6.QtCore import QPointF
            self.pick_object(QPointF(x+width/2,y+height/2))
        else:im=im.resize((max(1,int(width)),max(1,int(height))));self.doc.images[self.index].paste(im,(int(x),int(y)),im);self.refresh()
    @guarded
    def clipboard_new(self):
        im=QApplication.clipboard().image()
        if im.isNull():raise ValueError('Copy an image to the clipboard first.')
        if not self.discard():return
        self.doc=Document(); self.doc.images=[qimage_pil(im)]; self.doc.dirty=True; self.index=0; self.refresh()
    @guarded
    def add_signature(self):
        self.require()
        from signature_ui import capture_signature
        from PySide6.QtCore import QPointF
        image=capture_signature(self)
        if image is not None:
            bounds=self.canvas.sceneRect();self.drop_image(image,QPointF(bounds.width()*.25,bounds.height()*.6));self.statusBar().showMessage('Signature placed. Drag to move or resize, then Save.')
    @guarded
    def paste(self):
        self.require(); self.canvas.set_mode('stamp'); self.statusBar().showMessage('Drag a rectangle where the clipboard image should go.')
    @guarded
    def paste_at(self,rect):
        clip=QApplication.clipboard().image()
        if clip.isNull():raise ValueError('Copy an image first, then drag its placement rectangle.')
        im=qimage_pil(clip)
        if self.doc.is_pdf:
            if rect.width<2 or rect.height<2:return
            self.doc.checkpoint(); self.doc.pdf[self.index].insert_image(rect,stream=png_bytes(im),keep_proportion=True)
        else:
            x0,y0,x1,y1=[int(v) for v in rect]
            if x1<=x0 or y1<=y0:return
            self.doc.checkpoint(); im.thumbnail((x1-x0,y1-y0)); self.doc.images[self.index].paste(im,(x0,y0),im)
        self.refresh()
    def ink_color(self):
        c=QColorDialog.getColor(QColor(self.ink),self)
        if c.isValid():self.ink=c.name()
    def alpha_tolerance(self):
        value,ok=QInputDialog.getInt(self,'Instant Alpha','Color tolerance:',self.tolerance,0,441)
        if ok:self.tolerance=value; self.canvas.set_mode('alpha')
    @guarded
    def alpha(self,point):
        self.require(False); im=self.doc.images[self.index]; x,y=int(point.x()),int(point.y())
        if 0<=x<im.width and 0<=y<im.height:self.doc.checkpoint(); self.doc.images[self.index]=instant_alpha(im,x,y,self.tolerance); self.refresh()
    @guarded
    def remove_background(self,copy=False):
        self.require(False)
        if self.worker and self.worker.isRunning():raise ValueError('A background job is already running.')
        source=self.doc.images[self.index].copy(); index=self.index; document=self.doc
        def work():
            from rembg import remove,new_session
            return remove(source,session=new_session('u2netp'))
        self.run_job(work,lambda result:self.cutout_done(document,index,result,copy),'Removing background locally… First use downloads a small model.')
    def cutout_done(self,document,index,result,copy):
        if copy:QApplication.clipboard().setImage(ImageQt(result))
        elif self.doc is document:self.doc.checkpoint(); self.doc.images[index]=result; self.refresh()
    def run_job(self,job,done,label):
        self.progress=QProgressDialog(label,None,0,0,self); self.progress.setWindowModality(Qt.WindowModality.ApplicationModal); self.progress.show()
        self.worker=Worker(job,self); self.worker.result.connect(done); self.worker.failed.connect(lambda message:QMessageBox.warning(self,'Background operation failed',message)); self.worker.finished.connect(self.progress.close); self.worker.start()
    @guarded
    def resize_images(self):
        self.require(False); dlg=QDialog(self); dlg.setWindowTitle('Resize selected images'); form=QFormLayout(dlg); units=QComboBox(); units.addItems(['Pixels (fit within box)','Percent']); width=QSpinBox(); height=QSpinBox(); width.setRange(1,30000); height.setRange(1,30000); width.setValue(self.doc.images[self.index].width); height.setValue(self.doc.images[self.index].height); estimate=QLabel(); form.addRow('Units',units); form.addRow('Width / percentage',width); form.addRow('Height (pixels only)',height); form.addRow('Estimated PNG size',estimate)
        def estimate_size():
            im=self.doc.images[self.index].copy(); size=(max(1,int(im.width*width.value()/100)),max(1,int(im.height*width.value()/100))) if units.currentIndex()==1 else (width.value(),height.value()); im.thumbnail(size); estimate.setText(f'{len(png_bytes(im))/1024:.1f} KB (actual export may differ)')
        for c in [width,height]:c.valueChanged.connect(estimate_size)
        units.currentIndexChanged.connect(lambda i:(width.setValue(100 if i else self.doc.images[self.index].width),estimate_size())); estimate_size(); buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); form.addRow(buttons); buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject)
        if dlg.exec():
            self.doc.checkpoint()
            for i in self.selected():
                im=self.doc.images[i]; size=(max(1,int(im.width*width.value()/100)),max(1,int(im.height*width.value()/100))) if units.currentIndex()==1 else (width.value(),height.value()); self.doc.images[i]=ImageOps.contain(im,size,Image.Resampling.LANCZOS)
            self.refresh()
    @guarded
    def adjust_images(self):
        self.require(False); dlg=QDialog(self); dlg.setWindowTitle('Adjust selected images'); form=QFormLayout(dlg); fields=[]
        for label in ['Exposure','Contrast','Saturation','Sharpness']:
            value=QDoubleSpinBox(); value.setRange(0,4); value.setSingleStep(.1); value.setValue(1); form.addRow(label,value); fields.append(value)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); form.addRow(buttons); buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject)
        if dlg.exec():
            self.doc.checkpoint()
            for i in self.selected():self.doc.images[i]=adjust(self.doc.images[i],*[f.value() for f in fields])
            self.refresh()
    @guarded
    def free_rotate(self):
        self.require(False); angle,ok=QInputDialog.getDouble(self,'Rotate images','Clockwise degrees:',0,-360,360,1)
        if ok:
            self.doc.checkpoint()
            for i in self.selected(): self.doc.images[i]=self.doc.images[i].rotate(-angle,resample=Image.Resampling.BICUBIC,expand=True)
            self.refresh()
    @guarded
    def strip_gps(self):
        self.require(False); self.doc.checkpoint()
        for i in self.selected():self.doc.images[i]=remove_gps(self.doc.images[i])
        self.refresh()
    @guarded
    def strip_metadata(self):
        self.require(False); self.doc.checkpoint()
        for i in self.selected():self.doc.images[i]=Image.frombytes('RGBA',self.doc.images[i].size,self.doc.images[i].convert('RGBA').tobytes())
        self.refresh()
    def toggle_overview(self):
        grid=self.pages.viewMode()==QListWidget.ViewMode.ListMode; self.pages.setViewMode(QListWidget.ViewMode.IconMode if grid else QListWidget.ViewMode.ListMode); self.pages.setMinimumWidth(440 if grid else 180)
    def toggle_dark(self):self.dark=not self.dark; self.settings.setValue('dark',self.dark); self.show_page()
    def canvas_color(self):
        c=QColorDialog.getColor(parent=self)
        if c.isValid():self.canvas.setBackgroundBrush(c); self.settings.setValue('canvas',c.name())
    def customize(self):
        dlg=QDialog(self); dlg.setWindowTitle('Customize document toolbar'); layout=QVBoxLayout(dlg); checks=[]
        for a in self.main_toolbar.actions():
            widget=self.main_toolbar.widgetForAction(a);label=a.text() or (widget.toolTip() if widget else '')
            if not label:continue
            c=QCheckBox(label); c.setChecked(a.isVisible()); layout.addWidget(c); checks.append((a,c))
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); layout.addWidget(buttons); buttons.accepted.connect(dlg.accept); buttons.rejected.connect(dlg.reject)
        if dlg.exec():
            for a,c in checks:a.setVisible(c.isChecked())
            self.settings.setValue('hidden_tools',[c.text() for a,c in checks if not c.isChecked()])
    @guarded
    def versions(self):
        self.require()
        if not self.doc.path:raise ValueError('Save your document first. Versions are captured when an existing file is overwritten in this app.')
        import hashlib
        folder=Path(self.settings.value('versions_dir',str(Path.home()/'AppData'/'Local'/'PreviewWindows'/'versions')))/hashlib.sha256(str(self.doc.path.resolve()).encode()).hexdigest()[:20]
        versions=sorted(folder.glob('*'),reverse=True)
        if not versions:raise ValueError('No saved versions yet. Earlier copies are retained when this app overwrites a file.')
        name,ok=QInputDialog.getItem(self,'Restore version','Saved copy:',[v.name for v in versions],0,False)
        if ok:
            original=self.doc.path
            if self.load([str(folder/name)]):self.doc.path=original; self.doc.dirty=True; self.update_title()
    @guarded
    def reveal(self):
        if self.doc.path:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.doc.path.parent)))
    @guarded
    def print_doc(self):
        self.require(); printer=QPrinter(QPrinter.PrinterMode.HighResolution); dialog=QPrintDialog(printer,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        from PySide6.QtGui import QPainter
        painter=QPainter(printer)
        try:
            first=max(0,printer.fromPage()-1); last=printer.toPage() or self.doc.count
            for number,i in enumerate(range(first,min(last,self.doc.count))):
                if number:printer.newPage()
                page=self.doc.render(i,2); pix=pil_pixmap(page); area=printer.pageLayout().paintRectPixels(printer.resolution()); size=pix.size(); size.scale(area.size(),Qt.AspectRatioMode.KeepAspectRatio); painter.drawPixmap(area.x()+(area.width()-size.width())//2,area.y()+(area.height()-size.height())//2,size.width(),size.height(),pix)
        finally:painter.end()
    def help(self):
        QMessageBox.information(self,'Preview for Windows','Native local PDF and image workbench.\n\nCtrl+O: open • Ctrl+E: extract selected pages • Ctrl+V: place an image • Ctrl+Z: undo\n\nCtrl/Shift-click thumbnails to select multiple pages. Drag thumbnails to reorder. Drop PDFs/images to insert after the current page. Redaction removes underlying content on export. Originals stay untouched until Save As.\n\nVideo feature mapping, supported formats, licensing and limitations are in README.md and FEATURES.md alongside the code.')
    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():event.ignore(); self.statusBar().showMessage('Wait for the background job to finish.'); return
        if self.discard():event.accept()
        else:event.ignore()

def main():
    app=QApplication(sys.argv); app.setApplicationName('Preview for Windows'); window=Window(); window.show()
    if len(sys.argv)>1:window.load(sys.argv[1:])
    return app.exec()
if __name__=='__main__':sys.exit(main())
