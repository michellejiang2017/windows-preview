"""Draw or type a visual signature without saving it outside the document."""
from io import BytesIO
from PIL import Image
from PySide6.QtCore import Qt,QBuffer,QIODevice,QPointF
from PySide6.QtGui import QPainter,QImage,QColor,QPen,QPainterPath,QFont
from PySide6.QtWidgets import QWidget,QDialog,QVBoxLayout,QLabel,QLineEdit,QPushButton,QDialogButtonBox

class SignaturePad(QWidget):
    def __init__(self):
        super().__init__();self.setFixedSize(480,170);self.paths=[];self.current=None;self.name=''
    def clear(self):self.paths=[];self.current=None;self.name='';self.update()
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton:self.current=QPainterPath(event.position());self.paths.append(self.current);self.update()
    def mouseMoveEvent(self,event):
        if self.current is not None:self.current.lineTo(event.position());self.update()
    def mouseReleaseEvent(self,event):self.current=None
    def paint_signature(self,painter):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing);painter.setPen(QPen(QColor('#17212d'),2,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
        for path in self.paths:painter.drawPath(path)
        if self.name:painter.setFont(QFont('Georgia',32,-1,True));painter.drawText(20,112,self.name)
    def paintEvent(self,event):
        painter=QPainter(self);painter.fillRect(self.rect(),Qt.GlobalColor.white);self.paint_signature(painter);painter.end()
    def image(self):
        image=QImage(self.size()*2,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.transparent);painter=QPainter(image);painter.scale(2,2);self.paint_signature(painter);painter.end();buffer=QBuffer();buffer.open(QIODevice.OpenModeFlag.WriteOnly);image.save(buffer,'PNG');im=Image.open(BytesIO(bytes(buffer.data()))).convert('RGBA');bbox=im.getbbox()
        return im.crop(bbox) if bbox else None

def capture_signature(parent):
    dlg=QDialog(parent);dlg.setWindowTitle('Add signature');layout=QVBoxLayout(dlg);layout.addWidget(QLabel('Draw your signature below, or type your name.'));pad=SignaturePad();layout.addWidget(pad);name=QLineEdit();name.setPlaceholderText('Or type your name');name.setMaxLength(100);layout.addWidget(name)
    def typed(value):pad.paths=[];pad.name=value;pad.update()
    name.textChanged.connect(typed);clear=QPushButton('Clear');clear.clicked.connect(lambda:(name.clear(),pad.clear()));layout.addWidget(clear);layout.addWidget(QLabel('Adds a visible signature, not a certificate-based digital signature.'));buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Place signature');buttons.accepted.connect(dlg.accept);buttons.rejected.connect(dlg.reject);layout.addWidget(buttons)
    if dlg.exec()==QDialog.DialogCode.Accepted:
        result=pad.image()
        if result is None:raise ValueError('Draw a signature or type your name first.')
        return result
    return None
