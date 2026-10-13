# 📌 Mapa Maestro de Conexiones y Coordenadas DIYLC (`SCH_IDLine_2026-10-12.json`)

**Fuente única de redes:** [`hardware/esquematico/SCH_IDLine_2026-10-12.json`](esquematico/SCH_IDLine_2026-10-12.json)  
**Distribución física:** 3 niveles en Placa Perforada (Piso 1: Placa Madre | Piso 2: Pantalla + Botones | Punta Frontal: Sensores + MUX)

---

## 1. Coordenadas de `U_ESP32` (`IC1`) en Placa Madre (Piso 1)

* **Posición actual en DIYLC:** Filas **`A` a `S`** (19 pines por lado), **Columna `12`** (Izquierda) y **Columna `22`** (Derecha).
* **Zócalos hacia el Piso 2:** **Columna `11`** (Izquierda: `F11–H11`) y **Columna `23`** (Derecha: `A23–B23`, `G23–J23`, `L23`).

| Fila DIYLC | Pin Izq (`Col 12`) | Red en `SCH_IDLine_2026-10-12.json` | Destino Exacto | Pin Der (`Col 22`) | Red en `SCH_IDLine_2026-10-12.json` | Destino Exacto |
| :---: | :--- | :--- | :--- | :--- | :--- | :--- |
| **`A`** | `3V3` | *(NC)* | Sin conectar | `GND` | **`GND`** | Puente a **`A23`** (`J11.1`) y Tierra común |
| **`B`** | `EN` | *(NC)* | Sin conectar | `MOSI/P23` | **`SPI_MOSI`** | Puente a **`B23`** $\rightarrow$ `J11.4 (SDA)` |
| **`C`** | `VP` | **`BATT_SENSE`** | `R1.1`, `R2.2`, `C1.2` | `SCL/P22` | **`M1_IN2`** | `U1.15 (AIN2)` en **`W15`** |
| **`D`** | `VN` | **`MUX_SIG`** | `U3.24 (SIG)` vía `J_MAIN.3` | `TX` | *(NC)* | Sin conectar |
| **`E`** | `P34` | *(NC)* | Sin conectar | `RX` | *(NC)* | Sin conectar |
| **`F`** | `P35` | *(NC)* | Sin conectar *(Ojo: **`F11`** lleva `VCC_3V3`)* | `SDA/P21` | **`M1_IN1`** | `U1.14 (AIN1)` en **`W16`** |
| **`G`** | `P32` | **`BTN_CALIB`** | Puente a **`G11`** $\rightarrow$ `SW1.2`, `R3.2` | `GND` | **`GND`** | Puente a **`G23`** (`GND` Piso 2) y Tierra común |
| **`H`** | `P33` | **`BTN_START`** | Puente a **`H11`** $\rightarrow$ `SW2.2`, `R4.2` | `MISO/P19` | **`TFT_DC`** | Puente a **`H23`** $\rightarrow$ `J11.6 (DC)` |
| **`I`** | `P25` | **`M2_IN1`** | `U1.12 (BIN1)` en **`W18`** | `SCK/P18` | **`SPI_SCK`** | Puente a **`I23`** $\rightarrow$ `J11.3 (SCL)` |
| **`J`** | `P26` | **`M2_IN2`** | `U1.11 (BIN2)` en **`W19`** | `CS/P5` | **`TFT_CS`** | Puente a **`J23`** $\rightarrow$ `J11.7 (CS)` |
| **`K`** | `P27` | **`MUX_S0`** | `U3.20 (S0)` vía `J_MAIN.4` | `TX2/P17` | **`M2_PWM`** | `U1.10 (PWMB)` en **`W20`** |
| **`L`** | `P14` | **`MUX_S1`** | `U3.21 (S1)` vía `J_MAIN.5` | `RX2/P16` | **`TFT_RST`** | Puente a **`L23`** $\rightarrow$ `J11.5 (RST)` |
| **`M`** | `P12` | **`STBY`** | `U1.13 (STBY)` en **`W17`** + `R5.2 (10k a GND)` | `P4` | **`M1_PWM`** | `U1.16 (PWMA)` en **`W14`** |
| **`N`** | `GND` | **`GND`** | Tierra común (`GND`) | `P0` | *(NC)* | Sin conectar |
| **`O`** | `P13` | **`MUX_S2`** | `U3.22 (S2)` vía `J_MAIN.6` | `P2` | *(NC)* | Sin conectar |
| **`P`** | `SD2` | *(NC)* | Sin conectar | `P15` | **`MUX_S3`** | `U3.23 (S3)` vía `J_MAIN.7` |
| **`Q`** | `SD3` | *(NC)* | Sin conectar | `SD1` | *(NC)* | Sin conectar |
| **`R`** | `CMD` | *(NC)* | Sin conectar | `SD0` | *(NC)* | Sin conectar |
| **`S`** | `VIN` | **`5V`** | `D1.1 (Cátodo)`, `U7.3 (IN)`, `C7.2` | `CLK` | *(NC)* | Sin conectar |

