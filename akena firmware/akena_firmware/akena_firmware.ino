// NeoGuard hardware bench prototype. Not a validated medical monitor.
// ESP32-S3 only. See README.md before connecting power.
#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include <LiquidCrystal.h>
#include <Adafruit_MLX90614.h>
#include <ThreeWire.h>
#include <RtcDS1302.h>
#include <MAX30105.h>
#include "spo2_algorithm.h"
#include <math.h>
#include <sys/time.h>
#include "measurement.h"

constexpr int SDA_PIN = 4, SCL_PIN = 5;
constexpr int RTC_CLK = 6, RTC_DAT = 7, RTC_RST = 14;
constexpr int LCD_RS = 8, LCD_EN = 9, LCD_D4 = 10, LCD_D5 = 11, LCD_D6 = 12, LCD_D7 = 13;
constexpr int SD_SCK = 40, SD_MOSI = 41, SD_MISO = 42, SD_CS = 21;
constexpr int BUZZER = 15, RED_LED = 16, GREEN_LED = 17, BLUE_LED = 18;
constexpr bool ACTIVE_BUZZER = true;
constexpr bool BUZZER_ACTIVE_LOW = false; // Set true for an active-low buzzer module.
constexpr bool RGB_COMMON_ANODE = false;
constexpr bool SET_RTC_TIME = false; // Set true once, upload; false, upload again.
// Use sync_rtc.ps1 after uploading to set actual Nairobi time, without rebuilding.
constexpr bool AUTO_SET_RTC_IF_INVALID = false;
constexpr bool ENABLE_SD_LOGGING = true;
constexpr uint32_t FINGER_THRESHOLD = 50000; // Bench tuning required.
constexpr char LOG_PATH[] = "/neoguard_v2.csv";
constexpr char LOG_HEADER[] = "boot_id,row,uptime_ms,rtc_local,rtc_valid,object_c,ambient_c,temperature_valid,hr_bpm,hr_valid,spo2_pct,spo2_valid,contact,ir,red,max_detected,raw_hr,raw_spo2,raw_object_c,measurement_ready,contact_seconds,alarm_flags\n";

LiquidCrystal lcd(LCD_RS, LCD_EN, LCD_D4, LCD_D5, LCD_D6, LCD_D7);
Adafruit_MLX90614 mlx;
MAX30105 pulse;
SPIClass sdSPI(HSPI); // SD bus; LCD uses parallel GPIO, not SPI.
ThreeWire rtcWire(RTC_DAT, RTC_CLK, RTC_RST);
RtcDS1302<ThreeWire> rtc(rtcWire);

bool displayOK = false, tempOK = false, pulseOK = false, sdOK = false;
const char *sdError = "NOT STARTED";
void queueOfflineReading();
void beginOfflineSync();
void serviceOfflineSync();
void requestWifiSetup();
void printSystemStatus();
StableMeasurement measurement;
ThresholdAlarm thresholdAlarm;
AlarmLimits alarmLimits;
unsigned activeAlarmFlags() {
  Measurement result = measurement.get(millis());
  unsigned flags = thresholdAlarm.flags();
  if (result.ready) {
    if (result.hr < alarmLimits.hrLow) flags |= 1;
    if (result.hr > alarmLimits.hrHigh) flags |= 2;
    if (result.temperature < alarmLimits.tempLow) flags |= 4;
    if (result.oxygen < alarmLimits.spo2Low) flags |= 8;
  }
  return flags;
}
bool sensorFault = false;
uint32_t lastQueuedMeasurement = 0;
bool rtcOK = false, finger = false, goodTemp = false;
float objectC = NAN, ambientC = NAN;
uint32_t lastIR = 0, lastRed = 0;
int32_t spo2 = 0, heartRate = 0;
int8_t spo2Valid = 0, hrValid = 0;
uint32_t lastSample = 0, lastReport = 0, lastSDRetry = 0;
uint32_t bootBeepStart = 0, rowNumber = 0;
bool bootBeeping = false;
char timestamp[24] = "";
char dateLabel[16] = "", timeLabel[12] = "";
uint32_t savedRows = 0;
char serialCommand[64];
size_t commandLength = 0;
bool commandOverflow = false;

