#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Logger robusto para sensores (Temp, pH, O2) vía Arduino->Serial en Raspberry Pi.

Características:
- Alias udev: intenta primero /dev/sensorbio, luego /dev/ttyACM*/ttyUSB*.
- Media recortada del 5% por ventana (robusta a outliers).
- Guardado incremental a CSV (rotación diaria), con flush en cada ventana.
- Reintentos de conexión serial con backoff si falla/ se desconecta.
- Modo headless (sin DISPLAY) y opción de gráfica en vivo (--live).
- Logging a archivo en ~/bioreactor_data y también a consola.

Ejemplo de ejecución recomendada (headless, 10 min por ventana):
    python3 logger_bioreactor.py --port /dev/sensorbio --avg-interval 600 --headless
"""

# =========================
# 1) IMPORTS Y UTILIDADES
# =========================
import os
import sys
import time
import re
import math
import argparse
import csv
import glob
import logging
from datetime import datetime, date
from pathlib import Path
from collections import deque

# ---------------------------------------------
# 1.1) Configuración de logging (archivo+consola)
# ---------------------------------------------


def setup_logger(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / \
        f"run_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
    logging.basicConfig(
        filename=str(log_path),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"))
    logging.getLogger().addHandler(console)
    logging.info("==== Inicio de ejecución ====")
    return log_path

# -------------------------------------------------------
# 1.2) Backend seguro para matplotlib (headless si aplica)
# -------------------------------------------------------


def setup_matplotlib(force_headless: bool):
    headless_env = os.environ.get("DISPLAY", "") == ""
    headless = force_headless or headless_env
    if headless:
        import matplotlib
        matplotlib.use("Agg")  # backend sin ventana
    import matplotlib.pyplot as plt
    return headless, plt

# ==========================================
# 2) DETECCIÓN Y GESTIÓN DEL PUERTO SERIAL
# ==========================================


def autodetect_serial(candidates=None):
    """
    Devuelve una lista de puertos candidatos ordenada.
    Prioriza '/dev/sensorbio' (alias udev), luego ttyACM*/ttyUSB*.
    """
    if candidates is None:
        candidates = ["/dev/sensorbio", "/dev/ttyACM*", "/dev/ttyUSB*"]
    ports = []
    for pattern in candidates:
        ports.extend(glob.glob(pattern))
    return sorted(set(ports))


def open_serial(port, baud, timeout=1.0, tries=12):
    """
    Intenta abrir el puerto serial 'tries' veces con backoff.
    """
    import serial
    last_exc = None
    for i in range(tries):
        try:
            ser = serial.Serial(port, baud, timeout=timeout)
            ser.flushInput()
            logging.info(f"Serial abierto: {port} @ {baud}")
            return ser
        except Exception as e:
            last_exc = e
            wait = min(30, 1 + 2*i)
            logging.warning(
                f"No se pudo abrir {port} (intento {i+1}/{tries}): {e}. Reintento en {wait}s")
            time.sleep(wait)
    raise last_exc or RuntimeError(f"No se pudo abrir {port}")


def reopen_serial(current_ser, port, baud):
    """
    Cierra (si existe) y reabre el serial de forma persistente.
    """
    try:
        if current_ser:
            current_ser.close()
    except Exception:
        pass
    # tries alto para insistir si el Arduino "rebota"
    return open_serial(port, baud, timeout=1.0, tries=999)


# ================================
# 3) PARSEO DE LÍNEAS DEL ARDUINO
# ================================
# Formato esperado (insensible a mayúsculas/minúsculas):
# "Temp: 23.45, pH: 6.89, O2: 123.4"
PATTERN = re.compile(
    r"Temp:\s*([-+]?\d*\.?\d+)\s*,\s*pH:\s*([-+]?\d*\.?\d+)\s*,\s*O2:\s*([-+]?\d*\.?\d+)",
    re.IGNORECASE,
)


def parse_line(line: str):
    """
    Extrae (temp, pH, o2) como floats si calza el patrón; de lo contrario, None.
    """
    m = PATTERN.search(line)
    if not m:
        return None
    try:
        t = float(m.group(1))
        ph = float(m.group(2))
        o2 = float(m.group(3))
        return t, ph, o2
    except Exception:
        return None

# ===========================================
# 4) ESTADÍSTICOS ROBUSTOS (MEDIA RECORTADA)
# ===========================================


def median(xs):
    if not xs:
        return float("nan")
    xs_sorted = sorted(xs)
    n = len(xs_sorted)
    mid = n // 2
    return xs_sorted[mid] if n % 2 == 1 else 0.5*(xs_sorted[mid-1] + xs_sorted[mid])


def trimmed_mean(xs, alpha=0.05):
    """
    Media recortada: recorta 'alpha' (5%) en cada cola y promedia el resto.
    Si la ventana es muy pequeña, cae a mediana.
    """
    if not xs:
        return float("nan")
    xs_sorted = sorted(xs)
    n = len(xs_sorted)
    k = int(n * alpha)
    if 2*k >= n:  # si recorte vacía el conjunto, usar mediana
        return median(xs_sorted)
    core = xs_sorted[k:n-k]
    return sum(core) / len(core)


def robust_stats(xs, alpha=0.05):
    """
    Devuelve (central, min, max, std, n) usando media recortada al 5% como 'central'.
    La desviación estándar se calcula respecto al 'central' elegido.
    """
    if not xs:
        return (math.nan, math.nan, math.nan, math.nan, 0)
    mn = min(xs)
    mx = max(xs)
    n = len(xs)
    center = trimmed_mean(xs, alpha=alpha)
    if n > 1:
        var = sum((x-center)**2 for x in xs)/(n-1)
    else:
        var = 0.0
    std = math.sqrt(var)
    return (center, mn, mx, std, n)

# =====================================
# 5) ESCRITURA CSV (ROTACIÓN POR DÍA)
# =====================================


def csv_writer_for_today(out_dir: Path):
    """
    Abre/crea el CSV del día (YYYY-MM-DD) y devuelve (hoy, ruta, file, writer).
    """
    today = date.today().strftime("%Y-%m-%d")
    csv_path = out_dir / f"datos_promedio_{today}.csv"
    is_new = not csv_path.exists()
    f = open(csv_path, "a", newline="")
    fields = [
        "Fecha_Hora", "Tiempo_s",
        "Temp_central", "Temp_min", "Temp_max", "Temp_std", "Temp_n",
        "pH_central", "pH_min", "pH_max", "pH_std", "pH_n",
        "O2_central", "O2_min", "O2_max", "O2_std", "O2_n",
        "metrica_centro", "alpha_recorte"
    ]
    w = csv.DictWriter(f, fieldnames=fields)
    if is_new:
        w.writeheader()
    return today, csv_path, f, w

# =========================
# 6) PROGRAMA PRINCIPAL
# =========================


def main():
    # ---------------------------
    # 6.1) Parámetros de entrada
    # ---------------------------
    ap = argparse.ArgumentParser(
        description="Logger robusto para termopar, pH y O2 (Arduino->RPi)")
    ap.add_argument("--port", default="/dev/sensorbio",
                    help="Puerto serial (ej. /dev/sensorbio o 'auto' para autodetectar)")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--avg-interval", type=int, default=600,  # 10 min por defecto
                    help="Segundos por ventana de promedio")
    ap.add_argument("--out-dir", default=str(Path.home() / "bioreactor_data"))
    ap.add_argument("--headless", action="store_true",
                    help="Forzar modo sin GUI")
    ap.add_argument("--live", action="store_true",
                    help="Mostrar gráfica en vivo (requiere GUI)")
    ap.add_argument("--max-points", type=int, default=1500,
                    help="Máx. ventanas en la gráfica")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    log_path = setup_logger(out_dir)
    headless, plt = setup_matplotlib(args.headless)

    # -------------------------------------
    # 6.2) Selección/auto-detección puerto
    # -------------------------------------
    port = args.port
    if port == "auto":
        ports = autodetect_serial()
        if not ports:
            logging.error(
                "No se detectaron puertos: /dev/sensorbio, /dev/ttyACM* o /dev/ttyUSB*.")
            sys.exit(2)
        port = ports[0]
        logging.info(f"Puerto auto-seleccionado: {port}")

    # -----------------------------
    # 6.3) Apertura del puerto
    # -----------------------------
    try:
        ser = open_serial(port, args.baud, timeout=1.0, tries=20)
    except Exception as e:
        logging.error(f"Fallo al abrir serial: {e}")
        sys.exit(3)

    # --------------------------------------------
    # 6.4) CSV del día y buffers de adquisición
    # --------------------------------------------
    current_day, csv_path, csv_file, writer = csv_writer_for_today(out_dir)
    logging.info(f"Escribiendo en: {csv_path}")

    bufT, bufPH, bufO2 = [], [], []
    start = last_avg = time.time()

    # ------------------------------------------
    # 6.5) Opcional: gráfica en vivo (no headless)
    # ------------------------------------------
    if args.live and not headless:
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(9, 9))
        xs = deque(maxlen=args.max_points)
        ysT = deque(maxlen=args.max_points)
        ysPH = deque(maxlen=args.max_points)
        ysO2 = deque(maxlen=args.max_points)
        lt, = ax1.plot([], [], ".", linewidth=1.0)
        lp, = ax2.plot([], [], ".", linewidth=1.0)
        lo, = ax3.plot([], [], ".", linewidth=1.0)
        for ax, ttl, yl in [(ax1, "Temperatura (media recortada 5%)", "°C"),
                            (ax2, "pH (media recortada 5%)", "pH"),
                            (ax3, "O₂ disuelto (media recortada 5%)", "µg/L")]:
            ax.set_title(ttl)
            ax.set_xlabel("Tiempo (s)")
            ax.set_ylabel(yl)
            ax.grid(True)
        plt.tight_layout()
    else:
        fig = None  # headless o sin live

    # ----------------------------
    # 6.6) Bucle principal
    # ----------------------------
    logging.info("Adquisición iniciada. Ctrl+C para detener.")
    try:
        while True:
            # 6.6.1) Lectura de línea del serial
            try:
                raw = ser.readline().decode("utf-8", errors="ignore").strip()
            except Exception as e:
                logging.warning(
                    f"Fallo al leer serial: {e}. Reintentando apertura...")
                ser = reopen_serial(ser, port, args.baud)
                continue

            if raw:
                parsed = parse_line(raw)
                if parsed is None:
                    # Línea inválida: se registra en debug para no saturar la consola
                    logging.debug(f"Línea no parseable: {raw}")
                else:
                    t, ph, o2 = parsed
                    bufT.append(t)
                    bufPH.append(ph)
                    bufO2.append(o2)

            now = time.time()

            # 6.6.2) Al completar la ventana, calcular y guardar
            if now - last_avg >= args.avg_interval and bufT:
                T_c, T_min, T_max, T_std, T_n = robust_stats(bufT,  alpha=0.05)
                pH_c, pH_min, pH_max, pH_std, pH_n = robust_stats(
                    bufPH, alpha=0.05)
                O2_c, O2_min, O2_max, O2_std, O2_n = robust_stats(
                    bufO2, alpha=0.05)

                elapsed = now - start
                stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                row = {
                    "Fecha_Hora": stamp,
                    "Tiempo_s": round(elapsed, 2),
                    "Temp_central": T_c, "Temp_min": T_min, "Temp_max": T_max, "Temp_std": T_std, "Temp_n": T_n,
                    "pH_central": pH_c, "pH_min": pH_min, "pH_max": pH_max, "pH_std": pH_std, "pH_n": pH_n,
                    "O2_central": O2_c, "O2_min": O2_min, "O2_max": O2_max, "O2_std": O2_std, "O2_n": O2_n,
                    "metrica_centro": "trimmed_mean", "alpha_recorte": 0.05
                }
                writer.writerow(row)
                csv_file.flush()  # persistencia inmediata (crucial para campañas largas)

                # 6.6.3) Rotación diaria de CSV
                today = date.today().strftime("%Y-%m-%d")
                if today != current_day:
                    logging.info("Cambio de día: rotando CSV.")
                    csv_file.close()
                    current_day, csv_path, csv_file, writer = csv_writer_for_today(
                        out_dir)

                # 6.6.4) Actualizar gráfico o snapshot PNG (headless)
                if fig is not None:
                    xs.append(elapsed)
                    ysT.append(T_c)
                    ysPH.append(pH_c)
                    ysO2.append(O2_c)
                    lt.set_data(xs, ysT)
                    ax1.relim()
                    ax1.autoscale_view()
                    lp.set_data(xs, ysPH)
                    ax2.relim()
                    ax2.autoscale_view()
                    lo.set_data(xs, ysO2)
                    ax3.relim()
                    ax3.autoscale_view()
                    plt.pause(0.01)
                else:
                    # Guardar/actualizar PNG simple del día en headless (último punto)
                    png_path = out_dir / f"grafica_promedio_{today}.png"
                    import matplotlib.pyplot as plt2
                    fig2, (a1, a2, a3) = plt2.subplots(3, 1, figsize=(9, 9))
                    for ax, title, val, yl in [
                        (a1, "Temperatura (media recortada 5%)", T_c, "°C"),
                        (a2, "pH (media recortada 5%)", pH_c, "pH"),
                            (a3, "O₂ disuelto (media recortada 5%)", O2_c, "µg/L")]:
                        ax.plot([elapsed], [val], ".")
                        ax.set_title(title)
                        ax.set_xlabel("Tiempo (s)")
                        ax.set_ylabel(yl)
                        ax.grid(True)
                    plt2.tight_layout()
                    fig2.savefig(png_path, dpi=120)
                    plt2.close(fig2)

                # 6.6.5) Reset de buffers y marca de tiempo
                bufT.clear()
                bufPH.clear()
                bufO2.clear()
                last_avg = now

            time.sleep(0.05)  # suaviza uso de CPU

    except KeyboardInterrupt:
        logging.info("Interrupción por usuario: guardando y cerrando.")
    finally:
        try:
            ser.close()
        except Exception:
            pass
        try:
            csv_file.close()
        except Exception:
            pass
        logging.info("Ejecución finalizada. Log en: %s", log_path)


# Punto de entrada
if __name__ == "__main__":
    main()
