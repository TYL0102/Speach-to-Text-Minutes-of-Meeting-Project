import json
import time
import os
import csv
import paho.mqtt.client as mqtt

MQTT_BROKER = "localhost"
MQTT_TOPIC = "STT_Result"

# --- csv 設定 ---
def get_csv_filename() : 
    date_str = time.strftime("%Y-%m-%d")
    return f"meeting_{date_str}.csv"

def save_to_csv(payload) : 
    file_name = get_csv_filename()
    file_exists = os.path.isfile(file_name)
    with open(file_name, mode = "a", newline = "", encoding = "utf-8-sig") as file : 
        writer = csv.DictWriter(file, fieldnames = ["id", "start", "end", "lang", "text"])
        if not file_exists : # 如果是新檔案，先寫入標題列 (Header)
            writer.writeheader()
        writer.writerow(payload)

# --- MQTT 回呼函數 ---
def on_connect(client, userdata, flags, rc, properties = None) : 
    try : 
        if rc == 0 : 
            print(f">>> Server is listening on topic: {MQTT_TOPIC} ...")
            client.subscribe(MQTT_TOPIC)
        else : 
            raise Exception()
    except Exception as e : 
        print(f">>> Failed to connect, return code {rc}")

def on_message(client, userdata, msg, properties = None) : 

    try : 

        payload = json.loads(msg.payload.decode())
        print("-" * 50)
        print(f"From: {payload["id"]}")
        print(f"Time: {payload["start"]} ~ {payload["end"]}")
        print(f"Text[{payload["lang"]}]: {payload["text"]}")
        save_to_csv(payload)

    except Exception as e : 

        print("-" * 50)
        print(f"Error decoding message: {e}")

# --- 主程式 ---
if __name__ == "__main__" : 

    client = mqtt.Client(callback_api_version = mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    try : 

        client.connect(MQTT_BROKER, 1883, 60)
        client.loop_forever()

    except KeyboardInterrupt : 

        print()
        print(">>> Server Stopped.")