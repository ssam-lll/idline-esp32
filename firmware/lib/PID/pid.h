#ifndef IDLINE_PID_H
#define IDLINE_PID_H

#include <Arduino.h>
#include "types.h"

namespace idline {

class ControladorPID {
private:
    PidTuning _tuning;
    float     _integral;
    float     _last_error;
    float     _d_filtered;

public:
    explicit ControladorPID(const PidTuning& tuning = default_pid_tuning());

    void reset();
    void actualizarParametros(const PidTuning& tuning);
    void setGains(float kp, float ki, float kd, int16_t base_speed);

    DriveCommand calcular(int16_t position, LineStatus line_status, float dt_sec, int16_t* out_pid = nullptr);

    const PidTuning& tuning() const { return _tuning; }
};

} // namespace idline

#endif // IDLINE_PID_H
