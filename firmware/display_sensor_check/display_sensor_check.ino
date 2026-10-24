// Offline ESP32-S3 bench check: earlier ST7789 240x280 + MLX90614 + MAX30102.
// No Wi-Fi. ST7789 is an SPI TFT, not an SSD1306/SH1106 OLED.
#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <Adafruit_MLX90614.h>
#include <MAX30105.h>
#include <spo2_algorithm.h>
#include <freertos/FreeRTOS.h>
#include <freertos/semphr.h>
#include <freertos/queue.h>
#include <math.h>

constexpr int SDA_PIN=4, SCL_PIN=5;
constexpr int TFT_RST=8, TFT_DC=9, TFT_CS=10, TFT_MOSI=11, TFT_SCK=12;
constexpr int BUZZER_PIN=15, UNUSED_SD_CS=21;
constexpr bool ACTIVE_BUZZER=true, BUZZER_ACTIVE_LOW=false;
constexpr uint32_t CONTACT_ON_IR=50000, CONTACT_OFF_IR=40000; // Bench tuning only.
constexpr float WARM_TARGET_ON_C=1.5f, WARM_TARGET_OFF_C=0.7f;

Adafruit_ST7789 display(&SPI,TFT_CS,TFT_DC,TFT_RST);
Adafruit_MLX90614 mlx;
MAX30105 oximeter;
SemaphoreHandle_t i2cMutex=nullptr;
QueueHandle_t pulseQueue=nullptr;
bool displayStarted=false, mlxFound=false, maxFound=false;
bool buzzerRunning=false, previousContact=false, warmTarget=false;
uint32_t buzzerUntil=0, warmSince=0, lastTemp=0, lastLog=0, lastDraw=0, validTempAt=0;
uint32_t displayTests=0;
float objectC=NAN, ambientC=NAN;
String serialLine, lastEvent="Ready: D / T / O / B";

struct PulseData {
  uint32_t ir=0, red=0, sampledAt=0;
  int32_t bpm=0, spo2=0;
  bool contact=false, bpmValid=false, spo2Valid=false, sampled=false;
  unsigned windowSamples=0;
};
PulseData latest;

void scanSensors() {
  if (i2cMutex && xSemaphoreTake(i2cMutex,pdMS_TO_TICKS(500))!=pdTRUE) {
    Serial.println("I2C: bus busy; try S again."); return;
  }
  Serial.printf("I2C GPIO4 SDA=%d, GPIO5 SCL=%d (idle normally HIGH).\n",digitalRead(SDA_PIN),digitalRead(SCL_PIN));
  Serial.println("I2C scan: expect MLX90614 0x5A and MAX30102 0x57.");
  unsigned found=0, busErrors=0;
  for (uint8_t address=1; address<127; ++address) {
    Wire.beginTransmission(address);
    uint8_t result=Wire.endTransmission();
    if (result==0) {Serial.printf("I2C ACK 0x%02X\n",address); ++found;}
    else if (result!=2) ++busErrors;
  }
  Serial.printf("I2C result: %u responding address(es), %u bus error(s).\n",found,busErrors);
  if (i2cMutex) xSemaphoreGive(i2cMutex);
}

void serviceBuzzer() {
  if (buzzerRunning && (int32_t)(millis()-buzzerUntil)>=0) {
    if (ACTIVE_BUZZER) digitalWrite(BUZZER_PIN,BUZZER_ACTIVE_LOW ? HIGH : LOW);
    else noTone(BUZZER_PIN);
    buzzerRunning=false;
  }
}
void interaction(const String &message) {
  lastEvent=message;
  Serial.println("EVENT: "+message);
  if (ACTIVE_BUZZER) digitalWrite(BUZZER_PIN,BUZZER_ACTIVE_LOW ? LOW : HIGH);
  else tone(BUZZER_PIN,2000);
  buzzerUntil=millis()+90;
  buzzerRunning=true;
}

