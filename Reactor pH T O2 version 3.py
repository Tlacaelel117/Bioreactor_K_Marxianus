import serial
import time
import re
import matplotlib.pyplot as plt
import pandas as pd
import os
from datetime import datetime

# =====================================================
# CONFIGURACION DEL PUERTO SERIAL
# =====================================================
try:
    ser = serial.Serial("/dev/ttyACM0", 115200, timeout=1)
    time.sleep(2)
    ser.flushInput()
except Exception as e:
    print("Error: no se pudo abrir el puerto serial. Verifica la conexion.")
    raise e

# =====================================================
# PARAMETROS DE PRUEBA Y DEPURACION
# =====================================================
DEBUG = True
avg_interval = 60   # segundos

# =====================================================
# INICIALIZACION DE VARIABLES
# =====================================================
timeData_avg = []
tempData_avg = []
phData_avg = []
o2_1Data_avg = []
o2_2Data_avg = []
timestamps_avg = []

buffer_temp = []
buffer_ph = []
buffer_o2_1 = []
buffer_o2_2 = []

start_time = time.time()
last_avg_time = start_time

# =====================================================
# CONFIGURACION DE LA GRAFICA
# =====================================================
plt.ion()
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8, 9))

# Temperatura
line_temp, = ax1.plot([], [], "r.-", linewidth=1.5, label="T")
ax1.set_title("Temperatura promedio")
ax1.set_xlabel("Tiempo (s)")
ax1.set_ylabel("C")
ax1.grid(True)
ax1.legend()

# pH
line_ph, = ax2.plot([], [], "b.-", linewidth=1.5, label="pH")
ax2.set_title("pH promedio")
ax2.set_xlabel("Tiempo (s)")
ax2.set_ylabel("pH")
ax2.grid(True)
ax2.legend()

# Oxigeno disuelto
line_o2_1, = ax3.plot([], [], "g.-", linewidth=1.5, label="O2_1")
line_o2_2, = ax3.plot([], [], "m.-", linewidth=1.5, label="O2_2")
ax3.set_title("Oxigeno disuelto promedio")
ax3.set_xlabel("Tiempo (s)")
ax3.set_ylabel("ug/L")
ax3.grid(True)
ax3.legend()

# =====================================================
# EXPRESION REGULAR
# FORMATO ESPERADO:
# Temp: 25.10, pH: 6.85, O2|1: 1234, O2|2: 1201
# =====================================================
pattern = re.compile(
    r"Temp:\s*([-+]?\d*\.?\d+),\s*"
    r"pH:\s*([-+]?\d*\.?\d+),\s*"
    r"O2\|1:\s*([-+]?\d*\.?\d+),\s*"
    r"O2\|2:\s*([-+]?\d*\.?\d+)"
)

print("Inicio de la adquisicion. Presione Ctrl+C para detener el programa.")

try:
    while True:
        current_time = time.time()

        if ser.in_waiting > 0:
            try:
                data_line = ser.readline().decode("utf-8", errors="ignore").strip()
            except UnicodeDecodeError:
                continue

            if DEBUG:
                print("Linea recibida:", data_line)

            match = pattern.search(data_line)
            if match:
                temp_val = float(match.group(1))
                ph_val = float(match.group(2))
                o2_1_val = float(match.group(3))
                o2_2_val = float(match.group(4))

                buffer_temp.append(temp_val)
                buffer_ph.append(ph_val)
                buffer_o2_1.append(o2_1_val)
                buffer_o2_2.append(o2_2_val)

        # Verificar si se cumplio el intervalo de promedio
        if current_time - last_avg_time >= avg_interval:
            if buffer_temp:
                avg_temp = sum(buffer_temp) / len(buffer_temp)
                avg_ph = sum(buffer_ph) / len(buffer_ph)
                avg_o2_1 = sum(buffer_o2_1) / len(buffer_o2_1)
                avg_o2_2 = sum(buffer_o2_2) / len(buffer_o2_2)

                elapsed = current_time - start_time
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                timeData_avg.append(elapsed)
                tempData_avg.append(avg_temp)
                phData_avg.append(avg_ph)
                o2_1Data_avg.append(avg_o2_1)
                o2_2Data_avg.append(avg_o2_2)
                timestamps_avg.append(timestamp)

                # Actualizar graficas
                line_temp.set_data(timeData_avg, tempData_avg)
                ax1.relim()
                ax1.autoscale_view()

                line_ph.set_data(timeData_avg, phData_avg)
                ax2.relim()
                ax2.autoscale_view()

                line_o2_1.set_data(timeData_avg, o2_1Data_avg)
                line_o2_2.set_data(timeData_avg, o2_2Data_avg)
                ax3.relim()
                ax3.autoscale_view()

                plt.draw()
                plt.pause(0.1)

                print("Promedio guardado:")
                print("  Tiempo (s):", round(elapsed, 2))
                print("  Temperatura:", round(avg_temp, 2))
                print("  pH:", round(avg_ph, 2))
                print("  O2_1:", round(avg_o2_1, 2))
                print("  O2_2:", round(avg_o2_2, 2))

                # Reiniciar buffers
                buffer_temp = []
                buffer_ph = []
                buffer_o2_1 = []
                buffer_o2_2 = []
                last_avg_time = current_time

        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nInterrupcion detectada. Deteniendo la adquisicion y guardando los datos...")

finally:
    ser.close()

# =====================================================
# GUARDAR DATOS Y GRAFICA
# =====================================================
save_folder = r"/home/pi/Desktop/Maestria"
os.makedirs(save_folder, exist_ok=True)

fecha_actual = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# Guardar CSV
csv_path = os.path.join(save_folder, f"datos_sensor_promedio_{fecha_actual}.csv")

df = pd.DataFrame({
    "Fecha_Hora": timestamps_avg,
    "Tiempo_s": timeData_avg,
    "Temperatura_C": tempData_avg,
    "pH": phData_avg,
    "O2_1_ug_L": o2_1Data_avg,
    "O2_2_ug_L": o2_2Data_avg
})

df.to_csv(csv_path, index=False)
print(f"Datos guardados en '{csv_path}'.")

# Guardar grafica
graph_path = os.path.join(save_folder, f"grafica_sensor_promedio_{fecha_actual}.png")
fig.savefig(graph_path)
print(f"Graficas guardadas en '{graph_path}'.")
