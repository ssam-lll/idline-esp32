import time
import json
import paho.mqtt.client as mqtt

BROKER = "192.168.1.40"
PORT = 1883
TOPIC_TELEMETRY = "telemetria/sensores"
TOPIC_STATUS = "telemetria/motores/estado"
TOPIC_CONTROL = "control/motores"

history = []

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"[MQTT] Conectado ({rc})")
    client.subscribe([(TOPIC_TELEMETRY, 0), (TOPIC_STATUS, 0)])

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8", errors="ignore"))
        if msg.topic == TOPIC_TELEMETRY:
            history.append(data)
            pos = data.get("posicion", 0)
            modo = data.get("modo", "")
            m1 = data.get("m1", 0)
            m2 = data.get("m2", 0)
            s = data.get("sensores", [])
            s_str = " ".join(f"{v:4d}" for v in s) if s else ""
            print(f"[{modo:7s}] Pos:{pos:+5d} | M1:{m1:4d} M2:{m2:4d} | [{s_str}]")
        elif msg.topic == TOPIC_STATUS:
            print(f"[STATUS] {data}")
    except Exception as e:
        print("Err parse:", e)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_connect = on_connect
client.on_message = on_message
client.connect(BROKER, PORT, 60)
client.loop_start()

time.sleep(0.5)

# 1. Asegurar parámetros de CARRERA (680)
set_cmd = json.dumps({"cmd": "set_pid", "kp": 0.72, "ki": 0.0, "kd": 4.2, "speed": 680})
print("Configurando PID Perfil CARRERA:", set_cmd)
client.publish(TOPIC_CONTROL, set_cmd)
time.sleep(0.5)

# 2. Dar orden de arranque
print("\n>>> ENVIANDO START_PID (Perfil CARRERA 680)... <<<")
client.publish(TOPIC_CONTROL, json.dumps({"cmd": "start_pid"}))

# 3. Monitorear durante 5 segundos
try:
    for i in range(50):
        time.sleep(0.1)
finally:
    print("\n>>> ENVIANDO STOP... <<<")
    client.publish(TOPIC_CONTROL, json.dumps({"cmd": "stop"}))
    time.sleep(0.3)
    client.loop_stop()
    client.disconnect()
    print("Captura finalizada.")