// Acquisition has priority over drawing. The library's software FIFO holds only
// four samples, so it must be drained frequently even while the screen updates.
void sampleOximeter(void *) {
  uint32_t irWindow[100]={}, redWindow[100]={};
  unsigned count=0, added=0, presentCount=0, absentCount=0;
  uint32_t servicedAt=millis();
  PulseData state;
  for (;;) {
    if (xSemaphoreTake(i2cMutex,pdMS_TO_TICKS(10))==pdTRUE) {
      uint32_t now=millis();
      if (now-servicedAt>=120) {
        oximeter.clearFIFO(); count=added=presentCount=absentCount=0;
        state.contact=state.bpmValid=state.spo2Valid=false;
      }
      servicedAt=now;
      oximeter.check();
      while (oximeter.available()) {
        state.ir=oximeter.getFIFOIR(); state.red=oximeter.getFIFORed();
        oximeter.nextSample(); state.sampledAt=millis(); state.sampled=true;
        bool saturated=state.ir>=262000 || state.red>=262000;
        if (!state.contact) {
          presentCount=(state.ir>=CONTACT_ON_IR && !saturated) ? presentCount+1 : 0;
          if (presentCount>=8) {state.contact=true; absentCount=0;}
        } else {
          absentCount=(state.ir<CONTACT_OFF_IR || saturated) ? absentCount+1 : 0;
          if (absentCount>=4) {state.contact=false; presentCount=0;}
        }
        if (!state.contact || saturated || state.ir<CONTACT_OFF_IR) {
          count=added=0; state.bpmValid=state.spo2Valid=false;
          continue;
        }
        if (count<100) {
          irWindow[count]=state.ir; redWindow[count++]=state.red;
          if (count==100) added=25;
        } else {
          memmove(irWindow,irWindow+1,99*sizeof(uint32_t));
          memmove(redWindow,redWindow+1,99*sizeof(uint32_t));
          irWindow[99]=state.ir; redWindow[99]=state.red; ++added;
        }
        if (count==100 && added>=25) {
          int8_t validBpm=0,validSpo2=0;
          maxim_heart_rate_and_oxygen_saturation(irWindow,100,redWindow,
            &state.spo2,&validSpo2,&state.bpm,&validBpm);
          state.bpmValid=validBpm && state.bpm>0 && state.bpm<=250;
          state.spo2Valid=validSpo2 && state.spo2>0 && state.spo2<=100;
          added=0;
        }
      }
      state.windowSamples=count;
      xSemaphoreGive(i2cMutex);
      if (!state.sampled || millis()-state.sampledAt>2000) {
        state.contact=state.bpmValid=state.spo2Valid=false;
        count=added=presentCount=absentCount=0; state.windowSamples=0;
      }
      xQueueOverwrite(pulseQueue,&state);
    }
    vTaskDelay(pdMS_TO_TICKS(5));
  }
}

