from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QGraphicsDropShadowEffect
from PySide6.QtCore import Qt, QTimer, QPoint, QRectF
from PySide6.QtGui import QPainter, QPainterPath, QColor, QFont, QBrush, QPen

class SpeechBubble(QWidget):
    def __init__(self, parent=None, text=""):
        super().__init__(parent)
        # 设置为无边框、置顶、透明背景工具窗口
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 文本内容
        self.label = QLabel(text)
        self.label.setStyleSheet("color: #333333; background: transparent;")
        font = QFont("Microsoft YaHei UI", 12)
        font.setBold(True)
        self.label.setFont(font)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignCenter)
        
        # 布局
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 10, 15, 20) # 底部留多点给尖角
        layout.addWidget(self.label)
        self.setLayout(layout)
        
        # 阴影效果
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)
        
        # 自动隐藏定时器
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.fade_out)
        
        self.opacity = 1.0
        self.resize(200, 100)

    def show_msg(self, text, duration=5000):
        """显示消息"""
        self.label.setText(text)
        self.adjustSize() # 根据文字自动调整大小
        self.setWindowOpacity(1.0)
        self.show()
        self.hide_timer.start(duration)

    def fade_out(self):
        """简单的淡出效果（也可直接 hide）"""
        self.close()

    def paintEvent(self, event):
        """绘制气泡形状"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 气泡颜色
        bg_color = QColor(255, 255, 255, 240) # 米白色，微透
        border_color = QColor(255, 200, 200)  # 淡粉色边框
        
        path = QPainterPath()
        # 留出绘制尖角的空间
        rect = QRectF(0, 0, self.width(), self.height() - 15) 
        radius = 15
        
        path.addRoundedRect(rect, radius, radius)
        
        # 绘制底部的小尖角 (指向宠物)
        # 尖角位置在底部中间
        tri_x = self.width() / 2
        tri_y = self.height() - 15
        
        path.moveTo(tri_x - 10, tri_y) # 左点
        path.lineTo(tri_x, self.height()) # 尖点
        path.lineTo(tri_x + 10, tri_y) # 右点
        
        # 绘制
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 2))
        painter.drawPath(path)