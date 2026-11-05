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

    if (line_status == LineStatus::kLostLeft) {
        if (out_pid) *out_pid = -_tuning.max_speed;
        int16_t left = -(_tuning.base_speed / 2);
        int16_t right = _tuning.base_speed;
        return DriveCommand::diff(left, right);
    }

    if (line_status == LineStatus::kLostRight) {
        if (out_pid) *out_pid = _tuning.max_speed;
        int16_t left = _tuning.base_speed;
        int16_t right = -(_tuning.base_speed / 2);
        return DriveCommand::diff(left, right);
    }

    float error = static_cast<float>(position);
    float p_term = _tuning.kp * error;

    _integral += _tuning.ki * error * dt_sec;
    _integral = constrain(_integral, -static_cast<float>(_tuning.max_integral), static_cast<float>(_tuning.max_integral));

    float derivative = (error - _last_error) / dt_sec;
    _d_filtered = _tuning.lpf_alpha * derivative + (1.0f - _tuning.lpf_alpha) * _d_filtered;
    _last_error = error;
    float d_term = _tuning.kd * _d_filtered;

    float pid_total = p_term + _integral + d_term;
    if (out_pid) {
        *out_pid = static_cast<int16_t>(pid_total);
    }

    int16_t left_pwm = constrain(static_cast<int16_t>(_tuning.base_speed + pid_total),
                                 -_tuning.max_speed, _tuning.max_speed);
    int16_t right_pwm = constrain(static_cast<int16_t>(_tuning.base_speed - pid_total),
                                  -_tuning.max_speed, _tuning.max_speed);

    return DriveCommand::diff(left_pwm, right_pwm);
}

} // namespace idline
