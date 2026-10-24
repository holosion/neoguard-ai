// ESP32-S3 offline RGB + microSD bench test, with existing ST7789 status screen.
// Existing files are never overwritten. Formatting is explicitly disabled.
#include <Arduino.h>
#include <SPI.h>
#include <SD.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>

constexpr int RED_PIN=16, GREEN_PIN=17, BLUE_PIN=18;
constexpr bool COMMON_ANODE=false; // Existing design: common cathode to GND.
constexpr int SD_CS=21, SD_SCK=40, SD_MOSI=41, SD_MISO=42;
constexpr int TFT_RST=8, TFT_DC=9, TFT_CS=10, TFT_MOSI=11, TFT_SCK=12;
constexpr int BUZZER_PIN=15;
constexpr uint32_t SD_HZ=1000000;
Adafruit_ST7789 display(&SPI,TFT_CS,TFT_DC,TFT_RST);
SPIClass cardSPI(HSPI);
bool displayStarted=false, cycleEnabled=true, sdPassed=false;
uint8_t cycleStep=0;
uint32_t lastColourAt=0, lastStatusAt=0, testCount=0;
String serialLine, colour="OFF", sdStatus="not tested", detail="";

void drawStatus() {
  if (!displayStarted) return;
  display.fillRect(6,60,228,175,ST77XX_BLACK);
  display.setTextColor(ST77XX_WHITE); display.setTextSize(2);
  display.setCursor(6,65); display.print("RGB: "); display.print(colour);
  display.setTextSize(1);
  display.setCursor(6,98); display.print("Observe the separate RGB LED.");
  display.setCursor(6,116); display.print(cycleEnabled ? "Cycle: RED GREEN BLUE WHITE OFF" : "Manual colour selection");
  display.setCursor(6,145); display.print("SD: "); display.print(sdStatus);
  display.setCursor(6,165); display.print(detail.substring(0,37));
  display.setCursor(6,189); display.printf("SD attempts: %lu",(unsigned long)testCount);
  display.setCursor(6,211); display.printf("Uptime: %lu seconds",(unsigned long)(millis()/1000));
}
void setColour(bool red, bool green, bool blue, const char *label) {
  digitalWrite(RED_PIN,red != COMMON_ANODE);
  digitalWrite(GREEN_PIN,green != COMMON_ANODE);
  digitalWrite(BLUE_PIN,blue != COMMON_ANODE);
  colour=label;
  Serial.printf("RGB OUTPUT: %s (R16=%d G17=%d B18=%d); confirm visible colour.\n",label,
    red != COMMON_ANODE,green != COMMON_ANODE,blue != COMMON_ANODE);
  drawStatus();
}
void cycleColour() {
  switch (cycleStep) {
    case 0: setColour(true,false,false,"RED"); break;
    case 1: setColour(false,true,false,"GREEN"); break;
    case 2: setColour(false,false,true,"BLUE"); break;
    case 3: setColour(true,true,true,"WHITE"); break;
    default: setColour(false,false,false,"OFF"); break;
  }
  cycleStep=(cycleStep+1)%5; lastColourAt=millis();
}
void sdFailure(const char *stage, const String &info) {
  sdPassed=false; sdStatus=String("FAIL: ")+stage; detail=info;
  Serial.printf("SD FAIL: %s -- %s\n",stage,info.c_str()); drawStatus();
}
uint8_t expectedByte(size_t offset) {return (uint8_t)((offset*37U+testCount*11U)&0xFF);}
void testSD() {
  ++testCount; sdPassed=false; sdStatus="testing"; detail="No formatting"; drawStatus();
  Serial.printf("SD TEST #%lu: CS21 SCK40 MOSI41 MISO42, 1 MHz; format disabled.\n",(unsigned long)testCount);
  // Remount each time so a previous success is not mistaken for current presence.
  SD.end();
  if (!SD.begin(SD_CS,cardSPI,SD_HZ,"/sd",5,false)) {
    sdFailure("mount","Check card/power/wiring/FAT32"); return;
  }
  sdcard_type_t type=SD.cardType();
  if (type==CARD_NONE) {sdFailure("card","No card detected"); return;}
  const char *typeName=type==CARD_SDHC ? "SDHC/SDXC" : type==CARD_SD ? "SDSC" : "MMC/other";
  Serial.printf("SD CARD: %s, capacity %llu MiB, filesystem %llu MiB.\n",typeName,
    (unsigned long long)(SD.cardSize()/(1024*1024)),
    (unsigned long long)(SD.totalBytes()/(1024*1024)));
  char path[24]; bool available=false;
  for (unsigned n=0;n<1000;++n) {
    snprintf(path,sizeof(path),"/ngrtest%03u.tmp",n);
    if (!SD.exists(path)) {available=true; break;}
  }
  if (!available) {sdFailure("filename","All test filenames already exist"); return;}
  Serial.printf("SD FILE: %s (new temporary file)\n",path);
  uint8_t bytes[512];
  for (size_t i=0;i<512;++i) bytes[i]=expectedByte(i);
  File file=SD.open(path,FILE_WRITE);
  if (!file) {sdFailure("create",path); return;}
  size_t written=file.write(bytes,sizeof(bytes)); file.flush(); file.close();
  if (written!=sizeof(bytes)) {sdFailure("write",String(path)+" retained"); return;}
  file=SD.open(path,FILE_READ);
  if (!file) {sdFailure("read open",String(path)+" retained"); return;}
  bool ok=file.size()==512 && file.read(bytes,sizeof(bytes))==sizeof(bytes);
  file.close();
  for (size_t i=0;i<512 && ok;++i) ok=bytes[i]==expectedByte(i);
  if (!ok) {sdFailure("read compare",String(path)+" retained"); return;}
  Serial.println("SD PASS: create + write + close/reopen + compare 512 bytes.");
  for (size_t i=0;i<128;++i) bytes[i]=expectedByte(512+i);
  file=SD.open(path,FILE_APPEND);
  if (!file) {sdFailure("append open",String(path)+" retained"); return;}
  written=file.write(bytes,128); file.flush(); file.close();
  if (written!=128) {sdFailure("append",String(path)+" retained"); return;}
  file=SD.open(path,FILE_READ);
  if (!file) {sdFailure("verify open",String(path)+" retained"); return;}
  ok=file.size()==640;
  for (size_t i=0;i<640 && ok;++i) {
    int actual=file.read(); ok=actual>=0 && (uint8_t)actual==expectedByte(i);
  }
  file.close();
  if (!ok) {sdFailure("append compare",String(path)+" retained"); return;}
  Serial.println("SD PASS: append + reopen + compare all 640 bytes.");
  if (!SD.remove(path)) {sdFailure("cleanup",String(path)+" retained"); return;}
  if (SD.exists(path)) {sdFailure("cleanup verify",String(path)+" still exists"); return;}
  sdPassed=true; sdStatus="PASS"; detail="640 bytes verified; file removed";
  Serial.println("SD RESULT: PASS -- write/read/append/compare/delete; existing files preserved.");
  drawStatus();
}
void status() {
  Serial.printf("STATUS uptime=%lu s, RGB=%s, cycling=%d, SD_last_test=%s, attempts=%lu\n",
    (unsigned long)(millis()/1000),colour.c_str(),cycleEnabled,sdStatus.c_str(),(unsigned long)testCount);
  Serial.println("SD status is the last completed test; send SD to check again.");
}
void help() {
  Serial.println("Commands: CYCLE, RED, GREEN, BLUE, WHITE, OFF, SD, STATUS, HELP (newline).");
  Serial.println("RGB visibility requires observation. SD tests never format or overwrite existing files.");
}
void handleCommand(String text) {
  text.trim(); text.toUpperCase();
  if (text=="SD") {testSD(); lastColourAt=millis();}
  else if (text=="STATUS") status();
  else if (text=="CYCLE" || text=="RGB") {cycleEnabled=true; cycleStep=0; cycleColour();}
  else if (text=="RED") {cycleEnabled=false; setColour(true,false,false,"RED");}
  else if (text=="GREEN") {cycleEnabled=false; setColour(false,true,false,"GREEN");}
  else if (text=="BLUE") {cycleEnabled=false; setColour(false,false,true,"BLUE");}
  else if (text=="WHITE") {cycleEnabled=false; setColour(true,true,true,"WHITE");}
  else if (text=="OFF") {cycleEnabled=false; setColour(false,false,false,"OFF");}
  else if (text.length()) help();
}
void setup() {
  Serial.begin(115200);
  for (int pin : {RED_PIN,GREEN_PIN,BLUE_PIN}) {
    digitalWrite(pin,COMMON_ANODE ? HIGH : LOW); pinMode(pin,OUTPUT);
  }
  pinMode(BUZZER_PIN,OUTPUT); digitalWrite(BUZZER_PIN,LOW);
  pinMode(TFT_CS,OUTPUT); digitalWrite(TFT_CS,HIGH);
  pinMode(SD_CS,OUTPUT); digitalWrite(SD_CS,HIGH);
  delay(1000);
  Serial.println("NEOGUARD RGB + SD CHECK -- ESP32-S3 -- OFFLINE");
  Serial.println(COMMON_ANODE ? "RGB common anode: common to 3V3" : "RGB common cathode: common to GND");
  if (SPI.begin(TFT_SCK,-1,TFT_MOSI,TFT_CS)) {
    display.init(240,280,SPI_MODE0); display.setSPISpeed(1000000); display.setRotation(0);
    display.setTextWrap(false); displayStarted=true; display.fillScreen(ST77XX_BLACK);
    display.setTextColor(ST77XX_CYAN); display.setTextSize(2); display.setCursor(6,10); display.print("RGB + SD TEST");
    display.setTextSize(1); display.setTextColor(ST77XX_WHITE);
    display.setCursor(6,38); display.print("No Wi-Fi / existing wiring");
    display.setCursor(6,245); display.print("Serial 115200: CYCLE / SD / STATUS");
    display.setCursor(6,264); display.print("SD files preserved; no formatting");
  }
  if (cardSPI.begin(SD_SCK,SD_MISO,SD_MOSI,SD_CS)) testSD();
  else sdFailure("SPI init","Cannot start SD bus");
  help(); cycleColour(); status();
}
void loop() {
  while (Serial.available()) {
    char c=(char)Serial.read();
    if (c=='\n'||c=='\r') {if (serialLine.length()) {handleCommand(serialLine); serialLine="";}}
    else if (serialLine.length()<40) serialLine+=c;
  }
  if (cycleEnabled && millis()-lastColourAt>=1500) cycleColour();
  if (millis()-lastStatusAt>=10000) {lastStatusAt=millis(); status(); drawStatus();}
  delay(5);
}
