#include "pantalla.h"

namespace idline {

namespace {

constexpr uint16_t COLOR_BG       = ST77XX_BLACK;
constexpr uint16_t COLOR_TEXT     = ST77XX_WHITE;
constexpr uint16_t COLOR_BAR      = ST77XX_CYAN;
constexpr uint16_t COLOR_BAR_BG   = 0x18E3;
constexpr uint16_t COLOR_RETICLE  = ST77XX_GREEN;
constexpr uint16_t COLOR_CURSOR   = ST77XX_YELLOW;
constexpr uint16_t COLOR_ALERT    = ST77XX_RED;

const char* obtenerNombreModo(RobotMode mode) {
    switch (mode) {
        case RobotMode::kIdle:         return "IDLE";
        case RobotMode::kCalibrating:  return "CALIB";
        case RobotMode::kReady:        return "READY";
        case RobotMode::kRunning:      return "RUN";
        case RobotMode::kRemoteManual: return "MANUAL";
        case RobotMode::kMotorTest:    return "TEST";
        case RobotMode::kFaultLowBatt: return "LOW BATT";
        default:                       return "UNKNOWN";
    }
}

uint16_t obtenerColorModo(RobotMode mode) {
    switch (mode) {
        case RobotMode::kRunning:      return ST77XX_GREEN;
        case RobotMode::kReady:        return ST77XX_CYAN;
        case RobotMode::kCalibrating:  return ST77XX_YELLOW;
        case RobotMode::kMotorTest:    return ST77XX_ORANGE;
        case RobotMode::kRemoteManual: return ST77XX_MAGENTA;
        case RobotMode::kFaultLowBatt: return ST77XX_RED;
        default:                       return 0x8410;
    }
}

} // namespace

PantallaTFT::PantallaTFT(uint8_t cs, uint8_t dc, uint8_t rst, uint8_t sck, uint8_t mosi)
    : _pinCs(cs), _pinDc(dc), _pinRst(rst), _pinSck(sck), _pinMosi(mosi),
      _tft(&SPI, cs, dc, rst), _initialized(false), _last_render_ms(0), _last_resync_ms(0),
      _path{}, _path_count(0), _last_point_x(0.0f), _last_point_y(0.0f),
      _odom_x(0.0f), _odom_y(0.0f), _odom_theta(1.5707963f), _last_odom_ms(0),
      _prev_scr_x{}, _prev_scr_y{}, _prev_scr_count(0),
      _prev_robot_x(0), _prev_robot_y(0), _prev_head_x(0), _prev_head_y(0) {
    memset(&_prev, 0xFF, sizeof(_prev));
}

void PantallaTFT::resetOdometria() {
    _odom_x = 0.0f;
    _odom_y = 0.0f;
    _odom_theta = 1.5707963f;
    _last_point_x = 0.0f;
    _last_point_y = 0.0f;
    _path_count = 0;
    _prev_scr_count = 0;
    _last_odom_ms = 0;
}

void PantallaTFT::despertarControlador() {
    spiDetachMISO(SPI.bus(), -1);
    pinMode(_pinDc, OUTPUT);
    pinMode(_pinCs, OUTPUT);
    _tft.setSPISpeed(16000000);
    _tft.sendCommand(ST77XX_SLPOUT);
    uint8_t colmod = 0x55;
    _tft.sendCommand(ST77XX_COLMOD, &colmod, 1);
    _tft.setRotation(0);
    _tft.sendCommand(ST77XX_INVON);
    _tft.sendCommand(ST77XX_NORON);
    _tft.sendCommand(ST77XX_DISPON);
}

void PantallaTFT::begin() {
    delay(100);
    SPI.begin(_pinSck, -1, _pinMosi, _pinCs);
    _tft.init(hw::kTftWidth, hw::kTftHeight, SPI_MODE0);
    _tft.setSPISpeed(16000000);
    spiDetachMISO(SPI.bus(), -1);
    pinMode(_pinDc, OUTPUT);
    digitalWrite(_pinDc, HIGH);

    pinMode(_pinRst, OUTPUT);
    digitalWrite(_pinRst, LOW);
    delay(50);
    digitalWrite(_pinRst, HIGH);
    delay(150);

    _tft.sendCommand(ST77XX_SWRESET);
    delay(150);
    despertarControlador();
    delay(150);
    despertarControlador();
    delay(50);

    _tft.fillScreen(COLOR_BG);

    memset(&_prev, 0xFF, sizeof(_prev));
    _prev.position = 10000;

    dibujarEstructuraEstatica();
    _last_resync_ms = millis();
    _initialized = true;
}

void PantallaTFT::dibujarEstructuraEstatica() {
    _tft.drawFastHLine(0, 36, hw::kTftWidth, 0x4208);
    _tft.drawFastHLine(0, 138, hw::kTftWidth, 0x4208);
    _tft.drawFastHLine(0, 180, hw::kTftWidth, 0x4208);

    _tft.setTextSize(1);
    _tft.setTextColor(0x8410);
    _tft.setCursor(4, 40);
    _tft.print("SENSORES C4..C11");

    constexpr int16_t kBarWidth = 18;
    constexpr int16_t kBarGap = 8;
    constexpr int16_t kStartX = 18;
    constexpr int16_t kBaselineY = 130;

    for (uint8_t i = 0; i < 8; ++i) {
        int16_t x = kStartX + i * (kBarWidth + kBarGap);
        _tft.drawFastHLine(x, kBaselineY, kBarWidth, 0x4208);
    }

    _tft.setCursor(4, 142);
    _tft.print("POSICION LINEA");

    constexpr int16_t kLineY = 162;
    constexpr int16_t kCenterX = 120;
    constexpr int16_t kHalfSpan = 90;
    _tft.drawFastHLine(kCenterX - kHalfSpan, kLineY, kHalfSpan * 2, COLOR_RETICLE);
    _tft.drawFastVLine(kCenterX, kLineY - 4, 9, COLOR_RETICLE);
}

void PantallaTFT::renderizarHeader(const UiViewModel& curr) {
    if (curr.mode != _prev.mode) {
        _tft.fillRect(4, 4, 110, 16, COLOR_BG);
        _tft.setTextSize(2);
        _tft.setTextColor(obtenerColorModo(curr.mode));
        _tft.setCursor(4, 4);
        _tft.print(obtenerNombreModo(curr.mode));
    }

    if ((curr.vbat_mv / 100) != (_prev.vbat_mv / 100)) {
        _tft.fillRect(140, 4, 96, 16, COLOR_BG);
        _tft.setTextSize(2);
        if (curr.vbat_mv >= hw::kBattUsbFloor_mV && curr.vbat_mv < hw::kBattCutoff_mV) {
            _tft.setTextColor(COLOR_ALERT);
        } else {
            _tft.setTextColor(ST77XX_GREEN);
        }
        _tft.setCursor(140, 4);
        _tft.printf("%.2fV", curr.vbat_mv / 1000.0f);
    }

    if (curr.wifi_connected != _prev.wifi_connected ||
        curr.http_connected != _prev.http_connected ||
        curr.wifi_enabled != _prev.wifi_enabled) {
        _tft.fillRect(4, 22, 230, 10, COLOR_BG);
        _tft.setTextSize(1);
        _tft.setCursor(4, 23);
        if (!curr.wifi_enabled) {
            _tft.setTextColor(0x8410);
            _tft.print("WiFi: OFF (MODO COMPETENCIA)");
        } else {
            if (curr.http_connected) {
                _tft.setTextColor(ST77XX_GREEN);
                _tft.print("WIFI:HTTP");
            } else {
                _tft.setTextColor(curr.wifi_connected ? ST77XX_YELLOW : 0x8410);
                _tft.print("WIFI:WAIT");
            }
        }
    }
}

void PantallaTFT::renderizarSensores(const UiViewModel& curr) {
    constexpr int16_t kBarWidth = 18;
    constexpr int16_t kBarGap = 8;
    constexpr int16_t kStartX = 18;
    constexpr int16_t kBaselineY = 130;
    constexpr int16_t kMaxHeight = 65;

    for (uint8_t i = 0; i < 8; ++i) {
        int16_t new_h = constrain(static_cast<int16_t>(curr.bar_heights[i]), 0, kMaxHeight);
        bool force_full = (_prev.bar_heights[i] == 0xFF);
        int16_t old_h = force_full ? -1 : constrain(static_cast<int16_t>(_prev.bar_heights[i]), 0, kMaxHeight);

        if (force_full) {
            int16_t x = kStartX + i * (kBarWidth + kBarGap);
            if (new_h < kMaxHeight) {
                _tft.fillRect(x, kBaselineY - kMaxHeight, kBarWidth, kMaxHeight - new_h, COLOR_BAR_BG);
            }
            if (new_h > 0) {
                _tft.fillRect(x, kBaselineY - new_h, kBarWidth, new_h, COLOR_BAR);
            }
            _tft.drawFastHLine(x, kBaselineY, kBarWidth, 0x4208);
        } else if (new_h != old_h) {
            int16_t x = kStartX + i * (kBarWidth + kBarGap);

            if (new_h < old_h) {
                _tft.fillRect(x, kBaselineY - old_h, kBarWidth, old_h - new_h, COLOR_BAR_BG);
            } else if (new_h > old_h) {
                _tft.fillRect(x, kBaselineY - new_h, kBarWidth, new_h - old_h, COLOR_BAR);
            }
            _tft.drawFastHLine(x, kBaselineY, kBarWidth, 0x4208);
        }
    }
}

void PantallaTFT::renderizarReticula(const UiViewModel& curr) {
    constexpr int16_t kLineY = 162;
    constexpr int16_t kCenterX = 120;
    constexpr int16_t kHalfSpan = 90;

    int16_t clamped_curr = constrain(curr.position, static_cast<int16_t>(-1000), static_cast<int16_t>(1000));
    int16_t new_x = kCenterX + (clamped_curr * kHalfSpan) / 1000;
    bool prev_valid = (_prev.position >= -1000 && _prev.position <= 1000);
    int16_t old_x = prev_valid ? (kCenterX + (_prev.position * kHalfSpan) / 1000) : -1;

    if (!prev_valid || old_x != new_x) {
        if (prev_valid) {
            _tft.fillRect(old_x - 3, kLineY - 6, 7, 13, COLOR_BG);
        }
        _tft.drawFastHLine(kCenterX - kHalfSpan, kLineY, kHalfSpan * 2, COLOR_RETICLE);
        _tft.drawFastVLine(kCenterX, kLineY - 4, 9, COLOR_RETICLE);
        _tft.fillRect(new_x - 3, kLineY - 6, 7, 13, COLOR_CURSOR);
    }
}

void PantallaTFT::renderizarMiniMapa(uint32_t now_ms, const UiViewModel& curr) {
    if (_last_odom_ms == 0) {
        _last_odom_ms = now_ms;
    }
    float dt = (now_ms - _last_odom_ms) * 0.001f;
    _last_odom_ms = now_ms;
    if (dt <= 0.0001f || dt > 0.2f) {
        dt = 0.033f;
    }

    float vbat_v = curr.vbat_mv * 0.001f;
    if (vbat_v < 6.0f) {
        vbat_v = 7.4f;
    }
    float v_scale = (vbat_v / 8.0f) * (1200.0f / 255.0f);
    float vl = curr.m1 * v_scale;
    float vr = curr.m2 * v_scale;

    float v = (vl + vr) * 0.5f;
    float omega = (vr - vl) / 95.0f;

    float theta_mid = _odom_theta + omega * dt * 0.5f;
    _odom_x += v * cosf(theta_mid) * dt;
    _odom_y += v * sinf(theta_mid) * dt;
    _odom_theta += omega * dt;

    while (_odom_theta > 3.14159265f) _odom_theta -= 6.2831853f;
    while (_odom_theta < -3.14159265f) _odom_theta += 6.2831853f;

    float dx = _odom_x - _last_point_x;
    float dy = _odom_y - _last_point_y;
    if (_path_count == 0 || (dx * dx + dy * dy >= 25.0f * 25.0f)) {
        _last_point_x = _odom_x;
        _last_point_y = _odom_y;
        if (_path_count < kPathCapacity) {
            _path[_path_count++] = { _odom_x, _odom_y };
        } else {
            memmove(&_path[0], &_path[1], (kPathCapacity - 1) * sizeof(Point2D));
            _path[kPathCapacity - 1] = { _odom_x, _odom_y };
        }
    }

    float min_x = _odom_x;
    float max_x = _odom_x;
    float min_y = _odom_y;
    float max_y = _odom_y;
    for (size_t i = 0; i < _path_count; ++i) {
        if (_path[i].x < min_x) min_x = _path[i].x;
        if (_path[i].x > max_x) max_x = _path[i].x;
        if (_path[i].y < min_y) min_y = _path[i].y;
        if (_path[i].y > max_y) max_y = _path[i].y;
    }

    float span_x = max_x - min_x;
    float span_y = max_y - min_y;
    if (span_x < 200.0f) span_x = 200.0f;
    if (span_y < 200.0f) span_y = 200.0f;

    float scale_x = 210.0f / (span_x * 1.15f);
    float scale_y = 114.0f / (span_y * 1.15f);
    float scale = (scale_x < scale_y) ? scale_x : scale_y;

    float mid_x = (min_x + max_x) * 0.5f;
    float mid_y = (min_y + max_y) * 0.5f;

    auto to_sx = [&](float wx) -> int16_t {
        int16_t s = 120 + static_cast<int16_t>((wx - mid_x) * scale);
        return constrain(s, static_cast<int16_t>(6), static_cast<int16_t>(234));
    };

    auto to_sy = [&](float wy) -> int16_t {
        int16_t s = 110 - static_cast<int16_t>((wy - mid_y) * scale);
        return constrain(s, static_cast<int16_t>(44), static_cast<int16_t>(174));
    };

    if (_prev_scr_count > 1) {
        for (size_t i = 0; i < _prev_scr_count - 1; ++i) {
            _tft.drawLine(_prev_scr_x[i], _prev_scr_y[i], _prev_scr_x[i + 1], _prev_scr_y[i + 1], COLOR_BG);
        }
    }
    if (_prev_scr_count > 0) {
        _tft.fillCircle(_prev_robot_x, _prev_robot_y, 3, COLOR_BG);
        _tft.drawLine(_prev_robot_x, _prev_robot_y, _prev_head_x, _prev_head_y, COLOR_BG);
    }

    for (size_t i = 0; i < _path_count; ++i) {
        _prev_scr_x[i] = to_sx(_path[i].x);
        _prev_scr_y[i] = to_sy(_path[i].y);
    }
    _prev_scr_count = _path_count;

    if (_prev_scr_count > 1) {
        for (size_t i = 0; i < _prev_scr_count - 1; ++i) {
            _tft.drawLine(_prev_scr_x[i], _prev_scr_y[i], _prev_scr_x[i + 1], _prev_scr_y[i + 1], ST77XX_CYAN);
        }
    }

    _prev_robot_x = to_sx(_odom_x);
    _prev_robot_y = to_sy(_odom_y);
    _prev_head_x = _prev_robot_x + static_cast<int16_t>(cosf(_odom_theta) * 6.0f);
    _prev_head_y = _prev_robot_y - static_cast<int16_t>(sinf(_odom_theta) * 6.0f);

    _tft.fillCircle(_prev_robot_x, _prev_robot_y, 3, ST77XX_YELLOW);
    _tft.drawLine(_prev_robot_x, _prev_robot_y, _prev_head_x, _prev_head_y, ST77XX_RED);
}

void PantallaTFT::renderizarFooter(const UiViewModel& curr) {
    if (curr.m1 != _prev.m1 || curr.m2 != _prev.m2 || curr.profile_idx != _prev.profile_idx || (curr.loop_time_us / 100) != (_prev.loop_time_us / 100)) {
        _tft.fillRect(4, 186, 232, 50, COLOR_BG);
        _tft.setTextSize(1);
        _tft.setTextColor(COLOR_TEXT);

        _tft.setCursor(4, 190);
        _tft.printf("M1:%+4d  M2:%+4d", curr.m1, curr.m2);

        _tft.setCursor(140, 190);
        _tft.printf("Loop:%4uus", curr.loop_time_us);

        _tft.setCursor(4, 210);
        _tft.setTextSize(1);
        _tft.setTextColor(ST77XX_YELLOW);
        uint8_t pidx = curr.profile_idx % kNumProfiles;
        _tft.printf("PERFIL: %s (%d)", kProfiles[pidx].name, kProfiles[pidx].speed);
    }
}

void PantallaTFT::renderizarDiferencial(uint32_t now_ms, const SupervisorState& state, const ControlTelemetry& tel) {
    if (!_initialized) {
        return;
    }

    uint32_t min_interval_ms = (tel.current_mode == RobotMode::kRunning) ? 50 : 30;
    if (now_ms - _last_render_ms < min_interval_ms) {
        return;
    }
    _last_render_ms = now_ms;

    UiViewModel curr{};
    curr.mode = tel.current_mode;
    curr.vbat_mv = tel.vbat_mv;
    curr.wifi_enabled = state.wifi_enabled;
    curr.wifi_connected = state.wifi_connected;
    curr.http_connected = state.http_connected;
    curr.profile_idx = state.active_profile;
    curr.track_id = state.track_id;
    curr.position = (tel.position / 25) * 25;
    curr.m1 = tel.m1_pwm;
    curr.m2 = tel.m2_pwm;
    curr.loop_time_us = tel.loop_time_us;

    for (uint8_t i = 0; i < 8; ++i) {
        uint8_t ch = 4 + i;
        curr.bar_heights[i] = static_cast<uint8_t>((tel.normalized[ch] * 65UL) / 1000UL);
    }

    if (curr.mode != RobotMode::kRunning && (now_ms - _last_resync_ms >= 3000)) {
        _last_resync_ms = now_ms;
        despertarControlador();
        dibujarEstructuraEstatica();
    }

    renderizarHeader(curr);

    if (curr.mode == RobotMode::kRunning) {
        if (_prev.mode != RobotMode::kRunning || curr.track_id != _prev.track_id) {
            _tft.fillRect(0, 37, hw::kTftWidth, 143, COLOR_BG);
            _tft.setTextSize(1);
            _tft.setTextColor(0x8410);
            _tft.setCursor(4, 40);
            _tft.printf("PISTA LIVE #%u", curr.track_id);
            resetOdometria();
        }
        renderizarMiniMapa(now_ms, curr);
    } else {
        if (_prev.mode == RobotMode::kRunning) {
            _tft.fillRect(0, 37, hw::kTftWidth, 143, COLOR_BG);
            dibujarEstructuraEstatica();
            memset(_prev.bar_heights, 0xFF, sizeof(_prev.bar_heights));
            _prev.position = 10000;
        }
        renderizarSensores(curr);
        renderizarReticula(curr);
    }

    renderizarFooter(curr);

    _prev = curr;
}

} // namespace idline
