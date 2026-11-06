#include <Arduino.h>
#include <Preferences.h>
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
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

struct RunSample {
    uint16_t t_ms;
    int16_t  pos;
    int16_t  m1;
    int16_t  m2;
    uint8_t  status;
};

constexpr size_t kMaxSamples = 4000;
static RunSample g_run_buffer[kMaxSamples];
static size_t g_sample_count = 0;
static bool g_recording = false;
static uint8_t g_recorded_profile = 0;

static bool g_wifi_enabled = false;
static uint8_t g_boot_profile = 0;

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

        if (tel.current_mode == RobotMode::kRunning) {
            if (tick % 20 == 0) {
                if (!g_recording) {
                    g_recording = true;
                    g_sample_count = 0;
                    g_recorded_profile = cmd.profile_idx;
                }
                if (g_sample_count < kMaxSamples) {
                    g_run_buffer[g_sample_count++] = {
                        static_cast<uint16_t>(g_sample_count * 20),
                        tel.position,
                        tel.m1_pwm,
                        tel.m2_pwm,
                        static_cast<uint8_t>(tel.line_status)
                    };
                }
            }
        } else {
            if (g_recording) {
                g_recording = false;
            }
        }

        g_telemetry_bus.publish(tel.with_loop_time(micros() - t0_us));
        ++tick;
    }
}

static PantallaTFT g_pantalla;
static Telemetria  g_telemetria;

void supervisor_task_core0(void* pvParameters) {
    g_pantalla.begin();
    vTaskDelay(pdMS_TO_TICKS(100));
    g_telemetria.begin(g_wifi_enabled);

    SupervisorState sup_state{};
    sup_state.command.target_mode = RobotMode::kIdle;
    sup_state.active_profile = g_boot_profile;
    sup_state.command.profile_idx = g_boot_profile;
    sup_state.command.base_speed = kProfiles[g_boot_profile].speed;
    sup_state.command.pid_kp = kProfiles[g_boot_profile].kp;
    sup_state.command.pid_kd = kProfiles[g_boot_profile].kd;
    sup_state.command.pid_ki = 0.0f;
    sup_state.wifi_enabled = g_wifi_enabled;

    TickType_t last_wake = xTaskGetTickCount();

    for (;;) {
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(33));
        const uint32_t now_ms = millis();

        if (Serial.available()) {
            String line = Serial.readStringUntil('\n');
            line.trim();
            if (line == "dump" || line == "runs") {
                uint8_t pidx = g_recorded_profile % 3;
                Serial.printf("#run,1,profile,%s,speed,%d,kp,%.2f,kd,%.2f,samples,%u\n",
                              kProfiles[pidx].name,
                              kProfiles[pidx].speed,
                              kProfiles[pidx].kp,
                              kProfiles[pidx].kd,
                              (unsigned)g_sample_count);
                Serial.println("t_ms,pos,m1,m2,status");
                for (size_t i = 0; i < g_sample_count; ++i) {
                    Serial.printf("%u,%d,%d,%d,%u\n",
                                  g_run_buffer[i].t_ms,
                                  g_run_buffer[i].pos,
                                  g_run_buffer[i].m1,
                                  g_run_buffer[i].m2,
                                  g_run_buffer[i].status);
                }
                Serial.println("#end");
            } else if (line == "status") {
                Serial.printf("MODO:%d VBAT:%u SPEED:%d KP:%.2f KD:%.2f WIFI:%d SAMPLES:%u\n",
                              (int)sup_state.command.target_mode,
                              (unsigned)g_telemetry_bus.read().vbat_mv,
                              sup_state.command.base_speed,
                              sup_state.command.pid_kp,
                              sup_state.command.pid_kd,
                              g_wifi_enabled ? 1 : 0,
                              (unsigned)g_sample_count);
            }
        }

        const ControlTelemetry tel = g_telemetry_bus.read();
        g_telemetria.tick(now_ms, tel, &sup_state);
        g_pantalla.renderizarDiferencial(now_ms, sup_state, tel);

        g_supervisor_bus.publish(sup_state.command);
    }
}

void setup() {
    Serial.begin(115200);
    WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0); // Desactivar detector de brownout por caida transitoria de motores

    pinMode(hw::kPinBtnStart, INPUT_PULLUP);
    delay(50);
    g_wifi_enabled = (digitalRead(hw::kPinBtnStart) == LOW);

    Preferences prefs;
    if (prefs.begin("idline", true)) {
        g_boot_profile = prefs.getUChar("prof", 0) % 3;
        prefs.end();
    } else {
        g_boot_profile = 0;
    }

    xTaskCreatePinnedToCore(control_task_core1, "ControlCore1", 8192, nullptr, 5, nullptr, 1);
    xTaskCreatePinnedToCore(supervisor_task_core0, "SupervCore0", 8192, nullptr, 2, nullptr, 0);
}

void loop() {
    vTaskDelay(pdMS_TO_TICKS(1000));
}
