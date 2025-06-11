import serial
import time
import re
import matplotlib.pyplot as plt
import pandas as pd
import os
from datetime import datetime

# --- Configuración del puerto serial ---
try:
    ser = serial.Serial("/dev/ttyACM0", 9600, timeout=1)
    ser.flushInput()
except Exception as e:
    print("Error: No se pudo abrir el puerto serial. Verifica la conexión.")
    raise e

# --- Inicialización de variables ---
# Listas para datos promediados
timeData_avg = []
tempData_avg = []
phData_avg = []
timestamps_avg = []

# Buffers temporales para acumular datos dentro del intervalo
buffer_temp = []
buffer_ph = []

start_time = time.time()
last_avg_time = start_time
# Definir intervalo de promedio (por ejemplo, 30 segundos o 120 para 2 minutos)
avg_interval = 600  # segundos

# Configuración de la gráfica
plt.ion()
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6))
line_temp, = ax1.plot([], [], 'r.-', linewidth=1.5)
ax1.set_title("Temperatura (Promedio)")
ax1.set_xlabel("Tiempo (s)")
ax1.set_ylabel("°C")
ax1.grid(True)

line_ph, = ax2.plot([], [], 'b.-', linewidth=1.5)
ax2.set_title("pH (Promedio)")
ax2.set_xlabel("Tiempo (s)")
ax2.set_ylabel("pH")
ax2.grid(True)

pattern = re.compile(r"Temp:\s*([-+]?\d*\.?\d+),\s*pH:\s*([-+]?\d*\.?\d+)")
print("Inicio de la adquisición. Presione Ctrl+C para detener el programa.")

try:
    while True:
        current_time = time.time()
        if ser.in_waiting > 0:
            try:
                data_line = ser.readline().decode('utf-8').strip()
            except UnicodeDecodeError:
                continue
            if "Temp:" in data_line:
                match = pattern.search(data_line)
                if match:
                    try:
                        temp_val = float(match.group(1))
                        ph_val = float(match.group(2))
                    except ValueError:
                        continue
                    # Acumular datos en el buffer
                    buffer_temp.append(temp_val)
                    buffer_ph.append(ph_val)
        
        # Verificar si el intervalo de promedio se ha cumplido
        if current_time - last_avg_time >= avg_interval:
            if buffer_temp and buffer_ph:
                avg_temp = sum(buffer_temp) / len(buffer_temp)
                avg_ph = sum(buffer_ph) / len(buffer_ph)
                elapsed = current_time - start_time
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                timeData_avg.append(elapsed)
                tempData_avg.append(avg_temp)
                phData_avg.append(avg_ph)
                timestamps_avg.append(timestamp)
                
                # Actualizar las gráficas con los datos promediados
                line_temp.set_data(timeData_avg, tempData_avg)
                ax1.relim()
                ax1.autoscale_view()
                line_ph.set_data(timeData_avg, phData_avg)
                ax2.relim()
                ax2.autoscale_view()
                plt.draw()
                plt.pause(0.01)
                
                # Limpiar los buffers y actualizar el tiempo de último promedio
                buffer_temp = []
                buffer_ph = []
                last_avg_time = current_time
        time.sleep(0.05)
except KeyboardInterrupt:
    print("\nInterrupción detectada. Deteniendo la adquisición y guardando los datos...")
finally:
    ser.close()

# --- Guardar los datos y la gráfica ---
save_folder = r"/home/raspberrypi/Desktop/Maestria"
if not os.path.exists(save_folder):
    os.makedirs(save_folder)
fecha_actual = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
csv_filename = f"datos_sensor_promedio_{fecha_actual}.csv"
csv_path = os.path.join(save_folder, csv_filename)
data_dict = {
    "Fecha_Hora": timestamps_avg,
    "Tiempo_s": timeData_avg,
    "Temperatura_C": tempData_avg,
    "pH": phData_avg
}
df = pd.DataFrame(data_dict)
df.to_csv(csv_path, index=False)
print(f"Datos guardados en '{csv_path}'.")

graph_filename = f"grafica_sensor_promedio_{fecha_actual}.png"
graph_path = os.path.join(save_folder, graph_filename)
fig.savefig(graph_path)
print(f"Gráficas guardadas en '{graph_path}'.")
