// ESP32-S3 offline bench test. Earlier ST7789 SPI screen, NOT SSD1306 OLED.
// No Wi-Fi, backend, patient data or clinical alarms.
#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>
#include <Adafruit_MLX90614.h>
#include <MAX30105.h>
#include <ThreeWire.h>
#include <RtcDS1302.h>
#include <math.h>

constexpr int SDA_PIN=4, SCL_PIN=5;
constexpr int TFT_RST=8, TFT_DC=9, TFT_CS=10, TFT_MOSI=11, TFT_SCK=12;
constexpr int RTC_CLK=6, RTC_DAT=7, RTC_CE=14;
constexpr int BUZZER=15, LED_R=16, LED_G=17, LED_B=18;
constexpr int SD_CS=21, SD_SCK=40, SD_MOSI=41, SD_MISO=42;
constexpr bool COMMON_ANODE=false, ACTIVE_BUZZER=true;
constexpr bool SET_RTC_FROM_BUILD=false; // Set true once, upload, then false/upload.

Adafruit_ST7789 screen(&SPI, TFT_CS, TFT_DC, TFT_RST);
SPIClass sdSPI(HSPI);
Adafruit_MLX90614 temperature;
MAX30105 pulse;
ThreeWire rtcWire(RTC_DAT, RTC_CLK, RTC_CE);
RtcDS1302<ThreeWire> rtc(rtcWire);
bool screenStarted=false, tempFound=false, pulseFound=false, sdMounted=false;
String sdResult="not tested", command;
float objectC=NAN, ambientC=NAN;
uint32_t ir=0, red=0, lastSample=0, lastReport=0, lastTemp=0;
bool haveSample=false;

