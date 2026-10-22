#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>

// Signal repeatability checks for the bench prototype, not clinical validation.
struct AlarmLimits {
  float hrLow = 100, hrHigh = 160, tempLow = 36.5f, spo2Low = 90;
};
struct Measurement {
  bool ready = false;
  float hr = 0, oxygen = 0, temperature = 0;
};
class StableMeasurement {
  struct Sample { float hr, oxygen, temperature; bool valid; uint32_t observed; } samples[60]{};
  unsigned head = 0, count = 0;
  bool touching = false;
  uint32_t started = 0, observed = 0, published = 0;
  Measurement value;
 public:
  void reset() { head = count = 0; touching = false; value = Measurement{}; published = 0; }
  unsigned elapsed(uint32_t now) const { return touching ? std::min(60U, unsigned((now - started) / 1000)) : 0; }
  Measurement get(uint32_t now) const {
    Measurement out = value;
    if (!touching || now - observed > 2500) out.ready = false;
    return out;
  }
  void observe(uint32_t now, bool contact, bool valid, float hr, float oxygen, float temperature) {
    if (!contact) { reset(); return; }
    if (touching && now - observed > 2500) reset();
    if (!touching) { touching = true; started = now; }
    observed = now;
    valid = valid && std::isfinite(hr) && std::isfinite(oxygen) && std::isfinite(temperature);
    samples[head] = {hr, oxygen, temperature, valid, now}; head = (head + 1) % 60;
    count = std::min(60U, count + 1);
    unsigned validMinute = 0;
    for (unsigned i = 0; i < count; ++i) if (samples[i].valid && now - samples[i].observed <= 60000) ++validMinute;
    float heart[15], ox[15], temp[15]; unsigned n = 0;
    for (unsigned i = 0; i < std::min(15U, count); ++i) {
      const Sample &s = samples[(head + 59 - i) % 60];
      if (s.valid && now - s.observed <= 15000) { heart[n] = s.hr; ox[n] = s.oxygen; temp[n++] = s.temperature; }
    }
    if (elapsed(now) < 60 || validMinute < 45 || n < 12 || !valid) { value.ready = false; return; }
    std::sort(heart, heart + n); std::sort(ox, ox + n); std::sort(temp, temp + n);
    if (heart[n-1] - heart[0] > 12 || ox[n-1] - ox[0] > 3 || temp[n-1] - temp[0] > 0.4f) {
      value.ready = false; return;
    }
    if (!value.ready || now - published >= 5000) {
      auto median = [n](float *v) { return n % 2 ? v[n/2] : (v[n/2-1] + v[n/2]) / 2; };
      value = {true, median(heart), median(ox), median(temp)}; published = now;
    }
  }
};

class ThresholdAlarm {
  unsigned streak[4]{}, recovery = 0;
  unsigned active = 0;
 public:
  void reset() { for (auto &v : streak) v = 0; active = recovery = 0; }
  unsigned flags() const { return active; }
  void observe(bool contact, bool hrValid, float hr, bool oxygenValid, float oxygen,
               bool tempValid, float temperature, const AlarmLimits &limits) {
    if (!contact) { reset(); return; }
    const bool breach[] = {hrValid && hr < limits.hrLow, hrValid && hr > limits.hrHigh,
      tempValid && temperature < limits.tempLow, oxygenValid && oxygen < limits.spo2Low};
    unsigned confirmed = 0;
    for (unsigned i = 0; i < 4; ++i) {
      streak[i] = breach[i] ? std::min(3U, streak[i] + 1) : 0;
      if (streak[i] >= 3) confirmed |= 1U << i;
    }
    if (confirmed) { active = confirmed; recovery = 0; }
    else if (active) {
      // Invalid estimates cannot be used as evidence that a threshold recovered.
      if (hrValid && oxygenValid && tempValid && !breach[0] && !breach[1] && !breach[2] && !breach[3]) {
        if (++recovery >= 3) active = recovery = 0;
      } else recovery = 0;
    }
  }
};
