#include "telemetria.h"
#include <ArduinoJson.h>
#include <ArduinoOTA.h>
#include <Preferences.h>

namespace idline {

static bool s_ota_iniciado = false;

Telemetria::Telemetria(const char* ssid, const char* pass, const char* apiUrl, const char* deviceId)
    : _ssid(ssid), _pass(pass), _apiUrl(apiUrl), _deviceId(deviceId),
      _wifi_enabled(false), _http_connected(false), _ota_active(false), _wifi_ip_logged(false), _track_id(1),
      _latest_tel{}, _cmd_queue{}, _cmd_head(0), _cmd_tail(0), _mux(portMUX_INITIALIZER_UNLOCKED),
      _tls_client(), _http(), _http_initialized(false),
      _live_head(0), _live_tail(0),
      _run_buffer(nullptr), _sample_count_ptr(nullptr),
      _uploading_memory(false), _upload_offset(0),
      _http_task_handle(nullptr),
      _btn_calib_last_raw(HIGH), _btn_calib_press_start_ms(0), _btn_calib_last_debounce_ms(0),
      _btn_start_last_raw(HIGH), _btn_start_press_start_ms(0), _btn_start_last_debounce_ms(0) {}

void Telemetria::pushRemoteCmd(const RemoteCmdMailbox& mb) {
    portENTER_CRITICAL(&_mux);
    size_t next = (_cmd_head + 1) % kCmdQueueCap;
    if (next == _cmd_tail) {
        _cmd_tail = (_cmd_tail + 1) % kCmdQueueCap;
    }
    _cmd_queue[_cmd_head] = mb;
    _cmd_head = next;
    portEXIT_CRITICAL(&_mux);
}

bool Telemetria::popRemoteCmd(RemoteCmdMailbox& mb) {
    if (_cmd_tail == _cmd_head) {
        return false;
    }
    mb = _cmd_queue[_cmd_tail];
    _cmd_tail = (_cmd_tail + 1) % kCmdQueueCap;
    return true;
}

void Telemetria::setRunBuffer(const RunSample* buffer, const size_t* count_ptr) {
    _run_buffer = buffer;
    _sample_count_ptr = count_ptr;
}

void Telemetria::pushSample(const RunSample& sample) {
    size_t next = (_live_head + 1) % kLiveQueueCap;
    if (next == _live_tail) {
        _live_tail = (_live_tail + 1) % kLiveQueueCap;
    }
    _live_queue[_live_head] = sample;
    _live_head = next;
}

bool Telemetria::popSample(RunSample& sample) {
    if (_live_tail == _live_head) {
        return false;
    }
    sample = _live_queue[_live_tail];
    _live_tail = (_live_tail + 1) % kLiveQueueCap;
    return true;
}

void Telemetria::httpTaskTrampoline(void* arg) {
    static_cast<Telemetria*>(arg)->httpTaskLoop();
}

void Telemetria::httpTaskLoop() {
    uint32_t last_http_ms = 0;
    for (;;) {
        vTaskDelay(pdMS_TO_TICKS(15));
        uint32_t now = millis();

        if (WiFi.status() == WL_CONNECTED) {
            if (!_wifi_ip_logged) {
                _wifi_ip_logged = true;
                Serial.printf("[WIFI] Conectado IP=%s host=idline-esp32.local\n",
                              WiFi.localIP().toString().c_str());
            }
            if (!s_ota_iniciado) {
                ArduinoOTA.setHostname("idline-esp32");
                ArduinoOTA.onStart([this]() {
                    // Disable motor driver immediately; OTA blocks loop/Core 1 during flash writes.
                    digitalWrite(hw::kPinStby, LOW);
                    _ota_active = true;
                    RemoteCmdMailbox stop_mb{};
                    stop_mb.has_cmd = true;
                    strncpy(stop_mb.cmd, "stop", sizeof(stop_mb.cmd) - 1);
                    stop_mb.cmd[sizeof(stop_mb.cmd) - 1] = '\0';
                    pushRemoteCmd(stop_mb);
                    Serial.println("[OTA] Inicio");
                });
                ArduinoOTA.onEnd([this]() {
                    _ota_active = false;
                    Serial.println("[OTA] Fin, reiniciando...");
                });
                ArduinoOTA.onError([this](ota_error_t err) {
                    _ota_active = false;
                    Serial.printf("[OTA] Error (%u)\n", (unsigned)err);
                });
                ArduinoOTA.begin();
                s_ota_iniciado = true;
            }
            ArduinoOTA.handle();

            if (!_ota_active && (now - last_http_ms >= hw::kHttpIntervalMs)) {
                last_http_ms = now;
                executeHttpPost();
            }
        } else {
            _http_connected = false;
            _wifi_ip_logged = false;
            if (_http_initialized) {
                _http.end();
                _tls_client.stop();
                _http_initialized = false;
            }
        }
    }
}

void Telemetria::executeHttpPost() {
    ControlTelemetry tel;
    portENTER_CRITICAL(&_mux);
    tel = _latest_tel;
    uint32_t tid = _track_id;
    portEXIT_CRITICAL(&_mux);

    JsonDocument doc;
    doc["dispositivo_id"] = _deviceId;

    JsonArray arrSens = doc["sensores"].to<JsonArray>();
    for (uint8_t i = 4; i <= 11; ++i) {
        arrSens.add(tel.raw_values[i]);
    }

    doc["m1"] = tel.m1_pwm;
    doc["m2"] = tel.m2_pwm;
    doc["error"] = tel.sensor_error;

    switch (tel.current_mode) {
        case RobotMode::kRunning:      doc["modo"] = "RUNNING"; break;
        case RobotMode::kCalibrating:  doc["modo"] = "CALIBRATING"; break;
        case RobotMode::kReady:        doc["modo"] = "READY"; break;
        case RobotMode::kRemoteManual: doc["modo"] = "MANUAL"; break;
        case RobotMode::kMotorTest:    doc["modo"] = "TESTING"; break;
        case RobotMode::kFaultLowBatt: doc["modo"] = "LOW_BATT"; break;
        default:                       doc["modo"] = "IDLE"; break;
    }

    doc["posicion"] = tel.position;
    doc["vbat_mv"] = tel.vbat_mv;
    uint8_t vbat_pct = 0;
    if (tel.vbat_mv >= hw::kBattCutoff_mV) {
        uint32_t span = hw::kBattFull_mV - hw::kBattCutoff_mV;
        uint32_t clamped = (tel.vbat_mv > hw::kBattFull_mV) ? hw::kBattFull_mV : tel.vbat_mv;
        vbat_pct = static_cast<uint8_t>(((clamped - hw::kBattCutoff_mV) * 100UL) / span);
    }
    doc["vbat_pct"] = vbat_pct;
    doc["track_id"] = tid;
    doc["batch_cmds"] = true;

    JsonArray arrMuestras = doc["muestras"].to<JsonArray>();

    if (_uploading_memory && _run_buffer != nullptr && _sample_count_ptr != nullptr) {
        size_t total = *_sample_count_ptr;
        size_t count = 0;
        while (_upload_offset < total && count < 40) {
            const RunSample& s = _run_buffer[_upload_offset++];
            JsonObject m = arrMuestras.add<JsonObject>();
            m["t_ms"] = s.t_ms;
            m["pos"] = s.pos;
            m["m1"] = s.m1;
            m["m2"] = s.m2;
            m["status"] = s.status;
            ++count;
        }
        if (_upload_offset >= total) {
            _uploading_memory = false;
            _upload_offset = 0;
        }
    } else {
        RunSample s;
        size_t count = 0;
        while (popSample(s) && count < 30) {
            JsonObject m = arrMuestras.add<JsonObject>();
            m["t_ms"] = s.t_ms;
            m["pos"] = s.pos;
            m["m1"] = s.m1;
            m["m2"] = s.m2;
            m["status"] = s.status;
            ++count;
        }
    }

    String payload;
    serializeJson(doc, payload);

    if (_http_initialized && !_tls_client.connected()) {
        _http.end();
        _tls_client.stop();
        _http_initialized = false;
    }

    if (!_http_initialized) {
        _tls_client.setInsecure();
        _tls_client.setTimeout(4);
        _http.setReuse(true);
        _http.setConnectTimeout(hw::kHttpConnectTimeoutMs);
        _http.setTimeout(hw::kHttpTimeoutMs);
        _http_initialized = _http.begin(_tls_client, _apiUrl);
    }

    if (_http_initialized) {
        _http.addHeader("Content-Type", "application/json");
        int code = _http.POST(payload);
        if (code >= 200 && code < 300) {
            _http_connected = true;
            String resp = _http.getString();
            if (resp.length() > 0) {
                parseServerResponse(resp);
            }
        } else {
            Serial.printf("[HTTP] POST err=%d\n", code);
            _http_connected = false;
            _http.end();
            _tls_client.stop();
            _http_initialized = false;
        }
    } else {
        _http_connected = false;
    }
}

void Telemetria::enqueueCommandObject(JsonVariant cmdVar) {
    if (cmdVar.isNull()) {
        return;
    }

    const char* cmd = "";
    JsonObject cmdObj;
    if (cmdVar.is<JsonObject>()) {
        cmdObj = cmdVar.as<JsonObject>();
        cmd = cmdObj["cmd"] | cmdObj["action"] | cmdObj["tipo"] | "";
    } else if (cmdVar.is<const char*>()) {
        cmd = cmdVar.as<const char*>();
    }

    if (!cmd || strlen(cmd) == 0) {
        return;
    }

    RemoteCmdMailbox mb{};
    mb.has_cmd = true;
    strncpy(mb.cmd, cmd, sizeof(mb.cmd) - 1);
    mb.cmd[sizeof(mb.cmd) - 1] = '\0';
    mb.kp = -1.0f;
    mb.ki = -1.0f;
    mb.kd = -1.0f;
    mb.speed = -1;

    JsonObject paramsObj = cmdObj["payload"].is<JsonObject>() ? cmdObj["payload"].as<JsonObject>() : cmdObj;

    if (strcmp(cmd, "set_motores") == 0) {
        mb.m1 = paramsObj["m1"] | (cmdObj["m1"] | 0);
        mb.m2 = paramsObj["m2"] | (cmdObj["m2"] | 0);
    } else if (strcmp(cmd, "set_pid") == 0) {
        if (paramsObj["kp"].is<float>()) mb.kp = paramsObj["kp"];
        if (paramsObj["ki"].is<float>()) mb.ki = paramsObj["ki"];
        if (paramsObj["kd"].is<float>()) mb.kd = paramsObj["kd"];
        if (paramsObj["speed"].is<int16_t>()) mb.speed = paramsObj["speed"];
    } else if (strcmp(cmd, "new_track") == 0) {
        mb.is_new_track = true;
    } else if (strcmp(cmd, "upload_memory") == 0) {
        mb.is_upload_memory = true;
    }

    pushRemoteCmd(mb);
}

void Telemetria::parseServerResponse(const String& response) {
    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, response);
    if (err) {
        return;
    }

