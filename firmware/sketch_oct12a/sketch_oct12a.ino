// NeoGuard hardware bench prototype. Not a validated medical monitor.
// ESP32-S3 only. See README.md before connecting power.
#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include <Adafruit_GFX.h>
#include <Adafruit_MLX90614.h>
#include <ThreeWire.h>
#include <RtcDS1302.h>
#include <MAX30105.h>
#include "spo2_algorithm.h"
#include <math.h>
#include "display_icons.h"

// 1 = previous 240x280 ST7789 SPI display; 2 = 128x64 SSD1306 I2C OLED.
// Confirm the actual controller: these drivers are not interchangeable.
#define DISPLAY_KIND 1
#if DISPLAY_KIND == 1
#include <Adafruit_ST7789.h>
#elif DISPLAY_KIND == 2
#include <Adafruit_SSD1306.h>
#else
#error Select DISPLAY_KIND 1 or 2
#endif

constexpr int SDA_PIN = 4, SCL_PIN = 5;
constexpr int RTC_CLK = 6, RTC_DAT = 7, RTC_RST = 14;
constexpr int TFT_RST = 8, TFT_DC = 9, TFT_CS = 10; // Use -1 if confirmed CS-less.
constexpr int SPI_MOSI = 11, SPI_SCK = 12;
constexpr int SD_SCK = 40, SD_MOSI = 41, SD_MISO = 42, SD_CS = 21;
constexpr int BUZZER = 15, RED_LED = 16, GREEN_LED = 17, BLUE_LED = 18;
constexpr bool ACTIVE_BUZZER = true;
constexpr bool BUZZER_ACTIVE_LOW = false; // Set true for an active-low buzzer module.
constexpr bool RGB_COMMON_ANODE = false;
constexpr bool SET_RTC_TIME = false; // Set true once, upload; false, upload again.
// Use sync_rtc.ps1 after uploading to set actual Nairobi time, without rebuilding.
constexpr bool AUTO_SET_RTC_IF_INVALID = false;
constexpr bool ENABLE_SD_LOGGING = true;
constexpr uint16_t TFT_WIDTH = 240, TFT_HEIGHT = 280;
constexpr uint8_t OLED_ADDRESS = 0x3C; // Some OLEDs use 0x3D.
constexpr uint32_t FINGER_THRESHOLD = 50000; // Bench tuning required.
constexpr char LOG_PATH[] = "/neoguard.csv";
constexpr char LOG_HEADER[] = "boot_id,row,uptime_ms,rtc_local,rtc_valid,object_c,ambient_c,temperature_valid,hr_bpm,hr_valid,spo2_pct,spo2_valid,contact,ir,red,max_detected\n";

#if DISPLAY_KIND == 1
Adafruit_ST7789 screen(&SPI, TFT_CS, TFT_DC, TFT_RST);
#else
Adafruit_SSD1306 screen(128, 64, &Wire, -1, 100000, 100000);
#endif
Adafruit_MLX90614 mlx;
MAX30105 pulse;
SPIClass sdSPI(HSPI); // Independent bus also supports displays without CS.
ThreeWire rtcWire(RTC_DAT, RTC_CLK, RTC_RST);
RtcDS1302<ThreeWire> rtc(rtcWire);

bool displayOK = false, tempOK = false, pulseOK = false, sdOK = false;
const char *sdError = "NOT STARTED";
void queueOfflineReading();
void beginOfflineSync();
void serviceOfflineSync();
bool rtcOK = false, finger = false, goodTemp = false;
float objectC = NAN, ambientC = NAN;
uint32_t irBuffer[100], redBuffer[100], lastIR = 0, lastRed = 0;
int sampleCount = 0, newSamples = 0;
int32_t spo2 = 0, heartRate = 0;
int8_t spo2Valid = 0, hrValid = 0;
uint32_t lastSample = 0, lastService = 0, lastReport = 0, lastSDRetry = 0;
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

void resetPulse() {
  sampleCount = 0;
  newSamples = 0;
  hrValid = 0;
  spo2Valid = 0;
}

