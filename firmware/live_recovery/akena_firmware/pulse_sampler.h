#pragma once
#include <freertos/semphr.h>
struct PulseSnapshot {
  uint32_t ir = 0, red = 0, sampled = 0, generation = 0, estimated = 0;
  uint32_t total = 0, resets = 0;
  int32_t hr = 0, oxygen = 0;
  int8_t hrValid = 0, oxygenValid = 0;
  bool contact = false;
};
SemaphoreHandle_t sensorBusMutex = nullptr;
QueueHandle_t pulseSnapshots = nullptr;
TaskHandle_t pulseSamplerTask = nullptr;

void pulseSampler(void *) {
  uint32_t ir[100]{}, red[100]{};
  unsigned count = 0, added = 0, touching = 0, removed = 0;
  uint32_t serviced = millis();
  PulseSnapshot state;
  auto reset = [&]() { count = added = 0; state.hrValid = state.oxygenValid = 0; state.estimated = 0; };
  for (;;) {
    if (samplingPaused) {vTaskDelay(pdMS_TO_TICKS(10)); continue;}
    if (xSemaphoreTake(sensorBusMutex, pdMS_TO_TICKS(5)) == pdTRUE) {
      uint32_t now = millis();
      if (now - serviced >= 120) {
        pulse.clearFIFO(); reset(); touching = removed = 0;
        state.contact = false; ++state.generation; ++state.resets;
      }
      serviced = now;
      pulse.check();
      while (pulse.available()) {
        state.ir = pulse.getFIFOIR(); state.red = pulse.getFIFORed();
        pulse.nextSample(); state.sampled = millis(); ++state.total;
        bool saturated = state.ir >= 262000 || state.red >= 262000;
        if (!state.contact) {
          touching = state.ir >= FINGER_THRESHOLD && !saturated ? touching + 1 : 0;
          if (touching >= 8) { state.contact = true; removed = 0; }
        } else {
          removed = state.ir < FINGER_OFF_THRESHOLD || saturated ? removed + 1 : 0;
          if (removed >= 4) { state.contact = false; touching = 0; ++state.generation; }
        }
        if (!state.contact || saturated || state.ir < FINGER_OFF_THRESHOLD) { reset(); continue; }
        if (count < 100) {
          ir[count] = state.ir; red[count++] = state.red;
          if (count == 100) added = 25;
        } else {
          for (unsigned i = 1; i < 100; ++i) { ir[i-1] = ir[i]; red[i-1] = red[i]; }
          ir[99] = state.ir; red[99] = state.red; ++added;
        }
        if (count == 100 && added >= 25) {
          maxim_heart_rate_and_oxygen_saturation(ir, 100, red, &state.oxygen, &state.oxygenValid, &state.hr, &state.hrValid);
          state.hrValid = state.hrValid && state.hr > 0 && state.hr <= 250;
          state.oxygenValid = state.oxygenValid && state.oxygen > 0 && state.oxygen <= 100;
          state.estimated = millis();
          added = 0;
        }
      }
      xSemaphoreGive(sensorBusMutex);
      if (millis() - state.sampled > 2000) {
        if (state.contact) ++state.generation;
        state.contact = false; touching = removed = 0; reset();
      }
      xQueueOverwrite(pulseSnapshots, &state);
    }
    vTaskDelay(pdMS_TO_TICKS(5));
  }
}

void collectPulse() {
  if (!pulseSnapshots) return;
  PulseSnapshot state;
  static uint32_t generation = 0;
  if (xQueueReceive(pulseSnapshots, &state, 0) != pdTRUE) return;
  if (generation != state.generation) { measurement.reset(); thresholdAlarm.reset(); heartAverage.reset(); generation = state.generation; }
  lastIR = state.ir; lastRed = state.red; lastSample = state.sampled;
  heartRate = state.hr; spo2 = state.oxygen; hrValid = state.hrValid; spo2Valid = state.oxygenValid;
  finger = state.contact;
  heartAverage.observe(millis(), finger, hrValid, heartRate, state.estimated);
  pulseSampleTotal = state.total; pulseResetCount = state.resets;
}

void beginPulseSampling() {
  sensorBusMutex = xSemaphoreCreateMutex(); pulseSnapshots = xQueueCreate(1, sizeof(PulseSnapshot));
  if (!pulseOK || !sensorBusMutex || !pulseSnapshots ||
      xTaskCreatePinnedToCore(pulseSampler, "pulse-acquisition", 8192, nullptr, 3, &pulseSamplerTask, 1) != pdPASS) {
    pulseOK = false; Serial.println("MAX: sampler unavailable; check detection and free memory.");
  }
}

float readSurfaceTemperature(bool ambient) {
  if (!tempOK || !sensorBusMutex || xSemaphoreTake(sensorBusMutex, pdMS_TO_TICKS(60)) != pdTRUE) return NAN;
  uint8_t reg=ambient ? 0x06 : 0x07;
  float value=NAN;
  Wire.beginTransmission(0x5A); Wire.write(reg);
  bool ok=Wire.endTransmission(false)==0;
  if (ok && Wire.requestFrom(uint8_t(0x5A),uint8_t(3),uint8_t(true))==3) {
    uint8_t packet[3]; for (auto &byte : packet) byte=(uint8_t)Wire.read();
    ok=decodeMlxTemperature(0x5A,reg,packet,value);
  } else ok=false;
  if (!ok) {++temperaturePacketErrors; value=NAN;}
  xSemaphoreGive(sensorBusMutex); return value;
}
