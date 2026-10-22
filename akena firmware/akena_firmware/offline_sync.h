#pragma once
#include <ArduinoJson.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <NetworkClientSecure.h>
#include <new>
#include <time.h>
#include <sys/time.h>
#include <Preferences.h>
#include <WiFiManager.h>
#include <freertos/event_groups.h>
#include "root_ca.h"

// SD belongs exclusively to the Arduino loop; the network task receives copies.
struct UploadJob {
  String body, reply;
  uint32_t endOffset = 0;
  int code = 0;
  unsigned ramCount = 0;
};
QueueHandle_t uploadRequests = nullptr, uploadResults = nullptr;
String apiBase, deviceCode, deviceSecret, setupNetwork, setupPassword;
EventGroupHandle_t networkEvents = nullptr;
QueueHandle_t runtimeResults = nullptr;
struct RuntimeContext { uint32_t session = 0, started = 0, serverTime = 0; AlarmLimits limits; bool fallback = false; bool denied = false; };
String ramQueue[12];
unsigned ramHead = 0, ramSize = 0, droppedReadings = 0;
bool cursorLoaded = false;
uint32_t sessionStartedUnix = 0;
uint32_t assignedSession = 0, uploadCursor = 0, lastUploadAttempt = 0;
bool syncConfigured = false, uploadBusy = false, queueDamaged = false;
const char *syncState = "SYNC SETUP NEEDED";
constexpr char QUEUE_PATH[] = "/pending.ndjson";
constexpr char CURSOR_PATH[] = "/sync.cursor";

#include "network_setup.h"

bool saveUploadCursor(uint32_t offset) {
  // Interrupted writes fail the complement check and safely replay from zero.
  File file = SD.open(CURSOR_PATH, FILE_WRITE);
  if (!file) return false;
  char value[40];
  snprintf(value, sizeof(value), "%lu,%lu\n", (unsigned long)offset,
    (unsigned long)(offset ^ 0xA59C73E1UL));
  bool ok = file.print(value) == strlen(value);
  file.flush(); ok = ok && !file.getWriteError(); file.close();
  return ok;
}

void loadQueueCursor() {
  if (!sdOK || cursorLoaded) return;
  File pending = SD.open(QUEUE_PATH, FILE_READ);
  if (pending && pending.size()) {
    pending.seek(pending.size() - 1);
    queueDamaged = pending.read() != '\n';
    File cursor = SD.open(CURSOR_PATH, FILE_READ);
    unsigned long offset = 0, check = 0;
    String stored = cursor ? cursor.readStringUntil('\n') : ""; cursor.close();
    int used = 0;
    if (sscanf(stored.c_str(), "%lu,%lu%n", &offset, &check, &used) == 2 &&
        used == (int)stored.length() && (offset ^ 0xA59C73E1UL) == check && offset <= pending.size()) {
      if (offset == 0 || (pending.seek(offset - 1) && pending.read() == '\n')) uploadCursor = offset;
    }
  }
  pending.close(); cursorLoaded = true;
}

void beginOfflineSync() {
  loadQueueCursor();
  if (syncConfigured) return;
  Preferences settings; settings.begin("neoguard", true);
  apiBase = settings.getString("api", "https://neoguard-api-wwth.onrender.com/api/v1");
  deviceCode = settings.getString("code", ""); deviceSecret = settings.getString("secret", "");
  setupPassword = settings.getString("ap_pass", "");
  assignedSession = settings.getUInt("session", 0);
  sessionStartedUnix = settings.getUInt("started", 0);
  alarmLimits.hrLow = settings.getFloat("hr_low", 100);
  alarmLimits.hrHigh = settings.getFloat("hr_high", 160);
  alarmLimits.tempLow = settings.getFloat("temp_low", 36.5f);
  alarmLimits.spo2Low = settings.getFloat("spo2_low", 90);
  if (settings.getString("context_code", "") != deviceCode) {
    assignedSession = sessionStartedUnix = 0; alarmLimits = AlarmLimits{};
  }
  settings.end();
  if (!setupPassword.length()) {
    char password[16]; snprintf(password, sizeof(password), "NG%08lX", (unsigned long)esp_random());
    setupPassword = password;
    settings.begin("neoguard", false); settings.putString("ap_pass", setupPassword); settings.end();
  }
  char network[32]; snprintf(network, sizeof(network), "NeoGuard-%04X", (unsigned)(ESP.getEfuseMac() & 0xFFFF));
  setupNetwork = network;
  uploadRequests = xQueueCreate(1, sizeof(UploadJob *)); uploadResults = xQueueCreate(1, sizeof(UploadJob *));
  runtimeResults = xQueueCreate(1, sizeof(RuntimeContext)); networkEvents = xEventGroupCreate();
  if (!uploadRequests || !uploadResults || !runtimeResults || !networkEvents) {
    if (uploadRequests) vQueueDelete(uploadRequests);
    if (uploadResults) vQueueDelete(uploadResults);
    if (runtimeResults) vQueueDelete(runtimeResults);
    if (networkEvents) vEventGroupDelete(networkEvents);
    uploadRequests = uploadResults = runtimeResults = nullptr; networkEvents = nullptr;
    syncState = "NETWORK MEMORY ERROR"; return;
  }
  if (xTaskCreatePinnedToCore(networkWorker, "neoguard-network", 16384, nullptr, 1, nullptr, 0) != pdPASS) {
    vQueueDelete(uploadRequests); vQueueDelete(uploadResults); vQueueDelete(runtimeResults); vEventGroupDelete(networkEvents);
    uploadRequests = uploadResults = runtimeResults = nullptr; networkEvents = nullptr;
    syncState = "NETWORK TASK ERROR"; return;
  }
  syncConfigured = true; syncState = "CONNECTING WIFI";
  Serial.printf("PHONE SETUP: join %s, password %s, open 192.168.4.1\n", setupNetwork.c_str(), setupPassword.c_str());
}