---

## 2. Driver de Motores `U1` (`TB6612FNG`) en Posición Horizontal (`W14–W21` y `AB14–AB21`)

* **Orientación física:** Módulo acostado horizontalmente con el **capacitor amarillo hacia la IZQUIERDA (Columna `14`)** y el número `177` hacia la DERECHA (Columna `21`).
* **Ventaja:** Los **8 pines de control quedan arriba en la Fila `W`** mirando de frente al ESP32, y los **8 pines de potencia y motores quedan abajo en la Fila `AB`** sin cruzar cables.

### A. Fila Superior de `U1` — Control desde ESP32 (Fila `W`, Columnas `14` a `21`)
| Coordenada DIYLC | Pin `U1` (`TB6612FNG`) | Red en `SCH_IDLine_2026-10-12.json` | De dónde viene (en `U_ESP32`) |
| :---: | :--- | :--- | :--- |
| **`W14`** | `16: PWMA` | **`M1_PWM`** | Viene de **`M22`** (`P4`) |
| **`W15`** | `15: AIN2` | **`M1_IN2`** | Viene de **`C22`** (`P22`) |
| **`W16`** | `14: AIN1` | **`M1_IN1`** | Viene de **`F22`** (`P21`) |
| **`W17`** | `13: STBY` | **`STBY`** | Viene de **`M12`** (`P12`) + **`R5.2`** (`10k` a `GND`) |
| **`W18`** | `12: BIN1` | **`M2_IN1`** | Viene de **`I12`** (`P25`) |
| **`W19`** | `11: BIN2` | **`M2_IN2`** | Viene de **`J12`** (`P26`) |
| **`W20`** | `10: PWMB` | **`M2_PWM`** | Viene de **`K22`** (`P17`) |
| **`W21`** | `9: GND` | **`GND`** | Tierra común (`GND`) + otra pata de **`R5.1 (10k)`** |

### B. Fila Inferior de `U1` — Potencia y Salidas a Motores (Fila `AB`, Columnas `14` a `21`)
| Coordenada DIYLC | Pin `U1` (`TB6612FNG`) | Red en `SCH_IDLine_2026-10-12.json` | A dónde se conecta |
| :---: | :--- | :--- | :--- |
| **`AB14`** | `1: VM` | **`V_BATT`** | Entrada batería (`SW_EXT.2`) + **`C2.1 (100nF)`** + **`C3.1 (470uF +)`** |
| **`AB15`** | `2: VCC` | **`VCC_3V3`** | Salida `3.3V` de `U7.OUT` + **`C5.2 (100nF)`** |
| **`AB16`** | `3: GND` | **`GND`** | Tierra común (`GND`) + **`C2.2`**, **`C3.2 (-)`**, **`C5.1`** |
| **`AB17`** | `4: A1 (AO1)` | **`MOTOR_IZQ.1`** | Pin 1 del conector `MOTOR_IZQ` |
| **`AB18`** | `5: A2 (AO2)` | **`MOTOR_IZQ.2`** | Pin 2 del conector `MOTOR_IZQ` |
| **`AB19`** | `6: B2 (BO2)` | **`MOTOR_DER.2`** | Pin 2 del conector `MOTOR_DER` |
| **`AB20`** | `7: B1 (BO1)` | **`MOTOR_DER.1`** | Pin 1 del conector `MOTOR_DER` |
| **`AB21`** | `8: GND` | **`GND`** | Tierra común (`GND`) |

---

## 3. Interfaz Entre Piso 1 (`Col 11` y `Col 23`) y Piso 2 (`Col 1` y `Col 13`)