void refreshClock() {
  RtcDateTime now = rtc.GetDateTime();
  rtcOK = rtc.IsDateTimeValid() && now.IsValid() && rtc.GetIsRunning() && now.Year() >= 2020;
  timestamp[0] = dateLabel[0] = timeLabel[0] = '\0';
  if (!rtcOK) return;
  snprintf(timestamp, sizeof(timestamp), "%04u-%02u-%02u %02u:%02u:%02u",
    now.Year(), now.Month(), now.Day(), now.Hour(), now.Minute(), now.Second());
  snprintf(dateLabel, sizeof(dateLabel), "%02u/%02u/%04u", now.Day(), now.Month(), now.Year());
  snprintf(timeLabel, sizeof(timeLabel), "%02u:%02u:%02u", now.Hour(), now.Minute(), now.Second());
}

void handleClockCommand(const char *command) {
  if (strcmp(command, "STATUS") == 0) { printSystemStatus(); return; }
  if (strcmp(command, "WIFI SETUP") == 0) { requestWifiSetup(); return; }
  if (strcmp(command, "TIME?") == 0) {
    refreshClock();
    Serial.printf("RTC %s (Nairobi UTC+03:00)\n", rtcOK ? timestamp : "UNSET - send TIME YYYY-MM-DD HH:MM:SS");
    return;
  }
  unsigned int year, month, day, hour, minute, second;
  int consumed = 0;
  if (strlen(command) != 24 || sscanf(command, "TIME %4u-%2u-%2u %2u:%2u:%2u%n", &year, &month, &day,
      &hour, &minute, &second, &consumed) != 6 || command[consumed] != '\0' ||
      year < 2020 || year > 2099 || month < 1 || month > 12 || day < 1 ||
      hour > 23 || minute > 59 || second > 59) {
    Serial.println("RTC ERROR: use TIME YYYY-MM-DD HH:MM:SS, years 2020-2099, Nairobi local time.");
    return;
  }
  const uint8_t daysPerMonth[] = {31,28,31,30,31,30,31,31,30,31,30,31};
  uint8_t maxDay = daysPerMonth[month - 1];
  if (month == 2 && year % 4 == 0) maxDay = 29; // Range excludes 2100.
  if (day > maxDay) { Serial.println("RTC ERROR: invalid calendar date."); return; }
  RtcDateTime requested(year, month, day, hour, minute, second);
  rtc.SetIsWriteProtected(false);
  rtc.SetDateTime(requested);
  rtc.SetIsRunning(true);
  refreshClock();
  RtcDateTime readback = rtc.GetDateTime();
  if (rtcOK && readback.TotalSeconds() >= requested.TotalSeconds() &&
      readback.TotalSeconds() - requested.TotalSeconds() <= 2) {
    Serial.printf("RTC SET OK %s (Nairobi UTC+03:00)\n", timestamp);
  } else Serial.println("RTC ERROR: readback failed; check DS1302 wiring and power.");
}

void serviceSerial() {
  // Limit work per loop to keep the pulse sensor serviced during incoming text.
  for (int i = 0; i < 32 && Serial.available(); ++i) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (commandOverflow) Serial.println("RTC ERROR: command too long.");
      else if (commandLength) {
        serialCommand[commandLength] = '\0'; handleClockCommand(serialCommand);
      }
      commandLength = 0; commandOverflow = false;
    } else if ((unsigned char)c < 32 || (unsigned char)c > 126) {
      commandOverflow = true;
    } else if (commandLength < sizeof(serialCommand) - 1) {
      serialCommand[commandLength++] = c;
    } else commandOverflow = true;
  }
}

void setRGB(bool r, bool g, bool b) {
  digitalWrite(RED_LED, r != RGB_COMMON_ANODE);
  digitalWrite(GREEN_LED, g != RGB_COMMON_ANODE);
  digitalWrite(BLUE_LED, b != RGB_COMMON_ANODE);
}

void setBuzzer(bool on) {
  if (ACTIVE_BUZZER) digitalWrite(BUZZER, on != BUZZER_ACTIVE_LOW);
  else if (on) tone(BUZZER, 2000);
  else noTone(BUZZER);
}

#include "pulse_sampler.h"

