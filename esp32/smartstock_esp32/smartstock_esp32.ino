/*
  SmartStock AI - ESP32 weighing unit
  Hardware : ESP32 dev board + HX711 + 20 kg load cell
  Libraries: "HX711" by Bogdan Necula (Library Manager), ArduinoJson
  Wiring   : HX711 DT -> GPIO 16, SCK -> GPIO 4, VCC -> 3V3, GND -> GND

  What it does
  1. Tare at power-up (empty container on the scale).
  2. Reads the load cell 10 times per second.
  3. A reading is STABLE when the last 10 samples differ by less than 5 g (standard deviation).
  4. Every SEND_EVERY_MS it posts {device_id, seq_no, weight_kg, stable} to the Flask API.
  5. seq_no is stored in flash, so a retry or a reboot never creates a duplicate reading.

  Calibration (do this once)
  - Set CAL_FACTOR to 1.0, upload, open Serial Monitor.
  - Put a known weight (for example 1000 g) on the scale and note the raw value printed.
  - CAL_FACTOR = raw value / 1000.0   (units: raw counts per gram). Upload again and verify.
*/
#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <ArduinoJson.h>
#include "HX711.h"

const char* WIFI_SSID  = "YOUR_WIFI";
const char* WIFI_PASS  = "YOUR_PASSWORD";
const char* API_URL    = "http://192.168.1.10:5000/api/iot/readings";   // laptop IP running Flask
const char* DEVICE_ID  = "ESP32-RICE-01";
const char* DEVICE_KEY = "rice-key-123";

const int   PIN_DT = 16, PIN_SCK = 4;
float       CAL_FACTOR = 104.5;          // raw counts per gram - replace after calibration
const int   WINDOW = 10;                 // samples in the stability window
const float STABLE_SD_G = 5.0;           // stable if standard deviation < 5 g
const unsigned long SEND_EVERY_MS = 5000;

HX711 scale;
Preferences prefs;
float win[WINDOW];
int   widx = 0, wcount = 0;
unsigned long lastSend = 0;
uint32_t seqNo = 0;

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(250);
}

void setup() {
  Serial.begin(115200);
  scale.begin(PIN_DT, PIN_SCK);
  scale.set_scale(CAL_FACTOR);
  delay(1000);
  scale.tare(20);                        // empty container = 0 g
  prefs.begin("smartstock", false);
  seqNo = prefs.getUInt("seq", 0);
  connectWifi();
}

bool windowStats(float &meanG, float &sdG) {
  if (wcount < WINDOW) return false;
  float s = 0, s2 = 0;
  for (int i = 0; i < WINDOW; i++) { s += win[i]; s2 += win[i] * win[i]; }
  meanG = s / WINDOW;
  sdG = sqrt(max(0.0f, s2 / WINDOW - meanG * meanG));
  return true;
}

bool postReading(float kg, bool stable) {
  connectWifi();
  if (WiFi.status() != WL_CONNECTED) return false;
  StaticJsonDocument<200> doc;
  doc["device_id"] = DEVICE_ID;
  doc["seq_no"] = seqNo + 1;
  doc["weight_kg"] = kg;
  doc["stable"] = stable;
  String body; serializeJson(doc, body);
  HTTPClient http;
  http.begin(API_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);
  int code = http.POST(body);
  http.end();
  return code == 201 || code == 200;     // 200 = duplicate already stored (safe)
}

void loop() {
  if (scale.is_ready()) {
    win[widx] = scale.get_units(1);      // grams
    widx = (widx + 1) % WINDOW;
    if (wcount < WINDOW) wcount++;
  }
  float meanG, sdG;
  if (millis() - lastSend >= SEND_EVERY_MS && windowStats(meanG, sdG)) {
    lastSend = millis();
    bool stable = sdG < STABLE_SD_G;
    float kg = max(0.0f, meanG) / 1000.0;
    Serial.printf("weight=%.3f kg sd=%.1f g stable=%d\n", kg, sdG, stable);
    if (postReading(kg, stable)) {       // advance the sequence only after the server accepted it
      seqNo++;
      prefs.putUInt("seq", seqNo);
    }
  }
  delay(100);
}