void retainInRAM(const String &line) {
  if (ramSize < 12) { ramQueue[(ramHead + ramSize) % 12] = line; ++ramSize; }
  else { ++droppedReadings; Serial.printf("RAM QUEUE FULL: %u readings not retained; SD unavailable.\n", droppedReadings); }
}

void queueOfflineReading() {
  if (!syncConfigured || !assignedSession || !rtcOK) return;
  Measurement result = measurement.get(millis());
  if (!result.ready) return;
  uint32_t measuredUnix = rtc.GetDateTime().TotalSeconds() + 946684800UL - 10800UL;
  if (measuredUnix < sessionStartedUnix) return;
  // Preserve all bench values in CSV. Only send API-compatible values; never clamp.
  int stableHR = lroundf(result.hr), stableO2 = lroundf(result.oxygen);
  bool sendHR = stableHR >= 40 && stableHR <= 220;
  bool sendO2 = stableO2 >= 50 && stableO2 <= 100;
  bool sendTemp = result.temperature >= 30 && result.temperature <= 42;
  if (!sendHR && !sendO2 && !sendTemp) return;
  JsonDocument item;
  uint8_t id[16]; esp_fill_random(id, sizeof(id));
  id[6] = (id[6] & 0x0F) | 0x40; id[8] = (id[8] & 0x3F) | 0x80;
  char uuid[37], measured[32];
  snprintf(uuid, sizeof(uuid), "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x",
    id[0],id[1],id[2],id[3],id[4],id[5],id[6],id[7],id[8],id[9],id[10],id[11],id[12],id[13],id[14],id[15]);
  snprintf(measured, sizeof(measured), "%s+03:00", timestamp); measured[10] = 'T';
  item["event_id"] = uuid; item["session_id"] = assignedSession;
  item["measured_at"] = measured;
  if (sendHR) item["heart_rate_bpm"] = stableHR;
  if (sendO2) item["spo2_percent"] = stableO2;
  if (sendTemp) item["temperature_c"] = serialized(String(result.temperature, 2));
  item["quality"] = sendHR && sendO2 && sendTemp ? "ok" : "poor";
  String line;
  if (item.overflowed() || serializeJson(item, line) != measureJson(item)) {
    syncState = "SYNC MEMORY ERROR";
    Serial.println("SYNC: reading not queued; check storage and free memory.");
    return;
  }
  line += '\n';
  if (!sdOK || queueDamaged) { retainInRAM(line); return; }
  File file = SD.open(QUEUE_PATH, FILE_APPEND);
  if (!file) { sdOK = false; sdError = "QUEUE OPEN"; retainInRAM(line); return; }
  bool ok = file.print(line) == line.length(); file.flush();
  ok = ok && !file.getWriteError(); file.close();
  if (!ok) {
    queueDamaged = true; sdOK = false; sdError = "QUEUE WRITE";
    syncState = "SYNC FILE CHECK"; retainInRAM(line);
  }
}