bool initSD() {
  if (!ENABLE_SD_LOGGING) return false;
  Serial.println("SD: mounting on CS21 SCK40 MOSI41 MISO42...");
  SD.end();
  // Slow SPI is more tolerant of breadboard wiring. Never format automatically.
  bool mounted = SD.begin(SD_CS, sdSPI, 1000000);
  if (!mounted) {
    SD.end();
    Serial.println("SD: retrying mount at 400 kHz...");
    mounted = SD.begin(SD_CS, sdSPI, 400000);
  }
  if (!mounted || SD.cardType() == CARD_NONE) {
    sdError = "MOUNT";
    Serial.println("SD MOUNT FAILED: check FAT32 card, module-rated supply, shared GND and SPI wires.");
    return false;
  }
  File log = SD.open(LOG_PATH, FILE_APPEND);
  if (!log) { sdError = "OPEN CSV"; Serial.println("SD: cannot open neoguard_v2.csv."); return false; }
  bool ok = true;
  if (log.size() == 0) {
    ok = log.print(LOG_HEADER) == strlen(LOG_HEADER);
  }
  log.flush();
  ok = ok && !log.getWriteError();
  size_t expectedSize = log.size();
  log.close();
  File verify = SD.open(LOG_PATH, FILE_READ);
  ok = ok && verify && verify.size() == expectedSize;
  if (ok) {
    String actualHeader = verify.readStringUntil('\n');
    ok = actualHeader + '\n' == LOG_HEADER;
  }
  verify.close();
  sdError = ok ? "OK" : "CSV CHECK";
  Serial.printf("SD: %s, card size=%llu MB.\n", ok ? "CSV ready" : "CSV write/read check failed",
    (unsigned long long)(SD.cardSize() / (1024 * 1024)));
  return ok;
}

uint32_t bootID = 0;

void logReading() {
  Measurement result = measurement.get(millis());
  char tempText[16] = "", ambientText[16] = "", hrText[12] = "", oxygenText[12] = "";
  if (result.ready) {
    snprintf(tempText, sizeof(tempText), "%.2f", result.temperature);
  }
  if (goodTemp) snprintf(ambientText, sizeof(ambientText), "%.2f", ambientC);
  if (result.ready) snprintf(hrText, sizeof(hrText), "%d", (int)lroundf(result.hr));
  if (result.ready) snprintf(oxygenText, sizeof(oxygenText), "%d", (int)lroundf(result.oxygen));
  char row[384];
  int length = snprintf(row, sizeof(row), "%08lX,%lu,%lu,%s,%d,%s,%s,%d,%s,%d,%s,%d,%d,%lu,%lu,%d,%ld,%ld,%.2f,%d,%u,%u\n",
    (unsigned long)bootID, (unsigned long)++rowNumber, (unsigned long)millis(),
    timestamp, rtcOK, tempText, ambientText, result.ready, hrText, result.ready,
    oxygenText, result.ready, finger, (unsigned long)lastIR, (unsigned long)lastRed, pulseOK,
    (long)heartRate, (long)spo2, objectC, result.ready, measurement.elapsed(millis()), activeAlarmFlags());
  Serial.print(row);
  if (!ENABLE_SD_LOGGING || !sdOK || length < 0 || length >= (int)sizeof(row)) return;
  File log = SD.open(LOG_PATH, FILE_APPEND);
  if (!log) { sdOK = false; sdError = "OPEN CSV"; return; }
  size_t written = log.write((const uint8_t *)row, length);
  log.flush();
  sdOK = written == (size_t)length && !log.getWriteError();
  log.close();
  if (sdOK) ++savedRows;
  if (!sdOK) {
    if (strcmp(sdError, "OK") == 0) sdError = "WRITE CSV";
    Serial.printf("SD %s failed. Retry when finger is removed (10-second interval).\n", sdError);
  }
}

#include "offline_sync.h"

void printSystemStatus() {
  Measurement result = measurement.get(millis());
  Serial.printf("STATUS WiFi=%s IP=%s portal=%d configured=%d session=%lu RTC=%d SD=%d MAX=%d MLX=%d ready=%d\n",
    WiFi.status() == WL_CONNECTED ? "connected" : "offline", WiFi.localIP().toString().c_str(),
    wifiPortalActive(), deviceCode.length() >= 3 && deviceSecret.length() > 0,
    (unsigned long)assignedSession, rtcOK, sdOK, pulseOK, goodTemp, result.ready);
  Serial.printf("STATUS sync=%s signal_seconds=%u alarms=%u RAM_pending=%u dropped=%u\n",
    syncState, measurement.elapsed(millis()), activeAlarmFlags(), ramSize, droppedReadings);
}

// Pad every row so shorter messages cannot leave stale characters behind.
void lcdLine(uint8_t row, const char *text) {
  lcd.setCursor(0, row);
  for (uint8_t i = 0; i < 16; ++i) lcd.write(*text ? *text++ : ' ');
}

