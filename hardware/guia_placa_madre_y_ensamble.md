# 🛠️ Guía Técnica: Placa Madre, Simulación en DIYLC y Ensamble en Placa Perforada
**Proyecto:** Robot Seguidor de Línea de Competencia (Basado en IDLine)  
**Controlador:** ESP32 DevKit V1 (38 pines) | **Método Actual:** Simulación en **DIYLC** + Armado en **Placa Perforada (Through-Hole)**  
**Esquemático Base:** `hardware/esquematico/SCH_IDLine_2026-09-21.json`

---

## 0. Inventario Exacto para la Placa Madre (Placa Perforada / DIYLC)

Al diseñar el layout en **DIYLC** sobre placa perforada (paso 2.54 mm / 0.1"), estos son todos los bloques que van en la **Placa Madre** (el MUX `U3`, `C4` y el conector `U5` van aparte en la [Placa de Sensores](guia_placa_sensores_8ch.md)):

### Módulos y Conectores en Placa Madre
* **`U_ESP32`**: ESP32 DevKit V1 de 38 pines (2 filas de 19 pines, separación entre filas: 10 espacios / 25.4 mm).
* **`U1`**: Módulo Driver TB6612FNG (2 filas de 8 pines).
* **`U2`**: Módulo Buck Mini-360 (`IN+`, `IN-`, `OUT+`, `OUT-`).
* **`U7`**: Regulador Lineal `AMS1117-3.3` (en módulo o adaptado a pines 2.54 mm: `GND`, `OUT = VCC_3V3`, `IN = 5V`).
* **`J_MAIN`**: Header macho / JST-XH de **7 pines** hacia la Placa de Sensores (`1:GND`, `2:VCC_3V3`, `3:MUX_SIG`, `4:S0`, `5:S1`, `6:S2`, `7:S3`).
* **`J11`**: Header hembra de **8 pines** para la Pantalla TFT 1.54" ST7789.
* **`MOTOR_IZQ` y `MOTOR_DER`**: Headers de 2 pines hacia los motores N20.
* **`CN1` + `SW_EXT`**: Entrada de batería 2S (XT30) pasando por el interruptor principal.
* **`SW1` (`BTN_CALIB`) y `SW2` (`BTN_START`)**: 2 pulsadores táctiles Through-Hole.

### Componentes Pasivos Through-Hole (con patitas) en Placa Madre
| Ref | Valor | Tipo | Dónde se conecta exactamente |
| :---: | :--- | :--- | :--- |
| **`R1`** | `100 kΩ` | Resistencia TH | Entre `V_BATT` (después del switch) y el pin `VP (GPIO36)` del ESP32. |
| **`R2`** | `33 kΩ` | Resistencia TH | Entre el pin `VP (GPIO36)` del ESP32 y `GND`. |
| **`C1`** | `100 nF` (código 104) | Cerámico TH | En paralelo con `R2`: entre `VP (GPIO36)` y `GND` (filtra ruido en lectura de batería). |
| **`R3`** | `10 kΩ` | Resistencia TH | Pull-up de `BTN_CALIB`: entre `GPIO32` y `VCC_3V3`. |
| **`R4`** | `10 kΩ` | Resistencia TH | Pull-up de `BTN_START`: entre `GPIO33` y `VCC_3V3`. |
| **`R5`** | `10 kΩ` | Resistencia TH | Pull-down de `STBY`: entre `GPIO12` (`STBY`) y `GND`. |
| **`D1`** | `1N5819` | Diodo Schottky TH | Ánodo a `OUT+` del Mini-360; Cátodo (franja) al riel `5V` (`ESP32 VIN` y `AMS1117 IN`). |
| **`C2`** | `100 nF` (código 104) | Cerámico TH | Muy cerca del pin `VM` y `GND` del TB6612FNG. |
| **`C3`** | `470 µF` (≥16V) | Electrolítico TH | En paralelo con `C2`: positivo (`+`) a `VM` (`V_BATT`) y negativo (`-`) a `GND` del TB6612FNG. |
| **`C5`** | `100 nF` (código 104) | Cerámico TH | Pegado entre el pin `VCC` (lógica 3.3V) y `GND` del TB6612FNG. |
| **`C7`** | `10 µF` | Electrolítico/Cerámico TH | Entrada del `AMS1117-3.3`: entre el riel `5V` y `GND`. |
| **`C9`** | `22 µF` (o `10 µF`) | Electrolítico/Tántalo TH | Salida del `AMS1117-3.3`: entre `VCC_3V3` y `GND`. |

---

## 1. Calibres de Cable (Placa Perforada) / Anchos de Pista (PCB)

* **Líneas de Potencia (`POWER` — `V_BATT`, `5V`, `GND` de potencia y salidas a motores `A1, A2, B1, B2`):**
  * **En Placa Perforada / DIYLC:** Usar cable calibre **20 AWG a 22 AWG** o puentes gruesos de estaño en la cara inferior.
  * **En PCB EasyEDA:** Ancho de pista mínimo **1.5 mm a 2.0 mm** (60 a 80 mil).
* **Líneas de Señal (`SIGNAL` — SPI, selectores MUX, `MUX_SIG`, `BATT_SENSE`, pulsadores):**
  * **En Placa Perforada / DIYLC:** Cable delgado **26 AWG a 30 AWG** (cable tipo wrapping o filamento aislado).
  * **En PCB EasyEDA:** Ancho de pista **0.254 mm** (10 mil) o **0.3 mm** (12 mil).

---

## 2. Pautas Críticas de Ubicación (Placement) y Ruteo

1. **Desacoplo del TB6612FNG (`C5`, 100 nF):**
   * Debe colocarse físicamente **a milímetros del pin 2 (`VCC`) y pin 3 (`GND`)** del módulo TB6612 para absorber el ruido digital de conmutación.
2. **Capacitores de Batería (`C2` de 100 nF y `C3` de 470 µF):**
   * Ubícalos inmediatamente a la entrada del pin `VM` del TB6612, minimizando la distancia hacia las bornas de motor.
3. **Alivio Térmico del AMS1117-3.3 (`U7`):**
   * Disipará ~0.6 W en régimen continuo.
   * Conecta el **Pad 4 (Tab grande / VCC_3V3)** a un plano o polígono de cobre amplio con varias vías disipadoras hacia la capa inferior para evacuar calor.
4. **Plano de Masa (GND Plane) y Retorno de Motores:**
   * Genera un plano de masa sólido en la capa inferior (**Bottom Layer**).
   * **Regla de oro contra Ground Bounce:** La corriente de retorno de los motores N20 jamás debe fluir por debajo de la pista analógica `MUX_SIG` (GPIO39) ni del divisor `BATT_SENSE`. Mantén la zona de potencia (batería, switch, driver, motores) confinada en un extremo del PCB, separada de la electrónica analógica/digital.
5. **Conector XT30PW-M (`CN1`):**
   * Asegura que los pads mecánicos (pines 3 y 4) tengan cobre conectado a tierra o islas metálicas con buena superficie de soldadura para que la tracción del cable de batería no arranque las pistas eléctricas.
6. **Conector SW_EXT:**
   * Aumenta el diámetro de los taladros a **1.2 mm – 1.5 mm** para permitir soldar cables de calibre 18–20 AWG hacia el interruptor externo.

---

## 3. Checklist de Taller y Ensamble Físico (Antes y Durante el Armado)

- [ ] **Barra Central (8路寻线模块 / U5):**  
  Puentear con una gota de estaño los dos pads con la serigrafía **`3.3v`** (en la esquina superior izquierda de la placa). Vienen abiertos de fábrica; sin ese puente los LEDs IR reciben corriente insuficiente.
- [ ] **Calibración del Regulador Buck Mini-360:**  
  Antes de soldarlo a la placa o antes de encender el circuito por primera vez, alimentar el Mini-360 con la batería y girar el tornillo del potenciómetro multivuelta hasta medir exactamente **~5.35 V** en su salida (`OUT+`). Esto compensa la caída del diodo Schottky D1 y entrega 4.95 V estables al riel de 5V.
- [ ] **Capacitores de Supresión en Motores N20:**  
  Soldar un capacitor cerámico de **100 nF** directamente en las terminales traseras de latón de cada micromotor N20 (con opción de dos de 10 nF desde cada terminal hacia la carcasa metálica).
- [ ] **Polaridad del Tántalo C9 (22 µF CASE-A_3216):**  
  En tántalo SMD, **la franja marcada en el cuerpo es el ÁNODO (+)**. Debe coincidir con el Pad 1 conectado a `VCC_3V3`.
- [ ] **Polaridad del Electrolítico C3 (470 µF TH):**  
  La pata larga (+) va al pad cuadrado (`V_BATT`) y la franja blanca (-) va al pad redondo (`GND`).
- [ ] **Interruptor de Encendido:**  
  Utilizar un interruptor de palanca/rocker externo clasificado para **≥ 3 A a 5 A DC** para soportar el *inrush current* de carga de C3 y las corrientes de pico de los motores.

---

## 4. Notas para el Firmware

1. **Lectura Continua de Sensores:**  
   Los canales analógicos van del `S0` (extremo exterior izquierdo) al `S15` (extremo exterior derecho) de forma estrictamente monótona. El cálculo de error ponderado no requiere remapeo de índices.
2. **Corte por Bajo Voltaje (Protección de Celdas 18650 sin BMS):**  
   Monitorear `BATT_SENSE` (GPIO36). Si la lectura cae por debajo de **6.4 V** (3.2 V por celda), detener motores (`STBY` a LOW), deshabilitar periféricos y emitir alerta en pantalla/buzzer para evitar sobredescarga química destructiva.
3. **Pines de Strapping:**  
   `GPIO12` (STBY) tiene pull-down de 10 kΩ a GND y el módulo TB6612 no tiene pull-up interno. El ESP32 arrancará con flash a 3.3 V sin riesgo de bootloop.
