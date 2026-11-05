#ifndef IDLINE_MUX_H
#define IDLINE_MUX_H

#include <Arduino.h>
#include "config.h"
#include "types.h"

namespace idline {

class Multiplexor {
private:
    uint8_t _pinS0;
    uint8_t _pinS1;
    uint8_t _pinS2;
    uint8_t _pinS3;
    uint8_t _pinSig;
    uint8_t _pinBatt;

    uint16_t _cached_batt_raw;

public:
    Multiplexor(uint8_t s0 = hw::kPinMuxS0,
                uint8_t s1 = hw::kPinMuxS1,
                uint8_t s2 = hw::kPinMuxS2,
                uint8_t s3 = hw::kPinMuxS3,
                uint8_t sig = hw::kPinMuxSig,
                uint8_t batt = hw::kPinBattSense);

    void begin();
    void seleccionarCanal(uint8_t canal);
    int leerCanal(uint8_t canal);
    RawSensorFrame escanearFrame(uint32_t tick, SensorBarMode mode);
};

} // namespace idline

#endif // IDLINE_MUX_H
