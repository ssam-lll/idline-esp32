#include "sensor.h"

namespace idline {

namespace {

struct CalibRecord {
    uint32_t magic;
    uint8_t  mode;
    uint8_t  reserved[3];
    uint16_t min_vals[16];
    uint16_t max_vals[16];
    uint16_t crc16;
};

constexpr uint32_t kCalibMagic = 0x49444C31; // "IDL1"
constexpr int32_t  kWeights8[8] = {-3500, -2500, -1500, -500, 500, 1500, 2500, 3500};

} // namespace

BarraSensores::BarraSensores(Multiplexor& mux, SensorBarMode modo)
    : _mux(mux), _modo(modo), _calib_valida(false), _last_position(0),
      _last_status(LineStatus::kOnLine), _current_mode(RobotMode::kIdle),
      _test_start_ms(0), _last_calib_seq(0), _last_run_seq(0), _last_remote_seq(0),
      _last_tick_us(0) {
    for (uint8_t i = 0; i < 16; ++i) {
        _calib_min[i] = 4095;
        _calib_max[i] = 0;
    }
}

uint16_t BarraSensores::calcularCrc(const uint8_t* data, size_t len) const {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; ++i) {
        crc ^= static_cast<uint16_t>(data[i]);
        for (uint8_t j = 0; j < 8; ++j) {
            if (crc & 1) {
                crc = (crc >> 1) ^ 0xA001;
            } else {
                crc >>= 1;
            }
        }
    }
    return crc;
}

void BarraSensores::begin() {
    if (!cargarCalibracion()) {
        for (uint8_t i = 0; i < 16; ++i) {
            _calib_min[i] = 200;
            _calib_max[i] = 3800;
        }
        _calib_valida = false;
    }
}

void BarraSensores::leerBarra(int valores[8]) {
    for (uint8_t i = 0; i < kNumSensores8; ++i) {
        valores[i] = _mux.leerCanal(_canales8[i]);
    }
}

int BarraSensores::verificarError(int valor) {
    if (valor < 0 || valor > 4095) {
        return 101;
    }
    return 0;
}

void BarraSensores::resetCalibracion() {
    for (uint8_t i = 0; i < 16; ++i) {
        _calib_min[i] = 4095;
        _calib_max[i] = 0;
    }
    _calib_valida = false;
}

void BarraSensores::acumularCalibracion(const RawSensorFrame& frame) {
    uint8_t start = (_modo == SensorBarMode::kCenter8_C4_C11) ? 4 : 0;
    uint8_t end   = (_modo == SensorBarMode::kCenter8_C4_C11) ? 12 : 16;

    for (uint8_t i = start; i < end; ++i) {
        uint16_t v = frame.adc_raw[i];
        if (v < _calib_min[i]) _calib_min[i] = v;
        if (v > _calib_max[i]) _calib_max[i] = v;
    }
    _calib_valida = true;
}

bool BarraSensores::cargarCalibracion() {
    Preferences prefs;
    if (!prefs.begin("idline", true)) {
        return false;
    }

    CalibRecord rec{};
    size_t len = prefs.getBytes("calib", &rec, sizeof(rec));
    prefs.end();

    if (len != sizeof(rec) || rec.magic != kCalibMagic) {
        return false;
    }

    uint16_t expected_crc = calcularCrc(reinterpret_cast<const uint8_t*>(&rec), sizeof(rec) - sizeof(rec.crc16));
    if (rec.crc16 != expected_crc) {
        return false;
    }

    for (uint8_t i = 0; i < 16; ++i) {
        _calib_min[i] = rec.min_vals[i];
        _calib_max[i] = rec.max_vals[i];
    }
    _modo = static_cast<SensorBarMode>(rec.mode);
    _calib_valida = true;
    return true;
}

void BarraSensores::guardarCalibracion() {
    Preferences prefs;
    if (!prefs.begin("idline", false)) {
        return;
    }

    CalibRecord rec{};
    rec.magic = kCalibMagic;
    rec.mode = static_cast<uint8_t>(_modo);
    for (uint8_t i = 0; i < 16; ++i) {
        rec.min_vals[i] = _calib_min[i];
        rec.max_vals[i] = _calib_max[i];
    }
    rec.crc16 = calcularCrc(reinterpret_cast<const uint8_t*>(&rec), sizeof(rec) - sizeof(rec.crc16));

    prefs.putBytes("calib", &rec, sizeof(rec));
    prefs.end();
}

