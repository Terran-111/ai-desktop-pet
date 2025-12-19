import speech_recognition as sr
import edge_tts
import pygame 
import asyncio
from PySide6.QtCore import QThread, Signal
import os
import json
import queue
import re
import time
import threading

# ================= 配置区域 =================
# 在这里修改你的唤醒词
WAKE_WORDS = ["流萤", "萤萤", "刘莹", "刘盈", "流云", "老婆", "牛", "ai助手", "你好"] 

# 语音合成的角色
TTS_VOICE = "zh-CN-XiaoxiaoNeural"
# ===========================================

# 全局变量：标记是否正在说话 (用于锁住麦克风)
speech_lock = threading.Event()
speech_lock.clear()

# 尝试导入 vosk (离线识别库)
try:
    import vosk
    vosk_available = True
except ImportError:
    vosk_available = False

# --- 说话线程 (TTS - 包含中断控制与防回声冷却) ---
class TTSWorker(QThread):
    def __init__(self):
        super().__init__()
        self.text_queue = queue.Queue()   # 文本队列
        self.audio_queue = queue.Queue()  # 音频文件队列
        self.is_running = True
        self.interrupted = False          # 【核心】全局中断标志
        self.voice = TTS_VOICE
        
        try:
            pygame.mixer.init()
        except:
            pass

        # 启动播放消费者线程
        self.player_thread = threading.Thread(target=self._player_loop, daemon=True)
        self.player_thread.start()

    def run(self):
        """下载生产者：负责将文本转为音频文件"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self.is_running:
            try:
                # 获取文本
                text = self.text_queue.get(timeout=0.5)
                self.interrupted = False  # 开始新任务，重置中断状态
                
                # 只要有任务，立马锁住麦克风
                speech_lock.set()
                
                # 简单的断句处理
                sentences = re.split(r'([。\n？！?!;；])', text)
                clean_sentences = []
                for i in range(0, len(sentences)-1, 2):
                    clean_sentences.append(sentences[i] + sentences[i+1])
                if len(sentences) % 2 != 0:
                    clean_sentences.append(sentences[-1])

                for i, sent in enumerate(clean_sentences):
                    # 【关键修改】生成每一段音频前，检查是否被叫停
                    if self.interrupted or not self.is_running:
                        print("检测到中断信号，停止后续音频生成")
                        break
                        
                    if not sent.strip(): continue
                    
                    # 生成唯一文件名
                    temp_file = f"tts_temp_{int(time.time()*1000)}_{i}.mp3"
                    loop.run_until_complete(self._generate_audio(sent, temp_file))
                    self.audio_queue.put(temp_file)

            except queue.Empty:
                pass
            except Exception as e:
                print(f"TTS生成错误: {e}")
        
        loop.close()

    async def _generate_audio(self, text, filename):
        try:
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(filename)
        except Exception as e:
            print(f"音频生成失败: {e}")

    def _player_loop(self):
        """播放消费者：负责播放音频并管理锁"""
        while self.is_running:
            try:
                # 获取待播放的音频文件
                audio_file = self.audio_queue.get(timeout=0.5)
                
                # 【关键修改】播放前检查是否已被中断
                if self.interrupted:
                    if os.path.exists(audio_file): os.remove(audio_file)
                    continue
                
                speech_lock.set()
                
                if os.path.exists(audio_file):
                    print(f"正在播放: {audio_file}")
                    pygame.mixer.music.load(audio_file)
                    pygame.mixer.music.play()
                    
                    # 阻塞等待播放结束
                    while pygame.mixer.music.get_busy() and self.is_running:
                        # 【关键修改】播放过程中如果收到中断，立即停止物理声音
                        if self.interrupted:
                            pygame.mixer.music.stop()
                            break
                        time.sleep(0.1)
                    
                    pygame.mixer.music.unload()
                    try:
                        os.remove(audio_file)
                    except:
                        pass
                
                # 播放结束后的回声冷却（仅在未中断时执行）
                if self.is_running and not self.interrupted:
                    time.sleep(0.8) 

                # 只有当任务全部处理完毕且未被中断时，才释放麦克风锁
                if self.audio_queue.empty() and self.text_queue.empty():
                    print("所有对话播放结束，解锁麦克风...") 
                    speech_lock.clear()
                    
            except queue.Empty:
                if self.text_queue.empty() and speech_lock.is_set():
                    # 队列空闲且没有正在播放的声音时，尝试解锁
                    if not pygame.mixer.music.get_busy():
                        speech_lock.clear()
            except Exception as e:
                print(f"播放器错误: {e}")

    def add_speech(self, text):
        self.interrupted = False # 开始新语音，允许播放
        self.text_queue.put(text)
        speech_lock.set()

    def clear_queue(self):
        """全量紧急停止：不仅清空队列，还要立即掐断正在播放的声音"""
        print("执行：全量停止语音任务")
        self.interrupted = True # 1. 开启中断信号
        
        # 2. 立即停止物理声音播放
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        
        # 3. 清空待生成的文本队列
        with self.text_queue.mutex:
            self.text_queue.queue.clear()
        
        # 4. 清空音频文件队列并删除对应的磁盘文件
        while not self.audio_queue.empty():
            try:
                f = self.audio_queue.get_nowait()
                if os.path.exists(f): os.remove(f)
            except: pass
            
        speech_lock.clear() # 5. 强制释放麦克风锁

    def stop(self):
        self.is_running = False
        self.interrupted = True
        try:
            pygame.mixer.quit()
        except:
            pass
        self.wait()

# --- 听写线程 (STT - 包含唤醒词检测) ---
class VoiceWorker(QThread):
    sig_listening_start = Signal()       
    sig_speech_recognized = Signal(str)  
    
    def __init__(self):
        super().__init__()
        self.recognizer = sr.Recognizer()
        self.is_running = True
        
        self.tts_worker = TTSWorker()
        self.tts_worker.start()
        
        self.vosk_model = None
        if vosk_available and os.path.exists("model"):
            try:
                vosk.SetLogLevel(-1) 
                self.vosk_model = vosk.Model("model")
                print("【语音模块】Vosk 模型加载成功")
            except:
                pass

    def check_wake_word(self, text):
        if not text: return False
        clean_text = text.replace(" ", "").replace("，", "").replace("。", "")
        for wake_word in WAKE_WORDS:
            if clean_text.startswith(wake_word):
                return True
        return False

    def run(self):
        self.recognizer.dynamic_energy_threshold = True 
        self.recognizer.energy_threshold = 400 

        with sr.Microphone(sample_rate=16000) as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)

        while self.is_running:
            if speech_lock.is_set():
                time.sleep(0.1)
                continue

            with sr.Microphone(sample_rate=16000) as source:
                try:
                    if speech_lock.is_set(): continue
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                    
                    if speech_lock.is_set(): continue

                    self.sig_listening_start.emit()
                    
                    text = ""
                    if self.vosk_model:
                        try:
                            rec = vosk.KaldiRecognizer(self.vosk_model, 16000)
                            audio_data = audio.get_raw_data(convert_rate=16000, convert_width=2)
                            if rec.AcceptWaveform(audio_data):
                                res = json.loads(rec.Result())
                                text = res.get("text", "")
                            else:
                                res = json.loads(rec.FinalResult())
                                text = res.get("text", "")
                            text = text.replace(" ", "")
                        except:
                            pass
                    
                    if text and len(text) > 1:
                        if self.check_wake_word(text):
                            self.sig_speech_recognized.emit(text)
                            
                except sr.WaitTimeoutError:
                    pass
                except Exception as e:
                    pass

    def stop_speaking_immediately(self):
        self.tts_worker.clear_queue()

    def speak(self, text):
        self.tts_worker.add_speech(text)

    def stop(self):
        self.is_running = False
        self.tts_worker.stop()
        self.terminate()
        self.wait()