"""Preview-style chrome with original vector icons and a thumbnail delegate."""
from PySide6.QtCore import Qt,QSize,QRectF,QByteArray,QMimeData,QUrl
from PySide6.QtGui import QIcon,QPixmap,QPainter,QColor,QPen,QFont,QDrag
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget,QLabel,QVBoxLayout,QSizePolicy,QToolButton,QMenu,QLineEdit,QStyledItemDelegate,QStyle

PATHS={
 'sidebar':'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M5.5 8h1M5.5 12h1M5.5 16h1"/>',
 'back':'<path d="m14 6-6 6 6 6"/>','forward':'<path d="m10 6 6 6-6 6"/>',
 'zoom_in':'<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6M7 10h6M10 7v6"/>',
 'zoom_out':'<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6M7 10h6"/>',
 'share':'<path d="M7 8H4v13h16V8h-3M12 15V3m-4 4 4-4 4 4"/>',
 'markup':'<circle cx="12" cy="12" r="9"/><path d="m8 16 2-6 4-4 3 3-4 4-5 3m2-6 3 3"/>',
 'rotate':'<path d="M7 6a8 8 0 1 1-2 10M3 4v5h5"/><rect x="9" y="9" width="7" height="9" rx="1"/>',
 'search':'<circle cx="10" cy="10" r="6"/><path d="m15 15 6 6"/>',
 'select':'<path d="M4 3v16l4-4 3 6 3-2-3-6h6L4 3Z"/>',
 'text':'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M8 8h8M12 8v9M9 17h6"/>',
 'pen':'<path d="m4 17 1 4 4-1L20 9l-5-5L4 17Zm9-11 5 5M4 17l5 3"/>',
 'rectangle':'<rect x="4" y="5" width="16" height="14" rx="1"/>',
 'highlight':'<path d="m5 14 7-10 6 4-7 10-6-4Zm0 0-2 5h7M2 22h20"/>',
 'redact':'<rect x="3" y="6" width="18" height="12" rx="2"/><path d="m8 9 8 6m0-6-8 6"/>',
 'crop':'<path d="M7 2v15h15M2 7h15v15"/>',
 'stamp':'<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8" cy="9" r="1.5"/><path d="m4 17 5-5 4 4 3-7 5 8"/>',
 'alpha':'<path d="m4 20 13-13 3 3L7 23M3 3l2 2m8-3v3m9-1-2 2M2 12h3"/>',
 'info':'<circle cx="12" cy="12" r="9"/><path d="M12 10v7M11.9 6.5h.2"/>',
 'document':'<path d="M6 2h8l4 4v16H6V2Zm8 0v5h4M9 11h6M9 15h6"/>'}

def icon(name):
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><g fill="none" stroke="#454545" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">{PATHS[name]}</g></svg>'
    renderer=QSvgRenderer(QByteArray(svg.encode()));pix=QPixmap(48,48);pix.fill(Qt.GlobalColor.transparent);p=QPainter(pix);renderer.render(p);p.end();return QIcon(pix)

class ThumbnailDelegate(QStyledItemDelegate):
    def sizeHint(self,option,index):return QSize(170,184)
    def paint(self,painter,option,index):
        painter.save();painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center=option.rect.center().x();top=option.rect.top()+10;card=QRectF(center-53,top,106,146)
        painter.setPen(Qt.PenStyle.NoPen);painter.setBrush(QColor(0,0,0,22));painter.drawRoundedRect(card.translated(0,2),1,1)
        image=index.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(image,QIcon):
            pix=image.pixmap(QSize(102,142));size=pix.size();size.scale(102,142,Qt.AspectRatioMode.KeepAspectRatio);page=QRectF(center-size.width()/2,top+(146-size.height())/2,size.width(),size.height());painter.fillRect(page,QColor('white'));painter.drawPixmap(page.toRect(),pix)
            card=page.adjusted(-3,-3,3,3)
        selected=bool(option.state&QStyle.StateFlag.State_Selected)
        painter.setBrush(Qt.BrushStyle.NoBrush);painter.setPen(QPen(QColor('#3b82e6' if selected else '#c4c4c4'),3 if selected else .7));painter.drawRoundedRect(card,2,2)
        font=QFont(option.font);font.setPointSize(9);painter.setFont(font);painter.setPen(QColor('#2463bd' if selected else '#656565'));painter.drawText(QRectF(option.rect.x(),top+151,option.rect.width(),21),Qt.AlignmentFlag.AlignCenter,str(index.data(Qt.ItemDataRole.DisplayRole)));painter.restore()

