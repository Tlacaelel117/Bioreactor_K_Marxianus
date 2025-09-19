#include <Arduino.h>
#include <DallasTemperature.h>
#include <OneWire.h>
#include <Wire.h>

// ---------- Configuración de hardware ----------
#define ONE_WIRE_BUS 3     // DS18B20
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

// Pines de los sensores de oxígeno (añade más si es necesario)
const uint8_t DO_PINS[] = {A1, A2};
const uint8_t NUM_DO    = sizeof(DO_PINS) / sizeof(DO_PINS[0]);

// ---------- Calibración ----------
#define VREF 5000      // mV
#define ADC_RES 1024
const float ADC_TO_MV = VREF / float(ADC_RES); // constante de conversión

#define CAL1_V 1220    // mV
#define CAL1_T 40.0    // °C
#define CAL2_V 766     // mV
#define CAL2_T 16.44   // °C
const float PRESSURE_CORRECTION = 0.771f;

// Tabla de saturación (µg/L) indexada por temperatura entera
const uint16_t DO_Table[41] = {
  14460,14220,13820,13440,13090,12740,12420,12110,11810,11530,
  11260,11010,10770,10530,10300,10080,9860,9660,9460,9270,
  9080,8900,8730,8570,8410,8250,8110,7960,7820,7690,
  7560,7430,7300,7180,7070,6950,6840,6730,6630,6530,6410
};

// ---------- Funciones ----------
float leerTemperatura() {
  sensors.requestTemperatures();
  return sensors.getTempCByIndex(0);
}

int16_t readDO(uint32_t voltage_mv, uint8_t temperature_c) {
  uint16_t V_sat = (uint16_t)(
      (temperature_c - CAL2_T) *
      (CAL1_V - CAL2_V) / (CAL1_T - CAL2_T) + CAL2_V);
  return voltage_mv * DO_Table[temperature_c] / V_sat;
}

uint16_t leerSensorDO(uint8_t pin, uint8_t tempC) {
  uint16_t raw = analogRead(pin);
  uint32_t volt = uint32_t(raw * ADC_TO_MV);
  uint16_t value = readDO(volt, tempC);
  return (uint16_t)(value * PRESSURE_CORRECTION);
}

void setup() {
  Serial.begin(9600);
  sensors.begin();
  Wire.begin();
}

void loop() {
  // 1. Temperatura (una sola vez por ciclo)
  float temp = leerTemperatura();
  uint8_t tempInt = uint8_t(temp + 0.5);

  // 2. Lectura de todos los sensores DO
  Serial.print("Temp: ");
  Serial.print(temp, 2);
  Serial.print(" °C");

  for (uint8_t i = 0; i < NUM_DO; i++) {
    uint16_t doValue = leerSensorDO(DO_PINS[i], tempInt);
    Serial.print(" | O2-");
    Serial.print(i + 1);
    Serial.print(": ");
    Serial.print(doValue);
    Serial.print(" µg/L");
  }

  Serial.println();
  delay(500); // muestreo cada segundo
}
