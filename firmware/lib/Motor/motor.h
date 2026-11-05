#ifndef IDLINE_MOTOR_H
#define IDLINE_MOTOR_H

#include <Arduino.h>
#include "config.h"
#include "types.h"

namespace idline {

class Motor {
private:
    uint8_t _pinSTBY;
    uint8_t _pinAIN1;
    uint8_t _pinAIN2;
    uint8_t _pinPWMA;
    uint8_t _pinBIN1;
    uint8_t _pinBIN2;
    uint8_t _pinPWMB;

    int _velM1; // -255..255 representation
    int _velM2; // -255..255 representation

    void escribirHardware(int16_t pwm_m1, int16_t pwm_m2);

public:
    Motor(uint8_t stby = hw::kPinStby,
          uint8_t ain1 = hw::kPinAin1,
          uint8_t ain2 = hw::kPinAin2,
          uint8_t pwma = hw::kPinPwma,
          uint8_t bin1 = hw::kPinBin1,
          uint8_t bin2 = hw::kPinBin2,
          uint8_t pwmb = hw::kPinPwmb);

    void begin();
    void aplicar(const DriveCommand& cmd);
    void setMotorIzquierdo(int velocidad_255);
    void setMotorDerecho(int velocidad_255);
    void setMotores(int velM1_255, int velM2_255);
    void frenar();
    void desactivar();

    DriveCommand evaluarPruebaNoBloqueante(uint32_t elapsed_ms);

    int getVelocidadM1() const { return _velM1; }
    int getVelocidadM2() const { return _velM2; }
};

} // namespace idline

#endif // IDLINE_MOTOR_H
