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

DriveCommand ControladorPID::calcular(int16_t position, LineStatus line_status, float dt_sec,
                                      int16_t* out_pid, uint32_t line_lost_ms) {
    if (dt_sec <= 0.0f || dt_sec > 0.05f) {
        dt_sec = 0.001f;
    }
    float dt_ms = constrain(dt_sec * 1000.0f, 0.5f, 50.0f);

    if (line_status == LineStatus::kLostLeft || line_status == LineStatus::kLostRight) {
        if (line_lost_ms >= 1200) {
            if (out_pid) *out_pid = 0;
            return DriveCommand::brake();
        }
        int16_t outer = constrain(static_cast<int16_t>(_tuning.base_speed * 0.75f), 320, 560);
        int16_t inner = -constrain(static_cast<int16_t>(_tuning.base_speed * 0.35f), 140, 260);
        if (line_status == LineStatus::kLostLeft) {
            if (out_pid) *out_pid = -_tuning.max_speed;
            return DriveCommand::diff(inner, outer);
        } else {
            if (out_pid) *out_pid = _tuning.max_speed;
            return DriveCommand::diff(outer, inner);
        }
    }

    float error = static_cast<float>(position);
    float p_term = _tuning.kp * error;

    float derivative = (error - _last_error) / dt_ms;
    _d_filtered = _tuning.lpf_alpha * derivative + (1.0f - _tuning.lpf_alpha) * _d_filtered;
    _last_error = error;
    float d_term = _tuning.kd * _d_filtered;

    // Anti-windup: only integrate when output is not saturated
    float pre_sum = p_term + _integral + d_term;
    if (fabsf(pre_sum) < static_cast<float>(_tuning.max_speed)) {
        _integral += _tuning.ki * error * dt_sec;
        _integral = constrain(_integral, -static_cast<float>(_tuning.max_integral),
                              static_cast<float>(_tuning.max_integral));
    }

    float pid_total = p_term + _integral + d_term;
    if (out_pid) {
        *out_pid = static_cast<int16_t>(pid_total);
    }

    // Progressive curve speed reduction: fast on straightaways, controlled on 45-deg octagonal turns
    int16_t abs_error = (position < 0) ? -position : position;
    int16_t reduccion_curva = static_cast<int16_t>((static_cast<int32_t>(abs_error) * _tuning.base_speed) / 2400);
    int16_t min_curve_speed = (_tuning.base_speed > 260) ? 260 : _tuning.base_speed;
    int16_t current_speed = _tuning.base_speed - reduccion_curva;
    if (current_speed < min_curve_speed) {
        current_speed = min_curve_speed;
    }

    int16_t left_pwm = constrain(static_cast<int16_t>(current_speed + pid_total),
                                 -_tuning.max_speed, _tuning.max_speed);
    int16_t right_pwm = constrain(static_cast<int16_t>(current_speed - pid_total),
                                  -_tuning.max_speed, _tuning.max_speed);

    return DriveCommand::diff(left_pwm, right_pwm);
}

} // namespace idline
