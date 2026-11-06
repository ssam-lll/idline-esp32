import time
import json
import paho.mqtt.client as mqtt

BROKER = "192.168.1.40"
PORT = 1883

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"Conectado al broker MQTT ({BROKER}:{PORT}) con resultado: {rc}")
    client.subscribe("telemetria/#")
    client.subscribe("control/motores")

def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8", errors="ignore")
    print(f"[{msg.topic}] {payload}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message

print(f"Conectando a {BROKER}:{PORT}...")
client.connect(BROKER, PORT, 60)
client.loop_start()

try:
    for _ in range(6):
        time.sleep(1)
finally:
    client.loop_stop()
    client.disconnect()
    print("Desconectado.")
