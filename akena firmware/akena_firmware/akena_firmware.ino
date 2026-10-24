// NeoGuard hardware bench prototype. Not a validated medical monitor.
// ESP32-S3 only. See README.md before connecting power.
#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <Adafruit_MLX90614.h>
#include <ThreeWire.h>
#include <RtcDS1302.h>
#include <MAX30105.h>
#include "spo2_algorithm.h"
#include <math.h>
#include <sys/time.h>
#include "measurement.h"
#include "live_vitals.h"
#include "display_icons.h"
#include "temperature_packet.h"

// Network-enabled full monitor; set to 0 for isolated offline component testing.
#ifndef NEOGUARD_ENABLE_NETWORK
#define NEOGUARD_ENABLE_NETWORK 1
#endif

constexpr int SDA_PIN = 4, SCL_PIN = 5;
constexpr int RTC_CLK = 6, RTC_DAT = 7, RTC_RST = 14;
constexpr int TFT_RST = 8, TFT_DC = 9, TFT_CS = 10, TFT_MOSI = 11, TFT_SCK = 12;
constexpr uint16_t TFT_WIDTH = 240, TFT_HEIGHT = 280;
constexpr int SD_SCK = 40, SD_MOSI = 41, SD_MISO = 42, SD_CS = 21;
constexpr int BUZZER = 15, RED_LED = 16, GREEN_LED = 17, BLUE_LED = 18;
constexpr bool ACTIVE_BUZZER = true;
constexpr bool BUZZER_ACTIVE_LOW = false;  // Set true for an active-low buzzer module.
constexpr bool RGB_COMMON_ANODE = false;
constexpr bool SET_RTC_TIME = false;  // Set true once, upload; false, upload again.
// Use sync_rtc.ps1 after uploading to set actual Nairobi time, without rebuilding.
constexpr bool AUTO_SET_RTC_IF_INVALID = false;
constexpr bool ENABLE_SD_LOGGING = true;
constexpr uint32_t FINGER_THRESHOLD = 50000;  // Bench tuning required.
constexpr uint32_t FINGER_OFF_THRESHOLD = 40000;
constexpr char LOG_PATH[] = "/neoguard_v2.csv";
constexpr char LOG_HEADER[] = "boot_id,row,uptime_ms,rtc_local,rtc_valid,object_c,ambient_c,temperature_valid,hr_bpm,hr_valid,spo2_pct,spo2_valid,contact,ir,red,max_detected,raw_hr,raw_spo2,raw_object_c,measurement_ready,contact_seconds,alarm_flags\n";

