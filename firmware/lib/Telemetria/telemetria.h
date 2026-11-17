#ifndef IDLINE_TELEMETRIA_H
#define IDLINE_TELEMETRIA_H

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "config.h"
#include "types.h"

namespace idline {

class Telemetria {
private:
    struct RemoteCmdMailbox {
        bool    has_cmd;
        char    cmd[24];
        int16_t m1;
        int16_t m2;
        float   kp;
        float   ki;
        float   kd;
        int16_t speed;
        bool    is_new_track;
        bool    is_upload_memory;
    };

    static constexpr size_t kLiveQueueCap = 64;
    static constexpr size_t kCmdQueueCap  = 8;

    const char* _ssid;
    const char* _pass;
    const char* _apiUrl;
    const char* _deviceId;

    bool             _wifi_enabled;
    volatile bool    _http_connected;
    volatile bool    _ota_active;
    bool             _wifi_ip_logged;
    uint32_t         _track_id;

    ControlTelemetry _latest_tel;
    RemoteCmdMailbox _cmd_queue[kCmdQueueCap];
    size_t           _cmd_head;
    size_t           _cmd_tail;
    portMUX_TYPE     _mux;

    WiFiClientSecure _tls_client;
    HTTPClient       _http;
    bool             _http_initialized;

    RunSample        _live_queue[kLiveQueueCap];
    volatile size_t  _live_head;
    volatile size_t  _live_tail;

    const RunSample* _run_buffer;
    const size_t*    _sample_count_ptr;
    volatile bool    _uploading_memory;
    size_t           _upload_offset;

    TaskHandle_t     _http_task_handle;

    uint8_t  _btn_calib_last_raw;
    uint32_t _btn_calib_press_start_ms;
    uint32_t _btn_calib_last_debounce_ms;

    uint8_t  _btn_start_last_raw;
    uint32_t _btn_start_press_start_ms;
    uint32_t _btn_start_last_debounce_ms;

    void procesarBotones(uint32_t now_ms, SupervisorState* state);
    void executeHttpPost();
    void parseServerResponse(const String& response);
    void enqueueCommandObject(JsonVariant cmdVar);
    void pushRemoteCmd(const RemoteCmdMailbox& mb);
    bool popRemoteCmd(RemoteCmdMailbox& mb);
    bool popSample(RunSample& sample);

    static void httpTaskTrampoline(void* arg);
    void httpTaskLoop();

public:
    Telemetria(const char* ssid = hw::kWifiSsid,
               const char* pass = hw::kWifiPass,
               const char* apiUrl = hw::kApiUrl,
               const char* deviceId = hw::kDeviceId);

    void setRunBuffer(const RunSample* buffer, const size_t* count_ptr);
    void pushSample(const RunSample& sample);

    void begin(bool enable_wifi = true);
    void tick(uint32_t now_ms, const ControlTelemetry& tel, SupervisorState* state);
};

} // namespace idline

#endif // IDLINE_TELEMETRIA_H
