#pragma once
#include <ArduinoJson.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <NetworkClientSecure.h>
#include <new>
#include <time.h>

// SD belongs exclusively to the Arduino loop; the network task receives copies.
struct UploadJob {
  String body, reply;
  uint32_t endOffset = 0;
  int code = 0;
};
QueueHandle_t uploadRequests = nullptr, uploadResults = nullptr;
String wifiName, wifiPassword, apiBase, deviceCode, deviceSecret, rootCA;
uint32_t assignedSession = 0, uploadCursor = 0, lastUploadAttempt = 0;
bool syncConfigured = false, uploadBusy = false, queueDamaged = false;
const char *syncState = "SYNC SETUP NEEDED";
constexpr char QUEUE_PATH[] = "/pending.ndjson";
constexpr char CURSOR_PATH[] = "/sync.cursor";

void networkWorker(void *) {
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin(wifiName.c_str(), wifiPassword.c_str());
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  uint32_t lastReconnect = millis();
  for (;;) {
    if (WiFi.status() != WL_CONNECTED && millis() - lastReconnect > 30000) {
      WiFi.reconnect(); lastReconnect = millis();
    }
    UploadJob *job = nullptr;
    if (xQueueReceive(uploadRequests, &job, pdMS_TO_TICKS(500)) != pdTRUE) continue;
    job->code = -100; // Offline: retain the entire batch on SD.
    if (WiFi.status() == WL_CONNECTED && time(nullptr) > 1700000000) {
      NetworkClientSecure client;
      client.setCACert(rootCA.c_str());
      client.setHandshakeTimeout(12);
      HTTPClient http;
      http.setConnectTimeout(10000);
      http.setTimeout(15000);
      if (http.begin(client, apiBase + "/devices/sync")) {
        http.addHeader("Content-Type", "application/json");
        http.addHeader("Authorization", "Bearer " + deviceSecret);
        job->code = http.POST(job->body);
        // Bound memory use. Responses larger than this stay unacknowledged.
        if (job->code == 200 && http.getSize() >= 0 && http.getSize() <= 20000) job->reply = http.getString();
        http.end();
      }
    }
    xQueueSend(uploadResults, &job, portMAX_DELAY);
  }
}

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

void beginOfflineSync() {
  if (syncConfigured || !sdOK) return;
  File config = SD.open("/sync_config.json", FILE_READ);
  if (!config) { syncState = "SYNC SETUP NEEDED"; return; }
  JsonDocument settings;
  auto error = deserializeJson(settings, config); config.close();
  if (error) { syncState = "SYNC CONFIG ERROR"; return; }
  wifiName = settings["wifi_ssid"] | "";
  wifiPassword = settings["wifi_password"] | "";
  apiBase = settings["api_base_url"] | "";
  deviceCode = settings["device_code"] | "";
  deviceSecret = settings["device_secret"] | "";
  assignedSession = settings["session_id"] | 0U;
  while (apiBase.endsWith("/")) apiBase.remove(apiBase.length() - 1);
  File cert = SD.open("/root_ca.pem", FILE_READ);
  if (cert && cert.size() < 12000) rootCA = cert.readString();
  cert.close();
  if (!wifiName.length() || deviceCode.length() < 3 || deviceCode.length() > 30 ||
      !deviceSecret.length() || !assignedSession || !apiBase.startsWith("https://") ||
      rootCA.indexOf("-----BEGIN CERTIFICATE-----") < 0) {
    syncState = "SYNC SETUP NEEDED";
    Serial.println("SYNC: check config, original session ID and root_ca.pem; HTTPS required.");
    return;
  }
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
  pending.close();
  uploadRequests = xQueueCreate(1, sizeof(UploadJob *));
  uploadResults = xQueueCreate(1, sizeof(UploadJob *));
  if (!uploadRequests || !uploadResults) {
    if (uploadRequests) vQueueDelete(uploadRequests);
    if (uploadResults) vQueueDelete(uploadResults);
    uploadRequests = uploadResults = nullptr;
    syncState = "SYNC MEMORY ERROR"; return;
  }
  if (xTaskCreatePinnedToCore(networkWorker, "sd-upload", 12288, nullptr, 1, nullptr, 0) != pdPASS) {
    vQueueDelete(uploadRequests); vQueueDelete(uploadResults);
    uploadRequests = uploadResults = nullptr;
    syncState = "SYNC TASK ERROR"; return;
  }
  syncConfigured = true;
  syncState = queueDamaged ? "SYNC FILE CHECK" : "SYNC WAIT WIFI";
  Serial.printf("SYNC: configured for session %lu; stored events keep their original session.\n",
    (unsigned long)assignedSession);
}

