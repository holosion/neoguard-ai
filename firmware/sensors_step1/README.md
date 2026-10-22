# Step 1: oximeter and temperature sensor

ESP32-S3, MAX30102 breakout, MLX90614 breakout, Serial Monitor only. Unplug power and disconnect the other modules for this first test.

For confirmed 3.3 V compatible breakout modules, connect both GND pins to ESP32 GND, both supply pins to 3V3, both SDA pins to GPIO 4, and both SCL pins to GPIO 5. Leave MAX30102 INT unconnected. Follow printed labels, not pin positions. Do not use this supply plan for a 5 V-only module; verify its exact model first. ESP32 inputs and I2C pull-ups must use 3.3 V logic.

Install Adafruit MLX90614 Library and SparkFun MAX3010x Pulse and Proximity Sensor Library through Arduino Library Manager, accepting dependencies. Select your actual ESP32-S3 board and port. If using native USB, enable USB CDC On Boot. Open sensors_step1.ino and upload, then open Serial Monitor at 115200 baud and press RESET if the startup scan was missed.

The startup scan should find 0x57 (MAX30102) and 0x5A (MLX90614). Detection does not establish calibration or clinical accuracy. MAX30100 requires a different driver and is not supported here.

For a bench test, gently cover the MAX30102 optical window with an adult finger and hold still. Initial pulse estimates need at least four seconds of continuous contact; allow 10-20 seconds to observe behavior. Dashes indicate unavailable estimates, not zero readings. IR and RED report raw optical values. The contact threshold is initially IR=50000 and may require adjustment for the actual module. Move a hand near the MLX90614 sensing face and observe ObjectC separately from AmbientC; avoid touching the sensor can or heating it by handling it.

The MLX measures object/surface temperature, not core body temperature. These pulse/SpO2 estimates are experimental and not validated for neonatal monitoring. This sketch adds no clinical alarms, display, storage, or cloud upload.

Share the startup detection messages and several measurement lines before adding the next component.
