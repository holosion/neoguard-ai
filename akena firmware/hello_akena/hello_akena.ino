// Screen-only sketch for the previously working ST7789 240x280 display.
#include <Arduino.h>
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>

constexpr int TFT_CS = 10;
constexpr int TFT_DC = 9;
constexpr int TFT_RST = 8;
constexpr int TFT_MOSI = 11;
constexpr int TFT_SCK = 12;

Adafruit_ST7789 screen(&SPI, TFT_CS, TFT_DC, TFT_RST);

void setup() {
  Serial.begin(115200);
  delay(1500);

  pinMode(TFT_CS, OUTPUT);
  digitalWrite(TFT_CS, HIGH);

  if (!SPI.begin(TFT_SCK, -1, TFT_MOSI, TFT_CS)) {
    Serial.println("Screen SPI bus could not start.");
    return;
  }

  screen.init(240, 280, SPI_MODE0);
  screen.setSPISpeed(1000000);
  screen.setRotation(0);
  screen.setTextWrap(false);
  screen.fillScreen(ST77XX_WHITE);
  screen.setTextColor(ST77XX_BLACK);
  screen.setTextSize(3);
  screen.setCursor(21, 128);
  screen.print("Hello Akena");

  Serial.println("Hello Akena drawing commands sent.");
}

void loop() {
  delay(100);
}
