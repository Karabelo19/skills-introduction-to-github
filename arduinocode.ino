#include <WiFi.h>
#include <Adafruit_Sensor.h>
#include <DHT.h>
#include <HTTPClient.h>

// WiFi credentials
const char* ssid = "Karabelo_Wifi";
const char* password = "Karabelo19";

// Flask server URL
const char* serverName = "http://192.168.43.136:5000/cold_room";

// DHT11 sensor setup
#define DHTPIN 14         // GPIO pin connected to the DHT11
#define DHTTYPE DHT11     // DHT 11
DHT dht(DHTPIN, DHTTYPE);

// Sensor pins
const int soilMoisturePin = 35; // Analog pin
const int pirPin = 34;
const int ldr1Pin = 39;
const int ldr2Pin = 36;

// LED pin for grow light or cold room light
int ledpin = 25;

void setup() {
  Serial.begin(115200);
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");

  dht.begin();
  pinMode(pirPin, INPUT);
  pinMode(ledpin, OUTPUT);
  digitalWrite(ledpin, LOW); // Ensure LED is off initially
}

void loop() {
  float temperature = dht.readTemperature(); // Only temperature is used
  if (isnan(temperature)) {
    Serial.println("Failed to read from DHT11 sensor!");
    return;
  }

  int soilMoistureVal = analogRead(soilMoisturePin);
  int humidity = map(soilMoistureVal, 0, 4095, 100, 0);  // Simulated humidity

  int ldr1 = analogRead(ldr1Pin);
  int ldr2 = analogRead(ldr2Pin);
  int pir = digitalRead(pirPin);

  String alert = "";

  // Temperature alert
  if (temperature > 10) {
    alert += "Temperature too high for products! ";
  }

  // Humidity alert
  if (humidity > 80) {
    alert += "Humidity too high! ";
  }

  // LDR1 + PIR logic
  if (ldr1 < 100 && pir == HIGH) {
    alert += "Motion in dark detected - light ON. ";
    digitalWrite(ledpin, HIGH);  // Turn on LED
  } else {
    digitalWrite(ledpin, LOW);   // Turn off LED
  }

  // LDR2 + PIR logic (door opened, no one inside)
  if (ldr2 > 100 && pir == LOW) {
    alert += "Door open, no one inside! ";
  }

  // PIR motion status
  if (pir == HIGH) {
    alert += "Someone is inside. ";
  } else {
    alert += "No one is inside. ";
  }

  // Send data to Flask server
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(serverName);
    http.addHeader("Content-Type", "application/json");

    String jsonData = "{";
    jsonData += "\"temperature\":" + String(temperature) + ",";
    jsonData += "\"humidity\":" + String(humidity) + ",";
    jsonData += "\"ldr1\":" + String(ldr1) + ",";
    jsonData += "\"ldr2\":" + String(ldr2) + ",";
    jsonData += "\"pir\":" + String(pir) + ",";
    jsonData += "\"alert\":\"" + alert + "\"";
    jsonData += "}";

    int httpResponseCode = http.POST(jsonData);
    Serial.print("POST Response: ");
    Serial.println(httpResponseCode);
    Serial.println(jsonData);
    http.end();
  }

  delay(1000); // 10 seconds delay
}