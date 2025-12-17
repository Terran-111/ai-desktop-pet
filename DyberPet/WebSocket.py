from PyQt5.QtWebSockets import QWebSocket
from PyQt5.QtCore import QUrl, QCoreApplication
import sys

app = QCoreApplication(sys.argv)

client = QWebSocket()
client.connected.connect(lambda: print("Connected"))
client.disconnected.connect(lambda: print("Disconnected"))
client.textMessageReceived.connect(lambda msg: print(msg))

url = "ws://127.0.0.1:8000/chat"
client.open(QUrl(url))

# 添加错误处理
client.error.connect(lambda error: print(f"Connection error: {error}"))

# 启动事件循环
sys.exit(app.exec_())
