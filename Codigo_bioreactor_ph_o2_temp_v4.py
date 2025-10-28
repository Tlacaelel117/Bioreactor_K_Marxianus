import serial
import time
import re
import matplotlib.pyplot as plt
import pandas as pd
import os
from datetime import datetime

# --- Puerto serial ---
try:
    ser = serial.Serial("/dev/ttyACM0", 115200, timeout=1)
    time.sleep(2)
    ser.flushInput()
except Exception as e:
    print("Error al abrir el puerto serial:", e)
    raise

# --- Variables ---
timeData_avg = []
tempData_avg = []
phData_avg = []
o2_1Data_avg = []
o2_2Data_avg = []
timestamps_avg = []

buffer_temp, buffer_ph, buffer_o2_1, buffer_o2_2 = [], [], [], []

start_time = time.time()
last_avg_time = start_time
avg_interval = 600  # segundos

# --- Gráfica en tiempo real ---
plt.ion()
fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(8, 9))

line_temp, = ax1.plot([], [], 'r.-')
ax1.set_title("Temperatura promedio (°C)")
ax1.grid(True)

line_ph, = ax2.plot([], [], 'b.-')
ax2.set_title("pH promedio")
ax2.grid(True)

line_o2_1, = ax3.plot([], [], 'g.-', label="DO1")
line_o2_2, = ax3.plot([], [], 'm.-', label="DO2")
ax3.legend()
ax3.set_title("Oxígeno disuelto promedio (µg/L)")
ax3.grid(True)

# --- Regex compatible con Arduino ---
pattern = re.compile(
    r"T=([-+]?\d*\.?\d+).*pH=([-+]?\d*\.?\d+).*DO1=([-+]?\d*\.?\d+).*DO2=([-+]?\d*\.?\d+)"
)

print("Adquisición iniciada. Presione Ctrl+C para detener.")

try:
    while True:
        if ser.in_waiting > 0:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            match = pattern.search(line)
            if match:
                temp_val = float(match.group(1))
                ph_val   = float(match.group(2))
                o2_1_val = float(match.group(3))
                o2_2_val = float(match.group(4))

                buffer_temp.append(temp_val)
                buffer_ph.append(ph_val)
                buffer_o2_1.append(o2_1_val)
                buffer_o2_2.append(o2_2_val)

        current_time = time.time()
        if current_time - last_avg_time >= avg_interval and buffer_temp:
            avg_temp = sum(buffer_temp) / len(buffer_temp)
            avg_ph   = sum(buffer_ph) / len(buffer_ph)
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

            # Actualizar gráfica
            line_temp.set_data(timeData_avg, tempData_avg)
            ax1.relim(); ax1.autoscale_view()

            line_ph.set_data(timeData_avg, phData_avg)
            ax2.relim(); ax2.autoscale_view()

            line_o2_1.set_data(timeData_avg, o2_1Data_avg)
            line_o2_2.set_data(timeData_avg, o2_2Data_avg)
            ax3.relim(); ax3.autoscale_view()

            plt.draw()
            plt.pause(0.01)

            # Reiniciar buffers
            buffer_temp.clear()
            buffer_ph.clear()
            buffer_o2_1.clear()
            buffer_o2_2.clear()
            last_avg_time = current_time

        time.sleep(0.05)

except KeyboardInterrupt:
    print("\nInterrupción detectada. Guardando datos...")
finally:
    ser.close()

# --- Guardar datos ---
save_folder = "/home/pi/Desktop/Maestria"
os.makedirs(save_folder, exist_ok=True)
fecha = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

csv_path = os.path.join(save_folder, f"datos_sensor_promedio_{fecha}.csv")
df = pd.DataFrame({
    "Fecha_Hora": timestamps_avg,
    "Tiempo_s": timeData_avg,
    "Temperatura_C": tempData_avg,
    "pH": phData_avg,
    "DO1_ug_L": o2_1Data_avg,
    "DO2_ug_L": o2_2Data_avg
})
df.to_csv(csv_path, index=False)
print(f"Datos guardados en {csv_path}")

graph_path = os.path.join(save_folder, f"grafica_sensor_promedio_{fecha}.png")
fig.savefig(graph_path)
print(f"Gráfica guardada en {graph_path}")
