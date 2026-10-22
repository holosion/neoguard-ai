# Oximeter power and communication test

Use this isolated sketch when the complete system does not start or the oximeter stays dark. It starts no screen, clock, SD card, temperature sensor or buzzer. It reports uptime, I2C addresses and raw optical samples, and retries failed detection every five seconds. It does not calculate pulse or SpO2.

Disconnect USB and the external supply before changing wires. Disconnect the other modules for this test.

For a confirmed 3.3 V compatible MAX30102 breakout:

| Connection | Destination |
| --- | --- |
| ESP32-S3 power | Computer USB |
| Breadboard supply | Its specified input source; output switched on |
| Breadboard sensor positive rail | Set to 3.3 V; verify at the sensor with a meter |
| MAX VIN/VCC | Breadboard 3.3 V sensor rail |
| MAX GND | Breadboard negative rail |
| ESP32 GND | Same breadboard negative rail |
| MAX SDA | ESP32 GPIO 4 |
| MAX SCL | ESP32 GPIO 5 |
| MAX INT | Unconnected |

Do not connect the breadboard positive rail to ESP32 3V3 or 5V while the ESP32 is powered by USB. This test uses separate positive supplies and a shared ground. Keep ESP32 signal levels and I2C pull-ups at 3.3 V. Do not switch the sensor to 5 V without identifying the breakout and its requirements. Some boards expose a separate LED supply: identify the exact board before connecting extra pins.

Check rail polarity at the actual sensor connection. Many breadboards have interrupted rails; opposite rails may also be separate. A power-supply indicator alone does not establish voltage at the sensor. Supply jumper positions and input requirements depend on the actual power module.

Install **SparkFun MAX3010x Pulse and Proximity Sensor Library**. Open `oximeter_power_test.ino`, select the actual ESP32-S3 board/port and upload. Enable **USB CDC On Boot** if using native USB. Open Serial Monitor at **115200 baud** and press RESET.

- No uptime text: check board selection, upload, USB port/cable and serial configuration first.
- No `0x57`: check sensor supply voltage at VIN/GND, shared ground, SDA/SCL and module identity.
- `0x57` but `MAX NOT READY`: the address responds, but this driver could not verify its expected part ID; confirm module identity and wiring.
- `MAX configured` and increasing sample count: acquisition is running. Gently cover the optical window with an adult finger and compare raw RED/IR values. This does not prove measurement accuracy.
- Detected but no fresh samples or no red glow: check supply under load and the breakout's LED power requirements. Infrared cannot be seen with the eye.

Send the startup output and a clear photo showing the power-supply jumpers, breadboard rails, ESP32 labels and oximeter pin labels to diagnose further. Compilation alone cannot verify the wiring or sensor power.