### A. Lado Izquierdo (`Columna 11` en Piso 1 $\leftrightarrow$ `Columna 1` en Piso 2)
* **`F11` $\leftrightarrow$ `F1` (`VCC_3V3`):** Recibe `3.3V` desde `U7.OUT` en Piso 1 $\rightarrow$ alimenta `R3.1`, `R4.1`, `J11.2 (C4)` y `J11.8 (C10)` en Piso 2.
* **`G11` $\leftrightarrow$ `G1` (`BTN_CALIB`):** Viene de `G12 (P32)` $\rightarrow$ va a `SW1.2 (U2)` y `R3.2 (G2)`.
* **`H11` $\leftrightarrow$ `H1` (`BTN_START`):** Viene de `H12 (P33)` $\rightarrow$ va a `SW2.2 (U9)` y `R4.2 (H3)`.

### B. Lado Derecho (`Columna 23` en Piso 1 $\leftrightarrow$ `Columna 13` en Piso 2)
* **`A23` $\leftrightarrow$ `A13` (`GND`):** Viene de `A22 (GND)` $\rightarrow$ va a `J11.1 (C3)`.
* **`B23` $\leftrightarrow$ `B13` (`SPI_MOSI`):** Viene de `B22 (P23)` $\rightarrow$ va a `J11.4 (C6)`.
* **`G23` $\leftrightarrow$ `G13` (`GND`):** Viene de `G22 (GND)` $\rightarrow$ va a `SW1.1 (U4)` y `SW2.1 (U11)`.
* **`H23` $\leftrightarrow$ `H13` (`TFT_DC`):** Viene de `H22 (P19)` $\rightarrow$ va a `J11.6 (C8)`.
* **`I23` $\leftrightarrow$ `I13` (`SPI_SCK`):** Viene de `I22 (P18)` $\rightarrow$ va a `J11.3 (C5)`.
* **`J23` $\leftrightarrow$ `J13` (`TFT_CS`):** Viene de `J22 (P5)` $\rightarrow$ va a `J11.7 (C9)`.
* **`L23` $\leftrightarrow$ `L13` (`TFT_RST`):** Viene de `L22 (P16)` $\rightarrow$ va a `J11.5 (C7)`.

---

## 4. Etapa de Potencia (`CN1`, `SW_EXT`, `U2`, `D1`, `U7`, Divisor `R1/R2/C1`) y Sensores (`J_MAIN`)

* **Entrada Batería 2S (`CN1` XT30 + `SW_EXT`):**
  * `CN1.1 (-)` $\rightarrow$ **`GND`** | `CN1.2 (+)` $\rightarrow$ `SW_EXT.1` | `SW_EXT.2` $\rightarrow$ **`V_BATT`** (`U1.1 VM` en `AB14`, `U2.2 IN+`, `R1.2`, `C2.1`, `C3.1`).
* **Divisor de Batería (`BATT_SENSE`):**
  * `R1.2 (100k)` a **`V_BATT`** | Punto medio (`R1.1 + R2.2 (33k) + C1.2 (100nF)`) a **`C12` (`U_ESP32.VP`)** | `R2.1` y `C1.1` a **`GND`**.
* **Regulador 5V (`U2` Mini-360) + Diodo `D1` (`1N5819`):**
  * `U2.2 (IN+)` a **`V_BATT`** | `U2.1 (IN-)` y `U2.3 (OUT-)` a **`GND`** | `U2.4 (OUT+)` a **`D1.2 (Ánodo)`**.
  * `D1.1 (Cátodo)` $\rightarrow$ Riel **`5V`** (`U_ESP32.VIN` en **`S12`**, `U7.3 (IN)` y `C7.2 (10uF)`).
* **Regulador 3.3V (`U7` AMS1117-3.3):**
  * `U7.1 (ADJ/GND)` a **`GND`** | `U7.3 (IN)` a **`5V`** + `C7.2 (10uF)` | `U7.2 / U7.4 (OUT)` a **`VCC_3V3`** + `C9.1 (22uF)` (alimenta `AB15`, `F11` y `J_MAIN.2`).
* **Conector `J_MAIN` (7 pines hacia Placa de Sensores):**
  * `1: GND` | `2: VCC_3V3` | `3: MUX_SIG (D12)` | `4: MUX_S0 (K12)` | `5: MUX_S1 (L12)` | `6: MUX_S2 (O12)` | `7: MUX_S3 (P22)`.
