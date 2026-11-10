#pragma once
#include "runtime_compat.h"
#include <StreamString.h>

// HTTPClient decodes chunked responses into this bounded sink. Cloud proxies
// may omit Content-Length; a successful reply must still be consumed.
class BoundedBackendReply : public StreamString {
public:
  static constexpr size_t LIMIT = 20000;
  size_t write(const uint8_t *data, size_t size) override {
    if (size > LIMIT - length()) return 0;
    return StreamString::write(data, size);
  }
  size_t write(uint8_t data) override { return write(&data, 1); }
};
constexpr EventBits_t PORTAL_ACTIVE = 1, PORTAL_REQUEST = 2, SAFE_RESTART = 4;
bool wifiPortalActive() { return networkEvents && (xEventGroupGetBits(networkEvents) & PORTAL_ACTIVE); }
void requestWifiSetup() { if (networkEvents) xEventGroupSetBits(networkEvents, PORTAL_REQUEST); }

void ensureBackendDns() {
  // Some hotspot leases leave DNS unset. Preserve a supplied resolver, otherwise
  // use public resolvers. The hotspot gateway need not be a DNS proxy. Keep DHCP.
  if (WiFi.status() != WL_CONNECTED || WiFi.dnsIP() != IPAddress(0, 0, 0, 0)) return;
  IPAddress primary = WiFi.dnsIP(1);
  if (primary == IPAddress(0, 0, 0, 0)) primary = IPAddress(1, 1, 1, 1);
  bool saved = WiFi.setDNS(primary, IPAddress(8, 8, 8, 8));
  Serial.printf("NETWORK missing DNS fallback=%s configured=%d\n", primary.toString().c_str(), saved);
}

void diagnoseBackendTransport() {
  static uint32_t lastProbe = 0;
  if (lastProbe && millis() - lastProbe < 60000) return;
  lastProbe = millis();
  int end = apiBase.indexOf('/', 8);
  String host = apiBase.substring(8, end < 0 ? apiBase.length() : end);
  IPAddress address;
  int resolved = WiFi.hostByName(host.c_str(), address);
  Serial.printf("NETWORK route gateway=%s dns=%s host=%s resolved=%d address=%s\n",
    WiFi.gatewayIP().toString().c_str(), WiFi.dnsIP().toString().c_str(),
    host.c_str(), resolved, address.toString().c_str());
  if (resolved) {
    NetworkClient probe;
    int connected = probe.connect(address, 443, 2000);
    int socketError = errno;
    probe.stop();
    Serial.printf("NETWORK TCP443=%d socket_errno=%d\n", connected, socketError);
  }
}

String backendRequest(const String &path, const String *body, int &code) {
  NetworkClientSecure client; client.setCACert(ROOT_CA); client.setHandshakeTimeout(10);
  HTTPClient http; http.setConnectTimeout(8000); http.setTimeout(12000);
  code = -100;
  if (WiFi.status() != WL_CONNECTED || time(nullptr) < 1700000000 || !deviceSecret.length()) return "";
  ensureBackendDns();
  if (!http.begin(client, apiBase + path)) return "";
  http.addHeader("Authorization", "Bearer " + deviceSecret);
  http.addHeader("Content-Type", "application/json");
  code = body ? http.POST(*body) : http.GET();
  if (code < 0) {
    char detail[160]=""; lastTLSError=client.lastError(detail,sizeof(detail));
    Serial.printf("NETWORK transport HTTP=%d TLS=%d %s\n",code,(int)lastTLSError,detail);
    diagnoseBackendTransport();
  } else lastTLSError=0;
  String reply;
  if (code == 200) {
    int declared = http.getSize();
    BoundedBackendReply buffer;
    if (declared > (int)BoundedBackendReply::LIMIT) code = HTTPC_ERROR_STREAM_WRITE;
    else if (!buffer.reserve(declared >= 0 ? declared + 1 : 2048)) code = HTTPC_ERROR_TOO_LESS_RAM;
    else {
      int consumed = http.writeToStream(&buffer);
      if (consumed >= 0 && (size_t)consumed == buffer.length()) reply = buffer;
      else code = consumed < 0 ? consumed : HTTPC_ERROR_STREAM_WRITE;
    }
    if (code < 0) Serial.printf("NETWORK response body incomplete or too large status=%d\n", code);
  }
  http.end(); return reply;
}

