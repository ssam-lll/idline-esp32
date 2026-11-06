import time
import json
import paho.mqtt.client as mqtt

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"MQTT CONECTADO rc={rc}")
    client.subscribe("telemetria/sensores")
    client.subscribe("telemetria/motores/estado")

def on_message(client, userdata, msg):
    payload = msg.payload.decode('utf-8', errors='ignore')
    print(f"[{msg.topic}] {payload}")

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message
client.connect("192.168.1.40", 1883, 60)
client.loop_start()

time.sleep(5)

client.loop_stop()
client.disconnect()
print("FIN.")
