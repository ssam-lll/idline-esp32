#ifndef IDLINE_SENSOR_H
#define IDLINE_SENSOR_H

#include <Arduino.h>
#include <Preferences.h>
#include "config.h"
#include "types.h"
#include "mux.h"
#include "motor.h"
#include "pid.h"

namespace idline {

class BarraSensores {
private:
    Multiplexor&   _mux;
    SensorBarMode  _modo;

    uint16_t _calib_min[16];
    uint16_t _calib_max[16];
    bool     _calib_valida;

    int16_t    _last_position;
    LineStatus _last_status;

    RobotMode _current_mode;
    uint32_t  _test_start_ms;
    uint32_t  _last_calib_seq;
    uint32_t  _last_run_seq;
    uint32_t  _last_remote_seq;
    uint32_t  _last_tick_us;

    static const uint8_t kNumSensores8 = 8;
    const uint8_t _canales8[kNumSensores8] = {11, 10, 9, 8, 7, 6, 5, 4};

    uint16_t calcularCrc(const uint8_t* data, size_t len) const;

public:
    explicit BarraSensores(Multiplexor& mux, SensorBarMode modo = SensorBarMode::kCenter8_C4_C11);

    void begin();
    void leerBarra(int valores[8]);
    int verificarError(int valor);

    void resetCalibracion();
    void acumularCalibracion(const RawSensorFrame& frame);
    bool cargarCalibracion();
    void guardarCalibracion();

    SensorBarMode modo() const { return _modo; }
    void setModo(SensorBarMode m) { _modo = m; }
    bool esCalibracionValida() const { return _calib_valida; }

    ControlTelemetry procesarPaso(const RawSensorFrame& frame,
                                 const SupervisorCommand& cmd,
                                 ControladorPID& pid,
                                 Motor& motor,
                                 uint32_t t0_us,
                                 uint32_t tick);
};

typedef BarraSensores Sensor;

} // namespace idline

#endif // IDLINE_SENSOR_H
