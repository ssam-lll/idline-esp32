# 📐 Guía Técnica: Placa de Sensores (8 Canales) — Placa Perforada / DIYLC
**Proyecto:** IDLine — Robot Seguidor de Línea  
**Método Actual:** Simulación en **DIYLC** + Armado en **Placa Perforada** (Dimensiones ref: ~70 × 50 mm)

---

## Componentes en esta placa

| Ref | Componente | Formato / Dimensiones | Descripción |
|:---:|:---|:---:|:---|
| **U3** | CD74HC4067 (módulo breakout) | 40 × 17 mm (2 filas de 12 pines) | Multiplexor 16 canales |
| **C4** | 100 nF cerámico (código 104) | Through-Hole (con patitas) | Desacoplo entre `VCC` y `GND` del MUX |
| **U5** | Header hembra 11 pines | Paso 2.54 mm (~28 × 2.5 mm) | Conector para barra central de 8 sensores |
| **J_MAIN** | Header / JST-XH 7 pines | Paso 2.54 mm (~18 × 6 mm) | Conector de 7 hilos hacia la Placa Madre |

---

## Pinout del Conector J_MAIN (JST-XH 7p)

| Pin | Señal | Dirección | Conexión en placa madre |
|:---:|:---|:---|:---|
| 1 | GND | ⏚ Retorno | GND |
| 2 | VCC_3V3 | ← Desde madre | Salida AMS1117 |
| 3 | MUX_SIG | → Hacia madre | ESP32 GPIO39 (VN) |
| 4 | MUX_S0 | ← Desde madre | ESP32 GPIO27 |
| 5 | MUX_S1 | ← Desde madre | ESP32 GPIO14 |
| 6 | MUX_S2 | ← Desde madre | ESP32 GPIO13 |
| 7 | MUX_S3 | ← Desde madre | ESP32 GPIO15 |

---

## Conexiones del MUX (CD74HC4067)

### Canales activos (barra central U5):
- C4 → S4 (sensor 1) | C5 → S5 | C6 → S6 | C7 → S7
- C8 → S8 | C9 → S9 | C10 → S10 | C11 → S11 (sensor 8)

### Canales sin usar → GND:
- C0, C1, C2, C3 → GND (aleta izquierda, no instalada)
- C12, C13, C14, C15 → GND (aleta derecha, no instalada)

### Pines de control:
- SIG → MUX_SIG (hacia J_MAIN pin 3)
- S0-S3 → MUX_S0 a MUX_S3 (desde J_MAIN pines 4-7)
- EN → GND (siempre habilitado)
- VCC → VCC_3V3 (desde J_MAIN pin 2)
- GND → GND

---

## Reglas de diseño PCB

| Parámetro | Valor |
|:---|:---|
| Ancho de pista (señales) | 0.254 mm (10 mil) |
| Ancho de pista (VCC_3V3, GND) | 0.5 mm mínimo |
| Clearance | 0.2 mm (8 mil) |
| Vías | Pad 0.8 mm / Taladro 0.4 mm |
| Agujeros de montaje | M3 (3.2 mm taladro, 6 mm pad) |
| Capa inferior | Plano de GND sólido |

---

## Notas de placement

1. La barra de sensores (U5) se conecta por **debajo** del PCB, con los sensores apuntando al suelo
2. El header de U5 va en el **borde frontal** del PCB
3. El módulo MUX (U3) va **centrado** en la cara superior
4. C4 va **pegado** al MUX, entre VCC y GND del módulo
5. J_MAIN va en el **borde trasero** (cable sale hacia atrás, hacia la placa madre)
6. 4 agujeros M3 en las esquinas para separadores de nylon

---

## Pasos para implementar en EasyEDA

1. [ ] Guardar backup: `File → Save As → SCH_IDLine_16sensores_backup`
2. [ ] Eliminar J0–J7 (8 conectores de sensores individuales)
3. [ ] Conectar pines C0-C3 y C12-C15 del MUX a GND
4. [ ] Agregar J_MAIN (header 7 pines) con el pinout de arriba
5. [ ] Agregar J_MAIN duplicado en el esquemático de la placa madre
6. [ ] Correr ERC: `Design → Design Rule → Run ERC`
7. [ ] Convertir a PCB: `Design → Convert to PCB`