def button(toolbar,name,label,callback,checkable=False):
    b=QToolButton();b.setIcon(icon(name));b.setToolTip(label);b.setAccessibleName(label);b.setIconSize(QSize(20,20));b.setCheckable(checkable);b.clicked.connect(callback);toolbar.addWidget(b);return b

def spacer(toolbar):
    widget=QWidget();widget.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Preferred);toolbar.addWidget(widget)

class DocumentIcon(QLabel):
    def __init__(self,owner):super().__init__();self.owner=owner;self.setToolTip('Drag the saved document to Explorer or another app')
    def mouseMoveEvent(self,event):
        path=self.owner.doc.path
        if event.buttons()&Qt.MouseButton.LeftButton and path and path.exists() and not self.owner.doc.dirty:
            drag=QDrag(self);data=QMimeData();data.setUrls([QUrl.fromLocalFile(str(path.resolve()))]);drag.setMimeData(data);drag.exec(Qt.DropAction.CopyAction)

def install(owner,main,markup):
    for a in list(main.actions()):main.removeAction(a)
    for a in list(markup.actions()):markup.removeAction(a)
    main.setMovable(False);main.setFloatable(False);main.setIconSize(QSize(20,20));main.setObjectName('previewToolbar');owner.markup_toolbar=markup
    owner.removeToolBar(markup);owner.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea);owner.addToolBar(Qt.ToolBarArea.TopToolBarArea,markup);markup.setObjectName('previewMarkup');markup.setMovable(False);markup.hide()
    sidebar=button(main,'sidebar','Show or hide thumbnails',lambda:owner.pages.setVisible(not owner.pages.isVisible()),True);sidebar.setChecked(True);owner.sidebar_button=sidebar
    main.addSeparator()
    for name,delta in [('back',-1),('forward',1)]:
        b=button(main,name,'Previous page' if delta<0 else 'Next page',lambda checked=False,d=delta:owner.navigate(owner.index+d));b.setAutoRepeat(True);b.setAutoRepeatDelay(350);b.setAutoRepeatInterval(80)
    owner.page_number.setPrefix('');owner.page_number.setFixedWidth(57);owner.page_number.setAlignment(Qt.AlignmentFlag.AlignCenter);owner.page_number.setToolTip('Jump to page');main.addWidget(owner.page_number);owner.page_number.show()
    main.addSeparator();doc_icon=DocumentIcon(owner);doc_icon.setPixmap(icon('document').pixmap(19,19));doc_icon.setContentsMargins(6,0,0,0);main.addWidget(doc_icon)
    title=QWidget();title.setObjectName('documentIdentity');layout=QVBoxLayout(title);layout.setContentsMargins(5,1,8,1);layout.setSpacing(1);owner.document_title=QLabel('Preview');owner.document_title.setObjectName('documentName');owner.document_subtitle=QLabel('No document open');owner.document_subtitle.setObjectName('documentSubtitle');layout.addWidget(owner.document_title);layout.addWidget(owner.document_subtitle);main.addWidget(title)
    spacer(main)
    button(main,'zoom_out','Zoom out',lambda:owner.canvas.scale(1/1.2,1/1.2));button(main,'zoom_in','Zoom in',lambda:owner.canvas.scale(1.2,1.2));main.addSeparator()
    share=button(main,'share','Export and share',lambda:None);menu=QMenu(share)
    for label in ['Save','Save as…','Export selected pages…','Export images / render pages…','Reveal saved file']:menu.addAction(owner.actions[label])
    share.setMenu(menu);share.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    button(main,'rotate','Rotate selected pages',lambda:owner.rotate(90));toggle=button(main,'markup','Show markup toolbar',lambda checked:markup.setVisible(checked),True);owner.markup_button=toggle;markup.visibilityChanged.connect(toggle.setChecked)
    more=button(main,'info','Document tools',lambda:None);tools=QMenu(more)
    for label in ['Inspector','OCR whole document…','Edit page objects…','Search and redact…','Compare with another PDF…','Bookmarks…','Compress to target size…']:tools.addAction(owner.actions[label])
    more.setMenu(tools);more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup);main.addSeparator()
    owner.search_box=QLineEdit();owner.search_box.setPlaceholderText('Search');owner.search_box.setFixedWidth(150);owner.search_box.setClearButtonEnabled(True);owner.search_box.addAction(icon('search'),QLineEdit.ActionPosition.LeadingPosition);owner.search_box.returnPressed.connect(lambda:owner.find(owner.search_box.text()));main.addWidget(owner.search_box)
    modes=[('view','select','Move / browse'),('object','select','Edit objects'),('select text','text','Select text'),('pen','pen','Sketch'),('rectangle','rectangle','Shapes'),('text','text','Add text'),('highlight','highlight','Highlight'),('redact','redact','Redact'),('crop','crop','Crop'),('stamp','stamp','Place image'),('alpha','alpha','Instant Alpha')]
    owner.mode_buttons={}
    for mode,name,label in modes:
        b=button(markup,name,label,lambda checked=False,m=mode:owner.canvas.set_mode(m),True);owner.mode_buttons[mode]=b
    markup.addSeparator();color=QToolButton();color.setText('●');color.setToolTip('Stroke color');color.setAccessibleName('Stroke color');color.clicked.connect(owner.ink_color);color.setStyleSheet('color:#2563eb;font-size:21px;');markup.addWidget(color);spacer(markup)
    owner.pages.setItemDelegate(ThumbnailDelegate(owner.pages));owner.pages.setSpacing(0);owner.pages.setMinimumWidth(150);owner.pages.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    owner.statusBar().setSizeGripEnabled(False)
    for action in main.actions():
        widget=main.widgetForAction(action)
        if widget and widget.toolTip() in owner.settings.value('hidden_tools',[]):action.setVisible(False)

