import sys
import os
import time
import datetime
import serial
import serial.tools.list_ports

def find_esp32_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        desc = p.description.lower()
        if "ch340" in desc or "cp210" in desc or "usb-serial" in desc or "uart" in desc or "serial" in desc:
            return p.device
    if ports:
        return ports[0].device
    return None

def main():
    port = sys.argv[1] if len(sys.argv) > 1 else find_esp32_port()
    if not port:
        print("No se encontro puerto COM para el ESP32. Conecta el cable USB.")
        print("Uso: python dump_runs.py [COM_PORT]")
        return

    baud = 115200
    print(f"Conectando a {port} a {baud} baudios...")
    try:
        ser = serial.Serial(port, baud, timeout=2.0)
    except Exception as e:
        print(f"Error al abrir puerto {port}: {e}")
        return

    time.sleep(1.0)
    ser.reset_input_buffer()

    print("Enviando comando 'dump' a la caja negra del robot...")
    ser.write(b"dump\n")
    ser.flush()

    lines = []
    t0 = time.time()
    header_found = False

    while time.time() - t0 < 5.0:
        raw = ser.readline().decode("utf-8", errors="ignore").strip()
        if not raw:
            continue
        if raw.startswith("#run"):
            header_found = True
            lines.append(raw)
        elif header_found:
            lines.append(raw)
            if raw == "#end":
                break

    ser.close()

    if not header_found or len(lines) <= 2:
        print("No se encontraron carreras grabadas en la caja negra.")
        print("Asegurate de haber corrido al menos una vez en modo RUNNING antes de volcar.")
        return

    os.makedirs("runs", exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join("runs", f"carrera_{ts}.csv")

    with open(out_path, "w", encoding="utf-8") as f:
        for l in lines:
            f.write(l + "\n")

    print(f"\n=======================================================")
    print(f"  CAJA NEGRA: CARRERA DESCARGADA EXITOSAMENTE")
    print(f"  Archivo guardado: {out_path}")
    print(f"=======================================================")

    header = lines[0]
    print(f"\nEncabezado: {header}")

    # Analizar datos
    samples = []
    line_losses = []
    prev_status = 0

    for l in lines[2:-1]: # saltar #run y header t_ms,pos...
        parts = l.split(",")
        if len(parts) >= 5:
            try:
                t_ms = int(parts[0])
                pos = int(parts[1])
                m1 = int(parts[2])
                m2 = int(parts[3])
                status = int(parts[4])
                samples.append((t_ms, pos, m1, m2, status))
                if status != 0 and prev_status == 0:
                    line_losses.append((t_ms, pos, m1, m2, status))
                prev_status = status
            except ValueError:
                pass

    if samples:
        total_time_s = samples[-1][0] / 1000.0
        print(f"Duracion total de carrera: {total_time_s:.2f} segundos ({len(samples)} muestras)")
        print(f"Eventos de perdida de linea: {len(line_losses)}")
        if line_losses:
            print("\nDetalle de las salidas de pista:")
            for idx, (t, p, m1, m2, st) in enumerate(line_losses, 1):
                lado = "Izquierda" if st == 1 else "Derecha"
                print(f"  {idx}. A los {t/1000.0:.2f}s | Posicion:{p:+4d} | Salio por: {lado:9s} | M1:{m1} M2:{m2}")
        else:
            print(">> Vuelta limpia: ¡Cero perdidas de linea detectadas!")
    print(f"=======================================================\n")

if __name__ == "__main__":
    main()
