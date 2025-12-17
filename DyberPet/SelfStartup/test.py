import sys
import os
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QMenu, QAction
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QMovie, QCursor, QColor
from DyberPet.ChatWindow import ChatWindow

class DesktopPet(QWidget):
    def __init__(self):
        super().__init__()

        # --- 1. 变量初始化 ---
        self.is_dragging = False
        self.drag_position = QPoint()

        # 定义当前正在播放的状态标记
        self.current_state = "NONE"  # 可选: INTRO, IDLE, INTERACT

        # --- 2. 初始化界面 ---
        self.initUI()

        # --- 3. 加载所有动画资源 ---
        self.load_animations()
        self.chat_window = None

        # --- 4. 启动！播放开场动画 ---
        self.play_intro()

    def initUI(self):
        # 无边框、置顶、透明背景
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 窗口大小 (根据你的GIF尺寸调整，这里设为 200x200)
        self.resize(200, 200)

        # 标签 (用来放动画)
        self.label = QLabel(self)
        self.label.setGeometry(0, 0, 200, 200)
        self.label.setScaledContents(True)  # 允许缩放

        self.show()

    def load_animations(self):
        """预加载三个 QMovie 对象"""

        # 辅助函数：配置 QMovie
        def create_movie(path):
            if not os.path.exists(path):
                print(f"❌ 错误: 找不到文件 {path}")
                return QMovie()  # 返回空对象防止报错

            movie = QMovie(path)
            movie.setCacheMode(QMovie.CacheAll)
            movie.setBackgroundColor(QColor(0, 0, 0, 0))  # 修复透明黑边
            return movie

        # 1. 开场动画
        self.movie_intro = create_movie("D:/process/Python/DyberPet/res/role/流萤/action/bixin_0.png")
        # 监听帧变化，用于检测“播放完毕”
        self.movie_intro.frameChanged.connect(self.check_animation_end)

        # 2. 待机动画
        self.movie_idle = create_movie("D:/process/Python/DyberPet/res/role/流萤/action/bixin_1.png")

        # 3. 互动动画
        self.movie_interact = create_movie("D:/process/Python/DyberPet/res/role/流萤/action/bixin_2.png")
        self.movie_interact.frameChanged.connect(self.check_animation_end)

    def play_intro(self):
        """播放开场动画"""
        self.current_state = "INTRO"
        self.label.setMovie(self.movie_intro)
        self.movie_intro.jumpToFrame(0)  # 重置到第一帧
        self.movie_intro.start()

    def play_idle(self):
        """播放待机动画 (循环)"""
        # 如果已经是 IDLE 状态，就不重复刷新了，避免鬼畜
        if self.current_state == "IDLE":
            return

        self.current_state = "IDLE"
        self.label.setMovie(self.movie_idle)
        self.movie_idle.start()

    def play_interact(self):
        """播放互动动画"""
        self.current_state = "INTERACT"
        self.label.setMovie(self.movie_interact)
        self.movie_interact.jumpToFrame(0)  # 每次点击都从头播放
        self.movie_interact.start()

    def check_animation_end(self):
        """每一帧都会触发，检查是否播放到了最后一帧"""
        # 获取当前正在播放的 movie
        current_movie = self.label.movie()

        if current_movie:
            current_frame = current_movie.currentFrameNumber()
            total_frames = current_movie.frameCount()

            # 如果当前帧是最后一帧 (total_frames - 1)
            # 并且当前状态是 INTRO 或 INTERACT (因为 IDLE 不需要结束)
            if current_frame == total_frames - 1:
                if self.current_state in ["INTRO", "INTERACT"]:
                    # 强行切换到待机状态
                    self.play_idle()

    # --- 鼠标事件处理 ---

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            self.setCursor(QCursor(Qt.ClosedHandCursor))

            # 触发互动动画
            self.play_interact()
            print("摸头/点击 -> 播放 Interact 动画")

        elif event.button() == Qt.RightButton:
            # 右键也算一种互动，先播放动画，再弹菜单
            # self.play_interact()
            # self.showContextMenu()
            self.open_chat_window()

    def mouseMoveEvent(self, event):
        if self.is_dragging and (event.buttons() & Qt.LeftButton):
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.is_dragging = False
        self.setCursor(QCursor(Qt.ArrowCursor))

    def showContextMenu(self):
        menu = QMenu(self)
        chat_action = QAction("💬 聊天", self)
        chat_action.triggered.connect(self.open_chat_window)
        menu.addAction(chat_action)

        quit_action = QAction("❌ 退出", self)
        quit_action.triggered.connect(self.close)
        menu.addAction(quit_action)

        menu.exec_(QCursor.pos()) # 在鼠标位置显示菜单

    def open_chat_window(self):
        """打开聊天窗口"""
        if self.chat_window is None:
            # 创建新窗口
            self.chat_window = ChatWindow()
            print("创建新窗口")

        # 显示窗口
        self.chat_window.show()

        # 可选：让聊天窗口也置顶
        self.chat_window.raise_()
        self.chat_window.activateWindow()


if __name__ == '__main__':
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    pet = DesktopPet()
    sys.exit(app.exec_())
