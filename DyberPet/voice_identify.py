import pyaudio
import dashscope
from dashscope.audio.asr import *
import os
import threading
import time
# 若没有将API Key配置到环境变量中，需将下面这行代码注释放开， 并将your-api-key替换为自己的API Key
dashscope.api_key = os.environ.get("Qwen_API_Key")
text:str=None
mic = None
stream = None

class Callback(TranslationRecognizerCallback):
    def on_open(self) -> None:
        global mic
        global stream
        # print("TranslationRecognizerCallback open.")
        mic = pyaudio.PyAudio()
        stream = mic.open(
            format=pyaudio.paInt16, channels=1, rate=16000, input=True
        )

    def on_close(self) -> None:
        global mic
        global stream
        # print("TranslationRecognizerCallback close.")
        stream.stop_stream()
        stream.close()
        mic.terminate()
        stream = None
        mic = None

    def on_event(
        self,
        request_id,
        transcription_result: TranscriptionResult,
        translation_result: TranslationResult,
        usage,
    ) -> None:
        global text
        # print("request id: ", request_id)
        # print("usage: ", usage)
        if translation_result is not None:
            # print(
            #     "translation_languages: ",
            #     translation_result.get_language_list(),
            # )
            english_translation = translation_result.get_translation("en")
            # print("sentence id: ", english_translation.sentence_id)
            # print("translate to english: ", english_translation.text)
        if transcription_result is not None:
            # print("sentence id: ", transcription_result.sentence_id)
            # print("transcription: ", transcription_result.text)
            text = transcription_result.text


callback = Callback()


translator = TranslationRecognizerRealtime(
    model="gummy-realtime-v1",
    format="pcm",
    sample_rate=16000,
    transcription_enabled=True,
    translation_enabled=True,
    translation_target_languages=["en"],
    callback=callback,
)
# translator.start()
# print("请您通过麦克风讲话体验实时语音识别和翻译功能")
# start_time = time.time()
# duration = 5  # 5秒
#
# while time.time() - start_time < duration:
#     if stream:
#         data = stream.read(3200, exception_on_overflow=False)
#         translator.send_audio_frame(data)
#     else:
#         break
#
# translator.stop()
def start_recognition():
    """开始语音识别"""
    global is_recognizing, recognizer_thread

    def recognize_loop():
        global is_recognizing
        try:
            translator.start()
            print("开始语音识别，请讲话...")
            is_recognizing = True

            while is_recognizing:
                if stream:
                    try:
                        data = stream.read(3200, exception_on_overflow=False)
                        translator.send_audio_frame(data)
                    except Exception as e:
                        print(f"音频读取错误: {e}")
                        break
                else:
                    time.sleep(0.01)
        except Exception as e:
            print(f"识别器启动失败: {e}")
        finally:
            translator.stop()
            print("语音识别已停止")

    # 在新线程中运行识别循环
    recognizer_thread = threading.Thread(target=recognize_loop, daemon=True)
    recognizer_thread.start()


def stop_recognition():
    """停止语音识别"""
    global is_recognizing
    is_recognizing = False

    # 等待识别线程结束
    if recognizer_thread and recognizer_thread.is_alive():
        recognizer_thread.join(timeout=2)
    return text


def recognize_for_duration(seconds):
    """识别指定时长的语音"""
    start_recognition()
    time.sleep(seconds)
    stop_recognition()
if __name__ == '__main__':
    # recognize_for_duration(5)
    start_recognition()
    time.sleep(5)
    txt=stop_recognition()
    print("识别的文本",txt)