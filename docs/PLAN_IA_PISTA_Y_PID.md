# Plan de Implementación (`/swarm`) — Visión IA para Pista Real + Ajuste PID y UI

> **Objetivo para la nueva conversación:** Ejecutar este plan con `/swarm` dividiendo el trabajo por archivo sin colisiones, para integrar reconstrucción asistida por foto + Gemini Vision API en Django/Dash, pulir el feedback de botones y preparar el ajuste PID para la pista de la universidad.

---

## 1. Arquitectura Propuesta (IA Multi-Vista + Odometría + Django)

1. **Entrada (2 a 4 fotos desde esquinas opuestas):** El usuario sube de **2 a 4 fotos** de la pista real tomadas desde esquinas opuestas (sin necesidad de colocar objetos extra; la IA usa los propios bordes rectangulares de la lona/tablero blanco y cruza lo que se ve cerca en cada vista para compensar la perspectiva).
2. **Backend (`server/telemetria/`):**
   - Nuevo modelo `PistaReferencia` (por `track_id`): almacena la polilínea normalizada `[(x, y), ...]` consolidada desde las múltiples vistas y metadatos.
   - Nuevo endpoint `POST /api/pista/referencia/` (y servicio `server/telemetria/vision_ai.py`):
     - Envía las 2–4 imágenes juntas en una única llamada multimodal a **Gemini API** (leyendo `GEMINI_API_KEY` de variable de entorno) con prompt estructurado JSON para triangular las vistas opuestas y extraer el contorno de la pista negra en vista cenital normalizada (`0..1`).
3. **Alineación Geométrica (`server/telemetria/odometry.py`):**
   - Función `align_trajectory_to_reference(trajectory, reference_points)`:
     - Aplica ajuste 2D (traslación, rotación y escala uniforme) de la trayectoria odométrica sobre la polilínea extraída de las fotos para compensar la deriva acumulada sin encoders.
4. **Dashboard (`server/dashboard/app.py`):**
   - Componente `dcc.Upload(multiple=True)` ("SUBIR 2-4 FOTOS DE PISTA") en la tarjeta de sesión de pista.
   - Superposición en `MAPA DE PISTA RECONSTRUIDO`: traza punteada gris/verde para la **Pista Real (IA)** y traza azul para la **Trayectoria del Robot**.
   - Rediseño del feedback visual de botones según preferencia final de Samuel (ej. spinner/estado "Enviando..." + confirmación clara).

---

## 2. División del `/swarm` (Sin Colisiones de Archivos)

| Agente | Propiedad Exclusiva | Tareas |
| :--- | :--- | :--- |
| **`vision-backend`** | `server/telemetria/vision_ai.py`, `models.py`, `migrations/`, `views.py`, `urls.py` | Crear `PistaReferencia`, endpoint `POST /api/pista/referencia/`, cliente REST ligero para Gemini API (leyendo `os.environ["GEMINI_API_KEY"]`) y validación JSON de la polilínea. |
| **`odometry-fit`** | `server/telemetria/odometry.py` | Implementar `align_trajectory_to_reference()` (ajuste de escala/rotación/traslación 2D contra la polilínea de referencia) manteniendo compatibilidad con `reconstruct_trajectory()`. |
| **`dash-ui`** | `server/dashboard/app.py` | Agregar `dcc.Upload` para la foto de la pista, dibujar la referencia IA en el mapa 2D y pulir el feedback visual de los botones. |
| **`verifier`** | Solo lectura (`server/telemetria/tests.py`) | Verificar migraciones, correr `manage.py test telemetria` (con mock de Gemini API) y validar que `app.py` cargue sin errores antes de subir a PythonAnywhere. |

---

## 3. Protocolo de Ajuste PID en la Pista de la U

1. **Baterías al 100% (~8.4 V)** antes de empezar para no calibrar sobre voltaje caído.
2. **Calibración en sitio:** Ejecutar `CALIBRAR` bajo la iluminación del salón de la universidad.
3. **Pruebas escalonadas observando `HISTORIAL DE MOTORES Y LINEA`:**
   - Arrancar en `ARQUITEC (500 PWM)` → revisar si `posicion` oscila en recta (ajustar `Kp`/`Kd`).
   - Subir a `SEGURO (580 PWM)` → `CARRERA (680 PWM)` → `ATAQUE (750 PWM)`.
   - Usar el parámetro de reducción en curva en `firmware/lib/PID/pid.cpp` si entra pasado a curvas cerradas, manteniendo alta velocidad en rectas.

---

## 4. Prompt listo para pegar en la nueva conversación
```text
/swarm Lee docs/PLAN_IA_PISTA_Y_PID.md y ejecútalo con el swarm:
1. Integra la subida de foto de pista + extracción de contorno con Gemini API (usando variable de entorno GEMINI_API_KEY) + alineación en odometry.py + visualización en Dash.
2. Verifica con tests (mockeando la API de Gemini) y déjalo listo para subir a PythonAnywhere.
```
