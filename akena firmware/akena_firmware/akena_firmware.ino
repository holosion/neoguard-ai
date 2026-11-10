// ===== Pulse Irrigation System =====
// Arduino Uno | Soil moisture sensor (digital) on D2 | Pump via transistor on D7

// ---------- Pins ----------
const uint8_t SOIL_PIN = 2;
const uint8_t PUMP_PIN = 7;

// ---------- Sensor logic ----------
// Most LM393 modules output HIGH when DRY and LOW when WET.
// If yours behaves the opposite way, change this to false.
const bool DRY_IS_HIGH = true;

// ---------- Timing (tune these) ----------
const unsigned long PUMP_ON_MS      = 5000;   // each pulse: pump runs 2 s
const unsigned long SOAK_MS         = 20000;  // wait 30 s for water to settle
const unsigned long SAMPLE_MS       = 500;    // how often to read the sensor
const uint8_t       CONFIRM_COUNT   = 5;      // consecutive same readings needed (debounce)

// ---------- Safety ----------
const uint8_t       MAX_PULSES      = 10;     // max pulses per watering cycle
const unsigned long LOCKOUT_MS      = 600000UL; // 10 min lockout if MAX_PULSES reached (empty tank / faulty sensor)

// ---------- State machine ----------
enum State { IDLE, PUMPING, SOAKING, LOCKOUT };
State state = IDLE;

unsigned long stateStart = 0;
unsigned long lastSample = 0;
uint8_t dryCount = 0;
uint8_t wetCount = 0;
uint8_t pulseCount = 0;
bool soilDry = false;   // debounced status

void setPump(bool on) {
  digitalWrite(PUMP_PIN, on ? HIGH : LOW);
}

bool readRawDry() {
  bool level = digitalRead(SOIL_PIN);
  return DRY_IS_HIGH ? level : !level;
}

// Debounced reading: status only changes after CONFIRM_COUNT identical readings
void updateSoilStatus() {
  if (millis() - lastSample < SAMPLE_MS) return;
  lastSample = millis();

  if (readRawDry()) {
    dryCount++;
    wetCount = 0;
    if (dryCount >= CONFIRM_COUNT) { soilDry = true; dryCount = CONFIRM_COUNT; }
  } else {
    wetCount++;
    dryCount = 0;
    if (wetCount >= CONFIRM_COUNT) { soilDry = false; wetCount = CONFIRM_COUNT; }
  }
}

void enterState(State s) {
  state = s;
  stateStart = millis();
  switch (s) {
    case PUMPING:
      setPump(true);
      pulseCount++;
      Serial.print(F("Pulse #")); Serial.print(pulseCount); Serial.println(F(": pump ON"));
      break;
    case SOAKING:
      setPump(false);
      Serial.println(F("Pump OFF, letting water settle..."));
      break;
    case LOCKOUT:
      setPump(false);
      Serial.println(F("MAX pulses reached. Lockout (check tank/sensor)."));
      break;
    case IDLE:
      setPump(false);
      pulseCount = 0;
      Serial.println(F("Soil wet. Idle."));
      break;
  }
}

void setup() {
  Serial.begin(9600);
  pinMode(SOIL_PIN, INPUT);
  pinMode(PUMP_PIN, OUTPUT);
  setPump(false);
  Serial.println(F("Irrigation system started"));
}

void loop() {
  updateSoilStatus();
  unsigned long now = millis();

  switch (state) {
    case IDLE:
      // Start watering only when soil is confirmed dry
      if (soilDry) enterState(PUMPING);
      break;

    case PUMPING:
      // Stop early if soil becomes wet, otherwise stop after one pulse
      if (!soilDry) {
        enterState(IDLE);
      } else if (now - stateStart >= PUMP_ON_MS) {
        enterState(SOAKING);
      }
      break;

    case SOAKING:
      // After settling time, check again
      if (now - stateStart >= SOAK_MS) {
        if (!soilDry) {
          enterState(IDLE);
        } else if (pulseCount >= MAX_PULSES) {
          enterState(LOCKOUT);
        } else {
          enterState(PUMPING);
        }
      }
      break;

    case LOCKOUT:
      if (now - stateStart >= LOCKOUT_MS) {
        pulseCount = 0;
        enterState(IDLE);
      }
      break;
  }
}