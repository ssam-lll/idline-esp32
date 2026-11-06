#include "telemetria.h"
#include <ArduinoJson.h>
#include <ArduinoOTA.h>
#include <Preferences.h>

namespace idline {

static Telemetria* s_instancia = nullptr;
static bool s_ota_iniciado = false;

static void mqttStaticCallback(char* topic, byte* payload, unsigned int length) {
    if (s_instancia) {
        s_instancia->procesarMensaje(topic, payload, length);
    }
}

Telemetria::Telemetria(const char* ssid, const char* pass, const char* broker, int port, const char* clientId)
    : _ssid(ssid), _pass(pass), _broker(broker), _port(port), _clientId(clientId),
      _mqtt(_espClient), _lastReconnectMillis(0), _motorCallback(nullptr),
      _active_state(nullptr), _last_telemetry_ms(0), _last_ack_seq(0), _wifi_enabled(false),
      _btn_calib_last_raw(HIGH), _btn_calib_press_start_ms(0), _btn_calib_last_debounce_ms(0),
      _btn_start_last_raw(HIGH), _btn_start_press_start_ms(0), _btn_start_last_debounce_ms(0) {
    s_instancia = this;
}

void Telemetria::setMotorCallback(ComandoMotorCallback callback) {
    _motorCallback = callback;
}

void Telemetria::begin(bool enable_wifi) {
    _wifi_enabled = enable_wifi;
    pinMode(hw::kPinBtnCalib, INPUT_PULLUP);
    pinMode(hw::kPinBtnStart, INPUT_PULLUP);

    if (_wifi_enabled) {
        WiFi.mode(WIFI_STA);
        WiFi.begin(_ssid, _pass);
        _mqtt.setServer(_broker, _port);
        _mqtt.setCallback(mqttStaticCallback);
        _mqtt.setBufferSize(512);
    } else {
        WiFi.mode(WIFI_OFF);
    }
}

void Telemetria::mantenerConexion(unsigned long currentMillis) {
    if (!_wifi_enabled) {
        return;
    }
    if (WiFi.status() == WL_CONNECTED) {
        if (!s_ota_iniciado) {
            ArduinoOTA.setHostname("idline-esp32");
            ArduinoOTA.begin();
            s_ota_iniciado = true;
        }
        ArduinoOTA.handle();
        if (!_mqtt.connected() && (currentMillis - _lastReconnectMillis >= _reconnectInterval)) {
            _lastReconnectMillis = currentMillis;
            if (_mqtt.connect(_clientId)) {
                _mqtt.subscribe("control/motores", 1);
            }
        }
        if (_mqtt.connected()) {
            _mqtt.loop();
        }
    }
}

void Telemetria::procesarMensaje(char* topic, byte* payload, unsigned int length) {
    if (strcmp(topic, "control/motores") == 0) {
        JsonDocument doc;
        DeserializationError error = deserializeJson(doc, payload, length);
        if (error) {
            return;
        }

        const char* cmd = doc["cmd"] | "";
        int m1 = doc["m1"] | 0;
        int m2 = doc["m2"] | 0;

        if (_active_state) {
            if (strcmp(cmd, "set_motores") == 0) {
                _active_state->command.target_mode = RobotMode::kRemoteManual;
                _active_state->command.manual_m1 = constrain(m1, -255, 255);
                _active_state->command.manual_m2 = constrain(m2, -255, 255);
                ++_active_state->command.remote_cmd_seq;
            } else if (strcmp(cmd, "stop") == 0) {
                _active_state->command.target_mode = RobotMode::kIdle;
                _active_state->command.manual_m1 = 0;
                _active_state->command.manual_m2 = 0;
                ++_active_state->command.remote_cmd_seq;
            } else if (strcmp(cmd, "test") == 0) {
                _active_state->command.target_mode = RobotMode::kMotorTest;
                ++_active_state->command.remote_cmd_seq;
            } else if (strcmp(cmd, "calibrate") == 0) {
                if (_active_state->command.target_mode == RobotMode::kCalibrating) {
                    _active_state->command.target_mode = RobotMode::kReady;
                } else {
                    _active_state->command.target_mode = RobotMode::kCalibrating;
                }
                ++_active_state->command.calib_seq;
                ++_active_state->command.remote_cmd_seq;
            } else if (strcmp(cmd, "start_pid") == 0) {
                _active_state->command.target_mode = RobotMode::kRunning;
                ++_active_state->command.run_seq;
                ++_active_state->command.remote_cmd_seq;
            } else if (strcmp(cmd, "set_pid") == 0) {
                if (doc["kp"].is<float>()) _active_state->command.pid_kp = doc["kp"];
                if (doc["ki"].is<float>()) _active_state->command.pid_ki = doc["ki"];
                if (doc["kd"].is<float>()) _active_state->command.pid_kd = doc["kd"];
                if (doc["speed"].is<int16_t>()) _active_state->command.base_speed = doc["speed"];
                ++_active_state->command.remote_cmd_seq;
            }
        }

        if (_motorCallback) {
            _motorCallback(cmd, m1, m2);
        }
    }
}

void Telemetria::publicarSensores(const int valores[8], int error) {
    JsonDocument doc;
    JsonArray arr = doc["sensores"].to<JsonArray>();
    for (int i = 0; i < 8; ++i) {
        arr.add(valores[i]);
    }
    doc["error"] = error;

    char buffer[256];
    serializeJson(doc, buffer);

    if (_mqtt.connected()) {
        _mqtt.publish("telemetria/sensores", buffer);
    }
}

void Telemetria::publicarEstadoMotores(int m1, int m2, const char* status) {
    JsonDocument doc;
    doc["m1"] = m1;
    doc["m2"] = m2;
    doc["status"] = status;

    char buffer[128];
    serializeJson(doc, buffer);

    if (_mqtt.connected()) {
        _mqtt.publish("telemetria/motores/estado", buffer);
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
            } else if (press_duration >= 40) {
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
                    state->active_profile = (state->active_profile + 1) % 3;
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
                }
            } else if (press_duration >= 40) {
                if (state->command.target_mode == RobotMode::kRunning) {
                    state->command.target_mode = RobotMode::kIdle;
                } else {
                    state->command.target_mode = RobotMode::kRunning;
                    ++state->command.run_seq;
                }
            }
        }
        _btn_start_last_raw = raw_start;
    }
}

