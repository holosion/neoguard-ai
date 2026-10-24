#pragma once
#if NEOGUARD_ENABLE_NETWORK
#include "offline_sync.h"
bool wifiOnline() { return WiFi.status() == WL_CONNECTED; }
String wifiAddress() { return WiFi.localIP().toString(); }
void printConnectivityStatus() {
  Serial.printf("NETWORK clock_ready=%d RSSI=%ld runtime_http=%d heartbeat_http=%d sync_http=%d queue_cursor=%lu queue_damaged=%d TLS_error=%d\n",
    time(nullptr) >= 1700000000, (long)(wifiOnline() ? WiFi.RSSI() : 0),
    (int)lastRuntimeHTTP, (int)lastHeartbeatHTTP, (int)lastSyncHTTP,
    (unsigned long)uploadCursor, queueDamaged, (int)lastTLSError);
}
#else
// No WiFi/HTTP/provisioning headers or tasks are compiled into this validation.
// Existing network credentials and queued uploads are neither read nor changed.
String deviceCode, deviceSecret, setupNetwork, setupPassword;
uint32_t assignedSession = 0;
unsigned ramSize = 0, droppedReadings = 0;
bool queueDamaged = false;
const char *syncState = "OFFLINE / LOCAL SD";
bool wifiOnline() { return false; }
String wifiAddress() { return "0.0.0.0"; }
bool wifiPortalActive() { return false; }
void beginOfflineSync() {}
void serviceOfflineSync() {}
void queueOfflineReading() {}
void requestWifiSetup() { Serial.println("WiFi disabled in this offline validation build."); }
void printConnectivityStatus() { Serial.println("NETWORK disabled"); }
#endif
