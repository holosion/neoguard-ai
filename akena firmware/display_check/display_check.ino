// Screen-only diagnosis for the previously working NeoGuard ST7789 display.
// Uploading this temporarily replaces the monitor firmware. No sensors, SD or Wi-Fi.
#include <Arduino.h>
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>

constexpr int DISPLAY_CS = 10, DISPLAY_DC = 9, DISPLAY_RST = 8;
constexpr int DISPLAY_MOSI = 11, DISPLAY_SCK = 12;
Adafruit_ST7789 display(&SPI, DISPLAY_CS, DISPLAY_DC, DISPLAY_RST);
uint32_t lastUpdate = 0, counter = 0;
bool busReady = false;

void setup() {
  Serial.begin(115200);
  delay(1500);
  Serial.println("NEOGUARD SCREEN-ONLY TEST v1 - no Wi-Fi, SD or sensors");
  Serial.println("ST7789 240x280 MODE0: MOSI11 SCK12 CS10 DC9 RST8");
  // Deselect the attached SD module without starting its SPI bus.
  pinMode(21, OUTPUT); digitalWrite(21, HIGH);
  pinMode(DISPLAY_CS, OUTPUT); digitalWrite(DISPLAY_CS, HIGH);
  if (!SPI.begin(DISPLAY_SCK, -1, DISPLAY_MOSI, DISPLAY_CS)) {
    Serial.println("DISPLAY TEST: ESP32 SPI bus could not start.");
    return;
  }
  display.init(240, 280, SPI_MODE0);
  busReady = true;
  display.setSPISpeed(1000000);
  display.setRotation(0);
  display.setTextWrap(false);
  Serial.println("Watch screen: RED, GREEN, BLUE, then WHITE with BLACK text.");
  display.fillScreen(ST77XX_RED); delay(1500);
  display.fillScreen(ST77XX_GREEN); delay(1500);
  display.fillScreen(ST77XX_BLUE); delay(1500);
  display.fillScreen(ST77XX_WHITE);
  display.setTextColor(ST77XX_BLACK);
  display.setTextSize(2);
  display.setCursor(10, 24); display.print("NEOGUARD");
  display.setCursor(10, 50); display.print("SCREEN TEST");
  display.setTextSize(1);
  display.setCursor(10, 86); display.print("ST7789 / SPI MODE 0");
  display.setCursor(10, 104); display.print("MOSI11 SCK12 CS10");
  display.setCursor(10, 122); display.print("DC9 RST8");
  display.setCursor(10, 158); display.print("Text visible? Screen responds.");
  Serial.println("Drawing commands sent. This SPI screen has no readback confirmation.");
  Serial.println("If blank, report screen pin labels and actual ESP32 connections.");
}

void loop() {
  if (!busReady) { delay(100); return; }
  if (millis() - lastUpdate < 1000) return;
  lastUpdate = millis();
  display.fillRect(10, 190, 200, 20, ST77XX_WHITE);
  display.setCursor(10, 192); display.setTextSize(2);
  display.print("Count "); display.print(++counter);
  Serial.printf("DISPLAY TEST tick %lu\n", (unsigned long)counter);
}
