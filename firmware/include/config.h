#ifndef IDLINE_CONFIG_H
#define IDLINE_CONFIG_H

#include <stdint.h>
#include <stddef.h>

namespace idline {
namespace hw {

constexpr uint8_t kPinBattSense = 36; // ADC1_CH0, VP

constexpr uint8_t kPinMuxSig = 39; // ADC1_CH3, VN
constexpr uint8_t kPinMuxS0  = 27;
constexpr uint8_t kPinMuxS1  = 14;
constexpr uint8_t kPinMuxS2  = 13;
constexpr uint8_t kPinMuxS3  = 15;

constexpr uint8_t kPinBtnCalib = 32;
constexpr uint8_t kPinBtnStart = 33;

constexpr uint8_t kPinStby = 12;
constexpr uint8_t kPinAin1 = 21;
constexpr uint8_t kPinAin2 = 22;
constexpr uint8_t kPinPwma = 4;
constexpr uint8_t kPinBin1 = 25;
constexpr uint8_t kPinBin2 = 26;
constexpr uint8_t kPinPwmb = 17; // GPIO17 per GEMINI.md

constexpr uint8_t kPinSpiSck  = 18;
constexpr uint8_t kPinSpiMosi = 23;
constexpr uint8_t kPinTftRst  = 16;
constexpr uint8_t kPinTftDc   = 19;
constexpr uint8_t kPinTftCs   = 5;

constexpr uint16_t kTftWidth  = 240;
constexpr uint16_t kTftHeight = 240;

constexpr uint32_t kPwmFrequency       = 20000;
constexpr uint8_t  kPwmResolutionBits  = 10;
constexpr uint16_t kPwmMaxDuty         = (1U << kPwmResolutionBits) - 1U; // 1023
constexpr uint8_t  kPwmChannelLeft     = 0;
constexpr uint8_t  kPwmChannelRight    = 1;

constexpr uint32_t kBattR1_Ohms       = 100000;
constexpr uint32_t kBattR2_Ohms       = 33000;
constexpr uint16_t kBattCutoff_mV     = 6400; // 3.20V per cell
constexpr uint16_t kBattRecover_mV    = 6600; // 3.30V per cell
constexpr uint16_t kBattUsbFloor_mV   = 6300; // Below this, powered via USB / 5V rail without 2S cutoff

constexpr const char* kWifiSsid            = "ANDRES-LOPEZ";
constexpr const char* kWifiPass            = "Gallego162783";
constexpr const char* kMqttBroker          = "192.168.1.40";
constexpr uint16_t    kMqttPort            = 1883;
constexpr const char* kMqttClientId        = "ESP32_IDLine";
constexpr uint32_t    kTelemetryIntervalMs = 500;
constexpr uint32_t    kMqttReconnectMs     = 3000;

constexpr uint32_t kMuxAllMask = (1UL << kPinMuxS0) | (1UL << kPinMuxS1) | 
                                 (1UL << kPinMuxS2) | (1UL << kPinMuxS3);

constexpr uint32_t getMuxSetMask(uint8_t ch) {
    return ((ch & 1) ? (1UL << kPinMuxS0) : 0UL) |
           ((ch & 2) ? (1UL << kPinMuxS1) : 0UL) |
           ((ch & 4) ? (1UL << kPinMuxS2) : 0UL) |
           ((ch & 8) ? (1UL << kPinMuxS3) : 0UL);
}

constexpr uint32_t getMuxClrMask(uint8_t ch) {
    return kMuxAllMask & ~getMuxSetMask(ch);
}

constexpr uint32_t kMuxSetMask[16] = {
    getMuxSetMask(0),  getMuxSetMask(1),  getMuxSetMask(2),  getMuxSetMask(3),
    getMuxSetMask(4),  getMuxSetMask(5),  getMuxSetMask(6),  getMuxSetMask(7),
    getMuxSetMask(8),  getMuxSetMask(9),  getMuxSetMask(10), getMuxSetMask(11),
    getMuxSetMask(12), getMuxSetMask(13), getMuxSetMask(14), getMuxSetMask(15)
};

constexpr uint32_t kMuxClrMask[16] = {
    getMuxClrMask(0),  getMuxClrMask(1),  getMuxClrMask(2),  getMuxClrMask(3),
    getMuxClrMask(4),  getMuxClrMask(5),  getMuxClrMask(6),  getMuxClrMask(7),
    getMuxClrMask(8),  getMuxClrMask(9),  getMuxClrMask(10), getMuxClrMask(11),
    getMuxClrMask(12), getMuxClrMask(13), getMuxClrMask(14), getMuxClrMask(15)
};

} // namespace hw
} // namespace idline

#endif // IDLINE_CONFIG_H
