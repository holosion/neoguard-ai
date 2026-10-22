// ESP32-S3 + MAX30102 breakout only. Raw hardware test, no medical readings.
#include <Wire.h>
#include <MAX30105.h>

constexpr int SDA_PIN = 4, SCL_PIN = 5;
MAX30105 pulse;
bool ready = false;
uint32_t lastReport = 0, lastRetry = 0, lastSample = 0;
uint32_t red = 0, ir = 0, samples = 0;

void detectSensor() {
  Serial.println("Scanning I2C on GPIO4 SDA / GPIO5 SCL...");
  unsigned found = 0;
  for (uint8_t address = 1; address < 127; ++address) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) {
      Serial.printf("I2C found 0x%02X\n", address);
      ++found;
    }
  }
  if (!found) Serial.println("No I2C devices: check module power, shared GND and signal wires.");
  Serial.println("Starting MAX30102 (expected address 0x57)...");
  ready = pulse.begin(Wire, I2C_SPEED_STANDARD);
  Wire.setTimeOut(50);
  if (!ready) {
    Serial.println("MAX NOT READY: missing sensor or incompatible part ID. Retry in 5 seconds.");
    return;
  }
  Serial.println("MAX detected. Configuring red + infrared LEDs...");
  pulse.setup(60, 4, 2, 100, 411, 4096);
  pulse.setPulseAmplitudeRed(60);
  pulse.setPulseAmplitudeIR(60);
  pulse.setPulseAmplitudeGreen(0);
  pulse.wakeUp();
  pulse.clearFIFO();
  samples = 0;
  Serial.println("MAX configured. Look for a red glow; infrared is invisible.");
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("\nOXIMETER POWER TEST -- ESP32-S3 running");
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000);
  Wire.setTimeOut(50);
  detectSensor();
  lastRetry = millis();
}

void loop() {
  if (!ready && millis() - lastRetry >= 5000) {
    detectSensor();
    lastRetry = millis();
  }
  if (ready) {
    pulse.check();
    while (pulse.available()) {
      red = pulse.getFIFORed();
      ir = pulse.getFIFOIR();
      pulse.nextSample();
      ++samples;
      lastSample = millis();
    }
  }
  if (millis() - lastReport >= 1000) {
    lastReport = millis();
    Serial.printf("Uptime=%lus MAX=%s RED=%lu IR=%lu samples=%lu %s\n",
      (unsigned long)(millis() / 1000), ready ? "detected" : "missing",
      (unsigned long)red, (unsigned long)ir, (unsigned long)samples,
      !ready ? "Check power/wiring" :
      (!samples || millis() - lastSample > 2000) ? "NO FRESH SAMPLES" : "Sampling");
  }
}