void queueOfflineReading() {
  if (!syncConfigured || !sdOK || queueDamaged || !rtcOK) return;
  // Preserve all bench values in CSV. Only send API-compatible values; never clamp.
  bool sendHR = hrValid && heartRate >= 40 && heartRate <= 220;
  bool sendO2 = spo2Valid && spo2 >= 50 && spo2 <= 100;
  bool sendTemp = goodTemp && objectC >= 30 && objectC <= 42;
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
  if (sendHR) item["heart_rate_bpm"] = heartRate;
  if (sendO2) item["spo2_percent"] = spo2;
  if (sendTemp) item["temperature_c"] = serialized(String(objectC, 2));
  item["quality"] = sendHR && sendO2 && sendTemp ? "ok" : "poor";
  String line;
  if (item.overflowed() || serializeJson(item, line) != measureJson(item)) {
    syncState = "SYNC MEMORY ERROR";
    Serial.println("SYNC: could not queue this reading; its bench values remain in CSV.");
    return;
  }
  line += '\n';
  File file = SD.open(QUEUE_PATH, FILE_APPEND);
  if (!file) { sdOK = false; sdError = "QUEUE OPEN"; return; }
  bool ok = file.print(line) == line.length(); file.flush();
  ok = ok && !file.getWriteError(); file.close();
  if (!ok) {
    queueDamaged = true; sdOK = false; sdError = "QUEUE WRITE";
    syncState = "SYNC FILE CHECK";
  }
}

void serviceOfflineSync() {
  if (!syncConfigured || !sdOK) return;
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
    if (acknowledged && saveUploadCursor(result->endOffset)) {
      uploadCursor = result->endOffset; syncState = "SYNC UPLOADED";
      Serial.println("SYNC: batch acknowledged; progress saved on SD.");
    } else {
      syncState = result->code == -100 ? "SYNC WAIT WIFI" : "SYNC RETRY";
      Serial.printf("SYNC: retained batch; HTTP/status=%d (check WiFi, TLS, device credential or session).\n", result->code);
    }
    delete result;
  }
  if (uploadBusy || queueDamaged || millis() - lastUploadAttempt < 15000) return;
  lastUploadAttempt = millis();
  File pending = SD.open(QUEUE_PATH, FILE_READ);
  if (!pending) return;
  if (uploadCursor >= pending.size()) { pending.close(); return; }
  if (!pending.seek(uploadCursor)) { pending.close(); syncState = "SYNC FILE CHECK"; return; }
  JsonDocument batch;
  batch["device_code"] = deviceCode; batch["firmware_version"] = "blue-sd-sync-1";
  JsonArray readings = batch["readings"].to<JsonArray>();
  // Up to 20 per 15 seconds: replay can catch up with one queued event per second.
  while (pending.available() && readings.size() < 20) {
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
  if (queueDamaged || !readings.size()) return;
  UploadJob *job = new (std::nothrow) UploadJob;
  if (!job) { syncState = "SYNC MEMORY ERROR"; return; }
  if (serializeJson(batch, job->body) != measureJson(batch)) {
    delete job; syncState = "SYNC MEMORY ERROR"; return;
  }
  job->endOffset = endOffset;
  if (xQueueSend(uploadRequests, &job, 0) == pdTRUE) {
    uploadBusy = true; syncState = "SYNC SENDING";
  } else delete job;
}
