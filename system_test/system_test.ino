// Bench integration test; estimates are not clinically validated.
// DS1302: VCC=3.3V, GND=GND, CLK=GPIO6, DAT=GPIO7, RST=GPIO14.
#include <Wire.h>
#include <LiquidCrystal.h>
#include <Adafruit_MLX90614.h>
#include <ThreeWire.h>
#include <RtcDS1302.h>
#include <MAX30105.h>
#include "spo2_algorithm.h"
#include <math.h>

LiquidCrystal lcd(8, 9, 10, 11, 12, 13);
Adafruit_MLX90614 mlx;
constexpr uint8_t RTC_CLK = 6, RTC_DAT = 7, RTC_RST = 14;
ThreeWire rtcWire(RTC_DAT, RTC_CLK, RTC_RST); // IO, SCLK, CE order.
RtcDS1302<ThreeWire> rtc(rtcWire);
MAX30105 pulse;
constexpr int BUZZER = 15, RED = 16, GREEN = 17, BLUE = 18;
// Active two-pin buzzer through a transistor. Set false for passive piezo.
constexpr bool ACTIVE_BUZZER = true;
// Enable once to set RTC from computer compilation time, then disable/reupload.
constexpr bool SET_RTC_TIME = false;
constexpr uint32_t FINGER_THRESHOLD = 50000; // Tune to your module/raw IR values.
bool tempOK = false, pulseOK = false, finger = false;
float objectC = NAN, ambientC = NAN;
uint32_t ir[100], red[100], lastIR = 0, lastRed = 0;
int sampleCount = 0, newSamples = 0;
int32_t spo2 = 0, heartRate = 0;
int8_t spo2Valid = 0, hrValid = 0;
uint32_t lastSample = 0, lastReport = 0, beepStart = 0;
bool beeping = false;

