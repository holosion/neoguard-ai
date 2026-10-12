#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7789.h>

constexpr int TFT_MOSI = 11;
constexpr int TFT_SCLK = 12;
constexpr int TFT_CS = 10;
constexpr int TFT_DC = 9;
constexpr int TFT_RST = 8;

// Connect the module's backlight input to 3V3 as specified for your module.
Adafruit_ST7789 tft(&SPI, TFT_CS, TFT_DC, TFT_RST);

void setup() {
  SPI.begin(TFT_SCLK, -1, TFT_MOSI, TFT_CS);
  tft.init(240, 280);
  tft.setSPISpeed(10000000);
  tft.setRotation(0);
  tft.fillScreen(ST77XX_BLACK);
  tft.setTextWrap(false);
  tft.setTextColor(ST77XX_WHITE);
  tft.setTextSize(2);
  tft.setCursor(24, 110);
  tft.println("Hello, ESP32-S3!");
  tft.setTextColor(ST77XX_GREEN);
  tft.setCursor(24, 150);
  tft.println("Display ready");
}

void loop() {
  // The message stays on screen without needing to redraw it.
}
