# 🧠 Contexto Maestro del Proyecto — Robot Seguidor de Línea (IDLine ESP32 Edition)

> **INSTRUCCIÓN CRÍTICA PARA EL AGENTE (ANTIGRAVITY):**  
> Este archivo (`GEMINI.md`) es la **Única Fuente de la Verdad (Single Source of Truth)** del proyecto de Samuel. Léelo y respétalo estrictamente en cada respuesta para mantener 100% de precisión técnica y no perder contexto.

---

## 1. Estado Actual y Método de Construcción (¡MUY IMPORTANTE!)

- **Fase actual:** Diseño de ubicación/cableado en **DIYLC (DIY Layout Creator)** para **ensamble físico en Placa Perforada (Perfboard / Baquelita universal)**.
- **NO asumir PCB SMD fabricado en fábrica** a menos que Samuel lo pida expresamente. Aunque existe un esquemático base hecho en EasyEDA (`hardware/esquematico/SCH_IDLine_2026-09-21.json`), el armado real actual se hace con:
  - **Módulos Breakout comerciales** (ESP32 DevKit V1 38p, TB6612FNG, Mini-360, CD74HC4067, Barra de 8 sensores, Pantalla TFT 1.54" ST7789).
  - **Componentes pasivos Through-Hole (con patitas)** para resistencias, capacitores y diodo Schottky sobre placa perforada.
  - **Regulador de 3.3V (`AMS1117-3.3`)** en módulo o adaptado para placa perforada.
- **División Física en 2 Placas Separadas (unidas por cable `J_MAIN` de 7 pines):**
  1. **Placa Madre (Chasis):** Contiene el ESP32 (38 pines), Driver TB6612FNG, Regulador Buck Mini-360 (5V), Regulador AMS1117-3.3 (`VCC_3V3`), Divisor de batería (`100kΩ / 33kΩ`), Diodo `1N5819`, Pulsadores (`BTN_CALIB`, `BTN_START`), Conector de Pantalla TFT (`J11`), entrada de batería (`XT30` + `SW_EXT`) y conector `J_MAIN` (7 pines).
  2. **Placa de Sensores (Frontal a ras de suelo):** Contiene **únicamente la configuración de 8 canales activos** por ahora (sin aletas laterales `J0–J7`):
     - Módulo Multiplexor **CD74HC4067 (`U3`)**.
     - Capacitor cerámico de desacoplo **`C4` (100 nF)** entre `VCC` y `GND` del MUX.
     - Header hembra de 11 pines (`U5`) para la **Barra Central de 8 Sensores**, conectada a los canales **`C4` a `C11`** del MUX.
     - Los canales **`C0–C3`** y **`C12–C15`** (aletas no instaladas) se conectan a **`GND`** para evitar entradas flotantes.
     - Conector **`J_MAIN` (7 pines)** hacia la Placa Madre.

---

## 2. Arquitectura de Potencia (3 Rieles Aislados)

Para evitar reinicios por *Brownout* y ruido inductivo de los motores N20:

1. **Riel `V_BATT` (7.4V nominal – 8.4V máx, Batería 2S Li-Ion Samsung 18650-30Q):**
   - Pasa por el interruptor externo **`SW_EXT`** ($\ge 3\,\text{A DC}$, cables AWG 18–20).
   - Alimenta directamente **`VM`** del driver **TB6612FNG** (con filtro local **`C2` = 100 nF cerámico** + **`C3` = 470 µF electrolítico** entre `VM` y `GND`).
   - Alimenta **`IN+`** del convertidor Buck **Mini-360** (`U2`).
   - Alimenta el divisor resistivo de monitoreo de batería: **`R1` = 100 kΩ** (arriba, a `V_BATT`) y **`R2` = 33 kΩ** (abajo, a `GND`) + filtro **`C1` = 100 nF** en paralelo con `R2`. Punto medio va a `BATT_SENSE` (`GPIO36 / VP`). Escala: $8.4\,\text{V} \rightarrow 2.08\,\text{V}$.
2. **Riel `5V` (Salida del Mini-360):**
   - El Mini-360 se calibra con multímetro a **~5.35 V** antes de conectarlo, para que tras la caída del diodo Schottky **`D1` (1N5819)** entregue **~4.95 V – 5.0 V** limpios.
   - Alimenta el pin **`VIN`** del ESP32 (el diodo `1N5819` evita retorno de corriente cuando se conecta el cable USB-C al PC).
   - Alimenta la entrada **`IN`** del regulador lineal **AMS1117-3.3 (`U7`)** con su capacitor de entrada **`C7` = 10 µF** a `GND`.
3. **Riel `VCC_3V3` Aislado (Salida del AMS1117-3.3):**
   - Filtrado a la salida con **`C9` = 22 µF (o 10 µF)** a `GND`.
   - Alimenta **exclusivamente**:
     - Lógica **`VCC`** del TB6612FNG (con capacitor local **`C5` = 100 nF** entre `VCC` y `GND`).
     - Pantalla **TFT ST7789** (`VCC` y `BL`).
     - Resistencias pull-up de los pulsadores (**`R3` = 10 kΩ** para `BTN_CALIB` y **`R4` = 10 kΩ** para `BTN_START`).
     - Placa de Sensores vía pin 2 de `J_MAIN` (alimenta el módulo **CD74HC4067** + **Barra de 8 sensores**).
   - **Nota:** El pin `3V3` interno del ESP32 **NO se conecta a nada** (queda libre para no sobrecargar el regulador interno del DevKit).

---

## 3. Pinout Maestro Inamovible — ESP32 DevKit V1 (38 Pines)

| Pin ESP32 | GPIO | Etiqueta Red | Destino / Conexión Física | Notas Críticas |
| :--- | :--- | :--- | :--- | :--- |
| **VP** | `GPIO36` | `BATT_SENSE` | Punto medio divisor `R1 (100k)` / `R2 (33k)` + `C1 (100nF)` | Solo entrada (ADC1_CH0). Máx 2.08V @ 8.4V. |
| **VN** | `GPIO39` | `MUX_SIG` | Pin 3 de `J_MAIN` $\leftarrow$ Pin `SIG` del MUX CD74HC4067 | Solo entrada (ADC1_CH3). No conflicta con Wi-Fi. |
| **P32** | `GPIO32` | `BTN_CALIB` | Pulsador `SW1` (a GND) + Pull-up `R3 (10k)` a `VCC_3V3` | Activo en LOW. |
| **P33** | `GPIO33` | `BTN_START` | Pulsador `SW2` (a GND) + Pull-up `R4 (10k)` a `VCC_3V3` | Activo en LOW. |
| **P27** | `GPIO27` | `MUX_S0` | Pin 4 de `J_MAIN` $\rightarrow$ Pin `S0` del MUX | Bit 0 selector canal. |
| **P14** | `GPIO14` | `MUX_S1` | Pin 5 de `J_MAIN` $\rightarrow$ Pin `S1` del MUX | Bit 1 selector canal. |
| **P13** | `GPIO13` | `MUX_S2` | Pin 6 de `J_MAIN` $\rightarrow$ Pin `S2` del MUX | Bit 2 selector canal. |
| **P15** | `GPIO15` | `MUX_S3` | Pin 7 de `J_MAIN` $\rightarrow$ Pin `S3` del MUX | Bit 3 selector canal. |
| **P12** | `GPIO12` | `STBY` | Pin `STBY` del TB6612FNG + Pull-down `R5 (10k)` a `GND` | **Strapping pin:** `R5` asegura LOW al arrancar. |
| **P21** | `GPIO21` | `M1_IN1` | Pin `AIN1` del TB6612FNG | Dirección A Motor Izquierdo. |
| **P22** | `GPIO22` | `M1_IN2` | Pin `AIN2` del TB6612FNG | Dirección B Motor Izquierdo. |
| **P4** | `GPIO4` | `M1_PWM` | Pin `PWMA` del TB6612FNG | Velocidad PWM Motor Izquierdo. |
| **P25** | `GPIO25` | `M2_IN1` | Pin `BIN1` del TB6612FNG | Dirección A Motor Derecho. |
| **P26** | `GPIO26` | `M2_IN2` | Pin `BIN2` del TB6612FNG | Dirección B Motor Derecho. |
| **P17** | `GPIO17` | `M2_PWM` | Pin `PWMB` del TB6612FNG | Velocidad PWM Motor Derecho. |
| **P18** | `GPIO18` | `SPI_SCK` | Pin `SCL` de Pantalla TFT (`J11.3`) | Bus VSPI Hardware. |
| **P23** | `GPIO23` | `SPI_MOSI` | Pin `SDA` de Pantalla TFT (`J11.4`) | Bus VSPI Hardware. |
| **P16** | `GPIO16` | `TFT_RST` | Pin `RST` de Pantalla TFT (`J11.5`) | Reset pantalla. |
| **P19** | `GPIO19` | `TFT_DC` | Pin `DC` de Pantalla TFT (`J11.6`) | Data/Command pantalla. |
| **P5** | `GPIO5` | `TFT_CS` | Pin `CS` de Pantalla TFT (`J11.7`) | Chip Select pantalla. |

---

## 4. Interfaces de Conectores Clave

### A. Conector Inter-Placa `J_MAIN` (7 pines — une Placa Madre con Placa de Sensores)
| Pin | Señal | Dirección | Conexión en Placa Madre | Conexión en Placa de Sensores |
| :---: | :--- | :--- | :--- | :--- |
| **1** | `GND` | Retorno | Tierra común (`GND`) | `GND` del MUX (`U3`), `U5.1`, `C4`, y canales `C0–C3`, `C12–C15` |
| **2** | `VCC_3V3` | Madre $\rightarrow$ Sensores | Salida 3.3V del `AMS1117-3.3` | `VCC` del MUX (`U3`), `U5.2`, `U5.11`, y `C4` |
| **3** | `MUX_SIG` | Sensores $\rightarrow$ Madre | `ESP32 GPIO39 (VN)` | Pin `SIG` del MUX (`U3`) |
| **4** | `MUX_S0` | Madre $\rightarrow$ Sensores | `ESP32 GPIO27` | Pin `S0` del MUX (`U3`) |
| **5** | `MUX_S1` | Madre $\rightarrow$ Sensores | `ESP32 GPIO14` | Pin `S1` del MUX (`U3`) |
| **6** | `MUX_S2` | Madre $\rightarrow$ Sensores | `ESP32 GPIO13` | Pin `S2` del MUX (`U3`) |
| **7** | `MUX_S3` | Madre $\rightarrow$ Sensores | `ESP32 GPIO15` | Pin `S3` del MUX (`U3`) |

### B. Conector Barra Central de 8 Sensores `U5` (Header 11 pines en Placa de Sensores)
- `Pin 1`: `GND`
- `Pin 2`: `VCC_3V3`
- `Pines 3 a 10`: Salidas analógicas de los 8 sensores $\rightarrow$ van a **`C4, C5, C6, C7, C8, C9, C10, C11`** del MUX `CD74HC4067`.
- `Pin 11`: `VCC_3V3` (o control LED IR; recordar puentear con estaño el jumper `3.3V` en la barra física).

### C. Conector Pantalla TFT 1.54" ST7789 `J11` (Header 8 pines en Placa Madre)
- `1: GND` | `2: VCC (VCC_3V3)` | `3: SCL (GPIO18)` | `4: SDA (GPIO23)` | `5: RST (GPIO16)` | `6: DC (GPIO19)` | `7: CS (GPIO5)` | `8: BL (VCC_3V3)`

---

## 5. Estructura de Carpetas del Proyecto y Reglas de Consulta

```text
├── GEMINI.md                               # Este archivo (Memoria permanente del agente)
├── README.md                               # Resumen ejecutivo del proyecto
├── docs/                                   # Documentación general y catálogo
│   ├── bitacora_seguidor.md                # Historial y decisiones de diseño
│   ├── catalogo_componentes.md             # Especificaciones detalladas de cada módulo y fotos
│   ├── Catalogo_Componentes_Seguidor_Linea.docx
│   └── assets/                             # Fotografías recortadas de los módulos reales
├── hardware/                               # Guías de armado físico, DIYLC y Esquemático
│   ├── guia_placa_madre_y_ensamble.md      # Reglas de armado, componentes pasivos y checklist físico
│   ├── guia_placa_sensores_8ch.md          # Diseño específico de la Placa de Sensores de 8 canales
│   ├── diylc/                              # Layouts de placa perforada en DIY Layout Creator (.diy)
│   └── esquematico/                        # SCH_IDLine_2026-09-21.json (Esquemático base en EasyEDA)
├── firmware/                               # Código fuente para el ESP32 (Arduino / PlatformIO)
├── tools/                                  # Scripts de soporte
│   └── easyeda_audit/                      # analyzer.py y netlist_report.md (auditoría de redes del JSON)
└── reference/                              # ⚠️ ARCHIVOS EXTERNOS DE REFERENCIA
    └── idline_original/                    # Repositorio original IDLine (ESP32-C3 / ESP32-S2)
```

### 🚫 Regla de Exclusión para evitar Pérdida de Contexto
- **NUNCA** uses archivos dentro de `reference/idline_original/` para responder sobre pines, esquemáticos o conexiones del robot de Samuel (ese repositorio usa ESP32-C3/S2 y otra distribución). Solo consúltalo si Samuel pide explícitamente revisar cómo hacía algo el IDLine original.
