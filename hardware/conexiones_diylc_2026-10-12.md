# 📌 Mapa Maestro Final de Conexiones y Coordenadas DIYLC (`SCH_IDLine_2026-10-12.json`)

**Fuente única de redes:** [`hardware/esquematico/SCH_IDLine_2026-10-12.json`](esquematico/SCH_IDLine_2026-10-12.json)  
**Estado:** Placa Madre (Piso 2) y Placa Pantalla/Botones (Piso 1) **100% verificadas en DIYLC**.

---

## 1. Coordenadas Finales en Placa Madre (Piso 2)

* **`U_ESP32` (`IC1`):** Columnas **`G`** (Izquierda) y **`Q`** (Derecha), Filas **`5` a `23`**.
* **Zócalo Superior `J_MAIN` (8 pines hacia el Multiplexor):** **`Fila 3`**, de **`H3` a `O3`** (`H3:SIG`, `I3:S3`, `J3:S2`, `K3:S1`, `L3:S0`, `M3:EN=GND`, `N3:VCC_3V3`, `O3:GND`).
* **Zócalos hacia Piso 1 (Pantalla y Botones):**
  * Izquierda (`Columna F`): **`F10` (`VCC_3V3`)**, **`F11` (`BTN_CALIB`)**, **`F12` (`BTN_START`)**.
  * Derecha (`Columna R`): **`R5` (`GND`)**, **`R6` (`SPI_MOSI`)**, **`R11` (`GND`)**, **`R12` (`TFT_DC`)**, **`R13` (`SPI_SCK`)**, **`R14` (`TFT_CS`)**, **`R16` (`TFT_RST`)**.
* **Divisor de Batería (`R1`, `R2`, `C1` en `Filas 7 a 9`):**
  * `R1 (100k)`: de `A7 (V_BATT)` a `D7 (VP)`.
  * `R2 (33k)`: vertical de `D7 (VP)` a `D9 (GND)`.
  * `C1 (100nF)`: vertical de `F7 (VP)` a `F9 (GND)`.
* **Puente H `TB6612FNG` (`U1`):**
  * Fila Superior de Control (`Fila 27`, `N27–U27`): `N27:PWMA`, `O27:AIN2`, `P27:AIN1`, `Q27:STBY`, `R27:BIN1`, `S27:BIN2`, `T27:PWMB`, `U27:GND`.
  * Fila Inferior de Potencia y Motores (`Fila 33`, `N33–U33`): `N33:VM`, `O33:VCC_3V3`, `P33:GND`, `Q33:AO1`, `R33:AO2`, `S33:BO2`, `T33:BO1`, `U33:GND`.
* **Etapa de Potencia Compacta (Costado Izquierdo `Columnas A–L`, `Filas 27–38`):**
  * `U7 (AMS1117-3.3)`: `J29 (GND)`, `K29 (3.3V OUT)`, `L29 (5V IN)` con `C7 (10uF)` y `C9 (22uF)`.
  * `U2 (Mini-360)`: `B31 (IN-)`, `H31 (OUT-)`, `B35 (IN+)`, `H35 (OUT+)` + Diodo Schottky `D2/D1 (1N5819)` hacia `5V (Col L)`.
  * `SW_EXT` (`B28–C28`) y `CN1` (`E28–F28`).

---

## 2. Guía de Conexiones para Piso 3 (Placa de Sensores + Multiplexor `CD74HC4067`)

Basado en la disposición física de tu foto (`CD74HC4067` arriba y Barra Roja de 8 sensores abajo):

### A. Fila Superior del Multiplexor (`8 pines`: se unen 1 a 1 con `H3–O3` de la Placa Madre)
1. **`SIG`** $\leftarrow$ Jumper desde **`H3`** (`VN / GPIO39`)
2. **`S3`** $\leftarrow$ Jumper desde **`I3`** (`P15`)
3. **`S2`** $\leftarrow$ Jumper desde **`J3`** (`P13`)
4. **`S1`** $\leftarrow$ Jumper desde **`K3`** (`P14`)
5. **`S0`** $\leftarrow$ Jumper desde **`L3`** (`P27`)
6. **`EN`** $\leftarrow$ Jumper desde **`M3`** (`GND` — o unido directo al pin `GND` del MUX)
7. **`VCC`** $\leftarrow$ Jumper **ROJO** desde **`N3`** (`VCC_3V3`)
8. **`GND`** $\leftarrow$ Jumper **NEGRO** desde **`O3`** (`GND`)
* **Capacitor `C4` (`100 nF` cerámico):** Soldado justo al lado de los pines **`VCC`** y **`GND`** del Multiplexor.

### B. Fila Inferior del Multiplexor (`16 pines`: `C15` a `C0`) hacia la Barra de 8 Sensores (`U5`)
En tu foto de la placa de sensores, los 8 canales centrales (`C11` a `C4`) quedan **alineados frente a frente** con las 8 salidas (`D8` a `D1`) de la barra roja:
* **Canales activos (puentes rectos hacia abajo):**
  * `C11` $\rightarrow$ `D8` (`S11`)
  * `C10` $\rightarrow$ `D7` (`S10`)
  * `C9` $\rightarrow$ `D6` (`S9`)
  * `C8` $\rightarrow$ `D5` (`S8`)
  * `C7` $\rightarrow$ `D4` (`S7`)
  * `C6` $\rightarrow$ `D3` (`S6`)
  * `C5` $\rightarrow$ `D2` (`S5`)
  * `C4` $\rightarrow$ `D1` (`S4`)
* **Canales sin usar (puenteados a `GND` en Negro):**
  * Izquierda: Unir **`C15 — C14 — C13 — C12`** a **`GND`**.
  * Derecha: Unir **`C3 — C2 — C1 — C0`** a **`GND`**.
* **Alimentación de la Barra Roja de Sensores (`VCC`, `IR`, `GND`):**
  * Pin **`VCC`** (a la izquierda de `D8`) y pin **`IR`** (a la derecha de `D1`) $\rightarrow$ van unidos con cable **ROJO** al pin **`VCC` (`3.3V`)** del Multiplexor.
  * Pin **`GND`** (a la derecha de `IR`) $\rightarrow$ va unido con cable **NEGRO** al pin **`GND`** del Multiplexor (y a `C3..C0`).
  * *(Recordatorio físico: poner una gotita de estaño en el puente **`3.3v`** de la esquina derecha de la barra roja).*

---

## 3. Dimensiones Físicas Reales (Placa Terminada y Chasis)

| Bloque Físico | Ancho (`mm`) | Largo (`mm`) | Alto (`mm`) | Estado |
| :--- | :---: | :---: | :---: | :--- |
| **Placa Madre + MUX (Piso 2)** | `59.0 mm` | `109.0 mm` | `19.4 mm` | ✅ Soldada y verificada (`8.25V`, `4.99V`, `3.3V`, `VP=1.7V`) |
| **Placa Pantalla y Botones (Piso 1)** | `36.7 mm` | `62.2 mm` | `36.0 mm` *(con pines)* | ✅ Terminada (Altura total acoplada Piso 1 + Piso 2: `41.8 mm`) |
| **Portabaterías 2S 18650** | `40.4 mm` | `76.1 mm` | `19.0 mm` | ✅ Medido para diseño de chasis |
