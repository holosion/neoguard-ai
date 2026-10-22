#include "measurement.h"
#include "runtime_compat.h"
#include <cassert>
#include <iostream>

int main() {
  assert(useLegacyContext(401) && useLegacyContext(403) && useLegacyContext(404) && useLegacyContext(422));
  assert(!useLegacyContext(200) && !useLegacyContext(429) && !useLegacyContext(500) && !useLegacyContext(-100));
  StableMeasurement m;
  for (unsigned t = 0; t < 60; ++t) {
    m.observe(t * 1000, true, true, 140 + int(t % 3) - 1, 98, 37);
    assert(!m.get(t * 1000).ready);
  }
  m.observe(60000, true, true, 140, 98, 37);
  assert(m.get(60000).ready && m.get(60000).hr == 140);
  assert(!m.get(63000).ready); // No silently frozen, stale results.
  m.observe(61000, true, true, 190, 98, 37);
  assert(!m.get(61000).ready); // An unstable tail is not presented as stable.
  m.observe(62000, false, false, 0, 0, 0);
  assert(m.elapsed(62000) == 0 && !m.get(62000).ready);
  for (unsigned t = 63; t <= 122; ++t) m.observe(t * 1000, true, true, 150, 97, 37);
  assert(!m.get(122000).ready);
  m.observe(123000, true, true, 150, 97, 37);
  assert(m.get(123000).ready && m.get(123000).hr == 150);
  // A sampling outage restarts acquisition, including after a previously ready result.
  m.observe(130000, true, true, 150, 97, 37);
  assert(m.elapsed(130000) == 0 && !m.get(130000).ready);
  m.reset();
  for (unsigned t = 0; t <= 70; ++t) m.observe(t * 1000, true, t % 2 == 0, 140, 98, 37);
  assert(!m.get(70000).ready); // A minute with too few valid estimates is insufficient.
  m.reset();
  for (unsigned t = 0; t <= 70; ++t) m.observe(t * 1000, true, true, t % 2 ? 120 : 170, 98, 37);
  assert(!m.get(70000).ready);
  m.reset();
  for (unsigned t = 0; t <= 140; t += 2) m.observe(t * 1000, true, true, 140, 98, 37);
  assert(!m.get(140000).ready); // Sparse observations cannot masquerade as a full minute.
  m.reset();
  for (unsigned t = 0; t <= 60; ++t) m.observe(t * 1000, true, true, 140, 98, 37);
  for (unsigned t = 61; t <= 80; ++t) m.observe(t * 1000, true, true, 144, 98, 37);
  assert(m.get(80000).ready && m.get(80000).hr == 144); // Values follow genuine changes.
  m.reset();
  uint32_t base = UINT32_MAX - 30000;
  for (unsigned t = 0; t <= 60; ++t) m.observe(base + t * 1000, true, true, 140, 98, 37);
  assert(m.get(base + 60000).ready); // millis() rollover does not break acquisition.

  AlarmLimits limits;
  ThresholdAlarm alarm;
  for (unsigned i = 0; i < 2; ++i) alarm.observe(true, true, 170, true, 98, true, 37, limits);
  assert(alarm.flags() == 0);
  alarm.observe(true, true, 170, true, 98, true, 37, limits);
  assert(alarm.flags() == 2); // Alarm confirmed before the 60-second measurement.
  for (unsigned i = 0; i < 5; ++i) alarm.observe(true, false, 0, false, 0, false, 0, limits);
  assert(alarm.flags() == 2); // Invalid estimates do not prove recovery.
  for (unsigned i = 0; i < 3; ++i) alarm.observe(true, true, 140, true, 98, true, 37, limits);
  assert(alarm.flags() == 0);
  for (unsigned i = 0; i < 3; ++i) alarm.observe(true, true, 90, true, 85, true, 36, limits);
  assert(alarm.flags() == (1 | 4 | 8));
  alarm.observe(false, false, 0, false, 0, false, 0, limits);
  assert(alarm.flags() == 0);
  for (unsigned i = 0; i < 3; ++i) alarm.observe(true, true, 160, true, 90, true, 36.5f, limits);
  assert(alarm.flags() == 0); // Equal-to-threshold values match backend comparisons.
  std::cout << "Measurement and threshold alarm behavior: PASS\n";
}