Adafruit_ST7789 screen(&SPI, TFT_CS, TFT_DC, TFT_RST);
Adafruit_MLX90614 mlx;
MAX30105 pulse;
SPIClass sdSPI(HSPI);  // Independent from the ST7789's SPI peripheral.
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
RollingHeartAverage heartAverage;
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
uint32_t lastLoggedOffset = 0, pulseSampleTotal = 0, pulseResetCount = 0;
char lastLoggedRow[384] = "";
size_t lastLoggedLength = 0;
uint32_t manualBeepUntil = 0;
volatile bool samplingPaused = false;
uint32_t temperaturePacketErrors = 0;
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
  if (strcmp(command, "SD RETRY") == 0) { sdOK=initSD(); return; }
  if (strcmp(command, "SD QUIET") == 0) { diagnoseQuietSD(); return; }
  if (strcmp(command, "LOGCHECK") == 0) { verifyLatestLog(); return; }
  if (strcmp(command, "BEEP") == 0) {
    manualBeepUntil = millis() + 300;
    setBuzzer(true);
    Serial.println("BEEP: 300 ms output requested; alarms take priority."); return;
  }
  if (strcmp(command, "STATUS") == 0) {
    printSystemStatus();
    return;
  }
  if (strcmp(command, "WIFI SETUP") == 0) {
    requestWifiSetup();
    return;
  }
  if (strcmp(command, "TIME?") == 0) {
    refreshClock();
    Serial.printf("RTC %s (Nairobi UTC+03:00)\n", rtcOK ? timestamp : "UNSET - send TIME YYYY-MM-DD HH:MM:SS");
    return;
  }
  unsigned int year, month, day, hour, minute, second;
  int consumed = 0;
  if (strlen(command) != 24 || sscanf(command, "TIME %4u-%2u-%2u %2u:%2u:%2u%n", &year, &month, &day, &hour, &minute, &second, &consumed) != 6 || command[consumed] != '\0' || year < 2020 || year > 2099 || month < 1 || month > 12 || day < 1 || hour > 23 || minute > 59 || second > 59) {
    Serial.println("RTC ERROR: use TIME YYYY-MM-DD HH:MM:SS, years 2020-2099, Nairobi local time.");
    return;
  }
  const uint8_t daysPerMonth[] = { 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 };
  uint8_t maxDay = daysPerMonth[month - 1];
  if (month == 2 && year % 4 == 0) maxDay = 29;  // Range excludes 2100.
  if (day > maxDay) {
    Serial.println("RTC ERROR: invalid calendar date.");
    return;
  }
  RtcDateTime requested(year, month, day, hour, minute, second);
  rtc.SetIsWriteProtected(false);
  rtc.SetDateTime(requested);
  rtc.SetIsRunning(true);
  refreshClock();
  RtcDateTime readback = rtc.GetDateTime();
  if (rtcOK && readback.TotalSeconds() >= requested.TotalSeconds() && readback.TotalSeconds() - requested.TotalSeconds() <= 2) {
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
        serialCommand[commandLength] = '\0';
        handleClockCommand(serialCommand);
      }
      commandLength = 0;
      commandOverflow = false;
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
  sdSPI.end();
  pinMode(SD_CS,OUTPUT); digitalWrite(SD_CS,HIGH);
  bool busStarted=sdSPI.begin(SD_SCK,SD_MISO,SD_MOSI,SD_CS);
  Serial.printf("SD SPI rebind=%d: SCK%d MISO%d MOSI%d CS%d, host=%d\n",busStarted,SD_SCK,SD_MISO,SD_MOSI,SD_CS,HSPI);
  if (!busStarted) {sdError="SPI INIT"; return false;}
  // Slow SPI is more tolerant of breadboard wiring. Never format automatically.
  bool mounted = SD.begin(SD_CS, sdSPI, 1000000, "/sd", 5, false);
  if (!mounted) {
    SD.end();
    Serial.println("SD: retrying mount at 400 kHz...");
    mounted = SD.begin(SD_CS, sdSPI, 400000, "/sd", 5, false);
  }
  if (!mounted || SD.cardType() == CARD_NONE) {
    sdError = "MOUNT";
    Serial.println("SD MOUNT FAILED: check FAT32 card, module-rated supply, shared GND and SPI wires.");
    return false;
  }
  File log = SD.open(LOG_PATH, FILE_APPEND);
  if (!log) {
    sdError = "OPEN CSV";
    Serial.println("SD: cannot open neoguard_v2.csv.");
    return false;
  }
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