void Telemetria::tick(uint32_t now_ms, const ControlTelemetry& tel, SupervisorState* state) {
    _active_state = state;
    procesarBotones(now_ms, state);
    mantenerConexion(now_ms);

    state->wifi_enabled = _wifi_enabled;
    state->wifi_connected = _wifi_enabled && (WiFi.status() == WL_CONNECTED);
    state->mqtt_connected = _wifi_enabled && _mqtt.connected();

    if (!_wifi_enabled) {
        return;
    }

    if (tel.ack_remote_cmd_seq != _last_ack_seq && tel.ack_remote_cmd_seq != 0) {
        _last_ack_seq = tel.ack_remote_cmd_seq;
        const char* status_str = "OK";
        if (tel.current_mode == RobotMode::kIdle) {
            status_str = "STOPPED";
        } else if (tel.current_mode == RobotMode::kMotorTest) {
            status_str = "TESTING";
        } else if (tel.current_mode == RobotMode::kFaultLowBatt) {
            status_str = "LOW_BATT";
        }
        publicarEstadoMotores(tel.m1_pwm, tel.m2_pwm, status_str);
    }

    if (now_ms - _last_telemetry_ms >= hw::kTelemetryIntervalMs) {
        _last_telemetry_ms = now_ms;

        JsonDocument doc;
        JsonArray arr = doc["sensores"].to<JsonArray>();
        for (uint8_t i = 4; i <= 11; ++i) {
            arr.add(tel.raw_values[i]);
        }
        doc["error"] = tel.sensor_error;
        doc["posicion"] = tel.position;
        doc["vbat_mv"] = tel.vbat_mv;

        switch (tel.current_mode) {
            case RobotMode::kRunning:      doc["modo"] = "RUNNING"; break;
            case RobotMode::kCalibrating:  doc["modo"] = "CALIBRATING"; break;
            case RobotMode::kReady:        doc["modo"] = "READY"; break;
            case RobotMode::kRemoteManual: doc["modo"] = "MANUAL"; break;
            case RobotMode::kMotorTest:    doc["modo"] = "TESTING"; break;
            case RobotMode::kFaultLowBatt: doc["modo"] = "LOW_BATT"; break;
            default:                       doc["modo"] = "IDLE"; break;
        }

        doc["m1"] = tel.m1_pwm;
        doc["m2"] = tel.m2_pwm;

        char buffer[320];
        serializeJson(doc, buffer);

        if (_mqtt.connected()) {
            _mqtt.publish("telemetria/sensores", buffer);
        }
    }
}

} // namespace idline
