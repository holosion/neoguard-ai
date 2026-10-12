#include <LiquidCrystal.h>

// LCD pins: RS, Enable, D4, D5, D6, D7.
// Connect LCD RW (pin 5) permanently to GND.
LiquidCrystal lcd(8, 9, 10, 11, 12, 13);

unsigned long lastUpdate = 0;
unsigned long seconds = 0;

void setup() {
  delay(100);  // Allow LCD power to settle.
  lcd.begin(16, 2);
  lcd.setCursor(0, 0);
  lcd.print("NeoGuard LCD OK");
  lcd.setCursor(0, 1);
  lcd.print("Seconds: 0");
  lastUpdate = millis();
}

void loop() {
  if (millis() - lastUpdate >= 1000) {
    lastUpdate += 1000;
    seconds++;
    lcd.setCursor(0, 1);
    lcd.print("                ");
    lcd.setCursor(0, 1);
    lcd.print("Seconds: ");
    lcd.print(seconds);
  }
}
