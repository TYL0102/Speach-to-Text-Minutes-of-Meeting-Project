import pyaudio
import numpy
import time
import json
import paho.mqtt.client as mqtt
from faster_whisper import WhisperModel


# --- MQTT 參數 ---
MQTT_BROKER = "140.116.245.211"
MQTT_TOPIC = "STT_Result"
MIC_ID = "MIC01"

# --- 模型參數 ---
MODEL_SIZE = "base"   # tiny / base
DEVICE = "cpu"        # cpu / gpu
COMPUTE_TYPE = "int8" # int8 節省記憶體占用 & 加速計算
BEAM_SIZE = 1
LANGUAGE = "en"       # 可設 language = None 自動偵測語言

# --- 音訊流參數 ---
FORMAT = pyaudio.paInt16
CHANNELS = 1          # 單聲道
RATE = 16000          # Whisper 要求的採樣率
CHUNK = 1024          # 每次讀取的音框大小

# --- VAD (Voice Activity Detection) 參數 ---
THRESHOLD = 800       # 用於音訊 RMS 判斷是否有語音輸入 (根據麥克風靈敏度調整此數值)
SILENCE_LIMIT = 40    # 偵測到 25 個連續靜音 chunk 則判定語音輸入結束

# # --- 隱藏 ALSA 錯誤訊息 ---
# import os
# os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"

# from ctypes import *
# ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)

# def py_error_handler(filename, line, function, err, fmt) : 
#     pass

# c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
# asound = cdll.LoadLibrary("libasound.so.2")
# asound.snd_lib_error_set_handler(c_error_handler)

if __name__ == "__main__" : 

    # --- 初始化 MQTT ---
    client = mqtt.Client(callback_api_version = mqtt.CallbackAPIVersion.VERSION2)
    try : 
        print(f">>> Connecting to MQTT Broker: {MQTT_BROKER}")
        client.connect(MQTT_BROKER, 1883, 60)
        client.loop_start()
    except : 
        print(">>> MQTT Connection Failed! Please check your Broker IP.")

    # --- 初始化模型 ---
    print(f">>> Loading {MODEL_SIZE.upper()} Model ...")
    model = WhisperModel(MODEL_SIZE, device = DEVICE, compute_type = COMPUTE_TYPE)

    # --- 初始化 PyAudio ---
    audio = pyaudio.PyAudio()
    stream = audio.open(format = FORMAT, channels = CHANNELS, rate = RATE, input = True, frames_per_buffer = CHUNK)

    print()
    print(f">>> System Ready! Please Say Something ...")

    try : 
        frames = []
        is_speaking = False
        silent_chunks = 0
        start_time = 0

        while True : 

            # --- 讀取音訊 ---
            data = stream.read(CHUNK, exception_on_overflow = False)
            audio_data = numpy.frombuffer(data, dtype = numpy.int16).astype(numpy.float64) # 先轉成 float64 避免溢位
            rms = numpy.sqrt(numpy.mean(audio_data ** 2)) # 計算 RMS

            if rms > THRESHOLD : 

                # 語音輸入階段
                if not is_speaking : 
                    start_time = time.time()

                    print(">>> Recording ...         ", end = "\r")
                    is_speaking = True

                frames.append(data)
                silent_chunks = 0

            elif is_speaking : 

                # 靜音階段，判斷語音輸入是否結束
                frames.append(data)
                silent_chunks += 1

                if silent_chunks > SILENCE_LIMIT : 
                    
                    # 語音轉換文字
                    end_time = time.time() - (SILENCE_LIMIT * CHUNK / RATE)

                    print(">>> Converting to Text ...", end = "\r")
                    full_audio = b"".join(frames)
                    audio_np = numpy.frombuffer(full_audio, dtype = numpy.int16).astype(numpy.float32) / 32768.0
                    segments, info = model.transcribe(audio_np, beam_size = BEAM_SIZE, language = LANGUAGE)
                    full_text = "".join([s.text for s in segments])
                    print("                          ", end = "\r")

                    if full_text.strip() : # 確保有文字才傳送
                        payload = {
                            "id": MIC_ID, 
                            "start": time.strftime("%H:%M:%S", time.localtime(start_time)), 
                            "end": time.strftime("%H:%M:%S", time.localtime(end_time)), 
                            "lang": info.language, 
                            "text": full_text.strip()
                        }
                        client.publish(MQTT_TOPIC, json.dumps(payload))
                        print("-" * 50)
                        print(f"Time: {payload["start"]} ~ {payload["end"]}")
                        print(f"Text[{payload["lang"]}]: {payload["text"]}")

                    # 重置狀態
                    frames = []
                    is_speaking = False
                    silent_chunks = 0

    except KeyboardInterrupt : 
        
        print()
        print(f">>> System Terminated.")
    
    finally : 

        client.disconnect()
        stream.stop_stream()
        stream.close()
        audio.terminate()