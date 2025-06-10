// Bibliotecas requeridas
#include <SparkFun_SCD30_Arduino_Library.h>
#include <DallasTemperature.h>
#include <OneWire.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// PIN UTILIZADO PARA LA COMUNICACIÓN CON EL DS18B20 (T)
#define ONE_WIRE_BUS 3
OneWire ourWire(ONE_WIRE_BUS);
DallasTemperature sensors(&ourWire);

// Dirección del LCD (0x27 o 0x3F)
LiquidCrystal_I2C lcd(0x27, 20, 4);

// Valores para sensor pH
float calibration_value = 22.14+0.81; // Ajustar según calibración correccion+error de señal
#define PH_SENSOR_PIN A0

//Definimos el nombre del sensor de CO2
SCD30 airSensor;

void setup() {
  Serial.begin(9600);
  Serial.println(F("----------------------------------------------------"));
  Serial.println(F("      SENSOR DE TEMPERATURA y pH CON ARDUINO        "));
  Serial.println(F("         Arduino listo para enviar datos...         "));
  Serial.println(F("----------------------------------------------------"));

  // Iniciar sensores
  sensors.begin();
  Wire.begin();
  
  // Configurar LCD
  lcd.init();
  lcd.backlight();
  lcd.clear();
  lcd.print(F("   Bioreactor 3D"));
  lcd.setCursor(0, 1);
  lcd.print(F("    k.marxianus   "));
  delay(3000);
}
  //Configuracion de temperatura
  float leerTemperatura() {
  sensors.requestTemperatures();
  return sensors.getTempCByIndex(0);
}
  //Configuracion de pH
  float leerPH() {
  int muestras = 10;
  int buffer_arr[muestras];
  for (int i = 0; i < muestras; i++) {
    buffer_arr[i] = analogRead(PH_SENSOR_PIN);
    delay(30);
  }

  // Calculo del promedio sin ordenar
  unsigned long sum = 0;
  for (int i = 0; i < muestras; i++) {
    sum += buffer_arr[i];
  }
  float avgval = sum / (float)muestras;
  float volt = avgval * 5.0 / 1024;
  return -5.70 * volt + calibration_value;
}

unsigned long lastLcdUpdate = 0;
const unsigned long lcdInterval = 1000; // Actualizar LCD cada 1 segundo

void loop() {
  // Tomar la temperatura y pH sin retrasos excesivos
  sensors.requestTemperatures();
  float t = sensors.getTempCByIndex(0);

  // Leer pH: se reduce el número de muestras para acelerar el proceso
  int muestras = 5;
  unsigned long sum = 0;
  for (int i = 0; i < muestras; i++) {
    sum += analogRead(A0);
    delay(10);  // Menor delay por muestra
  }
  float avgval = sum / (float)muestras;
  float volt = avgval * 5.0 / 1024;
  float ph_act = -5.70 * volt + calibration_value;

  // Enviar datos por Serial inmediatamente
  Serial.print("Temp:");
  Serial.print(t, 2);
  Serial.print(",pH:");
  Serial.println(ph_act, 2);

  // Actualizar LCD solo cada cierto intervalo para no retrasar el envío serial
  if (millis() - lastLcdUpdate >= lcdInterval) {
    lcd.clear();
    lcd.print(F("TEMPERATURA (C)"));
    lcd.setCursor(3, 1);
    lcd.print(t, 2);
    lcd.setCursor(0, 2);
    lcd.print("pH");
    lcd.setCursor(3, 3);
    lcd.print(ph_act, 2);
    lastLcdUpdate = millis();
  }
  // Evitar un delay fijo al final del loop para permitir mayor reactividad
}
