"""Native dialogs for OCR, object editing, scan tools and document organization."""
from pathlib import Path
import json
import fitz
from PySide6.QtCore import Qt,QRectF
from PySide6.QtGui import QColor,QPen
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QListWidget,QListWidgetItem,QTextEdit,QLabel,QPushButton,QDialogButtonBox,QDoubleSpinBox,QSpinBox,QLineEdit,QCheckBox,QComboBox,QFileDialog,QMessageBox,QInputDialog)
import pdf_tools as tools
from engine import save_atomic

def dialog_buttons(dialog,layout,label='Apply'):
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel); buttons.button(QDialogButtonBox.StandardButton.Ok).setText(label); layout.addWidget(buttons) if isinstance(layout,QVBoxLayout) else layout.addRow(buttons); buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)

class PdfToolsMixin:
    def add_pdf_tools(self,menu):
        menu.addSeparator()
        for title,callback in [('OCR selected pages…',lambda:self.ocr_pages(False)),('OCR whole document…',lambda:self.ocr_pages(True)),('Edit page objects…',self.start_object_edit),('Object properties…',self.edit_page_objects),('Search and redact…',self.search_redact),('Review blank pages…',self.review_blanks),('Clean selected scans…',self.scan_cleanup),('Compress to target size…',self.compress_export),('Compare with another PDF…',self.compare_dialog),('Bookmarks…',self.bookmarks_dialog),('Page labels…',self.page_labels_dialog),('Headers, footers and numbering…',self.numbering_dialog)]:
            self.action(menu,title,self.safe_pdf_action(callback))
    def safe_pdf_action(self,callback):
        def run():
            try:
                self.require(True)
                if self.worker and self.worker.isRunning():raise ValueError('Wait for the current background operation to finish.')
                callback()
            except Exception as e:QMessageBox.warning(self,'PDF operation failed',str(e))
        return run
    def commit_pdf(self,data):
        self.doc.checkpoint(); self.doc.restore((data,True)); self.refresh()
    def pdf_data(self):return self.doc.pdf.tobytes(garbage=0,deflate=True)
    def start_object_edit(self):
        self.require(True);self.canvas.set_mode('object');self.statusBar().showMessage('Click an object, drag to move, or drag its corner to resize. Double-click for properties. Delete removes the selected object.')
    def pick_object(self,point):
        if not self.doc.is_pdf:return None
        p=self.doc.pdf[self.index];mapped=self.pdf_point(point);entries=[obj for obj in tools.objects(p) if not obj.get('hidden') and mapped in fitz.Rect(obj['rect'])]
        if not entries:return None
        obj=min(entries,key=lambda o:fitz.Rect(o['rect']).get_area());self.draw_object_selection(obj);return self.active_object
    def draw_object_selection(self,obj):
        if self.active_object:
            self.canvas.scene().removeItem(self.object_outline);self.canvas.scene().removeItem(self.object_grip)
        rect=fitz.Rect(obj['rect'])*self.doc.pdf[self.index].rotation_matrix;scene=QRectF(rect.x0*1.5,rect.y0*1.5,rect.width*1.5,rect.height*1.5);self.active_object={'object':obj,'scene_rect':scene}
        self.object_outline=self.canvas.scene().addRect(scene,QPen(QColor('#297ddd'),2));self.object_grip=self.canvas.scene().addRect(QRectF(scene.right()-5,scene.bottom()-5,10,10),QPen(QColor('#297ddd')),QColor('white'))
    def transform_selected_object(self,scene):
        if not self.active_object:return
        obj=self.active_object['object'];target=fitz.Rect(scene.left()/1.5,scene.top()/1.5,scene.right()/1.5,scene.bottom()/1.5)*self.doc.pdf[self.index].derotation_matrix
        try:
            data=tools.edit_object(self.pdf_data(),self.index,obj,tuple(target));self.commit_pdf(data)
            candidates=[o for o in tools.objects(self.doc.pdf[self.index]) if o['kind']==obj['kind']]
            if candidates:self.draw_object_selection(min(candidates,key=lambda o:abs(o['rect'][0]-target.x0)+abs(o['rect'][1]-target.y0)))
        except Exception as e:self.show_page();QMessageBox.warning(self,'Cannot move this object',str(e))
    def delete_selected_object(self):
        if self.active_object:
            try:self.commit_pdf(tools.edit_object(self.pdf_data(),self.index,self.active_object['object'],delete=True))
            except Exception as e:QMessageBox.warning(self,'Cannot remove this object',str(e))
    def ocr_pages(self,all_pages):
        if self.worker and self.worker.isRunning():raise ValueError('Wait for the current job to finish.')
        indices=list(range(self.doc.count)) if all_pages else self.selected(); source=self.pdf_data(); document=self.doc
        def done(result):
            if self.doc is not document:return
            data,summary=result
            if summary['recognized_lines']:self.commit_pdf(data)
            self.statusBar().showMessage(f'OCR: {summary["recognized_lines"]} recognized lines; {summary["skipped_text_pages"]} pages with existing text skipped. Review recognition before sharing.')
        self.run_job(lambda:tools.ocr_pdf(source,indices),done,'Recognizing scanned text locally…')
    def edit_page_objects(self):
        entries=[obj for obj in tools.objects(self.doc.pdf[self.index]) if not obj.get('hidden')]
        if not entries:raise ValueError('No editable text spans or direct images on this page. Run OCR on a scan to add text, or use image placement.')
        dlg=QDialog(self); dlg.setWindowTitle('Edit text or image object'); dlg.resize(720,520); layout=QVBoxLayout(dlg); chooser=QListWidget()
        for obj in entries:chooser.addItem(obj['kind'].title()+': '+obj['text'][:100])
        layout.addWidget(chooser); form=QFormLayout(); layout.addLayout(form); fields=[]
        for title in ['X','Y','Width','Height']:
            spin=QDoubleSpinBox(); spin.setRange(0,30000); spin.setDecimals(2); form.addRow(title+' (PDF points)',spin); fields.append(spin)
        text=QLineEdit(); text.setObjectName('replacement_text'); form.addRow('Replacement text',text); replace_button=QPushButton('Choose replacement image…'); replacement=QLabel('Keep original image'); replacement_path=[None]; form.addRow(replace_button,replacement); delete=QCheckBox('Delete this object'); form.addRow(delete)
        notice=QLabel('Text replacement uses a standard font and does not reflow paragraphs. Complex or repeated image placements are refused. Changes support Undo.'); notice.setWordWrap(True); layout.addWidget(notice)
        def select(row):
            if row<0:return
            obj=entries[row]; r=fitz.Rect(obj['rect'])
            for field,value in zip(fields,[r.x0,r.y0,r.width,r.height]):field.setValue(value)
            text.setText(obj['text'] if obj['kind']=='text' else ''); text.setEnabled(obj['kind']=='text'); replace_button.setEnabled(obj['kind']=='image'); replacement_path[0]=None; replacement.setText('Keep original image'); self.show_page(); rr=r*self.doc.pdf[self.index].rotation_matrix; self.canvas.scene().addRect(QRectF(rr.x0*1.5,rr.y0*1.5,rr.width*1.5,rr.height*1.5),QPen(QColor('#f59e0b'),2))
        def choose_replacement():
            path,_=QFileDialog.getOpenFileName(dlg,'Replacement image','','Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)')
            if path:replacement_path[0]=path; replacement.setText(Path(path).name)
        selected=self.active_object['object'] if self.active_object else None;selected_row=next((i for i,obj in enumerate(entries) if selected and obj['rect']==selected['rect']),0)
        chooser.currentRowChanged.connect(select); replace_button.clicked.connect(choose_replacement); chooser.setCurrentRow(selected_row); dialog_buttons(dlg,layout)
        try:
            if dlg.exec():
                x,y,w,h=[field.value() for field in fields]; data=tools.edit_object(self.pdf_data(),self.index,entries[chooser.currentRow()],(x,y,x+w,y+h),text.text(),replacement_path[0],delete.isChecked()); self.commit_pdf(data)
        finally:self.show_page()
    def search_redact(self):
        phrase,ok=QInputDialog.getText(self,'Search and redact','Exact phrase to find (run OCR first for scanned pages):')
        if not ok or not phrase.strip():return
        matches=tools.search_matches(self.doc.pdf,phrase)
        if not matches:raise ValueError('No matching text found. Scanned pages may need OCR first.')
        dlg=QDialog(self); dlg.setWindowTitle('Review redactions'); dlg.resize(650,480); layout=QVBoxLayout(dlg); layout.addWidget(QLabel('Select matches to remove permanently from the exported PDF.')); items=QListWidget(); layout.addWidget(items)
        for hit in matches:
            r=fitz.Rect(hit['rect']); item=QListWidgetItem(f'Page {hit["page"]+1}: {phrase} — {r.x0:.0f}, {r.y0:.0f}'); item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable); item.setCheckState(Qt.CheckState.Checked); items.addItem(item)
        def preview(row):
            if row<0:return
            hit=matches[row]; self.navigate(hit['page']); r=fitz.Rect(hit['rect'])*self.doc.pdf[hit['page']].rotation_matrix; self.canvas.scene().addRect(QRectF(r.x0*1.5,r.y0*1.5,r.width*1.5,r.height*1.5),QPen(QColor('#dc2626'),2))
        items.currentRowChanged.connect(preview); items.setCurrentRow(0); dialog_buttons(dlg,layout,'Apply selected redactions')
        try:
            if dlg.exec():
                selected=[hit for i,hit in enumerate(matches) if items.item(i).checkState()==Qt.CheckState.Checked]
                if selected:self.commit_pdf(tools.redact_matches(self.pdf_data(),selected))
        finally:self.show_page()
    def review_blanks(self):
        indices=tools.blank_candidates(self.doc.pdf,list(range(self.doc.count)))
        if not indices:raise ValueError('No likely blank pages found.')
        dlg=QDialog(self); dlg.setWindowTitle('Review likely blank pages'); layout=QVBoxLayout(dlg); layout.addWidget(QLabel('Faint marks may be missed. Check each page before removing it.')); items=QListWidget(); layout.addWidget(items)
        for index in indices:
            item=QListWidgetItem(f'Page {index+1}'); item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable); item.setCheckState(Qt.CheckState.Unchecked); items.addItem(item)
        items.currentRowChanged.connect(lambda row:self.navigate(indices[row]) if row>=0 else None); dialog_buttons(dlg,layout,'Remove checked pages')
        if dlg.exec():
            selected=[index for row,index in enumerate(indices) if items.item(row).checkState()==Qt.CheckState.Checked]
            if selected:self.doc.delete(selected);self.refresh()
    def scan_cleanup(self):
        dlg=QDialog(self); dlg.setWindowTitle('Clean selected scanned pages'); form=QFormLayout(dlg); deskew=QCheckBox(); deskew.setChecked(True); gray=QCheckBox(); gray.setChecked(True); contrast=QDoubleSpinBox(); contrast.setRange(.5,3); contrast.setValue(1.3); contrast.setSingleStep(.1); dpi=QSpinBox(); dpi.setRange(72,300); dpi.setValue(150)
        form.addRow('Straighten (up to ±5°)',deskew); form.addRow('Grayscale',gray); form.addRow('Contrast',contrast); form.addRow('Resolution DPI',dpi); note=QLabel('Selected pages are flattened into cleaned images. Existing text layers are removed; run OCR again afterward. Pages with forms, annotations or links are refused.'); note.setWordWrap(True); form.addRow(note); dialog_buttons(dlg,form)
        if dlg.exec():
            source=self.pdf_data(); indices=self.selected(); document=self.doc; options=(deskew.isChecked(),contrast.value(),gray.isChecked(),dpi.value())
            self.run_job(lambda:tools.clean_scans(source,indices,*options),lambda data:self.commit_pdf(data) if self.doc is document else None,'Cleaning selected scans…')
    def compress_export(self):
        target,ok=QInputDialog.getDouble(self,'Compress PDF copy','Target size in MB. If needed, pages become JPEG images with an approximate searchable text layer. Forms/links/annotations are preserved using lossless compression only.',2,.05,1000,2)
        if not ok:return
        path,_=QFileDialog.getSaveFileName(self,'Export compressed PDF','Compressed.pdf','PDF (*.pdf)')
        if not path:return
        source=self.pdf_data()
        def done(result):
            data,info=result; self.save_version(path); save_atomic(data,path); QMessageBox.information(self,'Compression result',f'{len(data)/1024/1024:.2f} MB\nTarget {"met" if info["target_met"] else "not reached"}.\n'+('Pages rasterized; review readability and text selection.' if info['rasterized'] else 'Lossless PDF export.'))
        self.run_job(lambda:tools.compress_pdf(source,int(target*1024*1024)),done,'Finding a smaller PDF export…')
    def compare_dialog(self):
        path,_=QFileDialog.getOpenFileName(self,'Compare current document with PDF','','PDF (*.pdf)')
        if not path:return
        source=self.pdf_data(); other=Path(path).read_bytes()
        with tools.open_copy(other) as d:
            if d.needs_pass:raise ValueError('Open and export an unlocked copy of the comparison PDF first.')
        changes=tools.compare_pdfs(source,other); dlg=QDialog(self); dlg.setWindowTitle('PDF comparison — current vs '+Path(path).name); dlg.resize(1100,800); layout=QVBoxLayout(dlg); items=QListWidget(); items.setMaximumHeight(140); layout.addWidget(items)
        if not changes:items.addItem('No text or rendered appearance differences found.')
        for change in changes:items.addItem(f'Page {change["page"]}: {change["status"]}')
        images=QHBoxLayout(); left=QLabel(); right=QLabel(); images.addWidget(left); images.addWidget(right); layout.addLayout(images); report=QTextEdit(); report.setReadOnly(True); report.setMaximumHeight(190); layout.addWidget(report)
        def select(row):
            if row<0 or not changes:return
            from app import pil_pixmap
            from PIL import Image
            change=changes[row]; pn=change['page']-1; report.setPlainText(change['diff'] or change['status'])
            with tools.open_copy(source) as a,tools.open_copy(other) as b:
                for doc,label in [(a,left),(b,right)]:
                    if pn>=len(doc):label.clear();label.setText('Page absent');continue
                    pix=doc[pn].get_pixmap(matrix=fitz.Matrix(1,1),alpha=False); im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples); label.setPixmap(pil_pixmap(im).scaled(480,430,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        items.currentRowChanged.connect(select); items.setCurrentRow(0); export=QPushButton('Export comparison report…'); layout.addWidget(export)
        def save_report():
            output,_=QFileDialog.getSaveFileName(dlg,'Export report','Comparison.txt','Text (*.txt)')
            if output:save_atomic(('Compared by page position; additions/reorders may shift subsequent pages.\n\n'+'\n\n'.join(f'Page {c["page"]}: {c["status"]}\n{c["diff"]}' for c in changes)).encode(),output)
        export.clicked.connect(save_report); dlg.exec()
    def bookmarks_dialog(self):
        dlg=QDialog(self); dlg.setWindowTitle('Bookmarks'); dlg.resize(650,450); layout=QVBoxLayout(dlg); layout.addWidget(QLabel('One bookmark per line: level | title | page number. Nested levels start at 1.')); text=QTextEdit(); text.setPlainText('\n'.join(f'{level} | {title} | {page}' for level,title,page in self.doc.pdf.get_toc())); layout.addWidget(text); add=QPushButton('Add current page'); layout.addWidget(add); add.clicked.connect(lambda:text.append(f'1 | Page {self.index+1} | {self.index+1}')); go=QPushButton('Go to bookmark on current line'); layout.addWidget(go)
        def jump():
            try:self.navigate(int(text.textCursor().block().text().rsplit('|',1)[1].strip())-1)
            except (ValueError,IndexError):pass
        go.clicked.connect(jump); dialog_buttons(dlg,layout)
        if dlg.exec():
            toc=[]
            for line in text.toPlainText().splitlines():
                if not line.strip():continue
                level,title,page=line.split('|',2); page=int(page.strip())
                if not 1<=page<=self.doc.count:raise ValueError('Bookmark page number is outside the document.')
                toc.append([int(level.strip()),title.strip(),page])
            self.commit_pdf(tools.set_bookmarks(self.pdf_data(),toc))
    def page_labels_dialog(self):
        dlg=QDialog(self); dlg.setWindowTitle('Page labels'); form=QFormLayout(dlg); prefix=QLineEdit(); style=QComboBox(); style.addItems(['Decimal','Roman lowercase','Roman uppercase','Letters lowercase','Letters uppercase']); first=QSpinBox(); first.setRange(1,100000); first.setValue(1); form.addRow('Prefix',prefix); form.addRow('Number style',style); form.addRow('First number',first); form.addRow(QLabel('Applies to the whole document. Page navigation still uses physical page numbers.')); dialog_buttons(dlg,form)
        if dlg.exec():
            with tools.open_copy(self.pdf_data()) as d:d.set_page_labels([{'startpage':0,'prefix':prefix.text(),'style':['D','r','R','a','A'][style.currentIndex()],'firstpagenum':first.value()}]);self.commit_pdf(tools.encoded(d))
    def numbering_dialog(self):
        dlg=QDialog(self); dlg.setWindowTitle('Headers, footers and page numbers'); form=QFormLayout(dlg); header=QLineEdit(); footer=QLineEdit(); numbers=QCheckBox(); numbers.setChecked(True); first=QSpinBox(); first.setRange(1,100000); first.setValue(1); form.addRow('Header',header); form.addRow('Footer',footer); form.addRow('Add page numbers',numbers); form.addRow('Starting number',first); form.addRow(QLabel('Applies to selected pages; added text may overlap existing content.')); dialog_buttons(dlg,form)
        if dlg.exec():self.commit_pdf(tools.decorate(self.pdf_data(),self.selected(),header.text(),footer.text(),numbers.isChecked(),first.value()))