void networkWorker(void *) {
  WiFiManager manager;
  manager.setDebugOutput(false); // Library debug logging can expose configuration.
  manager.setConfigPortalBlocking(false);
  manager.setConfigPortalTimeout(0);
  manager.setConnectTimeout(12); manager.setSaveConnectTimeout(12);
  manager.setShowPassword(false); manager.setShowInfoErase(false); manager.setShowInfoUpdate(false);
  manager.setClass("invert");
  WiFiManagerParameter codeField("device_code", "Dashboard device code", deviceCode.c_str(), 30);
  WiFiManagerParameter secretField("device_secret", "Device secret (blank keeps saved secret)", "", 128, "type='password' autocomplete='new-password'");
  WiFiManagerParameter apiField("api", "Backend API URL", apiBase.c_str(), 200);
  manager.addParameter(&codeField); manager.addParameter(&secretField); manager.addParameter(&apiField);
  bool configChanged = false;
  manager.setSaveParamsCallback([&]() {
    String code = codeField.getValue(), secret = secretField.getValue(), api = apiField.getValue();
    code.trim(); api.trim(); while (api.endsWith("/")) api.remove(api.length() - 1);
    if (!code.length() && !secret.length()) {
      Serial.println("SETUP: no device credentials supplied; Wi-Fi setup continues.");
      return;
    }
    bool validCode = code.length() >= 3 && code.length() <= 30;
    for (unsigned i = 0; i < code.length(); ++i) validCode = validCode && (isalnum((unsigned char)code[i]) || code[i] == '_' || code[i] == '-');
    if (!validCode || !api.startsWith("https://") || api.indexOf('@') >= 0) {
      Serial.println("SETUP: invalid device code or HTTPS API URL; device settings not saved."); return;
    }
    Preferences config; config.begin("neoguard", false);
    if (code != deviceCode) {
      config.putUInt("session", 0); config.putUInt("started", 0);
      config.remove("hr_low"); config.remove("hr_high"); config.remove("temp_low"); config.remove("spo2_low");
      if (!secret.length()) config.remove("secret");
    }
    config.putString("code", code); config.putString("api", api);
    if (secret.length()) config.putString("secret", secret);
    config.end(); configChanged = true;
  });
  manager.setAPCallback([](WiFiManager *) { xEventGroupSetBits(networkEvents, PORTAL_ACTIVE); });
  manager.autoConnect(setupNetwork.c_str(), setupPassword.c_str());
  // Wi-Fi works independently of backend registration. Keep the dashboard
  // available after reconnect; WIFI SETUP can open the device fields later.
  WiFi.setAutoReconnect(true);
  ensureBackendDns();
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  uint32_t lastRuntime = millis() - 15000, disconnectedSince = millis(), lastPost = millis();
  RuntimeContext cached; cached.limits = alarmLimits;
  for (;;) {
    manager.process();
    if (manager.getConfigPortalActive()) xEventGroupSetBits(networkEvents, PORTAL_ACTIVE);
    else xEventGroupClearBits(networkEvents, PORTAL_ACTIVE);
    if (configChanged && !manager.getConfigPortalActive() && WiFi.status() == WL_CONNECTED) {
      // The main loop owns SD files and restarts only after its current write closes.
      xEventGroupSetBits(networkEvents, SAFE_RESTART);
      vTaskDelay(pdMS_TO_TICKS(20)); continue;
    }
    EventBits_t flags = xEventGroupGetBits(networkEvents);
    if (WiFi.status() == WL_CONNECTED) disconnectedSince = millis();
    if ((flags & PORTAL_REQUEST) || (WiFi.status() != WL_CONNECTED && millis() - disconnectedSince > 30000)) {
      xEventGroupClearBits(networkEvents, PORTAL_REQUEST);
      if (!manager.getConfigPortalActive()) manager.startConfigPortal(setupNetwork.c_str(), setupPassword.c_str());
      disconnectedSince = millis();
    }
    // Leave the portal responsive while someone is configuring it by phone.
    bool canUseBackend = !(flags & PORTAL_ACTIVE) || WiFi.softAPgetStationNum() == 0;
    if (canUseBackend && WiFi.status() == WL_CONNECTED && deviceCode.length() >= 3 && deviceSecret.length() && millis() - lastRuntime >= 10000) {
      lastRuntime = millis(); int code;
      String body = backendRequest("/devices/runtime", nullptr, code);
      bool fallback = useLegacyContext(code);
      if (fallback) body = backendRequest("/devices/current-session", nullptr, code);
      lastRuntimeHTTP = code;
      if (code == 401 || code == 403) {
        RuntimeContext denied; denied.denied = true; xQueueOverwrite(runtimeResults, &denied);
      } else if (code == 200) {
        JsonDocument context;
        auto parseError = deserializeJson(context, body);
        if (!parseError && context["device_code"].as<String>() != deviceCode) {
          RuntimeContext denied; denied.denied = true; xQueueOverwrite(runtimeResults, &denied);
        } else if (!parseError) {
          RuntimeContext next = cached;
          next.session = context["session_id"] | 0U; next.started = context["session_started_unix"] | 0U;
          next.serverTime = context["server_time_unix"] | (uint32_t)time(nullptr);
          next.fallback = fallback; next.denied = false;
          if (!fallback) {
            next.limits.hrLow = context["thresholds"]["hr_low"] | cached.limits.hrLow;
            next.limits.hrHigh = context["thresholds"]["hr_high"] | cached.limits.hrHigh;
            // This MLX bench monitor measures surfaces. Do not replace its
            // requested 32 C limit with the server's clinical core-temp default.
            next.limits.tempLow = SURFACE_TEMP_LOW_C;
            next.limits.spo2Low = context["thresholds"]["spo2_low"] | cached.limits.spo2Low;
          }
          if (isfinite(next.limits.hrLow) && isfinite(next.limits.hrHigh) && next.limits.hrLow < next.limits.hrHigh &&
              isfinite(next.limits.tempLow) && isfinite(next.limits.spo2Low)) {
            cached = next; xQueueOverwrite(runtimeResults, &next);
          }
        }
      }
      // Report connectivity while the sensor is warming up, without inventing readings.
      if (millis() - lastPost >= 15000 && uxQueueMessagesWaiting(uploadRequests) == 0) {
        time_t now = time(nullptr); tm utc; gmtime_r(&now, &utc);
        char stamp[32]; strftime(stamp, sizeof(stamp), "%Y-%m-%dT%H:%M:%SZ", &utc);
        JsonDocument heartbeat;
        heartbeat["device_code"] = deviceCode; heartbeat["firmware_version"] = "akena-st7789-6";
        heartbeat["readings"].to<JsonArray>();
        heartbeat["telemetry"]["reported_at"] = stamp;
        heartbeat["telemetry"]["wifi_rssi_dbm"] = WiFi.RSSI();
        heartbeat["telemetry"]["uptime_seconds"] = millis() / 1000;
        String payload; serializeJson(heartbeat, payload);
        int heartbeatCode; backendRequest("/devices/sync", &payload, heartbeatCode);
        lastHeartbeatHTTP = heartbeatCode; lastPost = millis();
      }
    }
    UploadJob *job = nullptr;
    if (xQueueReceive(uploadRequests, &job, pdMS_TO_TICKS(20)) == pdTRUE) {
      job->code = -100;
      if (canUseBackend && millis() - lastPost >= 6000) {
        job->reply = backendRequest("/devices/sync", &job->body, job->code); lastPost = millis();
      }
      lastSyncHTTP = job->code;
      xQueueSend(uploadResults, &job, portMAX_DELAY);
    }
  }
}