    if (doc["comandos"].is<JsonArray>()) {
        JsonArray arr = doc["comandos"].as<JsonArray>();
        for (JsonVariant v : arr) {
            enqueueCommandObject(v);
        }
        return;
    }

    JsonVariant cmdVar = doc["comando"];
    if (cmdVar.isNull() && doc["cmd"].is<const char*>()) {
        cmdVar = doc.as<JsonVariant>();
    }
    enqueueCommandObject(cmdVar);
}

void Telemetria::begin(bool enable_wifi) {
    _wifi_enabled = enable_wifi;
    pinMode(hw::kPinBtnCalib, INPUT_PULLUP);
    pinMode(hw::kPinBtnStart, INPUT_PULLUP);

    if (_wifi_enabled) {
        WiFi.mode(WIFI_STA);
        WiFi.setSleep(false);
        WiFi.setAutoReconnect(true);
        WiFi.begin(_ssid, _pass);
        xTaskCreatePinnedToCore(httpTaskTrampoline, "HttpCore0", 10240, this, 1, &_http_task_handle, 0);
    }
}

void Telemetria::procesarBotones(uint32_t now_ms, SupervisorState* state) {
    uint8_t raw_calib = digitalRead(hw::kPinBtnCalib);
    if (raw_calib != _btn_calib_last_raw && (now_ms - _btn_calib_last_debounce_ms >= 30)) {
        _btn_calib_last_debounce_ms = now_ms;
        if (raw_calib == LOW) {
            _btn_calib_press_start_ms = now_ms;
        } else {
            uint32_t press_duration = now_ms - _btn_calib_press_start_ms;
            if (press_duration >= 1500) {
                state->command.invert_line_polarity = !state->command.invert_line_polarity;
                Serial.printf("[BTN_CALIB] Polaridad linea -> %s (dur=%lums)\n",
                              state->command.invert_line_polarity ? "INVERTIDA" : "NORMAL",
                              (unsigned long)press_duration);
            } else if (press_duration >= 20) {
                if (state->command.target_mode == RobotMode::kIdle ||
                    state->command.target_mode == RobotMode::kReady) {
                    state->command.target_mode = RobotMode::kCalibrating;
                    ++state->command.calib_seq;
                } else if (state->command.target_mode == RobotMode::kCalibrating) {
                    state->command.target_mode = RobotMode::kReady;
                    ++state->command.calib_seq;
                } else {
                    state->command.target_mode = RobotMode::kIdle;
                }
                Serial.printf("[BTN_CALIB] Modo -> %d (dur=%lums)\n",
                              (int)state->command.target_mode,
                              (unsigned long)press_duration);
            }
        }
        _btn_calib_last_raw = raw_calib;
    }

    uint8_t raw_start = digitalRead(hw::kPinBtnStart);
    if (raw_start != _btn_start_last_raw && (now_ms - _btn_start_last_debounce_ms >= 30)) {
        _btn_start_last_debounce_ms = now_ms;
        if (raw_start == LOW) {
            _btn_start_press_start_ms = now_ms;
        } else {
            uint32_t press_duration = now_ms - _btn_start_press_start_ms;
            if (press_duration >= 700) {
                if (state->command.target_mode == RobotMode::kIdle ||
                    state->command.target_mode == RobotMode::kReady) {
                    state->active_profile = (state->active_profile + 1) % kNumProfiles;
                    const auto& p = kProfiles[state->active_profile];
                    state->command.base_speed = p.speed;
                    state->command.pid_kp = p.kp;
                    state->command.pid_kd = p.kd;
                    state->command.pid_ki = 0.0f;
                    state->command.profile_idx = state->active_profile;
                    Preferences prefs;
                    if (prefs.begin("idline", false)) {
                        prefs.putUChar("prof", state->active_profile);
                        prefs.end();
                    }
                    Serial.printf("[BTN_START] Perfil -> %s (speed=%d kp=%.2f kd=%.2f)\n",
                                  p.name, p.speed, p.kp, p.kd);
                }
            } else if (press_duration >= 20) {
                if (state->command.target_mode == RobotMode::kRunning) {
                    state->command.target_mode = RobotMode::kIdle;
                } else {
                    state->command.target_mode = RobotMode::kRunning;
                    ++state->command.run_seq;
                }
                Serial.printf("[BTN_START] Modo -> %s (dur=%lums)\n",
                              state->command.target_mode == RobotMode::kRunning ? "RUNNING" : "IDLE",
                              (unsigned long)press_duration);
            }
        }
        _btn_start_last_raw = raw_start;
    }
}

