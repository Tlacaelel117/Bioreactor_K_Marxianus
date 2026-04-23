// =====================================================
// SISTEMA MULTISENSOR PARA BIOREACTOR 3D
// Temperatura, pH, Oxigeno Disuelto x2
// Compatible con Python en Raspberry Pi
// =====================================================

#include <Arduino.h>
#include <DallasTemperature.h>
#include <OneWire.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// =====================================================
// CONFIGURACION DE PINES
// =====================================================
#define PH_SENSOR_PIN A0
#define DO_PIN1       A1
#define DO_PIN2       A2
#define ONE_WIRE_BUS  3

// =====================================================
// CONFIGURACION LCD
// =====================================================
LiquidCrystal_I2C lcd(0x27, 20, 4);

// =====================================================
// SENSOR DE TEMPERATURA
// =====================================================
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature tempSensor(&oneWire);

// =====================================================
// CONSTANTES GENERALES
// =====================================================
#define VREF 5000
#define ADC_RES 1024
const float PRESSURE_CORRECTION = 0.771f;

// =====================================================
// CALIBRACION DO SENSOR 1
// =====================================================
#define CAL1_V1 1220.0
#define CAL1_T1 40.0
#define CAL2_V1 766.0
#define CAL2_T1 16.4

// =====================================================
// CALIBRACION DO SENSOR 2
// =====================================================
#define CAL1_V2 1347.0f
#define CAL1_T2 39.15f
#define CAL2_V2 619.5f
#define CAL2_T2 19.57f

// =====================================================
// TABLA DE SATURACION DE O2
// =====================================================
const uint16_t DO_Table[41] = {
  14460, 14220, 13820, 13440, 13090, 12740, 12420, 12110, 11810, 11530,
  11260, 11010, 10770, 10530, 10300, 10080, 9860, 9660, 9460, 9270,
  9080, 8900, 8730, 8570, 8410, 8250, 8110, 7960, 7820, 7690,
  7560, 7430, 7300, 7180, 7070, 6950, 6840, 6730, 6630, 6530, 6410
};

// =====================================================
// CALIBRACION PH
// =====================================================
float calibration_value = 22.14 + 0.81;

// =====================================================
// FUNCIONES DE CALCULO
// =====================================================
int16_t readDO(uint32_t voltage_mv, uint8_t temperature_c,
               float CAL1_V, float CAL1_T, float CAL2_V, float CAL2_T) {
  uint16_t V_sat = (uint16_t)((temperature_c - CAL2_T) * (CAL1_V - CAL2_V) /
                              (CAL1_T - CAL2_T) + CAL2_V);
  return voltage_mv * DO_Table[temperature_c] / V_sat;
}

float leerTemperatura() {
  tempSensor.requestTemperatures();
  return tempSensor.getTempCByIndex(0);
}

float leerPH() {
  int muestras = 10;
  int lectura;
  unsigned long suma = 0;

  for (int i = 0; i < muestras; i++) {
    lectura = analogRead(PH_SENSOR_PIN);
    suma += lectura;
    delay(10);
  }

  float promedio = (float)suma / muestras;
  float voltaje = promedio * 5.0 / 1024.0;
  return -5.70 * voltaje + calibration_value;
}

// =====================================================
// SETUP
// =====================================================
void setup() {
  Serial.begin(115200);
  tempSensor.begin();
  Wire.begin();
  lcd.init();
  lcd.backlight();

  lcd.clear();
  lcd.print(" Bioreactor 3D ");
  lcd.setCursor(0, 1);
  lcd.print("Sensores listos");
  delay(1500);

  Serial.println("----------------------------------------------------");
  Serial.println("Sistema Multisensor Bioreactor 3D");
  Serial.println("Salida formateada para Python");
  Serial.println("----------------------------------------------------");
  delay(1000);
}

// =====================================================
// LOOP
// =====================================================
void loop() {
  // Temperatura
  float tsensor = leerTemperatura();
  uint8_t Temperaturet = uint8_t(tsensor + 0.5);

  // pH
  float ph_act = leerPH();

  // DO SENSOR 1
  uint16_t ADC_Raw_DO1  = analogRead(DO_PIN1);
  uint16_t ADC_Volt_DO1 = (uint32_t)VREF * ADC_Raw_DO1 / ADC_RES;
  uint16_t DO_value1    = readDO(ADC_Volt_DO1, Temperaturet,
                                 CAL1_V1, CAL1_T1, CAL2_V1, CAL2_T1)
                          * PRESSURE_CORRECTION;

  // DO SENSOR 2
  uint16_t ADC_Raw_DO2  = analogRead(DO_PIN2);
  uint16_t ADC_Volt_DO2 = (uint32_t)VREF * ADC_Raw_DO2 / ADC_RES;
  uint16_t DO_value2    = readDO(ADC_Volt_DO2, Temperaturet,
                                 CAL1_V2, CAL1_T2, CAL2_V2, CAL2_T2)
                          * PRESSURE_CORRECTION;

  // Mostrar en Serial
  Serial.print("Temp: ");
  Serial.print(tsensor, 2);
  Serial.print(", pH: ");
  Serial.print(ph_act, 2);
  Serial.print(", O2_1: ");
  Serial.print(DO_value1);
  Serial.print(", O2_2: ");
  Serial.println(DO_value2);

  // Mostrar en LCD
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("T:");
  lcd.print(tsensor, 1);
  lcd.print("C  pH:");
  lcd.print(ph_act, 2);

  lcd.setCursor(0, 1);
  lcd.print("O2-1:");
  lcd.print(DO_value1);
  lcd.setCursor(10, 1);
  lcd.print("O2-2:");
  lcd.print(DO_value2);

  delay(1000);
}
