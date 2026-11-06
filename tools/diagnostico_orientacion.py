import time
import json
import paho.mqtt.client as mqtt

BROKER = "192.168.1.40"
PORT = 1883

def on_connect(client, userdata, flags, rc, properties=None):
    client.subscribe("telemetria/sensores")

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8", errors="ignore"))
        s = data.get("sensores", [])
        pos = data.get("posicion", 0)
        # Formato visual tipo barra
        # s[0] a s[7]
        bars = "".join("#" if v > 1500 else "." for v in s)
        s_str = " ".join(f"{v:4d}" for v in s)
        print(f"Pos:{pos:+5d} | [{bars}] | Raw: [{s_str}]")
    except Exception as e:
        pass

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.loop_start()

try:
    for _ in range(30):
        time.sleep(0.5)
finally:
    client.loop_stop()
    client.disconnect()
