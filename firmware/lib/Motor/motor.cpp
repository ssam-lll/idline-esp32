#include "motor.h"

namespace idline {

Motor::Motor(uint8_t stby, uint8_t ain1, uint8_t ain2, uint8_t pwma,
             uint8_t bin1, uint8_t bin2, uint8_t pwmb)
    : _pinSTBY(stby), _pinAIN1(ain1), _pinAIN2(ain2), _pinPWMA(pwma),
      _pinBIN1(bin1), _pinBIN2(bin2), _pinPWMB(pwmb),
      _velM1(0), _velM2(0) {}

void Motor::begin() {
    pinMode(_pinSTBY, OUTPUT);
    pinMode(_pinAIN1, OUTPUT);
    pinMode(_pinAIN2, OUTPUT);
    pinMode(_pinPWMA, OUTPUT);
    pinMode(_pinBIN1, OUTPUT);
    pinMode(_pinBIN2, OUTPUT);
    pinMode(_pinPWMB, OUTPUT);

    ledcSetup(hw::kPwmChannelLeft, hw::kPwmFrequency, hw::kPwmResolutionBits);
    ledcAttachPin(_pinPWMA, hw::kPwmChannelLeft);

    ledcSetup(hw::kPwmChannelRight, hw::kPwmFrequency, hw::kPwmResolutionBits);
    ledcAttachPin(_pinPWMB, hw::kPwmChannelRight);

    desactivar();
}

void Motor::escribirHardware(int16_t pwm_m1, int16_t pwm_m2) {
    digitalWrite(_pinSTBY, HIGH);

    if (pwm_m1 > 0) {
        digitalWrite(_pinAIN1, HIGH);
        digitalWrite(_pinAIN2, LOW);
        ledcWrite(hw::kPwmChannelLeft, pwm_m1);
    } else if (pwm_m1 < 0) {
        digitalWrite(_pinAIN1, LOW);
        digitalWrite(_pinAIN2, HIGH);
        ledcWrite(hw::kPwmChannelLeft, -pwm_m1);
    } else {
        digitalWrite(_pinAIN1, HIGH);
        digitalWrite(_pinAIN2, HIGH);
        ledcWrite(hw::kPwmChannelLeft, hw::kPwmMaxDuty);
    }

    if (pwm_m2 > 0) {
        digitalWrite(_pinBIN1, HIGH);
        digitalWrite(_pinBIN2, LOW);
        ledcWrite(hw::kPwmChannelRight, pwm_m2);
    } else if (pwm_m2 < 0) {
        digitalWrite(_pinBIN1, LOW);
        digitalWrite(_pinBIN2, HIGH);
        ledcWrite(hw::kPwmChannelRight, -pwm_m2);
    } else {
        digitalWrite(_pinBIN1, HIGH);
        digitalWrite(_pinBIN2, HIGH);
        ledcWrite(hw::kPwmChannelRight, hw::kPwmMaxDuty);
    }
}

void Motor::aplicar(const DriveCommand& cmd) {
    if (cmd.type == DriveCommand::Type::kCoastHighZ) {
        desactivar();
    } else if (cmd.type == DriveCommand::Type::kShortBrake) {
        frenar();
    } else {
        int16_t left = constrain(cmd.left_pwm, -static_cast<int16_t>(hw::kPwmMaxDuty), static_cast<int16_t>(hw::kPwmMaxDuty));
        int16_t right = constrain(cmd.right_pwm, -static_cast<int16_t>(hw::kPwmMaxDuty), static_cast<int16_t>(hw::kPwmMaxDuty));

        _velM1 = (left * 255) / static_cast<int>(hw::kPwmMaxDuty);
        _velM2 = (right * 255) / static_cast<int>(hw::kPwmMaxDuty);

        escribirHardware(left, right);
    }
}

void Motor::setMotorIzquierdo(int velocidad_255) {
    int v = constrain(velocidad_255, -255, 255);
    _velM1 = v;
    int16_t pwm = static_cast<int16_t>((v * static_cast<int>(hw::kPwmMaxDuty)) / 255);
    int16_t pwm_right = static_cast<int16_t>((_velM2 * static_cast<int>(hw::kPwmMaxDuty)) / 255);
    escribirHardware(pwm, pwm_right);
}

void Motor::setMotorDerecho(int velocidad_255) {
    int v = constrain(velocidad_255, -255, 255);
    _velM2 = v;
    int16_t pwm_left = static_cast<int16_t>((_velM1 * static_cast<int>(hw::kPwmMaxDuty)) / 255);
    int16_t pwm = static_cast<int16_t>((v * static_cast<int>(hw::kPwmMaxDuty)) / 255);
    escribirHardware(pwm_left, pwm);
}

void Motor::setMotores(int velM1_255, int velM2_255) {
    _velM1 = constrain(velM1_255, -255, 255);
    _velM2 = constrain(velM2_255, -255, 255);
    int16_t p1 = static_cast<int16_t>((_velM1 * static_cast<int>(hw::kPwmMaxDuty)) / 255);
    int16_t p2 = static_cast<int16_t>((_velM2 * static_cast<int>(hw::kPwmMaxDuty)) / 255);
    escribirHardware(p1, p2);
}

void Motor::frenar() {
    _velM1 = 0;
    _velM2 = 0;
    digitalWrite(_pinSTBY, HIGH);
    digitalWrite(_pinAIN1, HIGH);
    digitalWrite(_pinAIN2, HIGH);
    ledcWrite(hw::kPwmChannelLeft, hw::kPwmMaxDuty);
    digitalWrite(_pinBIN1, HIGH);
    digitalWrite(_pinBIN2, HIGH);
    ledcWrite(hw::kPwmChannelRight, hw::kPwmMaxDuty);
}

void Motor::desactivar() {
    _velM1 = 0;
    _velM2 = 0;
    digitalWrite(_pinSTBY, LOW);
    digitalWrite(_pinAIN1, LOW);
    digitalWrite(_pinAIN2, LOW);
    ledcWrite(hw::kPwmChannelLeft, 0);
    digitalWrite(_pinBIN1, LOW);
    digitalWrite(_pinBIN2, LOW);
    ledcWrite(hw::kPwmChannelRight, 0);
}

DriveCommand Motor::evaluarPruebaNoBloqueante(uint32_t elapsed_ms) {
    constexpr int16_t kTestPwm = 722; // 180 / 255 * 1023

    if (elapsed_ms < 400) {
        return DriveCommand::diff(kTestPwm, 0);
    } else if (elapsed_ms < 550) {
        return DriveCommand::brake();
    } else if (elapsed_ms < 950) {
        return DriveCommand::diff(-kTestPwm, 0);
    } else if (elapsed_ms < 1100) {
        return DriveCommand::brake();
    } else if (elapsed_ms < 1500) {
        return DriveCommand::diff(0, kTestPwm);
    } else if (elapsed_ms < 1650) {
        return DriveCommand::brake();
    } else if (elapsed_ms < 2050) {
        return DriveCommand::diff(0, -kTestPwm);
    } else if (elapsed_ms < 2200) {
        return DriveCommand::brake();
    }
    return DriveCommand::coast();
}

} // namespace idline