void serviceOfflineSync() {
  if (!syncConfigured) return;
  if (xEventGroupGetBits(networkEvents) & SAFE_RESTART) {
    Serial.println("SETUP: saved; restarting after storage operation completed.");
    ESP.restart(); return;
  }
  loadQueueCursor();
  applyRuntimeContext();
  if (WiFi.status() != WL_CONNECTED && !wifiPortalActive()) syncState = "WIFI OFFLINE / SD";
  UploadJob *result = nullptr;
  if (xQueueReceive(uploadResults, &result, 0) == pdTRUE) {
    uploadBusy = false;
    bool acknowledged = false;
    if (result->code == 200) {
      JsonDocument reply, request;
      auto replyError = deserializeJson(reply, result->reply);
      auto requestError = deserializeJson(request, result->body);
      JsonArray sent = request["readings"].as<JsonArray>();
      JsonArray received = reply["readings"].as<JsonArray>();
      acknowledged = !replyError && !requestError && reply["device_code"].as<String>() == deviceCode &&
        sent.size() > 0 && sent.size() == received.size();
      for (size_t i = 0; acknowledged && i < sent.size(); ++i) {
        String status = received[i]["status"] | "";
        acknowledged = sent[i]["event_id"].as<String>() == received[i]["event_id"].as<String>() &&
          (status == "accepted" || status == "duplicate");
      }
      if (!acknowledged) Serial.println("SYNC: server did not acknowledge every event; batch retained. Check session/timestamps.");
    }
    if (acknowledged && (result->ramCount || (sdOK && saveUploadCursor(result->endOffset)))) {
      if (result->ramCount) {
        for (unsigned i = 0; i < result->ramCount; ++i) { ramQueue[ramHead] = ""; ramHead = (ramHead + 1) % 12; --ramSize; }
      } else uploadCursor = result->endOffset; syncState = "SYNC UPLOADED";
      Serial.println(result->ramCount ? "SYNC: RAM batch acknowledged." : "SYNC: batch acknowledged; progress saved on SD.");
    } else {
      syncState = result->code == -100 ? "SYNC WAIT WIFI" : "SYNC RETRY";
      Serial.printf("SYNC: retained batch; HTTP/status=%d (check WiFi, TLS, device credential or session).\n", result->code);
    }
    delete result;
  }
  if (uploadBusy || (queueDamaged && !ramSize) || millis() - lastUploadAttempt < 6000) return;
  if (deviceCode.length() < 3 || !deviceSecret.length()) return;
  lastUploadAttempt = millis();
  if (!ramSize && !sdOK) return;
  File pending = sdOK ? SD.open(QUEUE_PATH, FILE_READ) : File();
  if (!ramSize && !pending) return;
  if (!ramSize && uploadCursor >= pending.size()) { pending.close(); return; }
  if (!ramSize && !pending.seek(uploadCursor)) { pending.close(); syncState = "SYNC FILE CHECK"; return; }
  JsonDocument batch;
  batch["device_code"] = deviceCode; batch["firmware_version"] = "akena-live-2";
  JsonArray readings = batch["readings"].to<JsonArray>();
  // Replay up to 20 stored events per attempt while recording a new event every 5s.
  unsigned ramBatch = ramSize;
  for (unsigned i = 0; i < ramBatch; ++i) {
    JsonDocument item;
    if (deserializeJson(item, ramQueue[(ramHead + i) % 12]) || !readings.add(item.as<JsonObject>())) return;
  }
  while (!ramBatch && pending.available() && readings.size() < 20) {
    String line;
    bool complete = false;
    while (pending.available() && line.length() <= 1024) {
      int value = pending.read();
      if (value == '\n') { complete = true; break; }
      if (value < 0) break;
      line += (char)value;
      if (line.length() % 128 == 0) collectPulse();
    }
    JsonDocument item;
    if (!complete || line.length() > 1024 || deserializeJson(item, line)) {
      queueDamaged = true; syncState = "SYNC FILE CHECK"; break;
    }
    if (!readings.add(item.as<JsonObject>()) || batch.overflowed()) {
      pending.close(); syncState = "SYNC MEMORY ERROR"; return;
    }
    collectPulse();
  }
  uint32_t endOffset = pending.position(); pending.close();
  if ((!ramBatch && queueDamaged) || !readings.size()) return;
  UploadJob *job = new (std::nothrow) UploadJob;
  if (!job) { syncState = "SYNC MEMORY ERROR"; return; }
  if (serializeJson(batch, job->body) != measureJson(batch)) {
    delete job; syncState = "SYNC MEMORY ERROR"; return;
  }
  job->endOffset = endOffset; job->ramCount = ramBatch;
  if (xQueueSend(uploadRequests, &job, 0) == pdTRUE) {
    uploadBusy = true; syncState = "SYNC SENDING";
  } else delete job;
}
