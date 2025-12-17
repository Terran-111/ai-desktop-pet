import os
import sys

# ================= 关键环境设置 =================
os.environ["QT_API"] = "pyside6"
# ===============================================

from PySide6.QtCore import Qt, QTimer, QUrl, QSize
from PySide6.QtGui import QIcon, QColor, QTextCursor, QFont, QLinearGradient, QGradient, QPalette, QBrush
from PySide6.QtWidgets import QApplication, QVBoxLayout, QHBoxLayout, QWidget, QFrame, QGraphicsDropShadowEffect
from PySide6.QtWebSockets import QWebSocket

# --- 核心组件 ---
from qframelesswindow import FramelessWindow, StandardTitleBar
from qfluentwidgets import (LineEdit, TextEdit, PushButton, 
                            Theme, setTheme, BodyLabel)
from qfluentwidgets import FluentIcon as FIF

class ChatWindow(FramelessWindow):
    """
    【二次元萌宠版】独立聊天窗口
    核心特点：圆润、粉嫩、半透明、可爱风
    """
    def __init__(self):
        super().__init__()
        
        # 1. 窗口基础设置
        self.setWindowTitle("与流萤的秘密对话")
        self.resize(380, 600)
        
        if os.path.exists("res/icons/icon.png"):
            self.setWindowIcon(QIcon("res/icons/icon.png"))
        
        # 2. 启用亮色主题
        setTheme(Theme.LIGHT)
        
        # --- ✨ 魔法背景设置 ✨ ---
        # 这里设置了一个梦幻的粉蓝渐变背景。
        # 如果你想用自己的二次元图片做背景，请把下面的 url(...) 换成你的图片路径，例如: url(res/bg.png)
        self.setStyleSheet("""
            ChatWindow { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fdfbfb, stop:1 #ebedee);
                /* 如果想要图片背景，取消下面这行的注释，并填入路径 */
                /* border-image: url("res/your_anime_bg.png") 0 0 0 0 stretch stretch; */
            }
            /* 隐藏自带的白色背景，让渐变透出来 */
            QWidget#MainWidget { background: transparent; }
        """)
        
        # 开启 Win11 云母效果 (增加通透感)
        if hasattr(self, 'windowEffect'):
            self.windowEffect.setMicaEffect(self.winId(), isDarkMode=False)

        # 3. 内部状态
        self.client = None
        self.websocket_url = "ws://127.0.0.1:8000/chat" 
        self.current_ai_text = ""
        
        # 4. 初始化界面
        self.create_ui()
        self.initialize_websocket()
        
        # 萌萌的欢迎语
        QTimer.singleShot(600, lambda: self.append_bubble("主人~ 今天想聊点什么呀？(*/ω＼*)", is_me=False))

    def create_ui(self):
        # --- 主布局 ---
        self.hBoxLayout = QVBoxLayout(self)
        # 留出标题栏高度
        self.hBoxLayout.setContentsMargins(0, 32, 0, 0) 
        
        # --- 内容容器 ---
        self.main_widget = QWidget()
        self.main_widget.setObjectName("MainWidget")
        self.layout = QVBoxLayout(self.main_widget)
        self.layout.setContentsMargins(15, 0, 15, 15)
        self.layout.setSpacing(10)
        
        # 1. 可爱的状态栏
        self.status_container = QHBoxLayout()
        # 用 emoji 或者图标代替原本严肃的点
        self.status_label = BodyLabel("✨ 正在呼唤流萤...", self)
        # 设置可爱的字体颜色
        self.status_label.setStyleSheet("color: #FF9A9E; font-weight: bold; font-family: 'Microsoft YaHei UI';")
        
        self.status_container.addStretch()
        self.status_container.addWidget(self.status_label)
        self.status_container.addStretch()
        self.layout.addLayout(self.status_container)

        # 2. 聊天记录显示区
        self.chat_display = TextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setFrameShape(QFrame.NoFrame)
        # 隐藏滚动条背景，完全透明
        self.chat_display.setStyleSheet("""
            QTextEdit { 
                background-color: transparent; 
                border: none; 
                font-family: 'Microsoft YaHei UI', 'Segoe UI';
                font-size: 15px;
            }
        """)
        self.layout.addWidget(self.chat_display, 1)
        
        # 3. 悬浮胶囊输入栏 (重点美化)
        self.input_container = QFrame()
        self.input_container.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.85); /* 半透明白色 */
                border-radius: 25px; /* 胶囊形状 */
                border: 2px solid #FFD1FF; /* 粉色边框 */
            }
        """)
        # 添加投影
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(255, 105, 180, 80)) # 粉色投影
        shadow.setOffset(0, 4)
        self.input_container.setGraphicsEffect(shadow)

        self.input_layout = QHBoxLayout(self.input_container)
        self.input_layout.setContentsMargins(15, 5, 5, 5)
        
        # 输入框
        self.input_box = LineEdit()
        self.input_box.setPlaceholderText("在这里输入咒语...")
        self.input_box.setClearButtonEnabled(False)
        self.input_box.setStyleSheet("""
            LineEdit { 
                border: none; 
                background: transparent; 
                font-size: 14px; 
                color: #555;
                font-weight: bold;
            }
        """)
        self.input_box.returnPressed.connect(self.send_message)
        self.input_box.setFixedHeight(40)
        
        # 发送按钮 (圆形按钮)
        self.send_btn = PushButton("发送") # 也可以换成图标
        self.send_btn.setFixedSize(60, 36)
        # 糖果色按钮样式
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff9a9e, stop:1 #fad0c4);
                color: white;
                border-radius: 18px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ffecd2, stop:1 #fcb69f);
            }
            QPushButton:pressed {
                padding-top: 2px;
                padding-left: 2px;
            }
        """)
        self.send_btn.clicked.connect(self.send_message)
        
        self.input_layout.addWidget(self.input_box, 1)
        self.input_layout.addWidget(self.send_btn)
        
        self.layout.addWidget(self.input_container)
        
        # 加入主布局
        self.hBoxLayout.addWidget(self.main_widget)

    def initialize_websocket(self):
        self.client = QWebSocket()
        self.client.connected.connect(self.on_connected)
        self.client.disconnected.connect(self.on_disconnected)
        self.client.textMessageReceived.connect(self.on_text_received)
        self.client.open(QUrl(self.websocket_url))

    def on_connected(self):
        self.status_label.setText("💖 流萤已连接")
        self.status_label.setStyleSheet("color: #FF69B4; font-weight: bold;") # 亮粉色

    def on_disconnected(self):
        self.status_label.setText("💔 连接断开")
        self.status_label.setStyleSheet("color: #aaa; font-weight: bold;")

    def send_message(self):
        text = self.input_box.text().strip()
        if not text: return

        self.append_bubble(text, is_me=True)
        self.input_box.clear()

        if self.client:
            self.client.sendTextMessage(text)
            self.current_ai_text = ""
            self.create_loading_bubble()
        else:
            QTimer.singleShot(800, lambda: self.append_bubble("呜呜...大脑连不上了... (｡•́︿•̀｡)", is_me=False))

    def on_text_received(self, message):
        self.current_ai_text += message
        self.update_last_bubble(self.current_ai_text)

    # ================= ✨ 萌系气泡样式 ✨ =================

    def append_bubble(self, text, is_me=False):
        import html
        safe_text = html.escape(text).replace("\n", "<br>")
        
        # 字体设置
        font_style = "font-family: 'Microsoft YaHei UI'; font-size: 14px; line-height: 1.5;"
        
        if is_me:
            # === 主人气泡 (右侧) ===
            # 颜色：粉嫩渐变
            # 形状：大圆角，像棉花糖
            html_content = f"""
            <div style="width: 100%; display: flex; justify-content: flex-end; margin-bottom: 20px;">
                <div style="float: right; max-width: 80%;">
                    <div style="{font_style} 
                                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #a18cd1, stop:1 #fbc2eb);
                                color: white; 
                                border-radius: 20px; border-bottom-right-radius: 5px;
                                padding: 12px 18px; 
                                box-shadow: 2px 2px 8px rgba(161, 140, 209, 0.4);">
                        {safe_text}
                    </div>
                </div>
            </div>
            """
        else:
            # === 流萤气泡 (左侧) ===
            # 颜色：纯白带粉色边框
            # 形状：圆润
            html_content = f"""
            <div style="width: 100%; margin-bottom: 20px;">
                <div style="margin-left: 15px; margin-bottom: 5px; font-size: 12px; color: #FF9A9E; font-weight: bold;">
                    ✨ 流萤
                </div>
                <div style="display: flex; justify-content: flex-start; max-width: 85%;">
                    <div style="{font_style} 
                                background-color: #ffffff; color: #555; 
                                border-radius: 20px; border-top-left-radius: 5px;
                                border: 2px solid #FFF0F5; /* 极淡的粉色边框 */
                                padding: 12px 18px; 
                                box-shadow: 2px 2px 8px rgba(0,0,0,0.05);">
                        {safe_text}
                    </div>
                </div>
            </div>
            """
        self._insert_html(html_content)

    def create_loading_bubble(self):
        """颜文字思考中"""
        html_content = f"""
        <div style="width: 100%; margin-bottom: 20px;">
            <div style="margin-left: 15px; margin-bottom: 5px; font-size: 12px; color: #FF9A9E; font-weight: bold;">✨ 流萤</div>
            <div style="display: flex; justify-content: flex-start;">
                <div style="background-color: #ffffff; color: #FF9A9E; 
                            border-radius: 20px; border-top-left-radius: 5px;
                            border: 2px solid #FFF0F5; padding: 10px 18px;">
                    Thinking... (｀・ω・´)
                </div>
            </div>
        </div>
        """
        self._insert_html(html_content)

    def update_last_bubble(self, full_text):
        import html
        safe_text = html.escape(full_text).replace("\n", "<br>")
        font_style = "font-family: 'Microsoft YaHei UI'; font-size: 14px; line-height: 1.5;"
        
        html_content = f"""
        <div style="width: 100%; margin-bottom: 20px;">
            <div style="margin-left: 15px; margin-bottom: 5px; font-size: 12px; color: #FF9A9E; font-weight: bold;">✨ 流萤</div>
            <div style="display: flex; justify-content: flex-start; max-width: 85%;">
                <div style="{font_style} 
                            background-color: #ffffff; color: #555; 
                            border-radius: 20px; border-top-left-radius: 5px;
                            border: 2px solid #FFF0F5;
                            padding: 12px 18px; 
                            box-shadow: 2px 2px 8px rgba(0,0,0,0.05);">
                    {safe_text}
                </div>
            </div>
        </div>
        """
        
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.select(QTextCursor.BlockUnderCursor) 
        cursor.removeSelectedText()
        cursor.insertHtml(html_content)
        self.scroll_to_bottom()

    def _insert_html(self, html):
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.chat_display.setTextCursor(cursor)
        self.chat_display.insertHtml(html)
        self.chat_display.insertPlainText("\n")
        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        QTimer.singleShot(50, lambda: self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum()))

    def closeEvent(self, event):
        if self.client: self.client.close()
        super().closeEvent(event)

if __name__ == '__main__':
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication(sys.argv)
    w = ChatWindow()
    w.show()
    sys.exit(app.exec())