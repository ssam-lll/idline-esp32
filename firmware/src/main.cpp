#include <Arduino.h>
#include "config.h"
#include "types.h"
#include "ipc.h"
#include "mux.h"
#include "sensor.h"
#include "motor.h"
#include "pid.h"
#include "pantalla.h"
#include "telemetria.h"

using namespace idline;

static Seqlock<SupervisorCommand> g_supervisor_bus;
static Seqlock<ControlTelemetry>  g_telemetry_bus;

void control_task_core1(void* pvParameters) {
    Multiplexor    mux;
    BarraSensores  barra(mux, SensorBarMode::kCenter8_C4_C11);
    Motor          motor;
    ControladorPID pid(default_pid_tuning());

    mux.begin();
    barra.begin();
    motor.begin();

    TickType_t last_wake = xTaskGetTickCount();
    uint32_t tick = 0;

    for (;;) {
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(1));
        const uint32_t t0_us = micros();

        const SupervisorCommand cmd = g_supervisor_bus.read();
        const RawSensorFrame    raw = mux.escanearFrame(tick, barra.modo());
        const ControlTelemetry  tel = barra.procesarPaso(raw, cmd, pid, motor, t0_us, tick);

        g_telemetry_bus.publish(tel.with_loop_time(micros() - t0_us));
        ++tick;
    }
}

void supervisor_task_core0(void* pvParameters) {
    PantallaTFT pantalla;
    Telemetria  telemetria;

    telemetria.begin();
    vTaskDelay(pdMS_TO_TICKS(200));
    pantalla.begin();

    SupervisorState sup_state{};
    sup_state.command.target_mode = RobotMode::kIdle;
    sup_state.command.base_speed = 450;
    sup_state.command.pid_kp = 1.8f;
    sup_state.command.pid_ki = 0.002f;
    sup_state.command.pid_kd = 8.5f;

    TickType_t last_wake = xTaskGetTickCount();

    for (;;) {
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(33));
        const uint32_t now_ms = millis();

        const ControlTelemetry tel = g_telemetry_bus.read();
        telemetria.tick(now_ms, tel, &sup_state);
        pantalla.renderizarDiferencial(now_ms, sup_state, tel);

        g_supervisor_bus.publish(sup_state.command);
    }
}

void setup() {
    Serial.begin(115200);
    xTaskCreatePinnedToCore(control_task_core1, "ControlCore1", 8192, nullptr, 5, nullptr, 1);
    xTaskCreatePinnedToCore(supervisor_task_core0, "SupervCore0", 8192, nullptr, 2, nullptr, 0);
}

void loop() {
    vTaskDelay(pdMS_TO_TICKS(1000));
}
