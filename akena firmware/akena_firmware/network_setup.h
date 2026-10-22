#pragma once
#include "runtime_compat.h"
constexpr EventBits_t PORTAL_ACTIVE = 1, PORTAL_REQUEST = 2, SAFE_RESTART = 4;
bool wifiPortalActive() { return networkEvents && (xEventGroupGetBits(networkEvents) & PORTAL_ACTIVE); }
void requestWifiSetup() { if (networkEvents) xEventGroupSetBits(networkEvents, PORTAL_REQUEST); }

String backendRequest(const String &path, const String *body, int &code) {
  NetworkClientSecure client; client.setCACert(ROOT_CA); client.setHandshakeTimeout(10);
  HTTPClient http; http.setConnectTimeout(8000); http.setTimeout(12000);
  code = -100;
  if (WiFi.status() != WL_CONNECTED || time(nullptr) < 1700000000 || !deviceSecret.length()) return "";
  if (!http.begin(client, apiBase + path)) return "";
  http.addHeader("Authorization", "Bearer " + deviceSecret);
  http.addHeader("Content-Type", "application/json");
  code = body ? http.POST(*body) : http.GET();
  String reply;
  if (code == 200 && http.getSize() >= 0 && http.getSize() <= 20000) reply = http.getString();
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
  if ((!deviceCode.length() || !deviceSecret.length()) && !manager.getConfigPortalActive()) {
    manager.startConfigPortal(setupNetwork.c_str(), setupPassword.c_str());
  }
  WiFi.setAutoReconnect(true);
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
            next.limits.tempLow = context["thresholds"]["temp_low"] | cached.limits.tempLow;
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
        heartbeat["device_code"] = deviceCode; heartbeat["firmware_version"] = "akena-live-2";
        heartbeat["readings"].to<JsonArray>();
        heartbeat["telemetry"]["reported_at"] = stamp;
        heartbeat["telemetry"]["wifi_rssi_dbm"] = WiFi.RSSI();
        heartbeat["telemetry"]["uptime_seconds"] = millis() / 1000;
        String payload; serializeJson(heartbeat, payload);
        int heartbeatCode; backendRequest("/devices/sync", &payload, heartbeatCode); lastPost = millis();
      }
    }
    UploadJob *job = nullptr;
    if (xQueueReceive(uploadRequests, &job, pdMS_TO_TICKS(20)) == pdTRUE) {
      job->code = -100;
      if (canUseBackend && millis() - lastPost >= 6000) {
        job->reply = backendRequest("/devices/sync", &job->body, job->code); lastPost = millis();
      }
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