void collectPulse() {
  if (!pulseOK) return;
  uint32_t now = millis();
  // An SD write can stall. Do not treat samples across a long gap as continuous.
  if (now - lastService >= 120) {
    pulse.clearFIFO();
    resetPulse();
    finger = false;
  }
  lastService = now;
  pulse.check();
  while (pulse.available()) {
    lastIR = pulse.getFIFOIR();
    lastRed = pulse.getFIFORed();
    pulse.nextSample();
    lastSample = millis();
    finger = lastIR >= FINGER_THRESHOLD;
    if (!finger) { resetPulse(); continue; }
    if (sampleCount < 100) {
      irBuffer[sampleCount] = lastIR;
      redBuffer[sampleCount++] = lastRed;
      if (sampleCount == 100) newSamples = 25;
    } else {
      for (int i = 1; i < 100; ++i) {
        irBuffer[i - 1] = irBuffer[i];
        redBuffer[i - 1] = redBuffer[i];
      }
      irBuffer[99] = lastIR;
      redBuffer[99] = lastRed;
      ++newSamples;
    }
    if (sampleCount == 100 && newSamples >= 25) {
      maxim_heart_rate_and_oxygen_saturation(irBuffer, 100, redBuffer,
        &spo2, &spo2Valid, &heartRate, &hrValid);
      hrValid = hrValid && heartRate > 0 && heartRate <= 250;
      spo2Valid = spo2Valid && spo2 >= 0 && spo2 <= 100;
      newSamples = 0;
    }
  }
  if (millis() - lastSample > 2000) { finger = false; resetPulse(); }
}

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
  if (!log) { sdError = "OPEN CSV"; Serial.println("SD: cannot open neoguard.csv."); return false; }
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
  char tempText[16] = "", ambientText[16] = "", hrText[12] = "", oxygenText[12] = "";
  if (goodTemp) {
    snprintf(tempText, sizeof(tempText), "%.2f", objectC);
    snprintf(ambientText, sizeof(ambientText), "%.2f", ambientC);
  }
  if (hrValid) snprintf(hrText, sizeof(hrText), "%ld", (long)heartRate);
  if (spo2Valid) snprintf(oxygenText, sizeof(oxygenText), "%ld", (long)spo2);
  char row[256];
  int length = snprintf(row, sizeof(row), "%08lX,%lu,%lu,%s,%d,%s,%s,%d,%s,%d,%s,%d,%d,%lu,%lu,%d\n",
    (unsigned long)bootID, (unsigned long)++rowNumber, (unsigned long)millis(),
    timestamp, rtcOK, tempText, ambientText, goodTemp, hrText, hrValid,
    oxygenText, spo2Valid, finger, (unsigned long)lastIR, (unsigned long)lastRed, pulseOK);
  Serial.print(row);
  if (!ENABLE_SD_LOGGING || !sdOK || length < 0 || length >= (int)sizeof(row)) return;
  File log = SD.open(LOG_PATH, FILE_APPEND);
  if (!log) { sdOK = false; sdError = "OPEN CSV"; return; }
  size_t written = log.write((const uint8_t *)row, length);
  log.flush();
  sdOK = written == (size_t)length && !log.getWriteError();
  log.close();
  if (sdOK) { ++savedRows; queueOfflineReading(); }
  if (!sdOK) {
    if (strcmp(sdError, "OK") == 0) sdError = "WRITE CSV";
    Serial.printf("SD %s failed. Automatic retry in 10 seconds.\n", sdError);
  }
}

#include "offline_sync.h"

#if DISPLAY_KIND == 1
constexpr uint16_t UI_BG = 0x08A4, UI_PANEL = 0x1147, UI_WHITE = 0xEFBF;
constexpr uint16_t UI_MUTED = 0x9578, UI_RED = 0xFB0F, UI_CYAN = 0x56BD;
constexpr uint16_t UI_GOLD = 0xFE2D, UI_GREEN = 0x6EB5;

void tftText(int x, int y, const char *text, uint8_t size, uint16_t color) {
  screen.setCursor(x, y); screen.setTextSize(size); screen.setTextColor(color);
  screen.print(text);
}

void drawDashboardFrame() {
  screen.fillScreen(UI_BG);
  screen.fillRect(0, 0, TFT_WIDTH, 28, UI_PANEL);
  screen.drawBitmap(12, 6, ICON_HEART_16, 16, 16, UI_RED);
  tftText(36, 6, "NEOGUARD", 2, UI_WHITE);
  tftText(178, 10, "BENCH", 1, UI_MUTED);
  tftText(12, 270, "SYNC SETUP NEEDED", 1, UI_MUTED);
}
#endif

