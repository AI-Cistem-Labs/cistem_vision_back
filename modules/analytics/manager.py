# modules/analytics/manager.py
import threading
import time
import pandas as pd
import os
from datetime import datetime, timedelta


class AnalyticsManager(threading.Thread):
    def __init__(self, csv_path, comms_module, interval=5):
        super().__init__()
        self.csv_path = csv_path
        self.comms = comms_module
        self.interval = interval
        self.running = False

    def run(self):
        self.running = True
        print("[ANALYTICS] Iniciando análisis de datos...")

        while self.running:
            try:
                self._generate_and_send_stats()
            except Exception as e:
                # Imprimir error detallado para debug
                print(f"[ANALYTICS ERROR] {e}")

            time.sleep(self.interval)

        print("[ANALYTICS] Detenido.")

    def _generate_and_send_stats(self):
        # Verificar si existe y tiene datos
        if not os.path.exists(self.csv_path) or os.path.getsize(self.csv_path) == 0:
            return

        try:
            # Leer CSV
            df = pd.read_csv(self.csv_path)
        except pd.errors.EmptyDataError:
            return

        if df.empty:
            return

        # --- CORRECCIÓN DE NOMBRES DE COLUMNA ---
        # Usamos 'Timestamp' (con mayúscula) tal como lo escribe el módulo de visión
        try:
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        except KeyError:
            print("[ANALYTICS] Error: Columna 'Timestamp' no encontrada en CSV.")
            return

        now = datetime.now()

        # A. Conteo Total
        total_detections = len(df)

        # B. Detecciones en el último minuto
        last_minute = now - timedelta(minutes=1)
        recent_df = df[df['Timestamp'] > last_minute]
        detections_last_min = len(recent_df)

        # C. Clase más detectada (Corregido a 'Class')
        # Usamos 'Class' (con mayúscula)
        if 'Class' in df.columns and not df.empty:
            top_class = df['Class'].mode()[0]
        else:
            top_class = "N/A"

        # 2. Empaquetar datos
        stats_packet = {
            "type": "analytics_update",
            "data": {
                "total_detections": total_detections,
                "ppm": detections_last_min,
                "top_class": top_class,
                "timestamp": now.strftime("%H:%M:%S")
            }
        }

        # 3. Enviar al Dashboard
        self.comms.send_data("analytics_event", stats_packet)

        # LOG DE CONFIRMACIÓN EN TERMINAL DE JETSON
        print(f"[ANALYTICS] Stats enviadas: Total={total_detections}, PPM={detections_last_min}")

    def stop(self):
        self.running = False