void diagnoseQuietSD() {
  Serial.println("SD QUIET: pausing acquisition and releasing I2C for an isolation test.");
  samplingPaused=true;
  if (!sensorBusMutex || xSemaphoreTake(sensorBusMutex,pdMS_TO_TICKS(500))!=pdTRUE) {
    samplingPaused=false; Serial.println("SD QUIET: I2C busy; no test performed."); return;
  }
  if (pulseOK) pulse.shutDown();
  Wire.end();
  sdOK=initSD();
  Serial.printf("SD QUIET result=%d; restoring sensor bus.\n",sdOK);
  Wire.begin(SDA_PIN,SCL_PIN); Wire.setClock(100000); Wire.setTimeOut(50);
  tempOK=mlx.begin(0x5A,&Wire);
  if (pulseOK) {pulse.wakeUp(); pulse.clearFIFO();}
  xSemaphoreGive(sensorBusMutex); samplingPaused=false;
  measurement.reset(); thresholdAlarm.reset();
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
  // SD is the record of truth. USB backpressure must not delay acquisition/logging.
  if (length>0 && length<(int)sizeof(row) && Serial && Serial.availableForWrite()>=length) {
    Serial.write((const uint8_t *)row,length);
  }
  if (!ENABLE_SD_LOGGING || !sdOK || length < 0 || length >= (int)sizeof(row)) return;
  File log = SD.open(LOG_PATH, FILE_APPEND);
  if (!log) {
    sdOK = false;
    sdError = "OPEN CSV";
    return;
  }
  uint32_t offset = log.size();
  size_t written = log.write((const uint8_t *)row, length);
  log.flush();
  sdOK = written == (size_t)length && !log.getWriteError();
  log.close();
  if (sdOK) {
    ++savedRows; lastLoggedOffset = offset; lastLoggedLength = length;
    memcpy(lastLoggedRow, row, length + 1);
  }
  if (!sdOK) {
    if (strcmp(sdError, "OK") == 0) sdError = "WRITE CSV";
    Serial.printf("SD %s failed. Retry when finger is removed (10-second interval).\n", sdError);
  }
}

void verifyLatestLog() {
  if (!sdOK || !lastLoggedLength) { Serial.println("LOGCHECK: no saved row available."); return; }
  File file = SD.open(LOG_PATH, FILE_READ);
  char actual[384] = "";
  bool ok = file && file.seek(lastLoggedOffset) &&
    file.readBytes(actual, lastLoggedLength) == lastLoggedLength &&
    memcmp(actual, lastLoggedRow, lastLoggedLength) == 0;
  file.close();
  Serial.printf("LOGCHECK %s: saved_rows=%lu, offset=%lu, bytes=%u; existing data retained.\n",
    ok ? "PASS" : "FAIL", (unsigned long)savedRows, (unsigned long)lastLoggedOffset, (unsigned)lastLoggedLength);
  if (!ok) { sdOK = false; sdError = "READBACK"; }
}

#include "connectivity.h"

void printSystemStatus() {
  Measurement result = measurement.get(millis());
  Serial.printf("STATUS WiFi=%s IP=%s portal=%d configured=%d session=%lu RTC=%d SD=%d MAX=%d MLX=%d ready=%d\n",
                wifiOnline() ? "connected" : "offline", wifiAddress().c_str(),
                wifiPortalActive(), deviceCode.length() >= 3 && deviceSecret.length() > 0,
                (unsigned long)assignedSession, rtcOK, sdOK, pulseOK, goodTemp, result.ready);
  Serial.printf("STATUS sync=%s signal_seconds=%u alarms=%u RAM_pending=%u dropped=%u\n",
                syncState, measurement.elapsed(millis()), activeAlarmFlags(), ramSize, droppedReadings);
  Serial.printf("STATUS raw_hr=%ld hr_valid=%d raw_spo2=%ld spo2_valid=%d surface=%.2f ambient=%.2f finger=%d IR=%lu red=%lu\n",
    (long)heartRate, hrValid, (long)spo2, spo2Valid, objectC, ambientC, finger, (unsigned long)lastIR, (unsigned long)lastRed);
  Serial.printf("STATUS uptime_ms=%lu saved_rows=%lu samples=%lu sampler_resets=%lu sample_age_ms=%lu heap=%lu network_build=%d\n",
    (unsigned long)millis(), (unsigned long)savedRows, (unsigned long)pulseSampleTotal, (unsigned long)pulseResetCount,
    (unsigned long)(millis()-lastSample), (unsigned long)ESP.getFreeHeap(), NEOGUARD_ENABLE_NETWORK);
  Serial.printf("STATUS temperature_packet_errors=%lu\n",(unsigned long)temperaturePacketErrors);
  LiveVitals live=selectLiveVitals(millis(),lastSample,finger,hrValid,heartRate,spo2Valid,spo2,goodTemp,objectC,result);
  Serial.printf("LIVE HR_available=%d HR=%.0f SpO2_available=%d SpO2=%.0f qualified=%d surface_low=%.1f\n",
    live.heartAvailable,live.heart,live.oxygenAvailable,live.oxygen,live.qualified,alarmLimits.tempLow);
  HeartAverage average=heartAverage.get(millis());
  LiveVitals displayed=displayHeartAverage(live,average);
  MonitorIndicator indicator=selectMonitorIndicator(displayed,average.ready,sensorFault,activeAlarmFlags(),alarmLimits);
  Serial.printf("AVERAGE HR_available=%d HR=%.1f samples=%u span_ms=%lu window_ms=10000 refresh_ms=3000 LED=%s\n",
    live.heartAvailable && average.ready,average.value,average.samples,(unsigned long)average.spanMs,
    indicator==MonitorIndicator::Green ? "GREEN" : indicator==MonitorIndicator::Red ? "RED" : "BLUE");
  Serial.printf("LIMITS HR_low=%.0f HR_high=%.0f SpO2_low=%.0f surface_low=%.1f\n",
    alarmLimits.hrLow,alarmLimits.hrHigh,alarmLimits.spo2Low,alarmLimits.tempLow);
  printConnectivityStatus();
}