STYLE='''
QMainWindow,QDialog {background:#f1f1f1;color:#292929;}
QMenuBar {background:#f3f3f3;color:#333;padding:1px;border-bottom:1px solid #d2d2d2;}
QMenuBar::item {padding:4px 9px;} QMenuBar::item:selected {background:#dfdfdf;border-radius:4px;}
QMenu {background:#fafafa;color:#292929;border:1px solid #c7c7c7;padding:5px;}
QMenu::item {padding:6px 24px 6px 12px;} QMenu::item:selected {background:#2978d5;color:white;border-radius:3px;}
QToolBar#previewToolbar {background:#eeeeee;border:0;border-bottom:1px solid #cecece;padding:7px 10px;spacing:4px;}
QToolBar#previewMarkup {background:#f6f6f6;border:0;border-bottom:1px solid #d1d1d1;padding:5px 10px;spacing:5px;}
QToolBar QToolButton {background:transparent;border:1px solid transparent;border-radius:5px;padding:5px;min-width:23px;min-height:22px;}
QToolBar QToolButton:hover {background:#dddddd;} QToolBar QToolButton:checked {background:#d6d6d6;border-color:#b8b8b8;}
QToolBar QToolButton::menu-indicator {image:none;}
QToolBar::separator {background:#c9c9c9;width:1px;margin:5px 8px;}
QLabel#documentName {font-size:12px;font-weight:600;color:#363636;} QLabel#documentSubtitle {font-size:10px;color:#737373;}
QToolBar QLineEdit,QToolBar QSpinBox {background:#fafafa;color:#333;border:1px solid #c9c9c9;border-radius:5px;padding:5px;min-height:18px;}
QToolBar QSpinBox::up-button,QToolBar QSpinBox::down-button {width:0;}
QListWidget {background:#e9e9e9;border:0;color:#494949;outline:0;}
QSplitter::handle {background:#cecece;width:1px;}
QGraphicsView {border:0;background:#d6d6d6;}
QStatusBar {background:#eeeeee;color:#777;border-top:1px solid #d2d2d2;font-size:10px;}
QDialog {background:#f5f5f5;} QDialog QLabel {color:#3d3d3d;}
QDialog QPushButton {background:#fff;border:1px solid #c7c7c7;border-radius:5px;padding:6px 12px;}
QDialog QPushButton:hover {background:#e7e7e7;}
QDialog QLineEdit,QDialog QTextEdit,QDialog QSpinBox,QDialog QDoubleSpinBox,QDialog QComboBox {background:#fff;color:#333;border:1px solid #c5c5c5;border-radius:4px;padding:5px;}
QScrollBar:vertical {background:transparent;width:10px;margin:3px;} QScrollBar::handle:vertical {background:#b9b9b9;border-radius:4px;min-height:30px;} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;} QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {background:transparent;}
'''
