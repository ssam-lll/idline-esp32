#ifndef IDLINE_TELEMETRIA_H
#define IDLINE_TELEMETRIA_H

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <functional>
#include "config.h"
#include "types.h"

namespace idline {

typedef std::function<void(const char* cmd, int m1, int m2)> ComandoMotorCallback;

class Telemetria {
private:
    const char* _ssid;
    const char* _pass;
    const char* _broker;
    int         _port;
    const char* _clientId;

    WiFiClient   _espClient;
    PubSubClient _mqtt;

    unsigned long _lastReconnectMillis;
    const unsigned long _reconnectInterval = hw::kMqttReconnectMs;

    ComandoMotorCallback _motorCallback;

    SupervisorState* _active_state;
    uint32_t         _last_telemetry_ms;
    uint32_t         _last_ack_seq;
    bool             _wifi_enabled;

    uint8_t  _btn_calib_last_raw;
    uint32_t _btn_calib_press_start_ms;
    uint32_t _btn_calib_last_debounce_ms;

    uint8_t  _btn_start_last_raw;
    uint32_t _btn_start_press_start_ms;
    uint32_t _btn_start_last_debounce_ms;

    void procesarBotones(uint32_t now_ms, SupervisorState* state);

public:
    Telemetria(const char* ssid = hw::kWifiSsid,
               const char* pass = hw::kWifiPass,
               const char* broker = hw::kMqttBroker,
               int port = hw::kMqttPort,
               const char* clientId = hw::kMqttClientId);

    void setMotorCallback(ComandoMotorCallback callback);
    void begin(bool enable_wifi = false);
    void mantenerConexion(unsigned long currentMillis);
    void procesarMensaje(char* topic, byte* payload, unsigned int length);
    void publicarSensores(const int valores[8], int error);
    void publicarEstadoMotores(int m1, int m2, const char* status);

    void tick(uint32_t now_ms, const ControlTelemetry& tel, SupervisorState* state);
};

} // namespace idline

#endif // IDLINE_TELEMETRIA_H