constexpr uint16_t UI_BG=0x08A4, UI_PANEL=0x1147, UI_WHITE=0xEFBF;
constexpr uint16_t UI_MUTED=0x9578, UI_RED=0xFB0F, UI_CYAN=0x56BD;
constexpr uint16_t UI_GOLD=0xFE2D, UI_GREEN=0x6EB5;

void tftText(int x, int y, const char *text, uint8_t size, uint16_t colour) {
  screen.setCursor(x,y); screen.setTextSize(size); screen.setTextColor(colour); screen.print(text);
}

void drawDashboardFrame() {
  if (!displayOK) return;
  screen.fillScreen(UI_BG); screen.fillRect(0,0,TFT_WIDTH,28,UI_PANEL);
  screen.drawBitmap(12,6,ICON_HEART_16,16,16,UI_RED);
  tftText(36,6,"NEOGUARD",2,UI_WHITE); tftText(178,10,"BENCH",1,UI_MUTED);
  screen.fillRoundRect(10,60,220,57,9,UI_PANEL);
  screen.drawBitmap(18,77,ICON_HEART_32,32,32,UI_RED);
  tftText(64,68,"HEART RATE / 10s AVG",1,UI_MUTED); tftText(182,101,"bpm",1,UI_MUTED);
  screen.fillRoundRect(10,124,104,62,9,UI_PANEL);
  screen.drawBitmap(18,130,ICON_OXYGEN_16,16,16,UI_CYAN);
  tftText(40,134,"SpO2",1,UI_MUTED); tftText(88,167,"%",1,UI_CYAN);
  screen.fillRoundRect(120,124,110,62,9,UI_PANEL);
  screen.drawBitmap(128,130,ICON_TEMPERATURE_16,16,16,UI_GOLD);
  tftText(150,134,"SURFACE",1,UI_MUTED); tftText(216,168,"C",1,UI_GOLD);
}

void drawConnectionSetup() {
  screen.fillScreen(UI_BG);
  tftText(10,14,"PHONE WIFI SETUP",2,UI_CYAN);
  tftText(10,52,"Join:",1,UI_WHITE); tftText(10,70,setupNetwork.c_str(),2,UI_WHITE);
  tftText(10,106,"Password:",1,UI_WHITE); tftText(10,124,setupPassword.c_str(),2,UI_WHITE);
  tftText(10,165,"Open 192.168.4.1",2,UI_CYAN);
  tftText(10,205,"Configure WiFi and device credential",1,UI_MUTED);
  tftText(10,235,sensorFault ? "CHECK SENSORS" : activeAlarmFlags() ? "THRESHOLD ALARM" : "Sensors running",1,UI_GOLD);
}