void Telemetria::tick(uint32_t now_ms, const ControlTelemetry& tel, SupervisorState* state) {
    if (state != nullptr) {
        procesarBotones(now_ms, state);

        RemoteCmdMailbox pending_cmds[kCmdQueueCap]{};
        size_t pending_count = 0;
        portENTER_CRITICAL(&_mux);
        while (pending_count < kCmdQueueCap && popRemoteCmd(pending_cmds[pending_count])) {
            ++pending_count;
        }
        _latest_tel = tel;
        portEXIT_CRITICAL(&_mux);

        for (size_t i = 0; i < pending_count; ++i) {
            const RemoteCmdMailbox& mb = pending_cmds[i];
            if (!mb.has_cmd) continue;
            if (strcmp(mb.cmd, "start_pid") == 0) {
                state->command.target_mode = RobotMode::kRunning;
                ++state->command.run_seq;
                ++state->command.remote_cmd_seq;
            } else if (strcmp(mb.cmd, "stop") == 0) {
                state->command.target_mode = RobotMode::kIdle;
                state->command.manual_m1 = 0;
                state->command.manual_m2 = 0;
                ++state->command.remote_cmd_seq;
            } else if (strcmp(mb.cmd, "calibrate") == 0) {
                if (state->command.target_mode == RobotMode::kCalibrating) {
                    state->command.target_mode = RobotMode::kReady;
                } else {
                    state->command.target_mode = RobotMode::kCalibrating;
                }
                ++state->command.calib_seq;
                ++state->command.remote_cmd_seq;
            } else if (strcmp(mb.cmd, "set_motores") == 0) {
                state->command.target_mode = RobotMode::kRemoteManual;
                state->command.manual_m1 = constrain(mb.m1, -255, 255);
                state->command.manual_m2 = constrain(mb.m2, -255, 255);
                ++state->command.remote_cmd_seq;
            } else if (strcmp(mb.cmd, "set_pid") == 0) {
                if (mb.kp >= 0.0f) state->command.pid_kp = mb.kp;
                if (mb.ki >= 0.0f) state->command.pid_ki = mb.ki;
                if (mb.kd >= 0.0f) state->command.pid_kd = mb.kd;
                if (mb.speed >= 0) state->command.base_speed = mb.speed;
                ++state->command.remote_cmd_seq;
            } else if (strcmp(mb.cmd, "test") == 0) {
                state->command.target_mode = RobotMode::kMotorTest;
                ++state->command.remote_cmd_seq;
            } else if (mb.is_new_track || strcmp(mb.cmd, "new_track") == 0) {
                ++_track_id;
                state->track_id = _track_id;
                ++state->command.remote_cmd_seq;
            } else if (mb.is_upload_memory || strcmp(mb.cmd, "upload_memory") == 0) {
                _uploading_memory = true;
                _upload_offset = 0;
                ++state->upload_memory_seq;
                ++state->command.remote_cmd_seq;
            }
        }

        state->wifi_enabled = _wifi_enabled;
        state->wifi_connected = _wifi_enabled && (WiFi.status() == WL_CONNECTED);
        state->http_connected = _wifi_enabled && _http_connected;
        state->track_id = _track_id;
    }
}

} // namespace idline
