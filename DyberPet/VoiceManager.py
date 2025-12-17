import speech_recognition as sr
import pyttsx3
from PySide6.QtCore import QThread, Signal

class VoiceWorker(QThread):
    sig_listening_start = Signal()       # 开始听了（气泡显示：听着呢...）
    sig_speech_recognized = Signal(str)  # 识别到了用户说的话
    sig_response_audio = Signal(str)     # 准备播放语音
    
    def __init__(self):
        super().__init__()
        self.recognizer = sr.Recognizer()
        self.engine = pyttsx3.init()
        self.is_running = True
        
        # 简单配置 TTS 音色 (可选)
        voices = self.engine.getProperty('voices')
        # 尝试找一个中文女声
        for voice in voices:
            if "Chinese" in voice.name or "Zira" in voice.name:
                self.engine.setProperty('voice', voice.id)
                break

    def run(self):
        """
        这里是一个简化的逻辑：
        实际项目中，这里应该先运行 '唤醒词检测(Porcupine)'，
        检测到唤醒词后，再运行下面的 sr.listen。
        为了演示，这里假设一直处于“等待说话”状态。
        """
        while self.is_running:
            with sr.Microphone() as source:
                # 调整环境噪音
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                print("等待语音指令...")
                
                try:
                    # 监听音频
                    audio = self.recognizer.listen(source, timeout=10, phrase_time_limit=5)
                    self.sig_listening_start.emit() # 通知UI显示状态
                    
                    # 识别文字 (需联网使用 Google API，国内建议换成 Baidu 或 OpenAI Whisper)
                    text = self.recognizer.recognize_google(audio, language='zh-CN')
                    print(f"识别内容: {text}")
                    
                    if text:
                        # 简单的唤醒词判断（如果没有用 Porcupine）
                        if "流萤" in text or "你好" in text:
                            self.sig_speech_recognized.emit(text)
                            
                except sr.WaitTimeoutError:
                    pass # 没人说话，继续循环
                except Exception as e:
                    print(f"语音识别错误: {e}")

    def speak(self, text):
        """播放语音"""
        # 注意：pyttsx3 的 runAndWait 会阻塞，建议在单独线程或使用非阻塞方式
        # 这里简单演示
        self.engine.say(text)
        self.engine.runAndWait()