import serial
import time
import re
import matplotlib.pyplot as plt
import pandas as pd
import os
from datetime import datetime

# --- Configuración del puerto serial ---
try:
    ser = serial.Serial("/dev/ttyACM0", 115200, timeout=1)
    time.sleep(2)  
    ser.flushInput()
except Exception as e:
    print("Error: No se pudo abrir el puerto serial. Verifica la conexión.")
    raise e

# --- Inicialización de variables ---
timeData_avg = []
tempData_avg = []
phData_avg = []
o2_1Data_avg = []
o2_2Data_avg = []
timestamps_avg = []

buffer_temp = []
buffer_ph   = []
buffer_o2_1 = []
buffer_o2_2 = []

start_time    = time.time()
last_avg_time = start_time
avg_interval  = 600  # segundos

# --- Configuración de la gráfica ---
plt.ion()
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8, 9))

# Temperatura
line_temp, = ax1.plot([], [], 'r.-', linewidth=1.5)
ax1.set_title("Temperatura (Promedio)")
ax1.set_xlabel("Tiempo (s)")
ax1.set_ylabel("°C")
ax1.grid(True)

# pH
line_ph, = ax2.plot([], [], 'b.-', linewidth=1.5)
ax2.set_title("pH (Promedio)")
ax2.set_xlabel("Tiempo (s)")
ax2.set_ylabel("pH")
ax2.grid(True)

# O₂
line_o2_1, = ax3.plot([], [], 'g.-', label='O₂|1', linewidth=1.5)
line_o2_2, = ax3.plot([], [], 'm.-', label='O₂|2', linewidth=1.5)
ax3.set_title("O₂ Disuelto (Promedio)")
ax3.set_xlabel("Tiempo (s)")
ax3.set_ylabel("µg/L")
ax3.grid(True)

# Expresión regular para extraer Temp, pH y O2
pattern = re.compile(
    r"Temp:\s*([-+]?\d*\.?\d+),\s*"
    r"pH:\s*([-+]?\d*\.?\d+),\s*"
    r"O2\|1:\s*([-+]?\d*\.?\d+),\s"
    r"O2\|2:\s*([-+]?\d*\.?\d+)"
)

print("Inicio de la adquisición. Presione Ctrl+C para detener el programa.")

try:
    while True:
        current_time = time.time()
        if ser.in_waiting > 0:
            try:
                data_line = ser.readline().decode('utf-8').strip()
            except UnicodeDecodeError:
                continue

            match = pattern.search(data_line)
            if not match:
                continue
            try
                temp_val = float(match.group(1))
                ph_val   = float(match.group(2))
                o2_1_val   = float(match.group(3))
                o2_2_val   = float(match.group(4))
                except ValueError:
                    continue
            
                buffer_temp.append(temp_val)
                buffer_ph.append(ph_val)
                buffer_o2_1.append(o2_1_val)
                buffer_o2_2.append(o2_2_val)

        # Verificar si el intervalo de promedio se ha cumplido
        if current_time - last_avg_time >= avg_interval:
            if buffer_temp:
                avg_temp = sum(buffer_temp) / len(buffer_temp)
                avg_ph   = sum(buffer_ph)   / len(buffer_ph)
                avg_o2_1 = sum(buffer_o2_1)   / len(buffer_o2_1)
                avg_o2_2 = sum(buffer_o2_2) / len(buffer_o2_2)
                
                elapsed  = current_time - start_time
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                timeData_avg.append(elapsed)
                tempData_avg.append(avg_temp)
                phData_avg.append(avg_ph)
                o2_1Data_avg.append(avg_o2_1)
                o2_2Data_avg.append(avg_o2_2)
                timestamps_avg.append(timestamp)

                # Actualizar graficas con datos promediado 
                line_temp.set_data(timeData_avg, tempData_avg)
                ax1.relim(); ax1.autoscale_view()
                
                line_ph.set_data(timeData_avg, phData_avg)
                ax2.relim(); ax2.autoscale_view()
                
                line_o2_1.set_data(timeData_avg, o2_1Data_avg)
                line_o2_2.set_data(timeData_avg, o2_2Data_avg)
                ax3.relim(); ax3.autoscale_view()

                plt.draw()
                plt.pause(0.01)

                # Reset buffers
                buffer_temp = []
                buffer_ph   = []
                buffer_o2_1 = []
                buffer_o2_2 = []
                last_avg_time = current_time

        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nInterrupción detectada. Deteniendo la adquisición y guardando los datos...")
finally:
    ser.close()

# --- Guardar datos y gráfica ---
save_folder = r"/home/pi/Desktop/Maestria"
os.makedirs(save_folder, exist_ok=True)
fecha_actual = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# CSV
csv_path = os.path.join(save_folder, f"datos_sensor_promedio_{fecha_actual}.csv")
df = pd.DataFrame({
    "Fecha_Hora":   timestamps_avg,
    "Tiempo_s":     timeData_avg,
    "Temperatura_C": tempData_avg,
    "pH":           phData_avg,
    "O2_1_ug_/_L":  o2_1Data_avg
    "O2_2_ug_/_L":  o2_2Data_avg
})
df.to_csv(csv_path, index=False)
print(f"Datos guardados en '{csv_path}'.")

# Gráfica
graph_path = os.path.join(save_folder, f"grafica_sensor_promedio_{fecha_actual}.png")
fig.savefig(graph_path)
print(f"Gráficas guardadas en '{graph_path}'.")