void drawDisplay() {
  if (!displayOK) return;
  char line[40], hrText[12] = "--", oxygenText[12] = "--", tempText[12] = "--";
  if (hrValid) snprintf(hrText, sizeof(hrText), "%ld", (long)heartRate);
  if (spo2Valid) snprintf(oxygenText, sizeof(oxygenText), "%ld", (long)spo2);
  // Keep the large surface-temperature value within its four-character field.
  if (goodTemp && objectC > -10 && objectC < 100) snprintf(tempText, sizeof(tempText), "%.1f", objectC);
  else if (goodTemp) snprintf(tempText, sizeof(tempText), "RNG");
  const char *status = !goodTemp ? "CHECK TEMP SENSOR" :
    !pulseOK ? "CHECK MAX SENSOR" : !finger ? "PLACE FINGER" :
    (!hrValid || !spo2Valid) ? "HOLD STILL..." : !rtcOK ? "SET CLOCK VIA USB" : "SIGNAL READY";
  uint16_t storageColor = sdOK ? 0x6EB5 : 0xFE2D;
  const char *storageState = !ENABLE_SD_LOGGING ? "SD DISABLED" : sdOK ? "SD LOGGING" : "SD NOT READY";
#if DISPLAY_KIND == 1
  // Update one small panel at a time and service the pulse FIFO between panels.
  screen.fillRect(0, 30, TFT_WIDTH, 26, UI_BG);
  screen.drawBitmap(12, 34, ICON_CLOCK_16, 16, 16, rtcOK ? UI_CYAN : UI_GOLD);
  tftText(36, 38, rtcOK ? dateLabel : "RTC UNSET", 1, UI_MUTED);
  tftText(132, 32, rtcOK ? timeLabel : "--:--:--", 2, UI_WHITE);
  collectPulse();

  screen.fillRoundRect(10, 60, 220, 61, 10, UI_PANEL);
  screen.drawBitmap(20, 75, ICON_HEART_32, 32, 32, UI_RED);
  tftText(64, 70, "HEART RATE", 1, UI_MUTED);
  tftText(64, 90, hrText, 3, UI_WHITE);
  tftText(178, 105, "bpm", 1, UI_MUTED);
  collectPulse();

  screen.fillRoundRect(10, 126, 104, 63, 9, UI_PANEL);
  screen.drawBitmap(18, 132, ICON_OXYGEN_16, 16, 16, UI_CYAN);
  tftText(40, 136, "SpO2", 1, UI_MUTED);
  tftText(20, 155, oxygenText, 3, UI_WHITE);
  tftText(86, 170, "%", 1, UI_CYAN);
  collectPulse();

  screen.fillRoundRect(120, 126, 110, 63, 9, UI_PANEL);
  screen.drawBitmap(128, 132, ICON_TEMPERATURE_16, 16, 16, UI_GOLD);
  tftText(150, 136, "SURFACE", 1, UI_MUTED);
  tftText(130, 155, tempText, 3, UI_WHITE);
  tftText(212, 170, "C", 1, UI_GOLD);
  collectPulse();

  screen.fillRect(10, 195, 220, 17, UI_BG);
  if (goodTemp) snprintf(line, sizeof(line), "AMBIENT %.1f C", ambientC);
  else snprintf(line, sizeof(line), "AMBIENT -- C");
  tftText(14, 199, line, 1, UI_MUTED);
  screen.fillRoundRect(10, 216, 220, 24, 6, UI_PANEL);
  bool signalReady = rtcOK && goodTemp && pulseOK && finger && hrValid && spo2Valid;
  tftText(20, 224, status, 1, signalReady ? UI_GREEN : UI_GOLD);
  collectPulse();

  screen.fillRect(10, 246, 220, 20, UI_BG);
  screen.drawBitmap(12, 248, ICON_STORAGE_16, 16, 16, storageColor);
  if (ENABLE_SD_LOGGING && !sdOK) snprintf(line, sizeof(line), "SD %s", sdError);
  else snprintf(line, sizeof(line), "%s #%lu", storageState, (unsigned long)savedRows);
  tftText(36, 252, line, 1, storageColor);
  screen.fillRect(10, 268, 220, 12, UI_BG);
  tftText(12, 270, !rtcOK ? "SET CLOCK VIA USB" : syncState, 1, UI_MUTED);
  collectPulse();
#else
  // Compact monochrome alternative; the actual wired screen uses the TFT layout.
  screen.clearDisplay(); screen.setTextSize(1); screen.setTextColor(SSD1306_WHITE);
  screen.setCursor(0, 0); screen.print(rtcOK ? timeLabel : "SET RTC VIA USB");
  screen.setCursor(0, 8); screen.print(rtcOK ? dateLabel : "TIME? for help");
  screen.drawBitmap(0, 18, ICON_HEART_16, 16, 16, SSD1306_WHITE);
  screen.setCursor(20, 20); screen.print("HR "); screen.print(hrText);
  screen.setCursor(20, 28); screen.print("O2 "); screen.print(oxygenText); screen.print('%');
  screen.drawBitmap(0, 36, ICON_TEMPERATURE_16, 16, 16, SSD1306_WHITE);
  screen.setCursor(20, 40); screen.print(tempText); screen.print(" C surface");
  screen.setCursor(0, 56); screen.print(storageState);
  screen.display();
#endif
}