void drawConnectionSetup() {
  // A 16x2 LCD needs several pages to show the phone setup instructions.
  // Keep a sensor/alarm page in the rotation while the portal is open.
  switch ((millis() / 4000) % 5) {
    case 0: lcdLine(0, "Join phone WiFi:"); lcdLine(1, setupNetwork.c_str()); break;
    case 1: lcdLine(0, "WiFi password:"); lcdLine(1, setupPassword.c_str()); break;
    case 2: lcdLine(0, "Open browser:"); lcdLine(1, "192.168.4.1"); break;
    case 3: lcdLine(0, "Choose 2.4G WiFi"); lcdLine(1, "Enter pass, Save"); break;
    default:
      lcdLine(0, "SENSOR STATUS");
      lcdLine(1, activeAlarmFlags() ? "ALARM: CHECK NOW" : sensorFault ? "CHECK SENSORS" : "Sensors running");
  }
}

void drawDisplay() {
  if (!displayOK) return;
  if (wifiPortalActive()) { drawConnectionSetup(); return; }
  char row[32];
  Measurement result = measurement.get(millis());
  const unsigned alarms = activeAlarmFlags();
  const char *alert = alarms & 1 ? "ALARM HR LOW" : alarms & 2 ? "ALARM HR HIGH" :
    alarms & 4 ? "ALARM TEMP LOW" : alarms & 8 ? "ALARM SPO2 LOW" : nullptr;
  // Keep alarms visible on every page, alongside alternating real measurements.
  unsigned page = (millis() / 4000) % 4;
  if (alert || sensorFault || page == 0) {
    if (result.ready) {
      snprintf(row, sizeof(row), "HR:%d O2:%d%%", (int)lroundf(result.hr), (int)lroundf(result.oxygen));
    } else snprintf(row, sizeof(row), "HR:-- O2:--%%");
    lcdLine(0, row);
    if (alert) lcdLine(1, alert);
    else if (sensorFault) lcdLine(1, !goodTemp ? "CHECK TEMP" : "CHECK MAX30102");
    else if (!finger) lcdLine(1, "PLACE FINGER");
    else if (!result.ready) {
      if (measurement.elapsed(millis()) < 60) {
        snprintf(row, sizeof(row), "Hold finger %u/60", measurement.elapsed(millis()));
        lcdLine(1, row);
      } else lcdLine(1, "SIGNAL UNSTABLE");
    } else {
      snprintf(row, sizeof(row), "Surface: %.1f C", result.temperature);
      lcdLine(1, row);
    }
  } else if (page == 1) {
    lcdLine(0, rtcOK ? dateLabel : "RTC UNSET");
    lcdLine(1, rtcOK ? timeLabel : "Set TIME via USB");
  } else if (page == 2) {
    lcdLine(0, WiFi.status() == WL_CONNECTED ? "WiFi connected" : "WiFi offline");
    lcdLine(1, WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString().c_str() : "Waiting for WiFi");
  } else {
    lcdLine(0, sdOK ? "SD recording" : "SD NOT READY");
    lcdLine(1, queueDamaged ? "SD QUEUE ERROR" : syncState);
  }
}

void displayStartupStep(const char *step) {
  Serial.printf("NEOGUARD LCD: %s\n", step);
  if (displayOK) { lcdLine(0, "AKENA NEOGUARD"); lcdLine(1, step); }
}