void drawDisplay() {
  if (!displayOK) return;
  static uint32_t updated=0;
  static uint8_t row=0;
  static uint8_t portalStatus=0;
  static bool wasPortal=false;
  if (wifiPortalActive()) {
    uint8_t nextStatus=sensorFault ? 2 : activeAlarmFlags() ? 1 : 0;
    if (!wasPortal) {
      drawConnectionSetup(); portalStatus=nextStatus;
    } else if (portalStatus!=nextStatus) {
      // Setup details are static. Redraw only this status band so the portal
      // cannot repeatedly delay the one-second reporting/storage interval.
      screen.fillRect(10,230,220,22,UI_BG);
      tftText(10,235,nextStatus==2 ? "CHECK SENSORS" : nextStatus==1 ? "THRESHOLD ALARM" : "Sensors running",1,UI_GOLD);
      portalStatus=nextStatus;
    }
    wasPortal=true; return;
  }
  if (wasPortal) {drawDashboardFrame(); wasPortal=false;}
  if (millis()-updated<60) return;
  updated=millis();
  Measurement result=measurement.get(millis());
  LiveVitals live=selectLiveVitals(millis(),lastSample,finger,hrValid,heartRate,spo2Valid,spo2,goodTemp,objectC,result);
  HeartAverage average=heartAverage.get(millis());
  live=displayHeartAverage(live,average);
  MonitorIndicator indicator=selectMonitorIndicator(live,average.ready,sensorFault,activeAlarmFlags(),alarmLimits);
  const unsigned alarms=activeAlarmFlags();
  char text[48];
  // Clear just one value band per loop: no recurring full-screen redraws.
  switch (row) {
    case 0:
      screen.fillRect(10,32,220,18,UI_BG);
      tftText(10,38,rtcOK ? dateLabel : "RTC UNSET",1,UI_MUTED);
      tftText(132,32,rtcOK ? timeLabel : "--:--:--",2,UI_WHITE);
      break;
    case 1:
      screen.fillRect(64,84,112,25,UI_PANEL);
      if (live.heartAvailable) snprintf(text,sizeof(text),"%d",(int)lroundf(live.heart));
      else snprintf(text,sizeof(text),"--");
      tftText(64,84,text,3,UI_WHITE); break;
    case 2:
      screen.fillRect(20,151,66,25,UI_PANEL);
      if (live.oxygenAvailable) snprintf(text,sizeof(text),"%d",(int)lroundf(live.oxygen));
      else snprintf(text,sizeof(text),"--");
      tftText(20,151,text,3,UI_WHITE); break;
    case 3:
      screen.fillRect(126,151,89,25,UI_PANEL);
      if (goodTemp) snprintf(text,sizeof(text),"%.1f",objectC);
      else snprintf(text,sizeof(text),"--");
      tftText(126,151,text,3,UI_WHITE); break;
    case 4:
      screen.fillRect(10,194,220,16,UI_BG);
      if (goodTemp) snprintf(text,sizeof(text),"Ambient %.1f C | check %u/60s",ambientC,measurement.elapsed(millis()));
      else snprintf(text,sizeof(text),"Temperature sensor unavailable");
      tftText(12,198,text,1,UI_MUTED); break;
    case 5: {
      screen.fillRect(10,216,220,20,UI_PANEL);
      const char *status=alarms&1 ? "ALARM: HR LOW" : alarms&2 ? "ALARM: HR HIGH" :
        alarms&4 ? "ALARM: SURFACE BELOW 32C" : alarms&8 ? "ALARM: SPO2 LOW" :
        sensorFault ? "CHECK SENSOR CONNECTIONS" : !finger ? "PLACE FINGER" :
        !average.ready ? "AVERAGING HR: HOLD STILL" :
        indicator==MonitorIndicator::Green ? (result.ready ? "VALUES IN RANGE" : "IN RANGE / ESTIMATE") :
        !live.heartAvailable || !live.oxygenAvailable || !live.temperatureAvailable ? "CHECK SIGNAL" : "CHECK LIMITS";
      tftText(15,222,status,1,indicator==MonitorIndicator::Red ? UI_RED : indicator==MonitorIndicator::Green ? UI_GREEN : UI_GOLD); break;
    }
    case 6:
      screen.fillRect(10,246,220,16,UI_BG);
      if (sdOK) snprintf(text,sizeof(text),"SD recording: %lu rows",(unsigned long)savedRows);
      else snprintf(text,sizeof(text),"SD error: %s",sdError);
      tftText(12,250,text,1,sdOK ? UI_GREEN : UI_GOLD); break;
    case 7:
      screen.fillRect(10,268,220,12,UI_BG);
      if (wifiOnline()) snprintf(text,sizeof(text),"WiFi %s",wifiAddress().c_str());
      else snprintf(text,sizeof(text),"%s",syncState);
      tftText(12,270,text,1,UI_MUTED); break;
  }
  row=(row+1)%8;
}