void setup() {
  Serial.begin(115200);
  delay(1500); // Allow native USB serial to enumerate before startup messages.
  bootID = esp_random();
  pinMode(BUZZER, OUTPUT);
  pinMode(RED_LED, OUTPUT); pinMode(GREEN_LED, OUTPUT); pinMode(BLUE_LED, OUTPUT);
  setBuzzer(false); setRGB(false, false, true);
  if (TFT_CS >= 0) { pinMode(TFT_CS, OUTPUT); digitalWrite(TFT_CS, HIGH); }
  pinMode(SD_CS, OUTPUT); digitalWrite(SD_CS, HIGH);
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000); Wire.setTimeOut(50);
  SPI.begin(SPI_SCK, -1, SPI_MOSI, TFT_CS);
  sdSPI.begin(SD_SCK, SD_MISO, SD_MOSI, SD_CS);
  Serial.println("NeoGuard bench prototype. CSV timestamps are Nairobi local time (no UTC suffix).");
  for (uint8_t address = 1; address < 127; ++address) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) Serial.printf("I2C found 0x%02X\n", address);
  }
  // SD uses its own SPI peripheral, independent of the display.
  sdOK = initSD();
  lastSDRetry = millis();
#if DISPLAY_KIND == 1
  screen.init(TFT_WIDTH, TFT_HEIGHT); screen.setSPISpeed(20000000);
  screen.setRotation(0); screen.setTextWrap(false);
  drawDashboardFrame();
  displayOK = true; // SPI TFT has no presence acknowledgement.
#else
  displayOK = screen.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS);
  screen.setTextSize(1); screen.setTextColor(SSD1306_WHITE); screen.setTextWrap(false);
#endif
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
  Serial.println("Clock commands: TIME? or TIME YYYY-MM-DD HH:MM:SS (Nairobi UTC+03:00).");
  Serial.println("Use sync_rtc.ps1 after upload to set current time accurately.");
  pulseOK = pulse.begin(Wire, I2C_SPEED_STANDARD);
  if (pulseOK) {
    pulse.setup(60, 4, 2, 100, 411, 4096); // Effective FIFO rate 25 Hz.
    pulse.clearFIFO();
  }
  Wire.setClock(100000);
  lastService = millis();
  beginOfflineSync();
  Serial.printf("MLX=%d MAX=%d SD=%d display_init=%d\n", tempOK, pulseOK, sdOK, displayOK);
  if (!ENABLE_SD_LOGGING) Serial.println("SD logging disabled: system runs without a card.");
  setBuzzer(true); bootBeeping = true; bootBeepStart = millis();
}

void loop() {
  if (bootBeeping && millis() - bootBeepStart >= 150) {
    setBuzzer(false); bootBeeping = false;
  }
  collectPulse();
  serviceSerial();
  serviceOfflineSync();
  collectPulse();
  if (millis() - lastReport < 1000) return;
  lastReport = millis();
  objectC = tempOK ? mlx.readObjectTempC() : NAN;
  collectPulse();
  ambientC = tempOK ? mlx.readAmbientTempC() : NAN;
  collectPulse();
  goodTemp = isfinite(objectC) && isfinite(ambientC) && objectC >= -70 &&
    objectC <= 380 && ambientC >= -40 && ambientC <= 125;
  refreshClock();
  if (ENABLE_SD_LOGGING && !sdOK && millis() - lastSDRetry >= 10000) {
    lastSDRetry = millis(); sdOK = initSD();
    if (sdOK) beginOfflineSync();
  }
  // Slow storage operations invalidate the pulse window before the next report.
  collectPulse();
  logReading();
  collectPulse();
  // Blue = running / awaiting contact. Red = sensor fault, not a clinical alarm.
  // Clock, storage and upload status remain visible separately.
  bool fault = !goodTemp || !pulseOK || millis() - lastSample > 2000;
  setRGB(fault, false, !fault);
  if (fault) Serial.printf("SENSOR FAULT: temp_valid=%d MAX_detected=%d sample_age_ms=%lu\n",
    goodTemp, pulseOK, (unsigned long)(millis() - lastSample));
  drawDisplay();
}