void rgb(bool r, bool g, bool b) {
  digitalWrite(LED_R, r != COMMON_ANODE);
  digitalWrite(LED_G, g != COMMON_ANODE);
  digitalWrite(LED_B, b != COMMON_ANODE);
}
void buzzerOff() {
  if (ACTIVE_BUZZER) digitalWrite(BUZZER, LOW);
  else noTone(BUZZER);
}
void testBuzzer() {
  Serial.println("BUZZER: listen for a short beep.");
  if (ACTIVE_BUZZER) digitalWrite(BUZZER, HIGH);
  else tone(BUZZER, 2000);
  delay(180); buzzerOff();
}
void testRGB() {
  Serial.println("RGB: watch RED, GREEN, BLUE, then OFF.");
  rgb(true,false,false); delay(600);
  rgb(false,true,false); delay(600);
  rgb(false,false,true); delay(600);
  rgb(false,false,false);
}
void scanI2C() {
  Serial.println("I2C scan: expect MLX90614=0x5A and MAX30102=0x57.");
  unsigned count=0;
  for (uint8_t addr=1; addr<127; ++addr) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission()==0) { Serial.printf("  0x%02X\n", addr); ++count; }
  }
  Serial.printf("I2C: %u responding address(es). RTC is not an I2C device.\n",count);
}
void testScreen() {
  if (!screenStarted) return;
  Serial.println("SCREEN: watch RED, GREEN, BLUE, then text. No display readback.");
  screen.fillScreen(ST77XX_RED); delay(600);
  screen.fillScreen(ST77XX_GREEN); delay(600);
  screen.fillScreen(ST77XX_BLUE); delay(600);
  screen.fillScreen(ST77XX_BLACK);
}
void testSD() {
  if (!sdMounted) sdMounted=SD.begin(SD_CS, sdSPI, 1000000);
  if (!sdMounted || SD.cardType()==CARD_NONE) {
    sdMounted=false; sdResult="mount FAILED"; Serial.println("SD: mount FAILED"); return;
  }
  // Choose an unused filename; never overwrite an existing file or format the card.
  char path[20]; bool freeName=false;
  for (unsigned n=0;n<1000;++n) {
    snprintf(path,sizeof(path),"/ngtest%03u.txt",n);
    if (!SD.exists(path)) { freeName=true; break; }
  }
  if (!freeName) { sdResult="no test filename"; return; }
  const char payload[]="NeoGuard offline SD test\n";
  File out=SD.open(path,FILE_WRITE);
  if (!out) { sdResult="open FAILED"; Serial.println("SD: open FAILED"); return; }
  size_t written=out.write((const uint8_t*)payload,sizeof(payload)-1); out.close();
  File in=SD.open(path,FILE_READ);
  char actual[sizeof(payload)]={0};
  size_t received=in ? in.readBytes(actual,sizeof(payload)-1) : 0;
  if (in) in.close();
  bool ok=written==sizeof(payload)-1 && received==sizeof(payload)-1 &&
          memcmp(actual,payload,sizeof(payload)-1)==0;
  if (ok) sdResult=SD.remove(path) ? "write/read PASS" : "PASS; cleanup failed";
  else sdResult="write/read FAILED"; // Retain failed file for inspection.
  Serial.printf("SD: %s (%s)\n",sdResult.c_str(),path);
}
String clockText() {
  RtcDateTime now=rtc.GetDateTime();
  if (!now.IsValid()) return "unset / check wiring";
  if (!rtc.GetIsRunning()) return "clock STOPPED";
  char text[24];
  snprintf(text,sizeof(text),"%04u-%02u-%02u %02u:%02u:%02u",
    now.Year(),now.Month(),now.Day(),now.Hour(),now.Minute(),now.Second());
  return String(text);
}
void help() {
  Serial.println("Commands (newline): HELP, I2C, RGB, BUZZ, SCREEN, SD, RTC");
  Serial.println("Raw MAX readings test sensor activity; HR/SpO2 are not calculated.");
}
void runCommand(String text) {
  text.trim(); text.toUpperCase();
  if (text=="RGB") testRGB();
  else if (text=="BUZZ") testBuzzer();
  else if (text=="SCREEN") testScreen();
  else if (text=="SD") testSD();
  else if (text=="I2C") scanI2C();
  else if (text=="RTC") Serial.println("RTC: "+clockText());
  else if (text.length()) help();
  // Long manual tests interrupt FIFO servicing; discard pre-test samples.
  if (pulseFound) { pulse.clearFIFO(); haveSample=false; }
}
void report() {
  bool fresh=haveSample && millis()-lastSample<2000;
  String clock=clockText();
  Serial.printf("MLX: %s object=%.2f C ambient=%.2f C | MAX: %s IR=%lu RED=%lu | RTC: %s | SD: %s\n",
    !tempFound ? "NOT FOUND" : (isfinite(objectC)&&isfinite(ambientC) ? "read" : "READ ERROR"),
    objectC,ambientC,!pulseFound ? "NOT FOUND" : (fresh ? "sampling" : "NO FRESH SAMPLES"),
    (unsigned long)ir,(unsigned long)red,clock.c_str(),sdResult.c_str());
  if (!screenStarted) return;
  screen.fillScreen(ST77XX_BLACK);
  screen.setTextSize(2); screen.setTextColor(ST77XX_CYAN);
  screen.setCursor(6,8); screen.println("NEOGUARD OFFLINE");
  screen.setTextSize(1); screen.setTextColor(ST77XX_WHITE);
  screen.setCursor(6,42); screen.println("MLX90614 surface temperature");
  screen.setCursor(6,58);
  if (!tempFound) screen.print("NOT FOUND");
  else if (!isfinite(objectC)||!isfinite(ambientC)) screen.print("READ ERROR");
  else screen.printf("Object %.2f C / Air %.2f C",objectC,ambientC);
  screen.setCursor(6,86); screen.print("MAX30102: ");
  screen.print(!pulseFound ? "NOT FOUND" : (fresh ? "sampling" : "NO FRESH DATA"));
  screen.setCursor(6,102); screen.printf("IR %lu / RED %lu",(unsigned long)ir,(unsigned long)red);
  screen.setCursor(6,118); screen.print("Hold finger still; compare raw values");
  screen.setCursor(6,146); screen.print("RTC:");
  screen.setCursor(6,162); screen.print(clock);
  screen.setCursor(6,190); screen.print("SD: "); screen.print(sdResult);
  screen.setCursor(6,218); screen.print("Serial 115200: HELP");
  screen.setCursor(6,234); screen.printf("Uptime: %lu seconds",(unsigned long)(millis()/1000));
  screen.setCursor(6,254); screen.print("Bench test; no clinical interpretation");
}
void setup() {
  Serial.begin(115200); // Do not wait for a connected computer.
  pinMode(BUZZER,OUTPUT); buzzerOff();
  pinMode(LED_R,OUTPUT); pinMode(LED_G,OUTPUT); pinMode(LED_B,OUTPUT); rgb(false,false,false);
  pinMode(SD_CS,OUTPUT); digitalWrite(SD_CS,HIGH);
  pinMode(TFT_CS,OUTPUT); digitalWrite(TFT_CS,HIGH);
  delay(1200);
  Serial.println("NEOGUARD OFFLINE COMPONENT TEST / ST7789 240x280");
  if (SPI.begin(TFT_SCK,-1,TFT_MOSI,TFT_CS)) {
    screen.init(240,280,SPI_MODE0); screen.setSPISpeed(1000000);
    screen.setRotation(0); screen.setTextWrap(false); screenStarted=true;
    testScreen();
  } else Serial.println("SCREEN SPI BUS FAILED");
  testRGB(); testBuzzer();
  Wire.begin(SDA_PIN,SCL_PIN); Wire.setClock(100000); Wire.setTimeOut(50);
  scanI2C();
  tempFound=temperature.begin(0x5A,&Wire);
  rtc.Begin(); rtc.SetTrickleChargeSettings(DS1302Tcr_Disabled);
  if (SET_RTC_FROM_BUILD) {
    rtc.SetIsWriteProtected(false); rtc.SetDateTime(RtcDateTime(__DATE__,__TIME__));
    rtc.SetIsRunning(true);
  }
  sdSPI.begin(SD_SCK,SD_MISO,SD_MOSI,SD_CS); testSD();
  pulseFound=pulse.begin(Wire,I2C_SPEED_STANDARD);
  if (pulseFound) {
    pulse.setup(0x1F,4,2,100,411,4096); // Red+IR; 25 averaged samples/second.
    pulse.setPulseAmplitudeGreen(0); pulse.clearFIFO();
  }
  help(); report();
}
void loop() {
  while (Serial.available()) {
    char c=(char)Serial.read();
    if (c=='\n'||c=='\r') { if(command.length()) {runCommand(command); command="";} }
    else if(command.length()<48) command+=c;
  }
  if (pulseFound) {
    pulse.check();
    while (pulse.available()) {
      ir=pulse.getFIFOIR(); red=pulse.getFIFORed(); pulse.nextSample();
      lastSample=millis(); haveSample=true;
    }
  }
  if (millis()-lastTemp>=1000) {
    lastTemp=millis();
    if (tempFound) { objectC=temperature.readObjectTempC(); ambientC=temperature.readAmbientTempC(); }
  }
  if (millis()-lastReport>=2000) {lastReport=millis(); report();}
  delay(2);
}
