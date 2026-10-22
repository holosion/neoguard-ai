# Display assets

The original heart, thermometer, oxygen droplet, clock, and storage pictograms are provided as SVGs. `../display_icons.h` contains 16x16 and 32x32 bitmap versions stored in program flash. They are rendered directly by Adafruit GFX and need no image files on the SD card.

`display_preview.png` illustrates the layout at 3x scale. Its sample date, readings, and row count are illustrative only; the firmware displays actual sensor/RTC values or unavailable indicators. Pixel typography in the preview can differ from the device's built-in font.

To rebuild the header, SVGs, and preview on this Windows workspace, run `python firmware/neoguard_system/assets/build_assets.py` from the project root. The rebuild tool uses Pillow and the Windows Consolas font. Neither is required on the ESP32 or for normal Arduino compilation.
