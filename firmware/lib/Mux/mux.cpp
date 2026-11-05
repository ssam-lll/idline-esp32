#include "mux.h"
#include <soc/gpio_struct.h>

namespace idline {

Multiplexor::Multiplexor(uint8_t s0, uint8_t s1, uint8_t s2, uint8_t s3, uint8_t sig, uint8_t batt)
    : _pinS0(s0), _pinS1(s1), _pinS2(s2), _pinS3(s3), _pinSig(sig), _pinBatt(batt), _cached_batt_raw(0) {}

void Multiplexor::begin() {
    pinMode(_pinS0, OUTPUT);
    pinMode(_pinS1, OUTPUT);
    pinMode(_pinS2, OUTPUT);
    pinMode(_pinS3, OUTPUT);
    pinMode(_pinSig, INPUT);
    pinMode(_pinBatt, INPUT);

    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);

    seleccionarCanal(0);
    _cached_batt_raw = static_cast<uint16_t>(analogReadMilliVolts(_pinBatt));
}

void Multiplexor::seleccionarCanal(uint8_t canal) {
    canal &= 0x0F;
    GPIO.out_w1tc = hw::kMuxClrMask[canal];
    GPIO.out_w1ts = hw::kMuxSetMask[canal];
    delayMicroseconds(2);
}

int Multiplexor::leerCanal(uint8_t canal) {
    seleccionarCanal(canal);
    return analogRead(_pinSig);
}

RawSensorFrame Multiplexor::escanearFrame(uint32_t tick, SensorBarMode mode) {
    RawSensorFrame frame{};
    frame.timestamp_us = micros();

    if (mode == SensorBarMode::kCenter8_C4_C11) {
        frame.count = 8;
        for (uint8_t ch = 4; ch <= 11; ++ch) {
            GPIO.out_w1tc = hw::kMuxClrMask[ch];
            GPIO.out_w1ts = hw::kMuxSetMask[ch];
            delayMicroseconds(2);
            frame.adc_raw[ch] = static_cast<uint16_t>(analogRead(_pinSig));
        }
    } else {
        frame.count = 16;
        for (uint8_t ch = 0; ch < 16; ++ch) {
            GPIO.out_w1tc = hw::kMuxClrMask[ch];
            GPIO.out_w1ts = hw::kMuxSetMask[ch];
            delayMicroseconds(2);
            frame.adc_raw[ch] = static_cast<uint16_t>(analogRead(_pinSig));
        }
    }

    if ((tick & 0x0F) == 0) {
        _cached_batt_raw = static_cast<uint16_t>(analogReadMilliVolts(_pinBatt));
    }
    frame.batt_raw = _cached_batt_raw;

    return frame;
}

} // namespace idline
