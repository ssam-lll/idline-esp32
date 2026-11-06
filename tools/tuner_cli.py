import sys
import time
import json
import threading
import paho.mqtt.client as mqtt

BROKER = "192.168.1.40"
PORT = 1883
TOPIC_TELEMETRY = "telemetria/sensores"
TOPIC_STATUS = "telemetria/motores/estado"
TOPIC_CONTROL = "control/motores"

latest_telemetry = None
running = True

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"\n[MQTT] Conectado exitosamente al broker {BROKER}:{PORT}")
        client.subscribe([(TOPIC_TELEMETRY, 0), (TOPIC_STATUS, 0)])
        print(f"[MQTT] Suscrito a {TOPIC_TELEMETRY} y {TOPIC_STATUS}")
    else:
        print(f"\n[MQTT] Error al conectar, rc={rc}")

def on_message(client, userdata, msg):
    global latest_telemetry
    try:
        data = json.loads(msg.payload.decode("utf-8", errors="ignore"))
        if msg.topic == TOPIC_TELEMETRY:
            latest_telemetry = data
            s = data.get("sensores", [])
            pos = data.get("posicion", 0)
            modo = data.get("modo", "UNKNOWN")
            m1 = data.get("m1", 0)
            m2 = data.get("m2", 0)
            vbat = data.get("vbat_mv", 0)
            # Imprimir una línea limpia y compacta
            s_str = " ".join(f"{v:4d}" for v in s) if s else "N/A"
            print(f"[{modo:11s}] Pos:{pos:+5d} | M1:{m1:4d} M2:{m2:4d} | Vbat:{vbat/1000.0:.2f}V | Sens: [{s_str}]")
        elif msg.topic == TOPIC_STATUS:
            print(f"[STATUS] {data}")
    except Exception as e:
        print(f"[ERROR PARSE] {e}")

def send_cmd(client, cmd_dict):
    payload = json.dumps(cmd_dict)
    client.publish(TOPIC_CONTROL, payload)
    print(f"\n-> Comando enviado: {payload}")

def main():
    global running
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"Iniciando monitor de telemetría hacia {BROKER}:{PORT}...")
    try:
        client.connect(BROKER, PORT, 60)
    except Exception as e:
        print(f"No se pudo conectar a {BROKER}:{PORT}: {e}")
        return

    client.loop_start()

    if len(sys.argv) > 1:
        # Modo comando directo
        action = sys.argv[1].lower()
        time.sleep(0.5)
        if action == "stop":
            send_cmd(client, {"cmd": "stop"})
        elif action == "start":
            send_cmd(client, {"cmd": "start_pid"})
        elif action == "calib":
            send_cmd(client, {"cmd": "calibrate"})
        elif action == "set":
            # set kp kd speed (e.g. set 0.45 3.5 400)
            kp = float(sys.argv[2])
            kd = float(sys.argv[3])
            speed = int(sys.argv[4])
            send_cmd(client, {"cmd": "set_pid", "kp": kp, "ki": 0.0, "kd": kd, "speed": speed})
        time.sleep(1)
        client.loop_stop()
        client.disconnect()
        return

    print("Esperando telemetría del robot... (Presiona Ctrl+C para salir)")
    try:
        while running:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()
        print("\nMonitor detenido.")

if __name__ == "__main__":
    main()
