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
# 建议多加几个同音字，防止识别不准，例如 "刘莹"
WAKE_WORDS = ["流萤", "萤萤", "刘莹", "流云", "老婆",] 

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

# --- 说话线程 (TTS - 包含防回声冷却) ---
class TTSWorker(QThread):
    def __init__(self):
        super().__init__()
        self.text_queue = queue.Queue()   # 文本队列
        self.audio_queue = queue.Queue()  # 音频文件队列
        self.is_running = True
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
                
                # 只要有任务，立马锁住耳朵，防止 AI 听到自己念稿子
                speech_lock.set()
                
                # 简单的断句处理
                sentences = re.split(r'([。\n？！?!;；])', text)
                clean_sentences = []
                for i in range(0, len(sentences)-1, 2):
                    clean_sentences.append(sentences[i] + sentences[i+1])
                if len(sentences) % 2 != 0:
                    clean_sentences.append(sentences[-1])

                for i, sent in enumerate(clean_sentences):
                    if not sent.strip(): continue
                    if not self.is_running: break
                    
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
                # 获取音频文件
                audio_file = self.audio_queue.get(timeout=0.5)
                
                # 【双重保险】播放前再次确认锁住耳朵
                speech_lock.set()
                
                if os.path.exists(audio_file):
                    print(f"正在播放: {audio_file}")
                    pygame.mixer.music.load(audio_file)
                    pygame.mixer.music.play()
                    
                    # 阻塞等待播放结束
                    while pygame.mixer.music.get_busy() and self.is_running:
                        time.sleep(0.1)
                    
                    pygame.mixer.music.unload()
                    try:
                        os.remove(audio_file)
                    except:
                        pass
                
                # =======================================================
                # 【核心修复】：物理回声冷却时间
                # 播放结束后，强制等待 0.8 秒，让声音在空气中彻底消散
                # 防止麦克风录到 AI 的尾音
                # =======================================================
                if self.is_running:
                    time.sleep(0.8) 

                # 只有当队列全空时，才释放锁
                if self.audio_queue.empty() and self.text_queue.empty():
                    print("播放结束，解锁麦克风...") 
                    speech_lock.clear()
                    
            except queue.Empty:
                # 队列空闲时的保底逻辑
                if self.text_queue.empty() and speech_lock.is_set():
                    # 如果锁还开着但没任务了，大概率是卡住了，强制解锁
                    # speech_lock.clear() # 视情况开启，有时候太激进会打断思考
                    pass
            except Exception as e:
                print(f"播放器错误: {e}")

    def add_speech(self, text):
        self.text_queue.put(text)
        speech_lock.set() # 收到任务瞬间上锁

    def clear_queue(self):
        """紧急停止：闭嘴"""
        print("执行：停止语音播放")
        with self.text_queue.mutex:
            self.text_queue.queue.clear()
        
        while not self.audio_queue.empty():
            try:
                f = self.audio_queue.get_nowait()
                if os.path.exists(f): os.remove(f)
            except: pass
        
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            
        speech_lock.clear() # 强制解锁

    def stop(self):
        self.is_running = False
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
        """检查是否包含唤醒词"""
        if not text: return False
        
        # 1. 移除标点和空格，方便匹配
        clean_text = text.replace(" ", "").replace("，", "").replace("。", "")
        
        # 2. 遍历唤醒词列表
        for wake_word in WAKE_WORDS:
            # 只要句子开头是唤醒词
            if clean_text.startswith(wake_word):
                print(f"【唤醒成功】检测到关键词: {wake_word}")
                return True
        
        return False

    def run(self):
        # 设置灵敏度
        self.recognizer.dynamic_energy_threshold = True 
        self.recognizer.energy_threshold = 400  # 稍微调高一点阈值，过滤极细微的噪音

        print("[语音线程] 启动监听循环...")

        # 【优化】只在启动时校准一次环境音，不在循环里反复校准
        with sr.Microphone(sample_rate=16000) as source:
            print("正在校准环境噪音...请保持安静 1 秒")
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
            print("校准完成，请呼唤 '流萤' 开始对话")

        while self.is_running:
            # 如果 AI 正在说话，歇一会儿，别占 CPU
            if speech_lock.is_set():
                time.sleep(0.1)
                continue

            with sr.Microphone(sample_rate=16000) as source:
                try:
                    # 再次检查锁，防止进入 listen 瞬间被锁住
                    if speech_lock.is_set(): continue

                    # 开始监听
                    # phrase_time_limit: 一句话最长听多久
                    # timeout: 等多久没人说话就报错
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                    
                    # 拿到录音后，如果发现 AI 突然插嘴说话了（比如多线程冲突），丢弃这段录音
                    if speech_lock.is_set(): 
                        print("检测到语音冲突，丢弃录音")
                        continue

                    self.sig_listening_start.emit()
                    
                    # --- 识别逻辑 ---
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
                    else:
                        # 如果没有 vosk，可以用 google 在线 (需要梯子)
                        # text = self.recognizer.recognize_google(audio, language='zh-CN')
                        pass

                    # --- 唤醒词核心逻辑 ---
                    if text and len(text) > 1:
                        print(f"识别原始内容: {text}")
                        
                        # 检查是否叫了名字
                        if self.check_wake_word(text):
                            # 如果唤醒成功，发送信号给主界面（连接大模型）
                            # 我们可以选择把唤醒词去掉，也可以留着，看你喜好
                            # 这里我选择把整句话发过去
                            self.sig_speech_recognized.emit(text)
                        else:
                            print(f"忽略输入 (未匹配唤醒词): {text}")
                            
                except sr.WaitTimeoutError:
                    pass # 超时没说话，正常现象
                except Exception as e:
                    # print(f"识别错误: {e}") # 调试时可打开
                    pass

    def stop_speaking_immediately(self):
        self.tts_worker.clear_queue()