void setup() {
  Serial.begin(115200);
  delay(1500); // Allow native USB serial to enumerate before startup messages.
  Serial.println("NEOGUARD FULL FIRMWARE LCD - RS8 EN9 D4:10 D5:11 D6:12 D7:13");
  pinMode(SD_CS, OUTPUT); digitalWrite(SD_CS, HIGH);
  lcd.begin(16, 2);
  displayOK = true; // Parallel LCD has no initialization readback.
  displayStartupStep("Starting system");
  bootID = esp_random();
  pinMode(BUZZER, OUTPUT);
  pinMode(RED_LED, OUTPUT); pinMode(GREEN_LED, OUTPUT); pinMode(BLUE_LED, OUTPUT);
  setBuzzer(false); setRGB(false, false, true);
  displayStartupStep("2. LED / BUZZER READY");
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000); Wire.setTimeOut(50);
  displayStartupStep("3. I2C BUS READY");
  sdSPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  displayStartupStep("4. SD BUS STARTED");
  Serial.println("NeoGuard bench prototype. CSV timestamps are Nairobi local time (no UTC suffix).");
  for (uint8_t address = 1; address < 127; ++address) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) Serial.printf("I2C found 0x%02X\n", address);
  }
  // SD uses its own SPI peripheral, independent of the display.
  sdOK = initSD();
  lastSDRetry = millis();
  displayStartupStep(sdOK ? "5. SD CARD READY" : "5. SD CARD NOT READY");
  tempOK = mlx.begin(0x5A, &Wire);
  rtc.Begin(); rtc.SetIsWriteProtected(false);
  rtc.SetTrickleChargeSettings(DS1302Tcr_Disabled); // CR2032 is not rechargeable.
  if (SET_RTC_TIME || (AUTO_SET_RTC_IF_INVALID &&
      (!rtc.IsDateTimeValid() || !rtc.GetIsRunning()))) {
    rtc.SetDateTime(RtcDateTime(__DATE__, __TIME__));
    rtc.SetIsRunning(true);
    Serial.println("RTC set from compilation time. Computer clock must use Nairobi time.");
  }
  refreshClock();
  if (rtcOK) {
    timeval systemTime = {(time_t)(rtc.GetDateTime().TotalSeconds() + 946684800UL - 10800UL), 0};
    settimeofday(&systemTime, nullptr);
  }
  Serial.println("Commands: STATUS, WIFI SETUP, TIME?, TIME YYYY-MM-DD HH:MM:SS (Nairobi UTC+03:00).");
  Serial.println("Use sync_rtc.ps1 after upload to set current time accurately.");
  displayStartupStep("6. TEMP / CLOCK CHECKED");
  pulseOK = pulse.begin(Wire, I2C_SPEED_STANDARD);
  if (pulseOK) {
    pulse.setup(60, 4, 2, 100, 411, 4096); // Effective FIFO rate 25 Hz.
    pulse.clearFIFO();
  }
  Wire.setClock(100000);
  displayStartupStep(pulseOK ? "7. PULSE SENSOR READY" : "7. PULSE SENSOR MISSING");
  displayStartupStep("8. STARTING TASKS / WIFI");
  beginPulseSampling();
  beginOfflineSync();
  drawDisplay();
  Serial.printf("MLX=%d MAX=%d SD=%d display_init=%d\n", tempOK, pulseOK, sdOK, displayOK);
  if (!ENABLE_SD_LOGGING) Serial.println("SD logging disabled: system runs without a card.");
  setBuzzer(true); bootBeeping = true; bootBeepStart = millis();
}

void loop() {
  bool sound = bootBeeping && millis() - bootBeepStart < 150;
  if (millis() - bootBeepStart >= 150) bootBeeping = false;
  sound = sound || (activeAlarmFlags() && millis() % 500 < 250) || (sensorFault && millis() % 2000 < 250);
  setBuzzer(sound);
  setRGB(sensorFault || activeAlarmFlags(), false, !sensorFault && !activeAlarmFlags());
  collectPulse();
  serviceSerial();
  serviceOfflineSync();
  collectPulse();
  if (millis() - lastReport < 1000) return;
  lastReport = millis();
  objectC = readSurfaceTemperature(false);
  collectPulse();
  ambientC = readSurfaceTemperature(true);
  collectPulse();
  goodTemp = isfinite(objectC) && isfinite(ambientC) && objectC >= -70 &&
    objectC <= 380 && ambientC >= -40 && ambientC <= 125;
  bool contact = finger && millis() - lastSample <= 2000;
  measurement.observe(millis(), contact, hrValid && spo2Valid && goodTemp,
    heartRate, spo2, objectC);
  thresholdAlarm.observe(contact, hrValid, heartRate, spo2Valid, spo2, goodTemp, objectC, alarmLimits);
  sensorFault = !goodTemp || !pulseOK || (millis() - lastSample > 2000 && millis() - bootBeepStart > 2500);
  refreshClock();
  if (ENABLE_SD_LOGGING && !sdOK && !finger && millis() - lastSDRetry >= 10000) {
    lastSDRetry = millis(); sdOK = initSD();
    if (sdOK) beginOfflineSync();
  }
  // Pulse acquisition continues in its own task during storage operations.
  collectPulse();
  logReading();
  if (measurement.get(millis()).ready && millis() - lastQueuedMeasurement >= 5000) {
    lastQueuedMeasurement = millis(); queueOfflineReading();
  }
  collectPulse();
  // Blue = running / acquiring. Red = threshold alarm or sensor fault.
  bool fault = sensorFault;
  if (fault) Serial.printf("SENSOR FAULT: temp_valid=%d MAX_detected=%d sample_age_ms=%lu\n",
    goodTemp, pulseOK, (unsigned long)(millis() - lastSample));
  drawDisplay();
}