void displayStartupStep(const char *step) {
  Serial.printf("NEOGUARD ST7789: %s\n",step);
  if (displayOK) {
    screen.fillRect(8,68,224,22,UI_BG); tftText(10,72,step,1,UI_WHITE);
  }
}

void setup() {
  Serial.begin(115200);
#if ARDUINO_USB_CDC_ON_BOOT && ARDUINO_USB_MODE
  Serial.setTxBufferSize(2048); // Keep complete diagnostic replies without blocking SD.
#endif
#if ARDUINO_USB_CDC_ON_BOOT
  Serial.setTxTimeoutMs(0);
#endif
  pinMode(SD_CS,OUTPUT); digitalWrite(SD_CS,HIGH);
  pinMode(TFT_CS,OUTPUT); digitalWrite(TFT_CS,HIGH);
  if (SPI.begin(TFT_SCK,-1,TFT_MOSI,TFT_CS)) {
    screen.init(TFT_WIDTH,TFT_HEIGHT,SPI_MODE0); screen.setSPISpeed(1000000);
    screen.setRotation(0); screen.setTextWrap(false); displayOK=true;
    screen.fillScreen(UI_BG); tftText(10,24,"AKENA NEOGUARD",2,UI_CYAN);
  }
  delay(1500);  // Allow native USB serial to enumerate before startup messages.
  Serial.printf("NEOGUARD FULL FIRMWARE ST7789 - network=%d RST8 DC9 CS10 MOSI11 SCK12\n",NEOGUARD_ENABLE_NETWORK);
  pinMode(SD_CS, OUTPUT);
  digitalWrite(SD_CS, HIGH);
  displayStartupStep("Starting system");
  bootID = esp_random();
  pinMode(BUZZER, OUTPUT);
  pinMode(RED_LED, OUTPUT);
  pinMode(GREEN_LED, OUTPUT);
  pinMode(BLUE_LED, OUTPUT);
  setBuzzer(false);
  setRGB(false, false, true);
  displayStartupStep("2. LED / BUZZER READY");
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000);
  Wire.setTimeOut(50);
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
  rtc.Begin();
  rtc.SetIsWriteProtected(false);
  rtc.SetTrickleChargeSettings(DS1302Tcr_Disabled);  // CR2032 is not rechargeable.
  if (SET_RTC_TIME || (AUTO_SET_RTC_IF_INVALID && (!rtc.IsDateTimeValid() || !rtc.GetIsRunning()))) {
    rtc.SetDateTime(RtcDateTime(__DATE__, __TIME__));
    rtc.SetIsRunning(true);
    Serial.println("RTC set from compilation time. Computer clock must use Nairobi time.");
  }
  refreshClock();
  if (rtcOK) {
    timeval systemTime = { (time_t)(rtc.GetDateTime().TotalSeconds() + 946684800UL - 10800UL), 0 };
    settimeofday(&systemTime, nullptr);
  }
  Serial.println("Commands: STATUS, WIFI SETUP, TIME?, TIME YYYY-MM-DD HH:MM:SS (Nairobi UTC+03:00).");
  Serial.println("Use sync_rtc.ps1 after upload to set current time accurately.");
  displayStartupStep("6. TEMP / CLOCK CHECKED");
  pulseOK = pulse.begin(Wire, I2C_SPEED_STANDARD);
  if (pulseOK) {
    pulse.setup(0x1F, 4, 2, 100, 411, 4096);  // Tested amplitude; effective FIFO rate 25 Hz.
    pulse.clearFIFO();
  }
  Wire.setClock(100000);
  displayStartupStep(pulseOK ? "7. PULSE SENSOR READY" : "7. PULSE SENSOR MISSING");
  displayStartupStep(NEOGUARD_ENABLE_NETWORK ? "8. STARTING TASKS / WIFI" : "8. STARTING OFFLINE MONITOR");
  beginPulseSampling();
  beginOfflineSync();
  drawDashboardFrame();
  drawDisplay();
  Serial.printf("MLX=%d MAX=%d SD=%d display_init=%d\n", tempOK, pulseOK, sdOK, displayOK);
  if (!ENABLE_SD_LOGGING) Serial.println("SD logging disabled: system runs without a card.");
  setBuzzer(true);
  bootBeeping = true;
  bootBeepStart = millis();
}

