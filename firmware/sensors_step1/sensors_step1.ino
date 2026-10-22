// Step 1: ESP32-S3 + MAX30102 + MLX90614, Serial Monitor only.
// Experimental bench readings, not clinically validated.
#include <Wire.h>
#include <Adafruit_MLX90614.h>
#include <MAX30105.h>
#include "spo2_algorithm.h"
#include <math.h>

constexpr int SDA_PIN = 4, SCL_PIN = 5;
constexpr uint32_t CONTACT_IR = 50000; // Adjust only after inspecting raw IR.
Adafruit_MLX90614 temperature;
MAX30105 oximeter; // Library class name also used for MAX30102.
bool temperatureFound = false, oximeterFound = false, contact = false;
uint32_t ir[100], red[100], rawIR = 0, rawRed = 0;
int count = 0, newSamples = 0;
int32_t oxygen = 0, heartRate = 0;
int8_t oxygenValid = 0, heartRateValid = 0;
uint32_t lastService = 0, lastSample = 0, lastReport = 0;

void resetWindow() {
  count = 0; newSamples = 0;
  oxygenValid = 0; heartRateValid = 0;
}

void collectPulse() {
  if (!oximeterFound) return;
  uint32_t now = millis();
  // At 25 samples/sec the library's small software buffer needs frequent service.
  if (now - lastService >= 120) {
    oximeter.clearFIFO(); resetWindow(); contact = false;
  }
  lastService = now;
  oximeter.check();
  while (oximeter.available()) {
    rawIR = oximeter.getFIFOIR();
    rawRed = oximeter.getFIFORed();
    oximeter.nextSample(); lastSample = millis();
    contact = rawIR >= CONTACT_IR;
    if (!contact) { resetWindow(); continue; }
    if (count < 100) {
      ir[count] = rawIR; red[count++] = rawRed;
      if (count == 100) newSamples = 25;
    } else {
      for (int i = 1; i < 100; ++i) { ir[i - 1] = ir[i]; red[i - 1] = red[i]; }
      ir[99] = rawIR; red[99] = rawRed; ++newSamples;
    }
    if (count == 100 && newSamples >= 25) {
      maxim_heart_rate_and_oxygen_saturation(ir, 100, red,
        &oxygen, &oxygenValid, &heartRate, &heartRateValid);
      oxygenValid = oxygenValid && oxygen >= 0 && oxygen <= 100;
      heartRateValid = heartRateValid && heartRate > 0 && heartRate <= 250;
      newSamples = 0;
    }
  }
  if (millis() - lastSample > 2000) { contact = false; resetWindow(); }
}

void setup() {
  Serial.begin(115200);
  delay(1500); // Give the native USB serial connection time to start.
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000); Wire.setTimeOut(50);
  Serial.println("\nSTEP 1: MAX30102 + MLX90614 bench test");
  Serial.println("I2C scan: expect 0x57 and 0x5A");
  for (uint8_t address = 1; address < 127; ++address) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) Serial.printf("Found 0x%02X\n", address);
  }
  temperatureFound = temperature.begin(0x5A, &Wire);
  oximeterFound = oximeter.begin(Wire, I2C_SPEED_STANDARD);
  if (oximeterFound) {
    // Red + IR, 100 Hz acquisition averaged by 4 = 25 Hz for the algorithm.
    oximeter.setup(60, 4, 2, 100, 411, 4096);
    oximeter.clearFIFO();
  }
  Wire.setClock(100000);
  lastService = millis();
  Serial.printf("MLX90614: %s\n", temperatureFound ? "detected" : "NOT DETECTED");
  Serial.printf("MAX30102: %s\n", oximeterFound ? "detected" : "NOT DETECTED");
  Serial.println("Hold an adult finger gently on MAX30102 for a bench test.");
}

void loop() {
  collectPulse();
  if (millis() - lastReport < 1000) return;
  lastReport = millis();
  float objectC = temperatureFound ? temperature.readObjectTempC() : NAN;
  collectPulse();
  float ambientC = temperatureFound ? temperature.readAmbientTempC() : NAN;
  collectPulse();
  bool tempValid = isfinite(objectC) && isfinite(ambientC) &&
    objectC >= -70 && objectC <= 380 && ambientC >= -40 && ambientC <= 125;
  Serial.print("ObjectC=");
  if (tempValid) Serial.print(objectC, 2); else Serial.print("unavailable");
  Serial.print(" AmbientC=");
  if (tempValid) Serial.print(ambientC, 2); else Serial.print("unavailable");
  Serial.print(" HR=");
  if (heartRateValid) Serial.print(heartRate); else Serial.print("--");
  Serial.print(" SpO2=");
  if (oxygenValid) { Serial.print(oxygen); Serial.print('%'); } else Serial.print("--");
  Serial.printf(" IR=%lu RED=%lu Samples=%d Status=%s\n", (unsigned long)rawIR,
    (unsigned long)rawRed, count, !oximeterFound ? "MAX missing" :
    millis() - lastSample > 2000 ? "No fresh MAX samples" :
    !contact ? "Place finger" : (!heartRateValid || !oxygenValid) ? "Hold still" : "Estimates available");
}