bool freshPulse() {return maxFound && latest.sampled && millis()-latest.sampledAt<2000;}
bool freshTemperature() {return mlxFound && validTempAt && millis()-validTempAt<2000;}
void collectPulse() {
  if (pulseQueue) xQueueReceive(pulseQueue,&latest,0);
  bool contact=freshPulse() && latest.contact;
  if (contact && !previousContact) interaction("Oximeter: finger detected");
  previousContact=contact;
}
void readTemperature() {
  if (!mlxFound || !i2cMutex || xSemaphoreTake(i2cMutex,pdMS_TO_TICKS(30))!=pdTRUE) return;
  objectC=mlx.readObjectTempC(); ambientC=mlx.readAmbientTempC();
  xSemaphoreGive(i2cMutex);
  if (!isfinite(objectC)||!isfinite(ambientC)) {warmSince=0; warmTarget=false; validTempAt=0; return;}
  validTempAt=millis();
  // A warm target is an approximation of interaction, not a proximity detector.
  float difference=objectC-ambientC;
  if (difference>=WARM_TARGET_ON_C) {
    if (!warmSince) warmSince=millis();
    if (!warmTarget && millis()-warmSince>=600) {
      warmTarget=true; interaction("Temperature: warm target");
    }
  } else {
    warmSince=0;
    if (difference<=WARM_TARGET_OFF_C) warmTarget=false;
  }
}
void drawRow(uint8_t row) {
  if (!displayStarted) return;
  int y=65+row*23;
  display.fillRect(6,y,228,17,ST77XX_BLACK);
  display.setTextSize(1); display.setTextColor(ST77XX_WHITE); display.setCursor(6,y+3);
  switch(row) {
    case 0:
      if (!mlxFound) display.print("MLX90614: NOT FOUND (0x5A)");
      else if (!freshTemperature()) display.print("Object: read error / stale");
      else display.printf("Object/surface: %.2f C",objectC);
      break;
    case 1:
      if (!freshTemperature()) display.print("Ambient: --");
      else display.printf("Ambient: %.2f C",ambientC);
      break;
    case 2:
      if (!maxFound) display.print("MAX30102: NOT FOUND (0x57)");
      else if (!freshPulse()) display.print("MAX30102: waiting / no fresh data");
      else display.print(latest.contact ? "Finger detected: hold still" : "MAX30102: place finger");
      break;
    case 3:
      if (freshPulse() && latest.contact && latest.bpmValid) display.printf("Heart rate estimate: %ld bpm",(long)latest.bpm);
      else display.printf("Heart rate: -- (window %u/100)",latest.windowSamples);
      break;
    case 4:
      if (freshPulse() && latest.contact && latest.spo2Valid) display.printf("SpO2 estimate: %ld %%",(long)latest.spo2);
      else display.print("SpO2: -- / waiting for valid signal");
      break;
    case 5:
      if (!freshPulse()) display.print("Raw IR / red: --");
      else display.printf("IR %lu / RED %lu",(unsigned long)latest.ir,(unsigned long)latest.red);
      break;
    case 6: display.print(lastEvent.substring(0,37)); break;
    case 7: display.printf("Screen tests %lu | uptime %lu s",(unsigned long)displayTests,(unsigned long)(millis()/1000)); break;
  }
  serviceBuzzer();
}
void screenInteraction() {
  interaction("Display test: check colour bars"); ++displayTests;
  if (!displayStarted) {Serial.println("Display SPI initialization failed."); return;}
  display.fillRect(6,40,72,12,ST77XX_RED); serviceBuzzer();
  display.fillRect(84,40,72,12,ST77XX_GREEN); serviceBuzzer();
  display.fillRect(162,40,72,12,ST77XX_BLUE); serviceBuzzer();
  Serial.println("Confirm red/green/blue bars, readable text and advancing uptime. No display readback.");
}
void help() {
  Serial.println("Newline commands: D/SCREEN; T/TEMP; O/OXI; B/BUZZ; S/SCAN; HELP.");
  Serial.println("D checks screen bars. T reports current surface temperature. O reports sensor state.");
  Serial.println("Finger placement and a new warm target trigger automatic beeps; remove to re-arm.");
}
void logReadings() {
  Serial.printf("MLX=%s surface=%.2f C ambient=%.2f C | MAX=%s finger=%d IR=%lu red=%lu window=%u/100 | ",
    !mlxFound ? "MISSING" : (freshTemperature() ? "reading" : "READ ERROR/STALE"),
    freshTemperature() ? objectC : NAN,freshTemperature() ? ambientC : NAN,
    !maxFound ? "MISSING" : (freshPulse() ? "sampling" : "NO FRESH DATA"),
    freshPulse()&&latest.contact,(unsigned long)latest.ir,(unsigned long)latest.red,latest.windowSamples);
  if (freshPulse()&&latest.contact&&latest.bpmValid) Serial.printf("HR=%ld bpm | ",(long)latest.bpm);
  else Serial.print("HR=-- | ");
  if (freshPulse()&&latest.contact&&latest.spo2Valid) Serial.printf("SpO2=%ld %%\n",(long)latest.spo2);
  else Serial.println("SpO2=--");
}
void command(String text) {
  text.trim(); text.toUpperCase();
  if (text=="D"||text=="SCREEN") screenInteraction();
  else if (text=="T"||text=="TEMP") {interaction("Temperature test requested"); logReadings();}
  else if (text=="O"||text=="OXI") {interaction("Oximeter test requested"); logReadings();}
  else if (text=="B"||text=="BUZZ") interaction("Buzzer test requested");
  else if (text=="S"||text=="SCAN") scanSensors();
  else if (text.length()) help();
}
void setup() {
  Serial.begin(115200);
  pinMode(BUZZER_PIN,OUTPUT); digitalWrite(BUZZER_PIN,BUZZER_ACTIVE_LOW ? HIGH : LOW);
  pinMode(UNUSED_SD_CS,OUTPUT); digitalWrite(UNUSED_SD_CS,HIGH);
  pinMode(TFT_CS,OUTPUT); digitalWrite(TFT_CS,HIGH);
  delay(1000);
  Serial.println("NEOGUARD DISPLAY/SENSOR CHECK -- OFFLINE -- ST7789 240x280");
  if (SPI.begin(TFT_SCK,-1,TFT_MOSI,TFT_CS)) {
    display.init(240,280,SPI_MODE0); display.setSPISpeed(1000000); display.setRotation(0);
    display.setTextWrap(false); displayStarted=true;
    // Initial full-screen test runs before acquisition starts.
    display.fillScreen(ST77XX_RED); delay(300);
    display.fillScreen(ST77XX_GREEN); delay(300);
    display.fillScreen(ST77XX_BLUE); delay(300);
    display.fillScreen(ST77XX_BLACK);
    display.setTextColor(ST77XX_CYAN); display.setTextSize(2); display.setCursor(6,8); display.print("SENSOR CHECK");
    display.setTextSize(1); display.setTextColor(ST77XX_WHITE);
    display.setCursor(6,29); display.print("ST7789 / ESP32-S3 / NO WI-FI");
    display.setCursor(6,255); display.print("Serial 115200: D / T / O / B");
    display.setCursor(6,269); display.print("Bench estimates; not medical results");
  } else Serial.println("ERROR: screen SPI bus failed; serial tests continue.");
  Wire.begin(SDA_PIN,SCL_PIN); Wire.setClock(100000); Wire.setTimeOut(50);
  scanSensors();
  mlxFound=mlx.begin(0x5A,&Wire);
  maxFound=oximeter.begin(Wire,I2C_SPEED_STANDARD);
  i2cMutex=xSemaphoreCreateMutex();
  if (!i2cMutex) {Serial.println("ERROR: no I2C mutex; acquisition disabled."); mlxFound=maxFound=false;}
  if (maxFound) {
    oximeter.setup(0x1F,4,2,100,411,4096); // 100 Hz / four-sample average = 25 Hz.
    oximeter.setPulseAmplitudeGreen(0); oximeter.clearFIFO();
    pulseQueue=xQueueCreate(1,sizeof(PulseData));
    if (!pulseQueue || xTaskCreatePinnedToCore(sampleOximeter,"oxi",8192,nullptr,2,nullptr,1)!=pdPASS) {
      maxFound=false; Serial.println("ERROR: oximeter sampler could not start.");
    }
  }
  Serial.printf("MLX90614=%s; MAX30102=%s\n",mlxFound ? "found" : "NOT FOUND",maxFound ? "found" : "NOT FOUND");
  screenInteraction(); help(); readTemperature();
}
void loop() {
  serviceBuzzer(); collectPulse();
  if (!freshTemperature()) {warmTarget=false; warmSince=0;}
  while (Serial.available()) {
    char c=(char)Serial.read();
    if (c=='\n'||c=='\r') {if (serialLine.length()) {command(serialLine); serialLine="";}}
    else if (serialLine.length()<40) serialLine+=c;
  }
  uint32_t now=millis();
  if (now-lastTemp>=300) {lastTemp=now; readTemperature();}
  if (now-lastLog>=1000) {lastLog=now; logReadings();}
  // One small row per update keeps interactions and buzzer timing responsive.
  if (now-lastDraw>=90) {
    static uint8_t row=0;
    lastDraw=now; drawRow(row); row=(row+1)%8;
  }
  serviceBuzzer(); delay(2);
}