void rgb(bool r, bool g, bool b) {
  digitalWrite(RED, r); digitalWrite(GREEN, g); digitalWrite(BLUE, b);
}
void buzzer(bool on) {
  if (ACTIVE_BUZZER) digitalWrite(BUZZER, on);
  else if (on) tone(BUZZER, 2000);
  else noTone(BUZZER);
}
void line(int row, const char *s) {
  lcd.setCursor(0, row);
  for (int i = 0; i < 16; i++) {
    if (*s) lcd.write(*s++); else lcd.write(' ');
  }
}
void resetPulse() {
  sampleCount = 0; newSamples = 0; hrValid = 0; spo2Valid = 0;
}
void collectPulse() {
  if (!pulseOK) return;
  pulse.check();
  while (pulse.available()) {
    lastIR = pulse.getFIFOIR(); lastRed = pulse.getFIFORed();
    pulse.nextSample(); lastSample = millis();
    finger = lastIR >= FINGER_THRESHOLD;
    if (!finger) { resetPulse(); continue; }
    if (sampleCount == 100) {
      for (int i = 1; i < 100; i++) { ir[i-1] = ir[i]; red[i-1] = red[i]; }
      ir[99] = lastIR; red[99] = lastRed;
      newSamples++;
    } else {
      ir[sampleCount] = lastIR; red[sampleCount] = lastRed;
      sampleCount++;
      if (sampleCount == 100) newSamples = 25;
    }
    if (sampleCount == 100 && newSamples >= 25) {
      maxim_heart_rate_and_oxygen_saturation(ir, 100, red,
        &spo2, &spo2Valid, &heartRate, &hrValid);
      hrValid = hrValid && heartRate > 0 && heartRate <= 250;
      spo2Valid = spo2Valid && spo2 >= 0 && spo2 <= 100;
      newSamples = 0;
    }
  }
  if (millis() - lastSample > 2000) { finger = false; resetPulse(); }
}
void setup() {
  Serial.begin(115200);
  pinMode(BUZZER, OUTPUT); pinMode(RED, OUTPUT);
  pinMode(GREEN, OUTPUT); pinMode(BLUE, OUTPUT);
  buzzer(false); rgb(false, false, true);
  delay(100); lcd.begin(16, 2);
  line(0, "NeoGuard test"); line(1, "Starting...");
  Wire.begin(4, 5); Wire.setClock(100000); Wire.setTimeOut(50);
  Serial.println("\nNeoGuard bench test. Experimental readings.");
  Serial.println("I2C scan (expected: MAX=0x57, MLX=0x5A; DS1302 uses separate pins):");
  for (uint8_t address = 1; address < 127; address++) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) Serial.printf("Found 0x%02X\n", address);
  }
  tempOK = mlx.begin(0x5A, &Wire);
  rtc.Begin();
  rtc.SetIsWriteProtected(false);
  // The pictured CR2032 is non-rechargeable.
  rtc.SetTrickleChargeSettings(DS1302Tcr_Disabled);
  if (SET_RTC_TIME) {
    rtc.SetDateTime(RtcDateTime(__DATE__, __TIME__));
    rtc.SetIsRunning(true);
  }
  pulseOK = pulse.begin(Wire, I2C_SPEED_STANDARD);
  if (pulseOK) {
    // 100Hz sampling averaged by 4 yields 25Hz for the reference algorithm.
    pulse.setup(60, 4, 2, 100, 411, 4096);
    pulse.clearFIFO();
  }
  Wire.setClock(100000);
  Serial.printf("MLX90614: %s; DS1302: %s; MAX: %s\n",
    tempOK ? "detected" : "missing", rtc.IsDateTimeValid() && rtc.GetIsRunning() ? "time valid/running" : "check wiring/set time",
    pulseOK ? "detected" : "missing/unsupported");
  Serial.println("MAX30100 is NOT supported by this MAX30101/02/05 driver.");
  Serial.println("RGB: red=fault, blue=waiting, green=valid estimates (not health status).");
  buzzer(true); beeping = true; beepStart = millis(); // Hardware test only.
}
void loop() {
  if (beeping && millis() - beepStart >= 150) { buzzer(false); beeping = false; }
  collectPulse();
  if (millis() - lastReport < 1000) return;
  lastReport = millis();
  objectC = tempOK ? mlx.readObjectTempC() : NAN;
  ambientC = tempOK ? mlx.readAmbientTempC() : NAN;
  bool goodTemp = isfinite(objectC) && isfinite(ambientC);
  // DS1302 has no I2C acknowledgement; validate each reading instead.
  RtcDateTime now = rtc.GetDateTime();
  bool clockRunning = rtc.IsDateTimeValid() && now.IsValid() && rtc.GetIsRunning();
  char timeText[12] = "RTC unset";
  if (clockRunning) {

    snprintf(timeText, sizeof(timeText), "%02u:%02u:%02u", now.Hour(), now.Minute(), now.Second());
    Serial.printf("Date=%04u-%02u-%02u ", now.Year(), now.Month(), now.Day());
  }
  Serial.printf("Time=%s ObjectC=", clockRunning ? timeText : "RTC unset/check");
  if (goodTemp) Serial.print(objectC, 2); else Serial.print("unavailable");
  Serial.print(" AmbientC=");
  if (goodTemp) Serial.print(ambientC, 2); else Serial.print("unavailable");
  Serial.print(" HR="); if (hrValid) Serial.print(heartRate); else Serial.print("invalid");
  Serial.print(" SpO2="); if (spo2Valid) Serial.print(spo2); else Serial.print("invalid");
  Serial.printf(" IR=%lu RED=%lu Contact=%s\n", (unsigned long)lastIR,
    (unsigned long)lastRed, finger ? "detected" : "absent/stale");
  bool fault = !goodTemp || !clockRunning || !pulseOK || millis() - lastSample > 2000;
  rgb(fault, !fault && hrValid && spo2Valid, !fault && (!hrValid || !spo2Valid));
  char text[40], hrText[8] = "--", oxygenText[8] = "--";
  if (hrValid) snprintf(hrText, sizeof(hrText), "%ld", (long)heartRate);
  if (spo2Valid) snprintf(oxygenText, sizeof(oxygenText), "%ld", (long)spo2);
  if ((millis() / 4000) % 2 == 0) {
    snprintf(text, sizeof(text), "HR:%s O2:%s%%", hrText, oxygenText); line(0, text);
    if (!pulseOK) line(1, "MAX missing");
    else if (!finger) line(1, "Place finger");
    else if (!hrValid || !spo2Valid) line(1, "Hold still...");
    else line(1, "Bench estimates");
  } else {
    if (goodTemp) snprintf(text, sizeof(text), "Object:%.1fC", objectC);
    else snprintf(text, sizeof(text), "Temp unavailable");
    line(0, text); line(1, clockRunning ? timeText : "RTC unset/check");
  }
}


