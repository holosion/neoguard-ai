#include "live_vitals.h"
#include <cassert>
#include <cmath>
#include <iostream>

int main() {
  RollingHeartAverage average;
  // A repeated sampler snapshot cannot masquerade as several observations.
  average.observe(0,true,true,70,0);
  for (unsigned t=100;t<=1900;t+=100) average.observe(t,true,true,70,0);
  assert(!average.get(1900).ready && average.get(1900).samples==1);
  average.reset();
  for (unsigned i=0;i<=4;++i) average.observe(i*1000,true,true,70+2*i,i*1000);
  auto value=average.get(4000);
  assert(value.ready && value.samples==5 && value.spanMs==4000 && value.value==74);
  average.observe(5000,true,true,80,5000);
  assert(average.get(5000).value==74); // Hold the displayed value between updates.
  average.observe(6000,true,true,82,6000);
  assert(average.get(6000).value==74);
  average.observe(7000,true,true,84,7000);
  assert(average.get(7000).value==77);
  for (unsigned i=8;i<=10;++i) average.observe(i*1000,true,true,70+2*i,i*1000);
  value=average.get(10000);
  assert(value.samples==10 && value.value==81); // 10 seconds, oldest expired.
  assert(!average.get(12001).ready); // Never freeze a disconnected estimate.

  average.observe(11000,true,false,100,11000);
  assert(!average.get(11000).ready);
  average.observe(12000,true,true,NAN,12000);
  assert(!average.get(12000).ready);
  average.observe(13000,true,true,0,13000);
  assert(!average.get(13000).ready);
  average.observe(14000,true,true,39,14000);
  assert(!average.get(14000).ready);
  average.observe(15000,true,true,221,15000);
  assert(!average.get(15000).ready);
  average.observe(16000,true,true,100,16000);
  assert(!average.get(16000).ready && average.get(16000).samples==1);
  for (unsigned i=17;i<=20;++i) average.observe(i*1000,true,true,100,i*1000);
  assert(average.get(20000).ready && average.get(20000).value==100);
  average.observe(21000,false,true,100,21000);
  assert(!average.get(21000).ready && average.get(21000).samples==0);

  // A sustained change reaches the display; smoothing does not lock a baseline.
  for (unsigned i=22;i<=33;++i) average.observe(i*1000,true,true,70,i*1000);
  for (unsigned i=34;i<=48;++i) average.observe(i*1000,true,true,110,i*1000);
  assert(average.get(48000).ready && average.get(48000).value==110);
  average.reset();
  uint32_t base=UINT32_MAX-3000;
  for (unsigned i=0;i<10;++i) average.observe(base+i*1000,true,true,125,base+i*1000);
  assert(average.get(base+9000).ready && average.get(base+9000).value==125);

  AlarmLimits limits;
  Measurement unqualified;
  auto raw=selectLiveVitals(10000,9990,true,true,125,true,98,true,34,unqualified);
  auto display=displayHeartAverage(raw,HeartAverage{true,120,10,9000});
  assert(display.heartAvailable && display.heart==120 && !display.qualified);
  assert(raw.heart==125); // Original data is retained for uploads/qualification.
  assert(selectMonitorIndicator(display,true,false,0,limits)==MonitorIndicator::Green);
  assert(!raw.qualified && !display.qualified); // Green never upgrades AI eligibility.
  Measurement qualified{true,100,90,32};
  raw=selectLiveVitals(10000,9990,true,true,100,true,90,true,32,qualified);
  assert(selectMonitorIndicator(raw,true,false,0,limits)==MonitorIndicator::Green);
  assert(selectMonitorIndicator(raw,false,false,0,limits)==MonitorIndicator::Blue);
  assert(selectMonitorIndicator(raw,true,true,0,limits)==MonitorIndicator::Red);
  assert(selectMonitorIndicator(raw,true,false,2,limits)==MonitorIndicator::Red);
  raw.heart=160;
  assert(selectMonitorIndicator(raw,true,false,0,limits)==MonitorIndicator::Green);
  raw.heart=170;
  assert(selectMonitorIndicator(raw,true,false,0,limits)==MonitorIndicator::Blue);
  display=displayHeartAverage(raw,HeartAverage{true,120,10,9000});
  assert(display.heart==120);
  assert(selectMonitorIndicator(display,true,false,0,limits)==MonitorIndicator::Green);
  ThresholdAlarm alarm;
  for (unsigned i=0;i<3;++i) alarm.observe(true,true,170,true,98,true,34,limits);
  assert(selectMonitorIndicator(display,true,false,alarm.flags(),limits)==MonitorIndicator::Red);
  raw.heart=125; raw.oxygenAvailable=false;
  assert(selectMonitorIndicator(raw,true,false,0,limits)==MonitorIndicator::Blue);
  display=displayHeartAverage(raw,HeartAverage{});
  assert(!display.heartAvailable && !display.qualified);
  assert(selectMonitorIndicator(display,false,false,0,limits)==MonitorIndicator::Blue);
  raw.heartAvailable=true; raw.oxygenAvailable=true; raw.heart=125; raw.oxygen=89;
  assert(selectMonitorIndicator(raw,true,false,0,limits)==MonitorIndicator::Blue);
  raw.oxygen=98; raw.temperature=31.9f;
  assert(selectMonitorIndicator(raw,true,false,0,limits)==MonitorIndicator::Blue);
  raw.temperature=34; raw.temperatureAvailable=false;
  assert(selectMonitorIndicator(raw,true,false,0,limits)==MonitorIndicator::Blue);
  std::cout << "Rolling HR average, freshness, cadence and indicator safeguards: PASS\n";
}
