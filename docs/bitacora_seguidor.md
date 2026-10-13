# 🏎️ Bitácora del Proyecto: Robot Seguidor de Línea de Alta Velocidad

**Autor:** Samuel  
**Inicio del Proyecto:** Junio 2026  
**Repositorio de Referencia:** IDLine (código abierto)  
**Herramienta de Diseño Electrónico:** EasyEDA  
**Plataforma de Desarrollo:** ESP32 DevKit V1 (38 pines, Xtensa Dual-Core 240 MHz)

---

## Índice

1. [Descripción General del Proyecto](#1-descripción-general-del-proyecto)
2. [Cronología del Desarrollo](#2-cronología-del-desarrollo)
3. [Fase 1: Investigación y Selección de Componentes](#fase-1-investigación-y-selección-de-componentes)
4. [Fase 2: Diseño del Esquemático](#fase-2-diseño-del-esquemático)
5. [Fase 3: Diseño del PCB (Próxima)](#fase-3-diseño-del-pcb-próxima)
6. [Fase 4: Firmware (Pendiente)](#fase-4-firmware-pendiente)
7. [Documentos de Referencia](#documentos-de-referencia)

---

## 1. Descripción General del Proyecto

Diseño y construcción de un robot seguidor de línea para competencia, basado en la arquitectura del proyecto de código abierto **IDLine**, con las siguientes mejoras y adaptaciones:

- **Mayor potencia de procesamiento:** Migración de ESP32-C3 a ESP32 DevKit V1 (38 pines, Dual-Core 240 MHz).
- **Sistema de visión modular y escalable:** Barra central fija de 8 sensores + dos aletas desmontables de 4 sensores individuales (QRE1113) cada una, sumando hasta 16 canales analógicos a través de un multiplexor CD74HC4067.
- **Doble etapa de alimentación aislada:** Separación de la potencia de motores (V_BATT directo), lógica de control (5V vía Mini-360) y sensores/pantalla (3.3V vía AMS1117-3.3) para eliminar reinicios por Brownout.
- **Telemetría visual a bordo:** Pantalla TFT IPS 1.54" (240×240, ST7789) para visualización en tiempo real de estado de sensores, voltaje de batería y parámetros PID.
- **Algoritmo de control PID** con muestreo analógico de alta velocidad y cálculo de error por promedio ponderado.

El robot permite adaptarse a diferentes niveles de competencia:
- **Modo 8 sensores:** Solo barra central. Para pistas simples con curvas suaves.
- **Modo 16 sensores:** Barra central + aletas laterales. Para pistas complejas con curvas cerradas.

La transición entre modos es física: las aletas se conectan/desconectan mediante conectores de 3 pines.

---

## 2. Cronología del Desarrollo

| Fecha | Hito | Estado |
| :--- | :--- | :---: |
| Jun 2026 | Pruebas iniciales del ESP32 DevKit V1 (LED Blink, verificación de upload) | ✅ |
| Jun – Jul 2026 | Investigación del proyecto IDLine y estudio de su arquitectura | ✅ |
| Jul – Ago 2026 | Selección y adquisición de componentes (motores, sensores, driver, pantalla) | ✅ |
| Ago – Sep 2026 | Diseño del esquemático completo en EasyEDA | ✅ |
| 17/Sep/2026 | Esquemático validado y finalizado (Rev 1.0) | ✅ |
| 20/Sep/2026 | Documentación técnica consolidada (pinout, arquitectura, catálogo) | ✅ |
| 21/Sep/2026 | Revisión técnica de hardware: ratificación divisor 2S (100k/33k), desacoplo TB6612 y taladros SW_EXT | ✅ |
| 24/Sep/2026 | Separación modular en 2 placas: Placa Madre + Placa de Sensores (8 canales activos por conector J_MAIN de 7 pines) | ✅ |
| Oct 2026 | Diseño de distribución en **DIYLC** y armado físico en **Placa Perforada** (componentes Through-Hole) | 🔄 En curso |
| Próximo | Desarrollo del firmware (muestreo, calibración, PID) | ⏳ |
| Próximo | Pruebas en pista y ajuste de constantes PID | ⏳ |

---

## Fase 1: Investigación y Selección de Componentes

### Decisiones de Diseño Clave

**¿Por qué ESP32 DevKit V1 en lugar del ESP32-C3 original del IDLine?**
- Doble núcleo (Dual-Core Xtensa LX6 @ 240 MHz) vs. single-core RISC-V del C3.
- Más pines GPIO disponibles (38 pines vs. ~22 del C3).
- Dos unidades ADC (ADC1 + ADC2) con más canales.
- Mayor ecosistema de librerías y soporte comunitario.
- Compatible con FreeRTOS para separar lazo PID (Core 1) de telemetría/pantalla (Core 0).

**¿Por qué sensores individuales QRE1113 en lugar de una barra QTR-8A completa?**
- Flexibilidad para el diseño modular con aletas desmontables.
- Menor costo unitario y facilidad de reemplazo individual.
- Permite geometrías no lineales (curvatura personalizada de la barra).

**¿Por qué multiplexor CD74HC4067?**
- Un solo pin ADC del ESP32 lee los 16 sensores.
- Evita la limitación de ADC2 cuando Wi-Fi está activo.
- Solo consume 4 GPIOs digitales para selección + 1 ADC.
- Baja resistencia ON (~70Ω a 4.5V), mínima distorsión.

**¿Por qué TB6612FNG en lugar de L298N?**
- MOSFETs internos vs. transistores bipolares: mucho menor caída de tensión.
- Hasta 3.2A de pico por canal (1.2A continuo).
- PWM de hasta 100 kHz (elimina zumbidos audibles).
- Factor de forma compacto y ligero.

### Catálogo de Componentes

La documentación detallada de cada componente (especificaciones técnicas, imágenes y función en el robot) se encuentra en el archivo:

📄 **[catalogo_componentes.md](catalogo_componentes.md)**

---

## Fase 2: Diseño del Esquemático

### Herramienta y Revisión

- **Herramienta:** EasyEDA (editor web)
- **Fecha de finalización:** 17 de septiembre de 2026 (Revisión técnica: 21 de septiembre de 2026)
- **Revisión:** 1.1
- **Autor:** 8samueldavid

### Esquemático Validado

El esquemático completo incluye:
- Sistema de alimentación con tres rieles aislados (V_BATT, 5V, 3.3V)
- Driver de motores TB6612FNG con protecciones de desacople (potencia y lógica)
- Multiplexor CD74HC4067 con canales mapeados
- Pantalla TFT ST7789 por SPI
- Divisor resistivo para monitoreo de batería (100kΩ / 33kΩ)
- Pulsadores de calibración y arranque con pull-ups

### Verificaciones Realizadas

- [x] Todos los pines del ESP32 asignados correctamente (sin conflictos de función)
- [x] GPIO12 (STBY) con pull-down de 10kΩ (compatible con secuencia de boot)
- [x] Lecturas analógicas exclusivamente en ADC1 (GPIO36 y GPIO39)
- [x] Capacitores de desacople en VM del TB6612 (100nF + 470µF)
- [x] Capacitor cerámico de desacoplo en lógica VCC del TB6612 (100nF entre Pin 2 y Pin 3)
- [x] Capacitores de entrada y salida del AMS1117-3.3 (10µF / 22µF)
- [x] Diodo Schottky 1N5819 de aislamiento USB/Batería
- [x] Divisor de tensión dimensionado para 2S Li-ion (100kΩ / 33kΩ $\rightarrow$ 2.08V máx en rango lineal óptimo del ADC)
- [x] Switch externo de panel clasificado $\ge 3$ A DC
- [x] Pin EN del multiplexor conectado a GND (siempre habilitado)

---

## Fase 3: Simulación en DIYLC y Armado en Placa Perforada (En Curso)

### Arquitectura Física en 2 Placas Separadas

1. **Placa Madre (Chasis):**
   - Módulos: `ESP32 DevKit V1 (38p)`, `TB6612FNG`, `Mini-360 (5V)`, `AMS1117-3.3 (VCC_3V3)`.
   - Pasivos Through-Hole (con patitas): Divisor `R1=100kΩ` / `R2=33kΩ` + `C1=100nF`, pull-ups `R3=10kΩ`, `R4=10kΩ`, pull-down `R5=10kΩ`, diodo `D1=1N5819`, capacitores `C2=100nF`, `C3=470µF`, `C5=100nF`, `C7=10µF`, `C9=22µF`.
   - Conectores: `XT30` + `SW_EXT`, `J11` (Pantalla TFT 8p), `MOTOR_IZQ` / `MOTOR_DER`, y conector inter-placa **`J_MAIN` (7 pines)**.
2. **Placa de Sensores (8 Canales Activos):**
   - Módulo `CD74HC4067` (`U3`) + capacitor `C4=100nF` + Header 11 pines (`U5`) para la barra central de 8 sensores (conectada a `C4–C11`).
   - Canales sin usar (`C0–C3` y `C12–C15`) puenteados a `GND` (sin aletas por ahora).
   - Conector **`J_MAIN` (7 pines: `GND`, `VCC_3V3`, `MUX_SIG`, `MUX_S0..S3`)** hacia la Placa Madre.

---

## Fase 4: Firmware (Pendiente)

### Arquitectura de Software Planificada

- **Framework:** Arduino / PlatformIO para ESP32
- **Núcleo 1 (Core 1):** Lazo de control PID a alta frecuencia (≥1 kHz)
  - Barrido de los 8 canales activos (`C4` a `C11`) del multiplexor
  - Normalización de lecturas (calibración blanco/negro)
  - Cálculo de error por promedio ponderado
  - Generación de señales PWM al TB6612
- **Núcleo 0 (Core 0):** Tareas secundarias
  - Actualización de pantalla TFT
  - Monitoreo de voltaje de batería
  - Gestión de pulsadores (debounce + estado)

### Módulos de Firmware Planificados

1. `sensors.h/cpp` — Lectura y calibración de los sensores a través del multiplexor
2. `motors.h/cpp` — Control del TB6612FNG (dirección, velocidad, freno)
3. `pid.h/cpp` — Algoritmo PID con anti-windup
4. `display.h/cpp` — Interfaz gráfica en TFT ST7789
5. `battery.h/cpp` — Monitoreo de tensión con filtro de media móvil
6. `config.h` — Definiciones de pines, constantes PID y parámetros de calibración

---

## Documentos de Referencia

| Documento | Descripción |
| :--- | :--- |
| [GEMINI.md](../GEMINI.md) | Fuente de la verdad y contexto maestro del proyecto |
| [catalogo_componentes.md](catalogo_componentes.md) | Catálogo técnico de los componentes principales con especificaciones e imágenes |
| [guia_placa_madre_y_ensamble.md](../hardware/guia_placa_madre_y_ensamble.md) | Guía de conexiones en placa perforada, componentes pasivos y checklist de taller |
| [guia_placa_sensores_8ch.md](../hardware/guia_placa_sensores_8ch.md) | Plan y pinout de la Placa de Sensores de 8 canales (`J_MAIN` 7p) |
| [SCH_IDLine_2026-09-21.json](../hardware/esquematico/SCH_IDLine_2026-09-21.json) | Esquemático base validado en EasyEDA |

---

*Última actualización: Octubre de 2026*
