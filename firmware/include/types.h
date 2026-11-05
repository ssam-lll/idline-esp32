#ifndef IDLINE_TYPES_H
#define IDLINE_TYPES_H

#include <stdint.h>
#include <stddef.h>

namespace idline {

enum class SensorBarMode : uint8_t {
    kCenter8_C4_C11 = 0,
    kFull16_C0_C15  = 1
};

enum class RobotMode : uint8_t {
    kIdle = 0,
    kCalibrating,
    kReady,
    kRunning,
    kRemoteManual,
    kMotorTest,
    kFaultLowBatt
};

enum class LineStatus : uint8_t {
    kOnLine = 0,
    kLostLeft,
    kLostRight
};

struct RawSensorFrame {
    uint32_t timestamp_us;
    uint16_t adc_raw[16];
    uint16_t batt_raw;
    uint8_t  count;
};

struct DriveCommand {
    enum class Type : uint8_t {
        kCoastHighZ = 0,
        kShortBrake,
        kDifferential
    };

    Type    type;
    int16_t left_pwm;
    int16_t right_pwm;

    static DriveCommand coast() {
        DriveCommand cmd{};
        cmd.type = Type::kCoastHighZ;
        return cmd;
    }

    static DriveCommand brake() {
        DriveCommand cmd{};
        cmd.type = Type::kShortBrake;
        return cmd;
    }

    static DriveCommand diff(int16_t left, int16_t right) {
        DriveCommand cmd{};
        cmd.type = Type::kDifferential;
        cmd.left_pwm = left;
        cmd.right_pwm = right;
        return cmd;
    }
};

struct PidTuning {
    float   kp;
    float   ki;
    float   kd;
    float   lpf_alpha;
    int16_t base_speed;
    int16_t max_speed;
    int16_t max_integral;
};

inline PidTuning default_pid_tuning() {
    PidTuning t{};
    t.kp = 1.8f;
    t.ki = 0.002f;
    t.kd = 8.5f;
    t.lpf_alpha = 0.25f;
    t.base_speed = 450;
    t.max_speed = 950;
    t.max_integral = 300;
    return t;
}

struct SupervisorCommand {
    RobotMode target_mode;
    uint32_t  calib_seq;
    uint32_t  run_seq;
    uint32_t  remote_cmd_seq;
    int16_t   manual_m1;
    int16_t   manual_m2;
    bool      invert_line_polarity;
    float     pid_kp;
    float     pid_ki;
    float     pid_kd;
    int16_t   base_speed;
};

struct ControlTelemetry {
    uint32_t      tick;
    uint32_t      loop_time_us;
    RobotMode     current_mode;
    LineStatus    line_status;
    int16_t       position;
    uint16_t      normalized[16];
    uint16_t      raw_values[16];
    uint16_t      vbat_mv;
    int16_t       m1_pwm;
    int16_t       m2_pwm;
    int16_t       pid_out;
    uint8_t       sensor_error;
    uint32_t      ack_remote_cmd_seq;

    ControlTelemetry with_loop_time(uint32_t dt) const {
        ControlTelemetry copy = *this;
        copy.loop_time_us = dt;
        return copy;
    }
};

struct SupervisorState {
    SupervisorCommand command;
    uint32_t last_calib_button_ms;
    uint32_t last_start_button_ms;
    bool wifi_connected;
    bool mqtt_connected;
};

} // namespace idline

#endif // IDLINE_TYPES_H