void applyRuntimeContext() {
  RuntimeContext current;
  if (xQueueReceive(runtimeResults, &current, 0) != pdTRUE) return;
  if (current.denied) {
    if (assignedSession) {
      measurement.reset(); thresholdAlarm.reset();
      Preferences config; config.begin("neoguard", false); config.putUInt("session", 0); config.putUInt("started", 0); config.end();
    }
    assignedSession = 0; syncState = "DEVICE AUTH ERROR"; return;
  }
  bool changed = assignedSession != current.session;
  bool limitsChanged = alarmLimits.hrLow != current.limits.hrLow || alarmLimits.hrHigh != current.limits.hrHigh ||
    alarmLimits.tempLow != current.limits.tempLow || alarmLimits.spo2Low != current.limits.spo2Low;
  if (changed) { measurement.reset(); thresholdAlarm.reset(); }
  if (limitsChanged) thresholdAlarm.reset();
  assignedSession = current.session; sessionStartedUnix = current.started; alarmLimits = current.limits;
  if (changed || limitsChanged) {
    Preferences config; config.begin("neoguard", false);
    config.putString("context_code", deviceCode);
    config.putUInt("session", assignedSession); config.putUInt("started", sessionStartedUnix);
    config.putFloat("hr_low", alarmLimits.hrLow); config.putFloat("hr_high", alarmLimits.hrHigh);
    config.putFloat("temp_low", alarmLimits.tempLow); config.putFloat("spo2_low", alarmLimits.spo2Low); config.end();
  }
  if (current.serverTime > 1700000000 && (!rtcOK || labs((long)(rtc.GetDateTime().TotalSeconds() + 946684800UL - 10800UL - current.serverTime)) > 5)) {
    rtc.SetIsWriteProtected(false); rtc.SetDateTime(RtcDateTime(current.serverTime + 10800UL - 946684800UL));
    rtc.SetIsRunning(true); refreshClock();
    Serial.println(current.fallback ? "RTC: synchronized to network time (Nairobi)." : "RTC: synchronized to authenticated backend time (Nairobi).");
  }
  syncState = !assignedSession ? "NO ACTIVE SESSION" : current.fallback ? "LOCAL LIMITS / ONLINE" : "SESSION CONNECTED";
}
