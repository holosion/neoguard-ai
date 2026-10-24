#pragma once
#include "measurement.h"

struct HeartAverage {
  bool ready = false;
  float value = 0;
  unsigned samples = 0;
  uint32_t spanMs = 0;
};

// Display smoothing only. The raw estimates still drive qualification, alarms,
// CSV and backend uploads. Never average a missing value or repeat one estimate.
class RollingHeartAverage {
  struct Sample { uint32_t at = 0; float value = 0; } samples[12]{};
  unsigned head = 0, count = 0;
  uint32_t lastEstimate = 0, publishedAt = 0;
  bool haveEstimate = false, havePublished = false, currentValid = false;
  float published = 0;
  HeartAverage window(uint32_t now) const {
    HeartAverage out;
    uint32_t oldest = 0, newest = WINDOW_MS;
    float total = 0;
    for (unsigned i = 0; i < count; ++i) {
      uint32_t age = now - samples[i].at;
      if (age >= WINDOW_MS) continue;
      total += samples[i].value; ++out.samples;
      oldest = std::max(oldest, age); newest = std::min(newest, age);
    }
    if (out.samples) {out.value = total / out.samples; out.spanMs = oldest - newest;}
    out.ready = out.samples >= 5 && out.spanMs >= 4000;
    return out;
  }
public:
  static constexpr uint32_t WINDOW_MS = 10000, REFRESH_MS = 3000;
  void reset() {
    head = count = 0; haveEstimate = havePublished = currentValid = false;
    lastEstimate = publishedAt = 0; published = 0;
  }
  void observe(uint32_t now, bool contact, bool valid, float value, uint32_t estimatedAt) {
    if (!contact || now - estimatedAt > 2000) {reset(); return;}
    currentValid = valid && std::isfinite(value) && value >= 40 && value <= 220;
    if (!currentValid) return;
    if (haveEstimate && estimatedAt == lastEstimate) return;
    if (haveEstimate && estimatedAt - lastEstimate > 2000) {reset(); currentValid = true;}
    samples[head] = {estimatedAt, value}; head = (head + 1) % 12;
    count = std::min(12U, count + 1); lastEstimate = estimatedAt; haveEstimate = true;
    HeartAverage next = window(now);
    if (next.ready && (!havePublished || now - publishedAt >= REFRESH_MS)) {
      published = next.value; publishedAt = now; havePublished = true;
    }
  }
  HeartAverage get(uint32_t now) const {
    HeartAverage out = window(now);
    out.ready = out.ready && currentValid && haveEstimate && havePublished &&
      now - lastEstimate <= 2000 && now - publishedAt <= REFRESH_MS + 2000;
    out.value = published;
    return out;
  }
};

struct LiveVitals {
  bool heartAvailable = false, oxygenAvailable = false, temperatureAvailable = false;
  bool qualified = false;
  float heart = 0, oxygen = 0, temperature = 0;
};

// Keep parameter availability independent. Never turn missing/stale signal into
// a zero or allow a moving temperature target to hide valid pulse estimates.
inline LiveVitals selectLiveVitals(uint32_t now, uint32_t sampled, bool contact,
    bool heartValid, float heart, bool oxygenValid, float oxygen,
    bool temperatureValid, float temperature, const Measurement &stable) {
  LiveVitals out;
  const bool pulseFresh = contact && now - sampled <= 2000;
  out.heart = stable.ready ? stable.hr : heart;
  out.oxygen = stable.ready ? stable.oxygen : oxygen;
  out.temperature = stable.ready ? stable.temperature : temperature;
  out.heartAvailable = pulseFresh && heartValid && std::isfinite(out.heart) && out.heart >= 40 && out.heart <= 220;
  out.oxygenAvailable = pulseFresh && oxygenValid && std::isfinite(out.oxygen) && out.oxygen >= 50 && out.oxygen <= 100;
  out.temperatureAvailable = temperatureValid && std::isfinite(out.temperature) && out.temperature >= 30 && out.temperature <= 42;
  out.qualified = stable.ready && out.heartAvailable && out.oxygenAvailable && out.temperatureAvailable;
  return out;
}

inline LiveVitals displayHeartAverage(LiveVitals live, const HeartAverage &average) {
  live.heart = average.value;
  live.heartAvailable = live.heartAvailable && average.ready;
  live.qualified = live.qualified && live.heartAvailable;
  return live;
}

enum class MonitorIndicator { Blue, Green, Red };
// This LED describes current displayed ranges. Full measurement qualification
// remains separate and is never promoted by the average or the LED colour.
inline MonitorIndicator selectMonitorIndicator(const LiveVitals &current,
    bool averageReady, bool sensorFault, unsigned alarmFlags, const AlarmLimits &limits) {
  if (sensorFault || alarmFlags) return MonitorIndicator::Red;
  bool within = averageReady && current.heartAvailable &&
    current.oxygenAvailable && current.temperatureAvailable &&
    current.heart >= limits.hrLow && current.heart <= limits.hrHigh &&
    current.oxygen >= limits.spo2Low && current.temperature >= limits.tempLow;
  return within ? MonitorIndicator::Green : MonitorIndicator::Blue;
}