void updateOutputs() {
  bool sound = bootBeeping && millis() - bootBeepStart < 150;
  if (millis() - bootBeepStart >= 150) bootBeeping = false;
  if (manualBeepUntil && (int32_t)(millis()-manualBeepUntil)>=0) manualBeepUntil=0;
  sound = sound || manualBeepUntil;
  sound = sound || (activeAlarmFlags() && millis() % 500 < 250) || (sensorFault && millis() % 2000 < 250);
  setBuzzer(sound);
  LiveVitals live=selectLiveVitals(millis(),lastSample,finger,hrValid,heartRate,spo2Valid,spo2,goodTemp,objectC,measurement.get(millis()));
  HeartAverage average=heartAverage.get(millis());
  live=displayHeartAverage(live,average);
  MonitorIndicator light=selectMonitorIndicator(live,average.ready,sensorFault,activeAlarmFlags(),alarmLimits);
  setRGB(light==MonitorIndicator::Red,light==MonitorIndicator::Green,light==MonitorIndicator::Blue);
}

void loop() {
  updateOutputs();
  collectPulse();
  serviceSerial();
  serviceOfflineSync();
  collectPulse();
  if (millis() - lastReport < 1000) {drawDisplay(); delay(2); return;}
  lastReport = millis();
  objectC = readSurfaceTemperature(false);
  collectPulse();
  ambientC = readSurfaceTemperature(true);
  collectPulse();
  goodTemp = isfinite(objectC) && isfinite(ambientC) && objectC >= -70 && objectC <= 380 && ambientC >= -40 && ambientC <= 125;
  bool contact = finger && millis() - lastSample <= 2000;
  measurement.observe(millis(), contact, hrValid && spo2Valid && goodTemp,
                      heartRate, spo2, objectC);
  thresholdAlarm.observe(contact, hrValid, heartRate, spo2Valid, spo2, goodTemp, objectC, alarmLimits);
  sensorFault = !goodTemp || !pulseOK || (millis() - lastSample > 2000 && millis() - bootBeepStart > 2500);
  refreshClock();
  if (ENABLE_SD_LOGGING && !sdOK && !finger && millis() - lastSDRetry >= 10000) {
    lastSDRetry = millis();
    sdOK = initSD();
    if (sdOK) beginOfflineSync();
  }
  // Pulse acquisition continues in its own task during storage operations.
  collectPulse();
  logReading();
  if (millis() - lastQueuedMeasurement >= 5000) {
    lastQueuedMeasurement = millis();
    queueOfflineReading();
  }
  collectPulse();
  // Blue = acquiring, green = qualified signal, red = threshold alarm/fault.
  bool fault = sensorFault;
  if (fault) Serial.printf("SENSOR FAULT: temp_valid=%d MAX_detected=%d sample_age_ms=%lu\n",
                           goodTemp, pulseOK, (unsigned long)(millis() - lastSample));
  drawDisplay();
  updateOutputs();
}