ControlTelemetry BarraSensores::procesarPaso(const RawSensorFrame& frame,
                                             const SupervisorCommand& cmd,
                                             ControladorPID& pid,
                                             Motor& motor,
                                             uint32_t t0_us,
                                             uint32_t tick) {
    ControlTelemetry tel{};
    tel.tick = tick;
    tel.ack_remote_cmd_seq = cmd.remote_cmd_seq;

    uint16_t vbat_mv = static_cast<uint16_t>(
        (static_cast<uint32_t>(frame.batt_raw) * (hw::kBattR1_Ohms + hw::kBattR2_Ohms)) / hw::kBattR2_Ohms);
    tel.vbat_mv = vbat_mv;

    if (cmd.calib_seq != _last_calib_seq) {
        _last_calib_seq = cmd.calib_seq;
        if (cmd.target_mode == RobotMode::kCalibrating) {
            resetCalibracion();
        } else if (_current_mode == RobotMode::kCalibrating) {
            guardarCalibracion();
        }
    }

    if (cmd.target_mode == RobotMode::kMotorTest) {
        if (cmd.remote_cmd_seq != _last_remote_seq) {
            _last_remote_seq = cmd.remote_cmd_seq;
            _test_start_ms = millis();
            _current_mode = RobotMode::kMotorTest;
        }
    } else if (cmd.target_mode != _current_mode) {
        if (cmd.target_mode == RobotMode::kRunning) {
            pid.reset();
        }
        _current_mode = cmd.target_mode;
    }

    for (uint8_t i = 0; i < 16; ++i) {
        tel.raw_values[i] = frame.adc_raw[i];
    }

    uint8_t general_error = 0;
    if (_modo == SensorBarMode::kCenter8_C4_C11) {
        for (uint8_t i = 4; i <= 11; ++i) {
            if (verificarError(frame.adc_raw[i]) != 0) {
                general_error = 101;
            }
        }
    }
    tel.sensor_error = general_error;

    if (_current_mode == RobotMode::kCalibrating) {
        acumularCalibracion(frame);
    }

    int32_t sum_weighted = 0;
    int32_t sum_norm = 0;

    for (uint8_t i = 0; i < 8; ++i) {
        uint8_t ch = _canales8[i];
        uint16_t val = frame.adc_raw[ch];
        uint16_t min_v = _calib_min[ch];
        uint16_t max_v = _calib_max[ch];
        uint16_t span = (max_v > min_v) ? (max_v - min_v) : 1;
        if (span < 50) span = 50;

        uint16_t clamped = constrain(val, min_v, max_v);
        uint16_t norm = 0;
        if (cmd.invert_line_polarity) {
            norm = static_cast<uint16_t>((static_cast<uint32_t>(max_v - clamped) * 1000UL) / span);
        } else {
            norm = static_cast<uint16_t>((static_cast<uint32_t>(clamped - min_v) * 1000UL) / span);
        }
        tel.normalized[ch] = norm;

        sum_weighted += static_cast<int32_t>(norm) * kWeights8[i];
        sum_norm += static_cast<int32_t>(norm);
    }

    if (sum_norm < 150) {
        if (_last_position < 0) {
            _last_status = LineStatus::kLostLeft;
            tel.position = -1000;
        } else {
            _last_status = LineStatus::kLostRight;
            tel.position = 1000;
        }
    } else {
        _last_status = LineStatus::kOnLine;
        int32_t pos3500 = sum_weighted / sum_norm;
        int16_t pos1000 = static_cast<int16_t>(constrain((pos3500 * 2) / 7, -1000, 1000));
        tel.position = pos1000;
        _last_position = pos1000;
    }
    tel.line_status = _last_status;

    if (vbat_mv >= hw::kBattUsbFloor_mV && vbat_mv < hw::kBattCutoff_mV) {
        _current_mode = RobotMode::kFaultLowBatt;
        motor.desactivar();
        tel.current_mode = _current_mode;
        return tel;
    }

    float dt_sec = 0.001f;
    if (_last_tick_us > 0 && t0_us > _last_tick_us) {
        dt_sec = static_cast<float>(t0_us - _last_tick_us) * 1e-6f;
    }
    _last_tick_us = t0_us;

    int16_t pid_out = 0;
    if (_current_mode == RobotMode::kRunning) {
        if (cmd.pid_kp > 0.0f) {
            pid.setGains(cmd.pid_kp, cmd.pid_ki, cmd.pid_kd, cmd.base_speed);
        }
        DriveCommand drive = pid.calcular(tel.position, tel.line_status, dt_sec, &pid_out);
        motor.aplicar(drive);
    } else if (_current_mode == RobotMode::kRemoteManual) {
        motor.setMotores(cmd.manual_m1, cmd.manual_m2);
    } else if (_current_mode == RobotMode::kMotorTest) {
        uint32_t elapsed = millis() - _test_start_ms;
        DriveCommand test_cmd = motor.evaluarPruebaNoBloqueante(elapsed);
        motor.aplicar(test_cmd);
        if (elapsed >= 2200) {
            _current_mode = RobotMode::kIdle;
        }
    } else {
        motor.desactivar();
    }

    tel.current_mode = _current_mode;
    tel.m1_pwm = static_cast<int16_t>(motor.getVelocidadM1());
    tel.m2_pwm = static_cast<int16_t>(motor.getVelocidadM2());
    tel.pid_out = pid_out;

    return tel;
}

} // namespace idline
