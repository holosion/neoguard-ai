#include "live_vitals.h"
#include <cassert>
#include <iostream>
int main() {
  Measurement unqualified;
  auto v=selectLiveVitals(10000,9990,true,true,72,true,98,true,34,unqualified);
  assert(v.heartAvailable && v.heart==72 && v.oxygenAvailable && v.oxygen==98);
  assert(v.temperatureAvailable && !v.qualified); // Real estimates before the minute gate.
  v=selectLiveVitals(10000,9990,true,true,72,false,0,false,NAN,unqualified);
  assert(v.heartAvailable && !v.oxygenAvailable && !v.temperatureAvailable);
  v=selectLiveVitals(10000,9990,true,false,0,true,98,true,34,unqualified);
  assert(!v.heartAvailable && v.oxygenAvailable && v.temperatureAvailable);
  v=selectLiveVitals(10000,7000,true,true,72,true,98,true,34,unqualified);
  assert(!v.heartAvailable && !v.oxygenAvailable && v.temperatureAvailable);
  v=selectLiveVitals(10000,9990,false,true,72,true,98,true,34,unqualified);
  assert(!v.heartAvailable && !v.oxygenAvailable); // Clear immediately on removal.
  v=selectLiveVitals(10000,9990,true,true,0,true,0,true,27,unqualified);
  assert(!v.heartAvailable && !v.oxygenAvailable && !v.temperatureAvailable);
  v=selectLiveVitals(10000,9990,true,true,221,true,101,true,43,unqualified);
  assert(!v.heartAvailable && !v.oxygenAvailable && !v.temperatureAvailable); // Never clamp into API range.
  Measurement stable{true,74,97,34.5f};
  v=selectLiveVitals(10000,9990,true,true,76,true,98,true,34.7f,stable);
  assert(v.qualified && v.heart==74 && v.oxygen==97 && v.temperature==34.5f);
  v=selectLiveVitals(10000,7000,true,true,76,true,98,true,34.7f,stable);
  assert(!v.qualified && !v.heartAvailable && !v.oxygenAvailable);
  v=selectLiveVitals(500,UINT32_MAX-200,true,true,72,true,98,true,34,unqualified);
  assert(v.heartAvailable && v.oxygenAvailable); // Uptime rollover.
  std::cout << "Live estimate availability, quality and stale/removal handling: PASS\n";
}
