#ifndef IDLINE_PANTALLA_H
#define IDLINE_PANTALLA_H

#include <Arduino.h>
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include "config.h"
#include "types.h"

namespace idline {

struct UiViewModel {
    RobotMode mode;
    uint16_t  vbat_mv;
    bool      wifi_enabled;
    bool      wifi_connected;
    bool      mqtt_connected;
    uint8_t   profile_idx;
    int16_t   position;
    uint8_t   bar_heights[8];
    int16_t   m1;
    int16_t   m2;
    uint32_t  loop_time_us;
};

class PantallaTFT {
private:
    uint8_t _pinCs;
    uint8_t _pinDc;
    uint8_t _pinRst;
    uint8_t _pinSck;
    uint8_t _pinMosi;

    Adafruit_ST7789 _tft;
    UiViewModel     _prev;
    bool            _initialized;
    uint32_t        _last_render_ms;
    uint32_t        _last_resync_ms;

    void despertarControlador();
    void dibujarEstructuraEstatica();
    void renderizarHeader(const UiViewModel& curr);
    void renderizarSensores(const UiViewModel& curr);
    void renderizarReticula(const UiViewModel& curr);
    void renderizarFooter(const UiViewModel& curr);

public:
    PantallaTFT(uint8_t cs = hw::kPinTftCs,
                uint8_t dc = hw::kPinTftDc,
                uint8_t rst = hw::kPinTftRst,
                uint8_t sck = hw::kPinSpiSck,
                uint8_t mosi = hw::kPinSpiMosi);

    void begin();
    void renderizarDiferencial(uint32_t now_ms, const SupervisorState& state, const ControlTelemetry& tel);
};

} // namespace idline

#endif // IDLINE_PANTALLA_H
