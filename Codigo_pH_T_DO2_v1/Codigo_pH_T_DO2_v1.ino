// Bibliotecas requeridas
#include <Arduino.h>  
#include <SparkFun_SCD30_Arduino_Library.h>
#include <DallasTemperature.h>
#include <OneWire.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

//CONFIGURACION DO2 PIN del sensor DO2 PIN A1
#define DO_PIN A1
#define VREF 5000    //VREF (mv)
#define ADC_RES 1024 //ADC Resolution
//Two-point calibration Mode=1 || Single-point calibration Mode=0
#define TWO_POINT_CALIBRATION 1
//Punto de calibracion caliente
#define CAL1_V (1220) //mv
#define CAL1_T (40)   //℃
//Punto de calibracion frio
#define CAL2_V (766) //mv
#define CAL2_T (16.44)   //℃
const uint16_t DO_Table[41] = {
    14460, 14220, 13820, 13440, 13090, 12740, 12420, 12110, 11810, 11530,
    11260, 11010, 10770, 10530, 10300, 10080, 9860, 9660, 9460, 9270,
    9080, 8900, 8730, 8570, 8410, 8250, 8110, 7960, 7820, 7690,
    7560, 7430, 7300, 7180, 7070, 6950, 6840, 6730, 6630, 6530, 6410};
// ——— Variables ———
float     tsensor;        // Temperatura en °C con decimales
uint8_t   Temperaturet;   // Temperatura redondeada (para tabla)
uint16_t  ADC_Raw_DO;     // Lectura cruda de O₂
uint16_t  ADC_Volt_DO;    // Voltaje del sensor de O₂
uint16_t  DO_value;       // Valor de O₂ disuelto en µg/L
// ——— Función para calcular O₂ disuelto ———
int16_t readDO(uint32_t voltage_mv, uint8_t temperature_c) {
  // Calcula el voltaje de saturación interpolado
  uint16_t V_saturation = (uint16_t)( (temperature_c - CAL2_T) * (CAL1_V - CAL2_V) / (CAL1_T - CAL2_T) + CAL2_V );
  // Escala según tabla
  return voltage_mv * DO_Table[temperature_c] / V_saturation;
}

// CONFIGURACION Sensor DS18B20 Temperatura (PIN 3 digital)
#define ONE_WIRE_BUS 3
OneWire ourWire(ONE_WIRE_BUS);
DallasTemperature sensors(&ourWire);

// CONFIGURACION Dirección del LCD (0x27 o 0x3F)(PIN A4-VDA,A5-SCL analogicos)
LiquidCrystal_I2C lcd(0x27, 20, 4);

// CONFIGURACION sensor pH (PIN A0 analogico)
float calibration_value = 22.14+0.81; // Ajustar según calibración correccion+error de señal
#define PH_SENSOR_PIN A0


void setup() {
  Serial.begin(115200);
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
  delay(1500);
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
  tsensor = sensors.getTempCByIndex(0);
  
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
  
  //Sensor DO2
  Temperaturet = uint8_t(tsensor + 0.5);  // redondear para tabla
  // ——— Leer sensor de O₂ ———
  ADC_Raw_DO  = analogRead(DO_PIN);
  ADC_Volt_DO = uint32_t(VREF) * ADC_Raw_DO / ADC_RES;
  DO_value    = readDO(ADC_Volt_DO, Temperaturet);
  
    // ——— Mostrar resultados ———
  Serial.print("Temp: ");
  Serial.print(tsensor, 2);
  Serial.print(", pH: ");
  Serial.print(ph_act, 2);
  Serial.print(", O2: ");
  Serial.print(DO_value);
  Serial.println();  // <-- fin de línea único
  //Serial.print("V_DO:");
    //Serial.print(ADC_Volt_DO); Serial.print(" mV");

  // Actualizar LCD solo cada cierto intervalo para no retrasar el envío serial
  if (millis() - lastLcdUpdate >= lcdInterval) {
    lcd.clear();
    lcd.print(F("TEMPERATURA (C)"));
    lcd.setCursor(3, 1);
    lcd.print(tsensor, 2);
    
    lcd.setCursor(0, 2);
    lcd.print("pH");
    lcd.setCursor(1, 3);
    lcd.print(ph_act, 2);
    
    lcd.setCursor(7, 2);
    lcd.print("O2(microg/L)");
    lcd.setCursor(7, 3);
    lcd.print(DO_value);
    lastLcdUpdate = millis();
  }
  // Evitar un delay fijo al final del loop para permitir mayor reactividad
}
