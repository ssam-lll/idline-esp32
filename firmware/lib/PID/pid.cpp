#include "pid.h"

namespace idline {

ControladorPID::ControladorPID(const PidTuning& tuning)
    : _tuning(tuning), _integral(0.0f), _last_error(0.0f), _d_filtered(0.0f) {}

void ControladorPID::reset() {
    _integral = 0.0f;
    _last_error = 0.0f;
    _d_filtered = 0.0f;
}

void ControladorPID::actualizarParametros(const PidTuning& tuning) {
    _tuning = tuning;
}

void ControladorPID::setGains(float kp, float ki, float kd, int16_t base_speed) {
    _tuning.kp = kp;
    _tuning.ki = ki;
    _tuning.kd = kd;
    _tuning.base_speed = base_speed;
}

DriveCommand ControladorPID::calcular(int16_t position, LineStatus line_status, float dt_sec, int16_t* out_pid) {
    if (dt_sec <= 0.0f || dt_sec > 0.05f) {
        dt_sec = 0.001f;
    }
    float dt_ms = constrain(dt_sec * 1000.0f, 0.5f, 50.0f);

    if (line_status == LineStatus::kLostLeft) {
        if (out_pid) *out_pid = -_tuning.max_speed;
        int16_t outer = (_tuning.base_speed < 620) ? 620 : _tuning.base_speed;
        int16_t inner = -360;
        return DriveCommand::diff(inner, outer);
    }

    if (line_status == LineStatus::kLostRight) {
        if (out_pid) *out_pid = _tuning.max_speed;
        int16_t outer = (_tuning.base_speed < 620) ? 620 : _tuning.base_speed;
        int16_t inner = -360;
        return DriveCommand::diff(outer, inner);
    }

    float error = static_cast<float>(position);
    float p_term = _tuning.kp * error;

    _integral += _tuning.ki * error * dt_sec;
    _integral = constrain(_integral, -static_cast<float>(_tuning.max_integral), static_cast<float>(_tuning.max_integral));

    float derivative = (error - _last_error) / dt_ms;
    _d_filtered = _tuning.lpf_alpha * derivative + (1.0f - _tuning.lpf_alpha) * _d_filtered;
    _last_error = error;
    float d_term = _tuning.kd * _d_filtered;

    float pid_total = p_term + _integral + d_term;
    if (out_pid) {
        *out_pid = static_cast<int16_t>(pid_total);
    }

    // Reducción adaptativa: rápido en rectas, dosificado en curvas
    int16_t abs_error = (position < 0) ? -position : position;
    int16_t reduccion_curva = (abs_error * 180) / 1000;
    int16_t current_speed = _tuning.base_speed - reduccion_curva;

    int16_t left_pwm = constrain(static_cast<int16_t>(current_speed + pid_total),
                                 -_tuning.max_speed, _tuning.max_speed);
    int16_t right_pwm = constrain(static_cast<int16_t>(current_speed - pid_total),
                                  -_tuning.max_speed, _tuning.max_speed);

    return DriveCommand::diff(left_pwm, right_pwm);
}

} // namespace idline
